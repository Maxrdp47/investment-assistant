from __future__ import annotations

"""Read-only methodology audit for the immutable first Swing Broad pass.

This module deliberately does not import or initialize the Broad writer.  It
opens the completed databases with SQLite ``mode=ro`` and writes reports only
to a separate append-only JSON artifact chosen by the caller.
"""

import copy
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


BROAD_V1_AUDIT_VERSION = "swing-broad-v1-method-audit-2026.08.25-v3"
FUTURE_REPORT_CONTRACT_VERSION = "swing-research-report-validity-2026.08.25-v2"
PROTECTED_DATASET_FINGERPRINT = (
    "e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed"
)
PROTECTED_FEATURE_CONTRACT_FINGERPRINT = (
    "c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd"
)
PROTECTED_CODE_FINGERPRINT = (
    "77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946"
)

VALIDITY_PASS = "PASS"
VALIDITY_FAIL = "FAIL"
VALIDITY_NOT_TESTABLE = "NOT_TESTABLE"
VALIDITY_EMPTY = "EMPTY"
VALIDITY_INVALID = "INVALID"
VALIDITY_UNDERPOWERED = "UNDERPOWERED"
VALIDITY_NON_DISCRIMINATING = "NON_DISCRIMINATING"

MIN_RAW_GROUP_N = 200
MIN_EFFECTIVE_GROUP_N = 100
MIN_GROUP_SHARE = 0.01

SETUP_PULLBACK = "objective_pullback"
SETUP_BREAKOUT = "objective_breakout"
ALL_SETUPS = (SETUP_PULLBACK, SETUP_BREAKOUT)
TEST_SCOPE = ("EQUITIES", "ETF", "CRYPTO")


HYPOTHESIS_CONTRACTS: dict[str, dict[str, object]] = {
    "buyer_confirmation": {
        "hypothesis_family": "entry_confirmation",
        "intended_setup_scope": (SETUP_PULLBACK,),
        "source_scope": ("GENERAL_METHOD",),
        "feature_path": "pullback.buyer_confirmation_close_above_prior_high",
        "original_direction": "buyer confirmation should improve the pullback entry",
    },
    "three_or_more_bearish_candles": {
        "hypothesis_family": "pullback_geometry",
        "intended_setup_scope": (SETUP_PULLBACK,),
        "source_scope": ("GENERAL_METHOD",),
        "feature_path": "pullback.bearish_candles",
        "original_direction": "three bearish pullback candles imply no trade",
        "post_hoc_direction_reversal": True,
    },
    "fibonacci_0618_0786": {
        "hypothesis_family": "pullback_depth",
        "intended_setup_scope": (SETUP_PULLBACK,),
        "source_scope": ("LEGACY_SOURCE_SCOPE_NOT_RECORDED",),
        "feature_path": "fibonacci.retracement_depth",
        "required_controls": (
            "continuous_pullback_depth",
            "equal_width_lower_0450_0618",
            "equal_width_upper_0786_0954",
        ),
    },
    "ema20_above_ema50": {
        "hypothesis_family": "trend_momentum",
        "intended_setup_scope": ALL_SETUPS,
        "source_scope": ("GENERAL_METHOD",),
        "feature_path": "technical.ema20_relative_to_ema50",
    },
    "rsi_40_70": {
        "hypothesis_family": "trend_momentum",
        "intended_setup_scope": ALL_SETUPS,
        "source_scope": ("GENERAL_METHOD",),
        "feature_path": "technical.rsi_14",
    },
    "bos_close_break": {
        "hypothesis_family": "market_structure",
        "intended_setup_scope": (SETUP_BREAKOUT,),
        "source_scope": ("GENERAL_METHOD",),
        "feature_path": "market_structure.close_break",
    },
    "opening_level_contact": {
        "hypothesis_family": "opening_levels",
        "intended_setup_scope": ALL_SETUPS,
        "source_scope": ("GENERAL_METHOD",),
        "feature_path": "opening_levels.*.contact",
    },
    "cot_available": {
        "hypothesis_family": "external_positioning",
        "intended_setup_scope": ALL_SETUPS,
        "source_scope": ("FUTURES",),
        "feature_path": "cot.status",
        "cross_market_transfer_allowed": False,
    },
}

PARAMETER_NEIGHBORHOODS: tuple[tuple[str, str, float], ...] = (
    ("rsi_lower_bound", "rsi_35_70", 35.0),
    ("rsi_lower_bound", "rsi_40_70", 40.0),
    ("rsi_lower_bound", "rsi_45_70", 45.0),
    ("ema20_to_ema50", "ema_ratio_0_995", 0.995),
    ("ema20_to_ema50", "ema_ratio_1_000", 1.0),
    ("ema20_to_ema50", "ema_ratio_1_005", 1.005),
    ("bos_excess_atr", "bos_excess_0_0", 0.0),
    ("bos_excess_atr", "bos_excess_0_1", 0.1),
    ("bos_excess_atr", "bos_excess_0_2", 0.2),
)

METRIC_SEMANTICS: dict[str, object] = {
    "candidate_sequence_drawdown": "chronological cumulative R over overlapping Broad candidates",
    "trade_strategy_drawdown": "not computed in this audit",
    "portfolio_simulation_drawdown": "not computed in Broad-v1",
    "win_rate_and_profit_factor_basis": "evaluated Broad candidates using the fixed pullback-low-plus-ATR-buffer/2R counterfactual",
    "raw_n_basis": "candidate observations",
    "effective_n_basis": "distinct stored dependency_cluster values",
    "portfolio_claim_allowed": False,
}


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


