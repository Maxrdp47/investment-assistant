from __future__ import annotations

"""Read-only post-run diagnostics for immutable Multi-Asset Development v5."""

import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from multi_asset_development_execution import (
    DEFAULT_DATASET_MANIFEST,
    DEFAULT_FX_STORE,
    build_development_universe,
    decode_payload,
    load_asset_history,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
RUN_ID = "mad1-development-a073df9096023f1da079a494"
POST_RUN_VERSION = "multi-asset-development-v5-post-run-integrity-2026.09.03-v1"
STORE_AUDIT_VERSION = "multi-asset-development-v5-full-store-audit-2026.09.03-v2"
EXPECTED_CONTRACT_VERSION = "multi-asset-opportunity-discovery-development-2026.09.01-v5"
DEFAULT_FEATURE_STORE = (
    PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_development_v5_features.sqlite3"
)
DEFAULT_OUTCOME_STORE = (
    PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_development_v5_outcomes.sqlite3"
)
DEFAULT_CONTROL_STORE = (
    PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_development_v5_control.sqlite3"
)
DEFAULT_DIAGNOSTIC_STORE = (
    PROJECT_ROOT
    / "runtime"
    / "multi_asset_development_v5_post_run_diagnostics_2026-09-03-v1.sqlite3"
)
DEFAULT_STRUCTURAL_REPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v5_structural_r_classification_2026-09-03-v1.json"
)
DEFAULT_FAILED_REPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v5_failed_work_units_2026-09-03-v1.json"
)
DEFAULT_TERMINAL_REPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v5_terminal_truth_2026-09-03-v1.json"
)
DEFAULT_STORE_AUDIT_REPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v5_full_store_audit_2026-09-03-v1.json"
)

DEVELOPMENT_START = "2016-01-01"
DEVELOPMENT_END = "2021-12-31"


class DevelopmentPostRunIntegrityError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)


