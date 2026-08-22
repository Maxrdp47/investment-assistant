from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from scripts.run_swing_walk_forward_campaign import (
    _command_for_job,
    _dataset_epoch_for_job,
    _dataset_prepare_command,
    _dataset_scopes_for_job,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward_campaign import (
    campaign_active_production_jobs,
    campaign_is_protected_time,
    campaign_jobs,
    campaign_start_buffer_minutes,
    campaign_status,
    load_campaign_config,
    load_campaign_state,
    next_campaign_job,
    save_campaign_state,
)


def config() -> dict:
    return {
        "version": "test-campaign-v1",
        "shard_count": 2,
        "batch_size": 100,
        "analysis_workers": 2,
        "analysis_executor": "threads",
        "start_time": "00:00",
        "duration_hours": 24,
        "repeat_minutes": 5,
        "dataset_epoch_version": "test-frozen-dataset-v1",
        "minimum_clear_window_minutes": 90,
        "protected_windows": [{"start": "17:45", "end": "18:45"}],
        "contracts": [
            {
                "id": "fixed-current",
                "recurrence": "once",
                "profiles": ["current", "balanced", "precision", "payoff"],
                "start": "2010-01-01",
                "end": "2016-01-01",
                "development_end": "2012-12-31",
                "validation_end": "2014-12-31",
                "future_sessions": 25,
                "step_sessions": 5,
                "maximum_cases_per_symbol": 12,
                "sampling_mode": "balanced_history",
            },
            {
                "id": "weekly-recent",
                "recurrence": "weekly",
                "profile": "precision",
                "start": "2022-01-01",
                "end": None,
                "development_end": "2023-12-31",
                "validation_end": "2024-12-31",
                "future_sessions": 25,
                "step_sessions": 3,
                "maximum_cases_per_symbol": 6,
                "sampling_mode": "recent_incremental",
            },
        ],
    }


def test_campaign_builds_diversified_fixed_and_weekly_shards() -> None:
    now = datetime.fromisoformat("2026-08-17T12:00:00+02:00")
    jobs = campaign_jobs(config(), ["AAA", "BBB", "CCC", "DDD"], now=now)

    assert len(jobs) == 4
    assert {job["epoch"] for job in jobs} == {"fixed", "2026-W34"}
    assert all(len(job["tickers"]) == 2 for job in jobs)
    assert jobs[0]["tickers"] == ["AAA", "CCC"]
    assert jobs[1]["tickers"] == ["BBB", "DDD"]


def test_campaign_state_rotates_failed_job_and_is_atomic(tmp_path) -> None:
    path = tmp_path / "campaign.json"
    now = datetime.fromisoformat("2026-08-17T12:00:00+02:00")
    jobs = campaign_jobs(config(), ["AAA", "BBB"], now=now)
    state = load_campaign_state(path)
    first = next_campaign_job(jobs, state)
    state["attempts"][first["job_key"]] = 1
    save_campaign_state(state, path)
    reloaded = load_campaign_state(path)
    second = next_campaign_job(jobs, reloaded)

    assert first["job_key"] != second["job_key"]
    assert campaign_status(jobs, reloaded)["jobs_pending"] == len(jobs)


def test_campaign_protected_window_and_command_contract() -> None:
    settings = config()
    settings["locked_profile_versions"] = {
        name: f"locked-{name}"
        for name in ("current", "balanced", "precision", "payoff")
    }
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-17T18:15:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-17T16:30:00+02:00"), settings
    )
    assert not campaign_is_protected_time(
        datetime.fromisoformat("2026-08-17T16:14:00+02:00"), settings
    )
    assert not campaign_is_protected_time(
        datetime.fromisoformat("2026-08-17T19:15:00+02:00"), settings
    )
    job = campaign_jobs(
        settings,
        ["AAA", "BBB"],
        now=datetime.fromisoformat("2026-08-17T12:00:00+02:00"),
    )[0]
    command = _command_for_job(job, settings)

    assert "--sampling-mode" in command
    assert "balanced_history" in command
    assert command[command.index("--selection-round") + 1] == "0"
    assert command[command.index("--selection-round-role") + 1] == "exploration"
    for name, version in settings["locked_profile_versions"].items():
        assert f"{name}={version}" in command
    assert "--end" in command
    assert "--skip-final-report" in command
    profile_index = command.index("--profiles")
    assert command[profile_index + 1 : profile_index + 5] == [
        "current",
        "balanced",
        "precision",
        "payoff",
    ]
    assert "2016-01-01" in command
    assert "AAA" in command


