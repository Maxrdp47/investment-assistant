from __future__ import annotations

"""Pure compute layer for the versioned Development-v6 reprocessing run.

Workers call only :func:`compute_v6_asset_batch`.  It reads immutable input
projections and returns ordinary Python payloads; it never opens an evidence
store.  The main runner is therefore the sole SQLite writer.
"""

import math
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from historical_dependency_policy import build_historical_dependency_policy
from multi_asset_development_execution import (
    _historical_asset,
    build_development_universe,
    precompute_structure_history,
)
from multi_asset_development_v6_inputs import (
    DEFAULT_CRYPTO_STORE,
    DEFAULT_EQUITY_ETF_STORE,
    DEFAULT_FX_STORE,
    DEFAULT_INPUT_PRECHECK_ARTIFACT,
    MINIMUM_SEGMENT_HISTORY,
    SegmentedAssetHistory,
    load_v6_asset_history,
)
from multi_asset_development_v6_outcomes import (
    build_outcome_v6,
    prepare_outcome_segment_v6,
)
from multi_asset_discovery_v1 import (
    PreparedFeatureSnapshotContext,
    build_feature_snapshot,
    fingerprint,
    prepare_feature_snapshot_context,
    prepare_indicators,
)


UNIVERSE_VERSION = "multi-asset-development-universe-2026.09.05-v6"
WORK_PLAN_VERSION = "multi-asset-development-work-plan-2026.09.05-v6"
COMPUTE_VERSION = "multi-asset-development-compute-2026.09.05-v6"


class DevelopmentV6ExecutionError(RuntimeError):
    """The v6 computation cannot continue without changing its contract."""


def build_v6_universe(
    *,
    combined_input_fingerprint: str,
    equity_etf_projection_fingerprint: str,
    crypto_projection_fingerprint: str,
    fx_projection_fingerprint: str,
) -> dict[str, object]:
    """Rebind the unchanged v5 eligibility universe to the audited inputs."""

    parent = build_development_universe()
    assets: list[dict[str, object]] = []
    for raw in parent.get("assets") or []:
        item = dict(raw)
        asset_class = str(item["asset_class"])
        if asset_class in {"EQUITIES", "ETF"}:
            source_type = "EQUITY_ETF_PIT_PROJECTION_V1"
            projection_fingerprint = equity_etf_projection_fingerprint
        elif asset_class == "CRYPTO":
            source_type = "CRYPTO_PIT_PROJECTION_V1"
            projection_fingerprint = crypto_projection_fingerprint
        elif asset_class == "FX":
            source_type = "FX_PIT_PROJECTION_V2"
            projection_fingerprint = fx_projection_fingerprint
        else:  # pragma: no cover - parent loader already fails closed
            raise DevelopmentV6ExecutionError(f"Unexpected asset class: {asset_class}")
        item["source_type"] = source_type
        item["projection_fingerprint"] = projection_fingerprint
        item.pop("modern_file", None)
        item.pop("legacy_file", None)
        item.pop("modern_history_fingerprint", None)
        item.pop("legacy_history_fingerprint", None)
        item.pop("fx_dataset_fingerprint", None)
        assets.append(item)
    assets.sort(key=lambda item: (str(item["asset_class"]), str(item["symbol"])))
    basis = [
        {
            "asset_key": item["asset_key"],
            "asset_class": item["asset_class"],
            "symbol": item["symbol"],
            "source_type": item["source_type"],
            "projection_fingerprint": item["projection_fingerprint"],
            "asset_id": (item.get("identity") or {}).get("asset_id"),
            "listing_id": (item.get("identity") or {}).get("listing_id"),
        }
        for item in assets
    ]
    payload: dict[str, object] = {
        "version": UNIVERSE_VERSION,
        "parent_universe_fingerprint": parent["universe_fingerprint"],
        "combined_input_fingerprint": combined_input_fingerprint,
        "assets": assets,
        "asset_count": len(assets),
        "asset_class_counts": {
            name: sum(item["asset_class"] == name for item in assets)
            for name in ("EQUITIES", "ETF", "FX", "CRYPTO")
        },
        "eligibility_universe_changed": False,
        "predictive_prefilter_used": False,
        "outcomes_used_for_selection": False,
        "validation_opened": False,
        "holdout_opened": False,
    }
    payload["universe_fingerprint"] = fingerprint(
        {
            "combined_input_fingerprint": combined_input_fingerprint,
            "assets": basis,
        }
    )
    return payload


