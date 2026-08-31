from __future__ import annotations

"""Pure final gate for defining, but never running, Multi-Asset Discovery v1."""

import hashlib
import json
from typing import Mapping


FINAL_PRECHECK_VERSION = "multi-asset-final-precheck-2026.08.31-v1"
READY_STATUS = "READY_TO_DEFINE_MULTI_ASSET_DISCOVERY_V1_CONTRACT"
NOT_READY_STATUS = "NOT_READY_TO_DEFINE_MULTI_ASSET_DISCOVERY_V1_CONTRACT"


def _fingerprint(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _all_true(values: Mapping[str, object]) -> bool:
    return bool(values) and all(value is True for value in values.values())


def evaluate_multi_asset_final_precheck(
    *,
    identity: Mapping[str, object],
    reclassification: Mapping[str, object],
    scheduler: Mapping[str, object],
    historical_fx: Mapping[str, object],
    kb_sync: Mapping[str, object],
    research_integrity: Mapping[str, object],
) -> dict[str, object]:
    coverage = dict(identity.get("coverage_gate") or {})
    dependency = dict(identity.get("dependency") or {})
    baseline_dependency = dict(
        dict(reclassification.get("dependency_reclassification") or {}).get("baseline")
        or {}
    )
    assessment = dict(reclassification.get("assessment") or {})
    fx_coverage = dict(historical_fx.get("coverage") or {})
    fx_status_counts = dict(fx_coverage.get("status_counts") or {})
    scheduler_checks = dict(scheduler.get("checks") or {})
    sync = dict(kb_sync.get("sync") or {})

    gates = {
        "A_RESEARCH_IDENTITY": {
            "registry_ready": identity.get("status")
            == "IDENTITY_REGISTRY_READY_WITH_VISIBLE_UNKNOWNS",
            "all_listings_present": int(identity.get("record_n") or 0) == 2_520,
            "coverage_gate_passed": coverage.get("status") == "PASS",
            "coverage_threshold_predeclared": coverage.get("not_optimized_on_research_results")
            is True,
            "verified_coverage_sufficient": float(coverage.get("verified_coverage_pct") or 0)
            >= float(coverage.get("minimum_verified_coverage_pct") or 100),
            "critical_conflicts_absent": int(identity.get("conflict_n") or 0) == 0,
            "known_relations_resolved": dict(coverage.get("checks") or {}).get(
                "known_official_dependency_groups_resolved"
            )
            is True,
            "unresolved_fail_closed": dependency.get("unknown_counted_as_independent")
            is False,
            "no_listing_data_mixing": research_integrity.get("listing_bundle_guard_present")
            is True,
        },
        "B_DEPENDENCY_EFFECTIVE_N": {
            "dependency_unknown_visible": int(dependency.get("dependency_unknown") or 0) > 0,
            "unknown_contributes_zero": int(
                baseline_dependency.get("unknown_dependency_contribution_to_effective_n")
                or 0
            )
            == 0,
            "effective_n_bounded": int(
                baseline_dependency.get("effective_independent_issuer_count") or 0
            )
            <= int(baseline_dependency.get("verified_dependency_observation_n") or 0),
            "failed_seller_dependency_coverage_sufficient": float(
                baseline_dependency.get("verified_dependency_coverage_pct") or 0
            )
            >= 80.0,
            "dependency_method_versioned": "maximum_non_overlapping"
            in str(baseline_dependency.get("effective_n_method") or ""),
        },
        "C_RESEARCH_INTEGRITY": {
            **{key: value is True for key, value in research_integrity.items()},
            "failed_seller_inputs_unchanged": reclassification.get(
                "protected_inputs_unchanged"
            )
            is True,
            "failed_seller_raw_metrics_unchanged": reclassification.get(
                "raw_metrics_changed"
            )
            is False,
            "failed_seller_inconclusive_retained": assessment.get(
                "classification_change"
            )
            == "INCONCLUSIVE_RETAINED",
            "kb_result_core_unchanged": sync.get("result_core_unchanged") is True,
            "no_new_research_attempts": int(
                reclassification.get("new_research_attempts") or 0
            )
            == 0,
            "validation_closed": reclassification.get("validation_opened") is False,
            "holdout_closed": reclassification.get("holdout_opened") is False,
        },
        "D_FX_OBSERVER": {
            "historical_partial_coverage_explicit": historical_fx.get("status")
            == "HISTORICAL_FX_PIT_READY_WITH_PARTIAL_COVERAGE",
            "historical_gaps_remain_unavailable": int(fx_status_counts.get("UNAVAILABLE") or 0)
            > 0,
            "no_backdated_macro": historical_fx.get("today_revised_macro_backdated")
            is False,
            "scheduler_audit_passed": scheduler.get("status") == "PASS",
            "exactly_one_scheduler": int(scheduler.get("matching_task_n") or 0) == 1,
            "planned_run_proven": int(scheduler.get("completed_daily_scheduler_run_n") or 0)
            >= 1,
            "scheduler_checks_passed": _all_true(scheduler_checks),
        },
        "E_SAFETY": {
            "multi_asset_scan_not_started": reclassification.get("multi_asset_scan_started")
            is False,
            "strategy_not_activated": reclassification.get("strategy_activated") is False,
            "fx_strategy_signals_forbidden": scheduler.get("strategy_signal_allowed") is False,
            "fx_trade_decisions_forbidden": scheduler.get("trade_decision_allowed") is False,
            "paper_trades_forbidden": scheduler.get("paper_trade_allowed") is False,
            "shadow_orders_forbidden": scheduler.get("shadow_order_allowed") is False,
            "broker_orders_forbidden": scheduler.get("broker_order_allowed") is False,
        },
    }
    gate_status = {
        name: "PASS" if _all_true(checks) else "FAIL" for name, checks in gates.items()
    }
    ready = all(status == "PASS" for status in gate_status.values())
    payload: dict[str, object] = {
        "version": FINAL_PRECHECK_VERSION,
        "status": READY_STATUS if ready else NOT_READY_STATUS,
        "gates": gates,
        "gate_status": gate_status,
        "failed_checks": [
            f"{gate}.{check}"
            for gate, checks in gates.items()
            for check, passed in checks.items()
            if not passed
        ],
        "multi_asset_scan_started": False,
        "strategy_activated": False,
        "validation_opened": False,
        "holdout_opened": False,
        "broker_accessed": False,
    }
    payload["gate_fingerprint"] = _fingerprint(payload)
    return payload
