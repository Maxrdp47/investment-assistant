from __future__ import annotations

import tempfile
import json
from datetime import datetime
from pathlib import Path

from forecast_calibration import (
    CALIBRATION_PROFILE_VERSION,
    build_calibration_profile,
    load_calibration_profile,
    write_calibration_profile,
)
from forecast_store import (
    FORECAST_LOGIC_VERSION,
    FORECAST_MODEL_ENTRY,
    record_evaluation,
    record_forecast,
    start_or_resume_run,
)
from forecast_runner import run_daily_process


def forecast_snapshot(ticker: str, run_date: str) -> dict:
    return {
        "run_date": run_date,
        "created_at": f"{run_date}T22:30:00+02:00",
        "ticker": ticker,
        "asset_name": ticker,
        "asset_type": "Aktie",
        "region": "Test",
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
        "data_coverage": "Testdaten",
        "uncertainties": [],
        "scenarios": [],
        "professional_decision": {},
        "signal_snapshot": {},
        "probability_snapshot": {
            "status": "available",
            "schema_version": "raw-up-scenario-mixture-2026.08.09-v1",
            "probability_up": 0.6,
            "calibration_status": "uncalibrated",
        },
        "module_scores": [],
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
        "model_type": FORECAST_MODEL_ENTRY,
        "logic_version": FORECAST_LOGIC_VERSION,
        "source": "test",
    }


def test_empty_profile_is_versioned_reproducible_and_never_changes_rules() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "empty.sqlite3"
        first = build_calibration_profile(database_path, generated_at="2026-08-02T10:00:00+02:00")
        second = build_calibration_profile(database_path, generated_at="2026-08-02T11:00:00+02:00")

        assert first["profile_version"] == CALIBRATION_PROFILE_VERSION
        assert first["overall"]["evaluated_cases"] == 0
        assert first["overall"]["maturity"] == "collect_only"
        assert first["data_fingerprint"] == second["data_fingerprint"]
        assert first["guardrails"]["production_weights_changed"] is False
        assert first["guardrails"]["automatic_rule_activation"] is False
        assert first["learning_readiness"]["eligible_cases"] == 0
        assert first["learning_readiness"]["production_activation_allowed"] is False
        assert first["monitoring"]["status"] == "collect_only"
        assert first["monitoring"]["guardrails"]["automatic_model_change"] is False


def test_profile_segments_real_evaluations_and_writes_atomically() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "evaluated.sqlite3"
        output_path = Path(directory) / "calibration.json"
        run_date = "2026-06-01"
        run = start_or_resume_run(run_date, 51, database_path)

        for index in range(51):
            forecast_id, inserted = record_forecast(
                run.run_id,
                forecast_snapshot(f"TEST{index:02d}", run_date),
                database_path,
            )
            assert inserted
            hit = index < 20
            assert record_evaluation(
                {
                    "forecast_id": forecast_id,
                    "horizon": "1w",
                    "evaluated_at": datetime(2026, 6, 8, 22, 30).astimezone().isoformat(),
                    "actual_price_original": 104.0 if hit else 96.0,
                    "actual_price_eur": 104.0 if hit else 96.0,
                    "actual_return_pct": 4.0 if hit else -4.0,
                    "direction_hit": int(hit),
                    "range_hit": 1,
                    "deviation_pct": 2.0,
                    "target_hit": int(hit),
                    "risk_hit": int(not hit),
                    "data_quality": "Gut",
                    "note": "Testauswertung",
                },
                database_path,
            )

        profile = write_calibration_profile(database_path, output_path)
        stored = load_calibration_profile(output_path)

        assert stored is not None
        assert stored["data_fingerprint"] == profile["data_fingerprint"]
        assert profile["overall"]["evaluated_cases"] == 51
        assert profile["overall"]["maturity"] == "manual_review_allowed"
        assert profile["segments"][0]["model_label"] == "Einstiegsanalyse"
        assert profile["segments"][0]["direction_hit_rate_pct"] == 39.2
        assert profile["segments"][0]["probability_evaluated"] == 51
        assert profile["segments"][0]["brier_score"] == 0.2816
        assert profile["overall"]["probability_evaluated"] == 51
        assert profile["segments"][0]["maturity"] == "manual_review_allowed"
        assert profile["manual_review_suggestions"][0]["automatic_change"] is False
        assert profile["manual_review_suggestions"][0]["priority"] == "hoch"
        assert not list(output_path.parent.glob(f".{output_path.name}.*.tmp"))


def test_daily_process_refreshes_profile_without_market_requests() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database_path = root / "daily.sqlite3"
        calibration_path = root / "daily-calibration.json"
        universe_path = root / "universe.csv"
        settings_path = root / "settings.json"
        universe_path.write_text(
            "ticker,asset_type,name,region,category,version\n"
            "TEST,Aktie,Test,Test,Test,v1\n",
            encoding="utf-8",
        )
        settings_path.write_text(
            json.dumps(
                {
                    "database_path": str(database_path),
                    "calibration_path": str(calibration_path),
                    "log_path": str(root / "daily.log"),
                    "universe_path": str(universe_path),
                    "batch_size": 1,
                    "request_delay_seconds": 0,
                    "batch_pause_seconds": 0,
                    "max_retries": 0,
                    "evaluation_limit": 10,
                    "logic_version": FORECAST_LOGIC_VERSION,
                }
            ),
            encoding="utf-8",
        )

        result = run_daily_process(
            settings_path=settings_path,
            run_date="2026-08-02",
            limit=0,
            no_delay=True,
        )

        assert result["collection"]["status"] == "completed"
        assert result["calibration"]["status"] == "ok"
        assert result["calibration"]["evaluated_cases"] == 0
        assert calibration_path.exists()
        assert load_calibration_profile(calibration_path)["guardrails"]["production_rules_changed"] is False
