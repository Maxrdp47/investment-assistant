from __future__ import annotations

import copy
from pathlib import Path

import pytest

from swing_edge_diagnostics import (
    FORWARD_STATUS_REQUIRED_CASE_FIELDS,
    analyze_real_forward_trades,
    analyze_real_forward_stopouts,
    analyze_swing_edge_cases,
    connect_development_patterns_to_forward_losses,
    render_forward_status_markdown,
    swing_edge_case_diagnostic,
)


def _case(
    case_id: str,
    result_r: float,
    *,
    terminal: str = "stop_reached",
    mfe_pct: float = 1.0,
    mae_pct: float = -2.0,
    gap: bool = False,
    issuer: str = "issuer-a",
) -> dict:
    return {
        "case_id": case_id,
        "symbol": case_id,
        "signal_at": f"2026-01-0{case_id[-1]}T23:59:00+00:00",
        "result_r": result_r,
        "research_identity": {"issuer_id": issuer},
        "snapshot": {
            "asset": {"asset_type": "Aktie", "region": "USA"},
            "strategy": {
                "setup_type": "pullback",
                "market_phase": "Aufwärtstrend",
                "volatility_regime": "normal",
            },
            "signal_features": {"risk_pct": 2.0},
            "order_plan": {"limit_price_original": 100.0, "initial_stop_original": 98.0},
        },
        "events": [
            {
                "event_type": "paper_entry_opened",
                "occurred_at": "2026-01-10T00:00:00+00:00",
                "payload": {"paper_entry_after_costs_original": 100.0},
            },
            {
                "event_type": terminal,
                "occurred_at": "2026-01-13T00:00:00+00:00",
                "payload": {
                    "interval": "1d",
                    "result_r": result_r,
                    "maximum_favorable_excursion_pct": mfe_pct,
                    "maximum_adverse_excursion_pct": mae_pct,
                    "gap_below_stop": gap,
                },
            },
        ],
    }


def test_case_diagnostic_converts_excursions_to_r_without_guessing_bar_order() -> None:
    row = swing_edge_case_diagnostic(_case("case-1", -1.0, mfe_pct=2.4, mae_pct=-2.2))

    assert row["mfe_r"] == pytest.approx(1.2)
    assert row["mae_r"] == pytest.approx(-1.1)
    assert row["calendar_days_to_terminal"] == 3
    assert row["mfe_before_stop_status"] == "not_provable_inside_daily_bar"
    assert row["stop_distance_atr"] is None
    assert row["diagnosis"] == "exit_or_stop_sensitivity_candidate"
    assert row["automatic_rule_change"] is False


def test_gap_loss_is_classified_separately() -> None:
    row = swing_edge_case_diagnostic(_case("case-1", -1.4, gap=True))

    assert row["diagnosis"] == "gap_or_execution_risk"
    assert row["gap_below_stop"] is True


def test_report_shows_loss_streak_segments_coverage_and_no_rule_change() -> None:
    report = analyze_swing_edge_cases(
        [
            _case("case-1", -1.0, mfe_pct=0.2),
            _case("case-2", -1.0, mfe_pct=0.4),
            _case("case-3", 2.0, terminal="target_2_reached", mfe_pct=4.0, mae_pct=-0.5),
        ]
    )

    assert report["overall"]["evaluated"] == 3
    assert report["overall"]["average_r"] == 0
    assert report["overall"]["profit_factor"] == 1
    assert report["maximum_loss_streak"] == 2
    assert report["coverage"]["mfe_mae_cases"] == 3
    assert report["coverage"]["atr_stop_distance_cases"] == 0
    assert report["segments"]["setup_type"][0]["setup_type"] == "pullback"
    assert report["automatic_rule_change"] is False
    assert report["production_activation_allowed"] is False


