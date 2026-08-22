from __future__ import annotations

import sqlite3

import pytest

from forecast_model_registry import (
    append_model_event,
    assess_model_promotion,
    load_model_candidates,
    model_registry_audit,
    register_shadow_candidate,
)


SHA = "a" * 64


def metadata() -> dict:
    return {
        "model_type": "entry_analysis",
        "horizon": "1w",
        "algorithm": "logistic_regression",
        "dataset_fingerprint": SHA,
        "walk_forward_fingerprint": "b" * 64,
        "feature_schema_version": "test-features-v1",
        "training_code_fingerprint": "c" * 64,
        "artifact_fingerprint": "d" * 64,
        "training_cutoff_at": "2026-08-09T22:30:00+02:00",
    }


def test_registry_is_append_only_and_never_activates_a_candidate(tmp_path) -> None:
    path = tmp_path / "models.sqlite3"
    result = register_shadow_candidate(metadata(), registered_at="2026-08-09T23:00:00+02:00", path=path)

    candidate = load_model_candidates(path)[0]
    gate = assess_model_promotion(candidate)

    assert result["inserted"] is True
    assert candidate["snapshot"]["mode"] == "shadow_only"
    assert gate["all_gates_passed"] is False
    assert gate["automatic_activation_performed"] is False
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM model_candidates")


def test_all_evidence_gates_still_require_separate_manual_activation(tmp_path) -> None:
    path = tmp_path / "models.sqlite3"
    candidate_id = register_shadow_candidate(
        metadata(), registered_at="2026-08-09T23:00:00+02:00", path=path
    )["candidate_id"]
    append_model_event(
        candidate_id,
        "shadow_evaluated",
        "2026-12-01T00:00:00+01:00",
        {
            "unseen_windows": 4,
            "evaluation_cases": 1_500,
            "observation_weeks": 16,
            "brier_improvement": 0.02,
            "log_loss_improvement": 0.03,
            "max_drawdown_delta": -0.2,
            "segments_passed": 5,
        },
        path=path,
    )
    append_model_event(candidate_id, "manual_review_approved", "2026-12-02", {"reviewed": True}, path=path)
    append_model_event(candidate_id, "canary_verified", "2026-12-15", {"passed": True}, path=path)
    append_model_event(candidate_id, "rollback_verified", "2026-12-15", {"passed": True}, path=path)

    gate = assess_model_promotion(load_model_candidates(path)[0])

    assert gate["all_gates_passed"] is True
    assert gate["manual_activation_still_required"] is True
    assert gate["production_activation_allowed_by_this_function"] is False
    assert model_registry_audit(path)["status"] == "ok"


def test_invalid_fingerprints_are_rejected_before_registry_write(tmp_path) -> None:
    broken = metadata()
    broken["dataset_fingerprint"] = "not-a-hash"

    with pytest.raises(ValueError, match="dataset_fingerprint"):
        register_shadow_candidate(broken, registered_at="2026-08-09", path=tmp_path / "models.sqlite3")

    assert not (tmp_path / "models.sqlite3").exists()


def test_approval_before_shadow_evaluation_never_satisfies_gate_sequence(tmp_path) -> None:
    path = tmp_path / "models.sqlite3"
    candidate_id = register_shadow_candidate(
        metadata(), registered_at="2026-08-09T23:00:00+02:00", path=path
    )["candidate_id"]
    append_model_event(candidate_id, "manual_review_approved", "2026-08-10", {"reviewed": True}, path=path)
    append_model_event(
        candidate_id,
        "shadow_evaluated",
        "2026-12-01",
        {
            "unseen_windows": 4,
            "evaluation_cases": 1_500,
            "observation_weeks": 16,
            "brier_improvement": 0.02,
            "log_loss_improvement": 0.03,
            "max_drawdown_delta": -0.2,
            "segments_passed": 5,
        },
        path=path,
    )
    append_model_event(candidate_id, "canary_verified", "2026-12-15", {"passed": True}, path=path)
    append_model_event(candidate_id, "rollback_verified", "2026-12-15", {"passed": True}, path=path)

    gate = assess_model_promotion(load_model_candidates(path)[0])

    assert gate["checks"]["manual_review"] is False
    assert gate["checks"]["gate_sequence_valid"] is False
    assert gate["all_gates_passed"] is False
