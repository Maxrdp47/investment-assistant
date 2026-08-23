from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from swing_campaign_forensic_hardening import (
    BASE_ABC_VERSION,
    BASE_CAMPAIGN_METHODOLOGY_VERSION,
    PROTECTED_V1_DATASET_FINGERPRINT,
    CampaignRetryLedger,
    CandidateFunnelLedger,
    CanonicalSetupId,
    SwingCampaignHardeningError,
    build_candidate_funnel_record,
    build_monitoring_contract,
    build_monitoring_evidence_record,
    build_retry_attempt_record,
    canonical_setup_identity,
    forensic_hypothesis_seeds,
    future_campaign_hardening_contract,
    future_setup_profile,
    future_setup_profile_matches,
    normalized_retry_reason,
    retry_log_line,
    summarize_candidate_funnel,
    summarize_monitoring_evidence,
    v1_forensic_reference_contract,
)
from swing_campaign_v2 import (
    SWING_ABC_V2_VERSION,
    SWING_CAMPAIGN_V2_METHODOLOGY_VERSION,
    abc_v2_round_report,
    campaign_v2_methodology_contract,
    round_evidence_status,
)
from swing_walk_forward import swing_walk_forward_strategy_profiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def funnel_record(
    candidate_id: str,
    stage: str,
    reason: str | None,
    *,
    setup_id: CanonicalSetupId | None = None,
) -> dict[str, object]:
    return build_candidate_funnel_record(
        campaign_version="future-campaign-v2.2-test",
        contract_id="future-contract-1",
        dataset_fingerprint="future-dataset-fingerprint",
        candidate_id=candidate_id,
        reached_stage=stage,
        terminal_reason=reason,
        recorded_at="2026-08-23T12:00:00+00:00",
        canonical_setup_id=setup_id,
    )


def retry_attempt(
    attempt_number: int,
    *,
    success: bool,
    dataset_fingerprint: str = "dataset-v2",
    result_fingerprint: str | None = None,
) -> dict[str, object]:
    return build_retry_attempt_record(
        campaign_version="future-campaign-v2.2-test",
        contract_id="contract-1",
        job_id="job-001",
        shard="2-of-8",
        attempt_number=attempt_number,
        worker_process=f"worker-{attempt_number}",
        start_time=f"2026-08-23T12:0{attempt_number}:00+00:00",
        end_time=f"2026-08-23T12:0{attempt_number}:30+00:00",
        success=success,
        exception_class=None if success else "FrozenResearchDatasetError",
        error_message=None if success else "frozen price file has divergent data",
        affected_asset=None if success else "TEST",
        dataset_fingerprint=dataset_fingerprint,
        code_contract_fingerprint="code-contract-v2",
        resume_key="resume-job-001",
        completion_id="completion-job-001",
        sample_selection_fingerprint="sample-selection-job-001",
        result_fingerprint=result_fingerprint,
    )


def test_canonical_setup_identity_is_independent_of_german_or_changed_display_name() -> None:
    german = canonical_setup_identity(CanonicalSetupId.LONG_PULLBACK_TREND)
    renamed = canonical_setup_identity(
        CanonicalSetupId.LONG_PULLBACK_TREND,
        display_name="Trendfortsetzung nach geordnetem Rücklauf",
    )
    profile = future_setup_profile(
        profile_id="future-pullback-only-v1",
        allowed_setup_ids=[CanonicalSetupId.LONG_PULLBACK_TREND],
    )

    assert german["display_name"] == "Rücksetzer im intakten Aufwärtstrend"
    assert renamed["display_name"] != german["display_name"]
    assert german["canonical_setup_id"] == renamed["canonical_setup_id"]
    assert future_setup_profile_matches(german, profile) is True
    assert future_setup_profile_matches(renamed, profile) is True


