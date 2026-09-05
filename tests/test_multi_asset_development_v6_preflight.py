from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from multi_asset_development_v6_contract import (
    DEFAULT_V6_CONFIG_PATH,
    DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
    DEVELOPMENT_V6_CONTRACT_DIFF_VERSION,
    DEVELOPMENT_V6_CONTRACT_VERSION,
    build_development_v6_benchmark_contract,
)
from multi_asset_development_v6_benchmark import (
    BENCHMARK_VERSION,
    REQUIRED_TECHNICAL_COVERAGE_GATES,
    classify_worker_configurations,
    configuration_evidence_checks,
)
from multi_asset_development_v6_inputs import INPUT_PRECHECK_VERSION
from multi_asset_development_v6_reporting import PLAN_VERSION
from multi_asset_development_v6_preflight import (
    DevelopmentV6PreflightError,
    REQUIRED_LOCAL_GATES,
    START_GATE_VERSION,
    build_start_gate,
)
from multi_asset_discovery_v1 import file_sha256, fingerprint


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _fingerprinted(
    payload: dict[str, object], field: str = "artifact_fingerprint"
) -> dict[str, object]:
    result = dict(payload)
    result[field] = fingerprint(result)
    return result


def _benchmark_configuration(worker_count: int) -> dict[str, object]:
    return {
        "worker_count": worker_count,
        "status": "PASS",
        "wall_seconds": 10.0 / worker_count,
        "throughput_cases_per_second": 10.0 * worker_count,
        "case_count": 40,
        "asset_result_count": 4,
        "work_unit_count": 8,
        "receipt_count": 8,
        "peak_ram_upper_bound_bytes": 1024,
        "worker_process_count_observed": worker_count,
        "worker_cpu_seconds": 1.0,
        "parent_cpu_seconds": 0.1,
        "aggregate_cpu_utilization_pct_of_one_logical_cpu": 50.0,
        "aggregate_cpu_utilization_pct_of_available_worker_capacity": 25.0,
        "central_writer_elapsed_seconds": 0.1,
        "central_writer_pid": 123,
        "central_writer_transaction_count": 8,
        "writer_wait_seconds_total": 0.0,
        "writer_wait_seconds_max": 0.0,
        "errors": [],
        "retries": 0,
        "scientific_digest": fingerprint("same-scientific-output"),
        "worker_result_digest_check_count": 4,
        "worker_result_digests_verified": True,
        "sqlite_writer_count": 1,
        "technical_coverage_gates": {
            name: True for name in REQUIRED_TECHNICAL_COVERAGE_GATES
        },
    }


