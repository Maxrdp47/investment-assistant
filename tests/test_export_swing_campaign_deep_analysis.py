from __future__ import annotations

import math

import pandas as pd

from scripts.export_swing_campaign_deep_analysis import (
    assign_dependency_clusters,
    metrics,
)


def _metric_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "case_id": "a",
                "symbol": "AAA",
                "signal_day": "2024-01-01",
                "future_last_day": "2024-01-20",
                "strategy_version": "v1",
                "research_split": "holdout",
                "evaluation_horizon_sessions": 25,
                "issuer_id": "issuer-a",
                "listing_id": "listing-a",
                "economic_instrument_id": None,
                "result_r": 2.0,
                "mfe_pct": 4.0,
                "mae_pct": -1.0,
            },
            {
                "case_id": "b",
                "symbol": "AAA2",
                "signal_day": "2024-01-10",
                "future_last_day": "2024-01-30",
                "strategy_version": "v1",
                "research_split": "holdout",
                "evaluation_horizon_sessions": 25,
                "issuer_id": "issuer-a",
                "listing_id": "listing-a2",
                "economic_instrument_id": None,
                "result_r": -1.0,
                "mfe_pct": 1.0,
                "mae_pct": -2.0,
            },
            {
                "case_id": "c",
                "symbol": "BBB",
                "signal_day": "2024-03-01",
                "future_last_day": "2024-03-25",
                "strategy_version": "v1",
                "research_split": "holdout",
                "evaluation_horizon_sessions": 25,
                "issuer_id": "issuer-b",
                "listing_id": "listing-b",
                "economic_instrument_id": None,
                "result_r": 0.0,
                "mfe_pct": 0.5,
                "mae_pct": -0.5,
            },
        ]
    )


def test_dependency_clusters_collapse_overlapping_same_issuer() -> None:
    frame = _metric_frame()
    clusters = assign_dependency_clusters(frame)

    assert clusters.iloc[0] == clusters.iloc[1]
    assert clusters.iloc[2] != clusters.iloc[0]
    assert clusters.nunique() == 2


def test_metrics_keep_zero_separate_and_reconcile() -> None:
    frame = _metric_frame()
    frame["dependency_cluster_id"] = assign_dependency_clusters(frame)

    result = metrics(frame)

    assert result["raw_n"] == 3
    assert result["evaluated_n"] == 3
    assert result["effective_n"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["zero"] == 1
    assert math.isclose(result["average_r"], 1.0 / 3.0)
    assert math.isclose(result["profit_factor"], 2.0)
    assert result["maximum_losing_streak"] == 2
