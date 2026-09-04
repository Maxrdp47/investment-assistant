from __future__ import annotations

import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import multi_asset_development_runner as runner
from multi_asset_development_contract import load_development_contract
from swing_walk_forward_campaign import (
    campaign_is_protected_time,
    load_campaign_config,
)


BERLIN = ZoneInfo("Europe/Berlin")


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=BERLIN)


def test_development_cannot_start_before_explicit_midnight_boundary() -> None:
    contract = load_development_contract()

    assert runner.development_time_guard(
        contract, now=_at("2026-09-01T23:59:59")
    ) == (
        False,
        "DEVELOPMENT_NOT_BEFORE:2026-09-02T00:00:00+02:00",
    )
    assert runner.development_time_guard(
        contract, now=_at("2026-09-02T00:00:00")
    ) == (True, "CLEAR")


def test_forward_only_windows_do_not_block_current_development(
    monkeypatch,
) -> None:
    contract = load_development_contract()
    monkeypatch.setattr(runner, "campaign_is_protected_time", lambda now, config: True)

    assert runner.development_time_guard(
        contract, now=_at("2026-09-02T22:00:00")
    ) == (True, "CLEAR")


def test_forward_context_retains_its_protected_windows(monkeypatch) -> None:
    contract = copy.deepcopy(load_development_contract())
    contract["development_execution"][
        "forward_only_time_windows_apply_to_development"
    ] = True
    monkeypatch.setattr(runner, "campaign_is_protected_time", lambda now, config: True)

    assert runner.development_time_guard(
        contract, now=_at("2026-09-02T22:00:00")
    ) == (False, "FORWARD_ONLY_PROTECTED_WINDOW")
    campaign = load_campaign_config()
    assert campaign_is_protected_time(_at("2026-09-02T22:00:00"), campaign)


def test_active_production_process_lock_still_blocks_development(
    monkeypatch,
) -> None:
    contract = load_development_contract()

    def _active_jobs(config, *, project_root):
        assert project_root == runner.PROJECT_ROOT
        return ["Swing-Live-/Forward-Scan"]

    monkeypatch.setattr(
        runner,
        "campaign_active_production_jobs",
        _active_jobs,
    )

    assert runner._production_clear(
        contract, now=_at("2026-09-02T00:00:00")
    ) == (False, "ACTIVE_PRODUCTION_LOCK:Swing-Live-/Forward-Scan")


def test_trade_lifecycle_and_unseen_stages_remain_closed() -> None:
    contract = load_development_contract()
    execution = contract["development_execution"]

    assert execution["validation_access_allowed"] is False
    assert execution["holdout_access_allowed"] is False
    assert execution["external_access_allowed"] is False
    assert execution["true_forward_access_allowed"] is False
    assert execution["paper_output_allowed"] is False
    assert execution["shadow_output_allowed"] is False
    assert execution["broker_output_allowed"] is False
    assert execution["automatic_orders_allowed"] is False
    assert all(value is False for value in contract["lifecycle"].values())


def test_all_canonical_terminal_states_are_never_reported_as_running() -> None:
    for status in (
        "COMPLETED",
        "COMPLETED_WITH_FAILURES",
        "FAILED",
        "CANCELLED",
        "ABORTED",
    ):
        assert runner._runner_final_status(status) != runner.RUNNING_STATUS


def test_terminal_run_returns_without_new_event_or_heavy_audit(
    monkeypatch, tmp_path
) -> None:
    status = {
        "run_id": "terminal-run",
        "status": "COMPLETED_WITH_FAILURES",
        "pending": 0,
        "active": 0,
        "failed": 1,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"run_id":"terminal-run"}', encoding="utf-8")
    control_path = tmp_path / "control.sqlite3"
    control_path.touch()
    monkeypatch.setattr(runner, "load_development_contract", lambda: {})
    monkeypatch.setattr(
        runner,
        "_paths",
        lambda contract: {
            "lock": tmp_path / "terminal.lock",
            "control": control_path,
            "log": tmp_path / "terminal.log",
            "manifest": manifest_path,
        },
    )
    monkeypatch.setattr(
        runner,
        "prepare_canonical_run",
        lambda: ({"run_id": "terminal-run"}, {"assets": []}, {}),
    )
    monkeypatch.setattr(runner, "checkpoint_status", lambda **kwargs: dict(status))
    monkeypatch.setattr(
        runner,
        "resume_interrupted_units",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not resume")),
    )
    monkeypatch.setattr(
        runner,
        "append_run_event",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not append")),
    )
    monkeypatch.setattr(
        runner,
        "audit_development_stores",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not audit")),
    )

    result = runner.run_development()

    assert result["status"] == "COMPLETED_WITH_FAILURES"
    assert result["final_status"] == runner.COMPLETE_STATUS
    assert result["processed_this_invocation"] == 0
    assert result["store_audit"] == {
        "skipped": True,
        "reason": "TERMINAL_RUN_IS_IMMUTABLE",
    }
