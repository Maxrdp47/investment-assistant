from __future__ import annotations

"""Causal R4-B equity/ETF capability features; no outcome or strategy hook."""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT / "config" / "multi_asset_v2_r4b.json"


def load_contract(path: Path = DEFAULT_CONTRACT) -> tuple[dict[str, Any], str]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if contract["program_block"] != "R4-B":
        raise ValueError("Wrong R4-B contract")
    if contract["market_benchmark"] != "ACWI" or contract["sector_benchmark_active"]:
        raise ValueError("R4-B historical benchmark scope changed")
    if contract["return_lookbacks_sessions"] != [20, 60, 120]:
        raise ValueError("R4-B lookbacks changed")
    digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return contract, digest


def _normalized(frame: pd.DataFrame, *, columns: tuple[str, ...]) -> pd.DataFrame:
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates:
        raise ValueError("R4-B requires a unique DatetimeIndex")
    if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
        raise ValueError("R4-B requires timezone-naive daily session dates")
    if any(column not in frame for column in columns):
        raise ValueError("R4-B missing required OHLC column")
    result = frame.sort_index(kind="stable").copy(deep=True)
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype(float)
        if result[column].isna().any() or (result[column] <= 0).any():
            raise ValueError(f"R4-B invalid {column} source values")
    if all(name in result for name in ("Open", "High", "Low", "Close")):
        if (
            (result["Low"] > result["Open"])
            | (result["Open"] > result["High"])
            | (result["Low"] > result["Close"])
            | (result["Close"] > result["High"])
        ).any():
            raise ValueError("R4-B OHLC envelope violation")
    return result


def _pivot_sequence(high: np.ndarray, low: np.ndarray) -> tuple[list[str], list[float], list[float]]:
    """Confirm a pivot only after two later, already completed bars exist."""

    sequence: list[str] = []
    confirmed_highs: list[float] = []
    confirmed_lows: list[float] = []
    hh_flags: list[float] = []
    hl_flags: list[float] = []
    for position in range(len(high)):
        candidate = position - 2
        if candidate >= 2:
            high_window = high[candidate - 2 : position + 1]
            low_window = low[candidate - 2 : position + 1]
            if high[candidate] == high_window.max() and np.count_nonzero(high_window == high[candidate]) == 1:
                confirmed_highs.append(float(high[candidate]))
            if low[candidate] == low_window.min() and np.count_nonzero(low_window == low[candidate]) == 1:
                confirmed_lows.append(float(low[candidate]))
        if len(confirmed_highs) < 2 or len(confirmed_lows) < 2:
            sequence.append("INSUFFICIENT_CONFIRMED_PIVOTS")
            hh_flags.append(np.nan)
            hl_flags.append(np.nan)
            continue
        higher_high = confirmed_highs[-1] > confirmed_highs[-2]
        lower_high = confirmed_highs[-1] < confirmed_highs[-2]
        higher_low = confirmed_lows[-1] > confirmed_lows[-2]
        lower_low = confirmed_lows[-1] < confirmed_lows[-2]
        hh_flags.append(float(higher_high) if higher_high or lower_high else np.nan)
        hl_flags.append(float(higher_low) if higher_low or lower_low else np.nan)
        if higher_high and higher_low:
            sequence.append("HIGHER_HIGH_HIGHER_LOW")
        elif lower_high and lower_low:
            sequence.append("LOWER_HIGH_LOWER_LOW")
        elif higher_high and lower_low:
            sequence.append("HIGHER_HIGH_LOWER_LOW")
        elif lower_high and higher_low:
            sequence.append("LOWER_HIGH_HIGHER_LOW")
        else:
            sequence.append("MIXED_OR_EQUAL")
    return sequence, hh_flags, hl_flags


