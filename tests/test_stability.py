from __future__ import annotations

import json
from pathlib import Path

import app
from streamlit.testing.v1 import AppTest


def test_evaluated_history_cases_accepts_empty_histories() -> None:
    assert app.evaluated_history_cases() == []
    assert app.evaluated_history_cases([], [], []) == []


def test_evaluated_history_cases_handles_legacy_records() -> None:
    trades = [
        None,
        {"Asset-Typ": "Aktie", "review_after": []},
        {
            "Asset-Typ": "Aktie",
            "Marktphase": "Bullenmarkt",
            "Richtung": "Long",
            "Kaufsignal": 7,
            "review_after": {"1w": {"result": "Treffer"}, "1m": None},
        },
    ]
    forward_tests = [
        {"asset_type": "ETF", "review_after": "altes Format"},
        {
            "asset_type": "ETF",
            "market_phase": "Seitwärtsmarkt",
            "buy_signal": 3,
            "review_after": {"1m": {"return_pct": -1.5}},
        },
    ]
    predictions = [
        {},
        {
            "asset_type": "Krypto",
            "market_phase": "Bullenmarkt",
            "review_after": {"3m": {"scenario_read": "Bull/Base wahrscheinlicher"}},
        },
    ]

    rows = app.evaluated_history_cases(trades, forward_tests, predictions)

    assert len(rows) == 3
    assert [row["hit"] for row in rows] == [True, False, True]
    assert {row["source"] for row in rows} == {"Trade Journal", "Forward-Test", "Prognose"}


def test_history_loaders_handle_missing_empty_and_legacy_json(tmp_path: Path, monkeypatch) -> None:
    paths = {
        "SEARCH_HISTORY_PATH": tmp_path / "search.json",
        "TRADE_HISTORY_PATH": tmp_path / "trades.json",
        "FORWARD_TEST_PATH": tmp_path / "forward.json",
        "DECISION_HISTORY_PATH": tmp_path / "decisions.json",
        "PREDICTION_HISTORY_PATH": tmp_path / "predictions.json",
    }
    for name, path in paths.items():
        monkeypatch.setattr(app, name, path)

    assert app.load_search_history() == []
    assert app.load_trade_history() == []
    assert app.load_forward_tests() == []
    assert app.load_decision_history() == []
    assert app.load_prediction_history() == []

    paths["TRADE_HISTORY_PATH"].write_text("", encoding="utf-8")
    paths["FORWARD_TEST_PATH"].write_text("not-json", encoding="utf-8")
    paths["PREDICTION_HISTORY_PATH"].write_text(json.dumps({"legacy": True}), encoding="utf-8")
    paths["SEARCH_HISTORY_PATH"].write_text(json.dumps([None, "old", {"symbol": "NVDA"}]), encoding="utf-8")

    assert app.load_trade_history() == []
    assert app.load_forward_tests() == []
    assert app.load_prediction_history() == []
    assert app.load_search_history() == [{"symbol": "NVDA"}]
    assert app.evaluate_due_trade_history() == (0, "Keine Trading-Setups gespeichert.")
    assert app.evaluate_due_forward_tests() == (0, "Keine Forward-Tests gespeichert.")
    assert app.evaluate_due_decision_history() == (0, "Keine Nutzerentscheidungen gespeichert.")
    assert app.evaluate_due_predictions() == (0, "Keine Prognosen gespeichert.")


def test_review_schedule_repairs_invalid_legacy_shape_without_losing_record() -> None:
    record = {"review_after": []}
    review_after = app.ensure_review_schedule(record)

    assert record["review_after"] is review_after
    assert review_after == {label: None for label in app.TRACKING_PERIODS}


def test_portfolio_loader_reports_empty_or_invalid_optional_file(tmp_path: Path, monkeypatch) -> None:
    portfolio_path = tmp_path / "portfolio.json"
    monkeypatch.setattr(app, "PORTFOLIO_PATH", portfolio_path)

    portfolio, message = app.load_portfolio_file()
    assert portfolio is None
    assert message == "Keine Portfolio-Datei gefunden. Portfolio-Modus kann nicht verwendet werden."

    portfolio_path.write_text("", encoding="utf-8")
    portfolio, message = app.load_portfolio_file()
    assert portfolio is None
    assert message is not None
    assert "kein gültiges JSON" in message