def test_pullback_only_and_breakout_only_match_exact_canonical_ids() -> None:
    pullback_profile = future_setup_profile(
        profile_id="future-pullback-only-v1",
        allowed_setup_ids=[CanonicalSetupId.LONG_PULLBACK_TREND],
    )
    breakout_profile = future_setup_profile(
        profile_id="future-breakout-only-v1",
        allowed_setup_ids=[CanonicalSetupId.LONG_BREAKOUT_CONFIRMED],
    )
    pullback = canonical_setup_identity(CanonicalSetupId.LONG_PULLBACK_TREND)
    breakout_with_pullback_text = canonical_setup_identity(
        CanonicalSetupId.LONG_BREAKOUT_CONFIRMED,
        display_name="Pullback im Anzeigenamen, fachlich weiterhin Ausbruch",
    )

    assert future_setup_profile_matches(pullback, pullback_profile) is True
    assert future_setup_profile_matches(pullback, breakout_profile) is False
    assert future_setup_profile_matches(
        breakout_with_pullback_text, pullback_profile
    ) is False
    assert future_setup_profile_matches(
        breakout_with_pullback_text, breakout_profile
    ) is True
    assert set(pullback_profile["technical_filter"]) == {"canonical_setup_ids"}
    assert pullback_profile["substring_selection_allowed"] is False


def test_missing_unknown_or_tampered_setup_identity_fails_closed() -> None:
    profile = future_setup_profile(
        profile_id="future-pullback-only-v1",
        allowed_setup_ids=[CanonicalSetupId.LONG_PULLBACK_TREND],
    )

    with pytest.raises(SwingCampaignHardeningError, match="kanonische Setup-ID"):
        future_setup_profile_matches(
            {"display_name": "Rücksetzer im intakten Aufwärtstrend"}, profile
        )
    with pytest.raises(SwingCampaignHardeningError, match="kanonische Setup-ID"):
        canonical_setup_identity("Pullback")
    tampered = deepcopy(profile)
    tampered["technical_filter"] = {"setup_type_contains": "Pullback"}
    with pytest.raises(SwingCampaignHardeningError, match="Fingerprint"):
        future_setup_profile_matches(canonical_setup_identity(CanonicalSetupId.LONG_PULLBACK_TREND), tampered)


def test_v1_reference_is_immutable_and_pullback_zero_is_not_negative_evidence() -> None:
    reference = v1_forensic_reference_contract()

    assert reference["campaign_v1"] == "IMMUTABLE_HISTORICAL_REFERENCE"
    assert reference["frozen_dataset_fingerprint"] == PROTECTED_V1_DATASET_FINGERPRINT
    assert reference["old_cases_changed"] is False
    assert reference["old_results_changed"] is False
    assert reference["long_v1_changed"] is False
    assert reference["pullback_only_v1"]["status"] == (
        "invalid_historical_profile_due_to_setup_identity_mismatch"
    )
    assert reference["pullback_only_v1"]["zero_cases_are_negative_pullback_evidence"] is False
    assert reference["breakout_and_long_v1"]["negative_evidence_retained"] is True


def test_candidate_funnel_reconciles_universe_trades_and_non_trades() -> None:
    records = [
        funnel_record("no-setup", "structural_candidate", "no_setup"),
        funnel_record(
            "missed",
            "entry_activated",
            "missed",
            setup_id=CanonicalSetupId.LONG_PULLBACK_TREND,
        ),
        funnel_record(
            "trade",
            "evaluated",
            None,
            setup_id=CanonicalSetupId.LONG_BREAKOUT_CONFIRMED,
        ),
    ]

    summary = summarize_candidate_funnel(records)

    assert summary["stage_counts"]["universe"] == 3
    assert summary["stage_counts"]["entry_executed"] == 1
    assert summary["stage_counts"]["evaluated"] == 1
    assert summary["trades"] == 1
    assert summary["non_trades"] == 2
    assert summary["universe_equals_trades_plus_non_trades"] is True
    assert summary["stage_counts_monotonic"] is True
    assert summary["terminal_reason_counts"] == {"no_setup": 1, "missed": 1}
    assert summary["status"] == "ok"


