from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from research_knowledge.entry_handoff import import_handoff
from research_knowledge.workflow import ResearchWorkflow
from scripts.import_entry_handoff import run


def _package() -> dict:
    return {
        "schema_version": "trading_handoff_v1",
        "handoff_id": "handoff-techfeed5-001",
        "entry_source_id": "entry-source-techfeed5-001",
        "source_hash": "a" * 64,
        "title": "Techfeed5: Pullback-Filter",
        "platform": "youtube",
        "creator": "techfeed5",
        "url": "https://youtu.be/AbCdEf12345?si=share",
        "published_date": "2026-08-31",
        "neutral_summary": "Das Video beschreibt einen möglichen Volumenfilter für Pullbacks.",
        "claims": [
            {
                "origin_claim_id": "entry-claim-001",
                "claim_text": "Ein erhöhtes relatives Volumen verbessert Pullback-Fortsetzungen.",
                "video_timestamps": [{"start": "00:01:12", "end": "00:01:38"}],
                "claim_type": "strategy_feature",
                "trading_relevance": "TRADING_RELEVANT",
                "market_scope": "US-Aktien, Daily Swing",
                "verification_status": "MOSTLY_SUPPORTED",
                "evidence_strength": "medium",
                "confidence": 72,
                "rationale": "Mehrere unabhängige Quellen stützen die Richtung, aber nicht jede Parametrisierung.",
                "evidence": [
                    {
                        "title": "Volume and return continuation",
                        "url": "https://example.test/evidence",
                        "publisher": "Example Journal",
                        "published_date": "2025-03-01",
                        "notes": "Unterstützt die Richtung im untersuchten Scope.",
                    },
                    {
                        "title": "Volume and return continuation",
                        "url": "https://example.test/evidence",
                        "publisher": "Example Journal",
                        "published_date": "2025-03-01",
                        "notes": "Unterstützt die Richtung im untersuchten Scope.",
                    },
                ],
                "counter_evidence": [
                    {
                        "title": "Regime dependence of volume signals",
                        "url": "https://example.test/counter",
                        "publisher": "Research Archive",
                        "published_date": "2024-06-15",
                        "notes": "Effekt ist nicht in allen Regimen stabil.",
                    }
                ],
                "limitations": ["Kein Beleg für die konkrete Schwelle.", "Nur Daily-Daten."],
                "risks": ["Overfitting", "Regimewechsel"],
                "valid_as_of": "2026-09-01",
                "tags": ["Pullback", "Volume", "volume"],
                "suggested_hypothesis": {
                    "title": "Relatives Volumen als Pullback-Filter",
                    "area": "swing_trader",
                    "category": "Pullback",
                    "claim": "Relatives Volumen verbessert netto die Pullback-Baseline.",
                    "mechanism": "Zusätzliche Marktteilnahme kann die Fortsetzung bestätigen.",
                    "external_evidence": "medium",
                    "rating": "B",
                    "risks_limitations": "Overfitting, Kosten und Regimeabhängigkeit.",
                    "strategy": "Long Pullback",
                    "asset_class": "EQUITIES",
                },
                "suggested_test": {
                    "title": "Relatives-Volumen-PIT-Test",
                    "test_definition": "Inkrementeller Vergleich gegen die unveränderte Baseline.",
                    "data_universe": "Historisches Point-in-Time-US-Aktienuniversum.",
                    "period_start": "2016-01-01",
                    "period_end": "2025-12-31",
                    "point_in_time_rules": "Nur zum Entscheidungszeitpunkt bekannte Daten.",
                    "baseline": "Unveränderte Pullback-Baseline.",
                    "features": ["relative_volume", "pullback"],
                    "parameters": {"relative_volume": "to_be_preregistered"},
                },
            }
        ],
    }


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_valid_dry_run_does_not_create_or_change_database(tmp_path: Path) -> None:
    database = tmp_path / "dry-run.sqlite3"
    result = import_handoff(_package(), database_path=database, dry_run=True)

    assert result["status"] == "IMPORTED"
    assert result["dry_run"] is True
    assert not database.exists()


