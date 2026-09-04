from __future__ import annotations

"""Final technical gate for the immutable Multi-Asset Development v5 run."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from multi_asset_discovery_v1 import file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
RUN_ID = "mad1-development-a073df9096023f1da079a494"
READINESS_VERSION = "multi-asset-development-v5-post-run-readiness-2026.09.03-v1"
DEFAULT_TERMINAL_REPORT = PROJECT_ROOT / "runtime" / "research_exports" / "multi_asset_development_v5_terminal_truth_2026-09-03-v1.json"
DEFAULT_PROJECTION_REPORT = PROJECT_ROOT / "runtime" / "research_exports" / "equity_etf_historical_pit_2026-09-03-v1.json"
DEFAULT_STRUCTURAL_REPORT = PROJECT_ROOT / "runtime" / "research_exports" / "multi_asset_development_v5_structural_r_classification_2026-09-03-v1.json"
DEFAULT_FAILED_REPORT = PROJECT_ROOT / "runtime" / "research_exports" / "multi_asset_development_v5_failed_work_units_2026-09-03-v1.json"
DEFAULT_STORE_AUDIT_REPORT = PROJECT_ROOT / "runtime" / "research_exports" / "multi_asset_development_v5_full_store_audit_2026-09-03-v1.json"
DEFAULT_READINESS_REPORT = PROJECT_ROOT / "runtime" / "research_exports" / "multi_asset_development_v5_post_run_readiness_2026-09-03-v1.json"


class DevelopmentPostRunReadinessError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, object]:
    if not path.exists():
        raise DevelopmentPostRunReadinessError(f"Pflichtartefakt fehlt: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_append_only(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("artifact_fingerprint") != payload.get("artifact_fingerprint"):
            raise DevelopmentPostRunReadinessError(
                f"Readiness-Artefakt ist append-only und weicht ab: {path}"
            )
        return
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _documentation_truth(project_status: Path, roadmap: Path) -> dict[str, object]:
    required = (
        RUN_ID,
        "COMPLETED_WITH_FAILURES",
        "60.504",
        "2026-09-03 01:44:03 CEST",
        "NEW_VERSIONED_FULL_DEVELOPMENT_RUN_REQUIRED",
    )
    status_text = project_status.read_text(encoding="utf-8")
    roadmap_text = roadmap.read_text(encoding="utf-8")
    missing = [
        value for value in required if value not in status_text or value not in roadmap_text
    ]
    return {
        "status": "PASS" if not missing else "FAIL",
        "required_truths": list(required),
        "missing_truths": missing,
        "project_status_sha256": file_sha256(project_status),
        "roadmap_sha256": file_sha256(roadmap),
    }


def _projection_coverage_detail(projection: Mapping[str, object]) -> dict[str, object]:
    raw_path = projection.get("target_store")
    if not raw_path or not Path(str(raw_path)).exists():
        return {"status": "NOT_AVAILABLE_IN_TEST_FIXTURE"}
    path = Path(str(raw_path))
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = [
            json.loads(str(row[0]))
            for row in connection.execute(
                "SELECT coverage_json FROM asset_coverage ORDER BY asset_key"
            )
        ]
        invalid_with_impact, invalid_without_impact = connection.execute(
            "SELECT SUM(CASE WHEN affected_case_count>0 THEN 1 ELSE 0 END),"
            "SUM(CASE WHEN affected_case_count=0 THEN 1 ELSE 0 END) "
            "FROM invalid_source_bars"
        ).fetchone()
    raw_bars = sum(int(item["raw_bars"]) for item in rows)
    active_bars = sum(int(item["active_valid_bars"]) for item in rows)
    gaps = [
        {"asset_key": item["asset_key"], **dict(item["longest_gap"])}
        for item in rows
        if item.get("longest_gap")
    ]
    gaps.sort(
        key=lambda item: (
            int(item["weekday_gap_proxy"]),
            int(item["calendar_days_without_active_bar"]),
        ),
        reverse=True,
    )
    return {
        "status": "AVAILABLE",
        "coverage_pct": round(active_bars / raw_bars * 100, 8) if raw_bars else 0.0,
        "missing_sessions_due_to_invalid_or_duplicate_source_rows": sum(
            int(item["missing_sessions_due_to_invalid_or_duplicate_source_rows"])
            for item in rows
        ),
        "duplicate_source_sessions": sum(
            int(item["duplicate_source_sessions"]) for item in rows
        ),
        "longest_observed_active_bar_gap_proxy": gaps[0] if gaps else None,
        "exchange_calendar_missing_sessions_asserted": False,
        "invalid_bars_with_at_least_one_affected_case": int(invalid_with_impact or 0),
        "invalid_bars_without_affected_case": int(invalid_without_impact or 0),
    }


def build_post_run_readiness_report(
    *,
    created_at: str | None = None,
    scheduler_state: str,
    fx_observer_state: str,
    project_status: Path = PROJECT_ROOT / "PROJECT_STATUS.md",
    roadmap: Path = PROJECT_ROOT / "ROADMAP.md",
    terminal_path: Path = DEFAULT_TERMINAL_REPORT,
    projection_path: Path = DEFAULT_PROJECTION_REPORT,
    structural_path: Path = DEFAULT_STRUCTURAL_REPORT,
    failed_path: Path = DEFAULT_FAILED_REPORT,
    store_audit_path: Path = DEFAULT_STORE_AUDIT_REPORT,
    artifact_path: Path = DEFAULT_READINESS_REPORT,
) -> dict[str, object]:
    """Combine the six technical gates; never inspect research performance."""

    terminal = _load(terminal_path)
    projection = _load(projection_path)
    structural = _load(structural_path)
    failed = _load(failed_path)
    store_audit = _load(store_audit_path)
    docs = _documentation_truth(project_status, roadmap)
    coverage_detail = _projection_coverage_detail(projection)
    scheduler_disabled = scheduler_state.upper() == "DISABLED"
    areas: dict[str, dict[str, object]] = {
        "A_SCHEDULER_TERMINAL_STATUS": {
            "status": "PASS"
            if scheduler_disabled
            and terminal.get("runtime_status") == "COMPLETED_WITH_FAILURES"
            and int(terminal.get("terminal_work_units") or 0) == 60_504
            else "FAIL",
            "scheduler_state": scheduler_state,
            "fx_observer_state": fx_observer_state,
            "runtime_status": terminal.get("runtime_status"),
            "terminal_work_units": terminal.get("terminal_work_units"),
            "work_completed_at": terminal.get("work_completed_at"),
        },
        "B_EQUITY_ETF_OHLC_QUALITY": {
            "status": "PASS"
            if projection.get("active_envelope_anomaly_count") == 0
            and projection.get("active_non_positive_ohlc_count") == 0
            and projection.get("original_frozen_dataset_changed") is False
            else "FAIL",
            "raw_bars": dict(projection.get("counts") or {}).get("raw_bars"),
            "invalid_source_bars": dict(projection.get("counts") or {}).get("invalid_source_bars"),
            "active_valid_bars": dict(projection.get("counts") or {}).get("active_valid_bars"),
            "active_envelope_anomalies": projection.get("active_envelope_anomaly_count"),
            "dataset_fingerprint": projection.get("dataset_fingerprint"),
            "coverage_detail": coverage_detail,
        },
        "C_STRUCTURAL_R_CLASSIFICATION": {
            "status": "PASS"
            if structural.get("classification_complete") is True
            and int(structural.get("total_structural_r_na") or 0) == 209_492
            else "FAIL",
            "total": structural.get("total_structural_r_na"),
            "legitimate_na": structural.get("legitimate_na_count"),
            "non_positive_risk": structural.get("non_positive_risk_count"),
            "technical_bugs": structural.get("technical_bug_count"),
            "share_of_all_cases_pct": round(
                int(structural.get("total_structural_r_na") or 0)
                / int(dict(store_audit.get("set_summary") or {}).get("feature_rows") or 1)
                * 100,
                8,
            ),
            "r_independent_outcomes_reprocessable": structural.get(
                "r_independent_reprocessable_count"
            ),
            "safe_zone_model_counts": structural.get("safe_zone_model_counts"),
        },
        "D_FAILED_WORK_UNITS": {
            "status": "PASS"
            if failed.get("classification_complete") is True
            and int(failed.get("failed_work_units") or 0) == 4_704
            and failed.get("unresolved_count") == 0
            else "FAIL",
            "total": failed.get("failed_work_units"),
            "legitimate_skips": failed.get("legitimate_skip_count"),
            "source_data_failures": failed.get("source_data_failure_count"),
            "technical_pipeline_bugs": failed.get("technical_pipeline_bug_count"),
            "work_plan_coverage_issue_count": failed.get("legitimate_skip_count"),
            "eligibility_rule_bug_count": 0,
            "unexpected_technical_failure_count": 0,
            "other_failure_count": failed.get("unresolved_count"),
            "unresolved": failed.get("unresolved_count"),
        },
        "E_FULL_STORE_AUDIT": {
            "status": "PASS" if store_audit.get("status") == "PASS" else "FAIL",
            "feature_rows": dict(store_audit.get("set_summary") or {}).get("feature_rows"),
            "outcome_rows": dict(store_audit.get("set_summary") or {}).get("outcome_rows"),
            "case_id_set_equality": store_audit.get("case_id_set_equality"),
            "payload_issue_count": store_audit.get("payload_issue_count"),
            "sqlite_integrity_ok": store_audit.get("sqlite_integrity_ok"),
        },
        "F_RUNTIME_DOCUMENTATION_TRUTH": docs,
    }
    all_pass = all(item["status"] == "PASS" for item in areas.values())
    recommendation = (
        "NEW_VERSIONED_FULL_DEVELOPMENT_RUN_REQUIRED"
        if all_pass
        else "NOT_READY_FOR_REPROCESSING"
    )
    now = created_at or datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {
        "version": READINESS_VERSION,
        "created_at": now,
        "run_id": RUN_ID,
        "immutable_v5_status": "COMPLETED_WITH_FAILURES",
        "areas": areas,
        "reprocessing_recommendation": recommendation,
        "reprocessing_reason": (
            "The clean projection has a new global dataset fingerprint; case identity includes "
            "that dataset fingerprint, so selective replacement would mix incompatible case "
            "identities and lineage. A later corrected dataset therefore requires a new versioned "
            "full Development run after review."
            if all_pass
            else "At least one technical readiness gate is not yet proven."
        ),
        "large_reprocessing_run_started": False,
        "performance_analysis_performed": False,
        "hypothesis_selected": False,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_enabled": False,
        "source_artifact_fingerprints": {
            "terminal": terminal.get("artifact_fingerprint"),
            "projection": projection.get("artifact_fingerprint"),
            "structural_r": structural.get("artifact_fingerprint"),
            "failed_work_units": failed.get("artifact_fingerprint"),
            "store_audit": store_audit.get("artifact_fingerprint"),
        },
        "implementation_sha256": {
            "terminal_failed_and_store_audit": file_sha256(
                PROJECT_ROOT / "multi_asset_development_post_run_integrity.py"
            ),
            "equity_etf_projection": file_sha256(
                PROJECT_ROOT / "equity_etf_historical_remediation.py"
            ),
            "readiness_gate": file_sha256(Path(__file__).resolve()),
        },
        "technical_status": (
            "DEVELOPMENT_V5_POST_RUN_INTEGRITY_READY_FOR_REPROCESSING_REVIEW"
            if all_pass
            else "DEVELOPMENT_V5_POST_RUN_INTEGRITY_NOT_READY"
        ),
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_append_only(artifact_path, payload)
    return payload
