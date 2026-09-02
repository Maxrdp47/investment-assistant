from __future__ import annotations

from multi_asset_development_contract import build_development_contract_artifact
from multi_asset_development_readiness import READY_STATUS
from multi_asset_development_readiness_v2 import (
    evaluate_multi_asset_development_readiness_v2,
)
from multi_asset_development_runner import RUNNER_VERSION
from multi_asset_discovery_v1 import load_discovery_contract
from scripts.run_multi_asset_development_readiness_v2 import (
    EXPECTED_PROTECTED_HASHES,
)


def _base() -> dict[str, object]:
    parent = load_discovery_contract()
    pilot_gates = {
        "effective_n_not_inflated": True,
        "dependency_fail_closed": True,
        "stores_physically_and_semantically_separate": True,
        "deterministic_replay_match": True,
        "no_predictive_prefilter": True,
        "no_composite_score": True,
        "no_ohlc_envelope_anomalies": True,
        "features_precede_outcomes": True,
        "next_open_entry_only": True,
        "stage_censoring_exercised": True,
    }
    artifact, diff = build_development_contract_artifact(
        git_branch="codex/test",
        git_commit="a" * 40,
        frozen_at="2026-09-01T12:00:00+00:00",
    )
    return {
        "parent_contract": parent,
        "expected_parent_contract_fingerprint": parent["contract_fingerprint"],
        "freeze_valid": True,
        "pilot": {"status": READY_STATUS, "gates": pilot_gates},
        "fx_remediation": {
            "status": "HISTORICAL_FX_ACTIVE_PIT_READY_WITH_INVALID_SOURCE_BARS_EXCLUDED",
            "dataset_fingerprint": "a3c41cddd06d7b24596bac5f1e375868a86784ea5a6feeacd9b44f49598c5c91",
            "v2_invalid_source_bar_n": 231,
            "active_envelope_anomaly_n": 0,
            "no_clipping": True,
            "no_imputation": True,
            "legacy_229_and_v2_231_same_group": False,
        },
        "historical_dependency": {
            "status": "PASS",
            "checks": {"one": True},
            "current_registry_valid_from_backdated": False,
            "policy": {
                "policy_fingerprint": "706b0b9e438464405f18d0972d49d34c553538c1236c3e7adb8fe37157214393",
                "unknown_historical_relation_contributes_to_effective_n": 0,
                "fail_closed": True,
            },
        },
        "identity_precheck": {"gate_status": {"A": "PASS"}},
        "fx_observer": {
            "status": "PASS",
            "matching_task_n": 1,
            "checks": {"one": True},
            "broker_order_allowed": False,
        },
        "database_integrity": {"fx_active_v2": "ok", "fx_forward": "ok"},
        "protected_sources_unchanged": True,
        "development_contract_artifact": artifact,
        "contract_diff": diff,
        "runner_preflight": {
            "status": "PASS",
            "runner_version": RUNNER_VERSION,
            "work_plan_fingerprint": "plan",
            "universe_fingerprint": "universe",
            "total_planned_work_units": 10,
            "contract_artifact_matches_head": True,
        },
        "scheduler_preflight": {
            "status": "PASS",
            "canonical_task_count": 0,
            "multiple_instances": "IgnoreNew",
            "logon_type": "Interactive",
        },
    }


def test_all_eight_groups_pass_with_execution_contract() -> None:
    result = evaluate_multi_asset_development_readiness_v2(**_base())

    assert result["status"] == READY_STATUS
    assert len(result["gate_status"]) == 8
    assert all(value == "PASS" for value in result["gate_status"].values())
    assert result["gate_status"]["H_DEVELOPMENT_EXECUTION_CONTRACT"] == "PASS"
    assert result["full_development_scan_started"] is False


def test_any_semantic_diff_blocks_full_development() -> None:
    inputs = _base()
    inputs["contract_diff"] = {
        **inputs["contract_diff"],
        "status": "FAIL",
        "research_semantics_diff_count": 1,
    }
    result = evaluate_multi_asset_development_readiness_v2(**inputs)

    assert result["status"] != READY_STATUS
    assert result["gate_status"]["H_DEVELOPMENT_EXECUTION_CONTRACT"] == "FAIL"
    assert result["full_development_scan_started"] is False


def test_mutable_forward_observer_store_is_not_pinned_as_immutable_source() -> None:
    assert "runtime/fx_forward_pit.sqlite3" not in EXPECTED_PROTECTED_HASHES
    assert "runtime/fx_historical_pit.sqlite3" in EXPECTED_PROTECTED_HASHES
