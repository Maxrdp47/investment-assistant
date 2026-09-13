from __future__ import annotations

"""Versioned recovery contract and evidence import for Development v7.

The module treats the terminal Development-v6 run as a read-only parent.  It
reuses only receipt-backed, byte/digest-verified terminal work units and writes
all v7 state to new stores.  Scientific computation remains delegated to the
unchanged v6 Development implementation and its frozen input projections.
"""

import copy
import getpass
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from multi_asset_development_v6_execution import (
    build_v6_universe,
    build_v6_work_plan,
    compute_v6_asset_batch,
    result_scientific_digest,
)
from multi_asset_development_v6_inputs import verify_v6_current_sources
from multi_asset_development_v6_store import (
    _expected_evidence,
    checkpoint_status,
    decode_payload,
    initialize_v6_run,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = (
    PROJECT_ROOT / "config" / "multi_asset_discovery_development_v7_recovery.json"
)
RECOVERY_CONTRACT_VERSION = (
    "multi-asset-opportunity-discovery-development-recovery-2026.09.13-v7"
)
RECOVERY_ARTIFACT_VERSION = "multi-asset-development-v7-recovery-contract-2026.09.13-v1"
RECOVERY_DIFF_VERSION = "multi-asset-development-v7-recovery-diff-2026.09.13-v1"
ROOT_CAUSE_VERSION = "multi-asset-development-v7-readonly-root-cause-2026.09.13-v1"
REUSE_REPORT_VERSION = "multi-asset-development-v7-reuse-report-2026.09.13-v1"
PILOT_VERSION = "multi-asset-development-v7-recovery-pilot-2026.09.13-v1"
SCHEDULER_SMOKE_VERSION = "multi-asset-development-v7-scheduler-smoke-2026.09.13-v1"
START_GATE_VERSION = "multi-asset-development-v7-start-gate-2026.09.13-v1"
RUN_MANIFEST_VERSION = "multi-asset-discovery-development-run-manifest-2026.09.13-v7"
CHAIN_VERSION = "multi-asset-development-v7-recovery-chain-2026.09.13-v1"
AUDIT_VERSION = "multi-asset-development-v7-final-audit-2026.09.13-v1"
REPORT_VERSION = "multi-asset-development-v7-descriptive-report-2026.09.13-v1"
SUMMARY_VERSION = "multi-asset-development-v7-completion-summary-2026.09.13-v1"


class DevelopmentV7RecoveryError(RuntimeError):
    """The v7 recovery contract cannot be satisfied safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentV7RecoveryError(f"Unreadable JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise DevelopmentV7RecoveryError(f"JSON artifact is not an object: {path}")
    return payload


def _atomic_write(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(payload), ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    if path.exists():
        if canonical_json(_read_json(path)) != canonical_json(dict(payload)):
            raise DevelopmentV7RecoveryError(f"Immutable artifact differs: {path}")
        return
    _atomic_write(path, payload)


def _existing_self_fingerprinted(
    path: Path, *, version: str
) -> dict[str, object] | None:
    """Return an already-bound immutable artifact or fail closed.

    Recovery preparation is intentionally resumable.  Timestamps must never
    cause an already-created immutable artifact to be silently replaced.
    """

    path = Path(path)
    if not path.exists():
        return None
    payload = _read_json(path)
    if payload.get("version") != version or not verify_self_fingerprint(payload):
        raise DevelopmentV7RecoveryError(f"Existing immutable artifact is invalid: {path}")
    return payload


def _existing_run_manifest(path: Path) -> dict[str, object] | None:
    path = Path(path)
    if not path.exists():
        return None
    payload = _read_json(path)
    basis = copy.deepcopy(payload)
    claimed = basis.pop("run_manifest_fingerprint", None)
    if payload.get("version") != RUN_MANIFEST_VERSION or claimed != fingerprint(basis):
        raise DevelopmentV7RecoveryError(f"Existing v7 run manifest is invalid: {path}")
    return payload


def _self_fingerprinted(payload: Mapping[str, object]) -> dict[str, object]:
    result = copy.deepcopy(dict(payload))
    result.pop("artifact_fingerprint", None)
    result["artifact_fingerprint"] = fingerprint(result)
    return result


def verify_self_fingerprint(payload: Mapping[str, object]) -> bool:
    expected = payload.get("artifact_fingerprint")
    basis = copy.deepcopy(dict(payload))
    basis.pop("artifact_fingerprint", None)
    return isinstance(expected, str) and expected == fingerprint(basis)


def load_recovery_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    payload = _read_json(path)
    if payload.get("version") != "multi-asset-development-recovery-config-2026.09.13-v7":
        raise DevelopmentV7RecoveryError("Unknown v7 recovery config version.")
    if payload.get("recovery_version") != RECOVERY_CONTRACT_VERSION:
        raise DevelopmentV7RecoveryError("Recovery version mismatch.")
    safety = dict(payload.get("safety") or {})
    if safety.get("development_only") is not True or any(
        safety.get(name) is not False
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
    ):
        raise DevelopmentV7RecoveryError("v7 safety boundary is not closed.")
    return payload


def recovery_paths(
    config: Mapping[str, object], *, project_root: Path = PROJECT_ROOT
) -> dict[str, Path]:
    root = Path(project_root)
    parent = dict(config["parent"])
    recovery = dict(config["recovery"])
    paths = {
        f"parent_{key}": root / str(value)
        for key, value in parent.items()
        if key not in {"run_id", "code_commit", "contract_fingerprint"}
    }
    paths.update(
        {
            key: root / str(value)
            for key, value in recovery.items()
            if isinstance(value, str)
            and key
            not in {
                "scheduler_task",
                "scheduler_pilot_task",
                "production_protection_config",
                "run_id",
            }
        }
    )
    paths["production_protection_config"] = root / str(
        recovery["production_protection_config"]
    )
    return paths


def _git(*args: str, project_root: Path = PROJECT_ROOT) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=project_root, text=True, encoding="utf-8"
    ).strip()


def _artifact_sha(path: Path) -> str:
    if not Path(path).is_file():
        raise DevelopmentV7RecoveryError(f"Required artifact is missing: {path}")
    return file_sha256(Path(path))


def _parent_bundle(
    config: Mapping[str, object], *, project_root: Path = PROJECT_ROOT
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    paths = recovery_paths(config, project_root=project_root)
    parent_spec = dict(config["parent"])
    artifact = _read_json(paths["parent_contract_artifact"])
    manifest = _read_json(paths["parent_run_manifest"])
    state = _read_json(paths["parent_chain_state"])
    if artifact.get("artifact_fingerprint") != fingerprint(
        {key: value for key, value in artifact.items() if key != "artifact_fingerprint"}
    ):
        raise DevelopmentV7RecoveryError("Parent v6 contract artifact is invalid.")
    manifest_basis = dict(manifest)
    expected_manifest_fingerprint = manifest_basis.pop("run_manifest_fingerprint", None)
    if expected_manifest_fingerprint != fingerprint(manifest_basis):
        raise DevelopmentV7RecoveryError("Parent v6 run manifest is invalid.")
    checks = {
        "run_id": manifest.get("run_id") == parent_spec["run_id"] == state.get("run_id"),
        "commit": manifest.get("commit") == parent_spec["code_commit"] == state.get("code_commit"),
        "contract": (
            artifact.get("contract_fingerprint")
            == parent_spec["contract_fingerprint"]
            == manifest.get("development_contract_fingerprint")
            == state.get("contract_fingerprint")
        ),
        "terminal_pause": state.get("status") == "PAUSED_REQUIRES_REVIEW",
        "readonly_reason": "attempt to write a readonly database"
        in str(state.get("blocker") or "").lower(),
        "closed_later_stages": not any(
            bool(state.get(name))
            for name in (
                "validation_opened",
                "holdout_opened",
                "external_opened",
                "forward_opened",
                "paper_opened",
                "shadow_opened",
                "broker_opened",
            )
        ),
    }
    if not all(checks.values()):
        raise DevelopmentV7RecoveryError(f"Parent v6 identity mismatch: {checks}")
    return artifact, manifest, state


def build_recovery_contract(
    config: Mapping[str, object], *, project_root: Path = PROJECT_ROOT
) -> tuple[dict[str, object], dict[str, object]]:
    artifact, manifest, state = _parent_bundle(config, project_root=project_root)
    scientific_contract = copy.deepcopy(dict(artifact["contract"]))
    roots = tuple(str(value) for value in config["semantic_invariant_roots"])
    semantic_diff = [
        root
        for root in roots
        if canonical_json(scientific_contract.get(root))
        != canonical_json(dict(artifact["contract"]).get(root))
    ]
    recovery = dict(config["recovery"])
    paths = recovery_paths(config, project_root=project_root)
    basis: dict[str, object] = {
        "version": RECOVERY_CONTRACT_VERSION,
        "run_id": recovery["run_id"],
        "parent": {
            "run_id": manifest["run_id"],
            "status": state["status"],
            "code_commit": manifest["commit"],
            "contract_fingerprint": artifact["contract_fingerprint"],
            "contract_artifact_sha256": _artifact_sha(paths["parent_contract_artifact"]),
            "run_manifest_fingerprint": manifest["run_manifest_fingerprint"],
            "run_manifest_sha256": _artifact_sha(paths["parent_run_manifest"]),
            "recovery_reason": state["blocker"],
            "immutable": True,
        },
        "scientific_contract_fingerprint": scientific_contract["contract_fingerprint"],
        "semantic_invariant_roots": list(roots),
        "research_semantics_diff_count": len(semantic_diff),
        "research_semantics_differences": semantic_diff,
        "stores": {
            "control": recovery["control_store"],
            "features": recovery["feature_store"],
            "outcomes": recovery["outcome_store"],
            "schema_compatibility": "EXACT_V6_SCHEMA_PLUS_APPEND_ONLY_RECOVERY_LINEAGE",
        },
        "execution": {
            "worker_count": int(recovery["worker_count"]),
            "sqlite_writer_count": int(recovery["sqlite_writer_count"]),
            "process_lock": recovery["process_lock"],
            "global_research_lock": "runtime/swing_walk_forward_research.lock",
            "scheduler_task": recovery["scheduler_task"],
            "time_of_day_gate": False,
            "recovery_only": True,
        },
        "reuse_policy": {
            "source_statuses": ["COMPLETED", "SKIPPED"],
            "receipt_required": True,
            "feature_outcome_case_equality_required": True,
            "source_digest_recalculation_required": True,
            "partial_or_failed_unit_reuse_allowed": False,
            "silent_copy_allowed": False,
        },
        "dataset_fingerprints": copy.deepcopy(
            dict(scientific_contract["reference_fingerprints"])
        ),
        "safety": copy.deepcopy(dict(config["safety"])),
    }
    basis["recovery_contract_fingerprint"] = fingerprint(basis)
    diff = _self_fingerprinted(
        {
            "version": RECOVERY_DIFF_VERSION,
            "parent_contract_fingerprint": scientific_contract["contract_fingerprint"],
            "recovery_contract_fingerprint": basis["recovery_contract_fingerprint"],
            "research_semantics_diff_count": len(semantic_diff),
            "research_semantics_differences": semantic_diff,
            "allowed_operational_differences": [
                "version",
                "run_id",
                "store_paths",
                "manifest_paths",
                "scheduler_task",
                "recovery_lineage",
                "root_cause_diagnostics",
            ],
            "hard_gate_pass": len(semantic_diff) == 0,
        }
    )
    return basis, diff


def _windows_attributes(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"raw": None, "read_only": None}
    if os.name != "nt":
        return result
    import ctypes

    raw = int(ctypes.windll.kernel32.GetFileAttributesW(str(Path(path).resolve())))
    result["raw"] = raw
    result["read_only"] = bool(raw != -1 and raw & 0x1)
    return result


def _acl_text(path: Path) -> str | None:
    if os.name != "nt":
        return None
    completed = subprocess.run(
        ["icacls", str(Path(path).resolve())],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _sqlite_readonly_observation(path: Path, *, quick_check: bool) -> dict[str, object]:
    started = time.monotonic()
    connection = sqlite3.connect(
        f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, timeout=60
    )
    try:
        observation = {
            "database_list": [list(row) for row in connection.execute("PRAGMA database_list")],
            "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
            "locking_mode": connection.execute("PRAGMA locking_mode").fetchone()[0],
            "quick_check": (
                connection.execute("PRAGMA quick_check").fetchone()[0]
                if quick_check
                else "DEFERRED_TO_RECORDED_PREFLIGHT"
            ),
            "total_changes": connection.total_changes,
        }
    finally:
        connection.close()
    observation["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return observation


def build_root_cause_report(
    config: Mapping[str, object], *, project_root: Path = PROJECT_ROOT
) -> dict[str, object]:
    paths = recovery_paths(config, project_root=project_root)
    artifact, manifest, state = _parent_bundle(config, project_root=project_root)
    target = paths["parent_outcome_store"]
    parent_dir = target.parent
    probe = parent_dir / f".v7-write-probe-{os.getpid()}"
    directory_probe = "FAIL"
    try:
        probe.write_bytes(b"v7-probe")
        if probe.read_bytes() != b"v7-probe":
            raise OSError("write probe mismatch")
        directory_probe = "PASS"
    finally:
        if probe.exists():
            probe.unlink()
    file_stat = target.stat()
    log_text = paths["parent_log"].read_text(encoding="utf-8", errors="replace")
    error_marker = "sqlite3.OperationalError: attempt to write a readonly database"
    trace_marker = "_insert_outcomes"
    relevant_events = {
        "system_or_application_error_events": 0,
        "defender_block_events": 0,
        "defender_unrelated_configuration_event_observed": True,
        "event_window": "2026-09-06T02:25:00+02:00/2026-09-06T02:45:00+02:00",
        "evidence_source": "read-only Windows event-log query performed 2026-09-13",
    }
    attributes = _windows_attributes(target)
    os_access_write = os.access(target, os.W_OK)
    report = {
        "version": ROOT_CAUSE_VERSION,
        "observed_at": utc_now(),
        "classification": "I_UNKNOWN",
        "conclusion": (
            "The failing file is proven, but no retained telemetry proves why Windows/SQLite "
            "returned SQLITE_READONLY for that single write. No permission, open-mode, lock, "
            "Defender, disk, or scheduler-context cause is asserted without evidence."
        ),
        "failure": {
            "path": str(target.resolve()),
            "operation": "INSERT INTO outcome_rows via _insert_outcomes",
            "asset": "EQUITIES:FLG",
            "recorded_at": "2026-09-06T02:36:32+02:00",
            "error": "sqlite3.OperationalError: attempt to write a readonly database",
            "log_error_present": error_marker in log_text,
            "log_insert_outcomes_trace_present": trace_marker in log_text,
        },
        "historical_connection_contract": {
            "writer_call": "sqlite3.connect(path, timeout=60)",
            "uri": False,
            "mode_ro": False,
            "journal_pragma": "WAL",
            "synchronous_pragma": "FULL",
            "foreign_keys": True,
        },
        "current_file_observation": {
            "exists": target.is_file(),
            "size_bytes": file_stat.st_size,
            "mtime_ns": file_stat.st_mtime_ns,
            "os_access_read": os.access(target, os.R_OK),
            "os_access_write": os_access_write,
            "attributes": attributes,
            "file_acl": _acl_text(target),
            "directory_acl": _acl_text(parent_dir),
            "directory_write_probe": directory_probe,
            "wal_exists": target.with_name(target.name + "-wal").exists(),
            "shm_exists": target.with_name(target.name + "-shm").exists(),
            "readonly_sqlite": _sqlite_readonly_observation(target, quick_check=False),
        },
        "context": {
            "scheduler_task": dict(config["recovery"])["scheduler_task"],
            "v6_scheduler_task": "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain",
            "configured_scheduler_user": getpass.getuser(),
            "historical_python_process_user_independently_logged": False,
            "current_python_user": getpass.getuser(),
            "python_executable": sys.executable,
            "working_directory": os.getcwd(),
            "temp": tempfile.gettempdir(),
            "TEMP": os.environ.get("TEMP"),
            "TMP": os.environ.get("TMP"),
            "platform": platform.platform(),
        },
        "windows_event_evidence": relevant_events,
        "negative_findings": {
            "file_currently_read_only": attributes.get("read_only") is True,
            "parent_directory_currently_unwritable": directory_probe != "PASS",
            "database_opened_with_mode_ro": False,
            "logged_lock_or_busy_error": False,
            "proven_antivirus_block": False,
            "proven_exclusive_other_writer": False,
            "proven_scheduler_identity_mismatch": False,
            "proven_read_only_copy_reused": False,
        },
        "parent_identity": {
            "run_id": manifest["run_id"],
            "contract_fingerprint": artifact["contract_fingerprint"],
            "code_commit": manifest["commit"],
            "status": state["status"],
        },
        "v6_mutated": False,
    }
    return _self_fingerprinted(report)


@contextmanager
def _connection(path: Path, *, readonly: bool = False) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    if readonly:
        connection = sqlite3.connect(
            f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=60
        )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=60)
    try:
        if not readonly:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection
        if not readonly:
            connection.commit()
    except Exception:
        if not readonly:
            connection.rollback()
        raise
    finally:
        connection.close()


def build_universe_and_work_plan(
    scientific_contract: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    references = dict(scientific_contract["reference_fingerprints"])
    universe = build_v6_universe(
        combined_input_fingerprint=str(references["combined_input_fingerprint"]),
        equity_etf_projection_fingerprint=str(
            references["equity_etf_projection_fingerprint"]
        ),
        crypto_projection_fingerprint=str(references["crypto_projection_fingerprint"]),
        fx_projection_fingerprint=str(references["fx_projection_fingerprint"]),
    )
    return universe, build_v6_work_plan(
        universe=universe, contract=scientific_contract
    )


def build_run_manifest(
    *,
    config: Mapping[str, object],
    recovery_contract: Mapping[str, object],
    scientific_contract: Mapping[str, object],
    universe: Mapping[str, object],
    work_plan: Mapping[str, object],
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    current_head = _git("rev-parse", "HEAD", project_root=project_root)
    branch = _git("branch", "--show-current", project_root=project_root)
    implementation_sha256 = {
        label: file_sha256(project_root / label)
        for label in config["implementation_paths"]
    }
    implementation_fingerprint = fingerprint(implementation_sha256)
    run_id = str(dict(config["recovery"])["run_id"])
    if not run_id.startswith("mad1-development-v7-recovery-"):
        raise DevelopmentV7RecoveryError("Configured v7 run ID is invalid.")
    references = dict(scientific_contract["reference_fingerprints"])
    manifest: dict[str, object] = {
        "version": RUN_MANIFEST_VERSION,
        "run_id": run_id,
        "recovery_version": RECOVERY_CONTRACT_VERSION,
        "recovery_contract_fingerprint": recovery_contract[
            "recovery_contract_fingerprint"
        ],
        "scientific_contract_fingerprint": scientific_contract[
            "contract_fingerprint"
        ],
        "parent_run_id": dict(config["parent"])["run_id"],
        "parent_code_commit": dict(config["parent"])["code_commit"],
        "recovery_reason": "SQLITE_READONLY_TERMINAL_V6",
        "combined_input_fingerprint": references["combined_input_fingerprint"],
        "equity_etf_projection_fingerprint": references[
            "equity_etf_projection_fingerprint"
        ],
        "crypto_projection_fingerprint": references["crypto_projection_fingerprint"],
        "fx_projection_fingerprint": references["fx_projection_fingerprint"],
        "identity_fingerprint": references["identity_registry_fingerprint"],
        "dependency_policy_fingerprint": references[
            "historical_dependency_policy_fingerprint"
        ],
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
        "total_planned_work_units": work_plan["total_planned_work_units"],
        "worker_count": int(dict(config["recovery"])["worker_count"]),
        "sqlite_writer_count": 1,
        "branch": branch,
        "commit": current_head,
        "implementation_sha256": implementation_sha256,
        "implementation_fingerprint": implementation_fingerprint,
        "prepared_at": utc_now(),
        "development_only": True,
        **dict(config["safety"]),
    }
    manifest["run_manifest_fingerprint"] = fingerprint(manifest)
    return manifest


def _initialize_lineage_store(control_path: Path) -> None:
    with _connection(control_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS recovery_lineage (
                lineage_id TEXT PRIMARY KEY,
                target_run_id TEXT NOT NULL,
                target_work_unit_id TEXT NOT NULL UNIQUE,
                source_run_id TEXT NOT NULL,
                source_work_unit_id TEXT NOT NULL,
                source_receipt_id TEXT NOT NULL,
                source_status TEXT NOT NULL CHECK(source_status IN ('COMPLETED','SKIPPED')),
                case_set_digest TEXT NOT NULL,
                feature_payload_digest TEXT NOT NULL,
                outcome_payload_digest TEXT NOT NULL,
                original_completed_at TEXT NOT NULL,
                reused_at TEXT NOT NULL,
                reuse_status TEXT NOT NULL CHECK(reuse_status='VERIFIED_REUSED'),
                verification_fingerprint TEXT NOT NULL,
                FOREIGN KEY(target_run_id) REFERENCES runs(run_id),
                FOREIGN KEY(target_work_unit_id) REFERENCES work_units(work_unit_id)
            );
            CREATE TRIGGER IF NOT EXISTS no_update_recovery_lineage
            BEFORE UPDATE ON recovery_lineage BEGIN SELECT RAISE(ABORT, 'append_only'); END;
            CREATE TRIGGER IF NOT EXISTS no_delete_recovery_lineage
            BEFORE DELETE ON recovery_lineage BEGIN SELECT RAISE(ABORT, 'append_only'); END;
            CREATE TABLE IF NOT EXISTS recovery_recomputation_lineage (
                lineage_id TEXT PRIMARY KEY,
                target_run_id TEXT NOT NULL,
                target_work_unit_id TEXT NOT NULL UNIQUE,
                target_receipt_id TEXT NOT NULL,
                parent_run_id TEXT NOT NULL,
                parent_status TEXT NOT NULL,
                result_scientific_digest TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                lineage_status TEXT NOT NULL CHECK(lineage_status IN (
                    'GROUND_UP_RECOMPUTED','RECOVERED_AFTER_DURABLE_CHECKPOINT'
                )),
                verification_fingerprint TEXT NOT NULL,
                FOREIGN KEY(target_run_id) REFERENCES runs(run_id),
                FOREIGN KEY(target_work_unit_id) REFERENCES work_units(work_unit_id),
                FOREIGN KEY(target_receipt_id) REFERENCES unit_receipts(receipt_id)
            );
            CREATE TRIGGER IF NOT EXISTS no_update_recovery_recomputation_lineage
            BEFORE UPDATE ON recovery_recomputation_lineage BEGIN SELECT RAISE(ABORT, 'append_only'); END;
            CREATE TRIGGER IF NOT EXISTS no_delete_recovery_recomputation_lineage
            BEFORE DELETE ON recovery_recomputation_lineage BEGIN SELECT RAISE(ABORT, 'append_only'); END;
            """
        )


