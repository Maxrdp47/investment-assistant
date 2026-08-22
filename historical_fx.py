from __future__ import annotations

import math
from typing import Callable

import pandas as pd
import yfinance as yf


HISTORICAL_FX_POLICY_VERSION = "historical-fx-point-in-time-2026.08.09-v1"
FxHistoryLoader = Callable[[str, pd.Timestamp, pd.Timestamp, str], pd.DataFrame]


def _default_history_loader(
    ticker: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    interval: str,
) -> pd.DataFrame:
    return yf.Ticker(ticker).history(
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        interval=interval,
        auto_adjust=False,
        actions=False,
    )


def _positive_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _evidence_from_frame(
    frame: pd.DataFrame,
    *,
    occurred_at: pd.Timestamp,
    ticker: str,
    inverse: bool,
    interval: str,
) -> dict | None:
    if frame.empty or "Close" not in frame:
        return None
    normalized = frame.copy()
    index = pd.to_datetime(normalized.index, errors="coerce", utc=True)
    normalized = normalized.loc[~index.isna()].copy()
    normalized.index = index[~index.isna()]
    closes = pd.to_numeric(normalized["Close"], errors="coerce").dropna()
    closes = closes[closes > 0]
    if closes.empty:
        return None
    if interval == "5m":
        eligible = closes.loc[closes.index <= occurred_at]
    else:
        # A daily bar is labelled with its calendar day although its close can lie
        # after an intraday trade. The previous daily close is therefore the safe
        # point-in-time fallback and never looks beyond the event.
        eligible = closes.loc[[timestamp.date() < occurred_at.date() for timestamp in closes.index]]
    if eligible.empty:
        return None
    observed_at = pd.Timestamp(eligible.index[-1])
    raw_rate = _positive_number(eligible.iloc[-1])
    if raw_rate is None:
        return None
    rate = 1.0 / raw_rate if inverse else raw_rate
    return {
        "policy_version": HISTORICAL_FX_POLICY_VERSION,
        "rate_to_eur": rate,
        "pair_ticker": ticker,
        "inverse_quote": inverse,
        "observed_at": observed_at.isoformat(),
        "interval": interval,
        "quality": "intraday_at_or_before_event" if interval == "5m" else "previous_daily_close",
        "source": f"Yahoo Finance/yfinance {interval}",
    }


def historical_fx_evidence(
    currency: str,
    occurred_at: object,
    *,
    history_loader: FxHistoryLoader = _default_history_loader,
) -> dict | None:
    """Return reproducible point-in-time FX evidence without using a future quote."""
    normalized_currency = str(currency or "EUR").strip().upper()
    event_time = _utc_timestamp(occurred_at)
    if normalized_currency == "EUR":
        return {
            "policy_version": HISTORICAL_FX_POLICY_VERSION,
            "rate_to_eur": 1.0,
            "pair_ticker": "EUR",
            "inverse_quote": False,
            "observed_at": event_time.isoformat(),
            "interval": "identity",
            "quality": "identity",
            "source": "EUR identity",
        }
    definitions = (
        (f"{normalized_currency}EUR=X", False),
        (f"EUR{normalized_currency}=X", True),
    )
    windows = (
        ("5m", event_time - pd.Timedelta(days=2), event_time + pd.Timedelta(days=1)),
        ("1d", event_time - pd.Timedelta(days=8), event_time + pd.Timedelta(days=2)),
    )
    for interval, start, end in windows:
        for ticker, inverse in definitions:
            try:
                frame = history_loader(ticker, start, end, interval)
            except Exception:
                continue
            evidence = _evidence_from_frame(
                frame,
                occurred_at=event_time,
                ticker=ticker,
                inverse=inverse,
                interval=interval,
            )
            if evidence is not None:
                return evidence
    return None
