from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cot_positioning import (  # noqa: E402
    DEFAULT_COT_DB_PATH,
    DEFAULT_COT_MAPPING_PATH,
    collect_forward_cot_contexts,
    cot_shadow_store_audit,
)
from swing_forward_store import DEFAULT_SWING_FORWARD_DB_PATH  # noqa: E402
from swing_shadow_live import (  # noqa: E402
    DEFAULT_SWING_SHADOW_DB_PATH,
    record_shadow_execution_observations,
    shadow_live_store_audit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "COT-Forward-Sidecars und brokerlose Shadow-Execution-Missingness "
            "append-only sammeln."
        )
    )
    parser.add_argument("--forward-database", type=Path, default=DEFAULT_SWING_FORWARD_DB_PATH)
    parser.add_argument("--cot-database", type=Path, default=DEFAULT_COT_DB_PATH)
    parser.add_argument("--cot-mapping", type=Path, default=DEFAULT_COT_MAPPING_PATH)
    parser.add_argument("--shadow-database", type=Path, default=DEFAULT_SWING_SHADOW_DB_PATH)
    parser.add_argument("--refresh-cot", action="store_true")
    parser.add_argument("--skip-cot", action="store_true")
    parser.add_argument("--skip-shadow", action="store_true")
    return parser.parse_args()


def _forward_signal_map(path: Path) -> tuple[list[str], dict[str, str]]:
    resolved = Path(path).resolve()
    uri = f"file:{resolved.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT signal_id, setup_id FROM swing_signals ORDER BY signal_at, signal_id"
        ).fetchall()
    return [str(row[0]) for row in rows], {str(row[1]): str(row[0]) for row in rows}


def main() -> int:
    args = parse_args()
    signal_ids, signal_ids_by_setup = _forward_signal_map(args.forward_database)
    collected_at = datetime.now(timezone.utc)
    cot_result = {"status": "skipped"}
    if not args.skip_cot:
        cot_result = collect_forward_cot_contexts(
            signal_ids=signal_ids,
            forward_path=args.forward_database,
            collected_at=collected_at,
            path=args.cot_database,
            mapping_path=args.cot_mapping,
            refresh_official=args.refresh_cot,
        )
    shadow_result = {"status": "skipped"}
    if not args.skip_shadow:
        shadow_result = record_shadow_execution_observations(
            signal_ids_by_setup=signal_ids_by_setup,
            observed_at=collected_at,
            quote_provider=None,
            path=args.shadow_database,
        )
    output = {
        "status": (
            "ok"
            if cot_result.get("status") in {"ok", "skipped"}
            and shadow_result.get("status") in {"ok", "skipped"}
            else "research_attention"
        ),
        "forward_database_mode": "read_only",
        "cot": cot_result,
        "cot_audit": cot_shadow_store_audit(args.cot_database) if not args.skip_cot else None,
        "shadow_execution": shadow_result,
        "shadow_audit": shadow_live_store_audit(args.shadow_database) if not args.skip_shadow else None,
        "broad_feature_freeze_changed": False,
        "long_v1_changed": False,
        "broker_order_sent": False,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
