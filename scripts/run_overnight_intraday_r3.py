from __future__ import annotations

"""Run the one frozen R3 descriptive Development attempt; no live hooks."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from overnight_intraday_r3 import DEFAULT_CONTRACT, load_contract, project_path, run  # noqa: E402
from swing_run_lock import SwingRunLock  # noqa: E402
from swing_walk_forward_campaign import historical_research_runtime_gate, load_campaign_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--max-assets", type=int)
    args = parser.parse_args()
    if args.max_assets is not None and args.max_assets < 1:
        parser.error("--max-assets must be positive")
    contract, contract_fingerprint = load_contract(args.contract)
    gate = historical_research_runtime_gate(load_campaign_config(), project_root=ROOT)
    if gate.get("run_allowed") is not True:
        print(json.dumps({"r3_start_blocked": gate}, sort_keys=True))
        return 2
    with SwingRunLock(project_path(contract["runtime"]["process_lock"])):
        with SwingRunLock(project_path(contract["runtime"]["research_lock"])):
            gate = historical_research_runtime_gate(load_campaign_config(), project_root=ROOT)
            if gate.get("run_allowed") is not True:
                print(json.dumps({"r3_start_blocked": gate}, sort_keys=True))
                return 2
            result = run(
                args.contract,
                max_assets=args.max_assets,
                should_pause=lambda: not historical_research_runtime_gate(
                    load_campaign_config(), project_root=ROOT
                )["run_allowed"],
            )
    print(json.dumps({"contract_fingerprint": contract_fingerprint, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
