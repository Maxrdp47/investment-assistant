from __future__ import annotations

"""Deterministic, Development-only execution infrastructure.

This module plans and persists research work.  It has no strategy, signal,
paper, shadow, broker, order, Validation or Holdout path.
"""

import bisect
import json
import math
import sqlite3
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from fx_carry_pit import default_fx_pair_contracts, normalize_fx_ohlc
from historical_dependency_policy import (
    build_historical_dependency_policy,
    classify_historical_dependency,
)
from multi_asset_development_contract import load_development_contract
from multi_asset_discovery_v1 import (
    MultiAssetDiscoveryContractError,
    build_feature_snapshot,
    build_outcome,
    canonical_json,
    file_sha256,
    fingerprint,
    prepare_indicators,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)
DEFAULT_IDENTITY_STORE = PROJECT_ROOT / "runtime" / "research_identity_registry.sqlite3"
DEFAULT_FX_STORE = (
    PROJECT_ROOT / "runtime" / "fx_historical_pit_2026-09-01-v2.sqlite3"
)
STORE_SCHEMA_VERSION = "multi-asset-discovery-development-store-2026.09.01-v2"
CONTROL_SCHEMA_VERSION = "multi-asset-discovery-development-control-2026.09.01-v2"
WORK_PLAN_VERSION = "multi-asset-discovery-development-work-plan-2026.09.01-v2"


