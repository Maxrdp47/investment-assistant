from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd

from trading_assistant import assess_swing_order_plan


SWING_EVALUATION_VERSION = "swing-forward-evaluation-2026.08.09-v1"
SWING_ACTIVE_MEASUREMENT_VERSION = "swing-active-measurement-2026.08.16-v1"


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _data_quality(interval: str) -> str:
    normalized = str(interval).lower()
    if normalized in {"1m", "2m", "5m", "15m"}:
        return "hoch"
    if normalized in {"30m", "60m", "90m", "1h"}:
        return "mittel"
    if normalized in {"1d", "1day"}:
        return "eingeschränkt"
    return "nicht auswertbar"


def _cost_bps(order_plan: dict) -> float:
    contract = dict(order_plan.get("execution_cost_contract") or {})
    values = [
        _number(contract.get("spread_bps_one_way")),
        _number(contract.get("slippage_bps_one_way")),
        _number(contract.get("fee_bps_one_way")),
    ]
    if any(value is None or value < 0 for value in values):
        raise ValueError("Der Swing-Orderplan besitzt keinen vollständigen Kostenvertrag.")
    return float(sum(values))


def _entry_with_costs(raw_price: float, cost_bps: float) -> float:
    return raw_price * (1 + cost_bps / 10_000)


def _exit_with_costs(raw_price: float, cost_bps: float) -> float:
    return raw_price * (1 - cost_bps / 10_000)


def _event(
    event_type: str,
    bar_time: pd.Timestamp,
    interval: str,
    payload: dict,
) -> dict:
    source_suffix = (
        f":{SWING_ACTIVE_MEASUREMENT_VERSION}" if event_type == "still_active" else ""
    )
    return {
        "event_type": event_type,
        "occurred_at": bar_time.isoformat(),
        "source_key": f"{interval}:{bar_time.isoformat()}:{event_type}{source_suffix}",
        "payload": {
            "evaluation_version": SWING_EVALUATION_VERSION,
            "interval": interval,
            "data_quality": _data_quality(interval),
            **payload,
        },
    }


