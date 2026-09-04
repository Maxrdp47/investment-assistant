from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_post_run_integrity import (  # noqa: E402
    DEFAULT_FAILED_REPORT,
    DEFAULT_STORE_AUDIT_REPORT,
    DEFAULT_STRUCTURAL_REPORT,
    DEFAULT_TERMINAL_REPORT,
    build_terminal_truth_artifact,
    build_failed_work_unit_report,
    build_full_store_audit,
    build_structural_r_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--terminal-truth", action="store_true")
    actions.add_argument("--structural-r", action="store_true")
    actions.add_argument("--failed-units", action="store_true")
    actions.add_argument("--store-audit", action="store_true")
    parser.add_argument("--at")
    args = parser.parse_args()
    created_at = args.at or datetime.now(timezone.utc).isoformat()
    if args.terminal_truth:
        result = build_terminal_truth_artifact(created_at=created_at)
    elif args.structural_r:
        result = build_structural_r_report(created_at=created_at)
    elif args.failed_units:
        result = build_failed_work_unit_report(created_at=created_at)
    else:
        result = build_full_store_audit(created_at=created_at)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
