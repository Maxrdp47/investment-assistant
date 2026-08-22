from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from swing_user_store import (
    SwingUserTradeDeviationConfirmationRequired,
    close_swing_user_trade,
    create_swing_user_trade,
    load_swing_user_trade_states,
    record_swing_user_partial_sale,
    swing_user_trade_guidance,
    swing_user_store_audit,
    tighten_swing_user_stop,
)
from trading_assistant import swing_order_plan_fingerprint


OPENED = datetime(2026, 8, 10, 15, 30)


def signal_snapshot() -> dict:
    plan = {
        "plan_version": "test-plan-v1",
        "stop_contract_version": "test-stop-v1",
        "earliest_entry_day": "2026-08-10",
        "valid_until": "2026-08-14",
        "limit_price_eur": 90.0,
        "maximum_entry_eur": 92.0,
        "initial_stop_eur": 85.0,
        "target_1_eur": 100.0,
        "target_2_eur": 106.0,
        "quantity": 10.0,
        "position_calculated": True,
        "automatic_order_execution": False,
    }
    plan["plan_fingerprint"] = swing_order_plan_fingerprint(plan)
    return {
        "signal_at": "2026-08-10T15:00:00+02:00",
        "asset": {
            "ticker": "TEST",
            "isin": "DE000TEST001",
            "name": "Test Asset",
            "asset_type": "Aktie",
        },
        "strategy": {"setup_type": "Ausbruch", "strategy_version": "test-v1"},
        "order_plan": plan,
        "trade_republic_execution": {
            "status": "TR handelbar",
            "execution_ready": True,
            "analysis_listing": {"ticker": "TEST", "isin": "DE000TEST001"},
            "tr_listing": {
                "ticker": "TEST-TR",
                "isin": "DE000TEST001",
                "exchange": "TEST EXCHANGE",
                "currency": "EUR",
            },
            "price_eur": 90.0,
            "price_source": "Manuell aus Trade Republic erfasst",
            "analysis_comparison_price_eur": 90.0,
            "analysis_price_source": "Yahoo Finance / yfinance – zeitgleicher Vergleichskurs",
        },
    }


def open_trade(path, **overrides):
    values = {
        "signal_id": "signal-1",
        "signal_snapshot": signal_snapshot(),
        "actual_entry_eur": 90.0,
        "quantity": 10.0,
        "opened_at": OPENED,
        "path": path,
    }
    values.update(overrides)
    return create_swing_user_trade(**values)


