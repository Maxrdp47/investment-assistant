from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from multi_asset_development_contract import load_development_contract
from multi_asset_development_v6_benchmark import (
    BENCHMARK_VERSION,
    DEFAULT_BENCHMARK_ARTIFACT,
    REQUIRED_TECHNICAL_COVERAGE_GATES,
    classify_worker_configurations,
    configuration_evidence_checks,
)
from multi_asset_development_v6_inputs import (
    DEFAULT_INPUT_PRECHECK_ARTIFACT,
    INPUT_PRECHECK_VERSION,
)
from multi_asset_development_v6_reporting import DEFAULT_PLAN_ARTIFACT, PLAN_VERSION
from multi_asset_development_v6_contract import (
    ALLOWED_REPAIR_CATEGORIES,
    DEFAULT_V6_CONFIG_PATH,
    DEVELOPMENT_V6_CONTRACT_VERSION,
    LIFECYCLE_CHAIN,
    SEMANTIC_INVARIANT_ROOTS,
    MultiAssetDevelopmentV6ContractError,
    build_development_v6_benchmark_contract,
    build_development_v6_contract_artifact,
    build_development_v6_contract_diff,
    load_development_v6_contract,
    verify_development_v6_contract_artifact,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _self_fingerprinted(**values: object) -> dict[str, object]:
    payload = dict(values)
    payload["artifact_fingerprint"] = fingerprint(payload)
    return payload


def _benchmark_configuration(worker_count: int) -> dict[str, object]:
    return {
        "worker_count": worker_count,
        "status": "PASS",
        "wall_seconds": 10.0 / worker_count,
        "throughput_cases_per_second": 10.0 * worker_count,
        "case_count": 10,
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
        "scientific_digest": fingerprint("same-scientific-payload"),
        "worker_result_digest_check_count": 4,
        "worker_result_digests_verified": True,
        "sqlite_writer_count": 1,
        "technical_coverage_gates": {
            name: True for name in REQUIRED_TECHNICAL_COVERAGE_GATES
        },
    }


def test_superseding_prerequisite_instances_preserve_v1_schemas() -> None:
    config = json.loads(DEFAULT_V6_CONFIG_PATH.read_text(encoding="utf-8"))
    required = dict(config["required_runtime_artifacts"])

    assert required["input_precheck"]["version"] == INPUT_PRECHECK_VERSION
    assert required["worker_benchmark"]["version"] == BENCHMARK_VERSION
    assert required["descriptive_plan"]["version"] == PLAN_VERSION
    for name in ("input_precheck", "worker_benchmark", "descriptive_plan"):
        assert str(required[name]["path"]).endswith("-v1-r6.json")
    assert str(DEFAULT_INPUT_PRECHECK_ARTIFACT).endswith(
        "multi_asset_development_v6_input_precheck_2026-09-05-v1.json"
    )
    assert DEFAULT_BENCHMARK_ARTIFACT.as_posix().endswith("-v1-r6.json")
    assert DEFAULT_PLAN_ARTIFACT.as_posix().endswith("-v1-r6.json")
    assert str(config["runtime"]["execution"]["contract_artifact"]).endswith(
        "multi_asset_discovery_v1_development_contract_2026-09-05-v6-r2.json"
    )
    assert str(config["runtime"]["execution"]["contract_diff_artifact"]).endswith(
        "multi_asset_discovery_v1_development_contract_diff_2026-09-05-v6-r2.json"
    )
    assert str(config["runtime"]["execution"]["start_gate_artifact"]).endswith(
        "multi_asset_development_v6_start_gate_2026-09-05-v1.json"
    )


@pytest.fixture()
def v6_fixture(tmp_path: Path) -> dict[str, object]:
    parent_contract = load_development_contract()
    parent_artifact = _self_fingerprinted(
        version="multi-asset-development-contract-artifact-2026.09.01-v5",
        contract=parent_contract,
        contract_fingerprint=parent_contract["contract_fingerprint"],
        frozen_at="2026-09-02T12:00:00+00:00",
    )
    parent_artifact_path = tmp_path / "runtime" / "parent_v5.json"
    _write_json(parent_artifact_path, parent_artifact)

    parent_manifest: dict[str, object] = {
        "version": "multi-asset-discovery-development-run-manifest-2026.09.01-v5",
        "run_id": "mad1-development-test-parent",
        "development_contract_fingerprint": parent_contract[
            "contract_fingerprint"
        ],
        "status": "STARTING",
    }
    parent_manifest["run_manifest_fingerprint"] = fingerprint(parent_manifest)
    parent_manifest_path = tmp_path / "runtime" / "parent_v5_manifest.json"
    _write_json(parent_manifest_path, parent_manifest)

    input_contract = {
        key: fingerprint({"input": key})
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
            "implementation_fingerprint",
        )
    }
    input_precheck = _self_fingerprinted(
        version="multi-asset-development-v6-input-precheck-2026.09.05-v1",
        status="PASS",
        contract_inputs=input_contract,
        development_run_started=False,
    )
    input_path = tmp_path / "runtime" / "input_precheck.json"
    _write_json(input_path, input_precheck)

    benchmark_configurations = [
        _benchmark_configuration(worker_count) for worker_count in (1, 2, 4)
    ]
    benchmark_classification = classify_worker_configurations(
        benchmark_configurations
    )
    benchmark = _self_fingerprinted(
        version="multi-asset-development-v6-worker-benchmark-2026.09.05-v1",
        status="PASS",
        input_precheck_fingerprint=input_precheck["artifact_fingerprint"],
        worker_input_precheck_artifact={
            "path": "runtime/input_precheck.json",
            "artifact_fingerprint": input_precheck["artifact_fingerprint"],
        },
        combined_input_fingerprint=input_contract["combined_input_fingerprint"],
        scientific_parent_contract_fingerprint=parent_contract[
            "contract_fingerprint"
        ],
        selected_worker_count=4,
        sqlite_writer_count=1,
        resources={
            "logical_cpu_count": 4,
            "total_physical_memory_bytes": 16 * 1024**3,
        },
        configurations=benchmark_configurations,
        configuration_evidence_checks={
            str(item["worker_count"]): configuration_evidence_checks(item)
            for item in benchmark_configurations
        },
        all_configuration_evidence_complete=True,
        benchmark_completed=True,
        protected_runtime_checks_before_each_configuration=[
            {
                "worker_count": worker_count,
                "status": "PASS",
                "reason": "CLEAR",
                "detail": {},
            }
            for worker_count in (1, 2, 4)
        ],
        exclusive_benchmark_process_lock_held=True,
        global_research_lock_held=True,
        reference_worker_count=1,
        reference_configuration_count=1,
        reference_configuration_passed=True,
        reference_scientific_digest=benchmark_classification[
            "reference_scientific_digest"
        ],
        configuration_decisions=benchmark_classification[
            "configuration_decisions"
        ],
        selection_candidate_worker_counts=benchmark_classification[
            "selection_candidate_worker_counts"
        ],
        excluded_multi_worker_configurations=[],
        all_tested_payloads_equal_to_reference=True,
        all_selection_candidates_identical_to_reference=True,
        deterministic_payloads_equal=True,
        selected_digest_matches_one_worker_reference=True,
        fallback_to_one_worker=False,
        fallback_reasons=[],
        multi_worker_instability_is_not_a_start_blocker=True,
        selection_used_outcomes=False,
        benchmark_used_for_research_selection=False,
        development_run_started=False,
    )
    benchmark_path = tmp_path / "runtime" / "benchmark.json"
    _write_json(benchmark_path, benchmark)

    plan = _self_fingerprinted(
        version="multi-asset-development-v6-descriptive-plan-2026.09.05-v1",
        status="FROZEN",
        created_at="2026-09-05T00:00:00+00:00",
        combined_input_fingerprint=input_contract["combined_input_fingerprint"],
        inferential_claims_allowed=False,
        selection_or_optimization_allowed=False,
        free_threshold_search_allowed=False,
        development_run_started=False,
    )
    plan_path = tmp_path / "runtime" / "plan.json"
    _write_json(plan_path, plan)
    benchmark.pop("artifact_fingerprint")
    benchmark.update(
        {
            "created_at": "2026-09-05T01:00:00+00:00",
            "descriptive_plan_artifact_fingerprint": plan[
                "artifact_fingerprint"
            ],
            "descriptive_plan_created_at": plan["created_at"],
        }
    )
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    config = json.loads(DEFAULT_V6_CONFIG_PATH.read_text(encoding="utf-8"))
    parent_spec = config["parent_reprocessing"]
    parent_spec.update(
        {
            "artifact_path": "runtime/parent_v5.json",
            "artifact_sha256": file_sha256(parent_artifact_path),
            "artifact_fingerprint": parent_artifact["artifact_fingerprint"],
            "contract_fingerprint": parent_contract["contract_fingerprint"],
            "run_manifest_path": "runtime/parent_v5_manifest.json",
            "run_manifest_sha256": file_sha256(parent_manifest_path),
            "run_manifest_fingerprint": parent_manifest[
                "run_manifest_fingerprint"
            ],
            "run_id": parent_manifest["run_id"],
        }
    )
    required = config["required_runtime_artifacts"]
    required["input_precheck"]["path"] = "runtime/input_precheck.json"
    required["worker_benchmark"]["path"] = "runtime/benchmark.json"
    required["descriptive_plan"]["path"] = "runtime/plan.json"
    config_path = tmp_path / "config" / "v6.json"
    _write_json(config_path, config)
    return {
        "root": tmp_path,
        "config": config,
        "config_path": config_path,
        "parent_contract": parent_contract,
        "parent_artifact_path": parent_artifact_path,
        "input_path": input_path,
        "input_contract": input_contract,
        "benchmark_path": benchmark_path,
        "benchmark": benchmark,
        "plan_path": plan_path,
        "plan": plan,
    }


