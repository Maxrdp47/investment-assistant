from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research_knowledge import ResearchKnowledgeBase, ResearchWorkflow
from research_knowledge.source_identity import normalize_source_url
from research_knowledge.workflow import WorkRequestConflict
from scripts.research_work_handoff import _parser as handoff_parser, run_command


def _source(kb: ResearchKnowledgeBase) -> dict:
    intake = kb.intake_source(
        title="Pullback Research",
        source_type="youtube",
        summary="Neutraler Research-Input.",
        platform="youtube",
        creator="Research Creator",
        direct_url="https://youtu.be/AbCdEf12345?si=tracking",
        published_date="2026-08-20",
        provenance="DB-Chat Video-Intake",
        captured_at="2026-08-20T08:00:00+00:00",
    )
    return intake["source"]


def _hypothesis(kb: ResearchKnowledgeBase, source_id: str) -> dict:
    idea = kb.create_hypothesis(
        title="Buyer Confirmation",
        area="swing_trader",
        category="Pullback",
        claim="Buyer Confirmation verbessert die Pullback-Fortsetzung.",
        mechanism="Ein abgeschlossener Käuferimpuls kann neue Nachfrage zeigen.",
        external_evidence="medium",
        rating="B",
        risks_limitations="Kosten, Sample Size, Regime und Survivorship Bias.",
        status="HYPOTHESIS",
        strategy="Long Pullback",
        asset_class="EQUITIES",
        created_at="2026-08-20T09:00:00+00:00",
    )
    kb.link_source(idea["id"], source_id, stance="context")
    return idea


def _experiment(kb: ResearchKnowledgeBase, hypothesis_id: str, *, status: str = "PLANNED") -> dict:
    return kb.create_experiment(
        hypothesis_id,
        title="Buyer-Confirmation PIT-Test",
        test_definition="Inkrementeller Test gegen unveränderte Pullback-Baseline.",
        features=["buyer_confirmation", "pullback_depth"],
        data_universe="Historisches Point-in-Time-Aktienuniversum.",
        period_start="2016-01-01",
        period_end="2025-12-31",
        point_in_time_rules="Chronologische Splits, OOS und Walk-Forward ohne Leakage.",
        baseline="Unveränderte Pullback-Baseline.",
        parameters={"buyer_confirmation": "close_above_previous_high"},
        test_status=status,
        created_at="2026-08-20T10:00:00+00:00",
    )


def _scope(workflow: ResearchWorkflow, *, hypothesis_id: str, experiment_id: str) -> None:
    workflow.record_market_scope(
        target_type="hypothesis",
        target_id=hypothesis_id,
        asset_class="EQUITIES",
        region="US",
        universe="Point-in-Time equities",
        timeframe="Daily",
        scope_notes="Eigener EQUITIES-Hypothesenscope.",
    )
    workflow.record_market_scope(
        target_type="experiment",
        target_id=experiment_id,
        asset_class="EQUITIES",
        region="US",
        universe="Point-in-Time equities",
        timeframe="Daily",
        scope_notes="Kein Cross-Market-Transfer.",
    )


def _capability(
    workflow: ResearchWorkflow,
    hypothesis_id: str,
    experiment_id: str,
    *,
    outcome: str = "TESTABLE_NOW",
) -> dict:
    return workflow.record_application_assessment(
        hypothesis_id,
        experiment_id=experiment_id,
        outcome=outcome,
        feature_available=True,
        required_data_available=outcome != "NEW_DATA_REQUIRED",
        existing_research_test=True,
        market_scope_reviewed=outcome not in {"NO_ACTION", "DEFERRED"},
        active_rule_exists=False,
        infrastructure_needed="Bestehender Research-Runner" if outcome != "NO_ACTION" else "Keine",
        existing_assets={"test": "tests/test_research_handoff.py"} if outcome not in {"NO_ACTION", "DEFERRED"} else {},
        rationale="Tatsächlichen Projektbestand geprüft.",
    )


def _work_request(workflow: ResearchWorkflow, source_id: str, hypothesis_id: str, experiment_id: str) -> dict:
    capability = _capability(workflow, hypothesis_id, experiment_id)
    return workflow.create_work_request(
        hypothesis_id,
        capability_assessment_id=capability["id"],
        experiment_id=experiment_id,
        source_id=source_id,
        request_type="RESEARCH_TEST",
        task="Führe den vorregistrierten PIT-Test aus.",
        expected_output="Persistentes Resultat mit OOS-/Walk-Forward-Metriken.",
        required_infrastructure="Bestehender Research-Runner und temporäre Testdatenbank.",
        scope={"source_scope": ["EQUITIES"], "test_scope": ["EQUITIES"]},
        safeguards={"long_v1_unchanged": True},
    )


