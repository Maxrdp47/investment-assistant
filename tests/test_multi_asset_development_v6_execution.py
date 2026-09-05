from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import multi_asset_development_v6_execution as execution
from multi_asset_development_v6_inputs import SegmentedAssetHistory


def _contract() -> dict[str, object]:
    return {
        "contract_version": "multi-asset-opportunity-discovery-development-2026.09.05-v6",
        "contract_fingerprint": "contract-fp",
        "development_execution": {
            "development_start": "2016-01-01",
            "development_end": "2021-12-31",
        },
        "outcome_contract": {"horizon_daily_observations": 252},
        "reference_fingerprints": {
            "combined_input_fingerprint": "combined-fp",
            "gap_policy_fingerprint": "gap-fp",
        },
    }


def _asset() -> dict[str, object]:
    return {
        "asset_key": "FX:EUR/USD",
        "asset_class": "FX",
        "symbol": "EUR/USD",
        "identity": None,
    }


def _unit(
    unit_id: str = "unit-1",
    *,
    period_start: str = "2016-01-01",
    period_end: str = "2016-12-31",
) -> dict[str, object]:
    return {
        "work_unit_id": unit_id,
        "asset_key": "FX:EUR/USD",
        "asset_class": "FX",
        "symbol": "EUR/USD",
        "period_start": period_start,
        "period_end": period_end,
        "attempts": 1,
    }


def _history(segment_lengths: tuple[int, ...]) -> SegmentedAssetHistory:
    frames = []
    cursor = pd.Timestamp("2016-01-01")
    end_reasons: dict[int, str] = {}
    availability: dict[str, str] = {}
    for segment_id, length in enumerate(segment_lengths):
        index = pd.date_range(cursor, periods=length, freq="D")
        base = np.linspace(100 + segment_id, 125 + segment_id, length)
        frame = pd.DataFrame(
            {
                "Open": base,
                "High": base + 1.5,
                "Low": base - 1.5,
                "Close": base + 0.4,
                "Volume": np.full(length, 1000.0),
                "SEGMENT_ID": np.full(length, segment_id),
                "SEGMENT_POSITION": np.arange(length),
                "GAP_BOUNDARY_BEFORE": np.arange(length) == 0,
                "SEGMENT_END_REASON": np.full(
                    length,
                    "MISSING_CALENDAR_OBSERVATIONS"
                    if segment_id < len(segment_lengths) - 1
                    else "END_OF_AVAILABLE_DEVELOPMENT_DATA",
                ),
            },
            index=index,
        )
        frames.append(frame)
        availability.update(
            {
                day.date().isoformat(): day.strftime("%Y-%m-%dT22:15:00+00:00")
                for day in index
            }
        )
        end_reasons[segment_id] = str(frame.iloc[-1]["SEGMENT_END_REASON"])
        cursor = index[-1] + pd.Timedelta(days=3)
    full = (
        pd.concat(frames)
        if frames
        else pd.DataFrame(
            columns=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "SEGMENT_ID",
                "SEGMENT_POSITION",
                "GAP_BOUNDARY_BEFORE",
                "SEGMENT_END_REASON",
            ],
            index=pd.DatetimeIndex([]),
        )
    )
    boundaries = tuple(
        {
            "boundary_type": "MISSING_CALENDAR_OBSERVATIONS",
            "after_date": frames[index].index[-1].date().isoformat(),
            "before_date": frames[index + 1].index[0].date().isoformat(),
            "missing_observations": 2,
        }
        for index in range(len(frames) - 1)
    )
    return SegmentedAssetHistory(
        asset_class="FX",
        symbol="EUR/USD",
        frame=full,
        availability=availability,
        dataset_fingerprint="fx-fp",
        combined_input_fingerprint="combined-fp",
        gap_boundaries=boundaries,
        coverage={"active_valid_bars": len(full)},
        segment_end_reasons=end_reasons,
    )


def test_work_plan_keeps_unchanged_quarter_partition() -> None:
    universe = {"universe_fingerprint": "u", "assets": [_asset()]}
    plan = execution.build_v6_work_plan(universe=universe, contract=_contract())
    assert plan["total_planned_work_units"] == 24
    assert plan["units"][0]["period_start"] == "2016-01-01"
    assert plan["units"][-1]["period_end"] == "2021-12-31"
    assert plan["validation_opened"] is False


def test_compute_resets_warmup_and_never_crosses_gap(monkeypatch) -> None:
    history = _history((222, 222))
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)
    result = execution.compute_v6_asset_batch(
        asset=_asset(),
        units=[_unit(period_end="2017-12-31")],
        contract=_contract(),
        input_precheck_artifact=Path("unused.json"),
    )
    unit = result["unit_results"][0]
    # Each segment contributes positions 219 and 220; its final position has
    # sufficient history but lacks a same-segment reference entry.
    assert len(unit["features"]) == 4
    assert len(unit["outcomes"]) == 4
    assert unit["summary"]["minimum_history_exclusions"] == 438
    assert unit["summary"]["missing_reference_entry"] == 2
    assert unit["summary"]["input_gap_censored_cases"] == 2
    assert unit["summary"]["end_of_data_censored_cases"] == 2
    assert all(item["cross_segment_observations_used"] == 0 for item in unit["outcomes"])
    assert {item["input_segment"]["segment_id"] for item in unit["outcomes"]} == {
        "0",
        "1",
    }