class MultiAssetDevelopmentExecutionError(RuntimeError):
    """The Development runner cannot proceed without violating its contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_identity_registry(path: Path) -> dict[str, object]:
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute(
            "SELECT registry_json FROM registry_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise MultiAssetDevelopmentExecutionError("Identity-Registry ist leer.")
    return json.loads(str(row[0]))


def _manifest_scopes(
    manifest: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    legacy = None
    modern = None
    for raw in (manifest.get("scopes") or {}).values():
        scope = dict(raw)
        contract = dict(scope.get("contract") or {})
        if contract.get("start") == "2010-01-01" and contract.get("end") == "2016-01-01":
            legacy = scope
        if contract.get("start") == "2016-01-01":
            modern = scope
    if legacy is None or modern is None:
        raise MultiAssetDevelopmentExecutionError(
            "Frozen Dataset enthält nicht beide kanonischen Historien-Scope."
        )
    return legacy, modern


def build_development_universe(
    *,
    manifest_path: Path = DEFAULT_DATASET_MANIFEST,
    identity_store: Path = DEFAULT_IDENTITY_STORE,
) -> dict[str, object]:
    contract = load_development_contract()
    references = dict(contract["reference_fingerprints"])
    manifest = _json(manifest_path)
    registry = _read_identity_registry(identity_store)
    if file_sha256(manifest_path) != references.get("dataset_manifest_sha256"):
        raise MultiAssetDevelopmentExecutionError(
            "Dataset-Manifest-SHA256 weicht ab."
        )
    if manifest.get("dataset_fingerprint") != references.get("dataset_fingerprint"):
        raise MultiAssetDevelopmentExecutionError("Dataset-Fingerprint weicht ab.")
    if registry.get("registry_fingerprint") != references.get(
        "identity_registry_fingerprint"
    ):
        raise MultiAssetDevelopmentExecutionError("Identity-Fingerprint weicht ab.")
    legacy_scope, modern_scope = _manifest_scopes(manifest)
    legacy_assets = dict(legacy_scope.get("assets") or {})
    modern_assets = dict(modern_scope.get("assets") or {})
    records = {str(item["ticker"]): dict(item) for item in registry.get("records") or []}
    assets: list[dict[str, object]] = []
    for symbol in sorted(modern_assets):
        modern = dict(modern_assets[symbol])
        if modern.get("status") != "available":
            continue
        identity = records.get(symbol)
        if identity is None:
            raise MultiAssetDevelopmentExecutionError(
                f"Kein Identity-Record für verfügbares Listing {symbol}."
            )
        raw_class = str(identity.get("asset_class") or "").upper()
        asset_class = "CRYPTO" if raw_class == "KRYPTO" else raw_class
        if asset_class not in {"EQUITIES", "ETF", "CRYPTO"}:
            raise MultiAssetDevelopmentExecutionError(
                f"Unzulässige Assetklasse im Universe: {symbol}={raw_class}"
            )
        legacy = dict(legacy_assets.get(symbol) or {})
        assets.append(
            {
                "asset_key": f"{asset_class}:{symbol}",
                "symbol": symbol,
                "asset_class": asset_class,
                "source_type": "FROZEN_PARQUET",
                "modern_file": str(modern["file"]),
                "modern_history_fingerprint": modern["history_fingerprint"],
                "legacy_file": (
                    str(legacy["file"]) if legacy.get("status") == "available" else None
                ),
                "legacy_history_fingerprint": (
                    legacy.get("history_fingerprint")
                    if legacy.get("status") == "available"
                    else None
                ),
                "identity": identity,
                "technical_eligibility_only": True,
                "selected_from_outcome": False,
            }
        )
    for pair in sorted(default_fx_pair_contracts()):
        assets.append(
            {
                "asset_key": f"FX:{pair}",
                "symbol": pair,
                "asset_class": "FX",
                "source_type": "FX_V2_SQLITE",
                "fx_dataset_fingerprint": references["fx_dataset_fingerprint"],
                "identity": None,
                "technical_eligibility_only": True,
                "selected_from_outcome": False,
            }
        )
    assets.sort(key=lambda item: (str(item["asset_class"]), str(item["symbol"])))
    universe_basis = [
        {
            "asset_key": item["asset_key"],
            "asset_class": item["asset_class"],
            "symbol": item["symbol"],
            "source_type": item["source_type"],
            "modern_history_fingerprint": item.get("modern_history_fingerprint"),
            "legacy_history_fingerprint": item.get("legacy_history_fingerprint"),
            "fx_dataset_fingerprint": item.get("fx_dataset_fingerprint"),
        }
        for item in assets
    ]
    payload: dict[str, object] = {
        "version": "multi-asset-discovery-development-universe-2026.09.01-v2",
        "mode": "full_eligibility_universe",
        "assets": assets,
        "asset_count": len(assets),
        "asset_class_counts": {
            name: sum(item["asset_class"] == name for item in assets)
            for name in ("EQUITIES", "ETF", "FX", "CRYPTO")
        },
        "dataset_fingerprint": manifest["dataset_fingerprint"],
        "identity_registry_fingerprint": registry["registry_fingerprint"],
        "fx_dataset_fingerprint": references["fx_dataset_fingerprint"],
        "predictive_prefilter_used": False,
        "outcomes_used_for_selection": False,
    }
    payload["universe_fingerprint"] = fingerprint(universe_basis)
    return payload


def build_work_plan(universe: Mapping[str, object]) -> dict[str, object]:
    contract = load_development_contract()
    execution = dict(contract["development_execution"])
    periods = pd.period_range(
        execution["development_start"], execution["development_end"], freq="Q"
    )
    units: list[dict[str, object]] = []
    for asset in universe.get("assets") or []:
        for period in periods:
            start = max(
                period.start_time.normalize(),
                pd.Timestamp(execution["development_start"]),
            )
            end = min(
                period.end_time.normalize(),
                pd.Timestamp(execution["development_end"]),
            )
            identity = {
                "work_plan_version": WORK_PLAN_VERSION,
                "contract_fingerprint": contract["contract_fingerprint"],
                "universe_fingerprint": universe["universe_fingerprint"],
                "asset_key": asset["asset_key"],
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
            }
            units.append(
                {
                    "work_unit_id": f"mad1-dev-unit-{fingerprint(identity)[:32]}",
                    "asset_key": asset["asset_key"],
                    "asset_class": asset["asset_class"],
                    "symbol": asset["symbol"],
                    "period_start": identity["period_start"],
                    "period_end": identity["period_end"],
                }
            )
    units.sort(
        key=lambda item: (
            str(item["asset_class"]),
            str(item["symbol"]),
            str(item["period_start"]),
        )
    )
    payload: dict[str, object] = {
        "version": WORK_PLAN_VERSION,
        "universe_fingerprint": universe["universe_fingerprint"],
        "total_planned_work_units": len(units),
        "units": units,
        "partition": "asset_by_calendar_quarter",
        "development_only": True,
        "validation_opened": False,
        "holdout_opened": False,
    }
    payload["work_plan_fingerprint"] = fingerprint(units)
    return payload


def _load_fx_history(
    *,
    path: Path,
    pair: str,
    development_start: str,
    development_end: str,
    expected_dataset_fingerprint: str | None = None,
) -> tuple[pd.DataFrame, dict[str, str], str]:
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT record_json FROM historical_fx_records "
            "WHERE pair_id=? AND feature='PRICE' AND pit_eligible=1 "
            "ORDER BY observation_date",
            (pair,),
        ).fetchall()
        version = connection.execute(
            "SELECT dataset_fingerprint FROM fx_dataset_versions "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    if version is None:
        raise MultiAssetDevelopmentExecutionError("FX-v2-Fingerprint fehlt.")
    if expected_dataset_fingerprint is not None and str(version[0]) != str(
        expected_dataset_fingerprint
    ):
        raise MultiAssetDevelopmentExecutionError(
            "FX-v2-Dataset-Fingerprint weicht vom Development-Contract ab."
        )
    values: list[dict[str, object]] = []
    availability: dict[str, str] = {}
    pair_contract = default_fx_pair_contracts()[pair]
    for row in rows:
        record = json.loads(str(row[0]))
        day = str(record["observation_date"])
        if day < development_start or day > development_end:
            continue
        normalized = normalize_fx_ohlc(
            pair_contract, dict(record["metadata"]["ohlc"])
        )
        values.append(
            {"Date": day, **{key.title(): value for key, value in normalized.items()}}
        )
        availability[day] = str(record["available_at"])
    frame = pd.DataFrame(values).set_index("Date")
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    prepared = prepare_indicators(frame)
    if not bool(prepared["OHLC_ENVELOPE_VALID"].all()):
        raise MultiAssetDevelopmentExecutionError(
            f"FX-v2 enthält aktive Hüllenverletzungen: {pair}"
        )
    return frame, availability, f"fx-historical-pit:{version[0]}"


def load_asset_history(
    asset: Mapping[str, object],
    *,
    manifest_path: Path = DEFAULT_DATASET_MANIFEST,
    fx_store: Path = DEFAULT_FX_STORE,
) -> tuple[pd.DataFrame, dict[str, str], str]:
    contract = load_development_contract()
    execution = dict(contract["development_execution"])
    development_end = str(execution["development_end"])
    if asset["source_type"] == "FX_V2_SQLITE":
        return _load_fx_history(
            path=fx_store,
            pair=str(asset["symbol"]),
            development_start=str(execution["development_start"]),
            development_end=development_end,
            expected_dataset_fingerprint=str(
                dict(contract["reference_fingerprints"])["fx_dataset_fingerprint"]
            ),
        )
    root = Path(manifest_path).parent
    relative = asset.get("modern_file")
    history_fingerprint = asset.get("modern_history_fingerprint")
    if not relative or not history_fingerprint:
        raise MultiAssetDevelopmentExecutionError(
            f"Keine moderne Frozen-Historie für {asset['asset_key']}."
        )
    # The modern parquet also contains later observations.  Predicate pushdown
    # keeps Validation/Holdout rows out of the Development frame, while the
    # lower bound prevents the legacy Validation/Holdout epoch from being used
    # as indicator warm-up for the modern Development stage.
    frame = pd.read_parquet(
        root / str(relative),
        filters=[
            ("Date", ">=", pd.Timestamp(execution["development_start"])),
            ("Date", "<=", pd.Timestamp(development_end)),
        ],
    )
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.loc[~frame.index.duplicated(keep="last")]
    if frame.empty:
        raise MultiAssetDevelopmentExecutionError(
            f"Keine Development-Balken für {asset['asset_key']}."
        )
    if frame.index.min() < pd.Timestamp(execution["development_start"]):
        raise MultiAssetDevelopmentExecutionError("Legacy-Daten im Development-Frame.")
    if frame.index.max() > pd.Timestamp(development_end):
        raise MultiAssetDevelopmentExecutionError(
            "Validation-/Holdout-Daten im Development-Frame."
        )
    dataset_fingerprint = str(
        dict(contract["reference_fingerprints"])["dataset_fingerprint"]
    )
    return frame, {}, f"{dataset_fingerprint}:{history_fingerprint}"


def _precompute_swings(
    prepared: pd.DataFrame, *, kind: str
) -> list[dict[str, object]]:
    values = prepared["Low" if kind == "low" else "High"].to_numpy(dtype=float)
    closes = prepared["Close"].to_numpy(dtype=float)
    atrs = prepared["ATR_14"].to_numpy(dtype=float)
    swings: list[dict[str, object]] = []
    for candidate in range(2, max(2, len(prepared) - 2)):
        if not math.isfinite(atrs[candidate]):
            continue
        neighborhood = values[candidate - 2 : candidate + 3]
        price = values[candidate]
        is_pivot = (
            price <= np.min(neighborhood)
            if kind == "low"
            else price >= np.max(neighborhood)
        )
        if not is_pivot:
            continue
        threshold = price + atrs[candidate] if kind == "low" else price - atrs[candidate]
        forward = closes[candidate + 2 :]
        matches = np.flatnonzero(
            forward >= threshold if kind == "low" else forward <= threshold
        )
        if not len(matches):
            continue
        confirmed = int(candidate + 2 + matches[0])
        swings.append(
            {
                "kind": kind,
                "candidate_position": candidate,
                "candidate_day": prepared.index[candidate].date().isoformat(),
                "confirmed_position": confirmed,
                "confirmed_day": prepared.index[confirmed].date().isoformat(),
                "price": float(price),
                "atr_14_at_reaction": float(atrs[candidate]),
            }
        )
    return swings


def precompute_structure_history(
    prepared: pd.DataFrame,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return exact safe/sell zones for every completed bar without rule changes."""

    lows = _precompute_swings(prepared, kind="low")
    highs = _precompute_swings(prepared, kind="high")
    low_events: dict[int, list[int]] = defaultdict(list)
    high_events: dict[int, list[int]] = defaultdict(list)
    for index, item in enumerate(lows):
        low_events[int(item["confirmed_position"])].append(index)
    for index, item in enumerate(highs):
        high_events[int(item["confirmed_position"])].append(index)
    pair_events: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for right_index, right in enumerate(lows):
        for left_index in range(right_index):
            left = lows[left_index]
            limit = min(
                float(left["atr_14_at_reaction"]),
                float(right["atr_14_at_reaction"]),
            )
            if abs(float(left["price"]) - float(right["price"])) <= limit:
                available = max(
                    int(left["confirmed_position"]), int(right["confirmed_position"])
                )
                pair_events[available].append((right_index, left_index))
    active_lows: list[int] = []
    active_highs: list[int] = []
    active_pairs: list[tuple[int, int]] = []
    safe_history: list[dict[str, object]] = []
    sell_history: list[dict[str, object]] = []
    for position in range(len(prepared)):
        for index in low_events.get(position, []):
            bisect.insort(active_lows, index)
        for index in high_events.get(position, []):
            bisect.insort(active_highs, index)
        active_pairs.extend(pair_events.get(position, []))
        last_low = (
            lows[
                max(
                    active_lows,
                    key=lambda index: (
                        int(lows[index]["confirmed_position"]),
                        -index,
                    ),
                )
            ]
            if active_lows
            else None
        )
        support = None
        if active_pairs:
            right_index, left_index = max(active_pairs, key=lambda pair: (pair[0], pair[1]))
            right = lows[right_index]
            left = lows[left_index]
            support = {
                "lower": min(float(left["price"]), float(right["price"])),
                "upper": max(float(left["price"]), float(right["price"])),
                "reaction_days": [left["candidate_day"], right["candidate_day"]],
                "confirmed_days": [left["confirmed_day"], right["confirmed_day"]],
                "confirmed_position": max(
                    int(left["confirmed_position"]), int(right["confirmed_position"])
                ),
            }
        atr = prepared.iloc[position].get("ATR_14")
        atr_value = float(atr) if pd.notna(atr) and math.isfinite(float(atr)) else None
        zone_a = (
            {
                "model": "A_CONFIRMED_SWING_LOW",
                "status": "AVAILABLE",
                "lower": float(last_low["price"]),
                "upper": float(last_low["price"]),
                "source": last_low,
            }
            if last_low
            else {
                "model": "A_CONFIRMED_SWING_LOW",
                "status": "UNAVAILABLE",
                "reason": "NO_CONFIRMED_SWING_LOW",
            }
        )
        zone_b = (
            {"model": "B_CONFIRMED_SUPPORT_ZONE", "status": "AVAILABLE", **support}
            if support
            else {
                "model": "B_CONFIRMED_SUPPORT_ZONE",
                "status": "UNAVAILABLE",
                "reason": "TWO_CONFIRMED_REACTIONS_NOT_AVAILABLE",
            }
        )
        base = support or (
            {
                "lower": float(last_low["price"]),
                "upper": float(last_low["price"]),
                "source": last_low,
            }
            if last_low
            else None
        )
        zone_c = (
            {
                "model": "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
                "status": "AVAILABLE",
                "lower": float(base["lower"]) - 0.5 * float(atr_value),
                "upper": float(base["upper"]),
                "base_model": (
                    "B_CONFIRMED_SUPPORT_ZONE"
                    if support
                    else "A_CONFIRMED_SWING_LOW"
                ),
                "atr_14": float(atr_value),
            }
            if base is not None and atr_value is not None
            else {
                "model": "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
                "status": "UNAVAILABLE",
                "reason": "STRUCTURE_OR_ATR_UNAVAILABLE",
            }
        )
        safe = {
            "safe_zone_version": "multi-asset-safe-zones-2026.08.31-v1",
            "A": zone_a,
            "B": zone_b,
            "C": zone_c,
            "confirmed_swing_low_count": len(active_lows),
            "original_zone_immutable": True,
        }
        close = float(prepared.iloc[position]["Close"])
        above = [highs[index] for index in active_highs if float(highs[index]["price"]) > close]
        resistance = min(above, key=lambda item: float(item["price"])) if above else None
        sell_a = (
            {"status": "AVAILABLE", "value": float(resistance["price"]), "source": resistance}
            if resistance
            else {
                "status": "UNAVAILABLE",
                "value": None,
                "reason": "NO_PRIOR_CONFIRMED_RESISTANCE_ABOVE_CLOSE",
            }
        )
        structural_base = dict(zone_b)
        if structural_base.get("status") != "AVAILABLE":
            structural_base = dict(zone_a)
        if resistance and structural_base.get("status") == "AVAILABLE":
            base_upper = float(structural_base["upper"])
            sell_b = {
                "status": "AVAILABLE",
                "value": float(resistance["price"])
                + (float(resistance["price"]) - base_upper),
                "structural_base_upper": base_upper,
            }
        else:
            sell_b = {
                "status": "UNAVAILABLE",
                "value": None,
                "reason": "STRUCTURAL_ANCHORS_UNAVAILABLE",
            }
        sell_c = (
            {
                "status": "AVAILABLE",
                "value": close + 2.0 * float(atr_value),
                "signal_close": close,
                "atr_14": atr_value,
            }
            if atr_value is not None
            else {"status": "UNAVAILABLE", "value": None, "reason": "ATR14_UNAVAILABLE"}
        )
        sell = {
            "sell_zone_version": "multi-asset-sell-zones-2026.08.31-v1",
            "A": sell_a,
            "B": sell_b,
            "C": sell_c,
            "measurement_only": True,
            "automatic_exit_allowed": False,
        }
        safe_history.append(safe)
        sell_history.append(sell)
    return safe_history, sell_history


