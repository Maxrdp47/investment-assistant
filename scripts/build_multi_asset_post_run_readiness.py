from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_post_run_readiness import (  # noqa: E402
    build_post_run_readiness_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheduler-state", required=True)
    parser.add_argument("--fx-observer-state", required=True)
    parser.add_argument("--at")
    args = parser.parse_args()
    result = build_post_run_readiness_report(
        created_at=args.at,
        scheduler_state=args.scheduler_state,
        fx_observer_state=args.fx_observer_state,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["technical_status"].endswith("READY_FOR_REPROCESSING_REVIEW") else 1


if __name__ == "__main__":
    raise SystemExit(main())
