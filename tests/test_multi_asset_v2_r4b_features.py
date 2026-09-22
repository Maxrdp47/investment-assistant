from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from multi_asset_v2_r4b_features import build_r4b_features, load_contract


def _bars(n: int = 170) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-02", periods=n)
    close = pd.Series(100 + np.arange(n) * 0.2 + np.sin(np.arange(n) / 4), index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.4,
            "Low": close - 0.5,
            "Close": close,
        },
        index=index,
    )


def test_r4b_contract_is_frozen_and_features_are_causal() -> None:
    _, fingerprint = load_contract()
    bars = _bars()
    benchmark = pd.DataFrame({"Close": 80 + np.arange(len(bars)) * 0.12}, index=bars.index)
    baseline = build_r4b_features(bars, benchmark)
    changed = bars.copy(deep=True)
    changed.iloc[140:, changed.columns.get_loc("Close")] *= 1.2
    changed.iloc[140:, changed.columns.get_loc("High")] *= 1.2
    changed.iloc[140:, changed.columns.get_loc("Low")] *= 0.8
    changed.iloc[140:, changed.columns.get_loc("Open")] *= 1.1
    changed_benchmark = benchmark.copy(deep=True)
    changed_benchmark.iloc[140:, 0] *= 2
    replay = build_r4b_features(changed, changed_benchmark)
    pd.testing.assert_frame_equal(baseline.iloc[:140], replay.iloc[:140])
    assert set(baseline["r4b_contract_fingerprint"]) == {fingerprint}
    assert baseline["strategy_filter_created"].eq(False).all()
    assert baseline["sector_benchmark_status"].eq("UNAVAILABLE_NO_HISTORICAL_SECTOR_MAPPING").all()
    pd.testing.assert_frame_equal(bars, _bars())


def test_benchmark_uses_only_strictly_prior_close_and_stale_is_missing() -> None:
    bars = _bars()
    benchmark = pd.DataFrame({"Close": 80 + np.arange(len(bars)) * 0.12}, index=bars.index)
    date = bars.index[125]
    features = build_r4b_features(bars, benchmark)
    assert features.loc[date, "benchmark_known_date"] == bars.index[124].date().isoformat()
    assert features.loc[date, "benchmark_return_20"] == pytest.approx(
        benchmark.iloc[124]["Close"] / benchmark.iloc[104]["Close"] - 1
    )
    changed = benchmark.copy(deep=True)
    changed.loc[date, "Close"] *= 3
    assert build_r4b_features(bars, changed).loc[date, "benchmark_return_20"] == pytest.approx(
        features.loc[date, "benchmark_return_20"]
    )
    stale = benchmark.drop(index=bars.index[120:126])
    stale_features = build_r4b_features(bars, stale)
    assert pd.isna(stale_features.loc[date, "benchmark_return_20"])
    assert pd.isna(stale_features.loc[date, "relative_momentum_20"])
    common = bars.index[130]
    expected = features.loc[common, "asset_return_20"] - features.loc[common, "benchmark_return_20"]
    assert features.loc[common, "relative_momentum_20"] == pytest.approx(expected)
    assert pd.isna(features.iloc[19]["asset_return_20"])
    assert pd.isna(features.iloc[119]["asset_return_120"])


def test_pivot_requires_two_completed_confirmation_bars() -> None:
    bars = _bars(30)
    bars.iloc[6, bars.columns.get_loc("High")] = 160
    benchmark = pd.DataFrame({"Close": np.linspace(80, 85, len(bars))}, index=bars.index)
    features = build_r4b_features(bars, benchmark)
    # The exceptional bar at index 6 cannot be a known pivot at index 6 or 7.
    assert features.iloc[6]["confirmed_structure_sequence"] == "INSUFFICIENT_CONFIRMED_PIVOTS"
    assert features.iloc[7]["confirmed_structure_sequence"] == "INSUFFICIENT_CONFIRMED_PIVOTS"
    assert pd.isna(features.iloc[7]["confirmed_higher_high"])


def test_invalid_ohlc_and_unfrozen_benchmark_fail_closed(tmp_path) -> None:
    bars = _bars()
    benchmark = pd.DataFrame({"Close": np.linspace(80, 85, len(bars))}, index=bars.index)
    broken = bars.copy(deep=True)
    broken.iloc[4, broken.columns.get_loc("Low")] = 1000
    with pytest.raises(ValueError, match="envelope"):
        build_r4b_features(broken, benchmark)
    contract, _ = load_contract()
    bad_contract = copy.deepcopy(contract)
    bad_contract["market_benchmark"] = "SPY"
    path = tmp_path / "bad.json"
    path.write_text(__import__("json").dumps(bad_contract), encoding="utf-8")
    with pytest.raises(ValueError, match="benchmark scope"):
        build_r4b_features(bars, benchmark, contract_path=path)


def test_benchmark_return_never_crosses_segment_boundary() -> None:
    bars = _bars(190)
    benchmark = pd.DataFrame(
        {"Close": np.linspace(80, 90, len(bars)), "SegmentId": 0},
        index=bars.index,
    )
    boundary_position = 80
    benchmark.iloc[boundary_position:, benchmark.columns.get_loc("SegmentId")] = 1

    features = build_r4b_features(bars, benchmark)

    first_signal_after_boundary = bars.index[boundary_position + 1]
    assert pd.isna(features.loc[first_signal_after_boundary, "benchmark_return_20"])
    assert pd.notna(features.loc[bars.index[boundary_position + 21], "benchmark_return_20"])
