from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research_knowledge import ResearchKnowledgeBase, ResearchWorkflow
from research_knowledge import CURRENT_SCHEMA_VERSION, initialize_database
from research_knowledge.schema import SCHEMA_MIGRATIONS


def add_source(kb: ResearchKnowledgeBase, title: str) -> dict:
    return kb.create_source(
        title=title,
        source_type="paper",
        reference=f"https://example.test/{title.casefold().replace(' ', '-')}",
        source_date="2026-08-20",
        summary=f"Neutrale Zusammenfassung: {title}.",
        created_at="2026-08-20T08:00:00+00:00",
    )


def add_hypothesis(
    kb: ResearchKnowledgeBase,
    *,
    claim: str = "Volumen nach einem Pullback verbessert die risikoadjustierte Rendite.",
    asset_class: str = "Aktien",
) -> dict:
    return kb.create_hypothesis(
        title="Volumenbestätigung nach Pullback",
        area="swing_trader",
        category="Momentum",
        claim=claim,
        mechanism="Neue Nachfrage kann die Fortsetzung eines Trends bestätigen.",
        external_evidence="medium",
        rating="B",
        risks_limitations="Survivorship Bias, Sektorcluster und Kosten.",
        strategy="Long Pullback",
        asset_class=asset_class,
        created_at="2026-08-20T09:00:00+00:00",
    )


def add_experiment(kb: ResearchKnowledgeBase, hypothesis_id: str, title: str = "PIT-Test") -> dict:
    return kb.create_experiment(
        hypothesis_id,
        title=title,
        test_definition="Inkrementeller Vergleich gegen die unveränderte Baseline.",
        features=["volume_ratio_20"],
        data_universe="Historisches Point-in-Time-Aktienuniversum.",
        period_start="2016-01-01",
        period_end="2025-12-31",
        point_in_time_rules="Features nur bis zum Signal-Cutoff; chronologische Splits.",
        baseline="Unverändertes Long-Pullback-Signal.",
        parameters={"volume_ratio": [1.0, 1.2]},
        test_status="COMPLETED",
        created_at="2026-08-20T10:00:00+00:00",
    )


def add_result(
    kb: ResearchKnowledgeBase,
    experiment_id: str,
    *,
    title: str,
    conclusion: str,
) -> dict:
    return kb.record_result(
        experiment_id,
        title=title,
        conclusion=conclusion,
        interpretation=(
            "Stabiler inkrementeller Mehrwert gegenüber der unveränderten Baseline."
            if conclusion == "supports"
            else "Kein stabiler inkrementeller Mehrwert nach Kosten."
        ),
        sample_size=1_240,
        hit_rate=54.2 if conclusion == "supports" else 48.1,
        expectancy=0.18 if conclusion == "supports" else -0.04,
        profit_factor=1.17 if conclusion == "supports" else 0.96,
        costs=0.12,
        slippage=0.08,
        validation={"expectancy": 0.14 if conclusion == "supports" else -0.01},
        out_of_sample={"expectancy": 0.16 if conclusion == "supports" else -0.04},
        walk_forward={"positive_folds": 5 if conclusion == "supports" else 2, "folds": 6},
        forward={"trades": 96, "expectancy": 0.11} if conclusion == "supports" else None,
        papertrade={"trades": 54, "expectancy": 0.09} if conclusion == "supports" else None,
        recorded_at="2026-08-21T10:00:00+00:00",
    )


def candidate_arguments(*, all_gates: bool) -> dict:
    return {
        "feature_combination": ["volume_ratio_20", "pullback_depth"],
        "incremental_value_assessment": "Expectancy +0,12 R gegenüber Baseline.",
        "oos_walk_forward_assessment": "Fünf von sechs Walk-Forward-Folds positiv.",
        "forward_paper_assessment": "Forward und Papertrade positiv, aber noch jung.",
        "sample_size_assessment": "1.240 historische und 150 Forward-/Paper-Fälle.",
        "costs_slippage_assessment": "Konservative Kosten und Slippage enthalten.",
        "feature_redundancy_assessment": "Korrelation geprüft; kein doppeltes Volumensignal.",
        "complexity_assessment": "Zwei Features, deterministische Berechnung.",
        "overfiltering_assessment": "Tradezahl bleibt bei 71 Prozent der Baseline.",
        "market_scope_assessment": "Nur liquide US-Aktien im getesteten Scope.",
        "simpler_variant_assessment": "Ein-Feature-Variante getestet und schwächer.",
        "baseline_trade_count": 2_000,
        "candidate_trade_count": 1_420,
        "incremental_value_confirmed": True,
        "oos_walk_forward_confirmed": True,
        "forward_paper_confirmed": all_gates,
        "sample_size_sufficient": True,
        "costs_included": True,
        "redundancy_acceptable": True,
        "complexity_justified": True,
        "overfiltering_acceptable": True,
        "trade_count_acceptable": True,
        "market_scope_validated": True,
        "simpler_solution_preferred": True,
        "limitations": "Gilt nicht für FX, Krypto oder illiquide Small Caps.",
    }


