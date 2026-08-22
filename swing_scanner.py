from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from swing_universe import SwingUniverseAsset


RISK_NOTICE = (
    "Trading kann zum vollständigen Verlust des eingesetzten Tradingkapitals führen. "
    "Automatisch berechnete Stops und kleine Positionsgrößen sollen Verluste begrenzen, "
    "können sie aber nicht garantieren. Die App führt keine Orders aus."
)


@dataclass(frozen=True)
class SwingPrefilterThresholds:
    filter_policy_version: str = "swing-filter-neutrality-2026.08.11-v1"
    min_history_rows: int = 200
    min_price_stock_etf: float = 1.0
    min_positive_volume_observations_20: int = 15
    min_annualized_volatility_pct_stock: float = 8.0
    min_annualized_volatility_pct_etf: float = 5.0
    min_annualized_volatility_pct_crypto: float = 20.0
    max_annualized_volatility_pct_stock: float = 120.0
    max_annualized_volatility_pct_etf: float = 80.0
    max_annualized_volatility_pct_crypto: float = 220.0
    pullback_touch_atr_multiple: float = 0.75
    pullback_extension_atr_multiple: float = 1.50
    breakout_extension_atr_multiple: float = 0.75
    min_pullback_touch_pct: float = 0.35
    min_pullback_extension_pct: float = 1.00
    min_breakout_extension_pct: float = 0.50
    max_pullback_touch_pct: float = 2.0
    max_breakout_extension_pct: float = 2.5
    max_pullback_extension_pct: float = 5.0
    # Backward-compatible test/config aliases from the previous shared bands.
    min_annualized_volatility_pct: float | None = None
    max_annualized_volatility_pct_stock_etf: float | None = None


@dataclass(frozen=True)
class ConservativeSwingRiskPolicy:
    version: str = "2026.08.17-v2"
    max_risk_pct_per_trade: float = 0.50
    max_total_open_risk_pct: float = 2.00
    max_total_exposure_pct: float = 50.0
    max_position_exposure_pct: float = 20.0
    position_limit_mode: str = "dynamic_total_risk_and_exposure"
    max_stop_distance_pct_stock: float = 8.0
    max_stop_distance_pct_etf: float = 7.0
    max_stop_distance_pct_crypto: float = 12.0
    gap_risk_notice: str = (
        "Geplanter Verlust gilt nur bei Ausführung nahe dem Stop. Bei Kurslücken kann der tatsächliche Verlust höher sein."
    )


DEFAULT_PREFILTER_THRESHOLDS = SwingPrefilterThresholds()
DEFAULT_SWING_RISK_POLICY = ConservativeSwingRiskPolicy()


def prefilter_thresholds_as_dict(
    thresholds: SwingPrefilterThresholds = DEFAULT_PREFILTER_THRESHOLDS,
) -> dict:
    return asdict(thresholds)


def risk_policy_as_dict(policy: ConservativeSwingRiskPolicy = DEFAULT_SWING_RISK_POLICY) -> dict:
    return asdict(policy)


def internal_swing_settings(
    trading_capital_eur: float | None,
    policy: ConservativeSwingRiskPolicy = DEFAULT_SWING_RISK_POLICY,
) -> dict:
    try:
        capital = float(trading_capital_eur) if trading_capital_eur is not None else None
    except (TypeError, ValueError):
        capital = None
    if capital is not None and (not math.isfinite(capital) or capital <= 0):
        capital = None
    return {
        "trading_capital_eur": capital,
        "max_risk_pct": policy.max_risk_pct_per_trade,
        "max_total_open_risk_pct": policy.max_total_open_risk_pct,
        "max_total_exposure_pct": policy.max_total_exposure_pct,
        "max_position_exposure_pct": policy.max_position_exposure_pct,
        "position_limit_mode": policy.position_limit_mode,
        "allowed_asset_types": ["Aktie", "ETF", "Krypto"],
        "risk_policy_version": policy.version,
    }


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _reject_prefilter(result: dict, filter_code: str, reason: str) -> dict:
    result["reasons"] = [reason]
    result["rejection_filters"] = [filter_code]
    return result