def test_candidate_funnel_requires_one_explicit_reason_and_rejects_outcomes() -> None:
    with pytest.raises(SwingCampaignHardeningError, match="terminalen Grund"):
        funnel_record("unfinished", "candidate_selected", None, setup_id=CanonicalSetupId.LONG_PULLBACK_TREND)
    with pytest.raises(SwingCampaignHardeningError, match="Unbekannter terminaler Grund"):
        funnel_record("unknown", "universe", "something_else")
    with pytest.raises(SwingCampaignHardeningError, match="Ergebnisfelder"):
        build_candidate_funnel_record(
            campaign_version="future-v2",
            contract_id="contract",
            dataset_fingerprint="dataset",
            candidate_id="outcome-leak",
            reached_stage="evaluated",
            terminal_reason=None,
            recorded_at="2026-08-23T12:00:00+00:00",
            canonical_setup_id=CanonicalSetupId.LONG_PULLBACK_TREND,
            metadata={"result_r": 2.0},
        )
    with pytest.raises(SwingCampaignHardeningError, match="metadata.diagnostics.mfe"):
        build_candidate_funnel_record(
            campaign_version="future-v2",
            contract_id="contract",
            dataset_fingerprint="dataset",
            candidate_id="nested-outcome-leak",
            reached_stage="evaluated",
            terminal_reason=None,
            recorded_at="2026-08-23T12:00:00+00:00",
            canonical_setup_id=CanonicalSetupId.LONG_PULLBACK_TREND,
            metadata={"diagnostics": {"mfe": 1.5}},
        )


def test_candidate_funnel_ledger_is_idempotent_append_only_and_divergence_safe(
    tmp_path: Path,
) -> None:
    path = tmp_path / "future-funnel.sqlite3"
    ledger = CandidateFunnelLedger(path)
    record = funnel_record("candidate-1", "universe", "insufficient_history")

    assert ledger.append(record)["inserted"] is True
    assert ledger.append(record)["existing"] is True
    divergent = funnel_record("candidate-1", "sufficient_data", "rejected_data_quality")
    with pytest.raises(SwingCampaignHardeningError, match="Divergenter"):
        ledger.append(divergent)
    assert ledger.summary()["records"] == 1
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM candidate_funnel_records")


def test_recent_incremental_only_counts_cases_new_after_previous_cutoff() -> None:
    contract = build_monitoring_contract(
        monitoring_version="monitoring-v2-week-35",
        previous_cutoff="2026-08-16",
        current_cutoff="2026-08-23",
        dataset_fingerprint="monitoring-dataset-v2",
    )
    new_case = build_monitoring_evidence_record(
        contract=contract,
        case_identity="new-case",
        signal_date="2026-08-20",
        first_eligible_at="2026-08-21",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
    )
    old_case = build_monitoring_evidence_record(
        contract=contract,
        case_identity="old-case",
        signal_date="2026-08-15",
        first_eligible_at="2026-08-16",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
    )
    seen_case = build_monitoring_evidence_record(
        contract=contract,
        case_identity="seen-case",
        signal_date="2026-08-20",
        first_eligible_at="2026-08-21",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
        previously_seen_case_identities=["seen-case"],
    )

    assert new_case["evidence_kind"] == "new_incremental_evidence"
    assert new_case["counts_as_recent_incremental"] is True
    assert old_case["evidence_kind"] == "historical_baseline"
    assert seen_case["evidence_kind"] == "historical_baseline"
    assert old_case["counts_as_recent_incremental"] is False


def test_incremental_can_have_an_older_signal_if_eligibility_is_new() -> None:
    contract = build_monitoring_contract(
        monitoring_version="monitoring-v2-week-35",
        previous_cutoff="2026-08-16",
        current_cutoff="2026-08-23",
        dataset_fingerprint="monitoring-dataset-v2",
    )

    record = build_monitoring_evidence_record(
        contract=contract,
        case_identity="newly-labeled-case",
        signal_date="2026-08-10",
        first_eligible_at="2026-08-20",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
    )

    assert record["evidence_kind"] == "new_incremental_evidence"
    assert record["inclusion_reason"] == "first_became_eligible_after_previous_cutoff"


def test_first_seen_before_cutoff_and_backfill_cannot_masquerade_as_new_evidence() -> None:
    contract = build_monitoring_contract(
        monitoring_version="monitoring-v2-week-35",
        previous_cutoff="2026-08-16",
        current_cutoff="2026-08-23",
        dataset_fingerprint="monitoring-dataset-v2",
    )
    already_seen = build_monitoring_evidence_record(
        contract=contract,
        case_identity="already-seen",
        signal_date="2026-08-10",
        first_eligible_at="2026-08-20",
        first_seen_in_monitoring="2026-08-15T10:00:00+00:00",
    )

    assert already_seen["evidence_kind"] == "historical_baseline"
    assert already_seen["counts_as_recent_incremental"] is False
    with pytest.raises(SwingCampaignHardeningError, match="Backfill"):
        build_monitoring_evidence_record(
            contract=contract,
            case_identity="impossible-forward",
            signal_date="2026-08-20",
            first_eligible_at="2026-08-21",
            first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
            historical_backfill=True,
            true_forward=True,
        )


