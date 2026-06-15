from __future__ import annotations

import json
import math
import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


APP_TITLE = "Investment-Assistent"
DISCLAIMER = "Dies ist keine Finanzberatung, sondern eine technische Analysehilfe."
YFINANCE_CACHE_DIR = Path(__file__).resolve().parent / ".yfinance-cache"
PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.json"
SEARCH_HISTORY_PATH = Path(__file__).resolve().parent / "search_history.json"
TRADE_HISTORY_PATH = Path(__file__).resolve().parent / "trade_history.json"
FORWARD_TEST_PATH = Path(__file__).resolve().parent / "forward_tests.json"
YFINANCE_CACHE_DIR.mkdir(exist_ok=True)
yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))

PERIOD_OPTIONS = {
    "Heute": "1d",
    "5 Tage": "5d",
    "1 Monat": "1mo",
    "6 Monate": "6mo",
    "1 Jahr": "1y",
    "5 Jahre": "5y",
    "Max": "max",
}

INTERVAL_OPTIONS = ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"]
REFRESH_OPTIONS = {
    "Aus": 0,
    "30 Sekunden": 30,
    "1 Minute": 60,
    "5 Minuten": 300,
}

KNOWN_TICKERS = {
    "xiaomi": ["1810.HK", "3CP.F", "3CP.DE", "XIACY"],
    "xiaomi aktie": ["1810.HK", "3CP.F", "3CP.DE", "XIACY"],
    "xiaomi corporation": ["1810.HK", "3CP.F", "3CP.DE", "XIACY"],
    "palantir": ["PLTR"],
    "nvidia": ["NVDA"],
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
    "BTC-EUR": {"name": "Bitcoin EUR", "exchange": "CCC", "currency": "EUR", "quote_type": "CRYPTOCURRENCY"},
    "BTC-USD": {"name": "Bitcoin USD", "exchange": "CCC", "currency": "USD", "quote_type": "CRYPTOCURRENCY"},
    "EUNL.DE": {"name": "iShares Core MSCI World UCITS ETF", "exchange": "Xetra", "currency": "EUR", "quote_type": "ETF"},
    "IWDA.AS": {"name": "iShares Core MSCI World UCITS ETF", "exchange": "Amsterdam", "currency": "EUR", "quote_type": "ETF"},
    "URTH": {"name": "iShares MSCI World ETF", "exchange": "NYSE Arca", "currency": "USD", "quote_type": "ETF"},
}


@dataclass
class ScoreResult:
    score: float
    recommendation: str
    reasons: list[str]
    breakdown: list[tuple[str, float, str]] | None = None


@dataclass
class ModuleScore:
    score: float
    summary: str
    details: list[str]


@dataclass
class MarketPhase:
    phase: str
    summary: str
    probabilities: dict[str, int]


@dataclass
class RiskReward:
    risk_pct: float | None
    reward_pct: float | None
    ratio: float | None
    score: float
    summary: str


@dataclass
class AssetProfile:
    asset_type: str
    quote_type: str
    summary: str
    weights: dict[str, float]


@dataclass
class PortfolioResult:
    enabled: bool
    available: bool
    score: float | None
    summary: str
    details: list[str]
    asset_weight: float | None = None
    cash_weight: float | None = None
    position_value: float | None = None
    adjusted_score: float | None = None


@dataclass
class ResearchModule:
    name: str
    score: float | None
    summary: str
    details: list[str]
    beginner: str


@dataclass
class ResearchPack:
    data_quality: ResearchModule
    modules: list[ResearchModule]
    institutional_modules: list[ResearchModule]
    confidence: ResearchModule
    uncertainty_factors: list[str]
    scenarios: list[dict]
    buy_zones: list[dict]
    action: str
    conclusion: dict[str, str | list[str]]


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


@st.cache_data(ttl=60 * 60)
def find_ticker_candidates(query: str) -> list[dict]:
    """Find plausible Yahoo Finance instruments and keep manual control visible."""
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

    # yfinance search is convenient when available, but this app also works
    # with the curated examples above and a manual ticker field.
    try:
        search = yf.Search(query, max_results=8)
        quotes = search.quotes or []
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


def load_search_history() -> list[dict]:
    if not SEARCH_HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(SEARCH_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_successful_search(query: str, candidate: dict) -> None:
    entry = {
        "query": query.strip(),
        "symbol": candidate.get("symbol", ""),
        "name": candidate.get("name", ""),
        "exchange": candidate.get("exchange", ""),
        "currency": candidate.get("currency", ""),
    }
    if not entry["query"] or not entry["symbol"]:
        return

    history = [item for item in load_search_history() if item.get("symbol") != entry["symbol"]]
    history.insert(0, entry)
    try:
        SEARCH_HISTORY_PATH.write_text(json.dumps(history[:12], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_trade_history() -> list[dict]:
    if not TRADE_HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(TRADE_HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def load_forward_tests() -> list[dict]:
    if not FORWARD_TEST_PATH.exists():
        return []
    try:
        data = json.loads(FORWARD_TEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_forward_test(record: dict) -> bool:
    history = load_forward_tests()
    history.insert(0, record)
    try:
        FORWARD_TEST_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def calibration_status_rows(history: list[dict]) -> tuple[str, list[dict[str, str]]]:
    cases = len(history)
    if cases < 20:
        status = "Datenbasis zu klein. Score-Gewichtungen werden nicht angepasst."
        permission = "Keine Kalibrierung erlaubt"
    elif cases <= 50:
        status = "Vorsichtige Hinweise möglich. Score-Gewichtungen bleiben unverändert."
        permission = "Nur Hinweise"
    else:
        status = "Kalibrierungsvorschläge erlaubt. Änderungen müssen dokumentiert und getestet werden."
        permission = "Vorschläge erlaubt"

    rows = [
        {"Messpunkt": "Dokumentierte Fälle", "Wert": str(cases), "Bedeutung": status},
        {"Messpunkt": "Mindestdatenmenge", "Wert": "20 Fälle", "Bedeutung": "Darunter sind Trefferquoten statistisch zu dünn."},
        {"Messpunkt": "Kalibrierungsregel", "Wert": permission, "Bedeutung": "Version 1 ändert Gewichtungen niemals automatisch."},
    ]
    return status, rows


@st.cache_data(ttl=60)
def load_price_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        data = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Yahoo-Finance-Daten konnten nicht geladen werden: {exc}") from exc

    if data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.rename(columns=str.title)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    return data[[col for col in needed if col in data.columns]].dropna(subset=["Close"])


def calculate_indicators(data: pd.DataFrame, interval: str) -> pd.DataFrame:
    df = data.copy()
    close = df["Close"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    df["SMA_50"] = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()

    df["Volume_SMA_20"] = df["Volume"].rolling(20).mean() if "Volume" in df else np.nan

    annualization = {"1d": 252, "1wk": 52, "1mo": 12}.get(interval, 252)
    returns = close.pct_change()
    df["Volatility"] = returns.rolling(20).std() * math.sqrt(annualization)
    return df


def local_levels(series: pd.Series, mode: str, window: int = 3) -> list[float]:
    """Return local lows or highs sorted by relevance to the current price."""
    values = series.dropna()
    if len(values) < window * 2 + 1:
        return []

    levels: list[float] = []
    for idx in range(window, len(values) - window):
        current = values.iloc[idx]
        neighborhood = values.iloc[idx - window : idx + window + 1]
        if mode == "support" and current == neighborhood.min():
            levels.append(float(current))
        if mode == "resistance" and current == neighborhood.max():
            levels.append(float(current))

    current_price = float(values.iloc[-1])
    if mode == "support":
        filtered = [level for level in levels if level < current_price]
    else:
        filtered = [level for level in levels if level > current_price]

    filtered.sort(key=lambda level: abs(level - current_price))
    return filtered[:3]


def pct_distance(price: float, level: float | None) -> float | None:
    if level is None or price == 0:
        return None
    return (price - level) / price


def clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


def value_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def percent_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.1f}%"


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def load_portfolio_file() -> tuple[dict | None, str | None]:
    if not PORTFOLIO_PATH.exists():
        return None, "Keine Portfolio-Datei gefunden. Portfolio-Modus kann nicht verwendet werden."
    try:
        with PORTFOLIO_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return None, "portfolio.json ist ungültig. Erwartet wird ein JSON-Objekt."
        return data, None
    except json.JSONDecodeError as exc:
        return None, f"portfolio.json ist kein gültiges JSON: {exc}"
    except OSError as exc:
        return None, f"portfolio.json konnte nicht gelesen werden: {exc}"


def portfolio_positions(portfolio: dict) -> list[dict]:
    positions = portfolio.get("positions", [])
    if not isinstance(positions, list):
        return []
    return [position for position in positions if isinstance(position, dict)]


def portfolio_position_ticker(position: dict) -> str:
    return str(position.get("ticker") or position.get("symbol") or "").strip()


def portfolio_position_shares(position: dict) -> float | None:
    return value_or_none(position.get("shares") or position.get("quantity"))


def portfolio_position_buy_price(position: dict) -> float | None:
    return value_or_none(position.get("buy_price") or position.get("average_buy_price"))


def known_ticker_fallbacks(symbol: str) -> list[str]:
    symbol_norm = normalize_symbol(symbol)
    for candidates in KNOWN_TICKERS.values():
        normalized_candidates = [normalize_symbol(candidate) for candidate in candidates]
        if symbol_norm in normalized_candidates:
            original_meta = KNOWN_TICKER_NAMES.get(symbol_norm, {})
            original_currency = original_meta.get("currency")
            alternatives = [candidate for candidate in candidates if normalize_symbol(candidate) != symbol_norm]
            if original_currency:
                alternatives.sort(
                    key=lambda candidate: KNOWN_TICKER_NAMES.get(normalize_symbol(candidate), {}).get("currency") != original_currency
                )
            return alternatives
    return []


@st.cache_data(ttl=60)
def latest_portfolio_price(symbol: str) -> float | None:
    for candidate in [symbol, *known_ticker_fallbacks(symbol)]:
        try:
            data = load_price_data(candidate, "5d", "1d")
            if data.empty:
                continue
            close = data["Close"].dropna()
            if not close.empty:
                return float(close.iloc[-1])
        except Exception:
            continue
    return None


def position_market_value(position: dict) -> float:
    value = value_or_none(position.get("market_value"))
    if value is not None:
        return value
    quantity = portfolio_position_shares(position)
    price = value_or_none(position.get("current_price") or position.get("price"))
    if price is None and quantity is not None:
        symbol = portfolio_position_ticker(position)
        price = latest_portfolio_price(symbol) if symbol else None
    if quantity is not None and price is not None:
        return quantity * price
    return 0.0


def evaluate_portfolio(
    symbol: str,
    portfolio_enabled: bool,
    asset_score: float,
    asset_profile: AssetProfile | None = None,
) -> PortfolioResult:
    if not portfolio_enabled:
        return PortfolioResult(
            enabled=False,
            available=False,
            score=None,
            summary="Portfolio-Modus: AUS. Die Analyse bewertet nur das Asset selbst.",
            details=["Keine Berücksichtigung bestehender Positionen, Klumpenrisiko oder Cash-Reserve."],
        )

    portfolio, error = load_portfolio_file()
    if error:
        return PortfolioResult(
            enabled=True,
            available=False,
            score=None,
            summary=error,
            details=[error],
        )

    assert portfolio is not None
    positions = portfolio_positions(portfolio)
    cash = value_or_none(portfolio.get("cash")) or 0.0
    target_cash_pct = value_or_none(portfolio.get("target_cash_pct"))
    if target_cash_pct is None:
        target_cash_pct = 0.10
    planned_buy = value_or_none(portfolio.get("planned_buy_amount")) or 0.0
    overweight_limit = value_or_none(portfolio.get("max_single_position_pct"))
    if overweight_limit is None:
        overweight_limit = 0.20

    total_positions = sum(position_market_value(position) for position in positions)
    total_value = total_positions + cash
    if total_value <= 0:
        return PortfolioResult(
            enabled=True,
            available=True,
            score=5.0,
            summary="Portfolio-Datei gefunden, aber Gesamtwert ist 0. Depot-Score wird neutral bewertet.",
            details=["Bitte market_value oder quantity/current_price in portfolio.json eintragen."],
            cash_weight=None,
        )

    symbol_norm = normalize_symbol(symbol)
    matching_positions = [
        position for position in positions if normalize_symbol(portfolio_position_ticker(position)) == symbol_norm
    ]
    position_value = sum(position_market_value(position) for position in matching_positions)
    asset_weight = position_value / total_value
    cash_weight = cash / total_value
    post_buy_total = total_value + planned_buy
    post_buy_position = position_value + planned_buy
    post_buy_weight = post_buy_position / post_buy_total if post_buy_total > 0 else asset_weight
    post_buy_cash_weight = max(cash - planned_buy, 0.0) / post_buy_total if post_buy_total > 0 else cash_weight

    score = 10.0
    details: list[str] = []
    if matching_positions:
        details.append(f"Du hältst dieses Asset bereits: {format_currency(position_value)} ({asset_weight * 100:.1f}% des Portfolios).")
        for position in matching_positions:
            avg_buy_price = portfolio_position_buy_price(position)
            if avg_buy_price is not None:
                details.append(f"Durchschnittlicher Einstandskurs laut portfolio.json: {format_currency(avg_buy_price)}.")
            lots = position.get("lots")
            if isinstance(lots, list) and lots:
                details.append(f"Einzelkäufe erfasst: {len(lots)} Lots.")
    else:
        details.append("Du hältst dieses Asset laut portfolio.json noch nicht.")

    if asset_weight > overweight_limit:
        penalty = min(4.0, (asset_weight - overweight_limit) * 25)
        score -= penalty
        details.append(f"Übergewichtet: aktueller Anteil {asset_weight * 100:.1f}% liegt über dem Limit von {overweight_limit * 100:.1f}%.")
    else:
        details.append(f"Kein Klumpenrisiko nach Limit: aktueller Anteil {asset_weight * 100:.1f}% von maximal {overweight_limit * 100:.1f}%.")

    if planned_buy > 0:
        details.append(f"Geplanter Nachkauf aus portfolio.json: {format_currency(planned_buy)}.")
        if post_buy_weight > overweight_limit:
            penalty = min(3.0, (post_buy_weight - overweight_limit) * 25)
            score -= penalty
            details.append(f"Nachkauf würde den Anteil auf {post_buy_weight * 100:.1f}% erhöhen und damit das Risiko steigern.")
        else:
            details.append(f"Nachkauf würde den Anteil auf {post_buy_weight * 100:.1f}% erhöhen und bleibt unter dem Limit.")
        if post_buy_cash_weight < target_cash_pct:
            penalty = min(2.5, (target_cash_pct - post_buy_cash_weight) * 20)
            score -= penalty
            details.append(f"Cash-Reserve nach Nachkauf wäre {post_buy_cash_weight * 100:.1f}% und damit unter Ziel {target_cash_pct * 100:.1f}%.")
        else:
            details.append(f"Cash-Reserve nach Nachkauf bleibt bei {post_buy_cash_weight * 100:.1f}% und damit ausreichend.")
    else:
        details.append("Kein geplanter Nachkaufbetrag eingetragen. Nachkauf-Risiko wird nur anhand der aktuellen Gewichtung bewertet.")
        if cash_weight < target_cash_pct:
            penalty = min(2.0, (target_cash_pct - cash_weight) * 20)
            score -= penalty
            details.append(f"Cash-Reserve ist niedrig: {cash_weight * 100:.1f}% statt Ziel {target_cash_pct * 100:.1f}%.")
        else:
            details.append(f"Cash-Reserve ist ausreichend: {cash_weight * 100:.1f}% bei Ziel {target_cash_pct * 100:.1f}%.")

    if asset_profile and asset_profile.asset_type == "Krypto" and asset_weight > 0.15:
        score -= 1.0
        details.append("Krypto-Anteil ist hoch; wegen hoher Schwankungen wird ein zusätzlicher Risikoabschlag berücksichtigt.")

    score = round(clamp(score), 1)
    if score >= 7:
        summary = "Depot-Score positiv: Portfolio spricht nicht gegen die Asset-Empfehlung."
    elif score >= 5:
        summary = "Depot-Score neutral: Nachkauf nur vorsichtig, Portfolio-Risiken sind moderat."
    else:
        summary = "Depot-Score schwach: Portfolio spricht gegen einen zusätzlichen Nachkauf."

    return PortfolioResult(
        enabled=True,
        available=True,
        score=score,
        summary=summary,
        details=details,
        asset_weight=asset_weight,
        cash_weight=cash_weight,
        position_value=position_value,
    )


def calculate_risk_reward(close: float, supports: list[float], resistances: list[float]) -> RiskReward:
    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None
    risk_pct = (nearest_support - close) / close if nearest_support else None
    reward_pct = (nearest_resistance - close) / close if nearest_resistance else None

    ratio = None
    score = 5.0
    if risk_pct is not None and reward_pct is not None and risk_pct < 0 and reward_pct > 0:
        ratio = reward_pct / abs(risk_pct)
        score = clamp(ratio / 3 * 10)
        summary = f"Risiko bis Unterstützung {percent_text(risk_pct)}, Potenzial bis Widerstand {percent_text(reward_pct)}, CRV {ratio:.2f}."
    elif risk_pct is not None:
        summary = f"Nächste Unterstützung liegt {percent_text(risk_pct)} entfernt; kein klarer Widerstand oberhalb erkannt."
        score = 5.5 if abs(risk_pct) <= 0.06 else 4.0
    elif reward_pct is not None:
        summary = f"Nächster Widerstand liegt {percent_text(reward_pct)} entfernt; keine klare Unterstützung unterhalb erkannt."
        score = 4.5
    else:
        summary = "Keine belastbaren Unterstützungs- und Widerstandszonen für ein CRV erkannt."
        score = 4.0

    return RiskReward(risk_pct=risk_pct, reward_pct=reward_pct, ratio=ratio, score=round(score, 1), summary=summary)


def detect_market_phase(df: pd.DataFrame) -> MarketPhase:
    latest = df.dropna(subset=["Close"]).iloc[-1]
    close = float(latest["Close"])
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    rsi = value_or_none(latest.get("RSI_14"))
    macd = value_or_none(latest.get("MACD"))
    signal = value_or_none(latest.get("MACD_Signal"))

    recent = df.dropna(subset=["Close"]).tail(120)
    recent_high = float(recent["Close"].max()) if not recent.empty else close
    recent_low = float(recent["Close"].min()) if not recent.empty else close
    drawdown = (close - recent_high) / recent_high if recent_high else 0.0
    rebound = (close - recent_low) / recent_low if recent_low else 0.0
    range_width = (recent_high - recent_low) / close if close else 0.0

    macd_positive = macd is not None and signal is not None and macd > signal
    macd_negative = macd is not None and signal is not None and macd < signal
    uptrend = sma_50 is not None and close > sma_50 and (sma_200 is None or sma_50 > sma_200)
    downtrend = sma_50 is not None and close < sma_50 and (sma_200 is None or sma_50 < sma_200)

    if uptrend and drawdown <= -0.08:
        phase = "Korrektur innerhalb eines Aufwärtstrends"
        summary = "Der übergeordnete Trend ist positiv, aber der Kurs korrigiert deutlich vom jüngsten Hoch."
    elif downtrend and (rsi is None or rsi < 45) and macd_negative:
        phase = "Bärenmarkt"
        summary = "Kurs und gleitende Durchschnitte zeigen abwärts, Momentum bestätigt die Schwäche."
    elif uptrend and (rsi is None or rsi >= 45) and not macd_negative:
        phase = "Bullenmarkt"
        summary = "Kursstruktur, Trend und Momentum sprechen überwiegend für einen Aufwärtstrend."
    elif downtrend and rebound > 0.06 and (rsi is not None and rsi >= 30) and not macd_negative:
        phase = "Bodenbildungsphase"
        summary = "Der Kurs kommt aus einer schwachen Phase, stabilisiert sich aber über den letzten Tiefs."
    elif range_width <= 0.16:
        phase = "Seitwärtsmarkt"
        summary = "Der Kurs bewegt sich in einer relativ engen Spanne ohne klaren Trend."
    else:
        phase = "Bodenbildungsphase" if macd_positive and rebound > 0.04 else "Seitwärtsmarkt"
        summary = "Die Signale sind gemischt; der Markt sucht noch eine klare Richtung."

    floor_seen = 35
    retest = 30
    new_low = 20
    strong_recovery = 15
    if phase == "Bullenmarkt":
        floor_seen, retest, new_low, strong_recovery = 45, 20, 5, 30
    elif phase == "Korrektur innerhalb eines Aufwärtstrends":
        floor_seen, retest, new_low, strong_recovery = 45, 30, 10, 15
    elif phase == "Bodenbildungsphase":
        floor_seen, retest, new_low, strong_recovery = 45, 25, 15, 15
    elif phase == "Bärenmarkt":
        floor_seen, retest, new_low, strong_recovery = 20, 35, 30, 15
    elif phase == "Seitwärtsmarkt":
        floor_seen, retest, new_low, strong_recovery = 35, 35, 10, 20

    if rsi is not None and rsi < 30:
        floor_seen += 8
        retest -= 3
        new_low -= 5
        strong_recovery += 2
    if macd_positive:
        floor_seen += 8
        retest -= 5
        new_low -= 3
        strong_recovery += 4
    if macd_negative:
        floor_seen -= 8
        retest += 5
        new_low += 3
        strong_recovery -= 2
    if drawdown < -0.2:
        new_low += 6
        floor_seen -= 3
        strong_recovery -= 3

    values = np.array([max(5, floor_seen), max(5, retest), max(5, new_low), max(5, strong_recovery)], dtype=float)
    values = np.round(values / values.sum() * 100).astype(int)
    values[0] += 100 - int(values.sum())
    probabilities = {
        "Boden bereits gesehen": int(values[0]),
        "Erneuter Test / weitere Korrektur": int(values[1]),
        "Neues Tief": int(values[2]),
        "Starke Erholung / Ausbruch": int(values[3]),
    }
    return MarketPhase(phase=phase, summary=summary, probabilities=probabilities)


@st.cache_data(ttl=60 * 60)
def load_ticker_info(symbol: str) -> dict:
    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}


def build_asset_identity(symbol: str, info: dict, candidate: dict | None = None) -> dict:
    candidate = candidate or {}
    known = KNOWN_TICKER_NAMES.get(symbol.upper(), {})
    name = (
        candidate.get("name")
        or info.get("longName")
        or info.get("shortName")
        or known.get("name")
        or symbol.upper()
    )
    exchange = (
        candidate.get("exchange")
        or info.get("exchangeName")
        or info.get("fullExchangeName")
        or info.get("exchange")
        or known.get("exchange")
        or "Daten nicht verfügbar"
    )
    currency = (
        candidate.get("currency")
        or info.get("currency")
        or info.get("financialCurrency")
        or known.get("currency")
        or "EUR"
    )
    return {
        "symbol": symbol.upper(),
        "name": name,
        "exchange": exchange,
        "currency": str(currency).upper(),
    }


@st.cache_data(ttl=60 * 30)
def get_fx_rate_to_eur(currency: str) -> tuple[float | None, str]:
    currency = (currency or "EUR").upper()
    if currency == "EUR":
        return 1.0, "EUR"

    direct_ticker = f"{currency}EUR=X"
    fallback_ticker = f"EUR{currency}=X"
    for ticker, inverse in [(direct_ticker, False), (fallback_ticker, True)]:
        try:
            data = yf.download(ticker, period="5d", interval="1d", auto_adjust=True, progress=False, threads=False)
        except Exception:
            continue
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if data.empty or "Close" not in data:
            continue
        close = data["Close"].dropna()
        if close.empty:
            continue
        rate = float(close.iloc[-1])
        if rate <= 0:
            continue
        return (1 / rate if inverse else rate), ticker

    return None, direct_ticker


def detect_asset_type(symbol: str, info: dict) -> AssetProfile:
    quote_type = str(info.get("quoteType", "")).upper()
    symbol_upper = symbol.upper()
    category = " ".join(
        str(info.get(key, "")) for key in ["category", "fundFamily", "longName", "shortName"]
    ).lower()

    if quote_type in {"CRYPTOCURRENCY", "CURRENCY"} or "-USD" in symbol_upper or "-EUR" in symbol_upper:
        return AssetProfile(
            "Krypto",
            quote_type or "CRYPTO",
            "Krypto erkannt. Klassische Unternehmenskennzahlen werden nicht verwendet.",
            {"Technik": 0.40, "Fundamentaldaten": 0.05, "Makro": 0.25, "News": 0.15, "CRV": 0.15},
        )
    if quote_type == "ETF" or "etf" in category or "fund" in category:
        return AssetProfile(
            "ETF",
            quote_type or "ETF",
            "ETF erkannt. Bewertet werden ETF-Struktur, Diversifikation, Kosten und Performance, soweit Daten verfügbar sind.",
            {"Technik": 0.25, "Fundamentaldaten": 0.25, "Makro": 0.25, "News": 0.10, "CRV": 0.15},
        )
    if quote_type in {"EQUITY", "MUTUALFUND"}:
        return AssetProfile(
            "Aktie" if quote_type == "EQUITY" else "ETF",
            quote_type,
            "Aktie erkannt. Bewertet werden Umsatz, Gewinn, Cashflow, Verschuldung, KGV und Wachstum.",
            {"Technik": 0.30, "Fundamentaldaten": 0.30, "Makro": 0.20, "News": 0.10, "CRV": 0.10},
        )
    return AssetProfile(
        "Derivat / unbekannt",
        quote_type or "Unbekannt",
        "Asset-Typ nicht eindeutig erkannt. Die App bewertet vorsichtiger und erfindet keine fehlenden Daten.",
        {"Technik": 0.45, "Fundamentaldaten": 0.05, "Makro": 0.25, "News": 0.10, "CRV": 0.15},
    )


def data_missing(label: str) -> str:
    return f"{label}: Daten nicht verfügbar."


def score_profitability_metric(value: float) -> float:
    if value >= 0.20:
        return 8.5
    if value >= 0.10:
        return 7.0
    if value >= 0.03:
        return 5.5
    if value >= 0:
        return 4.5
    return 2.5


def score_stock_fundamentals(info: dict) -> ModuleScore:
    quote_type = str(info.get("quoteType", "")).upper()
    details: list[str] = []
    points: list[float] = []

    revenue_growth = value_or_none(info.get("revenueGrowth"))
    if revenue_growth is not None:
        score = clamp(5 + revenue_growth * 20)
        points.append(score)
        details.append(f"Umsatzwachstum: {revenue_growth * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Umsatzwachstum"))

    earnings_growth = value_or_none(info.get("earningsGrowth"))
    if earnings_growth is not None:
        score = clamp(5 + earnings_growth * 18)
        points.append(score)
        details.append(f"Gewinnwachstum: {earnings_growth * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Gewinnwachstum"))

    cash = value_or_none(info.get("totalCash"))
    debt = value_or_none(info.get("totalDebt"))
    if cash is not None and debt is not None:
        cash_debt = cash / debt if debt > 0 else 3.0
        score = clamp(3 + cash_debt * 3)
        points.append(score)
        details.append(f"Cash/Verschuldung: {cash_debt:.2f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Cashbestand oder Verschuldung"))

    free_cashflow = value_or_none(info.get("freeCashflow"))
    if free_cashflow is not None:
        score = 8.0 if free_cashflow > 0 else 3.0
        points.append(score)
        details.append(f"Free Cashflow: {format_currency(free_cashflow)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Free Cashflow"))

    margin_candidates = [
        ("Nettomarge", info.get("profitMargins")),
        ("Operative Marge", info.get("operatingMargins")),
        ("Bruttomarge", info.get("grossMargins")),
    ]
    margin_label = None
    margin_value = None
    for label, raw_value in margin_candidates:
        parsed_value = value_or_none(raw_value)
        if parsed_value is not None:
            margin_label = label
            margin_value = parsed_value
            break
    if margin_value is not None and margin_label is not None:
        score = score_profitability_metric(margin_value)
        points.append(score)
        details.append(f"{margin_label}: {margin_value * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Marge"))

    roe = value_or_none(info.get("returnOnEquity"))
    roa = value_or_none(info.get("returnOnAssets"))
    if roe is not None:
        score = score_profitability_metric(roe)
        points.append(score)
        details.append(f"Eigenkapitalrendite: {roe * 100:.1f}% -> {score:.1f}/10.")
    elif roa is not None:
        score = score_profitability_metric(roa)
        points.append(score)
        details.append(f"Kapitalrendite: {roa * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Eigenkapitalrendite / Kapitalrendite"))

    pe = value_or_none(info.get("trailingPE") or info.get("forwardPE"))
    if pe is not None and pe > 0:
        if pe <= 15:
            score = 8.0
        elif pe <= 30:
            score = 6.5
        elif pe <= 60:
            score = 4.5
        else:
            score = 3.0
        points.append(score)
        details.append(f"KGV: {pe:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("KGV"))

    price_to_sales = value_or_none(info.get("priceToSalesTrailing12Months"))
    if price_to_sales is not None and price_to_sales > 0:
        score = 8.0 if price_to_sales <= 3 else 6.5 if price_to_sales <= 8 else 4.5 if price_to_sales <= 15 else 3.0
        points.append(score)
        details.append(f"Kurs-Umsatz-Verhältnis: {price_to_sales:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Kurs-Umsatz-Verhältnis"))

    market_cap = value_or_none(info.get("marketCap"))
    if market_cap is not None:
        score = 7.5 if market_cap >= 10_000_000_000 else 6.0 if market_cap >= 1_000_000_000 else 4.5
        points.append(score)
        details.append(f"Marktkapitalisierung: {format_currency(market_cap)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Marktkapitalisierung"))

    if not points:
        return ModuleScore(5.0, "Aktien-Fundamentaldaten nicht ausreichend verfügbar. Der Score wird neutral gewertet.", details)

    final_score = round(float(np.mean(points)), 1)
    return ModuleScore(final_score, f"Aktien-Fundamentalscore {final_score}/10 aus {len(points)} verfügbaren Kennzahlen.", details)


