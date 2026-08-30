from __future__ import annotations

"""Pure evaluation of the canonical Windows FX-PIT observer scheduler."""

import hashlib
import json
from datetime import datetime
from typing import Mapping, Sequence


FX_SCHEDULER_AUDIT_VERSION = "fx-pit-scheduler-audit-2026.08.30-v1"


def _fingerprint(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _norm_path(value: object) -> str:
    return str(value or "").strip().replace("/", "\\").rstrip("\\").casefold()


def evaluate_fx_scheduler(
    *,
    query_status: str,
    tasks: Sequence[Mapping[str, object]],
    settings: Mapping[str, object],
    collector_run: Mapping[str, object] | None,
    expected_project_root: str,
    expected_runner: str,
    expected_run_id: str,
) -> dict[str, object]:
    task_name = str(settings.get("task_name") or "")
    matching = [task for task in tasks if str(task.get("task_name") or "") == task_name]
    task = dict(matching[0]) if len(matching) == 1 else {}
    action = dict(task.get("action") or {})
    scheduler_settings = dict(task.get("settings") or {})
    trigger = dict(task.get("trigger") or {})
    safety = dict(settings.get("safety") or {})
    expected_time = str(settings.get("local_run_time") or "")
    trigger_start = str(trigger.get("start_boundary") or "")
    actual_time = None
    if trigger_start:
        try:
            actual_time = datetime.fromisoformat(trigger_start).strftime("%H:%M")
        except ValueError:
            actual_time = None
    collector = dict(collector_run or {})
    run_safety = all(
        collector.get(field) is False
        for field in (
            "strategy_signal_generated",
            "trade_decision_generated",
            "paper_trade_generated",
            "shadow_order_generated",
            "broker_accessed",
            "broker_order_allowed",
        )
    )
    config_safety = all(value is False for value in safety.values())
    checks = {
        "scheduler_query_succeeded": query_status == "SUCCESS",
        "exactly_one_canonical_task": len(matching) == 1,
        "task_enabled_and_ready": bool(task.get("enabled")) and str(task.get("state")) in {"Ready", "Running"},
        "canonical_command": str(action.get("execute") or "").casefold() == "cmd.exe"
        and _norm_path(expected_runner) in str(action.get("arguments") or "").casefold(),
        "canonical_working_directory": _norm_path(action.get("working_directory"))
        == _norm_path(expected_project_root),
        "daily_trigger_matches": actual_time == expected_time,
        "start_when_available": scheduler_settings.get("start_when_available") is True,
        "wake_to_run_explicitly_false": scheduler_settings.get("wake_to_run") is False,
        "single_instance": str(scheduler_settings.get("multiple_instances")) == "IgnoreNew",
        "retry_policy_present": int(scheduler_settings.get("restart_count") or 0) == 3,
        "historical_planned_run_succeeded": int(task.get("last_task_result", -1)) == 0
        and bool(task.get("last_run_time")),
        "collector_run_attributed": collector.get("run_id") == expected_run_id
        and collector.get("status") == "COMPLETED",
        "collector_is_data_only": collector.get("data_collection_only") is True,
        "config_has_no_trade_outputs": config_safety,
        "run_has_no_trade_outputs": run_safety,
    }
    payload = {
        "version": FX_SCHEDULER_AUDIT_VERSION,
        "query_status": query_status,
        "canonical_task_name": task_name,
        "matching_task_n": len(matching),
        "task": task,
        "collector_run_id": collector.get("run_id"),
        "collector_run_status": collector.get("status"),
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "duplicate_scheduler_created": False,
        "strategy_signal_allowed": False,
        "trade_decision_allowed": False,
        "paper_trade_allowed": False,
        "shadow_order_allowed": False,
        "broker_order_allowed": False,
    }
    payload["audit_fingerprint"] = _fingerprint(payload)
    return payload
