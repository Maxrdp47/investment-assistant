import pandas as pd

from swing_walk_forward import (
    TECHNICAL_CHALLENGER_PROFILE_NAMES,
    _technical_challenger_filter,
    swing_technical_challenger_report,
    swing_walk_forward_case_metrics,
    swing_walk_forward_strategy_profiles,
)


def test_baseline_identity_stays_frozen_and_challengers_are_separate() -> None:
    baseline = swing_walk_forward_strategy_profiles(("current",))
    assert list(baseline) == ["swing-research-current-9c3b17e3eed7"]
    assert next(iter(baseline.values()))["technical_filter"] == {}
    challengers = swing_walk_forward_strategy_profiles(TECHNICAL_CHALLENGER_PROFILE_NAMES)
    assert len(challengers) == 8
    assert all(profile["research_only"] for profile in challengers.values())
    assert all(not profile["automatic_production_activation"] for profile in challengers.values())
    assert len({profile["version"] for profile in challengers.values()}) == 8


def test_ema_rsi_filter_uses_only_the_supplied_signal_history() -> None:
    signal_history = pd.DataFrame(
        [{"Close": 101.0, "RSI_14": 55.0, "EMA_20": 100.0, "EMA_50": 98.0}]
    )
    passed, values = _technical_challenger_filter(
        signal_history,
        {"setup_type": "Pullback an Unterstützung"},
        {
            "rsi_min": 45.0,
            "rsi_max": 68.0,
            "ema20_above_ema50": True,
            "close_above_ema20": True,
        },
    )
    assert passed is True
    assert values == {
        "close": 101.0,
        "rsi_14": 55.0,
        "ema_20": 100.0,
        "ema_50": 98.0,
        "setup_type": "Pullback an Unterstützung",
    }


def test_metrics_expose_losing_streak_and_challenger_never_auto_activates() -> None:
    metrics = swing_walk_forward_case_metrics(
        [
            {"symbol": "A", "signal_at": f"202{i}-01-01", "result_r": result}
            for i, result in enumerate([1.0, -1.0, -0.5, -0.2, 2.0], start=1)
        ]
    )
    assert metrics["maximum_losing_streak"] == 3
    report = swing_technical_challenger_report([])
    assert report["production_activation_allowed"] is False
    assert report["holdout_selects_production_automatically"] is False
