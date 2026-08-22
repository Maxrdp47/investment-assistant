from __future__ import annotations

"""Ground-up frozen-history rescan for one manually frozen challenger stage."""

import argparse
import json
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cot_positioning import DEFAULT_COT_DB_PATH, load_cot_market_mapping  # noqa: E402
from swing_broad_research import (  # noqa: E402
    DEFAULT_BROAD_RESEARCH_DB_PATH,
    _load_fixed_challenger,
    build_fixed_challenger_rescan_asset,
    challenger_allowed_stage,
    completed_fixed_challenger_rescan_symbols,
    fixed_challenger_stage_metrics,
    record_fixed_challenger_rescan_asset,
)
from swing_research_dataset import load_frozen_histories, load_research_dataset_manifest  # noqa: E402
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock  # noqa: E402
from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_walk_forward_campaign import (  # noqa: E402
    DEFAULT_CAMPAIGN_CONFIG_PATH,
    DEFAULT_RESEARCH_LOCK_PATH,
    campaign_active_production_jobs,
    campaign_is_protected_time,
    load_campaign_config,
)


DEFAULT_FIXED_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)

_WORKER_MANIFEST: Path | None = None
_WORKER_CHALLENGER: dict = {}
_WORKER_SPLIT = ""
_WORKER_COT_REPORTS: list[dict] = []
_WORKER_COT_MAPPING: dict = {}


def _load_cot_reports(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT payload_json FROM cot_reports ORDER BY report_date, available_at, retrieved_at"
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(row[0]) for row in rows]


def _history(manifest_path: Path, symbol: str) -> pd.DataFrame:
    manifest = load_research_dataset_manifest(manifest_path)
    dataset_root = manifest_path.parent.parent
    frames = []
    for raw_scope in (manifest.get("scopes") or {}).values():
        contract = dict(raw_scope.get("contract") or {})
        histories, _ = load_frozen_histories(
            dataset_root,
            manifest,
            tickers=[symbol],
            start=contract.get("start"),
            end=contract.get("end"),
        )
        if symbol in histories:
            frames.append(histories[symbol])
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames).sort_index()
    return combined.loc[~combined.index.duplicated(keep="last")]


def _worker_init(
    manifest: str,
    challenger: dict,
    split: str,
    cot_database: str,
) -> None:
    global _WORKER_MANIFEST, _WORKER_CHALLENGER, _WORKER_SPLIT
    global _WORKER_COT_REPORTS, _WORKER_COT_MAPPING
    _WORKER_MANIFEST = Path(manifest)
    _WORKER_CHALLENGER = dict(challenger)
    _WORKER_SPLIT = str(split)
    _WORKER_COT_REPORTS = _load_cot_reports(Path(cot_database))
    _WORKER_COT_MAPPING = load_cot_market_mapping()


def _worker(asset: dict) -> dict:
    if _WORKER_MANIFEST is None:
        raise RuntimeError("Challenger-Worker wurde nicht initialisiert.")
    symbol = str(asset["ticker"]).upper()
    return build_fixed_challenger_rescan_asset(
        _WORKER_CHALLENGER,
        asset,
        _history(_WORKER_MANIFEST, symbol),
        research_split=_WORKER_SPLIT,
        cot_reports=_WORKER_COT_REPORTS,
        cot_mapping=_WORKER_COT_MAPPING,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manuell freigegebener Challenger-Rescan aus Frozen-OHLCV."
    )
    parser.add_argument("--challenger-version", required=True)
    parser.add_argument("--stage", choices=("validation", "holdout"), required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FIXED_MANIFEST)
    parser.add_argument("--database", type=Path, default=DEFAULT_BROAD_RESEARCH_DB_PATH)
    parser.add_argument("--universe", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--cot-database", type=Path, default=DEFAULT_COT_DB_PATH)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--maximum-assets", type=int, default=16)
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    challenger = _load_fixed_challenger(args.challenger_version, args.database)
    gate = challenger_allowed_stage(args.challenger_version, args.stage, args.database)
    completed = completed_fixed_challenger_rescan_symbols(
        args.challenger_version, args.stage, args.database
    )
    universe = load_swing_universe(args.universe)
    if universe.errors:
        raise RuntimeError("; ".join(universe.errors))
    assets = [asset.as_dict() for asset in universe.assets if asset.active]
    status = {
        "gate": gate,
        "completed_assets": len(completed),
        "expected_assets": len(assets),
        "stage_metrics": fixed_challenger_stage_metrics(
            args.challenger_version, args.stage, args.database
        ),
        "automatic_stage_review": False,
        "automatic_production_activation": False,
    }
    if args.status_only:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    if not gate["allowed"]:
        print(json.dumps({"challenger_rescan_skipped": "stage_locked", **status}, ensure_ascii=False))
        return 2
    manifest = load_research_dataset_manifest(args.manifest)
    if str(manifest["dataset_fingerprint"]) != str(challenger["dataset_fingerprint"]):
        raise RuntimeError("Challenger und Frozen-Manifest besitzen verschiedene Fingerprints.")
    config = load_campaign_config(DEFAULT_CAMPAIGN_CONFIG_PATH)
    now = datetime.now().astimezone()
    if campaign_is_protected_time(now, config):
        print(json.dumps({"challenger_rescan_skipped": "protected_production_window"}, ensure_ascii=False))
        return 2
    active_production = campaign_active_production_jobs(config, project_root=PROJECT_ROOT)
    if active_production:
        print(json.dumps({"challenger_rescan_skipped": "production_active", "active_production": active_production}, ensure_ascii=False))
        return 2
    pending = [asset for asset in assets if str(asset["ticker"]).upper() not in completed]
    pending = pending[: max(0, int(args.maximum_assets))]
    workers = max(1, min(int(args.workers), 8))
    try:
        with SwingRunLock(DEFAULT_RESEARCH_LOCK_PATH):
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_worker_init,
                initargs=(str(args.manifest), challenger, args.stage, str(args.cot_database)),
            ) as pool:
                futures = {pool.submit(_worker, asset): str(asset["ticker"]) for asset in pending}
                for index, future in enumerate(as_completed(futures), start=1):
                    symbol = futures[future]
                    stored = record_fixed_challenger_rescan_asset(future.result(), path=args.database)
                    print(json.dumps({"asset": symbol, "processed": index, "scheduled": len(pending), "stored": stored}, ensure_ascii=False), flush=True)
    except SwingRunAlreadyActiveError as exc:
        print(json.dumps({"challenger_rescan_skipped": "research_lock_active", "reason": str(exc)}, ensure_ascii=False))
        return 2
    completed_after = completed_fixed_challenger_rescan_symbols(
        args.challenger_version, args.stage, args.database
    )
    print(
        json.dumps(
            {
                "processed_this_run": len(pending),
                "completed_assets": len(completed_after),
                "expected_assets": len(assets),
                "stage_metrics": fixed_challenger_stage_metrics(
                    args.challenger_version, args.stage, args.database
                ),
                "manual_stage_review_required": len(completed_after) == len(assets),
                "automatic_stage_review": False,
                "automatic_production_activation": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
