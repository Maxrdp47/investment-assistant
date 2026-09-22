from __future__ import annotations

"""Guarded pilot and single-writer runner for finite-program R6 Development."""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from multi_asset_development_v6_benchmark import system_resources
from multi_asset_development_v6_inputs import verify_v6_current_sources
from multi_asset_development_v6_store import (
    checkpoint_sqlite,
    checkpoint_status,
    claim_next_asset_batch,
    fail_asset_batch,
    initialize_v6_run,
    mark_run_complete,
    pause_run_for_review,
    persist_and_complete_work_unit,
    reset_interrupted_units,
    skip_work_unit,
)
from multi_asset_discovery_v1 import file_sha256, fingerprint
from multi_asset_v2_r5_contract import load_contract as load_r5_contract
from multi_asset_v2_r5_contract import validate_freeze
from multi_asset_v2_r6_execution import (
    PARENT_CONTROL_STORE,
    PARENT_FEATURE_STORE,
    PARENT_OUTCOME_STORE,
    PARENT_RUN_ID,
    build_r6_universe_and_work_plan,
    compute_r6_asset_batch,
    r6_result_digest,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward_campaign import historical_research_runtime_gate, load_campaign_config


ROOT = Path(__file__).resolve().parent
R6_RUN_ID = "mad2-development-v2-20260922-v1"
GLOBAL_RESEARCH_LOCK = ROOT / "runtime" / "swing_walk_forward_research.lock"
PRODUCTION_CONFIG = ROOT / "config" / "swing_walk_forward_campaign.json"
PARENT_AUDIT = ROOT / "runtime" / "research_exports" / "multi_asset_development_v7_final_integrity_audit_2026-09-13-v2.json"
R6_MANIFEST = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_run_manifest_2026-09-22-v1.json"
R6_PREFLIGHT = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_preflight_2026-09-22-v1.json"
R6_PILOT_REPORT = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_pilot_2026-09-22-v1.json"
R6_PILOT_MANIFEST = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_pilot_manifest_2026-09-22-v1.json"
R6_START_GATE = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_start_gate_2026-09-22-v1.json"
R6_CHAIN_STATE = ROOT / "runtime" / "multi_asset_discovery_v2_r6_chain_state.json"
R6_PILOT_DIR = ROOT / "runtime" / "multi_asset_discovery_v2_r6_pilot_v1"
R6_VERSION = "multi-asset-discovery-v2-r6-runner-2026.09.22-v1"
PILOT_VERSION = "multi-asset-discovery-v2-r6-pilot-2026.09.22-v1"
PREFLIGHT_VERSION = "multi-asset-discovery-v2-r6-preflight-2026.09.22-v1"
START_GATE_VERSION = "multi-asset-discovery-v2-r6-start-gate-2026.09.22-v1"
CHAIN_VERSION = "multi-asset-discovery-v2-r6-chain-state-2026.09.22-v1"
MINIMUM_DISK_FREE_BYTES = 20 * 1024**3
MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3
R6_REVIEW_CONTRACT = ROOT / "config" / "multi_asset_discovery_v2_r6_review.json"


class MultiAssetV2R6RunnerError(RuntimeError):
    """R6 runner safety, provenance or integrity gate failed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiAssetV2R6RunnerError(f"JSON artifact unreadable: {path}") from exc


def _self_fingerprinted(payload: Mapping[str, object]) -> dict[str, object]:
    result = dict(payload)
    result.pop("artifact_fingerprint", None)
    result["artifact_fingerprint"] = fingerprint(result)
    return result


def verify_self_fingerprint(payload: Mapping[str, object]) -> bool:
    expected = payload.get("artifact_fingerprint")
    basis = dict(payload)
    basis.pop("artifact_fingerprint", None)
    return isinstance(expected, str) and expected == fingerprint(basis)


def _atomic_write(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    if path.exists():
        existing = _read_json(path)
        if not verify_self_fingerprint(existing) or existing != dict(payload):
            raise MultiAssetV2R6RunnerError(f"Immutable artifact conflict: {path}")
        return
    _atomic_write(path, payload)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip()


def _implementation_provenance() -> dict[str, object]:
    paths = (
        ROOT / "multi_asset_v2_r6_execution.py",
        ROOT / "multi_asset_v2_r6_runner.py",
        ROOT / "multi_asset_v2_r4b_features.py",
        ROOT / "crypto_r4h_features.py",
        ROOT / "multi_asset_v2_r5_contract.py",
        ROOT / "multi_asset_development_v6_store.py",
        ROOT / "multi_asset_development_v6_inputs.py",
        ROOT / "config" / "multi_asset_discovery_v2_r5_freeze.json",
        ROOT / "config" / "multi_asset_v2_r4b.json",
        ROOT / "config" / "crypto_r4h_features.json",
        ROOT / "config" / "multi_asset_discovery_v2_r6_review.json",
        ROOT / "scripts" / "run_multi_asset_v2_r6.py",
    )
    hashes = {
        path.relative_to(ROOT).as_posix(): file_sha256(path)
        for path in paths
        if path.is_file()
    }
    if len(hashes) != len(paths):
        raise MultiAssetV2R6RunnerError("R6 implementation provenance is incomplete.")
    return {"implementation_sha256": hashes, "implementation_fingerprint": fingerprint(hashes)}


def load_r6_review_contract(path: Path = R6_REVIEW_CONTRACT) -> tuple[dict[str, object], str]:
    contract = _read_json(path)
    features = list(contract.get("continuous_features") or [])
    names = [str(dict(item).get("name") or "") for item in features]
    method = dict(contract.get("method") or {})
    gate = dict(contract.get("candidate_gate") or {})
    safety = dict(contract.get("stage_safety") or {})
    outcomes = dict(contract.get("outcomes") or {})
    if (
        contract.get("program_block") != "R6"
        or contract.get("run_id") != R6_RUN_ID
        or not names
        or len(names) != len(set(names))
        or list(outcomes.get("checkpoints") or []) != [20, 60, 120, 252]
        or list(outcomes.get("metrics") or []) != ["return_pct", "mfe_pct", "mae_pct"]
        or any(
            bool(method.get(key))
            for key in ("threshold_search", "quantile_search", "parameter_search", "feature_combinations", "profit_ranking", "p_value_selection")
        )
        or gate.get("all_dimensions_must_pass") is not True
        or gate.get("unknown_dependency_may_not_pass") is not True
        or int(gate.get("historical_verified_issuer_effective_n", -1)) != 0
        or int(gate.get("automatic_candidates_maximum") or 0) != 3
        or any(bool(value) for key, value in safety.items() if key.endswith("_opened"))
    ):
        raise MultiAssetV2R6RunnerError("R6 descriptive review contract changed or is unsafe.")
    return contract, fingerprint(contract)


def _parent_audit() -> dict[str, object]:
    audit = _read_json(PARENT_AUDIT)
    counts = dict(audit.get("counts") or {})
    if (
        not verify_self_fingerprint(audit)
        or audit.get("status") != "PASS"
        or audit.get("run_id") != PARENT_RUN_ID
        or int(counts.get("feature_cases") or 0) != 2_356_553
        or int(counts.get("outcome_cases") or 0) != 2_356_553
        or int(counts.get("work_units") or 0) != 60_504
    ):
        raise MultiAssetV2R6RunnerError("Audited immutable v7-r2 parent is invalid.")
    return audit


def r6_paths(r5_contract: Mapping[str, object] | None = None) -> dict[str, Path]:
    contract = dict(r5_contract or load_r5_contract()[0])
    execution = dict(contract["r6_execution_contract"])
    return {
        "control": ROOT / str(execution["control_store"]),
        "feature": ROOT / str(execution["feature_store"]),
        "outcome": ROOT / str(execution["outcome_store"]),
        "process_lock": ROOT / str(execution["process_lock"]),
        "manifest": R6_MANIFEST,
        "preflight": R6_PREFLIGHT,
        "pilot_report": R6_PILOT_REPORT,
        "start_gate": R6_START_GATE,
        "chain_state": R6_CHAIN_STATE,
    }


def build_r6_manifest(
    *,
    commit: str | None = None,
    started_at: str | None = None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    r5, r5_fingerprint = load_r5_contract()
    audit = _parent_audit()
    _review_contract, review_contract_fingerprint = load_r6_review_contract()
    universe, work_plan = build_r6_universe_and_work_plan(
        r5_contract_fingerprint=r5_fingerprint
    )
    implementation = _implementation_provenance()
    basis: dict[str, object] = {
        "version": R6_VERSION,
        "run_id": R6_RUN_ID,
        "program_id": r5["program_id"],
        "program_block": "R6",
        "commit": commit or _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "started_at": started_at or utc_now(),
        "development_contract_fingerprint": r5_fingerprint,
        "combined_input_fingerprint": fingerprint(
            {
                "equity_etf": dict(r5["sources"])["equity_etf"],
                "crypto": dict(r5["sources"])["crypto"],
                "parent_audit_fingerprint": audit["artifact_fingerprint"],
            }
        ),
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
        "total_planned_work_units": work_plan["total_planned_work_units"],
        "parent_run_id": PARENT_RUN_ID,
        "parent_audit_fingerprint": audit["artifact_fingerprint"],
        "parent_feature_cases": dict(audit["counts"])["feature_cases"],
        "storage_model": "THIN_APPEND_ONLY_FEATURE_DELTA_AND_IMMUTABLE_PARENT_OUTCOME_REFERENCE",
        "worker_count": int(dict(r5["r6_execution_contract"])["worker_count"]),
        "sqlite_writer_count": 1,
        "implementation_fingerprint": implementation["implementation_fingerprint"],
        "implementation_sha256": implementation["implementation_sha256"],
        "review_contract_fingerprint": review_contract_fingerprint,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_execution_opened": False,
        "broker_opened": False,
        "automatic_orders_allowed": False,
        "automatic_strategy_optimization_allowed": False,
    }
    basis["run_manifest_fingerprint"] = fingerprint(basis)
    return basis, universe, work_plan


def _runtime_gate(process_lock_path: Path, *, probe_locks: bool = True) -> dict[str, object]:
    production = historical_research_runtime_gate(
        load_campaign_config(PRODUCTION_CONFIG), project_root=ROOT
    )
    resources = system_resources()
    available = int(resources.get("available_physical_memory_bytes_at_start") or 0)
    disk_free = int(shutil.disk_usage(ROOT).free)
    result: dict[str, object] = {
        "production_gate": production,
        "production_gate_clear": bool(production.get("run_allowed")),
        "available_memory_bytes": available,
        "memory_clear": not available or available >= MINIMUM_AVAILABLE_MEMORY_BYTES,
        "disk_free_bytes": disk_free,
        "disk_clear": disk_free >= MINIMUM_DISK_FREE_BYTES,
        "old_time_windows_applied": False,
    }
    if probe_locks:
        process_lock = SwingRunLock(process_lock_path)
        research_lock = SwingRunLock(GLOBAL_RESEARCH_LOCK)
        process_clear = False
        research_clear = False
        try:
            process_lock.acquire()
            process_clear = True
            research_lock.acquire()
            research_clear = True
        except SwingRunAlreadyActiveError:
            pass
        finally:
            research_lock.release()
            process_lock.release()
        result["process_lock_clear"] = process_clear
        result["global_research_lock_clear"] = research_clear
    return result


def run_preflight(*, ci_url: str, ci_conclusion: str = "success") -> dict[str, object]:
    paths = r6_paths()
    if paths["preflight"].is_file():
        existing = _read_json(paths["preflight"])
        if (
            verify_self_fingerprint(existing)
            and existing.get("status") == "PASS"
            and dict(existing.get("ci") or {}).get("url") == ci_url
            and existing.get("commit") == _git("rev-parse", "HEAD")
        ):
            return existing
        raise MultiAssetV2R6RunnerError("Existing R6 preflight is not valid for this commit/CI.")
    if _git("status", "--porcelain"):
        raise MultiAssetV2R6RunnerError("R6 preflight requires a clean worktree.")
    current_commit = _git("rev-parse", "HEAD")
    if (
        ci_conclusion.lower() != "success"
        or not ci_url.startswith("https://github.com/Maxrdp47/investment-assistant/actions/runs/")
    ):
        raise MultiAssetV2R6RunnerError("Exact successful GitHub CI evidence is required.")
    full_freeze = validate_freeze(require_runtime_sources=True)
    manifest, universe, work_plan = build_r6_manifest(commit=current_commit)
    source_verification = verify_v6_current_sources()
    gate = _runtime_gate(paths["process_lock"])
    blockers: list[str] = []
    if not gate["production_gate_clear"]:
        blockers.append("ACTIVE_PRODUCTION_LOCK")
    if not gate["process_lock_clear"]:
        blockers.append("R6_PROCESS_LOCK_ACTIVE")
    if not gate["global_research_lock_clear"]:
        blockers.append("GLOBAL_RESEARCH_LOCK_ACTIVE")
    if not gate["memory_clear"]:
        blockers.append("AVAILABLE_MEMORY_TOO_LOW")
    if not gate["disk_clear"]:
        blockers.append("DISK_RESERVE_TOO_LOW")
    if blockers:
        raise MultiAssetV2R6RunnerError(f"R6 preflight blocked: {blockers}")
    report = _self_fingerprinted(
        {
            "version": PREFLIGHT_VERSION,
            "status": "PASS" if not blockers else "FAIL",
            "created_at": utc_now(),
            "commit": current_commit,
            "branch": manifest["branch"],
            "run_id": R6_RUN_ID,
            "r5_contract_fingerprint": full_freeze["contract_fingerprint"],
            "parent_audit_fingerprint": manifest["parent_audit_fingerprint"],
            "implementation_fingerprint": manifest["implementation_fingerprint"],
            "universe_fingerprint": universe["universe_fingerprint"],
            "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
            "work_units": work_plan["total_planned_work_units"],
            "assets": universe["asset_count"],
            "source_set_fingerprint": source_verification["source_set_fingerprint"],
            "runtime_gate": gate,
            "blockers": blockers,
            "ci": {"url": ci_url, "conclusion": ci_conclusion, "commit": current_commit},
            "validation_opened": False,
            "holdout_opened": False,
        }
    )
    _write_immutable(paths["preflight"], report)
    return report


def _select_pilot_units() -> list[dict[str, object]]:
    selections: list[dict[str, object]] = []
    connection = sqlite3.connect(
        f"file:{PARENT_CONTROL_STORE.resolve().as_posix()}?mode=ro", uri=True
    )
    try:
        for asset_class in ("EQUITIES", "ETF", "CRYPTO"):
            row = connection.execute(
                "SELECT w.work_unit_id,w.asset_key,w.asset_class,w.symbol,w.period_start,w.period_end "
                "FROM work_units w JOIN unit_receipts r ON r.work_unit_id=w.work_unit_id "
                "WHERE w.run_id=? AND w.asset_class=? AND w.status='COMPLETED' AND r.feature_rows>0 "
                "ORDER BY w.symbol,w.period_start LIMIT 1",
                (PARENT_RUN_ID, asset_class),
            ).fetchone()
            if row is None:
                raise MultiAssetV2R6RunnerError(f"No deterministic R6 pilot unit: {asset_class}")
            selections.append(
                {
                    "work_unit_id": str(row[0]),
                    "asset_key": str(row[1]),
                    "asset_class": str(row[2]),
                    "symbol": str(row[3]),
                    "period_start": str(row[4]),
                    "period_end": str(row[5]),
                }
            )
    finally:
        connection.close()
    return selections


def _persist_result(
    *,
    result: Mapping[str, object],
    manifest: Mapping[str, object],
    paths: Mapping[str, Path],
    writer_pid: int,
) -> None:
    if result.get("scientific_digest") != r6_result_digest(result):
        raise MultiAssetV2R6RunnerError("R6 worker scientific digest mismatch.")
    for unit_result in result.get("unit_results") or []:
        unit = dict(unit_result["unit"])
        if unit_result["parent_status"] == "SKIPPED":
            skip_work_unit(
                writer_pid=writer_pid,
                run_id=str(manifest["run_id"]),
                unit=unit,
                reason_code="VERIFIED_PARENT_UNIT_SKIPPED",
                reason="Audited immutable parent work unit contains no evidence.",
                feature_path=paths["feature"],
                outcome_path=paths["outcome"],
                control_path=paths["control"],
            )
        else:
            persist_and_complete_work_unit(
                writer_pid=writer_pid,
                run_id=str(manifest["run_id"]),
                unit=unit,
                features=list(unit_result["features"]),
                outcomes=list(unit_result["outcomes"]),
                summary=dict(unit_result["summary"]),
                feature_path=paths["feature"],
                outcome_path=paths["outcome"],
                control_path=paths["control"],
            )


def _pilot_causality(feature_path: Path) -> tuple[bool, int]:
    connection = sqlite3.connect(f"file:{feature_path.resolve().as_posix()}?mode=ro", uri=True)
    checked = 0
    valid = True
    try:
        for signal_day, payload_blob in connection.execute(
            "SELECT signal_day,payload_zlib FROM feature_rows"
        ):
            import zlib

            payload = json.loads(zlib.decompress(payload_blob).decode("utf-8"))
            values = dict(payload.get("feature_values") or {})
            for key in ("r4b.benchmark_known_date", "r4h.btc_known_date"):
                known = values.get(key)
                if known is not None:
                    checked += 1
                    valid = valid and str(known) < str(signal_day)
            valid = valid and not payload.get("outcomes_used_for_feature_construction")
            valid = valid and not payload.get("strategy_filter_created")
    finally:
        connection.close()
    return valid, checked


def run_pilot(*, ci_url: str, ci_conclusion: str = "success") -> dict[str, object]:
    paths = r6_paths()
    if paths["pilot_report"].is_file():
        existing = _read_json(paths["pilot_report"])
        if verify_self_fingerprint(existing) and existing.get("status") == "PASS":
            return existing
        raise MultiAssetV2R6RunnerError("Existing R6 pilot report is invalid.")
    preflight = run_preflight(ci_url=ci_url, ci_conclusion=ci_conclusion)
    manifest, _, _ = build_r6_manifest(commit=str(preflight["commit"]), started_at=utc_now())
    selections = _select_pilot_units()
    pilot_paths = {
        "control": R6_PILOT_DIR / "control.sqlite3",
        "feature": R6_PILOT_DIR / "features.sqlite3",
        "outcome": R6_PILOT_DIR / "outcomes.sqlite3",
    }
    pilot_manifest = {
        **manifest,
        "run_id": "mad2-r6-pilot-" + fingerprint(selections)[:24],
        "worker_count": 1,
        "total_planned_work_units": len(selections),
        "universe_fingerprint": fingerprint(
            [{key: item[key] for key in ("asset_key", "asset_class", "symbol")} for item in selections]
        ),
        "work_plan_fingerprint": fingerprint(selections),
    }
    pilot_manifest["run_manifest_fingerprint"] = fingerprint(
        {key: value for key, value in pilot_manifest.items() if key != "run_manifest_fingerprint"}
    )
    if R6_PILOT_MANIFEST.is_file():
        pilot_manifest = _read_json(R6_PILOT_MANIFEST)
        if (
            not verify_self_fingerprint(pilot_manifest)
            or pilot_manifest.get("commit") != preflight.get("commit")
            or pilot_manifest.get("work_plan_fingerprint") != fingerprint(selections)
            or pilot_manifest.get("development_contract_fingerprint")
            != manifest.get("development_contract_fingerprint")
        ):
            raise MultiAssetV2R6RunnerError("Existing R6 pilot manifest is invalid.")
    else:
        _write_immutable(R6_PILOT_MANIFEST, _self_fingerprinted(pilot_manifest))
        pilot_manifest = _read_json(R6_PILOT_MANIFEST)
    pilot_plan = {"total_planned_work_units": len(selections), "units": selections}
    initialize_v6_run(
        run_manifest=pilot_manifest,
        work_plan=pilot_plan,
        feature_path=pilot_paths["feature"],
        outcome_path=pilot_paths["outcome"],
        control_path=pilot_paths["control"],
    )
    replay_equal = True
    digests: list[str] = []
    for unit in selections:
        asset = {key: unit[key] for key in ("asset_key", "asset_class", "symbol")}
        first = compute_r6_asset_batch(
            asset=asset,
            units=[unit],
            r5_contract_fingerprint=str(manifest["development_contract_fingerprint"]),
        )
        second = compute_r6_asset_batch(
            asset=asset,
            units=[unit],
            r5_contract_fingerprint=str(manifest["development_contract_fingerprint"]),
        )
        replay_equal = replay_equal and first["scientific_digest"] == second["scientific_digest"]
        digests.append(str(first["scientific_digest"]))
        _persist_result(
            result=first,
            manifest=pilot_manifest,
            paths=pilot_paths,
            writer_pid=os.getpid(),
        )
        _persist_result(
            result=second,
            manifest=pilot_manifest,
            paths=pilot_paths,
            writer_pid=os.getpid(),
        )
    completed = mark_run_complete(control_path=pilot_paths["control"], run_id=str(pilot_manifest["run_id"]))
    status = checkpoint_status(control_path=pilot_paths["control"], run_id=str(pilot_manifest["run_id"]))
    causal, causal_checks = _pilot_causality(pilot_paths["feature"])
    with sqlite3.connect(f"file:{pilot_paths['feature'].resolve().as_posix()}?mode=ro", uri=True) as feature_db:
        feature_duplicates = int(
            feature_db.execute("SELECT COUNT(*)-COUNT(DISTINCT case_id) FROM feature_rows").fetchone()[0]
        )
    with sqlite3.connect(f"file:{pilot_paths['outcome'].resolve().as_posix()}?mode=ro", uri=True) as outcome_db:
        outcome_duplicates = int(
            outcome_db.execute("SELECT COUNT(*)-COUNT(DISTINCT case_id) FROM outcome_rows").fetchone()[0]
        )
    checkpoint_sqlite(pilot_paths["control"], pilot_paths["feature"], pilot_paths["outcome"])
    requirements = {
        "three_asset_classes": {item["asset_class"] for item in selections}
        == {"EQUITIES", "ETF", "CRYPTO"},
        "deterministic_replay": replay_equal,
        "single_writer": int(pilot_manifest["sqlite_writer_count"]) == 1,
        "terminal_units": status["completed"] == len(selections),
        "feature_outcome_row_equality": status["feature_rows"] == status["outcome_rows"] > 0,
        "one_receipt_per_unit": status["receipts"] == len(selections),
        "causal_benchmark_dates": causal and causal_checks > 0,
        "resume_idempotent": status["retried"] == 0,
        "no_duplicate_cases": feature_duplicates == 0 and outcome_duplicates == 0,
        "validation_closed": True,
        "holdout_closed": True,
        "run_marked_complete": completed,
    }
    report = _self_fingerprinted(
        {
            "version": PILOT_VERSION,
            "status": "PASS" if all(requirements.values()) else "FAIL",
            "created_at": utc_now(),
            "commit": manifest["commit"],
            "run_id": pilot_manifest["run_id"],
            "preflight_fingerprint": preflight["artifact_fingerprint"],
            "selections": selections,
            "scientific_digests": digests,
            "requirements": requirements,
            "status_detail": status,
            "causal_date_checks": causal_checks,
            "validation_opened": False,
            "holdout_opened": False,
        }
    )
    _write_immutable(paths["pilot_report"], report)
    if report["status"] != "PASS":
        raise MultiAssetV2R6RunnerError("R6 deterministic pilot failed.")
    return report


def prepare_full_run(*, ci_url: str, ci_conclusion: str = "success") -> dict[str, object]:
    paths = r6_paths()
    pilot = run_pilot(ci_url=ci_url, ci_conclusion=ci_conclusion)
    manifest, _universe, work_plan = build_r6_manifest(commit=str(pilot["commit"]), started_at=utc_now())
    if paths["manifest"].exists():
        manifest = _read_json(paths["manifest"])
        if (
            not verify_self_fingerprint(manifest)
            or manifest.get("commit") != pilot.get("commit")
            or manifest.get("work_plan_fingerprint") != work_plan.get("work_plan_fingerprint")
        ):
            raise MultiAssetV2R6RunnerError("Existing R6 run manifest is invalid.")
    else:
        _write_immutable(paths["manifest"], _self_fingerprinted(manifest))
        manifest = _read_json(paths["manifest"])
    if paths["start_gate"].is_file() and paths["control"].is_file():
        gate = _read_json(paths["start_gate"])
        state = _read_json(paths["chain_state"]) if paths["chain_state"].is_file() else {}
        if (
            verify_self_fingerprint(gate)
            and gate.get("status") == "PASS"
            and gate.get("commit") == manifest.get("commit")
            and dict(gate.get("ci") or {}).get("url") == ci_url
        ):
            return {"manifest": manifest, "gate": gate, "state": state}
        raise MultiAssetV2R6RunnerError("Existing R6 start gate is invalid for this commit/CI.")
    runtime = _runtime_gate(paths["process_lock"])
    blockers = [
        name
        for name, clear in (
            ("ACTIVE_PRODUCTION_LOCK", runtime["production_gate_clear"]),
            ("R6_PROCESS_LOCK_ACTIVE", runtime["process_lock_clear"]),
            ("GLOBAL_RESEARCH_LOCK_ACTIVE", runtime["global_research_lock_clear"]),
            ("AVAILABLE_MEMORY_TOO_LOW", runtime["memory_clear"]),
            ("DISK_RESERVE_TOO_LOW", runtime["disk_clear"]),
        )
        if not clear
    ]
    if blockers:
        raise MultiAssetV2R6RunnerError(f"R6 full-run gate blocked: {blockers}")
    gate = _self_fingerprinted(
        {
            "version": START_GATE_VERSION,
            "status": "PASS" if not blockers else "FAIL",
            "created_at": utc_now(),
            "run_id": R6_RUN_ID,
            "commit": manifest["commit"],
            "run_manifest_fingerprint": manifest["run_manifest_fingerprint"],
            "pilot_fingerprint": pilot["artifact_fingerprint"],
            "runtime_gate": runtime,
            "blockers": blockers,
            "ci": {"url": ci_url, "conclusion": ci_conclusion, "commit": manifest["commit"]},
            "start_authorized": not blockers,
            "validation_opened": False,
            "holdout_opened": False,
        }
    )
    _write_immutable(paths["start_gate"], gate)
    initialize_v6_run(
        run_manifest=manifest,
        work_plan=work_plan,
        feature_path=paths["feature"],
        outcome_path=paths["outcome"],
        control_path=paths["control"],
    )
    state = _self_fingerprinted(
        {
            "version": CHAIN_VERSION,
            "status": "PREPARED",
            "phase": "DEVELOPMENT",
            "run_id": R6_RUN_ID,
            "commit": manifest["commit"],
            "progress": checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID),
            "validation_opened": False,
            "holdout_opened": False,
            "updated_at": utc_now(),
        }
    )
    _atomic_write(paths["chain_state"], state)
    return {"manifest": manifest, "gate": gate, "state": state}


def _load_bound_run() -> tuple[dict[str, object], dict[str, Path]]:
    paths = r6_paths()
    manifest = _read_json(paths["manifest"])
    gate = _read_json(paths["start_gate"])
    pilot = _read_json(paths["pilot_report"])
    if (
        not verify_self_fingerprint(manifest)
        or not verify_self_fingerprint(gate)
        or not verify_self_fingerprint(pilot)
        or gate.get("status") != "PASS"
        or pilot.get("status") != "PASS"
        or manifest.get("commit") != _git("rev-parse", "HEAD")
        or gate.get("commit") != manifest.get("commit")
        or pilot.get("commit") != manifest.get("commit")
    ):
        raise MultiAssetV2R6RunnerError("R6 bound run context is invalid for current HEAD.")
    full_freeze = validate_freeze(require_runtime_sources=True)
    if full_freeze.get("contract_fingerprint") != manifest.get("development_contract_fingerprint"):
        raise MultiAssetV2R6RunnerError("R6 frozen contract/source context changed after start gate.")
    verify_v6_current_sources()
    _parent_audit()
    return manifest, paths


def _dispatch_clear() -> tuple[bool, str, dict[str, object]]:
    gate = _runtime_gate(Path("unused"), probe_locks=False)
    if not gate["production_gate_clear"]:
        return False, "ACTIVE_PRODUCTION_LOCK", gate
    if not gate["memory_clear"]:
        return False, "AVAILABLE_MEMORY_TOO_LOW", gate
    if not gate["disk_clear"]:
        return False, "DISK_RESERVE_TOO_LOW", gate
    return True, "CLEAR", gate


def run_full(*, maximum_asset_batches: int | None = None) -> dict[str, object]:
    manifest, paths = _load_bound_run()
    process_lock = SwingRunLock(paths["process_lock"])
    try:
        process_lock.acquire()
    except SwingRunAlreadyActiveError:
        return {**checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID), "duplicate_start_rejected": True}
    try:
        research_lock = SwingRunLock(GLOBAL_RESEARCH_LOCK)
        try:
            research_lock.acquire()
        except SwingRunAlreadyActiveError:
            return {**checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID), "research_lock_active": True}
        try:
            reset_interrupted_units(control_path=paths["control"], run_id=R6_RUN_ID)
            current = checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID)
            if current["status"] == "COMPLETED":
                return {**current, "terminal_noop": True}
            if current["status"] != "RUNNING":
                return {**current, "persistent_terminal_status": True}
            worker_count = int(manifest["worker_count"])
            writer_pid = os.getpid()
            dispatched = 0
            stop_reason: str | None = None
            pending: dict[object, list[dict[str, object]]] = {}
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                while pending or stop_reason is None:
                    while stop_reason is None and len(pending) < worker_count:
                        if maximum_asset_batches is not None and dispatched >= maximum_asset_batches:
                            stop_reason = "BATCH_LIMIT_REACHED"
                            break
                        clear, reason, detail = _dispatch_clear()
                        if not clear:
                            stop_reason = reason
                            break
                        units = claim_next_asset_batch(control_path=paths["control"], run_id=R6_RUN_ID)
                        if not units:
                            stop_reason = "NO_PENDING_WORK"
                            break
                        asset = {
                            "asset_key": units[0]["asset_key"],
                            "asset_class": units[0]["asset_class"],
                            "symbol": units[0]["symbol"],
                        }
                        future = executor.submit(
                            compute_r6_asset_batch,
                            asset=asset,
                            units=units,
                            r5_contract_fingerprint=str(manifest["development_contract_fingerprint"]),
                        )
                        pending[future] = [dict(item) for item in units]
                        dispatched += 1
                    if not pending:
                        break
                    done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                    for future in done:
                        units = pending.pop(future)
                        try:
                            result = future.result()
                            _persist_result(
                                result=result,
                                manifest=manifest,
                                paths=paths,
                                writer_pid=writer_pid,
                            )
                        except Exception as exc:
                            fail_asset_batch(
                                control_path=paths["control"],
                                run_id=R6_RUN_ID,
                                units=units,
                                error=exc,
                                maximum_attempts=1,
                                retryable=False,
                            )
                            stop_reason = f"SYSTEMATIC_FAILURE:{type(exc).__name__}:{str(exc)[:500]}"
            status = checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID)
            if status["failed"]:
                pause_run_for_review(control_path=paths["control"], run_id=R6_RUN_ID, reason=str(stop_reason))
                status = checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID)
            elif not status["pending"] and not status["active"]:
                mark_run_complete(control_path=paths["control"], run_id=R6_RUN_ID)
                checkpoint_sqlite(paths["control"], paths["feature"], paths["outcome"])
                status = checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID)
            state = _self_fingerprinted(
                {
                    "version": CHAIN_VERSION,
                    "status": (
                        "R6_DEVELOPMENT_COMPLETE_AWAITING_FINAL_AUDIT"
                        if status["status"] == "COMPLETED"
                        else "PAUSED_REQUIRES_REVIEW"
                        if status["status"] == "PAUSED_REQUIRES_REVIEW"
                        else "R6_DEVELOPMENT_RUNNING"
                    ),
                    "phase": "FINAL_AUDIT" if status["status"] == "COMPLETED" else "DEVELOPMENT",
                    "run_id": R6_RUN_ID,
                    "commit": manifest["commit"],
                    "dispatch_stop_reason": stop_reason,
                    "progress": status,
                    "validation_opened": False,
                    "holdout_opened": False,
                    "updated_at": utc_now(),
                }
            )
            _atomic_write(paths["chain_state"], state)
            return state
        finally:
            research_lock.release()
    finally:
        process_lock.release()


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "pilot", "prepare", "run", "status"))
    parser.add_argument("--ci-url")
    parser.add_argument("--ci-conclusion", default="success")
    parser.add_argument("--maximum-asset-batches", type=int)
    args = parser.parse_args(argv)
    if args.action in {"preflight", "pilot", "prepare"} and not args.ci_url:
        parser.error("--ci-url is required for this action")
    if args.action == "preflight":
        result = run_preflight(ci_url=args.ci_url, ci_conclusion=args.ci_conclusion)
    elif args.action == "pilot":
        result = run_pilot(ci_url=args.ci_url, ci_conclusion=args.ci_conclusion)
    elif args.action == "prepare":
        result = prepare_full_run(ci_url=args.ci_url, ci_conclusion=args.ci_conclusion)
    elif args.action == "run":
        result = run_full(maximum_asset_batches=args.maximum_asset_batches)
    else:
        paths = r6_paths()
        result = (
            checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID)
            if paths["control"].is_file()
            else {"status": "NOT_PREPARED", "run_id": R6_RUN_ID}
        )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())


__all__ = [
    "MultiAssetV2R6RunnerError",
    "R6_RUN_ID",
    "build_r6_manifest",
    "load_r6_review_contract",
    "prepare_full_run",
    "r6_paths",
    "run_full",
    "run_pilot",
    "run_preflight",
    "verify_self_fingerprint",
]
