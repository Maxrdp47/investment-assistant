from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from swing_broad_research import (
    BROAD_RESEARCH_FEATURE_VERSION,
    BROAD_RESEARCH_PATTERN_VERSION,
    _canonical_json,
    _down_impulse_rally_geometry,
    _fingerprint,
    _pivot_structure,
    _prepare_historical_indicators,
    _simulate_fixed_target,
    _technical_regime_context,
    broad_research_code_fingerprint,
    broad_research_feature_contract_fingerprint,
    broad_research_feature_coverage,
    broad_research_split,
    broad_research_store_audit,
    build_asset_broad_research,
    build_broad_research_feature,
    build_broad_research_labels,
    build_fixed_challenger_rescan_asset,
    challenger_allowed_stage,
    completed_broad_research_symbols,
    development_pattern_report,
    directional_price_order_is_valid,
    fixed_challenger_rule_matches,
    initialize_broad_research_store,
    record_asset_broad_research,
    record_challenger_stage_review,
    record_fixed_challenger_rescan_asset,
    register_fixed_research_challenger,
)
from swing_walk_forward import _technical_scores
from swing_ml_dataset_contract import build_broad_research_ml_row
from swing_research_dataset import research_history_fingerprint


def _history() -> pd.DataFrame:
    index = pd.bdate_range("2020-01-02", periods=310)
    first = np.linspace(50.0, 100.0, 230)
    pullback = np.linspace(99.0, 82.0, 20)
    later = np.linspace(83.0, 110.0, 60)
    close = np.concatenate([first, pullback, later])
    open_ = close * (1 + np.sin(np.arange(len(close))) * 0.002)
    return pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) + 1.0,
            "Low": np.minimum(open_, close) - 1.0,
            "Close": close,
            "Volume": np.linspace(1_000_000, 1_500_000, len(close)),
        },
        index=index,
    )


def _asset() -> dict:
    return {
        "ticker": "TEST",
        "name": "Test Incorporated",
        "asset_type": "Aktie",
        "region": "USA",
        "category": "Test",
        "liquidity_class": "A",
    }


def _bearish_history() -> pd.DataFrame:
    index = pd.bdate_range("2020-01-02", periods=320)
    first = np.linspace(130.0, 120.0, 225)
    impulse = np.linspace(119.0, 72.0, 30)
    rally = np.linspace(73.0, 91.0, 20)
    later = np.linspace(90.0, 68.0, 45)
    close = np.concatenate([first, impulse, rally, later])
    open_ = close * (1 + np.cos(np.arange(len(close))) * 0.003)
    return pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) + 1.0,
            "Low": np.minimum(open_, close) - 1.0,
            "Close": close,
            "Volume": np.linspace(900_000, 1_600_000, len(close)),
        },
        index=index,
    )


def _seed_manual_c_evidence(
    path,
    hypothesis: dict,
    *,
    dataset_fingerprint: str = "dataset-v1",
    feature_fingerprint: str = "feature-contract-v1",
    expected_assets: int = 1,
) -> None:
    initialize_broad_research_store(path)
    manifest = {
        "dataset_fingerprint": dataset_fingerprint,
        "feature_contract_fingerprint": feature_fingerprint,
        "code_fingerprint": broad_research_code_fingerprint(),
        "asset_completions": expected_assets,
        "expected_assets": expected_assets,
        "automatic_production_activation": False,
    }
    manifest_fingerprint = _fingerprint(manifest)
    stored_hypothesis = {
        "pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
        **hypothesis,
        "validation_opened": False,
        "holdout_opened": False,
        "automatic_challenger_creation": False,
        "automatic_production_activation": False,
    }
    hypothesis_fingerprint = _fingerprint(stored_hypothesis)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO broad_research_manifests VALUES (?, ?, ?)",
            (f"manifest-{manifest_fingerprint[:20]}", _canonical_json(manifest), manifest_fingerprint),
        )
        connection.execute(
            "INSERT INTO broad_research_hypotheses VALUES (?, ?, ?)",
            (
                f"{BROAD_RESEARCH_PATTERN_VERSION}|{hypothesis['hypothesis_id']}",
                _canonical_json(stored_hypothesis),
                hypothesis_fingerprint,
            ),
        )


