from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

import multi_asset_development_v6_runner as runner
import multi_asset_development_v6_audit as audit_module
import multi_asset_development_v6_reporting as reporting_module
from multi_asset_discovery_v1 import fingerprint


def _contract() -> dict[str, object]:
    return {
        "contract_version": "v6",
        "contract_fingerprint": "contract-fp",
        "reprocessing_parent": {"run_id": "v5-run"},
        "reference_fingerprints": {
            "combined_input_fingerprint": "input-fp",
            "equity_etf_projection_fingerprint": "equity-fp",
            "crypto_projection_fingerprint": "crypto-fp",
            "fx_projection_fingerprint": "fx-fp",
            "input_precheck_artifact_fingerprint": "precheck-fp",
            "worker_benchmark_artifact_fingerprint": "benchmark-fp",
            "descriptive_plan_artifact_fingerprint": "plan-fp",
            "development_code_fingerprint": "code-fp",
            "identity_registry_fingerprint": "identity-fp",
            "historical_dependency_policy_fingerprint": "dependency-fp",
        },
        "development_execution": {
            "research_epoch": "epoch-v6",
            "worker_count": 4,
            "sqlite_writer_count": 1,
            "scheduler_task_name": "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain",
            "production_protection_config": "config/swing_walk_forward_campaign.json",
        },
    }


def test_run_manifest_closes_every_unseen_and_trading_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "_git",
        lambda *args: "codex/multi-asset-development-v6"
        if args[0] == "branch"
        else "abc123",
    )
    manifest = runner.build_run_manifest(
        contract=_contract(),
        contract_artifact={"artifact_fingerprint": "artifact-fp"},
        universe={"universe_fingerprint": "universe-fp"},
        work_plan={"work_plan_fingerprint": "work-fp", "total_planned_work_units": 24},
        started_at="2026-09-05T18:00:00+00:00",
    )
    assert manifest["worker_count"] == 4
    assert manifest["sqlite_writer_count"] == 1
    assert manifest["development_only"] is True
    for key in (
        "validation_opened",
        "holdout_opened",
        "external_opened",
        "forward_opened",
        "paper_opened",
        "shadow_opened",
        "broker_opened",
        "automatic_orders_allowed",
    ):
        assert manifest[key] is False
    expected = manifest.pop("run_manifest_fingerprint")
    assert expected == fingerprint(manifest)


def test_chain_state_is_persistent_and_operator_pause_is_cooperative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner, "_git", lambda *args: "abc123")
    path = tmp_path / "state.json"
    state = runner.load_chain_state(path, _contract())
    assert state["phase"] == "PRECHECK"
    paused = runner.set_operator_request(chain_state_path=path, request="PAUSE")
    assert paused["pause_requested"] is True
    assert paused["status"] == "PAUSED_REQUIRES_REVIEW"
    # A runner holding an older in-memory state must not erase a concurrent
    # cooperative request when it checkpoints progress.
    stale_runner_state = dict(state)
    checkpointed = runner.update_chain_state(
        path,
        stale_runner_state,
        phase="RUN",
        next_allowed_action="resume later",
    )
    assert checkpointed["pause_requested"] is True
    assert checkpointed["status"] == "PAUSED_REQUIRES_REVIEW"
    resumed = runner.set_operator_request(chain_state_path=path, request=None)
    assert resumed["pause_requested"] is False
    assert resumed["stop_requested"] is False
    assert resumed["status"] == "RUNNING"
    # The CLI never rewrites a possibly newer chain checkpoint.  RESUME is
    # overlaid from its own durable request artifact instead.
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["status"] == "PAUSED_REQUIRES_REVIEW"
    assert runner.read_chain_status(path)["status"] == "RUNNING"


