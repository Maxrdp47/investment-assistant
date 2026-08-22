from __future__ import annotations

import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd


RECOVERY_SCHEMA_VERSION = 1
RECOVERY_SOURCE = "yfinance-historical"


@contextmanager
def recovery_database(path: Path) -> Iterator[sqlite3.Connection]:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_recovery_database(path: Path) -> None:
    with recovery_database(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS recovery_runs (
                id INTEGER PRIMARY KEY,
                target_at TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                purpose TEXT NOT NULL,
                forward_test_eligible INTEGER NOT NULL DEFAULT 0 CHECK (forward_test_eligible = 0),
                prediction_generated_at_target INTEGER NOT NULL DEFAULT 0
                    CHECK (prediction_generated_at_target = 0),
                asset_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                partial_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                bar_count INTEGER NOT NULL DEFAULT 0,
                data_fingerprint TEXT,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS recovery_assets (
                run_id INTEGER NOT NULL REFERENCES recovery_runs(id),
                ticker TEXT NOT NULL,
                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                region TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                daily_bar_count INTEGER NOT NULL DEFAULT 0,
                intraday_bar_count INTEGER NOT NULL DEFAULT 0,
                last_observation_at TEXT,
                error_message TEXT,
                PRIMARY KEY (run_id, ticker)
            );

            CREATE TABLE IF NOT EXISTS recovery_market_bars (
                run_id INTEGER NOT NULL REFERENCES recovery_runs(id),
                ticker TEXT NOT NULL,
                interval TEXT NOT NULL,
                timestamp_kind TEXT NOT NULL,
                bar_time_utc TEXT NOT NULL,
                bar_end_utc TEXT,
                market_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL NOT NULL,
                adjusted_close REAL,
                volume REAL,
                cutoff_at TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (run_id, ticker, interval, bar_time_utc)
            );

            CREATE INDEX IF NOT EXISTS idx_recovery_bars_ticker_time
                ON recovery_market_bars(ticker, bar_time_utc);
            CREATE INDEX IF NOT EXISTS idx_recovery_assets_status
                ON recovery_assets(run_id, status);
            """
        )
        run_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(recovery_runs)")
        }
        if "data_fingerprint" not in run_columns:
            connection.execute("ALTER TABLE recovery_runs ADD COLUMN data_fingerprint TEXT")
        connection.execute(f"PRAGMA user_version = {RECOVERY_SCHEMA_VERSION}")


def validate_target(target_at: datetime) -> datetime:
    if target_at.tzinfo is None or target_at.utcoffset() is None:
        raise ValueError("Der Recovery-Zeitpunkt benötigt eine explizite Zeitzone.")
    if target_at > datetime.now(target_at.tzinfo):
        raise ValueError("Der Recovery-Zeitpunkt darf nicht in der Zukunft liegen.")
    return target_at


def start_recovery_run(path: Path, target_at: datetime, asset_count: int) -> int:
    target = validate_target(target_at)
    initialize_recovery_database(path)
    now = datetime.now().astimezone().isoformat()
    with recovery_database(path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO recovery_runs (
                target_at, started_at, status, source, purpose, asset_count, message
            ) VALUES (?, ?, 'running', ?, ?, ?, ?)
            """,
            (
                target.isoformat(),
                now,
                RECOVERY_SOURCE,
                "Historische Point-in-Time-Marktdaten für Replay und Datenqualitätsprüfung; "
                "keine nachträgliche Forward-Prognose.",
                int(asset_count),
                "Nur historische OHLCV-Daten vor oder am expliziten Cutoff.",
            ),
        )
        row = connection.execute(
            "SELECT id FROM recovery_runs WHERE target_at = ?", (target.isoformat(),)
        ).fetchone()
        if row is None:
            raise RuntimeError("Recovery-Lauf konnte nicht angelegt werden.")
        run_id = int(row["id"])
        connection.execute(
            "UPDATE recovery_runs SET status = 'running', finished_at = NULL WHERE id = ?",
            (run_id,),
        )
    return run_id


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(result) else result


def recovery_bars(
    frame: pd.DataFrame,
    *,
    interval: str,
    target_at: datetime,
) -> list[dict]:
    target = validate_target(target_at)
    target_utc = target.astimezone(timezone.utc)
    if not isinstance(frame, pd.DataFrame) or frame.empty or "Close" not in frame:
        return []

    bars: list[dict] = []
    retrieved_at = datetime.now().astimezone().isoformat()
    for timestamp, row in frame.iterrows():
        close = _number(row.get("Close"))
        if close is None:
            continue
        parsed = pd.Timestamp(timestamp)
        if interval == "1d":
            market_date = parsed.date()
            if market_date >= target.date():
                continue
            start_utc = datetime.combine(market_date, datetime.min.time(), tzinfo=timezone.utc)
            end_utc = None
            timestamp_kind = "market_date"
        elif interval == "5m":
            if parsed.tzinfo is None:
                continue
            start_utc = parsed.to_pydatetime().astimezone(timezone.utc)
            end_utc = start_utc + timedelta(minutes=5)
            if start_utc.astimezone(target.tzinfo).date() != target.date() or end_utc > target_utc:
                continue
            market_date = start_utc.astimezone(target.tzinfo).date()
            timestamp_kind = "interval_start"
        else:
            raise ValueError(f"Nicht unterstütztes Recovery-Intervall: {interval}")

        bars.append(
            {
                "interval": interval,
                "timestamp_kind": timestamp_kind,
                "bar_time_utc": start_utc.isoformat(),
                "bar_end_utc": end_utc.isoformat() if end_utc else None,
                "market_date": market_date.isoformat(),
                "open": _number(row.get("Open")),
                "high": _number(row.get("High")),
                "low": _number(row.get("Low")),
                "close": close,
                "adjusted_close": _number(row.get("Adj Close")),
                "volume": _number(row.get("Volume")),
                "cutoff_at": target.isoformat(),
                "retrieved_at": retrieved_at,
                "source": RECOVERY_SOURCE,
            }
        )
    return bars


def record_recovery_asset(
    path: Path,
    run_id: int,
    asset: dict,
    daily_bars: list[dict],
    intraday_bars: list[dict],
    errors: list[str] | None = None,
) -> None:
    ticker = str(asset["ticker"]).upper()
    all_bars = [*daily_bars, *intraday_bars]
    if daily_bars and intraday_bars:
        status = "success"
    elif all_bars:
        status = "partial"
    else:
        status = "failed"
    last_observation = max(
        (str(bar.get("bar_end_utc") or bar["bar_time_utc"]) for bar in all_bars),
        default=None,
    )
    error_message = "; ".join(str(error)[:300] for error in (errors or []))[:1000] or None

    with recovery_database(path) as connection:
        for bar in all_bars:
            connection.execute(
                """
                INSERT OR IGNORE INTO recovery_market_bars (
                    run_id, ticker, interval, timestamp_kind, bar_time_utc, bar_end_utc,
                    market_date, open, high, low, close, adjusted_close, volume,
                    cutoff_at, retrieved_at, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    ticker,
                    bar["interval"],
                    bar["timestamp_kind"],
                    bar["bar_time_utc"],
                    bar.get("bar_end_utc"),
                    bar["market_date"],
                    bar.get("open"),
                    bar.get("high"),
                    bar.get("low"),
                    bar["close"],
                    bar.get("adjusted_close"),
                    bar.get("volume"),
                    bar["cutoff_at"],
                    bar["retrieved_at"],
                    bar["source"],
                ),
            )
        connection.execute(
            """
            INSERT INTO recovery_assets (
                run_id, ticker, asset_name, asset_type, region, category, status,
                daily_bar_count, intraday_bar_count, last_observation_at, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, ticker) DO UPDATE SET
                status = excluded.status,
                daily_bar_count = excluded.daily_bar_count,
                intraday_bar_count = excluded.intraday_bar_count,
                last_observation_at = excluded.last_observation_at,
                error_message = excluded.error_message
            """,
            (
                run_id,
                ticker,
                asset.get("name") or ticker,
                asset.get("asset_type") or "Unbekannt",
                asset.get("region") or "Unbekannt",
                asset.get("category") or "Unbekannt",
                status,
                len(daily_bars),
                len(intraday_bars),
                last_observation,
                error_message,
            ),
        )


def finish_recovery_run(path: Path, run_id: int) -> dict:
    with recovery_database(path) as connection:
        counts = connection.execute(
            """
            SELECT COUNT(*) AS assets,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS succeeded,
                   SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) AS partial,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM recovery_assets WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        bar_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM recovery_market_bars WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
        )
        fingerprint = hashlib.sha256()
        for row in connection.execute(
            """
            SELECT ticker, interval, bar_time_utc, COALESCE(bar_end_utc, ''), market_date,
                   COALESCE(open, ''), COALESCE(high, ''), COALESCE(low, ''), close,
                   COALESCE(adjusted_close, ''), COALESCE(volume, ''), cutoff_at, source
            FROM recovery_market_bars WHERE run_id = ?
            ORDER BY ticker, interval, bar_time_utc
            """,
            (run_id,),
        ):
            fingerprint.update("|".join(str(value) for value in row).encode("utf-8"))
            fingerprint.update(b"\n")
        data_fingerprint = fingerprint.hexdigest()
        has_gaps = int(counts["partial"] or 0) + int(counts["failed"] or 0) > 0
        status = "completed_with_gaps" if has_gaps else "completed"
        connection.execute(
            """
            UPDATE recovery_runs
            SET status = ?, finished_at = ?, asset_count = ?, success_count = ?,
                partial_count = ?, failure_count = ?, bar_count = ?, data_fingerprint = ?,
                message = ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now().astimezone().isoformat(),
                int(counts["assets"] or 0),
                int(counts["succeeded"] or 0),
                int(counts["partial"] or 0),
                int(counts["failed"] or 0),
                bar_count,
                data_fingerprint,
                "Historische Marktdaten gespeichert; nicht für Forward-Trefferquoten zugelassen.",
                run_id,
            ),
        )
    return recovery_summary(path, run_id)


def recovery_summary(path: Path, run_id: int) -> dict:
    with recovery_database(path) as connection:
        run = connection.execute("SELECT * FROM recovery_runs WHERE id = ?", (run_id,)).fetchone()
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        intervals = connection.execute(
            """
            SELECT interval, COUNT(*) AS bars, MIN(market_date) AS first_date,
                   MAX(market_date) AS last_date
            FROM recovery_market_bars WHERE run_id = ? GROUP BY interval ORDER BY interval
            """,
            (run_id,),
        ).fetchall()
    if run is None:
        raise ValueError(f"Recovery-Lauf {run_id} ist nicht vorhanden.")
    return {
        **dict(run),
        "database_integrity": integrity,
        "intervals": [dict(row) for row in intervals],
    }