def test_new_source_claim_reuses_rejected_knowledge_instead_of_duplicating(tmp_path: Path) -> None:
    path = tmp_path / "claim-intake.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    old_source = add_source(kb, "Alte Volumenstudie")
    idea = add_hypothesis(kb)
    kb.link_source(idea["id"], old_source["id"], stance="supports")
    test = add_experiment(kb, idea["id"])
    add_result(kb, test["id"], title="Negativer Holdout", conclusion="negative")
    kb.change_hypothesis_status(
        idea["id"],
        "REJECTED",
        reason="Der Effekt verschwand nach Kosten im Holdout.",
    )
    new_source = add_source(kb, "Neue Replikation")

    captured = workflow.capture_source_claim(
        new_source["id"],
        claim=idea["claim"],
        original_market_scope="Liquide US-Aktien, Tagesdaten",
        extraction_notes="Claim neutral aus dem Paper extrahiert.",
    )

    assert captured["matches"][0]["hypothesis_id"] == idea["id"]
    assert captured["matches"][0]["exact_claim_match"] == 1
    assert captured["matches"][0]["was_rejected"] == 1
    assert captured["matches"][0]["experiment_count"] == 1
    assert captured["matches"][0]["result_count"] == 1
    assert captured["matches"][0]["rejection_reason"] == "Der Effekt verschwand nach Kosten im Holdout."

    resolved = workflow.resolve_claim_with_existing_hypothesis(
        captured["id"],
        idea["id"],
        rationale="Gleicher Claim; neue Quelle wird als zusätzliche Evidenz abgelegt.",
        stance="supports",
        updated_evidence_strength="strong",
        evidence_confidence=72,
    )
    detail = kb.get_hypothesis(idea["id"])

    assert resolved["resolutions"][-1]["resolution"] == "LINKED_EXISTING"
    assert len(detail["sources"]) == 2
    assert detail["current_status"] == "REJECTED"
    assert detail["effective_external_evidence"] == "strong"
    assert detail["evidence_confidence"] == 72
    assert len(kb.search_hypotheses()) == 1
    assert workflow.workflow_for_hypothesis(idea["id"])["automatic_strategy_integration"] is False

    with pytest.raises(ValueError, match="bereits"):
        workflow.capture_source_claim(
            new_source["id"],
            claim=idea["claim"],
            original_market_scope="Liquide US-Aktien, Tagesdaten",
        )
    with pytest.raises(ValueError, match="Derselbe Claim existiert bereits"):
        workflow.create_hypothesis_from_claim(
            captured["id"],
            title="Unzulässiges Duplikat",
            area="swing_trader",
            category="Momentum",
            mechanism="Gleicher Mechanismus.",
            external_evidence="strong",
            rating="C",
            risks_limitations="Wie zuvor.",
            strategy="Long Pullback",
            asset_class="Aktien",
            market_region="USA",
            market_universe="Liquide US-Aktien",
            market_timeframe="Daily",
        )


def test_unmatched_claim_creates_one_hypothesis_and_records_own_scope(tmp_path: Path) -> None:
    path = tmp_path / "new-claim.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    new_source = add_source(kb, "Gap-Studie")
    captured = workflow.capture_source_claim(
        new_source["id"],
        claim="Overnight-Gaps mit bestätigender Auktion zeigen höhere fünftägige MFE.",
        original_market_scope="DAX-Aktien, Xetra-Eröffnungsauktion",
    )

    assert captured["matches"] == []
    created = workflow.create_hypothesis_from_claim(
        captured["id"],
        title="Bestätigte Overnight-Gaps",
        area="swing_trader",
        category="Gap",
        mechanism="Auktionsvolumen bestätigt institutionelle Nachfrage.",
        external_evidence="weak",
        rating="B",
        risks_limitations="Nur Xetra, kleine Stichprobe, Gap-Kosten.",
        strategy="Gap Continuation",
        asset_class="Aktien",
        market_region="Deutschland",
        market_universe="DAX und MDAX mit Xetra-Auktion",
        market_timeframe="Daily / fünf Sitzungen",
    )

    workflow_state = workflow.workflow_for_hypothesis(created["id"])
    assert workflow_state["source_claims"][0]["resolution"] == "CREATED_HYPOTHESIS"
    assert workflow_state["market_scopes"][0]["asset_class"] == "Aktien"
    assert workflow_state["market_scopes"][0]["region"] == "Deutschland"
    assert kb.get_hypothesis(created["id"])["sources"][0]["id"] == new_source["id"]


