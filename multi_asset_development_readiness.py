from __future__ import annotations

"""Fail-closed final gate for Multi-Asset Discovery v1 Development execution."""

import hashlib
import json
from typing import Mapping


FINAL_DEVELOPMENT_READINESS_VERSION = (
    "multi-asset-final-development-readiness-2026.09.01-v1"
)
READY_STATUS = "READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT"
NOT_READY_STATUS = "NOT_READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT"


def fingerprint(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _all_true(values: Mapping[str, object]) -> bool:
    return bool(values) and all(value is True for value in values.values())


def evaluate_multi_asset_development_readiness(
    *,
    contract: Mapping[str, object],
    expected_contract_fingerprint: str,
    freeze_valid: bool,
    pilot: Mapping[str, object],
    fx_remediation: Mapping[str, object],
    historical_dependency: Mapping[str, object],
    identity_precheck: Mapping[str, object],
    fx_observer: Mapping[str, object],
    database_integrity: Mapping[str, object],
    protected_sources_unchanged: bool,
) -> dict[str, object]:
    candidate = dict(contract.get("candidate_generation") or {})
    lifecycle = dict(contract.get("lifecycle") or {})
    pilot_gates = dict(pilot.get("gates") or {})
    dependency_checks = dict(historical_dependency.get("checks") or {})
    legacy_gate_status = dict(identity_precheck.get("gate_status") or {})
    observer_checks = dict(fx_observer.get("checks") or {})

    gates = {
        "A_RESEARCH_IDENTITY": {
            "legacy_identity_precheck_passed": bool(legacy_gate_status)
            and all(value == "PASS" for value in legacy_gate_status.values()),
            "historical_dependency_policy_passed": historical_dependency.get("status")
            == "PASS",
            "historical_dependency_checks_passed": _all_true(dependency_checks),
            "current_identity_not_backdated": historical_dependency.get(
                "current_registry_valid_from_backdated"
            )
            is False,
        },
        "B_DEPENDENCY_EFFECTIVE_N": {
            "unknown_contributes_zero": int(
                dict(historical_dependency.get("policy") or {}).get(
                    "unknown_historical_relation_contributes_to_effective_n"
                )
                or 0
            )
            == 0,
            "unknown_not_counted_independent": dict(
                historical_dependency.get("policy") or {}
            ).get("fail_closed")
            is True,
            "effective_n_mechanics_pilot_passed": pilot_gates.get(
                "effective_n_not_inflated"
            )
            is True,
            "dependency_fail_closed_pilot_passed": pilot_gates.get(
                "dependency_fail_closed"
            )
            is True,
        },
        "C_RESEARCH_INTEGRITY": {
            "protected_sources_unchanged": protected_sources_unchanged,
            "feature_outcome_store_separation": pilot_gates.get(
                "stores_physically_and_semantically_separate"
            )
            is True,
            "determinism": pilot_gates.get("deterministic_replay_match") is True,
            "no_predictive_prefilter": pilot_gates.get("no_predictive_prefilter")
            is True,
            "no_composite_score": pilot_gates.get("no_composite_score") is True,
        },
        "D_FX_HISTORICAL_DATA_QUALITY": {
            "remediation_ready": fx_remediation.get("status")
            == "HISTORICAL_FX_ACTIVE_PIT_READY_WITH_INVALID_SOURCE_BARS_EXCLUDED",
            "all_231_classified": int(fx_remediation.get("v2_invalid_source_bar_n") or 0)
            == 231,
            "active_envelope_anomalies_zero": fx_remediation.get(
                "active_envelope_anomaly_n"
            )
            == 0,
            "no_clipping": fx_remediation.get("no_clipping") is True,
            "no_imputation": fx_remediation.get("no_imputation") is True,
            "legacy_229_separate": fx_remediation.get(
                "legacy_229_and_v2_231_same_group"
            )
            is False,
            "fx_store_integrity": database_integrity.get("fx_active_v2") == "ok",
        },
        "E_FX_OBSERVER": {
            "observer_database_integrity": database_integrity.get("fx_forward") == "ok",
            "scheduler_audit_passed": fx_observer.get("status") == "PASS",
            "exactly_one_observer": int(fx_observer.get("matching_task_n") or 0) == 1,
            "observer_checks_passed": _all_true(observer_checks),
            "broker_forbidden": fx_observer.get("broker_order_allowed") is False,
        },
        "F_PIT_LEAKAGE_AND_PILOT": {
            "contract_fingerprint_unchanged": contract.get("contract_fingerprint")
            == expected_contract_fingerprint,
            "freeze_valid": freeze_valid,
            "pilot_ready": pilot.get("status") == READY_STATUS,
            "all_pilot_gates_passed": bool(pilot_gates) and all(pilot_gates.values()),
            "no_ohlc_envelope_anomalies": pilot_gates.get(
                "no_ohlc_envelope_anomalies"
            )
            is True,
            "point_in_time": pilot_gates.get("features_precede_outcomes") is True
            and pilot_gates.get("next_open_entry_only") is True,
            "stage_censoring": pilot_gates.get("stage_censoring_exercised") is True,
        },
        "G_SAFETY": {
            "validation_closed": lifecycle.get("validation_opened") is False,
            "holdout_closed": lifecycle.get("holdout_opened") is False,
            "external_closed": lifecycle.get("external_opened") is False,
            "true_forward_closed": lifecycle.get("true_forward_opened") is False,
            "paper_closed": lifecycle.get("paper_opened") is False,
            "shadow_closed": lifecycle.get("shadow_opened") is False,
            "broker_closed": lifecycle.get("broker_opened") is False,
            "orders_forbidden": lifecycle.get("automatic_orders_allowed") is False,
        },
        "H_DEVELOPMENT_EXECUTION_CONTRACT": {
            "research_role_authorizes_development": contract.get("research_role")
            == "development",
            "candidate_mode_authorizes_full_universe": candidate.get("mode")
            == "full_eligibility_universe",
            "full_development_scan_authorized": candidate.get(
                "full_development_scan_allowed"
            )
            is True,
            "pilot_large_scan_authorized": dict(contract.get("pilot_contract") or {}).get(
                "large_scan_allowed"
            )
            is True,
            "development_store_contract_defined": "development"
            in str(dict(contract.get("store_contract") or {}).get("feature_store") or "")
            and "development"
            in str(dict(contract.get("store_contract") or {}).get("outcome_store") or ""),
        },
    }
    gate_status = {
        name: "PASS" if _all_true(checks) else "FAIL" for name, checks in gates.items()
    }
    ready = all(value == "PASS" for value in gate_status.values())
    payload: dict[str, object] = {
        "version": FINAL_DEVELOPMENT_READINESS_VERSION,
        "status": READY_STATUS if ready else NOT_READY_STATUS,
        "gates": gates,
        "gate_status": gate_status,
        "failed_checks": [
            f"{group}.{name}"
            for group, checks in gates.items()
            for name, passed in checks.items()
            if not passed
        ],
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
