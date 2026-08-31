from __future__ import annotations

from copy import deepcopy

from historical_dependency_policy import (
    build_historical_dependency_policy,
    classify_historical_dependency,
    historical_dependency_policy_self_check,
)
from swing_research_identity_v3 import dependency_episode_report_v3


def _mapping(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "ticker": "TEST",
        "asset_id": "asset-test",
        "listing_id": "listing-test",
        "issuer_id": "issuer-test",
        "mapping_status": "VERIFIED",
        "metadata": {
            "historical_dependency": {
                "status": "VERIFIED",
                "valid_from": "2010-01-01",
                "valid_to": "2020-12-31",
                "evidence_type": "CONTEMPORANEOUS_REGULATORY_FILING",
                "evidence_source": "official:test",
            }
        },
    }
    value.update(overrides)
    return value


def test_today_identity_is_not_automatic_historical_feature_availability() -> None:
    current_only = _mapping(metadata={})
    result = classify_historical_dependency(current_only, as_of="2019-01-01")
    assert result["dependency_status"] == "UNKNOWN"
    assert result["pit_trading_feature"] is False
    assert result["feature_values_mutated"] is False


def test_adr_and_primary_listing_cluster_only_inside_verified_period() -> None:
    adr = classify_historical_dependency(
        _mapping(ticker="ADR", listing_id="adr"), as_of="2018-01-01"
    )
    primary = classify_historical_dependency(
        _mapping(ticker="PRIMARY", listing_id="primary"), as_of="2018-01-01"
    )
    assert adr["issuer_id"] == primary["issuer_id"] == "issuer-test"
    assert adr["listing_id"] != primary["listing_id"]


def test_secondary_listing_and_share_classes_remain_dependent_by_issuer() -> None:
    secondary = classify_historical_dependency(
        _mapping(listing_id="secondary"), as_of="2015-01-01"
    )
    share_class = classify_historical_dependency(
        _mapping(listing_id="share-class-b"), as_of="2015-01-01"
    )
    assert secondary["issuer_id"] == share_class["issuer_id"]


def test_later_merger_does_not_backdate_successor_cluster() -> None:
    mapping = _mapping()
    mapping["metadata"] = {
        "historical_dependency": {
            "status": "VERIFIED",
            "valid_from": "2022-06-01",
            "evidence_type": "VERSIONED_CORPORATE_ACTION_LEDGER",
            "evidence_source": "official:merger",
        }
    }
    assert classify_historical_dependency(
        mapping, as_of="2021-12-31"
    )["dependency_status"] == "UNKNOWN"


def test_spin_off_requires_its_own_temporal_evidence() -> None:
    spin_off = _mapping(issuer_id="issuer-spin-off", metadata={})
    assert classify_historical_dependency(
        spin_off, as_of="2019-01-01"
    )["dependency_status"] == "UNKNOWN"


def test_ticker_and_listing_change_can_retain_issuer_with_temporal_evidence() -> None:
    old = classify_historical_dependency(
        _mapping(ticker="OLD", listing_id="listing-old"), as_of="2015-01-01"
    )
    new = classify_historical_dependency(
        _mapping(ticker="NEW", listing_id="listing-new"), as_of="2015-01-01"
    )
    assert old["issuer_id"] == new["issuer_id"]


def test_unknown_historical_relation_contributes_zero() -> None:
    result = classify_historical_dependency(_mapping(metadata={}), as_of="2019-01-01")
    assert result["dependency_status"] == "UNKNOWN"
    assert result["unknown_dependency_contribution_to_effective_n"] == 0


def test_valid_from_and_valid_to_are_enforced() -> None:
    assert classify_historical_dependency(
        _mapping(), as_of="2009-12-31"
    )["dependency_status"] == "UNKNOWN"
    assert classify_historical_dependency(
        _mapping(), as_of="2021-01-01"
    )["dependency_status"] == "UNKNOWN"


def test_cluster_determinism_and_same_issuer_not_counted_twice() -> None:
    known = classify_historical_dependency(_mapping(), as_of="2015-01-01")
    cases = [
        {
            **known,
            "signal_day": "2015-01-01",
            "label_end_day": "2015-03-01",
        },
        {
            **known,
            "listing_id": "listing-secondary",
            "signal_day": "2015-01-15",
            "label_end_day": "2015-04-01",
        },
    ]
    first = dependency_episode_report_v3(cases)
    second = dependency_episode_report_v3(list(reversed(deepcopy(cases))))
    assert first["effective_independent_issuer_count"] == 1
    assert first["report_fingerprint"] == second["report_fingerprint"]


def test_policy_self_check_passes_without_mutating_features() -> None:
    report = historical_dependency_policy_self_check()
    assert report["status"] == "PASS"
    assert all(report["checks"].values())
    assert build_historical_dependency_policy()["trading_feature"] is False

