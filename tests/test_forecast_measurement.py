from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from forecast_measurement import (
    BENCHMARK_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_CONTRACT_VERSION,
    build_measurement_record,
    verify_measurement_record,
)
from forecast_store import (
    CURRENT_SCHEMA_VERSION,
    FORECAST_LOGIC_VERSION,
    database_health,
    initialize_database,
    measurement_contract_audit,
    record_forecast,
    start_or_resume_run,
)


def measurement_snapshot() -> dict:
    return {
        "run_date": "2026-08-09",
        "created_at": datetime.now().astimezone().isoformat(),
        "ticker": "TEST",
        "asset_name": "Test Asset",
        "asset_type": "Aktie",
        "region": "USA",
        "category": "Test",
        "price_original": 100.0,
        "original_currency": "USD",
        "fx_rate_to_eur": 0.9,
        "price_eur": 90.0,
        "asset_quality": 7.0,
        "buy_signal": 6.0,
        "market_phase": "Bullenmarkt",
        "predicted_direction": "Steigend",
        "confidence": 7.0,
        "data_quality": 8.0,
        "data_quality_label": "Grün",
        "data_coverage": "Testabdeckung",
        "uncertainties": ["Testunsicherheit"],
        "scenarios": [{"Szenario": "Base-Case"}],
        "professional_decision": {"Titel": "Beobachten"},
        "signal_snapshot": {"RSI": 51.0, "MACD": "positiv"},
        "probability_snapshot": {
            "status": "available",
            "schema_version": "raw-up-scenario-mixture-2026.08.09-v1",
            "probability_up": 0.6,
            "calibration_status": "uncalibrated",
        },
        "module_scores": [{"name": "Technik", "score": 6.0}],
        "horizons": [
            {
                "horizon": "1w",
                "days": 7,
                "expected_direction": "Steigend",
                "expected_low_eur": 85.0,
                "expected_high_eur": 100.0,
                "target_eur": 98.0,
                "risk_eur": 82.0,
                "probability_up": 0.6,
                "probability_schema_version": "raw-up-scenario-mixture-2026.08.09-v1",
            }
        ],
        "model_type": "entry_analysis",
        "logic_version": FORECAST_LOGIC_VERSION,
        "source": "test",
    }


class ForecastMeasurementTests(unittest.TestCase):
    def test_contract_defines_labels_benchmarks_costs_quality_and_leakage(self) -> None:
        record = build_measurement_record(measurement_snapshot())
        contract = json.loads(record["measurement_contract_json"])

        self.assertEqual(record["feature_schema_version"], FEATURE_SCHEMA_VERSION)
        self.assertEqual(record["measurement_contract_version"], MEASUREMENT_CONTRACT_VERSION)
        self.assertEqual(
            contract["benchmark_contract"]["schema_version"], BENCHMARK_SCHEMA_VERSION
        )
        self.assertEqual(
            contract["label_contract"]["direction_hit"]["Steigend"],
            "actual_return_pct > 0",
        )
        self.assertEqual(
            contract["benchmark_contract"]["not_yet_captured"],
            ["simple_trend", "market_benchmark"],
        )
        self.assertEqual(contract["cost_contract"]["raw_forecast_metrics_round_trip_bps"], 0)
        self.assertEqual(contract["probability_contract"]["eligibility"], "scoreable")
        self.assertEqual(contract["probability_contract"]["calibration_status"], "uncalibrated")
        self.assertTrue(contract["quality_contract"]["forward_evaluation_eligible"])
        self.assertIn("spätere Kurse oder revidierte Historien", contract["leakage_guard"]["forbidden_inputs"])
        self.assertEqual(len(record["snapshot_fingerprint"]), 64)

    def test_new_forecast_persists_an_immutable_verifiable_measurement_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "measurement.sqlite3"
            run = start_or_resume_run("2026-08-09", 1, database_path)
            forecast_id, inserted = record_forecast(
                run.run_id,
                measurement_snapshot(),
                database_path,
            )

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                stored = dict(
                    connection.execute(
                        "SELECT observation_cutoff_at, feature_schema_version, "
                        "feature_snapshot_json, measurement_contract_version, "
                        "measurement_contract_json, snapshot_fingerprint "
                        "FROM forecasts WHERE id = ?",
                        (forecast_id,),
                    ).fetchone()
                )

            valid, reasons = verify_measurement_record(stored)
            health = database_health(database_path)
            self.assertTrue(inserted)
            self.assertTrue(valid, reasons)
            self.assertEqual(health["measurement_contract_count"], 1)
            self.assertEqual(health["legacy_without_measurement_contract"], 0)

            stored["feature_snapshot_json"] = stored["feature_snapshot_json"].replace(
                '"price_eur":90.0', '"price_eur":999.0'
            )
            valid, reasons = verify_measurement_record(stored)
            self.assertFalse(valid)
            self.assertIn("snapshot_fingerprint_mismatch", reasons)

    def test_schema_five_preserves_legacy_forecasts_without_inventing_contract_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE forecasts (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, "
                    "model_type TEXT NOT NULL DEFAULT 'entry_analysis')"
                )
                connection.execute("INSERT INTO forecasts (ticker) VALUES ('LEGACY')")
                connection.execute("PRAGMA user_version = 4")
                connection.commit()

            initialize_database(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(forecasts)")
                }
                legacy = connection.execute(
                    "SELECT measurement_contract_version, snapshot_fingerprint "
                    "FROM forecasts WHERE ticker = 'LEGACY'"
                ).fetchone()

            self.assertEqual(version, CURRENT_SCHEMA_VERSION)
            self.assertIn("feature_snapshot_json", columns)
            self.assertEqual(legacy, (None, None))

    def test_database_audit_separates_legacy_valid_and_tampered_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "audit.sqlite3"
            first_run = start_or_resume_run("2026-08-09", 1, database_path)
            valid_id, _ = record_forecast(first_run.run_id, measurement_snapshot(), database_path)

            broken_snapshot = {
                **measurement_snapshot(),
                "run_date": "2026-08-10",
                "ticker": "BROKEN",
            }
            second_run = start_or_resume_run("2026-08-10", 1, database_path)
            broken_id, _ = record_forecast(second_run.run_id, broken_snapshot, database_path)

            legacy_snapshot = {
                **measurement_snapshot(),
                "run_date": "2026-08-11",
                "ticker": "LEGACY",
            }
            third_run = start_or_resume_run("2026-08-11", 1, database_path)
            legacy_id, _ = record_forecast(third_run.run_id, legacy_snapshot, database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE forecasts SET feature_snapshot_json = ? WHERE id = ?",
                    ('{"tampered":true}', broken_id),
                )
                connection.execute(
                    "UPDATE forecasts SET observation_cutoff_at = NULL, "
                    "feature_schema_version = NULL, feature_snapshot_json = NULL, "
                    "measurement_contract_version = NULL, measurement_contract_json = NULL, "
                    "snapshot_fingerprint = NULL WHERE id = ?",
                    (legacy_id,),
                )
                connection.commit()

            audit = measurement_contract_audit(database_path)
            health = database_health(database_path)

            self.assertEqual(valid_id, 1)
            self.assertEqual(audit["status"], "attention")
            self.assertEqual(audit["valid_records"], 1)
            self.assertEqual(audit["invalid_records"], 1)
            self.assertEqual(audit["legacy_records"], 1)
            self.assertEqual(audit["reason_counts"]["snapshot_fingerprint_mismatch"], 1)
            self.assertEqual(health["status"], "attention")


if __name__ == "__main__":
    unittest.main()
