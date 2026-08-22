from __future__ import annotations

import sqlite3
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import swing_walk_forward as walk_forward_module
from swing_walk_forward import (
    SWING_OBSERVATIONAL_FEATURE_VERSION,
    SWING_WALK_FORWARD_ENGINE_VERSION,
    load_swing_walk_forward_cases,
    load_swing_walk_forward_forward_links,
    record_swing_walk_forward_forward_links,
    record_swing_walk_forward_run,
    run_historical_walk_forward,
    swing_observational_rsi_ema_report,
    swing_walk_forward_research_readiness,
    swing_walk_forward_store_audit,
    swing_walk_forward_forward_link_candidates,
    swing_walk_forward_strategy_comparison,
    swing_walk_forward_strategy_profiles,
    swing_walk_forward_summary,
)


def breakout_history(*, falling_future: bool = False) -> pd.DataFrame:
    index = pd.bdate_range("2022-01-03", periods=330)
    close = np.linspace(50.0, 100.0, 330) + np.sin(np.linspace(0, 20, 330))
    close[299] = float(max(close[279:299])) * 1.01
    if falling_future:
        close[300:] = np.linspace(close[299] * 0.99, close[299] * 0.88, 30)
    else:
        close[300:] = np.linspace(close[299] * 0.995, close[299] * 1.18, 30)
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.4,
            "Low": close - 0.4,
            "Close": close,
            "Volume": np.full(330, 500_000.0),
        },
        index=index,
    )


def test_walk_forward_signal_uses_identical_past_when_only_future_changes() -> None:
    rising = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    falling = run_historical_walk_forward(
        {"TEST": breakout_history(falling_future=True)},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )

    assert len(rising["cases"]) == 1
    assert len(falling["cases"]) == 1
    assert rising["cases"][0]["snapshot"] == falling["cases"][0]["snapshot"]
    assert rising["cases"][0]["future_data_used_for_signal"] is False
    assert rising["separate_from_real_forward"] is True
    assert rising["production_comparable"] is False
    assert rising["cases"][0]["events"] != falling["cases"][0]["events"]


def test_observational_rsi_ema_features_are_causal_and_deterministic() -> None:
    rising = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    falling = run_historical_walk_forward(
        {"TEST": breakout_history(falling_future=True)},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    repeated = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )

    rising_feature = next(iter(rising["observational_features"].values()))
    falling_feature = next(iter(falling["observational_features"].values()))
    repeated_feature = next(iter(repeated["observational_features"].values()))

    assert rising_feature == falling_feature == repeated_feature
    assert rising_feature["feature_version"] == SWING_OBSERVATIONAL_FEATURE_VERSION
    assert rising_feature["future_bars_used"] == 0
    assert rising_feature["causal_cutoff"] == "including_completed_signal_bar"
    assert rising_feature["baseline_filtering"] is False
    assert rising_feature["trade_selection_changed"] is False
    assert {
        "rsi_14",
        "ema_20",
        "ema_50",
        "close_relative_to_ema20",
        "close_relative_to_ema50",
        "ema20_relative_to_ema50",
        "close_distance_to_ema20",
        "close_distance_to_ema50",
    }.issubset(rising_feature["values"])


def test_observational_features_cannot_change_baseline_cases_or_results(monkeypatch) -> None:
    baseline = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    monkeypatch.setattr(
        walk_forward_module,
        "_observational_rsi_ema_features",
        lambda case: {
            "feature_version": SWING_OBSERVATIONAL_FEATURE_VERSION,
            "future_bars_used": 0,
            "baseline_filtering": False,
            "trade_selection_changed": False,
            "values": {"rsi_14": -999.0, "ema_20": 10**12, "ema_50": -10**12},
        },
    )
    with_extreme_observation = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )

    assert baseline["cases"] == with_extreme_observation["cases"]
    assert baseline["summary"] == with_extreme_observation["summary"]
    assert baseline["cases"][0]["case_id"] == with_extreme_observation["cases"][0]["case_id"]
    assert baseline["cases"][0]["case_fingerprint"] == with_extreme_observation["cases"][0]["case_fingerprint"]
    assert baseline["cases"][0]["result_r"] == with_extreme_observation["cases"][0]["result_r"]


