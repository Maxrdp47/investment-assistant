from __future__ import annotations

"""Outcome-blinder Vertrag für eine spätere Swing-A/B/C-Kampagne.

Das Modul reserviert nur künftige Research-Pools. Es startet keine Kampagne,
öffnet keine ungesehene Evidenz und besitzt keinerlei Produktionswirkung.
"""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Mapping, Sequence

from swing_research_market_scope import (
    DIRECT_ASSET_SCOPES,
    MARKET_SCOPE_CONTRACT_VERSION,
    market_scope_contract,
    normalize_market_scopes,
)


SWING_ABC_V2_VERSION = "swing-ground-up-abc-2026.08.23-v2.1"
SWING_EFFECTIVE_N_VERSION = "swing-effective-n-2026.08.23-v1"
SWING_CAMPAIGN_V2_METHODOLOGY_VERSION = "swing-campaign-methodology-2026.08.23-v2.1"
ABC_ROUNDS = ("A", "B", "C")
RESEARCH_STAGES = ("entry", "stop", "exit_management", "full_challenger_oos")

_SELECTION_FIELDS = (
    "candidate_id",
    "signal_at",
    "signal_day",
    "label_end_day",
    "ticker",
    "listing_id",
    "issuer_id",
    "economic_instrument_id",
    "correlation_cluster",
    "asset_type",
    "region",
    "sector",
    "market_phase",
    "volatility_regime",
    "setup_type",
    "evaluation_horizon_sessions",
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _clean(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _day(value: object) -> str:
    text = str(value or "").strip()
    if len(text) < 10:
        raise ValueError("Ein Ground-up-Kandidat benötigt einen kausalen Signalstag.")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise ValueError("Ungültiger Signalstag im A/B/C-v2-Kandidaten.") from exc


def abc_v2_selection_projection(candidate: Mapping[str, object]) -> dict[str, object]:
    """Return the only fields pool selection is allowed to inspect."""
    candidate_id = _clean(candidate.get("candidate_id"), "")
    if not candidate_id:
        raise ValueError("Jeder Ground-up-Kandidat benötigt eine vorab erzeugte candidate_id.")
    signal_day = _day(candidate.get("signal_day") or candidate.get("signal_at"))
    label_end = candidate.get("label_end_day")
    if label_end not in (None, ""):
        label_end = _day(label_end)
        if str(label_end) < signal_day:
            raise ValueError("Das vorab bekannte Labelende darf nicht vor dem Signal liegen.")
    projected = {
        key: candidate.get(key)
        for key in _SELECTION_FIELDS
        if key in candidate
    }
    projected.update(
        {
            "candidate_id": candidate_id,
            "signal_day": signal_day,
            "label_end_day": label_end,
            "ticker": _clean(candidate.get("ticker")),
            "listing_id": _clean(candidate.get("listing_id")),
            "issuer_id": _clean(candidate.get("issuer_id")),
            "economic_instrument_id": _clean(candidate.get("economic_instrument_id")),
            "correlation_cluster": _clean(candidate.get("correlation_cluster")),
            "asset_type": _clean(candidate.get("asset_type")),
            "region": _clean(candidate.get("region")),
            "sector": _clean(candidate.get("sector")),
            "market_phase": _clean(candidate.get("market_phase")),
            "volatility_regime": _clean(candidate.get("volatility_regime")),
            "setup_type": _clean(candidate.get("setup_type")),
            "evaluation_horizon_sessions": int(
                candidate.get("evaluation_horizon_sessions") or 0
            ),
        }
    )
    return projected


def _time_bucket(signal_day: str) -> str:
    year = int(signal_day[:4])
    if year <= 2015:
        return "2010-2015"
    if year <= 2019:
        return "2016-2019"
    if year <= 2021:
        return "2020-2021"
    if year <= 2023:
        return "2022-2023"
    return "2024+"


def _trade_clusters(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Keep overlapping cases for the same economic identity in one pool."""
    parents = list(range(len(rows)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    tokens: dict[str, list[int]] = defaultdict(list)
    intervals = [_label_interval(row) for row in rows]
    for index, row in enumerate(rows):
        for key in ("ticker", "listing_id", "issuer_id", "economic_instrument_id"):
            value = _clean(row.get(key), "").casefold()
            if value and value not in {"unknown", "unbekannt", "none", "n/a"}:
                tokens[f"{key}:{value}"].append(index)

    for members in tokens.values():
        anchor: int | None = None
        component_end: date | None = None
        for index in sorted(members, key=lambda item: (intervals[item], str(rows[item]["candidate_id"]))):
            start, end = intervals[index]
            if anchor is None or component_end is None or start > component_end:
                anchor = index
                component_end = end
            else:
                union(anchor, index)
                if end > component_end:
                    component_end = end

    components: dict[int, list[dict[str, object]]] = defaultdict(list)
    for index, row in enumerate(rows):
        components[find(index)].append(dict(row))

    clusters: dict[str, list[dict[str, object]]] = {}
    for component_rows in components.values():
        candidate_ids = sorted(str(row["candidate_id"]) for row in component_rows)
        cluster_id = _fingerprint(
            {
                "version": SWING_EFFECTIVE_N_VERSION,
                "candidate_ids": candidate_ids,
            }
        )
        clusters[cluster_id] = component_rows
    return clusters


def _stratum(row: Mapping[str, object]) -> tuple[str, ...]:
    return (
        _time_bucket(str(row["signal_day"])),
        _clean(row.get("asset_type")),
        _clean(row.get("region")),
        _clean(row.get("market_phase")),
        _clean(row.get("volatility_regime")),
    )


def _pool_coverage(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "time_buckets": dict(Counter(_time_bucket(str(row["signal_day"])) for row in rows)),
        "asset_types": dict(Counter(_clean(row.get("asset_type")) for row in rows)),
        "regions": dict(Counter(_clean(row.get("region")) for row in rows)),
        "market_phases": dict(Counter(_clean(row.get("market_phase")) for row in rows)),
        "volatility_regimes": dict(
            Counter(_clean(row.get("volatility_regime")) for row in rows)
        ),
        "real_frequency_preserved": True,
        "artificial_quota_enforced": False,
    }


def reserve_abc_v2_pools(
    candidates: Sequence[Mapping[str, object]],
    *,
    challenger_version: str,
    challenger_fingerprint: str,
    dataset_fingerprint: str,
    market_scopes: Sequence[str],
    seed: str,
    minimum_effective_n_per_round: int,
) -> dict[str, object]:
    """Freeze three outcome-blind, disjoint pools before any result is inspected."""
    if not _clean(challenger_version, "") or not _clean(challenger_fingerprint, ""):
        raise ValueError("A/B/C v2 benötigt einen vorab eingefrorenen Challenger.")
    if not _clean(dataset_fingerprint, ""):
        raise ValueError("A/B/C v2 benötigt einen eingefrorenen Datensatzfingerabdruck.")
    if int(minimum_effective_n_per_round) < 1:
        raise ValueError("Minimum Effective-N muss vor Kampagnenstart positiv festgelegt sein.")
    tested_market_scopes = normalize_market_scopes(
        market_scopes, field="campaign.market_scope"
    )
    if not set(tested_market_scopes) & DIRECT_ASSET_SCOPES:
        raise ValueError("Eine reale A/B/C-v2-Kampagne benötigt einen konkreten Asset-Market-Scope.")

    projections = [abc_v2_selection_projection(candidate) for candidate in candidates]
    ids = [str(row["candidate_id"]) for row in projections]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate_id ist innerhalb des A/B/C-v2-Vertrags nicht eindeutig.")

    clusters = _trade_clusters(projections)
    strata: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for cluster_id, rows in clusters.items():
        representative = min(rows, key=lambda item: str(item["candidate_id"]))
        strata[_stratum(representative)].append(cluster_id)

    pool_clusters: dict[str, list[str]] = {round_name: [] for round_name in ABC_ROUNDS}
    pool_candidates: dict[str, list[str]] = {round_name: [] for round_name in ABC_ROUNDS}
    for stratum, cluster_ids in sorted(strata.items()):
        ordered = sorted(
            cluster_ids,
            key=lambda cluster_id: _fingerprint(
                {
                    "version": SWING_ABC_V2_VERSION,
                    "seed": seed,
                    "stratum": stratum,
                    "cluster_id": cluster_id,
                }
            ),
        )
        offset = int(_fingerprint({"seed": seed, "stratum": stratum})[:8], 16) % 3
        for index, cluster_id in enumerate(ordered):
            round_name = ABC_ROUNDS[(index + offset) % 3]
            pool_clusters[round_name].append(cluster_id)
            pool_candidates[round_name].extend(
                str(row["candidate_id"]) for row in clusters[cluster_id]
            )

    pools: dict[str, dict[str, object]] = {}
    for round_name in ABC_ROUNDS:
        candidate_ids = sorted(pool_candidates[round_name])
        cluster_ids = sorted(pool_clusters[round_name])
        candidate_id_set = set(candidate_ids)
        selected_rows = [
            row for row in projections if str(row["candidate_id"]) in candidate_id_set
        ]
        payload = {
            "round": round_name,
            "role": {
                "A": "exploration_development",
                "B": "independent_locked_confirmation",
                "C": "second_independent_final_confirmation",
            }[round_name],
            "candidate_ids": candidate_ids,
            "trade_cluster_ids": cluster_ids,
            "raw_candidates": len(candidate_ids),
            "coverage": _pool_coverage(selected_rows),
            "pre_reserved": True,
            "outcomes_seen": False,
        }
        payload["pool_fingerprint"] = _fingerprint(payload)
        pools[round_name] = payload

    candidate_sets = [set(pools[name]["candidate_ids"]) for name in ABC_ROUNDS]
    cluster_sets = [set(pools[name]["trade_cluster_ids"]) for name in ABC_ROUNDS]
    if any(candidate_sets[left] & candidate_sets[right] for left in range(3) for right in range(left + 1, 3)):
        raise AssertionError("A/B/C-v2-Kandidatenpools überschneiden sich.")
    if any(cluster_sets[left] & cluster_sets[right] for left in range(3) for right in range(left + 1, 3)):
        raise AssertionError("Ein Trade-Cluster wurde als unabhängige Bestätigung wiederverwendet.")

    contract = {
        "version": SWING_ABC_V2_VERSION,
        "status": "prepared_not_started",
        "challenger_version": challenger_version,
        "challenger_fingerprint": challenger_fingerprint,
        "dataset_fingerprint": dataset_fingerprint,
        "market_scope": list(tested_market_scopes),
        "seed": str(seed),
        "minimum_effective_n_per_round": int(minimum_effective_n_per_round),
        "selection_input_fields": list(_SELECTION_FIELDS),
        "outcome_fields_used_for_selection": False,
        "pools_frozen_before_results": True,
        "all_candidate_ids_reserved_exactly_once": (
            sorted(candidate_id for pool in pools.values() for candidate_id in pool["candidate_ids"])
            == sorted(ids)
        ),
        "ground_up_trade_generation_required": True,
        "prior_round_results_may_change_later_pools": False,
        "same_trade_cluster_may_confirm_twice": False,
        "resume": {
            "pool_membership_immutable": True,
            "completed_candidate_ids_only": True,
            "outcomes_may_change_pending_selection": False,
            "duplicate_jobs_allowed": False,
            "append_only_results_required": True,
        },
        "a_b_c_replace_validation_holdout": False,
        "subsequent_gates": [
            "development",
            "validation",
            "holdout",
            "external",
            "true_forward",
        ],
        "identical_cost_contract_required": True,
        "identical_execution_contract_required": True,
        "automatic_strategy_selection": False,
        "automatic_c_classification": False,
        "automatic_production_activation": False,
        "short_activation": False,
        "broker_order_allowed": False,
        "execution_allowed": False,
        "pools": pools,
    }
    contract["contract_fingerprint"] = _fingerprint(contract)
    return contract


def abc_v2_resume_plan(
    frozen_contract: Mapping[str, object],
    *,
    completed_candidate_ids: Sequence[str],
) -> dict[str, object]:
    """Derive pending work without ever changing the pre-reserved pools."""
    contract = dict(frozen_contract)
    if contract.get("version") != SWING_ABC_V2_VERSION:
        raise ValueError("Resume benötigt einen A/B/C-v2-Vertrag.")
    expected_contract_fingerprint = str(contract.pop("contract_fingerprint", ""))
    if not expected_contract_fingerprint or _fingerprint(contract) != expected_contract_fingerprint:
        raise ValueError("Der eingefrorene A/B/C-v2-Vertrag wurde verändert.")

    pools = dict(contract.get("pools") or {})
    all_ids: set[str] = set()
    for round_name in ABC_ROUNDS:
        pool = dict(pools.get(round_name) or {})
        expected_pool_fingerprint = str(pool.pop("pool_fingerprint", ""))
        if not expected_pool_fingerprint or _fingerprint(pool) != expected_pool_fingerprint:
            raise ValueError(f"A/B/C-v2-Pool {round_name} wurde verändert.")
        all_ids.update(str(value) for value in pool.get("candidate_ids") or [])

    completed_list = [str(value) for value in completed_candidate_ids]
    if len(completed_list) != len(set(completed_list)):
        raise ValueError("Resume-Status enthält doppelte candidate_id-Werte.")
    unknown = sorted(set(completed_list) - all_ids)
    if unknown:
        raise ValueError("Resume-Status enthält unbekannte candidate_id-Werte.")
    completed = set(completed_list)
    pending = {
        round_name: [
            str(candidate_id)
            for candidate_id in dict(pools[round_name]).get("candidate_ids") or []
            if str(candidate_id) not in completed
        ]
        for round_name in ABC_ROUNDS
    }
    result: dict[str, object] = {
        "version": SWING_ABC_V2_VERSION,
        "contract_fingerprint": expected_contract_fingerprint,
        "completed_candidate_ids": sorted(completed),
        "pending_candidate_ids_by_round": pending,
        "pending_total": sum(len(values) for values in pending.values()),
        "pool_membership_changed": False,
        "outcomes_used": False,
        "duplicate_jobs_allowed": False,
    }
    result["resume_fingerprint"] = _fingerprint(result)
    return result


def _label_interval(row: Mapping[str, object]) -> tuple[date, date]:
    start = date.fromisoformat(str(row["signal_day"]))
    if row.get("label_end_day"):
        return start, date.fromisoformat(str(row["label_end_day"]))
    sessions = max(int(row.get("evaluation_horizon_sessions") or 0), 0)
    conservative_calendar_days = (sessions * 7 + 4) // 5 + (3 if sessions else 0)
    return start, start + timedelta(days=conservative_calendar_days)


def _episode_count(
    rows: Sequence[Mapping[str, object]],
    dependency_field: str,
) -> tuple[int, int]:
    """Count non-overlapping label episodes within one dependency identity.

    Unknown identities never get merged.  This avoids pretending that every
    missing issuer or correlation cluster is the same economic object.
    """
    groups: dict[str, list[tuple[date, date]]] = defaultdict(list)
    known_rows = 0
    for row in rows:
        value = _clean(row.get(dependency_field), "").casefold()
        if not value or value in {"unknown", "unbekannt", "none", "n/a"}:
            value = f"__missing__:{row['candidate_id']}"
        else:
            known_rows += 1
        groups[value].append(_label_interval(row))

    episodes = 0
    for intervals in groups.values():
        current_end: date | None = None
        for start, end in sorted(intervals):
            if current_end is None or start > current_end:
                episodes += 1
                current_end = end
            elif end > current_end:
                current_end = end
    return episodes, known_rows


def effective_n_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    projections = [abc_v2_selection_projection(row) for row in rows]
    candidate_ids = [str(row["candidate_id"]) for row in projections]
    unique_signal_days = len({str(row["signal_day"]) for row in projections})
    episode_counts: dict[str, dict[str, int]] = {}
    hard_limits = [len(projections), len(set(candidate_ids)), unique_signal_days]
    for key in (
        "ticker",
        "listing_id",
        "issuer_id",
        "economic_instrument_id",
        "correlation_cluster",
    ):
        episodes, known_rows = _episode_count(projections, key)
        episode_counts[key] = {
            "non_overlapping_episodes": episodes,
            "rows_with_known_identity": known_rows,
        }
        if known_rows:
            hard_limits.append(episodes)
    effective_n = min(hard_limits, default=0)
    dimensions = {}
    for key in (
        "signal_day",
        "ticker",
        "listing_id",
        "issuer_id",
        "economic_instrument_id",
        "sector",
        "region",
        "market_phase",
        "volatility_regime",
        "correlation_cluster",
    ):
        values = [_clean(row.get(key), "") for row in projections]
        known_values = [
            value
            for value in values
            if value and value.casefold() not in {"unknown", "unbekannt", "none", "n/a"}
        ]
        counts = Counter(known_values)
        unavailable = len(values) - len(known_values)
        largest_group = max(counts.values(), default=0)
        dimensions[key] = {
            "groups": len(counts),
            "largest_group": largest_group,
            "largest_group_share_pct": (
                round(largest_group / len(projections) * 100, 4)
                if projections and counts
                else None
            ),
            "unavailable": unavailable,
        }
    return {
        "version": SWING_EFFECTIVE_N_VERSION,
        "raw_n": len(rows),
        "effective_n": effective_n,
        "unique_candidate_ids": len(set(candidate_ids)),
        "unique_signal_days": unique_signal_days,
        "non_overlapping_dependency_episodes": episode_counts,
        "dependency_method": (
            "minimum_of_raw_unique_candidates_signal_days_and_non_overlapping_"
            "ticker_listing_issuer_instrument_correlation_episodes"
        ),
        "concentration": dimensions,
        "concentration_dimensions_considered": [
            "sector",
            "region",
            "market_phase",
            "volatility_regime",
        ],
        "effective_n_le_raw_n": effective_n <= len(rows),
        "raw_trades_are_independent_evidence": False,
    }


def round_evidence_status(
    *,
    raw_n: int,
    effective_n: int,
    minimum_effective_n: int,
    valid: bool = True,
) -> str:
    if (
        not valid
        or raw_n < 0
        or effective_n < 0
        or effective_n > raw_n
        or int(minimum_effective_n) < 1
    ):
        return "invalid"
    if raw_n == 0:
        return "empty"
    if effective_n < max(int(minimum_effective_n), 1):
        return "underpowered"
    return "sufficient"


def abc_v2_round_report(
    rows: Sequence[Mapping[str, object]],
    *,
    minimum_effective_n: int,
    valid: bool = True,
) -> dict[str, object]:
    evidence = effective_n_report(rows)
    integrity_valid = bool(valid) and evidence["unique_candidate_ids"] == evidence["raw_n"]
    status = round_evidence_status(
        raw_n=int(evidence["raw_n"]),
        effective_n=int(evidence["effective_n"]),
        minimum_effective_n=minimum_effective_n,
        valid=integrity_valid,
    )
    return {
        **evidence,
        "minimum_effective_n_predeclared": int(minimum_effective_n),
        "status": status,
        "case_identity_valid": evidence["unique_candidate_ids"] == evidence["raw_n"],
        "performance_conclusion_allowed": status == "sufficient",
        "underpowered_means_no_conclusion": status == "underpowered",
        "automatic_c_classification": False,
        "automatic_production_activation": False,
    }


def campaign_v2_methodology_contract() -> dict[str, object]:
    """Return the immutable design contract for a future, not-yet-started campaign."""
    contract: dict[str, object] = {
        "version": SWING_CAMPAIGN_V2_METHODOLOGY_VERSION,
        "abc_version": SWING_ABC_V2_VERSION,
        "effective_n_version": SWING_EFFECTIVE_N_VERSION,
        "market_scope_contract_version": MARKET_SCOPE_CONTRACT_VERSION,
        "status": "prepared_not_started",
        "v1_reference": {
            "immutable": True,
            "may_rewrite_cases": False,
            "may_rewrite_results": False,
            "may_change_fingerprints": False,
            "may_backfill_or_correct_research_artifacts": False,
        },
        "current_broad_pass": {
            "may_change_dataset": False,
            "may_change_feature_contract": False,
            "may_change_fingerprints": False,
            "may_restart": False,
            "may_inject_features": False,
        },
        "prerequisites": [
            "manually_selected_ground_up_challenger",
            "frozen_challenger_version_and_fingerprint",
            "frozen_dataset_fingerprint",
            "frozen_cost_and_execution_contract",
            "outcome_blind_candidate_universe",
            "predeclared_minimum_effective_n_per_round",
            "frozen_test_market_scopes",
        ],
        "abc": {
            "all_pools_reserved_before_first_result": True,
            "roles": {
                "A": "exploration_development",
                "B": "independent_locked_confirmation",
                "C": "second_independent_final_confirmation",
            },
            "prior_round_may_supply_remainder_to_later_round": False,
            "same_trade_cluster_may_confirm_twice": False,
            "deterministic_resume_from_completed_candidate_ids": True,
            "selection_may_use_outcomes": False,
            "ground_up_application_in_every_pool": True,
            "stratification_dimensions": [
                "time",
                "asset_type",
                "region",
                "market_phase",
                "volatility_regime",
            ],
            "preserve_real_frequency": True,
            "artificial_quotas": False,
            "round_statuses": ["sufficient", "underpowered", "empty", "invalid"],
            "underpowered_means_no_conclusion": True,
            "raw_n_and_effective_n_required": True,
            "market_scope_required": True,
            "cross_market_validation_inherited": False,
        },
        "effective_n": {
            "hard_dependencies": [
                "candidate_identity",
                "signal_day",
                "ticker",
                "listing",
                "issuer",
                "economic_instrument",
                "overlapping_label_window",
                "correlation_cluster",
            ],
            "reported_concentration": [
                "sector",
                "region",
                "market_phase",
                "volatility_regime",
            ],
            "raw_trades_assumed_independent": False,
        },
        "research_sequence": {
            "order": list(RESEARCH_STAGES),
            "entry_metrics": [
                "future_return",
                "mfe_1_3_5_sessions",
                "mae_1_3_5_sessions",
                "entry_efficiency",
                "time_to_plus_0_5r",
                "time_to_plus_1r",
                "first_plus_0_5r_or_minus_0_5r",
                "peak_mfe",
                "mfe_lost_until_exit",
            ],
            "daily_intrabar_order_may_be_invented": False,
            "entry_must_freeze_before_stop": True,
            "stop_must_freeze_before_exit": True,
            "exit_must_freeze_before_full_oos": True,
            "entry_stop_exit_grid_allowed": False,
            "crv_2_is_only_long_v1_baseline": True,
            "free_crv_optimization_allowed": False,
        },
        "quality_protection": {
            "selection_objective": "expected_r_after_costs",
            "hit_rate_is_primary_objective": False,
            "feature_families": [
                "trend_momentum",
                "volatility",
                "structure",
                "confirmation",
                "market_environment",
                "external_event",
                "execution_risk",
            ],
            "correlated_features_are_independent_votes": False,
            "ablation_required": True,
            "prefer_simpler_when_oos_equivalent": True,
            "predeclared_parameter_plateau_required": True,
            "razor_thin_optimum_accepted": False,
            "negative_controls": [
                "regime_matched_random_days",
                "time_shifted_signals",
                "simple_control_strategy",
                "matched_holding_period",
            ],
            "append_only_multiple_testing_ledger_required": True,
            "discarded_variants_remain_visible": True,
            "automatic_parameter_search": False,
        },
        "evidence_gates": {
            "abc_is_internal_robustness_not_holdout": True,
            "sequence_after_research_freeze": [
                "validation",
                "manual_review",
                "holdout",
                "external",
                "true_forward",
            ],
            "historical_broad_validation_holdout_external_true_forward_paper_shadow_separate": True,
            "combined_hit_rate": False,
            "rule_change_after_unseen_evidence_opens": False,
            "validated_plus_matching_market_scope_required": True,
            "cross_market_transfer_requires_new_experiment": True,
        },
        "survivorship": {
            "current_frozen_universe_fully_point_in_time": False,
            "later_audit_required": [
                "delistings",
                "bankruptcies",
                "former_index_members",
                "former_listings",
                "non_surviving_companies",
            ],
            "blocks_current_broad_pass": False,
            "high_confidence_without_quantified_risk": False,
        },
        "automatic_strategy_selection": False,
        "automatic_c_classification": False,
        "automatic_validation_or_holdout_open": False,
        "automatic_production_activation": False,
        "short_activation": False,
        "broker_order_allowed": False,
        "execution_allowed": False,
    }
    contract["contract_fingerprint"] = _fingerprint(contract)
    return contract


def validate_v2_stage_request(
    stage: str,
    *,
    frozen_stage_fingerprints: Mapping[str, str],
    changed_dimensions: Sequence[str],
) -> dict[str, object]:
    """Fail closed if v2 attempts to tune Entry, Stop and Exit together."""
    clean_stage = _clean(stage, "")
    if clean_stage not in RESEARCH_STAGES:
        raise ValueError(f"Unbekannte v2-Research-Stufe: {clean_stage or '<leer>'}")
    dimensions = {_clean(value, "") for value in changed_dimensions}
    if "" in dimensions:
        raise ValueError("Leere Research-Dimension ist nicht zulässig.")
    requirements = {
        "entry": (),
        "stop": ("entry",),
        "exit_management": ("entry", "stop"),
        "full_challenger_oos": ("entry", "stop", "exit_management"),
    }
    allowed = {
        "entry": {"setup", "entry"},
        "stop": {"stop"},
        "exit_management": {"exit", "management"},
        "full_challenger_oos": set(),
    }
    missing = [
        predecessor
        for predecessor in requirements[clean_stage]
        if not _clean(frozen_stage_fingerprints.get(predecessor), "")
    ]
    if missing:
        raise ValueError(
            "Vorgängerstufe nicht manuell eingefroren: " + ", ".join(missing)
        )
    forbidden = sorted(dimensions - allowed[clean_stage])
    if forbidden:
        raise ValueError(
            f"Stufe {clean_stage} darf diese Dimensionen nicht verändern: "
            + ", ".join(forbidden)
        )
    if clean_stage != "full_challenger_oos" and not dimensions:
        raise ValueError("Eine Research-Stufe benötigt eine vorab benannte Fragestellung.")
    return {
        "version": SWING_CAMPAIGN_V2_METHODOLOGY_VERSION,
        "stage": clean_stage,
        "changed_dimensions": sorted(dimensions),
        "required_freezes": list(requirements[clean_stage]),
        "freeze_fingerprints": {
            key: str(frozen_stage_fingerprints[key])
            for key in requirements[clean_stage]
        },
        "valid": True,
        "automatic_freeze": False,
        "automatic_strategy_selection": False,
        "automatic_production_activation": False,
    }


def prepare_v2_hypothesis(
    *,
    family: str,
    question: str,
    source_market_scopes: Sequence[str],
    test_market_scopes: Sequence[str],
    stage: str,
    changed_dimensions: Sequence[str],
    frozen_stage_fingerprints: Mapping[str, str],
    predeclared_parameters: Mapping[str, object],
    dataset_fingerprint: str,
    feature_fingerprint: str,
    code_fingerprint: str,
    family_attempt_ordinal: int,
) -> dict[str, object]:
    """Prepare an unevaluated ledger row; persistence must remain append-only."""
    stage_contract = validate_v2_stage_request(
        stage,
        frozen_stage_fingerprints=frozen_stage_fingerprints,
        changed_dimensions=changed_dimensions,
    )
    scope_contract = market_scope_contract(
        source_scopes=source_market_scopes,
        test_scopes=test_market_scopes,
    )
    required_text = {
        "family": family,
        "question": question,
        "dataset_fingerprint": dataset_fingerprint,
        "feature_fingerprint": feature_fingerprint,
        "code_fingerprint": code_fingerprint,
    }
    empty = [key for key, value in required_text.items() if not _clean(value, "")]
    if empty:
        raise ValueError("Fehlende v2-Hypothesenfelder: " + ", ".join(empty))
    if int(family_attempt_ordinal) < 1:
        raise ValueError("Der Familien-Versuchszähler muss bei 1 beginnen.")
    parameter_dimensions = {_clean(key, "") for key in predeclared_parameters}
    expected_dimensions = {_clean(value, "") for value in changed_dimensions}
    if parameter_dimensions != expected_dimensions:
        raise ValueError(
            "Parameter müssen ausschließlich unter den vorab benannten "
            "Research-Dimensionen gruppiert sein."
        )
    registration: dict[str, object] = {
        "version": SWING_CAMPAIGN_V2_METHODOLOGY_VERSION,
        "status": "registered_not_evaluated",
        "family": str(family),
        "family_attempt_ordinal": int(family_attempt_ordinal),
        "question": str(question),
        "market_scope_contract": scope_contract,
        "stage_contract": stage_contract,
        "predeclared_parameters": dict(predeclared_parameters),
        "dataset_fingerprint": str(dataset_fingerprint),
        "feature_fingerprint": str(feature_fingerprint),
        "code_fingerprint": str(code_fingerprint),
        "outcomes_seen": False,
        "append_only_required": True,
        "discarded_attempt_may_be_hidden": False,
        "automatic_parameter_search": False,
        "automatic_strategy_selection": False,
        "automatic_production_activation": False,
    }
    registration["hypothesis_fingerprint"] = _fingerprint(registration)
    return registration
