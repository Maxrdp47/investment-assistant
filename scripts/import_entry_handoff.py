from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge.entry_handoff import (  # noqa: E402
    EXIT_CODES,
    HandoffValidationError,
    failure_response,
    import_handoff,
)
from research_knowledge.schema import DEFAULT_DATABASE_PATH  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Importiert ein geprüftes trading_handoff_v1-Paket aus ENTRY sicher "
            "in die bestehende Research-Knowledge-Base."
        )
    )
    parser.add_argument("--input", type=Path, required=True, help="Pfad zur Handoff-JSON-Datei")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help="Ziel-Datenbank (Standard: aktive Research-Knowledge-Base)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validiert und simuliert den vollständigen Import ohne persistente Änderungen",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Gibt genau ein maschinenlesbares JSON-Objekt aus",
    )
    return parser


def _emit(response: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return
    print(f"{response['status']}: {response['reason']}")
    if response.get("handoff_id"):
        print(f"Handoff-ID: {response['handoff_id']}")
    if response.get("source_id"):
        print(f"Research-Source-ID: {response['source_id']}")
    if response.get("claim_ids"):
        print(f"Claim-IDs: {', '.join(str(item) for item in response['claim_ids'])}")


def run(argv: list[str] | None = None) -> tuple[dict[str, object], int]:
    args = build_parser().parse_args(argv)
    input_path = args.input.resolve()
    database_path = args.database.resolve()
    package: object | None = None
    try:
        with input_path.open("r", encoding="utf-8") as handle:
            package = json.load(handle)
        response = import_handoff(
            package,
            database_path=database_path,
            dry_run=bool(args.dry_run),
        )
    except (FileNotFoundError, PermissionError, UnicodeError, json.JSONDecodeError) as exc:
        response = failure_response(
            "REJECTED_INVALID",
            f"Handoff-Datei konnte nicht gelesen werden: {exc}",
            input_path=str(input_path),
        )
    except HandoffValidationError as exc:
        response = failure_response(
            "REJECTED_INVALID",
            str(exc),
            input_path=str(input_path),
        )
    except (sqlite3.DatabaseError, OSError, RuntimeError) as exc:
        response = failure_response(
            "FAILED_RETRYABLE",
            f"Temporärer Datenbank-/Dateifehler: {exc}",
            handoff_id=(package.get("handoff_id") if isinstance(package, dict) else None),
            database_path=str(database_path),
        )
    return response, EXIT_CODES[str(response["status"])]


def main(argv: list[str] | None = None) -> int:
    response, exit_code = run(argv)
    json_output = "--json-output" in (argv if argv is not None else sys.argv[1:])
    _emit(response, json_output=json_output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
