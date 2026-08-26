from __future__ import annotations

"""Broad, outcome-blind Point-in-Time research over the frozen Swing dataset.

This module is intentionally separate from the existing Walk-Forward campaign.  It
does not mutate its queue, cases, strategy profiles or database.  Candidate
selection and features only see bars through the completed signal bar.  Labels
and counterfactual execution experiments are built afterwards and persisted in
separate append-only tables.
"""

import bisect
import functools
import hashlib
import json
import math
import sqlite3
import zlib
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from cot_positioning import (
    COT_FEATURE_VERSION,
    build_asset_cot_shadow_context,
    load_cot_market_mapping,
)
from swing_broad_context import (
    BROAD_BENCHMARK_MAPPING_VERSION,
    BROAD_BREADTH_VERSION,
    BROAD_CONTEXT_VERSION,
    breadth_feature_for_asset,
    build_shared_asset_features,
)
from swing_research_dataset import normalized_research_history
from swing_research_identity import derive_swing_research_identity
from swing_research_quality import parameter_plateau_report
from swing_walk_forward import _prepare_historical_indicators, _technical_scores
from technical_analysis import value_or_none
from trading_assistant import (
    DEFAULT_SWING_THRESHOLDS,
    SWING_EXECUTION_COST_VERSION,
    _breakout_candidate,
    _pullback_candidate,
    data_quality_score,
    swing_execution_cost_contract,
)


BROAD_RESEARCH_SCHEMA_VERSION = 4
BROAD_RESEARCH_CANDIDATE_VERSION = "swing-broad-candidates-2026.08.22-v1"
BROAD_RESEARCH_FEATURE_VERSION = "swing-broad-pit-features-frozen-first-pass-2026.08.22-v3"
BROAD_RESEARCH_LABEL_VERSION = "swing-broad-direction-neutral-labels-2026.08.22-v2"
BROAD_RESEARCH_COUNTERFACTUAL_VERSION = "swing-stop-exit-counterfactuals-2026.08.22-v1"
BROAD_RESEARCH_PATTERN_VERSION = "swing-development-patterns-2026.08.23-v2"
BROAD_RESEARCH_COT_LINK_VERSION = "swing-broad-cot-link-2026.08.22-v1"
BROAD_RESEARCH_SPLIT_VERSION = "swing-broad-chronological-splits-2026.08.22-v1"
DEFAULT_BROAD_RESEARCH_DB_PATH = Path(__file__).resolve().parent / "runtime" / "swing_broad_research.sqlite3"

MINIMUM_HISTORY_ROWS = 220
FUTURE_SESSIONS = 25
CANDIDATE_COOLDOWN_SESSIONS = 5
PIVOT_WINDOW = 2
PULLBACK_IMPULSE_LOOKBACK = 60
PULLBACK_MIN_IMPULSE_PCT = 5.0
PULLBACK_MAX_DURATION = 30
PULLBACK_DEPTH_RANGE = (0.05, 1.20)
BREAKOUT_LOOKBACK = 20
BREAKOUT_PROXIMITY_ATR = 0.25
ATR_STOP_MULTIPLE = 2.0
PULLBACK_ATR_BUFFER = 0.25


class BroadResearchContractError(ValueError):
    """A broad-research row or operation violates the immutable contract."""


@functools.lru_cache(maxsize=1)
def broad_research_code_fingerprint() -> str:
    """Fingerprint the exact local research implementation reused by this pass."""
    root = Path(__file__).resolve().parent
    files = (
        "swing_broad_research.py",
        "swing_broad_context.py",
        "swing_walk_forward.py",
        "swing_research_dataset.py",
        "swing_research_identity.py",
        "swing_research_quality.py",
        "cot_positioning.py",
        "technical_analysis.py",
        "trading_assistant.py",
    )
    digest = hashlib.sha256()
    for name in files:
        path = root / name
        if not path.is_file():
            raise BroadResearchContractError(f"Research-Codebestand fehlt: {name}")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@functools.lru_cache(maxsize=1)
def broad_research_feature_contract_fingerprint() -> str:
    """Fingerprint versions and fixed thresholds without using any outcome."""
    return _fingerprint(
        {
            "candidate_version": BROAD_RESEARCH_CANDIDATE_VERSION,
            "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
            "split_version": BROAD_RESEARCH_SPLIT_VERSION,
            "indicator_source": "swing_walk_forward._prepare_historical_indicators",
            "market_phase_source": "swing_walk_forward._technical_scores",
            "minimum_history_rows": MINIMUM_HISTORY_ROWS,
            "future_sessions": FUTURE_SESSIONS,
            "candidate_cooldown_sessions": CANDIDATE_COOLDOWN_SESSIONS,
            "pivot_window": PIVOT_WINDOW,
            "pullback_impulse_lookback": PULLBACK_IMPULSE_LOOKBACK,
            "pullback_min_impulse_pct": PULLBACK_MIN_IMPULSE_PCT,
            "pullback_max_duration": PULLBACK_MAX_DURATION,
            "pullback_depth_range": PULLBACK_DEPTH_RANGE,
            "breakout_lookback": BREAKOUT_LOOKBACK,
            "breakout_proximity_atr": BREAKOUT_PROXIMITY_ATR,
            "feature_directions": ["long", "short"],
            "candidate_direction": "long",
            "short_strategy_enabled": False,
            "shared_context_version": BROAD_CONTEXT_VERSION,
            "benchmark_mapping_version": BROAD_BENCHMARK_MAPPING_VERSION,
            "breadth_version": BROAD_BREADTH_VERSION,
            "first_pass_feature_scope_frozen": True,
            "additional_feature_expansion_before_evaluation_allowed": False,
            "direction_neutral_label_horizons": [5, 10, 20, 25],
            "code_fingerprint": broad_research_code_fingerprint(),
        }
    )


