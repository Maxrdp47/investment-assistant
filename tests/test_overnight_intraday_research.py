from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from overnight_intraday_research import (
    OvernightIntradayResearchError,
    add_overnight_intraday_research_labels,
    build_overnight_intraday_features,
    classify_overnight_intraday_evidence,
    evaluate_overnight_intraday_research,
    overnight_intraday_research_plan,
)


def history(rows: int = 80, *, asset: str | None = None) -> pd.DataFrame:
    index = pd.date_range("2023-01-02", periods=rows, freq="B")
    previous = np.linspace(100.0, 120.0, rows)
    open_price = previous * (1.0 + np.sin(np.arange(rows)) * 0.002)
    close = open_price * (1.0 + np.cos(np.arange(rows)) * 0.003)
    frame = pd.DataFrame(
        {
            "Open": open_price,
            "High": np.maximum(open_price, close) * 1.01,
            "Low": np.minimum(open_price, close) * 0.99,
            "Close": close,
        },
        index=index,
    )
    if asset is not None:
        frame["asset"] = asset
    return frame


def test_exact_daily_decomposition_and_rolling_metrics() -> None:
    source = pd.DataFrame(
        {
            "Open": [100.0, 110.0, 108.0, 112.0],
            "High": [102.0, 112.0, 114.0, 115.0],
            "Low": [98.0, 107.0, 107.0, 110.0],
            "Close": [100.0, 108.0, 112.0, 114.0],
        },
        index=pd.date_range("2024-01-02", periods=4, freq="B"),
    )

    result = build_overnight_intraday_features(
        source, rolling_window=2, min_periods=2
    )

    assert result["overnight_return"].iloc[1] == pytest.approx(0.10)
    assert result["intraday_return"].iloc[1] == pytest.approx(108 / 110 - 1)
    assert result["close_to_close_return"].iloc[1] == pytest.approx(0.08)
    reconstructed = (1 + result["overnight_return"]) * (
        1 + result["intraday_return"]
    ) - 1
    pd.testing.assert_series_equal(
        reconstructed,
        result["close_to_close_return"],
        check_names=False,
    )
    expected_bias = (
        result["overnight_return"].rolling(2).mean()
        - result["intraday_return"].rolling(2).mean()
    )
    pd.testing.assert_series_equal(
        result["rolling_overnight_bias"], expected_bias, check_names=False
    )
    assert result["rolling_overnight_volatility"].notna().any()
    assert result["rolling_intraday_volatility"].notna().any()


def test_features_are_causal_and_inputs_are_not_mutated() -> None:
    source = history(60)
    original = source.copy(deep=True)
    changed_future = source.copy(deep=True)
    changed_future.iloc[-1, changed_future.columns.get_loc("Open")] *= 3
    changed_future.iloc[-1, changed_future.columns.get_loc("Close")] *= 2

    baseline = build_overnight_intraday_features(source, rolling_window=10)
    changed = build_overnight_intraday_features(changed_future, rolling_window=10)

    pd.testing.assert_frame_equal(source, original)
    pd.testing.assert_frame_equal(
        baseline.iloc[:-1], changed.iloc[:-1], check_exact=True
    )


def test_multiple_assets_never_share_previous_close_or_rolling_window() -> None:
    first = history(30, asset="AAA")
    second = history(30, asset="ETF-X")
    second[["Open", "High", "Low", "Close"]] *= 10
    combined = pd.concat([first, second])

    result = build_overnight_intraday_features(combined, rolling_window=5)

    first_rows = result[result["asset"] == "AAA"]
    second_rows = result[result["asset"] == "ETF-X"]
    assert pd.isna(first_rows["overnight_return"].iloc[0])
    assert pd.isna(second_rows["overnight_return"].iloc[0])
    assert first_rows["rolling_overnight_bias"].iloc[:4].isna().all()
    assert second_rows["rolling_overnight_bias"].iloc[:4].isna().all()


def test_future_labels_are_separate_and_respect_setup_mask() -> None:
    source = history(12)
    source["is_existing_setup"] = [True, False] * 6
    features = build_overnight_intraday_features(
        source, rolling_window=3, min_periods=2
    )
    causal_snapshot = features.copy(deep=True)

    labelled = add_overnight_intraday_research_labels(
        features,
        horizons=(1, 5),
        setup_mask_column="is_existing_setup",
    )

    pd.testing.assert_frame_equal(features, causal_snapshot)
    assert "forward_return_5s" not in features
    assert labelled.loc[~labelled["is_existing_setup"], "forward_return_1s"].isna().all()
    assert labelled["forward_mfe_5s"].dropna().ge(0).all()
    assert labelled["forward_mae_5s"].dropna().le(0).all()


