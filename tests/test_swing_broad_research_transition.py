from __future__ import annotations

import json

import pytest

from swing_broad_research_transition import (
    BroadResearchTransitionError,
    broad_transition_identity,
    load_broad_transition_receipt,
    record_broad_transition_receipt,
    validate_broad_research_transition,
)


def _inputs(*, completed: int = 248, pending: int = 0) -> dict:
    fingerprint = "dataset-fingerprint"
    jobs = [{"job_key": f"job-{index:03d}"} for index in range(248)]
    state = {
        "completed": {
            f"job-{index:03d}": {
                "dataset_epoch": "epoch|fixed",
                "dataset_fingerprint": fingerprint,
                "contract": "contract",
                "shard_index": index,
            }
            for index in range(completed)
        }
    }
    return {
        "campaign_status": {
            "jobs_total": 248,
            "jobs_completed": completed,
            "jobs_pending": pending,
        },
        "campaign_state": state,
        "campaign_jobs": jobs,
        "manifest": {
            "status": "finalized",
            "dataset_epoch": "epoch|fixed",
            "dataset_fingerprint": fingerprint,
            "dataset_revision": fingerprint,
            "manifest_version": "manifest-v1",
        },
        "walk_forward_audit": {
            "schema_version": 3,
            "quick_check": "ok",
            "status": "ok",
            "invalid_count": 0,
            "runs": 10,
            "cases": 100,
            "observational_features": 80,
        },
        "code_fingerprint": "code-fingerprint",
        "feature_contract_fingerprint": "feature-fingerprint",
    }


def test_transition_is_blocked_before_exact_248_completion() -> None:
    with pytest.raises(BroadResearchTransitionError, match="noch nicht vollständig"):
        validate_broad_research_transition(**_inputs(completed=247, pending=1))


def test_transition_rejects_invalid_store_or_mixed_dataset_fingerprint() -> None:
    invalid = _inputs()
    invalid["walk_forward_audit"] = {**invalid["walk_forward_audit"], "invalid_count": 1}
    with pytest.raises(BroadResearchTransitionError, match="nicht vollständig gültig"):
        validate_broad_research_transition(**invalid)

    mixed = _inputs()
    mixed["campaign_state"]["completed"]["job-247"]["dataset_fingerprint"] = "other"
    with pytest.raises(BroadResearchTransitionError, match="denselben Frozen-Datensatz"):
        validate_broad_research_transition(**mixed)


def test_transition_receipt_is_reproducible_append_only_and_verified(tmp_path) -> None:
    inputs = _inputs()
    payload = validate_broad_research_transition(**inputs)
    identity = broad_transition_identity(
        campaign_status=inputs["campaign_status"],
        manifest=inputs["manifest"],
        code_fingerprint=inputs["code_fingerprint"],
        feature_contract_fingerprint=inputs["feature_contract_fingerprint"],
    )
    first = record_broad_transition_receipt(payload, identity=identity, directory=tmp_path)
    second = record_broad_transition_receipt(payload, identity=identity, directory=tmp_path)

    assert first == second
    assert first["append_only"] is True
    assert load_broad_transition_receipt(identity, tmp_path) == first
    path = next(tmp_path.glob("*.json"))
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["payload"]["existing_campaign_changed"] = True
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(BroadResearchTransitionError, match="Fingerprint"):
        load_broad_transition_receipt(identity, tmp_path)


def test_campaign_wrapper_runs_broad_handoff_only_after_campaign_success() -> None:
    wrapper = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_swing_walk_forward_campaign.cmd"
    ).read_text(encoding="utf-8")
    campaign_at = wrapper.index("run_swing_walk_forward_campaign.py")
    error_gate_at = wrapper.index("if errorlevel 1")
    broad_at = wrapper.index("run_swing_broad_research.py")

    assert campaign_at < error_gate_at < broad_at
    assert "--automatic-handoff" in wrapper
    assert "--maximum-assets 16" in wrapper