def test_campaign_freezes_one_shared_dataset_contract_for_all_fixed_profiles() -> None:
    settings = config()
    job = campaign_jobs(
        settings,
        ["AAA", "BBB"],
        now=datetime.fromisoformat("2026-08-17T12:00:00+02:00"),
    )[0]
    epoch = _dataset_epoch_for_job(job, settings)
    scopes = _dataset_scopes_for_job(job, settings)
    prepare = _dataset_prepare_command(job, settings, universe_path=Path("universe.json"))
    command = _command_for_job(
        job,
        settings,
        universe_path=Path("universe.json"),
        dataset_epoch=epoch,
        dataset_fingerprint="abc123",
    )

    assert epoch == "test-frozen-dataset-v1|fixed"
    assert scopes == [("2010-01-01", "2016-01-01")]
    assert prepare.count("--prepare-dataset") == 1
    assert prepare[prepare.index("--dataset-epoch") + 1] == epoch
    assert "2010-01-01|2016-01-01" in prepare
    assert command[command.index("--expected-dataset-fingerprint") + 1] == "abc123"
    assert command[command.index("--dataset-epoch") + 1] == epoch


def test_global_campaign_lock_rejects_duplicate_job(tmp_path) -> None:
    lock_path = tmp_path / "campaign.lock"

    with SwingRunLock(lock_path):
        with pytest.raises(SwingRunAlreadyActiveError):
            with SwingRunLock(lock_path):
                pass


def test_active_production_lock_blocks_research_start_probe(tmp_path) -> None:
    production_lock = tmp_path / "swing_forward.scan.lock"
    settings = {
        "protected_runtime_locks": [
            {"name": "Swing-Live-/Forward-Scan", "path": str(production_lock)}
        ]
    }

    assert campaign_active_production_jobs(settings, project_root=tmp_path) == []
    with SwingRunLock(production_lock):
        assert campaign_active_production_jobs(settings, project_root=tmp_path) == [
            "Swing-Live-/Forward-Scan"
        ]
    assert campaign_active_production_jobs(settings, project_root=tmp_path) == []


def test_failed_worker_job_remains_resumable_and_uncompleted() -> None:
    jobs = campaign_jobs(
        config(),
        ["AAA", "BBB"],
        now=datetime.fromisoformat("2026-08-17T12:00:00+02:00"),
    )
    failed = jobs[0]
    state = {
        "completed": {},
        "attempts": {failed["job_key"]: 1},
        "last_event": {
            "type": "failed",
            "phase": "analysis",
            "job_key": failed["job_key"],
        },
    }

    assert campaign_status(jobs, state)["jobs_pending"] == len(jobs)
    assert failed["job_key"] not in state["completed"]


def test_later_selection_rounds_wait_for_all_prior_round_shards() -> None:
    settings = config()
    settings["contracts"] = [
        {
            **settings["contracts"][0],
            "id": "round-a",
            "selection_round": 0,
            "selection_round_label": "A",
            "selection_round_role": "exploration",
        },
        {
            **settings["contracts"][0],
            "id": "round-b",
            "selection_round": 1,
            "selection_round_label": "B",
            "selection_round_role": "locked_validation",
            "depends_on": ["round-a"],
        },
        {
            **settings["contracts"][0],
            "id": "round-c",
            "selection_round": 2,
            "selection_round_label": "C",
            "selection_round_role": "final_confirmation",
            "depends_on": ["round-b"],
        },
    ]
    jobs = campaign_jobs(
        settings,
        ["AAA", "BBB", "CCC", "DDD"],
        now=datetime.fromisoformat("2026-08-17T12:00:00+02:00"),
    )
    state = {"completed": {}, "attempts": {}}

    assert next_campaign_job(jobs, state)["contract"]["id"] == "round-a"
    round_a_jobs = [job for job in jobs if job["contract"]["id"] == "round-a"]
    for job in round_a_jobs:
        state["completed"][job["job_key"]] = {}
    assert next_campaign_job(jobs, state)["contract"]["id"] == "round-b"
    status = campaign_status(jobs, state)
    assert status["jobs_blocked_by_round_dependencies"] == 2
    assert status["fixed_rounds"][0]["jobs_completed"] == 2


