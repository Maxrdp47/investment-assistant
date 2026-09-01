from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_contract import load_development_contract  # noqa: E402
from multi_asset_development_execution import (  # noqa: E402
    build_development_universe,
    build_work_plan,
    checkpoint_status,
)
from multi_asset_development_runner import (  # noqa: E402
    _paths,
    export_development_contract,
    prepare_canonical_run,
    run_development,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--export-contract", action="store_true")
    actions.add_argument("--preflight", action="store_true")
    actions.add_argument("--prepare-run", action="store_true")
    actions.add_argument("--run", action="store_true")
    actions.add_argument("--status", action="store_true")
    parser.add_argument("--maximum-work-units", type=int)
    parser.add_argument("--frozen-at")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_development_contract()
    paths = _paths(contract)
    if args.export_contract:
        artifact, diff = export_development_contract(frozen_at=args.frozen_at)
        payload = {"contract": artifact, "diff": diff}
    elif args.preflight:
        universe = build_development_universe()
        work_plan = build_work_plan(universe)
        payload = {
            "contract_version": contract["contract_version"],
            "contract_fingerprint": contract["contract_fingerprint"],
            "research_role": contract["research_role"],
            "candidate_mode": contract["candidate_generation"]["mode"],
            "full_development_scan_allowed": contract["candidate_generation"][
                "full_development_scan_allowed"
            ],
            "universe_fingerprint": universe["universe_fingerprint"],
            "asset_count": universe["asset_count"],
            "asset_class_counts": universe["asset_class_counts"],
            "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
            "total_planned_work_units": work_plan["total_planned_work_units"],
            "development_only": work_plan["development_only"],
            "validation_opened": False,
            "holdout_opened": False,
        }
    elif args.prepare_run:
        manifest, universe, work_plan = prepare_canonical_run()
        payload = {
            "manifest": manifest,
            "asset_count": universe["asset_count"],
            "total_planned_work_units": work_plan["total_planned_work_units"],
        }
    elif args.run:
        payload = run_development(maximum_work_units=args.maximum_work_units)
    else:
        if not paths["manifest"].exists() or not paths["control"].exists():
            payload = {
                "status": "NOT_STARTED",
                "manifest_exists": paths["manifest"].exists(),
                "control_store_exists": paths["control"].exists(),
            }
        else:
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            payload = checkpoint_status(
                control_path=paths["control"], run_id=str(manifest["run_id"])
            )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
