from __future__ import annotations

import numpy as np
import pandas as pd

from analysis_models import ResearchModule
from technical_analysis import clamp, value_or_none


def fundamental_context_since_high(
    asset_type: str,
    info: dict | None,
) -> tuple[str, bool | None]:
    """Describe whether current fundamentals support a drawdown without inventing history."""
    info = info or {}
    if asset_type == "ETF":
        return (
            "Bei ETFs wird der Rückgang über Marktbreite, Kosten, Struktur und den zugrunde liegenden Index eingeordnet. "
            "Historische Fundamentaldaten eines einzelnen Unternehmens sind hier nicht anwendbar.",
            None,
        )
    if asset_type == "Krypto":
        return (
            "Der Kursrückgang wird als Markt- und Zykluskontext verwendet. Historische On-Chain-, Flow- und "
            "Liquiditätsdaten seit dem Hoch sind in der vorhandenen Datenquelle nicht verfügbar.",
            None,
        )
    if asset_type != "Aktie":
        return (
            "Ein belastbarer Vergleich der fundamentalen Entwicklung seit dem Hoch ist für diesen Asset-Typ nicht verfügbar.",
            None,
        )

    revenue_growth = value_or_none(info.get("revenueGrowth"))
    earnings_growth = value_or_none(info.get("earningsGrowth"))
    free_cashflow = value_or_none(info.get("freeCashflow"))
    operating_cashflow = value_or_none(info.get("operatingCashflow"))
    available = [
        value
        for value in [revenue_growth, earnings_growth, free_cashflow, operating_cashflow]
        if value is not None
    ]
    if not available:
        return (
            "Aktuelle Umsatz-, Gewinn- und Cashflow-Daten sind nicht ausreichend verfügbar. Ein belastbarer Vergleich "
            "mit dem Zeitpunkt des früheren Hochs ist deshalb nicht möglich.",
            None,
        )

    negative_signals = sum(
        [
            revenue_growth is not None and revenue_growth < -0.05,
            earnings_growth is not None and earnings_growth < -0.10,
            free_cashflow is not None and free_cashflow < 0,
            operating_cashflow is not None and operating_cashflow < 0,
        ]
    )
    positive_signals = sum(
        [
            revenue_growth is not None and revenue_growth > 0.05,
            earnings_growth is not None and earnings_growth > 0.05,
            free_cashflow is not None and free_cashflow > 0,
            operating_cashflow is not None and operating_cashflow > 0,
        ]
    )
    if negative_signals >= 2:
        return (
            "Die aktuell verfügbaren Umsatz-, Gewinn- oder Cashflow-Daten zeigen mehrere Schwächesignale. "
            "Der Kursrückgang wird deshalb nicht automatisch als günstig bewertet. Historische Stichtagsdaten vom Hoch "
            "sind in der vorhandenen Quelle nicht vollständig verfügbar.",
            True,
        )
    if positive_signals >= 2:
        return (
            "Die aktuell verfügbaren Wachstums- und Cashflow-Daten stützen die Investmentthese. Ein exakter Vergleich "
            "mit den damaligen Werten am früheren Hoch ist mit der vorhandenen Quelle dennoch nicht belastbar möglich.",
            False,
        )
    return (
        "Die aktuell verfügbaren Umsatz-, Gewinn- und Cashflow-Daten ergeben ein gemischtes Bild. Ein exakter Vergleich "
        "mit dem Zeitpunkt des früheren Hochs ist mit der vorhandenen Quelle nicht belastbar möglich.",
        None,
    )