def test_feature_is_causal_deterministic_and_reuses_existing_indicators() -> None:
    raw = _history()
    prepared = _prepare_historical_indicators(raw)
    position = 249
    first = build_broad_research_feature(
        "TEST", _asset(), prepared, position, "objective_pullback", dataset_fingerprint="dataset-v1"
    )
    changed_future = prepared.copy()
    changed_future.iloc[position + 1 :, changed_future.columns.get_loc("Close")] *= 9
    second = build_broad_research_feature(
        "TEST", _asset(), changed_future, position, "objective_pullback", dataset_fingerprint="dataset-v1"
    )

    assert first["feature_fingerprint"] == second["feature_fingerprint"]
    assert first["future_bars_used"] == 0
    assert first["labels_present_in_features"] is False
    assert first["technical"]["rsi_14"] == pytest.approx(prepared.iloc[position]["RSI_14"])
    assert first["technical"]["ema_20"] == pytest.approx(prepared.iloc[position]["EMA_20"])
    assert first["technical"]["ema_50"] == pytest.approx(prepared.iloc[position]["EMA_50"])
    assert first["technical"]["atr_14"] == pytest.approx(prepared.iloc[position]["ATR_14"])
    assert first["code_fingerprint"] == broad_research_code_fingerprint()
    assert first["feature_contract_fingerprint"] == broad_research_feature_contract_fingerprint()
    assert first["relative_strength"]["status"] == "benchmark_unavailable"
    assert first["trend_quality"]["additional_trend_indicator_added"] is False
    assert first["volatility_structure"]["signal_bar_excluded_from_prior_normal_ranges"] is True
    assert first["historical_breadth"]["survivorship_free"] is False
    assert first["first_pass_feature_scope"]["automatic_optimization"] is False


def test_short_readiness_geometry_is_causal_deterministic_and_reuses_indicators() -> None:
    raw = _bearish_history()
    frozen_before = research_history_fingerprint("TEST", raw)
    prepared = _prepare_historical_indicators(raw)
    position = 274
    first = build_broad_research_feature(
        "TEST",
        _asset(),
        prepared,
        position,
        "objective_pullback",
        dataset_fingerprint="dataset-v1",
    )
    changed_future = prepared.copy()
    changed_future.iloc[position + 1 :, changed_future.columns.get_loc("High")] *= 20
    changed_future.iloc[position + 1 :, changed_future.columns.get_loc("Low")] /= 20
    second = build_broad_research_feature(
        "TEST",
        _asset(),
        changed_future,
        position,
        "objective_pullback",
        dataset_fingerprint="dataset-v1",
    )

    readiness = first["short_readiness"]
    geometry = readiness["down_impulse_and_rally"]
    assert geometry["status"] == "available"
    assert geometry["impulse_high_day"] < geometry["impulse_low_day"] < first["feature_at"][:10]
    assert geometry["rally_retracement_depth"] == pytest.approx(
        (prepared.iloc[position]["Close"] - geometry["impulse_low"])
        / (geometry["impulse_high"] - geometry["impulse_low"])
    )
    assert first["feature_fingerprint"] == second["feature_fingerprint"]
    assert first["technical"]["rsi_14"] == pytest.approx(prepared.iloc[position]["RSI_14"])
    assert first["technical"]["atr_14"] == pytest.approx(prepared.iloc[position]["ATR_14"])
    assert readiness["ema_context"]["shared_indicator_source"] == "technical"
    assert readiness["strategy_created"] is False
    assert readiness["signal_created"] is False
    assert readiness["short_execution_data"]["borrow_fee"] is None
    assert frozen_before == research_history_fingerprint("TEST", raw)


