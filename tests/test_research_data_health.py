from __future__ import annotations

import sqlite3
from pathlib import Path

from research_data_health import (
    CANONICAL_STATUSES,
    audit_research_data_health,
    render_gap_markdown,
    render_health_markdown,
)


STAMP = "2026-09-23T09:00:00+00:00"


def _task(name: str) -> dict[str, object]:
    return {
        "task_name": name,
        "state": "Ready",
        "enabled": True,
        "last_run_time": "2026-09-22T22:30:00+02:00",
        "next_run_time": "2026-09-23T22:30:00+02:00",
        "last_task_result": 0,
        "start_when_available": True,
        "multiple_instances": "IgnoreNew",
    }


def test_audit_is_read_only_and_uses_only_canonical_family_statuses(tmp_path: Path) -> None:
    root = tmp_path / "project"
    result_a = audit_research_data_health(root, as_of=STAMP)
    result_b = audit_research_data_health(root, as_of=STAMP)
    assert not (root / "runtime").exists()
    assert result_a == result_b
    assert [item["family_id"] for item in result_a["families"]] == list("ABCDEFGHIJKLM")
    assert {item["status"] for item in result_a["families"]} <= CANONICAL_STATUSES
    assert result_a["new_challengers_created"] == 0
    assert result_a["validation_opened"] is False
    assert result_a["holdout_opened"] is False
    assert result_a["final_status"] == "RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA"


def test_fx_duplicate_alarm_and_reports_are_reproducible(tmp_path: Path) -> None:
    root = tmp_path / "project"
    runtime = root / "runtime"
    runtime.mkdir(parents=True)
    path = runtime / "fx_forward_pit.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE collector_runs(started_at TEXT);
            CREATE TABLE observations(
                status TEXT, source_timestamp TEXT, first_seen_at TEXT, observation_key TEXT
            );
            CREATE TABLE source_health(consecutive_failures INTEGER);
            CREATE TABLE expectations(id TEXT);
            CREATE TABLE macro_events(id TEXT);
            CREATE TABLE central_bank_events(id TEXT);
            CREATE TABLE quote_observations(id TEXT);
            INSERT INTO collector_runs VALUES ('2026-09-22T19:45:00+00:00');
            INSERT INTO observations VALUES ('OBSERVED','2026-09-22T00:00:00+00:00','2026-09-22T19:45:00+00:00','same');
            INSERT INTO observations VALUES ('OBSERVED','2026-09-22T00:00:00+00:00','2026-09-22T19:45:00+00:00','same');
            INSERT INTO source_health VALUES (0);
            """
        )
    tasks = [
        _task("InvestmentAssistant-FX-PIT-Observer"),
        _task("InvestmentAssistantDailyForecasts"),
    ]
    result = audit_research_data_health(
        root, as_of=STAMP, scheduler_tasks=tasks, scheduler_query_status="SUCCESS"
    )
    assert any(alert["rule"] == "duplicate_observations" for alert in result["alerts"])
    health = render_health_markdown(result)
    gaps = render_gap_markdown(result)
    assert "RESEARCH_DATA_HEALTH_AND_COVERAGE" in health
    assert "DATA_COLLECTION_GAP_REPORT" in gaps
    assert result["report_fingerprint"] in health
    assert "No technical negative claim was retested" in gaps
