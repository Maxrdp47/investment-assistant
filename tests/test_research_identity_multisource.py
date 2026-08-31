from __future__ import annotations

import copy

from research_identity_multisource import (
    build_multisource_registry,
    coverage_gate,
)
from swing_research_identity_v3 import dependency_episode_report_v3


STAMP = "2026-08-30T10:00:00+00:00"


def _asset(ticker: str, name: str = "Example Inc", asset_type: str = "Aktie") -> dict[str, str]:
    return {
        "version": "pytest-v1",
        "ticker": ticker,
        "name": name,
        "asset_type": asset_type,
        "region": "Global",
        "source_group": "pytest",
    }


def _relation(issuer_id: str, *tickers: str) -> dict[str, dict[str, object]]:
    result = {}
    for index, ticker in enumerate(tickers):
        result[ticker] = {
            "issuer_id": issuer_id,
            "issuer_anchor_value": f"official:{issuer_id}",
            "source_reference": "https://issuer.example.test/listings",
            "evidence": "Official issuer listing table",
            "listing": {
                "ticker": ticker,
                "listing_role": "PRIMARY" if index == 0 else "SECONDARY",
                "instrument_type": "ADS" if ticker == "XPEV" else "COMMON_STOCK",
            },
        }
    return result


def _registry(universe, *, sec=None, figi=None, relations=None):
    return build_multisource_registry(
        universe,
        sec_rows=sec or {},
        openfigi_rows=figi or {},
        official_relations=relations or {},
        mapping_version="pytest-multisource-v1",
        imported_at=STAMP,
        source_provenance={"sec_derived_snapshot_url": "https://source.example.test/pinned.csv"},
    )


def test_xpeng_ads_and_home_listing_share_issuer_not_listing_or_market_data() -> None:
    relations = _relation("official-issuer:xpeng", "9868.HK", "XPEV")
    figi = {
        "9868.HK": {"response": [{"figi": "BBG-HK", "shareClassFIGI": "BBG-SHARE-HK"}]},
        "XPEV": {"response": [{"figi": "BBG-US", "shareClassFIGI": "BBG-SHARE-US"}]},
    }
    registry = _registry([_asset("9868.HK"), _asset("XPEV")], figi=figi, relations=relations)
    hk, ads = sorted(registry["records"], key=lambda row: str(row["ticker"]))
    assert hk["issuer_id"] == ads["issuer_id"] == "official-issuer:xpeng"
    assert hk["listing_id"] != ads["listing_id"]
    assert {hk["currency"], ads["currency"]} == {"HKD", "USD"}
    assert hk["exchange_timezone"] != ads["exchange_timezone"]
    assert registry["dependency"]["verified_issuer_clusters"] == 1
    assert registry["dependency"]["raw_listings"] == 2


def test_same_cik_share_classes_collapse_to_one_issuer_but_two_listings() -> None:
    sec = {
        "FOO": [{"ticker": "FOO", "sec_cik": "0000000042", "exchange": "NASDAQ"}],
        "FOO-B": [{"ticker": "FOO-B", "sec_cik": "0000000042", "exchange": "NASDAQ"}],
    }
    registry = _registry([_asset("FOO"), _asset("FOO.B")], sec=sec)
    assert {row["issuer_id"] for row in registry["records"]} == {"sec-cik:0000000042"}
    assert len({row["listing_id"] for row in registry["records"]}) == 2
    assert registry["dependency"]["same_issuer_excess_case_n"] == 1


