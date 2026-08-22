from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cot_positioning import (  # noqa: E402
    CFTC_DATASETS,
    DEFAULT_COT_DB_PATH,
    cot_shadow_store_audit,
    fetch_cftc_rows,
    ingest_cftc_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offizielle CFTC-COT-Daten ausschließlich für den Swing-Shadow-Layer sammeln."
    )
    parser.add_argument(
        "--report-type",
        choices=["all", *CFTC_DATASETS],
        default="all",
    )
    parser.add_argument("--start", help="Startdatum YYYY-MM-DD; Standard: 21 Tage zurück")
    parser.add_argument("--end", help="Enddatum YYYY-MM-DD; Standard: heute")
    parser.add_argument("--database", type=Path, default=DEFAULT_COT_DB_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end = date.fromisoformat(args.end) if args.end else date.today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=21)
    retrieved_at = datetime.now(timezone.utc)
    report_types = list(CFTC_DATASETS) if args.report_type == "all" else [args.report_type]
    results = []
    for report_type in report_types:
        rows = fetch_cftc_rows(report_type, start=start, end=end)
        results.append(
            ingest_cftc_rows(
                rows,
                report_type=report_type,
                retrieved_at=retrieved_at,
                acquisition_mode="forward",
                path=args.database,
            )
        )
    output = {
        "status": "completed",
        "source": "official_cftc_public_reporting",
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "retrieved_at": retrieved_at.isoformat(),
        "results": results,
        "audit": cot_shadow_store_audit(args.database),
        "shadow_only": True,
        "production_effect": "none",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
