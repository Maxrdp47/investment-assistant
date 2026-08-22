from __future__ import annotations

import copy
import sqlite3

import numpy as np
import pandas as pd
import pytest

from swing_broad_context import (
    breadth_feature_for_asset,
    build_historical_breadth_context,
    build_shared_asset_features,
)
from swing_broad_research import (
    _prepare_historical_indicators,
    load_broad_research_breadth,
    record_broad_research_breadth,
)


def _prepared(scale: float = 1.0) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-02", periods=310)
    close = (80 + np.linspace(0, 35, len(index)) + np.sin(np.arange(len(index)) / 7) * 3) * scale
    opening = close * (1 + np.cos(np.arange(len(index))) * 0.003)
    raw = pd.DataFrame(
        {
            "Open": opening,
            "High": np.maximum(opening, close) + scale,
            "Low": np.minimum(opening, close) - scale,
            "Close": close,
            "Volume": np.linspace(800_000, 1_600_000, len(index)),
        },
        index=index,
    )
    return _prepare_historical_indicators(raw)


def _asset(region: str = "USA") -> dict:
    return {"ticker": "TEST", "asset_type": "Aktie", "region": region}


def test_shared_market_features_are_point_in_time_and_raw() -> None:
    asset_frame = _prepared()
    benchmark = _prepared(0.7)
    position = 260
    first = build_shared_asset_features(
        asset_frame,
        position,
        asset=_asset(),
        benchmark_histories={"SPY": benchmark},
    )
    changed_asset = asset_frame.copy()
    changed_asset.iloc[position + 1 :, :] *= 50
    changed_benchmark = benchmark.copy()
    changed_benchmark.iloc[position + 1 :, :] /= 50
    second = build_shared_asset_features(
        changed_asset,
        position,
        asset=_asset(),
        benchmark_histories={"SPY": changed_benchmark},
    )

    assert first == second
    assert first["future_bars_used"] == 0
    assert first["relative_strength"]["benchmark_symbol"] == "SPY"
    assert first["relative_strength"]["sector_benchmark"] is None
    assert first["relative_strength"]["comparison_group_percentile"] is None
    assert first["trend_quality"]["additional_trend_indicator_added"] is False
    assert first["volatility_structure"]["signal_bar_excluded_from_prior_normal_ranges"] is True
    assert first["candle_quality"]["subjective_candlestick_name"] is None
    assert first["gap_risk"]["hard_gate"] is False


def test_frozen_universe_breadth_is_causal_and_explicitly_not_survivorship_free() -> None:
    first_frame = _prepared()
    second_frame = _prepared(1.2)
    position = 250
    day = first_frame.index[position].date().isoformat()
    first = build_historical_breadth_context(
        [(_asset("USA"), first_frame), (_asset("Europa"), second_frame)]
    )
    changed = second_frame.copy()
    changed.iloc[position + 1 :, :] *= 100
    second = build_historical_breadth_context(
        [(_asset("USA"), first_frame), (_asset("Europa"), changed)]
    )

    key = f"{day}|overall|all"
    assert first[key] == second[key]
    feature = breadth_feature_for_asset(first, day=day, asset=_asset())
    assert feature["overall"] is not None
    assert feature["survivorship_free"] is False
    assert feature["sector"] is None
    assert feature["future_universe_information_claimed"] is False
    assert set(feature["overall"]["metrics"]["above_ema20"]["change_pct_points"]) == {
        "5d", "10d", "20d"
    }


def test_breadth_store_is_append_only_deterministic_and_resume_safe(tmp_path) -> None:
    path = tmp_path / "broad.sqlite3"
    context = build_historical_breadth_context([(_asset(), _prepared())])
    first = record_broad_research_breadth(context, dataset_fingerprint="frozen-v1", path=path)
    second = record_broad_research_breadth(context, dataset_fingerprint="frozen-v1", path=path)

    assert first["already_present"] is False
    assert second["already_present"] is True
    assert load_broad_research_breadth(dataset_fingerprint="frozen-v1", path=path) == context
    changed = copy.deepcopy(context)
    next(iter(changed.values()))["survivorship_free"] = True
    with pytest.raises(ValueError, match="Breadth-Kontext"):
        record_broad_research_breadth(changed, dataset_fingerprint="frozen-v1", path=path)
    with sqlite3.connect(path) as connection, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("DELETE FROM broad_research_breadth_manifests")
