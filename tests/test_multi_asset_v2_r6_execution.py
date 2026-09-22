from __future__ import annotations

import json
import sqlite3
import zlib
from pathlib import Path

import pandas as pd
import pytest

import multi_asset_v2_r6_execution as r6
from multi_asset_discovery_v1 import canonical_json, fingerprint


def _parent_stores(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    control = tmp_path / "parent_control.sqlite3"
    features = tmp_path / "parent_features.sqlite3"
    outcomes = tmp_path / "parent_outcomes.sqlite3"
    unit = {
        "work_unit_id": "parent-unit-1",
        "asset_key": "ETF:TEST",
        "asset_class": "ETF",
        "symbol": "TEST",
        "period_start": "2020-01-01",
        "period_end": "2020-03-31",
    }
    feature = {
        "case_id": "parent-case-1",
        "asset_id": "asset-test",
        "symbol": "TEST",
        "asset_class": "ETF",
        "signal_day": "2020-02-03",
        "dependency_status": "UNKNOWN",
    }
    feature["feature_fingerprint"] = fingerprint(feature)
    outcome = {
        "case_id": feature["case_id"],
        "feature_fingerprint": feature["feature_fingerprint"],
        "status": "CENSORED_AT_STAGE_BOUNDARY",
        "censoring_reason": "STAGE_BOUNDARY_BEFORE_REQUESTED_OBSERVATIONS",
        "measurement_status": "PARTIAL",
        "r_metrics_status": "AVAILABLE",
        "checkpoints": {
            "20": {"observations": 20, "end_day": "2020-03-02", "return_pct": 1.0},
            "60": {"observations": 60, "end_day": "2020-04-27", "return_pct": 2.0},
        },
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    feature_digest_rows = [(feature["case_id"], feature["feature_fingerprint"], None)]
    outcome_digest_rows = [
        (feature["case_id"], outcome["outcome_fingerprint"], feature["feature_fingerprint"])
    ]
    with sqlite3.connect(control) as connection:
        connection.executescript(
            "CREATE TABLE work_units(work_unit_id TEXT,run_id TEXT,status TEXT);"
            "CREATE TABLE unit_receipts(run_id TEXT,work_unit_id TEXT,feature_rows INTEGER,"
            "outcome_rows INTEGER,case_set_digest TEXT,feature_payload_digest TEXT,"
            "outcome_payload_digest TEXT);"
        )
        connection.execute(
            "INSERT INTO work_units VALUES (?,?,?)",
            (unit["work_unit_id"], r6.PARENT_RUN_ID, "COMPLETED"),
        )
        connection.execute(
            "INSERT INTO unit_receipts VALUES (?,?,?,?,?,?,?)",
            (
                r6.PARENT_RUN_ID,
                unit["work_unit_id"],
                1,
                1,
                fingerprint([feature["case_id"]]),
                fingerprint(feature_digest_rows),
                fingerprint(outcome_digest_rows),
            ),
        )
    with sqlite3.connect(features) as connection:
        connection.execute(
            "CREATE TABLE feature_rows(case_id TEXT,feature_fingerprint TEXT,run_id TEXT,"
            "work_unit_id TEXT,asset_id TEXT,symbol TEXT,asset_class TEXT,signal_day TEXT,"
            "dependency_status TEXT)"
        )
        connection.execute(
            "INSERT INTO feature_rows VALUES (?,?,?,?,?,?,?,?,?)",
            (
                feature["case_id"], feature["feature_fingerprint"], r6.PARENT_RUN_ID,
                unit["work_unit_id"], feature["asset_id"], feature["symbol"],
                feature["asset_class"], feature["signal_day"], feature["dependency_status"],
            ),
        )
    with sqlite3.connect(outcomes) as connection:
        connection.execute(
            "CREATE TABLE outcome_rows(case_id TEXT,outcome_fingerprint TEXT,"
            "feature_fingerprint TEXT,run_id TEXT,work_unit_id TEXT,asset_id TEXT,symbol TEXT,"
            "asset_class TEXT,signal_day TEXT,dependency_status TEXT,payload_zlib BLOB)"
        )
        connection.execute(
            "INSERT INTO outcome_rows VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                feature["case_id"], outcome["outcome_fingerprint"],
                feature["feature_fingerprint"], r6.PARENT_RUN_ID, unit["work_unit_id"],
                feature["asset_id"], feature["symbol"], feature["asset_class"],
                feature["signal_day"], feature["dependency_status"],
                zlib.compress(canonical_json(outcome).encode("utf-8")),
            ),
        )
    return control, features, outcomes, unit


def _enrichment() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "r4b_contract_fingerprint": ["f" * 64],
            "benchmark_known_date": ["2020-01-31"],
            "relative_momentum_20": [0.12],
            "relative_momentum_60": [float("nan")],
            "confirmed_structure_sequence": ["INSUFFICIENT_CONFIRMED_PIVOTS"],
            "sector_benchmark_status": ["UNAVAILABLE_NO_HISTORICAL_SECTOR_MAPPING"],
            "historical_region_status": ["UNVERIFIED_GLOBAL_FALLBACK_ONLY"],
            "strategy_filter_created": [False],
        },
        index=pd.DatetimeIndex(["2020-02-03"]),
    )


