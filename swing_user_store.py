from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from trading_assistant import SWING_STOP_CONTRACT_VERSION, swing_order_plan_fingerprint


SWING_USER_SCHEMA_VERSION = 1
SWING_USER_TRADE_VERSION = "swing-user-trade-2026.08.11-v2"
SWING_USER_EVENT_VERSION = "swing-user-event-2026.08.09-v1"
DEFAULT_SWING_USER_DB_PATH = Path(__file__).resolve().parent / "runtime" / "swing_user_trades.sqlite3"
LOCAL_MARKET_TIMEZONE = ZoneInfo("Europe/Berlin")


class SwingUserTradeDeviationConfirmationRequired(ValueError):
    def __init__(self, deviations: list[str]) -> None:
        self.deviations = list(deviations)
        super().__init__("Abweichungen vom Systemplan müssen ausdrücklich bestätigt werden: " + " | ".join(deviations))


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _comparable_timestamp(value: object, label: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ValueError
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(LOCAL_MARKET_TIMEZONE)
        return timestamp
    except Exception as exc:
        raise ValueError(f"{label} ist ungültig.") from exc


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (Path, date, datetime, pd.Timestamp)):
        return value.isoformat()
    item = getattr(value, "item", None)
    if callable(item):
        return _clean(item())
    return value


