from __future__ import annotations

"""Final Development-only robustness review for Buyer Confirmation.

The immutable Broad-v1 database and frozen OHLCV dataset are opened read-only.
Only ``objective_pullback`` candidates from the Development split are queried.
No Validation/Holdout reader and no challenger/freeze writer is imported here.
"""

import copy
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import pandas as pd


ROBUSTNESS_VERSION = "buyer-confirmation-development-robustness-2026.08.26-v3"
LEGACY_AUDIT_SEED_NAMESPACE = "swing-broad-v1-method-audit-2026.08.25-v3"
MATCH_SEED_NAMESPACE = "buyer-confirmation-final-development-match-v1"
MATCH_SENSITIVITY_SEEDS = tuple(f"predeclared-replicate-{index}" for index in range(5))
PROTECTED_DATASET_FINGERPRINT = (
    "e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed"
)
PROTECTED_FEATURE_CONTRACT_FINGERPRINT = (
    "c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd"
)
PROTECTED_CODE_FINGERPRINT = (
    "77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946"
)
BUYER_RULE = "Close[t] > High[t-1]"
SETUP_SCOPE = "objective_pullback"
BASELINE_ENTRY_POLICY = "next_session_open_after_completed_signal_bar"
STOP_CONTRACT = "pullback_low_minus_0.25_atr14"
EXIT_CONTRACT = "fixed_2r_with_25_session_horizon"
CONSERVATIVE_EXTRA_SLIPPAGE_BPS_ONE_WAY = 5.0
GAP_CASE_DEFINITION = "absolute entry gap of at least 1 ATR or simulated gap stop/gap target"
DECISION_KEEP_B = "KEEP_B"
DECISION_C_RECOMMENDATION = "C_RECOMMENDATION"

LEGACY_MATCH_KEYS = (
    "asset_type",
    "market_phase",
    "volatility_regime",
    "year",
)
REGION_CLUSTER_MATCH_KEYS = (
    "year",
    "asset_type",
    "region",
    "market_phase",
    "volatility_regime",
    "dependency_cluster",
)
STRICT_ASSET_CLUSTER_MATCH_KEYS = REGION_CLUSTER_MATCH_KEYS + ("symbol",)
DEPENDENCY_PROFILE_MATCH_KEYS = (
    "year",
    "asset_type",
    "region",
    "market_phase",
    "volatility_regime",
    "bearish_ge3",
    "pullback_depth_bin",
    "pullback_duration_bin",
    "relative_momentum_sign",
    "close_location_bin",
    "ema_trend",
    "bos_close_break",
)
STRICT_DEPENDENCY_MATCH_KEYS = STRICT_ASSET_CLUSTER_MATCH_KEYS + (
    "bearish_ge3",
    "pullback_depth_bin",
    "pullback_duration_bin",
    "relative_momentum_sign",
    "close_location_bin",
    "ema_trend",
    "bos_close_break",
)

