from __future__ import annotations

import pytest

from swing_research_identity_v2 import (
    ResearchIdentityError,
    dependency_evidence_report_v2,
    derive_research_identity_v2,
    research_identity_catalog_v2,
    validate_listing_scoped_bundle,
)


def _listing(
    ticker: str,
    *,
    issuer_id: str | None,
    name: str,
    exchange: str,
    currency: str,
    instrument_type: str = "COMMON_STOCK",
    listing_role: str = "UNKNOWN",
    exchange_timezone: str = "UTC",
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "issuer_id": issuer_id,
        "name": name,
        "exchange": exchange,
        "currency": currency,
        "instrument_type": instrument_type,
        "asset_class": "EQUITIES",
        "listing_role": listing_role,
        "exchange_timezone": exchange_timezone,
    }


def test_xpeng_adr_and_primary_are_distinct_listings_in_one_dependency_cluster() -> None:
    catalog = research_identity_catalog_v2(
        [
            _listing(
                "9868.HK",
                issuer_id="issuer-xpeng",
                name="XPeng Inc.",
                exchange="HKEX",
                currency="HKD",
                listing_role="PRIMARY",
                exchange_timezone="Asia/Hong_Kong",
            ),
            _listing(
                "XPEV",
                issuer_id="issuer-xpeng",
                name="XPeng Inc. ADS",
                exchange="NYSE",
                currency="USD",
                instrument_type="ADS",
                listing_role="SECONDARY",
                exchange_timezone="America/New_York",
            ),
        ]
    )

    identities = catalog["identities"]
    assert identities[0]["listing_id"] != identities[1]["listing_id"]
    assert identities[0]["dependency_cluster_id"] == identities[1]["dependency_cluster_id"]
    assert identities[1]["is_depositary_receipt"] is True
    assert identities[0]["currency"] == "HKD"
    assert identities[1]["currency"] == "USD"
    assert identities[0]["exchange_timezone"] == "Asia/Hong_Kong"
    assert identities[1]["exchange_timezone"] == "America/New_York"


@pytest.mark.parametrize(
    "assets",
    [
        [
            _listing("SAP.DE", issuer_id="issuer-sap", name="SAP SE", exchange="XETRA", currency="EUR"),
            _listing("SAP", issuer_id="issuer-sap", name="SAP SE ADR", exchange="NYSE", currency="USD", instrument_type="ADR"),
        ],
        [
            _listing("AIR.PA", issuer_id="issuer-airbus", name="Airbus SE", exchange="EURONEXT", currency="EUR"),
            _listing("AIR.DE", issuer_id="issuer-airbus", name="Airbus SE", exchange="XETRA", currency="EUR"),
        ],
    ],
)
def test_european_adr_and_multi_european_listings_cluster_by_verified_issuer(assets) -> None:
    catalog = research_identity_catalog_v2(assets)
    assert len(catalog["known_issuer_clusters"]) == 1
    assert catalog["raw_listing_n"] == 2


def test_single_direct_ticker_keeps_listing_identity_and_unknown_issuer_honest() -> None:
    identity = derive_research_identity_v2(
        _listing(
            "NVDA",
            issuer_id=None,
            name="NVIDIA Corporation",
            exchange="NASDAQ",
            currency="USD",
        )
    )
    assert identity["ticker"] == "NVDA"
    assert identity["listing_id"]
    assert identity["issuer_id"] is None
    assert identity["dependency_status"] == "UNKNOWN"
    assert identity["issuer_candidate_key"] == "nvidia"
    assert identity["unknown_is_independent_evidence"] is False


def test_unknown_issuer_is_not_counted_as_independent_effective_n() -> None:
    report = dependency_evidence_report_v2(
        [
            {"listing_id": "listing-a", "issuer_id": None, "dependency_status": "UNKNOWN"},
            {"listing_id": "listing-b", "issuer_id": None, "dependency_status": "UNKNOWN"},
        ]
    )
    assert report["raw_n"] == 2
    assert report["effective_n_known_clusters_only"] == 0
    assert report["unknown_dependency_n"] == 2
    assert report["unknown_cases_counted_as_independent"] is False


def test_listing_bundle_rejects_price_stop_target_currency_or_listing_mixing() -> None:
    identity = derive_research_identity_v2(
        _listing("XPEV", issuer_id="issuer-xpeng", name="XPeng ADS", exchange="NYSE", currency="USD", instrument_type="ADS")
    )
    listing_id = identity["listing_id"]
    valid = {
        "identity": identity,
        "ohlcv": {"listing_id": listing_id, "currency": "USD"},
        "price": {"listing_id": listing_id, "currency": "USD", "value": 20.0},
        "trading_hours": {"listing_id": listing_id, "currency": "USD"},
        "entry": {"listing_id": listing_id, "currency": "USD", "value": 20.0},
        "stop": {"listing_id": listing_id, "currency": "USD", "value": 18.0},
        "target": {"listing_id": listing_id, "currency": "USD", "value": 24.0},
    }
    assert validate_listing_scoped_bundle(valid)["status"] == "LISTING_CONSISTENT"

    with pytest.raises(ResearchIdentityError, match="gehört nicht"):
        validate_listing_scoped_bundle(
            {**valid, "stop": {"listing_id": "listing-9868-hk", "currency": "HKD"}}
        )
    for section in ("ohlcv", "price", "trading_hours", "target"):
        with pytest.raises(ResearchIdentityError, match="gehört nicht"):
            validate_listing_scoped_bundle(
                {
                    **valid,
                    section: {"listing_id": "listing-9868-hk", "currency": "HKD"},
                }
            )
    with pytest.raises(ResearchIdentityError, match="Listing-Währung"):
        validate_listing_scoped_bundle(
            {**valid, "target": {"listing_id": listing_id, "currency": "EUR"}}
        )
