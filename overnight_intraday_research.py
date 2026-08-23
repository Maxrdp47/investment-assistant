from __future__ import annotations

"""Causal, research-only decomposition of daily equity/ETF returns.

The module deliberately has no strategy, broker, signal-ranking, or production
activation hook.  Causal features and future research labels are separate
functions so a forward label cannot accidentally become a live input.
"""

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from swing_research_market_scope import (
    build_scoped_research_feature,
    build_scoped_research_hypothesis,
)


OVERNIGHT_INTRADAY_RESEARCH_VERSION = "overnight-intraday-research-2026.08.23-v1"
DEFAULT_ROLLING_WINDOW = 20
DEFAULT_FORWARD_HORIZONS = (1, 5, 20)
OPTIONAL_SEGMENT_COLUMNS = (
    "market_regime",
    "momentum_bucket",
    "liquidity_bucket",
    "company_size_bucket",
    "sector",
    "earnings_event_near",
)


class OvernightIntradayResearchError(ValueError):
    """Raised when a research input would make the decomposition ambiguous."""


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _column(frame: pd.DataFrame, name: str) -> object:
    matches = [column for column in frame.columns if str(column).strip().lower() == name.lower()]
    if len(matches) != 1:
        raise OvernightIntradayResearchError(
            f"OHLC-Spalte {name!r} fehlt oder ist nicht eindeutig."
        )
    return matches[0]