def _annualized_volatility_range(
    asset_type: str,
    thresholds: SwingPrefilterThresholds,
) -> tuple[float, float]:
    legacy_minimum = thresholds.min_annualized_volatility_pct
    legacy_stock_etf_maximum = thresholds.max_annualized_volatility_pct_stock_etf
    if asset_type == "ETF":
        return (
            thresholds.min_annualized_volatility_pct_etf if legacy_minimum is None else legacy_minimum,
            thresholds.max_annualized_volatility_pct_etf
            if legacy_stock_etf_maximum is None
            else legacy_stock_etf_maximum,
        )
    if asset_type == "Krypto":
        return (
            thresholds.min_annualized_volatility_pct_crypto,
            thresholds.max_annualized_volatility_pct_crypto,
        )
    return (
        thresholds.min_annualized_volatility_pct_stock if legacy_minimum is None else legacy_minimum,
        thresholds.max_annualized_volatility_pct_stock
        if legacy_stock_etf_maximum is None
        else legacy_stock_etf_maximum,
    )


def _atr_pct(frame: pd.DataFrame, latest_close: float) -> float | None:
    if latest_close <= 0 or not {"High", "Low"}.issubset(frame.columns):
        return None
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = _finite(true_range.rolling(14).mean().iloc[-1])
    return atr / latest_close * 100 if atr is not None and atr > 0 else None


def _adaptive_prefilter_bands(
    frame: pd.DataFrame,
    latest_close: float,
    thresholds: SwingPrefilterThresholds,
) -> dict[str, float] | None:
    atr_percent = _atr_pct(frame, latest_close)
    if atr_percent is None:
        return None
    return {
        "atr_pct": atr_percent,
        "pullback_touch_pct": min(
            thresholds.max_pullback_touch_pct,
            max(thresholds.min_pullback_touch_pct, atr_percent * thresholds.pullback_touch_atr_multiple),
        ),
        "pullback_extension_pct": min(
            thresholds.max_pullback_extension_pct,
            max(
                thresholds.min_pullback_extension_pct,
                atr_percent * thresholds.pullback_extension_atr_multiple,
            ),
        ),
        "breakout_extension_pct": min(
            thresholds.max_breakout_extension_pct,
            max(
                thresholds.min_breakout_extension_pct,
                atr_percent * thresholds.breakout_extension_atr_multiple,
            ),
        ),
    }


