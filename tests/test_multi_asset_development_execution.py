from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from multi_asset_development_contract import load_development_contract
from multi_asset_development_execution import (
    _load_fx_history,
    MultiAssetDevelopmentExecutionError,
    audit_development_stores,
    build_work_plan,
    checkpoint_status,
    claim_next_work_unit,
    complete_work_unit,
    decode_payload,
    execute_work_unit,
    initialize_run,
    load_asset_history,
    persist_work_unit_evidence,
    precompute_structure_history,
    resume_interrupted_units,
)
from multi_asset_discovery_v1 import (
    build_feature_snapshot,
    build_outcome,
    build_safe_zones,
    build_sell_zones,
    canonical_json,
    prepare_indicators,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock


def _history() -> pd.DataFrame:
    index = pd.bdate_range("2015-01-01", "2021-12-31")
    x = np.arange(len(index), dtype=float)
    close = 100 + 0.02 * x + 4.0 * np.sin(x / 13) + 1.2 * np.sin(x / 4)
    open_ = close * (1 + 0.001 * np.sin(x / 9))
    return pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) + 1.1,
            "Low": np.minimum(open_, close) - 1.1,
            "Close": close,
            "Volume": 1_000_000 + x * 100,
        },
        index=index,
    )


def _asset() -> dict[str, object]:
    return {
        "asset_key": "EQUITIES:TEST",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "source_type": "FROZEN_PARQUET",
        "identity": {
            "ticker": "TEST",
            "asset_id": "asset-test",
            "listing_id": "listing-test",
            "issuer_id": "issuer-current",
            "mapping_status": "VERIFIED",
            "valid_from": "2026-01-01",
        },
    }


def _outcome_ready_position(prepared: pd.DataFrame) -> int:
    """Return a deterministic Development row with a valid structural-R entry."""
    first_development_position = int(
        np.searchsorted(prepared.index.values, np.datetime64("2016-01-01"))
    )
    for position in range(max(219, first_development_position), len(prepared) - 253):
        safe_zones = build_safe_zones(prepared, position)
        invalidation = safe_zones["C"].get("lower")
        if (
            invalidation is not None
            and float(prepared.iloc[position + 1]["Open"]) > float(invalidation)
        ):
            return position
    raise AssertionError("Testhistorie enthält keinen auswertbaren strukturellen-R-Fall")


def test_precomputed_structure_is_exactly_equal_to_pilot_formulas() -> None:
    prepared = prepare_indicators(_history())
    safe_history, sell_history = precompute_structure_history(prepared)

    for position in (219, 300, 600, 1_000, len(prepared) - 1):
        expected_safe = build_safe_zones(prepared, position)
        expected_sell = build_sell_zones(prepared, position, expected_safe)
        assert canonical_json(safe_history[position]) == canonical_json(expected_safe)
        assert canonical_json(sell_history[position]) == canonical_json(expected_sell)


def test_prepared_reuse_does_not_change_feature_or_outcome() -> None:
    frame = _history()
    prepared = prepare_indicators(frame)
    safe_history, sell_history = precompute_structure_history(prepared)
    position = _outcome_ready_position(prepared)
    day = prepared.index[position].date().isoformat()
    asset = {
        "ticker": "TEST",
        "asset_id": "asset-test",
        "asset_class": "EQUITIES",
        "listing_id": "listing-test",
        "issuer_id": None,
        "mapping_status": "VERIFIED",
        "dependency_status": "UNKNOWN",
    }
    ordinary = build_feature_snapshot(
        asset=asset,
        frame=frame,
        decision_position=position,
        decision_time=f"{day}T23:59:59+00:00",
        dataset_fingerprint="dataset",
    )
    reused = build_feature_snapshot(
        asset=asset,
        frame=frame,
        prepared_frame=prepared,
        decision_position=position,
        decision_time=f"{day}T23:59:59+00:00",
        dataset_fingerprint="dataset",
        safe_zones_override=safe_history[position],
        sell_zones_override=sell_history[position],
    )
    assert reused == ordinary
    assert build_outcome(
        feature_snapshot=reused,
        frame=frame,
        prepared_frame=prepared,
        safe_zone_history=safe_history,
    ) == build_outcome(feature_snapshot=ordinary, frame=frame)


def test_work_plan_is_deterministic_and_quarter_partitioned() -> None:
    universe = {
        "universe_fingerprint": "universe",
        "assets": [
            {"asset_key": "FX:EUR/USD", "asset_class": "FX", "symbol": "EUR/USD"},
            {"asset_key": "EQUITIES:A", "asset_class": "EQUITIES", "symbol": "A"},
        ],
    }
    first = build_work_plan(universe)
    second = build_work_plan(universe)

    assert first == second
    assert first["total_planned_work_units"] == 48
    assert first["development_only"] is True
    assert first["validation_opened"] is False
    assert first["holdout_opened"] is False