def _positive_numeric(series: pd.Series, *, name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    if bool((numeric.dropna() <= 0).any()):
        raise OvernightIntradayResearchError(
            f"{name} muss für alle vorhandenen Beobachtungen positiv sein."
        )
    return numeric


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    valid = denominator.notna() & (denominator.abs() > 1e-12)
    return numerator.div(denominator).where(valid)


def _single_asset_features(
    history: pd.DataFrame,
    *,
    rolling_window: int,
    min_periods: int,
) -> pd.DataFrame:
    if history.index.has_duplicates:
        raise OvernightIntradayResearchError(
            "Zeitindex enthält doppelte Beobachtungen innerhalb eines Assets."
        )
    result = history.sort_index(kind="stable").copy(deep=True)
    if result.empty:
        for column in _feature_columns():
            result[column] = pd.Series(index=result.index, dtype=float)
        return result

    open_price = _positive_numeric(result[_column(result, "Open")], name="Open")
    close = _positive_numeric(result[_column(result, "Close")], name="Close")
    previous_close = close.shift(1)

    overnight = open_price.div(previous_close).sub(1.0)
    intraday = close.div(open_price).sub(1.0)
    close_to_close = close.div(previous_close).sub(1.0)

    result["overnight_return"] = overnight
    result["intraday_return"] = intraday
    result["close_to_close_return"] = close_to_close
    result["overnight_return_share"] = _safe_ratio(overnight, close_to_close)

    overnight_mean = overnight.rolling(rolling_window, min_periods=min_periods).mean()
    intraday_mean = intraday.rolling(rolling_window, min_periods=min_periods).mean()
    result["rolling_overnight_mean"] = overnight_mean
    result["rolling_intraday_mean"] = intraday_mean
    result["rolling_overnight_bias"] = overnight_mean.sub(intraday_mean)

    overnight_log = np.log1p(overnight)
    intraday_log = np.log1p(intraday)
    overnight_log_sum = overnight_log.rolling(
        rolling_window, min_periods=min_periods
    ).sum()
    intraday_log_sum = intraday_log.rolling(
        rolling_window, min_periods=min_periods
    ).sum()
    total_log_sum = overnight_log_sum.add(intraday_log_sum)
    result["rolling_overnight_total_return_share"] = _safe_ratio(
        overnight_log_sum, total_log_sum
    )
    result["rolling_overnight_absolute_move_share"] = _safe_ratio(
        overnight_log_sum.abs(), overnight_log_sum.abs().add(intraday_log_sum.abs())
    )

    overnight_volatility = overnight.rolling(
        rolling_window, min_periods=min_periods
    ).std(ddof=1)
    intraday_volatility = intraday.rolling(
        rolling_window, min_periods=min_periods
    ).std(ddof=1)
    result["rolling_overnight_volatility"] = overnight_volatility
    result["rolling_intraday_volatility"] = intraday_volatility
    result["rolling_overnight_intraday_volatility_ratio"] = _safe_ratio(
        overnight_volatility, intraday_volatility
    )
    return result


def _feature_columns() -> tuple[str, ...]:
    return (
        "overnight_return",
        "intraday_return",
        "close_to_close_return",
        "overnight_return_share",
        "rolling_overnight_mean",
        "rolling_intraday_mean",
        "rolling_overnight_bias",
        "rolling_overnight_total_return_share",
        "rolling_overnight_absolute_move_share",
        "rolling_overnight_volatility",
        "rolling_intraday_volatility",
        "rolling_overnight_intraday_volatility_ratio",
    )


def build_overnight_intraday_features(
    history: pd.DataFrame,
    *,
    rolling_window: int = DEFAULT_ROLLING_WINDOW,
    min_periods: int | None = None,
    asset_column: str = "asset",
) -> pd.DataFrame:
    """Return causal features known after each completed daily bar.

    If ``asset_column`` is present, shifts and rolling windows are isolated per
    asset.  Otherwise the input is treated as one asset.  The input is never
    mutated.  OHLC must be on one coherent split-adjustment basis.
    """

    if not isinstance(history, pd.DataFrame):
        raise OvernightIntradayResearchError("history muss ein pandas DataFrame sein.")
    if isinstance(rolling_window, bool) or int(rolling_window) < 2:
        raise OvernightIntradayResearchError("rolling_window muss mindestens 2 sein.")
    window = int(rolling_window)
    minimum = window if min_periods is None else int(min_periods)
    if minimum < 2 or minimum > window:
        raise OvernightIntradayResearchError(
            "min_periods muss zwischen 2 und rolling_window liegen."
        )

    if asset_column not in history.columns:
        return _single_asset_features(
            history, rolling_window=window, min_periods=minimum
        )

    pieces: list[pd.DataFrame] = []
    for _, group in history.groupby(asset_column, sort=False, dropna=False):
        pieces.append(
            _single_asset_features(
                group,
                rolling_window=window,
                min_periods=minimum,
            )
        )
    if not pieces:
        empty = history.copy(deep=True)
        for column in _feature_columns():
            empty[column] = pd.Series(index=empty.index, dtype=float)
        return empty
    return pd.concat(pieces, axis=0)


def _single_asset_labels(
    frame: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    setup_mask_column: str | None,
) -> pd.DataFrame:
    result = frame.sort_index(kind="stable").copy(deep=True)
    close = _positive_numeric(result[_column(result, "Close")], name="Close")
    high = _positive_numeric(result[_column(result, "High")], name="High")
    low = _positive_numeric(result[_column(result, "Low")], name="Low")
    setup_mask = (
        result[setup_mask_column].fillna(False).astype(bool)
        if setup_mask_column is not None
        else pd.Series(True, index=result.index)
    )
    for horizon in horizons:
        future_highs = pd.concat(
            [high.shift(-step) for step in range(1, horizon + 1)], axis=1
        )
        future_lows = pd.concat(
            [low.shift(-step) for step in range(1, horizon + 1)], axis=1
        )
        label_available = future_highs.notna().all(axis=1) & future_lows.notna().all(axis=1)
        forward_return = close.shift(-horizon).div(close).sub(1.0)
        # Excursions include the zero move at the signal close: MFE cannot be
        # negative and MAE cannot be positive even if every later bar gaps away.
        mfe = future_highs.max(axis=1).div(close).sub(1.0).clip(lower=0.0)
        mae = future_lows.min(axis=1).div(close).sub(1.0).clip(upper=0.0)
        allowed = setup_mask & label_available
        result[f"forward_return_{horizon}s"] = forward_return.where(allowed)
        result[f"forward_mfe_{horizon}s"] = mfe.where(allowed)
        result[f"forward_mae_{horizon}s"] = mae.where(allowed)
    return result


def add_overnight_intraday_research_labels(
    feature_frame: pd.DataFrame,
    *,
    horizons: Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    asset_column: str = "asset",
    setup_mask_column: str | None = None,
) -> pd.DataFrame:
    """Add future-only labels for offline research, never for live inference."""

    clean_horizons = tuple(sorted({int(value) for value in horizons}))
    if not clean_horizons or any(value < 1 for value in clean_horizons):
        raise OvernightIntradayResearchError("horizons benötigt positive Sitzungszahlen.")
    if setup_mask_column is not None and setup_mask_column not in feature_frame.columns:
        raise OvernightIntradayResearchError(
            f"Setup-Maske {setup_mask_column!r} fehlt."
        )
    if asset_column not in feature_frame.columns:
        return _single_asset_labels(
            feature_frame,
            horizons=clean_horizons,
            setup_mask_column=setup_mask_column,
        )
    pieces = [
        _single_asset_labels(
            group,
            horizons=clean_horizons,
            setup_mask_column=setup_mask_column,
        )
        for _, group in feature_frame.groupby(
            asset_column, sort=False, dropna=False
        )
    ]
    return pd.concat(pieces, axis=0) if pieces else feature_frame.copy(deep=True)


def _number(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, 10) if math.isfinite(numeric) else None


def _metric_summary(
    rows: pd.DataFrame,
    *,
    horizon: int,
    minimum_cases: int,
) -> dict[str, object]:
    label = pd.to_numeric(rows.get(f"forward_return_{horizon}s"), errors="coerce")
    valid = rows.loc[label.notna()].copy()
    label = label.loc[label.notna()]
    bias = pd.to_numeric(valid.get("rolling_overnight_bias"), errors="coerce")
    correlation_rows = bias.notna() & label.notna()
    correlation = (
        bias.loc[correlation_rows].corr(label.loc[correlation_rows])
        if int(correlation_rows.sum()) >= 2
        else None
    )

    def mean(column: str) -> float | None:
        values = pd.to_numeric(valid.get(column), errors="coerce").dropna()
        return _number(values.mean()) if not values.empty else None

    count = int(len(valid))
    return {
        "horizon_sessions": horizon,
        "cases": count,
        "underpowered": count < minimum_cases,
        "mean_forward_return": _number(label.mean()) if count else None,
        "median_forward_return": _number(label.median()) if count else None,
        "forward_positive_rate": _number(label.gt(0).mean()) if count else None,
        "mean_mfe": mean(f"forward_mfe_{horizon}s"),
        "mean_mae": mean(f"forward_mae_{horizon}s"),
        "mean_overnight_return": mean("overnight_return"),
        "mean_intraday_return": mean("intraday_return"),
        "overnight_volatility": _number(
            pd.to_numeric(valid.get("overnight_return"), errors="coerce").std(ddof=1)
        ),
        "intraday_volatility": _number(
            pd.to_numeric(valid.get("intraday_return"), errors="coerce").std(ddof=1)
        ),
        "overnight_bias_forward_correlation": _number(correlation),
        "after_cost_return": None,
        "cost_model_status": "NOT_APPLICABLE_NO_TRADABLE_VARIANT",
        "performance_claim_allowed": False,
    }


def _group_summaries(
    frame: pd.DataFrame,
    *,
    column: str,
    horizons: tuple[int, ...],
    minimum_cases: int,
) -> list[dict[str, object]]:
    if column not in frame.columns:
        return []
    rows: list[dict[str, object]] = []
    for value, group in frame.groupby(column, sort=True, dropna=False):
        label = "NOT_AVAILABLE" if pd.isna(value) else str(value)
        rows.append(
            {
                "segment": label,
                "metrics": [
                    _metric_summary(group, horizon=horizon, minimum_cases=minimum_cases)
                    for horizon in horizons
                ],
            }
        )
    return rows


def evaluate_overnight_intraday_research(
    dataset: pd.DataFrame,
    *,
    horizons: Sequence[int] = DEFAULT_FORWARD_HORIZONS,
    minimum_cases: int = 30,
    asset_column: str = "asset",
    split_column: str = "research_split",
    walk_forward_column: str = "walk_forward_fold",
    segment_columns: Sequence[str] = OPTIONAL_SEGMENT_COLUMNS,
) -> dict[str, object]:
    """Build a descriptive report without selecting a rule or claiming an edge."""

    if minimum_cases < 1:
        raise OvernightIntradayResearchError("minimum_cases muss positiv sein.")
    clean_horizons = tuple(sorted({int(value) for value in horizons}))
    required = set(_feature_columns())
    missing = sorted(required - set(dataset.columns))
    if missing:
        raise OvernightIntradayResearchError(
            "Kausale Feature-Spalten fehlen: " + ", ".join(missing)
        )
    missing_labels = [
        f"forward_return_{horizon}s"
        for horizon in clean_horizons
        if f"forward_return_{horizon}s" not in dataset.columns
    ]
    if missing_labels:
        raise OvernightIntradayResearchError(
            "Research-Labels fehlen: " + ", ".join(missing_labels)
        )

    frame = dataset.copy(deep=True)
    if "signal_date" in frame.columns:
        dates = pd.to_datetime(frame["signal_date"], errors="coerce")
    else:
        dates = pd.to_datetime(frame.index, errors="coerce")
    frame["_calendar_period"] = pd.Series(dates, index=frame.index).dt.year.astype("Int64")

    asset_count = (
        int(frame[asset_column].dropna().nunique()) if asset_column in frame.columns else 1
    )
    period_count = int(frame["_calendar_period"].dropna().nunique())
    fold_count = (
        int(frame[walk_forward_column].dropna().nunique())
        if walk_forward_column in frame.columns
        else 0
    )
    split_values = (
        {str(value).strip().lower() for value in frame[split_column].dropna().unique()}
        if split_column in frame.columns
        else set()
    )
    return {
        "version": OVERNIGHT_INTRADAY_RESEARCH_VERSION,
        "market_scope": "EQUITIES/ETF",
        "status": "DESCRIPTIVE_RESEARCH_ONLY_NOT_CLASSIFIED",
        "overall": [
            _metric_summary(frame, horizon=horizon, minimum_cases=minimum_cases)
            for horizon in clean_horizons
        ],
        "by_asset": _group_summaries(
            frame,
            column=asset_column,
            horizons=clean_horizons,
            minimum_cases=minimum_cases,
        ),
        "by_period": _group_summaries(
            frame,
            column="_calendar_period",
            horizons=clean_horizons,
            minimum_cases=minimum_cases,
        ),
        "by_split": _group_summaries(
            frame,
            column=split_column,
            horizons=clean_horizons,
            minimum_cases=minimum_cases,
        ),
        "by_walk_forward_fold": _group_summaries(
            frame,
            column=walk_forward_column,
            horizons=clean_horizons,
            minimum_cases=minimum_cases,
        ),
        "segments": {
            column: _group_summaries(
                frame,
                column=column,
                horizons=clean_horizons,
                minimum_cases=minimum_cases,
            )
            for column in segment_columns
            if column in frame.columns
        },
        "coverage": {
            "asset_count": asset_count,
            "calendar_period_count": period_count,
            "multiple_assets_present": asset_count >= 2,
            "multiple_periods_present": period_count >= 2,
            "oos_split_present": bool(
                split_values & {"validation", "holdout", "out_of_sample", "oos"}
            ),
            "walk_forward_fold_count": fold_count,
            "walk_forward_present": fold_count >= 2,
        },
        "classification": "NOT_TESTED_OR_MANUALLY_CLASSIFIED",
        "baseline_changed": False,
        "live_signal_influence": False,
        "automatic_rule_selection": False,
        "automatic_activation": False,
    }


def classify_overnight_intraday_evidence(
    *,
    test_completed: bool,
    multiple_assets: bool,
    multiple_periods: bool,
    interesting_signal: bool,
    robust_out_of_sample: bool,
    robust_walk_forward: bool,
    temporally_stable: bool,
) -> dict[str, object]:
    """Apply the predeclared A/B/C evidence meaning without metric mining."""

    if not test_completed and any(
        (
            interesting_signal,
            robust_out_of_sample,
            robust_walk_forward,
            temporally_stable,
        )
    ):
        raise OvernightIntradayResearchError(
            "Unvollständige Tests dürfen keine positive Evidenzklassifikation erhalten."
        )
    if test_completed and not (multiple_assets and multiple_periods):
        raise OvernightIntradayResearchError(
            "Ein abgeschlossener Test benötigt mehrere Assets und Zeiträume."
        )
    if robust_out_of_sample or robust_walk_forward:
        if not interesting_signal:
            raise OvernightIntradayResearchError(
                "Robuste Evidenz ist ohne interessantes Basissignal widersprüchlich."
            )
    if not test_completed:
        grade = "NOT_TESTED"
        action = "TEST_BEFORE_ASSESSMENT"
        knowledge_outcome = "NOT_TESTED"
    elif all(
        (
            interesting_signal,
            robust_out_of_sample,
            robust_walk_forward,
            temporally_stable,
        )
    ):
        grade = "C"
        action = "REVIEW_SEPARATELY_VALIDATED_TARGETED_INTEGRATION"
        knowledge_outcome = "POSITIVE_CANDIDATE_NOT_ACTIVE"
    elif interesting_signal:
        grade = "B"
        action = "KEEP_AS_RESEARCH_ONLY"
        knowledge_outcome = "INCONCLUSIVE"
    else:
        grade = "A"
        action = "REJECT_NO_ROBUST_ADDITIONAL_VALUE"
        knowledge_outcome = "NEGATIVE"
    return {
        "grade": grade,
        "action": action,
        "knowledge_outcome": knowledge_outcome,
        "classification_uses_predeclared_manual_evidence_gate": True,
        "active_filter_created": False,
        "trade_rule_created": False,
        "automatic_activation": False,
    }


def overnight_intraday_research_plan() -> dict[str, object]:
    """Return the registered future research hypothesis and safety contract."""

    hypothesis = build_scoped_research_hypothesis(
        hypothesis_id="equities-etf-overnight-intraday-decomposition-v1",
        name="Overnight-/Intraday-Renditezerlegung",
        origin="predeclared multi-asset OHLC research hypothesis",
        source_scopes=["EQUITIES", "ETF"],
        test_scopes=["EQUITIES", "ETF"],
    )
    feature = build_scoped_research_feature(
        feature_id="overnight-intraday-decomposition-v1",
        name="Causal daily overnight and intraday return decomposition",
        definition=(
            "overnight=open[t]/close[t-1]-1; intraday=close[t]/open[t]-1; "
            "rolling bias, return contribution, and component volatility"
        ),
        causal_cutoff="including_only_the_completed_daily_bar_t",
        source_scopes=["EQUITIES", "ETF"],
        test_scopes=["EQUITIES", "ETF"],
    )
    plan: dict[str, object] = {
        "version": OVERNIGHT_INTRADAY_RESEARCH_VERSION,
        "status": "REGISTERED_NOT_TESTED",
        "market_scope": "EQUITIES/ETF",
        "hypothesis": hypothesis,
        "feature": feature,
        "required_design": {
            "multiple_assets": True,
            "multiple_periods": True,
            "forward_returns": True,
            "mfe_mae_for_existing_setups_when_meaningful": True,
            "temporal_stability": True,
            "out_of_sample": True,
            "walk_forward": True,
            "point_in_time_segments_only": True,
            "coherent_split_adjusted_ohlc_basis": True,
        },
        "optional_segments_if_already_available_causally": list(
            OPTIONAL_SEGMENT_COLUMNS
        ),
        "tradable_variant_cost_gate": {
            "not_applicable_until_variant_is_predeclared": True,
            "spread_required": True,
            "slippage_required": True,
            "fees_required": True,
            "net_edge_required": True,
        },
        "classification_after_test": {
            "A": "no_robust_additional_value_reject",
            "B": "interesting_but_unstable_research_only",
            "C": "robust_oos_and_walk_forward_value_review_targeted_integration",
        },
        "close_to_next_open_strategy_active": False,
        "single_asset_parameter_selection_allowed": False,
        "micron_may_define_or_justify_parameters": False,
        "current_broad_campaign_changed": False,
        "current_campaign_queue_changed": False,
        "research_database_write": False,
        "additional_provider_download": False,
        "current_baseline_changed": False,
        "active_filter_created": False,
        "trade_rule_created": False,
        "automatic_activation": False,
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    return plan
