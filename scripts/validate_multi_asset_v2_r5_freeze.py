from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multi_asset_v2_r5_contract import validate_freeze  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository-only",
        action="store_true",
        help="Validate committed contracts/reports only; explicitly do not claim runtime datasets were checked.",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            validate_freeze(require_runtime_sources=not args.repository_only),
            indent=2,
            sort_keys=True,
        )
    )
