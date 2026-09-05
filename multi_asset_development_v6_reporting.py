from __future__ import annotations

"""Pre-registered, descriptive-only reporting for Development v6.

This module cannot rank variants, search thresholds, or calculate trading
strategy performance.  It summarizes the already frozen measurement schema
only after the complete final integrity audit has passed.
"""

import json
import math
import sqlite3
import zlib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Mapping

from multi_asset_development_v6_audit import verify_self_fingerprinted_artifact
from multi_asset_discovery_v1 import fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
PLAN_VERSION = "multi-asset-development-v6-descriptive-plan-2026.09.05-v1"
REPORT_VERSION = "multi-asset-development-v6-descriptive-report-2026.09.05-v1"
SUMMARY_VERSION = "multi-asset-development-v6-completion-summary-2026.09.05-v1"
DEFAULT_PLAN_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v6_descriptive_plan_2026-09-05-v1-r7.json"
)
DEFAULT_REPORT_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v6_descriptive_report_2026-09-05-v1.json"
)
DEFAULT_SUMMARY_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v6_completion_summary_2026-09-05-v1.json"
)

_GROUP_DIMENSIONS = (
    "ASSET_CLASS",
    "SIGNAL_YEAR",
    "MARKET_REGIME",
    "VOLATILITY_REGIME_IF_PRESENT",
    "SAFE_ZONE_A_STATUS",
    "SAFE_ZONE_B_STATUS",
    "SAFE_ZONE_C_STATUS",
    "DEPENDENCY_STATUS",
    "OUTCOME_STATUS",
    "CENSORING_REASON",
)
_OUTCOME_COMPLETENESS_DIMENSIONS = ("OUTCOME_STATUS", "CENSORING_REASON")
_OUTCOME_COMPLETENESS_POLICY = {
    "dimensions": list(_OUTCOME_COMPLETENESS_DIMENSIONS),
    "grouping": "ONE_DIMENSION_AT_A_TIME_NO_COMBINATORIAL_SEARCH",
    "not_censored_label": "NOT_CENSORED",
    "partition_counts_reported": True,
    "metric_defined_n_reported_per_partition": True,
    "pooled_metrics_are_all_case_coverage_descriptions_only": True,
    "complete_horizon_interpretation_requires_outcome_status_partition": True,
}
_PATH_METRICS = (
    "mfe_pct",
    "mae_pct",
    "mfe_atr",
    "mae_atr",
    "mfe_r",
    "mae_r",
    "final_return_pct",
    "entry_gap_pct",
    "entry_gap_atr",
    "time_to_mfe_observations",
    "time_to_structural_intraday_invalidation",
    "time_to_structural_close_invalidation",
)
_PATH_QUALITY_METRICS = (
    "mfe_to_mae_ratio",
    "positive_close_fraction",
    "peak_giveback_pct",
    "final_giveback_pct",
    "peak_giveback_r",
    "final_giveback_r",
)
_PROTECTIVE_RATCHET_METRICS = (
    "initial_lower",
    "final_lower",
    "lower_change",
    "update_count",
)
_PROTECTIVE_RATCHET_STATUS_FIELDS = ("status", "reason", "never_lowered")
_DETERIORATION_STATUS_FIELDS = ("status", "reason")
_DETERIORATION_COUNTERS = {
    "PRICE_STRUCTURE": "close_below_signal_ema20_count",
    "MOMENTUM": "rsi14_below_40_count",
    "VOLATILITY": "atr14_above_1_5x_signal_count",
    "LIQUIDITY": "volume_ratio_below_0_5_count",
    "EVENT": None,
}
_DEPENDENCY_EFFECTIVE_N_METHOD = (
    "maximum_pairwise_non_overlapping_outcome_windows_per_verified_issuer"
)
_DEPENDENCY_VERSION = "swing-research-dependency-2026.08.29-v3"
_METRIC_SEMANTICS = {
    "final_return_pct": (
        "RETURN_FROM_REFERENCE_ENTRY_TO_LAST_AVAILABLE_OUTCOME_CLOSE;"
        " NOT_AN_EXIT_OR_REALIZED_RETURN"
    ),
    "time_metrics": (
        "FIRST_OBSERVED_DAILY_BAR_CONDITION; NO_INTRABAR_ORDER_INFERRED"
    ),
    "protective_ratchet": (
        "DESCRIPTIVE_MEASUREMENT_ONLY; NOT_AN_ACTIVE_STOP_OR_EXIT_RULE"
    ),
    "deterioration": "FIXED_STORED_COUNTERS_ONLY; NOT_A_RULE_OR_THRESHOLD_SEARCH",
}
_CHECKPOINT_METRICS = (
    "calendar_span_days_inclusive",
    "return_pct",
    "mfe_pct",
    "mae_pct",
    "mfe_atr",
    "mae_atr",
    "mfe_r",
    "mae_r",
)
_OBSERVATION_AXIS_METRICS = (
    "observed_bar_count",
    "calendar_span_days_inclusive",
    "data_gaps_crossed",
)
_CHECKPOINTS = (20, 60, 120, 252)
_ZONE_KEYS = ("A", "B", "C")
_FIXED_R_LEVELS = ("1.0", "2.0", "3.0")
_SMALL_GROUP_WARNING_N = 30


class DevelopmentV6ReportingError(RuntimeError):
    """A frozen-plan, audit, or immutable-report guard failed."""


def _self_fingerprint(payload: Mapping[str, object]) -> str:
    basis = dict(payload)
    basis.pop("artifact_fingerprint", None)
    return fingerprint(basis)


def _load_verified(value: Mapping[str, object] | Path | str) -> dict[str, object]:
    payload = (
        dict(value)
        if isinstance(value, Mapping)
        else json.loads(Path(value).read_text(encoding="utf-8"))
    )
    if not verify_self_fingerprinted_artifact(payload):
        raise DevelopmentV6ReportingError("Referenced artifact fingerprint is invalid.")
    return payload


def _load_mapping_unverified(
    value: Mapping[str, object] | Path | str,
) -> dict[str, object]:
    return (
        dict(value)
        if isinstance(value, Mapping)
        else json.loads(Path(value).read_text(encoding="utf-8"))
    )