def score_etf_fundamentals(info: dict, df: pd.DataFrame | None = None) -> ModuleScore:
    details: list[str] = []
    points: list[float] = []

    category = info.get("category") or info.get("fundFamily") or info.get("longBusinessSummary")
    details.append(f"Index/Region/Sektor: {category}" if category else data_missing("Index/Region/Sektor"))

    ter = value_or_none(info.get("annualReportExpenseRatio") or info.get("expenseRatio"))
    if ter is not None:
        score = 8.5 if ter <= 0.0025 else 7.0 if ter <= 0.006 else 5.0 if ter <= 0.012 else 3.5
        points.append(score)
        details.append(f"TER/Kostenquote: {ter * 100:.2f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("TER/Kostenquote"))

    total_assets = value_or_none(info.get("totalAssets") or info.get("netAssets"))
    if total_assets is not None:
        score = 8.0 if total_assets >= 5_000_000_000 else 6.5 if total_assets >= 500_000_000 else 4.5
        points.append(score)
        details.append(f"Fondsvolumen: {format_currency(total_assets)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Fondsvolumen"))

    holdings = value_or_none(info.get("holdingsCount") or info.get("numberOfHoldings"))
    if holdings is not None:
        score = 8.0 if holdings >= 500 else 6.5 if holdings >= 100 else 4.5
        points.append(score)
        details.append(f"Diversifikation: {holdings:.0f} Positionen -> {score:.1f}/10.")
    else:
        details.append(data_missing("Diversifikation / Anzahl Positionen"))

    for label, key in [("1J-Performance", "52WeekChange"), ("3J-Performance", "threeYearAverageReturn"), ("5J-Performance", "fiveYearAverageReturn")]:
        perf = value_or_none(info.get(key))
        if perf is not None:
            score = clamp(5 + perf * 20)
            points.append(score)
            details.append(f"{label}: {perf * 100:.1f}% -> {score:.1f}/10.")
        else:
            details.append(data_missing(label))

    if df is not None and not df.empty and "Volatility" in df.columns:
        volatility = value_or_none(df.iloc[-1].get("Volatility"))
        if volatility is not None:
            score = 8.0 if volatility <= 0.18 else 6.5 if volatility <= 0.28 else 5.0 if volatility <= 0.45 else 3.5
            points.append(score)
            details.append(f"Langfristige Stabilität: Volatilität {volatility * 100:.1f}% -> {score:.1f}/10.")
        else:
            details.append(data_missing("Langfristige Stabilität / Volatilität"))
    else:
        details.append(data_missing("Langfristige Stabilität / Volatilität"))

    if not points:
        return ModuleScore(5.0, "ETF-Daten nicht ausreichend verfügbar. Der Score wird neutral gewertet.", details)

    final_score = round(float(np.mean(points)), 1)
    return ModuleScore(final_score, f"ETF-Score {final_score}/10 aus verfügbaren Struktur- und Performance-Daten.", details)


def score_crypto_fundamentals(info: dict, technical: ModuleScore, macro: ModuleScore, df: pd.DataFrame) -> ModuleScore:
    latest = df.iloc[-1]
    volatility = value_or_none(latest.get("Volatility"))
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))

    details = [
        "Bitcoin-Zyklus: Daten nicht verfügbar.",
        "ETF-Flows: Daten nicht verfügbar.",
        "On-Chain-Daten: Daten nicht verfügbar.",
    ]
    points = [technical.score, macro.score]
    details.append(f"Trend/Momentum aus Technik: {technical.score:.1f}/10.")
    details.append(f"Makro/Liquidität: {macro.score:.1f}/10.")

    if volatility is not None:
        vol_score = 7.0 if volatility <= 0.45 else 5.0 if volatility <= 0.75 else 3.0
        points.append(vol_score)
        details.append(f"Volatilität: {volatility * 100:.1f}% -> {vol_score:.1f}/10.")
    else:
        details.append(data_missing("Volatilität"))

    if volume is not None and volume_avg is not None and volume_avg > 0:
        liquidity_score = 7.0 if volume >= volume_avg else 5.0
        points.append(liquidity_score)
        details.append(f"Liquidität/Volumen: {volume / volume_avg:.2f}x des 20er-Schnitts -> {liquidity_score:.1f}/10.")
    else:
        details.append(data_missing("Liquidität / Volumenvergleich"))

    final_score = round(float(np.mean(points)), 1)
    return ModuleScore(final_score, f"Krypto-Score {final_score}/10. Externe On-Chain- und ETF-Flow-Daten sind nicht verfügbar.", details)


def score_unknown_fundamentals(profile: AssetProfile) -> ModuleScore:
    return ModuleScore(
        5.0,
        f"{profile.asset_type}: Fundamentale Sonderdaten nicht verfügbar. Neutraler Score, keine Werte erfunden.",
        [
            "Asset-Typ nicht eindeutig genug für Spezialkennzahlen.",
            "Daten nicht verfügbar.",
        ],
    )


def score_asset_fundamentals(symbol: str, profile: AssetProfile, technical: ModuleScore, macro: ModuleScore, df: pd.DataFrame) -> ModuleScore:
    info = load_ticker_info(symbol)
    if profile.asset_type == "Aktie":
        return score_stock_fundamentals(info)
    if profile.asset_type == "ETF":
        return score_etf_fundamentals(info, df)
    if profile.asset_type == "Krypto":
        return score_crypto_fundamentals(info, technical, macro, df)
    return score_unknown_fundamentals(profile)


def override_asset_profile(auto_profile: AssetProfile, selected_type: str) -> AssetProfile:
    if selected_type == "Automatisch":
        return auto_profile
    weights_by_type = {
        "Aktie": {"Technik": 0.30, "Fundamentaldaten": 0.30, "Makro": 0.20, "News": 0.10, "CRV": 0.10},
        "ETF": {"Technik": 0.25, "Fundamentaldaten": 0.25, "Makro": 0.25, "News": 0.10, "CRV": 0.15},
        "Krypto": {"Technik": 0.40, "Fundamentaldaten": 0.05, "Makro": 0.25, "News": 0.15, "CRV": 0.15},
        "Unbekannt": {"Technik": 0.45, "Fundamentaldaten": 0.05, "Makro": 0.25, "News": 0.10, "CRV": 0.15},
    }
    normalized = "Derivat / unbekannt" if selected_type == "Unbekannt" else selected_type
    return AssetProfile(
        normalized,
        f"Manuell: {selected_type}",
        f"Asset-Typ wurde manuell auf {selected_type} gesetzt.",
        weights_by_type[selected_type],
    )


def score_asset_quality(symbol: str, profile: AssetProfile, df: pd.DataFrame) -> ModuleScore:
    info = load_ticker_info(symbol)
    if profile.asset_type == "Aktie":
        result = score_stock_fundamentals(info)
        return ModuleScore(result.score, result.summary.replace("Fundamentalscore", "Asset-Qualität"), result.details)
    if profile.asset_type == "ETF":
        result = score_etf_fundamentals(info, df)
        return ModuleScore(result.score, result.summary.replace("ETF-Score", "ETF-Qualität"), result.details)
    if profile.asset_type == "Krypto":
        latest = df.iloc[-1]
        details: list[str] = []
        points: list[float] = []

        market_cap = value_or_none(info.get("marketCap"))
        if market_cap is not None:
            market_score = 9.0 if market_cap >= 500_000_000_000 else 7.0 if market_cap >= 50_000_000_000 else 5.0
            points.append(market_score)
            details.append(f"Marktstellung: Marktkapitalisierung {format_currency(market_cap)} -> {market_score:.1f}/10.")
        else:
            details.append(data_missing("Marktstellung / Marktkapitalisierung"))

        volume = value_or_none(latest.get("Volume"))
        volume_avg = value_or_none(latest.get("Volume_SMA_20"))
        if volume is not None and volume_avg is not None and volume_avg > 0:
            liquidity_score = 7.5 if volume >= volume_avg else 5.5
            points.append(liquidity_score)
            details.append(f"Liquidität: {volume / volume_avg:.2f}x des 20er-Volumenschnitts -> {liquidity_score:.1f}/10.")
        else:
            details.append(data_missing("Liquidität"))

        volatility = value_or_none(latest.get("Volatility"))
        if volatility is not None:
            vol_score = 7.0 if volatility <= 0.45 else 5.0 if volatility <= 0.75 else 3.0
            points.append(vol_score)
            details.append(f"Volatilität: {volatility * 100:.1f}% -> {vol_score:.1f}/10.")
        else:
            details.append(data_missing("Volatilität"))

        details.extend(
            [
                "Zyklusphase: Daten nicht verfügbar.",
                "Makroabhängigkeit: wird im Kaufsignal/Makro-Kontext betrachtet, nicht als langfristige Qualität erfunden.",
                "Institutionelle Akzeptanz: Daten nicht verfügbar.",
                "ETF-Flows: Daten nicht verfügbar.",
                "On-Chain-Daten: Daten nicht verfügbar.",
            ]
        )
        if not points:
            return ModuleScore(5.0, "Krypto-Asset-Qualität neutral, weil Spezialdaten nicht verfügbar sind.", details)
        score = round(float(np.mean(points)), 1)
        return ModuleScore(score, f"Krypto-Asset-Qualität {score}/10 aus verfügbaren Langfristdaten.", details)
    return score_unknown_fundamentals(profile)


def score_buy_signal(
    score_result: ScoreResult,
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    latest: pd.Series,
    profile: AssetProfile,
) -> ModuleScore:
    rsi = value_or_none(latest.get("RSI_14"))
    volatility = value_or_none(latest.get("Volatility"))
    macd = value_or_none(latest.get("MACD"))
    signal = value_or_none(latest.get("MACD_Signal"))
    score = score_result.score * 0.70 + risk_reward.score * 0.20
    details = list(score_result.reasons)
    details.append(risk_reward.summary)
    details.append("Asset-Qualität und Depot-Effekt fließen nicht in dieses Kaufsignal ein.")

    if market_phase.phase == "Bullenmarkt":
        score += 0.6
        details.append("Marktphase unterstützt den Einstieg.")
    elif market_phase.phase == "Bärenmarkt":
        score -= 0.8
        details.append("Bärenmarkt senkt die Zuverlässigkeit des aktuellen Einstiegszeitpunkts.")
    elif market_phase.phase == "Korrektur innerhalb eines Aufwärtstrends":
        score += 0.2
        details.append("Korrektur im Aufwärtstrend kann antizyklisch interessant sein.")
    elif market_phase.phase == "Bodenbildungsphase":
        score += 0.1
        details.append("Bodenbildungsphase kann interessant sein, braucht aber Bestätigung durch Kursverhalten, MACD oder Volumen.")

    if rsi is not None and rsi < 30:
        score += 0.4
        details.append("RSI ist überverkauft: positiv für antizyklische Käufer, aber nur mit Bestätigung.")
    if rsi is not None and rsi > 70:
        score -= 0.7
        details.append("RSI über 70 warnt vor Überhitzung.")

    if macd is not None and signal is not None:
        if macd > signal:
            score += 0.35
            details.append("MACD liegt über der Signal-Linie: kurzfristiges Momentum bestätigt den Einstieg eher.")
        else:
            score -= 0.35
            details.append("MACD liegt unter der Signal-Linie: Momentum bestätigt den Einstieg noch nicht.")
    else:
        details.append(data_missing("MACD-Timing"))

    volatility_thresholds = {
        "Aktie": (0.45, 0.65),
        "ETF": (0.25, 0.35),
        "Krypto": (0.75, 1.10),
    }
    elevated_volatility, high_volatility = volatility_thresholds.get(profile.asset_type, (0.55, 0.75))
    if volatility is not None:
        if volatility > high_volatility:
            score -= 0.7
            details.append(f"Sehr hohe Volatilität für {profile.asset_type}: Einstieg nur mit kleinerer Tranche und klarer Marke.")
        elif volatility > elevated_volatility:
            score -= 0.25
            details.append(f"Erhöhte Volatilität für {profile.asset_type}: Timing ist brauchbar, aber Positionsgröße vorsichtig wählen.")

    final_score = round(clamp(score), 1)
    return ModuleScore(final_score, f"Kaufsignal {final_score}/10 für {profile.asset_type} aus Marktphase, Trend, RSI, MACD, Volumen, Kurszonen, CRV und asset-typischer Volatilität.", details)


POSITIVE_WORDS = {
    "beat", "beats", "growth", "record", "upgrade", "bullish", "surge", "rally", "profit",
    "strong", "positive", "buy", "outperform", "erholung", "wachstum", "gewinn", "stark",
}
NEGATIVE_WORDS = {
    "miss", "cuts", "cut", "downgrade", "bearish", "fall", "falls", "drop", "risk", "loss",
    "weak", "lawsuit", "probe", "sell", "underperform", "crash", "verlust", "schwach", "risiko",
}


@st.cache_data(ttl=30 * 60)
def load_news_items(symbol: str) -> list[dict]:
    try:
        news = yf.Ticker(symbol).news or []
        return news[:8]
    except Exception:
        return []


def score_news(symbol: str) -> ModuleScore:
    news = load_news_items(symbol)
    if not news:
        return ModuleScore(5.0, "News-Daten nicht verfügbar oder keine aktuellen Nachrichten über Yahoo Finance gefunden. News wird neutral behandelt.", ["Keine News verfügbar."])

    sentiment_values: list[int] = []
    details: list[str] = []
    for item in news[:5]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        lower = title.lower()
        pos = sum(1 for word in POSITIVE_WORDS if word in lower)
        neg = sum(1 for word in NEGATIVE_WORDS if word in lower)
        sentiment_values.append(pos - neg)
        if pos > neg:
            tone = "positiv"
        elif neg > pos:
            tone = "negativ"
        else:
            tone = "neutral"
        details.append(f"{tone}: {title}")

    if not sentiment_values:
        return ModuleScore(5.0, "Nachrichten vorhanden, aber ohne klares Sentiment.", ["Sentiment neutral."])

    avg_sentiment = float(np.mean(sentiment_values))
    score = round(clamp(5 + avg_sentiment * 1.5), 1)
    if score >= 6.5:
        summary = "News-Sentiment ist überwiegend positiv."
    elif score <= 4.0:
        summary = "News-Sentiment ist überwiegend negativ."
    else:
        summary = "News-Sentiment ist überwiegend neutral."
    return ModuleScore(score, summary, details[:5])


@st.cache_data(ttl=30 * 60)
def load_macro_prices() -> dict[str, pd.DataFrame]:
    tickers = {
        "Nasdaq": "^IXIC",
        "US-Zinsen 10J": "^TNX",
        "Dollar-Index": "DX-Y.NYB",
        "Inflationserwartung Proxy": "TIP",
    }
    result: dict[str, pd.DataFrame] = {}
    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if not data.empty and "Close" in data:
                result[name] = data.dropna(subset=["Close"])
        except Exception:
            continue
    return result


@st.cache_data(ttl=30 * 60)
def load_commodity_prices() -> dict[str, pd.DataFrame]:
    tickers = {
        "Öl": "CL=F",
        "Gas": "NG=F",
        "Kupfer": "HG=F",
        "Gold": "GC=F",
        "Uran-Proxy": "URA",
    }
    result: dict[str, pd.DataFrame] = {}
    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if not data.empty and "Close" in data:
                result[name] = data.dropna(subset=["Close"])
        except Exception:
            continue
    return result


def trend_change(data: pd.DataFrame, days: int = 60) -> float | None:
    if data.empty or "Close" not in data or len(data) < 5:
        return None
    close = data["Close"].dropna()
    if close.empty:
        return None
    start = float(close.iloc[max(0, len(close) - days)])
    end = float(close.iloc[-1])
    if start == 0:
        return None
    return (end - start) / start


def score_macro() -> ModuleScore:
    data = load_macro_prices()
    details: list[str] = []
    score = 5.0

    nasdaq_change = trend_change(data.get("Nasdaq", pd.DataFrame()))
    if nasdaq_change is not None:
        adjustment = 1.5 if nasdaq_change > 0.08 else 0.7 if nasdaq_change > 0 else -1.0
        score += adjustment
        details.append(f"Nasdaq-Trend 3M: {nasdaq_change * 100:+.1f}% ({adjustment:+.1f}).")

    rates_change = trend_change(data.get("US-Zinsen 10J", pd.DataFrame()))
    if rates_change is not None:
        adjustment = -1.0 if rates_change > 0.08 else 0.6 if rates_change < -0.08 else 0.0
        score += adjustment
        details.append(f"US-Zinsen 10J 3M: {rates_change * 100:+.1f}% ({adjustment:+.1f}).")

    dollar_change = trend_change(data.get("Dollar-Index", pd.DataFrame()))
    if dollar_change is not None:
        adjustment = -0.7 if dollar_change > 0.04 else 0.4 if dollar_change < -0.04 else 0.0
        score += adjustment
        details.append(f"Dollar-Index 3M: {dollar_change * 100:+.1f}% ({adjustment:+.1f}).")

    inflation_proxy = trend_change(data.get("Inflationserwartung Proxy", pd.DataFrame()))
    if inflation_proxy is not None:
        adjustment = 0.4 if inflation_proxy > 0 else -0.4
        score += adjustment
        details.append(f"Inflations-/Realzins-Proxy TIP 3M: {inflation_proxy * 100:+.1f}% ({adjustment:+.1f}).")

    final_score = round(clamp(score), 1)
    if not details:
        return ModuleScore(5.0, "Makrodaten konnten nicht geladen werden. Makro wird neutral bewertet.", ["Keine Makrodaten verfügbar."])

    if final_score >= 6.5:
        summary = "Makroumfeld ist eher unterstützend."
    elif final_score <= 4.0:
        summary = "Makroumfeld ist belastend."
    else:
        summary = "Makroumfeld ist gemischt."
    return ModuleScore(final_score, summary, details)


