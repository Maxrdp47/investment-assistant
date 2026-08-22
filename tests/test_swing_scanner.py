from pathlib import Path

import numpy as np
import pandas as pd

from swing_scanner import (
    RISK_NOTICE,
    SwingPrefilterThresholds,
    asset_type_bias_audit,
    execute_multistage_scan,
    deterministic_rejection_control_sample,
    internal_swing_settings,
    load_risk_acknowledgement,
    quick_prefilter,
    save_risk_acknowledgement,
    swing_portfolio_cluster_audit,
)
from swing_universe import SwingUniverseAsset


def asset(index: int) -> SwingUniverseAsset:
    return SwingUniverseAsset(
        version="test-v1",
        ticker=f"T{index:04d}",
        name=f"Test Asset {index}",
        asset_type="Aktie",
        region="USA",
        category="Test",
        active=True,
        liquidity_class="A",
        source_group="test",
    )


def passing_history() -> pd.DataFrame:
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


def permissive_thresholds() -> SwingPrefilterThresholds:
    return SwingPrefilterThresholds(
        min_annualized_volatility_pct_stock=0.0,
        min_annualized_volatility_pct_etf=0.0,
        min_annualized_volatility_pct_crypto=0.0,
        max_annualized_volatility_pct_stock=1_000.0,
        max_annualized_volatility_pct_etf=1_000.0,
    )


def test_quick_prefilter_accepts_liquid_uptrend_breakout() -> None:
    result = quick_prefilter(asset(0), passing_history(), permissive_thresholds())

    assert result["passed"] is True
    assert result["metrics"]["structure"] in {"Ausbruch", "Rücksetzer"}


def test_etf_stock_bias_audit_measures_rates_without_changing_weights() -> None:
    audit = asset_type_bias_audit(
        {
            "Aktie": {
                "loaded_assets": 100,
                "prefilter_pass_rate_pct": 10.0,
                "prefilter_rejection_reasons": {"Kein Trend": 90},
                "prefilter_rejection_filters": {"uptrend": 90},
            },
            "ETF": {
                "loaded_assets": 40,
                "prefilter_pass_rate_pct": 40.0,
                "prefilter_rejection_reasons": {"Kein Setup": 24},
                "prefilter_rejection_filters": {"setup_structure": 24},
            },
        }
    )

    assert audit["status"] == "measured"
    assert audit["etf_to_stock_prefilter_rate_ratio"] == 4.0
    assert audit["stock_dominant_rejection_reason"] == "Kein Trend"
    assert audit["etf_dominant_rejection_reason"] == "Kein Setup"
    assert audit["automatic_weight_change"] is False
    assert audit["causal_claim"] is False
    assert audit["quota_or_asset_class_target"] is False
    assert audit["filter_contributions"][0]["filter"] in {"setup_structure", "uptrend"}


def test_prefilter_uses_volume_coverage_not_uncomparable_raw_share_count() -> None:
    frame = passing_history()
    frame["Volume"] = 10.0

    result = quick_prefilter(asset(0), frame, permissive_thresholds())

    assert result["passed"] is True
    assert result["metrics"]["positive_volume_observations_20"] == 20
    assert result["metrics"]["liquidity_hard_gate"] == "EUR-Turnover erst in der Tiefenanalyse"


def test_atr_normalization_rejects_a_far_extension_even_when_old_fixed_band_would_pass() -> None:
    frame = passing_history()
    prior_high = float(frame["High"].iloc[-21:-1].max())
    frame.loc[frame.index[-1], "Close"] = prior_high * 1.02
    frame.loc[frame.index[-1], "High"] = prior_high * 1.021
    frame.loc[frame.index[-1], "Low"] = prior_high * 1.019

    result = quick_prefilter(asset(0), frame, permissive_thresholds())

    assert result["passed"] is False
    assert result["rejection_filters"] == ["setup_structure"]


def test_every_serious_candidate_is_deeply_analyzed_without_top_n_cutoff() -> None:
    assets = [asset(index) for index in range(1_000)]
    frame = passing_history()
    histories = {item.ticker: frame for item in assets[:850]}

    result = execute_multistage_scan(
        assets,
        histories,
        lambda item, data: {
            "approved": True,
            "symbol": item.ticker,
            "expected_value_r": None,
            "quality_score": 7.0,
            "crv": 2.2,
        },
        thresholds=permissive_thresholds(),
    )

    statistics = result["statistics"]
    assert statistics["universe_size"] == 1_000
    assert statistics["loaded_assets"] == 850
    assert statistics["loaded_assets"] >= 800
    assert statistics["failed_downloads"] == 150
    assert statistics["prefilter_passed_total"] == 850
    assert statistics["fully_evaluated"] == 850
    assert statistics["approved_trades"] == 850
    assert result["deep_analysis_policy"] == "all_prefilter_passed"
    assert result["asset_type_funnel"]["Aktie"]["deep_coverage_pct"] == 100.0
    assert result["asset_type_funnel"]["Aktie"]["prefilter_rejection_reasons"] == {
        "Keine Kursdaten verfügbar.": 150
    }