def _initialize_diagnostic_store(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=120)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_metadata (
            metadata_fingerprint TEXT PRIMARY KEY,
            metadata_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS structural_r_classifications (
            case_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            listing_id TEXT,
            symbol TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            signal_day TEXT NOT NULL,
            classification TEXT NOT NULL,
            safe_zone_model TEXT,
            structural_risk REAL,
            classification_fingerprint TEXT NOT NULL UNIQUE,
            classification_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS failed_work_unit_classifications (
            work_unit_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            asset_key TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            symbol TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            attempts INTEGER NOT NULL,
            classification TEXT NOT NULL,
            classification_fingerprint TEXT NOT NULL UNIQUE,
            classification_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_snapshots (
            audit_fingerprint TEXT PRIMARY KEY,
            audit_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            audit_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS store_audit_batches (
            batch_number INTEGER PRIMARY KEY,
            first_case_id TEXT NOT NULL,
            last_case_id TEXT NOT NULL UNIQUE,
            row_count INTEGER NOT NULL,
            batch_fingerprint TEXT NOT NULL UNIQUE,
            batch_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS store_audit_batches_v2 (
            batch_number INTEGER PRIMARY KEY,
            first_case_id TEXT NOT NULL,
            last_case_id TEXT NOT NULL UNIQUE,
            row_count INTEGER NOT NULL,
            batch_fingerprint TEXT NOT NULL UNIQUE,
            batch_json TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS diagnostic_metadata_no_update
            BEFORE UPDATE ON diagnostic_metadata
            BEGIN SELECT RAISE(ABORT, 'diagnostic metadata append-only'); END;
        CREATE TRIGGER IF NOT EXISTS diagnostic_metadata_no_delete
            BEFORE DELETE ON diagnostic_metadata
            BEGIN SELECT RAISE(ABORT, 'diagnostic metadata append-only'); END;
        CREATE TRIGGER IF NOT EXISTS structural_r_no_update
            BEFORE UPDATE ON structural_r_classifications
            BEGIN SELECT RAISE(ABORT, 'structural-R classifications append-only'); END;
        CREATE TRIGGER IF NOT EXISTS structural_r_no_delete
            BEFORE DELETE ON structural_r_classifications
            BEGIN SELECT RAISE(ABORT, 'structural-R classifications append-only'); END;
        CREATE TRIGGER IF NOT EXISTS failed_units_no_update
            BEFORE UPDATE ON failed_work_unit_classifications
            BEGIN SELECT RAISE(ABORT, 'failed-unit classifications append-only'); END;
        CREATE TRIGGER IF NOT EXISTS failed_units_no_delete
            BEFORE DELETE ON failed_work_unit_classifications
            BEGIN SELECT RAISE(ABORT, 'failed-unit classifications append-only'); END;
        CREATE TRIGGER IF NOT EXISTS audit_snapshots_no_update
            BEFORE UPDATE ON audit_snapshots
            BEGIN SELECT RAISE(ABORT, 'audit snapshots append-only'); END;
        CREATE TRIGGER IF NOT EXISTS audit_snapshots_no_delete
            BEFORE DELETE ON audit_snapshots
            BEGIN SELECT RAISE(ABORT, 'audit snapshots append-only'); END;
        CREATE TRIGGER IF NOT EXISTS store_audit_batches_no_update
            BEFORE UPDATE ON store_audit_batches
            BEGIN SELECT RAISE(ABORT, 'store audit batches append-only'); END;
        CREATE TRIGGER IF NOT EXISTS store_audit_batches_no_delete
            BEFORE DELETE ON store_audit_batches
            BEGIN SELECT RAISE(ABORT, 'store audit batches append-only'); END;
        CREATE TRIGGER IF NOT EXISTS store_audit_batches_v2_no_update
            BEFORE UPDATE ON store_audit_batches_v2
            BEGIN SELECT RAISE(ABORT, 'store audit v2 batches append-only'); END;
        CREATE TRIGGER IF NOT EXISTS store_audit_batches_v2_no_delete
            BEFORE DELETE ON store_audit_batches_v2
            BEGIN SELECT RAISE(ABORT, 'store audit v2 batches append-only'); END;
        """
    )
    metadata = {
        "version": POST_RUN_VERSION,
        "run_id": RUN_ID,
        "source_feature_store": str(DEFAULT_FEATURE_STORE.resolve()),
        "source_outcome_store": str(DEFAULT_OUTCOME_STORE.resolve()),
        "source_control_store": str(DEFAULT_CONTROL_STORE.resolve()),
        "source_stores_opened_read_only": True,
        "performance_analysis_allowed": False,
        "validation_opened": False,
        "holdout_opened": False,
    }
    key = fingerprint(metadata)
    with connection:
        connection.execute(
            "INSERT OR IGNORE INTO diagnostic_metadata VALUES (?,?)",
            (key, canonical_json(metadata)),
        )
    return connection


def _write_artifact(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("artifact_fingerprint") != payload.get("artifact_fingerprint"):
            raise DevelopmentPostRunIntegrityError(
                f"Append-only-Artefakt weicht ab: {path}"
            )
        return
    path.write_text(encoded, encoding="utf-8")


def terminal_truth_report(
    *, control_path: Path = DEFAULT_CONTROL_STORE, created_at: str
) -> dict[str, object]:
    """Preserve work completion independently of mutable historical audit timestamps."""

    with _ro(control_path) as connection:
        run = connection.execute(
            "SELECT status,started_at,completed_at,last_checkpoint_at,"
            "total_planned_work_units FROM runs WHERE run_id=?",
            (RUN_ID,),
        ).fetchone()
        if run is None:
            raise DevelopmentPostRunIntegrityError("v5-Run fehlt.")
        counts = dict(
            connection.execute(
                "SELECT status,COUNT(*) FROM work_units WHERE run_id=? GROUP BY status",
                (RUN_ID,),
            )
        )
        work_completed_at = connection.execute(
            "SELECT MAX(completed_at) FROM work_units WHERE run_id=?",
            (RUN_ID,),
        ).fetchone()[0]
        event_counts = dict(
            connection.execute(
                "SELECT event_type,COUNT(*) FROM run_events WHERE run_id=? GROUP BY event_type",
                (RUN_ID,),
            )
        )
        first_terminal_event = connection.execute(
            "SELECT MIN(event_at) FROM run_events WHERE run_id=? AND event_type='RUN_COMPLETED' "
            "AND event_at>=?",
            (RUN_ID, work_completed_at),
        ).fetchone()[0]
    terminal = sum(int(counts.get(key, 0)) for key in ("COMPLETED", "SKIPPED", "FAILED"))
    payload: dict[str, object] = {
        "version": POST_RUN_VERSION,
        "run_id": RUN_ID,
        "created_at": created_at,
        "runtime_status": run[0],
        "total_planned_work_units": int(run[4]),
        "terminal_work_units": terminal,
        "work_unit_status_counts": {str(k): int(v) for k, v in counts.items()},
        "work_started_at": run[1],
        "work_completed_at": work_completed_at,
        "run_terminal_at": first_terminal_event or work_completed_at,
        "legacy_overwritten_completed_at": run[2],
        "legacy_last_checkpoint_at": run[3],
        "last_audited_at": created_at,
        "last_status_checked_at": created_at,
        "event_counts": {str(k): int(v) for k, v in event_counts.items()},
        "legacy_timestamp_mutated": bool(run[2] != work_completed_at),
        "original_control_store_changed": False,
        "status_rewritten_to_completed": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    return payload


def build_terminal_truth_artifact(
    *,
    control_path: Path = DEFAULT_CONTROL_STORE,
    artifact_path: Path = DEFAULT_TERMINAL_REPORT,
    created_at: str,
) -> dict[str, object]:
    """Create the terminal truth once; later status checks cannot overwrite it."""

    if artifact_path.exists():
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    payload = terminal_truth_report(control_path=control_path, created_at=created_at)
    _write_artifact(artifact_path, payload)
    return payload


def _available_number(feature: Mapping[str, object], name: str) -> float | None:
    item = dict((feature.get("features") or {}).get(name) or {})
    if item.get("status") != "AVAILABLE":
        return None
    try:
        value = float(item.get("value"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def classify_structural_r_case(
    feature: Mapping[str, object], *, next_open: float | None
) -> dict[str, object]:
    """Classify why the frozen outcome could not define structural R."""

    zones = dict(feature.get("safe_zones") or {})
    zone_a = dict(zones.get("A") or {})
    zone_b = dict(zones.get("B") or {})
    zone_c = dict(zones.get("C") or {})
    atr = _available_number(feature, "atr_14")
    lower = zone_c.get("lower")
    try:
        invalidation = float(lower) if lower is not None else None
    except (TypeError, ValueError):
        invalidation = None
    base_available = any(
        zone.get("status") == "AVAILABLE" for zone in (zone_a, zone_b)
    )
    bug = False
    risk: float | None = None
    if zone_c.get("status") != "AVAILABLE" or invalidation is None:
        if base_available and atr is not None:
            classification = "IMPLEMENTATION_BUG_SAFE_ZONE_C_NOT_DERIVED"
            bug = True
        else:
            classification = "SAFE_ZONE_NOT_AVAILABLE"
    elif atr is None:
        classification = "MATHEMATICALLY_UNDEFINED_ATR"
    elif next_open is None or not math.isfinite(float(next_open)):
        classification = "IMPLEMENTATION_BUG_NEXT_OPEN_NOT_AVAILABLE"
        bug = True
    else:
        risk = float(next_open) - invalidation
        if risk <= 0:
            classification = "NON_POSITIVE_STRUCTURAL_RISK"
        else:
            classification = "IMPLEMENTATION_BUG_UNEXPECTED_STRUCTURAL_R_REJECTION"
            bug = True
    payload: dict[str, object] = {
        "case_id": feature["case_id"],
        "asset_id": feature["asset_id"],
        "listing_id": feature.get("listing_id"),
        "symbol": feature["symbol"],
        "asset_class": feature["asset_class"],
        "signal_day": feature["signal_day"],
        "classification": classification,
        "technical_bug": bug,
        "safe_zone_model": zone_c.get("model"),
        "safe_zone_c_status": zone_c.get("status"),
        "safe_zone_c_reason": zone_c.get("reason"),
        "safe_zone_a_status": zone_a.get("status"),
        "safe_zone_b_status": zone_b.get("status"),
        "atr_14": atr,
        "next_open": next_open,
        "invalidation": invalidation,
        "structural_risk": risk,
        "structural_r_available": False,
        "r_dependent_outcomes_available_in_v5": False,
        "r_independent_outcomes_reprocessable": next_open is not None,
        "r_dependent_fields": [
            "mfe_r",
            "mae_r",
            "r_level_hits",
            "peak_giveback_r",
            "final_giveback_r",
        ],
        "r_independent_fields": [
            "mfe_pct",
            "mae_pct",
            "final_return_pct",
            "safe_zone_breaches",
            "sell_zone_measurements",
            "time_to_mfe_observations",
        ],
        "forced_safe_zone_created": False,
    }
    payload["classification_fingerprint"] = fingerprint(payload)
    return payload


def _next_open_lookup(
    asset: Mapping[str, object], signal_days: Iterable[str]
) -> dict[str, float | None]:
    frame, _, _ = load_asset_history(
        asset,
        manifest_path=DEFAULT_DATASET_MANIFEST,
        fx_store=DEFAULT_FX_STORE,
    )
    frame = frame.sort_index().loc[~frame.index.duplicated(keep="last")]
    positions = {stamp.date().isoformat(): index for index, stamp in enumerate(frame.index)}
    result: dict[str, float | None] = {}
    for signal_day in signal_days:
        position = positions.get(signal_day)
        if position is None or position >= len(frame) - 1:
            result[signal_day] = None
        else:
            try:
                value = float(frame.iloc[position + 1]["Open"])
            except (TypeError, ValueError):
                value = math.nan
            result[signal_day] = value if math.isfinite(value) else None
    return result


def build_structural_r_report(
    *,
    feature_path: Path = DEFAULT_FEATURE_STORE,
    outcome_path: Path = DEFAULT_OUTCOME_STORE,
    diagnostic_path: Path = DEFAULT_DIAGNOSTIC_STORE,
    artifact_path: Path = DEFAULT_STRUCTURAL_REPORT,
    created_at: str,
) -> dict[str, object]:
    """Classify every frozen Structural-R N/A outcome without mutating it."""

    if artifact_path.exists():
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    diagnostic = _initialize_diagnostic_store(diagnostic_path)
    uri = f"file:{Path(outcome_path).resolve().as_posix()}?mode=ro"
    source = sqlite3.connect(uri, uri=True)
    source.execute(
        "ATTACH DATABASE ? AS features",
        (f"file:{Path(feature_path).resolve().as_posix()}?mode=ro",),
    )
    universe = {
        (str(item["asset_class"]), str(item["symbol"])): item
        for item in build_development_universe()["assets"]
    }
    expected_count = 0
    current_key: tuple[str, str] | None = None
    current_features: list[dict[str, object]] = []

    def persist_group(
        key: tuple[str, str] | None, features: Sequence[Mapping[str, object]]
    ) -> None:
        if key is None or not features:
            return
        asset = universe.get(key)
        if asset is None:
            raise DevelopmentPostRunIntegrityError(f"Asset fehlt im Universe: {key}")
        lookup = _next_open_lookup(
            asset, (str(item["signal_day"]) for item in features)
        )
        classified = [
            classify_structural_r_case(
                feature, next_open=lookup.get(str(feature["signal_day"]))
            )
            for feature in features
        ]
        with diagnostic:
            diagnostic.executemany(
                "INSERT OR IGNORE INTO structural_r_classifications "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        item["case_id"], RUN_ID, item["asset_id"], item.get("listing_id"),
                        item["symbol"], item["asset_class"], item["signal_day"],
                        item["classification"], item.get("safe_zone_model"),
                        item.get("structural_risk"), item["classification_fingerprint"],
                        canonical_json(item),
                    )
                    for item in classified
                ],
            )

    cursor = source.execute(
        "SELECT o.asset_class,o.symbol,o.payload_zlib,f.payload_zlib "
        "FROM outcome_rows o JOIN features.feature_rows f ON f.case_id=o.case_id "
        "WHERE o.status='INVALID_TECHNICAL_ELIGIBILITY' "
        "ORDER BY o.asset_class,o.symbol,o.signal_day,o.case_id"
    )
    for asset_class, symbol, outcome_blob, feature_blob in cursor:
        outcome = decode_payload(outcome_blob)
        if outcome.get("reason") != "Strukturelles R ist für den Pilotfall nicht definiert.":
            continue
        key = (str(asset_class), str(symbol))
        if current_key is not None and key != current_key:
            persist_group(current_key, current_features)
            current_features = []
        current_key = key
        current_features.append(decode_payload(feature_blob))
        expected_count += 1
    persist_group(current_key, current_features)
    source.close()
    stored_count = int(
        diagnostic.execute("SELECT COUNT(*) FROM structural_r_classifications").fetchone()[0]
    )
    if stored_count != expected_count:
        raise DevelopmentPostRunIntegrityError(
            f"Structural-R-Klassifikation unvollständig: {stored_count}/{expected_count}"
        )
    classification_counts: Counter[str] = Counter()
    asset_class_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    reason_counts = Counter()
    model_counts = Counter()
    technical_bug_count = 0
    r_independent_reprocessable_count = 0
    row_digest = hashlib.sha256()
    for row in diagnostic.execute(
        "SELECT classification_json FROM structural_r_classifications ORDER BY case_id"
    ):
        item = json.loads(str(row[0]))
        classification_counts[str(item["classification"])] += 1
        asset_class_counts[str(item["asset_class"])][str(item["classification"])] += 1
        reason_counts[str(item.get("safe_zone_c_reason") or "NONE")] += 1
        model_counts[str(item.get("safe_zone_model") or "NONE")] += 1
        technical_bug_count += int(item["technical_bug"])
        r_independent_reprocessable_count += int(
            item["r_independent_outcomes_reprocessable"]
        )
        row_digest.update(str(item["classification_fingerprint"]).encode("ascii"))
        row_digest.update(b"\n")
    payload: dict[str, object] = {
        "version": POST_RUN_VERSION,
        "report": "STRUCTURAL_R_CLASSIFICATION",
        "created_at": created_at,
        "run_id": RUN_ID,
        "total_structural_r_na": stored_count,
        "classification_counts": dict(sorted(classification_counts.items())),
        "asset_class_counts": {
            key: dict(sorted(value.items())) for key, value in sorted(asset_class_counts.items())
        },
        "safe_zone_reason_counts": dict(sorted(reason_counts.items())),
        "safe_zone_model_counts": dict(sorted(model_counts.items())),
        "legitimate_na_count": int(classification_counts["SAFE_ZONE_NOT_AVAILABLE"]),
        "technical_bug_count": technical_bug_count,
        "non_positive_risk_count": int(
            classification_counts["NON_POSITIVE_STRUCTURAL_RISK"]
        ),
        "r_independent_reprocessable_count": r_independent_reprocessable_count,
        "classification_complete": stored_count == expected_count,
        "classification_row_digest": row_digest.hexdigest(),
        "source_feature_store_sha256": file_sha256(feature_path),
        "source_outcome_store_sha256": file_sha256(outcome_path),
        "source_stores_changed": False,
        "forced_r_created": False,
        "performance_analysis_performed": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_artifact(artifact_path, payload)
    audit = {"audit_type": "STRUCTURAL_R", **payload}
    with diagnostic:
        diagnostic.execute(
            "INSERT OR IGNORE INTO audit_snapshots VALUES (?,?,?,?)",
            (
                payload["artifact_fingerprint"],
                "STRUCTURAL_R",
                created_at,
                canonical_json(audit),
            ),
        )
    diagnostic.close()
    return payload


def _modern_manifest_assets(
    manifest_path: Path,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    modern: Mapping[str, object] | None = None
    for raw in (manifest.get("scopes") or {}).values():
        scope = dict(raw)
        if dict(scope.get("contract") or {}).get("start") == DEVELOPMENT_START:
            modern = scope
            break
    if modern is None:
        raise DevelopmentPostRunIntegrityError("Modern-Scope fehlt im Frozen Dataset.")
    assets = {
        str(symbol): dict(value)
        for symbol, value in dict(modern.get("assets") or {}).items()
    }
    return manifest, assets


def _non_positive_source_rows(
    *, asset: Mapping[str, object], manifest_path: Path
) -> list[dict[str, object]]:
    relative = str(asset.get("modern_file") or "")
    if not relative:
        return []
    frame = pd.read_parquet(
        manifest_path.parent / relative,
        filters=[
            ("Date", ">=", pd.Timestamp(DEVELOPMENT_START)),
            ("Date", "<=", pd.Timestamp(DEVELOPMENT_END)),
        ],
    )
    frame = frame.rename(
        columns={str(column).lower(): str(column).title() for column in frame.columns}
    )
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    results: list[dict[str, object]] = []
    for source_row, (stamp, row) in enumerate(frame.iterrows()):
        values: dict[str, float | None] = {}
        violations: list[str] = []
        for name in ("Open", "High", "Low", "Close"):
            try:
                value = float(row[name])
            except (KeyError, TypeError, ValueError):
                value = math.nan
            values[name.lower()] = value if math.isfinite(value) else None
            if not math.isfinite(value):
                violations.append(f"{name.upper()}_NON_FINITE")
            elif value <= 0:
                violations.append(f"{name.upper()}_NON_POSITIVE")
        if not violations:
            continue
        evidence: dict[str, object] = {
            "asset_key": asset["asset_key"],
            "symbol": asset["symbol"],
            "asset_class": asset["asset_class"],
            "session_date": pd.Timestamp(stamp).date().isoformat(),
            "source_file": relative,
            "source_row_in_development_slice": source_row,
            "source_history_fingerprint": asset.get("modern_history_fingerprint"),
            "violations": violations,
            **values,
            "root_cause": "NON_POSITIVE_VALUE_IN_FROZEN_SOURCE_ROW",
            "provider_or_adjustment_root_cause": (
                "UNKNOWN_NOT_PROVABLE_FROM_FROZEN_AUTO_ADJUSTED_BAR"
            ),
        }
        evidence["source_bar_fingerprint"] = fingerprint(evidence)
        results.append(evidence)
    return results


def classify_failed_work_unit(
    unit: Mapping[str, object],
    *,
    source_manifest_entry: Mapping[str, object] | None,
    source_bar_failures: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Classify one immutable v5 FAILED unit from preserved source evidence."""

    error_message = str(unit.get("last_error_message") or "")
    source_first_day = (
        str(source_manifest_entry.get("first_day"))
        if source_manifest_entry and source_manifest_entry.get("first_day")
        else None
    )
    if error_message.startswith("Keine Development-Balken"):
        coverage_proves_absence = bool(
            source_first_day is not None and source_first_day > DEVELOPMENT_END
        )
        classification = (
            "LEGITIMATE_SKIP_NO_DEVELOPMENT_COVERAGE"
            if coverage_proves_absence
            else "UNRESOLVED_NO_DEVELOPMENT_DATA"
        )
        future_status = "SKIPPED" if coverage_proves_absence else "FAILED"
        retryable = False
        planning_issue = (
            "COVERAGE_BOUNDS_NOT_APPLIED_TO_WORK_PLAN"
            if coverage_proves_absence
            else None
        )
    elif "OHLC muss positiv sein" in error_message:
        classification = (
            "SOURCE_DATA_FAILURE_NON_POSITIVE_OHLC"
            if source_bar_failures
            else "UNRESOLVED_POSITIVE_OHLC_CONTRACT_FAILURE"
        )
        future_status = "FAILED"
        retryable = False
        planning_issue = None
    else:
        classification = "UNRESOLVED_FAILURE"
        future_status = "FAILED"
        retryable = False
        planning_issue = None
    payload: dict[str, object] = {
        "work_unit_id": unit["work_unit_id"],
        "run_id": unit["run_id"],
        "asset_key": unit["asset_key"],
        "asset_class": unit["asset_class"],
        "symbol": unit["symbol"],
        "period_start": unit["period_start"],
        "period_end": unit["period_end"],
        "attempts": int(unit["attempts"]),
        "original_status": unit["status"],
        "original_error_class": unit.get("last_error_class"),
        "original_error_message": error_message,
        "classification": classification,
        "technical_pipeline_bug": False,
        "work_plan_coverage_issue": planning_issue,
        "source_first_day": source_first_day,
        "source_last_day": (
            source_manifest_entry.get("last_day") if source_manifest_entry else None
        ),
        "source_history_fingerprint": (
            source_manifest_entry.get("history_fingerprint")
            if source_manifest_entry
            else None
        ),
        "source_bar_failures": [dict(item) for item in source_bar_failures],
        "future_disposition": future_status,
        "future_retryable": retryable,
        "v5_status_changed": False,
        "v5_retry_count_changed": False,
    }
    payload["classification_fingerprint"] = fingerprint(payload)
    return payload


def build_failed_work_unit_report(
    *,
    control_path: Path = DEFAULT_CONTROL_STORE,
    diagnostic_path: Path = DEFAULT_DIAGNOSTIC_STORE,
    manifest_path: Path = DEFAULT_DATASET_MANIFEST,
    artifact_path: Path = DEFAULT_FAILED_REPORT,
    created_at: str,
) -> dict[str, object]:
    """Classify all v5 failed units and define deterministic future disposition."""

    if artifact_path.exists():
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    universe = {
        str(item["asset_key"]): item
        for item in build_development_universe(manifest_path=manifest_path)["assets"]
    }
    _, manifest_assets = _modern_manifest_assets(manifest_path)
    with _ro(control_path) as connection:
        columns = [
            "work_unit_id", "run_id", "asset_key", "asset_class", "symbol",
            "period_start", "period_end", "status", "attempts", "last_error_class",
            "last_error_message",
        ]
        rows = [
            dict(zip(columns, row))
            for row in connection.execute(
                "SELECT " + ",".join(columns) + " FROM work_units "
                "WHERE run_id=? AND status='FAILED' ORDER BY asset_class,symbol,period_start",
                (RUN_ID,),
            )
        ]
    failed_assets = sorted({str(row["asset_key"]) for row in rows})
    source_failures: dict[str, list[dict[str, object]]] = {}
    for asset_key in failed_assets:
        asset = universe.get(asset_key)
        if asset is None:
            raise DevelopmentPostRunIntegrityError(
                f"FAILED-Asset fehlt im eingefrorenen Universe: {asset_key}"
            )
        source_failures[asset_key] = _non_positive_source_rows(
            asset=asset, manifest_path=manifest_path
        )
    diagnostic = _initialize_diagnostic_store(diagnostic_path)
    classified: list[dict[str, object]] = []
    for row in rows:
        item = classify_failed_work_unit(
            row,
            source_manifest_entry=manifest_assets.get(str(row["symbol"])),
            source_bar_failures=source_failures[str(row["asset_key"])],
        )
        classified.append(item)
    with diagnostic:
        diagnostic.executemany(
            "INSERT OR IGNORE INTO failed_work_unit_classifications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    item["work_unit_id"], item["run_id"], item["asset_key"],
                    item["asset_class"], item["symbol"], item["period_start"],
                    item["period_end"], item["attempts"], item["classification"],
                    item["classification_fingerprint"], canonical_json(item),
                )
                for item in classified
            ],
        )
    stored = int(
        diagnostic.execute(
            "SELECT COUNT(*) FROM failed_work_unit_classifications WHERE run_id=?",
            (RUN_ID,),
        ).fetchone()[0]
    )
    if stored != len(rows):
        diagnostic.close()
        raise DevelopmentPostRunIntegrityError(
            f"Failed-Unit-Klassifikation unvollständig: {stored}/{len(rows)}"
        )
    classification_counts = Counter(str(item["classification"]) for item in classified)
    classification_asset_counts: dict[str, int] = {}
    for name in classification_counts:
        classification_asset_counts[name] = len(
            {item["asset_key"] for item in classified if item["classification"] == name}
        )
    unique_source_bars = {
        str(evidence["source_bar_fingerprint"]): evidence
        for values in source_failures.values()
        for evidence in values
    }
    row_digest = hashlib.sha256()
    for item in sorted(classified, key=lambda value: str(value["work_unit_id"])):
        row_digest.update(str(item["classification_fingerprint"]).encode("ascii"))
        row_digest.update(b"\n")
    payload: dict[str, object] = {
        "version": POST_RUN_VERSION,
        "report": "FAILED_WORK_UNIT_CLASSIFICATION",
        "created_at": created_at,
        "run_id": RUN_ID,
        "failed_work_units": len(rows),
        "failed_assets": len(failed_assets),
        "classification_counts": dict(sorted(classification_counts.items())),
        "classification_asset_counts": dict(sorted(classification_asset_counts.items())),
        "attempt_counts": dict(
            sorted(Counter(str(item["attempts"]) for item in classified).items())
        ),
        "source_failure_bars": [
            unique_source_bars[key] for key in sorted(unique_source_bars)
        ],
        "source_failure_bar_count": len(unique_source_bars),
        "legitimate_skip_count": int(
            classification_counts["LEGITIMATE_SKIP_NO_DEVELOPMENT_COVERAGE"]
        ),
        "source_data_failure_count": int(
            classification_counts["SOURCE_DATA_FAILURE_NON_POSITIVE_OHLC"]
        ),
        "technical_pipeline_bug_count": sum(
            int(item["technical_pipeline_bug"]) for item in classified
        ),
        "unresolved_count": sum(
            count for name, count in classification_counts.items() if name.startswith("UNRESOLVED")
        ),
        "future_policy": {
            "no_development_coverage": "SKIPPED_WITHOUT_RETRY",
            "deterministic_source_or_contract_failure": "FAILED_WITHOUT_RETRY",
            "transient_timeout_connection_or_sqlite_contention": "RETRY_UP_TO_CONFIGURED_LIMIT",
        },
        "v5_changed": False,
        "classification_complete": stored == len(rows),
        "classification_row_digest": row_digest.hexdigest(),
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_control_store_sha256": file_sha256(control_path),
        "performance_analysis_performed": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_artifact(artifact_path, payload)
    with diagnostic:
        diagnostic.execute(
            "INSERT OR IGNORE INTO audit_snapshots VALUES (?,?,?,?)",
            (
                payload["artifact_fingerprint"], "FAILED_WORK_UNITS", created_at,
                canonical_json(payload),
            ),
        )
    diagnostic.close()
    return payload


OUTCOME_ONLY_FEATURE_KEYS = frozenset(
    {
        "entry_day",
        "entry_open",
        "entry_gap_pct",
        "entry_gap_atr",
        "outcome_end_day",
        "observations_available",
        "requested_observations",
        "mfe_pct",
        "mae_pct",
        "mfe_atr",
        "mae_atr",
        "mfe_r",
        "mae_r",
        "final_return_pct",
        "time_to_mfe_observations",
        "r_level_hits",
        "checkpoints",
    }
)


def _payload_fingerprint_matches(payload: Mapping[str, object], key: str) -> bool:
    stored = payload.get(key)
    if not stored:
        return False
    basis = dict(payload)
    basis.pop(key, None)
    return str(stored) == fingerprint(basis)


def _known_at_after_decision(value: object, decision_time: str) -> bool:
    if isinstance(value, Mapping):
        known_at = value.get("known_at")
        if known_at and str(known_at) != decision_time:
            try:
                known = datetime.fromisoformat(str(known_at).replace("Z", "+00:00"))
                decision = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
            except ValueError:
                return True
            if known > decision:
                return True
        return any(_known_at_after_decision(item, decision_time) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_known_at_after_decision(item, decision_time) for item in value)
    return False


def audit_case_payload_pair(
    feature_columns: Mapping[str, object],
    outcome_columns: Mapping[str, object],
    feature: Mapping[str, object],
    outcome: Mapping[str, object],
    *,
    work_unit: Mapping[str, object] | None,
    expected_contract_version: str | None = None,
) -> Counter[str]:
    """Validate one persisted pair without interpreting performance."""

    issues: Counter[str] = Counter()
    case_id = str(feature_columns["case_id"])
    if not _payload_fingerprint_matches(feature, "feature_fingerprint"):
        issues["feature_payload_fingerprint_mismatch"] += 1
    if not _payload_fingerprint_matches(outcome, "outcome_fingerprint"):
        issues["outcome_payload_fingerprint_mismatch"] += 1
    identity = {
        "asset_id": feature.get("asset_id"),
        "signal_day": feature.get("signal_day"),
        "contract_version": feature.get("contract_version"),
        "dataset_fingerprint": feature.get("dataset_fingerprint"),
    }
    expected_case_id = f"mad1-{fingerprint(identity)[:32]}"
    if case_id != expected_case_id:
        issues["deterministic_case_id_mismatch"] += 1
    if str(outcome_columns["case_id"]) != case_id:
        issues["cross_store_case_id_mismatch"] += 1
    if str(feature.get("case_id")) != case_id:
        issues["feature_payload_case_id_mismatch"] += 1
    if str(outcome.get("case_id")) != case_id:
        issues["outcome_payload_case_id_mismatch"] += 1
    if str(outcome.get("feature_fingerprint")) != str(feature.get("feature_fingerprint")):
        issues["outcome_feature_link_mismatch"] += 1
    if str(outcome.get("contract_version")) != str(feature.get("contract_version")):
        issues["cross_payload_contract_version_mismatch"] += 1
    if expected_contract_version is not None and str(feature.get("contract_version")) != expected_contract_version:
        issues["unexpected_feature_contract_version"] += 1
    if str(outcome_columns["feature_fingerprint"]) != str(feature_columns["feature_fingerprint"]):
        issues["stored_feature_link_mismatch"] += 1
    for name in (
        "run_id", "work_unit_id", "asset_id", "symbol", "asset_class",
        "signal_day", "research_split", "dependency_status",
    ):
        if str(feature_columns.get(name)) != str(outcome_columns.get(name)):
            issues[f"cross_store_{name}_mismatch"] += 1
    for name in (
        "case_id", "feature_fingerprint", "asset_id", "symbol", "asset_class",
        "signal_day", "research_split", "dependency_status",
    ):
        if str(feature_columns.get(name)) != str(feature.get(name)):
            issues[f"feature_column_{name}_mismatch"] += 1
    for name in (
        "case_id", "outcome_fingerprint", "feature_fingerprint", "asset_id", "symbol",
        "asset_class", "signal_day", "research_split", "status", "dependency_status",
    ):
        if str(outcome_columns.get(name)) != str(outcome.get(name)):
            issues[f"outcome_column_{name}_mismatch"] += 1
    if feature.get("listing_id") != outcome.get("listing_id"):
        issues["listing_id_mismatch"] += 1
    if feature.get("issuer_id") != outcome.get("issuer_id"):
        issues["issuer_id_mismatch"] += 1
    if feature.get("research_split") != "development" or outcome.get("research_split") != "development":
        issues["non_development_payload"] += 1
    signal_day = str(feature.get("signal_day") or "")
    if feature.get("history_end_day") != signal_day:
        issues["feature_history_extends_beyond_signal"] += 1
    decision_time = str(feature.get("decision_time") or "")
    if not decision_time or decision_time[:10] < signal_day:
        issues["invalid_decision_time"] += 1
    elif _known_at_after_decision(feature.get("features"), decision_time):
        issues["feature_known_at_after_decision"] += 1
    if feature.get("known_at_lte_decision_time") is not True:
        issues["pit_attestation_missing"] += 1
    if OUTCOME_ONLY_FEATURE_KEYS.intersection(feature):
        issues["future_outcome_field_in_feature_payload"] += 1
    if outcome.get("future_features_written_to_feature_store") is not False:
        issues["future_feature_write_attestation_invalid"] += 1
    if feature.get("candidate_selected_from_outcome") is not False:
        issues["outcome_based_selection_attestation_invalid"] += 1
    if feature.get("predictive_prefilter_used") is not False:
        issues["predictive_prefilter_attestation_invalid"] += 1
    if work_unit is None:
        issues["orphan_work_unit_link"] += 1
    else:
        if str(work_unit.get("run_id")) != str(feature_columns.get("run_id")):
            issues["work_unit_run_link_mismatch"] += 1
        if str(work_unit.get("asset_class")) != str(feature_columns.get("asset_class")):
            issues["work_unit_asset_class_mismatch"] += 1
        if str(work_unit.get("symbol")) != str(feature_columns.get("symbol")):
            issues["work_unit_symbol_mismatch"] += 1
        if not str(work_unit.get("period_start")) <= signal_day <= str(work_unit.get("period_end")):
            issues["signal_outside_work_unit_period"] += 1
        if work_unit.get("status") != "COMPLETED":
            issues["case_linked_to_non_completed_work_unit"] += 1
    return issues


def _database_integrity(path: Path, *, role: str) -> dict[str, object]:
    with _ro(path) as connection:
        quick_rows = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
        integrity_rows = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
        foreign_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        triggers = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
            )
        ]
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    return {
        "role": role,
        "path": str(path.resolve()),
        "quick_check": quick_rows,
        "integrity_check": integrity_rows,
        "foreign_key_issues": len(foreign_rows),
        "tables": tables,
        "triggers": triggers,
        "journal_mode": journal_mode,
        "synchronous": synchronous,
        "integrity_ok": quick_rows == ["ok"] and integrity_rows == ["ok"] and not foreign_rows,
    }


def _load_work_units(control_path: Path) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    columns = (
        "work_unit_id", "run_id", "asset_key", "asset_class", "symbol", "period_start",
        "period_end", "status", "attempts", "feature_rows", "outcome_rows",
    )
    with _ro(control_path) as connection:
        units = {
            str(row[0]): dict(zip(columns, row))
            for row in connection.execute(
                "SELECT " + ",".join(columns) + " FROM work_units WHERE run_id=?",
                (RUN_ID,),
            )
        }
        run_row = connection.execute(
            "SELECT status,total_planned_work_units,feature_rows,outcome_rows,invalid_cases,"
            "censored_cases,contract_fingerprint,universe_fingerprint,work_plan_fingerprint,"
            "run_manifest_fingerprint FROM runs WHERE run_id=?",
            (RUN_ID,),
        ).fetchone()
    if run_row is None:
        raise DevelopmentPostRunIntegrityError("v5-Run fehlt im Control-Store.")
    run_names = (
        "status", "total_planned_work_units", "feature_rows", "outcome_rows",
        "invalid_cases", "censored_cases", "contract_fingerprint",
        "universe_fingerprint", "work_plan_fingerprint", "run_manifest_fingerprint",
    )
    return units, dict(zip(run_names, run_row))


def _source_set_summary(
    feature_path: Path, outcome_path: Path
) -> dict[str, int]:
    with _ro(feature_path) as connection:
        connection.execute(
            "ATTACH DATABASE ? AS outcomes",
            (f"file:{outcome_path.resolve().as_posix()}?mode=ro",),
        )
        feature_rows = int(connection.execute("SELECT COUNT(*) FROM feature_rows").fetchone()[0])
        outcome_rows = int(connection.execute("SELECT COUNT(*) FROM outcomes.outcome_rows").fetchone()[0])
        feature_only = int(
            connection.execute(
                "SELECT COUNT(*) FROM feature_rows f WHERE NOT EXISTS "
                "(SELECT 1 FROM outcomes.outcome_rows o WHERE o.case_id=f.case_id)"
            ).fetchone()[0]
        )
        outcome_only = int(
            connection.execute(
                "SELECT COUNT(*) FROM outcomes.outcome_rows o WHERE NOT EXISTS "
                "(SELECT 1 FROM feature_rows f WHERE f.case_id=o.case_id)"
            ).fetchone()[0]
        )
        feature_duplicates = int(
            connection.execute(
                "SELECT COUNT(*) FROM (SELECT case_id FROM feature_rows GROUP BY case_id HAVING COUNT(*)>1)"
            ).fetchone()[0]
        )
        outcome_duplicates = int(
            connection.execute(
                "SELECT COUNT(*) FROM (SELECT case_id FROM outcomes.outcome_rows GROUP BY case_id HAVING COUNT(*)>1)"
            ).fetchone()[0]
        )
    return {
        "feature_rows": feature_rows,
        "outcome_rows": outcome_rows,
        "feature_only_rows": feature_only,
        "outcome_only_rows": outcome_only,
        "feature_duplicate_case_ids": feature_duplicates,
        "outcome_duplicate_case_ids": outcome_duplicates,
    }


def build_full_store_audit(
    *,
    feature_path: Path = DEFAULT_FEATURE_STORE,
    outcome_path: Path = DEFAULT_OUTCOME_STORE,
    control_path: Path = DEFAULT_CONTROL_STORE,
    diagnostic_path: Path = DEFAULT_DIAGNOSTIC_STORE,
    artifact_path: Path = DEFAULT_STORE_AUDIT_REPORT,
    created_at: str,
    batch_size: int = 5_000,
) -> dict[str, object]:
    """Audit every v5 feature/outcome pair with append-only resumable batches."""

    if artifact_path.exists():
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    if batch_size <= 0:
        raise ValueError("batch_size muss positiv sein.")
    source_hashes_before = {
        "feature": file_sha256(feature_path),
        "outcome": file_sha256(outcome_path),
        "control": file_sha256(control_path),
    }
    context = {
        "version": STORE_AUDIT_VERSION,
        "run_id": RUN_ID,
        "source_hashes": source_hashes_before,
        "batch_size": batch_size,
        "audit_contract": "ALL_CASES_PAYLOAD_LINEAGE_PIT_AND_SQLITE_INTEGRITY",
    }
    context_fingerprint = fingerprint(context)
    units, run = _load_work_units(control_path)
    set_summary = _source_set_summary(feature_path, outcome_path)
    diagnostic = _initialize_diagnostic_store(diagnostic_path)
    existing_batches: list[dict[str, object]] = []
    for row in diagnostic.execute(
        "SELECT batch_number,batch_json FROM store_audit_batches_v2 ORDER BY batch_number"
    ):
        item = json.loads(str(row[1]))
        if item.get("context_fingerprint") != context_fingerprint:
            diagnostic.close()
            raise DevelopmentPostRunIntegrityError(
                "Vorhandener Store-Audit-Checkpoint gehört zu anderem Input oder Batchvertrag."
            )
        if int(item.get("batch_number", -1)) != int(row[0]):
            diagnostic.close()
            raise DevelopmentPostRunIntegrityError("Store-Audit-Batchnummer inkonsistent.")
        existing_batches.append(item)
    last_case_id = str(existing_batches[-1]["last_case_id"]) if existing_batches else ""
    batch_number = len(existing_batches)
    feature_names = (
        "case_id", "feature_fingerprint", "run_id", "work_unit_id", "asset_id",
        "symbol", "asset_class", "signal_day", "research_split", "dependency_status",
    )
    outcome_names = (
        "case_id", "outcome_fingerprint", "feature_fingerprint", "run_id",
        "work_unit_id", "asset_id", "symbol", "asset_class", "signal_day",
        "research_split", "status", "dependency_status",
    )
    source = _ro(feature_path)
    source.execute(
        "ATTACH DATABASE ? AS outcomes",
        (f"file:{outcome_path.resolve().as_posix()}?mode=ro",),
    )
    select_sql = (
        "SELECT f.case_id,f.feature_fingerprint,f.run_id,f.work_unit_id,f.asset_id,"
        "f.symbol,f.asset_class,f.signal_day,f.research_split,f.dependency_status,f.payload_zlib,"
        "o.case_id,o.outcome_fingerprint,o.feature_fingerprint,o.run_id,o.work_unit_id,"
        "o.asset_id,o.symbol,o.asset_class,o.signal_day,o.research_split,o.status,"
        "o.dependency_status,o.payload_zlib FROM feature_rows f "
        "JOIN outcomes.outcome_rows o ON o.case_id=f.case_id "
        "WHERE f.case_id>? ORDER BY f.case_id LIMIT ?"
    )
    while True:
        cursor = source.execute(select_sql, (last_case_id, batch_size))
        counts: Counter[str] = Counter()
        sample_issues: list[dict[str, object]] = []
        batch_digest = hashlib.sha256()
        first_case_id: str | None = None
        row_count = 0
        for row in cursor:
            feature_columns = dict(zip(feature_names, row[:10]))
            outcome_columns = dict(zip(outcome_names, row[11:23]))
            case_id = str(row[0])
            if first_case_id is None:
                first_case_id = case_id
            last_case_id = case_id
            row_count += 1
            batch_digest.update(case_id.encode("utf-8"))
            batch_digest.update(b"\0")
            batch_digest.update(str(row[1]).encode("ascii"))
            batch_digest.update(b"\0")
            batch_digest.update(str(row[12]).encode("ascii"))
            batch_digest.update(b"\n")
            try:
                feature = decode_payload(row[10])
            except Exception as exc:
                counts["feature_payload_decode_error"] += 1
                if len(sample_issues) < 20:
                    sample_issues.append(
                        {"case_id": case_id, "issue": "feature_payload_decode_error", "error": type(exc).__name__}
                    )
                continue
            try:
                outcome = decode_payload(row[23])
            except Exception as exc:
                counts["outcome_payload_decode_error"] += 1
                if len(sample_issues) < 20:
                    sample_issues.append(
                        {"case_id": case_id, "issue": "outcome_payload_decode_error", "error": type(exc).__name__}
                    )
                continue
            case_issues = audit_case_payload_pair(
                feature_columns,
                outcome_columns,
                feature,
                outcome,
                work_unit=units.get(str(feature_columns["work_unit_id"])),
                expected_contract_version=EXPECTED_CONTRACT_VERSION,
            )
            counts.update(case_issues)
            if case_issues and len(sample_issues) < 20:
                sample_issues.append(
                    {"case_id": case_id, "issues": dict(sorted(case_issues.items()))}
                )
            if feature.get("full_development_scan_started") is False:
                counts["obsolete_full_development_scan_started_false"] += 1
            else:
                counts["obsolete_full_development_scan_started_not_false"] += 1
        if row_count == 0:
            break
        batch_number += 1
        batch_payload: dict[str, object] = {
            "version": STORE_AUDIT_VERSION,
            "context_fingerprint": context_fingerprint,
            "batch_number": batch_number,
            "first_case_id": first_case_id,
            "last_case_id": last_case_id,
            "row_count": row_count,
            "issue_counts": dict(sorted(counts.items())),
            "sample_issues": sample_issues,
            "row_digest": batch_digest.hexdigest(),
        }
        batch_payload["batch_fingerprint"] = fingerprint(batch_payload)
        with diagnostic:
            diagnostic.execute(
                "INSERT INTO store_audit_batches_v2 VALUES (?,?,?,?,?,?)",
                (
                    batch_number, first_case_id, last_case_id, row_count,
                    batch_payload["batch_fingerprint"], canonical_json(batch_payload),
                ),
            )
        existing_batches.append(batch_payload)
    source.close()
    aggregate_counts: Counter[str] = Counter()
    aggregate_samples: list[dict[str, object]] = []
    audited_rows = 0
    ordered_batch_digest = hashlib.sha256()
    for item in existing_batches:
        audited_rows += int(item["row_count"])
        aggregate_counts.update(
            {str(key): int(value) for key, value in dict(item["issue_counts"]).items()}
        )
        for sample in item.get("sample_issues") or []:
            if len(aggregate_samples) < 50:
                aggregate_samples.append(dict(sample))
        ordered_batch_digest.update(str(item["batch_fingerprint"]).encode("ascii"))
        ordered_batch_digest.update(b"\n")
    non_error_metadata_count = int(
        aggregate_counts.pop("obsolete_full_development_scan_started_false", 0)
    )
    obsolete_flag_invalid = int(
        aggregate_counts.get("obsolete_full_development_scan_started_not_false", 0)
    )
    sqlite_integrity = {
        "feature": _database_integrity(feature_path, role="FEATURES"),
        "outcome": _database_integrity(outcome_path, role="OUTCOMES"),
        "control": _database_integrity(control_path, role="CONTROL"),
    }
    source_hashes_after = {
        "feature": file_sha256(feature_path),
        "outcome": file_sha256(outcome_path),
        "control": file_sha256(control_path),
    }
    unit_status_counts = Counter(str(item["status"]) for item in units.values())
    work_unit_feature_rows = sum(int(item["feature_rows"]) for item in units.values())
    work_unit_outcome_rows = sum(int(item["outcome_rows"]) for item in units.values())
    set_and_count_ok = all(
        (
            set_summary["feature_rows"] == set_summary["outcome_rows"],
            set_summary["feature_only_rows"] == 0,
            set_summary["outcome_only_rows"] == 0,
            set_summary["feature_duplicate_case_ids"] == 0,
            set_summary["outcome_duplicate_case_ids"] == 0,
            audited_rows == set_summary["feature_rows"],
            int(run["feature_rows"]) == set_summary["feature_rows"],
            int(run["outcome_rows"]) == set_summary["outcome_rows"],
            work_unit_feature_rows == set_summary["feature_rows"],
            work_unit_outcome_rows == set_summary["outcome_rows"],
        )
    )
    append_only_trigger_ok = all(
        {f"{table}_no_update", f"{table}_no_delete"}.issubset(
            set(sqlite_integrity[role]["triggers"])
        )
        for role, table in (("feature", "feature_rows"), ("outcome", "outcome_rows"))
    )
    payload_issue_count = sum(int(value) for value in aggregate_counts.values())
    integrity_ok = all(bool(item["integrity_ok"]) for item in sqlite_integrity.values())
    audit_pass = all(
        (
            set_and_count_ok,
            payload_issue_count == 0,
            obsolete_flag_invalid == 0,
            integrity_ok,
            append_only_trigger_ok,
            source_hashes_before == source_hashes_after,
            int(run["total_planned_work_units"]) == len(units),
            not any(status in unit_status_counts for status in ("PENDING", "RUNNING")),
        )
    )
    payload: dict[str, object] = {
        "version": STORE_AUDIT_VERSION,
        "report": "FULL_STORE_AUDIT",
        "created_at": created_at,
        "run_id": RUN_ID,
        "status": "PASS" if audit_pass else "FAIL",
        "context_fingerprint": context_fingerprint,
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after,
        "source_stores_changed": source_hashes_before != source_hashes_after,
        "physically_separate_stores": len(
            {feature_path.resolve(), outcome_path.resolve(), control_path.resolve()}
        ) == 3,
        "set_summary": set_summary,
        "audited_case_pairs": audited_rows,
        "audit_batches": len(existing_batches),
        "ordered_batch_digest": ordered_batch_digest.hexdigest(),
        "payload_issue_counts": dict(sorted(aggregate_counts.items())),
        "payload_issue_count": payload_issue_count,
        "sample_issues": aggregate_samples,
        "obsolete_metadata": {
            "field": "full_development_scan_started",
            "false_count": non_error_metadata_count,
            "not_false_count": obsolete_flag_invalid,
            "classification": "OBSOLETE_PER_CASE_METADATA_NOT_OPERATIONAL_RUN_STATE",
            "used_as_runtime_truth": False,
            "rewritten": False,
        },
        "work_unit_summary": {
            "total": len(units),
            "status_counts": dict(sorted(unit_status_counts.items())),
            "summed_feature_rows": work_unit_feature_rows,
            "summed_outcome_rows": work_unit_outcome_rows,
        },
        "run_summary": run,
        "set_and_count_ok": set_and_count_ok,
        "sqlite_integrity": sqlite_integrity,
        "sqlite_integrity_ok": integrity_ok,
        "append_only_feature_outcome_triggers_ok": append_only_trigger_ok,
        "case_id_set_equality": (
            set_summary["feature_only_rows"] == 0
            and set_summary["outcome_only_rows"] == 0
        ),
        "duplicate_case_ids_absent": (
            set_summary["feature_duplicate_case_ids"] == 0
            and set_summary["outcome_duplicate_case_ids"] == 0
        ),
        "all_payloads_decompressed_and_verified": audited_rows == set_summary["feature_rows"],
        "decision_timestamp_linkage": {
            "canonical_location": "FEATURE_PAYLOAD.decision_time",
            "outcome_direct_field_required_by_frozen_v5_contract": False,
            "outcome_linked_via_verified_feature_fingerprint": payload_issue_count == 0,
        },
        "expected_contract_version": EXPECTED_CONTRACT_VERSION,
        "validation_opened": False,
        "holdout_opened": False,
        "performance_analysis_performed": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_artifact(artifact_path, payload)
    with diagnostic:
        diagnostic.execute(
            "INSERT OR IGNORE INTO audit_snapshots VALUES (?,?,?,?)",
            (
                payload["artifact_fingerprint"], "FULL_STORE_AUDIT", created_at,
                canonical_json(payload),
            ),
        )
    diagnostic.close()
    return payload
