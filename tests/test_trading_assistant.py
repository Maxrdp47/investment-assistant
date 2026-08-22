from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from trading_assistant import (
    DEFAULT_SWING_THRESHOLDS,
    SWING_ORDER_PLAN_VERSION,
    SWING_STOP_CONTRACT_VERSION,
    active_trade_snapshot,
    assess_swing_order_plan,
    calculate_position_size,
    close_trade_record,
    evaluate_swing_trade,
    expected_value_in_r,
    expire_paper_trade,
    finalize_swing_order_plan,
    long_trade_metrics,
    open_trade_record,
    paper_trade_statistics,
    tighten_active_trade_stop,
    validate_traded_listing,
)


NOW = datetime(2026, 8, 2, 18, 0, 0)


def breakout_prices(*, last_close: float = 121.3, latest_volume: float = 1_500_000) -> pd.DataFrame:
    index = pd.bdate_range("2025-08-04", periods=260)
    close = np.linspace(80.0, 116.0, 260)
    close[-21:-1] = np.linspace(116.0, 120.0, 20)
    close[-1] = last_close
    frame = pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(260, 1_000_000.0),
        },
        index=index,
    )
    frame.iloc[-1, frame.columns.get_loc("Volume")] = latest_volume
    return frame


def pullback_prices(*, high_peak: float = 140.0, last_close: float = 130.0) -> pd.DataFrame:
    index = pd.bdate_range("2025-08-04", periods=260)
    close = np.linspace(80.0, 125.0, 260)
    tail = np.array(
        [126.0, 130.0, 135.0, high_peak, 137.0, 134.0, 131.0, 128.0, 127.0, 128.0, 127.8, 128.0, 128.5, 129.0, last_close]
    )
    if high_peak < 137:
        tail = np.array(
            [126.0, 129.0, 132.0, high_peak, 133.0, 132.0, 131.0, 128.0, 127.0, 128.0, 127.8, 128.0, 128.5, 129.0, last_close]
        )
    close[-15:] = tail
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": np.full(260, 1_000_000.0),
        },
        index=index,
    )


def evaluate(data: pd.DataFrame, **overrides: object) -> dict:
    kwargs = {
        "symbol": "TEST",
        "asset_name": "Test Asset",
        "asset_type": "Aktie",
        "market_phase": "Bullenmarkt",
        "buy_signal": 7.0,
        "asset_quality": 7.0,
        "confidence": 7.0,
        "market_score": 5.0,
        "fx_rate": 1.0,
        "original_currency": "EUR",
        "historical_cases": 0,
        "historical_hit_rate": None,
        "event_date": None,
        "now": NOW,
    }
    kwargs.update(overrides)
    return evaluate_swing_trade(data, **kwargs)


def test_confirmed_breakout_setup_is_released_with_exact_levels() -> None:
    result = evaluate(breakout_prices())

    assert result["approved"] is True
    assert result["setup_type"] == "Bestätigter Ausbruch über Widerstand"
    assert "Tagesschluss über" in result["entry_condition"]
    assert result["stop"] < result["entry_reference"] < result["target_1"]
    assert result["crv"] >= DEFAULT_SWING_THRESHOLDS.min_crv
    assert result["max_entry"] >= result["entry_reference"]
    assert "Schwankung" in result["stop_reason"]
    assert result["risk_pct"] <= DEFAULT_SWING_THRESHOLDS.max_stop_distance_pct_stock
    assert result["order_plan"]["plan_version"] == SWING_ORDER_PLAN_VERSION
    assert result["order_plan"]["automatic_order_execution"] is False
    assert len(result["order_plan"]["plan_fingerprint"]) == 64
    assert result["order_plan"]["earliest_entry_day"] > result["order_plan"]["signal_bar_day"]


def test_pullback_setup_requires_support_test_and_exact_daily_close() -> None:
    result = evaluate(pullback_prices())

    assert result["approved"] is True
    assert result["setup_type"] == "Rücksetzer im intakten Aufwärtstrend"
    assert "Test der Unterstützung" in result["entry_condition"]
    assert "Tagesschluss" in result["entry_condition"]
    assert result["order_plan"]["initial_stop_eur"] == pytest.approx(result["stop_eur"])


def test_current_daily_bar_is_never_used_as_a_completed_signal() -> None:
    data = breakout_prices()
    same_day = pd.Timestamp(data.index[-1]).to_pydatetime().replace(hour=18)

    result = evaluate(data, now=same_day)

    assert result["approved"] is False
    assert any("noch nicht sicher abgeschlossen" in reason for reason in result["rejection_reasons"])