def test_application_assessment_uses_fixed_outcomes_and_existing_assets(tmp_path: Path) -> None:
    path = tmp_path / "capability.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    idea = add_hypothesis(kb)
    existing_test = add_experiment(kb, idea["id"])

    assessment = workflow.record_application_assessment(
        idea["id"],
        outcome="TESTABLE_NOW",
        feature_available=True,
        required_data_available=True,
        existing_research_test=True,
        market_scope_reviewed=True,
        active_rule_exists=False,
        infrastructure_needed="Keine neue Infrastruktur; bestehende PIT-Daten verwenden.",
        existing_assets={
            "feature": "volume_ratio_20",
            "database": "runtime/swing_broad_research.sqlite3",
            "experiment_id": existing_test["id"],
        },
        rationale="Feature, Daten und Baseline-Test sind bereits vorhanden.",
        experiment_id=existing_test["id"],
    )

    assert assessment["outcome"] == "TESTABLE_NOW"
    assert assessment["existing_assets"]["feature"] == "volume_ratio_20"
    assert assessment["active_rule_exists"] == 0
    assert kb.get_hypothesis(idea["id"])["current_status"] == "RAW"
    assert kb.get_hypothesis(idea["id"])["ledger"][-1]["event_type"] == "application_capability_assessed"

    with pytest.raises(ValueError, match="verfügbare Daten"):
        workflow.record_application_assessment(
            idea["id"],
            outcome="TESTABLE_NOW",
            feature_available=False,
            required_data_available=False,
            existing_research_test=False,
            market_scope_reviewed=False,
            active_rule_exists=False,
            infrastructure_needed="Unbekannt",
            existing_assets={},
            rationale="Widersprüchliche Einstufung.",
        )


def test_cross_market_transfer_is_a_new_unvalidated_hypothesis(tmp_path: Path) -> None:
    path = tmp_path / "cross-market.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    fx_idea = add_hypothesis(
        kb,
        claim="Volumenimpulse nach Pullbacks verbessern die FX-Trendfortsetzung.",
        asset_class="FX",
    )
    fx_test = add_experiment(kb, fx_idea["id"], title="FX-Test")
    add_result(kb, fx_test["id"], title="FX Walk-Forward", conclusion="supports")
    kb.change_hypothesis_status(fx_idea["id"], "VALIDATED", reason="Eigene FX-Validierung.")

    equity_idea = workflow.create_cross_market_hypothesis(
        fx_idea["id"],
        title="Volumenimpulse bei Aktien-Pullbacks",
        claim="Volumenimpulse nach Pullbacks verbessern die Aktien-Trendfortsetzung.",
        target_asset_class="Aktien",
        target_region="USA",
        target_universe="Liquide US-Aktien",
        target_timeframe="Daily / 20 Sitzungen",
        mechanism="Börsenvolumen kann Nachfrage anders abbilden als FX-Tickvolumen.",
        category="Momentum",
        area="swing_trader",
        external_evidence="weak",
        rating="B",
        risks_limitations="FX-Evidenz ist nicht auf Aktien übertragbar.",
        strategy="Long Pullback",
        material_difference="Andere Assetklasse, andere Volumendefinition und eigener Market Scope.",
    )

    assert equity_idea["id"] != fx_idea["id"]
    assert equity_idea["current_status"] == "RAW"
    assert equity_idea["experiments"] == []
    assert equity_idea["relations"][0]["other_id"] == fx_idea["id"]
    assert workflow.workflow_for_hypothesis(equity_idea["id"])["market_scopes"][0]["asset_class"] == "Aktien"


