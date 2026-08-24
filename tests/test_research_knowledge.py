from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research_knowledge import CURRENT_SCHEMA_VERSION, ResearchKnowledgeBase, initialize_database
from research_knowledge.schema import SCHEMA_MIGRATIONS
from research_knowledge.ui import hypothesis_table_rows


def source(kb: ResearchKnowledgeBase, title: str, source_type: str = "paper") -> dict:
    return kb.create_source(
        title=title,
        source_type=source_type,
        reference=f"https://example.test/{title.casefold().replace(' ', '-')}",
        source_date="2026-08-20",
        summary=f"Neutrale Zusammenfassung für {title}.",
        created_at="2026-08-20T08:00:00+00:00",
    )


def hypothesis(kb: ResearchKnowledgeBase, *, status: str = "RAW") -> dict:
    return kb.create_hypothesis(
        title="Volumenbestätigung nach Pullback",
        area="swing_trader",
        category="Momentum",
        claim="Ein Volumenanstieg nach einem Pullback verbessert die 20-Tage-Expectancy.",
        mechanism="Neue Nachfrage bestätigt die Trendfortsetzung.",
        external_evidence="medium",
        rating="B",
        risks_limitations="Sektorcluster und Survivorship Bias.",
        status=status,
        strategy="Long Pullback",
        asset_class="Aktien",
        creation_reason="Externe Idee strukturiert erfasst.",
        created_at="2026-08-20T09:00:00+00:00",
    )


def experiment(kb: ResearchKnowledgeBase, hypothesis_id: str, *, title: str = "PIT Pullback-Test") -> dict:
    return kb.create_experiment(
        hypothesis_id,
        title=title,
        test_definition="Vergleiche Signale mit und ohne Volumenbestätigung.",
        features=["volume_ratio_20", "pullback_depth", "atr_14", "volume_ratio_20"],
        data_universe="Historisches US-Aktienuniversum mit delisteten Titeln.",
        period_start="2016-01-01",
        period_end="2025-12-31",
        point_in_time_rules="Features enden am Signal-Cutoff; zeitliche Splits; keine Zukunftsdaten.",
        baseline="Ungefiltertes Long-Pullback-Signal.",
        parameters={"volume_ratio": [1.0, 1.2, 1.5]},
        test_status="PLANNED",
        created_at="2026-08-20T10:00:00+00:00",
    )


def result(kb: ResearchKnowledgeBase, experiment_id: str, *, conclusion: str = "negative") -> dict:
    return kb.record_result(
        experiment_id,
        title="Chronologischer Holdout",
        conclusion=conclusion,
        sample_size=842,
        hit_rate=48.3,
        expectancy=-0.08,
        profit_factor=0.94,
        mfe=1.1,
        mae=-1.3,
        drawdown=12.4,
        r_multiples=-0.08,
        costs=0.12,
        slippage=0.07,
        in_sample={"expectancy": 0.21},
        validation={"expectancy": 0.03},
        out_of_sample={"expectancy": -0.08},
        walk_forward={"folds": 6, "positive_folds": 2},
        forward=None,
        papertrade=None,
        interpretation="Der Effekt verschwindet außerhalb der Entwicklung und nach Kosten.",
        recorded_at="2026-08-21T10:00:00+00:00",
    )


