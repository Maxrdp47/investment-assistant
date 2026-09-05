from __future__ import annotations

import json
import sqlite3
import zlib
from pathlib import Path

import pytest

from multi_asset_development_v6_audit import verify_self_fingerprinted_artifact
from multi_asset_development_v6_reporting import (
    DevelopmentV6ReportingError,
    build_v6_completion_summary,
    build_v6_descriptive_report,
    freeze_v6_descriptive_plan,
)
from multi_asset_discovery_v1 import canonical_json, fingerprint
from swing_research_identity_v3 import dependency_episode_report_v3


RUN_ID = "madv6-report-test"
CONTRACT_BASIS_FINGERPRINT = "benchmark-prefreeze-contract-fp"


def _seal(payload: dict[str, object]) -> dict[str, object]:
    payload["artifact_fingerprint"] = fingerprint(payload)
    return payload


def _audit(*, status: str = "PASS", pair_count: int = 2) -> dict[str, object]:
    return _seal(
        {
            "version": "audit-v1",
            "status": status,
            "created_at": "2026-09-05T20:00:00+00:00",
            "run_id": RUN_ID,
            "run": {
                "run_id": RUN_ID,
                "status": "COMPLETED",
                "contract_fingerprint": "contract-fp",
                "combined_input_fingerprint": "input-fp",
                "started_at": "2026-09-05T18:00:00+00:00",
            },
            "counts": {
                "audited_payload_pairs": pair_count,
                "feature_rows": pair_count,
                "outcome_rows": pair_count,
            },
        }
    )


def _contract(plan: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": "development-v6",
        "reference_fingerprints": {
            "combined_input_fingerprint": "input-fp",
            "descriptive_plan_artifact_fingerprint": plan["artifact_fingerprint"],
        },
    }
    payload["contract_fingerprint"] = fingerprint(payload)
    return payload


def _feature(case_id: str, *, asset_class: str, regime: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "symbol": "AAA" if case_id == "case-1" else "BBB",
        "listing_id": f"listing-{case_id}",
        "issuer_id": None,
        "mapping_status": "UNRESOLVED",
        "signal_day": "2020-03-02" if case_id == "case-1" else "2021-04-05",
        "asset_class": asset_class,
        "dependency_status": "UNKNOWN",
        "market_regime": regime,
        "features": {
            "rsi_14": {"status": "AVAILABLE", "value": 52.0},
            "event_context": {
                "status": "UNKNOWN",
                "reason": "NO_PIT_EVENT_FACT_AVAILABLE",
            },
        },
        "safe_zones": {
            "A": {"status": "AVAILABLE", "lower": 98.0},
            "B": {"status": "UNAVAILABLE", "reason": "NO_STRUCTURE"},
            "C": {"status": "AVAILABLE", "lower": 97.0},
        },
        "sell_zones": {
            "A": {"status": "AVAILABLE", "value": 105.0},
            "B": {"status": "UNAVAILABLE", "reason": "NO_STRUCTURE"},
            "C": {"status": "AVAILABLE", "value": 106.0},
        },
    }