def test_no_valid_trade_is_not_forced_and_multiple_valid_trades_are_supported() -> None:
    assets = [asset(index) for index in range(4)]
    histories = {item.ticker: passing_history() for item in assets}
    no_trade = execute_multistage_scan(
        assets,
        histories,
        lambda item, data: {"approved": False, "rejection_reasons": ["Qualitätsgate nicht erfüllt."]},
        thresholds=permissive_thresholds(),
    )
    multiple = execute_multistage_scan(
        assets,
        histories,
        lambda item, data: {
            "approved": int(item.ticker[-1]) % 2 == 0,
            "symbol": item.ticker,
            "rejection_reasons": ["Kein Setup."],
            "quality_score": 8.0,
            "crv": 2.5,
        },
        thresholds=permissive_thresholds(),
    )

    assert no_trade["approved"] == []
    assert len(no_trade["rejected"]) == 4
    assert len(multiple["approved"]) == 2
    assert len(multiple["rejected"]) == 2
    assert no_trade["asset_type_funnel"]["Aktie"]["final_rejection_filters"] == {"other": 4}


def test_single_deep_data_error_does_not_abort_other_assets() -> None:
    assets = [asset(index) for index in range(3)]
    histories = {item.ticker: passing_history() for item in assets}

    def evaluator(item: SwingUniverseAsset, data: pd.DataFrame) -> dict:
        if item.ticker == "T0001":
            raise RuntimeError("isolierter Datenfehler")
        return {
            "approved": True,
            "symbol": item.ticker,
            "expected_value_r": None,
            "quality_score": 7.0,
            "crv": 2.1,
        }

    result = execute_multistage_scan(
        assets,
        histories,
        evaluator,
        thresholds=permissive_thresholds(),
    )

    assert len(result["approved"]) == 2
    assert any("isolierter Datenfehler" in error for error in result["errors"])


def test_internal_risk_settings_are_conservative_and_not_user_supplied() -> None:
    settings = internal_swing_settings(10_000)

    assert settings["max_risk_pct"] == 0.5
    assert settings["max_total_open_risk_pct"] == 2.0
    assert "max_open_trades" not in settings
    assert settings["max_total_exposure_pct"] == 50.0
    assert settings["max_position_exposure_pct"] == 20.0
    assert settings["position_limit_mode"] == "dynamic_total_risk_and_exposure"
    assert "vollständigen Verlust" in RISK_NOTICE


def test_portfolio_cluster_audit_reports_correlation_without_auto_rejection() -> None:
    base = passing_history()
    opposite = base.copy()
    opposite["Close"] = list(reversed(base["Close"].to_list()))
    candidates = [
        {"symbol": "AAA", "universe_metadata": {"sector": "Banken", "region": "USA"}},
        {"symbol": "BBB", "universe_metadata": {"sector": "Banken", "region": "USA"}},
        {"symbol": "CCC", "universe_metadata": {"sector": "Technologie", "region": "Europa"}},
    ]

    audit = swing_portfolio_cluster_audit(
        candidates,
        {"AAA": base, "BBB": base.copy(), "CCC": opposite},
    )

    assert audit["status"] == "attention"
    assert audit["concentrated_sectors"] == {"Banken": 2}
    assert audit["high_correlation_pairs"][0]["left"] == "AAA"
    assert audit["high_correlation_pairs"][0]["right"] == "BBB"
    assert audit["automatic_rejection"] is False
    assert audit["automatic_weight_change"] is False


def test_rejection_control_sample_is_deterministic_bounded_and_never_a_trade() -> None:
    rejected = [
        {
            "Kontrollsnapshot": {
                "ticker": f"R{index}",
                "signal_day": "2026-08-14",
                "reference_price_original": 100.0 + index,
                "rejection_filters": ["crv"],
            }
        }
        for index in range(20)
    ]

    first = deterministic_rejection_control_sample(rejected, maximum_controls=5)
    second = deterministic_rejection_control_sample(list(reversed(rejected)), maximum_controls=5)

    assert first == second
    assert len(first) == 5
    assert all(item["control_only"] is True for item in first)
    assert all(item["not_a_trade_signal"] is True for item in first)


def test_risk_acknowledgement_is_written_atomically_and_invalid_content_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "preferences" / "risk.json"
    assert load_risk_acknowledgement(path) is False
    assert save_risk_acknowledgement(path, "2026-08-02T20:00:00+02:00") is True
    assert load_risk_acknowledgement(path) is True

    path.write_text("{invalid", encoding="utf-8")
    assert load_risk_acknowledgement(path) is False
