from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock  # noqa: E402
from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_walk_forward import (  # noqa: E402
    DEFAULT_SWING_WALK_FORWARD_DB_PATH,
    refresh_swing_walk_forward_forward_links,
    swing_walk_forward_store_audit,
)
from swing_forward_store import DEFAULT_SWING_FORWARD_DB_PATH  # noqa: E402
from swing_research_dataset import (  # noqa: E402
    load_research_dataset_manifest,
    research_dataset_manifest_path,
)
from swing_walk_forward_campaign import (  # noqa: E402
    DEFAULT_CAMPAIGN_CONFIG_PATH,
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_RESEARCH_LOCK_PATH,
    campaign_active_production_jobs,
    campaign_is_protected_time,
    campaign_jobs,
    campaign_status,
    campaign_week_epoch,
    load_campaign_config,
    load_campaign_state,
    next_campaign_job,
    save_campaign_state,
)


DEFAULT_RESEARCH_DATASET_ROOT = PROJECT_ROOT / "runtime" / "swing_walk_forward_datasets"


def _dataset_root(config: dict) -> Path:
    configured = Path(str(config.get("dataset_root") or DEFAULT_RESEARCH_DATASET_ROOT))
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


def _dataset_epoch_for_job(job: dict, config: dict) -> str:
    version = str(config.get("dataset_epoch_version") or config["version"])
    recurrence = str((job.get("contract") or {}).get("recurrence") or "once")
    epoch = "fixed" if recurrence == "once" else str(job["epoch"])
    return f"{version}|{epoch}"


def _dataset_scopes_for_job(job: dict, config: dict) -> list[tuple[str, str | None]]:
    recurrence = str((job.get("contract") or {}).get("recurrence") or "once")
    contracts = [
        *list(config.get("contracts") or []),
        *list(config.get("challenger_contracts") or []),
    ]
    scopes = {
        (
            str(contract["start"]),
            str(contract["end"]) if contract.get("end") else None,
        )
        for contract in contracts
        if str(contract.get("recurrence") or "once") == recurrence
    }
    return sorted(scopes, key=lambda scope: (scope[0], scope[1] or ""))


def _dataset_prepare_command(
    job: dict,
    config: dict,
    *,
    universe_path: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_swing_walk_forward.py"),
        "--prepare-dataset",
        "--dataset-root",
        str(_dataset_root(config)),
        "--dataset-epoch",
        _dataset_epoch_for_job(job, config),
        "--cache-path",
        str(PROJECT_ROOT / "runtime" / "swing_walk_forward_cache"),
        "--batch-size",
        str(config["batch_size"]),
    ]
    for start, end in _dataset_scopes_for_job(job, config):
        command.extend(["--dataset-scope", f"{start}|{end or 'latest'}"])
    if universe_path is not None:
        command.extend(["--universe-path", str(universe_path)])
    return command


