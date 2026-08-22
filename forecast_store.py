from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator, Sequence

from forecast_measurement import build_measurement_record, verify_measurement_record
from forecast_metrics import binary_up_metrics, probability_metrics, wilson_interval


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = Path(
    os.environ.get("INVESTMENT_ASSISTANT_FORECAST_DB", PROJECT_ROOT / "runtime" / "forecasts.sqlite3")
)
FORECAST_LOGIC_VERSION = "2026.08.01-v1"
FORECAST_MODEL_ENTRY = "entry_analysis"
FORECAST_MODEL_LABELS = {
    FORECAST_MODEL_ENTRY: "Einstiegsanalyse",
    "long_term": "Long-Term-Analyse",
    "swing_trade": "Swing Trade Finder",
}
FORECAST_HORIZONS = {
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "12m": 365,
}
CURRENT_SCHEMA_VERSION = 9

MEASUREMENT_RECORD_COLUMNS = (
    "observation_cutoff_at",
    "feature_schema_version",
    "feature_snapshot_json",
    "measurement_contract_version",
    "measurement_contract_json",
    "snapshot_fingerprint",
)


SCHEMA_MIGRATIONS = {
    1: """
        CREATE TABLE IF NOT EXISTS forecast_runs (
            id INTEGER PRIMARY KEY,
            run_date TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            universe_count INTEGER NOT NULL DEFAULT 0,
            processed_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_ticker TEXT,
            logic_version TEXT NOT NULL,
            message TEXT,
            sampling_json TEXT
        );

        CREATE TABLE IF NOT EXISTS run_assets (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            status TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            error_message TEXT,
            UNIQUE(run_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES forecast_runs(id),
            run_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            region TEXT NOT NULL,
            category TEXT NOT NULL,
            price_original REAL,
            original_currency TEXT,
            fx_rate_to_eur REAL,
            price_eur REAL,
            asset_quality REAL,
            buy_signal REAL,
            market_phase TEXT,
            predicted_direction TEXT NOT NULL,
            confidence REAL,
            data_quality REAL,
            data_quality_label TEXT,
            data_coverage TEXT,
            uncertainties_json TEXT NOT NULL,
            scenarios_json TEXT NOT NULL,
            professional_decision_json TEXT NOT NULL,
            signal_snapshot_json TEXT NOT NULL,
            module_scores_json TEXT NOT NULL,
            model_type TEXT NOT NULL DEFAULT 'entry_analysis',
            logic_version TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'daily-background',
            observation_cutoff_at TEXT,
            feature_schema_version TEXT,
            feature_snapshot_json TEXT,
            measurement_contract_version TEXT,
            measurement_contract_json TEXT,
            snapshot_fingerprint TEXT,
            UNIQUE(run_date, ticker, logic_version)
        );

        CREATE TABLE IF NOT EXISTS forecast_horizons (
            id INTEGER PRIMARY KEY,
            forecast_id INTEGER NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
            horizon TEXT NOT NULL,
            days INTEGER NOT NULL,
            expected_direction TEXT NOT NULL,
            expected_low_eur REAL,
            expected_high_eur REAL,
            target_eur REAL,
            risk_eur REAL,
            probability_up REAL,
            probability_schema_version TEXT,
            UNIQUE(forecast_id, horizon)
        );

        CREATE TABLE IF NOT EXISTS forecast_evaluations (
            id INTEGER PRIMARY KEY,
            forecast_id INTEGER NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
            horizon TEXT NOT NULL,
            evaluated_at TEXT NOT NULL,
            actual_price_original REAL,
            actual_price_eur REAL,
            actual_return_pct REAL,
            actual_day TEXT,
            max_return_pct REAL,
            min_return_pct REAL,
            always_up_hit INTEGER,
            no_change_hit INTEGER,
            simple_trend_hit INTEGER,
            market_benchmark_ticker TEXT,
            market_benchmark_return_pct REAL,
            excess_return_pct REAL,
            direction_hit INTEGER,
            range_hit INTEGER,
            deviation_pct REAL,
            target_hit INTEGER,
            risk_hit INTEGER,
            data_quality TEXT NOT NULL,
            note TEXT,
            UNIQUE(forecast_id, horizon)
        );

        CREATE INDEX IF NOT EXISTS idx_forecasts_created_at ON forecasts(created_at);
        CREATE INDEX IF NOT EXISTS idx_forecasts_ticker ON forecasts(ticker);
        CREATE INDEX IF NOT EXISTS idx_forecasts_asset_type ON forecasts(asset_type);
        CREATE INDEX IF NOT EXISTS idx_forecasts_model_type ON forecasts(model_type);
        CREATE INDEX IF NOT EXISTS idx_horizons_due ON forecast_horizons(days, horizon);
        CREATE INDEX IF NOT EXISTS idx_evaluations_result ON forecast_evaluations(direction_hit, horizon);
    """,
    2: """
        CREATE TABLE IF NOT EXISTS forecast_evaluation_attempts (
            forecast_id INTEGER NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
            horizon TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            status TEXT NOT NULL,
            error_kind TEXT,
            message TEXT,
            PRIMARY KEY (forecast_id, horizon)
        );

        CREATE INDEX IF NOT EXISTS idx_evaluation_attempts_status
            ON forecast_evaluation_attempts(status, error_kind);
    """,
    3: """
        -- Run metric columns are added idempotently by initialize_database.
    """,
    4: """
        -- The model type column is added idempotently by initialize_database.
    """,
    5: """
        -- Point-in-time measurement columns are added idempotently by initialize_database.
    """,
    6: """
        -- Weekly cohort metadata is added idempotently by initialize_database.
    """,
    7: """
        -- Rich forward outcomes and simple benchmark labels are added idempotently.
    """,
    8: """
        -- Point-in-time trend and market benchmark outcomes are added idempotently.
    """,
    9: """
        -- Explicit uncalibrated probability forecasts are added per horizon.
    """,
}

RUN_METRIC_COLUMNS = {
    "elapsed_seconds": "REAL",
    "processed_per_minute": "REAL",
    "failure_rate_pct": "REAL",
    "rate_limit_failures": "INTEGER NOT NULL DEFAULT 0",
    "database_bytes_before": "INTEGER",
    "database_bytes_after": "INTEGER",
    "database_growth_bytes": "INTEGER",
    "database_status": "TEXT",
}

MEASUREMENT_COLUMNS = {
    "observation_cutoff_at": "TEXT",
    "feature_schema_version": "TEXT",
    "feature_snapshot_json": "TEXT",
    "measurement_contract_version": "TEXT",
    "measurement_contract_json": "TEXT",
    "snapshot_fingerprint": "TEXT",
}

EVALUATION_OUTCOME_COLUMNS = {
    "actual_day": "TEXT",
    "max_return_pct": "REAL",
    "min_return_pct": "REAL",
    "always_up_hit": "INTEGER",
    "no_change_hit": "INTEGER",
}

