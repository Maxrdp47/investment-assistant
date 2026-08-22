from __future__ import annotations

from forecast_probabilities import (
    RAW_PROBABILITY_SCHEMA_VERSION,
    build_raw_up_probability,
)


def test_scenario_mixture_produces_explicit_uncalibrated_up_probability() -> None:
    result = build_raw_up_probability(
        [
            {"Szenario": "Bull-Case", "Wahrscheinlichkeit": "40%"},
            {"Szenario": "Base-Case", "Wahrscheinlichkeit": "35%"},
            {"Szenario": "Bear-Case", "Wahrscheinlichkeit": "25%"},
        ],
        {"bull": 120.0, "base": 100.0, "bear": 80.0},
        100.0,
    )

    assert result["status"] == "available"
    assert result["schema_version"] == RAW_PROBABILITY_SCHEMA_VERSION
    assert result["probability_up"] == 0.575
    assert result["calibration_status"] == "uncalibrated"
    assert result["event_definition"] == "actual_return_pct > 0"


def test_probability_remains_missing_when_a_scenario_is_not_measurable() -> None:
    result = build_raw_up_probability(
        [
            {"Szenario": "Bull-Case", "Wahrscheinlichkeit": "60%"},
            {"Szenario": "Base-Case", "Wahrscheinlichkeit": "40%"},
        ],
        {"bull": 120.0, "base": 100.0},
        100.0,
    )

    assert result["status"] == "missing"
    assert result["reason"] == "scenario_input_missing:Bear-Case"
