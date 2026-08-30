from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing_research_identity_v2 import ResearchIdentityError
from swing_research_identity_v3 import (
    append_identity_registry,
    build_identity_registry,
    dependency_evidence_report_v3,
    load_identity_registry,
    normalize_identity_mapping,
    resolve_research_identity_v3,
    validate_listing_scoped_bundle_v3,
)


STAMP = "2026-08-29T10:00:00+00:00"
VERSION = "research-identity-registry-pytest-v1"


def _mapping(
    ticker: str,
    *,
    issuer_anchor: str,
    issuer_id: str,
    isin: str,
    figi: str,
    mic: str,
    exchange: str,
    currency: str,
    name: str,
    instrument_type: str = "COMMON_STOCK",
    listing_role: str = "PRIMARY",
    exchange_timezone: str = "UTC",
    valid_from: str = "2010-01-01",
    valid_to: str | None = None,
    ticker_aliases: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "ticker_aliases": list(ticker_aliases),
        "name": name,
        "issuer_id": issuer_id,
        "issuer_anchor_type": "EXCHANGE_ISSUER_REFERENCE",
        "issuer_anchor_value": issuer_anchor,
        "mapping_status": "VERIFIED",
        "mapping_version": VERSION,
        "source": "pytest verified exchange register",
        "source_reference": f"https://example.test/register/{issuer_anchor}/{ticker}",
        "confidence": 100,
        "quality": "HIGH",
        "isin": isin,
        "figi": figi,
        "mic": mic,
        "exchange": exchange,
        "currency": currency,
        "instrument_type": instrument_type,
        "asset_class": "EQUITIES",
        "primary_listing_status": listing_role,
        "exchange_timezone": exchange_timezone,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "first_seen_at": STAMP,
        "imported_at": STAMP,
    }


def _registry(records: list[dict[str, object]]) -> dict[str, object]:
    return build_identity_registry(records, mapping_version=VERSION, created_at=STAMP)


def test_xpeng_primary_and_ads_share_verified_issuer_but_never_listing() -> None:
    registry = _registry(
        [
            _mapping(
                "9868.HK",
                issuer_anchor="xpeng",
                issuer_id="issuer-xpeng",
                isin="KYG982AW1003",
                figi="FIGI-XPENG-HK-TEST",
                mic="XHKG",
                exchange="HKEX",
                currency="HKD",
                name="XPeng Inc.",
                exchange_timezone="Asia/Hong_Kong",
            ),
            _mapping(
                "XPEV",
                issuer_anchor="xpeng",
                issuer_id="issuer-xpeng",
                isin="US98422D1054",
                figi="FIGI-XPENG-ADS-TEST",
                mic="XNYS",
                exchange="NYSE",
                currency="USD",
                name="XPeng Inc. ADS",
                instrument_type="ADS",
                listing_role="SECONDARY",
                exchange_timezone="America/New_York",
            ),
        ]
    )
    hk = resolve_research_identity_v3({"ticker": "9868.HK", "mic": "XHKG"}, registry=registry)
    ads = resolve_research_identity_v3({"ticker": "XPEV", "mic": "XNYS"}, registry=registry)
    assert hk["issuer_id"] == ads["issuer_id"] == "issuer-xpeng"
    assert hk["listing_id"] != ads["listing_id"]
    assert ads["is_depositary_receipt"] is True
    assert (hk["currency"], ads["currency"]) == ("HKD", "USD")
    assert hk["exchange_timezone"] != ads["exchange_timezone"]


@pytest.mark.parametrize(
    "records",
    [
        [
            _mapping("SAP.DE", issuer_anchor="sap", issuer_id="issuer-sap", isin="DE0007164600", figi="FIGI-SAP-DE-TEST", mic="XETR", exchange="XETRA", currency="EUR", name="SAP SE"),
            _mapping("SAP", issuer_anchor="sap", issuer_id="issuer-sap", isin="US8030542042", figi="FIGI-SAP-ADR-TEST", mic="XNYS", exchange="NYSE", currency="USD", name="SAP SE ADR", instrument_type="ADR", listing_role="SECONDARY"),
        ],
        [
            _mapping("AIR.PA", issuer_anchor="airbus", issuer_id="issuer-airbus", isin="NL0000235190", figi="FIGI-AIR-PA-TEST", mic="XPAR", exchange="EURONEXT", currency="EUR", name="Airbus SE"),
            _mapping("AIR.DE", issuer_anchor="airbus", issuer_id="issuer-airbus", isin="NL0000235190", figi="FIGI-AIR-DE-TEST", mic="XETR", exchange="XETRA", currency="EUR", name="Airbus SE", listing_role="SECONDARY"),
        ],
    ],
)
def test_home_adr_and_multiple_european_listings_cluster_generically(records) -> None:
    registry = _registry(records)
    identities = registry["records"]
    report = dependency_evidence_report_v3(identities)
    assert report["raw_n"] == 2
    assert report["issuer_cluster_n"] == 1
    assert report["listing_cluster_n"] == 2
    assert report["same_issuer_excess_case_n"] == 1


