from __future__ import annotations

import math

import pandas as pd

import app
from analysis_models import AssetProfile, ModuleScore
from valuation_analysis import research_valuation_score


def profile(asset_type: str) -> AssetProfile:
    return AssetProfile(asset_type, "EQUITY", asset_type, {})


def macro(score: float = 5.0) -> ModuleScore:
    return ModuleScore(score, "Makro-Kontext", [])


def test_app_reexports_extracted_valuation_function_for_compatibility() -> None:
    assert app.research_valuation_score is research_valuation_score


def test_stock_valuation_preserves_all_available_multiple_contributions() -> None:
    info = {
        "trailingPE": 24.0,
        "forwardPE": 18.0,
        "pegRatio": 1.4,
        "priceToSalesTrailing12Months": 6.0,
        "enterpriseToEbitda": 16.0,
        "enterpriseToRevenue": 5.5,
        "enterpriseValue": 120_000_000_000,
        "freeCashflow": 6_000_000_000,
        "priceToBook": 4.0,
        "marketCap": 100_000_000_000,
        "sector": "Technology",
        "industry": "Semiconductors",
    }
    original = dict(info)

    result = research_valuation_score(info, profile("Aktie"), pd.DataFrame(), macro())
    details = "\n".join(result.details)

    assert result.score == 6.7
    assert result.summary == "Bewertung 6.7/10 aus verfügbaren Bewertungskennzahlen."
    assert "Forward-KGV-Abstand: +25.0%" in details
    assert "EV/Umsatz: 5.5" in details
    assert "EV/FCF: 20.0" in details
    assert "Relative Bewertungsbasis: Sektor Technology, Branche Semiconductors" in details
    assert info == original


def test_missing_or_non_finite_multiples_remain_neutral_and_visible() -> None:
    result = research_valuation_score(
        {"trailingPE": math.inf, "forwardPE": math.nan},
        profile("Aktie"),
        pd.DataFrame(),
        macro(),
    )
    details = "\n".join(result.details)

    assert result.score == 5.0
    assert "KGV: Daten nicht verfügbar" in details
    assert "Forward-KGV: Daten nicht verfügbar" in details
    assert "Peer-Vergleich: Daten nicht verfügbar" in details


def test_crypto_valuation_uses_only_macro_context_without_inventing_on_chain_data() -> None:
    result = research_valuation_score({}, profile("Krypto"), pd.DataFrame(), macro(4.2))

    assert result.name == "Zyklus-/On-Chain-Score"
    assert result.score == 4.2
    assert all("Daten nicht verfügbar" in detail for detail in result.details)


def test_etf_valuation_discloses_missing_index_relative_data() -> None:
    result = research_valuation_score({}, profile("ETF"), pd.DataFrame(), macro())
    details = "\n".join(result.details)

    assert result.score == 5.0
    assert "ETF-Bewertung über Index-KGV/Region: Daten nicht verfügbar" in details
    assert "Relative Bewertungsbasis: Daten nicht verfügbar" in details
