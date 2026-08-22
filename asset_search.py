from __future__ import annotations

import difflib
from collections.abc import Callable


KNOWN_TICKERS = {
    "xiaomi": ["1810.HK", "3CP.F", "3CP.DE", "XIACY"],
    "xiaomi aktie": ["1810.HK", "3CP.F", "3CP.DE", "XIACY"],
    "xiaomi corporation": ["1810.HK", "3CP.F", "3CP.DE", "XIACY"],
    "palantir": ["PLTR"],
    "nvidia": ["NVDA"],
    "servicenow": ["NOW"],
    "service now": ["NOW"],
    "bitcoin": ["BTC-EUR", "BTC-USD"],
    "btc": ["BTC-EUR", "BTC-USD"],
    "msci world": ["EUNL.DE", "IWDA.AS", "URTH"],
    "msci world etf": ["EUNL.DE", "IWDA.AS", "URTH"],
}

KNOWN_TICKER_NAMES = {
    "3CP.F": {"name": "Xiaomi Corporation", "exchange": "Frankfurt Stock Exchange", "currency": "EUR", "quote_type": "EQUITY"},
    "3CP.DE": {"name": "Xiaomi Corporation", "exchange": "Xetra", "currency": "EUR", "quote_type": "EQUITY"},
    "1810.HK": {"name": "Xiaomi Corporation", "exchange": "Hong Kong Stock Exchange", "currency": "HKD", "quote_type": "EQUITY"},
    "XIACY": {"name": "Xiaomi Corporation ADR", "exchange": "OTC Markets", "currency": "USD", "quote_type": "EQUITY"},
    "PLTR": {"name": "Palantir Technologies Inc.", "exchange": "NYSE", "currency": "USD", "quote_type": "EQUITY"},
    "NVDA": {"name": "NVIDIA Corporation", "exchange": "NASDAQ", "currency": "USD", "quote_type": "EQUITY"},
    "NOW": {"name": "ServiceNow Inc.", "exchange": "NYSE", "currency": "USD", "quote_type": "EQUITY"},
    "BTC-EUR": {"name": "Bitcoin EUR", "exchange": "CCC", "currency": "EUR", "quote_type": "CRYPTOCURRENCY"},
    "BTC-USD": {"name": "Bitcoin USD", "exchange": "CCC", "currency": "USD", "quote_type": "CRYPTOCURRENCY"},
    "EUNL.DE": {"name": "iShares Core MSCI World UCITS ETF", "exchange": "Xetra", "currency": "EUR", "quote_type": "ETF"},
    "IWDA.AS": {"name": "iShares Core MSCI World UCITS ETF", "exchange": "Amsterdam", "currency": "EUR", "quote_type": "ETF"},
    "URTH": {"name": "iShares MSCI World ETF", "exchange": "NYSE Arca", "currency": "USD", "quote_type": "ETF"},
}


def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def looks_like_ticker(query: str) -> bool:
    clean = query.strip()
    if not clean or " " in clean:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-=^")
    has_market_suffix = any(char in clean for char in ".-=^")
    has_digit = any(char.isdigit() for char in clean)
    is_uppercase_symbol = clean == clean.upper()
    return all(char in allowed for char in clean) and (is_uppercase_symbol or has_market_suffix or has_digit)


def ticker_candidate(
    symbol: str,
    name: str | None = None,
    exchange: str | None = None,
    quote_type: str | None = None,
    currency: str | None = None,
    source: str = "Yahoo Finance",
) -> dict:
    metadata = KNOWN_TICKER_NAMES.get(symbol.upper(), {})
    return {
        "symbol": symbol.upper(),
        "name": name or metadata.get("name") or symbol.upper(),
        "exchange": exchange or metadata.get("exchange") or "Daten nicht verfügbar",
        "quote_type": quote_type or metadata.get("quote_type") or "Daten nicht verfügbar",
        "currency": currency or metadata.get("currency") or "",
        "source": source,
    }


def dedupe_candidates(candidates: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for candidate in candidates:
        symbol = str(candidate.get("symbol", "")).upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        candidate["symbol"] = symbol
        unique.append(candidate)
    return unique


def search_ticker_candidates(query: str, search_factory: Callable[..., object]) -> list[dict]:
    """Find plausible Yahoo instruments while keeping curated fallbacks available."""
    clean_query = normalize_query(query)
    if not clean_query:
        return []

    candidates: list[dict] = []
    if clean_query in KNOWN_TICKERS:
        candidates.extend(ticker_candidate(symbol, source="Bekannte Beispiele") for symbol in KNOWN_TICKERS[clean_query])
    else:
        for known_name, symbols in KNOWN_TICKERS.items():
            if known_name in clean_query or clean_query in known_name:
                candidates.extend(ticker_candidate(symbol, source="Bekannte Beispiele") for symbol in symbols)
                break

    if clean_query not in KNOWN_TICKERS and looks_like_ticker(query):
        candidates.insert(0, ticker_candidate(query.strip(), source="Direkte Eingabe"))

    try:
        search = search_factory(query, max_results=8)
        quotes = getattr(search, "quotes", None) or []
        for quote in quotes:
            symbol = quote.get("symbol")
            quote_type = quote.get("quoteType", "")
            exchange = quote.get("exchDisp") or quote.get("exchange", "")
            name = quote.get("longname") or quote.get("shortname") or quote.get("name")
            currency = quote.get("currency") or ""
            if symbol and exchange and quote_type in {"EQUITY", "ETF", "CRYPTOCURRENCY", "MUTUALFUND"}:
                candidates.append(ticker_candidate(symbol, name, exchange, quote_type, currency))
    except Exception:
        pass

    return dedupe_candidates(candidates)[:8]


def format_candidate(candidate: dict) -> str:
    name = candidate.get("name") or candidate.get("symbol")
    symbol = candidate.get("symbol", "")
    exchange = candidate.get("exchange") or "Daten nicht verfügbar"
    return f"{symbol} - {name} ({exchange})"


def similar_ticker_suggestions(query: str) -> list[dict]:
    clean_query = normalize_query(query)
    search_space = list(KNOWN_TICKERS.keys()) + list(KNOWN_TICKER_NAMES.keys())
    matches = difflib.get_close_matches(clean_query, [item.lower() for item in search_space], n=5, cutoff=0.35)
    candidates: list[dict] = []
    for match in matches:
        if match in KNOWN_TICKERS:
            candidates.extend(ticker_candidate(symbol, source="Ähnlicher Treffer") for symbol in KNOWN_TICKERS[match])
        else:
            symbol = match.upper()
            if symbol in KNOWN_TICKER_NAMES:
                candidates.append(ticker_candidate(symbol, source="Ähnlicher Treffer"))
    return dedupe_candidates(candidates)[:5]
