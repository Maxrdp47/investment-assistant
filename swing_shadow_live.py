from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

import pandas as pd

from swing_forward_store import SWING_STRATEGY_VERSION
from swing_paper_bot import DEFAULT_SWING_PAPER_DB_PATH, load_paper_signals
from swing_risk_engine import apply_swing_risk_engine, validate_risk_decision
from trading_assistant import swing_order_plan_fingerprint


SHADOW_LIVE_SCHEMA_VERSION = 1
SHADOW_LIVE_VERSION = "swing-shadow-live-2026.08.18-v1"
DEFAULT_SWING_SHADOW_DB_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_SWING_SHADOW_DB_PATH",
        Path(__file__).resolve().parent / "runtime" / "swing_shadow_live.sqlite3",
    )
)


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
    return json.dumps(_clean(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_shadow_live_store(path: Path = DEFAULT_SWING_SHADOW_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS shadow_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS shadow_drafts(
                draft_id TEXT PRIMARY KEY, setup_id TEXT NOT NULL, observed_at TEXT NOT NULL,
                symbol TEXT NOT NULL, strategy_version TEXT NOT NULL,
                snapshot_json TEXT NOT NULL, snapshot_fingerprint TEXT NOT NULL,
                UNIQUE(strategy_version, setup_id)
            );
            CREATE TABLE IF NOT EXISTS shadow_observations(
                observation_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES shadow_drafts(draft_id),
                occurred_at TEXT NOT NULL, observation_type TEXT NOT NULL,
                payload_json TEXT NOT NULL, payload_fingerprint TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS shadow_drafts_no_update BEFORE UPDATE ON shadow_drafts
            BEGIN SELECT RAISE(ABORT, 'shadow drafts append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_drafts_no_delete BEFORE DELETE ON shadow_drafts
            BEGIN SELECT RAISE(ABORT, 'shadow drafts append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_observations_no_update BEFORE UPDATE ON shadow_observations
            BEGIN SELECT RAISE(ABORT, 'shadow observations append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_observations_no_delete BEFORE DELETE ON shadow_observations
            BEGIN SELECT RAISE(ABORT, 'shadow observations append-only'); END;
            """
        )
        existing = connection.execute("SELECT value FROM shadow_meta WHERE key='schema_version'").fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO shadow_meta(key,value) VALUES('schema_version',?)",
                (str(SHADOW_LIVE_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != SHADOW_LIVE_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstützte Shadow-Live-Datenbankversion.")


def _execution_observations(candidate: Mapping[str, object]) -> dict:
    price = dict(candidate.get("trade_republic_price") or {})
    execution_plan = dict(candidate.get("trade_republic_execution_plan") or {})
    available = bool(price.get("available"))
    # Never infer venue microstructure from Yahoo OHLC bars or from a single TR price.
    return {
        "tradeability_status": (candidate.get("trade_republic") or {}).get("status"),
        "trade_republic_price_eur": price.get("price_eur") if available else None,
        "trade_republic_price_observed_at": price.get("observed_at") if available else None,
        "trade_republic_price_source": price.get("source") if available else None,
        "bid_eur": price.get("bid_eur") if price.get("bid_eur") is not None else None,
        "ask_eur": price.get("ask_eur") if price.get("ask_eur") is not None else None,
        "spread_bps": price.get("spread_bps") if price.get("spread_bps") is not None else None,
        "slippage_bps_observed": None,
        "limit_executability_observed": None,
        "stop_executability_observed": None,
        "gap_observed": None,
        "missed_execution_observed": None,
        "missing_values_estimated": False,
        "execution_plan_status": execution_plan.get("status"),
        "reason": "Nicht vorhandene echte Ausführungsdaten bleiben leer und werden nicht aus Fremdbörsenkursen geschätzt.",
    }


def record_shadow_live_drafts(
    scan_result: Mapping[str, object],
    settings: Mapping[str, object],
    *,
    current_exposure_eur: float,
    current_risk_eur: float,
    path: Path = DEFAULT_SWING_SHADOW_DB_PATH,
) -> dict:
    initialize_shadow_live_store(path)
    observed_at = str(scan_result.get("last_scan") or "")
    if not observed_at:
        raise ValueError("Shadow-Live benötigt einen Scanzeitpunkt.")
    exposure = float(current_exposure_eur)
    risk = float(current_risk_eur)
    inserted = existing = failures = 0
    candidates = [*list(scan_result.get("approved") or []), *list(scan_result.get("shadow_signals") or [])]
    for raw_candidate in candidates:
        try:
            raw_plan = dict(raw_candidate.get("order_plan") or {})
            setup_id = str(raw_candidate.get("setup_id") or raw_plan.get("plan_fingerprint") or "")
            if not setup_id:
                raise ValueError("Shadow-Entwurf besitzt keine stabile Setup-ID.")
            with _connect(path) as connection:
                prior = connection.execute(
                    "SELECT 1 FROM shadow_drafts WHERE strategy_version=? AND setup_id=?",
                    (SWING_STRATEGY_VERSION, setup_id),
                ).fetchone()
            if prior:
                existing += 1
                continue
            candidate = apply_swing_risk_engine(
                raw_candidate,
                settings,
                current_exposure_eur=exposure,
                current_risk_eur=risk,
                execution_mode="shadow_only",
            )
            validate_risk_decision(candidate, required_mode="shadow_only")
            plan = dict(candidate["order_plan"])
            if plan.get("plan_fingerprint") != swing_order_plan_fingerprint(plan):
                raise ValueError("Shadow-Orderentwurf besitzt einen ungültigen Fingerabdruck.")
            snapshot = {
                "shadow_live_version": SHADOW_LIVE_VERSION,
                "evidence_kind": "shadow_live_order_draft",
                "shadow_only": True,
                "paper_only": False,
                "broker_adapter_present": False,
                "broker_order_allowed": False,
                "broker_order_sent": False,
                "observed_at": observed_at,
                "market_data_source": plan.get("analysis_price_source"),
                "asset": {
                    "ticker": str(candidate.get("symbol") or "").upper(),
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
                "signal": {
                    "signal_at": observed_at,
                    "quality_score": candidate.get("quality_score"),
                    "confidence": candidate.get("confidence"),
                },
                "risk_decision": dict(candidate["risk_decision"]),
                "position_size": dict(candidate.get("position_size") or {}),
                "order_plan": plan,
                "trade_republic_execution_plan": dict(candidate.get("trade_republic_execution_plan") or {}),
                "execution_observations": _execution_observations(candidate),
            }
            fingerprint = _fingerprint(snapshot)
            draft_id = _fingerprint(
                {"kind": "shadow_live_order_draft", "strategy_version": SWING_STRATEGY_VERSION, "setup_id": setup_id}
            )
            with _connect(path) as connection:
                connection.execute(
                    "INSERT INTO shadow_drafts VALUES(?,?,?,?,?,?,?)",
                    (
                        draft_id, setup_id, observed_at, snapshot["asset"]["ticker"],
                        SWING_STRATEGY_VERSION, _canonical_json(snapshot), fingerprint,
                    ),
                )
            inserted += 1
            if candidate["risk_decision"]["approved"]:
                exposure += float((candidate.get("position_size") or {}).get("position_value_eur") or 0)
                risk += float((candidate.get("position_size") or {}).get("actual_risk_eur") or 0)
        except Exception:
            failures += 1
    return {
        "drafts_inserted": inserted,
        "drafts_existing": existing,
        "failures": failures,
        "shadow_only": True,
        "broker_order_sent": False,
    }


def load_shadow_drafts(path: Path = DEFAULT_SWING_SHADOW_DB_PATH) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_shadow_live_store(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT draft_id,setup_id,snapshot_json FROM shadow_drafts ORDER BY observed_at,draft_id"
        ).fetchall()
    return [
        {
            "draft_id": str(row["draft_id"]),
            "setup_id": str(row["setup_id"]),
            "snapshot": json.loads(str(row["snapshot_json"])),
        }
        for row in rows
    ]


def shadow_paper_comparison(
    shadow_path: Path = DEFAULT_SWING_SHADOW_DB_PATH,
    paper_path: Path = DEFAULT_SWING_PAPER_DB_PATH,
) -> dict:
    shadow = {item["setup_id"]: item for item in load_shadow_drafts(shadow_path)}
    paper = {}
    for item in load_paper_signals(paper_path):
        paper[str(item.get("setup_id") or "")] = item
    compared = deviations = 0
    for setup_id in set(shadow).intersection(paper):
        shadow_plan = dict(shadow[setup_id]["snapshot"].get("order_plan") or {})
        paper_plan = dict(paper[setup_id]["snapshot"].get("order_plan") or {})
        compared += 1
        if shadow_plan.get("plan_fingerprint") != paper_plan.get("plan_fingerprint"):
            deviations += 1
    return {
        "compared": compared,
        "plan_deviations": deviations,
        "unmatched_shadow": len(set(shadow) - set(paper)),
        "unmatched_paper": len(set(paper) - set(shadow)),
        "missing_execution_data_estimated": False,
    }


def shadow_live_store_audit(path: Path = DEFAULT_SWING_SHADOW_DB_PATH) -> dict:
    if not Path(path).exists():
        return {"status": "not_created", "drafts": 0, "observations": 0}
    initialize_shadow_live_store(path)
    with _connect(path) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        drafts = int(connection.execute("SELECT COUNT(*) FROM shadow_drafts").fetchone()[0])
        observations = int(connection.execute("SELECT COUNT(*) FROM shadow_observations").fetchone()[0])
        invalid = int(
            connection.execute(
                "SELECT COUNT(*) FROM shadow_drafts WHERE snapshot_json NOT LIKE '%\"shadow_only\":true%' OR snapshot_json LIKE '%\"broker_order_allowed\":true%'"
            ).fetchone()[0]
        )
    return {
        "status": "ok" if quick_check == "ok" and invalid == 0 else "attention",
        "quick_check": quick_check,
        "drafts": drafts,
        "observations": observations,
        "invalid_execution_flags": invalid,
        "append_only": True,
        "shadow_only": True,
        "broker_order_sent": False,
    }
