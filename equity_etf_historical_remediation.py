from __future__ import annotations

"""Versioned, non-imputing Equity/ETF OHLC remediation for Development.

The frozen parquet files remain immutable.  This module creates a separate
SQLite projection containing only valid Development bars plus an explicit
archive of every rejected source row.
"""

import json
import math
import os
import sqlite3
import uuid
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from multi_asset_development_execution import build_development_universe, decode_payload
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECTION_VERSION = "equity-etf-historical-pit-2026.09.03-v1"
REMEDIATION_VERSION = "equity-etf-historical-remediation-2026.09.03-v1"
DEVELOPMENT_START = "2016-01-01"
DEVELOPMENT_END = "2021-12-31"
DEFAULT_DATASET_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)
DEFAULT_OUTCOME_STORE = (
    PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_development_v5_outcomes.sqlite3"
)
DEFAULT_TARGET_STORE = (
    PROJECT_ROOT / "runtime" / "equity_etf_historical_pit_2026-09-03-v1.sqlite3"
)
DEFAULT_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "equity_etf_historical_pit_2026-09-03-v1.json"
)


class EquityEtfHistoricalRemediationError(RuntimeError):
    pass


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def ohlc_source_violations(row: Mapping[str, object]) -> list[dict[str, object]]:
    """Return exact OHLC violations without changing provider values."""

    values = {name: _finite(row.get(name)) for name in ("Open", "High", "Low", "Close")}
    violations: list[dict[str, object]] = []
    for field, value in values.items():
        if value is None:
            violations.append(
                {"violation": f"{field.upper()}_MISSING_OR_NON_NUMERIC", "field": field}
            )
        elif value <= 0:
            violations.append(
                {
                    "violation": f"{field.upper()}_NOT_POSITIVE",
                    "field": field,
                    "value": value,
                }
            )
    if any(value is None for value in values.values()):
        return violations
    low = float(values["Low"])
    high = float(values["High"])

    def add(field: str, kind: str, absolute: float, reference: float) -> None:
        violations.append(
            {
                "violation": kind,
                "field": field,
                "absolute": absolute,
                "relative_pct": absolute / abs(reference) * 100 if reference else None,
            }
        )

    if low > high:
        add("Low", "LOW_ABOVE_HIGH", low - high, high)
    for field in ("Open", "Close"):
        value = float(values[field])
        if value < low:
            add(field, f"{field.upper()}_BELOW_LOW", low - value, low)
        if value > high:
            add(field, f"{field.upper()}_ABOVE_HIGH", value - high, high)
    return violations


def _root_cause(violations: Sequence[Mapping[str, object]]) -> str:
    kinds = {str(item.get("violation") or "") for item in violations}
    if any(kind.endswith("_MISSING_OR_NON_NUMERIC") for kind in kinds):
        return "MISSING_OR_NON_NUMERIC_IN_FROZEN_SOURCE_ROW"
    if any(kind.endswith("_NOT_POSITIVE") for kind in kinds):
        return "NON_POSITIVE_VALUE_IN_FROZEN_SOURCE_ROW"
    return "UNKNOWN_NOT_PROVABLE_FROM_FROZEN_AUTO_ADJUSTED_BAR"


def _longest_gap(days: Sequence[str]) -> dict[str, object] | None:
    ordered = sorted({date.fromisoformat(day) for day in days})
    if len(ordered) < 2:
        return None
    best: dict[str, object] | None = None
    for left, right in zip(ordered, ordered[1:]):
        cursor = left + timedelta(days=1)
        weekdays = 0
        while cursor < right:
            weekdays += int(cursor.weekday() < 5)
            cursor += timedelta(days=1)
        candidate = {
            "after": left.isoformat(),
            "before": right.isoformat(),
            "calendar_days_without_active_bar": (right - left).days - 1,
            "weekday_gap_proxy": weekdays,
        }
        if best is None or (
            int(candidate["weekday_gap_proxy"]),
            int(candidate["calendar_days_without_active_bar"]),
        ) > (
            int(best["weekday_gap_proxy"]),
            int(best["calendar_days_without_active_bar"]),
        ):
            best = candidate
    return best


