from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from forecast_baselines import (
    direction_hit,
    market_benchmark_definition,
    simple_trend_snapshot,
)
from forecast_runner import build_evaluation, default_evaluation_market_data_batch


class ForecastBaselineTests(unittest.TestCase):
    def test_simple_trend_is_deterministic_and_requires_real_history(self) -> None:
        rising = simple_trend_snapshot(range(80, 101))
        falling = simple_trend_snapshot(range(120, 99, -1))
        sideways = simple_trend_snapshot([100.0] * 21)
        missing = simple_trend_snapshot([100.0] * 20)

        self.assertEqual(rising["predicted_direction"], "Steigend")
        self.assertEqual(falling["predicted_direction"], "Fallend")
        self.assertEqual(sideways["predicted_direction"], "Seitwärts")
        self.assertEqual(missing["status"], "missing")

    def test_direction_and_market_benchmarks_are_explicit(self) -> None:
        self.assertEqual(direction_hit("Steigend", 0.1), 1)
        self.assertEqual(direction_hit("Fallend", -0.1), 1)
        self.assertEqual(direction_hit("Seitwärts", 2.9), 1)
        self.assertEqual(direction_hit("Seitwärts", 3.1), 0)
        self.assertEqual(market_benchmark_definition("Krypto", "International")["ticker"], "BTC-EUR")
        self.assertEqual(market_benchmark_definition("Aktie", "Europa")["ticker"], "EXSA.DE")
        self.assertEqual(market_benchmark_definition("Aktie", "USA")["ticker"], "SPY")
        self.assertEqual(market_benchmark_definition("ETF", "Europa")["ticker"], "ACWI")

    def test_due_batch_keeps_asset_result_and_adds_point_in_time_market_baseline(self) -> None:
        index = pd.to_datetime(["2026-08-01", "2026-08-10"])
        histories = {
            "TEST": pd.DataFrame(
                {"Close": [100.0, 110.0], "High": [101.0, 112.0], "Low": [99.0, 97.0]},
                index=index,
            ),
            "EXSA.DE": pd.DataFrame(
                {"Close": [200.0, 204.0], "High": [201.0, 205.0], "Low": [199.0, 198.0]},
                index=index,
            ),
        }
        item = {
            "forecast_id": 1,
            "horizon": "1w",
            "ticker": "TEST",
            "created_at": "2026-08-01T22:30:00+02:00",
            "days": 7,
            "price_eur": 100.0,
            "original_currency": "EUR",
            "fx_rate_to_eur": 1.0,
            "predicted_direction": "Steigend",
            "expected_low_eur": 95.0,
            "expected_high_eur": 115.0,
            "target_eur": 112.0,
            "risk_eur": 95.0,
            "simple_trend_baseline": {
                "status": "available",
                "predicted_direction": "Steigend",
            },
            "market_benchmark_snapshot": {
                "status": "available",
                "ticker": "EXSA.DE",
                "currency": "EUR",
                "fx_rate_to_eur": 1.0,
                "price_eur": 200.0,
            },
        }

        with patch(
            "forecast_runner._batch_price_histories",
            return_value=(histories, {}),
        ):
            prepared, errors = default_evaluation_market_data_batch(
                [item],
                as_of=date(2026, 8, 10),
            )
        evaluation = build_evaluation(item, prepared[(1, "1w")])

        self.assertEqual(errors, {})
        self.assertEqual(evaluation["actual_return_pct"], 10.0)
        self.assertEqual(evaluation["simple_trend_hit"], 1)
        self.assertEqual(evaluation["market_benchmark_ticker"], "EXSA.DE")
        self.assertEqual(evaluation["market_benchmark_return_pct"], 2.0)
        self.assertEqual(evaluation["excess_return_pct"], 8.0)


if __name__ == "__main__":
    unittest.main()
