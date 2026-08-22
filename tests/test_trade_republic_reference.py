from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from trade_republic_reference import (
    TR_STATUS_NOT_TRADEABLE,
    TR_STATUS_TRADEABLE,
    TR_STATUS_UNKNOWN,
    build_trade_republic_execution_plan,
    record_trade_republic_price,
    record_trade_republic_status,
    trade_republic_price,
    trade_republic_reference,
    trade_republic_reference_store_audit,
)


ASSET = {
    "ticker": "TEST",
    "name": "Test AG",
    "isin": "DE000TEST001",
    "exchange": "XETRA",
    "original_currency": "EUR",
}


def mark_tradeable(path, asset: dict = ASSET, recorded_at=None) -> None:
    record_trade_republic_status(
        asset,
        TR_STATUS_TRADEABLE,
        tr_ticker="TEST-TR",
        tr_isin="DE000TEST001",
        tr_exchange="TR TEST VENUE",
        recorded_at=recorded_at,
        path=path,
    )


def test_unknown_is_safe_default_and_never_guesses_tradability(tmp_path) -> None:
    reference = trade_republic_reference(ASSET, tmp_path / "missing.sqlite3")

    assert reference["status"] == TR_STATUS_UNKNOWN
    assert reference["automatic_detection"] is False
    assert reference["broker_connection"] is False


