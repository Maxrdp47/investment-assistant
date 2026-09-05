from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import multi_asset_development_v6_store as store
from multi_asset_discovery_v1 import fingerprint


def _manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": "madv6-test-run",
        "development_contract_fingerprint": "contract-fp",
        "combined_input_fingerprint": "input-fp",
        "universe_fingerprint": "universe-fp",
        "work_plan_fingerprint": "plan-fp",
        "commit": "abc123",
        "worker_count": 2,
        "sqlite_writer_count": 1,
        "started_at": "2026-09-05T18:00:00+00:00",
    }
    payload["run_manifest_fingerprint"] = fingerprint(payload)
    return payload


def _plan() -> dict[str, object]:
    units = [
        {
            "work_unit_id": "unit-1",
            "asset_key": "EQUITIES:AAA",
            "asset_class": "EQUITIES",
            "symbol": "AAA",
            "period_start": "2016-01-01",
            "period_end": "2016-03-31",
        },
        {
            "work_unit_id": "unit-2",
            "asset_key": "EQUITIES:AAA",
            "asset_class": "EQUITIES",
            "symbol": "AAA",
            "period_start": "2016-04-01",
            "period_end": "2016-06-30",
        },
    ]
    return {"total_planned_work_units": 2, "units": units}


def _paths(root: Path) -> tuple[Path, Path, Path]:
    return root / "features.sqlite3", root / "outcomes.sqlite3", root / "control.sqlite3"


def _feature(case_id: str = "case-1") -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "asset_id": "asset-1",
        "symbol": "AAA",
        "asset_class": "EQUITIES",
        "signal_day": "2016-03-01",
        "research_split": "development",
        "dependency_status": "UNKNOWN",
    }
    payload["feature_fingerprint"] = fingerprint(payload)
    return payload


def _outcome(feature: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": feature["case_id"],
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": feature["asset_id"],
        "symbol": feature["symbol"],
        "asset_class": feature["asset_class"],
        "signal_day": feature["signal_day"],
        "research_split": "development",
        "status": "CENSORED_AT_STAGE_BOUNDARY",
        "r_availability": "UNAVAILABLE",
        "dependency_status": "UNKNOWN",
    }
    payload["outcome_fingerprint"] = fingerprint(payload)
    return payload


