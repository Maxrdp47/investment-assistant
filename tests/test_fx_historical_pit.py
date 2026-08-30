from __future__ import annotations

import pytest

from fx_historical_pit import (
    FxHistoricalPitError,
    append_fx_coverage_snapshot,
    append_historical_fx_records,
    cot_release_eligibility,
    fx_cost_proxy_contract,
    fx_coverage_matrix,
    historical_fx_inventory,
    load_historical_fx_records,
    normalize_historical_fx_record,
    policy_rate_differential,
    surprise_from_observations,
)


STAMP = "2026-08-29T10:00:00+00:00"


def _record(
    feature: str,
    *,
    pair_id: str = "EUR/USD",
    status: str = "AVAILABLE_PIT",
    source_type: str = "HISTORICAL_PIT",
    value: float | None = 1.0,
    release_at: str | None = "2020-01-02T10:00:00+00:00",
    available_at: str | None = "2020-01-02T10:05:00+00:00",
    revision_number: int = 0,
    supersedes: str | None = None,
) -> dict[str, object]:
    return {
        "feature": feature,
        "pair_id": pair_id,
        "observation_date": "2020-01-01",
        "release_at": release_at,
        "available_at": available_at,
        "vintage_date": "2020-01-02",
        "first_seen_at": STAMP,
        "imported_at": STAMP,
        "value": value,
        "unit": "pct",
        "source": "official test source",
        "source_record_id": f"{feature}-{revision_number}",
        "source_type": source_type,
        "coverage_status": status,
        "revision_number": revision_number,
        "supersedes": supersedes,
    }


def test_historical_pit_requires_release_and_availability_evidence() -> None:
    with pytest.raises(FxHistoricalPitError, match="Release"):
        normalize_historical_fx_record(_record("POLICY_RATE", release_at=None))
    item = normalize_historical_fx_record(_record("POLICY_RATE"))
    assert item["pit_eligible"] is True
    assert item["today_revised_value_backdated"] is False


def test_backfill_never_becomes_pit_just_because_it_is_imported_today() -> None:
    raw = _record(
        "MACRO_VINTAGE",
        status="AVAILABLE_SHADOW",
        source_type="HISTORICAL_BACKFILL_NON_PIT",
        release_at=None,
        available_at=None,
    )
    item = normalize_historical_fx_record(raw)
    assert item["pit_eligible"] is False
    with pytest.raises(FxHistoricalPitError, match="darf nicht"):
        normalize_historical_fx_record({**raw, "coverage_status": "AVAILABLE_PIT"})


def test_revisions_append_with_explicit_supersedes() -> None:
    original = normalize_historical_fx_record(_record("MACRO_VINTAGE"))
    revised = normalize_historical_fx_record(
        _record(
            "MACRO_VINTAGE",
            value=1.1,
            revision_number=1,
            supersedes=str(original["record_id"]),
        )
    )
    assert revised["record_id"] != original["record_id"]
    assert revised["supersedes"] == original["record_id"]
    with pytest.raises(FxHistoricalPitError, match="supersedes"):
        normalize_historical_fx_record(_record("MACRO_VINTAGE", revision_number=1))


def test_surprise_requires_an_expectation_known_before_release() -> None:
    missing = surprise_from_observations(
        expected_value=None,
        actual_value=1.2,
        expected_known_at=None,
        release_at="2020-01-02T10:00:00+00:00",
    )
    assert missing == {
        "status": "UNKNOWN",
        "surprise": None,
        "reason": "PRE_RELEASE_EXPECTATION_UNAVAILABLE",
        "release_at": "2020-01-02T10:00:00+00:00",
    }
    valid = surprise_from_observations(
        expected_value=1.0,
        actual_value=1.2,
        expected_known_at="2020-01-02T09:00:00+00:00",
        release_at="2020-01-02T10:00:00+00:00",
    )
    assert valid["surprise"] == pytest.approx(0.2)
    with pytest.raises(FxHistoricalPitError, match="nicht bekannt"):
        surprise_from_observations(
            expected_value=1.0,
            actual_value=1.2,
            expected_known_at="2020-01-02T11:00:00+00:00",
            release_at="2020-01-02T10:00:00+00:00",
        )