def research_market_regime(df: pd.DataFrame, market_phase: MarketPhase, macro: ModuleScore) -> ResearchModule:
    macro_data = load_macro_prices()
    nasdaq_change = trend_change(macro_data.get("Nasdaq", pd.DataFrame()))
    rates_change = trend_change(macro_data.get("US-Zinsen 10J", pd.DataFrame()))
    dollar_change = trend_change(macro_data.get("Dollar-Index", pd.DataFrame()))
    inflation_proxy = trend_change(macro_data.get("Inflationserwartung Proxy", pd.DataFrame()))
    latest = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    close = value_or_none(latest.get("Close"))
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    volatility = value_or_none(latest.get("Volatility"))

    hints: list[str] = []
    counterpoints: list[str] = []
    uncertainties: list[str] = []
    regimes: list[str] = []
    confidence_points = 0

    if nasdaq_change is not None:
        confidence_points += 1
        hints.append(f"Nasdaq 3M: {nasdaq_change * 100:+.1f}%.")
        if nasdaq_change > 0.06:
            regimes.append("Risk-On / Wachstumsphase")
        elif nasdaq_change < -0.06:
            regimes.append("Risk-Off / Defensivphase")
    else:
        uncertainties.append(data_missing("Nasdaq-Trend"))

    if rates_change is not None:
        confidence_points += 1
        hints.append(f"US-Zinsen 10J 3M: {rates_change * 100:+.1f}%.")
        if rates_change > 0.08:
            regimes.append("Liquiditätsentzug")
            counterpoints.append("Steigende Zinsen können Wachstumsaktien und Krypto belasten.")
        elif rates_change < -0.08:
            regimes.append("Liquiditätsentlastung")
    else:
        uncertainties.append(data_missing("US-Zinsen"))

    if dollar_change is not None:
        confidence_points += 1
        hints.append(f"Dollar-Index 3M: {dollar_change * 100:+.1f}%.")
        if dollar_change > 0.04:
            regimes.append("Dollar-Stärke / globale Straffung")
        elif dollar_change < -0.04:
            regimes.append("Dollar-Schwäche / Rückenwind für Risikoassets")
    else:
        uncertainties.append(data_missing("Dollar-Index"))

    if inflation_proxy is not None:
        confidence_points += 1
        hints.append(f"TIP-Proxy 3M: {inflation_proxy * 100:+.1f}%.")
    else:
        uncertainties.append(data_missing("Inflations-/Realzins-Proxy"))

    if close is not None and sma_50 is not None and sma_200 is not None:
        confidence_points += 1
        if close > sma_50 > sma_200:
            regimes.append("asset-spezifischer Aufwärtstrend")
            hints.append("Asset notiert über 50er- und 200er-Durchschnitt.")
        elif close < sma_50 < sma_200:
            regimes.append("asset-spezifischer Abwärtstrend")
            counterpoints.append("Asset notiert unter wichtigen Durchschnittslinien.")
    else:
        uncertainties.append(data_missing("50er/200er-Trendstruktur"))

    if volatility is not None:
        confidence_points += 1
        hints.append(f"Asset-Volatilität: {volatility * 100:.1f}%.")
        if volatility > 0.75:
            regimes.append("Spekulationsphase / hohe Unsicherheit")
            counterpoints.append("Hohe Schwankung kann Signale schnell entwerten.")
    else:
        uncertainties.append(data_missing("Volatilität"))

    if not regimes:
        regimes.append("Gemischtes Marktregime")
    unique_regimes = list(dict.fromkeys(regimes))
    confidence = round(clamp(3.5 + confidence_points * 1.0), 1)
    summary = f"Marktregime: {', '.join(unique_regimes[:3])}. Vertrauensgrad {confidence}/10."
    details = [
        "Erkannte Hinweise: " + ("; ".join(hints) if hints else "Daten nicht verfügbar."),
        "Gegenargumente: " + ("; ".join(counterpoints) if counterpoints else "Keine klaren Gegenargumente aus den verfügbaren Proxies."),
        "Unsicherheiten: " + ("; ".join(uncertainties) if uncertainties else "Keine wesentlichen Datenlücken in den genutzten Proxies."),
        f"Betroffene Asset-Klassen: Aktien, ETFs und Krypto; genaue Wirkung hängt vom Asset-Typ und der Marktphase `{market_phase.phase}` ab.",
        f"Praktische Bedeutung: {macro.summary} Marktregime ist ein Kontextsignal, kein automatisches Kaufsignal.",
    ]
    beginner = "Das Marktregime beschreibt das große Umfeld. Risk-On hilft Risikoassets eher, Risk-Off und Liquiditätsentzug machen Einstiege unsicherer. Es ist nur ein Kontextsignal."
    return ResearchModule("Marktregime", confidence, summary, details, beginner)


def research_macro_impact(profile: AssetProfile, macro: ModuleScore) -> ResearchModule:
    macro_data = load_macro_prices()
    nasdaq_change = trend_change(macro_data.get("Nasdaq", pd.DataFrame()))
    rates_change = trend_change(macro_data.get("US-Zinsen 10J", pd.DataFrame()))
    dollar_change = trend_change(macro_data.get("Dollar-Index", pd.DataFrame()))
    inflation_proxy = trend_change(macro_data.get("Inflationserwartung Proxy", pd.DataFrame()))

    details: list[str] = []
    if rates_change is None:
        details.append(data_missing("Zinswirkung"))
    elif rates_change > 0.08:
        details.append("Zinsen: steigend -> tendenziell Gegenwind für Wachstumsaktien, lange Duration, Krypto und hoch bewertete Assets.")
    elif rates_change < -0.08:
        details.append("Zinsen: fallend -> tendenziell Rückenwind für Wachstumsaktien, ETFs mit Growth-Anteil und Krypto.")
    else:
        details.append("Zinsen: weitgehend stabil -> kein starkes Makro-Signal aus den verfügbaren Zinsdaten.")

    if dollar_change is None:
        details.append(data_missing("Dollar-Wirkung"))
    elif dollar_change > 0.04:
        details.append("Dollar: stärker -> oft Gegenwind für globale Risikoassets, Rohstoffe und Krypto.")
    elif dollar_change < -0.04:
        details.append("Dollar: schwächer -> oft Rückenwind für Rohstoffe, internationale Assets und Risikoappetit.")
    else:
        details.append("Dollar: stabil -> kein klares Belastungs- oder Rückenwind-Signal.")

    if nasdaq_change is None:
        details.append(data_missing("Risikoappetit / Nasdaq"))
    elif nasdaq_change > 0.06:
        details.append("Risikoappetit: Nasdaq steigt -> Risk-On-Hinweis, positiv für Technologie, Growth und teilweise Krypto.")
    elif nasdaq_change < -0.06:
        details.append("Risikoappetit: Nasdaq fällt -> Risk-Off-Hinweis, vorsichtiger bei zyklischen Aktien und Krypto.")
    else:
        details.append("Risikoappetit: Nasdaq seitwärts -> gemischtes Umfeld.")

    if inflation_proxy is None:
        details.append(data_missing("Inflations-/Realzinswirkung"))
    elif inflation_proxy > 0:
        details.append("Inflations-/Realzins-Proxy: TIP steigt -> kann auf Entspannung beim Realzinsdruck oder Nachfrage nach Inflationsschutz hindeuten.")
    else:
        details.append("Inflations-/Realzins-Proxy: TIP fällt -> kann auf höheren Realzinsdruck hindeuten; das belastet oft Growth und Gold.")

    asset_effects = {
        "Aktie": "Für Aktien zählt besonders: steigende Zinsen belasten Bewertungen, Risk-On hilft Growth und starke Margen puffern Makrodruck besser ab.",
        "ETF": "Für ETFs zählt besonders: breite Diversifikation glättet Einzeleffekte, aber Region, Sektor und Growth-/Value-Anteil bestimmen die Makro-Sensitivität.",
        "Krypto": "Für Krypto zählt besonders: Liquidität, Dollar und Realzinsen wirken oft stärker als klassische Unternehmensdaten.",
        "Derivat / unbekannt": "Für unbekannte oder derivative Assets ist die Makro-Wirkung schwerer belastbar; Positionsgröße und Risikobegrenzung sind wichtiger.",
    }
    details.append("Asset-Typ-Wirkung: " + asset_effects.get(profile.asset_type, asset_effects["Derivat / unbekannt"]))
    details.append("Rohstoffe: Öl und Gas reagieren stark auf Angebot, Nachfrage und Geopolitik; Gold eher auf Realzinsen und Sicherheitsnachfrage; Kupfer eher auf Wachstum; Uran eher auf strukturelle Energie- und Angebotsfaktoren.")
    details.append("Unsicherheit: Diese Aussagen sind Wahrscheinlichkeitszusammenhänge, keine sicheren Kausalitäten.")

    summary = f"Makro-Wirkung {macro.score}/10 für {profile.asset_type}. {macro.summary}"
    beginner = "Das Makro-Wirkungsmodul erklärt, warum Zinsen, Dollar, Inflation und Risikoappetit ein Asset unterstützen oder belasten können. Es ist Kontext, kein Kaufbefehl."
    return ResearchModule("Makro-Wirkung", macro.score, summary, details, beginner)


def research_commodity_context(profile: AssetProfile) -> ResearchModule:
    commodity_data = load_commodity_prices()
    details: list[str] = []
    available = 0
    interpretations = {
        "Öl": "Öl reagiert stark auf Konjunktur, Angebot, OPEC-Politik und Geopolitik.",
        "Gas": "Gas reagiert stark auf Wetter, Lagerbestände, regionale Versorgung und Geopolitik.",
        "Kupfer": "Kupfer gilt oft als Wachstums- und Industrieindikator.",
        "Gold": "Gold reagiert häufig auf Realzinsen, Dollar und Sicherheitsnachfrage.",
        "Uran-Proxy": "Uran/URA ist ein struktureller Energie- und Angebotsmarkt; ETF-Proxies bilden den Spotmarkt nur indirekt ab.",
    }

    for name, explanation in interpretations.items():
        change = trend_change(commodity_data.get(name, pd.DataFrame()))
        if change is None:
            details.append(f"{name}: Daten nicht verfügbar. {explanation}")
            continue
        available += 1
        direction = "steigt" if change > 0.03 else "fällt" if change < -0.03 else "seitwärts"
        details.append(f"{name}: {direction} über ca. 3 Monate ({change * 100:+.1f}%). {explanation}")

    asset_context = {
        "Aktie": "Für Aktien sind Rohstoffe besonders relevant, wenn Kosten, Energiepreise oder Zyklik das Geschäftsmodell beeinflussen.",
        "ETF": "Für ETFs hängt die Wirkung von Region und Sektor ab; breite Welt-ETFs reagieren meist indirekter als Energie-, Rohstoff- oder Industrie-ETFs.",
        "Krypto": "Für Krypto wirken Rohstoffe meist indirekt über Inflation, Realzinsen, Dollar und Liquidität.",
        "Derivat / unbekannt": "Bei unbekannten Assets ist die Rohstoffwirkung schwerer zuzuordnen.",
    }
    details.append("Asset-Typ-Kontext: " + asset_context.get(profile.asset_type, asset_context["Derivat / unbekannt"]))
    details.append("Unsicherheit: Rohstoffpreise sind nur Kontextsignale und keine sicheren Prognosen für das analysierte Asset.")

    if available == 0:
        return ResearchModule("Rohstoff-Kontext", None, "Rohstoffdaten nicht verfügbar.", details, "Rohstoffe zeigen Konjunktur-, Inflations- und Sicherheitsstress. Ohne Daten wird nichts geschätzt.")

    confidence = round(clamp(3.0 + available * 1.3), 1)
    summary = f"Rohstoff-Kontext: {available}/5 Proxies verfügbar. Vertrauensgrad {confidence}/10."
    beginner = "Rohstoffe helfen, das Umfeld zu verstehen: Öl und Gas für Energie/Geopolitik, Kupfer für Wachstum, Gold für Realzinsen/Sicherheit, Uran für strukturelle Energie."
    return ResearchModule("Rohstoff-Kontext", confidence, summary, details, beginner)


def research_crypto_cycle(symbol: str, profile: AssetProfile, df: pd.DataFrame) -> ResearchModule:
    if profile.asset_type != "Krypto":
        return ResearchModule("Krypto-Zyklus", None, "Nicht relevant für diesen Asset-Typ.", ["Asset ist nicht als Krypto erkannt."], "Dieses Modul gilt nur für Kryptowährungen.")

    latest = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    volatility = value_or_none(latest.get("Volatility"))
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    today = pd.Timestamp.today().normalize()
    last_halving = pd.Timestamp("2024-04-20")
    next_halving_estimate = pd.Timestamp("2028-04-20")
    days_since_halving = int((today - last_halving).days)
    days_to_next_halving = int((next_halving_estimate - today).days)

    if days_since_halving < 180:
        phase = "frühe Nach-Halving-Phase"
        cycle_score = 6.5
    elif days_since_halving < 550:
        phase = "mittlere Zyklusphase"
        cycle_score = 7.0
    elif days_since_halving < 900:
        phase = "späte Zyklusphase mit erhöhtem Rückschlagsrisiko"
        cycle_score = 5.0
    else:
        phase = "späte/Übergangsphase vor dem nächsten Halving"
        cycle_score = 4.5

    details = [
        f"Ticker: {symbol}.",
        f"Letztes Bitcoin-Halving: 20.04.2024; Tage seitdem: {days_since_halving}.",
        f"Nächstes Halving grob geschätzt um 2028; Tage bis zur Schätzung: {days_to_next_halving}.",
        f"Zyklusphase: {phase} -> {cycle_score:.1f}/10.",
        "ETF-Flows: Daten nicht verfügbar.",
        "Fear & Greed: Daten nicht verfügbar.",
        "On-Chain-Daten: Daten nicht verfügbar.",
    ]
    points = [cycle_score]
    if volatility is not None:
        vol_score = 7.0 if volatility <= 0.55 else 5.0 if volatility <= 0.85 else 3.0
        points.append(vol_score)
        details.append(f"Krypto-Volatilität: {volatility * 100:.1f}% -> {vol_score:.1f}/10.")
    else:
        details.append(data_missing("Krypto-Volatilität"))

    if volume is not None and volume_avg is not None and volume_avg > 0:
        liquidity_score = 7.0 if volume >= volume_avg else 5.0
        points.append(liquidity_score)
        details.append(f"Krypto-Liquidität: {volume / volume_avg:.2f}x des 20er-Volumenschnitts -> {liquidity_score:.1f}/10.")
    else:
        details.append(data_missing("Krypto-Liquidität / Volumenvergleich"))

    score = round(float(np.mean(points)), 1)
    summary = f"Krypto-Zyklus {score}/10. {phase}."
    beginner = "Krypto-Zyklen können nach Bitcoin-Halvings Muster zeigen, sind aber keine Garantie. Fehlende ETF-Flow-, Fear-&-Greed- und On-Chain-Daten werden nicht geschätzt."
    return ResearchModule("Krypto-Zyklus", score, summary, details, beginner)


def research_bubble_risk(info: dict, df: pd.DataFrame, valuation: ResearchModule, momentum: ResearchModule, news: ModuleScore) -> ResearchModule:
    latest = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    points: list[float] = []
    details: list[str] = []

    pe = value_or_none(info.get("trailingPE") or info.get("forwardPE"))
    price_to_sales = value_or_none(info.get("priceToSalesTrailing12Months"))
    if pe is not None and pe > 0:
        risk = 2.0 if pe <= 20 else 4.5 if pe <= 40 else 7.0 if pe <= 80 else 9.0
        points.append(risk)
        details.append(f"Bewertung/KGV: {pe:.1f} -> Blasenrisiko {risk:.1f}/10.")
    elif price_to_sales is not None and price_to_sales > 0:
        risk = 2.5 if price_to_sales <= 4 else 5.0 if price_to_sales <= 10 else 7.5 if price_to_sales <= 20 else 9.0
        points.append(risk)
        details.append(f"Bewertung/KUV: {price_to_sales:.1f} -> Blasenrisiko {risk:.1f}/10.")
    else:
        details.append(data_missing("Bewertungsdaten für Blasenrisiko"))

    rsi = value_or_none(latest.get("RSI_14"))
    if rsi is not None:
        risk = 8.0 if rsi > 75 else 6.5 if rsi > 70 else 4.0 if rsi >= 45 else 3.0
        points.append(risk)
        details.append(f"Momentum/RSI: {rsi:.1f} -> Blasenrisiko {risk:.1f}/10.")
    else:
        details.append(data_missing("RSI für Blasenrisiko"))

    close = df["Close"].dropna() if not df.empty and "Close" in df else pd.Series(dtype=float)
    if len(close) >= 60 and float(close.iloc[-60]) != 0:
        change_3m = (float(close.iloc[-1]) - float(close.iloc[-60])) / float(close.iloc[-60])
        risk = 8.5 if change_3m > 0.60 else 7.0 if change_3m > 0.35 else 5.0 if change_3m > 0.15 else 3.5
        points.append(risk)
        details.append(f"3M-Kursanstieg: {change_3m * 100:+.1f}% -> Blasenrisiko {risk:.1f}/10.")
    else:
        details.append(data_missing("3M-Kursanstieg"))

    volatility = value_or_none(latest.get("Volatility"))
    if volatility is not None:
        risk = 8.0 if volatility > 0.90 else 6.5 if volatility > 0.60 else 4.5 if volatility > 0.35 else 3.0
        points.append(risk)
        details.append(f"Volatilität: {volatility * 100:.1f}% -> Blasenrisiko {risk:.1f}/10.")
    else:
        details.append(data_missing("Volatilität für Blasenrisiko"))

    if news.score >= 7:
        points.append(6.0)
        details.append("Sentiment/News: sehr positiv -> mögliches Hype-Risiko 6.0/10.")
    elif news.score <= 4:
        points.append(3.0)
        details.append("Sentiment/News: negativ -> kein positives Hype-Signal aus News.")
    else:
        points.append(4.5)
        details.append("Sentiment/News: neutral bis gemischt -> moderates Hype-Risiko.")

    details.append("Medienaufmerksamkeit: Daten nicht verfügbar.")
    details.append("Zuflüsse/Flows: Daten nicht verfügbar.")
    details.append(f"Bewertungsscore als Gegencheck: {valuation.score}/10. Momentum-Score als Gegencheck: {momentum.score}/10.")

    if not points:
        return ResearchModule("Blasenrisiko", None, "Blasenrisiko: Daten nicht verfügbar.", details, "Blasenrisiko zeigt, ob Bewertung, Momentum und Stimmung überhitzt wirken. Fehlende Daten werden nicht geschätzt.")

    score = round(float(np.mean(points)), 1)
    if score >= 7.5:
        summary = f"Blasenrisiko hoch: {score}/10."
    elif score >= 6.0:
        summary = f"Blasenrisiko erhöht: {score}/10."
    elif score >= 4.5:
        summary = f"Blasenrisiko mittel: {score}/10."
    else:
        summary = f"Blasenrisiko niedrig bis moderat: {score}/10."
    beginner = "Blasenrisiko prüft, ob Kurs, Bewertung, Momentum und Stimmung überhitzt wirken. Ein hoher Wert ist ein Warnsignal, kein automatischer Verkauf."
    return ResearchModule("Blasenrisiko", score, summary, details, beginner)


def research_innovation_context(info: dict, profile: AssetProfile, asset_quality: ModuleScore, bubble_risk: ResearchModule, news: ModuleScore) -> ResearchModule:
    details: list[str] = []
    points: list[float] = []
    labels: list[str] = []

    revenue_growth = value_or_none(info.get("revenueGrowth"))
    margin = value_or_none(info.get("profitMargins") or info.get("operatingMargins") or info.get("grossMargins"))
    free_cashflow = value_or_none(info.get("freeCashflow"))
    market_cap = value_or_none(info.get("marketCap"))
    summary_text = str(info.get("longBusinessSummary") or info.get("category") or "").lower()

    if profile.asset_type == "ETF":
        details.append("ETF: Innovationsbezug hängt von Index, Region und Sektor ab; Einzeltitel-Innovationsdaten sind nicht verfügbar.")
        labels.append("indirekter Profiteur möglich")
    elif profile.asset_type == "Krypto":
        details.append("Krypto: Netzwerk-, Entwickler- und On-Chain-Adoptionsdaten sind nicht verfügbar.")
        labels.append("Datenlage eingeschränkt")

    if revenue_growth is not None:
        score = 8.0 if revenue_growth >= 0.25 else 6.5 if revenue_growth >= 0.10 else 4.5 if revenue_growth >= 0 else 2.5
        points.append(score)
        details.append(f"Wachstum: Umsatzwachstum {revenue_growth * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Umsatzwachstum für Innovationsprüfung"))

    if margin is not None:
        score = score_profitability_metric(margin)
        points.append(score)
        details.append(f"Margenqualität: {margin * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Margen für Innovationsprüfung"))

    if free_cashflow is not None:
        score = 7.5 if free_cashflow > 0 else 3.0
        points.append(score)
        details.append(f"Free Cashflow: {format_currency(free_cashflow)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Free Cashflow für Innovationsprüfung"))

    if market_cap is not None:
        score = 7.5 if market_cap >= 10_000_000_000 else 5.5 if market_cap >= 1_000_000_000 else 4.0
        points.append(score)
        details.append(f"Marktstellung: Marktkapitalisierung {format_currency(market_cap)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Marktstellung für Innovationsprüfung"))

    theme_keywords = ["ai", "artificial intelligence", "semiconductor", "cloud", "software", "battery", "electric", "robot", "automation", "platform", "data center"]
    if summary_text and any(keyword in summary_text for keyword in theme_keywords):
        points.append(6.5)
        labels.append("Innovations-/Technologiebezug aus Beschreibung")
        details.append("Beschreibung: Innovations- oder Technologiethema erkannt -> 6.5/10.")
    elif summary_text:
        details.append("Beschreibung: kein klarer Innovationsbezug aus verfügbaren Textdaten erkannt.")
    else:
        details.append(data_missing("Beschreibung / Innovationsbelege"))

    if bubble_risk.score is not None and bubble_risk.score >= 7 and asset_quality.score < 6:
        labels.append("Hype-Risiko")
        details.append("Hype-Prüfung: hohes Blasenrisiko bei schwächerer Asset-Qualität.")
    elif asset_quality.score >= 7 and points:
        labels.append("Innovationsführer möglich")
    elif points:
        labels.append("indirekter Profiteur oder gemischte Innovationslage")

    details.append("Produktvorsprung, Patente, Entwickleraktivität und Marktanteilsdaten: Daten nicht verfügbar.")
    details.append(f"News-Sentiment als Kontext: {news.score}/10. {news.summary}")

    if not points:
        return ResearchModule("Innovation / Hype", None, "Innovationsdaten nicht verfügbar.", details, "Dieses Modul trennt echte Hinweise auf Innovationsqualität von reiner Story. Ohne Daten wird nichts geschätzt.")

    score = round(float(np.mean(points)), 1)
    unique_labels = list(dict.fromkeys(labels)) or ["gemischte Innovationslage"]
    summary = f"Innovation / Hype: {score}/10. Einordnung: {', '.join(unique_labels[:3])}."
    beginner = "Dieses Modul fragt: Gibt es echte Hinweise auf Qualität und Wachstum, oder wirkt die Story stärker als die Daten? Hoher Score ist nur sinnvoll, wenn echte Daten dahinterstehen."
    return ResearchModule("Innovation / Hype", score, summary, details, beginner)


def build_data_source_warnings(
    ticker_info: dict,
    original_currency: str,
    fx_rate: float | None,
    fx_ticker: str,
    news: ModuleScore,
    macro: ModuleScore,
) -> list[str]:
    warnings: list[str] = []
    if not ticker_info:
        warnings.append("Yahoo-Finance-Stammdaten sind nicht verfügbar; Asset-Name, Börse, Fundamentaldaten und institutionelle Daten können eingeschränkt sein.")
    if original_currency != "EUR" and fx_rate is None:
        warnings.append(f"EUR-Umrechnung für {original_currency} ist nicht verfügbar ({fx_ticker}); Anzeige erfolgt teilweise in Originalwährung.")
    if any("Keine News verfügbar" in detail or "Keine aktuellen Nachrichten" in detail for detail in [news.summary, *news.details]):
        warnings.append("Yahoo-Finance-News sind nicht verfügbar oder leer; News-Score wird neutral behandelt.")
    if any("Keine Makrodaten verfügbar" in detail or "Makrodaten konnten nicht geladen" in detail for detail in [macro.summary, *macro.details]):
        warnings.append("Makro-Proxies konnten nicht geladen werden; Makro-Score wird neutral behandelt.")
    return warnings


def data_quality_status(data_quality: ResearchModule, external_warnings: list[str]) -> tuple[str, str, list[str]]:
    score = data_quality.score if data_quality.score is not None else 0.0
    if score >= 8 and not external_warnings:
        label = "Grün"
        summary = "Datenqualität gut. Die Analyse ist aus Datensicht solide nutzbar."
    elif score >= 6:
        label = "Gelb"
        summary = "Datenqualität eingeschränkt. Die Analyse ist nutzbar, aber einzelne Datenlücken sollten beachtet werden."
    else:
        label = "Rot"
        summary = "Datenqualität schwach. Die Analyse ist nur vorsichtig nutzbar."

    issues = [detail for detail in data_quality.details if "nicht" in detail.lower() or "fehlt" in detail.lower() or "weniger" in detail.lower()]
    highlights = [*issues[:2], *external_warnings[:2]]
    if not highlights:
        highlights = ["Keine wesentlichen Datenlücken erkannt."]
    return label, summary, highlights[:3]


def score_weight_rows(profile: AssetProfile) -> list[dict[str, str]]:
    descriptions = {
        "Technik": "Trend, Momentum, RSI, MACD, Volumen, Unterstützungen und Widerstände.",
        "Fundamentaldaten": "Langfristige Qualität des Assets; bei Krypto Netzwerk-/Adoptionsnähe statt klassischer Unternehmensdaten.",
        "Makro": "Zinsen, Nasdaq, Dollar und weitere Makro-Proxies.",
        "News": "Aktuelle Yahoo-Finance-News und einfaches Sentiment.",
        "CRV": "Chance-Risiko-Verhältnis aus nächster Unterstützung und nächstem Widerstand.",
    }
    return [
        {
            "Baustein": name,
            "Gewichtung": f"{weight * 100:.0f}%",
            "Bedeutung": descriptions.get(name, "Bewertungsbaustein."),
        }
        for name, weight in profile.weights.items()
    ]


