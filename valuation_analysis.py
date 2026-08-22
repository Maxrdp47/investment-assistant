from __future__ import annotations

import numpy as np
import pandas as pd

from analysis_models import AssetProfile, ModuleScore, ResearchModule
from fundamental_analysis import (
    data_missing,
    score_valuation_multiple,
    stock_fundamental_snapshot,
)
from technical_analysis import value_or_none


def _score_from_optional(values: list[float], neutral_if_empty: float = 5.0) -> float:
    if not values:
        return neutral_if_empty
    return round(float(np.mean(values)), 1)


def research_valuation_score(
    info: dict,
    profile: AssetProfile,
    df: pd.DataFrame,
    macro: ModuleScore,
) -> ResearchModule:
    """Build the existing valuation module without UI or network dependencies."""
    details: list[str] = []
    points: list[float] = []
    if profile.asset_type == "Krypto":
        details.extend(
            [
                "Zyklusdaten: Daten nicht verfügbar.",
                "On-Chain-Bewertungsdaten: Daten nicht verfügbar.",
            ]
        )
        points.append(macro.score)
        score = _score_from_optional(points)
        beginner = (
            "Bei Krypto ersetzt dieser Score klassische Bewertung durch Zyklus-/On-Chain-Kontext. "
            "Wenn diese Daten fehlen, bleibt die Aussage eingeschränkt."
        )
        return ResearchModule(
            "Zyklus-/On-Chain-Score",
            score,
            f"Zyklus-/On-Chain-Score {score}/10; Spezialdaten nicht verfügbar.",
            details,
            beginner,
        )

    trailing_pe = value_or_none(info.get("trailingPE"))
    forward_pe = value_or_none(info.get("forwardPE"))
    peg_ratio = value_or_none(info.get("pegRatio"))
    price_to_sales = value_or_none(info.get("priceToSalesTrailing12Months"))
    enterprise_to_ebitda = value_or_none(info.get("enterpriseToEbitda"))
    enterprise_value = value_or_none(info.get("enterpriseValue"))
    free_cashflow = value_or_none(info.get("freeCashflow"))
    price_to_book = value_or_none(info.get("priceToBook"))
    market_cap = value_or_none(info.get("marketCap"))
    enterprise_to_revenue = value_or_none(info.get("enterpriseToRevenue"))
    sector = info.get("sector") or info.get("category")
    industry = info.get("industry")
    revenue_growth = value_or_none(info.get("revenueGrowth"))
    earnings_growth = value_or_none(info.get("earningsGrowth"))
    operating_margin = value_or_none(info.get("operatingMargins"))
    profit_margin = value_or_none(info.get("profitMargins"))
    debt_to_equity = value_or_none(info.get("debtToEquity"))
    snapshot = stock_fundamental_snapshot(info) if profile.asset_type == "Aktie" else None
    trailing_pe = snapshot.trailing_pe if snapshot else value_or_none(info.get("trailingPE"))
    forward_pe = snapshot.forward_pe if snapshot else value_or_none(info.get("forwardPE"))
    price_to_sales = (
        snapshot.price_to_sales
        if snapshot
        else value_or_none(info.get("priceToSalesTrailing12Months"))
    )
    if trailing_pe is not None:
        score = (
            8.0
            if trailing_pe <= 18
            else 6.0
            if trailing_pe <= 30
            else 4.0
            if trailing_pe <= 50
            else 2.5
        )
        points.append(score)
        details.append(f"KGV: {trailing_pe:.1f} -> {score:.1f}/10; KGV wird nicht isoliert verwendet.")
    else:
        details.append(data_missing("KGV"))
    if forward_pe is not None:
        score = (
            8.0
            if forward_pe <= 18
            else 6.0
            if forward_pe <= 30
            else 4.0
            if forward_pe <= 50
            else 2.5
        )
        points.append(score)
        details.append(f"Forward-KGV: {forward_pe:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Forward-KGV"))
    if trailing_pe is not None and forward_pe is not None and trailing_pe > 0:
        forward_discount = (trailing_pe - forward_pe) / trailing_pe
        score = (
            7.5
            if forward_discount >= 0.20
            else 6.5
            if forward_discount >= 0.05
            else 5.0
            if forward_discount >= -0.05
            else 3.5
        )
        points.append(score)
        details.append(
            f"Forward-KGV-Abstand: {forward_discount * 100:+.1f}% gegen aktuelles KGV -> {score:.1f}/10. "
            "Das ist ein Erwartungsindikator, keine Gewinnprognose der App."
        )
    else:
        details.append(data_missing("Forward-KGV-Abstand"))
    if peg_ratio is not None and peg_ratio > 0:
        score = (
            8.0
            if peg_ratio <= 1.2
            else 6.5
            if peg_ratio <= 2.0
            else 4.5
            if peg_ratio <= 3.5
            else 2.5
        )
        points.append(score)
        details.append(f"PEG-Ratio: {peg_ratio:.2f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("PEG-Ratio"))
    if price_to_sales is not None:
        score = (
            8.0
            if price_to_sales <= 3
            else 6.0
            if price_to_sales <= 8
            else 4.0
            if price_to_sales <= 15
            else 2.5
        )
        points.append(score)
        details.append(f"Kurs-Umsatz-Verhältnis: {price_to_sales:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Kurs-Umsatz-Verhältnis"))
    if enterprise_to_ebitda is not None and enterprise_to_ebitda > 0:
        score = (
            8.0
            if enterprise_to_ebitda <= 12
            else 6.5
            if enterprise_to_ebitda <= 20
            else 4.5
            if enterprise_to_ebitda <= 35
            else 2.5
        )
        points.append(score)
        details.append(
            f"EV/EBITDA als EV/EBIT-Näherung: {enterprise_to_ebitda:.1f} -> {score:.1f}/10."
        )
    else:
        details.append("EV/EBIT: Daten nicht verfügbar.")
    if enterprise_to_revenue is not None and enterprise_to_revenue > 0:
        score = (
            8.0
            if enterprise_to_revenue <= 3
            else 6.5
            if enterprise_to_revenue <= 7
            else 4.5
            if enterprise_to_revenue <= 12
            else 2.5
        )
        points.append(score)
        details.append(f"EV/Umsatz: {enterprise_to_revenue:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("EV/Umsatz"))
    if enterprise_value is not None and free_cashflow is not None and free_cashflow > 0:
        ev_fcf = enterprise_value / free_cashflow
        score = 8.0 if ev_fcf <= 18 else 6.5 if ev_fcf <= 30 else 4.5 if ev_fcf <= 50 else 2.5
        points.append(score)
        details.append(f"EV/FCF: {ev_fcf:.1f} -> {score:.1f}/10.")
    else:
        details.append("EV/FCF: Daten nicht verfügbar.")
    if price_to_book is not None and price_to_book > 0:
        score = (
            8.0
            if price_to_book <= 2
            else 6.0
            if price_to_book <= 6
            else 4.0
            if price_to_book <= 12
            else 2.5
        )
        points.append(score)
        details.append(f"Kurs/Buchwert: {price_to_book:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Kurs/Buchwert"))
    if market_cap is not None and free_cashflow is not None and market_cap > 0:
        fcf_yield = free_cashflow / market_cap
        score = (
            8.0
            if fcf_yield >= 0.06
            else 6.5
            if fcf_yield >= 0.035
            else 4.5
            if fcf_yield >= 0.015
            else 2.5
        )
        points.append(score)
        details.append(f"Free-Cashflow-Rendite: {fcf_yield * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append("Free-Cashflow-Rendite: Daten nicht verfügbar.")
    if revenue_growth is not None:
        details.append(f"Umsatzwachstum: {revenue_growth * 100:.1f}%.")
    else:
        details.append(data_missing("Umsatzwachstum"))
    if earnings_growth is not None:
        details.append(f"Gewinnwachstum: {earnings_growth * 100:.1f}%.")
    else:
        details.append(data_missing("Gewinnwachstum"))
    if operating_margin is not None or profit_margin is not None:
        margin_text = []
        if operating_margin is not None:
            margin_text.append(f"operative Marge {operating_margin * 100:.1f}%")
        if profit_margin is not None:
            margin_text.append(f"Nettomarge {profit_margin * 100:.1f}%")
        details.append("Margen: " + ", ".join(margin_text) + ".")
    else:
        details.append(data_missing("Margen"))
    if debt_to_equity is not None:
        details.append(f"Verschuldung Debt/Equity: {debt_to_equity:.1f}.")
    else:
        details.append(data_missing("Verschuldung / Debt-to-Equity"))
    if sector or industry:
        details.append(
            "Relative Bewertungsbasis: "
            f"Sektor {sector or 'Daten nicht verfügbar'}, Branche {industry or 'Daten nicht verfügbar'}."
        )
    else:
        details.append("Relative Bewertungsbasis: Daten nicht verfügbar.")
    details.append(
        "Historische Bewertungszeitreihe: Daten nicht verfügbar. "
        "Yahoo Finance liefert hier keine belastbare KGV-/KUV-Historie."
    )
    details.append(
        "Peer-Vergleich: Daten nicht verfügbar. "
        "Es werden keine Vergleichsunternehmen oder Peer-Multiples erfunden."
    )
    if snapshot:
        price_to_book_score, price_to_book_label = score_valuation_multiple(
            snapshot.price_to_book,
            (2.5, 5.0, 10.0),
        )
        if price_to_book_score is not None:
            points.append(price_to_book_score)
            details.append(
                f"Kurs-Buchwert-Verhältnis: {snapshot.price_to_book:.1f} ({price_to_book_label}) -> "
                f"{price_to_book_score:.1f}/10."
            )
        else:
            details.append(data_missing("Kurs-Buchwert-Verhältnis"))

        ev_ebitda_score, ev_ebitda_label = score_valuation_multiple(
            snapshot.enterprise_to_ebitda,
            (10.0, 18.0, 30.0),
        )
        if ev_ebitda_score is not None:
            points.append(ev_ebitda_score)
            details.append(
                f"EV/EBITDA: {snapshot.enterprise_to_ebitda:.1f} ({ev_ebitda_label}) -> "
                f"{ev_ebitda_score:.1f}/10."
            )
        else:
            details.append(data_missing("EV/EBITDA"))
    if profile.asset_type == "ETF":
        details.append("ETF-Bewertung über Index-KGV/Region: Daten nicht verfügbar.")
    score = _score_from_optional(points)
    beginner = (
        "Der Bewertungsscore prüft, ob der Preis im Verhältnis zu Gewinn/Umsatz teuer oder günstig wirkt. "
        "Fehlende Kennzahlen werden nicht erfunden."
    )
    return ResearchModule(
        "Bewertungsscore",
        score,
        f"Bewertung {score}/10 aus verfügbaren Bewertungskennzahlen.",
        details,
        beginner,
    )