def _fx_asset(pair: str) -> dict[str, object]:
    token = pair.replace("/", "-").lower()
    return {
        "pair_id": pair,
        "asset_id": f"fx-pair:{token}",
        "asset_class": "FX",
        "listing_id": f"fx-listing:{token}",
        "issuer_id": None,
        "mapping_status": "UNRESOLVED",
        "dependency_status": "UNKNOWN",
        "pit_trading_feature": False,
    }


def _historical_asset(
    asset: Mapping[str, object], *, signal_day: str
) -> dict[str, object]:
    if asset["asset_class"] == "FX":
        return _fx_asset(str(asset["symbol"]))
    identity = dict(asset.get("identity") or {})
    historical = classify_historical_dependency(
        identity,
        as_of=signal_day,
        policy=build_historical_dependency_policy(),
    )
    return {
        "ticker": asset["symbol"],
        "asset_id": identity.get("asset_id") or asset["asset_key"],
        "asset_class": asset["asset_class"],
        "listing_id": identity.get("listing_id"),
        "issuer_id": historical.get("issuer_id"),
        "mapping_status": identity.get("mapping_status") or "UNRESOLVED",
        "dependency_status": historical["dependency_status"],
        "historical_dependency_policy_version": historical[
            "historical_dependency_policy_version"
        ],
        "historical_dependency_policy_fingerprint": historical[
            "historical_dependency_policy_fingerprint"
        ],
        "historical_dependency_reason": historical["historical_dependency_reason"],
        "pit_trading_feature": False,
    }