def price_attractiveness_context(
    asset_type: str,
    future_score: float,
    valuation: ResearchModule,
    expected_value: ResearchModule,
    df: pd.DataFrame,
    latest: pd.Series,
    ticker_info: dict | None = None,
) -> dict[str, object]:
    """Evaluate price separately from quality and timing using only available evidence."""
    close = value_or_none(latest.get("Close"))
    peak = value_or_none(df["High"].dropna().max()) if "High" in df and not df.empty else None
    drawdown_pct = ((close / peak) - 1) * 100 if close is not None and peak is not None and peak > 0 else None
    peak_date = "Datum nicht verfügbar"
    if peak is not None and "High" in df and not df["High"].dropna().empty:
        try:
            peak_index = df["High"].astype(float).idxmax()
            parsed_peak = pd.to_datetime(peak_index, errors="coerce")
            if not pd.isna(parsed_peak) and not isinstance(peak_index, (int, np.integer)):
                peak_date = parsed_peak.strftime("%d.%m.%Y")
        except (TypeError, ValueError, KeyError):
            pass

    fundamental_context, fundamentals_deteriorated = fundamental_context_since_high(
        asset_type,
        ticker_info,
    )
    valuation_score = valuation.score
    expected_value_score = expected_value.score
    weighted_components: list[tuple[float, float]] = []
    if valuation_score is not None:
        weighted_components.append((float(valuation_score), 0.55))
    if expected_value_score is not None:
        weighted_components.append((float(expected_value_score), 0.30))
    weighted_components.append((float(future_score), 0.15))
    total_weight = sum(weight for _, weight in weighted_components)
    price_score = (
        sum(value * weight for value, weight in weighted_components) / total_weight
        if total_weight
        else None
    )

    if price_score is not None and drawdown_pct is not None and not fundamentals_deteriorated:
        drawdown = abs(min(drawdown_pct, 0.0))
        if drawdown >= 50:
            price_score += 2.0
        elif drawdown >= 35:
            price_score += 1.4
        elif drawdown >= 20:
            price_score += 0.7
    if price_score is not None and fundamentals_deteriorated:
        price_score -= 1.5
    price_score = clamp(price_score) if price_score is not None else None

    if price_score is None:
        assessment = "Nicht belastbar"
    elif price_score >= 7.25:
        assessment = "Günstig"
    elif price_score >= 5.5:
        assessment = "Fair"
    elif price_score >= 3.5:
        assessment = "Erhöht"
    else:
        assessment = "Extrem"

    if drawdown_pct is None:
        high_context = "Der Abstand zum höchsten Kurs der verfügbaren Historie konnte nicht belastbar berechnet werden."
    else:
        drawdown_text = f"{abs(drawdown_pct):.1f}".replace(".", ",")
        high_context = (
            f"Der Kurs liegt {drawdown_text} % unter dem höchsten Kurs der maximal verfügbaren Yahoo-Historie"
            f" ({peak_date}). Dieser Abstand ist Kontext und kein automatisches Kaufsignal."
            if drawdown_pct < 0
            else "Der Kurs liegt am höchsten Kurs der maximal verfügbaren Yahoo-Historie. Das ist kein automatisches Verkaufssignal."
        )

    if drawdown_pct is None or drawdown_pct > -10:
        decline_reason = "Es liegt kein ausgeprägter Rückgang vom Hoch vor, der gesondert erklärt werden müsste."
    elif fundamentals_deteriorated:
        decline_reason = "Der Rückgang passt zumindest teilweise zu schwächeren aktuellen Fundamentaldaten; billig allein wegen des Kursabstands wäre eine falsche Schlussfolgerung."
    elif asset_type == "Krypto":
        decline_reason = "Der Rückgang passt eher zu Marktzyklus, Risikoappetit und Momentum. On-Chain-, Flow- und Liquiditätsdaten fehlen für eine eindeutige Ursachenanalyse."
    elif asset_type == "ETF":
        decline_reason = "Der Rückgang ist vor allem im Kontext des zugrunde liegenden Marktes und des allgemeinen Risikoappetits zu lesen; eine eindeutige Einzelursache ist nicht ableitbar."
    else:
        decline_reason = "Die vorhandenen Kurs- und Fundamentaldaten liefern keine eindeutige Einzelursache. Bewertung, Erwartungen, Marktumfeld und Unternehmensentwicklung müssen gemeinsam betrachtet werden."

    return {
        "assessment": assessment,
        "score": price_score,
        "drawdown_pct": drawdown_pct,
        "high_context": high_context,
        "fundamental_context": fundamental_context,
        "fundamentals_deteriorated": fundamentals_deteriorated,
        "decline_reason": decline_reason,
    }