def test_same_day_us_bar_is_allowed_only_after_conservative_market_close() -> None:
    data = breakout_prices()
    signal_day = pd.Timestamp(data.index[-1]).date()
    before_close = datetime.combine(signal_day, datetime.min.time(), ZoneInfo("Europe/Berlin")).replace(hour=20)
    after_close = before_close.replace(hour=23)

    early = evaluate(data, now=before_close, region="USA")
    late = evaluate(data, now=after_close, region="USA")

    assert early["approved"] is False
    assert any("noch nicht sicher abgeschlossen" in reason for reason in early["rejection_reasons"])
    assert late["approved"] is True


def test_same_day_crypto_bar_remains_incomplete_until_next_utc_day() -> None:
    data = breakout_prices()
    signal_day = pd.Timestamp(data.index[-1]).date()
    after_midnight_local = datetime.combine(
        signal_day,
        datetime.min.time(),
        ZoneInfo("Europe/Berlin"),
    ).replace(hour=23)

    result = evaluate(data, now=after_midnight_local, region="Global", asset_type="Krypto")

    assert result["approved"] is False
    assert any("noch nicht sicher abgeschlossen" in reason for reason in result["rejection_reasons"])


def test_stale_regional_bar_never_exposes_an_entry_day_before_the_scan() -> None:
    data = breakout_prices()
    signal_day = pd.Timestamp(data.index[-1]).date()
    late_asia_scan = datetime.combine(
        signal_day + timedelta(days=2),
        datetime.min.time(),
        ZoneInfo("Europe/Berlin"),
    ).replace(hour=21)

    result = evaluate(data, now=late_asia_scan, region="Asien")

    assert result["approved"] is True
    earliest = date.fromisoformat(result["order_plan"]["earliest_entry_day"])
    asia_scan_day = late_asia_scan.astimezone(ZoneInfo("Asia/Hong_Kong")).date()
    assert earliest >= asia_scan_day


def test_larsen_toubro_stale_india_bar_is_rejected_instead_of_shown_as_current() -> None:
    data = breakout_prices()
    data.index = pd.bdate_range("2025-08-12", periods=260)
    assert data.index[-1].date() == date(2026, 8, 10)
    scan_time = datetime(2026, 8, 11, 22, 3, tzinfo=ZoneInfo("Europe/Berlin"))

    result = evaluate(
        data,
        symbol="LT.NS",
        asset_name="Larsen and Toubro",
        region="Asien",
        original_currency="INR",
        fx_rate=0.009071,
        now=scan_time,
    )

    assert result["approved"] is False
    assert result["market_validation_status"] == "not_tradable_confirmed"
    assert any("nicht ausreichend aktuell" in reason for reason in result["rejection_reasons"])
    assert any("2026-08-11" in reason for reason in result["rejection_reasons"])


def test_contradictory_daily_high_low_rejects_false_current_price() -> None:
    data = breakout_prices()
    data.iloc[-1, data.columns.get_loc("High")] = data.iloc[-1]["Close"] - 1.0

    result = evaluate(data)

    assert result["approved"] is False
    assert any("Tageshoch/-tief" in reason for reason in result["rejection_reasons"])


@pytest.mark.parametrize(
    ("entered", "symbol", "isin", "expected"),
    [
        ("AAPL", "AAPL", None, True),
        ("DE000BASF111", "BAS.DE", "DE000BASF111", True),
        ("USY5217N1183", "LT.NS", None, False),
    ],
)
def test_trade_confirmation_never_silently_mixes_listings(
    entered: str,
    symbol: str,
    isin: str | None,
    expected: bool,
) -> None:
    accepted, message = validate_traded_listing(
        entered,
        expected_symbol=symbol,
        expected_isin=isin,
    )

    assert accepted is expected
    if not expected:
        assert "nicht verifiziertes Listing" in message


def test_order_plan_assessment_is_conservative_and_never_sends_an_order() -> None:
    plan = evaluate(breakout_prices())["order_plan"]
    observed_day = date.fromisoformat(plan["earliest_entry_day"])
    limit_price = plan["limit_price_original"]

    filled = assess_swing_order_plan(
        plan,
        {"Open": limit_price + 0.5, "Low": limit_price - 0.1, "High": limit_price + 1.0},
        observed_day,
    )
    missed = assess_swing_order_plan(
        plan,
        {"Open": plan["maximum_entry_original"] + 0.1, "Low": limit_price, "High": limit_price + 2.0},
        observed_day,
    )
    cancelled = assess_swing_order_plan(
        plan,
        {
            "Open": limit_price + 0.5,
            "Low": plan["invalidation_original"] - 0.1,
            "High": limit_price + 1.0,
        },
        observed_day,
    )

    assert filled["status"] == "would_fill"
    assert filled["broker_order_sent"] is False
    assert missed["status"] == "missed"
    assert cancelled["status"] == "cancelled"


