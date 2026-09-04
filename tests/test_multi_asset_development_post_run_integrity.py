from __future__ import annotations

import sqlite3
import zlib
from pathlib import Path

import pytest

from multi_asset_development_post_run_integrity import (
    RUN_ID,
    audit_case_payload_pair,
    build_terminal_truth_artifact,
    build_full_store_audit,
    classify_failed_work_unit,
    classify_structural_r_case,
    terminal_truth_report,
)
from multi_asset_discovery_v1 import canonical_json, fingerprint


def _feature(
    *, zone_c: dict[str, object], atr: float | None = 2.0,
    zone_a_status: str = "UNAVAILABLE", zone_b_status: str = "UNAVAILABLE",
) -> dict[str, object]:
    return {
        "case_id": "case",
        "asset_id": "asset",
        "listing_id": "listing",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "features": {
            "atr_14": (
                {"status": "AVAILABLE", "value": atr}
                if atr is not None
                else {"status": "UNAVAILABLE", "value": None}
            )
        },
        "safe_zones": {
            "A": {"status": zone_a_status},
            "B": {"status": zone_b_status},
            "C": zone_c,
        },
    }


def test_structural_r_classifier_keeps_legitimate_missing_zone_as_na() -> None:
    result = classify_structural_r_case(
        _feature(
            zone_c={
                "model": "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
                "status": "UNAVAILABLE",
                "reason": "STRUCTURE_OR_ATR_UNAVAILABLE",
            }
        ),
        next_open=12.0,
    )
    assert result["classification"] == "SAFE_ZONE_NOT_AVAILABLE"
    assert result["technical_bug"] is False
    assert result["structural_risk"] is None
    assert result["forced_safe_zone_created"] is False


def test_structural_r_classifier_separates_non_positive_risk() -> None:
    result = classify_structural_r_case(
        _feature(zone_c={"model": "C", "status": "AVAILABLE", "lower": 10.0}),
        next_open=9.5,
    )
    assert result["classification"] == "NON_POSITIVE_STRUCTURAL_RISK"
    assert result["structural_risk"] == -0.5
    assert result["r_independent_outcomes_reprocessable"] is True


def test_structural_r_classifier_detects_missing_derived_zone_bug() -> None:
    result = classify_structural_r_case(
        _feature(
            zone_c={"model": "C", "status": "UNAVAILABLE", "reason": "missing"},
            zone_a_status="AVAILABLE",
        ),
        next_open=12.0,
    )
    assert result["classification"] == "IMPLEMENTATION_BUG_SAFE_ZONE_C_NOT_DERIVED"
    assert result["technical_bug"] is True


def test_structural_r_classifier_separates_missing_atr() -> None:
    result = classify_structural_r_case(
        _feature(
            zone_c={"model": "C", "status": "AVAILABLE", "lower": 10.0},
            atr=None,
        ),
        next_open=12.0,
    )
    assert result["classification"] == "MATHEMATICALLY_UNDEFINED_ATR"
    assert result["technical_bug"] is False


