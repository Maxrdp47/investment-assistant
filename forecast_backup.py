from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from forecast_store import CURRENT_SCHEMA_VERSION, DEFAULT_DATABASE_PATH


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "runtime" / "backups"


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    return sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=30)


def inspect_forecast_database(path: Path) -> dict:
    database_path = Path(path)
    if not database_path.is_file():
        raise FileNotFoundError(f"Prognose-Datenbank nicht gefunden: {database_path}")
    try:
        with closing(_readonly_connection(database_path)) as connection:
            quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            forecast_count = (
                int(connection.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0])
                if "forecasts" in tables
                else 0
            )
            evaluation_count = (
                int(connection.execute("SELECT COUNT(*) FROM forecast_evaluations").fetchone()[0])
                if "forecast_evaluations" in tables
                else 0
            )
    except sqlite3.Error as exc:
        raise ValueError(f"Prognose-Datenbank ist nicht lesbar: {exc}") from exc
    return {
        "path": str(database_path.resolve()),
        "status": "ok" if quick_check.lower() == "ok" else "attention",
        "quick_check": quick_check,
        "schema_version": schema_version,
        "supported_schema_version": CURRENT_SCHEMA_VERSION,
        "forecast_count": forecast_count,
        "evaluation_count": evaluation_count,
        "bytes": database_path.stat().st_size,
    }


def _verified_sqlite_copy(source: Path, destination: Path) -> dict:
    source_health = inspect_forecast_database(source)
    if source_health["status"] != "ok":
        raise ValueError("Quelle ist nicht integer; Sicherung oder Wiederherstellung wurde abgebrochen.")
    if int(source_health["schema_version"]) > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            "Quelle stammt aus einer neueren, nicht unterstützten Datenbankversion "
            f"({source_health['schema_version']})."
        )
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"Zieldatei existiert bereits und wird nicht überschrieben: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with closing(_readonly_connection(source)) as source_connection:
            with closing(sqlite3.connect(temporary)) as destination_connection:
                source_connection.backup(destination_connection)
                destination_connection.commit()
        copied_health = inspect_forecast_database(temporary)
        if copied_health["status"] != "ok":
            raise ValueError("Die erzeugte SQLite-Kopie hat die Integritätsprüfung nicht bestanden.")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return inspect_forecast_database(destination)


def create_forecast_backup(
    source: Path = DEFAULT_DATABASE_PATH,
    backup_directory: Path = DEFAULT_BACKUP_DIR,
    now: datetime | None = None,
) -> dict:
    timestamp = (now or datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S-%f")
    destination = Path(backup_directory) / f"forecasts-{timestamp}.sqlite3"
    result = _verified_sqlite_copy(Path(source), destination)
    return {**result, "operation": "backup", "source": str(Path(source).resolve()), "data_deleted": False}


def restore_forecast_backup_to_new_file(backup: Path, destination: Path) -> dict:
    """Create a verified restore copy without replacing an existing database."""

    result = _verified_sqlite_copy(Path(backup), Path(destination))
    return {**result, "operation": "restore-copy", "source": str(Path(backup).resolve()), "data_deleted": False}