def test_real_import_maps_into_existing_research_structure(tmp_path: Path) -> None:
    database = tmp_path / "research.sqlite3"
    result = import_handoff(_package(), database_path=database)

    assert result["status"] == "IMPORTED"
    assert len(result["claim_ids"]) == 1
    assert len(result["hypothesis_ids"]) == 1
    assert len(result["experiment_ids"]) == 1
    listed = ResearchWorkflow(database).list_source_claims()
    assert listed[0]["origin_system"] == "ENTRY"
    assert listed[0]["empirical_test_status"] == "NOT_TESTED"
    assert listed[0]["research_status"] == "CANDIDATE"
    assert listed[0]["tags_text"] == "Pullback, Volume"
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        imported = connection.execute("SELECT * FROM entry_claim_imports").fetchone()
        assert imported["origin_system"] == "ENTRY"
        assert imported["origin_source_id"] == _package()["entry_source_id"]
        assert imported["source_hash"] == _package()["source_hash"]
        assert imported["source_verification_status"] == "MOSTLY_SUPPORTED"
        assert imported["empirical_test_status"] == "NOT_TESTED"
        assert imported["research_status"] == "CANDIDATE"
        assessment = connection.execute(
            "SELECT verification_state, valid_as_of FROM claim_verification_assessments "
            "WHERE id = ?",
            (result["verification_assessment_ids"][0],),
        ).fetchone()
        assert dict(assessment) == {
            "verification_state": "PARTIALLY_SUPPORTED",
            "valid_as_of": "2026-09-01",
        }
        experiment = connection.execute(
            "SELECT current_status FROM experiments WHERE id = ?",
            (result["experiment_ids"][0],),
        ).fetchone()
        assert experiment["current_status"] == "DRAFT"
        assert _count(connection, "research_results") == 0
        assert _count(connection, "research_work_requests") == 0
        assert _count(connection, "integration_candidates") == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_identical_package_twice_is_no_change_without_duplicates(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.sqlite3"
    first = import_handoff(_package(), database_path=database)
    with sqlite3.connect(database) as connection:
        before = {
            table: _count(connection, table)
            for table in (
                "research_sources",
                "source_claims",
                "claim_verification_assessments",
                "claim_verification_references",
                "source_claim_tags",
                "hypotheses",
                "experiments",
                "entry_handoff_imports",
            )
        }
    second = import_handoff(_package(), database_path=database)
    with sqlite3.connect(database) as connection:
        after = {table: _count(connection, table) for table in before}

    assert first["status"] == "IMPORTED"
    assert second["status"] == "NO_CHANGE"
    assert before == after


def test_changed_revision_is_append_only_update_and_reuses_same_candidate(tmp_path: Path) -> None:
    database = tmp_path / "updated.sqlite3"
    first = import_handoff(_package(), database_path=database)
    changed = copy.deepcopy(_package())
    changed["claims"][0]["confidence"] = 81
    changed["claims"][0]["rationale"] = "Aktualisierte Prüfung mit zusätzlicher Bestätigung."

    result = import_handoff(changed, database_path=database)

    assert result["status"] == "UPDATED"
    assert result["claim_ids"] == first["claim_ids"]
    assert result["hypothesis_ids"] == first["hypothesis_ids"]
    assert result["experiment_ids"] == first["experiment_ids"]
    with sqlite3.connect(database) as connection:
        assert _count(connection, "entry_handoff_imports") == 2
        assert _count(connection, "source_claims") == 1
        assert _count(connection, "hypotheses") == 1
        assert _count(connection, "experiments") == 1
        assert _count(connection, "claim_verification_assessments") == 2
        assert _count(connection, "source_claim_tags") == 2
        assert _count(connection, "claim_verification_references") == 4


def test_local_managed_change_creates_conflict_and_rolls_back_update(tmp_path: Path) -> None:
    database = tmp_path / "conflict.sqlite3"
    first = import_handoff(_package(), database_path=database)
    workflow = ResearchWorkflow(database)
    workflow.record_claim_verification(
        first["claim_ids"][0],
        verification_state="CONFLICTING_EVIDENCE",
        evidence_strength="medium",
        confidence=55,
        rationale="Lokale Gegenprüfung.",
        limitations="Lokale Ergänzung.",
        counter_evidence=[{"title": "Lokaler Gegenbeleg", "notes": "Manuell geprüft."}],
        valid_as_of="2026-09-02",
    )
    changed = copy.deepcopy(_package())
    changed["claims"][0]["confidence"] = 80

    result = import_handoff(changed, database_path=database)
    replay = import_handoff(changed, database_path=database)

    assert result["status"] == "CONFLICT"
    assert replay["status"] == "CONFLICT"
    assert replay["conflict_ids"] == result["conflict_ids"]
    assert result["conflict_ids"]
    with sqlite3.connect(database) as connection:
        assert _count(connection, "entry_handoff_imports") == 1
        assert _count(connection, "entry_handoff_conflicts") == 1
        assert _count(connection, "claim_verification_assessments") == 2


def test_invalid_schema_and_missing_required_field_have_clear_exit_code(tmp_path: Path) -> None:
    invalid_schema = _package()
    invalid_schema["schema_version"] = "trading_handoff_v2"
    missing = _package()
    del missing["claims"][0]["rationale"]
    invalid_path = tmp_path / "invalid.json"
    missing_path = tmp_path / "missing.json"
    invalid_path.write_text(json.dumps(invalid_schema), encoding="utf-8")
    missing_path.write_text(json.dumps(missing), encoding="utf-8")

    invalid_response, invalid_code = run(
        ["--input", str(invalid_path), "--database", str(tmp_path / "invalid.sqlite3"), "--json-output"]
    )
    missing_response, missing_code = run(
        ["--input", str(missing_path), "--database", str(tmp_path / "missing.sqlite3"), "--json-output"]
    )

    assert invalid_response["status"] == "REJECTED_INVALID"
    assert invalid_code == 2
    assert "Schema-Version" in str(invalid_response["reason"])
    assert missing_response["status"] == "REJECTED_INVALID"
    assert missing_code == 2
    assert "rationale" in str(missing_response["reason"])


def test_evidence_tags_and_all_new_relations_have_no_duplicates_or_orphans(tmp_path: Path) -> None:
    database = tmp_path / "relations.sqlite3"
    import_handoff(_package(), database_path=database)

    with sqlite3.connect(database) as connection:
        assert _count(connection, "claim_verification_references") == 2
        assert _count(connection, "source_claim_tags") == 2
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            """SELECT COUNT(*) FROM entry_claim_imports eci
               LEFT JOIN source_claims sc ON sc.id = eci.claim_id
               LEFT JOIN entry_handoff_imports ehi ON ehi.id = eci.handoff_import_id
               WHERE sc.id IS NULL OR ehi.id IS NULL"""
        ).fetchone()[0] == 0
        assert connection.execute(
            """SELECT COUNT(*) FROM claim_verification_references cvr
               LEFT JOIN claim_verification_assessments cva ON cva.id = cvr.assessment_id
               WHERE cva.id IS NULL"""
        ).fetchone()[0] == 0


def test_non_trading_claim_is_ignored_without_leaking_into_claim_table(tmp_path: Path) -> None:
    package = _package()
    ignored = copy.deepcopy(package["claims"][0])
    ignored["origin_claim_id"] = "entry-claim-non-trading"
    ignored["claim_text"] = "Eine allgemeine Produktivitätsaussage ohne Tradingbezug."
    ignored["trading_relevance"] = "NOT_TRADING_RELEVANT"
    package["claims"].append(ignored)

    database = tmp_path / "filtered.sqlite3"
    result = import_handoff(package, database_path=database)

    assert result["ignored_claim_ids"] == ["entry-claim-non-trading"]
    assert len(result["claim_ids"]) == 1
    with sqlite3.connect(database) as connection:
        stored = json.loads(
            connection.execute("SELECT payload_json FROM entry_handoff_imports").fetchone()[0]
        )
    assert any(
        item["origin_claim_id"] == "entry-claim-non-trading" for item in stored["claims"]
    )
