from __future__ import annotations

import copy

import pytest

from swing_campaign_v2 import (
    campaign_v2_methodology_contract,
    prepare_v2_hypothesis,
    reserve_abc_v2_pools,
)
from swing_future_research_plans import (
    close_location_feature,
    existing_research_market_scope_catalog,
    pullback_seller_attempts_research_plan,
)
from swing_research_market_scope import (
    MARKET_SCOPES,
    MarketScopeError,
    assert_market_scope_activation_allowed,
    build_research_knowledge_entry,
    build_scoped_research_feature,
    build_scoped_research_experiment,
    build_scoped_research_hypothesis,
    build_scoped_research_result,
    legacy_unscoped_research_contract,
    market_scope_contract,
    normalize_market_scopes,
    prepare_cross_market_transfer,
)


def _hypothesis(*, source=("FX",), tested=("FX",)) -> dict[str, object]:
    return build_scoped_research_hypothesis(
        hypothesis_id="carry-change-v1",
        name="Expected rate differential change",
        origin="cross-market scope contract test",
        source_scopes=source,
        test_scopes=tested,
    )


def _experiment(
    hypothesis: dict[str, object],
    *,
    tested=("FX",),
) -> dict[str, object]:
    return build_scoped_research_experiment(
        experiment_id="carry-change-eurusd-v1",
        hypothesis=hypothesis,
        test_scopes=tested,
        asset_universe="frozen-point-in-time-fx-universe-v1",
        period_start="2012-01-01",
        period_end="2025-12-31",
        timeframe="daily",
        baseline="matched-holding-period-fx-baseline-v1",
        split_design="purged-development-validation-holdout-walk-forward-v1",
    )


def _validated_fx_result() -> dict[str, object]:
    return build_scoped_research_result(
        experiment=_experiment(_hypothesis()),
        sample_size=420,
        is_status="PASSED",
        oos_status="PASSED",
        walk_forward_status="PASSED",
        result_status="VALIDATED",
        validated_scopes=["FX"],
    )


def test_market_scope_vocabulary_is_exact_and_supports_multiple_scopes() -> None:
    assert MARKET_SCOPES == (
        "EQUITIES",
        "ETF",
        "FX",
        "FUTURES",
        "COMMODITIES",
        "CRYPTO",
        "CROSS_ASSET",
        "GENERAL_METHOD",
    )
    assert normalize_market_scopes(["crypto", "fx", "FUTURES", "FX"]) == (
        "FX",
        "FUTURES",
        "CRYPTO",
    )
    with pytest.raises(MarketScopeError, match="mindestens"):
        normalize_market_scopes([])
    with pytest.raises(MarketScopeError, match="unbekannte"):
        normalize_market_scopes(["REAL_ESTATE"])
    with pytest.raises(MarketScopeError, match="Liste"):
        normalize_market_scopes("FX")


def test_hypothesis_experiment_and_result_keep_source_and_test_scope() -> None:
    hypothesis = _hypothesis(source=("FX", "FUTURES"), tested=("FX",))
    experiment = _experiment(hypothesis)
    result = build_scoped_research_result(
        experiment=experiment,
        sample_size=420,
        is_status="PASSED",
        oos_status="PASSED",
        walk_forward_status="PASSED",
        result_status="VALIDATED",
        validated_scopes=["FX"],
    )

    assert hypothesis["scope"]["source_scope"] == ["FX", "FUTURES"]
    assert hypothesis["scope"]["test_scope"] == ["FX"]
    assert experiment["source_scope"] == ["FX", "FUTURES"]
    assert experiment["test_scope"] == ["FX"]
    assert result["source_scope"] == ["FX", "FUTURES"]
    assert result["test_scope"] == ["FX"]
    assert result["asset_universe"] == "frozen-point-in-time-fx-universe-v1"
    assert result["period"] == {"start": "2012-01-01", "end": "2025-12-31"}
    assert result["timeframe"] == "daily"
    assert result["baseline"] == "matched-holding-period-fx-baseline-v1"
    assert result["sample_size"] == 420
    assert result["is_status"] == "PASSED"
    assert result["oos_status"] == "PASSED"
    assert result["walk_forward_status"] == "PASSED"


def test_research_feature_has_its_own_scope_and_no_live_influence() -> None:
    feature = build_scoped_research_feature(
        feature_id="confirmation-close-location-v1",
        name="Confirmation candle close location",
        definition="(close-low)/(high-low); zero range is missing",
        causal_cutoff="completed confirmation candle",
        source_scopes=["GENERAL_METHOD"],
        test_scopes=["EQUITIES", "ETF"],
    )

    assert feature["record_type"] == "research_feature_scope"
    assert feature["scope"]["source_scope"] == ["GENERAL_METHOD"]
    assert feature["scope"]["test_scope"] == ["EQUITIES", "ETF"]
    assert feature["status"] == "REGISTERED_RESEARCH_ONLY"
    assert feature["cross_market_validation_inherited"] is False
    assert feature["live_signal_influence"] is False
    assert feature["automatic_activation"] is False


