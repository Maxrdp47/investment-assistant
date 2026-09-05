from __future__ import annotations

"""CLI for the closed and resumable Development-v6 lifecycle chain."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_v6_runner import (  # noqa: E402
    DEFAULT_CHAIN_STATE_PATH,
    advance_chain,
    read_chain_status,
    set_operator_request,
)


def _state_path() -> Path:
    return DEFAULT_CHAIN_STATE_PATH


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run or inspect the immutable Development-v6 local chain."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--advance", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--pause", action="store_true")
    action.add_argument("--stop", action="store_true")
    action.add_argument("--resume", action="store_true")
    parser.add_argument("--maximum-asset-batches", type=int)
    args = parser.parse_args()
    if args.maximum_asset_batches is not None and args.maximum_asset_batches <= 0:
        parser.error("--maximum-asset-batches must be positive")
    if args.status:
        payload = read_chain_status(_state_path())
    elif args.pause:
        payload = set_operator_request(chain_state_path=_state_path(), request="PAUSE")
    elif args.stop:
        payload = set_operator_request(chain_state_path=_state_path(), request="STOP")
    elif args.resume:
        payload = set_operator_request(chain_state_path=_state_path(), request=None)
    else:
        payload = advance_chain(maximum_asset_batches=args.maximum_asset_batches)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    if payload.get("status") == "PAUSED_REQUIRES_REVIEW" and args.advance:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
