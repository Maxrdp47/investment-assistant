from __future__ import annotations

"""Future-only Swing research plans that do not alter the active Broad pass."""

import hashlib
import json
import math
from typing import Mapping

from swing_research_market_scope import market_scope_contract


PULLBACK_SELLER_ATTEMPTS_PLAN_VERSION = (
    "swing-pullback-seller-attempts-plan-2026.08.23-v1"
)
RESEARCH_SCOPE_CATALOG_VERSION = "swing-research-scope-catalog-2026.08.23-v1"


def _fingerprinted(payload: dict[str, object], field: str) -> dict[str, object]:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    payload[field] = hashlib.sha256(encoded).hexdigest()
    return payload


def close_location_feature(
    *,
    close: float,
    low: float,
    high: float,
) -> float | None:
    """Causal close location for a completed bar; a zero-range bar is missing."""
    try:
        values = (float(close), float(low), float(high))
    except (TypeError, ValueError):
        return None
    close, low, high = values
    if not all(math.isfinite(value) for value in values):
        return None
    if high < low or close < low or close > high:
        return None
    if high == low:
        return None
    return (close - low) / (high - low)


def pullback_seller_attempts_research_plan() -> dict[str, object]:
    plan = {
        "version": PULLBACK_SELLER_ATTEMPTS_PLAN_VERSION,
        "status": "PLANNED_FOR_NEW_RESEARCH_EPOCH_NOT_IMPLEMENTED",
        "scope": market_scope_contract(
            source_scopes=["GENERAL_METHOD"],
            test_scopes=["EQUITIES"],
        ),
        "current_broad_pass_changed": False,
        "active_baseline_changed": False,
        "live_signal_influence": False,
        "new_strategy_branch_created": False,
        "feature_role": "OBSERVATIONAL_RESEARCH_ONLY",
        "causal_cutoff": "including_only_the_completed_confirmation_bar",
        "continuous_features_primary": [
            "bearish_push_count",
            "push_depth_atr_each",
            "push_recovery_fraction_each",
            "sessions_to_recovery_each",
            "failed_seller_attempts",
            "confirmation_close_location",
        ],
        "predeclared_push_definition": {
            "window": "existing_objective_pullback_start_through_completed_confirmation_bar",
            "push_start": (
                "first completed bar with both close below previous close and low below previous low"
            ),
            "push_membership": (
                "maximal consecutive completed-bar run while close declines or a new local low is set"
            ),
            "push_separation": (
                "at least one completed bar with neither a lower close nor a lower low"
            ),
            "new_relevant_low": (
                "push minimum low below the running objective pullback low before that push"
            ),
            "sustained_structure_break": (
                "at least two completed closes below the objective pre-push swing low before confirmation"
            ),
            "push_depth_atr": (
                "push start reference high minus push minimum low, divided by ATR known before push start"
            ),
            "recovery_fraction": (
                "maximum subsequent completed close through confirmation minus push low, divided by "
                "push start reference high minus push low"
            ),
            "time_to_recovery": (
                "completed sessions from push low to first close at or above push start reference high"
            ),
            "failed_seller_attempt": (
                "push without sustained structure break that reaches full recovery before confirmation"
            ),
            "definitions_must_freeze_before_labels": True,
        },
        "close_location": {
            "formula": "(close - low) / (high - low)",
            "high_equals_low": "missing_not_zero_not_one",
            "completed_confirmation_bar_only": True,
        },
        "limited_comparison_hypotheses": [
            "failed_seller_attempts_exactly_2_vs_all_other_counts",
            "confirmation_close_exactly_at_high",
            "confirmation_close_location_gte_0_90",
            "confirmation_close_location_gte_0_80",
        ],
        "exhaustive_threshold_search": False,
        "post_hoc_best_threshold_selection": False,
        "evaluation_targets": [
            "forward_returns",
            "mfe",
            "mae",
            "expectancy_after_costs",
            "incremental_value_for_existing_pullback_signals",
        ],
        "validation": {
            "development_first": True,
            "oos_required": True,
            "walk_forward_required": True,
            "market_scope_specific": True,
            "small_samples_do_not_prove_value": True,
        },
        "confluence_gate": {
            "opening_levels": "only_after_standalone_value",
            "volume_profile": "only_after_standalone_value",
            "other_features": "only_after_each_standalone_value",
        },
        "no_robust_incremental_value": {
            "action": "REJECT_FEATURE_HYPOTHESIS",
            "knowledge_base_outcome": "NEGATIVE",
            "negative_result_must_remain_visible": True,
        },
        "automatic_strategy_change": False,
        "automatic_activation": False,
    }
    return _fingerprinted(plan, "plan_fingerprint")


def existing_research_market_scope_catalog() -> dict[str, object]:
    """Scope planning only; it does not relabel historical results as validated."""
    assignments: dict[str, Mapping[str, object]] = {
        "pullback": {"source_scope": ["GENERAL_METHOD"], "test_scope": ["EQUITIES"]},
        "momentum": {"source_scope": ["GENERAL_METHOD"], "test_scope": ["EQUITIES"]},
        "bos": {"source_scope": ["GENERAL_METHOD"], "test_scope": ["EQUITIES"]},
        "candle_close_location": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
        },
        "opening_levels": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
        },
        "volume_profile": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
        },
        "objective_key_levels": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
        },
        "stop_exit_methods": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
        },
        "fibonacci": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
            "role": "RESEARCH_HYPOTHESIS_ONLY",
        },
        "seasonality": {
            "source_scope": ["GENERAL_METHOD"],
            "test_scope": ["EQUITIES"],
            "each_asset_class_requires_separate_validation": True,
        },
        "cot_direct_positioning": {
            "source_scope": ["FUTURES", "FX"],
            "test_scope": ["FUTURES", "FX"],
        },
        "cot_equity_regime_transfer": {
            "source_scope": ["FUTURES", "FX", "CROSS_ASSET"],
            "test_scope": ["EQUITIES"],
            "new_independent_equity_experiment_required": True,
        },
        "rate_differentials": {"source_scope": ["FX"], "test_scope": ["FX"]},
        "expected_rate_differentials": {
            "source_scope": ["FX"],
            "test_scope": ["FX"],
        },
        "carry_to_risk": {"source_scope": ["FX"], "test_scope": ["FX"]},
        "central_bank_surprise": {
            "source_scope": ["FX", "CROSS_ASSET"],
            "test_scope": ["FX"],
        },
        "fx_macro_bias": {"source_scope": ["FX"], "test_scope": ["FX"]},
        "fx_macro_cot_seasonality_bias": {
            "source_scope": ["FX", "FUTURES", "CROSS_ASSET"],
            "test_scope": ["FX"],
        },
        "macro_surprise": {
            "source_scope": ["CROSS_ASSET"],
            "test_scope": ["EQUITIES"],
            "each_new_asset_class_requires_new_experiment": True,
        },
    }
    catalog = {
        "version": RESEARCH_SCOPE_CATALOG_VERSION,
        "status": "PLANNING_ASSIGNMENTS_NOT_RETROACTIVE_VALIDATION",
        "assignments": assignments,
        "existing_research_removed": False,
        "legacy_results_without_scope": "LEGACY_SCOPE_NOT_RECORDED",
        "legacy_scope_inferred_from_performance": False,
        "automatic_activation": False,
    }
    return _fingerprinted(catalog, "catalog_fingerprint")
