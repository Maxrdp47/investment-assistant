from __future__ import annotations

"""Freeze and run the simple Buyer Confirmation challenger sequentially."""

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

from swing_buyer_confirmation_validation import (  # noqa: E402
    CHALLENGER_VERSION,
    _source_snapshot,
    build_challenger_freeze,
    build_stage_asset,
    completed_stage_symbols,
    evaluate_stage,
    load_challenger_freeze,
    open_stage,
    pre_validation_integrity_gate,
    record_challenger_freeze,
    record_integrity_receipt,
    record_stage_asset,
    record_stage_review,
    stage_allowed,
    validation_store_status,
    write_append_only_report,
)
from swing_research_dataset import (  # noqa: E402
    load_frozen_histories,
    load_research_dataset_manifest,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock  # noqa: E402
from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_walk_forward_campaign import (  # noqa: E402
    DEFAULT_CAMPAIGN_CONFIG_PATH,
    DEFAULT_RESEARCH_LOCK_PATH,
    historical_research_runtime_gate,
    load_campaign_config,
)


DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "runtime"
DEFAULT_DATABASE = DEFAULT_RUNTIME_ROOT / "buyer_confirmation_validation.sqlite3"
DEFAULT_BROAD_DATABASE = DEFAULT_RUNTIME_ROOT / "swing_broad_research.sqlite3"
DEFAULT_MANIFEST = (
    DEFAULT_RUNTIME_ROOT
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)
DEFAULT_DEVELOPMENT_REPORT = (
    DEFAULT_RUNTIME_ROOT
    / "research_exports"
    / "buyer_confirmation_development_robustness_2026-08-26-v3-authoritative.json"
)
DEFAULT_EXPORT_ROOT = DEFAULT_RUNTIME_ROOT / "research_exports"

_WORKER_MANIFEST: Path | None = None
_WORKER_FREEZE: dict = {}
_WORKER_STAGE = ""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _history(manifest_path: Path, symbol: str) -> pd.DataFrame:
    manifest = load_research_dataset_manifest(manifest_path)
    dataset_container = manifest_path.parent.parent
    frames = []
    for raw_scope in (manifest.get("scopes") or {}).values():
        contract = dict(raw_scope.get("contract") or {})
        histories, _ = load_frozen_histories(
            dataset_container,
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


def _worker_init(manifest: str, freeze: dict, stage: str) -> None:
    global _WORKER_MANIFEST, _WORKER_FREEZE, _WORKER_STAGE
    _WORKER_MANIFEST = Path(manifest)
    _WORKER_FREEZE = dict(freeze)
    _WORKER_STAGE = str(stage)


def _worker(asset: dict) -> dict:
    if _WORKER_MANIFEST is None:
        raise RuntimeError("Buyer Confirmation worker is not initialized.")
    symbol = str(asset["ticker"]).upper()
    return build_stage_asset(
        _WORKER_FREEZE,
        asset,
        _history(_WORKER_MANIFEST, symbol),
        research_stage=_WORKER_STAGE,
    )


def _protected_sources_unchanged(
    freeze: dict,
    *,
    broad_path: Path,
    manifest_path: Path,
    development_path: Path,
) -> bool:
    snapshots = freeze["source_snapshots"]
    return (
        _source_snapshot(broad_path, hash_file=False) == snapshots["broad_v1"]
        and _source_snapshot(manifest_path, hash_file=True) == snapshots["dataset_manifest"]
        and _source_snapshot(development_path, hash_file=True)
        == snapshots["development_report"]
    )


def _freeze(args: argparse.Namespace, assets: list[dict]) -> dict[str, object]:
    frozen_at = str(args.at or _now())
    freeze = build_challenger_freeze(
        development_report_path=args.development_report,
        broad_path=args.broad_database,
        dataset_manifest_path=args.manifest,
        expected_assets=len(assets),
        frozen_at=frozen_at,
    )
    freeze = record_challenger_freeze(freeze, args.database)
    receipt = pre_validation_integrity_gate(
        freeze,
        broad_path=args.broad_database,
        dataset_manifest_path=args.manifest,
        development_report_path=args.development_report,
        store_path=args.database,
        checked_at=frozen_at,
    )
    receipt = record_integrity_receipt(receipt, args.database)
    write_append_only_report(
        freeze, args.export_root / "buyer_confirmation_challenger_freeze_2026-08-26-v1.json"
    )
    write_append_only_report(
        receipt,
        args.export_root / "buyer_confirmation_pre_validation_integrity_2026-08-26-v1.json",
    )
    return {"freeze": freeze, "pre_validation_integrity": receipt}


def _run_stage(args: argparse.Namespace, assets: list[dict]) -> dict[str, object]:
    freeze = load_challenger_freeze(args.database)
    if not _protected_sources_unchanged(
        freeze,
        broad_path=args.broad_database,
        manifest_path=args.manifest,
        development_path=args.development_report,
    ):
        raise RuntimeError("A protected Broad-v1, dataset, or Development source changed.")
    gate = stage_allowed(freeze, args.stage, args.database)
    if not gate["allowed"]:
        return {"stage_run_skipped": "stage_locked", "gate": gate}
    status_before = validation_store_status(args.database)
    if status_before["stages"][args.stage]["decision"] is not None:
        return {
            "stage_run_skipped": "stage_already_reviewed",
            "decision": status_before["stages"][args.stage]["decision"],
        }
    config = load_campaign_config(args.campaign_config)
    runtime_gate = historical_research_runtime_gate(
        config, project_root=args.project_root
    )
    if not runtime_gate["run_allowed"]:
        return {
            "stage_run_skipped": "blocked_real_conflict",
            "runtime_gate": runtime_gate,
        }
    completed = completed_stage_symbols(CHALLENGER_VERSION, args.stage, args.database)
    pending = [asset for asset in assets if str(asset["ticker"]).upper() not in completed]
    batch_limit = (
        int(args.maximum_assets)
        if args.maximum_assets is not None
        else int(config.get("batch_size") or 100)
    )
    pending = pending[: max(0, batch_limit)]
    workers = max(1, min(int(args.workers), 8))
    processed = 0
    try:
        with SwingRunLock(args.research_lock):
            runtime_gate = historical_research_runtime_gate(
                config, project_root=args.project_root
            )
            if not runtime_gate["run_allowed"]:
                return {
                    "stage_run_skipped": "blocked_real_conflict_after_research_lock",
                    "runtime_gate": runtime_gate,
                }
            if not status_before["stages"][args.stage]["opened"]:
                open_stage(
                    freeze, args.stage, opened_at=str(args.at or _now()), path=args.database
                )
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_worker_init,
                initargs=(str(args.manifest), freeze, args.stage),
            ) as pool:
                futures = {pool.submit(_worker, asset): str(asset["ticker"]) for asset in pending}
                for future in as_completed(futures):
                    stored = record_stage_asset(future.result(), args.database)
                    processed += 1
                    print(
                        json.dumps(
                            {
                                "stage": args.stage,
                                "asset": futures[future],
                                "processed": processed,
                                "scheduled": len(pending),
                                "completed_asset": stored["already_complete"] is False,
                                "cases": stored["cases_inserted"],
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
    except SwingRunAlreadyActiveError as exc:
        return {"stage_run_skipped": "research_lock_active", "reason": str(exc)}
    if not _protected_sources_unchanged(
        freeze,
        broad_path=args.broad_database,
        manifest_path=args.manifest,
        development_path=args.development_report,
    ):
        raise RuntimeError("A protected source changed during the ground-up stage run.")
    completed_after = completed_stage_symbols(CHALLENGER_VERSION, args.stage, args.database)
    output: dict[str, object] = {
        "stage": args.stage,
        "processed_this_run": processed,
        "completed_assets": len(completed_after),
        "expected_assets": len(assets),
        "completion_pct": round(len(completed_after) / len(assets) * 100, 2),
        "automatic_production_activation": False,
    }
    if len(completed_after) == len(assets):
        evaluation = evaluate_stage(
            freeze,
            args.stage,
            path=args.database,
            dataset_root=args.manifest.parent,
        )
        review = record_stage_review(
            evaluation, reviewed_at=str(args.at or _now()), path=args.database
        )
        write_append_only_report(
            review,
            args.export_root
            / f"buyer_confirmation_{args.stage}_decision_2026-08-26-v1.json",
        )
        output["review"] = review
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze and evaluate Buyer Confirmation without touching Broad-v1."
    )
    parser.add_argument("action", choices=("freeze", "run", "status"))
    parser.add_argument("--stage", choices=("validation", "holdout"), default="validation")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--broad-database", type=Path, default=DEFAULT_BROAD_DATABASE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--development-report", type=Path, default=DEFAULT_DEVELOPMENT_REPORT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--campaign-config", type=Path, default=DEFAULT_CAMPAIGN_CONFIG_PATH)
    parser.add_argument("--research-lock", type=Path, default=DEFAULT_RESEARCH_LOCK_PATH)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--maximum-assets", type=int)
    parser.add_argument("--at")
    args = parser.parse_args()

    universe = load_swing_universe(args.universe)
    if universe.errors:
        raise RuntimeError("; ".join(universe.errors))
    assets = [asset.as_dict() for asset in universe.assets if asset.active]
    if args.action == "freeze":
        output = _freeze(args, assets)
    elif args.action == "run":
        output = _run_stage(args, assets)
    else:
        output = validation_store_status(args.database)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