def _connect_build(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=120)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS build_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS build_progress (
            asset_key TEXT PRIMARY KEY,
            completed_at TEXT NOT NULL,
            raw_bars INTEGER NOT NULL,
            active_bars INTEGER NOT NULL,
            invalid_bars INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS active_bars (
            bar_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            listing_id TEXT,
            ticker TEXT NOT NULL,
            asset_class TEXT NOT NULL CHECK(asset_class IN ('EQUITIES','ETF')),
            session_date TEXT NOT NULL,
            open REAL NOT NULL CHECK(open > 0),
            high REAL NOT NULL CHECK(high > 0),
            low REAL NOT NULL CHECK(low > 0),
            close REAL NOT NULL CHECK(close > 0),
            volume REAL,
            source_file TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            source_history_fingerprint TEXT NOT NULL,
            bar_fingerprint TEXT NOT NULL UNIQUE,
            UNIQUE(asset_id, listing_id, session_date),
            CHECK(low <= open AND open <= high),
            CHECK(low <= close AND close <= high),
            CHECK(low <= high)
        );
        CREATE TABLE IF NOT EXISTS invalid_source_bars (
            invalid_bar_fingerprint TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            listing_id TEXT,
            ticker TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            session_date TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            root_cause TEXT NOT NULL,
            first_affected_case_id TEXT,
            affected_case_count INTEGER NOT NULL DEFAULT 0,
            invalid_json TEXT NOT NULL,
            UNIQUE(asset_id, listing_id, session_date, source_row)
        );
        CREATE TABLE IF NOT EXISTS asset_coverage (
            asset_key TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            listing_id TEXT,
            ticker TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            raw_bars INTEGER NOT NULL,
            active_valid_bars INTEGER NOT NULL,
            invalid_source_bars INTEGER NOT NULL,
            duplicate_source_sessions INTEGER NOT NULL,
            coverage_pct REAL NOT NULL,
            first_active_date TEXT,
            last_active_date TEXT,
            longest_gap_json TEXT,
            coverage_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projection_versions (
            version TEXT PRIMARY KEY,
            dataset_fingerprint TEXT NOT NULL UNIQUE,
            invalid_manifest_fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS active_bars_symbol_day
            ON active_bars(asset_class,ticker,session_date);
        CREATE INDEX IF NOT EXISTS invalid_source_bars_symbol_day
            ON invalid_source_bars(asset_class,ticker,session_date);
        """
    )
    return connection


def _ensure_build_identity(
    connection: sqlite3.Connection, *, source_manifest_sha256: str, created_at: str
) -> str:
    expected = {
        "projection_version": PROJECTION_VERSION,
        "source_manifest_sha256": source_manifest_sha256,
        "development_start": DEVELOPMENT_START,
        "development_end": DEVELOPMENT_END,
    }
    existing = dict(connection.execute("SELECT key,value FROM build_metadata"))
    if existing:
        for key, value in expected.items():
            if existing.get(key) != str(value):
                raise EquityEtfHistoricalRemediationError(
                    f"Unvollständige Projektion gehört zu anderem Input: {key}"
                )
        return existing["created_at"]
    with connection:
        connection.executemany(
            "INSERT INTO build_metadata(key,value) VALUES (?,?)",
            [(key, str(value)) for key, value in {**expected, "created_at": created_at}.items()],
        )
    return created_at


def _asset_frame(asset: Mapping[str, object], manifest_path: Path) -> pd.DataFrame:
    relative = str(asset.get("modern_file") or "")
    if not relative:
        raise EquityEtfHistoricalRemediationError(
            f"Frozen-Datei fehlt für {asset.get('asset_key')}"
        )
    frame = pd.read_parquet(
        manifest_path.parent / relative,
        filters=[
            ("Date", ">=", pd.Timestamp(DEVELOPMENT_START)),
            ("Date", "<=", pd.Timestamp(DEVELOPMENT_END)),
        ],
    )
    frame = frame.rename(columns={str(column).lower(): str(column).title() for column in frame.columns})
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.sort_index(kind="stable")
    frame["_SOURCE_ROW"] = range(len(frame))
    return frame


def _clean_value(value: object) -> float | None:
    result = _finite(value)
    return result


def _invalid_payload(
    *, asset: Mapping[str, object], row: Mapping[str, object], session_date: str,
    source_file: str, source_row: int, violations: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
) -> dict[str, object]:
    identity = dict(asset.get("identity") or {})
    values = {name.lower(): _clean_value(row.get(name)) for name in ("Open", "High", "Low", "Close", "Volume")}
    payload: dict[str, object] = {
        "classification": "INVALID_SOURCE_BAR",
        "asset_id": identity.get("asset_id") or asset["asset_key"],
        "listing_id": identity.get("listing_id"),
        "ticker": asset["symbol"],
        "asset_class": asset["asset_class"],
        "session_date": session_date,
        **values,
        "source": "Yahoo Finance/yfinance frozen parquet",
        "source_file": source_file,
        "source_row_in_development_slice": source_row,
        "source_history_fingerprint": asset.get("modern_history_fingerprint"),
        "violation_types": sorted({str(item["violation"]) for item in violations}),
        "violations": [dict(item) for item in violations],
        "maximum_relative_violation_pct": max(
            [float(item["relative_pct"]) for item in violations if item.get("relative_pct") is not None]
            or [0.0]
        ),
        "root_cause": _root_cause(violations),
        "provider_or_adjustment_root_cause": (
            "UNKNOWN_NOT_PROVABLE_FROM_FROZEN_AUTO_ADJUSTED_BAR"
        ),
        "source_adjustment": dict(manifest.get("provider_policy") or {}),
        "source_manifest_version": manifest.get("manifest_version"),
        "source_dataset_revision": manifest.get("dataset_revision"),
        "transformation_version": REMEDIATION_VERSION,
        "active_pit_allowed": False,
        "remediation": "EXCLUDED_WITHOUT_REPLACEMENT",
        "clipped": False,
        "imputed": False,
        "interpolated": False,
        "external_replacement_used": False,
    }
    payload["invalid_bar_fingerprint"] = fingerprint(payload)
    return payload


def _insert_asset(
    connection: sqlite3.Connection,
    *, asset: Mapping[str, object], manifest_path: Path,
    manifest: Mapping[str, object], completed_at: str,
) -> None:
    asset_key = str(asset["asset_key"])
    if connection.execute(
        "SELECT 1 FROM build_progress WHERE asset_key=?", (asset_key,)
    ).fetchone():
        return
    frame = _asset_frame(asset, manifest_path)
    raw_bars = len(frame)
    duplicate_count = int(frame.index.duplicated(keep="last").sum())
    canonical = frame.loc[~frame.index.duplicated(keep="last")]
    identity = dict(asset.get("identity") or {})
    asset_id = str(identity.get("asset_id") or asset_key)
    listing_id = identity.get("listing_id")
    source_file = str(asset["modern_file"])
    history_fingerprint = str(asset["modern_history_fingerprint"])
    active_rows: list[tuple[object, ...]] = []
    invalid_rows: list[tuple[object, ...]] = []
    active_days: list[str] = []
    for stamp, series in canonical.iterrows():
        row = series.to_dict()
        session_date = pd.Timestamp(stamp).date().isoformat()
        source_row = int(row["_SOURCE_ROW"])
        violations = ohlc_source_violations(row)
        if violations:
            payload = _invalid_payload(
                asset=asset,
                row=row,
                session_date=session_date,
                source_file=source_file,
                source_row=source_row,
                violations=violations,
                manifest=manifest,
            )
            invalid_rows.append(
                (
                    payload["invalid_bar_fingerprint"], asset_id, listing_id,
                    asset["symbol"], asset["asset_class"], session_date, source_file,
                    source_row, payload["root_cause"], canonical_json(payload),
                )
            )
            continue
        values = {name: float(row[name]) for name in ("Open", "High", "Low", "Close")}
        bar_basis = {
            "projection_version": PROJECTION_VERSION,
            "asset_id": asset_id,
            "listing_id": listing_id,
            "session_date": session_date,
            "source_history_fingerprint": history_fingerprint,
            "ohlc": values,
            "volume": _clean_value(row.get("Volume")),
        }
        bar_fingerprint = fingerprint(bar_basis)
        bar_id = f"eqetf-bar-{bar_fingerprint[:32]}"
        active_rows.append(
            (
                bar_id, asset_id, listing_id, asset["symbol"], asset["asset_class"],
                session_date, values["Open"], values["High"], values["Low"],
                values["Close"], _clean_value(row.get("Volume")), source_file,
                source_row, history_fingerprint, bar_fingerprint,
            )
        )
        active_days.append(session_date)
    coverage = {
        "asset_key": asset_key,
        "asset_id": asset_id,
        "listing_id": listing_id,
        "ticker": asset["symbol"],
        "asset_class": asset["asset_class"],
        "period": [DEVELOPMENT_START, DEVELOPMENT_END],
        "raw_bars": raw_bars,
        "active_valid_bars": len(active_rows),
        "invalid_source_bars": len(invalid_rows),
        "duplicate_source_sessions": duplicate_count,
        "missing_sessions_due_to_invalid_or_duplicate_source_rows": (
            len(invalid_rows) + duplicate_count
        ),
        "weekday_missing_sessions": "NOT_ASSERTED_WITHOUT_EXCHANGE_CALENDAR",
        "coverage_pct": round(len(active_rows) / raw_bars * 100, 8) if raw_bars else 0.0,
        "first_active_date": min(active_days) if active_days else None,
        "last_active_date": max(active_days) if active_days else None,
        "longest_gap": _longest_gap(active_days),
        "fully_unusable": len(active_rows) == 0,
    }
    with connection:
        connection.executemany(
            "INSERT INTO active_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            active_rows,
        )
        connection.executemany(
            "INSERT INTO invalid_source_bars("
            "invalid_bar_fingerprint,asset_id,listing_id,ticker,asset_class,session_date,"
            "source_file,source_row,root_cause,invalid_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            invalid_rows,
        )
        connection.execute(
            "INSERT INTO asset_coverage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                asset_key, asset_id, listing_id, asset["symbol"], asset["asset_class"],
                raw_bars, len(active_rows), len(invalid_rows), duplicate_count,
                coverage["coverage_pct"], coverage["first_active_date"],
                coverage["last_active_date"], canonical_json(coverage["longest_gap"]),
                canonical_json(coverage),
            ),
        )
        connection.execute(
            "INSERT INTO build_progress VALUES (?,?,?,?,?)",
            (asset_key, completed_at, raw_bars, len(active_rows), len(invalid_rows)),
        )


def _source_case_impacts(
    connection: sqlite3.Connection, *, outcome_path: Path
) -> dict[str, object]:
    affected_assets = {
        (str(row[0]), str(row[1]))
        for row in connection.execute(
            "SELECT DISTINCT asset_class,ticker FROM invalid_source_bars"
        )
    }
    cases: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    if affected_assets:
        uri = f"file:{outcome_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as outcomes:
            cursor = outcomes.execute(
                "SELECT case_id,symbol,asset_class,signal_day,payload_zlib "
                "FROM outcome_rows WHERE status='INVALID_TECHNICAL_ELIGIBILITY' "
                "ORDER BY asset_class,symbol,signal_day,case_id"
            )
            for case_id, symbol, asset_class, signal_day, blob in cursor:
                key = (str(asset_class), str(symbol))
                if key not in affected_assets:
                    continue
                if decode_payload(blob).get("reason") == "SOURCE_OHLC_ENVELOPE_ANOMALY":
                    cases[key].append((str(signal_day), str(case_id)))
    recoverable = 0
    total = sum(len(rows) for rows in cases.values())
    for key in sorted(affected_assets):
        asset_class, ticker = key
        sessions = sorted(
            {
                str(row[0])
                for row in connection.execute(
                    "SELECT session_date FROM active_bars WHERE asset_class=? AND ticker=? "
                    "UNION SELECT session_date FROM invalid_source_bars "
                    "WHERE asset_class=? AND ticker=?",
                    (asset_class, ticker, asset_class, ticker),
                )
            }
        )
        positions = {day: index for index, day in enumerate(sessions)}
        active = {
            str(row[0])
            for row in connection.execute(
                "SELECT session_date FROM active_bars WHERE asset_class=? AND ticker=?",
                (asset_class, ticker),
            )
        }
        active_order = sorted(active)
        active_positions = {day: index for index, day in enumerate(active_order)}
        asset_cases = cases.get(key, [])
        for signal_day, _ in asset_cases:
            position = active_positions.get(signal_day)
            if position is not None and position >= 219 and position < len(active_order) - 1:
                recoverable += 1
        for invalid_fp, invalid_day in connection.execute(
            "SELECT invalid_bar_fingerprint,session_date FROM invalid_source_bars "
            "WHERE asset_class=? AND ticker=? ORDER BY session_date,source_row",
            (asset_class, ticker),
        ):
            bad_position = positions[str(invalid_day)]
            influenced = [
                (signal_day, case_id)
                for signal_day, case_id in asset_cases
                if signal_day in positions and bad_position <= positions[signal_day] + 252
            ]
            connection.execute(
                "UPDATE invalid_source_bars SET first_affected_case_id=?,affected_case_count=? "
                "WHERE invalid_bar_fingerprint=?",
                (
                    influenced[0][1] if influenced else None,
                    len(influenced),
                    invalid_fp,
                ),
            )
    connection.commit()
    return {
        "legacy_ohlc_invalid_case_count": total,
        "recoverable_after_clean_projection_count": recoverable,
        "not_recoverable_without_new_signal_case_count": total - recoverable,
    }


def _digest_rows(connection: sqlite3.Connection, query: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    for row in connection.execute(query):
        digest.update("\x1f".join(str(value) for value in row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _add_append_only_triggers(connection: sqlite3.Connection) -> None:
    for table in (
        "active_bars",
        "invalid_source_bars",
        "asset_coverage",
        "projection_versions",
        "build_metadata",
        "build_progress",
    ):
        connection.executescript(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table}
                BEGIN SELECT RAISE(ABORT, '{table} append-only'); END;
            CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table}
                BEGIN SELECT RAISE(ABORT, '{table} append-only'); END;
            """
        )


def build_equity_etf_clean_projection(
    *,
    target_path: Path = DEFAULT_TARGET_STORE,
    artifact_path: Path = DEFAULT_ARTIFACT,
    manifest_path: Path = DEFAULT_DATASET_MANIFEST,
    outcome_path: Path = DEFAULT_OUTCOME_STORE,
    assets: Sequence[Mapping[str, object]] | None = None,
    created_at: str,
    code_commit: str,
    branch: str,
    command: str,
) -> dict[str, object]:
    """Build or resume the separate clean Development projection."""

    target_path = Path(target_path)
    artifact_path = Path(artifact_path)
    manifest_path = Path(manifest_path)
    if target_path.exists():
        uri = f"file:{target_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as existing:
            row = existing.execute(
                "SELECT manifest_json FROM projection_versions WHERE version=?",
                (PROJECTION_VERSION,),
            ).fetchone()
        if row is None:
            raise EquityEtfHistoricalRemediationError("Vorhandene Projektion ist unvollständig.")
        return json.loads(str(row[0]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = list(assets) if assets is not None else [
        item
        for item in build_development_universe()["assets"]
        if item["asset_class"] in {"EQUITIES", "ETF"}
    ]
    selected.sort(key=lambda item: (str(item["asset_class"]), str(item["symbol"])))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    building = target_path.with_name(f".{target_path.name}.building")
    connection = _connect_build(building)
    actual_created_at = _ensure_build_identity(
        connection,
        source_manifest_sha256=file_sha256(manifest_path),
        created_at=created_at,
    )
    for asset in selected:
        _insert_asset(
            connection,
            asset=asset,
            manifest_path=manifest_path,
            manifest=manifest,
            completed_at=actual_created_at,
        )
    expected_assets = {str(item["asset_key"]) for item in selected}
    completed_assets = {
        str(row[0]) for row in connection.execute("SELECT asset_key FROM build_progress")
    }
    if completed_assets != expected_assets:
        raise EquityEtfHistoricalRemediationError("Projektion ist nicht vollständig aufgebaut.")
    impacts = _source_case_impacts(connection, outcome_path=outcome_path)
    active_digest = _digest_rows(
        connection,
        "SELECT bar_fingerprint FROM active_bars ORDER BY bar_fingerprint",
    )
    invalid_digest = _digest_rows(
        connection,
        "SELECT invalid_bar_fingerprint,affected_case_count,"
        "COALESCE(first_affected_case_id,'') FROM invalid_source_bars "
        "ORDER BY invalid_bar_fingerprint",
    )
    coverage_digest = _digest_rows(
        connection,
        "SELECT asset_key,coverage_json FROM asset_coverage ORDER BY asset_key",
    )
    counts = {
        "raw_bars": int(connection.execute("SELECT COALESCE(SUM(raw_bars),0) FROM asset_coverage").fetchone()[0]),
        "active_valid_bars": int(connection.execute("SELECT COUNT(*) FROM active_bars").fetchone()[0]),
        "invalid_source_bars": int(connection.execute("SELECT COUNT(*) FROM invalid_source_bars").fetchone()[0]),
        "affected_assets": int(connection.execute("SELECT COUNT(DISTINCT asset_id) FROM invalid_source_bars").fetchone()[0]),
        "fully_unusable_assets": int(connection.execute("SELECT COUNT(*) FROM asset_coverage WHERE active_valid_bars=0").fetchone()[0]),
    }
    class_counts = {
        str(row[0]): {
            "assets": int(row[1]),
            "raw_bars": int(row[2]),
            "active_valid_bars": int(row[3]),
            "invalid_source_bars": int(row[4]),
        }
        for row in connection.execute(
            "SELECT asset_class,COUNT(*),SUM(raw_bars),SUM(active_valid_bars),"
            "SUM(invalid_source_bars) FROM asset_coverage GROUP BY asset_class"
        )
    }
    root_causes = dict(
        Counter(
            str(row[0])
            for row in connection.execute("SELECT root_cause FROM invalid_source_bars")
        )
    )
    dataset_basis = {
        "version": PROJECTION_VERSION,
        "source_dataset_fingerprint": manifest["dataset_fingerprint"],
        "source_manifest_sha256": file_sha256(manifest_path),
        "active_bar_digest": active_digest,
        "invalid_manifest_fingerprint": invalid_digest,
        "coverage_fingerprint": coverage_digest,
    }
    dataset_fingerprint = fingerprint(dataset_basis)
    result: dict[str, object] = {
        "version": PROJECTION_VERSION,
        "remediation_version": REMEDIATION_VERSION,
        "status": "EQUITY_ETF_DEVELOPMENT_ACTIVE_PIT_READY_WITH_INVALID_SOURCE_BARS_EXCLUDED",
        "created_at": actual_created_at,
        "period": [DEVELOPMENT_START, DEVELOPMENT_END],
        "source_dataset_fingerprint": manifest["dataset_fingerprint"],
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_price_adjustment": "yfinance_auto_adjust_true",
        "source_lineage": "frozen parquet; no provider redownload",
        "target_store": str(target_path.resolve()),
        "asset_count": len(selected),
        "counts": counts,
        "asset_class_counts": class_counts,
        "root_cause_counts": root_causes,
        "case_impact": impacts,
        "active_envelope_anomaly_count": int(
            connection.execute(
                "SELECT COUNT(*) FROM active_bars WHERE NOT (low<=open AND open<=high "
                "AND low<=close AND close<=high AND low<=high)"
            ).fetchone()[0]
        ),
        "active_non_positive_ohlc_count": int(
            connection.execute(
                "SELECT COUNT(*) FROM active_bars WHERE open<=0 OR high<=0 OR low<=0 OR close<=0"
            ).fetchone()[0]
        ),
        "dataset_fingerprint": dataset_fingerprint,
        "invalid_bar_manifest_fingerprint": invalid_digest,
        "active_bar_digest": active_digest,
        "coverage_fingerprint": coverage_digest,
        "code_commit": code_commit,
        "branch": branch,
        "command": command,
        "no_clipping": True,
        "no_imputation": True,
        "no_interpolation": True,
        "original_frozen_dataset_changed": False,
        "research_rules_changed": False,
        "performance_analysis_performed": False,
    }
    result["manifest_fingerprint"] = fingerprint(result)
    with connection:
        connection.execute(
            "INSERT INTO projection_versions VALUES (?,?,?,?,?)",
            (
                PROJECTION_VERSION,
                dataset_fingerprint,
                invalid_digest,
                actual_created_at,
                canonical_json(result),
            ),
        )
        _add_append_only_triggers(connection)
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise EquityEtfHistoricalRemediationError("Zielprojektion ist nicht integer.")
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    os.replace(building, target_path)
    result["target_store_sha256"] = file_sha256(target_path)
    result["artifact_fingerprint"] = fingerprint(result)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
