from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from research_knowledge import (
    KnowledgeExporter,
    ResearchKnowledgeBase,
    ResearchMediaTranscription,
    ResearchWorkflow,
)
from scripts.export_research_knowledge import _parser as export_parser, run_command


def _source(kb: ResearchKnowledgeBase, tmp_path: Path) -> tuple[dict, Path]:
    video = tmp_path / "mixed-video.mp4"
    video.write_bytes(b"one-global-mixed-domain-video")
    intake = kb.intake_source(
        title="Immobilien, Steuern und REITs",
        source_type="tiktok",
        summary="Gemischter Research-Input; Claims werden einzeln klassifiziert.",
        platform="tiktok",
        creator="Knowledge Creator",
        direct_url="https://www.tiktok.com/@knowledge/video/7123456789012345678",
        local_file=video,
        provenance="Zentraler Video-Inbox",
    )
    return intake, video


def _general_claim(
    workflow: ResearchWorkflow,
    source_id: str,
    *,
    claim: str,
    domain: str,
    secondary: tuple[str, ...] = (),
    subcategory: str | None = None,
    relevance: str = "NOT_TRADING_RELEVANT",
    approved: bool = False,
) -> dict:
    return workflow.capture_knowledge_claim(
        source_id,
        claim=claim,
        primary_domain=domain,
        secondary_domains=secondary,
        subcategory=subcategory,
        trading_relevance=relevance,
        trading_path_approved=approved,
        classification_rationale="Claim-Inhalt und vorgesehener Nutzungspfad einzeln geprüft.",
        original_market_scope=(
            "Deutsche und europäische börsennotierte Immobilienunternehmen"
            if relevance == "TRADING_RELEVANT" or approved
            else None
        ),
    )


def _create_trading_hypothesis(workflow: ResearchWorkflow, claim_id: str) -> dict:
    return workflow.create_hypothesis_from_claim(
        claim_id,
        title="REIT-Finanzierung und Aktienbewertung",
        area="investment",
        category="Real Estate Equities",
        mechanism="Finanzierungskosten können Cashflows und Bewertungsmultiplikatoren beeinflussen.",
        external_evidence="weak",
        rating="B",
        risks_limitations="Zinsregime, Jurisdiktion, Unternehmensheterogenität und kleine Stichprobe.",
        strategy="Long-Term Research",
        asset_class="EQUITIES",
        market_region="EU",
        market_universe="Börsennotierte europäische Immobilienunternehmen",
        market_timeframe="Quarterly",
    )


def test_one_source_can_hold_multiple_domains_without_duplicate_video(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, video = _source(kb, tmp_path)

    real_estate = _general_claim(
        workflow,
        intake["source_id"],
        claim="Eine niedrigere Beleihungsquote kann die Immobilienfinanzierung stabilisieren.",
        domain="IMMOBILIEN",
        secondary=("PERSONAL_FINANCE",),
        subcategory="Finanzierung",
    )
    tax = _general_claim(
        workflow,
        intake["source_id"],
        claim="Für deutsche Immobilien können zeitabhängige Abschreibungsregeln gelten.",
        domain="STEUERN",
        secondary=("IMMOBILIEN",),
        subcategory="Immobilien",
    )
    trading = _general_claim(
        workflow,
        intake["source_id"],
        claim="Finanzierungskosten können die Bewertung europäischer Immobilienaktien beeinflussen.",
        domain="TRADING_INVESTMENT",
        secondary=("IMMOBILIEN",),
        subcategory="REITs",
        relevance="TRADING_RELEVANT",
    )

    duplicate_intake = kb.intake_source(
        title="Anderer Uploadtitel",
        source_type="tiktok",
        summary="Dasselbe Video erneut.",
        platform="tiktok",
        direct_url="https://tiktok.com/video/7123456789012345678?utm_source=again",
        local_file=video,
        provenance="Erneuter domainübergreifender Upload",
    )
    repeated_claim = _general_claim(
        workflow,
        duplicate_intake["source_id"],
        claim=real_estate["claim_text"],
        domain="IMMOBILIEN",
        secondary=("PERSONAL_FINANCE",),
        subcategory="Finanzierung",
    )

    assert duplicate_intake["status"] == "DUPLICATE_SOURCE"
    assert duplicate_intake["source_id"] == intake["source_id"]
    assert repeated_claim["id"] == real_estate["id"]
    assert repeated_claim["duplicate_claim"] is True
    assert {item["latest_classification"]["primary_domain"] for item in (real_estate, tax, trading)} == {
        "IMMOBILIEN",
        "STEUERN",
        "TRADING_INVESTMENT",
    }
    assert real_estate["latest_classification"]["secondary_domains"] == ["PERSONAL_FINANCE"]
    assert len(workflow.list_source_claims()) == 3
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0] == 0


