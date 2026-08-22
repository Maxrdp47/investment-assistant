from __future__ import annotations

"""Causal shared market features for the frozen Swing broad-research pass."""

import math
from collections import defaultdict
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


BROAD_CONTEXT_VERSION = "swing-broad-shared-context-2026.08.22-v1"
BROAD_BENCHMARK_MAPPING_VERSION = "swing-broad-benchmark-map-2026.08.22-v1"
BROAD_BREADTH_VERSION = "swing-broad-frozen-universe-breadth-2026.08.22-v1"
RETURN_HORIZONS = (20, 60, 120)
EXTREME_HORIZONS = (20, 50, 100, 252)
REGIONAL_BENCHMARKS = {"USA": "SPY", "Australien": "EWA", "Global": "ACWI"}
GLOBAL_BENCHMARK = "ACWI"


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _return(close: np.ndarray, position: int, horizon: int) -> float | None:
    if position < horizon or close[position - horizon] <= 0:
        return None
    return float(close[position] / close[position - horizon] - 1)


def _asof_return(frame: pd.DataFrame, day: pd.Timestamp, start_day: pd.Timestamp) -> float | None:
    history = frame.loc[:day]
    if history.empty:
        return None
    start = history.loc[:start_day]
    if start.empty:
        return None
    current_close = _number(history.iloc[-1].get("Close"))
    start_close = _number(start.iloc[-1].get("Close"))
    return current_close / start_close - 1 if current_close is not None and start_close else None


def relative_strength_features(
    frame: pd.DataFrame,
    position: int,
    *,
    asset: Mapping[str, object],
    benchmark_histories: Mapping[str, pd.DataFrame],
) -> dict[str, object]:
    close = frame["Close"].to_numpy(dtype=float)
    day = pd.Timestamp(frame.index[position])
    region = str(asset.get("region") or "")
    preferred = REGIONAL_BENCHMARKS.get(region)
    benchmark_symbol = preferred if preferred in benchmark_histories else GLOBAL_BENCHMARK
    benchmark = benchmark_histories.get(benchmark_symbol)
    status = "available" if benchmark is not None and not benchmark.empty else "benchmark_unavailable"
    rows: dict[str, dict[str, object]] = {}
    for horizon in RETURN_HORIZONS:
        asset_return = _return(close, position, horizon)
        benchmark_return = (
            _asof_return(
                benchmark,
                day,
                pd.Timestamp(frame.index[position - horizon]),
            )
            if benchmark is not None and position >= horizon
            else None
        )
        rows[f"{horizon}d"] = {
            "asset_return": asset_return,
            "benchmark_return": benchmark_return,
            "relative_strength": (
                asset_return - benchmark_return
                if asset_return is not None and benchmark_return is not None
                else None
            ),
        }
    current_20 = _number(rows["20d"].get("relative_strength"))
    prior_asset_20 = (
        float(close[position - 20] / close[position - 40] - 1)
        if position >= 40 and close[position - 40] > 0
        else None
    )
    prior_benchmark_20 = (
        _asof_return(
            benchmark,
            pd.Timestamp(frame.index[position - 20]),
            pd.Timestamp(frame.index[position - 40]),
        )
        if benchmark is not None and position >= 40
        else None
    )
    prior_relative_20 = (
        prior_asset_20 - prior_benchmark_20
        if prior_asset_20 is not None and prior_benchmark_20 is not None
        else None
    )
    return {
        "status": status,
        "mapping_version": BROAD_BENCHMARK_MAPPING_VERSION,
        "benchmark_symbol": benchmark_symbol if benchmark is not None else None,
        "benchmark_scope": "regional" if preferred == benchmark_symbol else "global_fallback",
        "horizons": rows,
        "relative_momentum_20d": (
            current_20 - prior_relative_20
            if current_20 is not None and prior_relative_20 is not None
            else None
        ),
        "sector_benchmark": None,
        "sector_benchmark_status": "historical_point_in_time_membership_unavailable",
        "comparison_group_percentile": None,
        "comparison_group_percentile_status": "not_precomputed_without_historical_membership_claim",
        "benchmark_bars_after_feature_at": 0,
    }


