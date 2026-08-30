from __future__ import annotations

from failed_seller_reclassification import (
    VARIANTS,
    assess_interpretation,
    dependency_results,
    make_accumulators,
    update_accumulators,
    verify_original_counts,
)


def _identity(issuer: str | None) -> dict[str, object]:
    return {
        "listing_id": f"listing:{issuer or 'unknown'}",
        "issuer_id": issuer,
        "mapping_status": "VERIFIED" if issuer else "UNRESOLVED",
        "dependency_status": "KNOWN" if issuer else "UNKNOWN",
    }


def _original(dependency: dict[str, object]) -> dict[str, object]:
    variants = {}
    for variant in VARIANTS:
        selected_n = dependency["variants"][variant]["selected"]["raw_observations"]
        control_n = dependency["variants"][variant]["control"]["raw_observations"]
        metrics = {
            "expectancy_r": 0.1,
            "profit_factor": 1.2,
            "cost_stress_expectancy_r": {"additional_0.10R": 0.0},
        }
        variants[variant] = {
            "selected": {**metrics, "raw_n": selected_n},
            "control": {**metrics, "raw_n": control_n},
        }
    return {
        "baseline": {"raw_n": dependency["baseline"]["raw_observations"]},
        "variants": variants,
    }


def test_reclassification_collapses_overlaps_excludes_unknown_and_preserves_counts() -> None:
    accumulators = make_accumulators()
    flags = {variant: True for variant in VARIANTS}
    update_accumulators(
        accumulators,
        signal_day="2025-01-01",
        identity=_identity("issuer-1"),
        flags=flags,
    )
    update_accumulators(
        accumulators,
        signal_day="2025-01-20",
        identity=_identity("issuer-1"),
        flags=flags,
    )
    update_accumulators(
        accumulators,
        signal_day="2025-04-01",
        identity=_identity("issuer-1"),
        flags={variant: False for variant in VARIANTS},
    )
    update_accumulators(
        accumulators,
        signal_day="2025-05-01",
        identity=_identity(None),
        flags=flags,
    )
    result = dependency_results(accumulators)
    baseline = result["baseline"]
    assert baseline["raw_observations"] == 4
    assert baseline["effective_independent_issuer_count"] == 2
    assert baseline["unresolved_dependency_observation_n"] == 1
    assert baseline["unknown_dependency_contribution_to_effective_n"] == 0
    assert result["variants"][VARIANTS[0]]["selected"]["raw_observations"] == 3
    verify_original_counts(_original(result), result)


def test_assessment_never_upgrades_or_opens_unseen_stages() -> None:
    accumulators = make_accumulators()
    flags = {variant: True for variant in VARIANTS}
    update_accumulators(
        accumulators,
        signal_day="2025-01-01",
        identity=_identity("issuer-1"),
        flags=flags,
    )
    dependency = dependency_results(accumulators)
    assessment = assess_interpretation(_original(dependency), dependency)
    assert assessment["classification_change"] == "INCONCLUSIVE_RETAINED"
    assert assessment["new_research_attempts"] == 0
    assert assessment["validation_opened"] is False
    assert assessment["holdout_opened"] is False
    assert assessment["strategy_activated"] is False
