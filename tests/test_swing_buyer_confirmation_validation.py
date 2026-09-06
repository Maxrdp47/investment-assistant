from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

import swing_buyer_confirmation_validation as validation
from scripts import run_buyer_confirmation_validation as runner


def _freeze(*, expected_assets: int = 1) -> dict:
    payload = {
        "challenger_version": validation.CHALLENGER_VERSION,
        "freeze_version": validation.FREEZE_VERSION,
        "expected_assets_per_stage": expected_assets,
        "identity": {"dataset_fingerprint": validation.EXPECTED_DATASET_FINGERPRINT},
        "single_new_rule": {
            "name": "buyer_confirmation",
            "definition": validation.BUYER_RULE,
            "point_in_time": "completed signal candle t only",
        },
        "additional_filters": [],
        "rules_mutable_after_freeze": False,
    }
    return {**payload, "freeze_fingerprint": validation._fingerprint(payload)}


def _integrity_receipt() -> dict:
    return {
        "gate_version": "buyer-confirmation-pre-validation-integrity-2026.08.26-v1",
        "challenger_version": validation.CHALLENGER_VERSION,
        "status": "PASS",
    }


def _case(candidate_id: str, *, treatment: bool) -> dict:
    return {
        "candidate_id": candidate_id,
        "comparison_group": "treatment" if treatment else "control",
        "result_r": 1.0 if treatment else -1.0,
        "dependency_cluster": candidate_id,
        "signal_day": "2022-01-03",
        "ground_up_from_frozen_ohlcv": True,
        "development_case_read": False,
        "additional_filter_applied": False,
        "parameters_changed": False,
    }


def _asset_result(*, stage: str = "validation") -> dict:
    cases = [_case("candidate-treatment", treatment=True), _case("candidate-control", treatment=False)]
    return {
        "challenger_version": validation.CHALLENGER_VERSION,
        "freeze_fingerprint": _freeze()["freeze_fingerprint"],
        "research_stage": stage,
        "symbol": "AAA",
        "source_status": "ok",
        "rebuilt_candidates": 2,
        "applicable_cases": 2,
        "treatment_cases": 1,
        "control_cases": 1,
        "missing_cases": 0,
        "ground_up_from_frozen_ohlcv": True,
        "development_case_read": False,
        "parameters_changed": False,
        "cases": [{**row, "research_stage": stage} for row in cases],
    }


def test_append_only_store_resume_and_stage_order(tmp_path) -> None:
    database = tmp_path / "validation.sqlite3"
    freeze = validation.record_challenger_freeze(_freeze(), database)
    validation.record_integrity_receipt(_integrity_receipt(), database)

    assert validation.stage_allowed(freeze, "validation", database)["allowed"] is True
    assert validation.stage_allowed(freeze, "holdout", database)["allowed"] is False
    validation.open_stage(freeze, "validation", opened_at="2026-08-26T20:00:00+02:00", path=database)
    first = validation.record_stage_asset(_asset_result(), database)
    second = validation.record_stage_asset(_asset_result(), database)

    assert first["cases_inserted"] == 2
    assert second["already_complete"] is True
    assert second["cases_inserted"] == 0
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE buyer_stage_cases SET comparison_group='control'"
            )


def test_holdout_opens_only_after_complete_passing_validation(tmp_path) -> None:
    database = tmp_path / "validation.sqlite3"
    freeze = validation.record_challenger_freeze(_freeze(), database)
    validation.record_integrity_receipt(_integrity_receipt(), database)
    validation.open_stage(freeze, "validation", opened_at="freeze-time", path=database)
    validation.record_stage_asset(_asset_result(), database)
    gates = {"all_frozen_gates": True}
    review = {
        "evaluation_version": "buyer-confirmation-unseen-stage-evaluation-2026.08.26-v1",
        "challenger_version": validation.CHALLENGER_VERSION,
        "research_stage": "validation",
        "status": "VALIDATION_PASS",
        "completed_assets": 1,
        "expected_assets": 1,
        "gates": gates,
        "next_stage_allowed": True,
    }
    validation.record_stage_review(review, reviewed_at="review-time", path=database)

    assert validation.stage_allowed(freeze, "holdout", database)["allowed"] is True
    opened = validation.open_stage(
        freeze, "holdout", opened_at="holdout-time", path=database
    )
    assert opened["development_cases_read"] is False
    assert opened["rules_changed"] is False


