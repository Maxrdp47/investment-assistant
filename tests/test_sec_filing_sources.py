from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError

import pytest

import sec_filing_sources
from sec_filing_sources import (
    SEC_SUBMISSIONS_URL,
    SEC_TICKER_MAP_URL,
    SecFairAccessClient,
    SecSourceError,
    discover_sec_filing_sources,
    load_sec_json,
    validate_sec_user_agent,
)


NOW = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
USER_AGENT = "Investment Assistant tests@example.com"


def ticker_payload() -> dict:
    return {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [1045810, "NVIDIA CORP", "NVDA", "Nasdaq"],
            [1067983, "BERKSHIRE HATHAWAY INC", "BRK-B", "NYSE"],
        ],
    }


def submissions_payload() -> dict:
    return {
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0001045810-26-000111",
                    "0001045810-26-000090",
                    "0001045810-26-000080",
                    "0001045810-25-000050",
                ],
                "filingDate": ["2026-07-20", "2026-06-10", "2026-05-01", "2025-11-20"],
                "form": ["10-Q", "8-K", "10-Q", "10-K"],
                "primaryDocument": ["nvda-20260720.htm", "nvda-8k.htm", "nvda-20260501.htm", "nvda-202510k.htm"],
            }
        }
    }


def loader_for(mapping: object, submissions: object, calls: list[tuple[str, str]]):
    def loader(url: str, user_agent: str) -> object:
        calls.append((url, user_agent))
        if url == SEC_TICKER_MAP_URL:
            return mapping
        if url == SEC_SUBMISSIONS_URL.format(cik=1045810):
            return submissions
        raise AssertionError(f"Unerwartete URL: {url}")

    return loader


def test_discovers_recent_official_filings_with_deterministic_archive_urls() -> None:
    calls: list[tuple[str, str]] = []
    mapping = ticker_payload()
    submissions = submissions_payload()
    original_mapping = deepcopy(mapping)
    original_submissions = deepcopy(submissions)

    result = discover_sec_filing_sources(
        "nvda",
        user_agent=USER_AGENT,
        json_loader=loader_for(mapping, submissions, calls),
        now=NOW,
    )

    assert result.available is True
    assert result.ticker == "NVDA"
    assert result.cik == 1045810
    assert result.company_name == "NVIDIA CORP"
    assert [source.source_type for source in result.sources] == [
        "quarterly_report",
        "quarterly_report",
        "annual_report",
    ]
    assert result.sources[0].url == (
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000111/nvda-20260720.htm"
    )
    assert all(source.publisher.endswith("(SEC)") for source in result.sources)
    assert all(USER_AGENT not in repr(source) for source in result.sources)
    assert [url for url, _ in calls] == [
        SEC_TICKER_MAP_URL,
        SEC_SUBMISSIONS_URL.format(cik=1045810),
    ]
    assert mapping == original_mapping
    assert submissions == original_submissions


def test_exact_ticker_match_supports_class_share_symbol_without_guessing() -> None:
    calls: list[tuple[str, str]] = []
    mapping = ticker_payload()

    def loader(url: str, user_agent: str) -> object:
        calls.append((url, user_agent))
        if url == SEC_TICKER_MAP_URL:
            return mapping
        return {"filings": {"recent": {field: [] for field in ("accessionNumber", "filingDate", "form", "primaryDocument")}}}

    result = discover_sec_filing_sources("BRK-B", user_agent=USER_AGENT, json_loader=loader, now=NOW)

    assert result.cik == 1067983
    assert result.company_name == "BERKSHIRE HATHAWAY INC"
    assert len(calls) == 2


def test_unknown_ticker_stops_after_mapping_without_inventing_company() -> None:
    calls: list[tuple[str, str]] = []
    result = discover_sec_filing_sources(
        "SAP.DE",
        user_agent=USER_AGENT,
        json_loader=loader_for(ticker_payload(), submissions_payload(), calls),
        now=NOW,
    )

    assert result.available is False
    assert result.cik is None
    assert result.sources == ()
    assert len(calls) == 1
    assert "keine offizielle US-Filingquelle" in result.status


def test_stale_filings_are_visible_warnings_not_accepted_sources() -> None:
    payload = submissions_payload()
    payload["filings"]["recent"]["filingDate"] = ["2024-01-01"] * 4
    calls: list[tuple[str, str]] = []

    result = discover_sec_filing_sources(
        "NVDA",
        user_agent=USER_AGENT,
        json_loader=loader_for(ticker_payload(), payload, calls),
        now=NOW,
    )

    assert result.available is False
    assert result.sources == ()
    assert any("veraltet" in warning for warning in result.warnings)


@pytest.mark.parametrize("user_agent", ["", "InvestmentAssistant", "test@example.com", "Bad\nAgent test@example.com"])
def test_fair_access_user_agent_is_required_before_network(user_agent: str) -> None:
    calls: list[tuple[str, str]] = []

    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        discover_sec_filing_sources(
            "NVDA",
            user_agent=user_agent,
            json_loader=loader_for(ticker_payload(), submissions_payload(), calls),
            now=NOW,
        )

    assert calls == []


def test_malformed_sec_payload_fails_explicitly_without_partial_sources() -> None:
    calls: list[tuple[str, str]] = []

    with pytest.raises(SecSourceError, match="Pflichtfelder"):
        discover_sec_filing_sources(
            "NVDA",
            user_agent=USER_AGENT,
            json_loader=loader_for({"fields": ["ticker"], "data": []}, {}, calls),
            now=NOW,
        )


