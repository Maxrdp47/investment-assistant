from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from long_term_analysis import (
    ENTRY_TIMING_SECTION,
    LONG_TERM_SECTION_REQUIREMENTS,
    LongTermEvidence,
    LongTermSource,
    assess_long_term_readiness,
)
from long_term_scoring import (
    LONG_TERM_FACTOR_DEFINITIONS,
    LONG_TERM_SCORING_MODEL_VERSION,
    LongTermFactorAssessment,
    LongTermScenario,
    score_long_term_assessment,
)


TEST_AS_OF = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


def complete_readiness():
    sources = [
        LongTermSource(
            "annual",
            "Geschäftsbericht",
            "https://example.com/annual",
            "Example AG",
            "annual_report",
            "2026-08-02T18:00:00+02:00",
            "Long-Term-Research",
        ),
        LongTermSource(
            "industry",
            "Branchenstudie",
            "https://example.com/industry",
            "Research Institute",
            "industry_research",
            "2026-08-02T18:00:00+02:00",
            "Long-Term-Research",
        ),
        LongTermSource(
            "market",
            "Marktdaten",
            "https://example.com/market",
            "Exchange",
            "market_data",
            "2026-08-02T18:00:00+02:00",
            "Long-Term-Research",
        ),
    ]
    references = {
        "business_model": ("annual",),
        "revenue_model": ("annual",),
        "market_opportunity": ("industry",),
        "competitive_position": ("annual", "industry"),
        "management_capital_allocation": ("annual",),
        "financial_quality": ("annual",),
        "valuation": ("market",),
        "long_term_risks": ("annual",),
        "scenarios": ("annual", "industry"),
        "thesis_conditions": ("annual", "industry"),
    }
    evidence = [
        LongTermEvidence(section, f"Belegte Aussage {section}.", source_ids)
        for section, source_ids in references.items()
    ]
    return assess_long_term_readiness(sources, evidence, as_of=TEST_AS_OF)


def complete_factors(score: float = 7.0) -> list[LongTermFactorAssessment]:
    return [
        LongTermFactorAssessment(key, score, f"Begründung für {key}.", definition.required_sections)
        for key, definition in LONG_TERM_FACTOR_DEFINITIONS.items()
    ]


def complete_scenarios() -> list[LongTermScenario]:
    return [
        LongTermScenario("Bear", 25.0, 70.0, ("These entwickelt sich schwächer.",)),
        LongTermScenario("Basis", 50.0, 140.0, ("Zentrale Annahmen erfüllen sich.",)),
        LongTermScenario("Bull", 25.0, 220.0, ("Markt und Wettbewerb entwickeln sich günstig.",)),
    ]


def test_incomplete_evidence_never_produces_score_or_return() -> None:
    readiness = assess_long_term_readiness([], [])

    result = score_long_term_assessment(
        readiness,
        complete_factors(),
        complete_scenarios(),
        current_value=100.0,
        horizon_years=5,
    )

    assert result.ready is False
    assert result.weighted_score is None
    assert result.expected_annualized_return_pct is None
    assert result.factor_assessments == ()
    assert result.scenarios == ()


def test_complete_evidence_calculates_separate_scores_and_three_scenarios() -> None:
    result = score_long_term_assessment(
        complete_readiness(),
        complete_factors(),
        complete_scenarios(),
        current_value=100.0,
        horizon_years=5,
    )

    assert result.ready is True
    assert result.scoring_model_version == LONG_TERM_SCORING_MODEL_VERSION
    assert result.weighted_score == pytest.approx(7.0)
    assert result.company_quality_score == pytest.approx(7.0)
    assert result.future_potential_score == pytest.approx(7.0)
    assert result.valuation_score == pytest.approx(7.0)
    assert result.capital_preservation_score == pytest.approx(7.0)
    assert result.expected_target_value == pytest.approx(142.5)
    assert result.expected_total_return_pct == pytest.approx(42.5)
    assert result.expected_annualized_return_pct == pytest.approx((1.425 ** 0.2 - 1.0) * 100.0)
    assert [scenario.name for scenario in result.scenarios] == ["Bear", "Basis", "Bull"]


def test_technical_entry_timing_cannot_support_factor_score() -> None:
    factors = complete_factors()
    factors[0] = replace(
        factors[0],
        evidence_sections=(*factors[0].evidence_sections, ENTRY_TIMING_SECTION),
    )

    with pytest.raises(ValueError, match="Einstiegstiming"):
        score_long_term_assessment(
            complete_readiness(),
            factors,
            complete_scenarios(),
            current_value=100.0,
            horizon_years=5,
        )


def test_missing_or_duplicate_factor_is_rejected() -> None:
    missing = complete_factors()[:-1]
    duplicate = [*complete_factors(), complete_factors()[0]]

    with pytest.raises(ValueError, match="fehlen"):
        score_long_term_assessment(
            complete_readiness(), missing, complete_scenarios(), current_value=100.0, horizon_years=5
        )
    with pytest.raises(ValueError, match="doppelt"):
        score_long_term_assessment(
            complete_readiness(), duplicate, complete_scenarios(), current_value=100.0, horizon_years=5
        )


@pytest.mark.parametrize("score", [-0.1, 10.1, float("nan"), float("inf")])
def test_non_finite_or_out_of_range_factor_scores_are_rejected(score: float) -> None:
    factors = complete_factors()
    factors[0] = replace(factors[0], score=score)

    with pytest.raises(ValueError, match="zwischen 0 und 10"):
        score_long_term_assessment(
            complete_readiness(), factors, complete_scenarios(), current_value=100.0, horizon_years=5
        )


@pytest.mark.parametrize("horizon", [2, 8, 4.5, True])
def test_horizon_must_be_whole_year_between_three_and_seven(horizon: object) -> None:
    with pytest.raises(ValueError, match="Horizont"):
        score_long_term_assessment(
            complete_readiness(),
            complete_factors(),
            complete_scenarios(),
            current_value=100.0,
            horizon_years=horizon,  # type: ignore[arg-type]
        )


def test_scenarios_require_probabilities_order_and_conditions() -> None:
    wrong_sum = [replace(item, probability_pct=30.0) for item in complete_scenarios()]
    wrong_order = complete_scenarios()
    wrong_order[0] = replace(wrong_order[0], target_value=150.0)
    no_conditions = complete_scenarios()
    no_conditions[1] = replace(no_conditions[1], conditions=())

    with pytest.raises(ValueError, match="100"):
        score_long_term_assessment(
            complete_readiness(), complete_factors(), wrong_sum, current_value=100.0, horizon_years=5
        )
    with pytest.raises(ValueError, match="Bear < Basis < Bull"):
        score_long_term_assessment(
            complete_readiness(), complete_factors(), wrong_order, current_value=100.0, horizon_years=5
        )
    with pytest.raises(ValueError, match="Bedingungen"):
        score_long_term_assessment(
            complete_readiness(), complete_factors(), no_conditions, current_value=100.0, horizon_years=5
        )


def test_inputs_remain_unchanged_and_all_sections_stay_covered() -> None:
    readiness = complete_readiness()
    factors = complete_factors()
    scenarios = complete_scenarios()
    original_factors = list(factors)
    original_scenarios = list(scenarios)

    result = score_long_term_assessment(
        readiness, factors, scenarios, current_value=100.0, horizon_years=5
    )

    assert result.ready is True
    assert factors == original_factors
    assert scenarios == original_scenarios
    assert set(readiness.covered_sections) == set(LONG_TERM_SECTION_REQUIREMENTS)
