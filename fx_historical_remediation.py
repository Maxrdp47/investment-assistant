from __future__ import annotations

"""Versioned, non-imputing remediation for historical FX OHLC source bars."""

import hashlib
import json
import os
import sqlite3
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence


FX_HISTORICAL_REMEDIATION_VERSION = "fx-historical-pit-remediation-2026.09.01-v2"
FX_HISTORICAL_ACTIVE_DATASET_VERSION = "fx-historical-pit-2026.09.01-v2"


class FxHistoricalRemediationError(RuntimeError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FxHistoricalRemediationError(f"{field} ist nicht numerisch.") from exc
    if not number > 0:
        raise FxHistoricalRemediationError(f"{field} muss positiv sein.")
    return number


def fx_ohlc_envelope_violations(
    ohlc: Mapping[str, object], *, pair_id: str
) -> list[dict[str, object]]:
    values = {
        key: _number(ohlc.get(key), key)
        for key in ("open", "high", "low", "close")
    }
    low = values["low"]
    high = values["high"]
    pip_size = 0.01 if str(pair_id).upper().endswith("/JPY") else 0.0001
    violations: list[dict[str, object]] = []

    def add(field: str, boundary: str, absolute: float, reference: float) -> None:
        violations.append(
            {
                "field": field.upper(),
                "violation": boundary,
                "absolute": absolute,
                "pips": absolute / pip_size,
                "relative": absolute / reference if reference else None,
                "relative_pct": absolute / reference * 100 if reference else None,
            }
        )

    if low > high:
        add("low", "LOW_ABOVE_HIGH", low - high, high)
    for field in ("open", "close"):
        value = values[field]
        if value < low:
            add(field, f"{field.upper()}_BELOW_LOW", low - value, low)
        if value > high:
            add(field, f"{field.upper()}_ABOVE_HIGH", value - high, high)
    return violations


def _invalid_manifest_row(record: Mapping[str, object]) -> dict[str, object]:
    metadata = dict(record.get("metadata") or {})
    ohlc = dict(metadata.get("ohlc") or {})
    pair_id = str(record.get("pair_id") or "")
    violations = fx_ohlc_envelope_violations(ohlc, pair_id=pair_id)
    if not violations:
        raise FxHistoricalRemediationError("Manifest-Zeile besitzt keine Hüllenverletzung.")
    payload: dict[str, object] = {
        "record_id": record.get("record_id"),
        "pair_id": pair_id,
        "observation_date": record.get("observation_date"),
        "session_date": record.get("observation_date"),
        "open": ohlc.get("open"),
        "high": ohlc.get("high"),
        "low": ohlc.get("low"),
        "close": ohlc.get("close"),
        "violation_types": sorted({str(item["violation"]) for item in violations}),
        "violations": violations,
        "maximum_absolute_violation": max(float(item["absolute"]) for item in violations),
        "maximum_pip_violation": max(float(item["pips"]) for item in violations),
        "maximum_relative_violation_pct": max(
            float(item["relative_pct"]) for item in violations
        ),
        "raw_source": record.get("source"),
        "import_source": "fx_historical_pit.sqlite3/historical_fx_records",
        "source_record_id": record.get("source_record_id"),
        "source_release_at": record.get("release_at"),
        "source_available_at": record.get("available_at"),
        "first_seen_at": record.get("first_seen_at"),
        "imported_at": record.get("imported_at"),
        "source_ticker": metadata.get("source_ticker"),
        "pair_orientation": "DIRECT"
        if metadata.get("source_is_inverse") is False
        else "INVERSE",
        "inversion_applied": bool(metadata.get("source_is_inverse")),
        "inversion_formula": (
            "O'=1/O,C'=1/C,H'=1/L,L'=1/H"
            if metadata.get("source_is_inverse")
            else "NOT_APPLICABLE_DIRECT_PAIR"
        ),
        "session_timezone": metadata.get("session_timezone"),
        "canonical_daily_close": metadata.get("canonical_daily_close"),
        "session_availability_transformation": metadata.get("availability_basis"),
        "rounding": "NO_IMPORT_ROUNDING_DOCUMENTED",
        "adjusted": metadata.get("adjusted"),
        "provider_version": "UNKNOWN_NOT_PRESERVED_BY_V1_IMPORT",
        "import_version": "fx-historical-pit-2026.08.29-v1",
        "store_version": "fx-historical-pit-2026.08.29-v1",
        "provider_or_session_root_cause": "UNKNOWN_NOT_PROVABLE_FROM_PRESERVED_V1_MATERIAL",
        "pipeline_admission_root_cause": (
            "ASYMMETRIC_ENVELOPE_VALIDATOR_MISSED_LOW_SIDE_VIOLATIONS"
        ),
        "classification": "INVALID_SOURCE_BAR",
        "active_pit_allowed": False,
        "remediation": "EXCLUDED_FROM_V2_ACTIVE_PIT_WITHOUT_REPLACEMENT",
        "clipped": False,
        "imputed": False,
        "interpolated": False,
        "external_source_used_as_historical_truth": False,
    }
    payload["invalid_bar_fingerprint"] = fingerprint(payload)
    return payload


def _longest_business_gap(days: Sequence[str]) -> dict[str, object] | None:
    ordered = sorted({date.fromisoformat(day[:10]) for day in days})
    if len(ordered) < 2:
        return None
    best: dict[str, object] | None = None
    for left, right in zip(ordered, ordered[1:]):
        cursor = left + timedelta(days=1)
        business_days = 0
        while cursor < right:
            business_days += int(cursor.weekday() < 5)
            cursor += timedelta(days=1)
        candidate = {
            "after": left.isoformat(),
            "before": right.isoformat(),
            "calendar_days_without_active_bar": (right - left).days - 1,
            "business_days_without_active_bar": business_days,
        }
        if best is None or (
            int(candidate["business_days_without_active_bar"]),
            int(candidate["calendar_days_without_active_bar"]),
        ) > (
            int(best["business_days_without_active_bar"]),
            int(best["calendar_days_without_active_bar"]),
        ):
            best = candidate
    return best


def _initialize_target(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE historical_fx_records (
            record_id TEXT PRIMARY KEY,
            pair_id TEXT,
            feature TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            source_type TEXT NOT NULL,
            pit_eligible INTEGER NOT NULL,
            record_fingerprint TEXT NOT NULL UNIQUE,
            record_json TEXT NOT NULL
        );
        CREATE TABLE historical_fx_invalid_bars (
            invalid_bar_fingerprint TEXT PRIMARY KEY,
            source_record_id TEXT NOT NULL UNIQUE,
            pair_id TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            classification TEXT NOT NULL,
            invalid_json TEXT NOT NULL
        );
        CREATE TABLE fx_dataset_versions (
            dataset_fingerprint TEXT PRIMARY KEY,
            version TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        CREATE TABLE historical_fx_coverage_snapshots (
            coverage_fingerprint TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            coverage_json TEXT NOT NULL
        );
        CREATE TRIGGER historical_fx_records_no_update BEFORE UPDATE ON historical_fx_records
            BEGIN SELECT RAISE(ABORT, 'historical FX active records append-only'); END;
        CREATE TRIGGER historical_fx_records_no_delete BEFORE DELETE ON historical_fx_records
            BEGIN SELECT RAISE(ABORT, 'historical FX active records append-only'); END;
        CREATE TRIGGER historical_fx_invalid_no_update BEFORE UPDATE ON historical_fx_invalid_bars
            BEGIN SELECT RAISE(ABORT, 'historical FX invalid manifest append-only'); END;
        CREATE TRIGGER historical_fx_invalid_no_delete BEFORE DELETE ON historical_fx_invalid_bars
            BEGIN SELECT RAISE(ABORT, 'historical FX invalid manifest append-only'); END;
        CREATE TRIGGER fx_dataset_versions_no_update BEFORE UPDATE ON fx_dataset_versions
            BEGIN SELECT RAISE(ABORT, 'historical FX dataset versions append-only'); END;
        CREATE TRIGGER fx_dataset_versions_no_delete BEFORE DELETE ON fx_dataset_versions
            BEGIN SELECT RAISE(ABORT, 'historical FX dataset versions append-only'); END;
        """
    )
    return connection


def remediate_historical_fx_store(
    *,
    source_path: Path,
    target_path: Path,
    previous_artifact_path: Path,
    created_at: str,
    code_commit: str,
    branch: str,
    command: str,
) -> dict[str, object]:
    """Build a new active projection while preserving the v1 source byte-for-byte."""

    source_path = Path(source_path)
    target_path = Path(target_path)
    previous_artifact_path = Path(previous_artifact_path)
    if not source_path.exists() or not previous_artifact_path.exists():
        raise FxHistoricalRemediationError("V1-Quelle oder Provenienz-Artefakt fehlt.")
    if source_path.resolve() == target_path.resolve():
        raise FxHistoricalRemediationError("Die immutable v1-Quelle darf nicht überschrieben werden.")
    previous = json.loads(previous_artifact_path.read_text(encoding="utf-8"))
    source_hash_before = file_sha256(source_path)
    source_uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source:
        if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise FxHistoricalRemediationError("Die v1-Quelldatenbank ist nicht integer.")
        rows = source.execute(
            "SELECT record_id,pair_id,feature,observation_date,source_type,"
            "pit_eligible,record_fingerprint,record_json "
            "FROM historical_fx_records ORDER BY pair_id,observation_date,record_id"
        ).fetchall()

    active_rows: list[tuple[object, ...]] = []
    active_fingerprints: list[str] = []
    active_days: dict[str, list[str]] = {}
    invalid_rows: list[dict[str, object]] = []
    for row in rows:
        record = json.loads(str(row[7]))
        metadata = dict(record.get("metadata") or {})
        ohlc = dict(metadata.get("ohlc") or {})
        violations = (
            fx_ohlc_envelope_violations(ohlc, pair_id=str(record.get("pair_id") or ""))
            if record.get("feature") == "PRICE" and ohlc
            else []
        )
        if violations:
            invalid_rows.append(_invalid_manifest_row(record))
            continue
        active_rows.append(row)
        active_fingerprints.append(str(row[6]))
        if record.get("feature") == "PRICE":
            active_days.setdefault(str(record.get("pair_id")), []).append(
                str(record.get("observation_date"))
            )

    invalid_rows.sort(key=lambda item: (str(item["pair_id"]), str(item["observation_date"])))
    invalid_manifest_fingerprint = fingerprint(
        [str(item["invalid_bar_fingerprint"]) for item in invalid_rows]
    )
    source_health = dict(previous.get("source_health") or {})
    invalid_counts = Counter(str(item["pair_id"]) for item in invalid_rows)
    coverage: dict[str, dict[str, object]] = {}
    for pair_id in sorted(source_health):
        health = dict(source_health[pair_id])
        raw_bars = int(health.get("bar_n") or 0)
        legacy_rejected = int(health.get("invalid_bar_n") or 0)
        active_valid = len(active_days.get(pair_id, []))
        newly_invalid = int(invalid_counts[pair_id])
        coverage[pair_id] = {
            "raw_bars": raw_bars,
            "active_valid_bars": active_valid,
            "legacy_import_rejected_bars": legacy_rejected,
            "v2_envelope_invalid_bars": newly_invalid,
            "missing_source_sessions": raw_bars - active_valid,
            "coverage_pct_of_provider_rows": (
                round(active_valid / raw_bars * 100, 6) if raw_bars else 0.0
            ),
            "longest_missing_interval": _longest_business_gap(active_days.get(pair_id, [])),
            "first_valid_date": min(active_days.get(pair_id, []) or [""]) or None,
            "last_valid_date": max(active_days.get(pair_id, []) or [""]) or None,
        }
    dataset_basis = {
        "version": FX_HISTORICAL_ACTIVE_DATASET_VERSION,
        "previous_store_sha256": source_hash_before,
        "previous_artifact_fingerprint": previous.get("artifact_fingerprint"),
        "active_record_fingerprints": active_fingerprints,
        "invalid_manifest_fingerprint": invalid_manifest_fingerprint,
        "coverage": coverage,
    }
    dataset_fingerprint = fingerprint(dataset_basis)
    manifest: dict[str, object] = {
        "version": FX_HISTORICAL_ACTIVE_DATASET_VERSION,
        "remediation_version": FX_HISTORICAL_REMEDIATION_VERSION,
        "status": "HISTORICAL_FX_ACTIVE_PIT_READY_WITH_INVALID_SOURCE_BARS_EXCLUDED",
        "created_at": created_at,
        "source_store": str(source_path.resolve()),
        "source_store_sha256": source_hash_before,
        "previous_store_version": previous.get("version"),
        "previous_artifact": str(previous_artifact_path.resolve()),
        "previous_artifact_fingerprint": previous.get("artifact_fingerprint"),
        "target_store": str(target_path.resolve()),
        "raw_source": "Yahoo Finance/yfinance unadjusted daily FX bar",
        "remediation_reason": (
            "231 low-side OHLC envelope violations passed the asymmetric v1 validator; "
            "the original provider/session cause is not provable, so the bars are archived "
            "as INVALID_SOURCE_BAR and excluded without replacement"
        ),
        "pipeline_root_cause": "ASYMMETRIC_ENVELOPE_VALIDATOR_MISSED_LOW_SIDE_VIOLATIONS",
        "provider_root_cause": "UNKNOWN_NOT_PROVABLE_FROM_PRESERVED_V1_MATERIAL",
        "legacy_229_and_v2_231_same_group": False,
        "legacy_rejected_bar_n": sum(
            int(dict(item).get("invalid_bar_n") or 0) for item in source_health.values()
        ),
        "v2_invalid_source_bar_n": len(invalid_rows),
        "active_valid_bar_n": len(active_rows),
        "active_envelope_anomaly_n": 0,
        "invalid_manifest_fingerprint": invalid_manifest_fingerprint,
        "coverage": coverage,
        "dataset_fingerprint": dataset_fingerprint,
        "pair_contract": "fx-pair-contract-2026.08.28-v1",
        "session_contract": "America/New_York 17:00 plus 15 minute availability delay",
        "row_count": len(active_rows),
        "code_commit": code_commit,
        "run_commit": code_commit,
        "artifact_packaging_commit": None,
        "branch": branch,
        "command": command,
        "no_clipping": True,
        "no_imputation": True,
        "no_interpolation": True,
        "source_records_changed": False,
        "forward_observer_touched": False,
        "discovery_contract_changed": False,
    }
    manifest["manifest_fingerprint"] = fingerprint(manifest)

    if target_path.exists():
        uri = f"file:{target_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as existing:
            row = existing.execute(
                "SELECT manifest_json FROM fx_dataset_versions WHERE version=?",
                (FX_HISTORICAL_ACTIVE_DATASET_VERSION,),
            ).fetchone()
            if row is None:
                raise FxHistoricalRemediationError("Vorhandenes v2-Ziel ist unvollständig.")
            stored = json.loads(str(row[0]))
            if stored.get("dataset_fingerprint") != dataset_fingerprint:
                raise FxHistoricalRemediationError("Vorhandenes v2-Ziel weicht deterministisch ab.")
            return stored

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_name(f".{target_path.name}.building-{uuid.uuid4().hex}")
    try:
        target = _initialize_target(temporary)
        with target:
            target.executemany(
                "INSERT INTO historical_fx_records VALUES (?,?,?,?,?,?,?,?)", active_rows
            )
            target.executemany(
                "INSERT INTO historical_fx_invalid_bars VALUES (?,?,?,?,?,?)",
                [
                    (
                        item["invalid_bar_fingerprint"],
                        item["record_id"],
                        item["pair_id"],
                        item["observation_date"],
                        item["classification"],
                        canonical_json(item),
                    )
                    for item in invalid_rows
                ],
            )
            target.execute(
                "INSERT INTO fx_dataset_versions VALUES (?,?,?,?)",
                (
                    dataset_fingerprint,
                    FX_HISTORICAL_ACTIVE_DATASET_VERSION,
                    created_at,
                    canonical_json(manifest),
                ),
            )
            coverage_payload = {
                "version": FX_HISTORICAL_ACTIVE_DATASET_VERSION,
                "coverage": coverage,
                "active_envelope_anomaly_n": 0,
            }
            target.execute(
                "INSERT INTO historical_fx_coverage_snapshots VALUES (?,?,?)",
                (fingerprint(coverage_payload), created_at, canonical_json(coverage_payload)),
            )
        target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        quick = target.execute("PRAGMA quick_check").fetchone()[0]
        foreign_keys = target.execute("PRAGMA foreign_key_check").fetchall()
        target.close()
        if quick != "ok" or foreign_keys:
            raise FxHistoricalRemediationError("Die erzeugte v2-Datenbank ist nicht integer.")
        os.replace(temporary, target_path)
    finally:
        if temporary.exists():
            temporary.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(temporary) + suffix)
            if sidecar.exists():
                sidecar.unlink()
    if file_sha256(source_path) != source_hash_before:
        raise FxHistoricalRemediationError("Die immutable v1-Quelle wurde verändert.")
    return manifest