def _write_once(path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    if not verify_self_fingerprinted_artifact(payload):
        raise DevelopmentV6ReportingError("Output artifact fingerprint is invalid.")
    path = Path(path)
    if path.exists():
        existing = _load_verified(path)
        if existing["artifact_fingerprint"] != payload["artifact_fingerprint"]:
            raise DevelopmentV6ReportingError(
                f"Immutable artifact already exists with other content: {path}"
            )
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    except FileExistsError:
        return _write_once(path, payload)
    return dict(payload)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def freeze_v6_descriptive_plan(
    *,
    contract_basis_fingerprint: str,
    combined_input_fingerprint: str,
    created_at: str,
    artifact_path: Path = DEFAULT_PLAN_ARTIFACT,
) -> dict[str, object]:
    """Freeze the narrow descriptive analysis contract before the run."""

    payload: dict[str, object] = {
        "version": PLAN_VERSION,
        "status": "FROZEN",
        "created_at": created_at,
        "contract_basis_fingerprint": contract_basis_fingerprint,
        "combined_input_fingerprint": combined_input_fingerprint,
        "analysis_population": "ALL_VERIFIED_DEVELOPMENT_V6_CASES",
        "group_dimensions": list(_GROUP_DIMENSIONS),
        "grouping_policy": "ONE_DIMENSION_AT_A_TIME_NO_COMBINATORIAL_SEARCH",
        "outcome_completeness_separation": dict(_OUTCOME_COMPLETENESS_POLICY),
        "path_metrics": list(_PATH_METRICS),
        "path_quality_metrics": list(_PATH_QUALITY_METRICS),
        "protective_ratchet_metrics": list(_PROTECTIVE_RATCHET_METRICS),
        "protective_ratchet_status_fields": list(
            _PROTECTIVE_RATCHET_STATUS_FIELDS
        ),
        "deterioration_counters": dict(_DETERIORATION_COUNTERS),
        "deterioration_status_fields": list(_DETERIORATION_STATUS_FIELDS),
        "dependency_evidence": {
            "version": _DEPENDENCY_VERSION,
            "effective_n_method": _DEPENDENCY_EFFECTIVE_N_METHOD,
            "unknown_dependency_contribution_to_effective_n": 0,
            "raw_n_claimed_independent": False,
        },
        "checkpoint_observations": list(_CHECKPOINTS),
        "checkpoint_metrics": list(_CHECKPOINT_METRICS),
        "observation_axis_metrics": list(_OBSERVATION_AXIS_METRICS),
        "fixed_r_levels": list(_FIXED_R_LEVELS),
        "summary_statistics": ["defined_n", "unavailable_n", "mean", "stddev", "min", "max"],
        "small_group_warning_n": _SMALL_GROUP_WARNING_N,
        "allowed_sections": [
            "coverage_and_na",
            "censoring",
            "outcome_completeness_separation",
            "path_measurements",
            "path_quality",
            "protective_ratchet",
            "deterioration",
            "dependency_evidence",
            "temporal_coverage",
            "checkpoints",
            "fixed_level_observations",
            "safe_zone_breaches",
            "sell_zone_measurements",
            "pre_existing_feature_coverage",
        ],
        "explicitly_forbidden": [
            "strategy_expectancy",
            "profit_factor",
            "net_edge",
            "best_score",
            "threshold_search",
            "parameter_search",
            "rule_selection",
            "hypothesis_generation",
            "validation",
            "holdout",
            "external",
            "production_or_broker_action",
        ],
        "inferential_claims_allowed": False,
        "selection_or_optimization_allowed": False,
        "metric_semantics": dict(_METRIC_SEMANTICS),
    }
    payload["artifact_fingerprint"] = _self_fingerprint(payload)
    return _write_once(Path(artifact_path), payload)


def _validate_frozen_plan(plan: Mapping[str, object]) -> None:
    if plan.get("version") != PLAN_VERSION or plan.get("status") != "FROZEN":
        raise DevelopmentV6ReportingError("Descriptive plan is not the frozen v1 plan.")
    if tuple(plan.get("group_dimensions") or ()) != _GROUP_DIMENSIONS:
        raise DevelopmentV6ReportingError("Frozen group dimensions differ from code.")
    if dict(plan.get("outcome_completeness_separation") or {}) != (
        _OUTCOME_COMPLETENESS_POLICY
    ):
        raise DevelopmentV6ReportingError(
            "Frozen outcome-completeness separation differs from code."
        )
    if tuple(plan.get("path_metrics") or ()) != _PATH_METRICS:
        raise DevelopmentV6ReportingError("Frozen path metrics differ from code.")
    if tuple(plan.get("path_quality_metrics") or ()) != _PATH_QUALITY_METRICS:
        raise DevelopmentV6ReportingError("Frozen path-quality metrics differ from code.")
    if tuple(plan.get("protective_ratchet_metrics") or ()) != (
        _PROTECTIVE_RATCHET_METRICS
    ):
        raise DevelopmentV6ReportingError(
            "Frozen protective-ratchet metrics differ from code."
        )
    if tuple(plan.get("protective_ratchet_status_fields") or ()) != (
        _PROTECTIVE_RATCHET_STATUS_FIELDS
    ):
        raise DevelopmentV6ReportingError(
            "Frozen protective-ratchet status fields differ from code."
        )
    if dict(plan.get("deterioration_counters") or {}) != _DETERIORATION_COUNTERS:
        raise DevelopmentV6ReportingError("Frozen deterioration counters differ from code.")
    if tuple(plan.get("deterioration_status_fields") or ()) != (
        _DETERIORATION_STATUS_FIELDS
    ):
        raise DevelopmentV6ReportingError(
            "Frozen deterioration status fields differ from code."
        )
    dependency = dict(plan.get("dependency_evidence") or {})
    if (
        dependency.get("version") != _DEPENDENCY_VERSION
        or dependency.get("effective_n_method") != _DEPENDENCY_EFFECTIVE_N_METHOD
        or dependency.get("unknown_dependency_contribution_to_effective_n") != 0
        or dependency.get("raw_n_claimed_independent") is not False
    ):
        raise DevelopmentV6ReportingError("Frozen dependency method differs from code.")
    if dict(plan.get("metric_semantics") or {}) != _METRIC_SEMANTICS:
        raise DevelopmentV6ReportingError("Frozen metric semantics differ from code.")
    if tuple(plan.get("checkpoint_observations") or ()) != _CHECKPOINTS:
        raise DevelopmentV6ReportingError("Frozen checkpoints differ from code.")
    if tuple(plan.get("checkpoint_metrics") or ()) != _CHECKPOINT_METRICS:
        raise DevelopmentV6ReportingError("Frozen checkpoint metrics differ from code.")
    if tuple(plan.get("observation_axis_metrics") or ()) != _OBSERVATION_AXIS_METRICS:
        raise DevelopmentV6ReportingError(
            "Frozen observation-axis metrics differ from code."
        )
    if plan.get("inferential_claims_allowed") is not False:
        raise DevelopmentV6ReportingError("Inferential claims must remain disabled.")
    if plan.get("selection_or_optimization_allowed") is not False:
        raise DevelopmentV6ReportingError("Selection/optimization must remain disabled.")


class _Metric:
    __slots__ = ("count", "total", "total_squares", "minimum", "maximum")

    def __init__(self) -> None:
        self.count = 0
        self.total = 0.0
        self.total_squares = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None

    def add(self, value: object) -> None:
        if value is None:
            return
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(number):
            return
        self.count += 1
        self.total += number
        self.total_squares += number * number
        self.minimum = number if self.minimum is None else min(self.minimum, number)
        self.maximum = number if self.maximum is None else max(self.maximum, number)

    def result(self, population_n: int) -> dict[str, object]:
        result: dict[str, object] = {
            "defined_n": self.count,
            "unavailable_n": max(0, population_n - self.count),
        }
        if not self.count:
            return result
        mean = self.total / self.count
        variance = max(0.0, self.total_squares / self.count - mean * mean)
        result.update(
            {
                "mean": mean,
                "stddev": math.sqrt(variance),
                "min": self.minimum,
                "max": self.maximum,
            }
        )
        return result


def _text(value: object) -> str | None:
    result = str(value or "").strip()
    return result or None


def _day(value: object, field: str) -> str | None:
    text = _text(value)
    if text is None:
        return None
    candidate = text[:10]
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise DevelopmentV6ReportingError(
            f"Stored dependency field {field} is not an ISO day."
        ) from exc
    return candidate


class _DependencyEpisodeEvidence:
    """Streaming equivalent of ``dependency_episode_report_v3``.

    Only the verified issuer intervals must remain in memory. Unknown mappings
    are counted but never promoted to independent evidence.
    """

    def __init__(self) -> None:
        self.raw_n = 0
        self.unknown = 0
        self.conflicts = 0
        self.verified_observations = 0
        self.issuer_case_counts: Counter[str] = Counter()
        self.listing_case_counts: Counter[str] = Counter()
        self.unresolved_listing_keys: set[str] = set()
        self.intervals: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def add(
        self, feature: Mapping[str, object], outcome: Mapping[str, object]
    ) -> None:
        index = self.raw_n
        self.raw_n += 1
        listing_id = _text(feature.get("listing_id") or outcome.get("listing_id"))
        issuer_id = _text(feature.get("issuer_id") or outcome.get("issuer_id"))
        mapping_status = str(
            feature.get("mapping_status")
            or outcome.get("mapping_status")
            or "UNRESOLVED"
        ).upper()
        dependency_value = feature.get("dependency_status") or outcome.get(
            "dependency_status"
        )

        if listing_id:
            self.listing_case_counts[listing_id] += 1
        if mapping_status != "VERIFIED":
            self.unresolved_listing_keys.add(
                listing_id
                or _text(feature.get("ticker") or outcome.get("ticker"))
                or f"row:{index}"
            )

        # dependency_evidence_report_v3 historically defaults a missing
        # dependency status to KNOWN for its coverage counts.
        dependency_known_for_coverage = bool(
            issuer_id
            and mapping_status == "VERIFIED"
            and str(dependency_value or "KNOWN").upper() == "KNOWN"
        )
        if dependency_known_for_coverage:
            self.issuer_case_counts[str(issuer_id)] += 1
            self.verified_observations += 1
        else:
            self.unknown += 1
            self.conflicts += int(mapping_status == "CONFLICT")

        # dependency_episode_report_v3 is deliberately stricter and defaults
        # the missing status to UNKNOWN for temporal Effective N.
        if not (
            issuer_id
            and mapping_status == "VERIFIED"
            and str(dependency_value or "UNKNOWN").upper() == "KNOWN"
        ):
            return
        start = _day(
            feature.get("signal_day")
            or outcome.get("signal_day")
            or outcome.get("observation_day"),
            "signal_day",
        )
        end = _day(
            outcome.get("label_end_day") or outcome.get("outcome_end_day") or start,
            "label_end_day",
        )
        if start is None:
            start = end = "0001-01-01"
        if end is None:
            end = start
        if end < start:
            raise DevelopmentV6ReportingError(
                "Stored dependency outcome end day precedes signal day."
            )
        self.intervals[str(issuer_id)].append((start, end))

    def result(self) -> dict[str, object]:
        issuer_episode_counts: dict[str, int] = {}
        episode_n = 0
        for issuer_id, intervals in sorted(self.intervals.items()):
            count = 0
            current_end: str | None = None
            for start, end in sorted(intervals, key=lambda item: (item[1], item[0])):
                if current_end is None or start > current_end:
                    count += 1
                    current_end = end
            issuer_episode_counts[issuer_id] = count
            episode_n += count

        payload: dict[str, object] = {
            "version": _DEPENDENCY_VERSION,
            "raw_n": self.raw_n,
            "raw_observations": self.raw_n,
            "raw_listings": len(self.listing_case_counts),
            "issuer_cluster_n": len(self.issuer_case_counts),
            "verified_issuer_clusters": len(self.issuer_case_counts),
            "listing_cluster_n": len(self.listing_case_counts),
            "unresolved_listings": len(self.unresolved_listing_keys),
            "dependency_unknown_n": self.unknown,
            "dependency_unknown": self.unknown,
            "conflict_observation_n": self.conflicts,
            "verified_dependency_observation_n": self.verified_observations,
            "verified_dependency_coverage_pct": (
                round(self.verified_observations / self.raw_n * 100, 6)
                if self.raw_n
                else 0.0
            ),
            "effective_n_known_issuers_only": episode_n,
            "effective_independent_issuer_count": episode_n,
            "same_issuer_excess_case_n": sum(
                max(value - 1, 0) for value in self.issuer_case_counts.values()
            ),
            "same_listing_excess_case_n": sum(
                max(value - 1, 0) for value in self.listing_case_counts.values()
            ),
            "unknown_counted_as_independent": False,
            "raw_n_claimed_independent": False,
            "effective_n_status": "COMPLETE" if self.unknown == 0 else "PARTIAL_UNKNOWN",
            "issuer_clusters": [
                {"issuer_id": key, "observation_n": self.issuer_case_counts[key]}
                for key in sorted(self.issuer_case_counts)
            ],
            "listing_clusters": [
                {"listing_id": key, "observation_n": self.listing_case_counts[key]}
                for key in sorted(self.listing_case_counts)
            ],
            "effective_n_method": _DEPENDENCY_EFFECTIVE_N_METHOD,
            "issuer_episode_counts": issuer_episode_counts,
            "unknown_dependency_contribution_to_effective_n": 0,
            "effective_n_le_raw_n": episode_n <= self.raw_n,
        }
        payload["report_fingerprint"] = fingerprint(payload)
        return payload


class _TemporalCoverage:
    def __init__(self) -> None:
        self.signal_days: set[str] = set()
        self.entry_days: set[str] = set()
        self.outcome_end_days: set[str] = set()
        self.observations_available = _Metric()

    @staticmethod
    def _range(days: set[str]) -> dict[str, object]:
        return {
            "distinct_n": len(days),
            "first_day": min(days) if days else None,
            "last_day": max(days) if days else None,
        }

    def add(
        self, feature: Mapping[str, object], outcome: Mapping[str, object]
    ) -> None:
        signal_day = _day(
            feature.get("signal_day") or outcome.get("signal_day"), "signal_day"
        )
        entry_day = _day(outcome.get("entry_day"), "entry_day")
        outcome_end_day = _day(outcome.get("outcome_end_day"), "outcome_end_day")
        if signal_day is not None:
            self.signal_days.add(signal_day)
        if entry_day is not None:
            self.entry_days.add(entry_day)
        if outcome_end_day is not None:
            self.outcome_end_days.add(outcome_end_day)
        self.observations_available.add(outcome.get("observations_available"))

    def result(self, population_n: int) -> dict[str, object]:
        boundaries = self.entry_days | self.outcome_end_days
        return {
            "signal_days": self._range(self.signal_days),
            "entry_observation_days": self._range(self.entry_days),
            "outcome_end_days": self._range(self.outcome_end_days),
            "recorded_observation_boundary_days": self._range(boundaries),
            "observations_available_per_case": self.observations_available.result(
                population_n
            ),
            "full_distinct_observed_session_days": {
                "status": "UNAVAILABLE_FROM_COMPACT_OUTCOME_PAYLOADS",
                "value": None,
                "reason": (
                    "Only entry/end boundaries and per-case observation counts are "
                    "stored; overlapping session-day identities cannot be reconstructed."
                ),
            },
            "boundary_day_counts_are_not_full_observation_day_counts": True,
        }


class _Description:
    def __init__(self) -> None:
        self.n = 0
        self.outcome_status: Counter[str] = Counter()
        self.censoring_reason: Counter[str] = Counter()
        self.measurement_status: Counter[str] = Counter()
        self.r_status: Counter[str] = Counter()
        self.r_reason: Counter[str] = Counter()
        self.atr_status: Counter[str] = Counter()
        self.atr_reason: Counter[str] = Counter()
        self.path_metrics = {name: _Metric() for name in _PATH_METRICS}
        self.path_quality = {name: _Metric() for name in _PATH_QUALITY_METRICS}
        self.protective_ratchet_status: Counter[str] = Counter()
        self.protective_ratchet_reasons: Counter[str] = Counter()
        self.protective_ratchet_never_lowered: Counter[str] = Counter()
        self.protective_ratchet_metrics = {
            name: _Metric() for name in _PROTECTIVE_RATCHET_METRICS
        }
        self.deterioration_status: dict[str, Counter[str]] = {
            category: Counter() for category in _DETERIORATION_COUNTERS
        }
        self.deterioration_reasons: dict[str, Counter[str]] = {
            category: Counter() for category in _DETERIORATION_COUNTERS
        }
        self.deterioration_metrics = {
            category: _Metric()
            for category, counter_name in _DETERIORATION_COUNTERS.items()
            if counter_name is not None
        }
        self.observation_axis = {
            name: _Metric() for name in _OBSERVATION_AXIS_METRICS
        }
        self.declared_gap_boundary_encountered = 0
        self.checkpoint_available = Counter()
        self.checkpoints = {
            str(observation): {name: _Metric() for name in _CHECKPOINT_METRICS}
            for observation in _CHECKPOINTS
        }
        self.r_level_available = Counter()
        self.r_level_hit = Counter()
        self.feature_coverage: dict[str, Counter[str]] = defaultdict(Counter)
        self.feature_unavailable_reasons: dict[str, Counter[str]] = defaultdict(Counter)
        self.safe_feature_status: dict[str, Counter[str]] = {
            key: Counter() for key in _ZONE_KEYS
        }
        self.safe_feature_reasons: dict[str, Counter[str]] = {
            key: Counter() for key in _ZONE_KEYS
        }
        self.safe_measurement_status: dict[str, Counter[str]] = {
            key: Counter() for key in _ZONE_KEYS
        }
        self.safe_intraday_breaches = Counter()
        self.safe_close_breaches = Counter()
        self.safe_intraday_time = {key: _Metric() for key in _ZONE_KEYS}
        self.safe_close_time = {key: _Metric() for key in _ZONE_KEYS}
        self.sell_feature_status: dict[str, Counter[str]] = {
            key: Counter() for key in _ZONE_KEYS
        }
        self.sell_feature_reasons: dict[str, Counter[str]] = {
            key: Counter() for key in _ZONE_KEYS
        }
        self.sell_measurement_status: dict[str, Counter[str]] = {
            key: Counter() for key in _ZONE_KEYS
        }
        self.sell_hits = Counter()
        self.sell_hit_time = {key: _Metric() for key in _ZONE_KEYS}
        self.sell_overshoot = {key: _Metric() for key in _ZONE_KEYS}

    def add(self, feature: Mapping[str, object], outcome: Mapping[str, object]) -> None:
        self.n += 1
        self.outcome_status[str(outcome.get("status") or "UNKNOWN")] += 1
        self.censoring_reason[str(outcome.get("censoring_reason") or "NOT_CENSORED")] += 1
        self.measurement_status[str(outcome.get("measurement_status") or "UNKNOWN")] += 1
        r_status = str(outcome.get("r_metrics_status") or "UNAVAILABLE")
        atr_status = str(outcome.get("atr_metrics_status") or "UNAVAILABLE")
        self.r_status[r_status] += 1
        self.atr_status[atr_status] += 1
        if r_status != "AVAILABLE":
            self.r_reason[str(outcome.get("r_metrics_reason") or "UNKNOWN")] += 1
        if atr_status != "AVAILABLE":
            self.atr_reason[str(outcome.get("atr_metrics_reason") or "UNKNOWN")] += 1
        for name, metric in self.path_metrics.items():
            metric.add(outcome.get(name))
        path_quality = dict(outcome.get("path_quality") or {})
        for name, metric in self.path_quality.items():
            metric.add(path_quality.get(name))

        ratchet = dict(outcome.get("protective_ratchet") or {})
        ratchet_status = str(ratchet.get("status") or "NOT_PRESENT")
        self.protective_ratchet_status[ratchet_status] += 1
        if ratchet_status != "AVAILABLE":
            self.protective_ratchet_reasons[
                str(ratchet.get("reason") or ratchet_status)
            ] += 1
        else:
            initial_lower = ratchet.get("initial_lower")
            final_lower = ratchet.get("final_lower")
            self.protective_ratchet_metrics["initial_lower"].add(initial_lower)
            self.protective_ratchet_metrics["final_lower"].add(final_lower)
            try:
                lower_change = float(final_lower) - float(initial_lower)
            except (TypeError, ValueError):
                lower_change = None
            self.protective_ratchet_metrics["lower_change"].add(lower_change)
            updates = ratchet.get("updates")
            if isinstance(updates, list):
                self.protective_ratchet_metrics["update_count"].add(len(updates))
        never_lowered = ratchet.get("never_lowered")
        if isinstance(never_lowered, bool):
            self.protective_ratchet_never_lowered[str(never_lowered).upper()] += 1

        deterioration = dict(outcome.get("deterioration") or {})
        for category, counter_name in _DETERIORATION_COUNTERS.items():
            item = deterioration.get(category)
            item = dict(item) if isinstance(item, Mapping) else {}
            status = str(item.get("status") or "NOT_PRESENT")
            self.deterioration_status[category][status] += 1
            if status != "AVAILABLE":
                self.deterioration_reasons[category][
                    str(item.get("reason") or status)
                ] += 1
            if counter_name is not None:
                self.deterioration_metrics[category].add(item.get(counter_name))
        observation_axis = dict(outcome.get("observation_axis") or {})
        for name, metric in self.observation_axis.items():
            metric.add(observation_axis.get(name))
        if observation_axis.get("declared_data_gap_boundary_encountered") is True:
            self.declared_gap_boundary_encountered += 1

        checkpoints = dict(outcome.get("checkpoints") or {})
        for observation in _CHECKPOINTS:
            key = str(observation)
            checkpoint = checkpoints.get(key)
            if isinstance(checkpoint, Mapping):
                self.checkpoint_available[key] += 1
                for name, metric in self.checkpoints[key].items():
                    metric.add(checkpoint.get(name))

        for level in _FIXED_R_LEVELS:
            hits = dict(outcome.get("r_level_hits") or {})
            if r_status == "AVAILABLE":
                self.r_level_available[level] += 1
                if hits.get(level) is not None:
                    self.r_level_hit[level] += 1

        for name, item in dict(feature.get("features") or {}).items():
            item = dict(item or {}) if isinstance(item, Mapping) else {}
            status = str(item.get("status") or "UNKNOWN")
            self.feature_coverage[str(name)][status] += 1
            if status != "AVAILABLE":
                self.feature_unavailable_reasons[str(name)][
                    str(item.get("reason") or "UNKNOWN")
                ] += 1

        safe_zones = dict(feature.get("safe_zones") or {})
        safe_measurements = dict(outcome.get("safe_zone_breaches") or {})
        sell_zones = dict(feature.get("sell_zones") or {})
        sell_measurements = dict(outcome.get("sell_zone_measurements") or {})
        for key in _ZONE_KEYS:
            safe = dict(safe_zones.get(key) or {})
            safe_status = str(safe.get("status") or "UNKNOWN")
            self.safe_feature_status[key][safe_status] += 1
            if safe_status != "AVAILABLE":
                self.safe_feature_reasons[key][str(safe.get("reason") or "UNKNOWN")] += 1
            measured = dict(safe_measurements.get(key) or {})
            measured_status = str(measured.get("status") or "UNKNOWN")
            self.safe_measurement_status[key][measured_status] += 1
            intraday = measured.get("intraday_breach_observation")
            close = measured.get("close_breach_observation")
            if intraday is not None:
                self.safe_intraday_breaches[key] += 1
                self.safe_intraday_time[key].add(intraday)
            if close is not None:
                self.safe_close_breaches[key] += 1
                self.safe_close_time[key].add(close)

            sell = dict(sell_zones.get(key) or {})
            sell_status = str(sell.get("status") or "UNKNOWN")
            self.sell_feature_status[key][sell_status] += 1
            if sell_status != "AVAILABLE":
                self.sell_feature_reasons[key][str(sell.get("reason") or "UNKNOWN")] += 1
            sell_measured = dict(sell_measurements.get(key) or {})
            sell_measured_status = str(sell_measured.get("status") or "UNKNOWN")
            self.sell_measurement_status[key][sell_measured_status] += 1
            hit = sell_measured.get("hit_observation")
            if hit is not None:
                self.sell_hits[key] += 1
                self.sell_hit_time[key].add(hit)
            self.sell_overshoot[key].add(sell_measured.get("max_overshoot_pct"))

    def result(self) -> dict[str, object]:
        return {
            "n": self.n,
            "small_group_warning": self.n < _SMALL_GROUP_WARNING_N,
            "coverage_and_na": {
                "measurement_status": dict(sorted(self.measurement_status.items())),
                "r_metrics_status": dict(sorted(self.r_status.items())),
                "r_unavailable_reasons": dict(sorted(self.r_reason.items())),
                "atr_metrics_status": dict(sorted(self.atr_status.items())),
                "atr_unavailable_reasons": dict(sorted(self.atr_reason.items())),
                "pre_existing_features": {
                    name: {
                        "status_counts": dict(sorted(counts.items())),
                        "unavailable_reasons": dict(
                            sorted(self.feature_unavailable_reasons[name].items())
                        ),
                    }
                    for name, counts in sorted(self.feature_coverage.items())
                },
            },
            "censoring": {
                "outcome_status": dict(sorted(self.outcome_status.items())),
                "censoring_reason": dict(sorted(self.censoring_reason.items())),
            },
            "observation_axis": {
                "measurements": {
                    name: metric.result(self.n)
                    for name, metric in self.observation_axis.items()
                },
                "declared_data_gap_boundary_encountered_n": (
                    self.declared_gap_boundary_encountered
                ),
                "bars_calendar_and_gaps_reported_separately": True,
            },
            "path_measurements": {
                name: metric.result(self.n)
                for name, metric in self.path_metrics.items()
            },
            "path_quality": {
                name: metric.result(self.n)
                for name, metric in self.path_quality.items()
            },
            "protective_ratchet": {
                "status_counts": dict(sorted(self.protective_ratchet_status.items())),
                "unavailable_reasons": dict(
                    sorted(self.protective_ratchet_reasons.items())
                ),
                "never_lowered_counts": dict(
                    sorted(self.protective_ratchet_never_lowered.items())
                ),
                "measurements": {
                    name: metric.result(self.n)
                    for name, metric in self.protective_ratchet_metrics.items()
                },
            },
            "deterioration": {
                category: {
                    "status_counts": dict(
                        sorted(self.deterioration_status[category].items())
                    ),
                    "unavailable_reasons": dict(
                        sorted(self.deterioration_reasons[category].items())
                    ),
                    "measurements": (
                        {
                            str(counter_name): self.deterioration_metrics[
                                category
                            ].result(self.n)
                        }
                        if counter_name is not None
                        else {}
                    ),
                }
                for category, counter_name in _DETERIORATION_COUNTERS.items()
            },
            "checkpoints": {
                key: {
                    "available_n": int(self.checkpoint_available[key]),
                    "unavailable_n": self.n - int(self.checkpoint_available[key]),
                    "measurements": {
                        name: metric.result(int(self.checkpoint_available[key]))
                        for name, metric in metrics.items()
                    },
                }
                for key, metrics in self.checkpoints.items()
            },
            "fixed_r_level_observations": {
                level: {
                    "r_defined_n": int(self.r_level_available[level]),
                    "hit_n": int(self.r_level_hit[level]),
                    "not_hit_n": int(self.r_level_available[level] - self.r_level_hit[level]),
                }
                for level in _FIXED_R_LEVELS
            },
            "safe_zones": {
                key: {
                    "feature_status": dict(sorted(self.safe_feature_status[key].items())),
                    "feature_unavailable_reasons": dict(
                        sorted(self.safe_feature_reasons[key].items())
                    ),
                    "measurement_status": dict(
                        sorted(self.safe_measurement_status[key].items())
                    ),
                    "intraday_breach_n": int(self.safe_intraday_breaches[key]),
                    "close_breach_n": int(self.safe_close_breaches[key]),
                    "intraday_breach_observation": self.safe_intraday_time[key].result(
                        int(self.safe_intraday_breaches[key])
                    ),
                    "close_breach_observation": self.safe_close_time[key].result(
                        int(self.safe_close_breaches[key])
                    ),
                }
                for key in _ZONE_KEYS
            },
            "sell_zones": {
                key: {
                    "feature_status": dict(sorted(self.sell_feature_status[key].items())),
                    "feature_unavailable_reasons": dict(
                        sorted(self.sell_feature_reasons[key].items())
                    ),
                    "measurement_status": dict(
                        sorted(self.sell_measurement_status[key].items())
                    ),
                    "hit_n": int(self.sell_hits[key]),
                    "hit_observation": self.sell_hit_time[key].result(
                        int(self.sell_hits[key])
                    ),
                    "max_overshoot_pct": self.sell_overshoot[key].result(self.n),
                }
                for key in _ZONE_KEYS
            },
        }


def _group_values(
    feature: Mapping[str, object], outcome: Mapping[str, object]
) -> dict[str, str]:
    day = str(feature.get("signal_day") or "")
    safe_zones = dict(feature.get("safe_zones") or {})
    volatility = feature.get("volatility_regime")
    if volatility is None and isinstance(feature.get("regimes"), Mapping):
        volatility = dict(feature["regimes"]).get("volatility")
    return {
        "ASSET_CLASS": str(feature.get("asset_class") or "UNKNOWN"),
        "SIGNAL_YEAR": day[:4] if len(day) >= 4 else "UNKNOWN",
        "MARKET_REGIME": str(feature.get("market_regime") or "UNKNOWN"),
        "VOLATILITY_REGIME_IF_PRESENT": str(volatility or "NOT_PRESENT"),
        "SAFE_ZONE_A_STATUS": str(
            dict(safe_zones.get("A") or {}).get("status") or "UNKNOWN"
        ),
        "SAFE_ZONE_B_STATUS": str(
            dict(safe_zones.get("B") or {}).get("status") or "UNKNOWN"
        ),
        "SAFE_ZONE_C_STATUS": str(
            dict(safe_zones.get("C") or {}).get("status") or "UNKNOWN"
        ),
        "DEPENDENCY_STATUS": str(feature.get("dependency_status") or "UNKNOWN"),
        "OUTCOME_STATUS": str(outcome.get("status") or "UNKNOWN"),
        "CENSORING_REASON": str(
            outcome.get("censoring_reason") or "NOT_CENSORED"
        ),
    }


def build_v6_descriptive_report(
    *,
    run_id: str,
    feature_path: Path,
    outcome_path: Path,
    audit: Mapping[str, object] | Path | str,
    frozen_plan: Mapping[str, object] | Path | str,
    final_contract: Mapping[str, object] | Path | str,
    expected_contract_basis_fingerprint: str,
    created_at: str,
    artifact_path: Path = DEFAULT_REPORT_ARTIFACT,
) -> dict[str, object]:
    """Stream all verified cases into the strictly descriptive frozen report."""

    audit_payload = _load_verified(audit)
    plan = _load_verified(frozen_plan)
    _validate_frozen_plan(plan)
    if audit_payload.get("status") != "PASS":
        raise DevelopmentV6ReportingError("Descriptive report requires audit status PASS.")
    if audit_payload.get("run_id") != run_id:
        raise DevelopmentV6ReportingError("Audit and requested run identifiers differ.")
    run = dict(audit_payload.get("run") or {})
    raw_contract = _load_mapping_unverified(final_contract)
    if "contract" in raw_contract and not verify_self_fingerprinted_artifact(raw_contract):
        raise DevelopmentV6ReportingError("Final contract artifact fingerprint is invalid.")
    contract = dict(raw_contract.get("contract") or raw_contract)
    contract_basis = dict(contract)
    claimed_contract_fingerprint = contract_basis.pop("contract_fingerprint", None)
    if claimed_contract_fingerprint != fingerprint(contract_basis):
        raise DevelopmentV6ReportingError("Final contract fingerprint is invalid.")
    if claimed_contract_fingerprint != run.get("contract_fingerprint"):
        raise DevelopmentV6ReportingError("Audit and final contract differ.")
    references = dict(contract.get("reference_fingerprints") or {})
    if references.get("descriptive_plan_artifact_fingerprint") != plan.get(
        "artifact_fingerprint"
    ):
        raise DevelopmentV6ReportingError(
            "Final contract does not reference the supplied frozen plan."
        )
    if plan.get("contract_basis_fingerprint") != expected_contract_basis_fingerprint:
        raise DevelopmentV6ReportingError("Frozen plan contract-basis fingerprint differs.")
    if plan.get("combined_input_fingerprint") != run.get("combined_input_fingerprint"):
        raise DevelopmentV6ReportingError("Frozen plan input fingerprint differs.")
    if references.get("combined_input_fingerprint") != plan.get(
        "combined_input_fingerprint"
    ):
        raise DevelopmentV6ReportingError("Final contract input differs from frozen plan.")
    frozen_at = _parse_time(plan.get("created_at"))
    run_started = _parse_time(run.get("started_at"))
    if frozen_at is None or run_started is None or frozen_at > run_started:
        raise DevelopmentV6ReportingError(
            "Descriptive plan was not demonstrably frozen before the run started."
        )
    if Path(artifact_path).exists():
        existing = _load_verified(Path(artifact_path))
        expected_links = {
            "status": "DESCRIPTIVE_COMPLETE",
            "run_id": run_id,
            "audit_fingerprint": audit_payload["artifact_fingerprint"],
            "frozen_plan_fingerprint": plan["artifact_fingerprint"],
            "contract_basis_fingerprint": expected_contract_basis_fingerprint,
            "final_contract_fingerprint": claimed_contract_fingerprint,
        }
        if any(existing.get(key) != value for key, value in expected_links.items()):
            raise DevelopmentV6ReportingError(
                "Existing descriptive report belongs to different inputs."
            )
        return existing

    overall = _Description()
    dependency_evidence = _DependencyEpisodeEvidence()
    temporal_coverage = _TemporalCoverage()
    groups: dict[str, dict[str, _Description]] = {
        dimension: defaultdict(_Description) for dimension in _GROUP_DIMENSIONS
    }
    feature_path = Path(feature_path)
    outcome_path = Path(outcome_path)
    if not feature_path.is_file() or not outcome_path.is_file():
        raise DevelopmentV6ReportingError("Feature/outcome store is missing.")
    connection = sqlite3.connect(
        f"file:{feature_path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )
    connection.execute(
        "ATTACH DATABASE ? AS outcomes",
        (f"file:{outcome_path.resolve().as_posix()}?mode=ro",),
    )
    try:
        cursor = connection.execute(
            "SELECT f.payload_zlib,o.payload_zlib FROM feature_rows f "
            "JOIN outcomes.outcome_rows o ON o.case_id=f.case_id "
            "WHERE f.run_id=? AND o.run_id=? ORDER BY f.case_id",
            (run_id, run_id),
        )
        for feature_blob, outcome_blob in cursor:
            feature = json.loads(zlib.decompress(feature_blob).decode("utf-8"))
            outcome = json.loads(zlib.decompress(outcome_blob).decode("utf-8"))
            overall.add(feature, outcome)
            dependency_evidence.add(feature, outcome)
            temporal_coverage.add(feature, outcome)
            for dimension, label in _group_values(feature, outcome).items():
                groups[dimension][label].add(feature, outcome)
    finally:
        connection.close()

    expected_cases = int(
        dict(audit_payload.get("counts") or {}).get("audited_payload_pairs") or -1
    )
    if overall.n != expected_cases:
        raise DevelopmentV6ReportingError(
            f"Report population differs from audited population: {overall.n}/{expected_cases}."
        )
    dependency_result = dependency_evidence.result()
    if int(dependency_result["raw_n"]) != overall.n:
        raise DevelopmentV6ReportingError(
            "Dependency population differs from descriptive population."
        )
    audited_status_counts = dict(
        audit_payload.get("work_unit_status_counts") or {}
    )
    audited_skipped_n = int(audited_status_counts.get("SKIPPED") or 0)
    skipped_work_unit_exclusions = dict(
        audit_payload.get("skipped_work_unit_exclusions") or {}
    )
    if audited_skipped_n:
        if (
            int(
                skipped_work_unit_exclusions.get("total_skipped_work_units")
                or -1
            )
            != audited_skipped_n
            or int(
                skipped_work_unit_exclusions.get(
                    "classified_skipped_work_units"
                )
                or -1
            )
            != audited_skipped_n
            or skipped_work_unit_exclusions.get("all_skipped_units_reconciled")
            is not True
        ):
            raise DevelopmentV6ReportingError(
                "Audit does not provide a complete reconciled skip classification."
            )
    payload: dict[str, object] = {
        "version": REPORT_VERSION,
        "status": "DESCRIPTIVE_COMPLETE",
        "created_at": created_at,
        "run_id": run_id,
        "audit_fingerprint": audit_payload["artifact_fingerprint"],
        "frozen_plan_fingerprint": plan["artifact_fingerprint"],
        "contract_basis_fingerprint": expected_contract_basis_fingerprint,
        "final_contract_fingerprint": claimed_contract_fingerprint,
        "source_stores_opened_read_only": True,
        "streaming_single_pass": True,
        "population": {
            "definition": "ALL_AUDIT_VERIFIED_DEVELOPMENT_V6_CASES",
            "n": overall.n,
        },
        "work_unit_exclusions": skipped_work_unit_exclusions,
        "dependency_evidence": dependency_result,
        "temporal_coverage": temporal_coverage.result(overall.n),
        "metric_semantics": dict(plan.get("metric_semantics") or {}),
        "outcome_completeness_separation": {
            **dict(plan.get("outcome_completeness_separation") or {}),
            "partition_location": "groups",
            "overall_metric_population": "ALL_AUDIT_VERIFIED_CASES",
            "interpretation": (
                "Overall metrics describe all defined stored measurements only; "
                "use the fixed OUTCOME_STATUS and CENSORING_REASON partitions "
                "for complete-versus-censored distributions."
            ),
        },
        "overall": overall.result(),
        "groups": {
            dimension: {
                label: description.result()
                for label, description in sorted(values.items())
            }
            for dimension, values in groups.items()
        },
        "interpretation_limits": {
            "descriptive_only": True,
            "small_groups_are_flagged_not_interpreted": True,
            "missing_values_never_imputed": True,
            "skip_reason_codes_are_machine_recorded_not_report_inferred": True,
            "complete_and_censored_outcomes_have_separate_fixed_partitions": True,
            "pooled_means_are_not_complete_horizon_estimates": True,
            "r_values_only_summarized_when_structural_r_is_defined": True,
            "atr_values_only_summarized_when_atr_is_defined": True,
            "no_intrabar_order_inferred": True,
            "final_return_pct_is_not_an_exit_or_realized_return": True,
            "path_quality_ratchet_and_deterioration_are_descriptive_only": True,
            "observation_boundary_days_are_not_full_distinct_session_days": True,
            "unknown_dependency_contribution_to_effective_n": 0,
            "dependency_effective_n_method": _DEPENDENCY_EFFECTIVE_N_METHOD,
            "no_strategy_expectancy_or_profit_factor": True,
            "no_net_edge_or_best_score": True,
            "no_threshold_parameter_or_rule_search": True,
            "no_selection_or_optimization": True,
            "no_causal_or_robustness_claim": True,
            "validation_holdout_external_unopened": True,
            "production_or_broker_effect": False,
        },
    }
    payload["artifact_fingerprint"] = _self_fingerprint(payload)
    return _write_once(Path(artifact_path), payload)


def build_v6_completion_summary(
    *,
    audit: Mapping[str, object] | Path | str,
    frozen_plan: Mapping[str, object] | Path | str,
    descriptive_report: Mapping[str, object] | Path | str,
    final_contract: Mapping[str, object] | Path | str | None = None,
    run_manifest: Mapping[str, object] | Path | str | None = None,
    input_precheck: Mapping[str, object] | Path | str | None = None,
    worker_benchmark: Mapping[str, object] | Path | str | None = None,
    runtime_status: Mapping[str, object] | None = None,
    artifact_paths: Mapping[str, object] | None = None,
    created_at: str,
    artifact_path: Path = DEFAULT_SUMMARY_ARTIFACT,
) -> dict[str, object]:
    """Create the immutable terminal hand-off after audit and description."""

    audit_payload = _load_verified(audit)
    plan = _load_verified(frozen_plan)
    report = _load_verified(descriptive_report)
    _validate_frozen_plan(plan)
    if audit_payload.get("status") != "PASS":
        raise DevelopmentV6ReportingError("Completion requires audit PASS.")
    if report.get("status") != "DESCRIPTIVE_COMPLETE":
        raise DevelopmentV6ReportingError("Completion requires descriptive report.")
    run_ids = {audit_payload.get("run_id"), report.get("run_id")}
    if len(run_ids) != 1:
        raise DevelopmentV6ReportingError("Completion artifacts belong to different runs.")
    if report.get("audit_fingerprint") != audit_payload.get("artifact_fingerprint"):
        raise DevelopmentV6ReportingError("Report does not link to supplied audit.")
    if report.get("frozen_plan_fingerprint") != plan.get("artifact_fingerprint"):
        raise DevelopmentV6ReportingError("Report does not link to supplied plan.")
    audit_skip_exclusions = dict(
        audit_payload.get("skipped_work_unit_exclusions") or {}
    )
    if dict(report.get("work_unit_exclusions") or {}) != audit_skip_exclusions:
        raise DevelopmentV6ReportingError(
            "Report skip classifications differ from the passed audit."
        )

    contract_payload: dict[str, object] = {}
    contract_artifact_fingerprint: object = None
    if final_contract is not None:
        raw_contract = _load_mapping_unverified(final_contract)
        if "contract" in raw_contract:
            if not verify_self_fingerprinted_artifact(raw_contract):
                raise DevelopmentV6ReportingError(
                    "Final contract artifact fingerprint is invalid."
                )
            contract_artifact_fingerprint = raw_contract.get("artifact_fingerprint")
            contract_payload = dict(raw_contract.get("contract") or {})
        else:
            contract_payload = raw_contract
        contract_basis = dict(contract_payload)
        claimed_contract_fingerprint = contract_basis.pop(
            "contract_fingerprint", None
        )
        if claimed_contract_fingerprint != fingerprint(contract_basis):
            raise DevelopmentV6ReportingError("Final contract fingerprint is invalid.")
        if claimed_contract_fingerprint != report.get("final_contract_fingerprint"):
            raise DevelopmentV6ReportingError(
                "Completion contract differs from descriptive report."
            )

    manifest: dict[str, object] = {}
    if run_manifest is not None:
        manifest = _load_mapping_unverified(run_manifest)
        manifest_basis = dict(manifest)
        claimed_manifest_fingerprint = manifest_basis.pop(
            "run_manifest_fingerprint", None
        )
        if claimed_manifest_fingerprint != fingerprint(manifest_basis):
            raise DevelopmentV6ReportingError("Run-manifest fingerprint is invalid.")
        if manifest.get("run_id") != next(iter(run_ids)):
            raise DevelopmentV6ReportingError(
                "Completion manifest belongs to a different run."
            )

    input_payload = (
        _load_verified(input_precheck) if input_precheck is not None else {}
    )
    benchmark_payload = (
        _load_verified(worker_benchmark) if worker_benchmark is not None else {}
    )
    references = dict(contract_payload.get("reference_fingerprints") or {})
    if input_payload and references.get("input_precheck_artifact_fingerprint") != (
        input_payload.get("artifact_fingerprint")
    ):
        raise DevelopmentV6ReportingError(
            "Completion input precheck differs from final contract."
        )
    if benchmark_payload and references.get(
        "worker_benchmark_artifact_fingerprint"
    ) != benchmark_payload.get("artifact_fingerprint"):
        raise DevelopmentV6ReportingError(
            "Completion benchmark differs from final contract."
        )
    if manifest and contract_payload:
        manifest_contract = manifest.get("development_contract_fingerprint")
        if manifest_contract != contract_payload.get("contract_fingerprint"):
            raise DevelopmentV6ReportingError(
                "Completion manifest differs from final contract."
            )

    runtime = dict(runtime_status or {})
    if runtime and runtime.get("run_id") != next(iter(run_ids)):
        raise DevelopmentV6ReportingError(
            "Runtime status belongs to a different completion run."
        )
    overall = dict(report.get("overall") or {})
    coverage_na = dict(overall.get("coverage_and_na") or {})
    r_status = dict(coverage_na.get("r_metrics_status") or {})
    r_reasons = dict(coverage_na.get("r_unavailable_reasons") or {})
    censoring = dict(overall.get("censoring") or {})
    observation_axis = dict(overall.get("observation_axis") or {})
    raw_n = int(dict(report.get("population") or {}).get("n") or 0)
    r_available_n = int(r_status.get("AVAILABLE") or 0)
    r_na_n = int(runtime.get("r_na_cases") or max(0, raw_n - r_available_n))
    censoring_reasons = dict(censoring.get("censoring_reason") or {})
    censored_n = int(
        runtime.get("censored_cases")
        or max(0, raw_n - int(censoring_reasons.get("NOT_CENSORED") or 0))
    )

    dependency_groups = {
        str(label): int(dict(value or {}).get("n") or 0)
        for label, value in dict(
            dict(report.get("groups") or {}).get("DEPENDENCY_STATUS") or {}
        ).items()
    }
    dependency_evidence = dict(report.get("dependency_evidence") or {})
    dependency_evidence_available = (
        dependency_evidence.get("version") == _DEPENDENCY_VERSION
        and dependency_evidence.get("effective_n_method")
        == _DEPENDENCY_EFFECTIVE_N_METHOD
    )
    temporal_coverage = dict(report.get("temporal_coverage") or {})
    temporal_coverage_available = bool(temporal_coverage)
    signal_day_coverage = dict(temporal_coverage.get("signal_days") or {})
    observation_boundary_coverage = dict(
        temporal_coverage.get("recorded_observation_boundary_days") or {}
    )
    full_observation_day_coverage = dict(
        temporal_coverage.get("full_distinct_observed_session_days") or {}
    )
    signal_year_groups = {
        str(label): int(dict(value or {}).get("n") or 0)
        for label, value in dict(
            dict(report.get("groups") or {}).get("SIGNAL_YEAR") or {}
        ).items()
    }
    input_contract = dict(input_payload.get("contract_inputs") or {})
    input_coverage = dict(input_payload.get("coverage") or {})
    compact_coverage: dict[str, object] = {}
    for asset_class, value in dict(input_coverage.get("by_asset_class") or {}).items():
        item = dict(value or {})
        compact_coverage[str(asset_class)] = {
            key: item.get(key)
            for key in (
                "coverage_assets",
                "active_assets",
                "no_data_assets",
                "active_rows",
                "invalid_source_bars",
                "eligible_signal_positions_after_gap_warmup",
                "first_active_day",
                "last_active_day",
            )
            if key in item
        }

    selected_worker_count = benchmark_payload.get("selected_worker_count")
    selected_configuration = next(
        (
            dict(item)
            for item in benchmark_payload.get("configurations") or []
            if int(dict(item).get("worker_count") or -1)
            == int(selected_worker_count or -2)
        ),
        {},
    )
    benchmark_metrics = {
        key: selected_configuration.get(key)
        for key in (
            "worker_count",
            "status",
            "wall_seconds",
            "throughput_cases_per_second",
            "case_count",
            "work_unit_count",
            "receipt_count",
            "peak_ram_upper_bound_bytes",
            "worker_process_count_observed",
            "worker_cpu_seconds",
            "parent_cpu_seconds",
            "central_writer_elapsed_seconds",
            "writer_wait_seconds_total",
            "writer_wait_seconds_max",
            "errors",
            "retries",
            "scientific_digest",
            "sqlite_writer_count",
        )
        if key in selected_configuration
    }
    execution = dict(contract_payload.get("development_execution") or {})
    stores = dict(contract_payload.get("store_contract") or {})
    normalized_paths = {
        str(key): str(value) for key, value in dict(artifact_paths or {}).items()
    }
    normalized_paths.setdefault("summary", str(Path(artifact_path).resolve()))

    project_snapshot: dict[str, object] = {
        "snapshot_kind": "COPYABLE_TECHNICAL_PROJECT_SNAPSHOT",
        "overall_status": "COMPLETED_AUDITED_AWAITING_REVIEW",
        "provenance": {
            "run_id": next(iter(run_ids)),
            "contract_fingerprint": report.get("final_contract_fingerprint"),
            "contract_artifact_fingerprint": contract_artifact_fingerprint,
            "source_dataset_fingerprint": input_contract.get(
                "source_dataset_fingerprint"
            )
            or references.get("dataset_fingerprint"),
            "combined_input_fingerprint": input_contract.get(
                "combined_input_fingerprint"
            )
            or dict(audit_payload.get("run") or {}).get(
                "combined_input_fingerprint"
            ),
            "universe_fingerprint": manifest.get("universe_fingerprint")
            or dict(audit_payload.get("run") or {}).get("universe_fingerprint"),
            "development_code_fingerprint": references.get(
                "development_code_fingerprint"
            ),
            "code_commit": manifest.get("commit")
            or dict(audit_payload.get("run") or {}).get("code_commit"),
            "work_plan_fingerprint": manifest.get("work_plan_fingerprint")
            or dict(audit_payload.get("run") or {}).get("work_plan_fingerprint"),
            "frozen_descriptive_plan_fingerprint": plan.get(
                "artifact_fingerprint"
            ),
            "descriptive_report_fingerprint": report.get("artifact_fingerprint"),
            "final_integrity_audit_fingerprint": audit_payload.get(
                "artifact_fingerprint"
            ),
            "input_precheck_fingerprint": input_payload.get(
                "artifact_fingerprint"
            ),
            "worker_benchmark_fingerprint": benchmark_payload.get(
                "artifact_fingerprint"
            ),
        },
        "versions": {
            "contract": contract_payload.get("contract_version"),
            "research_epoch": execution.get("research_epoch"),
            "store_schema": stores.get("schema_version"),
            "input_precheck": input_payload.get("version"),
            "gap_policy": dict(input_payload.get("gap_policy") or {}).get(
                "version"
            ),
            "benchmark": benchmark_payload.get("version"),
            "descriptive_plan": plan.get("version"),
            "final_integrity_audit": audit_payload.get("version"),
            "descriptive_report": report.get("version"),
            "completion_summary": SUMMARY_VERSION,
            "runner": manifest.get("runner_version"),
        },
        "inputs": {
            "development_period": list(input_payload.get("period") or []),
            "projection_fingerprints": {
                key: input_contract.get(key)
                for key in (
                    "equity_etf_projection_fingerprint",
                    "crypto_projection_fingerprint",
                    "fx_projection_fingerprint",
                )
            },
            "protected_input_hashes": {
                key: input_contract.get(key)
                for key in (
                    "equity_etf_store_sha256",
                    "crypto_store_sha256",
                    "fx_store_sha256",
                    "source_dataset_manifest_sha256",
                    "identity_store_sha256",
                )
            },
            "implementation_fingerprint": input_contract.get(
                "implementation_fingerprint"
            ),
            "coverage": {
                "planned_listings": input_coverage.get("asset_count"),
                "active_listings": input_coverage.get("active_asset_count"),
                "no_data_listings": input_coverage.get("no_data_asset_count"),
                "active_bars": input_coverage.get("active_bar_count"),
                "by_asset_class": compact_coverage,
            },
        },
        "benchmark": {
            "status": benchmark_payload.get("status") or "UNAVAILABLE",
            "selected_worker_count": selected_worker_count,
            "sqlite_writer_count": benchmark_payload.get("sqlite_writer_count"),
            "deterministic_payloads_equal": benchmark_payload.get(
                "deterministic_payloads_equal"
            ),
            "selection_rule": benchmark_payload.get("selection_rule"),
            "resources": dict(benchmark_payload.get("resources") or {}),
            "selected_configuration": benchmark_metrics,
        },
        "timeline": {
            "run_started_at": runtime.get("started_at")
            or dict(audit_payload.get("run") or {}).get("started_at"),
            "last_work_unit_id": runtime.get("last_completed_work_unit"),
            "last_work_unit_completed_at": runtime.get(
                "last_work_unit_completed_at"
            ),
            "last_checkpoint_at": runtime.get("last_checkpoint_at")
            or dict(audit_payload.get("run") or {}).get("last_checkpoint_at"),
            "compute_completed_at": runtime.get("completed_at")
            or dict(audit_payload.get("run") or {}).get("completed_at"),
            "final_audit_created_at": audit_payload.get("created_at"),
            "descriptive_report_created_at": report.get("created_at"),
            "completion_summary_created_at": created_at,
        },
        "counts": {
            "work_units": {
                "total": runtime.get("total_planned_work_units")
                or dict(audit_payload.get("counts") or {}).get("work_units"),
                "completed": runtime.get("completed"),
                "skipped": runtime.get("skipped"),
                "failed": runtime.get("failed"),
                "pending": runtime.get("pending"),
                "active": runtime.get("active"),
                "receipts": runtime.get("receipts")
                or dict(audit_payload.get("counts") or {}).get("receipts"),
                "status_counts": dict(
                    audit_payload.get("work_unit_status_counts") or {}
                ),
                "classification_counts": dict(
                    audit_payload.get("work_unit_classification_counts") or {}
                ),
                "skip_reasons": audit_skip_exclusions,
            },
            "cases": {
                "raw_n": raw_n,
                "feature_rows": dict(audit_payload.get("counts") or {}).get(
                    "feature_rows"
                ),
                "outcome_rows": dict(audit_payload.get("counts") or {}).get(
                    "outcome_rows"
                ),
                "fully_audited_pairs": dict(
                    audit_payload.get("counts") or {}
                ).get("audited_payload_pairs"),
                "r_na": r_na_n,
                "non_positive_structural_risk": int(
                    r_reasons.get("NON_POSITIVE_STRUCTURAL_RISK") or 0
                ),
                "censored": censored_n,
                "missing_reference_entry": runtime.get(
                    "missing_reference_entry"
                ),
                "missingness_exclusions": runtime.get("missingness_exclusions"),
            },
            "gaps_and_censoring": {
                "input_gap_boundary_provenance": dict(
                    input_payload.get("gap_boundary_provenance") or {}
                ),
                "cases_encountering_declared_gap_boundary": observation_axis.get(
                    "declared_data_gap_boundary_encountered_n"
                ),
                "outcome_status": dict(censoring.get("outcome_status") or {}),
                "censoring_reasons": censoring_reasons,
            },
        },
        "evidence_strength": {
            "raw_cases": raw_n,
            "unique_listings": {
                "status": (
                    "AVAILABLE_EXACT_FROM_STORED_IDENTITIES"
                    if dependency_evidence_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    dependency_evidence.get("raw_listings")
                    if dependency_evidence_available
                    else None
                ),
            },
            "listings": {
                "planned": input_coverage.get("asset_count"),
                "active": input_coverage.get("active_asset_count"),
                "no_data": input_coverage.get("no_data_asset_count"),
            },
            "development_period": list(input_payload.get("period") or []),
            "observed_signal_period": {
                "first_day": signal_day_coverage.get("first_day"),
                "last_day": signal_day_coverage.get("last_day"),
            },
            "observed_outcome_boundary_period": {
                "first_day": observation_boundary_coverage.get("first_day"),
                "last_day": observation_boundary_coverage.get("last_day"),
            },
            "signal_year_case_counts": signal_year_groups,
            "dependency_status_case_counts": dependency_groups,
            "distinct_signal_days": {
                "status": (
                    "AVAILABLE_EXACT_FROM_STORED_SIGNAL_DAYS"
                    if temporal_coverage_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    signal_day_coverage.get("distinct_n")
                    if temporal_coverage_available
                    else None
                ),
            },
            "distinct_recorded_observation_boundary_days": {
                "status": (
                    "AVAILABLE_EXACT_FOR_RECORDED_ENTRY_AND_END_BOUNDARIES"
                    if temporal_coverage_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    observation_boundary_coverage.get("distinct_n")
                    if temporal_coverage_available
                    else None
                ),
                "not_full_observation_session_day_count": True,
            },
            "distinct_observation_days": full_observation_day_coverage
            or {
                "status": "UNAVAILABLE_FROM_COMPACT_OUTCOME_PAYLOADS",
                "value": None,
            },
            "verified_known_issuer_relationship_count": {
                "status": (
                    "AVAILABLE_EXACT_FROM_STORED_VERIFIED_IDENTITIES"
                    if dependency_evidence_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    dependency_evidence.get("verified_dependency_observation_n")
                    if dependency_evidence_available
                    else None
                ),
                "unit": "CASE_OBSERVATIONS_WITH_VERIFIED_KNOWN_ISSUER",
            },
            "verified_issuer_clusters": {
                "status": (
                    "AVAILABLE_EXACT_FROM_STORED_VERIFIED_IDENTITIES"
                    if dependency_evidence_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    dependency_evidence.get("verified_issuer_clusters")
                    if dependency_evidence_available
                    else None
                ),
            },
            "dependency_unknown_cases": {
                "status": "AVAILABLE" if dependency_evidence_available else "UNAVAILABLE",
                "value": (
                    dependency_evidence.get("dependency_unknown_n")
                    if dependency_evidence_available
                    else None
                ),
                "contribution_to_effective_n": 0,
            },
            "temporal_dependency_episodes": {
                "status": (
                    dependency_evidence.get("effective_n_status")
                    if dependency_evidence_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    dependency_evidence.get("effective_independent_issuer_count")
                    if dependency_evidence_available
                    else None
                ),
                "method": (
                    dependency_evidence.get("effective_n_method")
                    if dependency_evidence_available
                    else None
                ),
            },
            "verified_issuer_adjusted_effective_n": {
                "status": (
                    dependency_evidence.get("effective_n_status")
                    if dependency_evidence_available
                    else "UNAVAILABLE"
                ),
                "value": (
                    dependency_evidence.get("effective_n_known_issuers_only")
                    if dependency_evidence_available
                    else None
                ),
                "method": (
                    dependency_evidence.get("effective_n_method")
                    if dependency_evidence_available
                    else None
                ),
                "unknown_dependency_contribution": 0,
                "raw_or_listing_counts_used_as_substitute": False,
            },
            "statistical_or_strategy_evidence_claimed": False,
        },
        "audit": {
            "status": audit_payload.get("status"),
            "issue_count": audit_payload.get("issue_count"),
            "gates": dict(audit_payload.get("gates") or {}),
            "digests": dict(audit_payload.get("digests") or {}),
            "all_payload_pairs_audited": audit_payload.get(
                "all_feature_outcome_payload_pairs_audited"
            ),
        },
        "artifact_paths": normalized_paths,
        "operations": {
            "status_command": (
                r".\.venv\Scripts\python.exe "
                r"scripts\run_multi_asset_development_v6_chain.py --status"
            ),
            "resume_command": (
                r".\.venv\Scripts\python.exe "
                r"scripts\run_multi_asset_development_v6_chain.py --resume"
            ),
            "pause_command": (
                r".\.venv\Scripts\python.exe "
                r"scripts\run_multi_asset_development_v6_chain.py --pause"
            ),
            "stop_command": (
                r".\.venv\Scripts\python.exe "
                r"scripts\run_multi_asset_development_v6_chain.py --stop"
            ),
            "terminal_runner_behavior": "NO_OP_AFTER_STOP",
            "local_runner_status": "TERMINAL_AWAITING_HUMAN_REVIEW",
            "model_resume_status": "NOT_DERIVABLE_FROM_LOCAL_RUN_ARTIFACTS",
        },
        "closed_paths": {
            "validation": True,
            "holdout": True,
            "external": True,
            "forward": True,
            "paper": True,
            "shadow": True,
            "production": True,
            "broker": True,
            "automatic_orders": True,
        },
        "interpretation": {
            "technical_completion_is_not_positive_strategy_evidence": True,
            "no_new_research_stage_opened": True,
            "human_review_required": True,
        },
    }
    if Path(artifact_path).exists():
        existing = _load_verified(Path(artifact_path))
        expected_links = {
            "status": "COMPLETED_AUDITED_AWAITING_REVIEW",
            "run_id": next(iter(run_ids)),
        }
        artifacts = dict(existing.get("artifacts") or {})
        linked = (
            dict(artifacts.get("frozen_descriptive_plan") or {}).get("fingerprint")
            == plan.get("artifact_fingerprint")
            and dict(artifacts.get("final_integrity_audit") or {}).get("fingerprint")
            == audit_payload.get("artifact_fingerprint")
            and dict(artifacts.get("descriptive_report") or {}).get("fingerprint")
            == report.get("artifact_fingerprint")
        )
        if (
            any(existing.get(key) != value for key, value in expected_links.items())
            or not linked
            or (
                final_contract is not None
                and dict(existing.get("project_snapshot") or {}).get("provenance")
                != project_snapshot["provenance"]
            )
        ):
            raise DevelopmentV6ReportingError(
                "Existing completion summary belongs to different inputs."
            )
        return existing

    payload: dict[str, object] = {
        "version": SUMMARY_VERSION,
        "status": "COMPLETED_AUDITED_AWAITING_REVIEW",
        "created_at": created_at,
        "run_id": next(iter(run_ids)),
        "run_status": dict(audit_payload.get("run") or {}).get("status"),
        "evidence_counts": dict(audit_payload.get("counts") or {}),
        "work_unit_exclusions": audit_skip_exclusions,
        "project_snapshot": project_snapshot,
        "artifacts": {
            "frozen_descriptive_plan": {
                "status": plan["status"],
                "fingerprint": plan["artifact_fingerprint"],
            },
            "final_integrity_audit": {
                "status": audit_payload["status"],
                "fingerprint": audit_payload["artifact_fingerprint"],
            },
            "descriptive_report": {
                "status": report["status"],
                "fingerprint": report["artifact_fingerprint"],
            },
        },
        "human_review_required_before_any_next_research_stage": True,
        "automatic_strategy_or_rule_change": False,
        "opened_stages": {
            "development": True,
            "validation": False,
            "holdout": False,
            "external": False,
            "forward": False,
            "paper": False,
            "shadow": False,
            "production": False,
            "broker": False,
        },
        "limitations": [
            "The report is descriptive and does not establish an edge.",
            "Small groups are retained with a warning and support no conclusion.",
            "Unavailable ATR or structural-R measurements remain unavailable.",
            "No parameter, threshold, rule, or hypothesis was selected.",
        ],
    }
    payload["artifact_fingerprint"] = _self_fingerprint(payload)
    return _write_once(Path(artifact_path), payload)


# Concise aliases for the chain orchestrator.
freeze_descriptive_plan = freeze_v6_descriptive_plan
build_descriptive_report = build_v6_descriptive_report
build_completion_summary = build_v6_completion_summary


__all__ = [
    "DEFAULT_PLAN_ARTIFACT",
    "DEFAULT_REPORT_ARTIFACT",
    "DEFAULT_SUMMARY_ARTIFACT",
    "DevelopmentV6ReportingError",
    "PLAN_VERSION",
    "REPORT_VERSION",
    "SUMMARY_VERSION",
    "build_completion_summary",
    "build_descriptive_report",
    "build_v6_completion_summary",
    "build_v6_descriptive_report",
    "freeze_descriptive_plan",
    "freeze_v6_descriptive_plan",
]