# These floors choose between predeclared matching designs using coverage only,
# never outcomes. They are research-power guards, not trading parameters.
MATCH_RAW_ADEQUACY_FLOOR = 5_000
MATCH_EFFECTIVE_ADEQUACY_FLOOR = 2_500


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _canonical_json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(
        _clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        allow_nan=False,
        indent=indent,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _source_snapshot(broad_path: Path, dataset_root: Path) -> dict[str, object]:
    manifest_path = dataset_root / "manifest.json"
    files = (Path(broad_path), manifest_path)
    return {
        str(path.resolve()): {
            "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in files
    }


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _distribution(values: Iterable[object]) -> dict[str, object]:
    clean_values = [value for item in values if (value := _number(item)) is not None]
    return {
        "available_n": len(clean_values),
        "mean": sum(clean_values) / len(clean_values) if clean_values else None,
        "median": _percentile(clean_values, 0.5),
        "q25": _percentile(clean_values, 0.25),
        "q75": _percentile(clean_values, 0.75),
        "minimum": min(clean_values) if clean_values else None,
        "maximum": max(clean_values) if clean_values else None,
        "mean_is_outlier_sensitive": True,
    }


def _depth_bin(value: object) -> str:
    number = _number(value)
    if number is None:
        return "missing"
    if number < 0.450:
        return "below_0450"
    if number < 0.618:
        return "0450_0618"
    if number <= 0.786:
        return "0618_0786"
    if number <= 0.954:
        return "0786_0954"
    return "above_0954"


def _duration_bin(value: object) -> str:
    number = _number(value)
    if number is None:
        return "missing"
    if number <= 3:
        return "1_3"
    if number <= 7:
        return "4_7"
    if number <= 14:
        return "8_14"
    return "15_plus"


def _close_location_bin(value: object) -> str:
    number = _number(value)
    if number is None:
        return "missing"
    if number < 1 / 3:
        return "lower_third"
    if number < 2 / 3:
        return "middle_third"
    return "upper_third"


DEVELOPMENT_BUYER_QUERY = """SELECT
 c.candidate_id, c.symbol, c.signal_day, c.dependency_cluster,
 json_extract(c.feature_json, '$.asset.asset_type') asset_type,
 json_extract(c.feature_json, '$.asset.region') region,
 json_extract(c.feature_json, '$.technical.market_phase') market_phase,
 json_extract(c.feature_json, '$.technical.volatility_regime') volatility_regime,
 json_extract(c.feature_json, '$.pullback.status') pullback_status,
 json_type(c.feature_json, '$.pullback.buyer_confirmation_close_above_prior_high') buyer_type,
 json_extract(c.feature_json, '$.pullback.buyer_confirmation_close_above_prior_high') buyer_confirmation,
 json_type(c.feature_json, '$.candle_quality.close_above_prior_high') alias_type,
 json_extract(c.feature_json, '$.candle_quality.close_above_prior_high') alias_confirmation,
 json_extract(c.feature_json, '$.pullback.bearish_candles') bearish_candles,
 json_extract(c.feature_json, '$.pullback.pullback_depth') pullback_depth,
 json_extract(c.feature_json, '$.pullback.pullback_duration_sessions') pullback_duration,
 json_extract(c.feature_json, '$.relative_strength.relative_momentum_20d') relative_momentum,
 json_extract(c.feature_json, '$.candle_quality.close_position_in_range') close_location,
 json_extract(c.feature_json, '$.technical.ema20_relative_to_ema50') ema_ratio,
 json_extract(c.feature_json, '$.trend_quality.ema20_slope_atr_per_session') ema20_slope,
 json_type(c.feature_json, '$.market_structure.close_break') bos_type,
 json_extract(c.feature_json, '$.market_structure.close_break') bos_close_break,
 json_extract(c.feature_json, '$.technical.close') signal_close,
 json_extract(c.feature_json, '$.technical.atr_14') atr14,
 json_extract(c.feature_json, '$.pullback.pullback_low') pullback_low,
 json_extract(l.label_json, '$.entry.policy') entry_policy,
 json_extract(l.label_json, '$.entry.entry_day') entry_day,
 json_extract(l.label_json, '$.entry.raw') entry_raw,
 json_extract(l.label_json, '$.entry.after_costs') entry_after_costs,
 json_extract(l.label_json, '$.entry.cost_bps_one_way') cost_bps_one_way,
 json_extract(l.label_json, '$.entry.retroactive_signal_close_entry') retroactive_entry,
 json_extract(l.label_json, '$.mfe_pct') mfe_pct,
 json_extract(l.label_json, '$.mae_pct') mae_pct,
 json_extract(l.label_json, '$.time_to_mfe_sessions') sessions_to_mfe,
 json_extract(l.label_json, '$.time_to_exit_sessions') sessions_to_exit,
 json_array_length(l.label_json, '$.gap_events') stored_gap_event_n,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.stop') stop,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.exits.fixed_2r.result_r') result_r,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.exits.fixed_2r.status') exit_status,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.exits.fixed_2r.sessions') result_sessions
 FROM broad_research_candidates c
 JOIN broad_research_labels l USING(candidate_id)
 JOIN broad_research_counterfactuals e USING(candidate_id)
 WHERE c.research_split='development'
   AND c.setup_family='objective_pullback'
 ORDER BY c.signal_day, c.candidate_id"""


def _guard_development_query(sql: str) -> None:
    normalized = "".join(sql.lower().split())
    if "frombroad_research_candidates" not in normalized:
        raise ValueError("Candidate reads require the guarded Development query.")
    if "c.research_split='development'" not in normalized:
        raise ValueError("Only the Development split may be read.")


def _record_from_sql(row: sqlite3.Row) -> dict[str, object]:
    entry = _number(row["entry_after_costs"])
    raw_entry = _number(row["entry_raw"])
    stop = _number(row["stop"])
    atr = _number(row["atr14"])
    pullback_low = _number(row["pullback_low"])
    risk = entry - stop if entry is not None and stop is not None else None
    mfe_pct = _number(row["mfe_pct"])
    mae_pct = _number(row["mae_pct"])
    result_r = _number(row["result_r"])
    entry_to_low = entry - pullback_low if entry is not None and pullback_low is not None else None
    valid_risk = risk is not None and risk > 0 and entry is not None and entry > 0
    valid_atr = atr is not None and atr > 0
    valid_entry_to_low = entry_to_low is not None and entry_to_low > 0

    def pct_to_price(value: float | None) -> float | None:
        return value / 100 * entry if value is not None and entry is not None else None

    mfe_price = pct_to_price(mfe_pct)
    mae_price = pct_to_price(mae_pct)
    target_distance = 2 * risk if risk is not None else None
    signal_close = _number(row["signal_close"])
    buyer = None if row["buyer_type"] is None else bool(row["buyer_confirmation"])
    alias = None if row["alias_type"] is None else bool(row["alias_confirmation"])
    return {
        "candidate_id": str(row["candidate_id"]),
        "symbol": str(row["symbol"]),
        "signal_day": str(row["signal_day"]),
        "year": str(row["signal_day"])[:4],
        "dependency_cluster": str(row["dependency_cluster"] or ""),
        "asset_type": str(row["asset_type"] or "unknown"),
        "region": str(row["region"] or "unknown"),
        "market_phase": str(row["market_phase"] or "unknown"),
        "volatility_regime": str(row["volatility_regime"] or "unknown"),
        "pullback_status": str(row["pullback_status"] or "missing"),
        "buyer_confirmation": buyer,
        "alias_confirmation": alias,
        "bearish_candles": _number(row["bearish_candles"]),
        "bearish_ge3": str((_number(row["bearish_candles"]) or 0) >= 3),
        "pullback_depth": _number(row["pullback_depth"]),
        "pullback_depth_bin": _depth_bin(row["pullback_depth"]),
        "pullback_duration": _number(row["pullback_duration"]),
        "pullback_duration_bin": _duration_bin(row["pullback_duration"]),
        "relative_momentum": _number(row["relative_momentum"]),
        "relative_momentum_sign": (
            "missing" if _number(row["relative_momentum"]) is None
            else "positive" if float(row["relative_momentum"]) > 0 else "non_positive"
        ),
        "close_location": _number(row["close_location"]),
        "close_location_bin": _close_location_bin(row["close_location"]),
        "ema_trend": str(
            (_number(row["ema_ratio"]) or 0) > 1
            and (_number(row["ema20_slope"]) or 0) > 0
        ),
        "bos_close_break": (
            "missing" if row["bos_type"] is None else str(bool(row["bos_close_break"]))
        ),
        "signal_close": signal_close,
        "atr14": atr,
        "pullback_low": pullback_low,
        "entry_policy": str(row["entry_policy"] or "missing"),
        "entry_day": str(row["entry_day"] or ""),
        "entry_raw": raw_entry,
        "entry_price": entry,
        "cost_bps_one_way": _number(row["cost_bps_one_way"]),
        "retroactive_entry": bool(row["retroactive_entry"]),
        "stop": stop,
        "risk": risk,
        "result_r": result_r,
        "result_pct": result_r * risk / entry * 100 if result_r is not None and valid_risk else None,
        "risk_geometry_valid": bool(valid_risk and valid_atr and valid_entry_to_low),
        "entry_to_pullback_low_pct": entry_to_low / entry * 100 if valid_entry_to_low and entry else None,
        "entry_to_pullback_low_atr": (
            entry_to_low / atr if valid_entry_to_low and valid_atr else None
        ),
        "stop_distance_pct": risk / entry * 100 if valid_risk else None,
        "stop_distance_atr": risk / atr if valid_risk and valid_atr else None,
        "initial_risk_pct": risk / entry * 100 if valid_risk else None,
        "target_distance_pct": target_distance / entry * 100 if valid_risk else None,
        "target_distance_atr": target_distance / atr if valid_risk and valid_atr else None,
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "mfe_atr": (
            mfe_price / atr
            if mfe_price is not None and valid_risk and valid_atr and valid_entry_to_low else None
        ),
        "mae_atr": (
            mae_price / atr
            if mae_price is not None and valid_risk and valid_atr and valid_entry_to_low else None
        ),
        "mfe_r": mfe_price / risk if mfe_price is not None and valid_risk else None,
        "mae_r": mae_price / risk if mae_price is not None and valid_risk else None,
        "giveback_r": (
            mfe_price / risk - result_r
            if mfe_price is not None and result_r is not None and valid_risk else None
        ),
        "sessions_to_mfe": _number(row["sessions_to_mfe"]),
        "sessions_to_exit": _number(row["sessions_to_exit"]),
        "stored_gap_event_n": int(row["stored_gap_event_n"] or 0),
        "entry_gap_atr": (
            (raw_entry - signal_close) / atr
            if raw_entry is not None and signal_close is not None and atr and atr > 0 else None
        ),
        "exit_status": str(row["exit_status"] or "missing"),
        "result_sessions": _number(row["result_sessions"]),
    }


def read_development_rows(path: Path) -> list[dict[str, object]]:
    _guard_development_query(DEVELOPMENT_BUYER_QUERY)
    with _read_only_connection(Path(path)) as connection:
        return [_record_from_sql(row) for row in connection.execute(DEVELOPMENT_BUYER_QUERY)]


@dataclass
class _Performance:
    cases: int = 0
    evaluated: int = 0
    sum_r: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    wins: int = 0
    clusters: set[str] = field(default_factory=set)

    def update(self, row: Mapping[str, object]) -> None:
        self.cases += 1
        cluster = str(row.get("dependency_cluster") or "")
        if cluster:
            self.clusters.add(cluster)
        result = _number(row.get("result_r"))
        if result is None:
            return
        self.evaluated += 1
        self.sum_r += result
        if result > 0:
            self.wins += 1
            self.gross_profit += result
        else:
            self.gross_loss += abs(result)

    def result(self) -> dict[str, object]:
        return {
            "raw_n": self.cases,
            "evaluated_n": self.evaluated,
            "effective_dependency_cluster_n": len(self.clusters),
            "expectancy_r": self.sum_r / self.evaluated if self.evaluated else None,
            "profit_factor": self.gross_profit / self.gross_loss if self.gross_loss else None,
            "win_rate_pct": self.wins / self.evaluated * 100 if self.evaluated else None,
            "total_r": self.sum_r,
        }


GEOMETRY_FIELDS = (
    "entry_price",
    "entry_to_pullback_low_pct",
    "entry_to_pullback_low_atr",
    "stop_distance_pct",
    "stop_distance_atr",
    "initial_risk_pct",
    "target_distance_pct",
    "target_distance_atr",
    "result_pct",
    "mfe_pct",
    "mae_pct",
    "mfe_atr",
    "mae_atr",
    "mfe_r",
    "mae_r",
    "giveback_r",
    "sessions_to_mfe",
    "sessions_to_exit",
)


def _performance(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    stats = _Performance()
    for row in rows:
        stats.update(row)
    return stats.result()


def _segment_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    dimensions = ("year", "market_phase", "volatility_regime", "asset_type", "region")
    result: dict[str, object] = {}
    for dimension in dimensions:
        groups: dict[str, _Performance] = {}
        for row in rows:
            name = str(row.get(dimension) or "unknown")
            groups.setdefault(name, _Performance()).update(row)
        metrics = {name: value.result() for name, value in sorted(groups.items())}
        total_cases = sum(int(value["raw_n"]) for value in metrics.values())
        absolute_result = sum(abs(float(value["total_r"])) for value in metrics.values())
        largest_case = max(metrics, key=lambda key: int(metrics[key]["raw_n"])) if metrics else None
        largest_result = max(metrics, key=lambda key: abs(float(metrics[key]["total_r"]))) if metrics else None
        result[dimension] = {
            "groups": metrics,
            "largest_case_group": largest_case,
            "largest_case_share": (
                int(metrics[largest_case]["raw_n"]) / total_cases
                if largest_case is not None and total_cases else None
            ),
            "largest_absolute_result_group": largest_result,
            "largest_absolute_result_contribution_share": (
                abs(float(metrics[largest_result]["total_r"])) / absolute_result
                if largest_result is not None and absolute_result else None
            ),
            "natural_sample_weights_preserved": True,
        }
    return result


def summarize_rows(rows: Sequence[Mapping[str, object]], *, include_segments: bool = True) -> dict[str, object]:
    base = _performance(rows)
    geometry = {name: _distribution(row.get(name) for row in rows) for name in GEOMETRY_FIELDS}
    mfe_r = [_number(row.get("mfe_r")) for row in rows]
    valid_mfe = [value for value in mfe_r if value is not None]
    valid_mfe_mae = [
        (mfe, abs(mae))
        for row in rows
        if (mfe := _number(row.get("mfe_r"))) is not None
        and (mae := _number(row.get("mae_r"))) is not None
        and abs(mae) > 0
    ]
    positive_giveback = [
        _number(row.get("giveback_r"))
        for row in rows
        if (_number(row.get("mfe_r")) or 0) > 0
        and _number(row.get("giveback_r")) is not None
    ]
    return {
        **base,
        "risk_and_entry_geometry": geometry,
        "risk_geometry_quality": {
            "valid_n": sum(row.get("risk_geometry_valid") is True for row in rows),
            "invalid_or_missing_n": sum(row.get("risk_geometry_valid") is not True for row in rows),
            "extreme_stop_distance_above_100_atr_n": sum(
                (_number(row.get("stop_distance_atr")) or 0) > 100 for row in rows
            ),
            "extreme_values_excluded_from_performance": False,
            "decision_comparison_uses_robust_medians": True,
        },
        "entry_efficiency": {
            "mfe_available_n": len(valid_mfe),
            "positive_mfe_share": (
                sum(value > 0 for value in valid_mfe) / len(valid_mfe) if valid_mfe else None
            ),
            "mfe_threshold_share": {
                f"at_least_{threshold:g}r": (
                    sum(value >= threshold for value in valid_mfe) / len(valid_mfe)
                    if valid_mfe else None
                )
                for threshold in (0.5, 1.0, 1.5, 2.0)
            },
            "mfe_to_absolute_mae_ratio": _distribution(
                mfe / mae for mfe, mae in valid_mfe_mae
            ),
            "peak_mfe_minus_final_result_r": geometry["giveback_r"],
            "giveback_after_positive_mfe_r": _distribution(positive_giveback),
            "time_to_first_positive_available": False,
            "earlier_positive_movement_claimed": False,
        },
        "segments": _segment_report(rows) if include_segments else None,
    }


def _stable_identity_hash(row: Mapping[str, object], seed: str) -> str:
    identity = f"{seed}|{row.get('candidate_id')}|{row.get('signal_day')}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def outcome_blind_exact_match(
    rows: Sequence[Mapping[str, object]],
    *,
    keys: Sequence[str],
    match_id: str,
    seed_namespace: str = MATCH_SEED_NAMESPACE,
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]], dict[str, object]]:
    groups: dict[tuple[str, ...], dict[bool, list[Mapping[str, object]]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    eligible_treatment = eligible_control = 0
    structurally_missing = 0
    for row in rows:
        selected = row.get("buyer_confirmation")
        if selected is None or row.get("pullback_status") != "available":
            structurally_missing += 1
            continue
        if bool(selected):
            eligible_treatment += 1
        else:
            eligible_control += 1
        key = tuple(str(row.get(name) if row.get(name) is not None else "missing") for name in keys)
        groups[key][bool(selected)].append(row)
    treatment: list[Mapping[str, object]] = []
    control: list[Mapping[str, object]] = []
    matched_strata = unmatched_strata = 0
    for stratum, pair in groups.items():
        size = min(len(pair[True]), len(pair[False]))
        if size <= 0:
            unmatched_strata += 1
            continue
        matched_strata += 1
        seed = f"{seed_namespace}|{match_id}|{'|'.join(stratum)}"
        treatment.extend(sorted(pair[True], key=lambda row: _stable_identity_hash(row, seed))[:size])
        control.extend(sorted(pair[False], key=lambda row: _stable_identity_hash(row, seed))[:size])
    treatment = sorted(treatment, key=lambda row: (str(row["signal_day"]), str(row["candidate_id"])))
    control = sorted(control, key=lambda row: (str(row["signal_day"]), str(row["candidate_id"])))
    treatment_result = summarize_rows(treatment)
    control_result = summarize_rows(control)
    treatment_r = _number(treatment_result.get("expectancy_r"))
    control_r = _number(control_result.get("expectancy_r"))
    report = {
        "match_id": match_id,
        "strata": list(keys),
        "selection": f"stable_identity_hash_within_{'_'.join(keys)}_strata",
        "selection_uses_outcomes": False,
        "natural_case_weights_preserved": True,
        "small_strata_equal_weighted": False,
        "matched_strata": matched_strata,
        "unmatched_strata": unmatched_strata,
        "structurally_missing_n": structurally_missing,
        "eligible_treatment_n": eligible_treatment,
        "eligible_control_n": eligible_control,
        "matched_treatment_n": len(treatment),
        "matched_control_n": len(control),
        "unmatched_treatment_n": eligible_treatment - len(treatment),
        "unmatched_control_n": eligible_control - len(control),
        "treatment_retention_share": len(treatment) / eligible_treatment if eligible_treatment else None,
        "control_retention_share": len(control) / eligible_control if eligible_control else None,
        "treatment": treatment_result,
        "control": control_result,
        "delta_expectancy_r": (
            treatment_r - control_r if treatment_r is not None and control_r is not None else None
        ),
        "effective_n": {
            "treatment": treatment_result["effective_dependency_cluster_n"],
            "control": control_result["effective_dependency_cluster_n"],
        },
        "point_in_time_matching_features_only": True,
        "causal_claim": False,
    }
    return treatment, control, report


def matching_seed_sensitivity(
    rows: Sequence[Mapping[str, object]],
    *,
    keys: Sequence[str],
    match_id: str,
) -> dict[str, object]:
    """Measure deterministic control-sampling sensitivity without choosing a seed by outcome."""
    groups: dict[tuple[str, ...], dict[bool, list[Mapping[str, object]]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    for row in rows:
        if row.get("buyer_confirmation") is None or row.get("pullback_status") != "available":
            continue
        key = tuple(str(row.get(name) if row.get(name) is not None else "missing") for name in keys)
        groups[key][bool(row["buyer_confirmation"])].append(row)
    replicates = []
    for replicate in MATCH_SENSITIVITY_SEEDS:
        treatment_stats, control_stats = _Performance(), _Performance()
        matched_n = 0
        for stratum, pair in groups.items():
            size = min(len(pair[True]), len(pair[False]))
            if size <= 0:
                continue
            seed = f"{MATCH_SEED_NAMESPACE}|{match_id}|{replicate}|{'|'.join(stratum)}"
            selected_treatment = sorted(
                pair[True], key=lambda row: _stable_identity_hash(row, seed)
            )[:size]
            selected_control = sorted(
                pair[False], key=lambda row: _stable_identity_hash(row, seed)
            )[:size]
            for row in selected_treatment:
                treatment_stats.update(row)
            for row in selected_control:
                control_stats.update(row)
            matched_n += size
        treatment_result = treatment_stats.result()
        control_result = control_stats.result()
        treatment_r = _number(treatment_result.get("expectancy_r"))
        control_r = _number(control_result.get("expectancy_r"))
        replicates.append(
            {
                "replicate": replicate,
                "matched_per_group_n": matched_n,
                "treatment_effective_n": treatment_result["effective_dependency_cluster_n"],
                "control_effective_n": control_result["effective_dependency_cluster_n"],
                "treatment_expectancy_r": treatment_r,
                "control_expectancy_r": control_r,
                "delta_expectancy_r": (
                    treatment_r - control_r
                    if treatment_r is not None and control_r is not None else None
                ),
            }
        )
    deltas = [
        float(row["delta_expectancy_r"])
        for row in replicates if _number(row.get("delta_expectancy_r")) is not None
    ]
    return {
        "replicates": replicates,
        "predeclared_replicate_n": len(MATCH_SENSITIVITY_SEEDS),
        "seed_selected_using_outcomes": False,
        "minimum_delta_expectancy_r": min(deltas) if deltas else None,
        "median_delta_expectancy_r": _percentile(deltas, 0.5),
        "maximum_delta_expectancy_r": max(deltas) if deltas else None,
        "all_replicates_positive": bool(deltas) and all(value > 0 for value in deltas),
    }


def _adequate_match(report: Mapping[str, object]) -> bool:
    effective = report.get("effective_n") or {}
    return (
        int(report.get("matched_treatment_n") or 0) >= MATCH_RAW_ADEQUACY_FLOOR
        and int(report.get("matched_control_n") or 0) >= MATCH_RAW_ADEQUACY_FLOOR
        and int(effective.get("treatment") or 0) >= MATCH_EFFECTIVE_ADEQUACY_FLOOR
        and int(effective.get("control") or 0) >= MATCH_EFFECTIVE_ADEQUACY_FLOOR
    )


def _choose_match(
    variants: Sequence[tuple[list[Mapping[str, object]], list[Mapping[str, object]], Mapping[str, object]]]
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]], Mapping[str, object]]:
    for variant in reversed(variants):
        if _adequate_match(variant[2]):
            return variant
    return max(variants, key=lambda item: int(item[2].get("matched_treatment_n") or 0))


def _alias_review(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    comparable = [
        row for row in rows
        if row.get("buyer_confirmation") is not None and row.get("alias_confirmation") is not None
    ]
    mismatches = sum(
        bool(row["buyer_confirmation"]) != bool(row["alias_confirmation"])
        for row in comparable
    )
    return {
        "compared_n": len(comparable),
        "mismatches": mismatches,
        "semantic_alias": mismatches == 0 and bool(comparable),
        "independent_confirmation_count": 1 if mismatches == 0 and comparable else None,
        "counted_twice": False,
    }


def _geometry_assessment(
    treatment: Mapping[str, object], control: Mapping[str, object]
) -> dict[str, object]:
    tg = treatment.get("risk_and_entry_geometry") or {}
    cg = control.get("risk_and_entry_geometry") or {}

    def statistic(group: Mapping[str, object], name: str, key: str) -> float | None:
        return _number((group.get(name) or {}).get(key))

    fields = (
        "stop_distance_pct",
        "stop_distance_atr",
        "result_pct",
        "mfe_pct",
        "mae_pct",
        "mfe_r",
        "mae_r",
    )
    mean_deltas = {
        name: (
            statistic(tg, name, "mean") - statistic(cg, name, "mean")
            if statistic(tg, name, "mean") is not None
            and statistic(cg, name, "mean") is not None else None
        )
        for name in fields
    }
    median_deltas = {
        name: (
            statistic(tg, name, "median") - statistic(cg, name, "median")
            if statistic(tg, name, "median") is not None
            and statistic(cg, name, "median") is not None else None
        )
        for name in fields
    }
    raw_result_improved = (_number(mean_deltas.get("result_pct")) or 0) > 0
    raw_mfe_improved = (_number(mean_deltas.get("mfe_pct")) or 0) > 0
    median_stop_delta = _number(median_deltas.get("stop_distance_pct"))
    denominator_mechanically_favors_treatment = (
        median_stop_delta is not None and median_stop_delta < 0
    )
    return {
        "treatment_minus_control_mean": mean_deltas,
        "treatment_minus_control_median": median_deltas,
        "r_denominator_changed": abs(median_stop_delta or 0) > 1e-12,
        "treatment_has_wider_median_stop_distance": (median_stop_delta or 0) > 0,
        "r_denominator_mechanically_favors_treatment": denominator_mechanically_favors_treatment,
        "raw_percent_result_improved": raw_result_improved,
        "raw_percent_mfe_improved": raw_mfe_improved,
        "advantage_explained_exclusively_by_r_denominator": (
            denominator_mechanically_favors_treatment
            and not (raw_result_improved and raw_mfe_improved)
        ),
        "interpretation": (
            "Treatment has wider median risk, so the R denominator works against rather than in favor of Buyer Confirmation. "
            "Average raw-percent outcome improves, while MFE/MAE path quality is broadly similar and does not support a causal claim."
        ),
        "causal_claim": False,
    }


def sensitivity_stress(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    scenarios = {
        "base": 0.0,
        "additional_0.05r_slippage": 0.05,
        "additional_0.10r_adverse_entry": 0.10,
        "additional_0.15r_total_cost": 0.15,
    }
    report = {}
    for name, penalty in scenarios.items():
        stressed = [
            {**row, "result_r": (_number(row.get("result_r")) - penalty)}
            for row in rows if _number(row.get("result_r")) is not None
        ]
        report[name] = _performance(stressed)
    gap_stressed = [
        {
            **row,
            "result_r": (
                _number(row.get("result_r")) - (0.25 if int(row.get("stored_gap_event_n") or 0) else 0)
            ),
        }
        for row in rows if _number(row.get("result_r")) is not None
    ]
    report["legacy_gap_sensitivity"] = _performance(gap_stressed)
    return {
        "classification": "SENSITIVITY_STRESS",
        "is_execution_simulation": False,
        "is_fill_or_broker_simulation": False,
        "historical_results_rewritten": False,
        "scenarios": report,
    }


def _simulate_fixed_2r(
    future: pd.DataFrame,
    *,
    entry: float,
    stop: float,
    cost_bps_one_way: float,
) -> dict[str, object]:
    risk = entry - stop
    if risk <= 0 or future.empty:
        return {"status": "invalid_or_unfilled", "result_r": None}
    target = entry + 2 * risk
    for offset, (_, bar) in enumerate(future.iloc[:25].iterrows(), start=1):
        opening, low, high = float(bar["Open"]), float(bar["Low"]), float(bar["High"])
        if opening <= stop:
            exit_price, status = opening, "gap_stop"
        elif low <= stop:
            exit_price, status = stop, "stop"
        elif opening >= target:
            exit_price, status = opening, "gap_target"
        elif high >= target:
            exit_price, status = target, "target"
        else:
            continue
        after_costs = exit_price * (1 - cost_bps_one_way / 10_000)
        return {
            "status": status,
            "sessions": offset,
            "result_r": (after_costs - entry) / risk,
        }
    exit_price = float(future.iloc[:25].iloc[-1]["Close"])
    after_costs = exit_price * (1 - cost_bps_one_way / 10_000)
    return {
        "status": "horizon_exit",
        "sessions": min(len(future), 25),
        "result_r": (after_costs - entry) / risk,
    }


class _FrozenHistoryReader:
    def __init__(self, dataset_root: Path):
        self.root = Path(dataset_root)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("status") != "finalized":
            raise RuntimeError("The frozen dataset must be finalized.")
        if self.manifest.get("dataset_fingerprint") != PROTECTED_DATASET_FINGERPRINT:
            raise RuntimeError("Protected frozen dataset fingerprint mismatch.")
        self.scopes = []
        for scope_id, payload in self.manifest.get("scopes", {}).items():
            contract = payload.get("contract") or {}
            self.scopes.append(
                (
                    str(contract.get("start") or "0000-01-01"),
                    str(contract.get("end") or "9999-12-31"),
                    scope_id,
                    payload.get("assets") or {},
                )
            )
        self._cached_key: tuple[str, str] | None = None
        self._cached_frame: pd.DataFrame | None = None

    def _scope_asset(self, symbol: str, signal_day: str) -> tuple[str, Mapping[str, object]]:
        for start, end, scope_id, assets in self.scopes:
            if start <= signal_day < end:
                payload = assets.get(symbol) or {}
                return scope_id, payload
        return "", {}

    def future(self, row: Mapping[str, object]) -> tuple[pd.DataFrame | None, str | None]:
        symbol, signal_day = str(row["symbol"]), str(row["signal_day"])
        scope_id, asset = self._scope_asset(symbol, signal_day)
        relative = asset.get("file")
        if asset.get("status") != "available" or not relative:
            return None, "frozen_history_unavailable"
        cache_key = (scope_id, symbol)
        if cache_key != self._cached_key:
            self._cached_frame = pd.read_parquet(self.root / str(relative))
            self._cached_key = cache_key
        frame = self._cached_frame
        if frame is None:
            return None, "frozen_history_unavailable"
        entry_day = pd.Timestamp(str(row.get("entry_day")))
        future = frame.loc[frame.index >= entry_day].iloc[:25]
        if future.empty or pd.Timestamp(future.index[0]).date().isoformat() != str(row.get("entry_day")):
            return None, "entry_day_not_found"
        expected_open = _number(row.get("entry_raw"))
        if expected_open is None or not math.isclose(float(future.iloc[0]["Open"]), expected_open, rel_tol=1e-10, abs_tol=1e-8):
            return None, "entry_open_contract_mismatch"
        return future, None


def execution_simulation(
    treatment: Sequence[Mapping[str, object]],
    control: Sequence[Mapping[str, object]],
    *,
    dataset_root: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, object]:
    reader = _FrozenHistoryReader(Path(dataset_root))
    groups = (("treatment", treatment), ("control", control))
    output: dict[str, object] = {}
    total = sum(len(rows) for _, rows in groups)
    processed = 0
    for group_name, source_rows in groups:
        baseline_rows: list[dict[str, object]] = []
        conservative_rows: list[dict[str, object]] = []
        no_fill: dict[str, int] = defaultdict(int)
        not_evaluable: dict[str, int] = defaultdict(int)
        not_evaluable_case_n = 0
        baseline_mismatches = 0
        maximum_difference = 0.0
        gap_cases = 0
        ordered = sorted(source_rows, key=lambda row: (str(row["symbol"]), str(row["signal_day"]), str(row["candidate_id"])))
        for row in ordered:
            processed += 1
            future, error = reader.future(row)
            if error or future is None:
                no_fill[str(error)] += 1
                continue
            stop = _number(row.get("stop"))
            raw_entry = _number(row.get("entry_raw"))
            base_cost = _number(row.get("cost_bps_one_way"))
            stored_entry = _number(row.get("entry_price"))
            if None in (stop, raw_entry, base_cost, stored_entry):
                no_fill["missing_execution_contract"] += 1
                continue
            baseline = _simulate_fixed_2r(
                future,
                entry=float(stored_entry),
                stop=float(stop),
                cost_bps_one_way=float(base_cost),
            )
            conservative_cost = float(base_cost) + CONSERVATIVE_EXTRA_SLIPPAGE_BPS_ONE_WAY
            conservative_entry = float(raw_entry) * (1 + conservative_cost / 10_000)
            conservative = _simulate_fixed_2r(
                future,
                entry=conservative_entry,
                stop=float(stop),
                cost_bps_one_way=conservative_cost,
            )
            baseline_invalid = _number(baseline.get("result_r")) is None
            conservative_invalid = _number(conservative.get("result_r")) is None
            if baseline_invalid or conservative_invalid:
                not_evaluable_case_n += 1
            if baseline_invalid:
                not_evaluable[f"baseline_{baseline.get('status')}"] += 1
            if conservative_invalid:
                not_evaluable[f"conservative_{conservative.get('status')}"] += 1
            stored_result = _number(row.get("result_r"))
            reconstructed = _number(baseline.get("result_r"))
            if stored_result is not None and reconstructed is not None:
                difference = abs(stored_result - reconstructed)
                maximum_difference = max(maximum_difference, difference)
                if difference > 1e-8:
                    baseline_mismatches += 1
            base_row = {**row, "result_r": reconstructed}
            conservative_row = {**row, "result_r": _number(conservative.get("result_r"))}
            baseline_rows.append(base_row)
            conservative_rows.append(conservative_row)
            if str(conservative.get("status")) in {"gap_stop", "gap_target"} or abs(_number(row.get("entry_gap_atr")) or 0) >= 1:
                gap_cases += 1
            if progress_callback and processed % 10_000 == 0:
                progress_callback(processed, total)
        output[group_name] = {
            "source_n": len(source_rows),
            "baseline": _performance(baseline_rows),
            "conservative": _performance(conservative_rows),
            "expectancy_change_r": (
                (_number(_performance(conservative_rows).get("expectancy_r")) or 0)
                - (_number(_performance(baseline_rows).get("expectancy_r")) or 0)
            ),
            "gap_case_n": gap_cases,
            "cases_without_realistic_fill": sum(no_fill.values()),
            "no_fill_reasons": dict(sorted(no_fill.items())),
            "not_evaluable_execution_case_n": not_evaluable_case_n,
            "not_evaluable_reasons": dict(sorted(not_evaluable.items())),
            "baseline_reproduction": {
                "mismatch_n": baseline_mismatches,
                "maximum_absolute_result_r_difference": maximum_difference,
            },
        }
    treatment_conservative = output["treatment"]["conservative"]
    control_conservative = output["control"]["conservative"]
    return {
        "classification": "EXECUTION_SIMULATION",
        "is_sensitivity_stress": False,
        "entry_contract": BASELINE_ENTRY_POLICY,
        "stop_contract": STOP_CONTRACT,
        "exit_contract": EXIT_CONTRACT,
        "baseline_cost_contract": "stored Broad-v1 one-way spread/slippage/fee contract",
        "conservative_variant": (
            f"same next-session Open with stored costs plus {CONSERVATIVE_EXTRA_SLIPPAGE_BPS_ONE_WAY:g} bps "
            "additional adverse slippage one-way at entry and exit"
        ),
        "variant_selected_by_outcomes": False,
        "daily_bar_order": "gap_then_stop_before_target",
        "gap_case_definition": GAP_CASE_DEFINITION,
        "intrabar_sequence_claimed": False,
        "treatment": output["treatment"],
        "control": output["control"],
        "conservative_delta_expectancy_r": (
            (_number(treatment_conservative.get("expectancy_r")) or 0)
            - (_number(control_conservative.get("expectancy_r")) or 0)
        ),
    }


def _verify_manifest(connection: sqlite3.Connection) -> dict[str, object]:
    rows = connection.execute(
        "SELECT manifest_json, manifest_fingerprint FROM broad_research_manifests"
    ).fetchall()
    if len(rows) != 1:
        raise RuntimeError("Exactly one Broad-v1 manifest is required.")
    manifest = json.loads(rows[0]["manifest_json"])
    if _fingerprint(manifest) != rows[0]["manifest_fingerprint"]:
        raise RuntimeError("Broad-v1 manifest fingerprint is invalid.")
    expected = {
        "dataset_fingerprint": PROTECTED_DATASET_FINGERPRINT,
        "feature_contract_fingerprint": PROTECTED_FEATURE_CONTRACT_FINGERPRINT,
        "code_fingerprint": PROTECTED_CODE_FINGERPRINT,
    }
    mismatch = {key: (manifest.get(key), value) for key, value in expected.items() if manifest.get(key) != value}
    if mismatch:
        raise RuntimeError(f"Protected Broad-v1 fingerprint mismatch: {mismatch}")
    return {**expected, "manifest_fingerprint": rows[0]["manifest_fingerprint"]}


def verify_prior_audit(path: Path) -> dict[str, object]:
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    stored_fingerprint = report.get("report_fingerprint")
    payload = {key: value for key, value in report.items() if key != "report_fingerprint"}
    if _fingerprint(payload) != stored_fingerprint:
        raise RuntimeError("Prior reviewed audit fingerprint is invalid.")
    buyer = next(
        row for row in report.get("hypotheses", []) if row.get("hypothesis_id") == "buyer_confirmation"
    )
    return {
        "audit_version": report.get("audit_version"),
        "report_fingerprint": stored_fingerprint,
        "manual_recommendation": (
            (((report.get("manual_review") or {}).get("decisions") or {}).get("buyer_confirmation") or {}).get("recommendation")
        ),
        "treatment_expectancy_r": (buyer.get("treatment") or {}).get("candidate_expectancy_r"),
        "treatment_profit_factor": (buyer.get("treatment") or {}).get("candidate_profit_factor"),
        "control_expectancy_r": (buyer.get("control") or {}).get("candidate_expectancy_r"),
        "positive_years": ((buyer.get("treatment") or {}).get("time_stability") or {}).get("positive_expectancy_years"),
        "evaluated_years": ((buyer.get("treatment") or {}).get("time_stability") or {}).get("evaluated_years"),
        "legacy_match": buyer.get("regime_matched_placebo"),
        "legacy_dependency_adjustment": (
            (buyer.get("dependency_and_ablation") or {}).get("descriptive_dependency_adjustment")
        ),
    }


def refresh_prior_audit_verification(
    report: Mapping[str, object], prior_audit_path: Path
) -> dict[str, object]:
    result = copy.deepcopy(dict(report))
    result.pop("report_fingerprint", None)
    result["prior_audit_verification"] = verify_prior_audit(prior_audit_path)
    if isinstance(result.get("execution_simulation"), dict):
        result["execution_simulation"]["gap_case_definition"] = GAP_CASE_DEFINITION
    result["report_fingerprint"] = _fingerprint(result)
    return result


def build_robustness_report(
    broad_path: Path,
    dataset_root: Path,
    prior_audit_path: Path,
    *,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict[str, object]:
    broad_path, dataset_root = Path(broad_path), Path(dataset_root)
    before = _source_snapshot(broad_path, dataset_root)
    with _read_only_connection(broad_path) as connection:
        fingerprints = _verify_manifest(connection)
    prior = verify_prior_audit(prior_audit_path)
    rows = read_development_rows(broad_path)
    treatment = [row for row in rows if row.get("buyer_confirmation") is True]
    control = [row for row in rows if row.get("buyer_confirmation") is False]
    missing = [row for row in rows if row.get("buyer_confirmation") is None]

    legacy = outcome_blind_exact_match(
        rows,
        keys=LEGACY_MATCH_KEYS,
        match_id="buyer_confirmation",
        seed_namespace=LEGACY_AUDIT_SEED_NAMESPACE,
    )
    region_cluster = outcome_blind_exact_match(
        rows, keys=REGION_CLUSTER_MATCH_KEYS, match_id="region_dependency_cluster"
    )
    strict_asset = outcome_blind_exact_match(
        rows, keys=STRICT_ASSET_CLUSTER_MATCH_KEYS, match_id="symbol_dependency_cluster"
    )
    structural_variants = (region_cluster, strict_asset)
    decision_structural = _choose_match(structural_variants)
    structural_seed_sensitivity = matching_seed_sensitivity(
        rows,
        keys=tuple(decision_structural[2]["strata"]),
        match_id=str(decision_structural[2]["match_id"]),
    )

    dependency_profile = outcome_blind_exact_match(
        rows, keys=DEPENDENCY_PROFILE_MATCH_KEYS, match_id="known_dependency_profile"
    )
    strict_dependency = outcome_blind_exact_match(
        rows, keys=STRICT_DEPENDENCY_MATCH_KEYS, match_id="strict_asset_cluster_and_dependencies"
    )
    dependency_variants = (dependency_profile, strict_dependency)
    decision_dependency = _choose_match(dependency_variants)
    dependency_seed_sensitivity = matching_seed_sensitivity(
        rows,
        keys=tuple(decision_dependency[2]["strata"]),
        match_id=str(decision_dependency[2]["match_id"]),
    )

    if progress_callback:
        progress_callback("execution", 0, len(decision_structural[0]) + len(decision_structural[1]))
    execution = execution_simulation(
        decision_structural[0],
        decision_structural[1],
        dataset_root=dataset_root,
        progress_callback=(
            (lambda done, total: progress_callback("execution", done, total))
            if progress_callback else None
        ),
    )
    treatment_summary = summarize_rows(treatment)
    control_summary = summarize_rows(control)
    structural_report = decision_structural[2]
    dependency_report = decision_dependency[2]
    geometry = _geometry_assessment(treatment_summary, control_summary)
    after = _source_snapshot(broad_path, dataset_root)
    if before != after:
        raise RuntimeError("A protected source artifact changed during the read-only review.")

    positive_years = sum(
        1
        for value in (treatment_summary.get("segments") or {}).get("year", {}).get("groups", {}).values()
        if (_number(value.get("expectancy_r")) or 0) > 0
    )
    evaluated_years = len(
        (treatment_summary.get("segments") or {}).get("year", {}).get("groups", {})
    )
    criteria = {
        "development_expectancy_positive": (_number(treatment_summary.get("expectancy_r")) or 0) > 0,
        "development_profit_factor_above_one": (_number(treatment_summary.get("profit_factor")) or 0) > 1,
        "improved_structural_match_delta_positive": (_number(structural_report.get("delta_expectancy_r")) or 0) > 0,
        "improved_structural_match_positive_across_predeclared_seeds": (
            structural_seed_sensitivity["all_replicates_positive"] is True
        ),
        "dependency_adjusted_delta_positive": (_number(dependency_report.get("delta_expectancy_r")) or 0) > 0,
        "dependency_adjusted_delta_positive_across_predeclared_seeds": (
            dependency_seed_sensitivity["all_replicates_positive"] is True
        ),
        "not_exclusively_risk_denominator": geometry["advantage_explained_exclusively_by_r_denominator"] is False,
        "conservative_execution_treatment_positive": (
            _number(execution["treatment"]["conservative"].get("expectancy_r")) or 0
        ) > 0,
        "conservative_execution_treatment_pf_above_one": (
            _number(execution["treatment"]["conservative"].get("profit_factor")) or 0
        ) > 1,
        "conservative_execution_incremental_delta_positive": (
            _number(execution.get("conservative_delta_expectancy_r")) or 0
        ) > 0,
        "raw_and_effective_n_adequate": _adequate_match(structural_report),
        "positive_in_at_least_60pct_of_years": (
            positive_years / evaluated_years >= 0.60 if evaluated_years else False
        ),
        "no_single_year_above_50pct_absolute_result_contribution": (
            (_number(
                treatment_summary["segments"]["year"].get(
                    "largest_absolute_result_contribution_share"
                )
            ) or 1) <= 0.50
        ),
        "no_disproportionate_regime_or_scope_concentration": all(
            (
                (_number(value.get("largest_absolute_result_contribution_share")) or 0)
                <= max(0.50, (_number(value.get("largest_case_share")) or 0) + 0.20)
            )
            for value in treatment_summary["segments"].values()
        ),
        "alias_not_double_counted": _alias_review(rows).get("counted_twice") is False,
    }
    report = {
        "robustness_version": ROBUSTNESS_VERSION,
        "status": "development_only_robustness_complete_pending_manual_decision",
        "hypothesis": {
            "name": "BUYER_CONFIRMATION",
            "rule": BUYER_RULE,
            "setup_scope": SETUP_SCOPE,
            "additional_filter_search": False,
            "threshold_search": False,
            "feature_combination_created": False,
        },
        "immutable_reference": {
            **fingerprints,
            "source_snapshot_before": before,
            "source_snapshot_after": after,
            "broad_v1_unchanged": True,
            "frozen_dataset_unchanged": True,
        },
        "data_access": {
            "split_read": "development",
            "setup_read": SETUP_SCOPE,
            "development_rows": len(rows),
            "validation_opened": False,
            "holdout_opened": False,
            "long_v1_opened": False,
            "broad_v1_write_connection_opened": False,
        },
        "prior_audit_verification": prior,
        "baseline": {
            "treatment": treatment_summary,
            "control": control_summary,
            "missing_feature_n": len(missing),
            "delta_expectancy_r": (
                (_number(treatment_summary.get("expectancy_r")) or 0)
                - (_number(control_summary.get("expectancy_r")) or 0)
            ),
        },
        "matching_review": {
            "legacy_description_correction": {
                "old_description": "stable_identity_hash_within_asset_market_volatility_year_strata",
                "actual_implemented_keys": list(LEGACY_MATCH_KEYS),
                "corrected_description": legacy[2]["selection"],
                "individual_asset_or_symbol_was_in_legacy_match": False,
            },
            "corrected_legacy": legacy[2],
            "improved_variants": [region_cluster[2], strict_asset[2]],
            "decision_variant": structural_report,
            "decision_variant_seed_sensitivity": structural_seed_sensitivity,
            "decision_variant_selected_using_outcomes": False,
            "selection_basis": "strictest predeclared variant passing raw/effective coverage floors; otherwise largest coverage",
        },
        "risk_geometry": {
            "treatment": treatment_summary["risk_and_entry_geometry"],
            "control": control_summary["risk_and_entry_geometry"],
            "treatment_quality": treatment_summary["risk_geometry_quality"],
            "control_quality": control_summary["risk_geometry_quality"],
            "assessment": geometry,
            "intrabar_sequence_claimed": False,
        },
        "entry_efficiency": {
            "treatment": treatment_summary["entry_efficiency"],
            "control": control_summary["entry_efficiency"],
        },
        "sensitivity_stress": sensitivity_stress(treatment),
        "execution_simulation": execution,
        "dependency_and_redundancy": {
            "alias_review": _alias_review(rows),
            "known_dependencies_only": [
                "bearish_candles_ge3",
                "pullback_depth",
                "pullback_duration",
                "relative_momentum",
                "close_location",
                "ema_trend",
                "bos_close_break",
                "volatility_regime",
                "market_phase",
            ],
            "variants": [dependency_profile[2], strict_dependency[2]],
            "decision_variant": dependency_report,
            "decision_variant_seed_sensitivity": dependency_seed_sensitivity,
            "new_feature_search": False,
            "causal_claim": False,
        },
        "time_and_regime_stability": treatment_summary["segments"],
        "false_positive_risks": {
            "predeclared_broad_hypotheses": 8,
            "overlapping_candidates": True,
            "raw_n_is_independent_n": False,
            "survivorship_complete": False,
            "point_in_time_universe_complete": False,
            "unseen_splits_remain_unseen": True,
            "semantic_alias_feature": True,
            "risk_geometry_reviewed": True,
            "execution_sensitivity_present": True,
            "naive_independent_candidate_p_values_used": False,
        },
        "hard_decision_criteria": criteria,
        "manual_decision": None,
        "challenger_created": False,
        "freeze_created": False,
        "production_changed": False,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def apply_manual_decision(
    report: Mapping[str, object],
    *,
    decision: str,
    reason: str,
    decided_at: str,
) -> dict[str, object]:
    normalized = str(decision).upper()
    if normalized not in {DECISION_KEEP_B, DECISION_C_RECOMMENDATION}:
        raise ValueError("Decision must be KEEP_B or C_RECOMMENDATION.")
    criteria = report.get("hard_decision_criteria") or {}
    failed = sorted(name for name, passed in criteria.items() if passed is not True)
    if normalized == DECISION_C_RECOMMENDATION and failed:
        raise ValueError(f"C recommendation is blocked by hard criteria: {failed}")
    result = copy.deepcopy(dict(report))
    result.pop("report_fingerprint", None)
    result["status"] = "development_only_robustness_complete"
    result["manual_decision"] = {
        "decision": normalized,
        "reason": str(reason),
        "decided_at": str(decided_at),
        "failed_hard_criteria": failed,
        "meaning": (
            "Development evidence is robust enough only to draft a later fixed challenger"
            if normalized == DECISION_C_RECOMMENDATION
            else "Keep the hypothesis at B and stop research without trying new rescue filters"
        ),
        "strategy_confirmed": False,
        "validation_passed": False,
        "production_eligible": False,
    }
    result["challenger_specification_draft"] = (
        {
            "challenger_name": "buyer-confirmation-objective-pullback-v1-draft",
            "status": "draft_not_frozen_not_started",
            "setup_scope": SETUP_SCOPE,
            "single_rule": BUYER_RULE,
            "entry_contract": BASELINE_ENTRY_POLICY,
            "stop_contract": STOP_CONTRACT,
            "exit_contract": EXIT_CONTRACT,
            "cost_contract": "stored Broad-v1 execution cost contract",
            "dataset_fingerprint": PROTECTED_DATASET_FINGERPRINT,
            "feature_contract_fingerprint": PROTECTED_FEATURE_CONTRACT_FINGERPRINT,
            "code_contract_fingerprint": PROTECTED_CODE_FINGERPRINT,
            "additional_filters": [],
            "forbidden_confluence": [
                "RSI",
                "EMA",
                "BOS",
                "bearish_candles",
                "Fibonacci",
                "volume",
                "volatility_regime",
                "market_regime",
            ],
            "validation_opened": False,
            "holdout_opened": False,
            "automatic_activation": False,
        }
        if normalized == DECISION_C_RECOMMENDATION else None
    )
    result["challenger_created"] = False
    result["freeze_created"] = False
    result["production_changed"] = False
    result["report_fingerprint"] = _fingerprint(result)
    return result


def write_append_only_json(report: Mapping[str, object], path: Path) -> dict[str, object]:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Append-only report already exists: {destination}")
    encoded = _canonical_json(report, indent=2) + "\n"
    destination.write_text(encoded, encoding="utf-8")
    return {
        "path": str(destination),
        "bytes": len(encoded.encode("utf-8")),
        "report_fingerprint": report.get("report_fingerprint"),
    }


def verify_report_fingerprint(report: Mapping[str, object]) -> bool:
    stored = report.get("report_fingerprint")
    payload = {key: value for key, value in report.items() if key != "report_fingerprint"}
    return bool(stored) and _fingerprint(payload) == stored
