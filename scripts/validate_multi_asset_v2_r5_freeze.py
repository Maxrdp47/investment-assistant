from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multi_asset_v2_r5_contract import validate_freeze  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(validate_freeze(), indent=2, sort_keys=True))
