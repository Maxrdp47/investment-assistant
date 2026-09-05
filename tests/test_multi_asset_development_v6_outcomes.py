from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

import multi_asset_development_v6_outcomes as outcomes_module
from multi_asset_development_v6_outcomes import (
    V6_OUTCOME_VERSION,
    build_outcome_v6,
    build_v6_outcome,
    prepare_outcome_segment_v6,
)
from multi_asset_discovery_v1 import (
    MultiAssetDiscoveryContractError,
    prepare_indicators,
)


def _history(periods: int = 540) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-02", periods=periods)
    x = np.arange(periods, dtype=float)
    close = 100.0 + 0.025 * x + 2.0 * np.sin(x / 9.0)
    open_ = close * (1.0 + 0.001 * np.sin(x / 7.0))
    high = np.maximum(open_, close) + 1.25
    low = np.minimum(open_, close) - 1.10
    frame = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": 1_000_000.0 + x * 100.0,
        },
        index=index,
    )
    frame.attrs["input_segment_id"] = "segment-001"
    return frame


def _zones(invalidation: float | None) -> tuple[dict[str, object], dict[str, object]]:
    unavailable = {"status": "UNAVAILABLE", "reason": "NOT_AVAILABLE_IN_FIXTURE"}
    c_zone = (
        {"status": "AVAILABLE", "lower": invalidation, "upper": invalidation + 1.0}
        if invalidation is not None
        else {"status": "UNAVAILABLE", "reason": "STRUCTURE_UNAVAILABLE"}
    )
    safe = {
        "safe_zone_version": "fixture-v1",
        "A": unavailable,
        "B": unavailable,
        "C": c_zone,
        "confirmed_swing_low_count": 0,
        "original_zone_immutable": True,
    }
    sell = {
        "sell_zone_version": "fixture-v1",
        "A": unavailable,
        "B": unavailable,
        "C": {"status": "AVAILABLE", "value": 120.0},
        "measurement_only": True,
        "automatic_exit_allowed": False,
    }
    return safe, sell


def _feature(
    frame: pd.DataFrame,
    position: int,
    *,
    invalidation: float | None,
) -> dict[str, object]:
    safe, sell = _zones(invalidation)
    return {
        "contract_version": "multi-asset-opportunity-discovery-development-test-v6",
        "case_id": f"case-{position}",
        "feature_fingerprint": f"feature-{position}",
        "asset_id": "asset-test",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "listing_id": "listing-test",
        "issuer_id": "issuer-test",
        "mapping_status": "VERIFIED",
        "dependency_status": "KNOWN",
        "research_split": "development",
        "signal_day": frame.index[position].date().isoformat(),
        "input_segment_id": "segment-001",
        "safe_zones": safe,
        "sell_zones": sell,
    }


def _safe_history(length: int, safe_zones: dict[str, object]) -> list[dict[str, object]]:
    return [copy.deepcopy(safe_zones) for _ in range(length)]


def test_v6_outcome_is_deterministic_and_preserves_complete_metrics() -> None:
    frame = _history()
    prepared = prepare_indicators(frame)
    position = 220
    invalidation = float(prepared.iloc[position + 1]["Open"]) - 5.0
    feature = _feature(frame, position, invalidation=invalidation)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    first = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
    )
    second = build_v6_outcome(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
    )

    assert first == second
    assert first["outcome_version"] == V6_OUTCOME_VERSION
    assert first["status"] == "COMPLETE"
    assert first["observations_available"] == 252
    assert first["observation_axis"]["observed_bar_count"] == 252
    assert first["observation_axis"]["calendar_span_days_inclusive"] >= 252
    assert first["observation_axis"]["data_gaps_crossed"] == 0
    assert first["checkpoints"]["20"]["calendar_span_days_inclusive"] >= 20
    assert first["r_metrics_status"] == "AVAILABLE"
    assert first["atr_metrics_status"] == "AVAILABLE"
    assert first["mfe_pct"] is not None
    assert first["mfe_atr"] is not None
    assert first["mfe_r"] is not None
    assert first["cross_segment_observations_used"] == 0
    assert first["no_intrabar_order_invented"] is True
    assert first["outcome_fingerprint"] == second["outcome_fingerprint"]


