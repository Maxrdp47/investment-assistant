from __future__ import annotations

import argparse
import hashlib
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
    BROAD_RESEARCH_FEATURE_VERSION,
    DEFAULT_BROAD_RESEARCH_DB_PATH,
    broad_research_code_fingerprint,
    broad_research_feature_contract_fingerprint,
    broad_research_store_audit,
    build_asset_broad_research,
    completed_broad_research_symbols,
    development_pattern_report,
    finalize_broad_research_manifest,
    load_broad_research_breadth,
    link_existing_long_v1_cases,
    record_asset_broad_research,
    record_broad_research_breadth,
)
from swing_broad_context import (  # noqa: E402
    GLOBAL_BENCHMARK,
    REGIONAL_BENCHMARKS,
    build_historical_breadth_context,
)
from swing_broad_research_transition import (  # noqa: E402
    DEFAULT_TRANSITION_DIR,
    broad_transition_identity,
    load_broad_transition_receipt,
    record_broad_transition_receipt,
    validate_broad_research_transition,
)
from swing_research_dataset import (  # noqa: E402
    load_frozen_histories,
    load_research_dataset_manifest,
    normalized_research_history,
)
from swing_research_quality import record_development_quality_ledger  # noqa: E402
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock  # noqa: E402
from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_walk_forward import (  # noqa: E402
    DEFAULT_SWING_WALK_FORWARD_DB_PATH,
    swing_walk_forward_store_audit,
    _prepare_historical_indicators,
)
from swing_walk_forward_campaign import (  # noqa: E402
    DEFAULT_CAMPAIGN_CONFIG_PATH,
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_RESEARCH_LOCK_PATH,
    campaign_active_production_jobs,
    campaign_is_protected_time,
    campaign_jobs,
    campaign_status,
    campaign_week_epoch,
    load_campaign_config,
    load_campaign_state,
)


DEFAULT_FIXED_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)

_WORKER_MANIFEST_PATH: Path | None = None
_WORKER_COT_REPORTS: list[dict] = []
_WORKER_COT_MAPPING: dict = {}
_WORKER_BENCHMARK_HISTORIES: dict[str, pd.DataFrame] = {}
_WORKER_BREADTH_CONTEXT: dict[str, dict] = {}

CHECKPOINT_INTERVAL_ASSETS = 256


def _load_cot_reports(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    connection = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT payload_json FROM cot_reports ORDER BY report_date, available_at, retrieved_at"
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(row[0]) for row in rows]


def _worker_init(manifest_path: str, cot_path: str, database_path: str, dataset_fingerprint: str) -> None:
    global _WORKER_MANIFEST_PATH, _WORKER_COT_REPORTS, _WORKER_COT_MAPPING
    global _WORKER_BENCHMARK_HISTORIES, _WORKER_BREADTH_CONTEXT
    _WORKER_MANIFEST_PATH = Path(manifest_path)
    _WORKER_COT_REPORTS = _load_cot_reports(Path(cot_path))
    _WORKER_COT_MAPPING = load_cot_market_mapping()
    benchmark_symbols = sorted({GLOBAL_BENCHMARK, *REGIONAL_BENCHMARKS.values()})
    _WORKER_BENCHMARK_HISTORIES = {
        symbol: history
        for symbol in benchmark_symbols
        for history, _ in [_history_for_symbol(_WORKER_MANIFEST_PATH, symbol)]
        if not history.empty
    }
    _WORKER_BREADTH_CONTEXT = load_broad_research_breadth(
        dataset_fingerprint=dataset_fingerprint,
        path=Path(database_path),
    )


def _history_for_symbol(manifest_path: Path, symbol: str) -> tuple[pd.DataFrame, str]:
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
        return pd.DataFrame(), str(manifest["dataset_fingerprint"])
    combined = pd.concat(frames).sort_index()
    combined = combined.loc[~combined.index.duplicated(keep="last")]
    return combined, str(manifest["dataset_fingerprint"])