def quick_prefilter(
    asset: SwingUniverseAsset,
    data: pd.DataFrame,
    thresholds: SwingPrefilterThresholds = DEFAULT_PREFILTER_THRESHOLDS,
) -> dict:
    result = {
        "ticker": asset.ticker,
        "name": asset.name,
        "passed": False,
        "score": 0.0,
        "reasons": [],
        "rejection_filters": [],
        "metrics": {},
    }
    if data.empty or "Close" not in data:
        return _reject_prefilter(result, "data_unavailable", "Keine Kursdaten verfügbar.")

    frame = data.copy()
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame.dropna(subset=["Close"])
    if len(frame) < thresholds.min_history_rows:
        return _reject_prefilter(
            result,
            "history_coverage",
            f"Nur {len(frame)} statt mindestens {thresholds.min_history_rows} verwertbare Tageszeilen.",
        )

    close = frame["Close"].astype(float)
    latest_close = _finite(close.iloc[-1])
    if latest_close is None or latest_close <= 0:
        return _reject_prefilter(result, "invalid_price", "Aktueller Kurs ist ungültig.")
    if asset.asset_type in {"Aktie", "ETF"} and latest_close < thresholds.min_price_stock_etf:
        return _reject_prefilter(
            result,
            "minimum_price",
            "Kurs liegt unter dem Mindestpreis für den liquiden Scanner.",
        )

    volume = (
        pd.to_numeric(frame["Volume"], errors="coerce")
        if "Volume" in frame
        else pd.Series(index=frame.index, dtype=float)
    )
    average_volume = _finite(volume.tail(20).mean())
    positive_volume_observations = int((volume.tail(20) > 0).sum())
    if average_volume is None or average_volume <= 0 or (
        positive_volume_observations < thresholds.min_positive_volume_observations_20
    ):
        return _reject_prefilter(
            result,
            "volume_data_coverage",
            "Zu wenige positive Volumenbeobachtungen für die spätere EUR-Liquiditätsprüfung.",
        )

    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
    volatility_pct = _finite(returns.tail(60).std(ddof=0) * np.sqrt(252) * 100)
    minimum_volatility, maximum_volatility = _annualized_volatility_range(asset.asset_type, thresholds)
    if (
        volatility_pct is None
        or volatility_pct < minimum_volatility
        or volatility_pct > maximum_volatility
    ):
        return _reject_prefilter(
            result,
            "asset_type_volatility",
            "Volatilität liegt außerhalb des assettypgerechten Swing-Bereichs.",
        )

    sma_20 = _finite(close.rolling(20).mean().iloc[-1])
    sma_50 = _finite(close.rolling(50).mean().iloc[-1])
    sma_200 = _finite(close.rolling(200).mean().iloc[-1])
    if sma_20 is None or sma_50 is None or sma_200 is None:
        return _reject_prefilter(
            result,
            "trend_data_coverage",
            "Trenddurchschnitte sind nicht vollständig verfügbar.",
        )

    uptrend = sma_50 > sma_200 and latest_close > sma_200
    if not uptrend:
        return _reject_prefilter(
            result,
            "uptrend",
            "Kein intakter Aufwärtstrend im schnellen Vorfilter.",
        )

    adaptive_bands = _adaptive_prefilter_bands(frame, latest_close, thresholds)
    if adaptive_bands is None:
        return _reject_prefilter(
            result,
            "volatility_data_coverage",
            "ATR-basierte Setup-Normalisierung ist nicht belastbar verfügbar.",
        )

    high = pd.to_numeric(frame.get("High", close), errors="coerce")
    low = pd.to_numeric(frame.get("Low", close), errors="coerce")
    prior_high = _finite(high.iloc[-21:-1].max())
    recent_low = _finite(low.tail(7).min())
    pullback = (
        recent_low is not None
        and recent_low <= sma_50 * (1 + adaptive_bands["pullback_touch_pct"] / 100)
        and latest_close >= sma_50
        and latest_close <= sma_50 * (1 + adaptive_bands["pullback_extension_pct"] / 100)
    )
    breakout = (
        prior_high is not None
        and latest_close >= prior_high * 1.001
        and latest_close <= prior_high * (1 + adaptive_bands["breakout_extension_pct"] / 100)
    )
    if not (pullback or breakout):
        return _reject_prefilter(
            result,
            "setup_structure",
            "Weder bestätigte Ausbruchs- noch ATR-normalisierte Rücksetzerstruktur im Vorfilter.",
        )

    current_volume = _finite(volume.iloc[-1])
    relative_volume = current_volume / average_volume if current_volume is not None and average_volume > 0 else 0.0
    distance_50 = abs(latest_close / sma_50 - 1) * 100
    structure_score = 3.0 if breakout else 2.5
    trend_score = min(max((sma_50 / sma_200 - 1) * 100, 0.0), 10.0) / 10 * 2.0
    volume_coverage_score = min(positive_volume_observations / 20, 1.0) * 2.0
    volume_score = min(max(relative_volume, 0.0), 2.0) / 2 * 1.5
    proximity_score = max(0.0, 1.5 - min(distance_50, 6.0) / 4)
    score = round(structure_score + trend_score + volume_coverage_score + volume_score + proximity_score, 3)
    result.update(
        {
            "passed": True,
            "score": score,
            "reasons": [],
            "metrics": {
                "close": latest_close,
                "average_volume_20": average_volume,
                "relative_volume": relative_volume,
                "annualized_volatility_pct": volatility_pct,
                "positive_volume_observations_20": positive_volume_observations,
                "liquidity_hard_gate": "EUR-Turnover erst in der Tiefenanalyse",
                **adaptive_bands,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "structure": "Ausbruch" if breakout else "Rücksetzer",
            },
        }
    )
    return result


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def classify_swing_rejection_reason(reason: object) -> str:
    text = str(reason or "")
    mappings = (
        ("data_quality", ("Datenqualität", "Kursdaten", "Trenddurchschnitte", "ATR-basierte")),
        ("bar_completion", ("Tageskerze",)),
        ("fx", ("Umrechnung",)),
        ("relative_volume", ("Aktuelles Volumen",)),
        ("turnover_liquidity", ("Handelbarkeit", "Liquiditätsminimum")),
        ("buy_signal", ("Kaufsignal",)),
        ("asset_quality", ("Asset-Qualität",)),
        ("confidence", ("Confidence",)),
        ("market", ("Marktumfeld",)),
        ("event", ("Ereignisrisiko",)),
        ("setup_structure", ("Rücksetzer:", "Ausbruch:", "Kein Setup")),
        ("crv", ("CRV",)),
        ("stop_distance", ("Stop-Abstand",)),
        ("expected_value", ("Erwartungswert",)),
        ("portfolio_risk", ("Höchstzahl", "Positionsgröße", "Gesamtbelastung", "Gesamtbudget", "Risikobudget")),
    )
    return next(
        (filter_code for filter_code, needles in mappings if any(needle in text for needle in needles)),
        "other",
    )