def _load(fixture: dict[str, object]) -> dict[str, object]:
    return load_development_v6_contract(
        Path(fixture["config_path"]), project_root=Path(fixture["root"])
    )


def test_v6_inherits_research_semantics_and_opens_only_full_development(
    v6_fixture: dict[str, object],
) -> None:
    parent_path = Path(v6_fixture["parent_artifact_path"])
    before = file_sha256(parent_path)
    parent = dict(v6_fixture["parent_contract"])
    contract = _load(v6_fixture)

    assert file_sha256(parent_path) == before
    assert contract["contract_version"] == DEVELOPMENT_V6_CONTRACT_VERSION
    assert contract["contract_fingerprint"] != parent["contract_fingerprint"]
    for root in SEMANTIC_INVARIANT_ROOTS:
        assert canonical_json(contract[root]) == canonical_json(parent[root])
    assert contract["candidate_generation"]["full_development_scan_allowed"] is True
    assert contract["pilot_contract"]["large_scan_allowed"] is True
    assert contract["development_execution"]["full_development_run_allowed"] is True
    assert tuple(contract["development_execution"]["lifecycle_chain"]) == LIFECYCLE_CHAIN
    assert contract["development_execution"]["final_audit_required_before_report"] is True
    assert contract["development_execution"]["stop_after_summary"] is True
    assert all(value is False for value in contract["lifecycle"].values())