def test_document_paths_and_accession_numbers_are_not_trusted() -> None:
    payload = submissions_payload()
    payload["filings"]["recent"]["accessionNumber"][0] = "../../invalid"
    payload["filings"]["recent"]["primaryDocument"][2] = "../escape.htm"
    calls: list[tuple[str, str]] = []

    result = discover_sec_filing_sources(
        "NVDA",
        user_agent=USER_AGENT,
        json_loader=loader_for(ticker_payload(), payload, calls),
        now=NOW,
    )

    assert all(".." not in source.url for source in result.sources)
    assert [source.source_type for source in result.sources] == ["annual_report"]


def test_fair_access_client_reuses_ticker_map_across_assets() -> None:
    underlying_calls: list[str] = []
    timeline = [0.0]

    def sleeper(seconds: float) -> None:
        timeline[0] += seconds

    def loader(url: str, user_agent: str) -> object:
        underlying_calls.append(url)
        if url == SEC_TICKER_MAP_URL:
            return ticker_payload()
        return {
            "filings": {
                "recent": {
                    field: []
                    for field in ("accessionNumber", "filingDate", "form", "primaryDocument")
                }
            }
        }

    client = SecFairAccessClient(
        USER_AGENT,
        loader=loader,
        clock=lambda: timeline[0],
        sleeper=sleeper,
    )
    discover_sec_filing_sources("NVDA", user_agent=USER_AGENT, json_loader=client, now=NOW)
    discover_sec_filing_sources("BRK-B", user_agent=USER_AGENT, json_loader=client, now=NOW)

    assert underlying_calls.count(SEC_TICKER_MAP_URL) == 1
    assert len(underlying_calls) == 3
    assert timeline[0] == pytest.approx(0.24)


def test_fair_access_client_returns_copy_of_cached_ticker_map() -> None:
    calls: list[str] = []

    def loader(url: str, user_agent: str) -> object:
        calls.append(url)
        return ticker_payload()

    client = SecFairAccessClient(USER_AGENT, loader=loader)
    first = client(SEC_TICKER_MAP_URL, USER_AGENT)
    assert isinstance(first, dict)
    first["data"][0][2] = "CHANGED"
    second = client(SEC_TICKER_MAP_URL, USER_AGENT)

    assert second["data"][0][2] == "NVDA"
    assert calls == [SEC_TICKER_MAP_URL]


def test_fair_access_client_does_not_cache_failed_ticker_request() -> None:
    attempts = [0]

    def loader(url: str, user_agent: str) -> object:
        attempts[0] += 1
        if attempts[0] == 1:
            raise SecSourceError("simulierter Fehler")
        return ticker_payload()

    client = SecFairAccessClient(USER_AGENT, loader=loader)

    with pytest.raises(SecSourceError, match="simulierter Fehler"):
        client(SEC_TICKER_MAP_URL, USER_AGENT)
    result = client(SEC_TICKER_MAP_URL, USER_AGENT)

    assert isinstance(result, dict)
    assert attempts[0] == 2


def test_fair_access_client_rejects_contact_change_and_unsafe_interval() -> None:
    with pytest.raises(ValueError, match="Anfrageintervall"):
        SecFairAccessClient(USER_AGENT, minimum_interval_seconds=0.05)

    client = SecFairAccessClient(USER_AGENT, loader=lambda url, agent: {})
    with pytest.raises(ValueError, match="anderen Kontaktkennung"):
        client(SEC_TICKER_MAP_URL, "Other Project other@example.com")


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]


def test_transport_retries_retryable_http_error_then_returns_json(monkeypatch) -> None:
    attempts = [0]
    sleeps: list[float] = []
    headers = Message()
    headers["Retry-After"] = "0"

    def fake_urlopen(request, timeout: int):
        attempts[0] += 1
        if attempts[0] == 1:
            raise HTTPError(request.full_url, 429, "rate limited", headers, None)
        return FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(sec_filing_sources, "urlopen", fake_urlopen)
    monkeypatch.setattr(sec_filing_sources.time, "sleep", sleeps.append)

    result = load_sec_json(SEC_TICKER_MAP_URL, USER_AGENT)

    assert result == {"ok": True}
    assert attempts[0] == 2
    assert sleeps == [0.1]


def test_transport_does_not_retry_permanent_http_error_or_expose_contact(monkeypatch) -> None:
    attempts = [0]

    def fake_urlopen(request, timeout: int):
        attempts[0] += 1
        raise HTTPError(request.full_url, 404, "missing", Message(), None)

    monkeypatch.setattr(sec_filing_sources, "urlopen", fake_urlopen)

    with pytest.raises(SecSourceError, match="HTTP 404") as error:
        load_sec_json(SEC_TICKER_MAP_URL, USER_AGENT)

    assert attempts[0] == 1
    assert USER_AGENT not in str(error.value)


def test_transport_rejects_invalid_utf8_json_without_retry(monkeypatch) -> None:
    attempts = [0]

    def fake_urlopen(request, timeout: int):
        attempts[0] += 1
        return FakeResponse(b"not-json")

    monkeypatch.setattr(sec_filing_sources, "urlopen", fake_urlopen)

    with pytest.raises(SecSourceError, match="gültiges UTF-8-JSON"):
        load_sec_json(SEC_TICKER_MAP_URL, USER_AGENT)

    assert attempts[0] == 1
