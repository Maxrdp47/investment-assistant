from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest

from crypto_r4h_features import build_crypto_r4h_features, load_contract


def _bars(days: int = 110) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=days, freq="D")
    close = pd.Series(100 + np.arange(days) * 0.3 + np.sin(np.arange(days) / 3), index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.4,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1000 + np.arange(days),
            "SegmentId": np.zeros(days, dtype=int),
        },
        index=index,
    )


def test_r4h_prefix_causality_and_lagged_btc_alignment() -> None:
    asset = _bars()
    btc = _bars()
    btc[["Open", "High", "Low", "Close"]] *= 2
    features = build_crypto_r4h_features(asset, btc)
    day = asset.index[65]
    prior = btc.index[64]
    assert features.loc[day, "btc_known_date"] == prior.date().isoformat()
    assert features.loc[day, "btc_lagged_return_20"] == pytest.approx(
        btc.loc[prior, "Close"] / btc.iloc[44]["Close"] - 1
    )
    assert features.loc[day, "asset_lagged_return_20"] == pytest.approx(
        asset.loc[prior, "Close"] / asset.iloc[44]["Close"] - 1
    )
    changed_asset = asset.copy(deep=True)
    changed_btc = btc.copy(deep=True)
    changed_asset.loc[asset.index[80]:, ["Open", "High", "Low", "Close"]] *= 1.3
    changed_btc.loc[btc.index[80]:, ["Open", "High", "Low", "Close"]] *= 1.4
    replay = build_crypto_r4h_features(changed_asset, changed_btc)
    pd.testing.assert_frame_equal(features.iloc[:80], replay.iloc[:80])
    assert features["strategy_filter_created"].eq(False).all()
    assert pd.testing.assert_frame_equal(asset, _bars()) is None


def test_r4h_missing_btc_day_and_segment_boundary_do_not_bridge() -> None:
    asset = _bars()
    btc = _bars()
    btc = btc.drop(index=btc.index[60])
    btc.loc[btc.index[60]:, "SegmentId"] = 1
    features = build_crypto_r4h_features(asset, btc)
    assert pd.isna(features.iloc[61]["btc_lagged_return_20"])
    assert pd.isna(features.iloc[61]["relative_to_btc_20"])
    asset.loc[asset.index[70]:, "SegmentId"] = 1
    split = build_crypto_r4h_features(asset, _bars())
    assert pd.isna(split.iloc[70]["asset_lagged_return_20"])
    assert pd.isna(split.iloc[70]["asset_volatility_20"])
    assert pd.isna(split.iloc[70]["reported_volume_ratio_20"])
    assert pd.isna(split.iloc[70]["close_vs_prior20_high_pct"])


def test_r4h_bad_source_and_contract_fail_closed(tmp_path) -> None:
    asset = _bars()
    btc = _bars()
    invalid = asset.copy(deep=True)
    invalid.iloc[3, invalid.columns.get_loc("Low")] = 1000
    with pytest.raises(ValueError, match="envelope"):
        build_crypto_r4h_features(invalid, btc)
    invalid = asset.copy(deep=True)
    invalid = invalid.drop(index=invalid.index[30])
    with pytest.raises(ValueError, match="missing UTC day"):
        build_crypto_r4h_features(invalid, btc)
    contract, _ = load_contract()
    altered = copy.deepcopy(contract)
    altered["onchain_available"] = True
    contract_path = tmp_path / "changed.json"
    contract_path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="scope changed"):
        build_crypto_r4h_features(asset, btc, contract_path=contract_path)