def test_initial_baseline_backfill_and_true_forward_remain_separate() -> None:
    initial_contract = build_monitoring_contract(
        monitoring_version="monitoring-v2-initial",
        previous_cutoff=None,
        current_cutoff="2026-08-23",
        dataset_fingerprint="monitoring-dataset-v2",
    )
    recurring_contract = build_monitoring_contract(
        monitoring_version="monitoring-v2-week-35",
        previous_cutoff="2026-08-16",
        current_cutoff="2026-08-23",
        dataset_fingerprint="monitoring-dataset-v2",
    )
    baseline = build_monitoring_evidence_record(
        contract=initial_contract,
        case_identity="initial",
        signal_date="2025-01-02",
        first_eligible_at="2025-02-01",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
    )
    backfill = build_monitoring_evidence_record(
        contract=recurring_contract,
        case_identity="backfill",
        signal_date="2020-01-02",
        first_eligible_at="2020-02-01",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
        historical_backfill=True,
    )
    forward = build_monitoring_evidence_record(
        contract=recurring_contract,
        case_identity="forward",
        signal_date="2026-08-20",
        first_eligible_at="2026-08-21",
        first_seen_in_monitoring="2026-08-23T10:00:00+00:00",
        true_forward=True,
    )

    summary = summarize_monitoring_evidence([baseline, backfill, forward])

    assert baseline["evidence_kind"] == "initial_monitoring_baseline"
    assert backfill["evidence_kind"] == "historical_backfill"
    assert forward["evidence_kind"] == "true_forward"
    assert summary["historical_baseline"] == 1
    assert summary["new_incremental_evidence"] == 0
    assert summary["historical_backfill"] == 1
    assert summary["true_forward"] == 1
    assert summary["backfill_counted_as_incremental"] is False


def test_retry_log_and_ledger_prove_stable_identity_without_double_counting(
    tmp_path: Path,
) -> None:
    path = tmp_path / "retry.sqlite3"
    ledger = CampaignRetryLedger(path)
    failed = retry_attempt(1, success=False)
    succeeded = retry_attempt(2, success=True, result_fingerprint="result-v1")

    assert failed["normalized_error_reason"] == "frozen_dataset_divergent_data"
    assert ledger.append(failed)["inserted"] is True
    assert ledger.append(failed)["existing"] is True
    assert ledger.append(succeeded)["completion_inserted"] is True
    report = ledger.integrity_report("job-001")
    log = json.loads(
        retry_log_line(
            failed,
            event="attempt_failed",
            traceback_log_reference="campaign.log#job-001-attempt-1",
        )
    )

    assert report["attempts"] == 2
    assert report["failures"] == 1
    assert report["successes"] == 1
    assert report["completion_rows"] == 1
    assert report["identical_completion_id"] is True
    assert report["sample_selection_unchanged"] is True
    assert report["dataset_unchanged"] is True
    assert report["no_double_counting"] is True
    assert report["result_change_through_retry"] is False
    assert report["status"] == "ok"
    assert log["job_id"] == "job-001"
    assert log["attempt_number"] == 1
    assert log["normalized_error_reason"] == "frozen_dataset_divergent_data"
    assert "traceback" not in failed
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM campaign_attempts")


def test_retry_cannot_change_dataset_sample_or_skip_attempt_number(tmp_path: Path) -> None:
    ledger = CampaignRetryLedger(tmp_path / "retry-safety.sqlite3")
    ledger.append(retry_attempt(1, success=False))

    with pytest.raises(SwingCampaignHardeningError, match="Dataset oder Sample"):
        ledger.append(
            retry_attempt(
                2,
                success=True,
                dataset_fingerprint="different-dataset",
                result_fingerprint="result-v1",
            )
        )
    with pytest.raises(SwingCampaignHardeningError, match="lückenlos"):
        ledger.append(retry_attempt(3, success=True, result_fingerprint="result-v1"))


