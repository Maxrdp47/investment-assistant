from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from research_knowledge import ResearchKnowledgeBase, ResearchWorkflow
from scripts import sync_buyer_confirmation_validation_kb as sync


def _seed_hypothesis(path: Path, monkeypatch) -> dict:
    knowledge = ResearchKnowledgeBase(path)
    hypothesis = knowledge.create_hypothesis(
        title="Pullback-Tiefe und Buyer Confirmation als inkrementelle Merkmale",
        area="swing_trader",
        category="Pullback",
        claim="Buyer Confirmation kann inkrementelle Information enthalten.",
        mechanism="Ein abgeschlossener Käuferimpuls kann Nachfrage anzeigen.",
        external_evidence="medium",
        rating="B",
        risks_limitations="Nur eine enge Regel wird separat getestet.",
        status="RAW",
        strategy="Long Pullback",
        asset_class="EQUITIES",
        created_at="2026-08-24T11:11:12+00:00",
    )
    monkeypatch.setattr(sync, "HYPOTHESIS_ID", hypothesis["id"])
    ResearchWorkflow(path).record_market_scope(
        target_type="hypothesis",
        target_id=hypothesis["id"],
        asset_class="EQUITIES",
        region="Bestehender SwingTrader-Scope",
        universe="Versioniertes Aktien-/ETF-Research-Universum",
        timeframe="Daily; Tage bis Wochen",
        scope_notes="Eigener Hypothesenscope.",
        assessed_at="2026-08-24T11:11:12+00:00",
    )
    return hypothesis


def _decision_report() -> dict[str, object]:
    return {
        "status": "VALIDATION_FAIL",
        "research_stage": "validation",
        "next_stage_allowed": False,
        "reviewed_at": "2026-08-27T03:51:53.005314+02:00",
        "review_fingerprint": "review-fingerprint",
        "failed_gates": [
            "conservative_execution_treatment_pf_above_one",
            "conservative_execution_treatment_positive",
            "positive_in_at_least_60pct_of_years",
        ],
        "treatment": {
            "evaluated_n": 30_294,
            "win_rate_pct": 42.18657,
            "expectancy_r": 0.009384,
            "profit_factor": 1.017033,
            "risk_and_entry_geometry": {
                "mfe_r": {"mean": 1.5},
                "mae_r": {"mean": -0.8},
            },
        },
        "candidate_sequence_drawdown": {"maximum_drawdown_r": 2515.744},
    }


def test_terminal_rejection_requires_the_exact_frozen_validation_failure() -> None:
    report = _decision_report()
    sync._validate_terminal_decision(report, sync.TERMINAL_VALIDATION_REJECTION)

    changed = dict(report)
    changed["next_stage_allowed"] = True
    with pytest.raises(ValueError, match="widerspricht"):
        sync._validate_terminal_decision(changed, sync.TERMINAL_VALIDATION_REJECTION)


def test_completed_negative_result_backfills_assessment_once_and_stays_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "knowledge.sqlite3"
    hypothesis = _seed_hypothesis(database, monkeypatch)
    report_path = tmp_path / "validation-decision.json"
    report = _decision_report()
    report_path.write_text(json.dumps(report), encoding="utf-8")
    prepared = sync.prepare(database, prepared_at="2026-08-26T20:12:20+02:00")

    # Reproduce the historical state: result/work request were complete, while
    # the append-only result gate assessment had not yet been recorded.
    workflow = ResearchWorkflow(database)
    request = workflow.get_work_request(prepared["work_request_id"], include_context=False)
    completed = workflow.complete_work_request(
        request["id"],
        claim_token=sync.CLAIM_TOKEN,
        worker_context=sync.WORKER_CONTEXT,
        result=sync._result_payload(report, sync.TERMINAL_VALIDATION_REJECTION),
        result_reference=str(report_path),
        artifact_references=(
            {
                "system": "buyer_confirmation_validation",
                "record_type": "stage_decision",
                "record_id": "review-fingerprint",
            },
        ),
        completed_at="2026-08-27T01:52:55+00:00",
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM result_validation_assessments"
        ).fetchone()[0] == 0

    repaired = sync.complete(
        database,
        decision_report_path=report_path,
        final_decision=sync.TERMINAL_VALIDATION_REJECTION,
        completed_at="2026-08-27T01:52:55+00:00",
    )
    replay = sync.complete(
        database,
        decision_report_path=report_path,
        final_decision=sync.TERMINAL_VALIDATION_REJECTION,
        completed_at="2026-08-27T01:52:55+00:00",
    )

    assert repaired["result_id"] == completed["result_id"]
    assert repaired["candidate_lifecycle_status"] == "REJECTED_AT_VALIDATION"
    assert repaired["hypothesis_status_unchanged"] is True
    assert repaired["hypothesis_validation_evidence_selected"] is False
    assert replay["result_validation_assessment_id"] == repaired[
        "result_validation_assessment_id"
    ]
    assert replay["idempotent_replay"] is True
    stored_hypothesis = ResearchKnowledgeBase(database).get_hypothesis(
        hypothesis["id"], include_details=False
    )
    assert stored_hypothesis["current_status"] == "RAW"
    assert stored_hypothesis["rating"] == "B"

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        assessment = dict(
            connection.execute(
                "SELECT * FROM result_validation_assessments WHERE result_id=?",
                (completed["result_id"],),
            ).fetchone()
        )
        assert assessment["result_direction"] == "NEGATIVE"
        assert assessment["oos_status"] == "FAILED"
        assert assessment["walk_forward_status"] == "FAILED"
        assert assessment["costs_slippage_status"] == "FAILED"
        assert assessment["sample_size_status"] == "PASSED"
        assert assessment["data_quality_status"] == "PASSED"
        assert connection.execute("SELECT COUNT(*) FROM research_results").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM result_validation_assessments"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM hypothesis_validation_evidence"
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM integration_candidates").fetchone()[0] == 0
