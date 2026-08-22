from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from swing_forward_store import SWING_STRATEGY_VERSION
from swing_shadow_live import (
    append_shadow_execution_observation,
    build_shadow_execution_observation,
    initialize_shadow_live_store,
    load_shadow_execution_observations,
    record_shadow_execution_observations,
    shadow_listing_identity,
    shadow_live_store_audit,
)


def stored_draft(path, *, draft_id: str = "draft-1") -> dict:
    snapshot = {
        "shadow_only": True,
        "broker_order_allowed": False,
        "asset": {
            "ticker": "TEST.DE",
            "listing": {
                "ticker": "TEST.DE",
                "isin": "DE000TEST001",
                "exchange": "XETRA",
                "original_currency": "EUR",
            },
        },
        "strategy": {"strategy_version": SWING_STRATEGY_VERSION},
        "signal": {"signal_id": "signal-1"},
        "order_plan": {
            "limit_price_eur": 100.0,
            "entry_activation_above_eur": 99.0,
            "max_entry_price_eur": 101.0,
            "initial_stop_eur": 95.0,
            "target_1_eur": 110.0,
            "target_2_eur": 115.0,
        },
        "execution_observations": {
            "trade_republic_price_eur": None,
            "trade_republic_price_observed_at": None,
            "trade_republic_price_source": None,
        },
    }
    encoded = json.dumps(snapshot, sort_keys=True)
    initialize_shadow_live_store(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO shadow_drafts VALUES(?,?,?,?,?,?,?)",
            (
                draft_id,
                "setup-1",
                "2026-08-23T10:00:00+00:00",
                "TEST.DE",
                SWING_STRATEGY_VERSION,
                encoded,
                hashlib.sha256(encoded.encode()).hexdigest(),
            ),
        )
    return {"draft_id": draft_id, "setup_id": "setup-1", "snapshot": snapshot}


def test_missing_quote_stays_explicitly_unavailable_without_invented_execution_values(tmp_path) -> None:
    path = tmp_path / "shadow.sqlite3"
    stored_draft(path)

    first = record_shadow_execution_observations(
        observed_at="2026-08-23T10:01:00+00:00",
        path=path,
    )
    repeated = record_shadow_execution_observations(
        observed_at="2026-08-23T10:02:00+00:00",
        path=path,
    )
    observation = load_shadow_execution_observations(path)[0]["observation"]
    market = observation["observed_market_data"]

    assert first["unavailable_observations"] == 1
    assert repeated["observations_existing"] == 1
    assert observation["execution_observation_status"] == "real_execution_quote_data_unavailable"
    assert all(market[field] is None for field in ("bid", "ask", "mid", "spread_absolute", "spread_percent", "last_price"))
    assert observation["execution_evidence"] == {
        "fill": None,
        "partial_fill": None,
        "slippage": None,
        "order_book": None,
        "broker_rejection": None,
    }
    assert observation["simulated_cost_assumptions"]["present"] is False
    assert observation["guardrails"]["broker_order_allowed"] is False
    assert shadow_live_store_audit(path)["real_quote_observations"] == 0


def test_real_quote_requires_exact_listing_source_timestamp_and_marks_staleness(tmp_path) -> None:
    path = tmp_path / "shadow.sqlite3"
    draft = stored_draft(path)
    listing = shadow_listing_identity(draft["snapshot"])
    quote = {
        "listing_id": listing["listing_id"],
        "source": "Official read-only exchange quote test fixture",
        "source_timestamp": "2026-08-23T10:00:00+00:00",
        "quote_quality": "realtime",
        "original_currency": "EUR",
        "bid": 99.8,
        "ask": 100.2,
        "last_price": 100.0,
    }

    observation = build_shadow_execution_observation(
        draft,
        signal_id="signal-1",
        observed_at="2026-08-23T10:10:00+00:00",
        quote=quote,
        max_quote_age_seconds=300,
    )
    appended = append_shadow_execution_observation(observation, path)
    market = observation["observed_market_data"]

    assert appended["inserted"] is True
    assert observation["execution_observation_status"] == "observed_market_quote"
    assert observation["quote_quality"] == "stale"
    assert market["mid"] == pytest.approx(100.0)
    assert market["spread_absolute"] == pytest.approx(0.4)
    assert market["spread_percent"] == pytest.approx(0.4)
    assert observation["later_shadow_evaluation"]["later_limit_touch"] is None
    assert observation["execution_evidence"]["fill"] is None

    with pytest.raises(ValueError, match="exakten Shadow-Listing"):
        build_shadow_execution_observation(
            draft,
            signal_id="signal-1",
            observed_at="2026-08-23T10:01:00+00:00",
            quote={**quote, "listing_id": "wrong-listing"},
        )
    with pytest.raises(ValueError, match="Quelle und Quellzeitpunkt"):
        build_shadow_execution_observation(
            draft,
            signal_id="signal-1",
            observed_at="2026-08-23T10:01:00+00:00",
            quote={**quote, "source": ""},
        )
    with pytest.raises(ValueError, match="Tages-/simulierte"):
        build_shadow_execution_observation(
            draft,
            signal_id="signal-1",
            observed_at="2026-08-23T10:01:00+00:00",
            quote={**quote, "source": "Yahoo daily OHLC"},
        )


def test_quote_provider_failure_is_visible_retryable_and_does_not_create_fake_observation(tmp_path) -> None:
    path = tmp_path / "shadow.sqlite3"
    stored_draft(path)

    result = record_shadow_execution_observations(
        observed_at="2026-08-23T10:01:00+00:00",
        quote_provider=lambda _draft: (_ for _ in ()).throw(RuntimeError("provider offline")),
        path=path,
    )

    assert result["status"] == "research_attention"
    assert result["errors"][0]["error"] == "provider offline"
    assert load_shadow_execution_observations(path) == []
    assert shadow_live_store_audit(path)["drafts_without_real_market_observation"] == 1


def test_execution_tables_are_append_only(tmp_path) -> None:
    path = tmp_path / "shadow.sqlite3"
    stored_draft(path)
    record_shadow_execution_observations(
        observed_at="2026-08-23T10:01:00+00:00",
        path=path,
    )

    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE shadow_execution_observations SET quote_quality='changed'"
            )
