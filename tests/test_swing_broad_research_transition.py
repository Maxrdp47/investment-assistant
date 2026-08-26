from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from swing_broad_research import BROAD_RESEARCH_FEATURE_VERSION
from swing_broad_research_transition import (
    BroadResearchTransitionError,
    broad_transition_identity,
    load_broad_transition_receipt,
    record_broad_transition_receipt,
    validate_broad_research_transition,
)
from scripts.run_swing_broad_research import (
    CHECKPOINT_INTERVAL_ASSETS,
    _checkpoint_crossed,
    _completion_ledger_checkpoint_audit,
    _incremental_block_audit,
    _next_checkpoint,
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
    with pytest.raises(BroadResearchTransitionError, match="festen Kampagnenjobs"):
        validate_broad_research_transition(**mixed)


def test_transition_accepts_separate_fixed_and_weekly_dataset_groups() -> None:
    inputs = _inputs()
    weekly_fingerprint = "weekly-dataset-fingerprint"
    for index in range(240, 248):
        job_key = f"job-{index:03d}"
        inputs["campaign_jobs"][index] = {
            "job_key": job_key,
            "epoch": "2026-W34",
            "contract": {"recurrence": "weekly"},
        }
        inputs["campaign_state"]["completed"][job_key] = {
            "dataset_epoch": "epoch|2026-W34",
            "dataset_fingerprint": weekly_fingerprint,
            "contract": "weekly-monitoring",
            "shard_index": index - 240,
        }

    payload = validate_broad_research_transition(**inputs)

    assert payload["campaign_dataset_groups"] == {
        "fixed_jobs": 240,
        "fixed_dataset_epoch": "epoch|fixed",
        "fixed_dataset_fingerprint": "dataset-fingerprint",
        "monitoring_jobs": 8,
        "monitoring_datasets": {"epoch|2026-W34": weekly_fingerprint},
    }


def test_transition_rejects_inconsistent_weekly_monitoring_dataset() -> None:
    inputs = _inputs()
    for index in range(240, 248):
        job_key = f"job-{index:03d}"
        inputs["campaign_jobs"][index] = {
            "job_key": job_key,
            "epoch": "2026-W34",
            "contract": {"recurrence": "weekly"},
        }
        inputs["campaign_state"]["completed"][job_key] = {
            "dataset_epoch": "epoch|2026-W34",
            "dataset_fingerprint": "weekly-dataset-fingerprint",
            "contract": "weekly-monitoring",
            "shard_index": index - 240,
        }
    inputs["campaign_state"]["completed"]["job-247"][
        "dataset_fingerprint"
    ] = "other-weekly-fingerprint"

    with pytest.raises(BroadResearchTransitionError, match="Monitoringjobs"):
        validate_broad_research_transition(**inputs)


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
    broad_at = wrapper.index("run_swing_broad_research_supervisor.py")

    assert campaign_at < error_gate_at < broad_at
    assert "--maximum-assets-per-batch 32" in wrapper
    assert "--workers 6" in wrapper


def test_broad_ledger_audit_runs_at_checkpoints_and_final_completion() -> None:
    assert CHECKPOINT_INTERVAL_ASSETS == 256
    assert _checkpoint_crossed(224, 256, 2520) is True
    assert _checkpoint_crossed(768, 800, 2520) is False
    assert _checkpoint_crossed(992, 1024, 2520) is True
    assert _checkpoint_crossed(2496, 2520, 2520) is True
    assert _next_checkpoint(800, 2520) == 1024
    assert _next_checkpoint(2496, 2520) == 2520


def test_incremental_broad_block_audit_keeps_per_write_quality_gates() -> None:
    audit = _incremental_block_audit(
        [
            {
                "already_complete": False,
                "candidates": 11,
                "labels": 11,
                "counterfactuals": 11,
            },
            {
                "already_complete": False,
                "candidates": 7,
                "labels": 7,
                "counterfactuals": 7,
            },
        ],
        completed_before=800,
        completed_after=802,
        expected_assets=2520,
    )

    assert audit["status"] == "ok"
    assert audit["new_asset_completions"] == 2
    assert audit["stored_candidates"] == 18
    assert audit["stored_labels"] == 18
    assert audit["stored_counterfactuals"] == 18
    assert audit["append_only_transactions_verified_on_write"] is True
    assert audit["fingerprints_verified_on_write"] is True


def test_incremental_broad_block_audit_fails_closed_on_count_mismatch() -> None:
    with pytest.raises(RuntimeError, match="Blockprüfung fehlgeschlagen"):
        _incremental_block_audit(
            [
                {
                    "already_complete": False,
                    "candidates": 10,
                    "labels": 9,
                    "counterfactuals": 10,
                }
            ],
            completed_before=800,
            completed_after=801,
            expected_assets=2520,
        )


def _record_completion_receipt(
    database,
    *,
    symbol: str = "AAA",
    candidates: int = 11,
    labels: int = 11,
    tamper_fingerprint: bool = False,
) -> None:
    dataset_fingerprint = "dataset-fingerprint"
    receipt = {
        "symbol": symbol,
        "dataset_fingerprint": dataset_fingerprint,
        "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
        "status": "ok",
        "candidate_ids": [f"candidate-{index}" for index in range(candidates)],
        "candidates": candidates,
        "labels": labels,
        "append_only": True,
    }
    receipt_json = json.dumps(
        receipt,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    fingerprint = hashlib.sha256(receipt_json.encode("utf-8")).hexdigest()
    if tamper_fingerprint:
        fingerprint = "0" * 64
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS broad_research_asset_completions (
            completion_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            dataset_fingerprint TEXT NOT NULL,
            feature_version TEXT NOT NULL,
            candidates INTEGER NOT NULL,
            labels INTEGER NOT NULL,
            completion_json TEXT NOT NULL,
            completion_fingerprint TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO broad_research_asset_completions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"completion-{symbol}",
                symbol,
                dataset_fingerprint,
                BROAD_RESEARCH_FEATURE_VERSION,
                candidates,
                labels,
                receipt_json,
                fingerprint,
            ),
        )


def test_completion_ledger_checkpoint_audit_verifies_signed_receipts(tmp_path) -> None:
    database = tmp_path / "broad.sqlite3"
    _record_completion_receipt(database)

    audit = _completion_ledger_checkpoint_audit(
        database,
        dataset_fingerprint="dataset-fingerprint",
        expected_assets=2520,
    )

    assert audit["status"] == "ok"
    assert audit["verified_completion_receipts"] == 1
    assert audit["candidate_count"] == 11
    assert audit["label_count"] == 11
    assert audit["research_row_scan_performed"] is False
    assert audit["final_full_audit_mandatory"] is True


@pytest.mark.parametrize(
    ("candidates", "labels", "tamper_fingerprint"),
    [(11, 10, False), (11, 11, True)],
)
def test_completion_ledger_checkpoint_audit_fails_closed(
    tmp_path,
    candidates: int,
    labels: int,
    tamper_fingerprint: bool,
) -> None:
    database = tmp_path / "broad.sqlite3"
    _record_completion_receipt(
        database,
        candidates=candidates,
        labels=labels,
        tamper_fingerprint=tamper_fingerprint,
    )

    with pytest.raises(RuntimeError, match="Abschlussbelegprüfung fehlgeschlagen"):
        _completion_ledger_checkpoint_audit(
            database,
            dataset_fingerprint="dataset-fingerprint",
            expected_assets=2520,
        )
