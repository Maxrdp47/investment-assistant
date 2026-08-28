from __future__ import annotations

import sqlite3
from pathlib import Path

import swing_buyer_confirmation_validation as validation
from swing_buyer_confirmation_provenance import (
    audit_validation_store,
    compare_validation_stores,
)


def _freeze() -> dict[str, object]:
    payload = {
        "challenger_version": validation.CHALLENGER_VERSION,
        "freeze_version": validation.FREEZE_VERSION,
        "expected_assets_per_stage": 1,
        "identity": {"dataset_fingerprint": validation.EXPECTED_DATASET_FINGERPRINT},
        "single_new_rule": {
            "name": "buyer_confirmation",
            "definition": validation.BUYER_RULE,
            "point_in_time": "completed signal candle t only",
        },
        "additional_filters": [],
        "rules_mutable_after_freeze": False,
        "source_snapshots": {},
    }
    return {**payload, "freeze_fingerprint": validation._fingerprint(payload)}


def _build_store(path: Path) -> None:
    freeze = validation.record_challenger_freeze(_freeze(), path)
    validation.record_integrity_receipt(
        {
            "gate_version": "buyer-confirmation-pre-validation-integrity-2026.08.26-v1",
            "challenger_version": validation.CHALLENGER_VERSION,
            "status": "PASS",
        },
        path,
    )
    validation.open_stage(freeze, "validation", opened_at="opening-time", path=path)
    cases = []
    for candidate_id, treatment in (("treatment", True), ("control", False)):
        cases.append(
            {
                "candidate_id": candidate_id,
                "challenger_version": validation.CHALLENGER_VERSION,
                "freeze_fingerprint": freeze["freeze_fingerprint"],
                "research_stage": "validation",
                "comparison_group": "treatment" if treatment else "control",
                "buyer_confirmation": treatment,
                "alias_confirmation": treatment,
                "result_r": 1.0 if treatment else -1.0,
                "dependency_cluster": candidate_id,
                "signal_day": "2022-01-03",
                "ground_up_from_frozen_ohlcv": True,
                "development_case_read": False,
                "additional_filter_applied": False,
                "parameters_changed": False,
                "automatic_production_activation": False,
            }
        )
    validation.record_stage_asset(
        {
            "challenger_version": validation.CHALLENGER_VERSION,
            "freeze_fingerprint": freeze["freeze_fingerprint"],
            "research_stage": "validation",
            "symbol": "AAA",
            "source_status": "ok",
            "rebuilt_candidates": 2,
            "applicable_cases": 2,
            "treatment_cases": 1,
            "control_cases": 1,
            "missing_cases": 0,
            "ground_up_from_frozen_ohlcv": True,
            "development_case_read": False,
            "parameters_changed": False,
            "cases": cases,
        },
        path,
    )
    validation.record_stage_review(
        {
            "evaluation_version": "buyer-confirmation-unseen-stage-evaluation-2026.08.26-v1",
            "challenger_version": validation.CHALLENGER_VERSION,
            "research_stage": "validation",
            "status": "VALIDATION_FAIL",
            "completed_assets": 1,
            "expected_assets": 1,
            "failed_gates": ["treatment_expectancy_positive"],
            "gates": {"treatment_expectancy_positive": False},
            "next_stage_allowed": False,
        },
        reviewed_at="review-time",
        path=path,
    )


def test_read_only_audit_verifies_payloads_and_holdout_lock(tmp_path: Path) -> None:
    path = tmp_path / "validation.sqlite3"
    _build_store(path)

    audit = audit_validation_store(path)

    assert audit["sqlite_integrity_check"] == "ok"
    assert audit["foreign_key_violations"] == []
    assert audit["holdout_counts"] == {
        "buyer_stage_openings": 0,
        "buyer_stage_cases": 0,
        "buyer_stage_completions": 0,
        "buyer_stage_reviews": 0,
    }
    assert audit["case_contract_violations"] == 0
    assert all(
        item["passed"] for item in audit["payload_fingerprint_checks"].values()
    )
    # The production audit additionally requires the immutable 2520/181473 shape.
    assert audit["result_integrity"] == "FAILED"


def test_logical_reproduction_comparison_is_order_independent(tmp_path: Path) -> None:
    reference = tmp_path / "reference.sqlite3"
    reproduction = tmp_path / "reproduction.sqlite3"
    _build_store(reference)
    with sqlite3.connect(reference) as source, sqlite3.connect(reproduction) as target:
        source.backup(target)

    comparison = compare_validation_stores(reference, reproduction)

    assert comparison["byte_identical"] is False
    assert comparison["logical_records_identical"] is True
    assert all(comparison["comparisons"].values())