def test_non_trading_claim_is_blocked_from_trading_tables_at_api_and_database(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, _ = _source(kb, tmp_path)
    claim = _general_claim(
        workflow,
        intake["source_id"],
        claim="Ein langfristiger Mietvertrag kann die Planbarkeit einer Vermietung erhöhen.",
        domain="IMMOBILIEN",
        subcategory="Vermietung",
    )

    with pytest.raises(ValueError, match="Nicht-Trading-Claim"):
        _create_trading_hypothesis(workflow, claim["id"])
    standalone = kb.create_hypothesis(
        title="Unabhängige Trading-Hypothese",
        area="investment",
        category="Test",
        claim="Unabhängiger Trading-Claim.",
        mechanism="Nur für Trigger-Test.",
        external_evidence="weak",
        rating="B",
        risks_limitations="Nicht aus dem Immobilien-Claim abgeleitet.",
        asset_class="EQUITIES",
    )
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError, match="non-trading claim"):
            connection.execute(
                """
                INSERT INTO source_claim_resolutions (
                    id, claim_id, resolution, hypothesis_id, new_evidence_basis,
                    rationale, resolved_at
                ) VALUES ('blocked', ?, 'LINKED_EXISTING', ?, NULL, 'blocked', ?)
                """,
                (claim["id"], standalone["id"], "2026-08-24T12:00:00+00:00"),
            )
    assert len(kb.search_hypotheses()) == 1
    assert workflow.summary()["work_requests"] == 0


