from __future__ import annotations

import sqlite3

import pytest

from swing_research_quality import (
    ResearchQualityError,
    append_research_hypothesis_event,
    build_research_quality_report,
    entry_efficiency_report,
    execution_stress_report,
    feature_ablation_report,
    forward_research_quality_report,
    parameter_plateau_report,
    placebo_test_suite,
    record_development_quality_ledger,
    regime_matched_placebo,
    register_research_hypothesis,
    research_quality_store_audit,
    robustness_metrics,
    survivorship_bias_audit,
)


def _attempt(path, hypothesis_id="rsi-a", name="RSI A"):
    return register_research_hypothesis(
        hypothesis_id=hypothesis_id,
        name=name,
        description="Vorab festgelegt",
        defined_at="2026-08-23T00:00:00+00:00",
        research_origin="development-plan",
        family_id="rsi",
        features=["technical.rsi_14"],
        parameters={"minimum": 40, "maximum": 70},
        dataset_fingerprint="dataset-1",
        feature_fingerprint="features-1",
        code_fingerprint="code-1",
        path=path,
    )


def _rows():
    return [
        {"candidate_id": "a", "signal_day": "2019-01-02", "issuer_id": "i1", "result_r": 1.0,
         "market_phase": "bull", "volatility_regime": "low", "region": "US", "sector": "tech", "mfe_r": 1.4, "mae_r": -0.3},
        {"candidate_id": "b", "signal_day": "2019-01-02", "issuer_id": "i2", "result_r": -0.5,
         "market_phase": "bull", "volatility_regime": "low", "region": "EU", "sector": "industry", "mfe_r": 0.4, "mae_r": -0.8},
        {"candidate_id": "c", "signal_day": "2020-03-02", "issuer_id": "i1", "result_r": 1.5,
         "market_phase": "bear", "volatility_regime": "high", "region": "US", "sector": "tech", "mfe_r": 2.0, "mae_r": -0.2},
        {"candidate_id": "d", "signal_day": "2021-04-02", "issuer_id": "i4", "result_r": -0.25,
         "market_phase": "bull", "volatility_regime": "low", "region": "EU", "sector": "health", "mfe_r": 0.7, "mae_r": -0.6},
    ]


def test_ledger_is_append_only_and_semantic_duplicate_is_not_counted(tmp_path) -> None:
    path = tmp_path / "quality.sqlite3"
    first = _attempt(path)
    renamed = _attempt(path, hypothesis_id="rsi-renamed", name="Neuer Name")
    assert first["inserted"] is True
    assert renamed["inserted"] is False
    attempt_id = first["attempt"]["attempt_id"]
    result = {"development_accessed": True, "raw_cases": 4}
    one = append_research_hypothesis_event(
        attempt_id, recorded_at="2026-08-23T01:00:00+00:00", action="evaluated", result=result, path=path
    )
    two = append_research_hypothesis_event(
        attempt_id, recorded_at="2026-08-23T02:00:00+00:00", action="evaluated", result=result, path=path
    )
    assert one["inserted"] is True
    assert two["inserted"] is False
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE research_hypothesis_attempts SET hypothesis_id='x'")
    audit = research_quality_store_audit(path)
    assert audit["registered_hypotheses"] == 1
    assert audit["attempts_by_family"] == {"rsi": 1}
    assert audit["invalid_fingerprints"] == 0


def test_ledger_forbids_automatic_tuning_or_production(tmp_path) -> None:
    attempt = _attempt(tmp_path / "quality.sqlite3")["attempt"]
    with pytest.raises(ResearchQualityError, match="Produktion"):
        append_research_hypothesis_event(
            attempt["attempt_id"],
            recorded_at="2026-08-23T01:00:00+00:00",
            action="evaluated",
            result={"production_activated": True},
            path=tmp_path / "quality.sqlite3",
        )


def test_cluster_components_are_reproducible_and_conservative() -> None:
    first = robustness_metrics(_rows())
    second = robustness_metrics(list(reversed(_rows())))
    assert first == second
    assert first["effective_independent_cases"] <= first["raw_cases"]
    # Same issuer links a/c; same signal day links a/b, so a/b/c form one component.
    assert first["effective_independent_cases"] == 2
    assert first["same_day_clusters"] == 3
    assert first["time_stability"]["maximum_temporal_drawdown_r"] == pytest.approx(0.5)
    assert first["time_stability"]["before_2020_expectancy_r"] == pytest.approx(0.25)
    assert first["time_stability"]["from_2020_expectancy_r"] == pytest.approx(0.625)


def test_regime_matched_placebo_is_deterministic_and_uses_no_outcome_for_selection() -> None:
    selected = [_rows()[0], _rows()[2]]
    controls = [
        {**_rows()[0], "candidate_id": "p1", "result_r": -0.2},
        {**_rows()[2], "candidate_id": "p2", "result_r": 0.1},
        {**_rows()[2], "candidate_id": "p3", "result_r": 9.0},
    ]
    first = regime_matched_placebo(selected, controls, seed_material="fixed")
    second = regime_matched_placebo(selected, list(reversed(controls)), seed_material="fixed")
    assert first == second
    assert first["selection_uses_outcomes"] is False
    assert first["future_information_used"] is False
    suite = placebo_test_suite(selected, controls, seed_material="fixed")
    assert suite["tests"]["time_shifted_same_asset"]["status"] == "not_available"