def _efficiency(values: np.ndarray) -> dict[str, float | None]:
    if len(values) < 2:
        return {"efficiency": None, "counter_move_share": None}
    changes = np.diff(values)
    total = float(np.sum(np.abs(changes)))
    net = float(values[-1] - values[0])
    efficiency = abs(net) / total if total > 0 else 0.0
    opposite = float(np.sum(np.abs(changes[changes < 0 if net >= 0 else changes > 0])))
    return {
        "efficiency": efficiency,
        "counter_move_share": opposite / total if total > 0 else 0.0,
    }


def trend_quality_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    row = frame.iloc[position]
    atr = _number(row.get("ATR_14"))
    close = frame["Close"].to_numpy(dtype=float)
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    ema20 = frame["EMA_20"].to_numpy(dtype=float)
    ema50 = frame["EMA_50"].to_numpy(dtype=float)

    def slope(values: np.ndarray, horizon: int = 5) -> tuple[float | None, float | None]:
        if position < horizon or not math.isfinite(values[position - horizon]):
            return None, None
        raw = float((values[position] - values[position - horizon]) / horizon)
        return raw, raw / atr if atr and atr > 0 else None

    ema20_slope, ema20_atr = slope(ema20)
    ema50_slope, ema50_atr = slope(ema50)
    lookback = close[max(0, position - 59) : position + 1]
    recent = close[max(0, position - 19) : position + 1]
    highs = high[max(0, position - 19) : position + 1]
    lows = low[max(0, position - 19) : position + 1]
    return {
        "ema20_slope_per_session": ema20_slope,
        "ema50_slope_per_session": ema50_slope,
        "ema20_slope_atr_per_session": ema20_atr,
        "ema50_slope_atr_per_session": ema50_atr,
        "price_slopes": {
            f"{horizon}d": (
                (close[position] / close[position - horizon] - 1) / horizon
                if position >= horizon and close[position - horizon] > 0
                else None
            )
            for horizon in (5, 20, 60)
        },
        "rising_close_share_20d": float(np.mean(np.diff(recent) > 0)) if len(recent) >= 2 else None,
        "higher_high_share_20d": float(np.mean(np.diff(highs) > 0)) if len(highs) >= 2 else None,
        "higher_low_share_20d": float(np.mean(np.diff(lows) > 0)) if len(lows) >= 2 else None,
        "lower_high_share_20d": float(np.mean(np.diff(highs) < 0)) if len(highs) >= 2 else None,
        "lower_low_share_20d": float(np.mean(np.diff(lows) < 0)) if len(lows) >= 2 else None,
        "trend_20d": _efficiency(recent),
        "trend_60d": _efficiency(lookback),
        "additional_trend_indicator_added": False,
    }


