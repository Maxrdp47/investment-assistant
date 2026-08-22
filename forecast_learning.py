from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from forecast_measurement import canonical_json, verify_measurement_record


LEARNING_DATASET_VERSION = "forward-learning-dataset-2026.08.09-v1"
SHADOW_RESEARCH_MIN_CASES = 1_000
SHADOW_RESEARCH_MIN_WEEKS = 12
SHADOW_RESEARCH_MIN_CLASS_CASES = 200
SHADOW_RESEARCH_MIN_PROBABILITY_COVERAGE_PCT = 90.0
MEASUREMENT_COLUMNS = (
    "observation_cutoff_at",
    "feature_schema_version",
    "feature_snapshot_json",
    "measurement_contract_version",
    "measurement_contract_json",
    "snapshot_fingerprint",
)


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _weeks_between(first: str | None, last: str | None) -> int:
    if not first or not last:
        return 0
    try:
        start = datetime.fromisoformat(first).date()
        end = datetime.fromisoformat(last).date()
    except (TypeError, ValueError):
        return 0
    return max((end - start).days // 7 + 1, 1)


def _segment_report(rows: list[dict]) -> dict:
    cases = len(rows)
    positives = sum(int(row["outcome_up"]) == 1 for row in rows)
    negatives = cases - positives
    probability_cases = sum(row.get("probability_up") is not None for row in rows)
    first_observation = min((str(row["observation_cutoff_at"]) for row in rows), default=None)
    last_observation = max((str(row["observation_cutoff_at"]) for row in rows), default=None)
    observation_weeks = _weeks_between(first_observation, last_observation)
    probability_coverage = round(probability_cases / cases * 100, 1) if cases else 0.0
    blockers = []
    if cases < SHADOW_RESEARCH_MIN_CASES:
        blockers.append("insufficient_cases")
    if observation_weeks < SHADOW_RESEARCH_MIN_WEEKS:
        blockers.append("insufficient_time_coverage")
    if positives < SHADOW_RESEARCH_MIN_CLASS_CASES:
        blockers.append("insufficient_positive_cases")
    if negatives < SHADOW_RESEARCH_MIN_CLASS_CASES:
        blockers.append("insufficient_negative_cases")
    if probability_coverage < SHADOW_RESEARCH_MIN_PROBABILITY_COVERAGE_PCT:
        blockers.append("insufficient_probability_coverage")
    return {
        "cases": cases,
        "positive_cases": positives,
        "negative_cases": negatives,
        "probability_cases": probability_cases,
        "probability_coverage_pct": probability_coverage,
        "first_observation_at": first_observation,
        "last_observation_at": last_observation,
        "observation_weeks": observation_weeks,
        "shadow_research_ready": not blockers,
        "blockers": blockers,
        "production_activation_allowed": False,
    }


def build_learning_dataset_report(database_path: Path) -> dict:
    """Build a read-only, reproducible readiness report from verified matured snapshots."""
    if not Path(database_path).is_file():
        return {
            "dataset_version": LEARNING_DATASET_VERSION,
            "status": "missing_database",
            "eligible_cases": 0,
            "segments": [],
            "production_activation_allowed": False,
        }
    columns = ", ".join(f"f.{column}" for column in MEASUREMENT_COLUMNS)
    with closing(_readonly_connection(database_path)) as connection:
        rows = connection.execute(
            f"""
            SELECT f.id AS forecast_id, f.model_type, f.logic_version, f.asset_type,
                   f.region, f.market_phase, f.data_quality_label, {columns},
                   h.horizon, h.days, h.probability_up, h.probability_schema_version,
                   e.actual_return_pct, e.actual_day, e.evaluated_at, e.direction_hit,
                   e.excess_return_pct
            FROM forecasts f
            JOIN forecast_horizons h ON h.forecast_id = f.id
            LEFT JOIN forecast_evaluations e
              ON e.forecast_id = f.id AND e.horizon = h.horizon
            ORDER BY f.created_at, f.id, h.days
            """
        ).fetchall()

    exclusions = {
        "legacy_without_contract": 0,
        "invalid_measurement_contract": 0,
        "outcome_not_matured": 0,
        "outcome_not_usable": 0,
    }
    invalid_reasons: dict[str, int] = {}
    eligible: list[dict] = []
    for row in rows:
        item = dict(row)
        measurement_values = [item.get(column) for column in MEASUREMENT_COLUMNS]
        if all(value is None for value in measurement_values):
            exclusions["legacy_without_contract"] += 1
            continue
        valid, reasons = verify_measurement_record(item)
        if not valid:
            exclusions["invalid_measurement_contract"] += 1
            for reason in reasons:
                invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1
            continue
        if item.get("evaluated_at") is None:
            exclusions["outcome_not_matured"] += 1
            continue
        if item.get("actual_return_pct") is None or not item.get("actual_day"):
            exclusions["outcome_not_usable"] += 1
            continue
        try:
            features = json.loads(str(item["feature_snapshot_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            exclusions["invalid_measurement_contract"] += 1
            invalid_reasons["measurement_json_invalid"] = (
                invalid_reasons.get("measurement_json_invalid", 0) + 1
            )
            continue
        eligible.append(
            {
                "forecast_id": int(item["forecast_id"]),
                "model_type": str(item.get("model_type") or "entry_analysis"),
                "logic_version": str(item.get("logic_version") or "Unbekannt"),
                "asset_type": str(item.get("asset_type") or "Unbekannt"),
                "region": str(item.get("region") or "Unbekannt"),
                "market_phase": str(item.get("market_phase") or "Unbekannt"),
                "data_quality_label": str(item.get("data_quality_label") or "Unbekannt"),
                "observation_cutoff_at": str(item["observation_cutoff_at"]),
                "snapshot_fingerprint": str(item["snapshot_fingerprint"]),
                "horizon": str(item["horizon"]),
                "horizon_days": int(item["days"]),
                "probability_up": item.get("probability_up"),
                "probability_schema_version": item.get("probability_schema_version"),
                "outcome_up": int(float(item["actual_return_pct"]) > 0),
                "actual_return_pct": float(item["actual_return_pct"]),
                "actual_day": item.get("actual_day"),
                "evaluated_at": str(item["evaluated_at"]),
                "direction_hit": item.get("direction_hit"),
                "excess_return_pct": item.get("excess_return_pct"),
                "features": features,
            }
        )

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in eligible:
        grouped[(row["model_type"], row["horizon"])].append(row)
    segments = []
    for (model_type, horizon), segment_rows in sorted(grouped.items()):
        segments.append(
            {
                "model_type": model_type,
                "horizon": horizon,
                **_segment_report(segment_rows),
            }
        )
    fingerprint_rows = [
        {
            "snapshot_fingerprint": row["snapshot_fingerprint"],
            "horizon": row["horizon"],
            "actual_day": row["actual_day"],
            "actual_return_pct": row["actual_return_pct"],
        }
        for row in eligible
    ]
    dataset_fingerprint = hashlib.sha256(
        canonical_json(fingerprint_rows).encode("utf-8")
    ).hexdigest()
    invalid_count = exclusions["invalid_measurement_contract"]
    return {
        "dataset_version": LEARNING_DATASET_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "attention" if invalid_count else "collect_only",
        "as_of": date.today().isoformat(),
        "source_rows": len(rows),
        "eligible_cases": len(eligible),
        "excluded": exclusions,
        "invalid_reasons": invalid_reasons,
        "dataset_fingerprint": dataset_fingerprint,
        "segments": segments,
        "shadow_research_policy": {
            "minimum_cases": SHADOW_RESEARCH_MIN_CASES,
            "minimum_observation_weeks": SHADOW_RESEARCH_MIN_WEEKS,
            "minimum_positive_cases": SHADOW_RESEARCH_MIN_CLASS_CASES,
            "minimum_negative_cases": SHADOW_RESEARCH_MIN_CLASS_CASES,
            "minimum_probability_coverage_pct": SHADOW_RESEARCH_MIN_PROBABILITY_COVERAGE_PCT,
            "requires_later_power_analysis": True,
            "random_row_split_allowed": False,
            "purging_required": True,
        },
        "production_activation_allowed": False,
    }


def build_purged_walk_forward_windows(
    rows: list[dict],
    *,
    minimum_training_days: int = 84,
    validation_days: int = 28,
    test_days: int = 28,
    step_days: int = 28,
) -> list[dict]:
    """Create expanding chronological windows whose labels were known before the next stage."""
    if not rows:
        return []
    numeric_values = (minimum_training_days, validation_days, test_days, step_days)
    if any(int(value) < 1 for value in numeric_values):
        raise ValueError("Walk-Forward-Zeiträume müssen mindestens einen Tag umfassen.")

    prepared = []
    for row in rows:
        try:
            observation_day = datetime.fromisoformat(str(row["observation_cutoff_at"])).date()
            outcome_day = date.fromisoformat(str(row["actual_day"])[:10])
        except (KeyError, TypeError, ValueError):
            continue
        if outcome_day < observation_day:
            continue
        prepared.append({**row, "_observation_day": observation_day, "_outcome_day": outcome_day})
    if not prepared:
        return []
    prepared.sort(key=lambda item: (item["_observation_day"], str(item.get("snapshot_fingerprint"))))
    first_day = prepared[0]["_observation_day"]
    last_day = prepared[-1]["_observation_day"]
    validation_start = first_day + timedelta(days=int(minimum_training_days))
    windows = []
    window_number = 1
    while True:
        validation_end = validation_start + timedelta(days=int(validation_days) - 1)
        test_start = validation_end + timedelta(days=1)
        test_end = test_start + timedelta(days=int(test_days) - 1)
        if test_end > last_day:
            break
        training = [
            row
            for row in prepared
            if row["_observation_day"] < validation_start
            and row["_outcome_day"] < validation_start
        ]
        validation = [
            row
            for row in prepared
            if validation_start <= row["_observation_day"] <= validation_end
            and row["_outcome_day"] < test_start
        ]
        test = [
            row
            for row in prepared
            if test_start <= row["_observation_day"] <= test_end
        ]
        purged_before_validation = sum(
            row["_observation_day"] < validation_start <= row["_outcome_day"]
            for row in prepared
        )
        purged_before_test = sum(
            validation_start <= row["_observation_day"] <= validation_end
            and row["_outcome_day"] >= test_start
            for row in prepared
        )
        window_payload = {
            "window": window_number,
            "training": {
                "observation_start": first_day.isoformat(),
                "observation_end_exclusive": validation_start.isoformat(),
                "cases": len(training),
                "latest_known_outcome_day": max(
                    (row["_outcome_day"].isoformat() for row in training),
                    default=None,
                ),
            },
            "validation": {
                "observation_start": validation_start.isoformat(),
                "observation_end": validation_end.isoformat(),
                "cases": len(validation),
                "latest_known_outcome_day": max(
                    (row["_outcome_day"].isoformat() for row in validation),
                    default=None,
                ),
            },
            "test": {
                "observation_start": test_start.isoformat(),
                "observation_end": test_end.isoformat(),
                "cases": len(test),
            },
            "purged_before_validation": purged_before_validation,
            "purged_before_test": purged_before_test,
            "random_row_split_used": False,
        }
        window_payload["fingerprint"] = hashlib.sha256(
            canonical_json(window_payload).encode("utf-8")
        ).hexdigest()
        windows.append(window_payload)
        validation_start += timedelta(days=int(step_days))
        window_number += 1
    return windows