def _metric_summary(values: Sequence[object]) -> dict:
    finite_values = sorted(value for raw in values if (value := _finite(raw)) is not None)
    if not finite_values:
        return {"count": 0, "median": None, "p25": None, "p75": None}
    series = pd.Series(finite_values, dtype=float)
    return {
        "count": len(finite_values),
        "median": round(float(series.median()), 4),
        "p25": round(float(series.quantile(0.25)), 4),
        "p75": round(float(series.quantile(0.75)), 4),
    }


def _asset_type_funnel(
    active_assets: Sequence[SwingUniverseAsset],
    loaded_tickers: set[str],
    prefilter_passed: Sequence[tuple[SwingUniverseAsset, dict]],
    deeply_evaluated: Sequence[SwingUniverseAsset],
    deeply_approved: Sequence[SwingUniverseAsset],
    rejection_reasons_by_type: Mapping[str, Mapping[str, int]],
    prefilter_filters_by_type: Mapping[str, Mapping[str, int]],
    final_filters_by_type: Mapping[str, Mapping[str, int]],
    final_rejected_by_type: Mapping[str, int],
    evaluated_metrics_by_type: Mapping[str, Mapping[str, Sequence[object]]],
) -> dict[str, dict]:
    asset_types = sorted({"Aktie", "ETF", "Krypto", *(asset.asset_type for asset in active_assets)})
    passed_tickers = {asset.ticker for asset, _ in prefilter_passed}
    evaluated_tickers = {asset.ticker for asset in deeply_evaluated}
    approved_tickers = {asset.ticker for asset in deeply_approved}
    funnel: dict[str, dict] = {}
    for asset_type in asset_types:
        tickers = {asset.ticker for asset in active_assets if asset.asset_type == asset_type}
        universe = len(tickers)
        loaded = len(tickers & loaded_tickers)
        passed = len(tickers & passed_tickers)
        evaluated = len(tickers & evaluated_tickers)
        approved = len(tickers & approved_tickers)
        funnel[asset_type] = {
            "universe_assets": universe,
            "loaded_assets": loaded,
            "prefilter_passed": passed,
            "fully_evaluated": evaluated,
            "setup_approved": approved,
            "final_rejected_assets": int(final_rejected_by_type.get(asset_type) or 0),
            "portfolio_released": approved,
            "load_rate_pct": _percentage(loaded, universe),
            "prefilter_pass_rate_pct": _percentage(passed, loaded),
            "deep_coverage_pct": _percentage(evaluated, passed),
            "setup_approval_rate_pct": _percentage(approved, evaluated),
            "portfolio_release_rate_pct": _percentage(approved, evaluated),
            "prefilter_rejection_reasons": dict(
                sorted(
                    (rejection_reasons_by_type.get(asset_type) or {}).items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "prefilter_rejection_filters": dict(
                sorted(
                    (prefilter_filters_by_type.get(asset_type) or {}).items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "final_rejection_filters": dict(
                sorted(
                    (final_filters_by_type.get(asset_type) or {}).items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "evaluated_metric_summary": {
                metric: _metric_summary(values)
                for metric, values in (evaluated_metrics_by_type.get(asset_type) or {}).items()
            },
        }
    return funnel


def asset_type_bias_audit(funnel: Mapping[str, Mapping[str, object]]) -> dict:
    stock = dict(funnel.get("Aktie") or {})
    etf = dict(funnel.get("ETF") or {})
    minimum_loaded = 20
    comparison_ready = (
        int(stock.get("loaded_assets") or 0) >= minimum_loaded
        and int(etf.get("loaded_assets") or 0) >= minimum_loaded
    )
    stock_rate = _finite(stock.get("prefilter_pass_rate_pct"))
    etf_rate = _finite(etf.get("prefilter_pass_rate_pct"))
    ratio = (
        round(etf_rate / stock_rate, 3)
        if comparison_ready and stock_rate is not None and stock_rate > 0 and etf_rate is not None
        else None
    )
    stock_reasons = dict(stock.get("prefilter_rejection_reasons") or {})
    etf_reasons = dict(etf.get("prefilter_rejection_reasons") or {})
    stock_filters = dict(stock.get("prefilter_rejection_filters") or {})
    etf_filters = dict(etf.get("prefilter_rejection_filters") or {})
    filter_contributions: list[dict] = []
    stock_loaded = int(stock.get("loaded_assets") or 0)
    etf_loaded = int(etf.get("loaded_assets") or 0)
    if comparison_ready:
        for filter_code in sorted(set(stock_filters) | set(etf_filters)):
            if filter_code == "data_unavailable":
                continue
            stock_filter_rate = int(stock_filters.get(filter_code) or 0) / stock_loaded * 100
            etf_filter_rate = int(etf_filters.get(filter_code) or 0) / etf_loaded * 100
            filter_contributions.append(
                {
                    "filter": filter_code,
                    "stock_rejected": int(stock_filters.get(filter_code) or 0),
                    "etf_rejected": int(etf_filters.get(filter_code) or 0),
                    "stock_rejection_rate_pct": round(stock_filter_rate, 3),
                    "etf_rejection_rate_pct": round(etf_filter_rate, 3),
                    "contribution_to_higher_etf_pass_rate_pp": round(
                        stock_filter_rate - etf_filter_rate,
                        3,
                    ),
                }
            )
        filter_contributions.sort(
            key=lambda item: abs(item["contribution_to_higher_etf_pass_rate_pp"]),
            reverse=True,
        )
    pass_rate_gap = (
        round(etf_rate - stock_rate, 3)
        if comparison_ready and stock_rate is not None and etf_rate is not None
        else None
    )
    explained_gap = (
        round(sum(item["contribution_to_higher_etf_pass_rate_pp"] for item in filter_contributions), 3)
        if filter_contributions
        else None
    )
    observation = "Noch keine belastbare ETF-/Aktien-Aussage in diesem Scan."
    status = "insufficient_sample"
    if comparison_ready and ratio is not None:
        status = "measured"
        if ratio >= 1.5:
            observation = "ETFs passieren den Grobfilter in diesem Scan deutlich häufiger als Aktien."
        elif ratio <= (1 / 1.5):
            observation = "Aktien passieren den Grobfilter in diesem Scan deutlich häufiger als ETFs."
        else:
            observation = "Kein deutlicher ETF-/Aktien-Unterschied im Grobfilter dieses Scans."
    return {
        "status": status,
        "minimum_loaded_per_class": minimum_loaded,
        "stock_loaded": stock_loaded,
        "etf_loaded": etf_loaded,
        "stock_prefilter_pass_rate_pct": stock_rate,
        "etf_prefilter_pass_rate_pct": etf_rate,
        "etf_to_stock_prefilter_rate_ratio": ratio,
        "etf_minus_stock_prefilter_pass_rate_pp": pass_rate_gap,
        "filter_contributions": filter_contributions,
        "arithmetically_explained_gap_pp": explained_gap,
        "unexplained_gap_pp": (
            round(pass_rate_gap - explained_gap, 3)
            if pass_rate_gap is not None and explained_gap is not None
            else None
        ),
        "stock_final_approval_rate_pct": _finite(stock.get("setup_approval_rate_pct")),
        "etf_final_approval_rate_pct": _finite(etf.get("setup_approval_rate_pct")),
        "stock_final_rejection_filters": dict(stock.get("final_rejection_filters") or {}),
        "etf_final_rejection_filters": dict(etf.get("final_rejection_filters") or {}),
        "stock_dominant_rejection_reason": next(iter(stock_reasons), None),
        "etf_dominant_rejection_reason": next(iter(etf_reasons), None),
        "observation": observation,
        "causal_claim": False,
        "automatic_weight_change": False,
        "quota_or_asset_class_target": False,
    }


def apply_portfolio_release_to_funnel(
    funnel: Mapping[str, Mapping[str, object]],
    released: Sequence[Mapping[str, object]],
) -> dict[str, dict]:
    released_by_type: dict[str, int] = {}
    for item in released:
        asset_type = str(item.get("asset_type") or item.get("Asset-Typ") or "Unbekannt")
        released_by_type[asset_type] = released_by_type.get(asset_type, 0) + 1
    updated = {asset_type: dict(values) for asset_type, values in funnel.items()}
    for asset_type, values in updated.items():
        released_count = released_by_type.get(asset_type, 0)
        values["portfolio_released"] = released_count
        values["portfolio_release_rate_pct"] = _percentage(
            released_count,
            int(values.get("fully_evaluated") or 0),
        )
    return updated


def swing_portfolio_cluster_audit(
    candidates: Sequence[Mapping[str, object]],
    histories: Mapping[str, pd.DataFrame],
    *,
    correlation_threshold: float = 0.75,
    lookback_sessions: int = 60,
    maximum_correlation_candidates: int = 50,
) -> dict:
    """Describe concentration without silently rejecting or reweighting a qualified setup."""
    normalized: list[dict] = []
    sector_counts: dict[str, int] = {}
    region_counts: dict[str, int] = {}
    for candidate in candidates:
        symbol = str(candidate.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        metadata = dict(candidate.get("universe_metadata") or {})
        sector = str(metadata.get("sector") or "Unbekannt")
        region = str(metadata.get("region") or "Unbekannt")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        region_counts[region] = region_counts.get(region, 0) + 1
        normalized.append({"symbol": symbol, "sector": sector, "region": region})

    high_correlation_pairs: list[dict] = []
    minimum_observations = min(max(int(lookback_sessions) // 3, 10), 20)
    correlation_candidates = normalized[: max(int(maximum_correlation_candidates), 2)]
    returns_by_symbol: dict[str, pd.Series] = {}
    for candidate in correlation_candidates:
        frame = histories.get(candidate["symbol"])
        if not isinstance(frame, pd.DataFrame) or "Close" not in frame:
            continue
        returns_by_symbol[candidate["symbol"]] = pd.to_numeric(
            frame["Close"], errors="coerce"
        ).pct_change().tail(max(int(lookback_sessions), 20))
    if returns_by_symbol:
        returns_frame = pd.concat(returns_by_symbol, axis=1)
        correlations = returns_frame.corr(min_periods=minimum_observations)
        observations = returns_frame.notna().astype(int).T.dot(returns_frame.notna().astype(int))
    else:
        correlations = pd.DataFrame()
        observations = pd.DataFrame()
    symbols = list(returns_by_symbol)
    for left_index, left_symbol in enumerate(symbols):
        for right_symbol in symbols[left_index + 1 :]:
            correlation = _finite(correlations.loc[left_symbol, right_symbol])
            if correlation is not None and correlation >= float(correlation_threshold):
                high_correlation_pairs.append(
                    {
                        "left": left_symbol,
                        "right": right_symbol,
                        "correlation": round(correlation, 4),
                        "observations": int(observations.loc[left_symbol, right_symbol]),
                    }
                )

    concentrated_sectors = {
        key: value for key, value in sector_counts.items() if key != "Unbekannt" and value >= 2
    }
    return {
        "version": "swing-portfolio-cluster-audit-2026.08.16-v1",
        "qualified_candidates": len(normalized),
        "correlation_candidates_analyzed": len(returns_by_symbol),
        "correlation_candidates_limited": len(normalized) > len(correlation_candidates),
        "lookback_sessions": max(int(lookback_sessions), 20),
        "correlation_threshold": float(correlation_threshold),
        "high_correlation_pairs": high_correlation_pairs,
        "sector_counts": sector_counts,
        "region_counts": region_counts,
        "concentrated_sectors": concentrated_sectors,
        "status": "attention" if high_correlation_pairs or concentrated_sectors else "ok",
        "automatic_rejection": False,
        "automatic_weight_change": False,
    }


def deterministic_rejection_control_sample(
    rejected: Sequence[Mapping[str, object]],
    *,
    maximum_controls: int = 5,
) -> list[dict]:
    candidates = []
    for item in rejected:
        snapshot = dict(item.get("Kontrollsnapshot") or {})
        symbol = str(snapshot.get("ticker") or "").strip().upper()
        signal_day = str(snapshot.get("signal_day") or "")
        reference_price = _finite(snapshot.get("reference_price_original"))
        if not symbol or not signal_day or reference_price is None or reference_price <= 0:
            continue
        identity = (
            f"{symbol}|{signal_day}|{','.join(str(value) for value in snapshot.get('rejection_filters') or [])}|"
            "swing-rejection-control-sampling-2026.08.16-v1"
        )
        candidates.append(
            {
                **snapshot,
                "sampling_version": "swing-rejection-control-sampling-2026.08.16-v1",
                "sampling_key": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "control_only": True,
                "not_a_trade_signal": True,
            }
        )
    candidates.sort(key=lambda item: str(item["sampling_key"]))
    return candidates[: max(int(maximum_controls), 0)]


def execute_multistage_scan(
    assets: Sequence[SwingUniverseAsset],
    histories: Mapping[str, pd.DataFrame],
    deep_evaluator: Callable[[SwingUniverseAsset, pd.DataFrame], dict],
    *,
    download_errors: Sequence[str] | None = None,
    thresholds: SwingPrefilterThresholds = DEFAULT_PREFILTER_THRESHOLDS,
) -> dict:
    active_assets = [asset for asset in assets if asset.active]
    prefilter_passed: list[tuple[SwingUniverseAsset, dict]] = []
    prefilter_rejected: list[dict] = []
    rejection_reasons_by_type: dict[str, dict[str, int]] = {}
    prefilter_filters_by_type: dict[str, dict[str, int]] = {}
    final_filters_by_type: dict[str, dict[str, int]] = {}
    final_rejected_by_type: dict[str, int] = {}
    evaluated_metrics_by_type: dict[str, dict[str, list[object]]] = {}
    loaded_assets = 0
    loaded_tickers: set[str] = set()
    missing_tickers: set[str] = set()

    for asset in active_assets:
        asset_reasons = rejection_reasons_by_type.setdefault(asset.asset_type, {})
        asset_filters = prefilter_filters_by_type.setdefault(asset.asset_type, {})
        frame = histories.get(asset.ticker)
        if not isinstance(frame, pd.DataFrame) or frame.empty or "Close" not in frame:
            missing_tickers.add(asset.ticker)
            no_data_reason = "Keine Kursdaten verfügbar."
            asset_reasons[no_data_reason] = asset_reasons.get(no_data_reason, 0) + 1
            asset_filters["data_unavailable"] = asset_filters.get("data_unavailable", 0) + 1
            prefilter_rejected.append(
                {
                    "Ticker": asset.ticker,
                    "Asset": asset.name,
                    "Asset-Typ": asset.asset_type,
                    "Ablehnungsgründe": [no_data_reason],
                    "Ablehnungsfilter": ["data_unavailable"],
                }
            )
            continue
        loaded_assets += 1
        loaded_tickers.add(asset.ticker)
        assessment = quick_prefilter(asset, frame, thresholds)
        if assessment["passed"]:
            prefilter_passed.append((asset, assessment))
        else:
            for reason in assessment["reasons"]:
                text_reason = str(reason)
                asset_reasons[text_reason] = asset_reasons.get(text_reason, 0) + 1
            rejection_filters = list(assessment.get("rejection_filters") or [])
            for filter_code in set(str(value) for value in rejection_filters):
                asset_filters[filter_code] = asset_filters.get(filter_code, 0) + 1
            prefilter_rejected.append(
                {
                    "Ticker": asset.ticker,
                    "Asset": asset.name,
                    "Asset-Typ": asset.asset_type,
                    "Ablehnungsgründe": list(assessment["reasons"]),
                    "Ablehnungsfilter": rejection_filters,
                    "Vorfilter": assessment.get("metrics", {}),
                }
            )

    prefilter_passed.sort(key=lambda item: item[1]["score"], reverse=True)
    selected = prefilter_passed
    approved: list[dict] = []
    deeply_evaluated: list[SwingUniverseAsset] = []
    deeply_approved: list[SwingUniverseAsset] = []
    deep_rejected: list[dict] = []
    deep_errors: list[str] = []
    for asset, prefilter in selected:
        deeply_evaluated.append(asset)
        try:
            assessment = deep_evaluator(asset, histories[asset.ticker])
            assessment["prefilter_score"] = prefilter["score"]
            assessment.setdefault("asset_type", asset.asset_type)
            metric_values = evaluated_metrics_by_type.setdefault(asset.asset_type, {})
            for metric in (
                "buy_signal",
                "asset_quality",
                "confidence",
                "data_quality",
                "relative_volume",
                "average_turnover_eur",
            ):
                metric_values.setdefault(metric, []).append(assessment.get(metric))
            if assessment.get("approved"):
                approved.append(assessment)
                deeply_approved.append(asset)
            else:
                final_rejected_by_type[asset.asset_type] = (
                    final_rejected_by_type.get(asset.asset_type, 0) + 1
                )
                final_reasons = list(assessment.get("rejection_reasons") or ["Kein freigegebenes Setup."])
                rejection_filters = list(assessment.get("rejection_filters") or [])
                if not rejection_filters:
                    rejection_filters = [classify_swing_rejection_reason(reason) for reason in final_reasons]
                asset_final_filters = final_filters_by_type.setdefault(asset.asset_type, {})
                for filter_code in set(str(value) for value in rejection_filters):
                    asset_final_filters[filter_code] = asset_final_filters.get(filter_code, 0) + 1
                deep_rejected.append(
                    {
                        "Ticker": asset.ticker,
                        "Asset": asset.name,
                        "Asset-Typ": asset.asset_type,
                        "Datenqualität": assessment.get("data_quality"),
                        "Relatives Volumen": assessment.get("relative_volume"),
                        "Ablehnungsgründe": final_reasons,
                        "Ablehnungsfilter": rejection_filters,
                        "Kontrollsnapshot": {
                            "ticker": asset.ticker,
                            "asset_name": asset.name,
                            "asset_type": asset.asset_type,
                            "region": asset.region,
                            "signal_day": pd.Timestamp(histories[asset.ticker].index[-1]).date().isoformat(),
                            "observed_at": assessment.get("evaluated_at"),
                            "reference_price_original": float(
                                pd.to_numeric(histories[asset.ticker]["Close"], errors="coerce").dropna().iloc[-1]
                            ),
                            "market_phase": assessment.get("market_phase"),
                            "volatility_regime": assessment.get("volatility_regime"),
                            "rejection_reasons": final_reasons,
                            "rejection_filters": rejection_filters,
                            "buy_signal": assessment.get("buy_signal"),
                            "confidence": assessment.get("confidence"),
                            "data_quality": assessment.get("data_quality"),
                            "relative_volume": assessment.get("relative_volume"),
                            "average_turnover_eur": assessment.get("average_turnover_eur"),
                            "source_kind": "real_forward_scan_rejection_control",
                        },
                    }
                )
        except Exception as exc:
            deep_errors.append(f"{asset.ticker}: {exc}")

    approved.sort(
        key=lambda item: (
            item.get("expected_value_r") if item.get("expected_value_r") is not None else -999,
            item.get("quality_score", 0),
            item.get("crv", 0),
        ),
        reverse=True,
    )
    all_errors = [*(download_errors or []), *deep_errors]
    failure_count = len(missing_tickers)
    asset_type_funnel = _asset_type_funnel(
        active_assets,
        loaded_tickers,
        prefilter_passed,
        deeply_evaluated,
        deeply_approved,
        rejection_reasons_by_type,
        prefilter_filters_by_type,
        final_filters_by_type,
        final_rejected_by_type,
        evaluated_metrics_by_type,
    )
    return {
        "approved": approved,
        "rejected": deep_rejected,
        "prefilter_rejected": prefilter_rejected,
        "rejection_controls": deterministic_rejection_control_sample(deep_rejected),
        "errors": all_errors,
        "statistics": {
            "universe_size": len(active_assets),
            "loaded_assets": loaded_assets,
            "prefilter_passed_total": len(prefilter_passed),
            "prefilter_candidates": len(selected),
            "fully_evaluated": len(selected),
            "approved_trades": len(approved),
            "failed_downloads": failure_count,
        },
        "deep_analysis_policy": "all_prefilter_passed",
        "asset_type_funnel": asset_type_funnel,
        "asset_type_bias_audit": asset_type_bias_audit(asset_type_funnel),
        "prefilter_thresholds": prefilter_thresholds_as_dict(thresholds),
    }


def load_risk_acknowledgement(path: Path) -> bool:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return bool(isinstance(data, dict) and data.get("acknowledged") is True)


def save_risk_acknowledgement(path: Path, acknowledged_at: str) -> bool:
    path = Path(path)
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(
                {
                    "schema_version": 1,
                    "acknowledged": True,
                    "acknowledged_at": str(acknowledged_at),
                    "notice_version": "2026.08.02-v1",
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        return True
    except (OSError, TypeError, ValueError):
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False