def test_walk_forward_store_is_append_only_idempotent_and_separate(tmp_path) -> None:
    path = tmp_path / "walk.sqlite3"
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )

    first = record_swing_walk_forward_run(run, path)
    second = record_swing_walk_forward_run(run, path)
    audit = swing_walk_forward_store_audit(path)

    assert first["run_inserted"] is True
    assert first["cases_inserted"] == 1
    assert first["observational_features_inserted"] == 1
    assert second["run_inserted"] is False
    assert second["cases_inserted"] == 0
    assert second["observational_features_inserted"] == 0
    assert audit["status"] == "ok"
    assert audit["runs"] == 1
    assert audit["cases"] == 1
    assert audit["observational_features"] == 1
    assert audit["separate_from_real_forward"] is True
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM walk_forward_cases")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM walk_forward_case_observational_features")


def test_legacy_case_is_readable_and_is_never_backfilled_as_previously_recorded(tmp_path) -> None:
    path = tmp_path / "legacy-features.sqlite3"
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    legacy_run = deepcopy(run)
    legacy_run.pop("observational_features")

    first = record_swing_walk_forward_run(legacy_run, path)
    legacy_case = load_swing_walk_forward_cases(path)[0]
    second = record_swing_walk_forward_run(run, path)
    still_legacy = load_swing_walk_forward_cases(path)[0]

    assert first["cases_inserted"] == 1
    assert first["observational_features_inserted"] == 0
    assert legacy_case["observational_features"] is None
    assert legacy_case["observational_feature_status"] == "legacy_feature_not_recorded"
    assert second["cases_inserted"] == 0
    assert second["observational_features_inserted"] == 0
    assert still_legacy["observational_features"] is None
    assert still_legacy["observational_feature_status"] == "legacy_feature_not_recorded"


def test_observational_report_is_split_aware_and_never_derives_a_rule(tmp_path) -> None:
    path = tmp_path / "feature-report.sqlite3"
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    record_swing_walk_forward_run(run, path)
    cases = load_swing_walk_forward_cases(path)
    report = swing_observational_rsi_ema_report(cases, minimum_segment_cases=50)

    assert report["feature_cases"] == 1
    assert report["legacy_or_unavailable_cases"] == 0
    assert report["automatic_threshold_search"] is False
    assert report["automatic_rule_change"] is False
    assert report["holdout_used_for_rule_selection"] is False
    assert report["improvement_claimed"] is False
    assert report["future_challenger_contract"] == {
        "status": "not_created",
        "manual_hypothesis_selection_required": True,
        "rule_must_be_frozen_before_test": True,
        "new_strategy_fingerprint_required": True,
        "new_hypothetical_trades_required": True,
        "baseline_storage_separate": True,
        "new_research_epoch_or_fresh_walk_forward_required": True,
        "current_observations_are_confirmatory_evidence": False,
        "production_activation_allowed": False,
    }
    for rows in report["segments"].values():
        assert rows
        assert all(set(row["by_split"]) == {"development", "validation", "holdout"} for row in rows)
        assert all(row["small_sample"] is True for row in rows)
        assert all(row["improvement_claimed"] is False for row in rows)
        for row in rows:
            for metrics in row["by_split"].values():
                assert {
                    "cases",
                    "average_r",
                    "profit_factor",
                    "hit_rate_pct",
                    "maximum_drawdown_r",
                }.issubset(metrics)


