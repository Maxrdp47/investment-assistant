from __future__ import annotations

"""Causal classification for historical FX research inputs.

The contract never turns today's revised value into a historical observation.
It records availability, vintages, proxies and structural missingness explicitly
so later research can select only information that was genuinely available.
"""

import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from fx_carry_pit import default_fx_pair_contracts


FX_HISTORICAL_PIT_VERSION = "fx-historical-pit-2026.08.29-v1"
FX_COVERAGE_MATRIX_VERSION = "fx-coverage-matrix-2026.08.29-v1"
FX_COST_PROXY_VERSION = "fx-cost-proxy-2026.08.29-v1"
DEFAULT_HISTORICAL_FX_DB_PATH = (
    Path(__file__).resolve().parent / "runtime" / "fx_historical_pit.sqlite3"
)

SOURCE_TYPES = {
    "HISTORICAL_PIT",
    "HISTORICAL_BACKFILL_NON_PIT",
    "FORWARD_PIT",
    "SHADOW_CONTEXT",
    "PROXY",
}
COVERAGE_STATUSES = {"AVAILABLE_PIT", "AVAILABLE_SHADOW", "UNAVAILABLE", "UNKNOWN"}
FEATURES = (
    "PRICE",
    "POLICY_RATE",
    "RATE_DIFFERENTIAL",
    "EXPECTED_RATE",
    "MACRO_VINTAGE",
    "SURPRISE",
    "COT",
    "SPREAD_BIDASK",
    "INTERVENTION",
    "VOLATILITY",
    "RISK_REGIME",
)


class FxHistoricalPitError(ValueError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: object) -> str | None:
    result = str(value or "").strip()
    return result or None


def _utc(value: object, field: str, *, required: bool = True) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise FxHistoricalPitError(f"{field} fehlt.")
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FxHistoricalPitError(f"{field} ist kein ISO-Zeitpunkt.") from exc
    if stamp.tzinfo is None:
        raise FxHistoricalPitError(f"{field} benötigt eine Zeitzone.")
    return stamp.astimezone(timezone.utc).isoformat()


def _day(value: object, field: str, *, required: bool = True) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise FxHistoricalPitError(f"{field} fehlt.")
        return None
    candidate = text[:10]
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise FxHistoricalPitError(f"{field} ist kein ISO-Datum.") from exc
    return candidate


def _number(value: object, field: str, *, required: bool = True) -> float | None:
    if value is None or value == "":
        if required:
            raise FxHistoricalPitError(f"{field} fehlt.")
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FxHistoricalPitError(f"{field} ist keine Zahl.") from exc
    if not math.isfinite(result):
        raise FxHistoricalPitError(f"{field} muss endlich sein.")
    return result