def _initialize(root: Path) -> tuple[Path, Path, Path]:
    feature_path, outcome_path, control_path = _paths(root)
    store.initialize_v6_run(
        run_manifest=_manifest(),
        work_plan=_plan(),
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    return feature_path, outcome_path, control_path


def test_cross_store_receipt_is_idempotent_and_completes_once(tmp_path: Path) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    units = store.claim_next_asset_batch(control_path=control_path, run_id="madv6-test-run")
    feature = _feature()
    outcome = _outcome(feature)
    first = store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=units[0],
        features=[feature],
        outcomes=[outcome],
        summary={"r_na_cases": 1, "censored_cases": 1},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    second = store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=units[0],
        features=[feature],
        outcomes=[outcome],
        summary={"r_na_cases": 1, "censored_cases": 1},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    assert first == second
    status = store.checkpoint_status(control_path=control_path, run_id="madv6-test-run")
    assert status["completed"] == 1
    assert status["feature_rows"] == 1
    assert status["outcome_rows"] == 1
    assert status["r_na_cases"] == 1
    assert status["receipts"] == 1


def test_completed_unit_conflict_is_rejected_before_new_evidence_is_written(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    unit = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )[0]
    first = _feature("case-1")
    store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=unit,
        features=[first],
        outcomes=[_outcome(first)],
        summary={},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    extra = _feature("case-2")
    with pytest.raises(store.DevelopmentV6StoreError, match="refusing any evidence write"):
        store.persist_and_complete_work_unit(
            writer_pid=os.getpid(),
            run_id="madv6-test-run",
            unit=unit,
            features=[first, extra],
            outcomes=[_outcome(first), _outcome(extra)],
            summary={},
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
    with sqlite3.connect(feature_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM feature_rows").fetchone()[0] == 1
    with sqlite3.connect(outcome_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM outcome_rows").fetchone()[0] == 1


def test_crash_between_feature_and_outcome_write_repairs_on_resume(tmp_path: Path) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    units = store.claim_next_asset_batch(control_path=control_path, run_id="madv6-test-run")
    feature = _feature()
    outcome = _outcome(feature)
    store._insert_features(
        path=feature_path,
        run_id="madv6-test-run",
        work_unit_id="unit-1",
        features=[feature],
    )
    assert store.reset_interrupted_units(
        control_path=control_path, run_id="madv6-test-run"
    ) == 2
    reclaimed = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )
    receipt = store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=reclaimed[0],
        features=[feature],
        outcomes=[outcome],
        summary={},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    assert receipt["feature_rows"] == receipt["outcome_rows"] == 1


def test_feature_outcome_link_mismatch_fails_before_any_write(tmp_path: Path) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    unit = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )[0]
    feature = _feature()
    outcome = _outcome(feature)
    outcome["feature_fingerprint"] = "wrong"
    with pytest.raises(store.DevelopmentV6StoreError, match="wrong feature"):
        store.persist_and_complete_work_unit(
            writer_pid=os.getpid(),
            run_id="madv6-test-run",
            unit=unit,
            features=[feature],
            outcomes=[outcome],
            summary={},
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
    with sqlite3.connect(feature_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM feature_rows").fetchone()[0] == 0


def test_main_writer_pid_is_enforced(tmp_path: Path) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    unit = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )[0]
    feature = _feature()
    with pytest.raises(store.DevelopmentV6StoreError, match="main writer"):
        store.persist_and_complete_work_unit(
            writer_pid=os.getpid() + 1,
            run_id="madv6-test-run",
            unit=unit,
            features=[feature],
            outcomes=[_outcome(feature)],
            summary={},
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )


def test_empty_no_data_units_receive_receipts_and_terminal_timestamp_is_stable(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    units = store.claim_next_asset_batch(control_path=control_path, run_id="madv6-test-run")
    for unit in units:
        store.skip_work_unit(
            writer_pid=os.getpid(),
            run_id="madv6-test-run",
            unit=unit,
            reason_code="EXPECTED_NO_DEVELOPMENT_DATA",
            reason="no rows",
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
    assert store.mark_run_complete(control_path=control_path, run_id="madv6-test-run")
    first = store.checkpoint_status(control_path=control_path, run_id="madv6-test-run")
    assert first["status"] == "COMPLETED"
    assert first["receipts"] == 2
    assert store.mark_run_complete(control_path=control_path, run_id="madv6-test-run")
    second = store.checkpoint_status(control_path=control_path, run_id="madv6-test-run")
    assert first["completed_at"] == second["completed_at"]


def test_append_only_evidence_rejects_update_and_delete(tmp_path: Path) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    unit = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )[0]
    feature = _feature()
    store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=unit,
        features=[feature],
        outcomes=[_outcome(feature)],
        summary={},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    with sqlite3.connect(feature_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute("DELETE FROM feature_rows")
    with sqlite3.connect(outcome_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute("UPDATE outcome_rows SET status='OTHER'")
    with sqlite3.connect(control_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="terminal_work_unit_immutable"):
            connection.execute(
                "UPDATE work_units SET completed_at='changed' WHERE work_unit_id='unit-1'"
            )


def test_asset_batch_failure_preserves_already_completed_units(tmp_path: Path) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    units = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )
    assert len(units) == 2
    first, second = units
    feature = _feature("case-completed")
    outcome = _outcome(feature)
    store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=first,
        features=[feature],
        outcomes=[outcome],
        summary={"r_na_cases": 0, "censored_cases": 0},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )

    disposition = store.fail_asset_batch(
        control_path=control_path,
        run_id="madv6-test-run",
        units=units,
        error=sqlite3.OperationalError("database is locked"),
        maximum_attempts=3,
        retryable=True,
    )

    assert disposition == "RETRY"
    with sqlite3.connect(control_path) as connection:
        rows = dict(
            connection.execute(
                "SELECT work_unit_id,status FROM work_units ORDER BY work_unit_id"
            ).fetchall()
        )
    assert rows[str(first["work_unit_id"])] == "COMPLETED"
    assert rows[str(second["work_unit_id"])] == "PENDING"


def test_post_commit_batch_error_is_reconciled_without_reopening_units(
    tmp_path: Path,
) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    units = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )
    for index, unit in enumerate(units):
        feature = _feature(f"case-{index}")
        store.persist_and_complete_work_unit(
            writer_pid=os.getpid(),
            run_id="madv6-test-run",
            unit=unit,
            features=[feature],
            outcomes=[_outcome(feature)],
            summary={"r_na_cases": 0, "censored_cases": 0},
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )

    disposition = store.fail_asset_batch(
        control_path=control_path,
        run_id="madv6-test-run",
        units=units,
        error=sqlite3.OperationalError("database is locked"),
        maximum_attempts=3,
        retryable=True,
    )

    assert disposition == "ALREADY_TERMINAL"
    status = store.checkpoint_status(
        control_path=control_path, run_id="madv6-test-run"
    )
    assert status["completed"] == 2
    assert status["failed"] == 0


def test_evidence_conflict_lookup_is_batched_once_per_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature_path, outcome_path, control_path = _initialize(tmp_path)
    unit = store.claim_next_asset_batch(
        control_path=control_path, run_id="madv6-test-run"
    )[0]
    features = [_feature(f"case-{index:03d}") for index in range(100)]
    outcomes = [_outcome(feature) for feature in features]
    calls: list[tuple[str, int]] = []
    original = store._existing_digests

    def counted(connection, *, table, digest_column, case_ids):
        calls.append((table, len(case_ids)))
        return original(
            connection,
            table=table,
            digest_column=digest_column,
            case_ids=case_ids,
        )

    monkeypatch.setattr(store, "_existing_digests", counted)
    receipt = store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id="madv6-test-run",
        unit=unit,
        features=features,
        outcomes=outcomes,
        summary={},
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )

    assert receipt["feature_rows"] == receipt["outcome_rows"] == 100
    assert calls == [("feature_rows", 100), ("outcome_rows", 100)]