def test_report_exposes_assets_periods_splits_folds_and_optional_segments() -> None:
    first = history(270, asset="AAA")
    second = history(270, asset="ETF-X")
    second.index = pd.date_range("2024-01-02", periods=270, freq="B")
    combined = pd.concat([first, second])
    combined["research_split"] = np.where(
        np.arange(len(combined)) % 3 == 0, "development", "holdout"
    )
    combined["walk_forward_fold"] = np.where(
        np.arange(len(combined)) % 2 == 0, "fold-1", "fold-2"
    )
    combined["market_regime"] = np.where(
        np.arange(len(combined)) % 2 == 0, "bull", "bear"
    )
    features = build_overnight_intraday_features(combined, rolling_window=10)
    dataset = add_overnight_intraday_research_labels(features, horizons=(5,))

    report = evaluate_overnight_intraday_research(
        dataset, horizons=(5,), minimum_cases=20
    )

    assert report["market_scope"] == "EQUITIES/ETF"
    assert report["coverage"]["asset_count"] == 2
    assert report["coverage"]["calendar_period_count"] >= 2
    assert report["coverage"]["oos_split_present"] is True
    assert report["coverage"]["walk_forward_present"] is True
    assert len(report["by_asset"]) == 2
    assert len(report["by_split"]) == 2
    assert len(report["by_walk_forward_fold"]) == 2
    assert len(report["segments"]["market_regime"]) == 2
    assert report["overall"][0]["cost_model_status"] == (
        "NOT_APPLICABLE_NO_TRADABLE_VARIANT"
    )
    assert report["automatic_rule_selection"] is False
    assert report["automatic_activation"] is False


def test_abc_classification_requires_completed_robust_evidence_for_c() -> None:
    assert classify_overnight_intraday_evidence(
        test_completed=True,
        multiple_assets=True,
        multiple_periods=True,
        interesting_signal=False,
        robust_out_of_sample=False,
        robust_walk_forward=False,
        temporally_stable=False,
    )["grade"] == "A"
    assert classify_overnight_intraday_evidence(
        test_completed=True,
        multiple_assets=True,
        multiple_periods=True,
        interesting_signal=True,
        robust_out_of_sample=False,
        robust_walk_forward=False,
        temporally_stable=False,
    )["grade"] == "B"
    c_result = classify_overnight_intraday_evidence(
        test_completed=True,
        multiple_assets=True,
        multiple_periods=True,
        interesting_signal=True,
        robust_out_of_sample=True,
        robust_walk_forward=True,
        temporally_stable=True,
    )
    assert c_result["grade"] == "C"
    assert c_result["knowledge_outcome"] == "POSITIVE_CANDIDATE_NOT_ACTIVE"
    assert c_result["trade_rule_created"] is False
    assert c_result["automatic_activation"] is False
    with pytest.raises(OvernightIntradayResearchError):
        classify_overnight_intraday_evidence(
            test_completed=False,
            multiple_assets=False,
            multiple_periods=False,
            interesting_signal=True,
            robust_out_of_sample=False,
            robust_walk_forward=False,
            temporally_stable=False,
        )


def test_plan_is_deterministic_scoped_and_cannot_activate_a_trade() -> None:
    plan = overnight_intraday_research_plan()
    original = copy.deepcopy(plan)

    assert plan == overnight_intraday_research_plan()
    assert plan == original
    assert plan["market_scope"] == "EQUITIES/ETF"
    assert plan["hypothesis"]["scope"]["test_scope"] == ["EQUITIES", "ETF"]
    assert plan["feature"]["live_signal_influence"] is False
    assert plan["close_to_next_open_strategy_active"] is False
    assert plan["single_asset_parameter_selection_allowed"] is False
    assert plan["micron_may_define_or_justify_parameters"] is False
    assert plan["current_broad_campaign_changed"] is False
    assert plan["current_campaign_queue_changed"] is False
    assert plan["research_database_write"] is False
    assert plan["current_baseline_changed"] is False
    assert plan["automatic_activation"] is False
    assert len(plan["plan_fingerprint"]) == 64