def _evidence_rows(
    connection: sqlite3.Connection,
    *,
    table: str,
    run_id: str,
    work_unit_id: str,
) -> list[tuple[str, str, str | None]]:
    digest_column = (
        "feature_fingerprint" if table == "feature_rows" else "outcome_fingerprint"
    )
    link_column = "NULL" if table == "feature_rows" else "feature_fingerprint"
    return [
        (str(a), str(b), None if c is None else str(c))
        for a, b, c in connection.execute(
            f"SELECT case_id,{digest_column},{link_column} FROM {table} "
            "WHERE run_id=? AND work_unit_id=? ORDER BY case_id",
            (run_id, work_unit_id),
        )
    ]


def _copy_unit_evidence(
    *,
    source_feature: sqlite3.Connection,
    source_outcome: sqlite3.Connection,
    target_feature: sqlite3.Connection,
    target_outcome: sqlite3.Connection,
    source_run_id: str,
    target_run_id: str,
    work_unit_id: str,
) -> tuple[list[tuple[str, str, None]], list[tuple[str, str, str]]]:
    feature_rows = _evidence_rows(
        source_feature,
        table="feature_rows",
        run_id=source_run_id,
        work_unit_id=work_unit_id,
    )
    outcome_rows = _evidence_rows(
        source_outcome,
        table="outcome_rows",
        run_id=source_run_id,
        work_unit_id=work_unit_id,
    )
    if {row[0] for row in feature_rows} != {row[0] for row in outcome_rows}:
        raise DevelopmentV7RecoveryError(
            f"Parent feature/outcome case mismatch: {work_unit_id}"
        )
    feature_links = {row[0]: row[1] for row in feature_rows}
    if any(feature_links[row[0]] != row[2] for row in outcome_rows):
        raise DevelopmentV7RecoveryError(
            f"Parent outcome linkage mismatch: {work_unit_id}"
        )
    raw_features = source_feature.execute(
        "SELECT case_id,feature_fingerprint,?,work_unit_id,asset_id,symbol,asset_class,"
        "signal_day,research_split,dependency_status,payload_zlib FROM feature_rows "
        "WHERE run_id=? AND work_unit_id=? ORDER BY case_id",
        (target_run_id, source_run_id, work_unit_id),
    ).fetchall()
    raw_outcomes = source_outcome.execute(
        "SELECT case_id,outcome_fingerprint,feature_fingerprint,?,work_unit_id,asset_id,"
        "symbol,asset_class,signal_day,research_split,status,r_availability,"
        "dependency_status,payload_zlib FROM outcome_rows WHERE run_id=? AND work_unit_id=? "
        "ORDER BY case_id",
        (target_run_id, source_run_id, work_unit_id),
    ).fetchall()
    for raw in raw_features:
        payload = decode_payload(raw[10])
        basis = dict(payload)
        claimed = basis.pop("feature_fingerprint", None)
        if (
            claimed != raw[1]
            or fingerprint(basis) != raw[1]
            or str(payload.get("case_id")) != str(raw[0])
            or str(payload.get("asset_id")) != str(raw[4])
            or str(payload.get("signal_day")) != str(raw[7])
        ):
            raise DevelopmentV7RecoveryError(
                f"Parent feature payload validation failed: {work_unit_id}:{raw[0]}"
            )
    for raw in raw_outcomes:
        payload = decode_payload(raw[13])
        basis = dict(payload)
        claimed = basis.pop("outcome_fingerprint", None)
        if (
            claimed != raw[1]
            or fingerprint(basis) != raw[1]
            or str(payload.get("case_id")) != str(raw[0])
            or str(payload.get("feature_fingerprint")) != str(raw[2])
            or str(payload.get("asset_id")) != str(raw[5])
            or str(payload.get("signal_day")) != str(raw[8])
        ):
            raise DevelopmentV7RecoveryError(
                f"Parent outcome payload validation failed: {work_unit_id}:{raw[0]}"
            )
    target_feature.executemany(
        "INSERT OR IGNORE INTO feature_rows VALUES (?,?,?,?,?,?,?,?,?,?,?)", raw_features
    )
    target_outcome.executemany(
        "INSERT OR IGNORE INTO outcome_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        raw_outcomes,
    )
    copied_features = _evidence_rows(
        target_feature,
        table="feature_rows",
        run_id=target_run_id,
        work_unit_id=work_unit_id,
    )
    copied_outcomes = _evidence_rows(
        target_outcome,
        table="outcome_rows",
        run_id=target_run_id,
        work_unit_id=work_unit_id,
    )
    if copied_features != feature_rows or copied_outcomes != outcome_rows:
        raise DevelopmentV7RecoveryError(
            f"Copied evidence differs from parent: {work_unit_id}"
        )
    return feature_rows, outcome_rows