def test_actual_and_expected_rate_differentials_are_separate() -> None:
    result = policy_rate_differential(
        base_rate=2.0,
        quote_rate=1.0,
        base_expected_rate=None,
        quote_expected_rate=None,
    )
    assert result["actual_rate_differential"] == 1.0
    assert result["expected_rate_differential"] is None
    assert result["carry_direction"] == "LONG_BASE"


def test_cot_is_pit_only_after_verified_release_or_real_forward_first_seen() -> None:
    before = cot_release_eligibility(
        report_date="2020-01-01",
        cutoff="2020-01-03T19:00:00+00:00",
        published_at="2020-01-03T20:00:00+00:00",
        first_seen_at=STAMP,
        acquisition_mode="BACKFILL",
    )
    assert before["pit_eligible"] is False
    historical_unknown = cot_release_eligibility(
        report_date="2020-01-01",
        cutoff="2020-02-01T00:00:00+00:00",
        published_at=None,
        first_seen_at=STAMP,
        acquisition_mode="BACKFILL",
    )
    assert historical_unknown["classification"] == "AVAILABLE_SHADOW"
    forward = cot_release_eligibility(
        report_date="2020-01-01",
        cutoff="2026-08-29T11:00:00+00:00",
        published_at=None,
        first_seen_at=STAMP,
        acquisition_mode="FORWARD",
    )
    assert forward["pit_eligible"] is True


def test_cost_levels_are_explicit_proxies_not_observed_spreads() -> None:
    empty = fx_cost_proxy_contract()
    assert empty["numeric_values_invented"] is False
    contract = fx_cost_proxy_contract(
        {
            "g10_liquid": {
                "base_cost_proxy": 1.0,
                "conservative_cost_proxy": 2.0,
                "stress_cost_proxy": 5.0,
                "source": "predeclared research assumption",
            }
        }
    )
    group = contract["pair_groups"]["g10_liquid"]
    assert group["classification"] == "PROXY"
    assert group["observed_historical_spread"] is False


def test_coverage_matrix_keeps_structural_missingness_visible() -> None:
    records = [
        _record("PRICE"),
        _record(
            "COT",
            status="AVAILABLE_SHADOW",
            source_type="SHADOW_CONTEXT",
            release_at=None,
            available_at=None,
        ),
    ]
    matrix = fx_coverage_matrix(records, pair_ids=["EUR/USD"], years=[2020])
    year = matrix["matrix"]["EUR/USD"]["2020"]
    assert year["PRICE"] == "AVAILABLE_PIT"
    assert year["COT"] == "AVAILABLE_SHADOW"
    assert year["EXPECTED_RATE"] == "UNAVAILABLE"
    assert matrix["missing_is_false"] is False


def test_inventory_separates_pit_from_shadow_records() -> None:
    inventory = historical_fx_inventory(
        [
            _record("PRICE"),
            _record(
                "SPREAD_BIDASK",
                status="AVAILABLE_SHADOW",
                source_type="PROXY",
                release_at=None,
                available_at=None,
            ),
        ]
    )
    assert inventory["record_n"] == 2
    assert inventory["pit_eligible_n"] == 1
    assert inventory["shadow_or_non_pit_n"] == 1


def test_historical_store_is_append_only_and_idempotent(tmp_path) -> None:
    path = tmp_path / "historical.sqlite3"
    raw = _record("PRICE")
    first = append_historical_fx_records([raw], path=path)
    second = append_historical_fx_records(
        [{**raw, "first_seen_at": "2026-08-30T10:00:00+00:00", "imported_at": "2026-08-30T10:00:00+00:00"}],
        path=path,
    )
    assert first == {"inserted": 1, "deduplicated": 0}
    assert second == {"inserted": 0, "deduplicated": 1}
    stored = load_historical_fx_records(path=path)
    assert len(stored) == 1
    assert stored[0]["first_seen_at"] == STAMP

    matrix = fx_coverage_matrix([raw], pair_ids=["EUR/USD"], years=[2020])
    assert append_fx_coverage_snapshot(matrix, created_at=STAMP, path=path) is True
    assert append_fx_coverage_snapshot(matrix, created_at=STAMP, path=path) is False