def test_no_valid_trade_is_not_forced() -> None:
    data = breakout_prices()
    data.loc[:, ["Open", "High", "Low", "Close"]] = 100.0
    result = evaluate(data)

    assert result["approved"] is False
    assert result["rejection_reasons"]


def test_crv_formula_is_central_and_mathematically_exact() -> None:
    metrics = long_trade_metrics(100.0, 95.0, 111.5)

    assert metrics["chance"] == pytest.approx(11.5)
    assert metrics["risk"] == pytest.approx(5.0)
    assert metrics["chance_pct"] == pytest.approx(11.5)
    assert metrics["risk_pct"] == pytest.approx(5.0)
    assert metrics["crv"] == pytest.approx(2.3)


def test_invalid_long_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="Stop < Einstieg < Kursziel"):
        long_trade_metrics(100.0, 101.0, 112.0)


def test_too_low_crv_rejects_otherwise_valid_pullback() -> None:
    result = evaluate(pullback_prices(high_peak=138.0))

    assert result["approved"] is False
    assert any("CRV" in reason for reason in result["rejection_reasons"])


def test_missed_breakout_entry_is_rejected() -> None:
    result = evaluate(breakout_prices(last_close=126.0))

    assert result["approved"] is False
    assert any("verpasst" in reason for reason in result["rejection_reasons"])


def test_missing_exact_breakout_close_is_rejected() -> None:
    result = evaluate(breakout_prices(last_close=120.8))

    assert result["approved"] is False
    assert any("Tagesschluss" in reason for reason in result["rejection_reasons"])


def test_broken_support_before_entry_is_rejected() -> None:
    data = pullback_prices(last_close=118.0)
    data.iloc[-2, data.columns.get_loc("Close")] = 119.0
    data.iloc[-2, data.columns.get_loc("High")] = 119.5
    data.iloc[-2, data.columns.get_loc("Low")] = 118.5
    result = evaluate(data)

    assert result["approved"] is False
    assert any("gebrochen" in reason or "Aufwärtstrend" in reason for reason in result["rejection_reasons"])


def test_insufficient_data_quality_rejects_setup() -> None:
    result = evaluate(breakout_prices().tail(60))

    assert result["approved"] is False
    assert any("Datenqualität" in reason for reason in result["rejection_reasons"])


def test_long_term_asset_quality_is_documented_but_not_a_swing_hard_gate() -> None:
    result = evaluate(breakout_prices(), asset_quality=1.0)

    assert result["approved"] is True
    assert result["asset_quality"] == 1.0
    assert result["asset_quality_hard_gate"] is False
    assert result["asset_quality_role"] == "diagnostic_not_hard_gate"


def test_upcoming_high_event_risk_rejects_trade() -> None:
    result = evaluate(breakout_prices(), event_date=NOW + timedelta(days=2))

    assert result["approved"] is False
    assert any("Ereignisrisiko" in reason for reason in result["rejection_reasons"])


def test_approved_trade_preserves_known_event_date_for_later_guidance() -> None:
    event_date = NOW + timedelta(days=10)

    result = evaluate(breakout_prices(), event_date=event_date)

    assert result["approved"] is True
    assert result["known_event_date_at_signal"] == event_date.date().isoformat()
    assert result["event_days_at_signal"] == 10


def test_setup_identity_uses_completed_signal_bar_not_weekend_scan_day() -> None:
    result = evaluate(breakout_prices())

    assert result["approved"] is True
    assert f"|{result['signal_bar_day']}|" in result["setup_id"]
    if result["order_plan"]["target_2_original"] is None:
        assert result["order_plan"]["target_1_exit_fraction"] == 1.0
        assert result["order_plan"]["target_2_exit_fraction"] == 0.0
    else:
        assert result["order_plan"]["target_1_exit_fraction"] == 0.5
        assert result["order_plan"]["target_2_exit_fraction"] == 0.5


def test_probability_stays_unreliable_below_minimum_history() -> None:
    result = evaluate(breakout_prices(), historical_cases=19, historical_hit_rate=80.0)

    assert result["approved"] is True
    assert result["historical_hit_rate"] is None
    assert result["hit_rate_text"] == "Trefferwahrscheinlichkeit noch nicht belastbar."
    assert result["expected_value_r"] is None