def normalize_historical_fx_record(record: Mapping[str, object]) -> dict[str, object]:
    feature = str(record.get("feature") or "").strip().upper()
    if feature not in FEATURES:
        raise FxHistoricalPitError(f"Unbekanntes FX-Coverage-Feature: {feature}")
    source_type = str(record.get("source_type") or "").strip().upper()
    if source_type not in SOURCE_TYPES:
        raise FxHistoricalPitError(f"Unbekannter source_type: {source_type}")
    status = str(record.get("coverage_status") or "").strip().upper()
    if status not in COVERAGE_STATUSES:
        raise FxHistoricalPitError(f"Unbekannter Coverage-Status: {status}")
    source = _text(record.get("source"))
    source_record_id = _text(record.get("source_record_id"))
    if not source or not source_record_id:
        raise FxHistoricalPitError("Quelle und Quell-ID sind Pflicht.")

    observation_date = _day(record.get("observation_date"), "observation_date")
    release_at = _utc(record.get("release_at"), "release_at", required=False)
    available_at = _utc(record.get("available_at"), "available_at", required=False)
    first_seen_at = _utc(record.get("first_seen_at"), "first_seen_at")
    imported_at = _utc(record.get("imported_at"), "imported_at")
    vintage_date = _day(record.get("vintage_date"), "vintage_date", required=False)
    value = _number(
        record.get("value"),
        "value",
        required=status in {"AVAILABLE_PIT", "AVAILABLE_SHADOW"},
    )

    if source_type == "HISTORICAL_PIT":
        if not release_at or not available_at:
            raise FxHistoricalPitError(
                "HISTORICAL_PIT benötigt belegte Release- und Availability-Zeitpunkte."
            )
        pit_eligible = status == "AVAILABLE_PIT"
    elif source_type == "FORWARD_PIT":
        available_at = available_at or first_seen_at
        pit_eligible = status == "AVAILABLE_PIT"
    else:
        pit_eligible = False
        if status == "AVAILABLE_PIT":
            raise FxHistoricalPitError(
                f"{source_type} darf nicht als AVAILABLE_PIT markiert werden."
            )

    if available_at and release_at and available_at < release_at:
        raise FxHistoricalPitError("available_at darf nicht vor release_at liegen.")
    revision_number = int(record.get("revision_number") or 0)
    supersedes = _text(record.get("supersedes"))
    if revision_number < 0:
        raise FxHistoricalPitError("revision_number darf nicht negativ sein.")
    if revision_number > 0 and not supersedes:
        raise FxHistoricalPitError("Eine Revision benötigt supersedes.")

    payload: dict[str, object] = {
        "version": FX_HISTORICAL_PIT_VERSION,
        "feature": feature,
        "pair_id": _text(record.get("pair_id")),
        "currency": str(record.get("currency") or "").strip().upper() or None,
        "observation_date": observation_date,
        "release_at": release_at,
        "available_at": available_at,
        "vintage_date": vintage_date,
        "first_seen_at": first_seen_at,
        "imported_at": imported_at,
        "value": value,
        "unit": _text(record.get("unit")),
        "source": source,
        "source_record_id": source_record_id,
        "source_type": source_type,
        "coverage_status": status,
        "pit_eligible": pit_eligible,
        "revision_number": revision_number,
        "revision_status": _text(record.get("revision_status")) or (
            "ORIGINAL" if revision_number == 0 else "REVISED"
        ),
        "supersedes": supersedes,
        "metadata": dict(record.get("metadata") or {}),
        "today_revised_value_backdated": False,
    }
    identity = {
        "feature": feature,
        "pair_id": payload["pair_id"],
        "currency": payload["currency"],
        "observation_date": observation_date,
        "source": source,
        "source_record_id": source_record_id,
        "revision_number": revision_number,
    }
    payload["record_id"] = f"fxhist-{_fingerprint(identity)[:32]}"
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"first_seen_at", "imported_at"}
    }
    payload["content_fingerprint"] = _fingerprint(content)
    payload["record_fingerprint"] = _fingerprint(payload)
    return payload


def surprise_from_observations(
    *,
    expected_value: object,
    actual_value: object,
    expected_known_at: object | None,
    release_at: object,
) -> dict[str, object]:
    release = _utc(release_at, "release_at")
    if expected_value in (None, "") or expected_known_at in (None, ""):
        return {
            "status": "UNKNOWN",
            "surprise": None,
            "reason": "PRE_RELEASE_EXPECTATION_UNAVAILABLE",
            "release_at": release,
        }
    expected_known = _utc(expected_known_at, "expected_known_at")
    if str(expected_known) > str(release):
        raise FxHistoricalPitError("Die Erwartung war vor dem Release nicht bekannt.")
    expected = _number(expected_value, "expected_value")
    actual = _number(actual_value, "actual_value")
    result = {
        "status": "AVAILABLE_PIT",
        "surprise": float(actual) - float(expected),
        "expected": expected,
        "actual": actual,
        "expected_known_at": expected_known,
        "release_at": release,
    }
    result["fingerprint"] = _fingerprint(result)
    return result


