from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_contract import load_development_contract  # noqa: E402
from multi_asset_development_execution import (  # noqa: E402
    build_development_universe,
    build_work_plan,
)
from multi_asset_development_readiness_v2 import (  # noqa: E402
    evaluate_multi_asset_development_readiness_v2,
)
from multi_asset_development_runner import RUNNER_VERSION, _paths  # noqa: E402
from multi_asset_development_readiness import READY_STATUS  # noqa: E402
from multi_asset_discovery_v1 import (  # noqa: E402
    file_sha256,
    load_discovery_contract,
    verify_contract_freeze,
)


EXPORTS = PROJECT_ROOT / "runtime" / "research_exports"
EXPECTED_PROTECTED_HASHES = {
    "runtime/fx_historical_pit.sqlite3": "f0b7af71cbf9d527027a7a095cc562116e68aed7a0bdc37465d818b3259ca73f",
    "runtime/fx_forward_pit.sqlite3": "1f97a80bd6376036ebe5e3dcbd6ecc3500f1139937d81da8088efbde0a85c5c7",
    "runtime/research_identity_registry.sqlite3": "3e09c776f23b690b4c7a52600bbb67e01fad91c29243ea4d31f2a8263f051067",
    "config/multi_asset_discovery_v1.json": "a34aca9c5b11679d133b264bf69983953bde8f4e5f666c18535f02f52203cecc",
}


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _quick_check(path: Path) -> str:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return str(connection.execute("PRAGMA quick_check").fetchone()[0])


def _scheduler_preflight(task_name: str) -> dict[str, object]:
    command = (
        "Get-ScheduledTask -ErrorAction SilentlyContinue | "
        f"Where-Object {{$_.TaskName -eq '{task_name}'}} | "
        "Select-Object -ExpandProperty TaskName"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    matches = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    installer = PROJECT_ROOT / "scripts" / "install_multi_asset_development_task.ps1"
    runner = PROJECT_ROOT / "scripts" / "run_multi_asset_development.cmd"
    installer_text = installer.read_text(encoding="utf-8") if installer.exists() else ""
    logon_type = (
        "Interactive" if "-LogonType Interactive" in installer_text else "UNKNOWN"
    )
    return {
        "status": (
            "PASS"
            if completed.returncode == 0
            and len(matches) <= 1
            and installer.exists()
            and runner.exists()
            and logon_type == "Interactive"
            else "FAIL"
        ),
        "query_return_code": completed.returncode,
        "canonical_task_count": len(matches),
        "installer_exists": installer.exists(),
        "runner_exists": runner.exists(),
        "multiple_instances": "IgnoreNew",
        "logon_type": logon_type,
        "start_when_available": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at")
    args = parser.parse_args()
    development = load_development_contract()
    paths = _paths(development)
    artifact = _json(paths["contract_artifact"])
    diff = _json(paths["contract_diff"])
    universe = build_development_universe()
    work_plan = build_work_plan(universe)
    execution = dict(development["development_execution"])
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    runner_preflight = {
        "status": "PASS",
        "runner_version": RUNNER_VERSION,
        "asset_count": universe["asset_count"],
        "asset_class_counts": universe["asset_class_counts"],
        "universe_fingerprint": universe["universe_fingerprint"],
        "work_plan_fingerprint": work_plan["work_plan_fingerprint"],
        "total_planned_work_units": work_plan["total_planned_work_units"],
        "development_only": work_plan["development_only"],
        "worker_count": execution["worker_count"],
        "sqlite_writer_count": execution["sqlite_writer_count"],
        "contract_artifact_matches_head": dict(artifact.get("git") or {}).get(
            "commit"
        )
        == current_head,
    }
    protected_unchanged = all(
        file_sha256(PROJECT_ROOT / relative).lower() == expected
        for relative, expected in EXPECTED_PROTECTED_HASHES.items()
    )
    parent = load_discovery_contract()
    freeze = _json(
        EXPORTS
        / "multi_asset_discovery_v1_contract_freeze_2026-09-01-v1-implementation-r5.json"
    )
    result = evaluate_multi_asset_development_readiness_v2(
        parent_contract=parent,
        expected_parent_contract_fingerprint=(
            "68994e462f90e2a4f1ad4adbdc858cc43fb0ddb85b0c2662d0f647e1dfa6c05a"
        ),
        freeze_valid=verify_contract_freeze(freeze)
        and freeze.get("freeze_fingerprint")
        == dict(development.get("parent_contract") or {}).get(
            "freeze_fingerprint"
        ),
        pilot=_json(
            EXPORTS
            / "multi_asset_discovery_v1_integrity_pilot_2026-09-01-v1-authoritative-r5.json"
        ),
        fx_remediation=_json(
            EXPORTS / "fx_historical_pit_remediation_2026-09-01-v2.json"
        ),
        historical_dependency=_json(
            EXPORTS / "historical_dependency_policy_2026-09-01-v1.json"
        ),
        identity_precheck=_json(
            EXPORTS / "multi_asset_final_precheck_2026-08-31-v1.json"
        ),
        fx_observer=_json(
            EXPORTS / "fx_pit_scheduler_audit_2026-08-31-v3.json"
        ),
        database_integrity={
            "fx_active_v2": _quick_check(
                PROJECT_ROOT / "runtime" / "fx_historical_pit_2026-09-01-v2.sqlite3"
            ),
            "fx_forward": _quick_check(
                PROJECT_ROOT / "runtime" / "fx_forward_pit.sqlite3"
            ),
        },
        protected_sources_unchanged=protected_unchanged,
        development_contract_artifact=artifact,
        contract_diff=diff,
        runner_preflight=runner_preflight,
        scheduler_preflight=_scheduler_preflight(
            str(execution["scheduler_task_name"])
        ),
    )
    result.update(
        {
            "created_at": args.at or datetime.now(timezone.utc).isoformat(),
            "git": {
                "branch": subprocess.check_output(
                    ["git", "branch", "--show-current"],
                    cwd=PROJECT_ROOT,
                    text=True,
                    encoding="utf-8",
                ).strip(),
                "commit": current_head,
            },
            "runner_preflight": runner_preflight,
        }
    )
    result.pop("gate_fingerprint", None)
    from multi_asset_development_readiness import fingerprint

    result["gate_fingerprint"] = fingerprint(result)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    paths["readiness"].parent.mkdir(parents=True, exist_ok=True)
    if paths["readiness"].exists():
        if _json(paths["readiness"]) != result:
            raise RuntimeError(f"Append-only-Artefakt weicht ab: {paths['readiness']}")
    else:
        paths["readiness"].write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["status"] == READY_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
