from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any

from forecast_probabilities import RAW_PROBABILITY_SCHEMA_VERSION


MEASUREMENT_CONTRACT_VERSION = "l0-measurement-2026.08.11-v4"
FEATURE_SCHEMA_VERSION = "entry-point-in-time-2026.08.11-v4"
SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS = {
    "l0-measurement-2026.08.09-v3",
    MEASUREMENT_CONTRACT_VERSION,
}
SUPPORTED_FEATURE_SCHEMA_VERSIONS = {
    "entry-point-in-time-2026.08.09-v3",
    FEATURE_SCHEMA_VERSION,
}
LABEL_SCHEMA_VERSION = "entry-outcome-2026.08.09-v1"
BENCHMARK_SCHEMA_VERSION = "entry-benchmarks-2026.08.09-v1"
COST_SCHEMA_VERSION = "entry-costs-2026.08.09-v1"
QUALITY_SCHEMA_VERSION = "entry-quality-2026.08.09-v1"


def _normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalized(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return _normalized(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalized(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _valid_timestamp(value: object) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _positive_number(value: object) -> bool:
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def _point_in_time_features(snapshot: dict) -> dict:
    return {
        "identity": {
            "ticker": str(snapshot.get("ticker") or "").upper(),
            "asset_name": snapshot.get("asset_name"),
            "asset_type": snapshot.get("asset_type"),
            "region": snapshot.get("region"),
            "category": snapshot.get("category"),
        },
        "observation": {
            "created_at": snapshot.get("created_at"),
            "run_date": snapshot.get("run_date"),
            "source": snapshot.get("source"),
            "logic_version": snapshot.get("logic_version"),
            "model_type": snapshot.get("model_type") or "entry_analysis",
        },
        "sampling": snapshot.get("sampling") or {},
        "pricing": {
            "price_original": snapshot.get("price_original"),
            "original_currency": snapshot.get("original_currency"),
            "fx_rate_to_eur": snapshot.get("fx_rate_to_eur"),
            "price_eur": snapshot.get("price_eur"),
        },
        "decision_inputs": {
            "asset_quality": snapshot.get("asset_quality"),
            "buy_signal": snapshot.get("buy_signal"),
            "market_phase": snapshot.get("market_phase"),
            "predicted_direction": snapshot.get("predicted_direction"),
            "confidence": snapshot.get("confidence"),
            "data_quality": snapshot.get("data_quality"),
            "data_quality_label": snapshot.get("data_quality_label"),
            "history_rows": snapshot.get("history_rows"),
            "data_coverage": snapshot.get("data_coverage"),
        },
        "horizon_collection_policy": snapshot.get("horizon_collection_policy") or {},
        "signal_snapshot": snapshot.get("signal_snapshot") or {},
        "probability_snapshot": snapshot.get("probability_snapshot") or {},
        "simple_trend_baseline": snapshot.get("simple_trend_baseline") or {},
        "market_benchmark_snapshot": snapshot.get("market_benchmark_snapshot") or {},
        "module_scores": snapshot.get("module_scores") or [],
        "uncertainties": snapshot.get("uncertainties") or [],
        "scenarios": snapshot.get("scenarios") or [],
        "professional_decision": snapshot.get("professional_decision") or {},
        "horizons": snapshot.get("horizons") or [],
    }


def _quality_contract(snapshot: dict) -> dict:
    checks = {
        "timezone_aware_cutoff": _valid_timestamp(snapshot.get("created_at")),
        "ticker_present": bool(str(snapshot.get("ticker") or "").strip()),
        "positive_entry_price_eur": _positive_number(snapshot.get("price_eur")),
        "known_direction": str(snapshot.get("predicted_direction") or "")
        in {"Steigend", "Fallend", "Seitwärts"},
        "signal_snapshot_present": bool(snapshot.get("signal_snapshot")),
        "module_scores_present": bool(snapshot.get("module_scores")),
        "horizons_present": bool(snapshot.get("horizons")),
    }
    original_currency = str(snapshot.get("original_currency") or "").upper()
    checks["historic_fx_snapshot_present"] = (
        original_currency == "EUR" or _positive_number(snapshot.get("fx_rate_to_eur"))
    )
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": QUALITY_SCHEMA_VERSION,
        "checks": checks,
        "failed_checks": failed,
        "forward_evaluation_eligible": not failed,
        "missing_or_weak_data_policy": "Nicht schätzen; als Datenlücke markieren und aus ungeeigneten Qualitätsmetriken ausschließen.",
    }


def _measurement_contract(snapshot: dict, quality: dict) -> dict:
    horizons = [
        {
            "horizon": item.get("horizon"),
            "calendar_days": item.get("days"),
            "expected_direction": item.get("expected_direction"),
            "expected_low_eur": item.get("expected_low_eur"),
            "expected_high_eur": item.get("expected_high_eur"),
            "target_eur": item.get("target_eur"),
            "risk_eur": item.get("risk_eur"),
            "probability_up": item.get("probability_up"),
            "probability_schema_version": item.get("probability_schema_version"),
        }
        for item in snapshot.get("horizons") or []
    ]
    available_benchmarks = {
        "no_change": {"expected_return_pct": 0.0, "direction": "Seitwärts"},
        "always_up": {"direction": "Steigend"},
    }
    missing_benchmarks: list[str] = []
    simple_trend = snapshot.get("simple_trend_baseline") or {}
    if simple_trend.get("status") == "available":
        available_benchmarks["simple_trend"] = simple_trend
    else:
        missing_benchmarks.append("simple_trend")
    market_benchmark = snapshot.get("market_benchmark_snapshot") or {}
    if market_benchmark.get("status") == "available":
        available_benchmarks["market_benchmark"] = market_benchmark
    else:
        missing_benchmarks.append("market_benchmark")
    return {
        "contract_version": MEASUREMENT_CONTRACT_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_contract": {
            "schema_version": LABEL_SCHEMA_VERSION,
            "valuation_price": "Erster verfügbarer automatisch adjustierter Tages-Schlusskurs am oder nach dem Fälligkeitstag.",
            "maximum_calendar_delay_days": 7,
            "currency_rule": "Historischer FX-Kurs des tatsächlichen Bewertungstags; kein aktueller Nachschlagekurs.",
            "direction_hit": {
                "Steigend": "actual_return_pct > 0",
                "Fallend": "actual_return_pct < 0",
                "Seitwärts": "abs(actual_return_pct) <= 3",
            },
            "range_hit": "actual_price_eur liegt einschließlich Grenzen in der gespeicherten Erwartungsspanne.",
            "target_and_risk": "Berührung bis einschließlich tatsächlichem Bewertungstag anhand gespeicherter Tages-Hochs/-Tiefs.",
            "missing_result": "Kein Treffer und kein Fehler; Ergebnis bleibt offen.",
            "horizons": horizons,
        },
        "benchmark_contract": {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "required": ["no_change", "always_up", "simple_trend", "market_benchmark"],
            "available_at_snapshot": available_benchmarks,
            "not_yet_captured": missing_benchmarks,
            "comparison_policy": "Keine Modellfreigabe ohne zeitlich getrennten Vergleich gegen alle erforderlichen Referenzen.",
        },
        "probability_contract": {
            "schema_version": RAW_PROBABILITY_SCHEMA_VERSION,
            "event": "actual_return_pct > 0",
            "source": "Zum Beobachtungszeitpunkt gespeicherte Bull-/Base-/Bear-Verteilung und numerische Szenarioziele.",
            "calibration_status": "uncalibrated",
            "scoring_rules": ["brier_score", "log_loss", "expected_calibration_error"],
            "eligibility": (
                "scoreable"
                if (snapshot.get("probability_snapshot") or {}).get("status") == "available"
                else "missing"
            ),
            "limitation": "Bis zu eigenen Horizontmodellen gilt dieselbe Rohwahrscheinlichkeit für alle Zeiträume; sie ist keine kalibrierte Erfolgszusage.",
        },
        "cost_contract": {
            "schema_version": COST_SCHEMA_VERSION,
            "raw_forecast_metrics_round_trip_bps": 0,
            "reason": "Richtung, Spanne und Abweichung messen zunächst Prognosegüte des Marktkurses, nicht eine ausgeführte Order.",
            "strategy_return_policy": "Rendite-, Expected-Value- und Swing-Metriken benötigen separat versionierte realistische Kosten; derzeit nicht anwendbar.",
        },
        "quality_contract": quality,
        "leakage_guard": {
            "observation_cutoff_at": snapshot.get("created_at"),
            "allowed_inputs": "Nur im unveränderbaren Feature-Snapshot gespeicherte Werte, die spätestens am Beobachtungszeitpunkt vorlagen.",
            "forbidden_inputs": [
                "spätere Kurse oder revidierte Historien",
                "spätere Fundamentaldaten, Nachrichten oder Ereignisse",
                "Ergebnis- und Kalibrierungsdaten desselben oder eines späteren Zeitraums",
                "getrennte Recovery-Daten als rückwirkende Prognose",
            ],
            "validation_split_policy": "Zeitlich vorwärts; kein zufälliges Mischen zukünftiger Beobachtungen in Training oder Kalibrierung.",
            "mutation_policy": "Feature-Snapshot und Vertrag werden nach INSERT nicht aktualisiert.",
        },
    }


def build_measurement_record(snapshot: dict) -> dict:
    features = _point_in_time_features(snapshot)
    quality = _quality_contract(snapshot)
    contract = _measurement_contract(snapshot, quality)
    payload = {
        "observation_cutoff_at": snapshot.get("created_at"),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_snapshot": features,
        "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
        "measurement_contract": contract,
    }
    return {
        "observation_cutoff_at": snapshot.get("created_at"),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_snapshot_json": canonical_json(features),
        "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
        "measurement_contract_json": canonical_json(contract),
        "snapshot_fingerprint": hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
    }


def verify_measurement_record(record: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    try:
        features = json.loads(str(record.get("feature_snapshot_json") or ""))
        contract = json.loads(str(record.get("measurement_contract_json") or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False, ["measurement_json_invalid"]
    if not isinstance(features, dict) or not isinstance(contract, dict):
        return False, ["measurement_json_invalid"]
    payload = {
        "observation_cutoff_at": record.get("observation_cutoff_at"),
        "feature_schema_version": record.get("feature_schema_version"),
        "feature_snapshot": features,
        "measurement_contract_version": record.get("measurement_contract_version"),
        "measurement_contract": contract,
    }
    expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    if expected != str(record.get("snapshot_fingerprint") or ""):
        reasons.append("snapshot_fingerprint_mismatch")
    if record.get("feature_schema_version") not in SUPPORTED_FEATURE_SCHEMA_VERSIONS:
        reasons.append("unknown_feature_schema")
    if record.get("measurement_contract_version") not in SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS:
        reasons.append("unknown_measurement_contract")
    cutoff = record.get("observation_cutoff_at")
    if not _valid_timestamp(cutoff):
        reasons.append("observation_cutoff_invalid")
    if contract.get("leakage_guard", {}).get("observation_cutoff_at") != cutoff:
        reasons.append("leakage_cutoff_mismatch")
    return not reasons, reasons