def test_start_gate_must_be_self_valid_pass_and_match_contract(tmp_path: Path) -> None:
    path = tmp_path / "gate.json"
    gate = {
        "version": runner.START_GATE_VERSION,
        "status": "PASS",
        "start_authorized": True,
        "blockers": [],
        "development_contract_fingerprint": "contract-fp",
        "gates": {name: "PASS" for name in runner.TOP_LEVEL_GATES},
    }
    gate["artifact_fingerprint"] = fingerprint(gate)
    path.write_text(json.dumps(gate), encoding="utf-8")
    assert runner._load_required_start_gate(
        path, contract_fingerprint="contract-fp"
    )["status"] == "PASS"
    gate["gates"][runner.TOP_LEVEL_GATES[0]] = "FAIL"
    gate["artifact_fingerprint"] = fingerprint(
        {key: value for key, value in gate.items() if key != "artifact_fingerprint"}
    )
    path.write_text(json.dumps(gate), encoding="utf-8")
    with pytest.raises(runner.DevelopmentV6RunnerError, match="not PASS"):
        runner._load_required_start_gate(path, contract_fingerprint="contract-fp")


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda gate: gate.__setitem__("start_authorized", False), "authorize"),
        (lambda gate: gate.__setitem__("blockers", ["BLOCKED"]), "blockers"),
        (
            lambda gate: gate["gates"].pop(runner.TOP_LEVEL_GATES[-1]),
            "exact required gate groups",
        ),
        (
            lambda gate: gate["gates"].__setitem__("UNEXPECTED", "PASS"),
            "exact required gate groups",
        ),
    ),
)
def test_start_gate_requires_explicit_authorization_no_blockers_and_exact_groups(
    tmp_path: Path, mutation, message: str
) -> None:
    path = tmp_path / "gate.json"
    gate = {
        "version": runner.START_GATE_VERSION,
        "status": "PASS",
        "start_authorized": True,
        "blockers": [],
        "development_contract_fingerprint": "contract-fp",
        "gates": {name: "PASS" for name in runner.TOP_LEVEL_GATES},
    }
    mutation(gate)
    gate["artifact_fingerprint"] = fingerprint(gate)
    path.write_text(json.dumps(gate), encoding="utf-8")

    with pytest.raises(runner.DevelopmentV6RunnerError, match=message):
        runner._load_required_start_gate(path, contract_fingerprint="contract-fp")


def test_advance_without_start_gate_has_no_persistent_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    paths = {
        name: tmp_path / f"{name}.artifact"
        for name in (
            "start_gate",
            "chain_state",
            "manifest",
            "feature",
            "outcome",
            "control",
            "lock",
        )
    }
    monkeypatch.setattr(runner, "load_development_v6_contract", lambda: contract)
    monkeypatch.setattr(runner, "contract_paths", lambda value: paths)

    result = runner.advance_chain()

    assert result["status"] == "BLOCKED_BEFORE_START"
    assert result["phase"] == "PRECHECK"
    assert result["run_id"] is None
    assert result["chain_state_created"] is False
    assert result["development_run_started"] is False
    assert result["blocker"] == (
        "START_GATE_PRECHECK_FAILED:DevelopmentV6RunnerError"
    )
    assert not paths["chain_state"].exists()
    assert not paths["manifest"].exists()
    assert not paths["feature"].exists()
    assert not paths["outcome"].exists()
    assert not paths["control"].exists()
    assert not paths["lock"].exists()
    assert not runner._operator_request_path(paths["chain_state"]).exists()


def test_concurrent_first_start_does_not_create_or_overwrite_chain_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    paths = {
        "start_gate": tmp_path / "start-gate.json",
        "chain_state": tmp_path / "chain-state.json",
        "lock": tmp_path / "runner.lock",
    }

    class _ConcurrentProcessLock:
        def __init__(self, path: Path) -> None:
            assert path == paths["lock"]

        def acquire(self) -> None:
            raise runner.SwingRunAlreadyActiveError("already active")

        def release(self) -> None:
            raise AssertionError("A lock that was not acquired must not be released.")

    monkeypatch.setattr(runner, "load_development_v6_contract", lambda: contract)
    monkeypatch.setattr(runner, "contract_paths", lambda value: paths)
    monkeypatch.setattr(
        runner, "_load_required_start_gate", lambda *args, **kwargs: {"status": "PASS"}
    )
    monkeypatch.setattr(runner, "SwingRunLock", _ConcurrentProcessLock)
    monkeypatch.setattr(
        runner,
        "load_chain_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("The duplicate must not create initial chain state.")
        ),
    )

    result = runner.advance_chain()

    assert result["status"] == "NOT_STARTED"
    assert result["duplicate_start_rejected"] is True
    assert not paths["chain_state"].exists()
    assert not runner._operator_request_path(paths["chain_state"]).exists()