def weighted_total_score(
    technical: ModuleScore,
    fundamentals: ModuleScore,
    macro: ModuleScore,
    news: ModuleScore,
    risk_reward: RiskReward,
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    parts = {
        "Technik": technical.score,
        "Fundamentaldaten": fundamentals.score,
        "Makro": macro.score,
        "News": news.score,
        "CRV": risk_reward.score,
    }
    weights = weights or {"Technik": 0.30, "Fundamentaldaten": 0.30, "Makro": 0.20, "News": 0.10, "CRV": 0.10}
    total = sum(parts[name] * weights.get(name, 0.0) for name in parts)
    return round(float(total), 1), parts


def score_from_optional(values: list[float], neutral_if_empty: float = 5.0) -> float:
    if not values:
        return neutral_if_empty
    return round(float(np.mean(values)), 1)


def data_quality_check(
    symbol: str,
    asset_profile: AssetProfile,
    asset_identity: dict,
    df: pd.DataFrame,
) -> ResearchModule:
    issues: list[str] = []
    positives: list[str] = []

    if symbol:
        positives.append("Ticker gefunden.")
    else:
        issues.append("Ticker nicht gefunden.")
    if asset_profile.asset_type and asset_profile.asset_type != "Derivat / unbekannt":
        positives.append(f"Asset-Typ erkannt: {asset_profile.asset_type}.")
    else:
        issues.append("Asset-Typ unsicher oder unbekannt.")
    if asset_identity.get("exchange") and asset_identity.get("exchange") != "Daten nicht verfügbar":
        positives.append(f"Börse erkannt: {asset_identity.get('exchange')}.")
    else:
        issues.append("Börse nicht erkannt.")
    if asset_identity.get("currency"):
        positives.append(f"Währung erkannt: {asset_identity.get('currency')}.")
    else:
        issues.append("Währung nicht erkannt.")
    if df.empty or "Close" not in df:
        issues.append("Kursdaten fehlen.")
    else:
        positives.append(f"Kursdaten vorhanden: {len(df)} Zeilen.")
    if "Volume" in df and df["Volume"].dropna().sum() > 0:
        positives.append("Volumen verfügbar.")
    else:
        issues.append("Volumen nicht verfügbar.")
    if len(df.dropna(subset=["Close"])) >= 200:
        positives.append("Mindestens 200 Handelstage vorhanden.")
    else:
        issues.append("Weniger als 200 Handelstage vorhanden.")
    latest = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    if value_or_none(latest.get("SMA_50")) is not None:
        positives.append("50er-Durchschnitt berechenbar.")
    else:
        issues.append("50er-Durchschnitt nicht berechenbar.")
    if value_or_none(latest.get("SMA_200")) is not None:
        positives.append("200er-Durchschnitt berechenbar.")
    else:
        issues.append("200er-Durchschnitt nicht berechenbar.")

    score = round(clamp(10 - len(issues) * 1.2), 1)
    summary = "Datenqualität gut." if not issues else "Datenqualität eingeschränkt: " + "; ".join(issues)
    beginner = "Je mehr Daten fehlen, desto vorsichtiger solltest du die Analyse lesen. Fehlende Daten werden nicht erfunden."
    return ResearchModule("Datenqualität", score, summary, positives + issues, beginner)


def research_chart_score(df: pd.DataFrame, supports: list[float], resistances: list[float], market_phase: MarketPhase) -> ResearchModule:
    latest = df.iloc[-1]
    close = float(latest["Close"])
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    points: list[float] = []
    details: list[str] = []

    if sma_50 is not None:
        score = 7.0 if close > sma_50 else 3.5
        points.append(score)
        details.append(f"Kurs zum 50er-Durchschnitt: {'darüber' if close > sma_50 else 'darunter'} -> {score:.1f}/10.")
    else:
        details.append(data_missing("50er-Durchschnitt"))
    if sma_200 is not None:
        score = 7.5 if close > sma_200 else 3.0
        points.append(score)
        details.append(f"Kurs zum 200er-Durchschnitt: {'darüber' if close > sma_200 else 'darunter'} -> {score:.1f}/10.")
    else:
        details.append(data_missing("200er-Durchschnitt"))
    if supports:
        distance = (close - supports[0]) / close
        score = 8.0 if 0 <= distance <= 0.04 else 6.0 if distance <= 0.10 else 4.0
        points.append(score)
        details.append(f"Abstand zur wichtigsten Unterstützung: {distance * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Unterstützungen"))
    if resistances:
        room = (resistances[0] - close) / close
        score = 8.0 if room >= 0.15 else 6.0 if room >= 0.06 else 3.5
        points.append(score)
        details.append(f"Abstand zum wichtigsten Widerstand: {room * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Widerstände"))
    phase_bonus = {"Bullenmarkt": 7.5, "Korrektur innerhalb eines Aufwärtstrends": 6.5, "Bodenbildungsphase": 5.5, "Seitwärtsmarkt": 5.0, "Bärenmarkt": 3.0}.get(market_phase.phase, 5.0)
    points.append(phase_bonus)
    details.append(f"Marktphase: {market_phase.phase} -> {phase_bonus:.1f}/10.")

    score = score_from_optional(points)
    beginner = "Der Charttechnik-Score bewertet Trend, wichtige Durchschnittslinien und Kurszonen. Hoch heißt: Der Chart unterstützt einen Einstieg eher."
    return ResearchModule("Charttechnik-Score", score, f"Charttechnik {score}/10. {market_phase.summary}", details, beginner)


def research_momentum_score(df: pd.DataFrame) -> ResearchModule:
    latest = df.iloc[-1]
    rsi = value_or_none(latest.get("RSI_14"))
    macd = value_or_none(latest.get("MACD"))
    signal = value_or_none(latest.get("MACD_Signal"))
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    points: list[float] = []
    details: list[str] = []

    if rsi is not None:
        if rsi < 30:
            score = 6.5
            text = "überverkauft, antizyklisch interessant"
        elif rsi > 70:
            score = 4.0
            text = "überhitzt"
        elif 45 <= rsi <= 65:
            score = 7.0
            text = "gesund"
        else:
            score = 5.5
            text = "neutral bis gemischt"
        points.append(score)
        details.append(f"RSI {rsi:.1f}: {text} -> {score:.1f}/10.")
    else:
        details.append(data_missing("RSI"))
    if macd is not None and signal is not None:
        score = 7.0 if macd > signal else 3.8
        points.append(score)
        details.append(f"MACD {'über' if macd > signal else 'unter'} Signal-Linie -> {score:.1f}/10.")
    else:
        details.append(data_missing("MACD"))
    if volume is not None and volume_avg is not None and volume_avg > 0:
        ratio = volume / volume_avg
        score = 7.0 if ratio >= 1.2 else 5.5 if ratio >= 0.8 else 4.0
        points.append(score)
        details.append(f"Volumen relativ zum 20er-Schnitt: {ratio:.2f}x -> {score:.1f}/10.")
    else:
        details.append(data_missing("Volumenvergleich"))

    score = score_from_optional(points)
    beginner = "Momentum zeigt, ob Käufer gerade stärker werden. Hoch heißt: Die aktuelle Bewegung wird eher bestätigt."
    return ResearchModule("Momentum-Score", score, f"Momentum {score}/10 aus RSI, MACD und Volumen.", details, beginner)


def research_risk_score(df: pd.DataFrame, risk_reward: RiskReward) -> ResearchModule:
    latest = df.iloc[-1]
    volatility = value_or_none(latest.get("Volatility"))
    points: list[float] = []
    details: list[str] = []
    if volatility is not None:
        vol_score = 8.0 if volatility <= 0.25 else 6.0 if volatility <= 0.45 else 4.0 if volatility <= 0.75 else 2.5
        points.append(vol_score)
        details.append(f"Volatilität {volatility * 100:.1f}% -> {vol_score:.1f}/10.")
    else:
        details.append(data_missing("Volatilität"))
    points.append(risk_reward.score)
    details.append(f"CRV-Score: {risk_reward.score:.1f}/10. {risk_reward.summary}")
    score = score_from_optional(points)
    beginner = "Der Risiko-Score bewertet Schwankungen und Verhältnis von möglichem Gewinn zu Verlust. Hoch heißt: Das Risiko ist besser planbar."
    return ResearchModule("Risiko-Score", score, f"Risiko {score}/10. {risk_reward.summary}", details, beginner)


def research_liquidity_score(df: pd.DataFrame, info: dict, profile: AssetProfile) -> ResearchModule:
    latest = df.iloc[-1]
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    avg_volume = value_or_none(info.get("averageVolume"))
    points: list[float] = []
    details: list[str] = []
    if volume is not None and volume_avg is not None and volume_avg > 0:
        ratio = volume / volume_avg
        score = 8.0 if ratio >= 1.0 else 6.0 if ratio >= 0.5 else 3.5
        points.append(score)
        details.append(f"Aktuelles Volumen zu 20er-Schnitt: {ratio:.2f}x -> {score:.1f}/10.")
    else:
        details.append(data_missing("aktuelles Volumen"))
    if avg_volume is not None:
        score = 8.0 if avg_volume >= 1_000_000 else 6.0 if avg_volume >= 100_000 else 4.0
        points.append(score)
        details.append(f"Durchschnittsvolumen Yahoo: {format_currency(avg_volume)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Yahoo-Durchschnittsvolumen"))
    if profile.asset_type == "Krypto":
        details.append("Orderbuch-/Spread-Daten: Daten nicht verfügbar.")
    score = score_from_optional(points)
    beginner = "Liquidität zeigt, wie gut man typischerweise kaufen oder verkaufen kann. Hoch heißt: Der Markt wirkt handelbarer."
    return ResearchModule("Liquiditäts-Score", score, f"Liquidität {score}/10 aus verfügbaren Volumendaten.", details, beginner)


def research_valuation_score(info: dict, profile: AssetProfile, df: pd.DataFrame, macro: ModuleScore) -> ResearchModule:
    details: list[str] = []
    points: list[float] = []
    if profile.asset_type == "Krypto":
        details.extend(["Zyklusdaten: Daten nicht verfügbar.", "On-Chain-Bewertungsdaten: Daten nicht verfügbar."])
        points.append(macro.score)
        score = score_from_optional(points)
        beginner = "Bei Krypto ersetzt dieser Score klassische Bewertung durch Zyklus-/On-Chain-Kontext. Wenn diese Daten fehlen, bleibt die Aussage eingeschränkt."
        return ResearchModule("Zyklus-/On-Chain-Score", score, f"Zyklus-/On-Chain-Score {score}/10; Spezialdaten nicht verfügbar.", details, beginner)

    trailing_pe = value_or_none(info.get("trailingPE"))
    forward_pe = value_or_none(info.get("forwardPE"))
    price_to_sales = value_or_none(info.get("priceToSalesTrailing12Months"))
    if trailing_pe is not None:
        score = 8.0 if trailing_pe <= 18 else 6.0 if trailing_pe <= 30 else 4.0 if trailing_pe <= 50 else 2.5
        points.append(score)
        details.append(f"KGV: {trailing_pe:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("KGV"))
    if forward_pe is not None:
        score = 8.0 if forward_pe <= 18 else 6.0 if forward_pe <= 30 else 4.0 if forward_pe <= 50 else 2.5
        points.append(score)
        details.append(f"Forward-KGV: {forward_pe:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Forward-KGV"))
    if price_to_sales is not None:
        score = 8.0 if price_to_sales <= 3 else 6.0 if price_to_sales <= 8 else 4.0 if price_to_sales <= 15 else 2.5
        points.append(score)
        details.append(f"Kurs-Umsatz-Verhältnis: {price_to_sales:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Kurs-Umsatz-Verhältnis"))
    if profile.asset_type == "ETF":
        details.append("ETF-Bewertung über Index-KGV/Region: Daten nicht verfügbar.")
    score = score_from_optional(points)
    beginner = "Der Bewertungsscore prüft, ob der Preis im Verhältnis zu Gewinn/Umsatz teuer oder günstig wirkt. Fehlende Kennzahlen werden nicht erfunden."
    return ResearchModule("Bewertungsscore", score, f"Bewertung {score}/10 aus verfügbaren Bewertungskennzahlen.", details, beginner)


def research_fundamental_module(asset_quality: ModuleScore, profile: AssetProfile) -> ResearchModule:
    name = "Krypto-Netzwerk-/Adoptionsscore" if profile.asset_type == "Krypto" else "Fundamentaldaten-Score"
    beginner = (
        "Bei Krypto geht es um Marktstellung, Liquidität und Adoption statt klassische Gewinne."
        if profile.asset_type == "Krypto"
        else "Fundamentaldaten zeigen, ob das Unternehmen oder der ETF langfristig solide wirkt."
    )
    return ResearchModule(name, asset_quality.score, asset_quality.summary, asset_quality.details, beginner)


def module_from_existing(name: str, module: ModuleScore, beginner: str) -> ResearchModule:
    return ResearchModule(name, module.score, module.summary, module.details, beginner)


def format_optional_number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "Daten nicht verfügbar"
    return f"{value:,.2f}{suffix}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_optional_date(value: object) -> str:
    if value is None or value == "":
        return "Daten nicht verfügbar"
    try:
        timestamp = pd.to_datetime(value, unit="s", utc=True)
        if pd.isna(timestamp):
            timestamp = pd.to_datetime(value)
    except Exception:
        try:
            timestamp = pd.to_datetime(value)
        except Exception:
            return str(value)
    if pd.isna(timestamp):
        return "Daten nicht verfügbar"
    return timestamp.strftime("%d.%m.%Y")


def safe_dataframe_from_yfinance(value: object) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    return pd.DataFrame()


def research_analyst_consensus(info: dict, profile: AssetProfile, original_currency: str, fx_rate: float | None, currency_mode: str) -> ResearchModule:
    if profile.asset_type not in {"Aktie", "ETF"}:
        return ResearchModule(
            "Analysten-Konsens",
            None,
            "Daten nicht verfügbar. Analysten-Konsens ist für diesen Asset-Typ über Yahoo Finance nicht belastbar verfügbar.",
            ["Durchschnittliches Kursziel: Daten nicht verfügbar.", "Buy/Hold/Sell-Ratings: Daten nicht verfügbar."],
            "Analysten-Konsens zeigt, ob professionelle Analysten eher positiv, neutral oder negativ sind. Für dieses Asset liegen keine belastbaren Daten vor.",
        )

    target_mean = value_or_none(info.get("targetMeanPrice"))
    target_high = value_or_none(info.get("targetHighPrice"))
    target_low = value_or_none(info.get("targetLowPrice"))
    analyst_count = value_or_none(info.get("numberOfAnalystOpinions"))
    recommendation_mean = value_or_none(info.get("recommendationMean"))
    recommendation_key = str(info.get("recommendationKey", "") or "").replace("_", " ").strip()

    details = [
        f"Durchschnittliches Analystenkursziel: {format_display_money(target_mean, original_currency, fx_rate, currency_mode) if target_mean is not None else 'Daten nicht verfügbar'}.",
        f"Höchstes Kursziel: {format_display_money(target_high, original_currency, fx_rate, currency_mode) if target_high is not None else 'Daten nicht verfügbar'}.",
        f"Niedrigstes Kursziel: {format_display_money(target_low, original_currency, fx_rate, currency_mode) if target_low is not None else 'Daten nicht verfügbar'}.",
        "Anzahl Buy-Ratings: Daten nicht verfügbar.",
        "Anzahl Hold-Ratings: Daten nicht verfügbar.",
        "Anzahl Sell-Ratings: Daten nicht verfügbar.",
    ]
    if analyst_count is not None:
        details.append(f"Anzahl Analystenmeinungen: {analyst_count:.0f}.")
    else:
        details.append("Anzahl Analystenmeinungen: Daten nicht verfügbar.")
    if recommendation_key:
        details.append(f"Yahoo-Empfehlung: {recommendation_key}.")
    else:
        details.append("Yahoo-Empfehlung: Daten nicht verfügbar.")

    points: list[float] = []
    if recommendation_mean is not None:
        score = clamp(10 - (recommendation_mean - 1) * 2.5)
        points.append(score)
        details.append(f"Recommendation-Mean: {recommendation_mean:.2f} -> {score:.1f}/10.")
    if target_mean is not None:
        current_price = value_or_none(info.get("currentPrice")) or value_or_none(info.get("regularMarketPrice")) or value_or_none(info.get("previousClose"))
        if current_price is not None and current_price > 0:
            upside = (target_mean - current_price) / current_price
            upside_score = 8.0 if upside >= 0.25 else 6.5 if upside >= 0.10 else 5.0 if upside >= -0.05 else 3.5
            points.append(upside_score)
            details.append(f"Impliziertes Potenzial zum Durchschnittskursziel: {upside * 100:+.1f}% -> {upside_score:.1f}/10.")

    if not points:
        return ResearchModule(
            "Analysten-Konsens",
            None,
            "Daten nicht verfügbar. Analystenkursziele und Rating-Verteilung konnten nicht belastbar geladen werden.",
            details + ["Werden Kursziele angehoben oder gesenkt: Daten nicht verfügbar."],
            "Ohne Analystendaten lässt sich nicht sagen, ob Analysten das Investment aktuell unterstützen.",
        )

    final_score = score_from_optional(points)
    support_text = "Analysten unterstützen das Investment eher." if final_score >= 6.5 else "Analysten sind neutral bis vorsichtig." if final_score >= 4.5 else "Analystenbild wirkt eher belastend."
    summary = f"Analysten-Score {final_score}/10. {support_text} Kurszieländerungen: Daten nicht verfügbar."
    beginner = "Der Analysten-Score fasst Kursziele und Yahoo-Empfehlung zusammen. Hoch heißt: Analystenbild und Kurszielpotenzial sprechen eher für das Investment."
    return ResearchModule("Analysten-Konsens", final_score, summary, details + ["Werden Kursziele angehoben oder gesenkt: Daten nicht verfügbar."], beginner)


def load_earnings_dates(symbol: str) -> pd.DataFrame:
    try:
        return safe_dataframe_from_yfinance(yf.Ticker(symbol).get_earnings_dates(limit=8))
    except Exception:
        return pd.DataFrame()


def research_earnings_module(symbol: str, info: dict, profile: AssetProfile) -> ResearchModule:
    if profile.asset_type != "Aktie":
        return ResearchModule(
            "Earnings-Modul",
            None,
            "Daten nicht verfügbar. Earnings-Modul ist nur für Aktien sinnvoll.",
            ["Nächster Quartalsbericht: Daten nicht verfügbar.", "Letzter Quartalsbericht: Daten nicht verfügbar."],
            "Earnings sind Quartalszahlen. Für ETFs und viele Kryptos gibt es keine klassischen Unternehmensgewinne.",
        )

    earnings_dates = load_earnings_dates(symbol)
    details: list[str] = []
    next_report = format_optional_date(info.get("earningsTimestamp") or info.get("earningsTimestampStart"))
    details.append(f"Nächster Quartalsbericht: {next_report}.")
    details.append(f"Letzter Quartalsbericht: {format_optional_date(info.get('mostRecentQuarter'))}.")

    points: list[float] = []
    surprise_text = "Daten nicht verfügbar"
    if not earnings_dates.empty:
        normalized = earnings_dates.copy()
        normalized.index = pd.to_datetime(normalized.index, errors="coerce")
        past = normalized[normalized.index <= pd.Timestamp.utcnow().tz_localize(None)] if normalized.index.tz is None else normalized[normalized.index <= pd.Timestamp.utcnow()]
        if not past.empty:
            last = past.sort_index().iloc[-1]
            eps_estimate = value_or_none(last.get("EPS Estimate"))
            reported_eps = value_or_none(last.get("Reported EPS"))
            surprise_pct = value_or_none(last.get("Surprise(%)"))
            details.append(f"Gewinnschätzung letzter Bericht: {format_optional_number(eps_estimate)}.")
            details.append(f"Tatsächlicher Gewinn letzter Bericht: {format_optional_number(reported_eps)}.")
            if surprise_pct is not None:
                surprise_text = f"{surprise_pct:.1f}%"
                score = 8.0 if surprise_pct >= 10 else 6.5 if surprise_pct > 0 else 5.0 if surprise_pct == 0 else 3.5
                points.append(score)
                details.append(f"Earnings-Surprise: {surprise_text} -> {score:.1f}/10.")
            else:
                details.append("Earnings-Surprise: Daten nicht verfügbar.")
        else:
            details.extend(["Gewinnschätzung: Daten nicht verfügbar.", "Tatsächliche Ergebnisse: Daten nicht verfügbar.", "Earnings-Surprise: Daten nicht verfügbar."])
    else:
        details.extend(["Umsatzschätzung: Daten nicht verfügbar.", "Gewinnschätzung: Daten nicht verfügbar.", "Tatsächliche Ergebnisse: Daten nicht verfügbar.", "Earnings-Surprise: Daten nicht verfügbar."])

    revenue_estimate = value_or_none(info.get("revenueEstimate"))
    earnings_estimate = value_or_none(info.get("earningsEstimate"))
    details.append(f"Umsatzschätzung: {format_optional_number(revenue_estimate)}.")
    details.append(f"Gewinnschätzung: {format_optional_number(earnings_estimate)}.")

    if next_report != "Daten nicht verfügbar":
        risk_score = 5.0
        details.append("Earnings-Termin vorhanden: Ereignisrisiko ist erhöht.")
        points.append(risk_score)

    if not points:
        return ResearchModule("Earnings-Modul", None, "Daten nicht verfügbar. Earnings-Schätzungen und tatsächliche Ergebnisse konnten nicht belastbar geladen werden.", details, "Earnings zeigen, ob ein Unternehmen Erwartungen schlägt oder verfehlt. Ohne Daten bleibt das Risiko schwer einschätzbar.")

    final_score = score_from_optional(points)
    tone = "positiv" if final_score >= 6.5 else "neutral" if final_score >= 4.5 else "negativ"
    summary = f"Earnings-Risiko-Score {final_score}/10. Earnings-Surprise: {surprise_text}. Einordnung: {tone}."
    beginner = "Der Earnings-Score bewertet, ob Quartalszahlen Erwartungen übertroffen haben und ob ein naher Bericht zusätzliches Risiko bringt."
    return ResearchModule("Earnings-Modul", final_score, summary, details, beginner)


def research_event_risk_module(info: dict, profile: AssetProfile, macro: ModuleScore) -> ResearchModule:
    details = [
        "Fed-Sitzungen: Daten nicht verfügbar.",
        "EZB-Sitzungen: Daten nicht verfügbar.",
        "CPI/Inflationsdaten: Daten nicht verfügbar.",
        "Arbeitsmarktdaten: Daten nicht verfügbar.",
        "IPOs: Daten nicht verfügbar.",
        "ETF-Entscheidungen: Daten nicht verfügbar.",
        "Wichtige Unternehmensereignisse: Daten nicht verfügbar.",
    ]
    next_event = "Daten nicht verfügbar"
    event_date = "Daten nicht verfügbar"
    impact = "Daten nicht verfügbar"
    points: list[float] = []

    earnings_date = format_optional_date(info.get("earningsTimestamp") or info.get("earningsTimestampStart"))
    if profile.asset_type == "Aktie" and earnings_date != "Daten nicht verfügbar":
        next_event = "Quartalsbericht"
        event_date = earnings_date
        impact = "Kann Volatilität stark erhöhen, besonders wenn Erwartungen verfehlt oder angehoben werden."
        points.append(4.5)
        details.append(f"Earnings-Termin: {earnings_date}.")

    if macro.score <= 4.0:
        points.append(4.0)
        details.append("Makro-Score ist schwach; makroökonomische Events können stärkere Kursreaktionen auslösen.")
    elif macro.score >= 6.5:
        points.append(6.5)
        details.append("Makro-Score ist unterstützend; Event-Risiko wirkt aktuell weniger belastend.")

    if not points:
        return ResearchModule(
            "Event-Risiko-Modul",
            None,
            "Daten nicht verfügbar. Konkrete Makro- und Unternehmensereignisse konnten nicht zuverlässig geladen werden.",
            [f"Nächstes relevantes Event: {next_event}.", f"Datum: {event_date}.", f"Potenzielle Auswirkung: {impact}."] + details,
            "Event-Risiko meint Termine, die Kurse plötzlich bewegen können. Ohne Kalenderdaten bleibt diese Einschätzung eingeschränkt.",
        )

    final_score = score_from_optional(points)
    summary = f"Event-Risiko-Score {final_score}/10. Nächstes relevantes Event: {next_event}. Datum: {event_date}. Potenzielle Auswirkung: {impact}."
    beginner = "Je niedriger der Event-Risiko-Score, desto mehr können Termine wie Earnings, Inflationsdaten oder Zentralbanken die Analyse kurzfristig widerlegen."
    return ResearchModule("Event-Risiko-Modul", final_score, summary, [f"Nächstes relevantes Event: {next_event}.", f"Datum: {event_date}.", f"Potenzielle Auswirkung: {impact}."] + details, beginner)


