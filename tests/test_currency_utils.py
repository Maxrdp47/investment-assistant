from __future__ import annotations

import pandas as pd

import app
from currency_utils import (
    convert_to_eur,
    converted_levels,
    converted_price_frame,
    format_currency,
    format_display_money,
    format_money,
)


def test_currency_formatting_preserves_existing_german_display_contract() -> None:
    assert format_currency(1_234_567.8) == "1.234.567,80"
    assert format_money(1234.5) == "1.234,50 €"
    assert format_money(1234.5, "usd") == "1.234,50 USD"
    assert format_money(1234.5, "") == "1.234,50 €"


def test_display_money_handles_euro_conversion_and_missing_rates() -> None:
    assert convert_to_eur(100, 0.92) == 92
    assert convert_to_eur(100, None) is None
    assert format_display_money(100, "USD", 0.92, "Nur EUR") == "92,00 €"
    assert format_display_money(100, "USD", 0.92, "Euro und Originalwährung") == "92,00 € (100,00 USD)"
    assert format_display_money(100, "USD", None, "Nur EUR") == "Daten nicht verfügbar (100,00 USD)"
    assert format_display_money(100, "EUR", None, "Nur EUR") == "100,00 €"


def test_price_frame_conversion_copies_input_and_only_converts_price_columns() -> None:
    source = pd.DataFrame(
        {
            "Open": [100.0],
            "Close": [110.0],
            "SMA_50": [105.0],
            "Volume": [1_000],
            "RSI": [55.0],
        }
    )

    converted = converted_price_frame(source, 0.9)

    assert converted.loc[0, "Open"] == 90.0
    assert converted.loc[0, "Close"] == 99.0
    assert converted.loc[0, "SMA_50"] == 94.5
    assert converted.loc[0, "Volume"] == 1_000
    assert converted.loc[0, "RSI"] == 55.0
    assert source.loc[0, "Open"] == 100.0
    assert converted_price_frame(source, None) is not source


def test_level_conversion_and_app_reexports_remain_compatible() -> None:
    levels = [100.0, 125.0]

    assert converted_levels(levels, 0.8) == [80.0, 100.0]
    assert converted_levels(levels, None) is levels
    assert app.format_currency is format_currency
    assert app.format_display_money is format_display_money
    assert app.converted_price_frame is converted_price_frame
