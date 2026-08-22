from __future__ import annotations

import pandas as pd

import app
from analysis_models import ResearchModule
from price_attractiveness import fundamental_context_since_high, price_attractiveness_context


def module(name: str, score: float | None) -> ResearchModule:
    return ResearchModule(name, score, "Zusammenfassung", [], "Einfach erklärt")


def drawdown_frame() -> tuple[pd.DataFrame, pd.Series]:
    index = pd.to_datetime(["2025-01-02", "2026-08-02"])
    frame = pd.DataFrame({"High": [100.0, 55.0], "Close": [95.0, 50.0]}, index=index)
    return frame, frame.iloc[-1]


def test_app_reexports_extracted_price_functions_for_compatibility() -> None:
    assert app.fundamental_context_since_high is fundamental_context_since_high
    assert app.price_attractiveness_context is price_attractiveness_context


def test_current_fundamental_context_distinguishes_strength_weakness_and_gaps() -> None:
    positive_text, positive_state = fundamental_context_since_high(
        "Aktie",
        {"revenueGrowth": 0.10, "freeCashflow": 100.0},
    )
    negative_text, negative_state = fundamental_context_since_high(
        "Aktie",
        {"revenueGrowth": -0.10, "operatingCashflow": -50.0},
    )
    missing_text, missing_state = fundamental_context_since_high("Aktie", {})

    assert positive_state is False
    assert "stützen" in positive_text
    assert negative_state is True
    assert "Schwächesignale" in negative_text
    assert missing_state is None
    assert "nicht ausreichend verfügbar" in missing_text


def test_large_drawdown_improves_price_context_only_with_intact_current_fundamentals() -> None:
    frame, latest = drawdown_frame()
    intact = price_attractiveness_context(
        "Aktie",
        6.0,
        module("Bewertung", 6.0),
        module("Expected Value", 6.0),
        frame,
        latest,
        {"revenueGrowth": 0.10, "freeCashflow": 100.0},
    )
    weak = price_attractiveness_context(
        "Aktie",
        6.0,
        module("Bewertung", 6.0),
        module("Expected Value", 6.0),
        frame,
        latest,
        {"revenueGrowth": -0.10, "freeCashflow": -100.0},
    )

    assert intact["drawdown_pct"] == -50.0
    assert intact["score"] == 8.0
    assert intact["assessment"] == "Günstig"
    assert weak["fundamentals_deteriorated"] is True
    assert weak["score"] == 4.5
    assert weak["assessment"] == "Erhöht"
    assert "billig allein" in str(weak["decline_reason"])


def test_drawdown_is_explicit_context_and_never_described_as_automatic_signal() -> None:
    frame, latest = drawdown_frame()

    result = price_attractiveness_context(
        "ETF",
        5.0,
        module("Bewertung", 5.0),
        module("Expected Value", 5.0),
        frame,
        latest,
    )

    assert "kein automatisches Kaufsignal" in str(result["high_context"])
    assert "zugrunde liegenden Marktes" in str(result["decline_reason"])


def test_missing_price_history_remains_visible_without_mutating_inputs() -> None:
    frame = pd.DataFrame({"Close": [50.0]})
    original = frame.copy(deep=True)
    latest = frame.iloc[-1].copy()

    result = price_attractiveness_context(
        "Krypto",
        5.0,
        module("Bewertung", None),
        module("Expected Value", None),
        frame,
        latest,
    )

    assert result["drawdown_pct"] is None
    assert "nicht belastbar berechnet" in str(result["high_context"])
    assert "On-Chain" in str(result["fundamental_context"])
    pd.testing.assert_frame_equal(frame, original)
