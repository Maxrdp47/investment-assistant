from __future__ import annotations

import pandas as pd


def format_currency(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_money(value: float, currency: str = "EUR") -> str:
    number = format_currency(value)
    currency = (currency or "EUR").upper()
    if currency == "EUR":
        return f"{number} €"
    return f"{number} {currency}"


def convert_to_eur(value: float, fx_rate: float | None) -> float | None:
    if fx_rate is None:
        return None
    return value * fx_rate


def format_display_money(
    value: float,
    original_currency: str,
    fx_rate: float | None,
    display_mode: str,
) -> str:
    original_currency = (original_currency or "EUR").upper()
    if original_currency == "EUR":
        return format_money(value, "EUR")

    eur_value = convert_to_eur(value, fx_rate)
    if eur_value is None:
        return f"Daten nicht verfügbar ({format_money(value, original_currency)})"
    if display_mode == "Nur EUR":
        return format_money(eur_value, "EUR")
    return f"{format_money(eur_value, 'EUR')} ({format_money(value, original_currency)})"


def converted_price_frame(df: pd.DataFrame, fx_rate: float | None) -> pd.DataFrame:
    if fx_rate is None:
        return df.copy()
    display_df = df.copy()
    for column in ["Open", "High", "Low", "Close", "SMA_50", "SMA_200"]:
        if column in display_df:
            display_df[column] = display_df[column] * fx_rate
    return display_df


def converted_levels(levels: list[float], fx_rate: float | None) -> list[float]:
    if fx_rate is None:
        return levels
    return [level * fx_rate for level in levels]
