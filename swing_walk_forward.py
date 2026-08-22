from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import unicodedata
from dataclasses import asdict, replace
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from swing_forward_evaluation import evaluate_swing_signal_bars
from swing_research_identity import (
    SWING_RESEARCH_IDENTITY_VERSION,
    default_swing_research_identity_map,
    derive_swing_research_identity,
)
from technical_analysis import calculate_indicators, detect_market_phase, value_or_none
from trading_assistant import DEFAULT_SWING_THRESHOLDS, evaluate_swing_trade


SWING_WALK_FORWARD_SCHEMA_VERSION = 3
SWING_WALK_FORWARD_ENGINE_VERSION = "swing-historical-research-2026.08.17-v6"
SWING_WALK_FORWARD_VERSION = SWING_WALK_FORWARD_ENGINE_VERSION
SWING_WALK_FORWARD_RESEARCH_CONTRACT = "swing-walk-forward-research-contract-2026.08.17-v5"
SWING_EVIDENCE_LINK_VERSION = "swing-historical-real-forward-link-2026.08.17-v1"
SWING_CASE_IDENTITY_RESOLUTION_VERSION = "swing-case-identity-resolution-2026.08.18-v1"
SWING_EVIDENCE_DEPENDENCY_VERSION = "swing-evidence-dependency-2026.08.18-v1"
SWING_OBSERVATIONAL_FEATURE_VERSION = "swing-observational-rsi-ema-2026.08.18-v1"
DEFAULT_RESEARCH_SPLIT_RATIOS = (0.60, 0.20, 0.20)
DEFAULT_MINIMUM_RESEARCH_OUTCOMES = 1_000
DEFAULT_MINIMUM_RESEARCH_SYMBOLS = 200
DEFAULT_MINIMUM_HOLDOUT_OUTCOMES = 200
DEFAULT_MINIMUM_SEGMENT_OUTCOMES = 50
SELECTION_ROUND_ROLES = {
    "exploration",
    "locked_validation",
    "final_confirmation",
    "monitoring",
}
DEFAULT_SWING_WALK_FORWARD_DB_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_SWING_WALK_FORWARD_DB_PATH",
        Path(__file__).resolve().parent / "runtime" / "swing_walk_forward.sqlite3",
    )
)


TECHNICAL_CHALLENGER_PROFILE_NAMES = (
    "long_v1_rsi_wide",
    "long_v1_rsi_core",
    "long_v1_ema_trend",
    "long_v1_ema_strict",
    "long_v1_ema_rsi_wide",
    "long_v1_ema_rsi_core",
    "long_v1_pullback_only",
    "long_v1_breakout_only",
)


def _strategy_profile_version(
    name: str,
    thresholds: object,
    technical_filter: Mapping[str, object] | None = None,
) -> str:
    payload = {
        "name": str(name),
        "thresholds": asdict(thresholds),
        "engine": SWING_WALK_FORWARD_ENGINE_VERSION,
    }
    # Existing baseline identities deliberately remain byte-for-byte unchanged.
    if technical_filter:
        payload["technical_filter"] = dict(technical_filter)
    return f"swing-research-{str(name).strip().lower()}-{_fingerprint(payload)[:12]}"


def swing_walk_forward_strategy_profiles(
    names: Sequence[str] | None = None,
) -> dict[str, dict]:
    """Return explicit research-only profiles; none can activate production rules."""
    requested = tuple(names or ("current",))
    definitions = {
        "current": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_baseline",
            "variant": "unchanged",
            "technical_filter": {},
        },
        "balanced": {
            "thresholds": replace(
                DEFAULT_SWING_THRESHOLDS,
                min_buy_signal=6.0,
                min_confidence=6.0,
                min_crv=2.2,
            ),
            "family": "legacy_threshold_hypothesis",
            "variant": "balanced",
            "technical_filter": {},
        },
        "precision": {
            "thresholds": replace(
                DEFAULT_SWING_THRESHOLDS,
                min_buy_signal=6.3,
                min_confidence=6.2,
                min_crv=2.0,
            ),
            "family": "legacy_threshold_hypothesis",
            "variant": "precision",
            "technical_filter": {},
        },
        "payoff": {
            "thresholds": replace(
                DEFAULT_SWING_THRESHOLDS,
                min_buy_signal=5.8,
                min_confidence=5.8,
                min_crv=2.6,
            ),
            "family": "legacy_threshold_hypothesis",
            "variant": "payoff",
            "technical_filter": {},
        },
        "long_v1_rsi_wide": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_plus_rsi",
            "variant": "rsi_40_72",
            "technical_filter": {"rsi_min": 40.0, "rsi_max": 72.0},
        },
        "long_v1_rsi_core": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_plus_rsi",
            "variant": "rsi_45_68",
            "technical_filter": {"rsi_min": 45.0, "rsi_max": 68.0},
        },
        "long_v1_ema_trend": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_plus_ema",
            "variant": "ema20_above_ema50",
            "technical_filter": {"ema20_above_ema50": True},
        },
        "long_v1_ema_strict": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_plus_ema",
            "variant": "close_above_ema20_above_ema50",
            "technical_filter": {
                "ema20_above_ema50": True,
                "close_above_ema20": True,
            },
        },
        "long_v1_ema_rsi_wide": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_plus_ema_rsi",
            "variant": "ema_trend_rsi_40_72",
            "technical_filter": {
                "ema20_above_ema50": True,
                "rsi_min": 40.0,
                "rsi_max": 72.0,
            },
        },
        "long_v1_ema_rsi_core": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_plus_ema_rsi",
            "variant": "close_ema_trend_rsi_45_68",
            "technical_filter": {
                "ema20_above_ema50": True,
                "close_above_ema20": True,
                "rsi_min": 45.0,
                "rsi_max": 68.0,
            },
        },
        "long_v1_pullback_only": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_setup_type",
            "variant": "pullback_only",
            "technical_filter": {"setup_type_contains": "Pullback"},
        },
        "long_v1_breakout_only": {
            "thresholds": DEFAULT_SWING_THRESHOLDS,
            "family": "long_v1_setup_type",
            "variant": "breakout_only",
            "technical_filter": {"setup_type_contains": "Ausbruch"},
        },
    }
    unknown = sorted(set(requested) - set(definitions))
    if unknown:
        raise ValueError(f"Unbekannte Walk-Forward-Forschungsprofile: {', '.join(unknown)}")
    profiles: dict[str, dict] = {}
    for name in requested:
        definition = definitions[name]
        thresholds = definition["thresholds"]
        technical_filter = dict(definition["technical_filter"])
        version = _strategy_profile_version(name, thresholds, technical_filter)
        profiles[version] = {
            "name": name,
            "version": version,
            "thresholds": thresholds,
            "thresholds_snapshot": asdict(thresholds),
            "strategy_family": str(definition["family"]),
            "parameter_variant": str(definition["variant"]),
            "technical_filter": technical_filter,
            "baseline_strategy": "current",
            "research_only": True,
            "automatic_production_activation": False,
        }
    return profiles


