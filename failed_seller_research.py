from __future__ import annotations

"""Causal, development-only Failed-Seller feature epoch.

This module is separate from immutable Broad-v1.  It may read a compatible
frozen OHLCV history and existing Development labels, but it never changes the
Broad database, strategy rules, validation, holdout, forward or production.
"""

import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from swing_research_identity_v2 import dependency_evidence_report_v2


FAILED_SELLER_FEATURE_VERSION = "failed-seller-attempts-2026.08.28-v1"
FAILED_SELLER_FEATURE_CONTRACT_VERSION = "failed-seller-contract-2026.08.28-v1"
FAILED_SELLER_RUN_SCHEMA_VERSION = 1
FAILED_SELLER_WORK_REQUEST_ID = "d4dbaf10-b321-4223-9a0b-91f0bc245151"
FAILED_SELLER_HYPOTHESIS_ID = "7cb6dd8b-85e2-4b46-ac9a-0654a1310fc4"
FAILED_SELLER_EXPERIMENT_ID = "f0ae30fb-d00e-461f-84ad-ac3110f4ae49"
DEFAULT_FAILED_SELLER_DB_PATH = (
    Path(__file__).resolve().parent / "runtime" / "failed_seller_research.sqlite3"
)

KB_SELLER_ATTEMPT_VARIANTS = (1, 2)
KB_CLOSE_LOCATION_VARIANTS = (0.70, 0.80)
FIXED_COST_STRESS_R = (0.05, 0.10)


class FailedSellerContractError(ValueError):
    """The preregistered feature or development-only run contract was violated."""


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def failed_seller_feature_contract() -> dict[str, object]:
    """Freeze the stored KB experiment before any Development result is read."""

    payload: dict[str, object] = {
        "version": FAILED_SELLER_FEATURE_CONTRACT_VERSION,
        "feature_version": FAILED_SELLER_FEATURE_VERSION,
        "work_request_id": FAILED_SELLER_WORK_REQUEST_ID,
        "hypothesis_id": FAILED_SELLER_HYPOTHESIS_ID,
        "experiment_id": FAILED_SELLER_EXPERIMENT_ID,
        "scope": ["EQUITIES", "ETF"],
        "setup_scope": "objective_pullback",
        "research_split": "development_only",
        "causal_cutoff": "completed_signal_bar",
        "source": "compatible_frozen_ohlcv_and_read_only_broad_development_cases",
        "push_definition": {
            "window": "session_after_objective_impulse_high_through_completed_signal_bar",
            "push_start": "close_below_previous_close_and_low_below_previous_low",
            "push_membership": "maximal_run_while_close_declines_or_new_running_low_is_set",
            "push_separation": "one_completed_bar_with_neither_lower_close_nor_lower_low",
            "new_relevant_low": "push_low_below_running_pullback_low_known_before_push",
            "sustained_structure_break": "at_least_two_completed_closes_below_pre_push_running_low",
            "push_depth_atr": "prior_high_minus_push_low_divided_by_atr14_known_before_push",
            "recovery_fraction": "max_subsequent_close_through_signal_minus_push_low_divided_by_prior_high_minus_push_low",
            "time_to_recovery": "completed_sessions_from_push_low_to_first_close_at_or_above_prior_high",
            "failed_seller_attempt": "new_relevant_low_and_no_sustained_break_and_full_recovery_before_or_on_signal",
        },
        "close_location": {
            "formula": "(close-low)/(high-low)",
            "zero_range": "MISSING",
        },
        # These are the immutable parameters stored on the referenced KB
        # experiment.  Later planning notes do not silently rewrite them.
        "isolated_variants": {
            "seller_attempt_count_exact": list(KB_SELLER_ATTEMPT_VARIANTS),
            "confirmation_close_location_gte": list(KB_CLOSE_LOCATION_VARIANTS),
        },
        "combination_policy": (
            "not_evaluated_until_isolated_value_has_separate_oos_and_walk_forward_support"
        ),
        "dynamic_threshold_mining": False,
        "future_bars_in_features": 0,
        "labels_stored_separately": True,
        "fixed_cost_stress_r": list(FIXED_COST_STRESS_R),
        "automatic_filter": False,
        "automatic_strategy_change": False,
        "automatic_activation": False,
        "validation_opened": False,
        "holdout_opened": False,
    }
    payload["feature_contract_fingerprint"] = _fingerprint(payload)
    return payload


