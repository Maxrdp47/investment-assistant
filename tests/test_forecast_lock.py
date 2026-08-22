from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from forecast_lock import ForecastRunAlreadyActiveError, ForecastRunLock, lock_path_for_database
from forecast_runner import run_daily_process


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ForecastRunLockTests(unittest.TestCase):
    def test_lock_blocks_another_process_and_is_reusable_after_release(self) -> None:
        child_script = (
            "import sys\n"
            "from pathlib import Path\n"
            "from forecast_lock import ForecastRunLock\n"
            "lock = ForecastRunLock(Path(sys.argv[1]))\n"
            "lock.acquire()\n"
            "lock.release()\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "forecasts.sqlite3.run.lock"
            parent_lock = ForecastRunLock(lock_path)
            parent_lock.acquire()
            try:
                blocked = subprocess.run(
                    [sys.executable, "-c", child_script, str(lock_path)],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            finally:
                parent_lock.release()

            available = subprocess.run(
                [sys.executable, "-c", child_script, str(lock_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("bereits aktiv", blocked.stderr)
        self.assertEqual(available.returncode, 0, available.stderr)

    def test_daily_runner_rejects_parallel_start_before_database_or_market_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "runtime" / "forecasts.sqlite3"
            universe_path = root / "universe.csv"
            settings_path = root / "settings.json"
            log_path = root / "runtime" / "logs" / "forecast.log"
            universe_path.write_text(
                "ticker,asset_type,name,region,category,version\n"
                "TEST,Aktie,Test,Test,Test,1\n",
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "database_path": str(database_path),
                        "log_path": str(log_path),
                        "calibration_path": str(root / "runtime" / "calibration.json"),
                        "universe_path": str(universe_path),
                    }
                ),
                encoding="utf-8",
            )
            lock = ForecastRunLock(lock_path_for_database(database_path))
            lock.acquire()
            try:
                with self.assertRaises(ForecastRunAlreadyActiveError):
                    run_daily_process(settings_path, no_delay=True)
            finally:
                lock.release()

            self.assertFalse(database_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("parallele Start", log_text)


if __name__ == "__main__":
    unittest.main()
