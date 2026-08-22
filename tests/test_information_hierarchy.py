from __future__ import annotations

import inspect

import app


def test_detail_text_hides_internal_score_values() -> None:
    assert app.user_facing_detail_text("Aktien-Asset-Qualität 7.2/10 aus 10 verfügbaren Kennzahlen.") == (
        "Die verfügbaren Qualitätsdaten unterstützen die langfristige Investmentthese."
    )
    assert "/10" not in app.user_facing_detail_text("Bewertungsscore 3.6/10 ist erhöht.")


def test_empty_or_unavailable_modules_are_hidden_from_normal_detail_view() -> None:
    modules = [
        app.ResearchModule("Leer", None, "Daten nicht verfügbar.", [], ""),
        app.ResearchModule("Neutral ohne Quelle", 5.0, "News-Daten nicht verfügbar.", [], ""),
        app.ResearchModule("Relevant", 6.0, "Makroumfeld ist gemischt.", [], ""),
    ]

    assert [module.name for module in app.user_relevant_modules(modules)] == ["Relevant"]


def test_scenario_and_risk_views_expose_only_understandable_fields() -> None:
    scenarios = app.compact_scenario_rows(
        [
            {
                "Szenario": "Bull-Case",
                "Was müsste passieren?": "Trend bestätigt sich.",
                "Wahrscheinlichkeit": "40%",
                "Kursziel": "120 €",
                "Wichtigste Treiber": "CRV 7.0/10, Volatilität 25%",
            }
        ]
    )
    risk_rows = app.recommendation_risk_rows(
        {
            "Risiko-Details": [
                {"Risiko": "Bewertung erhöht", "Relevanz": "hoch", "Erkennbar an": "schwächerem Wachstum"}
            ]
        }
    )

    assert set(scenarios[0]) == {
        "Szenario",
        "Notwendige Entwicklung",
        "Wahrscheinlichkeit",
        "Mögliche Folge",
        "Wichtigster Auslöser",
    }
    assert "CRV" not in " ".join(scenarios[0].values())
    assert risk_rows == [
        {"Risiko": "Bewertung erhöht", "Relevanz": "hoch", "Erkennbar an": "schwächerem Wachstum"}
    ]


def test_portfolio_facet_only_exists_when_portfolio_mode_is_enabled() -> None:
    without_portfolio = app.detail_analysis_tab_labels(False)
    with_portfolio = app.detail_analysis_tab_labels(True)

    assert "Portfolio-Effekt" not in without_portfolio
    assert with_portfolio == [*without_portfolio, "Portfolio-Effekt"]
    assert app.advanced_analysis_tab_labels() == [
        "Technische Kennzahlen",
        "Fundamentale Kennzahlen",
        "Datenqualität",
        "Methodik",
        "Prognosequalität",
    ]


def test_important_result_text_uses_wrapping_without_ellipsis() -> None:
    main_source = inspect.getsource(app.main)
    summary_source = inspect.getsource(app.render_recommendation_summary)

    assert "text-overflow: ellipsis" not in main_source
    assert "white-space: nowrap" not in main_source
    assert "overflow-wrap: anywhere" in main_source
    assert "@media (max-width: 700px)" in main_source
    assert ".metric(" not in summary_source


def test_compact_summary_contains_all_three_assessments_and_complete_plan() -> None:
    source = inspect.getsource(app.render_recommendation_summary)

    assert "Langfristige Attraktivität" in source
    assert "Preisattraktivität" in source
    assert "Kurzfristiges Timing" in source
    assert "Reihenfolge der Tranchen" in source
    assert "Falls der Rücksetzer nicht kommt" in source
    assert "Gültigkeit" in source