def test_exact_real_forward_link_is_append_only_and_excludes_duplicate_recent_monitoring(
    tmp_path,
) -> None:
    path = tmp_path / "walk.sqlite3"
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
        sampling_mode="recent_incremental",
    )
    case = run["cases"][0]
    forward_snapshot = deepcopy(case["snapshot"])
    forward_snapshot["source_kind"] = "real_forward_scan"
    forward_signal = {
        "signal_id": "real-forward-1",
        "snapshot": forward_snapshot,
        "events": [],
    }
    record_swing_walk_forward_run(run, path)
    candidates = swing_walk_forward_forward_link_candidates([case], [forward_signal])

    assert len(candidates) == 1
    assert candidates[0]["relation"] == "exact_same_trade"
    first = record_swing_walk_forward_forward_links(candidates, path)
    second = record_swing_walk_forward_forward_links(candidates, path)
    stored = load_swing_walk_forward_cases(path)[0]
    summary = swing_walk_forward_summary(path)
    audit = swing_walk_forward_store_audit(path)

    assert first["inserted"] == 1
    assert second["existing"] == 1
    assert stored["real_forward_link_status"] == "exact_same_trade"
    assert stored["historical_monitoring_counted"] is False
    assert summary["real_forward_linkage"]["exact_same_trade"] == 1
    assert summary["real_forward_linkage"]["historical_monitoring_excluded"] == 1
    assert summary["recent_monitoring"]["evaluated"] == 0
    assert audit["forward_links"] == 1
    assert audit["status"] == "ok"
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM walk_forward_real_links")


def test_related_real_forward_case_stays_a_separate_strategy_experiment(tmp_path) -> None:
    path = tmp_path / "walk.sqlite3"
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
        sampling_mode="recent_incremental",
    )
    case = run["cases"][0]
    forward_snapshot = deepcopy(case["snapshot"])
    forward_snapshot["order_plan"]["target_1_original"] = (
        float(forward_snapshot["order_plan"]["target_1_original"]) + 1.0
    )
    candidates = swing_walk_forward_forward_link_candidates(
        [case],
        [{"signal_id": "different-plan", "snapshot": forward_snapshot, "events": []}],
    )
    record_swing_walk_forward_run(run, path)
    record_swing_walk_forward_forward_links(candidates, path)
    stored = load_swing_walk_forward_cases(path)[0]

    assert candidates[0]["relation"] == "related_same_asset_day"
    assert stored["historical_monitoring_counted"] is True
    assert load_swing_walk_forward_forward_links(path)[0]["preferred_evidence"] == "separate"


def test_case_identity_ignores_later_bars_but_preserves_corrected_data_revision(tmp_path) -> None:
    path = tmp_path / "revisions.sqlite3"
    original = breakout_history()
    later_index = pd.bdate_range(original.index[-1] + pd.Timedelta(days=1), periods=10)
    later_close = np.linspace(float(original["Close"].iloc[-1]), 125.0, len(later_index))
    appended = pd.concat(
        [
            original,
            pd.DataFrame(
                {
                    "Open": later_close - 0.1,
                    "High": later_close + 0.4,
                    "Low": later_close - 0.4,
                    "Close": later_close,
                    "Volume": np.full(len(later_index), 500_000.0),
                },
                index=later_index,
            ),
        ]
    )
    corrected = original.copy()
    corrected.iloc[305, corrected.columns.get_loc("Close")] += 0.01
    boundaries = {
        "development_end": "2023-12-31",
        "validation_end": "2024-12-31",
        "last_signal_day": "2025-12-31",
    }

    def run(history: pd.DataFrame) -> dict:
        return run_historical_walk_forward(
            {"TEST": history},
            minimum_history_rows=300,
            step_sessions=1,
            future_sessions=25,
            maximum_cases=1,
            research_split_boundaries=boundaries,
        )

    first = run(original)
    with_later_bars = run(appended)
    with_correction = run(corrected)
    with_integer_volume = original.copy()
    with_integer_volume["Volume"] = with_integer_volume["Volume"].astype("int64")
    with_storage_dtype_change = run(with_integer_volume)

    assert first["cases"][0]["logical_case_id"] == with_later_bars["cases"][0]["logical_case_id"]
    assert first["cases"][0]["case_id"] == with_later_bars["cases"][0]["case_id"]
    assert first["cases"][0]["case_id"] == with_storage_dtype_change["cases"][0]["case_id"]
    assert first["cases"][0]["logical_case_id"] == with_correction["cases"][0]["logical_case_id"]
    assert first["cases"][0]["case_id"] != with_correction["cases"][0]["case_id"]

    record_swing_walk_forward_run(first, path)
    record_swing_walk_forward_run(with_correction, path)
    latest = load_swing_walk_forward_cases(path)
    all_revisions = load_swing_walk_forward_cases(path, include_superseded_revisions=True)

    assert len(latest) == 1
    assert len(all_revisions) == 2
    assert latest[0]["case_id"] == with_correction["cases"][0]["case_id"]
    summary = swing_walk_forward_summary(path)
    assert summary["stored_cases_total"] == 1
    assert summary["stored_case_revisions_total"] == 2
    assert summary["superseded_case_revisions"] == 1


