from __future__ import annotations

from datetime import datetime

import scripts.run_swing_broad_research_supervisor as supervisor


def test_supervisor_defaults_use_safe_parallel_capacity() -> None:
    assert supervisor.DEFAULT_BROAD_WORKERS == 6
    assert supervisor.DEFAULT_ASSETS_PER_BATCH == 32


def test_supervisor_guard_allows_legacy_window_without_real_conflict(monkeypatch) -> None:
    monkeypatch.setattr(
        supervisor,
        "_campaign_status",
        lambda now: ({"jobs_pending": 0}, {"protected_windows": []}, {}, []),
    )
    monkeypatch.setattr(
        supervisor,
        "historical_research_runtime_gate",
        lambda config, project_root: {
            "run_allowed": True,
            "reason": "CLEAR",
            "active_production": [],
            "time_of_day_used": False,
            "legacy_time_windows_applied": False,
        },
    )

    decision = supervisor.broad_supervisor_guard(
        datetime.fromisoformat("2026-09-06T21:45:00+02:00")
    )

    assert decision["run_allowed"] is True
    assert decision["reason"] == "clear"
    assert decision["runtime_gate"]["legacy_time_windows_applied"] is False


def test_supervisor_guard_stops_for_active_production(monkeypatch) -> None:
    monkeypatch.setattr(
        supervisor,
        "_campaign_status",
        lambda now: ({"jobs_pending": 0}, {"protected_windows": []}, {}, []),
    )
    monkeypatch.setattr(
        supervisor,
        "historical_research_runtime_gate",
        lambda config, project_root: {
            "run_allowed": False,
            "reason": "BLOCKED_REAL_CONFLICT",
            "active_production": ["Swing-Live-/Forward-Scan"],
            "time_of_day_used": False,
            "legacy_time_windows_applied": False,
        },
    )

    decision = supervisor.broad_supervisor_guard(datetime.now().astimezone())

    assert decision["run_allowed"] is False
    assert decision["reason"] == "blocked_real_conflict"
    assert decision["runtime_gate"]["active_production"] == [
        "Swing-Live-/Forward-Scan"
    ]


def test_supervisor_guard_allows_clear_research_window(monkeypatch) -> None:
    monkeypatch.setattr(
        supervisor,
        "_campaign_status",
        lambda now: ({"jobs_pending": 0}, {"protected_windows": []}, {}, []),
    )
    monkeypatch.setattr(
        supervisor,
        "historical_research_runtime_gate",
        lambda config, project_root: {
            "run_allowed": True,
            "reason": "CLEAR",
            "active_production": [],
            "time_of_day_used": False,
            "legacy_time_windows_applied": False,
        },
    )

    decision = supervisor.broad_supervisor_guard(datetime.now().astimezone())

    assert decision["run_allowed"] is True
    assert decision["reason"] == "clear"
