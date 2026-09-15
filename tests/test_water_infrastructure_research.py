from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import water_infrastructure_research as water


def _frame(*, mutate_future: bool = False) -> pd.DataFrame:
    index = pd.bdate_range("2014-01-02", periods=900)
    close = np.full(len(index), 100.0)
    close[300:361] = 70.0
    close[361:] = np.linspace(71.0, 95.0, len(index) - 361)
    if mutate_future:
        close[500:] = close[500:] * 9.0
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(len(index), 1_000_000.0),
        },
        index=index,
    )


def _frames() -> dict[str, pd.DataFrame]:
    return {ticker: _frame() for ticker in ("XYL", "BMI", "PNR", "SPY", "PHO")}


def _contract(tmp_path: Path | None = None) -> dict[str, object]:
    contract = water.load_contract()
    if tmp_path is not None:
        contract = deepcopy(contract)
        contract["runtime"] = {
            **contract["runtime"],
            "dataset_store": str(tmp_path / "prices.sqlite3"),
            "result_store": str(tmp_path / "results.sqlite3"),
            "artifact_root": str(tmp_path / "artifacts"),
            "process_lock": str(tmp_path / "process.lock"),
            "global_research_lock": str(tmp_path / "global.lock"),
        }
    return contract


def test_contract_is_one_attempt_and_keeps_all_later_stages_closed() -> None:
    contract = water.load_contract()
    assert contract["attempt_count"] == 1
    assert contract["data"]["symbols"] == ["XYL", "BMI", "PNR", "SPY", "PHO"]
    assert contract["primary_rule"]["drawdown_from_prior_252_close_high_lte"] == -0.15
    assert contract["primary_rule"]["breakout_close_above_prior_n_close_high"] == 60
    assert contract["development_gate"]["all_criteria_required"] is True
    for stage in ("external", "forward", "paper", "shadow", "broker", "orders", "production"):
        assert contract["stage_authorization"][stage] is False


def test_signal_features_do_not_use_future_bars() -> None:
    base = _frame()
    changed = _frame(mutate_future=True)
    first = water._feature_frame(base, 60, base)
    second = water._feature_frame(changed, 60, changed)
    cutoff = base.index[450]
    columns = ["prior_252_high", "prior_breakout_high", "drawdown", "first_cross", "realized_volatility_20"]
    pd.testing.assert_frame_equal(first.loc[:cutoff, columns], second.loc[:cutoff, columns])