def test_runtime_code_provenance_rehashes_frozen_files_and_detects_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    implementation = tmp_path / "worker.py"
    implementation.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    from multi_asset_development_v6_inputs import build_v6_implementation_provenance

    frozen = build_v6_implementation_provenance(
        [implementation], project_root=tmp_path
    )
    input_payload: dict[str, object] = {
        "status": "PASS",
        "implementation_paths": frozen["implementation_paths"],
        "implementation_sha256": frozen["implementation_sha256"],
        "contract_inputs": {
            "implementation_fingerprint": frozen["implementation_fingerprint"]
        },
    }
    input_payload["artifact_fingerprint"] = fingerprint(input_payload)
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    gate: dict[str, object] = {
        "version": runner.START_GATE_VERSION,
        "status": "PASS",
        "start_authorized": True,
        "blockers": [],
        "development_contract_fingerprint": "contract-fp",
        "gates": {name: "PASS" for name in runner.TOP_LEVEL_GATES},
        "git_provenance": {"head": "abc123"},
        "implementation_code_audit": {
            "current_implementation_fingerprint": frozen[
                "implementation_fingerprint"
            ]
        },
    }
    gate["artifact_fingerprint"] = fingerprint(gate)
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    paths = {
        "input_precheck": input_path,
        "start_gate": gate_path,
        "manifest": manifest_path,
    }
    contract = {
        "contract_fingerprint": "contract-fp",
        "reference_fingerprints": {
            "development_code_fingerprint": frozen["implementation_fingerprint"]
        },
    }

    def fake_git(*args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "abc123"
        if args[:2] == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git", fake_git)
    result = runner._verify_runtime_code_provenance(
        contract=contract, paths=paths
    )
    assert result["status"] == "PASS"

    implementation.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(runner.DevelopmentV6RunnerError, match="provenance drift"):
        runner._verify_runtime_code_provenance(contract=contract, paths=paths)


def test_operator_request_is_request_file_only_and_preserves_newer_phase(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner, "_git", lambda *args: "abc123")
    path = tmp_path / "state.json"
    state = runner.load_chain_state(path, _contract())
    state["phase"] = "FINAL_AUDIT"
    state["last_successful_work_unit"] = "unit-42"
    path.write_text(json.dumps(state), encoding="utf-8")
    before = path.read_bytes()

    effective = runner.set_operator_request(
        chain_state_path=path, request="PAUSE"
    )

    assert path.read_bytes() == before
    assert effective["phase"] == "FINAL_AUDIT"
    assert effective["last_successful_work_unit"] == "unit-42"
    assert effective["status"] == "PAUSED_REQUIRES_REVIEW"


def test_resource_guard_yields_before_dispatch_when_disk_reserve_is_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=100, used=99, free=1024),
    )
    monkeypatch.setattr(
        runner,
        "system_resources",
        lambda: {"available_physical_memory_bytes_at_start": 8 * 1024**3},
    )
    clear, reason, detail = runner.dispatch_readiness(_contract())
    assert clear is False
    assert reason == "DISK_RESERVE_BELOW_30_GIB"
    assert detail["disk_free_bytes"] == 1024


def test_resource_guard_respects_active_production_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=100, used=10, free=40 * 1024**3),
    )
    monkeypatch.setattr(
        runner,
        "system_resources",
        lambda: {"available_physical_memory_bytes_at_start": 8 * 1024**3},
    )
    monkeypatch.setattr(runner, "load_campaign_config", lambda path: {})
    monkeypatch.setattr(
        runner,
        "historical_research_runtime_gate",
        lambda config, project_root: {
            "run_allowed": False,
            "reason": "BLOCKED_REAL_CONFLICT",
            "active_production": ["live"],
        },
    )
    clear, reason, _ = runner.dispatch_readiness(_contract())
    assert clear is False
    assert reason == "BLOCKED_REAL_CONFLICT:live"


def test_resource_guard_marks_fx_observer_as_non_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=100, used=10, free=40 * 1024**3),
    )
    monkeypatch.setattr(
        runner,
        "system_resources",
        lambda: {"available_physical_memory_bytes_at_start": 8 * 1024**3},
    )
    monkeypatch.setattr(runner, "load_campaign_config", lambda path: {})
    monkeypatch.setattr(
        runner,
        "historical_research_runtime_gate",
        lambda config, project_root: {
            "run_allowed": True,
            "reason": "CLEAR",
            "active_production": [],
        },
    )

    clear, reason, detail = runner.dispatch_readiness(_contract())

    assert clear is True
    assert reason == "CLEAR"
    assert detail["fx_observer"]["blocking"] is False


def test_no_data_worker_result_must_name_exact_claimed_units(tmp_path: Path) -> None:
    manifest = {"run_id": "run"}
    units = [
        {"work_unit_id": "u1", "asset_key": "CRYPTO:APT"},
        {"work_unit_id": "u2", "asset_key": "CRYPTO:APT"},
    ]
    with pytest.raises(runner.DevelopmentV6RunnerError, match="incomplete unit"):
        runner._process_result(
            result={
                "asset_key": "CRYPTO:APT",
                "skip_reason_code": "EXPECTED_NO_DEVELOPMENT_DATA",
                "skip_reason": "none",
                # Set equality would accept this duplicate-bearing sequence.
                # The worker contract requires the exact claimed sequence.
                "unit_ids": ["u1", "u1", "u2"],
            },
            units=units,
            manifest=manifest,
            paths={},
            writer_pid=1,
        )


