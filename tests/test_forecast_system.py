from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app import forecast_status_messages
from forecast_runner import (
    _histories_from_batch,
    collect_forecasts,
    evaluation_market_data_from_history,
    evaluate_due_forecasts,
    is_rate_limit_error,
    load_universe,
    operational_run_metrics,
    run_daily_process,
    runtime_preflight,
)
from forecast_store import (
    CURRENT_SCHEMA_VERSION,
    FORECAST_LOGIC_VERSION,
    FORECAST_MODEL_ENTRY,
    database_health,
    forecast_operational_status,
    forecast_quality_rows,
    forecast_summary,
    initialize_database,
    latest_horizon_start_dates,
    maintain_database,
    measurement_contract_audit,
    recent_run_status,
    record_evaluation,
    record_forecast,
    start_or_resume_run,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fake_snapshot(asset: dict, run_date: str, logic_version: str, created_at: str | None = None) -> dict:
    ticker = asset["ticker"]
    return {
        "run_date": run_date,
        "created_at": created_at or datetime.now().astimezone().isoformat(),
        "ticker": ticker,
        "asset_name": asset.get("name") or ticker,
        "asset_type": asset.get("asset_type") or "Aktie",
        "region": asset.get("region") or "Test",
        "category": asset.get("category") or "Test",
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
        "data_coverage": "Isolierte Testdaten",
        "uncertainties": ["Testunsicherheit"],
        "scenarios": [{"Szenario": "Base-Case"}],
        "professional_decision": {"Titel": "Beobachten"},
        "signal_snapshot": {"MACD": "positiv"},
        "simple_trend_baseline": {
            "status": "available",
            "predicted_direction": "Steigend",
            "lookback_trading_days": 20,
        },
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
                "expected_high_eur": 115.0,
                "target_eur": 110.0,
                "risk_eur": 90.0,
                "probability_up": 0.6,
                "probability_schema_version": "raw-up-scenario-mixture-2026.08.09-v1",
            }
        ],
        "model_type": FORECAST_MODEL_ENTRY,
        "logic_version": logic_version,
        "source": "test",
    }


