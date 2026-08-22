from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from swing_forward_store import (
    append_swing_rejection_control_event,
    append_swing_signal_event,
    initialize_swing_forward_store,
    load_swing_forward_scans,
    load_swing_forward_signals,
    load_swing_rejection_controls,
    record_swing_forward_scan,
    swing_forward_store_audit,
)
from trading_assistant import swing_order_plan_fingerprint


OBSERVED_AT = "2026-08-09T22:45:00+02:00"


def test_schema_one_is_migrated_non_destructively_for_rejection_controls(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE swing_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO swing_meta (key, value) VALUES ('schema_version', '1')")

    initialize_swing_forward_store(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT value FROM swing_meta WHERE key = 'schema_version'"
        ).fetchone()[0] == "2"
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'swing_rejection_controls'"
        ).fetchone()[0] == "swing_rejection_controls"


def order_plan() -> dict:
    plan = {
        "plan_version": "swing-order-plan-test-v1",
        "stop_contract_version": "swing-stop-test-v1",
        "entry_method": "Schlusskursbestätigung",
        "order_type": "Limitorder nach Schlusskursbestätigung",
        "signal_bar_day": "2026-08-07",
        "earliest_entry_day": "2026-08-10",
        "valid_until": "2026-08-14",
        "limit_price_original": 100.0,
        "activation_price_original": 99.0,
        "maximum_entry_original": 102.0,
        "initial_stop_original": 95.0,
        "target_1_original": 111.0,
        "target_2_original": 118.0,
        "invalidation_original": 95.0,
        "original_currency": "USD",
        "fx_snapshot": {"rate_to_eur": 0.9, "observed_at": OBSERVED_AT},
        "limit_price_eur": 90.0,
        "activation_price_eur": 89.1,
        "maximum_entry_eur": 91.8,
        "initial_stop_eur": 85.5,
        "target_1_eur": 99.9,
        "target_2_eur": 106.2,
        "invalidation_eur": 85.5,
        "delete_conditions": ["Strukturbruch", "Ablauf"],
        "automatic_order_execution": False,
        "quantity": 10.0,
        "capital_committed_eur": 900.0,
        "planned_loss_eur": 45.0,
        "possible_gain_1_eur": 99.0,
        "possible_gain_2_eur": 162.0,
        "position_calculated": True,
        "position_note": "Testposition",
    }
    plan["plan_fingerprint"] = swing_order_plan_fingerprint(plan)
    return plan


def scan_result(*, approved: bool = True) -> dict:
    setup = {
        "setup_id": "TEST|2026-08-09|Ausbruch",
        "symbol": "TEST",
        "asset_name": "Test Asset",
        "asset_type": "Aktie",
        "direction": "Long",
        "setup_type": "Bestätigter Ausbruch über Widerstand",
        "market_phase": "Bullenmarkt",
        "quality_score": 7.4,
        "historical_cases": 0,
        "historical_hit_rate": None,
        "original_currency": "USD",
        "order_plan": order_plan(),
        "universe_metadata": {
            "version": "swing-universe-test-v1",
            "region": "USA",
            "category": "Test",
            "source_group": "test",
            "liquidity_class": "A",
        },
    }
    return {
        "last_scan": OBSERVED_AT,
        "approved": [setup] if approved else [],
        "errors": [],
        "market_label": "Unterstützend",
        "thresholds": {"min_crv": 2.0},
        "prefilter_thresholds": {"filter_policy_version": "swing-filter-neutrality-test-v1"},
        "risk_policy": {"version": "test-risk-v1"},
        "statistics": {
            "universe_size": 1_124,
            "loaded_assets": 900,
            "failed_downloads": 224,
            "prefilter_passed_total": 100,
            "prefilter_candidates": 60,
            "fully_evaluated": 60,
            "approved_trades": int(approved),
        },
        "deep_analysis_policy": "all_prefilter_passed",
        "asset_type_funnel": {
            "Aktie": {
                "universe_assets": 1124,
                "loaded_assets": 900,
                "prefilter_passed": 100,
                "fully_evaluated": 100,
                "setup_approved": int(approved),
                "portfolio_released": int(approved),
            }
        },
        "asset_type_bias_audit": {"status": "insufficient_sample"},
        "universe_report": {
            "version": "swing-universe-test-v1",
            "path": "config/swing_universe.csv",
        },
    }


