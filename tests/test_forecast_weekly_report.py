from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

from forecast_sampling import build_weekly_cohort_plan, select_weekly_cohort
from forecast_store import FORECAST_LOGIC_VERSION, start_or_resume_run
from forecast_weekly_report import build_weekly_report, load_weekly_report, write_weekly_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ForecastWeeklyReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = build_weekly_cohort_plan(
            PROJECT_ROOT / "config" / "forecast_weekly_universe.csv",
            PROJECT_ROOT / "config" / "forecast_universe.csv",
            minimum_active_assets=1500,
        )

    def test_prestart_week_has_no_false_overdue_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "prestart.sqlite3"
            start_or_resume_run("2026-08-09", 0, database_path)

            report = build_weekly_report(
                self.plan,
                database_path,
                date(2026, 8, 9),
                schedule_start_date=date(2026, 8, 10),
            )

            self.assertEqual(report["coverage"]["overdue_cohorts"], [])
            self.assertEqual(report["coverage"]["successful_asset_coverage_pct"], 0.0)

    def test_report_marks_completed_and_overdue_cohorts_with_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "weekly.sqlite3"
            monday = select_weekly_cohort(
                self.plan,
                date(2026, 8, 10),
                schedule_start_date=date(2026, 8, 10),
            )
            run = start_or_resume_run(
                "2026-08-10",
                len(monday["assets"]),
                database_path,
                FORECAST_LOGIC_VERSION,
                sampling=monday["sampling"],
            )
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE forecast_runs SET status='completed_with_errors', "
                    "processed_count=325, success_count=320, failure_count=5, "
                    "rate_limit_failures=2, elapsed_seconds=800, database_growth_bytes=1234 "
                    "WHERE id=?",
                    (run.run_id,),
                )
                connection.commit()

            result = write_weekly_report(
                self.plan,
                database_path,
                root / "reports",
                date(2026, 8, 11),
                schedule_start_date=date(2026, 8, 10),
            )
            saved = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
            loaded = load_weekly_report(root / "reports", date(2026, 8, 11))

            self.assertEqual(result["write_status"], "ok")
            self.assertEqual(saved["coverage"]["completed_cohorts"], 1)
            self.assertEqual(saved["coverage"]["processed_assets"], 325)
            self.assertEqual(saved["coverage"]["successful_assets"], 320)
            self.assertEqual(saved["coverage"]["failed_assets"], 5)
            self.assertEqual(saved["operations"]["rate_limit_failures"], 2)
            self.assertEqual(saved["operations"]["database_growth_bytes"], 1234)
            self.assertEqual(saved["cohorts"][0]["status"], "completed")
            self.assertEqual(saved["cohorts"][0]["catch_up_days"], 0)
            self.assertEqual(saved["cohorts"][1]["status"], "due_missing")
            self.assertIn(
                "2026-W33-tuesday-extension",
                saved["coverage"]["overdue_cohorts"],
            )
            self.assertEqual(saved["evaluations"]["integrity"], "ok")
            self.assertFalse(saved["data_deleted"])
            self.assertEqual(loaded["iso_week"], "2026-W33")


if __name__ == "__main__":
    unittest.main()