def test_history_loader_uses_only_modern_development_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, object]] = []
    frame = _history().loc["2016-01-01":"2021-12-31"]

    def fake_read_parquet(path: Path, *, filters: object) -> pd.DataFrame:
        calls.append((Path(path), filters))
        return frame

    monkeypatch.setattr(
        "multi_asset_development_execution.pd.read_parquet", fake_read_parquet
    )
    loaded, availability, source_fingerprint = load_asset_history(
        {
            "asset_key": "EQUITIES:TEST",
            "symbol": "TEST",
            "asset_class": "EQUITIES",
            "source_type": "FROZEN_PARQUET",
            "modern_file": "modern.parquet",
            "modern_history_fingerprint": "modern-history",
            "legacy_file": "legacy.parquet",
            "legacy_history_fingerprint": "legacy-history",
        },
        manifest_path=tmp_path / "manifest.json",
    )

    assert len(calls) == 1
    assert calls[0][0].name == "modern.parquet"
    assert calls[0][1] == [
        ("Date", ">=", pd.Timestamp("2016-01-01")),
        ("Date", "<=", pd.Timestamp("2021-12-31")),
    ]
    assert loaded.index.min() >= pd.Timestamp("2016-01-01")
    assert loaded.index.max() <= pd.Timestamp("2021-12-31")
    assert availability == {}
    assert source_fingerprint.endswith(":modern-history")