def test_zero_trade_scan_is_kept_as_a_real_forward_observation(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"

    result = record_swing_forward_scan(scan_result(approved=False), path)
    audit = swing_forward_store_audit(path)

    assert result["scan_inserted"] is True
    assert load_swing_forward_scans(path)[0]["snapshot"]["contains_zero_trade_result"] is True
    assert load_swing_forward_scans(path)[0]["snapshot"]["deep_analysis_policy"] == "all_prefilter_passed"
    assert load_swing_forward_scans(path)[0]["snapshot"]["prefilter_thresholds"]["filter_policy_version"] == (
        "swing-filter-neutrality-test-v1"
    )
    assert result["zero_trade_scan"] is True
    assert result["signals_total"] == 0
    assert audit == {
        "schema_version": 2,
        "quick_check": "ok",
        "scans": 1,
        "signals": 0,
        "events": 0,
        "rejection_controls": 0,
        "rejection_control_events": 0,
        "invalid_count": 0,
        "invalid": [],
        "status": "ok",
    }


def test_signal_snapshot_is_complete_immutable_and_idempotent(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"

    first = record_swing_forward_scan(scan_result(), path)
    second = record_swing_forward_scan(scan_result(), path)

    assert first["signals_inserted"] == 1
    assert first["signal_ids_by_setup"]["TEST|2026-08-09|Ausbruch"]
    assert second["scan_inserted"] is False
    assert second["signals_inserted"] == 0
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT signal_id, snapshot_json FROM swing_signals"
        ).fetchone()
        snapshot = json.loads(row[1])
        assert snapshot["source_kind"] == "real_forward_scan"
        assert snapshot["immutable"] is True
        assert snapshot["asset"]["ticker"] == "TEST"
        assert snapshot["order_plan"]["position_calculated"] is True
        assert snapshot["data_contract"]["no_market_data_before_signal"] is True
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE swing_signals SET symbol = 'CHANGED' WHERE signal_id = ?",
                (row[0],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM swing_signals WHERE signal_id = ?", (row[0],))


def test_strategy_qualified_shadow_signal_is_stored_but_labeled_separately(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    payload = scan_result(approved=False)
    shadow = scan_result()["approved"][0]
    shadow["forward_evidence_kind"] = "shadow_portfolio_capacity"
    shadow["forward_exclusion_reason"] = "Maximal drei gleichzeitige Nutzertrades."
    shadow["scanner_qualified"] = True
    payload["shadow_signals"] = [shadow]
    payload["statistics"]["strategy_qualified_total"] = 1

    stored = record_swing_forward_scan(payload, path)
    signal = load_swing_forward_signals(path)[0]
    scan = load_swing_forward_scans(path)[0]["snapshot"]

    assert stored["zero_trade_scan"] is True
    assert stored["zero_strategy_signal_scan"] is False
    assert stored["released_signals"] == 0
    assert stored["shadow_signals"] == 1
    assert signal["snapshot"]["forward_evidence"]["kind"] == "shadow_portfolio_capacity"
    assert signal["snapshot"]["forward_evidence"]["user_portfolio_released"] is False
    assert scan["contains_zero_trade_result"] is True
    assert scan["contains_zero_strategy_signal"] is False


def test_rejected_deep_candidate_control_is_append_only_and_not_a_signal(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    payload = scan_result(approved=False)
    payload["rejection_controls"] = [
        {
            "ticker": "REJECT",
            "asset_name": "Rejected Asset",
            "asset_type": "Aktie",
            "region": "USA",
            "signal_day": "2026-08-07",
            "reference_price_original": 100.0,
            "rejection_filters": ["crv"],
            "rejection_reasons": ["CRV zu niedrig"],
            "sampling_key": "a" * 64,
            "sampling_version": "test-v1",
            "control_only": True,
            "not_a_trade_signal": True,
        }
    ]

    stored = record_swing_forward_scan(payload, path)
    control = load_swing_rejection_controls(path)[0]
    first = append_swing_rejection_control_event(
        control["control_id"],
        5,
        "2026-08-14",
        {"return_pct": 4.0},
        path,
    )
    second = append_swing_rejection_control_event(
        control["control_id"],
        5,
        "2026-08-14",
        {"return_pct": 4.0},
        path,
    )

    assert stored["signals_total"] == 0
    assert stored["rejection_controls_inserted"] == 1
    assert control["snapshot"]["not_a_trade_signal"] is True
    assert first["inserted"] is True
    assert second["inserted"] is False
    assert swing_forward_store_audit(path)["rejection_control_events"] == 1


def test_same_completed_setup_bar_is_not_counted_twice_across_scans(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    first_scan = scan_result()
    second_scan = deepcopy(first_scan)
    second_scan["last_scan"] = "2026-08-10T10:00:00+02:00"

    first = record_swing_forward_scan(first_scan, path)
    second = record_swing_forward_scan(second_scan, path)
    audit = swing_forward_store_audit(path)

    assert first["signals_inserted"] == 1
    assert second["signals_inserted"] == 0
    assert second["signals_existing"] == 1
    assert first["signal_ids_by_setup"] == second["signal_ids_by_setup"]
    assert audit["scans"] == 2
    assert audit["signals"] == 1


def test_same_scan_identity_can_never_be_rewritten_with_other_data(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    original = scan_result()
    changed = deepcopy(original)
    changed["market_label"] = "Belastet"
    record_swing_forward_scan(original, path)

    with pytest.raises(ValueError, match="abweichende unveränderbare Daten"):
        record_swing_forward_scan(changed, path)


def test_invalid_or_unfinalized_order_plan_blocks_the_whole_scan(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    invalid = scan_result()
    invalid["approved"][0]["order_plan"]["limit_price_eur"] = 999.0

    with pytest.raises(ValueError, match="Fingerabdruck"):
        record_swing_forward_scan(invalid, path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM swing_scans").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM swing_signals").fetchone()[0] == 0


def test_events_are_append_only_idempotent_and_conflict_safe(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    record_swing_forward_scan(scan_result(), path)
    with sqlite3.connect(path) as connection:
        signal_id = connection.execute("SELECT signal_id FROM swing_signals").fetchone()[0]

    first = append_swing_signal_event(
        signal_id,
        "paper_entry_opened",
        datetime(2026, 8, 10, 13, 30, tzinfo=timezone.utc),
        "bar:2026-08-10T13:30:00Z:5m",
        {"entry_original": 100.0, "data_quality": "hoch"},
        path,
    )
    second = append_swing_signal_event(
        signal_id,
        "paper_entry_opened",
        datetime(2026, 8, 10, 13, 30, tzinfo=timezone.utc),
        "bar:2026-08-10T13:30:00Z:5m",
        {"entry_original": 100.0, "data_quality": "hoch"},
        path,
    )

    assert first["inserted"] is True
    assert second["inserted"] is False
    with pytest.raises(ValueError, match="anderen Daten"):
        append_swing_signal_event(
            signal_id,
            "paper_entry_opened",
            datetime(2026, 8, 10, 13, 30, tzinfo=timezone.utc),
            "bar:2026-08-10T13:30:00Z:5m",
            {"entry_original": 101.0, "data_quality": "hoch"},
            path,
        )
    audit = swing_forward_store_audit(path)
    assert audit["events"] == 1
    assert audit["status"] == "ok"
