from __future__ import annotations

"""Append-only evidence stores for the Development-v6 reprocessing run.

The feature and outcome databases are intentionally separate.  Only the
runner's main process may call :func:`persist_and_complete_work_unit`.  A
control-store receipt is written only after both evidence stores have been
re-read and their case sets and payload fingerprints agree.  This makes a
crash between the two SQLite commits safely resumable without pretending that
SQLite can provide a transaction across database files.
"""

import json
import os
import sqlite3
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from multi_asset_discovery_v1 import canonical_json, fingerprint


STORE_SCHEMA_VERSION = "multi-asset-discovery-development-store-2026.09.05-v6"
CONTROL_SCHEMA_VERSION = "multi-asset-discovery-development-control-2026.09.05-v6"
TERMINAL_RUN_STATUSES = frozenset(
    {"COMPLETED", "PAUSED_REQUIRES_REVIEW", "FAILED", "CANCELLED"}
)
TERMINAL_UNIT_STATUSES = frozenset({"COMPLETED", "SKIPPED", "FAILED"})


class DevelopmentV6StoreError(RuntimeError):
    """Evidence cannot be persisted without violating v6 provenance."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(
    path: Path, *, readonly: bool = False
) -> Iterator[sqlite3.Connection]:
    """Open one transaction and always release its Windows file handle."""

    path = Path(path)
    if readonly:
        connection = sqlite3.connect(
            f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=60
        )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=60)
    try:
        if not readonly:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        with connection:
            yield connection
    finally:
        connection.close()


def _compress(payload: Mapping[str, object]) -> bytes:
    return zlib.compress(canonical_json(payload).encode("utf-8"), level=6)


def decode_payload(value: bytes) -> dict[str, object]:
    return json.loads(zlib.decompress(value).decode("utf-8"))


def _append_only_triggers(table: str) -> str:
    return f"""
    CREATE TRIGGER IF NOT EXISTS no_update_{table}
    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'append_only'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_{table}
    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'append_only'); END;
    """


def initialize_v6_stores(
    *, feature_path: Path, outcome_path: Path, control_path: Path
) -> None:
    with _connect(feature_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS store_metadata (
                metadata_fingerprint TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feature_rows (
                case_id TEXT PRIMARY KEY,
                feature_fingerprint TEXT NOT NULL,
                run_id TEXT NOT NULL,
                work_unit_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                research_split TEXT NOT NULL CHECK(research_split='development'),
                dependency_status TEXT NOT NULL,
                payload_zlib BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_v6_feature_run_unit
            ON feature_rows(run_id, work_unit_id, case_id);
            """
            + _append_only_triggers("store_metadata")
            + _append_only_triggers("feature_rows")
        )
    with _connect(outcome_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS store_metadata (
                metadata_fingerprint TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outcome_rows (
                case_id TEXT PRIMARY KEY,
                outcome_fingerprint TEXT NOT NULL,
                feature_fingerprint TEXT NOT NULL,
                run_id TEXT NOT NULL,
                work_unit_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                research_split TEXT NOT NULL CHECK(research_split='development'),
                status TEXT NOT NULL,
                r_availability TEXT NOT NULL,
                dependency_status TEXT NOT NULL,
                payload_zlib BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_v6_outcome_run_unit
            ON outcome_rows(run_id, work_unit_id, case_id);
            """
            + _append_only_triggers("store_metadata")
            + _append_only_triggers("outcome_rows")
        )
    with _connect(control_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                contract_fingerprint TEXT NOT NULL,
                combined_input_fingerprint TEXT NOT NULL,
                universe_fingerprint TEXT NOT NULL,
                work_plan_fingerprint TEXT NOT NULL,
                run_manifest_fingerprint TEXT NOT NULL,
                code_commit TEXT NOT NULL,
                worker_count INTEGER NOT NULL CHECK(worker_count IN (1,2,4,6)),
                sqlite_writer_count INTEGER NOT NULL CHECK(sqlite_writer_count=1),
                total_planned_work_units INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                last_checkpoint_at TEXT NOT NULL,
                pause_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS work_units (
                work_unit_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                asset_key TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                symbol TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                feature_rows INTEGER NOT NULL DEFAULT 0,
                outcome_rows INTEGER NOT NULL DEFAULT 0,
                r_na_cases INTEGER NOT NULL DEFAULT 0,
                censored_cases INTEGER NOT NULL DEFAULT 0,
                missing_reference_entry INTEGER NOT NULL DEFAULT 0,
                missingness_exclusions INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                last_error_class TEXT,
                last_error_message TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_v6_units_run_status
            ON work_units(run_id, status, asset_class, symbol, period_start);
            CREATE TABLE IF NOT EXISTS unit_receipts (
                receipt_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                work_unit_id TEXT NOT NULL UNIQUE,
                feature_rows INTEGER NOT NULL,
                outcome_rows INTEGER NOT NULL,
                case_set_digest TEXT NOT NULL,
                feature_payload_digest TEXT NOT NULL,
                outcome_payload_digest TEXT NOT NULL,
                writer_pid INTEGER NOT NULL,
                committed_at TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id),
                FOREIGN KEY(work_unit_id) REFERENCES work_units(work_unit_id)
            );
            CREATE TABLE IF NOT EXISTS run_events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                work_unit_id TEXT,
                event_type TEXT NOT NULL,
                event_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TRIGGER IF NOT EXISTS no_delete_runs
            BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT, 'run_history'); END;
            CREATE TRIGGER IF NOT EXISTS no_reopen_terminal_run
            BEFORE UPDATE ON runs
            WHEN OLD.status IN ('COMPLETED','PAUSED_REQUIRES_REVIEW','FAILED','CANCELLED')
            BEGIN SELECT RAISE(ABORT, 'terminal_run_immutable'); END;
            CREATE TRIGGER IF NOT EXISTS no_delete_work_units
            BEFORE DELETE ON work_units BEGIN SELECT RAISE(ABORT, 'work_unit_history'); END;
            CREATE TRIGGER IF NOT EXISTS no_reopen_terminal_work_unit
            BEFORE UPDATE ON work_units
            WHEN OLD.status IN ('COMPLETED','SKIPPED','FAILED')
            BEGIN SELECT RAISE(ABORT, 'terminal_work_unit_immutable'); END;
            """
            + _append_only_triggers("unit_receipts")
            + _append_only_triggers("run_events")
        )


def _insert_store_metadata(path: Path, metadata: Mapping[str, object]) -> None:
    key = fingerprint(metadata)
    encoded = canonical_json(metadata)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM store_metadata WHERE metadata_fingerprint=?",
            (key,),
        ).fetchone()
        if row is not None and str(row[0]) != encoded:
            raise DevelopmentV6StoreError("Store metadata fingerprint collision.")
        connection.execute(
            "INSERT OR IGNORE INTO store_metadata VALUES (?,?)", (key, encoded)
        )


def initialize_v6_run(
    *,
    run_manifest: Mapping[str, object],
    work_plan: Mapping[str, object],
    feature_path: Path,
    outcome_path: Path,
    control_path: Path,
) -> str:
    initialize_v6_stores(
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    run_id = str(run_manifest["run_id"])
    metadata = {
        "schema_version": STORE_SCHEMA_VERSION,
        "run_id": run_id,
        "contract_fingerprint": run_manifest["development_contract_fingerprint"],
        "combined_input_fingerprint": run_manifest["combined_input_fingerprint"],
        "run_manifest_fingerprint": run_manifest["run_manifest_fingerprint"],
        "payload_encoding": "canonical_json_zlib",
        "append_only": True,
    }
    _insert_store_metadata(feature_path, {**metadata, "store_role": "FEATURES"})
    _insert_store_metadata(outcome_path, {**metadata, "store_role": "OUTCOMES"})
    expected = (
        str(run_manifest["development_contract_fingerprint"]),
        str(run_manifest["combined_input_fingerprint"]),
        str(run_manifest["universe_fingerprint"]),
        str(run_manifest["work_plan_fingerprint"]),
        str(run_manifest["run_manifest_fingerprint"]),
    )
    with _connect(control_path) as connection:
        existing = connection.execute(
            "SELECT contract_fingerprint,combined_input_fingerprint,universe_fingerprint,"
            "work_plan_fingerprint,run_manifest_fingerprint FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if existing is not None and tuple(map(str, existing)) != expected:
            raise DevelopmentV6StoreError("Run ID already belongs to other provenance.")
        if existing is None:
            connection.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    *expected,
                    str(run_manifest["commit"]),
                    int(run_manifest["worker_count"]),
                    int(run_manifest["sqlite_writer_count"]),
                    int(work_plan["total_planned_work_units"]),
                    "RUNNING",
                    str(run_manifest["started_at"]),
                    None,
                    str(run_manifest["started_at"]),
                    None,
                ),
            )
        for unit in work_plan.get("units") or []:
            connection.execute(
                "INSERT OR IGNORE INTO work_units("
                "work_unit_id,run_id,asset_key,asset_class,symbol,period_start,period_end,status"
                ") VALUES (?,?,?,?,?,?,?,'PENDING')",
                (
                    unit["work_unit_id"],
                    run_id,
                    unit["asset_key"],
                    unit["asset_class"],
                    unit["symbol"],
                    unit["period_start"],
                    unit["period_end"],
                ),
            )
        actual = int(
            connection.execute(
                "SELECT COUNT(*) FROM work_units WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
        if actual != int(work_plan["total_planned_work_units"]):
            raise DevelopmentV6StoreError("Control store work-plan count mismatch.")
    return run_id


def append_run_event(
    *,
    control_path: Path,
    run_id: str,
    event_type: str,
    work_unit_id: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    event_at = utc_now()
    payload = {
        "run_id": run_id,
        "work_unit_id": work_unit_id,
        "event_type": event_type,
        "event_at": event_at,
        "details": dict(details or {}),
    }
    event_id = "madv6-event-" + fingerprint(payload)[:32]
    with _connect(control_path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO run_events VALUES (?,?,?,?,?,?)",
            (
                event_id,
                run_id,
                work_unit_id,
                event_type,
                event_at,
                canonical_json(payload),
            ),
        )


def reset_interrupted_units(*, control_path: Path, run_id: str) -> int:
    with _connect(control_path) as connection:
        running = int(
            connection.execute(
                "SELECT COUNT(*) FROM work_units WHERE run_id=? AND status='RUNNING'",
                (run_id,),
            ).fetchone()[0]
        )
        connection.execute(
            "UPDATE work_units SET status='PENDING',started_at=NULL "
            "WHERE run_id=? AND status='RUNNING'",
            (run_id,),
        )
    return running


def claim_next_asset_batch(
    *, control_path: Path, run_id: str
) -> list[dict[str, object]]:
    """Claim all remaining quarters for one asset in one control transaction."""

    with _connect(control_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        first = connection.execute(
            "SELECT asset_key FROM work_units WHERE run_id=? AND status='PENDING' "
            "ORDER BY asset_class,symbol,period_start LIMIT 1",
            (run_id,),
        ).fetchone()
        if first is None:
            connection.commit()
            return []
        rows = connection.execute(
            "SELECT work_unit_id,asset_key,asset_class,symbol,period_start,period_end,attempts "
            "FROM work_units WHERE run_id=? AND status='PENDING' AND asset_key=? "
            "ORDER BY period_start",
            (run_id, str(first[0])),
        ).fetchall()
        started_at = utc_now()
        connection.executemany(
            "UPDATE work_units SET status='RUNNING',attempts=attempts+1,started_at=?,"
            "last_error_class=NULL,last_error_message=NULL WHERE work_unit_id=?",
            [(started_at, row[0]) for row in rows],
        )
        connection.execute(
            "UPDATE runs SET last_checkpoint_at=? WHERE run_id=?",
            (started_at, run_id),
        )
        connection.commit()
    return [
        {
            "work_unit_id": row[0],
            "asset_key": row[1],
            "asset_class": row[2],
            "symbol": row[3],
            "period_start": row[4],
            "period_end": row[5],
            "attempts": int(row[6]) + 1,
        }
        for row in rows
    ]


def _evidence_rows(
    path: Path, *, table: str, run_id: str, work_unit_id: str
) -> list[tuple[str, str, str | None]]:
    digest_column = "feature_fingerprint" if table == "feature_rows" else "outcome_fingerprint"
    link_column = "NULL" if table == "feature_rows" else "feature_fingerprint"
    with _connect(path, readonly=True) as connection:
        rows = connection.execute(
            f"SELECT case_id,{digest_column},{link_column} FROM {table} "
            "WHERE run_id=? AND work_unit_id=? ORDER BY case_id",
            (run_id, work_unit_id),
        ).fetchall()
    return [(str(a), str(b), None if c is None else str(c)) for a, b, c in rows]


def _existing_digests(
    connection: sqlite3.Connection,
    *,
    table: str,
    digest_column: str,
    case_ids: Sequence[str],
) -> dict[str, str]:
    """Fetch append-only conflicts in bounded batches instead of once per row."""

    if (table, digest_column) not in {
        ("feature_rows", "feature_fingerprint"),
        ("outcome_rows", "outcome_fingerprint"),
    }:
        raise DevelopmentV6StoreError("Unsupported evidence digest lookup.")
    unique_ids = list(dict.fromkeys(str(item) for item in case_ids))
    result: dict[str, str] = {}
    # Keep comfortably below SQLite's build-dependent parameter limit.
    for offset in range(0, len(unique_ids), 500):
        chunk = unique_ids[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = connection.execute(
            f"SELECT case_id,{digest_column} FROM {table} "
            f"WHERE case_id IN ({placeholders})",
            chunk,
        ).fetchall()
        result.update((str(case_id), str(digest)) for case_id, digest in rows)
    return result


def _insert_features(
    *,
    path: Path,
    run_id: str,
    work_unit_id: str,
    features: Sequence[Mapping[str, object]],
) -> None:
    if not features:
        return
    with _connect(path) as connection:
        case_ids = [str(item["case_id"]) for item in features]
        existing = _existing_digests(
            connection,
            table="feature_rows",
            digest_column="feature_fingerprint",
            case_ids=case_ids,
        )
        for item in features:
            prior = existing.get(str(item["case_id"]))
            if prior is not None and prior != str(item["feature_fingerprint"]):
                raise DevelopmentV6StoreError(
                    f"Feature append-only conflict: {item['case_id']}"
                )
        rows = [
            (
                item["case_id"],
                item["feature_fingerprint"],
                run_id,
                work_unit_id,
                item["asset_id"],
                item["symbol"],
                item["asset_class"],
                item["signal_day"],
                item["research_split"],
                item.get("dependency_status") or "UNKNOWN",
                _compress(item),
            )
            for item in features
            if str(item["case_id"]) not in existing
        ]
        if rows:
            connection.executemany(
                "INSERT INTO feature_rows VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows
            )


def _insert_outcomes(
    *,
    path: Path,
    run_id: str,
    work_unit_id: str,
    outcomes: Sequence[Mapping[str, object]],
) -> None:
    if not outcomes:
        return
    with _connect(path) as connection:
        case_ids = [str(item["case_id"]) for item in outcomes]
        existing = _existing_digests(
            connection,
            table="outcome_rows",
            digest_column="outcome_fingerprint",
            case_ids=case_ids,
        )
        for item in outcomes:
            prior = existing.get(str(item["case_id"]))
            if prior is not None and prior != str(item["outcome_fingerprint"]):
                raise DevelopmentV6StoreError(
                    f"Outcome append-only conflict: {item['case_id']}"
                )
        rows = [
            (
                item["case_id"],
                item["outcome_fingerprint"],
                item["feature_fingerprint"],
                run_id,
                work_unit_id,
                item["asset_id"],
                item["symbol"],
                item["asset_class"],
                item["signal_day"],
                item["research_split"],
                item["status"],
                item.get("r_availability")
                or item.get("r_metrics_status")
                or "UNAVAILABLE",
                item.get("dependency_status") or "UNKNOWN",
                _compress(item),
            )
            for item in outcomes
            if str(item["case_id"]) not in existing
        ]
        if rows:
            connection.executemany(
                "INSERT INTO outcome_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )


def _expected_evidence(
    features: Sequence[Mapping[str, object]],
    outcomes: Sequence[Mapping[str, object]],
) -> tuple[list[tuple[str, str, None]], list[tuple[str, str, str]]]:
    feature_rows = sorted(
        (str(item["case_id"]), str(item["feature_fingerprint"]), None)
        for item in features
    )
    outcome_rows = sorted(
        (
            str(item["case_id"]),
            str(item["outcome_fingerprint"]),
            str(item["feature_fingerprint"]),
        )
        for item in outcomes
    )
    if len({row[0] for row in feature_rows}) != len(feature_rows):
        raise DevelopmentV6StoreError("Duplicate feature case in work-unit payload.")
    if len({row[0] for row in outcome_rows}) != len(outcome_rows):
        raise DevelopmentV6StoreError("Duplicate outcome case in work-unit payload.")
    if {row[0] for row in feature_rows} != {row[0] for row in outcome_rows}:
        raise DevelopmentV6StoreError("Feature/outcome case sets differ before write.")
    feature_links = {row[0]: row[1] for row in feature_rows}
    if any(feature_links[row[0]] != row[2] for row in outcome_rows):
        raise DevelopmentV6StoreError("Outcome links to wrong feature fingerprint.")
    return feature_rows, outcome_rows


def _completed_receipt_if_exact(
    *,
    control_path: Path,
    feature_path: Path,
    outcome_path: Path,
    run_id: str,
    work_unit_id: str,
    expected_features: Sequence[tuple[str, str, None]],
    expected_outcomes: Sequence[tuple[str, str, str]],
    summary: Mapping[str, object],
) -> dict[str, object] | None:
    """Fail before evidence writes when a unit is terminal or inconsistent."""

    with _connect(control_path, readonly=True) as connection:
        unit = connection.execute(
            "SELECT status FROM work_units WHERE run_id=? AND work_unit_id=?",
            (run_id, work_unit_id),
        ).fetchone()
        receipt = connection.execute(
            "SELECT receipt_id,feature_rows,outcome_rows,case_set_digest,"
            "feature_payload_digest,outcome_payload_digest,summary_json "
            "FROM unit_receipts WHERE run_id=? AND work_unit_id=?",
            (run_id, work_unit_id),
        ).fetchone()
    if unit is None:
        raise DevelopmentV6StoreError("Unknown work unit.")
    status = str(unit[0])
    if status in {"SKIPPED", "FAILED"}:
        raise DevelopmentV6StoreError(f"Cannot write evidence to {status} work unit.")
    if status != "COMPLETED":
        if receipt is not None:
            raise DevelopmentV6StoreError(
                "Non-completed work unit already has an immutable receipt."
            )
        if status not in {"RUNNING", "PENDING"}:
            raise DevelopmentV6StoreError(f"Cannot write work unit from {status}.")
        return None
    if receipt is None:
        raise DevelopmentV6StoreError("Completed work unit is missing its receipt.")

    actual_features = _evidence_rows(
        feature_path,
        table="feature_rows",
        run_id=run_id,
        work_unit_id=work_unit_id,
    )
    actual_outcomes = _evidence_rows(
        outcome_path,
        table="outcome_rows",
        run_id=run_id,
        work_unit_id=work_unit_id,
    )
    if list(expected_features) != actual_features or list(expected_outcomes) != actual_outcomes:
        raise DevelopmentV6StoreError(
            "Completed work unit payload differs; refusing any evidence write."
        )
    case_set_digest = fingerprint([row[0] for row in actual_features])
    feature_digest = fingerprint(actual_features)
    outcome_digest = fingerprint(actual_outcomes)
    receipt_basis = {
        "run_id": run_id,
        "work_unit_id": work_unit_id,
        "case_set_digest": case_set_digest,
        "feature_payload_digest": feature_digest,
        "outcome_payload_digest": outcome_digest,
        "summary": dict(summary),
    }
    expected_receipt_id = "madv6-receipt-" + fingerprint(receipt_basis)[:32]
    expected_receipt = (
        expected_receipt_id,
        len(actual_features),
        len(actual_outcomes),
        case_set_digest,
        feature_digest,
        outcome_digest,
        canonical_json(dict(summary)),
    )
    if tuple(receipt) != expected_receipt:
        raise DevelopmentV6StoreError("Existing completed-unit receipt differs.")
    return {
        "receipt_id": expected_receipt_id,
        "work_unit_id": work_unit_id,
        "feature_rows": len(actual_features),
        "outcome_rows": len(actual_outcomes),
        "case_set_digest": case_set_digest,
        "feature_payload_digest": feature_digest,
        "outcome_payload_digest": outcome_digest,
    }


def persist_and_complete_work_unit(
    *,
    writer_pid: int,
    run_id: str,
    unit: Mapping[str, object],
    features: Sequence[Mapping[str, object]],
    outcomes: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    feature_path: Path,
    outcome_path: Path,
    control_path: Path,
) -> dict[str, object]:
    if os.getpid() != int(writer_pid):
        raise DevelopmentV6StoreError("Only the registered main writer may write evidence.")
    work_unit_id = str(unit["work_unit_id"])
    expected_features, expected_outcomes = _expected_evidence(features, outcomes)
    completed = _completed_receipt_if_exact(
        control_path=control_path,
        feature_path=feature_path,
        outcome_path=outcome_path,
        run_id=run_id,
        work_unit_id=work_unit_id,
        expected_features=expected_features,
        expected_outcomes=expected_outcomes,
        summary=summary,
    )
    if completed is not None:
        return completed
    _insert_features(
        path=feature_path,
        run_id=run_id,
        work_unit_id=work_unit_id,
        features=features,
    )
    _insert_outcomes(
        path=outcome_path,
        run_id=run_id,
        work_unit_id=work_unit_id,
        outcomes=outcomes,
    )
    actual_features = _evidence_rows(
        feature_path,
        table="feature_rows",
        run_id=run_id,
        work_unit_id=work_unit_id,
    )
    actual_outcomes = _evidence_rows(
        outcome_path,
        table="outcome_rows",
        run_id=run_id,
        work_unit_id=work_unit_id,
    )
    if actual_features != expected_features or actual_outcomes != expected_outcomes:
        raise DevelopmentV6StoreError("Cross-store reconciliation failed after write.")
    case_set_digest = fingerprint([row[0] for row in actual_features])
    feature_digest = fingerprint(actual_features)
    outcome_digest = fingerprint(actual_outcomes)
    completed_at = utc_now()
    receipt_basis = {
        "run_id": run_id,
        "work_unit_id": work_unit_id,
        "case_set_digest": case_set_digest,
        "feature_payload_digest": feature_digest,
        "outcome_payload_digest": outcome_digest,
        "summary": dict(summary),
    }
    receipt_id = "madv6-receipt-" + fingerprint(receipt_basis)[:32]
    receipt_row = (
        receipt_id,
        run_id,
        work_unit_id,
        len(actual_features),
        len(actual_outcomes),
        case_set_digest,
        feature_digest,
        outcome_digest,
        int(writer_pid),
        completed_at,
        canonical_json(dict(summary)),
    )
    with _connect(control_path) as connection:
        existing = connection.execute(
            "SELECT receipt_id,feature_rows,outcome_rows,case_set_digest,"
            "feature_payload_digest,outcome_payload_digest,summary_json "
            "FROM unit_receipts WHERE work_unit_id=?",
            (work_unit_id,),
        ).fetchone()
        if existing is not None:
            comparable = (
                receipt_id,
                len(actual_features),
                len(actual_outcomes),
                case_set_digest,
                feature_digest,
                outcome_digest,
                canonical_json(dict(summary)),
            )
            if tuple(existing) != comparable:
                raise DevelopmentV6StoreError("Existing unit receipt differs.")
        else:
            connection.execute(
                "INSERT INTO unit_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)", receipt_row
            )
        status = connection.execute(
            "SELECT status FROM work_units WHERE work_unit_id=?", (work_unit_id,)
        ).fetchone()
        if status is None:
            raise DevelopmentV6StoreError("Unknown work unit.")
        if str(status[0]) not in {"RUNNING", "PENDING", "COMPLETED"}:
            raise DevelopmentV6StoreError(
                f"Cannot complete work unit from {status[0]}."
            )
        if str(status[0]) != "COMPLETED":
            connection.execute(
                "UPDATE work_units SET status='COMPLETED',feature_rows=?,outcome_rows=?,"
                "r_na_cases=?,censored_cases=?,missing_reference_entry=?,"
                "missingness_exclusions=?,completed_at=? WHERE work_unit_id=?",
                (
                    len(actual_features),
                    len(actual_outcomes),
                    int(summary.get("r_na_cases") or 0),
                    int(summary.get("censored_cases") or 0),
                    int(summary.get("missing_reference_entry") or 0),
                    int(summary.get("missingness_exclusions") or 0),
                    completed_at,
                    work_unit_id,
                ),
            )
            connection.execute(
                "UPDATE runs SET last_checkpoint_at=? WHERE run_id=?",
                (completed_at, run_id),
            )
    return {
        "receipt_id": receipt_id,
        "work_unit_id": work_unit_id,
        "feature_rows": len(actual_features),
        "outcome_rows": len(actual_outcomes),
        "case_set_digest": case_set_digest,
        "feature_payload_digest": feature_digest,
        "outcome_payload_digest": outcome_digest,
    }


def skip_work_unit(
    *,
    writer_pid: int,
    run_id: str,
    unit: Mapping[str, object],
    reason_code: str,
    reason: str,
    feature_path: Path,
    outcome_path: Path,
    control_path: Path,
) -> None:
    if os.getpid() != int(writer_pid):
        raise DevelopmentV6StoreError("Only the registered main writer may skip units.")
    work_unit_id = str(unit["work_unit_id"])
    if _evidence_rows(feature_path, table="feature_rows", run_id=run_id, work_unit_id=work_unit_id):
        raise DevelopmentV6StoreError("Cannot skip unit containing feature evidence.")
    if _evidence_rows(outcome_path, table="outcome_rows", run_id=run_id, work_unit_id=work_unit_id):
        raise DevelopmentV6StoreError("Cannot skip unit containing outcome evidence.")
    summary = {"skip_reason_code": reason_code, "skip_reason": reason[:1000]}
    basis = {"run_id": run_id, "work_unit_id": work_unit_id, "summary": summary}
    receipt_id = "madv6-receipt-" + fingerprint(basis)[:32]
    completed_at = utc_now()
    empty_digest = fingerprint([])
    with _connect(control_path) as connection:
        row = connection.execute(
            "SELECT summary_json FROM unit_receipts WHERE work_unit_id=?", (work_unit_id,)
        ).fetchone()
        if row is not None and str(row[0]) != canonical_json(summary):
            raise DevelopmentV6StoreError("Existing skip receipt differs.")
        if row is None:
            connection.execute(
                "INSERT INTO unit_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    receipt_id,
                    run_id,
                    work_unit_id,
                    0,
                    0,
                    empty_digest,
                    empty_digest,
                    empty_digest,
                    int(writer_pid),
                    completed_at,
                    canonical_json(summary),
                ),
            )
        current = connection.execute(
            "SELECT status FROM work_units WHERE work_unit_id=?", (work_unit_id,)
        ).fetchone()
        if current is None:
            raise DevelopmentV6StoreError("Unknown work unit.")
        if str(current[0]) != "SKIPPED":
            if str(current[0]) not in {"RUNNING", "PENDING"}:
                raise DevelopmentV6StoreError(f"Cannot skip unit from {current[0]}.")
            connection.execute(
                "UPDATE work_units SET status='SKIPPED',completed_at=?,"
                "last_error_class=?,last_error_message=? WHERE work_unit_id=?",
                (completed_at, reason_code, reason[:1000], work_unit_id),
            )
            connection.execute(
                "UPDATE runs SET last_checkpoint_at=? WHERE run_id=?",
                (completed_at, run_id),
            )


def fail_asset_batch(
    *,
    control_path: Path,
    run_id: str,
    units: Sequence[Mapping[str, object]],
    error: BaseException,
    maximum_attempts: int,
    retryable: bool,
) -> str:
    """Classify only the still-active remainder of an asset batch.

    Evidence is committed one work unit at a time.  A writer-side failure can
    therefore happen after an earlier quarter in the same asset batch already
    received its immutable completion receipt.  Completed/skipped units must
    never be rewritten to FAILED (and the terminal-status trigger deliberately
    prevents that).  Querying the control store here also makes the retry
    decision use the authoritative attempt counters rather than a stale batch
    payload.
    """

    unit_ids = [str(unit["work_unit_id"]) for unit in units]
    if not unit_ids:
        raise DevelopmentV6StoreError("Cannot fail an empty asset batch.")
    now = utc_now()
    with _connect(control_path) as connection:
        placeholders = ",".join("?" for _ in unit_ids)
        rows = connection.execute(
            "SELECT work_unit_id,status,attempts FROM work_units "
            f"WHERE run_id=? AND work_unit_id IN ({placeholders})",
            (run_id, *unit_ids),
        ).fetchall()
        if len(rows) != len(set(unit_ids)):
            raise DevelopmentV6StoreError("Asset batch contains an unknown work unit.")
        active = [row for row in rows if str(row[1]) in {"RUNNING", "PENDING"}]
        if not active:
            return (
                "FAILED_SYSTEMATIC"
                if any(str(row[1]) == "FAILED" for row in rows)
                else "ALREADY_TERMINAL"
            )
        retry = bool(retryable) and all(
            int(row[2]) < maximum_attempts for row in active
        )
        status = "PENDING" if retry else "FAILED"
        connection.executemany(
            "UPDATE work_units SET status=?,last_error_class=?,last_error_message=? "
            "WHERE run_id=? AND work_unit_id=? AND status IN ('RUNNING','PENDING')",
            [
                (
                    status,
                    type(error).__name__,
                    str(error)[:1000],
                    run_id,
                    str(row[0]),
                )
                for row in active
            ],
        )
        connection.execute(
            "UPDATE runs SET last_checkpoint_at=? WHERE run_id=?", (now, run_id)
        )
    return "RETRY" if retry else "FAILED_SYSTEMATIC"


def pause_run_for_review(*, control_path: Path, run_id: str, reason: str) -> None:
    """Freeze a run only after all already-dispatched worker results are drained."""

    now = utc_now()
    with _connect(control_path) as connection:
        row = connection.execute(
            "SELECT status FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise DevelopmentV6StoreError("Run missing from control store.")
        if str(row[0]) == "PAUSED_REQUIRES_REVIEW":
            return
        if str(row[0]) != "RUNNING":
            raise DevelopmentV6StoreError(f"Cannot pause run from {row[0]}.")
        connection.execute(
            "UPDATE runs SET status='PAUSED_REQUIRES_REVIEW',pause_reason=?,"
            "last_checkpoint_at=? WHERE run_id=?",
            (reason[:1000], now, run_id),
        )


def checkpoint_status(*, control_path: Path, run_id: str) -> dict[str, object]:
    with _connect(control_path, readonly=True) as connection:
        run = connection.execute(
            "SELECT status,total_planned_work_units,started_at,completed_at,"
            "last_checkpoint_at,pause_reason,worker_count,sqlite_writer_count,code_commit "
            "FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise DevelopmentV6StoreError("Run missing from control store.")
        counts = {
            str(status): int(count)
            for status, count in connection.execute(
                "SELECT status,COUNT(*) FROM work_units WHERE run_id=? GROUP BY status",
                (run_id,),
            )
        }
        sums = connection.execute(
            "SELECT COALESCE(SUM(feature_rows),0),COALESCE(SUM(outcome_rows),0),"
            "COALESCE(SUM(r_na_cases),0),COALESCE(SUM(censored_cases),0),"
            "COALESCE(SUM(missing_reference_entry),0),"
            "COALESCE(SUM(missingness_exclusions),0),"
            "COALESCE(SUM(CASE WHEN attempts>1 THEN attempts-1 ELSE 0 END),0) "
            "FROM work_units WHERE run_id=?",
            (run_id,),
        ).fetchone()
        receipt_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM unit_receipts WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
        last_completed = connection.execute(
            "SELECT work_unit_id,completed_at FROM work_units WHERE run_id=? "
            "AND status IN ('COMPLETED','SKIPPED') AND completed_at IS NOT NULL "
            "ORDER BY completed_at DESC,work_unit_id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    terminal_units = counts.get("COMPLETED", 0) + counts.get("SKIPPED", 0)
    total = int(run[1])
    return {
        "run_id": run_id,
        "status": str(run[0]),
        "total_planned_work_units": total,
        "completed": counts.get("COMPLETED", 0),
        "skipped": counts.get("SKIPPED", 0),
        "failed": counts.get("FAILED", 0),
        "pending": counts.get("PENDING", 0),
        "active": counts.get("RUNNING", 0),
        "receipts": receipt_count,
        "progress_pct": round(100.0 * terminal_units / total, 6) if total else 0.0,
        "feature_rows": int(sums[0]),
        "outcome_rows": int(sums[1]),
        "r_na_cases": int(sums[2]),
        "censored_cases": int(sums[3]),
        "missing_reference_entry": int(sums[4]),
        "missingness_exclusions": int(sums[5]),
        "retried": int(sums[6]),
        "started_at": str(run[2]),
        "completed_at": run[3],
        "last_checkpoint_at": str(run[4]),
        "last_completed_work_unit": last_completed[0] if last_completed else None,
        "last_work_unit_completed_at": last_completed[1] if last_completed else None,
        "pause_reason": run[5],
        "worker_count": int(run[6]),
        "sqlite_writer_count": int(run[7]),
        "code_commit": str(run[8]),
    }


def mark_run_complete(*, control_path: Path, run_id: str) -> bool:
    status = checkpoint_status(control_path=control_path, run_id=run_id)
    if status["status"] == "COMPLETED":
        return True
    if status["status"] in TERMINAL_RUN_STATUSES:
        return False
    if status["pending"] or status["active"] or status["failed"]:
        return False
    if status["receipts"] != status["total_planned_work_units"]:
        raise DevelopmentV6StoreError("Cannot complete run without one receipt per unit.")
    completed_at = utc_now()
    with _connect(control_path) as connection:
        connection.execute(
            "UPDATE runs SET status='COMPLETED',completed_at=?,last_checkpoint_at=? "
            "WHERE run_id=? AND status='RUNNING'",
            (completed_at, completed_at, run_id),
        )
    return True


def checkpoint_sqlite(*paths: Path) -> None:
    for path in paths:
        with _connect(path) as connection:
            busy, _, _ = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        if int(busy):
            raise DevelopmentV6StoreError(f"SQLite checkpoint busy: {path.name}")
