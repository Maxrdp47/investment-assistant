from __future__ import annotations

from multi_asset_development_readiness import (
    NOT_READY_STATUS,
    evaluate_multi_asset_development_readiness,
)


def _inputs() -> dict[str, object]:
    contract = {
        "contract_fingerprint": "contract",
        "research_role": "technical_integrity_pilot_only",
        "candidate_generation": {
            "mode": "fixed_representatives_for_integrity_pilot",
            "full_development_scan_allowed": False,
        },
        "pilot_contract": {"large_scan_allowed": False},
        "store_contract": {
            "feature_store": "runtime/multi_asset_discovery_v1_pilot_features.sqlite3",
            "outcome_store": "runtime/multi_asset_discovery_v1_pilot_outcomes.sqlite3",
        },
        "lifecycle": {
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
            "true_forward_opened": False,
            "paper_opened": False,
            "shadow_opened": False,
            "broker_opened": False,
            "automatic_orders_allowed": False,
        },
    }
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
    return {
        "contract": contract,
        "expected_contract_fingerprint": "contract",
        "freeze_valid": True,
        "pilot": {
            "status": "READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT",
            "gates": pilot_gates,
        },
        "fx_remediation": {
            "status": "HISTORICAL_FX_ACTIVE_PIT_READY_WITH_INVALID_SOURCE_BARS_EXCLUDED",
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
                "unknown_historical_relation_contributes_to_effective_n": 0,
                "fail_closed": True,
            },
        },
        "identity_precheck": {"gate_status": {"A": "PASS", "B": "PASS"}},
        "fx_observer": {
            "status": "PASS",
            "matching_task_n": 1,
            "checks": {"one": True},
            "broker_order_allowed": False,
        },
        "database_integrity": {"fx_active_v2": "ok", "fx_forward": "ok"},
        "protected_sources_unchanged": True,
    }


def test_frozen_pilot_only_contract_blocks_full_development_without_downgrade() -> None:
    result = evaluate_multi_asset_development_readiness(**_inputs())
    assert result["status"] == NOT_READY_STATUS
    assert result["gate_status"]["D_FX_HISTORICAL_DATA_QUALITY"] == "PASS"
    assert result["gate_status"]["F_PIT_LEAKAGE_AND_PILOT"] == "PASS"
    assert result["gate_status"]["H_DEVELOPMENT_EXECUTION_CONTRACT"] == "FAIL"
    assert result["full_development_scan_started"] is False
    assert any(
        item.endswith("full_development_scan_authorized")
        for item in result["failed_checks"]
    )