def test_price_snapshot_is_deterministic_append_only_and_idempotent(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    path = tmp_path / "prices.sqlite3"
    first = water.write_price_snapshot(
        _frames(), contract=contract, path=path, retrieved_at="2026-09-15T00:00:00+00:00"
    )
    replay = water.write_price_snapshot(
        _frames(), contract=contract, path=path, retrieved_at="2026-09-15T01:00:00+00:00"
    )
    assert replay["idempotent_replay"] is True
    assert replay["dataset_fingerprint"] == first["dataset_fingerprint"]
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE price_bars SET close=close+1")


def test_changed_snapshot_cannot_reuse_same_version(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    path = tmp_path / "prices.sqlite3"
    water.write_price_snapshot(_frames(), contract=contract, path=path)
    changed = _frames()
    changed["XYL"] = changed["XYL"].copy()
    changed["XYL"].iloc[-1, changed["XYL"].columns.get_loc("Close")] += 1.0
    with pytest.raises(RuntimeError, match="differs"):
        water.write_price_snapshot(changed, contract=contract, path=path)


def test_matched_controls_are_outcome_blind() -> None:
    frame = _frame()
    featured = water._feature_frame(frame, 60, frame)
    positions = water._eligible_positions(
        featured,
        stage_start=pd.Timestamp("2014-01-01"),
        stage_end=pd.Timestamp("2017-12-31"),
        drawdown=-0.15,
        horizon=60,
    )
    before = water._matched_controls(
        featured,
        positions,
        stage_start=pd.Timestamp("2014-01-01"),
        stage_end=pd.Timestamp("2017-12-31"),
        horizon=20,
    )
    changed = featured.copy()
    changed["Open"] = changed["Open"] * np.linspace(1.0, 4.0, len(changed))
    changed["Close"] = changed["Close"] * np.linspace(1.0, 7.0, len(changed))
    after = water._matched_controls(
        changed,
        positions,
        stage_start=pd.Timestamp("2014-01-01"),
        stage_end=pd.Timestamp("2017-12-31"),
        horizon=20,
    )
    assert before == after


def test_effective_n_uses_conservative_trading_session_spacing() -> None:
    rows = [
        {"ticker": "XYL", "entry_day": "2020-01-01"},
        {"ticker": "XYL", "entry_day": "2020-02-20"},
        {"ticker": "XYL", "entry_day": "2020-04-05"},
    ]
    assert water._effective_nonoverlap_n(rows, horizon=60) == 2


def test_development_underpowered_is_terminal_inconclusive_and_does_not_open_validation(
    tmp_path: Path,
) -> None:
    contract = _contract(tmp_path)
    manifest = water.write_price_snapshot(_frames(), contract=contract, path=tmp_path / "prices.sqlite3")
    frames, stored = water.read_price_snapshot(tmp_path / "prices.sqlite3", contract)
    assert stored["dataset_fingerprint"] == manifest["dataset_fingerprint"]
    water.freeze_research_contract(
        tmp_path / "results.sqlite3",
        contract=contract,
        dataset_manifest=manifest,
        code_fingerprint="a" * 64,
        frozen_at="2026-09-15T00:00:00+00:00",
    )
    report = water.persist_stage(
        tmp_path / "results.sqlite3",
        frames=frames,
        contract=contract,
        stage="development",
        run_at="2026-09-15T00:01:00+00:00",
    )
    assert report["decision"] == "DEVELOPMENT_INCONCLUSIVE"
    assert report["validity_gate"]["performance_grade_allowed"] is False
    assert report["validation_opened"] is False
    assert report["holdout_opened"] is False
    status = water.store_status(tmp_path / "results.sqlite3")
    assert status["challenger_freezes"] == []
    assert status["stages"]["validation"] is None
    with pytest.raises(RuntimeError, match="Validation is closed"):
        water.persist_stage(
            tmp_path / "results.sqlite3",
            frames=frames,
            contract=contract,
            stage="validation",
        )


def test_resume_does_not_duplicate_cases_or_reviews(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    manifest = water.write_price_snapshot(_frames(), contract=contract, path=tmp_path / "prices.sqlite3")
    frames, _ = water.read_price_snapshot(tmp_path / "prices.sqlite3", contract)
    water.freeze_research_contract(
        tmp_path / "results.sqlite3",
        contract=contract,
        dataset_manifest=manifest,
        code_fingerprint="b" * 64,
    )
    first = water.persist_stage(
        tmp_path / "results.sqlite3", frames=frames, contract=contract, stage="development"
    )
    first_count = water.store_status(tmp_path / "results.sqlite3")["case_n"]["development"]
    replay = water.persist_stage(
        tmp_path / "results.sqlite3", frames=frames, contract=contract, stage="development"
    )
    assert replay["idempotent_replay"] is True
    assert replay["review_fingerprint"] == first["review_fingerprint"]
    assert water.store_status(tmp_path / "results.sqlite3")["case_n"]["development"] == first_count


def test_append_only_json_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    stored = water.write_append_only_artifact(path, {"status": "one"})
    assert water.write_append_only_artifact(path, {"status": "one"})["idempotent_replay"] is True
    with pytest.raises(RuntimeError, match="Append-only"):
        water.write_append_only_artifact(path, {"status": "two"})
    assert json.loads(path.read_text(encoding="utf-8"))["artifact_fingerprint"] == stored["artifact_fingerprint"]