def volatility_structure_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    row = frame.iloc[position]
    close = float(row["Close"])
    atrs = frame["ATR_14"].to_numpy(dtype=float)
    ranges = (frame["High"] - frame["Low"]).to_numpy(dtype=float)
    volumes = frame["Volume"].to_numpy(dtype=float)
    atr = _number(row.get("ATR_14"))

    def percentile(window: int) -> float | None:
        start = max(0, position - window)
        prior = atrs[start:position]
        prior = prior[np.isfinite(prior)]
        return float(np.mean(prior <= atr) * 100) if atr is not None and len(prior) else None

    prior_ranges = ranges[max(0, position - 20) : position]
    short_ranges = ranges[max(0, position - 5) : position]
    prior_volumes = volumes[max(0, position - 20) : position]
    normal_range = float(np.mean(prior_ranges)) if len(prior_ranges) else None
    signal_range = float(ranges[position])
    range_expansion = signal_range / normal_range if normal_range and normal_range > 0 else None
    volume_normal = float(np.mean(prior_volumes)) if len(prior_volumes) else None
    volume_expansion = volumes[position] / volume_normal if volume_normal and volume_normal > 0 else None
    return {
        "atr_relative_to_close": atr / close if atr is not None and close > 0 else None,
        "atr_percentiles_prior_only": {f"{window}d": percentile(window) for window in (60, 120, 252)},
        "atr_change": {
            f"{horizon}d": (
                atr / atrs[position - horizon] - 1
                if atr is not None
                and position >= horizon
                and math.isfinite(atrs[position - horizon])
                and atrs[position - horizon] > 0
                else None
            )
            for horizon in (1, 5, 20)
        },
        "short_range_to_long_range": (
            float(np.mean(short_ranges)) / normal_range
            if len(short_ranges) and normal_range and normal_range > 0
            else None
        ),
        "compression_before_signal": (
            float(np.mean(short_ranges)) / normal_range
            if len(short_ranges) and normal_range and normal_range > 0
            else None
        ),
        "signal_range_expansion": range_expansion,
        "signal_volume_expansion": volume_expansion,
        "range_and_volume_expansion": bool(
            range_expansion is not None
            and volume_expansion is not None
            and range_expansion > 1.0
            and volume_expansion > 1.0
        ),
        "signal_bar_excluded_from_prior_normal_ranges": True,
    }


def candle_quality_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    row = frame.iloc[position]
    prior = frame.iloc[position - 1]
    opening, high, low, close = map(float, (row["Open"], row["High"], row["Low"], row["Close"]))
    full_range = high - low
    body = abs(close - opening)
    upper = high - max(opening, close)
    lower = min(opening, close) - low
    atr = _number(row.get("ATR_14"))

    def consecutive(column: str, relation: str) -> int:
        values = frame[column].to_numpy(dtype=float)
        count = 0
        for index in range(position, 0, -1):
            matched = values[index] > values[index - 1] if relation == "higher" else values[index] < values[index - 1]
            if not matched:
                break
            count += 1
        return count

    gap = opening - float(prior["Close"])
    return {
        "body_to_range": body / full_range if full_range > 0 else None,
        "upper_wick_to_range": upper / full_range if full_range > 0 else None,
        "lower_wick_to_range": lower / full_range if full_range > 0 else None,
        "close_position_in_range": (close - low) / full_range if full_range > 0 else None,
        "range_to_atr": full_range / atr if atr and atr > 0 else None,
        "body_to_atr": body / atr if atr and atr > 0 else None,
        "inside_bar": bool(high <= float(prior["High"]) and low >= float(prior["Low"])),
        "outside_bar": bool(high > float(prior["High"]) and low < float(prior["Low"])),
        "gap_from_prior_close_pct": gap / float(prior["Close"]) * 100 if float(prior["Close"]) > 0 else None,
        "gap_from_prior_close_atr": gap / atr if atr and atr > 0 else None,
        "close_above_prior_high": close > float(prior["High"]),
        "close_below_prior_low": close < float(prior["Low"]),
        "consecutive_higher_highs": consecutive("High", "higher"),
        "consecutive_higher_lows": consecutive("Low", "higher"),
        "consecutive_lower_highs": consecutive("High", "lower"),
        "consecutive_lower_lows": consecutive("Low", "lower"),
        "subjective_candlestick_name": None,
    }


def historical_extreme_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    close = float(frame.iloc[position]["Close"])
    atr = _number(frame.iloc[position].get("ATR_14"))
    rows: dict[str, dict[str, object]] = {}
    for horizon in EXTREME_HORIZONS:
        start = max(0, position - horizon + 1)
        window = frame.iloc[start : position + 1]
        high_values = window["High"].to_numpy(dtype=float)
        low_values = window["Low"].to_numpy(dtype=float)
        highest, lowest = float(np.max(high_values)), float(np.min(low_values))
        width = highest - lowest
        rows[f"{horizon}d"] = {
            "history_available": len(window),
            "distance_to_high_pct": (close / highest - 1) * 100 if highest > 0 else None,
            "distance_to_low_pct": (close / lowest - 1) * 100 if lowest > 0 else None,
            "distance_to_high_atr": (close - highest) / atr if atr and atr > 0 else None,
            "distance_to_low_atr": (close - lowest) / atr if atr and atr > 0 else None,
            "sessions_since_high": len(window) - 1 - int(np.argmax(high_values)),
            "sessions_since_low": len(window) - 1 - int(np.argmin(low_values)),
            "position_in_range": (close - lowest) / width if width > 0 else None,
        }
    return rows