def _invalid_outcome(
    feature: Mapping[str, object], *, reason: str
) -> dict[str, object]:
    payload: dict[str, object] = {
        "outcome_version": "multi-asset-discovery-outcomes-2026.08.31-v1",
        "contract_version": feature["contract_version"],
        "case_id": feature["case_id"],
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": feature["asset_id"],
        "symbol": feature["symbol"],
        "asset_class": feature["asset_class"],
        "listing_id": feature.get("listing_id"),
        "issuer_id": feature.get("issuer_id"),
        "mapping_status": feature.get("mapping_status"),
        "dependency_status": feature.get("dependency_status"),
        "research_split": feature["research_split"],
        "signal_day": feature["signal_day"],
        "status": "INVALID_TECHNICAL_ELIGIBILITY",
        "reason": reason,
        "future_features_written_to_feature_store": False,
        "no_intrabar_order_invented": True,
    }
    payload["outcome_fingerprint"] = fingerprint(payload)
    return payload


def execute_work_unit(
    *,
    asset: Mapping[str, object],
    unit: Mapping[str, object],
    prepared: pd.DataFrame,
    availability: Mapping[str, str],
    source_dataset_fingerprint: str,
    safe_history: Sequence[Mapping[str, object]],
    sell_history: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    contract = load_development_contract()
    execution = dict(contract["development_execution"])
    minimum = int(execution["minimum_history_observations"])
    positions = [
        position
        for position, stamp in enumerate(prepared.index)
        if unit["period_start"] <= stamp.date().isoformat() <= unit["period_end"]
        and position >= minimum - 1
        and position < len(prepared) - 1
    ]
    features: list[dict[str, object]] = []
    outcomes: list[dict[str, object]] = []
    for position in positions:
        signal_day = prepared.index[position].date().isoformat()
        if not execution["development_start"] <= signal_day <= execution["development_end"]:
            raise MultiAssetDevelopmentExecutionError("Signal außerhalb Development.")
        decision_time = (
            str(availability[signal_day])
            if asset["asset_class"] == "FX"
            else f"{signal_day}T23:59:59+00:00"
        )
        feature = build_feature_snapshot(
            asset=_historical_asset(asset, signal_day=signal_day),
            frame=prepared,
            prepared_frame=prepared,
            decision_position=position,
            decision_time=decision_time,
            dataset_fingerprint=source_dataset_fingerprint,
            safe_zones_override=safe_history[position],
            sell_zones_override=sell_history[position],
            execution_contract_version=str(contract["contract_version"]),
        )
        if feature["research_split"] != "development":
            raise MultiAssetDevelopmentExecutionError(
                "Runner versuchte Nicht-Development-Snapshot."
            )
        anomaly_to_decision = int(
            dict(feature["source_integrity"]).get(
                "ohlc_envelope_anomaly_count_to_decision"
            )
            or 0
        )
        try:
            if anomaly_to_decision:
                raise MultiAssetDiscoveryContractError(
                    "SOURCE_OHLC_ENVELOPE_ANOMALY"
                )
            outcome = build_outcome(
                feature_snapshot=feature,
                frame=prepared,
                prepared_frame=prepared,
                safe_zone_history=safe_history,
            )
            if int(
                dict(outcome.get("source_integrity") or {}).get(
                    "ohlc_envelope_anomaly_count_in_outcome"
                )
                or 0
            ):
                outcome = _invalid_outcome(
                    feature, reason="SOURCE_OHLC_ENVELOPE_ANOMALY"
                )
        except MultiAssetDiscoveryContractError as exc:
            reason = str(exc)
            if reason not in {
                "SOURCE_OHLC_ENVELOPE_ANOMALY",
                "Strukturelles R ist für den Pilotfall nicht definiert.",
            }:
                raise
            outcome = _invalid_outcome(feature, reason=reason)
        features.append(feature)
        outcomes.append(outcome)
    return {
        "features": features,
        "outcomes": outcomes,
        "planned_signal_positions": len(positions),
        "invalid_cases": sum(
            item.get("status") == "INVALID_TECHNICAL_ELIGIBILITY"
            for item in outcomes
        ),
        "censored_cases": sum(
            item.get("status") == "CENSORED_AT_STAGE_BOUNDARY"
            for item in outcomes
        ),
    }


def _connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=60)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _append_only_triggers(table: str) -> str:
    return f"""
    CREATE TRIGGER IF NOT EXISTS {table}_no_update
    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'append_only'); END;
    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'append_only'); END;
    """