def test_per_symbol_cap_is_balanced_across_chronological_splits(monkeypatch) -> None:
    index = pd.bdate_range("2018-01-02", periods=1_600)
    close = np.linspace(50.0, 150.0, len(index))
    history = pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.4,
            "Low": close - 0.4,
            "Close": close,
            "Volume": np.full(len(index), 500_000.0),
        },
        index=index,
    )

    def approved_assessment(*args, **kwargs) -> dict:
        return {
            "approved": True,
            "market_phase": "Bullenmarkt",
            "volatility_regime": "Niedrig",
            "setup_type": "Test",
            "buy_signal": 7.0,
            "confidence": 7.0,
            "data_quality": 1.0,
            "relative_volume": 1.0,
            "average_turnover_eur": 1_000_000.0,
            "crv": 2.5,
            "risk_pct": 0.02,
            "order_plan": {
                "limit_price_original": 100.0,
                "initial_stop_original": 98.0,
                "target_1_original": 105.0,
                "target_2_original": 110.0,
            },
            "limitations": [],
        }

    monkeypatch.setattr(
        walk_forward_module,
        "historical_technical_shadow_assessment",
        approved_assessment,
    )
    monkeypatch.setattr(
        walk_forward_module,
        "evaluate_swing_signal_bars",
        lambda *args, **kwargs: [],
    )
    run = run_historical_walk_forward(
        {"TEST": history},
        minimum_history_rows=220,
        step_sessions=5,
        future_sessions=25,
        maximum_cases=12,
        maximum_cases_per_symbol=12,
        research_split_boundaries={
            "development_end": "2020-12-31",
            "validation_end": "2022-12-31",
            "last_signal_day": "2023-12-31",
        },
    )

    split_counts = pd.Series([case["research_split"] for case in run["cases"]]).value_counts()
    assert split_counts.to_dict() == {"development": 4, "validation": 4, "holdout": 4}
    assert all(case["signal_at"][:10] <= "2023-12-31" for case in run["cases"])