class ForecastSystemTests(unittest.TestCase):
    def test_collection_runner_starts_only_due_horizons_and_preserves_prior_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "horizon-runner.sqlite3"

            def all_horizon_snapshot(asset: dict, run_date: str, logic_version: str) -> dict:
                result = fake_snapshot(asset, run_date, logic_version)
                result["history_rows"] = 1_500
                template = dict(result["horizons"][0])
                result["horizons"] = [
                    {**template, "horizon": horizon, "days": days}
                    for horizon, days in {
                        "1w": 7,
                        "1m": 30,
                        "3m": 90,
                        "6m": 180,
                        "12m": 365,
                    }.items()
                ]
                return result

            first = collect_forecasts(
                [{"ticker": "CADENCE"}],
                database_path=database_path,
                run_date="2026-08-10",
                snapshot_builder=all_horizon_snapshot,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )
            second = collect_forecasts(
                [{"ticker": "CADENCE"}],
                database_path=database_path,
                run_date="2026-08-17",
                snapshot_builder=all_horizon_snapshot,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )

            self.assertEqual(first["succeeded"], 1)
            self.assertEqual(second["succeeded"], 1)
            with closing(sqlite3.connect(database_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT f.run_date, GROUP_CONCAT(h.horizon, ',')
                    FROM forecasts f
                    JOIN forecast_horizons h ON h.forecast_id = f.id
                    GROUP BY f.run_date
                    ORDER BY f.run_date
                    """
                ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(set(rows[0][1].split(",")), {"1w", "1m", "3m", "6m", "12m"})
            self.assertEqual(rows[1], ("2026-08-17", "1w"))

    def test_latest_horizon_dates_are_read_without_changing_old_forecasts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "horizon-dates.sqlite3"
            run = start_or_resume_run("2026-08-10", 1, database_path)
            original = fake_snapshot(
                {"ticker": "DATES"},
                "2026-08-10",
                FORECAST_LOGIC_VERSION,
            )
            record_forecast(run.run_id, original, database_path)

            assert latest_horizon_start_dates("dates", database_path) == {
                "1w": date(2026, 8, 10)
            }
            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM forecast_horizons").fetchone()[0], 1)

    def test_operational_metrics_make_large_run_observable(self) -> None:
        metrics = operational_run_metrics(
            {
                "processed": 10,
                "failed": 2,
                "rate_limit_failures": 1,
            },
            elapsed_seconds=120,
            database_bytes_before=1000,
            maintenance={"database_bytes": 1600, "schema_version": 2, "status": "ok"},
        )

        self.assertEqual(metrics["processed_per_minute"], 5.0)
        self.assertEqual(metrics["failure_rate_pct"], 20.0)
        self.assertEqual(metrics["rate_limit_failures"], 1)
        self.assertEqual(metrics["database_growth_bytes"], 600)
        self.assertEqual(metrics["database_status"], "ok")
        self.assertTrue(is_rate_limit_error("HTTP 429: Too Many Requests"))
        self.assertFalse(is_rate_limit_error("Keine Kursdaten verfügbar"))

    def test_daily_process_metrics_are_persisted_for_status_view(self) -> None:
        from forecast_store import record_run_operations

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "operations.sqlite3"
            run = start_or_resume_run("2026-08-02", 325, database_path)
            metrics = operational_run_metrics(
                {"processed": 10, "failed": 2, "rate_limit_failures": 1},
                elapsed_seconds=120,
                database_bytes_before=1000,
                maintenance={"database_bytes": 1600, "schema_version": 3, "status": "ok"},
            )

            record_run_operations(run.run_id, metrics, database_path)
            stored = recent_run_status(database_path)

            self.assertEqual(stored["elapsed_seconds"], 120.0)
            self.assertEqual(stored["processed_per_minute"], 5.0)
            self.assertEqual(stored["rate_limit_failures"], 1)
            self.assertEqual(stored["database_growth_bytes"], 600)

    def test_batch_histories_supports_both_yfinance_column_orders(self) -> None:
        index = pd.to_datetime(["2026-08-07", "2026-08-10"])
        ticker_first = pd.DataFrame(
            [[100.0, 103.0], [105.0, 108.0]],
            index=index,
            columns=pd.MultiIndex.from_tuples(
                [("AAA", "Close"), ("AAA", "High")]
            ),
        )
        field_first = pd.DataFrame(
            [[200.0, 198.0], [205.0, 201.0]],
            index=index,
            columns=pd.MultiIndex.from_tuples(
                [("Close", "BBB"), ("Low", "BBB")]
            ),
        )

        first = _histories_from_batch(ticker_first, ["AAA", "MISSING"])
        second = _histories_from_batch(field_first, ["BBB"])

        self.assertEqual(list(first), ["AAA"])
        self.assertEqual(first["AAA"]["Close"].tolist(), [100.0, 105.0])
        self.assertEqual(second["BBB"]["Close"].tolist(), [200.0, 205.0])

    def test_evaluation_history_uses_first_close_after_due_date_and_shared_fx_cache(self) -> None:
        item = {
            "created_at": "2026-08-01T22:30:00+02:00",
            "days": 7,
            "original_currency": "USD",
            "fx_rate_to_eur": 0.85,
        }
        history = pd.DataFrame(
            {
                "Close": [100.0, 110.0, 112.0],
                "High": [102.0, 115.0, 114.0],
                "Low": [98.0, 95.0, 109.0],
            },
            index=pd.to_datetime(["2026-08-07", "2026-08-10", "2026-08-11"]),
        )
        calls: list[tuple[str, date, float | None]] = []

        def fx_loader(currency: str, target_day: date, fallback: float | None) -> float:
            calls.append((currency, target_day, fallback))
            return 0.9

        cache: dict[tuple[str, date], float | None] = {}
        first = evaluation_market_data_from_history(
            item,
            history,
            fx_cache=cache,
            fx_loader=fx_loader,
        )
        second = evaluation_market_data_from_history(
            item,
            history,
            fx_cache=cache,
            fx_loader=fx_loader,
        )

        self.assertEqual(first["actual_day"], "2026-08-10")
        self.assertEqual(first["actual_price_eur"], 99.0)
        self.assertEqual(first["max_price_eur"], 103.5)
        self.assertEqual(first["min_price_eur"], 85.5)
        self.assertEqual(second, first)
        self.assertEqual(len(calls), 1)

    def test_schema_version_and_non_destructive_maintenance_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "maintenance.sqlite3"
            initialize_database(database_path)

            health = database_health(database_path)
            maintenance = maintain_database(database_path)
            compacted = maintain_database(database_path, compact=True)
            with closing(sqlite3.connect(database_path)) as connection:
                horizon_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(forecast_horizons)")
                }

            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertEqual(maintenance["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertFalse(maintenance["compacted"])
            self.assertFalse(maintenance["data_deleted"])
            self.assertIn("checkpointed_pages", maintenance["checkpoint"])
            self.assertTrue(compacted["compacted"])
            self.assertFalse(compacted["data_deleted"])
            self.assertIn("probability_up", horizon_columns)
            self.assertIn("probability_schema_version", horizon_columns)

    def test_schema_migration_preserves_existing_run_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "migration.sqlite3"
            run = start_or_resume_run("2026-08-01", 1, database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute("DROP TABLE forecast_evaluation_attempts")
                connection.execute("PRAGMA user_version = 1")
                connection.commit()

            initialize_database(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                run_count = int(connection.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0])
                attempts_table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'forecast_evaluation_attempts'"
                ).fetchone()
            self.assertEqual(version, CURRENT_SCHEMA_VERSION)
            self.assertEqual(run_count, 1)
            self.assertEqual(run.run_id, 1)
            self.assertIsNotNone(attempts_table)

    def test_newer_schema_is_rejected_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "future.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "neueren App-Version"):
                initialize_database(database_path)

    def test_schema_four_adds_explicit_model_type_without_changing_existing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "model-migration.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE forecasts (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL)"
                )
                connection.execute("INSERT INTO forecasts (ticker) VALUES ('LEGACY')")
                connection.execute("PRAGMA user_version = 3")
                connection.commit()

            initialize_database(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(forecasts)")
                }
                legacy_model = connection.execute(
                    "SELECT model_type FROM forecasts WHERE ticker = 'LEGACY'"
                ).fetchone()[0]
                model_index = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'index' "
                    "AND name = 'idx_forecasts_model_type'"
                ).fetchone()

            self.assertEqual(version, CURRENT_SCHEMA_VERSION)
            self.assertIn("model_type", columns)
            self.assertEqual(legacy_model, FORECAST_MODEL_ENTRY)
            self.assertIsNotNone(model_index)

    def test_curated_universe_is_unique_large_and_contains_servicenow(self) -> None:
        assets = load_universe(PROJECT_ROOT / "config" / "forecast_universe.csv")
        tickers = {asset["ticker"] for asset in assets}
        self.assertGreaterEqual(len(assets), 250)
        self.assertEqual(len(assets), len(tickers))
        self.assertIn("NOW", tickers)
        self.assertIn("BNY", tickers)
        self.assertIn("ROP.SW", tickers)
        self.assertNotIn("BK", tickers)
        self.assertNotIn("ROG.SW", tickers)
        self.assertTrue({"Aktie", "ETF", "Krypto"}.issubset({asset["asset_type"] for asset in assets}))

    def test_windows_wrapper_records_process_boundary_and_preserves_exit_code(self) -> None:
        wrapper = (PROJECT_ROOT / "scripts" / "run_forecasts.cmd").read_text(encoding="utf-8")

        self.assertIn("forecast_task_wrapper.log", wrapper)
        self.assertIn("START", wrapper)
        self.assertIn("ENDE exit=%forecast_exit%", wrapper)
        self.assertIn("2>&1", wrapper)
        self.assertIn("%*", wrapper)
        self.assertIn("exit /b %forecast_exit%", wrapper)

    def test_universe_without_usable_ticker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            universe_path = Path(directory) / "empty-universe.csv"
            universe_path.write_text(
                "ticker,asset_type,name,region,category,version\n,,,,,\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "keine verwendbaren Ticker"):
                load_universe(universe_path)

    def test_startup_failure_is_written_to_the_runner_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe_path = root / "invalid-universe.csv"
            settings_path = root / "settings.json"
            log_path = root / "logs" / "forecast.log"
            universe_path.write_text("ticker,name\nTEST,Test\n", encoding="utf-8")
            settings_path.write_text(
                json.dumps(
                    {
                        "database_path": str(root / "forecasts.sqlite3"),
                        "log_path": str(log_path),
                        "calibration_path": str(root / "calibration.json"),
                        "universe_path": str(universe_path),
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "erforderlichen Spalten"):
                run_daily_process(settings_path, no_delay=True)

            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("Startvorprüfung", log_text)
            self.assertIn("Täglicher Prognoselauf vor Abschluss beendet", log_text)
            self.assertIn("ValueError", log_text)

    def test_runtime_preflight_checks_paths_and_database_without_forecasts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe_path = root / "universe.csv"
            settings_path = root / "settings.json"
            database_path = root / "runtime" / "forecasts.sqlite3"
            universe_path.write_text(
                "ticker,asset_type,name,region,category,version\n"
                "TEST,Aktie,Test,Test,Test,1\n",
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "local_run_time": "22:30",
                        "database_path": str(database_path),
                        "log_path": str(root / "runtime" / "logs" / "forecast.log"),
                        "calibration_path": str(root / "runtime" / "calibration.json"),
                        "universe_path": str(universe_path),
                    }
                ),
                encoding="utf-8",
            )

            result = runtime_preflight(settings_path)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["universe"]["count"], 1)
            self.assertEqual(result["database"]["quick_check"], "ok")
            self.assertFalse(result["market_data_requested"])
            self.assertFalse(result["forecasts_written"])
            self.assertFalse(result["data_deleted"])
            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0], 0)

    def test_runtime_preflight_rejects_invalid_settings_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "invalid-settings.json"
            settings_path.write_text("{not valid json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "nicht lesbar"):
                runtime_preflight(settings_path)

    def test_daily_process_stops_before_market_work_when_measurement_audit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe_path = root / "universe.csv"
            settings_path = root / "settings.json"
            database_path = root / "forecasts.sqlite3"
            universe_path.write_text(
                "ticker,asset_type,name,region,category,version\n"
                "TEST,Aktie,Test,USA,Test,1\n",
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "database_path": str(database_path),
                        "log_path": str(root / "forecast.log"),
                        "calibration_path": str(root / "calibration.json"),
                        "universe_path": str(universe_path),
                    }
                ),
                encoding="utf-8",
            )
            run = start_or_resume_run("2026-08-08", 1, database_path)
            forecast_id, _ = record_forecast(
                run.run_id,
                fake_snapshot(
                    {"ticker": "TEST"},
                    "2026-08-08",
                    FORECAST_LOGIC_VERSION,
                ),
                database_path,
            )
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE forecasts SET snapshot_fingerprint = 'tampered' WHERE id = ?",
                    (forecast_id,),
                )
                connection.commit()

            self.assertEqual(measurement_contract_audit(database_path)["status"], "attention")
            with patch("forecast_runner.evaluate_due_forecasts") as evaluate_mock, patch(
                "forecast_runner.collect_forecasts"
            ) as collect_mock:
                with self.assertRaisesRegex(RuntimeError, "Messvertraege"):
                    run_daily_process(settings_path, run_date="2026-08-09", no_delay=True)
            evaluate_mock.assert_not_called()
            collect_mock.assert_not_called()

    def test_daily_process_pauses_collection_when_all_market_benchmarks_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe_path = root / "universe.csv"
            settings_path = root / "settings.json"
            database_path = root / "forecasts.sqlite3"
            universe_path.write_text(
                "ticker,asset_type,name,region,category,version\n"
                "TEST,Aktie,Test,USA,Test,1\n",
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "database_path": str(database_path),
                        "log_path": str(root / "forecast.log"),
                        "calibration_path": str(root / "calibration.json"),
                        "universe_path": str(universe_path),
                        "request_delay_seconds": 0,
                        "batch_pause_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "forecast_runner.evaluate_due_forecasts",
                return_value={"due": 0, "evaluated": 0, "failed": 0, "rate_limit_failures": 0},
            ), patch(
                "forecast_runner.prepare_market_benchmark_snapshots",
                return_value={"TEST": {"status": "missing"}},
            ), patch("forecast_runner.collect_forecasts") as collect_mock:
                with self.assertRaisesRegex(RuntimeError, "Neuprognose"):
                    run_daily_process(settings_path, run_date="2026-08-10", no_delay=True)

            collect_mock.assert_not_called()
            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0],
                    0,
                )

    def test_empty_database_quality_view_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "empty.sqlite3"
            initialize_database(database_path)
            self.assertEqual(forecast_summary(database_path)["evaluated"], 0)
            self.assertEqual(forecast_quality_rows(database_path), ([], 0))

    def test_operational_status_detects_stale_unfinished_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "stale.sqlite3"
            run = start_or_resume_run("2026-08-01", 325, database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE forecast_runs SET started_at = ? WHERE id = ?",
                    ("2026-08-01T22:30:00+00:00", run.run_id),
                )
                connection.commit()

            status = forecast_operational_status(
                database_path,
                now=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
                scheduled_time="22:30",
            )

            self.assertEqual(status["state"], "stale")
            self.assertEqual(status["severity"], "error")
            self.assertTrue(status["stale"])
            self.assertIn("ohne neue Aktivität", status["message"])

    def test_new_day_marks_older_running_run_as_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "abandoned.sqlite3"
            old_run = start_or_resume_run("2026-08-01", 325, database_path)

            start_or_resume_run("2026-08-02", 325, database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                old_status = connection.execute(
                    "SELECT status, finished_at, message FROM forecast_runs WHERE id = ?",
                    (old_run.run_id,),
                ).fetchone()
            self.assertEqual(old_status[0], "interrupted")
            self.assertIsNotNone(old_status[1])
            self.assertIn("automatisch", old_status[2])

    def test_operational_status_reports_completed_run_and_next_time(self) -> None:
        assets = [{"ticker": "OK", "name": "OK", "asset_type": "Aktie"}]
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "healthy.sqlite3"
            collect_forecasts(
                assets,
                database_path,
                run_date="2026-08-02",
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )

            status = forecast_operational_status(
                database_path,
                now=datetime(2026, 8, 2, 23, 0, tzinfo=timezone.utc),
                scheduled_time="22:30",
            )

            self.assertEqual(status["state"], "healthy")
            self.assertEqual(status["last_run"]["success_count"], 1)
            self.assertTrue(status["next_run_at"].startswith("2026-08-03T22:30"))

    def test_operational_status_treats_one_missed_run_as_warning(self) -> None:
        assets = [{"ticker": "OK", "name": "OK", "asset_type": "Aktie"}]
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "missed.sqlite3"
            collect_forecasts(
                assets,
                database_path,
                run_date="2026-08-05",
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )

            status = forecast_operational_status(
                database_path,
                now=datetime(2026, 8, 7, 21, 0, tzinfo=timezone.utc),
                scheduled_time="22:30",
            )

            self.assertEqual(status["state"], "overdue")
            self.assertEqual(status["severity"], "warning")
            self.assertIn("2026-08-06", status["message"])

    def test_interrupted_run_resumes_and_same_day_run_is_deduplicated(self) -> None:
        assets = [
            {"ticker": "AAA", "name": "A", "asset_type": "Aktie"},
            {"ticker": "BBB", "name": "B", "asset_type": "ETF"},
            {"ticker": "CCC", "name": "C", "asset_type": "Krypto"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "resume.sqlite3"
            first = collect_forecasts(
                assets,
                database_path,
                run_date="2026-07-31",
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
                interrupt_after=1,
            )
            self.assertEqual(first["status"], "interrupted")
            second = collect_forecasts(
                assets,
                database_path,
                run_date="2026-07-31",
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )
            self.assertTrue(second["resumed"])
            self.assertEqual(second["status"], "completed")
            self.assertEqual(second["succeeded"], 2)
            third = collect_forecasts(
                assets,
                database_path,
                run_date="2026-07-31",
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )
            self.assertEqual(third["status"], "skipped_same_day")

    def test_asset_attempt_is_logged_before_snapshot_work_starts(self) -> None:
        assets = [{"ticker": "FIRST", "name": "First", "asset_type": "Aktie"}]

        def hard_interrupt(_: dict, __: str, ___: str) -> dict:
            raise KeyboardInterrupt("simulierter harter Abbruch")

        logger = logging.getLogger("test.forecast.asset_progress")
        with tempfile.TemporaryDirectory() as directory, self.assertLogs(logger, level="INFO") as captured:
            result = collect_forecasts(
                assets,
                Path(directory) / "progress.sqlite3",
                run_date="2026-08-02",
                snapshot_builder=hard_interrupt,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
                logger=logger,
            )

        self.assertEqual(result["status"], "interrupted")
        log_text = "\n".join(captured.output)
        self.assertIn("Asset-Versuch gestartet", log_text)
        self.assertIn("ticker=FIRST", log_text)
        self.assertIn("position=1/1", log_text)
        self.assertIn("Lauf unterbrochen", log_text)

    def test_completed_day_never_overwrites_or_mixes_logic_versions(self) -> None:
        assets = [{"ticker": "SAFE", "name": "Safe", "asset_type": "Aktie"}]
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "version-integrity.sqlite3"
            first = collect_forecasts(
                assets,
                database_path,
                run_date="2026-08-02",
                logic_version=FORECAST_LOGIC_VERSION,
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )
            self.assertEqual(first["status"], "completed")

            with self.assertRaisesRegex(RuntimeError, "nicht in einem Lauf vermischt"):
                collect_forecasts(
                    assets,
                    database_path,
                    run_date="2026-08-02",
                    logic_version="2026.08.02-v2",
                    snapshot_builder=fake_snapshot,
                    max_retries=0,
                    request_delay_seconds=0,
                    batch_pause_seconds=0,
                    force=True,
                )

            same_version = collect_forecasts(
                assets,
                database_path,
                run_date="2026-08-02",
                logic_version=FORECAST_LOGIC_VERSION,
                snapshot_builder=fake_snapshot,
                max_retries=0,
                request_delay_seconds=0,
                batch_pause_seconds=0,
                force=True,
            )
            with closing(sqlite3.connect(database_path)) as connection:
                run_row = connection.execute(
                    "SELECT logic_version FROM forecast_runs WHERE run_date = '2026-08-02'"
                ).fetchone()
                forecast_count = int(connection.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0])

            self.assertEqual(same_version["status"], "skipped_same_day")
            self.assertEqual(run_row[0], FORECAST_LOGIC_VERSION)
            self.assertEqual(forecast_count, 1)

    def test_one_asset_failure_does_not_abort_the_batch(self) -> None:
        assets = [{"ticker": "GOOD"}, {"ticker": "BAD"}]

        def builder(asset: dict, run_date: str, logic_version: str) -> dict:
            if asset["ticker"] == "BAD":
                raise RuntimeError("simulierter Datenfehler")
            return fake_snapshot(asset, run_date, logic_version)

        with tempfile.TemporaryDirectory() as directory:
            result = collect_forecasts(
                assets,
                Path(directory) / "failure.sqlite3",
                run_date="2026-07-30",
                snapshot_builder=builder,
                max_retries=1,
                request_delay_seconds=0,
                batch_pause_seconds=0,
            )
            self.assertEqual(result["status"], "completed_with_errors")
            self.assertEqual(result["succeeded"], 1)
            self.assertEqual(result["failed"], 1)

    def test_due_forecast_is_evaluated_and_counted_by_direction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "evaluation.sqlite3"
            run_date = (date.today() - timedelta(days=10)).isoformat()
            run = start_or_resume_run(run_date, 1, database_path)
            created_at = (datetime.now().astimezone() - timedelta(days=10)).isoformat()
            record_forecast(
                run.run_id,
                fake_snapshot({"ticker": "TEST"}, run_date, FORECAST_LOGIC_VERSION, created_at),
                database_path,
            )

            result = evaluate_due_forecasts(
                database_path,
                as_of=date.today(),
                market_data_loader=lambda _: {
                    "actual_price_original": 108.0,
                    "actual_price_eur": 108.0,
                    "max_price_eur": 112.0,
                    "min_price_eur": 97.0,
                    "actual_day": date.today().isoformat(),
                    "market_benchmark_ticker": "SPY",
                    "market_benchmark_return_pct": 3.0,
                    "data_quality": "Gut",
                },
            )
            self.assertEqual(
                result,
                {"due": 1, "evaluated": 1, "failed": 0, "rate_limit_failures": 0},
            )
            summary = forecast_summary(database_path)
            self.assertEqual(summary["evaluated"], 1)
            self.assertEqual(summary["hit_rate"], 100.0)
            self.assertEqual(summary["outcome_count"], 1)
            self.assertEqual(summary["evaluation_coverage_pct"], 100.0)
            self.assertEqual(summary["always_up_hit_rate"], 100.0)
            self.assertEqual(summary["no_change_hit_rate"], 0.0)
            self.assertEqual(summary["average_return_pct"], 8.0)
            self.assertEqual(summary["average_max_return_pct"], 12.0)
            self.assertEqual(summary["average_drawdown_pct"], -3.0)
            self.assertEqual(summary["model_advantage_vs_always_up_pct"], 0.0)
            self.assertEqual(summary["simple_trend_hit_rate"], 100.0)
            self.assertEqual(summary["model_advantage_vs_simple_trend_pct"], 0.0)
            self.assertEqual(summary["average_market_benchmark_return_pct"], 3.0)
            self.assertEqual(summary["average_excess_return_pct"], 5.0)
            self.assertEqual(summary["by_region"][0]["label"], "Test")
            self.assertEqual(summary["by_market_phase"][0]["label"], "Bullenmarkt")
            self.assertEqual(summary["by_data_quality"][0]["label"], "Gut")
            self.assertEqual(summary["by_logic_version"][0]["label"], FORECAST_LOGIC_VERSION)
            self.assertEqual(summary["up_precision_pct"], 100.0)
            self.assertEqual(summary["up_recall_pct"], 100.0)
            self.assertIsNone(summary["balanced_accuracy_pct"])
            self.assertEqual(summary["hit_rate_ci_low_pct"], 20.7)
            self.assertEqual(summary["hit_rate_ci_high_pct"], 100.0)
            self.assertEqual(summary["by_model"][0]["label"], "Einstiegsanalyse")
            rows, total = forecast_quality_rows(
                database_path,
                search="test",
                asset_type="Aktie",
                model_type=FORECAST_MODEL_ENTRY,
                horizon="1w",
                result_status="Treffer",
            )
            self.assertEqual(total, 1)
            self.assertEqual(rows[0]["Modell"], "Einstiegsanalyse")
            self.assertEqual(rows[0]["Ergebnis"], "Treffer")
            self.assertEqual(rows[0]["Status"], "ausgewertet")
            self.assertEqual(rows[0]["Bewertungstag"], date.today().isoformat())
            self.assertEqual(rows[0]["Beste Bewegung (%)"], 12.0)
            self.assertEqual(rows[0]["Schlechteste Bewegung (%)"], -3.0)
            self.assertEqual(rows[0]["Marktbenchmark"], "SPY")
            self.assertEqual(rows[0]["Überschussrendite (%)"], 5.0)

    def test_due_forecasts_use_one_prepared_batch_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "batch-evaluation.sqlite3"
            run_date = (date.today() - timedelta(days=10)).isoformat()
            run = start_or_resume_run(run_date, 1, database_path)
            created_at = (datetime.now().astimezone() - timedelta(days=10)).isoformat()
            forecast_id, _ = record_forecast(
                run.run_id,
                fake_snapshot({"ticker": "BATCH"}, run_date, FORECAST_LOGIC_VERSION, created_at),
                database_path,
            )
            prepared = {
                (forecast_id, "1w"): {
                    "actual_price_original": 107.0,
                    "actual_price_eur": 107.0,
                    "max_price_eur": 111.0,
                    "min_price_eur": 98.0,
                    "data_quality": "Gut",
                }
            }

            with patch(
                "forecast_runner.default_evaluation_market_data_batch",
                return_value=(prepared, {}),
            ) as batch_loader:
                result = evaluate_due_forecasts(database_path, as_of=date.today())

            self.assertEqual(
                result,
                {"due": 1, "evaluated": 1, "failed": 0, "rate_limit_failures": 0},
            )
            batch_loader.assert_called_once()

    def test_different_models_are_never_combined_into_one_hit_rate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "model-separation.sqlite3"
            run = start_or_resume_run("2026-06-01", 2, database_path)
            entry_snapshot = fake_snapshot({"ticker": "ENTRY"}, "2026-06-01", FORECAST_LOGIC_VERSION)
            swing_snapshot = fake_snapshot({"ticker": "SWING"}, "2026-06-01", FORECAST_LOGIC_VERSION)
            swing_snapshot["model_type"] = "swing_trade"
            entry_id, _ = record_forecast(run.run_id, entry_snapshot, database_path)
            swing_id, _ = record_forecast(run.run_id, swing_snapshot, database_path)

            for forecast_id, hit in [(entry_id, 1), (swing_id, 0)]:
                record_evaluation(
                    {
                        "forecast_id": forecast_id,
                        "horizon": "1w",
                        "evaluated_at": datetime.now().astimezone().isoformat(),
                        "actual_return_pct": 3.0 if hit else -3.0,
                        "direction_hit": hit,
                        "data_quality": "Gut",
                    },
                    database_path,
                )

            summary = forecast_summary(database_path)

            self.assertEqual(summary["evaluated"], 2)
            self.assertEqual(summary["evaluated_model_count"], 2)
            self.assertTrue(summary["mixed_models"])
            self.assertIsNone(summary["hit_rate"])
            self.assertEqual(
                {row["label"] for row in summary["by_model"]},
                {"Einstiegsanalyse", "Swing Trade Finder"},
            )

    def test_balanced_accuracy_and_up_precision_use_all_four_binary_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "classification.sqlite3"
            run = start_or_resume_run("2026-06-01", 4, database_path)
            cases = [
                ("TP", "Steigend", 5.0, 1),
                ("FP", "Steigend", -5.0, 0),
                ("FN", "Fallend", 5.0, 0),
                ("TN", "Fallend", -5.0, 1),
            ]
            for ticker, predicted_direction, actual_return, hit in cases:
                snapshot = fake_snapshot(
                    {"ticker": ticker},
                    "2026-06-01",
                    FORECAST_LOGIC_VERSION,
                )
                snapshot["predicted_direction"] = predicted_direction
                snapshot["horizons"][0]["expected_direction"] = predicted_direction
                forecast_id, _ = record_forecast(run.run_id, snapshot, database_path)
                record_evaluation(
                    {
                        "forecast_id": forecast_id,
                        "horizon": "1w",
                        "evaluated_at": datetime.now().astimezone().isoformat(),
                        "actual_return_pct": actual_return,
                        "direction_hit": hit,
                        "data_quality": "Gut",
                    },
                    database_path,
                )

            summary = forecast_summary(database_path)

            self.assertEqual(summary["hit_rate"], 50.0)
            self.assertEqual(summary["up_precision_pct"], 50.0)
            self.assertEqual(summary["up_recall_pct"], 50.0)
            self.assertEqual(summary["up_specificity_pct"], 50.0)
            self.assertEqual(summary["balanced_accuracy_pct"], 50.0)
            self.assertEqual(summary["confusion"], {"tp": 1, "fp": 1, "fn": 1, "tn": 1})
            self.assertEqual(summary["probability_evaluated"], 4)
            self.assertEqual(summary["brier_score"], 0.26)
            self.assertEqual(summary["log_loss"], 0.7136)
            self.assertEqual(summary["calibration_error_pct"], 10.0)

    def test_open_forecast_explains_that_it_is_not_due_yet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "not-due.sqlite3"
            run_date = date.today().isoformat()
            run = start_or_resume_run(run_date, 1, database_path)
            record_forecast(
                run.run_id,
                fake_snapshot({"ticker": "OPEN"}, run_date, FORECAST_LOGIC_VERSION),
                database_path,
            )

            summary = forecast_summary(database_path)
            messages = forecast_status_messages(summary, {"run_date": run_date})

            self.assertEqual(summary["open"], 1)
            self.assertEqual(summary["due"], 0)
            self.assertIsNotNone(summary["next_due_date"])
            self.assertTrue(any("Prognosezeiträume noch offen" in message for message in messages))
            self.assertTrue(any("noch nicht fällig" in message for message in messages))
            self.assertTrue(any("Auswertung möglich ab" in message for message in messages))

    def test_failed_due_evaluation_reports_missing_market_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "market-data-missing.sqlite3"
            run_date = (date.today() - timedelta(days=10)).isoformat()
            run = start_or_resume_run(run_date, 1, database_path)
            created_at = (datetime.now().astimezone() - timedelta(days=10)).isoformat()
            record_forecast(
                run.run_id,
                fake_snapshot({"ticker": "MISSING"}, run_date, FORECAST_LOGIC_VERSION, created_at),
                database_path,
            )

            def missing_market_data(_: dict) -> dict:
                raise RuntimeError("Keine Kursdaten für die fällige Auswertung verfügbar")

            result = evaluate_due_forecasts(
                database_path,
                as_of=date.today(),
                market_data_loader=missing_market_data,
            )
            summary = forecast_summary(database_path)
            messages = forecast_status_messages(summary, {"run_date": run_date})

            self.assertEqual(
                result,
                {"due": 1, "evaluated": 0, "failed": 1, "rate_limit_failures": 0},
            )
            self.assertEqual(summary["due"], 1)
            self.assertEqual(summary["missing_market_data"], 1)
            self.assertTrue(any("fehlender verwertbarer Marktdaten" in message for message in messages))

    def test_empty_status_distinguishes_missing_background_run(self) -> None:
        messages = forecast_status_messages(forecast_summary(Path("does-not-exist.sqlite3")), None)

        self.assertEqual(messages[0], "Noch keine Prognosen vorhanden.")
        self.assertTrue(any("noch nicht aktiv" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
