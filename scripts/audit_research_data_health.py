from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_data_health import (  # noqa: E402
    audit_research_data_health,
    render_gap_markdown,
    render_health_markdown,
)


TASK_NAMES = (
    "InvestmentAssistant-FX-PIT-Observer",
    "InvestmentAssistantDailyForecasts",
)


def _scheduler_snapshot() -> tuple[str, list[dict[str, object]], str | None]:
    quoted = ",".join("'" + name.replace("'", "''") + "'" for name in TASK_NAMES)
    script = f"""
$ErrorActionPreference='Stop'
$names=@({quoted})
$items=@()
foreach ($task in @(Get-ScheduledTask | Where-Object {{ $names -contains $_.TaskName }})) {{
  $info=Get-ScheduledTaskInfo -InputObject $task
  $items += [pscustomobject]@{{
    task_name=[string]$task.TaskName
    state=[string]$task.State
    enabled=[bool]$task.Settings.Enabled
    last_run_time=if($info.LastRunTime.Year -gt 1900){{$info.LastRunTime.ToString('o')}}else{{$null}}
    next_run_time=if($info.NextRunTime.Year -gt 1900){{$info.NextRunTime.ToString('o')}}else{{$null}}
    last_task_result=[int]$info.LastTaskResult
    start_when_available=[bool]$task.Settings.StartWhenAvailable
    multiple_instances=[string]$task.Settings.MultipleInstances
  }}
}}
@($items) | ConvertTo-Json -Depth 5 -Compress
"""
    process = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        message = (process.stderr or process.stdout).strip()
        status = "VISIBILITY_DENIED" if "Access is denied" in message else "QUERY_FAILED"
        return status, [], message[:1000]
    raw = process.stdout.strip()
    if not raw:
        return "SUCCESS", [], None
    parsed = json.loads(raw)
    return "SUCCESS", parsed if isinstance(parsed, list) else [parsed], None


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only A-M research data health audit")
    parser.add_argument("--as-of", help="Timezone-aware ISO timestamp")
    parser.add_argument("--scheduler-json", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--health-markdown", type=Path)
    parser.add_argument("--gap-markdown", type=Path)
    args = parser.parse_args()

    as_of = args.as_of or datetime.now(timezone.utc).isoformat()
    day = str(as_of)[:10]
    if args.scheduler_json:
        snapshot = json.loads(args.scheduler_json.read_text(encoding="utf-8"))
        query_status = str(snapshot.get("query_status") or "SUPPLIED")
        tasks = list(snapshot.get("tasks") or [])
        query_error = snapshot.get("query_error")
    else:
        query_status, tasks, query_error = _scheduler_snapshot()

    payload = audit_research_data_health(
        PROJECT_ROOT,
        as_of=as_of,
        scheduler_tasks=tasks,
        scheduler_query_status=query_status,
    )
    payload["scheduler_query_error"] = query_error
    payload["branch"] = subprocess.run(
        ["git", "branch", "--show-current"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    payload["commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()

    json_output = args.json_output or (
        PROJECT_ROOT / "runtime" / "research_exports" / f"research_data_health_and_coverage_{day}.json"
    )
    health_output = args.health_markdown or (
        PROJECT_ROOT / f"RESEARCH_DATA_HEALTH_AND_COVERAGE_{day}.md"
    )
    gap_output = args.gap_markdown or (
        PROJECT_ROOT / f"DATA_COLLECTION_GAP_REPORT_{day}.md"
    )
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    health_output.write_text(render_health_markdown(payload), encoding="utf-8")
    gap_output.write_text(render_gap_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "status": "completed",
        "final_status": payload["final_status"],
        "json_output": str(json_output),
        "health_markdown": str(health_output),
        "gap_markdown": str(gap_output),
        "report_fingerprint": payload["report_fingerprint"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