def _worker(asset: dict) -> dict:
    if _WORKER_MANIFEST_PATH is None:
        raise RuntimeError("Broad-Research-Worker wurde nicht initialisiert.")
    symbol = str(asset["ticker"]).upper()
    history, dataset_fingerprint = _history_for_symbol(_WORKER_MANIFEST_PATH, symbol)
    return build_asset_broad_research(
        symbol,
        asset,
        history,
        dataset_fingerprint=dataset_fingerprint,
        cot_reports=_WORKER_COT_REPORTS,
        cot_mapping=_WORKER_COT_MAPPING,
        benchmark_histories=_WORKER_BENCHMARK_HISTORIES,
        breadth_context=_WORKER_BREADTH_CONTEXT,
    )


def _build_frozen_breadth(manifest_path: Path, assets: list[dict]) -> dict[str, dict]:
    def prepared_assets():
        for asset in assets:
            history, _ = _history_for_symbol(manifest_path, str(asset["ticker"]).upper())
            if history.empty:
                continue
            frame = _prepare_historical_indicators(normalized_research_history(history))
            yield asset, frame

    return build_historical_breadth_context(prepared_assets())


def _campaign_status(now: datetime) -> tuple[dict, dict, dict, list[dict]]:
    config = load_campaign_config(DEFAULT_CAMPAIGN_CONFIG_PATH)
    state = load_campaign_state(DEFAULT_CAMPAIGN_STATE_PATH)
    universe = load_swing_universe(DEFAULT_SWING_UNIVERSE_PATH)
    if universe.errors:
        raise RuntimeError("; ".join(universe.errors))
    tickers = [asset.ticker for asset in universe.assets if asset.active]
    active_week = str(state.get("active_week_epoch") or campaign_week_epoch(now))
    jobs = campaign_jobs(config, tickers, now=now, weekly_epoch=active_week)
    return campaign_status(jobs, state), config, state, jobs


def _checkpoint_crossed(
    completed_before: int,
    completed_after: int,
    expected_assets: int,
    *,
    interval: int = CHECKPOINT_INTERVAL_ASSETS,
) -> bool:
    if completed_after >= expected_assets:
        return True
    if interval <= 0 or completed_after <= completed_before:
        return False
    return completed_before // interval < completed_after // interval


def _incremental_block_audit(
    stored_summaries: list[dict[str, object]],
    *,
    completed_before: int,
    completed_after: int,
    expected_assets: int,
) -> dict[str, object]:
    changed = [row for row in stored_summaries if row.get("already_complete") is not True]
    count_mismatches = [
        index
        for index, row in enumerate(changed)
        if not (
            int(row.get("candidates") or 0)
            == int(row.get("labels") or 0)
            == int(row.get("counterfactuals") or 0)
        )
    ]
    completion_delta = completed_after - completed_before
    status = (
        "ok"
        if completion_delta == len(changed) and not count_mismatches
        else "invalid"
    )
    result = {
        "mode": "transactional_incremental_block",
        "status": status,
        "processed_assets": len(stored_summaries),
        "new_asset_completions": completion_delta,
        "asset_completions": completed_after,
        "expected_assets": expected_assets,
        "stored_candidates": sum(int(row.get("candidates") or 0) for row in changed),
        "stored_labels": sum(int(row.get("labels") or 0) for row in changed),
        "stored_counterfactuals": sum(
            int(row.get("counterfactuals") or 0) for row in changed
        ),
        "candidate_label_counterfactual_counts_match": not count_mismatches,
        "append_only_transactions_verified_on_write": True,
        "fingerprints_verified_on_write": True,
    }
    if status != "ok":
        raise RuntimeError(
            "Inkrementelle Broad-Blockprüfung fehlgeschlagen: "
            f"completion_delta={completion_delta}, writes={len(changed)}, "
            f"count_mismatches={count_mismatches}."
        )
    return result


def _next_checkpoint(completed_assets: int, expected_assets: int) -> int:
    if completed_assets >= expected_assets:
        return expected_assets
    next_checkpoint = (
        completed_assets // CHECKPOINT_INTERVAL_ASSETS + 1
    ) * CHECKPOINT_INTERVAL_ASSETS
    return min(next_checkpoint, expected_assets)