def test_manual_status_is_listing_specific_and_persistent(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    mark_tradeable(path)
    other_exchange = {**ASSET, "exchange": "NASDAQ"}
    record_trade_republic_status(other_exchange, TR_STATUS_NOT_TRADEABLE, path=path)

    xetra = trade_republic_reference(ASSET, path)
    nasdaq = trade_republic_reference(other_exchange, path)

    assert xetra["status"] == TR_STATUS_TRADEABLE
    assert xetra["tr_listing"]["isin"] == ASSET["isin"]
    assert nasdaq["status"] == TR_STATUS_NOT_TRADEABLE
    assert xetra["analysis_listing_key"] != nasdaq["analysis_listing_key"]


def test_same_ticker_and_exchange_with_other_isin_is_a_different_listing(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    mark_tradeable(path)
    other_instrument = {**ASSET, "isin": "DE000OTHER01"}

    reference = trade_republic_reference(other_instrument, path)

    assert reference["status"] == TR_STATUS_UNKNOWN
    assert reference["analysis_listing_key"] != trade_republic_reference(ASSET, path)[
        "analysis_listing_key"
    ]


def test_tradeable_mapping_rejects_other_isin_and_incomplete_listing(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    with pytest.raises(ValueError, match="stimmt nicht"):
        record_trade_republic_status(
            ASSET,
            TR_STATUS_TRADEABLE,
            tr_ticker="OTHER",
            tr_isin="US000OTHER01",
            tr_exchange="TR TEST VENUE",
            path=path,
        )
    with pytest.raises(ValueError, match="TR-Ticker, ISIN und Handelsplatz"):
        record_trade_republic_status(
            ASSET,
            TR_STATUS_TRADEABLE,
            tr_ticker="TEST-TR",
            tr_isin=ASSET["isin"],
            tr_exchange="",
            path=path,
        )


def test_manual_isin_override_supports_unknown_metadata_without_ticker_only_match(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    asset_without_isin = {**ASSET, "isin": ""}
    record_trade_republic_status(
        asset_without_isin,
        TR_STATUS_TRADEABLE,
        analysis_isin=ASSET["isin"],
        tr_ticker="TEST-TR",
        tr_isin=ASSET["isin"],
        tr_exchange="TR TEST VENUE",
        path=path,
    )

    reference = trade_republic_reference(asset_without_isin, path)

    assert reference["status"] == TR_STATUS_TRADEABLE
    assert reference["analysis_listing"]["isin"] == ASSET["isin"]
    assert reference["analysis_listing"]["isin_source"] == "Manuell verifiziert"
    assert trade_republic_reference(ASSET, path)["status"] == TR_STATUS_TRADEABLE


def test_tr_price_is_exact_listing_manual_and_expires_without_yahoo_fallback(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    mark_tradeable(path, recorded_at=now - timedelta(minutes=1))
    with pytest.raises(ValueError, match="zeitgleich"):
        record_trade_republic_price(
            ASSET,
            120.0,
            analysis_comparison_price_eur=0,
            observed_at=now,
            path=path,
        )
    record_trade_republic_price(
        ASSET,
        120.0,
        analysis_comparison_price_eur=100.0,
        observed_at=now,
        path=path,
    )

    fresh = trade_republic_price(ASSET, now=now + timedelta(minutes=5), path=path)
    stale = trade_republic_price(ASSET, now=now + timedelta(minutes=16), path=path)

    assert fresh["available"] is True
    assert fresh["price_eur"] == 120.0
    assert fresh["source"] == "Manuell aus Trade Republic erfasst"
    assert stale["available"] is False
    assert stale["label"] == "TR-Preis nicht verfügbar"
    assert stale["price_eur"] is None


def test_execution_plan_uses_one_verified_tr_listing_for_every_absolute_level(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    mark_tradeable(path, recorded_at=now - timedelta(minutes=1))
    record_trade_republic_price(
        ASSET,
        120.0,
        analysis_comparison_price_eur=100.0,
        observed_at=now,
        path=path,
    )
    reference = trade_republic_reference(ASSET, path)
    price = trade_republic_price(ASSET, now=now, path=path)
    analysis_plan = {
        "plan_fingerprint": "analysis-plan",
        "stop_contract_version": "stop-v1",
        "entry_method": "Pullback-Limit",
        "order_type": "Limitorder",
        "activation_type": "Tageskerze",
        "analysis_reference_price_eur": 100.0,
        "analysis_price_source": "Yahoo Finance / yfinance",
        "analysis_reference_observed_at": "2026-08-10",
        "activation_price_eur": 98.0,
        "limit_price_eur": 100.0,
        "maximum_entry_eur": 102.0,
        "initial_stop_eur": 95.0,
        "target_1_eur": 110.0,
        "target_2_eur": 115.0,
        "invalidation_eur": 94.0,
        "target_1_exit_fraction": 0.5,
        "target_2_exit_fraction": 0.5,
        "signal_bar_day": "2026-08-10",
        "earliest_entry_day": "2026-08-11",
        "valid_until": "2026-08-17",
        "delete_conditions": [],
        "automatic_order_execution": False,
    }

    plan = build_trade_republic_execution_plan(
        analysis_plan,
        reference,
        price,
        trading_capital_eur=10_000,
        max_risk_pct=0.5,
        asset_type="Aktie",
        max_total_exposure_pct=50,
        current_exposure_eur=0,
        max_position_exposure_pct=20,
    )

    assert plan is not None
    assert plan["current_tr_price_eur"] == 120.0
    assert plan["limit_price_eur"] == pytest.approx(120.0)
    assert plan["initial_stop_eur"] == pytest.approx(114.0)
    assert plan["target_1_eur"] == pytest.approx(132.0)
    assert plan["trade_republic_listing"]["isin"] == ASSET["isin"]
    assert plan["execution_price_source"] == "Manuell aus Trade Republic erfasst"
    assert plan["analysis_price_source"] == "Yahoo Finance / yfinance"
    assert plan["automatic_order_execution"] is False


def test_reference_store_is_append_only_and_auditable(tmp_path) -> None:
    path = tmp_path / "tr.sqlite3"
    mark_tradeable(path)

    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE tr_listing_events SET status = 'unbekannt'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM tr_listing_events")

    audit = trade_republic_reference_store_audit(path)
    assert audit["status"] == "ok"
    assert audit["listing_events"] == 1
    assert audit["append_only"] is True
    assert audit["broker_connection"] is False