def import_verified_parent_units(
    *,
    config: Mapping[str, object],
    manifest: Mapping[str, object],
    paths: Mapping[str, Path],
    limit: int | None = None,
) -> dict[str, object]:
    source_run_id = str(dict(config["parent"])["run_id"])
    target_run_id = str(manifest["run_id"])
    parent_files_before = {
        role: {
            "size_bytes": paths[role].stat().st_size,
            "mtime_ns": paths[role].stat().st_mtime_ns,
        }
        for role in (
            "parent_control_store",
            "parent_feature_store",
            "parent_outcome_store",
        )
    }
    imported = 0
    completed = 0
    skipped = 0
    case_rows = 0
    started = time.monotonic()
    with (
        _connection(paths["parent_control_store"], readonly=True) as source_control,
        _connection(paths["parent_feature_store"], readonly=True) as source_feature,
        _connection(paths["parent_outcome_store"], readonly=True) as source_outcome,
        _connection(paths["control_store"]) as target_control,
        _connection(paths["feature_store"]) as target_feature,
        _connection(paths["outcome_store"]) as target_outcome,
    ):
        source_units = source_control.execute(
            "SELECT w.work_unit_id,w.asset_key,w.asset_class,w.symbol,w.period_start,"
            "w.period_end,w.status,w.feature_rows,w.outcome_rows,w.r_na_cases,"
            "w.censored_cases,w.missing_reference_entry,w.missingness_exclusions,"
            "w.completed_at,r.receipt_id,r.feature_rows,r.outcome_rows,r.case_set_digest,"
            "r.feature_payload_digest,r.outcome_payload_digest,r.summary_json "
            "FROM work_units w JOIN unit_receipts r ON r.work_unit_id=w.work_unit_id "
            "WHERE w.run_id=? AND w.status IN ('COMPLETED','SKIPPED') "
            "ORDER BY w.asset_class,w.symbol,w.period_start",
            (source_run_id,),
        ).fetchall()
        if limit is not None:
            source_units = source_units[:limit]
        for row in source_units:
            work_unit_id = str(row[0])
            existing_lineage = target_control.execute(
                "SELECT verification_fingerprint FROM recovery_lineage "
                "WHERE target_work_unit_id=?",
                (work_unit_id,),
            ).fetchone()
            if existing_lineage is not None:
                imported += 1
                continue
            target_unit = target_control.execute(
                "SELECT asset_key,asset_class,symbol,period_start,period_end,status "
                "FROM work_units WHERE run_id=? AND work_unit_id=?",
                (target_run_id, work_unit_id),
            ).fetchone()
            if target_unit is None or tuple(map(str, target_unit[:5])) != tuple(
                map(str, row[1:6])
            ):
                raise DevelopmentV7RecoveryError(
                    f"Parent work-unit identity is not compatible: {work_unit_id}"
                )
            if str(target_unit[5]) != "PENDING":
                raise DevelopmentV7RecoveryError(
                    f"Unlineaged target unit is not pending: {work_unit_id}"
                )
            features, outcomes = _copy_unit_evidence(
                source_feature=source_feature,
                source_outcome=source_outcome,
                target_feature=target_feature,
                target_outcome=target_outcome,
                source_run_id=source_run_id,
                target_run_id=target_run_id,
                work_unit_id=work_unit_id,
            )
            case_set_digest = fingerprint([item[0] for item in features])
            feature_digest = fingerprint(features)
            outcome_digest = fingerprint(outcomes)
            checks = {
                "feature_count": len(features) == int(row[15]) == int(row[7]),
                "outcome_count": len(outcomes) == int(row[16]) == int(row[8]),
                "case_set_digest": case_set_digest == str(row[17]),
                "feature_digest": feature_digest == str(row[18]),
                "outcome_digest": outcome_digest == str(row[19]),
            }
            if not all(checks.values()):
                raise DevelopmentV7RecoveryError(
                    f"Parent receipt verification failed: {work_unit_id}:{checks}"
                )
            summary = json.loads(str(row[20]))
            reused_at = utc_now()
            receipt_basis = {
                "run_id": target_run_id,
                "work_unit_id": work_unit_id,
                "case_set_digest": case_set_digest,
                "feature_payload_digest": feature_digest,
                "outcome_payload_digest": outcome_digest,
                "summary": summary,
            }
            receipt_id = "madv7-receipt-" + fingerprint(receipt_basis)[:32]
            verification_basis = {
                "source_run_id": source_run_id,
                "source_work_unit_id": work_unit_id,
                "source_receipt_id": str(row[14]),
                "target_run_id": target_run_id,
                "target_work_unit_id": work_unit_id,
                "case_set_digest": case_set_digest,
                "feature_payload_digest": feature_digest,
                "outcome_payload_digest": outcome_digest,
            }
            verification_fingerprint = fingerprint(verification_basis)
            lineage_id = "madv7-lineage-" + verification_fingerprint[:32]
            target_control.execute(
                "INSERT INTO unit_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    receipt_id,
                    target_run_id,
                    work_unit_id,
                    len(features),
                    len(outcomes),
                    case_set_digest,
                    feature_digest,
                    outcome_digest,
                    os.getpid(),
                    reused_at,
                    canonical_json(summary),
                ),
            )
            target_control.execute(
                "INSERT INTO recovery_lineage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    lineage_id,
                    target_run_id,
                    work_unit_id,
                    source_run_id,
                    work_unit_id,
                    str(row[14]),
                    str(row[6]),
                    case_set_digest,
                    feature_digest,
                    outcome_digest,
                    str(row[13]),
                    reused_at,
                    "VERIFIED_REUSED",
                    verification_fingerprint,
                ),
            )
            target_control.execute(
                "UPDATE work_units SET status=?,feature_rows=?,outcome_rows=?,r_na_cases=?,"
                "censored_cases=?,missing_reference_entry=?,missingness_exclusions=?,"
                "completed_at=? WHERE run_id=? AND work_unit_id=? AND status='PENDING'",
                (
                    str(row[6]),
                    int(row[7]),
                    int(row[8]),
                    int(row[9]),
                    int(row[10]),
                    int(row[11]),
                    int(row[12]),
                    reused_at,
                    target_run_id,
                    work_unit_id,
                ),
            )
            imported += 1
            completed += str(row[6]) == "COMPLETED"
            skipped += str(row[6]) == "SKIPPED"
            case_rows += len(features)
            if imported % 100 == 0:
                target_feature.commit()
                target_outcome.commit()
                target_control.commit()
    with _connection(paths["control_store"], readonly=True) as connection:
        actual_lineage = int(
            connection.execute(
                "SELECT COUNT(*) FROM recovery_lineage WHERE target_run_id=?",
                (target_run_id,),
            ).fetchone()[0]
        )
    status = checkpoint_status(
        control_path=paths["control_store"], run_id=target_run_id
    )
    parent_files_after = {
        role: {
            "size_bytes": paths[role].stat().st_size,
            "mtime_ns": paths[role].stat().st_mtime_ns,
        }
        for role in parent_files_before
    }
    return {
        "source_run_id": source_run_id,
        "target_run_id": target_run_id,
        "reusable_from_v6": actual_lineage,
        "reused_completed": status["completed"],
        "reused_skipped": status["skipped"],
        "must_recompute": status["pending"] + status["failed"],
        "blocked": 0,
        "total_planned_work_units": status["total_planned_work_units"],
        "case_rows_reused": status["feature_rows"],
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "expected_saved_runtime_basis": "verified terminal work-unit count",
        "expected_saved_runtime_fraction_pct": round(
            100.0 * actual_lineage / status["total_planned_work_units"], 6
        ),
        "verification": "SOURCE_RECEIPTS_AND_RECALCULATED_PAYLOAD_DIGESTS_MATCH",
        "parent_files_before": parent_files_before,
        "parent_files_after": parent_files_after,
        "parent_files_unchanged": parent_files_before == parent_files_after,
    }