def test_matching_user_trade_is_separate_immutable_and_sends_no_order(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"

    created = open_trade(path)
    state = load_swing_user_trade_states(path)[0]

    assert created["inserted"] is True
    assert created["deviations"] == []
    assert state["status"] == "Aktiv"
    assert state["snapshot"]["broker_order_sent"] is False
    assert state["snapshot"]["signal_id"] == "signal-1"
    assert state["remaining_quantity"] == 10.0
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE user_trades SET signal_id = 'changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM user_trades")


def test_user_trade_requires_verified_trade_republic_execution(tmp_path) -> None:
    snapshot = signal_snapshot()
    snapshot.pop("trade_republic_execution")

    with pytest.raises(ValueError, match="Trade-Republic-Plan"):
        open_trade(tmp_path / "missing-tr.sqlite3", signal_snapshot=snapshot)


def test_yahoo_price_cannot_be_used_as_trade_republic_execution_price(tmp_path) -> None:
    snapshot = signal_snapshot()
    snapshot["trade_republic_execution"]["price_source"] = "Yahoo Finance / yfinance"

    with pytest.raises(ValueError, match="Yahoo"):
        open_trade(tmp_path / "yahoo-price.sqlite3", signal_snapshot=snapshot)


def test_plan_deviation_requires_explicit_confirmation_and_stays_visible(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"

    with pytest.raises(SwingUserTradeDeviationConfirmationRequired) as exc_info:
        open_trade(path, actual_entry_eur=94.0, quantity=7.0)

    assert any("Maximalpreis" in item for item in exc_info.value.deviations)
    assert any("Stückzahl" in item for item in exc_info.value.deviations)
    created = open_trade(
        path,
        actual_entry_eur=94.0,
        quantity=7.0,
        confirm_deviations=True,
    )
    state = load_swing_user_trade_states(path)[0]
    assert created["inserted"] is True
    assert state["snapshot"]["deviation_confirmed"] is True
    assert len(state["snapshot"]["deviations"]) == 2


def test_entry_before_earliest_day_and_after_expiry_are_not_silent(tmp_path) -> None:
    early_snapshot = signal_snapshot()
    early_snapshot["signal_at"] = "2026-08-08T15:00:00+02:00"
    with pytest.raises(SwingUserTradeDeviationConfirmationRequired, match="frühesten"):
        open_trade(
            tmp_path / "early.sqlite3",
            signal_snapshot=early_snapshot,
            opened_at=datetime(2026, 8, 9, 12, 0),
        )
    with pytest.raises(SwingUserTradeDeviationConfirmationRequired, match="Ablauf"):
        open_trade(tmp_path / "late.sqlite3", opened_at=datetime(2026, 8, 15, 12, 0))


def test_entry_at_or_before_signal_time_cannot_be_confirmed_as_a_deviation(tmp_path) -> None:
    for opened_at in (
        "2026-08-10T14:59:59+02:00",
        "2026-08-10T15:00:00+02:00",
    ):
        with pytest.raises(ValueError, match="nach dem gespeicherten Signalzeitpunkt"):
            open_trade(
                tmp_path / f"invalid-{opened_at[-8:-6]}.sqlite3",
                opened_at=opened_at,
                confirm_deviations=True,
            )


def test_entry_on_wrong_side_of_stop_can_never_be_confirmed(tmp_path) -> None:
    with pytest.raises(ValueError, match="nicht über dem System-Stop"):
        open_trade(
            tmp_path / "below-stop.sqlite3",
            actual_entry_eur=84.0,
            confirm_deviations=True,
        )


def test_stop_can_only_tighten_and_initial_stop_never_changes(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"
    trade_id = open_trade(path)["user_trade_id"]

    tighten_swing_user_stop(trade_id, 87.0, OPENED + timedelta(days=1), path)
    state = load_swing_user_trade_states(path)[0]

    assert state["current_stop_eur"] == 87.0
    assert state["snapshot"]["initial_stop_eur"] == 85.0
    with pytest.raises(ValueError, match="niemals erweitert"):
        tighten_swing_user_stop(trade_id, 86.0, OPENED + timedelta(days=2), path)


def test_partial_sale_and_close_preserve_full_event_history_and_result(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"
    trade_id = open_trade(path)["user_trade_id"]

    record_swing_user_partial_sale(trade_id, 4.0, 100.0, OPENED + timedelta(days=2), path)
    close_swing_user_trade(trade_id, 95.0, OPENED + timedelta(days=4), path)
    state = load_swing_user_trade_states(path)[0]

    assert state["status"] == "Geschlossen"
    assert state["remaining_quantity"] == 0.0
    assert state["realized_pnl_eur"] == pytest.approx(70.0)
    assert [event["event_type"] for event in state["events"]] == ["partial_sale", "closed"]
    assert swing_user_store_audit(path)["status"] == "ok"


def test_one_objective_signal_can_create_only_one_personal_trade(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"
    first = open_trade(path)
    second = open_trade(path)

    assert first["inserted"] is True
    assert second["inserted"] is False
    with pytest.raises(ValueError, match="bereits"):
        open_trade(path, actual_entry_eur=91.0)


def test_active_guidance_is_rule_based_and_never_executes_an_order(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"
    open_trade(path)
    state = load_swing_user_trade_states(path)[0]

    intact = swing_user_trade_guidance(state, 91.0, OPENED + timedelta(hours=1))
    one_r = swing_user_trade_guidance(state, 95.0, OPENED + timedelta(days=1))
    stopped = swing_user_trade_guidance(state, 84.0, OPENED + timedelta(days=2))

    assert intact["status"] == "Plan intakt"
    assert one_r["status"] == "Regelbasierte Anpassung empfohlen"
    assert "Stop auf Einstand" in one_r["reason"]
    assert stopped["status"] == "Notausstieg empfohlen"
    assert stopped["automatic_order_execution"] is False


def test_active_guidance_prioritizes_confirmed_structure_break_with_selling_volume(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"
    open_trade(path)
    state = load_swing_user_trade_states(path)[0]

    guidance = swing_user_trade_guidance(
        state,
        90.0,
        OPENED + timedelta(days=2),
        market_context={
            "version": "test-monitor-v1",
            "data_quality": "hoch",
            "structure_break": True,
            "high_volume_structure_break": True,
            "checked_factors": ["Kursstruktur", "relatives Volumen"],
            "unavailable_factors": ["Nachrichten"],
        },
    )

    assert guidance["status"] == "Notausstieg empfohlen"
    assert "Verkaufsvolumen" in guidance["reason"]
    assert guidance["monitor_version"] == "test-monitor-v1"
    assert guidance["automatic_order_execution"] is False


def test_active_guidance_warns_before_a_confirmed_near_event(tmp_path) -> None:
    path = tmp_path / "user.sqlite3"
    open_trade(path)
    state = load_swing_user_trade_states(path)[0]

    guidance = swing_user_trade_guidance(
        state,
        91.0,
        OPENED + timedelta(days=2),
        market_context={"days_to_known_event": 1},
    )

    assert guidance["status"] == "Regelbasierte Anpassung empfohlen"
    assert "Unternehmensereignis" in guidance["reason"]
