from datetime import date, datetime, timezone
from copy import deepcopy

import pandas as pd
import pytest

from swing_paper_bot import (
    load_paper_signals,
    paper_bot_store_audit,
    record_paper_scan_cycle,
    run_paper_bot_evaluations,
)
from swing_risk_engine import apply_swing_risk_engine, validate_risk_decision
from swing_scanner import internal_swing_settings
from swing_shadow_live import (
    record_shadow_live_drafts,
    shadow_live_store_audit,
    shadow_paper_comparison,
)
from trading_assistant import build_swing_order_plan


def candidate(setup_id: str = "setup-1") -> dict:
    evaluated_at = datetime(2026, 8, 3, 22, 0, tzinfo=timezone.utc)
    plan = build_swing_order_plan(
        {
            "setup_type": "Pullback an Unterstützung",
            "entry_reference": 100.0,
            "entry_low": 99.0,
            "max_entry": 101.0,
            "stop": 95.0,
            "target_1": 110.0,
            "target_2": 115.0,
            "invalidation": 94.0,
        },
        asset_type="Aktie",
        original_currency="EUR",
        fx_rate_to_eur=1.0,
        analysis_reference_price_original=100.0,
        analysis_price_source="Testkurs",
        analysis_reference_observed_at=evaluated_at.isoformat(),
        evaluated_at=evaluated_at,
        signal_bar_day=date(2026, 8, 3),
        valid_until="2026-08-10",
        region="Europa",
    )
    return {
        "approved": True,
        "setup_id": setup_id,
        "symbol": "TEST.DE",
        "asset_name": "Test AG",
        "asset_type": "Aktie",
        "setup_type": "Pullback an Unterstützung",
        "entry_reference_eur": 100.0,
        "stop_eur": 95.0,
        "target_1_eur": 110.0,
        "target_2_eur": 115.0,
        "quality_score": 7.0,
        "confidence": 6.5,
        "order_plan": plan,
        "universe_metadata": {"isin": "DE000TEST001", "exchange": "XETRA"},
        "trade_republic": {"status": "unbekannt"},
        "trade_republic_price": {"available": False},
    }


def scan_result(item: dict) -> dict:
    return {
        "last_scan": "2026-08-03T22:00:00+00:00",
        "scan_scope": "test",
        "approved": [item],
        "shadow_signals": [],
        "universe_report": {"version": "test-v1"},
    }


def future_bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 96.0],
            "High": [101.0, 97.0],
            "Low": [99.0, 94.0],
            "Close": [100.0, 95.0],
            "Volume": [100_000.0, 100_000.0],
        },
        index=pd.to_datetime(["2026-08-04", "2026-08-05"]),
    )


def test_risk_engine_is_required_and_can_never_enable_a_broker_order() -> None:
    result = apply_swing_risk_engine(
        candidate(),
        internal_swing_settings(10_000.0),
        current_exposure_eur=0.0,
        current_risk_eur=0.0,
        execution_mode="paper_only",
    )
    validate_risk_decision(result, required_mode="paper_only")
    assert result["risk_decision"]["approved"] is True
    assert result["risk_decision"]["paper_only"] is True
    assert result["risk_decision"]["broker_order_allowed"] is False
    assert result["risk_decision"]["broker_order_sent"] is False


def test_explicit_short_can_never_reach_risk_paper_or_shadow_paths(tmp_path) -> None:
    short = deepcopy(candidate("short-blocked"))
    short["direction"] = "Short"
    short["order_plan"]["direction"] = "Short"
    settings = internal_swing_settings(10_000.0)

    with pytest.raises(ValueError, match="Short-Signale"):
        apply_swing_risk_engine(
            short,
            settings,
            current_exposure_eur=0.0,
            current_risk_eur=0.0,
            execution_mode="analysis_only",
        )
    paper = record_paper_scan_cycle(
        scan_result(short), settings, path=tmp_path / "paper.sqlite3"
    )
    shadow = record_shadow_live_drafts(
        scan_result(short),
        settings,
        current_exposure_eur=0.0,
        current_risk_eur=0.0,
        path=tmp_path / "shadow.sqlite3",
    )
    assert paper["signals_inserted"] == 0
    assert paper["failures"]
    assert shadow["drafts_inserted"] == 0
    assert shadow["failures"]


def test_paper_cycle_and_restart_are_idempotent_and_fills_are_causal(tmp_path) -> None:
    database = tmp_path / "paper.sqlite3"
    settings = internal_swing_settings(10_000.0)
    scan = scan_result(candidate())
    first = record_paper_scan_cycle(scan, settings, path=database)
    repeated = record_paper_scan_cycle(scan, settings, path=database)
    assert first["signals_inserted"] == 1
    assert repeated["signals_existing"] == 1
    assert paper_bot_store_audit(database)["signals"] == 1

    loader = lambda _snapshot, _now: (future_bars(), "1d", "test daily bars")
    evaluation = run_paper_bot_evaluations(
        path=database,
        evaluated_at="2026-08-06T12:00:00+00:00",
        bars_loader=loader,
    )
    restarted = run_paper_bot_evaluations(
        path=database,
        evaluated_at="2026-08-06T12:00:00+00:00",
        bars_loader=loader,
    )
    assert evaluation["events_inserted"] >= 2
    assert restarted["terminal_skipped"] == 1
    events = load_paper_signals(database)[0]["events"]
    entries = [event for event in events if event["event_type"] == "paper_entry_opened"]
    assert len(entries) == 1
    assert entries[0]["occurred_at"].startswith("2026-08-04")
    assert any(event["event_type"] == "stop_reached" for event in events)
    assert all(event["payload"]["broker_order_sent"] is False for event in events)


def test_missing_data_fails_closed_without_virtual_fill(tmp_path) -> None:
    database = tmp_path / "paper.sqlite3"
    record_paper_scan_cycle(
        scan_result(candidate("setup-data-error")),
        internal_swing_settings(10_000.0),
        path=database,
    )
    result = run_paper_bot_evaluations(
        path=database,
        evaluated_at="2026-08-06T12:00:00+00:00",
        bars_loader=lambda _snapshot, _now: (pd.DataFrame(), "", "Provider fehlt"),
    )
    events = load_paper_signals(database)[0]["events"]
    assert result["data_failures"] == 1
    assert any(event["event_type"] == "data_error_fail_closed" for event in events)
    assert not any(event["event_type"] == "paper_entry_opened" for event in events)


def test_shadow_draft_is_separate_brokerless_and_matches_paper_plan(tmp_path) -> None:
    paper_database = tmp_path / "paper.sqlite3"
    shadow_database = tmp_path / "shadow.sqlite3"
    settings = internal_swing_settings(10_000.0)
    scan = scan_result(candidate("setup-shadow"))
    shadow = record_shadow_live_drafts(
        scan,
        settings,
        current_exposure_eur=0.0,
        current_risk_eur=0.0,
        path=shadow_database,
    )
    repeated = record_shadow_live_drafts(
        scan,
        settings,
        current_exposure_eur=0.0,
        current_risk_eur=0.0,
        path=shadow_database,
    )
    record_paper_scan_cycle(scan, settings, path=paper_database)
    comparison = shadow_paper_comparison(shadow_database, paper_database)
    assert shadow["drafts_inserted"] == 1
    assert repeated["drafts_existing"] == 1
    assert comparison["compared"] == 1
    assert comparison["plan_deviations"] == 0
    assert shadow_live_store_audit(shadow_database)["broker_order_sent"] is False
    assert paper_database != shadow_database