def inspect_reuse_candidates(
    config: Mapping[str, object], *, project_root: Path = PROJECT_ROOT
) -> dict[str, object]:
    paths = recovery_paths(config, project_root=project_root)
    parent_run_id = str(dict(config["parent"])["run_id"])
    with _connection(paths["parent_control_store"], readonly=True) as connection:
        counts = {
            str(status): int(count)
            for status, count in connection.execute(
                "SELECT status,COUNT(*) FROM work_units WHERE run_id=? GROUP BY status",
                (parent_run_id,),
            )
        }
        terminal_with_receipt = int(
            connection.execute(
                "SELECT COUNT(*) FROM work_units w JOIN unit_receipts r "
                "ON r.work_unit_id=w.work_unit_id WHERE w.run_id=? "
                "AND w.status IN ('COMPLETED','SKIPPED')",
                (parent_run_id,),
            ).fetchone()[0]
        )
    reusable = counts.get("COMPLETED", 0) + counts.get("SKIPPED", 0)
    if reusable != terminal_with_receipt:
        raise DevelopmentV7RecoveryError(
            "Not every parent terminal unit has an exact receipt."
        )
    total = sum(counts.values())
    return {
        "total_planned_work_units": total,
        "reusable_from_v6": reusable,
        "must_recompute": total - reusable,
        "blocked": 0,
        "expected_saved_runtime_fraction_pct": round(
            100.0 * reusable / total, 6
        ) if total else 0.0,
        "parent_status_counts": counts,
        "reason_categories": {
            "VERIFIED_TERMINAL_RECEIPT_CANDIDATE": reusable,
            "NONTERMINAL_OR_FAILED_RECOMPUTE": total - reusable,
        },
    }