def test_result_scope_is_deterministic_and_does_not_mutate_inputs() -> None:
    hypothesis = _hypothesis()
    experiment = _experiment(hypothesis)
    original_hypothesis = copy.deepcopy(hypothesis)
    original_experiment = copy.deepcopy(experiment)

    first = build_scoped_research_result(
        experiment=experiment,
        sample_size=420,
        is_status="PASSED",
        oos_status="PASSED",
        walk_forward_status="PASSED",
        result_status="VALIDATED",
        validated_scopes=["FX"],
    )
    second = build_scoped_research_result(
        experiment=experiment,
        sample_size=420,
        is_status="PASSED",
        oos_status="PASSED",
        walk_forward_status="PASSED",
        result_status="VALIDATED",
        validated_scopes=["FX"],
    )

    assert first == second
    assert hypothesis == original_hypothesis
    assert experiment == original_experiment


def test_validated_fx_result_cannot_activate_equities() -> None:
    result = _validated_fx_result()

    fx_gate = assert_market_scope_activation_allowed(result, target_scope="FX")

    assert fx_gate["scope_gate_passed"] is True
    assert fx_gate["scope_gate_is_not_strategy_release"] is True
    assert fx_gate["automatic_activation"] is False
    with pytest.raises(MarketScopeError, match="passend validierten"):
        assert_market_scope_activation_allowed(result, target_scope="EQUITIES")


def test_validated_crypto_result_cannot_activate_another_market_scope() -> None:
    hypothesis = _hypothesis(source=("CRYPTO",), tested=("CRYPTO",))
    experiment = _experiment(hypothesis, tested=("CRYPTO",))
    result = build_scoped_research_result(
        experiment=experiment,
        sample_size=360,
        is_status="PASSED",
        oos_status="PASSED",
        walk_forward_status="PASSED",
        result_status="VALIDATED",
        validated_scopes=["CRYPTO"],
    )

    assert assert_market_scope_activation_allowed(
        result, target_scope="CRYPTO"
    )["scope_gate_passed"] is True
    with pytest.raises(MarketScopeError, match="passend validierten"):
        assert_market_scope_activation_allowed(result, target_scope="EQUITIES")


def test_validated_without_matching_scope_is_never_enough() -> None:
    malformed = copy.deepcopy(_validated_fx_result())
    malformed["validated_scopes"] = []

    with pytest.raises(MarketScopeError, match="Fingerabdruck"):
        assert_market_scope_activation_allowed(malformed, target_scope="FX")
    with pytest.raises(MarketScopeError, match="direkt aktivieren"):
        assert_market_scope_activation_allowed(_validated_fx_result(), target_scope="CROSS_ASSET")


def test_scope_fingerprints_block_relabeling_after_results() -> None:
    result = _validated_fx_result()
    result["validated_scopes"] = ["EQUITIES"]
    result["test_scope"] = ["EQUITIES"]

    with pytest.raises(MarketScopeError, match="Fingerabdruck"):
        assert_market_scope_activation_allowed(result, target_scope="EQUITIES")
    with pytest.raises(MarketScopeError, match="Fingerabdruck"):
        prepare_cross_market_transfer(
            source_result=result,
            transfer_experiment_id="tampered-transfer-v1",
            target_scopes=["COMMODITIES"],
        )


def test_cross_market_transfer_creates_new_unvalidated_experiment() -> None:
    result = _validated_fx_result()

    transfer = prepare_cross_market_transfer(
        source_result=result,
        transfer_experiment_id="cot-fx-to-equities-v1",
        target_scopes=["EQUITIES"],
    )

    assert transfer["source_scope"] == ["FX"]
    assert transfer["test_scope"] == ["EQUITIES"]
    assert transfer["status"] == "INDEPENDENT_EXPERIMENT_REQUIRED"
    assert transfer["inherited_validated_scopes"] == []
    assert transfer["inherited_performance_evidence"] is False
    assert transfer["new_oos_and_walk_forward_required"] is True
    assert transfer["automatic_activation"] is False