def build_v6_work_plan(
    *, universe: Mapping[str, object], contract: Mapping[str, object]
) -> dict[str, object]:
    execution = dict(contract["development_execution"])
    periods = pd.period_range(
        str(execution["development_start"]),
        str(execution["development_end"]),
        freq="Q",
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
                "version": WORK_PLAN_VERSION,
                "contract_fingerprint": contract["contract_fingerprint"],
                "universe_fingerprint": universe["universe_fingerprint"],
                "asset_key": asset["asset_key"],
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
            }
            units.append(
                {
                    "work_unit_id": "madv6-unit-" + fingerprint(identity)[:32],
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
        "partition": "asset_by_calendar_quarter",
        "total_planned_work_units": len(units),
        "units": units,
        "development_only": True,
        "validation_opened": False,
        "holdout_opened": False,
    }
    payload["work_plan_fingerprint"] = fingerprint(units)
    return payload


def _decision_time(
    history: SegmentedAssetHistory, asset: Mapping[str, object], signal_day: str
) -> str:
    if str(asset["asset_class"]) == "FX":
        try:
            return str(history.availability[signal_day])
        except KeyError as exc:
            raise DevelopmentV6ExecutionError(
                f"Missing FX PIT availability at {asset['asset_key']} {signal_day}."
            ) from exc
    return f"{signal_day}T23:59:59+00:00"


def _feature_with_input_provenance(
    *,
    asset: Mapping[str, object],
    history: SegmentedAssetHistory,
    prepared: pd.DataFrame,
    local_position: int,
    safe_history: Sequence[Mapping[str, object]],
    sell_history: Sequence[Mapping[str, object]],
    contract: Mapping[str, object],
    segment_id: int,
    source_fingerprint: str,
    feature_context: PreparedFeatureSnapshotContext,
    dependency_policy: Mapping[str, object] | None,
) -> dict[str, object]:
    signal_day = prepared.index[local_position].date().isoformat()
    feature = build_feature_snapshot(
        asset=_historical_asset(
            asset,
            signal_day=signal_day,
            dependency_policy=dependency_policy,
        ),
        frame=prepared,
        prepared_frame=prepared,
        decision_position=local_position,
        decision_time=_decision_time(history, asset, signal_day),
        dataset_fingerprint=source_fingerprint,
        safe_zones_override=safe_history[local_position],
        sell_zones_override=sell_history[local_position],
        execution_contract_version=str(contract["contract_version"]),
        prepared_context=feature_context,
    )
    if feature.get("research_split") != "development":
        raise DevelopmentV6ExecutionError("Non-Development feature escaped stage gate.")
    feature["input_provenance"] = {
        "combined_input_fingerprint": history.combined_input_fingerprint,
        "projection_fingerprint": history.dataset_fingerprint,
        "source_fingerprint": source_fingerprint,
        "gap_policy_fingerprint": dict(contract["reference_fingerprints"])[
            "gap_policy_fingerprint"
        ],
        "segment_id": str(segment_id),
        "segment_position": int(prepared.iloc[local_position]["SEGMENT_POSITION"]),
        "minimum_same_segment_history": MINIMUM_SEGMENT_HISTORY,
        "provider_values_repaired": False,
    }
    feature["segment_id"] = str(segment_id)
    feature.pop("feature_fingerprint", None)
    feature["feature_fingerprint"] = fingerprint(feature)
    return feature


def _empty_unit_summary() -> dict[str, object]:
    return {
        "r_na_cases": 0,
        "censored_cases": 0,
        "input_gap_censored_cases": 0,
        "end_of_data_censored_cases": 0,
        "stage_censored_cases": 0,
        "missing_reference_entry": 0,
        "missingness_exclusions": 0,
        "minimum_history_exclusions": 0,
        "gap_boundary_count": 0,
    }


def _position_ranges_by_unit(
    index: pd.DatetimeIndex,
    units: Sequence[Mapping[str, object]],
) -> dict[str, range]:
    """Index each claimed period once without scanning every bar per unit."""

    if not index.is_monotonic_increasing:
        raise DevelopmentV6ExecutionError(
            "Prepared segment index must be ordered before work-unit indexing."
        )
    ranges: dict[str, range] = {}
    for unit in units:
        start = int(index.searchsorted(pd.Timestamp(str(unit["period_start"])), side="left"))
        stop = int(index.searchsorted(pd.Timestamp(str(unit["period_end"])), side="right"))
        ranges[str(unit["work_unit_id"])] = range(start, stop)
    return ranges


def compute_v6_asset_batch(
    *,
    asset: Mapping[str, object],
    units: Sequence[Mapping[str, object]],
    contract: Mapping[str, object],
    input_precheck_artifact: Path = DEFAULT_INPUT_PRECHECK_ARTIFACT,
    equity_etf_store: Path = DEFAULT_EQUITY_ETF_STORE,
    crypto_store: Path = DEFAULT_CRYPTO_STORE,
    fx_store: Path = DEFAULT_FX_STORE,
) -> dict[str, object]:
    """Compute all claimed quarters for one asset without evidence writes."""

    history = load_v6_asset_history(
        asset,
        input_precheck_artifact=Path(input_precheck_artifact),
        equity_etf_store=Path(equity_etf_store),
        crypto_store=Path(crypto_store),
        fx_store=Path(fx_store),
    )
    if history.combined_input_fingerprint != dict(contract["reference_fingerprints"])[
        "combined_input_fingerprint"
    ]:
        raise DevelopmentV6ExecutionError("Input fingerprint differs from v6 contract.")
    if history.frame.empty:
        return {
            "compute_version": COMPUTE_VERSION,
            "asset_key": asset["asset_key"],
            "skip_reason_code": "EXPECTED_NO_DEVELOPMENT_DATA",
            "skip_reason": "No active bars in the frozen Development input projection.",
            "unit_results": [],
            "unit_ids": [str(unit["work_unit_id"]) for unit in units],
        }
    execution = dict(contract["development_execution"])
    development_start = str(execution["development_start"])
    development_end = str(execution["development_end"])
    if history.frame.index.min() < pd.Timestamp(development_start):
        raise DevelopmentV6ExecutionError("Pre-Development bar in v6 history.")
    if history.frame.index.max() > pd.Timestamp(development_end):
        raise DevelopmentV6ExecutionError("Unseen post-Development bar in v6 history.")
    if not history.eligible_signal_positions():
        return {
            "compute_version": COMPUTE_VERSION,
            "asset_key": asset["asset_key"],
            "input_projection_fingerprint": history.dataset_fingerprint,
            "combined_input_fingerprint": history.combined_input_fingerprint,
            "gap_boundary_count": len(history.gap_boundaries),
            "coverage": dict(history.coverage),
            "skip_reason_code": "NO_GAP_SAFE_220_OBSERVATION_HISTORY",
            "skip_reason": (
                "No continuity segment in the frozen input contains 220 "
                "observations plus a same-segment reference-entry bar."
            ),
            "unit_results": [],
            "unit_ids": [str(unit["work_unit_id"]) for unit in units],
        }
    unit_results = {
        str(unit["work_unit_id"]): {
            "unit": dict(unit),
            "features": [],
            "outcomes": [],
            "summary": _empty_unit_summary(),
        }
        for unit in units
    }
    by_period = [dict(unit) for unit in units]
    source_fingerprint = fingerprint(
        {
            "combined_input_fingerprint": history.combined_input_fingerprint,
            "projection_fingerprint": history.dataset_fingerprint,
            "asset_key": asset["asset_key"],
        }
    )
    outcome_observations = int(
        dict(contract["outcome_contract"])["horizon_daily_observations"]
    )
    dependency_policy = (
        None
        if str(asset["asset_class"]) == "FX"
        else build_historical_dependency_policy()
    )
    gap_counts_by_unit = {
        str(unit["work_unit_id"]): sum(
            str(boundary.get("after_date") or "") >= str(unit["period_start"])
            and str(boundary.get("after_date") or "") <= str(unit["period_end"])
            for boundary in history.gap_boundaries
        )
        for unit in by_period
    }
    for segment_id, raw_segment in history.frame.groupby("SEGMENT_ID", sort=True):
        segment = raw_segment.copy()
        segment.attrs["input_segment_id"] = str(int(segment_id))
        segment.attrs["segment_end_reason"] = history.segment_end_reasons.get(
            int(segment_id), "END_OF_AVAILABLE_DEVELOPMENT_DATA"
        )
        prepared = prepare_indicators(segment)
        # The frozen scientific indicator pass intentionally returns only its
        # feature columns.  Reattach technical continuity metadata afterwards;
        # these columns do not participate in indicator calculations.
        for metadata_column in (
            "SEGMENT_ID",
            "SEGMENT_POSITION",
            "GAP_BOUNDARY_BEFORE",
            "SEGMENT_END_REASON",
        ):
            prepared[metadata_column] = segment[metadata_column].to_numpy()
        prepared.attrs.update(segment.attrs)
        if not bool(prepared["OHLC_ENVELOPE_VALID"].all()):
            raise DevelopmentV6ExecutionError(
                f"Active invalid OHLC reached compute layer: {asset['asset_key']}"
            )
        safe_history, sell_history = precompute_structure_history(prepared)
        feature_context = prepare_feature_snapshot_context(
            frame=prepared,
            prepared_frame=prepared,
        )
        outcome_context = prepare_outcome_segment_v6(
            frame=prepared,
            prepared_frame=prepared,
            safe_zone_history=safe_history,
            segment_end_reason=str(segment.attrs["segment_end_reason"]),
        )
        positions_by_unit = _position_ranges_by_unit(prepared.index, by_period)
        segment_positions = prepared["SEGMENT_POSITION"].to_numpy(dtype=int, copy=False)
        prepared_segment_ids = prepared["SEGMENT_ID"].to_numpy(dtype=int, copy=False)
        last_local = len(prepared) - 1
        for unit in by_period:
            result = unit_results[str(unit["work_unit_id"])]
            positions = positions_by_unit[str(unit["work_unit_id"])]
            for local_position in positions:
                segment_position = int(segment_positions[local_position])
                if segment_position < MINIMUM_SEGMENT_HISTORY - 1:
                    result["summary"]["minimum_history_exclusions"] += 1
                    result["summary"]["missingness_exclusions"] += 1
                    continue
                if local_position == last_local:
                    result["summary"]["missing_reference_entry"] += 1
                    result["summary"]["missingness_exclusions"] += 1
                    continue
                if int(prepared_segment_ids[local_position + 1]) != int(segment_id):
                    raise DevelopmentV6ExecutionError(
                        "Prepared segment unexpectedly contains a cross-segment next bar."
                    )
                feature = _feature_with_input_provenance(
                    asset=asset,
                    history=history,
                    prepared=prepared,
                    local_position=local_position,
                    safe_history=safe_history,
                    sell_history=sell_history,
                    contract=contract,
                    segment_id=int(segment_id),
                    source_fingerprint=source_fingerprint,
                    feature_context=feature_context,
                    dependency_policy=dependency_policy,
                )
                outcome = build_outcome_v6(
                    feature_snapshot=feature,
                    frame=prepared,
                    requested_observations=outcome_observations,
                    segment_context=outcome_context,
                    signal_position_hint=local_position,
                )
                if int(
                    dict(outcome.get("source_integrity") or {}).get(
                        "ohlc_envelope_anomaly_count_in_outcome"
                    )
                    or 0
                ):
                    raise DevelopmentV6ExecutionError(
                        "Invalid OHLC reached a v6 outcome despite input precheck."
                    )
                result["features"].append(feature)
                result["outcomes"].append(outcome)
                if outcome.get("r_metrics_status") != "AVAILABLE":
                    result["summary"]["r_na_cases"] += 1
                if str(outcome.get("status", "")).startswith("CENSORED_"):
                    result["summary"]["censored_cases"] += 1
                if outcome.get("status") == "CENSORED_AT_INPUT_GAP":
                    result["summary"]["input_gap_censored_cases"] += 1
                if outcome.get("status") == "CENSORED_AT_END_OF_AVAILABLE_DATA":
                    result["summary"]["end_of_data_censored_cases"] += 1
                if outcome.get("status") == "CENSORED_AT_STAGE_BOUNDARY":
                    result["summary"]["stage_censored_cases"] += 1
            if positions:
                result["summary"]["gap_boundary_count"] = gap_counts_by_unit[
                    str(unit["work_unit_id"])
                ]
    ordered = [unit_results[str(unit["work_unit_id"])] for unit in units]
    for result in ordered:
        features = result["features"]
        outcomes = result["outcomes"]
        if len(features) != len(outcomes):
            raise DevelopmentV6ExecutionError("Feature/outcome count differs in compute result.")
        result["case_digest"] = fingerprint(
            [
                (
                    item["case_id"],
                    item["feature_fingerprint"],
                    outcomes[index]["outcome_fingerprint"],
                )
                for index, item in enumerate(features)
            ]
        )
    return {
        "compute_version": COMPUTE_VERSION,
        "asset_key": asset["asset_key"],
        "input_projection_fingerprint": history.dataset_fingerprint,
        "combined_input_fingerprint": history.combined_input_fingerprint,
        "gap_boundary_count": len(history.gap_boundaries),
        "coverage": dict(history.coverage),
        "unit_results": ordered,
        "skip_reason_code": None,
        "skip_reason": None,
    }


def result_scientific_digest(result: Mapping[str, object]) -> str:
    """Digest stable scientific/classification payloads, never worker timing.

    Asset-level terminal skips have no unit payloads, so hashing only
    ``unit_results`` would collapse every distinct skip to ``fingerprint([])``.
    Bind the exact unit set, skip classification and immutable input/gap
    evidence as well; process ids, timings and run ids remain excluded.
    """

    unit_results = []
    for unit in result.get("unit_results") or []:
        unit_results.append(
            {
                "work_unit_id": dict(unit["unit"])["work_unit_id"],
                "features": unit["features"],
                "outcomes": unit["outcomes"],
                "summary": unit["summary"],
            }
        )
    returned_unit_ids = result.get("unit_ids")
    unit_ids = (
        sorted(str(item) for item in returned_unit_ids)
        if isinstance(returned_unit_ids, list)
        else sorted(str(item["work_unit_id"]) for item in unit_results)
    )
    basis = {
        "asset_key": result.get("asset_key"),
        "input_projection_fingerprint": result.get(
            "input_projection_fingerprint"
        ),
        "combined_input_fingerprint": result.get("combined_input_fingerprint"),
        "gap_boundary_count": result.get("gap_boundary_count"),
        "coverage": dict(result.get("coverage") or {}),
        "skip_reason_code": result.get("skip_reason_code"),
        "skip_reason": result.get("skip_reason"),
        "unit_ids": unit_ids,
        "unit_results": unit_results,
    }
    return fingerprint(basis)


def is_retryable_compute_error(error: BaseException) -> bool:
    """Offline deterministic inputs make almost every compute error terminal."""

    import sqlite3

    return isinstance(error, sqlite3.OperationalError) and any(
        token in str(error).lower() for token in ("locked", "busy", "timeout")
    )


__all__ = [
    "COMPUTE_VERSION",
    "DevelopmentV6ExecutionError",
    "UNIVERSE_VERSION",
    "WORK_PLAN_VERSION",
    "build_v6_universe",
    "build_v6_work_plan",
    "compute_v6_asset_batch",
    "is_retryable_compute_error",
    "result_scientific_digest",
]
