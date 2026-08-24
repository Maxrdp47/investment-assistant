from __future__ import annotations

from pathlib import Path

from research_knowledge import ResearchKnowledgeBase
from scripts.migrate_research_legacy_inventory import reconcile_legacy_inventory


def test_a_to_o_reconciliation_is_repeatable_and_ids_remain_stable(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    first = reconcile_legacy_inventory(path)
    kb = ResearchKnowledgeBase(path)
    source_ids = {item["candidate"]: item["source_id"] for item in first["candidates"]}
    hypothesis_ids = {
        item["candidate"]: tuple(item["hypothesis_ids"])
        for item in first["candidates"]
    }
    before_second = dict(first["after"])

    second = reconcile_legacy_inventory(path)

    assert second["before"] == before_second
    assert second["after"] == before_second
    assert {item["candidate"] for item in second["candidates"]} == set("ABCDEFGHIJKLMNO")
    assert all(item["idempotent_replay"] is True for item in second["candidates"])
    assert {item["candidate"]: item["source_id"] for item in second["candidates"]} == source_ids
    assert {
        item["candidate"]: tuple(item["hypothesis_ids"])
        for item in second["candidates"]
    } == hypothesis_ids
    assert second["legacy_backlog_complete"] == "UNKNOWN"
    assert kb.health()["quick_check"] == "ok"


def test_existing_rejected_history_survives_legacy_reconciliation(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite3"
    kb = ResearchKnowledgeBase(path)
    idea = kb.create_hypothesis(
        title="Unabhängige verworfene Hypothese",
        area="swing_trader",
        category="Negative Memory",
        claim="Eine unabhängige Idee besitzt keinen robusten Nettoeffekt.",
        mechanism="Unbewiesener Mechanismus.",
        external_evidence="weak",
        rating="B",
        risks_limitations="Negatives Ergebnis dauerhaft erhalten.",
    )
    kb.change_hypothesis_status(idea["id"], "REJECTED", reason="Negativer Holdout.")
    history_before = kb.get_hypothesis(idea["id"])["status_history"]

    reconcile_legacy_inventory(path)

    detail = kb.get_hypothesis(idea["id"])
    assert detail["current_status"] == "REJECTED"
    assert detail["status_history"] == history_before