def _positive_result() -> dict:
    return {
        "title": "Buyer Confirmation OOS",
        "conclusion": "supports",
        "interpretation": "Positiver inkrementeller Nettoeffekt im festgelegten Scope.",
        "sample_size": 1_240,
        "hit_rate": 54.2,
        "expectancy": 0.18,
        "profit_factor": 1.17,
        "drawdown": 8.4,
        "mfe": 1.4,
        "mae": -0.8,
        "r_multiples": 0.18,
        "costs": 0.12,
        "slippage": 0.08,
        "in_sample": {"status": "PASSED"},
        "validation": {"status": "PASSED"},
        "out_of_sample": {"status": "PASSED"},
        "walk_forward": {"status": "PASSED", "folds": 6},
        "forward": {"status": "PASSED"},
        "papertrade": {"status": "PASSED"},
    }


def _assessment_arguments(*, pit_status: str = "PASSED") -> dict:
    return {
        "research_type": "tradable_strategy_feature",
        "result_direction": "SUPPORTING",
        "source_scopes": ["EQUITIES"],
        "hypothesis_test_scopes": ["EQUITIES"],
        "experiment_test_scopes": ["EQUITIES"],
        "validated_scopes": ["EQUITIES"],
        "is_status": "PASSED",
        "oos_status": "PASSED",
        "walk_forward_status": "PASSED",
        "external_unseen_status": "NOT_REQUIRED",
        "forward_status": "PASSED",
        "paper_status": "PASSED",
        "sample_size_status": "PASSED",
        "uncertainty_status": "PASSED",
        "costs_slippage_status": "PASSED",
        "data_quality_status": "PASSED",
        "leakage_status": "PASSED",
        "pit_status": pit_status,
        "critical_blocker": False,
        "limitations": "Nur der vorregistrierte EQUITIES-Scope.",
        "artifact_references": [{"system": "pytest", "record_id": "run-1"}],
        "rationale": "Bestehende versionierte Gates wurden einzeln geprüft.",
    }


def test_source_identity_normalizes_video_urls_and_is_idempotent(tmp_path: Path) -> None:
    kb = ResearchKnowledgeBase(tmp_path / "source.sqlite3")
    first = _source(kb)

    duplicate = kb.intake_source(
        title="Pullback Research",
        source_type="youtube",
        summary="Neutraler Research-Input.",
        platform="youtube",
        creator="Research Creator",
        direct_url="https://www.youtube.com/watch?v=AbCdEf12345&utm_source=x&feature=share",
        published_date="2026-08-20",
        provenance="DB-Chat Video-Intake",
        captured_at="2026-08-21T08:00:00+00:00",
    )

    assert normalize_source_url("https://youtu.be/AbCdEf12345?si=x") == "https://youtube.com/watch?v=AbCdEf12345"
    assert duplicate["status"] == "DUPLICATE_SOURCE"
    assert duplicate["source_id"] == first["id"]
    assert duplicate["provenance_added"] is False
    assert len(duplicate["source"]["provenance"]) == 1
    assert len(kb.search_hypotheses()) == 0
    with sqlite3.connect(kb.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1


def test_source_hash_provenance_and_conservative_possible_duplicate(tmp_path: Path) -> None:
    kb = ResearchKnowledgeBase(tmp_path / "hash.sqlite3")
    first = _source(kb)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"same-video-content")
    enriched = kb.intake_source(
        title="Pullback Research",
        source_type="youtube",
        summary="Neutraler Research-Input.",
        platform="youtube",
        creator="Research Creator",
        direct_url="https://youtube.com/shorts/AbCdEf12345",
        local_file=video,
        provenance="Originaldatei ergänzt",
    )
    file_only = kb.intake_source(
        title="Lokale Kopie",
        source_type="youtube",
        summary="Dieselbe Originaldatei.",
        platform="youtube",
        local_file=video,
        provenance="Erneuter Datei-Upload",
    )
    uncertain = kb.intake_source(
        title="Metadaten ohne Link",
        source_type="other",
        summary="Erste Metadatenquelle.",
        creator="Creator X",
        provenance="Legacy-Notiz",
        confirm_distinct=True,
    )
    possible = kb.intake_source(
        title="Metadaten ohne Link",
        source_type="other",
        summary="Ähnliche Metadaten.",
        creator="Creator X",
        direct_url="https://example.test/original-research",
        provenance="Zweite Legacy-Notiz",
    )
    resolved = kb.intake_source(
        title="Metadaten ohne Link",
        source_type="other",
        summary="Original-Link nach Prüfung ergänzt.",
        creator="Creator X",
        direct_url="https://example.test/original-research?utm_source=chat",
        provenance="Original-Link nach bewusster Prüfung",
        resolve_to_source_id=uncertain["source_id"],
    )
    new_video = kb.intake_source(
        title="Pullback Research",
        source_type="youtube",
        summary="Anderes Video desselben Creators.",
        platform="youtube",
        creator="Research Creator",
        direct_url="https://youtu.be/ZyXwVu98765",
        provenance="Neues Video",
    )

    assert enriched["status"] == "PROVENANCE_ENRICHED"
    assert enriched["source_id"] == first["id"]
    assert file_only["source_id"] == first["id"]
    assert possible["status"] == "POSSIBLE_DUPLICATE"
    assert possible["possible_duplicate_source_ids"] == [uncertain["source_id"]]
    assert resolved["status"] == "PROVENANCE_ENRICHED"
    assert resolved["source_id"] == uncertain["source_id"]
    assert new_video["status"] == "NEW_SOURCE"
    assert new_video["source_id"] != first["id"]