def test_negative_historical_expected_value_rejects_trade() -> None:
    result = evaluate(breakout_prices(), historical_cases=25, historical_hit_rate=10.0)

    assert result["approved"] is False
    assert any("Erwartungswert" in reason for reason in result["rejection_reasons"])
    assert expected_value_in_r(2.0, 10.0) < 0


def test_position_size_respects_risk_and_exposure_limits() -> None:
    result = calculate_position_size(
        10_000.0,
        0.75,
        100.0,
        95.0,
        asset_type="Aktie",
        max_total_exposure_pct=60.0,
        target_1_eur=111.5,
        target_2_eur=118.0,
    )

    assert result["risk_budget_eur"] == pytest.approx(75.0)
    assert result["quantity"] == 15
    assert result["actual_risk_eur"] == pytest.approx(75.0)
    assert result["potential_gain_1_eur"] == pytest.approx(172.5)
    assert result["potential_gain_2_eur"] == pytest.approx(270.0)
    assert "ca. 75.00 €" in result["planned_loss_notice"]
    assert "Kurslücken" in result["planned_loss_notice"]
    assert "15 Anteile" in result["explanation"]


def test_position_size_uses_remaining_dynamic_total_risk_instead_of_trade_count() -> None:
    result = calculate_position_size(
        10_000.0,
        0.5,
        100.0,
        95.0,
        asset_type="Aktie",
        max_total_exposure_pct=50.0,
        max_total_risk_pct=2.0,
        current_risk_eur=175.0,
    )

    assert result["per_trade_risk_budget_eur"] == pytest.approx(50.0)
    assert result["total_open_risk_limit_eur"] == pytest.approx(200.0)
    assert result["remaining_open_risk_before_trade_eur"] == pytest.approx(25.0)
    assert result["quantity"] == 5
    assert result["actual_risk_eur"] == pytest.approx(25.0)


def test_missing_trading_capital_never_invents_quantity() -> None:
    result = calculate_position_size(None, 0.75, 100.0, 95.0, asset_type="Aktie")

    assert result["quantity"] is None
    assert "keine konkrete Stückzahl" in result["explanation"]


def test_final_order_plan_contains_the_same_position_risk_and_gain_values() -> None:
    setup = evaluate(breakout_prices())
    position = calculate_position_size(
        10_000.0,
        0.5,
        setup["entry_reference_eur"],
        setup["stop_eur"],
        asset_type="Aktie",
        target_1_eur=setup["target_1_eur"],
        target_2_eur=setup["target_2_eur"],
    )

    finalized = finalize_swing_order_plan(setup["order_plan"], position)

    assert finalized["position_calculated"] is True
    assert finalized["quantity"] == position["quantity"]
    assert finalized["capital_committed_eur"] == position["position_value_eur"]
    assert finalized["planned_loss_eur"] == position["actual_risk_eur"]
    assert finalized["possible_gain_1_eur"] == position["potential_gain_1_eur"]
    assert len(finalized["plan_fingerprint"]) == 64


def test_two_target_order_plan_uses_partial_then_cumulative_gain() -> None:
    plan = {
        "plan_version": "test-v1",
        "target_1_exit_fraction": 0.5,
        "target_2_exit_fraction": 0.5,
        "target_2_eur": 120.0,
    }
    position = {
        "quantity": 10.0,
        "position_value_eur": 1_000.0,
        "actual_risk_eur": 50.0,
        "potential_gain_1_eur": 100.0,
        "potential_gain_2_eur": 200.0,
        "explanation": "Test",
    }

    finalized = finalize_swing_order_plan(plan, position)

    assert finalized["possible_gain_1_eur"] == 50.0
    assert finalized["possible_gain_2_eur"] == 150.0
    assert "50/50" in finalized["gain_policy"]


@pytest.mark.parametrize("capital", [None, 0.0, -100.0, float("nan"), "ungültig"])
def test_invalid_capital_never_creates_a_position(capital: object) -> None:
    result = calculate_position_size(capital, 0.5, 100.0, 95.0, asset_type="Aktie")

    assert result["quantity"] is None
    assert result["actual_risk_eur"] is None
    assert result["potential_gain_1_eur"] is None


def sample_trade_record() -> dict:
    return {
        "Setup-ID": "TEST|2026-08-02|Ausbruch",
        "Status": "Paper",
        "Maximaler Einstieg EUR": 102.0,
        "Stop-Loss EUR": 95.0,
        "Kursziel 1 EUR": 111.5,
        "Kursziel 2 EUR": 118.0,
        "Gültig bis": "2026-08-09",
    }