def test_project_campaign_prelocks_three_twelve_case_rounds() -> None:
    settings = load_campaign_config()
    assert len(settings["contracts"]) == 7
    assert len(settings["challenger_contracts"]) == 24
    assert (
        len(settings["contracts"]) + len(settings["challenger_contracts"])
    ) * int(settings["shard_count"]) == 248
    fixed = [contract for contract in settings["contracts"] if contract["recurrence"] == "once"]
    capacity_by_round: dict[str, int] = {}
    for contract in fixed:
        label = str(contract["selection_round_label"])
        capacity_by_round[label] = capacity_by_round.get(label, 0) + int(
            contract["maximum_cases_per_symbol"]
        )

    assert capacity_by_round == {"A": 12, "B": 12, "C": 12}
    assert len(settings["locked_profile_versions"]) == 4
    round_b = [contract for contract in fixed if contract["selection_round_label"] == "B"]
    round_c = [contract for contract in fixed if contract["selection_round_label"] == "C"]
    assert all(len(contract["depends_on"]) == 2 for contract in round_b + round_c)
    jobs = campaign_jobs(
        settings,
        ["AAA"],
        now=datetime.fromisoformat("2026-08-18T12:00:00+02:00"),
    )
    fixed_jobs = [job for job in jobs if job["contract"]["recurrence"] == "once"]
    assert {
        _dataset_epoch_for_job(job, settings)
        for job in fixed_jobs
    } == {"swing-research-frozen-ohlcv-2026.08.18-v1|fixed"}
    assert set(_dataset_scopes_for_job(fixed_jobs[0], settings)) == {
        ("2010-01-01", "2016-01-01"),
        ("2016-01-01", None),
    }


def test_project_campaign_uses_five_minute_ignore_new_trigger() -> None:
    settings = load_campaign_config()
    installer = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "install_swing_walk_forward_campaign_task.ps1"
    ).read_text(encoding="utf-8")

    assert settings["repeat_minutes"] == 5
    assert settings["start_time"] == "00:00"
    assert settings["duration_hours"] == 24
    assert settings["analysis_workers"] == 6
    assert settings["analysis_executor"] == "processes"
    assert settings["minimum_clear_window_minutes"] == 90
    assert settings["maximum_expected_shard_minutes"] == 90
    assert settings["production_priority_grace_seconds"] == 5
    assert campaign_start_buffer_minutes(settings) == 90
    assert settings["protected_windows"] == [
        {
            "start": "10:30",
            "end": "11:30",
            "reason": "Asien-/Australien-Swing-Scan",
        },
        {"start": "17:15", "end": "18:45", "reason": "Europa-Swing-Scan"},
        {
            "start": "21:30",
            "end": "23:59",
            "reason": "Abendprognosen und Amerika/Krypto-Scan",
        },
    ]
    assert "-MultipleInstances IgnoreNew" in installer
    assert "$dailyTrigger.Repetition = $repetitionTemplate.Repetition" in installer
    assert "-ExecutionTimeLimit (New-TimeSpan -Seconds 0)" in installer


def test_project_campaign_allows_night_and_protects_all_production_runs() -> None:
    settings = load_campaign_config()

    assert not campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T00:30:00+02:00"), settings
    )
    assert not campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T08:59:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T09:00:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T10:30:00+02:00"), settings
    )
    assert not campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T11:30:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T15:45:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T18:15:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T20:00:00+02:00"), settings
    )
    assert campaign_is_protected_time(
        datetime.fromisoformat("2026-08-19T22:30:00+02:00"), settings
    )


def test_completed_job_releases_queue_for_next_valid_trigger() -> None:
    jobs = campaign_jobs(
        config(),
        ["AAA", "BBB"],
        now=datetime.fromisoformat("2026-08-19T02:00:00+02:00"),
    )
    state = {"completed": {}, "attempts": {}}
    first = next_campaign_job(jobs, state)
    state["completed"][first["job_key"]] = {"completed_at": "2026-08-19T02:10:00+02:00"}
    second = next_campaign_job(jobs, state)

    assert second is not None
    assert second["job_key"] != first["job_key"]
