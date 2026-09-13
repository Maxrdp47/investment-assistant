from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

import multi_asset_development_v7_recovery as recovery
import multi_asset_development_v7_runner as runner
from multi_asset_development_v6_store import (
    checkpoint_status,
    initialize_v6_run,
    persist_and_complete_work_unit,
)
from multi_asset_discovery_v1 import fingerprint


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _unit(name: str) -> dict[str, object]:
    return {
        "work_unit_id": name,
        "asset_key": "EQUITIES:TEST",
        "asset_class": "EQUITIES",
        "symbol": "TEST",
        "period_start": "2020-01-01",
        "period_end": "2020-03-31",
    }


def _manifest(run_id: str, *, total: int) -> dict[str, object]:
    return {
        "run_id": run_id,
        "development_contract_fingerprint": "contract",
        "combined_input_fingerprint": "input",
        "run_manifest_fingerprint": "manifest",
        "universe_fingerprint": "universe",
        "work_plan_fingerprint": "plan",
        "commit": "commit",
        "worker_count": 1,
        "sqlite_writer_count": 1,
        "started_at": "2026-09-13T00:00:00+00:00",
        "total_planned_work_units": total,
    }


def _store_paths(root: Path, prefix: str) -> dict[str, Path]:
    return {
        "control_store": root / f"{prefix}_control.sqlite3",
        "feature_store": root / f"{prefix}_feature.sqlite3",
        "outcome_store": root / f"{prefix}_outcome.sqlite3",
    }


def _mock_parent_bundle() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    scientific_basis = {
        "feature_contract": {"version": "unchanged"},
        "reference_fingerprints": {"combined_input_fingerprint": "input"},
    }
    scientific = {**scientific_basis, "contract_fingerprint": fingerprint(scientific_basis)}
    artifact = {
        "contract": scientific,
        "contract_fingerprint": scientific["contract_fingerprint"],
    }
    manifest = {
        "run_id": "v6-parent",
        "commit": "parent-commit",
        "development_contract_fingerprint": scientific["contract_fingerprint"],
        "run_manifest_fingerprint": "parent-manifest",
    }
    state = {
        "run_id": "v6-parent",
        "status": "PAUSED_REQUIRES_REVIEW",
        "blocker": "EQUITIES:TEST:OperationalError:attempt to write a readonly database",
    }
    return artifact, manifest, state


def test_recovery_contract_has_zero_semantic_diff_and_distinct_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, manifest, state = _mock_parent_bundle()
    monkeypatch.setattr(recovery, "_parent_bundle", lambda *args, **kwargs: (artifact, manifest, state))
    monkeypatch.setattr(recovery, "_artifact_sha", lambda path: "a" * 64)
    monkeypatch.setattr(
        recovery,
        "recovery_paths",
        lambda *args, **kwargs: {
            "parent_contract_artifact": Path("parent-contract.json"),
            "parent_run_manifest": Path("parent-manifest.json"),
        },
    )
    config = {
        "parent": {"run_id": "v6-parent"},
        "recovery": {
            "run_id": "mad1-development-v7-recovery-test",
            "control_store": "target-control.sqlite3",
            "feature_store": "target-feature.sqlite3",
            "outcome_store": "target-outcome.sqlite3",
            "worker_count": 4,
            "sqlite_writer_count": 1,
            "process_lock": "target.lock",
            "scheduler_task": "v7-task",
        },
        "semantic_invariant_roots": ["feature_contract"],
        "safety": {"development_only": True},
    }
    contract, diff = recovery.build_recovery_contract(config)
    assert contract["research_semantics_diff_count"] == 0
    assert diff["hard_gate_pass"] is True
    assert contract["run_id"] == "mad1-development-v7-recovery-test"
    assert contract["scientific_contract_fingerprint"] == artifact["contract_fingerprint"]
    assert contract["recovery_contract_fingerprint"] != artifact["contract_fingerprint"]


def test_scheduler_store_smoke_proves_wal_shm_rollback_reopen_and_append_only(
    tmp_path: Path,
) -> None:
    report = recovery.scheduler_store_smoke(tmp_path)
    assert report["status"] == "PASS"
    assert recovery.verify_self_fingerprint(report)
    for role in ("control", "feature", "outcome"):
        assert report["checks"][f"{role}_journal_mode"] == "wal"
        assert report["checks"][f"{role}_wal_exists_during_write"] is True
        assert report["checks"][f"{role}_shm_exists_during_write"] is True
        assert report["checks"][f"{role}_reopen_rows"] == [["probe", role]]
        assert report["checks"][f"{role}_append_only"] is True


