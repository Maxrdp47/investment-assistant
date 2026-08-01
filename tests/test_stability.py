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


def test_trade_journal_auto_documentation_deduplicates_same_day(tmp_path: Path, monkeypatch) -> None:
    trade_path = tmp_path / "trade_history.json"
    monkeypatch.setattr(app, "TRADE_HISTORY_PATH", trade_path)
    setup = {
        "Datum": "2026-07-31T10:00:00",
        "Ticker": "BTC-EUR",
        "Richtung": "Long",
        "Einstieg": 100.0,
        "review_after": app.empty_review_schedule(),
    }

    added, message = app.auto_document_trade_setups([setup])
    added_again, second_message = app.auto_document_trade_setups([{**setup, "Datum": "2026-07-31T12:00:00"}])

    history = app.load_trade_history()
    assert added == 1
    assert "Keine Order" in message
    assert added_again == 0
    assert "bereits" in second_message
    assert len(history) == 1


def test_trade_journal_allows_new_direction_or_day(tmp_path: Path, monkeypatch) -> None:
    trade_path = tmp_path / "trade_history.json"
    monkeypatch.setattr(app, "TRADE_HISTORY_PATH", trade_path)
    setups = [
        {"Datum": "2026-07-31T10:00:00", "Ticker": "NVDA", "Richtung": "Long"},
        {"Datum": "2026-07-31T10:00:00", "Ticker": "NVDA", "Richtung": "Short / Absicherung"},
        {"Datum": "2026-08-01T10:00:00", "Ticker": "NVDA", "Richtung": "Long"},
    ]

    added, _ = app.auto_document_trade_setups(setups)

    assert added == 3
    assert len(app.load_trade_history()) == 3


