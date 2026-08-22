from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from trading_assistant import swing_order_plan_fingerprint


SWING_FORWARD_SCHEMA_VERSION = 2
SWING_SIGNAL_SCHEMA_VERSION = "swing-forward-signal-2026.08.16-v3"
SWING_EVENT_SCHEMA_VERSION = "swing-forward-event-2026.08.09-v1"
SWING_REJECTION_CONTROL_SCHEMA_VERSION = "swing-rejection-control-2026.08.16-v1"
SWING_STRATEGY_VERSION = "swing-long-pullback-breakout-2026.08.11-v3"
DEFAULT_SWING_FORWARD_DB_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_SWING_FORWARD_DB_PATH",
        Path(__file__).resolve().parent / "runtime" / "swing_forward.sqlite3",
    )
)

ALLOWED_EVENT_TYPES = {
    "activation_checked",
    "paper_entry_opened",
    "entry_missed",
    "invalidated_before_entry",
    "expired_without_entry",
    "target_1_reached",
    "target_2_reached",
    "stop_reached",
    "still_active",
    "ambiguous_sequence",
    "not_evaluable",
    "historical_fx_valuation",
    "counterfactual_outcome",
}


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    raise TypeError(f"Nicht JSON-kompatibler Wert: {type(value).__name__}")


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return _clean(item())
    if isinstance(value, (Path, date, datetime)):
        return _json_default(value)
    return value