def test_selection_rounds_are_deterministic_disjoint_and_keep_round_a_unchanged(
    monkeypatch,
) -> None:
    index = pd.bdate_range("2010-01-04", periods=3_300)
    close = np.linspace(50.0, 170.0, len(index))
    history = pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.4,
            "Low": close - 0.4,
            "Close": close,
            "Volume": np.full(len(index), 500_000.0),
        },
        index=index,
    )

    def approved_assessment(*args, **kwargs) -> dict:
        return {
            "approved": True,
            "market_phase": "Bullenmarkt",
            "volatility_regime": "Niedrig",
            "setup_type": "Test",
            "buy_signal": 7.0,
            "confidence": 7.0,
            "data_quality": 1.0,
            "relative_volume": 1.0,
            "average_turnover_eur": 1_000_000.0,
            "crv": 2.5,
            "risk_pct": 0.02,
            "order_plan": {
                "limit_price_original": 100.0,
                "initial_stop_original": 98.0,
                "target_1_original": 105.0,
                "target_2_original": 110.0,
            },
            "limitations": [],
        }

    monkeypatch.setattr(
        walk_forward_module,
        "historical_technical_shadow_assessment",
        approved_assessment,
    )
    monkeypatch.setattr(
        walk_forward_module,
        "evaluate_swing_signal_bars",
        lambda *args, **kwargs: [],
    )
    common = {
        "minimum_history_rows": 220,
        "step_sessions": 1,
        "future_sessions": 25,
        "maximum_cases": 6,
        "maximum_cases_per_symbol": 6,
        "research_split_boundaries": {
            "development_end": "2015-12-31",
            "validation_end": "2019-12-31",
            "last_signal_day": "2022-12-31",
        },
    }
    default_round = run_historical_walk_forward({"TEST": history}, **common)
    rounds = [
        run_historical_walk_forward(
            {"TEST": history},
            **common,
            selection_round=index,
            selection_round_role=role,
        )
        for index, role in enumerate(
            ("exploration", "locked_validation", "final_confirmation")
        )
    ]

    assert [case["cutoff_position"] for case in default_round["cases"]] == [
        case["cutoff_position"] for case in rounds[0]["cases"]
    ]
    assert [len(run["cases"]) for run in rounds] == [6, 6, 6]
    assert [run["parameters"]["selection_round"] for run in rounds] == ["A", "B", "C"]
    all_positions = [
        case["cutoff_position"]
        for run in rounds
        for case in run["cases"]
    ]
    assert len(all_positions) == len(set(all_positions))
    assert all(
        abs(left - right) >= 25
        for index, left in enumerate(all_positions)
        for right in all_positions[index + 1 :]
    )


def test_recent_sampling_prefers_latest_cases_and_evidence_deduplicates_sampling_modes(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "sampling.sqlite3"
    original_assessment = walk_forward_module.historical_technical_shadow_assessment

    def only_first_signal(symbol, history, **kwargs):
        if len(history) != 300:
            return {"approved": False}
        return original_assessment(symbol, history, **kwargs)

    monkeypatch.setattr(
        walk_forward_module,
        "historical_technical_shadow_assessment",
        only_first_signal,
    )
    boundaries = {
        "development_end": "2023-12-31",
        "validation_end": "2024-12-31",
        "last_signal_day": "2025-12-31",
    }
    balanced = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
        research_split_boundaries=boundaries,
        sampling_mode="balanced_history",
    )
    recent = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
        research_split_boundaries=boundaries,
        sampling_mode="recent_incremental",
    )

    assert balanced["cases"][0]["evidence_key"] == recent["cases"][0]["evidence_key"]
    assert balanced["cases"][0]["logical_case_id"] != recent["cases"][0]["logical_case_id"]
    assert recent["cases"][0]["monitoring_only"] is True
    assert recent["cases"][0]["selection_eligible"] is False
    recent_readiness = swing_walk_forward_research_readiness(
        recent["cases"],
        minimum_outcomes=1,
        minimum_symbols=1,
        minimum_holdout_outcomes=1,
        minimum_segment_outcomes=1,
    )
    assert recent_readiness["technical_challenger_review_allowed"] is False
    record_swing_walk_forward_run(balanced, path)
    record_swing_walk_forward_run(recent, path)
    assert len(load_swing_walk_forward_cases(path)) == 1
    assert len(load_swing_walk_forward_cases(path, include_superseded_revisions=True)) == 2


def test_last_signal_day_does_not_change_existing_case_identity() -> None:
    common = {
        "development_end": "2023-12-31",
        "validation_end": "2024-12-31",
    }
    first = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
        research_split_boundaries={**common, "last_signal_day": "2025-01-01"},
    )
    later = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
        research_split_boundaries={**common, "last_signal_day": "2026-01-01"},
    )

    assert first["cases"][0]["case_id"] == later["cases"][0]["case_id"]
    assert first["cases"][0]["case_fingerprint"] == later["cases"][0]["case_fingerprint"]