def test_unresolved_name_never_creates_a_fuzzy_issuer_link() -> None:
    registry = _registry([])
    first = resolve_research_identity_v3(
        {"ticker": "AAA", "name": "Example Holdings", "currency": "USD"},
        registry=registry,
    )
    second = resolve_research_identity_v3(
        {"ticker": "BBB", "name": "Example Holdings Inc", "currency": "USD"},
        registry=registry,
    )
    assert first["issuer_id"] is None
    assert second["issuer_id"] is None
    assert first["mapping_status"] == second["mapping_status"] == "UNRESOLVED"
    report = dependency_evidence_report_v3([first, second])
    assert report["dependency_unknown_n"] == 2
    assert report["effective_n_known_issuers_only"] == 0
    assert report["unknown_counted_as_independent"] is False


def test_verified_mapping_requires_a_strong_anchor_not_just_a_name() -> None:
    record = _mapping(
        "NVDA",
        issuer_anchor="nvda",
        issuer_id="issuer-nvda",
        isin="US67066G1040",
        figi="FIGI-NVDA-TEST",
        mic="XNAS",
        exchange="NASDAQ",
        currency="USD",
        name="NVIDIA Corporation",
    )
    record.pop("issuer_anchor_value")
    with pytest.raises(ResearchIdentityError, match="Issuer-Anker"):
        normalize_identity_mapping(record)


def test_ticker_change_keeps_stable_listing_id_when_figi_anchor_is_unchanged() -> None:
    old = _mapping(
        "OLD",
        issuer_anchor="rename",
        issuer_id="issuer-rename",
        isin="US0000000001",
        figi="FIGI-SAME-LISTING-TEST",
        mic="XNYS",
        exchange="NYSE",
        currency="USD",
        name="Rename Corp",
        valid_from="2010-01-01",
        valid_to="2020-12-31",
    )
    new = _mapping(
        "NEW",
        issuer_anchor="rename",
        issuer_id="issuer-rename",
        isin="US0000000001",
        figi="FIGI-SAME-LISTING-TEST",
        mic="XNYS",
        exchange="NYSE",
        currency="USD",
        name="Rename Corp",
        valid_from="2021-01-01",
    )
    registry = _registry([old, new])
    before = resolve_research_identity_v3(
        {"ticker": "OLD", "mic": "XNYS"}, registry=registry, as_of="2020-06-01"
    )
    after = resolve_research_identity_v3(
        {"ticker": "NEW", "mic": "XNYS"}, registry=registry, as_of="2021-06-01"
    )
    assert before["listing_id"] == after["listing_id"]
    assert before["issuer_id"] == after["issuer_id"]


def test_listing_bundle_rejects_ohlcv_stop_or_target_from_another_listing() -> None:
    identity = normalize_identity_mapping(
        _mapping("AAA", issuer_anchor="a", issuer_id="issuer-a", isin="US0000000002", figi="FIGI-A-TEST", mic="XNAS", exchange="NASDAQ", currency="USD", name="A Corp")
    )
    listing_id = identity["listing_id"]
    valid = {
        "identity": identity,
        "ohlcv": {"listing_id": listing_id, "currency": "USD"},
        "entry": {"listing_id": listing_id, "currency": "USD"},
        "stop": {"listing_id": listing_id, "currency": "USD"},
        "target": {"listing_id": listing_id, "currency": "USD"},
    }
    assert validate_listing_scoped_bundle_v3(valid)["cross_listing_values_used"] is False
    for section in ("ohlcv", "stop", "target"):
        with pytest.raises(ResearchIdentityError, match="gehört nicht"):
            validate_listing_scoped_bundle_v3(
                {**valid, section: {"listing_id": "other", "currency": "EUR"}}
            )


def test_registry_fingerprint_is_deterministic_append_only_and_idempotent(tmp_path: Path) -> None:
    records = [
        _mapping("AAA", issuer_anchor="a", issuer_id="issuer-a", isin="US0000000002", figi="FIGI-A-TEST", mic="XNAS", exchange="NASDAQ", currency="USD", name="A Corp")
    ]
    first = _registry(records)
    second = _registry(list(reversed(records)))
    assert first["registry_fingerprint"] == second["registry_fingerprint"]
    path = tmp_path / "identity.sqlite3"
    assert append_identity_registry(first, path=path) == 1
    assert append_identity_registry(first, path=path) == 0
    assert load_identity_registry(VERSION, path=path) == first
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM identity_mappings")