def test_trading_claim_from_mixed_source_can_enter_existing_workflow(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, _ = _source(kb, tmp_path)
    _general_claim(
        workflow,
        intake["source_id"],
        claim="Eine Immobilie kann langfristig vermietet werden.",
        domain="IMMOBILIEN",
    )
    trading = _general_claim(
        workflow,
        intake["source_id"],
        claim="Finanzierungskosten können die Bewertung europäischer Immobilienaktien beeinflussen.",
        domain="TRADING_INVESTMENT",
        secondary=("IMMOBILIEN",),
        relevance="TRADING_RELEVANT",
    )

    hypothesis = _create_trading_hypothesis(workflow, trading["id"])
    assert hypothesis["current_status"] == "RAW"
    assert hypothesis["sources"][0]["id"] == intake["source_id"]
    assert workflow.workflow_for_hypothesis(hypothesis["id"])["source_claims"][0]["id"] == trading["id"]
    assert len(workflow.list_source_claims()) == 2


def test_potential_trading_claim_requires_append_only_conscious_approval(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, _ = _source(kb, tmp_path)
    claim = _general_claim(
        workflow,
        intake["source_id"],
        claim="Regionale Mietdaten könnten möglicherweise Immobilienaktien kontextualisieren.",
        domain="IMMOBILIEN",
        secondary=("TRADING_INVESTMENT",),
        relevance="POTENTIALLY_TRADING_RELEVANT",
        approved=False,
    )
    with pytest.raises(ValueError, match="Nicht-Trading-Claim"):
        _create_trading_hypothesis(workflow, claim["id"])

    approved = workflow.classify_claim(
        claim["id"],
        primary_domain="IMMOBILIEN",
        secondary_domains=("TRADING_INVESTMENT",),
        subcategory="Bewertung",
        trading_relevance="POTENTIALLY_TRADING_RELEVANT",
        trading_path_approved=True,
        rationale="Bewusste Prüfung bestätigt einen klaren, testbaren Aktienbezug.",
    )
    hypothesis = _create_trading_hypothesis(workflow, claim["id"])

    assert len(approved["domain_assessments"]) == 2
    assert approved["domain_assessments"][0]["trading_path_approved"] == 0
    assert approved["latest_classification"]["trading_path_approved"] == 1
    assert hypothesis["current_status"] == "RAW"
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE claim_domain_assessments SET rationale = 'changed' WHERE claim_id = ?",
                (claim["id"],),
            )


def test_verification_keeps_jurisdiction_evidence_and_outdated_history(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, _ = _source(kb, tmp_path)
    claim = _general_claim(
        workflow,
        intake["source_id"],
        claim="Für deutsche Wohngebäude gilt unter bestimmten Voraussetzungen eine Abschreibung.",
        domain="STEUERN",
        secondary=("IMMOBILIEN",),
        subcategory="Immobilien",
    )
    supported = workflow.record_claim_verification(
        claim["id"],
        verification_state="PARTIALLY_SUPPORTED",
        evidence_strength="strong",
        confidence=82,
        rationale="Amtliche Quelle bestätigt die Regel nur für einen begrenzten Anwendungsfall.",
        limitations="Keine individuelle Steuerberatung; Voraussetzungen und Baujahr prüfen.",
        verifying_sources=(
            {
                "title": "Amtlicher Hinweis zur Gebäudeabschreibung",
                "url": "https://example.test/amtlich/afa",
                "publisher": "Finanzverwaltung",
                "published_date": "2026-01-15",
                "notes": "Primärquelle für den allgemeinen Rechtsstand.",
            },
        ),
        counter_evidence=(
            {
                "title": "Abweichender Sonderfall",
                "url": "https://example.test/sonderfall",
                "publisher": "Fachinformation",
                "notes": "Zeigt eine relevante Ausnahme.",
            },
        ),
        jurisdiction="DE",
        valid_from="2026-01-01",
        valid_as_of="2026-08-24",
        update_required=True,
    )
    repeated = workflow.record_claim_verification(
        claim["id"],
        verification_state="PARTIALLY_SUPPORTED",
        evidence_strength="strong",
        confidence=82,
        rationale="Amtliche Quelle bestätigt die Regel nur für einen begrenzten Anwendungsfall.",
        limitations="Keine individuelle Steuerberatung; Voraussetzungen und Baujahr prüfen.",
        verifying_sources=(
            {
                "title": "Amtlicher Hinweis zur Gebäudeabschreibung",
                "url": "https://example.test/amtlich/afa",
                "publisher": "Finanzverwaltung",
                "published_date": "2026-01-15",
                "notes": "Primärquelle für den allgemeinen Rechtsstand.",
            },
        ),
        counter_evidence=(
            {
                "title": "Abweichender Sonderfall",
                "url": "https://example.test/sonderfall",
                "publisher": "Fachinformation",
                "notes": "Zeigt eine relevante Ausnahme.",
            },
        ),
        jurisdiction="DE",
        valid_from="2026-01-01",
        valid_as_of="2026-08-24",
        update_required=True,
    )
    outdated = workflow.record_claim_verification(
        claim["id"],
        verification_state="OUTDATED",
        evidence_strength="weak",
        confidence=95,
        rationale="Der gespeicherte Datenstand wurde durch eine spätere Regeländerung überholt.",
        limitations="Historischer Stand bleibt nur zur Nachvollziehbarkeit erhalten.",
        jurisdiction="DE",
        valid_until="2026-12-31",
        valid_as_of="2027-01-10",
        update_required=True,
    )
    detail = workflow.get_source_claim(claim["id"])

    assert supported["id"] == repeated["id"]
    assert supported["jurisdiction"] == "DE"
    assert len(supported["verifying_sources"]) == 1
    assert len(supported["counter_evidence"]) == 1
    assert len(detail["verification_assessments"]) == 3  # initial + supported + outdated
    assert detail["latest_verification"]["id"] == outdated["id"]
    assert detail["latest_verification"]["verification_state"] == "OUTDATED"


def test_conflicting_claims_remain_separate_and_related(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, _ = _source(kb, tmp_path)
    first = _general_claim(
        workflow,
        intake["source_id"],
        claim="Eine hohe Tilgung verbessert immer die Immobilienrendite.",
        domain="IMMOBILIEN",
        subcategory="Finanzierung",
    )
    second = _general_claim(
        workflow,
        intake["source_id"],
        claim="Eine hohe Tilgung kann die laufende Eigenkapitalrendite reduzieren.",
        domain="IMMOBILIEN",
        subcategory="Finanzierung",
    )
    relation = workflow.relate_claims(
        first["id"],
        second["id"],
        relation_type="CONTRADICTS",
        rationale="Die pauschale erste Aussage wird durch Liquiditäts- und Leverage-Effekte begrenzt.",
    )

    assert first["id"] != second["id"]
    assert relation["relation_type"] == "CONTRADICTS"
    assert workflow.get_source_claim(first["id"])["knowledge_relations"][0]["related_claim_text"] == second["claim_text"]


def test_domain_export_is_read_only_filtered_and_byte_stable(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    workflow = ResearchWorkflow(database)
    intake, _ = _source(kb, tmp_path)
    real_estate = _general_claim(
        workflow,
        intake["source_id"],
        claim="Der Beleihungsauslauf beeinflusst Finanzierungskonditionen.",
        domain="IMMOBILIEN",
        secondary=("PERSONAL_FINANCE",),
        subcategory="Finanzierung",
    )
    tax = _general_claim(
        workflow,
        intake["source_id"],
        claim="Eine Immobiliensteuerregel benötigt einen aktuellen deutschen Rechtsstand.",
        domain="STEUERN",
        secondary=("IMMOBILIEN",),
        subcategory="Immobilien",
    )
    _general_claim(
        workflow,
        intake["source_id"],
        claim="Ein lokales Sprachmodell kann Dokumente klassifizieren.",
        domain="AI_TECH",
        subcategory="Automatisierung",
    )
    workflow.record_claim_verification(
        real_estate["id"],
        verification_state="SUPPORTED",
        evidence_strength="medium",
        confidence=74,
        rationale="Mehrere Finanzierungshinweise unterstützen den begrenzten Claim.",
        limitations="Konditionen hängen zusätzlich von Objekt, Bank und Bonität ab.",
        verifying_sources=(
            {"title": "Finanzierungsleitfaden", "url": "https://example.test/finanzierung"},
        ),
        valid_as_of="2026-08-24",
    )
    transcript = ResearchMediaTranscription(database).process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Vorhandenes vollständiges Transcript für alle Domains registriert.",
        existing_transcript_text="Immobilien-, Steuer- und Technikclaims aus derselben Source.",
        language="de",
    )
    exporter = KnowledgeExporter(database)
    before = database.read_bytes()
    first_json = exporter.export_json("IMMOBILIEN")
    second_json = exporter.export_json("IMMOBILIEN")
    verified_json = exporter.export_json("IMMOBILIEN", verified_only=True)
    after = database.read_bytes()
    payload = json.loads(first_json)
    verified_payload = json.loads(verified_json)

    assert first_json == second_json
    assert before == after
    assert {item["claim_id"] for item in payload["claims"]} == {real_estate["id"], tax["id"]}
    assert [item["claim_id"] for item in verified_payload["claims"]] == [real_estate["id"]]
    assert payload["claims"][0]["source_id"] == intake["source_id"]
    assert {
        item["transcript_reference"]["path"] for item in payload["claims"]
    } == {transcript["transcript_path"]}
    assert "experiments" not in first_json
    assert "research_results" not in first_json
    assert payload["export_fingerprint"]

    args = export_parser().parse_args(
        ["--database", str(database), "--domain", "IMMOBILIEN", "--format", "json"]
    )
    assert run_command(args) == first_json
