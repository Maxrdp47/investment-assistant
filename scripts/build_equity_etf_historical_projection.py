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

from equity_etf_historical_remediation import (  # noqa: E402
    DEFAULT_ARTIFACT,
    DEFAULT_TARGET_STORE,
    build_equity_etf_clean_projection,
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=PROJECT_ROOT, text=True, encoding="utf-8"
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET_STORE)
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--at")
    args = parser.parse_args()
    command = "scripts/build_equity_etf_historical_projection.py"
    result = build_equity_etf_clean_projection(
        target_path=args.target,
        artifact_path=args.output,
        created_at=args.at or datetime.now(timezone.utc).isoformat(),
        code_commit=_git("rev-parse", "HEAD"),
        branch=_git("branch", "--show-current"),
        command=command,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (
        result["active_envelope_anomaly_count"] == 0
        and result["active_non_positive_ohlc_count"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