def initialize_development_stores(
    *, feature_path: Path, outcome_path: Path, control_path: Path
) -> None:
    if Path(feature_path).resolve() == Path(outcome_path).resolve():
        raise MultiAssetDevelopmentExecutionError(
            "Feature- und Outcome-Store müssen physisch getrennt sein."
        )
    with _connect(feature_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS store_metadata (
                metadata_fingerprint TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feature_rows (
                case_id TEXT PRIMARY KEY,
                feature_fingerprint TEXT NOT NULL,
                run_id TEXT NOT NULL,
                work_unit_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                research_split TEXT NOT NULL CHECK(research_split='development'),
                dependency_status TEXT NOT NULL,
                payload_zlib BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_feature_run_unit
            ON feature_rows(run_id, work_unit_id);
            """
            + _append_only_triggers("store_metadata")
            + _append_only_triggers("feature_rows")
        )
    with _connect(outcome_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS store_metadata (
                metadata_fingerprint TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outcome_rows (
                case_id TEXT PRIMARY KEY,
                outcome_fingerprint TEXT NOT NULL,
                feature_fingerprint TEXT NOT NULL,
                run_id TEXT NOT NULL,
                work_unit_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                research_split TEXT NOT NULL CHECK(research_split='development'),
                status TEXT NOT NULL,
                dependency_status TEXT NOT NULL,
                payload_zlib BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_outcome_run_unit
            ON outcome_rows(run_id, work_unit_id);
            """
            + _append_only_triggers("store_metadata")
            + _append_only_triggers("outcome_rows")
        )
    with _connect(control_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                contract_fingerprint TEXT NOT NULL,
                universe_fingerprint TEXT NOT NULL,
                work_plan_fingerprint TEXT NOT NULL,
                run_manifest_fingerprint TEXT NOT NULL,
                total_planned_work_units INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                last_checkpoint_at TEXT NOT NULL,
                last_completed_work_unit TEXT,
                feature_rows INTEGER NOT NULL DEFAULT 0,
                outcome_rows INTEGER NOT NULL DEFAULT 0,
                invalid_cases INTEGER NOT NULL DEFAULT 0,
                censored_cases INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS work_units (
                work_unit_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                asset_key TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                symbol TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                feature_rows INTEGER NOT NULL DEFAULT 0,
                outcome_rows INTEGER NOT NULL DEFAULT 0,
                invalid_cases INTEGER NOT NULL DEFAULT 0,
                censored_cases INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                last_error_class TEXT,
                last_error_message TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_work_units_run_status
            ON work_units(run_id, status, asset_class, symbol, period_start);
            CREATE TABLE IF NOT EXISTS run_events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                work_unit_id TEXT,
                event_type TEXT NOT NULL,
                event_at TEXT NOT NULL,
                event_json TEXT NOT NULL
            );
            """
            + _append_only_triggers("run_events")
        )


def _compress(payload: Mapping[str, object]) -> bytes:
    return zlib.compress(canonical_json(payload).encode("utf-8"), level=6)


def decode_payload(value: bytes) -> dict[str, object]:
    return json.loads(zlib.decompress(value).decode("utf-8"))


def _insert_store_metadata(
    path: Path, metadata: Mapping[str, object]
) -> None:
    content = canonical_json(metadata)
    key = fingerprint(metadata)
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT metadata_json FROM store_metadata WHERE metadata_fingerprint=?",
            (key,),
        ).fetchone()
        if existing is not None and str(existing[0]) != content:
            raise MultiAssetDevelopmentExecutionError("Store-Metadaten-Konflikt.")
        connection.execute(
            "INSERT OR IGNORE INTO store_metadata(metadata_fingerprint, metadata_json) "
            "VALUES (?,?)",
            (key, content),
        )


def persist_work_unit_evidence(
    *,
    run_id: str,
    work_unit_id: str,
    features: Sequence[Mapping[str, object]],
    outcomes: Sequence[Mapping[str, object]],
    feature_path: Path,
    outcome_path: Path,
) -> tuple[int, int]:
    feature_inserted = 0
    with _connect(feature_path) as connection:
        for item in features:
            existing = connection.execute(
                "SELECT feature_fingerprint FROM feature_rows WHERE case_id=?",
                (item["case_id"],),
            ).fetchone()
            if existing is not None:
                if str(existing[0]) != str(item["feature_fingerprint"]):
                    raise MultiAssetDevelopmentExecutionError(
                        f"Feature-Append-only-Konflikt: {item['case_id']}"
                    )
                continue
            connection.execute(
                "INSERT INTO feature_rows(case_id,feature_fingerprint,run_id,work_unit_id,"
                "asset_id,symbol,asset_class,signal_day,research_split,dependency_status,payload_zlib) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["case_id"],
                    item["feature_fingerprint"],
                    run_id,
                    work_unit_id,
                    item["asset_id"],
                    item["symbol"],
                    item["asset_class"],
                    item["signal_day"],
                    item["research_split"],
                    item.get("dependency_status") or "UNKNOWN",
                    _compress(item),
                ),
            )
            feature_inserted += 1
    outcome_inserted = 0
    with _connect(outcome_path) as connection:
        for item in outcomes:
            existing = connection.execute(
                "SELECT outcome_fingerprint FROM outcome_rows WHERE case_id=?",
                (item["case_id"],),
            ).fetchone()
            if existing is not None:
                if str(existing[0]) != str(item["outcome_fingerprint"]):
                    raise MultiAssetDevelopmentExecutionError(
                        f"Outcome-Append-only-Konflikt: {item['case_id']}"
                    )
                continue
            connection.execute(
                "INSERT INTO outcome_rows(case_id,outcome_fingerprint,feature_fingerprint,"
                "run_id,work_unit_id,asset_id,symbol,asset_class,signal_day,research_split,"
                "status,dependency_status,payload_zlib) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["case_id"],
                    item["outcome_fingerprint"],
                    item["feature_fingerprint"],
                    run_id,
                    work_unit_id,
                    item["asset_id"],
                    item["symbol"],
                    item["asset_class"],
                    item["signal_day"],
                    item["research_split"],
                    item["status"],
                    item.get("dependency_status") or "UNKNOWN",
                    _compress(item),
                ),
            )
            outcome_inserted += 1
    return feature_inserted, outcome_inserted


def initialize_run(
    *,
    run_manifest: Mapping[str, object],
    universe: Mapping[str, object],
    work_plan: Mapping[str, object],
    feature_path: Path,
    outcome_path: Path,
    control_path: Path,
) -> str:
    initialize_development_stores(
        feature_path=feature_path, outcome_path=outcome_path, control_path=control_path
    )
    metadata = {
        "schema_version": STORE_SCHEMA_VERSION,
        "contract_version": run_manifest["development_contract_version"],
        "contract_fingerprint": run_manifest["development_contract_fingerprint"],
        "run_id": run_manifest["run_id"],
        "run_manifest_fingerprint": run_manifest["run_manifest_fingerprint"],
        "payload_encoding": "canonical_json_zlib",
        "append_only": True,
    }
    _insert_store_metadata(feature_path, {**metadata, "store_role": "FEATURES"})
    _insert_store_metadata(outcome_path, {**metadata, "store_role": "OUTCOMES"})
    run_id = str(run_manifest["run_id"])
    with _connect(control_path) as connection:
        existing = connection.execute(
            "SELECT contract_fingerprint,universe_fingerprint,work_plan_fingerprint "
            "FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        expected = (
            run_manifest["development_contract_fingerprint"],
            universe["universe_fingerprint"],
            work_plan["work_plan_fingerprint"],
        )
        if existing is not None and tuple(existing) != expected:
            raise MultiAssetDevelopmentExecutionError("Run-ID-Konflikt.")
        connection.execute(
            "INSERT OR IGNORE INTO runs(run_id,contract_fingerprint,universe_fingerprint,"
            "work_plan_fingerprint,run_manifest_fingerprint,total_planned_work_units,status,"
            "started_at,last_checkpoint_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                *expected,
                run_manifest["run_manifest_fingerprint"],
                work_plan["total_planned_work_units"],
                "READY",
                run_manifest["started_at"],
                run_manifest["started_at"],
            ),
        )
        for unit in work_plan["units"]:
            connection.execute(
                "INSERT OR IGNORE INTO work_units(work_unit_id,run_id,asset_key,asset_class,"
                "symbol,period_start,period_end,status) VALUES (?,?,?,?,?,?,?,?)",
                (
                    unit["work_unit_id"],
                    run_id,
                    unit["asset_key"],
                    unit["asset_class"],
                    unit["symbol"],
                    unit["period_start"],
                    unit["period_end"],
                    "PENDING",
                ),
            )
    return run_id


def append_run_event(
    *,
    control_path: Path,
    run_id: str,
    event_type: str,
    work_unit_id: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    event_at = utc_now()
    payload = {
        "run_id": run_id,
        "work_unit_id": work_unit_id,
        "event_type": event_type,
        "event_at": event_at,
        "details": dict(details or {}),
    }
    event_id = f"mad1-event-{fingerprint(payload)[:32]}"
    with _connect(control_path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO run_events(event_id,run_id,work_unit_id,event_type,event_at,event_json) "
            "VALUES (?,?,?,?,?,?)",
            (event_id, run_id, work_unit_id, event_type, event_at, canonical_json(payload)),
        )


def resume_interrupted_units(*, control_path: Path, run_id: str) -> int:
    with _connect(control_path) as connection:
        rows = connection.execute(
            "SELECT work_unit_id FROM work_units WHERE run_id=? AND status='RUNNING'",
            (run_id,),
        ).fetchall()
        connection.execute(
            "UPDATE work_units SET status='PENDING',started_at=NULL "
            "WHERE run_id=? AND status='RUNNING'",
            (run_id,),
        )
    return len(rows)


def claim_next_work_unit(
    *, control_path: Path, run_id: str
) -> dict[str, object] | None:
    with _connect(control_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT work_unit_id,asset_key,asset_class,symbol,period_start,period_end,attempts "
            "FROM work_units WHERE run_id=? AND status='PENDING' "
            "ORDER BY asset_class,symbol,period_start LIMIT 1",
            (run_id,),
        ).fetchone()
        if row is None:
            connection.commit()
            return None
        started_at = utc_now()
        connection.execute(
            "UPDATE work_units SET status='RUNNING',attempts=attempts+1,started_at=?,"
            "last_error_class=NULL,last_error_message=NULL WHERE work_unit_id=?",
            (started_at, row[0]),
        )
        connection.execute(
            "UPDATE runs SET status='RUNNING',last_checkpoint_at=? WHERE run_id=?",
            (started_at, run_id),
        )
        connection.commit()
    return {
        "work_unit_id": row[0],
        "asset_key": row[1],
        "asset_class": row[2],
        "symbol": row[3],
        "period_start": row[4],
        "period_end": row[5],
        "attempts": int(row[6]) + 1,
    }


def complete_work_unit(
    *,
    control_path: Path,
    run_id: str,
    unit: Mapping[str, object],
    feature_rows: int,
    outcome_rows: int,
    invalid_cases: int,
    censored_cases: int,
) -> None:
    completed_at = utc_now()
    status = "SKIPPED" if feature_rows == 0 and outcome_rows == 0 else "COMPLETED"
    with _connect(control_path) as connection:
        connection.execute(
            "UPDATE work_units SET status=?,feature_rows=?,outcome_rows=?,invalid_cases=?,"
            "censored_cases=?,completed_at=? WHERE work_unit_id=?",
            (
                status,
                feature_rows,
                outcome_rows,
                invalid_cases,
                censored_cases,
                completed_at,
                unit["work_unit_id"],
            ),
        )
        connection.execute(
            "UPDATE runs SET last_checkpoint_at=?,last_completed_work_unit=?,"
            "feature_rows=feature_rows+?,outcome_rows=outcome_rows+?,"
            "invalid_cases=invalid_cases+?,censored_cases=censored_cases+? WHERE run_id=?",
            (
                completed_at,
                unit["work_unit_id"],
                feature_rows,
                outcome_rows,
                invalid_cases,
                censored_cases,
                run_id,
            ),
        )


def fail_work_unit(
    *,
    control_path: Path,
    run_id: str,
    unit: Mapping[str, object],
    error: BaseException,
    maximum_attempts: int,
) -> str:
    retry = int(unit["attempts"]) < maximum_attempts
    status = "PENDING" if retry else "FAILED"
    with _connect(control_path) as connection:
        connection.execute(
            "UPDATE work_units SET status=?,last_error_class=?,last_error_message=? "
            "WHERE work_unit_id=?",
            (
                status,
                type(error).__name__,
                str(error)[:1000],
                unit["work_unit_id"],
            ),
        )
        connection.execute(
            "UPDATE runs SET last_checkpoint_at=? WHERE run_id=?",
            (utc_now(), run_id),
        )
    return "RETRY" if retry else "FAILED"


def checkpoint_status(*, control_path: Path, run_id: str) -> dict[str, object]:
    uri = f"file:{Path(control_path).resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        run = connection.execute(
            "SELECT status,total_planned_work_units,last_checkpoint_at,last_completed_work_unit,"
            "feature_rows,outcome_rows,invalid_cases,censored_cases,started_at,completed_at "
            "FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise MultiAssetDevelopmentExecutionError("Run fehlt im Control-Store.")
        counts = {
            row[0]: int(row[1])
            for row in connection.execute(
                "SELECT status,COUNT(*) FROM work_units WHERE run_id=? GROUP BY status",
                (run_id,),
            )
        }
        retries = int(
            connection.execute(
                "SELECT COALESCE(SUM(CASE WHEN attempts>1 THEN attempts-1 ELSE 0 END),0) "
                "FROM work_units WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
        )
    completed_units = counts.get("COMPLETED", 0) + counts.get("SKIPPED", 0)
    total = int(run[1])
    return {
        "run_id": run_id,
        "status": run[0],
        "total_planned_work_units": total,
        "completed": counts.get("COMPLETED", 0),
        "skipped": counts.get("SKIPPED", 0),
        "failed": counts.get("FAILED", 0),
        "active": counts.get("RUNNING", 0),
        "pending": counts.get("PENDING", 0),
        "retried": retries,
        "progress_pct": round(100.0 * completed_units / total, 6) if total else 0.0,
        "last_checkpoint": run[2],
        "last_completed_work_unit": run[3],
        "feature_rows": int(run[4]),
        "outcome_rows": int(run[5]),
        "invalid_cases": int(run[6]),
        "censored_cases": int(run[7]),
        "started_at": run[8],
        "completed_at": run[9],
        "run_health": "HEALTHY" if counts.get("FAILED", 0) == 0 else "DEGRADED",
    }


def mark_run_complete(*, control_path: Path, run_id: str) -> bool:
    status = checkpoint_status(control_path=control_path, run_id=run_id)
    terminal = status["pending"] == 0 and status["active"] == 0
    if not terminal:
        return False
    final_status = "COMPLETED" if status["failed"] == 0 else "COMPLETED_WITH_FAILURES"
    with _connect(control_path) as connection:
        connection.execute(
            "UPDATE runs SET status=?,completed_at=?,last_checkpoint_at=? WHERE run_id=?",
            (final_status, utc_now(), utc_now(), run_id),
        )
    return True


def audit_development_stores(
    *, feature_path: Path, outcome_path: Path, control_path: Path, run_id: str
) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, path, table in (
        ("feature", feature_path, "feature_rows"),
        ("outcome", outcome_path, "outcome_rows"),
        ("control", control_path, "work_units"),
    ):
        uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            result[f"{name}_quick_check"] = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
            result[f"{name}_foreign_key_issues"] = len(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            )
            result[f"{name}_rows"] = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                    + (" WHERE run_id=?" if name != "control" else " WHERE run_id=?"),
                    (run_id,),
                ).fetchone()[0]
            )
    result["physically_separate"] = len(
        {Path(feature_path).resolve(), Path(outcome_path).resolve(), Path(control_path).resolve()}
    ) == 3
    result["all_integrity_ok"] = all(
        result.get(f"{name}_quick_check") == "ok"
        and result.get(f"{name}_foreign_key_issues") == 0
        for name in ("feature", "outcome", "control")
    )
    return result
