from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd

from swing_forward_store import SWING_STRATEGY_VERSION
from swing_paper_bot import DEFAULT_SWING_PAPER_DB_PATH, load_paper_signals
from swing_risk_engine import apply_swing_risk_engine, validate_risk_decision
from trading_assistant import swing_order_plan_fingerprint


SHADOW_LIVE_SCHEMA_VERSION = 2
SHADOW_LIVE_VERSION = "swing-shadow-live-2026.08.18-v1"
SHADOW_EXECUTION_OBSERVATION_VERSION = "swing-shadow-execution-observation-2026.08.23-v1"
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
            CREATE TABLE IF NOT EXISTS shadow_execution_observations(
                observation_id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL REFERENCES shadow_drafts(draft_id),
                signal_id TEXT,
                listing_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                source_timestamp TEXT,
                source TEXT,
                quote_quality TEXT NOT NULL,
                execution_observation_status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS shadow_drafts_no_update BEFORE UPDATE ON shadow_drafts
            BEGIN SELECT RAISE(ABORT, 'shadow drafts append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_drafts_no_delete BEFORE DELETE ON shadow_drafts
            BEGIN SELECT RAISE(ABORT, 'shadow drafts append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_observations_no_update BEFORE UPDATE ON shadow_observations
            BEGIN SELECT RAISE(ABORT, 'shadow observations append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_observations_no_delete BEFORE DELETE ON shadow_observations
            BEGIN SELECT RAISE(ABORT, 'shadow observations append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_execution_observations_no_update
            BEFORE UPDATE ON shadow_execution_observations
            BEGIN SELECT RAISE(ABORT, 'shadow execution observations append-only'); END;
            CREATE TRIGGER IF NOT EXISTS shadow_execution_observations_no_delete
            BEFORE DELETE ON shadow_execution_observations
            BEGIN SELECT RAISE(ABORT, 'shadow execution observations append-only'); END;
            """
        )
        existing = connection.execute("SELECT value FROM shadow_meta WHERE key='schema_version'").fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO shadow_meta(key,value) VALUES('schema_version',?)",
                (str(SHADOW_LIVE_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) == 1 and SHADOW_LIVE_SCHEMA_VERSION == 2:
            connection.execute(
                "UPDATE shadow_meta SET value = ? WHERE key='schema_version'",
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
    signal_ids_by_setup: Mapping[str, str] | None = None,
    path: Path = DEFAULT_SWING_SHADOW_DB_PATH,
) -> dict:
    initialize_shadow_live_store(path)
    observed_at = str(scan_result.get("last_scan") or "")
    if not observed_at:
        raise ValueError("Shadow-Live benötigt einen Scanzeitpunkt.")
    exposure = float(current_exposure_eur)
    risk = float(current_risk_eur)
    inserted = existing = failures = 0
    draft_ids_by_setup: dict[str, str] = {}
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
                draft_id = _fingerprint(
                    {"kind": "shadow_live_order_draft", "strategy_version": SWING_STRATEGY_VERSION, "setup_id": setup_id}
                )
                draft_ids_by_setup[setup_id] = draft_id
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
                    "signal_id": (signal_ids_by_setup or {}).get(setup_id),
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
            draft_ids_by_setup[setup_id] = draft_id
            if candidate["risk_decision"]["approved"]:
                exposure += float((candidate.get("position_size") or {}).get("position_value_eur") or 0)
                risk += float((candidate.get("position_size") or {}).get("actual_risk_eur") or 0)
        except Exception:
            failures += 1
    return {
        "drafts_inserted": inserted,
        "drafts_existing": existing,
        "failures": failures,
        "draft_ids_by_setup": draft_ids_by_setup,
        "draft_ids": list(draft_ids_by_setup.values()),
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


def _utc(value: object) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Shadow-Execution-Zeitpunkte benötigen eine Zeitzone.")
    return parsed.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def shadow_listing_identity(snapshot: Mapping[str, object]) -> dict:
    asset = dict(snapshot.get("asset") or {})
    listing = dict(asset.get("listing") or {})
    identity = {
        "ticker": str(asset.get("ticker") or listing.get("ticker") or "").upper(),
        "isin": listing.get("isin"),
        "exchange": listing.get("exchange"),
        "original_currency": listing.get("original_currency") or listing.get("currency"),
    }
    if not identity["ticker"]:
        raise ValueError("Shadow-Orderentwurf besitzt kein Listing-Ticker.")
    return {**identity, "listing_id": _fingerprint(identity)}


def build_shadow_execution_observation(
    draft: Mapping[str, object],
    *,
    signal_id: str | None,
    observed_at: datetime | str,
    quote: Mapping[str, object] | None = None,
    max_quote_age_seconds: int = 300,
) -> dict:
    """Build one evidence sidecar; quote providers are read-only callables outside this contract."""
    snapshot = dict(draft.get("snapshot") or {})
    listing = shadow_listing_identity(snapshot)
    plan = dict(snapshot.get("order_plan") or {})
    observed = _utc(observed_at)
    source = source_timestamp = None
    bid = ask = last_price = None
    quality = "unavailable"
    status = "real_execution_quote_data_unavailable"
    if quote is not None:
        quote_listing_id = str(quote.get("listing_id") or "")
        if quote_listing_id != listing["listing_id"]:
            raise ValueError("Quote gehört nicht zum exakten Shadow-Listing.")
        source = str(quote.get("source") or "").strip()
        source_timestamp = str(quote.get("source_timestamp") or "").strip()
        if not source or not source_timestamp:
            raise ValueError("Reale Quote benötigt Quelle und Quellzeitpunkt.")
        source_lower = source.lower()
        if any(token in source_lower for token in ("yahoo daily", "yfinance daily", "ohlc", "simulated", "estimated")):
            raise ValueError("Tages-/simulierte Daten dürfen nicht als Execution-Quote gespeichert werden.")
        quote_time = _utc(source_timestamp)
        if quote_time - observed > timedelta(minutes=5):
            raise ValueError("Quote-Zeitpunkt liegt unplausibel nach der Beobachtung.")
        bid = _number(quote.get("bid"))
        ask = _number(quote.get("ask"))
        last_price = _number(quote.get("last_price"))
        if any(value is not None and value <= 0 for value in (bid, ask, last_price)):
            raise ValueError("Beobachtete Marktpreise müssen positiv sein.")
        if bid is not None and ask is not None and bid > ask:
            raise ValueError("Beobachtetes Bid darf nicht über Ask liegen.")
        if bid is None and ask is None and last_price is None:
            raise ValueError("Quote enthält keinen tatsächlich beobachteten Preis.")
        age = observed - quote_time
        quality = str(quote.get("quote_quality") or "observed")
        if age > timedelta(seconds=max(0, int(max_quote_age_seconds))):
            quality = "stale"
        status = (
            "observed_market_quote"
            if bid is not None and ask is not None
            else "observed_market_trade_only"
        )
    mid = (bid + ask) / 2.0 if bid is not None and ask is not None else None
    spread = ask - bid if bid is not None and ask is not None else None
    spread_percent = (spread / mid * 100.0) if spread is not None and mid not in (None, 0) else None
    theoretical_entry = _number(plan.get("limit_price_eur") or plan.get("entry_reference_eur"))
    max_price = _number(plan.get("max_entry_price_eur") or plan.get("max_price_eur"))
    observed_market = {
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread_absolute": spread,
        "spread_percent": spread_percent,
        "last_price": last_price,
        "quote_currency": (quote or {}).get("original_currency") if quote else None,
        "distance_theoretical_entry_to_bid": (
            theoretical_entry - bid if theoretical_entry is not None and bid is not None else None
        ),
        "distance_theoretical_entry_to_ask": (
            theoretical_entry - ask if theoretical_entry is not None and ask is not None else None
        ),
        "distance_max_price_to_ask": (
            max_price - ask if max_price is not None and ask is not None else None
        ),
        "observed_gap": (quote or {}).get("observed_gap") if quote else None,
    }
    payload = {
        "observation_version": SHADOW_EXECUTION_OBSERVATION_VERSION,
        "shadow_order_id": str(draft.get("draft_id") or ""),
        "signal_id": str(signal_id) if signal_id else None,
        "strategy_version": str(dict(snapshot.get("strategy") or {}).get("strategy_version") or SWING_STRATEGY_VERSION),
        "listing": listing,
        "observed_at": observed.isoformat(),
        "source": source,
        "source_timestamp": _utc(source_timestamp).isoformat() if source_timestamp else None,
        "quote_quality": quality,
        "execution_observation_status": status,
        "observed_market_data": observed_market,
        "theoretical_system_order_draft": {
            "theoretical_entry": theoretical_entry,
            "activation_price": _number(plan.get("entry_activation_above_eur")),
            "max_price": max_price,
            "stop": _number(plan.get("initial_stop_eur")),
            "targets": [
                value
                for value in (
                    _number(plan.get("target_1_eur")),
                    _number(plan.get("target_2_eur")),
                )
                if value is not None
            ],
            "broker_order_allowed": False,
            "broker_order_sent": False,
        },
        "later_shadow_evaluation": {
            "market_open_gap": None,
            "price_path_after_draft": None,
            "later_limit_touch": None,
            "theoretical_price_improvement_or_deterioration": None,
            "status": "not_evaluated",
        },
        "simulated_cost_assumptions": {
            "present": False,
            "values": None,
        },
        "execution_evidence": {
            "fill": None,
            "partial_fill": None,
            "slippage": None,
            "order_book": None,
            "broker_rejection": None,
        },
        "missingness": {
            "real_execution_quote_data_unavailable": quote is None,
            "bid_unavailable": bid is None,
            "ask_unavailable": ask is None,
            "spread_unavailable": spread is None,
            "fill_evidence_unavailable": True,
            "slippage_evidence_unavailable": True,
            "values_estimated": False,
        },
        "guardrails": {
            "observed_theoretical_later_and_simulated_separated": True,
            "shadow_only": True,
            "broker_adapter_present": False,
            "broker_order_allowed": False,
            "production_effect": "none",
        },
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def append_shadow_execution_observation(
    observation: Mapping[str, object],
    path: Path = DEFAULT_SWING_SHADOW_DB_PATH,
) -> dict:
    initialize_shadow_live_store(path)
    payload = dict(observation)
    expected = payload.pop("fingerprint", None)
    fingerprint = _fingerprint(payload)
    if fingerprint != expected:
        raise ValueError("Shadow-Execution-Beobachtung besitzt einen ungültigen Fingerabdruck.")
    payload["fingerprint"] = fingerprint
    observed_market = dict(payload.get("observed_market_data") or {})
    identity = {
        "version": SHADOW_EXECUTION_OBSERVATION_VERSION,
        "draft_id": payload.get("shadow_order_id"),
        "status": payload.get("execution_observation_status"),
        "source": payload.get("source"),
        "source_timestamp": payload.get("source_timestamp"),
        "observed_market_data": observed_market,
    }
    observation_id = _fingerprint(identity)
    listing = dict(payload.get("listing") or {})
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT 1 FROM shadow_execution_observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
        if existing is not None:
            return {"observation_id": observation_id, "inserted": False}
        if connection.execute(
            "SELECT 1 FROM shadow_drafts WHERE draft_id = ?",
            (payload["shadow_order_id"],),
        ).fetchone() is None:
            raise ValueError("Shadow-Execution-Beobachtung verweist auf unbekannten Entwurf.")
        connection.execute(
            """INSERT INTO shadow_execution_observations
            (observation_id, draft_id, signal_id, listing_id, observed_at, source_timestamp,
             source, quote_quality, execution_observation_status, payload_json, payload_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                observation_id,
                payload["shadow_order_id"],
                payload.get("signal_id"),
                listing["listing_id"],
                payload["observed_at"],
                payload.get("source_timestamp"),
                payload.get("source"),
                payload["quote_quality"],
                payload["execution_observation_status"],
                _canonical_json(payload),
                fingerprint,
            ),
        )
    return {"observation_id": observation_id, "inserted": True}


def _manual_listing_price_quote(draft: Mapping[str, object]) -> dict | None:
    snapshot = dict(draft.get("snapshot") or {})
    execution = dict(snapshot.get("execution_observations") or {})
    price = _number(execution.get("trade_republic_price_eur"))
    source_timestamp = execution.get("trade_republic_price_observed_at")
    source = execution.get("trade_republic_price_source")
    if price is None or not source_timestamp or not source:
        return None
    listing = shadow_listing_identity(snapshot)
    return {
        "listing_id": listing["listing_id"],
        "source": source,
        "source_timestamp": source_timestamp,
        "quote_quality": "manual_listing_price",
        "original_currency": "EUR",
        "bid": execution.get("bid_eur"),
        "ask": execution.get("ask_eur"),
        "last_price": price,
    }


def record_shadow_execution_observations(
    *,
    draft_ids: list[str] | None = None,
    signal_ids_by_setup: Mapping[str, str] | None = None,
    observed_at: datetime | str | None = None,
    quote_provider=None,
    path: Path = DEFAULT_SWING_SHADOW_DB_PATH,
    max_quote_age_seconds: int = 300,
) -> dict:
    """Collect real quotes through an optional read-only adapter, otherwise persist honest missingness."""
    collected = _utc(observed_at or datetime.now(timezone.utc))
    requested = {str(value) for value in draft_ids} if draft_ids is not None else None
    drafts = [
        draft for draft in load_shadow_drafts(path)
        if requested is None or draft["draft_id"] in requested
    ]
    inserted = existing = real_quotes = real_trade_only = unavailable = 0
    errors: list[dict] = []
    for draft in drafts:
        try:
            quote = quote_provider(draft) if quote_provider is not None else None
            if quote is None:
                quote = _manual_listing_price_quote(draft)
            signal_id = (signal_ids_by_setup or {}).get(str(draft.get("setup_id") or ""))
            if not signal_id:
                signal_id = dict(dict(draft.get("snapshot") or {}).get("signal") or {}).get("signal_id")
            observation = build_shadow_execution_observation(
                draft,
                signal_id=str(signal_id) if signal_id else None,
                observed_at=collected,
                quote=quote,
                max_quote_age_seconds=max_quote_age_seconds,
            )
            result = append_shadow_execution_observation(observation, path)
            inserted += int(result["inserted"])
            existing += int(not result["inserted"])
            real_quotes += int(observation["execution_observation_status"] == "observed_market_quote")
            real_trade_only += int(observation["execution_observation_status"] == "observed_market_trade_only")
            unavailable += int(observation["execution_observation_status"] == "real_execution_quote_data_unavailable")
        except Exception as exc:
            errors.append({"draft_id": draft["draft_id"], "error": str(exc)})
    return {
        "status": "ok" if not errors else "research_attention",
        "drafts_requested": len(drafts),
        "observations_inserted": inserted,
        "observations_existing": existing,
        "real_quote_observations": real_quotes,
        "real_trade_only_observations": real_trade_only,
        "unavailable_observations": unavailable,
        "errors": errors,
        "configured_read_only_quote_provider": quote_provider is not None,
        "shadow_only": True,
        "broker_order_sent": False,
        "production_effect": "none",
    }


def load_shadow_execution_observations(
    path: Path = DEFAULT_SWING_SHADOW_DB_PATH,
) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_shadow_live_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT observation_id, draft_id, payload_json FROM shadow_execution_observations "
            "ORDER BY observed_at, observation_id"
        ).fetchall()
    return [
        {
            "observation_id": str(row["observation_id"]),
            "draft_id": str(row["draft_id"]),
            "observation": json.loads(str(row["payload_json"])),
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
        return {
            "status": "not_created",
            "drafts": 0,
            "observations": 0,
            "execution_observations": 0,
            "real_quote_observations": 0,
            "real_trade_only_observations": 0,
            "unavailable_execution_observations": 0,
        }
    initialize_shadow_live_store(path)
    with _connect(path) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        drafts = int(connection.execute("SELECT COUNT(*) FROM shadow_drafts").fetchone()[0])
        observations = int(connection.execute("SELECT COUNT(*) FROM shadow_observations").fetchone()[0])
        execution_rows = connection.execute(
            "SELECT draft_id, execution_observation_status, source, source_timestamp, payload_json "
            "FROM shadow_execution_observations"
        ).fetchall()
        invalid = int(
            connection.execute(
                "SELECT COUNT(*) FROM shadow_drafts WHERE snapshot_json NOT LIKE '%\"shadow_only\":true%' OR snapshot_json LIKE '%\"broker_order_allowed\":true%'"
            ).fetchone()[0]
        )
    invalid_execution = 0
    real_drafts: set[str] = set()
    real_quotes = real_trade_only = unavailable = 0
    for row in execution_rows:
        payload = json.loads(str(row["payload_json"]))
        market = dict(payload.get("observed_market_data") or {})
        status = str(row["execution_observation_status"])
        if status == "observed_market_quote":
            real_quotes += 1
            real_drafts.add(str(row["draft_id"]))
            if not row["source"] or not row["source_timestamp"] or market.get("bid") is None or market.get("ask") is None:
                invalid_execution += 1
        elif status == "observed_market_trade_only":
            real_trade_only += 1
            real_drafts.add(str(row["draft_id"]))
            if not row["source"] or not row["source_timestamp"] or market.get("last_price") is None:
                invalid_execution += 1
        elif status == "real_execution_quote_data_unavailable":
            unavailable += 1
            if any(market.get(field) is not None for field in ("bid", "ask", "mid", "spread_absolute", "spread_percent", "last_price")):
                invalid_execution += 1
        else:
            invalid_execution += 1
    return {
        "status": "ok" if quick_check == "ok" and invalid == 0 and invalid_execution == 0 else "attention",
        "quick_check": quick_check,
        "drafts": drafts,
        "observations": observations,
        "execution_observations": len(execution_rows),
        "real_quote_observations": real_quotes,
        "real_trade_only_observations": real_trade_only,
        "unavailable_execution_observations": unavailable,
        "drafts_without_real_market_observation": max(0, drafts - len(real_drafts)),
        "invalid_execution_flags": invalid,
        "invalid_execution_observations": invalid_execution,
        "append_only": True,
        "shadow_only": True,
        "broker_order_sent": False,
    }
