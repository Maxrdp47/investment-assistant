from __future__ import annotations

import math
from datetime import datetime

import pandas as pd

from trading_assistant import completed_daily_signal_bar


SWING_MONITOR_VERSION = "swing-trade-monitor-2026.08.09-v1"


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def swing_market_context_from_daily_bars(
    bars: pd.DataFrame,
    *,
    fx_rate_to_eur: float,
    evaluated_at: object,
    asset_type: str,
    region: str | None,
) -> dict:
    """Build leakage-safe structure and volume context from completed daily bars."""
    fx_rate = _number(fx_rate_to_eur)
    if fx_rate is None or fx_rate <= 0:
        return {"version": SWING_MONITOR_VERSION, "data_quality": "nicht belastbar", "reason": "FX-Kurs fehlt."}
    required = {"Open", "High", "Low", "Close"}
    if bars.empty or not required.issubset(bars.columns):
        return {"version": SWING_MONITOR_VERSION, "data_quality": "nicht belastbar", "reason": "OHLC-Daten fehlen."}
    now = pd.Timestamp(evaluated_at)
    evaluated_datetime = now.to_pydatetime()
    frame = bars.copy().sort_index()
    index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame.loc[~index.isna()].copy()
    frame.index = index[~index.isna()]
    complete_mask = [
        completed_daily_signal_bar(
            pd.Timestamp(timestamp).date(),
            evaluated_datetime,
            asset_type=asset_type,
            region=region,
        )
        for timestamp in frame.index
    ]
    frame = frame.loc[complete_mask].copy()
    for column in required | {"Volume"}:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=list(required))
    if len(frame) < 21:
        return {
            "version": SWING_MONITOR_VERSION,
            "data_quality": "nicht belastbar",
            "reason": "Weniger als 21 vollständig abgeschlossene Tageskerzen verfügbar.",
            "completed_bars": len(frame),
        }
    latest = frame.iloc[-1]
    previous_20 = frame.iloc[-21:-1]
    previous_close = float(frame.iloc[-2]["Close"])
    close = float(latest["Close"])
    open_price = float(latest["Open"])
    support = float(previous_20["Low"].min())
    resistance = float(previous_20["High"].max())
    sma_20 = float(frame["Close"].tail(20).mean())
    sma_50 = float(frame["Close"].tail(50).mean()) if len(frame) >= 50 else None
    relative_volume = None
    if "Volume" in frame and frame["Volume"].tail(21).notna().all():
        baseline_volume = float(frame["Volume"].iloc[-21:-1].mean())
        if baseline_volume > 0:
            relative_volume = float(latest["Volume"]) / baseline_volume
    five_day_return = None
    if len(frame) >= 6 and float(frame.iloc[-6]["Close"]) > 0:
        five_day_return = close / float(frame.iloc[-6]["Close"]) - 1
    structure_break = close < support
    selling_volume = close < open_price and relative_volume is not None and relative_volume >= 1.5
    trend_broken = close < sma_20 and (sma_50 is None or sma_20 < sma_50)
    return {
        "version": SWING_MONITOR_VERSION,
        "data_quality": "hoch" if len(frame) >= 60 else "eingeschränkt",
        "completed_bars": len(frame),
        "observed_bar_day": pd.Timestamp(frame.index[-1]).date().isoformat(),
        "close_eur": close * fx_rate,
        "open_eur": open_price * fx_rate,
        "support_20d_eur": support * fx_rate,
        "resistance_20d_eur": resistance * fx_rate,
        "sma_20_eur": sma_20 * fx_rate,
        "sma_50_eur": sma_50 * fx_rate if sma_50 is not None else None,
        "relative_volume": relative_volume,
        "gap_pct": (open_price / previous_close - 1) * 100 if previous_close > 0 else None,
        "five_day_return_pct": five_day_return * 100 if five_day_return is not None else None,
        "structure_break": structure_break,
        "selling_volume": selling_volume,
        "high_volume_structure_break": structure_break and selling_volume,
        "trend_broken": trend_broken,
        "checked_factors": ["Kursstruktur", "20-Tage-Unterstützung", "Trend", "Gap", "relatives Volumen"],
        "unavailable_factors": ["bestätigte schwere Nachrichten", "kommende Unternehmensereignisse", "Branchenvergleich"],
    }
