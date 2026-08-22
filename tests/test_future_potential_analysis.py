from __future__ import annotations

import math

import app
from analysis_models import AssetProfile, ModuleScore, ResearchModule
from future_potential_analysis import research_future_potential, research_priced_expectations


def profile(asset_type: str = "Aktie") -> AssetProfile:
    return AssetProfile(asset_type, "EQUITY", asset_type, {})


def module_score(score: float) -> ModuleScore:
    return ModuleScore(score, "Kontext", [])


def research_module(name: str, score: float | None) -> ResearchModule:
    return ResearchModule(name, score, "Kontext", [], "Erklärung")


def test_app_reexports_future_potential_functions_for_compatibility() -> None:
    assert app.research_future_potential is research_future_potential
    assert app.research_priced_expectations is research_priced_expectations


def test_future_potential_preserves_growth_margin_quality_and_news_contributions() -> None:
    info = {
        "revenueGrowth": 0.20,
        "earningsGrowth": 0.10,
        "operatingMargins": 0.15,
    }
    original = dict(info)

    result = research_future_potential(info, profile(), module_score(7.0), module_score(7.0))
    details = "\n".join(result.details)

    assert result.score == 7.1
    assert "Umsatzwachstum: 20.0% -> Zukunftspotenzial 8.6/10" in details
    assert "Gewinnwachstum: 10.0% -> Zukunftspotenzial 6.6/10" in details
    assert "Operative Marge: 15.0% -> Skalierbarkeit 7.0/10" in details
    assert "News-Sentiment stützt" in details
    assert info == original


def test_missing_or_non_finite_growth_data_stays_visible_and_neutral() -> None:
    result = research_future_potential(
        {"revenueGrowth": math.inf, "earningsGrowth": math.nan},
        profile("Krypto"),
        module_score(6.0),
        module_score(5.0),
    )
    details = "\n".join(result.details)

    assert result.score == 6.0
    assert "Umsatzwachstum: Daten nicht verfügbar" in details
    assert "Gewinnwachstum: Daten nicht verfügbar" in details
    assert "Netzwerk-/Adoptionsdaten: Daten nicht verfügbar" in details


def test_priced_expectations_preserve_high_and_low_optimism_cases() -> None:
    high = research_priced_expectations(
        {"recommendationKey": "strong_buy"},
        profile(),
        research_module("Bewertung", 3.0),
        research_module("Momentum", 8.0),
        module_score(8.0),
    )
    low = research_priced_expectations(
        {},
        profile(),
        research_module("Bewertung", 8.0),
        research_module("Momentum", 3.0),
        module_score(3.0),
    )

    assert high.score == 6.8
    assert "strong buy" in "\n".join(high.details)
    assert low.score == 2.8
    assert "weniger Euphorie" in "\n".join(low.details)


def test_priced_expectations_does_not_invent_missing_special_sentiment_sources() -> None:
    result = research_priced_expectations(
        {},
        profile("ETF"),
        research_module("Bewertung", None),
        research_module("Momentum", None),
        module_score(5.0),
    )
    details = "\n".join(result.details)

    assert result.score == 4.8
    assert "Bewertungsniveau: Daten nicht verfügbar" in details
    assert "Momentum: Daten nicht verfügbar" in details
    assert "Kapitalzuflüsse: Daten nicht verfügbar" in details
    assert "Sentiment-Spezialdaten: Daten nicht verfügbar" in details
