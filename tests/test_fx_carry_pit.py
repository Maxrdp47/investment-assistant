from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fx_carry_pit import (
    FxCarryContractError,
    carry_snapshot,
    default_fx_pair_contracts,
    fx_pair_contract,
    fx_pipeline_coverage_report,
    normalize_fx_ohlc,
    normalize_pit_observation,
    observations_available_at,
    store_fx_pair_contracts,
    store_pit_observations,
)


def _observation(feature: str, value: float, *, currency=None, pair_id=None, known="2020-01-01T12:00:00+00:00", available=None, vintage="ORIGINAL", metadata=None):
    return {
        "feature": feature,
        "value": value,
        "unit": "pct",
        "currency": currency,
        "pair_id": pair_id,
        "effective_at": "2020-01-01T12:00:00+00:00",
        "known_at": known,
        "available_at": available or known,
        "source": "test-source",
        "source_record_id": f"{feature}-{currency or pair_id}-{vintage}",
        "vintage": vintage,
        "metadata": metadata or {},
    }


def test_default_pair_contracts_cover_required_pairs_and_sessions() -> None:
    pairs = default_fx_pair_contracts()
    assert set(pairs) == {"EUR/USD", "USD/JPY", "GBP/USD"}
    assert pairs["EUR/USD"]["carry_sign"] == "base_rate_minus_quote_rate"
    assert pairs["USD/JPY"]["session_timezone"] == "America/New_York"
    assert pairs["GBP/USD"]["canonical_daily_close"] == "17:00"


def test_inverse_pair_normalizes_ohlc_high_and_low_correctly() -> None:
    contract = fx_pair_contract(
        "EUR", "USD", source_ticker="USDEUR=X",
        source_base_currency="USD", source_quote_currency="EUR",
    )
    result = normalize_fx_ohlc(
        contract, {"open": 0.8, "high": 0.9, "low": 0.75, "close": 0.85}
    )
    assert result == pytest.approx(
        {"open": 1.25, "high": 1 / 0.75, "low": 1 / 0.9, "close": 1 / 0.85}
    )


def test_carry_sign_uses_base_minus_quote_and_no_future_release() -> None:
    contract = default_fx_pair_contracts()["EUR/USD"]
    observations = [
        _observation("policy_rate", 2.0, currency="EUR"),
        _observation("policy_rate", 1.0, currency="USD"),
        _observation("realized_volatility", 10.0, pair_id="EUR/USD"),
        _observation(
            "expected_policy_rate", 2.5, currency="EUR",
            known="2020-01-02T12:00:00+00:00",
        ),
    ]
    before = carry_snapshot(contract, observations, cutoff="2020-01-01T23:00:00+00:00")
    assert before["short_rate_differential"] == 1.0
    assert before["carry_direction"] == "LONG_BASE"
    assert before["carry_to_risk"] == 0.1
    assert before["expected_rate_differential"] is None
    assert before["future_observations_used"] == 0


def test_release_revision_and_missing_consensus_are_point_in_time_safe() -> None:
    original = _observation("policy_rate", 1.0, currency="USD")
    revision = _observation(
        "policy_rate", 1.1, currency="USD", vintage="REVISION_1",
        known="2020-02-01T12:00:00+00:00",
    )
    assert len(observations_available_at([original, revision], "2020-01-15T00:00:00+00:00")) == 1

    with pytest.raises(FxCarryContractError, match="Konsens"):
        normalize_pit_observation(
            _observation("central_bank_surprise", 0.2, currency="USD")
        )
    valid = _observation(
        "central_bank_surprise",
        0.2,
        currency="USD",
        metadata={
            "consensus": 1.0,
            "actual": 1.2,
            "consensus_known_at": "2020-01-01T08:00:00+00:00",
        },
    )
    assert normalize_pit_observation(valid)["value"] == pytest.approx(0.2)


def test_append_only_store_is_idempotent_and_fingerprints_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "fx.sqlite3"
    contracts = default_fx_pair_contracts()
    observation = _observation("policy_rate", 1.0, currency="USD")
    assert store_fx_pair_contracts(contracts.values(), path=path, created_at="2020-01-01T00:00:00+00:00") == 3
    assert store_fx_pair_contracts(contracts.values(), path=path, created_at="2020-01-01T00:00:00+00:00") == 0
    assert store_pit_observations([observation], path=path) == 1
    assert store_pit_observations([observation], path=path) == 0
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM fx_pit_observations")

    first = fx_pipeline_coverage_report([observation], contracts=contracts)
    second = fx_pipeline_coverage_report([observation], contracts=contracts)
    assert first == second
    assert first["status"] == "PARTIAL_READY_TRANSPARENT_LIMITS"
    assert first["fields"]["expected_rate_differential"] == "UNAVAILABLE_NO_HISTORICAL_EXPECTATIONS"
    assert first["cost_contract"]["numeric_spread_invented"] is False
