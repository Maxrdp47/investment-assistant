from __future__ import annotations

import threading

import pandas as pd

import app


def test_daily_chart_frame_reuses_long_term_history() -> None:
    index = pd.date_range("2024-01-01", periods=420, freq="B")
    frame = pd.DataFrame({"Close": range(420)}, index=index)

    assert len(app.daily_chart_frame_from_analysis(frame, "1d")) == 1
    assert len(app.daily_chart_frame_from_analysis(frame, "5d")) == 5
    assert 15 <= len(app.daily_chart_frame_from_analysis(frame, "1mo")) <= 25
    assert app.daily_chart_frame_from_analysis(frame, "max").equals(frame)


def test_external_analysis_context_loads_independent_inputs_in_parallel(monkeypatch) -> None:
    barrier = threading.Barrier(5)

    def together(value: object) -> object:
        barrier.wait(timeout=2)
        return value

    macro = app.ModuleScore(6.0, "Makro", [])
    news = app.ModuleScore(5.5, "News", [])
    earnings = pd.DataFrame({"date": ["2026-08-01"]})
    monkeypatch.setattr(app, "load_ticker_info", lambda symbol: together({"symbol": symbol}))
    monkeypatch.setattr(app, "score_macro", lambda: together(macro))
    monkeypatch.setattr(app, "score_news", lambda symbol: together(news))
    monkeypatch.setattr(app, "load_commodity_prices", lambda: together({"Gold": pd.DataFrame()}))
    monkeypatch.setattr(app, "load_earnings_dates", lambda symbol: together(earnings))

    result = app.load_external_analysis_context("NOW")

    assert result["ticker_info"] == {"symbol": "NOW"}
    assert result["macro"] is macro
    assert result["news"] is news
    assert "Gold" in result["commodity_data"]
    assert result["earnings_dates"].equals(earnings)
    assert result["errors"] == []