def research_institutional_data(info: dict, profile: AssetProfile) -> ResearchModule:
    held_institutions = value_or_none(info.get("heldPercentInstitutions"))
    held_insiders = value_or_none(info.get("heldPercentInsiders"))
    shares_short = value_or_none(info.get("sharesShort"))
    short_ratio = value_or_none(info.get("shortRatio"))
    short_percent_float = value_or_none(info.get("shortPercentOfFloat"))
    details = [
        f"Institutionelle Beteiligungen: {held_institutions * 100:.1f}%." if held_institutions is not None else "Institutionelle Beteiligungen: Daten nicht verfügbar.",
        f"Insider-Beteiligungen: {held_insiders * 100:.1f}%." if held_insiders is not None else "Insider-Beteiligungen: Daten nicht verfügbar.",
        f"Short Interest Aktien: {format_optional_number(shares_short)}." if shares_short is not None else "Short Interest: Daten nicht verfügbar.",
        f"Short Ratio: {short_ratio:.2f}." if short_ratio is not None else "Short Ratio: Daten nicht verfügbar.",
        f"Short Interest vom Float: {short_percent_float * 100:.1f}%." if short_percent_float is not None else "Short Interest vom Float: Daten nicht verfügbar.",
        "Insiderkäufe: Daten nicht verfügbar.",
        "Insiderverkäufe: Daten nicht verfügbar.",
        "ETF-Flows: Daten nicht verfügbar.",
    ]

    points: list[float] = []
    if held_institutions is not None:
        score = 7.5 if held_institutions >= 0.45 else 6.0 if held_institutions >= 0.20 else 4.5
        points.append(score)
    if short_percent_float is not None:
        score = 8.0 if short_percent_float <= 0.03 else 6.0 if short_percent_float <= 0.10 else 3.5
        points.append(score)
    elif short_ratio is not None:
        score = 7.0 if short_ratio <= 3 else 5.5 if short_ratio <= 7 else 3.5
        points.append(score)

    if not points:
        return ResearchModule(
            "Institutionelle Daten",
            None,
            "Daten nicht verfügbar. Institutionelle Käufe/Verkäufe, Short Interest oder ETF-Flows konnten nicht belastbar geladen werden.",
            details,
            "Institutionelle Daten zeigen, ob große Marktteilnehmer eher aufbauen oder reduzieren. Ohne Daten bleibt diese Ebene offen.",
        )

    final_score = score_from_optional(points)
    direction = "Institutionelle Daten wirken eher unterstützend." if final_score >= 6.5 else "Institutionelle Daten sind gemischt." if final_score >= 4.5 else "Institutionelle Daten wirken eher belastend."
    summary = f"Institutioneller Score {final_score}/10. {direction} Ob Institutionen aktuell zukaufen oder abbauen: Daten nicht verfügbar."
    beginner = "Der institutionelle Score bewertet verfügbare Hinweise wie institutionelle Beteiligung und Short Interest. Hoch heißt: große Marktteilnehmer wirken weniger belastend."
    return ResearchModule("Institutionelle Daten", final_score, summary, details, beginner)


def market_phase_clarity_score(market_phase: MarketPhase) -> float:
    values = list(market_phase.probabilities.values())
    if not values:
        return 5.0
    top = max(values)
    second = sorted(values, reverse=True)[1] if len(values) > 1 else 0
    spread = top - second
    return 8.0 if spread >= 25 else 6.5 if spread >= 15 else 5.0 if spread >= 8 else 3.5


def signal_stability_score(df: pd.DataFrame) -> float:
    recent = df.dropna(subset=["Close"]).tail(30)
    if len(recent) < 20:
        return 4.0
    close = recent["Close"]
    sma_50 = recent["SMA_50"] if "SMA_50" in recent else pd.Series(dtype=float)
    macd = recent["MACD"] if "MACD" in recent else pd.Series(dtype=float)
    signal = recent["MACD_Signal"] if "MACD_Signal" in recent else pd.Series(dtype=float)
    points: list[float] = []
    if not sma_50.dropna().empty:
        above_share = float((close.loc[sma_50.dropna().index] > sma_50.dropna()).mean())
        points.append(8.0 if above_share >= 0.75 or above_share <= 0.25 else 5.0)
    if not macd.dropna().empty and not signal.dropna().empty:
        common = macd.dropna().index.intersection(signal.dropna().index)
        if len(common) >= 10:
            positive_share = float((macd.loc[common] > signal.loc[common]).mean())
            points.append(8.0 if positive_share >= 0.75 or positive_share <= 0.25 else 5.0)
    returns = close.pct_change().dropna()
    if not returns.empty:
        vol = float(returns.std())
        points.append(7.5 if vol <= 0.025 else 5.5 if vol <= 0.05 else 3.5)
    return score_from_optional(points)


def available_data_source_count(modules: list[ResearchModule], institutional_modules: list[ResearchModule]) -> int:
    count = 0
    for module in modules + institutional_modules:
        joined = " ".join(module.details)
        if module.score is not None and "Daten nicht verfügbar" not in joined:
            count += 1
        elif module.score is not None:
            count += 1
    return count


def research_confidence_score(
    data_quality: ResearchModule,
    liquidity: ResearchModule,
    market_phase: MarketPhase,
    df: pd.DataFrame,
    modules: list[ResearchModule],
    institutional_modules: list[ResearchModule],
) -> ResearchModule:
    data_sources = available_data_source_count(modules, institutional_modules)
    source_score = 8.0 if data_sources >= 8 else 6.5 if data_sources >= 5 else 4.5 if data_sources >= 3 else 3.0
    phase_score = market_phase_clarity_score(market_phase)
    stability_score = signal_stability_score(df)
    liquidity_score = liquidity.score if liquidity.score is not None else 4.0
    data_quality_score = data_quality.score if data_quality.score is not None else 4.0
    final_score = score_from_optional([data_quality_score, liquidity_score, source_score, phase_score, stability_score])
    details = [
        f"Datenqualität: {data_quality_score:.1f}/10.",
        f"Liquidität: {liquidity_score:.1f}/10.",
        f"Verfügbare Datenquellen: {data_sources} -> {source_score:.1f}/10.",
        f"Klarheit der Marktphase: {phase_score:.1f}/10.",
        f"Stabilität der Signale: {stability_score:.1f}/10.",
    ]
    if final_score >= 7:
        summary = f"Vertrauen in Analyse: {final_score}/10. Die Analyse ist aktuell relativ belastbar, weil Datenqualität, Liquidität oder Signalstabilität ausreichend sind."
    elif final_score >= 5:
        summary = f"Vertrauen in Analyse: {final_score}/10. Die Analyse ist brauchbar, aber mehrere Punkte bleiben unsicher."
    else:
        summary = f"Vertrauen in Analyse: {final_score}/10. Die Analyse ist unsicher, weil Datenlage, Liquidität oder Signale nicht stabil genug sind."
    beginner = "Der Vertrauensscore sagt nicht, ob du kaufen sollst. Er sagt, wie belastbar die Analyse selbst gerade ist."
    return ResearchModule("Vertrauen in Analyse", final_score, summary, details, beginner)


def build_uncertainty_factors(
    data_quality: ResearchModule,
    event_risk: ResearchModule,
    earnings: ResearchModule,
    news: ModuleScore,
    macro: ModuleScore,
    latest: pd.Series,
    market_phase: MarketPhase,
    supports: list[float],
) -> list[str]:
    factors: list[str] = []
    volatility = value_or_none(latest.get("Volatility"))
    if event_risk.score is None or event_risk.score <= 5:
        factors.append("Bevorstehende oder nicht zuverlässig geladene Makro-/Unternehmensereignisse können die Analyse widerlegen.")
    if earnings.score is None:
        factors.append("Earnings-Daten sind nicht verfügbar; Quartalszahlen könnten eine andere Richtung erzwingen.")
    elif earnings.score <= 5:
        factors.append("Earnings-Risiko ist erhöht; ein Bericht kann die aktuelle Einschätzung schnell verändern.")
    if data_quality.score is not None and data_quality.score < 8:
        factors.append("Datenqualität ist eingeschränkt; fehlende Daten reduzieren die Belastbarkeit.")
    if volatility is not None and volatility > 0.45:
        factors.append("Hohe Volatilität kann Unterstützungen und Kaufsignale schneller entwerten.")
    if macro.score <= 4.5:
        factors.append("Schwaches Makro-Umfeld kann positive Asset-Signale überlagern.")
    if news.score <= 4.5:
        factors.append("Negativer Nachrichtenfluss kann die technische Analyse kurzfristig widerlegen.")
    if not supports:
        factors.append("Keine klare Unterstützung erkannt; dadurch fehlt eine belastbare Risikomarke.")
    if market_phase_clarity_score(market_phase) < 5:
        factors.append("Marktphase ist nicht klar; Signale können häufiger kippen.")
    factors.append("Geopolitische Risiken sind nicht vollständig modelliert.")
    while len(factors) < 3:
        factors.append("Neue externe Daten können die Einschätzung verändern.")
    return factors[:5]