def test_pre_freeze_benchmark_contract_has_no_run_or_store_authority(
    v6_fixture: dict[str, object],
) -> None:
    Path(v6_fixture["benchmark_path"]).unlink()
    Path(v6_fixture["plan_path"]).unlink()
    parent = dict(v6_fixture["parent_contract"])

    contract = build_development_v6_benchmark_contract(
        Path(v6_fixture["config_path"]), project_root=Path(v6_fixture["root"])
    )

    assert contract["contract_version"] == DEVELOPMENT_V6_CONTRACT_VERSION
    assert contract["contract_state"] == "BENCHMARK_PRE_FREEZE"
    assert "store_contract" not in contract
    assert contract["development_execution"]["execution_authorization"] == (
        "BENCHMARK_ONLY"
    )
    assert contract["development_execution"]["full_development_run_allowed"] is False
    assert contract["development_execution"]["input_precheck_artifact"] == dict(
        v6_fixture["config"]["required_runtime_artifacts"]
    )["input_precheck"]["path"]
    assert contract["development_execution"]["input_precheck_version"] == dict(
        v6_fixture["config"]["required_runtime_artifacts"]
    )["input_precheck"]["version"]
    assert "worker_benchmark_artifact_fingerprint" not in contract[
        "reference_fingerprints"
    ]
    assert "descriptive_plan_artifact_fingerprint" not in contract[
        "reference_fingerprints"
    ]
    for root in SEMANTIC_INVARIANT_ROOTS:
        assert canonical_json(contract[root]) == canonical_json(parent[root])
    assert all(value is False for value in contract["lifecycle"].values())


