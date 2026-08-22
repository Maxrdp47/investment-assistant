from __future__ import annotations

from asset_search import (
    looks_like_ticker,
    search_ticker_candidates,
    similar_ticker_suggestions,
)


class SearchResult:
    def __init__(self, quotes: list[dict]) -> None:
        self.quotes = quotes


def no_network_search(*_args, **_kwargs):
    raise RuntimeError("Netzwerk nicht verfügbar")


def test_known_name_works_without_yahoo_search() -> None:
    results = search_ticker_candidates("ServiceNow", no_network_search)

    assert results[0]["symbol"] == "NOW"
    assert results[0]["source"] == "Bekannte Beispiele"


def test_direct_ticker_is_prioritized_and_yahoo_duplicates_are_removed() -> None:
    def fake_search(*_args, **_kwargs):
        return SearchResult(
            [
                {
                    "symbol": "NVDA",
                    "quoteType": "EQUITY",
                    "exchange": "NMS",
                    "shortname": "NVIDIA",
                    "currency": "USD",
                },
                {
                    "symbol": "NVDA",
                    "quoteType": "EQUITY",
                    "exchange": "NMS",
                },
            ]
        )

    results = search_ticker_candidates("NVDA", fake_search)

    assert results[0]["symbol"] == "NVDA"
    assert results[0]["source"] == "Direkte Eingabe"
    assert [item["symbol"] for item in results].count("NVDA") == 1


def test_unsupported_yahoo_result_is_ignored() -> None:
    results = search_ticker_candidates(
        "Example",
        lambda *_args, **_kwargs: SearchResult(
            [{"symbol": "EXAMPLE", "quoteType": "OPTION", "exchange": "TEST"}]
        ),
    )

    assert results == []


def test_ticker_detection_and_typo_suggestions_remain_available() -> None:
    assert looks_like_ticker("BTC-EUR")
    assert not looks_like_ticker("service now")
    assert any(item["symbol"] == "NOW" for item in similar_ticker_suggestions("servicenoww"))