def _canonical_json(payload: dict) -> str:
    return json.dumps(
        _clean(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
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


def initialize_swing_forward_store(path: Path = DEFAULT_SWING_FORWARD_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS swing_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS swing_scans (
                scan_id TEXT PRIMARY KEY,
                observed_at TEXT NOT NULL,
                source_kind TEXT NOT NULL CHECK (source_kind = 'real_forward_scan'),
                universe_version TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status = 'completed'),
                snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS swing_signals (
                signal_id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL REFERENCES swing_scans(scan_id),
                setup_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_at TEXT NOT NULL,
                plan_fingerprint TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL,
                UNIQUE (scan_id, setup_id)
            );

            CREATE TABLE IF NOT EXISTS swing_events (
                event_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL REFERENCES swing_signals(signal_id),
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                source_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL,
                UNIQUE (signal_id, source_key)
            );

            CREATE TABLE IF NOT EXISTS swing_rejection_controls (
                control_id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL REFERENCES swing_scans(scan_id),
                symbol TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL,
                UNIQUE (scan_id, symbol, signal_day)
            );

            CREATE TABLE IF NOT EXISTS swing_rejection_control_events (
                event_id TEXT PRIMARY KEY,
                control_id TEXT NOT NULL REFERENCES swing_rejection_controls(control_id),
                horizon_sessions INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL,
                UNIQUE (control_id, horizon_sessions)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_swing_signals_setup_unique
            ON swing_signals(setup_id);

            CREATE TRIGGER IF NOT EXISTS swing_scans_no_update
            BEFORE UPDATE ON swing_scans BEGIN
                SELECT RAISE(ABORT, 'swing_scans is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_scans_no_delete
            BEFORE DELETE ON swing_scans BEGIN
                SELECT RAISE(ABORT, 'swing_scans is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_signals_no_update
            BEFORE UPDATE ON swing_signals BEGIN
                SELECT RAISE(ABORT, 'swing_signals is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_signals_no_delete
            BEFORE DELETE ON swing_signals BEGIN
                SELECT RAISE(ABORT, 'swing_signals is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_events_no_update
            BEFORE UPDATE ON swing_events BEGIN
                SELECT RAISE(ABORT, 'swing_events is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_events_no_delete
            BEFORE DELETE ON swing_events BEGIN
                SELECT RAISE(ABORT, 'swing_events is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_rejection_controls_no_update
            BEFORE UPDATE ON swing_rejection_controls BEGIN
                SELECT RAISE(ABORT, 'swing_rejection_controls is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_rejection_controls_no_delete
            BEFORE DELETE ON swing_rejection_controls BEGIN
                SELECT RAISE(ABORT, 'swing_rejection_controls is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_rejection_control_events_no_update
            BEFORE UPDATE ON swing_rejection_control_events BEGIN
                SELECT RAISE(ABORT, 'swing_rejection_control_events is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS swing_rejection_control_events_no_delete
            BEFORE DELETE ON swing_rejection_control_events BEGIN
                SELECT RAISE(ABORT, 'swing_rejection_control_events is append-only');
            END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM swing_meta WHERE key = 'schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO swing_meta (key, value) VALUES ('schema_version', ?)",
                (str(SWING_FORWARD_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) == 1 and SWING_FORWARD_SCHEMA_VERSION == 2:
            connection.execute(
                "UPDATE swing_meta SET value = ? WHERE key = 'schema_version'",
                (str(SWING_FORWARD_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != SWING_FORWARD_SCHEMA_VERSION:
            raise RuntimeError(
                f"Nicht unterstütztes Swing-Forward-Schema {existing['value']}; erwartet {SWING_FORWARD_SCHEMA_VERSION}."
            )


def _scan_snapshot(scan_result: dict) -> dict:
    statistics = dict(scan_result.get("statistics") or {})
    universe = dict(scan_result.get("universe_report") or {})
    observed_at = str(scan_result.get("last_scan") or "").strip()
    if not observed_at:
        raise ValueError("Der echte Swing-Scan besitzt keinen Scanzeitpunkt.")
    technical_failures = []
    for item in scan_result.get("prefilter_rejected") or []:
        reasons = [str(reason) for reason in (item.get("Ablehnungsgründe") or [])]
        if any("Kursdaten" in reason or "Daten" in reason for reason in reasons):
            technical_failures.append(
                {
                    "ticker": str(item.get("Ticker") or ""),
                    "asset": str(item.get("Asset") or ""),
                    "reasons": reasons,
                }
            )
    return {
        "schema_version": SWING_SIGNAL_SCHEMA_VERSION,
        "source_kind": "real_forward_scan",
        "observed_at": observed_at,
        "status": "completed",
        "scan_scope": str(scan_result.get("scan_scope") or "manual_full"),
        "objective_forward": bool(scan_result.get("objective_forward", False)),
        "universe_version": str(universe.get("version") or "unbekannt"),
        "universe_path": str(universe.get("path") or ""),
        "strategy_version": SWING_STRATEGY_VERSION,
        "statistics": {
            "universe_size": int(statistics.get("universe_size") or 0),
            "loaded_assets": int(statistics.get("loaded_assets") or 0),
            "failed_downloads": int(statistics.get("failed_downloads") or 0),
            "prefilter_passed_total": int(statistics.get("prefilter_passed_total") or 0),
            "prefilter_candidates": int(statistics.get("prefilter_candidates") or 0),
            "fully_evaluated": int(statistics.get("fully_evaluated") or 0),
            "approved_trades": len(scan_result.get("approved") or []),
            "strategy_qualified_total": int(
                statistics.get("strategy_qualified_total")
                or len(scan_result.get("approved") or []) + len(scan_result.get("shadow_signals") or [])
            ),
            "shadow_signals": len(scan_result.get("shadow_signals") or []),
            "rejection_controls": len(scan_result.get("rejection_controls") or []),
        },
        "deep_analysis_policy": str(
            scan_result.get("deep_analysis_policy") or "legacy_unknown"
        ),
        "asset_type_funnel": dict(scan_result.get("asset_type_funnel") or {}),
        "asset_type_bias_audit": dict(scan_result.get("asset_type_bias_audit") or {}),
        "portfolio_cluster_audit": dict(scan_result.get("portfolio_cluster_audit") or {}),
        "market_label": str(scan_result.get("market_label") or "Nicht verfügbar"),
        "thresholds": dict(scan_result.get("thresholds") or {}),
        "prefilter_thresholds": dict(scan_result.get("prefilter_thresholds") or {}),
        "risk_policy": dict(scan_result.get("risk_policy") or {}),
        "errors": [str(item) for item in (scan_result.get("errors") or [])],
        "technical_failures": technical_failures,
        "background_run": dict(scan_result.get("background_run") or {}),
        "contains_zero_trade_result": not bool(scan_result.get("approved")),
        "contains_zero_strategy_signal": not bool(
            (scan_result.get("approved") or []) or (scan_result.get("shadow_signals") or [])
        ),
    }


def _scan_id(snapshot: dict) -> str:
    identity = (
        f"real_forward_scan|{snapshot['observed_at']}|{snapshot['universe_version']}|{snapshot['scan_scope']}|"
        f"{snapshot['strategy_version']}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _signal_snapshot(scan_id: str, scan_snapshot: dict, setup: dict) -> dict:
    order_plan = dict(setup.get("order_plan") or {})
    stored_plan_fingerprint = str(order_plan.get("plan_fingerprint") or "")
    if not stored_plan_fingerprint or stored_plan_fingerprint != swing_order_plan_fingerprint(order_plan):
        raise ValueError(f"{setup.get('symbol', 'Unbekannt')}: Orderplan-Fingerabdruck ist ungültig.")
    if "position_calculated" not in order_plan:
        raise ValueError(f"{setup.get('symbol', 'Unbekannt')}: Orderplan ist noch nicht finalisiert.")
    setup_id = str(setup.get("setup_id") or "").strip()
    symbol = str(setup.get("symbol") or "").strip().upper()
    if not setup_id or not symbol:
        raise ValueError("Ein Swing-Signal benötigt Setup-ID und Ticker.")
    metadata = dict(setup.get("universe_metadata") or {})
    tr_reference = dict(setup.get("trade_republic") or {})
    tr_price = dict(setup.get("trade_republic_price") or {})
    tr_execution_plan = dict(setup.get("trade_republic_execution_plan") or {})
    asset_id = str(metadata.get("asset_id") or f"{metadata.get('version', 'unbekannt')}|{symbol}")
    return {
        "signal_schema_version": SWING_SIGNAL_SCHEMA_VERSION,
        "source_kind": "real_forward_scan",
        "immutable": True,
        "scan_id": scan_id,
        "signal_at": scan_snapshot["observed_at"],
        "setup_id": setup_id,
        "asset": {
            "asset_id": asset_id,
            "name": str(setup.get("asset_name") or symbol),
            "ticker": symbol,
            "isin": metadata.get("isin"),
            "exchange": metadata.get("exchange"),
            "asset_type": str(setup.get("asset_type") or metadata.get("asset_type") or "Unbekannt"),
            "original_currency": str(setup.get("original_currency") or "Unbekannt"),
            "region": metadata.get("region"),
            "category": metadata.get("category"),
        },
        "strategy": {
            "strategy_version": SWING_STRATEGY_VERSION,
            "setup_type": str(setup.get("setup_type") or ""),
            "direction": str(setup.get("direction") or "Long"),
            "market_phase": str(setup.get("market_phase") or "Nicht verfügbar"),
            "quality_score": setup.get("quality_score"),
            "buy_signal": setup.get("buy_signal"),
            "asset_quality": setup.get("asset_quality"),
            "confidence": setup.get("confidence"),
            "historical_cases": setup.get("historical_cases"),
            "historical_hit_rate": setup.get("historical_hit_rate"),
            "known_event_date_at_signal": setup.get("known_event_date_at_signal"),
            "event_days_at_signal": setup.get("event_days_at_signal"),
            "volatility_regime": str(setup.get("volatility_regime") or "Nicht verfügbar"),
        },
        "forward_evidence": {
            "kind": str(setup.get("forward_evidence_kind") or "scanner_released"),
            "scanner_qualified": bool(setup.get("scanner_qualified", True)),
            "user_portfolio_released": str(
                setup.get("forward_evidence_kind") or "scanner_released"
            )
            == "scanner_released",
            "exclusion_reason": setup.get("forward_exclusion_reason"),
            "separate_from_historical_walk_forward": True,
        },
        "order_plan": order_plan,
        "trade_republic": {
            "status": str(tr_reference.get("status") or "unbekannt"),
            "status_source": tr_reference.get("status_source"),
            "status_recorded_at": tr_reference.get("status_recorded_at"),
            "analysis_listing_key": tr_reference.get("analysis_listing_key"),
            "analysis_listing": dict(tr_reference.get("analysis_listing") or {}),
            "tr_listing_key": tr_reference.get("tr_listing_key"),
            "tr_listing": dict(tr_reference.get("tr_listing") or {}),
            "execution_ready_at_signal": bool(tr_execution_plan),
            "execution_price": (
                {
                    "price_eur": tr_price.get("price_eur"),
                    "observed_at": tr_price.get("observed_at"),
                    "source": tr_price.get("source"),
                    "analysis_comparison_price_eur": tr_price.get(
                        "analysis_comparison_price_eur"
                    ),
                    "analysis_price_source": tr_price.get("analysis_price_source"),
                }
                if tr_price.get("available")
                else None
            ),
            "execution_plan": tr_execution_plan or None,
            "automatic_detection": False,
            "broker_connection": False,
        },
        "data_contract": {
            "price_source": "Yahoo Finance über yfinance",
            "scan_interval": "1d",
            "history_window": "1y",
            "signal_bar_day": order_plan.get("signal_bar_day"),
            "no_market_data_before_signal": True,
            "automatic_order_execution": False,
        },
        "universe": {
            "version": metadata.get("version") or scan_snapshot["universe_version"],
            "source_group": metadata.get("source_group"),
            "liquidity_class": metadata.get("liquidity_class"),
        },
    }


def record_swing_forward_scan(
    scan_result: dict,
    path: Path = DEFAULT_SWING_FORWARD_DB_PATH,
) -> dict:
    initialize_swing_forward_store(path)
    scan_snapshot = _scan_snapshot(scan_result)
    scan_id = _scan_id(scan_snapshot)
    scan_fingerprint = _fingerprint(scan_snapshot)
    signal_rows: list[tuple[str, dict, str]] = []
    signal_setups = [
        *(scan_result.get("approved") or []),
        *(scan_result.get("shadow_signals") or []),
    ]
    for setup in signal_setups:
        snapshot = _signal_snapshot(scan_id, scan_snapshot, setup)
        setup_id = str(snapshot["setup_id"])
        signal_identity = f"{scan_id}|{setup_id}|{snapshot['order_plan']['plan_fingerprint']}"
        signal_id = hashlib.sha256(signal_identity.encode("utf-8")).hexdigest()
        signal_rows.append((signal_id, snapshot, _fingerprint(snapshot)))
    control_rows: list[tuple[str, dict, str]] = []
    for raw_control in scan_result.get("rejection_controls") or []:
        control = dict(raw_control)
        symbol = str(control.get("ticker") or "").strip().upper()
        signal_day = str(control.get("signal_day") or "")
        sampling_key = str(control.get("sampling_key") or "")
        if not symbol or not signal_day or not sampling_key:
            raise ValueError("Eine Ablehnungs-Kontrollprobe benötigt Ticker, Signaltag und Sampling-Schlüssel.")
        snapshot = {
            "control_schema_version": SWING_REJECTION_CONTROL_SCHEMA_VERSION,
            "immutable": True,
            "scan_id": scan_id,
            "strategy_version": scan_snapshot["strategy_version"],
            **control,
            "control_only": True,
            "not_a_trade_signal": True,
            "automatic_order_execution": False,
        }
        control_id = hashlib.sha256(f"{scan_id}|{sampling_key}".encode("utf-8")).hexdigest()
        control_rows.append((control_id, snapshot, _fingerprint(snapshot)))

    inserted_signals = 0
    existing_signals = 0
    signal_ids_by_setup: dict[str, str] = {}
    inserted_controls = 0
    existing_controls = 0
    with _connect(Path(path)) as connection:
        existing_scan = connection.execute(
            "SELECT snapshot_fingerprint FROM swing_scans WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        if existing_scan is not None and existing_scan["snapshot_fingerprint"] != scan_fingerprint:
            raise ValueError("Ein Scan mit derselben Identität besitzt abweichende unveränderbare Daten.")
        if existing_scan is None:
            connection.execute(
                """
                INSERT INTO swing_scans (
                    scan_id, observed_at, source_kind, universe_version, strategy_version,
                    status, snapshot_json, snapshot_fingerprint
                ) VALUES (?, ?, 'real_forward_scan', ?, ?, 'completed', ?, ?)
                """,
                (
                    scan_id,
                    scan_snapshot["observed_at"],
                    scan_snapshot["universe_version"],
                    scan_snapshot["strategy_version"],
                    _canonical_json(scan_snapshot),
                    scan_fingerprint,
                ),
            )
        for signal_id, snapshot, snapshot_fingerprint in signal_rows:
            existing_setup = connection.execute(
                "SELECT signal_id FROM swing_signals WHERE setup_id = ?",
                (snapshot["setup_id"],),
            ).fetchone()
            if existing_setup is not None:
                signal_ids_by_setup[str(snapshot["setup_id"])] = str(existing_setup["signal_id"])
                existing_signals += 1
                continue
            existing_signal = connection.execute(
                "SELECT snapshot_fingerprint FROM swing_signals WHERE signal_id = ?", (signal_id,)
            ).fetchone()
            if existing_signal is not None:
                if existing_signal["snapshot_fingerprint"] != snapshot_fingerprint:
                    raise ValueError("Ein Signal mit derselben Identität besitzt abweichende unveränderbare Daten.")
                continue
            connection.execute(
                """
                INSERT INTO swing_signals (
                    signal_id, scan_id, setup_id, symbol, signal_at, plan_fingerprint,
                    snapshot_json, snapshot_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_id,
                    scan_id,
                    snapshot["setup_id"],
                    snapshot["asset"]["ticker"],
                    snapshot["signal_at"],
                    snapshot["order_plan"]["plan_fingerprint"],
                    _canonical_json(snapshot),
                    snapshot_fingerprint,
                ),
            )
            inserted_signals += 1
            signal_ids_by_setup[str(snapshot["setup_id"])] = signal_id
        for control_id, snapshot, snapshot_fingerprint in control_rows:
            existing_control = connection.execute(
                "SELECT snapshot_fingerprint FROM swing_rejection_controls WHERE control_id = ?",
                (control_id,),
            ).fetchone()
            if existing_control is not None:
                if existing_control["snapshot_fingerprint"] != snapshot_fingerprint:
                    raise ValueError("Eine Kontrollprobe mit derselben Identität besitzt abweichende Daten.")
                existing_controls += 1
                continue
            connection.execute(
                """
                INSERT INTO swing_rejection_controls (
                    control_id, scan_id, symbol, signal_day, snapshot_json, snapshot_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    control_id,
                    scan_id,
                    snapshot["ticker"],
                    snapshot["signal_day"],
                    _canonical_json(snapshot),
                    snapshot_fingerprint,
                ),
            )
            inserted_controls += 1
    return {
        "scan_id": scan_id,
        "scan_inserted": existing_scan is None,
        "signals_total": len(signal_rows),
        "signals_inserted": inserted_signals,
        "signals_existing": existing_signals,
        "signal_ids_by_setup": signal_ids_by_setup,
        "zero_trade_scan": not bool(scan_result.get("approved") or []),
        "zero_strategy_signal_scan": not signal_rows,
        "released_signals": len(scan_result.get("approved") or []),
        "shadow_signals": len(scan_result.get("shadow_signals") or []),
        "rejection_controls_total": len(control_rows),
        "rejection_controls_inserted": inserted_controls,
        "rejection_controls_existing": existing_controls,
    }


def append_swing_signal_event(
    signal_id: str,
    event_type: str,
    occurred_at: object,
    source_key: str,
    payload: dict,
    path: Path = DEFAULT_SWING_FORWARD_DB_PATH,
) -> dict:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unbekannter Swing-Ereignistyp: {event_type}")
    source = str(source_key).strip()
    if not source:
        raise ValueError("Ein Swing-Ereignis benötigt einen stabilen Quellschlüssel.")
    occurred = str(occurred_at) if isinstance(occurred_at, str) else str(_json_default(occurred_at))
    event_payload = {
        "event_schema_version": SWING_EVENT_SCHEMA_VERSION,
        "signal_id": str(signal_id),
        "event_type": event_type,
        "occurred_at": occurred,
        "source_key": source,
        "payload": dict(payload),
    }
    event_fingerprint = _fingerprint(event_payload)
    event_id = hashlib.sha256(f"{signal_id}|{source}".encode("utf-8")).hexdigest()
    initialize_swing_forward_store(path)
    with _connect(Path(path)) as connection:
        if connection.execute(
            "SELECT 1 FROM swing_signals WHERE signal_id = ?", (signal_id,)
        ).fetchone() is None:
            raise ValueError("Das zugehörige unveränderbare Swing-Signal existiert nicht.")
        existing = connection.execute(
            "SELECT event_fingerprint FROM swing_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if existing is not None:
            if existing["event_fingerprint"] != event_fingerprint:
                raise ValueError("Der Ereignisschlüssel wurde bereits mit anderen Daten verwendet.")
            return {"event_id": event_id, "inserted": False}
        connection.execute(
            """
            INSERT INTO swing_events (
                event_id, signal_id, event_type, occurred_at, source_key,
                payload_json, event_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                signal_id,
                event_type,
                occurred,
                source,
                _canonical_json(event_payload),
                event_fingerprint,
            ),
        )
    return {"event_id": event_id, "inserted": True}


def append_swing_rejection_control_event(
    control_id: str,
    horizon_sessions: int,
    occurred_at: object,
    payload: dict,
    path: Path = DEFAULT_SWING_FORWARD_DB_PATH,
) -> dict:
    horizon = int(horizon_sessions)
    if horizon <= 0:
        raise ValueError("Der Kontrollhorizont muss positiv sein.")
    occurred = str(occurred_at) if isinstance(occurred_at, str) else str(_json_default(occurred_at))
    event_payload = {
        "event_schema_version": SWING_REJECTION_CONTROL_SCHEMA_VERSION,
        "control_id": str(control_id),
        "horizon_sessions": horizon,
        "occurred_at": occurred,
        "payload": {
            **dict(payload),
            "control_only": True,
            "not_a_trade_result": True,
            "automatic_rule_change": False,
        },
    }
    event_fingerprint = _fingerprint(event_payload)
    event_id = hashlib.sha256(f"{control_id}|{horizon}".encode("utf-8")).hexdigest()
    initialize_swing_forward_store(path)
    with _connect(Path(path)) as connection:
        if connection.execute(
            "SELECT 1 FROM swing_rejection_controls WHERE control_id = ?", (control_id,)
        ).fetchone() is None:
            raise ValueError("Die zugehörige Ablehnungs-Kontrollprobe existiert nicht.")
        existing = connection.execute(
            "SELECT event_fingerprint FROM swing_rejection_control_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if existing is not None:
            if existing["event_fingerprint"] != event_fingerprint:
                raise ValueError("Der Kontrollhorizont wurde bereits mit anderen Daten verwendet.")
            return {"event_id": event_id, "inserted": False}
        connection.execute(
            """
            INSERT INTO swing_rejection_control_events (
                event_id, control_id, horizon_sessions, occurred_at, payload_json, event_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                control_id,
                horizon,
                occurred,
                _canonical_json(event_payload),
                event_fingerprint,
            ),
        )
    return {"event_id": event_id, "inserted": True}


def load_swing_rejection_controls(
    path: Path = DEFAULT_SWING_FORWARD_DB_PATH,
) -> list[dict]:
    initialize_swing_forward_store(path)
    with _connect(Path(path)) as connection:
        controls = connection.execute(
            "SELECT control_id, snapshot_json FROM swing_rejection_controls ORDER BY signal_day, control_id"
        ).fetchall()
        events = connection.execute(
            """
            SELECT control_id, event_id, horizon_sessions, occurred_at, payload_json
            FROM swing_rejection_control_events
            ORDER BY occurred_at, horizon_sessions, event_id
            """
        ).fetchall()
    by_control: dict[str, list[dict]] = {}
    for row in events:
        payload = json.loads(row["payload_json"])
        by_control.setdefault(str(row["control_id"]), []).append(
            {
                "event_id": str(row["event_id"]),
                "horizon_sessions": int(row["horizon_sessions"]),
                "occurred_at": str(row["occurred_at"]),
                "payload": dict(payload.get("payload") or {}),
            }
        )
    return [
        {
            "control_id": str(row["control_id"]),
            "snapshot": json.loads(row["snapshot_json"]),
            "events": by_control.get(str(row["control_id"]), []),
        }
        for row in controls
    ]


def load_swing_forward_signals(path: Path = DEFAULT_SWING_FORWARD_DB_PATH) -> list[dict]:
    initialize_swing_forward_store(path)
    with _connect(Path(path)) as connection:
        signal_rows = connection.execute(
            "SELECT signal_id, snapshot_json FROM swing_signals ORDER BY signal_at, signal_id"
        ).fetchall()
        event_rows = connection.execute(
            """
            SELECT signal_id, event_id, event_type, occurred_at, source_key, payload_json
            FROM swing_events
            ORDER BY occurred_at,
                CASE event_type
                    WHEN 'paper_entry_opened' THEN 10
                    WHEN 'target_1_reached' THEN 20
                    WHEN 'target_2_reached' THEN 30
                    WHEN 'stop_reached' THEN 30
                    WHEN 'structure_invalidated' THEN 30
                    WHEN 'expired_unfilled' THEN 30
                    WHEN 'expired_time_exit' THEN 30
                    WHEN 'historical_fx_valuation' THEN 100
                    ELSE 90
                END,
                event_id
            """
        ).fetchall()
    events_by_signal: dict[str, list[dict]] = {}
    for row in event_rows:
        payload = json.loads(row["payload_json"])
        events_by_signal.setdefault(str(row["signal_id"]), []).append(
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "source_key": str(row["source_key"]),
                "payload": dict(payload.get("payload") or {}),
            }
        )
    return [
        {
            "signal_id": str(row["signal_id"]),
            "snapshot": json.loads(row["snapshot_json"]),
            "events": events_by_signal.get(str(row["signal_id"]), []),
        }
        for row in signal_rows
    ]


def load_swing_forward_scans(path: Path = DEFAULT_SWING_FORWARD_DB_PATH) -> list[dict]:
    initialize_swing_forward_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT scan_id, observed_at, snapshot_json FROM swing_scans ORDER BY observed_at, scan_id"
        ).fetchall()
    return [
        {
            "scan_id": str(row["scan_id"]),
            "observed_at": str(row["observed_at"]),
            "snapshot": json.loads(row["snapshot_json"]),
        }
        for row in rows
    ]


def swing_forward_store_audit(path: Path = DEFAULT_SWING_FORWARD_DB_PATH) -> dict:
    initialize_swing_forward_store(path)
    invalid: list[str] = []
    with _connect(Path(path)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        scans = connection.execute(
            "SELECT scan_id, snapshot_json, snapshot_fingerprint FROM swing_scans ORDER BY observed_at"
        ).fetchall()
        signals = connection.execute(
            "SELECT signal_id, snapshot_json, snapshot_fingerprint, plan_fingerprint FROM swing_signals ORDER BY signal_at"
        ).fetchall()
        events = connection.execute(
            "SELECT event_id, payload_json, event_fingerprint FROM swing_events ORDER BY occurred_at"
        ).fetchall()
        controls = connection.execute(
            "SELECT control_id, snapshot_json, snapshot_fingerprint FROM swing_rejection_controls ORDER BY signal_day"
        ).fetchall()
        control_events = connection.execute(
            "SELECT event_id, payload_json, event_fingerprint FROM swing_rejection_control_events ORDER BY occurred_at"
        ).fetchall()
    for row in scans:
        try:
            snapshot = json.loads(row["snapshot_json"])
            if _fingerprint(snapshot) != row["snapshot_fingerprint"]:
                invalid.append(f"scan:{row['scan_id']}:fingerprint")
        except Exception:
            invalid.append(f"scan:{row['scan_id']}:json")
    for row in signals:
        try:
            snapshot = json.loads(row["snapshot_json"])
            if _fingerprint(snapshot) != row["snapshot_fingerprint"]:
                invalid.append(f"signal:{row['signal_id']}:fingerprint")
            plan = dict(snapshot.get("order_plan") or {})
            if swing_order_plan_fingerprint(plan) != row["plan_fingerprint"]:
                invalid.append(f"signal:{row['signal_id']}:order_plan")
        except Exception:
            invalid.append(f"signal:{row['signal_id']}:json")
    for row in events:
        try:
            payload = json.loads(row["payload_json"])
            if _fingerprint(payload) != row["event_fingerprint"]:
                invalid.append(f"event:{row['event_id']}:fingerprint")
        except Exception:
            invalid.append(f"event:{row['event_id']}:json")
    for row in controls:
        try:
            snapshot = json.loads(row["snapshot_json"])
            if _fingerprint(snapshot) != row["snapshot_fingerprint"]:
                invalid.append(f"control:{row['control_id']}:fingerprint")
        except Exception:
            invalid.append(f"control:{row['control_id']}:json")
    for row in control_events:
        try:
            payload = json.loads(row["payload_json"])
            if _fingerprint(payload) != row["event_fingerprint"]:
                invalid.append(f"control_event:{row['event_id']}:fingerprint")
        except Exception:
            invalid.append(f"control_event:{row['event_id']}:json")
    return {
        "schema_version": SWING_FORWARD_SCHEMA_VERSION,
        "quick_check": quick_check,
        "scans": len(scans),
        "signals": len(signals),
        "events": len(events),
        "rejection_controls": len(controls),
        "rejection_control_events": len(control_events),
        "invalid_count": len(invalid),
        "invalid": invalid[:20],
        "status": "ok" if quick_check == "ok" and not invalid else "attention",
    }
