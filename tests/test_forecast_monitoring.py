from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from forecast_monitoring import (
    FORECAST_MONITORING_VERSION,
    build_forecast_monitoring_report,
    compare_evaluation_windows,
)
from forecast_store import initialize_database


def evaluation_rows(*, cases: int, hits: int, trend_hits: int, excess_return: float) -> list[dict]:
    return [
        {
            "direction_hit": int(index < hits),
            "simple_trend_hit": int(index < trend_hits),
            "probability_up": 0.8,
            "actual_return_pct": 4.0 if index < hits else -4.0,
            "excess_return_pct": excess_return,
        }
        for index in range(cases)
    ]


def test_monitoring_detects_multiple_outcome_and_probability_deteriorations() -> None:
    comparison = compare_evaluation_windows(
        evaluation_rows(cases=60, hits=48, trend_hits=36, excess_return=2.0),
        evaluation_rows(cases=60, hits=24, trend_hits=36, excess_return=-5.0),
        model_type="entry_analysis",
        horizon="1w",
    )

    alert_codes = {alert["code"] for alert in comparison["alerts"]}
    assert comparison["status"] == "attention"
    assert comparison["outcome_comparison_ready"] is True
    assert comparison["probability_comparison_ready"] is True
    assert comparison["deltas"]["direction_hit_rate_pct_points"] == -40.0
    assert "direction_quality_drop" in alert_codes
    assert "benchmark_advantage_drop" in alert_codes
    assert "excess_return_drop" in alert_codes
    assert "brier_score_worse" in alert_codes
    assert "log_loss_worse" in alert_codes
    assert all(alert["automatic_change"] is False for alert in comparison["alerts"])


def test_small_windows_are_not_misreported_as_drift() -> None:
    comparison = compare_evaluation_windows(
        evaluation_rows(cases=5, hits=5, trend_hits=5, excess_return=4.0),
        evaluation_rows(cases=5, hits=0, trend_hits=5, excess_return=-9.0),
        model_type="entry_analysis",
        horizon="1w",
    )

    assert comparison["status"] == "insufficient_data"
    assert comparison["alerts"] == []
    assert comparison["outcome_comparison_ready"] is False


def test_empty_database_report_is_observe_only_and_reproducible() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "monitoring.sqlite3"
        initialize_database(database_path)

        first = build_forecast_monitoring_report(database_path, as_of=date(2026, 8, 9))
        second = build_forecast_monitoring_report(database_path, as_of=date(2026, 8, 9))

        assert first == second
        assert first["monitoring_version"] == FORECAST_MONITORING_VERSION
        assert first["status"] == "collect_only"
        assert first["operational"]["due_total"] == 0
        assert first["alerts"] == []
        assert first["guardrails"]["observe_only"] is True
        assert first["guardrails"]["automatic_model_change"] is False
