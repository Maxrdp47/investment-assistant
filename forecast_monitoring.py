from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from forecast_metrics import percentage, probability_metrics


FORECAST_MONITORING_VERSION = "forecast-monitoring-2026.08.09-v1"
DEFAULT_RECENT_DAYS = 28
DEFAULT_REFERENCE_DAYS = 84
DEFAULT_MIN_EVALUATED_CASES = 50
DEFAULT_MIN_PROBABILITY_CASES = 50
DEFAULT_MIN_INPUT_CASES = 100
EVALUATION_GRACE_DAYS = 3
KNOWN_DIRECTIONS = {"Steigend", "Fallend", "Seitwärts"}

ALERT_THRESHOLDS = {
    "direction_hit_rate_drop_pct_points": 10.0,
    "brier_score_increase": 0.05,
    "log_loss_increase": 0.10,
    "benchmark_advantage_drop_pct_points": 10.0,
    "excess_return_drop_pct_points": 5.0,
    "probability_coverage_min_pct": 90.0,
    "stale_evaluation_coverage_min_pct": 90.0,
    "run_success_coverage_min_pct": 95.0,
    "categorical_total_variation": 0.20,
    "numeric_mean_shift": 1.0,
    "abstention_rate_change_pct_points": 10.0,
}


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _average(values: list[object]) -> float | None:
    valid = [number for value in values if (number := _finite(value)) is not None]
    return round(sum(valid) / len(valid), 4) if valid else None


def _metric_delta(recent: object, reference: object, digits: int = 4) -> float | None:
    recent_value = _finite(recent)
    reference_value = _finite(reference)
    if recent_value is None or reference_value is None:
        return None
    return round(recent_value - reference_value, digits)


def evaluation_window_metrics(rows: list[dict]) -> dict:
    evaluated_rows = [row for row in rows if row.get("direction_hit") is not None]
    cases = len(evaluated_rows)
    hits = sum(int(row["direction_hit"]) == 1 for row in evaluated_rows)
    trend_rows = [row for row in evaluated_rows if row.get("simple_trend_hit") is not None]
    trend_hits = sum(int(row["simple_trend_hit"]) == 1 for row in trend_rows)
    probability_cases = [
        (row.get("probability_up"), int(float(row["actual_return_pct"]) > 0))
        for row in evaluated_rows
        if row.get("probability_up") is not None and row.get("actual_return_pct") is not None
    ]
    hit_rate = percentage(hits, cases)
    trend_hit_rate = percentage(trend_hits, len(trend_rows))
    return {
        "evaluated_cases": cases,
        "direction_hits": hits,
        "direction_hit_rate_pct": hit_rate,
        "simple_trend_evaluated": len(trend_rows),
        "simple_trend_hit_rate_pct": trend_hit_rate,
        "advantage_vs_simple_trend_pct_points": (
            round(float(hit_rate) - float(trend_hit_rate), 1)
            if hit_rate is not None and trend_hit_rate is not None
            else None
        ),
        "average_return_pct": _average([row.get("actual_return_pct") for row in evaluated_rows]),
        "average_excess_return_pct": _average(
            [row.get("excess_return_pct") for row in evaluated_rows]
        ),
        "probability_coverage_pct": percentage(len(probability_cases), cases),
        **probability_metrics(probability_cases),
    }


