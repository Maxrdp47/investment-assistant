from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from historical_dependency_policy import (  # noqa: E402
    historical_dependency_policy_self_check,
)


DEFAULT_IDENTITY_STORE = PROJECT_ROOT / "runtime" / "research_identity_registry.sqlite3"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "historical_dependency_policy_2026-09-01-v1.json"
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=PROJECT_ROOT, text=True, encoding="utf-8"
    ).strip()


def _latest_registry(path: Path) -> dict[str, object]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute(
            "SELECT registry_json FROM registry_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise RuntimeError("Identity Registry ist leer.")
    return json.loads(str(row[0]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-store", type=Path, default=DEFAULT_IDENTITY_STORE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--at")
    args = parser.parse_args()
    registry = _latest_registry(args.identity_store)
    payload = historical_dependency_policy_self_check()
    payload.update(
        {
            "created_at": args.at or datetime.now(timezone.utc).isoformat(),
            "identity_registry_fingerprint": registry["registry_fingerprint"],
            "identity_mapping_version": registry["mapping_version"],
            "code_commit": _git("rev-parse", "HEAD"),
            "run_commit": _git("rev-parse", "HEAD"),
            "artifact_packaging_commit": None,
            "branch": _git("branch", "--show-current"),
            "historical_relationship_records_present": sum(
                bool(
                    dict(record.get("metadata") or {}).get("historical_dependency")
                    or record.get("historical_dependency")
                )
                for record in registry.get("records", [])
            ),
            "current_registry_valid_from_backdated": False,
            "development_or_later_stage_opened": False,
        }
    )
    payload["artifact_fingerprint"] = __import__(
        "historical_dependency_policy"
    ).fingerprint(payload)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if existing != payload:
            raise RuntimeError(f"Append-only-Artefakt weicht ab: {args.output}")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

