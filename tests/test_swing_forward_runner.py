from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from swing_forward_runner import run_swing_forward_evaluations
from swing_forward_store import (
    load_swing_forward_signals,
    load_swing_rejection_controls,
    record_swing_forward_scan,
)
from trading_assistant import swing_order_plan_fingerprint


def stored_scan() -> dict:
    plan = {
        "plan_version": "test-v1",
        "stop_contract_version": "test-stop-v1",
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
        "fx_snapshot": {"rate_to_eur": 0.9, "observed_at": "2026-08-09T22:45:00+02:00"},
        "execution_cost_contract": {
            "version": "test-cost-v1",
            "spread_bps_one_way": 3.0,
            "slippage_bps_one_way": 5.0,
            "fee_bps_one_way": 1.0,
        },
        "limit_price_eur": 90.0,
        "activation_price_eur": 89.1,
        "maximum_entry_eur": 91.8,
        "initial_stop_eur": 85.5,
        "target_1_eur": 99.9,
        "target_2_eur": 106.2,
        "invalidation_eur": 85.5,
        "automatic_order_execution": False,
        "position_calculated": True,
        "quantity": 10.0,
    }
    plan["plan_fingerprint"] = swing_order_plan_fingerprint(plan)
    return {
        "last_scan": "2026-08-09T22:45:00+02:00",
        "approved": [
            {
                "setup_id": "TEST|2026-08-09|Ausbruch",
                "symbol": "TEST",
                "asset_name": "Test Asset",
                "asset_type": "Aktie",
                "direction": "Long",
                "setup_type": "Bestätigter Ausbruch über Widerstand",
                "market_phase": "Bullenmarkt",
                "original_currency": "USD",
                "order_plan": plan,
                "universe_metadata": {"version": "test-universe-v1", "region": "USA"},
            }
        ],
        "errors": [],
        "statistics": {"universe_size": 1_124, "loaded_assets": 900, "approved_trades": 1},
        "universe_report": {"version": "test-universe-v1", "path": "test.csv"},
        "thresholds": {},
        "risk_policy": {},
    }


def completed_bars(*_args) -> tuple[pd.DataFrame, str, str]:
    return (
        pd.DataFrame(
            [
                {"Open": 101.0, "High": 101.5, "Low": 99.5, "Close": 100.5},
                {"Open": 101.0, "High": 112.0, "Low": 99.0, "Close": 111.5},
                {"Open": 112.0, "High": 119.0, "Low": 108.0, "Close": 118.5},
            ],
            index=pd.to_datetime(
                ["2026-08-10T13:30:00Z", "2026-08-10T13:35:00Z", "2026-08-11T13:30:00Z"],
                utc=True,
            ),
        ),
        "5m",
        "isolierter Testfeed",
    )


def fixed_fx_loader(currency: str, occurred_at: object) -> dict:
    timestamp = pd.Timestamp(occurred_at)
    rate = 0.90 if timestamp.date().isoformat() == "2026-08-10" else 0.95
    return {
        "policy_version": "test-fx-v1",
        "rate_to_eur": rate,
        "pair_ticker": f"{currency}EUR=X",
        "inverse_quote": False,
        "observed_at": timestamp.isoformat(),
        "interval": "5m",
        "quality": "intraday_at_or_before_event",
        "source": "isolierter FX-Testfeed",
    }


def test_runner_appends_chronological_events_and_skips_terminal_signal(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    record_swing_forward_scan(stored_scan(), path)

    first = run_swing_forward_evaluations(
        path=path,
        evaluated_at=datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc),
        bars_loader=completed_bars,
        fx_loader=fixed_fx_loader,
    )
    second = run_swing_forward_evaluations(
        path=path,
        evaluated_at=datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc),
        bars_loader=completed_bars,
        fx_loader=fixed_fx_loader,
    )

    assert first["events_inserted"] == 3
    assert first["fx_valuations_inserted"] == 1
    assert first["store_audit"]["status"] == "ok"
    assert second["terminal_skipped"] == 1
    assert second["fx_valuations_existing"] == 1
    assert [event["event_type"] for event in load_swing_forward_signals(path)[0]["events"]] == [
        "paper_entry_opened",
        "target_1_reached",
        "target_2_reached",
        "historical_fx_valuation",
    ]
    valuation = load_swing_forward_signals(path)[0]["events"][-1]["payload"]
    assert valuation["paper_entry_after_costs_eur"] != valuation["paper_exit_after_costs_eur"]
    assert valuation["entry_fx"]["rate_to_eur"] == 0.90
    assert valuation["exit_fx"]["rate_to_eur"] == 0.95
    assert len(valuation["exit_fx_legs"]) == 2
    assert [leg["fx"]["rate_to_eur"] for leg in valuation["exit_fx_legs"]] == [0.90, 0.95]