def test_bearish_confirmation_and_bos_are_point_in_time_only() -> None:
    prepared = _prepare_historical_indicators(_bearish_history())
    structure = _pivot_structure(prepared)
    found = None
    for position in range(219, len(prepared) - 25):
        feature = build_broad_research_feature(
            "TEST",
            _asset(),
            prepared,
            position,
            "objective_pullback",
            dataset_fingerprint="dataset-v1",
            structure=structure,
        )
        short = feature["short_readiness"]
        if short["market_structure"]["bearish_bos"]:
            found = (position, feature)
            break
    assert found is not None
    position, feature = found
    confirmation = feature["short_readiness"]["market_structure"]["confirmation_at"]
    assert confirmation == feature["feature_at"]
    assert feature["short_readiness"]["market_structure"]["future_bars_used"] == 0
    changed = prepared.copy()
    changed.iloc[position + 1 :, changed.columns.get_loc("Close")] *= 99
    repeated = build_broad_research_feature(
        "TEST",
        _asset(),
        changed,
        position,
        "objective_pullback",
        dataset_fingerprint="dataset-v1",
        structure=structure,
    )
    assert feature["feature_fingerprint"] == repeated["feature_fingerprint"]


def test_directional_price_order_contract_is_mirrored_without_short_execution() -> None:
    assert directional_price_order_is_valid(entry=100, stop=95, target=110, direction="long")
    assert directional_price_order_is_valid(entry=100, stop=105, target=90, direction="short")
    assert not directional_price_order_is_valid(entry=100, stop=95, target=90, direction="long")
    assert not directional_price_order_is_valid(entry=100, stop=105, target=110, direction="short")


def test_precomputed_market_phase_matches_existing_source_logic() -> None:
    prepared = _prepare_historical_indicators(_history())
    phases, regimes = _technical_regime_context(prepared)

    for position in (219, 249, 279, 309):
        signal_frame = prepared.iloc[max(0, position - 320) : position + 1]
        _, expected_phase, _, _, expected_regime = _technical_scores(signal_frame)
        assert phases[position] == expected_phase
        assert regimes[position] == expected_regime


def test_pullback_fibonacci_bos_openings_seasonality_and_volume_profile_contract() -> None:
    prepared = _prepare_historical_indicators(_history())
    feature = build_broad_research_feature(
        "TEST", _asset(), prepared, 249, "objective_pullback", dataset_fingerprint="dataset-v1"
    )

    assert feature["pullback"]["status"] == "available"
    assert feature["pullback"]["impulse_high_day"] < feature["feature_at"][:10]
    assert feature["fibonacci"]["retracement_depth"] == feature["pullback"]["pullback_depth"]
    assert feature["fibonacci"]["extensions_tested"] is False
    assert feature["market_structure"]["retroactive_entry_allowed"] is False
    assert feature["market_structure"]["earliest_trade_day"] is None
    assert set(feature["opening_levels"]) == {"daily", "weekly", "monthly", "quarterly", "yearly"}
    assert feature["seasonality"]["historical_completed_periods_only"] is True
    assert feature["seasonality"]["free_calendar_search"] is False
    assert feature["volume_profile"]["status"] == "unavailable_daily_ohlcv_insufficient"
    assert feature["volume_profile"]["approximated"] is False