def compare_evaluation_windows(
    reference_rows: list[dict],
    recent_rows: list[dict],
    *,
    model_type: str,
    horizon: str,
    minimum_evaluated_cases: int = DEFAULT_MIN_EVALUATED_CASES,
    minimum_probability_cases: int = DEFAULT_MIN_PROBABILITY_CASES,
) -> dict:
    reference = evaluation_window_metrics(reference_rows)
    recent = evaluation_window_metrics(recent_rows)
    scope = f"{model_type} · {horizon}"
    deltas = {
        "direction_hit_rate_pct_points": _metric_delta(
            recent["direction_hit_rate_pct"], reference["direction_hit_rate_pct"], 1
        ),
        "brier_score": _metric_delta(recent["brier_score"], reference["brier_score"]),
        "log_loss": _metric_delta(recent["log_loss"], reference["log_loss"]),
        "benchmark_advantage_pct_points": _metric_delta(
            recent["advantage_vs_simple_trend_pct_points"],
            reference["advantage_vs_simple_trend_pct_points"],
            1,
        ),
        "average_excess_return_pct_points": _metric_delta(
            recent["average_excess_return_pct"], reference["average_excess_return_pct"], 2
        ),
    }
    alerts: list[dict] = []
    outcome_ready = (
        int(reference["evaluated_cases"]) >= int(minimum_evaluated_cases)
        and int(recent["evaluated_cases"]) >= int(minimum_evaluated_cases)
    )
    probability_ready = (
        int(reference["probability_evaluated"]) >= int(minimum_probability_cases)
        and int(recent["probability_evaluated"]) >= int(minimum_probability_cases)
    )

    def add_alert(code: str, message: str, severity: str = "warning") -> None:
        alerts.append(
            {
                "code": code,
                "severity": severity,
                "scope": scope,
                "message": message,
                "automatic_change": False,
            }
        )

    hit_delta = deltas["direction_hit_rate_pct_points"]
    if outcome_ready and hit_delta is not None and hit_delta <= -ALERT_THRESHOLDS["direction_hit_rate_drop_pct_points"]:
        add_alert(
            "direction_quality_drop",
            f"Richtungstrefferquote ist gegenüber dem Referenzfenster um {abs(hit_delta):.1f} Prozentpunkte gefallen.",
        )
    advantage_delta = deltas["benchmark_advantage_pct_points"]
    if outcome_ready and advantage_delta is not None and advantage_delta <= -ALERT_THRESHOLDS["benchmark_advantage_drop_pct_points"]:
        add_alert(
            "benchmark_advantage_drop",
            f"Vorsprung gegenüber der festen Trendregel ist um {abs(advantage_delta):.1f} Prozentpunkte gefallen.",
        )
    excess_delta = deltas["average_excess_return_pct_points"]
    if outcome_ready and excess_delta is not None and excess_delta <= -ALERT_THRESHOLDS["excess_return_drop_pct_points"]:
        add_alert(
            "excess_return_drop",
            f"Mittlere Überschussrendite ist um {abs(excess_delta):.2f} Prozentpunkte gefallen.",
        )
    brier_delta = deltas["brier_score"]
    if probability_ready and brier_delta is not None and brier_delta >= ALERT_THRESHOLDS["brier_score_increase"]:
        add_alert(
            "brier_score_worse",
            f"Brier Score hat sich um {brier_delta:.4f} verschlechtert.",
        )
    log_loss_delta = deltas["log_loss"]
    if probability_ready and log_loss_delta is not None and log_loss_delta >= ALERT_THRESHOLDS["log_loss_increase"]:
        add_alert(
            "log_loss_worse",
            f"Log Loss hat sich um {log_loss_delta:.4f} verschlechtert.",
        )
    probability_coverage = recent.get("probability_coverage_pct")
    if (
        int(recent["evaluated_cases"]) >= int(minimum_evaluated_cases)
        and probability_coverage is not None
        and float(probability_coverage) < ALERT_THRESHOLDS["probability_coverage_min_pct"]
    ):
        add_alert(
            "probability_coverage_low",
            f"Nur {float(probability_coverage):.1f} % der jüngsten Ergebnisse besitzen eine prüfbare Wahrscheinlichkeit.",
        )
    return {
        "model_type": model_type,
        "horizon": horizon,
        "status": "attention" if alerts else "ok" if outcome_ready else "insufficient_data",
        "outcome_comparison_ready": outcome_ready,
        "probability_comparison_ready": probability_ready,
        "reference": reference,
        "recent": recent,
        "deltas": deltas,
        "alerts": alerts,
    }


def _distribution(rows: list[dict], key: str) -> dict[str, float]:
    counter = Counter(str(row.get(key) or "Unbekannt") for row in rows)
    total = sum(counter.values())
    return {label: count / total for label, count in sorted(counter.items())} if total else {}


def _total_variation(reference: dict[str, float], recent: dict[str, float]) -> float | None:
    if not reference or not recent:
        return None
    labels = set(reference) | set(recent)
    return round(0.5 * sum(abs(reference.get(label, 0.0) - recent.get(label, 0.0)) for label in labels), 4)


