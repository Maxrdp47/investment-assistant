from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from forecast_learning import build_learning_dataset_report, build_purged_walk_forward_windows
from forecast_store import FORECAST_LOGIC_VERSION, record_evaluation, record_forecast, start_or_resume_run


def snapshot(ticker: str, run_date: str) -> dict:
    return {
        "run_date": run_date,
        "created_at": f"{run_date}T22:30:00+02:00",
        "ticker": ticker,
        "asset_name": ticker,
        "asset_type": "Aktie",
        "region": "USA",
        "category": "Test",
        "price_original": 100.0,
        "original_currency": "EUR",
        "fx_rate_to_eur": 1.0,
        "price_eur": 100.0,
        "asset_quality": 7.0,
        "buy_signal": 6.0,
        "market_phase": "Bullenmarkt",
        "predicted_direction": "Steigend",
        "confidence": 7.0,
        "data_quality": 8.0,
        "data_quality_label": "Grün",
        "data_coverage": "Test",
        "uncertainties": [],
        "scenarios": [],
        "professional_decision": {},
        "signal_snapshot": {"MACD": "positiv"},
        "probability_snapshot": {
            "status": "available",
            "schema_version": "raw-up-scenario-mixture-2026.08.09-v1",
            "probability_up": 0.6,
            "calibration_status": "uncalibrated",
        },
        "module_scores": [{"name": "Test", "score": 7.0}],
        "horizons": [
            {
                "horizon": "1w",
                "days": 7,
                "expected_direction": "Steigend",
                "expected_low_eur": 95.0,
                "expected_high_eur": 110.0,
                "target_eur": 108.0,
                "risk_eur": 92.0,
                "probability_up": 0.6,
                "probability_schema_version": "raw-up-scenario-mixture-2026.08.09-v1",
            }
        ],
        "model_type": "entry_analysis",
        "logic_version": FORECAST_LOGIC_VERSION,
        "source": "test",
    }


def test_learning_dataset_uses_only_verified_matured_point_in_time_rows() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "learning.sqlite3"
        identifiers = {}
        for index, ticker in enumerate(("ELIGIBLE", "OPEN", "LEGACY", "BROKEN"), start=1):
            run_date = f"2026-06-0{index}"
            run = start_or_resume_run(run_date, 1, database_path)
            identifiers[ticker], _ = record_forecast(
                run.run_id,
                snapshot(ticker, run_date),
                database_path,
            )
        record_evaluation(
            {
                "forecast_id": identifiers["ELIGIBLE"],
                "horizon": "1w",
                "evaluated_at": "2026-06-10T22:30:00+02:00",
                "actual_return_pct": 4.0,
                "actual_day": "2026-06-10",
                "direction_hit": 1,
                "data_quality": "Gut",
            },
            database_path,
        )
        record_evaluation(
            {
                "forecast_id": identifiers["LEGACY"],
                "horizon": "1w",
                "evaluated_at": "2026-06-12T22:30:00+02:00",
                "actual_return_pct": -2.0,
                "actual_day": "2026-06-12",
                "direction_hit": 0,
                "data_quality": "Gut",
            },
            database_path,
        )
        record_evaluation(
            {
                "forecast_id": identifiers["BROKEN"],
                "horizon": "1w",
                "evaluated_at": "2026-06-13T22:30:00+02:00",
                "actual_return_pct": 1.0,
                "actual_day": "2026-06-13",
                "direction_hit": 1,
                "data_quality": "Gut",
            },
            database_path,
        )
        with closing(sqlite3.connect(database_path)) as connection:
            connection.execute(
                "UPDATE forecasts SET observation_cutoff_at = NULL, feature_schema_version = NULL, "
                "feature_snapshot_json = NULL, measurement_contract_version = NULL, "
                "measurement_contract_json = NULL, snapshot_fingerprint = NULL WHERE id = ?",
                (identifiers["LEGACY"],),
            )
            connection.execute(
                "UPDATE forecasts SET snapshot_fingerprint = 'tampered' WHERE id = ?",
                (identifiers["BROKEN"],),
            )
            connection.commit()

        first = build_learning_dataset_report(database_path)
        second = build_learning_dataset_report(database_path)

        assert first["status"] == "attention"
        assert first["eligible_cases"] == 1
        assert first["excluded"]["legacy_without_contract"] == 1
        assert first["excluded"]["invalid_measurement_contract"] == 1
        assert first["excluded"]["outcome_not_matured"] == 1
        assert first["segments"][0]["probability_coverage_pct"] == 100.0
        assert first["segments"][0]["shadow_research_ready"] is False
        assert first["production_activation_allowed"] is False
        assert first["dataset_fingerprint"] == second["dataset_fingerprint"]


def test_learning_dataset_reports_missing_database_without_creating_it() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "missing.sqlite3"
        report = build_learning_dataset_report(database_path)

        assert report["status"] == "missing_database"
        assert report["eligible_cases"] == 0
        assert report["production_activation_allowed"] is False
        assert not database_path.exists()


def test_walk_forward_windows_purge_labels_not_known_at_stage_start() -> None:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(100):
        observation_day = start + timedelta(days=offset)
        outcome_day = observation_day + timedelta(days=7)
        rows.append(
            {
                "observation_cutoff_at": datetime.combine(
                    observation_day,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ).isoformat(),
                "actual_day": outcome_day.isoformat(),
                "snapshot_fingerprint": f"row-{offset:03d}",
            }
        )

    windows = build_purged_walk_forward_windows(
        rows,
        minimum_training_days=28,
        validation_days=14,
        test_days=14,
        step_days=14,
    )

    assert windows
    first = windows[0]
    assert first["training"]["cases"] == 21
    assert first["validation"]["cases"] == 7
    assert first["test"]["cases"] == 14
    assert first["training"]["latest_known_outcome_day"] < first["validation"]["observation_start"]
    assert first["validation"]["latest_known_outcome_day"] < first["test"]["observation_start"]
    assert first["purged_before_validation"] == 7
    assert first["purged_before_test"] == 7
    assert first["random_row_split_used"] is False
    assert len(first["fingerprint"]) == 64
