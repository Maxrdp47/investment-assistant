from __future__ import annotations

"""Run the read-only Buyer Confirmation integrity/reproduction audit."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_buyer_confirmation_provenance import (  # noqa: E402
    audit_validation_store,
    compare_validation_stores,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Buyer Confirmation Validation provenance audit."
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--decision-report", type=Path)
    parser.add_argument("--reproduction", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.reproduction is None:
        result = audit_validation_store(
            args.reference, decision_report_path=args.decision_report
        )
    else:
        result = compare_validation_stores(args.reference, args.reproduction)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
