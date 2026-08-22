from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from analysis_models import ModuleScore, RiskReward
from currency_utils import format_display_money
from technical_analysis import value_or_none


def build_buy_zones(
    close: float,
    supports: list[float],
    resistances: list[float],
    latest: pd.Series,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
) -> list[dict]:
    sma_50 = value_or_none(latest.get("SMA_50"))
    valid_supports = [level for level in supports if level < close]
    valid_resistances = [level for level in resistances if level > close]
    support = valid_supports[0] if valid_supports else None
    resistance = valid_resistances[0] if valid_resistances else None
    aggressive = close
    fair = support
    safe = resistance if resistance else sma_50 if sma_50 is not None and sma_50 > close else None
    invalid = support * 0.98 if support else None
    return [
        {
            "Zone": "Aggressive Kaufzone",
            "Marke": format_display_money(aggressive, original_currency, fx_rate, currency_mode),
            "Status": "Aktueller Kurs",
            "Bedeutung": (
                "Nur sinnvoll, wenn Kaufsignal stark ist und man bewusst in kleiner Tranche startet."
            ),
        },
        {
            "Zone": "Faire Kaufzone",
            "Marke": (
                format_display_money(fair, original_currency, fx_rate, currency_mode)
                if fair
                else "Daten nicht verfügbar"
            ),
            "Status": "Berechenbar" if fair else "Keine klare Unterstützung",
            "Bedeutung": (
                "Nahe erster Unterstützung; wenn keine Unterstützung erkannt wird, "
                "wird keine faire Kaufzone erfunden."
            ),
        },
        {
            "Zone": "Sicherheits-Kaufzone",
            "Marke": (
                format_display_money(safe, original_currency, fx_rate, currency_mode)
                if safe
                else "Daten nicht verfügbar"
            ),
            "Status": "Berechenbar" if safe else "Keine klare Bestätigungsmarke",
            "Bedeutung": (
                "Nach bestätigter Trendwende oder Ausbruch über den wichtigsten Widerstand; "
                "ohne passende Marke lieber beobachten."
            ),
        },
        {
            "Zone": "Ungültig, wenn Unterstützung bricht",
            "Marke": (
                format_display_money(invalid, original_currency, fx_rate, currency_mode)
                if invalid
                else "Daten nicht verfügbar"
            ),
            "Status": "Berechenbar" if invalid else "Keine klare Ungültigkeitsmarke",
            "Bedeutung": (
                "Unter dieser Zone ist die technische Idee beschädigt; "
                "ohne Marke muss die Position manuell neu bewertet werden."
            ),
        },
    ]


def research_action(
    buy_signal: ModuleScore,
    risk_reward: RiskReward,
    supports: list[float],
    close: float,
) -> str:
    near_support = bool(supports and 0 <= (close - supports[0]) / close <= 0.04)
    if buy_signal.score < 3.5:
        return "Risiko zu hoch"
    if buy_signal.score < 5:
        return "Heute nicht kaufen"
    if buy_signal.score < 6.5:
        return "Beobachten"
    if near_support and risk_reward.score >= 6:
        return "Nachkaufzone erreicht"
    if buy_signal.score >= 8:
        return "Kleine Tranche möglich"
    return "Nachkauf nur bei Bestätigung"


def recommendation_confidence_label(score: float | None) -> str:
    if score is None or score < 5.0:
        return "niedrig"
    if score < 7.0:
        return "mittel"
    return "hoch"


def recommendation_horizon(asset_type: str) -> str:
    if asset_type == "ETF":
        return "mindestens 5 Jahre"
    if asset_type == "Krypto":
        return "1–3 Jahre bei hoher Risikotoleranz"
    if asset_type == "Aktie":
        return "3–5 Jahre"
    return "mehrjährig"


def recommendation_validity(asset_type: str, ticker_info: dict | None = None) -> str:
    latest_valid_day = date.today() + timedelta(days=30)
    deadline = latest_valid_day.strftime("%d.%m.%Y")
    if asset_type == "Aktie":
        info = ticker_info or {}
        report_value = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
        try:
            if isinstance(report_value, (int, float, np.integer, np.floating)):
                parsed_report = pd.to_datetime(report_value, unit="s", errors="coerce")
            else:
                parsed_report = pd.to_datetime(report_value, errors="coerce")
            report_date = None if pd.isna(parsed_report) else parsed_report.date()
        except (AttributeError, TypeError, ValueError, OverflowError):
            report_date = None
        if report_date is not None and report_date >= date.today():
            next_report = report_date.strftime("%d.%m.%Y")
            return (
                f"Bis zu den nächsten Quartalszahlen am {next_report}, höchstens bis {deadline} "
                "(maximal 30 Tage). Bei Bruch der Widerlegungsbedingung oder wesentlichen neuen "
                "Unternehmensdaten früher neu bewerten."
            )
    return (
        f"Höchstens bis {deadline} (maximal 30 Tage). Bei Bruch der Widerlegungsbedingung oder "
        "wesentlichen neuen Markt- oder Asset-Daten früher neu bewerten."
    )
