from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forecast_backup import (
    DEFAULT_BACKUP_DIR,
    create_forecast_backup,
    inspect_forecast_database,
    restore_forecast_backup_to_new_file,
)
from forecast_store import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prognose-Datenbank sicher prüfen, sichern oder in eine neue Datei wiederherstellen."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="SQLite-Datei nur lesend prüfen.")
    inspect_parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_DATABASE_PATH)

    backup_parser = subparsers.add_parser("backup", help="Zeitgestempelte, geprüfte Sicherung erstellen.")
    backup_parser.add_argument("--source", type=Path, default=DEFAULT_DATABASE_PATH)
    backup_parser.add_argument("--directory", type=Path, default=DEFAULT_BACKUP_DIR)

    restore_parser = subparsers.add_parser(
        "restore-copy",
        help="Sicherung in eine neue Datei kopieren; vorhandene Dateien werden niemals überschrieben.",
    )
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("--to", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "inspect":
            result = inspect_forecast_database(args.path)
        elif args.command == "backup":
            result = create_forecast_backup(args.source, args.directory)
        else:
            result = restore_forecast_backup_to_new_file(args.backup, args.to)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