def test_integration_candidate_never_changes_strategy_and_approval_requires_every_gate(tmp_path: Path) -> None:
    path = tmp_path / "integration.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    idea = add_hypothesis(kb)
    own_test = add_experiment(kb, idea["id"])
    incomplete_result = add_result(kb, own_test["id"], title="Positiver Research-Stand", conclusion="supports")
    complete_result = add_result(kb, own_test["id"], title="Bestätigter Research-Stand", conclusion="supports")
    negative_result = add_result(kb, own_test["id"], title="Negative Variante", conclusion="negative")

    with pytest.raises(sqlite3.IntegrityError, match="supporting result"):
        workflow.create_integration_candidate(
            idea["id"],
            negative_result["id"],
            **candidate_arguments(all_gates=True),
        )
    with pytest.raises(ValueError, match="höchstens 5"):
        workflow.create_integration_candidate(
            idea["id"],
            incomplete_result["id"],
            **{
                **candidate_arguments(all_gates=False),
                "feature_combination": [f"feature_{index}" for index in range(6)],
            },
        )

    incomplete = workflow.create_integration_candidate(
        idea["id"],
        incomplete_result["id"],
        **candidate_arguments(all_gates=False),
    )
    with pytest.raises(sqlite3.IntegrityError, match="all research and simplicity gates"):
        workflow.record_integration_decision(
            incomplete["id"],
            decision="APPROVED_FOR_IMPLEMENTATION",
            rationale="Unzulässige vorschnelle Freigabe.",
            decided_by="manual-review",
        )
    research_decision = workflow.record_integration_decision(
        incomplete["id"],
        decision="MORE_RESEARCH_REQUIRED",
        rationale="Forward-/Paper-Bestätigung noch nicht ausreichend.",
        decided_by="manual-review",
    )
    with pytest.raises(sqlite3.IntegrityError, match="approved matching decision"):
        workflow.record_integration_event(
            incomplete["id"],
            research_decision["id"],
            event_type="INTEGRATED",
            implementation_reference="git:not-allowed",
            summary="Darf nicht als integriert markiert werden.",
        )

    complete = workflow.create_integration_candidate(
        idea["id"],
        complete_result["id"],
        **candidate_arguments(all_gates=True),
    )
    approval = workflow.record_integration_decision(
        complete["id"],
        decision="APPROVED_FOR_IMPLEMENTATION",
        rationale="Alle unabhängigen Research- und Einfachheits-Gates manuell geprüft.",
        decided_by="manual-review",
    )
    integrated = workflow.record_integration_event(
        complete["id"],
        approval["id"],
        event_type="INTEGRATED",
        implementation_reference="git:example-reviewed-change",
        summary="Eine separat geprüfte externe Codeänderung wurde dokumentiert.",
    )

    assert incomplete["candidate_status"] == "INTEGRATION_CANDIDATE"
    assert integrated["event_type"] == "INTEGRATED"
    assert kb.get_hypothesis(idea["id"])["current_status"] == "RAW"
    state = workflow.workflow_for_hypothesis(idea["id"])
    assert state["automatic_strategy_integration"] is False
    assert len(state["integration_candidates"]) == 2
    assert state["integration_candidates"][1]["events"][0]["implementation_reference"] == "git:example-reviewed-change"
    assert workflow.summary()["integration_events"] == 1


def test_workflow_decisions_are_append_only(tmp_path: Path) -> None:
    path = tmp_path / "workflow-append-only.sqlite3"
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    source = add_source(kb, "Neue Quelle")
    claim = workflow.capture_source_claim(
        source["id"],
        claim="Ein neutraler Claim ohne ausreichenden Research-Nutzen.",
        original_market_scope="Unklar",
    )
    workflow.resolve_claim_without_research(
        claim["id"],
        resolution="NO_ACTION",
        rationale="Kein konkreter, testbarer Zusatznutzen.",
    )
    intake_rows = workflow.list_source_claims()
    assert intake_rows[0]["latest_resolution"] == "NO_ACTION"
    assert intake_rows[0]["resolved_hypothesis_id"] is None

    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="source_claims is append-only"):
            connection.execute("UPDATE source_claims SET claim_text = 'anders' WHERE id = ?", (claim["id"],))
        with pytest.raises(sqlite3.IntegrityError, match="source_claim_resolutions is append-only"):
            connection.execute("DELETE FROM source_claim_resolutions WHERE claim_id = ?", (claim["id"],))


def test_schema_two_migrates_workflow_and_preserves_initial_evidence(tmp_path: Path) -> None:
    path = tmp_path / "schema-two.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_MIGRATIONS[1])
        connection.executescript(SCHEMA_MIGRATIONS[2])
        connection.execute(
            """
            INSERT INTO hypotheses (
                id, title, area, category, claim, normalized_claim, claim_fingerprint,
                mechanism, external_evidence, rating, current_status, risks_limitations,
                strategy, asset_class, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-hypothesis",
                "Bestehende Hypothese",
                "investment",
                "Quality",
                "Bestehender Claim bleibt erhalten.",
                "bestehender claim bleibt erhalten",
                "legacy-fingerprint",
                "Bestehender Mechanismus.",
                "medium",
                "B",
                "WATCH",
                "Bestehende Einschränkung.",
                "Quality Investment",
                "Aktien",
                "2026-08-01T08:00:00+00:00",
                "2026-08-01T08:00:00+00:00",
            ),
        )
        connection.execute("PRAGMA user_version = 2")

    initialize_database(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'source_claims'"
        ).fetchone() == ("source_claims",)
        assert connection.execute(
            """
            SELECT strength, confidence, rationale
            FROM hypothesis_evidence_assessments
            WHERE hypothesis_id = 'legacy-hypothesis'
            """
        ).fetchone() == (
            "medium",
            None,
            "Initiale Evidenzeinstufung aus dem bestehenden Hypotheseneintrag.",
        )
