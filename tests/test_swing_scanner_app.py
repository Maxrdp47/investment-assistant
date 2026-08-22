from pathlib import Path

import numpy as np
import pandas as pd

import app
from swing_scanner import SwingPrefilterThresholds, internal_swing_settings
from swing_universe import SwingUniverseAsset, SwingUniverseReport


def history() -> pd.DataFrame:
    index = pd.bdate_range("2025-08-01", periods=260)
    close = np.linspace(50.0, 100.0, 260) + np.sin(np.linspace(0, 20, 260))
    high = close + 0.4
    low = close - 0.4
    close[-1] = float(high[-21:-1].max()) * 1.005
    high[-1] = close[-1] + 0.4
    low[-1] = close[-1] - 0.4
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(260, 250_000.0),
        },
        index=index,
    )


def test_market_scan_connects_universe_prefilter_deep_analysis_and_release(monkeypatch) -> None:
    assets = tuple(
        SwingUniverseAsset(
            version="test-v1",
            ticker=f"T{index:04d}",
            name=f"Test {index}",
            asset_type="Aktie",
            region="USA",
            category="Test",
            active=True,
            liquidity_class="A",
            source_group="test",
        )
        for index in range(1_000)
    )
    report = SwingUniverseReport(assets, (), 1_000, 1_000, 0, 0, 0)
    frame = history()
    histories = {item.ticker: frame for item in assets[:850]}

    monkeypatch.setattr(app, "load_swing_universe", lambda path: report)
    monkeypatch.setattr(app, "load_trade_history", lambda: [])
    monkeypatch.setattr(app, "score_macro", lambda: app.ModuleScore(5.0, "Makro neutral", []))
    monkeypatch.setattr(
        app,
        "_evaluate_swing_asset",
        lambda item, data, **kwargs: {
            "approved": True,
            "symbol": item.ticker,
            "asset_name": item.name,
            "asset_type": item.asset_type,
            "entry_reference_eur": 100.0,
            "stop_eur": 95.0,
            "target_1_eur": 111.0,
            "target_2_eur": 118.0,
            "expected_value_r": None,
            "quality_score": 7.0,
            "crv": 2.2,
            "order_plan": {"plan_version": "test-v1", "plan_fingerprint": "initial"},
        },
    )

    result = app.scan_swing_market(
        internal_swing_settings(10_000.0),
        universe_path=Path("unused.csv"),
        prefilter_thresholds=SwingPrefilterThresholds(
            min_annualized_volatility_pct_stock=0.0,
            min_annualized_volatility_pct_etf=0.0,
            min_annualized_volatility_pct_crypto=0.0,
            max_annualized_volatility_pct_stock=1_000.0,
            max_annualized_volatility_pct_etf=1_000.0,
        ),
        histories_loader=lambda selected_assets: (histories, []),
    )

    assert result["statistics"]["universe_size"] == 1_000
    assert result["statistics"]["loaded_assets"] == 850
    assert result["statistics"]["fully_evaluated"] == 850
    assert result["statistics"]["approved_trades"] == 4
    assert len(result["approved"]) == 4
    assert len(result["shadow_signals"]) == 846
    assert all(
        item["forward_evidence_kind"] == "shadow_dynamic_risk_budget"
        for item in result["shadow_signals"]
    )
    assert result["statistics"]["strategy_qualified_total"] == 850
    assert any("Gesamtbudget" in item["Ablehnungsgründe"][0] for item in result["rejected"])
    assert all(item["position_size"]["quantity"] == 10 for item in result["approved"])
    assert all(item["order_plan"]["quantity"] == 10 for item in result["approved"])
    assert all(len(item["order_plan"]["plan_fingerprint"]) == 64 for item in result["approved"])
    assert result["asset_type_funnel"]["Aktie"]["fully_evaluated"] == 850
    assert result["asset_type_funnel"]["Aktie"]["setup_approved"] == 850
    assert result["asset_type_funnel"]["Aktie"]["portfolio_released"] == 4


def test_yfinance_multiindex_batch_is_split_per_ticker() -> None:
    index = pd.bdate_range("2026-01-01", periods=2)
    columns = pd.MultiIndex.from_product([["AAA", "BBB"], ["Close", "Volume"]])
    payload = pd.DataFrame(
        [[10.0, 100_000.0, 20.0, 200_000.0], [11.0, 110_000.0, 21.0, 210_000.0]],
        index=index,
        columns=columns,
    )

    result = app._histories_from_yfinance_batch(payload, ["AAA", "BBB"])

    assert set(result) == {"AAA", "BBB"}
    assert result["AAA"]["Close"].iloc[-1] == 11.0
    assert result["BBB"]["Volume"].iloc[-1] == 210_000.0


def test_active_trade_open_risk_uses_current_tightened_stop() -> None:
    risk = app.active_trade_open_risk_eur(
        [
            {
                "Status": "Aktiv",
                "Tatsächlicher Einstieg EUR": 100.0,
                "Tatsächliche Stückzahl": 10.0,
                "Initialer Stop EUR": 95.0,
                "Aktueller Stop EUR": 98.0,
            },
            {
                "Status": "Aktiv",
                "Tatsächlicher Einstieg EUR": 50.0,
                "Tatsächliche Stückzahl": 5.0,
                "Aktueller Stop EUR": 52.0,
            },
        ]
    )

    assert risk == 20.0