def _clean(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return _clean(item())
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return value


def _canonical_json(payload: dict) -> str:
    return json.dumps(
        _clean(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _valid_bars(raw: pd.DataFrame) -> pd.DataFrame:
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not isinstance(raw, pd.DataFrame) or raw.empty or not required.issubset(raw.columns):
        return pd.DataFrame()
    frame = raw.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame.loc[~frame.index.isna()].sort_index()
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["Open", "High", "Low", "Close"])


def _prepare_historical_indicators(raw: pd.DataFrame) -> pd.DataFrame:
    """Calculate trailing indicators once; every value remains causal at its row."""
    frame = calculate_indicators(raw, "1d")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    frame["EMA_20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    frame["EMA_50"] = close.ewm(span=50, adjust=False, min_periods=50).mean()
    if "ATR_14" not in frame and {"High", "Low", "Close"}.issubset(frame.columns):
        high = pd.to_numeric(frame["High"], errors="coerce")
        low = pd.to_numeric(frame["Low"], errors="coerce")
        close = pd.to_numeric(frame["Close"], errors="coerce")
        previous_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
            axis=1,
        ).max(axis=1)
        frame["ATR_14"] = true_range.rolling(14).mean()
    return frame


def _safe_relative_value(numerator: object, denominator: object) -> float | None:
    numerator_value = value_or_none(numerator)
    denominator_value = value_or_none(denominator)
    if numerator_value is None or denominator_value in {None, 0}:
        return None
    return float(numerator_value) / float(denominator_value)


def _relative_position(left: object, right: object) -> str:
    left_value = value_or_none(left)
    right_value = value_or_none(right)
    if left_value is None or right_value is None:
        return "Nicht verfügbar"
    return "Über" if float(left_value) > float(right_value) else "Unter/gleich"


def _observational_rsi_ema_features(case: Mapping[str, object]) -> dict:
    """Build a deterministic signal-bar-only sidecar without changing the case."""
    snapshot = dict(case.get("snapshot") or {})
    signal_features = dict(snapshot.get("signal_features") or {})
    close = value_or_none(signal_features.get("close"))
    rsi_14 = value_or_none(signal_features.get("rsi_14"))
    ema_20 = value_or_none(signal_features.get("ema_20"))
    ema_50 = value_or_none(signal_features.get("ema_50"))
    close_to_ema20 = _safe_relative_value(close, ema_20)
    close_to_ema50 = _safe_relative_value(close, ema_50)
    ema20_to_ema50 = _safe_relative_value(ema_20, ema_50)
    stacked = (
        None
        if close is None or ema_20 is None or ema_50 is None
        else bool(float(close) > float(ema_20) > float(ema_50))
    )
    return {
        "feature_version": SWING_OBSERVATIONAL_FEATURE_VERSION,
        "signal_at": str(case.get("signal_at") or snapshot.get("signal_at") or ""),
        "causal_cutoff": "including_completed_signal_bar",
        "future_bars_used": 0,
        "source_pass": "existing_historical_indicator_pass",
        "values": {
            "rsi_14": rsi_14,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "close": close,
            "close_relative_to_ema20": close_to_ema20,
            "close_relative_to_ema50": close_to_ema50,
            "ema20_relative_to_ema50": ema20_to_ema50,
            "close_distance_to_ema20": (
                close_to_ema20 - 1.0 if close_to_ema20 is not None else None
            ),
            "close_distance_to_ema50": (
                close_to_ema50 - 1.0 if close_to_ema50 is not None else None
            ),
            "ema20_distance_to_ema50": (
                ema20_to_ema50 - 1.0 if ema20_to_ema50 is not None else None
            ),
            "close_position_vs_ema20": _relative_position(close, ema_20),
            "close_position_vs_ema50": _relative_position(close, ema_50),
            "ema20_position_vs_ema50": _relative_position(ema_20, ema_50),
            "close_above_ema20_above_ema50": stacked,
        },
        "baseline_filtering": False,
        "trade_selection_changed": False,
        "automatic_rule_change": False,
    }


def _technical_challenger_filter(
    history: pd.DataFrame,
    assessment: Mapping[str, object],
    technical_filter: Mapping[str, object] | None,
) -> tuple[bool, dict]:
    """Apply only point-in-time values from the signal bar; future bars are inaccessible."""
    rules = dict(technical_filter or {})
    latest = history.iloc[-1]
    values = {
        "close": value_or_none(latest.get("Close")),
        "rsi_14": value_or_none(latest.get("RSI_14")),
        "ema_20": value_or_none(latest.get("EMA_20")),
        "ema_50": value_or_none(latest.get("EMA_50")),
        "setup_type": str(assessment.get("setup_type") or ""),
    }
    passed = True
    if "rsi_min" in rules:
        passed = passed and values["rsi_14"] is not None and float(values["rsi_14"]) >= float(rules["rsi_min"])
    if "rsi_max" in rules:
        passed = passed and values["rsi_14"] is not None and float(values["rsi_14"]) <= float(rules["rsi_max"])
    if rules.get("ema20_above_ema50"):
        passed = passed and values["ema_20"] is not None and values["ema_50"] is not None and float(values["ema_20"]) > float(values["ema_50"])
    if rules.get("close_above_ema20"):
        passed = passed and values["close"] is not None and values["ema_20"] is not None and float(values["close"]) > float(values["ema_20"])
    setup_marker = str(rules.get("setup_type_contains") or "")
    if setup_marker:
        passed = passed and setup_marker.casefold() in str(values["setup_type"]).casefold()
    return bool(passed), values


def _technical_scores(history: pd.DataFrame) -> tuple[pd.DataFrame, str, float, float, str]:
    required = {"RSI_14", "MACD", "MACD_Signal", "SMA_50", "SMA_200", "Volatility"}
    frame = history.copy() if required.issubset(history.columns) else _prepare_historical_indicators(history)
    phase = detect_market_phase(frame)
    latest = frame.iloc[-1]
    close = float(latest["Close"])
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    macd = value_or_none(latest.get("MACD"))
    macd_signal = value_or_none(latest.get("MACD_Signal"))
    rsi = value_or_none(latest.get("RSI_14"))
    buy_signal = 4.5
    buy_signal += {
        "Bullenmarkt": 1.3,
        "Korrektur innerhalb eines Aufwärtstrends": 0.9,
        "Bodenbildungsphase": 0.2,
        "Seitwärtsmarkt": 0.0,
        "Bärenmarkt": -1.0,
    }.get(phase.phase, 0.0)
    if sma_50 is not None and close > sma_50:
        buy_signal += 0.6
    if sma_50 is not None and sma_200 is not None and sma_50 > sma_200:
        buy_signal += 0.6
    if macd is not None and macd_signal is not None and macd > macd_signal:
        buy_signal += 0.4
    if rsi is not None and 42 <= rsi <= 72:
        buy_signal += 0.3
    history_coverage = min(len(frame) / 260, 1.0)
    missing_ratio = float(frame[["Open", "High", "Low", "Close"]].isna().mean().mean())
    confidence = 5.2 + history_coverage * 1.4 - min(missing_ratio * 5, 1.0)
    volatility = value_or_none(latest.get("Volatility"))
    volatility_regime = (
        "Nicht verfügbar"
        if volatility is None
        else "Hoch"
        if volatility >= 0.45
        else "Mittel"
        if volatility >= 0.25
        else "Niedrig"
    )
    return frame, phase.phase, round(max(0.0, min(buy_signal, 10.0)), 3), round(
        max(0.0, min(confidence, 10.0)), 3
    ), volatility_regime


def historical_technical_shadow_assessment(
    symbol: str,
    history: pd.DataFrame,
    *,
    asset_type: str = "Aktie",
    region: str = "USA",
    thresholds=DEFAULT_SWING_THRESHOLDS,
    strategy_profile: Mapping[str, object] | None = None,
) -> dict:
    """Build a deliberately limited point-in-time technical case without current fundamentals."""
    frame, market_phase, buy_signal, confidence, volatility_regime = _technical_scores(history)
    signal_timestamp = pd.Timestamp(frame.index[-1])
    signal_day = signal_timestamp.date()
    observed_at = datetime.combine(signal_day, time(23, 59), tzinfo=timezone.utc)
    assessment = evaluate_swing_trade(
        frame,
        symbol=symbol,
        asset_name=symbol,
        asset_type=asset_type,
        market_phase=market_phase,
        buy_signal=buy_signal,
        asset_quality=5.0,
        confidence=confidence,
        market_score=5.0,
        fx_rate=1.0,
        original_currency="EUR",
        region=region,
        historical_cases=0,
        historical_hit_rate=None,
        event_date=None,
        now=observed_at,
        thresholds=thresholds,
    )
    profile = dict(strategy_profile or {})
    assessment["research_strategy_name"] = str(profile.get("name") or "current")
    assessment["research_strategy_version"] = str(
        profile.get("version") or _strategy_profile_version("current", thresholds)
    )
    assessment["volatility_regime"] = volatility_regime
    assessment["historical_evidence_kind"] = "historical_technical_shadow"
    assessment["production_comparable"] = False
    assessment["limitations"] = [
        "Keine Point-in-Time-Fundamentaldaten",
        "Keine Point-in-Time-News oder Earnings",
        "Neutrales historisches Makroumfeld",
        "Keine Trade-Republic-Ausführungsdaten",
        "Kein Ersatz für echte Forward-Ergebnisse",
    ]
    return assessment


def _terminal_event(events: list[dict]) -> dict | None:
    terminal_types = {
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
        "target_1_reached",
        "target_2_reached",
        "stop_reached",
        "ambiguous_sequence",
    }
    candidates = [
        event
        for event in events
        if event.get("event_type") in terminal_types
        and not (
            event.get("event_type") == "target_1_reached"
            and (event.get("payload") or {}).get("terminal") is False
        )
    ]
    return candidates[-1] if candidates else None


def _frame_fingerprint(symbol: str, frame: pd.DataFrame) -> str:
    normalized = frame.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
    normalized.index = pd.to_datetime(normalized.index, errors="raise")
    if getattr(normalized.index, "tz", None) is not None:
        normalized.index = normalized.index.tz_convert("UTC").tz_localize(None)
    for column in normalized.columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="raise").astype("float64")
    hashed = pd.util.hash_pandas_object(normalized, index=True).to_numpy(dtype="uint64")
    digest = hashlib.sha256()
    digest.update(str(symbol).encode("utf-8"))
    digest.update(hashed.tobytes())
    return digest.hexdigest()


def _research_split_boundaries(
    frames: Mapping[str, pd.DataFrame],
    *,
    minimum_history_rows: int,
    future_sessions: int,
    step_sessions: int,
) -> dict[str, str | None]:
    possible_dates: set[pd.Timestamp] = set()
    for frame in frames.values():
        if len(frame) < minimum_history_rows + future_sessions:
            continue
        # Boundaries describe the complete historical calendar, not only the first
        # date on which this particular asset already has enough warm-up rows.
        # This keeps the split independent from listing age and from future outcomes.
        positions = range(0, len(frame) - future_sessions, step_sessions)
        possible_dates.update(pd.Timestamp(frame.index[position]).normalize() for position in positions)
    ordered = sorted(possible_dates)
    if len(ordered) < 3:
        return {"development_end": None, "validation_end": None, "last_signal_day": None}
    development_index = min(max(int(len(ordered) * DEFAULT_RESEARCH_SPLIT_RATIOS[0]) - 1, 0), len(ordered) - 1)
    validation_index = min(
        max(
            int(len(ordered) * sum(DEFAULT_RESEARCH_SPLIT_RATIOS[:2])) - 1,
            development_index + 1,
        ),
        len(ordered) - 1,
    )
    return {
        "development_end": ordered[development_index].date().isoformat(),
        "validation_end": ordered[validation_index].date().isoformat(),
        "last_signal_day": ordered[-1].date().isoformat(),
    }


def _assign_research_split(
    signal_day: object,
    outcome_day: object,
    boundaries: Mapping[str, object],
) -> str | None:
    signal = pd.Timestamp(signal_day).normalize()
    outcome = pd.Timestamp(outcome_day).normalize()
    development_end = boundaries.get("development_end")
    validation_end = boundaries.get("validation_end")
    last_signal_day = boundaries.get("last_signal_day")
    if not development_end or not validation_end:
        return None
    if last_signal_day and signal > pd.Timestamp(last_signal_day):
        return None
    development_boundary = pd.Timestamp(development_end)
    validation_boundary = pd.Timestamp(validation_end)
    if signal <= development_boundary:
        return "development" if outcome <= development_boundary else None
    if signal <= validation_boundary:
        return "validation" if outcome <= validation_boundary else None
    return "holdout"


def _split_balanced_cutoff_positions(
    symbol: str,
    frame: pd.DataFrame,
    *,
    minimum_history_rows: int,
    future_sessions: int,
    step_sessions: int,
    split_boundaries: Mapping[str, object],
    sampling_mode: str = "balanced_history",
) -> list[int]:
    """Distribute a small per-symbol sample across time splits without using outcomes."""
    if sampling_mode not in {"balanced_history", "recent_incremental"}:
        raise ValueError(f"Unbekannter Walk-Forward-Samplingmodus: {sampling_mode}")
    groups: dict[str, dict[int, list[int]]] = {
        "development": {},
        "validation": {},
        "holdout": {},
    }
    for position in range(
        minimum_history_rows - 1,
        len(frame) - future_sessions,
        step_sessions,
    ):
        split = _assign_research_split(
            frame.index[position],
            frame.index[position + future_sessions],
            split_boundaries,
        )
        if split is not None:
            year = int(pd.Timestamp(frame.index[position]).year)
            groups[split].setdefault(year, []).append(position)
    if sampling_mode == "recent_incremental":
        return sorted(
            [position for years in groups.values() for positions in years.values() for position in positions],
            reverse=True,
        )
    year_offsets = {split: 0 for split in groups}
    ordered: list[int] = []
    while any(any(years.values()) for years in groups.values()):
        for split in ("development", "validation", "holdout"):
            available_years = [
                year for year in sorted(groups[split]) if groups[split][year]
            ]
            if not available_years:
                continue
            offset = year_offsets[split] % len(available_years)
            year = available_years[offset]
            ordered.append(groups[split][year].pop(0))
            year_offsets[split] += 1
    return ordered


def _selection_round_label(selection_round: int) -> str:
    index = max(int(selection_round), 0)
    return chr(ord("A") + index) if index < 26 else f"R{index + 1}"


def _balanced_case_limit(cases: list[dict], maximum_cases: int) -> list[dict]:
    """Cap deterministically without letting the first alphabetic symbols dominate."""
    if len(cases) <= maximum_cases:
        return cases
    groups: dict[tuple[str, str], list[dict]] = {}
    for case in cases:
        strategy = str(((case.get("snapshot") or {}).get("strategy") or {}).get("strategy_version") or "")
        groups.setdefault((strategy, str(case.get("symbol") or "")), []).append(case)
    for values in groups.values():
        values.sort(key=lambda item: hashlib.sha256(str(item["case_id"]).encode("utf-8")).hexdigest())
    selected: list[dict] = []
    keys = sorted(groups)
    while len(selected) < maximum_cases:
        progressed = False
        for key in keys:
            values = groups[key]
            if not values:
                continue
            selected.append(values.pop(0))
            progressed = True
            if len(selected) >= maximum_cases:
                break
        if not progressed:
            break
    return sorted(selected, key=lambda item: (str(item.get("signal_at") or ""), str(item.get("symbol") or "")))


def _wilson_interval(wins: int, total: int) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    z = 1.959963984540054
    probability = wins / total
    denominator = 1 + z**2 / total
    center = (probability + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(
        probability * (1 - probability) / total + z**2 / (4 * total**2)
    ) / denominator
    return max(0.0, center - margin) * 100, min(1.0, center + margin) * 100


def _case_research_identity(case: Mapping[str, object]) -> dict:
    stored = dict(case.get("research_identity") or {})
    snapshot = dict(case.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    if not stored and (asset.get("issuer_id") or asset.get("company_id")):
        stored = asset
    if stored.get("issuer_id") and stored.get("listing_id"):
        return stored
    ticker = str(case.get("symbol") or asset.get("ticker") or "").strip().upper()
    legacy = default_swing_research_identity_map().get(ticker)
    if legacy:
        return dict(legacy)
    return derive_swing_research_identity(
        {
            **asset,
            "ticker": ticker,
            "asset_type": asset.get("asset_type") or "Aktie",
        }
    )


def _case_dependency_clusters(cases: Sequence[Mapping[str, object]]) -> list[dict]:
    grouped: dict[tuple[str, str, int], list[dict]] = {}
    for case in cases:
        identity = _case_research_identity(case)
        snapshot = dict(case.get("snapshot") or {})
        strategy = dict(snapshot.get("strategy") or {})
        signal_day = pd.to_datetime(str(case.get("signal_at") or "")[:10], errors="coerce")
        future_day = pd.to_datetime(case.get("future_last_day"), errors="coerce")
        if pd.isna(signal_day):
            signal_day = pd.Timestamp.min
        if pd.isna(future_day) or future_day < signal_day:
            future_day = signal_day
        issuer_id = str(identity.get("issuer_id") or identity.get("listing_id") or "")
        economic_instrument_id = str(identity.get("economic_instrument_id") or "")
        strategy_version = str(strategy.get("strategy_version") or "legacy_unspecified")
        research_split = str(case.get("research_split") or "legacy_unspecified")
        horizon = int(case.get("evaluation_horizon_sessions") or 0)
        dependency_tokens = {f"issuer:{issuer_id}"}
        if economic_instrument_id:
            dependency_tokens.add(f"instrument:{economic_instrument_id}")
        grouped.setdefault((strategy_version, research_split, horizon), []).append(
            {
                "case": case,
                "identity": identity,
                "issuer_id": issuer_id,
                "economic_instrument_id": economic_instrument_id,
                "dependency_tokens": dependency_tokens,
                "start": signal_day,
                "end": future_day,
            }
        )

    clusters: list[dict] = []
    for context, members in sorted(grouped.items(), key=lambda item: item[0]):
        ordered = sorted(
            members,
            key=lambda member: (
                member["start"],
                member["end"],
                str(member["case"].get("case_id") or ""),
            ),
        )
        parents = list(range(len(ordered)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        active_by_token: dict[str, tuple[int, pd.Timestamp]] = {}
        for index, member in enumerate(ordered):
            for token in member["dependency_tokens"]:
                active = active_by_token.get(token)
                if active is not None and member["start"] <= active[1]:
                    union(index, active[0])
            for token in member["dependency_tokens"]:
                active = active_by_token.get(token)
                maximum_end = max(active[1], member["end"]) if active is not None else member["end"]
                active_by_token[token] = (find(index), maximum_end)

        components_by_root: dict[int, list[dict]] = {}
        for index, member in enumerate(ordered):
            components_by_root.setdefault(find(index), []).append(member)
        for component in components_by_root.values():
            listing_ids = sorted(
                {
                    str(member["identity"].get("listing_id") or "")
                    for member in component
                    if str(member["identity"].get("listing_id") or "")
                }
            )
            symbols = sorted(
                {
                    str(member["case"].get("symbol") or "")
                    for member in component
                    if str(member["case"].get("symbol") or "")
                }
            )
            raw_results = [
                float(member["case"]["result_r"])
                for member in component
                if member["case"].get("result_r") is not None
            ]
            issuer_ids = sorted({str(member["issuer_id"]) for member in component})
            economic_instrument_ids = sorted(
                {
                    str(member["economic_instrument_id"])
                    for member in component
                    if str(member["economic_instrument_id"])
                }
            )
            dependency_entity_id = (
                issuer_ids[0]
                if len(issuer_ids) == 1
                else _fingerprint(
                    {
                        "version": SWING_EVIDENCE_DEPENDENCY_VERSION,
                        "issuer_ids": issuer_ids,
                        "economic_instrument_ids": economic_instrument_ids,
                    }
                )
            )
            cluster_seed = {
                "version": SWING_EVIDENCE_DEPENDENCY_VERSION,
                "issuer_ids": issuer_ids,
                "economic_instrument_ids": economic_instrument_ids,
                "strategy_version": context[0],
                "research_split": context[1],
                "evaluation_horizon_sessions": context[2],
                "first_signal_day": component[0]["start"].date().isoformat()
                if component[0]["start"] != pd.Timestamp.min
                else None,
                "last_outcome_day": max(member["end"] for member in component).date().isoformat()
                if component[0]["start"] != pd.Timestamp.min
                else None,
                "case_ids": sorted(str(member["case"].get("case_id") or "") for member in component),
            }
            clusters.append(
                {
                    "cluster_id": _fingerprint(cluster_seed),
                    "issuer_id": dependency_entity_id,
                    "issuer_ids": issuer_ids,
                    "economic_instrument_ids": economic_instrument_ids,
                    "listing_ids": listing_ids,
                    "symbols": symbols,
                    "case_ids": [
                        str(member["case"].get("case_id") or "") for member in component
                    ],
                    "raw_cases": len(component),
                    "effective_independent_cases": 1,
                    "dependent_listings": len(listing_ids) > 1,
                    "result_r_for_inference": (
                        sum(raw_results) / len(raw_results) if raw_results else None
                    ),
                }
            )
    return clusters


def swing_walk_forward_case_metrics(cases: Sequence[Mapping[str, object]]) -> dict:
    evaluated = [case for case in cases if case.get("result_r") is not None]
    results = [float(case["result_r"]) for case in evaluated]
    wins = [value for value in results if value > 0]
    losses = [value for value in results if value <= 0]
    lower, upper = _wilson_interval(len(wins), len(results))
    cumulative = 0.0
    peak = 0.0
    maximum_drawdown = 0.0
    maximum_losing_streak = 0
    losing_streak = 0
    for case in sorted(evaluated, key=lambda item: (str(item.get("signal_at") or ""), str(item.get("symbol") or ""))):
        cumulative += float(case["result_r"])
        peak = max(peak, cumulative)
        maximum_drawdown = min(maximum_drawdown, cumulative - peak)
        if float(case["result_r"]) <= 0:
            losing_streak += 1
            maximum_losing_streak = max(maximum_losing_streak, losing_streak)
        else:
            losing_streak = 0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    all_dependency_clusters = _case_dependency_clusters(cases)
    dependency_clusters = _case_dependency_clusters(evaluated)
    effective_results = [
        float(cluster["result_r_for_inference"])
        for cluster in dependency_clusters
        if cluster.get("result_r_for_inference") is not None
    ]
    effective_wins = [value for value in effective_results if value > 0]
    effective_lower, effective_upper = _wilson_interval(
        len(effective_wins), len(effective_results)
    )
    dependent_clusters = [
        cluster for cluster in dependency_clusters if cluster["dependent_listings"]
    ]
    issuer_ids = {
        str(cluster.get("issuer_id") or "")
        for cluster in dependency_clusters
        if str(cluster.get("issuer_id") or "")
    }
    return {
        "cases": len(cases),
        "raw_cases": len(cases),
        "evaluated": len(results),
        "raw_evaluated": len(results),
        "effective_independent_cases": len(all_dependency_clusters),
        "effective_independent_evaluated": len(effective_results),
        "wins": len(wins),
        "losses": len(losses),
        "hit_rate_pct": len(wins) / len(results) * 100 if results else None,
        "hit_rate_wilson_low_pct": lower,
        "hit_rate_wilson_high_pct": upper,
        "average_r": sum(results) / len(results) if results else None,
        "median_r": float(np.median(results)) if results else None,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "maximum_drawdown_r": abs(maximum_drawdown),
        "maximum_losing_streak": maximum_losing_streak,
        "positive_expectancy": bool(results and sum(results) / len(results) > 0),
        "symbols": len({str(case.get("symbol") or "") for case in evaluated}),
        "issuer_clusters": len(issuer_ids),
        "signal_days": len({str(case.get("signal_at") or "")[:10] for case in evaluated}),
        "dependency_adjustment_required": len(effective_results) < len(results),
        "dependent_listing_clusters": len(dependent_clusters),
        "dependent_listing_raw_cases": sum(
            int(cluster["raw_cases"]) for cluster in dependent_clusters
        ),
        "independence_adjusted_hit_rate_pct": (
            len(effective_wins) / len(effective_results) * 100 if effective_results else None
        ),
        "independence_adjusted_hit_rate_wilson_low_pct": effective_lower,
        "independence_adjusted_hit_rate_wilson_high_pct": effective_upper,
        "dependency_contract_version": SWING_EVIDENCE_DEPENDENCY_VERSION,
        "raw_trade_metrics_unchanged": True,
    }


def _segmented_case_metrics(
    cases: Sequence[Mapping[str, object]],
    *,
    label: str,
    value_getter,
) -> list[dict]:
    groups: dict[str, list[Mapping[str, object]]] = {}
    for case in cases:
        value = str(value_getter(case) or "Unbekannt")
        groups.setdefault(value, []).append(case)
    return [
        {label: value, **swing_walk_forward_case_metrics(group)}
        for value, group in sorted(groups.items())
    ]


def swing_walk_forward_research_readiness(
    cases: Sequence[Mapping[str, object]],
    *,
    minimum_outcomes: int = DEFAULT_MINIMUM_RESEARCH_OUTCOMES,
    minimum_symbols: int = DEFAULT_MINIMUM_RESEARCH_SYMBOLS,
    minimum_holdout_outcomes: int = DEFAULT_MINIMUM_HOLDOUT_OUTCOMES,
    minimum_segment_outcomes: int = DEFAULT_MINIMUM_SEGMENT_OUTCOMES,
) -> dict:
    eligible_cases = [case for case in cases if case.get("selection_eligible", True)]
    metrics = swing_walk_forward_case_metrics(eligible_cases)
    evaluated = [case for case in eligible_cases if case.get("result_r") is not None]
    split_counts = {
        split: sum(1 for case in evaluated if case.get("research_split") == split)
        for split in ("development", "validation", "holdout")
    }
    effective_split_counts = {
        split: swing_walk_forward_case_metrics(
            [case for case in evaluated if case.get("research_split") == split]
        )["effective_independent_evaluated"]
        for split in ("development", "validation", "holdout")
    }
    phase_counts: dict[str, int] = {}
    asset_type_counts: dict[str, int] = {}
    volatility_counts: dict[str, int] = {}
    for case in evaluated:
        snapshot = dict(case.get("snapshot") or {})
        strategy = dict(snapshot.get("strategy") or {})
        asset = dict(snapshot.get("asset") or {})
        phase = str(strategy.get("market_phase") or "Unbekannt")
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        asset_type = str(asset.get("asset_type") or "Unbekannt")
        asset_type_counts[asset_type] = asset_type_counts.get(asset_type, 0) + 1
        volatility = str(strategy.get("volatility_regime") or "Unbekannt")
        volatility_counts[volatility] = volatility_counts.get(volatility, 0) + 1
    represented_phases = {phase: count for phase, count in phase_counts.items() if phase != "Unbekannt"}
    represented_asset_types = {
        value: count for value, count in asset_type_counts.items() if value != "Unbekannt"
    }
    represented_volatility = {
        value: count for value, count in volatility_counts.items() if value != "Unbekannt"
    }
    effective_phase_counts = {
        phase: swing_walk_forward_case_metrics(
            [
                case
                for case in evaluated
                if str(((case.get("snapshot") or {}).get("strategy") or {}).get("market_phase") or "Unbekannt")
                == phase
            ]
        )["effective_independent_evaluated"]
        for phase in represented_phases
    }
    effective_asset_type_counts = {
        asset_type: swing_walk_forward_case_metrics(
            [
                case
                for case in evaluated
                if str(((case.get("snapshot") or {}).get("asset") or {}).get("asset_type") or "Unbekannt")
                == asset_type
            ]
        )["effective_independent_evaluated"]
        for asset_type in represented_asset_types
    }
    effective_volatility_counts = {
        volatility: swing_walk_forward_case_metrics(
            [
                case
                for case in evaluated
                if str(((case.get("snapshot") or {}).get("strategy") or {}).get("volatility_regime") or "Unbekannt")
                == volatility
            ]
        )["effective_independent_evaluated"]
        for volatility in represented_volatility
    }
    segments_ready = (
        len(effective_phase_counts) >= 2
        and bool(effective_asset_type_counts)
        and bool(effective_volatility_counts)
        and all(
            count >= minimum_segment_outcomes
            for count in (
                *effective_phase_counts.values(),
                *effective_asset_type_counts.values(),
                *effective_volatility_counts.values(),
            )
        )
    )
    overlap_safe = all(bool(case.get("overlap_purged")) for case in evaluated)
    adjusted_prices = all(
        str((((case.get("snapshot") or {}).get("evidence") or {}).get("price_adjustment") or ""))
        == "yfinance_auto_adjust_true"
        for case in evaluated
    )
    ready = bool(
        metrics["effective_independent_evaluated"] >= minimum_outcomes
        and metrics["issuer_clusters"] >= minimum_symbols
        and effective_split_counts["validation"] >= minimum_holdout_outcomes
        and effective_split_counts["holdout"] >= minimum_holdout_outcomes
        and segments_ready
        and overlap_safe
        and adjusted_prices
    )
    return {
        "status": "technical_challenger_review_ready" if ready else "collecting",
        "technical_challenger_review_allowed": ready,
        "full_swing_trader_change_allowed": False,
        "production_activation_allowed": False,
        "automatic_rule_change": False,
        "evaluated": metrics["evaluated"],
        "raw_evaluated": metrics["raw_evaluated"],
        "effective_independent_evaluated": metrics["effective_independent_evaluated"],
        "dependency_adjustment_required": metrics["dependency_adjustment_required"],
        "dependent_listing_clusters": metrics["dependent_listing_clusters"],
        "minimum_outcomes": minimum_outcomes,
        "minimum_outcomes_basis": "effective_independent_evaluated",
        "symbols": metrics["symbols"],
        "issuer_clusters": metrics["issuer_clusters"],
        "minimum_symbols": minimum_symbols,
        "minimum_symbols_basis": "issuer_clusters",
        "split_counts": split_counts,
        "effective_split_counts": effective_split_counts,
        "minimum_validation_and_holdout_outcomes": minimum_holdout_outcomes,
        "market_phase_counts": phase_counts,
        "effective_market_phase_counts": effective_phase_counts,
        "asset_type_counts": asset_type_counts,
        "effective_asset_type_counts": effective_asset_type_counts,
        "volatility_regime_counts": volatility_counts,
        "effective_volatility_regime_counts": effective_volatility_counts,
        "minimum_segment_outcomes": minimum_segment_outcomes,
        "overlap_purged": overlap_safe,
        "adjusted_prices_verified": adjusted_prices,
        "limitations": [
            "Nur technische historische Kurs- und Volumendaten",
            "Keine Point-in-Time-Fundamental-, News-, Makro- oder Trade-Republic-Daten",
            "Issuer- und listingabhängige Fälle werden für Mindestfall- und Robustheitsgates geclustert",
            "Freigabe höchstens für einen technischen Shadow-Challenger",
        ],
    }


def run_historical_walk_forward(
    histories: Mapping[str, pd.DataFrame],
    *,
    asset_types: Mapping[str, str] | None = None,
    regions: Mapping[str, str] | None = None,
    asset_identities: Mapping[str, Mapping[str, object]] | None = None,
    minimum_history_rows: int = 220,
    step_sessions: int = 5,
    future_sessions: int = 25,
    maximum_cases: int = 25_000,
    maximum_cases_per_symbol: int = 12,
    strategy_profiles: Mapping[str, Mapping[str, object]] | None = None,
    purge_overlapping_signals: bool = True,
    price_adjustment: str = "unknown",
    research_split_boundaries: Mapping[str, object] | None = None,
    sampling_mode: str = "balanced_history",
    selection_round: int = 0,
    selection_round_role: str | None = None,
    research_dataset: Mapping[str, object] | None = None,
) -> dict:
    minimum = max(int(minimum_history_rows), 200)
    step = max(int(step_sessions), 1)
    future_count = max(int(future_sessions), 5)
    maximum = max(int(maximum_cases), 1)
    per_symbol_maximum = max(int(maximum_cases_per_symbol), 1)
    sampling = str(sampling_mode).strip().lower()
    if sampling not in {"balanced_history", "recent_incremental"}:
        raise ValueError(f"Unbekannter Walk-Forward-Samplingmodus: {sampling_mode}")
    round_index = int(selection_round)
    if round_index < 0:
        raise ValueError("Die historische Auswahlrunde darf nicht negativ sein.")
    round_role = str(
        selection_round_role
        or ("monitoring" if sampling == "recent_incremental" else "exploration")
    ).strip().lower()
    if round_role not in SELECTION_ROUND_ROLES:
        raise ValueError(f"Unbekannte Rolle der historischen Auswahlrunde: {selection_round_role}")
    if sampling == "recent_incremental" and round_index != 0:
        raise ValueError("Das wöchentliche Monitoring besitzt keine zusätzlichen Auswahlrunden.")
    dataset_contract = dict(research_dataset or {})
    if dataset_contract:
        required_dataset_fields = {
            "dataset_epoch",
            "dataset_revision",
            "dataset_fingerprint",
            "scope_id",
        }
        missing_dataset_fields = sorted(
            field for field in required_dataset_fields if not dataset_contract.get(field)
        )
        if missing_dataset_fields:
            raise ValueError(
                "Unvollständiger Research-Dataset-Vertrag: "
                + ", ".join(missing_dataset_fields)
            )
        if dataset_contract.get("provider_access_during_job") is not False:
            raise ValueError(
                "Ein finalisierter Research-Dataset-Vertrag darf während des Jobs keinen Providerzugriff erlauben."
            )
    round_label = "Aktuell" if sampling == "recent_incremental" else _selection_round_label(round_index)
    round_start = round_index * per_symbol_maximum if sampling == "balanced_history" else 0
    round_stop = round_start + per_symbol_maximum
    profiles = dict(strategy_profiles or swing_walk_forward_strategy_profiles(("current",)))
    if not profiles:
        raise ValueError("Mindestens ein versioniertes Forschungsprofil ist erforderlich.")
    cases: list[dict] = []
    data_fingerprints: dict[str, str] = {}
    research_identities: dict[str, dict] = {}
    prepared_histories: dict[str, pd.DataFrame] = {}
    for raw_symbol, raw_history in sorted(histories.items()):
        symbol = str(raw_symbol).strip().upper()
        frame = _valid_bars(raw_history)
        if not symbol or len(frame) < minimum + future_count:
            continue
        prepared_histories[symbol] = _prepare_historical_indicators(frame)
        data_fingerprints[symbol] = _frame_fingerprint(symbol, frame)
        raw_identity = dict((asset_identities or {}).get(symbol) or {})
        research_identities[symbol] = (
            raw_identity
            if raw_identity.get("issuer_id") and raw_identity.get("listing_id")
            else derive_swing_research_identity(
                {
                    **raw_identity,
                    "ticker": symbol,
                    "asset_type": (asset_types or {}).get(symbol) or "Aktie",
                    "region": (regions or {}).get(symbol) or "USA",
                }
            )
        )

    split_boundaries = (
        {
            "development_end": str(research_split_boundaries.get("development_end") or "") or None,
            "validation_end": str(research_split_boundaries.get("validation_end") or "") or None,
            "last_signal_day": str(research_split_boundaries.get("last_signal_day") or "") or None,
        }
        if research_split_boundaries is not None
        else _research_split_boundaries(
            prepared_histories,
            minimum_history_rows=minimum,
            future_sessions=future_count,
            step_sessions=step,
        )
    )
    if split_boundaries.get("development_end") and split_boundaries.get("validation_end"):
        if pd.Timestamp(split_boundaries["development_end"]) >= pd.Timestamp(
            split_boundaries["validation_end"]
        ):
            raise ValueError("Development-Ende muss vor dem Validation-Ende liegen.")
    for symbol, frame in prepared_histories.items():
        asset_type = str((asset_types or {}).get(symbol) or "Aktie")
        region = str((regions or {}).get(symbol) or "USA")
        research_identity = dict(research_identities[symbol])
        for profile_version, raw_profile in profiles.items():
            profile = dict(raw_profile)
            thresholds = profile.get("thresholds")
            if thresholds is None:
                raise ValueError(f"Forschungsprofil {profile_version} besitzt keine Grenzwerte.")
            if str(profile.get("version") or "") != str(profile_version):
                raise ValueError("Forschungsprofil und Versionsschlüssel stimmen nicht überein.")
            accepted_for_symbol = 0
            accepted_positions: list[int] = []
            cutoff_positions = _split_balanced_cutoff_positions(
                symbol,
                frame,
                minimum_history_rows=minimum,
                future_sessions=future_count,
                step_sessions=step,
                split_boundaries=split_boundaries,
                sampling_mode=sampling,
            )
            for cutoff_position in cutoff_positions:
                if accepted_for_symbol >= round_stop:
                    break
                if purge_overlapping_signals and any(
                    abs(cutoff_position - accepted_position) < future_count
                    for accepted_position in accepted_positions
                ):
                    continue
                future = frame.iloc[
                    cutoff_position + 1 : cutoff_position + 1 + future_count
                ].loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
                split = _assign_research_split(
                    frame.index[cutoff_position],
                    future.index[-1],
                    split_boundaries,
                )
                if split is None:
                    continue
                # All expensive trailing indicators were calculated once. A bounded causal
                # window is sufficient because setup geometry uses at most 220 prior bars.
                window_start = max(0, cutoff_position - max(minimum, 320) + 1)
                past = frame.iloc[window_start : cutoff_position + 1].copy()
                assessment = historical_technical_shadow_assessment(
                    symbol,
                    past,
                    asset_type=asset_type,
                    region=region,
                    thresholds=thresholds,
                    strategy_profile=profile,
                )
                if not assessment.get("approved"):
                    continue
                filter_passed, technical_filter_values = _technical_challenger_filter(
                    past,
                    assessment,
                    profile.get("technical_filter"),
                )
                if not filter_passed:
                    continue
                # Rounds are slices of one deterministic, outcome-blind stream of
                # strategy-approved and mutually purged signals. Earlier-round
                # positions are reconstructed, reserved and skipped before a later
                # round is stored. Thus A remains unchanged while B/C cannot reuse
                # A/B signals or choose dates based on their later outcomes.
                accepted_positions.append(cutoff_position)
                accepted_index = accepted_for_symbol
                accepted_for_symbol += 1
                if accepted_index < round_start:
                    continue
                signal_at = datetime.combine(
                    pd.Timestamp(past.index[-1]).date(), time(23, 59), tzinfo=timezone.utc
                )
                snapshot = {
                    "signal_at": signal_at.isoformat(),
                    "asset": {
                        "ticker": symbol,
                        "asset_type": asset_type,
                        "region": region,
                        "listing_id": research_identity["listing_id"],
                        "issuer_id": research_identity["issuer_id"],
                        "company_id": research_identity["company_id"],
                        "identity_version": research_identity["identity_version"],
                    },
                    "strategy": {
                        "strategy_version": profile_version,
                        "strategy_name": str(profile.get("name") or profile_version),
                        "strategy_family": str(
                            profile.get("strategy_family") or "legacy_unspecified"
                        ),
                        "parameter_variant": str(
                            profile.get("parameter_variant") or "unspecified"
                        ),
                        "engine_version": SWING_WALK_FORWARD_ENGINE_VERSION,
                        "thresholds": dict(profile.get("thresholds_snapshot") or {}),
                        "technical_filter": dict(profile.get("technical_filter") or {}),
                        "market_phase": assessment.get("market_phase"),
                        "volatility_regime": assessment.get("volatility_regime"),
                        "setup_type": assessment.get("setup_type"),
                        "evaluation_horizon_sessions": future_count,
                        "sampling_mode": sampling,
                        "selection_round": round_label,
                        "selection_round_index": round_index,
                        "selection_round_role": round_role,
                    },
                    "signal_features": {
                        "buy_signal": assessment.get("buy_signal"),
                        "confidence": assessment.get("confidence"),
                        "data_quality": assessment.get("data_quality"),
                        "relative_volume": assessment.get("relative_volume"),
                        "average_turnover_eur": assessment.get("average_turnover_eur"),
                        "crv": assessment.get("crv"),
                        "risk_pct": assessment.get("risk_pct"),
                        "rsi_14": technical_filter_values.get("rsi_14"),
                        "ema_20": technical_filter_values.get("ema_20"),
                        "ema_50": technical_filter_values.get("ema_50"),
                        "close": technical_filter_values.get("close"),
                    },
                    "order_plan": dict(assessment["order_plan"]),
                    "evidence": {
                        "kind": "historical_technical_shadow",
                        "production_comparable": False,
                        "research_contract": SWING_WALK_FORWARD_RESEARCH_CONTRACT,
                        "price_adjustment": str(price_adjustment),
                        "evaluation_horizon_sessions": future_count,
                        "sampling_mode": sampling,
                        "selection_round": round_label,
                        "selection_round_index": round_index,
                        "selection_round_role": round_role,
                        "limitations": list(assessment["limitations"]),
                        "technical_filter_uses_signal_bar_only": True,
                    },
                }
                evaluated_at = pd.Timestamp(future.index[-1]) + pd.Timedelta(days=1)
                events = evaluate_swing_signal_bars(
                    snapshot,
                    future,
                    interval="1d",
                    evaluated_at=evaluated_at,
                )
                terminal = _terminal_event(events)
                stable_split_contract = {
                    "development_end": split_boundaries.get("development_end"),
                    "validation_end": split_boundaries.get("validation_end"),
                }
                evidence_key = hashlib.sha256(
                    (
                        f"{symbol}|{snapshot['signal_at']}|{assessment.get('setup_type')}|"
                        f"{profile_version}|{SWING_WALK_FORWARD_RESEARCH_CONTRACT}|"
                        f"{future_count}|{_fingerprint(stable_split_contract)}"
                    ).encode("utf-8")
                ).hexdigest()
                logical_case_id = hashlib.sha256(
                    f"{evidence_key}|{sampling}".encode("utf-8")
                ).hexdigest()
                # The signal and its outcome depend only on bars through the end of
                # this label window. Later downloads may correct those historical
                # bars. Keep every such revision append-only, but do not let data
                # appended after the outcome create a duplicate research case.
                case_data_fingerprint = _frame_fingerprint(
                    symbol,
                    frame.iloc[: cutoff_position + 1 + future_count],
                )
                case = {
                    "case_version": SWING_WALK_FORWARD_ENGINE_VERSION,
                    "logical_case_id": logical_case_id,
                    "evidence_key": evidence_key,
                    "case_data_fingerprint": case_data_fingerprint,
                    "case_id": hashlib.sha256(
                        f"{logical_case_id}|{case_data_fingerprint}".encode("utf-8")
                    ).hexdigest(),
                    "symbol": symbol,
                    "signal_at": snapshot["signal_at"],
                    "cutoff_position": cutoff_position,
                    "past_rows_available": cutoff_position + 1,
                    "past_rows_used": len(past),
                    "future_rows_used": len(future),
                    "evaluation_horizon_sessions": future_count,
                    "sampling_mode": sampling,
                    "selection_round": round_label,
                    "selection_round_index": round_index,
                    "selection_round_role": round_role,
                    "selection_eligible": sampling == "balanced_history",
                    "monitoring_only": sampling == "recent_incremental",
                    "research_identity": research_identity,
                    "future_last_day": pd.Timestamp(future.index[-1]).date().isoformat(),
                    "research_split": split,
                    "split_boundaries": stable_split_contract,
                    "label_window_purged_at_split": True,
                    "overlap_purged": bool(purge_overlapping_signals),
                    "snapshot": snapshot,
                    "events": events,
                    "status": str((terminal or events[-1] if events else {}).get("event_type") or "stored"),
                    "result_r": (terminal or {}).get("payload", {}).get("result_r") if terminal else None,
                    "result_pct": (terminal or {}).get("payload", {}).get("result_pct") if terminal else None,
                    "future_data_used_for_signal": False,
                    "automatic_rule_change": False,
                }
                case["case_fingerprint"] = _fingerprint(case)
                cases.append(case)

    uncapped_case_count = len(cases)
    cases = _balanced_case_limit(cases, maximum)
    observational_features = {
        str(case["case_id"]): _observational_rsi_ema_features(case)
        for case in cases
    }
    evaluated = [case for case in cases if case.get("result_r") is not None]
    profile_summaries: list[dict] = []
    for profile_version, profile in profiles.items():
        profile_cases = [
            case
            for case in cases
            if ((case.get("snapshot") or {}).get("strategy") or {}).get("strategy_version")
            == profile_version
        ]
        profile_summaries.append(
            {
                "strategy_name": str(profile.get("name") or profile_version),
                "strategy_version": profile_version,
                **swing_walk_forward_case_metrics(profile_cases),
                "readiness": swing_walk_forward_research_readiness(profile_cases),
                "by_split": {
                    split: swing_walk_forward_case_metrics(
                        [case for case in profile_cases if case.get("research_split") == split]
                    )
                    for split in ("development", "validation", "holdout")
                },
            }
        )
    run = {
        "run_version": SWING_WALK_FORWARD_ENGINE_VERSION,
        "evidence_kind": "historical_technical_shadow",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "minimum_history_rows": minimum,
            "step_sessions": step,
            "future_sessions": future_count,
            "maximum_cases": maximum,
            "maximum_cases_per_symbol": per_symbol_maximum,
            "purge_overlapping_signals": bool(purge_overlapping_signals),
            "price_adjustment": str(price_adjustment),
            "sampling_mode": sampling,
            "selection_round": round_label,
            "selection_round_index": round_index,
            "selection_round_role": round_role,
            "selection_round_size": per_symbol_maximum,
            "selection_round_offset": round_start,
            "split_ratios": DEFAULT_RESEARCH_SPLIT_RATIOS,
            "split_boundaries": split_boundaries,
            "case_cap_policy": "deterministic_round_robin_by_strategy_and_symbol",
        },
        "strategy_profiles": {
            version: {
                key: value
                for key, value in profile.items()
                if key != "thresholds"
            }
            for version, profile in profiles.items()
        },
        "data_fingerprints": data_fingerprints,
        "research_dataset": dataset_contract or None,
        "asset_identities": research_identities,
        "cases": cases,
        # Stored in a separate append-only sidecar. It is intentionally excluded
        # from the baseline case and run fingerprints.
        "observational_features": observational_features,
        "summary": {
            **swing_walk_forward_case_metrics(cases),
            "signals": len(cases),
            "uncapped_signals": uncapped_case_count,
            "profiles": profile_summaries,
        },
        "research_contract": {
            "version": SWING_WALK_FORWARD_RESEARCH_CONTRACT,
            "chronological_splits": True,
            "purged_split_boundaries": True,
            "overlapping_symbol_labels": not bool(purge_overlapping_signals),
            "adjusted_ohlcv_required": True,
            "adjusted_ohlcv_verified": str(price_adjustment) == "yfinance_auto_adjust_true",
            "point_in_time_technical_only": True,
            "selection_rounds_are_outcome_blind": True,
            "selection_rounds_are_signal_disjoint": True,
            "issuer_listing_identity_version": SWING_RESEARCH_IDENTITY_VERSION,
            "dependent_listings_clustered_for_inference": True,
            "holdout_may_select_production": False,
        },
        "separate_from_real_forward": True,
        "production_comparable": False,
        "automatic_rule_change": False,
    }
    run["run_id"] = _fingerprint(
        {
            "run_version": run["run_version"],
            "created_at": run["created_at"],
            "parameters": run["parameters"],
            "data_fingerprints": run["data_fingerprints"],
            "research_dataset": run["research_dataset"],
        }
    )
    return run


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_swing_walk_forward_store(
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS walk_forward_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS walk_forward_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                run_json TEXT NOT NULL,
                run_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS walk_forward_cases (
                case_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES walk_forward_runs(run_id),
                symbol TEXT NOT NULL,
                signal_at TEXT NOT NULL,
                case_json TEXT NOT NULL,
                case_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS walk_forward_real_links (
                link_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES walk_forward_cases(case_id),
                forward_signal_id TEXT NOT NULL,
                relation TEXT NOT NULL CHECK (
                    relation IN ('exact_same_trade', 'related_same_asset_day')
                ),
                discovered_at TEXT NOT NULL,
                link_json TEXT NOT NULL,
                link_fingerprint TEXT NOT NULL,
                UNIQUE (case_id, forward_signal_id)
            );
            CREATE TABLE IF NOT EXISTS walk_forward_case_identity_conflicts (
                conflict_id TEXT PRIMARY KEY,
                original_case_id TEXT NOT NULL REFERENCES walk_forward_cases(case_id),
                resolved_case_id TEXT NOT NULL REFERENCES walk_forward_cases(case_id),
                run_id TEXT NOT NULL REFERENCES walk_forward_runs(run_id),
                detected_at TEXT NOT NULL,
                conflict_json TEXT NOT NULL,
                conflict_fingerprint TEXT NOT NULL,
                UNIQUE (original_case_id, resolved_case_id)
            );
            CREATE TABLE IF NOT EXISTS walk_forward_case_observational_features (
                feature_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES walk_forward_cases(case_id),
                feature_version TEXT NOT NULL,
                feature_json TEXT NOT NULL,
                feature_fingerprint TEXT NOT NULL,
                UNIQUE (case_id, feature_version)
            );
            CREATE TRIGGER IF NOT EXISTS walk_forward_runs_no_update
            BEFORE UPDATE ON walk_forward_runs BEGIN
                SELECT RAISE(ABORT, 'walk_forward_runs is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_runs_no_delete
            BEFORE DELETE ON walk_forward_runs BEGIN
                SELECT RAISE(ABORT, 'walk_forward_runs is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_cases_no_update
            BEFORE UPDATE ON walk_forward_cases BEGIN
                SELECT RAISE(ABORT, 'walk_forward_cases is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_cases_no_delete
            BEFORE DELETE ON walk_forward_cases BEGIN
                SELECT RAISE(ABORT, 'walk_forward_cases is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_real_links_no_update
            BEFORE UPDATE ON walk_forward_real_links BEGIN
                SELECT RAISE(ABORT, 'walk_forward_real_links is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_real_links_no_delete
            BEFORE DELETE ON walk_forward_real_links BEGIN
                SELECT RAISE(ABORT, 'walk_forward_real_links is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_case_identity_conflicts_no_update
            BEFORE UPDATE ON walk_forward_case_identity_conflicts BEGIN
                SELECT RAISE(ABORT, 'walk_forward_case_identity_conflicts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_case_identity_conflicts_no_delete
            BEFORE DELETE ON walk_forward_case_identity_conflicts BEGIN
                SELECT RAISE(ABORT, 'walk_forward_case_identity_conflicts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_case_observational_features_no_update
            BEFORE UPDATE ON walk_forward_case_observational_features BEGIN
                SELECT RAISE(ABORT, 'walk_forward_case_observational_features is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS walk_forward_case_observational_features_no_delete
            BEFORE DELETE ON walk_forward_case_observational_features BEGIN
                SELECT RAISE(ABORT, 'walk_forward_case_observational_features is append-only');
            END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM walk_forward_meta WHERE key = 'schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO walk_forward_meta (key, value) VALUES ('schema_version', ?)",
                (str(SWING_WALK_FORWARD_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) < SWING_WALK_FORWARD_SCHEMA_VERSION:
            connection.execute(
                "UPDATE walk_forward_meta SET value = ? WHERE key = 'schema_version'",
                (str(SWING_WALK_FORWARD_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != SWING_WALK_FORWARD_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstützte Swing-Walk-Forward-Datenbankversion.")


def _resolve_walk_forward_case_identity_conflict(
    connection: sqlite3.Connection,
    case: Mapping[str, object],
    *,
    existing_case_fingerprint: str,
) -> tuple[dict, dict]:
    original = json.loads(_canonical_json(dict(case)))
    original_case_id = str(original["case_id"])
    incoming_case_fingerprint = str(original["case_fingerprint"])
    resolution_identity = {
        "version": SWING_CASE_IDENTITY_RESOLUTION_VERSION,
        "original_case_id": original_case_id,
        "existing_case_fingerprint": str(existing_case_fingerprint),
        "incoming_case_fingerprint": incoming_case_fingerprint,
    }
    resolved_case_id = _fingerprint(resolution_identity)
    resolved = {
        **original,
        "case_id": resolved_case_id,
        "identity_revision": {
            **resolution_identity,
            "resolution": "append_only_case_revision",
        },
    }
    resolved["case_fingerprint"] = _fingerprint(
        {key: value for key, value in resolved.items() if key != "case_fingerprint"}
    )
    collision = connection.execute(
        "SELECT case_fingerprint FROM walk_forward_cases WHERE case_id = ?",
        (resolved_case_id,),
    ).fetchone()
    if collision is not None and str(collision["case_fingerprint"]) != str(
        resolved["case_fingerprint"]
    ):
        raise RuntimeError("Deterministische Walk-Forward-Fallrevision ist nicht eindeutig.")
    conflict_payload = {
        **resolution_identity,
        "resolved_case_id": resolved_case_id,
        "resolved_case_fingerprint": resolved["case_fingerprint"],
        "original_case_preserved": True,
        "automatic_overwrite": False,
    }
    conflict_payload["conflict_id"] = _fingerprint(conflict_payload)
    return resolved, conflict_payload


def record_swing_walk_forward_run(
    run: dict,
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
) -> dict:
    initialize_swing_walk_forward_store(path)
    run_id = str(run.get("run_id") or "")
    if not run_id or run.get("evidence_kind") != "historical_technical_shadow":
        raise ValueError("Walk-Forward-Lauf besitzt keine gültige getrennte Evidenzidentität.")
    run_payload = {
        key: value
        for key, value in run.items()
        if key not in {"cases", "observational_features"}
    }
    run_fingerprint = _fingerprint(run_payload)
    inserted_cases = 0
    inserted_observational_features = 0
    resolved_identity_conflicts = 0
    inserted_identity_conflicts = 0
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT run_fingerprint FROM walk_forward_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if existing is not None and existing["run_fingerprint"] != run_fingerprint:
            raise ValueError("Walk-Forward-Laufidentität besitzt abweichende Daten.")
        if existing is None:
            connection.execute(
                "INSERT INTO walk_forward_runs (run_id, created_at, run_json, run_fingerprint) VALUES (?, ?, ?, ?)",
                (run_id, str(run["created_at"]), _canonical_json(run_payload), run_fingerprint),
            )
        observational_features = dict(run.get("observational_features") or {})
        for raw_case in run.get("cases") or []:
            case = json.loads(_canonical_json(dict(raw_case)))
            case_id = str(case.get("case_id") or "")
            raw_observational_feature = observational_features.get(case_id)
            case_fingerprint = str(case.get("case_fingerprint") or "")
            if not case_id or case_fingerprint != _fingerprint(
                {key: value for key, value in case.items() if key != "case_fingerprint"}
            ):
                raise ValueError("Walk-Forward-Fall besitzt keinen gültigen Fingerabdruck.")
            existing_case = connection.execute(
                "SELECT case_fingerprint FROM walk_forward_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            conflict_payload: dict | None = None
            if existing_case is not None:
                if existing_case["case_fingerprint"] != case_fingerprint:
                    case, conflict_payload = _resolve_walk_forward_case_identity_conflict(
                        connection,
                        case,
                        existing_case_fingerprint=str(existing_case["case_fingerprint"]),
                    )
                    case_id = str(case["case_id"])
                    case_fingerprint = str(case["case_fingerprint"])
                    resolved_identity_conflicts += 1
                    existing_case = connection.execute(
                        "SELECT case_fingerprint FROM walk_forward_cases WHERE case_id = ?",
                        (case_id,),
                    ).fetchone()
                else:
                    continue
            if existing_case is None:
                connection.execute(
                    """
                    INSERT INTO walk_forward_cases (
                        case_id, run_id, symbol, signal_at, case_json, case_fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case_id,
                        run_id,
                        str(case["symbol"]),
                        str(case["signal_at"]),
                        _canonical_json(case),
                        case_fingerprint,
                    ),
                )
                inserted_cases += 1
                if raw_observational_feature is not None:
                    feature_payload = json.loads(
                        _canonical_json(
                            {
                                **dict(raw_observational_feature),
                                "case_id": case_id,
                            }
                        )
                    )
                    if (
                        feature_payload.get("feature_version")
                        != SWING_OBSERVATIONAL_FEATURE_VERSION
                        or int(feature_payload.get("future_bars_used") or 0) != 0
                        or feature_payload.get("baseline_filtering") is not False
                        or feature_payload.get("trade_selection_changed") is not False
                        or feature_payload.get("automatic_rule_change") is not False
                        or str(feature_payload.get("signal_at") or "")
                        != str(case.get("signal_at") or "")
                    ):
                        raise ValueError("Ungültiger beobachtender RSI-/EMA-Featurevertrag.")
                    feature_id = _fingerprint(
                        {
                            "case_id": case_id,
                            "feature_version": SWING_OBSERVATIONAL_FEATURE_VERSION,
                        }
                    )
                    feature_fingerprint = _fingerprint(feature_payload)
                    connection.execute(
                        """
                        INSERT INTO walk_forward_case_observational_features (
                            feature_id, case_id, feature_version,
                            feature_json, feature_fingerprint
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            feature_id,
                            case_id,
                            SWING_OBSERVATIONAL_FEATURE_VERSION,
                            _canonical_json(feature_payload),
                            feature_fingerprint,
                        ),
                    )
                    inserted_observational_features += 1
            elif str(existing_case["case_fingerprint"]) != case_fingerprint:
                raise RuntimeError("Aufgelöste Walk-Forward-Fallrevision besitzt abweichende Daten.")
            if conflict_payload is not None:
                conflict_id = str(conflict_payload["conflict_id"])
                conflict_fingerprint = _fingerprint(conflict_payload)
                previous_conflict = connection.execute(
                    """
                    SELECT conflict_fingerprint
                    FROM walk_forward_case_identity_conflicts
                    WHERE conflict_id = ?
                    """,
                    (conflict_id,),
                ).fetchone()
                if previous_conflict is None:
                    connection.execute(
                        """
                        INSERT INTO walk_forward_case_identity_conflicts (
                            conflict_id, original_case_id, resolved_case_id, run_id,
                            detected_at, conflict_json, conflict_fingerprint
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            conflict_id,
                            str(conflict_payload["original_case_id"]),
                            str(conflict_payload["resolved_case_id"]),
                            run_id,
                            str(run["created_at"]),
                            _canonical_json(conflict_payload),
                            conflict_fingerprint,
                        ),
                    )
                    inserted_identity_conflicts += 1
                elif str(previous_conflict["conflict_fingerprint"]) != conflict_fingerprint:
                    raise RuntimeError("Walk-Forward-Identitätsrevision besitzt abweichende Daten.")
    return {
        "run_id": run_id,
        "run_inserted": existing is None,
        "cases_total": len(run.get("cases") or []),
        "cases_inserted": inserted_cases,
        "observational_features_inserted": inserted_observational_features,
        "identity_conflicts_resolved": resolved_identity_conflicts,
        "identity_conflicts_recorded": inserted_identity_conflicts,
        "identity_resolution_version": SWING_CASE_IDENTITY_RESOLUTION_VERSION,
        "separate_from_real_forward": True,
    }


def _normalized_link_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return " ".join("".join(character for character in text if not unicodedata.combining(character)).split())


def _signal_day(snapshot: Mapping[str, object]) -> str:
    plan = dict(snapshot.get("order_plan") or {})
    explicit = str(plan.get("signal_bar_day") or "").strip()
    return explicit or str(snapshot.get("signal_at") or "")[:10]


def _execution_plan_identity(plan: Mapping[str, object]) -> str:
    fields = (
        "plan_version",
        "signal_bar_day",
        "direction",
        "entry_method",
        "earliest_entry_day",
        "valid_until",
        "activation_type",
        "activation_price_original",
        "limit_price_original",
        "maximum_entry_original",
        "invalidation_original",
        "initial_stop_original",
        "target_1_original",
        "target_1_exit_fraction",
        "target_2_original",
        "target_2_exit_fraction",
        "original_currency",
        "execution_cost_contract",
    )
    return _fingerprint({field: plan.get(field) for field in fields})


def swing_walk_forward_forward_link_candidates(
    cases: Sequence[Mapping[str, object]],
    forward_signals: Sequence[Mapping[str, object]],
) -> list[dict]:
    """Build deterministic cross-store links without merging either evidence source."""
    signals_by_asset_day: dict[tuple[str, str], list[dict]] = {}
    for raw_signal in forward_signals:
        signal = dict(raw_signal)
        snapshot = dict(signal.get("snapshot") or {})
        asset = dict(snapshot.get("asset") or {})
        ticker = str(asset.get("ticker") or "").strip().upper()
        day = _signal_day(snapshot)
        signal_id = str(signal.get("signal_id") or "")
        if ticker and day and signal_id:
            signals_by_asset_day.setdefault((ticker, day), []).append(signal)

    links: list[dict] = []
    for raw_case in cases:
        case = dict(raw_case)
        case_id = str(case.get("case_id") or "")
        snapshot = dict(case.get("snapshot") or {})
        asset = dict(snapshot.get("asset") or {})
        historical_ticker = str(case.get("symbol") or asset.get("ticker") or "").strip().upper()
        day = _signal_day(snapshot)
        if not case_id or not historical_ticker or not day:
            continue
        historical_plan = dict(snapshot.get("order_plan") or {})
        historical_strategy = dict(snapshot.get("strategy") or {})
        historical_plan_identity = _execution_plan_identity(historical_plan)
        historical_setup = _normalized_link_text(historical_strategy.get("setup_type"))
        historical_direction = _normalized_link_text(
            historical_plan.get("direction") or historical_strategy.get("direction")
        )
        for signal in signals_by_asset_day.get((historical_ticker, day), []):
            forward_snapshot = dict(signal.get("snapshot") or {})
            forward_asset = dict(forward_snapshot.get("asset") or {})
            forward_plan = dict(forward_snapshot.get("order_plan") or {})
            forward_strategy = dict(forward_snapshot.get("strategy") or {})
            historical_isin = str(asset.get("isin") or "").strip().upper()
            forward_isin = str(forward_asset.get("isin") or "").strip().upper()
            historical_exchange = _normalized_link_text(asset.get("exchange"))
            forward_exchange = _normalized_link_text(forward_asset.get("exchange"))
            listing_compatible = not (
                (historical_isin and forward_isin and historical_isin != forward_isin)
                or (
                    historical_exchange
                    and forward_exchange
                    and historical_exchange != forward_exchange
                )
            )
            forward_plan_identity = _execution_plan_identity(forward_plan)
            exact = bool(
                listing_compatible
                and historical_setup
                == _normalized_link_text(forward_strategy.get("setup_type"))
                and historical_direction
                == _normalized_link_text(
                    forward_plan.get("direction") or forward_strategy.get("direction")
                )
                and historical_plan_identity == forward_plan_identity
            )
            relation = "exact_same_trade" if exact else "related_same_asset_day"
            forward_signal_id = str(signal["signal_id"])
            links.append(
                {
                    "link_version": SWING_EVIDENCE_LINK_VERSION,
                    "historical_case_id": case_id,
                    "historical_evidence_key": str(case.get("evidence_key") or ""),
                    "forward_signal_id": forward_signal_id,
                    "relation": relation,
                    "asset": {
                        "ticker": historical_ticker,
                        "historical_isin": historical_isin or None,
                        "forward_isin": forward_isin or None,
                        "historical_exchange": str(asset.get("exchange") or "") or None,
                        "forward_exchange": str(forward_asset.get("exchange") or "") or None,
                    },
                    "signal_bar_day": day,
                    "historical_strategy_version": str(
                        historical_strategy.get("strategy_version") or ""
                    ),
                    "forward_strategy_version": str(
                        forward_strategy.get("strategy_version") or ""
                    ),
                    "historical_plan_identity": historical_plan_identity,
                    "forward_plan_identity": forward_plan_identity,
                    "preferred_evidence": "real_forward" if exact else "separate",
                    "counts_as_independent_historical_monitoring": not exact,
                    "historical_source_remains_immutable": True,
                    "forward_source_remains_immutable": True,
                    "automatic_rule_change": False,
                }
            )
    links.sort(
        key=lambda link: (
            str(link["historical_case_id"]),
            str(link["forward_signal_id"]),
        )
    )
    return links


def record_swing_walk_forward_forward_links(
    links: Sequence[Mapping[str, object]],
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
) -> dict:
    initialize_swing_walk_forward_store(path)
    inserted = 0
    existing_count = 0
    discovered_at = datetime.now(timezone.utc).isoformat()
    with _connect(Path(path)) as connection:
        for raw_link in links:
            link = _clean(dict(raw_link))
            case_id = str(link.get("historical_case_id") or "")
            forward_signal_id = str(link.get("forward_signal_id") or "")
            relation = str(link.get("relation") or "")
            if (
                link.get("link_version") != SWING_EVIDENCE_LINK_VERSION
                or not case_id
                or not forward_signal_id
                or relation not in {"exact_same_trade", "related_same_asset_day"}
            ):
                raise ValueError("Ungültige historische/echte Forward-Verknüpfung.")
            case_exists = connection.execute(
                "SELECT 1 FROM walk_forward_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if case_exists is None:
                raise ValueError("Historischer Fall der Forward-Verknüpfung existiert nicht.")
            link_id = hashlib.sha256(
                f"{SWING_EVIDENCE_LINK_VERSION}|{case_id}|{forward_signal_id}".encode("utf-8")
            ).hexdigest()
            link_fingerprint = _fingerprint(link)
            previous = connection.execute(
                """
                SELECT relation, link_fingerprint
                FROM walk_forward_real_links
                WHERE case_id = ? AND forward_signal_id = ?
                """,
                (case_id, forward_signal_id),
            ).fetchone()
            if previous is not None:
                if (
                    str(previous["relation"]) != relation
                    or str(previous["link_fingerprint"]) != link_fingerprint
                ):
                    raise ValueError("Forward-Verknüpfung besitzt abweichende Daten.")
                existing_count += 1
                continue
            connection.execute(
                """
                INSERT INTO walk_forward_real_links (
                    link_id, case_id, forward_signal_id, relation, discovered_at,
                    link_json, link_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    case_id,
                    forward_signal_id,
                    relation,
                    discovered_at,
                    _canonical_json(link),
                    link_fingerprint,
                ),
            )
            inserted += 1
    return {
        "candidates": len(links),
        "inserted": inserted,
        "existing": existing_count,
        "automatic_rule_change": False,
    }


def load_swing_walk_forward_forward_links(
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_swing_walk_forward_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            """
            SELECT link_id, discovered_at, link_json
            FROM walk_forward_real_links
            ORDER BY discovered_at, link_id
            """
        ).fetchall()
    return [
        {
            "link_id": str(row["link_id"]),
            "discovered_at": str(row["discovered_at"]),
            **json.loads(row["link_json"]),
        }
        for row in rows
    ]


def refresh_swing_walk_forward_forward_links(
    walk_forward_path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
    forward_path: Path | None = None,
) -> dict:
    from swing_forward_store import DEFAULT_SWING_FORWARD_DB_PATH, load_swing_forward_signals

    historical_path = Path(walk_forward_path)
    source_path = Path(
        forward_path
        if forward_path is not None
        else (
            DEFAULT_SWING_FORWARD_DB_PATH
            if historical_path.resolve() == DEFAULT_SWING_WALK_FORWARD_DB_PATH.resolve()
            else historical_path.with_name("swing_forward.sqlite3")
        )
    )
    if not historical_path.exists() or not source_path.exists():
        return {
            "historical_cases": 0,
            "forward_signals": 0,
            "candidates": 0,
            "inserted": 0,
            "existing": 0,
            "status": "source_not_available",
            "automatic_rule_change": False,
        }
    cases = load_swing_walk_forward_cases(
        historical_path,
        include_real_forward_links=False,
    )
    signals = load_swing_forward_signals(source_path)
    candidates = swing_walk_forward_forward_link_candidates(cases, signals)
    stored = record_swing_walk_forward_forward_links(candidates, historical_path)
    return {
        "historical_cases": len(cases),
        "forward_signals": len(signals),
        **stored,
        "status": "ok",
    }


def swing_walk_forward_store_audit(
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
) -> dict:
    initialize_swing_walk_forward_store(path)
    invalid: list[str] = []
    with _connect(Path(path)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        runs = connection.execute(
            "SELECT run_id, run_json, run_fingerprint FROM walk_forward_runs"
        ).fetchall()
        cases = connection.execute(
            "SELECT case_id, case_json, case_fingerprint FROM walk_forward_cases"
        ).fetchall()
        links = connection.execute(
            """
            SELECT link_id, case_id, forward_signal_id, relation, link_json, link_fingerprint
            FROM walk_forward_real_links
            """
        ).fetchall()
        identity_conflicts = connection.execute(
            """
            SELECT conflict_id, original_case_id, resolved_case_id, run_id,
                   conflict_json, conflict_fingerprint
            FROM walk_forward_case_identity_conflicts
            """
        ).fetchall()
        observational_features = connection.execute(
            """
            SELECT feature_id, case_id, feature_version,
                   feature_json, feature_fingerprint
            FROM walk_forward_case_observational_features
            """
        ).fetchall()
    for row in runs:
        try:
            if _fingerprint(json.loads(row["run_json"])) != row["run_fingerprint"]:
                invalid.append(f"run:{row['run_id']}:fingerprint")
        except Exception:
            invalid.append(f"run:{row['run_id']}:json")
    for row in cases:
        try:
            payload = json.loads(row["case_json"])
            expected = _fingerprint({key: value for key, value in payload.items() if key != "case_fingerprint"})
            if expected != row["case_fingerprint"]:
                invalid.append(f"case:{row['case_id']}:fingerprint")
        except Exception:
            invalid.append(f"case:{row['case_id']}:json")
    case_ids = {str(row["case_id"]) for row in cases}
    run_ids = {str(row["run_id"]) for row in runs}
    for row in links:
        try:
            payload = json.loads(row["link_json"])
            if _fingerprint(payload) != row["link_fingerprint"]:
                invalid.append(f"link:{row['link_id']}:fingerprint")
            if str(payload.get("historical_case_id") or "") != str(row["case_id"]):
                invalid.append(f"link:{row['link_id']}:case")
            if str(payload.get("forward_signal_id") or "") != str(row["forward_signal_id"]):
                invalid.append(f"link:{row['link_id']}:signal")
            if str(payload.get("relation") or "") != str(row["relation"]):
                invalid.append(f"link:{row['link_id']}:relation")
            if str(row["case_id"]) not in case_ids:
                invalid.append(f"link:{row['link_id']}:missing_case")
        except Exception:
            invalid.append(f"link:{row['link_id']}:json")
    for row in identity_conflicts:
        try:
            payload = json.loads(row["conflict_json"])
            if _fingerprint(payload) != row["conflict_fingerprint"]:
                invalid.append(f"identity_conflict:{row['conflict_id']}:fingerprint")
            if str(payload.get("conflict_id") or "") != str(row["conflict_id"]):
                invalid.append(f"identity_conflict:{row['conflict_id']}:identity")
            if str(payload.get("original_case_id") or "") != str(row["original_case_id"]):
                invalid.append(f"identity_conflict:{row['conflict_id']}:original_case")
            if str(payload.get("resolved_case_id") or "") != str(row["resolved_case_id"]):
                invalid.append(f"identity_conflict:{row['conflict_id']}:resolved_case")
            if str(row["original_case_id"]) not in case_ids:
                invalid.append(f"identity_conflict:{row['conflict_id']}:missing_original")
            if str(row["resolved_case_id"]) not in case_ids:
                invalid.append(f"identity_conflict:{row['conflict_id']}:missing_revision")
            if str(row["run_id"]) not in run_ids:
                invalid.append(f"identity_conflict:{row['conflict_id']}:missing_run")
        except Exception:
            invalid.append(f"identity_conflict:{row['conflict_id']}:json")
    for row in observational_features:
        try:
            payload = json.loads(row["feature_json"])
            if _fingerprint(payload) != row["feature_fingerprint"]:
                invalid.append(f"observational_feature:{row['feature_id']}:fingerprint")
            if str(payload.get("case_id") or "") != str(row["case_id"]):
                invalid.append(f"observational_feature:{row['feature_id']}:case")
            if str(payload.get("feature_version") or "") != str(row["feature_version"]):
                invalid.append(f"observational_feature:{row['feature_id']}:version")
            if str(row["case_id"]) not in case_ids:
                invalid.append(f"observational_feature:{row['feature_id']}:missing_case")
            if int(payload.get("future_bars_used") or 0) != 0:
                invalid.append(f"observational_feature:{row['feature_id']}:future_data")
            if payload.get("baseline_filtering") is not False:
                invalid.append(f"observational_feature:{row['feature_id']}:baseline_filter")
            if payload.get("trade_selection_changed") is not False:
                invalid.append(f"observational_feature:{row['feature_id']}:trade_selection")
            if payload.get("automatic_rule_change") is not False:
                invalid.append(f"observational_feature:{row['feature_id']}:rule_change")
        except Exception:
            invalid.append(f"observational_feature:{row['feature_id']}:json")
    exact_links = sum(str(row["relation"]) == "exact_same_trade" for row in links)
    return {
        "schema_version": SWING_WALK_FORWARD_SCHEMA_VERSION,
        "quick_check": quick_check,
        "runs": len(runs),
        "cases": len(cases),
        "forward_links": len(links),
        "exact_forward_links": exact_links,
        "related_forward_links": len(links) - exact_links,
        "case_identity_conflicts_resolved": len(identity_conflicts),
        "observational_features": len(observational_features),
        "observational_feature_version": SWING_OBSERVATIONAL_FEATURE_VERSION,
        "invalid_count": len(invalid),
        "invalid": invalid[:20],
        "status": "ok" if quick_check == "ok" and not invalid else "attention",
        "separate_from_real_forward": True,
    }


def load_swing_walk_forward_cases(
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
    *,
    limit: int | None = None,
    include_superseded_revisions: bool = False,
    include_real_forward_links: bool = True,
) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_swing_walk_forward_store(path)
    query = """
        SELECT cases.case_json, runs.created_at AS run_created_at
        FROM walk_forward_cases AS cases
        JOIN walk_forward_runs AS runs ON runs.run_id = cases.run_id
        ORDER BY runs.created_at DESC, cases.signal_at DESC, cases.case_id DESC
    """
    with _connect(Path(path)) as connection:
        rows = connection.execute(query).fetchall()
        observational_feature_rows = connection.execute(
            """
            SELECT case_id, feature_json
            FROM walk_forward_case_observational_features
            WHERE feature_version = ?
            """,
            (SWING_OBSERVATIONAL_FEATURE_VERSION,),
        ).fetchall()
        link_rows = (
            connection.execute(
                """
                SELECT case_id, link_id, discovered_at, link_json
                FROM walk_forward_real_links
                ORDER BY discovered_at, link_id
                """
            ).fetchall()
            if include_real_forward_links
            else []
        )
    observational_features_by_case = {
        str(row["case_id"]): json.loads(row["feature_json"])
        for row in observational_feature_rows
    }
    links_by_case: dict[str, list[dict]] = {}
    for row in link_rows:
        links_by_case.setdefault(str(row["case_id"]), []).append(
            {
                "link_id": str(row["link_id"]),
                "discovered_at": str(row["discovered_at"]),
                **json.loads(row["link_json"]),
            }
        )
    cases: list[dict] = []
    selected_by_evidence: dict[str, dict] = {}
    for row in rows:
        case = json.loads(row["case_json"])
        logical_case_id = str(
            case.get("evidence_key") or case.get("logical_case_id") or case.get("case_id") or ""
        )
        if include_superseded_revisions:
            cases.append(case)
            continue
        existing = selected_by_evidence.get(logical_case_id)
        if existing is None or (
            bool(case.get("selection_eligible", True))
            and not bool(existing.get("selection_eligible", True))
        ):
            selected_by_evidence[logical_case_id] = case
    if not include_superseded_revisions:
        cases = list(selected_by_evidence.values())
    if include_real_forward_links:
        for case in cases:
            case_links = links_by_case.get(str(case.get("case_id") or ""), [])
            exact = any(link.get("relation") == "exact_same_trade" for link in case_links)
            related = any(link.get("relation") == "related_same_asset_day" for link in case_links)
            case["real_forward_links"] = case_links
            case["real_forward_link_status"] = (
                "exact_same_trade" if exact else "related_same_asset_day" if related else "not_linked"
            )
            case["historical_monitoring_counted"] = not exact
            case["preferred_evidence"] = "real_forward" if exact else "historical_separate"
    for case in cases:
        observational = observational_features_by_case.get(str(case.get("case_id") or ""))
        case["observational_features"] = observational
        case["observational_feature_status"] = (
            "available" if observational is not None else "legacy_feature_not_recorded"
        )
    cases.sort(
        key=lambda case: (str(case.get("signal_at") or ""), str(case.get("case_id") or "")),
        reverse=True,
    )
    if limit is not None:
        return cases[: max(int(limit), 0)]
    return cases


def swing_walk_forward_strategy_comparison(
    cases: Sequence[Mapping[str, object]],
) -> dict:
    research_cases = [
        dict(case)
        for case in cases
        if case.get("case_version") == SWING_WALK_FORWARD_ENGINE_VERSION
    ]
    grouped: dict[str, list[dict]] = {}
    group_metadata: dict[str, dict] = {}
    for case in research_cases:
        strategy = dict((case.get("snapshot") or {}).get("strategy") or {})
        version = str(strategy.get("strategy_version") or "Unbekannt")
        grouped.setdefault(version, []).append(case)
        group_metadata.setdefault(
            version,
            {
                "strategy_name": str(strategy.get("strategy_name") or version),
                "derived_threshold_hypothesis": False,
            },
        )
    current_group = next(
        (
            group
            for version, group in grouped.items()
            if group_metadata.get(version, {}).get("strategy_name") == "current"
        ),
        [],
    )
    current_group = [case for case in current_group if case.get("selection_eligible", True)]
    if current_group:
        for version, profile in swing_walk_forward_strategy_profiles(
            ("balanced", "precision", "payoff")
        ).items():
            if version in grouped:
                continue
            thresholds = profile["thresholds"]
            filtered: list[dict] = []
            for case in current_group:
                features = dict((case.get("snapshot") or {}).get("signal_features") or {})
                try:
                    qualifies = (
                        float(features.get("buy_signal")) >= float(thresholds.min_buy_signal)
                        and float(features.get("confidence")) >= float(thresholds.min_confidence)
                        and float(features.get("crv")) >= float(thresholds.min_crv)
                    )
                except (TypeError, ValueError):
                    qualifies = False
                if qualifies:
                    filtered.append(case)
            grouped[version] = filtered
            group_metadata[version] = {
                "strategy_name": str(profile["name"]),
                "derived_threshold_hypothesis": True,
            }
    rows: list[dict] = []
    for version, group in sorted(grouped.items()):
        metadata = group_metadata.get(version) or {}
        strategy = dict((group[0].get("snapshot") or {}).get("strategy") or {}) if group else {}
        selection_group = [case for case in group if case.get("selection_eligible", True)]
        raw_monitoring_group = [case for case in group if not case.get("selection_eligible", True)]
        monitoring_group = [
            case for case in raw_monitoring_group if case.get("historical_monitoring_counted", True)
        ]
        holdout = swing_walk_forward_case_metrics(
            [case for case in selection_group if case.get("research_split") == "holdout"]
        )
        validation = swing_walk_forward_case_metrics(
            [case for case in selection_group if case.get("research_split") == "validation"]
        )
        overall = swing_walk_forward_case_metrics(selection_group)
        monitoring = swing_walk_forward_case_metrics(monitoring_group)
        readiness = swing_walk_forward_research_readiness(selection_group)
        rows.append(
            {
                "strategy_name": str(metadata.get("strategy_name") or strategy.get("strategy_name") or version),
                "strategy_version": version,
                "derived_threshold_hypothesis": bool(metadata.get("derived_threshold_hypothesis")),
                "evaluated": overall["evaluated"],
                "raw_evaluated": overall["raw_evaluated"],
                "effective_independent_evaluated": overall["effective_independent_evaluated"],
                "dependency_adjustment_required": overall["dependency_adjustment_required"],
                "dependent_listing_clusters": overall["dependent_listing_clusters"],
                "symbols": overall["symbols"],
                "issuer_clusters": overall["issuer_clusters"],
                "hit_rate_pct": overall["hit_rate_pct"],
                "independence_adjusted_hit_rate_pct": overall[
                    "independence_adjusted_hit_rate_pct"
                ],
                "average_r": overall["average_r"],
                "profit_factor": overall["profit_factor"],
                "maximum_drawdown_r": overall["maximum_drawdown_r"],
                "monitoring_evaluated": monitoring["evaluated"],
                "monitoring_exact_forward_links_excluded": len(raw_monitoring_group)
                - len(monitoring_group),
                "monitoring_hit_rate_pct": monitoring["hit_rate_pct"],
                "monitoring_average_r": monitoring["average_r"],
                "validation_evaluated": validation["evaluated"],
                "validation_effective_independent_evaluated": validation[
                    "effective_independent_evaluated"
                ],
                "validation_hit_rate_pct": validation["hit_rate_pct"],
                "validation_average_r": validation["average_r"],
                "holdout_evaluated": holdout["evaluated"],
                "holdout_effective_independent_evaluated": holdout[
                    "effective_independent_evaluated"
                ],
                "holdout_hit_rate_pct": holdout["hit_rate_pct"],
                "holdout_average_r": holdout["average_r"],
                "holdout_profit_factor": holdout["profit_factor"],
                "technical_review_ready": bool(
                    readiness["technical_challenger_review_allowed"]
                    and not metadata.get("derived_threshold_hypothesis")
                ),
                "pareto_front_holdout": False,
                "automatic_production_activation": False,
            }
        )
    eligible = [
        row
        for row in rows
        if int(row.get("holdout_effective_independent_evaluated") or 0)
        >= DEFAULT_MINIMUM_HOLDOUT_OUTCOMES
        and row.get("holdout_hit_rate_pct") is not None
        and row.get("holdout_average_r") is not None
    ]
    for row in eligible:
        dominated = any(
            other is not row
            and float(other["holdout_hit_rate_pct"]) >= float(row["holdout_hit_rate_pct"])
            and float(other["holdout_average_r"]) >= float(row["holdout_average_r"])
            and (
                float(other["holdout_hit_rate_pct"]) > float(row["holdout_hit_rate_pct"])
                or float(other["holdout_average_r"]) > float(row["holdout_average_r"])
            )
            for other in eligible
        )
        row["pareto_front_holdout"] = not dominated
    return {
        "rows": rows,
        "research_cases": len(research_cases),
        "pareto_versions": [row["strategy_version"] for row in rows if row["pareto_front_holdout"]],
        "objective": "Trefferquote und durchschnittliches R gemeinsam, mit Profitfaktor und Drawdown als Schutzgrenzen",
        "holdout_selects_production_automatically": False,
        "derived_hypotheses_require_locked_rerun": True,
        "production_activation_allowed": False,
    }


def _strategy_case_segments(cases: Sequence[Mapping[str, object]]) -> dict:
    return {
        "market_regimes": _segmented_case_metrics(
            cases,
            label="market_regime",
            value_getter=lambda case: ((case.get("snapshot") or {}).get("strategy") or {}).get(
                "market_phase"
            ),
        ),
        "volatility_regimes": _segmented_case_metrics(
            cases,
            label="volatility_regime",
            value_getter=lambda case: ((case.get("snapshot") or {}).get("strategy") or {}).get(
                "volatility_regime"
            ),
        ),
        "setup_types": _segmented_case_metrics(
            cases,
            label="setup_type",
            value_getter=lambda case: ((case.get("snapshot") or {}).get("strategy") or {}).get(
                "setup_type"
            ),
        ),
        "calendar_years": _segmented_case_metrics(
            cases,
            label="calendar_year",
            value_getter=lambda case: str(case.get("signal_at") or "")[:4],
        ),
    }


def _rsi_observational_bucket(value: object) -> str:
    rsi = value_or_none(value)
    if rsi is None:
        return "Nicht verfügbar"
    if rsi < 30:
        return "RSI < 30"
    if rsi < 40:
        return "RSI 30–<40"
    if rsi < 50:
        return "RSI 40–<50"
    if rsi < 60:
        return "RSI 50–<60"
    if rsi < 70:
        return "RSI 60–<70"
    return "RSI >= 70"


def _observational_segment_rows(
    cases: Sequence[Mapping[str, object]],
    *,
    value_getter,
    minimum_segment_cases: int,
) -> list[dict]:
    groups: dict[str, list[Mapping[str, object]]] = {}
    for case in cases:
        groups.setdefault(str(value_getter(case) or "Nicht verfügbar"), []).append(case)
    rows: list[dict] = []
    for segment, group in sorted(groups.items()):
        metrics = swing_walk_forward_case_metrics(group)
        effective = int(metrics.get("effective_independent_evaluated") or 0)
        rows.append(
            {
                "segment": segment,
                **metrics,
                "by_split": {
                    split: swing_walk_forward_case_metrics(
                        [case for case in group if case.get("research_split") == split]
                    )
                    for split in ("development", "validation", "holdout")
                },
                "minimum_segment_cases": int(minimum_segment_cases),
                "small_sample": effective < int(minimum_segment_cases),
                "research_hint_only": True,
                "improvement_claimed": False,
            }
        )
    return rows


def swing_observational_rsi_ema_report(
    cases: Sequence[Mapping[str, object]],
    *,
    minimum_segment_cases: int = DEFAULT_MINIMUM_SEGMENT_OUTCOMES,
) -> dict:
    """Segment stored sidecars without selecting or changing any strategy rule."""
    eligible = [
        case
        for case in cases
        if bool(case.get("selection_eligible", True))
    ]
    available = [
        case
        for case in eligible
        if case.get("observational_feature_status") == "available"
        and isinstance(case.get("observational_features"), Mapping)
    ]

    def values(case: Mapping[str, object]) -> dict:
        return dict((case.get("observational_features") or {}).get("values") or {})

    def strategy(case: Mapping[str, object]) -> dict:
        return dict((case.get("snapshot") or {}).get("strategy") or {})

    dimensions = {
        "rsi_ranges": lambda case: _rsi_observational_bucket(values(case).get("rsi_14")),
        "ema20_vs_ema50": lambda case: values(case).get("ema20_position_vs_ema50"),
        "close_vs_ema20": lambda case: values(case).get("close_position_vs_ema20"),
        "close_vs_ema50": lambda case: values(case).get("close_position_vs_ema50"),
        "close_ema_stack": lambda case: (
            "Kurs > EMA20 > EMA50"
            if values(case).get("close_above_ema20_above_ema50") is True
            else "Andere EMA-Anordnung"
            if values(case).get("close_above_ema20_above_ema50") is False
            else "Nicht verfügbar"
        ),
        "rsi_by_setup": lambda case: (
            f"{_rsi_observational_bucket(values(case).get('rsi_14'))} | "
            f"{strategy(case).get('setup_type') or 'Unbekannt'}"
        ),
        "ema20_vs_ema50_by_setup": lambda case: (
            f"{values(case).get('ema20_position_vs_ema50') or 'Nicht verfügbar'} | "
            f"{strategy(case).get('setup_type') or 'Unbekannt'}"
        ),
        "close_ema_stack_by_setup": lambda case: (
            f"{'Kurs > EMA20 > EMA50' if values(case).get('close_above_ema20_above_ema50') is True else 'Andere EMA-Anordnung' if values(case).get('close_above_ema20_above_ema50') is False else 'Nicht verfügbar'} | "
            f"{strategy(case).get('setup_type') or 'Unbekannt'}"
        ),
        "market_phases": lambda case: strategy(case).get("market_phase") or "Unbekannt",
        "volatility_regimes": lambda case: strategy(case).get("volatility_regime") or "Unbekannt",
    }
    segments = {
        name: _observational_segment_rows(
            available,
            value_getter=getter,
            minimum_segment_cases=minimum_segment_cases,
        )
        for name, getter in dimensions.items()
    }
    return {
        "feature_version": SWING_OBSERVATIONAL_FEATURE_VERSION,
        "eligible_cases": len(eligible),
        "feature_cases": len(available),
        "legacy_or_unavailable_cases": len(eligible) - len(available),
        "coverage_pct": len(available) / len(eligible) * 100 if eligible else 0.0,
        "segments": segments,
        "predefined_rsi_buckets": [
            "RSI < 30",
            "RSI 30–<40",
            "RSI 40–<50",
            "RSI 50–<60",
            "RSI 60–<70",
            "RSI >= 70",
        ],
        "minimum_segment_cases": int(minimum_segment_cases),
        "automatic_threshold_search": False,
        "automatic_rule_change": False,
        "holdout_used_for_rule_selection": False,
        "improvement_claimed": False,
        "research_hints_only": True,
        "future_challenger_contract": {
            "status": "not_created",
            "manual_hypothesis_selection_required": True,
            "rule_must_be_frozen_before_test": True,
            "new_strategy_fingerprint_required": True,
            "new_hypothetical_trades_required": True,
            "baseline_storage_separate": True,
            "new_research_epoch_or_fresh_walk_forward_required": True,
            "current_observations_are_confirmatory_evidence": False,
            "production_activation_allowed": False,
        },
    }


def swing_technical_challenger_report(
    cases: Sequence[Mapping[str, object]],
    *,
    minimum_validation_cases: int = 200,
    minimum_holdout_cases: int = 200,
    minimum_variant_trade_retention: float = 0.50,
) -> dict:
    """Assess locked challengers without ever promoting one to production."""
    eligible = [dict(case) for case in cases if case.get("selection_eligible", True)]
    grouped: dict[str, list[dict]] = {}
    metadata: dict[str, dict] = {}
    for case in eligible:
        strategy = dict((case.get("snapshot") or {}).get("strategy") or {})
        version = str(strategy.get("strategy_version") or "")
        if not version:
            continue
        grouped.setdefault(version, []).append(case)
        metadata.setdefault(
            version,
            {
                "strategy_name": str(strategy.get("strategy_name") or version),
                "strategy_family": str(strategy.get("strategy_family") or "legacy_unspecified"),
                "parameter_variant": str(strategy.get("parameter_variant") or "unspecified"),
                "technical_filter": dict(strategy.get("technical_filter") or {}),
            },
        )
    baseline_version = next(
        (
            version
            for version, item in metadata.items()
            if item.get("strategy_name") == "current"
        ),
        None,
    )
    baseline_cases = grouped.get(str(baseline_version), []) if baseline_version else []
    baseline_by_split = {
        split: swing_walk_forward_case_metrics(
            [case for case in baseline_cases if case.get("research_split") == split]
        )
        for split in ("development", "validation", "holdout")
    }
    rows: list[dict] = []
    for version, group in sorted(grouped.items()):
        item = metadata[version]
        if item["strategy_family"] not in {
            "long_v1_plus_rsi",
            "long_v1_plus_ema",
            "long_v1_plus_ema_rsi",
            "long_v1_setup_type",
        }:
            continue
        by_split = {
            split: swing_walk_forward_case_metrics(
                [case for case in group if case.get("research_split") == split]
            )
            for split in ("development", "validation", "holdout")
        }
        baseline_total = max(int(swing_walk_forward_case_metrics(baseline_cases)["evaluated"]), 1)
        overall = swing_walk_forward_case_metrics(group)
        retention = int(overall["evaluated"]) / baseline_total
        unseen_advantages: dict[str, bool] = {}
        for split in ("validation", "holdout"):
            challenger = by_split[split]
            baseline = baseline_by_split[split]
            unseen_advantages[split] = bool(
                int(challenger["evaluated"])
                >= (minimum_validation_cases if split == "validation" else minimum_holdout_cases)
                and challenger["average_r"] is not None
                and baseline["average_r"] is not None
                and float(challenger["average_r"]) > float(baseline["average_r"])
                and challenger["profit_factor"] is not None
                and baseline["profit_factor"] is not None
                and float(challenger["profit_factor"]) > float(baseline["profit_factor"])
                and float(challenger["maximum_drawdown_r"])
                <= max(float(baseline["maximum_drawdown_r"]) * 1.10, 0.0)
            )
        rows.append(
            {
                **item,
                "strategy_version": version,
                "overall": overall,
                "by_split": by_split,
                "segments": _strategy_case_segments(group),
                "trade_retention_vs_baseline": retention,
                "lower_trade_count_visible": retention < 1.0,
                "validation_advantage": unseen_advantages["validation"],
                "holdout_advantage": unseen_advantages["holdout"],
                "unseen_robust_advantage": all(unseen_advantages.values())
                and retention >= minimum_variant_trade_retention,
                "automatic_production_activation": False,
            }
        )
    family_rows: list[dict] = []
    for family in sorted({str(row["strategy_family"]) for row in rows}):
        variants = [row for row in rows if row["strategy_family"] == family]
        enough_variants = len(variants) >= 2
        robust_count = sum(bool(row["unseen_robust_advantage"]) for row in variants)
        family_rows.append(
            {
                "strategy_family": family,
                "variants": len(variants),
                "parameter_robust": bool(enough_variants and robust_count == len(variants)),
                "interesting_for_manual_review": bool(
                    enough_variants and robust_count == len(variants)
                ),
                "robust_variants": robust_count,
                "reason": (
                    "Alle vorab festgelegten Varianten zeigen einen robusten Vorteil auf Validation und Holdout."
                    if enough_variants and robust_count == len(variants)
                    else "Kein stabiler Vorteil über alle vorab festgelegten Varianten belegt."
                ),
                "production_activation_allowed": False,
            }
        )
    return {
        "baseline_strategy_version": baseline_version,
        "baseline_unchanged": True,
        "baseline_by_split": baseline_by_split,
        "challengers": rows,
        "families": family_rows,
        "minimum_validation_cases": int(minimum_validation_cases),
        "minimum_holdout_cases": int(minimum_holdout_cases),
        "selection_objective": "Robustheit statt historisch höchster Gewinn",
        "holdout_selects_production_automatically": False,
        "production_activation_allowed": False,
    }


def swing_walk_forward_archive_rows(
    cases: Sequence[Mapping[str, object]],
) -> list[dict]:
    rows: list[dict] = []
    cluster_by_case_id = {
        case_id: cluster
        for cluster in _case_dependency_clusters(cases)
        for case_id in cluster["case_ids"]
    }
    for case in cases:
        snapshot = dict(case.get("snapshot") or {})
        strategy = dict(snapshot.get("strategy") or {})
        asset = dict(snapshot.get("asset") or {})
        order_plan = dict(snapshot.get("order_plan") or {})
        observational = dict(case.get("observational_features") or {})
        observational_values = dict(observational.get("values") or {})
        identity = _case_research_identity(case)
        dependency_cluster = cluster_by_case_id.get(str(case.get("case_id") or ""), {})
        rows.append(
            {
                "Datum": str(case.get("signal_at") or "")[:10],
                "Ticker": str(case.get("symbol") or asset.get("ticker") or ""),
                "Listing-ID": str(identity.get("listing_id") or ""),
                "Issuer-ID": str(identity.get("issuer_id") or ""),
                "Identitätsquelle": str(identity.get("issuer_identity_source") or "Unbekannt"),
                "Evidenzcluster": str(dependency_cluster.get("cluster_id") or ""),
                "Rohfälle im Evidenzcluster": dependency_cluster.get("raw_cases"),
                "Abhängige Listings": bool(dependency_cluster.get("dependent_listings")),
                "Asset-Typ": str(asset.get("asset_type") or "Unbekannt"),
                "Strategie": str(strategy.get("strategy_name") or strategy.get("strategy_version") or "Legacy"),
                "Sampling": str(case.get("sampling_mode") or strategy.get("sampling_mode") or "Legacy"),
                "Testrunde": str(case.get("selection_round") or strategy.get("selection_round") or "Legacy"),
                "Rundenrolle": str(
                    case.get("selection_round_role")
                    or strategy.get("selection_round_role")
                    or "Legacy"
                ),
                "Horizont Sitzungen": case.get("evaluation_horizon_sessions"),
                "Forschungsfenster": str(case.get("research_split") or "Legacy"),
                "Setup": str(strategy.get("setup_type") or "Unbekannt"),
                "Marktphase": str(strategy.get("market_phase") or "Unbekannt"),
                "RSI-/EMA-Featurestatus": str(
                    case.get("observational_feature_status") or "legacy_feature_not_recorded"
                ),
                "RSI14": observational_values.get("rsi_14"),
                "EMA20": observational_values.get("ema_20"),
                "EMA50": observational_values.get("ema_50"),
                "Kurs relativ EMA20": observational_values.get("close_relative_to_ema20"),
                "Kurs relativ EMA50": observational_values.get("close_relative_to_ema50"),
                "EMA20 relativ EMA50": observational_values.get("ema20_relative_to_ema50"),
                "Einstieg": order_plan.get("limit_price_original"),
                "Stop": order_plan.get("initial_stop_original"),
                "Ziel 1": order_plan.get("target_1_original"),
                "Status": str(case.get("status") or "Unbekannt"),
                "Ergebnis R": case.get("result_r"),
                "Ergebnis %": case.get("result_pct"),
                "Forward-Verknüpfung": str(case.get("real_forward_link_status") or "not_linked"),
                "Bevorzugte Evidenz": str(case.get("preferred_evidence") or "historical_separate"),
                "Als historisches Monitoring gezählt": bool(
                    case.get("historical_monitoring_counted", True)
                ),
                "Überlappung bereinigt": bool(case.get("overlap_purged")),
                "Produktionsvergleichbar": False,
            }
        )
    return rows


def swing_walk_forward_summary(
    path: Path = DEFAULT_SWING_WALK_FORWARD_DB_PATH,
) -> dict:
    if not Path(path).exists():
        return {
            "runs": 0,
            "cases": 0,
            "raw_cases": 0,
            "evaluated": 0,
            "raw_evaluated": 0,
            "effective_independent_cases": 0,
            "effective_independent_evaluated": 0,
            "dependency_adjustment_required": False,
            "hit_rate_pct": None,
            "average_r": None,
            "profit_factor": None,
            "maximum_drawdown_r": None,
            "stored_cases_total": 0,
            "stored_case_revisions_total": 0,
            "superseded_case_revisions": 0,
            "case_identity_conflicts_resolved": 0,
            "real_forward_linkage": {
                "links": 0,
                "exact_same_trade": 0,
                "related_same_asset_day": 0,
                "historical_monitoring_excluded": 0,
            },
            "by_market_phase": [],
            "strategy_comparison": {"rows": [], "research_cases": 0, "pareto_versions": []},
            "technical_challengers": {
                "challengers": [],
                "families": [],
                "production_activation_allowed": False,
            },
            "observational_rsi_ema": {
                "feature_version": SWING_OBSERVATIONAL_FEATURE_VERSION,
                "eligible_cases": 0,
                "feature_cases": 0,
                "legacy_or_unavailable_cases": 0,
                "segments": {},
                "automatic_rule_change": False,
                "improvement_claimed": False,
                "research_hints_only": True,
            },
            "separate_from_real_forward": True,
            "production_comparable": False,
        }
    initialize_swing_walk_forward_store(path)
    with _connect(Path(path)) as connection:
        run_count = int(connection.execute("SELECT COUNT(*) FROM walk_forward_runs").fetchone()[0])
        stored_case_revisions_total = int(
            connection.execute("SELECT COUNT(*) FROM walk_forward_cases").fetchone()[0]
        )
        identity_conflicts_total = int(
            connection.execute(
                "SELECT COUNT(*) FROM walk_forward_case_identity_conflicts"
            ).fetchone()[0]
        )
    cases = load_swing_walk_forward_cases(path)
    research_cases = [
        case for case in cases if case.get("case_version") == SWING_WALK_FORWARD_ENGINE_VERSION
    ]
    baseline_cases = [
        case
        for case in research_cases
        if str(((case.get("snapshot") or {}).get("strategy") or {}).get("strategy_name") or "")
        == "current"
        and int(case.get("evaluation_horizon_sessions") or 25) == 25
        and bool(case.get("selection_eligible", True))
    ]
    primary_cases = baseline_cases or research_cases or cases
    metrics = swing_walk_forward_case_metrics(primary_cases)
    evaluated = [case for case in primary_cases if case.get("result_r") is not None]
    phase_groups: dict[str, list[dict]] = {}
    for case in evaluated:
        phase = str(((case.get("snapshot") or {}).get("strategy") or {}).get("market_phase") or "Unbekannt")
        phase_groups.setdefault(phase, []).append(case)
    by_market_phase = [
        {"market_phase": phase, **swing_walk_forward_case_metrics(group)}
        for phase, group in sorted(phase_groups.items())
    ]
    by_asset_type = _segmented_case_metrics(
        evaluated,
        label="asset_type",
        value_getter=lambda case: ((case.get("snapshot") or {}).get("asset") or {}).get("asset_type"),
    )
    by_setup_type = _segmented_case_metrics(
        evaluated,
        label="setup_type",
        value_getter=lambda case: ((case.get("snapshot") or {}).get("strategy") or {}).get("setup_type"),
    )
    by_volatility_regime = _segmented_case_metrics(
        evaluated,
        label="volatility_regime",
        value_getter=lambda case: ((case.get("snapshot") or {}).get("strategy") or {}).get("volatility_regime"),
    )
    by_research_split = _segmented_case_metrics(
        evaluated,
        label="research_split",
        value_getter=lambda case: case.get("research_split") or "Legacy",
    )
    by_sampling_mode = _segmented_case_metrics(
        evaluated,
        label="sampling_mode",
        value_getter=lambda case: case.get("sampling_mode") or "Legacy",
    )
    by_selection_round = _segmented_case_metrics(
        evaluated,
        label="selection_round",
        value_getter=lambda case: case.get("selection_round") or "Legacy",
    )
    by_signal_year = _segmented_case_metrics(
        evaluated,
        label="signal_year",
        value_getter=lambda case: str(case.get("signal_at") or "")[:4] or "Unbekannt",
    )
    raw_monitoring_cases = [
        case
        for case in research_cases
        if not case.get("selection_eligible", True)
    ]
    monitoring_cases = [
        case for case in raw_monitoring_cases if case.get("historical_monitoring_counted", True)
    ]
    unique_links = {
        str(link.get("link_id") or ""): link
        for case in cases
        for link in case.get("real_forward_links") or []
        if str(link.get("link_id") or "")
    }
    exact_links = sum(
        link.get("relation") == "exact_same_trade" for link in unique_links.values()
    )
    has_technical_challengers = any(
        str(((case.get("snapshot") or {}).get("strategy") or {}).get("strategy_name") or "")
        in TECHNICAL_CHALLENGER_PROFILE_NAMES
        for case in cases
    )
    return {
        "runs": run_count,
        **metrics,
        "stored_cases_total": len(cases),
        "stored_case_revisions_total": stored_case_revisions_total,
        "superseded_case_revisions": max(stored_case_revisions_total - len(cases), 0),
        "case_identity_conflicts_resolved": identity_conflicts_total,
        "identity_resolution_version": SWING_CASE_IDENTITY_RESOLUTION_VERSION,
        "dependency_contract_version": SWING_EVIDENCE_DEPENDENCY_VERSION,
        "current_research_cases": len(research_cases),
        "legacy_cases": len(cases) - len(research_cases),
        "by_market_phase": by_market_phase,
        "by_asset_type": by_asset_type,
        "by_setup_type": by_setup_type,
        "by_volatility_regime": by_volatility_regime,
        "by_research_split": by_research_split,
        "by_sampling_mode": by_sampling_mode,
        "by_selection_round": by_selection_round,
        "by_signal_year": by_signal_year,
        "recent_monitoring": swing_walk_forward_case_metrics(monitoring_cases),
        "recent_monitoring_before_forward_deduplication": swing_walk_forward_case_metrics(
            raw_monitoring_cases
        ),
        "real_forward_linkage": {
            "links": len(unique_links),
            "exact_same_trade": exact_links,
            "related_same_asset_day": len(unique_links) - exact_links,
            "historical_monitoring_excluded": len(raw_monitoring_cases) - len(monitoring_cases),
            "priority": "real_forward_for_exact_match",
            "different_strategy_or_plan_remains_separate": True,
        },
        "strategy_comparison": swing_walk_forward_strategy_comparison(cases),
        "technical_challengers": (
            swing_technical_challenger_report(cases)
            if has_technical_challengers
            else {
                "challengers": [],
                "families": [],
                "production_activation_allowed": False,
            }
        ),
        "observational_rsi_ema": swing_observational_rsi_ema_report(primary_cases),
        "separate_from_real_forward": True,
        "production_comparable": False,
    }