def test_terminal_truth_preserves_last_work_unit_time_not_later_audit(
    tmp_path: Path,
) -> None:
    control = tmp_path / "control.sqlite3"
    with sqlite3.connect(control) as connection:
        connection.executescript(
            """
            CREATE TABLE runs(
                run_id TEXT,status TEXT,started_at TEXT,completed_at TEXT,
                last_checkpoint_at TEXT,total_planned_work_units INTEGER
            );
            CREATE TABLE work_units(
                run_id TEXT,status TEXT,completed_at TEXT
            );
            CREATE TABLE run_events(
                run_id TEXT,event_type TEXT,event_at TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?)",
            (
                RUN_ID,
                "COMPLETED_WITH_FAILURES",
                "2026-09-02T14:22:39+00:00",
                "2026-09-03T12:30:23+00:00",
                "2026-09-03T12:30:23+00:00",
                2,
            ),
        )
        connection.executemany(
            "INSERT INTO work_units VALUES (?,?,?)",
            [
                (RUN_ID, "COMPLETED", "2026-09-02T23:44:02+00:00"),
                (RUN_ID, "FAILED", None),
            ],
        )
        connection.execute(
            "INSERT INTO run_events VALUES (?,?,?)",
            (RUN_ID, "RUN_COMPLETED", "2026-09-02T23:44:04+00:00"),
        )

    result = terminal_truth_report(
        control_path=control, created_at="2026-09-03T13:00:00+00:00"
    )

    assert result["runtime_status"] == "COMPLETED_WITH_FAILURES"
    assert result["work_completed_at"] == "2026-09-02T23:44:02+00:00"
    assert result["run_terminal_at"] == "2026-09-02T23:44:04+00:00"
    assert result["legacy_overwritten_completed_at"] == "2026-09-03T12:30:23+00:00"
    assert result["legacy_timestamp_mutated"] is True


def test_terminal_truth_artifact_is_append_only_across_later_checks(
    tmp_path: Path,
) -> None:
    control = tmp_path / "control.sqlite3"
    artifact = tmp_path / "terminal.json"
    with sqlite3.connect(control) as connection:
        connection.executescript(
            """
            CREATE TABLE runs(run_id TEXT,status TEXT,started_at TEXT,completed_at TEXT,
              last_checkpoint_at TEXT,total_planned_work_units INTEGER);
            CREATE TABLE work_units(run_id TEXT,status TEXT,completed_at TEXT);
            CREATE TABLE run_events(run_id TEXT,event_type TEXT,event_at TEXT);
            """
        )
        connection.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?)",
            (RUN_ID, "COMPLETED_WITH_FAILURES", "start", "later", "later", 1),
        )
        connection.execute(
            "INSERT INTO work_units VALUES (?,?,?)",
            (RUN_ID, "FAILED", "terminal"),
        )
    first = build_terminal_truth_artifact(
        control_path=control, artifact_path=artifact, created_at="first-check"
    )
    second = build_terminal_truth_artifact(
        control_path=control, artifact_path=artifact, created_at="second-check"
    )
    assert first == second
    assert second["last_audited_at"] == "first-check"


def _failed_unit(message: str) -> dict[str, object]:
    return {
        "work_unit_id": "unit",
        "run_id": RUN_ID,
        "asset_key": "EQUITIES:TEST",
        "asset_class": "EQUITIES",
        "symbol": "TEST",
        "period_start": "2016-01-01",
        "period_end": "2016-03-31",
        "status": "FAILED",
        "attempts": 3,
        "last_error_class": "MultiAssetDevelopmentExecutionError",
        "last_error_message": message,
    }


def test_failed_unit_without_development_coverage_becomes_future_skip() -> None:
    result = classify_failed_work_unit(
        _failed_unit("Keine Development-Balken für EQUITIES:TEST."),
        source_manifest_entry={
            "first_day": "2022-01-03",
            "last_day": "2026-08-14",
            "history_fingerprint": "source",
        },
        source_bar_failures=[],
    )
    assert result["classification"] == "LEGITIMATE_SKIP_NO_DEVELOPMENT_COVERAGE"
    assert result["future_disposition"] == "SKIPPED"
    assert result["future_retryable"] is False
    assert result["work_plan_coverage_issue"] == "COVERAGE_BOUNDS_NOT_APPLIED_TO_WORK_PLAN"


def test_failed_unit_with_preserved_non_positive_bar_is_source_failure() -> None:
    result = classify_failed_work_unit(
        _failed_unit("OHLC muss positiv sein."),
        source_manifest_entry={"first_day": "2016-01-04", "last_day": "2026-08-14"},
        source_bar_failures=[{"source_bar_fingerprint": "bad-bar"}],
    )
    assert result["classification"] == "SOURCE_DATA_FAILURE_NON_POSITIVE_OHLC"
    assert result["future_disposition"] == "FAILED"
    assert result["future_retryable"] is False
    assert result["technical_pipeline_bug"] is False


def test_case_pair_audit_accepts_deterministic_pit_lineage() -> None:
    identity = {
        "asset_id": "asset",
        "signal_day": "2020-01-02",
        "contract_version": "contract",
        "dataset_fingerprint": "dataset",
    }
    case_id = f"mad1-{fingerprint(identity)[:32]}"
    feature = {
        "case_id": case_id,
        "asset_id": "asset",
        "listing_id": "listing",
        "issuer_id": "issuer",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "contract_version": "contract",
        "dataset_fingerprint": "dataset",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
        "decision_time": "2020-01-02T23:59:59+00:00",
        "known_at_lte_decision_time": True,
        "history_end_day": "2020-01-02",
        "features": {
            "rsi_14": {
                "status": "AVAILABLE",
                "value": 50.0,
                "known_at": "2020-01-02T23:59:59+00:00",
            }
        },
        "candidate_selected_from_outcome": False,
        "predictive_prefilter_used": False,
        "full_development_scan_started": False,
    }
    feature["feature_fingerprint"] = fingerprint(feature)
    outcome = {
        "contract_version": "contract",
        "case_id": case_id,
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": "asset",
        "listing_id": "listing",
        "issuer_id": "issuer",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
        "status": "COMPLETE",
        "future_features_written_to_feature_store": False,
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    feature_columns = {
        "case_id": case_id,
        "feature_fingerprint": feature["feature_fingerprint"],
        "run_id": RUN_ID,
        "work_unit_id": "unit",
        "asset_id": "asset",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
    }
    outcome_columns = {
        **feature_columns,
        "outcome_fingerprint": outcome["outcome_fingerprint"],
        "feature_fingerprint": feature["feature_fingerprint"],
        "status": "COMPLETE",
    }
    work_unit = {
        "run_id": RUN_ID,
        "asset_class": "EQUITIES",
        "symbol": "TEST",
        "period_start": "2020-01-01",
        "period_end": "2020-03-31",
        "status": "COMPLETED",
    }
    assert not audit_case_payload_pair(
        feature_columns,
        outcome_columns,
        feature,
        outcome,
        work_unit=work_unit,
    )


def test_case_pair_audit_rejects_future_known_at_and_orphan() -> None:
    feature = {
        "case_id": "bad",
        "asset_id": "asset",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "contract_version": "contract",
        "dataset_fingerprint": "dataset",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
        "decision_time": "2020-01-02T23:59:59+00:00",
        "known_at_lte_decision_time": True,
        "history_end_day": "2020-01-02",
        "features": {"event": {"known_at": "2020-01-03T00:00:00+00:00"}},
        "candidate_selected_from_outcome": False,
        "predictive_prefilter_used": False,
    }
    feature["feature_fingerprint"] = fingerprint(feature)
    outcome = {
        "contract_version": "contract",
        "case_id": "bad",
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": "asset",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
        "status": "COMPLETE",
        "future_features_written_to_feature_store": False,
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    shared = {
        "case_id": "bad",
        "feature_fingerprint": feature["feature_fingerprint"],
        "run_id": RUN_ID,
        "work_unit_id": "missing",
        "asset_id": "asset",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
    }
    issues = audit_case_payload_pair(
        shared,
        {**shared, "outcome_fingerprint": outcome["outcome_fingerprint"], "status": "COMPLETE"},
        feature,
        outcome,
        work_unit=None,
    )
    assert issues["feature_known_at_after_decision"] == 1
    assert issues["orphan_work_unit_link"] == 1


def test_full_store_audit_checks_every_pair_and_is_resumable(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.sqlite3"
    outcome_path = tmp_path / "outcomes.sqlite3"
    control_path = tmp_path / "control.sqlite3"
    diagnostic_path = tmp_path / "diagnostic.sqlite3"
    artifact_path = tmp_path / "audit.json"
    for path, schema in (
        (
            feature_path,
            """
            CREATE TABLE store_metadata(metadata_fingerprint TEXT PRIMARY KEY,metadata_json TEXT);
            CREATE TABLE feature_rows(case_id TEXT PRIMARY KEY,feature_fingerprint TEXT,run_id TEXT,
              work_unit_id TEXT,asset_id TEXT,symbol TEXT,asset_class TEXT,signal_day TEXT,
              research_split TEXT,dependency_status TEXT,payload_zlib BLOB);
            CREATE TRIGGER feature_rows_no_update BEFORE UPDATE ON feature_rows BEGIN SELECT RAISE(ABORT,'append_only'); END;
            CREATE TRIGGER feature_rows_no_delete BEFORE DELETE ON feature_rows BEGIN SELECT RAISE(ABORT,'append_only'); END;
            """,
        ),
        (
            outcome_path,
            """
            CREATE TABLE store_metadata(metadata_fingerprint TEXT PRIMARY KEY,metadata_json TEXT);
            CREATE TABLE outcome_rows(case_id TEXT PRIMARY KEY,outcome_fingerprint TEXT,feature_fingerprint TEXT,
              run_id TEXT,work_unit_id TEXT,asset_id TEXT,symbol TEXT,asset_class TEXT,signal_day TEXT,
              research_split TEXT,status TEXT,dependency_status TEXT,payload_zlib BLOB);
            CREATE TRIGGER outcome_rows_no_update BEFORE UPDATE ON outcome_rows BEGIN SELECT RAISE(ABORT,'append_only'); END;
            CREATE TRIGGER outcome_rows_no_delete BEFORE DELETE ON outcome_rows BEGIN SELECT RAISE(ABORT,'append_only'); END;
            """,
        ),
        (
            control_path,
            """
            CREATE TABLE runs(run_id TEXT PRIMARY KEY,status TEXT,total_planned_work_units INTEGER,
              feature_rows INTEGER,outcome_rows INTEGER,invalid_cases INTEGER,censored_cases INTEGER,
              contract_fingerprint TEXT,universe_fingerprint TEXT,work_plan_fingerprint TEXT,
              run_manifest_fingerprint TEXT);
            CREATE TABLE work_units(work_unit_id TEXT PRIMARY KEY,run_id TEXT,asset_key TEXT,
              asset_class TEXT,symbol TEXT,period_start TEXT,period_end TEXT,status TEXT,attempts INTEGER,
              feature_rows INTEGER,outcome_rows INTEGER);
            """,
        ),
    ):
        with sqlite3.connect(path) as connection:
            connection.executescript(schema)
    identity = {
        "asset_id": "asset",
        "signal_day": "2020-01-02",
        "contract_version": "multi-asset-opportunity-discovery-development-2026.09.01-v5",
        "dataset_fingerprint": "dataset",
    }
    case_id = f"mad1-{fingerprint(identity)[:32]}"
    feature = {
        **identity,
        "case_id": case_id,
        "listing_id": "listing",
        "issuer_id": "issuer",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
        "decision_time": "2020-01-02T23:59:59+00:00",
        "known_at_lte_decision_time": True,
        "history_end_day": "2020-01-02",
        "features": {},
        "candidate_selected_from_outcome": False,
        "predictive_prefilter_used": False,
        "full_development_scan_started": False,
    }
    feature["feature_fingerprint"] = fingerprint(feature)
    outcome = {
        "contract_version": identity["contract_version"],
        "case_id": case_id,
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": "asset",
        "listing_id": "listing",
        "issuer_id": "issuer",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "signal_day": "2020-01-02",
        "research_split": "development",
        "dependency_status": "INDEPENDENT",
        "status": "COMPLETE",
        "future_features_written_to_feature_store": False,
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    with sqlite3.connect(feature_path) as connection:
        connection.execute(
            "INSERT INTO feature_rows VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                case_id, feature["feature_fingerprint"], RUN_ID, "unit", "asset",
                "TEST", "EQUITIES", "2020-01-02", "development", "INDEPENDENT",
                zlib.compress(canonical_json(feature).encode("utf-8")),
            ),
        )
    with sqlite3.connect(outcome_path) as connection:
        connection.execute(
            "INSERT INTO outcome_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                case_id, outcome["outcome_fingerprint"], feature["feature_fingerprint"],
                RUN_ID, "unit", "asset", "TEST", "EQUITIES", "2020-01-02",
                "development", "COMPLETE", "INDEPENDENT",
                zlib.compress(canonical_json(outcome).encode("utf-8")),
            ),
        )
    with sqlite3.connect(control_path) as connection:
        connection.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (RUN_ID, "COMPLETED_WITH_FAILURES", 1, 1, 1, 0, 0, "contract", "universe", "plan", "manifest"),
        )
        connection.execute(
            "INSERT INTO work_units VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("unit", RUN_ID, "EQUITIES:TEST", "EQUITIES", "TEST", "2020-01-01", "2020-03-31", "COMPLETED", 1, 1, 1),
        )

    result = build_full_store_audit(
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        diagnostic_path=diagnostic_path,
        artifact_path=artifact_path,
        created_at="2026-09-03T20:00:00+00:00",
        batch_size=1,
    )
    assert result["status"] == "PASS"
    assert result["audited_case_pairs"] == 1
    assert result["case_id_set_equality"] is True
    assert result["payload_issue_count"] == 0
    assert result["append_only_feature_outcome_triggers_ok"] is True
    assert build_full_store_audit(
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        diagnostic_path=diagnostic_path,
        artifact_path=artifact_path,
        created_at="later",
        batch_size=1,
    )["artifact_fingerprint"] == result["artifact_fingerprint"]
