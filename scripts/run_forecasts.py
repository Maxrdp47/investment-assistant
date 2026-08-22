from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forecast_runner import (
    DEFAULT_SETTINGS_PATH,
    load_settings,
    project_path,
    run_daily_process,
    runtime_preflight,
)
from forecast_calibration import write_calibration_profile
from forecast_store import maintain_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tägliche Prognosen und fällige Auswertungen ausführen.")
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--date", help="Optionales Laufdatum im Format JJJJ-MM-TT.")
    parser.add_argument("--limit", type=int, help="Nur für kontrollierte Testläufe: Zahl der Assets begrenzen.")
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Kompatibilitätsoption für die Wiederaufnahme eines unvollständigen Laufs; "
            "abgeschlossene Tagesläufe und andere Logikversionen werden nie überschrieben."
        ),
    )
    parser.add_argument("--no-delay", action="store_true", help="Nur für lokale Tests: konfigurierte Pausen auslassen.")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Konfiguration, Universum, Schreibpfade und Datenbank ohne Marktabruf vorprüfen.",
    )
    parser.add_argument(
        "--maintenance-only",
        action="store_true",
        help="Nur Schema, Integrität, Größe und WAL der Prognose-Datenbank prüfen und optimieren.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Bei der Wartung zusätzlich freien SQLite-Platz zurückgewinnen; löscht keine Prognosen.",
    )
    parser.add_argument(
        "--calibration-only",
        action="store_true",
        help="Nur das versionierte Kalibrierungsprofil aus vorhandenen Auswertungen aktualisieren.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight:
        result = runtime_preflight(args.settings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1
    if args.calibration_only:
        settings = load_settings(args.settings)
        database_path = project_path(settings["database_path"])
        output_path = project_path(settings["calibration_path"])
        profile = write_calibration_profile(database_path, output_path)
        result = {
            "status": "ok",
            "path": str(output_path),
            "profile_version": profile["profile_version"],
            "evaluated_cases": profile["overall"]["evaluated_cases"],
            "manual_review_suggestions": len(profile["manual_review_suggestions"]),
            "data_fingerprint": profile["data_fingerprint"],
            "production_rules_changed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.maintenance_only or args.compact:
        settings = load_settings(args.settings)
        result = maintain_database(project_path(settings["database_path"]), compact=args.compact)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1
    result = run_daily_process(args.settings, args.date, args.limit, args.force, args.no_delay)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["collection"]["status"] != "interrupted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