EVALUATION_BASELINE_COLUMNS = {
    "simple_trend_hit": "INTEGER",
    "market_benchmark_ticker": "TEXT",
    "market_benchmark_return_pct": "REAL",
    "excess_return_pct": "REAL",
}

HORIZON_PROBABILITY_COLUMNS = {
    "probability_up": "REAL",
    "probability_schema_version": "TEXT",
}


def forecast_model_label(model_type: object) -> str:
    key = str(model_type or FORECAST_MODEL_ENTRY)
    return FORECAST_MODEL_LABELS.get(key, key.replace("_", " ").strip().title())


@dataclass(frozen=True)
class RunStart:
    run_id: int
    should_run: bool
    resumed: bool
    existing_status: str | None = None


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


@contextmanager
def database(path: Path = DEFAULT_DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path = DEFAULT_DATABASE_PATH) -> None:
    with database(path) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                "Die Prognose-Datenbank stammt aus einer neueren App-Version "
                f"(Schema {version}, unterstützt bis {CURRENT_SCHEMA_VERSION})."
            )
        for target_version in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
            migration = SCHEMA_MIGRATIONS.get(target_version)
            if not migration:
                raise RuntimeError(f"Fehlende Datenbankmigration für Schema {target_version}.")
            if target_version == 3:
                existing_columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(forecast_runs)")
                }
                for column, definition in RUN_METRIC_COLUMNS.items():
                    if column not in existing_columns:
                        connection.execute(
                            f"ALTER TABLE forecast_runs ADD COLUMN {column} {definition}"
                        )
            elif target_version == 4:
                existing_columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(forecasts)")
                }
                if "model_type" not in existing_columns:
                    connection.execute(
                        "ALTER TABLE forecasts ADD COLUMN model_type "
                        "TEXT NOT NULL DEFAULT 'entry_analysis'"
                    )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_forecasts_model_type ON forecasts(model_type)"
                )
            elif target_version == 5:
                existing_columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(forecasts)")
                }
                for column, definition in MEASUREMENT_COLUMNS.items():
                    if column not in existing_columns:
                        connection.execute(
                            f"ALTER TABLE forecasts ADD COLUMN {column} {definition}"
                        )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_forecasts_measurement_contract "
                    "ON forecasts(measurement_contract_version, feature_schema_version)"
                )
            elif target_version == 6:
                existing_columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(forecast_runs)")
                }
                if existing_columns and "sampling_json" not in existing_columns:
                    connection.execute("ALTER TABLE forecast_runs ADD COLUMN sampling_json TEXT")
            elif target_version == 7:
                existing_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(forecast_evaluations)")
                }
                for column, definition in EVALUATION_OUTCOME_COLUMNS.items():
                    if existing_columns and column not in existing_columns:
                        connection.execute(
                            f"ALTER TABLE forecast_evaluations ADD COLUMN {column} {definition}"
                        )
            elif target_version == 8:
                existing_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(forecast_evaluations)")
                }
                for column, definition in EVALUATION_BASELINE_COLUMNS.items():
                    if existing_columns and column not in existing_columns:
                        connection.execute(
                            f"ALTER TABLE forecast_evaluations ADD COLUMN {column} {definition}"
                        )
            elif target_version == 9:
                existing_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(forecast_horizons)")
                }
                for column, definition in HORIZON_PROBABILITY_COLUMNS.items():
                    if existing_columns and column not in existing_columns:
                        connection.execute(
                            f"ALTER TABLE forecast_horizons ADD COLUMN {column} {definition}"
                        )
            else:
                connection.executescript(migration)
            connection.execute(f"PRAGMA user_version = {target_version}")


def database_health(path: Path = DEFAULT_DATABASE_PATH) -> dict:
    """Return non-destructive database health and growth information."""
    initialize_database(path)
    with database(path) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        freelist_count = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
        forecast_count = int(connection.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0])
        evaluation_count = int(
            connection.execute("SELECT COUNT(*) FROM forecast_evaluations").fetchone()[0]
        )
        measurement_audit = _measurement_contract_audit(connection)
    database_path = Path(path)
    wal_path = Path(f"{database_path}-wal")
    return {
        "status": (
            "ok"
            if quick_check.lower() == "ok" and measurement_audit["status"] == "ok"
            else "attention"
        ),
        "quick_check": quick_check,
        "schema_version": schema_version,
        "current_schema_version": CURRENT_SCHEMA_VERSION,
        "database_bytes": database_path.stat().st_size if database_path.exists() else 0,
        "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        "allocated_bytes": page_size * page_count,
        "reclaimable_bytes": page_size * freelist_count,
        "forecast_count": forecast_count,
        "evaluation_count": evaluation_count,
        "measurement_contract_count": measurement_audit["valid_records"],
        "legacy_without_measurement_contract": measurement_audit["legacy_records"],
        "measurement_contract_audit": measurement_audit,
    }


def _measurement_contract_audit(connection: sqlite3.Connection) -> dict:
    columns = ", ".join(("id", "ticker", *MEASUREMENT_RECORD_COLUMNS))
    rows = connection.execute(f"SELECT {columns} FROM forecasts ORDER BY id").fetchall()
    valid_records = 0
    legacy_records = 0
    invalid_records = 0
    reason_counts: dict[str, int] = {}
    invalid_examples: list[dict] = []
    for row in rows:
        record = dict(row)
        values = [record.get(column) for column in MEASUREMENT_RECORD_COLUMNS]
        if all(value is None for value in values):
            legacy_records += 1
            continue
        valid, reasons = verify_measurement_record(record)
        if valid:
            valid_records += 1
            continue
        invalid_records += 1
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if len(invalid_examples) < 10:
            invalid_examples.append(
                {
                    "forecast_id": int(record["id"]),
                    "ticker": str(record["ticker"]),
                    "reasons": reasons,
                }
            )
    return {
        "status": "ok" if invalid_records == 0 else "attention",
        "total_records": len(rows),
        "valid_records": valid_records,
        "invalid_records": invalid_records,
        "legacy_records": legacy_records,
        "reason_counts": reason_counts,
        "invalid_examples": invalid_examples,
    }


def measurement_contract_audit(path: Path = DEFAULT_DATABASE_PATH) -> dict:
    """Verify every non-legacy point-in-time record without changing stored forecasts."""
    initialize_database(path)
    with database(path) as connection:
        return _measurement_contract_audit(connection)


def maintain_database(path: Path = DEFAULT_DATABASE_PATH, compact: bool = False) -> dict:
    """Optimize/checkpoint SQLite; compact only when explicitly requested."""
    initialize_database(path)
    with database(path) as connection:
        connection.execute("PRAGMA optimize")
        checkpoint = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        checkpoint_result = {
            "busy": int(checkpoint[0]),
            "wal_pages": int(checkpoint[1]),
            "checkpointed_pages": int(checkpoint[2]),
        }
        if compact:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.commit()
            connection.execute("VACUUM")
    return {
        **database_health(path),
        "compacted": bool(compact),
        "checkpoint": checkpoint_result,
        "data_deleted": False,
    }


