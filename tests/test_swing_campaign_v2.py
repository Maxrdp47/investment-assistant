from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from swing_campaign_v2 import (
    SWING_ABC_V2_VERSION,
    SWING_CAMPAIGN_V2_METHODOLOGY_VERSION,
    abc_v2_resume_plan,
    abc_v2_round_report,
    campaign_v2_methodology_contract,
    effective_n_report,
    prepare_v2_hypothesis,
    reserve_abc_v2_pools,
    round_evidence_status,
    validate_v2_stage_request,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _candidate(index: int) -> dict[str, object]:
    day = index % 12 + 1
    return {
        "candidate_id": f"candidate-{index:02d}",
        "signal_day": f"2024-01-{day:02d}",
        "label_end_day": f"2024-02-{day:02d}",
        "ticker": f"T{index:02d}",
        "listing_id": f"listing-{index:02d}",
        "issuer_id": f"issuer-{index:02d}",
        "economic_instrument_id": f"instrument-{index:02d}",
        "correlation_cluster": f"cluster-{index % 4}",
        "asset_type": "stock",
        "region": "Europe" if index % 2 else "North America",
        "sector": "Industrials" if index % 3 else "Technology",
        "market_phase": "bull" if index % 2 else "sideways",
        "volatility_regime": "normal",
        "setup_type": "pullback" if index % 2 else "breakout",
        "evaluation_horizon_sessions": 25,
    }


def _reserve(candidates: list[dict[str, object]]) -> dict[str, object]:
    return reserve_abc_v2_pools(
        candidates,
        challenger_version="ground-up-challenger-v2",
        challenger_fingerprint="challenger-fingerprint-v2",
        dataset_fingerprint="future-frozen-dataset-v2",
        seed="pre-result-seed-v2",
        minimum_effective_n_per_round=40,
    )


def test_methodology_config_is_future_only_and_not_started() -> None:
    path = PROJECT_ROOT / "config" / "swing_campaign_v2_methodology.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    runtime = campaign_v2_methodology_contract()

    assert payload["version"] == runtime["version"] == SWING_CAMPAIGN_V2_METHODOLOGY_VERSION
    assert payload["abc_version"] == runtime["abc_version"] == SWING_ABC_V2_VERSION
    assert payload["status"] == runtime["status"] == "prepared_not_started"
    assert payload["scope"] == "future_campaigns_only"
    assert payload["v1_reference_immutable"] is True
    assert payload["current_broad_pass_immutable"] is True
    assert payload["automatic_strategy_selection"] is False
    assert payload["automatic_production_activation"] is False
    assert payload["short_activation"] is False
    assert payload["broker_order_allowed"] is False
    assert runtime["v1_reference"]["may_rewrite_cases"] is False
    assert runtime["current_broad_pass"]["may_restart"] is False


def test_v2_planning_is_pure_and_does_not_mutate_candidate_inputs(monkeypatch) -> None:
    candidates = [_candidate(index) for index in range(12)]
    original = copy.deepcopy(candidates)

    def _forbid_file_access(*args, **kwargs):
        raise AssertionError("v2-Planung darf keine v1-/Broad-Datei öffnen")

    monkeypatch.setattr("builtins.open", _forbid_file_access)
    contract = _reserve(candidates)
    effective = effective_n_report(candidates)
    methodology = campaign_v2_methodology_contract()

    assert candidates == original
    assert contract["status"] == "prepared_not_started"
    assert effective["effective_n_le_raw_n"] is True
    assert methodology["v1_reference"]["immutable"] is True


def test_abc_v2_reservation_is_deterministic_disjoint_and_complete() -> None:
    candidates = [_candidate(index) for index in range(30)]

    first = _reserve(candidates)
    second = _reserve(list(reversed(candidates)))

    assert first == second
    assert first["all_candidate_ids_reserved_exactly_once"] is True
    candidate_sets = {
        name: set(pool["candidate_ids"])
        for name, pool in first["pools"].items()
    }
    cluster_sets = {
        name: set(pool["trade_cluster_ids"])
        for name, pool in first["pools"].items()
    }
    assert set.union(*candidate_sets.values()) == {
        str(row["candidate_id"]) for row in candidates
    }
    assert all(
        not candidate_sets[left] & candidate_sets[right]
        for left, right in (("A", "B"), ("A", "C"), ("B", "C"))
    )
    assert all(
        not cluster_sets[left] & cluster_sets[right]
        for left, right in (("A", "B"), ("A", "C"), ("B", "C"))
    )
    assert all(pool["coverage"]["artificial_quota_enforced"] is False for pool in first["pools"].values())


def test_abc_v2_pool_selection_is_outcome_blind_and_prior_results_cannot_change_it() -> None:
    candidates = [_candidate(index) for index in range(24)]
    with_outcomes = copy.deepcopy(candidates)
    for index, row in enumerate(with_outcomes):
        row.update(
            {
                "result_r": 4.0 if index % 2 else -1.0,
                "status": "win" if index % 2 else "loss",
                "mfe_r": 7.0,
                "mae_r": -2.0,
                "round_a_result": "passed",
            }
        )

    before = _reserve(candidates)
    after = _reserve(with_outcomes)

    assert before == after
    assert before["outcome_fields_used_for_selection"] is False
    assert before["prior_round_results_may_change_later_pools"] is False


def test_same_trade_cluster_cannot_be_reused_as_independent_confirmation() -> None:
    candidates = [_candidate(index) for index in range(9)]
    duplicate_cluster = copy.deepcopy(candidates[0])
    duplicate_cluster["candidate_id"] = "same-trade-second-case"
    duplicate_cluster["signal_day"] = "2024-01-02"
    duplicate_cluster["label_end_day"] = "2024-02-02"
    candidates.append(duplicate_cluster)

    contract = _reserve(candidates)
    owning_pools = [
        round_name
        for round_name, pool in contract["pools"].items()
        if {"candidate-00", "same-trade-second-case"} <= set(pool["candidate_ids"])
    ]

    assert owning_pools in (["A"], ["B"], ["C"])
    assert contract["same_trade_cluster_may_confirm_twice"] is False


def test_resume_is_deterministic_and_cannot_repartition_or_duplicate_work() -> None:
    contract = _reserve([_candidate(index) for index in range(18)])
    completed = sorted(contract["pools"]["A"]["candidate_ids"][:2])

    first = abc_v2_resume_plan(contract, completed_candidate_ids=completed)
    second = abc_v2_resume_plan(contract, completed_candidate_ids=list(reversed(completed)))

    assert first == second
    assert first["pool_membership_changed"] is False
    assert first["outcomes_used"] is False
    assert first["duplicate_jobs_allowed"] is False
    pending_ids = {
        candidate_id
        for values in first["pending_candidate_ids_by_round"].values()
        for candidate_id in values
    }
    assert not pending_ids & set(completed)
    with pytest.raises(ValueError, match="doppelte"):
        abc_v2_resume_plan(contract, completed_candidate_ids=[completed[0], completed[0]])


def test_each_pool_reports_time_asset_and_regime_coverage_without_forced_quota() -> None:
    candidates = [_candidate(index) for index in range(30)]
    candidates[0]["signal_day"] = "2014-05-12"
    candidates[0]["label_end_day"] = "2014-06-16"
    candidates[1]["signal_day"] = "2018-05-12"
    candidates[1]["label_end_day"] = "2018-06-16"
    candidates[2]["signal_day"] = "2021-05-12"
    candidates[2]["label_end_day"] = "2021-06-16"
    candidates[3]["signal_day"] = "2023-05-12"
    candidates[3]["label_end_day"] = "2023-06-16"

    contract = _reserve(candidates)

    for pool in contract["pools"].values():
        coverage = pool["coverage"]
        assert set(coverage) >= {
            "time_buckets",
            "asset_types",
            "regions",
            "market_phases",
            "volatility_regimes",
        }
        assert coverage["real_frequency_preserved"] is True
        assert coverage["artificial_quota_enforced"] is False


def test_effective_n_is_conservative_deterministic_and_never_exceeds_raw_n() -> None:
    rows = [_candidate(index) for index in range(4)]
    rows[1]["signal_day"] = rows[0]["signal_day"]
    rows[1]["label_end_day"] = rows[0]["label_end_day"]
    rows[2]["ticker"] = rows[0]["ticker"]
    rows[2]["listing_id"] = rows[0]["listing_id"]
    rows[2]["issuer_id"] = rows[0]["issuer_id"]
    rows[2]["economic_instrument_id"] = rows[0]["economic_instrument_id"]

    report = effective_n_report(rows)

    assert report == effective_n_report(copy.deepcopy(rows))
    assert report["raw_n"] == 4
    assert report["unique_signal_days"] == 3
    assert 0 < report["effective_n"] <= report["raw_n"]
    assert report["effective_n_le_raw_n"] is True
    assert report["raw_trades_are_independent_evidence"] is False
    assert "sector" in report["concentration_dimensions_considered"]


def test_unknown_identity_values_do_not_form_one_fake_dependency_cluster() -> None:
    rows = [_candidate(0), _candidate(1)]
    for row in rows:
        row.update(
            {
                "listing_id": None,
                "issuer_id": None,
                "economic_instrument_id": None,
                "correlation_cluster": None,
            }
        )

    report = effective_n_report(rows)

    assert report["effective_n"] == 2
    assert report["non_overlapping_dependency_episodes"]["issuer_id"] == {
        "non_overlapping_episodes": 2,
        "rows_with_known_identity": 0,
    }


@pytest.mark.parametrize(
    ("raw_n", "effective_n", "minimum", "valid", "expected"),
    [
        (0, 0, 40, True, "empty"),
        (100, 20, 40, True, "underpowered"),
        (100, 40, 40, True, "sufficient"),
        (20, 21, 40, True, "invalid"),
        (100, 100, 40, False, "invalid"),
        (100, 100, 0, True, "invalid"),
    ],
)
def test_round_status_never_calls_small_c_passed_or_failed(
    raw_n: int,
    effective_n: int,
    minimum: int,
    valid: bool,
    expected: str,
) -> None:
    assert round_evidence_status(
        raw_n=raw_n,
        effective_n=effective_n,
        minimum_effective_n=minimum,
        valid=valid,
    ) == expected


def test_round_report_blocks_conclusions_when_underpowered() -> None:
    report = abc_v2_round_report([_candidate(index) for index in range(20)], minimum_effective_n=40)

    assert report["status"] == "underpowered"
    assert report["performance_conclusion_allowed"] is False
    assert report["underpowered_means_no_conclusion"] is True
    assert report["automatic_c_classification"] is False
    assert report["automatic_production_activation"] is False


def test_round_report_is_invalid_when_candidate_identity_is_duplicated() -> None:
    rows = [_candidate(0), copy.deepcopy(_candidate(0))]

    report = abc_v2_round_report(rows, minimum_effective_n=1)

    assert report["case_identity_valid"] is False
    assert report["status"] == "invalid"
    assert report["performance_conclusion_allowed"] is False


def test_sequential_stage_gate_requires_manual_predecessor_freezes() -> None:
    with pytest.raises(ValueError, match="Vorgängerstufe"):
        validate_v2_stage_request(
            "stop",
            frozen_stage_fingerprints={},
            changed_dimensions=["stop"],
        )
    with pytest.raises(ValueError, match="nicht verändern"):
        validate_v2_stage_request(
            "stop",
            frozen_stage_fingerprints={"entry": "entry-freeze-v2"},
            changed_dimensions=["stop", "exit"],
        )

    valid = validate_v2_stage_request(
        "exit_management",
        frozen_stage_fingerprints={"entry": "entry-freeze-v2", "stop": "stop-freeze-v2"},
        changed_dimensions=["management"],
    )

    assert valid["valid"] is True
    assert valid["automatic_freeze"] is False
    assert valid["automatic_production_activation"] is False


def test_full_challenger_oos_accepts_no_parameter_variants() -> None:
    freezes = {
        "entry": "entry-freeze-v2",
        "stop": "stop-freeze-v2",
        "exit_management": "exit-freeze-v2",
    }
    assert validate_v2_stage_request(
        "full_challenger_oos",
        frozen_stage_fingerprints=freezes,
        changed_dimensions=[],
    )["valid"] is True
    with pytest.raises(ValueError, match="nicht verändern"):
        validate_v2_stage_request(
            "full_challenger_oos",
            frozen_stage_fingerprints=freezes,
            changed_dimensions=["entry"],
        )


def test_multiple_testing_registration_is_pre_result_append_only_and_non_activating() -> None:
    registration = prepare_v2_hypothesis(
        family="momentum-rsi",
        question="Trennt ein vorab definierter RSI-Core robuste Ground-up-Entries?",
        stage="entry",
        changed_dimensions=["entry"],
        frozen_stage_fingerprints={},
        predeclared_parameters={"entry": {"rsi_band": [55, 65]}},
        dataset_fingerprint="future-frozen-dataset-v2",
        feature_fingerprint="future-feature-contract-v2",
        code_fingerprint="future-code-v2",
        family_attempt_ordinal=1,
    )

    assert registration["status"] == "registered_not_evaluated"
    assert registration["outcomes_seen"] is False
    assert registration["append_only_required"] is True
    assert registration["discarded_attempt_may_be_hidden"] is False
    assert registration["automatic_parameter_search"] is False
    assert registration["automatic_strategy_selection"] is False
    assert registration["automatic_production_activation"] is False


def test_hypothesis_parameters_cannot_smuggle_another_research_stage() -> None:
    with pytest.raises(ValueError, match="Research-Dimensionen"):
        prepare_v2_hypothesis(
            family="stop-calibration",
            question="Hält ein vorab definierter Strukturstop nach Entry-Freeze?",
            stage="stop",
            changed_dimensions=["stop"],
            frozen_stage_fingerprints={"entry": "entry-freeze-v2"},
            predeclared_parameters={
                "stop": {"variant": "pullback_low"},
                "entry": {"rsi_threshold": 60},
            },
            dataset_fingerprint="future-frozen-dataset-v2",
            feature_fingerprint="future-feature-contract-v2",
            code_fingerprint="future-code-v2",
            family_attempt_ordinal=1,
        )


def test_contract_keeps_abc_separate_from_unseen_gates_and_forbids_execution() -> None:
    contract = campaign_v2_methodology_contract()

    assert contract["evidence_gates"]["abc_is_internal_robustness_not_holdout"] is True
    assert contract["evidence_gates"]["sequence_after_research_freeze"] == [
        "validation",
        "manual_review",
        "holdout",
        "external",
        "true_forward",
    ]
    assert contract["automatic_c_classification"] is False
    assert contract["automatic_validation_or_holdout_open"] is False
    assert contract["automatic_production_activation"] is False
    assert contract["short_activation"] is False
    assert contract["broker_order_allowed"] is False
    assert contract["execution_allowed"] is False
