from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swing_broad_research_audit import (  # noqa: E402
    apply_manual_development_review,
    audit_broad_v1,
    write_append_only_json,
)


DEFAULT_BROAD = ROOT / "runtime" / "swing_broad_research.sqlite3"
DEFAULT_QUALITY = ROOT / "runtime" / "swing_research_quality.sqlite3"
DEFAULT_OUTPUT = (
    ROOT / "runtime" / "research_exports" / "swing_broad_v1_method_audit_2026-08-25-v3.json"
)


def _progress(rows: int) -> None:
    print(json.dumps({"development_rows_read_only_audited": rows}), file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of immutable Swing Broad-v1.")
    parser.add_argument("--broad", type=Path, default=DEFAULT_BROAD)
    parser.add_argument("--quality", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manual-decisions", type=Path)
    args = parser.parse_args()
    report = audit_broad_v1(args.broad, args.quality, progress_callback=_progress)
    if args.manual_decisions:
        decisions = json.loads(args.manual_decisions.read_text(encoding="utf-8"))
        report = apply_manual_development_review(
            report,
            decisions,
            reviewed_at=datetime.now().astimezone().isoformat(),
        )
    receipt = write_append_only_json(report, args.output)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