def test_fx_loader_excludes_legacy_validation_and_holdout_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fx.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE historical_fx_records (
                pair_id TEXT,
                feature TEXT,
                pit_eligible INTEGER,
                observation_date TEXT,
                record_json TEXT
            );
            CREATE TABLE fx_dataset_versions (dataset_fingerprint TEXT);
            INSERT INTO fx_dataset_versions VALUES ('fx-v2-fingerprint');
            """
        )
        for day in ("2015-12-31", "2016-01-04"):
            record = {
                "observation_date": day,
                "available_at": f"{day}T23:59:59+00:00",
                "metadata": {
                    "ohlc": {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15}
                },
            }
            connection.execute(
                "INSERT INTO historical_fx_records VALUES (?,?,?,?,?)",
                ("EUR/USD", "PRICE", 1, day, canonical_json(record)),
            )

    with pytest.raises(
        MultiAssetDevelopmentExecutionError,
        match="FX-v2-Dataset-Fingerprint weicht",
    ):
        _load_fx_history(
            path=path,
            pair="EUR/USD",
            development_start="2016-01-01",
            development_end="2021-12-31",
            expected_dataset_fingerprint="wrong",
        )
    loaded, availability, source_fingerprint = _load_fx_history(
        path=path,
        pair="EUR/USD",
        development_start="2016-01-01",
        development_end="2021-12-31",
        expected_dataset_fingerprint="fx-v2-fingerprint",
    )

    assert loaded.index.tolist() == [pd.Timestamp("2016-01-04")]
    assert list(availability) == ["2016-01-04"]
    assert source_fingerprint == "fx-historical-pit:fx-v2-fingerprint"


def test_execute_work_unit_is_development_only_and_unknown_is_fail_closed() -> None:
    prepared = prepare_indicators(_history())
    safe, sell = precompute_structure_history(prepared)
    result = execute_work_unit(
        asset=_asset(),
        unit={
            "work_unit_id": "unit",
            "period_start": "2021-10-01",
            "period_end": "2021-12-31",
        },
        prepared=prepared,
        availability={},
        source_dataset_fingerprint="dataset",
        safe_history=safe,
        sell_history=sell,
    )

    assert result["features"]
    assert all(item["research_split"] == "development" for item in result["features"])
    assert all(item["dependency_status"] == "UNKNOWN" for item in result["features"])
    assert all(
        item.get("outcome_end_day", "2021-12-31") <= "2021-12-31"
        for item in result["outcomes"]
    )
    assert all(item["research_split"] == "development" for item in result["outcomes"])


def _manifest(run_id: str = "run-test") -> dict[str, object]:
    contract = load_development_contract()
    payload = {
        "run_id": run_id,
        "development_contract_version": contract["contract_version"],
        "development_contract_fingerprint": contract["contract_fingerprint"],
        "run_manifest_fingerprint": "manifest",
        "started_at": "2026-09-01T12:00:00+00:00",
    }
    return payload


def test_stores_are_separate_append_only_idempotent_and_readable(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.sqlite3"
    outcome_path = tmp_path / "outcomes.sqlite3"
    control_path = tmp_path / "control.sqlite3"
    universe = {"universe_fingerprint": "universe"}
    work_plan = {
        "work_plan_fingerprint": "plan",
        "total_planned_work_units": 1,
        "units": [
            {
                "work_unit_id": "unit",
                "asset_key": "EQUITIES:TEST",
                "asset_class": "EQUITIES",
                "symbol": "TEST",
                "period_start": "2020-01-01",
                "period_end": "2020-03-31",
            }
        ],
    }
    initialize_run(
        run_manifest=_manifest(),
        universe=universe,
        work_plan=work_plan,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    frame = _history()
    prepared = prepare_indicators(frame)
    position = _outcome_ready_position(prepared)
    day = prepared.index[position].date().isoformat()
    feature = build_feature_snapshot(
        asset={
            "ticker": "TEST",
            "asset_id": "asset-test",
            "asset_class": "EQUITIES",
            "listing_id": "listing-test",
            "issuer_id": None,
            "mapping_status": "VERIFIED",
            "dependency_status": "UNKNOWN",
        },
        frame=frame,
        prepared_frame=prepared,
        decision_position=position,
        decision_time=f"{day}T23:59:59+00:00",
        dataset_fingerprint="dataset",
        execution_contract_version=load_development_contract()["contract_version"],
    )
    outcome = build_outcome(
        feature_snapshot=feature,
        frame=frame,
        prepared_frame=prepared,
    )
    first = persist_work_unit_evidence(
        run_id="run-test",
        work_unit_id="unit",
        features=[feature],
        outcomes=[outcome],
        feature_path=feature_path,
        outcome_path=outcome_path,
    )
    second = persist_work_unit_evidence(
        run_id="run-test",
        work_unit_id="unit",
        features=[feature],
        outcomes=[outcome],
        feature_path=feature_path,
        outcome_path=outcome_path,
    )
    assert first == (1, 1)
    assert second == (0, 0)
    with sqlite3.connect(feature_path) as connection:
        payload = connection.execute("SELECT payload_zlib FROM feature_rows").fetchone()[0]
        assert decode_payload(payload)["case_id"] == feature["case_id"]
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute("DELETE FROM feature_rows")
    audit = audit_development_stores(
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        run_id="run-test",
    )
    assert audit["physically_separate"] is True
    assert audit["all_integrity_ok"] is True


def test_control_resume_does_not_create_a_second_run(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.sqlite3"
    outcome_path = tmp_path / "outcomes.sqlite3"
    control_path = tmp_path / "control.sqlite3"
    universe = {"universe_fingerprint": "universe"}
    work_plan = {
        "work_plan_fingerprint": "plan",
        "total_planned_work_units": 1,
        "units": [
            {
                "work_unit_id": "unit",
                "asset_key": "EQUITIES:TEST",
                "asset_class": "EQUITIES",
                "symbol": "TEST",
                "period_start": "2020-01-01",
                "period_end": "2020-03-31",
            }
        ],
    }
    for _ in range(2):
        initialize_run(
            run_manifest=_manifest(),
            universe=universe,
            work_plan=work_plan,
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
    unit = claim_next_work_unit(control_path=control_path, run_id="run-test")
    assert unit is not None
    assert resume_interrupted_units(control_path=control_path, run_id="run-test") == 1
    resumed = claim_next_work_unit(control_path=control_path, run_id="run-test")
    assert resumed["work_unit_id"] == unit["work_unit_id"]
    complete_work_unit(
        control_path=control_path,
        run_id="run-test",
        unit=resumed,
        feature_rows=0,
        outcome_rows=0,
        invalid_cases=0,
        censored_cases=0,
    )
    status = checkpoint_status(control_path=control_path, run_id="run-test")
    assert status["skipped"] == 1
    with sqlite3.connect(control_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_process_lock_rejects_duplicate_runner(tmp_path: Path) -> None:
    first = SwingRunLock(tmp_path / "development.lock")
    second = SwingRunLock(tmp_path / "development.lock")
    first.acquire()
    try:
        with pytest.raises(SwingRunAlreadyActiveError):
            second.acquire()
    finally:
        first.release()


def test_scheduler_contract_is_persistent_and_single_instance() -> None:
    text = Path("scripts/install_multi_asset_development_task.ps1").read_text(
        encoding="utf-8"
    )
    assert "StartWhenAvailable" in text
    assert "MultipleInstances IgnoreNew" in text
    assert "LogonType Interactive" in text
    assert "ExecutionTimeLimit (New-TimeSpan -Seconds 0)" in text
    assert "Register-ScheduledTask" in text
    assert "Start-ScheduledTask" in text