def _command_for_job(
    job: dict,
    config: dict,
    *,
    database: Path | None = None,
    universe_path: Path | None = None,
    dataset_epoch: str | None = None,
    dataset_fingerprint: str | None = None,
) -> list[str]:
    contract = dict(job["contract"])
    profiles = list(contract.get("profiles") or [contract["profile"]])
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_swing_walk_forward.py"),
        *job["tickers"],
        "--start",
        str(contract["start"]),
        "--development-end",
        str(contract["development_end"]),
        "--validation-end",
        str(contract["validation_end"]),
        "--future-sessions",
        str(contract["future_sessions"]),
        "--step-sessions",
        str(contract["step_sessions"]),
        "--maximum-cases-per-symbol",
        str(contract["maximum_cases_per_symbol"]),
        "--sampling-mode",
        str(contract["sampling_mode"]),
        "--selection-round",
        str(contract.get("selection_round", 0)),
        "--selection-round-role",
        str(contract.get("selection_round_role", "monitoring" if contract["recurrence"] == "weekly" else "exploration")),
        "--batch-size",
        str(config["batch_size"]),
        "--analysis-workers",
        str(config["analysis_workers"]),
        "--analysis-executor",
        str(config["analysis_executor"]),
        "--profiles",
        *(str(profile) for profile in profiles),
    ]
    if dataset_epoch is not None:
        if not dataset_fingerprint:
            raise ValueError("Ein Kampagnenjob mit Research-Epoch benötigt den erwarteten Dataset-Fingerprint.")
        command.extend(
            [
                "--dataset-root",
                str(_dataset_root(config)),
                "--dataset-epoch",
                str(dataset_epoch),
                "--expected-dataset-fingerprint",
                str(dataset_fingerprint),
            ]
        )
    if universe_path is not None:
        command.extend(["--universe-path", str(universe_path)])
    profile_versions = dict(
        contract.get("profile_versions")
        or config.get("locked_profile_versions")
        or {}
    )
    for profile_name, profile_version in sorted(profile_versions.items()):
        command.extend(["--expected-profile-version", f"{profile_name}={profile_version}"])
    command.append("--skip-final-report")
    if contract.get("end"):
        command.extend(["--end", str(contract["end"])])
    if database is not None:
        command.extend(["--database", str(database)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotierende, überlappungsgeschützte Swing-Forschungskampagne.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CAMPAIGN_CONFIG_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--forward-database", type=Path, default=DEFAULT_SWING_FORWARD_DB_PATH)
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument("--ignore-protected-window", action="store_true")
    args = parser.parse_args()

    config = load_campaign_config(args.config)
    state = load_campaign_state(args.state)
    universe = load_swing_universe(args.universe_path)
    if universe.errors:
        raise RuntimeError("; ".join(universe.errors))
    tickers = [asset.ticker for asset in universe.assets if asset.active]
    now = datetime.now().astimezone()
    current_week = campaign_week_epoch(now)
    active_week = str(state.get("active_week_epoch") or current_week)
    jobs = campaign_jobs(config, tickers, now=now, weekly_epoch=active_week)
    if next_campaign_job(jobs, state) is None and active_week != current_week:
        active_week = current_week
        state["active_week_epoch"] = active_week
        jobs = campaign_jobs(config, tickers, now=now, weekly_epoch=active_week)
    status = campaign_status(jobs, state)
    if args.status_only:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    if campaign_is_protected_time(now, config) and not args.ignore_protected_window:
        print(json.dumps({"campaign_skipped": "protected_window", "status": status}, ensure_ascii=False))
        return 0
    # Give a simultaneously resumed production task first opportunity to own
    # its runtime lock before research probes it. Normal five-minute starts pay
    # only this bounded grace period; no research state is changed meanwhile.
    production_grace_seconds = max(
        0,
        min(int(config.get("production_priority_grace_seconds") or 0), 60),
    )
    if production_grace_seconds:
        time.sleep(production_grace_seconds)
    active_production = campaign_active_production_jobs(config, project_root=PROJECT_ROOT)
    if active_production:
        print(
            json.dumps(
                {
                    "campaign_skipped": "protected_production_active",
                    "active_production": active_production,
                    "status": status,
                },
                ensure_ascii=False,
            )
        )
        return 0
    job = next_campaign_job(jobs, state)
    if job is None:
        print(json.dumps({"campaign": "up_to_date", "status": status}, ensure_ascii=False))
        return 0

    key = str(job["job_key"])
    try:
        with SwingRunLock(DEFAULT_RESEARCH_LOCK_PATH):
            # Re-read after acquiring the global lock. A predecessor may have
            # completed between the optimistic queue read and lock acquisition;
            # using its latest atomic state prevents a duplicate shard start.
            state = load_campaign_state(args.state)
            active_week = str(state.get("active_week_epoch") or current_week)
            jobs = campaign_jobs(config, tickers, now=now, weekly_epoch=active_week)
            if next_campaign_job(jobs, state) is None and active_week != current_week:
                active_week = current_week
                state["active_week_epoch"] = active_week
                jobs = campaign_jobs(config, tickers, now=now, weekly_epoch=active_week)
            job = next_campaign_job(jobs, state)
            if job is None:
                print(
                    json.dumps(
                        {"campaign": "up_to_date", "status": campaign_status(jobs, state)},
                        ensure_ascii=False,
                    )
                )
                return 0
            key = str(job["job_key"])
            active_production = campaign_active_production_jobs(
                config,
                project_root=PROJECT_ROOT,
            )
            if active_production:
                print(
                    json.dumps(
                        {
                            "campaign_skipped": "protected_production_active",
                            "active_production": active_production,
                            "status": campaign_status(jobs, state),
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            attempts = dict(state.get("attempts") or {})
            state["active_week_epoch"] = active_week
            attempts[key] = int(attempts.get(key, 0)) + 1
            state["attempts"] = attempts
            dataset_epoch = _dataset_epoch_for_job(job, config)
            state["last_event"] = {
                "type": "dataset_preparing",
                "job_key": key,
                "at": now.isoformat(),
                "attempt": attempts[key],
                "dataset_epoch": dataset_epoch,
            }
            save_campaign_state(state, args.state)
            prepared = subprocess.run(
                _dataset_prepare_command(
                    job,
                    config,
                    universe_path=args.universe_path,
                ),
                cwd=PROJECT_ROOT,
                check=False,
            )
            if prepared.returncode != 0:
                state["last_event"] = {
                    "type": "failed",
                    "phase": "dataset_prepare",
                    "job_key": key,
                    "at": datetime.now().astimezone().isoformat(),
                    "return_code": prepared.returncode,
                    "dataset_epoch": dataset_epoch,
                }
                save_campaign_state(state, args.state)
                return int(prepared.returncode)
            manifest = load_research_dataset_manifest(
                research_dataset_manifest_path(_dataset_root(config), dataset_epoch)
            )
            dataset_fingerprint = str(manifest["dataset_fingerprint"])
            state["last_event"] = {
                "type": "started",
                "phase": "analysis",
                "job_key": key,
                "at": datetime.now().astimezone().isoformat(),
                "attempt": attempts[key],
                "dataset_epoch": dataset_epoch,
                "dataset_fingerprint": dataset_fingerprint,
            }
            save_campaign_state(state, args.state)
            print(
                json.dumps(
                    {
                        "campaign_job_started": key,
                        "contract": job["contract"]["id"],
                        "shard": f"{job['shard_index'] + 1}/{job['shard_count']}",
                        "assets": len(job["tickers"]),
                        "dataset_epoch": dataset_epoch,
                        "dataset_fingerprint": dataset_fingerprint,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            completed = subprocess.run(
                _command_for_job(
                    job,
                    config,
                    database=args.database,
                    universe_path=args.universe_path,
                    dataset_epoch=dataset_epoch,
                    dataset_fingerprint=dataset_fingerprint,
                ),
                cwd=PROJECT_ROOT,
                check=False,
            )
            if completed.returncode != 0:
                state["last_event"] = {
                    "type": "failed",
                    "phase": "analysis",
                    "job_key": key,
                    "at": datetime.now().astimezone().isoformat(),
                    "return_code": completed.returncode,
                    "dataset_epoch": dataset_epoch,
                    "dataset_fingerprint": dataset_fingerprint,
                }
                save_campaign_state(state, args.state)
                return int(completed.returncode)
            linkage = refresh_swing_walk_forward_forward_links(
                args.database or DEFAULT_SWING_WALK_FORWARD_DB_PATH,
                args.forward_database,
            )
            print(json.dumps({"historical_real_forward_linkage": linkage}, ensure_ascii=False), flush=True)
            if int(job["shard_index"]) == int(job["shard_count"]) - 1:
                audit = swing_walk_forward_store_audit(args.database or DEFAULT_SWING_WALK_FORWARD_DB_PATH)
                print(json.dumps({"campaign_contract_audit": audit}, ensure_ascii=False), flush=True)
                if audit.get("status") != "ok":
                    state["last_event"] = {
                        "type": "audit_failed",
                        "job_key": key,
                        "at": datetime.now().astimezone().isoformat(),
                    }
                    save_campaign_state(state, args.state)
                    return 2
            completed_jobs = dict(state.get("completed") or {})
            completed_jobs[key] = {
                "completed_at": datetime.now().astimezone().isoformat(),
                "contract": job["contract"]["id"],
                "shard_index": job["shard_index"],
                "assets": len(job["tickers"]),
                "dataset_epoch": dataset_epoch,
                "dataset_fingerprint": dataset_fingerprint,
            }
            state["completed"] = completed_jobs
            state["last_event"] = {
                "type": "completed",
                "job_key": key,
                "at": datetime.now().astimezone().isoformat(),
                "dataset_epoch": dataset_epoch,
                "dataset_fingerprint": dataset_fingerprint,
            }
            save_campaign_state(state, args.state)
    except SwingRunAlreadyActiveError:
        print(json.dumps({"campaign_skipped": "another_research_run_active", "job_key": key}, ensure_ascii=False))
        return 0

    print(json.dumps({"campaign_job_completed": key, "status": campaign_status(jobs, state)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