def consolidation_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    atr = _number(frame.iloc[position].get("ATR_14"))
    best: dict[str, object] | None = None
    for duration in range(5, 31):
        start = position - duration
        if start < 0:
            break
        window = frame.iloc[start:position]
        high, low = float(window["High"].max()), float(window["Low"].min())
        width = high - low
        closes = window["Close"].to_numpy(dtype=float)
        efficiency = _efficiency(closes)["efficiency"]
        if atr and atr > 0 and width / atr <= 4.0 and efficiency is not None and efficiency <= 0.35:
            tolerance = 0.25 * atr
            best = {
                "status": "available",
                "duration_sessions": duration,
                "high": high,
                "low": low,
                "width_pct": width / float(closes[-1]) * 100 if closes[-1] > 0 else None,
                "width_atr": width / atr,
                "net_move_pct": (closes[-1] / closes[0] - 1) * 100 if closes[0] > 0 else None,
                "upper_tests": int(np.sum(window["High"].to_numpy(dtype=float) >= high - tolerance)),
                "lower_tests": int(np.sum(window["Low"].to_numpy(dtype=float) <= low + tolerance)),
                "efficiency": efficiency,
                "source_end_day": pd.Timestamp(window.index[-1]).date().isoformat(),
            }
    if best is None:
        return {"status": "not_detected", "future_breakout_used": False}
    close = float(frame.iloc[position]["Close"])
    upward = close > float(best["high"])
    downward = close < float(best["low"])
    start_position = position - int(best["duration_sessions"])
    prior_start = max(0, start_position - 20)
    prior_close = float(frame.iloc[prior_start]["Close"])
    anchor_close = float(frame.iloc[start_position]["Close"])
    return {
        **best,
        "breakout_up": upward,
        "breakout_down": downward,
        "breakout_distance_atr": (
            (close - float(best["high"])) / atr if upward and atr and atr > 0
            else (float(best["low"]) - close) / atr if downward and atr and atr > 0
            else 0.0 if atr and atr > 0
            else None
        ),
        "prior_move_pct": (anchor_close / prior_close - 1) * 100 if prior_close > 0 else None,
        "future_breakout_used": False,
    }


