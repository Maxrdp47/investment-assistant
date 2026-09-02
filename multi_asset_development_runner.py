from __future__ import annotations

"""Persistent runner for the Development-only Multi-Asset Discovery v1 scan."""

import json
import logging
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

import pandas as pd

from multi_asset_development_contract import (
    build_development_contract_artifact,
    load_development_contract,
    verify_development_contract_artifact,
)
from multi_asset_development_execution import (
    DEFAULT_DATASET_MANIFEST,
    DEFAULT_FX_STORE,
    DEFAULT_IDENTITY_STORE,
    append_run_event,
    audit_development_stores,
    build_development_universe,
    build_work_plan,
    checkpoint_status,
    claim_next_work_unit,
    complete_work_unit,
    execute_work_unit,
    fail_work_unit,
    initialize_run,
    load_asset_history,
    mark_run_complete,
    precompute_structure_history,
    resume_interrupted_units,
    utc_now,
)
from multi_asset_discovery_v1 import (
    canonical_json,
    fingerprint,
    prepare_indicators,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward_campaign import (
    campaign_active_production_jobs,
    campaign_is_protected_time,
    load_campaign_config,
)


PROJECT_ROOT = Path(__file__).resolve().parent
BERLIN = ZoneInfo("Europe/Berlin")
RUNNER_VERSION = "multi-asset-discovery-development-runner-2026.09.01-v4"
RUNNING_STATUS = "MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT_RUNNING"
COMPLETE_STATUS = "MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT_COMPLETE_AWAITING_REVIEW"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=PROJECT_ROOT, text=True, encoding="utf-8"
    ).strip()


def _git_commit_is_ancestor(commit: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, descendant],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


def _paths(contract: Mapping[str, object]) -> dict[str, Path]:
    stores = dict(contract["store_contract"])
    execution = dict(contract["development_execution"])
    return {
        "feature": PROJECT_ROOT / str(stores["feature_store"]),
        "outcome": PROJECT_ROOT / str(stores["outcome_store"]),
        "control": PROJECT_ROOT / str(stores["control_store"]),
        "lock": PROJECT_ROOT / str(execution["process_lock"]),
        "manifest": PROJECT_ROOT / str(execution["run_manifest"]),
        "contract_artifact": PROJECT_ROOT / str(execution["contract_artifact"]),
        "contract_diff": PROJECT_ROOT / str(execution["contract_diff_artifact"]),
        "readiness": PROJECT_ROOT / str(execution["readiness_artifact"]),
        "log": PROJECT_ROOT / str(execution["log_path"]),
    }


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_json(existing) != canonical_json(payload):
            raise RuntimeError(f"Append-only-Artefakt weicht ab: {path}")
        return
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def export_development_contract(
    *, frozen_at: str | None = None
) -> tuple[dict[str, object], dict[str, object]]:
    contract = load_development_contract()
    paths = _paths(contract)
    if paths["contract_artifact"].exists():
        artifact = json.loads(paths["contract_artifact"].read_text(encoding="utf-8"))
        diff = json.loads(paths["contract_diff"].read_text(encoding="utf-8"))
        if not verify_development_contract_artifact(artifact):
            raise RuntimeError("Development-Contract-Artefakt ist nicht integer.")
        if artifact.get("contract_fingerprint") != contract["contract_fingerprint"]:
            raise RuntimeError("Development-Contract-Artefakt gehört zu anderem Code.")
        return artifact, diff
    if _git("status", "--porcelain"):
        raise RuntimeError(
            "Development-Contract darf nur aus sauberem Arbeitsbaum eingefroren werden."
        )
    artifact, diff = build_development_contract_artifact(
        git_branch=_git("branch", "--show-current"),
        git_commit=_git("rev-parse", "HEAD"),
        frozen_at=frozen_at or utc_now(),
    )
    if diff["status"] != "PASS" or diff["research_semantics_diff_count"] != 0:
        raise RuntimeError("Research-Semantik-Diff ist nicht null.")
    _write_immutable(paths["contract_artifact"], artifact)
    _write_immutable(paths["contract_diff"], diff)
    return artifact, diff


