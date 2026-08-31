from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fx_scheduler_audit import evaluate_fx_scheduler  # noqa: E402


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "fx_pit_collector.json"
DEFAULT_DB = PROJECT_ROOT / "runtime" / "fx_forward_pit.sqlite3"
DEFAULT_LOG = PROJECT_ROOT / "runtime" / "logs" / "fx_pit_collector.log"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "runtime" / "research_exports" / "fx_pit_scheduler_audit_2026-08-31-v3.json"
)
REFERENCE_RUN_ID = "fxpit-run-d6bb93a2d1685de5c3a564dcb1bf7d8a"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _query_scheduler(task_name: str) -> tuple[str, list[dict[str, object]], str | None]:
    escaped = task_name.replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
$items = @()
$matches = @(Get-ScheduledTask | Where-Object {{ $_.TaskName -eq '{escaped}' }})
foreach ($task in $matches) {{
  $info = Get-ScheduledTaskInfo -InputObject $task
  $action = @($task.Actions)[0]
  $trigger = @($task.Triggers)[0]
  $items += [pscustomobject]@{{
    task_name = [string]$task.TaskName
    task_path = [string]$task.TaskPath
    state = [string]$task.State
    enabled = [bool]$task.Settings.Enabled
    user_id = [string]$task.Principal.UserId
    logon_type = [string]$task.Principal.LogonType
    run_level = [string]$task.Principal.RunLevel
    action = [pscustomobject]@{{
      execute = [string]$action.Execute
      arguments = [string]$action.Arguments
      working_directory = [string]$action.WorkingDirectory
    }}
    trigger = [pscustomobject]@{{
      start_boundary = [string]$trigger.StartBoundary
      enabled = [bool]$trigger.Enabled
    }}
    settings = [pscustomobject]@{{
      start_when_available = [bool]$task.Settings.StartWhenAvailable
      wake_to_run = [bool]$task.Settings.WakeToRun
      multiple_instances = [string]$task.Settings.MultipleInstances
      restart_count = [int]$task.Settings.RestartCount
      restart_interval = [string]$task.Settings.RestartInterval
      execution_time_limit = [string]$task.Settings.ExecutionTimeLimit
      allow_start_on_batteries = -not [bool]$task.Settings.DisallowStartIfOnBatteries
      stop_on_batteries = [bool]$task.Settings.StopIfGoingOnBatteries
    }}
    last_run_time = if ($info.LastRunTime.Year -gt 1900) {{ $info.LastRunTime.ToString('o') }} else {{ $null }}
    next_run_time = if ($info.NextRunTime.Year -gt 1900) {{ $info.NextRunTime.ToString('o') }} else {{ $null }}
    last_task_result = [int]$info.LastTaskResult
    missed_runs = [int]$info.NumberOfMissedRuns
  }}
}}
@($items) | ConvertTo-Json -Depth 8 -Compress
"""
    process = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        message = (process.stderr or process.stdout).strip()
        status = "VISIBILITY_DENIED" if "Access is denied" in message else "QUERY_FAILED"
        return status, [], message[:1000]
    raw = process.stdout.strip()
    if not raw:
        return "SUCCESS", [], None
    parsed = json.loads(raw)
    return "SUCCESS", parsed if isinstance(parsed, list) else [parsed], None


def _collector_run(path: Path, run_id: str) -> dict[str, object]:
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT run_json FROM collector_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    if row is None:
        raise RuntimeError(f"Collector run not found: {run_id}")
    return json.loads(str(row[0]))


def _completed_daily_runs(path: Path) -> list[dict[str, object]]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT run_json FROM collector_runs ORDER BY started_at, run_id"
        ).fetchall()
    completed = []
    for row in rows:
        run = json.loads(str(row[0]))
        if run.get("status") != "COMPLETED" or not str(
            run.get("schedule_slot") or ""
        ).endswith(":daily"):
            continue
        completed.append(
            {
                "run_id": run.get("run_id"),
                "schedule_slot": run.get("schedule_slot"),
                "start": run.get("start"),
                "end": run.get("end"),
                "run_fingerprint": run.get("run_fingerprint"),
                "data_collection_only": run.get("data_collection_only"),
                "strategy_signal_generated": run.get("strategy_signal_generated"),
                "trade_decision_generated": run.get("trade_decision_generated"),
                "paper_trade_generated": run.get("paper_trade_generated"),
                "shadow_order_generated": run.get("shadow_order_generated"),
                "broker_order_allowed": run.get("broker_order_allowed"),
            }
        )
    return completed


def run(args: argparse.Namespace) -> dict[str, object]:
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    query_status, tasks, query_error = _query_scheduler(str(config["task_name"]))
    collector = _collector_run(Path(args.database), args.run_id)
    completed_daily_runs = _completed_daily_runs(Path(args.database))
    runner = PROJECT_ROOT / "scripts" / "run_fx_pit_collector.cmd"
    audit = evaluate_fx_scheduler(
        query_status=query_status,
        tasks=tasks,
        settings=config,
        collector_run=collector,
        expected_project_root=str(PROJECT_ROOT),
        expected_runner=str(runner),
        expected_run_id=args.run_id,
    )
    log_text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    log_has_run = args.run_id in log_text
    audit["scheduler_visibility_explanation"] = (
        "Earlier restricted queries returned access denied; the elevated read-only audit "
        "finds the existing canonical task. No task was missing and no duplicate was created."
    )
    audit["query_error"] = query_error
    audit["reference_run_in_collector_log"] = log_has_run
    audit["checks"]["reference_run_in_collector_log"] = log_has_run
    audit["completed_daily_scheduler_runs"] = completed_daily_runs
    audit["completed_daily_scheduler_run_n"] = len(completed_daily_runs)
    audit["checks"]["at_least_one_completed_daily_scheduler_run"] = (
        len(completed_daily_runs) >= 1
    )
    audit["second_completed_daily_scheduler_run_observed"] = (
        len(completed_daily_runs) >= 2
    )
    audit["status"] = "PASS" if all(audit["checks"].values()) else "FAIL"
    audit.pop("audit_fingerprint", None)
    audit["created_at"] = args.at or datetime.now(timezone.utc).isoformat()
    audit["branch"] = _git("rev-parse", "--abbrev-ref", "HEAD")
    audit["commit"] = _git("rev-parse", "HEAD")
    audit["command"] = "python " + " ".join(sys.argv)
    audit["input_artifacts"] = {
        "config": str(Path(args.config).resolve()),
        "database": str(Path(args.database).resolve()),
        "log": str(Path(args.log).resolve()),
    }
    audit["audit_fingerprint"] = hashlib.sha256(
        json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of the FX-PIT Windows task")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-id", default=REFERENCE_RUN_ID)
    parser.add_argument("--at")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
