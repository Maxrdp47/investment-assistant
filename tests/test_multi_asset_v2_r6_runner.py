from __future__ import annotations

import os
from pathlib import Path

from multi_asset_development_v6_store import checkpoint_status, initialize_v6_run
from multi_asset_discovery_v1 import fingerprint
from multi_asset_v2_r6_execution import r6_result_digest
from multi_asset_v2_r6_runner import (
    _persist_result,
    load_r6_review_contract,
    verify_self_fingerprint,
)


def test_r6_self_fingerprint_detects_mutation() -> None:
    payload = {"version": "test", "status": "PASS"}
    payload["artifact_fingerprint"] = fingerprint(payload)
    assert verify_self_fingerprint(payload)
    payload["status"] = "FAIL"
    assert not verify_self_fingerprint(payload)


def test_r6_review_contract_is_finite_outcome_blind_and_stage_closed() -> None:
    contract, contract_fingerprint = load_r6_review_contract()
    names = [item["name"] for item in contract["continuous_features"]]
    assert len(names) == len(set(names)) == 31
    assert len(contract_fingerprint) == 64
    assert contract["method"]["feature_combinations"] is False
    assert contract["method"]["threshold_search"] is False
    assert contract["method"]["profit_ranking"] is False
    assert contract["candidate_gate"]["historical_verified_issuer_effective_n"] == 0
    assert contract["candidate_gate"]["automatic_candidates_maximum"] == 3
    assert not any(contract["stage_safety"].values())


def test_r6_single_writer_persistence_is_idempotent(tmp_path: Path) -> None:
    paths = {
        "control": tmp_path / "control.sqlite3",
        "feature": tmp_path / "feature.sqlite3",
        "outcome": tmp_path / "outcome.sqlite3",
    }
    unit = {
        "work_unit_id": "unit-1",
        "asset_key": "ETF:TEST",
        "asset_class": "ETF",
        "symbol": "TEST",
        "period_start": "2020-01-01",
        "period_end": "2020-03-31",
    }
    manifest = {
        "run_id": "r6-test",
        "development_contract_fingerprint": "a" * 64,
        "combined_input_fingerprint": "b" * 64,
        "universe_fingerprint": "c" * 64,
        "work_plan_fingerprint": fingerprint([unit]),
        "run_manifest_fingerprint": "d" * 64,
        "commit": "e" * 40,
        "worker_count": 1,
        "sqlite_writer_count": 1,
        "started_at": "2026-09-22T00:00:00+00:00",
    }
    initialize_v6_run(
        run_manifest=manifest,
        work_plan={"total_planned_work_units": 1, "units": [unit]},
        feature_path=paths["feature"], outcome_path=paths["outcome"], control_path=paths["control"],
    )
    feature = {
        "case_id": "case-1", "asset_id": "asset-1", "symbol": "TEST",
        "asset_class": "ETF", "signal_day": "2020-02-03", "research_split": "development",
        "dependency_status": "UNKNOWN", "feature_values": {"r4b.x": 1.0},
    }
    feature["feature_fingerprint"] = fingerprint(feature)
    outcome = {
        "case_id": "case-1", "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": "asset-1", "symbol": "TEST", "asset_class": "ETF",
        "signal_day": "2020-02-03", "research_split": "development",
        "dependency_status": "UNKNOWN", "status": "PARENT_OUTCOME_REFERENCE_VERIFIED",
        "r_availability": "AVAILABLE",
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    result = {
        "compute_version": "test", "asset": {"asset_key": "ETF:TEST"},
        "r5_contract_fingerprint": "a" * 64, "feature_contract_fingerprint": "f" * 64,
        "unit_results": [{"unit": unit, "parent_status": "COMPLETED", "features": [feature],
                          "outcomes": [outcome], "summary": {"r_na_cases": 0}}],
    }
    result["scientific_digest"] = r6_result_digest(result)

    _persist_result(result=result, manifest=manifest, paths=paths, writer_pid=os.getpid())
    _persist_result(result=result, manifest=manifest, paths=paths, writer_pid=os.getpid())

    status = checkpoint_status(control_path=paths["control"], run_id="r6-test")
    assert status["completed"] == 1
    assert status["feature_rows"] == 1
    assert status["outcome_rows"] == 1
    assert status["receipts"] == 1
