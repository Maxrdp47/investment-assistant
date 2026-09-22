from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from multi_asset_discovery_v1 import fingerprint
from research_knowledge import ResearchKnowledgeBase
from scripts.sync_multi_asset_v2_r6_kb import sync


def _write_verified(path: Path, payload: dict[str, object]) -> None:
    payload = dict(payload)
    payload["artifact_fingerprint"] = fingerprint(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_r6_kb_sync_is_idempotent_and_labels_archival_timing(tmp_path: Path) -> None:
    kb_path = tmp_path / "kb.sqlite3"
    ResearchKnowledgeBase(kb_path)
    audit = tmp_path / "audit.json"
    report = tmp_path / "report.json"
    summary = tmp_path / "summary.json"
    manifest = tmp_path / "manifest.json"
    contract = tmp_path / "contract.json"
    _write_verified(audit, {"status": "PASS"})
    _write_verified(
        report,
        {
            "status": "R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE",
            "robust_candidate_count": 0,
            "cases_reviewed": 100,
            "feature_count": 1,
            "candidate_gate_reason": "DEPENDENCIES_FAIL",
        },
    )
    _write_verified(summary, {"status": "R6_COMPLETE_NO_ROBUST_CANDIDATES_R7_NOT_OPENED"})
    _write_verified(
        manifest,
        {
            "program_id": "finite-research-program-2026-09-15-v1",
            "run_id": "run-1",
            "development_contract_fingerprint": "r5",
            "review_contract_fingerprint": "review",
            "run_manifest_fingerprint": "manifest",
        },
    )
    contract.write_text(
        json.dumps({"continuous_features": [{"name": "core.return_20"}]}),
        encoding="utf-8",
    )
    arguments = {
        "kb_path": kb_path,
        "audit_path": audit,
        "report_path": report,
        "summary_path": summary,
        "manifest_path": manifest,
        "review_contract_path": contract,
    }
    first = sync(**arguments)
    second = sync(**arguments)
    assert first["result_id"] == second["result_id"]
    assert first["hypothesis_status"] == "REJECTED"
    assert first["result_conclusion"] == "inconclusive"
    assert second["idempotent_replay"] is True
    with sqlite3.connect(kb_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM research_results").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM external_references").fetchone()[0] == 4
        parameters = json.loads(
            connection.execute("SELECT parameters_json FROM experiments").fetchone()[0]
        )
        assert parameters["archival_catalog_created_after_result"] is True
