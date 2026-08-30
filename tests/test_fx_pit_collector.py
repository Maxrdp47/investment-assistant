from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from fx_pit_collector import (
    FxPitCollectorError,
    append_derived_feature,
    append_observations,
    append_scheduled_events,
    build_derived_feature,
    fx_pit_collector_audit,
    initialize_fx_pit_collector_store,
    normalize_collector_observation,
    run_fx_pit_collector,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock


STAMP = "2026-08-29T10:00:00+00:00"


def _settings(*providers: str) -> dict[str, object]:
    return {
        "version": "pytest-fx-pit-v1",
        "mode": "FX_PIT_OBSERVER",
        "providers": {name: {"enabled": True} for name in providers},
        "safety": {
            "strategy_signal_allowed": False,
            "trade_decision_allowed": False,
            "paper_trade_allowed": False,
            "shadow_order_allowed": False,
            "broker_order_allowed": False,
        },
    }


def _observation(
    *,
    source_record_id: str = "quote-1",
    first_seen_at: str = STAMP,
    observation_type: str = "FX_PRICE_BAR",
    status: str = "OBSERVED",
    payload: dict[str, object] | None = None,
    revision_number: int = 0,
    supersedes: str | None = None,
) -> dict[str, object]:
    return {
        "observation_type": observation_type,
        "entity_id": "EUR/USD",
        "pair_id": "EUR/USD",
        "status": status,
        "source_type": "FORWARD_PIT",
        "source": "pytest provider",
        "source_record_id": source_record_id,
        "source_timestamp": "2026-08-29T09:55:00+00:00",
        "observed_at": STAMP,
        "first_seen_at": first_seen_at,
        "imported_at": first_seen_at,
        "payload": payload or {"close": 1.1},
        "quality": "TEST",
        "revision_number": revision_number,
        "supersedes": supersedes,
    }


def test_observations_are_append_only_idempotent_and_keep_first_seen(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    first = _observation()
    assert append_observations([first], run_id="run-a", path=path) == {
        "inserted": 1,
        "deduplicated": 0,
        "revisions": 0,
    }
    replay = _observation(first_seen_at="2026-08-29T11:00:00+00:00")
    result = append_observations([replay], run_id="run-b", path=path)
    assert result["inserted"] == 0
    assert result["deduplicated"] == 1
    with sqlite3.connect(path) as connection:
        stored = json.loads(connection.execute("SELECT observation_json FROM observations").fetchone()[0])
        assert stored["first_seen_at"] == STAMP
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE observations SET status='UNKNOWN'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM observations")


def test_revision_appends_instead_of_overwriting_parent(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    parent = normalize_collector_observation(_observation())
    append_observations([_observation()], run_id="run-a", path=path)
    revision = _observation(
        source_record_id="quote-1-revision",
        payload={"close": 1.2},
        revision_number=1,
        supersedes=str(parent["observation_id"]),
    )
    result = append_observations([revision], run_id="run-b", path=path)
    assert result == {"inserted": 1, "deduplicated": 0, "revisions": 1}
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 1


def test_provider_failure_is_not_recorded_as_no_event(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"

    def broken(_context):
        raise RuntimeError("provider unavailable")

    run = run_fx_pit_collector(
        _settings("broken"),
        {"broken": broken},
        path=path,
        lock_path=tmp_path / "collector.lock",
        observed_at=STAMP,
        schedule_slot="2026-08-29:daily",
    )
    assert run["status"] == "COMPLETED_WITH_SOURCE_GAPS"
    with sqlite3.connect(path) as connection:
        status = connection.execute("SELECT status FROM observations").fetchone()[0]
        health = json.loads(connection.execute("SELECT health_json FROM source_health").fetchone()[0])
    assert status == "PROVIDER_FAILURE"
    assert health["coverage_status"] == "PROVIDER_FAILURE"
    assert health["last_success"] is None


def test_daily_run_is_idempotent_and_does_not_call_provider_twice(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    calls = {"count": 0}

    def provider(_context):
        calls["count"] += 1
        return {
            "status": "OBSERVED",
            "source": "pytest provider",
            "observations": [_observation()],
            "coverage": [
                {"pair_id": "EUR/USD", "feature": "PRICE", "status": "AVAILABLE_PIT", "reason": "forward first_seen"}
            ],
            "response_quality": "TEST",
        }

    arguments = {
        "settings": _settings("prices"),
        "providers": {"prices": provider},
        "path": path,
        "lock_path": tmp_path / "collector.lock",
        "observed_at": STAMP,
        "schedule_slot": "2026-08-29:daily",
        "provenance": {"branch": "pytest", "commit_hash": "abc", "command": "pytest"},
    }
    first = run_fx_pit_collector(**arguments)
    second = run_fx_pit_collector(**arguments)
    assert first["run_id"] == second["run_id"]
    assert second["idempotent_replay"] is True
    assert calls["count"] == 1


def test_restart_after_partial_observation_deduplicates_and_completes_run(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    append_observations([_observation()], run_id="interrupted-run", path=path)

    def provider(_context):
        return {
            "status": "OBSERVED",
            "source": "pytest provider",
            "observations": [_observation()],
            "response_quality": "TEST",
        }

    run = run_fx_pit_collector(
        _settings("prices"),
        {"prices": provider},
        path=path,
        lock_path=tmp_path / "collector.lock",
        observed_at=STAMP,
        schedule_slot="2026-08-29:restart",
    )
    assert run["observations_inserted"] == 0
    assert run["observations_deduplicated"] == 1
    assert run["status"] == "COMPLETED"


def test_process_lock_rejects_parallel_collector(tmp_path: Path) -> None:
    lock_path = tmp_path / "collector.lock"
    with SwingRunLock(lock_path):
        with pytest.raises(SwingRunAlreadyActiveError):
            run_fx_pit_collector(
                _settings(),
                {},
                path=tmp_path / "collector.sqlite3",
                lock_path=lock_path,
                observed_at=STAMP,
                schedule_slot="2026-08-29:locked",
            )


def test_derived_features_are_deterministic_and_link_raw_inputs(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    first_raw = _observation(source_record_id="base-rate", observation_type="POLICY_RATE", payload={"value": 2.0})
    second_raw = _observation(source_record_id="quote-rate", observation_type="POLICY_RATE", payload={"value": 1.0})
    append_observations([first_raw, second_raw], run_id="run-a", path=path)
    first = normalize_collector_observation(first_raw)
    second = normalize_collector_observation(second_raw)
    inputs = [
        {"observation_id": first["observation_id"], "value": 2.0},
        {"observation_id": second["observation_id"], "value": 1.0},
    ]
    feature_a = build_derived_feature("RATE_DIFFERENTIAL", inputs, calculated_at=STAMP)
    feature_b = build_derived_feature("RATE_DIFFERENTIAL", inputs, calculated_at=STAMP)
    assert feature_a == feature_b
    assert feature_a["value"] == 1.0
    assert append_derived_feature(feature_a, path=path) is True
    assert append_derived_feature(feature_a, path=path) is False


def test_scheduled_event_stores_known_time_not_future_result(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    event = {
        "event_type": "CENTRAL_BANK_MEETING",
        "currency": "EUR",
        "scheduled_for": "2026-09-10T12:15:00+00:00",
        "known_at": STAMP,
        "source": "official calendar fixture",
        "source_reference": "https://example.test/calendar/event-1",
    }
    assert append_scheduled_events([event], path=path) == 1
    assert append_scheduled_events([event], path=path) == 0
    with sqlite3.connect(path) as connection:
        stored = json.loads(connection.execute("SELECT event_json FROM scheduled_events").fetchone()[0])
    assert stored["result_known"] is False


def test_trade_fields_and_unsafe_settings_are_rejected() -> None:
    with pytest.raises(FxPitCollectorError, match="Trade-/Strategiefeld"):
        normalize_collector_observation(_observation(payload={"entry": 1.1}))
    unsafe = _settings()
    unsafe["safety"]["broker_order_allowed"] = True
    with pytest.raises(FxPitCollectorError, match="fail-closed"):
        run_fx_pit_collector(unsafe, {}, lock_path=None, observed_at=STAMP)


def test_audit_proves_no_signals_orders_or_broker_path(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    run = run_fx_pit_collector(
        _settings(),
        {},
        path=path,
        lock_path=tmp_path / "collector.lock",
        observed_at=STAMP,
        schedule_slot="2026-08-29:empty-pilot",
        provenance={"branch": "pytest", "commit_hash": "abc", "command": "pytest"},
    )
    assert run["strategy_signal_generated"] is False
    assert run["paper_trade_generated"] is False
    assert run["shadow_order_generated"] is False
    assert run["broker_order_allowed"] is False
    audit = fx_pit_collector_audit(path)
    assert audit["status"] == "ok"
    assert audit["invalid_run_safety_flags"] == []
    assert audit["append_only_trigger_n"] >= 20


def test_store_initialization_is_restart_safe(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    initialize_fx_pit_collector_store(path)
    initialize_fx_pit_collector_store(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM schema_metadata").fetchone()[0] == 1
