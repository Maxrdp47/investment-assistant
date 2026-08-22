from __future__ import annotations

import pytest

from swing_forward_statistics import (
    filter_swing_forward_archive_rows,
    swing_asset_failure_rows,
    swing_forward_asset_type_comparison,
    swing_forward_archive_rows,
    swing_forward_statistics,
    swing_learning_readiness,
    swing_rejection_control_statistics,
)


def signal(
    signal_id: str,
    *,
    events: list[dict],
    target_2: float | None = 118.0,
    setup: str = "Ausbruch",
    asset_type: str = "Aktie",
    strategy_version: str = "test-v1",
) -> dict:
    return {
        "signal_id": signal_id,
        "snapshot": {
            "source_kind": "real_forward_scan",
            "signal_at": "2026-08-09T22:45:00+02:00",
            "asset": {
                "name": f"Asset {signal_id}",
                "ticker": signal_id,
                "isin": f"ISIN{signal_id}",
                "asset_type": asset_type,
                "region": "USA",
            },
            "strategy": {
                "setup_type": setup,
                "strategy_version": strategy_version,
            },
            "order_plan": {
                "entry_method": "Schlusskursbestätigung",
                "target_2_original": target_2,
            },
        },
        "events": events,
    }


def event(event_type: str, *, result_r: float | None = None) -> dict:
    payload = {"data_quality": "hoch"}
    if result_r is not None:
        payload.update(
            {
                "result_r": result_r,
                "result_pct": result_r * 5,
                "maximum_favorable_excursion_pct": max(result_r * 6, 0),
                "maximum_adverse_excursion_pct": min(result_r * 4, -1),
            }
        )
    if event_type == "paper_entry_opened":
        payload["paper_entry_after_costs_original"] = 100.1
    return {
        "event_type": event_type,
        "occurred_at": "2026-08-10T13:30:00+00:00",
        "payload": payload,
    }


def test_archive_does_not_count_open_missed_ambiguous_or_unusable_as_losses() -> None:
    signals = [
        signal("WIN", events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.8)]),
        signal("LOSS", events=[event("paper_entry_opened"), event("stop_reached", result_r=-1.1)]),
        signal("ACTIVE", events=[event("paper_entry_opened"), event("still_active")]),
        signal("MISSED", events=[event("entry_missed")]),
        signal("AMB", events=[event("ambiguous_sequence", result_r=-1.1)]),
        signal("EMPTY", events=[event("not_evaluable")]),
    ]

    stats = swing_forward_statistics(signals)

    assert stats["signals"] == 6
    assert stats["evaluated"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["hit_rate_pct"] == pytest.approx(50.0)
    assert stats["active"] == 1
    assert stats["missed"] == 1
    assert stats["ambiguous"] == 1
    assert stats["not_evaluable"] == 1


def test_successful_retry_supersedes_temporary_not_evaluable_status() -> None:
    recovered = signal(
        "RECOVERED",
        events=[
            event("paper_entry_opened"),
            event("not_evaluable"),
            event("still_active"),
        ],
    )

    row = swing_forward_archive_rows([recovered])[0]

    assert row["Status"] == "still_active"
    assert row["Ergebnis R"] is None


def test_retryable_provider_failure_does_not_replace_lifecycle_status() -> None:
    temporary_failure = event("not_evaluable")
    temporary_failure["payload"]["retry_allowed"] = True
    active = signal(
        "ACTIVE_RETRY",
        events=[event("paper_entry_opened"), temporary_failure],
    )
    stored_failure = event("not_evaluable")
    stored_failure["payload"]["retry_allowed"] = True
    stored = signal("STORED_RETRY", events=[stored_failure])
    genuinely_not_evaluable = signal("UNUSABLE", events=[event("not_evaluable")])

    rows = {
        row["Ticker"]: row
        for row in swing_forward_archive_rows([active, stored, genuinely_not_evaluable])
    }

    assert rows["ACTIVE_RETRY"]["Status"] == "still_active"
    assert rows["STORED_RETRY"]["Status"] == "stored"
    assert rows["UNUSABLE"]["Status"] == "not_evaluable"


def test_counterfactual_controls_never_change_trade_hit_rate() -> None:
    missed = signal(
        "MISSED_CONTROL",
        events=[
            event("entry_missed"),
            {
                "event_type": "counterfactual_outcome",
                "occurred_at": "2026-08-20T20:00:00+00:00",
                "payload": {
                    "horizon_sessions": 5,
                    "return_pct": 8.0,
                    "not_a_trade_result": True,
                },
            },
        ],
    )

    stats = swing_forward_statistics([missed])

    assert stats["evaluated"] == 0
    assert stats["wins"] == 0
    assert stats["counterfactual_controls"]["cases"] == 1
    assert stats["counterfactual_controls"]["rows"][0]["positive_rate_pct"] == 100.0


def test_released_and_shadow_strategy_statistics_are_separate() -> None:
    released = signal(
        "RELEASED",
        events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.0)],
    )
    shadow = signal(
        "SHADOW",
        events=[event("paper_entry_opened"), event("stop_reached", result_r=-1.0)],
    )
    shadow["snapshot"]["forward_evidence"] = {
        "kind": "shadow_portfolio_capacity",
        "user_portfolio_released": False,
        "exclusion_reason": "Portfoliolimit",
    }

    stats = swing_forward_statistics([released, shadow])

    assert stats["scanner_quality_total"]["signals"] == 2
    assert stats["portfolio_released"]["signals"] == 1
    assert stats["portfolio_released"]["average_r"] == 2.0
    assert stats["shadow_strategy_signals"]["signals"] == 1
    assert stats["shadow_strategy_signals"]["average_r"] == -1.0