def _load_ready_artifact(path: Path, contract_fingerprint: str) -> dict[str, object]:
    if not path.exists():
        raise RuntimeError("Finales 8/8-Readiness-Artefakt fehlt.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT":
        raise RuntimeError("Finales Readiness-Gate ist nicht READY.")
    if payload.get("development_contract_fingerprint") != contract_fingerprint:
        raise RuntimeError("Readiness-Artefakt gehört zu anderem Development-Contract.")
    if any(value != "PASS" for value in dict(payload.get("gate_status") or {}).values()):
        raise RuntimeError("Nicht alle acht Gate-Gruppen sind PASS.")
    return payload


def build_run_manifest(
    *,
    contract_artifact: Mapping[str, object],
    universe: Mapping[str, object],
    work_plan: Mapping[str, object],
    started_at: str,
) -> dict[str, object]:
    contract = dict(contract_artifact["contract"])
    references = dict(contract["reference_fingerprints"])
    execution = dict(contract["development_execution"])
    basis = {
        "research_epoch": execution["research_epoch"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
    }
    run_id = f"mad1-development-{fingerprint(basis)[:24]}"
    payload: dict[str, object] = {
        "version": "multi-asset-discovery-development-run-manifest-2026.09.01-v4",
        "run_id": run_id,
        "research_epoch": execution["research_epoch"],
        "development_contract_version": contract["contract_version"],
        "parent_contract_version": contract["parent_contract"]["version"],
        "parent_fingerprint": contract["parent_contract"]["fingerprint"],
        "development_contract_fingerprint": contract["contract_fingerprint"],
        "code_fingerprint": references["development_code_fingerprint"],
        "dataset_fingerprint": references["dataset_fingerprint"],
        "fx_v2_fingerprint": references["fx_dataset_fingerprint"],
        "identity_fingerprint": references["identity_registry_fingerprint"],
        "dependency_policy_fingerprint": references[
            "historical_dependency_policy_fingerprint"
        ],
        "universe_fingerprint": universe["universe_fingerprint"],
        "feature_contract_fingerprint": references[
            "feature_contract_fingerprint"
        ],
        "outcome_contract_fingerprint": references[
            "outcome_contract_fingerprint"
        ],
        "stage_split_fingerprint": references["stage_split_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
        "total_planned_work_units": work_plan["total_planned_work_units"],
        "branch": _git("branch", "--show-current"),
        "commit": _git("rev-parse", "HEAD"),
        "command": "scripts/run_multi_asset_development.py --run",
        "worker_count": execution["worker_count"],
        "sqlite_writer_count": execution["sqlite_writer_count"],
        "scheduler": execution["scheduler_task_name"],
        "runner": RUNNER_VERSION,
        "started_at": started_at,
        "status": "STARTING",
        "development_only": True,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "true_forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
        "automatic_orders_allowed": False,
    }
    payload["run_manifest_fingerprint"] = fingerprint(payload)
    return payload


def prepare_canonical_run() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    contract = load_development_contract()
    paths = _paths(contract)
    artifact, _ = export_development_contract()
    _load_ready_artifact(paths["readiness"], str(contract["contract_fingerprint"]))
    universe = build_development_universe()
    work_plan = build_work_plan(universe)
    if paths["manifest"].exists():
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    else:
        if _git("status", "--porcelain"):
            raise RuntimeError(
                "Run-Manifest darf nur aus sauberem Arbeitsbaum erzeugt werden."
            )
        manifest = build_run_manifest(
            contract_artifact=artifact,
            universe=universe,
            work_plan=work_plan,
            started_at=utc_now(),
        )
        _write_immutable(paths["manifest"], manifest)
    current_head = _git("rev-parse", "HEAD")
    if not _git_commit_is_ancestor(str(manifest["commit"]), current_head):
        raise RuntimeError(
            "Run-Manifest-Commit ist kein Vorfahr des aktuellen HEAD."
        )
    if manifest["development_contract_fingerprint"] != contract["contract_fingerprint"]:
        raise RuntimeError("Run-Manifest besitzt falschen Contract-Fingerprint.")
    initialize_run(
        run_manifest=manifest,
        universe=universe,
        work_plan=work_plan,
        feature_path=paths["feature"],
        outcome_path=paths["outcome"],
        control_path=paths["control"],
    )
    return manifest, universe, work_plan


def _configure_logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("multi_asset_discovery_development")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    return logger


def development_time_guard(
    contract: Mapping[str, object], *, now: datetime
) -> tuple[bool, str]:
    """Apply only Development-owned time gates, never Forward-only windows."""

    execution = dict(contract["development_execution"])
    not_before = datetime.fromisoformat(str(execution["development_not_before"]))
    if not_before.tzinfo is None or now.tzinfo is None:
        raise RuntimeError("Development-Startgrenze benötigt Zeitzonen.")
    if now.astimezone(not_before.tzinfo) < not_before:
        return False, "DEVELOPMENT_NOT_BEFORE:" + not_before.isoformat()
    if execution.get("forward_only_time_windows_apply_to_development") is True:
        config_path = PROJECT_ROOT / str(execution["production_protection_config"])
        config = load_campaign_config(config_path)
        if campaign_is_protected_time(now, config):
            return False, "FORWARD_ONLY_PROTECTED_WINDOW"
    return True, "CLEAR"


def _production_clear(
    contract: Mapping[str, object], *, now: datetime | None = None
) -> tuple[bool, str]:
    execution = dict(contract["development_execution"])
    effective_now = now or datetime.now(BERLIN)
    clear, reason = development_time_guard(contract, now=effective_now)
    if not clear:
        return False, reason
    config_path = PROJECT_ROOT / str(execution["production_protection_config"])
    config = load_campaign_config(config_path)
    if execution.get("active_production_locks_apply_to_development") is True:
        active = campaign_active_production_jobs(config, project_root=PROJECT_ROOT)
        if active:
            return False, "ACTIVE_PRODUCTION_LOCK:" + ",".join(active)
    return True, "CLEAR"


def _checkpoint_sqlite(paths: Mapping[str, Path]) -> None:
    for key in ("feature", "outcome", "control"):
        with sqlite3.connect(paths[key], timeout=60) as connection:
            busy, _, _ = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        if int(busy):
            raise RuntimeError(f"SQLite-Checkpoint busy: {key}")


def run_development(
    *, maximum_work_units: int | None = None
) -> dict[str, object]:
    contract = load_development_contract()
    paths = _paths(contract)
    manifest, universe, _ = prepare_canonical_run()
    run_id = str(manifest["run_id"])
    logger = _configure_logger(paths["log"])
    lock = SwingRunLock(paths["lock"])
    try:
        lock.acquire()
    except SwingRunAlreadyActiveError:
        return {
            **checkpoint_status(control_path=paths["control"], run_id=run_id),
            "duplicate_start_rejected": True,
        }
    try:
        resumed = resume_interrupted_units(control_path=paths["control"], run_id=run_id)
        append_run_event(
            control_path=paths["control"],
            run_id=run_id,
            event_type="RUNNER_STARTED",
            details={"resumed_interrupted_units": resumed, "pid": os.getpid()},
        )
        assets = {str(item["asset_key"]): item for item in universe["assets"]}
        cached_key = None
        cached_frame = None
        cached_prepared = None
        cached_availability: Mapping[str, str] = {}
        cached_fingerprint = ""
        cached_safe = None
        cached_sell = None
        processed = 0
        maximum_attempts = int(
            dict(contract["development_execution"])["maximum_attempts_per_work_unit"]
        )
        while maximum_work_units is None or processed < maximum_work_units:
            clear, reason = _production_clear(contract)
            if not clear:
                logger.info("Runner yields to production | reason=%s", reason)
                append_run_event(
                    control_path=paths["control"],
                    run_id=run_id,
                    event_type="PRODUCTION_PRIORITY_YIELD",
                    details={"reason": reason},
                )
                break
            unit = claim_next_work_unit(control_path=paths["control"], run_id=run_id)
            if unit is None:
                mark_run_complete(control_path=paths["control"], run_id=run_id)
                append_run_event(
                    control_path=paths["control"],
                    run_id=run_id,
                    event_type="RUN_COMPLETED",
                )
                break
            try:
                asset = assets[str(unit["asset_key"])]
                if cached_key != unit["asset_key"]:
                    cached_frame, cached_availability, cached_fingerprint = load_asset_history(
                        asset,
                        manifest_path=DEFAULT_DATASET_MANIFEST,
                        fx_store=DEFAULT_FX_STORE,
                    )
                    cached_prepared = prepare_indicators(cached_frame)
                    if cached_prepared.index.max() > pd.Timestamp("2021-12-31"):
                        raise RuntimeError("Nicht-Development-Daten im Runner-Frame.")
                    cached_safe, cached_sell = precompute_structure_history(cached_prepared)
                    cached_key = unit["asset_key"]
                result = execute_work_unit(
                    asset=asset,
                    unit=unit,
                    prepared=cached_prepared,
                    availability=cached_availability,
                    source_dataset_fingerprint=cached_fingerprint,
                    safe_history=cached_safe,
                    sell_history=cached_sell,
                )
                from multi_asset_development_execution import persist_work_unit_evidence

                persist_work_unit_evidence(
                    run_id=run_id,
                    work_unit_id=str(unit["work_unit_id"]),
                    features=result["features"],
                    outcomes=result["outcomes"],
                    feature_path=paths["feature"],
                    outcome_path=paths["outcome"],
                )
                complete_work_unit(
                    control_path=paths["control"],
                    run_id=run_id,
                    unit=unit,
                    feature_rows=len(result["features"]),
                    outcome_rows=len(result["outcomes"]),
                    invalid_cases=int(result["invalid_cases"]),
                    censored_cases=int(result["censored_cases"]),
                )
                _checkpoint_sqlite(paths)
                append_run_event(
                    control_path=paths["control"],
                    run_id=run_id,
                    work_unit_id=str(unit["work_unit_id"]),
                    event_type="WORK_UNIT_COMPLETED",
                    details={
                        "feature_rows": len(result["features"]),
                        "outcome_rows": len(result["outcomes"]),
                        "invalid_cases": result["invalid_cases"],
                    },
                )
                logger.info(
                    "Work unit completed | unit=%s asset=%s features=%s outcomes=%s invalid=%s",
                    unit["work_unit_id"],
                    unit["asset_key"],
                    len(result["features"]),
                    len(result["outcomes"]),
                    result["invalid_cases"],
                )
            except Exception as exc:
                disposition = fail_work_unit(
                    control_path=paths["control"],
                    run_id=run_id,
                    unit=unit,
                    error=exc,
                    maximum_attempts=maximum_attempts,
                )
                append_run_event(
                    control_path=paths["control"],
                    run_id=run_id,
                    work_unit_id=str(unit["work_unit_id"]),
                    event_type=f"WORK_UNIT_{disposition}",
                    details={"error_class": type(exc).__name__, "error": str(exc)[:1000]},
                )
                logger.exception("Work unit failed | unit=%s", unit["work_unit_id"])
            processed += 1
        status = checkpoint_status(control_path=paths["control"], run_id=run_id)
        status["processed_this_invocation"] = processed
        status["duplicate_start_rejected"] = False
        status["store_audit"] = audit_development_stores(
            feature_path=paths["feature"],
            outcome_path=paths["outcome"],
            control_path=paths["control"],
            run_id=run_id,
        )
        status["final_status"] = (
            COMPLETE_STATUS if status["status"] == "COMPLETED" else RUNNING_STATUS
        )
        return status
    finally:
        lock.release()
