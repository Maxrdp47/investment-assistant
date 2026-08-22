from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_background_runner import (
    DEFAULT_SWING_BACKGROUND_SETTINGS_PATH,
    run_swing_background_scope,
    swing_background_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bedienungsfreie regionale Swing-Scans ausführen.")
    parser.add_argument("--settings", type=Path, default=DEFAULT_SWING_BACKGROUND_SETTINGS_PATH)
    parser.add_argument("--scope", choices=["asia", "europe", "america_global", "crypto"])
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = swing_background_preflight(args.settings)
    else:
        if not args.scope:
            parser.error("--scope ist ohne --preflight erforderlich")
        result = run_swing_background_scope(args.scope, settings_path=args.settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "provider_unavailable", "already_active"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
