from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import scripts.complete_multi_asset_prerequisites as prerequisites
from research_knowledge import ResearchKnowledgeBase, ResearchWorkflow


ROOT = Path(__file__).resolve().parents[1]


def _audit_sources(tmp_path: Path, monkeypatch: object) -> None:
    audit_json = tmp_path / "broad_audit.json"
    audit_markdown = tmp_path / "broad_audit.md"
    audit_json.write_text('{"status":"reviewed"}\n', encoding="utf-8")
    audit_markdown.write_text("# Reviewed Broad audit\n", encoding="utf-8")
    monkeypatch.setattr(prerequisites, "FIB_AUDIT_JSON", audit_json)
    monkeypatch.setattr(prerequisites, "FIB_AUDIT_MD", audit_markdown)


def _ready_request(workflow: ResearchWorkflow, *, suffix: str) -> str:
    knowledge = workflow.knowledge
    hypothesis = knowledge.create_hypothesis(
        title=f"Prerequisite {suffix}",
        area="swing_trader",
        category="pytest",
        claim=f"Prerequisite contract {suffix} is evaluated independently.",
        mechanism="The test fixture exercises only the work-request lifecycle.",
        external_evidence="weak",
        rating="C",
        risks_limitations="Synthetic lifecycle fixture; no market conclusion.",
        asset_class="MULTI_ASSET",
        created_at="2026-08-28T00:00:00+00:00",
    )
    experiment = knowledge.create_experiment(
        hypothesis["id"],
        title=f"Prerequisite experiment {suffix}",
        test_definition="Exercise the administrative completion channel.",
        features=[f"fixture_{suffix}"],
        data_universe="Synthetic lifecycle fixture only.",
        point_in_time_rules="No market data are loaded.",
        baseline="No trading baseline.",
        parameters={"fixture": True},
        test_status="DRAFT",
        created_at="2026-08-28T00:00:00+00:00",
    )
    assessment = workflow.record_application_assessment(
        hypothesis["id"],
        experiment_id=experiment["id"],
        outcome="TESTABLE_NOW",
        feature_available=True,
        required_data_available=True,
        existing_research_test=True,
        market_scope_reviewed=True,
        active_rule_exists=False,
        infrastructure_needed="Pytest lifecycle fixture",
        existing_assets={"test": "tests/test_complete_multi_asset_prerequisites.py"},
        rationale="The fixture deliberately avoids private runtime artifacts.",
        assessed_at="2026-08-28T00:00:00+00:00",
    )
    request = workflow.create_work_request(
        hypothesis["id"],
        capability_assessment_id=assessment["id"],
        experiment_id=experiment["id"],
        request_type="RESEARCH_TEST",
        task=f"Complete fixture prerequisite {suffix}.",
        expected_output="One idempotently linked result.",
        required_infrastructure="Temporary SQLite database.",
        scope={"fixture": suffix},
        safeguards={"no_scan": True},
        idempotency_key=f"pytest-prerequisite-{suffix}",
        created_at="2026-08-28T00:00:00+00:00",
    )
    return str(request["id"])


def _knowledge_fixture(path: Path, monkeypatch: object) -> dict[str, str]:
    knowledge = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    ids = {
        "fibonacci": _ready_request(workflow, suffix="fibonacci"),
        "fx": _ready_request(workflow, suffix="fx"),
        "failed_seller": _ready_request(workflow, suffix="failed-seller"),
        "gold": _ready_request(workflow, suffix="gold"),
        "water": _ready_request(workflow, suffix="water"),
    }
    monkeypatch.setattr(prerequisites, "FIBONACCI_REQUEST_ID", ids["fibonacci"])
    monkeypatch.setattr(prerequisites, "FX_CARRY_REQUEST_ID", ids["fx"])
    monkeypatch.setattr(prerequisites, "FAILED_SELLER_REQUEST_ID", ids["failed_seller"])
    monkeypatch.setattr(prerequisites, "GOLD_SILVER_REQUEST_ID", ids["gold"])
    monkeypatch.setattr(prerequisites, "WATER_REQUEST_ID", ids["water"])
    return ids


