from __future__ import annotations

from fx_scheduler_audit import FX_SCHEDULER_AUDIT_VERSION, evaluate_fx_scheduler


RUN_ID = "fxpit-run-test"


def _settings() -> dict[str, object]:
    return {
        "task_name": "InvestmentAssistant-FX-PIT-Observer",
        "local_run_time": "21:45",
        "safety": {
            "strategy_signal_allowed": False,
            "trade_decision_allowed": False,
            "paper_trade_allowed": False,
            "shadow_order_allowed": False,
            "broker_order_allowed": False,
        },
    }


def _task() -> dict[str, object]:
    return {
        "task_name": "InvestmentAssistant-FX-PIT-Observer",
        "task_path": "\\",
        "state": "Ready",
        "enabled": True,
        "action": {
            "execute": "cmd.exe",
            "arguments": '/d /c "C:\\investment-assistent\\scripts\\run_fx_pit_collector.cmd"',
            "working_directory": "C:\\investment-assistent",
        },
        "trigger": {"start_boundary": "2026-08-29T21:45:00+02:00"},
        "settings": {
            "start_when_available": True,
            "wake_to_run": False,
            "multiple_instances": "IgnoreNew",
            "restart_count": 3,
        },
        "last_run_time": "2026-08-29T21:45:00+02:00",
        "last_task_result": 0,
    }


def _run() -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "status": "COMPLETED",
        "data_collection_only": True,
        "strategy_signal_generated": False,
        "trade_decision_generated": False,
        "paper_trade_generated": False,
        "shadow_order_generated": False,
        "broker_accessed": False,
        "broker_order_allowed": False,
    }


def _evaluate(tasks, query_status="SUCCESS"):
    return evaluate_fx_scheduler(
        query_status=query_status,
        tasks=tasks,
        settings=_settings(),
        collector_run=_run(),
        expected_project_root="C:\\investment-assistent",
        expected_runner="C:\\investment-assistent\\scripts\\run_fx_pit_collector.cmd",
        expected_run_id=RUN_ID,
    )


def test_exactly_one_safe_canonical_scheduler_passes() -> None:
    result = _evaluate([_task()])
    assert result["status"] == "PASS"
    assert result["version"] == FX_SCHEDULER_AUDIT_VERSION
    assert result["matching_task_n"] == 1
    assert result["duplicate_scheduler_created"] is False
    assert result["checks"]["historical_planned_run_succeeded"] is True
    assert result["checks"]["run_has_no_trade_outputs"] is True


def test_duplicate_or_invisible_scheduler_fails_instead_of_creating_another() -> None:
    duplicate = _evaluate([_task(), _task()])
    invisible = _evaluate([], query_status="VISIBILITY_DENIED")
    assert duplicate["status"] == "FAIL"
    assert duplicate["checks"]["exactly_one_canonical_task"] is False
    assert invisible["status"] == "FAIL"
    assert invisible["duplicate_scheduler_created"] is False


def test_trade_output_or_wrong_wake_setting_fails_closed() -> None:
    task = _task()
    task["settings"]["wake_to_run"] = True
    result = _evaluate([task])
    assert result["status"] == "FAIL"
    assert result["checks"]["wake_to_run_explicitly_false"] is False