def test_missing_invalidation_keeps_percent_and_atr_but_never_fabricates_r() -> None:
    frame = _history()
    prepared = prepare_indicators(frame)
    position = 220
    feature = _feature(frame, position, invalidation=None)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    outcome = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=60,
    )

    assert outcome["status"] == "COMPLETE"
    assert outcome["measurement_status"] == "PARTIAL_NON_R"
    assert outcome["r_metrics_status"] == "UNAVAILABLE"
    assert outcome["r_metrics_reason"] == "MISSING_INVALIDATION"
    assert outcome["structural_risk"] is None
    assert outcome["mfe_pct"] is not None
    assert outcome["mae_pct"] is not None
    assert outcome["mfe_atr"] is not None
    assert outcome["mae_atr"] is not None
    assert outcome["mfe_r"] is None
    assert outcome["mae_r"] is None
    assert outcome["r_level_hits"] == {"1.0": None, "2.0": None, "3.0": None}
    assert outcome["checkpoints"]["20"]["mfe_r"] is None
    assert outcome["path_quality"]["peak_giveback_r"] is None
    assert outcome["path_quality"]["final_giveback_r"] is None


def test_non_positive_structural_risk_is_explicit_and_non_r_path_survives() -> None:
    frame = _history()
    prepared = prepare_indicators(frame)
    position = 220
    entry = float(prepared.iloc[position + 1]["Open"])
    feature = _feature(frame, position, invalidation=entry)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    outcome = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=20,
    )

    assert outcome["r_metrics_status"] == "UNAVAILABLE"
    assert outcome["r_metrics_reason"] == "NON_POSITIVE_STRUCTURAL_RISK"
    assert outcome["structural_risk"] is None
    assert outcome["mfe_pct"] is not None
    assert outcome["final_return_pct"] is not None
    assert outcome["mfe_r"] is None
    assert outcome["checkpoints"]["20"]["return_pct"] is not None
    assert outcome["checkpoints"]["20"]["mfe_r"] is None


def test_missing_atr_keeps_percent_path_and_marks_atr_metrics_unavailable() -> None:
    frame = _history()
    prepared = prepare_indicators(frame)
    position = 220
    entry = float(prepared.iloc[position + 1]["Open"])
    prepared.iloc[position, prepared.columns.get_loc("ATR_14")] = np.nan
    feature = _feature(frame, position, invalidation=entry - 4.0)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    outcome = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=20,
    )

    assert outcome["atr_metrics_status"] == "UNAVAILABLE"
    assert outcome["atr_metrics_reason"] == "MISSING_ATR"
    assert outcome["mfe_pct"] is not None
    assert outcome["mae_pct"] is not None
    assert outcome["mfe_atr"] is None
    assert outcome["mae_atr"] is None
    assert outcome["entry_gap_atr"] is None
    assert outcome["checkpoints"]["20"]["mfe_atr"] is None
    # Structural R itself is still well-defined by entry and invalidation.
    assert outcome["r_metrics_status"] == "AVAILABLE"
    assert outcome["mfe_r"] is not None


def test_missing_atr_and_invalidation_explain_unavailable_r_without_losing_path() -> None:
    frame = _history()
    prepared = prepare_indicators(frame)
    position = 220
    prepared.iloc[position, prepared.columns.get_loc("ATR_14")] = np.nan
    feature = _feature(frame, position, invalidation=None)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    outcome = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=20,
    )

    assert outcome["atr_metrics_reason"] == "MISSING_ATR"
    assert outcome["r_metrics_status"] == "UNAVAILABLE"
    assert outcome["r_metrics_reason"] == "MISSING_ATR"
    assert outcome["mfe_pct"] is not None
    assert outcome["mfe_atr"] is None
    assert outcome["mfe_r"] is None


def test_no_next_session_is_censored_at_declared_input_gap() -> None:
    full = _history()
    position = 220
    frame = full.iloc[: position + 1].copy()
    frame.attrs["input_segment_id"] = "segment-001"
    frame.attrs["segment_end_reason"] = "INVALID_SOURCE_SESSION"
    feature = _feature(frame, position, invalidation=90.0)

    outcome = build_outcome_v6(feature_snapshot=feature, frame=frame)

    assert outcome["status"] == "CENSORED_AT_INPUT_GAP"
    assert outcome["reason"] == "NEXT_OPEN_AFTER_INPUT_GAP"
    assert outcome["measurement_status"] == "NO_REFERENCE_ENTRY"
    assert outcome["observations_available"] == 0
    assert outcome["observation_axis"] == {
        "observed_bar_count": 0,
        "calendar_span_days_inclusive": None,
        "declared_data_gap_boundary_encountered": True,
        "data_gaps_crossed": 0,
        "counting_basis": "AVAILABLE_SOURCE_BARS_WITHIN_ONE_INPUT_SEGMENT",
    }
    assert outcome["entry_open"] is None
    assert outcome["mfe_pct"] is None
    assert outcome["mfe_r"] is None
    assert outcome["cross_segment_observations_used"] == 0


