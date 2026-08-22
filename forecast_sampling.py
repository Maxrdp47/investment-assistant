from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from swing_universe import active_swing_assets, load_swing_universe


WEEKDAY_LABELS = {
    0: "monday-reference-core",
    1: "tuesday-extension",
    2: "wednesday-extension",
    3: "thursday-extension",
    4: "friday-extension",
}


def _reference_tickers(path: Path) -> set[str]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    tickers = {str(row.get("ticker") or "").strip().upper() for row in rows}
    tickers.discard("")
    if not tickers:
        raise ValueError("Das Referenzuniversum enthält keine verwendbaren Ticker.")
    return tickers


def deterministic_extension_weekday(ticker: str, universe_version: str) -> int:
    digest = hashlib.sha256(f"{universe_version}|{ticker.upper()}".encode("utf-8")).digest()
    return 1 + int.from_bytes(digest[:4], "big") % 4


def build_weekly_cohort_plan(
    universe_path: Path,
    reference_universe_path: Path,
    *,
    minimum_active_assets: int = 1_500,
) -> dict:
    report = load_swing_universe(
        Path(universe_path),
        minimum_active_assets=int(minimum_active_assets),
    )
    if not report.valid:
        raise ValueError("Ungültiges Wochenuniversum: " + " | ".join(report.errors[:10]))
    assets = active_swing_assets(report)
    versions = sorted({asset.version for asset in assets})
    if len(versions) != 1:
        raise ValueError("Das Wochenuniversum muss genau eine gemeinsame Version besitzen.")
    universe_version = versions[0]
    reference_tickers = _reference_tickers(Path(reference_universe_path))
    available_tickers = {asset.ticker for asset in assets}
    missing_reference = sorted(reference_tickers - available_tickers)
    if missing_reference:
        raise ValueError(
            "Referenz-Assets fehlen im Wochenuniversum: " + ", ".join(missing_reference[:20])
        )

    cohorts: dict[int, list[dict]] = {weekday: [] for weekday in WEEKDAY_LABELS}
    for asset in assets:
        role = "reference_core" if asset.ticker in reference_tickers else "weekly_extension"
        weekday = 0 if role == "reference_core" else deterministic_extension_weekday(
            asset.ticker, universe_version
        )
        item = asset.as_dict()
        item.update(
            {
                "cohort_weekday": weekday,
                "cohort_label": WEEKDAY_LABELS[weekday],
                "sampling_role": role,
                "universe_version": universe_version,
            }
        )
        cohorts[weekday].append(item)
    for weekday in cohorts:
        cohorts[weekday].sort(key=lambda item: item["ticker"])

    assignment = [
        (item["ticker"], weekday, item["sampling_role"])
        for weekday, cohort in cohorts.items()
        for item in cohort
    ]
    fingerprint = hashlib.sha256(
        json.dumps(assignment, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "universe_path": str(Path(universe_path)),
        "reference_universe_path": str(Path(reference_universe_path)),
        "universe_version": universe_version,
        "universe_count": len(assets),
        "reference_core_count": len(reference_tickers),
        "extension_count": len(assets) - len(reference_tickers),
        "cohort_sizes": {WEEKDAY_LABELS[key]: len(value) for key, value in cohorts.items()},
        "assignment_fingerprint": fingerprint,
        "cohorts": cohorts,
    }


def select_weekly_cohort(
    plan: dict,
    run_day: date,
    *,
    completed_cohort_ids: set[str] | None = None,
    schedule_start_date: date | None = None,
) -> dict:
    iso_year, iso_week, _ = run_day.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"
    completed = completed_cohort_ids or set()
    if schedule_start_date is not None and run_day < schedule_start_date:
        eligible_weekdays: list[int] = []
    elif run_day.weekday() <= 4:
        eligible_weekdays = list(range(run_day.weekday() + 1))
    else:
        eligible_weekdays = list(WEEKDAY_LABELS)

    selected_weekday: int | None = None
    for weekday in eligible_weekdays:
        cohort_id = f"{week_id}-{WEEKDAY_LABELS[weekday]}"
        if cohort_id not in completed:
            selected_weekday = weekday
            break

    if selected_weekday is None:
        return {
            "assets": [],
            "sampling": {
                "mode": "evaluation_only",
                "iso_week": week_id,
                "cohort_id": None,
                "cohort_weekday": None,
                "cohort_label": None,
                "universe_version": plan["universe_version"],
                "weekly_universe_count": plan["universe_count"],
                "reference_core_count": plan["reference_core_count"],
                "assignment_fingerprint": plan["assignment_fingerprint"],
                "scheduled_assets": 0,
            },
        }

    label = WEEKDAY_LABELS[selected_weekday]
    assets = list(plan["cohorts"][selected_weekday])
    return {
        "assets": assets,
        "sampling": {
            "mode": "weekly_cohort",
            "iso_week": week_id,
            "cohort_id": f"{week_id}-{label}",
            "cohort_weekday": selected_weekday,
            "cohort_label": label,
            "universe_version": plan["universe_version"],
            "weekly_universe_count": plan["universe_count"],
            "reference_core_count": plan["reference_core_count"],
            "assignment_fingerprint": plan["assignment_fingerprint"],
            "scheduled_assets": len(assets),
        },
    }
