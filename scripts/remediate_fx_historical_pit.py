from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fx_historical_remediation import remediate_historical_fx_store  # noqa: E402


DEFAULT_SOURCE = PROJECT_ROOT / "runtime" / "fx_historical_pit.sqlite3"
DEFAULT_TARGET = (
    PROJECT_ROOT / "runtime" / "fx_historical_pit_2026-09-01-v2.sqlite3"
)
DEFAULT_PREVIOUS_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "fx_historical_pit_2026-08-29-v1.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "fx_historical_pit_remediation_2026-09-01-v2.json"
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=PROJECT_ROOT, text=True, encoding="utf-8"
    ).strip()


def write_immutable_json(path: Path, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != payload:
            raise RuntimeError(f"Append-only-Artefakt weicht ab: {path}")
        return
    path.write_text(encoded, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument(
        "--previous-artifact", type=Path, default=DEFAULT_PREVIOUS_ARTIFACT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--at")
    args = parser.parse_args()
    commit = _git("rev-parse", "HEAD")
    result = remediate_historical_fx_store(
        source_path=args.source,
        target_path=args.target,
        previous_artifact_path=args.previous_artifact,
        created_at=args.at or datetime.now(timezone.utc).isoformat(),
        code_commit=commit,
        branch=_git("branch", "--show-current"),
        command=(
            "scripts/remediate_fx_historical_pit.py "
            f"--source {args.source} --target {args.target}"
        ),
    )
    write_immutable_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("active_envelope_anomaly_n") == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

