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
    tmp_path, *, database_name: str = "swing.sqlite3", autonomous_bot: bool = False
) -> Path:
    payload = {
        "version": "test-background-v1",
        "universe_path": str(PROJECT_ROOT / "config" / "swing_universe.csv"),
        "database_path": str(tmp_path / database_name),
        "log_path": str(tmp_path / "swing.log"),
        "task_prefix": "TestSwingTask",
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
        }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_production_schedule_keeps_night_off_and_chains_evening_provider_load() -> None:
    settings = load_swing_background_settings()
    scopes = settings["scopes"]
    pipeline = (PROJECT_ROOT / "scripts" / "run_evening_pipeline.cmd").read_text(encoding="utf-8")

    assert scopes["asia"]["local_run_time"] == "10:30"
    assert scopes["europe"]["local_run_time"] == "18:15"
    assert scopes["america_global"]["schedule_mode"] == "after_forecasts"
    assert scopes["crypto"]["schedule_mode"] == "after_america_global"
    assert "00:30" not in json.dumps(settings)
    assert "02:15" not in json.dumps(settings)
    assert pipeline.index("run_forecasts.cmd") < pipeline.index("america_global") < pipeline.index("crypto")
    assert "exit /b %pipeline_exit%" in pipeline


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
