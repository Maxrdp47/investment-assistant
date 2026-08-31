from __future__ import annotations

import copy

from multi_asset_final_precheck import (
    NOT_READY_STATUS,
    READY_STATUS,
    evaluate_multi_asset_final_precheck,
)


def _inputs() -> dict[str, object]:
    return {
        "identity": {
            "status": "IDENTITY_REGISTRY_READY_WITH_VISIBLE_UNKNOWNS",
            "record_n": 2520,
            "conflict_n": 0,
            "coverage_gate": {
                "status": "PASS",
                "not_optimized_on_research_results": True,
                "verified_coverage_pct": 87.55,
                "minimum_verified_coverage_pct": 80.0,
                "checks": {"known_official_dependency_groups_resolved": True},
            },
            "dependency": {
                "dependency_unknown": 340,
                "unknown_counted_as_independent": False,
            },
        },
        "reclassification": {
            "dependency_reclassification": {
                "baseline": {
                    "unknown_dependency_contribution_to_effective_n": 0,
                    "effective_independent_issuer_count": 69534,
                    "verified_dependency_observation_n": 338229,
                    "verified_dependency_coverage_pct": 89.23,
                    "effective_n_method": (
                        "verified_issuer_maximum_non_overlapping_conservative_windows"
                    ),
                }
            },
            "assessment": {"classification_change": "INCONCLUSIVE_RETAINED"},
            "protected_inputs_unchanged": True,
            "raw_metrics_changed": False,
            "new_research_attempts": 0,
            "validation_opened": False,
            "holdout_opened": False,
            "multi_asset_scan_started": False,
            "strategy_activated": False,
        },
        "scheduler": {
            "status": "PASS",
            "matching_task_n": 1,
            "completed_daily_scheduler_run_n": 2,
            "checks": {"one": True, "two": True},
            "strategy_signal_allowed": False,
            "trade_decision_allowed": False,
            "paper_trade_allowed": False,
            "shadow_order_allowed": False,
            "broker_order_allowed": False,
        },
        "historical_fx": {
            "status": "HISTORICAL_FX_PIT_READY_WITH_PARTIAL_COVERAGE",
            "today_revised_macro_backdated": False,
            "coverage": {"status_counts": {"AVAILABLE_PIT": 51, "UNAVAILABLE": 510}},
        },
        "kb_sync": {"sync": {"result_core_unchanged": True}},
        "research_integrity": {
            "broad_v1_snapshot_unchanged": True,
            "frozen_dataset_manifest_unchanged": True,
            "buyer_development_artifact_unchanged": True,
            "buyer_validation_terminal_and_holdout_closed": True,
            "failed_seller_original_report_unchanged": True,
            "listing_bundle_guard_present": True,
        },
    }


def test_ready_requires_every_gate_and_never_starts_scan() -> None:
    result = evaluate_multi_asset_final_precheck(**_inputs())
    assert result["status"] == READY_STATUS
    assert set(result["gate_status"].values()) == {"PASS"}
    assert result["multi_asset_scan_started"] is False
    assert result["strategy_activated"] is False


def test_unknown_counted_independent_fails_closed() -> None:
    values = copy.deepcopy(_inputs())
    values["identity"]["dependency"]["unknown_counted_as_independent"] = True
    result = evaluate_multi_asset_final_precheck(**values)
    assert result["status"] == NOT_READY_STATUS
    assert "A_RESEARCH_IDENTITY.unresolved_fail_closed" in result["failed_checks"]