def _result_payload(
    *,
    raw_exit: float,
    entry_with_costs: float,
    initial_stop: float,
    cost_bps: float,
    fx_rate: float,
    exit_fraction: float = 1.0,
    occurred_at: pd.Timestamp | None = None,
    prior_exit_legs: list[dict] | None = None,
    maximum_price_after_entry: float | None = None,
    minimum_price_after_entry: float | None = None,
) -> dict:
    exit_with_costs = _exit_with_costs(raw_exit, cost_bps)
    current_leg = {
        "paper_exit_original": raw_exit,
        "paper_exit_after_costs_original": exit_with_costs,
        "exit_fraction": exit_fraction,
        "occurred_at": occurred_at.isoformat() if occurred_at is not None else None,
    }
    exit_legs = [*(prior_exit_legs or []), current_leg]
    total_fraction = sum(float(leg["exit_fraction"]) for leg in exit_legs)
    if not math.isclose(total_fraction, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Die Swing-Ausstiegsanteile ergeben nicht genau 100 Prozent.")
    weighted_exit_with_costs = sum(
        float(leg["paper_exit_after_costs_original"]) * float(leg["exit_fraction"])
        for leg in exit_legs
    )
    risk = entry_with_costs - initial_stop
    result_original = weighted_exit_with_costs - entry_with_costs
    maximum_favorable_excursion_pct = (
        (maximum_price_after_entry - entry_with_costs) / entry_with_costs * 100
        if maximum_price_after_entry is not None and entry_with_costs > 0
        else None
    )
    maximum_adverse_excursion_pct = (
        (minimum_price_after_entry - entry_with_costs) / entry_with_costs * 100
        if minimum_price_after_entry is not None and entry_with_costs > 0
        else None
    )
    return {
        "paper_exit_original": raw_exit,
        "paper_exit_after_costs_original": weighted_exit_with_costs,
        "last_exit_after_costs_original": exit_with_costs,
        "exit_legs": exit_legs,
        "result_original_per_unit": result_original,
        "result_eur_per_unit_at_signal_fx": result_original * fx_rate,
        "result_pct": result_original / entry_with_costs * 100,
        "result_r": result_original / risk if risk > 0 else None,
        "maximum_favorable_excursion_pct": maximum_favorable_excursion_pct,
        "maximum_adverse_excursion_pct": maximum_adverse_excursion_pct,
        "excursion_source": "Vollständige Kursbalken ab der Paper-Einstiegskerze; bei groben Intervallen konservativ eingeschränkt.",
        "fx_policy": "Vorläufige Vergleichsgröße mit unveränderbarem Signal-FX; eine genaue historische EUR-Bewertung wird append-only als eigenes Ereignis ergänzt.",
    }


def evaluate_swing_signal_bars(
    signal_snapshot: dict,
    bars: pd.DataFrame,
    *,
    interval: str,
    evaluated_at: object,
) -> list[dict]:
    """Evaluate only complete post-signal bars and return append-only event candidates."""
    if bars.empty or not {"Open", "High", "Low", "Close"}.issubset(bars.columns):
        return []
    order_plan = dict(signal_snapshot.get("order_plan") or {})
    cost_bps = _cost_bps(order_plan)
    initial_stop = _number(order_plan.get("initial_stop_original"))
    target_1 = _number(order_plan.get("target_1_original"))
    target_2 = _number(order_plan.get("target_2_original"))
    target_1_fraction = _number(order_plan.get("target_1_exit_fraction"))
    target_2_fraction = _number(order_plan.get("target_2_exit_fraction"))
    fx_rate = _number((order_plan.get("fx_snapshot") or {}).get("rate_to_eur"))
    if initial_stop is None or target_1 is None or fx_rate is None or fx_rate <= 0:
        raise ValueError("Stop, Ziel oder Signal-FX fehlen für die Swing-Auswertung.")
    if target_2 is None:
        target_1_fraction, target_2_fraction = 1.0, 0.0
    else:
        target_1_fraction = 0.5 if target_1_fraction is None else target_1_fraction
        target_2_fraction = 0.5 if target_2_fraction is None else target_2_fraction
        if target_1_fraction <= 0 or target_2_fraction <= 0 or not math.isclose(
            target_1_fraction + target_2_fraction, 1.0, rel_tol=0.0, abs_tol=1e-9
        ):
            raise ValueError("Ziel-1- und Ziel-2-Ausstiegsanteil müssen zusammen 100 Prozent ergeben.")
    try:
        signal_at = pd.Timestamp(signal_snapshot["signal_at"])
        evaluation_time = pd.Timestamp(evaluated_at)
    except Exception as exc:
        raise ValueError("Signal- oder Auswertungszeitpunkt ist ungültig.") from exc
    if evaluation_time.tzinfo is not None:
        evaluation_day = evaluation_time.tz_convert(None).date()
    else:
        evaluation_day = evaluation_time.date()

    frame = bars.copy().sort_index()
    normalized_index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame.loc[~normalized_index.isna()].copy()
    frame.index = normalized_index[~normalized_index.isna()]

    events: list[dict] = []
    entered = False
    entry_with_costs: float | None = None
    target_1_seen = False
    realized_exit_legs: list[dict] = []
    terminal = False
    last_complete_time: pd.Timestamp | None = None
    maximum_price_after_entry: float | None = None
    minimum_price_after_entry: float | None = None
    last_complete_close: float | None = None

    for bar_time, row in frame.iterrows():
        timestamp = pd.Timestamp(bar_time)
        entered_this_bar = False
        comparable_timestamp = timestamp
        comparable_signal = signal_at
        if comparable_timestamp.tzinfo is None and comparable_signal.tzinfo is not None:
            comparable_signal = comparable_signal.tz_localize(None)
        elif comparable_timestamp.tzinfo is not None and comparable_signal.tzinfo is None:
            comparable_timestamp = comparable_timestamp.tz_localize(None)
        elif comparable_timestamp.tzinfo is not None and comparable_signal.tzinfo is not None:
            comparable_timestamp = comparable_timestamp.tz_convert("UTC")
            comparable_signal = comparable_signal.tz_convert("UTC")
        if comparable_timestamp <= comparable_signal:
            continue
        if interval.lower() in {"1d", "1day"} and timestamp.date() >= evaluation_day:
            continue
        comparable_evaluation = evaluation_time
        if comparable_timestamp.tzinfo is None and comparable_evaluation.tzinfo is not None:
            comparable_evaluation = comparable_evaluation.tz_localize(None)
        elif comparable_timestamp.tzinfo is not None and comparable_evaluation.tzinfo is None:
            comparable_timestamp = comparable_timestamp.tz_localize(None)
        elif comparable_timestamp.tzinfo is not None and comparable_evaluation.tzinfo is not None:
            comparable_timestamp = comparable_timestamp.tz_convert("UTC")
            comparable_evaluation = comparable_evaluation.tz_convert("UTC")
        if comparable_timestamp >= comparable_evaluation:
            continue
        last_complete_time = timestamp
        observed_day = timestamp.date()
        open_price = _number(row.get("Open"))
        high = _number(row.get("High"))
        low = _number(row.get("Low"))
        close = _number(row.get("Close"))
        if None in {open_price, high, low, close}:
            continue
        last_complete_close = close
        bar = {"Open": open_price, "High": high, "Low": low, "Close": close}

        if not entered:
            assessment = assess_swing_order_plan(order_plan, bar, observed_day)
            status = assessment["status"]
            if status == "pending":
                continue
            if status == "would_fill":
                raw_entry = float(assessment["paper_entry_original"])
                entry_with_costs = _entry_with_costs(raw_entry, cost_bps)
                events.append(
                    _event(
                        "paper_entry_opened",
                        timestamp,
                        interval,
                        {
                            "paper_entry_original": raw_entry,
                            "paper_entry_after_costs_original": entry_with_costs,
                            "cost_bps_one_way": cost_bps,
                            "broker_order_sent": False,
                        },
                    )
                )
                entered = True
                entered_this_bar = True
                # The entry bar can also reach stop/target. Continue conservatively below.
            elif status == "missed":
                events.append(_event("entry_missed", timestamp, interval, {"reason": assessment["reason"]}))
                terminal = True
                break
            elif status == "cancelled":
                events.append(
                    _event("invalidated_before_entry", timestamp, interval, {"reason": assessment["reason"]})
                )
                terminal = True
                break
            elif status == "expired":
                events.append(
                    _event("expired_without_entry", timestamp, interval, {"reason": assessment["reason"]})
                )
                terminal = True
                break
            else:
                events.append(_event("not_evaluable", timestamp, interval, {"reason": assessment["reason"]}))
                terminal = True
                break

        if entered and entry_with_costs is not None:
            if open_price <= initial_stop:
                gap_maximum = max(
                    open_price,
                    maximum_price_after_entry
                    if maximum_price_after_entry is not None
                    else entry_with_costs,
                )
                gap_minimum = min(
                    open_price,
                    minimum_price_after_entry
                    if minimum_price_after_entry is not None
                    else entry_with_costs,
                )
                events.append(
                    _event(
                        "stop_reached",
                        timestamp,
                        interval,
                        {
                            "reason": "Kurslücke am oder unter dem initialen Stop; Ausstieg zum ersten beobachteten Kurs.",
                            "gap_below_stop": True,
                            **_result_payload(
                                raw_exit=open_price,
                                entry_with_costs=entry_with_costs,
                                initial_stop=initial_stop,
                                cost_bps=cost_bps,
                                fx_rate=fx_rate,
                                exit_fraction=target_2_fraction if target_1_seen else 1.0,
                                occurred_at=timestamp,
                                prior_exit_legs=realized_exit_legs,
                                maximum_price_after_entry=gap_maximum,
                                minimum_price_after_entry=gap_minimum,
                            ),
                        },
                    )
                )
                terminal = True
                break
            maximum_price_after_entry = max(
                high,
                maximum_price_after_entry if maximum_price_after_entry is not None else entry_with_costs,
            )
            minimum_price_after_entry = min(
                low,
                minimum_price_after_entry if minimum_price_after_entry is not None else entry_with_costs,
            )
            next_target = target_2 if target_1_seen and target_2 is not None else target_1
            stop_touched = low <= initial_stop
            target_touched = high >= next_target
            if entered_this_bar and target_touched:
                events.append(
                    _event(
                        "ambiguous_sequence",
                        timestamp,
                        interval,
                        {
                            "reason": "Einstieg und Ziel liegen in derselben Kerze; ihre Reihenfolge ist nicht beweisbar.",
                            "conservative_assumption": "Kein Zieltreffer behauptet",
                        },
                    )
                )
                terminal = True
                break
            if stop_touched and target_touched:
                events.append(
                    _event(
                        "ambiguous_sequence",
                        timestamp,
                        interval,
                        {
                            "reason": "Stop und nächstes Ziel liegen in derselben Kerze; die Reihenfolge ist nicht beweisbar.",
                            "conservative_assumption": "Stop zuerst",
                            **_result_payload(
                                raw_exit=initial_stop,
                                entry_with_costs=entry_with_costs,
                                initial_stop=initial_stop,
                                cost_bps=cost_bps,
                                fx_rate=fx_rate,
                                exit_fraction=target_2_fraction if target_1_seen else 1.0,
                                occurred_at=timestamp,
                                prior_exit_legs=realized_exit_legs,
                                maximum_price_after_entry=maximum_price_after_entry,
                                minimum_price_after_entry=minimum_price_after_entry,
                            ),
                        },
                    )
                )
                terminal = True
                break
            if stop_touched:
                events.append(
                    _event(
                        "stop_reached",
                        timestamp,
                        interval,
                        _result_payload(
                            raw_exit=initial_stop,
                            entry_with_costs=entry_with_costs,
                            initial_stop=initial_stop,
                            cost_bps=cost_bps,
                            fx_rate=fx_rate,
                            exit_fraction=target_2_fraction if target_1_seen else 1.0,
                            occurred_at=timestamp,
                            prior_exit_legs=realized_exit_legs,
                            maximum_price_after_entry=maximum_price_after_entry,
                            minimum_price_after_entry=minimum_price_after_entry,
                        ),
                    )
                )
                terminal = True
                break
            if target_touched:
                if not target_1_seen and target_2 is not None:
                    partial_exit_after_costs = _exit_with_costs(next_target, cost_bps)
                    partial_leg = {
                        "paper_exit_original": next_target,
                        "paper_exit_after_costs_original": partial_exit_after_costs,
                        "exit_fraction": target_1_fraction,
                        "occurred_at": timestamp.isoformat(),
                    }
                    partial_result = (partial_exit_after_costs - entry_with_costs) * target_1_fraction
                    events.append(
                        _event(
                            "target_1_reached",
                            timestamp,
                            interval,
                            {
                                "terminal": False,
                                "exit_fraction": target_1_fraction,
                                "paper_exit_original": next_target,
                                "paper_exit_after_costs_original": partial_exit_after_costs,
                                "realized_result_original_per_initial_unit": partial_result,
                                "realized_result_r": partial_result / (entry_with_costs - initial_stop),
                            },
                        )
                    )
                    realized_exit_legs.append(partial_leg)
                    target_1_seen = True
                    if high >= target_2:
                        events.append(
                            _event(
                                "target_2_reached",
                                timestamp,
                                interval,
                                {
                                    "terminal": True,
                                    **_result_payload(
                                        raw_exit=target_2,
                                        entry_with_costs=entry_with_costs,
                                        initial_stop=initial_stop,
                                        cost_bps=cost_bps,
                                        fx_rate=fx_rate,
                                        exit_fraction=target_2_fraction,
                                        occurred_at=timestamp,
                                        prior_exit_legs=realized_exit_legs,
                                        maximum_price_after_entry=maximum_price_after_entry,
                                        minimum_price_after_entry=minimum_price_after_entry,
                                    ),
                                },
                            )
                        )
                        terminal = True
                        break
                    continue
                events.append(
                    _event(
                        "target_2_reached" if target_1_seen and target_2 is not None else "target_1_reached",
                        timestamp,
                        interval,
                        {
                            "terminal": target_2 is None or target_1_seen,
                            **_result_payload(
                                raw_exit=next_target,
                                entry_with_costs=entry_with_costs,
                                initial_stop=initial_stop,
                                cost_bps=cost_bps,
                                fx_rate=fx_rate,
                                exit_fraction=target_2_fraction if target_1_seen else 1.0,
                                occurred_at=timestamp,
                                prior_exit_legs=realized_exit_legs,
                                maximum_price_after_entry=maximum_price_after_entry,
                                minimum_price_after_entry=minimum_price_after_entry,
                            ),
                        },
                    )
                )
                if target_2 is None or target_1_seen:
                    terminal = True
                    break
                target_1_seen = True

    if not terminal and last_complete_time is not None:
        if entered:
            current_exit_after_costs = (
                _exit_with_costs(last_complete_close, cost_bps)
                if last_complete_close is not None
                else None
            )
            unrealized_result_original = (
                current_exit_after_costs - entry_with_costs
                if current_exit_after_costs is not None and entry_with_costs is not None
                else None
            )
            initial_risk = (
                entry_with_costs - initial_stop
                if entry_with_costs is not None
                else None
            )
            next_target = target_2 if target_1_seen and target_2 is not None else target_1
            events.append(
                _event(
                    "still_active",
                    last_complete_time,
                    interval,
                    {
                        "active_measurement_version": SWING_ACTIVE_MEASUREMENT_VERSION,
                        "target_1_reached": target_1_seen,
                        "broker_order_sent": False,
                        "current_close_original": last_complete_close,
                        "current_exit_after_costs_original": current_exit_after_costs,
                        "unrealized_result_original_per_unit": unrealized_result_original,
                        "unrealized_result_pct": (
                            unrealized_result_original / entry_with_costs * 100
                            if unrealized_result_original is not None
                            and entry_with_costs is not None
                            and entry_with_costs > 0
                            else None
                        ),
                        "unrealized_result_r": (
                            unrealized_result_original / initial_risk
                            if unrealized_result_original is not None
                            and initial_risk is not None
                            and initial_risk > 0
                            else None
                        ),
                        "maximum_favorable_excursion_pct": (
                            (maximum_price_after_entry - entry_with_costs) / entry_with_costs * 100
                            if maximum_price_after_entry is not None
                            and entry_with_costs is not None
                            and entry_with_costs > 0
                            else None
                        ),
                        "maximum_adverse_excursion_pct": (
                            (minimum_price_after_entry - entry_with_costs) / entry_with_costs * 100
                            if minimum_price_after_entry is not None
                            and entry_with_costs is not None
                            and entry_with_costs > 0
                            else None
                        ),
                        "distance_to_stop_pct": (
                            (last_complete_close - initial_stop) / last_complete_close * 100
                            if last_complete_close is not None and last_complete_close > 0
                            else None
                        ),
                        "distance_to_next_target_pct": (
                            (next_target - last_complete_close) / last_complete_close * 100
                            if next_target is not None
                            and last_complete_close is not None
                            and last_complete_close > 0
                            else None
                        ),
                    },
                )
            )
        else:
            try:
                valid_until = date.fromisoformat(str(order_plan["valid_until"]))
            except Exception:
                valid_until = None
            if valid_until is not None and last_complete_time.date() > valid_until:
                events.append(
                    _event(
                        "expired_without_entry",
                        last_complete_time,
                        interval,
                        {"reason": "Orderplan ist ohne Einstieg abgelaufen."},
                    )
                )
    return events
