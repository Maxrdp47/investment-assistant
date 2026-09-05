from __future__ import annotations

"""Fail-closed start gate for the immutable Development-v6 reprocessing run.

The module does not execute research, create evidence stores, install scheduler
tasks, or run tests on behalf of the caller.  It verifies explicit evidence
collected after the final code commit and writes the canonical start gate only
when every blocking check passes.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from multi_asset_development_v6_benchmark import (
    REQUIRED_TECHNICAL_COVERAGE_GATES,
    classify_worker_configurations,
    configuration_evidence_checks,
    eligible_worker_counts,
    system_resources,
)
from multi_asset_development_v6_contract import (
    DEFAULT_V6_CONFIG_PATH,
    DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
    DEVELOPMENT_V6_CONTRACT_DIFF_VERSION,
    DEVELOPMENT_V6_CONTRACT_VERSION,
    build_development_v6_benchmark_contract,
    verify_development_v6_contract_artifact,
)
from multi_asset_development_v6_inputs import (
    DEFAULT_CRYPTO_STORE,
    DEFAULT_EQUITY_ETF_STORE,
    MultiAssetV6InputError,
    default_implementation_paths,
    verify_v6_current_sources,
)
from multi_asset_development_execution import DEFAULT_FX_STORE
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
START_GATE_VERSION = "multi-asset-development-v6-start-gate-2026.09.05-v1"
DEFAULT_CONTRACT_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_discovery_v1_development_contract_2026-09-05-v6.json"
)
DEFAULT_CONTRACT_DIFF = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_discovery_v1_development_contract_diff_2026-09-05-v6.json"
)

MINIMUM_DISK_RESERVE_BYTES = 30 * 1024**3
MINIMUM_AVAILABLE_MEMORY_BYTES = 2 * 1024**3
STORE_ESTIMATE_MULTIPLIER = 1.25
MINIMUM_TRANSIENT_RESERVE_BYTES = 4 * 1024**3
REPORT_AND_LOG_RESERVE_BYTES = 512 * 1024**2

REQUIRED_LOCAL_GATES = (
    "compileall",
    "full_pytest",
    "repository_safety",
    "offline_smoke",
    "streamlit_start",
    "git_diff_check",
)
TOP_LEVEL_GATES = (
    "CONTRACT_AND_DIFF",
    "IMMUTABLE_V5_PARENT",
    "INPUT_BINDING",
    "WORKER_BENCHMARK_BINDING",
    "DESCRIPTIVE_PLAN_BINDING",
    "RESOURCES",
    "PYTHON_ENVIRONMENT",
    "GIT_PROVENANCE",
    "LOCAL_VERIFICATION",
    "CI_VERIFICATION",
    "SCHEDULER_CONTRACT",
    "RUN_ABSENT",
)


class DevelopmentV6PreflightError(RuntimeError):
    """The start gate cannot be evaluated or immutably persisted."""


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentV6PreflightError(f"{label} is not readable: {path}") from exc
    if not isinstance(value, dict):
        raise DevelopmentV6PreflightError(f"{label} must be a JSON object: {path}")
    return value


def _self_fingerprint_valid(
    payload: Mapping[str, object], *, field: str = "artifact_fingerprint"
) -> bool:
    expected = str(payload.get(field) or "")
    basis = dict(payload)
    basis.pop(field, None)
    return len(expected) == 64 and expected == fingerprint(basis)


def _aware_artifact_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _contract_fingerprint_valid(contract: Mapping[str, object]) -> bool:
    expected = str(contract.get("contract_fingerprint") or "")
    basis = dict(contract)
    basis.pop("contract_fingerprint", None)
    return len(expected) == 64 and expected == fingerprint(basis)


def _resolve_project_path(project_root: Path, value: object, *, label: str) -> Path:
    relative = Path(str(value or ""))
    if not str(relative) or relative.is_absolute():
        raise DevelopmentV6PreflightError(f"{label} must be project-relative.")
    root = Path(project_root).resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise DevelopmentV6PreflightError(f"{label} leaves the project root.") from exc
    return resolved


def _relative(project_root: Path, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix()
    except ValueError:
        return str(Path(path).resolve())


def _file_size(path: Path) -> int:
    try:
        return int(Path(path).stat().st_size)
    except OSError:
        return 0


def _implementation_label(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _audit_implementation_code(
    *,
    input_precheck: Mapping[str, object],
    contract: Mapping[str, object],
    contract_artifact: Mapping[str, object],
    project_root: Path,
    implementation_paths: Sequence[Path] | None = None,
    tracked_implementation_labels: Sequence[str] | None = None,
) -> tuple[dict[str, object], dict[str, bool]]:
    """Re-hash the exact frozen implementation set and prove it is committed."""

    paths = tuple(
        Path(path)
        for path in (
            default_implementation_paths()
            if implementation_paths is None
            else implementation_paths
        )
    )
    expected_labels = [_implementation_label(path) for path in paths]
    stored_hashes = {
        str(label): str(value)
        for label, value in dict(input_precheck.get("implementation_sha256") or {}).items()
    }
    current_hashes: dict[str, str] = {}
    missing_labels: list[str] = []
    non_file_labels: list[str] = []
    for path, label in zip(paths, expected_labels):
        if not path.exists():
            missing_labels.append(label)
            continue
        if not path.is_file():
            non_file_labels.append(label)
            continue
        current_hashes[label] = file_sha256(path)

    if tracked_implementation_labels is None:
        tracked: set[str] = set()
        tracking_errors: dict[str, str] = {}
        root = Path(project_root).resolve()
        for path, label in zip(paths, expected_labels):
            try:
                relative = path.resolve().relative_to(root).as_posix()
            except ValueError:
                tracking_errors[label] = "IMPLEMENTATION_PATH_OUTSIDE_PROJECT"
                continue
            output, error = _git(root, "ls-files", "--error-unmatch", "--", relative)
            if error is not None:
                tracking_errors[label] = error
            elif output:
                tracked.add(label)
    else:
        tracked = {str(label) for label in tracked_implementation_labels}
        tracking_errors = {}

    expected_set = set(expected_labels)
    stored_set = set(stored_hashes)
    current_fingerprint = fingerprint(current_hashes) if current_hashes else None
    input_fingerprint = dict(input_precheck.get("contract_inputs") or {}).get(
        "implementation_fingerprint"
    )
    contract_fingerprint = dict(contract.get("reference_fingerprints") or {}).get(
        "development_code_fingerprint"
    )
    checks = {
        "implementation_path_list_nonempty": bool(paths),
        "implementation_labels_unique": len(expected_labels) == len(expected_set),
        "no_missing_implementation_file": not missing_labels,
        "every_implementation_path_is_file": not non_file_labels,
        "stored_label_set_exact": stored_set == expected_set,
        "rehash_label_set_exact": set(current_hashes) == expected_set,
        "stored_hashes_match_current_files": stored_hashes == current_hashes,
        "every_implementation_file_tracked_at_head": tracked == expected_set
        and not tracking_errors,
        "current_fingerprint_matches_input_contract": current_fingerprint
        == input_fingerprint,
        "current_fingerprint_matches_contract_reference": current_fingerprint
        == contract_fingerprint,
        "current_fingerprint_matches_contract_artifact": current_fingerprint
        == contract_artifact.get("development_code_fingerprint"),
    }
    details: dict[str, object] = {
        "expected_labels": sorted(expected_set),
        "stored_labels": sorted(stored_set),
        "current_labels": sorted(current_hashes),
        "missing_labels": sorted(missing_labels),
        "non_file_labels": sorted(non_file_labels),
        "missing_stored_labels": sorted(expected_set - stored_set),
        "additional_stored_labels": sorted(stored_set - expected_set),
        "untracked_labels": sorted(expected_set - tracked),
        "tracking_errors": dict(sorted(tracking_errors.items())),
        "stored_sha256": dict(sorted(stored_hashes.items())),
        "current_sha256": dict(sorted(current_hashes.items())),
        "current_implementation_fingerprint": current_fingerprint,
        "input_contract_implementation_fingerprint": input_fingerprint,
        "contract_reference_development_code_fingerprint": contract_fingerprint,
        "contract_artifact_development_code_fingerprint": contract_artifact.get(
            "development_code_fingerprint"
        ),
        "committed_proof": (
            "Every expected file is tracked; the separate Git gate requires exact "
            "committed HEAD and a clean tracked worktree."
        ),
    }
    return details, checks


def _audit_current_input_sources(
    *,
    input_path: Path,
    input_precheck: Mapping[str, object],
    project_root: Path,
) -> tuple[dict[str, object], dict[str, bool]]:
    """Re-hash every source frozen by the PASS input precheck.

    ``verify_v6_current_sources`` is the single path-resolution authority for
    this check. It rejects absolute paths, traversal, unknown roots, missing
    files and byte drift. This wrapper records those failures as explicit
    start-gate evidence and keeps the canonical immutable PASS path unused.
    """

    stored_hashes = {
        str(label): str(value)
        for label, value in dict(
            input_precheck.get("source_sha256_before") or {}
        ).items()
    }
    expected_fingerprint = fingerprint(stored_hashes) if stored_hashes else None
    try:
        audit = verify_v6_current_sources(
            input_precheck_artifact=Path(input_path),
            input_precheck=input_precheck,
            project_root=Path(project_root),
        )
    except (MultiAssetV6InputError, OSError, ValueError, TypeError) as exc:
        details: dict[str, object] = {
            "status": "FAIL",
            "source_count": 0,
            "source_sha256": {},
            "source_set_fingerprint": None,
            "resolved_sources": {},
            "error_class": type(exc).__name__,
            "error": str(exc),
        }
        return details, {
            "current_source_rehash_pass": False,
            "current_source_label_set_exact": False,
            "current_source_hashes_exact": False,
            "current_source_count_exact": False,
            "current_source_fingerprint_exact": False,
        }

    current_hashes = {
        str(label): str(value)
        for label, value in dict(audit.get("source_sha256") or {}).items()
    }
    checks = {
        "current_source_rehash_pass": audit.get("status") == "PASS",
        "current_source_label_set_exact": set(current_hashes) == set(stored_hashes),
        "current_source_hashes_exact": current_hashes == stored_hashes,
        "current_source_count_exact": int(audit.get("source_count") or 0)
        == len(stored_hashes)
        and len(stored_hashes) > 0,
        "current_source_fingerprint_exact": audit.get("source_set_fingerprint")
        == expected_fingerprint,
    }
    return dict(audit), checks


def _git(project_root: Path, *args: str) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip()
    return completed.stdout.strip(), None


def capture_environment_snapshot(
    *,
    contract: Mapping[str, object],
    parent_contract: Mapping[str, object],
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    """Capture resources, Python and Git without mutating runtime state."""

    project_root = Path(project_root).resolve()
    execution = dict(contract.get("development_execution") or {})
    selected_worker_count = int(execution.get("worker_count") or 0)
    resources = dict(system_resources())
    disk = shutil.disk_usage(project_root)

    projection_paths = (
        Path(DEFAULT_EQUITY_ETF_STORE),
        Path(DEFAULT_CRYPTO_STORE),
        Path(DEFAULT_FX_STORE),
    )
    parent_stores = dict(parent_contract.get("store_contract") or {})
    parent_store_paths = [
        _resolve_project_path(project_root, parent_stores.get(key), label=f"v5.{key}")
        for key in ("feature_store", "outcome_store", "control_store")
    ]
    projection_bytes = sum(_file_size(path) for path in projection_paths)
    parent_store_bytes = sum(_file_size(path) for path in parent_store_paths)
    estimated_new_store_bytes = max(
        1,
        int(parent_store_bytes * STORE_ESTIMATE_MULTIPLIER),
    )
    transient_bytes = max(
        MINIMUM_TRANSIENT_RESERVE_BYTES,
        int(estimated_new_store_bytes * 0.25),
        max((_file_size(path) for path in projection_paths), default=0),
    )
    required_free = (
        MINIMUM_DISK_RESERVE_BYTES
        + estimated_new_store_bytes
        + transient_bytes
        + REPORT_AND_LOG_RESERVE_BYTES
    )
    resources.update(
        {
            "disk_total_bytes": int(disk.total),
            "disk_free_bytes": int(disk.free),
            "minimum_disk_reserve_after_run_bytes": MINIMUM_DISK_RESERVE_BYTES,
            "projection_store_bytes_already_allocated": projection_bytes,
            "projection_store_paths": [
                {
                    "path": _relative(project_root, path),
                    "exists": path.exists(),
                    "bytes": _file_size(path),
                }
                for path in projection_paths
            ],
            "v5_store_bytes_used_for_estimate": parent_store_bytes,
            "v5_store_paths": [
                {
                    "path": _relative(project_root, path),
                    "exists": path.exists(),
                    "bytes": _file_size(path),
                }
                for path in parent_store_paths
            ],
            "new_v6_store_estimate_bytes": estimated_new_store_bytes,
            "store_estimate_multiplier": STORE_ESTIMATE_MULTIPLIER,
            "wal_temporary_spool_reserve_bytes": transient_bytes,
            "report_and_log_reserve_bytes": REPORT_AND_LOG_RESERVE_BYTES,
            "required_free_before_start_bytes": required_free,
            "selected_worker_count": selected_worker_count,
            "eligible_worker_counts_now": list(eligible_worker_counts(resources)),
        }
    )

    project_python = (
        project_root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    ).resolve()
    python_snapshot = {
        "running_executable": str(Path(sys.executable).resolve()),
        "project_venv_executable": str(project_python),
        "project_venv_exists": project_python.is_file(),
        "running_from_project_venv": Path(sys.executable).resolve() == project_python,
        "version": ".".join(map(str, sys.version_info[:3])),
        "supported_version": sys.version_info >= (3, 11),
    }

    branch, branch_error = _git(project_root, "branch", "--show-current")
    head, head_error = _git(project_root, "rev-parse", "HEAD")
    tracked_status, status_error = _git(
        project_root, "status", "--porcelain", "--untracked-files=no"
    )
    upstream, upstream_error = _git(
        project_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    divergence, divergence_error = _git(
        project_root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
    )
    ahead: int | None = None
    behind: int | None = None
    if divergence is not None:
        parts = divergence.replace("\t", " ").split()
        if len(parts) == 2 and all(item.isdigit() for item in parts):
            ahead, behind = map(int, parts)
    git_snapshot = {
        "branch": branch,
        "head": head,
        "tracked_worktree_clean": tracked_status == "" and status_error is None,
        "tracked_status": tracked_status,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "errors": {
            key: value
            for key, value in {
                "branch": branch_error,
                "head": head_error,
                "status": status_error,
                "upstream": upstream_error,
                "divergence": divergence_error,
            }.items()
            if value
        },
    }
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "resources": resources,
        "python": python_snapshot,
        "git": git_snapshot,
    }


def capture_operational_observations(
    *, project_root: Path = PROJECT_ROOT
) -> dict[str, object]:
    """Observe existing advisory locks without creating or changing lock files."""

    root = Path(project_root).resolve()

    def observe_lock(relative: str, *, name: str) -> dict[str, object]:
        path = root / relative
        result: dict[str, object] = {
            "name": name,
            "path": relative,
            "exists": path.exists(),
            "bytes": _file_size(path),
            "probe_mutated_file": False,
        }
        if not path.exists():
            result.update({"activity": "CLEAR_ABSENT", "active_owner_detected": False})
            return result
        try:
            with path.open("r+b") as handle:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover - CI exercises the platform-specific branch
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            result.update(
                {
                    "activity": "ACTIVE_OR_UNPROBEABLE",
                    "active_owner_detected": True,
                    "probe_error": f"{type(exc).__name__}: {exc}",
                }
            )
        else:
            result.update({"activity": "CLEAR_STALE_FILE", "active_owner_detected": False})
        return result

    observed = [
        observe_lock(
            "runtime/swing_walk_forward_research.lock", name="Global Research Lock"
        ),
        observe_lock(
            "runtime/fx_forward_pit.collector.lock", name="FX PIT Observer"
        ),
    ]
    production_observed: list[dict[str, object]] = []
    protection_path = root / "config" / "swing_walk_forward_campaign.json"
    if protection_path.exists():
        try:
            protection = _read_json(protection_path, label="production protection config")
            for raw in protection.get("protected_runtime_locks") or []:
                item = dict(raw)
                configured = Path(str(item.get("path") or ""))
                if configured.is_absolute():
                    try:
                        relative = configured.resolve().relative_to(root).as_posix()
                    except ValueError:
                        production_observed.append(
                            {
                                "name": str(item.get("name") or "UNKNOWN"),
                                "path": str(configured),
                                "activity": "OUTSIDE_PROJECT_NOT_PROBED",
                                "active_owner_detected": None,
                                "probe_mutated_file": False,
                            }
                        )
                        continue
                else:
                    relative = configured.as_posix()
                production_observed.append(
                    observe_lock(relative, name=str(item.get("name") or "UNKNOWN"))
                )
        except DevelopmentV6PreflightError as exc:
            production_observed.append(
                {
                    "name": "Production protection config",
                    "path": _relative(root, protection_path),
                    "activity": "CONFIG_UNREADABLE",
                    "active_owner_detected": None,
                    "probe_error": str(exc),
                    "probe_mutated_file": False,
                }
            )
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "lock_files": observed,
        "production_lock_files": production_observed,
        "active_production_jobs_at_snapshot": [
            str(item["name"])
            for item in production_observed
            if item.get("active_owner_detected") is True
        ],
        "start_gate_blocking": False,
        "dispatch_rechecks_authoritatively": True,
    }


def _validate_local_gates(
    local_gate_results: Mapping[str, object],
    *,
    expected_commit: str,
) -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {}
    blockers: list[str] = []
    for name in REQUIRED_LOCAL_GATES:
        evidence = dict(local_gate_results.get(name) or {})
        checks[f"{name}_present"] = bool(evidence)
        checks[f"{name}_pass"] = evidence.get("status") == "PASS"
        checks[f"{name}_exit_zero"] = evidence.get("exit_code") == 0
        checks[f"{name}_command_recorded"] = bool(str(evidence.get("command") or "").strip())
        checks[f"{name}_evidence_recorded"] = bool(
            str(evidence.get("evidence") or "").strip()
        )
        checks[f"{name}_commit_bound"] = str(evidence.get("commit") or "") == expected_commit
        checks[f"{name}_completed_at_recorded"] = bool(
            str(evidence.get("completed_at") or "").strip()
        )
        checks[f"{name}_not_bypassed"] = evidence.get("skipped_by_preflight") is False
        if not all(value for key, value in checks.items() if key.startswith(name + "_")):
            blockers.append(f"LOCAL_GATE_INVALID:{name}")
    extras = sorted(set(local_gate_results) - set(REQUIRED_LOCAL_GATES))
    checks["no_required_gate_replaced_by_extra_name"] = not any(
        name not in local_gate_results for name in REQUIRED_LOCAL_GATES
    )
    if extras:
        # Extra diagnostics are retained, but cannot replace a required gate.
        checks["extra_local_evidence_is_non_authorizing"] = True
    return checks, blockers


def _validate_ci(
    ci_evidence: Mapping[str, object], *, expected_commit: str
) -> tuple[dict[str, bool], list[str], list[str]]:
    status = str(ci_evidence.get("status") or "")
    checks = {
        "allowed_status": status in {"SUCCESS", "REMOTE_UNAVAILABLE"},
        "commit_bound": str(ci_evidence.get("commit") or "") == expected_commit,
        "checked_at_recorded": bool(str(ci_evidence.get("checked_at") or "").strip()),
        "workflow_recorded": bool(str(ci_evidence.get("workflow") or "").strip()),
        "known_failure_absent": status != "FAIL",
    }
    warnings: list[str] = []
    if status == "SUCCESS":
        checks["success_evidence_reference_recorded"] = bool(
            str(ci_evidence.get("evidence") or "").strip()
        )
    elif status == "REMOTE_UNAVAILABLE":
        checks["remote_failure_reason_recorded"] = bool(
            str(ci_evidence.get("reason") or "").strip()
        )
        warnings.append("CI_REMOTE_UNAVAILABLE_LOCAL_GATES_USED_WITH_DISCLOSURE")
    else:
        checks["success_evidence_reference_recorded"] = False
    blockers = [f"CI_CHECK_FAILED:{key}" for key, passed in checks.items() if not passed]
    return checks, blockers, warnings


def _validate_scheduler(
    scheduler_evidence: Mapping[str, object],
    *, contract: Mapping[str, object],
) -> tuple[dict[str, bool], list[str]]:
    execution = dict(contract.get("development_execution") or {})
    expected_name = str(execution.get("scheduler_task_name") or "")
    expected_wrapper = str(execution.get("scheduler_wrapper") or "").replace("\\", "/")
    status = str(scheduler_evidence.get("status") or "")
    task_exists = scheduler_evidence.get("task_exists") is True
    common = {
        "installed_status_exact": status == "INSTALLED",
        "task_installed": task_exists,
        "task_enabled": scheduler_evidence.get("enabled") is True,
        "unique_v6_name": str(scheduler_evidence.get("task_name") or "")
        == expected_name
        and expected_name.endswith("-v6-Chain"),
        "exact_task_count": scheduler_evidence.get("task_count") == 1,
        "five_minute_repetition": scheduler_evidence.get(
            "repetition_interval_minutes"
        )
        == 5,
        "long_lived_repetition": isinstance(
            scheduler_evidence.get("repetition_duration_days"), int
        )
        and not isinstance(scheduler_evidence.get("repetition_duration_days"), bool)
        and int(scheduler_evidence.get("repetition_duration_days") or 0) >= 3650,
        "wrapper_matches": str(scheduler_evidence.get("wrapper") or "").replace(
            "\\", "/"
        )
        == expected_wrapper,
        "multiple_instances_ignore_new": str(
            scheduler_evidence.get("multiple_instances") or ""
        ).upper()
        == "IGNORENEW",
        "start_when_available": scheduler_evidence.get("start_when_available") is True,
        "wake_to_run": scheduler_evidence.get("wake_to_run") is True,
        "limited_run_level": str(scheduler_evidence.get("run_level") or "").upper()
        == "LIMITED",
        "interactive_user_context": str(
            scheduler_evidence.get("logon_type") or ""
        ).upper()
        == "INTERACTIVE",
        "user_context_recorded": bool(
            str(scheduler_evidence.get("user_context") or "").strip()
        ),
        "observed_at_recorded": bool(
            str(scheduler_evidence.get("observed_at") or "").strip()
        ),
    }
    blockers = [
        f"SCHEDULER_CHECK_FAILED:{key}" for key, passed in common.items() if not passed
    ]
    return common, blockers


def _validate_resources(
    resources: Mapping[str, object], *, selected_worker_count: int
) -> tuple[dict[str, bool], list[str]]:
    cpu = int(resources.get("logical_cpu_count") or 0)
    total_memory = int(resources.get("total_physical_memory_bytes") or 0)
    available_memory = int(
        resources.get("available_physical_memory_bytes_at_start") or 0
    )
    free = int(resources.get("disk_free_bytes") or 0)
    required_free = int(resources.get("required_free_before_start_bytes") or 0)
    eligible = tuple(eligible_worker_counts(resources))
    projection_paths = [dict(item) for item in resources.get("projection_store_paths") or []]
    v5_paths = [dict(item) for item in resources.get("v5_store_paths") or []]
    checks = {
        "logical_cpu_count_reported": cpu > 0,
        "total_memory_reported": total_memory > 0,
        "selected_workers_fit_cpu": selected_worker_count > 0
        and cpu >= selected_worker_count,
        "selected_workers_currently_eligible": selected_worker_count in eligible,
        "available_memory_at_least_2_gib": available_memory
        >= MINIMUM_AVAILABLE_MEMORY_BYTES,
        "raw_disk_free_at_least_30_gib": free >= MINIMUM_DISK_RESERVE_BYTES,
        "projection_stores_accounted": len(projection_paths) == 3
        and all(item.get("exists") is True and int(item.get("bytes") or 0) > 0 for item in projection_paths),
        "v5_stores_accounted_for_estimate": len(v5_paths) == 3
        and all(item.get("exists") is True and int(item.get("bytes") or 0) > 0 for item in v5_paths),
        "new_store_estimate_positive": int(
            resources.get("new_v6_store_estimate_bytes") or 0
        )
        > 0,
        "transient_reserve_at_least_4_gib": int(
            resources.get("wal_temporary_spool_reserve_bytes") or 0
        )
        >= MINIMUM_TRANSIENT_RESERVE_BYTES,
        "post_run_30_gib_reserve_protected": required_free
        >= MINIMUM_DISK_RESERVE_BYTES
        and free >= required_free,
    }
    blockers = [f"RESOURCE_CHECK_FAILED:{key}" for key, passed in checks.items() if not passed]
    return checks, blockers


def _run_absence(
    *, contract: Mapping[str, object], project_root: Path
) -> tuple[dict[str, object], dict[str, bool], list[str]]:
    stores = dict(contract.get("store_contract") or {})
    execution = dict(contract.get("development_execution") or {})
    fields = {
        "feature_store": stores.get("feature_store"),
        "outcome_store": stores.get("outcome_store"),
        "control_store": stores.get("control_store"),
        "run_manifest": execution.get("run_manifest"),
        "chain_state": execution.get("chain_state"),
        "final_audit": execution.get("final_audit_artifact"),
        "descriptive_report": execution.get("descriptive_report_artifact"),
        "completion_summary": execution.get("completion_summary_artifact"),
    }
    observed: dict[str, object] = {}
    checks: dict[str, bool] = {}
    blockers: list[str] = []
    for name, relative in fields.items():
        path = _resolve_project_path(project_root, relative, label=f"v6.{name}")
        exists = path.exists()
        observed[name] = {
            "path": _relative(project_root, path),
            "exists": exists,
            "bytes": _file_size(path),
        }
        checks[f"{name}_absent"] = not exists
        if exists:
            blockers.append(f"V6_RUN_ALREADY_EXISTS:{name}")
    return observed, checks, blockers


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    except FileExistsError:
        existing = _read_json(path, label="existing v6 start gate")
        if not _self_fingerprint_valid(existing) or canonical_json(existing) != canonical_json(payload):
            raise DevelopmentV6PreflightError(
                f"Immutable v6 start gate already exists with different content: {path}"
            )


def build_start_gate(
    *,
    contract_artifact_path: Path = DEFAULT_CONTRACT_ARTIFACT,
    contract_diff_path: Path = DEFAULT_CONTRACT_DIFF,
    local_gate_results: Mapping[str, object],
    ci_evidence: Mapping[str, object],
    scheduler_evidence: Mapping[str, object],
    config_path: Path = DEFAULT_V6_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
    input_precheck_path: Path | None = None,
    worker_benchmark_path: Path | None = None,
    descriptive_plan_path: Path | None = None,
    environment_snapshot: Mapping[str, object] | None = None,
    operational_observations: Mapping[str, object] | None = None,
    artifact_path: Path | None = None,
    created_at: str | None = None,
    persist: bool = True,
) -> dict[str, object]:
    """Build the final v6 start gate and persist it only when status is PASS.

    Failed evaluations are returned with blockers but never occupy the immutable
    canonical path.  This permits a real resource, Git, CI, or local-test issue
    to be fixed and evaluated again without weakening immutability.
    """

    project_root = Path(project_root).resolve()
    config = _read_json(Path(config_path), label="v6 config")
    contract_artifact = _read_json(Path(contract_artifact_path), label="v6 contract artifact")
    contract_diff = _read_json(Path(contract_diff_path), label="v6 contract diff")
    contract = dict(contract_artifact.get("contract") or {})
    references = dict(contract.get("reference_fingerprints") or {})
    execution = dict(contract.get("development_execution") or {})
    parent_spec = dict(config.get("parent_reprocessing") or {})
    parent_binding = dict(contract.get("reprocessing_parent") or {})

    contract_checks = {
        "artifact_self_valid": verify_development_v6_contract_artifact(contract_artifact),
        "artifact_version_exact": contract_artifact.get("version")
        == DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
        "contract_version_exact": contract.get("contract_version")
        == DEVELOPMENT_V6_CONTRACT_VERSION,
        "contract_self_valid": _contract_fingerprint_valid(contract),
        "artifact_contract_binding": contract_artifact.get("contract_fingerprint")
        == contract.get("contract_fingerprint"),
        "development_code_binding": contract_artifact.get(
            "development_code_fingerprint"
        )
        == references.get("development_code_fingerprint"),
        "full_run_authorized": contract_artifact.get("full_development_run_authorized")
        is True,
        "run_not_marked_started": contract_artifact.get("development_run_started")
        is False,
        "diff_self_valid": _self_fingerprint_valid(
            contract_diff, field="diff_fingerprint"
        ),
        "diff_version_exact": contract_diff.get("version")
        == DEVELOPMENT_V6_CONTRACT_DIFF_VERSION,
        "diff_status_pass": contract_diff.get("status") == "PASS",
        "diff_development_binding": contract_diff.get("development_fingerprint")
        == contract.get("contract_fingerprint"),
        "diff_parent_binding": contract_diff.get("parent_fingerprint")
        == parent_binding.get("contract_fingerprint"),
        "artifact_diff_binding": contract_artifact.get("parent_diff_fingerprint")
        == contract_diff.get("diff_fingerprint"),
        "zero_unauthorized_semantics": contract_diff.get(
            "unauthorized_research_semantics_count"
        )
        == 0
        and contract_artifact.get("unauthorized_research_semantics_count") == 0,
        "zero_research_semantics_diff": contract_diff.get(
            "research_semantics_diff_count"
        )
        == 0
        and contract_artifact.get("research_semantics_diff_count") == 0,
        "zero_semantic_invariant_failures": contract_diff.get(
            "semantic_invariant_failure_count"
        )
        == 0,
        "all_diff_rows_authorized": all(
            dict(item).get("authorized") is True
            for item in contract_diff.get("differences") or []
        ),
        "all_unseen_and_trading_paths_closed": all(
            contract_artifact.get(name) is False
            for name in (
                "validation_opened",
                "holdout_opened",
                "external_opened",
                "true_forward_opened",
                "paper_opened",
                "shadow_opened",
                "broker_opened",
            )
        ),
    }

    parent_artifact_path = _resolve_project_path(
        project_root, parent_spec.get("artifact_path"), label="v5 parent artifact"
    )
    parent_manifest_path = _resolve_project_path(
        project_root, parent_spec.get("run_manifest_path"), label="v5 parent manifest"
    )
    parent_artifact = _read_json(parent_artifact_path, label="v5 parent artifact")
    parent_manifest = _read_json(parent_manifest_path, label="v5 parent manifest")
    parent_contract = dict(parent_artifact.get("contract") or {})
    parent_checks = {
        "contract_parent_matches_config": canonical_json(parent_binding)
        == canonical_json(parent_spec),
        "artifact_sha256_unchanged": file_sha256(parent_artifact_path)
        == parent_spec.get("artifact_sha256"),
        "artifact_self_valid": _self_fingerprint_valid(parent_artifact),
        "artifact_version_exact": parent_artifact.get("version")
        == parent_spec.get("artifact_version"),
        "artifact_fingerprint_exact": parent_artifact.get("artifact_fingerprint")
        == parent_spec.get("artifact_fingerprint"),
        "parent_contract_self_valid": _contract_fingerprint_valid(parent_contract),
        "parent_contract_fingerprint_exact": parent_contract.get("contract_fingerprint")
        == parent_spec.get("contract_fingerprint"),
        "manifest_sha256_unchanged": file_sha256(parent_manifest_path)
        == parent_spec.get("run_manifest_sha256"),
        "manifest_self_valid": _self_fingerprint_valid(
            parent_manifest, field="run_manifest_fingerprint"
        ),
        "manifest_version_exact": parent_manifest.get("version")
        == parent_spec.get("run_manifest_version"),
        "manifest_fingerprint_exact": parent_manifest.get("run_manifest_fingerprint")
        == parent_spec.get("run_manifest_fingerprint"),
        "manifest_run_exact": parent_manifest.get("run_id") == parent_spec.get("run_id"),
        "manifest_contract_binding": parent_manifest.get(
            "development_contract_fingerprint"
        )
        == parent_spec.get("contract_fingerprint"),
    }

    runtime_specs = dict(config.get("required_runtime_artifacts") or {})
    artifact_runtime_inputs = dict(contract_artifact.get("runtime_input_artifacts") or {})

    def runtime_path(name: str, override: Path | None) -> Path:
        return (
            Path(override).resolve()
            if override is not None
            else _resolve_project_path(
                project_root,
                dict(runtime_specs.get(name) or {}).get("path"),
                label=f"{name} artifact",
            )
        )

    input_path = runtime_path("input_precheck", input_precheck_path)
    benchmark_path = runtime_path("worker_benchmark", worker_benchmark_path)
    plan_path = runtime_path("descriptive_plan", descriptive_plan_path)
    input_payload = _read_json(input_path, label="input precheck")
    benchmark = _read_json(benchmark_path, label="worker benchmark")
    plan = _read_json(plan_path, label="descriptive plan")
    raw_worker_input_precheck = benchmark.get("worker_input_precheck_artifact")
    worker_input_precheck = (
        dict(raw_worker_input_precheck)
        if isinstance(raw_worker_input_precheck, Mapping)
        else {}
    )
    benchmark_created_at = _aware_artifact_timestamp(benchmark.get("created_at"))
    plan_created_at = _aware_artifact_timestamp(plan.get("created_at"))
    input_source_audit, input_source_checks = _audit_current_input_sources(
        input_path=input_path,
        input_precheck=input_payload,
        project_root=project_root,
    )
    implementation_audit, implementation_checks = _audit_implementation_code(
        input_precheck=input_payload,
        contract=contract,
        contract_artifact=contract_artifact,
        project_root=project_root,
    )
    expected_plan_contract_basis = fingerprint(
        build_development_v6_benchmark_contract(
            config_path=Path(config_path),
            project_root=project_root,
            input_precheck_path=input_path,
        )
    )
    inputs = dict(input_payload.get("contract_inputs") or {})
    selected_workers = int(benchmark.get("selected_worker_count") or 0)
    benchmark_configurations = [
        dict(item) for item in benchmark.get("configurations") or []
        if isinstance(item, Mapping)
    ]
    benchmark_worker_counts = [
        item.get("worker_count")
        if isinstance(item.get("worker_count"), int)
        and not isinstance(item.get("worker_count"), bool)
        else 0
        for item in benchmark_configurations
    ]
    expected_benchmark_worker_counts = list(
        eligible_worker_counts(dict(benchmark.get("resources") or {}))
    )
    recomputed_configuration_checks = {
        str(item.get("worker_count")): configuration_evidence_checks(item)
        for item in benchmark_configurations
    }
    benchmark_classification = classify_worker_configurations(
        benchmark_configurations
    )
    recomputed_configuration_decisions = dict(
        benchmark_classification.get("configuration_decisions") or {}
    )
    stored_configuration_decisions = dict(
        benchmark.get("configuration_decisions") or {}
    )
    selected_decision = dict(
        recomputed_configuration_decisions.get(str(selected_workers)) or {}
    )
    reference_decision = dict(recomputed_configuration_decisions.get("1") or {})
    stored_configuration_checks = {
        str(label): {
            str(name): value
            for name, value in dict(checks).items()
        }
        for label, checks in dict(
            benchmark.get("configuration_evidence_checks") or {}
        ).items()
        if isinstance(checks, Mapping)
    }
    raw_runtime_checks = benchmark.get(
        "protected_runtime_checks_before_each_configuration"
    )
    runtime_checks = (
        [dict(item) for item in raw_runtime_checks if isinstance(item, Mapping)]
        if isinstance(raw_runtime_checks, list)
        else []
    )
    runtime_check_worker_counts = [
        item.get("worker_count") for item in runtime_checks
    ]
    runtime_check_worker_counts_well_formed = all(
        isinstance(item, int) and not isinstance(item, bool)
        for item in runtime_check_worker_counts
    )
    recomputed_all_configuration_evidence_complete = bool(
        recomputed_configuration_checks
    ) and all(
        checks and all(value is True for value in checks.values())
        for checks in recomputed_configuration_checks.values()
    )
    excluded_multi = list(
        benchmark_classification.get("excluded_multi_worker_configurations") or []
    )
    reference_digest = str(
        benchmark_classification.get("reference_scientific_digest") or ""
    )
    recomputed_all_tested_equal = bool(reference_digest) and all(
        str(item.get("scientific_digest") or "") == reference_digest
        for item in benchmark_configurations
    )
    fallback_expected = selected_workers == 1
    input_checks = {
        "self_valid": _self_fingerprint_valid(input_payload),
        "version_exact": input_payload.get("version")
        == dict(runtime_specs.get("input_precheck") or {}).get("version"),
        "status_pass": input_payload.get("status") == "PASS",
        "all_internal_checks_pass": bool(input_payload.get("checks"))
        and all(value is True for value in dict(input_payload.get("checks") or {}).values()),
        "contract_reference_binding": input_payload.get("artifact_fingerprint")
        == references.get("input_precheck_artifact_fingerprint"),
        "combined_input_binding": inputs.get("combined_input_fingerprint")
        == references.get("combined_input_fingerprint"),
        "artifact_runtime_binding": canonical_json(
            dict(artifact_runtime_inputs.get("input_precheck") or {})
        )
        == canonical_json(
            {
                "path": dict(runtime_specs.get("input_precheck") or {}).get("path"),
                "version": input_payload.get("version"),
                "status": input_payload.get("status"),
                "artifact_fingerprint": input_payload.get("artifact_fingerprint"),
            }
        ),
        "contract_execution_path_binding": execution.get(
            "input_precheck_artifact"
        )
        == dict(runtime_specs.get("input_precheck") or {}).get("path"),
        "source_hashes_stable": input_payload.get("source_sha256_before")
        == input_payload.get("source_sha256_after"),
        **input_source_checks,
        "no_download_or_data_repair": input_payload.get("no_downloads") is True
        and input_payload.get("no_clipping") is True
        and input_payload.get("no_imputation") is True
        and input_payload.get("no_interpolation") is True,
        "run_not_started": input_payload.get("development_run_started") is False,
        **{
            f"code_{name}": passed
            for name, passed in implementation_checks.items()
        },
    }
    benchmark_checks = {
        "self_valid": _self_fingerprint_valid(benchmark),
        "version_exact": benchmark.get("version")
        == dict(runtime_specs.get("worker_benchmark") or {}).get("version"),
        "status_pass": benchmark.get("status") == "PASS",
        "contract_reference_binding": benchmark.get("artifact_fingerprint")
        == references.get("worker_benchmark_artifact_fingerprint"),
        "input_precheck_binding": benchmark.get("input_precheck_fingerprint")
        == input_payload.get("artifact_fingerprint"),
        "worker_input_precheck_fingerprint_binding": worker_input_precheck.get(
            "artifact_fingerprint"
        )
        == input_payload.get("artifact_fingerprint"),
        "worker_input_precheck_path_binding": worker_input_precheck.get("path")
        == dict(runtime_specs.get("input_precheck") or {}).get("path"),
        "combined_input_binding": benchmark.get("combined_input_fingerprint")
        == inputs.get("combined_input_fingerprint"),
        "parent_contract_binding": benchmark.get(
            "scientific_parent_contract_fingerprint"
        )
        == parent_spec.get("contract_fingerprint"),
        "descriptive_plan_artifact_binding": benchmark.get(
            "descriptive_plan_artifact_fingerprint"
        )
        == plan.get("artifact_fingerprint"),
        "descriptive_plan_timestamp_binding": benchmark.get(
            "descriptive_plan_created_at"
        )
        == plan.get("created_at"),
        "descriptive_plan_frozen_before_benchmark": plan_created_at is not None
        and benchmark_created_at is not None
        and plan_created_at <= benchmark_created_at,
        "benchmark_completed": benchmark.get("benchmark_completed") is True,
        "configuration_worker_counts_unique": len(benchmark_worker_counts)
        == len(set(benchmark_worker_counts)),
        "configuration_worker_counts_exact": sorted(benchmark_worker_counts)
        == sorted(expected_benchmark_worker_counts),
        "configuration_evidence_artifact_binding": canonical_json(
            stored_configuration_checks
        )
        == canonical_json(recomputed_configuration_checks),
        "all_configuration_evidence_complete_honest": benchmark.get(
            "all_configuration_evidence_complete"
        )
        is recomputed_all_configuration_evidence_complete,
        "configuration_decisions_artifact_binding": canonical_json(
            stored_configuration_decisions
        )
        == canonical_json(recomputed_configuration_decisions),
        "reference_worker_exact": benchmark.get("reference_worker_count") == 1
        and benchmark.get("reference_configuration_count") == 1,
        "reference_configuration_pass": benchmark.get(
            "reference_configuration_passed"
        )
        is True
        and reference_decision.get("eligible_for_selection") is True,
        "reference_digest_binding": benchmark.get("reference_scientific_digest")
        == benchmark_classification.get("reference_scientific_digest"),
        "selection_candidates_artifact_binding": benchmark.get(
            "selection_candidate_worker_counts"
        )
        == benchmark_classification.get("selection_candidate_worker_counts"),
        "selection_candidates_identical_to_reference": benchmark.get(
            "all_selection_candidates_identical_to_reference"
        )
        is True,
        "all_tested_digest_equality_honestly_disclosed": benchmark.get(
            "all_tested_payloads_equal_to_reference"
        )
        is recomputed_all_tested_equal
        and benchmark.get("deterministic_payloads_equal")
        is recomputed_all_tested_equal,
        "excluded_multi_configurations_disclosed": canonical_json(
            benchmark.get("excluded_multi_worker_configurations") or []
        )
        == canonical_json(excluded_multi),
        "technical_gate_schema_exact": bool(benchmark_configurations)
        and all(
            isinstance(item.get("technical_coverage_gates"), Mapping)
            and set(dict(item.get("technical_coverage_gates") or {}))
            == set(REQUIRED_TECHNICAL_COVERAGE_GATES)
            for item in benchmark_configurations
        ),
        "reference_and_selected_digests_equal": len(
            str(benchmark_classification.get("reference_scientific_digest") or "")
        )
        == 64
        and selected_decision.get("digest_matches_one_worker_reference") is True
        and benchmark.get("selected_digest_matches_one_worker_reference") is True,
        "selected_worker_bound_to_contract": selected_workers > 0
        and selected_workers == int(execution.get("worker_count") or 0),
        "selected_worker_is_passing_configuration": any(
            item.get("worker_count") == selected_workers
            and item.get("status") == "PASS"
            for item in benchmark_configurations
        )
        and selected_decision.get("eligible_for_selection") is True,
        "fallback_disclosure_consistent": benchmark.get(
            "fallback_to_one_worker"
        )
        is fallback_expected
        and (
            not fallback_expected
            or bool(benchmark.get("fallback_reasons"))
        ),
        "multi_worker_failure_not_hidden": benchmark.get(
            "multi_worker_instability_is_not_a_start_blocker"
        )
        is True,
        "single_sqlite_writer": benchmark.get("sqlite_writer_count") == 1
        and execution.get("sqlite_writer_count") == 1,
        "selection_did_not_use_outcomes": benchmark.get("selection_used_outcomes")
        is False,
        "exclusive_benchmark_process_lock_held": benchmark.get(
            "exclusive_benchmark_process_lock_held"
        )
        is True,
        "global_research_lock_held": benchmark.get("global_research_lock_held")
        is True,
        "protected_runtime_checked_before_every_configuration": isinstance(
            raw_runtime_checks, list
        )
        and len(runtime_checks) == len(raw_runtime_checks)
        and runtime_check_worker_counts_well_formed
        and sorted(int(item) for item in runtime_check_worker_counts)
        == sorted(expected_benchmark_worker_counts)
        and all(
            item.get("status") == "PASS" and item.get("reason") == "CLEAR"
            for item in runtime_checks
        ),
        "artifact_runtime_binding": canonical_json(
            dict(artifact_runtime_inputs.get("worker_benchmark") or {})
        )
        == canonical_json(
            {
                "path": dict(runtime_specs.get("worker_benchmark") or {}).get("path"),
                "version": benchmark.get("version"),
                "status": benchmark.get("status"),
                "artifact_fingerprint": benchmark.get("artifact_fingerprint"),
            }
        ),
        "contract_execution_path_binding": execution.get(
            "worker_benchmark_artifact"
        )
        == dict(runtime_specs.get("worker_benchmark") or {}).get("path"),
    }
    plan_checks = {
        "self_valid": _self_fingerprint_valid(plan),
        "version_exact": plan.get("version")
        == dict(runtime_specs.get("descriptive_plan") or {}).get("version"),
        "status_frozen": plan.get("status") == "FROZEN",
        "contract_reference_binding": plan.get("artifact_fingerprint")
        == references.get("descriptive_plan_artifact_fingerprint"),
        "combined_input_binding": plan.get("combined_input_fingerprint")
        == inputs.get("combined_input_fingerprint"),
        "inferential_claims_closed": plan.get("inferential_claims_allowed") is False,
        "selection_and_optimization_closed": plan.get(
            "selection_or_optimization_allowed"
        )
        is False,
        "created_at_timezone_aware": plan_created_at is not None,
        "frozen_before_worker_benchmark": plan_created_at is not None
        and benchmark_created_at is not None
        and plan_created_at <= benchmark_created_at,
        "worker_benchmark_fingerprint_binding": benchmark.get(
            "descriptive_plan_artifact_fingerprint"
        )
        == plan.get("artifact_fingerprint"),
        "contract_basis_exact": plan.get("contract_basis_fingerprint")
        == expected_plan_contract_basis,
        "artifact_runtime_binding": canonical_json(
            dict(artifact_runtime_inputs.get("descriptive_plan") or {})
        )
        == canonical_json(
            {
                "path": dict(runtime_specs.get("descriptive_plan") or {}).get("path"),
                "version": plan.get("version"),
                "status": plan.get("status"),
                "artifact_fingerprint": plan.get("artifact_fingerprint"),
            }
        ),
        "contract_execution_path_binding": execution.get(
            "descriptive_plan_artifact"
        )
        == dict(runtime_specs.get("descriptive_plan") or {}).get("path"),
    }

    environment = (
        dict(environment_snapshot)
        if environment_snapshot is not None
        else capture_environment_snapshot(
            contract=contract, parent_contract=parent_contract, project_root=project_root
        )
    )
    resources = dict(environment.get("resources") or {})
    python_snapshot = dict(environment.get("python") or {})
    git_snapshot = dict(environment.get("git") or {})
    resource_checks, resource_blockers = _validate_resources(
        resources, selected_worker_count=selected_workers
    )
    resource_checks["environment_snapshot_timestamp_recorded"] = bool(
        str(environment.get("captured_at") or "").strip()
    )
    python_checks = {
        "project_venv_exists": python_snapshot.get("project_venv_exists") is True,
        "running_from_project_venv": python_snapshot.get("running_from_project_venv")
        is True,
        "supported_python_version": python_snapshot.get("supported_version") is True,
        "python_paths_recorded": bool(python_snapshot.get("running_executable"))
        and bool(python_snapshot.get("project_venv_executable")),
        "python_version_recorded": bool(python_snapshot.get("version")),
    }
    expected_git = dict(contract_artifact.get("git") or {})
    git_checks = {
        "branch_matches_frozen_contract": git_snapshot.get("branch")
        == expected_git.get("branch"),
        "head_matches_frozen_contract": git_snapshot.get("head")
        == expected_git.get("commit"),
        "tracked_worktree_clean": git_snapshot.get("tracked_worktree_clean") is True,
        "no_git_probe_errors": not dict(git_snapshot.get("errors") or {}),
        "upstream_configured": bool(git_snapshot.get("upstream")),
        "exactly_pushed_no_ahead_or_behind": git_snapshot.get("ahead") == 0
        and git_snapshot.get("behind") == 0,
    }
    local_checks, local_blockers = _validate_local_gates(
        local_gate_results,
        expected_commit=str(expected_git.get("commit") or ""),
    )
    ci_checks, ci_blockers, ci_warnings = _validate_ci(
        ci_evidence, expected_commit=str(expected_git.get("commit") or "")
    )
    scheduler_checks, scheduler_blockers = _validate_scheduler(
        scheduler_evidence, contract=contract
    )
    absence_observed, absence_checks, absence_blockers = _run_absence(
        contract=contract, project_root=project_root
    )

    groups: dict[str, dict[str, bool]] = {
        "CONTRACT_AND_DIFF": contract_checks,
        "IMMUTABLE_V5_PARENT": parent_checks,
        "INPUT_BINDING": input_checks,
        "WORKER_BENCHMARK_BINDING": benchmark_checks,
        "DESCRIPTIVE_PLAN_BINDING": plan_checks,
        "RESOURCES": resource_checks,
        "PYTHON_ENVIRONMENT": python_checks,
        "GIT_PROVENANCE": git_checks,
        "LOCAL_VERIFICATION": local_checks,
        "CI_VERIFICATION": ci_checks,
        "SCHEDULER_CONTRACT": scheduler_checks,
        "RUN_ABSENT": absence_checks,
    }
    gates = {
        name: "PASS" if checks and all(checks.values()) else "FAIL"
        for name, checks in groups.items()
    }
    blockers = [
        f"{group}:{name}"
        for group, checks in groups.items()
        for name, passed in checks.items()
        if not passed
    ]
    blockers.extend(resource_blockers)
    blockers.extend(local_blockers)
    blockers.extend(ci_blockers)
    blockers.extend(scheduler_blockers)
    blockers.extend(absence_blockers)
    blockers = sorted(set(blockers))
    status = "PASS" if all(gates.get(name) == "PASS" for name in TOP_LEVEL_GATES) else "FAIL"
    warnings = sorted(set(ci_warnings))
    observations = (
        dict(operational_observations)
        if operational_observations is not None
        else capture_operational_observations(project_root=project_root)
    )
    output_path = (
        Path(artifact_path).resolve()
        if artifact_path is not None
        else _resolve_project_path(
            project_root, execution.get("readiness_artifact"), label="v6 start gate"
        )
    )
    payload: dict[str, object] = {
        "version": START_GATE_VERSION,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "status": status,
        "start_authorized": status == "PASS",
        "development_contract_version": contract.get("contract_version"),
        "development_contract_fingerprint": contract.get("contract_fingerprint"),
        "contract_artifact_fingerprint": contract_artifact.get("artifact_fingerprint"),
        "contract_diff_fingerprint": contract_diff.get("diff_fingerprint"),
        "v5_parent_contract_fingerprint": parent_spec.get("contract_fingerprint"),
        "input_precheck_artifact_fingerprint": input_payload.get("artifact_fingerprint"),
        "input_source_audit": input_source_audit,
        "implementation_code_audit": implementation_audit,
        "worker_benchmark_artifact_fingerprint": benchmark.get("artifact_fingerprint"),
        "descriptive_plan_artifact_fingerprint": plan.get("artifact_fingerprint"),
        "selected_worker_count": selected_workers,
        "sqlite_writer_count": execution.get("sqlite_writer_count"),
        "gates": gates,
        "checks": groups,
        "blockers": blockers,
        "warnings": warnings,
        "resources": resources,
        "python_environment": python_snapshot,
        "git_provenance": git_snapshot,
        "local_gate_results": dict(local_gate_results),
        "ci_evidence": dict(ci_evidence),
        "scheduler_evidence": dict(scheduler_evidence),
        "operational_observations": observations,
        "operational_observations_are_non_authoritative": True,
        "production_and_fx_locks_rechecked_before_every_dispatch": True,
        "run_absence": absence_observed,
        "canonical_artifact_path": _relative(project_root, output_path),
        "failed_report_persisted_to_canonical_path": False,
        "development_run_started": False,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    if persist and status == "PASS":
        _write_immutable(output_path, payload)
    return payload


__all__ = [
    "DEFAULT_CONTRACT_ARTIFACT",
    "DEFAULT_CONTRACT_DIFF",
    "DevelopmentV6PreflightError",
    "MINIMUM_AVAILABLE_MEMORY_BYTES",
    "MINIMUM_DISK_RESERVE_BYTES",
    "PROJECT_ROOT",
    "REQUIRED_LOCAL_GATES",
    "START_GATE_VERSION",
    "TOP_LEVEL_GATES",
    "build_start_gate",
    "capture_environment_snapshot",
    "capture_operational_observations",
]
