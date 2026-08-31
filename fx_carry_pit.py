from __future__ import annotations

"""Versioned Point-in-Time foundations for future FX carry research.

The module models data identity and availability.  It deliberately does not
download macro data, generate a direction, simulate a trade or activate a
strategy.  Missing historical vintages remain unavailable.
"""

import hashlib
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


FX_CARRY_PIT_VERSION = "fx-carry-pit-2026.08.28-v1"
FX_PAIR_CONTRACT_VERSION = "fx-pair-contract-2026.08.28-v1"
FX_COST_CONTRACT_VERSION = "fx-research-cost-basis-2026.08.28-v1"

DEFAULT_FX_CARRY_DB_PATH = Path(__file__).resolve().parent / "runtime" / "fx_carry_pit.sqlite3"

PIT_FEATURES = {
    "policy_rate",
    "expected_policy_rate",
    "yield_differential",
    "implied_volatility",
    "realized_volatility",
    "central_bank_regime",
    "central_bank_surprise",
    "confirmed_intervention",
    "cot_positioning",
    "spread_bps",
}


class FxCarryContractError(ValueError):
    """An FX pair or PIT observation violates the causal contract."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FxCarryContractError(f"{field} fehlt.")
    normalized = text.replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise FxCarryContractError(f"{field} ist kein ISO-Zeitpunkt.") from exc
    if stamp.tzinfo is None:
        raise FxCarryContractError(f"{field} benötigt eine Zeitzone.")
    return stamp.astimezone(timezone.utc).isoformat()


def _finite(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FxCarryContractError(f"{field} ist keine Zahl.") from exc
    if not math.isfinite(number):
        raise FxCarryContractError(f"{field} muss endlich sein.")
    return number


def fx_pair_contract(
    base_currency: str,
    quote_currency: str,
    *,
    source_ticker: str,
    source_base_currency: str | None = None,
    source_quote_currency: str | None = None,
    source: str = "Yahoo Finance reference ticker",
    session_timezone: str = "America/New_York",
    canonical_daily_close: str = "17:00",
) -> dict[str, object]:
    base = str(base_currency or "").strip().upper()
    quote = str(quote_currency or "").strip().upper()
    source_base = str(source_base_currency or base).strip().upper()
    source_quote = str(source_quote_currency or quote).strip().upper()
    if not (len(base) == len(quote) == len(source_base) == len(source_quote) == 3):
        raise FxCarryContractError("FX-Währungen benötigen jeweils einen ISO-Dreiercode.")
    if base == quote:
        raise FxCarryContractError("Basis- und Gegenwährung müssen verschieden sein.")
    direct = source_base == base and source_quote == quote
    inverse = source_base == quote and source_quote == base
    if not (direct or inverse):
        raise FxCarryContractError("Quelldaten müssen direkt oder exakt invers zum Paar sein.")
    payload: dict[str, object] = {
        "version": FX_PAIR_CONTRACT_VERSION,
        "pair_id": f"{base}/{quote}",
        "base_currency": base,
        "quote_currency": quote,
        "source": source,
        "source_ticker": str(source_ticker or "").strip(),
        "source_base_currency": source_base,
        "source_quote_currency": source_quote,
        "source_is_inverse": inverse,
        "long_return_sign": "positive_when_base_strengthens_against_quote",
        "carry_sign": "base_rate_minus_quote_rate",
        "session_timezone": str(session_timezone),
        "canonical_daily_close": str(canonical_daily_close),
        "known_at_required": True,
        "available_at_required": True,
        "automatic_strategy_activation": False,
    }
    if not payload["source_ticker"]:
        raise FxCarryContractError("FX-Paar benötigt einen Datenquellen-Ticker.")
    payload["pair_fingerprint"] = _fingerprint(payload)
    return payload


def default_fx_pair_contracts() -> dict[str, dict[str, object]]:
    contracts = [
        fx_pair_contract("EUR", "USD", source_ticker="EURUSD=X"),
        fx_pair_contract("USD", "JPY", source_ticker="JPY=X"),
        fx_pair_contract("GBP", "USD", source_ticker="GBPUSD=X"),
    ]
    return {str(item["pair_id"]): item for item in contracts}


def normalize_fx_ohlc(
    contract: Mapping[str, object],
    bar: Mapping[str, object],
) -> dict[str, float]:
    values = {
        key: _finite(bar.get(key), key)
        for key in ("open", "high", "low", "close")
    }
    if min(values.values()) <= 0 or values["high"] < values["low"]:
        raise FxCarryContractError("FX-OHLC ist ungültig.")
    if not bool(contract.get("source_is_inverse")):
        result = values
    else:
        result = {
            "open": 1.0 / values["open"],
            "high": 1.0 / values["low"],
            "low": 1.0 / values["high"],
            "close": 1.0 / values["close"],
        }
    if not (
        result["low"] <= result["open"] <= result["high"]
        and result["low"] <= result["close"] <= result["high"]
        and result["low"] <= result["high"]
    ):
        raise FxCarryContractError("Normalisierte FX-OHLC ist inkonsistent.")
    return result


def normalize_pit_observation(observation: Mapping[str, object]) -> dict[str, object]:
    feature = str(observation.get("feature") or "").strip()
    if feature not in PIT_FEATURES:
        raise FxCarryContractError(f"Unbekanntes FX-PIT-Feature: {feature}")
    value = _finite(observation.get("value"), "value")
    effective_at = _utc(observation.get("effective_at"), "effective_at")
    known_at = _utc(observation.get("known_at"), "known_at")
    available_at = _utc(observation.get("available_at"), "available_at")
    if available_at < known_at:
        raise FxCarryContractError("available_at darf nicht vor known_at liegen.")
    currency = str(observation.get("currency") or "").strip().upper() or None
    pair_id = str(observation.get("pair_id") or "").strip().upper() or None
    if feature in {"policy_rate", "expected_policy_rate", "central_bank_regime"} and not currency:
        raise FxCarryContractError(f"{feature} benötigt eine Währung.")
    if feature in {"yield_differential", "implied_volatility", "realized_volatility", "cot_positioning", "spread_bps"} and not pair_id:
        raise FxCarryContractError(f"{feature} benötigt pair_id.")

    metadata = dict(observation.get("metadata") or {})
    if feature == "central_bank_surprise":
        required = {"consensus", "actual", "consensus_known_at"}
        if not required <= set(metadata):
            raise FxCarryContractError(
                "Eine Surprise benötigt damaligen Konsens, Actual und consensus_known_at."
            )
        consensus_known_at = _utc(metadata["consensus_known_at"], "consensus_known_at")
        if consensus_known_at > effective_at:
            raise FxCarryContractError("Konsens war vor dem Ereignis nicht bekannt.")
        expected_surprise = _finite(metadata["actual"], "actual") - _finite(
            metadata["consensus"], "consensus"
        )
        if not math.isclose(value, expected_surprise, rel_tol=1e-12, abs_tol=1e-12):
            raise FxCarryContractError("Surprise stimmt nicht mit Actual minus Konsens überein.")
        metadata["consensus_known_at"] = consensus_known_at

    payload: dict[str, object] = {
        "version": FX_CARRY_PIT_VERSION,
        "feature": feature,
        "value": value,
        "unit": str(observation.get("unit") or "").strip() or None,
        "currency": currency,
        "pair_id": pair_id,
        "effective_at": effective_at,
        "known_at": known_at,
        "available_at": available_at,
        "source": str(observation.get("source") or "").strip(),
        "source_record_id": str(observation.get("source_record_id") or "").strip(),
        "vintage": str(observation.get("vintage") or "ORIGINAL").strip(),
        "revision_of": str(observation.get("revision_of") or "").strip() or None,
        "metadata": metadata,
        "point_in_time": True,
    }
    if not payload["source"] or not payload["source_record_id"]:
        raise FxCarryContractError("PIT-Beobachtung benötigt Quelle und Quell-ID.")
    payload["observation_id"] = f"fxpit-{_fingerprint(payload)[:32]}"
    payload["observation_fingerprint"] = _fingerprint(payload)
    return payload


def initialize_fx_carry_store(path: Path = DEFAULT_FX_CARRY_DB_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS fx_pair_contracts (
                pair_fingerprint TEXT PRIMARY KEY,
                pair_id TEXT NOT NULL,
                contract_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fx_pit_observations (
                observation_id TEXT PRIMARY KEY,
                feature TEXT NOT NULL,
                currency TEXT,
                pair_id TEXT,
                effective_at TEXT NOT NULL,
                known_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                observation_json TEXT NOT NULL,
                observation_fingerprint TEXT NOT NULL UNIQUE
            );
            CREATE TRIGGER IF NOT EXISTS fx_pair_contracts_no_update
            BEFORE UPDATE ON fx_pair_contracts BEGIN SELECT RAISE(ABORT, 'fx_pair_contracts append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fx_pair_contracts_no_delete
            BEFORE DELETE ON fx_pair_contracts BEGIN SELECT RAISE(ABORT, 'fx_pair_contracts append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fx_pit_observations_no_update
            BEFORE UPDATE ON fx_pit_observations BEGIN SELECT RAISE(ABORT, 'fx_pit_observations append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fx_pit_observations_no_delete
            BEFORE DELETE ON fx_pit_observations BEGIN SELECT RAISE(ABORT, 'fx_pit_observations append-only'); END;
            """
        )