def test_forward_stopout_classes_and_counterfactuals_remain_separate() -> None:
    case = _case("case-1", -1.0, mfe_pct=1.2, mae_pct=-2.2)
    case["snapshot"]["source_kind"] = "real_forward_scan"
    case["snapshot"]["asset"]["ticker"] = "TEST"
    case["snapshot"]["signal_at"] = case["signal_at"]
    before = copy.deepcopy(case)
    context = {
        "case-1": {
            "status": "available",
            "dataset_fingerprint": "frozen-v1",
            "future_bars_used_for_features": 0,
            "atr_14_original": 4.0,
            "pullback_low_original": 94.0,
            "rsi_14": 55.0,
            "ema_20": 101.0,
            "ema_50": 99.0,
            "ema20_relative_to_ema50": 1.02,
            "close_relative_to_ema20": 1.01,
            "close_relative_to_ema50": 1.03,
            "buyer_confirmation": True,
            "bearish_candles": 3,
            "fibonacci_inside_0618_0786": False,
            "bos_close_break": True,
            "market_structure_classification": ["HH", "HL"],
            "opening_level_contact": False,
            "cot_status": "unavailable_point_in_time",
            "post_terminal_recovery": {"recovered_entry": False},
        }
    }

    report = analyze_real_forward_stopouts([case], contexts=context)
    row = report["cases"][0]

    assert case == before
    assert report["stopouts_analyzed"] == 1
    assert row["stopout_class"] == "F"
    assert row["stop_distance_atr"] == pytest.approx(0.5)
    assert row["future_bars_used_for_signal_features"] == 0
    assert row["counterfactuals"]["variants"]["existing_stop"]["outcome_at_original_terminal"]["real_forward_result"] is True
    assert row["counterfactuals"]["variants"]["pullback_low"]["outcome_at_original_terminal"]["real_forward_result"] is False
    assert row["counterfactuals"]["intrabar_order_invented"] is False
    assert report["automatic_rule_change"] is False


def test_all_closed_forward_trades_keep_required_status_fields_and_winners() -> None:
    loss = _case("case-1", -1.0, mfe_pct=1.2, mae_pct=-2.2)
    win = _case(
        "case-2",
        2.0,
        terminal="target_2_reached",
        mfe_pct=4.2,
        mae_pct=-0.5,
    )
    for case in (loss, win):
        case["snapshot"]["source_kind"] = "real_forward_scan"
        case["snapshot"]["asset"]["ticker"] = case["case_id"].upper()
    before = copy.deepcopy([loss, win])

    report = analyze_real_forward_trades([loss, win])

    assert [loss, win] == before
    assert report["scope"] == "all_closed_real_forward_paper_trades"
    assert report["overall"]["wins"] == 1
    assert report["overall"]["losses"] == 1
    assert report["overall"]["median_mfe_r"] == pytest.approx(1.35)
    assert report["overall"]["mfe_at_least_1r_count"] == 1
    assert report["overall"]["mfe_at_least_2r_count"] == 1
    for row in report["cases"]:
        assert set(FORWARD_STATUS_REQUIRED_CASE_FIELDS).issubset(row)
    assert set(report["required_case_fields"]) == set(
        FORWARD_STATUS_REQUIRED_CASE_FIELDS
    )
    assert report["automatic_rule_change"] is False


def test_stop_execution_and_post_stop_windows_are_explicit_counterfactuals() -> None:
    case = _case("case-1", -1.3, mfe_pct=1.0, mae_pct=-3.0, gap=True)
    case["snapshot"]["source_kind"] = "real_forward_scan"
    case["snapshot"]["asset"]["ticker"] = "TEST"
    case["snapshot"]["order_plan"].update(
        {"target_1_original": 104.0, "target_2_original": 108.0}
    )
    case["events"][-1]["payload"]["paper_exit_original"] = 97.0
    case["events"].append(
        {
            "event_type": "counterfactual_outcome",
            "occurred_at": "2026-01-20T00:00:00+00:00",
            "payload": {
                "not_a_trade_result": True,
                "horizon_sessions": 5,
                "reference_day": "2026-01-14",
                "reference_price_original": 98.0,
                "outcome_day": "2026-01-20",
                "outcome_close_original": 103.0,
                "maximum_favorable_excursion_pct": 7.0,
                "maximum_adverse_excursion_pct": -1.0,
            },
        }
    )
    context = {
        "case-1": {
            "status": "available",
            "atr_14_original": 3.0,
            "pullback_low_original": 95.0,
            "future_bars_used_for_features": 0,
        }
    }

    row = analyze_real_forward_trades([case], contexts=context)["cases"][0]
    window = row["post_stop_counterfactuals"]["5"]

    assert row["stop_execution_worse_than_planned"] is True
    assert row["stop_execution_deviation_r"] == pytest.approx(-0.5)
    assert row["stop_execution_deviation_pct"] == pytest.approx((97 / 98 - 1) * 100)
    assert window["diagnostic_only"] is True
    assert window["real_forward_result"] is False
    assert window["target_1_reached_after_stop"] is True
    assert window["stop_variants"]["pullback_low"]["stop_held_through_horizon"] is True
    assert window["stop_variants"]["pullback_low"]["real_forward_result"] is False
    assert window["intrabar_order_proven"] is False


