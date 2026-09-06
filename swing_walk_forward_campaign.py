from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Mapping, Sequence

from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward import TECHNICAL_CHALLENGER_PROFILE_NAMES


CAMPAIGN_STATE_VERSION = "swing-walk-forward-campaign-state-2026.08.17-v1"
DEFAULT_CAMPAIGN_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "swing_walk_forward_campaign.json"
DEFAULT_CAMPAIGN_STATE_PATH = Path(__file__).resolve().parent / "runtime" / "swing_walk_forward_campaign_state.json"
DEFAULT_RESEARCH_LOCK_PATH = Path(__file__).resolve().parent / "runtime" / "swing_walk_forward_research.lock"


def load_campaign_config(path: Path = DEFAULT_CAMPAIGN_CONFIG_PATH) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload.get("version"):
        raise ValueError("Die Walk-Forward-Kampagnenkonfiguration ist ungültig.")
    repeat_minutes = int(payload.get("repeat_minutes") or 0)
    analysis_workers = int(payload.get("analysis_workers") or 0)
    if repeat_minutes < 5:
        raise ValueError("Der Kampagnentrigger darf nicht häufiger als alle fünf Minuten laufen.")
    if analysis_workers < 1 or analysis_workers > 8:
        raise ValueError("Die Kampagne benötigt zwischen einem und acht Analyseworkern.")
    if payload.get("analysis_executor") not in {"threads", "processes"}:
        raise ValueError("Unbekannter paralleler Analysemodus in der Kampagne.")
    if not str(payload.get("dataset_epoch_version") or "").strip():
        raise ValueError("Die Kampagne benötigt eine explizite Version des eingefrorenen Datensatzes.")
    try:
        _parse_clock(payload.get("start_time"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Die Kampagne benötigt eine gültige tägliche Startzeit.") from exc
    duration_hours = int(payload.get("duration_hours") or 0)
    if duration_hours < 1 or duration_hours > 24:
        raise ValueError("Der tägliche Kampagnentrigger muss zwischen einer und 24 Stunden aktiv sein.")
    if campaign_start_buffer_minutes(payload) < 1:
        raise ValueError("Die Kampagne benötigt einen positiven Startpuffer vor Produktionsläufen.")
    production_grace_seconds = int(payload.get("production_priority_grace_seconds") or 0)
    if production_grace_seconds < 0 or production_grace_seconds > 60:
        raise ValueError("Die Produktions-Prioritätsfrist muss zwischen null und 60 Sekunden liegen.")
    for window in payload.get("protected_windows") or []:
        try:
            _parse_clock(window["start"])
            _parse_clock(window["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Ungültiges Schutzfenster in der Kampagnenkonfiguration.") from exc
    for runtime_lock in payload.get("protected_runtime_locks") or []:
        if not str(runtime_lock.get("name") or "").strip() or not str(
            runtime_lock.get("path") or ""
        ).strip():
            raise ValueError("Jeder geschützte Produktions-Lock benötigt Name und Pfad.")
    shard_count = int(payload.get("shard_count") or 0)
    contracts = [
        *list(payload.get("contracts") or []),
        *list(payload.get("challenger_contracts") or []),
    ]
    if shard_count < 1 or not contracts:
        raise ValueError("Die Kampagne benötigt Shards und Forschungsaufträge.")
    contract_ids = [str(contract.get("id") or "") for contract in contracts]
    if any(not contract_id for contract_id in contract_ids) or len(contract_ids) != len(set(contract_ids)):
        raise ValueError("Jeder Forschungsauftrag benötigt eine eindeutige ID.")
    for contract in contracts:
        if contract.get("recurrence") not in {"once", "weekly"}:
            raise ValueError("Forschungsaufträge dürfen nur einmalig oder wöchentlich sein.")
        raw_profiles = contract.get("profiles") or [contract.get("profile")]
        profiles = [str(profile) for profile in raw_profiles if profile]
        if not profiles or any(
            profile not in {
                "current", "balanced", "precision", "payoff",
                *TECHNICAL_CHALLENGER_PROFILE_NAMES,
            }
            for profile in profiles
        ):
            raise ValueError("Unbekanntes Forschungsprofil in der Kampagne.")
        if len(profiles) != len(set(profiles)):
            raise ValueError("Forschungsprofile dürfen innerhalb eines Vertrags nicht doppelt vorkommen.")
        if contract.get("sampling_mode") not in {"balanced_history", "recent_incremental"}:
            raise ValueError("Unbekannter Samplingmodus in der Kampagne.")
        selection_round = int(contract.get("selection_round") or 0)
        if selection_round < 0:
            raise ValueError("Historische Auswahlrunden dürfen nicht negativ sein.")
        selection_round_role = str(
            contract.get("selection_round_role")
            or ("monitoring" if contract.get("recurrence") == "weekly" else "exploration")
        )
        if selection_round_role not in {
            "exploration",
            "locked_validation",
            "final_confirmation",
            "monitoring",
        }:
            raise ValueError("Unbekannte Rolle einer historischen Auswahlrunde.")
        if contract.get("recurrence") == "weekly" and selection_round != 0:
            raise ValueError("Wöchentliches Monitoring darf keine zusätzliche Auswahlrunde verwenden.")
        dependencies = [str(item) for item in contract.get("depends_on") or []]
        if str(contract.get("id")) in dependencies:
            raise ValueError("Ein Forschungsauftrag darf nicht von sich selbst abhängen.")
        if any(dependency not in contract_ids for dependency in dependencies):
            raise ValueError("Forschungsauftrag verweist auf eine unbekannte Abhängigkeit.")
        profile_versions = dict(
            contract.get("profile_versions")
            or payload.get("locked_profile_versions")
            or {}
        )
        if profile_versions and set(profile_versions) != set(profiles):
            raise ValueError("Der Strategie-Freeze muss alle Profile des Forschungsauftrags abdecken.")
    dependency_graph = {
        str(contract["id"]): [str(item) for item in contract.get("depends_on") or []]
        for contract in contracts
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(contract_id: str) -> None:
        if contract_id in visiting:
            raise ValueError("Zyklische Forschungsabhängigkeit in der Kampagne.")
        if contract_id in visited:
            return
        visiting.add(contract_id)
        for dependency in dependency_graph[contract_id]:
            visit(dependency)
        visiting.remove(contract_id)
        visited.add(contract_id)

    for contract_id in contract_ids:
        visit(contract_id)
    return payload


def campaign_week_epoch(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _parse_clock(value: object) -> time:
    return time.fromisoformat(str(value))


def campaign_start_buffer_minutes(config: Mapping[str, object]) -> int:
    return max(
        int(config.get("maximum_expected_shard_minutes") or 0),
        int(config.get("minimum_clear_window_minutes") or 0),
        0,
    )


def campaign_is_protected_time(now: datetime, config: Mapping[str, object]) -> bool:
    """Evaluate the retired clock-window policy for historical evidence only.

    Historical Research/Development runners must not use this helper for an
    active start decision.  The configured windows are retained so old reports
    and tests can still explain the former operating policy.
    """

    start_buffer = timedelta(minutes=campaign_start_buffer_minutes(config))
    for window in config.get("protected_windows") or []:
        start_clock = _parse_clock(window["start"])
        end_clock = _parse_clock(window["end"])
        for day_offset in (-1, 0, 1):
            window_day = now.date() + timedelta(days=day_offset)
            starts_at = datetime.combine(window_day, start_clock, tzinfo=now.tzinfo)
            ends_at = datetime.combine(window_day, end_clock, tzinfo=now.tzinfo)
            if ends_at <= starts_at:
                ends_at += timedelta(days=1)
            if starts_at - start_buffer <= now < ends_at:
                return True
    return False


def campaign_active_production_jobs(
    config: Mapping[str, object],
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Probe production-owned locks without ever holding them during research."""
    root = Path(project_root or Path(__file__).resolve().parent)
    active: list[str] = []
    for raw_lock in config.get("protected_runtime_locks") or []:
        runtime_lock = dict(raw_lock)
        name = str(runtime_lock["name"])
        configured_path = Path(str(runtime_lock["path"]))
        lock_path = configured_path if configured_path.is_absolute() else root / configured_path
        probe = SwingRunLock(lock_path)
        try:
            probe.acquire()
        except (SwingRunAlreadyActiveError, OSError):
            active.append(name)
        else:
            probe.release()
    return active


def historical_research_runtime_gate(
    config: Mapping[str, object],
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    """Return the shared clock-free gate for historical research dispatch.

    A configured production lock is a real conflict only while its operating-
    system lock is held (or cannot be probed safely).  Stale lock files and the
    time of day never block research.  Campaign/run locks, SQLite safety
    pauses, resource limits and integrity gates remain owned by their existing
    callers because those states are specific to the corresponding store/run.
    """

    active = campaign_active_production_jobs(config, project_root=project_root)
    if active:
        return {
            "run_allowed": False,
            "reason": "BLOCKED_REAL_CONFLICT",
            "conflict_type": "ACTIVE_OR_UNPROBEABLE_PRODUCTION_LOCK",
            "active_production": active,
            "time_of_day_used": False,
            "legacy_time_windows_applied": False,
        }
    return {
        "run_allowed": True,
        "reason": "CLEAR",
        "conflict_type": None,
        "active_production": [],
        "time_of_day_used": False,
        "legacy_time_windows_applied": False,
    }


def campaign_jobs(
    config: Mapping[str, object],
    tickers: Sequence[str],
    *,
    now: datetime,
    weekly_epoch: str | None = None,
) -> list[dict]:
    shard_count = int(config["shard_count"])
    unique_tickers = list(dict.fromkeys(str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()))
    shards = [unique_tickers[index::shard_count] for index in range(shard_count)]
    jobs: list[dict] = []
    week = str(weekly_epoch or campaign_week_epoch(now))
    all_contracts = [
        *list(config.get("contracts") or []),
        *list(config.get("challenger_contracts") or []),
    ]
    for contract_order, raw_contract in enumerate(all_contracts):
        contract = dict(raw_contract)
        priority = int(contract.get("priority", contract_order))
        epoch = "fixed" if contract["recurrence"] == "once" else week
        for shard_index, shard_tickers in enumerate(shards):
            if not shard_tickers:
                continue
            job_key = (
                f"{config['version']}|{epoch}|{contract['id']}|"
                f"{shard_index + 1}-of-{shard_count}"
            )
            jobs.append(
                {
                    "job_key": job_key,
                    "epoch": epoch,
                    "priority": priority,
                    "contract": contract,
                    "shard_index": shard_index,
                    "shard_count": shard_count,
                    "tickers": shard_tickers,
                }
            )
    return jobs


def load_campaign_state(path: Path = DEFAULT_CAMPAIGN_STATE_PATH) -> dict:
    if not Path(path).exists():
        return {
            "version": CAMPAIGN_STATE_VERSION,
            "completed": {},
            "attempts": {},
            "last_event": None,
            "active_week_epoch": None,
        }
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("version") != CAMPAIGN_STATE_VERSION:
        raise ValueError("Nicht unterstützte Walk-Forward-Kampagnenstatusversion.")
    payload.setdefault("completed", {})
    payload.setdefault("attempts", {})
    payload.setdefault("last_event", None)
    payload.setdefault("active_week_epoch", None)
    return payload


def save_campaign_state(state: Mapping[str, object], path: Path = DEFAULT_CAMPAIGN_STATE_PATH) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(state, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def next_campaign_job(jobs: Sequence[Mapping[str, object]], state: Mapping[str, object]) -> dict | None:
    completed = dict(state.get("completed") or {})
    attempts = dict(state.get("attempts") or {})
    pending = [dict(job) for job in jobs if str(job["job_key"]) not in completed]
    if not pending:
        return None
    ready = [
        job
        for job in pending
        if _campaign_job_dependencies_completed(job, jobs, completed)
    ]
    if not ready:
        return None
    ready.sort(
        key=lambda job: (
            int(attempts.get(str(job["job_key"]), 0)),
            int(job.get("priority") or 0),
            int(job.get("shard_index") or 0),
        )
    )
    return ready[0]


def _campaign_job_dependencies_completed(
    job: Mapping[str, object],
    jobs: Sequence[Mapping[str, object]],
    completed: Mapping[str, object],
) -> bool:
    contract = dict(job.get("contract") or {})
    dependencies = {str(item) for item in contract.get("depends_on") or []}
    if not dependencies:
        return True
    required_keys = {
        str(candidate["job_key"])
        for candidate in jobs
        if str((candidate.get("contract") or {}).get("id") or "") in dependencies
    }
    return bool(required_keys) and required_keys.issubset(completed)


def campaign_status(jobs: Sequence[Mapping[str, object]], state: Mapping[str, object]) -> dict:
    completed = dict(state.get("completed") or {})
    relevant_keys = {str(job["job_key"]) for job in jobs}
    relevant_completed = len(relevant_keys.intersection(completed))
    pending_jobs = [job for job in jobs if str(job["job_key"]) not in completed]
    blocked_jobs = [
        job
        for job in pending_jobs
        if not _campaign_job_dependencies_completed(job, jobs, completed)
    ]
    fixed_rounds: list[dict] = []
    round_labels = sorted(
        {
            str((job.get("contract") or {}).get("selection_round_label") or "A")
            for job in jobs
            if (job.get("contract") or {}).get("recurrence") == "once"
        }
    )
    for label in round_labels:
        round_jobs = [
            job
            for job in jobs
            if (job.get("contract") or {}).get("recurrence") == "once"
            and str((job.get("contract") or {}).get("selection_round_label") or "A") == label
        ]
        round_keys = {str(job["job_key"]) for job in round_jobs}
        round_completed = len(round_keys.intersection(completed))
        role = str((round_jobs[0].get("contract") or {}).get("selection_round_role") or "exploration")
        fixed_rounds.append(
            {
                "selection_round": label,
                "selection_round_role": role,
                "jobs_total": len(round_jobs),
                "jobs_completed": round_completed,
                "jobs_pending": len(round_jobs) - round_completed,
            }
        )
    return {
        "jobs_total": len(jobs),
        "jobs_completed": relevant_completed,
        "jobs_pending": len(jobs) - relevant_completed,
        "jobs_blocked_by_round_dependencies": len(blocked_jobs),
        "fixed_rounds": fixed_rounds,
        "completion_pct": round(relevant_completed / len(jobs) * 100, 2) if jobs else 100.0,
        "last_event": state.get("last_event"),
        "automatic_rule_change": False,
        "production_activation": False,
    }