def test_v6_loads_exact_runtime_fingerprints_and_worker_selection(
    v6_fixture: dict[str, object],
) -> None:
    contract = _load(v6_fixture)
    inputs = dict(v6_fixture["input_contract"])
    benchmark = dict(v6_fixture["benchmark"])
    plan = dict(v6_fixture["plan"])
    references = contract["reference_fingerprints"]

    assert references["dataset_fingerprint"] == inputs["combined_input_fingerprint"]
    assert references["equity_etf_projection_fingerprint"] == inputs[
        "equity_etf_projection_fingerprint"
    ]
    assert references["crypto_projection_fingerprint"] == inputs[
        "crypto_projection_fingerprint"
    ]
    assert references["fx_projection_fingerprint"] == inputs[
        "fx_projection_fingerprint"
    ]
    assert references["development_code_fingerprint"] == inputs[
        "implementation_fingerprint"
    ]
    assert references["worker_benchmark_artifact_fingerprint"] == benchmark[
        "artifact_fingerprint"
    ]
    assert references["descriptive_plan_artifact_fingerprint"] == plan[
        "artifact_fingerprint"
    ]
    assert contract["development_execution"]["worker_count"] == 4
    assert contract["development_execution"]["sqlite_writer_count"] == 1
    assert contract["store_contract"]["serial_sqlite_writes_main_process_only"] is True


def test_v6_parent_diff_has_only_five_authorized_categories(
    v6_fixture: dict[str, object],
) -> None:
    parent = dict(v6_fixture["parent_contract"])
    contract = _load(v6_fixture)
    report = build_development_v6_contract_diff(
        parent=parent,
        development=contract,
        config=dict(v6_fixture["config"]),
    )

    assert report["status"] == "PASS"
    assert report["unauthorized_research_semantics_count"] == 0
    assert report["semantic_invariant_failure_count"] == 0
    assert report["differences"]
    assert {item["category"] for item in report["differences"]} <= set(
        ALLOWED_REPAIR_CATEGORIES
    )
    assert all(item["authorized"] is True for item in report["differences"])
    assert all(item["repair_finding"] for item in report["differences"])


