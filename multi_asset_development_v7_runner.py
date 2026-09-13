from __future__ import annotations

"""Persistent, fail-closed runner for the Development-v7 recovery run."""

import copy
import errno
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from multi_asset_development_v6_benchmark import system_resources
from multi_asset_development_v6_execution import (
    compute_v6_asset_batch,
    is_retryable_compute_error,
    result_scientific_digest,
)
from multi_asset_development_v6_inputs import verify_v6_current_sources
from multi_asset_development_v6_runner import (
    _StayAwake,
    _process_result,
    _set_below_normal_priority,
)
from multi_asset_development_v6_store import (
    append_run_event,
    checkpoint_sqlite,
    checkpoint_status,
    claim_next_asset_batch,
    decode_payload,
    fail_asset_batch,
    mark_run_complete,
    pause_run_for_review,
    reset_interrupted_units,
)
from multi_asset_development_v7_recovery import (
    AUDIT_VERSION,
    CHAIN_VERSION,
    DEFAULT_CONFIG_PATH,
    REPORT_VERSION,
    RUN_MANIFEST_VERSION,
    START_GATE_VERSION,
    SUMMARY_VERSION,
    DevelopmentV7RecoveryError,
    _connection,
    _git,
    _parent_bundle,
    _read_json,
    _self_fingerprinted,
    _write_immutable,
    build_recovery_contract,
    build_universe_and_work_plan,
    load_recovery_config,
    recovery_paths,
    verify_self_fingerprint,
)
from multi_asset_discovery_v1 import file_sha256, fingerprint
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward_campaign import historical_research_runtime_gate, load_campaign_config


PROJECT_ROOT = Path(__file__).resolve().parent
RUNNER_VERSION = "multi-asset-development-v7-recovery-runner-2026.09.13-v2"
GLOBAL_RESEARCH_LOCK = PROJECT_ROOT / "runtime" / "swing_walk_forward_research.lock"


