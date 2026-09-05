from __future__ import annotations

"""Persistent local runner for the closed Development-v6 lifecycle chain."""

import json
import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from multi_asset_development_v6_benchmark import system_resources
from multi_asset_development_v6_contract import (
    build_development_v6_benchmark_contract,
    load_development_v6_contract,
    verify_development_v6_contract_artifact,
)
from multi_asset_development_v6_execution import (
    build_v6_universe,
    build_v6_work_plan,
    compute_v6_asset_batch,
    is_retryable_compute_error,
)
from multi_asset_development_v6_preflight import START_GATE_VERSION, TOP_LEVEL_GATES
from multi_asset_development_v6_store import (
    DevelopmentV6StoreError,
    append_run_event,
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
from multi_asset_discovery_v1 import canonical_json, fingerprint
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward_campaign import campaign_active_production_jobs, load_campaign_config


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CHAIN_STATE_PATH = (
    PROJECT_ROOT
    / "runtime"
    / "multi_asset_discovery_v1_development_v6_chain_state.json"
)
RUNNER_VERSION = "multi-asset-development-runner-2026.09.05-v6"
CHAIN_VERSION = "multi-asset-development-chain-2026.09.05-v6"
OPERATOR_REQUEST_VERSION = "multi-asset-development-operator-request-2026.09.05-v1"
RUN_MANIFEST_VERSION = "multi-asset-discovery-development-run-manifest-2026.09.05-v6"
GLOBAL_RESEARCH_LOCK = PROJECT_ROOT / "runtime" / "swing_walk_forward_research.lock"
FX_OBSERVER_LOCK = PROJECT_ROOT / "runtime" / "fx_forward_pit.collector.lock"
MINIMUM_DISK_FREE_BYTES = 30 * 1024**3
MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3


class DevelopmentV6RunnerError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=PROJECT_ROOT, text=True, encoding="utf-8"
    ).strip()


def _atomic_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _operator_request_path(chain_state_path: Path) -> Path:
    chain_state_path = Path(chain_state_path)
    return chain_state_path.with_name(
        chain_state_path.stem + "_operator_request.json"
    )