def test_labels_are_attached_after_features_and_entry_is_next_session() -> None:
    prepared = _prepare_historical_indicators(_history())
    position = 249
    feature = build_broad_research_feature(
        "TEST", _asset(), prepared, position, "objective_pullback", dataset_fingerprint="dataset-v1"
    )
    feature_before = json.dumps(feature, sort_keys=True)
    labels, experiments = build_broad_research_labels(
        prepared, position, feature, asset_type="Aktie"
    )

    assert json.dumps(feature, sort_keys=True) == feature_before
    assert labels["labels_used_for_candidate_selection"] is False
    assert labels["entry"]["entry_day"] == prepared.index[position + 1].date().isoformat()
    assert labels["entry"]["retroactive_signal_close_entry"] is False
    assert set(labels["forward_returns"]) == {"5d", "10d", "20d", "25d"}
    assert set(labels["direction_neutral_horizons"]) == {"5d", "10d", "20d", "25d"}
    raw = labels["direction_neutral_horizons"]["25d"]
    future = prepared.iloc[position + 1 : position + 26]
    assert raw["future_maximum_high"] == pytest.approx(float(future["High"].max()))
    assert raw["future_minimum_low"] == pytest.approx(float(future["Low"].min()))
    assert raw["sessions_to_future_high"] == int(np.argmax(future["High"].to_numpy())) + 1
    assert raw["sessions_to_future_low"] == int(np.argmin(future["Low"].to_numpy())) + 1
    assert raw["long_mfe_derivable"] is True
    assert raw["short_mfe_derivable"] is True
    assert labels["short_strategy_evaluated"] is False
    assert "direction_neutral_horizons" not in feature
    assert experiments["same_entry_all_variants"] is True
    assert experiments["conservative_same_bar_order"] == "gap_then_stop_before_target"
    assert experiments["features_affected"] is False


def test_stop_wins_when_stop_and_target_are_inside_same_daily_bar() -> None:
    future = pd.DataFrame(
        [{"Open": 100.0, "High": 110.0, "Low": 90.0, "Close": 105.0}],
        index=pd.to_datetime(["2025-01-02"]),
    )
    result = _simulate_fixed_target(
        future, entry=100.0, stop=95.0, target_r=2.0, cost_bps=9.0
    )

    assert result["status"] == "stop"
    assert result["result_r"] < -1.0


def test_asset_candidate_stream_is_outcome_blind_and_store_is_resume_safe(tmp_path) -> None:
    result = build_asset_broad_research(
        "TEST", _asset(), _history(), dataset_fingerprint="dataset-v1"
    )
    assert result["candidates"]
    for candidate in result["candidates"]:
        assert candidate["candidate_selected_from_outcome"] is False
        assert candidate["long_v1_required_for_selection"] is False
        assert candidate["direction"] == "long"
        assert candidate["short_signal_created"] is False
        assert candidate["feature"]["research_direction"] == "long"
        assert candidate["feature"]["short_strategy_enabled"] is False
        assert "result_r" not in candidate["feature"]
    path = tmp_path / "broad.sqlite3"
    first = record_asset_broad_research(result, dataset_fingerprint="dataset-v1", path=path)
    second = record_asset_broad_research(result, dataset_fingerprint="dataset-v1", path=path)

    assert first["candidates"] == len(result["candidates"])
    assert second["already_complete"] is True
    assert completed_broad_research_symbols(dataset_fingerprint="dataset-v1", path=path) == {"TEST"}
    assert broad_research_store_audit(path)["quick_check"] == "ok"
    coverage = broad_research_feature_coverage(path, dataset_fingerprint="dataset-v1")
    assert coverage["candidates"] == len(result["candidates"])
    assert 0 < coverage["available"]["rsi_14"] <= len(result["candidates"])
    assert coverage["available"]["volume_profile"] == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT DISTINCT direction FROM broad_research_candidates"
        ).fetchall() == [("long",)]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE broad_research_candidates SET symbol='CHANGED'")

    report = development_pattern_report(path)
    repeated = development_pattern_report(path)
    assert report == repeated
    assert report["cases"] == len(result["candidates"])
    assert len(report["hypotheses"]) == 8
    assert len(report["parameter_neighborhoods"]) == 9
    assert "expectancy_r" in report["development_candidate_baseline"]
    assert "trade_count_loss_vs_development_baseline" in report["hypotheses"][0]
    assert all(row["quality_review_complete"] is False for row in report["hypotheses"])
    assert all(row["eligible_for_manual_fixed_challenger"] is False for row in report["hypotheses"])
    assert set(report["parameter_plateaus"]) == {"bos_excess_atr", "ema20_to_ema50", "rsi_lower_bound"}
    assert report["validation_opened"] is False
    assert report["holdout_opened"] is False
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM broad_research_hypotheses").fetchone()[0] == 8


