from __future__ import annotations

"""Read-only diagnostics for historical and real-forward Swing evidence.

The functions in this module never append events, mutate a strategy or promote a
challenger. They only combine immutable signal/event evidence with an optional
point-in-time context reconstructed from an already frozen OHLCV dataset.
Unknown prices and ambiguous intrabar ordering remain unknown.
"""

import math
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median
from typing import Mapping, Sequence

import pandas as pd


DIAGNOSTIC_VERSION = "swing-edge-diagnostics-2026.08.22-v3"
FORWARD_STOPOUT_FORENSICS_VERSION = "swing-forward-stopout-forensics-2026.08.22-v2"
FORWARD_COUNTERFACTUAL_VERSION = "swing-forward-diagnostic-counterfactuals-2026.08.22-v2"
MINIMUM_SEGMENT_CASES_FOR_INTERPRETATION = 20

FORWARD_STATUS_REQUIRED_CASE_FIELDS = (
    "symbol",
    "signal_day",
    "setup_family",
    "asset_type",
    "region",
    "issuer_cluster",
    "entry_original",
    "initial_stop_original",
    "initial_stop_distance_pct",
    "stop_distance_atr",
    "result_r",
    "mfe_r",
    "mfe_pct",
    "mae_r",
    "mae_pct",
    "maximum_intermediate_profit_r",
    "mfe_at_least_0_5r",
    "mfe_at_least_1r",
    "mfe_at_least_1_5r",
    "mfe_at_least_2r",
    "observed_sessions_to_maximum_mfe",
    "observed_sessions_to_terminal",
    "terminal_event",
    "gap_below_stop",
    "stop_execution_worse_than_planned",
    "stop_execution_deviation_r",
    "stop_execution_deviation_pct",
    "rsi_14",
    "ema20_relative_to_ema50_state",
    "price_relative_to_ema20_state",
    "price_relative_to_ema50_state",
    "buyer_confirmation",
    "market_structure_state",
    "market_phase",
    "volatility_regime",
    "stopout_class",
    "stopout_class_reason",
    "post_stop_counterfactuals",
)


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _terminal_event(case: Mapping[str, object]) -> dict:
    terminal_types = {
        "target_1_reached",
        "target_2_reached",
        "stop_reached",
        "ambiguous_sequence",
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
        "expired_unfilled",
        "expired_time_exit",
        "not_evaluable",
    }
    for event in reversed(list(case.get("events") or [])):
        item = dict(event or {})
        payload = dict(item.get("payload") or {})
        if item.get("event_type") in terminal_types and (
            item.get("event_type") != "target_1_reached" or payload.get("terminal", True)
        ):
            return item
    return {}


def _entry_event(case: Mapping[str, object]) -> dict:
    for event in list(case.get("events") or []):
        item = dict(event or {})
        if item.get("event_type") == "paper_entry_opened":
            return item
    return {}


