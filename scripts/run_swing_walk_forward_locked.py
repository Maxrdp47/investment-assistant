from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_swing_walk_forward import main  # noqa: E402
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock  # noqa: E402
from swing_walk_forward_campaign import DEFAULT_RESEARCH_LOCK_PATH  # noqa: E402


if __name__ == "__main__":
    try:
        with SwingRunLock(DEFAULT_RESEARCH_LOCK_PATH):
            raise SystemExit(main())
    except SwingRunAlreadyActiveError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(75)