def test_streamlit_start_page_and_primary_controls_render_without_exception() -> None:
    app_test = AppTest.from_file("app.py", default_timeout=30).run()

    assert list(app_test.exception) == []
    assert [title.value for title in app_test.title] == ["Investment-Assistent"]
    assert [header.value for header in app_test.sidebar.header] == ["Analyse"]
    expander_labels = {expander.label for expander in app_test.expander}
    assert {"Forward-Testing", "Opportunity Scanner"} <= expander_labels
    button_labels = {button.label for button in app_test.button}
    assert {
        "Analysieren",
        "Watchlist scannen",
        "Fällige Trading-Setups auswerten",
        "Fällige Entscheidungen auswerten",
        "Fällige Forward-Tests auswerten",
        "Fällige Prognosen auswerten",
    } <= button_labels

    history_buttons = [
        "Fällige Trading-Setups auswerten",
        "Fällige Entscheidungen auswerten",
        "Fällige Forward-Tests auswerten",
        "Fällige Prognosen auswerten",
    ]
    for label in history_buttons:
        rerun = AppTest.from_file("app.py", default_timeout=30).run()
        next(button for button in rerun.button if button.label == label).click().run()
        assert list(rerun.exception) == []

    empty_analysis = AppTest.from_file("app.py", default_timeout=30).run()
    next(button for button in empty_analysis.button if button.label == "Analysieren").click().run()
    assert list(empty_analysis.exception) == []


def test_calibration_suggestions_handle_empty_history() -> None:
    status, rows = app.calibration_suggestion_rows([], [], [], [])

    assert "keine ausgewerteten" in status.lower()
    assert rows[0]["Vorschlag"] == "Keine Änderung"


def test_calibration_suggestions_report_no_miss_pattern() -> None:
    records = [
        {
            "action": "Long",
            "asset_type": "Aktie",
            "market_phase": "Bullenmarkt",
            "buy_signal": 8,
            "signal_snapshot": {"MACD": "positiv", "CRV": "stark"},
            "review_after": {"1m": {"return_pct": 4.2}},
        }
    ]

    status, rows = app.calibration_suggestion_rows(records, [], [], [])

    assert "keine auffälligen" in status.lower()
    assert rows[0]["Vorschlag"] == "Keine Änderung"


def test_calibration_suggestions_allow_manual_proposal_after_large_error_basis() -> None:
    records = []
    for index in range(55):
        records.append(
            {
                "action": "Long",
                "asset_type": "Krypto",
                "market_phase": "Bärenmarkt",
                "buy_signal": 7,
                "signal_snapshot": {
                    "MACD": "negativ",
                    "CRV": "knapp",
                    "Volatilität": "hoch",
                    "News": "niedrig",
                    "Makro": "niedrig",
                },
                "review_after": {"1m": {"return_pct": -3.0 if index < 40 else 2.0}},
            }
        )

    status, rows = app.calibration_suggestion_rows(records, [], [], [])

    assert "Kalibrierungsvorschläge erlaubt" in status
    assert any(
        row["Bereich"] == "MACD"
        and row["Muster"] == "negativ"
        and row["Vorschlag"] == "Manueller Kalibrierungsvorschlag erlaubt"
        and "55 Fälle" in row["Datenbasis"]
        for row in rows
    )


def test_research_valuation_score_discloses_relative_and_missing_peer_data() -> None:
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})
    macro = app.ModuleScore(5.0, "Makro neutral", [])
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

    module = app.research_valuation_score(info, profile, app.pd.DataFrame(), macro)
    details = "\n".join(module.details)

    assert module.name == "Bewertungsscore"
    assert "EV/Umsatz" in details
    assert "Forward-KGV-Abstand" in details
    assert "Relative Bewertungsbasis" in details
    assert "Technology" in details
    assert "Historische Bewertungszeitreihe: Daten nicht verfügbar" in details
    assert "Peer-Vergleich: Daten nicht verfügbar" in details


def test_research_valuation_score_does_not_invent_missing_relative_data() -> None:
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})
    macro = app.ModuleScore(5.0, "Makro neutral", [])

    module = app.research_valuation_score({}, profile, app.pd.DataFrame(), macro)
    details = "\n".join(module.details)

    assert "Relative Bewertungsbasis: Daten nicht verfügbar" in details
    assert "Historische Bewertungszeitreihe: Daten nicht verfügbar" in details
    assert "Peer-Vergleich: Daten nicht verfügbar" in details