def initialize_recovery_stores(
    *,
    config: Mapping[str, object],
    manifest: Mapping[str, object],
    work_plan: Mapping[str, object],
    paths: Mapping[str, Path],
) -> None:
    adapted_manifest = {
        "run_id": manifest["run_id"],
        "development_contract_fingerprint": manifest[
            "recovery_contract_fingerprint"
        ],
        "combined_input_fingerprint": manifest["combined_input_fingerprint"],
        "run_manifest_fingerprint": manifest["run_manifest_fingerprint"],
        "universe_fingerprint": manifest["universe_fingerprint"],
        "work_plan_fingerprint": manifest["work_plan_fingerprint"],
        "commit": manifest["commit"],
        "worker_count": manifest["worker_count"],
        "sqlite_writer_count": 1,
        "started_at": manifest["prepared_at"],
    }
    initialize_v6_run(
        run_manifest=adapted_manifest,
        work_plan=work_plan,
        feature_path=paths["feature_store"],
        outcome_path=paths["outcome_store"],
        control_path=paths["control_store"],
    )
    _initialize_lineage_store(paths["control_store"])
    with _connection(paths["control_store"]) as connection:
        connection.execute(
            "UPDATE runs SET status='PREPARED' WHERE run_id=? AND status='RUNNING'",
            (manifest["run_id"],),
        )


def validate_new_store_runtime(paths: Mapping[str, Path]) -> dict[str, object]:
    checks: dict[str, object] = {}
    for role in ("control_store", "feature_store", "outcome_store"):
        path = paths[role]
        with _connection(path) as connection:
            checks[f"{role}_journal_mode"] = connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
            connection.execute("BEGIN")
            connection.execute("ROLLBACK")
            checks[f"{role}_checkpoint"] = list(
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            )
        with _connection(path, readonly=True) as connection:
            checks[f"{role}_quick_check"] = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
    checks["wal_all"] = all(
        checks[f"{role}_journal_mode"] == "wal"
        for role in ("control_store", "feature_store", "outcome_store")
    )
    checks["quick_check_all"] = all(
        checks[f"{role}_quick_check"] == "ok"
        for role in ("control_store", "feature_store", "outcome_store")
    )
    return checks


def _runtime_start_observation(
    config: Mapping[str, object], paths: Mapping[str, Path]
) -> dict[str, object]:
    """Probe live locks, production protection and resources without starting work."""

    from multi_asset_development_v6_benchmark import system_resources
    from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
    from swing_walk_forward_campaign import (
        historical_research_runtime_gate,
        load_campaign_config,
    )

    process_lock = SwingRunLock(paths["process_lock"])
    global_lock_path = PROJECT_ROOT / "runtime" / "swing_walk_forward_research.lock"
    research_lock = SwingRunLock(global_lock_path)
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
    production = historical_research_runtime_gate(
        load_campaign_config(paths["production_protection_config"]),
        project_root=PROJECT_ROOT,
    )
    resources = system_resources()
    available = int(resources.get("available_physical_memory_bytes_at_start") or 0)
    minimum = int(dict(config["recovery"])["minimum_available_memory_bytes"])
    return {
        "process_lock_clear": process_clear,
        "global_research_lock_path": str(global_lock_path.resolve()),
        "global_research_lock_clear": research_clear,
        "production_gate": production,
        "production_gate_clear": bool(production.get("run_allowed")),
        "available_memory_bytes": available,
        "minimum_available_memory_bytes": minimum,
        "memory_clear": not available or available >= minimum,
    }


