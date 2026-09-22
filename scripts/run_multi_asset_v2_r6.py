from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multi_asset_v2_r6_runner import cli  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(cli())