def _case_identity(case: Mapping[str, object]) -> str:
    identity = dict(case.get("research_identity") or {})
    snapshot = dict(case.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    return str(
        identity.get("issuer_id")
        or asset.get("issuer_id")
        or case.get("symbol")
        or asset.get("ticker")
        or "Unbekannt"
    )


def _evidence_session_count(
    case: Mapping[str, object], entry_at: datetime | None, terminal_at: datetime | None
) -> tuple[int | None, str]:
    if entry_at is None or terminal_at is None:
        return None, "entry_or_terminal_timestamp_missing"
    days: set[str] = set()
    for raw_event in case.get("events") or []:
        event = dict(raw_event or {})
        event_at = _timestamp(event.get("occurred_at"))
        if event_at is not None and entry_at <= event_at <= terminal_at:
            # Count only exchange-local dates for which evidence exists. This is
            # intentionally not an invented exchange calendar.
            days.add(event_at.date().isoformat())
    return (
        (len(days), "observed_event_sessions_lower_bound")
        if days
        else (None, "no_session_evidence_stored")
    )


def _context_for_case(
    case: Mapping[str, object], contexts: Mapping[str, Mapping[str, object]] | None
) -> dict:
    if not contexts:
        return {}
    snapshot = dict(case.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    plan = dict(snapshot.get("order_plan") or {})
    keys = (
        str(case.get("signal_id") or case.get("case_id") or ""),
        f"{asset.get('ticker') or case.get('symbol') or ''}|{plan.get('signal_bar_day') or str(snapshot.get('signal_at') or case.get('signal_at') or '')[:10]}",
        str(asset.get("ticker") or case.get("symbol") or ""),
    )
    for key in keys:
        if key and key in contexts:
            return dict(contexts[key])
    return {}


def _frozen_recovery_windows(
    later: pd.DataFrame,
    *,
    scale: float | None,
) -> dict[str, dict[str, object]]:
    windows: dict[str, dict[str, object]] = {}
    for horizon in (5, 20):
        key = str(horizon)
        if scale is None or len(later) < horizon:
            windows[key] = {
                "status": "insufficient_completed_frozen_sessions",
                "horizon_sessions": horizon,
                "sessions_available": len(later),
                "diagnostic_only": True,
                "real_forward_result": False,
            }
            continue
        window = later.iloc[:horizon]
        reference = _number(window.iloc[0].get("Open"))
        maximum = _number(window["High"].max())
        minimum = _number(window["Low"].min())
        outcome = _number(window.iloc[-1].get("Close"))
        if reference is None or maximum is None or minimum is None or outcome is None:
            windows[key] = {
                "status": "frozen_window_prices_unavailable",
                "horizon_sessions": horizon,
                "sessions_available": len(window),
                "diagnostic_only": True,
                "real_forward_result": False,
            }
            continue
        reference *= scale
        maximum *= scale
        minimum *= scale
        outcome *= scale
        windows[key] = {
            "status": "available_from_frozen_completed_daily_sessions",
            "source": "frozen_dataset",
            "horizon_sessions": horizon,
            "sessions_available": len(window),
            "reference_day": pd.Timestamp(window.index[0]).date().isoformat(),
            "reference_price_original": reference,
            "outcome_day": pd.Timestamp(window.index[-1]).date().isoformat(),
            "outcome_close_original": outcome,
            "maximum_high_original": maximum,
            "minimum_low_original": minimum,
            "maximum_favorable_excursion_pct": (maximum / reference - 1) * 100,
            "maximum_adverse_excursion_pct": (minimum / reference - 1) * 100,
            "diagnostic_only": True,
            "real_forward_result": False,
            "intrabar_order_proven": False,
        }
    return windows


def build_frozen_forward_context(
    case: Mapping[str, object],
    raw_history: pd.DataFrame,
    *,
    dataset_fingerprint: str,
) -> dict[str, object]:
    """Reconstruct signal-day facts from frozen bars without reading future labels."""
    from swing_broad_research import (  # Local import keeps the pure report lightweight.
        _prepare_historical_indicators,
        build_broad_research_feature,
    )
    from swing_research_dataset import normalized_research_history

    snapshot = dict(case.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    plan = dict(snapshot.get("order_plan") or {})
    strategy = dict(snapshot.get("strategy") or {})
    signal_day = str(
        plan.get("signal_bar_day")
        or snapshot.get("signal_at")
        or case.get("signal_at")
        or ""
    )[:10]
    symbol = str(asset.get("ticker") or case.get("symbol") or "").upper()
    if raw_history is None or raw_history.empty:
        return {
            "status": "frozen_history_unavailable",
            "symbol": symbol,
            "signal_day": signal_day,
            "dataset_fingerprint": dataset_fingerprint,
            "future_bars_used_for_features": 0,
        }
    full = normalized_research_history(raw_history)
    signal_positions = [
        index
        for index, day in enumerate(full.index)
        if pd.Timestamp(day).date().isoformat() == signal_day
    ]
    if not signal_positions:
        return {
            "status": "signal_day_not_in_frozen_history",
            "symbol": symbol,
            "signal_day": signal_day,
            "frozen_last_day": pd.Timestamp(full.index[-1]).date().isoformat() if len(full) else None,
            "dataset_fingerprint": dataset_fingerprint,
            "future_bars_used_for_features": 0,
        }
    signal_position_full = signal_positions[-1]
    causal = _prepare_historical_indicators(full.iloc[: signal_position_full + 1].copy())
    if len(causal) < 220:
        return {
            "status": "insufficient_causal_history",
            "symbol": symbol,
            "signal_day": signal_day,
            "causal_rows": len(causal),
            "dataset_fingerprint": dataset_fingerprint,
            "future_bars_used_for_features": 0,
        }
    setup_text = str(strategy.get("setup_type") or "").casefold()
    setup_family = (
        "objective_breakout"
        if "ausbruch" in setup_text or "breakout" in setup_text
        else "objective_pullback"
    )
    feature_asset = {
        "ticker": symbol,
        "name": asset.get("name") or symbol,
        "asset_type": asset.get("asset_type"),
        "region": asset.get("region"),
        "category": asset.get("category"),
        "exchange": asset.get("exchange"),
        "isin": asset.get("isin"),
    }
    feature = build_broad_research_feature(
        symbol,
        feature_asset,
        causal,
        len(causal) - 1,
        setup_family,
        dataset_fingerprint=dataset_fingerprint,
    )
    technical = dict(feature.get("technical") or {})
    pullback = dict(feature.get("pullback") or {})
    structure = dict(feature.get("market_structure") or {})
    fibonacci = dict(feature.get("fibonacci") or {})
    opening_levels = dict(feature.get("opening_levels") or {})
    cot = dict(feature.get("cot") or {})
    signal_close = _number(causal.iloc[-1].get("Close"))
    price_anchor = _number(plan.get("limit_price_original")) or _number(
        plan.get("activation_price_original")
    )
    scale = price_anchor / signal_close if signal_close and price_anchor and signal_close > 0 else None
    atr_adjusted = _number(technical.get("atr_14"))
    atr_original = atr_adjusted * scale if atr_adjusted is not None and scale else None
    pullback_low_adjusted = _number(pullback.get("pullback_low"))
    pullback_low_original = (
        pullback_low_adjusted * scale
        if pullback_low_adjusted is not None and scale
        else None
    )
    entry_event = _entry_event(case)
    terminal_event = _terminal_event(case)
    entry = _number(
        dict(entry_event.get("payload") or {}).get("paper_entry_after_costs_original")
    )
    terminal_at = _timestamp(terminal_event.get("occurred_at"))
    recovery = {
        "status": "no_frozen_sessions_after_terminal",
        "sessions": 0,
        "recovered_entry": None,
        "maximum_high_original": None,
    }
    recovery_windows = _frozen_recovery_windows(pd.DataFrame(), scale=scale)
    if terminal_at is not None and scale:
        later = full[
            [pd.Timestamp(index).date() > terminal_at.date() for index in full.index]
        ]
        recovery_windows = _frozen_recovery_windows(later, scale=scale)
        if not later.empty:
            maximum_high = float(later["High"].max()) * scale
            recovery = {
                "status": "measured_from_frozen_daily_bars_after_terminal",
                "sessions": len(later),
                "through_day": pd.Timestamp(later.index[-1]).date().isoformat(),
                "maximum_high_original": maximum_high,
                "recovered_entry": maximum_high >= entry if entry is not None else None,
                "intrabar_order_inferred": False,
            }
    return {
        "status": "available",
        "symbol": symbol,
        "signal_day": signal_day,
        "setup_family": setup_family,
        "dataset_fingerprint": dataset_fingerprint,
        "frozen_last_day": pd.Timestamp(full.index[-1]).date().isoformat(),
        "feature_at": feature.get("feature_at"),
        "feature_fingerprint": feature.get("feature_fingerprint"),
        "future_bars_used_for_features": 0,
        "price_scale": scale,
        "price_scale_status": (
            "stored_order_limit_divided_by_frozen_signal_close"
            if scale is not None
            else "unavailable"
        ),
        "signal_close_adjusted": signal_close,
        "atr_14_original": atr_original,
        "atr_14_pct_of_signal_close": (
            atr_adjusted / signal_close * 100
            if atr_adjusted is not None and signal_close
            else None
        ),
        "rsi_14": technical.get("rsi_14"),
        "ema_20": technical.get("ema_20"),
        "ema_50": technical.get("ema_50"),
        "close_relative_to_ema20": technical.get("close_relative_to_ema20"),
        "close_relative_to_ema50": technical.get("close_relative_to_ema50"),
        "ema20_relative_to_ema50": technical.get("ema20_relative_to_ema50"),
        "buyer_confirmation": pullback.get("buyer_confirmation_close_above_prior_high"),
        "bearish_candles": pullback.get("bearish_candles"),
        "fibonacci_inside_0618_0786": fibonacci.get("inside_0618_0786"),
        "bos_close_break": structure.get("close_break"),
        "bos_close_break_excess_atr": structure.get("close_break_excess_atr"),
        "opening_level_contact": any(
            bool(dict(value or {}).get("contact")) for value in opening_levels.values()
        ),
        "cot_status": cot.get("status"),
        "last_swing_low": structure.get("last_swing_low"),
        "last_swing_high": structure.get("last_swing_high"),
        "market_structure_classification": list(
            structure.get("current_high_low_classification") or []
        ),
        "pullback_low_original": pullback_low_original,
        "pullback_low_status": pullback.get("status") or "unavailable",
        "post_terminal_recovery": recovery,
        "post_terminal_recovery_windows": recovery_windows,
    }


def _threshold_observation(
    *, threshold_pct: float | None, observed_pct: float | None, direction: str
) -> dict[str, object]:
    if threshold_pct is None or threshold_pct <= 0 or observed_pct is None:
        return {"status": "unavailable", "threshold_pct": threshold_pct}
    touched = observed_pct >= threshold_pct
    return {
        "status": (
            f"{direction}_threshold_reached_before_or_on_terminal_observation"
            if touched
            else f"{direction}_threshold_not_reached_before_original_terminal"
        ),
        "threshold_pct": threshold_pct,
        "observed_pct": observed_pct,
        "touched": touched,
        "intrabar_order_proven": False,
    }


def _forward_counterfactuals(
    *,
    entry: float | None,
    existing_stop: float | None,
    plan: Mapping[str, object],
    context: Mapping[str, object],
    mfe_pct: float | None,
    mae_pct: float | None,
    actual_result_r: float | None,
    terminal_type: str,
) -> dict[str, object]:
    if entry is None or entry <= 0:
        return {
            "version": FORWARD_COUNTERFACTUAL_VERSION,
            "status": "entry_unavailable",
            "diagnostic_only": True,
            "real_forward_result": False,
        }
    atr = _number(context.get("atr_14_original"))
    pullback_low = _number(context.get("pullback_low_original"))
    stop_levels = {
        "existing_stop": existing_stop,
        "pullback_low": pullback_low,
        "pullback_low_atr_buffer": (
            pullback_low - 0.25 * atr
            if pullback_low is not None and atr is not None
            else None
        ),
        "atr_2_stop": entry - 2.0 * atr if atr is not None else None,
    }
    adverse_pct = abs(min(mae_pct or 0.0, 0.0)) if mae_pct is not None else None
    target_1 = _number(plan.get("target_1_original"))
    target_2 = _number(plan.get("target_2_original"))
    variants: dict[str, dict] = {}
    for name, level in stop_levels.items():
        if level is None or not 0 < level < entry:
            variants[name] = {"status": "unavailable_or_invalid", "stop": level}
            continue
        risk_pct = (entry - level) / entry * 100
        stop_observation = _threshold_observation(
            threshold_pct=risk_pct,
            observed_pct=adverse_pct,
            direction="stop",
        )
        exits: dict[str, dict] = {
            f"fixed_{target:g}r": _threshold_observation(
                threshold_pct=target * risk_pct,
                observed_pct=mfe_pct,
                direction="target",
            )
            for target in (1.0, 1.5, 2.0, 3.0)
        }
        for target_name, target in (
            ("existing_target_1", target_1),
            ("existing_target_2", target_2),
        ):
            if target is not None and target > entry:
                exits[target_name] = _threshold_observation(
                    threshold_pct=(target / entry - 1) * 100,
                    observed_pct=mfe_pct,
                    direction="target",
                )
        if name == "existing_stop" and terminal_type in {
            "stop_reached",
            "ambiguous_sequence",
        }:
            observed_outcome = {
                "status": "actual_stored_real_forward_stop",
                "result_r": actual_result_r,
                "real_forward_result": True,
            }
        else:
            stop_touched = stop_observation.get("touched")
            reached = [item for item in exits.values() if item.get("touched")]
            if stop_touched and reached:
                state = "indeterminate_stop_target_order"
            elif stop_touched:
                state = "counterfactual_stop_touched_before_or_on_original_terminal"
            elif reached:
                state = "counterfactual_target_touched_before_or_on_original_terminal"
            else:
                state = "counterfactual_still_open_at_original_terminal"
            observed_outcome = {
                "status": state,
                "result_r": None,
                "real_forward_result": False,
            }
        variants[name] = {
            "status": "observed_threshold_comparison_only",
            "stop": level,
            "stop_distance_pct": risk_pct,
            "stop_observation": stop_observation,
            "exits": exits,
            "outcome_at_original_terminal": observed_outcome,
        }
    return {
        "version": FORWARD_COUNTERFACTUAL_VERSION,
        "status": "available_with_explicit_ordering_limits",
        "same_stored_entry_for_all_variants": True,
        "observed_only_through_original_terminal": True,
        "intrabar_order_invented": False,
        "later_recovery": dict(context.get("post_terminal_recovery") or {}),
        "variants": variants,
        "diagnostic_only": True,
        "automatic_rule_change": False,
    }


def _stored_recovery_windows(case: Mapping[str, object]) -> dict[str, dict[str, object]]:
    windows: dict[str, dict[str, object]] = {}
    for raw_event in case.get("events") or []:
        event = dict(raw_event or {})
        if event.get("event_type") != "counterfactual_outcome":
            continue
        payload = dict(event.get("payload") or {})
        if payload.get("not_a_trade_result") is not True:
            continue
        horizon = int(_number(payload.get("horizon_sessions")) or 0)
        if horizon not in {5, 20}:
            continue
        reference = _number(payload.get("reference_price_original"))
        maximum_pct = _number(payload.get("maximum_favorable_excursion_pct"))
        minimum_pct = _number(payload.get("maximum_adverse_excursion_pct"))
        windows[str(horizon)] = {
            "status": "available_from_append_only_counterfactual_event",
            "source": "stored_counterfactual_outcome_event",
            "horizon_sessions": horizon,
            "sessions_available": horizon,
            "reference_day": payload.get("reference_day"),
            "reference_price_original": reference,
            "outcome_day": payload.get("outcome_day"),
            "outcome_close_original": _number(payload.get("outcome_close_original")),
            "maximum_high_original": (
                reference * (1 + maximum_pct / 100)
                if reference is not None and maximum_pct is not None
                else None
            ),
            "minimum_low_original": (
                reference * (1 + minimum_pct / 100)
                if reference is not None and minimum_pct is not None
                else None
            ),
            "maximum_favorable_excursion_pct": maximum_pct,
            "maximum_adverse_excursion_pct": minimum_pct,
            "diagnostic_only": True,
            "real_forward_result": False,
            "intrabar_order_proven": False,
        }
    return windows


def _unavailable_recovery_window(
    horizon: int, status: str = "not_available"
) -> dict[str, object]:
    return {
        "status": status,
        "horizon_sessions": horizon,
        "sessions_available": 0,
        "maximum_recovery_after_stop_pct": None,
        "maximum_recovery_from_original_entry_r": None,
        "target_1_reached_after_stop": None,
        "target_2_reached_after_stop": None,
        "stop_variants": {},
        "diagnostic_only": True,
        "real_forward_result": False,
        "intrabar_order_proven": False,
    }


def _post_stop_counterfactuals(
    case: Mapping[str, object],
    *,
    entry: float | None,
    plan: Mapping[str, object],
    counterfactuals: Mapping[str, object],
    context: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    stored = _stored_recovery_windows(case)
    frozen = {
        str(key): dict(value or {})
        for key, value in dict(context.get("post_terminal_recovery_windows") or {}).items()
    }
    variants = {
        str(key): dict(value or {})
        for key, value in dict(counterfactuals.get("variants") or {}).items()
    }
    target_1 = _number(plan.get("target_1_original"))
    target_2 = _number(plan.get("target_2_original"))
    initial_stop = _number(plan.get("initial_stop_original"))
    original_risk = (
        entry - initial_stop
        if entry is not None and initial_stop is not None and entry > initial_stop
        else None
    )
    result: dict[str, dict[str, object]] = {}
    for horizon in (5, 20):
        key = str(horizon)
        raw = dict(stored.get(key) or frozen.get(key) or {})
        if not str(raw.get("status") or "").startswith("available"):
            result[key] = _unavailable_recovery_window(
                horizon, str(raw.get("status") or "not_available")
            )
            result[key]["sessions_available"] = int(
                _number(raw.get("sessions_available")) or 0
            )
            continue
        maximum_high = _number(raw.get("maximum_high_original"))
        minimum_low = _number(raw.get("minimum_low_original"))
        outcome_close = _number(raw.get("outcome_close_original"))
        maximum_recovery_pct = _number(raw.get("maximum_favorable_excursion_pct"))
        target_1_reached = (
            maximum_high >= target_1
            if maximum_high is not None and target_1 is not None
            else None
        )
        target_2_reached = (
            maximum_high >= target_2
            if maximum_high is not None and target_2 is not None
            else None
        )
        variant_rows: dict[str, dict[str, object]] = {}
        for name, variant in variants.items():
            level = _number(variant.get("stop"))
            preterminal_touched = dict(variant.get("stop_observation") or {}).get(
                "touched"
            )
            later_touched = (
                minimum_low <= level
                if minimum_low is not None and level is not None
                else None
            )
            held = (
                preterminal_touched is False and later_touched is False
                if later_touched is not None
                else None
            )
            variant_risk = (
                entry - level
                if entry is not None and level is not None and entry > level
                else None
            )
            target_touched = bool(target_1_reached or target_2_reached)
            if preterminal_touched is True:
                outcome_status = "stop_already_touched_by_original_terminal"
                result_r = None
                basis = "ordering_or_execution_not_replayed"
            elif later_touched is True and target_touched:
                outcome_status = "stop_and_target_touched_order_indeterminate"
                result_r = None
                basis = "aggregate_daily_window_has_no_intrabar_order"
            elif later_touched is True:
                outcome_status = "counterfactual_stop_touched"
                result_r = -1.0
                basis = "nominal_stop_r_before_costs_and_gap_execution"
            elif target_2_reached is True and target_2 is not None and variant_risk:
                outcome_status = "target_2_threshold_reached"
                result_r = (target_2 - entry) / variant_risk
                basis = "threshold_r_not_replayed_position_management"
            elif target_1_reached is True and target_1 is not None and variant_risk:
                outcome_status = "target_1_threshold_reached"
                result_r = (target_1 - entry) / variant_risk
                basis = "threshold_r_not_replayed_position_management"
            elif outcome_close is not None and entry is not None and variant_risk:
                outcome_status = "held_to_horizon_close"
                result_r = (outcome_close - entry) / variant_risk
                basis = "mark_to_horizon_close_before_exit_costs"
            else:
                outcome_status = "counterfactual_result_unavailable"
                result_r = None
                basis = "required_prices_missing"
            variant_rows[name] = {
                "stop": level,
                "stop_held_through_horizon": held,
                "stop_touched_before_or_on_original_terminal": preterminal_touched,
                "stop_touched_after_original_exit": later_touched,
                "counterfactual_result_status": outcome_status,
                "counterfactual_result_r": result_r,
                "counterfactual_result_basis": basis,
                "diagnostic_only": True,
                "real_forward_result": False,
            }
        result[key] = {
            **raw,
            "maximum_recovery_after_stop_pct": maximum_recovery_pct,
            "maximum_recovery_from_original_entry_r": (
                (maximum_high - entry) / original_risk
                if maximum_high is not None and entry is not None and original_risk
                else None
            ),
            "target_1_reached_after_stop": target_1_reached,
            "target_2_reached_after_stop": target_2_reached,
            "stop_variants": variant_rows,
            "diagnostic_only": True,
            "real_forward_result": False,
            "intrabar_order_proven": False,
        }
    return result


def _sessions_to_maximum_mfe(
    case: Mapping[str, object],
    *,
    entry_at: datetime | None,
    terminal_at: datetime | None,
    terminal_mfe_pct: float | None,
) -> tuple[int | None, str]:
    if entry_at is None or terminal_at is None or terminal_mfe_pct is None:
        return None, "entry_terminal_or_mfe_missing"
    first_maximum_at: datetime | None = None
    for raw_event in case.get("events") or []:
        event = dict(raw_event or {})
        event_at = _timestamp(event.get("occurred_at"))
        observed_mfe = _number(dict(event.get("payload") or {}).get(
            "maximum_favorable_excursion_pct"
        ))
        if (
            event_at is not None
            and entry_at <= event_at <= terminal_at
            and observed_mfe is not None
            and observed_mfe >= terminal_mfe_pct - 1e-9
        ):
            first_maximum_at = event_at
            break
    if first_maximum_at is None:
        return None, "maximum_mfe_timestamp_not_stored"
    sessions, _ = _evidence_session_count(case, entry_at, first_maximum_at)
    return (
        (sessions, "observed_event_sessions_lower_bound_to_first_stored_maximum")
        if sessions is not None
        else (None, "no_session_evidence_to_maximum")
    )


def _relative_state(value: object, *, above: str, below: str) -> str:
    ratio = _number(value)
    if ratio is None:
        return "nicht verfügbar"
    if math.isclose(ratio, 1.0, rel_tol=0.0, abs_tol=1e-9):
        return "gleich"
    return above if ratio > 1 else below


def _normalized_setup(value: object, fallback: object = None) -> str:
    text = str(value or fallback or "").casefold()
    if "ausbruch" in text or "breakout" in text:
        return "Breakout"
    if "pullback" in text or "rücklauf" in text:
        return "Pullback"
    return "nicht verfügbar"


def _classification(row: Mapping[str, object]) -> dict[str, object]:
    if not row.get("stopped"):
        return {
            "code": "G",
            "label": "nicht bestimmbar",
            "reason": "Kein abgeschlossener Stopout.",
        }
    if row.get("gap_below_stop"):
        return {
            "code": "D",
            "label": "Gap/Ausführung",
            "reason": "Der gespeicherte Stopout war ein Gap am oder unter dem Stop.",
        }
    counterfactuals = dict(row.get("counterfactuals") or {})
    variants = dict(counterfactuals.get("variants") or {})
    wider_held = any(
        name != "existing_stop"
        and dict(value.get("stop_observation") or {}).get("touched") is False
        for name, value in variants.items()
        if isinstance(value, Mapping)
    )
    recovery = dict(counterfactuals.get("later_recovery") or {})
    if wider_held and recovery.get("recovered_entry") is True:
        return {
            "code": "C",
            "label": "enger Stop, spätere Erholung",
            "reason": "Mindestens ein vorab definierter weiterer Stop hielt und eingefrorene spätere Bars erholten sich über den Einstieg.",
        }
    mfe_r = _number(row.get("maximum_r_before_stop"))
    if mfe_r is not None and mfe_r >= 1.0:
        return {
            "code": "B",
            "label": "zunächst günstig, dann Stop",
            "reason": "Die gespeicherte MFE erreichte mindestens 1R; die genaue Intrabar-Reihenfolge bleibt unbehauptet.",
        }
    stop_atr = _number(row.get("stop_distance_atr"))
    if (
        wider_held
        and mfe_r is not None
        and mfe_r >= 0.5
        and stop_atr is not None
        and stop_atr < 1.0
    ):
        return {
            "code": "F",
            "label": "mögliche Stopkalibrierung",
            "reason": "Der vorhandene Stop lag unter 1 ATR, während mindestens ein vorab definierter weiterer Stop bis zum Originalende nicht berührt wurde.",
        }
    if bool(row.get("entry_timing_warning")):
        return {
            "code": "E",
            "label": "mögliches Einstiegstiming",
            "reason": "Ein kausal gespeicherter Timing-Hinweis liegt vor; dies ist keine Regeländerung.",
        }
    if mfe_r is not None and mfe_r < 0.5:
        return {
            "code": "A",
            "label": "sofort schwach/niedrige MFE",
            "reason": "Vor dem Stop wurden weniger als 0,5R günstige Bewegung beobachtet.",
        }
    return {
        "code": "G",
        "label": "nicht bestimmbar",
        "reason": "Die vorhandene Evidenz trennt Einstiegs- und Stopursache nicht belastbar.",
    }


def _plain_number(value: object, suffix: str = "", digits: int = 2) -> str:
    number = _number(value)
    return "nicht verfügbar" if number is None else f"{number:.{digits}f}{suffix}"


def _concrete_class_reason(
    row: Mapping[str, object], classification: Mapping[str, object]
) -> str:
    code = str(classification.get("code") or "G")
    result = _plain_number(row.get("result_r"), "R")
    mfe = _plain_number(row.get("mfe_r"), "R")
    sessions = row.get("observed_sessions_to_terminal")
    duration = (
        f"{sessions} beobachtete Sitzungen"
        if sessions is not None
        else "Sitzungszahl nicht verfügbar"
    )
    if code == "A":
        return f"Nur {mfe} MFE (<0,5R), danach {result} nach {duration}; kaum positive Bewegung belegt."
    if code == "B":
        return f"Zunächst {mfe} MFE (mindestens 1R), später {result} nach {duration}; Intrabar-Reihenfolge bleibt offen."
    if code == "C":
        return f"Mindestens ein vorab definierter weiterer Stop hielt bis zum ursprünglichen Exit; spätere gespeicherte Kurse erholten sich über den Einstieg. Echtes Ergebnis blieb {result}."
    if code == "D":
        deviation_r = _plain_number(row.get("stop_execution_deviation_r"), "R")
        deviation_pct = _plain_number(row.get("stop_execution_deviation_pct"), "%")
        return f"Gespeicherter Gap-Stop; tatsächliche Ausführung wich um {deviation_r} beziehungsweise {deviation_pct} vom geplanten Stop ab. Ergebnis {result}."
    if code == "E":
        return f"Ein zum Signalzeitpunkt gespeicherter Timing-Hinweis liegt vor; MFE {mfe}, Ergebnis {result}. Keine Regeländerung."
    if code == "F":
        held = []
        variants = dict(dict(row.get("counterfactuals") or {}).get("variants") or {})
        for name, raw in variants.items():
            if name != "existing_stop" and dict(dict(raw or {}).get("stop_observation") or {}).get("touched") is False:
                held.append(name)
        held_text = ", ".join(held) if held else "keine Variante belastbar"
        return f"Stopweite {_plain_number(row.get('stop_distance_atr'), ' ATR')} bei {mfe} MFE; bis zum Originalende hielten: {held_text}. Ergebnis {result}."
    if not row.get("stopped"):
        return f"Kein Stopout; Ergebnis {result}. Die Stopout-Ursachenklassen A–F sind nicht anwendbar."
    return f"MFE {mfe}, Ergebnis {result}, {duration}; vorhandene Evidenz trennt Entry-, Stop- und Ausführungsursache nicht belastbar."


def swing_edge_case_diagnostic(
    case: Mapping[str, object],
    *,
    context: Mapping[str, object] | None = None,
) -> dict:
    """Extract causal, already-stored diagnostic facts for one case."""
    snapshot = dict(case.get("snapshot") or {})
    strategy = dict(snapshot.get("strategy") or {})
    asset = dict(snapshot.get("asset") or {})
    features = dict(snapshot.get("signal_features") or {})
    plan = dict(snapshot.get("order_plan") or {})
    entry_event = _entry_event(case)
    terminal_event = _terminal_event(case)
    entry_payload = dict(entry_event.get("payload") or {})
    terminal_payload = dict(terminal_event.get("payload") or {})
    frozen = dict(context or {})

    result_r = _number(case.get("result_r"))
    if result_r is None:
        result_r = _number(terminal_payload.get("result_r"))
    entry = _number(entry_payload.get("paper_entry_after_costs_original"))
    if entry is None:
        entry = _number(plan.get("limit_price_original"))
    stop = _number(plan.get("initial_stop_original"))
    initial_risk_pct = (
        (entry - stop) / entry * 100
        if entry is not None and stop is not None and entry > stop and entry > 0
        else _number(features.get("risk_pct"))
    )
    mfe_pct = _number(terminal_payload.get("maximum_favorable_excursion_pct"))
    mae_pct = _number(terminal_payload.get("maximum_adverse_excursion_pct"))
    mfe_r = mfe_pct / initial_risk_pct if mfe_pct is not None and initial_risk_pct else None
    mae_r = mae_pct / initial_risk_pct if mae_pct is not None and initial_risk_pct else None
    atr = _number(frozen.get("atr_14_original")) or _number(features.get("atr_14"))
    stop_distance_atr = (
        (entry - stop) / atr
        if entry is not None and stop is not None and atr is not None and atr > 0
        else None
    )

    entry_at = _timestamp(entry_event.get("occurred_at"))
    terminal_at = _timestamp(terminal_event.get("occurred_at"))
    calendar_days_to_terminal = (
        (terminal_at - entry_at).total_seconds() / 86_400
        if entry_at is not None and terminal_at is not None
        else None
    )
    evidence_sessions, session_status = _evidence_session_count(case, entry_at, terminal_at)
    mfe_sessions, mfe_session_status = _sessions_to_maximum_mfe(
        case,
        entry_at=entry_at,
        terminal_at=terminal_at,
        terminal_mfe_pct=mfe_pct,
    )
    interval = str(terminal_payload.get("interval") or "")
    stopped = terminal_event.get("event_type") in {"stop_reached", "ambiguous_sequence"}
    if stopped and mfe_pct is not None:
        mfe_before_stop_status = (
            "not_provable_inside_daily_bar"
            if interval.lower() in {"1d", "1day"}
            else "measured_before_or_on_terminal_intraday_bar_order_not_invented"
        )
    else:
        mfe_before_stop_status = "not_applicable_or_unavailable"
    previous_events = [
        dict(event or {})
        for event in case.get("events") or []
        if _timestamp(dict(event or {}).get("occurred_at")) is not None
        and terminal_at is not None
        and _timestamp(dict(event or {}).get("occurred_at")) < terminal_at
    ]
    last_pre_exit = previous_events[-1] if previous_events else {}
    counterfactuals = _forward_counterfactuals(
        entry=entry,
        existing_stop=stop,
        plan=plan,
        context=frozen,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        actual_result_r=result_r,
        terminal_type=str(terminal_event.get("event_type") or ""),
    )
    post_stop_counterfactuals = _post_stop_counterfactuals(
        case,
        entry=entry,
        plan=plan,
        counterfactuals=counterfactuals,
        context=frozen,
    )
    paper_exit = _number(terminal_payload.get("paper_exit_original"))
    stop_execution_worse = (
        paper_exit < stop
        if stopped and paper_exit is not None and stop is not None
        else None
    )
    stop_execution_deviation_r = (
        (paper_exit - stop) / (entry - stop)
        if stopped
        and paper_exit is not None
        and stop is not None
        and entry is not None
        and entry > stop
        else None
    )
    stop_execution_deviation_pct = (
        (paper_exit / stop - 1) * 100
        if stopped and paper_exit is not None and stop is not None and stop > 0
        else None
    )
    close_relative_to_ema20 = frozen.get("close_relative_to_ema20")
    close_relative_to_ema50 = frozen.get("close_relative_to_ema50")
    ema20_relative_to_ema50 = frozen.get("ema20_relative_to_ema50") or features.get(
        "ema20_relative_to_ema50"
    )
    structure_classes = list(frozen.get("market_structure_classification") or [])
    bos_close_break = frozen.get("bos_close_break")
    market_structure_state = (
        f"BOS-Close={'ja' if bos_close_break else 'nein'}; "
        + ("/".join(str(value) for value in structure_classes) if structure_classes else "Swing-Klassen nicht verfügbar")
        if bos_close_break is not None or structure_classes
        else "nicht verfügbar"
    )
    row = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "forensics_version": FORWARD_STOPOUT_FORENSICS_VERSION,
        "case_id": str(case.get("signal_id") or case.get("case_id") or ""),
        "signal_at": snapshot.get("signal_at") or case.get("signal_at"),
        "signal_day": plan.get("signal_bar_day")
        or str(snapshot.get("signal_at") or case.get("signal_at") or "")[:10],
        "symbol": str(asset.get("ticker") or case.get("symbol") or ""),
        "issuer_cluster": _case_identity(case),
        "issuer_cluster_status": (
            "point_in_time_stored"
            if (case.get("research_identity") or asset.get("issuer_id"))
            else "ticker_fallback_issuer_not_stored"
        ),
        "correlation_cluster": None,
        "correlation_cluster_status": "not_stored_per_forward_signal",
        "entry_original": entry,
        "initial_stop_original": stop,
        "paper_exit_original": paper_exit,
        "result_r": result_r,
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "maximum_r_before_stop": mfe_r,
        "maximum_intermediate_profit_r": mfe_r,
        "mfe_at_least_0_5r": mfe_r >= 0.5 if mfe_r is not None else None,
        "mfe_at_least_1r": mfe_r >= 1.0 if mfe_r is not None else None,
        "mfe_at_least_1_5r": mfe_r >= 1.5 if mfe_r is not None else None,
        "mfe_at_least_2r": mfe_r >= 2.0 if mfe_r is not None else None,
        "mfe_before_stop_status": mfe_before_stop_status,
        "initial_stop_distance_pct": initial_risk_pct,
        "atr_14_original": atr,
        "atr_14_pct_of_signal_close": frozen.get("atr_14_pct_of_signal_close"),
        "stop_distance_atr": stop_distance_atr,
        "stop_distance_atr_status": (
            "reconstructed_from_frozen_signal_day_without_future_bars"
            if stop_distance_atr is not None
            else "not_stored_or_reconstructable"
        ),
        "distance_to_stop_just_before_exit_pct": None,
        "distance_to_stop_just_before_exit_status": "price_not_stored_in_last_pre_exit_event",
        "last_pre_exit_observation_at": last_pre_exit.get("occurred_at"),
        "calendar_days_to_terminal": calendar_days_to_terminal,
        "observed_sessions_to_maximum_mfe": mfe_sessions,
        "sessions_to_maximum_mfe_status": mfe_session_status,
        "observed_sessions_to_terminal": evidence_sessions,
        "sessions_to_terminal_status": session_status,
        "gap_below_stop": bool(terminal_payload.get("gap_below_stop")),
        "stop_execution_worse_than_planned": stop_execution_worse,
        "stop_execution_deviation_r": stop_execution_deviation_r,
        "stop_execution_deviation_pct": stop_execution_deviation_pct,
        "stop_execution_shortfall_r": (
            abs(min(stop_execution_deviation_r, 0.0))
            if stop_execution_deviation_r is not None
            else None
        ),
        "stop_execution_shortfall_pct": (
            abs(min(stop_execution_deviation_pct, 0.0))
            if stop_execution_deviation_pct is not None
            else None
        ),
        "stopped": stopped,
        "terminal_event": str(terminal_event.get("event_type") or case.get("status") or ""),
        "terminal_interval": interval or None,
        "setup_type": str(strategy.get("setup_type") or "Unbekannt"),
        "setup_family": _normalized_setup(
            strategy.get("setup_type"), frozen.get("setup_family")
        ),
        "market_phase": str(strategy.get("market_phase") or "Unbekannt"),
        "volatility_regime": str(strategy.get("volatility_regime") or "Unbekannt"),
        "asset_type": str(asset.get("asset_type") or "Unbekannt"),
        "region": str(asset.get("region") or "Unbekannt"),
        "sector": str(asset.get("sector") or "Nicht gespeichert"),
        "rsi_14": frozen.get("rsi_14") or features.get("rsi_14"),
        "ema_20": frozen.get("ema_20") or features.get("ema_20"),
        "ema_50": frozen.get("ema_50") or features.get("ema_50"),
        "ema20_relative_to_ema50": ema20_relative_to_ema50,
        "ema20_relative_to_ema50_state": _relative_state(
            ema20_relative_to_ema50,
            above="EMA20 über EMA50",
            below="EMA20 unter EMA50",
        ),
        "price_relative_to_ema20_state": _relative_state(
            close_relative_to_ema20,
            above="Kurs über EMA20",
            below="Kurs unter EMA20",
        ),
        "price_relative_to_ema50_state": _relative_state(
            close_relative_to_ema50,
            above="Kurs über EMA50",
            below="Kurs unter EMA50",
        ),
        "buyer_confirmation": frozen.get("buyer_confirmation"),
        "bearish_candles": frozen.get("bearish_candles"),
        "fibonacci_inside_0618_0786": frozen.get("fibonacci_inside_0618_0786"),
        "bos_close_break": bos_close_break,
        "bos_close_break_excess_atr": frozen.get("bos_close_break_excess_atr"),
        "market_structure_state": market_structure_state,
        "opening_level_contact": frozen.get("opening_level_contact"),
        "cot_status": frozen.get("cot_status"),
        "frozen_context_status": str(frozen.get("status") or "not_supplied"),
        "frozen_dataset_fingerprint": frozen.get("dataset_fingerprint"),
        "future_bars_used_for_signal_features": int(
            frozen.get("future_bars_used_for_features") or 0
        ),
        "counterfactuals": counterfactuals,
        "post_stop_counterfactuals": post_stop_counterfactuals,
        "diagnostic_only": True,
        "automatic_rule_change": False,
    }
    classification = _classification(row)
    row["stopout_class"] = classification["code"]
    row["stopout_class_label"] = classification["label"]
    row["stopout_class_reason"] = _concrete_class_reason(row, classification)
    # Backward-compatible coarse label used by existing reports/tests.
    row["diagnosis"] = {
        "A": "entry_or_setup_quality_candidate",
        "B": "exit_or_stop_sensitivity_candidate",
        "C": "exit_or_stop_sensitivity_candidate",
        "D": "gap_or_execution_risk",
        "E": "entry_or_setup_quality_candidate",
        "F": "exit_or_stop_sensitivity_candidate",
        "G": "loss_needs_segment_evidence",
    }.get(classification["code"], "insufficient_evidence")
    if result_r is not None and result_r > 0:
        row["diagnosis"] = "positive_outcome"
    elif terminal_event.get("event_type") in {
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
        "expired_unfilled",
    }:
        row["diagnosis"] = "no_fill_or_pre_entry_invalidation"
    return row


def _metrics(rows: Sequence[Mapping[str, object]]) -> dict:
    results = [
        value for row in rows if (value := _number(row.get("result_r"))) is not None
    ]
    wins = [value for value in results if value > 0]
    losses = [value for value in results if value < 0]
    breakeven = [value for value in results if value == 0]
    mfe_values = [
        value for row in rows if (value := _number(row.get("mfe_r"))) is not None
    ]
    cumulative = peak = 0.0
    maximum_drawdown = 0.0
    for value in results:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown = min(maximum_drawdown, cumulative - peak)
    metrics = {
        "cases": len(rows),
        "evaluated": len(results),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "hit_rate_pct": len(wins) / len(results) * 100 if results else None,
        "average_r": sum(results) / len(results) if results else None,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "maximum_drawdown_r": abs(maximum_drawdown),
        "average_mfe_r": _average(row.get("mfe_r") for row in rows),
        "average_mae_r": _average(row.get("mae_r") for row in rows),
        "median_mfe_r": median(mfe_values) if mfe_values else None,
        "gap_stop_count": sum(bool(row.get("gap_below_stop")) for row in rows),
        "gap_or_slippage_count": sum(
            bool(row.get("gap_below_stop"))
            or row.get("stop_execution_worse_than_planned") is True
            for row in rows
        ),
        "positive_movement_before_stop_count": sum(
            bool(row.get("stopped"))
            and (_number(row.get("mfe_r")) or 0.0) > 0
            for row in rows
        ),
        "almost_no_positive_movement_stopout_count": sum(
            bool(row.get("stopped"))
            and (value := _number(row.get("mfe_r"))) is not None
            and value < 0.5
            for row in rows
        ),
        "possible_stop_calibration_count": sum(
            str(row.get("stopout_class") or "") in {"C", "F"} for row in rows
        ),
    }
    for threshold, key in (
        (0.5, "0_5r"),
        (1.0, "1r"),
        (1.5, "1_5r"),
        (2.0, "2r"),
    ):
        count = sum(value >= threshold for value in mfe_values)
        metrics[f"mfe_at_least_{key}_count"] = count
        metrics[f"mfe_at_least_{key}_pct"] = (
            count / len(mfe_values) * 100 if mfe_values else None
        )
    return metrics


def _average(values: object) -> float | None:
    numbers = [
        number for value in values if (number := _number(value)) is not None
    ]
    return sum(numbers) / len(numbers) if numbers else None


def _segments(rows: Sequence[dict], field: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "Unbekannt")].append(row)
    return [
        {
            field: key,
            **_metrics(group),
            "minimum_cases_for_interpretation": MINIMUM_SEGMENT_CASES_FOR_INTERPRETATION,
            "interpretation_ready": len(group)
            >= MINIMUM_SEGMENT_CASES_FOR_INTERPRETATION,
        }
        for key, group in sorted(grouped.items(), key=lambda item: item[0])
    ]


def _maximum_loss_streak(rows: Sequence[dict]) -> int:
    maximum = current = 0
    for row in sorted(rows, key=lambda item: str(item.get("signal_at") or "")):
        result = _number(row.get("result_r"))
        current = current + 1 if result is not None and result <= 0 else 0
        maximum = max(maximum, current)
    return maximum


def analyze_swing_edge_cases(
    cases: Sequence[Mapping[str, object]],
    *,
    contexts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict:
    """Build a reproducible diagnostic report without selecting a new strategy."""
    rows = [
        swing_edge_case_diagnostic(case, context=_context_for_case(case, contexts))
        for case in cases
    ]
    evaluated = [row for row in rows if row.get("result_r") is not None]
    coverage = {
        "mfe_mae_cases": sum(
            row.get("mfe_r") is not None and row.get("mae_r") is not None
            for row in rows
        ),
        "atr_stop_distance_cases": sum(
            row.get("stop_distance_atr") is not None for row in rows
        ),
        "session_duration_cases": sum(
            row.get("observed_sessions_to_terminal") is not None for row in rows
        ),
        "sector_cases": sum(
            row.get("sector") != "Nicht gespeichert" for row in rows
        ),
        "rsi_ema_cases": sum(
            row.get("rsi_14") is not None
            and row.get("ema_20") is not None
            and row.get("ema_50") is not None
            for row in rows
        ),
        "buyer_confirmation_cases": sum(
            row.get("buyer_confirmation") is not None for row in rows
        ),
        "bos_cases": sum(row.get("bos_close_break") is not None for row in rows),
        "later_recovery_cases": sum(
            any(
                str(dict(window or {}).get("status") or "").startswith("available")
                for window in dict(row.get("post_stop_counterfactuals") or {}).values()
            )
            for row in rows
        ),
        "sessions_to_maximum_mfe_cases": sum(
            row.get("observed_sessions_to_maximum_mfe") is not None for row in rows
        ),
        "stop_execution_cases": sum(
            row.get("stop_execution_worse_than_planned") is not None for row in rows
        ),
    }
    classifications = Counter(
        str(row.get("stopout_class") or "G") for row in rows
    )
    meaningful_mfe = sum(
        (_number(row.get("maximum_r_before_stop")) or -math.inf) >= 1.0
        for row in rows
    )
    likely_entry = sum(
        str(row.get("stopout_class")) in {"A", "E"} for row in rows
    )
    likely_stop = sum(
        str(row.get("stopout_class")) in {"C", "F"} for row in rows
    )
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "forensics_version": FORWARD_STOPOUT_FORENSICS_VERSION,
        "created_from_stored_evidence_only": True,
        "overall": _metrics(evaluated),
        "maximum_loss_streak": _maximum_loss_streak(evaluated),
        "diagnosis_counts": dict(
            sorted(Counter(row["diagnosis"] for row in rows).items())
        ),
        "stopout_class_counts": dict(sorted(classifications.items())),
        "likely_entry_or_setup_issue_count": likely_entry,
        "likely_stop_calibration_issue_count": likely_stop,
        "meaningful_mfe_at_least_1r_count": meaningful_mfe,
        "coverage": coverage,
        "required_case_fields": list(FORWARD_STATUS_REQUIRED_CASE_FIELDS),
        "required_case_field_coverage": {
            field: sum(row.get(field) is not None for row in rows)
            for field in FORWARD_STATUS_REQUIRED_CASE_FIELDS
        },
        "coverage_limitations": [
            "MFE auf der terminalen Kerze beweist ohne Tickfolge nicht die Intrabar-Reihenfolge.",
            "Der Preis unmittelbar vor dem Exit und ein per Signal gespeicherter Korrelationscluster fehlen in bestehenden Fällen.",
            "Rekonstruierte RSI-/EMA-/ATR-/Strukturwerte stammen ausschließlich aus eingefrorenen Bars bis einschließlich Signaltag.",
            "Kontrafakten sind getrennte Diagnosewerte und niemals echte Forward-Ergebnisse.",
            "Diagnoseklassen sind Hinweise; sie ändern weder Baseline noch Stops, Ziele oder Freigaben.",
        ],
        "segments": {
            field: _segments(evaluated, field)
            for field in (
                "setup_type",
                "setup_family",
                "market_phase",
                "volatility_regime",
                "asset_type",
                "region",
                "sector",
                "issuer_cluster",
                "stopout_class",
            )
        },
        "cases": rows,
        "diagnostic_only": True,
        "automatic_rule_change": False,
        "production_activation_allowed": False,
        "segment_interpretation_minimum_cases": MINIMUM_SEGMENT_CASES_FOR_INTERPRETATION,
    }


def analyze_real_forward_trades(
    cases: Sequence[Mapping[str, object]],
    *,
    contexts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Analyze every closed filled real-forward paper trade, including winners."""
    closed = []
    for case in cases:
        snapshot = dict(case.get("snapshot") or {})
        terminal = _terminal_event(case)
        result = _number(dict(terminal.get("payload") or {}).get("result_r"))
        if (
            str(snapshot.get("source_kind") or "") == "real_forward_scan"
            and bool(_entry_event(case))
            and result is not None
        ):
            closed.append(case)
    report = analyze_swing_edge_cases(closed, contexts=contexts)
    report["scope"] = "all_closed_real_forward_paper_trades"
    report["source_cases_received"] = len(cases)
    report["closed_forward_trades_analyzed"] = len(closed)
    report["historical_cases_included"] = 0
    return report


def analyze_real_forward_stopouts(
    cases: Sequence[Mapping[str, object]],
    *,
    contexts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Analyze only closed losing real-forward stopouts; never historical cases."""
    stopouts = []
    for case in cases:
        snapshot = dict(case.get("snapshot") or {})
        terminal = _terminal_event(case)
        result = _number(dict(terminal.get("payload") or {}).get("result_r"))
        if (
            str(snapshot.get("source_kind") or "") == "real_forward_scan"
            and terminal.get("event_type") in {"stop_reached", "ambiguous_sequence"}
            and result is not None
            and result < 0
        ):
            stopouts.append(case)
    report = analyze_swing_edge_cases(stopouts, contexts=contexts)
    report["scope"] = "closed_losing_real_forward_stopouts_only"
    report["source_cases_received"] = len(cases)
    report["stopouts_analyzed"] = len(stopouts)
    report["historical_cases_included"] = 0
    return report


def _markdown_value(value: object, *, digits: int = 2) -> str:
    if value is None:
        return "n/v"
    if isinstance(value, bool):
        return "ja" if value else "nein"
    number = _number(value)
    if number is not None and not isinstance(value, str):
        return f"{number:.{digits}f}".replace(".", ",")
    return str(value).replace("|", "/").replace("\n", " ")


def _variant_markdown(window: Mapping[str, object], name: str) -> str:
    variant = dict(dict(window.get("stop_variants") or {}).get(name) or {})
    if not variant:
        return "n/v"
    held = _markdown_value(variant.get("stop_held_through_horizon"))
    result = _markdown_value(variant.get("counterfactual_result_r"))
    status = str(variant.get("counterfactual_result_status") or "n/v")
    return f"hielt {held}; {result}R ({status})"


def render_forward_status_markdown(report: Mapping[str, object]) -> str:
    """Render a compact, copyable PROJECT_STATUS section from a read-only report."""
    rows = [dict(row or {}) for row in report.get("cases") or []]
    overall = dict(report.get("overall") or {})
    classes = dict(report.get("stopout_class_counts") or {})
    threshold_text = ", ".join(
        f"{label}: {_markdown_value(overall.get(f'mfe_at_least_{key}_count'), digits=0)}/"
        f"{_markdown_value(overall.get(f'mfe_at_least_{key}_pct'))}%"
        for label, key in (("0,5R", "0_5r"), ("1R", "1r"), ("1,5R", "1_5r"), ("2R", "2r"))
    )
    lines = [
        "#### Konkreter echter Swing-Forward-Status",
        "",
        "> Rein lesend aus append-only Forward-Ereignissen und dem unveränderten Frozen-Datensatz abgeleitet. `n/v` bedeutet nicht verfügbar. Spätere Kursfenster und alternative Stops sind ausschließlich Counterfactuals/Diagnose, keine echten Forward-Ergebnisse; eine Intrabar-Reihenfolge wird nicht erfunden.",
        "",
        "| Kennzahl | Wert |",
        "|---|---:|",
        f"| Abgeschlossene Trades | {_markdown_value(overall.get('evaluated'), digits=0)} |",
        f"| Gewinne / Verluste / Null | {_markdown_value(overall.get('wins'), digits=0)} / {_markdown_value(overall.get('losses'), digits=0)} / {_markdown_value(overall.get('breakeven'), digits=0)} |",
        f"| Ø R / Profit Factor / Max Drawdown | {_markdown_value(overall.get('average_r'))}R / {_markdown_value(overall.get('profit_factor'))} / {_markdown_value(overall.get('maximum_drawdown_r'))}R |",
        f"| Ø MFE / Median MFE / Ø MAE | {_markdown_value(overall.get('average_mfe_r'))}R / {_markdown_value(overall.get('median_mfe_r'))}R / {_markdown_value(overall.get('average_mae_r'))}R |",
        f"| MFE-Schwellen Anzahl/Anteil | {threshold_text} |",
        f"| Vor Stop zeitweise im Gewinn / fast ohne Bewegung ausgestoppt | {_markdown_value(overall.get('positive_movement_before_stop_count'), digits=0)} / {_markdown_value(overall.get('almost_no_positive_movement_stopout_count'), digits=0)} |",
        f"| Gap-/Slippage-Fälle / mögliche Stop-Kalibrierung | {_markdown_value(overall.get('gap_or_slippage_count'), digits=0)} / {_markdown_value(overall.get('possible_stop_calibration_count'), digits=0)} |",
        f"| Ursachen A–G | {_markdown_value(', '.join(f'{key}={value}' for key, value in sorted(classes.items())))} |",
        "",
        "##### Deskriptive Gruppen",
        "",
        "| Dimension | Gruppe | Fälle | Gewinne/Verluste | Ø R | PF | Ø MFE / MAE | interpretierbar |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    segments = dict(report.get("segments") or {})
    for field, label in (
        ("setup_family", "Setup"),
        ("market_phase", "Marktphase"),
        ("volatility_regime", "Volatilität"),
    ):
        for segment in segments.get(field) or []:
            item = dict(segment or {})
            lines.append(
                "| "
                + " | ".join(
                    (
                        label,
                        _markdown_value(item.get(field)),
                        _markdown_value(item.get("evaluated"), digits=0),
                        f"{_markdown_value(item.get('wins'), digits=0)}/{_markdown_value(item.get('losses'), digits=0)}",
                        _markdown_value(item.get("average_r")),
                        _markdown_value(item.get("profit_factor")),
                        f"{_markdown_value(item.get('average_mfe_r'))}/{_markdown_value(item.get('average_mae_r'))}",
                        _markdown_value(item.get("interpretation_ready")),
                    )
                )
                + " |"
            )
    lines.extend(
        [
        "",
        "##### Trade-Kerndaten",
        "",
        "| Ticker | Setup | Entry | Stop | Stop % / ATR | Ergebnis R | MFE R / % | MAE R / % | Max. Gewinn R | >=0,5/1/1,5/2R | Sitzungen MFE / Exit | Gap | schlechter als Stop; Abw. R/% | Klasse |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|",
        ]
    )
    for row in rows:
        thresholds = "/".join(
            _markdown_value(row.get(field))
            for field in (
                "mfe_at_least_0_5r",
                "mfe_at_least_1r",
                "mfe_at_least_1_5r",
                "mfe_at_least_2r",
            )
        )
        execution = (
            f"{_markdown_value(row.get('stop_execution_worse_than_planned'))}; "
            f"{_markdown_value(row.get('stop_execution_deviation_r'))}R/"
            f"{_markdown_value(row.get('stop_execution_deviation_pct'))}%"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_value(row.get("symbol")),
                    _markdown_value(row.get("setup_family")),
                    _markdown_value(row.get("entry_original")),
                    _markdown_value(row.get("initial_stop_original")),
                    f"{_markdown_value(row.get('initial_stop_distance_pct'))}% / {_markdown_value(row.get('stop_distance_atr'))}",
                    _markdown_value(row.get("result_r")),
                    f"{_markdown_value(row.get('mfe_r'))} / {_markdown_value(row.get('mfe_pct'))}%",
                    f"{_markdown_value(row.get('mae_r'))} / {_markdown_value(row.get('mae_pct'))}%",
                    _markdown_value(row.get("maximum_intermediate_profit_r")),
                    thresholds,
                    f"{_markdown_value(row.get('observed_sessions_to_maximum_mfe'), digits=0)} / {_markdown_value(row.get('observed_sessions_to_terminal'), digits=0)}",
                    _markdown_value(row.get("gap_below_stop")),
                    execution,
                    _markdown_value(row.get("stopout_class")),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "##### Signalkontext und maschinell erzeugte sachliche Ursache",
            "",
            "| Ticker | RSI14 | EMA20/EMA50 | Kurs/EMA20 | Kurs/EMA50 | Käufer | BOS/Struktur | Marktphase | Volatilität | Klasse und Begründung |",
            "|---|---:|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_value(row.get("symbol")),
                    _markdown_value(row.get("rsi_14")),
                    _markdown_value(row.get("ema20_relative_to_ema50_state")),
                    _markdown_value(row.get("price_relative_to_ema20_state")),
                    _markdown_value(row.get("price_relative_to_ema50_state")),
                    _markdown_value(row.get("buyer_confirmation")),
                    _markdown_value(row.get("market_structure_state")),
                    _markdown_value(row.get("market_phase")),
                    _markdown_value(row.get("volatility_regime")),
                    f"{_markdown_value(row.get('stopout_class'))}: {_markdown_value(row.get('stopout_class_reason'))}",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "##### Spätere 5-/20-Sitzungs-Diagnose (nur Counterfactual)",
            "",
            "| Ticker | 5S Erholung % / R | 5S Ziel 1/2 | 5S Pullback / +ATR / ATR-Stop | 20S Erholung % / R | 20S Ziel 1/2 | 20S Pullback / +ATR / ATR-Stop |",
            "|---|---:|---|---|---:|---|---|",
        ]
    )
    for row in rows:
        windows = dict(row.get("post_stop_counterfactuals") or {})
        five = dict(windows.get("5") or {})
        twenty = dict(windows.get("20") or {})
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_value(row.get("symbol")),
                    f"{_markdown_value(five.get('maximum_recovery_after_stop_pct'))}% / {_markdown_value(five.get('maximum_recovery_from_original_entry_r'))}R",
                    f"{_markdown_value(five.get('target_1_reached_after_stop'))}/{_markdown_value(five.get('target_2_reached_after_stop'))}",
                    " / ".join(_variant_markdown(five, name) for name in ("pullback_low", "pullback_low_atr_buffer", "atr_2_stop")),
                    f"{_markdown_value(twenty.get('maximum_recovery_after_stop_pct'))}% / {_markdown_value(twenty.get('maximum_recovery_from_original_entry_r'))}R",
                    f"{_markdown_value(twenty.get('target_1_reached_after_stop'))}/{_markdown_value(twenty.get('target_2_reached_after_stop'))}",
                    " / ".join(_variant_markdown(twenty, name) for name in ("pullback_low", "pullback_low_atr_buffer", "atr_2_stop")),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"Segmentwerte werden erst ab {MINIMUM_SEGMENT_CASES_FOR_INTERPRETATION} Fällen je Gruppe als interpretierbar markiert. Bis dahin bleiben Pullback/Breakout-, Marktphasen- und Volatilitätsgruppen rein deskriptiv.",
        ]
    )
    return "\n".join(lines)


def connect_development_patterns_to_forward_losses(
    development_report: Mapping[str, object],
    forward_report: Mapping[str, object],
) -> dict[str, object]:
    """Count pattern overlap in forward losses without treating it as proof."""
    cases = [dict(row or {}) for row in forward_report.get("cases") or []]
    predicates = {
        "buyer_confirmation": lambda row: row.get("buyer_confirmation") is True,
        "three_or_more_bearish_candles": lambda row: (_number(row.get("bearish_candles")) or 0) >= 3,
        "fibonacci_0618_0786": lambda row: row.get("fibonacci_inside_0618_0786") is True,
        "ema20_above_ema50": lambda row: (_number(row.get("ema20_relative_to_ema50")) or -math.inf) > 1,
        "rsi_40_70": lambda row: (
            (value := _number(row.get("rsi_14"))) is not None and 40 <= value <= 70
        ),
        "bos_close_break": lambda row: row.get("bos_close_break") is True,
        "opening_level_contact": lambda row: row.get("opening_level_contact") is True,
        "cot_available": lambda row: row.get("cot_status") == "available",
    }
    availability = {
        "buyer_confirmation": lambda row: row.get("buyer_confirmation") is not None,
        "three_or_more_bearish_candles": lambda row: row.get("bearish_candles") is not None,
        "fibonacci_0618_0786": lambda row: row.get("fibonacci_inside_0618_0786") is not None,
        "ema20_above_ema50": lambda row: row.get("ema20_relative_to_ema50") is not None,
        "rsi_40_70": lambda row: row.get("rsi_14") is not None,
        "bos_close_break": lambda row: row.get("bos_close_break") is not None,
        "opening_level_contact": lambda row: row.get("opening_level_contact") is not None,
        "cot_available": lambda row: row.get("cot_status") is not None,
    }
    report_hypotheses = {
        str(row.get("hypothesis_id") or ""): dict(row or {})
        for row in development_report.get("hypotheses") or []
    }
    rows = []
    for hypothesis_id, predicate in predicates.items():
        covered = [row for row in cases if availability[hypothesis_id](row)]
        matched = [row for row in covered if predicate(row)]
        alternative_held = 0
        for row in matched:
            variants = dict(dict(row.get("counterfactuals") or {}).get("variants") or {})
            if any(
                name != "existing_stop"
                and dict(value.get("stop_observation") or {}).get("touched") is False
                for name, value in variants.items()
                if isinstance(value, Mapping)
            ):
                alternative_held += 1
        development = report_hypotheses.get(hypothesis_id, {})
        rows.append(
            {
                "hypothesis_id": hypothesis_id,
                "development_classification": development.get("classification"),
                "forward_stopouts_total": len(cases),
                "forward_feature_coverage": len(covered),
                "forward_losses_with_pattern": len(matched),
                "forward_losses_with_pattern_and_alternative_stop_held": alternative_held,
                "forward_stop_classes": dict(
                    sorted(Counter(str(row.get("stopout_class") or "G") for row in matched).items())
                ),
                "used_to_change_strategy": False,
            }
        )
    return {
        "link_version": "swing-development-forward-diagnostic-link-2026.08.22-v1",
        "development_pattern_version": development_report.get("pattern_version"),
        "forward_forensics_version": forward_report.get("forensics_version"),
        "rows": rows,
        "diagnostic_association_only": True,
        "causal_proof": False,
        "automatic_rule_change": False,
        "production_activation_allowed": False,
    }
