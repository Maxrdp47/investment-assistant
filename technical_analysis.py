from __future__ import annotations

import math

import numpy as np
import pandas as pd

from analysis_models import MarketPhase, RiskReward


def value_or_none(value: object) -> float | None:
    """Convert a scalar value to float while treating missing values as unavailable."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        converted = float(value)
        return converted if math.isfinite(converted) else None
    except (TypeError, ValueError):
        return None


def clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


def pct_distance(price: float, level: float | None) -> float | None:
    if level is None or price == 0:
        return None
    return (price - level) / price


def percent_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.1f}%"


def calculate_indicators(data: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Add the technical indicators used by both the UI and background analysis."""
    df = data.copy()
    close = df["Close"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    df["SMA_50"] = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()
    df["Volume_SMA_20"] = df["Volume"].rolling(20).mean() if "Volume" in df else np.nan

    annualization = {"1d": 252, "1wk": 52, "1mo": 12}.get(interval, 252)
    returns = close.pct_change()
    df["Volatility"] = returns.rolling(20).std() * math.sqrt(annualization)
    return df


def local_levels(series: pd.Series, mode: str, window: int = 3) -> list[float]:
    """Return local lows or highs sorted by relevance to the current price."""
    values = series.dropna()
    if len(values) < window * 2 + 1:
        return []

    neighborhood = values.rolling(window * 2 + 1, center=True)
    if mode == "support":
        extrema = neighborhood.min()
    elif mode == "resistance":
        extrema = neighborhood.max()
    else:
        return []
    levels = values[values.eq(extrema)].astype(float).tolist()

    current_price = float(values.iloc[-1])
    if mode == "support":
        filtered = [level for level in levels if level < current_price]
    else:
        filtered = [level for level in levels if level > current_price]

    filtered.sort(key=lambda level: abs(level - current_price))
    return filtered[:3]


def calculate_risk_reward(close: float, supports: list[float], resistances: list[float]) -> RiskReward:
    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None
    risk_pct = (nearest_support - close) / close if nearest_support else None
    reward_pct = (nearest_resistance - close) / close if nearest_resistance else None

    ratio = None
    score = 5.0
    if risk_pct is not None and reward_pct is not None and risk_pct < 0 and reward_pct > 0:
        ratio = reward_pct / abs(risk_pct)
        score = clamp(ratio / 3 * 10)
        summary = (
            f"Risiko bis Unterstützung {percent_text(risk_pct)}, Potenzial bis Widerstand "
            f"{percent_text(reward_pct)}, CRV {ratio:.2f}."
        )
    elif risk_pct is not None:
        summary = (
            f"Nächste Unterstützung liegt {percent_text(risk_pct)} entfernt; "
            "kein klarer Widerstand oberhalb erkannt."
        )
        score = 5.5 if abs(risk_pct) <= 0.06 else 4.0
    elif reward_pct is not None:
        summary = (
            f"Nächster Widerstand liegt {percent_text(reward_pct)} entfernt; "
            "keine klare Unterstützung unterhalb erkannt."
        )
        score = 4.5
    else:
        summary = "Keine belastbaren Unterstützungs- und Widerstandszonen für ein CRV erkannt."
        score = 4.0

    return RiskReward(
        risk_pct=risk_pct,
        reward_pct=reward_pct,
        ratio=ratio,
        score=round(score, 1),
        summary=summary,
    )


def detect_market_phase(df: pd.DataFrame) -> MarketPhase:
    latest = df.dropna(subset=["Close"]).iloc[-1]
    close = float(latest["Close"])
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    rsi = value_or_none(latest.get("RSI_14"))
    macd = value_or_none(latest.get("MACD"))
    signal = value_or_none(latest.get("MACD_Signal"))

    recent = df.dropna(subset=["Close"]).tail(120)
    recent_high = float(recent["Close"].max()) if not recent.empty else close
    recent_low = float(recent["Close"].min()) if not recent.empty else close
    drawdown = (close - recent_high) / recent_high if recent_high else 0.0
    rebound = (close - recent_low) / recent_low if recent_low else 0.0
    range_width = (recent_high - recent_low) / close if close else 0.0

    macd_positive = macd is not None and signal is not None and macd > signal
    macd_negative = macd is not None and signal is not None and macd < signal
    uptrend = sma_50 is not None and close > sma_50 and (sma_200 is None or sma_50 > sma_200)
    downtrend = sma_50 is not None and close < sma_50 and (sma_200 is None or sma_50 < sma_200)

    if uptrend and drawdown <= -0.08:
        phase = "Korrektur innerhalb eines Aufwärtstrends"
        summary = "Der übergeordnete Trend ist positiv, aber der Kurs korrigiert deutlich vom jüngsten Hoch."
    elif downtrend and (rsi is None or rsi < 45) and macd_negative:
        phase = "Bärenmarkt"
        summary = "Kurs und gleitende Durchschnitte zeigen abwärts, Momentum bestätigt die Schwäche."
    elif uptrend and (rsi is None or rsi >= 45) and not macd_negative:
        phase = "Bullenmarkt"
        summary = "Kursstruktur, Trend und Momentum sprechen überwiegend für einen Aufwärtstrend."
    elif downtrend and rebound > 0.06 and (rsi is not None and rsi >= 30) and not macd_negative:
        phase = "Bodenbildungsphase"
        summary = "Der Kurs kommt aus einer schwachen Phase, stabilisiert sich aber über den letzten Tiefs."
    elif range_width <= 0.16:
        phase = "Seitwärtsmarkt"
        summary = "Der Kurs bewegt sich in einer relativ engen Spanne ohne klaren Trend."
    else:
        phase = "Bodenbildungsphase" if macd_positive and rebound > 0.04 else "Seitwärtsmarkt"
        summary = "Die Signale sind gemischt; der Markt sucht noch eine klare Richtung."

    floor_seen = 35
    retest = 30
    new_low = 20
    strong_recovery = 15
    if phase == "Bullenmarkt":
        floor_seen, retest, new_low, strong_recovery = 45, 20, 5, 30
    elif phase == "Korrektur innerhalb eines Aufwärtstrends":
        floor_seen, retest, new_low, strong_recovery = 45, 30, 10, 15
    elif phase == "Bodenbildungsphase":
        floor_seen, retest, new_low, strong_recovery = 45, 25, 15, 15
    elif phase == "Bärenmarkt":
        floor_seen, retest, new_low, strong_recovery = 20, 35, 30, 15
    elif phase == "Seitwärtsmarkt":
        floor_seen, retest, new_low, strong_recovery = 35, 35, 10, 20

    if rsi is not None and rsi < 30:
        floor_seen += 8
        retest -= 3
        new_low -= 5
        strong_recovery += 2
    if macd_positive:
        floor_seen += 8
        retest -= 5
        new_low -= 3
        strong_recovery += 4
    if macd_negative:
        floor_seen -= 8
        retest += 5
        new_low += 3
        strong_recovery -= 2
    if drawdown < -0.2:
        new_low += 6
        floor_seen -= 3
        strong_recovery -= 3

    values = np.array(
        [max(5, floor_seen), max(5, retest), max(5, new_low), max(5, strong_recovery)],
        dtype=float,
    )
    values = np.round(values / values.sum() * 100).astype(int)
    values[0] += 100 - int(values.sum())
    probabilities = {
        "Boden bereits gesehen": int(values[0]),
        "Erneuter Test / weitere Korrektur": int(values[1]),
        "Neues Tief": int(values[2]),
        "Starke Erholung / Ausbruch": int(values[3]),
    }
    return MarketPhase(phase=phase, summary=summary, probabilities=probabilities)


__all__ = [
    "calculate_indicators",
    "calculate_risk_reward",
    "clamp",
    "detect_market_phase",
    "local_levels",
    "pct_distance",
    "percent_text",
    "value_or_none",
]