def test_failed_validation_keeps_holdout_locked(tmp_path) -> None:
    database = tmp_path / "validation.sqlite3"
    freeze = validation.record_challenger_freeze(_freeze(), database)
    validation.record_integrity_receipt(_integrity_receipt(), database)
    validation.open_stage(freeze, "validation", opened_at="freeze-time", path=database)
    validation.record_stage_asset(_asset_result(), database)
    validation.record_stage_review(
        {
            "evaluation_version": "buyer-confirmation-unseen-stage-evaluation-2026.08.26-v1",
            "challenger_version": validation.CHALLENGER_VERSION,
            "research_stage": "validation",
            "status": "VALIDATION_FAIL",
            "completed_assets": 1,
            "expected_assets": 1,
            "gates": {"treatment_expectancy_positive": False},
            "next_stage_allowed": False,
        },
        reviewed_at="review-time",
        path=database,
    )

    assert validation.stage_allowed(freeze, "holdout", database)["allowed"] is False
    with pytest.raises(validation.BuyerConfirmationValidationError, match="locked"):
        validation.open_stage(freeze, "holdout", opened_at="later", path=database)


def test_build_stage_asset_uses_only_objective_pullback_and_buyer_rule(monkeypatch) -> None:
    def candidate(candidate_id: str, setup: str, split: str, buyer: bool) -> dict:
        return {
            "candidate_id": candidate_id,
            "candidate_fingerprint": f"fp-{candidate_id}",
            "symbol": "AAA",
            "signal_day": "2022-01-03",
            "dependency_cluster": f"dep-{candidate_id}",
            "setup_family": setup,
            "research_split": split,
            "feature": {
                "feature_fingerprint": f"feature-{candidate_id}",
                "asset": {"asset_type": "Aktie", "region": "Europa"},
                "technical": {
                    "market_phase": "Aufwärtstrend",
                    "volatility_regime": "normal",
                    "close": 101.0,
                    "atr_14": 2.0,
                    "ema20_relative_to_ema50": 1.01,
                },
                "pullback": {
                    "status": "available",
                    "buyer_confirmation_close_above_prior_high": buyer,
                    "pullback_low": 95.0,
                    "bearish_candles": 2,
                    "pullback_depth": 0.5,
                    "pullback_duration_sessions": 4,
                },
                "candle_quality": {
                    "close_above_prior_high": buyer,
                    "close_position_in_range": 0.8,
                },
                "relative_strength": {"relative_momentum_20d": 0.1},
                "trend_quality": {"ema20_slope_atr_per_session": 0.1},
                "market_structure": {"close_break": False},
            },
        }

    candidates = [
        candidate("treatment", "objective_pullback", "validation", True),
        candidate("control", "objective_pullback", "validation", False),
        candidate("breakout", "objective_breakout", "validation", True),
        candidate("holdout", "objective_pullback", "holdout", True),
    ]
    labels = []
    experiments = []
    for item in candidates:
        candidate_id = item["candidate_id"]
        labels.append(
            {
                "candidate_id": candidate_id,
                "label_fingerprint": f"label-{candidate_id}",
                "entry": {
                    "policy": validation.BASELINE_ENTRY_POLICY,
                    "entry_day": "2022-01-04",
                    "raw": 100.0,
                    "after_costs": 100.1,
                    "cost_bps_one_way": 10.0,
                    "retroactive_signal_close_entry": False,
                },
                "mfe_pct": 2.0,
                "mae_pct": -1.0,
                "time_to_mfe_sessions": 2,
                "time_to_exit_sessions": 4,
                "gap_events": [],
            }
        )
        experiments.append(
            {
                "candidate_id": candidate_id,
                "experiment_fingerprint": f"experiment-{candidate_id}",
                "results": {
                    "pullback_low_atr_buffer": {
                        "stop": 94.5,
                        "exits": {"fixed_2r": {"result_r": 2.0, "status": "target", "sessions": 4}},
                    }
                },
            }
        )
    monkeypatch.setattr(
        validation,
        "build_asset_broad_research",
        lambda *args, **kwargs: {
            "status": "ok",
            "candidates": candidates,
            "labels": labels,
            "counterfactuals": experiments,
        },
    )

    result = validation.build_stage_asset(
        _freeze(), {"ticker": "AAA"}, validation.pd.DataFrame(), research_stage="validation"
    )

    assert [row["candidate_id"] for row in result["cases"]] == ["treatment", "control"]
    assert [row["comparison_group"] for row in result["cases"]] == ["treatment", "control"]
    assert all(row["additional_filter_applied"] is False for row in result["cases"])
    assert all(row["development_case_read"] is False for row in result["cases"])