def test_work_request_claim_completion_and_result_retry_are_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "handoff.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = _source(kb)
    idea = _hypothesis(kb, source["id"])
    experiment = _experiment(kb, idea["id"])
    _scope(workflow, hypothesis_id=idea["id"], experiment_id=experiment["id"])
    request = _work_request(workflow, source["id"], idea["id"], experiment["id"])
    duplicate_request = _work_request(workflow, source["id"], idea["id"], experiment["id"])

    assert request["current_status"] == "READY"
    assert duplicate_request["id"] == request["id"]
    cli_ready = run_command(
        handoff_parser().parse_args(
            ["--database", str(path), "list", "--status", "READY"]
        )
    )
    assert cli_ready[0]["id"] == request["id"]
    claimed = workflow.claim_work_request(request["id"], worker_context="work-chat-A")
    with pytest.raises(WorkRequestConflict):
        workflow.claim_work_request(request["id"], worker_context="work-chat-B")
    completed = workflow.complete_work_request(
        request["id"],
        claim_token=claimed["claim_token"],
        worker_context="work-chat-A",
        result=_positive_result(),
        result_reference="runtime/research-run.sqlite3#run-1",
        artifact_references=[
            {
                "system": "research_runner",
                "record_type": "run",
                "record_id": "run-1",
                "uri": "runtime/research-run.sqlite3#run-1",
            }
        ],
    )
    replay = workflow.complete_work_request(
        request["id"],
        claim_token=claimed["claim_token"],
        worker_context="work-chat-A",
        result=_positive_result(),
    )

    assert completed["current_status"] == "COMPLETED"
    assert completed["result"]["experiment_id"] == experiment["id"]
    assert replay["idempotent_replay"] is True
    assert kb.get_experiment(experiment["id"])["current_status"] == "COMPLETED"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_results").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM research_work_requests").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM work_request_result_links").fetchone()[0] == 1


def test_work_request_block_retry_and_no_action_guards(tmp_path: Path) -> None:
    path = tmp_path / "blocked.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = _source(kb)
    idea = _hypothesis(kb, source["id"])
    experiment = _experiment(kb, idea["id"])
    _scope(workflow, hypothesis_id=idea["id"], experiment_id=experiment["id"])
    request = _work_request(workflow, source["id"], idea["id"], experiment["id"])
    claimed = workflow.claim_work_request(request["id"], worker_context="work-chat-A")
    blocked = workflow.block_work_request(
        request["id"],
        claim_token=claimed["claim_token"],
        blocker_reason="Point-in-Time-Daten fehlen.",
        worker_context="work-chat-A",
    )
    ready = workflow.retry_blocked_work_request(
        request["id"], reason="Daten sind jetzt vorhanden.", actor="db-chat"
    )
    no_action = _capability(workflow, idea["id"], experiment["id"], outcome="NO_ACTION")

    assert blocked["current_status"] == "BLOCKED"
    assert ready["current_status"] == "READY"
    with pytest.raises(ValueError, match="NO_ACTION"):
        workflow.create_work_request(
            idea["id"],
            capability_assessment_id=no_action["id"],
            experiment_id=experiment["id"],
            request_type="RESEARCH_TEST",
            task="Soll nicht entstehen.",
            expected_output="Keiner.",
            required_infrastructure="Keine.",
            scope={"test_scope": ["EQUITIES"]},
            safeguards={},
        )
    deferred = _capability(workflow, idea["id"], experiment["id"], outcome="DEFERRED")
    with pytest.raises(ValueError, match="DEFERRED"):
        workflow.create_work_request(
            idea["id"],
            capability_assessment_id=deferred["id"],
            experiment_id=experiment["id"],
            request_type="RESEARCH_TEST",
            task="Soll ebenfalls nicht entstehen.",
            expected_output="Keiner.",
            required_infrastructure="Keine.",
            scope={"test_scope": ["EQUITIES"]},
            safeguards={},
        )