def _outcome(case_id: str, *, r_available: bool) -> dict[str, object]:
    return {
        "case_id": case_id,
        "entry_day": "2020-03-03" if r_available else "2021-04-06",
        "outcome_end_day": "2020-04-03" if r_available else "2021-04-20",
        "observations_available": 22 if r_available else 10,
        "status": "COMPLETE" if r_available else "CENSORED_AT_INPUT_GAP",
        "censoring_reason": None if r_available else "INPUT_GAP_BEFORE_REQUESTED_OBSERVATIONS",
        "measurement_status": "COMPLETE" if r_available else "PARTIAL_NON_R",
        "r_metrics_status": "AVAILABLE" if r_available else "UNAVAILABLE",
        "r_metrics_reason": None if r_available else "NON_POSITIVE_STRUCTURAL_RISK",
        "atr_metrics_status": "AVAILABLE" if r_available else "UNAVAILABLE",
        "atr_metrics_reason": None if r_available else "MISSING_ATR",
        "mfe_pct": 4.0 if r_available else 1.0,
        "mae_pct": -2.0 if r_available else -3.0,
        "mfe_atr": 2.0 if r_available else None,
        "mae_atr": -1.0 if r_available else None,
        "mfe_r": 1.5 if r_available else None,
        "mae_r": -0.75 if r_available else None,
        "final_return_pct": 1.25 if r_available else -0.5,
        "entry_gap_pct": 0.4 if r_available else -0.2,
        "entry_gap_atr": 0.2 if r_available else None,
        "time_to_mfe_observations": 12 if r_available else 4,
        "time_to_structural_intraday_invalidation": 8 if r_available else None,
        "time_to_structural_close_invalidation": None,
        "observation_axis": {
            "observed_bar_count": 22 if r_available else 10,
            "calendar_span_days_inclusive": 32 if r_available else 15,
            "declared_data_gap_boundary_encountered": not r_available,
            "data_gaps_crossed": 0,
        },
        "protective_ratchet": (
            {
                "status": "AVAILABLE",
                "initial_lower": 98.0,
                "final_lower": 101.0,
                "updates": [
                    {
                        "effective_day": "2020-03-20",
                        "prior_lower": 98.0,
                        "new_lower": 101.0,
                    }
                ],
                "never_lowered": True,
            }
            if r_available
            else {
                "status": "UNAVAILABLE",
                "reason": "SAFE_ZONE_C_UNAVAILABLE",
                "updates": [],
                "never_lowered": True,
            }
        ),
        "path_quality": {
            "mfe_to_mae_ratio": 2.0 if r_available else 0.5,
            "positive_close_fraction": 0.75 if r_available else 0.2,
            "peak_giveback_pct": 1.1 if r_available else 0.4,
            "final_giveback_pct": 2.2 if r_available else 1.5,
            "peak_giveback_r": 0.4 if r_available else None,
            "final_giveback_r": 0.8 if r_available else None,
        },
        "deterioration": {
            "PRICE_STRUCTURE": {
                "status": "AVAILABLE",
                "close_below_signal_ema20_count": 3 if r_available else 7,
            },
            "MOMENTUM": {
                "status": "AVAILABLE",
                "rsi14_below_40_count": 2 if r_available else 5,
            },
            "VOLATILITY": (
                {
                    "status": "AVAILABLE",
                    "atr14_above_1_5x_signal_count": 1,
                }
                if r_available
                else {"status": "UNAVAILABLE", "reason": "MISSING_ATR"}
            ),
            "LIQUIDITY": {
                "status": "AVAILABLE",
                "volume_ratio_below_0_5_count": 4,
            },
            "EVENT": {
                "status": "UNKNOWN",
                "reason": "NO_PIT_EVENT_PATH_IN_TECHNICAL_DEVELOPMENT",
            },
        },
        "checkpoints": {
            "20": (
                {
                    "return_pct": 1.0,
                    "mfe_pct": 3.0,
                    "mae_pct": -1.0,
                    "mfe_atr": 1.5,
                    "mae_atr": -0.5,
                    "mfe_r": 1.0,
                    "mae_r": -0.3,
                }
                if r_available
                else None
            ),
            "60": None,
            "120": None,
            "252": None,
        },
        "r_level_hits": {
            "1.0": 12 if r_available else None,
            "2.0": None,
            "3.0": None,
        },
        "safe_zone_breaches": {
            "A": {
                "status": "AVAILABLE",
                "intraday_breach_observation": 8 if r_available else None,
                "close_breach_observation": None,
            },
            "B": {"status": "UNAVAILABLE", "reason": "NO_STRUCTURE"},
            "C": {
                "status": "AVAILABLE",
                "intraday_breach_observation": None,
                "close_breach_observation": None,
            },
        },
        "sell_zone_measurements": {
            "A": {
                "status": "AVAILABLE",
                "hit_observation": 10 if r_available else None,
                "max_overshoot_pct": 1.0 if r_available else 0.0,
            },
            "B": {"status": "UNAVAILABLE", "reason": "NO_STRUCTURE"},
            "C": {
                "status": "AVAILABLE",
                "hit_observation": None,
                "max_overshoot_pct": 0.0,
            },
        },
    }