def _fixture(root: Path) -> dict[str, object]:
    for relative in (
        "runtime/v5_features.sqlite3",
        "runtime/v5_outcomes.sqlite3",
        "runtime/v5_control.sqlite3",
        "runtime/equity.sqlite3",
        "runtime/crypto.sqlite3",
        "runtime/fx.sqlite3",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-store")

    implementation_paths = (root / "code/a.py", root / "code/b.py")
    for index, path in enumerate(implementation_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"VALUE = {index}\n", encoding="utf-8")
    implementation_hashes = {
        path.resolve().as_posix(): file_sha256(path) for path in implementation_paths
    }
    implementation_fingerprint = fingerprint(implementation_hashes)

    source_path = root / "runtime/dataset-manifest.json"
    source_path.write_text('{"frozen":true}\n', encoding="utf-8")
    source_hash = file_sha256(source_path)

    parent_contract = {
        "contract_version": "multi-asset-opportunity-discovery-development-2026.09.01-v5",
        "store_contract": {
            "feature_store": "runtime/v5_features.sqlite3",
            "outcome_store": "runtime/v5_outcomes.sqlite3",
            "control_store": "runtime/v5_control.sqlite3",
        },
        "lifecycle": {
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
        },
    }
    parent_contract["contract_fingerprint"] = fingerprint(parent_contract)
    parent_artifact = _fingerprinted(
        {
            "version": "multi-asset-development-contract-artifact-2026.09.01-v5",
            "contract": parent_contract,
            "contract_fingerprint": parent_contract["contract_fingerprint"],
        }
    )
    parent_artifact_path = root / "runtime/parent.json"
    _write(parent_artifact_path, parent_artifact)
    parent_manifest = _fingerprinted(
        {
            "version": "multi-asset-discovery-development-run-manifest-2026.09.01-v5",
            "run_id": "v5-run",
            "development_contract_fingerprint": parent_contract["contract_fingerprint"],
        },
        "run_manifest_fingerprint",
    )
    parent_manifest_path = root / "runtime/parent-manifest.json"
    _write(parent_manifest_path, parent_manifest)
    parent_spec = {
        "artifact_path": "runtime/parent.json",
        "artifact_sha256": file_sha256(parent_artifact_path),
        "artifact_version": parent_artifact["version"],
        "artifact_fingerprint": parent_artifact["artifact_fingerprint"],
        "contract_version": parent_contract["contract_version"],
        "contract_fingerprint": parent_contract["contract_fingerprint"],
        "run_manifest_path": "runtime/parent-manifest.json",
        "run_manifest_sha256": file_sha256(parent_manifest_path),
        "run_manifest_version": parent_manifest["version"],
        "run_manifest_fingerprint": parent_manifest["run_manifest_fingerprint"],
        "run_id": parent_manifest["run_id"],
    }

    contract_inputs = {
        key: fingerprint({"test_input": key})
        for key in (
            "combined_input_fingerprint",
            "equity_etf_projection_fingerprint",
            "crypto_projection_fingerprint",
            "fx_projection_fingerprint",
            "equity_etf_store_sha256",
            "crypto_store_sha256",
            "fx_store_sha256",
            "source_dataset_manifest_sha256",
            "identity_store_sha256",
            "identity_registry_fingerprint",
            "gap_policy_fingerprint",
        )
    }
    contract_inputs["implementation_fingerprint"] = implementation_fingerprint
    input_payload = _fingerprinted(
        {
            "version": INPUT_PRECHECK_VERSION,
            "status": "PASS",
            "contract_inputs": contract_inputs,
            "implementation_sha256": implementation_hashes,
            "checks": {"whole_universe": True, "ohlc_valid": True},
            "source_sha256_before": {"dataset_manifest": source_hash},
            "source_sha256_after": {"dataset_manifest": source_hash},
            "source_paths": {
                "dataset_manifest": {
                    "root": "INPUT_PRECHECK_PARENT",
                    "relative_path": "dataset-manifest.json",
                }
            },
            "no_downloads": True,
            "no_clipping": True,
            "no_imputation": True,
            "no_interpolation": True,
            "development_run_started": False,
        }
    )
    input_path = root / "runtime/input.json"
    _write(input_path, input_payload)
    benchmark_configurations = [
        _benchmark_configuration(worker_count) for worker_count in (1, 2, 4)
    ]
    benchmark_configuration_checks = {
        str(item["worker_count"]): configuration_evidence_checks(item)
        for item in benchmark_configurations
    }
    benchmark_classification = classify_worker_configurations(
        benchmark_configurations
    )
    benchmark = _fingerprinted(
        {
            "version": BENCHMARK_VERSION,
            "status": "PASS",
            "input_precheck_fingerprint": input_payload["artifact_fingerprint"],
            "combined_input_fingerprint": input_payload["contract_inputs"][
                "combined_input_fingerprint"
            ],
            "scientific_parent_contract_fingerprint": parent_contract[
                "contract_fingerprint"
            ],
            "deterministic_payloads_equal": True,
            "resources": {
                "logical_cpu_count": 4,
                "total_physical_memory_bytes": 16 * 1024**3,
            },
            "configurations": benchmark_configurations,
            "configuration_evidence_checks": benchmark_configuration_checks,
            "all_configuration_evidence_complete": True,
            "benchmark_completed": True,
            "protected_runtime_checks_before_each_configuration": [
                {
                    "worker_count": worker_count,
                    "status": "PASS",
                    "reason": "CLEAR",
                    "detail": {},
                }
                for worker_count in (1, 2, 4)
            ],
            "exclusive_benchmark_process_lock_held": True,
            "global_research_lock_held": True,
            "reference_worker_count": 1,
            "reference_configuration_count": 1,
            "reference_configuration_passed": True,
            "reference_scientific_digest": benchmark_classification[
                "reference_scientific_digest"
            ],
            "configuration_decisions": benchmark_classification[
                "configuration_decisions"
            ],
            "selection_candidate_worker_counts": benchmark_classification[
                "selection_candidate_worker_counts"
            ],
            "excluded_multi_worker_configurations": [],
            "all_tested_payloads_equal_to_reference": True,
            "all_selection_candidates_identical_to_reference": True,
            "selected_worker_count": 4,
            "selected_digest_matches_one_worker_reference": True,
            "fallback_to_one_worker": False,
            "fallback_reasons": [],
            "multi_worker_instability_is_not_a_start_blocker": True,
            "sqlite_writer_count": 1,
            "selection_used_outcomes": False,
        }
    )
    benchmark_path = root / "runtime/benchmark.json"
    _write(benchmark_path, benchmark)
    config = json.loads(DEFAULT_V6_CONFIG_PATH.read_text(encoding="utf-8"))
    config["parent_reprocessing"] = parent_spec
    required = config["required_runtime_artifacts"]
    required["input_precheck"].update(
        {"path": "runtime/input.json", "version": INPUT_PRECHECK_VERSION, "status": "PASS"}
    )
    required["worker_benchmark"].update(
        {"path": "runtime/benchmark.json", "version": BENCHMARK_VERSION, "status": "PASS"}
    )
    required["descriptive_plan"].update(
        {"path": "runtime/plan.json", "version": PLAN_VERSION, "status": "FROZEN"}
    )
    config_path = root / "config/v6.json"
    _write(config_path, config)
    expected_contract_basis = fingerprint(
        build_development_v6_benchmark_contract(
            config_path=config_path,
            project_root=root,
            input_precheck_path=input_path,
        )
    )
    plan = _fingerprinted(
        {
            "version": PLAN_VERSION,
            "status": "FROZEN",
            "created_at": "2026-09-05T17:00:00+02:00",
            "combined_input_fingerprint": input_payload["contract_inputs"][
                "combined_input_fingerprint"
            ],
            "contract_basis_fingerprint": expected_contract_basis,
            "inferential_claims_allowed": False,
            "selection_or_optimization_allowed": False,
        }
    )
    plan_path = root / "runtime/plan.json"
    _write(plan_path, plan)
    benchmark.pop("artifact_fingerprint")
    benchmark.update(
        {
            "created_at": "2026-09-05T18:00:00+02:00",
            "descriptive_plan_artifact_fingerprint": plan[
                "artifact_fingerprint"
            ],
            "descriptive_plan_created_at": plan["created_at"],
        }
    )
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write(benchmark_path, benchmark)

    contract = {
        "contract_version": DEVELOPMENT_V6_CONTRACT_VERSION,
        "reprocessing_parent": parent_spec,
        "reference_fingerprints": {
            "combined_input_fingerprint": input_payload["contract_inputs"][
                "combined_input_fingerprint"
            ],
            "input_precheck_artifact_fingerprint": input_payload[
                "artifact_fingerprint"
            ],
            "worker_benchmark_artifact_fingerprint": benchmark[
                "artifact_fingerprint"
            ],
            "descriptive_plan_artifact_fingerprint": plan["artifact_fingerprint"],
            "development_code_fingerprint": implementation_fingerprint,
        },
        "store_contract": {
            "feature_store": "runtime/v6_features.sqlite3",
            "outcome_store": "runtime/v6_outcomes.sqlite3",
            "control_store": "runtime/v6_control.sqlite3",
        },
        "development_execution": {
            "worker_count": 4,
            "sqlite_writer_count": 1,
            "run_manifest": "runtime/v6-manifest.json",
            "chain_state": "runtime/v6-state.json",
            "readiness_artifact": "runtime/start-gate.json",
            "final_audit_artifact": "runtime/audit.json",
            "descriptive_report_artifact": "runtime/report.json",
            "completion_summary_artifact": "runtime/summary.json",
            "scheduler_wrapper": "scripts/run_multi_asset_development_v6_chain.cmd",
            "scheduler_task_name": "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain",
            "input_precheck_artifact": "runtime/input.json",
            "worker_benchmark_artifact": "runtime/benchmark.json",
            "descriptive_plan_artifact": "runtime/plan.json",
        },
    }
    contract["contract_fingerprint"] = fingerprint(contract)
    diff = _fingerprinted(
        {
            "version": DEVELOPMENT_V6_CONTRACT_DIFF_VERSION,
            "status": "PASS",
            "parent_fingerprint": parent_contract["contract_fingerprint"],
            "development_fingerprint": contract["contract_fingerprint"],
            "differences": [{"path": "contract_version", "authorized": True}],
            "semantic_invariant_failure_count": 0,
            "unauthorized_research_semantics_count": 0,
            "research_semantics_diff_count": 0,
        },
        "diff_fingerprint",
    )
    diff_path = root / "runtime/v6-diff.json"
    _write(diff_path, diff)
    contract_artifact = _fingerprinted(
        {
            "version": DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
            "contract": contract,
            "contract_fingerprint": contract["contract_fingerprint"],
            "parent_diff_fingerprint": diff["diff_fingerprint"],
            "runtime_input_artifacts": {
                "input_precheck": {
                    "path": "runtime/input.json",
                    "version": INPUT_PRECHECK_VERSION,
                    "status": "PASS",
                    "artifact_fingerprint": input_payload["artifact_fingerprint"],
                },
                "worker_benchmark": {
                    "path": "runtime/benchmark.json",
                    "version": BENCHMARK_VERSION,
                    "status": "PASS",
                    "artifact_fingerprint": benchmark["artifact_fingerprint"],
                },
                "descriptive_plan": {
                    "path": "runtime/plan.json",
                    "version": PLAN_VERSION,
                    "status": "FROZEN",
                    "artifact_fingerprint": plan["artifact_fingerprint"],
                },
            },
            "unauthorized_research_semantics_count": 0,
            "research_semantics_diff_count": 0,
            "full_development_run_authorized": True,
            "development_run_started": False,
            "development_code_fingerprint": implementation_fingerprint,
            "git": {"branch": "codex/v6", "commit": "b" * 40},
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
            "true_forward_opened": False,
            "paper_opened": False,
            "shadow_opened": False,
            "broker_opened": False,
        }
    )
    contract_path = root / "runtime/v6-contract.json"
    _write(contract_path, contract_artifact)

    resources = {
        "logical_cpu_count": 12,
        "total_physical_memory_bytes": 16 * 1024**3,
        "available_physical_memory_bytes_at_start": 8 * 1024**3,
        "disk_free_bytes": 80 * 1024**3,
        "required_free_before_start_bytes": 55 * 1024**3,
        "projection_store_paths": [
            {"path": f"runtime/p{index}.sqlite3", "exists": True, "bytes": 100}
            for index in range(3)
        ],
        "v5_store_paths": [
            {"path": f"runtime/v5-{index}.sqlite3", "exists": True, "bytes": 100}
            for index in range(3)
        ],
        "new_v6_store_estimate_bytes": 20 * 1024**3,
        "wal_temporary_spool_reserve_bytes": 5 * 1024**3,
    }
    environment = {
        "captured_at": "2026-09-05T20:00:00+02:00",
        "resources": resources,
        "python": {
            "project_venv_exists": True,
            "running_from_project_venv": True,
            "supported_version": True,
            "running_executable": "C:/project/.venv/Scripts/python.exe",
            "project_venv_executable": "C:/project/.venv/Scripts/python.exe",
            "version": "3.12.1",
        },
        "git": {
            "branch": "codex/v6",
            "head": "b" * 40,
            "tracked_worktree_clean": True,
            "upstream": "origin/codex/v6",
            "ahead": 0,
            "behind": 0,
            "errors": {},
        },
    }
    local = {
        name: {
            "status": "PASS",
            "exit_code": 0,
            "command": f"command for {name}",
            "evidence": f"verified {name}",
            "commit": "b" * 40,
            "completed_at": "2026-09-05T19:59:00+02:00",
            "skipped_by_preflight": False,
        }
        for name in REQUIRED_LOCAL_GATES
    }
    ci = {
        "status": "SUCCESS",
        "commit": "b" * 40,
        "checked_at": "2026-09-05T20:00:00+02:00",
        "workflow": "Smoke Test / smoke",
        "evidence": "https://github.invalid/run/1",
    }
    scheduler = {
        "status": "INSTALLED",
        "task_exists": True,
        "task_count": 1,
        "enabled": True,
        "repetition_interval_minutes": 5,
        "repetition_duration_days": 3650,
        "task_name": "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain",
        "wrapper": "scripts/run_multi_asset_development_v6_chain.cmd",
        "multiple_instances": "IgnoreNew",
        "start_when_available": True,
        "wake_to_run": True,
        "run_level": "Limited",
        "logon_type": "Interactive",
        "user_context": "MACHINE\\test-user",
        "observed_at": "2026-09-05T20:00:00+02:00",
    }
    return {
        "root": root,
        "config_path": config_path,
        "contract_path": contract_path,
        "diff_path": diff_path,
        "input_path": input_path,
        "benchmark_path": benchmark_path,
        "plan_path": plan_path,
        "environment": environment,
        "local": local,
        "ci": ci,
        "scheduler": scheduler,
        "output": root / "runtime/start-gate.json",
        "implementation_paths": implementation_paths,
        "tracked_implementation_labels": tuple(implementation_hashes),
        "source_path": source_path,
    }


def _build(fixture: dict[str, object], **overrides: object) -> dict[str, object]:
    kwargs = {
        "contract_artifact_path": fixture["contract_path"],
        "contract_diff_path": fixture["diff_path"],
        "local_gate_results": fixture["local"],
        "ci_evidence": fixture["ci"],
        "scheduler_evidence": fixture["scheduler"],
        "config_path": fixture["config_path"],
        "project_root": fixture["root"],
        "input_precheck_path": fixture["input_path"],
        "worker_benchmark_path": fixture["benchmark_path"],
        "descriptive_plan_path": fixture["plan_path"],
        "environment_snapshot": fixture["environment"],
        "operational_observations": {
            "start_gate_blocking": False,
            "dispatch_rechecks_authoritatively": True,
        },
        "artifact_path": fixture["output"],
        "created_at": "2026-09-05T20:05:00+02:00",
    }
    kwargs.update(overrides)
    tracked = set(fixture["tracked_implementation_labels"])

    def tracked_git(_root: Path, *args: str) -> tuple[str | None, str | None]:
        if args[:2] == ("ls-files", "--error-unmatch"):
            relative = Path(str(args[-1]))
            candidate = (Path(fixture["root"]) / relative).resolve().as_posix()
            if candidate in tracked:
                return relative.as_posix(), None
            return None, "not tracked"
        raise AssertionError(f"Unexpected Git probe in test: {args}")

    with patch(
        "multi_asset_development_v6_preflight.default_implementation_paths",
        return_value=fixture["implementation_paths"],
    ), patch("multi_asset_development_v6_preflight._git", side_effect=tracked_git):
        return build_start_gate(**kwargs)


def test_complete_pass_is_self_fingerprinted_and_written_once(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    result = _build(fixture)
    assert result["version"] == START_GATE_VERSION
    assert result["status"] == "PASS"
    assert result["start_authorized"] is True
    assert set(result["gates"].values()) == {"PASS"}
    stored = json.loads(Path(fixture["output"]).read_text(encoding="utf-8"))
    expected = stored.pop("artifact_fingerprint")
    assert expected == fingerprint(stored)
    replay = _build(fixture)
    assert replay["artifact_fingerprint"] == expected


def test_failed_local_gate_is_not_persisted(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    local = dict(fixture["local"])
    local["full_pytest"] = {
        **dict(local["full_pytest"]),
        "status": "FAIL",
        "exit_code": 1,
    }
    result = _build(fixture, local_gate_results=local)
    assert result["status"] == "FAIL"
    assert result["gates"]["LOCAL_VERIFICATION"] == "FAIL"
    assert not Path(fixture["output"]).exists()


def test_known_ci_failure_blocks_but_disclosed_remote_unavailable_is_allowed(
    tmp_path: Path,
) -> None:
    failed_fixture = _fixture(tmp_path / "failed")
    failed_ci = {
        **dict(failed_fixture["ci"]),
        "status": "FAIL",
        "evidence": "known failing run",
    }
    failed = _build(failed_fixture, ci_evidence=failed_ci)
    assert failed["status"] == "FAIL"
    assert failed["gates"]["CI_VERIFICATION"] == "FAIL"

    unavailable_fixture = _fixture(tmp_path / "unavailable")
    unavailable_ci = {
        "status": "REMOTE_UNAVAILABLE",
        "commit": "b" * 40,
        "checked_at": "2026-09-05T20:00:00+02:00",
        "workflow": "Smoke Test / smoke",
        "reason": "GitHub API unavailable after an explicit attempt",
    }
    allowed = _build(unavailable_fixture, ci_evidence=unavailable_ci)
    assert allowed["status"] == "PASS"
    assert "CI_REMOTE_UNAVAILABLE_LOCAL_GATES_USED_WITH_DISCLOSURE" in allowed[
        "warnings"
    ]


def test_scheduler_must_be_installed_enabled_and_repeat_every_five_minutes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    not_installed = {
        **dict(fixture["scheduler"]),
        "status": "NOT_YET_INSTALLED_ALLOWED",
        "task_exists": False,
        "task_count": 0,
        "enabled": False,
    }
    result = _build(fixture, scheduler_evidence=not_installed)
    assert result["status"] == "FAIL"
    assert result["gates"]["SCHEDULER_CONTRACT"] == "FAIL"
    assert result["checks"]["SCHEDULER_CONTRACT"][
        "installed_status_exact"
    ] is False

    wrong_interval = {
        **dict(fixture["scheduler"]),
        "repetition_interval_minutes": 10,
    }
    result = _build(fixture, scheduler_evidence=wrong_interval)
    assert result["status"] == "FAIL"
    assert result["checks"]["SCHEDULER_CONTRACT"][
        "five_minute_repetition"
    ] is False


def test_existing_run_store_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    (tmp_path / "runtime/v6_control.sqlite3").write_bytes(b"existing-run")
    result = _build(fixture)
    assert result["status"] == "FAIL"
    assert result["gates"]["RUN_ABSENT"] == "FAIL"
    assert "V6_RUN_ALREADY_EXISTS:control_store" in result["blockers"]
    assert not Path(fixture["output"]).exists()


def test_worker_must_remain_eligible_for_current_resources(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    environment = dict(fixture["environment"])
    resources = dict(environment["resources"])
    resources["logical_cpu_count"] = 2
    environment["resources"] = resources
    result = _build(fixture, environment_snapshot=environment)
    assert result["status"] == "FAIL"
    assert result["checks"]["RESOURCES"]["selected_workers_fit_cpu"] is False


def test_benchmark_missing_operational_metric_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    benchmark_path = Path(fixture["benchmark_path"])
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["configurations"][0].pop("peak_ram_upper_bound_bytes")
    payload["configuration_evidence_checks"]["1"] = configuration_evidence_checks(
        payload["configurations"][0]
    )
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(benchmark_path, payload)

    result = _build(fixture)

    checks = result["checks"]["WORKER_BENCHMARK_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["reference_configuration_pass"] is False
    assert checks["configuration_decisions_artifact_binding"] is False
    assert not Path(fixture["output"]).exists()


def test_benchmark_failed_technical_gate_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    benchmark_path = Path(fixture["benchmark_path"])
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["configurations"][2]["technical_coverage_gates"][
        "input_gap_censoring_exercised"
    ] = False
    payload["configuration_evidence_checks"]["4"] = configuration_evidence_checks(
        payload["configurations"][2]
    )
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(benchmark_path, payload)

    result = _build(fixture)

    checks = result["checks"]["WORKER_BENCHMARK_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["configuration_decisions_artifact_binding"] is False
    assert checks["selected_worker_is_passing_configuration"] is False
    assert checks["technical_gate_schema_exact"] is True
    assert not Path(fixture["output"]).exists()


def test_benchmark_descriptive_plan_binding_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    benchmark_path = Path(fixture["benchmark_path"])
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["descriptive_plan_artifact_fingerprint"] = "f" * 64
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(benchmark_path, payload)

    result = _build(fixture)

    checks = result["checks"]["WORKER_BENCHMARK_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["descriptive_plan_artifact_binding"] is False
    assert not Path(fixture["output"]).exists()


def test_benchmark_lock_and_runtime_protection_evidence_blocks_start(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    benchmark_path = Path(fixture["benchmark_path"])
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["global_research_lock_held"] = False
    payload["protected_runtime_checks_before_each_configuration"] = []
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(benchmark_path, payload)

    result = _build(fixture)

    checks = result["checks"]["WORKER_BENCHMARK_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["global_research_lock_held"] is False
    assert checks["protected_runtime_checked_before_every_configuration"] is False
    assert not Path(fixture["output"]).exists()


def test_plan_frozen_after_benchmark_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    benchmark_path = Path(fixture["benchmark_path"])
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["created_at"] = "2026-09-05T16:59:59+02:00"
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(benchmark_path, payload)

    result = _build(fixture)

    benchmark_checks = result["checks"]["WORKER_BENCHMARK_BINDING"]
    plan_checks = result["checks"]["DESCRIPTIVE_PLAN_BINDING"]
    assert result["status"] == "FAIL"
    assert benchmark_checks["descriptive_plan_frozen_before_benchmark"] is False
    assert plan_checks["frozen_before_worker_benchmark"] is False
    assert not Path(fixture["output"]).exists()


def test_existing_immutable_gate_cannot_be_rewritten(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _build(fixture)
    with pytest.raises(DevelopmentV6PreflightError, match="different content"):
        _build(fixture, created_at="2026-09-05T20:06:00+02:00")


def test_changed_implementation_hash_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    changed = Path(fixture["implementation_paths"][0])
    changed.write_text("VALUE = 'changed after freeze'\n", encoding="utf-8")
    result = _build(fixture)
    checks = result["checks"]["INPUT_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["code_stored_hashes_match_current_files"] is False
    assert checks["code_current_fingerprint_matches_input_contract"] is False
    assert not Path(fixture["output"]).exists()


def test_changed_frozen_source_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    Path(fixture["source_path"]).write_text('{"frozen":false}\n', encoding="utf-8")

    result = _build(fixture)

    checks = result["checks"]["INPUT_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["current_source_rehash_pass"] is False
    assert checks["current_source_hashes_exact"] is False
    assert result["input_source_audit"]["status"] == "FAIL"
    assert "weichen" in result["input_source_audit"]["error"]
    assert not Path(fixture["output"]).exists()


def test_missing_frozen_source_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    Path(fixture["source_path"]).unlink()

    result = _build(fixture)

    checks = result["checks"]["INPUT_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["current_source_rehash_pass"] is False
    assert result["input_source_audit"]["status"] == "FAIL"
    assert "fehlt" in result["input_source_audit"]["error"]
    assert not Path(fixture["output"]).exists()


def test_source_path_traversal_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    input_path = Path(fixture["input_path"])
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["source_paths"]["dataset_manifest"]["relative_path"] = "../escape.json"
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(input_path, payload)

    result = _build(fixture)

    checks = result["checks"]["INPUT_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["current_source_rehash_pass"] is False
    assert result["input_source_audit"]["status"] == "FAIL"
    assert "Unsicherer" in result["input_source_audit"]["error"]
    assert not Path(fixture["output"]).exists()


def test_missing_implementation_file_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    Path(fixture["implementation_paths"][1]).unlink()
    result = _build(fixture)
    checks = result["checks"]["INPUT_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["code_no_missing_implementation_file"] is False
    assert checks["code_rehash_label_set_exact"] is False
    assert result["implementation_code_audit"]["missing_labels"]
    assert not Path(fixture["output"]).exists()


def test_implementation_fingerprint_mismatch_blocks_start(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    input_path = Path(fixture["input_path"])
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload.pop("artifact_fingerprint")
    payload["contract_inputs"]["implementation_fingerprint"] = "f" * 64
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write(input_path, payload)

    result = _build(fixture)
    checks = result["checks"]["INPUT_BINDING"]
    assert result["status"] == "FAIL"
    assert checks["code_current_fingerprint_matches_input_contract"] is False
    assert checks["code_current_fingerprint_matches_contract_reference"] is True
    assert not Path(fixture["output"]).exists()