def test_semantic_change_is_never_hidden_by_an_authorized_category(
    v6_fixture: dict[str, object],
) -> None:
    parent = dict(v6_fixture["parent_contract"])
    contract = copy.deepcopy(_load(v6_fixture))
    contract["safe_zone_contract"]["zone_c_atr_buffer"] = 0.75
    contract.pop("contract_fingerprint")
    contract["contract_fingerprint"] = fingerprint(contract)
    report = build_development_v6_contract_diff(
        parent=parent,
        development=contract,
        config=dict(v6_fixture["config"]),
    )

    assert report["status"] == "FAIL"
    assert report["unauthorized_research_semantics_count"] == 1
    assert report["semantic_invariant_failure_count"] == 1
    assert report["unauthorized_differences"][0]["path"] == (
        "safe_zone_contract.zone_c_atr_buffer"
    )
    assert report["unauthorized_differences"][0]["category"] is None


def test_config_cannot_whitelist_a_research_semantic_change(
    v6_fixture: dict[str, object],
) -> None:
    parent = dict(v6_fixture["parent_contract"])
    contract = _load(v6_fixture)
    config = copy.deepcopy(dict(v6_fixture["config"]))
    config["authorized_changes"].append(
        {
            "prefix": "safe_zone_contract",
            "category": "OUTPUT_PROVENANCE",
            "repair_finding": "NOT_ACTUALLY_TECHNICAL",
        }
    )

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError,
        match="Nicht erlaubte Diff-Autorisierung",
    ):
        build_development_v6_contract_diff(
            parent=parent, development=contract, config=config
        )


def test_tampered_pass_artifact_blocks_contract_freeze(
    v6_fixture: dict[str, object],
) -> None:
    input_path = Path(v6_fixture["input_path"])
    tampered = json.loads(input_path.read_text(encoding="utf-8"))
    tampered["contract_inputs"]["combined_input_fingerprint"] = "f" * 64
    _write_json(input_path, tampered)

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError, match="Self-Fingerprint"
    ):
        _load(v6_fixture)


def test_missing_runtime_artifact_fails_closed(
    v6_fixture: dict[str, object],
) -> None:
    Path(v6_fixture["plan_path"]).unlink()

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError, match="Pflichtartefakt für v6 fehlt"
    ):
        _load(v6_fixture)


def test_benchmark_with_dishonest_digest_equality_disclosure_fails_closed(
    v6_fixture: dict[str, object],
) -> None:
    benchmark_path = Path(v6_fixture["benchmark_path"])
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark.pop("artifact_fingerprint")
    benchmark["deterministic_payloads_equal"] = False
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError,
        match="referenztreu/fail-closed",
    ):
        _load(v6_fixture)


def test_honest_divergent_multi_worker_fallback_to_reference_is_allowed(
    v6_fixture: dict[str, object],
) -> None:
    benchmark_path = Path(v6_fixture["benchmark_path"])
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark.pop("artifact_fingerprint")
    for configuration in benchmark["configurations"]:
        if configuration["worker_count"] > 1:
            configuration["scientific_digest"] = fingerprint(
                f"divergent-{configuration['worker_count']}"
            )
    classification = classify_worker_configurations(benchmark["configurations"])
    benchmark.update(
        {
            "configuration_evidence_checks": {
                str(item["worker_count"]): configuration_evidence_checks(item)
                for item in benchmark["configurations"]
            },
            "all_configuration_evidence_complete": True,
            "reference_configuration_passed": True,
            "reference_scientific_digest": classification[
                "reference_scientific_digest"
            ],
            "configuration_decisions": classification["configuration_decisions"],
            "selection_candidate_worker_counts": [1],
            "excluded_multi_worker_configurations": classification[
                "excluded_multi_worker_configurations"
            ],
            "all_tested_payloads_equal_to_reference": False,
            "all_selection_candidates_identical_to_reference": True,
            "deterministic_payloads_equal": False,
            "selected_worker_count": 1,
            "selected_digest_matches_one_worker_reference": True,
            "fallback_to_one_worker": True,
            "fallback_reasons": [
                "ONE_OR_MORE_MULTI_WORKER_CONFIGURATIONS_EXCLUDED",
                "NO_STABLE_IDENTICAL_MULTI_WORKER_CONFIGURATION",
            ],
        }
    )
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    contract = _load(v6_fixture)

    assert contract["development_execution"]["worker_count"] == 1
    worker_runtime = contract["technical_reprocessing_contract"]["worker_runtime"]
    assert worker_runtime["one_worker_reference_passed"] is True
    assert worker_runtime["selected_digest_matches_one_worker_reference"] is True
    assert worker_runtime["fallback_to_one_worker"] is True
    assert worker_runtime["excluded_multi_worker_configurations"]