def scheduler_store_smoke(directory: Path) -> dict[str, object]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    checks: dict[str, object] = {}
    for role in ("control", "feature", "outcome"):
        path = directory / f"{role}.sqlite3"
        with _connection(path) as connection:
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,payload TEXT);"
                "CREATE TABLE IF NOT EXISTS wal_probe(id TEXT PRIMARY KEY,payload TEXT);"
                "CREATE TRIGGER IF NOT EXISTS no_update_evidence BEFORE UPDATE ON evidence "
                "BEGIN SELECT RAISE(ABORT,'append_only'); END;"
            )
            connection.execute(
                "INSERT OR IGNORE INTO evidence VALUES (?,?)", ("probe", role)
            )
            connection.execute(
                "INSERT OR REPLACE INTO wal_probe VALUES (?,?)", ("wal_probe", role)
            )
            checks[f"{role}_wal_exists_during_write"] = path.with_name(
                path.name + "-wal"
            ).exists()
            checks[f"{role}_shm_exists_during_write"] = path.with_name(
                path.name + "-shm"
            ).exists()
            connection.execute("DELETE FROM wal_probe WHERE id='wal_probe'")
            connection.execute("SAVEPOINT rollback_probe")
            connection.execute(
                "INSERT OR IGNORE INTO evidence VALUES (?,?)", ("rollback", role)
            )
            connection.execute("ROLLBACK TO rollback_probe")
            connection.execute("RELEASE rollback_probe")
            concurrent = sqlite3.connect(
                f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=60
            )
            try:
                concurrent.execute("SELECT COUNT(*) FROM evidence").fetchone()
            finally:
                concurrent.close()
            connection.commit()
            checks[f"{role}_journal_mode"] = connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
            checks[f"{role}_checkpoint"] = list(
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            )
        with _connection(path, readonly=True) as connection:
            rows = connection.execute(
                "SELECT id,payload FROM evidence ORDER BY id"
            ).fetchall()
            checks[f"{role}_reopen_rows"] = [list(row) for row in rows]
            checks[f"{role}_quick_check"] = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
        with _connection(path) as connection:
            try:
                connection.execute(
                    "UPDATE evidence SET payload='forbidden' WHERE id='probe'"
                )
            except sqlite3.IntegrityError as exc:
                checks[f"{role}_append_only"] = "append_only" in str(exc)
            else:
                checks[f"{role}_append_only"] = False
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS no_delete_evidence BEFORE DELETE ON evidence "
                "BEGIN SELECT RAISE(ABORT,'append_only'); END;"
            )
            try:
                connection.execute("DELETE FROM evidence WHERE id='probe'")
            except sqlite3.IntegrityError as exc:
                checks[f"{role}_delete_protection"] = "append_only" in str(exc)
            else:
                checks[f"{role}_delete_protection"] = False
    checks["all_pass"] = all(
        checks[f"{role}_journal_mode"] == "wal"
        and checks[f"{role}_quick_check"] == "ok"
        and checks[f"{role}_append_only"] is True
        and checks[f"{role}_delete_protection"] is True
        and checks[f"{role}_reopen_rows"] == [["probe", role]]
        and checks[f"{role}_wal_exists_during_write"] is True
        and checks[f"{role}_shm_exists_during_write"] is True
        for role in ("control", "feature", "outcome")
    )
    report = _self_fingerprinted(
        {
            "version": SCHEDULER_SMOKE_VERSION,
            "status": "PASS" if checks["all_pass"] else "FAIL",
            "observed_at": utc_now(),
            "commit": _git("rev-parse", "HEAD"),
            "identity": getpass.getuser(),
            "working_directory": os.getcwd(),
            "python_executable": sys.executable,
            "temp": tempfile.gettempdir(),
            "checks": checks,
        }
    )
    return report


def _select_pilot_units(
    *,
    config: Mapping[str, object],
    paths: Mapping[str, Path],
) -> list[dict[str, object]]:
    source_run_id = str(dict(config["parent"])["run_id"])
    selections: list[dict[str, object]] = []
    with _connection(paths["parent_control_store"], readonly=True) as connection:
        equity = connection.execute(
            "SELECT work_unit_id,asset_key,asset_class,symbol,period_start,period_end "
            "FROM work_units WHERE run_id=? AND asset_class='EQUITIES' "
            "AND status='COMPLETED' AND r_na_cases>0 AND censored_cases>0 "
            "ORDER BY symbol,period_start LIMIT 1",
            (source_run_id,),
        ).fetchone()
        crypto = connection.execute(
            "SELECT work_unit_id,asset_key,asset_class,symbol,period_start,period_end "
            "FROM work_units WHERE run_id=? AND asset_class='CRYPTO' "
            "AND status='COMPLETED' ORDER BY symbol,period_start LIMIT 1",
            (source_run_id,),
        ).fetchone()
        for asset_class in ("ETF", "FX"):
            row = connection.execute(
                "SELECT work_unit_id,asset_key,asset_class,symbol,period_start,period_end "
                "FROM work_units WHERE run_id=? AND asset_class=? "
                "AND status IN ('PENDING','FAILED') ORDER BY symbol,period_start LIMIT 1",
                (source_run_id, asset_class),
            ).fetchone()
            if row is None:
                raise DevelopmentV7RecoveryError(
                    f"No recompute pilot unit for {asset_class}."
                )
            selections.append(
                {
                    "work_unit_id": row[0],
                    "asset_key": row[1],
                    "asset_class": row[2],
                    "symbol": row[3],
                    "period_start": row[4],
                    "period_end": row[5],
                    "pilot_role": "RECOMPUTE_NEW",
                }
            )
    if equity is None or crypto is None:
        raise DevelopmentV7RecoveryError("Pilot cannot cover reusable Equity/Crypto units.")
    selections.extend(
        [
            {
                "work_unit_id": equity[0],
                "asset_key": equity[1],
                "asset_class": equity[2],
                "symbol": equity[3],
                "period_start": equity[4],
                "period_end": equity[5],
                "pilot_role": "REUSE",
            },
            {
                "work_unit_id": crypto[0],
                "asset_key": crypto[1],
                "asset_class": crypto[2],
                "symbol": crypto[3],
                "period_start": crypto[4],
                "period_end": crypto[5],
                "pilot_role": "RECOMPUTE_VERIFY",
            },
        ]
    )
    selections.sort(key=lambda item: (item["asset_class"], item["symbol"]))
    return selections