def test_name_similarity_is_only_unresolved_and_conflicting_strong_ids_fail_closed() -> None:
    sec = {
        "CONFLICT": [
            {"ticker": "CONFLICT", "sec_cik": "0000000001"},
            {"ticker": "CONFLICT", "sec_cik": "0000000002"},
        ]
    }
    registry = _registry(
        [_asset("AAA", "Same Holdings"), _asset("BBB", "Same Holdings Inc"), _asset("CONFLICT")],
        sec=sec,
    )
    by_ticker = {row["ticker"]: row for row in registry["records"]}
    assert by_ticker["AAA"]["mapping_status"] == "UNRESOLVED"
    assert by_ticker["BBB"]["mapping_status"] == "UNRESOLVED"
    assert by_ticker["AAA"]["issuer_id"] is None
    assert by_ticker["CONFLICT"]["mapping_status"] == "CONFLICT"
    assert by_ticker["CONFLICT"]["dependency_status"] == "UNKNOWN"
    assert registry["dependency"]["effective_independent_issuer_count"] == 0


def test_openfigi_alone_is_listing_evidence_not_a_verified_issuer() -> None:
    registry = _registry(
        [_asset("AAA")],
        figi={"AAA": {"response": [{"figi": "BBG000AAA", "shareClassFIGI": "BBG00SHARE"}]}},
    )
    row = registry["records"][0]
    assert row["mapping_status"] == "CANDIDATE_UNVERIFIED"
    assert row["issuer_id"] is None
    assert row["listing_identity_quality"] == "ANCHORED"
    assert row["dependency_status"] == "UNKNOWN"


def test_mapping_and_gate_are_deterministic_and_predeclared() -> None:
    universe = [_asset(f"S{index}") for index in range(5)]
    sec = {
        f"S{index}": [{"ticker": f"S{index}", "sec_cik": f"{index + 1:010d}"}]
        for index in range(4)
    }
    first = _registry(universe, sec=sec)
    second = _registry(copy.deepcopy(universe), sec=copy.deepcopy(sec))
    assert first["registry_fingerprint"] == second["registry_fingerprint"]
    gate = coverage_gate(first["records"], official_relations={})
    assert gate["minimum_verified_coverage_pct"] == 80.0
    assert gate["verified_coverage_pct"] == 80.0
    assert gate["status"] == "PASS"


def test_effective_n_collapses_overlapping_issuer_windows_and_excludes_unknown() -> None:
    rows = [
        {
            "ticker": "A",
            "listing_id": "listing-a",
            "issuer_id": "issuer-1",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2025-01-01",
            "label_end_day": "2025-01-10",
        },
        {
            "ticker": "A2",
            "listing_id": "listing-a2",
            "issuer_id": "issuer-1",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2025-01-05",
            "label_end_day": "2025-01-12",
        },
        {
            "ticker": "A",
            "listing_id": "listing-a",
            "issuer_id": "issuer-1",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2025-02-01",
            "label_end_day": "2025-02-10",
        },
        {
            "ticker": "UNKNOWN",
            "listing_id": "listing-u",
            "issuer_id": None,
            "mapping_status": "UNRESOLVED",
            "dependency_status": "UNKNOWN",
            "signal_day": "2025-03-01",
            "label_end_day": "2025-03-10",
        },
    ]
    report = dependency_episode_report_v3(rows)
    assert report["raw_observations"] == 4
    assert report["raw_listings"] == 3
    assert report["verified_issuer_clusters"] == 1
    assert report["dependency_unknown"] == 1
    assert report["effective_independent_issuer_count"] == 2
    assert report["unknown_dependency_contribution_to_effective_n"] == 0
    assert report["effective_n_le_raw_n"] is True


def test_effective_n_uses_maximum_non_overlapping_interval_subset() -> None:
    rows = [
        {
            "ticker": "A",
            "listing_id": "listing-a",
            "issuer_id": "issuer-1",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2025-01-01",
            "label_end_day": "2025-01-10",
        },
        {
            "ticker": "A2",
            "listing_id": "listing-a2",
            "issuer_id": "issuer-1",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2025-01-05",
            "label_end_day": "2025-01-20",
        },
        {
            "ticker": "A",
            "listing_id": "listing-a",
            "issuer_id": "issuer-1",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2025-01-11",
            "label_end_day": "2025-01-12",
        },
    ]

    report = dependency_episode_report_v3(rows)
    assert report["raw_observations"] == 3
    assert report["effective_independent_issuer_count"] == 2