def _normalized_history(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not isinstance(frame, pd.DataFrame) or frame.empty or not required <= set(frame.columns):
        raise FailedSellerContractError("Failed-Seller benötigt vollständige OHLCV-Historie.")
    result = frame.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
    result.index = pd.to_datetime(result.index, errors="coerce")
    if result.index.tz is not None:
        result.index = result.index.tz_convert(None)
    result = result.loc[~result.index.isna()].sort_index()
    result = result.loc[~result.index.duplicated(keep="last")]
    for column in result.columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["Open", "High", "Low", "Close"])
    if result.empty:
        raise FailedSellerContractError("Failed-Seller-Historie enthält keine gültigen Kerzen.")
    return result


def causal_atr14(frame: pd.DataFrame) -> pd.Series:
    normalized = _normalized_history(frame)
    prior_close = normalized["Close"].shift(1)
    true_range = pd.concat(
        [
            normalized["High"] - normalized["Low"],
            (normalized["High"] - prior_close).abs(),
            (normalized["Low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(14, min_periods=14).mean()


def close_location(*, close: object, low: object, high: object) -> float | None:
    try:
        close_value, low_value, high_value = float(close), float(low), float(high)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (close_value, low_value, high_value)):
        return None
    if high_value <= low_value or not low_value <= close_value <= high_value:
        return None
    return (close_value - low_value) / (high_value - low_value)


def build_failed_seller_feature(
    frame: pd.DataFrame,
    *,
    pullback_start_day: object,
    signal_day: object,
    candidate_id: str,
    dataset_fingerprint: str,
    prepared_history: bool = False,
    pullback_start_position: int | None = None,
    signal_position: int | None = None,
    atr14_series: pd.Series | None = None,
) -> dict[str, object]:
    """Build one feature row using no bar after ``signal_day``."""

    history = frame if prepared_history else _normalized_history(frame)
    start_day = pd.Timestamp(pullback_start_day).normalize()
    cutoff_day = pd.Timestamp(signal_day).normalize()
    eligible = (
        history.iloc[: signal_position + 1]
        if signal_position is not None
        else history.loc[history.index.normalize() <= cutoff_day]
    )
    if eligible.empty or eligible.index[-1].normalize() != cutoff_day:
        raise FailedSellerContractError("Signalstag fehlt in der eingefrorenen Historie.")
    if pullback_start_position is None:
        start_positions = [
            index for index, day in enumerate(eligible.index.normalize()) if day == start_day
        ]
        if not start_positions:
            raise FailedSellerContractError("Objektiver Pullback-Start fehlt in der Historie.")
        start_position = start_positions[-1]
    else:
        start_position = int(pullback_start_position)
    signal_position = len(eligible) - 1
    if start_position >= signal_position:
        raise FailedSellerContractError("Pullback-Fenster enthält keine abgeschlossene Folgekerze.")

    atr = (
        atr14_series.iloc[: signal_position + 1]
        if atr14_series is not None
        else causal_atr14(eligible)
    )
    pushes: list[dict[str, object]] = []
    position = max(start_position + 1, 1)
    while position <= signal_position:
        previous = eligible.iloc[position - 1]
        current = eligible.iloc[position]
        starts = (
            float(current["Close"]) < float(previous["Close"])
            and float(current["Low"]) < float(previous["Low"])
        )
        if not starts:
            position += 1
            continue

        push_start = position
        push_end = position
        running_push_low = float(current["Low"])
        while push_end + 1 <= signal_position:
            candidate = eligible.iloc[push_end + 1]
            prior = eligible.iloc[push_end]
            continues = (
                float(candidate["Close"]) < float(prior["Close"])
                or float(candidate["Low"]) < running_push_low
            )
            if not continues:
                break
            push_end += 1
            running_push_low = min(running_push_low, float(eligible.iloc[push_end]["Low"]))

        separation_position = push_end + 1
        if separation_position > signal_position:
            break
        separator = eligible.iloc[separation_position]
        push_last = eligible.iloc[push_end]
        if (
            float(separator["Close"]) < float(push_last["Close"])
            or float(separator["Low"]) < running_push_low
        ):
            position = separation_position
            continue

        pre_push = eligible.iloc[start_position:push_start]
        pre_push_low = float(pre_push["Low"].min())
        reference_high = float(eligible.iloc[push_start - 1]["High"])
        push_rows = eligible.iloc[push_start : push_end + 1]
        push_low = float(push_rows["Low"].min())
        push_low_position = push_start + int(push_rows["Low"].to_numpy().argmin())
        new_relevant_low = push_low < pre_push_low
        closes_below_pre_push_low = int(
            (eligible.iloc[push_start : signal_position + 1]["Close"] < pre_push_low).sum()
        )
        sustained_break = closes_below_pre_push_low >= 2
        recovery_rows = eligible.iloc[push_end + 1 : signal_position + 1]
        denominator = reference_high - push_low
        maximum_recovery_close = (
            float(recovery_rows["Close"].max()) if not recovery_rows.empty else None
        )
        recovery_fraction = (
            (maximum_recovery_close - push_low) / denominator
            if maximum_recovery_close is not None and denominator > 0 else None
        )
        recovery_positions = [
            index
            for index in range(push_end + 1, signal_position + 1)
            if float(eligible.iloc[index]["Close"]) >= reference_high
        ]
        recovery_position = recovery_positions[0] if recovery_positions else None
        atr_before_push = (
            float(atr.iloc[push_start - 1])
            if push_start > 0 and pd.notna(atr.iloc[push_start - 1]) and float(atr.iloc[push_start - 1]) > 0
            else None
        )
        failed = bool(new_relevant_low and not sustained_break and recovery_position is not None)
        pushes.append(
            {
                "push_index": len(pushes) + 1,
                "push_start_day": eligible.index[push_start].date().isoformat(),
                "push_end_day": eligible.index[push_end].date().isoformat(),
                "push_low_day": eligible.index[push_low_position].date().isoformat(),
                "separation_day": eligible.index[separation_position].date().isoformat(),
                "pre_push_running_low": pre_push_low,
                "push_start_reference_high": reference_high,
                "push_low": push_low,
                "new_relevant_low": new_relevant_low,
                "closes_below_pre_push_low": closes_below_pre_push_low,
                "sustained_structure_break": sustained_break,
                "push_depth_atr": (
                    (reference_high - push_low) / atr_before_push
                    if atr_before_push is not None else None
                ),
                "atr_known_before_push": atr_before_push,
                "maximum_recovery_close_through_signal": maximum_recovery_close,
                "recovery_fraction": recovery_fraction,
                "recovery_day": (
                    eligible.index[recovery_position].date().isoformat()
                    if recovery_position is not None else None
                ),
                "sessions_to_recovery": (
                    recovery_position - push_low_position
                    if recovery_position is not None else None
                ),
                "failed_seller_attempt": failed,
            }
        )
        position = separation_position + 1

    signal = eligible.iloc[signal_position]
    location = close_location(
        close=signal["Close"], low=signal["Low"], high=signal["High"]
    )
    failed_count = sum(bool(item["failed_seller_attempt"]) for item in pushes)
    contract = failed_seller_feature_contract()
    payload: dict[str, object] = {
        "feature_version": FAILED_SELLER_FEATURE_VERSION,
        "feature_contract_fingerprint": contract["feature_contract_fingerprint"],
        "candidate_id": str(candidate_id),
        "dataset_fingerprint": str(dataset_fingerprint),
        "pullback_start_day": start_day.date().isoformat(),
        "feature_at": cutoff_day.date().isoformat(),
        "causal_cutoff": "completed_signal_bar",
        "history_last_day_used": eligible.index[-1].date().isoformat(),
        "future_bars_used": 0,
        "pushes": pushes,
        "seller_push_count": len(pushes),
        "failed_seller_attempt_count": failed_count,
        "confirmation_close_location": location,
        "isolated_variant_flags": {
            "failed_seller_attempts_exactly_1": failed_count == 1,
            "failed_seller_attempts_exactly_2": failed_count == 2,
            "confirmation_close_location_gte_0_70": (
                location is not None and location >= 0.70
            ),
            "confirmation_close_location_gte_0_80": (
                location is not None and location >= 0.80
            ),
        },
        "labels_present": False,
        "automatic_trade_rule": False,
        "automatic_strategy_change": False,
    }
    payload["feature_fingerprint"] = _fingerprint(payload)
    return payload


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    results = [value for row in rows if (value := _number(row.get("result_r"))) is not None]
    positives = [value for value in results if value > 0]
    negatives = [value for value in results if value < 0]
    mfe = [value for row in rows if (value := _number(row.get("mfe_pct"))) is not None]
    mae = [value for row in rows if (value := _number(row.get("mae_pct"))) is not None]
    dependency = dependency_evidence_report_v2(rows)
    return {
        "raw_n": len(rows),
        "evaluated_n": len(results),
        "effective_n_known_issuer_clusters_only": dependency[
            "effective_n_known_clusters_only"
        ],
        "unknown_dependency_n": dependency["unknown_dependency_n"],
        "expectancy_r": sum(results) / len(results) if results else None,
        "profit_factor": (
            sum(positives) / abs(sum(negatives)) if positives and negatives else None
        ),
        "hit_rate_pct": (
            sum(value > 0 for value in results) / len(results) * 100 if results else None
        ),
        "average_mfe_pct": sum(mfe) / len(mfe) if mfe else None,
        "average_mae_pct": sum(mae) / len(mae) if mae else None,
        "cost_stress_expectancy_r": {
            f"additional_{stress:.2f}R": (
                sum(value - stress for value in results) / len(results)
                if results else None
            )
            for stress in FIXED_COST_STRESS_R
        },
    }


def evaluate_failed_seller_development(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    contract = failed_seller_feature_contract()
    variants = (
        "failed_seller_attempts_exactly_1",
        "failed_seller_attempts_exactly_2",
        "confirmation_close_location_gte_0_70",
        "confirmation_close_location_gte_0_80",
    )
    valid_rows = [row for row in rows if row.get("feature_status") == "available"]
    reports: dict[str, object] = {}
    for variant in variants:
        selected = [row for row in valid_rows if bool(dict(row.get("variant_flags") or {}).get(variant))]
        control = [row for row in valid_rows if not bool(dict(row.get("variant_flags") or {}).get(variant))]
        selected_metrics = _metrics(selected)
        control_metrics = _metrics(control)
        reports[variant] = {
            "selected": selected_metrics,
            "control": control_metrics,
            "incremental_expectancy_r": (
                float(selected_metrics["expectancy_r"]) - float(control_metrics["expectancy_r"])
                if selected_metrics["expectancy_r"] is not None and control_metrics["expectancy_r"] is not None
                else None
            ),
        }

    strata: dict[str, dict[str, int]] = {}
    for field in ("asset_class", "year", "regime", "region", "market_scope"):
        strata[field] = dict(sorted(Counter(str(row.get(field) or "UNKNOWN") for row in valid_rows).items()))
    dependency = dependency_evidence_report_v2(valid_rows)
    payload: dict[str, object] = {
        "version": FAILED_SELLER_FEATURE_VERSION,
        "status": "DEVELOPMENT_ONLY_DESCRIPTIVE_IDENTITY_LIMITED",
        "feature_contract_fingerprint": contract["feature_contract_fingerprint"],
        "raw_case_n": len(rows),
        "valid_feature_n": len(valid_rows),
        "missing_feature_n": len(rows) - len(valid_rows),
        "dependency": dependency,
        "variants": reports,
        "strata_counts": strata,
        "research_attempt_count": len(variants),
        "attempts": list(variants),
        "combination_variants_evaluated": [],
        "combination_gate": "BLOCKED_UNTIL_ISOLATED_OOS_AND_WALK_FORWARD_VALUE",
        "validation_opened": False,
        "holdout_opened": False,
        "result_direction": "INCONCLUSIVE",
        "reason": (
            "Development descriptions are retained, but unknown/legacy-derived issuer "
            "dependencies are not promoted to independent evidence."
        ),
        "strategy_activated": False,
        "production_filter_created": False,
    }
    payload["result_fingerprint"] = _fingerprint(payload)
    return payload


def initialize_failed_seller_store(path: Path = DEFAULT_FAILED_SELLER_DB_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS failed_seller_runs (
                run_id TEXT PRIMARY KEY,
                run_json TEXT NOT NULL,
                run_fingerprint TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS failed_seller_features (
                run_id TEXT NOT NULL REFERENCES failed_seller_runs(run_id),
                candidate_id TEXT NOT NULL,
                feature_json TEXT NOT NULL,
                feature_fingerprint TEXT NOT NULL,
                PRIMARY KEY(run_id, candidate_id)
            );
            CREATE TABLE IF NOT EXISTS failed_seller_attempt_ledger (
                run_id TEXT NOT NULL REFERENCES failed_seller_runs(run_id),
                attempt_index INTEGER NOT NULL,
                variant TEXT NOT NULL,
                PRIMARY KEY(run_id, attempt_index)
            );
            CREATE TRIGGER IF NOT EXISTS failed_seller_runs_no_update
            BEFORE UPDATE ON failed_seller_runs BEGIN SELECT RAISE(ABORT, 'failed_seller_runs append-only'); END;
            CREATE TRIGGER IF NOT EXISTS failed_seller_runs_no_delete
            BEFORE DELETE ON failed_seller_runs BEGIN SELECT RAISE(ABORT, 'failed_seller_runs append-only'); END;
            CREATE TRIGGER IF NOT EXISTS failed_seller_features_no_update
            BEFORE UPDATE ON failed_seller_features BEGIN SELECT RAISE(ABORT, 'failed_seller_features append-only'); END;
            CREATE TRIGGER IF NOT EXISTS failed_seller_features_no_delete
            BEFORE DELETE ON failed_seller_features BEGIN SELECT RAISE(ABORT, 'failed_seller_features append-only'); END;
            CREATE TRIGGER IF NOT EXISTS failed_seller_attempt_ledger_no_update
            BEFORE UPDATE ON failed_seller_attempt_ledger BEGIN SELECT RAISE(ABORT, 'failed_seller_attempt_ledger append-only'); END;
            CREATE TRIGGER IF NOT EXISTS failed_seller_attempt_ledger_no_delete
            BEFORE DELETE ON failed_seller_attempt_ledger BEGIN SELECT RAISE(ABORT, 'failed_seller_attempt_ledger append-only'); END;
            """
        )


def store_failed_seller_run(
    run: Mapping[str, object],
    features: Sequence[Mapping[str, object]],
    *,
    path: Path = DEFAULT_FAILED_SELLER_DB_PATH,
) -> dict[str, int]:
    initialize_failed_seller_store(path)
    run_payload = dict(run)
    run_id = str(run_payload.get("run_id") or "")
    if not run_id:
        raise FailedSellerContractError("Failed-Seller-Run benötigt run_id.")
    run_fingerprint = str(run_payload.get("run_fingerprint") or "")
    expected = _fingerprint({key: value for key, value in run_payload.items() if key != "run_fingerprint"})
    if run_fingerprint != expected:
        raise FailedSellerContractError("Failed-Seller-Run-Fingerprint ist ungültig.")
    inserted_features = 0
    with sqlite3.connect(path) as connection:
        existing = connection.execute(
            "SELECT run_fingerprint FROM failed_seller_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if existing is not None:
            if str(existing[0]) != run_fingerprint:
                raise FailedSellerContractError("run_id existiert mit anderem Fingerprint.")
            return {"run_inserted": 0, "features_inserted": 0}
        connection.execute(
            "INSERT INTO failed_seller_runs VALUES (?, ?, ?)",
            (run_id, _canonical_json(run_payload), run_fingerprint),
        )
        for feature in features:
            candidate_id = str(feature.get("candidate_id") or "")
            feature_fingerprint = str(feature.get("feature_fingerprint") or "")
            if not candidate_id or not feature_fingerprint:
                raise FailedSellerContractError("Feature benötigt Kandidaten- und Fingerprint-ID.")
            connection.execute(
                "INSERT INTO failed_seller_features VALUES (?, ?, ?, ?)",
                (run_id, candidate_id, _canonical_json(feature), feature_fingerprint),
            )
            inserted_features += 1
        for index, variant in enumerate(run_payload.get("attempts") or [], start=1):
            connection.execute(
                "INSERT INTO failed_seller_attempt_ledger VALUES (?, ?, ?)",
                (run_id, index, str(variant)),
            )
    return {"run_inserted": 1, "features_inserted": inserted_features}


def finalize_run_payload(payload: Mapping[str, object]) -> dict[str, object]:
    result = dict(payload)
    result.pop("run_fingerprint", None)
    result["run_fingerprint"] = _fingerprint(result)
    return result