def start_or_resume_run(
    run_date: str,
    universe_count: int,
    path: Path = DEFAULT_DATABASE_PATH,
    logic_version: str = FORECAST_LOGIC_VERSION,
    force: bool = False,
    sampling: dict | None = None,
) -> RunStart:
    initialize_database(path)
    now = datetime.now().astimezone().isoformat()
    with database(path) as connection:
        connection.execute(
            """
            UPDATE forecast_runs
            SET status = 'interrupted', finished_at = ?,
                message = 'Älterer nicht abgeschlossener Lauf automatisch als unterbrochen markiert.'
            WHERE status = 'running' AND run_date < ?
            """,
            (now, run_date),
        )
        existing = connection.execute(
            "SELECT id, status, logic_version, sampling_json "
            "FROM forecast_runs WHERE run_date = ?",
            (run_date,),
        ).fetchone()
        if existing:
            existing_status = str(existing["status"])
            existing_logic_version = str(existing["logic_version"])
            if existing_logic_version != logic_version:
                raise RuntimeError(
                    "Ein Tageslauf mit einer anderen Logikversion ist bereits vorhanden "
                    f"({existing_logic_version} statt {logic_version}). "
                    "Versionen werden aus Gründen der Datenintegrität nicht in einem Lauf vermischt."
                )
            try:
                existing_sampling = (
                    json.loads(str(existing["sampling_json"]))
                    if existing["sampling_json"]
                    else None
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("Die gespeicherte Wochenkohorte des Tageslaufs ist beschädigt.") from exc
            if existing_sampling is not None and sampling is not None and existing_sampling != sampling:
                raise RuntimeError(
                    "Der Tageslauf besitzt bereits eine andere Wochenkohorte; "
                    "Kohorten werden nicht still vermischt."
                )
            if existing_status in {"completed", "completed_with_errors"}:
                return RunStart(int(existing["id"]), False, False, existing_status)
            connection.execute(
                """
                UPDATE forecast_runs
                SET status = 'running', finished_at = NULL, universe_count = ?,
                    logic_version = ?, message = ?, sampling_json = COALESCE(sampling_json, ?)
                WHERE id = ?
                """,
                (
                    universe_count,
                    logic_version,
                    "Fortgesetzter Lauf",
                    _json(sampling) if sampling is not None else None,
                    int(existing["id"]),
                ),
            )
            return RunStart(int(existing["id"]), True, True, existing_status)

        cursor = connection.execute(
            """
            INSERT INTO forecast_runs
                (run_date, status, started_at, universe_count, logic_version, message, sampling_json)
            VALUES (?, 'running', ?, ?, ?, ?, ?)
            """,
            (
                run_date,
                now,
                universe_count,
                logic_version,
                "Neuer täglicher Lauf",
                _json(sampling) if sampling is not None else None,
            ),
        )
        return RunStart(int(cursor.lastrowid), True, False, None)


def completed_sampling_cohort_ids(
    iso_week: str,
    path: Path = DEFAULT_DATABASE_PATH,
) -> set[str]:
    if not Path(path).exists():
        return set()
    initialize_database(path)
    with database(path) as connection:
        rows = connection.execute(
            "SELECT sampling_json FROM forecast_runs "
            "WHERE status IN ('completed', 'completed_with_errors') "
            "AND sampling_json IS NOT NULL"
        ).fetchall()
    completed: set[str] = set()
    for row in rows:
        try:
            sampling = json.loads(str(row["sampling_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if sampling.get("iso_week") == iso_week and sampling.get("cohort_id"):
            completed.add(str(sampling["cohort_id"]))
    return completed


def sampling_for_run_date(
    run_date: str,
    path: Path = DEFAULT_DATABASE_PATH,
) -> dict | None:
    if not Path(path).exists():
        return None
    initialize_database(path)
    with database(path) as connection:
        row = connection.execute(
            "SELECT sampling_json FROM forecast_runs WHERE run_date = ?",
            (run_date,),
        ).fetchone()
    if row is None or not row["sampling_json"]:
        return None
    try:
        value = json.loads(str(row["sampling_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Die gespeicherte Wochenkohorte des Tageslaufs ist beschädigt.") from exc
    return value if isinstance(value, dict) else None


def latest_horizon_start_dates(
    ticker: str,
    path: Path = DEFAULT_DATABASE_PATH,
    *,
    model_type: str = FORECAST_MODEL_ENTRY,
) -> dict[str, date]:
    if not Path(path).exists():
        return {}
    with database(path) as connection:
        rows = connection.execute(
            """
            SELECT h.horizon, MAX(f.run_date) AS latest_run_date
            FROM forecast_horizons h
            JOIN forecasts f ON f.id = h.forecast_id
            WHERE f.ticker = ? AND f.model_type = ?
            GROUP BY h.horizon
            """,
            (str(ticker).upper(), str(model_type)),
        ).fetchall()
    result: dict[str, date] = {}
    for row in rows:
        try:
            result[str(row["horizon"])] = date.fromisoformat(str(row["latest_run_date"]))
        except (TypeError, ValueError):
            continue
    return result


def successful_tickers(run_id: int, path: Path = DEFAULT_DATABASE_PATH) -> set[str]:
    if not Path(path).exists():
        return set()
    with database(path) as connection:
        rows = connection.execute(
            "SELECT ticker FROM run_assets WHERE run_id = ? AND status = 'success'", (run_id,)
        ).fetchall()
    return {str(row["ticker"]).upper() for row in rows}


def _update_run_counts(connection: sqlite3.Connection, run_id: int, ticker: str) -> None:
    counts = connection.execute(
        """
        SELECT COUNT(*) AS processed,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS succeeded,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
        FROM run_assets WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    connection.execute(
        """
        UPDATE forecast_runs
        SET processed_count = ?, success_count = ?, failure_count = ?, last_ticker = ?
        WHERE id = ?
        """,
        (
            int(counts["processed"] or 0),
            int(counts["succeeded"] or 0),
            int(counts["failed"] or 0),
            ticker,
            run_id,
        ),
    )


def record_forecast(
    run_id: int,
    snapshot: dict,
    path: Path = DEFAULT_DATABASE_PATH,
) -> tuple[int, bool]:
    initialize_database(path)
    ticker = str(snapshot["ticker"]).upper()
    measurement = build_measurement_record(snapshot)
    with database(path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO forecasts (
                run_id, run_date, created_at, ticker, asset_name, asset_type, region, category,
                price_original, original_currency, fx_rate_to_eur, price_eur,
                asset_quality, buy_signal, market_phase, predicted_direction,
                confidence, data_quality, data_quality_label, data_coverage,
                uncertainties_json, scenarios_json, professional_decision_json,
                signal_snapshot_json, module_scores_json, model_type, logic_version, source,
                observation_cutoff_at, feature_schema_version, feature_snapshot_json,
                measurement_contract_version, measurement_contract_json, snapshot_fingerprint
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                run_id,
                snapshot["run_date"],
                snapshot["created_at"],
                ticker,
                snapshot.get("asset_name") or ticker,
                snapshot.get("asset_type") or "Unbekannt",
                snapshot.get("region") or "Unbekannt",
                snapshot.get("category") or "Unbekannt",
                snapshot.get("price_original"),
                snapshot.get("original_currency"),
                snapshot.get("fx_rate_to_eur"),
                snapshot.get("price_eur"),
                snapshot.get("asset_quality"),
                snapshot.get("buy_signal"),
                snapshot.get("market_phase"),
                snapshot["predicted_direction"],
                snapshot.get("confidence"),
                snapshot.get("data_quality"),
                snapshot.get("data_quality_label"),
                snapshot.get("data_coverage"),
                _json(snapshot.get("uncertainties", [])),
                _json(snapshot.get("scenarios", [])),
                _json(snapshot.get("professional_decision", {})),
                _json(snapshot.get("signal_snapshot", {})),
                _json(snapshot.get("module_scores", [])),
                snapshot.get("model_type") or FORECAST_MODEL_ENTRY,
                snapshot.get("logic_version") or FORECAST_LOGIC_VERSION,
                snapshot.get("source") or "daily-background",
                measurement["observation_cutoff_at"],
                measurement["feature_schema_version"],
                measurement["feature_snapshot_json"],
                measurement["measurement_contract_version"],
                measurement["measurement_contract_json"],
                measurement["snapshot_fingerprint"],
            ),
        )
        inserted = cursor.rowcount > 0
        row = connection.execute(
            "SELECT id FROM forecasts "
            "WHERE run_date = ? AND ticker = ? AND model_type = ? AND logic_version = ?",
            (
                snapshot["run_date"],
                ticker,
                snapshot.get("model_type") or FORECAST_MODEL_ENTRY,
                snapshot.get("logic_version") or FORECAST_LOGIC_VERSION,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError(
                "Prognose konnte nicht eindeutig nach Modellart und Logikversion gespeichert werden."
            )
        forecast_id = int(row["id"])
        for horizon in snapshot.get("horizons", []):
            connection.execute(
                """
                INSERT OR IGNORE INTO forecast_horizons (
                    forecast_id, horizon, days, expected_direction,
                    expected_low_eur, expected_high_eur, target_eur, risk_eur,
                    probability_up, probability_schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    forecast_id,
                    horizon["horizon"],
                    int(horizon["days"]),
                    horizon["expected_direction"],
                    horizon.get("expected_low_eur"),
                    horizon.get("expected_high_eur"),
                    horizon.get("target_eur"),
                    horizon.get("risk_eur"),
                    horizon.get("probability_up"),
                    horizon.get("probability_schema_version"),
                ),
            )
        connection.execute(
            """
            INSERT INTO run_assets (run_id, ticker, status, attempted_at, error_message)
            VALUES (?, ?, 'success', ?, NULL)
            ON CONFLICT(run_id, ticker) DO UPDATE SET
                status = 'success', attempted_at = excluded.attempted_at, error_message = NULL
            """,
            (run_id, ticker, datetime.now().astimezone().isoformat()),
        )
        _update_run_counts(connection, run_id, ticker)
    return forecast_id, inserted


def record_asset_failure(
    run_id: int,
    ticker: str,
    error_message: str,
    path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    safe_error = " ".join(str(error_message).split())[:1000]
    with database(path) as connection:
        connection.execute(
            """
            INSERT INTO run_assets (run_id, ticker, status, attempted_at, error_message)
            VALUES (?, ?, 'failed', ?, ?)
            ON CONFLICT(run_id, ticker) DO UPDATE SET
                status = 'failed', attempted_at = excluded.attempted_at,
                error_message = excluded.error_message
            """,
            (run_id, ticker.upper(), datetime.now().astimezone().isoformat(), safe_error),
        )
        _update_run_counts(connection, run_id, ticker.upper())


def finish_run(
    run_id: int,
    path: Path = DEFAULT_DATABASE_PATH,
    message: str | None = None,
) -> str:
    with database(path) as connection:
        row = connection.execute(
            "SELECT failure_count FROM forecast_runs WHERE id = ?", (run_id,)
        ).fetchone()
        status = "completed_with_errors" if row and int(row["failure_count"] or 0) else "completed"
        connection.execute(
            "UPDATE forecast_runs SET status = ?, finished_at = ?, message = ? WHERE id = ?",
            (status, datetime.now().astimezone().isoformat(), message, run_id),
        )
    return status


def interrupt_run(
    run_id: int,
    message: str,
    path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    with database(path) as connection:
        connection.execute(
            "UPDATE forecast_runs SET status = 'interrupted', finished_at = ?, message = ? WHERE id = ?",
            (datetime.now().astimezone().isoformat(), " ".join(message.split())[:1000], run_id),
        )


def record_run_operations(
    run_id: int,
    operations: dict,
    path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    initialize_database(path)
    with database(path) as connection:
        connection.execute(
            """
            UPDATE forecast_runs
            SET elapsed_seconds = ?, processed_per_minute = ?, failure_rate_pct = ?,
                rate_limit_failures = ?, database_bytes_before = ?, database_bytes_after = ?,
                database_growth_bytes = ?, database_status = ?
            WHERE id = ?
            """,
            (
                operations.get("elapsed_seconds"),
                operations.get("processed_per_minute"),
                operations.get("failure_rate_pct"),
                int(operations.get("rate_limit_failures") or 0),
                operations.get("database_bytes_before"),
                operations.get("database_bytes_after"),
                operations.get("database_growth_bytes"),
                operations.get("database_status"),
                int(run_id),
            ),
        )


def pending_evaluations(
    as_of: date | None = None,
    path: Path = DEFAULT_DATABASE_PATH,
    limit: int = 1000,
) -> list[dict]:
    if not Path(path).exists():
        return []
    as_of = as_of or date.today()
    with database(path) as connection:
        rows = connection.execute(
            """
            SELECT f.id AS forecast_id, f.ticker, f.created_at, f.price_original,
                   f.price_eur, f.original_currency, f.fx_rate_to_eur,
                   f.predicted_direction, f.feature_snapshot_json, h.horizon, h.days,
                   h.probability_up, h.probability_schema_version,
                   h.expected_low_eur, h.expected_high_eur, h.target_eur, h.risk_eur
            FROM forecast_horizons h
            JOIN forecasts f ON f.id = h.forecast_id
            LEFT JOIN forecast_evaluations e
                ON e.forecast_id = f.id AND e.horizon = h.horizon
            WHERE e.id IS NULL
              AND date(f.created_at, '+' || h.days || ' days') <= date(?)
            ORDER BY f.created_at, f.ticker, h.days
            LIMIT ?
            """,
            (as_of.isoformat(), int(limit)),
        ).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        try:
            features = json.loads(str(item.get("feature_snapshot_json") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            features = {}
        item["simple_trend_baseline"] = features.get("simple_trend_baseline") or {}
        item["market_benchmark_snapshot"] = features.get("market_benchmark_snapshot") or {}
        result.append(item)
    return result


def record_evaluation(
    evaluation: dict,
    path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    with database(path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO forecast_evaluations (
                forecast_id, horizon, evaluated_at, actual_price_original, actual_price_eur,
                actual_return_pct, actual_day, max_return_pct, min_return_pct,
                always_up_hit, no_change_hit, simple_trend_hit,
                market_benchmark_ticker, market_benchmark_return_pct, excess_return_pct,
                direction_hit, range_hit, deviation_pct,
                target_hit, risk_hit, data_quality, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation["forecast_id"],
                evaluation["horizon"],
                evaluation["evaluated_at"],
                evaluation.get("actual_price_original"),
                evaluation.get("actual_price_eur"),
                evaluation.get("actual_return_pct"),
                evaluation.get("actual_day"),
                evaluation.get("max_return_pct"),
                evaluation.get("min_return_pct"),
                evaluation.get("always_up_hit"),
                evaluation.get("no_change_hit"),
                evaluation.get("simple_trend_hit"),
                evaluation.get("market_benchmark_ticker"),
                evaluation.get("market_benchmark_return_pct"),
                evaluation.get("excess_return_pct"),
                evaluation.get("direction_hit"),
                evaluation.get("range_hit"),
                evaluation.get("deviation_pct"),
                evaluation.get("target_hit"),
                evaluation.get("risk_hit"),
                evaluation.get("data_quality") or "Unbekannt",
                evaluation.get("note"),
            ),
        )
        connection.execute(
            "DELETE FROM forecast_evaluation_attempts WHERE forecast_id = ? AND horizon = ?",
            (evaluation["forecast_id"], evaluation["horizon"]),
        )
    return cursor.rowcount > 0


def record_evaluation_failure(
    forecast_id: int,
    horizon: str,
    message: str,
    path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Persist the latest failed due-evaluation attempt without storing market or user data."""
    initialize_database(path)
    normalized = " ".join(str(message).split())[:500]
    lowered = normalized.lower()
    error_kind = (
        "market_data"
        if any(marker in lowered for marker in ["kursdaten", "marktdaten", "handelsschlusskurs", "actual price"])
        else "technical"
    )
    with database(path) as connection:
        connection.execute(
            """
            INSERT INTO forecast_evaluation_attempts
                (forecast_id, horizon, attempted_at, status, error_kind, message)
            VALUES (?, ?, ?, 'failed', ?, ?)
            ON CONFLICT(forecast_id, horizon) DO UPDATE SET
                attempted_at = excluded.attempted_at,
                status = excluded.status,
                error_kind = excluded.error_kind,
                message = excluded.message
            """,
            (
                int(forecast_id),
                str(horizon),
                datetime.now().astimezone().isoformat(),
                error_kind,
                normalized,
            ),
        )


def forecast_summary(path: Path = DEFAULT_DATABASE_PATH) -> dict:
    empty = {
        "hit_rate": None,
        "evaluated": 0,
        "open": 0,
        "due": 0,
        "missing_market_data": 0,
        "next_due_date": None,
        "average_deviation_pct": None,
        "outcome_count": 0,
        "evaluation_coverage_pct": None,
        "metric_coverage_pct": None,
        "average_return_pct": None,
        "average_max_return_pct": None,
        "average_drawdown_pct": None,
        "always_up_hit_rate": None,
        "no_change_hit_rate": None,
        "simple_trend_hit_rate": None,
        "model_advantage_vs_simple_trend_pct": None,
        "average_market_benchmark_return_pct": None,
        "average_excess_return_pct": None,
        "model_advantage_vs_always_up_pct": None,
        "hit_rate_ci_low_pct": None,
        "hit_rate_ci_high_pct": None,
        "up_precision_pct": None,
        "up_recall_pct": None,
        "up_specificity_pct": None,
        "balanced_accuracy_pct": None,
        "probability_evaluated": 0,
        "brier_score": None,
        "log_loss": None,
        "calibration_error_pct": None,
        "calibration_bias_pct": None,
        "confusion": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "by_horizon": [],
        "by_asset_type": [],
        "by_model": [],
        "by_region": [],
        "by_market_phase": [],
        "by_data_quality": [],
        "by_logic_version": [],
        "evaluated_model_count": 0,
        "mixed_models": False,
    }
    if not Path(path).exists():
        return empty
    try:
        initialize_database(path)
        with database(path) as connection:
            today = date.today().isoformat()
            totals = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN e.direction_hit IS NOT NULL THEN 1 ELSE 0 END) AS evaluated,
                    SUM(CASE WHEN e.id IS NOT NULL THEN 1 ELSE 0 END) AS outcome_count,
                    SUM(CASE WHEN e.direction_hit = 1 THEN 1 ELSE 0 END) AS hits,
                    SUM(CASE WHEN e.id IS NULL THEN 1 ELSE 0 END) AS open_count,
                    SUM(
                        CASE WHEN e.id IS NULL
                                  AND date(f.created_at, '+' || h.days || ' days') <= date(?)
                             THEN 1 ELSE 0 END
                    ) AS due_count,
                    MIN(
                        CASE WHEN e.id IS NULL
                                  AND date(f.created_at, '+' || h.days || ' days') > date(?)
                             THEN date(f.created_at, '+' || h.days || ' days') END
                    ) AS next_due_date,
                    AVG(ABS(e.deviation_pct)) AS average_deviation,
                    AVG(e.actual_return_pct) AS average_return,
                    AVG(e.max_return_pct) AS average_max_return,
                    AVG(e.min_return_pct) AS average_drawdown,
                    AVG(e.always_up_hit) * 100 AS always_up_hit_rate,
                    AVG(e.no_change_hit) * 100 AS no_change_hit_rate,
                    AVG(e.simple_trend_hit) * 100 AS simple_trend_hit_rate,
                    AVG(e.market_benchmark_return_pct) AS average_market_benchmark_return,
                    AVG(e.excess_return_pct) AS average_excess_return,
                    SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction = 'Steigend' AND e.actual_return_pct > 0 THEN 1 ELSE 0 END) AS up_tp,
                    SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction = 'Steigend' AND e.actual_return_pct <= 0 THEN 1 ELSE 0 END) AS up_fp,
                    SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction <> 'Steigend' AND e.actual_return_pct > 0 THEN 1 ELSE 0 END) AS up_fn,
                    SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction <> 'Steigend' AND e.actual_return_pct <= 0 THEN 1 ELSE 0 END) AS up_tn
                FROM forecast_horizons h
                JOIN forecasts f ON f.id = h.forecast_id
                LEFT JOIN forecast_evaluations e
                    ON e.forecast_id = f.id AND e.horizon = h.horizon
                """,
                (today, today),
            ).fetchone()
            evaluated = int(totals["evaluated"] or 0)
            outcome_count = int(totals["outcome_count"] or 0)
            hits = int(totals["hits"] or 0)
            attempt_table_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'forecast_evaluation_attempts'"
            ).fetchone()
            missing_market_data = 0
            if attempt_table_exists:
                missing_market_data = int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM forecast_evaluation_attempts a
                        JOIN forecasts f ON f.id = a.forecast_id
                        JOIN forecast_horizons h
                          ON h.forecast_id = a.forecast_id AND h.horizon = a.horizon
                        LEFT JOIN forecast_evaluations e
                          ON e.forecast_id = a.forecast_id AND e.horizon = a.horizon
                        WHERE e.id IS NULL
                          AND a.status = 'failed'
                          AND a.error_kind = 'market_data'
                          AND date(f.created_at, '+' || h.days || ' days') <= date(?)
                        """,
                        (today,),
                    ).fetchone()[0]
                    or 0
                )
            by_horizon = connection.execute(
                """
                SELECT h.horizon AS label,
                       SUM(CASE WHEN e.direction_hit IS NOT NULL THEN 1 ELSE 0 END) AS evaluated,
                       AVG(CASE WHEN e.direction_hit IS NOT NULL THEN e.direction_hit END) * 100 AS hit_rate
                FROM forecast_horizons h
                LEFT JOIN forecast_evaluations e
                    ON e.forecast_id = h.forecast_id AND e.horizon = h.horizon
                GROUP BY h.horizon ORDER BY h.days
                """
            ).fetchall()
            by_asset_type = connection.execute(
                """
                SELECT f.asset_type AS label,
                       SUM(CASE WHEN e.direction_hit IS NOT NULL THEN 1 ELSE 0 END) AS evaluated,
                       AVG(CASE WHEN e.direction_hit IS NOT NULL THEN e.direction_hit END) * 100 AS hit_rate
                FROM forecasts f
                JOIN forecast_horizons h ON h.forecast_id = f.id
                LEFT JOIN forecast_evaluations e
                    ON e.forecast_id = f.id AND e.horizon = h.horizon
                GROUP BY f.asset_type ORDER BY f.asset_type
                """
            ).fetchall()
            by_model = connection.execute(
                """
                SELECT COALESCE(NULLIF(f.model_type, ''), 'entry_analysis') AS label,
                       SUM(CASE WHEN e.direction_hit IS NOT NULL THEN 1 ELSE 0 END) AS evaluated,
                       SUM(CASE WHEN e.direction_hit = 1 THEN 1 ELSE 0 END) AS hits,
                       AVG(CASE WHEN e.direction_hit IS NOT NULL THEN e.direction_hit END) * 100 AS hit_rate,
                       SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction = 'Steigend' AND e.actual_return_pct > 0 THEN 1 ELSE 0 END) AS up_tp,
                       SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction = 'Steigend' AND e.actual_return_pct <= 0 THEN 1 ELSE 0 END) AS up_fp,
                       SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction <> 'Steigend' AND e.actual_return_pct > 0 THEN 1 ELSE 0 END) AS up_fn,
                       SUM(CASE WHEN e.actual_return_pct IS NOT NULL AND f.predicted_direction <> 'Steigend' AND e.actual_return_pct <= 0 THEN 1 ELSE 0 END) AS up_tn
                FROM forecasts f
                JOIN forecast_horizons h ON h.forecast_id = f.id
                LEFT JOIN forecast_evaluations e
                    ON e.forecast_id = f.id AND e.horizon = h.horizon
                GROUP BY COALESCE(NULLIF(f.model_type, ''), 'entry_analysis')
                ORDER BY label
                """
            ).fetchall()
            segment_queries = {
                "by_region": "COALESCE(NULLIF(f.region, ''), 'Unbekannt')",
                "by_market_phase": "COALESCE(NULLIF(f.market_phase, ''), 'Unbekannt')",
                "by_data_quality": "COALESCE(NULLIF(e.data_quality, ''), NULLIF(f.data_quality_label, ''), 'Unbekannt')",
                "by_logic_version": "COALESCE(NULLIF(f.logic_version, ''), 'Unbekannt')",
            }
            segment_rows = {}
            for key, expression in segment_queries.items():
                segment_rows[key] = connection.execute(
                    f"""
                    SELECT {expression} AS label,
                           SUM(CASE WHEN e.direction_hit IS NOT NULL THEN 1 ELSE 0 END) AS evaluated,
                           AVG(CASE WHEN e.direction_hit IS NOT NULL THEN e.direction_hit END) * 100 AS hit_rate,
                           AVG(e.actual_return_pct) AS average_return_pct,
                           AVG(e.excess_return_pct) AS average_excess_return_pct
                    FROM forecasts f
                    JOIN forecast_horizons h ON h.forecast_id = f.id
                    LEFT JOIN forecast_evaluations e
                      ON e.forecast_id = f.id AND e.horizon = h.horizon
                    GROUP BY {expression}
                    ORDER BY evaluated DESC, label
                    """
                ).fetchall()
            probability_rows = connection.execute(
                """
                SELECT COALESCE(NULLIF(f.model_type, ''), 'entry_analysis') AS model_type,
                       h.horizon, h.probability_up,
                       CASE WHEN e.actual_return_pct > 0 THEN 1 ELSE 0 END AS outcome_up
                FROM forecasts f
                JOIN forecast_horizons h ON h.forecast_id = f.id
                JOIN forecast_evaluations e
                  ON e.forecast_id = f.id AND e.horizon = h.horizon
                WHERE h.probability_up IS NOT NULL
                  AND e.actual_return_pct IS NOT NULL
                """
            ).fetchall()
        probability_cases = [
            (row["probability_up"], row["outcome_up"])
            for row in probability_rows
        ]
        probability_by_model: dict[str, list[tuple[float, int]]] = {}
        probability_by_horizon: dict[str, list[tuple[float, int]]] = {}
        for row in probability_rows:
            case = (row["probability_up"], row["outcome_up"])
            probability_by_model.setdefault(str(row["model_type"]), []).append(case)
            probability_by_horizon.setdefault(str(row["horizon"]), []).append(case)
        model_rows = []
        for row in by_model:
            item = dict(row)
            low, high = wilson_interval(int(item.get("hits") or 0), int(item.get("evaluated") or 0))
            item.update(
                binary_up_metrics(
                    int(item.get("up_tp") or 0),
                    int(item.get("up_fp") or 0),
                    int(item.get("up_fn") or 0),
                    int(item.get("up_tn") or 0),
                )
            )
            item.update(
                probability_metrics(probability_by_model.get(str(row["label"]), []))
            )
            item["hit_rate_ci_low_pct"] = low
            item["hit_rate_ci_high_pct"] = high
            item["label"] = forecast_model_label(row["label"])
            model_rows.append(item)
        evaluated_model_count = sum(int(row["evaluated"] or 0) > 0 for row in model_rows)
        mixed_models = evaluated_model_count > 1
        due_count = int(totals["due_count"] or 0)
        hit_rate = None if mixed_models else round(hits / evaluated * 100, 1) if evaluated else None
        always_up_hit_rate = (
            round(float(totals["always_up_hit_rate"]), 1)
            if totals["always_up_hit_rate"] is not None
            else None
        )
        simple_trend_hit_rate = (
            round(float(totals["simple_trend_hit_rate"]), 1)
            if totals["simple_trend_hit_rate"] is not None
            else None
        )
        hit_rate_ci_low, hit_rate_ci_high = wilson_interval(hits, evaluated)
        up_metrics = binary_up_metrics(
            int(totals["up_tp"] or 0),
            int(totals["up_fp"] or 0),
            int(totals["up_fn"] or 0),
            int(totals["up_tn"] or 0),
        )
        overall_probability_metrics = probability_metrics(probability_cases)
        if mixed_models:
            hit_rate_ci_low = hit_rate_ci_high = None
            up_metrics = {
                "up_precision_pct": None,
                "up_recall_pct": None,
                "up_specificity_pct": None,
                "balanced_accuracy_pct": None,
                "confusion": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
            }
            overall_probability_metrics = probability_metrics([])
        horizon_rows = []
        for row in by_horizon:
            item = dict(row)
            item.update(
                probability_metrics(probability_by_horizon.get(str(row["label"]), []))
            )
            horizon_rows.append(item)
        return {
            "hit_rate": hit_rate,
            "evaluated": evaluated,
            "open": int(totals["open_count"] or 0),
            "due": due_count,
            "missing_market_data": missing_market_data,
            "next_due_date": totals["next_due_date"],
            "average_deviation_pct": (
                round(float(totals["average_deviation"]), 2)
                if totals["average_deviation"] is not None
                else None
            ),
            "outcome_count": outcome_count,
            "evaluation_coverage_pct": (
                round(outcome_count / (outcome_count + due_count) * 100, 1)
                if outcome_count + due_count
                else None
            ),
            "metric_coverage_pct": (
                round(evaluated / outcome_count * 100, 1) if outcome_count else None
            ),
            "average_return_pct": (
                round(float(totals["average_return"]), 2)
                if totals["average_return"] is not None
                else None
            ),
            "average_max_return_pct": (
                round(float(totals["average_max_return"]), 2)
                if totals["average_max_return"] is not None
                else None
            ),
            "average_drawdown_pct": (
                round(float(totals["average_drawdown"]), 2)
                if totals["average_drawdown"] is not None
                else None
            ),
            "always_up_hit_rate": always_up_hit_rate,
            "no_change_hit_rate": (
                round(float(totals["no_change_hit_rate"]), 1)
                if totals["no_change_hit_rate"] is not None
                else None
            ),
            "simple_trend_hit_rate": simple_trend_hit_rate,
            "model_advantage_vs_simple_trend_pct": (
                round(hit_rate - simple_trend_hit_rate, 1)
                if hit_rate is not None and simple_trend_hit_rate is not None
                else None
            ),
            "average_market_benchmark_return_pct": (
                round(float(totals["average_market_benchmark_return"]), 2)
                if totals["average_market_benchmark_return"] is not None
                else None
            ),
            "average_excess_return_pct": (
                round(float(totals["average_excess_return"]), 2)
                if totals["average_excess_return"] is not None
                else None
            ),
            "model_advantage_vs_always_up_pct": (
                round(hit_rate - always_up_hit_rate, 1)
                if hit_rate is not None and always_up_hit_rate is not None
                else None
            ),
            "hit_rate_ci_low_pct": hit_rate_ci_low,
            "hit_rate_ci_high_pct": hit_rate_ci_high,
            **up_metrics,
            **overall_probability_metrics,
            "by_horizon": horizon_rows,
            "by_asset_type": [dict(row) for row in by_asset_type],
            "by_model": model_rows,
            **{
                key: [dict(row) for row in rows]
                for key, rows in segment_rows.items()
            },
            "evaluated_model_count": evaluated_model_count,
            "mixed_models": mixed_models,
        }
    except sqlite3.Error:
        return empty


def forecast_quality_rows(
    path: Path = DEFAULT_DATABASE_PATH,
    search: str = "",
    asset_type: str = "Alle",
    model_type: str = "Alle",
    horizon: str = "Alle",
    result_status: str = "Alle",
    created_from: date | None = None,
    created_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    if not Path(path).exists():
        return [], 0
    initialize_database(path)
    where = ["1 = 1"]
    params: list[object] = []
    if search.strip():
        where.append("(LOWER(f.ticker) LIKE ? OR LOWER(f.asset_name) LIKE ?)")
        needle = f"%{search.strip().lower()}%"
        params.extend([needle, needle])
    if asset_type != "Alle":
        where.append("f.asset_type = ?")
        params.append(asset_type)
    if model_type != "Alle":
        where.append("f.model_type = ?")
        params.append(model_type)
    if horizon != "Alle":
        where.append("h.horizon = ?")
        params.append(horizon)
    if result_status == "Offen":
        where.append("e.id IS NULL")
    elif result_status == "Treffer":
        where.append("e.direction_hit = 1")
    elif result_status == "Fehler":
        where.append("e.direction_hit = 0")
    if created_from:
        where.append("date(f.created_at) >= date(?)")
        params.append(created_from.isoformat())
    if created_to:
        where.append("date(f.created_at) <= date(?)")
        params.append(created_to.isoformat())
    where_sql = " AND ".join(where)
    select_sql = f"""
        FROM forecasts f
        JOIN forecast_horizons h ON h.forecast_id = f.id
        LEFT JOIN forecast_evaluations e
            ON e.forecast_id = f.id AND e.horizon = h.horizon
        WHERE {where_sql}
    """
    with database(path) as connection:
        total = int(connection.execute(f"SELECT COUNT(*) {select_sql}", params).fetchone()[0])
        rows = connection.execute(
            f"""
            SELECT f.asset_name AS Asset, f.ticker AS Ticker,
                   f.model_type AS Modell,
                   substr(f.created_at, 1, 10) AS "Prognose vom",
                   f.price_eur AS "Kurs damals (EUR)", h.horizon AS Prognosezeitraum,
                   h.expected_direction AS Prognose,
                   h.probability_up * 100 AS "Rohwahrscheinlichkeit Steigend (%)",
                   CASE
                     WHEN h.expected_low_eur IS NULL OR h.expected_high_eur IS NULL THEN NULL
                     ELSE printf('%.2f – %.2f EUR', h.expected_low_eur, h.expected_high_eur)
                   END AS "Erwarteter Kursbereich",
                   e.actual_price_eur AS "Tatsächlicher Kurs (EUR)",
                   e.actual_day AS "Bewertungstag",
                   e.actual_return_pct AS "Tatsächliche Rendite (%)",
                   e.max_return_pct AS "Beste Bewegung (%)",
                   e.min_return_pct AS "Schlechteste Bewegung (%)",
                   e.market_benchmark_ticker AS "Marktbenchmark",
                   e.market_benchmark_return_pct AS "Benchmark-Rendite (%)",
                   e.excess_return_pct AS "Überschussrendite (%)",
                   e.deviation_pct AS "Abweichung (%)",
                   CASE
                     WHEN e.id IS NULL THEN 'Offen'
                     WHEN e.direction_hit = 1 THEN 'Treffer'
                     WHEN e.direction_hit = 0 THEN 'Fehler'
                     ELSE 'Nicht wertbar'
                   END AS Ergebnis,
                   f.confidence AS Confidence,
                   COALESCE(e.data_quality, f.data_quality_label) AS Datenqualität,
                   CASE WHEN e.id IS NULL THEN 'offen' ELSE 'ausgewertet' END AS Status
            {select_sql}
            ORDER BY f.created_at DESC, f.ticker, h.days
            LIMIT ? OFFSET ?
            """,
            [*params, int(limit), int(offset)],
        ).fetchall()
    result_rows = [dict(row) for row in rows]
    for row in result_rows:
        row["Modell"] = forecast_model_label(row.get("Modell"))
    return result_rows, total


def recent_run_status(path: Path = DEFAULT_DATABASE_PATH) -> dict | None:
    if not Path(path).exists():
        return None
    initialize_database(path)
    with database(path) as connection:
        row = connection.execute(
            "SELECT * FROM forecast_runs ORDER BY run_date DESC, id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    try:
        result["sampling"] = (
            json.loads(str(result["sampling_json"]))
            if result.get("sampling_json")
            else None
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        result["sampling"] = None
        result["sampling_invalid"] = True
    return result


def forecast_operational_status(
    path: Path = DEFAULT_DATABASE_PATH,
    now: datetime | None = None,
    scheduled_time: str = "22:30",
    stale_after_hours: float = 9.0,
) -> dict:
    """Summarize whether the unattended daily process is running reliably.

    The function is read-only with regard to forecast content. A run is only
    considered stale after the configured maximum task duration has elapsed.
    """

    reference = now or datetime.now().astimezone()
    if reference.tzinfo is None:
        reference = reference.astimezone()
    try:
        hour_text, minute_text = str(scheduled_time).split(":", maxsplit=1)
        hour, minute = int(hour_text), int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (TypeError, ValueError):
        hour, minute = 22, 30
        scheduled_time = "22:30"

    scheduled_today = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if reference < scheduled_today:
        expected_run_date = (reference.date() - timedelta(days=1)).isoformat()
        next_run_at = scheduled_today
    else:
        expected_run_date = reference.date().isoformat()
        next_run_at = scheduled_today + timedelta(days=1)

    empty = {
        "state": "not_started",
        "label": "Noch kein Lauf dokumentiert",
        "severity": "warning",
        "message": "Der automatische Datenlauf wurde in der Prognosedatenbank noch nicht dokumentiert.",
        "scheduled_time": scheduled_time,
        "expected_run_date": expected_run_date,
        "next_run_at": next_run_at.isoformat(),
        "last_run": None,
        "last_successful_run": None,
        "last_activity_at": None,
        "last_error": None,
        "stale": False,
        "consecutive_problem_runs": 0,
    }
    if not Path(path).exists():
        return empty

    try:
        initialize_database(path)
        with database(path) as connection:
            runs = connection.execute(
                "SELECT * FROM forecast_runs ORDER BY run_date DESC, id DESC LIMIT 20"
            ).fetchall()
            if not runs:
                return empty
            latest = dict(runs[0])
            try:
                latest["sampling"] = (
                    json.loads(str(latest["sampling_json"]))
                    if latest.get("sampling_json")
                    else None
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                latest["sampling"] = None
                latest["sampling_invalid"] = True
            activity = connection.execute(
                "SELECT MAX(attempted_at) FROM run_assets WHERE run_id = ?",
                (int(latest["id"]),),
            ).fetchone()[0]
            failure = connection.execute(
                """
                SELECT error_message FROM run_assets
                WHERE run_id = ? AND status = 'failed' AND error_message IS NOT NULL
                ORDER BY attempted_at DESC LIMIT 1
                """,
                (int(latest["id"]),),
            ).fetchone()
            successful = connection.execute(
                """
                SELECT run_date, finished_at, success_count, failure_count
                FROM forecast_runs
                WHERE status IN ('completed', 'completed_with_errors') AND success_count > 0
                ORDER BY run_date DESC, id DESC LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error as exc:
        return {
            **empty,
            "state": "database_error",
            "label": "Datenbankstatus nicht lesbar",
            "severity": "error",
            "message": f"Der Betriebsstatus konnte nicht gelesen werden: {str(exc)[:300]}",
        }

    def parsed_timestamp(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=reference.tzinfo)
        return parsed.astimezone(reference.tzinfo)

    last_activity = parsed_timestamp(activity) or parsed_timestamp(latest.get("started_at"))
    stale = bool(
        str(latest.get("status")) == "running"
        and last_activity is not None
        and reference - last_activity > timedelta(hours=max(float(stale_after_hours), 0.0))
    )
    latest_date = str(latest.get("run_date") or "")
    overdue = latest_date < expected_run_date and str(latest.get("status")) != "running"
    status = str(latest.get("status") or "unknown")

    if stale:
        state, label, severity = "stale", "Lauf ohne Abschluss", "error"
        message = (
            f"Der Lauf vom {latest_date or 'unbekannten Datum'} ist seit mehr als "
            f"{float(stale_after_hours):g} Stunden ohne neue Aktivität."
        )
    elif overdue:
        state, label, severity = "overdue", "Geplanter Lauf fehlt", "warning"
        message = f"Für den erwarteten Lauftag {expected_run_date} ist kein Lauf dokumentiert."
    elif status == "running":
        state, label, severity = "running", "Datenlauf läuft", "info"
        message = f"Der Datenlauf vom {latest_date} ist aktiv."
    elif status == "completed":
        state, label, severity = "healthy", "Datenlauf erfolgreich", "success"
        message = f"Der Datenlauf vom {latest_date} wurde erfolgreich abgeschlossen."
    elif status == "completed_with_errors":
        state, label, severity = "degraded", "Lauf mit Einzelfehlern", "warning"
        message = (
            f"Der Datenlauf vom {latest_date} wurde mit "
            f"{int(latest.get('failure_count') or 0)} fehlgeschlagenen Assets abgeschlossen."
        )
    else:
        state, label, severity = "interrupted", "Datenlauf unterbrochen", "error"
        message = f"Der Datenlauf vom {latest_date} wurde nicht vollständig abgeschlossen."

    problem_statuses = {"interrupted", "completed_with_errors"}
    consecutive_problem_runs = 0
    for row in runs:
        row_status = str(row["status"])
        if row_status in problem_statuses:
            consecutive_problem_runs += 1
            continue
        if row_status == "running" and stale and int(row["id"]) == int(latest["id"]):
            consecutive_problem_runs += 1
            continue
        break

    return {
        **empty,
        "state": state,
        "label": label,
        "severity": severity,
        "message": message,
        "last_run": latest,
        "last_successful_run": dict(successful) if successful else None,
        "last_activity_at": last_activity.isoformat() if last_activity else None,
        "last_error": str(failure[0]) if failure else None,
        "stale": stale,
        "consecutive_problem_runs": consecutive_problem_runs,
    }