def _canonical_json(payload: object) -> str:
    return json.dumps(
        _clean(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    return value


def _number(value: object) -> float | None:
    return value_or_none(value)


def broad_research_split(signal_day: object) -> str:
    """Use the existing campaign's fixed chronological split boundaries."""
    day = pd.Timestamp(signal_day).date()
    if day < pd.Timestamp("2010-01-01").date():
        return "outside_contract"
    if day <= pd.Timestamp("2012-12-31").date():
        return "development"
    if day <= pd.Timestamp("2014-12-31").date():
        return "validation"
    if day < pd.Timestamp("2016-01-01").date():
        return "holdout"
    if day <= pd.Timestamp("2021-12-31").date():
        return "development"
    if day <= pd.Timestamp("2023-12-31").date():
        return "validation"
    return "holdout"


def _connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_broad_research_store(path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS broad_research_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS broad_research_candidates (
                candidate_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                setup_family TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('long', 'short')),
                research_split TEXT NOT NULL,
                issuer_id TEXT NOT NULL,
                listing_id TEXT NOT NULL,
                dependency_cluster TEXT NOT NULL,
                dataset_fingerprint TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                feature_json TEXT NOT NULL,
                feature_fingerprint TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS broad_candidates_symbol_day
                ON broad_research_candidates(symbol, signal_day);
            CREATE INDEX IF NOT EXISTS broad_candidates_split_setup
                ON broad_research_candidates(research_split, setup_family);
            CREATE TABLE IF NOT EXISTS broad_research_labels (
                candidate_id TEXT PRIMARY KEY REFERENCES broad_research_candidates(candidate_id),
                label_version TEXT NOT NULL,
                label_json TEXT NOT NULL,
                label_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS broad_research_counterfactuals (
                candidate_id TEXT PRIMARY KEY REFERENCES broad_research_candidates(candidate_id),
                experiment_version TEXT NOT NULL,
                experiment_json TEXT NOT NULL,
                experiment_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS broad_research_baseline_links (
                link_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL REFERENCES broad_research_candidates(candidate_id),
                walk_forward_case_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                relation TEXT NOT NULL,
                link_json TEXT NOT NULL,
                link_fingerprint TEXT NOT NULL,
                UNIQUE(candidate_id, walk_forward_case_id)
            );
            CREATE TABLE IF NOT EXISTS broad_research_asset_completions (
                completion_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                dataset_fingerprint TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                candidates INTEGER NOT NULL,
                labels INTEGER NOT NULL,
                completion_json TEXT NOT NULL,
                completion_fingerprint TEXT NOT NULL,
                UNIQUE(symbol, dataset_fingerprint, feature_version)
            );
            CREATE TABLE IF NOT EXISTS broad_research_manifests (
                manifest_id TEXT PRIMARY KEY,
                manifest_json TEXT NOT NULL,
                manifest_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS broad_research_breadth_manifests (
                breadth_id TEXT PRIMARY KEY,
                dataset_fingerprint TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                breadth_json TEXT NOT NULL,
                breadth_fingerprint TEXT NOT NULL,
                UNIQUE(dataset_fingerprint, feature_version)
            );
            CREATE TABLE IF NOT EXISTS broad_research_hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                hypothesis_json TEXT NOT NULL,
                hypothesis_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS broad_research_challengers (
                challenger_version TEXT PRIMARY KEY,
                challenger_json TEXT NOT NULL,
                challenger_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS broad_research_challenger_trades (
                trade_id TEXT PRIMARY KEY,
                challenger_version TEXT NOT NULL REFERENCES broad_research_challengers(challenger_version),
                candidate_id TEXT NOT NULL REFERENCES broad_research_candidates(candidate_id),
                research_split TEXT NOT NULL,
                trade_json TEXT NOT NULL,
                trade_fingerprint TEXT NOT NULL,
                UNIQUE(challenger_version, candidate_id)
            );
            CREATE TABLE IF NOT EXISTS broad_research_challenger_rescan_completions (
                completion_id TEXT PRIMARY KEY,
                challenger_version TEXT NOT NULL REFERENCES broad_research_challengers(challenger_version),
                symbol TEXT NOT NULL,
                research_split TEXT NOT NULL,
                completion_json TEXT NOT NULL,
                completion_fingerprint TEXT NOT NULL,
                UNIQUE(challenger_version, symbol, research_split)
            );
            CREATE TABLE IF NOT EXISTS broad_research_challenger_reviews (
                review_id TEXT PRIMARY KEY,
                challenger_version TEXT NOT NULL REFERENCES broad_research_challengers(challenger_version),
                research_stage TEXT NOT NULL,
                decision TEXT NOT NULL,
                review_json TEXT NOT NULL,
                review_fingerprint TEXT NOT NULL,
                UNIQUE(challenger_version, research_stage)
            );
            """
        )
        for table in (
            "broad_research_candidates",
            "broad_research_labels",
            "broad_research_counterfactuals",
            "broad_research_baseline_links",
            "broad_research_asset_completions",
            "broad_research_manifests",
            "broad_research_breadth_manifests",
            "broad_research_hypotheses",
            "broad_research_challengers",
            "broad_research_challenger_trades",
            "broad_research_challenger_rescan_completions",
            "broad_research_challenger_reviews",
        ):
            connection.executescript(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_no_update
                BEFORE UPDATE ON {table} BEGIN
                    SELECT RAISE(ABORT, '{table} is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                BEFORE DELETE ON {table} BEGIN
                    SELECT RAISE(ABORT, '{table} is append-only');
                END;
                """
            )
        existing = connection.execute(
            "SELECT value FROM broad_research_meta WHERE key = 'schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO broad_research_meta(key, value) VALUES('schema_version', ?)",
                (str(BROAD_RESEARCH_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) in {1, 2, 3}:
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(broad_research_candidates)"
                ).fetchall()
            }
            if "direction" not in columns:
                connection.execute(
                    "ALTER TABLE broad_research_candidates ADD COLUMN direction TEXT NOT NULL DEFAULT 'long' CHECK(direction IN ('long', 'short'))"
                )
            connection.execute(
                "UPDATE broad_research_meta SET value=? WHERE key='schema_version'",
                (str(BROAD_RESEARCH_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != BROAD_RESEARCH_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstützte Broad-Research-Datenbankversion.")


def record_broad_research_breadth(
    context: Mapping[str, Mapping[str, object]],
    *,
    dataset_fingerprint: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    """Persist one deterministic compressed breadth snapshot append-only."""
    initialize_broad_research_store(path)
    payload = {
        "breadth_version": BROAD_BREADTH_VERSION,
        "dataset_fingerprint": dataset_fingerprint,
        "universe_policy": "frozen_current_project_universe_with_historical_coverage_only",
        "survivorship_free": False,
        "rows": dict(context),
    }
    fingerprint = _fingerprint(payload)
    breadth_id = f"breadth-{fingerprint[:32]}"
    encoded = zlib.compress(_canonical_json(payload).encode("utf-8"), level=9)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            """SELECT breadth_fingerprint FROM broad_research_breadth_manifests
            WHERE dataset_fingerprint=? AND feature_version=?""",
            (dataset_fingerprint, BROAD_RESEARCH_FEATURE_VERSION),
        ).fetchone()
        if existing is not None:
            if str(existing["breadth_fingerprint"]) != fingerprint:
                raise BroadResearchContractError(
                    "Der unveränderliche Breadth-Kontext weicht beim Resume ab."
                )
            return {"already_present": True, "rows": len(context), "fingerprint": fingerprint}
        connection.execute(
            "INSERT INTO broad_research_breadth_manifests VALUES (?, ?, ?, ?, ?)",
            (breadth_id, dataset_fingerprint, BROAD_RESEARCH_FEATURE_VERSION, encoded, fingerprint),
        )
    return {"already_present": False, "rows": len(context), "fingerprint": fingerprint}


def load_broad_research_breadth(
    *,
    dataset_fingerprint: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, dict[str, object]]:
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        row = connection.execute(
            """SELECT breadth_json FROM broad_research_breadth_manifests
            WHERE dataset_fingerprint=? AND feature_version=?""",
            (dataset_fingerprint, BROAD_RESEARCH_FEATURE_VERSION),
        ).fetchone()
    if row is None:
        return {}
    raw = row["breadth_json"]
    decoded = zlib.decompress(bytes(raw)).decode("utf-8") if not isinstance(raw, str) else raw
    payload = json.loads(decoded)
    return {str(key): dict(value) for key, value in dict(payload.get("rows") or {}).items()}


def _pivot_structure(frame: pd.DataFrame) -> dict[str, object]:
    highs = frame["High"].to_numpy(dtype=float)
    lows = frame["Low"].to_numpy(dtype=float)
    confirmed_high_positions: list[int] = []
    confirmed_low_positions: list[int] = []
    high_class: dict[int, str] = {}
    low_class: dict[int, str] = {}
    previous_high: float | None = None
    previous_low: float | None = None
    window = PIVOT_WINDOW
    for pivot in range(window, len(frame) - window):
        high_window = highs[pivot - window : pivot + window + 1]
        low_window = lows[pivot - window : pivot + window + 1]
        if highs[pivot] == np.nanmax(high_window) and np.sum(high_window == highs[pivot]) == 1:
            confirmation = pivot + window
            confirmed_high_positions.append(confirmation)
            high_class[confirmation] = (
                "HH" if previous_high is not None and highs[pivot] > previous_high else "LH"
                if previous_high is not None
                else "first_high"
            )
            previous_high = float(highs[pivot])
        if lows[pivot] == np.nanmin(low_window) and np.sum(low_window == lows[pivot]) == 1:
            confirmation = pivot + window
            confirmed_low_positions.append(confirmation)
            low_class[confirmation] = (
                "HL" if previous_low is not None and lows[pivot] > previous_low else "LL"
                if previous_low is not None
                else "first_low"
            )
            previous_low = float(lows[pivot])
    return {
        "confirmed_high_positions": confirmed_high_positions,
        "confirmed_low_positions": confirmed_low_positions,
        "high_class": high_class,
        "low_class": low_class,
    }


def _last_confirmed_swing(
    frame: pd.DataFrame,
    structure: Mapping[str, object],
    position: int,
    kind: str,
) -> dict[str, object] | None:
    positions = list(structure[f"confirmed_{kind}_positions"])
    at = bisect.bisect_right(positions, position) - 1
    if at < 0:
        return None
    confirmation = positions[at]
    pivot = confirmation - PIVOT_WINDOW
    column = "High" if kind == "high" else "Low"
    return {
        "pivot_position": pivot,
        "confirmed_position": confirmation,
        "pivot_day": pd.Timestamp(frame.index[pivot]).date().isoformat(),
        "confirmed_day": pd.Timestamp(frame.index[confirmation]).date().isoformat(),
        "level": float(frame.iloc[pivot][column]),
        "classification": str(structure[f"{kind}_class"].get(confirmation) or "unknown"),
    }


def _impulse_pullback_geometry(frame: pd.DataFrame, position: int) -> dict[str, object]:
    start = max(0, position - PULLBACK_IMPULSE_LOOKBACK)
    end = position
    history = frame.iloc[start:end]
    if len(history) < 10:
        return {"status": "insufficient_history"}
    highs = history["High"].to_numpy(dtype=float)
    high_relative = int(np.nanargmax(highs))
    high_position = start + high_relative
    before_high = frame.iloc[start : high_position + 1]
    if before_high.empty:
        return {"status": "no_impulse"}
    low_relative = int(np.nanargmin(before_high["Low"].to_numpy(dtype=float)))
    low_position = start + low_relative
    if high_position <= low_position or high_position >= position:
        return {"status": "no_completed_impulse"}
    low_value = float(frame.iloc[low_position]["Low"])
    high_value = float(frame.iloc[high_position]["High"])
    close = float(frame.iloc[position]["Close"])
    impulse_range = high_value - low_value
    if low_value <= 0 or impulse_range <= 0:
        return {"status": "invalid_geometry"}
    pullback_slice = frame.iloc[high_position + 1 : position + 1]
    bearish = (pullback_slice["Close"] < pullback_slice["Open"]).tolist()
    longest = current = 0
    for is_bearish in bearish:
        current = current + 1 if is_bearish else 0
        longest = max(longest, current)
    atr = _number(frame.iloc[position].get("ATR_14"))
    pullback_distance = high_value - close
    duration = position - high_position
    return {
        "status": "available",
        "impulse_low": low_value,
        "impulse_low_day": pd.Timestamp(frame.index[low_position]).date().isoformat(),
        "impulse_high": high_value,
        "impulse_high_day": pd.Timestamp(frame.index[high_position]).date().isoformat(),
        "impulse_strength_pct": impulse_range / low_value * 100,
        "impulse_strength_atr": impulse_range / atr if atr and atr > 0 else None,
        "impulse_duration_sessions": high_position - low_position,
        "pullback_depth": pullback_distance / impulse_range,
        "pullback_duration_sessions": duration,
        "bearish_candles": int(sum(bearish)),
        "longest_bearish_streak": longest,
        "pullback_speed_atr_per_session": (
            pullback_distance / atr / duration if atr and atr > 0 and duration > 0 else None
        ),
        "pullback_low": float(pullback_slice["Low"].min()) if not pullback_slice.empty else None,
    }


def _all_impulse_pullback_geometries(frame: pd.DataFrame) -> list[dict[str, object]]:
    opens = frame["Open"].to_numpy(dtype=float)
    highs = frame["High"].to_numpy(dtype=float)
    lows = frame["Low"].to_numpy(dtype=float)
    closes = frame["Close"].to_numpy(dtype=float)
    atrs = frame["ATR_14"].to_numpy(dtype=float)
    index = pd.DatetimeIndex(frame.index)
    output: list[dict[str, object]] = []
    for position in range(len(frame)):
        start = max(0, position - PULLBACK_IMPULSE_LOOKBACK)
        if position - start < 10:
            output.append({"status": "insufficient_history"})
            continue
        high_position = start + int(np.nanargmax(highs[start:position]))
        if high_position < start:
            output.append({"status": "no_impulse"})
            continue
        low_position = start + int(np.nanargmin(lows[start : high_position + 1]))
        if high_position <= low_position or high_position >= position:
            output.append({"status": "no_completed_impulse"})
            continue
        low_value = float(lows[low_position])
        high_value = float(highs[high_position])
        impulse_range = high_value - low_value
        if low_value <= 0 or impulse_range <= 0:
            output.append({"status": "invalid_geometry"})
            continue
        bearish = closes[high_position + 1 : position + 1] < opens[high_position + 1 : position + 1]
        longest = current = 0
        for is_bearish in bearish:
            current = current + 1 if bool(is_bearish) else 0
            longest = max(longest, current)
        atr = float(atrs[position]) if math.isfinite(float(atrs[position])) else None
        pullback_distance = high_value - float(closes[position])
        duration = position - high_position
        output.append(
            {
                "status": "available",
                "impulse_low": low_value,
                "impulse_low_day": index[low_position].date().isoformat(),
                "impulse_high": high_value,
                "impulse_high_day": index[high_position].date().isoformat(),
                "impulse_strength_pct": impulse_range / low_value * 100,
                "impulse_strength_atr": impulse_range / atr if atr and atr > 0 else None,
                "impulse_duration_sessions": high_position - low_position,
                "pullback_depth": pullback_distance / impulse_range,
                "pullback_duration_sessions": duration,
                "bearish_candles": int(np.sum(bearish)),
                "longest_bearish_streak": longest,
                "pullback_speed_atr_per_session": (
                    pullback_distance / atr / duration if atr and atr > 0 and duration > 0 else None
                ),
                "pullback_low": float(np.min(lows[high_position + 1 : position + 1])),
            }
        )
    return output


def _down_impulse_rally_geometry(frame: pd.DataFrame, position: int) -> dict[str, object]:
    """Mirror the objective impulse geometry using only bars through ``position``."""
    start = max(0, position - PULLBACK_IMPULSE_LOOKBACK)
    history = frame.iloc[start:position]
    if len(history) < 10:
        return {"status": "insufficient_history"}
    low_position = start + int(np.nanargmin(history["Low"].to_numpy(dtype=float)))
    before_low = frame.iloc[start : low_position + 1]
    if before_low.empty:
        return {"status": "no_impulse"}
    high_position = start + int(np.nanargmax(before_low["High"].to_numpy(dtype=float)))
    if low_position <= high_position or low_position >= position:
        return {"status": "no_completed_down_impulse"}
    high_value = float(frame.iloc[high_position]["High"])
    low_value = float(frame.iloc[low_position]["Low"])
    close = float(frame.iloc[position]["Close"])
    impulse_range = high_value - low_value
    if high_value <= 0 or impulse_range <= 0:
        return {"status": "invalid_geometry"}
    rally = frame.iloc[low_position + 1 : position + 1]
    bullish = (rally["Close"] > rally["Open"]).tolist()
    longest = current = 0
    for is_bullish in bullish:
        current = current + 1 if is_bullish else 0
        longest = max(longest, current)
    atr = _number(frame.iloc[position].get("ATR_14"))
    rally_distance = close - low_value
    duration = position - low_position
    return {
        "status": "available",
        "impulse_high": high_value,
        "impulse_high_day": pd.Timestamp(frame.index[high_position]).date().isoformat(),
        "impulse_low": low_value,
        "impulse_low_day": pd.Timestamp(frame.index[low_position]).date().isoformat(),
        "down_impulse_strength_pct": impulse_range / high_value * 100,
        "down_impulse_strength_atr": impulse_range / atr if atr and atr > 0 else None,
        "down_impulse_duration_sessions": low_position - high_position,
        "rally_retracement_depth": rally_distance / impulse_range,
        "rally_duration_sessions": duration,
        "bullish_candles": int(sum(bullish)),
        "longest_bullish_streak": longest,
        "rally_speed_atr_per_session": (
            rally_distance / atr / duration if atr and atr > 0 and duration > 0 else None
        ),
        "rally_high": float(rally["High"].max()) if not rally.empty else None,
        "calculation_direction": "short_readiness_only",
        "outcome_used": False,
    }


def _all_down_impulse_rally_geometries(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Precompute the mirrored geometry once per asset without future-bar access."""
    opens = frame["Open"].to_numpy(dtype=float)
    highs = frame["High"].to_numpy(dtype=float)
    lows = frame["Low"].to_numpy(dtype=float)
    closes = frame["Close"].to_numpy(dtype=float)
    atrs = frame["ATR_14"].to_numpy(dtype=float)
    index = pd.DatetimeIndex(frame.index)
    output: list[dict[str, object]] = []
    for position in range(len(frame)):
        start = max(0, position - PULLBACK_IMPULSE_LOOKBACK)
        if position - start < 10:
            output.append({"status": "insufficient_history"})
            continue
        low_position = start + int(np.nanargmin(lows[start:position]))
        high_position = start + int(np.nanargmax(highs[start : low_position + 1]))
        if low_position <= high_position or low_position >= position:
            output.append({"status": "no_completed_down_impulse"})
            continue
        high_value = float(highs[high_position])
        low_value = float(lows[low_position])
        impulse_range = high_value - low_value
        if high_value <= 0 or impulse_range <= 0:
            output.append({"status": "invalid_geometry"})
            continue
        bullish = closes[low_position + 1 : position + 1] > opens[low_position + 1 : position + 1]
        longest = current = 0
        for is_bullish in bullish:
            current = current + 1 if bool(is_bullish) else 0
            longest = max(longest, current)
        atr = float(atrs[position]) if math.isfinite(float(atrs[position])) else None
        rally_distance = float(closes[position]) - low_value
        duration = position - low_position
        output.append(
            {
                "status": "available",
                "impulse_high": high_value,
                "impulse_high_day": index[high_position].date().isoformat(),
                "impulse_low": low_value,
                "impulse_low_day": index[low_position].date().isoformat(),
                "down_impulse_strength_pct": impulse_range / high_value * 100,
                "down_impulse_strength_atr": impulse_range / atr if atr and atr > 0 else None,
                "down_impulse_duration_sessions": low_position - high_position,
                "rally_retracement_depth": rally_distance / impulse_range,
                "rally_duration_sessions": duration,
                "bullish_candles": int(np.sum(bullish)),
                "longest_bullish_streak": longest,
                "rally_speed_atr_per_session": (
                    rally_distance / atr / duration if atr and atr > 0 and duration > 0 else None
                ),
                "rally_high": float(np.max(highs[low_position + 1 : position + 1])),
                "calculation_direction": "short_readiness_only",
                "outcome_used": False,
            }
        )
    return output


def directional_price_order_is_valid(
    *, entry: object, stop: object, target: object, direction: str
) -> bool:
    """Direction-neutral research contract; it does not create or execute an order."""
    entry_value, stop_value, target_value = map(_number, (entry, stop, target))
    if None in {entry_value, stop_value, target_value}:
        return False
    normalized = str(direction).strip().lower()
    if normalized == "long":
        return bool(stop_value < entry_value < target_value)
    if normalized == "short":
        return bool(target_value < entry_value < stop_value)
    return False


def _candidate_setups(
    frame: pd.DataFrame,
    position: int,
    geometry: Mapping[str, object],
) -> list[str]:
    row = frame.iloc[position]
    atr = _number(row.get("ATR_14"))
    setups: list[str] = []
    if geometry.get("status") == "available":
        depth = _number(geometry.get("pullback_depth"))
        strength = _number(geometry.get("impulse_strength_pct"))
        duration = int(geometry.get("pullback_duration_sessions") or 0)
        if (
            depth is not None
            and PULLBACK_DEPTH_RANGE[0] <= depth <= PULLBACK_DEPTH_RANGE[1]
            and strength is not None
            and strength >= PULLBACK_MIN_IMPULSE_PCT
            and 1 <= duration <= PULLBACK_MAX_DURATION
        ):
            setups.append("objective_pullback")
    if position >= BREAKOUT_LOOKBACK:
        prior = frame.iloc[position - BREAKOUT_LOOKBACK : position]
        breakout_level = float(prior["High"].max())
        high = float(row["High"])
        tolerance = (atr or 0.0) * BREAKOUT_PROXIMITY_ATR
        if breakout_level > 0 and high >= breakout_level - tolerance:
            setups.append("objective_breakout")
    return setups


def _opening_level(
    frame: pd.DataFrame,
    position: int,
    *,
    period: str,
    atr: float | None,
) -> dict[str, object]:
    index = pd.DatetimeIndex(frame.index)
    current = pd.Timestamp(index[position])
    if period == "daily":
        start = position
    elif period == "weekly":
        marker = current.to_period("W-FRI")
        start = position
        while start > 0 and pd.Timestamp(index[start - 1]).to_period("W-FRI") == marker:
            start -= 1
    elif period == "monthly":
        marker = current.to_period("M")
        start = position
        while start > 0 and pd.Timestamp(index[start - 1]).to_period("M") == marker:
            start -= 1
    elif period == "quarterly":
        marker = current.to_period("Q")
        start = position
        while start > 0 and pd.Timestamp(index[start - 1]).to_period("Q") == marker:
            start -= 1
    elif period == "yearly":
        marker = current.year
        start = position
        while start > 0 and pd.Timestamp(index[start - 1]).year == marker:
            start -= 1
    else:
        raise ValueError(f"Unbekanntes Opening-Level: {period}")
    level = float(frame.iloc[start]["Open"])
    current_row = frame.iloc[position]
    close = float(current_row["Close"])
    since = frame.iloc[start : position + 1]
    contacts = int(((since["Low"] <= level) & (since["High"] >= level)).sum())
    return {
        "level": level,
        "position": "above" if close > level else "below" if close < level else "at",
        "distance_atr": (close - level) / atr if atr and atr > 0 else None,
        "contact": bool(float(current_row["Low"]) <= level <= float(current_row["High"])),
        "retest_count": max(contacts - 1, 0),
        "retest_type": "repeated" if contacts >= 3 else "first" if contacts == 2 else "none",
        "age_sessions": position - start,
        "source_day": pd.Timestamp(index[start]).date().isoformat(),
    }


def _opening_level_context(frame: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    index = pd.DatetimeIndex(frame.index)
    opens = frame["Open"].to_numpy(dtype=float)
    highs = frame["High"].to_numpy(dtype=float)
    lows = frame["Low"].to_numpy(dtype=float)
    closes = frame["Close"].to_numpy(dtype=float)
    atrs = frame["ATR_14"].to_numpy(dtype=float)
    markers = {
        "daily": list(range(len(frame))),
        "weekly": [str(timestamp.to_period("W-FRI")) for timestamp in index],
        "monthly": [str(timestamp.to_period("M")) for timestamp in index],
        "quarterly": [str(timestamp.to_period("Q")) for timestamp in index],
        "yearly": [timestamp.year for timestamp in index],
    }
    context: dict[str, list[dict[str, object]]] = {}
    for period, values in markers.items():
        rows: list[dict[str, object]] = []
        start = 0
        contacts = 0
        previous_marker: object = object()
        for position, marker in enumerate(values):
            if position == 0 or marker != previous_marker:
                start = position
                contacts = 0
            level = float(opens[start])
            contact = bool(lows[position] <= level <= highs[position])
            contacts += int(contact)
            atr = float(atrs[position]) if math.isfinite(float(atrs[position])) else None
            rows.append(
                {
                    "level": level,
                    "position": "above" if closes[position] > level else "below" if closes[position] < level else "at",
                    "distance_atr": (closes[position] - level) / atr if atr and atr > 0 else None,
                    "contact": contact,
                    "retest_count": max(contacts - 1, 0),
                    "retest_type": "repeated" if contacts >= 3 else "first" if contacts == 2 else "none",
                    "age_sessions": position - start,
                    "source_day": index[start].date().isoformat(),
                }
            )
            previous_marker = marker
        context[period] = rows
    return context


def _seasonality_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    current = pd.Timestamp(frame.index[position])
    observations: dict[str, list[float]] = {"week": [], "month": [], "quarter": []}
    for year in sorted(set(pd.DatetimeIndex(frame.index[:position]).year)):
        year_mask = pd.DatetimeIndex(frame.index[:position]).year == year
        prior = frame.iloc[:position].loc[year_mask]
        if prior.empty:
            continue
        same_month = prior[pd.DatetimeIndex(prior.index).month == current.month]
        if len(same_month) >= 2 and pd.Timestamp(same_month.index[-1]) < current:
            observations["month"].append(float(same_month["Close"].iloc[-1] / same_month["Open"].iloc[0] - 1))
        quarter = (current.month - 1) // 3 + 1
        same_quarter = prior[((pd.DatetimeIndex(prior.index).month - 1) // 3 + 1) == quarter]
        if len(same_quarter) >= 2 and pd.Timestamp(same_quarter.index[-1]) < current:
            observations["quarter"].append(
                float(same_quarter["Close"].iloc[-1] / same_quarter["Open"].iloc[0] - 1)
            )
        iso = pd.DatetimeIndex(prior.index).isocalendar()
        same_week = prior[np.asarray(iso.week == current.isocalendar().week)]
        if len(same_week) >= 2 and pd.Timestamp(same_week.index[-1]) < current:
            observations["week"].append(float(same_week["Close"].iloc[-1] / same_week["Open"].iloc[0] - 1))

    def metrics(values: Sequence[float]) -> dict[str, object]:
        array = np.asarray(values, dtype=float)
        deviation = float(np.std(array, ddof=1)) if len(array) >= 2 else None
        average = float(np.mean(array)) if len(array) else None
        return {
            "observations": len(array),
            "win_rate_pct": float(np.mean(array > 0) * 100) if len(array) else None,
            "average_return": average,
            "risk_adjusted": average / deviation if average is not None and deviation and deviation > 0 else None,
        }

    return {
        "calendar_week": int(current.isocalendar().week),
        "month": current.month,
        "quarter": (current.month - 1) // 3 + 1,
        "month_start": current.day <= 7,
        "month_end": current.day >= 25,
        "quarter_start": current.month in {1, 4, 7, 10} and current.day <= 7,
        "quarter_end": current.month in {3, 6, 9, 12} and current.day >= 25,
        "historical_completed_periods_only": True,
        "week": metrics(observations["week"]),
        "month_history": metrics(observations["month"]),
        "quarter_history": metrics(observations["quarter"]),
        "free_calendar_search": False,
    }


def _seasonality_period_context(frame: pd.DataFrame) -> dict[str, dict[int, list[tuple[int, float]]]]:
    """Precompute completed-period returns; lookup still filters by the current cutoff."""
    index = pd.DatetimeIndex(frame.index)
    context: dict[str, dict[int, list[tuple[int, float]]]] = {
        "week": defaultdict(list),
        "month": defaultdict(list),
        "quarter": defaultdict(list),
    }
    markers = {
        "week": [(timestamp.year, int(timestamp.isocalendar().week)) for timestamp in index],
        "month": [(timestamp.year, timestamp.month) for timestamp in index],
        "quarter": [(timestamp.year, (timestamp.month - 1) // 3 + 1) for timestamp in index],
    }
    for kind, values in markers.items():
        start = 0
        while start < len(values):
            end = start
            while end + 1 < len(values) and values[end + 1] == values[start]:
                end += 1
            if end > start:
                key = int(values[start][1])
                period_return = float(frame.iloc[end]["Close"] / frame.iloc[start]["Open"] - 1)
                context[kind][key].append((end, period_return))
            start = end + 1
    return {kind: dict(groups) for kind, groups in context.items()}


def _seasonality_features_from_context(
    frame: pd.DataFrame,
    position: int,
    context: Mapping[str, Mapping[int, Sequence[tuple[int, float]]]],
) -> dict[str, object]:
    current = pd.Timestamp(frame.index[position])

    def metrics(values: Sequence[float]) -> dict[str, object]:
        array = np.asarray(values, dtype=float)
        deviation = float(np.std(array, ddof=1)) if len(array) >= 2 else None
        average = float(np.mean(array)) if len(array) else None
        return {
            "observations": len(array),
            "win_rate_pct": float(np.mean(array > 0) * 100) if len(array) else None,
            "average_return": average,
            "risk_adjusted": average / deviation if average is not None and deviation and deviation > 0 else None,
        }

    week_key = int(current.isocalendar().week)
    month_key = current.month
    quarter_key = (current.month - 1) // 3 + 1
    values = {
        kind: [result for end, result in context.get(kind, {}).get(key, ()) if end < position]
        for kind, key in (("week", week_key), ("month", month_key), ("quarter", quarter_key))
    }
    return {
        "calendar_week": week_key,
        "month": month_key,
        "quarter": quarter_key,
        "month_start": current.day <= 7,
        "month_end": current.day >= 25,
        "quarter_start": current.month in {1, 4, 7, 10} and current.day <= 7,
        "quarter_end": current.month in {3, 6, 9, 12} and current.day >= 25,
        "historical_completed_periods_only": True,
        "week": metrics(values["week"]),
        "month_history": metrics(values["month"]),
        "quarter_history": metrics(values["quarter"]),
        "free_calendar_search": False,
    }


def _technical_regime_context(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Vectorized equivalent of the existing `_technical_scores` phase/regime rules."""
    close = frame["Close"].astype(float)
    recent_high = close.rolling(120, min_periods=1).max()
    recent_low = close.rolling(120, min_periods=1).min()
    phases: list[str] = []
    regimes: list[str] = []
    for position, (_, row) in enumerate(frame.iterrows()):
        current = float(row["Close"])
        sma_50 = _number(row.get("SMA_50"))
        sma_200 = _number(row.get("SMA_200"))
        rsi = _number(row.get("RSI_14"))
        macd = _number(row.get("MACD"))
        signal = _number(row.get("MACD_Signal"))
        drawdown = (current - float(recent_high.iloc[position])) / float(recent_high.iloc[position])
        rebound = (current - float(recent_low.iloc[position])) / float(recent_low.iloc[position])
        range_width = (float(recent_high.iloc[position]) - float(recent_low.iloc[position])) / current
        macd_positive = macd is not None and signal is not None and macd > signal
        macd_negative = macd is not None and signal is not None and macd < signal
        uptrend = sma_50 is not None and current > sma_50 and (sma_200 is None or sma_50 > sma_200)
        downtrend = sma_50 is not None and current < sma_50 and (sma_200 is None or sma_50 < sma_200)
        if uptrend and drawdown <= -0.08:
            phase = "Korrektur innerhalb eines Aufwärtstrends"
        elif downtrend and (rsi is None or rsi < 45) and macd_negative:
            phase = "Bärenmarkt"
        elif uptrend and (rsi is None or rsi >= 45) and not macd_negative:
            phase = "Bullenmarkt"
        elif downtrend and rebound > 0.06 and rsi is not None and rsi >= 30 and not macd_negative:
            phase = "Bodenbildungsphase"
        elif range_width <= 0.16:
            phase = "Seitwärtsmarkt"
        else:
            phase = "Bodenbildungsphase" if macd_positive and rebound > 0.04 else "Seitwärtsmarkt"
        phases.append(phase)
        volatility = _number(row.get("Volatility"))
        regimes.append(
            "Nicht verfügbar" if volatility is None else "Hoch" if volatility >= 0.45 else "Mittel" if volatility >= 0.25 else "Niedrig"
        )
    return phases, regimes


def _cot_features(
    asset: Mapping[str, object],
    reports: Sequence[Mapping[str, object]],
    *,
    signal_at: str,
    mapping: Mapping[str, object],
) -> dict[str, object]:
    context = build_asset_cot_shadow_context(
        asset,
        reports,
        decision_at=signal_at,
        mapping=mapping,
        technical_direction="long",
    )
    base = dict(context.get("features") or {})
    categories = dict(base.get("categories") or {})
    decision = pd.Timestamp(signal_at)
    selected_market = str(base.get("market_code") or "")
    selected_type = str(base.get("report_type") or "")
    eligible_reports = []
    for report in reports:
        available_at = report.get("available_at")
        if (
            report.get("pit_eligible") is not True
            or not available_at
            or str(report.get("market_code") or "") != selected_market
            or str(report.get("report_type") or "") != selected_type
        ):
            continue
        available = pd.Timestamp(available_at)
        if available.tzinfo is None:
            available = available.tz_localize("UTC")
        else:
            available = available.tz_convert("UTC")
        if available <= decision:
            eligible_reports.append(dict(report))
    by_report: dict[str, dict] = {}
    for report in sorted(eligible_reports, key=lambda item: str(item.get("available_at") or "")):
        by_report[str(report.get("report_key") or report.get("report_id"))] = report
    history_52w = sorted(
        by_report.values(), key=lambda item: (str(item.get("report_date") or ""), str(item.get("available_at") or ""))
    )[-52:]

    def percentile(values: Sequence[float], current: float) -> float | None:
        return 100.0 * sum(value <= current for value in values) / len(values) if values else None

    def z_score(values: Sequence[float], current: float) -> float | None:
        if len(values) < 2:
            return None
        deviation = float(np.std(np.asarray(values, dtype=float), ddof=0))
        return 0.0 if deviation == 0 else (current - float(np.mean(values))) / deviation

    enriched: dict[str, dict] = {}
    open_interest = _number(base.get("open_interest"))
    for name, raw in categories.items():
        values = dict(raw or {})
        net = _number(values.get("net_position"))
        net_history = [
            float(report["categories"][name]["net"])
            for report in history_52w
            if name in dict(report.get("categories") or {})
        ]
        ratio_history = [
            float(report["categories"][name]["net"]) / float(report["open_interest"])
            for report in history_52w
            if name in dict(report.get("categories") or {})
            and _number(report.get("open_interest")) not in {None, 0}
        ]
        ratio = net / open_interest if net is not None and open_interest else None
        current_z = z_score(net_history, net) if net is not None else None
        prior_z = (
            z_score(net_history[:-1], net_history[-2])
            if len(net_history) >= 3
            else None
        )
        enriched[str(name)] = {
            **values,
            "net_position_open_interest": ratio,
            "net_percentile_52w": percentile(net_history, net) if net is not None else None,
            "net_z_score_52w": current_z,
            "net_oi_percentile_52w": percentile(ratio_history, ratio) if ratio is not None else None,
            "net_oi_z_score_52w": z_score(ratio_history, ratio) if ratio is not None else None,
            "history_reports_52w": len(net_history),
            "extreme_52w": bool(
                current_z is not None and abs(current_z) >= 2.0
                or net is not None and percentile(net_history, net) in {0.0, 100.0}
            ),
            "reversal_from_prior_extreme": bool(
                prior_z is not None and current_z is not None and abs(prior_z) >= 2.0 and abs(current_z) < abs(prior_z)
            ),
            "normalization_52w_available": len(net_history) >= 52,
        }
    participant_spreads = []
    category_names = sorted(enriched)
    for left_index, left in enumerate(category_names):
        for right in category_names[left_index + 1 :]:
            left_net = _number(enriched[left].get("net_position"))
            right_net = _number(enriched[right].get("net_position"))
            participant_spreads.append(
                {
                    "left": left,
                    "right": right,
                    "net_spread": left_net - right_net if left_net is not None and right_net is not None else None,
                }
            )
    return {
        "link_version": BROAD_RESEARCH_COT_LINK_VERSION,
        "base_feature_version": base.get("feature_version") or COT_FEATURE_VERSION,
        "status": base.get("status") or "unavailable_point_in_time",
        "mapping": context.get("mapping"),
        "report_id": base.get("report_id"),
        "report_date": base.get("report_date"),
        "available_at": base.get("available_at"),
        "market_code": base.get("market_code"),
        "report_type": base.get("report_type"),
        "open_interest": open_interest,
        "categories": enriched,
        "participant_spreads": participant_spreads,
        "divergences": base.get("divergences") or [],
        "future_reports_used": 0,
        "guessed_mapping": False,
        "shadow_only": True,
    }


def build_broad_research_feature(
    symbol: str,
    asset: Mapping[str, object],
    frame: pd.DataFrame,
    position: int,
    setup_family: str,
    *,
    dataset_fingerprint: str,
    structure: Mapping[str, object] | None = None,
    cot_reports: Sequence[Mapping[str, object]] = (),
    cot_mapping: Mapping[str, object] | None = None,
    cot_context: Mapping[str, object] | None = None,
    benchmark_histories: Mapping[str, pd.DataFrame] | None = None,
    breadth_context: Mapping[str, Mapping[str, object]] | None = None,
    precomputed: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create one deterministic feature row using bars no later than position."""
    if position < MINIMUM_HISTORY_ROWS - 1:
        raise BroadResearchContractError("Der Featurezeitpunkt besitzt zu wenig Historie.")
    prepared = frame if "ATR_14" in frame and "EMA_20" in frame else _prepare_historical_indicators(frame)
    signal_frame = prepared.iloc[max(0, position - 320) : position + 1]
    cached = dict(precomputed or {})
    if cached.get("market_phase") and cached.get("volatility_regime"):
        market_phase = str(cached["market_phase"])
        volatility_regime = str(cached["volatility_regime"])
    else:
        _, market_phase, _, _, volatility_regime = _technical_scores(signal_frame)
    row = prepared.iloc[position]
    prior = prepared.iloc[position - 1]
    atr = _number(row.get("ATR_14"))
    close = float(row["Close"])
    geometry = dict(cached.get("geometry") or _impulse_pullback_geometry(prepared, position))
    bearish_geometry = dict(
        cached.get("bearish_geometry") or _down_impulse_rally_geometry(prepared, position)
    )
    pivots = dict(structure or _pivot_structure(prepared))
    last_high = _last_confirmed_swing(prepared, pivots, position, "high")
    last_low = _last_confirmed_swing(prepared, pivots, position, "low")
    breakout_level = float(prepared.iloc[position - BREAKOUT_LOOKBACK : position]["High"].max())
    high_break = bool(last_high and float(row["High"]) > float(last_high["level"]))
    close_break = bool(last_high and close > float(last_high["level"]))
    bos_excess = (
        (close - float(last_high["level"])) / atr
        if close_break and atr and atr > 0 and last_high
        else None
    )
    low_break = bool(last_low and float(row["Low"]) < float(last_low["level"]))
    bearish_close_break = bool(last_low and close < float(last_low["level"]))
    bearish_bos_excess = (
        (float(last_low["level"]) - close) / atr
        if bearish_close_break and atr and atr > 0 and last_low
        else None
    )
    signal_at = datetime.combine(
        pd.Timestamp(prepared.index[position]).date(), time(23, 59), tzinfo=timezone.utc
    ).isoformat()
    identity = derive_swing_research_identity(asset)
    pullback_depth = _number(geometry.get("pullback_depth"))
    fib = {
        "retracement_depth": pullback_depth,
        "distance_to_0618": pullback_depth - 0.618 if pullback_depth is not None else None,
        "inside_0618_0786": bool(pullback_depth is not None and 0.618 <= pullback_depth <= 0.786),
        "comparison_zone": (
            "fib_0618_0786" if pullback_depth is not None and 0.618 <= pullback_depth <= 0.786
            else "equal_width_lower_0450_0618" if pullback_depth is not None and 0.450 <= pullback_depth < 0.618
            else "equal_width_upper_0786_0954" if pullback_depth is not None and 0.786 < pullback_depth <= 0.954
            else "outside_predeclared_zones"
        ),
        "distance_to_0618_atr": (
            (close - (float(geometry["impulse_high"]) - 0.618 * (float(geometry["impulse_high"]) - float(geometry["impulse_low"])))) / atr
            if geometry.get("status") == "available" and atr and atr > 0
            else None
        ),
        "key_level_distance_atr": (
            (close - float(last_low["level"])) / atr if last_low and atr and atr > 0 else None
        ),
        "extensions_tested": False,
    }
    bearish_depth = _number(bearish_geometry.get("rally_retracement_depth"))
    bearish_fib = {
        "retracement_depth": bearish_depth,
        "distance_to_0618": bearish_depth - 0.618 if bearish_depth is not None else None,
        "inside_0618_0786": bool(
            bearish_depth is not None and 0.618 <= bearish_depth <= 0.786
        ),
        "distance_to_0618_atr": (
            (
                close
                - (
                    float(bearish_geometry["impulse_low"])
                    + 0.618
                    * (
                        float(bearish_geometry["impulse_high"])
                        - float(bearish_geometry["impulse_low"])
                    )
                )
            )
            / atr
            if bearish_geometry.get("status") == "available" and atr and atr > 0
            else None
        ),
        "extensions_tested": False,
        "short_rule_derived": False,
    }
    opening_levels = dict(cached.get("opening_levels") or {
        period: _opening_level(prepared, position, period=period, atr=atr)
        for period in ("daily", "weekly", "monthly", "quarterly", "yearly")
    })
    cot = dict(cot_context or _cot_features(
        asset,
        cot_reports,
        signal_at=signal_at,
        mapping=dict(cot_mapping or load_cot_market_mapping()),
    ))
    shared = dict(
        cached.get("shared_features")
        or build_shared_asset_features(
            prepared,
            position,
            asset=asset,
            benchmark_histories=dict(benchmark_histories or {}),
        )
    )
    shared["candle_quality"]["range_and_volume_expansion"] = shared[
        "volatility_structure"
    ]["range_and_volume_expansion"]
    signal_day = pd.Timestamp(prepared.index[position]).date().isoformat()
    historical_breadth = breadth_feature_for_asset(
        dict(breadth_context or {}), day=signal_day, asset=asset
    )
    feature = {
        "candidate_version": BROAD_RESEARCH_CANDIDATE_VERSION,
        "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
        "code_fingerprint": broad_research_code_fingerprint(),
        "feature_contract_fingerprint": broad_research_feature_contract_fingerprint(),
        "dataset_fingerprint": dataset_fingerprint,
        "feature_at": signal_at,
        "causal_cutoff": "completed_signal_bar",
        "future_bars_used": 0,
        "indicator_source": "swing_walk_forward._prepare_historical_indicators",
        "market_phase_source": "swing_walk_forward._technical_scores",
        "identity": identity,
        "asset": {
            "ticker": symbol,
            "name": asset.get("name"),
            "asset_type": asset.get("asset_type"),
            "region": asset.get("region"),
            "category": asset.get("category"),
            "liquidity_class": asset.get("liquidity_class"),
        },
        "setup_family": setup_family,
        "research_direction": "long",
        "feature_directions": ["long", "short"],
        "short_strategy_enabled": False,
        "data_quality": data_quality_score(signal_frame),
        "technical": {
            "close": close,
            "rsi_14": _number(row.get("RSI_14")),
            "ema_20": _number(row.get("EMA_20")),
            "ema_50": _number(row.get("EMA_50")),
            "close_relative_to_ema20": close / float(row["EMA_20"]) if _number(row.get("EMA_20")) else None,
            "close_relative_to_ema50": close / float(row["EMA_50"]) if _number(row.get("EMA_50")) else None,
            "ema20_relative_to_ema50": float(row["EMA_20"]) / float(row["EMA_50"]) if _number(row.get("EMA_20")) and _number(row.get("EMA_50")) else None,
            "close_below_ema20": bool(
                _number(row.get("EMA_20")) is not None and close < float(row["EMA_20"])
            ),
            "close_below_ema50": bool(
                _number(row.get("EMA_50")) is not None and close < float(row["EMA_50"])
            ),
            "ema20_below_ema50": bool(
                _number(row.get("EMA_20")) is not None
                and _number(row.get("EMA_50")) is not None
                and float(row["EMA_20"]) < float(row["EMA_50"])
            ),
            "atr_14": atr,
            "volatility": _number(row.get("Volatility")),
            "volume": _number(row.get("Volume")),
            "relative_volume": (
                float(row["Volume"]) / float(row["Volume_SMA_20"])
                if _number(row.get("Volume")) is not None and _number(row.get("Volume_SMA_20")) not in {None, 0}
                else None
            ),
            "market_phase": market_phase,
            "volatility_regime": volatility_regime,
        },
        "pullback": {
            **geometry,
            "buyer_confirmation_close_above_prior_high": close > float(prior["High"]),
            "distance_to_last_support_atr": (
                (close - float(last_low["level"])) / atr if last_low and atr and atr > 0 else None
            ),
            "distance_to_last_resistance_atr": (
                (float(last_high["level"]) - close) / atr if last_high and atr and atr > 0 else None
            ),
        },
        "fibonacci": fib,
        "short_readiness": {
            "status": "features_only",
            "strategy_created": False,
            "signal_created": False,
            "challenger_created": False,
            "production_eligible": False,
            "down_impulse_and_rally": {
                **bearish_geometry,
                "bearish_confirmation_close_below_prior_low": close < float(prior["Low"]),
                "confirmation_at": signal_at if close < float(prior["Low"]) else None,
            },
            "fibonacci": bearish_fib,
            "market_structure": {
                "lower_high": bool(last_high and last_high.get("classification") == "LH"),
                "lower_low": bool(last_low and last_low.get("classification") == "LL"),
                "last_swing_high": last_high,
                "last_swing_low": last_low,
                "bearish_bos": low_break or bearish_close_break,
                "high_low_break": low_break,
                "close_break": bearish_close_break,
                "close_break_excess_atr": bearish_bos_excess,
                "breakdown_level_20": float(
                    prepared.iloc[position - BREAKOUT_LOOKBACK : position]["Low"].min()
                ),
                "confirmation_at": signal_at if low_break or bearish_close_break else None,
                "future_bars_used": 0,
            },
            "ema_context": {
                "close_below_ema20": bool(
                    _number(row.get("EMA_20")) is not None and close < float(row["EMA_20"])
                ),
                "close_below_ema50": bool(
                    _number(row.get("EMA_50")) is not None and close < float(row["EMA_50"])
                ),
                "ema20_below_ema50": bool(
                    _number(row.get("EMA_20")) is not None
                    and _number(row.get("EMA_50")) is not None
                    and float(row["EMA_20"]) < float(row["EMA_50"])
                ),
                "close_relative_to_ema20": close / float(row["EMA_20"])
                if _number(row.get("EMA_20"))
                else None,
                "close_relative_to_ema50": close / float(row["EMA_50"])
                if _number(row.get("EMA_50"))
                else None,
                "ema20_relative_to_ema50": float(row["EMA_20"]) / float(row["EMA_50"])
                if _number(row.get("EMA_20")) and _number(row.get("EMA_50"))
                else None,
                "shared_indicator_source": "technical",
            },
            "shared_feature_references": {
                "rsi_atr_volume_volatility_market_phase": "technical",
                "opening_levels": "opening_levels",
                "seasonality": "seasonality",
                "cot": "cot",
            },
            "short_execution_data": {
                "borrow_availability": None,
                "borrow_fee": None,
                "financing_cost": None,
                "broker_short_fee": None,
                "real_short_spread": None,
                "status": "not_collected_not_approximated",
            },
        },
        "market_structure": {
            "last_swing_high": last_high,
            "last_swing_low": last_low,
            "current_high_low_classification": [
                item for item in (
                    last_high.get("classification") if last_high else None,
                    last_low.get("classification") if last_low else None,
                ) if item
            ],
            "high_break": high_break,
            "close_break": close_break,
            "close_break_excess_atr": bos_excess,
            "breakout_level_20": breakout_level,
            "confirmation_at": signal_at if high_break or close_break else None,
            "earliest_trade_day": None,
            "earliest_trade_policy": "first_observed_trading_session_after_confirmation",
            "earliest_trade_day_is_future_label": True,
            "retroactive_entry_allowed": False,
        },
        "opening_levels": opening_levels,
        "seasonality": dict(
            cached.get("seasonality") or _seasonality_features(prepared, position)
        ),
        "cot": cot,
        "relative_strength": shared["relative_strength"],
        "trend_quality": shared["trend_quality"],
        "volatility_structure": shared["volatility_structure"],
        "candle_quality": shared["candle_quality"],
        "historical_extremes": shared["historical_extremes"],
        "consolidation": shared["consolidation"],
        "gap_risk": shared["gap_risk"],
        "historical_breadth": historical_breadth,
        "first_pass_feature_scope": {
            "status": "frozen_before_first_broad_pass",
            "automatic_optimization": False,
            "production_rules_changed": False,
            "correlated_features_are_independent_evidence": False,
        },
        "volume_profile": {
            "status": "unavailable_daily_ohlcv_insufficient",
            "poc": None,
            "vah": None,
            "val": None,
            "approximated": False,
            "required_resolution": "belastbare Intraday-Preis-Volumen-Verteilung je Preisniveau",
            "additional_download_forced": False,
        },
        "labels_present_in_features": False,
        "automatic_rule_change": False,
        "production_activation_allowed": False,
    }
    feature["feature_missing"] = sorted(_missing_paths(feature))
    feature["feature_fingerprint"] = _fingerprint(feature)
    return feature


def _missing_paths(value: object, prefix: str = "") -> list[str]:
    missing: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if item is None:
                missing.append(path)
            elif isinstance(item, Mapping):
                missing.extend(_missing_paths(item, path))
    return missing


def _cost_bps(asset_type: str) -> float:
    contract = swing_execution_cost_contract(asset_type)
    return float(
        contract["spread_bps_one_way"]
        + contract["slippage_bps_one_way"]
        + contract["fee_bps_one_way"]
    )


def _exit_after_costs(price: float, bps: float) -> float:
    return price * (1 - bps / 10_000)


def _simulate_fixed_target(
    future: pd.DataFrame,
    *,
    entry: float,
    stop: float,
    target_r: float,
    cost_bps: float,
) -> dict[str, object]:
    risk = entry - stop
    if risk <= 0:
        return {"status": "invalid_stop"}
    target = entry + target_r * risk
    opens = future["Open"].to_numpy(dtype=float)
    lows = future["Low"].to_numpy(dtype=float)
    highs = future["High"].to_numpy(dtype=float)
    for index, (open_price, low, high) in enumerate(zip(opens, lows, highs)):
        offset = index + 1
        if open_price <= stop:
            exit_price, status = open_price, "gap_stop"
        elif low <= stop:
            exit_price, status = stop, "stop"
        elif open_price >= target:
            exit_price, status = open_price, "gap_target"
        elif high >= target:
            exit_price, status = target, "target"
        else:
            continue
        result_r = (_exit_after_costs(exit_price, cost_bps) - entry) / risk
        return {"status": status, "sessions": offset, "exit": exit_price, "result_r": result_r}
    exit_price = float(future.iloc[-1]["Close"])
    return {
        "status": "horizon_exit",
        "sessions": len(future),
        "exit": exit_price,
        "result_r": (_exit_after_costs(exit_price, cost_bps) - entry) / risk,
    }


def _simulate_breakeven_or_partial(
    future: pd.DataFrame,
    *,
    entry: float,
    stop: float,
    cost_bps: float,
    partial: bool,
) -> dict[str, object]:
    risk = entry - stop
    if risk <= 0:
        return {"status": "invalid_stop"}
    target_1 = entry + risk
    target_2 = entry + 2 * risk
    active_stop = stop
    move_to_break_even_next_bar = False
    partial_realized: float | None = None
    opens = future["Open"].to_numpy(dtype=float)
    lows = future["Low"].to_numpy(dtype=float)
    highs = future["High"].to_numpy(dtype=float)
    for index, (open_price, low, high) in enumerate(zip(opens, lows, highs)):
        offset = index + 1
        if move_to_break_even_next_bar:
            active_stop = entry
            move_to_break_even_next_bar = False
        if open_price <= active_stop:
            raw_exit, status = open_price, "gap_stop"
        elif low <= active_stop:
            raw_exit, status = active_stop, "stop"
        else:
            raw_exit = None
            status = ""
        if raw_exit is not None:
            remaining_r = (_exit_after_costs(raw_exit, cost_bps) - entry) / risk
            result = (
                0.5 * float(partial_realized) + 0.5 * remaining_r
                if partial_realized is not None
                else remaining_r
            )
            return {"status": status, "sessions": offset, "result_r": result}
        if partial and partial_realized is None and high >= target_1:
            partial_realized = (_exit_after_costs(target_1, cost_bps) - entry) / risk
            move_to_break_even_next_bar = True
        elif not partial and high >= target_1 and active_stop < entry:
            move_to_break_even_next_bar = True
        if high >= target_2:
            target_r = (_exit_after_costs(target_2, cost_bps) - entry) / risk
            result = 0.5 * float(partial_realized) + 0.5 * target_r if partial_realized is not None else target_r
            return {"status": "target_2", "sessions": offset, "result_r": result}
    raw_exit = float(future.iloc[-1]["Close"])
    remaining_r = (_exit_after_costs(raw_exit, cost_bps) - entry) / risk
    result = 0.5 * float(partial_realized) + 0.5 * remaining_r if partial_realized is not None else remaining_r
    return {"status": "horizon_exit", "sessions": len(future), "result_r": result}


def _direction_neutral_future_movement(
    future: pd.DataFrame,
    *,
    reference_price: float,
    signal_atr: float | None,
) -> dict[str, object]:
    """Describe future raw movement without assigning a long or short trade result."""
    if future.empty or reference_price <= 0:
        return {"status": "future_not_available"}
    highs = future["High"].to_numpy(dtype=float)
    lows = future["Low"].to_numpy(dtype=float)
    closes = future["Close"].to_numpy(dtype=float)
    maximum_high = float(np.max(highs))
    minimum_low = float(np.min(lows))
    upward = max(maximum_high - reference_price, 0.0)
    downward = max(reference_price - minimum_low, 0.0)
    return {
        "status": "evaluated",
        "sessions_observed": len(future),
        "reference": "completed_signal_bar_close",
        "reference_price": reference_price,
        "forward_return": float(closes[-1]) / reference_price - 1,
        "future_maximum_high": maximum_high,
        "future_minimum_low": minimum_low,
        "maximum_high_return_pct": (maximum_high / reference_price - 1) * 100,
        "minimum_low_return_pct": (minimum_low / reference_price - 1) * 100,
        "maximum_upward_move_pct": upward / reference_price * 100,
        "maximum_downward_move_pct": downward / reference_price * 100,
        "maximum_upward_move_atr": upward / signal_atr
        if signal_atr and signal_atr > 0
        else None,
        "maximum_downward_move_atr": downward / signal_atr
        if signal_atr and signal_atr > 0
        else None,
        "sessions_to_future_high": int(np.argmax(highs)) + 1,
        "sessions_to_future_low": int(np.argmin(lows)) + 1,
        "long_mfe_derivable": True,
        "long_mae_derivable": True,
        "short_mfe_derivable": True,
        "short_mae_derivable": True,
        "trade_direction_assigned": False,
    }


def build_broad_research_labels(
    frame: pd.DataFrame,
    position: int,
    feature: Mapping[str, object],
    *,
    asset_type: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Attach future-only labels after the feature payload has been finalized."""
    feature_fingerprint = str(feature.get("feature_fingerprint") or "")
    if not feature_fingerprint or feature_fingerprint != _fingerprint(
        {key: value for key, value in feature.items() if key != "feature_fingerprint"}
    ):
        raise BroadResearchContractError("Labels benötigen zuerst ein unverändertes Feature-Artefakt.")
    future = frame.iloc[position + 1 : position + 1 + FUTURE_SESSIONS].copy()
    if future.empty:
        labels = {
            "label_version": BROAD_RESEARCH_LABEL_VERSION,
            "status": "future_not_available",
            "feature_fingerprint": feature_fingerprint,
        }
        experiments = {
            "experiment_version": BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
            "status": "future_not_available",
            "feature_fingerprint": feature_fingerprint,
        }
        labels["label_fingerprint"] = _fingerprint(labels)
        experiments["experiment_fingerprint"] = _fingerprint(experiments)
        return labels, experiments
    signal_close = float(frame.iloc[position]["Close"])
    raw_entry = float(future.iloc[0]["Open"])
    cost_bps = _cost_bps(asset_type)
    entry = raw_entry * (1 + cost_bps / 10_000)
    highs = future["High"].to_numpy(dtype=float)
    lows = future["Low"].to_numpy(dtype=float)
    closes = future["Close"].to_numpy(dtype=float)
    forward_returns = {
        f"{horizon}d": (float(closes[horizon - 1]) / signal_close - 1)
        if len(closes) >= horizon
        else None
        for horizon in (5, 10, 20, 25)
    }
    direction_neutral_horizons = {
        f"{horizon}d": (
            _direction_neutral_future_movement(
                future.iloc[:horizon],
                reference_price=signal_close,
                signal_atr=_number((feature.get("technical") or {}).get("atr_14")),
            )
            if len(future) >= horizon
            else {"status": "future_not_available", "sessions_observed": len(future)}
        )
        for horizon in (5, 10, 20, 25)
    }
    mfe_offset = int(np.argmax(highs)) + 1
    mae_offset = int(np.argmin(lows)) + 1
    gap_events = []
    prior_close = signal_close
    atr = _number((feature.get("technical") or {}).get("atr_14"))
    future_opens = future["Open"].to_numpy(dtype=float)
    future_closes = future["Close"].to_numpy(dtype=float)
    for index, (opening, closing) in enumerate(zip(future_opens, future_closes)):
        offset = index + 1
        gap_atr = (opening - prior_close) / atr if atr and atr > 0 else None
        if gap_atr is not None and abs(gap_atr) >= 1.0:
            gap_events.append({"sessions": offset, "gap_atr": gap_atr})
        prior_close = float(closing)
    labels = {
        "label_version": BROAD_RESEARCH_LABEL_VERSION,
        "status": "evaluated" if len(future) >= FUTURE_SESSIONS else "partially_evaluated",
        "feature_fingerprint": feature_fingerprint,
        "entry": {
            "policy": "next_session_open_after_completed_signal_bar",
            "entry_day": pd.Timestamp(future.index[0]).date().isoformat(),
            "raw": raw_entry,
            "after_costs": entry,
            "sessions_after_signal": 1,
            "retroactive_signal_close_entry": False,
            "cost_version": SWING_EXECUTION_COST_VERSION,
            "cost_bps_one_way": cost_bps,
        },
        "forward_returns": forward_returns,
        "direction_neutral_horizons": direction_neutral_horizons,
        "direction_neutral_raw_movement": _direction_neutral_future_movement(
            future,
            reference_price=signal_close,
            signal_atr=atr,
        ),
        "mfe_pct": (float(np.max(highs)) / entry - 1) * 100,
        "mae_pct": (float(np.min(lows)) / entry - 1) * 100,
        "time_to_mfe_sessions": mfe_offset,
        "time_to_mae_sessions": mae_offset,
        "time_to_exit_sessions": len(future),
        "gap_events": gap_events,
        "baseline_result": None,
        "baseline_result_status": "linkable_separately_not_used_for_selection",
        "labels_used_for_candidate_selection": False,
        "features_affected": False,
        "short_strategy_evaluated": False,
    }
    geometry = dict(feature.get("pullback") or {})
    stops: dict[str, float | None] = {
        "pullback_low": _number(geometry.get("pullback_low")),
        "pullback_low_atr_buffer": (
            float(geometry["pullback_low"]) - PULLBACK_ATR_BUFFER * atr
            if _number(geometry.get("pullback_low")) is not None and atr and atr > 0
            else None
        ),
        "atr_stop": entry - ATR_STOP_MULTIPLE * atr if atr and atr > 0 else None,
        "existing_structure_stop": None,
    }
    signal_frame = frame.iloc[max(0, position - 320) : position + 1]
    existing, _ = (
        _pullback_candidate(signal_frame, DEFAULT_SWING_THRESHOLDS)
        if str(feature.get("setup_family")) == "objective_pullback"
        else _breakout_candidate(signal_frame, DEFAULT_SWING_THRESHOLDS)
    )
    if existing:
        stops["existing_structure_stop"] = _number(existing.get("stop"))
    results: dict[str, dict] = {}
    for stop_name, stop in stops.items():
        if stop is None or not 0 < stop < entry:
            results[stop_name] = {"status": "unavailable_or_invalid", "stop": stop}
            continue
        variants = {
            f"fixed_{target:g}r": _simulate_fixed_target(
                future, entry=entry, stop=stop, target_r=target, cost_bps=cost_bps
            )
            for target in (1.0, 1.5, 2.0, 3.0)
        }
        variants["breakeven_after_1r_then_2r"] = _simulate_breakeven_or_partial(
            future, entry=entry, stop=stop, cost_bps=cost_bps, partial=False
        )
        variants["partial_1r_then_rest_2r"] = _simulate_breakeven_or_partial(
            future, entry=entry, stop=stop, cost_bps=cost_bps, partial=True
        )
        results[stop_name] = {"status": "evaluated", "stop": stop, "exits": variants}
    experiments = {
        "experiment_version": BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
        "feature_fingerprint": feature_fingerprint,
        "entry_after_costs": entry,
        "same_entry_all_variants": True,
        "cost_version": SWING_EXECUTION_COST_VERSION,
        "conservative_same_bar_order": "gap_then_stop_before_target",
        "future_information_in_parameters": False,
        "results": results,
        "features_affected": False,
        "automatic_strategy_change": False,
    }
    labels["label_fingerprint"] = _fingerprint(labels)
    experiments["experiment_fingerprint"] = _fingerprint(experiments)
    return labels, experiments


def build_asset_broad_research(
    symbol: str,
    asset: Mapping[str, object],
    raw_history: pd.DataFrame,
    *,
    dataset_fingerprint: str,
    cot_reports: Sequence[Mapping[str, object]] = (),
    cot_mapping: Mapping[str, object] | None = None,
    benchmark_histories: Mapping[str, pd.DataFrame] | None = None,
    breadth_context: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    frame = normalized_research_history(raw_history)
    if len(frame) < MINIMUM_HISTORY_ROWS:
        return {"symbol": symbol, "candidates": [], "labels": [], "counterfactuals": [], "status": "insufficient_history"}
    frame = _prepare_historical_indicators(frame)
    structure = _pivot_structure(frame)
    geometries = _all_impulse_pullback_geometries(frame)
    bearish_geometries = _all_down_impulse_rally_geometries(frame)
    market_phases, volatility_regimes = _technical_regime_context(frame)
    seasonality_context = _seasonality_period_context(frame)
    opening_context = _opening_level_context(frame)
    last_accepted = defaultdict(lambda: -10_000)
    mapping = dict(cot_mapping or load_cot_market_mapping())
    available_times = sorted(
        str(item.get("available_at"))
        for item in cot_reports
        if item.get("pit_eligible") is True and item.get("available_at")
    )
    earliest_cot = pd.Timestamp(available_times[0]) if available_times else None
    cot_cache: dict[str, dict] = {}
    shared_cache: dict[int, dict[str, object]] = {}
    candidates: list[dict] = []
    labels: list[dict] = []
    experiments: list[dict] = []
    identity = derive_swing_research_identity(asset)
    for position in range(MINIMUM_HISTORY_ROWS - 1, len(frame)):
        geometry = geometries[position]
        for setup_family in _candidate_setups(frame, position, geometry):
            if position - last_accepted[setup_family] < CANDIDATE_COOLDOWN_SESSIONS:
                continue
            signal_at = datetime.combine(
                pd.Timestamp(frame.index[position]).date(), time(23, 59), tzinfo=timezone.utc
            ).isoformat()
            cache_key = signal_at[:10]
            if cache_key not in cot_cache:
                comparable_signal = pd.Timestamp(signal_at)
                comparable_earliest = earliest_cot
                if comparable_earliest is not None:
                    if comparable_earliest.tzinfo is None:
                        comparable_earliest = comparable_earliest.tz_localize("UTC")
                    else:
                        comparable_earliest = comparable_earliest.tz_convert("UTC")
                if comparable_earliest is None or comparable_signal < comparable_earliest:
                    cot_cache[cache_key] = {
                        "link_version": BROAD_RESEARCH_COT_LINK_VERSION,
                        "base_feature_version": COT_FEATURE_VERSION,
                        "status": "unavailable_point_in_time",
                        "mapping": None,
                        "report_id": None,
                        "report_date": None,
                        "available_at": None,
                        "market_code": None,
                        "report_type": None,
                        "open_interest": None,
                        "categories": {},
                        "divergences": [],
                        "future_reports_used": 0,
                        "guessed_mapping": False,
                        "shadow_only": True,
                    }
                else:
                    cot_cache[cache_key] = _cot_features(
                        asset,
                        cot_reports,
                        signal_at=signal_at,
                        mapping=mapping,
                    )
            if position not in shared_cache:
                shared_cache[position] = build_shared_asset_features(
                    frame,
                    position,
                    asset=asset,
                    benchmark_histories=dict(benchmark_histories or {}),
                )
            feature = build_broad_research_feature(
                symbol,
                asset,
                frame,
                position,
                setup_family,
                dataset_fingerprint=dataset_fingerprint,
                structure=structure,
                cot_reports=cot_reports,
                cot_mapping=mapping,
                cot_context=cot_cache[cache_key],
                benchmark_histories=benchmark_histories,
                breadth_context=breadth_context,
                precomputed={
                    "geometry": geometry,
                    "bearish_geometry": bearish_geometries[position],
                    "market_phase": market_phases[position],
                    "volatility_regime": volatility_regimes[position],
                    "seasonality": _seasonality_features_from_context(
                        frame, position, seasonality_context
                    ),
                    "opening_levels": {
                        period: rows[position] for period, rows in opening_context.items()
                    },
                    "shared_features": shared_cache[position],
                },
            )
            signal_day = pd.Timestamp(frame.index[position]).date().isoformat()
            candidate_identity = {
                "candidate_version": BROAD_RESEARCH_CANDIDATE_VERSION,
                "dataset_fingerprint": dataset_fingerprint,
                "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
                "direction": "long",
                "listing_id": identity["listing_id"],
                "signal_day": signal_day,
                "setup_family": setup_family,
            }
            candidate_id = f"broad-{_fingerprint(candidate_identity)[:32]}"
            dependency_cluster = f"dep-{_fingerprint({'issuer': identity['issuer_id'], 'setup': setup_family, 'bucket': position // FUTURE_SESSIONS})[:24]}"
            candidate = {
                "candidate_id": candidate_id,
                "symbol": symbol,
                "signal_day": signal_day,
                "setup_family": setup_family,
                "direction": "long",
                "research_split": broad_research_split(signal_day),
                "issuer_id": identity["issuer_id"],
                "listing_id": identity["listing_id"],
                "dependency_cluster": dependency_cluster,
                "dataset_fingerprint": dataset_fingerprint,
                "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
                "feature": feature,
                "candidate_selected_from_outcome": False,
                "long_v1_required_for_selection": False,
                "short_signal_created": False,
            }
            candidate["candidate_fingerprint"] = _fingerprint(candidate)
            label, experiment = build_broad_research_labels(
                frame,
                position,
                feature,
                asset_type=str(asset.get("asset_type") or "Aktie"),
            )
            label["candidate_id"] = candidate_id
            experiment["candidate_id"] = candidate_id
            label.pop("label_fingerprint", None)
            experiment.pop("experiment_fingerprint", None)
            label["label_fingerprint"] = _fingerprint(label)
            experiment["experiment_fingerprint"] = _fingerprint(experiment)
            candidates.append(candidate)
            labels.append(label)
            experiments.append(experiment)
            last_accepted[setup_family] = position
    return {
        "symbol": symbol,
        "status": "ok",
        "candidates": candidates,
        "labels": labels,
        "counterfactuals": experiments,
    }


def record_asset_broad_research(
    result: Mapping[str, object],
    *,
    dataset_fingerprint: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, int | bool]:
    initialize_broad_research_store(path)
    symbol = str(result.get("symbol") or "").strip().upper()
    if not symbol:
        raise BroadResearchContractError("Asset-Ergebnis ohne Symbol.")
    candidates = list(result.get("candidates") or [])
    labels = {str(item["candidate_id"]): dict(item) for item in result.get("labels") or []}
    experiments = {
        str(item["candidate_id"]): dict(item) for item in result.get("counterfactuals") or []
    }
    completion_identity = {
        "symbol": symbol,
        "dataset_fingerprint": dataset_fingerprint,
        "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
    }
    completion_id = f"complete-{_fingerprint(completion_identity)[:32]}"
    with _connect(Path(path)) as connection:
        existing_completion = connection.execute(
            "SELECT completion_json FROM broad_research_asset_completions WHERE completion_id = ?",
            (completion_id,),
        ).fetchone()
        if existing_completion is not None:
            return {"already_complete": True, "candidates": 0, "labels": 0, "counterfactuals": 0}
        stored_candidates = stored_labels = stored_experiments = 0
        for raw_candidate in candidates:
            candidate = dict(raw_candidate)
            if str(candidate.get("direction") or "").lower() != "long":
                raise BroadResearchContractError(
                    "Der aktuelle Broad-Research-Pass darf ausschließlich Long-Kandidaten speichern."
                )
            candidate_id = str(candidate["candidate_id"])
            feature = dict(candidate["feature"])
            feature_json = _canonical_json(feature)
            feature_fingerprint = str(feature["feature_fingerprint"])
            current = connection.execute(
                "SELECT feature_fingerprint FROM broad_research_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if current is not None:
                if current["feature_fingerprint"] != feature_fingerprint:
                    raise BroadResearchContractError("Candidate-ID ist bereits abweichend belegt.")
            else:
                connection.execute(
                    """INSERT INTO broad_research_candidates(
                    candidate_id, symbol, signal_day, setup_family, direction, research_split,
                    issuer_id, listing_id, dependency_cluster, dataset_fingerprint,
                    feature_version, feature_json, feature_fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate_id,
                        symbol,
                        candidate["signal_day"],
                        candidate["setup_family"],
                        str(candidate.get("direction") or "long"),
                        candidate["research_split"],
                        candidate["issuer_id"],
                        candidate["listing_id"],
                        candidate["dependency_cluster"],
                        dataset_fingerprint,
                        BROAD_RESEARCH_FEATURE_VERSION,
                        feature_json,
                        feature_fingerprint,
                    ),
                )
                stored_candidates += 1
            label = labels[candidate_id]
            label_fingerprint = str(label["label_fingerprint"])
            current_label = connection.execute(
                "SELECT label_fingerprint FROM broad_research_labels WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if current_label is not None and current_label["label_fingerprint"] != label_fingerprint:
                raise BroadResearchContractError("Kandidatenlabel ist bereits abweichend belegt.")
            if current_label is None:
                connection.execute(
                    "INSERT INTO broad_research_labels VALUES (?, ?, ?, ?)",
                    (candidate_id, BROAD_RESEARCH_LABEL_VERSION, _canonical_json(label), label_fingerprint),
                )
                stored_labels += 1
            experiment = experiments[candidate_id]
            experiment_fingerprint = str(experiment["experiment_fingerprint"])
            current_experiment = connection.execute(
                "SELECT experiment_fingerprint FROM broad_research_counterfactuals WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if current_experiment is not None and current_experiment["experiment_fingerprint"] != experiment_fingerprint:
                raise BroadResearchContractError("Counterfactual ist bereits abweichend belegt.")
            if current_experiment is None:
                connection.execute(
                    "INSERT INTO broad_research_counterfactuals VALUES (?, ?, ?, ?)",
                    (
                        candidate_id,
                        BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
                        _canonical_json(experiment),
                        experiment_fingerprint,
                    ),
                )
                stored_experiments += 1
        completion = {
            **completion_identity,
            "status": str(result.get("status") or "ok"),
            "candidate_ids": [str(item["candidate_id"]) for item in candidates],
            "candidates": len(candidates),
            "labels": len(labels),
            "append_only": True,
        }
        completion_fingerprint = _fingerprint(completion)
        connection.execute(
            "INSERT INTO broad_research_asset_completions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                completion_id,
                symbol,
                dataset_fingerprint,
                BROAD_RESEARCH_FEATURE_VERSION,
                len(candidates),
                len(labels),
                _canonical_json(completion),
                completion_fingerprint,
            ),
        )
    return {
        "already_complete": False,
        "candidates": stored_candidates,
        "labels": stored_labels,
        "counterfactuals": stored_experiments,
    }


def completed_broad_research_symbols(
    *,
    dataset_fingerprint: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> set[str]:
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            """SELECT symbol FROM broad_research_asset_completions
            WHERE dataset_fingerprint = ? AND feature_version = ?""",
            (dataset_fingerprint, BROAD_RESEARCH_FEATURE_VERSION),
        ).fetchall()
    return {str(row["symbol"]) for row in rows}


def broad_research_feature_coverage(
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
    *,
    dataset_fingerprint: str | None = None,
) -> dict[str, object]:
    """Return exact JSON-field coverage for the stored immutable feature rows."""
    initialize_broad_research_store(path)
    where = " WHERE dataset_fingerprint = ?" if dataset_fingerprint else ""
    parameters: tuple[object, ...] = (dataset_fingerprint,) if dataset_fingerprint else ()
    with _connect(Path(path)) as connection:
        total = int(
            connection.execute(
                f"SELECT COUNT(*) FROM broad_research_candidates{where}", parameters
            ).fetchone()[0]
        )

        def count(condition: str) -> int:
            conjunction = " AND " if where else " WHERE "
            return int(
                connection.execute(
                    f"SELECT COUNT(*) FROM broad_research_candidates{where}{conjunction}{condition}",
                    parameters,
                ).fetchone()[0]
            )

        fields = {
            "rsi_14": "json_type(feature_json, '$.technical.rsi_14') IN ('integer','real')",
            "ema_20": "json_type(feature_json, '$.technical.ema_20') IN ('integer','real')",
            "ema_50": "json_type(feature_json, '$.technical.ema_50') IN ('integer','real')",
            "atr_14": "json_type(feature_json, '$.technical.atr_14') IN ('integer','real')",
            "volatility": "json_type(feature_json, '$.technical.volatility') IN ('integer','real')",
            "volume": "json_type(feature_json, '$.technical.volume') IN ('integer','real')",
            "relative_volume": "json_type(feature_json, '$.technical.relative_volume') IN ('integer','real')",
            "pullback_geometry": "json_extract(feature_json, '$.pullback.status') = 'available'",
            "fibonacci_geometry": "json_type(feature_json, '$.fibonacci.retracement_depth') IN ('integer','real')",
            "bearish_impulse_rally_geometry": "json_extract(feature_json, '$.short_readiness.down_impulse_and_rally.status') = 'available'",
            "bearish_fibonacci_geometry": "json_type(feature_json, '$.short_readiness.fibonacci.retracement_depth') IN ('integer','real')",
            "bearish_confirmation": "json_extract(feature_json, '$.short_readiness.down_impulse_and_rally.bearish_confirmation_close_below_prior_low') = 1",
            "bearish_bos": "json_extract(feature_json, '$.short_readiness.market_structure.bearish_bos') = 1",
            "bearish_ema_context": "json_type(feature_json, '$.short_readiness.ema_context.close_below_ema20') IN ('true','false') AND json_type(feature_json, '$.short_readiness.ema_context.close_below_ema50') IN ('true','false') AND json_type(feature_json, '$.short_readiness.ema_context.ema20_below_ema50') IN ('true','false')",
            "confirmed_swing_high": "json_type(feature_json, '$.market_structure.last_swing_high') = 'object'",
            "confirmed_swing_low": "json_type(feature_json, '$.market_structure.last_swing_low') = 'object'",
            "opening_levels": "json_type(feature_json, '$.opening_levels.daily.level') IN ('integer','real') AND json_type(feature_json, '$.opening_levels.weekly.level') IN ('integer','real') AND json_type(feature_json, '$.opening_levels.monthly.level') IN ('integer','real') AND json_type(feature_json, '$.opening_levels.quarterly.level') IN ('integer','real') AND json_type(feature_json, '$.opening_levels.yearly.level') IN ('integer','real')",
            "seasonality_week_history": "COALESCE(json_extract(feature_json, '$.seasonality.week.observations'), 0) > 0",
            "seasonality_month_history": "COALESCE(json_extract(feature_json, '$.seasonality.month_history.observations'), 0) > 0",
            "seasonality_quarter_history": "COALESCE(json_extract(feature_json, '$.seasonality.quarter_history.observations'), 0) > 0",
            "cot": "json_extract(feature_json, '$.cot.status') = 'available'",
            "relative_strength_20d": "json_type(feature_json, '$.relative_strength.horizons.20d.relative_strength') IN ('integer','real')",
            "trend_quality": "json_type(feature_json, '$.trend_quality.trend_20d.efficiency') IN ('integer','real')",
            "volatility_structure": "json_type(feature_json, '$.volatility_structure.atr_relative_to_close') IN ('integer','real')",
            "candle_quality": "json_type(feature_json, '$.candle_quality.body_to_range') IN ('integer','real')",
            "historical_extremes": "json_type(feature_json, '$.historical_extremes.252d.position_in_range') IN ('integer','real')",
            "gap_risk": "json_type(feature_json, '$.gap_risk.current_gap_pct') IN ('integer','real')",
            "historical_breadth": "json_type(feature_json, '$.historical_breadth.overall.metrics') = 'object'",
            "volume_profile": "json_extract(feature_json, '$.volume_profile.status') = 'available'",
        }
        counts = {name: count(condition) if total else 0 for name, condition in fields.items()}
        cot_rows = connection.execute(
            f"""SELECT COALESCE(json_extract(feature_json, '$.cot.status'), 'missing') status,
            COUNT(*) count FROM broad_research_candidates{where}
            GROUP BY COALESCE(json_extract(feature_json, '$.cot.status'), 'missing') ORDER BY status""",
            parameters,
        ).fetchall()
        missing_values = int(
            connection.execute(
                f"SELECT COALESCE(SUM(json_array_length(feature_json, '$.feature_missing')), 0) FROM broad_research_candidates{where}",
                parameters,
            ).fetchone()[0]
        )
    return {
        "candidates": total,
        "available": counts,
        "coverage_pct": {
            name: round(value / total * 100, 4) if total else 0.0
            for name, value in counts.items()
        },
        "cot_statuses": {str(row["status"]): int(row["count"]) for row in cot_rows},
        "recorded_missing_values": missing_values,
        "volume_profile_unavailable_by_contract": counts["volume_profile"] == 0,
    }


def finalize_broad_research_manifest(
    *,
    dataset_fingerprint: str,
    expected_assets: int,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        completions = connection.execute(
            """SELECT completion_fingerprint FROM broad_research_asset_completions
            WHERE dataset_fingerprint = ? AND feature_version = ? ORDER BY symbol""",
            (dataset_fingerprint, BROAD_RESEARCH_FEATURE_VERSION),
        ).fetchall()
        if len(completions) != int(expected_assets):
            raise BroadResearchContractError(
                f"Manifest erst nach vollständiger Asset-Abdeckung: {len(completions)}/{expected_assets}."
            )
        counts = {
            "candidates": int(connection.execute("SELECT COUNT(*) FROM broad_research_candidates").fetchone()[0]),
            "labels": int(connection.execute("SELECT COUNT(*) FROM broad_research_labels").fetchone()[0]),
            "counterfactuals": int(connection.execute("SELECT COUNT(*) FROM broad_research_counterfactuals").fetchone()[0]),
        }
        split_rows = connection.execute(
            "SELECT research_split, COUNT(*) count FROM broad_research_candidates GROUP BY research_split"
        ).fetchall()
        feature_coverage = broad_research_feature_coverage(
            path,
            dataset_fingerprint=dataset_fingerprint,
        )
        manifest = {
            "schema_version": BROAD_RESEARCH_SCHEMA_VERSION,
            "candidate_version": BROAD_RESEARCH_CANDIDATE_VERSION,
            "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
            "label_version": BROAD_RESEARCH_LABEL_VERSION,
            "counterfactual_version": BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
            "split_version": BROAD_RESEARCH_SPLIT_VERSION,
            "dataset_fingerprint": dataset_fingerprint,
            "code_fingerprint": broad_research_code_fingerprint(),
            "feature_contract_fingerprint": broad_research_feature_contract_fingerprint(),
            "asset_completions": len(completions),
            "expected_assets": expected_assets,
            "completion_fingerprints": [str(row[0]) for row in completions],
            "counts": counts,
            "splits": {str(row["research_split"]): int(row["count"]) for row in split_rows},
            "feature_coverage": feature_coverage,
            "cot_available_candidates": int(feature_coverage["available"]["cot"]),
            "volume_profile_available_candidates": 0,
            "outcome_independent_candidate_selection": True,
            "features_created_before_labels": True,
            "shared_direction_neutral_historical_features": True,
            "first_pass_feature_scope_frozen": True,
            "shared_context_version": BROAD_CONTEXT_VERSION,
            "benchmark_mapping_version": BROAD_BENCHMARK_MAPPING_VERSION,
            "breadth_version": BROAD_BREADTH_VERSION,
            "breadth_survivorship_free": False,
            "sector_benchmark_and_breadth_unavailable_without_pit_membership": True,
            "additional_feature_expansion_before_evaluation_allowed": False,
            "automatic_feature_optimization": False,
            "candidate_direction": "long",
            "short_strategy_enabled": False,
            "short_signals_created": False,
            "random_split_allowed": False,
            "automatic_production_activation": False,
        }
        manifest_fingerprint = _fingerprint(manifest)
        manifest_id = f"manifest-{manifest_fingerprint[:32]}"
        connection.execute(
            "INSERT OR IGNORE INTO broad_research_manifests VALUES (?, ?, ?)",
            (manifest_id, _canonical_json(manifest), manifest_fingerprint),
        )
    return {**manifest, "manifest_id": manifest_id, "manifest_fingerprint": manifest_fingerprint}


def link_existing_long_v1_cases(
    walk_forward_path: Path,
    *,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, int]:
    """Append same-asset/day baseline links without using them for candidate selection."""
    initialize_broad_research_store(path)
    source_path = Path(walk_forward_path)
    if not source_path.exists():
        return {"baseline_cases": 0, "candidate_matches": 0, "stored_links": 0}
    source = sqlite3.connect(f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    baseline_cases = candidate_matches = stored_links = 0
    try:
        with _connect(Path(path)) as destination:
            for row in source.execute(
                "SELECT case_id, symbol, signal_at, case_json FROM walk_forward_cases ORDER BY signal_at, case_id"
            ):
                case = json.loads(row["case_json"])
                strategy = dict((case.get("snapshot") or {}).get("strategy") or {})
                if str(strategy.get("strategy_name") or "") != "current":
                    continue
                baseline_cases += 1
                setup_text = str(strategy.get("setup_type") or "").casefold()
                setup_family = (
                    "objective_pullback" if "rück" in setup_text or "pullback" in setup_text
                    else "objective_breakout" if "ausbruch" in setup_text or "breakout" in setup_text
                    else None
                )
                query = """SELECT candidate_id FROM broad_research_candidates
                    WHERE symbol=? AND signal_day=?"""
                parameters: list[object] = [str(row["symbol"]), str(row["signal_at"])[:10]]
                if setup_family:
                    query += " AND setup_family=?"
                    parameters.append(setup_family)
                matches = destination.execute(query, tuple(parameters)).fetchall()
                for match in matches:
                    candidate_matches += 1
                    payload = {
                        "candidate_id": str(match["candidate_id"]),
                        "walk_forward_case_id": str(row["case_id"]),
                        "strategy_version": str(strategy.get("strategy_version") or "unknown"),
                        "relation": "same_asset_signal_day_setup_family",
                        "baseline_result_r": case.get("result_r"),
                        "baseline_result_pct": case.get("result_pct"),
                        "used_for_candidate_selection": False,
                    }
                    fingerprint = _fingerprint(payload)
                    link_id = f"baseline-link-{fingerprint[:32]}"
                    existing = destination.execute(
                        "SELECT link_fingerprint FROM broad_research_baseline_links WHERE link_id=?",
                        (link_id,),
                    ).fetchone()
                    if existing is not None and existing["link_fingerprint"] != fingerprint:
                        raise BroadResearchContractError("Baseline-Link ist abweichend belegt.")
                    if existing is None:
                        destination.execute(
                            "INSERT INTO broad_research_baseline_links VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                link_id,
                                payload["candidate_id"],
                                payload["walk_forward_case_id"],
                                payload["strategy_version"],
                                payload["relation"],
                                _canonical_json(payload),
                                fingerprint,
                            ),
                        )
                        stored_links += 1
    finally:
        source.close()
    return {
        "baseline_cases": baseline_cases,
        "candidate_matches": candidate_matches,
        "stored_links": stored_links,
    }


def broad_research_store_audit(path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH) -> dict[str, object]:
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "broad_research_candidates",
                "broad_research_labels",
                "broad_research_counterfactuals",
                "broad_research_baseline_links",
                "broad_research_asset_completions",
                "broad_research_manifests",
                "broad_research_breadth_manifests",
                "broad_research_hypotheses",
                "broad_research_challengers",
                "broad_research_challenger_trades",
                "broad_research_challenger_rescan_completions",
                "broad_research_challenger_reviews",
            )
        }
        splits = {
            str(row[0]): int(row[1])
            for row in connection.execute(
                "SELECT research_split, COUNT(*) FROM broad_research_candidates GROUP BY research_split"
            ).fetchall()
        }
        setups = {
            str(row[0]): int(row[1])
            for row in connection.execute(
                "SELECT setup_family, COUNT(*) FROM broad_research_candidates GROUP BY setup_family"
            ).fetchall()
        }
        directions = {
            str(row[0]): int(row[1])
            for row in connection.execute(
                "SELECT direction, COUNT(*) FROM broad_research_candidates GROUP BY direction"
            ).fetchall()
        }
    return {
        "schema_version": BROAD_RESEARCH_SCHEMA_VERSION,
        "quick_check": quick_check,
        "status": "ok" if quick_check == "ok" else "invalid",
        "counts": counts,
        "splits": splits,
        "setups": setups,
        "directions": directions,
        "short_candidates": int(directions.get("short", 0)),
        "append_only": True,
        "separate_from_walk_forward": True,
        "separate_features_and_labels": True,
        "automatic_production_activation": False,
    }


def _metric_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    results = [float(row["result_r"]) for row in rows if _number(row.get("result_r")) is not None]
    wins = [value for value in results if value > 0]
    losses = [value for value in results if value < 0]
    cumulative = peak = drawdown = 0.0
    streak = maximum_streak = 0
    for value in results:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = min(drawdown, cumulative - peak)
        streak = streak + 1 if value <= 0 else 0
        maximum_streak = max(maximum_streak, streak)
    return {
        "cases": len(rows),
        "effective_independent_cases": len({str(row.get("dependency_cluster")) for row in rows}),
        "average_r": sum(results) / len(results) if results else None,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "hit_rate_pct": len(wins) / len(results) * 100 if results else None,
        "maximum_drawdown_r": abs(drawdown),
        "maximum_loss_streak": maximum_streak,
    }


def _new_metric_accumulator() -> dict[str, object]:
    return {
        "cases": 0,
        "evaluated": 0,
        "sum_r": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "wins": 0,
        "cumulative_r": 0.0,
        "peak_r": 0.0,
        "maximum_drawdown_r": 0.0,
        "loss_streak": 0,
        "maximum_loss_streak": 0,
        "mfe_sum": 0.0,
        "mfe_count": 0,
        "mae_sum": 0.0,
        "mae_count": 0,
        "segments": defaultdict(lambda: defaultdict(lambda: {"cases": 0, "evaluated": 0, "sum_r": 0.0})),
    }


def _update_metric_accumulator(
    accumulator: dict[str, object],
    *,
    result_r: float | None,
    mfe_pct: float | None,
    mae_pct: float | None,
    segments: Mapping[str, str],
) -> None:
    accumulator["cases"] = int(accumulator["cases"]) + 1
    for dimension, raw_value in segments.items():
        value = str(raw_value or "Unbekannt")
        bucket = accumulator["segments"][dimension][value]
        bucket["cases"] += 1
        if result_r is not None:
            bucket["evaluated"] += 1
            bucket["sum_r"] += result_r
    if mfe_pct is not None:
        accumulator["mfe_sum"] = float(accumulator["mfe_sum"]) + mfe_pct
        accumulator["mfe_count"] = int(accumulator["mfe_count"]) + 1
    if mae_pct is not None:
        accumulator["mae_sum"] = float(accumulator["mae_sum"]) + mae_pct
        accumulator["mae_count"] = int(accumulator["mae_count"]) + 1
    if result_r is None:
        return
    accumulator["evaluated"] = int(accumulator["evaluated"]) + 1
    accumulator["sum_r"] = float(accumulator["sum_r"]) + result_r
    if result_r > 0:
        accumulator["wins"] = int(accumulator["wins"]) + 1
        accumulator["gross_profit"] = float(accumulator["gross_profit"]) + result_r
        accumulator["loss_streak"] = 0
    else:
        accumulator["gross_loss"] = float(accumulator["gross_loss"]) + abs(result_r)
        accumulator["loss_streak"] = int(accumulator["loss_streak"]) + 1
        accumulator["maximum_loss_streak"] = max(
            int(accumulator["maximum_loss_streak"]), int(accumulator["loss_streak"])
        )
    cumulative = float(accumulator["cumulative_r"]) + result_r
    peak = max(float(accumulator["peak_r"]), cumulative)
    accumulator["cumulative_r"] = cumulative
    accumulator["peak_r"] = peak
    accumulator["maximum_drawdown_r"] = max(
        float(accumulator["maximum_drawdown_r"]), peak - cumulative
    )


def _finalize_metric_accumulator(
    accumulator: Mapping[str, object],
    *,
    effective_independent_cases: int,
) -> dict[str, object]:
    evaluated = int(accumulator["evaluated"])
    gross_loss = float(accumulator["gross_loss"])
    segments = {}
    for dimension, raw_groups in accumulator["segments"].items():
        segments[str(dimension)] = {
            str(value): {
                "cases": int(bucket["cases"]),
                "evaluated": int(bucket["evaluated"]),
                "average_r": (
                    float(bucket["sum_r"]) / int(bucket["evaluated"])
                    if int(bucket["evaluated"])
                    else None
                ),
            }
            for value, bucket in sorted(raw_groups.items())
        }
    yearly = segments.get("year", {})
    evaluated_years = [item for item in yearly.values() if int(item["evaluated"]) > 0]
    positive_years = sum(
        1 for item in evaluated_years if _number(item.get("average_r")) is not None and float(item["average_r"]) > 0
    )
    return {
        "cases": int(accumulator["cases"]),
        "evaluated": evaluated,
        "effective_independent_cases": int(effective_independent_cases),
        "average_r": float(accumulator["sum_r"]) / evaluated if evaluated else None,
        "expectancy_r": float(accumulator["sum_r"]) / evaluated if evaluated else None,
        "profit_factor": float(accumulator["gross_profit"]) / gross_loss if gross_loss > 0 else None,
        "hit_rate_pct": int(accumulator["wins"]) / evaluated * 100 if evaluated else None,
        "maximum_drawdown_r": float(accumulator["maximum_drawdown_r"]),
        "maximum_loss_streak": int(accumulator["maximum_loss_streak"]),
        "average_mfe_pct": (
            float(accumulator["mfe_sum"]) / int(accumulator["mfe_count"])
            if int(accumulator["mfe_count"])
            else None
        ),
        "average_mae_pct": (
            float(accumulator["mae_sum"]) / int(accumulator["mae_count"])
            if int(accumulator["mae_count"])
            else None
        ),
        "time_stability": {
            "evaluated_years": len(evaluated_years),
            "positive_expectancy_years": positive_years,
            "positive_expectancy_year_share_pct": (
                positive_years / len(evaluated_years) * 100 if evaluated_years else None
            ),
            "by_year": yearly,
        },
        "segments": {key: value for key, value in segments.items() if key != "year"},
    }


def development_pattern_report(path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH) -> dict[str, object]:
    """Stream a fixed, small hypothesis list over Development data only."""
    initialize_broad_research_store(path)
    hypotheses = [
        (
            "buyer_confirmation",
            "json_extract(c.feature_json, '$.pullback.buyer_confirmation_close_above_prior_high') = 1",
        ),
        (
            "three_or_more_bearish_candles",
            "COALESCE(json_extract(c.feature_json, '$.pullback.bearish_candles'), 0) >= 3",
        ),
        (
            "fibonacci_0618_0786",
            "json_extract(c.feature_json, '$.fibonacci.inside_0618_0786') = 1",
        ),
        (
            "ema20_above_ema50",
            "COALESCE(json_extract(c.feature_json, '$.technical.ema20_relative_to_ema50'), 0) > 1",
        ),
        (
            "rsi_40_70",
            "json_extract(c.feature_json, '$.technical.rsi_14') BETWEEN 40 AND 70",
        ),
        (
            "bos_close_break",
            "json_extract(c.feature_json, '$.market_structure.close_break') = 1",
        ),
        (
            "opening_level_contact",
            "json_extract(c.feature_json, '$.opening_levels.daily.contact') = 1 OR json_extract(c.feature_json, '$.opening_levels.weekly.contact') = 1 OR json_extract(c.feature_json, '$.opening_levels.monthly.contact') = 1 OR json_extract(c.feature_json, '$.opening_levels.quarterly.contact') = 1 OR json_extract(c.feature_json, '$.opening_levels.yearly.contact') = 1",
        ),
        (
            "cot_available",
            "json_extract(c.feature_json, '$.cot.status') = 'available'",
        ),
    ]
    # Small, predeclared neighborhoods make isolated threshold peaks visible.
    # They are diagnostic only and are evaluated in the same single Development
    # stream; no value is chosen from Validation or Holdout.
    neighborhoods = [
        ("rsi_lower_bound", "rsi_35_70", 35.0, "json_extract(c.feature_json, '$.technical.rsi_14') BETWEEN 35 AND 70"),
        ("rsi_lower_bound", "rsi_40_70", 40.0, "json_extract(c.feature_json, '$.technical.rsi_14') BETWEEN 40 AND 70"),
        ("rsi_lower_bound", "rsi_45_70", 45.0, "json_extract(c.feature_json, '$.technical.rsi_14') BETWEEN 45 AND 70"),
        ("ema20_to_ema50", "ema_ratio_0_995", 0.995, "COALESCE(json_extract(c.feature_json, '$.technical.ema20_relative_to_ema50'), 0) > 0.995"),
        ("ema20_to_ema50", "ema_ratio_1_000", 1.0, "COALESCE(json_extract(c.feature_json, '$.technical.ema20_relative_to_ema50'), 0) > 1.0"),
        ("ema20_to_ema50", "ema_ratio_1_005", 1.005, "COALESCE(json_extract(c.feature_json, '$.technical.ema20_relative_to_ema50'), 0) > 1.005"),
        ("bos_excess_atr", "bos_excess_0_0", 0.0, "COALESCE(json_extract(c.feature_json, '$.market_structure.close_break_excess_atr'), -999) >= 0.0"),
        ("bos_excess_atr", "bos_excess_0_1", 0.1, "COALESCE(json_extract(c.feature_json, '$.market_structure.close_break_excess_atr'), -999) >= 0.1"),
        ("bos_excess_atr", "bos_excess_0_2", 0.2, "COALESCE(json_extract(c.feature_json, '$.market_structure.close_break_excess_atr'), -999) >= 0.2"),
    ]
    accumulators = [(_new_metric_accumulator(), _new_metric_accumulator()) for _ in hypotheses]
    neighborhood_accumulators = [_new_metric_accumulator() for _ in neighborhoods]
    baseline_accumulator = _new_metric_accumulator()
    with _connect(Path(path)) as connection:
        hypothesis_flags = ", ".join(
            f"CASE WHEN ({condition}) THEN 1 ELSE 0 END h{index}"
            for index, (_, condition) in enumerate(hypotheses)
        )
        neighborhood_flags = ", ".join(
            f"CASE WHEN ({condition}) THEN 1 ELSE 0 END n{index}"
            for index, (_, _, _, condition) in enumerate(neighborhoods)
        )
        flags = ", ".join(value for value in (hypothesis_flags, neighborhood_flags) if value)
        query = f"""SELECT c.signal_day, c.setup_family,
        json_extract(c.feature_json, '$.asset.asset_type') asset_type,
        json_extract(c.feature_json, '$.asset.region') region,
        json_extract(c.feature_json, '$.technical.market_phase') market_phase,
        json_extract(c.feature_json, '$.technical.volatility_regime') volatility_regime,
        json_extract(l.label_json, '$.mfe_pct') mfe_pct,
        json_extract(l.label_json, '$.mae_pct') mae_pct,
        json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.exits.fixed_2r.result_r') result_r,
        {flags}
        FROM broad_research_candidates c
        JOIN broad_research_labels l USING(candidate_id)
        JOIN broad_research_counterfactuals e USING(candidate_id)
        WHERE c.research_split = 'development'
        ORDER BY c.signal_day, c.candidate_id"""
        case_count = 0
        for row in connection.execute(query):
            case_count += 1
            result_r = _number(row["result_r"])
            segments = {
                "asset_group": str(row["asset_type"] or "Unbekannt"),
                "region": str(row["region"] or "Unbekannt"),
                "setup": str(row["setup_family"] or "Unbekannt"),
                "market_phase": str(row["market_phase"] or "Unbekannt"),
                "volatility_regime": str(row["volatility_regime"] or "Unbekannt"),
                "year": str(row["signal_day"] or "")[:4] or "Unbekannt",
            }
            _update_metric_accumulator(
                baseline_accumulator,
                result_r=result_r,
                mfe_pct=_number(row["mfe_pct"]),
                mae_pct=_number(row["mae_pct"]),
                segments=segments,
            )
            for index in range(len(hypotheses)):
                selected = bool(row[f"h{index}"])
                _update_metric_accumulator(
                    accumulators[index][0 if selected else 1],
                    result_r=result_r,
                    mfe_pct=_number(row["mfe_pct"]),
                    mae_pct=_number(row["mae_pct"]),
                    segments=segments,
                )
            for index in range(len(neighborhoods)):
                if bool(row[f"n{index}"]):
                    _update_metric_accumulator(
                        neighborhood_accumulators[index],
                        result_r=result_r,
                        mfe_pct=_number(row["mfe_pct"]),
                        mae_pct=_number(row["mae_pct"]),
                        segments=segments,
                    )
        distinct_columns = []
        for index, (_, condition) in enumerate(hypotheses):
            distinct_columns.extend(
                (
                    f"COUNT(DISTINCT CASE WHEN ({condition}) THEN c.dependency_cluster END) h{index}_selected",
                    f"COUNT(DISTINCT CASE WHEN NOT COALESCE(({condition}), 0) THEN c.dependency_cluster END) h{index}_control",
                )
            )
        distinct_columns.append("COUNT(DISTINCT c.dependency_cluster) baseline_effective")
        for index, (_, _, _, condition) in enumerate(neighborhoods):
            distinct_columns.append(
                f"COUNT(DISTINCT CASE WHEN ({condition}) THEN c.dependency_cluster END) n{index}_selected"
            )
        effective = connection.execute(
            f"SELECT {', '.join(distinct_columns)} FROM broad_research_candidates c WHERE c.research_split='development'"
        ).fetchone()
    baseline_metrics = _finalize_metric_accumulator(
        baseline_accumulator,
        effective_independent_cases=int(effective["baseline_effective"] or 0),
    )
    report_rows = []
    for index, (hypothesis_id, _) in enumerate(hypotheses):
        selected_metrics = _finalize_metric_accumulator(
            accumulators[index][0],
            effective_independent_cases=int(effective[f"h{index}_selected"] or 0),
        )
        control_metrics = _finalize_metric_accumulator(
            accumulators[index][1],
            effective_independent_cases=int(effective[f"h{index}_control"] or 0),
        )
        classification = "B"
        reason = "Nur Development-Hinweis; Validation und Holdout bleiben gesperrt."
        selected_average = _number(selected_metrics.get("average_r"))
        control_average = _number(control_metrics.get("average_r"))
        selected_pf = _number(selected_metrics.get("profit_factor"))
        stability = dict(selected_metrics.get("time_stability") or {})
        if (
            int(selected_metrics["effective_independent_cases"]) >= 500
            and selected_average is not None
            and control_average is not None
            and selected_pf is not None
            and selected_average > 0
            and selected_average - control_average >= 0.10
            and selected_pf >= 1.15
            and int(stability.get("evaluated_years") or 0) >= 4
            and (_number(stability.get("positive_expectancy_year_share_pct")) or 0) >= 60
        ):
            classification = "B"
            reason = (
                "Vorab definierte Development-Mindestwerte erreicht. Vor einer C-Einstufung "
                "fehlen noch die vollständige Placebo-, Ablations-, Plateau-, Cluster-, "
                "Zeit-/Regime- und Execution-Qualitätsprüfung."
            )
        elif selected_metrics["cases"] >= 200 and (
            selected_metrics["average_r"] is None or float(selected_metrics["average_r"]) <= 0
        ):
            classification = "A"
            reason = "Vorab definierte Development-Hypothese zeigt bei ausreichender Fallzahl keinen positiven Erwartungswert."
        report_rows.append(
            {
                "hypothesis_id": hypothesis_id,
                "tested_on": "development_only",
                "selected": selected_metrics,
                "control": control_metrics,
                "classification": classification,
                "eligible_for_manual_fixed_challenger": classification == "C",
                "preliminary_c_metrics_reached": (
                    selected_metrics["effective_independent_cases"] >= 500
                    and selected_average is not None
                    and control_average is not None
                    and selected_pf is not None
                    and selected_average > 0
                    and selected_average - control_average >= 0.10
                    and selected_pf >= 1.15
                    and int(stability.get("evaluated_years") or 0) >= 4
                    and (_number(stability.get("positive_expectancy_year_share_pct")) or 0) >= 60
                ),
                "quality_review_complete": False,
                "required_quality_dimensions": [
                    "placebo",
                    "parameter_plateau",
                    "feature_ablation",
                    "cluster_robustness",
                    "time_and_regime_stability",
                    "entry_efficiency",
                    "execution_stress",
                    "complexity",
                    "survivorship_bias_audit",
                ],
                "classification_c_is_production_approval": False,
                "reason": reason,
                "parameter_robustness": "Keine Schwelle optimiert; Robustheit muss als feste Challenger-Version separat geprüft werden.",
                "trade_retention_vs_development_baseline": (
                    int(selected_metrics["evaluated"]) / int(baseline_metrics["evaluated"])
                    if int(baseline_metrics["evaluated"])
                    else None
                ),
                "trade_count_loss_vs_development_baseline": max(
                    int(baseline_metrics["evaluated"]) - int(selected_metrics["evaluated"]),
                    0,
                ),
            }
        )
    neighborhood_rows = []
    for index, (family, variant_id, value, _) in enumerate(neighborhoods):
        metrics = _finalize_metric_accumulator(
            neighborhood_accumulators[index],
            effective_independent_cases=int(effective[f"n{index}_selected"] or 0),
        )
        neighborhood_rows.append(
            {
                "family": family,
                "variant_id": variant_id,
                "fixed_parameter_value": value,
                "tested_on": "development_only",
                "metrics": metrics,
                "trade_retention_vs_development_baseline": (
                    int(metrics["evaluated"]) / int(baseline_metrics["evaluated"])
                    if int(baseline_metrics["evaluated"])
                    else None
                ),
                "trade_count_loss_vs_development_baseline": max(
                    int(baseline_metrics["evaluated"]) - int(metrics["evaluated"]),
                    0,
                ),
                "single_best_value_selected": False,
                "validation_opened": False,
                "holdout_opened": False,
            }
        )
    parameter_plateaus = {}
    for family in sorted({str(row["family"]) for row in neighborhood_rows}):
        variants = []
        for row in neighborhood_rows:
            if row["family"] != family:
                continue
            metrics = dict(row["metrics"])
            variants.append(
                {
                    "variant_id": row["variant_id"],
                    "parameter_value": row["fixed_parameter_value"],
                    "expectancy_r": metrics.get("expectancy_r"),
                    "profit_factor": metrics.get("profit_factor"),
                    "maximum_drawdown_r": metrics.get("maximum_drawdown_r"),
                    "raw_cases": metrics.get("cases"),
                    "effective_independent_cases": metrics.get("effective_independent_cases"),
                }
            )
        parameter_plateaus[family] = parameter_plateau_report(variants)
    report = {
        "pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
        "cases": case_count,
        "development_candidate_baseline": baseline_metrics,
        "hypotheses": report_rows,
        "parameter_neighborhoods": neighborhood_rows,
        "parameter_plateaus": parameter_plateaus,
        "multiple_testing_count": len(hypotheses),
        "grid_search": False,
        "validation_opened": False,
        "holdout_opened": False,
        "automatic_challenger_creation": False,
        "automatic_production_activation": False,
    }
    with _connect(Path(path)) as connection:
        for row in report_rows:
            payload = {
                "pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
                **row,
                "validation_opened": False,
                "holdout_opened": False,
                "automatic_challenger_creation": False,
                "automatic_production_activation": False,
            }
            fingerprint = _fingerprint(payload)
            hypothesis_key = f"{BROAD_RESEARCH_PATTERN_VERSION}|{row['hypothesis_id']}"
            existing = connection.execute(
                "SELECT hypothesis_fingerprint FROM broad_research_hypotheses WHERE hypothesis_id=?",
                (hypothesis_key,),
            ).fetchone()
            if existing is not None and str(existing["hypothesis_fingerprint"]) != fingerprint:
                raise BroadResearchContractError(
                    "Development-Hypothese ist für dieselbe Version abweichend belegt."
                )
            if existing is None:
                connection.execute(
                    "INSERT INTO broad_research_hypotheses VALUES (?, ?, ?)",
                    (hypothesis_key, _canonical_json(payload), fingerprint),
                )
    return report


def register_fixed_research_challenger(
    rule: Mapping[str, object],
    *,
    hypothesis_id: str,
    dataset_fingerprint: str,
    feature_fingerprint: str,
    development_report: Mapping[str, object],
    manual_confirmation: str,
    approved_at: str,
    expected_assets: int,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    """Freeze a manually chosen Development hypothesis before unseen evaluation."""
    if not rule or _contains_outcome_knowledge(rule):
        raise BroadResearchContractError("Challenger-Regel fehlt oder enthält Ergebniswissen.")
    if manual_confirmation != "CONFIRM_CHALLENGER_C_FREEZE":
        raise BroadResearchContractError("Explizite manuelle Challenger-C-Bestätigung fehlt.")
    allowed_rule_keys = {
        "setup_family",
        "buyer_confirmation",
        "minimum_bearish_candles",
        "fibonacci_inside_0618_0786",
        "ema20_to_ema50_min",
        "rsi_min",
        "rsi_max",
        "bos_close_break",
        "minimum_bos_excess_atr",
        "opening_level_contact",
        "cot_available",
    }
    unknown_rule_keys = sorted(set(rule) - allowed_rule_keys)
    if unknown_rule_keys:
        raise BroadResearchContractError(
            f"Nicht unterstützte feste Challenger-Regel: {', '.join(unknown_rule_keys)}"
        )
    hypotheses = {
        str(row.get("hypothesis_id") or ""): dict(row or {})
        for row in development_report.get("hypotheses") or []
    }
    selected_hypothesis = hypotheses.get(str(hypothesis_id))
    if (
        str(development_report.get("pattern_version") or "") != BROAD_RESEARCH_PATTERN_VERSION
        or selected_hypothesis is None
        or selected_hypothesis.get("classification") != "C"
        or selected_hypothesis.get("eligible_for_manual_fixed_challenger") is not True
        or selected_hypothesis.get("quality_review_complete") is not True
        or development_report.get("validation_opened") is not False
        or development_report.get("holdout_opened") is not False
    ):
        raise BroadResearchContractError(
            "Nur eine manuell bestätigte Development-Klassifikation C darf eingefroren werden."
        )
    if int(expected_assets) <= 0:
        raise BroadResearchContractError("Die erwartete Frozen-Assetzahl muss positiv sein.")
    verified_evidence = _verify_manual_c_evidence(
        hypothesis_id=str(hypothesis_id),
        selected_hypothesis=selected_hypothesis,
        dataset_fingerprint=dataset_fingerprint,
        feature_fingerprint=feature_fingerprint,
        expected_assets=int(expected_assets),
        path=path,
    )
    payload = {
        "hypothesis_id": str(hypothesis_id),
        "rule": dict(rule),
        "dataset_fingerprint": dataset_fingerprint,
        "feature_fingerprint": feature_fingerprint,
        "candidate_version": BROAD_RESEARCH_CANDIDATE_VERSION,
        "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
        "label_version": BROAD_RESEARCH_LABEL_VERSION,
        "counterfactual_version": BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
        "split_version": BROAD_RESEARCH_SPLIT_VERSION,
        "code_fingerprint": broad_research_code_fingerprint(),
        "development_pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
        "development_hypothesis_fingerprint": verified_evidence[
            "hypothesis_fingerprint"
        ],
        "broad_manifest_fingerprint": verified_evidence["manifest_fingerprint"],
        "manual_approval": {
            "confirmation": manual_confirmation,
            "approved_at": str(approved_at),
            "performance_release": False,
        },
        "expected_assets_per_historical_stage": int(expected_assets),
        "evaluation_contract": {
            "entry": "next_session_open_after_completed_signal_bar",
            "stop_variant": "pullback_low_atr_buffer",
            "exit_variant": "fixed_2r",
            "cost_version": SWING_EXECUTION_COST_VERSION,
            "conservative_same_bar_order": "gap_then_stop_before_target",
            "purging": "dependency_cluster_and_candidate_cooldown",
        },
        "strategy_role": "research_challenger",
        "selection_source": "development_only_manual_freeze",
        "full_frozen_history_rescan_required": True,
        "stage_order": ["validation", "holdout", "external", "true_forward"],
        "validation_parameters_mutable": False,
        "holdout_parameters_mutable": False,
        "external_universe_required": True,
        "true_forward_required": True,
        "automatic_production_activation": False,
    }
    fingerprint = _fingerprint(payload)
    version = f"swing-broad-challenger-{fingerprint[:20]}"
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT challenger_fingerprint FROM broad_research_challengers WHERE challenger_version = ?",
            (version,),
        ).fetchone()
        if existing is not None and existing["challenger_fingerprint"] != fingerprint:
            raise BroadResearchContractError("Challenger-Version ist abweichend belegt.")
        if existing is None:
            connection.execute(
                "INSERT INTO broad_research_challengers VALUES (?, ?, ?)",
                (version, _canonical_json(payload), fingerprint),
            )
    return {**payload, "challenger_version": version, "challenger_fingerprint": fingerprint}


def _contains_outcome_knowledge(value: object) -> bool:
    forbidden = {
        "result",
        "result_r",
        "result_pct",
        "mfe",
        "mfe_pct",
        "mae",
        "mae_pct",
        "holdout_result",
        "validation_result",
        "profit_factor",
        "hit_rate",
        "expectancy",
    }
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in forbidden or _contains_outcome_knowledge(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_outcome_knowledge(item) for item in value)
    return False


def _verify_manual_c_evidence(
    *,
    hypothesis_id: str,
    selected_hypothesis: Mapping[str, object],
    dataset_fingerprint: str,
    feature_fingerprint: str,
    expected_assets: int,
    path: Path,
) -> dict[str, str]:
    """Bind the manual freeze to the completed append-only Broad evidence."""
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        manifests = connection.execute(
            "SELECT manifest_json, manifest_fingerprint FROM broad_research_manifests"
        ).fetchall()
        matching_manifest = None
        for row in manifests:
            manifest = json.loads(row["manifest_json"])
            if str(manifest.get("dataset_fingerprint") or "") == str(dataset_fingerprint):
                matching_manifest = (manifest, str(row["manifest_fingerprint"]))
                break
        hypothesis_key = f"{BROAD_RESEARCH_PATTERN_VERSION}|{hypothesis_id}"
        hypothesis_row = connection.execute(
            "SELECT hypothesis_json, hypothesis_fingerprint FROM broad_research_hypotheses WHERE hypothesis_id=?",
            (hypothesis_key,),
        ).fetchone()
    if matching_manifest is None:
        raise BroadResearchContractError(
            "Challenger-Freeze benötigt zuerst ein vollständiges Broad-Research-Manifest."
        )
    manifest, manifest_fingerprint = matching_manifest
    if (
        int(manifest.get("asset_completions") or 0) != int(expected_assets)
        or int(manifest.get("expected_assets") or 0) != int(expected_assets)
        or str(manifest.get("feature_contract_fingerprint") or "")
        != str(feature_fingerprint)
        or str(manifest.get("code_fingerprint") or "")
        != broad_research_code_fingerprint()
        or manifest.get("automatic_production_activation") is not False
    ):
        raise BroadResearchContractError(
            "Broad-Manifest, Assetabdeckung oder Code-/Feature-Fingerprint passt nicht zum Freeze."
        )
    if hypothesis_row is None:
        raise BroadResearchContractError(
            "Der bestätigte Development-C-Hinweis fehlt im append-only Hypothesenregister."
        )
    stored_hypothesis = json.loads(hypothesis_row["hypothesis_json"])
    stored_fingerprint = str(hypothesis_row["hypothesis_fingerprint"])
    if _fingerprint(stored_hypothesis) != stored_fingerprint:
        raise BroadResearchContractError("Gespeicherter Development-Hinweis ist beschädigt.")
    for key, value in selected_hypothesis.items():
        if _canonical_json(stored_hypothesis.get(key)) != _canonical_json(value):
            raise BroadResearchContractError(
                "Manuell vorgelegter C-Hinweis weicht vom append-only Development-Bericht ab."
            )
    if (
        stored_hypothesis.get("classification") != "C"
        or stored_hypothesis.get("eligible_for_manual_fixed_challenger") is not True
        or stored_hypothesis.get("quality_review_complete") is not True
        or stored_hypothesis.get("validation_opened") is not False
        or stored_hypothesis.get("holdout_opened") is not False
    ):
        raise BroadResearchContractError("Gespeicherter Development-Hinweis ist nicht freeze-fähig.")
    return {
        "manifest_fingerprint": manifest_fingerprint,
        "hypothesis_fingerprint": stored_fingerprint,
    }


def _load_fixed_challenger(
    challenger_version: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT challenger_json, challenger_fingerprint FROM broad_research_challengers WHERE challenger_version=?",
            (str(challenger_version),),
        ).fetchone()
    if row is None:
        raise BroadResearchContractError("Unbekannte feste Challenger-Version.")
    payload = json.loads(row["challenger_json"])
    if _fingerprint(payload) != str(row["challenger_fingerprint"]):
        raise BroadResearchContractError("Challenger-Fingerprint ist ungültig.")
    return {
        **payload,
        "challenger_version": str(challenger_version),
        "challenger_fingerprint": str(row["challenger_fingerprint"]),
    }


def fixed_challenger_rule_matches(
    candidate: Mapping[str, object],
    rule: Mapping[str, object],
) -> bool:
    """Apply the frozen rule to point-in-time features only."""
    feature = dict(candidate.get("feature") or {})
    technical = dict(feature.get("technical") or {})
    pullback = dict(feature.get("pullback") or {})
    fibonacci = dict(feature.get("fibonacci") or {})
    structure = dict(feature.get("market_structure") or {})
    opening_levels = dict(feature.get("opening_levels") or {})
    cot = dict(feature.get("cot") or {})
    if rule.get("setup_family") is not None and str(candidate.get("setup_family")) != str(
        rule.get("setup_family")
    ):
        return False
    checks = (
        ("buyer_confirmation", pullback.get("buyer_confirmation_close_above_prior_high")),
        ("fibonacci_inside_0618_0786", fibonacci.get("inside_0618_0786")),
        ("bos_close_break", structure.get("close_break")),
        (
            "opening_level_contact",
            any(bool(dict(value or {}).get("contact")) for value in opening_levels.values()),
        ),
        ("cot_available", cot.get("status") == "available"),
    )
    for key, actual in checks:
        if key in rule and bool(actual) is not bool(rule[key]):
            return False
    minimum_bearish = _number(rule.get("minimum_bearish_candles"))
    if minimum_bearish is not None and (
        _number(pullback.get("bearish_candles")) is None
        or float(pullback["bearish_candles"]) < minimum_bearish
    ):
        return False
    ema_min = _number(rule.get("ema20_to_ema50_min"))
    if ema_min is not None and (
        _number(technical.get("ema20_relative_to_ema50")) is None
        or float(technical["ema20_relative_to_ema50"]) < ema_min
    ):
        return False
    rsi = _number(technical.get("rsi_14"))
    rsi_min = _number(rule.get("rsi_min"))
    rsi_max = _number(rule.get("rsi_max"))
    if (rsi_min is not None or rsi_max is not None) and rsi is None:
        return False
    if rsi_min is not None and rsi is not None and rsi < rsi_min:
        return False
    if rsi_max is not None and rsi is not None and rsi > rsi_max:
        return False
    bos_min = _number(rule.get("minimum_bos_excess_atr"))
    if bos_min is not None and (
        _number(structure.get("close_break_excess_atr")) is None
        or float(structure["close_break_excess_atr"]) < bos_min
    ):
        return False
    return True


def challenger_allowed_stage(
    challenger_version: str,
    stage: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    """Open only the next stage after an explicit review of its predecessor."""
    stage_order = ("validation", "holdout", "external", "true_forward")
    requested = str(stage)
    if requested not in stage_order:
        raise BroadResearchContractError(f"Unbekannte Challenger-Stufe: {requested}")
    challenger = _load_fixed_challenger(challenger_version, path)
    with _connect(Path(path)) as connection:
        reviews = {
            str(row["research_stage"]): str(row["decision"])
            for row in connection.execute(
                "SELECT research_stage, decision FROM broad_research_challenger_reviews WHERE challenger_version=?",
                (str(challenger_version),),
            )
        }
    predecessor = stage_order[stage_order.index(requested) - 1] if requested != "validation" else None
    allowed = predecessor is None or reviews.get(predecessor) == "approved_to_next_stage"
    return {
        "challenger_version": challenger_version,
        "requested_stage": requested,
        "predecessor": predecessor,
        "predecessor_decision": reviews.get(predecessor) if predecessor else None,
        "allowed": allowed,
        "parameters_mutable": False,
        "automatic_production_activation": False,
    }


def build_fixed_challenger_rescan_asset(
    challenger: Mapping[str, object],
    asset: Mapping[str, object],
    raw_history: pd.DataFrame,
    *,
    research_split: str,
    cot_reports: Sequence[Mapping[str, object]] = (),
    cot_mapping: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Rebuild one asset from frozen OHLCV for Validation or Holdout."""
    split = str(research_split)
    if split not in {"validation", "holdout"}:
        raise BroadResearchContractError("Historischer Challenger-Rescan ist nur für Validation/Holdout erlaubt.")
    dataset_fingerprint = str(challenger.get("dataset_fingerprint") or "")
    if not dataset_fingerprint:
        raise BroadResearchContractError("Challenger besitzt keinen Frozen-Datensatzfingerprint.")
    symbol = str(asset.get("ticker") or "").upper()
    rebuilt = build_asset_broad_research(
        symbol,
        asset,
        raw_history,
        dataset_fingerprint=dataset_fingerprint,
        cot_reports=cot_reports,
        cot_mapping=cot_mapping,
    )
    labels = {str(row["candidate_id"]): row for row in rebuilt.get("labels") or []}
    experiments = {
        str(row["candidate_id"]): row for row in rebuilt.get("counterfactuals") or []
    }
    trades = []
    for candidate in rebuilt.get("candidates") or []:
        if str(candidate.get("research_split")) != split or not fixed_challenger_rule_matches(
            candidate, dict(challenger.get("rule") or {})
        ):
            continue
        candidate_id = str(candidate["candidate_id"])
        experiment = dict(experiments.get(candidate_id) or {})
        selected = dict(
            dict(dict(experiment.get("results") or {}).get("pullback_low_atr_buffer") or {})
            .get("exits", {})
            .get("fixed_2r", {})
        )
        label = dict(labels.get(candidate_id) or {})
        feature = dict(candidate.get("feature") or {})
        technical = dict(feature.get("technical") or {})
        feature_asset = dict(feature.get("asset") or {})
        trades.append(
            {
                "challenger_version": str(challenger.get("challenger_version") or ""),
                "challenger_fingerprint": str(challenger.get("challenger_fingerprint") or ""),
                "candidate_id": candidate_id,
                "candidate_fingerprint": candidate.get("candidate_fingerprint"),
                "feature_fingerprint": dict(candidate.get("feature") or {}).get("feature_fingerprint"),
                "label_fingerprint": label.get("label_fingerprint"),
                "experiment_fingerprint": experiment.get("experiment_fingerprint"),
                "symbol": symbol,
                "signal_day": candidate.get("signal_day"),
                "research_split": split,
                "dependency_cluster": candidate.get("dependency_cluster"),
                "label_metrics": {
                    "mfe_pct": label.get("mfe_pct"),
                    "mae_pct": label.get("mae_pct"),
                    "time_to_mfe_sessions": label.get("time_to_mfe_sessions"),
                    "time_to_mae_sessions": label.get("time_to_mae_sessions"),
                },
                "segments": {
                    "asset_group": feature_asset.get("asset_type"),
                    "region": feature_asset.get("region"),
                    "setup": candidate.get("setup_family"),
                    "market_phase": technical.get("market_phase"),
                    "volatility_regime": technical.get("volatility_regime"),
                    "year": str(candidate.get("signal_day") or "")[:4],
                },
                "selected_result": selected,
                "rebuilt_from_frozen_ohlcv": True,
                "development_data_read": False,
                "parameters_changed": False,
                "automatic_production_activation": False,
            }
        )
    return {
        "challenger_version": str(challenger.get("challenger_version") or ""),
        "challenger_fingerprint": str(challenger.get("challenger_fingerprint") or ""),
        "dataset_fingerprint": dataset_fingerprint,
        "symbol": symbol,
        "research_split": split,
        "trades": trades,
        "rebuilt_candidates": len(rebuilt.get("candidates") or []),
        "selected_trades": len(trades),
        "full_history_rescan": True,
        "automatic_production_activation": False,
    }


def record_fixed_challenger_rescan_asset(
    result: Mapping[str, object],
    *,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    """Append one verified asset completion and its separate challenger trades."""
    initialize_broad_research_store(path)
    version = str(result.get("challenger_version") or "")
    split = str(result.get("research_split") or "")
    symbol = str(result.get("symbol") or "").upper()
    gate = challenger_allowed_stage(version, split, path)
    if not gate["allowed"]:
        raise BroadResearchContractError(f"Challenger-Stufe {split} ist noch gesperrt.")
    payload = {
        "challenger_version": version,
        "challenger_fingerprint": result.get("challenger_fingerprint"),
        "dataset_fingerprint": result.get("dataset_fingerprint"),
        "symbol": symbol,
        "research_split": split,
        "rebuilt_candidates": int(result.get("rebuilt_candidates") or 0),
        "selected_trades": int(result.get("selected_trades") or 0),
        "full_history_rescan": result.get("full_history_rescan") is True,
        "parameters_changed": False,
        "automatic_production_activation": False,
    }
    completion_fingerprint = _fingerprint(payload)
    completion_id = f"challenger-rescan-{completion_fingerprint[:32]}"
    inserted = 0
    with _connect(Path(path)) as connection:
        for raw_trade in result.get("trades") or []:
            trade = dict(raw_trade or {})
            candidate_id = str(trade.get("candidate_id") or "")
            candidate = connection.execute(
                "SELECT feature_fingerprint, research_split FROM broad_research_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if (
                candidate is None
                or str(candidate["feature_fingerprint"]) != str(trade.get("feature_fingerprint"))
                or str(candidate["research_split"]) != split
            ):
                raise BroadResearchContractError(
                    "Ground-up-Rescan stimmt nicht mit dem eingefrorenen Kandidatenbestand überein."
                )
            trade_fingerprint = _fingerprint(trade)
            trade_id = f"challenger-trade-{trade_fingerprint[:32]}"
            existing_trade = connection.execute(
                "SELECT trade_fingerprint FROM broad_research_challenger_trades WHERE trade_id=?",
                (trade_id,),
            ).fetchone()
            if existing_trade is not None and str(existing_trade[0]) != trade_fingerprint:
                raise BroadResearchContractError("Challenger-Trade ist abweichend belegt.")
            if existing_trade is None:
                connection.execute(
                    "INSERT INTO broad_research_challenger_trades VALUES (?, ?, ?, ?, ?, ?)",
                    (trade_id, version, candidate_id, split, _canonical_json(trade), trade_fingerprint),
                )
                inserted += 1
        existing_completion = connection.execute(
            "SELECT completion_fingerprint FROM broad_research_challenger_rescan_completions WHERE challenger_version=? AND symbol=? AND research_split=?",
            (version, symbol, split),
        ).fetchone()
        if existing_completion is not None and str(existing_completion[0]) != completion_fingerprint:
            raise BroadResearchContractError("Challenger-Assetabschluss ist abweichend belegt.")
        if existing_completion is None:
            connection.execute(
                "INSERT INTO broad_research_challenger_rescan_completions VALUES (?, ?, ?, ?, ?, ?)",
                (completion_id, version, symbol, split, _canonical_json(payload), completion_fingerprint),
            )
    return {
        **payload,
        "trades_inserted": inserted,
        "completion_id": completion_id,
        "completion_fingerprint": completion_fingerprint,
    }


def record_challenger_stage_review(
    challenger_version: str,
    stage: str,
    decision: str,
    metrics: Mapping[str, object],
    *,
    manual_confirmation: str,
    reviewed_at: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    """Append a manual stage decision; never activate production."""
    if manual_confirmation != "CONFIRM_CHALLENGER_STAGE_REVIEW":
        raise BroadResearchContractError("Explizite manuelle Stufenprüfung fehlt.")
    if decision not in {"approved_to_next_stage", "rejected"}:
        raise BroadResearchContractError("Ungültige Challenger-Stufenentscheidung.")
    gate = challenger_allowed_stage(challenger_version, stage, path)
    if not gate["allowed"]:
        raise BroadResearchContractError(f"Challenger-Stufe {stage} ist noch gesperrt.")
    challenger = _load_fixed_challenger(challenger_version, path)
    expected = int(challenger.get("expected_assets_per_historical_stage") or 0)
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        completed_assets = int(
            connection.execute(
                "SELECT COUNT(*) FROM broad_research_challenger_rescan_completions WHERE challenger_version=? AND research_split=?",
                (challenger_version, stage),
            ).fetchone()[0]
        )
    if stage in {"validation", "holdout"} and completed_assets != expected:
        raise BroadResearchContractError(
            f"Stufe {stage} ist noch nicht vollständig neu gerechnet: {completed_assets}/{expected}."
        )
    payload = {
        "challenger_version": challenger_version,
        "challenger_fingerprint": challenger.get("challenger_fingerprint"),
        "research_stage": stage,
        "decision": decision,
        "metrics": dict(metrics),
        "completed_assets": completed_assets,
        "expected_assets": expected if stage in {"validation", "holdout"} else None,
        "manual_confirmation": manual_confirmation,
        "reviewed_at": str(reviewed_at),
        "parameters_changed": False,
        "automatic_production_activation": False,
    }
    fingerprint = _fingerprint(payload)
    review_id = f"challenger-review-{fingerprint[:32]}"
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT review_fingerprint FROM broad_research_challenger_reviews WHERE challenger_version=? AND research_stage=?",
            (challenger_version, stage),
        ).fetchone()
        if existing is not None and str(existing[0]) != fingerprint:
            raise BroadResearchContractError("Challenger-Stufenprüfung ist bereits abweichend belegt.")
        if existing is None:
            connection.execute(
                "INSERT INTO broad_research_challenger_reviews VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, challenger_version, stage, decision, _canonical_json(payload), fingerprint),
            )
    return {**payload, "review_id": review_id, "review_fingerprint": fingerprint}


def completed_fixed_challenger_rescan_symbols(
    challenger_version: str,
    research_split: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> set[str]:
    initialize_broad_research_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT symbol FROM broad_research_challenger_rescan_completions WHERE challenger_version=? AND research_split=?",
            (str(challenger_version), str(research_split)),
        ).fetchall()
    return {str(row[0]).upper() for row in rows}


def fixed_challenger_stage_metrics(
    challenger_version: str,
    research_split: str,
    path: Path = DEFAULT_BROAD_RESEARCH_DB_PATH,
) -> dict[str, object]:
    """Report one sealed stage without opening a later stage."""
    initialize_broad_research_store(path)
    accumulator = _new_metric_accumulator()
    clusters: set[str] = set()
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT trade_json FROM broad_research_challenger_trades WHERE challenger_version=? AND research_split=? ORDER BY json_extract(trade_json, '$.signal_day'), trade_id",
            (str(challenger_version), str(research_split)),
        ).fetchall()
        for row in rows:
            trade = json.loads(row[0])
            selected = dict(trade.get("selected_result") or {})
            labels = dict(trade.get("label_metrics") or {})
            segments = {
                str(key): str(value or "Unbekannt")
                for key, value in dict(trade.get("segments") or {}).items()
            }
            _update_metric_accumulator(
                accumulator,
                result_r=_number(selected.get("result_r")),
                mfe_pct=_number(labels.get("mfe_pct")),
                mae_pct=_number(labels.get("mae_pct")),
                segments=segments,
            )
            clusters.add(str(trade.get("dependency_cluster") or trade.get("candidate_id")))
    metrics = _finalize_metric_accumulator(
        accumulator, effective_independent_cases=len(clusters)
    )
    return {
        "challenger_version": str(challenger_version),
        "research_split": str(research_split),
        **metrics,
        "parameters_mutable": False,
        "next_stage_opened": False,
        "automatic_production_activation": False,
    }
