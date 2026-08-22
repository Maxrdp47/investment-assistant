from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

from forecast_sampling import WEEKDAY_LABELS, build_weekly_cohort_plan, select_weekly_cohort
from forecast_runner import run_daily_process
from forecast_store import (
    CURRENT_SCHEMA_VERSION,
    FORECAST_LOGIC_VERSION,
    recent_run_status,
    start_or_resume_run,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ForecastSamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = build_weekly_cohort_plan(
            PROJECT_ROOT / "config" / "forecast_weekly_universe.csv",
            PROJECT_ROOT / "config" / "forecast_universe.csv",
            minimum_active_assets=1500,
        )

    def test_production_plan_is_versioned_unique_and_covers_every_asset_once(self) -> None:
        assets = [
            item
            for weekday in WEEKDAY_LABELS
            for item in self.plan["cohorts"][weekday]
        ]
        tickers = [item["ticker"] for item in assets]

        self.assertEqual(self.plan["universe_count"], 1726)
        self.assertEqual(self.plan["reference_core_count"], 325)
        self.assertEqual(len(tickers), len(set(tickers)))
        self.assertEqual(len(tickers), self.plan["universe_count"])
        self.assertEqual(len(self.plan["assignment_fingerprint"]), 64)
        self.assertEqual(
            len(self.plan["cohorts"][0]),
            self.plan["reference_core_count"],
        )
        self.assertTrue(
            all(item["sampling_role"] == "reference_core" for item in self.plan["cohorts"][0])
        )
        for weekday in range(1, 5):
            self.assertTrue(self.plan["cohorts"][weekday])
            self.assertTrue(
                all(
                    item["sampling_role"] == "weekly_extension"
                    for item in self.plan["cohorts"][weekday]
                )
            )

    def test_selection_catches_up_without_backdating_and_then_becomes_evaluation_only(self) -> None:
        schedule_start = date(2026, 8, 10)
        before_start = select_weekly_cohort(
            self.plan,
            date(2026, 8, 9),
            schedule_start_date=schedule_start,
        )
        monday = select_weekly_cohort(
            self.plan,
            date(2026, 8, 10),
            schedule_start_date=schedule_start,
        )
        monday_id = monday["sampling"]["cohort_id"]
        tuesday_catchup = select_weekly_cohort(
            self.plan,
            date(2026, 8, 11),
            schedule_start_date=schedule_start,
        )
        tuesday = select_weekly_cohort(
            self.plan,
            date(2026, 8, 11),
            completed_cohort_ids={monday_id},
            schedule_start_date=schedule_start,
        )
        all_ids = {
            f"2026-W33-{label}" for label in WEEKDAY_LABELS.values()
        }
        finished_week = select_weekly_cohort(
            self.plan,
            date(2026, 8, 16),
            completed_cohort_ids=all_ids,
            schedule_start_date=schedule_start,
        )

        self.assertEqual(before_start["sampling"]["mode"], "evaluation_only")
        self.assertEqual(monday["sampling"]["cohort_weekday"], 0)
        self.assertEqual(tuesday_catchup["sampling"]["cohort_weekday"], 0)
        self.assertEqual(tuesday["sampling"]["cohort_weekday"], 1)
        self.assertEqual(finished_week["sampling"]["mode"], "evaluation_only")
        self.assertEqual(finished_week["assets"], [])

    def test_run_keeps_one_sampling_contract_and_rejects_silent_cohort_mix(self) -> None:
        sampling = {
            "mode": "weekly_cohort",
            "iso_week": "2026-W33",
            "cohort_id": "2026-W33-monday-reference-core",
            "cohort_weekday": 0,
        }
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sampling.sqlite3"
            run = start_or_resume_run(
                "2026-08-10",
                325,
                database_path,
                FORECAST_LOGIC_VERSION,
                sampling=sampling,
            )
            with closing(sqlite3.connect(database_path)) as connection:
                stored = connection.execute(
                    "SELECT sampling_json FROM forecast_runs WHERE id = ?",
                    (run.run_id,),
                ).fetchone()[0]

            self.assertEqual(json.loads(stored), sampling)
            with self.assertRaisesRegex(RuntimeError, "nicht still vermischt"):
                start_or_resume_run(
                    "2026-08-10",
                    400,
                    database_path,
                    FORECAST_LOGIC_VERSION,
                    sampling={**sampling, "cohort_weekday": 1},
                )

    def test_daily_process_before_schedule_start_evaluates_without_collecting_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            database_path = root / "forecasts.sqlite3"
            settings_path.write_text(
                json.dumps(
                    {
                        "database_path": str(database_path),
                        "log_path": str(root / "forecast.log"),
                        "calibration_path": str(root / "calibration.json"),
                        "universe_path": str(PROJECT_ROOT / "config" / "forecast_universe.csv"),
                        "reference_universe_path": str(
                            PROJECT_ROOT / "config" / "forecast_universe.csv"
                        ),
                        "weekly_universe_path": str(
                            PROJECT_ROOT / "config" / "forecast_weekly_universe.csv"
                        ),
                        "weekly_minimum_assets": 1500,
                        "weekly_schedule_start_date": "2026-08-10",
                        "weekly_report_directory": str(root / "weekly-reports"),
                        "request_delay_seconds": 0,
                        "batch_pause_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )

            result = run_daily_process(
                settings_path,
                run_date="2026-08-09",
                no_delay=True,
            )

            self.assertEqual(result["sampling"]["mode"], "evaluation_only")
            self.assertEqual(result["collection"]["processed"], 0)
            self.assertEqual(result["evaluation"]["due"], 0)
            self.assertEqual(result["maintenance"]["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertEqual(recent_run_status(database_path)["sampling"]["mode"], "evaluation_only")


if __name__ == "__main__":
    unittest.main()