def test_root_cause_report_names_proven_file_but_does_not_invent_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact, manifest, state = _mock_parent_bundle()
    target = tmp_path / "parent_outcomes.sqlite3"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE evidence(id TEXT PRIMARY KEY)")
    log = tmp_path / "parent.log"
    log.write_text(
        "_insert_outcomes\nsqlite3.OperationalError: attempt to write a readonly database\n",
        encoding="utf-8",
    )
    paths = {"parent_outcome_store": target, "parent_log": log}
    monkeypatch.setattr(recovery, "recovery_paths", lambda *args, **kwargs: paths)
    monkeypatch.setattr(recovery, "_parent_bundle", lambda *args, **kwargs: (artifact, manifest, state))
    config = {
        "recovery": {"scheduler_task": "v7-task"},
    }
    before = (target.stat().st_size, target.stat().st_mtime_ns)
    report = recovery.build_root_cause_report(config)
    after = (target.stat().st_size, target.stat().st_mtime_ns)
    assert report["classification"] == "I_UNKNOWN"
    assert Path(report["failure"]["path"]) == target.resolve()
    assert report["failure"]["operation"] == "INSERT INTO outcome_rows via _insert_outcomes"
    assert report["historical_connection_contract"]["mode_ro"] is False
    assert report["v6_mutated"] is False
    assert before == after


def test_reuse_import_accepts_only_receipted_terminal_unit_and_is_idempotent(
    tmp_path: Path,
) -> None:
    source_paths = _store_paths(tmp_path, "source")
    target_paths = _store_paths(tmp_path, "target")
    complete = _unit("unit-complete")
    partial = {**_unit("unit-partial"), "period_start": "2020-04-01", "period_end": "2020-06-30"}
    plan = {"total_planned_work_units": 2, "units": [complete, partial]}
    initialize_v6_run(
        run_manifest=_manifest("v6-parent", total=2),
        work_plan=plan,
        feature_path=source_paths["feature_store"],
        outcome_path=source_paths["outcome_store"],
        control_path=source_paths["control_store"],
    )
    feature = {
        "case_id": "case-1",
        "asset_id": "asset-1",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "dependency_status": "RESOLVED",
    }
    feature["feature_fingerprint"] = fingerprint(feature)
    outcome = {
        "case_id": "case-1",
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": "asset-1",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "status": "COMPLETE",
        "r_availability": "AVAILABLE",
        "dependency_status": "RESOLVED",
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="v6-parent",
        unit=complete,
        features=[feature],
        outcomes=[outcome],
        summary={"r_na_cases": 0, "censored_cases": 0},
        feature_path=source_paths["feature_store"],
        outcome_path=source_paths["outcome_store"],
        control_path=source_paths["control_store"],
    )
    target_manifest = {
        **_manifest("v7-target", total=2),
        "recovery_contract_fingerprint": "recovery-contract",
        "prepared_at": "2026-09-13T01:00:00+00:00",
    }
    recovery.initialize_recovery_stores(
        config={}, manifest=target_manifest, work_plan=plan, paths=target_paths
    )
    paths = {
        **target_paths,
        "parent_control_store": source_paths["control_store"],
        "parent_feature_store": source_paths["feature_store"],
        "parent_outcome_store": source_paths["outcome_store"],
    }
    config = {"parent": {"run_id": "v6-parent"}}
    first = recovery.import_verified_parent_units(
        config=config, manifest=target_manifest, paths=paths
    )
    second = recovery.import_verified_parent_units(
        config=config, manifest=target_manifest, paths=paths
    )
    assert first["reusable_from_v6"] == second["reusable_from_v6"] == 1
    assert first["must_recompute"] == 1
    assert first["parent_files_unchanged"] is True
    status = checkpoint_status(
        control_path=target_paths["control_store"], run_id="v7-target"
    )
    assert status["completed"] == 1
    assert status["pending"] == 1
    with sqlite3.connect(target_paths["control_store"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM recovery_lineage").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute(
                "UPDATE recovery_lineage SET reuse_status='VERIFIED_REUSED'"
            )
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
        assert "no_update_recovery_recomputation_lineage" in triggers
        assert "no_delete_recovery_recomputation_lineage" in triggers


def test_readonly_error_is_never_retryable() -> None:
    error = sqlite3.OperationalError("attempt to write a readonly database")
    assert runner._is_readonly_error(error) is True
    assert runner._is_retryable_runtime_error(error) is False
    assert runner._is_retryable_runtime_error(TimeoutError("temporary")) is True
    assert runner._is_retryable_runtime_error(PermissionError("denied")) is False
    from multi_asset_development_v6_execution import is_retryable_compute_error

    assert is_retryable_compute_error(error) is False


def test_scheduler_installer_keeps_v6_and_v7_tasks_separate() -> None:
    script = (
        PROJECT_ROOT / "scripts" / "install_multi_asset_development_v7_task.ps1"
    ).read_text(encoding="utf-8")
    assert "Development-v7-Recovery" in script
    assert "Development-v6-Chain" in script
    assert "Disable-ScheduledTask" in script
    assert "-MultipleInstances IgnoreNew" in script
    assert 'Repetition.Interval = "PT5M"' in script
    assert "-LogonType Interactive" in script
    assert "-RunLevel Limited" in script
    assert "-WorkingDirectory $projectRoot" in script
    assert "Unregister-ScheduledTask" in script


def test_v7_config_closes_every_later_stage() -> None:
    config = recovery.load_recovery_config()
    safety = config["safety"]
    assert safety["development_only"] is True
    assert all(value is False for key, value in safety.items() if key != "development_only")
    assert config["recovery"]["worker_count"] == 4
    assert config["recovery"]["sqlite_writer_count"] == 1
