from __future__ import annotations

import pandas as pd

import app
from analysis_models import AssetProfile, ModuleScore, ResearchModule
from data_quality_analysis import (
    build_data_source_warnings,
    data_quality_check,
    data_quality_status,
)


def test_app_reexports_extracted_data_quality_interfaces() -> None:
    assert app.build_data_source_warnings is build_data_source_warnings
    assert app.data_quality_status is data_quality_status
    assert app.data_quality_check is data_quality_check


def test_external_source_warnings_report_each_real_gap() -> None:
    warnings = build_data_source_warnings(
        {},
        "USD",
        None,
        "EURUSD=X",
        ModuleScore(5.0, "Keine News verfügbar.", []),
        ModuleScore(5.0, "Makrodaten konnten nicht geladen werden.", []),
    )

    assert len(warnings) == 4
    assert any("Stammdaten" in warning for warning in warnings)
    assert any("EUR-Umrechnung" in warning for warning in warnings)
    assert any("News" in warning for warning in warnings)
    assert any("Makro" in warning for warning in warnings)


def test_complete_external_sources_produce_no_warning() -> None:
    warnings = build_data_source_warnings(
        {"symbol": "NVDA"},
        "EUR",
        1.0,
        "",
        ModuleScore(6.0, "Aktuelle Nachrichten verfügbar.", []),
        ModuleScore(6.0, "Makro-Proxies verfügbar.", []),
    )

    assert warnings == []


def test_status_keeps_green_yellow_red_thresholds_and_limits_highlights() -> None:
    green = data_quality_status(ResearchModule("Datenqualität", 8.0, "", [], ""), [])
    yellow = data_quality_status(
        ResearchModule("Datenqualität", 6.0, "", ["Volumen fehlt."], ""),
        ["Warnung 1", "Warnung 2", "Warnung 3"],
    )
    red = data_quality_status(ResearchModule("Datenqualität", 5.9, "", [], ""), [])

    assert green[0] == "Grün"
    assert yellow[0] == "Gelb"
    assert len(yellow[2]) == 3
    assert red[0] == "Rot"


def test_complete_history_scores_full_data_quality_without_mutation() -> None:
    frame = pd.DataFrame(
        {
            "Close": [100.0] * 220,
            "Volume": [1_000.0] * 220,
            "SMA_50": [99.0] * 220,
            "SMA_200": [90.0] * 220,
        }
    )
    before = frame.copy(deep=True)
    identity = {"exchange": "Nasdaq", "currency": "USD"}

    result = data_quality_check(
        "NVDA",
        AssetProfile("Aktie", "EQUITY", "", {}),
        identity,
        frame,
        chart_history_label="1 Jahr",
        analysis_history_label="Max",
        chart_rows=220,
    )

    assert result.score == 10.0
    assert result.summary == "Datenqualität gut."
    assert "Mindestens 200 Handelstage vorhanden." in result.details
    pd.testing.assert_frame_equal(frame, before)
    assert identity == {"exchange": "Nasdaq", "currency": "USD"}


def test_empty_unknown_asset_has_explicit_issues_and_no_invented_data() -> None:
    result = data_quality_check(
        "",
        AssetProfile("Derivat / unbekannt", "", "", {}),
        {},
        pd.DataFrame(),
    )

    assert result.score == 0.0
    assert "Ticker nicht gefunden." in result.details
    assert "Kursdaten fehlen." in result.details
    assert "200er-Durchschnitt nicht berechenbar." in result.details
    assert "Fehlende Daten werden nicht erfunden" in result.beginner