def _input_drift(reference_rows: list[dict], recent_rows: list[dict], minimum_cases: int) -> dict:
    ready = len(reference_rows) >= minimum_cases and len(recent_rows) >= minimum_cases
    dimensions = []
    alerts: list[dict] = []
    for key in ("asset_type", "region", "market_phase", "data_quality_label", "predicted_direction"):
        reference = _distribution(reference_rows, key)
        recent = _distribution(recent_rows, key)
        distance = _total_variation(reference, recent)
        item = {
            "dimension": key,
            "total_variation": distance,
            "reference_distribution": reference,
            "recent_distribution": recent,
            "comparison_ready": ready,
        }
        dimensions.append(item)
        if ready and distance is not None and distance >= ALERT_THRESHOLDS["categorical_total_variation"]:
            alerts.append(
                {
                    "code": "input_distribution_shift",
                    "severity": "warning",
                    "scope": key,
                    "message": f"Eingabeverteilung hat sich deutlich verschoben (Distanz {distance:.3f}).",
                    "automatic_change": False,
                }
            )
        if ready:
            for label, reference_share in reference.items():
                recent_share = recent.get(label, 0.0)
                if reference_share >= 0.05 and recent_share < max(0.01, reference_share * 0.25):
                    alerts.append(
                        {
                            "code": "segment_outage",
                            "severity": "warning",
                            "scope": f"{key}:{label}",
                            "message": "Ein zuvor relevantes Eingabesegment ist im jüngsten Fenster nahezu ausgefallen.",
                            "automatic_change": False,
                        }
                    )
    numeric = []
    for key in ("asset_quality", "buy_signal", "confidence", "data_quality"):
        reference_mean = _average([row.get(key) for row in reference_rows])
        recent_mean = _average([row.get(key) for row in recent_rows])
        delta = _metric_delta(recent_mean, reference_mean, 3)
        numeric.append(
            {
                "feature": key,
                "reference_mean": reference_mean,
                "recent_mean": recent_mean,
                "delta": delta,
                "comparison_ready": ready,
            }
        )
        if ready and delta is not None and abs(delta) >= ALERT_THRESHOLDS["numeric_mean_shift"]:
            alerts.append(
                {
                    "code": "numeric_feature_shift",
                    "severity": "warning",
                    "scope": key,
                    "message": f"Mittelwert hat sich um {delta:+.3f} Punkte verschoben.",
                    "automatic_change": False,
                }
            )
    reference_abstentions = sum(str(row.get("predicted_direction") or "") not in KNOWN_DIRECTIONS for row in reference_rows)
    recent_abstentions = sum(str(row.get("predicted_direction") or "") not in KNOWN_DIRECTIONS for row in recent_rows)
    reference_abstention_rate = percentage(reference_abstentions, len(reference_rows))
    recent_abstention_rate = percentage(recent_abstentions, len(recent_rows))
    abstention_delta = _metric_delta(recent_abstention_rate, reference_abstention_rate, 1)
    if ready and abstention_delta is not None and abs(abstention_delta) >= ALERT_THRESHOLDS["abstention_rate_change_pct_points"]:
        alerts.append(
            {
                "code": "abstention_rate_shift",
                "severity": "warning",
                "scope": "predicted_direction",
                "message": f"Enthaltungsquote hat sich um {abstention_delta:+.1f} Prozentpunkte verschoben.",
                "automatic_change": False,
            }
        )
    return {
        "comparison_ready": ready,
        "reference_cases": len(reference_rows),
        "recent_cases": len(recent_rows),
        "categorical": dimensions,
        "numeric": numeric,
        "abstention": {
            "definition": "Richtung außerhalb Steigend/Fallend/Seitwärts",
            "reference_rate_pct": reference_abstention_rate,
            "recent_rate_pct": recent_abstention_rate,
            "delta_pct_points": abstention_delta,
            "current_champion_has_explicit_ood_abstention": False,
        },
        "alerts": alerts,
    }


def _empty_report(as_of: date, status: str) -> dict:
    return {
        "monitoring_version": FORECAST_MONITORING_VERSION,
        "as_of": as_of.isoformat(),
        "status": status,
        "windows": {},
        "operational": {},
        "segments": [],
        "input_drift": {},
        "alerts": [],
        "guardrails": {
            "observe_only": True,
            "automatic_model_change": False,
            "automatic_production_activation": False,
        },
    }