def scenario_probabilities(
    buy_signal: ModuleScore,
    asset_quality: ModuleScore,
    risk_reward: RiskReward,
    market_phase: MarketPhase,
    close: float,
    supports: list[float],
    resistances: list[float],
    latest: pd.Series,
) -> tuple[int, int, int]:
    bull = 25 + int((buy_signal.score - 5) * 4) + int((asset_quality.score - 5) * 2)
    bear = 25 + int((5 - buy_signal.score) * 4)
    if risk_reward.ratio is not None and risk_reward.ratio >= 2:
        bull += 8
        bear -= 5
    elif risk_reward.ratio is not None and risk_reward.ratio < 1:
        bull -= 4
        bear += 6
    if market_phase.phase == "Bullenmarkt":
        bull += 8
        bear -= 5
    if market_phase.phase == "Bärenmarkt":
        bull -= 8
        bear += 10
    if market_phase.phase == "Bodenbildungsphase":
        bull += 3
        bear += 2

    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    if sma_50 is not None and sma_200 is not None:
        if close > sma_50 > sma_200:
            bull += 8
            bear -= 4
        elif close < sma_50 < sma_200:
            bull -= 8
            bear += 8

    valid_supports = [level for level in supports if level < close]
    valid_resistances = [level for level in resistances if level > close]
    if valid_supports:
        support_distance = (close - valid_supports[0]) / close
        if support_distance <= 0.06:
            bull += 4
            bear -= 2
        elif support_distance > 0.18:
            bear += 4
    else:
        bear += 5

    if valid_resistances:
        resistance_room = (valid_resistances[0] - close) / close
        if resistance_room >= 0.15:
            bull += 5
        elif resistance_room <= 0.04:
            bull -= 4
            bear += 3
    else:
        bull -= 3

    volatility = value_or_none(latest.get("Volatility"))
    if volatility is not None:
        if volatility > 0.75:
            bull -= 3
            bear += 6
        elif volatility < 0.25:
            bear -= 3

    bull = int(np.clip(bull, 10, 65))
    bear = int(np.clip(bear, 10, 65))
    base = 100 - bull - bear
    if base < 20:
        diff = 20 - base
        bull = max(10, bull - diff // 2)
        bear = max(10, bear - (diff - diff // 2))
        base = 100 - bull - bear
    return bull, base, bear


def build_scenarios(
    close: float,
    supports: list[float],
    resistances: list[float],
    buy_signal: ModuleScore,
    asset_quality: ModuleScore,
    risk_reward: RiskReward,
    market_phase: MarketPhase,
    latest: pd.Series,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
) -> list[dict]:
    bull_p, base_p, bear_p = scenario_probabilities(buy_signal, asset_quality, risk_reward, market_phase, close, supports, resistances, latest)
    valid_resistances = [level for level in resistances if level > close]
    valid_supports = [level for level in supports if level < close]
    first_resistance = valid_resistances[0] if valid_resistances else None
    second_resistance = valid_resistances[1] if len(valid_resistances) > 1 else first_resistance
    first_support = valid_supports[0] if valid_supports else None
    second_support = valid_supports[1] if len(valid_supports) > 1 else first_support
    base_target = first_resistance if buy_signal.score >= 6.5 else close if buy_signal.score >= 5 else first_support
    bull_target = format_display_money(second_resistance, original_currency, fx_rate, currency_mode) if second_resistance else "Daten nicht verfügbar"
    base_target_text = format_display_money(base_target, original_currency, fx_rate, currency_mode) if base_target else "Daten nicht verfügbar"
    bear_target = format_display_money(second_support, original_currency, fx_rate, currency_mode) if second_support else "Daten nicht verfügbar"
    volatility = value_or_none(latest.get("Volatility"))
    volatility_text = f"Volatilität {volatility * 100:.1f}%" if volatility is not None else "Volatilität: Daten nicht verfügbar"
    return [
        {
            "Szenario": "Bull-Case",
            "Was müsste passieren?": "Trend bestätigt sich, MACD bleibt positiv, Volumen zieht an und der nächste Widerstand wird überwunden.",
            "Kursziel": bull_target,
            "Wahrscheinlichkeit": f"{bull_p}%",
            "Wichtigste Treiber": f"{market_phase.phase}, CRV {risk_reward.score:.1f}/10, {volatility_text}.",
        },
        {
            "Szenario": "Base-Case",
            "Was müsste passieren?": "Der Kurs bleibt in der aktuellen Struktur und reagiert an Unterstützung und Widerstand wie bisher.",
            "Kursziel": base_target_text,
            "Wahrscheinlichkeit": f"{base_p}%",
            "Wichtigste Treiber": "Wahrscheinlichstes Szenario bei gemischten Signalen und intakter Kursstruktur.",
        },
        {
            "Szenario": "Bear-Case",
            "Was müsste passieren?": "Unterstützung bricht, Momentum bleibt schwach oder das Makro-/News-Umfeld verschlechtert sich.",
            "Kursziel": bear_target,
            "Wahrscheinlichkeit": f"{bear_p}%",
            "Wichtigste Treiber": "Risiko steigt besonders bei Bruch der nächsten Unterstützung oder hoher Volatilität.",
        },
    ]


def build_buy_zones(
    close: float,
    supports: list[float],
    resistances: list[float],
    latest: pd.Series,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
) -> list[dict]:
    sma_50 = value_or_none(latest.get("SMA_50"))
    valid_supports = [level for level in supports if level < close]
    valid_resistances = [level for level in resistances if level > close]
    support = valid_supports[0] if valid_supports else None
    resistance = valid_resistances[0] if valid_resistances else None
    aggressive = close
    fair = support
    safe = resistance if resistance else sma_50 if sma_50 is not None and sma_50 > close else None
    invalid = support * 0.98 if support else None
    return [
        {
            "Zone": "Aggressive Kaufzone",
            "Marke": format_display_money(aggressive, original_currency, fx_rate, currency_mode),
            "Status": "Aktueller Kurs",
            "Bedeutung": "Nur sinnvoll, wenn Kaufsignal stark ist und man bewusst in kleiner Tranche startet.",
        },
        {
            "Zone": "Faire Kaufzone",
            "Marke": format_display_money(fair, original_currency, fx_rate, currency_mode) if fair else "Daten nicht verfügbar",
            "Status": "Berechenbar" if fair else "Keine klare Unterstützung",
            "Bedeutung": "Nahe erster Unterstützung; wenn keine Unterstützung erkannt wird, wird keine faire Kaufzone erfunden.",
        },
        {
            "Zone": "Sicherheits-Kaufzone",
            "Marke": format_display_money(safe, original_currency, fx_rate, currency_mode) if safe else "Daten nicht verfügbar",
            "Status": "Berechenbar" if safe else "Keine klare Bestätigungsmarke",
            "Bedeutung": "Nach bestätigter Trendwende oder Ausbruch über den wichtigsten Widerstand; ohne passende Marke lieber beobachten.",
        },
        {
            "Zone": "Ungültig, wenn Unterstützung bricht",
            "Marke": format_display_money(invalid, original_currency, fx_rate, currency_mode) if invalid else "Daten nicht verfügbar",
            "Status": "Berechenbar" if invalid else "Keine klare Ungültigkeitsmarke",
            "Bedeutung": "Unter dieser Zone ist die technische Idee beschädigt; ohne Marke muss die Position manuell neu bewertet werden.",
        },
    ]


def research_action(buy_signal: ModuleScore, risk_reward: RiskReward, supports: list[float], close: float) -> str:
    near_support = bool(supports and 0 <= (close - supports[0]) / close <= 0.04)
    if buy_signal.score < 3.5:
        return "Risiko zu hoch"
    if buy_signal.score < 5:
        return "Heute nicht kaufen"
    if buy_signal.score < 6.5:
        return "Beobachten"
    if near_support and risk_reward.score >= 6:
        return "Nachkaufzone erreicht"
    if buy_signal.score >= 8:
        return "Kleine Tranche möglich"
    return "Nachkauf nur bei Bestätigung"


def build_research_conclusion(
    action: str,
    modules: list[ResearchModule],
    buy_signal: ModuleScore,
    asset_quality: ModuleScore,
    risk_reward: RiskReward,
    supports: list[float],
    resistances: list[float],
    latest: pd.Series,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
) -> dict[str, str | list[str]]:
    positive = [m.summary for m in modules if m.score is not None and m.score >= 6.5][:3]
    negative = [m.summary for m in modules if m.score is not None and m.score <= 4.5][:3]
    if not positive:
        positive = ["Keine klar starken Research-Module erkannt."]
    if not negative:
        negative = ["Keine klar schwachen Research-Module erkannt."]
    decisive = supports[0] if supports else resistances[0] if resistances else None
    decisive_text = format_display_money(decisive, original_currency, fx_rate, currency_mode) if decisive else "Daten nicht verfügbar"
    improves = []
    if any("Daten nicht verfügbar" in " ".join(m.details) for m in modules):
        improves.append("Mehr belastbare Fundamental-/On-Chain-/ETF-Spezialdaten würden die Analyse verbessern.")
    if not improves:
        improves.append("Bestätigung durch Volumen, MACD und Verhalten an der entscheidenden Marke würde die Analyse verbessern.")
    if decisive:
        plan = (
            f"{action}. Konkreter Plan: keine Automatik, sondern Marke beobachten. "
            f"Wenn der Kurs die entscheidende Marke {decisive_text} verteidigt und Momentum bestätigt, ist eine kleine Tranche eher vertretbar. "
            "Wenn die Marke bricht oder Momentum schwach bleibt, abwarten und neu bewerten."
        )
    else:
        plan = (
            f"{action}. Konkreter Plan: keine Automatik. Weil keine belastbare Unterstützung oder kein belastbarer Widerstand erkannt wurde, "
            "erst auf eine klarere Kurszone, bessere Datenqualität und Momentum-Bestätigung warten."
        )
    return {
        "Was spricht für Kauf?": positive,
        "Was spricht gegen Kauf?": negative,
        "Was würde die Analyse verbessern?": improves,
        "Welche Marke ist entscheidend?": decisive_text,
        "Was wäre mein konkreter Plan?": plan,
    }


def build_research_pack(
    symbol: str,
    asset_profile: AssetProfile,
    asset_identity: dict,
    df: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    macro: ModuleScore,
    news: ModuleScore,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
) -> ResearchPack:
    latest = df.iloc[-1]
    close = float(latest["Close"])
    info = load_ticker_info(symbol)
    data_quality = data_quality_check(symbol, asset_profile, asset_identity, df)
    chart = research_chart_score(df, supports, resistances, market_phase)
    momentum = research_momentum_score(df)
    valuation = research_valuation_score(info, asset_profile, df, macro)
    fundamentals = research_fundamental_module(asset_quality, asset_profile)
    market_regime = research_market_regime(df, market_phase, macro)
    macro_impact = research_macro_impact(asset_profile, macro)
    commodity_context = research_commodity_context(asset_profile)
    bubble_risk = research_bubble_risk(info, df, valuation, momentum, news)
    innovation = research_innovation_context(info, asset_profile, asset_quality, bubble_risk, news)
    crypto_cycle = research_crypto_cycle(symbol, asset_profile, df)
    macro_module = module_from_existing("Makro-Score", macro, "Der Makro-Score bewertet Zinsen, Nasdaq, Dollar und Inflationsumfeld. Hoch heißt: Das Umfeld hilft eher.")
    news_module = module_from_existing("News-Score", news, "Der News-Score bewertet die Nachrichtenstimmung. Hoch heißt: Nachrichten geben eher Rückenwind.")
    risk = research_risk_score(df, risk_reward)
    liquidity = research_liquidity_score(df, info, asset_profile)
    analyst = research_analyst_consensus(info, asset_profile, original_currency, fx_rate, currency_mode)
    earnings = research_earnings_module(symbol, info, asset_profile)
    event_risk = research_event_risk_module(info, asset_profile, macro)
    institutional = research_institutional_data(info, asset_profile)
    modules = [chart, momentum, valuation, fundamentals, innovation, bubble_risk, market_regime, macro_impact, commodity_context, macro_module, news_module, risk, liquidity]
    if asset_profile.asset_type == "Krypto":
        modules.insert(4, crypto_cycle)
    institutional_modules = [analyst, earnings, event_risk, institutional]
    confidence = research_confidence_score(data_quality, liquidity, market_phase, df, modules, institutional_modules)
    uncertainty_factors = build_uncertainty_factors(data_quality, event_risk, earnings, news, macro, latest, market_phase, supports)
    scenarios = build_scenarios(close, supports, resistances, buy_signal, asset_quality, risk_reward, market_phase, latest, original_currency, fx_rate, currency_mode)
    buy_zones = build_buy_zones(close, supports, resistances, latest, original_currency, fx_rate, currency_mode)
    action = research_action(buy_signal, risk_reward, supports, close)
    conclusion = build_research_conclusion(action, modules, buy_signal, asset_quality, risk_reward, supports, resistances, latest, original_currency, fx_rate, currency_mode)
    return ResearchPack(data_quality, modules, institutional_modules, confidence, uncertainty_factors, scenarios, buy_zones, action, conclusion)


def build_forward_test_record(
    symbol: str,
    asset_identity: dict,
    asset_profile: AssetProfile,
    latest: pd.Series,
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    research_pack: ResearchPack,
    portfolio_result: PortfolioResult,
) -> dict:
    close = value_or_none(latest.get("Close"))
    return {
        "created_at": pd.Timestamp.now().isoformat(),
        "symbol": symbol,
        "name": asset_identity.get("name", ""),
        "asset_type": asset_profile.asset_type,
        "entry_price": close,
        "market_phase": market_phase.phase,
        "asset_quality": asset_quality.score,
        "buy_signal": buy_signal.score,
        "confidence": research_pack.confidence.score,
        "risk_reward_score": risk_reward.score,
        "risk_reward_ratio": risk_reward.ratio,
        "portfolio_mode": portfolio_result.enabled,
        "portfolio_score": portfolio_result.score,
        "action": research_pack.action,
        "scenarios": research_pack.scenarios,
        "buy_zones": research_pack.buy_zones,
        "module_scores": [
            {"name": module.name, "score": module.score, "summary": module.summary}
            for module in research_pack.modules
        ],
        "review_after": {
            "1w": None,
            "1m": None,
            "3m": None,
        },
        "note": "Forward-Test speichert nur die Analyse. Keine Kauf- oder Verkaufsautomatisierung.",
    }


def technical_module(score_result: ScoreResult, phase: MarketPhase) -> ModuleScore:
    details = score_result.reasons.copy()
    details.append(f"Marktphase: {phase.phase}.")
    return ModuleScore(score_result.score, f"Technischer Score {score_result.score}/10. {phase.summary}", details)


def final_recommendation(
    total_score: float,
    phase: MarketPhase,
    risk_reward: RiskReward,
    technical: ModuleScore,
    fundamentals: ModuleScore,
    macro: ModuleScore,
    news: ModuleScore,
    latest: pd.Series,
    supports: list[float],
    resistances: list[float],
    has_position: bool,
    portfolio_result: PortfolioResult | None = None,
) -> tuple[str, str]:
    close = float(latest["Close"])
    rsi = value_or_none(latest.get("RSI_14"))
    macd = value_or_none(latest.get("MACD"))
    signal = value_or_none(latest.get("MACD_Signal"))
    sma_50 = value_or_none(latest.get("SMA_50"))
    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None
    macd_positive = macd is not None and signal is not None and macd > signal
    overbought = rsi is not None and rsi > 70
    oversold = rsi is not None and rsi < 30
    trend_ok = sma_50 is not None and close >= sma_50
    support_label = format_currency(nearest_support) if nearest_support else "keine klare Unterstützung"
    resistance_label = format_currency(nearest_resistance) if nearest_resistance else "kein klarer Widerstand"

    if total_score >= 8 and technical.score >= 7 and risk_reward.score >= 6.5 and not overbought:
        title = "Aggressiver Nachkauf"
        action = f"Technisch und im Gesamtscore stark. Kauf in mehreren Tranchen: erste Tranche nahe aktuellem Kurs oder Rücksetzer Richtung {support_label}, weitere Tranche bei Ausbruch über {resistance_label} mit Volumen."
    elif total_score >= 6.5 and technical.score >= 5.5 and not overbought:
        title = "Kleiner Nachkauf"
        action = f"Kleiner Nachkauf ist vertretbar, aber nicht voll investieren. Besser in 2 Tranchen: eine nahe {support_label}, eine erst bei Bestätigung durch MACD/Volumen oder Ausbruch über {resistance_label}."
    elif total_score >= 5.5 and has_position:
        title = "Halten"
        action = f"Bestehende Position halten. Kein aggressiver Nachkauf, solange {resistance_label} nicht überwunden wird. Unter {support_label} würde das Risiko steigen."
    elif total_score >= 4.8:
        title = "Beobachten"
        action = f"Noch kein sauberer Kauf. Beobachten bis MACD positiv dreht, der Kurs {support_label} verteidigt oder {resistance_label} mit Volumen bricht."
    elif total_score >= 3.8 or oversold:
        title = "Warten"
        action = f"Warten. {'RSI ist überverkauft und kann eine Gegenbewegung auslösen, aber das reicht allein nicht.' if oversold else 'Die Signale sind zu gemischt.'} Kauf erst nach Stabilisierung über {support_label} oder Rückeroberung des 50er-Durchschnitts."
    else:
        title = "Risiko hoch"
        action = f"Keine neuen Käufe. Für bestehende Positionen Risiko reduzieren, wenn {support_label} bricht oder der Kurs unter dem 50er-Durchschnitt bleibt."

    if overbought:
        action += " RSI über 70 warnt zusätzlich vor Überhitzung; nicht hinterherkaufen."
    if phase.phase == "Bärenmarkt":
        action += " Die Marktphase ist ein Bärenmarkt, daher haben Kaufsignale geringere Qualität."
    if phase.phase == "Korrektur innerhalb eines Aufwärtstrends":
        action += " Die Marktphase ist eine Korrektur im Aufwärtstrend; Tranchen sind sinnvoller als ein voller Sofortkauf."

    if portfolio_result and portfolio_result.enabled:
        if not portfolio_result.available:
            action += " Portfolio-Modus ist aktiv, aber die Portfolio-Datei fehlt oder ist ungültig; die Empfehlung basiert daher nur auf dem Asset."
        elif portfolio_result.score is not None:
            if portfolio_result.score < 5:
                action += " Separater Depot-Effekt: Dein Portfolio spricht gegen einen Nachkauf, weil Klumpenrisiko oder Cash-Reserve kritisch sind. Das Kaufsignal bleibt unverändert."
            elif portfolio_result.score < 7 and title == "Aggressiver Nachkauf":
                action += " Separater Depot-Effekt: Moderate Depot-Risiken sprechen für kleinere Tranchen, verändern aber das Kaufsignal nicht."

    reason = (
        f"Gesamtscore {total_score}/10 aus Technik {technical.score}/10, Fundamentaldaten {fundamentals.score}/10, "
        f"Makro {macro.score}/10, News {news.score}/10 und CRV {risk_reward.score}/10. "
        f"Marktphase: {phase.phase}. {risk_reward.summary}"
    )
    if portfolio_result and portfolio_result.enabled and portfolio_result.available and portfolio_result.score is not None:
        reason += f" Depot-Score: {portfolio_result.score}/10. {portfolio_result.summary}"
    html = f"""
    <div class="decision-box">
        <div class="decision-title">{title}</div>
        <div class="decision-section"><strong>Konkrete Empfehlung:</strong> {action}</div>
        <div class="decision-section"><strong>Warum:</strong> {reason}</div>
        <div class="decision-section"><strong>Wahrscheinlichkeiten:</strong> {format_probabilities(phase.probabilities)}</div>
    </div>
    """
    return title, html


def final_recommendation_v2(
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    portfolio_result: PortfolioResult,
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    research_action_text: str,
    confidence: ResearchModule,
) -> tuple[str, str]:
    score = buy_signal.score
    if score >= 8:
        title = "Kleine Tranche möglich"
    elif score >= 6.5:
        title = "Nachkauf nur bei Bestätigung"
    elif score >= 5:
        title = "Beobachten"
    elif score >= 3.5:
        title = "Heute nicht kaufen"
    else:
        title = "Risiko zu hoch"

    context = f"Asset-Qualität: {asset_quality.score}/10. Kaufsignal: {buy_signal.score}/10."
    if asset_quality.score >= 7 and buy_signal.score < 6.5:
        context += " Die Anlage wirkt langfristig interessant, aber der aktuelle Einstieg ist noch nicht klar bestätigt."
    elif asset_quality.score < 5 and buy_signal.score >= 6.5:
        context += " Der Zeitpunkt wirkt besser als die langfristige Qualität; das spricht eher für vorsichtige Tranchen statt große Käufe."
    else:
        context += " Qualität und Timing widersprechen sich nicht stark."

    if research_action_text == title:
        research_text = "Research-Modul und Kaufsignal zeigen dieselbe Handlungseinschätzung."
    else:
        research_text = (
            f"Research-Modul ergänzt: {research_action_text}. "
            "Wenn diese Einschätzung vom Kaufsignal abweicht, ist das kein zweites Signal, sondern ein Hinweis auf Timing, Datenqualität oder CRV."
        )

    depot_text = "Portfolio-Modus ist aus; der Depot-Effekt wird nicht berücksichtigt."
    if portfolio_result.enabled:
        if portfolio_result.available and portfolio_result.score is not None:
            depot_text = f"Depot-Effekt: {portfolio_result.score}/10. {portfolio_result.summary}"
            if abs(portfolio_result.score - buy_signal.score) >= 2:
                depot_text += " Der Depot-Effekt verändert nicht das Kaufsignal, zeigt aber, ob ein Kauf für dein Depot verkraftbar wäre."
        else:
            depot_text = portfolio_result.summary

    confidence_text = "Daten nicht verfügbar."
    if confidence.score is not None:
        confidence_text = f"{confidence.score:.1f}/10. {confidence.summary}"

    html = f"""
    <div class="decision-box">
        <div class="recommendation-label">Zentrale Einschätzung</div>
        <div class="decision-title">{title}</div>
        <div class="decision-section"><strong>Primär nach Kaufsignal:</strong> {buy_signal.summary}</div>
        <div class="decision-section"><strong>Research-Einordnung:</strong> {research_text}</div>
        <div class="decision-section"><strong>Langfristiger Kontext:</strong> {context}</div>
        <div class="decision-section"><strong>Depot-Effekt:</strong> {depot_text}</div>
        <div class="decision-section"><strong>Vertrauen:</strong> {confidence_text}</div>
        <div class="decision-section"><strong>Marktphase / CRV:</strong> {market_phase.phase}. {risk_reward.summary}</div>
        <div class="decision-section"><strong>Wahrscheinlichkeiten:</strong> {format_probabilities(market_phase.probabilities)}</div>
    </div>
    """
    return title, html


def format_probabilities(probabilities: dict[str, int]) -> str:
    return " · ".join(f"{name}: {value}%" for name, value in probabilities.items())


def beginner_buy_answer(buy_signal_score: float, action_title: str) -> tuple[str, str]:
    if buy_signal_score >= 8:
        answer = "Ja"
    elif buy_signal_score >= 6.5:
        answer = "Eher Ja"
    elif buy_signal_score >= 5.0:
        answer = "Neutral"
    elif buy_signal_score >= 3.5:
        answer = "Eher Nein"
    else:
        answer = "Nein"

    score_text = str(buy_signal_score).replace(".", ",")
    text = (
        f"Meine einfache Einschätzung heute: {answer}. "
        f"Das Kaufsignal liegt bei {score_text}/10 und die Empfehlung lautet: {action_title}. "
        "Ein Kauf ist nur sinnvoll, wenn der Chart die genannten Marken bestätigt. "
        "Bei Unsicherheit ist Abwarten oder ein kleiner Einstieg besser als ein großer Sofortkauf. "
        "Die App ist nur eine Analysehilfe und ersetzt keine eigene Entscheidung."
    )
    return answer, text


def signal_tone(score: float, positive_at: float = 6.0, negative_at: float = 4.0) -> str:
    if score >= positive_at:
        return "positiv"
    if score <= negative_at:
        return "negativ"
    return "neutral"


def is_warning_score_module(module: ResearchModule) -> bool:
    return "Blasenrisiko" in module.name


def score_band(score: float | None, inverse: bool = False) -> str:
    if score is None:
        return "Daten nicht verfügbar"
    if inverse:
        if score >= 7.5:
            return "hoch / Warnsignal"
        if score >= 6.0:
            return "erhöht"
        if score >= 4.5:
            return "mittel"
        if score >= 3.5:
            return "moderat"
        return "niedrig"
    if score >= 7.5:
        return "stark"
    if score >= 6.0:
        return "konstruktiv"
    if score >= 4.5:
        return "gemischt"
    if score >= 3.5:
        return "schwach"
    return "kritisch"


def research_score_interpretation(module: ResearchModule) -> str:
    if module.score is None:
        return "Für diesen Baustein fehlen belastbare Daten. Er sollte die Entscheidung deshalb nicht stark beeinflussen."

    inverse = is_warning_score_module(module)
    band = score_band(module.score, inverse)
    if inverse:
        if module.score >= 7.5:
            return f"{band.capitalize()}: Dieser Baustein warnt vor Überhitzung oder spekulativer Bewertung. Praktisch heißt das: besonders vorsichtig planen."
        if module.score >= 6.0:
            return f"{band.capitalize()}: Es gibt Überhitzungszeichen. Praktisch heißt das: keine großen Sofortkäufe."
        if module.score >= 4.5:
            return f"{band.capitalize()}: Das Blasenrisiko ist gemischt. Praktisch heißt das: weitere Bestätigung abwarten."
        return f"{band.capitalize()}: Aus den verfügbaren Daten kommt kein starkes Blasenwarnsignal."
    if module.score >= 7.5:
        return f"{band.capitalize()}: Dieser Baustein unterstützt das Investment klar, ersetzt aber kein Kaufsignal."
    if module.score >= 6.0:
        return f"{band.capitalize()}: Dieser Baustein spricht eher für das Investment, braucht aber Bestätigung durch die übrigen Module."
    if module.score >= 4.5:
        return f"{band.capitalize()}: Dieser Baustein ist uneindeutig. Praktisch heißt das: nicht übergewichten, sondern auf Bestätigung warten."
    if module.score >= 3.5:
        return f"{band.capitalize()}: Dieser Baustein bremst die Analyse. Praktisch heißt das: vorsichtiger planen oder kleinere Tranchen wählen."
    return f"{band.capitalize()}: Dieser Baustein spricht deutlich gegen einen Einstieg oder erhöht das Risiko stark."


def beginner_explanations(
    latest: pd.Series,
    supports: list[float],
    resistances: list[float],
    asset_profile: AssetProfile,
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    fundamentals: ModuleScore,
    news: ModuleScore,
    macro: ModuleScore,
    technical: ModuleScore,
    portfolio_result: PortfolioResult,
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    data_quality: ResearchModule,
    quality_label: str,
    quality_highlights: list[str],
    original_currency: str = "EUR",
    fx_rate: float | None = 1.0,
    currency_mode: str = "EUR + Originalwährung",
) -> list[tuple[str, str, str]]:
    close = float(latest["Close"])
    rsi = value_or_none(latest.get("RSI_14"))
    macd = value_or_none(latest.get("MACD"))
    signal = value_or_none(latest.get("MACD_Signal"))
    volatility = value_or_none(latest.get("Volatility"))
    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None

    items: list[tuple[str, str, str]] = []

    items.append(("Asset-Typ", "Der Asset-Typ entscheidet, welche Kennzahlen sinnvoll sind.", f"Aktuell erkannt: {asset_profile.asset_type}. Praktisch heißt das: Die App nutzt dafür passende Gewichtungen und schreibt bei fehlenden Spezialdaten ehrlich 'Daten nicht verfügbar'."))
    data_score = "n/a" if data_quality.score is None else f"{data_quality.score:.1f}/10"
    items.append(("Datenqualität", "Die Datenqualität zeigt, wie belastbar die Analysegrundlage ist.", f"Aktuell steht die Ampel auf {quality_label} ({data_score}). Wichtigste Hinweise: {' | '.join(quality_highlights)}. Praktisch heißt das: Je schlechter die Datenqualität, desto vorsichtiger solltest du Score und Empfehlung verwenden."))
    items.append(("Asset-Qualität", "Asset-Qualität bewertet, ob das Asset langfristig interessant und solide wirkt.", f"Aktuell liegt die Asset-Qualität bei {asset_quality.score}/10. Praktisch heißt das: Ein gutes Asset kann langfristig interessant sein, auch wenn der Einstieg heute noch nicht ideal ist."))
    items.append(("Kaufsignal", "Das Kaufsignal bewertet nur, ob jetzt ein guter Einstiegsmoment sein könnte.", f"Aktuell liegt das Kaufsignal bei {buy_signal.score}/10. Praktisch heißt das: Dieser Wert steuert die Kaufempfehlung, nicht dein Depot und nicht die langfristige Qualität allein."))

    if rsi is None:
        rsi_current = "Aktuell gibt es noch zu wenige Daten für eine saubere RSI-Bewertung."
        rsi_practical = "Praktisch heißt das: RSI heute nicht überbewerten."
    elif rsi < 30:
        rsi_current = f"Der RSI liegt bei {rsi:.1f}. Das ist überverkauft und für antizyklische Käufer grundsätzlich interessant."
        rsi_practical = "Praktisch heißt das: Nicht blind kaufen, sondern auf Stabilisierung oder ein bestätigendes MACD-/Volumensignal warten."
    elif rsi > 70:
        rsi_current = f"Der RSI liegt bei {rsi:.1f}. Das ist überkauft und warnt vor Überhitzung."
        rsi_practical = "Praktisch heißt das: Nicht hinterherkaufen; eher Rücksetzer oder Teilgewinne prüfen."
    else:
        rsi_current = f"Der RSI liegt bei {rsi:.1f}. Das ist weder extrem überkauft noch extrem überverkauft."
        rsi_practical = "Praktisch heißt das: Andere Signale wie Trend, MACD und Unterstützungen sind wichtiger."
    items.append(("RSI", "Der RSI misst, ob ein Asset kurzfristig stark gekauft oder stark verkauft wurde.", f"{rsi_current} {rsi_practical}"))

    if macd is None or signal is None:
        macd_current = "Aktuell fehlen genug Daten für eine klare MACD-Aussage."
    elif macd > signal:
        macd_current = "Aktuell liegt MACD über der Signal-Linie. Das ist positiv, weil das Momentum eher nach oben zeigt."
    else:
        macd_current = "Aktuell liegt MACD unter der Signal-Linie. Das ist negativ, weil das Momentum noch schwach ist."
    items.append(("MACD", "Der MACD zeigt, ob sich das Momentum verbessert oder verschlechtert.", f"{macd_current} Praktisch heißt das: Kaufen wird besser, wenn MACD nach oben dreht."))

    if nearest_support:
        distance = (close - nearest_support) / close * 100
        support_label = format_display_money(nearest_support, original_currency, fx_rate, currency_mode)
        current = f"Die wichtigste Unterstützung liegt bei {support_label}, also {distance:.1f}% unter dem aktuellen Kurs."
        practical = "Praktisch heißt das: Dort könnte der Kurs Halt finden; fällt er darunter, steigt das Risiko."
    else:
        current = "Aktuell wurde keine klare Unterstützung erkannt."
        practical = "Praktisch heißt das: Ein Einstieg ist schwerer planbar."
    items.append(("Unterstützungen", "Unterstützungen sind Kursbereiche, in denen Käufer früher wieder eingestiegen sind.", f"{current} {practical}"))

    if nearest_resistance:
        distance = (nearest_resistance - close) / close * 100
        resistance_label = format_display_money(nearest_resistance, original_currency, fx_rate, currency_mode)
        current = f"Der wichtigste Widerstand liegt bei {resistance_label}, also {distance:.1f}% über dem aktuellen Kurs."
        practical = "Praktisch heißt das: Dort können Verkäufer auftauchen; ein Ausbruch darüber wäre positiv."
    else:
        current = "Aktuell wurde kein klarer Widerstand erkannt."
        practical = "Praktisch heißt das: Das Gewinnziel ist weniger sauber ableitbar."
    items.append(("Widerstände", "Widerstände sind Kursbereiche, an denen früher Verkaufsdruck entstanden ist.", f"{current} {practical}"))

    phase_tone = "positiv" if market_phase.phase == "Bullenmarkt" else "negativ" if market_phase.phase == "Bärenmarkt" else "neutral"
    items.append(("Marktphase", "Die Marktphase beschreibt das große Umfeld des Charts.", f"Aktuell erkennt die App: {market_phase.phase}. Das ist insgesamt {phase_tone}. Praktisch heißt das: In starken Marktphasen sind Kaufsignale zuverlässiger, in schwachen Marktphasen vorsichtiger handeln."))

    if risk_reward.ratio is None:
        crv_current = "Das CRV ist aktuell nicht sauber berechenbar, weil Unterstützung oder Widerstand fehlt."
    else:
        crv_current = f"Das CRV liegt bei {risk_reward.ratio:.2f}. Risiko: {percent_text(risk_reward.risk_pct)}, Potenzial: {percent_text(risk_reward.reward_pct)}."
    items.append(("CRV", "Das Chancen-Risiko-Verhältnis vergleicht möglichen Gewinn mit möglichem Verlust.", f"{crv_current} Praktisch heißt das: Je höher das CRV, desto attraktiver ist ein Einstieg."))

    if volatility is None:
        vol_current = "Aktuell fehlen genug Daten für die Volatilität."
    else:
        vol_current = f"Die Volatilität liegt bei ca. {volatility * 100:.1f}%. Das ist {signal_tone(10 - min(volatility * 15, 10), 6, 4)} für die Planbarkeit."
    items.append(("Volatilität", "Volatilität zeigt, wie stark der Kurs schwankt.", f"{vol_current} Praktisch heißt das: Bei hoher Volatilität kleinere Positionen und klare Grenzen wählen."))

    items.append(("Fundamentaldaten", "Fundamentaldaten zeigen, wie gesund ein Unternehmen finanziell wirkt.", f"Aktuell liegt der Fundamentalscore bei {fundamentals.score}/10. Das ist {signal_tone(fundamentals.score)}. Praktisch heißt das: Gute Fundamentaldaten stützen langfristige Käufe, schlechte sprechen für Vorsicht."))

    items.append(("News-Score", "Der News-Score fasst die Stimmung aktueller Nachrichten zusammen.", f"Aktuell liegt der News-Score bei {news.score}/10. Das ist {signal_tone(news.score)}. Praktisch heißt das: Positive Nachrichten können Rückenwind geben, negative erhöhen das kurzfristige Risiko."))

    items.append(("Makro-Score", "Der Makro-Score bewertet das große Umfeld wie Zinsen, Nasdaq und Dollar.", f"Aktuell liegt der Makro-Score bei {macro.score}/10. Das ist {signal_tone(macro.score)}. Praktisch heißt das: Ein gutes Umfeld macht Kaufsignale glaubwürdiger."))

    probability_text = format_probabilities(market_phase.probabilities)
    items.append(("Wahrscheinlichkeiten", "Die Wahrscheinlichkeiten sind eine grobe Szenario-Schätzung aus Trend, RSI, MACD, Volumen und Volatilität.", f"Aktuell: {probability_text}. Praktisch heißt das: Du siehst, ob die App eher Bodenbildung, weiteren Test oder Erholung erwartet."))

    if portfolio_result.enabled:
        if portfolio_result.available:
            depot_score = "n/a" if portfolio_result.score is None else f"{portfolio_result.score}/10"
            items.append(("Depot-Effekt", "Der Depot-Effekt prüft, ob ein Kauf zu deinem bestehenden Portfolio passt.", f"Aktuell liegt der Depot-Effekt bei {depot_score}. {portfolio_result.summary} Praktisch heißt das: Er verändert nicht das Kaufsignal, sondern zeigt nur, ob ein Kauf für dein Depot verkraftbar wäre."))
        else:
            items.append(("Depot-Effekt", "Der Portfolio-Modus braucht eine portfolio.json.", portfolio_result.summary))
    else:
        items.append(("Depot-Effekt", "Der Portfolio-Modus ist ausgeschaltet.", "Praktisch heißt das: Die App bewertet nur Asset-Qualität und Kaufsignal und ignoriert bestehende Positionen, Klumpenrisiko und Cash-Reserve."))

    return items


def calculate_score(df: pd.DataFrame, supports: list[float], resistances: list[float]) -> ScoreResult:
    latest = df.dropna(subset=["Close"]).iloc[-1]
    close = float(latest["Close"])
    score = 0.0
    reasons: list[str] = []

    sma_50 = latest.get("SMA_50")
    sma_200 = latest.get("SMA_200")
    if pd.notna(sma_50) and close > sma_50:
        score += 1.0
        reasons.append("Der Kurs liegt über dem 50er-Durchschnitt.")
    if pd.notna(sma_50) and pd.notna(sma_200) and sma_50 > sma_200:
        score += 1.0
        reasons.append("Der mittelfristige Trend liegt über dem langfristigen Trend.")

    rsi = latest.get("RSI_14")
    if pd.notna(rsi):
        if 45 <= rsi <= 65:
            score += 2.0
            reasons.append("Der RSI wirkt konstruktiv, aber nicht stark überhitzt.")
        elif 35 <= rsi < 45 or 65 < rsi <= 72:
            score += 1.0
            reasons.append("Der RSI ist neutral bis leicht angespannt.")
        elif rsi < 30:
            score += 0.75
            reasons.append("Der RSI zeigt Überverkauftheit, bleibt aber riskant.")
        else:
            reasons.append("Der RSI warnt vor Überhitzung oder Schwäche.")

    nearest_support = supports[0] if supports else None
    support_distance = pct_distance(close, nearest_support)
    if support_distance is not None:
        if 0 <= support_distance <= 0.05:
            score += 1.5
            reasons.append("Der Kurs liegt nahe an einer Unterstützung.")
        elif support_distance <= 0.12:
            score += 1.0
            reasons.append("Die nächste Unterstützung ist noch in Reichweite.")
        else:
            score += 0.25
            reasons.append("Die nächste Unterstützung liegt relativ weit entfernt.")

    nearest_resistance = resistances[0] if resistances else None
    resistance_room = None
    if nearest_resistance and close:
        resistance_room = (nearest_resistance - close) / close
        if resistance_room >= 0.12:
            score += 1.5
            reasons.append("Bis zum nächsten Widerstand bleibt spürbar Platz.")
        elif resistance_room >= 0.05:
            score += 1.0
            reasons.append("Zum nächsten Widerstand besteht noch moderater Abstand.")
        else:
            score += 0.25
            reasons.append("Der nächste Widerstand liegt nah am aktuellen Kurs.")

    volume = latest.get("Volume")
    volume_avg = latest.get("Volume_SMA_20")
    macd = latest.get("MACD")
    signal = latest.get("MACD_Signal")
    if pd.notna(volume) and pd.notna(volume_avg) and volume_avg > 0:
        volume_ratio = volume / volume_avg
        if pd.notna(macd) and pd.notna(signal) and macd >= signal and volume_ratio >= 1:
            score += 1.0
            reasons.append("Das Volumen bestätigt die positive MACD-Tendenz.")
        elif 0.75 <= volume_ratio <= 1.5:
            score += 0.6
            reasons.append("Das Volumen wirkt unauffällig.")
        else:
            reasons.append("Das Volumen liefert kein klares positives Signal.")

    volatility = latest.get("Volatility")
    if pd.notna(volatility):
        if volatility <= 0.25:
            score += 1.0
            reasons.append("Die aktuelle Volatilität ist vergleichsweise moderat.")
        elif volatility <= 0.45:
            score += 0.6
            reasons.append("Die Volatilität ist erhöht, aber noch handhabbar.")
        else:
            reasons.append("Die Volatilität ist hoch und erhöht das Risiko.")

    score = round(max(0.0, min(10.0, score)), 1)
    if score >= 8:
        recommendation = "Nachkauf prüfen"
    elif score >= 6:
        recommendation = "Halten / beobachten"
    elif score >= 4:
        recommendation = "Warten"
    else:
        recommendation = "Risiko hoch"

    return ScoreResult(score=score, recommendation=recommendation, reasons=reasons[:5])


def calculate_score_v2(df: pd.DataFrame, supports: list[float], resistances: list[float]) -> ScoreResult:
    latest = df.dropna(subset=["Close"]).iloc[-1]
    close = float(latest["Close"])
    score = 0.0
    reasons: list[str] = []
    breakdown: list[tuple[str, float, str]] = []

    sma_50 = latest.get("SMA_50")
    sma_200 = latest.get("SMA_200")
    trend_points = 0.0
    if pd.notna(sma_50) and close > sma_50:
        trend_points += 1.0
        reasons.append("Der Kurs liegt über dem 50er-Durchschnitt.")
    if pd.notna(sma_50) and pd.notna(sma_200) and sma_50 > sma_200:
        trend_points += 1.0
        reasons.append("Der mittelfristige Trend liegt über dem langfristigen Trend.")
    score += trend_points
    if pd.isna(sma_50):
        breakdown.append(("Trend", 0.0, "Noch zu wenige Daten für den 50er-Durchschnitt."))
    elif trend_points >= 2:
        breakdown.append(("Trend", trend_points, "Kurz- und Langfristtrend sind positiv."))
    elif trend_points > 0:
        breakdown.append(("Trend", trend_points, "Der kurzfristige Trend ist positiv, aber noch nicht voll bestätigt."))
    else:
        breakdown.append(("Trend", 0.0, "Der Kurs liegt nicht über wichtigen Durchschnitten."))

    rsi = latest.get("RSI_14")
    if pd.notna(rsi):
        if 45 <= rsi <= 65:
            score += 2.0
            breakdown.append(("RSI", 2.0, "Neutral bis konstruktiv: Kaufdruck ist sichtbar, aber nicht überhitzt."))
            reasons.append("Der RSI wirkt konstruktiv, aber nicht stark überhitzt.")
        elif 35 <= rsi < 45 or 65 < rsi <= 72:
            score += 1.0
            breakdown.append(("RSI", 1.0, "Leicht angespannt: Das Signal ist brauchbar, aber nicht eindeutig."))
            reasons.append("Der RSI ist neutral bis leicht angespannt.")
        elif rsi < 30:
            score += 1.5
            breakdown.append(("RSI", 1.5, "Überverkauft: Für antizyklische Käufer positiv, aber nur mit Stabilisierung und Bestätigung durch MACD oder Volumen."))
            reasons.append("Der RSI zeigt Überverkauftheit, bleibt aber riskant.")
        else:
            breakdown.append(("RSI", 0.0, "Warnsignal: Der Markt wirkt überhitzt oder technisch schwach."))
            reasons.append("Der RSI warnt vor Überhitzung oder Schwäche.")
    else:
        breakdown.append(("RSI", 0.0, "Noch nicht genug Kursdaten für RSI 14."))

    nearest_support = supports[0] if supports else None
    support_distance = pct_distance(close, nearest_support)
    if support_distance is not None:
        if 0 <= support_distance <= 0.05:
            score += 1.5
            breakdown.append(("Unterstützung", 1.5, "Der Kurs liegt nahe an einer Zone, in der zuvor Käufer aktiv wurden."))
            reasons.append("Der Kurs liegt nahe an einer Unterstützung.")
        elif support_distance <= 0.12:
            score += 1.0
            breakdown.append(("Unterstützung", 1.0, "Die nächste Unterstützung ist erreichbar, aber nicht direkt unter dem Kurs."))
            reasons.append("Die nächste Unterstützung ist noch in Reichweite.")
        else:
            score += 0.25
            breakdown.append(("Unterstützung", 0.25, "Bis zur nächsten Unterstützung ist viel Platz nach unten."))
            reasons.append("Die nächste Unterstützung liegt relativ weit entfernt.")
    else:
        breakdown.append(("Unterstützung", 0.0, "Im gewählten Zeitraum wurde keine nahe Unterstützung erkannt."))

    nearest_resistance = resistances[0] if resistances else None
    if nearest_resistance and close:
        resistance_room = (nearest_resistance - close) / close
        if resistance_room >= 0.12:
            score += 1.5
            breakdown.append(("Widerstand", 1.5, "Bis zur nächsten Verkaufszone bleibt viel Aufwärtsspielraum."))
            reasons.append("Bis zum nächsten Widerstand bleibt spürbar Platz.")
        elif resistance_room >= 0.05:
            score += 1.0
            breakdown.append(("Widerstand", 1.0, "Bis zum nächsten Widerstand bleibt noch etwas Platz."))
            reasons.append("Zum nächsten Widerstand besteht noch moderater Abstand.")
        else:
            score += 0.25
            breakdown.append(("Widerstand", 0.25, "Der Kurs steht nahe an einer Zone, in der zuvor verkauft wurde."))
            reasons.append("Der nächste Widerstand liegt nah am aktuellen Kurs.")
    else:
        breakdown.append(("Widerstand", 0.0, "Im gewählten Zeitraum wurde kein naher Widerstand erkannt."))

    volume = latest.get("Volume")
    volume_avg = latest.get("Volume_SMA_20")
    macd = latest.get("MACD")
    signal = latest.get("MACD_Signal")
    if pd.notna(volume) and pd.notna(volume_avg) and volume_avg > 0:
        volume_ratio = volume / volume_avg
        if pd.notna(macd) and pd.notna(signal) and macd >= signal and volume_ratio >= 1:
            score += 1.0
            breakdown.append(("Volumen", 1.0, "Mehr Aktivität als im Schnitt bestätigt die positive MACD-Tendenz."))
            reasons.append("Das Volumen bestätigt die positive MACD-Tendenz.")
        elif 0.75 <= volume_ratio <= 1.5:
            score += 0.6
            breakdown.append(("Volumen", 0.6, "Das Handelsvolumen ist normal und gibt kein starkes Warnsignal."))
            reasons.append("Das Volumen wirkt unauffällig.")
        else:
            breakdown.append(("Volumen", 0.0, "Das Volumen bestätigt die Bewegung nicht klar."))
            reasons.append("Das Volumen liefert kein klares positives Signal.")
    else:
        breakdown.append(("Volumen", 0.0, "Noch nicht genug Volumendaten für einen Vergleich."))

    volatility = latest.get("Volatility")
    if pd.notna(volatility):
        if volatility <= 0.25:
            score += 1.0
            breakdown.append(("Volatilität", 1.0, "Die Schwankung ist moderat. Positionsgrößen lassen sich leichter planen."))
            reasons.append("Die aktuelle Volatilität ist vergleichsweise moderat.")
        elif volatility <= 0.45:
            score += 0.6
            breakdown.append(("Volatilität", 0.6, "Die Schwankung ist erhöht. Einstieg und Positionsgröße sollten vorsichtiger gewählt werden."))
            reasons.append("Die Volatilität ist erhöht, aber noch handhabbar.")
        else:
            breakdown.append(("Volatilität", 0.0, "Die Schwankung ist hoch. Kleine Nachrichten können große Kursbewegungen auslösen."))
            reasons.append("Die Volatilität ist hoch und erhöht das Risiko.")
    else:
        breakdown.append(("Volatilität", 0.0, "Noch nicht genug Daten für die aktuelle Volatilität."))

    score = round(max(0.0, min(10.0, score)), 1)
    if score >= 8:
        recommendation = "Kaufen in Tranchen prüfen"
    elif score >= 6:
        recommendation = "Halten / beobachten"
    elif score >= 4:
        recommendation = "Warten"
    else:
        recommendation = "Risiko hoch"

    return ScoreResult(score=score, recommendation=recommendation, reasons=reasons[:5], breakdown=breakdown)


def format_currency(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_money(value: float, currency: str = "EUR") -> str:
    number = format_currency(value)
    currency = (currency or "EUR").upper()
    if currency == "EUR":
        return f"{number} €"
    return f"{number} {currency}"


def convert_to_eur(value: float, fx_rate: float | None) -> float | None:
    if fx_rate is None:
        return None
    return value * fx_rate


def format_display_money(value: float, original_currency: str, fx_rate: float | None, display_mode: str) -> str:
    original_currency = (original_currency or "EUR").upper()
    if original_currency == "EUR":
        return format_money(value, "EUR")

    eur_value = convert_to_eur(value, fx_rate)
    if eur_value is None:
        return f"Daten nicht verfügbar ({format_money(value, original_currency)})"
    if display_mode == "Nur EUR":
        return format_money(eur_value, "EUR")
    return f"{format_money(eur_value, 'EUR')} ({format_money(value, original_currency)})"


def converted_price_frame(df: pd.DataFrame, fx_rate: float | None) -> pd.DataFrame:
    if fx_rate is None:
        return df.copy()
    display_df = df.copy()
    for column in ["Open", "High", "Low", "Close", "SMA_50", "SMA_200"]:
        if column in display_df:
            display_df[column] = display_df[column] * fx_rate
    return display_df


def converted_levels(levels: list[float], fx_rate: float | None) -> list[float]:
    if fx_rate is None:
        return levels
    return [level * fx_rate for level in levels]


def add_level_lines(fig: go.Figure, levels: Iterable[float], color: str, label: str) -> None:
    for idx, level in enumerate(levels, start=1):
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_color=color,
            annotation_text=f"{label} {idx}",
            annotation_position="right",
        )


def render_price_chart(df: pd.DataFrame, supports: list[float], resistances: list[float], currency_label: str = "") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Kurs",
        )
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="50er Durchschnitt", line=dict(color="#2563eb")))
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_200"], name="200er Durchschnitt", line=dict(color="#f97316")))
    add_level_lines(fig, supports, "#16a34a", "Unterstützung")
    add_level_lines(fig, resistances, "#dc2626", "Widerstand")
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis_rangeslider_visible=False,
        yaxis_title=currency_label,
    )
    return fig