def test_r6_creates_deterministic_delta_and_horizon_specific_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, features, outcomes, unit = _parent_stores(tmp_path)
    monkeypatch.setattr(r6, "_r4b_enrichment", lambda *_: (_enrichment(), "f" * 64))

    first = r6.compute_r6_asset_batch(
        asset={"asset_key": "ETF:TEST", "asset_class": "ETF", "symbol": "TEST"},
        units=[unit],
        r5_contract_fingerprint="a" * 64,
        parent_control_store=control,
        parent_feature_store=features,
        parent_outcome_store=outcomes,
    )
    second = r6.compute_r6_asset_batch(
        asset={"asset_key": "ETF:TEST", "asset_class": "ETF", "symbol": "TEST"},
        units=[unit],
        r5_contract_fingerprint="a" * 64,
        parent_control_store=control,
        parent_feature_store=features,
        parent_outcome_store=outcomes,
    )

    assert first == second
    feature = first["unit_results"][0]["features"][0]
    outcome = first["unit_results"][0]["outcomes"][0]
    assert feature["parent_core_features"] == "IMMUTABLE_REFERENCE_NOT_COPIED"
    assert feature["feature_values"]["r4b.relative_momentum_20"] == pytest.approx(0.12)
    assert feature["missing_features"]["r4b.relative_momentum_60"]["status"] == "UNKNOWN"
    assert feature["missing_features"]["r4b.sector_benchmark_status"]["status"] == "UNAVAILABLE"
    assert outcome["outcome_values_copied"] is False
    assert outcome["checkpoint_availability"]["20"]["status"] == "AVAILABLE"
    assert outcome["checkpoint_availability"]["120"]["status"] == "CENSORED_OR_UNAVAILABLE"
    assert outcome["validation_opened"] is False
    assert outcome["holdout_opened"] is False


def test_r6_rejects_parent_payload_changed_behind_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, features, outcomes, unit = _parent_stores(tmp_path)
    monkeypatch.setattr(r6, "_r4b_enrichment", lambda *_: (_enrichment(), "f" * 64))
    with sqlite3.connect(outcomes) as connection:
        payload = {"case_id": "parent-case-1", "tampered": True}
        connection.execute(
            "UPDATE outcome_rows SET payload_zlib=?",
            (zlib.compress(canonical_json(payload).encode("utf-8")),),
        )
    with pytest.raises(r6.MultiAssetV2R6ExecutionError, match="payload invalid"):
        r6.compute_r6_asset_batch(
            asset={"asset_key": "ETF:TEST", "asset_class": "ETF", "symbol": "TEST"},
            units=[unit],
            r5_contract_fingerprint="a" * 64,
            parent_control_store=control,
            parent_feature_store=features,
            parent_outcome_store=outcomes,
        )