class DevelopmentV7RunnerError(RuntimeError):
    """The v7 runner cannot advance without violating its frozen gate."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("multi_asset_development_v7_recovery")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _manifest_valid(manifest: Mapping[str, object]) -> bool:
    basis = copy.deepcopy(dict(manifest))
    claimed = basis.pop("run_manifest_fingerprint", None)
    return manifest.get("version") == RUN_MANIFEST_VERSION and claimed == fingerprint(basis)


def _closed_safety(payload: Mapping[str, object]) -> bool:
    return payload.get("development_only") is True and not any(
        bool(payload.get(name))
        for name in (
            "validation_opened",
            "holdout_opened",
            "external_opened",
            "forward_opened",
            "paper_opened",
            "shadow_opened",
            "broker_opened",
            "automatic_orders_allowed",
            "automatic_strategy_optimization_allowed",
        )
    )


def _load_bound_context(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> tuple[dict[str, object], dict[str, Path], dict[str, object], dict[str, object], dict[str, object]]:
    config = load_recovery_config(config_path)
    paths = recovery_paths(config, project_root=PROJECT_ROOT)
    gate = _read_json(paths["start_gate"])
    manifest = _read_json(paths["run_manifest"])
    contract_artifact = _read_json(paths["contract_artifact"])
    if not verify_self_fingerprint(gate) or gate.get("version") != START_GATE_VERSION:
        raise DevelopmentV7RunnerError("v7 start gate is invalid.")
    if gate.get("status") != "PASS" or gate.get("start_authorized") is not True:
        raise DevelopmentV7RunnerError("v7 start gate is not PASS.")
    if gate.get("blockers") != []:
        raise DevelopmentV7RunnerError("v7 start gate contains blockers.")
    if not _manifest_valid(manifest):
        raise DevelopmentV7RunnerError("v7 run manifest is invalid.")
    if not verify_self_fingerprint(contract_artifact):
        raise DevelopmentV7RunnerError("v7 recovery contract artifact is invalid.")
    contract = dict(contract_artifact.get("contract") or {})
    recovery_contract, _diff = build_recovery_contract(config, project_root=PROJECT_ROOT)
    checks = {
        "manifest_gate_run": manifest.get("run_id") == gate.get("run_id"),
        "manifest_gate_commit": manifest.get("commit") == gate.get("commit"),
        "manifest_contract": manifest.get("recovery_contract_fingerprint")
        == contract.get("recovery_contract_fingerprint")
        == gate.get("recovery_contract_fingerprint")
        == recovery_contract.get("recovery_contract_fingerprint"),
        "semantic_diff_zero": contract.get("research_semantics_diff_count") == 0,
        "implementation": manifest.get("implementation_fingerprint")
        == gate.get("implementation_fingerprint"),
        "safety_manifest": _closed_safety(manifest),
        "safety_gate": _closed_safety(dict(gate.get("safety") or {})),
    }
    current_head = _git("rev-parse", "HEAD", project_root=PROJECT_ROOT)
    checks["exact_commit"] = current_head == manifest.get("commit")
    checks["clean_worktree"] = _git("status", "--porcelain", project_root=PROJECT_ROOT) == ""
    implementation_hashes = {
        str(label): file_sha256(PROJECT_ROOT / str(label))
        for label in config["implementation_paths"]
    }
    checks["implementation_hashes"] = implementation_hashes == manifest.get(
        "implementation_sha256"
    )
    if not all(checks.values()):
        raise DevelopmentV7RunnerError(f"v7 runtime provenance mismatch: {checks}")
    _artifact, _parent_manifest, _parent_state = _parent_bundle(
        config, project_root=PROJECT_ROOT
    )
    scientific_contract = dict(_artifact["contract"])
    verify_v6_current_sources(
        input_precheck_artifact=PROJECT_ROOT
        / str(dict(scientific_contract["development_execution"])["input_precheck_artifact"]),
        project_root=PROJECT_ROOT,
    )
    return config, paths, manifest, contract, scientific_contract


def read_chain_status(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    config = load_recovery_config(config_path)
    paths = recovery_paths(config, project_root=PROJECT_ROOT)
    if not paths["chain_state"].is_file():
        return {
            "version": CHAIN_VERSION,
            "status": "V7_RECOVERY_BLOCKED_BEFORE_START",
            "phase": "PREPARE",
            "run_id": None,
        }
    state = _read_json(paths["chain_state"])
    if state.get("version") != CHAIN_VERSION:
        raise DevelopmentV7RunnerError("Unknown v7 chain-state version.")
    if paths["control_store"].is_file() and state.get("run_id"):
        state["progress"] = checkpoint_status(
            control_path=paths["control_store"], run_id=str(state["run_id"])
        )
    return state


def _update_state(
    path: Path,
    state: Mapping[str, object],
    *,
    status: str | None = None,
    phase: str | None = None,
    blocker: str | None = None,
    progress: Mapping[str, object] | None = None,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    updated = dict(state)
    if status is not None:
        updated["status"] = status
    if phase is not None:
        updated["phase"] = phase
    updated["blocker"] = blocker
    if progress is not None:
        updated["progress"] = dict(progress)
    if extra:
        updated.update(dict(extra))
    updated["updated_at"] = utc_now()
    _atomic_write(path, updated)
    return updated


def dispatch_readiness(
    config: Mapping[str, object], paths: Mapping[str, Path]
) -> tuple[bool, str, dict[str, object]]:
    settings = dict(config["recovery"])
    disk = shutil.disk_usage(PROJECT_ROOT)
    resources = system_resources()
    available = int(resources.get("available_physical_memory_bytes_at_start") or 0)
    detail: dict[str, object] = {
        "disk_free_bytes": int(disk.free),
        "minimum_disk_free_bytes": int(settings["minimum_disk_free_bytes"]),
        "available_memory_bytes": available,
        "minimum_available_memory_bytes": int(settings["minimum_available_memory_bytes"]),
    }
    if disk.free < int(settings["minimum_disk_free_bytes"]):
        return False, "DISK_RESERVE_TOO_LOW", detail
    if available and available < int(settings["minimum_available_memory_bytes"]):
        return False, "AVAILABLE_MEMORY_TOO_LOW", detail
    runtime_gate = historical_research_runtime_gate(
        load_campaign_config(paths["production_protection_config"]),
        project_root=PROJECT_ROOT,
    )
    detail["historical_research_runtime_gate"] = runtime_gate
    if not runtime_gate["run_allowed"]:
        return False, "BLOCKED_REAL_CONFLICT:" + ",".join(runtime_gate["active_production"]), detail
    return True, "CLEAR", detail


def _start_prepared_run(paths: Mapping[str, Path], manifest: Mapping[str, object]) -> str:
    started_at = utc_now()
    with _connection(paths["control_store"]) as connection:
        row = connection.execute(
            "SELECT status FROM runs WHERE run_id=?", (manifest["run_id"],)
        ).fetchone()
        if row is None:
            raise DevelopmentV7RunnerError("v7 run is absent from the control store.")
        if str(row[0]) == "PREPARED":
            connection.execute(
                "UPDATE runs SET status='RUNNING',started_at=?,last_checkpoint_at=? "
                "WHERE run_id=? AND status='PREPARED'",
                (started_at, started_at, manifest["run_id"]),
            )
        elif str(row[0]) != "RUNNING":
            return str(row[0])
    return "RUNNING"


def _is_readonly_error(error: BaseException) -> bool:
    return isinstance(error, sqlite3.OperationalError) and "readonly" in str(error).lower()


def _is_retryable_runtime_error(error: BaseException) -> bool:
    if _is_readonly_error(error) or isinstance(error, PermissionError):
        return False
    if is_retryable_compute_error(error) or isinstance(error, (TimeoutError, ConnectionError)):
        return True
    return isinstance(error, OSError) and error.errno in {
        errno.EAGAIN,
        errno.EBUSY,
        errno.ETIMEDOUT,
        errno.ECONNABORTED,
        errno.ECONNREFUSED,
        errno.ECONNRESET,
    }


def _record_recomputed_units(
    *,
    paths: Mapping[str, Path],
    manifest: Mapping[str, object],
    units: list[dict[str, object]],
    scientific_digest: str,
    lineage_status: str = "GROUND_UP_RECOMPUTED",
) -> None:
    parent_run_id = str(manifest["parent_run_id"])
    unit_ids = [str(unit["work_unit_id"]) for unit in units]
    if not unit_ids:
        return
    placeholders = ",".join("?" for _ in unit_ids)
    with _connection(paths["parent_control_store"], readonly=True) as parent:
        parent_statuses = {
            str(unit_id): str(status)
            for unit_id, status in parent.execute(
                "SELECT work_unit_id,status FROM work_units WHERE run_id=? "
                f"AND work_unit_id IN ({placeholders})",
                (parent_run_id, *unit_ids),
            )
        }
    with _connection(paths["control_store"]) as control:
        for unit in units:
            unit_id = str(unit["work_unit_id"])
            receipt = control.execute(
                "SELECT receipt_id,case_set_digest,feature_payload_digest,outcome_payload_digest "
                "FROM unit_receipts WHERE run_id=? AND work_unit_id=?",
                (manifest["run_id"], unit_id),
            ).fetchone()
            if receipt is None:
                raise DevelopmentV7RunnerError(
                    f"Cannot record recomputation without receipt: {unit_id}"
                )
            basis = {
                "target_run_id": manifest["run_id"],
                "target_work_unit_id": unit_id,
                "target_receipt_id": receipt[0],
                "parent_run_id": parent_run_id,
                "parent_status": parent_statuses.get(unit_id, "UNKNOWN"),
                "result_scientific_digest": scientific_digest,
                "lineage_status": lineage_status,
                "receipt_digests": list(receipt[1:]),
            }
            verification = fingerprint(basis)
            control.execute(
                "INSERT OR IGNORE INTO recovery_recomputation_lineage VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "madv7-recompute-" + verification[:32],
                    manifest["run_id"],
                    unit_id,
                    receipt[0],
                    parent_run_id,
                    parent_statuses.get(unit_id, "UNKNOWN"),
                    scientific_digest,
                    utc_now(),
                    lineage_status,
                    verification,
                ),
            )


def _reconcile_recomputation_lineage(
    *, paths: Mapping[str, Path], manifest: Mapping[str, object]
) -> int:
    """Bind receipts durable before an interruption to explicit recompute lineage."""

    with _connection(paths["control_store"], readonly=True) as control:
        missing = [
            {
                "work_unit_id": str(row[0]),
                "receipt_id": str(row[1]),
                "case_set_digest": str(row[2]),
                "feature_payload_digest": str(row[3]),
                "outcome_payload_digest": str(row[4]),
            }
            for row in control.execute(
                "SELECT w.work_unit_id,r.receipt_id,r.case_set_digest,"
                "r.feature_payload_digest,r.outcome_payload_digest FROM work_units w "
                "JOIN unit_receipts r ON r.work_unit_id=w.work_unit_id "
                "LEFT JOIN recovery_lineage reuse ON reuse.target_work_unit_id=w.work_unit_id "
                "LEFT JOIN recovery_recomputation_lineage recompute "
                "ON recompute.target_work_unit_id=w.work_unit_id "
                "WHERE w.run_id=? AND w.status IN ('COMPLETED','SKIPPED') "
                "AND reuse.target_work_unit_id IS NULL AND recompute.target_work_unit_id IS NULL",
                (manifest["run_id"],),
            )
        ]
    for item in missing:
        digest = fingerprint(
            {
                "recovered_after_durable_checkpoint": True,
                "target_receipt_id": item["receipt_id"],
                "case_set_digest": item["case_set_digest"],
                "feature_payload_digest": item["feature_payload_digest"],
                "outcome_payload_digest": item["outcome_payload_digest"],
            }
        )
        _record_recomputed_units(
            paths=paths,
            manifest=manifest,
            units=[{"work_unit_id": item["work_unit_id"]}],
            scientific_digest=digest,
            lineage_status="RECOVERED_AFTER_DURABLE_CHECKPOINT",
        )
    return len(missing)


def _readonly_diagnostic(
    *, paths: Mapping[str, Path], manifest: Mapping[str, object], error: BaseException
) -> dict[str, object]:
    stores = {}
    for role in ("control_store", "feature_store", "outcome_store"):
        path = paths[role]
        stores[role] = {
            "path": str(path.resolve()),
            "exists": path.is_file(),
            "os_access_write": os.access(path, os.W_OK) if path.exists() else False,
            "parent_os_access_write": os.access(path.parent, os.W_OK),
            "wal_exists": path.with_name(path.name + "-wal").exists(),
            "shm_exists": path.with_name(path.name + "-shm").exists(),
        }
    report = _self_fingerprinted(
        {
            "version": "multi-asset-development-v7-readonly-runtime-diagnostic-2026.09.13-v1",
            "status": "PAUSED_REQUIRES_REVIEW",
            "observed_at": utc_now(),
            "run_id": manifest["run_id"],
            "commit": manifest["commit"],
            "error_class": type(error).__name__,
            "error": str(error),
            "identity": os.environ.get("USERNAME"),
            "working_directory": os.getcwd(),
            "python_executable": os.path.abspath(os.sys.executable),
            "stores": stores,
            "permissions_widened": False,
            "automatic_retry": False,
        }
    )
    diagnostic_path = paths["chain_state"].with_name(
        "multi_asset_discovery_v1_development_v7_readonly_diagnostic.json"
    )
    _atomic_write(diagnostic_path, report)
    return report


def run_compute(
    *,
    config: Mapping[str, object],
    paths: Mapping[str, Path],
    manifest: Mapping[str, object],
    scientific_contract: Mapping[str, object],
    maximum_asset_batches: int | None = None,
) -> dict[str, object]:
    run_id = str(manifest["run_id"])
    status = checkpoint_status(control_path=paths["control_store"], run_id=run_id)
    if status["status"] != "RUNNING":
        return status
    reset_count = reset_interrupted_units(control_path=paths["control_store"], run_id=run_id)
    recovered_lineage = _reconcile_recomputation_lineage(paths=paths, manifest=manifest)
    logger = _logger(paths["log"])
    _set_below_normal_priority()
    append_run_event(
        control_path=paths["control_store"],
        run_id=run_id,
        event_type="V7_RECOVERY_RUNNER_STARTED",
        details={
            "pid": os.getpid(),
            "reset_interrupted_units": reset_count,
            "recovered_recomputation_lineage": recovered_lineage,
        },
    )
    universe, _work_plan = build_universe_and_work_plan(scientific_contract)
    assets = {str(item["asset_key"]): dict(item) for item in universe["assets"]}
    worker_count = int(dict(config["recovery"])["worker_count"])
    maximum_attempts = int(dict(config["recovery"])["maximum_attempts_per_work_unit"])
    input_path = PROJECT_ROOT / str(
        dict(scientific_contract["development_execution"])["input_precheck_artifact"]
    )
    in_flight: dict[Future[dict[str, object]], list[dict[str, object]]] = {}
    dispatched = 0
    completed_units = 0
    systematic_errors: list[str] = []
    yield_reason: str | None = None
    readonly_diagnostic: dict[str, object] | None = None
    with _StayAwake(), ProcessPoolExecutor(max_workers=worker_count) as executor:
        while True:
            while (
                not systematic_errors
                and yield_reason is None
                and len(in_flight) < worker_count
                and (maximum_asset_batches is None or dispatched < maximum_asset_batches)
            ):
                clear, reason, detail = dispatch_readiness(config, paths)
                if not clear:
                    yield_reason = reason
                    logger.info("Dispatch held | reason=%s detail=%s", reason, detail)
                    break
                units = claim_next_asset_batch(
                    control_path=paths["control_store"], run_id=run_id
                )
                if not units:
                    break
                future = executor.submit(
                    compute_v6_asset_batch,
                    asset=assets[str(units[0]["asset_key"])],
                    units=units,
                    contract=dict(scientific_contract),
                    input_precheck_artifact=input_path,
                )
                in_flight[future] = units
                dispatched += 1
            if not in_flight:
                break
            done, _pending = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
            for future in done:
                units = in_flight.pop(future)
                try:
                    result = future.result()
                    completed_units += _process_result(
                        result=result,
                        units=units,
                        manifest=manifest,
                        paths={
                            "feature": paths["feature_store"],
                            "outcome": paths["outcome_store"],
                            "control": paths["control_store"],
                        },
                        writer_pid=os.getpid(),
                    )
                    _record_recomputed_units(
                        paths=paths,
                        manifest=manifest,
                        units=units,
                        scientific_digest=result_scientific_digest(result),
                    )
                    checkpoint_sqlite(
                        paths["feature_store"], paths["outcome_store"], paths["control_store"]
                    )
                    append_run_event(
                        control_path=paths["control_store"],
                        run_id=run_id,
                        event_type="V7_RECOVERY_ASSET_BATCH_COMPLETED",
                        details={"asset_key": units[0]["asset_key"], "work_units": len(units)},
                    )
                    logger.info("Asset batch completed | asset=%s units=%s", units[0]["asset_key"], len(units))
                except Exception as exc:
                    readonly = _is_readonly_error(exc)
                    if readonly:
                        readonly_diagnostic = _readonly_diagnostic(
                            paths=paths, manifest=manifest, error=exc
                        )
                    retryable = _is_retryable_runtime_error(exc)
                    disposition = fail_asset_batch(
                        control_path=paths["control_store"],
                        run_id=run_id,
                        units=units,
                        error=exc,
                        maximum_attempts=maximum_attempts,
                        retryable=retryable,
                    )
                    logger.exception("Asset batch failed | asset=%s", units[0]["asset_key"])
                    if disposition == "FAILED_SYSTEMATIC" or readonly:
                        systematic_errors.append(
                            f"{units[0]['asset_key']}:{type(exc).__name__}:{str(exc)[:500]}"
                        )
                    elif disposition == "RETRY":
                        yield_reason = "TRANSIENT_ERROR_BACKOFF_TO_NEXT_SCHEDULER"
            if maximum_asset_batches is not None and dispatched >= maximum_asset_batches:
                yield_reason = "MAXIMUM_ASSET_BATCHES_REACHED"
            if (yield_reason or systematic_errors) and not in_flight:
                break
    if systematic_errors:
        pause_run_for_review(
            control_path=paths["control_store"],
            run_id=run_id,
            reason=" | ".join(systematic_errors),
        )
    else:
        mark_run_complete(control_path=paths["control_store"], run_id=run_id)
    status = checkpoint_status(control_path=paths["control_store"], run_id=run_id)
    status.update(
        {
            "asset_batches_dispatched_this_invocation": dispatched,
            "work_units_completed_this_invocation": completed_units,
            "yield_reason": yield_reason,
            "systematic_errors": systematic_errors,
            "readonly_diagnostic_fingerprint": (
                readonly_diagnostic.get("artifact_fingerprint") if readonly_diagnostic else None
            ),
        }
    )
    return status


def _database_health(path: Path, required_triggers: set[str]) -> dict[str, object]:
    with _connection(path, readonly=True) as connection:
        quick = connection.execute("PRAGMA quick_check").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = list(connection.execute("PRAGMA foreign_key_check"))
        triggers = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
    return {
        "quick_check": quick,
        "integrity_check": integrity,
        "foreign_key_errors": len(foreign),
        "journal_mode": journal,
        "required_triggers_present": sorted(required_triggers) == sorted(required_triggers & triggers),
    }


def _stream_store_audit(
    *, path: Path, table: str, digest_column: str, run_id: str
) -> tuple[int, int, dict[str, tuple[int, str, str]]]:
    total = 0
    payload_errors = 0
    digests: dict[str, tuple[int, str, str]] = {}
    current_unit: str | None = None
    current_rows: list[tuple[str, str, str | None]] = []

    def flush() -> None:
        nonlocal current_rows, current_unit
        if current_unit is None:
            return
        digests[current_unit] = (
            len(current_rows),
            fingerprint(current_rows),
            fingerprint([row[0] for row in current_rows]),
        )
        current_rows = []

    link_column = "NULL" if table == "feature_rows" else "feature_fingerprint"
    with _connection(path, readonly=True) as connection:
        cursor = connection.execute(
            f"SELECT work_unit_id,case_id,{digest_column},{link_column},payload_zlib "
            f"FROM {table} WHERE run_id=? ORDER BY work_unit_id,case_id",
            (run_id,),
        )
        for work_unit_id, case_id, stored_digest, link, compressed in cursor:
            unit_id = str(work_unit_id)
            if current_unit is not None and unit_id != current_unit:
                flush()
            current_unit = unit_id
            total += 1
            try:
                payload = decode_payload(compressed)
                basis = dict(payload)
                claimed = basis.pop(digest_column, None)
                if claimed != stored_digest or fingerprint(basis) != stored_digest:
                    payload_errors += 1
            except Exception:
                payload_errors += 1
            current_rows.append(
                (str(case_id), str(stored_digest), None if link is None else str(link))
            )
    flush()
    return total, payload_errors, digests


def build_final_audit(
    *, paths: Mapping[str, Path], manifest: Mapping[str, object]
) -> dict[str, object]:
    existing = paths["final_audit"]
    if existing.is_file():
        payload = _read_json(existing)
        if payload.get("version") != AUDIT_VERSION or not verify_self_fingerprint(payload):
            raise DevelopmentV7RunnerError("Existing v7 final audit is invalid.")
        return payload
    run_id = str(manifest["run_id"])
    health = {
        "feature": _database_health(
            paths["feature_store"], {"no_update_feature_rows", "no_delete_feature_rows"}
        ),
        "outcome": _database_health(
            paths["outcome_store"], {"no_update_outcome_rows", "no_delete_outcome_rows"}
        ),
        "control": _database_health(
            paths["control_store"],
            {
                "no_delete_runs",
                "no_reopen_terminal_run",
                "no_delete_work_units",
                "no_reopen_terminal_work_unit",
                "no_update_unit_receipts",
                "no_delete_unit_receipts",
                "no_update_recovery_lineage",
                "no_delete_recovery_lineage",
                "no_update_recovery_recomputation_lineage",
                "no_delete_recovery_recomputation_lineage",
            },
        ),
    }
    feature_total, feature_payload_errors, feature_digests = _stream_store_audit(
        path=paths["feature_store"], table="feature_rows", digest_column="feature_fingerprint", run_id=run_id
    )
    outcome_total, outcome_payload_errors, outcome_digests = _stream_store_audit(
        path=paths["outcome_store"], table="outcome_rows", digest_column="outcome_fingerprint", run_id=run_id
    )
    issues: Counter[str] = Counter()
    with _connection(paths["control_store"], readonly=True) as connection:
        runtime = checkpoint_status(control_path=paths["control_store"], run_id=run_id)
        receipt_rows = connection.execute(
            "SELECT work_unit_id,feature_rows,outcome_rows,case_set_digest,"
            "feature_payload_digest,outcome_payload_digest FROM unit_receipts WHERE run_id=?",
            (run_id,),
        ).fetchall()
        lineage = int(connection.execute(
            "SELECT COUNT(*) FROM recovery_lineage WHERE target_run_id=?", (run_id,)
        ).fetchone()[0])
        recomputation_lineage = int(connection.execute(
            "SELECT COUNT(*) FROM recovery_recomputation_lineage WHERE target_run_id=?", (run_id,)
        ).fetchone()[0])
        work_units = int(connection.execute(
            "SELECT COUNT(*) FROM work_units WHERE run_id=?", (run_id,)
        ).fetchone()[0])
        duplicate_receipts = int(connection.execute(
            "SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM unit_receipts "
            "WHERE run_id=? GROUP BY work_unit_id HAVING COUNT(*)>1)", (run_id,)
        ).fetchone()[0])
        reuse_rows = connection.execute(
            "SELECT l.lineage_id,l.target_work_unit_id,l.source_run_id,"
            "l.source_work_unit_id,l.source_receipt_id,l.case_set_digest,"
            "l.feature_payload_digest,l.outcome_payload_digest,l.reuse_status,"
            "l.verification_fingerprint,r.receipt_id,r.case_set_digest,"
            "r.feature_payload_digest,r.outcome_payload_digest "
            "FROM recovery_lineage l JOIN unit_receipts r "
            "ON r.work_unit_id=l.target_work_unit_id WHERE l.target_run_id=?",
            (run_id,),
        ).fetchall()
        recompute_rows = connection.execute(
            "SELECT l.lineage_id,l.target_work_unit_id,l.target_receipt_id,"
            "l.parent_run_id,l.parent_status,l.result_scientific_digest,"
            "l.lineage_status,l.verification_fingerprint,r.receipt_id,"
            "r.case_set_digest,r.feature_payload_digest,r.outcome_payload_digest "
            "FROM recovery_recomputation_lineage l JOIN unit_receipts r "
            "ON r.work_unit_id=l.target_work_unit_id WHERE l.target_run_id=?",
            (run_id,),
        ).fetchall()
    with _connection(paths["parent_control_store"], readonly=True) as parent_control:
        parent_receipts = {
            str(work_unit_id): str(receipt_id)
            for work_unit_id, receipt_id in parent_control.execute(
                "SELECT work_unit_id,receipt_id FROM unit_receipts WHERE run_id=?",
                (manifest["parent_run_id"],),
            )
        }
        parent_statuses = {
            str(work_unit_id): str(status)
            for work_unit_id, status in parent_control.execute(
                "SELECT work_unit_id,status FROM work_units WHERE run_id=?",
                (manifest["parent_run_id"],),
            )
        }
    for row in reuse_rows:
        verification_basis = {
            "source_run_id": str(row[2]),
            "source_work_unit_id": str(row[3]),
            "source_receipt_id": str(row[4]),
            "target_run_id": run_id,
            "target_work_unit_id": str(row[1]),
            "case_set_digest": str(row[5]),
            "feature_payload_digest": str(row[6]),
            "outcome_payload_digest": str(row[7]),
        }
        verification = fingerprint(verification_basis)
        receipt_matches = (
            str(row[4]) == parent_receipts.get(str(row[3]))
            and str(row[5]) == str(row[11])
            and str(row[6]) == str(row[12])
            and str(row[7]) == str(row[13])
        )
        if (
            str(row[0]) != "madv7-lineage-" + verification[:32]
            or str(row[9]) != verification
            or str(row[8]) != "VERIFIED_REUSED"
            or str(row[1]) != str(row[3])
            or str(row[2]) != str(manifest["parent_run_id"])
            or not receipt_matches
        ):
            issues["reuse_lineage_mismatch"] += 1
    for row in recompute_rows:
        verification_basis = {
            "target_run_id": run_id,
            "target_work_unit_id": str(row[1]),
            "target_receipt_id": str(row[2]),
            "parent_run_id": str(row[3]),
            "parent_status": str(row[4]),
            "result_scientific_digest": str(row[5]),
            "lineage_status": str(row[6]),
            "receipt_digests": [str(row[9]), str(row[10]), str(row[11])],
        }
        verification = fingerprint(verification_basis)
        if (
            str(row[0]) != "madv7-recompute-" + verification[:32]
            or str(row[7]) != verification
            or str(row[2]) != str(row[8])
            or str(row[3]) != str(manifest["parent_run_id"])
            or parent_statuses.get(str(row[1])) != str(row[4])
            or str(row[6]) not in {
                "GROUND_UP_RECOMPUTED",
                "RECOVERED_AFTER_DURABLE_CHECKPOINT",
            }
        ):
            issues["recomputation_lineage_mismatch"] += 1
    for unit_id, feature_rows, outcome_rows, case_digest, feature_digest, outcome_digest in receipt_rows:
        f_rows = feature_digests.get(str(unit_id), (0, fingerprint([]), fingerprint([])))
        o_rows = outcome_digests.get(str(unit_id), (0, fingerprint([]), fingerprint([])))
        if int(feature_rows) != f_rows[0] or str(feature_digest) != f_rows[1]:
            issues["feature_receipt_mismatch"] += 1
        if int(outcome_rows) != o_rows[0] or str(outcome_digest) != o_rows[1]:
            issues["outcome_receipt_mismatch"] += 1
        if f_rows[2] != str(case_digest) or o_rows[2] != str(case_digest):
            issues["case_set_digest_mismatch"] += 1
    reconciliation = sqlite3.connect(":memory:", uri=True)
    try:
        reconciliation.execute(
            "ATTACH DATABASE ? AS features",
            (f"file:{paths['feature_store'].resolve().as_posix()}?mode=ro",),
        )
        reconciliation.execute(
            "ATTACH DATABASE ? AS outcomes",
            (f"file:{paths['outcome_store'].resolve().as_posix()}?mode=ro",),
        )
        feature_orphans = int(reconciliation.execute(
            "SELECT COUNT(*) FROM features.feature_rows f LEFT JOIN outcomes.outcome_rows o "
            "ON o.case_id=f.case_id WHERE f.run_id=? AND o.case_id IS NULL", (run_id,)
        ).fetchone()[0])
        outcome_orphans = int(reconciliation.execute(
            "SELECT COUNT(*) FROM outcomes.outcome_rows o LEFT JOIN features.feature_rows f "
            "ON f.case_id=o.case_id WHERE o.run_id=? AND f.case_id IS NULL", (run_id,)
        ).fetchone()[0])
        link_mismatches = int(reconciliation.execute(
            "SELECT COUNT(*) FROM outcomes.outcome_rows o JOIN features.feature_rows f "
            "ON f.case_id=o.case_id WHERE o.run_id=? AND f.run_id=? "
            "AND o.feature_fingerprint<>f.feature_fingerprint", (run_id, run_id)
        ).fetchone()[0])
    finally:
        reconciliation.close()
    orphans = feature_orphans + outcome_orphans
    if link_mismatches:
        issues["feature_outcome_link_mismatch"] += link_mismatches
    if orphans:
        issues["feature_outcome_orphan"] += orphans
    if feature_payload_errors:
        issues["feature_payload_error"] += feature_payload_errors
    if outcome_payload_errors:
        issues["outcome_payload_error"] += outcome_payload_errors
    if duplicate_receipts:
        issues["duplicate_receipt"] += duplicate_receipts
    if runtime["status"] != "COMPLETED":
        issues["run_not_completed"] += 1
    if runtime["receipts"] != runtime["total_planned_work_units"]:
        issues["receipt_count_mismatch"] += 1
    if lineage + recomputation_lineage != runtime["receipts"]:
        issues["lineage_receipt_count_mismatch"] += 1
    if not _closed_safety(manifest):
        issues["later_stage_safety_open"] += 1
    if any(
        item["quick_check"] != "ok"
        or item["integrity_check"] != "ok"
        or item["foreign_key_errors"]
        or not item["required_triggers_present"]
        for item in health.values()
    ):
        issues["database_health"] += 1
    report = _self_fingerprinted(
        {
            "version": AUDIT_VERSION,
            "status": "PASS" if not issues else "FAIL",
            "created_at": utc_now(),
            "run_id": run_id,
            "run_manifest_fingerprint": manifest["run_manifest_fingerprint"],
            "runtime": runtime,
            "database_health": health,
            "counts": {
                "work_units": work_units,
                "receipts": len(receipt_rows),
                "feature_cases": feature_total,
                "outcome_cases": outcome_total,
                "reused_units": lineage,
                "recomputed_units": recomputation_lineage,
                "duplicates": duplicate_receipts,
                "orphans": orphans,
                "payload_errors": feature_payload_errors + outcome_payload_errors,
                "link_mismatches": link_mismatches,
            },
            "issues": dict(sorted(issues.items())),
            "safety": {
                "validation_opened": False,
                "holdout_opened": False,
                "external_opened": False,
                "forward_opened": False,
                "paper_opened": False,
                "shadow_opened": False,
                "broker_opened": False,
            },
        }
    )
    _write_immutable(paths["final_audit"], report)
    return report


def build_descriptive_report(
    *, paths: Mapping[str, Path], manifest: Mapping[str, object], audit: Mapping[str, object]
) -> dict[str, object]:
    if audit.get("status") != "PASS":
        raise DevelopmentV7RunnerError("Descriptive output requires a PASS final audit.")
    if paths["descriptive_report"].is_file():
        payload = _read_json(paths["descriptive_report"])
        if payload.get("version") != REPORT_VERSION or not verify_self_fingerprint(payload):
            raise DevelopmentV7RunnerError("Existing v7 descriptive report is invalid.")
        return payload
    run_id = str(manifest["run_id"])
    with _connection(paths["control_store"], readonly=True) as control:
        units_by_class = {
            str(asset_class): {str(status): int(count) for status, count in rows}
            for asset_class, rows in (
                (
                    asset_class,
                    control.execute(
                        "SELECT status,COUNT(*) FROM work_units WHERE run_id=? AND asset_class=? GROUP BY status",
                        (run_id, asset_class),
                    ).fetchall(),
                )
                for (asset_class,) in control.execute(
                    "SELECT DISTINCT asset_class FROM work_units WHERE run_id=? ORDER BY asset_class", (run_id,)
                )
            )
        }
        checkpoints = int(control.execute(
            "SELECT COUNT(*) FROM run_events WHERE run_id=?", (run_id,)
        ).fetchone()[0])
    with _connection(paths["outcome_store"], readonly=True) as outcomes:
        outcome_status = {
            str(status): int(count)
            for status, count in outcomes.execute(
                "SELECT status,COUNT(*) FROM outcome_rows WHERE run_id=? GROUP BY status", (run_id,)
            )
        }
        r_availability = {
            str(status): int(count)
            for status, count in outcomes.execute(
                "SELECT r_availability,COUNT(*) FROM outcome_rows WHERE run_id=? GROUP BY r_availability", (run_id,)
            )
        }
    report = _self_fingerprinted(
        {
            "version": REPORT_VERSION,
            "status": "DESCRIPTIVE_COMPLETE",
            "created_at": utc_now(),
            "run_id": run_id,
            "audit_fingerprint": audit["artifact_fingerprint"],
            "coverage_by_asset_class": units_by_class,
            "outcome_status": outcome_status,
            "structural_r_availability": r_availability,
            "checkpoint_events": checkpoints,
            "censored_cases": dict(audit["runtime"])["censored_cases"],
            "research_interpretation": "DESCRIPTIVE_ONLY_NO_SELECTION_NO_OPTIMIZATION",
            "remaining_limits": [
                "Development evidence only",
                "No strategy result is inferred from technical recovery",
                "Validation and Holdout remain unopened",
            ],
        }
    )
    _write_immutable(paths["descriptive_report"], report)
    return report


def build_completion_summary(
    *, paths: Mapping[str, Path], manifest: Mapping[str, object], audit: Mapping[str, object], report: Mapping[str, object]
) -> dict[str, object]:
    if paths["completion_summary"].is_file():
        payload = _read_json(paths["completion_summary"])
        if payload.get("version") != SUMMARY_VERSION or not verify_self_fingerprint(payload):
            raise DevelopmentV7RunnerError("Existing v7 completion summary is invalid.")
        return payload
    summary = _self_fingerprinted(
        {
            "version": SUMMARY_VERSION,
            "status": "V7_RECOVERY_COMPLETE_AWAITING_REVIEW",
            "created_at": utc_now(),
            "run_id": manifest["run_id"],
            "commit": manifest["commit"],
            "recovery_contract_fingerprint": manifest["recovery_contract_fingerprint"],
            "audit_fingerprint": audit["artifact_fingerprint"],
            "descriptive_report_fingerprint": report["artifact_fingerprint"],
            "scheduler_terminal_behavior": "TERMINAL_NOOP",
            "safety": dict(audit["safety"]),
        }
    )
    _write_immutable(paths["completion_summary"], summary)
    return summary


def advance_chain(
    *, config_path: Path = DEFAULT_CONFIG_PATH, maximum_asset_batches: int | None = None
) -> dict[str, object]:
    try:
        config, paths, manifest, _recovery_contract, scientific_contract = _load_bound_context(
            config_path
        )
    except Exception as exc:
        return {
            "version": CHAIN_VERSION,
            "status": "V7_RECOVERY_BLOCKED_BEFORE_START",
            "phase": "START_GATE",
            "blocker": f"START_GATE_FAILED:{type(exc).__name__}",
            "error": str(exc)[:2000],
            "validation_opened": False,
            "holdout_opened": False,
        }
    process_lock = SwingRunLock(paths["process_lock"])
    try:
        process_lock.acquire()
    except SwingRunAlreadyActiveError:
        return {**read_chain_status(config_path), "duplicate_start_rejected": True}
    try:
        state = read_chain_status(config_path)
        if state.get("status") == "V7_RECOVERY_COMPLETE_AWAITING_REVIEW":
            return {**state, "terminal_noop": True}
        if state.get("status") == "PAUSED_REQUIRES_REVIEW":
            return {**state, "persistent_review_pause": True}
        research_lock = SwingRunLock(GLOBAL_RESEARCH_LOCK)
        try:
            research_lock.acquire()
        except SwingRunAlreadyActiveError:
            return {**state, "research_lock_active": True}
        try:
            clear, reason, detail = dispatch_readiness(config, paths)
            if not clear:
                return _update_state(
                    paths["chain_state"],
                    state,
                    blocker=None,
                    extra={"dispatch_wait": reason, "dispatch_detail": detail},
                )
            run_status = _start_prepared_run(paths, manifest)
            if run_status not in {"RUNNING", "COMPLETED"}:
                return _update_state(
                    paths["chain_state"], state, status="PAUSED_REQUIRES_REVIEW", blocker=run_status
                )
            if run_status == "RUNNING":
                state = _update_state(
                    paths["chain_state"],
                    state,
                    status="V7_RECOVERY_RUNNING",
                    phase="RUN",
                    blocker=None,
                    extra={
                        "started_at": state.get("started_at") or utc_now(),
                        "scheduler_task": dict(config["recovery"])["scheduler_task"],
                        "process_pid": os.getpid(),
                    },
                )
                result = run_compute(
                    config=config,
                    paths=paths,
                    manifest=manifest,
                    scientific_contract=scientific_contract,
                    maximum_asset_batches=maximum_asset_batches,
                )
                if result["status"] == "PAUSED_REQUIRES_REVIEW":
                    return _update_state(
                        paths["chain_state"], state, status="PAUSED_REQUIRES_REVIEW", blocker=str(result.get("pause_reason")), progress=result
                    )
                if result["status"] != "COMPLETED":
                    return _update_state(
                        paths["chain_state"], state, status="V7_RECOVERY_RUNNING", blocker=None, progress=result
                    )
                state = _update_state(
                    paths["chain_state"], state, status="V7_RECOVERY_RUNNING", phase="FINAL_AUDIT", blocker=None, progress=result
                )
            audit = build_final_audit(paths=paths, manifest=manifest)
            if audit["status"] != "PASS":
                return _update_state(
                    paths["chain_state"], state, status="PAUSED_REQUIRES_REVIEW", phase="FINAL_AUDIT", blocker="FINAL_AUDIT_FAILED", extra={"audit_fingerprint": audit["artifact_fingerprint"]}
                )
            report = build_descriptive_report(paths=paths, manifest=manifest, audit=audit)
            summary = build_completion_summary(
                paths=paths, manifest=manifest, audit=audit, report=report
            )
            return _update_state(
                paths["chain_state"],
                state,
                status="V7_RECOVERY_COMPLETE_AWAITING_REVIEW",
                phase="STOP",
                blocker=None,
                progress=dict(audit["runtime"]),
                extra={
                    "audit_fingerprint": audit["artifact_fingerprint"],
                    "report_fingerprint": report["artifact_fingerprint"],
                    "summary_fingerprint": summary["artifact_fingerprint"],
                    "terminal_noop": True,
                },
            )
        finally:
            research_lock.release()
    except Exception as exc:
        latest = read_chain_status(config_path)
        if latest.get("status") == "V7_RECOVERY_BLOCKED_BEFORE_START":
            return {**latest, "error": str(exc)[:2000]}
        return _update_state(
            paths["chain_state"],
            latest,
            status="PAUSED_REQUIRES_REVIEW",
            blocker=f"RUNNER_EXCEPTION:{type(exc).__name__}:{str(exc)[:1000]}",
        )
    finally:
        process_lock.release()


__all__ = [
    "DevelopmentV7RunnerError",
    "RUNNER_VERSION",
    "advance_chain",
    "build_completion_summary",
    "build_descriptive_report",
    "build_final_audit",
    "dispatch_readiness",
    "read_chain_status",
    "run_compute",
]