def render_line_chart(df: pd.DataFrame, columns: list[str], title: str) -> go.Figure:
    fig = go.Figure()
    for column in columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[column], name=column, mode="lines"))
    fig.update_layout(height=300, title=title, margin=dict(l=10, r=10, t=45, b=10))
    return fig


def render_volume_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volumen", marker_color="#64748b"))
    fig.add_trace(go.Scatter(x=df.index, y=df["Volume_SMA_20"], name="20er Volumenschnitt", line=dict(color="#0f766e")))
    fig.update_layout(height=300, title="Volumenentwicklung", margin=dict(l=10, r=10, t=45, b=10))
    return fig


def latest_value(latest: pd.Series, key: str) -> float | None:
    value = latest.get(key)
    if pd.isna(value):
        return None
    return float(value)


def rsi_explanation(rsi: float | None) -> tuple[str, str]:
    if rsi is None:
        return "Nicht verfügbar", "Es gibt noch nicht genug Kursdaten für RSI 14."
    if rsi < 30:
        return (
            "Überverkauft",
            "Der Kurs ist zuletzt stark gefallen. Für dich heißt das: Nicht blind kaufen, sondern auf Stabilisierung, steigendes Volumen oder eine Rückeroberung wichtiger Marken achten.",
        )
    if rsi <= 45:
        return (
            "Schwach bis neutral",
            "Der Verkaufsdruck lässt nach, aber der Markt zeigt noch keine klare Stärke. Als Anleger eher beobachten und nicht alles auf einmal investieren.",
        )
    if rsi <= 65:
        return (
            "Neutral bis konstruktiv",
            "Das Momentum ist gesund. Bestehende Positionen können beobachtet werden; neue Einstiege sollten trotzdem an Unterstützungen oder Pullbacks geplant werden.",
        )
    if rsi <= 70:
        return (
            "Kräftig",
            "Der Trend ist stark, aber ein Einstieg kann schon spät sein. Teilkäufe oder Warten auf Rücksetzer sind defensiver.",
        )
    return (
        "Überkauft",
        "Der Kurs ist stark gelaufen. Das ist nicht automatisch ein Verkaufssignal, aber Gewinnmitnahmen oder Rücksetzer werden wahrscheinlicher.",
    )


def macd_explanation(macd: float | None, signal: float | None) -> tuple[str, str]:
    if macd is None or signal is None:
        return "Nicht verfügbar", "Es gibt noch nicht genug Daten für MACD und Signal-Linie."
    if macd > signal:
        return "Positives Momentum", "MACD liegt über der Signal-Linie. Das spricht kurzfristig für steigenden Kaufdruck."
    if macd < signal:
        return "Negatives Momentum", "MACD liegt unter der Signal-Linie. Das spricht kurzfristig für Vorsicht oder abnehmenden Kaufdruck."
    return "Neutral", "MACD und Signal-Linie liegen fast gleichauf. Das Momentum ist unentschlossen."


def trend_explanation(close: float, sma_50: float | None, sma_200: float | None) -> tuple[str, str]:
    if sma_50 is None:
        return "Nicht verfügbar", "Für den 50er-Durchschnitt gibt es im gewählten Zeitraum noch nicht genug Daten."
    if sma_200 is None:
        if close > sma_50:
            return "Kurzfristig positiv", "Der Kurs liegt über dem 50er-Durchschnitt. Der langfristige Vergleich fehlt noch."
        return "Kurzfristig schwach", "Der Kurs liegt unter dem 50er-Durchschnitt. Das spricht für Vorsicht."
    if close > sma_50 > sma_200:
        return "Aufwärtstrend", "Kurs, 50er- und 200er-Durchschnitt sind positiv gestaffelt. Das ist technisch konstruktiv."
    if close < sma_50 < sma_200:
        return "Abwärtstrend", "Kurs, 50er- und 200er-Durchschnitt sind negativ gestaffelt. Als Anleger eher defensiv bleiben."
    return "Gemischter Trend", "Die Durchschnitte liefern kein einheitliches Bild. Besser auf klare Ausbrüche oder Rücksetzer warten."


def volatility_explanation(volatility: float | None) -> tuple[str, str]:
    if volatility is None:
        return "Nicht verfügbar", "Es gibt noch nicht genug Renditedaten für die Volatilität."
    percent = volatility * 100
    if volatility <= 0.25:
        return "Moderat", f"Die annualisierte Schwankung liegt bei ca. {percent:.1f}%. Das Risiko ist technisch besser planbar."
    if volatility <= 0.45:
        return "Erhöht", f"Die annualisierte Schwankung liegt bei ca. {percent:.1f}%. Positionsgröße und Einstieg sollten vorsichtig gewählt werden."
    return "Hoch", f"Die annualisierte Schwankung liegt bei ca. {percent:.1f}%. Kleine Positionsgrößen und klare Risikogrenzen sind wichtiger."


def level_explanation(
    close: float,
    supports: list[float],
    resistances: list[float],
    original_currency: str = "EUR",
    fx_rate: float | None = 1.0,
    currency_mode: str = "EUR + Originalwährung",
) -> tuple[str, str]:
    support_text = "Keine nahe Unterstützung erkannt."
    resistance_text = "Kein naher Widerstand erkannt."
    if supports:
        distance = (close - supports[0]) / close * 100
        support_text = f"Nächste Unterstützung: {format_display_money(supports[0], original_currency, fx_rate, currency_mode)}, ca. {distance:.1f}% unter dem Kurs."
    if resistances:
        distance = (resistances[0] - close) / close * 100
        resistance_text = f"Nächster Widerstand: {format_display_money(resistances[0], original_currency, fx_rate, currency_mode)}, ca. {distance:.1f}% über dem Kurs."
    return "Kurszonen", f"{support_text} {resistance_text} Nahe Unterstützungen können Einstiege planbarer machen; nahe Widerstände begrenzen oft das kurzfristige Chance-Risiko-Verhältnis."


def build_action_plan(
    score_result: ScoreResult,
    latest: pd.Series,
    supports: list[float],
    resistances: list[float],
) -> tuple[str, str]:
    close = float(latest["Close"])
    rsi = latest_value(latest, "RSI_14")
    sma_50 = latest_value(latest, "SMA_50")
    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None

    support_text = "einer erkannten Unterstützung"
    support_break_text = "eine erkannte Unterstützung"
    if nearest_support:
        support_distance = (close - nearest_support) / close * 100
        support_text = f"der nächsten Unterstützung bei {format_currency(nearest_support)} ({support_distance:.1f}% unter dem aktuellen Kurs)"
        support_break_text = f"die nächste Unterstützung bei {format_currency(nearest_support)}"

    resistance_text = "dem nächsten Widerstand"
    if nearest_resistance:
        resistance_distance = (nearest_resistance - close) / close * 100
        resistance_text = f"dem nächsten Widerstand bei {format_currency(nearest_resistance)} ({resistance_distance:.1f}% über dem aktuellen Kurs)"

    if score_result.score >= 8:
        return (
            "Kaufen in Tranchen prüfen",
            f"Technisch ist das Bild stark. Sinnvoller als ein voller Sofortkauf sind 2 bis 3 Tranchen: eine kleine Startposition jetzt oder nahe {support_text}, eine zweite bei Bestätigung über dem letzten Hoch oder über dem 50er-Durchschnitt, und eine letzte nur, wenn der Ausbruch mit Volumen bestätigt wird. Tranchen reduzieren das Risiko, dass du direkt vor einem Rücksetzer alles investierst.",
        )

    if score_result.score >= 6:
        return (
            "Halten, Nachkauf nur bei Bestätigung",
            f"Das Setup ist brauchbar, aber nicht stark genug für aggressives Kaufen. Bestehende Positionen können gehalten werden. Ein Nachkauf ist technisch am saubersten bei einem Rücksetzer Richtung {support_text} oder bei einem klaren Ausbruch über {resistance_text}. Wenn der RSI über 70 steigt, eher nicht hinterherkaufen.",
        )

    if score_result.score >= 4:
        return (
            "Warten bis ein klares Signal kommt",
            f"Der Score ist gemischt. Warten heißt hier: nicht kaufen, bis entweder der Kurs eine Unterstützung verteidigt und wieder steigt, MACD über die Signal-Linie dreht oder der Kurs einen Widerstand mit Volumen überwindet. Fällt der Kurs unter {support_break_text}, steigt das Risiko weiter.",
        )

    if rsi is not None and rsi < 30:
        return (
            "Risiko hoch, keine Eile trotz Überverkauftheit",
            f"Der RSI ist überverkauft, aber das ist allein kein Kaufsignal. Besser warten, bis der Kurs nicht mehr weiter fällt, eine Unterstützung hält und MACD oder Volumen eine Stabilisierung zeigen. Wer bereits investiert ist, kann prüfen, ob die eigene Verlustgrenze erreicht ist.",
        )

    if sma_50 is not None and close < sma_50:
        return (
            "Risiko reduzieren prüfen",
            f"Der Kurs liegt unter dem 50er-Durchschnitt und der Score ist schwach. Für bestehende Positionen heißt das: Verkauf oder Teilverkauf erst prüfen, wenn die eigene Strategie verletzt ist, z. B. Bruch einer Unterstützung, weiter fallender Trend oder zu große Positionsgröße. Neue Käufe erst nach Stabilisierung.",
        )

    return (
        "Risiko hoch, abwarten",
        "Die Technik liefert zu wenige positive Signale. Neue Käufe sind aktuell schwer zu begründen. Besser auf Trendwende, stabilere Volatilität und klare Unterstützung achten.",
    )


def build_decision_summary(
    score_result: ScoreResult,
    latest: pd.Series,
    supports: list[float],
    resistances: list[float],
    has_position: bool,
) -> tuple[str, str]:
    close = float(latest["Close"])
    rsi = latest_value(latest, "RSI_14")
    macd = latest_value(latest, "MACD")
    signal = latest_value(latest, "MACD_Signal")
    sma_50 = latest_value(latest, "SMA_50")
    sma_200 = latest_value(latest, "SMA_200")
    volatility = latest_value(latest, "Volatility")
    volume = latest_value(latest, "Volume")
    volume_avg = latest_value(latest, "Volume_SMA_20")

    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None
    support_distance = (close - nearest_support) / close if nearest_support else None
    resistance_room = (nearest_resistance - close) / close if nearest_resistance else None

    macd_positive = macd is not None and signal is not None and macd > signal
    macd_negative = macd is not None and signal is not None and macd < signal
    trend_positive = sma_50 is not None and close > sma_50 and (sma_200 is None or sma_50 >= sma_200)
    trend_negative = sma_50 is not None and close < sma_50 and (sma_200 is None or sma_50 <= sma_200)
    near_support = support_distance is not None and 0 <= support_distance <= 0.05
    enough_room = resistance_room is None or resistance_room >= 0.06
    high_volatility = volatility is not None and volatility > 0.45
    volume_confirms = volume is not None and volume_avg is not None and volume_avg > 0 and volume >= volume_avg
    overbought = rsi is not None and rsi > 70
    oversold = rsi is not None and rsi < 30

    support_label = format_currency(nearest_support) if nearest_support else "keine klare Unterstützung"
    resistance_label = format_currency(nearest_resistance) if nearest_resistance else "kein klarer Widerstand"
    sma50_label = format_currency(sma_50) if sma_50 is not None else "kein 50er-Durchschnitt"

    if score_result.score >= 8 and trend_positive and macd_positive and not overbought and enough_room:
        title = "Kaufen in Tranchen"
        buy_line = (
            f"Kauf jetzt in 2 bis 3 Tranchen ist technisch vertretbar. Erste Tranche nahe dem aktuellen Kurs oder bei Rücksetzer Richtung {support_label}; "
            f"zweite Tranche erst, wenn der Kurs Stärke zeigt und nicht unter {sma50_label} fällt; letzte Tranche nur bei Ausbruch über {resistance_label} mit bestätigendem Volumen."
        )
    elif score_result.score >= 6 and trend_positive and not overbought:
        title = "Halten, Nachkauf nur an klarer Marke"
        buy_line = (
            f"Nicht aggressiv kaufen. Nachkauf erst bei Rücksetzer an {support_label} mit Stabilisierung oder bei Ausbruch über {resistance_label}. "
            "Warum: Der Trend ist brauchbar, aber der Score ist nicht stark genug für einen vollen Sofortkauf."
        )
    elif score_result.score >= 4:
        title = "Nicht kaufen, warten"
        buy_line = (
            f"Kauf erst ab Bestätigung: MACD muss über die Signal-Linie drehen, der Kurs sollte {support_label} verteidigen oder {resistance_label} mit Volumen überwinden. "
            "Bis dahin ist das Chance-Risiko-Verhältnis technisch nicht sauber genug."
        )
    elif oversold and near_support:
        title = "Noch nicht kaufen, Stabilisierung abwarten"
        buy_line = (
            f"RSI ist überverkauft und der Kurs liegt nahe {support_label}. Das kann eine Gegenbewegung bringen, ist aber allein kein Kaufsignal. "
            "Kaufen erst, wenn der Kurs nicht weiter fällt und MACD oder Volumen eine Stabilisierung bestätigen."
        )
    else:
        title = "Nicht kaufen"
        buy_line = (
            "Neue Käufe sind technisch aktuell nicht sinnvoll. Es fehlen Trendbestätigung, Momentum oder eine saubere Unterstützungszone. "
            f"Erst wieder interessant bei Rückeroberung des 50er-Durchschnitts ({sma50_label}) oder einem bestätigten Ausbruch über {resistance_label}."
        )

    if has_position:
        if score_result.score < 4 and trend_negative and (macd_negative or high_volatility):
            position_line = (
                f"Bestehende Position: Teilverkauf oder Risikoreduzierung ist technisch sinnvoll. Grund: schwacher Score, Kurs unter dem 50er-Durchschnitt und negatives Momentum/Risiko. "
                f"Spätestens bei weiterem Bruch unter {support_label} wäre die technische Lage klar schwach."
            )
        elif score_result.score < 6:
            position_line = (
                f"Bestehende Position: Halten nur defensiv. Kein Nachkauf. Technisch kritisch wird es bei Schlusskurs unter {support_label}; besser wird es erst über {sma50_label} oder bei positivem MACD-Signal."
            )
        else:
            position_line = (
                "Bestehende Position: Halten ist technisch vertretbar. Teilgewinne können nahe Widerständen sinnvoll sein, Nachkäufe nur an den genannten Marken."
            )
    else:
        position_line = "Ohne bestehende Position: Keine Eile. Der Einstieg sollte nur an den genannten Marken erfolgen, nicht aus FOMO."

    reasons = []
    reasons.append(f"Score: {score_result.score}/10.")
    reasons.append("Trend positiv." if trend_positive else "Trend nicht klar positiv.")
    reasons.append("MACD positiv." if macd_positive else "MACD noch nicht positiv.")
    if rsi is not None:
        reasons.append(f"RSI: {rsi:.1f}.")
    if near_support:
        reasons.append(f"Kurs nahe Unterstützung {support_label}.")
    if nearest_resistance:
        reasons.append(f"Nächster Widerstand: {resistance_label}.")
    if high_volatility:
        reasons.append("Volatilität hoch.")
    if volume_confirms:
        reasons.append("Volumen bestätigt die Bewegung.")

    html = f"""
    <div class="decision-box">
        <div class="decision-title">{title}</div>
        <div class="decision-section"><strong>Konkrete Empfehlung:</strong> {buy_line}</div>
        <div class="decision-section"><strong>Halten / Verkaufen:</strong> {position_line}</div>
        <div class="decision-section"><strong>Warum:</strong> {" ".join(reasons)}</div>
    </div>
    """
    return title, html