def policy_rate_differential(
    *,
    base_rate: object | None,
    quote_rate: object | None,
    base_expected_rate: object | None = None,
    quote_expected_rate: object | None = None,
) -> dict[str, object]:
    actual = (
        None
        if base_rate in (None, "") or quote_rate in (None, "")
        else _number(base_rate, "base_rate") - _number(quote_rate, "quote_rate")
    )
    expected = (
        None
        if base_expected_rate in (None, "") or quote_expected_rate in (None, "")
        else _number(base_expected_rate, "base_expected_rate")
        - _number(quote_expected_rate, "quote_expected_rate")
    )
    payload: dict[str, object] = {
        "actual_rate_differential": actual,
        "expected_rate_differential": expected,
        "actual_and_expected_separated": True,
        "carry_direction": (
            "LONG_BASE"
            if actual is not None and actual > 0
            else "SHORT_BASE"
            if actual is not None and actual < 0
            else "NEUTRAL"
            if actual == 0
            else "UNKNOWN"
        ),
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def cot_release_eligibility(
    *,
    report_date: object,
    cutoff: object,
    published_at: object | None,
    first_seen_at: object | None,
    acquisition_mode: str,
) -> dict[str, object]:
    report_day = _day(report_date, "report_date")
    cutoff_utc = _utc(cutoff, "cutoff")
    published = _utc(published_at, "published_at", required=False)
    first_seen = _utc(first_seen_at, "first_seen_at", required=False)
    mode = str(acquisition_mode or "").strip().upper()
    if published:
        eligible_at = published
        basis = "VERIFIED_PUBLISHED_AT"
    elif mode == "FORWARD" and first_seen:
        eligible_at = first_seen
        basis = "FORWARD_FIRST_SEEN_AT"
    else:
        eligible_at = None
        basis = "HISTORICAL_RELEASE_UNVERIFIED"
    eligible = bool(eligible_at and str(eligible_at) <= str(cutoff_utc))
    return {
        "report_date": report_day,
        "cutoff": cutoff_utc,
        "pit_eligible": eligible,
        "eligible_at": eligible_at,
        "availability_basis": basis,
        "classification": "AVAILABLE_PIT" if eligible else "AVAILABLE_SHADOW",
    }


def fx_cost_proxy_contract(
    pair_groups: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    groups = {
        str(name): {
            "base_cost_proxy": values.get("base_cost_proxy"),
            "conservative_cost_proxy": values.get("conservative_cost_proxy"),
            "stress_cost_proxy": values.get("stress_cost_proxy"),
            "unit": values.get("unit") or "bps",
            "classification": "PROXY",
            "observed_historical_spread": False,
            "source": values.get("source") or "research assumption; not observed",
        }
        for name, values in sorted((pair_groups or {}).items())
    }
    payload: dict[str, object] = {
        "version": FX_COST_PROXY_VERSION,
        "pair_groups": groups,
        "historical_bid_ask_available": False,
        "proxy_is_observation": False,
        "numeric_values_invented": False if not groups else None,
        "multiple_cost_levels_supported": True,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def fx_coverage_matrix(
    records: Sequence[Mapping[str, object]],
    *,
    pair_ids: Sequence[str] | None = None,
    years: Sequence[int | str] | None = None,
) -> dict[str, object]:
    normalized = [normalize_historical_fx_record(record) for record in records]
    pairs = sorted(pair_ids or default_fx_pair_contracts())
    observed_years = {str(item["observation_date"])[:4] for item in normalized}
    year_values = sorted({str(year) for year in (years or observed_years)})
    matrix: dict[str, dict[str, dict[str, str]]] = {}
    status_rank = {"UNKNOWN": 0, "UNAVAILABLE": 1, "AVAILABLE_SHADOW": 2, "AVAILABLE_PIT": 3}
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for item in normalized:
        pair_id = str(item.get("pair_id") or "")
        if not pair_id:
            continue
        grouped[(pair_id, str(item["observation_date"])[:4], str(item["feature"]))].append(
            str(item["coverage_status"])
        )
    for pair_id in pairs:
        matrix[pair_id] = {}
        for year in year_values:
            matrix[pair_id][year] = {}
            for feature in FEATURES:
                statuses = grouped.get((pair_id, year, feature), [])
                matrix[pair_id][year][feature] = (
                    max(statuses, key=status_rank.get) if statuses else "UNAVAILABLE"
                )
    counts = Counter(
        status
        for pair in matrix.values()
        for year in pair.values()
        for status in year.values()
    )
    payload: dict[str, object] = {
        "version": FX_COVERAGE_MATRIX_VERSION,
        "pairs": pairs,
        "years": year_values,
        "features": list(FEATURES),
        "matrix": matrix,
        "status_counts": dict(sorted(counts.items())),
        "missing_is_false": False,
        "historical_backfill_promoted_automatically": False,
    }
    payload["coverage_fingerprint"] = _fingerprint(payload)
    return payload


def historical_fx_inventory(
    records: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    normalized = [normalize_historical_fx_record(item) for item in records]
    pairs = sorted({str(item["pair_id"]) for item in normalized if item.get("pair_id")})
    dates = sorted(str(item["observation_date"]) for item in normalized)
    feature_counts = Counter(str(item["feature"]) for item in normalized)
    source_counts = Counter(str(item["source_type"]) for item in normalized)
    payload: dict[str, object] = {
        "version": FX_HISTORICAL_PIT_VERSION,
        "pairs": pairs,
        "record_n": len(normalized),
        "period_start": dates[0] if dates else None,
        "period_end": dates[-1] if dates else None,
        "feature_counts": dict(sorted(feature_counts.items())),
        "source_type_counts": dict(sorted(source_counts.items())),
        "pit_eligible_n": sum(bool(item["pit_eligible"]) for item in normalized),
        "shadow_or_non_pit_n": sum(not bool(item["pit_eligible"]) for item in normalized),
        "today_revised_value_backdated": False,
    }
    payload["inventory_fingerprint"] = _fingerprint(payload)
    return payload


def initialize_historical_fx_store(
    path: Path = DEFAULT_HISTORICAL_FX_DB_PATH,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS historical_fx_records (
                record_id TEXT PRIMARY KEY,
                pair_id TEXT,
                feature TEXT NOT NULL,
                observation_date TEXT NOT NULL,
                source_type TEXT NOT NULL,
                pit_eligible INTEGER NOT NULL,
                record_fingerprint TEXT NOT NULL UNIQUE,
                record_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS historical_fx_coverage_snapshots (
                coverage_fingerprint TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                coverage_json TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS historical_fx_records_no_update
            BEFORE UPDATE ON historical_fx_records BEGIN SELECT RAISE(ABORT, 'historical FX records append-only'); END;
            CREATE TRIGGER IF NOT EXISTS historical_fx_records_no_delete
            BEFORE DELETE ON historical_fx_records BEGIN SELECT RAISE(ABORT, 'historical FX records append-only'); END;
            CREATE TRIGGER IF NOT EXISTS historical_fx_coverage_no_update
            BEFORE UPDATE ON historical_fx_coverage_snapshots BEGIN SELECT RAISE(ABORT, 'historical FX coverage append-only'); END;
            CREATE TRIGGER IF NOT EXISTS historical_fx_coverage_no_delete
            BEFORE DELETE ON historical_fx_coverage_snapshots BEGIN SELECT RAISE(ABORT, 'historical FX coverage append-only'); END;
            """
        )


def append_historical_fx_records(
    records: Iterable[Mapping[str, object]],
    *,
    path: Path = DEFAULT_HISTORICAL_FX_DB_PATH,
) -> dict[str, int]:
    initialize_historical_fx_store(path)
    inserted = deduplicated = 0
    with sqlite3.connect(path) as connection:
        for raw in records:
            item = normalize_historical_fx_record(raw)
            encoded = _canonical_json(item)
            existing = connection.execute(
                "SELECT record_json FROM historical_fx_records WHERE record_id=?",
                (item["record_id"],),
            ).fetchone()
            if existing is not None:
                previous = json.loads(str(existing[0]))
                if previous.get("content_fingerprint") != item["content_fingerprint"]:
                    raise FxHistoricalPitError(
                        "Dieselbe historische Record-ID besitzt abweichenden Inhalt."
                    )
                deduplicated += 1
                continue
            connection.execute(
                "INSERT INTO historical_fx_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["record_id"],
                    item["pair_id"],
                    item["feature"],
                    item["observation_date"],
                    item["source_type"],
                    int(bool(item["pit_eligible"])),
                    item["record_fingerprint"],
                    encoded,
                ),
            )
            inserted += 1
    return {"inserted": inserted, "deduplicated": deduplicated}


def load_historical_fx_records(
    *,
    path: Path = DEFAULT_HISTORICAL_FX_DB_PATH,
) -> list[dict[str, object]]:
    if not Path(path).exists():
        return []
    initialize_historical_fx_store(path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT record_json FROM historical_fx_records ORDER BY observation_date, pair_id, record_id"
        ).fetchall()
    return [json.loads(str(row[0])) for row in rows]


def append_fx_coverage_snapshot(
    coverage: Mapping[str, object],
    *,
    created_at: object,
    path: Path = DEFAULT_HISTORICAL_FX_DB_PATH,
) -> bool:
    initialize_historical_fx_store(path)
    payload = dict(coverage)
    fingerprint = str(payload.get("coverage_fingerprint") or "")
    comparable = {key: value for key, value in payload.items() if key != "coverage_fingerprint"}
    if not fingerprint or _fingerprint(comparable) != fingerprint:
        raise FxHistoricalPitError("Coverage-Fingerprint ist ungültig.")
    timestamp = _utc(created_at, "created_at")
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO historical_fx_coverage_snapshots VALUES (?, ?, ?)",
            (fingerprint, timestamp, _canonical_json(payload)),
        )
    return bool(cursor.rowcount)
