from __future__ import annotations

import pytest

from swing_ml_dataset_contract import (
    SwingMLDatasetContractError,
    build_swing_ml_dataset_row,
    swing_ml_dataset_manifest,
)


def _case() -> dict:
    return {
        "case_id": "case-1",
        "logical_case_id": "logical-1",
        "case_data_fingerprint": "data-v1",
        "signal_at": "2025-01-10T23:59:00+00:00",
        "research_split": "holdout",
        "result_r": -1.0,
        "snapshot": {
            "asset": {"ticker": "TEST", "asset_type": "Aktie", "region": "USA"},
            "strategy": {"strategy_version": "frozen-v1", "setup_type": "pullback"},
            "signal_features": {"rsi_14": 48.0, "atr_14": None},
        },
        "observational_features": {"values": {"ema_20": 101.0}},
        "events": [
            {
                "event_type": "stop_reached",
                "occurred_at": "2025-01-15T00:00:00+00:00",
                "payload": {
                    "result_r": -1.0,
                    "result_pct": -2.0,
                    "maximum_favorable_excursion_pct": 0.4,
                    "maximum_adverse_excursion_pct": -2.1,
                },
            }
        ],
    }


def test_features_and_later_labels_are_physically_separate() -> None:
    row = build_swing_ml_dataset_row(
        _case(),
        additional_features={"cot_z_score": 1.2},
        feature_sources=[
            {"source": "CFTC", "published_at": "2025-01-10T20:00:00+00:00"}
        ],
    )

    assert row["features"]["cot_z_score"] == 1.2
    assert "result_r" not in row["features"]
    assert row["labels"]["result_r"] == -1.0
    assert row["labels"]["mfe_pct"] == 0.4
    assert row["feature_missing"] == ["atr_14"]
    assert row["shadow_only"] is True
    assert row["random_split_allowed"] is False


def test_future_source_is_rejected_fail_closed() -> None:
    with pytest.raises(SwingMLDatasetContractError, match="nach dem Featurezeitpunkt"):
        build_swing_ml_dataset_row(
            _case(),
            feature_sources=[
                {"source": "future", "available_at": "2025-01-11T00:00:00+00:00"}
            ],
        )


def test_target_leak_in_additional_features_is_rejected() -> None:
    with pytest.raises(SwingMLDatasetContractError, match="Zielvariablen"):
        build_swing_ml_dataset_row(_case(), additional_features={"mfe_r": 1.5})


def test_row_and_manifest_are_reproducible_and_never_production_ready() -> None:
    first = build_swing_ml_dataset_row(_case())
    second = build_swing_ml_dataset_row(_case())
    manifest = swing_ml_dataset_manifest([first, second])

    assert first["row_fingerprint"] == second["row_fingerprint"]
    assert manifest["rows"] == 2
    assert manifest["split_policy"] == "time_based_purged_walk_forward_only"
    assert manifest["production_activation_allowed"] is False

