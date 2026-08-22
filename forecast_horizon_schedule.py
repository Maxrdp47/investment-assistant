from __future__ import annotations

import calendar
from copy import deepcopy
from datetime import date
from typing import Mapping


HORIZON_COLLECTION_POLICY_VERSION = "forecast-horizon-calendar-2026.08.11-v1"
HORIZON_CADENCE = {
    "1w": {"label": "weekly", "months": 0, "days": 7},
    "1m": {"label": "biweekly", "months": 0, "days": 14},
    "3m": {"label": "monthly", "months": 1, "days": 0},
    "6m": {"label": "quarterly", "months": 3, "days": 0},
    "12m": {"label": "semiannual", "months": 6, "days": 0},
}
LONG_HORIZONS = {"6m", "12m"}


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + int(months)
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_due(last_started: date, horizon: str) -> date:
    cadence = HORIZON_CADENCE[horizon]
    if horizon == "1w":
        start_of_week = date.fromordinal(last_started.toordinal() - last_started.weekday())
        return date.fromordinal(start_of_week.toordinal() + 7)
    if cadence["months"]:
        return _add_months(last_started, int(cadence["months"]))
    return date.fromordinal(last_started.toordinal() + int(cadence["days"]))


def assess_long_horizon_eligibility(snapshot: Mapping[str, object]) -> dict:
    asset_type = str(snapshot.get("asset_type") or "")
    category = str(snapshot.get("category") or "")
    history_rows = int(snapshot.get("history_rows") or 0)
    data_quality = _finite(snapshot.get("data_quality"))
    asset_quality = _finite(snapshot.get("asset_quality"))
    price_eur = _finite(snapshot.get("price_eur"))
    reasons: list[str] = []

    if asset_type not in {"Aktie", "ETF", "Krypto"}:
        reasons.append("asset_type_not_supported")
    minimum_history = 1_095 if asset_type == "Krypto" else 750
    if history_rows < minimum_history:
        reasons.append("history_too_short")
    minimum_data_quality = 8.0 if asset_type == "Krypto" else 7.0
    if data_quality is None or data_quality < minimum_data_quality:
        reasons.append("data_quality_below_gate")
    minimum_asset_quality = 6.5 if asset_type == "Krypto" else 6.0
    if asset_quality is None or asset_quality < minimum_asset_quality:
        reasons.append("asset_quality_below_gate")
    if price_eur is None or price_eur <= 0:
        reasons.append("eur_price_missing")
    if asset_type == "Krypto" and category.casefold() == "stablecoin":
        reasons.append("stablecoin_not_directionally_suitable")

    return {
        "policy_version": HORIZON_COLLECTION_POLICY_VERSION,
        "eligible": not reasons,
        "reasons": reasons,
        "asset_type": asset_type,
        "history_rows": history_rows,
        "minimum_history_rows": minimum_history,
        "data_quality": data_quality,
        "minimum_data_quality": minimum_data_quality,
        "asset_quality": asset_quality,
        "minimum_asset_quality": minimum_asset_quality,
        "limitation": (
            "Technisches Evidenzgate für 6M/12M; kein positives oder negatives Investmenturteil."
        ),
    }


def apply_horizon_collection_policy(
    snapshot: dict,
    run_day: date,
    previous_start_dates: Mapping[str, date],
) -> dict:
    result = deepcopy(snapshot)
    eligibility = assess_long_horizon_eligibility(result)
    decisions: dict[str, dict] = {}
    due_horizons: list[str] = []

    available = {
        str(item.get("horizon")): item
        for item in result.get("horizons") or []
        if isinstance(item, dict) and item.get("horizon")
    }
    for horizon, cadence in HORIZON_CADENCE.items():
        last_started = previous_start_dates.get(horizon)
        next_due = _next_due(last_started, horizon) if last_started is not None else run_day
        cadence_due = run_day >= next_due
        eligible = horizon not in LONG_HORIZONS or bool(eligibility["eligible"])
        available_now = horizon in available
        due = cadence_due and eligible and available_now
        if due:
            due_horizons.append(horizon)
        reason = "due"
        if not available_now:
            reason = "horizon_not_produced"
        elif not cadence_due:
            reason = "cadence_not_due"
        elif not eligible:
            reason = "long_horizon_not_eligible"
        decisions[horizon] = {
            "cadence": cadence["label"],
            "due": due,
            "reason": reason,
            "last_started_on": last_started.isoformat() if last_started else None,
            "next_due_on": next_due.isoformat(),
            "requires_long_horizon_eligibility": horizon in LONG_HORIZONS,
        }

    result["horizons"] = [
        item for item in result.get("horizons") or [] if item.get("horizon") in due_horizons
    ]
    result["horizon_collection_policy"] = {
        "policy_version": HORIZON_COLLECTION_POLICY_VERSION,
        "run_date": run_day.isoformat(),
        "due_horizons": due_horizons,
        "decisions": decisions,
        "long_horizon_eligibility": eligibility,
        "append_only": True,
        "historical_forecasts_changed": False,
    }
    if not result["horizons"]:
        raise ValueError("Für dieses Asset ist kein Prognosehorizont fällig.")
    return result