def _completion_ledger_checkpoint_audit(
    path: Path,
    *,
    dataset_fingerprint: str,
    expected_assets: int,
) -> dict[str, object]:
    """Verify the small signed completion ledger without scanning research rows."""

    database_path = Path(path).resolve()
    connection = sqlite3.connect(
        f"file:{database_path.as_posix()}?mode=ro",
        uri=True,
        timeout=60,
    )
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT completion_id, symbol, candidates, labels,
            completion_json, completion_fingerprint
            FROM broad_research_asset_completions
            WHERE dataset_fingerprint = ? AND feature_version = ?
            ORDER BY symbol""",
            (dataset_fingerprint, BROAD_RESEARCH_FEATURE_VERSION),
        ).fetchall()
    finally:
        connection.close()

    invalid_receipts: list[str] = []
    total_candidates = 0
    total_labels = 0
    receipt_fingerprints: list[str] = []
    seen_symbols: set[str] = set()
    for row in rows:
        receipt_id = str(row["completion_id"])
        symbol = str(row["symbol"])
        candidate_count = int(row["candidates"])
        label_count = int(row["labels"])
        try:
            receipt = json.loads(str(row["completion_json"]))
            canonical = json.dumps(
                receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            receipt_fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        except (TypeError, ValueError, json.JSONDecodeError):
            invalid_receipts.append(receipt_id)
            continue
        stored_fingerprint = str(row["completion_fingerprint"])
        valid = (
            symbol not in seen_symbols
            and receipt_fingerprint == stored_fingerprint
            and str(receipt.get("symbol") or "") == symbol
            and str(receipt.get("dataset_fingerprint") or "") == dataset_fingerprint
            and str(receipt.get("feature_version") or "") == BROAD_RESEARCH_FEATURE_VERSION
            and int(receipt.get("candidates") or 0) == candidate_count
            and int(receipt.get("labels") or 0) == label_count
            and candidate_count == label_count
            and receipt.get("append_only") is True
        )
        if not valid:
            invalid_receipts.append(receipt_id)
            continue
        seen_symbols.add(symbol)
        total_candidates += candidate_count
        total_labels += label_count
        receipt_fingerprints.append(stored_fingerprint)

    status = (
        "ok"
        if not invalid_receipts and len(rows) <= int(expected_assets)
        else "invalid"
    )
    ledger_payload = {
        "dataset_fingerprint": dataset_fingerprint,
        "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
        "asset_completions": len(rows),
        "expected_assets": int(expected_assets),
        "candidate_count": total_candidates,
        "label_count": total_labels,
        "completion_fingerprints": receipt_fingerprints,
    }
    result = {
        "mode": "signed_completion_ledger",
        "status": status,
        "asset_completions": len(rows),
        "expected_assets": int(expected_assets),
        "candidate_count": total_candidates,
        "label_count": total_labels,
        "candidate_label_counts_match": total_candidates == total_labels,
        "verified_completion_receipts": len(receipt_fingerprints),
        "invalid_completion_receipts": invalid_receipts,
        "ledger_fingerprint": hashlib.sha256(
            json.dumps(
                ledger_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest(),
        "research_row_scan_performed": False,
        "final_full_audit_mandatory": True,
    }
    if status != "ok":
        raise RuntimeError(
            "Broad-Abschlussbelegprüfung fehlgeschlagen: "
            f"assets={len(rows)}/{expected_assets}, invalid={invalid_receipts[:10]}."
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Breiter outcome-unabhängiger Point-in-Time-Swing-Researchlauf."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FIXED_MANIFEST)
    parser.add_argument("--database", type=Path, default=DEFAULT_BROAD_RESEARCH_DB_PATH)
    parser.add_argument("--universe", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--cot-database", type=Path, default=DEFAULT_COT_DB_PATH)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--maximum-assets", type=int, default=None)
    parser.add_argument("--transition-directory", type=Path, default=DEFAULT_TRANSITION_DIR)
    parser.add_argument("--automatic-handoff", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    now = datetime.now().astimezone()
    campaign, campaign_config, campaign_state, campaign_job_rows = _campaign_status(now)
    if args.status_only:
        audit = broad_research_store_audit(args.database)
        print(
            json.dumps(
                {
                    "campaign": campaign,
                    "broad_research": audit,
                    "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
                    "code_fingerprint": broad_research_code_fingerprint(),
                    "feature_contract_fingerprint": broad_research_feature_contract_fingerprint(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if int(campaign.get("jobs_pending") or 0) > 0:
        print(
            json.dumps(
                {
                    "broad_research_skipped": "existing_campaign_not_finished",
                    "campaign": campaign,
                    "existing_campaign_changed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if args.automatic_handoff else 2
    if campaign_is_protected_time(now, campaign_config):
        print(json.dumps({"broad_research_skipped": "protected_production_window"}, ensure_ascii=False))
        return 0 if args.automatic_handoff else 2
    active_production = campaign_active_production_jobs(campaign_config, project_root=PROJECT_ROOT)
    if active_production:
        print(
            json.dumps(
                {"broad_research_skipped": "production_active", "active_production": active_production},
                ensure_ascii=False,
            )
        )
        return 0 if args.automatic_handoff else 2

    manifest = load_research_dataset_manifest(args.manifest)
    dataset_fingerprint = str(manifest["dataset_fingerprint"])
    code_fingerprint = broad_research_code_fingerprint()
    feature_contract_fingerprint = broad_research_feature_contract_fingerprint()
    transition_identity = broad_transition_identity(
        campaign_status=campaign,
        manifest=manifest,
        code_fingerprint=code_fingerprint,
        feature_contract_fingerprint=feature_contract_fingerprint,
    )
    universe = load_swing_universe(args.universe)
    if universe.errors:
        raise RuntimeError("; ".join(universe.errors))
    assets = [asset.as_dict() for asset in universe.assets if asset.active]
    expected_assets = len(assets)
    completed = completed_broad_research_symbols(
        dataset_fingerprint=dataset_fingerprint,
        path=args.database,
    )
    pending = [asset for asset in assets if str(asset["ticker"]).upper() not in completed]
    if args.maximum_assets is not None:
        pending = pending[: max(0, int(args.maximum_assets))]
    workers = max(1, min(int(args.workers), 8))
    transition_receipt: dict[str, object] | None = None
    stored_summaries: list[dict[str, object]] = []
    try:
        with SwingRunLock(DEFAULT_RESEARCH_LOCK_PATH):
            # Recheck every mutable gate after taking the same global research
            # lock as the old campaign.  This cannot restart or edit that queue.
            now = datetime.now().astimezone()
            campaign, campaign_config, campaign_state, campaign_job_rows = _campaign_status(now)
            if int(campaign.get("jobs_pending") or 0) > 0:
                print(
                    json.dumps(
                        {
                            "broad_research_skipped": "existing_campaign_not_finished_after_lock",
                            "campaign": campaign,
                            "existing_campaign_changed": False,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0 if args.automatic_handoff else 2
            if campaign_is_protected_time(now, campaign_config):
                print(json.dumps({"broad_research_skipped": "protected_production_window_after_lock"}, ensure_ascii=False))
                return 0 if args.automatic_handoff else 2
            active_production = campaign_active_production_jobs(
                campaign_config, project_root=PROJECT_ROOT
            )
            if active_production:
                print(
                    json.dumps(
                        {
                            "broad_research_skipped": "production_active_after_lock",
                            "active_production": active_production,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0 if args.automatic_handoff else 2
            transition_identity = broad_transition_identity(
                campaign_status=campaign,
                manifest=manifest,
                code_fingerprint=code_fingerprint,
                feature_contract_fingerprint=feature_contract_fingerprint,
            )
            transition_receipt = load_broad_transition_receipt(
                transition_identity, args.transition_directory
            )
            if transition_receipt is None:
                transition_payload = validate_broad_research_transition(
                    campaign_status=campaign,
                    campaign_state=campaign_state,
                    campaign_jobs=campaign_job_rows,
                    manifest=manifest,
                    walk_forward_audit=swing_walk_forward_store_audit(
                        DEFAULT_SWING_WALK_FORWARD_DB_PATH
                    ),
                    code_fingerprint=code_fingerprint,
                    feature_contract_fingerprint=feature_contract_fingerprint,
                )
                transition_receipt = record_broad_transition_receipt(
                    transition_payload,
                    identity=transition_identity,
                    directory=args.transition_directory,
                )
            existing_breadth = load_broad_research_breadth(
                dataset_fingerprint=dataset_fingerprint,
                path=args.database,
            )
            if not existing_breadth:
                breadth = _build_frozen_breadth(args.manifest, assets)
                record_broad_research_breadth(
                    breadth,
                    dataset_fingerprint=dataset_fingerprint,
                    path=args.database,
                )
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_worker_init,
                initargs=(
                    str(args.manifest),
                    str(args.cot_database),
                    str(args.database),
                    dataset_fingerprint,
                ),
            ) as pool:
                futures = {pool.submit(_worker, asset): str(asset["ticker"]) for asset in pending}
                processed = 0
                for future in as_completed(futures):
                    symbol = futures[future]
                    result = future.result()
                    stored = record_asset_broad_research(
                        result,
                        dataset_fingerprint=dataset_fingerprint,
                        path=args.database,
                    )
                    stored_summaries.append(dict(stored))
                    processed += 1
                    print(
                        json.dumps(
                            {
                                "asset": symbol,
                                "processed": processed,
                                "scheduled": len(pending),
                                "stored": stored,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
    except SwingRunAlreadyActiveError as exc:
        print(json.dumps({"broad_research_skipped": "research_lock_active", "reason": str(exc)}, ensure_ascii=False))
        return 0 if args.automatic_handoff else 2

    completed_after = completed_broad_research_symbols(
        dataset_fingerprint=dataset_fingerprint,
        path=args.database,
    )
    incremental_audit = _incremental_block_audit(
        stored_summaries,
        completed_before=len(completed),
        completed_after=len(completed_after),
        expected_assets=expected_assets,
    )
    checkpoint_due = _checkpoint_crossed(
        len(completed),
        len(completed_after),
        expected_assets,
    )
    output: dict[str, object] = {
        "processed_this_run": len(pending),
        "asset_completions": len(completed_after),
        "expected_assets": expected_assets,
        "incremental_audit": incremental_audit,
        "checkpoint_audit": {
            "status": "deferred_to_checkpoint",
            "checkpoint_interval_assets": CHECKPOINT_INTERVAL_ASSETS,
            "next_checkpoint_assets": _next_checkpoint(
                len(completed_after), expected_assets
            ),
            "mode": "signed_completion_ledger",
            "research_row_scan_performed": False,
        },
        "full_audit": {
            "status": "deferred_to_final_completion",
            "final_full_audit_mandatory": True,
        },
        "code_fingerprint": code_fingerprint,
        "feature_contract_fingerprint": feature_contract_fingerprint,
        "transition_receipt": {
            "transition_fingerprint": transition_receipt.get("transition_fingerprint") if transition_receipt else None,
            "validated_at": transition_receipt.get("validated_at") if transition_receipt else None,
            "append_only": bool(transition_receipt and transition_receipt.get("append_only")),
        },
        "existing_campaign_changed": False,
        "automatic_production_activation": False,
    }
    if checkpoint_due:
        output["checkpoint_audit"] = _completion_ledger_checkpoint_audit(
            args.database,
            dataset_fingerprint=dataset_fingerprint,
            expected_assets=expected_assets,
        )
    if len(completed_after) == expected_assets:
        output["baseline_links"] = link_existing_long_v1_cases(
            DEFAULT_SWING_WALK_FORWARD_DB_PATH,
            path=args.database,
        )
        output["manifest"] = finalize_broad_research_manifest(
            dataset_fingerprint=dataset_fingerprint,
            expected_assets=expected_assets,
            path=args.database,
        )
        output["development_patterns"] = development_pattern_report(args.database)
        output["research_quality_ledger"] = record_development_quality_ledger(
            output["development_patterns"],
            dataset_fingerprint=dataset_fingerprint,
            feature_fingerprint=feature_contract_fingerprint,
            code_fingerprint=code_fingerprint,
            recorded_at=datetime.now().astimezone().isoformat(),
        )
        output["feature_coverage"] = output["manifest"]["feature_coverage"]
        output["full_audit"] = {
            "status": "complete",
            "final_full_audit_mandatory": True,
            "audit": broad_research_store_audit(args.database),
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
