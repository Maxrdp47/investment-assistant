from __future__ import annotations

import json

import app
from recommendation_synthesis import professional_decision, synthesize_investment_recommendation


RECOMMENDATION_CATEGORIES = {
    "Jetzt kaufen",
    "Erste Tranche kaufen",
    "Bei Bestätigung kaufen",
    "Auf konkrete Kaufzone warten",
    "Halten",
    "Teilweise reduzieren",
    "Verkaufen oder vermeiden",
}


def research_module(name: str, score: float | None) -> app.ResearchModule:
    return app.ResearchModule(name, score, f"{name}: {score}", [], "")


def recommendation_case(
    *,
    asset_type: str = "Aktie",
    quality: float = 7.5,
    future: float = 7.0,
    valuation: float | None = 6.0,
    expectations: float | None = 5.0,
    bubble: float | None = 5.0,
    entry: float = 7.5,
    expected_value: float | None = 6.5,
    confidence: float | None = 7.0,
    data_quality: float | None = 8.0,
    phase: str = "Bullenmarkt",
    has_position: bool = False,
    portfolio: app.PortfolioResult | None = None,
    ticker_info: dict | None = None,
    history_prices: list[float] | None = None,
) -> dict[str, object]:
    rows = len(history_prices) if history_prices else 260
    close = app.pd.Series(history_prices or [80 + index * 20 / (rows - 1) for index in range(rows)])
    frame = app.pd.DataFrame(
        {
            "Close": close,
            "High": close * 1.02,
            "Low": close * 0.98,
            "Volume": [120.0] * rows,
        }
    )
    latest = app.pd.Series(
        {
            "Close": 100.0,
            "SMA_50": 95.0,
            "SMA_200": 90.0,
            "MACD": 2.0,
            "MACD_Signal": 1.0,
            "Volatility": 0.25,
            "Volume": 120.0,
            "Volume_SMA_20": 100.0,
        }
    )
    return app.synthesize_investment_recommendation(
        app.AssetProfile(asset_type, "", "", {}),
        app.ModuleScore(quality, "", []),
        research_module("Zukunftspotenzial", future),
        research_module("Bewertung", valuation),
        research_module("Eingepreiste Erwartungen", expectations),
        research_module("Blasenrisiko", bubble),
        app.ModuleScore(entry, "", []),
        research_module("Expected Value", expected_value),
        app.ModuleScore(5.0, "", []),
        app.MarketPhase(phase, "", {}),
        app.RiskReward(-0.05, 0.10, 2.0, 7.0, "CRV 2,0"),
        research_module("Confidence", confidence),
        research_module("Datenqualität", data_quality),
        [95.0],
        [110.0],
        frame,
        latest,
        "EUR",
        1.0,
        "Nur EUR",
        ["Neue externe Daten können die Einschätzung verändern."],
        portfolio,
        has_position,
        ticker_info,
    )


def test_app_reexports_extracted_recommendation_interfaces() -> None:
    assert app.synthesize_investment_recommendation is synthesize_investment_recommendation
    assert app.professional_decision is professional_decision


def test_legacy_professional_decision_contract_remains_available() -> None:
    result = professional_decision(
        app.ModuleScore(8.0, "", []),
        research_module("Zukunftspotenzial", 7.5),
        research_module("Bewertung", 6.5),
        research_module("Eingepreiste Erwartungen", 5.0),
        research_module("Blasenrisiko", 4.0),
        app.ModuleScore(7.6, "", []),
        research_module("Expected Value", 7.1),
        app.ModuleScore(5.0, "", []),
        app.MarketPhase("Bullenmarkt", "", {}),
        research_module("Confidence", 7.0),
    )

    assert result["Titel"] == "Stark kaufen"
    assert result["Asset-Qualität"] == "8.0/10"
    assert result["Expected Value"] == "7.1/10"