def test_provider_failure_stays_retryable_and_is_idempotent_per_day(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    record_swing_forward_scan(stored_scan(), path)

    def empty_loader(*_args):
        return pd.DataFrame(), "", "Provider vorübergehend leer"

    first = run_swing_forward_evaluations(
        path=path,
        evaluated_at="2026-08-10T20:00:00+00:00",
        bars_loader=empty_loader,
    )
    second = run_swing_forward_evaluations(
        path=path,
        evaluated_at="2026-08-10T21:00:00+00:00",
        bars_loader=empty_loader,
    )

    def different_empty_loader(*_args):
        return pd.DataFrame(), "", "Provider-Netzwerk vorübergehend nicht erreichbar"

    third = run_swing_forward_evaluations(
        path=path,
        evaluated_at="2026-08-10T22:00:00+00:00",
        bars_loader=different_empty_loader,
    )

    assert first["data_failures"] == 1
    assert first["events_inserted"] == 1
    assert second["events_existing"] == 1
    assert second["terminal_skipped"] == 0
    assert third["events_inserted"] == 1
    assert third["errors"] == []
    events = load_swing_forward_signals(path)[0]["events"]
    assert len(events) == 2
    assert all(event["payload"]["retry_allowed"] is True for event in events)
    assert len({event["source_key"] for event in events}) == 2


def test_finished_signal_retries_missing_fx_without_reloading_market_bars(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    record_swing_forward_scan(stored_scan(), path)

    first = run_swing_forward_evaluations(
        path=path,
        evaluated_at=datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc),
        bars_loader=completed_bars,
        fx_loader=lambda *_args: None,
    )

    def must_not_load_bars(*_args):
        raise AssertionError("Ein abgeschlossener Trade darf für die reine FX-Nachbewertung keine Kursbalken laden.")

    second = run_swing_forward_evaluations(
        path=path,
        evaluated_at=datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc),
        bars_loader=must_not_load_bars,
        fx_loader=fixed_fx_loader,
    )

    assert first["fx_valuations_pending"] == 1
    assert second["fx_valuations_inserted"] == 1
    assert second["errors"] == []


def test_missed_signal_collects_separate_counterfactual_outcomes(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    record_swing_forward_scan(stored_scan(), path)
    index = pd.bdate_range("2026-08-10", periods=25, tz="UTC")
    closes = [103.0 + index_value * 0.25 for index_value in range(len(index))]
    bars = pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1.0 for value in closes],
            "Low": [value - 1.0 for value in closes],
            "Close": [value + 0.5 for value in closes],
        },
        index=index,
    )

    def missed_then_followed(*_args):
        return bars, "1d", "isolierter Kontrollfeed"

    first = run_swing_forward_evaluations(
        path=path,
        evaluated_at="2026-09-20T20:00:00+00:00",
        bars_loader=missed_then_followed,
    )
    second = run_swing_forward_evaluations(
        path=path,
        evaluated_at="2026-09-20T21:00:00+00:00",
        bars_loader=missed_then_followed,
    )

    assert first["events_inserted"] == 1
    assert second["counterfactual_events_inserted"] == 2
    events = load_swing_forward_signals(path)[0]["events"]
    controls = [event for event in events if event["event_type"] == "counterfactual_outcome"]
    assert [event["payload"]["horizon_sessions"] for event in controls] == [5, 20]
    assert all(event["payload"]["not_a_trade_result"] is True for event in controls)
    assert all(event["payload"]["return_pct"] > 0 for event in controls)


def test_rejected_candidate_sample_gets_fixed_horizon_controls_without_becoming_signal(tmp_path) -> None:
    path = tmp_path / "swing.sqlite3"
    payload = stored_scan()
    payload["approved"] = []
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
            "sampling_key": "b" * 64,
            "sampling_version": "test-v1",
            "control_only": True,
            "not_a_trade_signal": True,
        }
    ]
    record_swing_forward_scan(payload, path)
    index = pd.bdate_range("2026-08-10", periods=25, tz="UTC")
    bars = pd.DataFrame(
        {
            "Open": [100.0] * 25,
            "High": [101.0 + value for value in range(25)],
            "Low": [99.0] * 25,
            "Close": [100.5 + value for value in range(25)],
        },
        index=index,
    )

    summary = run_swing_forward_evaluations(
        path=path,
        evaluated_at="2026-09-20T20:00:00+00:00",
        bars_loader=lambda *_args: (bars, "1d", "isolierter Kontrollfeed"),
    )

    assert summary["signals_total"] == 0
    assert summary["rejection_controls_total"] == 1
    assert summary["rejection_control_events_inserted"] == 2
    control = load_swing_rejection_controls(path)[0]
    assert [event["horizon_sessions"] for event in control["events"]] == [5, 20]
    assert all(event["payload"]["not_a_trade_result"] is True for event in control["events"])