def test_learning_readiness_never_counts_historical_walk_forward_as_real_forward() -> None:
    completed = signal(
        "REAL",
        events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.0)],
    )

    readiness = swing_learning_readiness(
        [completed],
        minimum_evaluated=1,
        minimum_observation_weeks=1,
        minimum_per_segment=1,
    )

    assert readiness["evaluated"] == 1
    assert readiness["manual_review_possible"] is False
    assert readiness["historical_walk_forward_counts_as_real_forward"] is False
    assert readiness["automatic_rule_change"] is False


def test_rejection_control_statistics_stay_outside_trade_results() -> None:
    controls = [
        {
            "snapshot": {"market_phase": "Bullenmarkt", "rejection_filters": ["crv"]},
            "events": [
                {"horizon_sessions": 5, "payload": {"return_pct": 4.0}},
                {"horizon_sessions": 20, "payload": {"return_pct": -2.0}},
            ],
        }
    ]

    result = swing_rejection_control_statistics(controls)

    assert result["controls"] == 1
    assert result["outcomes"] == 2
    assert result["counts_as_trade_result"] is False
    assert result["automatic_rule_change"] is False


def test_target_one_is_terminal_only_when_no_second_target_exists() -> None:
    with_target_two = signal(
        "OPEN_AFTER_T1",
        events=[event("paper_entry_opened"), event("target_1_reached", result_r=2.0)],
        target_2=118.0,
    )
    without_target_two = signal(
        "CLOSED_AT_T1",
        events=[event("paper_entry_opened"), event("target_1_reached", result_r=2.0)],
        target_2=None,
    )

    rows = {row["Ticker"]: row for row in swing_forward_archive_rows([with_target_two, without_target_two])}

    assert rows["OPEN_AFTER_T1"]["Status"] == "still_active"
    assert rows["OPEN_AFTER_T1"]["Ergebnis R"] is None
    assert rows["CLOSED_AT_T1"]["Status"] == "target_1_reached"
    assert rows["CLOSED_AT_T1"]["Ergebnis R"] == 2.0
    assert rows["CLOSED_AT_T1"]["Ergebnisstatus"] == "Gewinn"
    assert rows["CLOSED_AT_T1"]["Max. Zwischengewinn %"] == 12.0
    assert rows["CLOSED_AT_T1"]["Haltedauer Tage"] == 0.0


def test_profit_factor_expected_r_drawdown_and_segments_are_transparent() -> None:
    signals = [
        signal("W1", events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.0)]),
        signal("L1", events=[event("paper_entry_opened"), event("stop_reached", result_r=-1.0)]),
        signal("L2", events=[event("paper_entry_opened"), event("stop_reached", result_r=-0.5)]),
    ]

    stats = swing_forward_statistics(signals)

    assert stats["average_r"] == pytest.approx(1 / 6)
    assert stats["profit_factor_r"] == pytest.approx(4 / 3)
    assert stats["max_drawdown_r"] == pytest.approx(-1.5)
    setup_segment = next(
        row for row in stats["segments"] if row["Segment"] == "Setup" and row["Wert"] == "Ausbruch"
    )
    assert setup_segment["Ausgewertet"] == 3
    assert setup_segment["Trefferquote %"] == pytest.approx(100 / 3)