def test_servicenow_like_quality_with_high_valuation_uses_first_tranche() -> None:
    decision = recommendation_case(
        quality=8.0,
        future=8.0,
        valuation=4.0,
        expectations=7.8,
        bubble=7.6,
        entry=8.0,
        expected_value=7.0,
        confidence=8.0,
    )

    assert decision["Titel"] == "Erste Tranche kaufen"
    assert "25 %" in str(decision["Nächste Handlung"])
    assert decision["Langfristige Einschätzung"] == "Sehr attraktiv"
    assert decision["Preisattraktivität"] == "Fair"


def test_high_quality_pullback_is_not_rejected_for_imperfect_timing() -> None:
    decision = recommendation_case(
        quality=8.0,
        future=8.0,
        entry=5.2,
        expected_value=5.5,
        phase="Korrektur innerhalb eines Aufwärtstrends",
    )

    assert decision["Titel"] == "Erste Tranche kaufen"
    assert "Rücksetzer" in str(decision["Alternative Handlung"])
    assert "Bestätigung" in str(decision["Alternative Handlung"])


def test_weak_company_is_not_promoted_by_short_term_technical_strength() -> None:
    decision = recommendation_case(quality=4.0, future=4.0, entry=8.0, expected_value=7.0)

    assert decision["Titel"] == "Verkaufen oder vermeiden"


def test_etf_and_crypto_keep_asset_specific_quality_thresholds() -> None:
    etf = recommendation_case(asset_type="ETF", quality=6.2, future=6.2, valuation=None)
    crypto = recommendation_case(
        asset_type="Krypto",
        quality=5.8,
        future=6.0,
        valuation=None,
        entry=6.2,
        expected_value=5.5,
    )

    assert etf["Titel"] == "Jetzt kaufen"
    assert crypto["Titel"] in {"Erste Tranche kaufen", "Bei Bestätigung kaufen"}
    assert etf["Anlagehorizont"] == "mindestens 5 Jahre"
    assert "hoher Risikotoleranz" in str(crypto["Anlagehorizont"])


def test_missing_fundamentals_lower_confidence_without_automatic_rejection() -> None:
    decision = recommendation_case(
        quality=6.8,
        future=6.5,
        valuation=None,
        entry=6.3,
        expected_value=5.5,
        confidence=4.0,
        data_quality=4.0,
    )

    assert decision["Titel"] == "Auf konkrete Kaufzone warten"
    assert decision["Confidence"] == "niedrig"
    assert "Bewertung nicht verfügbar" in str(decision["Kurzbegründung"])
    assert "fehlende daten" in str(decision["Nicht der Hauptgrund"]).lower()


def test_existing_position_and_portfolio_effect_are_separate() -> None:
    holding = recommendation_case(has_position=True, entry=4.2, expected_value=5.0)
    concentrated = recommendation_case(
        has_position=True,
        portfolio=app.PortfolioResult(True, True, 3.5, "Klumpenrisiko", []),
    )

    assert holding["Titel"] == "Halten"
    assert concentrated["Titel"] == "Teilweise reduzieren"


def test_conditional_recommendation_always_has_two_paths_and_invalidation() -> None:
    decision = recommendation_case(entry=4.0, expected_value=4.5, confidence=6.0, valuation=3.5)

    assert decision["Titel"] == "Auf konkrete Kaufzone warten"
    assert "95,00 €" in str(decision["Rücksetzer-Einstieg"])
    assert "110,00 €" in str(decision["Bestätigungs-Einstieg"])
    assert "Kommt kein Rücksetzer" in str(decision["Alternative Handlung"])
    assert "Tagesschluss unter" in str(decision["Widerlegungsbedingung"])
    assert " bis " in str(decision["Kaufzone"])