def _active_operator_request(chain_state_path: Path) -> str | None:
    path = _operator_request_path(chain_state_path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentV6RunnerError(
            "Operator-request artifact is unreadable."
        ) from exc
    if payload.get("version") != OPERATOR_REQUEST_VERSION:
        raise DevelopmentV6RunnerError("Unknown operator-request version.")
    request = payload.get("request")
    if request not in {None, "PAUSE", "STOP", "RESUME"}:
        raise DevelopmentV6RunnerError("Unknown operator request.")
    return request


def _overlay_operator_request(
    chain_state_path: Path, state: Mapping[str, object]
) -> dict[str, object]:
    updated = dict(state)
    request = _active_operator_request(chain_state_path)
    updated["pause_requested"] = request == "PAUSE"
    updated["stop_requested"] = request == "STOP"
    updated["operator_request"] = request
    if updated.get("phase") != "STOP":
        if request in {"PAUSE", "STOP"}:
            updated["status"] = "PAUSED_REQUIRES_REVIEW"
            updated["blocker"] = f"OPERATOR_{request}_REQUESTED"
        elif request == "RESUME":
            # Resuming is explicit but remains request-file-only.  Expose the
            # effective resumed state without rewriting a potentially newer
            # chain checkpoint from a stale CLI read.
            updated["status"] = "RUNNING"
            updated["blocker"] = None
    return updated


def read_chain_status(
    chain_state_path: Path = DEFAULT_CHAIN_STATE_PATH,
) -> dict[str, object]:
    """Read the operational state without loading or rebuilding the contract."""

    chain_state_path = Path(chain_state_path)
    if not chain_state_path.exists():
        return {
            "status": "NOT_STARTED",
            "chain_state": str(chain_state_path.resolve()),
            "operator_request_path": str(
                _operator_request_path(chain_state_path).resolve()
            ),
        }
    try:
        state = json.loads(chain_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentV6RunnerError("Chain-state artifact is unreadable.") from exc
    if state.get("version") != CHAIN_VERSION:
        raise DevelopmentV6RunnerError("Unknown chain-state version.")
    result = _overlay_operator_request(chain_state_path, state)
    result["chain_state"] = str(chain_state_path.resolve())
    result["operator_request_path"] = str(
        _operator_request_path(chain_state_path).resolve()
    )
    return result


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_json(existing) != canonical_json(payload):
            raise DevelopmentV6RunnerError(f"Immutable artifact differs: {path}")
        return
    _atomic_write(path, payload)


def _verify_self_fingerprint(payload: Mapping[str, object]) -> bool:
    expected = payload.get("artifact_fingerprint")
    basis = dict(payload)
    basis.pop("artifact_fingerprint", None)
    return bool(expected) and expected == fingerprint(basis)


def contract_paths(contract: Mapping[str, object]) -> dict[str, Path]:
    stores = dict(contract["store_contract"])
    execution = dict(contract["development_execution"])
    return {
        "feature": PROJECT_ROOT / str(stores["feature_store"]),
        "outcome": PROJECT_ROOT / str(stores["outcome_store"]),
        "control": PROJECT_ROOT / str(stores["control_store"]),
        "lock": PROJECT_ROOT / str(execution["process_lock"]),
        "chain_state": PROJECT_ROOT / str(execution["chain_state"]),
        "manifest": PROJECT_ROOT / str(execution["run_manifest"]),
        "contract_artifact": PROJECT_ROOT / str(execution["contract_artifact"]),
        "contract_diff": PROJECT_ROOT / str(execution["contract_diff_artifact"]),
        "start_gate": PROJECT_ROOT / str(execution["readiness_artifact"]),
        "input_precheck": PROJECT_ROOT / str(execution["input_precheck_artifact"]),
        "benchmark": PROJECT_ROOT / str(execution["worker_benchmark_artifact"]),
        "plan": PROJECT_ROOT / str(execution["descriptive_plan_artifact"]),
        "audit": PROJECT_ROOT / str(execution["final_audit_artifact"]),
        "report": PROJECT_ROOT / str(execution["descriptive_report_artifact"]),
        "summary": PROJECT_ROOT / str(execution["completion_summary_artifact"]),
        "log": PROJECT_ROOT / str(execution["log_path"]),
    }


def _logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("multi_asset_development_v6")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _set_below_normal_priority() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        process = ctypes.windll.kernel32.GetCurrentProcess()
        return bool(ctypes.windll.kernel32.SetPriorityClass(process, 0x00004000))
    except (AttributeError, OSError):  # pragma: no cover - defensive OS path
        return False


class _StayAwake:
    def __enter__(self) -> "_StayAwake":
        self.enabled = False
        if os.name == "nt":
            try:
                import ctypes

                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED.  This is process-scoped
                # and is automatically released if the process terminates.
                self.enabled = bool(
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
                )
            except (AttributeError, OSError):  # pragma: no cover
                self.enabled = False
        return self

    def __exit__(self, *args: object) -> None:
        if self.enabled and os.name == "nt":
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def _probe_lock_clear(path: Path) -> tuple[bool, str]:
    lock = SwingRunLock(path)
    try:
        lock.acquire()
    except SwingRunAlreadyActiveError:
        return False, f"ACTIVE_LOCK:{path.name}"
    else:
        lock.release()
        return True, "CLEAR"


def dispatch_readiness(contract: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    disk = shutil.disk_usage(PROJECT_ROOT)
    resources = system_resources()
    detail: dict[str, object] = {
        "disk_free_bytes": int(disk.free),
        "minimum_disk_free_bytes": MINIMUM_DISK_FREE_BYTES,
        "available_memory_bytes": int(
            resources.get("available_physical_memory_bytes_at_start") or 0
        ),
        "minimum_available_memory_bytes": MINIMUM_AVAILABLE_MEMORY_BYTES,
    }
    if disk.free < MINIMUM_DISK_FREE_BYTES:
        return False, "DISK_RESERVE_BELOW_30_GIB", detail
    available = int(resources.get("available_physical_memory_bytes_at_start") or 0)
    if available and available < MINIMUM_AVAILABLE_MEMORY_BYTES:
        return False, "AVAILABLE_MEMORY_BELOW_2_GIB", detail
    execution = dict(contract["development_execution"])
    protection = PROJECT_ROOT / str(execution["production_protection_config"])
    active = campaign_active_production_jobs(
        load_campaign_config(protection), project_root=PROJECT_ROOT
    )
    detail["active_production_jobs"] = list(active)
    if active:
        return False, "ACTIVE_PRODUCTION_JOB:" + ",".join(active), detail
    fx_clear, fx_reason = _probe_lock_clear(FX_OBSERVER_LOCK)
    detail["fx_observer_lock"] = fx_reason
    if not fx_clear:
        return False, fx_reason, detail
    return True, "CLEAR", detail


def _load_required_start_gate(
    path: Path, *, contract_fingerprint: str
) -> dict[str, object]:
    if not path.exists():
        raise DevelopmentV6RunnerError("v6 start-gate artifact is missing.")
    gate = json.loads(path.read_text(encoding="utf-8"))
    if not _verify_self_fingerprint(gate):
        raise DevelopmentV6RunnerError("v6 start-gate fingerprint is invalid.")
    if gate.get("version") != START_GATE_VERSION or gate.get("status") != "PASS":
        raise DevelopmentV6RunnerError("v6 start gate is not PASS.")
    if gate.get("start_authorized") is not True:
        raise DevelopmentV6RunnerError("v6 start gate does not authorize a start.")
    if gate.get("blockers") != []:
        raise DevelopmentV6RunnerError("v6 start gate contains blockers.")
    if gate.get("development_contract_fingerprint") != contract_fingerprint:
        raise DevelopmentV6RunnerError("v6 start gate belongs to another contract.")
    raw_gates = gate.get("gates")
    if not isinstance(raw_gates, Mapping) or set(raw_gates) != set(TOP_LEVEL_GATES):
        raise DevelopmentV6RunnerError(
            "v6 start gate does not contain the exact required gate groups."
        )
    if any(value != "PASS" for value in raw_gates.values()):
        raise DevelopmentV6RunnerError("At least one v6 start-gate group is not PASS.")
    return gate


def _verify_runtime_code_provenance(
    *, contract: Mapping[str, object], paths: Mapping[str, Path]
) -> dict[str, object]:
    """Re-hash the frozen implementation and prove the scheduled checkout."""

    from multi_asset_development_v6_inputs import (
        build_v6_implementation_provenance,
    )

    gate = _load_required_start_gate(
        paths["start_gate"],
        contract_fingerprint=str(contract["contract_fingerprint"]),
    )
    try:
        input_payload = json.loads(
            paths["input_precheck"].read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentV6RunnerError(
            "Frozen v6 input-precheck is unreadable at runtime."
        ) from exc
    if not _verify_self_fingerprint(input_payload) or input_payload.get(
        "status"
    ) != "PASS":
        raise DevelopmentV6RunnerError(
            "Frozen v6 input-precheck is not self-valid PASS at runtime."
        )
    labels = [str(value) for value in input_payload.get("implementation_paths") or []]
    if not labels or len(labels) != len(set(labels)):
        raise DevelopmentV6RunnerError(
            "Frozen implementation-path set is empty or duplicated."
        )
    implementation_paths: list[Path] = []
    for label in labels:
        relative = Path(label)
        if relative.is_absolute() or ".." in relative.parts:
            raise DevelopmentV6RunnerError(
                f"Unsafe frozen implementation path: {label}"
            )
        resolved = (PROJECT_ROOT / relative).resolve()
        try:
            resolved.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise DevelopmentV6RunnerError(
                f"Frozen implementation path leaves project root: {label}"
            ) from exc
        implementation_paths.append(resolved)
    current = build_v6_implementation_provenance(
        implementation_paths, project_root=PROJECT_ROOT
    )
    stored_hashes = {
        str(key): str(value)
        for key, value in dict(input_payload.get("implementation_sha256") or {}).items()
    }
    stored_fingerprint = dict(input_payload.get("contract_inputs") or {}).get(
        "implementation_fingerprint"
    )
    contract_fingerprint = dict(contract.get("reference_fingerprints") or {}).get(
        "development_code_fingerprint"
    )
    checks = {
        "complete": current.get("complete") is True,
        "paths_exact": list(current.get("implementation_paths") or []) == labels,
        "hashes_exact": dict(current.get("implementation_sha256") or {})
        == stored_hashes,
        "input_fingerprint_exact": current.get("implementation_fingerprint")
        == stored_fingerprint,
        "contract_fingerprint_exact": current.get("implementation_fingerprint")
        == contract_fingerprint,
        "start_gate_fingerprint_exact": current.get("implementation_fingerprint")
        == dict(gate.get("implementation_code_audit") or {}).get(
            "current_implementation_fingerprint"
        ),
    }
    current_head = _git("rev-parse", "HEAD")
    expected_heads = {
        str(value)
        for value in (
            dict(gate.get("git_provenance") or {}).get("head"),
            (
                json.loads(paths["manifest"].read_text(encoding="utf-8")).get(
                    "commit"
                )
                if paths["manifest"].exists()
                else None
            ),
        )
        if value
    }
    checks["head_matches_frozen_gate_and_manifest"] = bool(expected_heads) and (
        expected_heads == {current_head}
    )
    checks["tracked_worktree_clean"] = not bool(
        _git("status", "--porcelain", "--untracked-files=no")
    )
    if not all(checks.values()):
        raise DevelopmentV6RunnerError(
            f"Runtime implementation/commit provenance drift: {checks}"
        )
    return {
        "status": "PASS",
        "implementation_fingerprint": current.get("implementation_fingerprint"),
        "implementation_file_count": len(stored_hashes),
        "head": current_head,
        "checks": checks,
    }


def build_run_manifest(
    *,
    contract: Mapping[str, object],
    contract_artifact: Mapping[str, object],
    universe: Mapping[str, object],
    work_plan: Mapping[str, object],
    started_at: str,
) -> dict[str, object]:
    references = dict(contract["reference_fingerprints"])
    execution = dict(contract["development_execution"])
    basis = {
        "contract_fingerprint": contract["contract_fingerprint"],
        "combined_input_fingerprint": references["combined_input_fingerprint"],
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
        "code_commit": _git("rev-parse", "HEAD"),
    }
    run_id = "mad1-development-v6-" + fingerprint(basis)[:24]
    payload: dict[str, object] = {
        "version": RUN_MANIFEST_VERSION,
        "run_id": run_id,
        "research_epoch": execution["research_epoch"],
        "development_contract_version": contract["contract_version"],
        "development_contract_fingerprint": contract["contract_fingerprint"],
        "contract_artifact_fingerprint": contract_artifact["artifact_fingerprint"],
        "parent_v5_run_id": dict(contract["reprocessing_parent"])["run_id"],
        "combined_input_fingerprint": references["combined_input_fingerprint"],
        "equity_etf_projection_fingerprint": references[
            "equity_etf_projection_fingerprint"
        ],
        "crypto_projection_fingerprint": references["crypto_projection_fingerprint"],
        "fx_projection_fingerprint": references["fx_projection_fingerprint"],
        "input_precheck_artifact_fingerprint": references[
            "input_precheck_artifact_fingerprint"
        ],
        "worker_benchmark_artifact_fingerprint": references[
            "worker_benchmark_artifact_fingerprint"
        ],
        "descriptive_plan_artifact_fingerprint": references[
            "descriptive_plan_artifact_fingerprint"
        ],
        "code_fingerprint": references["development_code_fingerprint"],
        "identity_fingerprint": references["identity_registry_fingerprint"],
        "dependency_policy_fingerprint": references[
            "historical_dependency_policy_fingerprint"
        ],
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
        "total_planned_work_units": work_plan["total_planned_work_units"],
        "worker_count": execution["worker_count"],
        "sqlite_writer_count": execution["sqlite_writer_count"],
        "branch": _git("branch", "--show-current"),
        "commit": _git("rev-parse", "HEAD"),
        "runner_version": RUNNER_VERSION,
        "command": "scripts/run_multi_asset_development_v6_chain.py --advance",
        "scheduler": execution["scheduler_task_name"],
        "started_at": started_at,
        "status_at_creation": "STARTING",
        "development_only": True,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
        "automatic_orders_allowed": False,
    }
    payload["run_manifest_fingerprint"] = fingerprint(payload)
    return payload


def prepare_canonical_run(
    contract: Mapping[str, object], paths: Mapping[str, Path]
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    artifact = json.loads(paths["contract_artifact"].read_text(encoding="utf-8"))
    if not verify_development_v6_contract_artifact(artifact):
        raise DevelopmentV6RunnerError("Frozen v6 contract artifact is invalid.")
    if artifact.get("contract_fingerprint") != contract["contract_fingerprint"]:
        raise DevelopmentV6RunnerError("Frozen v6 contract differs from loader contract.")
    _load_required_start_gate(
        paths["start_gate"], contract_fingerprint=str(contract["contract_fingerprint"])
    )
    references = dict(contract["reference_fingerprints"])
    universe = build_v6_universe(
        combined_input_fingerprint=str(references["combined_input_fingerprint"]),
        equity_etf_projection_fingerprint=str(
            references["equity_etf_projection_fingerprint"]
        ),
        crypto_projection_fingerprint=str(references["crypto_projection_fingerprint"]),
        fx_projection_fingerprint=str(references["fx_projection_fingerprint"]),
    )
    work_plan = build_v6_work_plan(universe=universe, contract=contract)
    if paths["manifest"].exists():
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        expected_fp = manifest.get("run_manifest_fingerprint")
        manifest_basis = dict(manifest)
        manifest_basis.pop("run_manifest_fingerprint", None)
        if expected_fp != fingerprint(manifest_basis):
            raise DevelopmentV6RunnerError("Run manifest self-fingerprint is invalid.")
    else:
        if _git("status", "--porcelain"):
            raise DevelopmentV6RunnerError(
                "Run manifest may only be frozen from a clean tracked worktree."
            )
        manifest = build_run_manifest(
            contract=contract,
            contract_artifact=artifact,
            universe=universe,
            work_plan=work_plan,
            started_at=utc_now(),
        )
        _write_immutable(paths["manifest"], manifest)
    current_head = _git("rev-parse", "HEAD")
    if str(manifest["commit"]) != current_head:
        raise DevelopmentV6RunnerError(
            "Current HEAD differs from the immutable v6 run-manifest commit."
        )
    checks = {
        "contract": manifest["development_contract_fingerprint"]
        == contract["contract_fingerprint"],
        "input": manifest["combined_input_fingerprint"]
        == references["combined_input_fingerprint"],
        "universe": manifest["universe_fingerprint"]
        == universe["universe_fingerprint"],
        "work_plan": manifest["work_plan_fingerprint"]
        == work_plan["work_plan_fingerprint"],
        "worker": int(manifest["worker_count"])
        == int(dict(contract["development_execution"])["worker_count"]),
        "single_writer": int(manifest["sqlite_writer_count"]) == 1,
    }
    if not all(checks.values()):
        raise DevelopmentV6RunnerError(f"Run manifest mismatch: {checks}")
    initialize_v6_run(
        run_manifest=manifest,
        work_plan=work_plan,
        feature_path=paths["feature"],
        outcome_path=paths["outcome"],
        control_path=paths["control"],
    )
    return manifest, universe, work_plan


def _rebuild_expected_work_plan(
    contract: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Recreate the deterministic universe/plan without touching run stores."""

    references = dict(contract["reference_fingerprints"])
    universe = build_v6_universe(
        combined_input_fingerprint=str(references["combined_input_fingerprint"]),
        equity_etf_projection_fingerprint=str(
            references["equity_etf_projection_fingerprint"]
        ),
        crypto_projection_fingerprint=str(references["crypto_projection_fingerprint"]),
        fx_projection_fingerprint=str(references["fx_projection_fingerprint"]),
    )
    return universe, build_v6_work_plan(universe=universe, contract=contract)


def _prefreeze_contract_basis_fingerprint() -> str:
    """Return the exact pre-freeze contract basis bound into the plan."""

    return fingerprint(build_development_v6_benchmark_contract())


def _process_result(
    *,
    result: Mapping[str, object],
    units: list[dict[str, object]],
    manifest: Mapping[str, object],
    paths: Mapping[str, Path],
    writer_pid: int,
) -> int:
    run_id = str(manifest["run_id"])
    if not units or result.get("asset_key") != units[0].get("asset_key"):
        raise DevelopmentV6RunnerError("Worker result belongs to another asset batch.")
    if result.get("skip_reason_code"):
        expected_unit_ids = [str(unit["work_unit_id"]) for unit in units]
        returned_unit_ids = [
            str(unit_id) for unit_id in result.get("unit_ids") or []
        ]
        if returned_unit_ids != expected_unit_ids:
            raise DevelopmentV6RunnerError("No-data result has an incomplete unit set.")
        units_by_id = {str(unit["work_unit_id"]): unit for unit in units}
        for unit_id in returned_unit_ids:
            skip_work_unit(
                writer_pid=writer_pid,
                run_id=run_id,
                unit=units_by_id[unit_id],
                reason_code=str(result["skip_reason_code"]),
                reason=str(result["skip_reason"]),
                feature_path=paths["feature"],
                outcome_path=paths["outcome"],
                control_path=paths["control"],
            )
        return len(units)
    by_id = {
        str(item["work_unit_id"]): item for item in units
    }
    unit_results = list(result.get("unit_results") or [])
    if {str(dict(item["unit"])["work_unit_id"]) for item in unit_results} != set(by_id):
        raise DevelopmentV6RunnerError("Worker returned incomplete asset batch.")
    for unit_result in unit_results:
        unit = dict(unit_result["unit"])
        persist_and_complete_work_unit(
            writer_pid=writer_pid,
            run_id=run_id,
            unit=unit,
            features=list(unit_result["features"]),
            outcomes=list(unit_result["outcomes"]),
            summary=dict(unit_result["summary"]),
            feature_path=paths["feature"],
            outcome_path=paths["outcome"],
            control_path=paths["control"],
        )
    return len(unit_results)


def run_development_compute(
    *,
    contract: Mapping[str, object],
    paths: Mapping[str, Path],
    maximum_asset_batches: int | None = None,
    executor_factory: Callable[..., ProcessPoolExecutor] = ProcessPoolExecutor,
) -> dict[str, object]:
    manifest, universe, _ = prepare_canonical_run(contract, paths)
    run_id = str(manifest["run_id"])
    status = checkpoint_status(control_path=paths["control"], run_id=run_id)
    if status["status"] != "RUNNING":
        return status
    reset_count = reset_interrupted_units(control_path=paths["control"], run_id=run_id)
    logger = _logger(paths["log"])
    _set_below_normal_priority()
    append_run_event(
        control_path=paths["control"],
        run_id=run_id,
        event_type="RUNNER_STARTED",
        details={"pid": os.getpid(), "reset_interrupted_units": reset_count},
    )
    assets = {str(item["asset_key"]): dict(item) for item in universe["assets"]}
    execution = dict(contract["development_execution"])
    worker_count = int(execution["worker_count"])
    maximum_attempts = int(execution["maximum_attempts_per_work_unit"])
    input_path = paths["input_precheck"]
    in_flight: dict[Future[dict[str, object]], list[dict[str, object]]] = {}
    dispatched = 0
    completed_units = 0
    systematic_errors: list[str] = []
    yield_reason: str | None = None
    with _StayAwake(), executor_factory(max_workers=worker_count) as executor:
        while True:
            while (
                not systematic_errors
                and yield_reason is None
                and len(in_flight) < worker_count
                and (maximum_asset_batches is None or dispatched < maximum_asset_batches)
            ):
                if paths["chain_state"].exists():
                    operator_request = _active_operator_request(paths["chain_state"])
                    if operator_request in {"PAUSE", "STOP"}:
                        yield_reason = (
                            "OPERATOR_STOP_REQUESTED"
                            if operator_request == "STOP"
                            else "OPERATOR_PAUSE_REQUESTED"
                        )
                        break
                clear, reason, detail = dispatch_readiness(contract)
                if not clear:
                    yield_reason = reason
                    logger.info("Dispatch paused | reason=%s detail=%s", reason, detail)
                    break
                units = claim_next_asset_batch(control_path=paths["control"], run_id=run_id)
                if not units:
                    break
                asset = assets[str(units[0]["asset_key"])]
                future = executor.submit(
                    compute_v6_asset_batch,
                    asset=asset,
                    units=units,
                    contract=dict(contract),
                    input_precheck_artifact=input_path,
                )
                in_flight[future] = units
                dispatched += 1
            if not in_flight:
                break
            done, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
            for future in done:
                units = in_flight.pop(future)
                try:
                    result = future.result()
                    completed_units += _process_result(
                        result=result,
                        units=units,
                        manifest=manifest,
                        paths=paths,
                        writer_pid=os.getpid(),
                    )
                    checkpoint_sqlite(paths["feature"], paths["outcome"], paths["control"])
                    append_run_event(
                        control_path=paths["control"],
                        run_id=run_id,
                        event_type="ASSET_BATCH_COMPLETED",
                        details={
                            "asset_key": units[0]["asset_key"],
                            "work_units": len(units),
                        },
                    )
                    logger.info(
                        "Asset batch completed | asset=%s units=%s",
                        units[0]["asset_key"],
                        len(units),
                    )
                except Exception as exc:
                    disposition = fail_asset_batch(
                        control_path=paths["control"],
                        run_id=run_id,
                        units=units,
                        error=exc,
                        maximum_attempts=maximum_attempts,
                        retryable=is_retryable_compute_error(exc),
                    )
                    append_run_event(
                        control_path=paths["control"],
                        run_id=run_id,
                        event_type="ASSET_BATCH_" + disposition,
                        details={
                            "asset_key": units[0]["asset_key"],
                            "error_class": type(exc).__name__,
                            "error": str(exc)[:1000],
                        },
                    )
                    logger.exception("Asset batch failed | asset=%s", units[0]["asset_key"])
                    if disposition == "FAILED_SYSTEMATIC":
                        systematic_errors.append(
                            f"{units[0]['asset_key']}:{type(exc).__name__}:{str(exc)[:500]}"
                        )
                    elif disposition == "RETRY":
                        # Do not immediately reclaim the same transiently
                        # failed batch.  Drain already-running workers and let
                        # the five-minute scheduler provide a bounded backoff.
                        yield_reason = "TRANSIENT_ERROR_BACKOFF_TO_NEXT_SCHEDULER"
            if maximum_asset_batches is not None and dispatched >= maximum_asset_batches:
                yield_reason = "MAXIMUM_ASSET_BATCHES_REACHED"
                if not in_flight:
                    break
            if yield_reason and not in_flight:
                break
    if systematic_errors:
        pause_run_for_review(
            control_path=paths["control"],
            run_id=run_id,
            reason=" | ".join(systematic_errors),
        )
    else:
        mark_run_complete(control_path=paths["control"], run_id=run_id)
    status = checkpoint_status(control_path=paths["control"], run_id=run_id)
    status.update(
        {
            "asset_batches_dispatched_this_invocation": dispatched,
            "work_units_completed_this_invocation": completed_units,
            "yield_reason": yield_reason,
            "systematic_errors": systematic_errors,
        }
    )
    return status


def _default_chain_state(contract: Mapping[str, object]) -> dict[str, object]:
    return {
        "version": CHAIN_VERSION,
        "phase": "PRECHECK",
        "status": "RUNNING",
        "run_id": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "last_successful_work_unit": None,
        "blocker": None,
        "pause_requested": False,
        "stop_requested": False,
        "next_allowed_action": "Verify frozen start gate, then execute Development only.",
        "contract_fingerprint": contract["contract_fingerprint"],
        "code_commit": _git("rev-parse", "HEAD"),
        "phases": {},
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
    }


def load_chain_state(path: Path, contract: Mapping[str, object]) -> dict[str, object]:
    if not path.exists():
        state = _default_chain_state(contract)
        _atomic_write(path, state)
        return state
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != CHAIN_VERSION:
        raise DevelopmentV6RunnerError("Unknown chain-state version.")
    if state.get("contract_fingerprint") != contract["contract_fingerprint"]:
        raise DevelopmentV6RunnerError("Chain state belongs to another contract.")
    return _overlay_operator_request(path, state)


def update_chain_state(
    path: Path,
    state: Mapping[str, object],
    *,
    phase: str | None = None,
    status: str | None = None,
    blocker: str | None = None,
    next_allowed_action: str | None = None,
    phase_result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    updated = _overlay_operator_request(path, state)
    if phase is not None:
        updated["phase"] = phase
    if status is not None:
        updated["status"] = status
    updated["blocker"] = blocker
    if next_allowed_action is not None:
        updated["next_allowed_action"] = next_allowed_action
    if phase_result is not None:
        phases = dict(updated.get("phases") or {})
        phases[str(state.get("phase"))] = dict(phase_result)
        updated["phases"] = phases
        if phase_result.get("run_id"):
            updated["run_id"] = phase_result["run_id"]
        if phase_result.get("last_completed_work_unit"):
            updated["last_successful_work_unit"] = phase_result[
                "last_completed_work_unit"
            ]
    if updated.get("phase") != "STOP" and (
        updated.get("pause_requested") or updated.get("stop_requested")
    ):
        request = "STOP" if updated.get("stop_requested") else "PAUSE"
        updated["status"] = "PAUSED_REQUIRES_REVIEW"
        updated["blocker"] = f"OPERATOR_{request}_REQUESTED"
    updated["updated_at"] = utc_now()
    _atomic_write(path, updated)
    return updated


def set_operator_request(
    *, chain_state_path: Path, request: str | None
) -> dict[str, object]:
    """Set or clear the persistent cooperative pause/stop request.

    The request artifact is the sole write target.  In particular, this
    function never writes a chain-state snapshot that may have become stale
    while the runner advances to a newer phase.
    """

    if not chain_state_path.exists():
        raise DevelopmentV6RunnerError("Chain state does not exist yet.")
    normalized = request.upper() if request else "RESUME"
    if normalized not in {"RESUME", "PAUSE", "STOP"}:
        raise ValueError(request)
    _atomic_write(
        _operator_request_path(chain_state_path),
        {
            "version": OPERATOR_REQUEST_VERSION,
            "request": normalized,
            "updated_at": utc_now(),
        },
    )
    return read_chain_status(chain_state_path)


def _pause_after_terminal_phase_exception(
    *,
    paths: Mapping[str, Path],
    state: Mapping[str, object],
    phase: str,
    error: Exception,
) -> dict[str, object]:
    """Persist a fail-closed terminal-chain error at the current phase."""

    latest = dict(state)
    try:
        candidate = json.loads(paths["chain_state"].read_text(encoding="utf-8"))
        if candidate.get("version") == CHAIN_VERSION:
            latest = candidate
    except (OSError, json.JSONDecodeError):
        pass
    detail = {
        "status": "EXCEPTION",
        "phase": phase,
        "error_class": type(error).__name__,
        "error": str(error)[:2000],
        "failed_at": utc_now(),
    }
    return update_chain_state(
        paths["chain_state"],
        latest,
        status="PAUSED_REQUIRES_REVIEW",
        blocker=f"{phase}_EXCEPTION:{type(error).__name__}",
        next_allowed_action=(
            f"Review and resolve the persisted {phase} exception; "
            "later phases remain closed."
        ),
        phase_result=detail,
    )


def _build_final_audit_phase(
    *, contract: Mapping[str, object], paths: Mapping[str, Path]
) -> dict[str, object]:
    from multi_asset_development_v6_audit import build_v6_full_audit

    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    _universe, expected_work_plan = _rebuild_expected_work_plan(contract)
    return build_v6_full_audit(
        run_id=str(manifest["run_id"]),
        feature_path=paths["feature"],
        outcome_path=paths["outcome"],
        control_path=paths["control"],
        expected_work_plan=expected_work_plan,
        final_contract=paths["contract_artifact"],
        input_precheck=paths["input_precheck"],
        expected_run_manifest=manifest,
        artifact_path=paths["audit"],
        created_at=utc_now(),
    )


def _build_descriptive_report_phase(
    *, contract: Mapping[str, object], paths: Mapping[str, Path]
) -> dict[str, object]:
    from multi_asset_development_v6_reporting import build_v6_descriptive_report

    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    return build_v6_descriptive_report(
        run_id=str(manifest["run_id"]),
        feature_path=paths["feature"],
        outcome_path=paths["outcome"],
        audit=audit,
        frozen_plan=plan,
        final_contract=paths["contract_artifact"],
        expected_contract_basis_fingerprint=(
            _prefreeze_contract_basis_fingerprint()
        ),
        created_at=utc_now(),
        artifact_path=paths["report"],
    )


def _build_completion_summary_phase(
    *,
    contract: Mapping[str, object],
    paths: Mapping[str, Path],
) -> dict[str, object]:
    from multi_asset_development_v6_reporting import build_v6_completion_summary

    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    runtime_status = checkpoint_status(
        control_path=paths["control"], run_id=str(manifest["run_id"])
    )
    artifact_paths = {
        name: str(Path(path).resolve()) for name, path in sorted(paths.items())
    }
    return build_v6_completion_summary(
        audit=audit,
        frozen_plan=plan,
        descriptive_report=report,
        final_contract=paths.get("contract_artifact"),
        run_manifest=manifest,
        input_precheck=paths.get("input_precheck"),
        worker_benchmark=paths.get("benchmark"),
        runtime_status=runtime_status,
        artifact_paths=artifact_paths,
        created_at=utc_now(),
        artifact_path=paths["summary"],
    )


def advance_chain(*, maximum_asset_batches: int | None = None) -> dict[str, object]:
    contract = load_development_v6_contract()
    paths = contract_paths(contract)
    # The scheduler must be installed and enabled before the preflight can bind
    # its observed operating-system contract.  Its first automatic trigger can
    # therefore race with creation of the immutable start gate.  Keep that
    # harmless: an absent or invalid gate must not create chain state, stores,
    # a manifest, or any other persistent run artifact.
    try:
        _load_required_start_gate(
            paths["start_gate"],
            contract_fingerprint=str(contract["contract_fingerprint"]),
        )
    except Exception as exc:
        return {
            "version": CHAIN_VERSION,
            "phase": "PRECHECK",
            "status": "BLOCKED_BEFORE_START",
            "run_id": None,
            "blocker": f"START_GATE_PRECHECK_FAILED:{type(exc).__name__}",
            "error_class": type(exc).__name__,
            "error": str(exc)[:2000],
            "next_allowed_action": (
                "Create or repair the immutable PASS start gate; no run or "
                "chain artifact was created."
            ),
            "contract_fingerprint": contract["contract_fingerprint"],
            "chain_state_created": False,
            "development_run_started": False,
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
            "forward_opened": False,
            "paper_opened": False,
            "shadow_opened": False,
            "broker_opened": False,
        }
    process_lock = SwingRunLock(paths["lock"])
    try:
        process_lock.acquire()
    except SwingRunAlreadyActiveError:
        # A competing first invocation may own the lock without having written
        # its initial state yet.  Observe whatever is durable, but never call
        # load_chain_state here because that helper creates a missing state.
        state = read_chain_status(paths["chain_state"])
        return {**state, "duplicate_start_rejected": True}
    try:
        # The initial state is mutable run state.  Serialize both its first
        # creation and every read used to decide a transition under the v6
        # process lock so concurrent scheduler/manual starts cannot overwrite
        # one another with stale first-start snapshots.
        state = load_chain_state(paths["chain_state"], contract)
        if state.get("phase") == "STOP":
            return {**state, "terminal_noop": True}
        if state.get("pause_requested") or state.get("stop_requested"):
            return {
                **state,
                "operator_request_active": (
                    "STOP" if state.get("stop_requested") else "PAUSE"
                ),
            }
        if state.get("status") == "PAUSED_REQUIRES_REVIEW":
            return {**state, "persistent_review_pause": True}
        research_lock = SwingRunLock(GLOBAL_RESEARCH_LOCK)
        try:
            research_lock.acquire()
        except SwingRunAlreadyActiveError:
            return {**state, "research_lock_active": True}
        try:
            try:
                _verify_runtime_code_provenance(contract=contract, paths=paths)
            except Exception as exc:
                return _pause_after_terminal_phase_exception(
                    paths=paths,
                    state=state,
                    phase="RUNTIME_CODE_PROVENANCE",
                    error=exc,
                )
            if state["phase"] == "PRECHECK":
                gate = _load_required_start_gate(
                    paths["start_gate"],
                    contract_fingerprint=str(contract["contract_fingerprint"]),
                )
                state = update_chain_state(
                    paths["chain_state"],
                    state,
                    phase="RUN",
                    next_allowed_action="Execute/resume the immutable Development-v6 run.",
                    phase_result={
                        "status": "PASS",
                        "artifact_fingerprint": gate["artifact_fingerprint"],
                    },
                )
                if state.get("pause_requested") or state.get("stop_requested"):
                    return state
            if state["phase"] == "RUN":
                result = run_development_compute(
                    contract=contract,
                    paths=paths,
                    maximum_asset_batches=maximum_asset_batches,
                )
                if result["status"] == "PAUSED_REQUIRES_REVIEW":
                    return update_chain_state(
                        paths["chain_state"],
                        state,
                        status="PAUSED_REQUIRES_REVIEW",
                        blocker=str(result.get("pause_reason")),
                        next_allowed_action="Human review required; do not open any later phase.",
                        phase_result=result,
                    )
                if result["status"] != "COMPLETED":
                    return update_chain_state(
                        paths["chain_state"],
                        state,
                        next_allowed_action="Resume RUN on the next safe scheduler invocation.",
                        phase_result=result,
                    )
                state = update_chain_state(
                    paths["chain_state"],
                    state,
                    phase="FINAL_AUDIT",
                    next_allowed_action="Run the full read-only integrity audit exactly once.",
                    phase_result=result,
                )
                if state.get("pause_requested") or state.get("stop_requested"):
                    return state
            if state["phase"] == "FINAL_AUDIT":
                try:
                    audit = _build_final_audit_phase(
                        contract=contract, paths=paths
                    )
                except Exception as exc:
                    return _pause_after_terminal_phase_exception(
                        paths=paths, state=state, phase="FINAL_AUDIT", error=exc
                    )
                if audit.get("status") != "PASS":
                    return update_chain_state(
                        paths["chain_state"],
                        state,
                        status="PAUSED_REQUIRES_REVIEW",
                        blocker="FINAL_INTEGRITY_AUDIT_FAILED",
                        next_allowed_action="Human review required; descriptive report remains closed.",
                        phase_result=audit,
                    )
                state = update_chain_state(
                    paths["chain_state"],
                    state,
                    phase="DESCRIPTIVE_REPORT",
                    next_allowed_action="Build only the frozen descriptive Development report.",
                    phase_result=audit,
                )
                if state.get("pause_requested") or state.get("stop_requested"):
                    return state
            if state["phase"] == "DESCRIPTIVE_REPORT":
                try:
                    report = _build_descriptive_report_phase(
                        contract=contract, paths=paths
                    )
                except Exception as exc:
                    return _pause_after_terminal_phase_exception(
                        paths=paths,
                        state=state,
                        phase="DESCRIPTIVE_REPORT",
                        error=exc,
                    )
                state = update_chain_state(
                    paths["chain_state"],
                    state,
                    phase="SUMMARY",
                    next_allowed_action="Write the technical completion summary, then stop.",
                    phase_result=report,
                )
                if state.get("pause_requested") or state.get("stop_requested"):
                    return state
            if state["phase"] == "SUMMARY":
                try:
                    summary = _build_completion_summary_phase(
                        contract=contract, paths=paths
                    )
                except Exception as exc:
                    return _pause_after_terminal_phase_exception(
                        paths=paths, state=state, phase="SUMMARY", error=exc
                    )
                state = update_chain_state(
                    paths["chain_state"],
                    state,
                    phase="STOP",
                    status="COMPLETED_AUDITED_AWAITING_REVIEW",
                    next_allowed_action="STOP. Await human review; do not open Validation or any new research.",
                    phase_result=summary,
                )
            return state
        finally:
            research_lock.release()
    finally:
        process_lock.release()


__all__ = [
    "CHAIN_VERSION",
    "DEFAULT_CHAIN_STATE_PATH",
    "DevelopmentV6RunnerError",
    "RUNNER_VERSION",
    "START_GATE_VERSION",
    "advance_chain",
    "build_run_manifest",
    "contract_paths",
    "dispatch_readiness",
    "load_chain_state",
    "prepare_canonical_run",
    "read_chain_status",
    "run_development_compute",
    "set_operator_request",
    "update_chain_state",
]
