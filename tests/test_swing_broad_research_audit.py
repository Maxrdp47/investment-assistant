from __future__ import annotations

import json

import pytest

from swing_broad_research_audit import (
    ALL_SETUPS,
    BROAD_V1_AUDIT_VERSION,
    FUTURE_REPORT_CONTRACT_VERSION,
    HYPOTHESIS_CONTRACTS,
    METRIC_SEMANTICS,
    PARAMETER_NEIGHBORHOODS,
    PROTECTED_CODE_FINGERPRINT,
    PROTECTED_DATASET_FINGERPRINT,
    PROTECTED_FEATURE_CONTRACT_FINGERPRINT,
    SETUP_BREAKOUT,
    SETUP_PULLBACK,
    TEST_SCOPE,
    VALIDITY_NON_DISCRIMINATING,
    VALIDITY_NOT_TESTABLE,
    VALIDITY_PASS,
    VALIDITY_UNDERPOWERED,
    _automatic_performance_grade,
    _depth_bin,
    _fib_review,
    apply_manual_development_review,
    validity_gate,
    write_append_only_json,
)


def _gate(**overrides):
    values = {
        "universe_n": 1_000,
        "applicable_n": 1_000,
        "valid_n": 1_000,
        "structurally_not_applicable_n": 0,
        "missing_n": 0,
        "treatment_n": 500,
        "control_n": 500,
        "treatment_effective_n": 250,
        "control_effective_n": 250,
        "feature_point_in_time_available": True,
        "outcome_independent_definition": True,
        "market_scope_correct": True,
        "setup_scope_correct": True,
        "structural_missingness_treated_as_false": False,
    }
    values.update(overrides)
    return validity_gate(**values)


def test_zero_available_cases_are_not_testable_and_never_b_or_c() -> None:
    gate = _gate(
        valid_n=0,
        missing_n=1_000,
        treatment_n=0,
        control_n=0,
        treatment_effective_n=0,
        control_effective_n=0,
        feature_point_in_time_available=False,
    )
    assert gate["status"] == VALIDITY_NOT_TESTABLE
    assert gate["performance_grade_allowed"] is False
    assert _automatic_performance_grade(gate, {}, {}) is None


def test_treatment_without_meaningful_control_is_non_discriminating() -> None:
    gate = _gate(
        treatment_n=999,
        control_n=1,
        treatment_effective_n=250,
        control_effective_n=1,
    )
    assert gate["status"] == VALIDITY_NON_DISCRIMINATING
    assert gate["performance_grade_allowed"] is False


def test_small_effective_groups_are_underpowered_not_b() -> None:
    gate = _gate(treatment_effective_n=20, control_effective_n=30)
    assert gate["status"] == VALIDITY_UNDERPOWERED
    assert _automatic_performance_grade(gate, {}, {}) is None


def test_structural_missingness_is_never_false_and_scopes_are_explicit() -> None:
    assert HYPOTHESIS_CONTRACTS["buyer_confirmation"]["intended_setup_scope"] == (
        SETUP_PULLBACK,
    )
    assert HYPOTHESIS_CONTRACTS["fibonacci_0618_0786"]["intended_setup_scope"] == (
        SETUP_PULLBACK,
    )
    assert HYPOTHESIS_CONTRACTS["bos_close_break"]["intended_setup_scope"] == (
        SETUP_BREAKOUT,
    )
    assert HYPOTHESIS_CONTRACTS["ema20_above_ema50"]["intended_setup_scope"] == ALL_SETUPS
    assert TEST_SCOPE == ("EQUITIES", "ETF", "CRYPTO")
    assert "FX" not in TEST_SCOPE
    assert HYPOTHESIS_CONTRACTS["cot_available"]["cross_market_transfer_allowed"] is False
    assert _gate()["structural_missingness_is_false"] is False


def test_fib_controls_are_equal_width_continuous_and_have_no_extensions() -> None:
    rows = []
    for index, (depth, result) in enumerate(((0.50, 0.0), (0.65, 0.1), (0.80, 0.2))):
        rows.append(
            {
                "candidate_id": str(index),
                "signal_day": f"2020-01-0{index + 1}",
                "setup_family": SETUP_PULLBACK,
                "dependency_cluster": str(index),
                "asset_type": "Aktie",
                "region": "USA",
                "market_phase": "sideways",
                "volatility_regime": "medium",
                "pullback_depth": depth,
                "result_r": result,
                "fib_extensions_tested": False,
                "gap_affected": False,
            }
        )
    review = _fib_review(rows)
    assert _depth_bin(0.50) == "equal_width_lower_0450_0618"
    assert _depth_bin(0.65) == "fib_0618_0786"
    assert _depth_bin(0.80) == "equal_width_upper_0786_0954"
    assert review["zone_widths"]["all_equal"] is True
    assert review["continuous_pullback_depth"]["threshold_or_zone_optimization"] is False
    assert review["extensions_tested_true_n"] == 0
    assert review["extensions_allowed"] is False