def test_source_hypothesis_experiment_result_persist_with_full_ledger(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(path)
    supporting = source(kb, "Volumenstudie")
    contradicting = source(kb, "Replikationsstudie", "study")
    idea = hypothesis(kb)

    kb.link_source(
        idea["id"],
        supporting["id"],
        stance="supports",
        note="Plausibler Mechanismus, aber fremdes Universum.",
        linked_at="2026-08-20T09:10:00+00:00",
    )
    kb.link_source(
        idea["id"],
        contradicting["id"],
        stance="contradicts",
        note="Keine robuste Out-of-Sample-Wirkung.",
        linked_at="2026-08-20T09:20:00+00:00",
    )
    kb.record_external_review(
        idea["id"],
        summary="Methodik beider Quellen geprüft; eigene Validierung bleibt nötig.",
        outcome="mixed",
        reviewed_at="2026-08-20T09:30:00+00:00",
    )
    test = experiment(kb, idea["id"])
    second_test = experiment(kb, idea["id"], title="Alternative Universumsdefinition")
    kb.add_external_reference(
        target_type="experiment",
        target_id=test["id"],
        system="swing_broad_research",
        record_type="challenger_review",
        record_id="review-2026-08-21-v1",
        uri="runtime/swing_broad_research.sqlite3#review-2026-08-21-v1",
        description="Bestehendes PIT-Research wird nur referenziert.",
        created_at="2026-08-20T10:10:00+00:00",
    )
    kb.change_hypothesis_status(
        idea["id"],
        "TESTING",
        reason="PIT-Testdefinition freigegeben.",
        changed_at="2026-08-20T11:00:00+00:00",
    )
    kb.change_experiment_status(
        test["id"],
        "RUNNING",
        reason="Chronologischer Lauf gestartet.",
        changed_at="2026-08-20T12:00:00+00:00",
    )
    negative = result(kb, test["id"])
    kb.change_experiment_status(
        test["id"],
        "COMPLETED",
        reason="Alle festgelegten Splits abgeschlossen.",
        changed_at="2026-08-21T10:05:00+00:00",
    )
    kb.change_hypothesis_status(
        idea["id"],
        "REJECTED",
        reason="Negativer Holdout und instabile Walk-Forward-Folds nach Kosten.",
        changed_at="2026-08-21T10:10:00+00:00",
    )

    reopened = ResearchKnowledgeBase(path)
    detail = reopened.get_hypothesis(idea["id"])

    assert len(detail["sources"]) == 2
    assert {item["stance"] for item in detail["sources"]} == {"supports", "contradicts"}
    assert len(detail["experiments"]) == 2
    stored_test = next(item for item in detail["experiments"] if item["id"] == test["id"])
    assert stored_test["features"] == ["atr_14", "pullback_depth", "volume_ratio_20"]
    assert stored_test["parameters"] == {"volume_ratio": [1.0, 1.2, 1.5]}
    assert stored_test["references"][0]["record_id"] == "review-2026-08-21-v1"
    assert stored_test["results"][0]["out_of_sample"] == {"expectancy": -0.08}
    assert stored_test["results"][0]["id"] == negative["id"]
    assert detail["current_status"] == "REJECTED"
    assert [item["to_status"] for item in detail["status_history"]] == ["RAW", "TESTING", "REJECTED"]
    assert [item["event_at"] for item in detail["ledger"]] == sorted(
        item["event_at"] for item in detail["ledger"]
    )
    assert {item["event_type"] for item in detail["ledger"]} >= {
        "hypothesis_created",
        "source_linked",
        "external_review",
        "experiment_defined",
        "external_reference_linked",
        "experiment_status_changed",
        "result_recorded",
        "status_changed",
    }
    assert reopened.health() == {
        "status": "ok",
        "quick_check": "ok",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "current_schema_version": CURRENT_SCHEMA_VERSION,
        "sources": 2,
        "hypotheses": 1,
        "experiments": 2,
        "results": 1,
        "ledger_events": len(detail["ledger"]),
    }


def test_validated_is_blocked_until_an_experiment_result_exists(tmp_path: Path) -> None:
    kb = ResearchKnowledgeBase(tmp_path / "validation.sqlite3")
    idea = hypothesis(kb)
    external = source(kb, "Starke externe Metaanalyse")
    kb.link_source(idea["id"], external["id"], stance="supports")

    with pytest.raises(sqlite3.IntegrityError, match="VALIDATED requires an internal experiment result"):
        kb.change_hypothesis_status(
            idea["id"],
            "VALIDATED",
            reason="Nur externe Quelle.",
        )

    assert kb.get_hypothesis(idea["id"])["current_status"] == "RAW"
    own_test = experiment(kb, idea["id"])
    result(kb, own_test["id"], conclusion="supports")
    changed = kb.change_hypothesis_status(
        idea["id"],
        "VALIDATED",
        reason="Eigenes PIT-Ergebnis liegt zusätzlich zur externen Evidenz vor.",
    )

    assert changed["current_status"] == "VALIDATED"


def test_rejected_hypotheses_remain_searchable_and_retest_requires_new_basis(tmp_path: Path) -> None:
    kb = ResearchKnowledgeBase(tmp_path / "negative-memory.sqlite3")
    idea = hypothesis(kb)
    own_test = experiment(kb, idea["id"])
    result(kb, own_test["id"])
    kb.change_hypothesis_status(
        idea["id"],
        "REJECTED",
        reason="Kein stabiler Nettoeffekt im Holdout.",
    )

    similar = kb.find_similar_hypotheses(
        title="Pullback mit Volumen",
        claim="Ein Volumenanstieg nach einem Pullback verbessert die 20-Tage-Expectancy.",
    )
    assert similar[0]["id"] == idea["id"]
    assert similar[0]["exact_claim_match"] is True
    assert similar[0]["rejection_reason"] == "Kein stabiler Nettoeffekt im Holdout."
    assert similar[0]["result_summaries"][0]["conclusion"] == "negative"

    with pytest.raises(ValueError, match="Grund für erneuten Test"):
        kb.change_hypothesis_status(
            idea["id"],
            "TESTING",
            reason="Noch einmal testen.",
        )

    with sqlite3.connect(kb.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="retesting REJECTED requires"):
            connection.execute(
                "UPDATE hypotheses SET current_status = 'TESTING' WHERE id = ?",
                (idea["id"],),
            )

    kb.change_hypothesis_status(
        idea["id"],
        "TESTING",
        reason="Neues survivorship-bias-freies Universum verfügbar.",
        retest_basis="new_data",
    )
    historically_rejected = kb.search_hypotheses(status="REJECTED")
    assert [item["id"] for item in historically_rejected] == [idea["id"]]
    assert historically_rejected[0]["current_status"] == "TESTING"
    assert historically_rejected[0]["was_rejected"] == 1
    assert kb.get_hypothesis(idea["id"])["status_history"][-1]["retest_basis"] == "new_data"


def test_search_covers_category_feature_strategy_asset_source_status_and_rating(tmp_path: Path) -> None:
    kb = ResearchKnowledgeBase(tmp_path / "search.sqlite3")
    idea = hypothesis(kb)
    linked_source = source(kb, "Volumen Paper")
    kb.link_source(idea["id"], linked_source["id"], stance="supports")
    experiment(kb, idea["id"])

    filters = (
        {"query": "Trendfortsetzung"},
        {"category": "moment"},
        {"feature": "volume_ratio"},
        {"strategy": "pullback"},
        {"asset_class": "akt"},
        {"source": "Volumen Paper"},
        {"status": "RAW"},
        {"rating": "B"},
        {"area": "swing_trader"},
    )
    for selected in filters:
        assert [item["id"] for item in kb.search_hypotheses(**selected)] == [idea["id"]]

    values = kb.filter_values()
    assert values == {
        "categories": ["Momentum"],
        "strategies": ["Long Pullback"],
        "asset_classes": ["Aktien"],
        "features": ["atr_14", "pullback_depth", "volume_ratio_20"],
    }


def test_history_results_and_rejected_knowledge_are_append_only(tmp_path: Path) -> None:
    path = tmp_path / "append-only.sqlite3"
    kb = ResearchKnowledgeBase(path)
    idea = hypothesis(kb)
    own_test = experiment(kb, idea["id"])
    stored_result = result(kb, own_test["id"])
    kb.change_hypothesis_status(idea["id"], "REJECTED", reason="Negatives Ergebnis.")

    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="evidence_ledger is append-only"):
            connection.execute("DELETE FROM evidence_ledger WHERE hypothesis_id = ?", (idea["id"],))
        with pytest.raises(sqlite3.IntegrityError, match="research_results is append-only"):
            connection.execute(
                "UPDATE research_results SET interpretation = 'überschrieben' WHERE id = ?",
                (stored_result["id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="hypotheses cannot be deleted"):
            connection.execute("DELETE FROM hypotheses WHERE id = ?", (idea["id"],))


def test_direct_status_change_is_still_audited_by_database_trigger(tmp_path: Path) -> None:
    path = tmp_path / "direct-status.sqlite3"
    kb = ResearchKnowledgeBase(path)
    idea = hypothesis(kb)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE hypotheses SET current_status = 'WATCH' WHERE id = ?",
            (idea["id"],),
        )

    detail = kb.get_hypothesis(idea["id"])
    assert detail["current_status"] == "WATCH"
    assert detail["status_history"][-1]["from_status"] == "RAW"
    assert detail["status_history"][-1]["to_status"] == "WATCH"
    assert detail["status_history"][-1]["reason"] == "Direkte Statusänderung ohne Repository-Kontext"
    assert detail["ledger"][-1]["event_type"] == "status_changed"


def test_schema_migrates_forward_and_rejects_unknown_future_version(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(legacy_path) as connection:
        connection.executescript(SCHEMA_MIGRATIONS[1])
        connection.execute("PRAGMA user_version = 1")

    initialize_database(legacy_path)
    with sqlite3.connect(legacy_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'external_references'"
        ).fetchone() == ("external_references",)

    future_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(future_path) as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError, match="neueren App-Version"):
        initialize_database(future_path)


def test_related_hypotheses_and_ui_rows_expose_negative_history(tmp_path: Path) -> None:
    kb = ResearchKnowledgeBase(tmp_path / "relations.sqlite3")
    original = hypothesis(kb)
    revision = kb.create_hypothesis(
        title="Volumenbestätigung mit Regimefilter",
        area="swing_trader",
        category="Momentum",
        claim="Volumenbestätigung wirkt nur in liquiden Bullenmarkt-Regimen.",
        mechanism="Regimefilter reduziert falsche Nachfrageimpulse.",
        external_evidence="weak",
        rating="B",
        risks_limitations="Kleine Regimestichprobe und multiple Tests.",
        strategy="Long Pullback",
        asset_class="Aktien",
    )
    kb.link_hypotheses(
        revision["id"],
        original["id"],
        relation_type="extends",
        note="Materiell engerer Claim statt stiller Überschreibung.",
    )
    kb.change_hypothesis_status(original["id"], "REJECTED", reason="Frühere breite Variante verworfen.")

    relations = kb.get_hypothesis(original["id"])["relations"]
    assert relations[0]["other_id"] == revision["id"]
    assert relations[0]["relation_type"] == "extends"
    rows = hypothesis_table_rows(kb.search_hypotheses())
    original_row = next(item for item in rows if item["Titel"] == original["title"])
    assert original_row["Früher verworfen"] == "Ja"
    assert original_row["Negative Ergebnisse"] == 0
