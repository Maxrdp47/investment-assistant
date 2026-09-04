from __future__ import annotations

import json
from pathlib import Path

from multi_asset_development_post_run_readiness import (
    RUN_ID,
    build_post_run_readiness_report,
)
from multi_asset_discovery_v1 import fingerprint


def _artifact(path: Path, payload: dict[str, object]) -> Path:
    payload["artifact_fingerprint"] = fingerprint(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_readiness_requires_all_six_gates_and_recommends_full_versioned_run(
    tmp_path: Path,
) -> None:
    terminal = _artifact(
        tmp_path / "terminal.json",
        {
            "runtime_status": "COMPLETED_WITH_FAILURES",
            "terminal_work_units": 60_504,
            "work_completed_at": "2026-09-02T23:44:03+00:00",
        },
    )
    projection = _artifact(
        tmp_path / "projection.json",
        {
            "active_envelope_anomaly_count": 0,
            "active_non_positive_ohlc_count": 0,
            "original_frozen_dataset_changed": False,
            "counts": {"raw_bars": 10, "active_valid_bars": 9, "invalid_source_bars": 1},
            "dataset_fingerprint": "new",
        },
    )
    structural = _artifact(
        tmp_path / "structural.json",
        {
            "classification_complete": True,
            "total_structural_r_na": 209_492,
            "legitimate_na_count": 0,
            "non_positive_risk_count": 209_492,
            "technical_bug_count": 0,
        },
    )
    failed = _artifact(
        tmp_path / "failed.json",
        {
            "classification_complete": True,
            "failed_work_units": 4_704,
            "unresolved_count": 0,
            "legitimate_skip_count": 4_608,
            "source_data_failure_count": 96,
            "technical_pipeline_bug_count": 0,
        },
    )
    audit = _artifact(
        tmp_path / "audit.json",
        {
            "status": "PASS",
            "set_summary": {"feature_rows": 2_564_825, "outcome_rows": 2_564_825},
            "case_id_set_equality": True,
            "payload_issue_count": 0,
            "sqlite_integrity_ok": True,
        },
    )
    truth = (
        f"{RUN_ID} COMPLETED_WITH_FAILURES 60.504 2026-09-03 01:44:03 CEST "
        "NEW_VERSIONED_FULL_DEVELOPMENT_RUN_REQUIRED"
    )
    status = tmp_path / "PROJECT_STATUS.md"
    roadmap = tmp_path / "ROADMAP.md"
    status.write_text(truth, encoding="utf-8")
    roadmap.write_text(truth, encoding="utf-8")
    result = build_post_run_readiness_report(
        created_at="2026-09-03T20:00:00+00:00",
        scheduler_state="Disabled",
        fx_observer_state="Ready",
        project_status=status,
        roadmap=roadmap,
        terminal_path=terminal,
        projection_path=projection,
        structural_path=structural,
        failed_path=failed,
        store_audit_path=audit,
        artifact_path=tmp_path / "readiness.json",
    )
    assert all(item["status"] == "PASS" for item in result["areas"].values())
    assert result["reprocessing_recommendation"] == "NEW_VERSIONED_FULL_DEVELOPMENT_RUN_REQUIRED"
    assert result["technical_status"] == "DEVELOPMENT_V5_POST_RUN_INTEGRITY_READY_FOR_REPROCESSING_REVIEW"
    assert result["large_reprocessing_run_started"] is False


def test_readiness_fails_closed_when_store_audit_fails(tmp_path: Path) -> None:
    truth = (
        f"{RUN_ID} COMPLETED_WITH_FAILURES 60.504 2026-09-03 01:44:03 CEST "
        "NEW_VERSIONED_FULL_DEVELOPMENT_RUN_REQUIRED"
    )
    status = tmp_path / "PROJECT_STATUS.md"
    roadmap = tmp_path / "ROADMAP.md"
    status.write_text(truth, encoding="utf-8")
    roadmap.write_text(truth, encoding="utf-8")
    common = {
        "terminal": {"runtime_status": "COMPLETED_WITH_FAILURES", "terminal_work_units": 60_504},
        "projection": {"active_envelope_anomaly_count": 0, "active_non_positive_ohlc_count": 0, "original_frozen_dataset_changed": False},
        "structural": {"classification_complete": True, "total_structural_r_na": 209_492},
        "failed": {"classification_complete": True, "failed_work_units": 4_704, "unresolved_count": 0},
        "audit": {"status": "FAIL"},
    }
    paths = {name: _artifact(tmp_path / f"{name}.json", value) for name, value in common.items()}
    result = build_post_run_readiness_report(
        scheduler_state="Disabled",
        fx_observer_state="Ready",
        project_status=status,
        roadmap=roadmap,
        terminal_path=paths["terminal"],
        projection_path=paths["projection"],
        structural_path=paths["structural"],
        failed_path=paths["failed"],
        store_audit_path=paths["audit"],
        artifact_path=tmp_path / "readiness.json",
    )
    assert result["reprocessing_recommendation"] == "NOT_READY_FOR_REPROCESSING"
    assert result["technical_status"] == "DEVELOPMENT_V5_POST_RUN_INTEGRITY_NOT_READY"
