from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from forecast_backup import (
    create_forecast_backup,
    inspect_forecast_database,
    restore_forecast_backup_to_new_file,
)
from forecast_store import CURRENT_SCHEMA_VERSION, initialize_database, start_or_resume_run


class ForecastBackupTests(unittest.TestCase):
    def test_backup_and_restore_copy_preserve_database_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "forecasts.sqlite3"
            initialize_database(database_path)
            start_or_resume_run("2026-08-02", 325, database_path)

            backup = create_forecast_backup(
                database_path,
                root / "backups",
                now=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
            )
            restored_path = root / "restored" / "forecasts.sqlite3"
            restored = restore_forecast_backup_to_new_file(Path(backup["path"]), restored_path)

            self.assertEqual(backup["status"], "ok")
            self.assertFalse(backup["data_deleted"])
            self.assertEqual(restored["status"], "ok")
            self.assertEqual(restored["schema_version"], CURRENT_SCHEMA_VERSION)
            with closing(sqlite3.connect(restored_path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0], 1)

            with self.assertRaises(FileExistsError):
                restore_forecast_backup_to_new_file(Path(backup["path"]), restored_path)

    def test_corrupt_database_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "corrupt.sqlite3"
            corrupt.write_bytes(b"keine sqlite datenbank")

            with self.assertRaisesRegex(ValueError, "nicht lesbar"):
                inspect_forecast_database(corrupt)


if __name__ == "__main__":
    unittest.main()