def _write_stores(
    root: Path,
    *,
    features: list[dict[str, object]],
    outcomes: list[dict[str, object]],
) -> tuple[Path, Path]:
    feature_path = root / "features.sqlite3"
    outcome_path = root / "outcomes.sqlite3"
    with sqlite3.connect(feature_path) as connection:
        connection.execute(
            "CREATE TABLE feature_rows(case_id TEXT PRIMARY KEY,run_id TEXT,payload_zlib BLOB)"
        )
        for feature in features:
            connection.execute(
                "INSERT INTO feature_rows VALUES (?,?,?)",
                (
                    feature["case_id"],
                    RUN_ID,
                    zlib.compress(canonical_json(feature).encode("utf-8")),
                ),
            )
    with sqlite3.connect(outcome_path) as connection:
        connection.execute(
            "CREATE TABLE outcome_rows(case_id TEXT PRIMARY KEY,run_id TEXT,payload_zlib BLOB)"
        )
        for outcome in outcomes:
            connection.execute(
                "INSERT INTO outcome_rows VALUES (?,?,?)",
                (
                    outcome["case_id"],
                    RUN_ID,
                    zlib.compress(canonical_json(outcome).encode("utf-8")),
                ),
            )
    return feature_path, outcome_path


def _stores(root: Path) -> tuple[Path, Path]:
    return _write_stores(
        root,
        features=[
            _feature("case-1", asset_class="EQUITIES", regime="UPTREND"),
            _feature("case-2", asset_class="CRYPTO", regime="MIXED"),
        ],
        outcomes=[
            _outcome("case-1", r_available=True),
            _outcome("case-2", r_available=False),
        ],
    )


def _plan(root: Path) -> dict[str, object]:
    return freeze_v6_descriptive_plan(
        contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        combined_input_fingerprint="input-fp",
        created_at="2026-09-05T17:00:00+00:00",
        artifact_path=root / "plan.json",
    )


def test_frozen_plan_is_self_fingerprinted_and_idempotent(tmp_path: Path) -> None:
    first = _plan(tmp_path)
    second = freeze_v6_descriptive_plan(
        contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        combined_input_fingerprint="input-fp",
        created_at="2026-09-05T17:00:00+00:00",
        artifact_path=tmp_path / "plan.json",
    )
    assert first == second
    assert first["status"] == "FROZEN"
    assert verify_self_fingerprinted_artifact(first)
    assert first["selection_or_optimization_allowed"] is False
    assert "final_return_pct" in first["path_metrics"]
    assert first["metric_semantics"]["final_return_pct"].endswith(
        "NOT_AN_EXIT_OR_REALIZED_RETURN"
    )
    assert first["dependency_evidence"][
        "unknown_dependency_contribution_to_effective_n"
    ] == 0
    assert first["outcome_completeness_separation"] == {
        "dimensions": ["OUTCOME_STATUS", "CENSORING_REASON"],
        "grouping": "ONE_DIMENSION_AT_A_TIME_NO_COMBINATORIAL_SEARCH",
        "not_censored_label": "NOT_CENSORED",
        "partition_counts_reported": True,
        "metric_defined_n_reported_per_partition": True,
        "pooled_metrics_are_all_case_coverage_descriptions_only": True,
        "complete_horizon_interpretation_requires_outcome_status_partition": True,
    }