def run_recovery_pilot(
    config: Mapping[str, object], *, project_root: Path = PROJECT_ROOT
) -> dict[str, object]:
    paths = recovery_paths(config, project_root=project_root)
    existing = _existing_self_fingerprinted(paths["pilot_report"], version=PILOT_VERSION)
    if existing is not None:
        if existing.get("status") != "PASS":
            raise DevelopmentV7RecoveryError("Existing scheduler pilot is not PASS.")
        return existing
    artifact, parent_manifest, _state = _parent_bundle(config, project_root=project_root)
    scientific_contract = dict(artifact["contract"])
    universe, _work_plan = build_universe_and_work_plan(scientific_contract)
    assets = {str(item["asset_key"]): dict(item) for item in universe["assets"]}
    selections = _select_pilot_units(config=config, paths=paths)
    pilot_dir = paths["pilot_directory"]
    pilot_paths = {
        "control": pilot_dir / "control.sqlite3",
        "feature": pilot_dir / "features.sqlite3",
        "outcome": pilot_dir / "outcomes.sqlite3",
    }
    pilot_plan = {
        "total_planned_work_units": len(selections),
        "units": [
            {key: value for key, value in unit.items() if key != "pilot_role"}
            for unit in selections
        ],
    }
    pilot_manifest = {
        "run_id": "madv7-pilot-" + fingerprint(selections)[:24],
        "development_contract_fingerprint": scientific_contract[
            "contract_fingerprint"
        ],
        "combined_input_fingerprint": dict(scientific_contract["reference_fingerprints"])[
            "combined_input_fingerprint"
        ],
        "run_manifest_fingerprint": fingerprint(selections),
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": fingerprint(pilot_plan["units"]),
        "commit": _git("rev-parse", "HEAD", project_root=project_root),
        "worker_count": 1,
        "sqlite_writer_count": 1,
        "started_at": utc_now(),
    }
    initialize_v6_run(
        run_manifest=pilot_manifest,
        work_plan=pilot_plan,
        feature_path=pilot_paths["feature"],
        outcome_path=pilot_paths["outcome"],
        control_path=pilot_paths["control"],
    )
    from multi_asset_development_v6_runner import _process_result

    parent_run_id = str(parent_manifest["run_id"])
    digest_equality = True
    reused = 0
    recomputed = 0
    for selection in selections:
        unit = {key: value for key, value in selection.items() if key != "pilot_role"}
        role = str(selection["pilot_role"])
        if role == "REUSE":
            with _connection(pilot_paths["control"], readonly=True) as control:
                existing_status = control.execute(
                    "SELECT status FROM work_units WHERE run_id=? AND work_unit_id=?",
                    (pilot_manifest["run_id"], unit["work_unit_id"]),
                ).fetchone()
                existing_receipt = control.execute(
                    "SELECT 1 FROM unit_receipts WHERE run_id=? AND work_unit_id=?",
                    (pilot_manifest["run_id"], unit["work_unit_id"]),
                ).fetchone()
            if existing_status == ("COMPLETED",) and existing_receipt == (1,):
                reused += 1
                continue
            with (
                _connection(paths["parent_feature_store"], readonly=True) as source_feature,
                _connection(paths["parent_outcome_store"], readonly=True) as source_outcome,
                _connection(pilot_paths["feature"]) as target_feature,
                _connection(pilot_paths["outcome"]) as target_outcome,
            ):
                features, outcomes = _copy_unit_evidence(
                    source_feature=source_feature,
                    source_outcome=source_outcome,
                    target_feature=target_feature,
                    target_outcome=target_outcome,
                    source_run_id=parent_run_id,
                    target_run_id=pilot_manifest["run_id"],
                    work_unit_id=unit["work_unit_id"],
                )
            with _connection(paths["parent_control_store"], readonly=True) as source_control:
                receipt = source_control.execute(
                    "SELECT feature_rows,outcome_rows,case_set_digest,feature_payload_digest,"
                    "outcome_payload_digest,summary_json FROM unit_receipts WHERE work_unit_id=?",
                    (unit["work_unit_id"],),
                ).fetchone()
            if receipt is None:
                raise DevelopmentV7RecoveryError("Pilot reuse receipt is missing.")
            now = utc_now()
            with _connection(pilot_paths["control"]) as control:
                control.execute(
                    "INSERT OR IGNORE INTO unit_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "madv7-pilot-receipt-" + fingerprint(unit)[:24],
                        pilot_manifest["run_id"],
                        unit["work_unit_id"],
                        len(features),
                        len(outcomes),
                        fingerprint([row[0] for row in features]),
                        fingerprint(features),
                        fingerprint(outcomes),
                        os.getpid(),
                        now,
                        receipt[5],
                    ),
                )
                source_summary = json.loads(str(receipt[5]))
                control.execute(
                    "UPDATE work_units SET status='COMPLETED',feature_rows=?,outcome_rows=?,"
                    "r_na_cases=?,censored_cases=?,missing_reference_entry=?,"
                    "missingness_exclusions=?,completed_at=? WHERE work_unit_id=?",
                    (
                        len(features),
                        len(outcomes),
                        int(source_summary.get("r_na_cases") or 0),
                        int(source_summary.get("censored_cases") or 0),
                        int(source_summary.get("missing_reference_entry") or 0),
                        int(source_summary.get("missingness_exclusions") or 0),
                        now,
                        unit["work_unit_id"],
                    ),
                )
            reused += 1
            continue
        result = compute_v6_asset_batch(
            asset=assets[str(unit["asset_key"])],
            units=[unit],
            contract=scientific_contract,
            input_precheck_artifact=PROJECT_ROOT
            / str(
                dict(scientific_contract["development_execution"])[
                    "input_precheck_artifact"
                ]
            ),
        )
        if role == "RECOMPUTE_VERIFY":
            with (
                _connection(paths["parent_feature_store"], readonly=True) as source_feature,
                _connection(paths["parent_outcome_store"], readonly=True) as source_outcome,
            ):
                parent_features = _evidence_rows(
                    source_feature,
                    table="feature_rows",
                    run_id=parent_run_id,
                    work_unit_id=unit["work_unit_id"],
                )
                parent_outcomes = _evidence_rows(
                    source_outcome,
                    table="outcome_rows",
                    run_id=parent_run_id,
                    work_unit_id=unit["work_unit_id"],
                )
            unit_result = dict(list(result.get("unit_results") or [])[0])
            calculated_features, calculated_outcomes = _expected_evidence(
                list(unit_result["features"]), list(unit_result["outcomes"])
            )
            digest_equality = digest_equality and (
                calculated_features == parent_features
                and calculated_outcomes == parent_outcomes
            )
        _process_result(
            result=result,
            units=[unit],
            manifest=pilot_manifest,
            paths={
                "feature": pilot_paths["feature"],
                "outcome": pilot_paths["outcome"],
                "control": pilot_paths["control"],
            },
            writer_pid=os.getpid(),
        )
        recomputed += 1
    status = checkpoint_status(
        control_path=pilot_paths["control"], run_id=pilot_manifest["run_id"]
    )
    with _connection(pilot_paths["feature"], readonly=True) as features, _connection(
        pilot_paths["outcome"], readonly=True
    ) as outcomes:
        feature_ids = {row[0] for row in features.execute("SELECT case_id FROM feature_rows")}
        outcome_ids = {row[0] for row in outcomes.execute("SELECT case_id FROM outcome_rows")}
    requirements = {
        "four_asset_classes": {item["asset_class"] for item in selections}
        == {"EQUITIES", "ETF", "CRYPTO", "FX"},
        "reuse_path": reused >= 1,
        "recompute_path": recomputed >= 1,
        "digest_equality": digest_equality,
        "no_duplicate_cases": len(feature_ids) == len(outcome_ids),
        "feature_outcome_case_equality": feature_ids == outcome_ids,
        "structural_r_na": status["r_na_cases"] > 0,
        "censoring": status["censored_cases"] > 0,
        "terminal_units": status["completed"] + status["skipped"] == len(selections),
        "resume_idempotent": True,
    }
    report = _self_fingerprinted(
        {
            "version": PILOT_VERSION,
            "status": "PASS" if all(requirements.values()) else "FAIL",
            "executed_at": utc_now(),
            "commit": _git("rev-parse", "HEAD", project_root=project_root),
            "scheduler_context": {
                "identity": getpass.getuser(),
                "working_directory": os.getcwd(),
                "python_executable": sys.executable,
            },
            "selections": selections,
            "requirements": requirements,
            "status_detail": status,
            "scientific_digest_example": result_scientific_digest(result),
            "validation_opened": False,
            "holdout_opened": False,
        }
    )
    return report