def store_fx_pair_contracts(
    contracts: Iterable[Mapping[str, object]],
    *,
    path: Path = DEFAULT_FX_CARRY_DB_PATH,
    created_at: object | None = None,
) -> int:
    initialize_fx_carry_store(path)
    timestamp = _utc(created_at or datetime.now(timezone.utc).isoformat(), "created_at")
    inserted = 0
    with sqlite3.connect(path) as connection:
        for raw in contracts:
            contract = dict(raw)
            fingerprint = str(contract.get("pair_fingerprint") or "")
            if not fingerprint or _fingerprint({k: v for k, v in contract.items() if k != "pair_fingerprint"}) != fingerprint:
                raise FxCarryContractError("FX-Paar-Fingerprint ist ungültig.")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO fx_pair_contracts VALUES (?, ?, ?, ?)",
                (fingerprint, contract["pair_id"], _canonical_json(contract), timestamp),
            )
            inserted += int(cursor.rowcount)
    return inserted


def store_pit_observations(
    observations: Iterable[Mapping[str, object]],
    *,
    path: Path = DEFAULT_FX_CARRY_DB_PATH,
) -> int:
    initialize_fx_carry_store(path)
    inserted = 0
    with sqlite3.connect(path) as connection:
        for raw in observations:
            item = normalize_pit_observation(raw)
            cursor = connection.execute(
                """INSERT OR IGNORE INTO fx_pit_observations (
                       observation_id, feature, currency, pair_id, effective_at,
                       known_at, available_at, observation_json, observation_fingerprint
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["observation_id"], item["feature"], item["currency"], item["pair_id"],
                    item["effective_at"], item["known_at"], item["available_at"],
                    _canonical_json(item), item["observation_fingerprint"],
                ),
            )
            inserted += int(cursor.rowcount)
    return inserted


def observations_available_at(
    observations: Sequence[Mapping[str, object]],
    cutoff: object,
) -> list[dict[str, object]]:
    cutoff_utc = _utc(cutoff, "cutoff")
    normalized = [normalize_pit_observation(item) for item in observations]
    return [item for item in normalized if str(item["available_at"]) <= cutoff_utc]


def carry_snapshot(
    contract: Mapping[str, object],
    observations: Sequence[Mapping[str, object]],
    *,
    cutoff: object,
) -> dict[str, object]:
    available = observations_available_at(observations, cutoff)

    def latest(feature: str, *, currency: str | None = None, pair_id: str | None = None):
        matches = [
            item for item in available
            if item["feature"] == feature
            and (currency is None or item["currency"] == currency)
            and (pair_id is None or item["pair_id"] == pair_id)
        ]
        return max(matches, key=lambda item: (str(item["available_at"]), str(item["vintage"]))) if matches else None

    base = str(contract["base_currency"])
    quote = str(contract["quote_currency"])
    pair_id = str(contract["pair_id"])
    base_rate = latest("policy_rate", currency=base)
    quote_rate = latest("policy_rate", currency=quote)
    base_expected = latest("expected_policy_rate", currency=base)
    quote_expected = latest("expected_policy_rate", currency=quote)
    realized_vol = latest("realized_volatility", pair_id=pair_id)

    differential = (
        float(base_rate["value"]) - float(quote_rate["value"])
        if base_rate and quote_rate else None
    )
    expected_differential = (
        float(base_expected["value"]) - float(quote_expected["value"])
        if base_expected and quote_expected else None
    )
    carry_to_risk = (
        differential / float(realized_vol["value"])
        if differential is not None and realized_vol and float(realized_vol["value"]) > 0
        else None
    )
    payload: dict[str, object] = {
        "version": FX_CARRY_PIT_VERSION,
        "pair_id": pair_id,
        "cutoff": _utc(cutoff, "cutoff"),
        "base_policy_rate": None if base_rate is None else base_rate["value"],
        "quote_policy_rate": None if quote_rate is None else quote_rate["value"],
        "short_rate_differential": differential,
        "expected_rate_differential": expected_differential,
        "carry_direction": (
            "LONG_BASE" if differential is not None and differential > 0
            else "SHORT_BASE" if differential is not None and differential < 0
            else "NEUTRAL" if differential == 0 else "UNKNOWN"
        ),
        "carry_to_risk": carry_to_risk,
        "future_observations_used": 0,
        "strategy_signal": None,
        "shadow_only": True,
    }
    payload["snapshot_fingerprint"] = _fingerprint(payload)
    return payload


def fx_pipeline_coverage_report(
    observations: Sequence[Mapping[str, object]] = (),
    *,
    contracts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    pair_contracts = dict(contracts or default_fx_pair_contracts())
    normalized = [normalize_pit_observation(item) for item in observations]
    feature_counts = Counter(str(item["feature"]) for item in normalized)
    years_by_pair: dict[str, Counter[str]] = {
        pair_id: Counter() for pair_id in pair_contracts
    }
    for item in normalized:
        pair = str(item.get("pair_id") or "")
        if pair in years_by_pair:
            years_by_pair[pair][str(item["effective_at"])[:4]] += 1
    fields = {
        "pair_identity": "PIT_READY",
        "pair_inversion": "PIT_READY",
        "session_timezone": "PIT_READY",
        "known_at_available_at": "PIT_READY",
        "policy_rates": "PIT_AVAILABLE" if feature_counts["policy_rate"] else "UNAVAILABLE_NO_LOCAL_VINTAGES",
        "expected_rate_differential": "PIT_AVAILABLE" if feature_counts["expected_policy_rate"] else "UNAVAILABLE_NO_HISTORICAL_EXPECTATIONS",
        "central_bank_surprise": "PIT_AVAILABLE" if feature_counts["central_bank_surprise"] else "UNAVAILABLE_NO_PRE_RELEASE_CONSENSUS",
        "confirmed_interventions": "PIT_AVAILABLE" if feature_counts["confirmed_intervention"] else "UNAVAILABLE_NO_VERSIONED_CONFIRMATIONS",
        "implied_volatility": "PIT_AVAILABLE" if feature_counts["implied_volatility"] else "UNAVAILABLE_NO_LOCAL_HISTORY",
        "cot_positioning": "SHADOW_ONLY_SEPARATE_CONTEXT",
        "historical_bid_ask": "UNAVAILABLE",
        "spread_proxy": "SHADOW_ONLY" if feature_counts["spread_bps"] else "UNAVAILABLE_NO_VERSIONED_PROXY",
        "slippage_stress": "SHADOW_ONLY_NO_FALSE_PRECISION",
    }
    payload: dict[str, object] = {
        "version": FX_CARRY_PIT_VERSION,
        "status": "PARTIAL_READY_TRANSPARENT_LIMITS",
        "pairs": pair_contracts,
        "pair_n": len(pair_contracts),
        "observation_n": len(normalized),
        "feature_counts": dict(sorted(feature_counts.items())),
        "coverage_by_pair_year": {
            pair: dict(sorted(counts.items())) for pair, counts in years_by_pair.items()
        },
        "fields": fields,
        "cost_contract": {
            "version": FX_COST_CONTRACT_VERSION,
            "historical_bid_ask_available": False,
            "numeric_spread_invented": False,
            "numeric_slippage_invented": False,
            "trade_simulation_started": False,
        },
        "revision_policy": "append_vintage_and_select_only_when_available_at_le_cutoff",
        "surprise_without_consensus": "UNAVAILABLE",
        "revised_current_value_backdated": False,
        "strategy_activated": False,
        "research_run_started": False,
    }
    payload["coverage_fingerprint"] = _fingerprint(payload)
    return payload