def test_equity_transfer_can_pass_scope_gate_only_after_equity_oos() -> None:
    hypothesis = _hypothesis(source=("FX", "FUTURES", "CROSS_ASSET"), tested=("EQUITIES",))
    experiment = _experiment(hypothesis, tested=("EQUITIES",))
    equity_result = build_scoped_research_result(
        experiment=experiment,
        sample_size=310,
        is_status="PASSED",
        oos_status="PASSED",
        walk_forward_status="PASSED",
        result_status="VALIDATED",
        validated_scopes=["EQUITIES"],
    )

    assert assert_market_scope_activation_allowed(
        equity_result, target_scope="EQUITIES"
    )["scope_gate_passed"] is True
    with pytest.raises(MarketScopeError):
        assert_market_scope_activation_allowed(equity_result, target_scope="FX")


def test_new_unplanned_test_scope_is_rejected_before_experiment() -> None:
    with pytest.raises(MarketScopeError, match="neue unabhängige"):
        _experiment(_hypothesis(), tested=("EQUITIES",))


def test_validated_requires_oos_and_walk_forward_for_that_scope() -> None:
    with pytest.raises(MarketScopeError, match="OOS- und Walk-Forward"):
        build_scoped_research_result(
            experiment=_experiment(_hypothesis()),
            sample_size=420,
            is_status="PASSED",
            oos_status="PASSED",
            walk_forward_status="UNDERPOWERED",
            result_status="VALIDATED",
            validated_scopes=["FX"],
        )


def test_negative_result_is_first_class_scoped_knowledge() -> None:
    hypothesis = _hypothesis(source=("GENERAL_METHOD",), tested=("EQUITIES",))
    experiment = _experiment(hypothesis, tested=("EQUITIES",))
    result = build_scoped_research_result(
        experiment=experiment,
        sample_size=260,
        is_status="FAILED",
        oos_status="FAILED",
        walk_forward_status="FAILED",
        result_status="REJECTED",
        rejected_scopes=["EQUITIES"],
    )
    knowledge = build_research_knowledge_entry(
        knowledge_id="seller-attempts-equities-negative-v1",
        origin="future pullback seller-attempts research",
        source_scopes=result["source_scope"],
        test_scopes=result["test_scope"],
        result_scope_fingerprint=result["result_scope_fingerprint"],
        outcome="NEGATIVE",
        rejected_scopes=result["rejected_scopes"],
    )

    assert knowledge["source_scope"] == ["GENERAL_METHOD"]
    assert knowledge["test_scope"] == ["EQUITIES"]
    assert knowledge["validated_scopes"] == []
    assert knowledge["rejected_scopes"] == ["EQUITIES"]
    assert knowledge["negative_results_are_first_class_knowledge"] is True
    assert knowledge["cross_market_transfer_is_evidence"] is False


def test_legacy_results_without_scope_fail_closed_without_rewrite() -> None:
    contract = legacy_unscoped_research_contract()

    assert contract["status"] == "LEGACY_SCOPE_NOT_RECORDED"
    assert contract["scope_may_be_inferred_from_positive_result"] is False
    assert contract["activation_allowed"] is False
    assert contract["migration_may_rewrite_old_evidence"] is False
    assert contract["new_scoped_validation_required_before_activation"] is True


def test_close_location_is_continuous_and_zero_range_is_missing() -> None:
    assert close_location_feature(close=109.0, low=100.0, high=110.0) == pytest.approx(0.9)
    assert close_location_feature(close=110.0, low=100.0, high=110.0) == 1.0
    assert close_location_feature(close=100.0, low=100.0, high=100.0) is None
    assert close_location_feature(close=111.0, low=100.0, high=110.0) is None
    assert close_location_feature(close=float("nan"), low=100.0, high=110.0) is None


def test_pullback_extension_is_planned_observational_and_threshold_limited() -> None:
    plan = pullback_seller_attempts_research_plan()

    assert plan["status"] == "PLANNED_FOR_NEW_RESEARCH_EPOCH_NOT_IMPLEMENTED"
    assert plan["scope"]["source_scope"] == ["GENERAL_METHOD"]
    assert plan["scope"]["test_scope"] == ["EQUITIES"]
    assert plan["current_broad_pass_changed"] is False
    assert plan["active_baseline_changed"] is False
    assert plan["feature_role"] == "OBSERVATIONAL_RESEARCH_ONLY"
    assert plan["continuous_features_primary"] == [
        "bearish_push_count",
        "push_depth_atr_each",
        "push_recovery_fraction_each",
        "sessions_to_recovery_each",
        "failed_seller_attempts",
        "confirmation_close_location",
    ]
    assert plan["limited_comparison_hypotheses"] == [
        "failed_seller_attempts_exactly_2_vs_all_other_counts",
        "confirmation_close_exactly_at_high",
        "confirmation_close_location_gte_0_90",
        "confirmation_close_location_gte_0_80",
    ]
    assert plan["exhaustive_threshold_search"] is False
    assert plan["post_hoc_best_threshold_selection"] is False
    assert plan["validation"]["oos_required"] is True
    assert plan["validation"]["walk_forward_required"] is True
    assert plan["no_robust_incremental_value"]["knowledge_base_outcome"] == "NEGATIVE"
    assert plan["automatic_activation"] is False
    assert len(plan["plan_fingerprint"]) == 64
    assert plan == pullback_seller_attempts_research_plan()


