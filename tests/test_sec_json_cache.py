from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import sec_json_cache
from sec_filing_sources import SEC_COMPANY_FACTS_URL, SEC_SUBMISSIONS_URL, SEC_TICKER_MAP_URL
from sec_json_cache import (
    SEC_JSON_CACHE_SCHEMA_VERSION,
    SecCachedJsonClient,
    load_fresh_sec_json_cache,
    save_sec_json_cache,
    sec_cache_path_for_url,
)


NOW = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
USER_AGENT = "Investment Assistant tests@example.com"
SUBMISSIONS_URL = SEC_SUBMISSIONS_URL.format(cik=1045810)
COMPANY_FACTS_URL = SEC_COMPANY_FACTS_URL.format(cik=1045810)


def test_cache_paths_are_fixed_by_whitelisted_sec_url(tmp_path: Path) -> None:
    ticker_path = sec_cache_path_for_url(SEC_TICKER_MAP_URL, tmp_path)
    submissions_path = sec_cache_path_for_url(SUBMISSIONS_URL, tmp_path)
    company_facts_path = sec_cache_path_for_url(COMPANY_FACTS_URL, tmp_path)

    assert ticker_path == tmp_path / "company_tickers_exchange.json"
    assert submissions_path == tmp_path / "submissions-CIK0001045810.json"
    assert company_facts_path == tmp_path / "companyfacts-CIK0001045810.json"
    with pytest.raises(ValueError, match="Nicht zugelassene"):
        sec_cache_path_for_url("https://example.com/evil", tmp_path)


def test_fresh_roundtrip_preserves_public_payload_without_contact_data(tmp_path: Path) -> None:
    path = sec_cache_path_for_url(SEC_TICKER_MAP_URL, tmp_path)
    payload = {"fields": ["cik", "ticker"], "data": [[1045810, "NVDA"]]}

    assert save_sec_json_cache(path, url=SEC_TICKER_MAP_URL, fetched_at=NOW, payload=payload) is True
    loaded = load_fresh_sec_json_cache(
        path,
        url=SEC_TICKER_MAP_URL,
        now=NOW + timedelta(hours=1),
        ttl=timedelta(hours=24),
    )

    assert loaded == payload
    assert USER_AGENT not in path.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == SEC_JSON_CACHE_SCHEMA_VERSION


def test_fresh_cache_prevents_network_and_returns_independent_copy(tmp_path: Path) -> None:
    calls: list[str] = []

    def upstream(url: str, user_agent: str) -> object:
        calls.append(url)
        return {"data": [["original"]]}

    client = SecCachedJsonClient(upstream, cache_dir=tmp_path, now_provider=lambda: NOW)
    first = client(SEC_TICKER_MAP_URL, USER_AGENT)
    first["data"][0][0] = "changed"
    second = client(SEC_TICKER_MAP_URL, USER_AGENT)

    assert second == {"data": [["original"]]}
    assert calls == [SEC_TICKER_MAP_URL]


def test_stale_or_corrupt_cache_is_refetched(tmp_path: Path) -> None:
    path = sec_cache_path_for_url(SUBMISSIONS_URL, tmp_path)
    assert save_sec_json_cache(
        path,
        url=SUBMISSIONS_URL,
        fetched_at=NOW - timedelta(hours=7),
        payload={"stale": True},
    ) is True
    calls: list[str] = []

    def upstream(url: str, user_agent: str) -> object:
        calls.append(url)
        return {"fresh": len(calls)}

    client = SecCachedJsonClient(upstream, cache_dir=tmp_path, now_provider=lambda: NOW)
    assert client(SUBMISSIONS_URL, USER_AGENT) == {"fresh": 1}
    path.write_text("{broken", encoding="utf-8")
    assert client(SUBMISSIONS_URL, USER_AGENT) == {"fresh": 2}
    assert calls == [SUBMISSIONS_URL, SUBMISSIONS_URL]


def test_future_or_unknown_schema_cache_is_never_served(tmp_path: Path) -> None:
    path = sec_cache_path_for_url(SEC_TICKER_MAP_URL, tmp_path)
    assert save_sec_json_cache(
        path,
        url=SEC_TICKER_MAP_URL,
        fetched_at=NOW + timedelta(hours=1),
        payload={"future": True},
    ) is True
    assert load_fresh_sec_json_cache(
        path,
        url=SEC_TICKER_MAP_URL,
        now=NOW,
        ttl=timedelta(hours=24),
    ) is None

    document = json.loads(path.read_text(encoding="utf-8"))
    document["schema_version"] = SEC_JSON_CACHE_SCHEMA_VERSION + 1
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_fresh_sec_json_cache(
        path,
        url=SEC_TICKER_MAP_URL,
        now=NOW,
        ttl=timedelta(hours=24),
    ) is None


def test_failed_atomic_replace_preserves_previous_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = sec_cache_path_for_url(SEC_TICKER_MAP_URL, tmp_path)
    assert save_sec_json_cache(path, url=SEC_TICKER_MAP_URL, fetched_at=NOW, payload={"old": True}) is True
    before = path.read_bytes()

    monkeypatch.setattr(sec_json_cache.os, "replace", lambda source, target: (_ for _ in ()).throw(OSError("fail")))

    assert save_sec_json_cache(
        path,
        url=SEC_TICKER_MAP_URL,
        fetched_at=NOW + timedelta(hours=1),
        payload={"new": True},
    ) is False
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_cache_rejects_wrong_filename_and_naive_time(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Dateiname"):
        save_sec_json_cache(
            tmp_path / "wrong.json",
            url=SEC_TICKER_MAP_URL,
            fetched_at=NOW,
            payload={},
        )
    with pytest.raises(ValueError, match="Zeitzone"):
        save_sec_json_cache(
            sec_cache_path_for_url(SEC_TICKER_MAP_URL, tmp_path),
            url=SEC_TICKER_MAP_URL,
            fetched_at=datetime(2026, 8, 2, 18, 0),
            payload={},
        )