def test_asset_type_forward_comparison_waits_for_real_results_without_changing_weights() -> None:
    signals = [
        signal(
            "STOCK",
            events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.0)],
            asset_type="Aktie",
            strategy_version="neutral-v1",
        ),
        signal(
            "ETF",
            events=[event("paper_entry_opened"), event("stop_reached", result_r=-1.0)],
            asset_type="ETF",
            strategy_version="neutral-v1",
        ),
    ]

    collecting = swing_forward_asset_type_comparison(
        signals,
        minimum_evaluated_per_class=2,
        strategy_versions={"neutral-v1"},
    )
    descriptive = swing_forward_asset_type_comparison(
        signals,
        minimum_evaluated_per_class=1,
        strategy_versions={"neutral-v1"},
    )

    assert collecting["comparison_ready"] is False
    assert all(row["hit_rate_pct"] is None for row in collecting["rows"])
    assert descriptive["comparison_ready"] is True
    assert descriptive["causal_claim"] is False
    assert descriptive["automatic_weight_change"] is False
    assert descriptive["quota_or_asset_class_target"] is False


def test_archive_filters_combine_without_changing_source_rows() -> None:
    source_rows = swing_forward_archive_rows(
        [
            signal("WIN", events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.0)]),
            signal("MISS", events=[event("entry_missed")], setup="Pullback"),
        ],
        user_signal_ids={"WIN"},
    )

    filtered = filter_swing_forward_archive_rows(
        source_rows,
        statuses={"target_2_reached"},
        setups={"Ausbruch"},
        asset_types={"Aktie"},
        regions={"USA"},
        market_phases={"Unbekannt"},
        volatility_regimes={"Nicht verfügbar"},
        evidence_kinds={"scanner_released"},
        strategy_versions={"test-v1"},
        sources={"real_forward_scan"},
        user_trade_states={"Ja"},
        entry_methods={"Schlusskursbestätigung"},
        result_states={"Gewinn"},
        search="isinwin",
        signal_from="2026-08-09",
        signal_to="2026-08-09",
        minimum_result_r=1.5,
        maximum_result_r=2.5,
    )

    assert [row["Ticker"] for row in filtered] == ["WIN"]
    assert filtered[0]["Nutzertrade"] == "Ja"
    assert len(source_rows) == 2


def test_repeated_asset_failures_are_visible_but_never_auto_deleted() -> None:
    scans = [
        {
            "observed_at": f"2026-08-{day:02d}T18:15:00+02:00",
            "snapshot": {
                "scan_scope": "europe",
                "technical_failures": [
                    {"ticker": "BAD.DE", "asset": "Bad Data", "reasons": ["Keine Kursdaten verfügbar."]}
                ],
            },
        }
        for day in (9, 10, 11)
    ]

    rows = swing_asset_failure_rows(scans)

    assert rows[0]["Ticker"] == "BAD.DE"
    assert rows[0]["Fehlschläge"] == 3
    assert rows[0]["Wiederkehrend"] is True
    assert "niemals automatisch" in rows[0]["Maßnahme"]


def test_scanner_quality_and_tr_executable_statistics_are_strictly_separate() -> None:
    tr_signal = signal(
        "TR",
        events=[event("paper_entry_opened"), event("target_2_reached", result_r=2.0)],
    )
    paper_signal = signal(
        "PAPER",
        events=[event("paper_entry_opened"), event("stop_reached", result_r=-1.0)],
    )
    tr_signal["snapshot"]["trade_republic"] = {
        "analysis_listing_key": "listing-tr",
        "status": "unbekannt",
        "execution_ready_at_signal": False,
    }
    paper_signal["snapshot"]["trade_republic"] = {
        "analysis_listing_key": "listing-paper",
        "status": "TR nicht handelbar",
        "execution_ready_at_signal": False,
    }

    stats = swing_forward_statistics(
        [tr_signal, paper_signal],
        tr_references={
            "listing-tr": {
                "status": "TR handelbar",
                "execution_ready": True,
                "tr_listing": {
                    "ticker": "TR-TEST",
                    "isin": "ISINTR",
                    "exchange": "TR TEST VENUE",
                },
            },
            "listing-paper": {
                "status": "TR nicht handelbar",
                "execution_ready": False,
            },
        },
    )

    assert stats["scanner_quality_total"]["signals"] == 2
    assert stats["scanner_quality_total"]["evaluated"] == 2
    assert stats["tr_tradeable_listings"]["signals"] == 1
    assert stats["tr_executable_trades"]["signals"] == 1
    assert stats["tr_executable_trades"]["average_r"] == 2.0
    assert stats["paper_only"]["signals"] == 1
    assert stats["paper_only"]["average_r"] == -1.0