def gap_risk_features(frame: pd.DataFrame, position: int) -> dict[str, object]:
    start = max(1, position - 60)
    current_open = float(frame.iloc[position]["Open"])
    prior_close = float(frame.iloc[position - 1]["Close"])
    current_atr = _number(frame.iloc[position - 1].get("ATR_14"))
    current_gap = current_open - prior_close
    gaps_pct: list[float] = []
    gaps_atr: list[float] = []
    intraday_pct: list[float] = []
    for index in range(start, position):
        previous_close = float(frame.iloc[index - 1]["Close"])
        opening = float(frame.iloc[index]["Open"])
        closing = float(frame.iloc[index]["Close"])
        prior_atr = _number(frame.iloc[index - 1].get("ATR_14"))
        gaps_pct.append((opening / previous_close - 1) * 100 if previous_close > 0 else 0.0)
        if prior_atr and prior_atr > 0:
            gaps_atr.append((opening - previous_close) / prior_atr)
        intraday_pct.append((closing / opening - 1) * 100 if opening > 0 else 0.0)
    abs_gaps = np.abs(np.asarray(gaps_pct, dtype=float))
    gap_atr_array = np.asarray(gaps_atr, dtype=float)
    intraday = np.asarray(intraday_pct, dtype=float)
    overnight_std = float(np.std(np.asarray(gaps_pct), ddof=1)) if len(gaps_pct) >= 2 else None
    intraday_std = float(np.std(intraday, ddof=1)) if len(intraday) >= 2 else None
    return {
        "current_gap_pct": current_gap / prior_close * 100 if prior_close > 0 else None,
        "current_gap_atr": current_gap / current_atr if current_atr and current_atr > 0 else None,
        "current_gap_absolute": abs(current_gap),
        "lookback_sessions": len(gaps_pct),
        "gap_frequency": {
            f"absolute_gt_{threshold:g}_atr": float(np.mean(np.abs(gap_atr_array) > threshold))
            if len(gap_atr_array)
            else None
            for threshold in (0.5, 1.0, 1.5)
        },
        "average_absolute_overnight_pct": float(np.mean(abs_gaps)) if len(abs_gaps) else None,
        "maximum_absolute_overnight_pct": float(np.max(abs_gaps)) if len(abs_gaps) else None,
        "overnight_volatility_pct": overnight_std,
        "intraday_open_close_volatility_pct": intraday_std,
        "overnight_to_intraday_volatility": overnight_std / intraday_std
        if overnight_std is not None and intraday_std and intraday_std > 0
        else None,
        "large_down_gap_frequency": float(np.mean(gap_atr_array < -0.5)) if len(gap_atr_array) else None,
        "large_up_gap_frequency": float(np.mean(gap_atr_array > 0.5)) if len(gap_atr_array) else None,
        "future_gaps_used": 0,
        "hard_gate": False,
    }


def build_shared_asset_features(
    frame: pd.DataFrame,
    position: int,
    *,
    asset: Mapping[str, object],
    benchmark_histories: Mapping[str, pd.DataFrame],
) -> dict[str, object]:
    return {
        "context_version": BROAD_CONTEXT_VERSION,
        "relative_strength": relative_strength_features(
            frame,
            position,
            asset=asset,
            benchmark_histories=benchmark_histories,
        ),
        "trend_quality": trend_quality_features(frame, position),
        "volatility_structure": volatility_structure_features(frame, position),
        "candle_quality": candle_quality_features(frame, position),
        "historical_extremes": historical_extreme_features(frame, position),
        "consolidation": consolidation_features(frame, position),
        "gap_risk": gap_risk_features(frame, position),
        "direction_neutral": True,
        "future_bars_used": 0,
        "automatic_rule_change": False,
    }


