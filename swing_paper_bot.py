from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd

from swing_forward_evaluation import evaluate_swing_signal_bars
from swing_forward_runner import load_swing_signal_bars
from swing_forward_store import SWING_STRATEGY_VERSION
from swing_risk_engine import apply_swing_risk_engine, validate_risk_decision
from trading_assistant import swing_order_plan_fingerprint


PAPER_BOT_SCHEMA_VERSION = 1
PAPER_BOT_VERSION = "swing-autonomous-paper-bot-2026.08.18-v1"
DEFAULT_SWING_PAPER_DB_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_SWING_PAPER_DB_PATH",
        Path(__file__).resolve().parent / "runtime" / "swing_paper_bot.sqlite3",
    )
)
BarsLoader = Callable[[dict, pd.Timestamp], tuple[pd.DataFrame, str, str]]


def _clean(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (Path, date, datetime, pd.Timestamp)):
        return value.isoformat()
    item = getattr(value, "item", None)
    return _clean(item()) if callable(item) else value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _clean(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_paper_bot_store(path: Path = DEFAULT_SWING_PAPER_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS paper_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_cycles(
                cycle_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL,
                scope TEXT NOT NULL, snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_cycle_events(
                event_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES paper_cycles(cycle_id),
                event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL, event_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_signals(
                signal_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES paper_cycles(cycle_id),
                setup_id TEXT NOT NULL, symbol TEXT NOT NULL, signal_at TEXT NOT NULL,
                strategy_version TEXT NOT NULL, snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL, UNIQUE(strategy_version, setup_id)
            );
            CREATE TABLE IF NOT EXISTS paper_events(
                event_id TEXT PRIMARY KEY, signal_id TEXT NOT NULL REFERENCES paper_signals(signal_id),
                event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, source_key TEXT NOT NULL,
                payload_json TEXT NOT NULL, event_fingerprint TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS paper_cycles_no_update BEFORE UPDATE ON paper_cycles
            BEGIN SELECT RAISE(ABORT, 'paper cycles append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_cycles_no_delete BEFORE DELETE ON paper_cycles
            BEGIN SELECT RAISE(ABORT, 'paper cycles append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_cycle_events_no_update BEFORE UPDATE ON paper_cycle_events
            BEGIN SELECT RAISE(ABORT, 'paper cycle events append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_cycle_events_no_delete BEFORE DELETE ON paper_cycle_events
            BEGIN SELECT RAISE(ABORT, 'paper cycle events append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_signals_no_update BEFORE UPDATE ON paper_signals
            BEGIN SELECT RAISE(ABORT, 'paper signals append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_signals_no_delete BEFORE DELETE ON paper_signals
            BEGIN SELECT RAISE(ABORT, 'paper signals append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_events_no_update BEFORE UPDATE ON paper_events
            BEGIN SELECT RAISE(ABORT, 'paper events append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_events_no_delete BEFORE DELETE ON paper_events
            BEGIN SELECT RAISE(ABORT, 'paper events append-only'); END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM paper_meta WHERE key='schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO paper_meta(key,value) VALUES('schema_version',?)",
                (str(PAPER_BOT_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != PAPER_BOT_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstützte Paper-Bot-Datenbankversion.")


def _append_cycle_event(
    cycle_id: str, event_type: str, occurred_at: object, payload: Mapping[str, object], path: Path
) -> bool:
    normalized = {**dict(payload), "paper_only": True, "broker_order_sent": False}
    fingerprint = _fingerprint(normalized)
    event_id = _fingerprint(
        {"cycle_id": cycle_id, "event_type": event_type, "occurred_at": str(occurred_at), "payload": normalized}
    )
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT 1 FROM paper_cycle_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if existing:
            return False
        connection.execute(
            "INSERT INTO paper_cycle_events VALUES(?,?,?,?,?,?)",
            (event_id, cycle_id, event_type, str(occurred_at), _canonical_json(normalized), fingerprint),
        )
    return True


def _append_paper_event(
    signal_id: str,
    event_type: str,
    occurred_at: object,
    source_key: str,
    payload: Mapping[str, object],
    path: Path,
) -> bool:
    normalized = {**dict(payload), "paper_only": True, "broker_order_sent": False}
    fingerprint = _fingerprint(normalized)
    event_id = _fingerprint(
        {"signal_id": signal_id, "source_key": source_key, "payload_fingerprint": fingerprint}
    )
    with _connect(path) as connection:
        if connection.execute("SELECT 1 FROM paper_events WHERE event_id=?", (event_id,)).fetchone():
            return False
        connection.execute(
            "INSERT INTO paper_events VALUES(?,?,?,?,?,?,?)",
            (
                event_id, signal_id, str(event_type), str(occurred_at), str(source_key),
                _canonical_json(normalized), fingerprint,
            ),
        )
    return True


def load_paper_signals(path: Path = DEFAULT_SWING_PAPER_DB_PATH) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_paper_bot_store(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT signal_id,setup_id,snapshot_json FROM paper_signals ORDER BY signal_at,signal_id"
        ).fetchall()
        events = connection.execute(
            "SELECT * FROM paper_events ORDER BY occurred_at,event_id"
        ).fetchall()
    by_signal: dict[str, list[dict]] = {}
    for row in events:
        by_signal.setdefault(str(row["signal_id"]), []).append(
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "source_key": str(row["source_key"]),
                "payload": json.loads(str(row["payload_json"])),
            }
        )
    return [
        {
            "signal_id": str(row["signal_id"]),
            "setup_id": str(row["setup_id"]),
            "snapshot": json.loads(str(row["snapshot_json"])),
            "events": by_signal.get(str(row["signal_id"]), []),
        }
        for row in rows
    ]


def _terminal(signal: Mapping[str, object]) -> bool:
    plan = dict((signal.get("snapshot") or {}).get("order_plan") or {})
    types = {"paper_risk_rejected", "entry_missed", "invalidated_before_entry", "expired_without_entry", "stop_reached"}
    types.add("target_2_reached" if plan.get("target_2_original") is not None else "target_1_reached")
    return any(event.get("event_type") in types for event in signal.get("events") or [])


def derive_paper_position_state(signal: Mapping[str, object]) -> dict:
    snapshot = dict(signal.get("snapshot") or {})
    events = list(signal.get("events") or [])
    plan = dict(snapshot.get("order_plan") or {})
    position = dict(snapshot.get("position_size") or {})
    quantity = float(position.get("quantity") or 0)
    event_types = [str(event.get("event_type") or "") for event in events]
    if "paper_risk_rejected" in event_types:
        status = "risk_rejected"
        remaining_fraction = 0.0
    elif _terminal(signal):
        status = "closed_or_unfilled"
        remaining_fraction = 0.0
    elif "target_1_reached" in event_types and plan.get("target_2_original") is not None:
        status = "partial_position_open"
        remaining_fraction = float(plan.get("target_2_exit_fraction") or 0.5)
    elif "paper_entry_opened" in event_types:
        status = "position_open"
        remaining_fraction = 1.0
    else:
        status = "virtual_order_pending"
        remaining_fraction = 1.0
    return {
        "status": status,
        "initial_quantity": quantity,
        "remaining_quantity": quantity * remaining_fraction,
        "remaining_fraction": remaining_fraction,
        "reserved_exposure_eur": float(position.get("position_value_eur") or 0)
        * remaining_fraction,
        "reserved_risk_eur": float(position.get("actual_risk_eur") or 0)
        * remaining_fraction,
        "reconstructed_from_append_only_events": True,
    }


def paper_portfolio_state(path: Path = DEFAULT_SWING_PAPER_DB_PATH) -> dict:
    exposure = 0.0
    risk = 0.0
    reserved = 0
    for signal in load_paper_signals(path):
        position_state = derive_paper_position_state(signal)
        if position_state["remaining_fraction"] <= 0:
            continue
        exposure += float(position_state["reserved_exposure_eur"])
        risk += float(position_state["reserved_risk_eur"])
        reserved += 1
    return {"reserved_or_active": reserved, "exposure_eur": exposure, "risk_eur": risk}


def _paper_snapshot(candidate: Mapping[str, object], scan_result: Mapping[str, object]) -> dict:
    order_plan = dict(candidate.get("order_plan") or {})
    if order_plan.get("plan_fingerprint") != swing_order_plan_fingerprint(order_plan):
        raise ValueError("Paper-Orderplan besitzt keinen gültigen Fingerabdruck.")
    validate_risk_decision(candidate, required_mode="paper_only")
    observed_at = str(scan_result.get("last_scan") or "")
    symbol = str(candidate.get("symbol") or "").upper()
    if not observed_at or not symbol:
        raise ValueError("Paper-Signal benötigt Zeitpunkt und Ticker.")
    return {
        "paper_bot_version": PAPER_BOT_VERSION,
        "evidence_kind": "autonomous_paper_bot",
        "paper_only": True,
        "shadow_only": False,
        "broker_adapter_present": False,
        "broker_order_allowed": False,
        "broker_order_sent": False,
        "signal_at": observed_at,
        "asset": {
            "ticker": symbol,
            "name": candidate.get("asset_name"),
            "asset_type": candidate.get("asset_type"),
            "listing": dict(candidate.get("universe_metadata") or {}),
            "trade_republic": dict(candidate.get("trade_republic") or {}),
        },
        "strategy": {
            "strategy_version": SWING_STRATEGY_VERSION,
            "strategy_name": "Long-v1",
            "setup_type": candidate.get("setup_type"),
            "unchanged_production_baseline": True,
        },
        "risk_decision": dict(candidate["risk_decision"]),
        "position_size": dict(candidate.get("position_size") or {}),
        "order_plan": order_plan,
        "trade_republic_execution_plan": dict(candidate.get("trade_republic_execution_plan") or {}),
        "source_scan": {
            "scope": str(scan_result.get("scan_scope") or "unknown"),
            "universe_version": str((scan_result.get("universe_report") or {}).get("version") or "unknown"),
            "market_data_sources": ["Yahoo Finance/yfinance"],
        },
    }


def record_paper_scan_cycle(
    scan_result: Mapping[str, object],
    settings: Mapping[str, object],
    *,
    path: Path = DEFAULT_SWING_PAPER_DB_PATH,
) -> dict:
    initialize_paper_bot_store(path)
    observed_at = str(scan_result.get("last_scan") or "")
    scope = str(scan_result.get("scan_scope") or "unknown")
    if not observed_at:
        raise ValueError("Paper-Zyklus benötigt einen Scanzeitpunkt.")
    cycle_snapshot = {
        "paper_bot_version": PAPER_BOT_VERSION,
        "evidence_kind": "autonomous_paper_bot_cycle",
        "paper_only": True,
        "broker_order_allowed": False,
        "observed_at": observed_at,
        "scope": scope,
        "settings": dict(settings),
        "source_scan_fingerprint": _fingerprint(dict(scan_result)),
    }
    cycle_id = _fingerprint(
        {"paper_bot_version": PAPER_BOT_VERSION, "observed_at": observed_at, "scope": scope}
    )
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT snapshot_fingerprint FROM paper_cycles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        snapshot_fingerprint = _fingerprint(cycle_snapshot)
        if existing is None:
            connection.execute(
                "INSERT INTO paper_cycles VALUES(?,?,?,?,?)",
                (cycle_id, observed_at, scope, _canonical_json(cycle_snapshot), snapshot_fingerprint),
            )
        elif str(existing["snapshot_fingerprint"]) != snapshot_fingerprint:
            raise ValueError("Paper-Zyklus existiert mit abweichendem Eingabestand.")
    _append_cycle_event(cycle_id, "cycle_started", observed_at, {}, path)
    state = paper_portfolio_state(path)
    inserted = existing_count = rejected = failures = 0
    candidates = [
        *list(scan_result.get("approved") or []),
        *list(scan_result.get("shadow_signals") or []),
    ]
    for raw_candidate in candidates:
        try:
            raw_plan = dict(raw_candidate.get("order_plan") or {})
            setup_id = str(
                raw_candidate.get("setup_id") or raw_plan.get("plan_fingerprint") or ""
            )
            if not setup_id:
                raise ValueError("Paper-Signal besitzt keine stabile Setup-ID.")
            with _connect(path) as connection:
                prior = connection.execute(
                    "SELECT 1 FROM paper_signals WHERE strategy_version=? AND setup_id=?",
                    (SWING_STRATEGY_VERSION, setup_id),
                ).fetchone()
            if prior is not None:
                existing_count += 1
                continue
            candidate = apply_swing_risk_engine(
                raw_candidate,
                settings,
                current_exposure_eur=float(state["exposure_eur"]),
                current_risk_eur=float(state["risk_eur"]),
                execution_mode="paper_only",
            )
            snapshot = _paper_snapshot(candidate, scan_result)
            signal_id = _fingerprint(
                {"evidence_kind": "autonomous_paper_bot", "strategy_version": SWING_STRATEGY_VERSION, "setup_id": setup_id}
            )
            encoded = _canonical_json(snapshot)
            fingerprint = _fingerprint(snapshot)
            with _connect(path) as connection:
                existing_signal = connection.execute(
                    "SELECT snapshot_fingerprint FROM paper_signals WHERE signal_id=?", (signal_id,)
                ).fetchone()
                if existing_signal is None:
                    connection.execute(
                        "INSERT INTO paper_signals VALUES(?,?,?,?,?,?,?,?)",
                        (
                            signal_id, cycle_id, setup_id, snapshot["asset"]["ticker"], observed_at,
                            SWING_STRATEGY_VERSION, encoded, fingerprint,
                        ),
                    )
                    inserted += 1
                elif str(existing_signal["snapshot_fingerprint"]) == fingerprint:
                    existing_count += 1
                else:
                    raise ValueError("Paper-Signal existiert mit abweichendem unveränderbarem Snapshot.")
            if not candidate["risk_decision"]["approved"]:
                _append_paper_event(
                    signal_id, "paper_risk_rejected", observed_at,
                    f"risk:{candidate['risk_decision']['decision_fingerprint']}",
                    {"reason": candidate["risk_decision"]["reason"]}, path,
                )
                rejected += 1
                continue
            state["exposure_eur"] += float((candidate.get("position_size") or {}).get("position_value_eur") or 0)
            state["risk_eur"] += float((candidate.get("position_size") or {}).get("actual_risk_eur") or 0)
            _append_paper_event(
                signal_id, "virtual_order_created", observed_at,
                f"order:{snapshot['order_plan']['plan_fingerprint']}",
                {"order_plan_fingerprint": snapshot["order_plan"]["plan_fingerprint"]}, path,
            )
        except Exception as exc:
            failures += 1
            _append_cycle_event(
                cycle_id, "candidate_failed_closed", observed_at,
                {"symbol": str(raw_candidate.get("symbol") or ""), "error": f"{type(exc).__name__}: {exc}"}, path,
            )
    _append_cycle_event(
        cycle_id, "cycle_completed", observed_at,
        {"signals_inserted": inserted, "signals_existing": existing_count, "risk_rejected": rejected, "failures": failures}, path,
    )
    return {
        "cycle_id": cycle_id,
        "signals_inserted": inserted,
        "signals_existing": existing_count,
        "risk_rejected": rejected,
        "failures": failures,
        "paper_only": True,
        "broker_order_sent": False,
    }


def run_paper_bot_evaluations(
    *,
    path: Path = DEFAULT_SWING_PAPER_DB_PATH,
    evaluated_at: object = None,
    bars_loader: BarsLoader = load_swing_signal_bars,
) -> dict:
    now = pd.Timestamp(evaluated_at or datetime.now().astimezone())
    signals = load_paper_signals(path)
    summary = {"signals_total": len(signals), "checked": 0, "terminal_skipped": 0, "events_inserted": 0, "events_existing": 0, "data_failures": 0, "errors": []}
    for signal in signals:
        if _terminal(signal):
            summary["terminal_skipped"] += 1
            continue
        snapshot = dict(signal["snapshot"])
        validate_risk_decision(snapshot, required_mode="paper_only")
        if not snapshot["risk_decision"].get("approved"):
            summary["terminal_skipped"] += 1
            continue
        summary["checked"] += 1
        try:
            frame, interval, source = bars_loader(snapshot, now)
            if frame.empty or not interval:
                reason = source or "Keine belastbaren Kursdaten verfügbar."
                stored = _append_paper_event(
                    str(signal["signal_id"]), "data_error_fail_closed", now.isoformat(),
                    f"data-error:{now.date().isoformat()}:{_fingerprint(reason)[:16]}",
                    {"reason": reason, "new_virtual_position_allowed": False, "retry_allowed": True}, path,
                )
                summary["events_inserted" if stored else "events_existing"] += 1
                summary["data_failures"] += 1
                continue
            candidates = evaluate_swing_signal_bars(snapshot, frame, interval=interval, evaluated_at=now)
            for event in candidates:
                payload = {**dict(event["payload"]), "market_data_source": source}
                stored = _append_paper_event(
                    str(signal["signal_id"]), str(event["event_type"]), event["occurred_at"],
                    str(event["source_key"]), payload, path,
                )
                summary["events_inserted" if stored else "events_existing"] += 1
        except Exception as exc:
            summary["errors"].append(f"{(snapshot.get('asset') or {}).get('ticker')}: {exc}")
    summary["paper_only"] = True
    summary["broker_order_sent"] = False
    summary["store_audit"] = paper_bot_store_audit(path)
    return summary


def paper_bot_store_audit(path: Path = DEFAULT_SWING_PAPER_DB_PATH) -> dict:
    if not Path(path).exists():
        return {"status": "not_created", "cycles": 0, "signals": 0, "events": 0}
    initialize_paper_bot_store(path)
    with _connect(path) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("paper_cycles", "paper_signals", "paper_events", "paper_cycle_events")
        }
        invalid = int(
            connection.execute(
                "SELECT COUNT(*) FROM paper_signals WHERE snapshot_json NOT LIKE '%\"paper_only\":true%' OR snapshot_json LIKE '%\"broker_order_allowed\":true%'"
            ).fetchone()[0]
        )
    return {
        "status": "ok" if quick_check == "ok" and invalid == 0 else "attention",
        "quick_check": quick_check,
        "cycles": counts["paper_cycles"],
        "signals": counts["paper_signals"],
        "events": counts["paper_events"],
        "cycle_events": counts["paper_cycle_events"],
        "invalid_execution_flags": invalid,
        "append_only": True,
        "paper_only": True,
        "broker_order_sent": False,
    }
