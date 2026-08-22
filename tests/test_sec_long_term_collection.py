from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from sec_filing_sources import (
    SEC_COMPANY_FACTS_URL,
    SEC_SUBMISSIONS_URL,
    SEC_TICKER_MAP_URL,
    SecSourceError,
)
from sec_long_term_collection import collect_sec_long_term_context


NOW = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
USER_AGENT = "Investment Assistant tests@example.com"
CIK = 1045810
ACCESSION = "0001045810-26-000001"


def payloads(accession: str = ACCESSION) -> dict[str, object]:
    filings = {
        "filings": {
            "recent": {
                "accessionNumber": [accession],
                "filingDate": ["2026-03-01"],
                "form": ["10-K"],
                "primaryDocument": ["nvda-202610k.htm"],
            }
        }
    }
    revenue = {
        "units": {
            "USD": [
                {
                    "start": "2025-02-01",
                    "end": "2026-01-31",
                    "val": 120_000_000_000,
                    "accn": ACCESSION,
                    "fy": 2026,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2026-03-01",
                }
            ]
        }
    }
    facts = {
        "cik": CIK,
        "entityName": "NVIDIA CORP",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": revenue,
            }
        },
    }
    return {
        SEC_TICKER_MAP_URL: {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[CIK, "NVIDIA CORP", "NVDA", "Nasdaq"]],
        },
        SEC_SUBMISSIONS_URL.format(cik=CIK): filings,
        SEC_COMPANY_FACTS_URL.format(cik=CIK): facts,
    }


def loader_for(documents: dict[str, object], calls: list[str]):
    def loader(url: str, user_agent: str) -> object:
        calls.append(url)
        return documents[url]

    return loader


def test_collection_links_filing_and_xbrl_fact_but_keeps_full_gate_closed() -> None:
    documents = payloads()
    before = deepcopy(documents)
    calls: list[str] = []

    result = collect_sec_long_term_context(
        "nvda",
        user_agent=USER_AGENT,
        json_loader=loader_for(documents, calls),
        now=NOW,
    )

    assert result.available is True
    assert len(result.sources) == 1
    assert len(result.evidence) == 1
    assert result.evidence[0].section == "financial_quality"
    assert result.evidence[0].source_ids == (result.sources[0].source_id,)
    assert result.readiness.ready is False
    assert result.readiness.covered_sections == ("financial_quality",)
    assert "market_opportunity" in result.readiness.missing_sections
    assert calls == [
        SEC_TICKER_MAP_URL,
        SEC_SUBMISSIONS_URL.format(cik=CIK),
        SEC_COMPANY_FACTS_URL.format(cik=CIK),
    ]
    assert documents == before


def test_unknown_ticker_stops_without_companyfacts_request() -> None:
    documents = payloads()
    documents[SEC_TICKER_MAP_URL] = {"fields": ["cik", "name", "ticker"], "data": []}
    calls: list[str] = []

    result = collect_sec_long_term_context(
        "SAP.DE",
        user_agent=USER_AGENT,
        json_loader=loader_for(documents, calls),
        now=NOW,
    )

    assert result.available is False
    assert result.financial_snapshot is None
    assert result.evidence == ()
    assert calls == [SEC_TICKER_MAP_URL]


def test_companyfacts_failure_preserves_discovered_source_and_visible_warning() -> None:
    documents = payloads()
    calls: list[str] = []

    def loader(url: str, user_agent: str) -> object:
        calls.append(url)
        if url == SEC_COMPANY_FACTS_URL.format(cik=CIK):
            raise SecSourceError("Company Facts vorübergehend nicht verfügbar.")
        return documents[url]

    result = collect_sec_long_term_context(
        "NVDA",
        user_agent=USER_AGENT,
        json_loader=loader,
        now=NOW,
    )

    assert result.available is True
    assert len(result.sources) == 1
    assert result.financial_snapshot is None
    assert result.evidence == ()
    assert any("vorübergehend" in warning for warning in result.warnings)
    assert result.readiness.ready is False


def test_mismatched_xbrl_accession_never_creates_evidence() -> None:
    documents = payloads(accession="0001045810-26-000099")
    calls: list[str] = []

    result = collect_sec_long_term_context(
        "NVDA",
        user_agent=USER_AGENT,
        json_loader=loader_for(documents, calls),
        now=NOW,
    )

    assert result.sources
    assert result.evidence == ()
    assert result.readiness.covered_sections == ()
    assert any("passend entdeckte Filing" in warning for warning in result.warnings)