def test_freeze_contract_contains_no_extra_filters(monkeypatch, tmp_path) -> None:
    development = {
        "manual_decision": {"decision": "C_RECOMMENDATION", "failed_hard_criteria": []},
        "challenger_specification_draft": {
            "setup_scope": validation.SETUP_SCOPE,
            "single_rule": validation.BUYER_RULE,
            "entry_contract": validation.BASELINE_ENTRY_POLICY,
            "stop_contract": validation.STOP_CONTRACT,
            "exit_contract": validation.EXIT_CONTRACT,
            "additional_filters": [],
        },
        "freeze_created": False,
        "challenger_created": False,
        "data_access": {"validation_opened": False, "holdout_opened": False},
    }
    development["report_fingerprint"] = validation._fingerprint(development)
    development_path = tmp_path / "development.json"
    development_path.write_text(json.dumps(development), encoding="utf-8")
    broad_path = tmp_path / "broad.sqlite3"
    broad_path.write_bytes(b"read-only-reference")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"status": "finalized", "dataset_fingerprint": validation.EXPECTED_DATASET_FINGERPRINT}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        validation, "EXPECTED_DEVELOPMENT_REPORT_FINGERPRINT", development["report_fingerprint"]
    )
    monkeypatch.setattr(validation, "_broad_reference", lambda path: {"manifest_fingerprint": "broad"})
    monkeypatch.setattr(validation, "broad_research_code_fingerprint", lambda: validation.EXPECTED_CODE_FINGERPRINT)
    monkeypatch.setattr(
        validation,
        "broad_research_feature_contract_fingerprint",
        lambda: validation.EXPECTED_FEATURE_FINGERPRINT,
    )

    freeze = validation.build_challenger_freeze(
        development_report_path=development_path,
        broad_path=broad_path,
        dataset_manifest_path=manifest_path,
        expected_assets=2520,
        frozen_at="2026-08-26T20:00:00+02:00",
    )

    assert freeze["setup_scope"] == "objective_pullback"
    assert freeze["single_new_rule"]["definition"] == "Close[t] > High[t-1]"
    assert freeze["additional_filters"] == []
    assert freeze["rules_mutable_after_freeze"] is False
    assert freeze["validation_opened"] is False
    assert freeze["holdout_opened"] is False


def test_real_process_conflict_does_not_open_validation(monkeypatch, tmp_path) -> None:
    freeze = _freeze()
    opened = []
    monkeypatch.setattr(runner, "load_challenger_freeze", lambda path: freeze)
    monkeypatch.setattr(runner, "_protected_sources_unchanged", lambda *args, **kwargs: True)
    monkeypatch.setattr(runner, "stage_allowed", lambda *args, **kwargs: {"allowed": True})
    monkeypatch.setattr(
        runner,
        "validation_store_status",
        lambda path: {"stages": {"validation": {"opened": False, "decision": None}}},
    )
    monkeypatch.setattr(runner, "load_campaign_config", lambda path: {})
    monkeypatch.setattr(
        runner,
        "historical_research_runtime_gate",
        lambda config, project_root: {
            "run_allowed": False,
            "reason": "BLOCKED_REAL_CONFLICT",
            "active_production": ["Forecast"],
        },
    )
    monkeypatch.setattr(runner, "open_stage", lambda *args, **kwargs: opened.append(True))
    args = SimpleNamespace(
        database=tmp_path / "store.sqlite3",
        broad_database=tmp_path / "broad.sqlite3",
        manifest=tmp_path / "manifest.json",
        development_report=tmp_path / "development.json",
        stage="validation",
        campaign_config=tmp_path / "campaign.json",
        project_root=tmp_path,
    )

    result = runner._run_stage(args, [{"ticker": "AAA"}])

    assert result["stage_run_skipped"] == "blocked_real_conflict"
    assert opened == []
