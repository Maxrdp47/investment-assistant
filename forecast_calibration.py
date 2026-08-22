from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from forecast_learning import build_learning_dataset_report
from forecast_metrics import probability_metrics
from forecast_monitoring import build_forecast_monitoring_report
from forecast_store import (
    DEFAULT_DATABASE_PATH,
    FORECAST_MODEL_ENTRY,
    database,
    forecast_model_label,
    initialize_database,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CALIBRATION_PATH = PROJECT_ROOT / "runtime" / "calibration_profile.json"
CALIBRATION_PROFILE_VERSION = "2026.08.09-v3"
CAUTIOUS_MIN_CASES = 20
MANUAL_REVIEW_MIN_CASES = 51


def calibration_maturity(cases: int) -> tuple[str, str]:
    if cases < CAUTIOUS_MIN_CASES:
        return "collect_only", "Datenbasis zu klein – nur sammeln, keine Kalibrierung."
    if cases < MANUAL_REVIEW_MIN_CASES:
        return "cautious_review", "Vorsichtiger Prüfhinweis; keine automatische Änderung."
    return "manual_review_allowed", "Manuelle Kalibrierungsprüfung erlaubt; keine automatische Änderung."


def _rounded(value: object, digits: int = 2) -> float | None:
    return round(float(value), digits) if value is not None else None


def _segment_from_row(row: dict) -> dict:
    cases = int(row.get("cases") or 0)
    maturity, maturity_label = calibration_maturity(cases)
    return {
        "model_type": str(row.get("model_type") or FORECAST_MODEL_ENTRY),
        "model_label": forecast_model_label(row.get("model_type")),
        "logic_version": str(row.get("logic_version") or "Unbekannt"),
        "asset_type": str(row.get("asset_type") or "Unbekannt"),
        "horizon": str(row.get("horizon") or "Unbekannt"),
        "evaluated_cases": cases,
        "direction_hits": int(row.get("hits") or 0),
        "direction_hit_rate_pct": _rounded(row.get("hit_rate_pct"), 1),
        "average_return_pct": _rounded(row.get("average_return_pct")),
        "average_absolute_deviation_pct": _rounded(row.get("average_deviation_pct")),
        "target_hit_rate_pct": _rounded(row.get("target_hit_rate_pct"), 1),
        "risk_hit_rate_pct": _rounded(row.get("risk_hit_rate_pct"), 1),
        "probability_evaluated": int(row.get("probability_evaluated") or 0),
        "brier_score": _rounded(row.get("brier_score"), 4),
        "log_loss": _rounded(row.get("log_loss"), 4),
        "calibration_error_pct": _rounded(row.get("calibration_error_pct"), 1),
        "calibration_bias_pct": _rounded(row.get("calibration_bias_pct"), 1),
        "maturity": maturity,
        "maturity_label": maturity_label,
    }


def _manual_review_suggestions(segments: list[dict]) -> list[dict]:
    suggestions: list[dict] = []
    for segment in segments:
        cases = int(segment["evaluated_cases"])
        hit_rate = segment.get("direction_hit_rate_pct")
        deviation = segment.get("average_absolute_deviation_pct")
        probability_cases = int(segment.get("probability_evaluated") or 0)
        if cases < CAUTIOUS_MIN_CASES:
            continue
        scope = (
            f"{segment['model_label']} · {segment['asset_type']} · {segment['horizon']} "
            f"· {segment['logic_version']}"
        )
        if hit_rate is not None and float(hit_rate) < 50.0:
            suggestions.append(
                {
                    "scope": scope,
                    "priority": "hoch" if float(hit_rate) < 45.0 and cases >= MANUAL_REVIEW_MIN_CASES else "mittel",
                    "evidence": f"{cases} ausgewertete Fälle, Richtungstrefferquote {float(hit_rate):.1f} %.",
                    "suggestion": "Signal- und Marktphasenlogik dieses Segments manuell untersuchen.",
                    "automatic_change": False,
                }
            )
        if deviation is not None and float(deviation) > 15.0:
            suggestions.append(
                {
                    "scope": scope,
                    "priority": "mittel",
                    "evidence": (
                        f"{cases} ausgewertete Fälle, mittlere absolute Kursbereichsabweichung "
                        f"{float(deviation):.2f} %."
                    ),
                    "suggestion": "Horizont-spezifische Kursbereichslogik manuell prüfen.",
                    "automatic_change": False,
                }
            )
        if probability_cases >= CAUTIOUS_MIN_CASES and segment.get("brier_score") is not None:
            brier = float(segment["brier_score"])
            calibration_error = segment.get("calibration_error_pct")
            if brier > 0.25 or (
                calibration_error is not None and float(calibration_error) > 10.0
            ):
                suggestions.append(
                    {
                        "scope": scope,
                        "priority": "hoch" if probability_cases >= MANUAL_REVIEW_MIN_CASES else "mittel",
                        "evidence": (
                            f"{probability_cases} Wahrscheinlichkeitsfälle, Brier Score {brier:.4f}, "
                            f"Kalibrierungsfehler {float(calibration_error or 0):.1f} %."
                        ),
                        "suggestion": "Rohwahrscheinlichkeit zeitlich getrennt kalibrieren und gegen einen Challenger prüfen.",
                        "automatic_change": False,
                    }
                )
    return suggestions


def build_calibration_profile(
    database_path: Path = DEFAULT_DATABASE_PATH,
    generated_at: str | None = None,
) -> dict:
    generated_timestamp = generated_at or datetime.now().astimezone().isoformat()
    try:
        monitoring_day = datetime.fromisoformat(generated_timestamp).date()
    except (TypeError, ValueError):
        monitoring_day = datetime.now().astimezone().date()
    initialize_database(database_path)
    with database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT COALESCE(NULLIF(f.model_type, ''), 'entry_analysis') AS model_type,
                   f.logic_version,
                   f.asset_type,
                   h.horizon,
                   COUNT(e.direction_hit) AS cases,
                   SUM(CASE WHEN e.direction_hit = 1 THEN 1 ELSE 0 END) AS hits,
                   AVG(CASE WHEN e.direction_hit IS NOT NULL THEN e.direction_hit END) * 100 AS hit_rate_pct,
                   AVG(e.actual_return_pct) AS average_return_pct,
                   AVG(ABS(e.deviation_pct)) AS average_deviation_pct,
                   AVG(CASE WHEN e.target_hit IS NOT NULL THEN e.target_hit END) * 100 AS target_hit_rate_pct,
                   AVG(CASE WHEN e.risk_hit IS NOT NULL THEN e.risk_hit END) * 100 AS risk_hit_rate_pct
            FROM forecasts f
            JOIN forecast_horizons h ON h.forecast_id = f.id
            JOIN forecast_evaluations e
              ON e.forecast_id = f.id AND e.horizon = h.horizon
            WHERE e.direction_hit IS NOT NULL
            GROUP BY COALESCE(NULLIF(f.model_type, ''), 'entry_analysis'),
                     f.logic_version, f.asset_type, h.horizon
            ORDER BY model_type, f.logic_version, f.asset_type, h.days, h.horizon
            """
        ).fetchall()
        totals = connection.execute(
            """
            SELECT COUNT(e.direction_hit) AS cases,
                   SUM(CASE WHEN e.direction_hit = 1 THEN 1 ELSE 0 END) AS hits,
                   MAX(e.evaluated_at) AS data_through
            FROM forecast_evaluations e
            WHERE e.direction_hit IS NOT NULL
            """
        ).fetchone()
        probability_rows = connection.execute(
            """
            SELECT COALESCE(NULLIF(f.model_type, ''), 'entry_analysis') AS model_type,
                   f.logic_version, f.asset_type, h.horizon, h.probability_up,
                   CASE WHEN e.actual_return_pct > 0 THEN 1 ELSE 0 END AS outcome_up
            FROM forecasts f
            JOIN forecast_horizons h ON h.forecast_id = f.id
            JOIN forecast_evaluations e
              ON e.forecast_id = f.id AND e.horizon = h.horizon
            WHERE h.probability_up IS NOT NULL
              AND e.actual_return_pct IS NOT NULL
            ORDER BY f.id, h.days
            """
        ).fetchall()

    probability_by_segment: dict[tuple[str, str, str, str], list[tuple[float, int]]] = {}
    for row in probability_rows:
        key = (
            str(row["model_type"]),
            str(row["logic_version"]),
            str(row["asset_type"]),
            str(row["horizon"]),
        )
        probability_by_segment.setdefault(key, []).append(
            (row["probability_up"], row["outcome_up"])
        )
    segments = []
    for row in rows:
        item = dict(row)
        key = (
            str(item.get("model_type") or FORECAST_MODEL_ENTRY),
            str(item.get("logic_version") or "Unbekannt"),
            str(item.get("asset_type") or "Unbekannt"),
            str(item.get("horizon") or "Unbekannt"),
        )
        item.update(probability_metrics(probability_by_segment.get(key, [])))
        segments.append(_segment_from_row(item))
    overall_probability_metrics = probability_metrics(
        [(row["probability_up"], row["outcome_up"]) for row in probability_rows]
    )
    total_cases = int(totals["cases"] or 0)
    total_hits = int(totals["hits"] or 0)
    maturity, maturity_label = calibration_maturity(total_cases)
    learning_readiness = {
        key: value
        for key, value in build_learning_dataset_report(database_path).items()
        if key != "generated_at"
    }
    monitoring = build_forecast_monitoring_report(database_path, as_of=monitoring_day)
    stable_content = {
        "profile_version": CALIBRATION_PROFILE_VERSION,
        "scope": "forecast_horizon_evaluations",
        "data_through": totals["data_through"],
        "minimum_cases": {
            "cautious_review": CAUTIOUS_MIN_CASES,
            "manual_review_allowed": MANUAL_REVIEW_MIN_CASES,
        },
        "overall": {
            "evaluated_cases": total_cases,
            "direction_hits": total_hits,
            "direction_hit_rate_pct": round(total_hits / total_cases * 100, 1) if total_cases else None,
            **overall_probability_metrics,
            "maturity": maturity,
            "maturity_label": maturity_label,
        },
        "segments": segments,
        "learning_readiness": learning_readiness,
        "monitoring": monitoring,
        "manual_review_suggestions": _manual_review_suggestions(segments),
        "guardrails": {
            "production_weights_changed": False,
            "production_rules_changed": False,
            "automatic_rule_activation": False,
            "manual_review_required": True,
            "missing_data_is_not_estimated": True,
            "raw_probabilities_are_uncalibrated": True,
            "shadow_learning_only_after_readiness_gate": True,
            "drift_monitoring_is_observe_only": True,
        },
    }
    fingerprint_source = json.dumps(
        stable_content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        **stable_content,
        "generated_at": generated_timestamp,
        "data_fingerprint": hashlib.sha256(fingerprint_source).hexdigest(),
    }


def write_calibration_profile(
    database_path: Path = DEFAULT_DATABASE_PATH,
    output_path: Path = DEFAULT_CALIBRATION_PATH,
) -> dict:
    profile = build_calibration_profile(database_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    )
    temporary_path = Path(handle.name)
    try:
        with handle:
            json.dump(profile, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return profile


def load_calibration_profile(path: Path = DEFAULT_CALIBRATION_PATH) -> dict | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None