def test_self_valid_benchmark_from_another_input_is_rejected(
    v6_fixture: dict[str, object],
) -> None:
    benchmark_path = Path(v6_fixture["benchmark_path"])
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark.pop("artifact_fingerprint")
    benchmark["combined_input_fingerprint"] = "e" * 64
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError,
        match="Benchmark-Provenienz",
    ):
        _load(v6_fixture)


def test_benchmark_must_bind_exact_frozen_descriptive_plan(
    v6_fixture: dict[str, object],
) -> None:
    benchmark_path = Path(v6_fixture["benchmark_path"])
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark.pop("artifact_fingerprint")
    benchmark["descriptive_plan_artifact_fingerprint"] = "e" * 64
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError,
        match="Benchmark-Provenienz",
    ):
        _load(v6_fixture)


def test_benchmark_without_lock_and_runtime_protection_evidence_is_rejected(
    v6_fixture: dict[str, object],
) -> None:
    benchmark_path = Path(v6_fixture["benchmark_path"])
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark.pop("artifact_fingerprint")
    benchmark["global_research_lock_held"] = False
    benchmark["protected_runtime_checks_before_each_configuration"] = []
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError,
        match="referenztreu/fail-closed",
    ):
        _load(v6_fixture)


def test_descriptive_plan_must_be_frozen_before_benchmark(
    v6_fixture: dict[str, object],
) -> None:
    plan_path = Path(v6_fixture["plan_path"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.pop("artifact_fingerprint")
    plan["created_at"] = "2026-09-05T02:00:00+00:00"
    plan["artifact_fingerprint"] = fingerprint(plan)
    _write_json(plan_path, plan)

    benchmark_path = Path(v6_fixture["benchmark_path"])
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark.pop("artifact_fingerprint")
    benchmark["descriptive_plan_artifact_fingerprint"] = plan[
        "artifact_fingerprint"
    ]
    benchmark["descriptive_plan_created_at"] = plan["created_at"]
    benchmark["artifact_fingerprint"] = fingerprint(benchmark)
    _write_json(benchmark_path, benchmark)

    with pytest.raises(
        MultiAssetDevelopmentV6ContractError,
        match="Benchmark-Provenienz",
    ):
        _load(v6_fixture)


def test_v6_artifact_is_parent_linked_self_valid_and_never_starts_a_run(
    v6_fixture: dict[str, object],
) -> None:
    artifact, diff = build_development_v6_contract_artifact(
        git_branch="codex/test-v6",
        git_commit="a" * 40,
        frozen_at="2026-09-05T12:00:00+00:00",
        config_path=Path(v6_fixture["config_path"]),
        project_root=Path(v6_fixture["root"]),
    )

    assert verify_development_v6_contract_artifact(artifact) is True
    assert diff["status"] == "PASS"
    assert artifact["unauthorized_research_semantics_count"] == 0
    assert artifact["reprocessing_parent"]["immutable"] is True
    assert artifact["full_development_run_authorized"] is True
    assert artifact["development_run_started"] is False
    assert tuple(artifact["lifecycle_chain"]) == LIFECYCLE_CHAIN
    for key in (
        "validation_opened",
        "holdout_opened",
        "external_opened",
        "true_forward_opened",
        "paper_opened",
        "shadow_opened",
        "broker_opened",
    ):
        assert artifact[key] is False