def test_candidate_drawdown_contract_is_not_a_portfolio_claim() -> None:
    assert METRIC_SEMANTICS["portfolio_claim_allowed"] is False
    assert METRIC_SEMANTICS["candidate_sequence_drawdown"] != METRIC_SEMANTICS["portfolio_simulation_drawdown"]
    report = {
        "audit_version": BROAD_V1_AUDIT_VERSION,
        "hypotheses": [],
        "validation_opened": False,
        "holdout_opened": False,
    }
    reviewed = apply_manual_development_review(report, {}, reviewed_at="2026-08-25T12:00:00+02:00")
    assert reviewed["manual_review"]["validation_opened"] is False
    assert reviewed["manual_review"]["holdout_opened"] is False
    assert reviewed["manual_review"]["challenger_created"] is False


def test_only_predeclared_rsi_ema_bos_neighborhoods_exist() -> None:
    assert PARAMETER_NEIGHBORHOODS == (
        ("rsi_lower_bound", "rsi_35_70", 35.0),
        ("rsi_lower_bound", "rsi_40_70", 40.0),
        ("rsi_lower_bound", "rsi_45_70", 45.0),
        ("ema20_to_ema50", "ema_ratio_0_995", 0.995),
        ("ema20_to_ema50", "ema_ratio_1_000", 1.0),
        ("ema20_to_ema50", "ema_ratio_1_005", 1.005),
        ("bos_excess_atr", "bos_excess_0_0", 0.0),
        ("bos_excess_atr", "bos_excess_0_1", 0.1),
        ("bos_excess_atr", "bos_excess_0_2", 0.2),
    )


def test_positive_metrics_only_auto_grade_b_and_never_create_c() -> None:
    gate = _gate()
    assert gate["status"] == VALIDITY_PASS
    grade = _automatic_performance_grade(
        gate,
        {"candidate_expectancy_r": 0.2},
        {"candidate_expectancy_r": 0.0},
    )
    assert grade == "B"


def test_manual_review_rejects_post_hoc_c_and_multiple_c() -> None:
    base_row = {
        "validity": {"status": VALIDITY_PASS},
        "quality_review_complete": True,
    }
    report = {
        "hypotheses": [
            {"hypothesis_id": "buyer_confirmation", **base_row},
            {"hypothesis_id": "fibonacci_0618_0786", **base_row},
            {
                "hypothesis_id": "three_or_more_bearish_candles",
                **base_row,
                "post_hoc_direction_reversal": True,
            },
        ],
        "validation_opened": False,
        "holdout_opened": False,
    }
    with pytest.raises(ValueError, match="Post-hoc"):
        apply_manual_development_review(
            report,
            {"three_or_more_bearish_candles": {"recommendation": "C_RECOMMENDATION"}},
            reviewed_at="2026-08-25T12:00:00+02:00",
        )
    with pytest.raises(ValueError, match="At most one"):
        apply_manual_development_review(
            report,
            {
                "buyer_confirmation": {"recommendation": "C_RECOMMENDATION"},
                "fibonacci_0618_0786": {"recommendation": "C_RECOMMENDATION"},
            },
            reviewed_at="2026-08-25T12:00:00+02:00",
        )


def test_append_only_report_never_overwrites(tmp_path) -> None:
    path = tmp_path / "audit.json"
    report = {"report_fingerprint": "one", "contract": FUTURE_REPORT_CONTRACT_VERSION}
    assert write_append_only_json(report, path)["created"] is True
    assert write_append_only_json(report, path)["created"] is False
    with pytest.raises(RuntimeError, match="Append-only"):
        write_append_only_json({"report_fingerprint": "two"}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["report_fingerprint"] == "one"


def test_protected_broad_v1_fingerprints_are_exact() -> None:
    assert PROTECTED_DATASET_FINGERPRINT == "e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed"
    assert PROTECTED_FEATURE_CONTRACT_FINGERPRINT == "c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd"
    assert PROTECTED_CODE_FINGERPRINT == "77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946"