def test_forensic_patterns_are_neutral_hypothesis_seeds_only() -> None:
    seeds = forensic_hypothesis_seeds()
    joined = " ".join(str(seed["claim"]) for seed in seeds).casefold()

    assert len(seeds) == 5
    assert {seed["source"] for seed in seeds} == {"campaign_v1_forensic_postmortem"}
    assert {seed["status"] for seed in seeds} == {"hypothesis_seed_only"}
    assert all(seed["available_after_current_broad_pass"] is True for seed in seeds)
    assert all(seed["automatic_strategy_change"] is False for seed in seeds)
    assert all(seed["automatic_activation"] is False for seed in seeds)
    assert "68" not in joined
    assert "1.5" not in joined
    assert ">=" not in joined


def test_existing_abc_v2_1_and_underpowered_gate_remain_unchanged() -> None:
    methodology = campaign_v2_methodology_contract()
    report = abc_v2_round_report([], minimum_effective_n=200)
    underpowered = round_evidence_status(
        raw_n=100,
        effective_n=100,
        minimum_effective_n=200,
    )

    assert SWING_CAMPAIGN_V2_METHODOLOGY_VERSION == BASE_CAMPAIGN_METHODOLOGY_VERSION
    assert SWING_ABC_V2_VERSION == BASE_ABC_VERSION
    assert methodology["version"] == BASE_CAMPAIGN_METHODOLOGY_VERSION
    assert methodology["abc"]["all_pools_reserved_before_first_result"] is True
    assert methodology["abc"]["selection_may_use_outcomes"] is False
    assert methodology["evidence_gates"]["abc_is_internal_robustness_not_holdout"] is True
    assert report["status"] == "empty"
    assert underpowered == "underpowered"
    assert report["performance_conclusion_allowed"] is False
    assert report["automatic_c_classification"] is False


def test_hardening_layers_on_v2_1_without_changing_broad_or_long_v1() -> None:
    contract = future_campaign_hardening_contract()
    current = next(iter(swing_walk_forward_strategy_profiles(("current",)).values()))
    old_pullback = next(
        iter(swing_walk_forward_strategy_profiles(("long_v1_pullback_only",)).values())
    )

    assert contract["base_methodology_version"] == BASE_CAMPAIGN_METHODOLOGY_VERSION
    assert contract["base_abc_version"] == BASE_ABC_VERSION
    assert contract["abc_v2_1_rebuilt"] is False
    assert contract["abc_v2_1_changed"] is False
    assert set(contract["canonical_setup_consumers"]) == {
        "research",
        "scanner",
        "campaign",
        "strategy_freeze",
        "reporting",
    }
    assert set(contract["canonical_setup_consumers"].values()) == {
        "canonical_setup_id"
    }
    assert contract["localized_setup_text_is_presentation_only"] is True
    assert contract["substring_setup_selection_allowed"] is False
    assert contract["abc_replaces_development_validation_holdout"] is False
    assert contract["positive_c_opens_production"] is False
    assert contract["sample_size_policy"]["underpowered_may_pass"] is False
    assert contract["sample_size_policy"]["fixed_technical_threshold_is_scientific_truth"] is False
    assert not any(contract["current_broad_pass"].values())
    assert contract["long_v1_retuned"] is False
    assert current["thresholds_snapshot"]["min_crv"] == 2.0
    assert current["technical_filter"] == {}
    assert old_pullback["technical_filter"] == {"setup_type_contains": "Pullback"}


def test_protected_frozen_manifest_keeps_exact_v1_fingerprint() -> None:
    manifest_path = (
        PROJECT_ROOT
        / "runtime"
        / "swing_walk_forward_datasets"
        / "f7109e21474a027892eb01ed"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "finalized"
    assert manifest["dataset_fingerprint"] == PROTECTED_V1_DATASET_FINGERPRINT
    assert manifest["dataset_revision"] == PROTECTED_V1_DATASET_FINGERPRINT
    assert manifest["provider_policy"]["automatic_revision"] is False
    assert manifest["provider_policy"]["provider_access_after_finalize"] is False