def test_existing_research_scope_catalog_preserves_all_requested_families() -> None:
    catalog = existing_research_market_scope_catalog()
    assignments = catalog["assignments"]

    assert set(assignments) >= {
        "pullback",
        "momentum",
        "bos",
        "candle_close_location",
        "opening_levels",
        "volume_profile",
        "objective_key_levels",
        "stop_exit_methods",
        "fibonacci",
        "seasonality",
        "cot_direct_positioning",
        "cot_equity_regime_transfer",
        "rate_differentials",
        "expected_rate_differentials",
        "carry_to_risk",
        "central_bank_surprise",
        "fx_macro_bias",
        "fx_macro_cot_seasonality_bias",
        "macro_surprise",
        "overnight_intraday_return_decomposition",
    }
    assert catalog["existing_research_removed"] is False
    assert catalog["legacy_results_without_scope"] == "LEGACY_SCOPE_NOT_RECORDED"
    assert catalog["legacy_scope_inferred_from_performance"] is False
    assert catalog["automatic_activation"] is False
    assert len(catalog["catalog_fingerprint"]) == 64
    for assignment in assignments.values():
        normalize_market_scopes(assignment["source_scope"], field="source_scope")
        normalize_market_scopes(assignment["test_scope"], field="test_scope")

    overnight = assignments["overnight_intraday_return_decomposition"]
    assert overnight["source_scope"] == ["EQUITIES", "ETF"]
    assert overnight["test_scope"] == ["EQUITIES", "ETF"]
    assert overnight["role"] == "OBSERVATIONAL_RESEARCH_ONLY"
    assert overnight["active_trade_rule"] is False


def test_v2_hypothesis_and_campaign_require_explicit_market_scope() -> None:
    registration = prepare_v2_hypothesis(
        family="pullback-seller-attempts",
        question="Liefern gescheiterte Verkäufer-Pushs Equity-Zusatznutzen?",
        source_market_scopes=["GENERAL_METHOD"],
        test_market_scopes=["EQUITIES"],
        stage="entry",
        changed_dimensions=["entry"],
        frozen_stage_fingerprints={},
        predeclared_parameters={"entry": {"failed_seller_attempts": [2]}},
        dataset_fingerprint="future-equities-dataset-v2",
        feature_fingerprint="future-pullback-feature-v2",
        code_fingerprint="future-code-v2",
        family_attempt_ordinal=1,
    )
    candidate = {
        "candidate_id": "equity-candidate-1",
        "signal_day": "2024-01-02",
        "label_end_day": "2024-02-06",
        "ticker": "AAA",
        "listing_id": "AAA-XNYS",
        "issuer_id": "issuer-aaa",
        "economic_instrument_id": "instrument-aaa",
        "asset_type": "stock",
        "region": "North America",
        "market_phase": "bull",
        "volatility_regime": "normal",
        "setup_type": "pullback",
        "evaluation_horizon_sessions": 25,
    }
    campaign = reserve_abc_v2_pools(
        [candidate],
        challenger_version="seller-attempts-equity-v2",
        challenger_fingerprint="challenger-v2",
        dataset_fingerprint="future-equities-dataset-v2",
        market_scopes=["EQUITIES"],
        seed="scope-test-v2",
        minimum_effective_n_per_round=40,
    )

    assert registration["market_scope_contract"]["source_scope"] == ["GENERAL_METHOD"]
    assert registration["market_scope_contract"]["test_scope"] == ["EQUITIES"]
    assert campaign["market_scope"] == ["EQUITIES"]
    assert campaign_v2_methodology_contract()["evidence_gates"][
        "validated_plus_matching_market_scope_required"
    ] is True


def test_v2_campaign_rejects_only_general_or_cross_asset_scope() -> None:
    candidate = {
        "candidate_id": "method-candidate-1",
        "signal_day": "2024-01-02",
        "ticker": "AAA",
    }
    with pytest.raises(ValueError, match="konkreten Asset-Market-Scope"):
        reserve_abc_v2_pools(
            [candidate],
            challenger_version="method-v2",
            challenger_fingerprint="challenger-v2",
            dataset_fingerprint="dataset-v2",
            market_scopes=["GENERAL_METHOD", "CROSS_ASSET"],
            seed="scope-test-v2",
            minimum_effective_n_per_round=40,
        )
