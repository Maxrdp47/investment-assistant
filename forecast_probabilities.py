from __future__ import annotations

import math
import re


RAW_PROBABILITY_SCHEMA_VERSION = "raw-up-scenario-mixture-2026.08.09-v1"
SCENARIO_NAMES = ("Bull-Case", "Base-Case", "Bear-Case")
SCENARIO_LEVEL_KEYS = {
    "Bull-Case": "bull",
    "Base-Case": "base",
    "Bear-Case": "bear",
}


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _probability_pct(value: object) -> float | None:
    if isinstance(value, str):
        match = re.fullmatch(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*%\s*", value)
        if not match:
            return None
        value = match.group(1).replace(",", ".")
    number = _number(value)
    return number if number is not None and 0 <= number <= 100 else None


def build_raw_up_probability(
    scenarios: list[dict],
    scenario_levels: dict,
    current_price: float,
) -> dict:
    """Convert the stored scenario mixture into an explicitly uncalibrated up probability."""
    price = _number(current_price)
    if price is None or price <= 0:
        return {
            "status": "missing",
            "schema_version": RAW_PROBABILITY_SCHEMA_VERSION,
            "reason": "current_price_invalid",
        }

    scenario_rows = {
        str(item.get("Szenario") or ""): item
        for item in scenarios
        if isinstance(item, dict)
    }
    weights: dict[str, float] = {}
    targets: dict[str, float] = {}
    for name in SCENARIO_NAMES:
        row = scenario_rows.get(name) or {}
        probability = _probability_pct(row.get("Wahrscheinlichkeit"))
        target = _number(scenario_levels.get(SCENARIO_LEVEL_KEYS[name]))
        if probability is None or target is None or target <= 0:
            return {
                "status": "missing",
                "schema_version": RAW_PROBABILITY_SCHEMA_VERSION,
                "reason": f"scenario_input_missing:{name}",
            }
        weights[name] = probability
        targets[name] = target
    if not math.isclose(sum(weights.values()), 100.0, abs_tol=0.01):
        return {
            "status": "missing",
            "schema_version": RAW_PROBABILITY_SCHEMA_VERSION,
            "reason": "scenario_probabilities_do_not_sum_to_100",
        }

    event_values = {
        name: 1.0 if target > price else 0.0 if target < price else 0.5
        for name, target in targets.items()
    }
    probability_up = sum(weights[name] / 100 * event_values[name] for name in SCENARIO_NAMES)
    return {
        "status": "available",
        "schema_version": RAW_PROBABILITY_SCHEMA_VERSION,
        "probability_up": round(probability_up, 6),
        "event_definition": "actual_return_pct > 0",
        "calibration_status": "uncalibrated",
        "source": "stored_bull_base_bear_scenario_mixture",
        "horizon_policy": "shared_across_horizons_until_horizon_specific_models_exist",
        "scenario_probabilities_pct": weights,
        "scenario_targets": targets,
        "scenario_event_values": event_values,
    }
