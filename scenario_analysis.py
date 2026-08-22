from __future__ import annotations

import numpy as np
import pandas as pd

from analysis_models import MarketPhase, ModuleScore, ResearchModule, RiskReward
from currency_utils import format_display_money
from technical_analysis import clamp, value_or_none


def scenario_probabilities(
    buy_signal: ModuleScore,
    asset_quality: ModuleScore,
    risk_reward: RiskReward,
    market_phase: MarketPhase,
    close: float,
    supports: list[float],
    resistances: list[float],
    latest: pd.Series,
) -> tuple[int, int, int]:
    bull = 25 + int((buy_signal.score - 5) * 4) + int((asset_quality.score - 5) * 2)
    bear = 25 + int((5 - buy_signal.score) * 4)
    if risk_reward.ratio is not None and risk_reward.ratio >= 2:
        bull += 8
        bear -= 5
    elif risk_reward.ratio is not None and risk_reward.ratio < 1:
        bull -= 4
        bear += 6
    if market_phase.phase == "Bullenmarkt":
        bull += 8
        bear -= 5
    if market_phase.phase == "Bärenmarkt":
        bull -= 8
        bear += 10
    if market_phase.phase == "Bodenbildungsphase":
        bull += 3
        bear += 2

    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    if sma_50 is not None and sma_200 is not None:
        if close > sma_50 > sma_200:
            bull += 8
            bear -= 4
        elif close < sma_50 < sma_200:
            bull -= 8
            bear += 8

    valid_supports = [level for level in supports if level < close]
    valid_resistances = [level for level in resistances if level > close]
    if valid_supports:
        support_distance = (close - valid_supports[0]) / close
        if support_distance <= 0.06:
            bull += 4
            bear -= 2
        elif support_distance > 0.18:
            bear += 4
    else:
        bear += 5

    if valid_resistances:
        resistance_room = (valid_resistances[0] - close) / close
        if resistance_room >= 0.15:
            bull += 5
        elif resistance_room <= 0.04:
            bull -= 4
            bear += 3
    else:
        bull -= 3

    volatility = value_or_none(latest.get("Volatility"))
    if volatility is not None:
        if volatility > 0.75:
            bull -= 3
            bear += 6
        elif volatility < 0.25:
            bear -= 3

    bull = int(np.clip(bull, 10, 65))
    bear = int(np.clip(bear, 10, 65))
    base = 100 - bull - bear
    if base < 20:
        diff = 20 - base
        bull = max(10, bull - diff // 2)
        bear = max(10, bear - (diff - diff // 2))
        base = 100 - bull - bear
    return bull, base, bear


def numeric_scenario_levels(
    close: float,
    supports: list[float],
    resistances: list[float],
    buy_signal_score: float,
) -> dict[str, float | None]:
    """Expose the same support/resistance targets used by visible and stored scenarios."""
    valid_supports = [float(level) for level in supports if level < close]
    valid_resistances = [float(level) for level in resistances if level > close]
    first_support = valid_supports[0] if valid_supports else None
    second_support = valid_supports[1] if len(valid_supports) > 1 else first_support
    first_resistance = valid_resistances[0] if valid_resistances else None
    second_resistance = valid_resistances[1] if len(valid_resistances) > 1 else first_resistance
    base_target = (
        first_resistance
        if buy_signal_score >= 6.5
        else close
        if buy_signal_score >= 5
        else first_support
    )
    available = [
        value
        for value in [second_support, base_target, second_resistance]
        if value is not None
    ]
    return {
        "bull": second_resistance,
        "base": base_target,
        "bear": second_support,
        "low": min(available) if available else None,
        "high": max(available) if available else None,
        "support": first_support,
        "resistance": first_resistance,
    }


def build_scenarios(
    close: float,
    supports: list[float],
    resistances: list[float],
    buy_signal: ModuleScore,
    asset_quality: ModuleScore,
    risk_reward: RiskReward,
    market_phase: MarketPhase,
    latest: pd.Series,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
) -> list[dict]:
    bull_p, base_p, bear_p = scenario_probabilities(
        buy_signal,
        asset_quality,
        risk_reward,
        market_phase,
        close,
        supports,
        resistances,
        latest,
    )
    levels = numeric_scenario_levels(close, supports, resistances, buy_signal.score)
    bull_target = (
        format_display_money(levels["bull"], original_currency, fx_rate, currency_mode)
        if levels["bull"]
        else "Daten nicht verfügbar"
    )
    base_target_text = (
        format_display_money(levels["base"], original_currency, fx_rate, currency_mode)
        if levels["base"]
        else "Daten nicht verfügbar"
    )
    bear_target = (
        format_display_money(levels["bear"], original_currency, fx_rate, currency_mode)
        if levels["bear"]
        else "Daten nicht verfügbar"
    )
    volatility = value_or_none(latest.get("Volatility"))
    volatility_text = (
        f"Volatilität {volatility * 100:.1f}%"
        if volatility is not None
        else "Volatilität: Daten nicht verfügbar"
    )
    return [
        {
            "Szenario": "Bull-Case",
            "Was müsste passieren?": (
                "Trend bestätigt sich, MACD bleibt positiv, Volumen zieht an und der nächste Widerstand wird überwunden."
            ),
            "Kursziel": bull_target,
            "Wahrscheinlichkeit": f"{bull_p}%",
            "Wichtigste Treiber": (
                f"{market_phase.phase}, CRV {risk_reward.score:.1f}/10, {volatility_text}."
            ),
        },
        {
            "Szenario": "Base-Case",
            "Was müsste passieren?": (
                "Der Kurs bleibt in der aktuellen Struktur und reagiert an Unterstützung und Widerstand wie bisher."
            ),
            "Kursziel": base_target_text,
            "Wahrscheinlichkeit": f"{base_p}%",
            "Wichtigste Treiber": (
                "Wahrscheinlichstes Szenario bei gemischten Signalen und intakter Kursstruktur."
            ),
        },
        {
            "Szenario": "Bear-Case",
            "Was müsste passieren?": (
                "Unterstützung bricht, Momentum bleibt schwach oder das Makro-/News-Umfeld verschlechtert sich."
            ),
            "Kursziel": bear_target,
            "Wahrscheinlichkeit": f"{bear_p}%",
            "Wichtigste Treiber": (
                "Risiko steigt besonders bei Bruch der nächsten Unterstützung oder hoher Volatilität."
            ),
        },
    ]


def research_expected_value(
    close: float,
    supports: list[float],
    resistances: list[float],
    buy_signal: ModuleScore,
    asset_quality: ModuleScore,
    risk_reward: RiskReward,
    market_phase: MarketPhase,
    latest: pd.Series,
) -> ResearchModule:
    bull_p, base_p, bear_p = scenario_probabilities(
        buy_signal,
        asset_quality,
        risk_reward,
        market_phase,
        close,
        supports,
        resistances,
        latest,
    )
    valid_resistances = [level for level in resistances if level > close]
    valid_supports = [level for level in supports if level < close]
    bull_return = (
        ((valid_resistances[1] if len(valid_resistances) > 1 else valid_resistances[0]) - close)
        / close
        if valid_resistances
        else 0.12
    )
    base_return = (
        (valid_resistances[0] - close) / close * 0.45 if valid_resistances else 0.03
    )
    bear_return = (
        ((valid_supports[1] if len(valid_supports) > 1 else valid_supports[0]) - close) / close
        if valid_supports
        else -0.10
    )
    expected_return = (
        bull_return * bull_p / 100
        + base_return * base_p / 100
        + bear_return * bear_p / 100
    )
    expected_loss = abs(min(bear_return, 0)) * bear_p / 100
    score = clamp(5 + expected_return * 25 - expected_loss * 10)
    details = [
        f"Bull-Case: {bull_return * 100:+.1f}% mit {bull_p}% Wahrscheinlichkeit.",
        f"Base-Case: {base_return * 100:+.1f}% mit {base_p}% Wahrscheinlichkeit.",
        f"Bear-Case: {bear_return * 100:+.1f}% mit {bear_p}% Wahrscheinlichkeit.",
        f"Erwartete Rendite: {expected_return * 100:+.1f}%.",
        f"Erwarteter Verlustbeitrag: {expected_loss * 100:.1f}%.",
    ]
    summary = (
        f"Expected-Value-Score {score:.1f}/10. "
        f"Erwartungswert {expected_return * 100:+.1f}% statt perfektem Einstieg."
    )
    beginner = (
        "Expected Value fragt, ob Chance und Wahrscheinlichkeit höher wiegen als das Risiko. "
        "Ein perfekter Einstieg ist nicht zwingend nötig."
    )
    return ResearchModule("Expected Value", round(score, 1), summary, details, beginner)
