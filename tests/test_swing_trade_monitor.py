from __future__ import annotations

from datetime import datetime

import pandas as pd

from swing_trade_monitor import swing_market_context_from_daily_bars


def daily_bars(*, break_support: bool = False, high_volume: bool = False) -> pd.DataFrame:
    index = pd.date_range("2026-05-01", periods=80, freq="D")
    closes = [100.0 + day * 0.2 for day in range(80)]
    opens = [value - 0.1 for value in closes]
    highs = [value + 1.0 for value in closes]
    lows = [value - 1.0 for value in closes]
    volumes = [1_000_000.0] * 80
    if break_support:
        closes[-1] = min(lows[-21:-1]) - 1.0
        opens[-1] = closes[-1] + 2.0
        lows[-1] = closes[-1] - 0.5
        highs[-1] = opens[-1] + 0.5
    if high_volume:
        volumes[-1] = 2_000_000.0
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=index,
    )


def test_market_context_detects_high_volume_structure_break() -> None:
    context = swing_market_context_from_daily_bars(
        daily_bars(break_support=True, high_volume=True),
        fx_rate_to_eur=0.9,
        evaluated_at=datetime.fromisoformat("2026-08-09T18:30:00+02:00"),
        asset_type="Aktie",
        region="Europa",
    )

    assert context["data_quality"] == "hoch"
    assert context["structure_break"] is True
    assert context["high_volume_structure_break"] is True
    assert context["relative_volume"] == 2.0


def test_same_day_bar_before_regional_close_is_excluded() -> None:
    frame = daily_bars()
    frame.loc[pd.Timestamp("2026-08-09")] = {
        "Open": 10.0,
        "High": 11.0,
        "Low": 5.0,
        "Close": 6.0,
        "Volume": 9_000_000.0,
    }
    context = swing_market_context_from_daily_bars(
        frame,
        fx_rate_to_eur=1.0,
        evaluated_at=datetime.fromisoformat("2026-08-09T16:00:00+02:00"),
        asset_type="Aktie",
        region="Europa",
    )

    assert context["observed_bar_day"] == "2026-07-19"
    assert context["structure_break"] is False


def test_short_or_incomplete_history_is_explicitly_not_reliable() -> None:
    context = swing_market_context_from_daily_bars(
        daily_bars().tail(10),
        fx_rate_to_eur=1.0,
        evaluated_at="2026-08-09T20:00:00+02:00",
        asset_type="Aktie",
        region="Europa",
    )

    assert context["data_quality"] == "nicht belastbar"
    assert context["completed_bars"] == 10
