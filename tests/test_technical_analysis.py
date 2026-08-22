import math

import numpy as np
import pandas as pd
import pytest

import app
import technical_analysis


def test_app_reexports_extracted_technical_analysis_contract() -> None:
    assert app.calculate_indicators is technical_analysis.calculate_indicators
    assert app.local_levels is technical_analysis.local_levels
    assert app.calculate_risk_reward is technical_analysis.calculate_risk_reward
    assert app.detect_market_phase is technical_analysis.detect_market_phase
    assert app.value_or_none is technical_analysis.value_or_none


def test_calculate_indicators_keeps_columns_and_interval_annualization() -> None:
    index = pd.date_range("2025-01-01", periods=260, freq="D")
    close = pd.Series(100 + np.arange(260) * 0.08 + np.sin(np.arange(260) / 3), index=index)
    source = pd.DataFrame({"Close": close, "Volume": np.arange(1_000, 1_260)}, index=index)

    daily = technical_analysis.calculate_indicators(source, "1d")
    weekly = technical_analysis.calculate_indicators(source, "1wk")

    assert source.columns.tolist() == ["Close", "Volume"]
    assert {"RSI_14", "MACD", "MACD_Signal", "SMA_50", "SMA_200", "Volume_SMA_20", "Volatility"} <= set(daily.columns)
    assert daily.iloc[-1]["SMA_50"] == pytest.approx(close.tail(50).mean())
    assert daily.iloc[-1]["SMA_200"] == pytest.approx(close.tail(200).mean())
    assert weekly.iloc[-1]["Volatility"] / daily.iloc[-1]["Volatility"] == pytest.approx(
        math.sqrt(52 / 252)
    )


def test_risk_reward_uses_nearest_levels_without_changing_score_contract() -> None:
    result = technical_analysis.calculate_risk_reward(100.0, [90.0, 80.0], [130.0, 140.0])

    assert result.risk_pct == pytest.approx(-0.10)
    assert result.reward_pct == pytest.approx(0.30)
    assert result.ratio == pytest.approx(3.0)
    assert result.score == 10.0
    assert "CRV 3.00" in result.summary

    missing = technical_analysis.calculate_risk_reward(100.0, [], [])
    assert missing.score == 4.0
    assert missing.ratio is None


def test_detect_market_phase_returns_probabilities_that_sum_to_100() -> None:
    close = np.linspace(100.0, 140.0, 120)
    frame = pd.DataFrame(
        {
            "Close": close,
            "SMA_50": np.linspace(95.0, 125.0, 120),
            "SMA_200": np.linspace(90.0, 115.0, 120),
            "RSI_14": np.full(120, 55.0),
            "MACD": np.full(120, 2.0),
            "MACD_Signal": np.full(120, 1.0),
        }
    )

    result = technical_analysis.detect_market_phase(frame)

    assert result.phase == "Bullenmarkt"
    assert sum(result.probabilities.values()) == 100
    assert set(result.probabilities) == {
        "Boden bereits gesehen",
        "Erneuter Test / weitere Korrektur",
        "Neues Tief",
        "Starke Erholung / Ausbruch",
    }


def test_numeric_helpers_keep_missing_and_boundary_semantics() -> None:
    assert technical_analysis.value_or_none(None) is None
    assert technical_analysis.value_or_none(pd.NA) is None
    assert technical_analysis.value_or_none(float("inf")) is None
    assert technical_analysis.value_or_none(float("-inf")) is None
    assert technical_analysis.value_or_none("1.5") == 1.5
    assert technical_analysis.clamp(-1.0) == 0.0
    assert technical_analysis.clamp(11.0) == 10.0
    assert technical_analysis.pct_distance(100.0, 80.0) == pytest.approx(0.2)
    assert technical_analysis.pct_distance(0.0, 80.0) is None
