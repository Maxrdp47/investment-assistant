from __future__ import annotations

from datetime import datetime

import scripts.run_swing_broad_research_supervisor as supervisor


def test_supervisor_defaults_use_safe_parallel_capacity() -> None:
    assert supervisor.DEFAULT_BROAD_WORKERS == 6
    assert supervisor.DEFAULT_ASSETS_PER_BATCH == 32


def test_supervisor_guard_stops_during_protected_window(monkeypatch) -> None:
    monkeypatch.setattr(
        supervisor,
        "_campaign_status",
        lambda now: ({"jobs_pending": 0}, {"protected_windows": []}, {}, []),
    )
    monkeypatch.setattr(supervisor, "campaign_is_protected_time", lambda now, config: True)
    monkeypatch.setattr(
        supervisor,
        "campaign_active_production_jobs",
        lambda config, project_root: [],
    )

    decision = supervisor.broad_supervisor_guard(datetime.now().astimezone())

    assert decision == {
        "run_allowed": False,
        "reason": "protected_production_window",
    }


def test_supervisor_guard_stops_for_active_production(monkeypatch) -> None:
    monkeypatch.setattr(
        supervisor,
        "_campaign_status",
        lambda now: ({"jobs_pending": 0}, {"protected_windows": []}, {}, []),
    )
    monkeypatch.setattr(supervisor, "campaign_is_protected_time", lambda now, config: False)
    monkeypatch.setattr(
        supervisor,
        "campaign_active_production_jobs",
        lambda config, project_root: ["Swing-Live-/Forward-Scan"],
    )

    decision = supervisor.broad_supervisor_guard(datetime.now().astimezone())

    assert decision["run_allowed"] is False
    assert decision["reason"] == "production_active"
    assert decision["active_production"] == ["Swing-Live-/Forward-Scan"]


def test_supervisor_guard_allows_clear_research_window(monkeypatch) -> None:
    monkeypatch.setattr(
        supervisor,
        "_campaign_status",
        lambda now: ({"jobs_pending": 0}, {"protected_windows": []}, {}, []),
    )
    monkeypatch.setattr(supervisor, "campaign_is_protected_time", lambda now, config: False)
    monkeypatch.setattr(
        supervisor,
        "campaign_active_production_jobs",
        lambda config, project_root: [],
    )

    decision = supervisor.broad_supervisor_guard(datetime.now().astimezone())

    assert decision == {"run_allowed": True, "reason": "clear"}