def build_r4b_features(
    asset_ohlc: pd.DataFrame,
    benchmark_close: pd.DataFrame,
    *,
    contract_path: Path = DEFAULT_CONTRACT,
) -> pd.DataFrame:
    """Compute after-close features from same-or-earlier bars only.

    The global ACWI fallback does not imply a verified historical region or
    sector assignment. A same-date US benchmark close might be in the future
    for another market; therefore only strictly earlier benchmark dates are
    eligible, with a conservative five-calendar-day freshness ceiling.
    """

    contract, fingerprint = load_contract(contract_path)
    asset = _normalized(asset_ohlc, columns=("Open", "High", "Low", "Close"))
    benchmark = _normalized(benchmark_close, columns=("Close",))
    close = asset["Close"]
    result = pd.DataFrame(index=asset.index)
    result["r4b_contract_fingerprint"] = fingerprint
    result["benchmark_symbol"] = contract["market_benchmark"]
    result["benchmark_scope"] = contract["benchmark_scope"]
    benchmark_positions = benchmark.index.searchsorted(asset.index, side="left") - 1
    safe_positions = np.maximum(benchmark_positions, 0)
    source_dates = benchmark.index.take(safe_positions)
    freshness = asset.index - source_dates
    benchmark_available = (
        (benchmark_positions >= 0)
        & (freshness <= pd.Timedelta(days=5))
    )
    result["benchmark_known_date"] = pd.Series(source_dates.strftime("%Y-%m-%d"), index=asset.index).where(benchmark_available)
    result["benchmark_age_calendar_days"] = pd.Series(
        freshness.days.astype(float), index=asset.index
    ).where(benchmark_available)
    for horizon in contract["return_lookbacks_sessions"]:
        result[f"asset_return_{horizon}"] = close.div(close.shift(horizon)).sub(1)
        if "SegmentId" in benchmark:
            segment = pd.to_numeric(benchmark["SegmentId"], errors="coerce")
            if (
                segment.isna().any()
                or (segment < 0).any()
                or (segment % 1 != 0).any()
                or not segment.astype(int).is_monotonic_increasing
            ):
                raise ValueError("R4-B invalid benchmark segment identifiers")
            benchmark_return = benchmark["Close"].div(
                benchmark.groupby(segment.astype(int), sort=False)["Close"].shift(horizon)
            ).sub(1)
        else:
            benchmark_return = benchmark["Close"].div(
                benchmark["Close"].shift(horizon)
            ).sub(1)
        aligned = pd.Series(
            benchmark_return.to_numpy(dtype=float)[safe_positions], index=asset.index
        ).where(benchmark_available)
        result[f"benchmark_return_{horizon}"] = aligned
        result[f"relative_momentum_{horizon}"] = result[f"asset_return_{horizon}"].sub(aligned)

    prior20_high = asset["High"].shift(1).rolling(20, min_periods=20).max()
    prior20_low = asset["Low"].shift(1).rolling(20, min_periods=20).min()
    prior60_high = asset["High"].shift(1).rolling(60, min_periods=60).max()
    prior60_low = asset["Low"].shift(1).rolling(60, min_periods=60).min()
    result["resistance_distance_prior20_pct"] = prior20_high.div(close).sub(1)
    result["support_distance_prior20_pct"] = close.div(prior20_low).sub(1)
    result["breakout_above_prior20_high"] = close.gt(prior20_high).where(prior20_high.notna())
    result["pullback_from_prior20_high_pct"] = close.div(prior20_high).sub(1)
    width20 = prior20_high.sub(prior20_low)
    width60 = prior60_high.sub(prior60_low)
    result["consolidation_width_ratio_20_60"] = width20.div(width60.where(width60 > 0))
    for horizon in contract["structure"]["trend_efficiency_sessions"]:
        path = close.diff().abs().rolling(horizon, min_periods=horizon).sum()
        displacement = close.sub(close.shift(horizon)).abs()
        result[f"trend_efficiency_{horizon}"] = displacement.div(path.where(path > 0))

    structure, hh, hl = _pivot_sequence(
        asset["High"].to_numpy(dtype=float), asset["Low"].to_numpy(dtype=float)
    )
    result["confirmed_structure_sequence"] = structure
    result["confirmed_higher_high"] = hh
    result["confirmed_higher_low"] = hl
    result["sector_benchmark_status"] = "UNAVAILABLE_NO_HISTORICAL_SECTOR_MAPPING"
    result["historical_region_status"] = "UNVERIFIED_GLOBAL_FALLBACK_ONLY"
    result["strategy_filter_created"] = False
    return result
