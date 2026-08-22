from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from forecast_sampling import WEEKDAY_LABELS


WEEKLY_REPORT_VERSION = "2026.08.09-v1"
DEFAULT_WEEKLY_REPORT_DIRECTORY = Path(__file__).resolve().parent / "runtime" / "weekly_reports"


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _week_bounds(process_day: date) -> tuple[date, date]:
    monday = process_day - timedelta(days=process_day.weekday())
    return monday, monday + timedelta(days=6)


def _run_rows(
    database_path: Path,
    week_id: str,
    process_day: date,
) -> tuple[list[dict], dict]:
    if not Path(database_path).is_file():
        return [], {
            "integrity": "missing",
            "evaluated_this_week": 0,
            "due_open": 0,
            "failed_evaluation_attempts": 0,
        }
    with closing(_readonly_connection(database_path)) as connection:
        runs = []
        for row in connection.execute(
            "SELECT * FROM forecast_runs WHERE sampling_json IS NOT NULL ORDER BY run_date, id"
        ):
            try:
                sampling = json.loads(str(row["sampling_json"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(sampling, dict) or sampling.get("iso_week") != week_id:
                continue
            item = dict(row)
            item["sampling"] = sampling
            runs.append(item)
        monday = date.fromisocalendar(int(week_id[:4]), int(week_id[-2:]), 1)
        through_day = min(process_day, monday + timedelta(days=6))
        evaluated_this_week = int(
            connection.execute(
                "SELECT COUNT(*) FROM forecast_evaluations "
                "WHERE date(evaluated_at) BETWEEN date(?) AND date(?)",
                (monday.isoformat(), through_day.isoformat()),
            ).fetchone()[0]
        )
        due_open = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM forecast_horizons h
                JOIN forecasts f ON f.id = h.forecast_id
                LEFT JOIN forecast_evaluations e
                  ON e.forecast_id = h.forecast_id AND e.horizon = h.horizon
                WHERE e.id IS NULL
                  AND date(f.created_at, '+' || h.days || ' days') <= date(?)
                """,
                (process_day.isoformat(),),
            ).fetchone()[0]
        )
        failed_evaluation_attempts = int(
            connection.execute(
                "SELECT COUNT(*) FROM forecast_evaluation_attempts "
                "WHERE date(attempted_at) BETWEEN date(?) AND date(?) AND status = 'failed'",
                (monday.isoformat(), through_day.isoformat()),
            ).fetchone()[0]
        )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    return runs, {
        "integrity": integrity,
        "evaluated_this_week": evaluated_this_week,
        "due_open": due_open,
        "failed_evaluation_attempts": failed_evaluation_attempts,
    }


def build_weekly_report(
    plan: dict,
    database_path: Path,
    process_day: date,
    *,
    schedule_start_date: date | None = None,
) -> dict:
    iso_year, iso_week, _ = process_day.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"
    monday, sunday = _week_bounds(process_day)
    runs, database_metrics = _run_rows(database_path, week_id, process_day)
    completed_runs = [
        item
        for item in runs
        if item.get("status") in {"completed", "completed_with_errors"}
        and (item.get("sampling") or {}).get("cohort_id")
    ]
    completed_ids = {
        str(item["sampling"]["cohort_id"])
        for item in completed_runs
    }
    expected = [
        {
            "weekday": weekday,
            "label": label,
            "cohort_id": f"{week_id}-{label}",
            "scheduled_assets": int(plan["cohort_sizes"][label]),
        }
        for weekday, label in WEEKDAY_LABELS.items()
    ]
    due_weekdays = (
        list(range(min(process_day.weekday(), 4) + 1))
        if (schedule_start_date is None or process_day >= schedule_start_date)
        else []
    )
    due_ids = {expected[weekday]["cohort_id"] for weekday in due_weekdays}
    cohort_rows = []
    for expected_item in expected:
        matching = next(
            (
                item
                for item in completed_runs
                if item["sampling"]["cohort_id"] == expected_item["cohort_id"]
            ),
            None,
        )
        actual_run_day = date.fromisoformat(str(matching["run_date"])) if matching else None
        cohort_rows.append(
            {
                **expected_item,
                "status": "completed" if matching else "due_missing" if expected_item["cohort_id"] in due_ids else "future",
                "run_date": actual_run_day.isoformat() if actual_run_day else None,
                "catch_up_days": (
                    (actual_run_day - (monday + timedelta(days=expected_item["weekday"]))).days
                    if actual_run_day
                    else None
                ),
                "processed_assets": int(matching.get("processed_count") or 0) if matching else 0,
                "successful_assets": int(matching.get("success_count") or 0) if matching else 0,
                "failed_assets": int(matching.get("failure_count") or 0) if matching else 0,
                "rate_limit_failures": int(matching.get("rate_limit_failures") or 0) if matching else 0,
                "elapsed_seconds": matching.get("elapsed_seconds") if matching else None,
                "database_growth_bytes": matching.get("database_growth_bytes") if matching else None,
            }
        )
    successful_assets = sum(item["successful_assets"] for item in cohort_rows)
    processed_assets = sum(item["processed_assets"] for item in cohort_rows)
    failed_assets = sum(item["failed_assets"] for item in cohort_rows)
    return {
        "report_version": WEEKLY_REPORT_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "iso_week": week_id,
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "as_of": process_day.isoformat(),
        "schedule": {
            "start_date": schedule_start_date.isoformat() if schedule_start_date else None,
            "active": schedule_start_date is None or process_day >= schedule_start_date,
        },
        "universe": {
            "version": plan["universe_version"],
            "planned_assets": int(plan["universe_count"]),
            "reference_core_assets": int(plan["reference_core_count"]),
            "extension_assets": int(plan["extension_count"]),
            "assignment_fingerprint": plan["assignment_fingerprint"],
        },
        "coverage": {
            "completed_cohorts": len(completed_ids),
            "planned_cohorts": len(expected),
            "processed_assets": processed_assets,
            "successful_assets": successful_assets,
            "failed_assets": failed_assets,
            "successful_asset_coverage_pct": round(
                successful_assets / int(plan["universe_count"]) * 100,
                2,
            ),
            "overdue_cohorts": sorted(due_ids - completed_ids),
        },
        "operations": {
            "rate_limit_failures": sum(item["rate_limit_failures"] for item in cohort_rows),
            "elapsed_seconds": round(
                sum(float(item["elapsed_seconds"] or 0) for item in cohort_rows),
                2,
            ),
            "database_growth_bytes": sum(
                int(item["database_growth_bytes"] or 0) for item in cohort_rows
            ),
        },
        "evaluations": database_metrics,
        "cohorts": cohort_rows,
        "data_deleted": False,
    }


def write_weekly_report(
    plan: dict,
    database_path: Path,
    output_directory: Path,
    process_day: date,
    *,
    schedule_start_date: date | None = None,
) -> dict:
    report = build_weekly_report(
        plan,
        database_path,
        process_day,
        schedule_start_date=schedule_start_date,
    )
    destination = Path(output_directory) / f"{report['iso_week']}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {**report, "path": str(destination), "write_status": "ok"}


def load_weekly_report(
    output_directory: Path = DEFAULT_WEEKLY_REPORT_DIRECTORY,
    process_day: date | None = None,
) -> dict:
    target_day = process_day or date.today()
    iso_year, iso_week, _ = target_day.isocalendar()
    path = Path(output_directory) / f"{iso_year}-W{iso_week:02d}.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("report_version") != WEEKLY_REPORT_VERSION:
        return {}
    return payload
