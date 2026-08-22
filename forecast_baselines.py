from __future__ import annotations

import math
from typing import Iterable


BASELINE_SCHEMA_VERSION = "entry-baselines-2026.08.09-v1"
SIMPLE_TREND_LOOKBACK_TRADING_DAYS = 20
SIMPLE_TREND_SIDEWAYS_BAND_PCT = 1.0


def direction_from_return(return_pct: float, *, sideways_band_pct: float = 3.0) -> str:
    value = float(return_pct)
    if value > float(sideways_band_pct):
        return "Steigend"
    if value < -float(sideways_band_pct):
        return "Fallend"
    return "Seitwärts"


def direction_hit(expected_direction: object, actual_return_pct: float | None) -> int | None:
    if actual_return_pct is None:
        return None
    value = float(actual_return_pct)
    direction = str(expected_direction or "")
    if direction == "Steigend":
        return int(value > 0)
    if direction == "Fallend":
        return int(value < 0)
    if direction == "Seitwärts":
        return int(abs(value) <= 3)
    return None


def simple_trend_snapshot(closes: Iterable[object]) -> dict:
    values: list[float] = []
    for item in closes:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            values.append(value)
    required = SIMPLE_TREND_LOOKBACK_TRADING_DAYS + 1
    if len(values) < required:
        return {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "status": "missing",
            "lookback_trading_days": SIMPLE_TREND_LOOKBACK_TRADING_DAYS,
            "reason": f"Mindestens {required} gültige Schlusskurse erforderlich.",
        }
    start = values[-required]
    end = values[-1]
    return_pct = (end - start) / start * 100
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "status": "available",
        "lookback_trading_days": SIMPLE_TREND_LOOKBACK_TRADING_DAYS,
        "sideways_band_pct": SIMPLE_TREND_SIDEWAYS_BAND_PCT,
        "return_pct": round(return_pct, 6),
        "predicted_direction": direction_from_return(
            return_pct,
            sideways_band_pct=SIMPLE_TREND_SIDEWAYS_BAND_PCT,
        ),
    }


def market_benchmark_definition(asset_type: object, region: object) -> dict:
    asset_type_text = str(asset_type or "").strip()
    region_text = str(region or "").strip().lower()
    if asset_type_text == "Krypto":
        ticker, name, currency = "BTC-EUR", "Bitcoin in Euro", "EUR"
    elif asset_type_text == "ETF":
        ticker, name, currency = "ACWI", "MSCI ACWI ETF", "USD"
    elif any(token in region_text for token in ("europa", "europe", "deutsch")):
        ticker, name, currency = "EXSA.DE", "STOXX Europe 600 ETF", "EUR"
    elif any(token in region_text for token in ("asien", "asia", "japan", "china", "hongkong")):
        ticker, name, currency = "AAXJ", "MSCI Asia ex Japan ETF", "USD"
    elif region_text in {"usa", "us", "vereinigte staaten", "nordamerika"} or "amerika" in region_text:
        ticker, name, currency = "SPY", "S&P 500 ETF", "USD"
    else:
        ticker, name, currency = "ACWI", "MSCI ACWI ETF", "USD"
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "selection_rule": "asset_type_and_region_v1",
    }