def build_historical_breadth_context(
    prepared_assets: Iterable[tuple[Mapping[str, object], pd.DataFrame]],
) -> dict[str, dict[str, object]]:
    """Aggregate the frozen project universe; it is not a survivorship-free index."""
    accumulators: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for asset, frame in prepared_assets:
        if frame.empty:
            continue
        close = frame["Close"].to_numpy(dtype=float)
        groups = (
            ("overall", "all"),
            ("region", str(asset.get("region") or "Unbekannt")),
            ("asset_type", str(asset.get("asset_type") or "Unbekannt")),
        )
        rolling_high20 = frame["High"].rolling(20, min_periods=20).max().to_numpy(dtype=float)
        rolling_high50 = frame["High"].rolling(50, min_periods=50).max().to_numpy(dtype=float)
        rolling_low20 = frame["Low"].rolling(20, min_periods=20).min().to_numpy(dtype=float)
        rolling_low50 = frame["Low"].rolling(50, min_periods=50).min().to_numpy(dtype=float)
        for position, timestamp in enumerate(pd.DatetimeIndex(frame.index)):
            day = timestamp.date().isoformat()
            metrics = {
                "above_ema20": float(close[position] > frame.iloc[position]["EMA_20"])
                if _number(frame.iloc[position].get("EMA_20")) is not None else math.nan,
                "above_ema50": float(close[position] > frame.iloc[position]["EMA_50"])
                if _number(frame.iloc[position].get("EMA_50")) is not None else math.nan,
                "above_ema200": float(close[position] > frame.iloc[position]["SMA_200"])
                if _number(frame.iloc[position].get("SMA_200")) is not None else math.nan,
                "positive_momentum20": float(close[position] > close[position - 20]) if position >= 20 else math.nan,
                "positive_momentum60": float(close[position] > close[position - 60]) if position >= 60 else math.nan,
                "near_high20": float(close[position] >= 0.98 * rolling_high20[position]) if math.isfinite(rolling_high20[position]) else math.nan,
                "near_high50": float(close[position] >= 0.98 * rolling_high50[position]) if math.isfinite(rolling_high50[position]) else math.nan,
                "near_low20": float(close[position] <= 1.02 * rolling_low20[position]) if math.isfinite(rolling_low20[position]) else math.nan,
                "near_low50": float(close[position] <= 1.02 * rolling_low50[position]) if math.isfinite(rolling_low50[position]) else math.nan,
            }
            for kind, value in groups:
                target = accumulators[(day, kind, value)]
                for name, metric in metrics.items():
                    if math.isfinite(metric):
                        target[name].append(metric)
    rows_by_group: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for (day, kind, value), metrics in accumulators.items():
        payload = {
            "breadth_version": BROAD_BREADTH_VERSION,
            "day": day,
            "group_kind": kind,
            "group_value": value,
            "metrics": {
                name: {
                    "share_pct": float(np.mean(values) * 100),
                    "assets": len(values),
                }
                for name, values in sorted(metrics.items())
            },
            "survivorship_free": False,
            "universe_policy": "frozen_current_project_universe_with_historical_coverage_only",
            "sector_breadth_available": False,
        }
        asset_counts = [int(item["assets"]) for item in payload["metrics"].values()]
        payload["group_minimum_assets"] = min(asset_counts) if asset_counts else 0
        payload["group_adequate"] = bool(kind == "overall" or (asset_counts and min(asset_counts) >= 5))
        rows_by_group[(kind, value)].append(payload)
    output: dict[str, dict[str, object]] = {}
    for group_rows in rows_by_group.values():
        group_rows.sort(key=lambda item: str(item["day"]))
        for index, payload in enumerate(group_rows):
            for metric_name, metric in payload["metrics"].items():
                metric["change_pct_points"] = {
                    f"{horizon}d": (
                        float(metric["share_pct"])
                        - float(group_rows[index - horizon]["metrics"][metric_name]["share_pct"])
                        if index >= horizon
                        and metric_name in group_rows[index - horizon]["metrics"]
                        else None
                    )
                    for horizon in (5, 10, 20)
                }
                changes = metric["change_pct_points"]
                metric["acceleration_5_vs_10"] = (
                    float(changes["5d"]) - float(changes["10d"]) / 2
                    if changes["5d"] is not None and changes["10d"] is not None
                    else None
                )
            output[f"{payload['day']}|{payload['group_kind']}|{payload['group_value']}"] = payload
    return output


def breadth_feature_for_asset(
    context: Mapping[str, Mapping[str, object]],
    *,
    day: str,
    asset: Mapping[str, object],
) -> dict[str, object]:
    def row(kind: str, value: str) -> dict[str, object] | None:
        payload = context.get(f"{day}|{kind}|{value}")
        return dict(payload) if payload is not None and payload.get("group_adequate") else None

    return {
        "breadth_version": BROAD_BREADTH_VERSION,
        "overall": row("overall", "all"),
        "region": row("region", str(asset.get("region") or "Unbekannt")),
        "asset_type": row("asset_type", str(asset.get("asset_type") or "Unbekannt")),
        "regional_or_type_status": "available_only_with_at_least_5_assets_per_metric",
        "sector": None,
        "sector_status": "historical_point_in_time_membership_unavailable",
        "survivorship_free": False,
        "limitation": "Breadth basiert auf dem eingefrorenen heutigen Projektuniversum und seiner jeweiligen historischen Datenabdeckung.",
        "future_universe_information_claimed": False,
    }