def _status(path: Path, request_id: str) -> tuple[str, str | None]:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT current_status, result_id FROM research_work_requests WHERE id=?",
            (request_id,),
        ).fetchone()
    assert row is not None
    return str(row[0]), None if row[1] is None else str(row[1])


def _failed_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "COMPLETED_DEVELOPMENT_ONLY",
                "run_id": "pytest-failed-seller-run",
                "multi_asset_scan_started": False,
                "result": {
                    "result_direction": "INCONCLUSIVE",
                    "valid_feature_n": 12,
                    "baseline": {
                        "hit_rate_pct": 50.0,
                        "expectancy_r": 0.0,
                        "profit_factor": 1.0,
                        "average_mfe_pct": 2.0,
                        "average_mae_pct": -1.0,
                    },
                    "variants": {},
                    "validation_opened": False,
                    "holdout_opened": False,
                    "strategy_activated": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_identity_and_fibonacci_contracts_are_explicit(
    tmp_path: Path, monkeypatch: object
) -> None:
    _audit_sources(tmp_path, monkeypatch)
    identity = prerequisites.build_identity_gate(created_at="2026-08-28T00:00:00+00:00")
    assert identity["issuer_resolution"]["unknown_assumed_independent"] is False
    assert identity["multi_asset_scan_started"] is False

    fibonacci = prerequisites.build_fibonacci_reuse(created_at="2026-08-28T00:00:00+00:00")
    assert fibonacci["new_research_run_started"] is False
    assert fibonacci["contract_identity"]["equal_width_controls"] == [
        [0.45, 0.618],
        [0.786, 0.954],
    ]
    assert fibonacci["existing_development_result"]["conclusion"] == (
        "INCONCLUSIVE_DEVELOPMENT_B_ONLY"
    )


def test_completion_is_idempotent_and_leaves_other_ready_requests_untouched(
    tmp_path: Path, monkeypatch: object
) -> None:
    kb = tmp_path / "research_knowledge.sqlite3"
    ids = _knowledge_fixture(kb, monkeypatch)
    _audit_sources(tmp_path, monkeypatch)
    report = tmp_path / "failed.json"
    _failed_report(report)
    export_root = tmp_path / "exports"
    fx_database = tmp_path / "fx.sqlite3"

    first = prerequisites.complete_all(
        knowledge_base=kb,
        export_root=export_root,
        fx_database=fx_database,
        failed_seller_report=report,
        completed_at="2026-08-28T00:00:00+00:00",
    )
    result_ids = {
        request_id: _status(kb, request_id)[1]
        for request_id in (ids["fibonacci"], ids["fx"], ids["failed_seller"])
    }
    second = prerequisites.complete_all(
        knowledge_base=kb,
        export_root=export_root,
        fx_database=fx_database,
        failed_seller_report=report,
        completed_at="2026-08-28T00:00:00+00:00",
    )

    assert first["multi_asset_scan_started"] is False
    assert second["multi_asset_scan_started"] is False
    assert second["idempotent_replay"] is True
    assert second["artifact_fingerprint"] == first["artifact_fingerprint"]
    for request_id, result_id in result_ids.items():
        assert _status(kb, request_id) == ("COMPLETED", result_id)
        with sqlite3.connect(kb) as connection:
            result_n = connection.execute(
                "SELECT COUNT(*) FROM research_result_identities WHERE idempotency_key=?",
                (f"work_request:{request_id}",),
            ).fetchone()[0]
            request_artifacts = connection.execute(
                "SELECT artifact_references_json FROM research_work_requests WHERE id=?",
                (request_id,),
            ).fetchone()[0]
        assert result_n == 1
        assert json.loads(request_artifacts)
    assert _status(kb, ids["gold"]) == ("READY", None)
    assert _status(kb, ids["water"]) == ("READY", None)