def test_parameter_plateau_is_deterministic_and_never_selects_best() -> None:
    variants = [
        {"parameter_value": 45, "expectancy_r": -0.1, "profit_factor": 0.9, "maximum_drawdown_r": 3, "raw_cases": 80},
        {"parameter_value": 35, "expectancy_r": -0.2, "profit_factor": 0.8, "maximum_drawdown_r": 4, "raw_cases": 120},
        {"parameter_value": 40, "expectancy_r": 0.3, "profit_factor": 1.2, "maximum_drawdown_r": 2, "raw_cases": 100},
    ]
    report = parameter_plateau_report(variants)
    assert [row["parameter_value"] for row in report["variants"]] == [35, 40, 45]
    assert report["isolated_positive_peak"] is True
    assert report["single_best_parameter_selected"] is False
    assert report == parameter_plateau_report(list(reversed(variants)))


def test_feature_ablation_requires_exactly_one_removed_feature() -> None:
    metrics = robustness_metrics(_rows())
    report = feature_ablation_report(
        {"features": ["trend", "bos"], "metrics": metrics},
        [{"removed_feature": "bos", "features": ["trend"], "metrics": metrics}],
    )
    assert report["ablations"][0]["only_removed_feature_changed"] is True
    assert report["ablations"][0]["trade_retention"] == 1.0
    assert report["automatic_feature_removal"] is False
    with pytest.raises(ResearchQualityError, match="genau ein"):
        feature_ablation_report(
            {"features": ["trend", "bos"], "metrics": metrics},
            [{"removed_feature": "bos", "features": [], "metrics": metrics}],
        )


def test_entry_efficiency_is_causal_and_does_not_invent_intrabar_order() -> None:
    report = entry_efficiency_report(
        entry=100,
        stop=95,
        direction="long",
        final_result_r=-0.2,
        bars=[
            {"High": 103, "Low": 97},
            {"High": 106, "Low": 96},
            {"High": 105, "Low": 94},
        ],
    )
    assert report["mfe_r"]["1s"] == pytest.approx(0.6)
    assert report["mfe_r"]["3s"] == pytest.approx(1.2)
    assert report["sessions_to"]["plus_1r"] == 2
    assert report["diagnostic_class"] == "C"
    assert report["intrabar_sequence_claimed"] is False
    ambiguous = entry_efficiency_report(
        entry=100, stop=95, direction="long", bars=[{"High": 103, "Low": 97}]
    )
    assert ambiguous["first_half_r_event"] == "ambiguous_same_daily_bar"


def test_execution_stress_is_separate_and_does_not_rewrite_rows() -> None:
    rows = _rows()
    original = [dict(row) for row in rows]
    report = execution_stress_report(rows)
    assert rows == original
    assert report["scenarios"]["base"]["historical_result_rewritten"] is False
    assert report["scenarios"]["higher_total_cost"]["metrics"]["expectancy_r"] < report["scenarios"]["base"]["metrics"]["expectancy_r"]
    assert report["automatic_rule_change"] is False


def test_survivorship_and_forward_evidence_remain_transparent_and_separate() -> None:
    audit = survivorship_bias_audit(
        uses_current_frozen_universe=True,
        historical_constituents_available=False,
        delistings_available=False,
        bankruptcies_available=False,
        point_in_time_universe_available=False,
    )
    assert audit["survivorship_bias_fully_excluded"] is False
    assert audit["broad_research_blocked"] is False
    rows = [{**_rows()[0], "evidence_type": "forward"}, {**_rows()[1], "evidence_type": "paper"}]
    report = forward_research_quality_report(rows)
    assert set(report["evidence"]) == {"forward", "paper"}
    assert report["evidence_types_merged"] is False


def test_complete_quality_report_requires_manual_review_and_keeps_gates_closed(tmp_path) -> None:
    attempt = _attempt(tmp_path / "quality.sqlite3")["attempt"]
    selected, controls = _rows()[:2], _rows()[2:]
    report = build_research_quality_report(
        attempt=attempt,
        selected_rows=selected,
        eligible_control_rows=controls,
        seed_material="fixed",
        rule={"rsi_min": 40, "rsi_max": 70},
        features=["technical.rsi_14"],
    )
    assert report["abc_result"] == "manual_review_required"
    assert report["validation_opened"] is False
    assert report["holdout_opened"] is False
    assert report["production_activated"] is False
    assert report["automatic_parameter_tuning"] is False
    assert "why_could_this_be_false_positive" in report


def test_development_ledger_resume_dedupes_attempts_and_events(tmp_path) -> None:
    path = tmp_path / "quality.sqlite3"
    report = {
        "pattern_version": "patterns-v1",
        "hypotheses": [
            {"hypothesis_id": "buyer_confirmation", "classification": "B", "selected": {"cases": 50, "effective_independent_cases": 30}, "eligible_for_manual_fixed_challenger": False},
            {"hypothesis_id": "rsi_40_70", "classification": "A", "selected": {"cases": 60, "effective_independent_cases": 40}, "eligible_for_manual_fixed_challenger": False},
        ],
    }
    kwargs = dict(
        dataset_fingerprint="dataset-1",
        feature_fingerprint="features-1",
        code_fingerprint="code-1",
        path=path,
    )
    first = record_development_quality_ledger(report, recorded_at="2026-08-23T01:00:00+00:00", **kwargs)
    second = record_development_quality_ledger(report, recorded_at="2026-08-23T02:00:00+00:00", **kwargs)
    assert first["attempts_inserted"] == 2
    assert first["events_inserted"] == 2
    assert second["attempts_inserted"] == 0
    assert second["events_inserted"] == 0
    assert second["audit"]["validation_mining"] is False
    assert second["audit"]["production_activation"] is False