def test_manual_open_trade_records_actual_execution_without_order() -> None:
    opened, error = open_trade_record(sample_trade_record(), 100.0, 8.0, NOW)

    assert error is None
    assert opened is not None
    assert opened["Status"] == "Aktiv"
    assert opened["Tatsächlicher Einstieg EUR"] == 100.0
    assert opened["Tatsächliche Stückzahl"] == 8.0
    assert opened["Initialer Stop EUR"] == 95.0
    assert opened["Stop-Vertrag Version"] == SWING_STOP_CONTRACT_VERSION


def test_manual_open_rejects_a_retroactive_entry_before_order_plan_activation() -> None:
    record = sample_trade_record()
    record["Frühester Einstieg"] = "2026-08-03"

    opened, error = open_trade_record(record, 100.0, 8.0, NOW)

    assert opened is None
    assert error is not None
    assert "vor dem frühesten" in error


def test_manual_open_rejects_entry_above_maximum() -> None:
    opened, error = open_trade_record(sample_trade_record(), 103.0, 8.0, NOW)

    assert opened is None
    assert error is not None
    assert "oberhalb" in error


def test_active_trade_actions_cover_hold_target_and_stop() -> None:
    active, _ = open_trade_record(sample_trade_record(), 100.0, 8.0, NOW)
    assert active is not None

    holding = active_trade_snapshot(active, 102.0, NOW)
    target = active_trade_snapshot(active, 112.0, NOW)
    stopped = active_trade_snapshot(active, 94.0, NOW)

    assert holding["action"] == "Halten"
    assert target["action"] == "Teilgewinn prüfen"
    assert stopped["action"] == "Ausstieg empfohlen"
    assert stopped["pnl_eur"] == pytest.approx(-48.0)


def test_active_long_stop_can_only_be_tightened_and_initial_stop_stays_immutable() -> None:
    active, _ = open_trade_record(sample_trade_record(), 100.0, 8.0, NOW)
    assert active is not None

    tightened, error = tighten_active_trade_stop(active, 97.0, NOW + timedelta(days=1))

    assert error is None
    assert tightened is not None
    assert tightened["Initialer Stop EUR"] == 95.0
    assert tightened["Aktueller Stop EUR"] == 97.0

    widened, error = tighten_active_trade_stop(tightened, 96.0, NOW + timedelta(days=2))

    assert widened is None
    assert error is not None
    assert "niemals erweitert" in error


def test_manual_exit_closes_active_trade_and_calculates_result() -> None:
    active, _ = open_trade_record(sample_trade_record(), 100.0, 8.0, NOW)
    assert active is not None
    closed, error = close_trade_record(active, 110.0, NOW + timedelta(days=5))

    assert error is None
    assert closed is not None
    assert closed["Status"] == "Geschlossen"
    assert closed["Realisierter Gewinn/Verlust EUR"] == pytest.approx(80.0)
    assert closed["Realisierter Gewinn/Verlust %"] == pytest.approx(10.0)


def test_expired_paper_setup_is_marked_without_deletion() -> None:
    record = sample_trade_record()
    expired, changed = expire_paper_trade(record, date(2026, 8, 10))

    assert changed is True
    assert expired["Status"] == "Abgelaufen"
    assert expired["Setup-ID"] == record["Setup-ID"]


def test_paper_statistics_include_targets_stops_profit_factor_and_drawdown() -> None:
    history = [
        {
            "Setup-Typ": "Ausbruch",
            "Marktphase": "Bullenmarkt",
            "review_after": {
                "1w": {"return_pct": 10.0, "target_hit": True, "stop_hit": False, "opportunity_cost_pct": 0.0}
            },
        },
        {
            "Setup-Typ": "Rücksetzer",
            "Marktphase": "Bullenmarkt",
            "review_after": {
                "1w": {"return_pct": -5.0, "target_hit": False, "stop_hit": True, "opportunity_cost_pct": 10.0}
            },
        },
        {"Status": "Abgelaufen", "review_after": {}},
    ]

    stats = paper_trade_statistics(history)

    assert stats["evaluated"] == 2
    assert stats["hit_rate_pct"] == pytest.approx(50.0)
    assert stats["average_win_pct"] == pytest.approx(10.0)
    assert stats["average_loss_pct"] == pytest.approx(-5.0)
    assert stats["expected_value_pct"] == pytest.approx(2.5)
    assert stats["profit_factor"] == pytest.approx(2.0)
    assert stats["max_drawdown_pct"] == pytest.approx(-5.0)
    assert stats["target_hits"] == 1
    assert stats["stop_hits"] == 1
    assert stats["expired"] == 1
