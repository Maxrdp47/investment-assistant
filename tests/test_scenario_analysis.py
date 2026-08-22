from __future__ import annotations

import pandas as pd

import app
from analysis_models import MarketPhase, ModuleScore, RiskReward
from scenario_analysis import (
    build_scenarios,
    numeric_scenario_levels,
    research_expected_value,
    scenario_probabilities,
)


def score(value: float) -> ModuleScore:
    return ModuleScore(value, "Kontext", [])


def risk(ratio: float | None) -> RiskReward:
    return RiskReward(-0.05, 0.10, ratio, 6.0, "CRV-Kontext")


def phase(name: str) -> MarketPhase:
    return MarketPhase(name, "Marktphase", {})


def test_app_reexports_extracted_scenario_functions_for_compatibility() -> None:
    assert app.scenario_probabilities is scenario_probabilities
    assert app.research_expected_value is research_expected_value
    assert app.numeric_scenario_levels is numeric_scenario_levels
    assert app.build_scenarios is build_scenarios


def test_probabilities_sum_to_100_and_keep_minimum_base_case() -> None:
    probabilities = scenario_probabilities(
        score(10.0),
        score(10.0),
        risk(4.0),
        phase("Bullenmarkt"),
        100.0,
        [98.0],
        [150.0],
        pd.Series({"SMA_50": 90.0, "SMA_200": 80.0, "Volatility": 0.10}),
    )

    assert sum(probabilities) == 100
    assert probabilities[2] >= 10
    assert probabilities[1] >= 20


def test_strong_and_weak_market_structures_change_scenario_balance() -> None:
    strong = scenario_probabilities(
        score(8.0),
        score(8.0),
        risk(2.5),
        phase("Bullenmarkt"),
        100.0,
        [95.0],
        [120.0],
        pd.Series({"SMA_50": 90.0, "SMA_200": 80.0, "Volatility": 0.20}),
    )
    weak = scenario_probabilities(
        score(3.0),
        score(3.0),
        risk(0.5),
        phase("Bärenmarkt"),
        100.0,
        [60.0],
        [103.0],
        pd.Series({"SMA_50": 110.0, "SMA_200": 120.0, "Volatility": 0.90}),
    )

    assert strong[0] > strong[2]
    assert weak[2] > weak[0]
    assert sum(strong) == sum(weak) == 100


def test_expected_value_uses_real_support_and_resistance_geometry_without_mutation() -> None:
    supports = [90.0, 80.0]
    resistances = [120.0, 130.0]
    original_supports = list(supports)
    original_resistances = list(resistances)

    result = research_expected_value(
        100.0,
        supports,
        resistances,
        score(7.0),
        score(7.0),
        risk(2.0),
        phase("Bullenmarkt"),
        pd.Series({"SMA_50": 95.0, "SMA_200": 90.0, "Volatility": 0.30}),
    )
    details = "\n".join(result.details)

    assert result.name == "Expected Value"
    assert 0.0 <= result.score <= 10.0
    assert "Bull-Case: +30.0%" in details
    assert "Bear-Case: -20.0%" in details
    assert supports == original_supports
    assert resistances == original_resistances


def test_expected_value_discloses_conservative_fallbacks_when_levels_are_missing() -> None:
    result = research_expected_value(
        100.0,
        [],
        [],
        score(5.0),
        score(5.0),
        risk(None),
        phase("Seitwärtsmarkt"),
        pd.Series({"Volatility": 0.40}),
    )
    details = "\n".join(result.details)

    assert "Bull-Case: +12.0%" in details
    assert "Base-Case: +3.0%" in details
    assert "Bear-Case: -10.0%" in details


def test_numeric_scenario_levels_filter_wrong_side_levels_and_preserve_inputs() -> None:
    supports = [95.0, 85.0, 105.0]
    resistances = [110.0, 125.0, 90.0]
    original_supports = list(supports)
    original_resistances = list(resistances)

    levels = numeric_scenario_levels(100.0, supports, resistances, 7.0)

    assert levels == {
        "bull": 125.0,
        "base": 110.0,
        "bear": 85.0,
        "low": 85.0,
        "high": 125.0,
        "support": 95.0,
        "resistance": 110.0,
    }
    assert supports == original_supports
    assert resistances == original_resistances


def test_visible_scenarios_use_same_numeric_levels_and_complete_probabilities() -> None:
    rows = build_scenarios(
        100.0,
        [95.0, 85.0],
        [110.0, 125.0],
        score(7.0),
        score(7.0),
        risk(2.0),
        phase("Bullenmarkt"),
        pd.Series({"SMA_50": 95.0, "SMA_200": 90.0, "Volatility": 0.30}),
        "EUR",
        1.0,
        "Nur EUR",
    )

    probabilities = [int(row["Wahrscheinlichkeit"].rstrip("%")) for row in rows]
    assert [row["Szenario"] for row in rows] == ["Bull-Case", "Base-Case", "Bear-Case"]
    assert rows[0]["Kursziel"] == "125,00 €"
    assert rows[1]["Kursziel"] == "110,00 €"
    assert rows[2]["Kursziel"] == "85,00 €"
    assert sum(probabilities) == 100