def test_validated_requires_selected_supporting_result_and_every_gate(tmp_path: Path) -> None:
    path = tmp_path / "validated.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = _source(kb)
    idea = _hypothesis(kb, source["id"])
    experiment = _experiment(kb, idea["id"], status="COMPLETED")
    _scope(workflow, hypothesis_id=idea["id"], experiment_id=experiment["id"])
    result = kb.record_result(experiment["id"], **_positive_result())

    with pytest.raises(ValueError, match="explizite ID"):
        kb.change_hypothesis_status(idea["id"], "VALIDATED", reason="Zu früh.")
    failed_pit = workflow.assess_result_for_validation(
        result["id"], **_assessment_arguments(pit_status="FAILED")
    )
    with pytest.raises(sqlite3.IntegrityError, match="every applicable gate passed"):
        workflow.select_result_for_validation(
            idea["id"],
            result["id"],
            failed_pit["id"],
            selected_by="db-chat",
            rationale="PIT ist nicht bestanden.",
        )
    passed = workflow.assess_result_for_validation(result["id"], **_assessment_arguments())
    workflow.select_result_for_validation(
        idea["id"],
        result["id"],
        passed["id"],
        selected_by="db-chat",
        rationale="Alle geltenden Gates sind bestanden.",
    )
    changed = kb.change_hypothesis_status(
        idea["id"],
        "VALIDATED",
        validation_result_id=result["id"],
        reason="Explizit ausgewähltes internes Resultat erfüllt alle Gates.",
    )

    assert changed["current_status"] == "VALIDATED"
    assert workflow.workflow_for_hypothesis(idea["id"])["automatic_strategy_integration"] is False


@pytest.mark.parametrize("conclusion,direction", [("negative", "NEGATIVE"), ("inconclusive", "INCONCLUSIVE")])
def test_negative_or_inconclusive_result_cannot_validate(
    tmp_path: Path, conclusion: str, direction: str
) -> None:
    path = tmp_path / f"{conclusion}.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = _source(kb)
    idea = _hypothesis(kb, source["id"])
    experiment = _experiment(kb, idea["id"], status="COMPLETED")
    _scope(workflow, hypothesis_id=idea["id"], experiment_id=experiment["id"])
    values = _positive_result()
    values["conclusion"] = conclusion
    values["interpretation"] = "Kein unterstützendes Ergebnis."
    result = kb.record_result(experiment["id"], **values)
    arguments = _assessment_arguments()
    arguments["result_direction"] = direction
    arguments["validated_scopes"] = []
    if direction == "NEGATIVE":
        arguments["rejected_scopes"] = ["EQUITIES"]
    else:
        arguments["rejected_scopes"] = []
    assessment = workflow.assess_result_for_validation(result["id"], **arguments)

    with pytest.raises(sqlite3.IntegrityError, match="every applicable gate passed"):
        workflow.select_result_for_validation(
            idea["id"],
            result["id"],
            assessment["id"],
            selected_by="db-chat",
            rationale="Darf nicht validieren.",
        )


def test_validation_rejects_scope_transfer_and_missing_oos(tmp_path: Path) -> None:
    path = tmp_path / "scope.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = _source(kb)
    idea = _hypothesis(kb, source["id"])
    experiment = _experiment(kb, idea["id"], status="COMPLETED")
    _scope(workflow, hypothesis_id=idea["id"], experiment_id=experiment["id"])
    result = kb.record_result(experiment["id"], **_positive_result())
    wrong_scope = _assessment_arguments()
    wrong_scope["experiment_test_scopes"] = ["FX"]
    with pytest.raises(ValueError, match="Experiment-Scope widerspricht"):
        workflow.assess_result_for_validation(result["id"], **wrong_scope)
    missing_oos = _assessment_arguments()
    missing_oos["oos_status"] = "NOT_RUN"
    with pytest.raises(ValueError, match="OOS"):
        workflow.assess_result_for_validation(result["id"], **missing_oos)


def test_data_leakage_gate_blocks_validation_selection(tmp_path: Path) -> None:
    path = tmp_path / "leakage.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = _source(kb)
    idea = _hypothesis(kb, source["id"])
    experiment = _experiment(kb, idea["id"], status="COMPLETED")
    _scope(workflow, hypothesis_id=idea["id"], experiment_id=experiment["id"])
    result = kb.record_result(experiment["id"], **_positive_result())
    arguments = _assessment_arguments()
    arguments["leakage_status"] = "INVALID"
    assessment = workflow.assess_result_for_validation(result["id"], **arguments)

    with pytest.raises(sqlite3.IntegrityError, match="every applicable gate passed"):
        workflow.select_result_for_validation(
            idea["id"],
            result["id"],
            assessment["id"],
            selected_by="db-chat",
            rationale="Leakage muss sperren.",
        )