def render_analysis_card(title: str, status: str, explanation: str) -> None:
    st.markdown(
        f"""
        <div class="analysis-card">
            <div class="analysis-card-title">{title}</div>
            <div class="analysis-card-status">{status}</div>
            <div class="analysis-card-text">{explanation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")

    st.markdown(
        """
        <style>
        .recommendation-box {
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 8px;
            padding: 18px 20px;
            background: rgba(15, 23, 42, 0.35);
            min-height: 118px;
        }
        .recommendation-label, .analysis-card-title, .score-label {
            color: #9ca3af;
            font-size: 0.9rem;
            margin-bottom: 4px;
        }
        .recommendation-value {
            font-size: clamp(1.8rem, 4vw, 3.2rem);
            font-weight: 700;
            line-height: 1.08;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .recommendation-help, .analysis-card-text, .score-text {
            color: #d1d5db;
            font-size: 0.98rem;
            line-height: 1.45;
            margin-top: 8px;
        }
        .analysis-card {
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 8px;
            padding: 14px 16px;
            background: rgba(15, 23, 42, 0.28);
            min-height: 118px;
            margin-bottom: 12px;
        }
        .analysis-card-status {
            font-size: 1.25rem;
            font-weight: 650;
            line-height: 1.2;
        }
        .score-row {
            border-bottom: 1px solid rgba(148, 163, 184, 0.18);
            padding: 10px 0;
        }
        .decision-box {
            border: 1px solid rgba(34, 197, 94, 0.35);
            border-radius: 8px;
            padding: 20px 22px;
            background: rgba(15, 23, 42, 0.42);
            margin: 12px 0 18px 0;
        }
        .decision-title {
            font-size: clamp(2rem, 5vw, 3.4rem);
            font-weight: 750;
            line-height: 1.05;
            margin-bottom: 14px;
        }
        .decision-section {
            font-size: 1.05rem;
            line-height: 1.55;
            margin-top: 10px;
            color: #e5e7eb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(APP_TITLE)
    st.warning(DISCLAIMER)
    st.caption("Keine Broker-Anbindung. Keine Kauf- oder Verkaufsautomatisierung. Die letzte Entscheidung trifft immer der Nutzer.")

    with st.sidebar:
        st.header("Analyse")
        query = st.text_input("Asset-Name oder Ticker", value="Nvidia", placeholder="z. B. Xiaomi, PLTR, Bitcoin")
        period_label = st.selectbox("Zeitraum", list(PERIOD_OPTIONS), index=2)
        interval = st.selectbox("Intervall", INTERVAL_OPTIONS, index=4)
        refresh_label = st.selectbox("Auto-Refresh", list(REFRESH_OPTIONS), index=0)
        currency_mode = st.selectbox("Währungsanzeige", ["EUR + Originalwährung", "Nur EUR"], index=0)
        manual_asset_type = st.selectbox("Asset-Typ", ["Automatisch", "Aktie", "ETF", "Krypto", "Unbekannt"], index=0)
        position_status = st.radio("Aktuelle Position", ["Ich habe keine Position", "Ich halte bereits"], index=0)
        portfolio_enabled = st.toggle("Portfolio in Bewertung einbeziehen", value=False)
        beginner_mode = st.toggle("Anfänger-Modus", value=True)

        candidates = find_ticker_candidates(query)
        candidate_labels = [format_candidate(candidate) for candidate in candidates]
        selected_label = st.selectbox("Gefundene Yahoo-Finance-Treffer", candidate_labels or [""])
        selected_candidate_data = candidates[candidate_labels.index(selected_label)] if selected_label and candidate_labels else None
        if selected_candidate_data:
            st.caption(
                f"{selected_candidate_data['name']} | Ticker: {selected_candidate_data['symbol']} | Börse: {selected_candidate_data['exchange']}"
            )
        elif query.strip():
            st.error("Kein passender Yahoo-Finance-Treffer gefunden.")
            suggestions = similar_ticker_suggestions(query)
            if suggestions:
                st.info("Ähnliche bekannte Treffer: " + ", ".join(format_candidate(item) for item in suggestions))

        history = load_search_history()
        selected_history_data = None
        if history:
            with st.expander("Zuletzt erfolgreiche Suchen", expanded=False):
                history_labels = [
                    f"{item.get('name', item.get('symbol'))} | {item.get('symbol')} | {item.get('exchange', 'Daten nicht verfügbar')}"
                    for item in history[:8]
                ]
                selected_history_label = st.selectbox("Schnellwahl aus Historie", [""] + history_labels)
                if selected_history_label:
                    selected_history_data = history[history_labels.index(selected_history_label)]
                    st.caption(f"Aus Historie übernommen: {selected_history_data.get('symbol', '')}")
                for item in history[:5]:
                    st.write(f"{item.get('name', item.get('symbol'))} | {item.get('symbol')} | {item.get('exchange', 'Daten nicht verfügbar')}")
        manual_symbol = st.text_input(
            "Manueller Ticker überschreibt Auswahl",
            value="",
            placeholder="z. B. NVDA, BTC-EUR, EUNL.DE",
        )
        analyze = st.button("Analysieren", type="primary", use_container_width=True)

    refresh_seconds = REFRESH_OPTIONS[refresh_label]
    if refresh_seconds:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_seconds}'>", unsafe_allow_html=True)
        st.caption(f"Auto-Refresh aktiv: Die Seite lädt alle {refresh_seconds} Sekunden neu. Yahoo-Finance-Daten können verzögert sein.")

    if manual_symbol.strip():
        symbol = manual_symbol.strip().upper()
        selected_candidate_data = ticker_candidate(symbol, source="Manuelle Eingabe")
    elif selected_history_data:
        symbol = str(selected_history_data.get("symbol", "")).upper()
        selected_candidate_data = {
            "symbol": symbol,
            "name": selected_history_data.get("name", symbol),
            "exchange": selected_history_data.get("exchange", "Daten nicht verfügbar"),
            "currency": selected_history_data.get("currency", ""),
            "quote_type": selected_history_data.get("quote_type", ""),
            "source": "Suchhistorie",
        }
    else:
        symbol = str(selected_candidate_data.get("symbol", "")).upper() if selected_candidate_data else ""
    if not query.strip():
        st.info("Gib links ein Asset oder einen Yahoo-Finance-Ticker ein.")
        return

    if not symbol:
        st.info("Kein Ticker gefunden. Bitte gib einen Yahoo-Finance-Ticker manuell ein.")
        return

    if analyze or symbol:
        selected_period = PERIOD_OPTIONS[period_label]
        if interval in {"1m", "5m", "15m"} and selected_period not in {"1d", "5d", "1mo"}:
            selected_period = "5d"
            st.info("Intraday-Daten sind bei Yahoo Finance nur für kürzere Zeiträume sinnvoll. Der Zeitraum wurde für diesen Abruf auf 5 Tage gesetzt.")
        with st.spinner(f"Lade Kursdaten für {symbol}..."):
            try:
                raw_data = load_price_data(symbol, selected_period, interval)
            except RuntimeError as exc:
                st.error(str(exc))
                return

        if raw_data.empty or "Close" not in raw_data:
            st.error("Für diesen Ticker konnten keine Kursdaten geladen werden. Prüfe das Yahoo-Finance-Symbol oder probiere eine andere Börse.")
            return

        df = calculate_indicators(raw_data, interval)
        supports = local_levels(df["Low"], "support")
        resistances = local_levels(df["High"], "resistance")
        score_result = calculate_score_v2(df, supports, resistances)
        latest = df.iloc[-1]
        has_position = position_status == "Ich halte bereits"
        close_value = float(latest["Close"])
        ticker_info = load_ticker_info(symbol)
        asset_identity = build_asset_identity(symbol, ticker_info, selected_candidate_data)
        original_currency = asset_identity["currency"]
        fx_rate, fx_ticker = get_fx_rate_to_eur(original_currency)
        save_successful_search(query, asset_identity)
        auto_profile = detect_asset_type(symbol, ticker_info)
        asset_profile = override_asset_profile(auto_profile, manual_asset_type)
        market_phase = detect_market_phase(df)
        risk_reward = calculate_risk_reward(close_value, supports, resistances)
        technical = technical_module(score_result, market_phase)
        macro = score_macro()
        asset_quality = score_asset_quality(symbol, asset_profile, df)
        fundamentals = asset_quality
        news = score_news(symbol)
        buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, asset_profile)
        research_pack = build_research_pack(
            symbol,
            asset_profile,
            asset_identity,
            df,
            supports,
            resistances,
            market_phase,
            risk_reward,
            asset_quality,
            buy_signal,
            macro,
            news,
            original_currency,
            fx_rate,
            currency_mode,
        )
        portfolio_result = evaluate_portfolio(symbol, portfolio_enabled, buy_signal.score, asset_profile)
        data_source_warnings = build_data_source_warnings(
            ticker_info,
            original_currency,
            fx_rate,
            fx_ticker,
            news,
            macro,
        )
        calibration_status, calibration_rows = calibration_status_rows(load_trade_history())
        action_title, action_html = final_recommendation_v2(
            asset_quality,
            buy_signal,
            portfolio_result,
            market_phase,
            risk_reward,
            research_pack.action,
            research_pack.confidence,
        )
        score_result.recommendation = action_title
        display_df = converted_price_frame(df, fx_rate)
        display_supports = converted_levels(supports, fx_rate)
        display_resistances = converted_levels(resistances, fx_rate)
        quality_label, quality_summary, quality_highlights = data_quality_status(research_pack.data_quality, data_source_warnings)

        st.subheader(f"{asset_identity['name']} · technische Analyse")
        st.caption(f"Ticker: {asset_identity['symbol']} | Börse: {asset_identity['exchange']}")
        if original_currency == "EUR":
            st.caption("Originalwährung: EUR. Keine Umrechnung nötig.")
        elif fx_rate is None:
            st.warning(f"Originalwährung: {original_currency}. EUR-Umrechnung aktuell nicht verfügbar ({fx_ticker}). Preise werden in Originalwährung angezeigt.")
        else:
            st.caption(f"Originalwährung: {original_currency}. Verwendeter Wechselkurs: 1 {original_currency} = {fx_rate:.4f} EUR ({fx_ticker}).")
        st.caption("Portfolio-Modus: AN" if portfolio_result.enabled else "Portfolio-Modus: AUS")
        if portfolio_result.enabled and not portfolio_result.available:
            st.warning(portfolio_result.summary)
        quality_score_text = "n/a" if research_pack.data_quality.score is None else f"{research_pack.data_quality.score:.1f}/10"
        quality_message = f"Datenqualität {quality_label} ({quality_score_text}): {quality_summary}"
        if quality_label == "Grün":
            st.success(quality_message)
        elif quality_label == "Gelb":
            st.warning(quality_message)
        else:
            st.error(quality_message)
        st.caption("Wichtigste Datenhinweise: " + " | ".join(quality_highlights))
        with st.expander("Details zu Datenqualität und externen Quellen", expanded=False):
            st.markdown("**Datenqualitäts-Check**")
            for detail in research_pack.data_quality.details:
                st.write(f"- {detail}")
            if data_source_warnings:
                st.markdown("**Externe Datenquellen**")
                for warning in data_source_warnings:
                    st.write(f"- {warning}")
        st.markdown(action_html, unsafe_allow_html=True)
        if st.button("Analyse als Forward-Test speichern", use_container_width=True):
            record = build_forward_test_record(
                symbol,
                asset_identity,
                asset_profile,
                latest,
                asset_quality,
                buy_signal,
                market_phase,
                risk_reward,
                research_pack,
                portfolio_result,
            )
            if save_forward_test(record):
                st.success("Forward-Test gespeichert. Die Datei `forward_tests.json` bleibt lokal und löst keine Order aus.")
            else:
                st.error("Forward-Test konnte nicht gespeichert werden.")
        if beginner_mode:
            buy_answer, buy_text = beginner_buy_answer(buy_signal.score, action_title)
            st.markdown(
                f"""
                <div class="decision-box">
                    <div class="recommendation-label">Würde ich heute kaufen?</div>
                    <div class="decision-title">{buy_answer}</div>
                    <div class="decision-section">{buy_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption(f"Asset-Typ: {asset_profile.asset_type} ({asset_profile.quote_type}). {asset_profile.summary}")
        st.info(f"Marktphase: {market_phase.phase}. {market_phase.summary}")

        metric_cols = st.columns(7 if portfolio_result.enabled else 6)
        metric_cols[0].metric("Aktueller Kurs", format_display_money(float(latest["Close"]), original_currency, fx_rate, currency_mode))
        metric_cols[1].metric("Datenqualität", f"{quality_label} {quality_score_text}")
        metric_cols[2].metric("Asset-Qualität", f"{asset_quality.score}/10")
        metric_cols[3].metric("Kaufsignal", f"{buy_signal.score}/10")
        if portfolio_result.enabled:
            metric_cols[4].metric("Depot-Effekt", "n/a" if portfolio_result.score is None else f"{portfolio_result.score}/10")
            metric_cols[5].metric("CRV", "n/a" if risk_reward.ratio is None else f"{risk_reward.ratio:.2f}")
            metric_cols[6].metric("RSI 14", "n/a" if pd.isna(latest["RSI_14"]) else f"{latest['RSI_14']:.1f}")
        else:
            metric_cols[4].metric("CRV", "n/a" if risk_reward.ratio is None else f"{risk_reward.ratio:.2f}")
            metric_cols[5].metric("RSI 14", "n/a" if pd.isna(latest["RSI_14"]) else f"{latest['RSI_14']:.1f}")

        level_cols = st.columns(2)
        level_cols[0].metric("Wichtigste Unterstützung", "n/a" if not supports else format_display_money(supports[0], original_currency, fx_rate, currency_mode))
        level_cols[1].metric("Wichtigster Widerstand", "n/a" if not resistances else format_display_money(resistances[0], original_currency, fx_rate, currency_mode))

        prob_cols = st.columns(len(market_phase.probabilities))
        for col, (name, probability) in zip(prob_cols, market_phase.probabilities.items()):
            col.metric(name, f"{probability}%")

        st.markdown("**Professionelle Research-Scores**")
        research_cols = st.columns(4)
        for idx, module in enumerate(research_pack.modules):
            value = "n/a" if module.score is None else f"{module.score:.1f}/10"
            research_cols[idx % 4].metric(module.name, value)

        if beginner_mode:
            with st.expander("Anfänger-Erklärungen anzeigen", expanded=True):
                for title, meaning, interpretation in beginner_explanations(
                    latest,
                    supports,
                    resistances,
                    asset_profile,
                    market_phase,
                    risk_reward,
                    fundamentals,
                    news,
                    macro,
                    technical,
                    portfolio_result,
                    asset_quality,
                    buy_signal,
                    research_pack.data_quality,
                    quality_label,
                    quality_highlights,
                    original_currency,
                    fx_rate,
                    currency_mode,
                ):
                    render_analysis_card(title, meaning, interpretation)

        chart_currency = "EUR" if fx_rate is not None else original_currency
        st.plotly_chart(render_price_chart(display_df, display_supports, display_resistances, chart_currency), use_container_width=True)

        with st.expander("Professionelles Research-Modul anzeigen", expanded=True):
            st.markdown("**Datenqualitäts-Check**")
            st.write(research_pack.data_quality.summary)
            for detail in research_pack.data_quality.details:
                st.write(f"- {detail}")
            if data_source_warnings:
                st.markdown("**Eingeschränkte externe Datenquellen**")
                for warning in data_source_warnings:
                    st.write(f"- {warning}")

            st.markdown("**Modul-Scores**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Modul": module.name,
                            "Score": "n/a" if module.score is None else f"{module.score:.1f}/10",
                            "Einordnung": score_band(module.score, is_warning_score_module(module)),
                            "Kurzfazit": module.summary,
                            "Praktische Bedeutung": research_score_interpretation(module),
                        }
                        for module in research_pack.modules
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

            if beginner_mode:
                st.markdown("**Einfache Erklärung der Research-Scores**")
                for module in research_pack.modules:
                    render_analysis_card(module.name, module.beginner, f"{module.summary} {research_score_interpretation(module)}")

            st.markdown("**Institutionelle Research-Module**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Modul": module.name,
                            "Score": "n/a" if module.score is None else f"{module.score:.1f}/10",
                            "Einordnung": score_band(module.score, is_warning_score_module(module)),
                            "Kurzfazit": module.summary,
                            "Praktische Bedeutung": research_score_interpretation(module),
                        }
                        for module in research_pack.institutional_modules
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Details zu institutionellen Modulen", expanded=False):
                for module in research_pack.institutional_modules:
                    render_analysis_card(module.name, "n/a" if module.score is None else f"{module.score:.1f}/10 - {score_band(module.score, is_warning_score_module(module))}", f"{module.beginner} {research_score_interpretation(module)}")
                    for detail in module.details:
                        st.write(f"- {detail}")

            st.markdown("**Vertrauen in Analyse**")
            render_analysis_card(
                research_pack.confidence.name,
                "n/a" if research_pack.confidence.score is None else f"{research_pack.confidence.score:.1f}/10",
                research_pack.confidence.summary,
            )
            for detail in research_pack.confidence.details:
                st.write(f"- {detail}")

            st.markdown("**Was könnte diese Analyse widerlegen?**")
            for factor in research_pack.uncertainty_factors[:5]:
                st.write(f"- {factor}")

            st.markdown("**Bull / Base / Bear-Szenarien**")
            st.dataframe(pd.DataFrame(research_pack.scenarios), use_container_width=True, hide_index=True)

            st.markdown("**Nachkaufzonen**")
            st.dataframe(pd.DataFrame(research_pack.buy_zones), use_container_width=True, hide_index=True)

            st.markdown("**Research-Fazit**")
            for title, value in research_pack.conclusion.items():
                st.markdown(f"**{title}**")
                if isinstance(value, list):
                    for item in value:
                        st.write(f"- {item}")
                else:
                    st.write(value)

        with st.expander("Analyse-Details anzeigen", expanded=False):
            st.markdown("**Score-Transparenz**")
            transparency_rows = [
                {"Bereich": "Asset-Qualität", "Score": f"{asset_quality.score:.1f}/10", "Was wird bewertet?": "Langfristige Qualität des Assets", "Begründung": asset_quality.summary},
                {"Bereich": "Kaufsignal", "Score": f"{buy_signal.score:.1f}/10", "Was wird bewertet?": "Ob jetzt ein guter Einstieg sein könnte", "Begründung": buy_signal.summary},
            ]
            if portfolio_result.enabled:
                transparency_rows.append(
                    {"Bereich": "Depot-Effekt", "Score": "n/a" if portfolio_result.score is None else f"{portfolio_result.score:.1f}/10", "Was wird bewertet?": "Nur Portfolio-Auswirkung", "Begründung": portfolio_result.summary}
                )
            st.dataframe(
                pd.DataFrame(transparency_rows),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("**Gewichtungen nach Asset-Typ**")
            st.caption("Diese Gewichtungen erklären den Research-/Gesamtkontext. Das finale Kaufsignal bleibt separat und bewertet den aktuellen Einstiegszeitpunkt.")
            st.dataframe(
                pd.DataFrame(score_weight_rows(asset_profile)),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("**Kaufsignal-Gewichtung**")
            st.write("Das Kaufsignal nutzt den Technik-Score mit 70 %, den CRV-Score mit 20 % und danach begrenzte Zu- oder Abschläge für Marktphase, RSI, MACD und asset-typische Volatilität. Asset-Qualität und Depot-Effekt fließen nicht ein.")

            st.markdown("**Kalibrierungsstatus**")
            st.write(calibration_status)
            st.dataframe(
                pd.DataFrame(calibration_rows),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("**Technik-Score erklärt**")
            for name, points, text in score_result.breakdown:
                st.markdown(
                    f"""
                    <div class="score-row">
                        <div class="score-label">{name}: {points:g} Punkte</div>
                        <div class="score-text">{text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            info_cols = st.columns(2)
            with info_cols[0]:
                st.markdown("**Wichtigste Unterstützungen**")
                if supports:
                    st.write(
                        pd.DataFrame(
                            {
                                "Zone": ["Wichtigste Unterstützung", "Zweite Unterstützung", "Dritte Unterstützung"][: len(supports)],
                                "Kurs": [format_display_money(level, original_currency, fx_rate, currency_mode) for level in supports],
                                "Abstand": [percent_text((level - close_value) / close_value) for level in supports],
                            }
                        )
                    )
                else:
                    st.write("Keine belastbaren lokalen Unterstützungen im gewählten Zeitraum gefunden.")

            with info_cols[1]:
                st.markdown("**Wichtigste Widerstände**")
                if resistances:
                    st.write(
                        pd.DataFrame(
                            {
                                "Zone": ["Wichtigster Widerstand", "Zweiter Widerstand", "Dritter Widerstand"][: len(resistances)],
                                "Kurs": [format_display_money(level, original_currency, fx_rate, currency_mode) for level in resistances],
                                "Abstand": [percent_text((level - close_value) / close_value) for level in resistances],
                            }
                        )
                    )
                else:
                    st.write("Keine belastbaren lokalen Widerstände im gewählten Zeitraum gefunden.")

            st.markdown("**Risiko-Rendite-Bewertung**")
            st.write(
                pd.DataFrame(
                    [
                        {
                            "Risiko bis Unterstützung": percent_text(risk_reward.risk_pct),
                            "Potenzial bis Widerstand": percent_text(risk_reward.reward_pct),
                            "CRV": "n/a" if risk_reward.ratio is None else f"{risk_reward.ratio:.2f}",
                            "CRV-Score": f"{risk_reward.score:.1f}/10",
                        }
                    ]
                )
            )

            if portfolio_result.enabled:
                st.markdown("**Depot-Effekt**")
                st.write(portfolio_result.summary)
                for detail in portfolio_result.details:
                    st.write(f"- {detail}")

            st.markdown("**Kurze Begründung**")
            for reason in score_result.reasons:
                st.write(f"- {reason}")

            st.markdown("**Asset-Qualität**")
            for detail in fundamentals.details:
                st.write(f"- {detail}")

            st.markdown("**News-Sentiment**")
            st.write(news.summary)
            for detail in news.details:
                st.write(f"- {detail}")

            st.markdown("**Makro-Modul**")
            st.write(macro.summary)
            for detail in macro.details:
                st.write(f"- {detail}")

            close_value = float(latest["Close"])
            rsi_status, rsi_text = rsi_explanation(latest_value(latest, "RSI_14"))
            macd_status, macd_text = macd_explanation(latest_value(latest, "MACD"), latest_value(latest, "MACD_Signal"))
            trend_status, trend_text = trend_explanation(close_value, latest_value(latest, "SMA_50"), latest_value(latest, "SMA_200"))
            level_status, level_text = level_explanation(close_value, supports, resistances, original_currency, fx_rate, currency_mode)
            volatility_status, volatility_text = volatility_explanation(latest_value(latest, "Volatility"))

            st.markdown("**Was bedeutet das für mich als Anleger?**")
            analysis_cols = st.columns(2)
            with analysis_cols[0]:
                render_analysis_card("RSI 14", rsi_status, rsi_text)
                render_analysis_card("Trend", trend_status, trend_text)
                render_analysis_card("Unterstützung und Widerstand", level_status, level_text)
            with analysis_cols[1]:
                render_analysis_card("MACD", macd_status, macd_text)
                render_analysis_card("Volatilität", volatility_status, volatility_text)
                render_analysis_card(
                    "Konkreter Plan",
                    action_title,
                    str(research_pack.conclusion.get("Was wäre mein konkreter Plan?", action_title)),
                )

        with st.expander("Weitere Charts anzeigen", expanded=False):
            chart_cols = st.columns(2)
            with chart_cols[0]:
                rsi_fig = render_line_chart(df, ["RSI_14"], "RSI 14")
                rsi_fig.add_hline(y=70, line_dash="dot", line_color="#dc2626")
                rsi_fig.add_hline(y=30, line_dash="dot", line_color="#16a34a")
                st.plotly_chart(rsi_fig, use_container_width=True)

            with chart_cols[1]:
                st.plotly_chart(render_line_chart(df, ["MACD", "MACD_Signal"], "MACD und Signal-Linie"), use_container_width=True)

            st.plotly_chart(render_volume_chart(df), use_container_width=True)

        with st.expander("Rohdaten und Indikatoren anzeigen"):
            st.dataframe(df.tail(250), use_container_width=True)


if __name__ == "__main__":
    main()
