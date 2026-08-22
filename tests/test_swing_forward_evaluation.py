from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from swing_forward_evaluation import evaluate_swing_signal_bars
from trading_assistant import swing_order_plan_fingerprint


def signal_snapshot() -> dict:
    plan = {
        "plan_version": "test-v1",
        "entry_method": "Schlusskursbestätigung",
        "earliest_entry_day": "2026-08-10",
        "valid_until": "2026-08-14",
        "limit_price_original": 100.0,
        "maximum_entry_original": 102.0,
        "invalidation_original": 95.0,
        "initial_stop_original": 95.0,
        "target_1_original": 111.0,
        "target_2_original": 118.0,
        "fx_snapshot": {"rate_to_eur": 0.9},
        "execution_cost_contract": {
            "version": "test-cost-v1",
            "spread_bps_one_way": 3.0,
            "slippage_bps_one_way": 5.0,
            "fee_bps_one_way": 1.0,
        },
        "automatic_order_execution": False,
        "position_calculated": True,
    }
    plan["plan_fingerprint"] = swing_order_plan_fingerprint(plan)
    return {
        "signal_at": "2026-08-09T22:45:00+02:00",
        "order_plan": plan,
    }


def bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Open": open_price, "High": high, "Low": low, "Close": close}
            for _, open_price, high, low, close in rows
        ],
        index=pd.to_datetime([timestamp for timestamp, *_ in rows], utc=True),
    )


def test_gap_above_maximum_is_a_missed_entry_not_a_trade() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars([("2026-08-10T13:30:00Z", 103.0, 105.0, 100.0, 104.0)]),
        interval="5m",
        evaluated_at=datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc),
    )

    assert [event["event_type"] for event in events] == ["entry_missed"]


def test_entry_target_one_target_two_and_cost_adjusted_result_are_chronological() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars(
            [
                ("2026-08-10T13:30:00Z", 101.0, 101.5, 99.5, 100.5),
                ("2026-08-10T13:35:00Z", 101.0, 112.0, 99.0, 111.5),
                ("2026-08-11T13:30:00Z", 112.0, 119.0, 108.0, 118.5),
            ]
        ),
        interval="5m",
        evaluated_at=datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc),
    )

    assert [event["event_type"] for event in events] == [
        "paper_entry_opened",
        "target_1_reached",
        "target_2_reached",
    ]
    entry = events[0]["payload"]["paper_entry_after_costs_original"]
    assert entry > 100.0
    assert [leg["exit_fraction"] for leg in events[-1]["payload"]["exit_legs"]] == [0.5, 0.5]
    assert events[-1]["payload"]["paper_exit_after_costs_original"] < 118.0
    assert events[-1]["payload"]["result_r"] > 0
    assert events[-1]["payload"]["result_pct"] > 0
    assert events[-1]["payload"]["maximum_favorable_excursion_pct"] > 18.0
    assert events[-1]["payload"]["maximum_adverse_excursion_pct"] < 0


def test_target_one_then_stop_uses_half_target_and_half_stop_result() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars(
            [
                ("2026-08-10T13:30:00Z", 101.0, 101.5, 99.5, 100.5),
                ("2026-08-10T13:35:00Z", 101.0, 112.0, 99.0, 111.5),
                ("2026-08-11T13:30:00Z", 96.0, 97.0, 94.0, 95.0),
            ]
        ),
        interval="5m",
        evaluated_at=datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc),
    )

    assert [event["event_type"] for event in events] == [
        "paper_entry_opened",
        "target_1_reached",
        "stop_reached",
    ]
    assert events[-1]["payload"]["result_r"] > 0
    assert [leg["exit_fraction"] for leg in events[-1]["payload"]["exit_legs"]] == [0.5, 0.5]


def test_gap_below_stop_uses_first_observed_price_and_keeps_the_larger_loss() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars(
            [
                ("2026-08-10T13:30:00Z", 101.0, 101.5, 99.5, 100.5),
                ("2026-08-11T13:30:00Z", 92.0, 94.0, 90.0, 91.0),
            ]
        ),
        interval="5m",
        evaluated_at=datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc),
    )

    assert [event["event_type"] for event in events] == ["paper_entry_opened", "stop_reached"]
    stopped = events[-1]["payload"]
    assert stopped["gap_below_stop"] is True
    assert stopped["paper_exit_original"] == 92.0
    assert stopped["result_r"] < -1.0
    assert stopped["maximum_adverse_excursion_pct"] < -8.0


def test_stop_and_target_in_same_bar_are_never_counted_as_a_win() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars(
            [
                ("2026-08-10T13:30:00Z", 101.0, 101.5, 99.5, 100.5),
                ("2026-08-11T13:30:00Z", 100.0, 112.0, 94.0, 105.0),
            ]
        ),
        interval="1d",
        evaluated_at=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
    )

    assert events[-1]["event_type"] == "ambiguous_sequence"
    assert events[-1]["payload"]["conservative_assumption"] == "Stop zuerst"
    assert events[-1]["payload"]["data_quality"] == "eingeschränkt"
    assert events[-1]["payload"]["result_r"] < 0


def test_entry_and_target_in_same_bar_remain_ambiguous() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars([("2026-08-10T13:30:00Z", 101.0, 112.0, 99.5, 111.5)]),
        interval="5m",
        evaluated_at=datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc),
    )

    assert [event["event_type"] for event in events] == ["paper_entry_opened", "ambiguous_sequence"]
    assert "result_r" not in events[-1]["payload"]


def test_active_trade_exposes_unrealized_r_excursions_and_distances() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        bars(
            [
                ("2026-08-10T13:30:00Z", 101.0, 101.5, 99.5, 100.5),
                ("2026-08-11T13:30:00Z", 103.0, 107.0, 98.0, 105.0),
            ]
        ),
        interval="5m",
        evaluated_at=datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc),
    )

    assert [event["event_type"] for event in events] == ["paper_entry_opened", "still_active"]
    active = events[-1]["payload"]
    assert active["unrealized_result_pct"] > 0
    assert active["unrealized_result_r"] > 0
    assert active["maximum_favorable_excursion_pct"] > 0
    assert active["maximum_adverse_excursion_pct"] < 0
    assert active["distance_to_stop_pct"] > 0
    assert active["distance_to_next_target_pct"] > 0


def test_daily_bar_from_current_evaluation_day_is_not_treated_as_complete() -> None:
    events = evaluate_swing_signal_bars(
        signal_snapshot(),
        pd.DataFrame(
            [{"Open": 101.0, "High": 102.0, "Low": 99.0, "Close": 100.0}],
            index=pd.to_datetime(["2026-08-10"]),
        ),
        interval="1d",
        evaluated_at=datetime(2026, 8, 10, 22, 0, tzinfo=timezone.utc),
    )

    assert events == []


def test_missing_cost_contract_is_not_silently_assumed() -> None:
    snapshot = signal_snapshot()
    snapshot["order_plan"].pop("execution_cost_contract")

    with pytest.raises(ValueError, match="Kostenvertrag"):
        evaluate_swing_signal_bars(
            snapshot,
            bars([("2026-08-10T13:30:00Z", 101.0, 101.5, 99.5, 100.5)]),
            interval="5m",
            evaluated_at=datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc),
        )
