from copy import deepcopy
from datetime import date

from forecast_horizon_schedule import (
    HORIZON_COLLECTION_POLICY_VERSION,
    apply_horizon_collection_policy,
    assess_long_horizon_eligibility,
)


def snapshot(*, eligible: bool = True) -> dict:
    return {
        "ticker": "TEST",
        "asset_type": "Aktie",
        "category": "Industrials",
        "history_rows": 1_500 if eligible else 200,
        "data_quality": 8.0,
        "asset_quality": 7.0,
        "price_eur": 100.0,
        "horizons": [
            {"horizon": horizon, "days": days}
            for horizon, days in {
                "1w": 7,
                "1m": 30,
                "3m": 90,
                "6m": 180,
                "12m": 365,
            }.items()
        ],
    }


def test_first_eligible_observation_starts_all_horizons_without_mutating_input() -> None:
    original = snapshot()
    before = deepcopy(original)

    result = apply_horizon_collection_policy(original, date(2026, 8, 11), {})

    assert [item["horizon"] for item in result["horizons"]] == ["1w", "1m", "3m", "6m", "12m"]
    assert result["horizon_collection_policy"]["policy_version"] == HORIZON_COLLECTION_POLICY_VERSION
    assert result["horizon_collection_policy"]["append_only"] is True
    assert original == before


def test_cadences_are_independent_and_use_calendar_months_for_longer_periods() -> None:
    prior = {horizon: date(2026, 8, 10) for horizon in ("1w", "1m", "3m", "6m", "12m")}

    week_two = apply_horizon_collection_policy(snapshot(), date(2026, 8, 17), prior)
    biweekly = apply_horizon_collection_policy(snapshot(), date(2026, 8, 24), prior)
    monthly = apply_horizon_collection_policy(snapshot(), date(2026, 9, 10), prior)
    quarterly = apply_horizon_collection_policy(snapshot(), date(2026, 11, 10), prior)
    semiannual = apply_horizon_collection_policy(snapshot(), date(2027, 2, 10), prior)

    assert [item["horizon"] for item in week_two["horizons"]] == ["1w"]
    assert [item["horizon"] for item in biweekly["horizons"]] == ["1w", "1m"]
    assert [item["horizon"] for item in monthly["horizons"]] == ["1w", "1m", "3m"]
    assert [item["horizon"] for item in quarterly["horizons"]] == ["1w", "1m", "3m", "6m"]
    assert [item["horizon"] for item in semiannual["horizons"]] == ["1w", "1m", "3m", "6m", "12m"]


def test_weekly_horizon_starts_in_next_iso_week_after_a_late_catchup() -> None:
    prior = {"1w": date(2026, 8, 14)}

    result = apply_horizon_collection_policy(snapshot(), date(2026, 8, 17), prior)

    assert "1w" in [item["horizon"] for item in result["horizons"]]
    assert result["horizon_collection_policy"]["decisions"]["1w"]["next_due_on"] == "2026-08-17"


def test_ineligible_assets_never_force_six_or_twelve_month_horizons() -> None:
    result = apply_horizon_collection_policy(snapshot(eligible=False), date(2026, 8, 11), {})

    assert [item["horizon"] for item in result["horizons"]] == ["1w", "1m", "3m"]
    policy = result["horizon_collection_policy"]
    assert policy["long_horizon_eligibility"]["eligible"] is False
    assert "history_too_short" in policy["long_horizon_eligibility"]["reasons"]
    assert policy["decisions"]["6m"]["reason"] == "long_horizon_not_eligible"
    assert policy["decisions"]["12m"]["reason"] == "long_horizon_not_eligible"


def test_stablecoins_are_not_long_horizon_eligible() -> None:
    candidate = snapshot()
    candidate.update(
        {
            "asset_type": "Krypto",
            "category": "Stablecoin",
            "history_rows": 2_000,
            "data_quality": 9.0,
            "asset_quality": 8.0,
        }
    )

    eligibility = assess_long_horizon_eligibility(candidate)

    assert eligibility["eligible"] is False
    assert "stablecoin_not_directionally_suitable" in eligibility["reasons"]
