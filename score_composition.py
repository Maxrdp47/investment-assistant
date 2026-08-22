from __future__ import annotations

import numpy as np

from analysis_models import AssetProfile, ModuleScore, RiskReward

def score_weight_rows(profile: AssetProfile) -> list[dict[str, str]]:
    descriptions = {
        "Technik": "Trend, Momentum, RSI, MACD, Volumen, Unterstützungen und Widerstände.",
        "Fundamentaldaten": "Langfristige Qualität des Assets; bei Krypto Netzwerk-/Adoptionsnähe statt klassischer Unternehmensdaten.",
        "Makro": "Zinsen, Nasdaq, Dollar und weitere Makro-Proxies.",
        "News": "Aktuelle Yahoo-Finance-News und einfaches Sentiment.",
        "CRV": "Chance-Risiko-Verhältnis aus nächster Unterstützung und nächstem Widerstand.",
    }
    return [
        {
            "Baustein": name,
            "Gewichtung": f"{weight * 100:.0f}%",
            "Bedeutung": descriptions.get(name, "Bewertungsbaustein."),
        }
        for name, weight in profile.weights.items()
    ]


def weighted_total_score(
    technical: ModuleScore,
    fundamentals: ModuleScore,
    macro: ModuleScore,
    news: ModuleScore,
    risk_reward: RiskReward,
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    parts = {
        "Technik": technical.score,
        "Fundamentaldaten": fundamentals.score,
        "Makro": macro.score,
        "News": news.score,
        "CRV": risk_reward.score,
    }
    weights = weights or {"Technik": 0.30, "Fundamentaldaten": 0.30, "Makro": 0.20, "News": 0.10, "CRV": 0.10}
    total = sum(parts[name] * weights.get(name, 0.0) for name in parts)
    return round(float(total), 1), parts


def score_from_optional(values: list[float], neutral_if_empty: float = 5.0) -> float:
    if not values:
        return neutral_if_empty
    return round(float(np.mean(values)), 1)
