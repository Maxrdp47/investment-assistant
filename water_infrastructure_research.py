from __future__ import annotations

"""Isolated finite R1 research for the preregistered water hypothesis.

The module never talks to a broker or a production scanner.  It stores a
versioned market-data snapshot and stage-specific research evidence in new
append-only SQLite stores.  Validation and holdout access fail closed until
the preceding immutable gate has passed.
"""

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from swing_broad_research_audit import VALIDITY_PASS, validity_gate


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "water_infrastructure_research_v1.json"
STAGES = ("development", "validation", "holdout")
REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
STORE_SCHEMA_VERSION = 1


def canonical_json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(
        _clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        allow_nan=False,
        indent=indent,
    )


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def load_contract(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if contract.get("program_block") != "R1" or int(contract.get("attempt_count", 0)) != 1:
        raise ValueError("Water contract must be the single R1 attempt.")
    data = dict(contract.get("data") or {})
    if data.get("symbols") != ["XYL", "BMI", "PNR", "SPY", "PHO"]:
        raise ValueError("The canonical water universe changed.")
    if data.get("treatment_symbols") != ["XYL", "BMI", "PNR"]:
        raise ValueError("The canonical treatment universe changed.")
    splits = dict(contract.get("splits") or {})
    if tuple(splits) != STAGES:
        raise ValueError("Exactly development, validation and holdout must be defined.")
    prior_end: pd.Timestamp | None = None
    for stage in STAGES:
        start, end = (pd.Timestamp(value) for value in splits[stage])
        if start > end or (prior_end is not None and start <= prior_end):
            raise ValueError("Stage periods must be ordered and non-overlapping.")
        prior_end = end
    authorization = dict(contract.get("stage_authorization") or {})
    forbidden = ("external", "forward", "paper", "shadow", "broker", "orders", "production")
    if any(authorization.get(key) is not False for key in forbidden):
        raise ValueError("A forbidden later or trading stage is open.")
    return contract


def _normalize_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    value = frame.copy()
    if isinstance(value.columns, pd.MultiIndex):
        if value.columns.nlevels != 2:
            raise ValueError("Unsupported market-data column shape.")
        value.columns = [str(column[0]) for column in value.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in value.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")
    value.index = pd.to_datetime(value.index, errors="coerce", utc=True).tz_convert(None).normalize()
    value = value[~value.index.isna()].sort_index()
    value = value[~value.index.duplicated(keep=False)]
    invalid: list[dict[str, object]] = []
    valid_rows: list[dict[str, object]] = []
    for day, row in value.iterrows():
        numbers = {column: pd.to_numeric(row[column], errors="coerce") for column in REQUIRED_COLUMNS}
        ohlc = [numbers[column] for column in ("Open", "High", "Low", "Close")]
        reason = None
        if any(pd.isna(item) or not math.isfinite(float(item)) or float(item) <= 0 for item in ohlc):
            reason = "INVALID_OR_NONPOSITIVE_OHLC"
        elif float(numbers["High"]) < max(float(numbers["Open"]), float(numbers["Close"]), float(numbers["Low"])):
            reason = "HIGH_BELOW_OCL"
        elif float(numbers["Low"]) > min(float(numbers["Open"]), float(numbers["Close"]), float(numbers["High"])):
            reason = "LOW_ABOVE_OCH"
        volume = numbers["Volume"]
        if reason is not None:
            invalid.append({"session_date": day.date().isoformat(), "reason": reason})
            continue
        valid_rows.append(
            {
                "session_date": day.date().isoformat(),
                "open": float(numbers["Open"]),
                "high": float(numbers["High"]),
                "low": float(numbers["Low"]),
                "close": float(numbers["Close"]),
                "volume": None if pd.isna(volume) else float(volume),
            }
        )
    normalized = pd.DataFrame(valid_rows)
    if normalized.empty:
        raise ValueError("No valid OHLCV rows remain.")
    normalized["session_date"] = pd.to_datetime(normalized["session_date"])
    normalized = normalized.set_index("session_date")
    normalized.columns = [str(column).capitalize() for column in normalized.columns]
    return normalized, invalid


def _create_price_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS dataset_manifests (
            version TEXT PRIMARY KEY,
            dataset_fingerprint TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            contract_fingerprint TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS price_bars (
            version TEXT NOT NULL REFERENCES dataset_manifests(version),
            ticker TEXT NOT NULL,
            session_date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL,
            row_fingerprint TEXT NOT NULL,
            PRIMARY KEY(version,ticker,session_date)
        );
        CREATE TABLE IF NOT EXISTS invalid_source_rows (
            version TEXT NOT NULL REFERENCES dataset_manifests(version),
            ticker TEXT NOT NULL,
            session_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            row_fingerprint TEXT NOT NULL,
            PRIMARY KEY(version,ticker,session_date,reason)
        );
        CREATE TRIGGER IF NOT EXISTS dataset_manifests_no_update BEFORE UPDATE ON dataset_manifests
        BEGIN SELECT RAISE(ABORT,'dataset_manifests is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS dataset_manifests_no_delete BEFORE DELETE ON dataset_manifests
        BEGIN SELECT RAISE(ABORT,'dataset_manifests is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS price_bars_no_update BEFORE UPDATE ON price_bars
        BEGIN SELECT RAISE(ABORT,'price_bars is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS price_bars_no_delete BEFORE DELETE ON price_bars
        BEGIN SELECT RAISE(ABORT,'price_bars is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS invalid_source_rows_no_update BEFORE UPDATE ON invalid_source_rows
        BEGIN SELECT RAISE(ABORT,'invalid_source_rows is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS invalid_source_rows_no_delete BEFORE DELETE ON invalid_source_rows
        BEGIN SELECT RAISE(ABORT,'invalid_source_rows is append-only'); END;
        """
    )


def write_price_snapshot(
    frames: Mapping[str, pd.DataFrame],
    *,
    contract: Mapping[str, object],
    path: Path,
    retrieved_at: str | None = None,
) -> dict[str, object]:
    """Create or verify one immutable price snapshot without silent repairs."""

    required = list(dict(contract["data"])["symbols"])
    if sorted(frames) != sorted(required):
        raise ValueError("The downloaded symbols do not equal the frozen universe.")
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    normalized: dict[str, pd.DataFrame] = {}
    invalid: dict[str, list[dict[str, object]]] = {}
    canonical_rows: list[dict[str, object]] = []
    coverage: dict[str, object] = {}
    for ticker in required:
        frame, rejected = _normalize_frame(frames[ticker])
        normalized[ticker], invalid[ticker] = frame, rejected
        rows: list[dict[str, object]] = []
        for day, row in frame.iterrows():
            item = {
                "ticker": ticker,
                "session_date": day.date().isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": None if pd.isna(row["Volume"]) else float(row["Volume"]),
            }
            rows.append(item)
            canonical_rows.append(item)
        coverage[ticker] = {
            "valid_n": len(rows),
            "invalid_n": len(rejected),
            "first_session": rows[0]["session_date"],
            "last_session": rows[-1]["session_date"],
        }
    dataset_fingerprint = fingerprint(canonical_rows)
    contract_fingerprint = fingerprint(contract)
    version = str(contract["version"])
    manifest = {
        "schema_version": STORE_SCHEMA_VERSION,
        "version": version,
        "dataset_fingerprint": dataset_fingerprint,
        "contract_fingerprint": contract_fingerprint,
        "retrieved_at": timestamp,
        "source": dict(contract["data"])["source"],
        "source_semantics": dict(contract["data"])["source_semantics"],
        "coverage": coverage,
        "invalid_rows_are_missing_not_imputed": True,
        "dataset_used_to_select_universe_or_splits": False,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        _create_price_schema(connection)
        existing = connection.execute(
            "SELECT dataset_fingerprint,manifest_json FROM dataset_manifests WHERE version=?",
            (version,),
        ).fetchone()
        if existing is not None:
            if str(existing[0]) != dataset_fingerprint:
                raise RuntimeError("Immutable water price snapshot differs from the existing version.")
            stored = json.loads(str(existing[1]))
            return {**stored, "idempotent_replay": True}
        connection.execute(
            "INSERT INTO dataset_manifests VALUES (?,?,?,?,?)",
            (version, dataset_fingerprint, timestamp, contract_fingerprint, canonical_json(manifest)),
        )
        for item in canonical_rows:
            row_fingerprint = fingerprint(item)
            connection.execute(
                "INSERT INTO price_bars VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    version,
                    item["ticker"],
                    item["session_date"],
                    item["open"],
                    item["high"],
                    item["low"],
                    item["close"],
                    item["volume"],
                    row_fingerprint,
                ),
            )
        for ticker, rejected in invalid.items():
            for item in rejected:
                row = {"ticker": ticker, **item}
                connection.execute(
                    "INSERT INTO invalid_source_rows VALUES (?,?,?,?,?)",
                    (version, ticker, item["session_date"], item["reason"], fingerprint(row)),
                )
    return manifest


def read_price_snapshot(path: Path, contract: Mapping[str, object]) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    version = str(contract["version"])
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        manifest_row = connection.execute(
            "SELECT manifest_json FROM dataset_manifests WHERE version=?", (version,)
        ).fetchone()
        if manifest_row is None:
            raise RuntimeError("The frozen water dataset is missing.")
        manifest = json.loads(str(manifest_row[0]))
        frames: dict[str, pd.DataFrame] = {}
        for ticker in dict(contract["data"])["symbols"]:
            rows = connection.execute(
                "SELECT session_date,open,high,low,close,volume FROM price_bars "
                "WHERE version=? AND ticker=? ORDER BY session_date",
                (version, ticker),
            ).fetchall()
            frame = pd.DataFrame([dict(row) for row in rows])
            if frame.empty:
                raise RuntimeError(f"No frozen rows for {ticker}.")
            frame["session_date"] = pd.to_datetime(frame["session_date"])
            frame = frame.set_index("session_date")
            frame.columns = [str(column).capitalize() for column in frame.columns]
            frames[str(ticker)] = frame
    finally:
        connection.close()
    if fingerprint(
        [
            {
                "ticker": ticker,
                "session_date": day.date().isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": None if pd.isna(row["Volume"]) else float(row["Volume"]),
            }
            for ticker in dict(contract["data"])["symbols"]
            for day, row in frames[str(ticker)].iterrows()
        ]
    ) != manifest["dataset_fingerprint"]:
        raise RuntimeError("Water dataset fingerprint verification failed.")
    return frames, manifest


def _create_result_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS contract_freezes (
            version TEXT PRIMARY KEY,
            freeze_fingerprint TEXT NOT NULL UNIQUE,
            frozen_at TEXT NOT NULL,
            freeze_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS challenger_freezes (
            challenger_version TEXT PRIMARY KEY,
            freeze_fingerprint TEXT NOT NULL UNIQUE,
            frozen_at TEXT NOT NULL,
            freeze_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage_events (
            event_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_at TEXT NOT NULL,
            event_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_cases (
            case_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            case_type TEXT NOT NULL,
            signal_day TEXT NOT NULL,
            ticker TEXT NOT NULL,
            horizon INTEGER NOT NULL,
            case_fingerprint TEXT NOT NULL,
            case_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage_reviews (
            stage TEXT PRIMARY KEY,
            decision TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            review_fingerprint TEXT NOT NULL UNIQUE,
            review_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS research_cases_stage ON research_cases(stage,case_type,ticker,signal_day);
        CREATE TRIGGER IF NOT EXISTS contract_freezes_no_update BEFORE UPDATE ON contract_freezes
        BEGIN SELECT RAISE(ABORT,'contract_freezes is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS contract_freezes_no_delete BEFORE DELETE ON contract_freezes
        BEGIN SELECT RAISE(ABORT,'contract_freezes is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS challenger_freezes_no_update BEFORE UPDATE ON challenger_freezes
        BEGIN SELECT RAISE(ABORT,'challenger_freezes is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS challenger_freezes_no_delete BEFORE DELETE ON challenger_freezes
        BEGIN SELECT RAISE(ABORT,'challenger_freezes is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS stage_events_no_update BEFORE UPDATE ON stage_events
        BEGIN SELECT RAISE(ABORT,'stage_events is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS stage_events_no_delete BEFORE DELETE ON stage_events
        BEGIN SELECT RAISE(ABORT,'stage_events is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS research_cases_no_update BEFORE UPDATE ON research_cases
        BEGIN SELECT RAISE(ABORT,'research_cases is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS research_cases_no_delete BEFORE DELETE ON research_cases
        BEGIN SELECT RAISE(ABORT,'research_cases is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS stage_reviews_no_update BEFORE UPDATE ON stage_reviews
        BEGIN SELECT RAISE(ABORT,'stage_reviews is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS stage_reviews_no_delete BEFORE DELETE ON stage_reviews
        BEGIN SELECT RAISE(ABORT,'stage_reviews is append-only'); END;
        """
    )


def freeze_research_contract(
    result_store: Path,
    *,
    contract: Mapping[str, object],
    dataset_manifest: Mapping[str, object],
    code_fingerprint: str,
    frozen_at: str | None = None,
) -> dict[str, object]:
    timestamp = frozen_at or datetime.now(timezone.utc).isoformat()
    value = {
        "version": contract["version"],
        "program_id": contract["program_id"],
        "program_block": "R1",
        "attempt_count": 1,
        "contract_fingerprint": fingerprint(contract),
        "dataset_fingerprint": dataset_manifest["dataset_fingerprint"],
        "code_fingerprint": code_fingerprint,
        "splits": contract["splits"],
        "primary_rule": contract["primary_rule"],
        "sensitivity_rules": contract["sensitivity_rules"],
        "controls": contract["controls"],
        "costs": contract["costs"],
        "development_gate": contract["development_gate"],
        "stage_authorization": contract["stage_authorization"],
        "frozen_before_any_outcome_review": True,
    }
    value["freeze_fingerprint"] = fingerprint(value)
    target = Path(result_store)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        _create_result_schema(connection)
        existing = connection.execute(
            "SELECT freeze_json FROM contract_freezes WHERE version=?", (str(contract["version"]),)
        ).fetchone()
        if existing is not None:
            stored = json.loads(str(existing[0]))
            if stored.get("freeze_fingerprint") != value["freeze_fingerprint"]:
                raise RuntimeError("The immutable R1 research freeze differs.")
            return {**stored, "idempotent_replay": True}
        connection.execute(
            "INSERT INTO contract_freezes VALUES (?,?,?,?)",
            (contract["version"], value["freeze_fingerprint"], timestamp, canonical_json(value)),
        )
    return value


def _basket(frames: Mapping[str, pd.DataFrame], members: Sequence[str]) -> pd.DataFrame:
    common = None
    for ticker in members:
        common = frames[ticker].index if common is None else common.intersection(frames[ticker].index)
    if common is None or len(common) == 0:
        raise RuntimeError("No common water-basket sessions.")
    components = []
    for ticker in members:
        item = frames[ticker].loc[common, list(REQUIRED_COLUMNS)].copy()
        base = float(item.iloc[0]["Close"])
        item[["Open", "High", "Low", "Close"]] = item[["Open", "High", "Low", "Close"]] / base
        item["Volume"] = np.nan
        components.append(item)
    result = sum((item[["Open", "High", "Low", "Close"]] for item in components)) / len(components)
    result["Volume"] = np.nan
    return result


def _feature_frame(frame: pd.DataFrame, breakout_days: int, spy: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["Close"].astype(float)
    result["prior_252_high"] = close.shift(1).rolling(252, min_periods=252).max()
    result["prior_breakout_high"] = close.shift(1).rolling(breakout_days, min_periods=breakout_days).max()
    result["drawdown"] = close / result["prior_252_high"] - 1.0
    result["first_cross"] = (close > result["prior_breakout_high"]) & (
        close.shift(1) <= result["prior_breakout_high"].shift(1)
    )
    result["realized_volatility_20"] = close.pct_change().rolling(20, min_periods=20).std() * math.sqrt(252)
    spy_close = spy["Close"].astype(float)
    spy_regime = spy_close >= spy_close.rolling(200, min_periods=200).mean()
    result["spy_regime"] = spy_regime.reindex(result.index)
    return result


def _net_return(frame: pd.DataFrame, signal_position: int, horizon: int, one_way_bps: float) -> dict[str, object] | None:
    entry_position = signal_position + 1
    exit_position = entry_position + horizon - 1
    if exit_position >= len(frame):
        return None
    entry_day = frame.index[entry_position]
    exit_day = frame.index[exit_position]
    raw_entry = float(frame.iloc[entry_position]["Open"])
    raw_exit = float(frame.iloc[exit_position]["Close"])
    if raw_entry <= 0 or raw_exit <= 0:
        return None
    entry = raw_entry * (1.0 + one_way_bps / 10_000.0)
    exit_value = raw_exit * (1.0 - one_way_bps / 10_000.0)
    return {
        "entry_day": entry_day.date().isoformat(),
        "exit_day": exit_day.date().isoformat(),
        "raw_entry": raw_entry,
        "raw_exit": raw_exit,
        "gross_return": raw_exit / raw_entry - 1.0,
        "net_return": exit_value / entry - 1.0,
    }


def _eligible_positions(
    featured: pd.DataFrame,
    *,
    stage_start: pd.Timestamp,
    stage_end: pd.Timestamp,
    drawdown: float,
    horizon: int,
) -> list[int]:
    positions: list[int] = []
    for position, (day, row) in enumerate(featured.iterrows()):
        exit_position = position + horizon
        if day < stage_start or day > stage_end or exit_position >= len(featured):
            continue
        if featured.index[exit_position] > stage_end:
            continue
        if bool(row["first_cross"]) and float(row["drawdown"]) <= drawdown:
            positions.append(position)
    return positions


def _case(
    *,
    stage: str,
    case_type: str,
    ticker: str,
    signal_day: pd.Timestamp,
    horizon: int,
    payload: Mapping[str, object],
) -> dict[str, object]:
    core = {
        "stage": stage,
        "case_type": case_type,
        "ticker": ticker,
        "signal_day": signal_day.date().isoformat(),
        "horizon": int(horizon),
        **dict(payload),
    }
    core["case_id"] = "water-case-" + fingerprint(core)[:32]
    core["case_fingerprint"] = fingerprint(core)
    return core


def _metrics(rows: Sequence[Mapping[str, object]], key: str = "net_return") -> dict[str, object]:
    values = [float(row[key]) for row in rows if row.get(key) is not None and math.isfinite(float(row[key]))]
    if not values:
        return {"n": 0, "mean": None, "median": None, "hit_rate": None, "profit_factor": None, "max_sequence_drawdown": None}
    series = np.asarray(values, dtype=float)
    gross_profit = float(series[series > 0].sum())
    gross_loss = float(abs(series[series < 0].sum()))
    equity = np.cumsum(series)
    drawdown = equity - np.maximum.accumulate(np.concatenate(([0.0], equity)))[1:]
    return {
        "n": len(values),
        "mean": float(series.mean()),
        "median": float(np.median(series)),
        "hit_rate": float((series > 0).mean()),
        "profit_factor": None if gross_loss == 0 else gross_profit / gross_loss,
        "max_sequence_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
    }


def _cluster_bootstrap(
    rows: Sequence[Mapping[str, object]], *, seed: int, replicates: int
) -> dict[str, object]:
    clusters: dict[str, list[float]] = {}
    for row in rows:
        value = row.get("net_return")
        if value is None:
            continue
        cluster = f"{row['ticker']}|{str(row['signal_day'])[:4]}"
        clusters.setdefault(cluster, []).append(float(value))
    cluster_means = np.asarray(
        [float(np.mean(values)) for _, values in sorted(clusters.items())], dtype=float
    )
    if len(cluster_means) < 2:
        return {
            "status": "UNDERPOWERED",
            "cluster_n": int(len(cluster_means)),
            "mean_ci_95": [None, None],
        }
    generator = np.random.default_rng(seed)
    estimates = np.empty(replicates, dtype=float)
    for index in range(replicates):
        draw = generator.choice(cluster_means, size=len(cluster_means), replace=True)
        estimates[index] = float(draw.mean())
    return {
        "status": "DESCRIPTIVE_ONLY",
        "cluster_n": int(len(cluster_means)),
        "replicates": int(replicates),
        "seed": int(seed),
        "mean_ci_95": [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))],
    }


def _effective_nonoverlap_n(rows: Sequence[Mapping[str, object]], horizon: int = 60) -> int:
    by_ticker: dict[str, list[pd.Timestamp]] = {}
    for row in rows:
        by_ticker.setdefault(str(row["ticker"]), []).append(pd.Timestamp(str(row["entry_day"])))
    total = 0
    for days in by_ticker.values():
        last: pd.Timestamp | None = None
        for day in sorted(set(days)):
            # ``horizon`` is measured in trading sessions.  Convert it to a
            # conservative calendar-day separation before counting another
            # observation as non-overlapping.
            if last is None or (day - last).days >= math.ceil(horizon * 7 / 5):
                total += 1
                last = day
    return total


def _matched_controls(
    featured: pd.DataFrame,
    signal_positions: Sequence[int],
    *,
    stage_start: pd.Timestamp,
    stage_end: pd.Timestamp,
    horizon: int,
) -> list[int]:
    signal_set = set(signal_positions)
    used: set[int] = set()
    controls: list[int] = []
    for signal_position in signal_positions:
        signal_day = featured.index[signal_position]
        signal = featured.iloc[signal_position]
        if pd.isna(signal["realized_volatility_20"]) or pd.isna(signal["spy_regime"]):
            continue
        candidates: list[tuple[float, str, int]] = []
        for position, (day, row) in enumerate(featured.iterrows()):
            if position in signal_set or position in used or day < stage_start or day > stage_end:
                continue
            if day.year != signal_day.year or bool(row["spy_regime"]) != bool(signal["spy_regime"]):
                continue
            if pd.isna(row["realized_volatility_20"]) or position + horizon >= len(featured):
                continue
            if featured.index[position + horizon] > stage_end:
                continue
            distance = abs(float(row["realized_volatility_20"]) - float(signal["realized_volatility_20"]))
            candidates.append((distance, day.date().isoformat(), position))
        if candidates:
            selected = min(candidates)[2]
            used.add(selected)
            controls.append(selected)
    return controls


def _benchmark_case(
    frame: pd.DataFrame,
    *,
    signal_day: pd.Timestamp,
    horizon: int,
    one_way_bps: float,
) -> dict[str, object] | None:
    after = np.flatnonzero(frame.index > signal_day)
    if len(after) == 0:
        return None
    entry_position = int(after[0])
    synthetic_signal_position = entry_position - 1
    if synthetic_signal_position < 0:
        return None
    return _net_return(frame, synthetic_signal_position, horizon, one_way_bps)


def _stage_cases(
    frames: Mapping[str, pd.DataFrame],
    contract: Mapping[str, object],
    stage: str,
    *,
    drawdown: float,
    breakout_days: int,
    rule_id: str,
) -> list[dict[str, object]]:
    start, end = (pd.Timestamp(value) for value in dict(contract["splits"])[stage])
    horizons = [int(value) for value in dict(contract["primary_rule"])["horizons"]]
    primary_horizon = int(dict(contract["development_gate"])["required_primary_horizon"])
    equity_cost = float(dict(contract["costs"])["equity_one_way_bps"])
    etf_cost = float(dict(contract["costs"])["etf_one_way_bps"])
    treatment_symbols = list(dict(contract["data"])["treatment_symbols"])
    results: list[dict[str, object]] = []
    featured_by_symbol: dict[str, pd.DataFrame] = {}
    for ticker in treatment_symbols:
        featured = _feature_frame(frames[ticker], breakout_days, frames["SPY"])
        featured_by_symbol[ticker] = featured
        positions = _eligible_positions(
            featured, stage_start=start, stage_end=end, drawdown=drawdown, horizon=max(horizons)
        )
        for position in positions:
            day = featured.index[position]
            feature_payload = {
                "rule_id": rule_id,
                "drawdown": float(featured.iloc[position]["drawdown"]),
                "prior_252_high": float(featured.iloc[position]["prior_252_high"]),
                "prior_breakout_high": float(featured.iloc[position]["prior_breakout_high"]),
                "realized_volatility_20": float(featured.iloc[position]["realized_volatility_20"]),
                "spy_regime": "ABOVE_SMA200" if bool(featured.iloc[position]["spy_regime"]) else "BELOW_SMA200",
            }
            for horizon in horizons:
                outcome = _net_return(featured, position, horizon, equity_cost)
                if outcome is None or pd.Timestamp(str(outcome["exit_day"])) > end:
                    continue
                results.append(
                    _case(stage=stage, case_type="treatment", ticker=ticker, signal_day=day, horizon=horizon, payload={**feature_payload, **outcome})
                )
                for benchmark in dict(contract["data"])["benchmark_symbols"]:
                    benchmark_outcome = _benchmark_case(
                        frames[str(benchmark)], signal_day=day, horizon=horizon, one_way_bps=etf_cost
                    )
                    if benchmark_outcome is not None and pd.Timestamp(str(benchmark_outcome["exit_day"])) <= end:
                        results.append(
                            _case(
                                stage=stage,
                                case_type=f"benchmark_{str(benchmark).lower()}",
                                ticker=ticker,
                                signal_day=day,
                                horizon=horizon,
                                payload={"rule_id": rule_id, "benchmark": benchmark, **benchmark_outcome},
                            )
                        )
        controls = _matched_controls(
            featured, positions, stage_start=start, stage_end=end, horizon=primary_horizon
        )
        for position in controls:
            outcome = _net_return(featured, position, primary_horizon, equity_cost)
            if outcome is None:
                continue
            day = featured.index[position]
            results.append(
                _case(
                    stage=stage,
                    case_type="matched_control",
                    ticker=ticker,
                    signal_day=day,
                    horizon=primary_horizon,
                    payload={
                        "rule_id": rule_id,
                        "realized_volatility_20": float(featured.iloc[position]["realized_volatility_20"]),
                        "spy_regime": "ABOVE_SMA200" if bool(featured.iloc[position]["spy_regime"]) else "BELOW_SMA200",
                        **outcome,
                    },
                )
            )
    if rule_id == "primary":
        basket_contract = dict(dict(contract["controls"])["equal_weight_water_basket"])
        basket_frame = _basket(frames, list(basket_contract["members"]))
        basket_featured = _feature_frame(basket_frame, breakout_days, frames["SPY"])
        basket_positions = _eligible_positions(
            basket_featured, stage_start=start, stage_end=end, drawdown=drawdown, horizon=max(horizons)
        )
        basket_cost = float(dict(contract["costs"])["basket_one_way_bps"])
        for position in basket_positions:
            day = basket_featured.index[position]
            for horizon in horizons:
                outcome = _net_return(basket_featured, position, horizon, basket_cost)
                if outcome is not None and pd.Timestamp(str(outcome["exit_day"])) <= end:
                    results.append(
                        _case(
                            stage=stage,
                            case_type="equal_weight_basket",
                            ticker="WATER_EW",
                            signal_day=day,
                            horizon=horizon,
                            payload={
                                "rule_id": rule_id,
                                "drawdown": float(basket_featured.iloc[position]["drawdown"]),
                                "realized_volatility_20": float(basket_featured.iloc[position]["realized_volatility_20"]),
                                **outcome,
                            },
                        )
                    )
    return results


def _buy_and_hold(frames: Mapping[str, pd.DataFrame], contract: Mapping[str, object], stage: str) -> dict[str, object]:
    start, end = (pd.Timestamp(value) for value in dict(contract["splits"])[stage])
    output: dict[str, object] = {}
    for ticker in dict(contract["data"])["treatment_symbols"]:
        frame = frames[str(ticker)].loc[start:end]
        if frame.empty:
            output[str(ticker)] = {"status": "NO_DATA"}
            continue
        bps = float(dict(contract["costs"])["equity_one_way_bps"])
        entry = float(frame.iloc[0]["Open"]) * (1.0 + bps / 10_000.0)
        exit_value = float(frame.iloc[-1]["Close"]) * (1.0 - bps / 10_000.0)
        output[str(ticker)] = {
            "status": "COMPLETE",
            "entry_day": frame.index[0].date().isoformat(),
            "exit_day": frame.index[-1].date().isoformat(),
            "net_return": exit_value / entry - 1.0,
        }
    return output


def review_stage(
    frames: Mapping[str, pd.DataFrame], contract: Mapping[str, object], stage: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if stage not in STAGES:
        raise ValueError(stage)
    primary_rule = dict(contract["primary_rule"])
    primary = _stage_cases(
        frames,
        contract,
        stage,
        drawdown=float(primary_rule["drawdown_from_prior_252_close_high_lte"]),
        breakout_days=int(primary_rule["breakout_close_above_prior_n_close_high"]),
        rule_id="primary",
    )
    sensitivity_cases: list[dict[str, object]] = []
    for rule in contract["sensitivity_rules"]:
        sensitivity_cases.extend(
            _stage_cases(
                frames,
                contract,
                stage,
                drawdown=float(rule["drawdown"]),
                breakout_days=int(rule["breakout_days"]),
                rule_id=str(rule["id"]),
            )
        )
    cases = primary + sensitivity_cases
    horizon = int(dict(contract["development_gate"])["required_primary_horizon"])
    treatment = [row for row in primary if row["case_type"] == "treatment" and row["horizon"] == horizon]
    control = [row for row in primary if row["case_type"] == "matched_control" and row["horizon"] == horizon]
    spy = [row for row in primary if row["case_type"] == "benchmark_spy" and row["horizon"] == horizon]
    pho = [row for row in primary if row["case_type"] == "benchmark_pho" and row["horizon"] == horizon]
    basket = [row for row in primary if row["case_type"] == "equal_weight_basket" and row["horizon"] == horizon]
    gate_contract = dict(contract["development_gate"])
    validity = validity_gate(
        universe_n=len(treatment) + len(control),
        applicable_n=len(treatment) + len(control),
        valid_n=len(treatment) + len(control),
        structurally_not_applicable_n=0,
        missing_n=0,
        treatment_n=len(treatment),
        control_n=len(control),
        treatment_effective_n=_effective_nonoverlap_n(treatment),
        control_effective_n=_effective_nonoverlap_n(control),
        feature_point_in_time_available=True,
        outcome_independent_definition=True,
        market_scope_correct=True,
        setup_scope_correct=True,
        structural_missingness_treated_as_false=False,
        min_raw_group_n=int(gate_contract["minimum_raw_treatment_n"]),
        min_effective_group_n=int(gate_contract["minimum_effective_treatment_n"]),
        min_group_share=float(gate_contract["minimum_group_share"]),
    )
    treatment_metrics = _metrics(treatment)
    control_metrics = _metrics(control)
    spy_metrics = _metrics(spy)
    pho_metrics = _metrics(pho)
    by_year: dict[str, dict[str, object]] = {}
    for year in sorted({str(row["signal_day"])[:4] for row in treatment}):
        by_year[year] = _metrics([row for row in treatment if str(row["signal_day"]).startswith(year)])
    abs_year = {year: abs(float(value["mean"] or 0.0) * int(value["n"])) for year, value in by_year.items()}
    abs_total = sum(abs_year.values())
    positive_year_share = (
        sum(1 for value in by_year.values() if float(value["mean"] or 0.0) > 0) / len(by_year)
        if by_year
        else 0.0
    )
    largest_year_share = max(abs_year.values(), default=0.0) / abs_total if abs_total else 1.0
    sensitivity: dict[str, object] = {}
    for rule in contract["sensitivity_rules"]:
        rule_rows = [
            row
            for row in sensitivity_cases
            if row["case_type"] == "treatment" and row["horizon"] == horizon and row.get("rule_id") == rule["id"]
        ]
        sensitivity[str(rule["id"])] = _metrics(rule_rows)
    uncertainty_contract = dict(contract["uncertainty"])
    uncertainty = _cluster_bootstrap(
        treatment,
        seed=int(uncertainty_contract["seed"]),
        replicates=int(uncertainty_contract["replicates"]),
    )
    treatment_mean = treatment_metrics["mean"]
    control_mean = control_metrics["mean"]
    spy_mean = spy_metrics["mean"]
    pho_mean = pho_metrics["mean"]
    criteria = {
        "validity_gate_pass": validity["status"] == VALIDITY_PASS,
        "net_expectancy_positive": treatment_mean is not None and float(treatment_mean) > 0,
        "net_profit_factor_above_one": treatment_metrics["profit_factor"] is not None and float(treatment_metrics["profit_factor"]) > 1,
        "matched_control_delta_positive": treatment_mean is not None and control_mean is not None and float(treatment_mean) > float(control_mean),
        "alpha_vs_spy_positive": treatment_mean is not None and spy_mean is not None and float(treatment_mean) > float(spy_mean),
        "alpha_vs_pho_positive": treatment_mean is not None and pho_mean is not None and float(treatment_mean) > float(pho_mean),
        "positive_in_at_least_60pct_of_evaluated_years": positive_year_share >= 0.60,
        "no_single_year_above_50pct_absolute_result_contribution": largest_year_share <= 0.50,
        "all_predeclared_one_factor_sensitivities_non_negative": bool(sensitivity) and all(
            value["mean"] is not None and float(value["mean"]) >= 0 for value in sensitivity.values()
        ),
    }
    passed = all(criteria.values())
    if stage == "development":
        decision = "DEVELOPMENT_PASS" if passed else (
            "DEVELOPMENT_INCONCLUSIVE" if validity["status"] != VALIDITY_PASS else "DEVELOPMENT_FAIL"
        )
    elif stage == "validation":
        decision = "VALIDATION_PASS" if passed else (
            "VALIDATION_INCONCLUSIVE" if validity["status"] != VALIDITY_PASS else "VALIDATION_FAIL"
        )
    else:
        decision = "HOLDOUT_PASS" if passed else (
            "HOLDOUT_INCONCLUSIVE" if validity["status"] != VALIDITY_PASS else "HOLDOUT_FAIL"
        )
    review = {
        "version": contract["version"],
        "program_block": "R1",
        "stage": stage,
        "decision": decision,
        "attempt_count": 1,
        "primary_horizon": horizon,
        "validity_gate": validity,
        "treatment": treatment_metrics,
        "matched_control": control_metrics,
        "benchmark_spy": spy_metrics,
        "benchmark_pho": pho_metrics,
        "equal_weight_water_basket": _metrics(basket),
        "buy_and_hold": _buy_and_hold(frames, contract, stage),
        "year_stability": {
            "years": by_year,
            "positive_year_share": positive_year_share,
            "largest_absolute_result_contribution_share": largest_year_share,
        },
        "uncertainty": uncertainty,
        "walk_forward": {
            "method": "fixed preregistered rule; chronological calendar-year diagnostics; no refit",
            "year_slices": by_year,
            "parameter_refits": 0,
        },
        "sensitivity": sensitivity,
        "robustness_criteria": criteria,
        "all_criteria_required": True,
        "selection_after_outcomes": False,
        "individual_symbols_dropped_after_results": False,
        "portfolio_claim_allowed": False,
        "validation_opened": stage in {"validation", "holdout"},
        "holdout_opened": stage == "holdout",
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
        "orders_opened": False,
    }
    review["review_fingerprint"] = fingerprint(review)
    return cases, review


def _read_review(connection: sqlite3.Connection, stage: str) -> dict[str, object] | None:
    row = connection.execute("SELECT review_json FROM stage_reviews WHERE stage=?", (stage,)).fetchone()
    return None if row is None else json.loads(str(row[0]))


def _ensure_stage_allowed(connection: sqlite3.Connection, stage: str) -> None:
    if stage == "development":
        return
    development = _read_review(connection, "development")
    if development is None or development.get("decision") != "DEVELOPMENT_PASS":
        raise RuntimeError("Validation is closed because Development did not pass.")
    frozen = connection.execute("SELECT 1 FROM challenger_freezes LIMIT 1").fetchone()
    if frozen is None:
        raise RuntimeError("Validation is closed because no challenger was frozen.")
    if stage == "holdout":
        validation = _read_review(connection, "validation")
        if validation is None or validation.get("decision") != "VALIDATION_PASS":
            raise RuntimeError("Holdout is closed because Validation did not pass.")


def persist_stage(
    result_store: Path,
    *,
    frames: Mapping[str, pd.DataFrame],
    contract: Mapping[str, object],
    stage: str,
    run_at: str | None = None,
) -> dict[str, object]:
    timestamp = run_at or datetime.now(timezone.utc).isoformat()
    target = Path(result_store)
    with sqlite3.connect(target) as connection:
        connection.row_factory = sqlite3.Row
        _create_result_schema(connection)
        existing = _read_review(connection, stage)
        if existing is not None:
            return {**existing, "idempotent_replay": True}
        _ensure_stage_allowed(connection, stage)
        start_event = {
            "stage": stage,
            "event_type": "OPENED",
            "seen_data_consumed": True,
            "period": dict(contract["splits"])[stage],
            "hypothesis_id": dict(contract["knowledge_base"])["hypothesis_id"],
            "version": contract["version"],
        }
        connection.execute(
            "INSERT OR IGNORE INTO stage_events VALUES (?,?,?,?,?)",
            (f"{contract['version']}:{stage}:OPENED", stage, "OPENED", timestamp, canonical_json(start_event)),
        )
        connection.commit()
    cases, review = review_stage(frames, contract, stage)
    reviewed_at = timestamp
    with sqlite3.connect(target) as connection:
        connection.row_factory = sqlite3.Row
        _create_result_schema(connection)
        _ensure_stage_allowed(connection, stage)
        for item in cases:
            connection.execute(
                "INSERT OR IGNORE INTO research_cases VALUES (?,?,?,?,?,?,?,?)",
                (
                    item["case_id"],
                    stage,
                    item["case_type"],
                    item["signal_day"],
                    item["ticker"],
                    item["horizon"],
                    item["case_fingerprint"],
                    canonical_json(item),
                ),
            )
        connection.execute(
            "INSERT INTO stage_reviews VALUES (?,?,?,?,?)",
            (stage, review["decision"], reviewed_at, review["review_fingerprint"], canonical_json(review)),
        )
        complete_event = {
            "stage": stage,
            "event_type": "COMPLETED",
            "decision": review["decision"],
            "case_n": len(cases),
            "review_fingerprint": review["review_fingerprint"],
        }
        connection.execute(
            "INSERT OR IGNORE INTO stage_events VALUES (?,?,?,?,?)",
            (f"{contract['version']}:{stage}:COMPLETED", stage, "COMPLETED", timestamp, canonical_json(complete_event)),
        )
        if stage == "development" and review["decision"] == "DEVELOPMENT_PASS":
            challenger = {
                "challenger_version": "water-infrastructure-primary-2026.09.15-v1",
                "parent_research_version": contract["version"],
                "rule": contract["primary_rule"],
                "scope": contract["data"],
                "costs": contract["costs"],
                "splits": contract["splits"],
                "missingness": {
                    "missing_is_false": False,
                    "invalid_rows_imputed": False,
                },
                "development_review_fingerprint": review["review_fingerprint"],
                "changes_after_freeze_allowed": False,
            }
            challenger["freeze_fingerprint"] = fingerprint(challenger)
            connection.execute(
                "INSERT INTO challenger_freezes VALUES (?,?,?,?)",
                (
                    challenger["challenger_version"],
                    challenger["freeze_fingerprint"],
                    timestamp,
                    canonical_json(challenger),
                ),
            )
    return review


def write_append_only_artifact(path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    target = Path(path)
    value = dict(payload)
    value.setdefault("artifact_fingerprint", fingerprint(value))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stored = json.loads(target.read_text(encoding="utf-8"))
        if stored != value:
            raise RuntimeError(f"Append-only artifact differs: {target}")
        return {**stored, "idempotent_replay": True}
    target.write_text(canonical_json(value, indent=2) + "\n", encoding="utf-8")
    return value


def store_status(path: Path) -> dict[str, object]:
    target = Path(path)
    if not target.exists():
        return {"status": "NOT_PREPARED", "stages": {stage: None for stage in STAGES}}
    connection = sqlite3.connect(target.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        freezes = [dict(row) for row in connection.execute("SELECT version,freeze_fingerprint,frozen_at FROM contract_freezes")]
        challenger = [dict(row) for row in connection.execute("SELECT challenger_version,freeze_fingerprint,frozen_at FROM challenger_freezes")]
        reviews = {
            stage: _read_review(connection, stage)
            for stage in STAGES
        }
        case_n = {
            str(row["stage"]): int(row["n"])
            for row in connection.execute("SELECT stage,COUNT(*) n FROM research_cases GROUP BY stage")
        }
    finally:
        connection.close()
    return {
        "status": "PREPARED" if freezes else "INVALID_NO_FREEZE",
        "freezes": freezes,
        "challenger_freezes": challenger,
        "stages": reviews,
        "case_n": case_n,
    }
