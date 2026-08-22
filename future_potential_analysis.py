from __future__ import annotations

import numpy as np

from analysis_models import AssetProfile, ModuleScore, ResearchModule
from fundamental_analysis import data_missing, score_profitability_metric
from technical_analysis import clamp, value_or_none


def _score_from_optional(values: list[float], neutral_if_empty: float = 5.0) -> float:
    if not values:
        return neutral_if_empty
    return round(float(np.mean(values)), 1)


def research_future_potential(
    info: dict,
    profile: AssetProfile,
    asset_quality: ModuleScore,
    news: ModuleScore,
) -> ResearchModule:
    details: list[str] = []
    points: list[float] = [asset_quality.score]
    revenue_growth = value_or_none(info.get("revenueGrowth"))
    earnings_growth = value_or_none(info.get("earningsGrowth"))
    operating_margin = value_or_none(info.get("operatingMargins"))
    if revenue_growth is not None:
        score = clamp(5 + revenue_growth * 18)
        points.append(score)
        details.append(
            f"Umsatzwachstum: {revenue_growth * 100:.1f}% -> Zukunftspotenzial {score:.1f}/10."
        )
    else:
        details.append(data_missing("Umsatzwachstum"))
    if earnings_growth is not None:
        score = clamp(5 + earnings_growth * 16)
        points.append(score)
        details.append(
            f"Gewinnwachstum: {earnings_growth * 100:.1f}% -> Zukunftspotenzial {score:.1f}/10."
        )
    else:
        details.append(data_missing("Gewinnwachstum"))
    if operating_margin is not None:
        score = score_profitability_metric(operating_margin)
        points.append(score)
        details.append(
            f"Operative Marge: {operating_margin * 100:.1f}% -> Skalierbarkeit {score:.1f}/10."
        )
    else:
        details.append(data_missing("operative Marge"))
    if profile.asset_type == "Aktie":
        details.append(
            "Langfristige Produkt-/KI-/Software-Chance: nur indirekt über Wachstum, Margen und News ableitbar; "
            "Spezialdaten nicht verfügbar."
        )
    elif profile.asset_type == "Krypto":
        details.append("Netzwerk-/Adoptionsdaten: Daten nicht verfügbar.")
    if news.score >= 6.5:
        points.append(6.5)
        details.append("News-Sentiment stützt das Zukunftsnarrativ moderat.")
    elif news.score <= 4:
        points.append(4.0)
        details.append("News-Sentiment belastet das Zukunftsnarrativ.")
    score = _score_from_optional(points)
    summary = (
        f"Zukunftspotenzial {score}/10 aus Qualität, Wachstum, Margen und verfügbarem Sentiment."
    )
    beginner = (
        "Zukunftspotenzial fragt, ob das Asset langfristig wachsen kann. "
        "Fehlende Spezialdaten werden nicht erfunden."
    )
    return ResearchModule("Zukunftspotenzial", score, summary, details, beginner)


def research_priced_expectations(
    info: dict,
    profile: AssetProfile,
    valuation: ResearchModule,
    momentum: ResearchModule,
    news: ModuleScore,
) -> ResearchModule:
    details: list[str] = []
    points: list[float] = []
    valuation_score = valuation.score
    if valuation_score is not None:
        risk = clamp(10 - valuation_score)
        points.append(risk)
        details.append(
            f"Bewertungsniveau: Bewertungsscore {valuation_score:.1f}/10 -> "
            f"eingepreiste Erwartungen {risk:.1f}/10."
        )
    else:
        details.append("Bewertungsniveau: Daten nicht verfügbar.")
    if momentum.score is not None:
        risk = (
            7.0
            if momentum.score >= 7.5
            else 5.5
            if momentum.score >= 6
            else 4.0
            if momentum.score >= 4
            else 3.0
        )
        points.append(risk)
        details.append(
            f"Momentum: {momentum.score:.1f}/10 -> Optimismus-/Momentum-Anteil {risk:.1f}/10."
        )
    else:
        details.append("Momentum: Daten nicht verfügbar.")
    if news.score >= 7:
        points.append(6.5)
        details.append("Medien-/News-Sentiment sehr positiv -> höhere eingepreiste Erwartungen.")
    elif news.score <= 4:
        points.append(3.5)
        details.append("Medien-/News-Sentiment schwach -> weniger Euphorie eingepreist.")
    else:
        points.append(4.8)
        details.append("Medien-/News-Sentiment neutral bis gemischt.")
    recommendation_key = str(info.get("recommendationKey", "") or "").replace("_", " ").strip()
    if recommendation_key:
        details.append(f"Analysteneuphorie/Yahoo-Empfehlung: {recommendation_key}.")
    else:
        details.append("Analysteneuphorie: Daten nicht verfügbar.")
    details.extend(
        [
            "IPO-Hype: Daten nicht verfügbar.",
            "KI-Hype: Daten nicht verfügbar.",
            "Kapitalzuflüsse: Daten nicht verfügbar.",
            "Sentiment-Spezialdaten: Daten nicht verfügbar.",
        ]
    )
    score = _score_from_optional(points)
    summary = (
        f"Eingepreiste Erwartungen {score}/10. Hoher Wert bedeutet: viel Optimismus ist bereits im Kurs enthalten."
    )
    beginner = "Dieses Modul warnt, wenn ein fantastisches Unternehmen bereits sehr optimistisch bewertet ist."
    return ResearchModule("Eingepreiste Erwartungen", score, summary, details, beginner)