def test_descriptive_report_streams_only_defined_metrics_and_fixed_groups(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path = _stores(tmp_path)
    plan = _plan(tmp_path)
    contract = _contract(plan)
    audit = _audit()
    audit["run"]["contract_fingerprint"] = contract["contract_fingerprint"]
    audit.pop("artifact_fingerprint")
    _seal(audit)
    report = build_v6_descriptive_report(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        audit=audit,
        frozen_plan=plan,
        final_contract=contract,
        expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        created_at="2026-09-05T21:00:00+00:00",
        artifact_path=tmp_path / "report.json",
    )
    assert report["status"] == "DESCRIPTIVE_COMPLETE"
    assert report["population"]["n"] == 2
    overall = report["overall"]
    assert overall["path_measurements"]["mfe_pct"]["defined_n"] == 2
    assert overall["path_measurements"]["mfe_r"]["defined_n"] == 1
    assert overall["path_measurements"]["mfe_r"]["unavailable_n"] == 1
    assert overall["path_measurements"]["final_return_pct"]["defined_n"] == 2
    assert overall["path_measurements"]["entry_gap_atr"]["defined_n"] == 1
    assert overall["path_measurements"][
        "time_to_structural_intraday_invalidation"
    ]["defined_n"] == 1
    assert overall["path_quality"]["positive_close_fraction"]["defined_n"] == 2
    assert overall["protective_ratchet"]["status_counts"] == {
        "AVAILABLE": 1,
        "UNAVAILABLE": 1,
    }
    assert overall["protective_ratchet"]["measurements"]["update_count"][
        "defined_n"
    ] == 1
    assert overall["deterioration"]["PRICE_STRUCTURE"]["measurements"][
        "close_below_signal_ema20_count"
    ]["defined_n"] == 2
    assert overall["deterioration"]["VOLATILITY"]["status_counts"] == {
        "AVAILABLE": 1,
        "UNAVAILABLE": 1,
    }
    assert overall["checkpoints"]["20"]["available_n"] == 1
    assert overall["fixed_r_level_observations"]["1.0"]["hit_n"] == 1
    assert overall["safe_zones"]["A"]["intraday_breach_n"] == 1
    assert set(report["groups"]["ASSET_CLASS"]) == {"CRYPTO", "EQUITIES"}
    assert report["groups"]["VOLATILITY_REGIME_IF_PRESENT"]["NOT_PRESENT"]["n"] == 2
    complete = report["groups"]["OUTCOME_STATUS"]["COMPLETE"]
    censored = report["groups"]["OUTCOME_STATUS"]["CENSORED_AT_INPUT_GAP"]
    assert complete["n"] == 1
    assert complete["path_measurements"]["mfe_pct"] == {
        "defined_n": 1,
        "unavailable_n": 0,
        "mean": 4.0,
        "stddev": 0.0,
        "min": 4.0,
        "max": 4.0,
    }
    assert censored["n"] == 1
    assert censored["path_measurements"]["mfe_pct"]["defined_n"] == 1
    assert censored["path_measurements"]["mfe_pct"]["mean"] == 1.0
    assert report["groups"]["CENSORING_REASON"]["NOT_CENSORED"]["n"] == 1
    input_gap = report["groups"]["CENSORING_REASON"][
        "INPUT_GAP_BEFORE_REQUESTED_OBSERVATIONS"
    ]
    assert input_gap["n"] == 1
    assert input_gap["path_measurements"]["mfe_r"]["defined_n"] == 0
    assert input_gap["path_measurements"]["mfe_r"]["unavailable_n"] == 1
    assert report["outcome_completeness_separation"]["partition_location"] == (
        "groups"
    )
    assert report["dependency_evidence"]["raw_listings"] == 2
    assert report["dependency_evidence"]["effective_n_known_issuers_only"] == 0
    assert report["dependency_evidence"][
        "unknown_dependency_contribution_to_effective_n"
    ] == 0
    assert report["temporal_coverage"]["signal_days"]["distinct_n"] == 2
    assert report["temporal_coverage"]["recorded_observation_boundary_days"][
        "distinct_n"
    ] == 4
    assert report["temporal_coverage"]["full_distinct_observed_session_days"][
        "value"
    ] is None
    assert report["interpretation_limits"]["no_selection_or_optimization"] is True
    assert report["interpretation_limits"][
        "final_return_pct_is_not_an_exit_or_realized_return"
    ] is True
    assert report["interpretation_limits"][
        "complete_and_censored_outcomes_have_separate_fixed_partitions"
    ] is True
    assert report["interpretation_limits"][
        "pooled_means_are_not_complete_horizon_estimates"
    ] is True
    assert verify_self_fingerprinted_artifact(report)


def test_dependency_evidence_matches_frozen_v3_episode_semantics(
    tmp_path: Path,
) -> None:
    windows = [
        ("issuer-1", "listing-1", "2020-01-01", "2020-01-10", "VERIFIED", "KNOWN"),
        ("issuer-1", "listing-1", "2020-01-05", "2020-01-08", "VERIFIED", "KNOWN"),
        ("issuer-1", "listing-2", "2020-01-11", "2020-01-20", "VERIFIED", "KNOWN"),
        ("issuer-2", "listing-3", "2020-01-02", "2020-01-02", "VERIFIED", "KNOWN"),
        (None, "listing-4", "2020-01-03", "2020-01-04", "UNRESOLVED", "UNKNOWN"),
    ]
    features: list[dict[str, object]] = []
    outcomes: list[dict[str, object]] = []
    expected_cases: list[dict[str, object]] = []
    for index, (
        issuer_id,
        listing_id,
        signal_day,
        outcome_end_day,
        mapping_status,
        dependency_status,
    ) in enumerate(windows, start=1):
        case_id = f"dependency-case-{index}"
        feature = _feature(case_id, asset_class="EQUITIES", regime="UPTREND")
        feature.update(
            {
                "signal_day": signal_day,
                "listing_id": listing_id,
                "issuer_id": issuer_id,
                "mapping_status": mapping_status,
                "dependency_status": dependency_status,
            }
        )
        outcome = _outcome(case_id, r_available=True)
        outcome.update(
            {
                "entry_day": signal_day,
                "outcome_end_day": outcome_end_day,
            }
        )
        features.append(feature)
        outcomes.append(outcome)
        expected_cases.append(
            {
                "listing_id": listing_id,
                "issuer_id": issuer_id,
                "mapping_status": mapping_status,
                "dependency_status": dependency_status,
                "signal_day": signal_day,
                "label_end_day": outcome_end_day,
            }
        )

    feature_path, outcome_path = _write_stores(
        tmp_path, features=features, outcomes=outcomes
    )
    plan = _plan(tmp_path)
    contract = _contract(plan)
    audit = _audit(pair_count=len(windows))
    audit["run"]["contract_fingerprint"] = contract["contract_fingerprint"]
    audit.pop("artifact_fingerprint")
    _seal(audit)
    report = build_v6_descriptive_report(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        audit=audit,
        frozen_plan=plan,
        final_contract=contract,
        expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        created_at="2026-09-05T21:00:00+00:00",
        artifact_path=tmp_path / "report.json",
    )

    assert report["dependency_evidence"] == dependency_episode_report_v3(
        expected_cases
    )
    assert report["dependency_evidence"]["effective_n_known_issuers_only"] == 3
    assert report["dependency_evidence"]["dependency_unknown_n"] == 1
    assert report["dependency_evidence"][
        "unknown_dependency_contribution_to_effective_n"
    ] == 0


def test_descriptive_report_refuses_failed_audit(tmp_path: Path) -> None:
    feature_path, outcome_path = _stores(tmp_path)
    with pytest.raises(DevelopmentV6ReportingError, match="audit status PASS"):
        build_v6_descriptive_report(
            run_id=RUN_ID,
            feature_path=feature_path,
            outcome_path=outcome_path,
            audit=_audit(status="FAIL"),
            frozen_plan=(plan := _plan(tmp_path)),
            final_contract=_contract(plan),
            expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
            created_at="2026-09-05T21:00:00+00:00",
            artifact_path=tmp_path / "report.json",
        )
    assert not (tmp_path / "report.json").exists()


def test_descriptive_report_refuses_unclassified_skipped_work_units(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path = _stores(tmp_path)
    plan = _plan(tmp_path)
    contract = _contract(plan)
    audit = _audit()
    audit["run"]["contract_fingerprint"] = contract["contract_fingerprint"]
    audit["work_unit_status_counts"] = {"COMPLETED": 1, "SKIPPED": 1}
    audit.pop("artifact_fingerprint")
    _seal(audit)

    with pytest.raises(
        DevelopmentV6ReportingError,
        match="complete reconciled skip classification",
    ):
        build_v6_descriptive_report(
            run_id=RUN_ID,
            feature_path=feature_path,
            outcome_path=outcome_path,
            audit=audit,
            frozen_plan=plan,
            final_contract=contract,
            expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
            created_at="2026-09-05T21:00:00+00:00",
            artifact_path=tmp_path / "report.json",
        )
    assert not (tmp_path / "report.json").exists()


def test_completion_summary_links_only_passed_artifacts_and_leaves_later_stages_closed(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path = _stores(tmp_path)
    plan = _plan(tmp_path)
    contract = _contract(plan)
    audit = _audit()
    audit["run"]["contract_fingerprint"] = contract["contract_fingerprint"]
    audit.pop("artifact_fingerprint")
    _seal(audit)
    report = build_v6_descriptive_report(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        audit=audit,
        frozen_plan=plan,
        final_contract=contract,
        expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        created_at="2026-09-05T21:00:00+00:00",
        artifact_path=tmp_path / "report.json",
    )
    summary = build_v6_completion_summary(
        audit=audit,
        frozen_plan=plan,
        descriptive_report=report,
        created_at="2026-09-05T21:05:00+00:00",
        artifact_path=tmp_path / "summary.json",
    )
    assert summary["status"] == "COMPLETED_AUDITED_AWAITING_REVIEW"
    assert summary["human_review_required_before_any_next_research_stage"] is True
    assert summary["opened_stages"]["development"] is True
    assert all(
        value is False
        for key, value in summary["opened_stages"].items()
        if key != "development"
    )
    assert summary["automatic_strategy_or_rule_change"] is False
    assert verify_self_fingerprinted_artifact(summary)

    # A crash after an immutable write but before the chain-state transition
    # must resume without rebuilding or changing terminal timestamps.
    report_again = build_v6_descriptive_report(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        audit=audit,
        frozen_plan=plan,
        final_contract=contract,
        expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        created_at="2026-09-05T22:00:00+00:00",
        artifact_path=tmp_path / "report.json",
    )
    summary_again = build_v6_completion_summary(
        audit=audit,
        frozen_plan=plan,
        descriptive_report=report_again,
        created_at="2026-09-05T22:05:00+00:00",
        artifact_path=tmp_path / "summary.json",
    )
    assert report_again == report
    assert summary_again == summary


def test_completion_summary_contains_copyable_technical_project_snapshot(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path = _stores(tmp_path)
    plan = _plan(tmp_path)
    input_precheck = _seal(
        {
            "version": "input-v6",
            "status": "PASS",
            "period": ["2010-01-01", "2025-12-31"],
            "contract_inputs": {
                "source_dataset_fingerprint": "dataset-fp",
                "combined_input_fingerprint": "input-fp",
                "equity_etf_projection_fingerprint": "eq-fp",
                "crypto_projection_fingerprint": "crypto-fp",
                "fx_projection_fingerprint": "fx-fp",
                "equity_etf_store_sha256": "eq-sha",
                "crypto_store_sha256": "crypto-sha",
                "fx_store_sha256": "fx-sha",
                "source_dataset_manifest_sha256": "manifest-sha",
                "identity_store_sha256": "identity-sha",
                "implementation_fingerprint": "code-fp",
            },
            "coverage": {
                "asset_count": 4,
                "active_asset_count": 3,
                "no_data_asset_count": 1,
                "active_bar_count": 1000,
                "by_asset_class": {
                    "EQUITIES_ETF": {
                        "coverage_assets": 2,
                        "active_assets": 2,
                        "no_data_assets": 0,
                        "active_rows": 800,
                    },
                    "CRYPTO": {
                        "coverage_assets": 1,
                        "active_assets": 1,
                        "no_data_assets": 0,
                        "active_rows": 180,
                    },
                    "FX": {
                        "coverage_assets": 1,
                        "active_assets": 0,
                        "no_data_assets": 1,
                        "active_rows": 20,
                    },
                },
            },
            "gap_policy": {"version": "gap-v1"},
            "gap_boundary_provenance": {
                "equity_etf_archived_invalid_sessions": 2,
                "crypto_archived_invalid_sessions": 3,
                "fx_archived_invalid_sessions": 1,
            },
        }
    )
    benchmark = _seal(
        {
            "version": "benchmark-v6",
            "status": "PASS",
            "selected_worker_count": 4,
            "sqlite_writer_count": 1,
            "deterministic_payloads_equal": True,
            "selection_rule": "stable-fastest",
            "resources": {"logical_cpu_count": 12},
            "configurations": [
                {
                    "worker_count": 4,
                    "status": "PASS",
                    "wall_seconds": 12.5,
                    "throughput_cases_per_second": 123.4,
                    "peak_ram_upper_bound_bytes": 456789,
                    "scientific_digest": "digest-fp",
                    "sqlite_writer_count": 1,
                }
            ],
        }
    )
    contract: dict[str, object] = {
        "contract_version": "development-v6",
        "reference_fingerprints": {
            "combined_input_fingerprint": "input-fp",
            "descriptive_plan_artifact_fingerprint": plan["artifact_fingerprint"],
            "input_precheck_artifact_fingerprint": input_precheck[
                "artifact_fingerprint"
            ],
            "worker_benchmark_artifact_fingerprint": benchmark[
                "artifact_fingerprint"
            ],
            "development_code_fingerprint": "code-fp",
        },
        "development_execution": {"research_epoch": "epoch-v6"},
        "store_contract": {"schema_version": "store-v6"},
    }
    contract["contract_fingerprint"] = fingerprint(contract)
    audit = _audit()
    audit["run"].update(
        {
            "contract_fingerprint": contract["contract_fingerprint"],
            "universe_fingerprint": "universe-fp",
            "work_plan_fingerprint": "work-plan-fp",
            "code_commit": "abc123",
            "completed_at": "2026-09-05T20:00:00+00:00",
            "last_checkpoint_at": "2026-09-05T20:00:00+00:00",
        }
    )
    audit["work_unit_status_counts"] = {"COMPLETED": 1, "SKIPPED": 1}
    audit["work_unit_classification_counts"] = {
        "COMPLETED_RECONCILED": 1,
        "SKIPPED_WITH_EMPTY_RECEIPT": 1,
    }
    audit["skipped_work_unit_exclusions"] = {
        "classification_source": "unit_receipts.summary_json.skip_reason_code",
        "control_reconciliation": (
            "work_units.last_error_class_and_last_error_message_exact_match"
        ),
        "allowed_reason_codes": [
            "EXPECTED_NO_DEVELOPMENT_DATA",
            "NO_GAP_SAFE_220_OBSERVATION_HISTORY",
        ],
        "total_skipped_work_units": 1,
        "classified_skipped_work_units": 1,
        "all_skipped_units_reconciled": True,
        "by_reason_code": {
            "EXPECTED_NO_DEVELOPMENT_DATA": {
                "work_units": 1,
                "by_asset_class": {"CRYPTO": 1},
            },
            "NO_GAP_SAFE_220_OBSERVATION_HISTORY": {
                "work_units": 0,
                "by_asset_class": {},
            },
        },
        "free_text_reinterpreted_as_reason_code": False,
    }
    audit["gates"] = {"run_completed": True}
    audit["digests"] = {"verified_payload_pair_stream_sha256": "payload-digest"}
    audit["issue_count"] = 0
    audit.pop("artifact_fingerprint")
    _seal(audit)
    report = build_v6_descriptive_report(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        audit=audit,
        frozen_plan=plan,
        final_contract=contract,
        expected_contract_basis_fingerprint=CONTRACT_BASIS_FINGERPRINT,
        created_at="2026-09-05T21:00:00+00:00",
        artifact_path=tmp_path / "report.json",
    )
    manifest: dict[str, object] = {
        "run_id": RUN_ID,
        "development_contract_fingerprint": contract["contract_fingerprint"],
        "universe_fingerprint": "universe-fp",
        "work_plan_fingerprint": "work-plan-fp",
        "commit": "abc123",
        "runner_version": "runner-v6",
    }
    manifest["run_manifest_fingerprint"] = fingerprint(manifest)
    runtime = {
        "run_id": RUN_ID,
        "status": "COMPLETED",
        "total_planned_work_units": 2,
        "completed": 1,
        "skipped": 1,
        "failed": 0,
        "pending": 0,
        "active": 0,
        "receipts": 2,
        "r_na_cases": 1,
        "censored_cases": 1,
        "missing_reference_entry": 0,
        "missingness_exclusions": 1,
        "started_at": "2026-09-05T18:00:00+00:00",
        "completed_at": "2026-09-05T20:00:00+00:00",
        "last_checkpoint_at": "2026-09-05T20:00:00+00:00",
        "last_completed_work_unit": "unit-2",
        "last_work_unit_completed_at": "2026-09-05T19:59:59+00:00",
    }
    summary = build_v6_completion_summary(
        audit=audit,
        frozen_plan=plan,
        descriptive_report=report,
        final_contract=contract,
        run_manifest=manifest,
        input_precheck=input_precheck,
        worker_benchmark=benchmark,
        runtime_status=runtime,
        artifact_paths={"log": tmp_path / "run.log", "control": tmp_path / "c.db"},
        created_at="2026-09-05T21:05:00+00:00",
        artifact_path=tmp_path / "summary.json",
    )

    snapshot = summary["project_snapshot"]
    assert snapshot["snapshot_kind"] == "COPYABLE_TECHNICAL_PROJECT_SNAPSHOT"
    assert snapshot["provenance"]["contract_fingerprint"] == contract[
        "contract_fingerprint"
    ]
    assert snapshot["provenance"]["source_dataset_fingerprint"] == "dataset-fp"
    assert snapshot["provenance"]["universe_fingerprint"] == "universe-fp"
    assert snapshot["benchmark"]["selected_worker_count"] == 4
    assert snapshot["benchmark"]["selected_configuration"][
        "scientific_digest"
    ] == "digest-fp"
    assert snapshot["timeline"]["last_work_unit_id"] == "unit-2"
    assert snapshot["counts"]["cases"]["raw_n"] == 2
    assert snapshot["counts"]["cases"]["r_na"] == 1
    assert snapshot["counts"]["cases"]["censored"] == 1
    assert snapshot["counts"]["work_units"]["skip_reasons"] == audit[
        "skipped_work_unit_exclusions"
    ]
    assert report["work_unit_exclusions"] == audit[
        "skipped_work_unit_exclusions"
    ]
    assert summary["work_unit_exclusions"] == audit[
        "skipped_work_unit_exclusions"
    ]
    effective_n = snapshot["evidence_strength"][
        "verified_issuer_adjusted_effective_n"
    ]
    assert effective_n["status"] == "PARTIAL_UNKNOWN"
    assert effective_n["value"] == 0
    assert effective_n["unknown_dependency_contribution"] == 0
    assert effective_n["raw_or_listing_counts_used_as_substitute"] is False
    assert snapshot["evidence_strength"]["unique_listings"]["value"] == 2
    assert snapshot["evidence_strength"]["distinct_signal_days"]["value"] == 2
    assert snapshot["evidence_strength"]["distinct_observation_days"]["value"] is None
    assert all(snapshot["closed_paths"].values())
    assert "--status" in snapshot["operations"]["status_command"]
    assert verify_self_fingerprinted_artifact(summary)


def test_existing_plan_conflict_is_not_overwritten(tmp_path: Path) -> None:
    _plan(tmp_path)
    with pytest.raises(DevelopmentV6ReportingError, match="other content"):
        freeze_v6_descriptive_plan(
            contract_basis_fingerprint="other-basis",
            combined_input_fingerprint="input-fp",
            created_at="2026-09-05T17:00:00+00:00",
            artifact_path=tmp_path / "plan.json",
        )
    persisted = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    assert persisted["contract_basis_fingerprint"] == CONTRACT_BASIS_FINGERPRINT