def test_frozen_dataset_contract_is_assigned_without_changing_research_cases() -> None:
    common = {
        "minimum_history_rows": 300,
        "step_sessions": 1,
        "future_sessions": 25,
        "maximum_cases": 1,
    }
    baseline = run_historical_walk_forward({"TEST": breakout_history()}, **common)
    dataset_contract = {
        "dataset_epoch": "test-fixed-v1",
        "dataset_revision": "revision-abc",
        "dataset_fingerprint": "fingerprint-abc",
        "scope_id": "scope-abc",
        "provider_access_during_job": False,
        "manifest_version": "test-manifest-v1",
    }
    frozen = run_historical_walk_forward(
        {"TEST": breakout_history()},
        research_dataset=dataset_contract,
        **common,
    )

    assert frozen["research_dataset"] == dataset_contract
    assert frozen["cases"] == baseline["cases"]
    assert frozen["summary"] == baseline["summary"]
    assert frozen["data_fingerprints"] == baseline["data_fingerprints"]
    assert frozen["run_id"] != baseline["run_id"]


def test_frozen_dataset_contract_must_be_provider_free() -> None:
    with pytest.raises(ValueError, match="keinen Providerzugriff"):
        run_historical_walk_forward(
            {"TEST": breakout_history()},
            minimum_history_rows=300,
            step_sessions=1,
            future_sessions=25,
            maximum_cases=1,
            research_dataset={
                "dataset_epoch": "test-fixed-v1",
                "dataset_revision": "revision-abc",
                "dataset_fingerprint": "fingerprint-abc",
                "scope_id": "scope-abc",
                "provider_access_during_job": True,
            },
        )


def test_walk_forward_v2_uses_purged_splits_adjusted_prices_and_versioned_profile(tmp_path) -> None:
    path = tmp_path / "research.sqlite3"
    profiles = swing_walk_forward_strategy_profiles(("current",))
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=10,
        maximum_cases_per_symbol=2,
        strategy_profiles=profiles,
        purge_overlapping_signals=True,
        price_adjustment="yfinance_auto_adjust_true",
    )

    assert run["run_version"] == SWING_WALK_FORWARD_ENGINE_VERSION
    assert run["research_contract"]["chronological_splits"] is True
    assert run["research_contract"]["adjusted_ohlcv_verified"] is True
    assert all(case["overlap_purged"] is True for case in run["cases"])
    assert all(case["research_split"] in {"development", "validation", "holdout"} for case in run["cases"])
    assert all(
        case["snapshot"]["strategy"]["strategy_version"] in profiles
        for case in run["cases"]
    )

    record_swing_walk_forward_run(run, path)
    stored = load_swing_walk_forward_cases(path)
    assert len(stored) == len(run["cases"])


def test_research_gate_and_strategy_comparison_never_activate_production() -> None:
    run = run_historical_walk_forward(
        {"TEST": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=5,
        price_adjustment="yfinance_auto_adjust_true",
    )

    readiness = swing_walk_forward_research_readiness(
        run["cases"],
        minimum_outcomes=1,
        minimum_symbols=1,
        minimum_holdout_outcomes=1,
        minimum_segment_outcomes=1,
    )
    comparison = swing_walk_forward_strategy_comparison(run["cases"])

    assert readiness["full_swing_trader_change_allowed"] is False
    assert readiness["production_activation_allowed"] is False
    assert readiness["automatic_rule_change"] is False
    assert comparison["production_activation_allowed"] is False
    assert comparison["holdout_selects_production_automatically"] is False
    assert comparison["derived_hypotheses_require_locked_rerun"] is True
    assert {row["strategy_name"] for row in comparison["rows"]} == {
        "current",
        "balanced",
        "precision",
        "payoff",
    }
