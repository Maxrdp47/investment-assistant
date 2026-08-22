from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

import app
from analysis_models import ModuleScore, RiskReward
from entry_plan import (
    build_buy_zones,
    recommendation_confidence_label,
    recommendation_horizon,
    recommendation_validity,
    research_action,
)


def signal(value: float) -> ModuleScore:
    return ModuleScore(value, "Signal", [])


def risk(score: float = 6.0) -> RiskReward:
    return RiskReward(-0.05, 0.10, 2.0, score, "CRV")


def test_app_reexports_extracted_entry_plan_functions_for_compatibility() -> None:
    assert app.build_buy_zones is build_buy_zones
    assert app.research_action is research_action
    assert app.recommendation_confidence_label is recommendation_confidence_label
    assert app.recommendation_horizon is recommendation_horizon
    assert app.recommendation_validity is recommendation_validity


def test_buy_zones_use_only_real_support_resistance_and_invalidation_geometry() -> None:
    supports = [95.0]
    resistances = [110.0]
    rows = build_buy_zones(
        100.0,
        supports,
        resistances,
        pd.Series({"SMA_50": 98.0}),
        "EUR",
        1.0,
        "Nur EUR",
    )

    assert [row["Marke"] for row in rows] == ["100,00 €", "95,00 €", "110,00 €", "93,10 €"]
    assert supports == [95.0]
    assert resistances == [110.0]


def test_missing_support_is_not_invented_while_valid_sma_confirmation_remains_available() -> None:
    rows = build_buy_zones(
        100.0,
        [],
        [],
        pd.Series({"SMA_50": 105.0}),
        "USD",
        0.90,
        "Nur EUR",
    )

    assert rows[1]["Marke"] == "Daten nicht verfügbar"
    assert rows[2]["Marke"] == "94,50 €"
    assert rows[3]["Marke"] == "Daten nicht verfügbar"


@pytest.mark.parametrize(
    ("buy_score", "risk_score", "supports", "expected"),
    [
        (3.0, 6.0, [98.0], "Risiko zu hoch"),
        (4.0, 6.0, [98.0], "Heute nicht kaufen"),
        (5.5, 6.0, [98.0], "Beobachten"),
        (7.0, 6.0, [98.0], "Nachkaufzone erreicht"),
        (8.0, 5.0, [90.0], "Kleine Tranche möglich"),
        (7.0, 5.0, [90.0], "Nachkauf nur bei Bestätigung"),
    ],
)
def test_research_action_thresholds_remain_explicit(
    buy_score: float,
    risk_score: float,
    supports: list[float],
    expected: str,
) -> None:
    assert research_action(signal(buy_score), risk(risk_score), supports, 100.0) == expected


def test_confidence_and_horizon_labels_remain_asset_specific() -> None:
    assert recommendation_confidence_label(None) == "niedrig"
    assert recommendation_confidence_label(5.0) == "mittel"
    assert recommendation_confidence_label(7.0) == "hoch"
    assert recommendation_horizon("Aktie") == "3–5 Jahre"
    assert recommendation_horizon("ETF") == "mindestens 5 Jahre"
    assert recommendation_horizon("Krypto") == "1–3 Jahre bei hoher Risikotoleranz"


def test_only_future_earnings_can_shorten_stock_validity() -> None:
    future = date.today() + timedelta(days=10)
    past = date.today() - timedelta(days=10)

    future_text = recommendation_validity(
        "Aktie",
        {"earningsTimestamp": pd.Timestamp(future).timestamp()},
    )
    past_text = recommendation_validity(
        "Aktie",
        {"earningsTimestamp": pd.Timestamp(past).timestamp()},
    )

    assert future.strftime("%d.%m.%Y") in future_text
    assert "nächsten Quartalszahlen" in future_text
    assert "nächsten Quartalszahlen" not in past_text
    assert "maximal 30 Tage" in past_text
