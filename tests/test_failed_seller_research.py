from __future__ import annotations

import copy
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from failed_seller_research import (
    FailedSellerContractError,
    build_failed_seller_feature,
    close_location,
    evaluate_failed_seller_development,
    failed_seller_feature_contract,
    finalize_run_payload,
    store_failed_seller_run,
)


def _history() -> pd.DataFrame:
    # Prefix provides causal ATR history.  The final six bars contain exactly
    # two fully recovered seller pushes before the signal bar.
    dates = pd.date_range("2020-01-01", periods=26, freq="D")
    rows = [
        {"Open": 100.0, "High": 102.0, "Low": 99.0, "Close": 101.0, "Volume": 1000.0}
        for _ in range(20)
    ]
    rows.extend(
        [
            {"Open": 108.0, "High": 110.0, "Low": 100.0, "Close": 109.0, "Volume": 1000.0},
            {"Open": 108.0, "High": 109.0, "Low": 98.0, "Close": 100.0, "Volume": 1200.0},
            {"Open": 101.0, "High": 111.0, "Low": 99.0, "Close": 110.0, "Volume": 1300.0},
            {"Open": 109.0, "High": 110.0, "Low": 97.0, "Close": 99.0, "Volume": 1250.0},
            {"Open": 100.0, "High": 112.0, "Low": 98.0, "Close": 111.0, "Volume": 1400.0},
            {"Open": 111.0, "High": 114.0, "Low": 108.0, "Close": 113.0, "Volume": 1500.0},
        ]
    )
    return pd.DataFrame(rows, index=dates)


def _feature(frame: pd.DataFrame | None = None) -> dict[str, object]:
    history = _history() if frame is None else frame
    return build_failed_seller_feature(
        history,
        pullback_start_day=history.index[20],
        signal_day=history.index[25],
        candidate_id="candidate-1",
        dataset_fingerprint="frozen-dataset",
    )


def test_definition_is_frozen_to_exact_kb_thresholds_without_dynamic_mining() -> None:
    contract = failed_seller_feature_contract()
    assert contract["isolated_variants"] == {
        "seller_attempt_count_exact": [1, 2],
        "confirmation_close_location_gte": [0.7, 0.8],
    }
    assert contract["dynamic_threshold_mining"] is False
    assert contract["combination_policy"].startswith("not_evaluated")


def test_feature_counts_two_deterministic_failed_pushes_and_keeps_labels_separate() -> None:
    feature = _feature()
    assert feature["failed_seller_attempt_count"] == 2
    assert feature["seller_push_count"] == 2
    assert all(item["failed_seller_attempt"] for item in feature["pushes"])
    assert feature["isolated_variant_flags"]["failed_seller_attempts_exactly_2"] is True
    assert feature["future_bars_used"] == 0
    assert feature["labels_present"] is False
    assert "result_r" not in str(feature)


def test_future_bars_cannot_change_feature_at_fixed_signal_cutoff() -> None:
    base = _history()
    first = _feature(base)
    future = pd.DataFrame(
        [{"Open": 1.0, "High": 1000.0, "Low": 0.5, "Close": 900.0, "Volume": 999999.0}],
        index=[base.index[-1] + pd.Timedelta(days=1)],
    )
    second = _feature(pd.concat([base, future]))
    assert first == second


def test_close_location_zero_range_is_missing_and_variants_are_isolated() -> None:
    assert close_location(close=10, low=10, high=10) is None
    assert close_location(close=9, low=10, high=11) is None
    rows = [
        {
            "feature_status": "available",
            "variant_flags": _feature()["isolated_variant_flags"],
            "result_r": 0.5,
            "mfe_pct": 3.0,
            "mae_pct": -1.0,
            "issuer_id": None,
            "dependency_status": "UNKNOWN",
            "listing_id": "listing-a",
            "asset_class": "EQUITIES",
            "year": "2020",
            "regime": "normal",
            "region": "Europe",
            "market_scope": "EQUITIES",
        },
        {
            "feature_status": "available",
            "variant_flags": {
                "failed_seller_attempts_exactly_1": True,
                "failed_seller_attempts_exactly_2": False,
                "confirmation_close_location_gte_0_70": False,
                "confirmation_close_location_gte_0_80": False,
            },
            "result_r": -1.0,
            "mfe_pct": 1.0,
            "mae_pct": -4.0,
            "issuer_id": None,
            "dependency_status": "UNKNOWN",
            "listing_id": "listing-b",
            "asset_class": "ETF",
            "year": "2020",
            "regime": "high",
            "region": "USA",
            "market_scope": "ETF",
        },
    ]
    report = evaluate_failed_seller_development(rows)
    assert report["research_attempt_count"] == 4
    assert report["combination_variants_evaluated"] == []
    assert report["dependency"]["effective_n_known_clusters_only"] == 0
    assert report["result_direction"] == "INCONCLUSIVE"


def test_append_only_run_store_is_idempotent(tmp_path: Path) -> None:
    feature = _feature()
    run = finalize_run_payload(
        {
            "run_id": "failed-seller-run-1",
            "attempts": ["attempts_exactly_1", "attempts_exactly_2"],
            "status": "complete",
        }
    )
    path = tmp_path / "failed.sqlite3"
    assert store_failed_seller_run(run, [feature], path=path) == {
        "run_inserted": 1,
        "features_inserted": 1,
    }
    assert store_failed_seller_run(copy.deepcopy(run), [feature], path=path) == {
        "run_inserted": 0,
        "features_inserted": 0,
    }
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM failed_seller_features")


def test_missing_signal_or_pullback_start_fails_closed() -> None:
    history = _history()
    with pytest.raises(FailedSellerContractError):
        build_failed_seller_feature(
            history,
            pullback_start_day="1999-01-01",
            signal_day=history.index[-1],
            candidate_id="bad",
            dataset_fingerprint="frozen",
        )