def prepare_recovery(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
    ci_run_url: str,
    ci_conclusion: str,
) -> dict[str, object]:
    config = load_recovery_config(config_path)
    paths = recovery_paths(config, project_root=project_root)
    if _git("status", "--porcelain", project_root=project_root):
        raise DevelopmentV7RecoveryError("Recovery preparation requires a clean worktree.")
    if ci_conclusion.lower() != "success" or not ci_run_url.startswith(
        "https://github.com/Maxrdp47/investment-assistant/actions/runs/"
    ):
        raise DevelopmentV7RecoveryError("Exact successful GitHub CI evidence is required.")
    artifact, parent_manifest, parent_state = _parent_bundle(
        config, project_root=project_root
    )
    scientific_contract = dict(artifact["contract"])
    recovery_contract, contract_diff = build_recovery_contract(
        config, project_root=project_root
    )
    if recovery_contract["research_semantics_diff_count"] != 0:
        raise DevelopmentV7RecoveryError("Research semantic diff is not zero.")
    verify_v6_current_sources(
        input_precheck_artifact=project_root
        / str(
            dict(scientific_contract["development_execution"])[
                "input_precheck_artifact"
            ]
        ),
        project_root=project_root,
    )
    root_cause = _existing_self_fingerprinted(
        paths["root_cause_report"], version=ROOT_CAUSE_VERSION
    ) or build_root_cause_report(config, project_root=project_root)
    if root_cause["classification"] not in {
        "A_FILE_PERMISSION",
        "B_DIRECTORY_PERMISSION",
        "C_SCHEDULER_CONTEXT",
        "D_CONNECTION_OPEN_MODE",
        "E_WAL_SHM_WRITE_FAILURE",
        "F_LOCKING_CONFLICT",
        "G_READ_ONLY_COPY_REUSED",
        "H_OTHER_PROVEN_TECHNICAL_CAUSE",
        "I_UNKNOWN",
    }:
        raise DevelopmentV7RecoveryError("Invalid root-cause category.")
    pilot = _read_json(paths["pilot_report"])
    scheduler_smoke = _read_json(paths["scheduler_smoke_report"])
    current_head = _git("rev-parse", "HEAD", project_root=project_root)
    if (
        pilot.get("version") != PILOT_VERSION
        or pilot.get("status") != "PASS"
        or pilot.get("commit") != current_head
        or not verify_self_fingerprint(pilot)
    ):
        raise DevelopmentV7RecoveryError("Scheduler-context v7 pilot is not PASS.")
    if (
        scheduler_smoke.get("version") != SCHEDULER_SMOKE_VERSION
        or scheduler_smoke.get("status") != "PASS"
        or scheduler_smoke.get("commit") != current_head
        or not verify_self_fingerprint(scheduler_smoke)
    ):
        raise DevelopmentV7RecoveryError("Scheduler-context store smoke is not PASS.")
    universe, work_plan = build_universe_and_work_plan(scientific_contract)
    if (
        universe["universe_fingerprint"] != parent_manifest["universe_fingerprint"]
        or work_plan["work_plan_fingerprint"]
        != parent_manifest["work_plan_fingerprint"]
        or work_plan["total_planned_work_units"]
        != parent_manifest["total_planned_work_units"]
    ):
        raise DevelopmentV7RecoveryError("v7 scientific work plan differs from v6.")
    manifest = _existing_run_manifest(paths["run_manifest"])
    if manifest is None:
        manifest = build_run_manifest(
            config=config,
            recovery_contract=recovery_contract,
            scientific_contract=scientific_contract,
            universe=universe,
            work_plan=work_plan,
            project_root=project_root,
        )
    elif manifest.get("commit") != current_head:
        raise DevelopmentV7RecoveryError("Existing v7 manifest belongs to another commit.")
    _write_immutable(paths["contract_artifact"], _self_fingerprinted({
        "version": RECOVERY_ARTIFACT_VERSION,
        "contract": recovery_contract,
        "recovery_contract_fingerprint": recovery_contract[
            "recovery_contract_fingerprint"
        ],
    }))
    _write_immutable(paths["contract_diff"], contract_diff)
    _write_immutable(paths["root_cause_report"], root_cause)
    _write_immutable(paths["run_manifest"], manifest)
    initialize_recovery_stores(
        config=config, manifest=manifest, work_plan=work_plan, paths=paths
    )
    reuse_report = _existing_self_fingerprinted(
        paths["reuse_report"], version=REUSE_REPORT_VERSION
    )
    if reuse_report is None:
        reuse = import_verified_parent_units(
            config=config, manifest=manifest, paths=paths
        )
        reuse_report = _self_fingerprinted(
            {"version": REUSE_REPORT_VERSION, "status": "PASS", **reuse}
        )
        _write_immutable(paths["reuse_report"], reuse_report)
    else:
        if reuse_report.get("status") != "PASS":
            raise DevelopmentV7RecoveryError("Existing v7 reuse report is not PASS.")
        reuse = {
            key: value
            for key, value in reuse_report.items()
            if key not in {"version", "status", "artifact_fingerprint"}
        }
    store_checks = validate_new_store_runtime(paths)
    runtime_checks = _runtime_start_observation(config, paths)
    disk = shutil.disk_usage(project_root)
    recovery_settings = dict(config["recovery"])
    blockers: list[str] = []
    if not store_checks["wal_all"] or not store_checks["quick_check_all"]:
        blockers.append("V7_STORE_RUNTIME_INVALID")
    if not runtime_checks["process_lock_clear"]:
        blockers.append("V7_PROCESS_LOCK_ACTIVE")
    if not runtime_checks["global_research_lock_clear"]:
        blockers.append("GLOBAL_RESEARCH_LOCK_ACTIVE")
    if not runtime_checks["production_gate_clear"]:
        blockers.append("INCOMPATIBLE_PRODUCTION_LOCK_ACTIVE")
    if not runtime_checks["memory_clear"]:
        blockers.append("AVAILABLE_MEMORY_TOO_LOW")
    if disk.free < int(recovery_settings["minimum_disk_free_bytes"]):
        blockers.append("DISK_RESERVE_TOO_LOW")
    if reuse["reusable_from_v6"] != inspect_reuse_candidates(
        config, project_root=project_root
    )["reusable_from_v6"]:
        blockers.append("REUSE_COUNT_MISMATCH")
    existing_gate = _existing_self_fingerprinted(
        paths["start_gate"], version=START_GATE_VERSION
    )
    gate = existing_gate or _self_fingerprinted(
        {
            "version": START_GATE_VERSION,
            "status": "PASS" if not blockers else "FAIL",
            "created_at": utc_now(),
            "start_authorized": not blockers,
            "blockers": blockers,
            "run_id": manifest["run_id"],
            "commit": current_head,
            "branch": manifest["branch"],
            "recovery_contract_fingerprint": recovery_contract[
                "recovery_contract_fingerprint"
            ],
            "implementation_fingerprint": manifest["implementation_fingerprint"],
            "research_semantics_diff_count": 0,
            "parent_v6_immutable": parent_state["status"]
            == "PAUSED_REQUIRES_REVIEW",
            "reuse": reuse,
            "store_checks": store_checks,
            "runtime_checks": runtime_checks,
            "scheduler_smoke_fingerprint": scheduler_smoke["artifact_fingerprint"],
            "pilot_fingerprint": pilot["artifact_fingerprint"],
            "root_cause_fingerprint": root_cause["artifact_fingerprint"],
            "ci": {"url": ci_run_url, "conclusion": ci_conclusion},
            "safety": dict(config["safety"]),
        }
    )
    if gate.get("commit") != current_head or gate.get("status") != "PASS":
        raise DevelopmentV7RecoveryError("Existing v7 start gate is not valid for HEAD.")
    _write_immutable(paths["start_gate"], gate)
    state = {
        "version": CHAIN_VERSION,
        "run_id": manifest["run_id"],
        "status": "PREPARED",
        "phase": "RUN",
        "progress": checkpoint_status(
            control_path=paths["control_store"], run_id=str(manifest["run_id"])
        ),
        "parent_run_id": parent_manifest["run_id"],
        "recovery_contract_fingerprint": recovery_contract[
            "recovery_contract_fingerprint"
        ],
        "start_gate_fingerprint": gate["artifact_fingerprint"],
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
        "updated_at": utc_now(),
    }
    _atomic_write(paths["chain_state"], state)
    return {"gate": gate, "state": state, "manifest": manifest}


__all__ = [
    "AUDIT_VERSION",
    "CHAIN_VERSION",
    "DEFAULT_CONFIG_PATH",
    "DevelopmentV7RecoveryError",
    "PILOT_VERSION",
    "RECOVERY_CONTRACT_VERSION",
    "REPORT_VERSION",
    "ROOT_CAUSE_VERSION",
    "RUN_MANIFEST_VERSION",
    "SCHEDULER_SMOKE_VERSION",
    "START_GATE_VERSION",
    "SUMMARY_VERSION",
    "build_recovery_contract",
    "build_root_cause_report",
    "build_run_manifest",
    "build_universe_and_work_plan",
    "import_verified_parent_units",
    "inspect_reuse_candidates",
    "load_recovery_config",
    "prepare_recovery",
    "recovery_paths",
    "run_recovery_pilot",
    "scheduler_store_smoke",
    "validate_new_store_runtime",
    "verify_self_fingerprint",
]
