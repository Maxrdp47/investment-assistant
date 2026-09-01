from __future__ import annotations

"""Final eight-group gate for the versioned Development execution contract."""

from pathlib import Path
from typing import Mapping

from multi_asset_development_contract import (
    DEVELOPMENT_CONTRACT_VERSION,
    verify_development_contract_artifact,
)
from multi_asset_development_runner import RUNNER_VERSION
from multi_asset_development_readiness import (
    NOT_READY_STATUS,
    READY_STATUS,
    evaluate_multi_asset_development_readiness,
    fingerprint,
)


FINAL_DEVELOPMENT_READINESS_V2 = (
    "multi-asset-final-development-readiness-2026.09.01-v3"
)


def _all_true(values: Mapping[str, object]) -> bool:
    return bool(values) and all(value is True for value in values.values())


def evaluate_multi_asset_development_readiness_v2(
    *,
    parent_contract: Mapping[str, object],
    expected_parent_contract_fingerprint: str,
    freeze_valid: bool,
    pilot: Mapping[str, object],
    fx_remediation: Mapping[str, object],
    historical_dependency: Mapping[str, object],
    identity_precheck: Mapping[str, object],
    fx_observer: Mapping[str, object],
    database_integrity: Mapping[str, object],
    protected_sources_unchanged: bool,
    development_contract_artifact: Mapping[str, object],
    contract_diff: Mapping[str, object],
    runner_preflight: Mapping[str, object],
    scheduler_preflight: Mapping[str, object],
) -> dict[str, object]:
    base = evaluate_multi_asset_development_readiness(
        contract=parent_contract,
        expected_contract_fingerprint=expected_parent_contract_fingerprint,
        freeze_valid=freeze_valid,
        pilot=pilot,
        fx_remediation=fx_remediation,
        historical_dependency=historical_dependency,
        identity_precheck=identity_precheck,
        fx_observer=fx_observer,
        database_integrity=database_integrity,
        protected_sources_unchanged=protected_sources_unchanged,
    )
    development = dict(development_contract_artifact.get("contract") or {})
    candidate = dict(development.get("candidate_generation") or {})
    stores = dict(development.get("store_contract") or {})
    execution = dict(development.get("development_execution") or {})
    references = dict(development.get("reference_fingerprints") or {})
    parent = dict(development.get("parent_contract") or {})
    h_checks = {
        "development_contract_artifact_valid": verify_development_contract_artifact(
            development_contract_artifact
        ),
        "new_version": development.get("contract_version")
        == DEVELOPMENT_CONTRACT_VERSION,
        "parent_link_valid": parent.get("fingerprint")
        == expected_parent_contract_fingerprint
        and parent.get("immutable") is True,
        "research_semantics_diff_zero": contract_diff.get(
            "research_semantics_diff_count"
        )
        == 0
        and contract_diff.get("status") == "PASS",
        "research_role_authorizes_development": development.get("research_role")
        == "development",
        "candidate_mode_authorizes_full_universe": candidate.get("mode")
        == "full_eligibility_universe",
        "full_development_scan_authorized": candidate.get(
            "full_development_scan_allowed"
        )
        is True,
        "large_scan_authorized": dict(development.get("pilot_contract") or {}).get(
            "large_scan_allowed"
        )
        is True,
        "development_stores_separate": "development"
        in str(stores.get("feature_store") or "")
        and "development" in str(stores.get("outcome_store") or "")
        and stores.get("feature_store") != stores.get("outcome_store"),
        "development_only_split": execution.get("development_start") == "2016-01-01"
        and execution.get("development_end") == "2021-12-31",
        "validation_holdout_access_forbidden": execution.get(
            "validation_access_allowed"
        )
        is False
        and execution.get("holdout_access_allowed") is False,
        "fx_v2_mandatory": references.get("fx_dataset_fingerprint")
        == fx_remediation.get("dataset_fingerprint"),
        "historical_dependency_policy_mandatory": references.get(
            "historical_dependency_policy_fingerprint"
        )
        == dict(historical_dependency.get("policy") or {}).get("policy_fingerprint"),
        "runner_preflight_passed": runner_preflight.get("status") == "PASS"
        and runner_preflight.get("runner_version") == RUNNER_VERSION,
        "contract_artifact_matches_gate_head": runner_preflight.get(
            "contract_artifact_matches_head"
        )
        is True,
        "deterministic_work_plan": bool(
            runner_preflight.get("work_plan_fingerprint")
        )
        and int(runner_preflight.get("total_planned_work_units") or 0) > 0,
        "process_lock_and_resume_defined": bool(execution.get("process_lock"))
        and execution.get("checkpoint_after_each_work_unit") is True
        and stores.get("resume_must_not_duplicate") is True,
        "scheduler_persistence_preflight_passed": scheduler_preflight.get("status")
        == "PASS"
        and scheduler_preflight.get("canonical_task_count") in {0, 1}
        and scheduler_preflight.get("multiple_instances") == "IgnoreNew",
        "scheduler_uses_project_logon_convention": scheduler_preflight.get(
            "logon_type"
        )
        == execution.get("scheduler_logon_type")
        == "Interactive",
        "no_strategy_or_trade_outputs": all(
            execution.get(key) is False
            for key in (
                "paper_output_allowed",
                "shadow_output_allowed",
                "broker_output_allowed",
                "automatic_orders_allowed",
                "automatic_strategy_optimization_allowed",
            )
        ),
    }
    gates = dict(base["gates"])
    gates["H_DEVELOPMENT_EXECUTION_CONTRACT"] = h_checks
    gate_status = {
        name: "PASS" if _all_true(dict(checks)) else "FAIL"
        for name, checks in gates.items()
    }
    ready = all(value == "PASS" for value in gate_status.values())
    payload: dict[str, object] = {
        "version": FINAL_DEVELOPMENT_READINESS_V2,
        "status": READY_STATUS if ready else NOT_READY_STATUS,
        "gates": gates,
        "gate_status": gate_status,
        "failed_checks": [
            f"{group}.{name}"
            for group, checks in gates.items()
            for name, passed in dict(checks).items()
            if not passed
        ],
        "parent_contract_fingerprint": expected_parent_contract_fingerprint,
        "development_contract_fingerprint": development.get(
            "contract_fingerprint"
        ),
        "contract_diff_fingerprint": contract_diff.get("diff_fingerprint"),
        "universe_fingerprint": runner_preflight.get("universe_fingerprint"),
        "work_plan_fingerprint": runner_preflight.get("work_plan_fingerprint"),
        "full_development_scan_started": False,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "true_forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
    }
    payload["gate_fingerprint"] = fingerprint(payload)
    return payload
