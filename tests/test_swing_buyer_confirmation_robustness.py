from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

import swing_buyer_confirmation_robustness as robustness


def _feature(*, buyer: bool | None, alias: bool | None = None) -> dict[str, object]:
    alias = buyer if alias is None else alias
    return {
        "asset": {"asset_type": "EQUITIES", "region": "Europe"},
        "technical": {
            "market_phase": "trend",
            "volatility_regime": "medium",
            "close": 100.0,
            "atr_14": 5.0,
            "ema20_relative_to_ema50": 1.02,
        },
        "trend_quality": {"ema20_slope_atr_per_session": 0.1},
        "pullback": {
            "status": "available",
            "buyer_confirmation_close_above_prior_high": buyer,
            "bearish_candles": 3,
            "pullback_depth": 0.5,
            "pullback_duration_sessions": 5,
            "pullback_low": 92.0,
        },
        "candle_quality": {
            "close_above_prior_high": alias,
            "close_position_in_range": 0.75,
        },
        "relative_strength": {"relative_momentum_20d": 0.1},
        "market_structure": {"close_break": False},
    }


def _label() -> dict[str, object]:
    return {
        "entry": {
            "policy": robustness.BASELINE_ENTRY_POLICY,
            "entry_day": "2020-01-03",
            "raw": 100.0,
            "after_costs": 100.1,
            "cost_bps_one_way": 10.0,
            "retroactive_signal_close_entry": False,
        },
        "mfe_pct": 20.0,
        "mae_pct": -5.0,
        "time_to_mfe_sessions": 2,
        "time_to_exit_sessions": 3,
        "gap_events": [],
    }