def test_recommendation_contract_is_compact_consistent_and_serializable() -> None:
    decisions = [
        recommendation_case(),
        recommendation_case(entry=6.0, expected_value=5.0, quality=5.5),
        recommendation_case(entry=4.0, expected_value=4.5),
        recommendation_case(quality=4.0, future=4.0, entry=8.0),
    ]

    assert {str(decision["Titel"]) for decision in decisions} <= RECOMMENDATION_CATEGORIES
    assert all(len(app.decision_items(decision, "Hauptgründe")) <= 3 for decision in decisions)
    assert all(len(app.decision_items(decision, "Zentrale Risiken")) <= 2 for decision in decisions)
    assert all(str(decision["Titel"]) not in {"Abwarten", "Beobachten", "Nicht kaufen"} for decision in decisions)
    for decision in decisions:
        json.dumps(decision, ensure_ascii=False)


def test_action_family_treats_conditional_entries_as_waiting_not_active_long() -> None:
    assert app.action_family("Bei Bestätigung kaufen") == "Abwarten/Beobachten"
    assert app.action_family("Auf konkrete Kaufzone warten") == "Abwarten/Beobachten"
    assert app.action_family("Erste Tranche kaufen") == "Long/Kaufen"
    assert app.action_family("Teilweise reduzieren") == "Short/Verkaufen"


def test_recommendation_contract_separates_horizon_timing_and_all_plan_paths() -> None:
    decision = recommendation_case()

    required_fields = {
        "Empfehlungskategorie",
        "Langfristige Einschätzung",
        "Preisattraktivität",
        "Aktuelles Timing",
        "Anlagehorizont",
        "Confidence",
        "Hauptgründe",
        "Zentrale Risiken",
        "Handlung jetzt",
        "Handlung bei Rücksetzer",
        "Handlung bei weiterer Stärke",
        "Tranchierung",
        "Widerlegungsbedingung",
        "Gültigkeit",
    }
    assert required_fields <= set(decision)
    assert decision["Empfehlungskategorie"] == decision["Titel"]
    assert decision["Langfristige Einschätzung"] == "Attraktiv"
    assert decision["Aktuelles Timing"] == "Gut"


def test_bitcoin_plan_is_multistep_and_horizon_appropriate() -> None:
    decision = recommendation_case(
        asset_type="Krypto",
        quality=6.2,
        future=6.5,
        valuation=None,
        entry=4.2,
        expected_value=4.8,
        confidence=5.5,
    )

    assert "1–3 Jahre" in str(decision["Anlagehorizont"])
    assert " bis " in str(decision["Kaufzone"])
    assert decision["Handlung jetzt"]
    assert decision["Handlung bei Rücksetzer"]
    assert decision["Handlung bei weiterer Stärke"]
    assert str(decision["Kaufzone"]) != str(decision["Widerlegungsbedingung"])


def test_quality_stock_and_expensive_growth_stock_remain_distinguishable() -> None:
    quality_stock = recommendation_case(quality=8.5, future=7.8, valuation=6.5, entry=7.4)
    expensive_growth = recommendation_case(
        quality=8.2,
        future=8.5,
        valuation=2.8,
        expectations=8.8,
        bubble=8.6,
        entry=7.8,
    )

    assert quality_stock["Titel"] == "Jetzt kaufen"
    assert expensive_growth["Titel"] != "Jetzt kaufen"
    assert expensive_growth["Langfristige Einschätzung"] == "Sehr attraktiv"
    assert expensive_growth["Preisattraktivität"] in {"Erhöht", "Extrem"}


def test_broad_and_thematic_etf_keep_practical_but_different_plans() -> None:
    broad = recommendation_case(asset_type="ETF", quality=7.2, future=6.8, valuation=6.0, entry=7.2)
    thematic = recommendation_case(
        asset_type="ETF",
        quality=6.2,
        future=7.2,
        valuation=3.8,
        expectations=7.8,
        bubble=7.6,
        entry=5.0,
    )

    assert broad["Titel"] in {"Jetzt kaufen", "Erste Tranche kaufen"}
    assert thematic["Titel"] == "Erste Tranche kaufen"
    assert broad["Handlung jetzt"] != thematic["Handlung jetzt"] or broad["Aktuelles Timing"] != thematic["Aktuelles Timing"]