def test_terminal_chain_uses_exact_audit_report_and_summary_contracts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    paths = {
        name: tmp_path / f"{name}.json"
        for name in (
            "chain_state",
            "manifest",
            "audit",
            "plan",
            "report",
                "summary",
                "contract_artifact",
                "input_precheck",
                "start_gate",
                "lock",
            "feature",
            "outcome",
            "control",
        )
    }
    manifest = {"run_id": "run-v6"}
    plan = {"artifact_fingerprint": "plan-fp"}
    paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    paths["plan"].write_text(json.dumps(plan), encoding="utf-8")
    paths["contract_artifact"].write_text("{}", encoding="utf-8")
    state = {
        "version": runner.CHAIN_VERSION,
        "phase": "FINAL_AUDIT",
        "status": "RUNNING",
        "contract_fingerprint": contract["contract_fingerprint"],
        "pause_requested": False,
        "stop_requested": False,
        "phases": {},
    }
    paths["chain_state"].write_text(json.dumps(state), encoding="utf-8")

    class _Lock:
        def __init__(self, path: Path) -> None:
            self.path = path

        def acquire(self) -> None:
            return None

        def release(self) -> None:
            return None

    calls: dict[str, dict[str, object]] = {}

    def fake_audit(**kwargs: object) -> dict[str, object]:
        calls["audit"] = kwargs
        payload = {
            "status": "PASS",
            "run_id": "run-v6",
            "artifact_fingerprint": "audit-fp",
        }
        Path(kwargs["artifact_path"]).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def fake_report(**kwargs: object) -> dict[str, object]:
        calls["report"] = kwargs
        payload = {
            "status": "DESCRIPTIVE_COMPLETE",
            "run_id": "run-v6",
            "artifact_fingerprint": "report-fp",
        }
        Path(kwargs["artifact_path"]).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def fake_summary(**kwargs: object) -> dict[str, object]:
        calls["summary"] = kwargs
        payload = {
            "status": "COMPLETED_AUDITED_AWAITING_REVIEW",
            "run_id": "run-v6",
            "artifact_fingerprint": "summary-fp",
        }
        Path(kwargs["artifact_path"]).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(runner, "load_development_v6_contract", lambda: contract)
    monkeypatch.setattr(runner, "contract_paths", lambda value: paths)
    monkeypatch.setattr(
        runner, "_load_required_start_gate", lambda *args, **kwargs: {"status": "PASS"}
    )
    monkeypatch.setattr(runner, "SwingRunLock", _Lock)
    monkeypatch.setattr(
        runner, "_verify_runtime_code_provenance", lambda **kwargs: {"status": "PASS"}
    )
    monkeypatch.setattr(
        runner,
        "checkpoint_status",
        lambda **kwargs: {
            "run_id": "run-v6",
            "status": "COMPLETED",
            "total_planned_work_units": 1,
        },
    )
    monkeypatch.setattr(
        runner, "_rebuild_expected_work_plan", lambda value: ({}, {"units": []})
    )
    monkeypatch.setattr(
        runner, "_prefreeze_contract_basis_fingerprint", lambda: "basis-fp"
    )
    monkeypatch.setattr(audit_module, "build_v6_full_audit", fake_audit)
    monkeypatch.setattr(reporting_module, "build_v6_descriptive_report", fake_report)
    monkeypatch.setattr(reporting_module, "build_v6_completion_summary", fake_summary)

    final_state = runner.advance_chain()

    assert final_state["phase"] == "STOP"
    assert final_state["status"] == "COMPLETED_AUDITED_AWAITING_REVIEW"
    assert calls["audit"]["run_id"] == "run-v6"
    assert calls["audit"]["expected_work_plan"] == {"units": []}
    assert calls["audit"]["expected_run_manifest"] == manifest
    assert calls["audit"]["final_contract"] == paths["contract_artifact"]
    assert calls["audit"]["input_precheck"] == paths["input_precheck"]
    assert calls["report"]["final_contract"] == paths["contract_artifact"]
    assert calls["report"]["expected_contract_basis_fingerprint"] == "basis-fp"
    assert calls["summary"]["frozen_plan"] == plan