def test_empty_prepass_schema_two_migrates_to_direction_without_research_data(tmp_path) -> None:
    path = tmp_path / "prepass.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE broad_research_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO broad_research_meta VALUES('schema_version', '2')")
        connection.execute(
            """CREATE TABLE broad_research_candidates(
            candidate_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, signal_day TEXT NOT NULL,
            setup_family TEXT NOT NULL, research_split TEXT NOT NULL, issuer_id TEXT NOT NULL,
            listing_id TEXT NOT NULL, dependency_cluster TEXT NOT NULL,
            dataset_fingerprint TEXT NOT NULL, feature_version TEXT NOT NULL,
            feature_json TEXT NOT NULL, feature_fingerprint TEXT NOT NULL)"""
        )

    initialize_broad_research_store(path)

    with sqlite3.connect(path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(broad_research_candidates)")]
        assert "direction" in columns
        assert connection.execute(
            "SELECT value FROM broad_research_meta WHERE key='schema_version'"
        ).fetchone()[0] == "4"
        assert connection.execute("SELECT COUNT(*) FROM broad_research_candidates").fetchone()[0] == 0


def test_ml_adapter_keeps_broad_features_and_labels_physically_separate() -> None:
    result = build_asset_broad_research(
        "TEST", _asset(), _history(), dataset_fingerprint="dataset-v1"
    )
    candidate = result["candidates"][0]
    label = result["labels"][0]
    row = build_broad_research_ml_row(candidate, labels=label)

    assert row["candidate_id"] == candidate["candidate_id"]
    assert row["direction"] == "long"
    assert row["features"]["labels_present_in_features"] is False
    assert row["labels"]["candidate_id"] == candidate["candidate_id"]
    assert row["model_training_performed"] is False
    assert row["random_split_allowed"] is False
    assert row["production_activation_allowed"] is False


def test_split_contract_matches_existing_campaign_boundaries() -> None:
    assert broad_research_split("2012-12-31") == "development"
    assert broad_research_split("2013-01-01") == "validation"
    assert broad_research_split("2015-06-01") == "holdout"
    assert broad_research_split("2021-12-31") == "development"
    assert broad_research_split("2022-01-01") == "validation"
    assert broad_research_split("2024-01-01") == "holdout"


def test_fixed_challenger_is_append_only_and_never_activated(tmp_path) -> None:
    path = tmp_path / "challenger.sqlite3"
    development_report = {
        "pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
        "validation_opened": False,
        "holdout_opened": False,
        "hypotheses": [
            {
                "hypothesis_id": "buyer_confirmation",
                "classification": "C",
                "eligible_for_manual_fixed_challenger": True,
                "quality_review_complete": True,
            }
        ],
    }
    approval = {
        "development_report": development_report,
        "manual_confirmation": "CONFIRM_CHALLENGER_C_FREEZE",
        "approved_at": "2026-08-22T12:00:00+00:00",
        "expected_assets": 1,
    }
    _seed_manual_c_evidence(path, development_report["hypotheses"][0])
    first = register_fixed_research_challenger(
        {"setup_family": "objective_pullback", "buyer_confirmation": True},
        hypothesis_id="buyer_confirmation",
        dataset_fingerprint="dataset-v1",
        feature_fingerprint="feature-contract-v1",
        path=path,
        **approval,
    )
    second = register_fixed_research_challenger(
        {"setup_family": "objective_pullback", "buyer_confirmation": True},
        hypothesis_id="buyer_confirmation",
        dataset_fingerprint="dataset-v1",
        feature_fingerprint="feature-contract-v1",
        path=path,
        **approval,
    )

    assert first == second
    assert first["automatic_production_activation"] is False
    assert first["external_universe_required"] is True
    with pytest.raises(ValueError, match="Ergebniswissen"):
        register_fixed_research_challenger(
            {"result_r": 2.0},
            hypothesis_id="invalid",
            dataset_fingerprint="dataset-v1",
            feature_fingerprint="feature-contract-v1",
            path=path,
            **approval,
        )

    assert fixed_challenger_rule_matches(
        {
            "setup_family": "objective_pullback",
            "feature": {"pullback": {"buyer_confirmation_close_above_prior_high": True}},
        },
        first["rule"],
    )


def test_challenger_freeze_rejects_non_c_development_hint(tmp_path) -> None:
    with pytest.raises(ValueError, match="Klassifikation C"):
        register_fixed_research_challenger(
            {"rsi_min": 40.0, "rsi_max": 70.0},
            hypothesis_id="rsi_40_70",
            dataset_fingerprint="dataset-v1",
            feature_fingerprint="feature-contract-v1",
            development_report={
                "pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
                "validation_opened": False,
                "holdout_opened": False,
                "hypotheses": [
                    {
                        "hypothesis_id": "rsi_40_70",
                        "classification": "B",
                        "eligible_for_manual_fixed_challenger": False,
                    }
                ],
            },
            manual_confirmation="CONFIRM_CHALLENGER_C_FREEZE",
            approved_at="2026-08-22T12:00:00+00:00",
            expected_assets=1,
            path=tmp_path / "blocked.sqlite3",
        )


def test_manual_challenger_rescans_frozen_validation_before_holdout(tmp_path) -> None:
    path = tmp_path / "handoff.sqlite3"
    history = _history()
    history.index = pd.bdate_range("2022-01-03", periods=len(history))
    broad = build_asset_broad_research(
        "TEST", _asset(), history, dataset_fingerprint="dataset-v1"
    )
    record_asset_broad_research(broad, dataset_fingerprint="dataset-v1", path=path)
    report = {
        "pattern_version": BROAD_RESEARCH_PATTERN_VERSION,
        "validation_opened": False,
        "holdout_opened": False,
        "hypotheses": [
            {
                "hypothesis_id": "pullback_family",
                "classification": "C",
                "eligible_for_manual_fixed_challenger": True,
                "quality_review_complete": True,
            }
        ],
    }
    _seed_manual_c_evidence(path, report["hypotheses"][0])
    challenger = register_fixed_research_challenger(
        {"setup_family": "objective_pullback"},
        hypothesis_id="pullback_family",
        dataset_fingerprint="dataset-v1",
        feature_fingerprint="feature-contract-v1",
        development_report=report,
        manual_confirmation="CONFIRM_CHALLENGER_C_FREEZE",
        approved_at="2026-08-22T12:00:00+00:00",
        expected_assets=1,
        path=path,
    )

    assert challenger_allowed_stage(challenger["challenger_version"], "validation", path)["allowed"] is True
    assert challenger_allowed_stage(challenger["challenger_version"], "holdout", path)["allowed"] is False
    rescan = build_fixed_challenger_rescan_asset(
        challenger, _asset(), history, research_split="validation"
    )
    stored = record_fixed_challenger_rescan_asset(rescan, path=path)
    repeated = record_fixed_challenger_rescan_asset(rescan, path=path)

    assert stored["full_history_rescan"] is True
    assert repeated["trades_inserted"] == 0
    assert all(trade["development_data_read"] is False for trade in rescan["trades"])
    review = record_challenger_stage_review(
        challenger["challenger_version"],
        "validation",
        "approved_to_next_stage",
        {"average_r": 0.1, "manual_review": True},
        manual_confirmation="CONFIRM_CHALLENGER_STAGE_REVIEW",
        reviewed_at="2026-08-22T13:00:00+00:00",
        path=path,
    )
    assert review["automatic_production_activation"] is False
    assert challenger_allowed_stage(challenger["challenger_version"], "holdout", path)["allowed"] is True