def test_markdown_status_contains_trade_level_mfe_mae_time_and_context() -> None:
    case = _case("case-1", -1.0, mfe_pct=1.2, mae_pct=-2.2)
    case["snapshot"]["source_kind"] = "real_forward_scan"
    case["snapshot"]["asset"]["ticker"] = "TEST"
    report = analyze_real_forward_trades([case])

    markdown = render_forward_status_markdown(report)

    assert "Trade-Kerndaten" in markdown
    assert "Ergebnis R" in markdown
    assert "MFE R / %" in markdown
    assert "MAE R / %" in markdown
    assert "Sitzungen MFE / Exit" in markdown
    assert "Signalkontext und maschinell erzeugte sachliche Ursache" in markdown
    assert "nur Counterfactual" in markdown
    assert "TEST" in markdown


def test_project_status_keeps_concrete_forward_trade_contract() -> None:
    project_status = (
        Path(__file__).resolve().parents[1] / "PROJECT_STATUS.md"
    ).read_text(encoding="utf-8")

    for required_text in (
        "#### Konkreter echter Swing-Forward-Status",
        "| Ticker | Setup | Entry | Stop |",
        "Ergebnis R",
        "MFE R / %",
        "MAE R / %",
        "Sitzungen MFE / Exit",
        "schlechter als Stop; Abweichung R/%",
        "Signalkontext und maschinell erzeugte sachliche Ursache",
        "5-/20-Sitzungs-Diagnose nach dem Stop",
        "ausschließlich Counterfactual",
        "scripts/run_swing_edge_diagnostics.py --markdown",
    ):
        assert required_text in project_status
    for symbol in (
        "EWL",
        "BANR",
        "ASB",
        "UMBF",
        "HOPE",
        "BATRK",
        "IJH",
        "LLYVA",
        "LYV",
        "LT.NS",
        "LLYVK",
        "EWBC",
        "SREN.SW",
        "BBT",
    ):
        assert f"| {symbol} |" in project_status


def test_development_forward_link_is_diagnostic_not_proof() -> None:
    forward = {
        "forensics_version": "forensics-v1",
        "cases": [
            {
                "buyer_confirmation": True,
                "bearish_candles": 3,
                "fibonacci_inside_0618_0786": False,
                "ema20_relative_to_ema50": 1.02,
                "rsi_14": 55.0,
                "bos_close_break": True,
                "opening_level_contact": False,
                "cot_status": "unavailable_point_in_time",
                "stopout_class": "F",
                "counterfactuals": {
                    "variants": {
                        "pullback_low": {"stop_observation": {"touched": False}}
                    }
                },
            }
        ],
    }
    development = {
        "pattern_version": "patterns-v1",
        "hypotheses": [
            {"hypothesis_id": "buyer_confirmation", "classification": "C"}
        ],
    }

    linked = connect_development_patterns_to_forward_losses(development, forward)

    buyer = next(row for row in linked["rows"] if row["hypothesis_id"] == "buyer_confirmation")
    assert buyer["forward_losses_with_pattern"] == 1
    assert buyer["forward_losses_with_pattern_and_alternative_stop_held"] == 1
    assert linked["causal_proof"] is False
    assert linked["automatic_rule_change"] is False