def test_worker_computation_is_payload_deterministic(monkeypatch) -> None:
    history = _history((222,))
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)
    first = execution.compute_v6_asset_batch(
        asset=_asset(), units=[_unit()], contract=_contract()
    )
    second = execution.compute_v6_asset_batch(
        asset=_asset(), units=[_unit()], contract=_contract()
    )
    assert execution.result_scientific_digest(first) == execution.result_scientific_digest(
        second
    )


def test_asset_worker_fastpath_is_exactly_equal_to_defensive_outcome_path(
    monkeypatch,
) -> None:
    history = _history((230, 230))
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)
    units = [_unit(period_end="2017-12-31")]
    fast = execution.compute_v6_asset_batch(
        asset=_asset(), units=units, contract=_contract()
    )
    fast_builder = execution.build_outcome_v6

    def defensive_builder(
        *,
        feature_snapshot,
        frame,
        requested_observations,
        segment_context,
        signal_position_hint,
        **kwargs,
    ):
        del signal_position_hint, kwargs
        return fast_builder(
            feature_snapshot=feature_snapshot,
            frame=frame,
            prepared_frame=segment_context.prepared,
            safe_zone_history=segment_context.safe_zone_history,
            segment_end_reason=segment_context.segment_end_reason,
            requested_observations=requested_observations,
        )

    monkeypatch.setattr(execution, "build_outcome_v6", defensive_builder)
    reference = execution.compute_v6_asset_batch(
        asset=_asset(), units=units, contract=_contract()
    )

    assert fast == reference
    assert execution.result_scientific_digest(fast) == execution.result_scientific_digest(
        reference
    )


def test_segment_contexts_and_quarter_index_are_built_once_per_segment(
    monkeypatch,
) -> None:
    history = _history((222, 222))
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)
    counts = {"feature": 0, "outcome": 0, "period_index": 0}
    original_feature = execution.prepare_feature_snapshot_context
    original_outcome = execution.prepare_outcome_segment_v6
    original_period_index = execution._position_ranges_by_unit

    def counted_feature(*args, **kwargs):
        counts["feature"] += 1
        return original_feature(*args, **kwargs)

    def counted_outcome(*args, **kwargs):
        counts["outcome"] += 1
        return original_outcome(*args, **kwargs)

    def counted_period_index(*args, **kwargs):
        counts["period_index"] += 1
        return original_period_index(*args, **kwargs)

    monkeypatch.setattr(execution, "prepare_feature_snapshot_context", counted_feature)
    monkeypatch.setattr(execution, "prepare_outcome_segment_v6", counted_outcome)
    monkeypatch.setattr(execution, "_position_ranges_by_unit", counted_period_index)
    result = execution.compute_v6_asset_batch(
        asset=_asset(),
        units=[
            _unit("unit-a", period_end="2016-06-30"),
            _unit(
                "unit-b",
                period_start="2016-07-01",
                period_end="2017-12-31",
            ),
        ],
        contract=_contract(),
    )

    assert sum(len(item["features"]) for item in result["unit_results"]) > 0
    assert counts == {"feature": 2, "outcome": 2, "period_index": 2}


def test_dependency_policy_is_built_once_per_equity_asset(monkeypatch) -> None:
    history = _history((223,))
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)
    calls = 0
    original = execution.build_historical_dependency_policy

    def counted_policy():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(execution, "build_historical_dependency_policy", counted_policy)
    asset = {
        "asset_key": "EQUITIES:TEST",
        "asset_class": "EQUITIES",
        "symbol": "TEST",
        "identity": {
            "ticker": "TEST",
            "asset_id": "asset-test",
            "listing_id": "listing-test",
            "issuer_id": "issuer-test",
            "mapping_status": "VERIFIED",
        },
    }
    unit = {
        **_unit(period_end="2016-12-31"),
        "asset_key": "EQUITIES:TEST",
        "asset_class": "EQUITIES",
        "symbol": "TEST",
    }

    result = execution.compute_v6_asset_batch(
        asset=asset,
        units=[unit],
        contract=_contract(),
    )

    assert len(result["unit_results"][0]["features"]) > 1
    assert calls == 1


def test_no_data_is_expected_skip_without_retry(monkeypatch) -> None:
    history = _history(())
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)
    result = execution.compute_v6_asset_batch(
        asset=_asset(), units=[_unit()], contract=_contract()
    )
    assert result["skip_reason_code"] == "EXPECTED_NO_DEVELOPMENT_DATA"
    assert result["unit_results"] == []


def test_nonempty_history_without_gap_safe_220_bar_segment_is_expected_skip(
    monkeypatch,
) -> None:
    history = _history((220, 220))
    monkeypatch.setattr(execution, "load_v6_asset_history", lambda *args, **kwargs: history)

    result = execution.compute_v6_asset_batch(
        asset=_asset(), units=[_unit(period_end="2017-12-31")], contract=_contract()
    )

    assert result["skip_reason_code"] == "NO_GAP_SAFE_220_OBSERVATION_HISTORY"
    assert result["unit_results"] == []
    assert result["gap_boundary_count"] == 1
    assert result["coverage"] == {"active_valid_bars": 440}


def test_non_transient_contract_errors_are_not_retryable() -> None:
    assert not execution.is_retryable_compute_error(
        execution.DevelopmentV6ExecutionError("fingerprint mismatch")
    )
