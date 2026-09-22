from __future__ import annotations

"""Outcome-free, segment-safe crypto features on frozen daily OHLCV."""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_CONTRACT = Path(__file__).resolve().parent / "config" / "crypto_r4h_features.json"


def load_contract(path: Path = DEFAULT_CONTRACT) -> tuple[dict[str, Any], str]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        contract["program_block"] != "R4-H"
        or contract["btc_benchmark"] != "BTC-USD"
        or contract["relative_return_lookbacks_days"] != [20, 60]
        or contract["benchmark_alignment"] != "exactly previous UTC calendar day; never same-date close"
        or not contract["segment_boundaries_respected"]
        or contract["quote_volume_or_liquidity_claim"]
        or contract["dominance_available"]
        or contract["onchain_available"]
        or contract["strategy_filter_created"]
    ):
        raise ValueError("R4-H frozen observational scope changed")
    digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return contract, digest


def _validated_bars(frame: pd.DataFrame) -> pd.DataFrame:
    required = ("Open", "High", "Low", "Close", "Volume", "SegmentId")
    if (
        not isinstance(frame.index, pd.DatetimeIndex)
        or frame.index.has_duplicates
        or frame.index.tz is not None
        or not frame.index.equals(frame.index.normalize())
        or any(column not in frame for column in required)
    ):
        raise ValueError("R4-H requires unique timezone-naive daily OHLCV and SegmentId")
    bars = frame.sort_index(kind="stable").copy(deep=True)
    for column in required[:5]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce").astype(float)
    if not np.isfinite(bars[list(required[:5])].to_numpy()).all():
        raise ValueError("R4-H source values must be finite")
    if (bars[list(required[:4])] <= 0).any().any() or (bars["Volume"] < 0).any():
        raise ValueError("R4-H OHLC must be positive and reported volume nonnegative")
    if (
        (bars["Low"] > bars["Open"])
        | (bars["Open"] > bars["High"])
        | (bars["Low"] > bars["Close"])
        | (bars["Close"] > bars["High"])
    ).any():
        raise ValueError("R4-H OHLC envelope violation")
    segments = pd.to_numeric(bars["SegmentId"], errors="coerce")
    if segments.isna().any() or (segments < 0).any() or (segments % 1 != 0).any():
        raise ValueError("R4-H invalid source segment identifiers")
    bars["SegmentId"] = segments.astype(int)
    if not bars["SegmentId"].is_monotonic_increasing:
        raise ValueError("R4-H segment identifiers must be monotonic")
    prior_date = pd.Series(bars.index, index=bars.index).shift(1)
    same_segment = bars["SegmentId"].eq(bars["SegmentId"].shift(1))
    if ((bars.index.to_series() - prior_date).dt.days.ne(1) & same_segment).any():
        raise ValueError("R4-H missing UTC day inside a continuity segment")
    return bars


def _rolling(series: pd.Series, segment: pd.Series, window: int, operation: str) -> pd.Series:
    return series.groupby(segment, sort=False).transform(
        lambda part: getattr(part.rolling(window, min_periods=window), operation)()
    )


def _lagged_return(bars: pd.DataFrame, lookback: int) -> pd.Series:
    grouped = bars.groupby("SegmentId", sort=False)["Close"]
    return grouped.shift(1).div(grouped.shift(lookback + 1)).sub(1)


def build_crypto_r4h_features(
    asset_bars: pd.DataFrame,
    btc_bars: pd.DataFrame,
    *,
    contract_path: Path = DEFAULT_CONTRACT,
) -> pd.DataFrame:
    """Compute signal-close features; both relative-return legs end on t-1."""

    contract, contract_fingerprint = load_contract(contract_path)
    asset = _validated_bars(asset_bars)
    btc = _validated_bars(btc_bars)
    result = pd.DataFrame(index=asset.index)
    result["r4h_contract_fingerprint"] = contract_fingerprint
    result["source_dataset_fingerprint"] = contract["source_dataset_fingerprint"]
    result["btc_benchmark"] = "BTC-USD"

    btc_features = pd.DataFrame(index=btc.index)
    for window in contract["relative_return_lookbacks_days"]:
        btc_features[f"btc_return_{window}"] = btc["Close"].div(
            btc.groupby("SegmentId", sort=False)["Close"].shift(window)
        ).sub(1)
    btc_log_return = np.log(btc["Close"].div(btc.groupby("SegmentId")["Close"].shift(1)))
    btc_features["btc_volatility_20"] = _rolling(
        btc_log_return, btc["SegmentId"], contract["volatility_lookback_days"], "std"
    )
    prior_btc_dates = asset.index - pd.Timedelta(days=1)
    aligned_btc = btc_features.reindex(prior_btc_dates)
    aligned_btc.index = asset.index
    known_btc = pd.Series(prior_btc_dates.strftime("%Y-%m-%d"), index=asset.index).where(
        aligned_btc["btc_return_20"].notna()
    )
    result["btc_known_date"] = known_btc
    for window in contract["relative_return_lookbacks_days"]:
        asset_lagged = _lagged_return(asset, window)
        btc_lagged = aligned_btc[f"btc_return_{window}"]
        result[f"asset_lagged_return_{window}"] = asset_lagged
        result[f"btc_lagged_return_{window}"] = btc_lagged
        result[f"relative_to_btc_{window}"] = asset_lagged.sub(btc_lagged)
    result["btc_lagged_volatility_20"] = aligned_btc["btc_volatility_20"]

    prior_asset_close = asset.groupby("SegmentId")["Close"].shift(1)
    asset_log_return = np.log(asset["Close"].div(prior_asset_close))
    result["asset_volatility_20"] = _rolling(
        asset_log_return, asset["SegmentId"], contract["volatility_lookback_days"], "std"
    )
    prior_volume_median = _rolling(
        asset.groupby("SegmentId")["Volume"].shift(1),
        asset["SegmentId"],
        contract["relative_volume_lookback_days"],
        "median",
    )
    result["reported_volume_ratio_20"] = asset["Volume"].where(asset["Volume"] > 0).div(
        prior_volume_median.where(prior_volume_median > 0)
    )
    result["reported_volume_units_status"] = "UNKNOWN_PROVIDER_UNITS_RELATIVE_ONLY"
    prior_high = _rolling(
        asset.groupby("SegmentId")["High"].shift(1),
        asset["SegmentId"],
        contract["structure_lookback_days"],
        "max",
    )
    result["close_vs_prior20_high_pct"] = asset["Close"].div(prior_high).sub(1)
    daily_distance = asset["Close"].sub(prior_asset_close).abs()
    total_path = _rolling(daily_distance, asset["SegmentId"], 20, "sum")
    start_close = asset.groupby("SegmentId")["Close"].shift(20)
    result["trend_efficiency_20"] = asset["Close"].sub(start_close).abs().div(total_path.where(total_path > 0))
    result["onchain_status"] = "UNAVAILABLE_NO_PIT_SOURCE"
    result["dominance_status"] = "UNAVAILABLE_NO_PIT_SOURCE"
    result["strategy_filter_created"] = False
    return result
