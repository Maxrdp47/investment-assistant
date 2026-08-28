from __future__ import annotations

import json
from pathlib import Path

from swing_background_runner import (
    load_swing_background_settings,
    run_swing_background_scope,
    swing_background_preflight,
)
from swing_forward_store import load_swing_forward_scans


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def settings_file(
    tmp_path,
    *,
    database_name: str = "swing.sqlite3",
    autonomous_bot: bool = False,
    event_research: bool = False,
    cot_context: bool = False,
    strategy_forward_enabled: bool = True,
) -> Path:
    payload = {
        "version": "test-background-v1",
        "universe_path": str(PROJECT_ROOT / "config" / "swing_universe.csv"),
        "database_path": str(tmp_path / database_name),
        "log_path": str(tmp_path / "swing.log"),
        "task_prefix": "TestSwingTask",
        "strategy_forward": {
            "enabled": strategy_forward_enabled,
            "lifecycle_status": (
                "ACTIVE_TEST" if strategy_forward_enabled else "LEGACY_RESEARCH_FROZEN"
            ),
            "strategy_version": "swing-long-pullback-breakout-2026.08.11-v3",
            "new_strategy_signals_allowed": strategy_forward_enabled,
            "new_paper_cycles_allowed": strategy_forward_enabled,
            "new_shadow_drafts_allowed": strategy_forward_enabled,
            "broker_order_allowed": False,
        },
        "observer": {"enabled": False},
        "scopes": {
            "asia": {
                "local_run_time": "10:30",
                "regions": ["Asien", "Australien"],
                "asset_types": ["Aktie", "ETF"],
                "evaluate_open_signals": True,
            },
            "europe": {
                "local_run_time": "18:15",
                "regions": ["Europa"],
                "asset_types": ["Aktie", "ETF"],
                "evaluate_open_signals": False,
            },
            "america_global": {
                "local_run_time": "22:30",
                "schedule_mode": "after_forecasts",
                "regions": ["USA", "Nordamerika", "Südamerika", "Global"],
                "asset_types": ["Aktie", "ETF"],
                "evaluate_open_signals": False,
            },
            "crypto": {
                "local_run_time": "22:30",
                "schedule_mode": "after_america_global",
                "regions": [],
                "asset_types": ["Krypto"],
                "evaluate_open_signals": False,
            },
        },
    }
    if autonomous_bot:
        payload["paper_bot"] = {
            "enabled": True,
            "database_path": str(tmp_path / "paper.sqlite3"),
            "virtual_capital_eur": 10_000.0,
            "paper_only": True,
        }
        payload["shadow_live"] = {
            "enabled": True,
            "database_path": str(tmp_path / "shadow.sqlite3"),
            "shadow_only": True,
            "broker_order_allowed": False,
            "collect_execution_observations": True,
            "read_only_quote_provider": None,
            "max_quote_age_seconds": 300,
        }
    if event_research:
        payload["event_research"] = {
            "enabled": True,
            "database_path": str(tmp_path / "events.sqlite3"),
            "research_only": True,
            "changes_trade_decision": False,
            "broker_order_allowed": False,
        }
    if cot_context:
        payload["cot_context"] = {
            "enabled": True,
            "database_path": str(tmp_path / "cot.sqlite3"),
            "mapping_path": str(PROJECT_ROOT / "config" / "cot_market_mapping.json"),
            "refresh_official_forward": False,
            "shadow_only": True,
            "research_only": True,
            "changes_trade_decision": False,
            "broker_order_allowed": False,
        }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_production_schedule_keeps_night_off_and_chains_evening_provider_load() -> None:
    settings = load_swing_background_settings()
    scopes = settings["scopes"]
    pipeline = (PROJECT_ROOT / "scripts" / "run_evening_pipeline.cmd").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "scripts" / "install_swing_tasks.ps1").read_text(
        encoding="utf-8"
    )

    assert scopes["asia"]["local_run_time"] == "10:30"
    assert scopes["europe"]["local_run_time"] == "18:15"
    assert scopes["america_global"]["schedule_mode"] == "after_forecasts"
    assert scopes["crypto"]["schedule_mode"] == "after_america_global"
    assert "00:30" not in json.dumps(settings)
    assert "02:15" not in json.dumps(settings)
    assert pipeline.index("run_forecasts.cmd") < pipeline.index("america_global") < pipeline.index("crypto")
    assert settings["strategy_forward"]["enabled"] is False
    assert settings["strategy_forward"]["lifecycle_status"] == "LEGACY_RESEARCH_FROZEN"
    assert settings["strategy_forward"]["new_strategy_signals_allowed"] is False
    assert settings["strategy_forward"]["new_paper_cycles_allowed"] is False
    assert settings["strategy_forward"]["new_shadow_drafts_allowed"] is False
    assert settings["strategy_forward"]["broker_order_allowed"] is False
    assert settings["observer"]["enabled"] is False
    assert "run_swing_scans.cmd" not in pipeline
    assert pipeline.count("status=LEGACY_RESEARCH_FROZEN") == 2
    assert "Disable-ScheduledTask" in installer
    assert "Legacy-Forward deaktiviert" in installer
    assert "exit /b %pipeline_exit%" in pipeline