def _experiment(result_r: float = 1.0) -> dict[str, object]:
    return {
        "results": {
            "pullback_low_atr_buffer": {
                "stop": 90.0,
                "exits": {
                    "fixed_2r": {
                        "result_r": result_r,
                        "status": "horizon_exit",
                        "sessions": 3,
                    }
                },
            }
        }
    }


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE broad_research_candidates(
              candidate_id TEXT PRIMARY KEY, symbol TEXT, signal_day TEXT,
              setup_family TEXT, dependency_cluster TEXT, research_split TEXT,
              feature_json TEXT
            );
            CREATE TABLE broad_research_labels(candidate_id TEXT PRIMARY KEY, label_json TEXT);
            CREATE TABLE broad_research_counterfactuals(candidate_id TEXT PRIMARY KEY, experiment_json TEXT);
            """
        )
        for candidate_id, split, buyer, result in (
            ("dev-t", "development", True, 1.0),
            ("dev-c", "development", False, -1.0),
            ("unseen", "validation", True, 99.0),
        ):
            connection.execute(
                "INSERT INTO broad_research_candidates VALUES(?,?,?,?,?,?,?)",
                (
                    candidate_id,
                    "AAA",
                    "2020-01-02",
                    "objective_pullback",
                    "cluster-1",
                    split,
                    json.dumps(_feature(buyer=buyer)),
                ),
            )
            connection.execute(
                "INSERT INTO broad_research_labels VALUES(?,?)",
                (candidate_id, json.dumps(_label())),
            )
            connection.execute(
                "INSERT INTO broad_research_counterfactuals VALUES(?,?)",
                (candidate_id, json.dumps(_experiment(result))),
            )


def _row(candidate_id: str, selected: bool, result: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "signal_day": "2020-01-02",
        "year": "2020",
        "symbol": "AAA",
        "dependency_cluster": "cluster-1",
        "asset_type": "EQUITIES",
        "region": "Europe",
        "market_phase": "trend",
        "volatility_regime": "medium",
        "buyer_confirmation": selected,
        "alias_confirmation": selected,
        "pullback_status": "available",
        "result_r": result,
        "bearish_ge3": "True",
        "pullback_depth_bin": "0450_0618",
        "pullback_duration_bin": "4_7",
        "relative_momentum_sign": "positive",
        "close_location_bin": "upper_third",
        "ema_trend": "True",
        "bos_close_break": "False",
    }


def test_reader_returns_only_development_pullbacks(tmp_path: Path) -> None:
    database = tmp_path / "broad.sqlite3"
    _database(database)
    before = database.stat().st_mtime_ns
    rows = robustness.read_development_rows(database)
    assert {row["candidate_id"] for row in rows} == {"dev-t", "dev-c"}
    assert database.stat().st_mtime_ns == before


def test_candidate_query_names_only_the_development_split() -> None:
    query = robustness.DEVELOPMENT_BUYER_QUERY.lower()
    assert "research_split='development'" in query
    assert "validation" not in query
    assert "holdout" not in query


def test_query_guard_rejects_any_non_development_candidate_read() -> None:
    with pytest.raises(ValueError, match="Development"):
        robustness._guard_development_query(
            "SELECT * FROM broad_research_candidates c WHERE c.research_split='holdout'"
        )


def test_geometry_and_pct_atr_metrics_are_correct(tmp_path: Path) -> None:
    database = tmp_path / "broad.sqlite3"
    _database(database)
    treatment = next(
        row for row in robustness.read_development_rows(database) if row["buyer_confirmation"]
    )
    assert treatment["entry_to_pullback_low_pct"] == pytest.approx(8.1 / 100.1 * 100)
    assert treatment["entry_to_pullback_low_atr"] == pytest.approx(8.1 / 5)
    assert treatment["stop_distance_pct"] == pytest.approx(10.1 / 100.1 * 100)
    assert treatment["stop_distance_atr"] == pytest.approx(10.1 / 5)
    assert treatment["target_distance_atr"] == pytest.approx(20.2 / 5)
    assert treatment["mfe_r"] == pytest.approx(20.02 / 10.1)
    assert treatment["mfe_atr"] == pytest.approx(20.02 / 5)
    assert treatment["mae_atr"] == pytest.approx(-5.005 / 5)


def test_wider_treatment_risk_cannot_be_called_denominator_inflation() -> None:
    treatment = {
        "risk_and_entry_geometry": {
            "stop_distance_pct": {"mean": 7.0, "median": 6.0},
            "stop_distance_atr": {"mean": 2.2, "median": 2.1},
            "result_pct": {"mean": 0.7, "median": -1.2},
            "mfe_pct": {"mean": 9.0, "median": 6.1},
            "mae_pct": {"mean": -7.5, "median": -5.2},
            "mfe_r": {"mean": 1.7, "median": 1.1},
            "mae_r": {"mean": -1.4, "median": -0.9},
        }
    }
    control = {
        "risk_and_entry_geometry": {
            "stop_distance_pct": {"mean": 3.7, "median": 2.5},
            "stop_distance_atr": {"mean": 1.2, "median": 1.0},
            "result_pct": {"mean": 0.2, "median": -1.1},
            "mfe_pct": {"mean": 9.1, "median": 6.1},
            "mae_pct": {"mean": -7.4, "median": -5.1},
            "mfe_r": {"mean": 7.8, "median": 2.3},
            "mae_r": {"mean": -6.4, "median": -1.9},
        }
    }
    result = robustness._geometry_assessment(treatment, control)
    assert result["treatment_has_wider_median_stop_distance"] is True
    assert result["r_denominator_mechanically_favors_treatment"] is False
    assert result["advantage_explained_exclusively_by_r_denominator"] is False


def test_matching_selection_is_outcome_blind() -> None:
    original = [
        _row("t1", True, 1.0),
        _row("t2", True, -1.0),
        _row("c1", False, 2.0),
        _row("c2", False, -2.0),
        _row("c3", False, 3.0),
    ]
    changed = [{**row, "result_r": 1000 - index} for index, row in enumerate(original)]
    first_t, first_c, first_report = robustness.outcome_blind_exact_match(
        original, keys=robustness.LEGACY_MATCH_KEYS, match_id="test"
    )
    next_t, next_c, next_report = robustness.outcome_blind_exact_match(
        changed, keys=robustness.LEGACY_MATCH_KEYS, match_id="test"
    )
    assert [row["candidate_id"] for row in first_t] == [row["candidate_id"] for row in next_t]
    assert [row["candidate_id"] for row in first_c] == [row["candidate_id"] for row in next_c]
    assert first_report["selection_uses_outcomes"] is False
    assert next_report["small_strata_equal_weighted"] is False


def test_matching_seed_sensitivity_never_selects_best_outcome_seed() -> None:
    rows = [
        _row("t1", True, 1.0),
        _row("t2", True, -0.5),
        _row("c1", False, -1.0),
        _row("c2", False, 0.1),
        _row("c3", False, 0.2),
    ]
    result = robustness.matching_seed_sensitivity(
        rows, keys=robustness.LEGACY_MATCH_KEYS, match_id="seed-test"
    )
    assert result["predeclared_replicate_n"] == 5
    assert result["seed_selected_using_outcomes"] is False
    assert len(result["replicates"]) == 5


def test_structural_missingness_is_not_control() -> None:
    rows = [_row("t", True, 1.0), _row("c", False, -1.0), _row("missing", False, 0.0)]
    rows[-1]["buyer_confirmation"] = None
    treatment, control, report = robustness.outcome_blind_exact_match(
        rows, keys=robustness.LEGACY_MATCH_KEYS, match_id="missing"
    )
    assert len(treatment) == len(control) == 1
    assert report["structurally_missing_n"] == 1


def test_alias_feature_is_counted_once() -> None:
    review = robustness._alias_review([_row("t", True, 1), _row("c", False, -1)])
    assert review == {
        "compared_n": 2,
        "mismatches": 0,
        "semantic_alias": True,
        "independent_confirmation_count": 1,
        "counted_twice": False,
    }


def test_entry_efficiency_has_fixed_mfe_thresholds_and_no_early_move_claim() -> None:
    rows = [
        {**_row("one", True, 1), "mfe_r": 2.1, "mae_r": -1, "giveback_r": 1.1},
        {**_row("two", True, -1), "mfe_r": 0.75, "mae_r": -0.5, "giveback_r": 1.75},
    ]
    efficiency = robustness.summarize_rows(rows, include_segments=False)["entry_efficiency"]
    assert efficiency["mfe_threshold_share"]["at_least_0.5r"] == 1
    assert efficiency["mfe_threshold_share"]["at_least_1r"] == 0.5
    assert efficiency["mfe_threshold_share"]["at_least_1.5r"] == 0.5
    assert efficiency["mfe_threshold_share"]["at_least_2r"] == 0.5
    assert efficiency["time_to_first_positive_available"] is False
    assert efficiency["earlier_positive_movement_claimed"] is False


def test_sensitivity_stress_is_not_execution_simulation() -> None:
    result = robustness.sensitivity_stress([_row("t", True, 0.2)])
    assert result["classification"] == "SENSITIVITY_STRESS"
    assert result["is_execution_simulation"] is False
    assert result["is_fill_or_broker_simulation"] is False


def test_conservative_execution_uses_next_open_and_no_intrabar_claim(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    scope = dataset / "scope"
    scope.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000.0, 1000.0, 1000.0],
        },
        index=pd.to_datetime(["2020-01-03", "2020-01-06", "2020-01-07"]),
    )
    frame.to_parquet(scope / "aaa.parquet")
    manifest = {
        "status": "finalized",
        "dataset_fingerprint": robustness.PROTECTED_DATASET_FINGERPRINT,
        "scopes": {
            "scope": {
                "contract": {"start": "2019-01-01", "end": None},
                "assets": {
                    "AAA": {
                        "status": "available",
                        "file": "scope/aaa.parquet",
                    }
                },
            }
        },
    }
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    base = {
        **_row("t", True, 0.0),
        "entry_day": "2020-01-03",
        "entry_raw": 100.0,
        "entry_price": 100.1,
        "cost_bps_one_way": 10.0,
        "stop": 90.0,
        "entry_gap_atr": 0.0,
    }
    control = {**base, "candidate_id": "c", "buyer_confirmation": False}
    result = robustness.execution_simulation([base], [control], dataset_root=dataset)
    assert result["classification"] == "EXECUTION_SIMULATION"
    assert result["is_sensitivity_stress"] is False
    assert result["entry_contract"] == robustness.BASELINE_ENTRY_POLICY
    assert result["intrabar_sequence_claimed"] is False
    assert result["variant_selected_by_outcomes"] is False
    assert result["treatment"]["cases_without_realistic_fill"] == 0


def test_c_recommendation_is_blocked_when_any_hard_criterion_fails() -> None:
    report = {"hard_decision_criteria": {"execution_positive": False}}
    with pytest.raises(ValueError, match="hard criteria"):
        robustness.apply_manual_decision(
            report,
            decision=robustness.DECISION_C_RECOMMENDATION,
            reason="not robust",
            decided_at="2026-08-25T00:00:00+02:00",
        )
    kept = robustness.apply_manual_decision(
        report,
        decision=robustness.DECISION_KEEP_B,
        reason="not robust",
        decided_at="2026-08-25T00:00:00+02:00",
    )
    assert kept["manual_decision"]["decision"] == "KEEP_B"
    assert kept["challenger_created"] is False
    assert kept["freeze_created"] is False
    assert kept["production_changed"] is False


def test_c_recommendation_only_drafts_one_rule_challenger() -> None:
    report = {"hard_decision_criteria": {"all_required": True}}
    reviewed = robustness.apply_manual_decision(
        report,
        decision=robustness.DECISION_C_RECOMMENDATION,
        reason="all predeclared Development checks passed",
        decided_at="2026-08-26T00:00:00+02:00",
    )
    draft = reviewed["challenger_specification_draft"]
    assert draft["single_rule"] == "Close[t] > High[t-1]"
    assert draft["setup_scope"] == "objective_pullback"
    assert draft["additional_filters"] == []
    assert draft["status"] == "draft_not_frozen_not_started"
    assert reviewed["challenger_created"] is False
    assert reviewed["freeze_created"] is False


def test_append_only_report_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    robustness.write_append_only_json({"report_fingerprint": "one"}, output)
    with pytest.raises(FileExistsError):
        robustness.write_append_only_json({"report_fingerprint": "two"}, output)


def test_report_fingerprint_detects_mutation() -> None:
    report = {"status": "complete"}
    report["report_fingerprint"] = robustness._fingerprint(report)
    assert robustness.verify_report_fingerprint(report) is True
    report["status"] = "changed"
    assert robustness.verify_report_fingerprint(report) is False


def test_contract_contains_no_feature_combination_or_threshold_search() -> None:
    assert robustness.BUYER_RULE == "Close[t] > High[t-1]"
    assert robustness.SETUP_SCOPE == "objective_pullback"
    assert robustness.CONSERVATIVE_EXTRA_SLIPPAGE_BPS_ONE_WAY == 5.0
    assert "rsi" not in robustness.STRICT_DEPENDENCY_MATCH_KEYS
    assert "fibonacci" not in robustness.STRICT_DEPENDENCY_MATCH_KEYS