def test_trade_performance_tracking_records_best_alternative(tmp_path: Path, monkeypatch) -> None:
    trade_path = tmp_path / "trade_history.json"
    monkeypatch.setattr(app, "TRADE_HISTORY_PATH", trade_path)
    trade_path.write_text(
        json.dumps(
            [
                {
                    "Datum": "2025-01-01T10:00:00",
                    "Ticker": "NVDA",
                    "Richtung": "Long",
                    "Einstieg": 100.0,
                    "Zielzone": 120.0,
                    "Stop-Zone": 90.0,
                    "review_after": app.empty_review_schedule(),
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prices = app.pd.DataFrame(
        {
            "Close": [100.0, 95.0, 85.0],
            "High": [102.0, 100.0, 91.0],
            "Low": [98.0, 92.0, 80.0],
        },
        index=app.pd.date_range("2025-01-01", periods=3, freq="D"),
    )

    monkeypatch.setattr(app.yf, "download", lambda *args, **kwargs: prices.copy())

    updated, message = app.evaluate_due_trade_history()
    review = app.load_trade_history()[0]["review_after"]["1w"]

    assert updated >= 1
    assert "aktualisiert" in message
    assert review["return_pct"] == -15.0
    assert review["stop_hit"] is True
    assert review["best_alternative"] == "Short / Absicherung"
    assert review["best_alternative_return_pct"] == 15.0
    assert review["opportunity_cost_pct"] == 30.0


def test_decision_alignment_maps_user_decision_against_app_action() -> None:
    aligned = app.decision_alignment("Kleine Tranche", "kleine Tranche möglich")
    divergent = app.decision_alignment("Nicht kaufen", "Heute kaufen / Nachkauf prüfen")

    assert aligned["app_exposure"] == "Long"
    assert aligned["decision_matches_app"] is True
    assert divergent["app_exposure"] == "Long"
    assert divergent["decision_matches_app"] is False
    assert divergent["decision_alignment"] == "gegen App-Einschätzung"


def test_decision_tracking_records_alignment_and_user_context(tmp_path: Path, monkeypatch) -> None:
    decision_path = tmp_path / "decision_history.json"
    monkeypatch.setattr(app, "DECISION_HISTORY_PATH", decision_path)
    decision_path.write_text(
        json.dumps(
            [
                {
                    "created_at": "2025-01-01T10:00:00",
                    "symbol": "NVDA",
                    "decision": "Nicht kaufen",
                    "user_note": "Timing war mir zu unsicher.",
                    "app_action": "Heute kaufen / Nachkauf prüfen",
                    "asset_quality": 8.0,
                    "buy_signal": 8.2,
                    "price_at_decision": 100.0,
                    "review_after": app.empty_review_schedule(),
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prices = app.pd.DataFrame(
        {"Close": [100.0, 110.0], "High": [101.0, 112.0], "Low": [99.0, 108.0]},
        index=app.pd.date_range("2025-01-01", periods=2, freq="D"),
    )

    monkeypatch.setattr(app.yf, "download", lambda *args, **kwargs: prices.copy())

    updated, _ = app.evaluate_due_decision_history()
    record = app.load_decision_history()[0]
    review = record["review_after"]["1w"]

    assert updated >= 1
    assert record["user_note"] == "Timing war mir zu unsicher."
    assert review["decision_exposure"] == "Beobachten"
    assert review["app_exposure"] == "Long"
    assert review["decision_matches_app"] is False
    assert review["decision_alignment"] == "gegen App-Einschätzung"
    assert review["best_alternative"] == "Long"


def test_forward_test_evaluation_records_scenario_read(tmp_path: Path, monkeypatch) -> None:
    forward_path = tmp_path / "forward_tests.json"
    monkeypatch.setattr(app, "FORWARD_TEST_PATH", forward_path)
    forward_path.write_text(
        json.dumps(
            [
                {
                    "created_at": "2025-01-01T10:00:00",
                    "symbol": "NVDA",
                    "asset_type": "Aktie",
                    "entry_price": 100.0,
                    "module_scores": [{"name": "Momentum-Score", "score": 8.0}],
                    "scenarios": [{"Szenario": "Bull-Case", "Wahrscheinlichkeit": "40%"}],
                    "review_after": app.empty_review_schedule(),
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prices = app.pd.DataFrame(
        {"Close": [100.0, 104.5], "High": [101.0, 106.0], "Low": [99.0, 103.0]},
        index=app.pd.date_range("2025-01-01", periods=2, freq="D"),
    )

    monkeypatch.setattr(app.yf, "download", lambda *args, **kwargs: prices.copy())

    updated, _ = app.evaluate_due_forward_tests()
    review = app.load_forward_tests()[0]["review_after"]["1w"]

    assert updated >= 1
    assert review["return_pct"] == 4.5
    assert review["scenario_read"] == "Bull/Base wahrscheinlicher"


def test_signal_learning_rows_include_forward_module_and_scenario_groups() -> None:
    forward_tests = []
    for index in range(20):
        forward_tests.append(
            {
                "asset_type": "Aktie",
                "module_scores": [{"name": "Momentum-Score", "score": 8.0}],
                "review_after": {
                    "1m": {
                        "return_pct": 4.0 if index < 14 else -2.0,
                        "scenario_read": "Bull/Base wahrscheinlicher" if index < 14 else "Bear wahrscheinlicher",
                    }
                },
            }
        )

    status, rows = app.signal_learning_rows(forward_tests, [])
    signals = {row["Signal"] for row in rows}

    assert "Vorsichtige Hinweise" in status
    assert "Modulgruppe Momentum-Score (hoch)" in signals
    assert "Szenario-Lesart Bull/Base wahrscheinlicher" in signals


def test_scanner_factor_snapshot_discloses_missing_and_available_sources() -> None:
    latest = app.pd.Series({"Volume": 200_000, "Volume_SMA_20": 100_000})
    info = {
        "trailingPE": 24.0,
        "heldPercentInstitutions": 0.52,
    }
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})
    asset_quality = app.ModuleScore(7.2, "Qualität", [])
    macro = app.ModuleScore(6.0, "Makro", [])
    news = app.ModuleScore(5.5, "News", [])

    snapshot = app.scanner_factor_snapshot(info, profile, latest, asset_quality, macro, news)

    assert snapshot["News"] == "5.5/10"
    assert snapshot["Makro"] == "6.0/10"
    assert snapshot["Liquidität"] == "2.00x 20T-Volumen"
    assert snapshot["Bewertung"] == "Proxy über Asset-Qualität 7.2/10"
    assert snapshot["Institutionelle Faktoren"] == "Yahoo-Daten teilweise verfügbar"


def test_scanner_factor_snapshot_keeps_missing_data_explicit() -> None:
    latest = app.pd.Series({"Volume": None, "Volume_SMA_20": None})
    profile = app.AssetProfile("Krypto", "CRYPTOCURRENCY", "Krypto", {})

    snapshot = app.scanner_factor_snapshot(
        {},
        profile,
        latest,
        app.ModuleScore(5.0, "Qualität", []),
        app.ModuleScore(5.0, "Makro", []),
        app.ModuleScore(5.0, "News", []),
    )

    assert snapshot["Liquidität"] == "Daten nicht verfügbar"
    assert snapshot["Bewertung"] == "Zyklus/On-Chain: Daten nicht verfügbar"
    assert snapshot["Institutionelle Faktoren"] == "Daten nicht verfügbar"


def test_opportunity_scanner_reuses_loaded_ticker_info(monkeypatch) -> None:
    calls = {"ticker_info": 0}
    index = app.pd.date_range("2025-01-01", periods=260, freq="D")
    prices = app.pd.DataFrame(
        {
            "Close": list(range(100, 360)),
            "High": list(range(101, 361)),
            "Low": list(range(99, 359)),
            "Volume": [100_000] * 260,
        },
        index=index,
    )

    def fake_load_price_data(symbol: str, period: str, interval: str) -> app.pd.DataFrame:
        return prices.copy()

    def fake_load_ticker_info(symbol: str) -> dict:
        calls["ticker_info"] += 1
        return {
            "quoteType": "EQUITY",
            "shortName": "Nvidia",
            "trailingPE": 24.0,
            "heldPercentInstitutions": 0.52,
        }

    monkeypatch.setattr(app, "load_price_data", fake_load_price_data)
    monkeypatch.setattr(app, "load_ticker_info", fake_load_ticker_info)
    monkeypatch.setattr(app, "score_macro", lambda: app.ModuleScore(5.0, "Makro neutral", []))
    monkeypatch.setattr(app, "score_news", lambda symbol: app.ModuleScore(5.0, "News neutral", []))

    rows, errors = app.scan_opportunities(["NVDA"])

    assert errors == []
    assert calls["ticker_info"] == 1
    assert rows[0]["Ticker"] == "NVDA"
    assert {"News", "Makro", "Liquidität", "Bewertung", "Institutionelle Faktoren"} <= set(rows[0])


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


def test_learning_guardrails_block_calibration_under_minimum() -> None:
    status, rows = app.learning_guardrail_rows([], [], [], [])

    rules = {row["Regel"]: row for row in rows}
    assert "Datenbasis zu klein" in status
    assert rules["Ausgewertete Fälle"]["Status"] == "0"
    assert rules["Unter 20 Fällen"]["Status"] == "Nur zählen"
    assert rules["Automatische Gewichtungsänderung"]["Status"] == "Nein"


def test_learning_guardrails_allow_only_manual_suggestions_after_large_basis() -> None:
    records = [
        {
            "action": "Long",
            "asset_type": "Aktie",
            "review_after": {"1m": {"return_pct": 3.0}},
        }
        for _ in range(55)
    ]

    status, rows = app.learning_guardrail_rows(records, [], [], [])
    rules = {row["Regel"]: row for row in rows}

    assert "manuelle Kalibrierungsvorschläge erlaubt" in status
    assert rules["Ausgewertete Fälle"]["Status"] == "55"
    assert rules["Aktuelle Freigabe"]["Status"] == "Manuelle Vorschläge erlaubt"
    assert rules["Automatische Gewichtungsänderung"]["Status"] == "Nein"


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


def test_institutional_research_modules_disclose_data_coverage_and_neutrality(monkeypatch) -> None:
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})
    macro = app.ModuleScore(5.0, "Makro neutral", [])
    monkeypatch.setattr(app, "load_earnings_dates", lambda symbol: app.pd.DataFrame())

    analyst = app.research_analyst_consensus({}, profile, "USD", None, "EUR + Originalwährung")
    earnings = app.research_earnings_module("NVDA", {}, profile)
    event = app.research_event_risk_module({}, profile, macro)
    institutional = app.research_institutional_data({}, profile)

    for module in [analyst, earnings, event, institutional]:
        details = "\n".join(module.details)
        assert "Datenabdeckung" in details
        assert "Score-Neutralität" in details
        assert "Daten nicht verfügbar" in details


def test_institutional_research_modules_use_available_yfinance_fields(monkeypatch) -> None:
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})
    macro = app.ModuleScore(6.8, "Makro konstruktiv", [])
    monkeypatch.setattr(app, "load_earnings_dates", lambda symbol: app.pd.DataFrame())

    info = {
        "targetMeanPrice": 120.0,
        "targetHighPrice": 150.0,
        "targetLowPrice": 90.0,
        "numberOfAnalystOpinions": 18,
        "recommendationMean": 2.0,
        "recommendationKey": "buy",
        "currentPrice": 100.0,
        "earningsTimestamp": 1_800_000_000,
        "heldPercentInstitutions": 0.55,
        "heldPercentInsiders": 0.08,
        "shortPercentOfFloat": 0.02,
    }

    analyst = app.research_analyst_consensus(info, profile, "USD", None, "EUR + Originalwährung")
    event = app.research_event_risk_module(info, profile, macro)
    institutional = app.research_institutional_data(info, profile)

    assert analyst.score is not None
    assert event.score is not None
    assert institutional.score is not None
    assert any("Datenabdeckung Analysten-Konsens" in detail for detail in analyst.details)
    assert any("Quartalsbericht" in detail for detail in event.details)
    assert any("Institutionelle Beteiligungen: 55.0%" in detail for detail in institutional.details)


def test_news_score_discloses_missing_news_coverage(monkeypatch) -> None:
    monkeypatch.setattr(app, "load_news_items", lambda symbol: [])

    module = app.score_news("NVDA")
    details = "\n".join(module.details)

    assert module.score == 5.0
    assert "Datenabdeckung News" in details
    assert "Score-Neutralität News" in details
    assert "Keine News verfügbar" in details


def test_news_score_discloses_source_date_relevance_and_sentiment_quality(monkeypatch) -> None:
    monkeypatch.setattr(
        app,
        "load_news_items",
        lambda symbol: [
            {
                "title": "Nvidia shares rally after strong growth",
                "publisher": "Example News",
                "providerPublishTime": 1_800_000_000,
                "link": "https://example.com/nvda",
                "relatedTickers": ["NVDA"],
            },
            {
                "content": {
                    "title": "Chip sector faces risk after weak demand",
                    "provider": {"displayName": "Market Desk"},
                    "pubDate": "2026-07-30T12:00:00Z",
                    "finance": {"stockTickers": ["AMD"]},
                }
            },
        ],
    )

    module = app.score_news("NVDA")
    details = "\n".join(module.details)

    assert "Datenabdeckung News" in details
    assert "Quelle: Example News" in details
    assert "Datum:" in details
    assert "Relevanz: hoch" in details
    assert "Sentiment-Qualität" in details
    assert module.summary.startswith("News-Sentiment")


def test_macro_score_discloses_missing_proxy_coverage(monkeypatch) -> None:
    monkeypatch.setattr(app, "load_macro_prices", lambda: {})

    module = app.score_macro()
    details = "\n".join(module.details)

    assert module.score == 5.0
    assert "Datenabdeckung Makro" in details
    assert "Score-Neutralität Makro" in details
    assert "Liquiditätsproxy direkt: Daten nicht verfügbar" in details
    assert "Risikoappetit / Nasdaq-Trend: Daten nicht verfügbar" in details


def test_macro_score_explains_available_proxy_effects(monkeypatch) -> None:
    def frame(start: float, end: float) -> app.pd.DataFrame:
        return app.pd.DataFrame({"Close": [start, start, start, start, start, end]})

    monkeypatch.setattr(
        app,
        "load_macro_prices",
        lambda: {
            "Nasdaq": frame(100, 112),
            "US-Zinsen 10J": frame(100, 90),
            "Dollar-Index": frame(100, 95),
            "Inflationserwartung Proxy": frame(100, 102),
        },
    )

    module = app.score_macro()
    details = "\n".join(module.details)

    assert module.score > 5.0
    assert "Risikoappetit / Nasdaq-Trend" in details
    assert "Zinsdruck / US-Zinsen 10J" in details
    assert "Dollar-/Liquiditätsdruck" in details
    assert "Inflations-/Realzins-Proxy TIP" in details


def test_geopolitical_context_does_not_invent_missing_data(monkeypatch) -> None:
    monkeypatch.setattr(app, "load_news_items", lambda symbol: [])
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})

    module = app.research_geopolitical_context("NVDA", profile)
    details = "\n".join(module.details)

    assert module.score is None
    assert module.summary == "Geopolitische Daten nicht verfügbar."
    assert "Datenabdeckung Geopolitik" in details
    assert "Daten nicht verfügbar" in details
    assert "keine geopolitischen Ereignisse" in details


def test_geopolitical_context_uses_news_titles_as_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        app,
        "load_news_items",
        lambda symbol: [
            {
                "title": "Chip stocks fall as new export controls raise Taiwan supply risk",
                "publisher": "Example News",
                "providerPublishTime": 1_800_000_000,
                "relatedTickers": ["NVDA"],
            },
            {
                "title": "Markets rally after tariff relief deal",
                "publisher": "Market Desk",
                "providerPublishTime": 1_800_000_100,
                "relatedTickers": ["NVDA"],
            },
        ],
    )
    profile = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})

    module = app.research_geopolitical_context("NVDA", profile)
    details = "\n".join(module.details)

    assert module.score is not None
    assert module.score < 6.0
    assert "Geopolitische Risikotreffer" in details
    assert "export control" in details or "export controls" in details
    assert "Entlastungstreffer" in details


def test_risk_score_uses_asset_type_thresholds_and_crv_details() -> None:
    df = app.pd.DataFrame({"Volatility": [0.60]})
    risk_reward = app.RiskReward(
        risk_pct=-0.08,
        reward_pct=0.20,
        ratio=2.5,
        score=8.0,
        summary="Risiko bis Unterstützung -8,0 %, Potenzial bis Widerstand +20,0 %, CRV 2,50.",
    )
    stock = app.AssetProfile("Aktie", "EQUITY", "Aktie", {})
    crypto = app.AssetProfile("Krypto", "CRYPTOCURRENCY", "Krypto", {})

    stock_module = app.research_risk_score(df, risk_reward, stock)
    crypto_module = app.research_risk_score(df, risk_reward, crypto)
    details = "\n".join(stock_module.details)

    assert stock_module.score < crypto_module.score
    assert "Datenabdeckung Risiko" in details
    assert "Score-Neutralität Risiko" in details
    assert "CRV-Einordnung: 2.50" in details
    assert "Risiko bis nächste Unterstützung" in details


def test_liquidity_score_discloses_volume_coverage_and_missing_market_depth() -> None:
    df = app.pd.DataFrame({"Volume": [25_000], "Volume_SMA_20": [100_000]})
    info = {"averageVolume": 40_000, "averageVolume10days": 50_000}
    profile = app.AssetProfile("ETF", "ETF", "ETF", {})

    module = app.research_liquidity_score(df, info, profile)
    details = "\n".join(module.details)

    assert "Datenabdeckung Liquidität" in details
    assert "Score-Neutralität Liquidität" in details
    assert "0.25x" in details
    assert "Handel ist dünn" in details
    assert "10T-Durchschnittsvolumen Yahoo" in details
    assert "Bid-Ask-Spread und Orderbuchtiefe: Daten nicht verfügbar" in details


def test_crypto_cycle_discloses_special_data_coverage_and_market_structure() -> None:
    df = app.pd.DataFrame(
        {
            "Close": [120.0],
            "SMA_50": [110.0],
            "SMA_200": [90.0],
            "Volatility": [0.62],
            "Volume": [150_000],
            "Volume_SMA_20": [100_000],
        }
    )
    profile = app.AssetProfile("Krypto", "CRYPTOCURRENCY", "Krypto", {})

    module = app.research_crypto_cycle("BTC-EUR", profile, df)
    details = "\n".join(module.details)

    assert module.score is not None
    assert "Datenabdeckung Krypto-Zyklus" in details
    assert "Score-Neutralität Krypto-Zyklus" in details
    assert "Fear & Greed: Daten nicht verfügbar" in details
    assert "ETF-Flows: Daten nicht verfügbar" in details
    assert "On-Chain-Daten: Daten nicht verfügbar" in details
    assert "Stablecoin-Liquiditätsdaten: Daten nicht verfügbar" in details
    assert "Trendstruktur konstruktiv" in details
    assert "Zyklusfortschritt" in details
    assert "Praktische Bedeutung" in details
    assert "kein Kaufsignal" in details


def test_crypto_halving_cycle_context_is_deterministic_for_known_dates() -> None:
    early = app.crypto_halving_cycle_context(app.pd.Timestamp("2024-06-01"))
    middle = app.crypto_halving_cycle_context(app.pd.Timestamp("2025-06-01"))
    late = app.crypto_halving_cycle_context(app.pd.Timestamp("2026-08-01"))

    assert early["phase"] == "frühe Nach-Halving-Phase"
    assert middle["phase"] == "mittlere Zyklusphase"
    assert late["phase"] == "späte Zyklusphase mit erhöhtem Rückschlagsrisiko"
    assert 0 <= late["progress_pct"] <= 100
    assert "Für Anleger bedeutet das" in late["practical_meaning"]


def test_crypto_fundamentals_disclose_missing_special_sources() -> None:
    df = app.pd.DataFrame({"Volatility": [0.80], "Volume": [50_000], "Volume_SMA_20": [100_000]})
    technical = app.ModuleScore(6.0, "Technik", [])
    macro = app.ModuleScore(5.0, "Makro", [])

    module = app.score_crypto_fundamentals({}, technical, macro, df)
    details = "\n".join(module.details)

    assert "Datenabdeckung Krypto-Spezialdaten" in details
    assert "Score-Neutralität Krypto-Spezialdaten" in details
    assert "Fear & Greed: Daten nicht verfügbar" in details
    assert "ETF-Flows: Daten nicht verfügbar" in details
    assert "On-Chain-Daten: Daten nicht verfügbar" in details
    assert "Stablecoin-Liquidität: Daten nicht verfügbar" in details


def test_prediction_hit_rate_rows_group_by_asset_and_module() -> None:
    predictions = [
        {
            "asset_type": "Aktie",
            "module_scores": [
                {"name": "Makro-Score", "score": 7.0},
                {"name": "News-Score", "score": 4.0},
            ],
            "review_after": {
                "1m": {
                    "return_pct": 6.2,
                    "scenario_read": "Bull/Base wahrscheinlicher",
                }
            },
        }
    ]

    status, rows = app.prediction_hit_rate_rows(predictions)
    dimensions = {(row["Dimension"], row["Gruppe"]) for row in rows}

    assert "Datenbasis zu klein" in status
    assert ("Asset-Typ", "Aktie") in dimensions
    assert ("Modul", "Makro-Score (hoch)") in dimensions
    assert ("Modul", "News-Score (niedrig)") in dimensions


def test_prediction_hit_rate_rows_keeps_legacy_signal_snapshots() -> None:
    predictions = [
        {
            "asset_type": "Krypto",
            "signal_snapshot": {"RSI": "überverkauft", "Makro": "hoch"},
            "review_after": {
                "1w": {
                    "return_pct": -3.0,
                    "scenario_read": "Bear wahrscheinlicher",
                }
            },
        }
    ]

    _, rows = app.prediction_hit_rate_rows(predictions)
    dimensions = {(row["Dimension"], row["Gruppe"]) for row in rows}

    assert ("Asset-Typ", "Krypto") in dimensions
    assert ("Signal", "RSI (überverkauft)") in dimensions
    assert ("Signal", "Makro (hoch)") in dimensions
