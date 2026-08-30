from __future__ import annotations

"""Dependency-only reassessment of the immutable Failed-Seller Development run."""

import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Mapping, Sequence


FAILED_SELLER_RECLASSIFICATION_VERSION = "failed-seller-dependency-reclassification-2026.08.30-v1"
DEPENDENCY_METHOD = "verified_issuer_non_overlapping_conservative_42_calendar_day_windows"
# Broad-v1 labels observe at most 25 trading sessions.  Forty-two calendar days
# conservatively cover that horizon without inventing an exchange calendar.
CONSERVATIVE_OUTCOME_WINDOW_DAYS = 42
VARIANTS = (
    "failed_seller_attempts_exactly_1",
    "failed_seller_attempts_exactly_2",
    "confirmation_close_location_gte_0_70",
    "confirmation_close_location_gte_0_80",
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class DependencyAccumulator:
    """Streaming effective-N lower bound for rows ordered by signal day."""

    def __init__(self) -> None:
        self.raw_n = 0
        self.verified_observation_n = 0
        self.unknown_observation_n = 0
        self.conflict_observation_n = 0
        self.listing_ids: set[str] = set()
        self.issuer_ids: set[str] = set()
        self._latest_end: dict[str, date] = {}
        self._episodes: dict[str, int] = defaultdict(int)

    def update(self, signal_day: str, identity: Mapping[str, object]) -> None:
        self.raw_n += 1
        listing_id = str(identity.get("listing_id") or "")
        if listing_id:
            self.listing_ids.add(listing_id)
        status = str(identity.get("mapping_status") or "UNRESOLVED").upper()
        issuer_id = str(identity.get("issuer_id") or "")
        dependency_status = str(identity.get("dependency_status") or "UNKNOWN").upper()
        if status != "VERIFIED" or dependency_status != "KNOWN" or not issuer_id:
            self.unknown_observation_n += 1
            self.conflict_observation_n += int(status == "CONFLICT")
            return
        start = date.fromisoformat(str(signal_day)[:10])
        end = start + timedelta(days=CONSERVATIVE_OUTCOME_WINDOW_DAYS)
        previous_end = self._latest_end.get(issuer_id)
        if previous_end is None or start > previous_end:
            self._episodes[issuer_id] += 1
            self._latest_end[issuer_id] = end
        elif end > previous_end:
            self._latest_end[issuer_id] = end
        self.issuer_ids.add(issuer_id)
        self.verified_observation_n += 1

    def result(self) -> dict[str, object]:
        effective_n = sum(self._episodes.values())
        return {
            "raw_observations": self.raw_n,
            "raw_listings": len(self.listing_ids),
            "verified_issuer_clusters": len(self.issuer_ids),
            "verified_dependency_observation_n": self.verified_observation_n,
            "verified_dependency_coverage_pct": (
                round(self.verified_observation_n / self.raw_n * 100, 6)
                if self.raw_n
                else 0.0
            ),
            "unresolved_dependency_observation_n": self.unknown_observation_n,
            "conflict_observation_n": self.conflict_observation_n,
            "effective_independent_issuer_count": effective_n,
            "effective_n_method": DEPENDENCY_METHOD,
            "outcome_window_calendar_days": CONSERVATIVE_OUTCOME_WINDOW_DAYS,
            "unknown_dependency_contribution_to_effective_n": 0,
            "effective_n_le_raw_n": effective_n <= self.raw_n,
            "issuer_episode_counts": dict(sorted(self._episodes.items())),
        }


def make_accumulators() -> dict[str, DependencyAccumulator]:
    result = {"baseline": DependencyAccumulator()}
    for variant in VARIANTS:
        result[f"{variant}:selected"] = DependencyAccumulator()
        result[f"{variant}:control"] = DependencyAccumulator()
    return result


def update_accumulators(
    accumulators: Mapping[str, DependencyAccumulator],
    *,
    signal_day: str,
    identity: Mapping[str, object],
    flags: Mapping[str, object],
) -> None:
    accumulators["baseline"].update(signal_day, identity)
    for variant in VARIANTS:
        selected = bool(flags.get(variant))
        key = f"{variant}:{'selected' if selected else 'control'}"
        accumulators[key].update(signal_day, identity)


def dependency_results(
    accumulators: Mapping[str, DependencyAccumulator],
) -> dict[str, object]:
    return {
        "baseline": accumulators["baseline"].result(),
        "variants": {
            variant: {
                "selected": accumulators[f"{variant}:selected"].result(),
                "control": accumulators[f"{variant}:control"].result(),
            }
            for variant in VARIANTS
        },
    }


def verify_original_counts(
    original_result: Mapping[str, object],
    dependency: Mapping[str, object],
) -> None:
    expected_baseline = int(dict(original_result["baseline"])["raw_n"])
    actual_baseline = int(dict(dependency["baseline"])["raw_observations"])
    if expected_baseline != actual_baseline:
        raise ValueError(f"Baseline raw N changed: {expected_baseline} != {actual_baseline}")
    original_variants = dict(original_result["variants"])
    reclassified_variants = dict(dependency["variants"])
    for variant in VARIANTS:
        for group in ("selected", "control"):
            expected = int(dict(dict(original_variants[variant])[group])["raw_n"])
            actual = int(dict(dict(reclassified_variants[variant])[group])["raw_observations"])
            if expected != actual:
                raise ValueError(
                    f"{variant}/{group} raw N changed: {expected} != {actual}"
                )


def assess_interpretation(
    original_result: Mapping[str, object],
    dependency: Mapping[str, object],
) -> dict[str, object]:
    variants = {}
    original_variants = dict(original_result["variants"])
    for variant in VARIANTS:
        selected_metrics = dict(dict(original_variants[variant])["selected"])
        selected_dependency = dict(dict(dependency["variants"])[variant])["selected"]
        cost_10 = dict(selected_metrics.get("cost_stress_expectancy_r") or {}).get(
            "additional_0.10R"
        )
        variants[variant] = {
            "raw_metrics_changed": False,
            "expectancy_r": selected_metrics.get("expectancy_r"),
            "profit_factor": selected_metrics.get("profit_factor"),
            "additional_0_10r_expectancy_r": cost_10,
            "verified_dependency_coverage_pct": selected_dependency[
                "verified_dependency_coverage_pct"
            ],
            "effective_independent_issuer_count": selected_dependency[
                "effective_independent_issuer_count"
            ],
            "interpretation": (
                "DEVELOPMENT_SIGNAL_INTERPRETABLE_BUT_NOT_VALIDATED"
                if selected_dependency["verified_dependency_coverage_pct"] >= 80.0
                else "DEPENDENCY_COVERAGE_INSUFFICIENT"
            ),
            "limitations": [
                "development_only",
                "no_validation",
                "no_holdout",
                "no_automatic_upgrade",
                "cost_sensitive" if cost_10 is not None and float(cost_10) <= 0 else "cost_stress_positive",
            ],
        }
    return {
        "classification_change": "INCONCLUSIVE_RETAINED",
        "result_direction": "INCONCLUSIVE",
        "identity_limitation": "SUBSTANTIALLY_REDUCED_NOT_ELIMINATED",
        "reason": (
            "Verified dependency coverage now supports a development-only cluster "
            "description, but it cannot replace unseen validation or authorize a rule."
        ),
        "variants": variants,
        "validation_opened": False,
        "holdout_opened": False,
        "new_research_attempts": 0,
        "strategy_activated": False,
    }