def build_forecast_monitoring_report(
    database_path: Path,
    *,
    as_of: date | None = None,
    recent_days: int = DEFAULT_RECENT_DAYS,
    reference_days: int = DEFAULT_REFERENCE_DAYS,
    minimum_evaluated_cases: int = DEFAULT_MIN_EVALUATED_CASES,
    minimum_probability_cases: int = DEFAULT_MIN_PROBABILITY_CASES,
    minimum_input_cases: int = DEFAULT_MIN_INPUT_CASES,
) -> dict:
    process_day = as_of or date.today()
    if not Path(database_path).is_file():
        return _empty_report(process_day, "missing_database")
    if min(recent_days, reference_days, minimum_evaluated_cases, minimum_probability_cases, minimum_input_cases) < 1:
        raise ValueError("Monitoring-Fenster und Mindestfallzahlen müssen positiv sein.")
    recent_start = process_day - timedelta(days=int(recent_days) - 1)
    reference_end = recent_start - timedelta(days=1)
    reference_start = reference_end - timedelta(days=int(reference_days) - 1)
    stale_due_cutoff = process_day - timedelta(days=EVALUATION_GRACE_DAYS)

    with closing(_readonly_connection(database_path)) as connection:
        evaluation_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT COALESCE(NULLIF(f.model_type, ''), 'entry_analysis') AS model_type,
                       f.logic_version, f.asset_type, f.region, f.market_phase,
                       f.data_quality_label, f.predicted_direction, h.horizon,
                       h.probability_up, e.actual_return_pct, e.direction_hit,
                       e.simple_trend_hit, e.excess_return_pct,
                       COALESCE(e.actual_day, substr(e.evaluated_at, 1, 10)) AS result_day
                FROM forecast_evaluations e
                JOIN forecasts f ON f.id = e.forecast_id
                JOIN forecast_horizons h
                  ON h.forecast_id = e.forecast_id AND h.horizon = e.horizon
                WHERE date(COALESCE(e.actual_day, e.evaluated_at)) BETWEEN date(?) AND date(?)
                ORDER BY result_day, f.id, h.days
                """,
                (reference_start.isoformat(), process_day.isoformat()),
            ).fetchall()
        ]
        forecast_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT created_at, asset_type, region, market_phase, data_quality_label,
                       predicted_direction, asset_quality, buy_signal, confidence, data_quality
                FROM forecasts
                WHERE date(created_at) BETWEEN date(?) AND date(?)
                ORDER BY created_at, id
                """,
                (reference_start.isoformat(), process_day.isoformat()),
            ).fetchall()
        ]
        due_row = connection.execute(
            """
            SELECT COUNT(*) AS due_total,
                   SUM(CASE WHEN e.id IS NOT NULL THEN 1 ELSE 0 END) AS evaluated_total,
                   SUM(CASE WHEN date(f.created_at, '+' || h.days || ' days') <= date(?) THEN 1 ELSE 0 END) AS stale_due_total,
                   SUM(CASE WHEN date(f.created_at, '+' || h.days || ' days') <= date(?) AND e.id IS NOT NULL THEN 1 ELSE 0 END) AS stale_evaluated_total
            FROM forecasts f
            JOIN forecast_horizons h ON h.forecast_id = f.id
            LEFT JOIN forecast_evaluations e
              ON e.forecast_id = f.id AND e.horizon = h.horizon
            WHERE date(f.created_at, '+' || h.days || ' days') <= date(?)
            """,
            (stale_due_cutoff.isoformat(), stale_due_cutoff.isoformat(), process_day.isoformat()),
        ).fetchone()
        attempt_rows = connection.execute(
            """
            SELECT error_kind, COUNT(*) AS cases
            FROM forecast_evaluation_attempts
            WHERE date(attempted_at) BETWEEN date(?) AND date(?)
            GROUP BY error_kind
            """,
            (recent_start.isoformat(), process_day.isoformat()),
        ).fetchall()
        run_row = connection.execute(
            """
            SELECT COUNT(*) AS runs,
                   SUM(processed_count) AS processed,
                   SUM(success_count) AS succeeded,
                   SUM(failure_count) AS failed,
                   SUM(rate_limit_failures) AS rate_limits
            FROM forecast_runs
            WHERE date(run_date) BETWEEN date(?) AND date(?)
              AND status <> 'running'
            """,
            (recent_start.isoformat(), process_day.isoformat()),
        ).fetchone()

    reference_evaluations = [row for row in evaluation_rows if reference_start.isoformat() <= str(row["result_day"]) <= reference_end.isoformat()]
    recent_evaluations = [row for row in evaluation_rows if recent_start.isoformat() <= str(row["result_day"]) <= process_day.isoformat()]
    grouped_reference: dict[tuple[str, str], list[dict]] = defaultdict(list)
    grouped_recent: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in reference_evaluations:
        grouped_reference[(str(row["model_type"]), str(row["horizon"]))].append(row)
    for row in recent_evaluations:
        grouped_recent[(str(row["model_type"]), str(row["horizon"]))].append(row)
    segments = [
        compare_evaluation_windows(
            grouped_reference.get(key, []),
            grouped_recent.get(key, []),
            model_type=key[0],
            horizon=key[1],
            minimum_evaluated_cases=minimum_evaluated_cases,
            minimum_probability_cases=minimum_probability_cases,
        )
        for key in sorted(set(grouped_reference) | set(grouped_recent))
    ]

    reference_forecasts = [row for row in forecast_rows if reference_start.isoformat() <= str(row["created_at"])[:10] <= reference_end.isoformat()]
    recent_forecasts = [row for row in forecast_rows if recent_start.isoformat() <= str(row["created_at"])[:10] <= process_day.isoformat()]
    input_drift = _input_drift(reference_forecasts, recent_forecasts, minimum_input_cases)
    alerts = [alert for segment in segments for alert in segment["alerts"]]
    alerts.extend(input_drift["alerts"])

    due_total = int(due_row["due_total"] or 0)
    evaluated_total = int(due_row["evaluated_total"] or 0)
    stale_due_total = int(due_row["stale_due_total"] or 0)
    stale_evaluated_total = int(due_row["stale_evaluated_total"] or 0)
    evaluation_coverage = percentage(evaluated_total, due_total)
    stale_coverage = percentage(stale_evaluated_total, stale_due_total)
    attempts = {str(row["error_kind"] or "unknown"): int(row["cases"] or 0) for row in attempt_rows}
    processed = int(run_row["processed"] or 0)
    succeeded = int(run_row["succeeded"] or 0)
    run_success_coverage = percentage(succeeded, processed)
    if (
        stale_due_total >= minimum_evaluated_cases
        and stale_coverage is not None
        and stale_coverage < ALERT_THRESHOLDS["stale_evaluation_coverage_min_pct"]
    ):
        alerts.append(
            {
                "code": "stale_evaluation_coverage_low",
                "severity": "critical",
                "scope": "operations",
                "message": f"Nur {stale_coverage:.1f} % der seit mehr als {EVALUATION_GRACE_DAYS} Tagen fälligen Fälle sind ausgewertet.",
                "automatic_change": False,
            }
        )
    if processed >= minimum_input_cases and run_success_coverage is not None and run_success_coverage < ALERT_THRESHOLDS["run_success_coverage_min_pct"]:
        alerts.append(
            {
                "code": "forecast_collection_coverage_low",
                "severity": "critical",
                "scope": "operations",
                "message": f"Nur {run_success_coverage:.1f} % der jüngsten Asset-Versuche waren erfolgreich.",
                "automatic_change": False,
            }
        )
    if attempts.get("technical", 0) > 0:
        alerts.append(
            {
                "code": "technical_evaluation_failures",
                "severity": "critical",
                "scope": "operations",
                "message": f"{attempts['technical']} fällige Auswertungen besitzen einen technischen Fehler.",
                "automatic_change": False,
            }
        )
    recent_rate_limits = int(run_row["rate_limits"] or 0)
    if recent_rate_limits > 0:
        alerts.append(
            {
                "code": "rate_limits_detected",
                "severity": "warning",
                "scope": "operations",
                "message": f"Im jüngsten Fenster wurden {recent_rate_limits} Rate-Limit-Fehler protokolliert.",
                "automatic_change": False,
            }
        )

    comparable_segments = sum(segment["outcome_comparison_ready"] for segment in segments)
    status = "attention" if alerts else "ok" if comparable_segments or input_drift["comparison_ready"] else "collect_only"
    return {
        "monitoring_version": FORECAST_MONITORING_VERSION,
        "as_of": process_day.isoformat(),
        "status": status,
        "windows": {
            "reference": {"start": reference_start.isoformat(), "end": reference_end.isoformat(), "days": reference_days},
            "recent": {"start": recent_start.isoformat(), "end": process_day.isoformat(), "days": recent_days},
            "minimum_evaluated_cases": minimum_evaluated_cases,
            "minimum_probability_cases": minimum_probability_cases,
            "minimum_input_cases": minimum_input_cases,
        },
        "operational": {
            "due_total": due_total,
            "evaluated_total": evaluated_total,
            "evaluation_coverage_pct": evaluation_coverage,
            "stale_after_days": EVALUATION_GRACE_DAYS,
            "stale_due_total": stale_due_total,
            "stale_evaluated_total": stale_evaluated_total,
            "stale_evaluation_coverage_pct": stale_coverage,
            "recent_evaluation_attempt_failures": attempts,
            "recent_runs": int(run_row["runs"] or 0),
            "recent_assets_processed": processed,
            "recent_assets_succeeded": succeeded,
            "recent_assets_failed": int(run_row["failed"] or 0),
            "recent_run_success_coverage_pct": run_success_coverage,
            "recent_rate_limits": recent_rate_limits,
        },
        "segments": segments,
        "input_drift": {key: value for key, value in input_drift.items() if key != "alerts"},
        "alerts": alerts,
        "guardrails": {
            "observe_only": True,
            "automatic_model_change": False,
            "automatic_production_activation": False,
            "single_failure_triggers_retraining": False,
            "insufficient_data_is_not_drift": True,
        },
    }