def test_positive_and_negative_recommendations_have_consistent_actions() -> None:
    positive = recommendation_case()
    negative = recommendation_case(quality=3.5, future=3.5, entry=3.0, expected_value=3.0)

    assert positive["Titel"] == "Jetzt kaufen"
    assert "Keine neue Position" not in str(positive["Handlung jetzt"])
    assert negative["Titel"] == "Verkaufen oder vermeiden"
    assert "Keine neue Position" in str(negative["Handlung jetzt"])


def test_large_drawdown_is_context_not_automatic_bargain_when_fundamentals_are_weak() -> None:
    prices = [100 + index for index in range(101)] + [200 - index for index in range(1, 101)]
    decision = recommendation_case(
        quality=8.0,
        future=7.5,
        valuation=6.0,
        entry=5.0,
        expected_value=6.0,
        history_prices=prices,
        ticker_info={
            "revenueGrowth": -0.12,
            "earningsGrowth": -0.25,
            "freeCashflow": -1_000_000,
            "operatingCashflow": -500_000,
        },
    )

    assert decision["Preisattraktivität"] in {"Erhöht", "Extrem"}
    assert decision["Titel"] != "Jetzt kaufen"
    assert "kein automatisches Kaufsignal" in str(decision["Allzeithoch-Kontext"])
    assert "Schwächesignale" in str(decision["Fundamentaldaten seit Hoch"])


def test_quality_stock_with_large_drawdown_and_intact_current_data_can_start_small() -> None:
    prices = [100 + index for index in range(101)] + [200 - index for index in range(1, 101)]
    decision = recommendation_case(
        quality=8.2,
        future=8.0,
        valuation=4.2,
        entry=4.2,
        expected_value=5.5,
        phase="Bodenbildungsphase",
        history_prices=prices,
        ticker_info={
            "revenueGrowth": 0.12,
            "earningsGrowth": 0.10,
            "freeCashflow": 2_000_000,
            "operatingCashflow": 3_000_000,
        },
    )

    assert decision["Preisattraktivität"] in {"Günstig", "Fair"}
    assert decision["Aktuelles Timing"] == "Nur bei Bestätigung"
    assert decision["Titel"] == "Erste Tranche kaufen"
    assert "25 %" in str(decision["Handlung jetzt"])


def test_plan_uses_one_set_of_zones_percentages_and_validity() -> None:
    decision = recommendation_case()

    assert str(decision["Kaufzone"]) in str(decision["Handlung bei Rücksetzer"])
    assert str(decision["Sofort-Kaufzone"]) in str(decision["Handlung jetzt"])
    assert "%" in str(decision["Tranchierung"])
    assert "30" in str(decision["Gültigkeit"]) or "Quartalszahlen" in str(decision["Gültigkeit"])
    assert "Eurobetrag" in str(decision["Positionsgröße"])


def test_crypto_drawdown_explains_missing_specialist_data() -> None:
    decision = recommendation_case(
        asset_type="Krypto",
        history_prices=[100 + index for index in range(101)] + [200 - index for index in range(1, 101)],
        valuation=None,
        entry=4.0,
    )

    assert "On-Chain" in str(decision["Fundamentaldaten seit Hoch"])
    assert " bis " in str(decision["Kaufzone"])
    assert decision["Kaufzone"] != decision["Sofort-Kaufzone"]


def test_past_earnings_date_is_not_used_as_future_validity_limit() -> None:
    decision = recommendation_case(ticker_info={"earningsTimestamp": 1_700_000_000})

    assert "2023" not in str(decision["Gültigkeit"])
    assert "maximal 30 Tage" in str(decision["Gültigkeit"])