def test_no_next_session_without_gap_declaration_is_stage_censored() -> None:
    full = _history()
    position = 220
    frame = full.iloc[: position + 1].copy()
    frame.attrs["input_segment_id"] = "segment-001"
    feature = _feature(frame, position, invalidation=90.0)

    outcome = build_outcome_v6(feature_snapshot=feature, frame=frame)

    assert outcome["status"] == "CENSORED_AT_STAGE_BOUNDARY"


def test_end_of_available_data_is_not_mislabeled_as_input_gap() -> None:
    frame = _history(240)
    snapshot = _feature(frame, 239, invalidation=90.0)
    frame.attrs["segment_end_reason"] = "END_OF_AVAILABLE_DEVELOPMENT_DATA"
    outcome = build_outcome_v6(
        feature_snapshot=snapshot,
        frame=frame,
        segment_end_reason="END_OF_AVAILABLE_DEVELOPMENT_DATA",
    )
    assert outcome["status"] == "CENSORED_AT_END_OF_AVAILABLE_DATA"
    assert outcome["censoring_reason"] == (
        "NEXT_OPEN_NOT_AVAILABLE_IN_FROZEN_DEVELOPMENT_INPUT"
    )
    assert outcome["observation_axis"][
        "declared_data_gap_boundary_encountered"
    ] is False
    assert outcome["observations_available"] == 0


def test_partial_horizon_stops_at_input_gap_and_never_uses_next_segment() -> None:
    full = _history()
    position = 220
    frame = full.iloc[: position + 11].copy()
    frame.attrs["input_segment_id"] = "segment-001"
    frame.attrs["segment_end_reason"] = "CALENDAR_GAP"
    prepared = prepare_indicators(frame)
    entry = float(prepared.iloc[position + 1]["Open"])
    feature = _feature(frame, position, invalidation=entry - 4.0)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    outcome = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=50,
    )

    assert outcome["status"] == "CENSORED_AT_INPUT_GAP"
    assert outcome["censoring_reason"] == "INPUT_GAP_BEFORE_REQUESTED_OBSERVATIONS"
    assert outcome["observations_available"] == 10
    assert outcome["observation_axis"]["observed_bar_count"] == 10
    assert outcome["observation_axis"][
        "declared_data_gap_boundary_encountered"
    ] is True
    assert outcome["observation_axis"]["data_gaps_crossed"] == 0
    assert outcome["outcome_end_day"] == frame.index[-1].date().isoformat()
    assert outcome["cross_segment_observations_used"] == 0
    assert outcome["checkpoints"]["20"] is None


def test_mixed_or_mismatched_segment_identity_is_rejected() -> None:
    frame = _history(260)
    frame["input_segment_id"] = "segment-001"
    frame.iloc[-1, frame.columns.get_loc("input_segment_id")] = "segment-002"
    feature = _feature(frame, 220, invalidation=90.0)

    with pytest.raises(MultiAssetDiscoveryContractError, match="mehrere Input-Segmente"):
        build_outcome_v6(feature_snapshot=feature, frame=frame)

    clean = _history(260)
    mismatched = _feature(clean, 220, invalidation=90.0)
    mismatched["input_segment_id"] = "another-segment"
    with pytest.raises(MultiAssetDiscoveryContractError, match="verschiedene Segmente"):
        build_outcome_v6(feature_snapshot=mismatched, frame=clean)