def test_frozen_legacy_forward_is_a_side_effect_free_noop(tmp_path) -> None:
    settings = settings_file(
        tmp_path,
        autonomous_bot=True,
        event_research=True,
        cot_context=True,
        strategy_forward_enabled=False,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Ein eingefrorener Legacy-Forward darf keine Arbeit starten.")

    result = run_swing_background_scope(
        "asia",
        settings_path=settings,
        scan_callable=forbidden,
        evaluation_callable=forbidden,
        event_collection_callable=forbidden,
        cot_collection_callable=forbidden,
        shadow_quote_collection_callable=forbidden,
    )

    assert result == {
        "status": "legacy_strategy_frozen",
        "scope": "asia",
        "lifecycle_status": "LEGACY_RESEARCH_FROZEN",
        "strategy_version": "swing-long-pullback-breakout-2026.08.11-v3",
        "reason": None,
        "strategy_forward_enabled": False,
        "observer_enabled": False,
        "market_data_loaded": False,
        "strategy_evaluation_started": False,
        "scan_recorded": False,
        "new_strategy_signals": 0,
        "paper_cycle_created": False,
        "shadow_drafts_created": False,
        "broker_order_allowed": False,
        "orders_enabled": False,
    }
    assert not list(tmp_path.glob("*.sqlite3"))
    assert not (tmp_path / "swing.log").exists()


def test_frozen_legacy_forward_configuration_is_fail_closed(tmp_path) -> None:
    settings = settings_file(tmp_path, strategy_forward_enabled=False)
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["strategy_forward"]["new_paper_cycles_allowed"] = True
    settings.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_swing_background_settings(settings)
    except ValueError as exc:
        assert "fail-closed" in str(exc)
    else:
        raise AssertionError("Ein unsicherer Freeze-Vertrag muss abgelehnt werden.")


def test_observer_cannot_be_enabled_without_clean_technical_separation(tmp_path) -> None:
    settings = settings_file(tmp_path, strategy_forward_enabled=False)
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["observer"]["enabled"] = True
    settings.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_swing_background_settings(settings)
    except ValueError as exc:
        assert "Observer" in str(exc)
    else:
        raise AssertionError("Ein nicht separierter Observer muss gesperrt bleiben.")


def scan_result(scope: str, *, selected: int, loaded: int) -> dict:
    return {
        "last_scan": "2026-08-09T18:30:00+02:00",
        "scan_scope": scope,
        "objective_forward": True,
        "approved": [],
        "rejected": [],
        "prefilter_rejected": [],
        "errors": [],
        "statistics": {
            "universe_size": selected,
            "loaded_assets": loaded,
            "failed_downloads": selected - loaded,
            "approved_trades": 0,
        },
        "universe_report": {"version": "test-universe-v1", "path": "test.csv"},
        "thresholds": {},
        "risk_policy": {},
    }


def test_preflight_proves_exact_once_daily_scope_coverage_without_creating_database(tmp_path) -> None:
    settings = settings_file(tmp_path)

    result = swing_background_preflight(settings)

    assert result["status"] == "ok"
    assert result["universe_assets"] == 2_520
    assert result["covered_assets"] == 2_520
    assert result["scope_counts"] == {
        "asia": 65,
        "europe": 73,
        "america_global": 2_352,
        "crypto": 30,
    }
    assert result["unassigned"] == []
    assert result["duplicate_assignments"] == []
    assert result["database"]["status"] == "not_created"
    assert result["event_research"] == {"status": "disabled", "production_effect": "none"}
    assert result["cot_context"] == {"status": "disabled", "production_effect": "none"}
    assert not (tmp_path / "swing.sqlite3").exists()


def test_background_scope_is_objective_and_keeps_a_zero_trade_scan(tmp_path) -> None:
    settings = settings_file(tmp_path)
    received: dict = {}

    def fake_scan(_settings, **kwargs):
        received.update(kwargs)
        return scan_result("europe", selected=73, loaded=70)

    result = run_swing_background_scope(
        "europe",
        settings_path=settings,
        scan_callable=fake_scan,
    )

    assert result["status"] == "ok"
    assert result["scan_recorded"] is True
    assert result["stored"]["zero_trade_scan"] is True
    assert received["objective_forward"] is True
    assert received["scope_regions"] == {"Europa"}
    assert received["scope_asset_types"] == {"Aktie", "ETF"}
    assert result["database"]["scans"] == 1
    assert result["database"]["signals"] == 0
    assert result["run_metrics"]["selected_assets"] == 73
    assert result["run_metrics"]["loaded_assets"] == 70
    assert result["run_metrics"]["orders_enabled"] is False
    stored_run = load_swing_forward_scans(tmp_path / "swing.sqlite3")[0]["snapshot"]["background_run"]
    assert stored_run["scope"] == "europe"
    assert stored_run["duration_seconds"] >= 0


def test_total_provider_outage_is_not_recorded_as_a_valid_zero_trade_scan(tmp_path) -> None:
    settings = settings_file(tmp_path)

    result = run_swing_background_scope(
        "asia",
        settings_path=settings,
        scan_callable=lambda *_args, **_kwargs: scan_result("asia", selected=65, loaded=0),
    )

    assert result["status"] == "provider_unavailable"
    assert result["scan_recorded"] is False
    assert not (tmp_path / "swing.sqlite3").exists()


def test_background_cycle_runs_separate_paper_and_shadow_stores_without_orders(tmp_path) -> None:
    settings = settings_file(tmp_path, autonomous_bot=True)

    result = run_swing_background_scope(
        "europe",
        settings_path=settings,
        scan_callable=lambda *_args, **_kwargs: scan_result("europe", selected=73, loaded=70),
    )

    assert result["status"] == "ok"
    assert result["paper_cycle"]["paper_only"] is True
    assert result["paper_cycle"]["signals_inserted"] == 0
    assert result["shadow_cycle"]["shadow_only"] is True
    assert result["orders_enabled"] is False
    assert (tmp_path / "paper.sqlite3").exists()
    assert (tmp_path / "shadow.sqlite3").exists()


def test_event_sidecar_is_automatic_but_cannot_block_or_change_forward_scan(tmp_path) -> None:
    settings = settings_file(tmp_path, event_research=True)
    received = {}

    def failed_research_collector(**kwargs):
        received.update(kwargs)
        raise RuntimeError("event provider unavailable")

    result = run_swing_background_scope(
        "europe",
        settings_path=settings,
        scan_callable=lambda *_args, **_kwargs: scan_result("europe", selected=73, loaded=70),
        event_collection_callable=failed_research_collector,
    )

    assert result["status"] == "ok"
    assert result["scan_recorded"] is True
    assert result["database"]["scans"] == 1
    assert result["event_research"]["status"] == "research_attention"
    assert result["event_research"]["scan_or_signal_blocked"] is False
    assert result["event_research"]["production_effect"] == "none"
    assert result["event_research"]["broad_research_blocked"] is False
    assert received["signal_ids"] == []


def test_event_research_configuration_must_be_research_only_and_brokerless(tmp_path) -> None:
    settings = settings_file(tmp_path, event_research=True)
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["event_research"]["changes_trade_decision"] = True
    settings.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_swing_background_settings(settings)
    except ValueError as exc:
        assert "produktionsneutral" in str(exc)
    else:
        raise AssertionError("Produktionswirksames Event-Research muss abgelehnt werden.")


def test_cot_sidecar_failure_is_fail_open_for_scan_signal_and_broad_research(tmp_path) -> None:
    settings = settings_file(tmp_path, cot_context=True)
    received = {}

    def failed_cot_collector(**kwargs):
        received.update(kwargs)
        raise RuntimeError("CFTC unavailable")

    result = run_swing_background_scope(
        "europe",
        settings_path=settings,
        scan_callable=lambda *_args, **_kwargs: scan_result("europe", selected=73, loaded=70),
        cot_collection_callable=failed_cot_collector,
    )

    assert result["status"] == "ok"
    assert result["scan_recorded"] is True
    assert result["cot_context"]["status"] == "research_attention"
    assert result["cot_context"]["scan_or_signal_blocked"] is False
    assert result["cot_context"]["paper_cycle_blocked"] is False
    assert result["cot_context"]["broad_research_blocked"] is False
    assert result["cot_context"]["production_effect"] == "none"
    assert received["signal_ids"] == []


def test_shadow_quote_failure_cannot_block_paper_cycle_or_create_broker_order(tmp_path) -> None:
    settings = settings_file(tmp_path, autonomous_bot=True)

    result = run_swing_background_scope(
        "europe",
        settings_path=settings,
        scan_callable=lambda *_args, **_kwargs: scan_result("europe", selected=73, loaded=70),
        shadow_quote_collection_callable=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("quote provider unavailable")
        ),
    )

    assert result["status"] == "ok"
    assert result["paper_cycle"]["signals_inserted"] == 0
    assert result["shadow_execution_observations"]["status"] == "research_attention"
    assert result["shadow_execution_observations"]["paper_cycle_blocked"] is False
    assert result["shadow_execution_observations"]["broker_order_sent"] is False
    assert result["orders_enabled"] is False


def test_cot_configuration_cannot_affect_trading_decisions(tmp_path) -> None:
    settings = settings_file(tmp_path, cot_context=True)
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["cot_context"]["changes_trade_decision"] = True
    settings.write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_swing_background_settings(settings)
    except ValueError as exc:
        assert "produktionsneutral" in str(exc)
    else:
        raise AssertionError("Produktionswirksamer COT-Kontext muss abgelehnt werden.")
