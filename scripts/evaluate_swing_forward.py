from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_forward_runner import run_swing_forward_evaluations
from swing_forward_store import DEFAULT_SWING_FORWARD_DB_PATH, swing_forward_store_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Wertet echte append-only Swing-Paper-Signale aus.")
    parser.add_argument("--database", type=Path, default=DEFAULT_SWING_FORWARD_DB_PATH)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(swing_forward_store_audit(args.database), ensure_ascii=False, indent=2))
        return 0
    result = run_swing_forward_evaluations(path=args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] and result["store_audit"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