def _json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(
        _clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        allow_nan=False,
        indent=indent,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _counted_median(values: Mapping[float, int]) -> float | None:
    total = sum(int(count) for count in values.values())
    if total <= 0:
        return None
    left_rank = (total - 1) // 2
    right_rank = total // 2
    cumulative = 0
    left = right = None
    for value, count in sorted(values.items()):
        next_cumulative = cumulative + int(count)
        if left is None and left_rank < next_cumulative:
            left = float(value)
        if right_rank < next_cumulative:
            right = float(value)
            break
        cumulative = next_cumulative
    return (float(left) + float(right)) / 2 if left is not None and right is not None else None


def _read_only_connection(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    connection = sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def validity_gate(
    *,
    universe_n: int,
    applicable_n: int,
    valid_n: int,
    structurally_not_applicable_n: int,
    missing_n: int,
    treatment_n: int,
    control_n: int,
    treatment_effective_n: int,
    control_effective_n: int,
    feature_point_in_time_available: bool,
    outcome_independent_definition: bool,
    market_scope_correct: bool,
    setup_scope_correct: bool,
    structural_missingness_treated_as_false: bool,
    min_raw_group_n: int = MIN_RAW_GROUP_N,
    min_effective_group_n: int = MIN_EFFECTIVE_GROUP_N,
    min_group_share: float = MIN_GROUP_SHARE,
) -> dict[str, object]:
    """Fail closed before any A/B/C performance interpretation."""
    counts = {
        "universe_n": int(universe_n),
        "applicable_n": int(applicable_n),
        "valid_n": int(valid_n),
        "structurally_not_applicable_n": int(structurally_not_applicable_n),
        "missing_n": int(missing_n),
        "treatment_n": int(treatment_n),
        "control_n": int(control_n),
        "treatment_effective_n": int(treatment_effective_n),
        "control_effective_n": int(control_effective_n),
    }
    common = {
        "contract_version": FUTURE_REPORT_CONTRACT_VERSION,
        **counts,
        "structural_missingness_is_false": False,
        "performance_grade_allowed": False,
    }
    if universe_n <= 0 or applicable_n <= 0:
        return {**common, "status": VALIDITY_EMPTY, "reason": "No applicable hypothesis universe."}
    if not feature_point_in_time_available or valid_n <= 0:
        return {
            **common,
            "status": VALIDITY_NOT_TESTABLE,
            "reason": "No point-in-time evaluable feature cases are available.",
        }
    if (
        not outcome_independent_definition
        or not market_scope_correct
        or not setup_scope_correct
        or structural_missingness_treated_as_false
        or valid_n != treatment_n + control_n
        or applicable_n != valid_n + missing_n
        or universe_n != applicable_n + structurally_not_applicable_n
    ):
        return {
            **common,
            "status": VALIDITY_INVALID,
            "reason": "Applicability, scope, missingness, or outcome-independence contract is invalid.",
        }
    if treatment_n <= 0 or control_n <= 0:
        return {
            **common,
            "status": VALIDITY_NON_DISCRIMINATING,
            "reason": "Treatment or control is empty.",
        }
    smaller_share = min(treatment_n, control_n) / valid_n if valid_n else 0.0
    if smaller_share < float(min_group_share):
        return {
            **common,
            "status": VALIDITY_NON_DISCRIMINATING,
            "smaller_group_share": smaller_share,
            "reason": "The condition is almost always or almost never true.",
        }
    if (
        treatment_n < min_raw_group_n
        or control_n < min_raw_group_n
        or treatment_effective_n < min_effective_group_n
        or control_effective_n < min_effective_group_n
    ):
        return {
            **common,
            "status": VALIDITY_UNDERPOWERED,
            "smaller_group_share": smaller_share,
            "reason": "Raw or effective comparison evidence is underpowered.",
        }
    return {
        **common,
        "status": VALIDITY_PASS,
        "smaller_group_share": smaller_share,
        "performance_grade_allowed": True,
        "reason": "Applicability, treatment/control, scope, PIT, and power gates passed.",
    }


@dataclass
class _BasicStats:
    cases: int = 0
    evaluated: int = 0
    sum_r: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    wins: int = 0
    mfe_pct_sum: float = 0.0
    mfe_pct_n: int = 0
    mae_pct_sum: float = 0.0
    mae_pct_n: int = 0
    mfe_r_sum: float = 0.0
    mfe_r_n: int = 0
    mae_r_sum: float = 0.0
    mae_r_n: int = 0
    giveback_r_sum: float = 0.0
    giveback_r_n: int = 0
    time_to_mfe: dict[float, int] = field(default_factory=lambda: defaultdict(int))
    time_to_exit: dict[float, int] = field(default_factory=lambda: defaultdict(int))

    def update(self, row: Mapping[str, object]) -> None:
        self.cases += 1
        result_r = _number(row.get("result_r"))
        if result_r is not None:
            self.evaluated += 1
            self.sum_r += result_r
            if result_r > 0:
                self.wins += 1
                self.gross_profit += result_r
            else:
                self.gross_loss += abs(result_r)
        for key, total, count in (
            ("mfe_pct", "mfe_pct_sum", "mfe_pct_n"),
            ("mae_pct", "mae_pct_sum", "mae_pct_n"),
            ("mfe_r", "mfe_r_sum", "mfe_r_n"),
            ("mae_r", "mae_r_sum", "mae_r_n"),
        ):
            value = _number(row.get(key))
            if value is not None:
                setattr(self, total, float(getattr(self, total)) + value)
                setattr(self, count, int(getattr(self, count)) + 1)
        mfe_r = _number(row.get("mfe_r"))
        if mfe_r is not None and result_r is not None:
            self.giveback_r_sum += mfe_r - result_r
            self.giveback_r_n += 1
        for key, target in (("time_to_mfe", self.time_to_mfe), ("time_to_exit", self.time_to_exit)):
            value = _number(row.get(key))
            if value is not None:
                target[value] += 1

    def result(self) -> dict[str, object]:
        return {
            "raw_candidate_n": self.cases,
            "evaluated_candidate_n": self.evaluated,
            "candidate_expectancy_r": self.sum_r / self.evaluated if self.evaluated else None,
            "candidate_profit_factor": (
                self.gross_profit / self.gross_loss if self.gross_loss > 0 else None
            ),
            "candidate_win_rate_pct": self.wins / self.evaluated * 100 if self.evaluated else None,
            "candidate_total_r": self.sum_r,
            "average_mfe_pct": self.mfe_pct_sum / self.mfe_pct_n if self.mfe_pct_n else None,
            "average_mae_pct": self.mae_pct_sum / self.mae_pct_n if self.mae_pct_n else None,
            "average_mfe_r": self.mfe_r_sum / self.mfe_r_n if self.mfe_r_n else None,
            "average_mae_r": self.mae_r_sum / self.mae_r_n if self.mae_r_n else None,
            "average_giveback_r": (
                self.giveback_r_sum / self.giveback_r_n if self.giveback_r_n else None
            ),
            "median_sessions_to_mfe": _counted_median(self.time_to_mfe),
            "median_sessions_to_exit": _counted_median(self.time_to_exit),
        }


@dataclass
class _Stats:
    basic: _BasicStats = field(default_factory=_BasicStats)
    dependency_clusters: set[str] = field(default_factory=set)
    cumulative_r: float = 0.0
    peak_r: float = 0.0
    maximum_drawdown_r: float = 0.0
    loss_streak: int = 0
    maximum_loss_streak: int = 0
    segments: dict[str, dict[str, _BasicStats]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    stress: dict[str, _BasicStats] = field(
        default_factory=lambda: {
            "base": _BasicStats(),
            "elevated_slippage": _BasicStats(),
            "adverse_entry": _BasicStats(),
            "higher_total_cost": _BasicStats(),
            "conservative_gap_stop": _BasicStats(),
        }
    )

    def update(self, row: Mapping[str, object]) -> None:
        self.basic.update(row)
        cluster = str(row.get("dependency_cluster") or "")
        if cluster:
            self.dependency_clusters.add(cluster)
        result_r = _number(row.get("result_r"))
        if result_r is not None:
            self.cumulative_r += result_r
            self.peak_r = max(self.peak_r, self.cumulative_r)
            self.maximum_drawdown_r = max(
                self.maximum_drawdown_r, self.peak_r - self.cumulative_r
            )
            self.loss_streak = self.loss_streak + 1 if result_r <= 0 else 0
            self.maximum_loss_streak = max(self.maximum_loss_streak, self.loss_streak)
        dimensions = {
            "year": str(row.get("signal_day") or "")[:4] or "unknown",
            "setup": str(row.get("setup_family") or "unknown"),
            "asset_type": str(row.get("asset_type") or "unknown"),
            "region": str(row.get("region") or "unknown"),
            "market_phase": str(row.get("market_phase") or "unknown"),
            "volatility_regime": str(row.get("volatility_regime") or "unknown"),
        }
        for dimension, value in dimensions.items():
            bucket = self.segments[dimension].get(value)
            if bucket is None:
                bucket = self.segments[dimension][value] = _BasicStats()
            bucket.update(row)
        penalties = {
            "base": 0.0,
            "elevated_slippage": 0.05,
            "adverse_entry": 0.10,
            "higher_total_cost": 0.15,
            "conservative_gap_stop": 0.25 if bool(row.get("gap_affected")) else 0.0,
        }
        for scenario, penalty in penalties.items():
            stressed = dict(row)
            stressed["result_r"] = result_r - penalty if result_r is not None else None
            self.stress[scenario].update(stressed)

    def result(self) -> dict[str, object]:
        segment_results = {
            dimension: {name: stats.result() for name, stats in sorted(groups.items())}
            for dimension, groups in sorted(self.segments.items())
        }
        years = segment_results.get("year", {})
        ordered_years = sorted(years)
        rolling: dict[str, list[dict[str, object]]] = {"2_observed_years": [], "3_observed_years": []}
        for width in (2, 3):
            for start in range(0, max(len(ordered_years) - width + 1, 0)):
                names = ordered_years[start : start + width]
                evaluated = sum(int(years[name]["evaluated_candidate_n"]) for name in names)
                weighted = sum(
                    float(years[name]["candidate_expectancy_r"] or 0)
                    * int(years[name]["evaluated_candidate_n"])
                    for name in names
                )
                rolling[f"{width}_observed_years"].append(
                    {
                        "window": names,
                        "candidate_expectancy_r": weighted / evaluated if evaluated else None,
                        "evaluated_candidate_n": evaluated,
                        "calendar_continuity_claimed": False,
                    }
                )
        base = self.basic.result()
        positive_years = sum(
            1 for value in years.values() if (_number(value.get("candidate_expectancy_r")) or 0) > 0
        )
        concentration = {}
        for dimension, groups in segment_results.items():
            total_cases = sum(int(value["raw_candidate_n"]) for value in groups.values())
            absolute_result = sum(abs(float(value["candidate_total_r"])) for value in groups.values())
            largest_cases = max(groups, key=lambda name: int(groups[name]["raw_candidate_n"])) if groups else None
            largest_result = max(groups, key=lambda name: abs(float(groups[name]["candidate_total_r"]))) if groups else None
            concentration[dimension] = {
                "largest_case_group": largest_cases,
                "largest_case_share": (
                    int(groups[largest_cases]["raw_candidate_n"]) / total_cases
                    if largest_cases is not None and total_cases else None
                ),
                "largest_absolute_result_group": largest_result,
                "largest_absolute_result_contribution_share": (
                    abs(float(groups[largest_result]["candidate_total_r"])) / absolute_result
                    if largest_result is not None and absolute_result > 0 else None
                ),
                "natural_sample_weights_preserved": True,
            }
        return {
            **base,
            "effective_dependency_cluster_n": len(self.dependency_clusters),
            "candidate_sequence_drawdown_r": self.maximum_drawdown_r,
            "candidate_sequence_maximum_loss_streak": self.maximum_loss_streak,
            "candidate_sequence_is_portfolio_simulation": False,
            "segments": segment_results,
            "segment_concentration": concentration,
            "time_stability": {
                "evaluated_years": len(years),
                "positive_expectancy_years": positive_years,
                "positive_expectancy_year_share_pct": (
                    positive_years / len(years) * 100 if years else None
                ),
                "by_year": years,
                "rolling_observed_year_windows": rolling,
            },
            "execution_stress": {
                "historical_results_rewritten": False,
                "predeclared_penalties_r": {
                    "base": 0.0,
                    "elevated_slippage": 0.05,
                    "adverse_entry": 0.10,
                    "higher_total_cost": 0.15,
                    "conservative_gap_stop": 0.25,
                },
                "scenarios": {name: value.result() for name, value in self.stress.items()},
            },
        }


@dataclass
class _PlateauStats:
    cases: int = 0
    evaluated: int = 0
    sum_r: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    wins: int = 0
    dependency_clusters: set[str] = field(default_factory=set)
    cumulative_r: float = 0.0
    peak_r: float = 0.0
    maximum_drawdown_r: float = 0.0

    def update(self, row: Mapping[str, object]) -> None:
        self.cases += 1
        cluster = str(row.get("dependency_cluster") or "")
        if cluster:
            self.dependency_clusters.add(cluster)
        result_r = _number(row.get("result_r"))
        if result_r is None:
            return
        self.evaluated += 1
        self.sum_r += result_r
        if result_r > 0:
            self.wins += 1
            self.gross_profit += result_r
        else:
            self.gross_loss += abs(result_r)
        self.cumulative_r += result_r
        self.peak_r = max(self.peak_r, self.cumulative_r)
        self.maximum_drawdown_r = max(
            self.maximum_drawdown_r, self.peak_r - self.cumulative_r
        )

    def result(self) -> dict[str, object]:
        return {
            "raw_candidate_n": self.cases,
            "evaluated_candidate_n": self.evaluated,
            "effective_dependency_cluster_n": len(self.dependency_clusters),
            "candidate_expectancy_r": self.sum_r / self.evaluated if self.evaluated else None,
            "candidate_profit_factor": (
                self.gross_profit / self.gross_loss if self.gross_loss > 0 else None
            ),
            "candidate_win_rate_pct": self.wins / self.evaluated * 100 if self.evaluated else None,
            "candidate_sequence_drawdown_r": self.maximum_drawdown_r,
            "candidate_sequence_is_portfolio_simulation": False,
        }


def _applicable_and_valid(row: Mapping[str, object], hypothesis_id: str) -> tuple[bool, bool]:
    setup = str(row.get("setup_family") or "")
    intended = set(HYPOTHESIS_CONTRACTS[hypothesis_id]["intended_setup_scope"])
    if setup not in intended:
        return False, False
    if hypothesis_id == "buyer_confirmation":
        return True, row.get("buyer_confirmation") is not None and row.get("pullback_status") == "available"
    if hypothesis_id == "three_or_more_bearish_candles":
        return True, _number(row.get("bearish_candles")) is not None and row.get("pullback_status") == "available"
    if hypothesis_id == "fibonacci_0618_0786":
        return True, _number(row.get("pullback_depth")) is not None and row.get("pullback_status") == "available"
    if hypothesis_id == "ema20_above_ema50":
        return True, _number(row.get("ema_ratio")) is not None
    if hypothesis_id == "rsi_40_70":
        return True, _number(row.get("rsi_14")) is not None
    if hypothesis_id == "bos_close_break":
        return True, row.get("bos_close_break") is not None
    if hypothesis_id == "opening_level_contact":
        return True, any(value is not None for value in row.get("opening_contacts", ()))
    if hypothesis_id == "cot_available":
        return True, str(row.get("cot_status") or "") == "available"
    raise KeyError(hypothesis_id)


def _selected(row: Mapping[str, object], hypothesis_id: str) -> bool:
    if hypothesis_id == "buyer_confirmation":
        return bool(row.get("buyer_confirmation"))
    if hypothesis_id == "three_or_more_bearish_candles":
        return float(row["bearish_candles"]) >= 3
    if hypothesis_id == "fibonacci_0618_0786":
        depth = float(row["pullback_depth"])
        return 0.618 <= depth <= 0.786
    if hypothesis_id == "ema20_above_ema50":
        return float(row["ema_ratio"]) > 1.0
    if hypothesis_id == "rsi_40_70":
        return 40 <= float(row["rsi_14"]) <= 70
    if hypothesis_id == "bos_close_break":
        return bool(row.get("bos_close_break"))
    if hypothesis_id == "opening_level_contact":
        return any(bool(value) for value in row.get("opening_contacts", ()))
    if hypothesis_id == "cot_available":
        return str(row.get("cot_status") or "") == "available"
    raise KeyError(hypothesis_id)


def _depth_bin(value: object) -> str:
    number = _number(value)
    if number is None:
        return "missing"
    if number < 0.450:
        return "below_0450"
    if number < 0.618:
        return "equal_width_lower_0450_0618"
    if number <= 0.786:
        return "fib_0618_0786"
    if number <= 0.954:
        return "equal_width_upper_0786_0954"
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


def _record_from_sql(row: sqlite3.Row) -> dict[str, object]:
    entry = _number(row["entry_after_costs"])
    stop = _number(row["stop"])
    risk = entry - stop if entry is not None and stop is not None else None
    mfe_pct = _number(row["mfe_pct"])
    mae_pct = _number(row["mae_pct"])
    mfe_r = mfe_pct / 100 * entry / risk if mfe_pct is not None and entry and risk and risk > 0 else None
    mae_r = mae_pct / 100 * entry / risk if mae_pct is not None and entry and risk and risk > 0 else None
    contacts = tuple(row[name] for name in ("daily_contact", "weekly_contact", "monthly_contact", "quarterly_contact", "yearly_contact"))
    return {
        "candidate_id": row["candidate_id"],
        "symbol": row["symbol"],
        "signal_day": row["signal_day"],
        "setup_family": row["setup_family"],
        "dependency_cluster": row["dependency_cluster"],
        "asset_type": row["asset_type"],
        "region": row["region"],
        "market_phase": row["market_phase"],
        "volatility_regime": row["volatility_regime"],
        "pullback_status": row["pullback_status"],
        "buyer_confirmation": None if row["buyer_confirmation_type"] is None else bool(row["buyer_confirmation"]),
        "candle_close_above_prior_high": None if row["candle_confirmation_type"] is None else bool(row["candle_confirmation"]),
        "bearish_candles": _number(row["bearish_candles"]),
        "pullback_depth": _number(row["pullback_depth"]),
        "pullback_duration": _number(row["pullback_duration"]),
        "fib_zone": row["fib_zone"],
        "fib_extensions_tested": bool(row["fib_extensions_tested"]),
        "ema_ratio": _number(row["ema_ratio"]),
        "ema20_slope": _number(row["ema20_slope"]),
        "rsi_14": _number(row["rsi_14"]),
        "bos_close_break": None if row["bos_type"] is None else bool(row["bos_close_break"]),
        "bos_excess_atr": _number(row["bos_excess_atr"]),
        "opening_contacts": contacts,
        "cot_status": row["cot_status"],
        "relative_momentum20": _number(row["relative_momentum20"]),
        "close_location": _number(row["close_location"]),
        "range_volume_expansion": None if row["range_volume_type"] is None else bool(row["range_volume_expansion"]),
        "result_r": _number(row["result_r"]),
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "time_to_mfe": _number(row["time_to_mfe"]),
        "time_to_exit": _number(row["time_to_exit"]),
        "gap_affected": int(row["gap_count"] or 0) > 0,
    }


DEVELOPMENT_QUERY = """SELECT
 c.candidate_id, c.symbol, c.signal_day, c.setup_family, c.dependency_cluster,
 json_extract(c.feature_json, '$.asset.asset_type') asset_type,
 json_extract(c.feature_json, '$.asset.region') region,
 json_extract(c.feature_json, '$.technical.market_phase') market_phase,
 json_extract(c.feature_json, '$.technical.volatility_regime') volatility_regime,
 json_extract(c.feature_json, '$.pullback.status') pullback_status,
 json_type(c.feature_json, '$.pullback.buyer_confirmation_close_above_prior_high') buyer_confirmation_type,
 json_extract(c.feature_json, '$.pullback.buyer_confirmation_close_above_prior_high') buyer_confirmation,
 json_type(c.feature_json, '$.candle_quality.close_above_prior_high') candle_confirmation_type,
 json_extract(c.feature_json, '$.candle_quality.close_above_prior_high') candle_confirmation,
 json_extract(c.feature_json, '$.pullback.bearish_candles') bearish_candles,
 json_extract(c.feature_json, '$.pullback.pullback_depth') pullback_depth,
 json_extract(c.feature_json, '$.pullback.pullback_duration_sessions') pullback_duration,
 json_extract(c.feature_json, '$.fibonacci.comparison_zone') fib_zone,
 json_extract(c.feature_json, '$.fibonacci.extensions_tested') fib_extensions_tested,
 json_extract(c.feature_json, '$.technical.ema20_relative_to_ema50') ema_ratio,
 json_extract(c.feature_json, '$.trend_quality.ema20_slope_atr_per_session') ema20_slope,
 json_extract(c.feature_json, '$.technical.rsi_14') rsi_14,
 json_type(c.feature_json, '$.market_structure.close_break') bos_type,
 json_extract(c.feature_json, '$.market_structure.close_break') bos_close_break,
 json_extract(c.feature_json, '$.market_structure.close_break_excess_atr') bos_excess_atr,
 json_extract(c.feature_json, '$.opening_levels.daily.contact') daily_contact,
 json_extract(c.feature_json, '$.opening_levels.weekly.contact') weekly_contact,
 json_extract(c.feature_json, '$.opening_levels.monthly.contact') monthly_contact,
 json_extract(c.feature_json, '$.opening_levels.quarterly.contact') quarterly_contact,
 json_extract(c.feature_json, '$.opening_levels.yearly.contact') yearly_contact,
 json_extract(c.feature_json, '$.cot.status') cot_status,
 json_extract(c.feature_json, '$.relative_strength.relative_momentum_20d') relative_momentum20,
 json_extract(c.feature_json, '$.candle_quality.close_position_in_range') close_location,
 json_type(c.feature_json, '$.candle_quality.range_and_volume_expansion') range_volume_type,
 json_extract(c.feature_json, '$.candle_quality.range_and_volume_expansion') range_volume_expansion,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.exits.fixed_2r.result_r') result_r,
 json_extract(e.experiment_json, '$.entry_after_costs') entry_after_costs,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.stop') stop,
 json_extract(l.label_json, '$.mfe_pct') mfe_pct,
 json_extract(l.label_json, '$.mae_pct') mae_pct,
 json_extract(l.label_json, '$.time_to_mfe_sessions') time_to_mfe,
 json_extract(l.label_json, '$.time_to_exit_sessions') time_to_exit,
 json_array_length(l.label_json, '$.gap_events') gap_count
 FROM broad_research_candidates c
 JOIN broad_research_labels l USING(candidate_id)
 JOIN broad_research_counterfactuals e USING(candidate_id)
 WHERE c.research_split='development'
 ORDER BY c.signal_day, c.candidate_id"""


def _automatic_performance_grade(gate: Mapping[str, object], selected: Mapping[str, object], control: Mapping[str, object]) -> str | None:
    """Automatically close negatives at A; positives remain B pending manual review."""
    if gate.get("performance_grade_allowed") is not True:
        return None
    selected_r = _number(selected.get("candidate_expectancy_r"))
    control_r = _number(control.get("candidate_expectancy_r"))
    if selected_r is None or control_r is None:
        return None
    return "A" if selected_r <= 0 or selected_r <= control_r else "B"


def _stable_hash(row: Mapping[str, object], seed: str) -> str:
    value = f"{seed}|{row.get('candidate_id')}|{row.get('signal_day')}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _matched_placebo(rows: Sequence[Mapping[str, object]], hypothesis_id: str) -> dict[str, object]:
    groups: dict[tuple[str, ...], dict[bool, list[Mapping[str, object]]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    for row in rows:
        applicable, valid = _applicable_and_valid(row, hypothesis_id)
        if not applicable or not valid:
            continue
        stratum = (
            str(row.get("asset_type") or "unknown"),
            str(row.get("market_phase") or "unknown"),
            str(row.get("volatility_regime") or "unknown"),
            str(row.get("signal_day") or "")[:4],
        )
        groups[stratum][_selected(row, hypothesis_id)].append(row)
    selected_rows: list[Mapping[str, object]] = []
    control_rows: list[Mapping[str, object]] = []
    unmatched_strata = 0
    for stratum, pair in groups.items():
        size = min(len(pair[True]), len(pair[False]))
        if size <= 0:
            unmatched_strata += 1
            continue
        seed = f"{BROAD_V1_AUDIT_VERSION}|{hypothesis_id}|{'|'.join(stratum)}"
        selected_rows.extend(sorted(pair[True], key=lambda row: _stable_hash(row, seed))[:size])
        control_rows.extend(sorted(pair[False], key=lambda row: _stable_hash(row, seed))[:size])
    selected_stats, control_stats = _Stats(), _Stats()
    for row in sorted(selected_rows, key=lambda item: (str(item.get("signal_day")), str(item.get("candidate_id")))):
        selected_stats.update(row)
    for row in sorted(control_rows, key=lambda item: (str(item.get("signal_day")), str(item.get("candidate_id")))):
        control_stats.update(row)
    selected_result, control_result = selected_stats.result(), control_stats.result()
    selected_r = _number(selected_result.get("candidate_expectancy_r"))
    control_r = _number(control_result.get("candidate_expectancy_r"))
    return {
        "selection": "stable_identity_hash_within_asset_market_volatility_year_strata",
        "selection_uses_outcomes": False,
        "point_in_time_features_only": True,
        "matched_treatment_n": len(selected_rows),
        "matched_control_n": len(control_rows),
        "unmatched_strata": unmatched_strata,
        "treatment": selected_result,
        "control": control_result,
        "delta_candidate_expectancy_r": (
            selected_r - control_r if selected_r is not None and control_r is not None else None
        ),
        "placebo_is_strategy": False,
    }


def _pearson(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    xs, ys = zip(*pairs)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    xx = sum((value - mx) ** 2 for value in xs)
    yy = sum((value - my) ** 2 for value in ys)
    if xx <= 0 or yy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / math.sqrt(xx * yy)


def _dependency_review(rows: Sequence[Mapping[str, object]], hypothesis_id: str) -> dict[str, object]:
    feature = [(row, 1.0 if _selected(row, hypothesis_id) else 0.0) for row in rows]
    if hypothesis_id == "buyer_confirmation":
        proxy_values = {
            "candle_close_above_prior_high": lambda row: 1.0 if row.get("candle_close_above_prior_high") else 0.0,
            "relative_momentum_20d": lambda row: _number(row.get("relative_momentum20")),
            "close_location": lambda row: _number(row.get("close_location")),
            "bos_close_break": lambda row: 1.0 if row.get("bos_close_break") else 0.0,
            "ema_trend": lambda row: 1.0 if (_number(row.get("ema_ratio")) or 0) > 1 and (_number(row.get("ema20_slope")) or 0) > 0 else 0.0,
            "pullback_depth": lambda row: _number(row.get("pullback_depth")),
            "three_or_more_bearish_candles": lambda row: 1.0 if (_number(row.get("bearish_candles")) or 0) >= 3 else 0.0,
        }
        adjustment_keys = (
            "year", "market_phase", "volatility_regime", "momentum_sign", "close_location_bin",
            "bos_close_break", "ema_trend", "pullback_depth_bin", "bearish_ge3",
        )
    else:
        proxy_values = {
            "buyer_confirmation": lambda row: 1.0 if row.get("buyer_confirmation") else 0.0,
            "pullback_depth": lambda row: _number(row.get("pullback_depth")),
            "pullback_duration": lambda row: _number(row.get("pullback_duration")),
            "relative_momentum_20d": lambda row: _number(row.get("relative_momentum20")),
            "close_location": lambda row: _number(row.get("close_location")),
            "ema_trend": lambda row: 1.0 if (_number(row.get("ema_ratio")) or 0) > 1 and (_number(row.get("ema20_slope")) or 0) > 0 else 0.0,
        }
        adjustment_keys = (
            "year", "market_phase", "volatility_regime", "momentum_sign", "close_location_bin",
            "ema_trend", "pullback_depth_bin", "duration_bin", "buyer_confirmation",
        )
    correlations = {}
    for name, getter in proxy_values.items():
        pairs = []
        for row, selected in feature:
            value = getter(row)
            if value is not None:
                pairs.append((selected, float(value)))
        correlations[name] = {"pearson_or_point_biserial": _pearson(pairs), "n": len(pairs)}
    mismatches = sum(
        1
        for row, _ in feature
        if row.get("buyer_confirmation") is not None
        and row.get("candle_close_above_prior_high") is not None
        and bool(row.get("buyer_confirmation")) != bool(row.get("candle_close_above_prior_high"))
    )
    strata: dict[tuple[str, ...], dict[bool, list[float]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    for row, _ in feature:
        result = _number(row.get("result_r"))
        if result is None:
            continue
        values = {
            "year": str(row.get("signal_day") or "")[:4],
            "market_phase": str(row.get("market_phase") or "unknown"),
            "volatility_regime": str(row.get("volatility_regime") or "unknown"),
            "momentum_sign": "positive" if (_number(row.get("relative_momentum20")) or 0) > 0 else "non_positive",
            "close_location_bin": _close_location_bin(row.get("close_location")),
            "bos_close_break": str(bool(row.get("bos_close_break"))),
            "ema_trend": str((_number(row.get("ema_ratio")) or 0) > 1 and (_number(row.get("ema20_slope")) or 0) > 0),
            "pullback_depth_bin": _depth_bin(row.get("pullback_depth")),
            "bearish_ge3": str((_number(row.get("bearish_candles")) or 0) >= 3),
            "duration_bin": _duration_bin(row.get("pullback_duration")),
            "buyer_confirmation": str(bool(row.get("buyer_confirmation"))),
        }
        key = tuple(values[name] for name in adjustment_keys)
        strata[key][_selected(row, hypothesis_id)].append(result)
    treatment_sum = control_sum = 0.0
    matched_n = 0
    matched_strata = 0
    for pair in strata.values():
        size = min(len(pair[True]), len(pair[False]))
        if size <= 0:
            continue
        matched_strata += 1
        treatment_sum += sum(pair[True]) / len(pair[True]) * size
        control_sum += sum(pair[False]) / len(pair[False]) * size
        matched_n += size
    return {
        "correlations_are_not_independent_confirmations": True,
        "feature_proxy_correlations": correlations,
        "buyer_confirmation_alias_check": {
            "compared_n": len(feature),
            "mismatches": mismatches,
            "semantic_duplicate": hypothesis_id == "buyer_confirmation" and mismatches == 0,
        },
        "descriptive_dependency_adjustment": {
            "controls": list(adjustment_keys),
            "matched_strata": matched_strata,
            "matched_per_group_n": matched_n,
            "treatment_expectancy_r": treatment_sum / matched_n if matched_n else None,
            "control_expectancy_r": control_sum / matched_n if matched_n else None,
            "incremental_expectancy_r": (
                (treatment_sum - control_sum) / matched_n if matched_n else None
            ),
            "causal_or_strategy_claim": False,
        },
        "automatic_feature_combination": False,
    }


def _fib_review(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    zones = {
        "fib_0618_0786": _Stats(),
        "equal_width_lower_0450_0618": _Stats(),
        "equal_width_upper_0786_0954": _Stats(),
    }
    evaluated: list[tuple[float, float, str, Mapping[str, object]]] = []
    extensions_true = 0
    for row in rows:
        depth = _number(row.get("pullback_depth"))
        result = _number(row.get("result_r"))
        if bool(row.get("fib_extensions_tested")):
            extensions_true += 1
        if depth is None:
            continue
        zone = _depth_bin(depth)
        if zone in zones:
            zones[zone].update(row)
        if result is not None:
            evaluated.append((depth, result, zone, row))
    n = len(evaluated)
    sx = sum(row[0] for row in evaluated)
    sy = sum(row[1] for row in evaluated)
    sxx = sum(row[0] ** 2 for row in evaluated)
    sxy = sum(row[0] * row[1] for row in evaluated)
    syy = sum(row[1] ** 2 for row in evaluated)
    denominator = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denominator if n and denominator else None
    intercept = (sy - slope * sx) / n if n and slope is not None else None
    total_y = syy - sy * sy / n if n else 0.0
    explained = slope * (sxy - sx * sy / n) if slope is not None and n else 0.0
    residuals: dict[str, list[float]] = defaultdict(list)
    if slope is not None and intercept is not None:
        for depth, result, zone, _ in evaluated:
            if zone in zones:
                residuals[zone].append(result - (intercept + slope * depth))
    results = {name: stats.result() for name, stats in zones.items()}
    treatment_r = _number(results["fib_0618_0786"].get("candidate_expectancy_r"))
    controls = [
        _number(results[name].get("candidate_expectancy_r"))
        for name in ("equal_width_lower_0450_0618", "equal_width_upper_0786_0954")
    ]
    known_controls = [value for value in controls if value is not None]
    treatment_residual = (
        sum(residuals["fib_0618_0786"]) / len(residuals["fib_0618_0786"])
        if residuals["fib_0618_0786"] else None
    )
    control_residual_values = residuals["equal_width_lower_0450_0618"] + residuals["equal_width_upper_0786_0954"]
    control_residual = (
        sum(control_residual_values) / len(control_residual_values)
        if control_residual_values else None
    )
    return {
        "setup_scope": (SETUP_PULLBACK,),
        "same_setup_entry_cost_label_contract": True,
        "zones": results,
        "zone_widths": {
            "fib_0618_0786": 0.786 - 0.618,
            "equal_width_lower_0450_0618": 0.618 - 0.450,
            "equal_width_upper_0786_0954": 0.954 - 0.786,
            "all_equal": math.isclose(0.786 - 0.618, 0.618 - 0.450)
            and math.isclose(0.786 - 0.618, 0.954 - 0.786),
        },
        "continuous_pullback_depth": {
            "model": "single_predeclared_linear_explanatory_variable",
            "n": n,
            "slope_expectancy_r_per_depth_unit": slope,
            "intercept": intercept,
            "r_squared": explained / total_y if total_y > 0 else None,
            "threshold_or_zone_optimization": False,
        },
        "incremental_specific_effect": {
            "raw_delta_vs_mean_equal_width_controls": (
                treatment_r - sum(known_controls) / len(known_controls)
                if treatment_r is not None and known_controls else None
            ),
            "depth_linear_residual_treatment": treatment_residual,
            "depth_linear_residual_equal_width_controls": control_residual,
            "residual_delta": (
                treatment_residual - control_residual
                if treatment_residual is not None and control_residual is not None else None
            ),
            "development_hint_only": True,
        },
        "extensions_tested_true_n": extensions_true,
        "extensions_allowed": False,
        "new_fib_level_search": False,
    }


def _neighborhood_selected(row: Mapping[str, object], family: str, value: float) -> bool:
    if family == "rsi_lower_bound":
        rsi = _number(row.get("rsi_14"))
        return rsi is not None and value <= rsi <= 70
    if family == "ema20_to_ema50":
        ratio = _number(row.get("ema_ratio"))
        return ratio is not None and ratio > value
    if family == "bos_excess_atr":
        excess = _number(row.get("bos_excess_atr"))
        return row.get("setup_family") == SETUP_BREAKOUT and excess is not None and excess >= value
    raise KeyError(family)


def _parameter_plateau_report(accumulators: Mapping[str, _PlateauStats]) -> dict[str, object]:
    families: dict[str, list[dict[str, object]]] = defaultdict(list)
    for family, variant_id, value in PARAMETER_NEIGHBORHOODS:
        metrics = accumulators[variant_id].result()
        families[family].append(
            {"variant_id": variant_id, "parameter_value": value, "metrics": metrics}
        )
    result = {}
    for family, variants in families.items():
        positive = [
            row for row in variants
            if (_number(row["metrics"].get("candidate_expectancy_r")) or 0) > 0
        ]
        result[family] = {
            "variants": variants,
            "predeclared_neighborhood_only": True,
            "single_best_parameter_selected": False,
            "positive_variant_share": len(positive) / len(variants),
            "wide_positive_zone_visible": len(positive) >= 2,
            "isolated_positive_peak": len(positive) == 1,
            "new_threshold_search_allowed": False,
            "validation_opened": False,
            "holdout_opened": False,
        }
    return result


def _false_positive_risks(row: Mapping[str, object]) -> list[str]:
    risks = [
        "Eight predeclared hypotheses share an overlapping candidate universe.",
        "The frozen current universe is not fully survivorship-free.",
        "Validation and Holdout remain unseen, so Development stability is not confirmation.",
    ]
    treatment = row.get("treatment") or {}
    scenarios = ((treatment.get("execution_stress") or {}).get("scenarios") or {})
    if (_number((scenarios.get("higher_total_cost") or {}).get("candidate_expectancy_r")) or 0) <= 0:
        risks.append("The selected effect is not positive under the predeclared higher-cost stress.")
    time = treatment.get("time_stability") or {}
    if (_number(time.get("positive_expectancy_year_share_pct")) or 0) < 60:
        risks.append("Fewer than 60 percent of evaluated years have positive selected expectancy.")
    if row.get("post_hoc_direction_reversal") is True:
        risks.append("The observed direction is the reverse of the original hypothesis and is post hoc.")
    if row.get("hypothesis_id") == "buyer_confirmation":
        risks.append("The stored candle-quality alias is the identical boolean, not independent confirmation.")
    if row.get("hypothesis_id") == "fibonacci_0618_0786":
        risks.append("The incremental depth-adjusted residual is small and the base Profit Factor is weak.")
    return risks


def _ledger_audit(path: Path) -> dict[str, object]:
    with _read_only_connection(path) as connection:
        attempts = []
        for row in connection.execute(
            "SELECT hypothesis_id, family_id, family_attempt_number, payload_json, payload_fingerprint "
            "FROM research_hypothesis_attempts ORDER BY family_attempt_number"
        ):
            payload = json.loads(row["payload_json"])
            attempts.append(
                {
                    "hypothesis_id": row["hypothesis_id"],
                    "family_id": row["family_id"],
                    "family_attempt_number": row["family_attempt_number"],
                    "payload_fingerprint_valid": _fingerprint(payload) == row["payload_fingerprint"],
                    "dataset_fingerprint": payload.get("dataset_fingerprint"),
                    "feature_fingerprint": payload.get("feature_fingerprint"),
                    "code_fingerprint": payload.get("code_fingerprint"),
                }
            )
        events = int(connection.execute("SELECT COUNT(*) FROM research_hypothesis_events").fetchone()[0])
    return {
        "attempts": attempts,
        "attempt_count": len(attempts),
        "event_count": events,
        "invalid_fingerprints": sum(not row["payload_fingerprint_valid"] for row in attempts),
        "append_only_v1_entries_modified": False,
        "audit_note": (
            "The eight immutable v1 summaries remain as recorded. This report is their separate erratum."
        ),
    }


def _manifest(path: Path) -> tuple[dict[str, object], str]:
    with _read_only_connection(path) as connection:
        rows = connection.execute(
            "SELECT manifest_json, manifest_fingerprint FROM broad_research_manifests"
        ).fetchall()
    if len(rows) != 1:
        raise RuntimeError("Exactly one immutable Broad-v1 manifest is required.")
    manifest = json.loads(rows[0]["manifest_json"])
    fingerprint = str(rows[0]["manifest_fingerprint"])
    if _fingerprint(manifest) != fingerprint:
        raise RuntimeError("Broad-v1 manifest fingerprint is invalid.")
    expected = {
        "dataset_fingerprint": PROTECTED_DATASET_FINGERPRINT,
        "feature_contract_fingerprint": PROTECTED_FEATURE_CONTRACT_FINGERPRINT,
        "code_fingerprint": PROTECTED_CODE_FINGERPRINT,
        "asset_completions": 2520,
        "expected_assets": 2520,
    }
    mismatches = {key: (manifest.get(key), value) for key, value in expected.items() if manifest.get(key) != value}
    if mismatches:
        raise RuntimeError(f"Protected Broad-v1 manifest mismatch: {mismatches}")
    return manifest, fingerprint


def audit_broad_v1(
    broad_path: Path,
    quality_path: Path,
    *,
    progress_every: int = 100_000,
    progress_callback=None,
) -> dict[str, object]:
    broad_path, quality_path = Path(broad_path), Path(quality_path)
    before = {
        "broad_size": broad_path.stat().st_size,
        "broad_mtime_ns": broad_path.stat().st_mtime_ns,
        "quality_size": quality_path.stat().st_size,
        "quality_mtime_ns": quality_path.stat().st_mtime_ns,
    }
    manifest, manifest_fingerprint = _manifest(broad_path)
    ledgers = {
        hypothesis_id: {
            "applicable_n": 0,
            "valid_n": 0,
            "structurally_not_applicable_n": 0,
            "missing_n": 0,
            "treatment": _Stats(),
            "control": _Stats(),
        }
        for hypothesis_id in HYPOTHESIS_CONTRACTS
    }
    priority_rows: list[dict[str, object]] = []
    neighborhood_accumulators = {
        variant_id: _PlateauStats() for _, variant_id, _ in PARAMETER_NEIGHBORHOODS
    }
    all_asset_types: set[str] = set()
    all_setups: set[str] = set()
    universe_n = 0
    with _read_only_connection(broad_path) as connection:
        for sql_row in connection.execute(DEVELOPMENT_QUERY):
            universe_n += 1
            row = _record_from_sql(sql_row)
            all_asset_types.add(str(row.get("asset_type") or "unknown"))
            all_setups.add(str(row.get("setup_family") or "unknown"))
            if row["setup_family"] == SETUP_PULLBACK:
                priority_rows.append(row)
            for family, variant_id, value in PARAMETER_NEIGHBORHOODS:
                if _neighborhood_selected(row, family, value):
                    neighborhood_accumulators[variant_id].update(row)
            for hypothesis_id, ledger in ledgers.items():
                applicable, valid = _applicable_and_valid(row, hypothesis_id)
                if not applicable:
                    ledger["structurally_not_applicable_n"] += 1
                    continue
                ledger["applicable_n"] += 1
                if not valid:
                    ledger["missing_n"] += 1
                    continue
                ledger["valid_n"] += 1
                ledger["treatment" if _selected(row, hypothesis_id) else "control"].update(row)
            if progress_callback and progress_every > 0 and universe_n % progress_every == 0:
                progress_callback(universe_n)
    rows = []
    for hypothesis_id, ledger in ledgers.items():
        selected = ledger["treatment"].result()
        control = ledger["control"].result()
        treatment_n = int(selected["raw_candidate_n"])
        control_n = int(control["raw_candidate_n"])
        contract = HYPOTHESIS_CONTRACTS[hypothesis_id]
        gate = validity_gate(
            universe_n=universe_n,
            applicable_n=int(ledger["applicable_n"]),
            valid_n=int(ledger["valid_n"]),
            structurally_not_applicable_n=int(ledger["structurally_not_applicable_n"]),
            missing_n=int(ledger["missing_n"]),
            treatment_n=treatment_n,
            control_n=control_n,
            treatment_effective_n=int(selected["effective_dependency_cluster_n"]),
            control_effective_n=int(control["effective_dependency_cluster_n"]),
            feature_point_in_time_available=int(ledger["valid_n"]) > 0,
            outcome_independent_definition=True,
            market_scope_correct=True,
            setup_scope_correct=True,
            structural_missingness_treated_as_false=False,
        )
        selected_r = _number(selected.get("candidate_expectancy_r"))
        control_r = _number(control.get("candidate_expectancy_r"))
        selected_pf = _number(selected.get("candidate_profit_factor"))
        control_pf = _number(control.get("candidate_profit_factor"))
        row = {
            "hypothesis_id": hypothesis_id,
            "contract": {
                **contract,
                "actual_evaluated_setup_scope": tuple(contract["intended_setup_scope"]),
                "test_scope": TEST_SCOPE,
                "validated_scope": (),
                "fx_evidence_claimed": False,
                "validation_opened": False,
                "holdout_opened": False,
            },
            "validity": gate,
            "treatment": selected,
            "control": control,
            "delta": {
                "candidate_expectancy_r": selected_r - control_r if selected_r is not None and control_r is not None else None,
                "candidate_profit_factor": selected_pf - control_pf if selected_pf is not None and control_pf is not None else None,
                "average_mfe_r": (
                    float(selected["average_mfe_r"]) - float(control["average_mfe_r"])
                    if _number(selected.get("average_mfe_r")) is not None and _number(control.get("average_mfe_r")) is not None else None
                ),
                "average_mae_r": (
                    float(selected["average_mae_r"]) - float(control["average_mae_r"])
                    if _number(selected.get("average_mae_r")) is not None and _number(control.get("average_mae_r")) is not None else None
                ),
            },
            "automatic_abc_grade": _automatic_performance_grade(gate, selected, control),
            "automatic_c_allowed": False,
            "automatic_challenger_creation": False,
            "automatic_confluence_building": False,
            "quality_review_complete": False,
        }
        rows.append(row)
    row_by_id = {row["hypothesis_id"]: row for row in rows}
    for hypothesis_id in ("buyer_confirmation", "three_or_more_bearish_candles"):
        scoped = [
            row for row in priority_rows
            if _applicable_and_valid(row, hypothesis_id) == (True, True)
        ]
        row_by_id[hypothesis_id]["regime_matched_placebo"] = _matched_placebo(scoped, hypothesis_id)
        row_by_id[hypothesis_id]["dependency_and_ablation"] = _dependency_review(scoped, hypothesis_id)
        row_by_id[hypothesis_id]["quality_review_complete"] = True
    row_by_id["three_or_more_bearish_candles"]["post_hoc_direction_reversal"] = True
    row_by_id["three_or_more_bearish_candles"]["development_derived_followup_only"] = True
    fib = _fib_review(priority_rows)
    row_by_id["fibonacci_0618_0786"]["fibonacci_control_review"] = fib
    row_by_id["fibonacci_0618_0786"]["quality_review_complete"] = True
    parameter_neighborhoods = _parameter_plateau_report(neighborhood_accumulators)
    for row in rows:
        row["false_positive_risks"] = _false_positive_risks(row)
    quality_ledger = _ledger_audit(quality_path)
    after = {
        "broad_size": broad_path.stat().st_size,
        "broad_mtime_ns": broad_path.stat().st_mtime_ns,
        "quality_size": quality_path.stat().st_size,
        "quality_mtime_ns": quality_path.stat().st_mtime_ns,
    }
    if before != after:
        raise RuntimeError("A protected source artifact changed during the read-only audit.")
    report = {
        "audit_version": BROAD_V1_AUDIT_VERSION,
        "future_report_contract_version": FUTURE_REPORT_CONTRACT_VERSION,
        "status": "complete_development_only_method_audit",
        "immutable_reference": {
            "dataset_fingerprint": manifest["dataset_fingerprint"],
            "feature_contract_fingerprint": manifest["feature_contract_fingerprint"],
            "code_fingerprint": manifest["code_fingerprint"],
            "manifest_fingerprint": manifest_fingerprint,
            "asset_completions": manifest["asset_completions"],
            "counts": manifest["counts"],
            "splits": manifest["splits"],
            "source_files_unchanged_during_audit": True,
            "source_snapshot_before": before,
            "source_snapshot_after": after,
        },
        "actual_market_scope": {
            "asset_types": sorted(all_asset_types),
            "test_scope": TEST_SCOPE,
            "source_scope": "stored_per_hypothesis",
            "validated_scope": (),
            "fx_tested": False,
            "futures_tested": False,
            "commodities_tested": False,
            "cross_market_transfer_claimed": False,
        },
        "actual_setup_scope": sorted(all_setups),
        "development_universe_n": universe_n,
        "hypotheses": rows,
        "parameter_neighborhoods": parameter_neighborhoods,
        "research_quality_ledger": quality_ledger,
        "multiple_testing": {
            "predeclared_hypotheses": len(rows),
            "attempt_count_in_v1_ledger": quality_ledger["attempt_count"],
            "future_hypothesis_families": {
                family: sum(
                    1 for contract in HYPOTHESIS_CONTRACTS.values()
                    if contract["hypothesis_family"] == family
                )
                for family in sorted(
                    {str(contract["hypothesis_family"]) for contract in HYPOTHESIS_CONTRACTS.values()}
                )
            },
            "v1_ledger_family_design_problem": (
                "All eight distinct feature concepts were recorded in one broad-development-single-feature family."
            ),
            "semantic_deduplication_issue": (
                "buyer_confirmation and candle_quality.close_above_prior_high are the same stored boolean and cannot count twice"
            ),
            "candidate_overlap_requires_effective_n": True,
            "raw_n_is_independent_n": False,
            "holm_or_fdr_p_values_claimed": False,
            "reason": "Overlapping candidates do not justify naive independent p-values.",
            "validation_or_holdout_used": False,
        },
        "metric_semantics": METRIC_SEMANTICS,
        "global_limits": {
            "survivorship_free": False,
            "historical_constituents_available": False,
            "delistings_and_bankruptcies_complete": False,
            "point_in_time_universe_available": False,
            "intrabar_sequence_claimed": False,
            "time_to_first_positive_movement_available": False,
            "validation_opened": False,
            "holdout_opened": False,
        },
        "errata": [
            {"hypothesis_id": "cot_available", "finding": "classification_error", "correction": VALIDITY_NOT_TESTABLE},
            {"hypothesis_id": "opening_level_contact", "finding": "hypothesis_design_problem", "correction": VALIDITY_NON_DISCRIMINATING, "root_cause": "The OR includes the current daily open, which is structurally inside almost every valid daily OHLC bar."},
            {"hypothesis_id": "buyer_confirmation", "finding": "feature_applicability_scope_mismatch", "correction": "pullback_only"},
            {"hypothesis_id": "three_or_more_bearish_candles", "finding": "feature_applicability_scope_mismatch_and_post_hoc_reversal", "correction": "pullback_only_and_new_hypothesis_if_continued"},
            {"hypothesis_id": "fibonacci_0618_0786", "finding": "feature_applicability_and_incomplete_control_reporting", "correction": "pullback_only_with_equal_width_and_continuous_depth_controls"},
            {"hypothesis_id": "bos_close_break", "finding": "feature_applicability_scope_mismatch", "correction": "breakout_only"},
            {"hypothesis_id": "all", "finding": "metric_reporting_error", "correction": "candidate_sequence_drawdown_not_portfolio_drawdown"},
            {"hypothesis_id": "all", "finding": "hypothesis_family_design_problem", "correction": "future reports count the seven explicit feature families separately"},
        ],
        "ranking_order": [
            "buyer_confirmation",
            "three_or_more_bearish_candles",
            "fibonacci_0618_0786",
            "ema20_above_ema50",
            "rsi_40_70",
            "bos_close_break",
            "opening_level_contact",
            "cot_available",
        ],
        "manual_review": None,
        "validation_opened": False,
        "holdout_opened": False,
        "automatic_strategy_selection": False,
        "automatic_challenger_creation": False,
        "automatic_confluence_building": False,
        "production_activated": False,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def apply_manual_development_review(
    report: Mapping[str, object],
    decisions: Mapping[str, Mapping[str, object]],
    *,
    reviewed_at: str,
) -> dict[str, object]:
    """Attach an explicit human Development review without opening unseen data."""
    result = copy.deepcopy(dict(report))
    if result.get("validation_opened") or result.get("holdout_opened"):
        raise ValueError("Manual Development review cannot use Validation or Holdout.")
    rows = {row["hypothesis_id"]: row for row in result.get("hypotheses", [])}
    c_recommendations = 0
    normalized = {}
    for hypothesis_id, raw in decisions.items():
        if hypothesis_id not in rows:
            raise ValueError(f"Unknown hypothesis: {hypothesis_id}")
        decision = str(raw.get("recommendation") or "").upper()
        if decision not in {"A", "B", "C_RECOMMENDATION", "NOT_TESTABLE", "INVALID"}:
            raise ValueError("Unknown manual recommendation.")
        if decision == "C_RECOMMENDATION":
            c_recommendations += 1
            if rows[hypothesis_id]["validity"]["status"] != VALIDITY_PASS:
                raise ValueError("Only a valid hypothesis can receive a C recommendation.")
            if rows[hypothesis_id].get("quality_review_complete") is not True:
                raise ValueError("C recommendation requires a complete Development quality review.")
            if rows[hypothesis_id].get("post_hoc_direction_reversal") is True:
                raise ValueError("Post-hoc direction reversal requires a new hypothesis, not C.")
        normalized[hypothesis_id] = {
            "recommendation": decision,
            "reason": str(raw.get("reason") or "").strip(),
            "manual_judgment": True,
            "production_approval": False,
        }
    if c_recommendations > 1:
        raise ValueError("At most one simple Development hypothesis may be recommended for freeze.")
    result["manual_review"] = {
        "reviewed_at": str(reviewed_at),
        "decisions": normalized,
        "validation_opened": False,
        "holdout_opened": False,
        "challenger_created": False,
        "production_activated": False,
    }
    result.pop("report_fingerprint", None)
    result["report_fingerprint"] = _fingerprint(result)
    return result


def write_append_only_json(report: Mapping[str, object], path: Path) -> dict[str, object]:
    """Create a versioned report; an existing different artifact is never overwritten."""
    path = Path(path)
    content = _json(report, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        created = True
    except FileExistsError:
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise RuntimeError("Append-only audit artifact already exists with different content.")
        created = False
    return {
        "path": str(path),
        "created": created,
        "report_fingerprint": report.get("report_fingerprint"),
        "bytes": len(content.encode("utf-8")),
    }