@pytest.mark.parametrize("phase", ["FINAL_AUDIT", "DESCRIPTIVE_REPORT", "SUMMARY"])
def test_terminal_phase_exception_persists_review_pause(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str
) -> None:
    contract = _contract()
    paths = {
        name: tmp_path / f"{name}.json"
        for name in (
            "chain_state",
            "manifest",
            "audit",
            "plan",
            "report",
            "summary",
                "contract_artifact",
                "input_precheck",
                "benchmark",
                "start_gate",
                "lock",
            "feature",
            "outcome",
            "control",
        )
    }
    state = {
        "version": runner.CHAIN_VERSION,
        "phase": phase,
        "status": "RUNNING",
        "contract_fingerprint": contract["contract_fingerprint"],
        "pause_requested": False,
        "stop_requested": False,
        "phases": {},
    }
    paths["chain_state"].write_text(json.dumps(state), encoding="utf-8")

    class _Lock:
        def __init__(self, path: Path) -> None:
            self.path = path

        def acquire(self) -> None:
            return None

        def release(self) -> None:
            return None

    def fail(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("terminal phase exploded")

    monkeypatch.setattr(runner, "load_development_v6_contract", lambda: contract)
    monkeypatch.setattr(runner, "contract_paths", lambda value: paths)
    monkeypatch.setattr(
        runner, "_load_required_start_gate", lambda *args, **kwargs: {"status": "PASS"}
    )
    monkeypatch.setattr(runner, "SwingRunLock", _Lock)
    monkeypatch.setattr(
        runner, "_verify_runtime_code_provenance", lambda **kwargs: {"status": "PASS"}
    )
    monkeypatch.setattr(runner, "_build_final_audit_phase", fail)
    monkeypatch.setattr(runner, "_build_descriptive_report_phase", fail)
    monkeypatch.setattr(runner, "_build_completion_summary_phase", fail)

    result = runner.advance_chain()

    assert result["phase"] == phase
    assert result["status"] == "PAUSED_REQUIRES_REVIEW"
    assert result["blocker"] == f"{phase}_EXCEPTION:RuntimeError"
    persisted = json.loads(paths["chain_state"].read_text(encoding="utf-8"))
    assert persisted["status"] == "PAUSED_REQUIRES_REVIEW"
    assert persisted["phases"][phase]["status"] == "EXCEPTION"


def test_transient_worker_failure_backs_off_until_next_scheduler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unit = {
        "work_unit_id": "u1",
        "asset_key": "EQUITIES:AAA",
        "asset_class": "EQUITIES",
        "symbol": "AAA",
    }
    contract = {
        "development_execution": {
            "worker_count": 1,
            "maximum_attempts_per_work_unit": 3,
        }
    }
    paths = {
        name: tmp_path / name
        for name in ("control", "log", "chain_state", "input_precheck")
    }
    claim_calls = 0

    def claim(**kwargs: object) -> list[dict[str, object]]:
        nonlocal claim_calls
        claim_calls += 1
        return [unit]

    def transient_compute(**kwargs: object) -> dict[str, object]:
        raise TimeoutError("temporary")

    monkeypatch.setattr(
        runner,
        "prepare_canonical_run",
        lambda contract, paths: (
            {"run_id": "run-v6"},
            {"assets": [{"asset_key": "EQUITIES:AAA"}]},
            {},
        ),
    )
    monkeypatch.setattr(
        runner,
        "checkpoint_status",
        lambda **kwargs: {"run_id": "run-v6", "status": "RUNNING"},
    )
    monkeypatch.setattr(runner, "reset_interrupted_units", lambda **kwargs: 0)
    monkeypatch.setattr(runner, "append_run_event", lambda **kwargs: None)
    monkeypatch.setattr(runner, "dispatch_readiness", lambda contract: (True, "CLEAR", {}))
    monkeypatch.setattr(runner, "claim_next_asset_batch", claim)
    monkeypatch.setattr(runner, "compute_v6_asset_batch", transient_compute)
    monkeypatch.setattr(runner, "is_retryable_compute_error", lambda exc: True)
    monkeypatch.setattr(runner, "fail_asset_batch", lambda **kwargs: "RETRY")
    monkeypatch.setattr(runner, "mark_run_complete", lambda **kwargs: False)
    monkeypatch.setattr(runner, "_set_below_normal_priority", lambda: True)

    result = runner.run_development_compute(
        contract=contract,
        paths=paths,
        executor_factory=ThreadPoolExecutor,
    )

    assert claim_calls == 1
    assert result["yield_reason"] == "TRANSIENT_ERROR_BACKOFF_TO_NEXT_SCHEDULER"
    assert result["asset_batches_dispatched_this_invocation"] == 1