def test_outcome_does_not_infer_intrabar_order_from_same_bar_extremes() -> None:
    frame = _history(260)
    prepared = prepare_indicators(frame)
    position = 220
    entry = float(prepared.iloc[position + 1]["Open"])
    prepared.iloc[position + 1, prepared.columns.get_loc("High")] = entry + 10.0
    prepared.iloc[position + 1, prepared.columns.get_loc("Low")] = entry - 10.0
    feature = _feature(frame, position, invalidation=entry - 5.0)
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    outcome = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=1,
    )

    assert outcome["r_level_hits"]["1.0"] == 1
    assert outcome["time_to_structural_intraday_invalidation"] == 1
    assert outcome["no_intrabar_order_invented"] is True
    assert "first_event" not in outcome


@pytest.mark.parametrize(
    ("periods", "position", "horizon", "invalidation_offset", "end_reason"),
    [
        (540, 220, 252, 5.0, None),
        (280, 220, 60, None, "CALENDAR_GAP"),
        (231, 220, 50, 4.0, "CALENDAR_GAP"),
    ],
)
def test_once_validated_fastpath_is_exactly_equal_to_defensive_reference_path(
    periods: int,
    position: int,
    horizon: int,
    invalidation_offset: float | None,
    end_reason: str | None,
) -> None:
    frame = _history(periods)
    if end_reason:
        frame.attrs["segment_end_reason"] = end_reason
    prepared = prepare_indicators(frame)
    entry = float(prepared.iloc[position + 1]["Open"])
    feature = _feature(
        frame,
        position,
        invalidation=(
            None if invalidation_offset is None else entry - invalidation_offset
        ),
    )
    safe_history = _safe_history(len(frame), feature["safe_zones"])

    reference = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        segment_end_reason=end_reason,
        requested_observations=horizon,
    )
    context = prepare_outcome_segment_v6(
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        segment_end_reason=end_reason,
    )
    fast = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        segment_context=context,
        signal_position_hint=position,
        requested_observations=horizon,
    )

    assert fast == reference
    assert fast["outcome_fingerprint"] == reference["outcome_fingerprint"]
    assert fast["observations_available"] <= horizon


def test_fastpath_validates_segment_once_and_reuses_direct_position_hints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _history(500)
    prepared = prepare_indicators(frame)
    safe, _ = _zones(90.0)
    safe_history = _safe_history(len(frame), safe)
    validation_calls = 0
    original_validate = outcomes_module._validate_ordered_segment

    def counted_validate(candidate: pd.DataFrame) -> None:
        nonlocal validation_calls
        validation_calls += 1
        original_validate(candidate)

    monkeypatch.setattr(outcomes_module, "_validate_ordered_segment", counted_validate)
    context = prepare_outcome_segment_v6(
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
    )
    assert validation_calls == 2

    for position in (220, 221, 222):
        entry = float(prepared.iloc[position + 1]["Open"])
        feature = _feature(frame, position, invalidation=entry - 5.0)
        outcome = build_outcome_v6(
            feature_snapshot=feature,
            frame=frame,
            segment_context=context,
            signal_position_hint=position,
            requested_observations=20,
        )
        assert outcome["observations_available"] == 20

    # Neither whole-frame validation nor a defensive prepared-frame copy is
    # repeated for subsequent cases in the same segment.
    assert validation_calls == 2


def test_fastpath_rejects_wrong_position_hint_without_searching_for_a_substitute() -> None:
    frame = _history(300)
    prepared = prepare_indicators(frame)
    feature = _feature(frame, 220, invalidation=90.0)
    context = prepare_outcome_segment_v6(frame=frame, prepared_frame=prepared)

    with pytest.raises(MultiAssetDiscoveryContractError, match="Signalpositions-Hinweis"):
        build_outcome_v6(
            feature_snapshot=feature,
            frame=frame,
            segment_context=context,
            signal_position_hint=221,
        )


def test_fastpath_and_reference_are_exact_at_stage_boundary() -> None:
    frame = _history(560)
    prepared = prepare_indicators(frame)
    position = int(prepared.index.get_loc(pd.Timestamp("2021-12-31")))
    feature = _feature(frame, position, invalidation=90.0)
    safe_history = _safe_history(len(frame), feature["safe_zones"])
    reference = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
        requested_observations=20,
    )
    context = prepare_outcome_segment_v6(
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
    )
    fast = build_outcome_v6(
        feature_snapshot=feature,
        frame=frame,
        segment_context=context,
        signal_position_hint=position,
        requested_observations=20,
    )

    assert fast == reference
    assert fast["status"] == "CENSORED_AT_STAGE_BOUNDARY"
    assert fast["observations_available"] == 0
