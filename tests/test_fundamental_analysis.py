from __future__ import annotations

import math

import pandas as pd
import pytest

import app
from fundamental_analysis import (
    etf_fundamental_snapshot,
    score_etf_fundamentals,
    score_profitability_metric,
    score_stock_fundamentals,
    score_valuation_multiple,
    stock_fundamental_snapshot,
)


def test_stock_snapshot_normalizes_missing_and_non_finite_values() -> None:
    snapshot = stock_fundamental_snapshot(
        {
            "revenueGrowth": "0.12",
            "earningsGrowth": float("nan"),
            "profitMargins": None,
            "totalCash": 2_500,
            "marketCap": math.inf,
        }
    )

    assert snapshot.revenue_growth == 0.12
    assert snapshot.earnings_growth is None
    assert snapshot.profit_margin is None
    assert snapshot.total_cash == 2_500
    assert snapshot.market_cap is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.20, 8.5),
        (0.10, 7.0),
        (0.03, 5.5),
        (0.00, 4.5),
        (-0.01, 2.5),
    ],
)
def test_profitability_thresholds_remain_explicit(value: float, expected: float) -> None:
    assert score_profitability_metric(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, (None, "Daten nicht verfügbar")),
        (0, (None, "Daten nicht verfügbar")),
        (2.5, (8.0, "günstig")),
        (5.0, (6.5, "fair")),
        (10.0, (4.5, "teuer")),
        (10.1, (3.0, "sehr teuer")),
    ],
)
def test_valuation_multiple_boundaries_remain_compatible(
    value: float | None,
    expected: tuple[float | None, str],
) -> None:
    assert score_valuation_multiple(value, (2.5, 5.0, 10.0)) == expected


def test_stock_score_is_neutral_when_no_fundamental_data_exists() -> None:
    result = score_stock_fundamentals({})

    assert result.score == 5.0
    assert result.summary == "Aktien-Fundamentaldaten nicht ausreichend verfügbar. Der Score wird neutral gewertet."
    assert result.details
    assert all("Daten nicht verfügbar" in detail for detail in result.details)


def test_stock_score_preserves_all_existing_metric_contributions() -> None:
    result = score_stock_fundamentals(
        {
            "revenueGrowth": 0.20,
            "earningsGrowth": 0.10,
            "profitMargins": 0.15,
            "returnOnEquity": 0.25,
            "totalCash": 100,
            "totalDebt": 50,
            "freeCashflow": 10,
            "trailingPE": 20,
            "priceToSalesTrailing12Months": 4,
            "priceToBook": 2,
            "enterpriseToEbitda": 12,
            "marketCap": 20_000_000_000,
        }
    )

    assert result.score == 7.6
    assert result.summary == "Aktien-Fundamentalscore 7.6/10 aus 11 verfügbaren Kennzahlen."
    assert any("Cash/Verschuldung: 2.00 -> 9.0/10" in detail for detail in result.details)
    assert any("Kurs-Buchwert-Verhältnis: 2.0 (günstig) -> 8.0/10" in detail for detail in result.details)
    assert any("Marktkapitalisierung: 20.000.000.000,00" in detail for detail in result.details)


def test_etf_snapshot_supports_both_holdings_field_names() -> None:
    snapshot = etf_fundamental_snapshot(
        {
            "category": "World Equity",
            "numberOfHoldings": "650",
            "annualReportExpenseRatio": "0.002",
        }
    )

    assert snapshot.category == "World Equity"
    assert snapshot.holdings_count == 650
    assert snapshot.annual_report_expense_ratio == 0.002


def test_etf_score_is_neutral_when_structure_and_performance_are_missing() -> None:
    result = score_etf_fundamentals({}, pd.DataFrame())

    assert result.score == 5.0
    assert result.summary == "ETF-Daten nicht ausreichend verfügbar. Der Score wird neutral gewertet."
    assert result.details
    assert all("Daten nicht verfügbar" in detail for detail in result.details)


def test_etf_score_preserves_structure_performance_and_volatility_rules() -> None:
    frame = pd.DataFrame({"Volatility": [0.15]})
    original = frame.copy(deep=True)

    result = score_etf_fundamentals(
        {
            "category": "Global Large-Cap Blend",
            "annualReportExpenseRatio": 0.002,
            "totalAssets": 6_000_000_000,
            "holdingsCount": 600,
            "52WeekChange": 0.10,
            "ytdReturn": 0.05,
            "threeYearAverageReturn": 0.08,
            "fiveYearAverageReturn": 0.07,
            "beta3Year": 0.9,
        },
        frame,
    )

    assert result.score == 7.4
    assert result.summary == "ETF-Score 7.4/10 aus verfügbaren Struktur- und Performance-Daten."
    assert any("TER/Kostenquote: 0.20% -> 8.5/10" in detail for detail in result.details)
    assert any("Diversifikation: 600 Positionen -> 8.0/10" in detail for detail in result.details)
    assert any("Volatilität 15.0% -> 8.0/10" in detail for detail in result.details)
    pd.testing.assert_frame_equal(frame, original)


def test_app_reexports_fundamental_functions_after_extraction() -> None:
    assert app.stock_fundamental_snapshot is stock_fundamental_snapshot
    assert app.etf_fundamental_snapshot is etf_fundamental_snapshot
    assert app.score_stock_fundamentals is score_stock_fundamentals
    assert app.score_etf_fundamentals is score_etf_fundamentals
    assert app.score_valuation_multiple is score_valuation_multiple
