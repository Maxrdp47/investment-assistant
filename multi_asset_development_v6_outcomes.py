from __future__ import annotations

"""Gap-safe outcome measurements for Multi-Asset Development v6.

The caller supplies one already segmented OHLCV history.  This module never
joins segments and rejects frames that contain more than one explicit segment
identifier.  Structural-R availability is deliberately independent from the
raw price path: missing or non-positive structural risk leaves every R-scaled
field ``None`` while percentage and, when possible, ATR-scaled measurements
remain available.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from multi_asset_discovery_v1 import (
    MultiAssetDiscoveryContractError,
    build_safe_zones,
    fingerprint,
    prepare_indicators,
)
from swing_broad_research import broad_research_split


V6_OUTCOME_VERSION = "multi-asset-development-outcomes-2026.09.05-v6"
V6_OUTCOME_POLICY_VERSION = "multi-asset-development-outcome-policy-2026.09.05-v6"
DEFAULT_OUTCOME_OBSERVATIONS = 252
END_OF_AVAILABLE_DATA_REASON = "END_OF_AVAILABLE_DEVELOPMENT_DATA"

_SEGMENT_COLUMNS = (
    "INPUT_SEGMENT_ID",
    "input_segment_id",
    "SEGMENT_ID",
    "segment_id",
)


@dataclass(frozen=True)
class PreparedOutcomeSegmentV6:
    """One validated, read-only-by-contract segment shared by all its cases.

    Pandas frames cannot be made deeply immutable without copying their full
    backing arrays.  This frozen context therefore owns the exact frame objects
    passed at construction and callers must not mutate them afterwards.  The
    production worker creates the context only after its indicator/structure
    pass is complete and never exposes either frame to another writer.
    """

    frame: pd.DataFrame
    prepared: pd.DataFrame
    safe_zone_history: Sequence[Mapping[str, object]] | None
    segment_id: str | None
    segment_end_reason: str | None
    segment_start_day: str
    segment_end_day: str
    position_by_timestamp: Mapping[pd.Timestamp, int]


def _frame_segment_identity(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    values: set[str] = set()
    for column in _SEGMENT_COLUMNS:
        if column not in frame.columns:
            continue
        values.update(
            str(value)
            for value in frame[column].dropna().unique().tolist()
            if str(value)
        )
    if len(values) > 1:
        raise MultiAssetDiscoveryContractError(
            "Das Outcome-Frame enthält mehrere Input-Segmente."
        )
    explicit_id = next(iter(values), None)
    attr_id = frame.attrs.get("input_segment_id") or frame.attrs.get("segment_id")
    claimed_ids = {
        str(value) for value in (explicit_id, attr_id) if value is not None and str(value)
    }
    if len(claimed_ids) > 1:
        raise MultiAssetDiscoveryContractError(
            "Outcome-Spalte und Frame-Attribut referenzieren verschiedene Segmente."
        )
    boundary_reason = frame.attrs.get("segment_end_reason") or frame.attrs.get(
        "input_boundary_reason"
    )
    return next(iter(claimed_ids), None), (
        str(boundary_reason) if boundary_reason else None
    )


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _stage_end(signal_day: str) -> pd.Timestamp | None:
    day = pd.Timestamp(signal_day)
    split = broad_research_split(day)
    if split == "outside_contract":
        return None
    if day.year <= 2015:
        return {
            "development": pd.Timestamp("2012-12-31"),
            "validation": pd.Timestamp("2014-12-31"),
            "holdout": pd.Timestamp("2015-12-31"),
        }[split]
    return {
        "development": pd.Timestamp("2021-12-31"),
        "validation": pd.Timestamp("2023-12-31"),
        "holdout": pd.Timestamp.max.normalize(),
    }[split]


def _validate_ordered_segment(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise MultiAssetDiscoveryContractError("Das Outcome-Segment ist leer.")
    index = pd.DatetimeIndex(pd.to_datetime(frame.index)).tz_localize(None).normalize()
    if index.has_duplicates:
        raise MultiAssetDiscoveryContractError(
            "Das Outcome-Segment enthält doppelte Sitzungstage."
        )
    if not index.is_monotonic_increasing:
        raise MultiAssetDiscoveryContractError(
            "Das Outcome-Segment muss chronologisch sortiert sein."
        )
    required = {"Open", "High", "Low", "Close"}
    normalized_columns = {str(column).title() for column in frame.columns}
    missing = sorted(required - normalized_columns)
    if missing:
        raise MultiAssetDiscoveryContractError(
            f"Dem Outcome-Segment fehlen OHLC-Spalten: {missing}"
        )


def _segment_identity(
    frame: pd.DataFrame,
    feature_snapshot: Mapping[str, object],
) -> tuple[str | None, str | None]:
    """Return the verified segment id and declared boundary reason."""

    frame_id, boundary_reason = _frame_segment_identity(frame)
    snapshot_id = feature_snapshot.get("input_segment_id") or feature_snapshot.get(
        "segment_id"
    )
    claimed_ids = {
        str(value)
        for value in (frame_id, snapshot_id)
        if value is not None and str(value)
    }
    if len(claimed_ids) > 1:
        raise MultiAssetDiscoveryContractError(
            "Feature-Snapshot und Outcome-Frame referenzieren verschiedene Segmente."
        )
    return next(iter(claimed_ids), None), boundary_reason


def prepare_outcome_segment_v6(
    *,
    frame: pd.DataFrame,
    prepared_frame: pd.DataFrame | None = None,
    safe_zone_history: Sequence[Mapping[str, object]] | None = None,
    segment_end_reason: str | None = None,
) -> PreparedOutcomeSegmentV6:
    """Validate a segment once and pre-index its signal timestamps.

    Supplying ``prepared_frame`` avoids another indicator pass and deliberately
    retains that exact object.  The caller must finish all mutations before
    constructing this frozen context.
    """

    _validate_ordered_segment(frame)
    prepared = prepared_frame if prepared_frame is not None else prepare_indicators(frame)
    _validate_ordered_segment(prepared)
    if len(prepared) != len(frame):
        raise MultiAssetDiscoveryContractError(
            "Prepared Frame und Input-Segment haben unterschiedliche Längen."
        )
    raw_index = pd.DatetimeIndex(pd.to_datetime(frame.index)).tz_localize(None).normalize()
    prepared_index = (
        pd.DatetimeIndex(pd.to_datetime(prepared.index)).tz_localize(None).normalize()
    )
    if not raw_index.equals(prepared_index):
        raise MultiAssetDiscoveryContractError(
            "Prepared Frame und Input-Segment besitzen nicht dieselben Sitzungstage."
        )
    if safe_zone_history is not None and len(safe_zone_history) != len(prepared):
        raise MultiAssetDiscoveryContractError(
            "Safe-Zone-Historie und Input-Segment haben unterschiedliche Längen."
        )
    segment_id, frame_boundary_reason = _frame_segment_identity(frame)
    position_by_timestamp = {
        pd.Timestamp(stamp): position for position, stamp in enumerate(prepared.index)
    }
    if len(position_by_timestamp) != len(prepared):  # defensive; validator is authoritative
        raise MultiAssetDiscoveryContractError(
            "Das Outcome-Segment enthält doppelte Sitzungstage."
        )
    return PreparedOutcomeSegmentV6(
        frame=frame,
        prepared=prepared,
        safe_zone_history=(
            tuple(safe_zone_history) if safe_zone_history is not None else None
        ),
        segment_id=segment_id,
        segment_end_reason=segment_end_reason or frame_boundary_reason,
        segment_start_day=prepared.index[0].date().isoformat(),
        segment_end_day=prepared.index[-1].date().isoformat(),
        position_by_timestamp=MappingProxyType(position_by_timestamp),
    )


def _first_hit(values: pd.Series, threshold: float, *, mode: str) -> int | None:
    if mode not in {"above", "below"}:
        raise ValueError(mode)
    mask = values >= threshold if mode == "above" else values < threshold
    positions = np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool))
    return int(positions[0] + 1) if len(positions) else None


def _metric_division(numerator: float, denominator: float | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _checkpoint(
    future: pd.DataFrame,
    observations: int,
    *,
    entry: float,
    atr: float | None,
    structural_risk: float | None,
) -> dict[str, object] | None:
    if len(future) < observations:
        return None
    part = future.iloc[:observations]
    high = float(part["High"].max())
    low = float(part["Low"].min())
    close = float(part.iloc[-1]["Close"])
    return {
        "observations": observations,
        "end_day": part.index[-1].date().isoformat(),
        "calendar_span_days_inclusive": int(
            (part.index[-1].normalize() - part.index[0].normalize()).days
        )
        + 1,
        "return_pct": (close / entry - 1) * 100,
        "mfe_pct": (high / entry - 1) * 100,
        "mae_pct": (low / entry - 1) * 100,
        "mfe_atr": _metric_division(high - entry, atr),
        "mae_atr": _metric_division(low - entry, atr),
        "mfe_r": _metric_division(high - entry, structural_risk),
        "mae_r": _metric_division(low - entry, structural_risk),
    }


def _protective_ratchet(
    prepared: pd.DataFrame,
    signal_position: int,
    future_end_position: int,
    *,
    safe_zone_history: Sequence[Mapping[str, object]] | None,
) -> dict[str, object]:
    if safe_zone_history is not None and len(safe_zone_history) != len(prepared):
        raise MultiAssetDiscoveryContractError(
            "Safe-Zone-Historie und Input-Segment haben unterschiedliche Längen."
        )
    initial_source = (
        safe_zone_history[signal_position]
        if safe_zone_history is not None
        else build_safe_zones(prepared, signal_position)
    )
    initial = dict((initial_source or {}).get("C") or {})
    initial_lower = _number(initial.get("lower"))
    if initial.get("status") != "AVAILABLE" or initial_lower is None:
        return {
            "status": "UNAVAILABLE",
            "reason": initial.get("reason") or "SAFE_ZONE_C_UNAVAILABLE",
            "updates": [],
            "never_lowered": True,
        }
    current = initial_lower
    updates: list[dict[str, object]] = []
    for position in range(signal_position + 1, future_end_position + 1):
        candidate_source = (
            safe_zone_history[position]
            if safe_zone_history is not None
            else build_safe_zones(prepared, position)
        )
        candidate = dict((candidate_source or {}).get("C") or {})
        proposed = _number(candidate.get("lower"))
        if candidate.get("status") != "AVAILABLE" or proposed is None:
            continue
        if proposed > current:
            updates.append(
                {
                    "effective_day": prepared.index[position].date().isoformat(),
                    "prior_lower": current,
                    "new_lower": proposed,
                    "confirmed_structure_required": True,
                }
            )
            current = proposed
    return {
        "status": "AVAILABLE",
        "initial_lower": initial_lower,
        "final_lower": current,
        "updates": updates,
        "never_lowered": all(
            item["new_lower"] > item["prior_lower"] for item in updates
        ),
    }


def _base_identity(
    feature_snapshot: Mapping[str, object],
    *,
    signal_day: str,
) -> dict[str, object]:
    return {
        "outcome_version": V6_OUTCOME_VERSION,
        "outcome_policy_version": V6_OUTCOME_POLICY_VERSION,
        "contract_version": feature_snapshot.get("contract_version"),
        "case_id": feature_snapshot["case_id"],
        "feature_fingerprint": feature_snapshot["feature_fingerprint"],
        "asset_id": feature_snapshot["asset_id"],
        "symbol": feature_snapshot["symbol"],
        "asset_class": feature_snapshot["asset_class"],
        "listing_id": feature_snapshot.get("listing_id"),
        "issuer_id": feature_snapshot.get("issuer_id"),
        "mapping_status": feature_snapshot.get("mapping_status"),
        "dependency_status": feature_snapshot.get("dependency_status"),
        "research_split": feature_snapshot["research_split"],
        "signal_day": signal_day,
    }


def _censored_without_entry(
    feature_snapshot: Mapping[str, object],
    *,
    signal_day: str,
    segment_id: str | None,
    segment_start_day: str,
    segment_end_day: str,
    segment_end_reason: str | None,
    requested_observations: int,
    input_boundary: bool,
    end_of_available_data: bool,
) -> dict[str, object]:
    if input_boundary:
        status = "CENSORED_AT_INPUT_GAP"
        reason = "NEXT_OPEN_AFTER_INPUT_GAP"
    elif end_of_available_data:
        status = "CENSORED_AT_END_OF_AVAILABLE_DATA"
        reason = "NEXT_OPEN_NOT_AVAILABLE_IN_FROZEN_DEVELOPMENT_INPUT"
    else:
        status = "CENSORED_AT_STAGE_BOUNDARY"
        reason = "NEXT_OPEN_OUTSIDE_STAGE"
    outcome = {
        **_base_identity(feature_snapshot, signal_day=signal_day),
        "status": status,
        "reason": reason,
        "censoring_reason": reason,
        "measurement_status": "NO_REFERENCE_ENTRY",
        "measurement_reason": reason,
        "r_metrics_status": "UNAVAILABLE",
        "r_metrics_reason": "NO_REFERENCE_ENTRY",
        "atr_metrics_status": "UNAVAILABLE",
        "atr_metrics_reason": "NO_REFERENCE_ENTRY",
        "observations_available": 0,
        "requested_observations": requested_observations,
        "observation_axis": {
            "observed_bar_count": 0,
            "calendar_span_days_inclusive": None,
            "declared_data_gap_boundary_encountered": input_boundary,
            "data_gaps_crossed": 0,
            "counting_basis": "AVAILABLE_SOURCE_BARS_WITHIN_ONE_INPUT_SEGMENT",
        },
        "input_segment": {
            "segment_id": segment_id,
            "start_day": segment_start_day,
            "end_day": segment_end_day,
            "declared_end_reason": segment_end_reason,
            "single_segment_verified": True,
        },
        "entry_day": None,
        "entry_open": None,
        "entry_gap_pct": None,
        "entry_gap_atr": None,
        "original_structural_invalidation": None,
        "structural_risk": None,
        "mfe_pct": None,
        "mae_pct": None,
        "mfe_atr": None,
        "mae_atr": None,
        "mfe_r": None,
        "mae_r": None,
        "final_return_pct": None,
        "r_level_hits": {str(level): None for level in (1.0, 2.0, 3.0)},
        "checkpoints": {
            str(observation): None for observation in (20, 60, 120, 252)
        },
        "future_features_written_to_feature_store": False,
        "no_intrabar_order_invented": True,
        "cross_segment_observations_used": 0,
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    return outcome


def build_outcome_v6(
    *,
    feature_snapshot: Mapping[str, object],
    frame: pd.DataFrame,
    prepared_frame: pd.DataFrame | None = None,
    safe_zone_history: Sequence[Mapping[str, object]] | None = None,
    segment_end_reason: str | None = None,
    requested_observations: int = DEFAULT_OUTCOME_OBSERVATIONS,
    segment_context: PreparedOutcomeSegmentV6 | None = None,
    signal_position_hint: int | None = None,
) -> dict[str, object]:
    """Measure one feature snapshot inside exactly one pre-segmented history.

    ``segment_end_reason`` must be supplied (or set in ``frame.attrs``) when
    the segment ends because of an excluded source session or a detected
    input gap.  Absence of that declaration means ordinary stage/end-of-input
    censoring.  A caller must never concatenate segments before this call.
    """

    if not feature_snapshot.get("feature_fingerprint"):
        raise MultiAssetDiscoveryContractError(
            "Outcome v6 benötigt einen eingefrorenen Feature-Snapshot."
        )
    if requested_observations <= 0:
        raise MultiAssetDiscoveryContractError(
            "Der Outcome-Horizont muss positiv sein."
        )
    signal_day = str(feature_snapshot["signal_day"])
    signal_timestamp = pd.Timestamp(signal_day)
    if segment_context is None:
        # Compatibility/reference path: preserve defensive copying for callers
        # that have not opted into the once-validated production context.
        _validate_ordered_segment(frame)
        segment_id, frame_boundary_reason = _segment_identity(frame, feature_snapshot)
        declared_boundary_reason = segment_end_reason or frame_boundary_reason
        prepared = (
            prepared_frame.copy()
            if prepared_frame is not None
            else prepare_indicators(frame)
        )
        _validate_ordered_segment(prepared)
        if len(prepared) != len(frame):
            raise MultiAssetDiscoveryContractError(
                "Prepared Frame und Input-Segment haben unterschiedliche Längen."
            )
        raw_index = (
            pd.DatetimeIndex(pd.to_datetime(frame.index)).tz_localize(None).normalize()
        )
        prepared_index = (
            pd.DatetimeIndex(pd.to_datetime(prepared.index))
            .tz_localize(None)
            .normalize()
        )
        if not raw_index.equals(prepared_index):
            raise MultiAssetDiscoveryContractError(
                "Prepared Frame und Input-Segment besitzen nicht dieselben Sitzungstage."
            )
        matching = np.flatnonzero(prepared.index == signal_timestamp)
        if len(matching) != 1:
            raise MultiAssetDiscoveryContractError(
                "Signaltag ist im Input-Segment nicht eindeutig."
            )
        signal_position = int(matching[0])
        segment_start_day = prepared.index[0].date().isoformat()
        segment_end_day = prepared.index[-1].date().isoformat()
    else:
        if frame is not segment_context.frame and frame is not segment_context.prepared:
            raise MultiAssetDiscoveryContractError(
                "Fastpath-Frame gehört nicht zum vorbereiteten Outcome-Segment."
            )
        if prepared_frame is not None and prepared_frame is not segment_context.prepared:
            raise MultiAssetDiscoveryContractError(
                "Fastpath-Prepared-Frame gehört nicht zum Outcome-Kontext."
            )
        if (
            safe_zone_history is not None
            and safe_zone_history is not segment_context.safe_zone_history
        ):
            raise MultiAssetDiscoveryContractError(
                "Fastpath-Safe-Zone-Historie gehört nicht zum Outcome-Kontext."
            )
        prepared = segment_context.prepared
        safe_zone_history = segment_context.safe_zone_history
        snapshot_id = feature_snapshot.get("input_segment_id") or feature_snapshot.get(
            "segment_id"
        )
        claimed_ids = {
            str(value)
            for value in (segment_context.segment_id, snapshot_id)
            if value is not None and str(value)
        }
        if len(claimed_ids) > 1:
            raise MultiAssetDiscoveryContractError(
                "Feature-Snapshot und Outcome-Frame referenzieren verschiedene Segmente."
            )
        segment_id = next(iter(claimed_ids), None)
        declared_boundary_reason = (
            segment_end_reason or segment_context.segment_end_reason
        )
        if signal_position_hint is None:
            resolved = segment_context.position_by_timestamp.get(signal_timestamp)
            if resolved is None:
                raise MultiAssetDiscoveryContractError(
                    "Signaltag ist im Input-Segment nicht eindeutig."
                )
            signal_position = int(resolved)
        else:
            signal_position = int(signal_position_hint)
            if (
                signal_position < 0
                or signal_position >= len(prepared)
                or pd.Timestamp(prepared.index[signal_position]) != signal_timestamp
            ):
                raise MultiAssetDiscoveryContractError(
                    "Signalpositions-Hinweis passt nicht zum eingefrorenen Signaltag."
                )
        segment_start_day = segment_context.segment_start_day
        segment_end_day = segment_context.segment_end_day
    stage_end = _stage_end(signal_day)
    if stage_end is None:
        raise MultiAssetDiscoveryContractError(
            "Signaltag liegt außerhalb des eingefrorenen Stage-Vertrags."
        )
    expected_split = broad_research_split(signal_day)
    if str(feature_snapshot.get("research_split")) != expected_split:
        raise MultiAssetDiscoveryContractError(
            "Research-Split des Features passt nicht zum Signaltag."
        )

    stage_stop = int(prepared.index.searchsorted(stage_end, side="right"))
    entry_position = signal_position + 1
    horizon_stop = min(
        len(prepared),
        stage_stop,
        entry_position + requested_observations,
    )
    observations_available = max(0, horizon_stop - entry_position)
    end_of_available_data = declared_boundary_reason == END_OF_AVAILABLE_DATA_REASON
    input_boundary = bool(
        declared_boundary_reason
        and not end_of_available_data
        and prepared.index[-1] < stage_end
        and signal_position == len(prepared) - 1
    )
    if observations_available == 0:
        return _censored_without_entry(
            feature_snapshot,
            signal_day=signal_day,
            segment_id=segment_id,
            segment_start_day=segment_start_day,
            segment_end_day=segment_end_day,
            segment_end_reason=declared_boundary_reason,
            requested_observations=requested_observations,
            input_boundary=input_boundary,
            end_of_available_data=end_of_available_data
            and prepared.index[-1] < stage_end
            and signal_position == len(prepared) - 1,
        )

    # The outcome frame is always one contiguous, stage-clipped slice and can
    # never exceed the frozen horizon.  No unbounded future-position list is
    # materialized for any case.
    future = prepared.iloc[entry_position:horizon_stop]
    entry = float(prepared.iloc[entry_position]["Open"])
    signal_close = float(prepared.iloc[signal_position]["Close"])
    atr_raw = _number(prepared.iloc[signal_position].get("ATR_14"))
    atr = atr_raw if atr_raw is not None and atr_raw > 0 else None
    atr_reason = None if atr is not None else (
        "MISSING_ATR" if atr_raw is None else "NON_POSITIVE_ATR"
    )
    zone_c = dict((feature_snapshot.get("safe_zones") or {}).get("C") or {})
    invalidation = _number(zone_c.get("lower"))
    if invalidation is None:
        structural_risk = None
        # Zone C can be undefined specifically because its causal ATR input is
        # missing.  Preserve that narrower diagnosis instead of collapsing
        # every unavailable zone into a generic structure failure.
        r_reason = "MISSING_ATR" if atr is None else "MISSING_INVALIDATION"
    else:
        risk_candidate = entry - invalidation
        if risk_candidate <= 0:
            structural_risk = None
            r_reason = "NON_POSITIVE_STRUCTURAL_RISK"
        else:
            structural_risk = risk_candidate
            r_reason = None

    highs = future["High"]
    lows = future["Low"]
    closes = future["Close"]
    max_high = float(highs.max())
    min_low = float(lows.min())
    max_high_offset = int(np.argmax(highs.to_numpy(dtype=float)))
    peak_close_after = float(closes.iloc[max_high_offset:].min())

    safe_breaches: dict[str, object] = {}
    for key in ("A", "B", "C"):
        zone = dict((feature_snapshot.get("safe_zones") or {}).get(key) or {})
        lower = _number(zone.get("lower"))
        safe_breaches[key] = (
            {
                "status": "AVAILABLE",
                "lower": lower,
                "intraday_breach_observation": _first_hit(
                    lows, float(lower), mode="below"
                ),
                "close_breach_observation": _first_hit(
                    closes, float(lower), mode="below"
                ),
            }
            if lower is not None
            else {
                "status": "UNAVAILABLE",
                "reason": zone.get("reason") or "MISSING_ZONE_LOWER",
            }
        )

    sell_measurements: dict[str, object] = {}
    for key in ("A", "B", "C"):
        zone = dict((feature_snapshot.get("sell_zones") or {}).get(key) or {})
        value = _number(zone.get("value"))
        sell_measurements[key] = (
            {
                "status": "AVAILABLE",
                "value": value,
                "hit_observation": _first_hit(highs, float(value), mode="above"),
                "max_overshoot_pct": max(0.0, (max_high / float(value) - 1) * 100),
            }
            if value is not None and value > 0
            else {
                "status": "UNAVAILABLE",
                "reason": zone.get("reason") or "MISSING_SELL_ZONE_VALUE",
            }
        )

    checkpoints = {
        str(observation): _checkpoint(
            future,
            observation,
            entry=entry,
            atr=atr,
            structural_risk=structural_risk,
        )
        for observation in (20, 60, 120, 252)
    }
    r_hits = {
        str(level): (
            _first_hit(highs, entry + level * structural_risk, mode="above")
            if structural_risk is not None
            else None
        )
        for level in (1.0, 2.0, 3.0)
    }

    final_position = horizon_stop - 1
    final_close = float(future.iloc[-1]["Close"])
    horizon_complete = len(future) == requested_observations
    ended_before_stage = prepared.index[-1] < stage_end
    censored_at_input = bool(
        not horizon_complete
        and declared_boundary_reason
        and not end_of_available_data
        and ended_before_stage
        and final_position == len(prepared) - 1
    )
    censored_at_end_of_data = bool(
        not horizon_complete
        and end_of_available_data
        and ended_before_stage
        and final_position == len(prepared) - 1
    )
    if horizon_complete:
        status = "COMPLETE"
        censoring_reason = None
    elif censored_at_input:
        status = "CENSORED_AT_INPUT_GAP"
        censoring_reason = "INPUT_GAP_BEFORE_REQUESTED_OBSERVATIONS"
    elif censored_at_end_of_data:
        status = "CENSORED_AT_END_OF_AVAILABLE_DATA"
        censoring_reason = "END_OF_AVAILABLE_DATA_BEFORE_REQUESTED_OBSERVATIONS"
    else:
        status = "CENSORED_AT_STAGE_BOUNDARY"
        censoring_reason = "STAGE_BOUNDARY_BEFORE_REQUESTED_OBSERVATIONS"

    signal_ema20 = _number(prepared.iloc[signal_position].get("EMA_20"))
    signal_rsi = pd.to_numeric(future.get("RSI_14"), errors="coerce")
    future_atr = pd.to_numeric(future.get("ATR_14"), errors="coerce")
    volume_ratio = pd.to_numeric(future.get("VOLUME_RATIO_20"), errors="coerce")
    path_adverse = entry - min_low
    outcome: dict[str, object] = {
        **_base_identity(feature_snapshot, signal_day=signal_day),
        "status": status,
        "reason": censoring_reason,
        "censoring_reason": censoring_reason,
        "measurement_status": "COMPLETE" if r_reason is None and atr_reason is None else "PARTIAL_NON_R",
        "measurement_reason": r_reason or atr_reason,
        "r_metrics_status": "AVAILABLE" if structural_risk is not None else "UNAVAILABLE",
        "r_metrics_reason": r_reason,
        "atr_metrics_status": "AVAILABLE" if atr is not None else "UNAVAILABLE",
        "atr_metrics_reason": atr_reason,
        "input_segment": {
            "segment_id": segment_id,
            "start_day": segment_start_day,
            "end_day": segment_end_day,
            "declared_end_reason": declared_boundary_reason,
            "single_segment_verified": True,
        },
        "entry_day": prepared.index[entry_position].date().isoformat(),
        "entry_open": entry,
        "signal_close": signal_close,
        "entry_gap_pct": (entry / signal_close - 1) * 100,
        "entry_gap_atr": _metric_division(entry - signal_close, atr),
        "original_structural_invalidation": invalidation,
        "structural_risk": structural_risk,
        "observations_available": len(future),
        "requested_observations": requested_observations,
        "outcome_end_day": future.index[-1].date().isoformat(),
        "observation_axis": {
            "observed_bar_count": len(future),
            "calendar_span_days_inclusive": int(
                (future.index[-1].normalize() - future.index[0].normalize()).days
            )
            + 1,
            "declared_data_gap_boundary_encountered": censored_at_input,
            "data_gaps_crossed": 0,
            "counting_basis": "AVAILABLE_SOURCE_BARS_WITHIN_ONE_INPUT_SEGMENT",
        },
        "source_integrity": {
            "ohlc_envelope_anomaly_count_in_outcome": int(
                (~future["OHLC_ENVELOPE_VALID"]).sum()
            ),
            "provider_values_repaired": False,
            "cross_segment_observations_used": 0,
        },
        "mfe_pct": (max_high / entry - 1) * 100,
        "mae_pct": (min_low / entry - 1) * 100,
        "mfe_atr": _metric_division(max_high - entry, atr),
        "mae_atr": _metric_division(min_low - entry, atr),
        "mfe_r": _metric_division(max_high - entry, structural_risk),
        "mae_r": _metric_division(min_low - entry, structural_risk),
        "final_return_pct": (final_close / entry - 1) * 100,
        "time_to_mfe_observations": max_high_offset + 1,
        "time_to_structural_intraday_invalidation": (
            _first_hit(lows, invalidation, mode="below")
            if invalidation is not None
            else None
        ),
        "time_to_structural_close_invalidation": (
            _first_hit(closes, invalidation, mode="below")
            if invalidation is not None
            else None
        ),
        "r_level_hits": r_hits,
        "safe_zone_breaches": safe_breaches,
        "sell_zone_measurements": sell_measurements,
        "checkpoints": checkpoints,
        "protective_ratchet": _protective_ratchet(
            prepared,
            signal_position,
            final_position,
            safe_zone_history=safe_zone_history,
        ),
        "path_quality": {
            "mfe_to_mae_ratio": (
                (max_high - entry) / max(path_adverse, 1e-12)
            ),
            "positive_close_fraction": float((closes >= entry).mean()),
            "peak_giveback_pct": (max_high / peak_close_after - 1) * 100,
            "final_giveback_pct": (max_high / final_close - 1) * 100,
            "peak_giveback_r": _metric_division(
                max_high - peak_close_after, structural_risk
            ),
            "final_giveback_r": _metric_division(
                max_high - final_close, structural_risk
            ),
        },
        "deterioration": {
            "PRICE_STRUCTURE": (
                {
                    "status": "AVAILABLE",
                    "close_below_signal_ema20_count": int(
                        (closes < signal_ema20).sum()
                    ),
                }
                if signal_ema20 is not None
                else {"status": "UNAVAILABLE", "reason": "MISSING_SIGNAL_EMA20"}
            ),
            "MOMENTUM": {
                "status": "AVAILABLE" if signal_rsi is not None else "UNAVAILABLE",
                "rsi14_below_40_count": (
                    int((signal_rsi < 40).fillna(False).sum())
                    if signal_rsi is not None
                    else None
                ),
            },
            "VOLATILITY": (
                {
                    "status": "AVAILABLE",
                    "atr14_above_1_5x_signal_count": int(
                        (future_atr > 1.5 * atr).fillna(False).sum()
                    ),
                }
                if atr is not None and future_atr is not None
                else {"status": "UNAVAILABLE", "reason": atr_reason or "MISSING_ATR"}
            ),
            "LIQUIDITY": (
                {"status": "STRUCTURAL_NOT_APPLICABLE"}
                if feature_snapshot["asset_class"] == "FX"
                else {
                    "status": "AVAILABLE" if volume_ratio is not None else "UNAVAILABLE",
                    "volume_ratio_below_0_5_count": (
                        int((volume_ratio < 0.5).fillna(False).sum())
                        if volume_ratio is not None
                        else None
                    ),
                }
            ),
            "EVENT": {
                "status": "UNKNOWN",
                "reason": "NO_PIT_EVENT_PATH_IN_TECHNICAL_DEVELOPMENT",
            },
        },
        "future_features_written_to_feature_store": False,
        "no_intrabar_order_invented": True,
        "cross_segment_observations_used": 0,
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    return outcome


# Readable alias for callers that group v6-specific helpers by prefix.
build_v6_outcome = build_outcome_v6


__all__ = [
    "END_OF_AVAILABLE_DATA_REASON",
    "DEFAULT_OUTCOME_OBSERVATIONS",
    "PreparedOutcomeSegmentV6",
    "V6_OUTCOME_POLICY_VERSION",
    "V6_OUTCOME_VERSION",
    "build_outcome_v6",
    "build_v6_outcome",
    "prepare_outcome_segment_v6",
]