def _canonical_json(payload: dict) -> str:
    return json.dumps(
        _clean(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_swing_user_store(path: Path = DEFAULT_SWING_USER_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_trades (
                user_trade_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL,
                UNIQUE (signal_id)
            );
            CREATE TABLE IF NOT EXISTS user_trade_events (
                event_id TEXT PRIMARY KEY,
                user_trade_id TEXT NOT NULL REFERENCES user_trades(user_trade_id),
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                source_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL,
                UNIQUE (user_trade_id, source_key)
            );
            CREATE TRIGGER IF NOT EXISTS user_trades_no_update
            BEFORE UPDATE ON user_trades BEGIN
                SELECT RAISE(ABORT, 'user_trades is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS user_trades_no_delete
            BEFORE DELETE ON user_trades BEGIN
                SELECT RAISE(ABORT, 'user_trades is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS user_trade_events_no_update
            BEFORE UPDATE ON user_trade_events BEGIN
                SELECT RAISE(ABORT, 'user_trade_events is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS user_trade_events_no_delete
            BEFORE DELETE ON user_trade_events BEGIN
                SELECT RAISE(ABORT, 'user_trade_events is append-only');
            END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM user_meta WHERE key = 'schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO user_meta (key, value) VALUES ('schema_version', ?)",
                (str(SWING_USER_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != SWING_USER_SCHEMA_VERSION:
            raise RuntimeError(
                f"Nicht unterstütztes Nutzertrade-Schema {existing['value']}; erwartet {SWING_USER_SCHEMA_VERSION}."
            )


def assess_user_trade_deviations(
    signal_snapshot: dict,
    actual_entry_eur: float,
    quantity: float,
    opened_at: object,
) -> list[str]:
    plan = dict(signal_snapshot.get("order_plan") or {})
    entry = _number(actual_entry_eur)
    units = _number(quantity)
    if entry is None or entry <= 0 or units is None or units <= 0:
        raise ValueError("Tatsächlicher Einstieg und Stückzahl müssen größer als null sein.")
    opened = _comparable_timestamp(opened_at, "Einstiegszeitpunkt")
    signal_at = signal_snapshot.get("signal_at")
    if signal_at and opened <= _comparable_timestamp(signal_at, "Signalzeitpunkt"):
        raise ValueError("Der tatsächliche Einstieg muss nach dem gespeicherten Signalzeitpunkt liegen.")
    deviations: list[str] = []
    earliest = plan.get("earliest_entry_day")
    valid_until = plan.get("valid_until")
    maximum = _number(plan.get("maximum_entry_eur"))
    initial_stop = _number(plan.get("initial_stop_eur"))
    if initial_stop is None or initial_stop <= 0:
        raise ValueError("Der initiale System-Stop fehlt.")
    if entry <= initial_stop:
        raise ValueError(
            f"Der tatsächliche Einstieg {entry:.2f} EUR liegt nicht über dem System-Stop "
            f"{initial_stop:.2f} EUR. Dieser Trade kann nicht als handelbar bestätigt werden."
        )
    planned_quantity = _number(plan.get("quantity"))
    if earliest and opened.date() < pd.Timestamp(earliest).date():
        deviations.append("Einstieg liegt vor dem frühesten erlaubten Handelstag.")
    if valid_until and opened.date() > pd.Timestamp(valid_until).date():
        deviations.append("Einstieg liegt nach Ablauf des Systemplans.")
    if maximum is not None and entry > maximum:
        deviations.append(f"Einstieg {entry:.2f} EUR liegt über dem Maximalpreis {maximum:.2f} EUR.")
    if planned_quantity is None:
        deviations.append("Der Systemplan enthielt ohne Tradingkapital keine berechnete Stückzahl.")
    elif not math.isclose(units, planned_quantity, rel_tol=0.01, abs_tol=1e-9):
        deviations.append(
            f"Stückzahl {units:g} weicht von der Systemgröße {planned_quantity:g} ab."
        )
    asset_type = str((signal_snapshot.get("asset") or {}).get("asset_type") or "")
    if asset_type in {"Aktie", "ETF"} and not math.isclose(units, round(units), abs_tol=1e-9):
        deviations.append("Bruchstücke bei Aktie/ETF weichen von der konservativen Ganzstück-Planung ab.")
    return deviations


def create_swing_user_trade(
    signal_id: str,
    signal_snapshot: dict,
    actual_entry_eur: float,
    quantity: float,
    opened_at: object,
    *,
    note: str = "",
    confirm_deviations: bool = False,
    path: Path = DEFAULT_SWING_USER_DB_PATH,
) -> dict:
    plan = dict(signal_snapshot.get("order_plan") or {})
    if str(plan.get("plan_fingerprint") or "") != swing_order_plan_fingerprint(plan):
        raise ValueError("Der unveränderbare Systemplan besitzt keinen gültigen Fingerabdruck.")
    tr_execution = dict(signal_snapshot.get("trade_republic_execution") or {})
    tr_listing = dict(tr_execution.get("tr_listing") or {})
    analysis_listing = dict(tr_execution.get("analysis_listing") or {})
    if tr_execution.get("status") != "TR handelbar" or not tr_execution.get("execution_ready"):
        raise ValueError(
            "Ein persönlicher Swing-Trade darf nur mit einem verifizierten, ausführbaren "
            "Trade-Republic-Plan gespeichert werden."
        )
    if not tr_listing.get("isin") or tr_listing.get("isin") != analysis_listing.get("isin"):
        raise ValueError(
            "Die ISIN des TR-Ausführungslistings stimmt nicht mit dem analysierten Instrument überein."
        )
    if not tr_listing.get("exchange") or str(tr_listing.get("currency") or "").upper() != "EUR":
        raise ValueError(
            "Das konkrete TR-Ausführungslisting mit EUR-Kurs und Handelsplatz ist nicht vollständig."
        )
    execution_source = str(tr_execution.get("price_source") or "")
    if not execution_source or "yahoo" in execution_source.casefold():
        raise ValueError(
            "Yahoo- oder Fremdbörsenkurse dürfen nicht als Trade-Republic-Ausführungspreis dienen."
        )
    if (
        _number(tr_execution.get("analysis_comparison_price_eur")) is None
        or float(tr_execution.get("analysis_comparison_price_eur") or 0) <= 0
        or not str(tr_execution.get("analysis_price_source") or "").strip()
    ):
        raise ValueError(
            "Der zeitgleiche Analyse-Vergleichskurs für die TR-Listing-Basis fehlt."
        )
    deviations = assess_user_trade_deviations(signal_snapshot, actual_entry_eur, quantity, opened_at)
    if deviations and not confirm_deviations:
        raise SwingUserTradeDeviationConfirmationRequired(deviations)
    entry = float(actual_entry_eur)
    units = float(quantity)
    opened = pd.Timestamp(opened_at).isoformat()
    initial_stop = _number(plan.get("initial_stop_eur"))
    if initial_stop is None or initial_stop <= 0:
        raise ValueError("Der initiale System-Stop fehlt.")
    snapshot = {
        "user_trade_version": SWING_USER_TRADE_VERSION,
        "signal_id": str(signal_id),
        "source": "Vom Nutzer extern ausgeführter und anschließend lokal bestätigter Trade",
        "broker_order_sent": False,
        "opened_at": opened,
        "actual_entry_eur": entry,
        "initial_quantity": units,
        "initial_stop_eur": initial_stop,
        "stop_contract_version": str(plan.get("stop_contract_version") or SWING_STOP_CONTRACT_VERSION),
        "system_plan_fingerprint": str(plan["plan_fingerprint"]),
        "asset": dict(signal_snapshot.get("asset") or {}),
        "strategy": dict(signal_snapshot.get("strategy") or {}),
        "system_order_plan": plan,
        "trade_republic_execution": tr_execution,
        "deviations": deviations,
        "deviation_confirmed": bool(deviations and confirm_deviations),
        "note": str(note or "")[:2_000],
    }
    identity = f"{signal_id}|{opened}|{entry:.12g}|{units:.12g}"
    user_trade_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    fingerprint = _fingerprint(snapshot)
    initialize_swing_user_store(path)
    with _connect(Path(path)) as connection:
        by_signal = connection.execute(
            "SELECT user_trade_id, snapshot_fingerprint FROM user_trades WHERE signal_id = ?",
            (str(signal_id),),
        ).fetchone()
        if by_signal is not None:
            if by_signal["user_trade_id"] == user_trade_id and by_signal["snapshot_fingerprint"] == fingerprint:
                return {"user_trade_id": user_trade_id, "inserted": False, "deviations": deviations}
            raise ValueError("Für dieses objektive Paper-Signal existiert bereits ein persönlicher Nutzertrade.")
        connection.execute(
            """
            INSERT INTO user_trades (
                user_trade_id, signal_id, opened_at, snapshot_json, snapshot_fingerprint
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (user_trade_id, str(signal_id), opened, _canonical_json(snapshot), fingerprint),
        )
    return {"user_trade_id": user_trade_id, "inserted": True, "deviations": deviations}


def _load_raw(path: Path) -> list[dict]:
    initialize_swing_user_store(path)
    with _connect(Path(path)) as connection:
        trades = connection.execute(
            "SELECT user_trade_id, snapshot_json FROM user_trades ORDER BY opened_at, user_trade_id"
        ).fetchall()
        events = connection.execute(
            """
            SELECT user_trade_id, event_id, event_type, occurred_at, source_key, payload_json
            FROM user_trade_events ORDER BY occurred_at, event_id
            """
        ).fetchall()
    by_trade: dict[str, list[dict]] = {}
    for row in events:
        wrapper = json.loads(row["payload_json"])
        by_trade.setdefault(str(row["user_trade_id"]), []).append(
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "source_key": str(row["source_key"]),
                "payload": dict(wrapper.get("payload") or {}),
            }
        )
    return [
        {
            "user_trade_id": str(row["user_trade_id"]),
            "snapshot": json.loads(row["snapshot_json"]),
            "events": by_trade.get(str(row["user_trade_id"]), []),
        }
        for row in trades
    ]


def _state(trade: dict) -> dict:
    snapshot = dict(trade["snapshot"])
    quantity = float(snapshot["initial_quantity"])
    remaining = quantity
    stop = float(snapshot["initial_stop_eur"])
    realized = 0.0
    status = "Aktiv"
    for event in trade.get("events") or []:
        payload = dict(event.get("payload") or {})
        if event.get("event_type") == "stop_tightened":
            stop = float(payload["new_stop_eur"])
        elif event.get("event_type") == "partial_sale":
            sold = float(payload["quantity"])
            remaining = max(remaining - sold, 0.0)
            realized += (float(payload["exit_eur"]) - float(snapshot["actual_entry_eur"])) * sold
        elif event.get("event_type") == "closed":
            sold = remaining
            realized += (float(payload["exit_eur"]) - float(snapshot["actual_entry_eur"])) * sold
            remaining = 0.0
            status = "Geschlossen"
    return {
        **trade,
        "status": status,
        "current_stop_eur": stop,
        "remaining_quantity": remaining,
        "realized_pnl_eur": realized,
    }


def load_swing_user_trade_states(path: Path = DEFAULT_SWING_USER_DB_PATH) -> list[dict]:
    return [_state(trade) for trade in _load_raw(Path(path))]


def swing_user_trade_guidance(
    state: dict,
    current_price_eur: float,
    observed_at: object = None,
    *,
    market_context: dict | None = None,
) -> dict:
    current = _number(current_price_eur)
    snapshot = dict(state.get("snapshot") or {})
    plan = dict(snapshot.get("system_order_plan") or {})
    entry = _number(snapshot.get("actual_entry_eur"))
    remaining = _number(state.get("remaining_quantity"))
    stop = _number(state.get("current_stop_eur"))
    target_1 = _number(plan.get("target_1_eur"))
    target_2 = _number(plan.get("target_2_eur"))
    if current is None or entry is None or remaining is None or remaining <= 0 or stop is None:
        return {
            "status": "Daten derzeit nicht belastbar",
            "reason": "Aktueller Kurs oder unveränderbare Trade-Marken fehlen.",
            "automatic_order_execution": False,
        }
    initial_stop = _number(snapshot.get("initial_stop_eur")) or stop
    initial_risk = entry - initial_stop
    unrealized = (current - entry) * remaining
    context = dict(market_context or {})
    structure_break = bool(context.get("structure_break"))
    high_volume_structure_break = bool(context.get("high_volume_structure_break"))
    trend_broken = bool(context.get("trend_broken"))
    confirmed_thesis_break = bool(context.get("confirmed_thesis_break"))
    event_days = _number(context.get("days_to_known_event"))
    strategy = dict(snapshot.get("strategy") or {})
    setup_type = str(strategy.get("setup_type") or "")
    activation = _number(plan.get("activation_price_eur"))
    context_close = _number(context.get("close_eur"))
    if current <= stop:
        status = "Notausstieg empfohlen"
        reason = "Der aktuelle Kurs liegt am oder unter dem bestätigten Stop. Die App handelt nicht; ein tatsächlicher Ausstieg muss extern erfolgen und danach bestätigt werden."
    elif confirmed_thesis_break:
        status = "Notausstieg empfohlen"
        reason = "Eine ausdrücklich bestätigte schwere Änderung des Trade-Grunds liegt vor. Ausstieg extern prüfen; die App führt keine Order aus."
    elif high_volume_structure_break:
        status = "Notausstieg empfohlen"
        reason = "Der letzte abgeschlossene Kurs hat die 20-Tage-Unterstützung mit erhöhtem Verkaufsvolumen gebrochen. Regelbasierten Ausstieg extern prüfen."
    elif structure_break:
        status = "Regelbasierte Anpassung empfohlen"
        reason = "Der letzte abgeschlossene Kurs liegt unter der vorherigen 20-Tage-Unterstützung. Stop und Ausstiegsregel prüfen; den Stop niemals erweitern."
    elif "Ausbruch" in setup_type and activation is not None and context_close is not None and context_close < activation:
        status = "Erhöhte Aufmerksamkeit"
        reason = "Das Ausbruchssetup liegt auf Schlusskursbasis wieder unter seiner Aktivierungsmarke. Fehlausbruch und bestätigten Stop eng prüfen."
    elif event_days is not None and event_days <= 1:
        status = "Regelbasierte Anpassung empfohlen"
        reason = "Ein bestätigtes Unternehmensereignis liegt innerhalb eines Tages. Positionsrisiko nach dem gespeicherten Plan prüfen; keine automatische Order."
    elif target_2 is not None and current >= target_2:
        status = "Regelbasierte Anpassung empfohlen"
        reason = "Das zweite Systemziel wurde erreicht oder überschritten; vollständigen Ausstieg prüfen und extern selbst ausführen."
    elif target_1 is not None and current >= target_1:
        status = "Regelbasierte Anpassung empfohlen"
        reason = "Das erste Systemziel wurde erreicht; vorher vorgesehenen Teilgewinn und einen engeren Stop prüfen."
    elif initial_risk > 0 and current >= entry + initial_risk:
        status = "Regelbasierte Anpassung empfohlen"
        reason = "Der offene Gewinn entspricht mindestens dem anfänglichen Risiko; Stop auf Einstand oder unter ein bestätigtes höheres Tief prüfen."
    elif initial_risk > 0 and current <= entry - initial_risk * 0.5:
        status = "Erhöhte Aufmerksamkeit"
        reason = "Der Kurs hat mindestens die Hälfte des anfänglichen Risikobudgets abgegeben; Stop und Setup-Struktur eng beobachten, aber den Stop niemals erweitern."
    elif trend_broken:
        status = "Erhöhte Aufmerksamkeit"
        reason = "Der letzte abgeschlossene Kurs liegt unter dem 20-Tage-Trend. Das allein löst keinen Verkauf aus, verlangt aber eine engere Strukturprüfung."
    else:
        status = "Plan intakt"
        reason = "Bestätigter Stop und nächste Zielmarke sind nicht erreicht. Keine spontane Regeländerung erforderlich."
    return {
        "status": status,
        "reason": reason,
        "current_price_eur": current,
        "unrealized_pnl_eur": unrealized,
        "unrealized_pnl_pct": (current - entry) / entry * 100 if entry > 0 else None,
        "observed_at": pd.Timestamp(observed_at or datetime.now().astimezone()).isoformat(),
        "monitor_version": context.get("version"),
        "market_context_quality": context.get("data_quality", "nur aktueller Kurs"),
        "checked_factors": list(context.get("checked_factors") or ["aktueller Kurs", "Stop", "Ziele"]),
        "unavailable_factors": list(context.get("unavailable_factors") or []),
        "automatic_order_execution": False,
    }


def _append_event(
    user_trade_id: str,
    event_type: str,
    occurred_at: object,
    payload: dict,
    path: Path,
) -> dict:
    occurred = pd.Timestamp(occurred_at).isoformat()
    source_payload = {
        "event_version": SWING_USER_EVENT_VERSION,
        "user_trade_id": str(user_trade_id),
        "event_type": event_type,
        "occurred_at": occurred,
        "payload": dict(payload),
        "broker_order_sent": False,
    }
    fingerprint = _fingerprint(source_payload)
    source_key = hashlib.sha256(_canonical_json(source_payload).encode("utf-8")).hexdigest()
    event_id = hashlib.sha256(f"{user_trade_id}|{source_key}".encode("utf-8")).hexdigest()
    initialize_swing_user_store(path)
    with _connect(Path(path)) as connection:
        if connection.execute(
            "SELECT 1 FROM user_trades WHERE user_trade_id = ?", (user_trade_id,)
        ).fetchone() is None:
            raise ValueError("Der persönliche Nutzertrade existiert nicht.")
        existing = connection.execute(
            "SELECT event_fingerprint FROM user_trade_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if existing is not None:
            if existing["event_fingerprint"] != fingerprint:
                raise ValueError("Nutzertrade-Ereignis besitzt einen Identitätskonflikt.")
            return {"event_id": event_id, "inserted": False}
        connection.execute(
            """
            INSERT INTO user_trade_events (
                event_id, user_trade_id, event_type, occurred_at, source_key,
                payload_json, event_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                user_trade_id,
                event_type,
                occurred,
                source_key,
                _canonical_json(source_payload),
                fingerprint,
            ),
        )
    return {"event_id": event_id, "inserted": True}


def tighten_swing_user_stop(
    user_trade_id: str,
    new_stop_eur: float,
    occurred_at: object,
    path: Path = DEFAULT_SWING_USER_DB_PATH,
) -> dict:
    state = next(
        (item for item in load_swing_user_trade_states(path) if item["user_trade_id"] == user_trade_id),
        None,
    )
    if state is None or state["status"] != "Aktiv":
        raise ValueError("Nur ein aktiver persönlicher Trade kann den Stop nachziehen.")
    new_stop = _number(new_stop_eur)
    if new_stop is None or new_stop <= float(state["current_stop_eur"]):
        raise ValueError("Der Long-Stop darf nur strikt angehoben und niemals erweitert werden.")
    return _append_event(
        user_trade_id,
        "stop_tightened",
        occurred_at,
        {"previous_stop_eur": state["current_stop_eur"], "new_stop_eur": new_stop},
        Path(path),
    )


def record_swing_user_partial_sale(
    user_trade_id: str,
    quantity: float,
    exit_eur: float,
    occurred_at: object,
    path: Path = DEFAULT_SWING_USER_DB_PATH,
) -> dict:
    state = next(
        (item for item in load_swing_user_trade_states(path) if item["user_trade_id"] == user_trade_id),
        None,
    )
    sold = _number(quantity)
    price = _number(exit_eur)
    if state is None or state["status"] != "Aktiv":
        raise ValueError("Nur ein aktiver persönlicher Trade kann einen Teilverkauf erhalten.")
    if sold is None or sold <= 0 or sold >= float(state["remaining_quantity"]):
        raise ValueError("Teilverkaufsmenge muss größer als null und kleiner als die Restmenge sein.")
    if price is None or price <= 0:
        raise ValueError("Teilverkaufskurs muss größer als null sein.")
    return _append_event(
        user_trade_id,
        "partial_sale",
        occurred_at,
        {"quantity": sold, "exit_eur": price},
        Path(path),
    )


def close_swing_user_trade(
    user_trade_id: str,
    exit_eur: float,
    occurred_at: object,
    path: Path = DEFAULT_SWING_USER_DB_PATH,
) -> dict:
    state = next(
        (item for item in load_swing_user_trade_states(path) if item["user_trade_id"] == user_trade_id),
        None,
    )
    price = _number(exit_eur)
    if state is None or state["status"] != "Aktiv":
        raise ValueError("Nur ein aktiver persönlicher Trade kann geschlossen werden.")
    if price is None or price <= 0:
        raise ValueError("Ausstiegskurs muss größer als null sein.")
    return _append_event(
        user_trade_id,
        "closed",
        occurred_at,
        {"exit_eur": price, "remaining_quantity": state["remaining_quantity"]},
        Path(path),
    )


def swing_user_store_audit(path: Path = DEFAULT_SWING_USER_DB_PATH) -> dict:
    initialize_swing_user_store(path)
    invalid: list[str] = []
    with _connect(Path(path)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        trades = connection.execute(
            "SELECT user_trade_id, snapshot_json, snapshot_fingerprint FROM user_trades"
        ).fetchall()
        events = connection.execute(
            "SELECT event_id, payload_json, event_fingerprint FROM user_trade_events"
        ).fetchall()
    for row in trades:
        try:
            if _fingerprint(json.loads(row["snapshot_json"])) != row["snapshot_fingerprint"]:
                invalid.append(f"trade:{row['user_trade_id']}")
        except Exception:
            invalid.append(f"trade:{row['user_trade_id']}:json")
    for row in events:
        try:
            if _fingerprint(json.loads(row["payload_json"])) != row["event_fingerprint"]:
                invalid.append(f"event:{row['event_id']}")
        except Exception:
            invalid.append(f"event:{row['event_id']}:json")
    return {
        "schema_version": SWING_USER_SCHEMA_VERSION,
        "quick_check": quick_check,
        "trades": len(trades),
        "events": len(events),
        "invalid_count": len(invalid),
        "status": "ok" if quick_check == "ok" and not invalid else "attention",
    }
