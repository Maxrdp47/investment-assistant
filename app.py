from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from html import escape as html_escape
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from analysis_models import (
    AssetProfile,
    EtfFundamentalSnapshot,
    MarketPhase,
    ModuleScore,
    PortfolioResult,
    ResearchModule,
    ResearchPack,
    RiskReward,
    ScoreResult,
    StockFundamentalSnapshot,
)
from asset_search import (
    KNOWN_TICKER_NAMES,
    KNOWN_TICKERS,
    dedupe_candidates,
    format_candidate,
    looks_like_ticker,
    normalize_query,
    search_ticker_candidates,
    similar_ticker_suggestions,
    ticker_candidate,
)
from currency_utils import (
    convert_to_eur,
    converted_levels,
    converted_price_frame,
    format_currency,
    format_display_money,
    format_money,
)
from data_quality_analysis import build_data_source_warnings, data_quality_check, data_quality_status
from entry_plan import (
    build_buy_zones,
    recommendation_confidence_label,
    recommendation_horizon,
    recommendation_validity,
    research_action,
)
from forecast_calibration import DEFAULT_CALIBRATION_PATH, load_calibration_profile
from forecast_baselines import simple_trend_snapshot
from forecast_probabilities import build_raw_up_probability
from forecast_store import (
    DEFAULT_DATABASE_PATH,
    FORECAST_HORIZONS,
    FORECAST_LOGIC_VERSION,
    FORECAST_MODEL_ENTRY,
    FORECAST_MODEL_LABELS,
    forecast_operational_status,
    forecast_quality_rows,
    forecast_summary,
    recent_run_status,
)
from forecast_weekly_report import load_weekly_report
from future_potential_analysis import research_future_potential, research_priced_expectations
from fundamental_analysis import (
    data_missing,
    etf_fundamental_overview,
    etf_fundamental_snapshot,
    format_money_or_missing,
    format_percent_or_missing,
    score_etf_fundamentals,
    score_profitability_metric,
    score_stock_fundamentals,
    score_valuation_multiple,
    stock_fundamental_overview,
    stock_fundamental_snapshot,
)
from json_history_store import load_json_dict_list, save_json_dict_list
from portfolio_analysis import (
    evaluate_portfolio_data,
    load_portfolio_file as load_portfolio_document,
    normalize_symbol,
    portfolio_position_buy_price,
    portfolio_position_shares,
    portfolio_position_ticker,
    portfolio_positions,
    position_market_value as calculate_position_market_value,
)
from price_attractiveness import fundamental_context_since_high, price_attractiveness_context
from recommendation_synthesis import professional_decision, synthesize_investment_recommendation
from research_knowledge.ui import render_research_knowledge_base
from scenario_analysis import (
    build_scenarios,
    numeric_scenario_levels,
    research_expected_value,
    scenario_probabilities,
)
from score_composition import score_from_optional, score_weight_rows, weighted_total_score
from swing_scanner import (
    DEFAULT_PREFILTER_THRESHOLDS,
    DEFAULT_SWING_RISK_POLICY,
    RISK_NOTICE,
    apply_portfolio_release_to_funnel,
    asset_type_bias_audit,
    execute_multistage_scan,
    internal_swing_settings,
    load_risk_acknowledgement,
    prefilter_thresholds_as_dict,
    risk_policy_as_dict,
    save_risk_acknowledgement,
    swing_portfolio_cluster_audit,
)
from swing_risk_engine import apply_swing_risk_engine
from swing_forward_statistics import (
    filter_swing_forward_archive_rows,
    swing_asset_failure_rows,
    swing_forward_asset_type_comparison,
    swing_learning_readiness,
    swing_rejection_control_statistics,
    swing_forward_statistics,
)
from swing_forward_store import (
    DEFAULT_SWING_FORWARD_DB_PATH,
    SWING_STRATEGY_VERSION,
    load_swing_forward_scans,
    load_swing_forward_signals,
    load_swing_rejection_controls,
    record_swing_forward_scan,
    swing_forward_store_audit,
)
from swing_paper_bot import (
    DEFAULT_SWING_PAPER_DB_PATH,
    derive_paper_position_state,
    load_paper_signals,
    paper_bot_store_audit,
)
from swing_shadow_live import (
    DEFAULT_SWING_SHADOW_DB_PATH,
    shadow_live_store_audit,
    shadow_paper_comparison,
)
from swing_strategy_freeze import (
    DEFAULT_STRATEGY_FREEZE_DB_PATH,
    strategy_freeze_store_audit,
)
from swing_trade_monitor import swing_market_context_from_daily_bars
from swing_walk_forward import (
    DEFAULT_SWING_WALK_FORWARD_DB_PATH,
    load_swing_walk_forward_cases,
    refresh_swing_walk_forward_forward_links,
    swing_walk_forward_archive_rows,
    swing_walk_forward_summary,
)
from swing_walk_forward_campaign import (
    campaign_jobs,
    campaign_status,
    load_campaign_config,
    load_campaign_state,
)
from swing_universe import (
    DEFAULT_SWING_UNIVERSE_PATH,
    SwingUniverseAsset,
    active_swing_assets,
    load_swing_universe,
)
from swing_user_store import (
    DEFAULT_SWING_USER_DB_PATH,
    SwingUserTradeDeviationConfirmationRequired,
    close_swing_user_trade,
    create_swing_user_trade,
    load_swing_user_trade_states,
    record_swing_user_partial_sale,
    swing_user_trade_guidance,
    tighten_swing_user_stop,
)
from technical_analysis import (
    calculate_indicators,
    calculate_risk_reward,
    clamp,
    detect_market_phase,
    local_levels,
    pct_distance,
    percent_text,
    value_or_none,
)
from trade_republic_reference import (
    TR_STATUS_NOT_TRADEABLE,
    TR_STATUS_OPTIONS,
    TR_STATUS_TRADEABLE,
    TR_STATUS_UNKNOWN,
    build_trade_republic_execution_plan,
    record_trade_republic_price,
    record_trade_republic_status,
    trade_republic_price,
    trade_republic_reference,
)
from trading_assistant import (
    DEFAULT_SWING_THRESHOLDS,
    SwingTradeThresholds,
    active_trade_snapshot,
    close_trade_record,
    evaluate_swing_trade,
    expire_paper_trade,
    open_trade_record,
    paper_trade_statistics,
    tighten_active_trade_stop,
    thresholds_as_dict,
    validate_traded_listing,
)
from valuation_analysis import research_valuation_score


APP_TITLE = "Investment-Assistent"
DISCLAIMER = "Dies ist keine Finanzberatung, sondern eine technische Analysehilfe."
PROJECT_ROOT = Path(__file__).resolve().parent
PRIVATE_HISTORY_DIR = Path(os.environ.get("INVESTMENT_ASSISTANT_HISTORY_DIR", PROJECT_ROOT))
YFINANCE_CACHE_DIR = PROJECT_ROOT / ".yfinance-cache"
PORTFOLIO_PATH = PROJECT_ROOT / "portfolio.json"
SEARCH_HISTORY_PATH = PRIVATE_HISTORY_DIR / "search_history.json"
TRADE_HISTORY_PATH = PRIVATE_HISTORY_DIR / "trade_history.json"
FORWARD_TEST_PATH = PRIVATE_HISTORY_DIR / "forward_tests.json"
DECISION_HISTORY_PATH = PRIVATE_HISTORY_DIR / "decision_history.json"
PREDICTION_HISTORY_PATH = PRIVATE_HISTORY_DIR / "prediction_history.json"
BACKTEST_HISTORY_PATH = PRIVATE_HISTORY_DIR / "backtest_history.json"
RESEARCH_KNOWLEDGE_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_RESEARCH_KB_DB",
        PROJECT_ROOT / "runtime" / "research_knowledge.sqlite3",
    )
)
SWING_RISK_ACK_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_SWING_RISK_ACK_PATH",
        PROJECT_ROOT / "runtime" / "preferences" / "swing_risk_acknowledgement.json",
    )
)
try:
    YFINANCE_CACHE_DIR.mkdir(exist_ok=True)
except OSError:
    YFINANCE_CACHE_DIR = Path(tempfile.gettempdir()) / "investment-assistent-yfinance-cache"
    YFINANCE_CACHE_DIR.mkdir(exist_ok=True)
yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))

PERIOD_OPTIONS = {
    "Heute": "1d",
    "5 Tage": "5d",
    "1 Monat": "1mo",
    "3 Monate": "3mo",
    "6 Monate": "6mo",
    "1 Jahr": "1y",
    "5 Jahre": "5y",
    "Max": "max",
}

PERIOD_HISTORY_LABELS = {
    "1d": "1 Tag",
    "5d": "5 Tage",
    "1mo": "1 Monat",
    "6mo": "6 Monate",
    "1y": "1 Jahr",
    "5y": "5 Jahre",
    "max": "maximale verfügbare Historie",
}

INTERVAL_OPTIONS = ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"]
REFRESH_OPTIONS = {
    "Aus": 0,
    "30 Sekunden": 30,
    "1 Minute": 60,
    "5 Minuten": 300,
}
TRACKING_PERIODS = {
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "12m": 365,
}


def empty_review_schedule() -> dict[str, None]:
    return {label: None for label in TRACKING_PERIODS}


def ensure_review_schedule(record: dict) -> dict:
    review_after = record.get("review_after")
    if not isinstance(review_after, dict):
        review_after = {}
        record["review_after"] = review_after
    for label in TRACKING_PERIODS:
        review_after.setdefault(label, None)
    return review_after

@st.cache_data(ttl=60 * 60)
def find_ticker_candidates(query: str) -> list[dict]:
    return search_ticker_candidates(query, yf.Search)


def load_search_history() -> list[dict]:
    return load_json_dict_list(SEARCH_HISTORY_PATH)


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
    save_json_dict_list(SEARCH_HISTORY_PATH, history[:12])


def trade_record_key(record: dict) -> tuple[str, str, str]:
    raw_date = record.get("Datum") or record.get("created_at") or ""
    try:
        day = pd.Timestamp(raw_date).strftime("%Y-%m-%d")
    except Exception:
        day = str(raw_date)[:10]
    return (
        str(record.get("Ticker") or record.get("symbol") or "").upper(),
        str(record.get("Richtung") or record.get("direction") or ""),
        day,
    )


def normalize_trade_record(record: dict) -> dict:
    normalized = dict(record)
    field_aliases = {
        "Datum": ["created_at", "date"],
        "Ticker": ["symbol"],
        "Richtung": ["direction"],
        "Einstieg": ["entry_price"],
        "Zielzone": ["target"],
        "Stop-Zone": ["stop"],
        "Asset-Typ": ["asset_type"],
        "Ähnliche Setups": ["similar_setups"],
        "Treffer ähnliche Setups": ["similar_setup_hits"],
        "Trefferquote ähnliche Setups": ["similar_setup_hit_rate"],
        "Historienstatus": ["history_status"],
        "Historienhinweis": ["history_summary"],
        "Kalibrierungskontext": ["calibration_context"],
        "Kalibrierungshinweis": ["calibration_hint"],
        "Setup-ID": ["setup_id"],
        "Setup-Typ": ["setup_type"],
        "Gültig bis": ["valid_until"],
        "Maximaler Einstieg EUR": ["max_entry_eur"],
        "Stop-Loss EUR": ["stop_eur"],
        "Kursziel 1 EUR": ["target_1_eur"],
        "Kursziel 2 EUR": ["target_2_eur"],
        "Orderplan": ["order_plan"],
        "Ordertyp": ["order_type"],
        "Aktivierung EUR": ["activation_price_eur"],
        "Limitpreis EUR": ["limit_price_eur"],
        "Frühester Einstieg": ["earliest_entry_day"],
        "Plan-Fingerabdruck": ["plan_fingerprint"],
        "Initialer Stop EUR": ["initial_stop_eur"],
        "Stop-Vertrag Version": ["stop_contract_version"],
    }
    for canonical, aliases in field_aliases.items():
        if canonical in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[canonical] = normalized[alias]
                break

    normalized.setdefault("review_after", empty_review_schedule())
    normalized.setdefault("Ähnliche Setups", 0)
    normalized.setdefault("Treffer ähnliche Setups", 0)
    normalized.setdefault("Trefferquote ähnliche Setups", None)
    normalized.setdefault("Historienstatus", "Datenbasis zu klein")
    normalized.setdefault("Historienhinweis", "Ähnliche historische Setups: 0. Datenbasis zu klein; Trefferquote wird nicht als belastbar gewertet.")
    normalized.setdefault("Kalibrierungskontext", "Daten nicht verfügbar")
    normalized.setdefault("Kalibrierungshinweis", "Keine gespeicherte Backtest-Historie vorhanden; Trade Journal ändert keine Einschätzung.")
    normalized.setdefault("Status", "Paper")
    normalized.setdefault("Hinweis", "Nur Analyse und Dokumentation. Keine automatische Kauf- oder Verkaufsfunktion.")
    return normalized


def append_trade_records(records: list[dict]) -> bool:
    if not records:
        return False
    history = load_trade_history()
    existing_keys = {trade_record_key(record) for record in history}
    new_records = []
    for record in records:
        normalized_record = normalize_trade_record(record)
        key = trade_record_key(normalized_record)
        if not key[0] or key in existing_keys:
            continue
        new_records.append(normalized_record)
        existing_keys.add(key)
    if not new_records:
        return True
    history = new_records + history
    return save_json_dict_list(TRADE_HISTORY_PATH, history)


def auto_document_trade_setups(setups: list[dict]) -> tuple[int, str]:
    if not setups:
        return 0, "Keine Trading-Setups zur Dokumentation vorhanden."
    before = len(load_trade_history())
    if not append_trade_records(setups):
        return 0, "Trading-Setups konnten nicht lokal dokumentiert werden."
    after = len(load_trade_history())
    added = max(after - before, 0)
    if added == 0:
        return 0, "Trading-Setups waren bereits im heutigen Trade Journal dokumentiert."
    return added, f"{added} Trading-Setups automatisch lokal dokumentiert. Keine Order, keine Broker-Anbindung."


def load_trade_history() -> list[dict]:
    return load_json_dict_list(TRADE_HISTORY_PATH)


def load_forward_tests() -> list[dict]:
    return load_json_dict_list(FORWARD_TEST_PATH)


def load_backtest_history() -> list[dict]:
    return load_json_dict_list(BACKTEST_HISTORY_PATH)


def save_backtest_result(record: dict) -> bool:
    history = load_backtest_history()
    history.insert(0, record)
    return save_json_dict_list(BACKTEST_HISTORY_PATH, history)


def trade_direction_multiplier(direction: str) -> int:
    return -1 if "Short" in str(direction) else 1


def trade_best_alternative(direction: str, return_pct: float) -> dict:
    chosen_label = "Short / Absicherung" if trade_direction_multiplier(direction) < 0 else "Long"
    alternatives = {
        "Long": return_pct if chosen_label == "Long" else -return_pct,
        "Short / Absicherung": return_pct if chosen_label == "Short / Absicherung" else -return_pct,
        "Beobachten": 0.0,
    }
    best_label, best_return = max(alternatives.items(), key=lambda item: item[1])
    chosen_return = alternatives[chosen_label]
    return {
        "chosen_action": chosen_label,
        "chosen_return_pct": round(chosen_return, 2),
        "best_alternative": best_label,
        "best_alternative_return_pct": round(best_return, 2),
        "opportunity_cost_pct": round(best_return - chosen_return, 2),
    }


def evaluate_due_trade_history() -> tuple[int, str]:
    history = load_trade_history()
    if not history:
        return 0, "Keine Trading-Setups gespeichert."

    now = pd.Timestamp.now(tz=None)
    updated = 0
    for record in history:
        record.update(normalize_trade_record(record))
        symbol = record.get("Ticker") or record.get("symbol")
        entry_price = value_or_none(record.get("Einstieg") or record.get("entry_price"))
        target_price = value_or_none(record.get("Zielzone") or record.get("target"))
        stop_price = value_or_none(record.get("Stop-Zone") or record.get("stop"))
        direction = str(record.get("Richtung") or record.get("direction") or "Long")
        created_at_raw = record.get("Datum") or record.get("created_at")
        if not symbol or entry_price is None or not created_at_raw:
            continue
        try:
            created_at = pd.Timestamp(created_at_raw).tz_localize(None)
        except Exception:
            continue

        review_after = ensure_review_schedule(record)
        due_periods = [
            label for label, days in TRACKING_PERIODS.items()
            if review_after.get(label) is None and now >= created_at + pd.Timedelta(days=days)
        ]
        if not due_periods:
            continue

        try:
            data = yf.download(symbol, start=created_at.date(), end=(now + pd.Timedelta(days=1)).date(), interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.dropna(subset=["Close"]) if not data.empty and "Close" in data else pd.DataFrame()
        except Exception:
            data = pd.DataFrame()
        if data.empty:
            continue

        closes = data["Close"].astype(float)
        highs = data["High"].astype(float) if "High" in data else closes
        lows = data["Low"].astype(float) if "Low" in data else closes
        current_price = float(closes.iloc[-1])
        multiplier = trade_direction_multiplier(direction)
        if multiplier > 0:
            return_pct = (current_price - entry_price) / entry_price * 100
            max_positive = (float(highs.max()) - entry_price) / entry_price * 100
            max_negative = (float(lows.min()) - entry_price) / entry_price * 100
            target_hit = target_price is not None and float(highs.max()) >= target_price
            stop_hit = stop_price is not None and float(lows.min()) <= stop_price
        else:
            return_pct = (entry_price - current_price) / entry_price * 100
            max_positive = (entry_price - float(lows.min())) / entry_price * 100
            max_negative = (entry_price - float(highs.max())) / entry_price * 100
            target_hit = target_price is not None and float(lows.min()) <= target_price
            stop_hit = stop_price is not None and float(highs.max()) >= stop_price

        if target_hit and stop_hit:
            result = "Ziel und Stop im Zeitraum berührt"
        elif target_hit:
            result = "Treffer"
        elif stop_hit:
            result = "Fehlschlag"
        elif return_pct > 0:
            result = "positiv offen"
        elif return_pct < 0:
            result = "negativ offen"
        else:
            result = "neutral"

        alternative = trade_best_alternative(direction, return_pct)
        history_context = {
            "similar_setups": record.get("Ähnliche Setups"),
            "similar_setup_hits": record.get("Treffer ähnliche Setups"),
            "similar_setup_hit_rate": record.get("Trefferquote ähnliche Setups"),
            "history_status": record.get("Historienstatus"),
            "history_summary": record.get("Historienhinweis"),
            "calibration_context": record.get("Kalibrierungskontext"),
            "calibration_hint": record.get("Kalibrierungshinweis"),
        }

        for label in due_periods:
            review_after[label] = {
                "reviewed_at": now.isoformat(),
                "current_price": current_price,
                "return_pct": round(return_pct, 2),
                "max_positive_pct": round(max_positive, 2),
                "max_negative_pct": round(max_negative, 2),
                "target_hit": bool(target_hit),
                "stop_hit": bool(stop_hit),
                "result": result,
                **alternative,
                **history_context,
                "note": "Trade-Journal-Auswertung mit Kursdaten; keine Kauf- oder Verkaufsautomatisierung.",
            }
            updated += 1

    if updated:
        if not save_json_dict_list(TRADE_HISTORY_PATH, history):
            return updated, "Trading-Setups ausgewertet, aber Datei konnte nicht gespeichert werden."
    return updated, f"{updated} fällige Trade-Journal-Auswertungen aktualisiert."


def save_forward_test(record: dict) -> bool:
    history = load_forward_tests()
    history.insert(0, record)
    return save_json_dict_list(FORWARD_TEST_PATH, history)


def load_decision_history() -> list[dict]:
    return load_json_dict_list(DECISION_HISTORY_PATH)


def save_decision_record(record: dict) -> bool:
    history = load_decision_history()
    history.insert(0, record)
    return save_json_dict_list(DECISION_HISTORY_PATH, history)


def decision_exposure(decision: str) -> str:
    normalized = str(decision).strip().lower()
    if normalized in {"kaufen", "halten", "kleine tranche", "gestaffelt kaufen"}:
        return "Long"
    if normalized == "verkaufen":
        return "Short"
    return "Beobachten"


def app_action_exposure(action: object) -> str:
    normalized = str(action or "").strip().lower()
    if any(term in normalized for term in ["kaufen", "nachkauf", "tranche", "long"]):
        return "Long"
    if any(term in normalized for term in ["verkaufen", "short", "risiko zu hoch"]):
        return "Short"
    return "Beobachten"


def decision_alignment(decision: str, app_action: object) -> dict:
    user_exposure = decision_exposure(decision)
    app_exposure = app_action_exposure(app_action)
    aligned = user_exposure == app_exposure
    return {
        "app_exposure": app_exposure,
        "decision_matches_app": aligned,
        "decision_alignment": "mit App-Einschätzung" if aligned else "gegen App-Einschätzung",
    }


def evaluate_due_decision_history() -> tuple[int, str]:
    history = load_decision_history()
    if not history:
        return 0, "Keine Nutzerentscheidungen gespeichert."

    now = pd.Timestamp.now(tz=None)
    updated = 0
    for record in history:
        symbol = record.get("symbol")
        entry_price = value_or_none(record.get("price_at_decision"))
        created_at_raw = record.get("created_at")
        decision = str(record.get("decision", "Beobachten"))
        app_action = record.get("app_action") or record.get("action") or record.get("recommendation")
        if not symbol or entry_price is None or not created_at_raw:
            continue
        try:
            created_at = pd.Timestamp(created_at_raw).tz_localize(None)
        except Exception:
            continue

        review_after = ensure_review_schedule(record)
        due_periods = [
            label for label, days in TRACKING_PERIODS.items()
            if review_after.get(label) is None and now >= created_at + pd.Timedelta(days=days)
        ]
        if not due_periods:
            continue

        try:
            data = yf.download(symbol, start=created_at.date(), end=(now + pd.Timedelta(days=1)).date(), interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.dropna(subset=["Close"]) if not data.empty and "Close" in data else pd.DataFrame()
        except Exception:
            data = pd.DataFrame()
        if data.empty:
            continue

        closes = data["Close"].astype(float)
        highs = data["High"].astype(float) if "High" in data else closes
        lows = data["Low"].astype(float) if "Low" in data else closes
        current_price = float(closes.iloc[-1])
        long_return = (current_price - entry_price) / entry_price * 100
        short_return = -long_return
        neutral_return = 0.0
        alternatives = {
            "Long": long_return,
            "Short": short_return,
            "Halten/Beobachten": neutral_return,
        }
        exposure = decision_exposure(decision)
        alignment = decision_alignment(decision, app_action)
        decision_return = alternatives["Long"] if exposure == "Long" else alternatives["Short"] if exposure == "Short" else neutral_return
        best_alternative = max(alternatives, key=alternatives.get)
        best_return = alternatives[best_alternative]
        opportunity_cost = best_return - decision_return
        max_positive_long = (float(highs.max()) - entry_price) / entry_price * 100
        max_negative_long = (float(lows.min()) - entry_price) / entry_price * 100

        for label in due_periods:
            review_after[label] = {
                "reviewed_at": now.isoformat(),
                "current_price": current_price,
                "decision": decision,
                "decision_exposure": exposure,
                **alignment,
                "decision_return_pct": round(decision_return, 2),
                "best_alternative": best_alternative,
                "best_alternative_return_pct": round(best_return, 2),
                "opportunity_cost_pct": round(opportunity_cost, 2),
                "long_return_pct": round(long_return, 2),
                "short_return_pct": round(short_return, 2),
                "neutral_return_pct": round(neutral_return, 2),
                "max_positive_long_pct": round(max_positive_long, 2),
                "max_negative_long_pct": round(max_negative_long, 2),
                "note": "Decision-Tracking-Auswertung mit Kursdaten; keine Kauf- oder Verkaufsautomatisierung.",
            }
            updated += 1

    if updated:
        if not save_json_dict_list(DECISION_HISTORY_PATH, history):
            return updated, "Entscheidungen ausgewertet, aber Datei konnte nicht gespeichert werden."
    return updated, f"{updated} fällige Decision-Tracking-Auswertungen aktualisiert."


def load_prediction_history() -> list[dict]:
    return load_json_dict_list(PREDICTION_HISTORY_PATH)


def save_prediction_record(record: dict) -> bool:
    history = load_prediction_history()
    history.insert(0, record)
    return save_json_dict_list(PREDICTION_HISTORY_PATH, history)


def scenario_read_from_return(return_pct: float) -> str:
    if return_pct > 3:
        return "Bull/Base wahrscheinlicher"
    if return_pct < -3:
        return "Bear wahrscheinlicher"
    return "Base wahrscheinlicher"


def prediction_miss_reason(record: dict, return_pct: float) -> str:
    if return_pct > 0:
        return "Keine Fehlprognose"
    market_phase = str(record.get("market_phase") or record.get("Marktphase") or "")
    if "Bär" in market_phase or "Bear" in market_phase:
        return "Schwache Marktphase"

    snapshot = record.get("signal_snapshot")
    if isinstance(snapshot, dict):
        for signal_name in ["Makro", "News", "MACD", "CRV", "Volatilität"]:
            value = str(snapshot.get(signal_name) or "").lower()
            if any(marker in value for marker in ["niedrig", "negativ", "schwach", "hoch", "sehr hoch"]):
                return f"Signalproblem: {signal_name}"

    module_scores = record.get("module_scores")
    if isinstance(module_scores, list):
        for module in module_scores:
            if not isinstance(module, dict):
                continue
            score = value_or_none(module.get("score"))
            if score is not None and score < 4:
                return f"Schwaches Modul: {module.get('name') or 'Unbekanntes Modul'}"

    return "Kursentwicklung gegen Prognose"


def evaluate_due_predictions() -> tuple[int, str]:
    history = load_prediction_history()
    if not history:
        return 0, "Keine Prognosen gespeichert."

    now = pd.Timestamp.now(tz=None)
    updated = 0
    for record in history:
        symbol = record.get("symbol")
        entry_price = value_or_none(record.get("price_at_prediction"))
        created_at_raw = record.get("created_at")
        if not symbol or entry_price is None or not created_at_raw:
            continue
        try:
            created_at = pd.Timestamp(created_at_raw).tz_localize(None)
        except Exception:
            continue
        review_after = ensure_review_schedule(record)
        due_periods = [
            label for label, days in TRACKING_PERIODS.items()
            if review_after.get(label) is None and now >= created_at + pd.Timedelta(days=days)
        ]
        if not due_periods:
            continue
        try:
            data = yf.download(symbol, start=created_at.date(), end=(now + pd.Timedelta(days=1)).date(), interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.dropna(subset=["Close"]) if not data.empty and "Close" in data else pd.DataFrame()
        except Exception:
            data = pd.DataFrame()
        if data.empty:
            continue

        closes = data["Close"].astype(float)
        highs = data["High"].astype(float) if "High" in data else closes
        lows = data["Low"].astype(float) if "Low" in data else closes
        current_price = float(closes.iloc[-1])
        max_positive = (float(highs.max()) - entry_price) / entry_price * 100
        max_negative = (float(lows.min()) - entry_price) / entry_price * 100
        return_pct = (current_price - entry_price) / entry_price * 100
        scenario_hit = scenario_read_from_return(return_pct)
        miss_reason = prediction_miss_reason(record, return_pct)
        for label in due_periods:
            review_after[label] = {
                "reviewed_at": now.isoformat(),
                "current_price": current_price,
                "return_pct": round(return_pct, 2),
                "max_positive_pct": round(max_positive, 2),
                "max_negative_pct": round(max_negative, 2),
                "scenario_read": scenario_hit,
                "miss_reason": miss_reason,
                "note": "Prognose-Auswertung mit Kursdaten; keine Kauf- oder Verkaufsautomatisierung.",
            }
            updated += 1

    if updated:
        if not save_json_dict_list(PREDICTION_HISTORY_PATH, history):
            return updated, "Prognosen ausgewertet, aber Datei konnte nicht gespeichert werden."
    return updated, f"{updated} fällige Prognose-Auswertungen aktualisiert."


def evaluate_due_forward_tests() -> tuple[int, str]:
    history = load_forward_tests()
    if not history:
        return 0, "Keine Forward-Tests gespeichert."

    now = pd.Timestamp.now(tz=None)
    updated = 0
    for record in history:
        symbol = record.get("symbol")
        entry_price = value_or_none(record.get("entry_price"))
        created_at_raw = record.get("created_at")
        if not symbol or entry_price is None or not created_at_raw:
            continue
        try:
            created_at = pd.Timestamp(created_at_raw).tz_localize(None)
        except Exception:
            continue
        review_after = ensure_review_schedule(record)
        due_periods = [
            label for label, days in TRACKING_PERIODS.items()
            if review_after.get(label) is None and now >= created_at + pd.Timedelta(days=days)
        ]
        if not due_periods:
            continue
        try:
            data = yf.download(symbol, start=created_at.date(), end=(now + pd.Timedelta(days=1)).date(), interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.dropna(subset=["Close"]) if not data.empty and "Close" in data else pd.DataFrame()
        except Exception:
            data = pd.DataFrame()
        if data.empty:
            continue

        closes = data["Close"].astype(float)
        highs = data["High"].astype(float) if "High" in data else closes
        lows = data["Low"].astype(float) if "Low" in data else closes
        current_price = float(closes.iloc[-1])
        return_pct = (current_price - entry_price) / entry_price * 100
        scenario_read = scenario_read_from_return(return_pct)
        for label in due_periods:
            review_after[label] = {
                "reviewed_at": now.isoformat(),
                "current_price": current_price,
                "return_pct": round(return_pct, 2),
                "max_positive_pct": round((float(highs.max()) - entry_price) / entry_price * 100, 2),
                "max_negative_pct": round((float(lows.min()) - entry_price) / entry_price * 100, 2),
                "result": "positiv" if current_price >= entry_price else "negativ",
                "scenario_read": scenario_read,
                "note": "Automatische Forward-Test-Auswertung mit Kursdaten; keine Kauf- oder Verkaufsautomatisierung.",
            }
            updated += 1

    if updated:
        if not save_json_dict_list(FORWARD_TEST_PATH, history):
            return updated, "Auswertung berechnet, aber Datei konnte nicht gespeichert werden."
    return updated, f"{updated} fällige Forward-Test-Auswertungen aktualisiert."


def count_completed_reviews(history: list[dict]) -> int:
    count = 0
    for item in history:
        review_after = item.get("review_after", {})
        if isinstance(review_after, dict):
            count += sum(1 for value in review_after.values() if value)
    return count


def score_bucket(value: object) -> str:
    score = value_or_none(value)
    if score is None:
        return "unbekannt"
    if score >= 7:
        return "hoch"
    if score >= 5:
        return "mittel"
    return "niedrig"


def rsi_bucket(value: object) -> str:
    rsi = value_or_none(value)
    if rsi is None:
        return "Daten nicht verfügbar"
    if rsi < 30:
        return "überverkauft"
    if rsi > 70:
        return "überhitzt"
    if rsi >= 55:
        return "positiv"
    if rsi <= 45:
        return "schwach"
    return "neutral"

def signal_bucket(score: float | None) -> str:
    value = value_or_none(score)
    if value is None:
        return "unbekannt"
    if value >= 6.5:
        return "stark"
    if value <= 3.5:
        return "schwach"
    return "neutral"


def macd_bucket(macd_value: object, signal_value: object) -> str:
    macd = value_or_none(macd_value)
    signal = value_or_none(signal_value)
    if macd is None or signal is None:
        return "Daten nicht verfügbar"
    spread = abs(macd - signal)
    scale = max(abs(macd), abs(signal), 1.0)
    if spread / scale < 0.01:
        return "neutral"
    return "positiv" if macd > signal else "negativ"


def volatility_bucket(value: object) -> str:
    volatility = value_or_none(value)
    if volatility is None:
        return "Daten nicht verfügbar"
    if volatility >= 0.75:
        return "sehr hoch"
    if volatility >= 0.45:
        return "erhöht"
    if volatility <= 0.22:
        return "ruhig"
    return "normal"


def crv_bucket(value: object) -> str:
    ratio = value_or_none(value)
    if ratio is None:
        return "Daten nicht verfügbar"
    if ratio >= 2.5:
        return "stark"
    if ratio >= 1.5:
        return "positiv"
    if ratio >= 1.0:
        return "knapp"
    return "schwach"


def module_score_from_record(record: dict, *needles: str) -> float | None:
    modules = record.get("module_scores", [])
    if not isinstance(modules, list):
        return None
    normalized_needles = [needle.lower() for needle in needles]
    for module in modules:
        if not isinstance(module, dict):
            continue
        name = str(module.get("name", "")).lower()
        if any(needle in name for needle in normalized_needles):
            score = value_or_none(module.get("score"))
            if score is not None:
                return float(score)
    return None


def build_signal_snapshot(latest: pd.Series, risk_reward: RiskReward, modules: list[ResearchModule] | None = None) -> dict:
    modules = modules or []
    module_scores = {module.name: module.score for module in modules}
    news_score = next((score for name, score in module_scores.items() if "News" in name), None)
    macro_score = next((score for name, score in module_scores.items() if "Makro" in name), None)
    return {
        "RSI": rsi_bucket(latest.get("RSI_14")),
        "MACD": macd_bucket(latest.get("MACD"), latest.get("MACD_Signal")),
        "Volatilität": volatility_bucket(latest.get("Volatility")),
        "CRV": crv_bucket(risk_reward.ratio),
        "News": score_bucket(news_score),
        "Makro": score_bucket(macro_score),
    }


def snapshot_signal_value(snapshot: dict, signal_name: str) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    aliases = {
        "RSI": ["RSI", "rsi"],
        "MACD": ["MACD", "macd"],
        "Marktphase": ["Marktphase", "market_phase"],
        "Volatilität": ["Volatilität", "Volatilitaet", "Volatility"],
        "News": ["News", "news"],
        "Makro": ["Makro", "Macro", "macro"],
        "CRV": ["CRV", "crv", "risk_reward"],
    }
    for key in aliases.get(signal_name, [signal_name]):
        value = snapshot.get(key)
        if value:
            return str(value)
    return None


def signal_bucket_from_record(record: dict, signal_name: str) -> str:
    snapshot = record.get("signal_snapshot", {})
    snapshot_value = snapshot_signal_value(snapshot, signal_name)
    if snapshot_value:
        return snapshot_value
    if signal_name == "Marktphase":
        return str(record.get("market_phase") or record.get("Marktphase") or "Daten nicht verfügbar")
    if signal_name == "CRV":
        return crv_bucket(record.get("risk_reward_ratio") or record.get("CRV"))
    if signal_name == "News":
        return score_bucket(module_score_from_record(record, "news"))
    if signal_name == "Makro":
        return score_bucket(module_score_from_record(record, "makro"))
    return "Daten nicht verfügbar"


def action_family(action: object) -> str:
    text = str(action or "").lower()
    if any(token in text for token in ["auf konkrete kaufzone warten", "bei bestätigung kaufen"]):
        return "Abwarten/Beobachten"
    if any(token in text for token in ["teilweise reduzieren", "verkaufen oder vermeiden", "verkaufen", "short", "absicherung"]):
        return "Short/Verkaufen"
    if any(token in text for token in ["jetzt kaufen", "erste tranche", "stark kaufen", "gestaffelt", "kleine tranche", "kaufen", "nachkauf", "long", "halten"]):
        return "Long/Kaufen"
    if any(token in text for token in ["nicht kaufen", "abwarten", "beobachten", "risiko zu hoch"]):
        return "Abwarten/Beobachten"
    return "Unbekannt"


def record_action(record: dict) -> str:
    professional = record.get("professional_decision")
    if isinstance(professional, dict) and professional.get("Titel"):
        return str(professional["Titel"])
    for key in ["app_action", "action", "Richtung", "direction", "decision"]:
        if record.get(key):
            return str(record[key])
    return "Unbekannt"


def record_return_for_review(record: dict, review: dict) -> float | None:
    for key in ["decision_return_pct", "return_pct"]:
        value = value_or_none(review.get(key))
        if value is not None:
            return float(value)
    return None


def action_hit(action: str, return_pct: float) -> bool:
    family = action_family(action)
    if family == "Short/Verkaufen":
        return return_pct > 0
    if family == "Abwarten/Beobachten":
        return return_pct <= 0
    return return_pct > 0


def evaluated_history_cases(
    trade_history: list[dict] | None = None,
    forward_tests: list[dict] | None = None,
    predictions: list[dict] | None = None,
    decisions: list[dict] | None = None,
) -> list[dict]:
    histories = [
        ("Trade Journal", trade_history or []),
        ("Forward-Test", forward_tests or []),
        ("Prognose", predictions or []),
        ("Entscheidung", decisions or []),
    ]
    cases: list[dict] = []
    for source, history in histories:
        for record in history:
            if not isinstance(record, dict):
                continue
            review_after = record.get("review_after", {})
            if not isinstance(review_after, dict):
                continue
            for period, review in review_after.items():
                if not isinstance(review, dict):
                    continue
                return_pct = record_return_for_review(record, review)
                legacy_hit = setup_result_is_hit(review) if return_pct is None else None
                if return_pct is None and legacy_hit is None:
                    continue
                action = record_action(record)
                cases.append(
                    {
                        "source": source,
                        "period": period,
                        "record": record,
                        "action": action,
                        "action_family": action_family(action),
                        "asset_type": str(record.get("asset_type") or record.get("Asset-Typ") or "Unbekannt"),
                        "market_phase": str(record.get("market_phase") or record.get("Marktphase") or "Unbekannt"),
                        "buy_signal_bucket": score_bucket(record.get("buy_signal") or record.get("Kaufsignal")),
                        "quality_bucket": score_bucket(record.get("asset_quality") or record.get("Asset-Qualität")),
                        "return_pct": return_pct if return_pct is not None else 0.0,
                        "hit": action_hit(action, return_pct) if return_pct is not None else legacy_hit,
                        "scenario_read": str(review.get("scenario_read") or "Daten nicht verfügbar"),
                        "miss_reason": str(review.get("miss_reason") or "Daten nicht verfügbar"),
                        "decision_alignment": str(review.get("decision_alignment") or "Daten nicht verfügbar"),
                        "history_status": str(review.get("history_status") or record.get("Historienstatus") or record.get("history_status") or "Daten nicht verfügbar"),
                        "calibration_context": str(review.get("calibration_context") or record.get("Kalibrierungskontext") or record.get("calibration_context") or "Daten nicht verfügbar"),
                        "calibration_hint": str(review.get("calibration_hint") or record.get("Kalibrierungshinweis") or record.get("calibration_hint") or "Daten nicht verfügbar"),
                        "signals": {
                            name: signal_bucket_from_record(record, name)
                            for name in ["RSI", "MACD", "Marktphase", "Volatilität", "News", "Makro", "CRV"]
                        },
                    }
                )
    return cases


def setup_result_is_hit(result: dict) -> bool | None:
    if not isinstance(result, dict):
        return None
    result_label = str(result.get("result") or result.get("scenario_read") or "").lower()
    if "treffer" in result_label or "positiv" in result_label or "bull" in result_label:
        return True
    if "fehlschlag" in result_label or "negativ" in result_label or "bear" in result_label:
        return False
    return_pct = value_or_none(result.get("return_pct"))
    if return_pct is None:
        return None
    return float(return_pct) > 0


def review_results(record: dict) -> list[tuple[str, dict]]:
    review_after = record.get("review_after")
    if not isinstance(review_after, dict):
        return []
    return [
        (str(period), result)
        for period, result in review_after.items()
        if isinstance(result, dict)
    ]


def historical_review_cases() -> list[dict]:
    cases: list[dict] = []
    for record in load_trade_history():
        asset_type = str(record.get("Asset-Typ") or record.get("asset_type") or "Unbekannt")
        market_phase = str(record.get("Marktphase") or record.get("market_phase") or "Unbekannt")
        direction = str(record.get("Richtung") or record.get("direction") or "Unbekannt")
        score = value_or_none(record.get("Kaufsignal") or record.get("buy_signal"))
        for period, result in review_results(record):
            hit = setup_result_is_hit(result)
            if hit is not None:
                cases.append(
                    {
                        "source": "Trade Journal",
                        "asset_type": asset_type,
                        "market_phase": market_phase,
                        "direction": direction,
                        "signal_bucket": signal_bucket(score),
                        "period": period,
                        "hit": hit,
                    }
                )
    for record in load_forward_tests():
        asset_type = str(record.get("asset_type") or "Unbekannt")
        market_phase = str(record.get("market_phase") or "Unbekannt")
        score = value_or_none(record.get("buy_signal"))
        direction = "Long" if score is not None and float(score) >= 5 else "Beobachten"
        for period, result in review_results(record):
            hit = setup_result_is_hit(result)
            if hit is not None:
                cases.append(
                    {
                        "source": "Forward-Test",
                        "asset_type": asset_type,
                        "market_phase": market_phase,
                        "direction": direction,
                        "signal_bucket": signal_bucket(score),
                        "period": period,
                        "hit": hit,
                    }
                )
    for record in load_prediction_history():
        asset_type = str(record.get("asset_type") or "Unbekannt")
        market_phase = str(record.get("market_phase") or "Unbekannt")
        for period, result in review_results(record):
            hit = setup_result_is_hit(result)
            if hit is not None:
                cases.append(
                    {
                        "source": "Prognose",
                        "asset_type": asset_type,
                        "market_phase": market_phase,
                        "direction": "Szenario",
                        "signal_bucket": "unbekannt",
                        "period": period,
                        "hit": hit,
                    }
                )
    return cases


def calibration_permission(count: int) -> tuple[str, str]:
    if count < 20:
        return "Datenbasis zu klein", "Noch keine Kalibrierung. Signal wird nur gezählt."
    if count <= 50:
        return "Vorsichtiger Hinweis", "Nur Beobachtung: Signal auffällig, aber noch keine robuste Anpassung."
    return "Kalibrierungsvorschlag erlaubt", "Manueller Vorschlag möglich; Gewichtungen werden nicht automatisch geändert."


def signal_calibration_rows(similar: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for signal_name in ["RSI", "MACD", "Marktphase", "Volatilität", "News", "Makro", "CRV"]:
        grouped: dict[str, list[dict]] = {}
        for case in similar:
            bucket = case.get("signals", {}).get(signal_name, "Daten nicht verfügbar")
            if bucket in {"Daten nicht verfügbar", "unbekannt", ""}:
                continue
            grouped.setdefault(str(bucket), []).append(case)

        if not grouped:
            rows.append(
                {
                    "Messpunkt": f"Signal {signal_name}",
                    "Wert": "Daten nicht verfügbar",
                    "Bedeutung": f"Für {signal_name} liegen in ähnlichen historischen Setups noch keine gespeicherten Signalwerte vor.",
                }
            )
            continue

        best_bucket, best_cases = max(
            grouped.items(),
            key=lambda item: (
                sum(1 for case in item[1] if case["hit"]) / len(item[1]),
                len(item[1]),
            ),
        )
        count = len(best_cases)
        hit_rate = sum(1 for case in best_cases if case["hit"]) / count * 100
        avg_return = float(np.mean([case["return_pct"] for case in best_cases]))
        permission, meaning = calibration_permission(count)
        display_value = (
            f"{best_bucket}: {count} Fälle, {hit_rate:.1f}% Treffer, {avg_return:+.2f}% Ø"
            if count >= 20
            else f"{best_bucket}: {count} Fälle"
        )
        rows.append(
            {
                "Messpunkt": f"Signal {signal_name}",
                "Wert": display_value,
                "Bedeutung": f"{permission}. {meaning}",
            }
        )
    return rows


def segmented_learning_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
) -> tuple[str, list[dict[str, str]]]:
    cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    if not cases:
        return "Keine ausgewerteten Historienfälle vorhanden.", [
            {
                "Dimension": "Gesamt",
                "Gruppe": "Daten nicht verfügbar",
                "Fälle": "0",
                "Trefferquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Status": "Keine Kalibrierung",
                "Bedeutung": "Es gibt noch keine ausgewerteten Trade-, Forward-, Decision- oder Prognosefälle.",
            }
        ]

    if len(cases) < 20:
        status = "Datenbasis zu klein. Segment-Trefferquoten werden gezählt, aber noch nicht belastbar interpretiert."
    elif len(cases) <= 50:
        status = "Vorsichtige Segment-Hinweise möglich. Gewichtungen bleiben unverändert."
    else:
        status = "Ausreichend Historie für Segment-Vorschläge. Gewichtungen werden trotzdem nicht automatisch geändert."

    dimensions = [
        ("Asset-Typ", lambda case: case.get("asset_type") or "Unbekannt"),
        ("Marktphase", lambda case: case.get("market_phase") or "Unbekannt"),
        ("Zeithorizont", lambda case: case.get("period") or "Unbekannt"),
    ]
    rows: list[dict[str, str]] = []
    for dimension, getter in dimensions:
        grouped: dict[str, list[dict]] = {}
        for case in cases:
            group = str(getter(case))
            if not group or group.lower() in {"unbekannt", "none"}:
                continue
            grouped.setdefault(group, []).append(case)

        if not grouped:
            rows.append(
                {
                    "Dimension": dimension,
                    "Gruppe": "Daten nicht verfügbar",
                    "Fälle": "0",
                    "Trefferquote": "Datenbasis zu klein",
                    "Durchschnittsrendite": "Datenbasis zu klein",
                    "Status": "Keine Kalibrierung",
                    "Bedeutung": f"Für {dimension} liegen noch keine verwertbaren historischen Gruppen vor.",
                }
            )
            continue

        for group, group_cases in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:8]:
            count = len(group_cases)
            hit_rate = sum(1 for case in group_cases if case["hit"]) / count * 100
            avg_return = float(np.mean([case["return_pct"] for case in group_cases]))
            permission, meaning = calibration_permission(count)
            rows.append(
                {
                    "Dimension": dimension,
                    "Gruppe": group,
                    "Fälle": str(count),
                    "Trefferquote": "Datenbasis zu klein" if count < 20 else f"{hit_rate:.1f}%",
                    "Durchschnittsrendite": "Datenbasis zu klein" if count < 20 else f"{avg_return:+.2f}%",
                    "Status": permission,
                    "Bedeutung": meaning,
                }
            )
    return status, rows


def negative_case_cause_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
) -> tuple[str, list[dict[str, str]]]:
    cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    misses = [case for case in cases if case.get("hit") is False]

    if not cases:
        return "Keine ausgewerteten Historienfälle vorhanden.", [
            {
                "Dimension": "Gesamt",
                "Ausprägung": "Daten nicht verfügbar",
                "Fehlfälle": "0",
                "Anteil": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Schlechtester Fall": "Datenbasis zu klein",
                "Status": "Keine Kalibrierung",
                "Bedeutung": "Es gibt noch keine ausgewerteten Fälle, aus denen Fehlerursachen abgeleitet werden können.",
            }
        ]

    if not misses:
        return "Keine Fehlfälle in der lokalen Historie erkannt.", [
            {
                "Dimension": "Gesamt",
                "Ausprägung": "Keine Fehlfälle",
                "Fehlfälle": "0",
                "Anteil": "0.0%",
                "Durchschnittsrendite": "n/a",
                "Schlechtester Fall": "n/a",
                "Status": "Nur Beobachtung",
                "Bedeutung": "Die ausgewerteten Fälle enthalten bisher keinen verfehlten Ausgang. Gewichtungen bleiben unverändert.",
            }
        ]

    if len(misses) < 20:
        status = "Datenbasis zu klein. Fehlerursachen werden gezählt, aber noch nicht belastbar interpretiert."
    elif len(misses) <= 50:
        status = "Vorsichtige Fehlerursachen-Hinweise möglich. Gewichtungen bleiben unverändert."
    else:
        status = "Genügend Fehlfälle für transparentere Ursachenhinweise. Änderungen bleiben manuell und testpflichtig."

    dimensions: list[tuple[str, Callable[[dict], object]]] = [
        ("Asset-Typ", lambda case: case.get("asset_type") or "Unbekannt"),
        ("Marktphase", lambda case: case.get("market_phase") or "Unbekannt"),
        ("Kaufsignal", lambda case: case.get("buy_signal_bucket") or "Unbekannt"),
        ("RSI", lambda case: case.get("signals", {}).get("RSI") or "Daten nicht verfügbar"),
        ("MACD", lambda case: case.get("signals", {}).get("MACD") or "Daten nicht verfügbar"),
        ("Volatilität", lambda case: case.get("signals", {}).get("Volatilität") or "Daten nicht verfügbar"),
        ("CRV", lambda case: case.get("signals", {}).get("CRV") or "Daten nicht verfügbar"),
        ("News", lambda case: case.get("signals", {}).get("News") or "Daten nicht verfügbar"),
        ("Makro", lambda case: case.get("signals", {}).get("Makro") or "Daten nicht verfügbar"),
        ("Szenario-Lesart", lambda case: case.get("scenario_read") or "Daten nicht verfügbar"),
        ("Fehlursache", lambda case: case.get("miss_reason") or "Daten nicht verfügbar"),
        ("Decision-Alignment", lambda case: case.get("decision_alignment") or "Daten nicht verfügbar"),
        ("Kalibrierungskontext", lambda case: case.get("calibration_context") or "Daten nicht verfügbar"),
        ("Kalibrierungshinweis", lambda case: case.get("calibration_hint") or "Daten nicht verfügbar"),
    ]

    rows: list[dict[str, str]] = [
        {
            "Dimension": "Gesamt",
            "Ausprägung": "Alle Fehlfälle",
            "Fehlfälle": str(len(misses)),
            "Anteil": f"{len(misses) / len(cases) * 100:.1f}%",
            "Durchschnittsrendite": f"{float(np.mean([case['return_pct'] for case in misses])):+.2f}%",
            "Schlechtester Fall": f"{min(case['return_pct'] for case in misses):+.2f}%",
            "Status": calibration_permission(len(misses))[0],
            "Bedeutung": status,
        }
    ]

    for dimension, getter in dimensions:
        grouped: dict[str, list[dict]] = {}
        for case in misses:
            group = str(getter(case))
            if not group or group.lower() in {"unbekannt", "none", "daten nicht verfügbar"}:
                continue
            grouped.setdefault(group, []).append(case)

        for group, group_cases in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:3]:
            count = len(group_cases)
            permission, meaning = calibration_permission(count)
            avg_return = float(np.mean([case["return_pct"] for case in group_cases]))
            worst_return = min(case["return_pct"] for case in group_cases)
            rows.append(
                {
                    "Dimension": dimension,
                    "Ausprägung": group,
                    "Fehlfälle": str(count),
                    "Anteil": f"{count / len(misses) * 100:.1f}%",
                    "Durchschnittsrendite": "Datenbasis zu klein" if count < 20 else f"{avg_return:+.2f}%",
                    "Schlechtester Fall": "Datenbasis zu klein" if count < 20 else f"{worst_return:+.2f}%",
                    "Status": permission,
                    "Bedeutung": f"{meaning} Diese Gruppe zeigt, wo verfehlte Empfehlungen gehäuft auftraten.",
                }
            )

    if len(rows) == 1:
        rows.append(
            {
                "Dimension": "Signalgruppen",
                "Ausprägung": "Daten nicht verfügbar",
                "Fehlfälle": "0",
                "Anteil": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Schlechtester Fall": "Datenbasis zu klein",
                "Status": "Keine Kalibrierung",
                "Bedeutung": "Die Fehlfälle enthalten noch keine verwertbaren Asset-, Marktphasen- oder Signalgruppen.",
            }
        )
    return status, rows


def backtest_calibration_candidates(history: list[dict]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for record in history:
        rows = record.get("rows", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            count = value_or_none(row_value(row, "Fälle", "Faelle", "Falle"))
            hit_rate = percent_value(row_value(row, "Trefferquote") or "")
            avg_return = percent_value(row_value(row, "Durchschnittsrendite") or "")
            if count is None or count < 20 or hit_rate is None or avg_return is None:
                continue
            if hit_rate >= 45 and avg_return >= 0:
                continue
            miss_rate = max(0.0, 100.0 - hit_rate)
            miss_count = max(1, int(round(int(count) * miss_rate / 100.0)))
            label = backtest_group_label(record, row)
            candidates.append(
                {
                    "dimension": "Backtest-Signal",
                    "group": label,
                    "count": int(count),
                    "miss_count": miss_count,
                    "miss_rate": miss_rate,
                    "avg_return": avg_return,
                    "suggestion": "Prüfen, ob diese historische Signalkombination im Kaufsignal, Confidence-Kontext oder in Warnhinweisen stärker sichtbar sein sollte.",
                }
            )
    return candidates


def backtest_calibration_context(history: list[dict], market_phase: str, buy_signal_score: float | None) -> tuple[str, str]:
    candidates = backtest_calibration_candidates(history)
    if not history:
        return (
            "Daten nicht verfügbar",
            "Keine gespeicherte Backtest-Historie vorhanden; Scanner und Trading-Modus ändern deshalb keine Einschätzung.",
        )
    if not candidates:
        return (
            "Keine auffällige Backtest-Warnung",
            "Gespeicherte Backtests enthalten aktuell kein schwaches Muster mit ausreichender Datenbasis.",
        )

    bucket = score_bucket(buy_signal_score)
    phase_text = str(market_phase or "")

    def relevance(candidate: dict[str, object]) -> tuple[int, int, float, float]:
        label = str(candidate.get("group") or "")
        phase_match = 1 if phase_text and phase_text in label else 0
        bucket_match = 1 if bucket and f"Kauf {bucket}" in label else 0
        return (
            phase_match + bucket_match,
            int(candidate.get("count") or 0),
            float(candidate.get("miss_rate") or 0.0),
            -float(candidate.get("avg_return") or 0.0),
        )

    best = max(candidates, key=relevance)
    count = int(best.get("count") or 0)
    miss_rate = float(best.get("miss_rate") or 0.0)
    avg_return = float(best.get("avg_return") or 0.0)
    label = str(best.get("group") or "Backtest-Signal")
    status, _ = backtest_confidence_context(count, 100.0 - miss_rate, avg_return)
    return (
        status,
        f"Schwaches Backtest-Muster: {label}. Datenbasis {count} Fälle, Fehlquote {miss_rate:.1f}%, Durchschnittsrendite {avg_return:+.2f}%. Nur manueller Hinweis, keine automatische Score-Änderung.",
    )


def calibration_suggestion_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
    backtest_history: list[dict] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    candidates: list[dict[str, object]] = backtest_calibration_candidates(backtest_history or [])
    if not cases and not candidates:
        return "Keine Kalibrierungsvorschläge möglich: keine ausgewerteten Historienfälle vorhanden.", [
            {
                "Bereich": "Gesamt",
                "Muster": "Daten nicht verfügbar",
                "Datenbasis": "0 Fälle",
                "Fehlquote": "Datenbasis zu klein",
                "Vorschlag": "Keine Änderung",
                "Begründung": "Ohne ausgewertete Historie darf die App keine Kalibrierungsvorschläge ableiten.",
                "Umsetzung": "Keine automatische Gewichtungsänderung.",
            }
        ]

    dimensions: list[tuple[str, Callable[[dict], object], str]] = [
        ("Asset-Typ", lambda case: case.get("asset_type") or "Unbekannt", "Prüfen, ob die Bewertungslogik für diesen Asset-Typ zu optimistisch oder zu vorsichtig ist."),
        ("Marktphase", lambda case: case.get("market_phase") or "Unbekannt", "Prüfen, ob die Marktphasen-Erkennung oder ihre Gewichtung im Kaufsignal angepasst werden sollte."),
        ("Kaufsignal", lambda case: case.get("buy_signal_bucket") or "Unbekannt", "Prüfen, ob die Kaufsignal-Schwellen zu aggressiv oder zu defensiv gesetzt sind."),
        ("RSI", lambda case: case.get("signals", {}).get("RSI") or "Daten nicht verfügbar", "Prüfen, ob RSI-Signale je Asset-Typ anders interpretiert werden sollten."),
        ("MACD", lambda case: case.get("signals", {}).get("MACD") or "Daten nicht verfügbar", "Prüfen, ob Momentum-Bestätigung stärker verlangt werden sollte."),
        ("Volatilität", lambda case: case.get("signals", {}).get("Volatilität") or "Daten nicht verfügbar", "Prüfen, ob hohe Schwankung das Timing oder die Positionsgröße stärker begrenzen sollte."),
        ("CRV", lambda case: case.get("signals", {}).get("CRV") or "Daten nicht verfügbar", "Prüfen, ob ein schwaches Chancen-Risiko-Verhältnis stärker gegen Einstiege sprechen sollte."),
        ("News", lambda case: case.get("signals", {}).get("News") or "Daten nicht verfügbar", "Prüfen, ob News-Signale zuverlässiger gefiltert oder schwächer gewichtet werden sollten."),
        ("Makro", lambda case: case.get("signals", {}).get("Makro") or "Daten nicht verfügbar", "Prüfen, ob Makro-Gegenwind stärker in Risiko und Timing einfließen sollte."),
        ("Szenario-Lesart", lambda case: case.get("scenario_read") or "Daten nicht verfügbar", "Prüfen, ob Szenario-Wahrscheinlichkeiten zu optimistisch oder zu defensiv gesetzt werden."),
        ("Fehlursache", lambda case: case.get("miss_reason") or "Daten nicht verfügbar", "Prüfen, ob wiederkehrende Fehlursachen eine Modulverbesserung statt eine Gewichtungsänderung erfordern."),
        ("Decision-Alignment", lambda case: case.get("decision_alignment") or "Daten nicht verfügbar", "Prüfen, ob Nutzerentscheidungen gegen die App systematisch bessere oder schlechtere Ergebnisse liefern."),
        ("Kalibrierungskontext", lambda case: case.get("calibration_context") or "Daten nicht verfügbar", "Prüfen, ob frühere Backtest-Warnungen tatsächlich mit schwächeren Ergebnissen zusammenfielen."),
        ("Kalibrierungshinweis", lambda case: case.get("calibration_hint") or "Daten nicht verfügbar", "Prüfen, ob wiederkehrende Backtest-Hinweise bessere Warntexte oder manuelle Regelprüfungen erfordern."),
    ]

    for dimension, getter, suggestion in dimensions:
        grouped: dict[str, list[dict]] = {}
        for case in cases:
            group = str(getter(case))
            if not group or group.lower() in {"unbekannt", "none", "daten nicht verfügbar"}:
                continue
            grouped.setdefault(group, []).append(case)

        for group, group_cases in grouped.items():
            count = len(group_cases)
            misses = [case for case in group_cases if case.get("hit") is False]
            miss_count = len(misses)
            if miss_count == 0:
                continue
            miss_rate = miss_count / count * 100
            avg_return = float(np.mean([case["return_pct"] for case in group_cases]))
            candidates.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "count": count,
                    "miss_count": miss_count,
                    "miss_rate": miss_rate,
                    "avg_return": avg_return,
                    "suggestion": suggestion,
                }
            )

    if not candidates:
        return "Keine auffälligen Fehlmuster erkannt.", [
            {
                "Bereich": "Gesamt",
                "Muster": "Keine Fehlmuster",
                "Datenbasis": f"{len(cases)} Fälle",
                "Fehlquote": "0.0%",
                "Vorschlag": "Keine Änderung",
                "Begründung": "Die lokale Historie enthält aktuell keine gruppierbaren Fehlmuster.",
                "Umsetzung": "Keine automatische Gewichtungsänderung.",
            }
        ]

    candidates.sort(key=lambda item: (int(item["miss_count"]), float(item["miss_rate"]), -float(item["avg_return"])), reverse=True)
    rows: list[dict[str, str]] = []
    for candidate in candidates[:10]:
        count = int(candidate["count"])
        miss_count = int(candidate["miss_count"])
        miss_rate = float(candidate["miss_rate"])
        permission, meaning = calibration_permission(count)
        if count < 20:
            proposal = "Nur zählen"
        elif count <= 50:
            proposal = "Vorsichtig prüfen"
        else:
            proposal = "Manueller Kalibrierungsvorschlag erlaubt"
        rows.append(
            {
                "Bereich": str(candidate["dimension"]),
                "Muster": str(candidate["group"]),
                "Datenbasis": f"{count} Fälle, davon {miss_count} Fehlfälle",
                "Fehlquote": "Datenbasis zu klein" if count < 20 else f"{miss_rate:.1f}%",
                "Vorschlag": proposal,
                "Begründung": f"{meaning} {candidate['suggestion']}",
                "Umsetzung": "Nicht automatisch ändern; erst dokumentieren, testen und Roadmap begründen.",
            }
        )

    largest_basis = max(int(candidate["count"]) for candidate in candidates)
    if largest_basis < 20:
        status = "Datenbasis zu klein. Vorschläge werden nur als Zählhinweis angezeigt."
    elif largest_basis <= 50:
        status = "Vorsichtige Kalibrierungshinweise möglich. Gewichtungen bleiben unverändert."
    else:
        status = "Kalibrierungsvorschläge erlaubt. Jede Änderung bleibt manuell, dokumentiert und testpflichtig."
    return status, rows


def calibration_context_summary_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
) -> tuple[str, list[dict[str, str]]]:
    cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    grouped: dict[str, list[dict]] = {}
    for case in cases:
        context = str(case.get("calibration_context") or "")
        if context.lower() in {"", "none", "daten nicht verfügbar"}:
            continue
        grouped.setdefault(context, []).append(case)

    if not grouped:
        return "Keine zusammenfassbaren Kalibrierungskontexte vorhanden.", [
            {
                "Kalibrierungskontext": "Daten nicht verfügbar",
                "Fälle": "0",
                "Fehlquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Bedeutung": "Es gibt noch keine ausgewerteten Performance-Reviews mit Kalibrierungskontext.",
            }
        ]

    rows: list[dict[str, str]] = []
    for context, context_cases in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:6]:
        count = len(context_cases)
        misses = sum(1 for case in context_cases if case.get("hit") is False)
        miss_rate = misses / count * 100
        avg_return = float(np.mean([case["return_pct"] for case in context_cases]))
        permission, meaning = calibration_permission(count)
        if count < 20:
            practical = "Nur zählen; für Entscheidungen noch nicht belastbar."
        elif miss_rate >= 55:
            practical = "Warnhinweis ernst nehmen und Setup genauer prüfen."
        elif miss_rate <= 35 and avg_return > 0:
            practical = "Warnhinweis war historisch weniger kritisch, bleibt aber nur Kontext."
        else:
            practical = "Gemischtes Bild; weitere Fälle sammeln."
        rows.append(
            {
                "Kalibrierungskontext": context,
                "Fälle": str(count),
                "Fehlquote": "Datenbasis zu klein" if count < 20 else f"{miss_rate:.1f}%",
                "Durchschnittsrendite": "Datenbasis zu klein" if count < 20 else f"{avg_return:+.2f}%",
                "Bedeutung": f"{permission}. {meaning} {practical} Keine automatische Gewichtungsänderung.",
            }
        )

    largest = max(len(items) for items in grouped.values())
    if largest < 20:
        status = "Kalibrierungskontexte werden gezählt, aber wegen kleiner Datenbasis nicht interpretiert."
    elif largest <= 50:
        status = "Vorsichtige Zusammenfassung der Kalibrierungskontexte verfügbar. Gewichtungen bleiben unverändert."
    else:
        status = "Belastbarere Kalibrierungskontext-Zusammenfassung verfügbar. Änderungen bleiben manuell und testpflichtig."
    return status, rows


def local_history_quality_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
    backtest_history: list[dict],
) -> tuple[str, list[dict[str, str]]]:
    history_groups = [
        ("Trade Journal", trade_history),
        ("Forward-Tests", forward_tests),
        ("Entscheidungen", decisions),
        ("Prognosen", predictions),
    ]
    evaluated_cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    rows: list[dict[str, str]] = []
    issues = 0
    total_records = 0
    total_reviews = 0

    for label, records in history_groups:
        total_records += len(records)
        review_records = 0
        completed_reviews = 0
        malformed = 0
        for record in records:
            review_after = record.get("review_after")
            if not isinstance(review_after, dict):
                malformed += 1
                continue
            if review_after:
                review_records += 1
            completed_reviews += sum(1 for review in review_after.values() if isinstance(review, dict))
        total_reviews += completed_reviews
        if malformed:
            issues += 1
        rows.append(
            {
                "Historie": label,
                "Einträge": str(len(records)),
                "Auswertungen": str(completed_reviews),
                "Datenqualität": "Eingeschränkt" if malformed else "OK",
                "Hinweis": (
                    f"{malformed} Einträge haben kein gültiges `review_after` und werden im Lernsystem ignoriert."
                    if malformed
                    else "Struktur lesbar; fehlende einzelne Daten bleiben `Daten nicht verfügbar`."
                ),
                "Reparaturhinweis": (
                    "Betroffene JSON-Datei prüfen oder alte Einträge mit ungültigem `review_after` manuell entfernen; die App löscht nichts automatisch."
                    if malformed
                    else "Keine Reparatur nötig."
                ),
            }
        )

    backtest_rows = 0
    usable_backtest_rows = 0
    malformed_backtests = 0
    for record in backtest_history:
        rows_raw = record.get("rows")
        if not isinstance(rows_raw, list):
            malformed_backtests += 1
            continue
        for row in rows_raw:
            if not isinstance(row, dict):
                malformed_backtests += 1
                continue
            backtest_rows += 1
            count = value_or_none(row_value(row, "Fälle", "Faelle", "Falle"))
            hit_rate = percent_value(row_value(row, "Trefferquote") or "")
            avg_return = percent_value(row_value(row, "Durchschnittsrendite") or "")
            if count is not None and count >= 20 and hit_rate is not None and avg_return is not None:
                usable_backtest_rows += 1
    if malformed_backtests or (backtest_history and usable_backtest_rows == 0):
        issues += 1
    rows.append(
        {
            "Historie": "Backtests",
            "Einträge": str(len(backtest_history)),
            "Auswertungen": str(usable_backtest_rows),
            "Datenqualität": "Eingeschränkt" if malformed_backtests or (backtest_history and usable_backtest_rows == 0) else "OK",
            "Hinweis": (
                f"{malformed_backtests} Backtest-Einträge sind unvollständig; {backtest_rows} Tabellenzeilen gefunden, {usable_backtest_rows} belastbar."
                if malformed_backtests
                else f"{backtest_rows} Tabellenzeilen gefunden, {usable_backtest_rows} mit mindestens 20 Fällen und vollständigen Kennzahlen."
            ),
            "Reparaturhinweis": (
                "Backtest-Historie prüfen oder neue Backtests speichern; alte unvollständige Zeilen werden ignoriert, aber nicht automatisch gelöscht."
                if malformed_backtests or (backtest_history and usable_backtest_rows == 0)
                else "Keine Reparatur nötig."
            ),
        }
    )

    if total_records == 0 and not backtest_history:
        status = "Keine lokalen Lernhistorien vorhanden. Lernmodule zeigen deshalb nur `Datenbasis zu klein`."
    elif issues:
        status = "Datenqualität der lokalen Lernhistorien eingeschränkt. Einzelne Einträge werden ignoriert, fehlende Werte nicht geschätzt."
    elif len(evaluated_cases) < 20:
        status = "Lokale Lernhistorien lesbar, aber Datenbasis für belastbare Lernhinweise noch zu klein."
    else:
        status = "Lokale Lernhistorien lesbar. Lernhinweise bleiben trotzdem nur Kontext und ändern keine Gewichtungen automatisch."
    return status, rows


def local_history_quality_context(quality_rows: list[dict[str, str]]) -> tuple[str, str]:
    if not quality_rows:
        return "Daten nicht verfügbar", "Keine lokale Historienqualitätsprüfung vorhanden."
    if all(row.get("Einträge") == "0" for row in quality_rows):
        return "Keine Historie", "Es gibt noch keine lokalen Lernhistorien; Confidence und Kalibrierung bleiben explorativ."
    limited = [row for row in quality_rows if str(row.get("Datenqualität") or "").lower().startswith("eingeschr")]
    if limited:
        names = ", ".join(row.get("Historie", "Unbekannt") for row in limited[:3])
        return "Eingeschränkt", f"Eingeschränkte lokale Historienqualität bei {names}; Lern- und Confidence-Hinweise vorsichtig interpretieren."
    return "OK", "Lokale Lernhistorien sind strukturell lesbar; Gewichtungen ändern sich trotzdem nicht automatisch."


@st.cache_data(ttl=30 * 60)
def backtest_signal_buckets(df: pd.DataFrame, profile: AssetProfile) -> tuple[str, list[dict[str, str]]]:
    required_columns = {"Close", "Low", "High"}
    if df.empty or not required_columns.issubset(df.columns):
        return "Backtest nicht möglich: Kursdaten unvollständig.", [
            {
                "Zeithorizont": "Daten nicht verfügbar",
                "Asset-Typ": profile.asset_type,
                "Marktphase": "Daten nicht verfügbar",
                "Kaufsignal-Bucket": "Daten nicht verfügbar",
                "RSI-Bucket": "Daten nicht verfügbar",
                "MACD-Bucket": "Daten nicht verfügbar",
                "CRV-Bucket": "Daten nicht verfügbar",
                "Fälle": "0",
                "Trefferquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Max. Drawdown": "Datenbasis zu klein",
                "Bedeutung": "Für einen Backtest werden historische Close-, Low- und High-Daten benötigt.",
            }
        ]

    clean = df.dropna(subset=["Close"]).copy()
    horizons = {"1m": 20, "3m": 60, "6m": 120, "12m": 240}
    min_history = 220
    if len(clean) < min_history + 20:
        return "Backtest nicht möglich: weniger als 240 Handelstage verfügbar.", [
            {
                "Zeithorizont": "Daten nicht verfügbar",
                "Asset-Typ": profile.asset_type,
                "Marktphase": "Daten nicht verfügbar",
                "Kaufsignal-Bucket": "Daten nicht verfügbar",
                "RSI-Bucket": "Daten nicht verfügbar",
                "MACD-Bucket": "Daten nicht verfügbar",
                "CRV-Bucket": "Daten nicht verfügbar",
                "Fälle": "0",
                "Trefferquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Max. Drawdown": "Datenbasis zu klein",
                "Bedeutung": "Die App benötigt genug Historie, damit 50er/200er-Durchschnitt und spätere Kursfolgen ohne Schätzung berechnet werden können.",
            }
        ]

    last_entry_index = len(clean) - 21
    step = max(5, (last_entry_index - min_history) // 80) if last_entry_index > min_history else 5
    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, float]]] = {}
    tested_points = 0

    for idx in range(min_history, last_entry_index + 1, step):
        history = clean.iloc[: idx + 1].copy()
        latest = history.iloc[-1]
        close = value_or_none(latest.get("Close"))
        if close is None or close <= 0:
            continue
        supports = local_levels(history["Low"], "support") if "Low" in history else []
        resistances = local_levels(history["High"], "resistance") if "High" in history else []
        score_result = calculate_score_v2(history, supports, resistances)
        market_phase = detect_market_phase(history)
        risk_reward = calculate_risk_reward(float(close), supports, resistances)
        buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, profile)
        bucket = score_bucket(buy_signal.score)
        phase = market_phase.phase
        rsi_signal = rsi_bucket(latest.get("RSI_14"))
        macd_signal = macd_bucket(latest.get("MACD"), latest.get("MACD_Signal"))
        crv_signal = crv_bucket(risk_reward.ratio)
        tested_points += 1

        for label, days in horizons.items():
            future_idx = idx + days
            if future_idx >= len(clean):
                continue
            future_close = value_or_none(clean.iloc[future_idx].get("Close"))
            if future_close is None:
                continue
            future_window = clean.iloc[idx + 1 : future_idx + 1]
            future_low = value_or_none(future_window["Low"].min()) if "Low" in future_window else None
            max_drawdown = None if future_low is None else (float(future_low) - float(close)) / float(close) * 100
            grouped.setdefault((label, phase, bucket, rsi_signal, macd_signal, crv_signal), []).append(
                {
                    "return_pct": (float(future_close) - float(close)) / float(close) * 100,
                    "drawdown_pct": max_drawdown if max_drawdown is not None else 0.0,
                }
            )

    if not grouped:
        return "Backtest nicht möglich: keine vollständigen historischen Einstiegs- und Ausstiegspunkte gefunden.", [
            {
                "Zeithorizont": "Daten nicht verfügbar",
                "Asset-Typ": profile.asset_type,
                "Marktphase": "Daten nicht verfügbar",
                "Kaufsignal-Bucket": "Daten nicht verfügbar",
                "RSI-Bucket": "Daten nicht verfügbar",
                "MACD-Bucket": "Daten nicht verfügbar",
                "CRV-Bucket": "Daten nicht verfügbar",
                "Fälle": "0",
                "Trefferquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Max. Drawdown": "Datenbasis zu klein",
                "Bedeutung": "Es wurden keine vollständigen Kursfolgen gefunden; fehlende Daten werden nicht geschätzt.",
            }
        ]

    rows: list[dict[str, str]] = []
    for label in horizons:
        grouped_keys = sorted(
            [key for key in grouped if key[0] == label],
            key=lambda key: (key[1], {"hoch": 0, "mittel": 1, "niedrig": 2}.get(key[2], 3)),
        )
        for _, phase, bucket, rsi_signal, macd_signal, crv_signal in grouped_keys:
            values = grouped.get((label, phase, bucket, rsi_signal, macd_signal, crv_signal), [])
            if not values:
                continue
            count = len(values)
            returns = [item["return_pct"] for item in values]
            drawdowns = [item["drawdown_pct"] for item in values]
            hit_rate = sum(1 for value in returns if value > 0) / count * 100
            avg_return = float(np.mean(returns))
            max_drawdown = float(np.min(drawdowns))
            permission, meaning = calibration_permission(count)
            history_status, learning_hint = backtest_confidence_context(count, hit_rate, avg_return)
            rows.append(
                {
                    "Zeithorizont": label,
                    "Asset-Typ": profile.asset_type,
                    "Marktphase": phase,
                    "Kaufsignal-Bucket": bucket,
                    "RSI-Bucket": rsi_signal,
                    "MACD-Bucket": macd_signal,
                    "CRV-Bucket": crv_signal,
                    "Fälle": str(count),
                    "Trefferquote": "Datenbasis zu klein" if count < 20 else f"{hit_rate:.1f}%",
                    "Durchschnittsrendite": "Datenbasis zu klein" if count < 20 else f"{avg_return:+.2f}%",
                    "Max. Drawdown": "Datenbasis zu klein" if count < 20 else f"{max_drawdown:+.2f}%",
                    "Status": permission,
                    "Historienstatus": history_status,
                    "Lernhinweis": learning_hint,
                    "Bedeutung": f"{meaning} Backtest nutzt nur historische Kursdaten und ändert keine Gewichtungen automatisch.",
                }
            )

    status = (
        f"Backtest-Basis aus {tested_points} historischen Analysepunkten. "
        "Ergebnis ist ein Signaltest, keine Handelsstrategie und keine Kauf-/Verkaufsautomatisierung."
    )
    return status, rows


def percent_value(text: str) -> float | None:
    if not isinstance(text, str):
        return None
    cleaned = text.replace("%", "").replace("+", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def row_value(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return str(value)
    for key, value in row.items():
        normalized = str(key).lower()
        if any(alias.lower() in normalized for alias in keys):
            return str(value)
    return None


def backtest_confidence_context(count: int, hit_rate: float | None = None, avg_return: float | None = None) -> tuple[str, str]:
    if count < 20:
        return (
            "Datenbasis zu klein",
            "Unter 20 historischen Fällen wird diese Backtest-Gruppe nur gezählt und nicht als belastbarer Lernhinweis genutzt.",
        )
    if count <= 50:
        direction = "neutral"
        if hit_rate is not None and avg_return is not None:
            if hit_rate >= 55 and avg_return > 0:
                direction = "positiv"
            elif hit_rate < 45 or avg_return < 0:
                direction = "negativ"
        return (
            f"Vorsichtiger Lernhinweis ({direction})",
            "20 bis 50 Fälle liefern Kontext für Confidence und Lernsystem, aber noch keinen automatischen Kalibrierungsgrund.",
        )
    direction = "neutral"
    if hit_rate is not None and avg_return is not None:
        if hit_rate >= 55 and avg_return > 0:
            direction = "positiv"
        elif hit_rate < 45 or avg_return < 0:
            direction = "negativ"
    return (
        f"Belastbarer Lernkontext ({direction})",
        "Über 50 Fälle dürfen als manueller Kalibrierungshinweis geprüft werden; Gewichtungen ändern sich nicht automatisch.",
    )


def backtest_compact_rows(backtest_rows: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    valid: list[dict] = []
    for row in backtest_rows:
        count = value_or_none(row_value(row, "Fälle", "Faelle", "Falle"))
        hit_rate = percent_value(row_value(row, "Trefferquote") or "")
        avg_return = percent_value(row_value(row, "Durchschnittsrendite") or "")
        drawdown = percent_value(row_value(row, "Max. Drawdown", "Drawdown") or "")
        if count is None or count < 20 or hit_rate is None or avg_return is None or drawdown is None:
            continue
        valid.append(
            {
                "row": row,
                "count": int(count),
                "hit_rate": hit_rate,
                "avg_return": avg_return,
                "drawdown": drawdown,
            }
        )

    if not valid:
        return "Kompaktansicht nicht verfügbar: keine Backtest-Gruppe mit mindestens 20 Fällen.", [
            {
                "Einordnung": "Datenbasis zu klein",
                "Gruppe": "Daten nicht verfügbar",
                "Fälle": "0",
                "Trefferquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Max. Drawdown": "Datenbasis zu klein",
                "Bedeutung": "Die App verdichtet Backtests erst ab mindestens 20 Fällen pro Gruppe.",
            }
        ]

    def group_label(item: dict) -> str:
        row = item["row"]
        return (
            f"{row.get('Zeithorizont')} | {row.get('Marktphase')} | "
            f"Kauf {row.get('Kaufsignal-Bucket')} | RSI {row.get('RSI-Bucket')} | "
            f"MACD {row.get('MACD-Bucket')} | CRV {row.get('CRV-Bucket')}"
        )

    best = max(valid, key=lambda item: (item["hit_rate"], item["avg_return"], item["count"]))
    weakest = min(valid, key=lambda item: (item["avg_return"], item["hit_rate"]))
    drawdown_risk = min(valid, key=lambda item: (item["drawdown"], item["avg_return"]))
    largest = max(valid, key=lambda item: item["count"])
    summary_items = [
        ("Beste Trefferquote", best, "Diese Gruppe hatte historisch die höchste Trefferquote unter den belastbaren Gruppen."),
        ("Schwächste Rendite", weakest, "Diese Gruppe hatte historisch die schwächste Durchschnittsrendite und sollte vorsichtig interpretiert werden."),
        ("Größter Drawdown", drawdown_risk, "Diese Gruppe hatte historisch den stärksten zwischenzeitlichen Rückgang."),
        ("Größte Datenbasis", largest, "Diese Gruppe hat die meisten historischen Fälle und ist deshalb statistisch am wenigsten dünn."),
    ]
    rows = []
    for title, item, meaning in summary_items:
        row = item["row"]
        rows.append(
            {
                "Einordnung": title,
                "Gruppe": group_label(item),
                "Fälle": str(item["count"]),
                "Trefferquote": row.get("Trefferquote", "Datenbasis zu klein"),
                "Durchschnittsrendite": row.get("Durchschnittsrendite", "Datenbasis zu klein"),
                "Max. Drawdown": row.get("Max. Drawdown", "Datenbasis zu klein"),
                "Historienstatus": row.get("Historienstatus", backtest_confidence_context(item["count"], item["hit_rate"], item["avg_return"])[0]),
                "Bedeutung": meaning,
            }
        )
    return f"Kompaktansicht aus {len(valid)} belastbaren Backtest-Gruppen.", rows


def backtest_group_label(record: dict, row: dict[str, str]) -> str:
    symbol = str(record.get("symbol") or "Unbekannt")
    horizon = row_value(row, "Zeithorizont") or "Unbekannt"
    phase = row_value(row, "Marktphase") or "Unbekannt"
    buy_bucket = row_value(row, "Kaufsignal-Bucket") or "Unbekannt"
    rsi_signal = row_value(row, "RSI-Bucket") or "Unbekannt"
    macd_signal = row_value(row, "MACD-Bucket") or "Unbekannt"
    crv_signal = row_value(row, "CRV-Bucket") or "Unbekannt"
    return f"{symbol} | {horizon} | {phase} | Kauf {buy_bucket} | RSI {rsi_signal} | MACD {macd_signal} | CRV {crv_signal}"


def backtest_history_learning_rows(history: list[dict]) -> tuple[str, list[dict[str, str]]]:
    groups: list[dict] = []
    for record in history:
        rows = record.get("rows", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            count = value_or_none(row_value(row, "Fälle", "Faelle", "Falle"))
            hit_rate = percent_value(row_value(row, "Trefferquote") or "")
            avg_return = percent_value(row_value(row, "Durchschnittsrendite") or "")
            drawdown = percent_value(row_value(row, "Max. Drawdown", "Drawdown") or "")
            if count is None or count < 20 or hit_rate is None or avg_return is None or drawdown is None:
                continue
            groups.append(
                {
                    "record": record,
                    "row": row,
                    "count": int(count),
                    "hit_rate": hit_rate,
                    "avg_return": avg_return,
                    "drawdown": drawdown,
                }
            )

    if not history:
        return "Keine gespeicherte Backtest-Historie vorhanden.", [
            {
                "Messpunkt": "Gespeicherte Backtests",
                "Wert": "0",
                "Bedeutung": "Speichere zuerst ein Backtest-Ergebnis im Analyse-Detailbereich. Es wird keine Order ausgelöst.",
            },
            {
                "Messpunkt": "Kalibrierungsregel",
                "Wert": "Keine Kalibrierung",
                "Bedeutung": "Ohne gespeicherte Backtests bleibt dieser Lernkontext leer.",
            },
        ]

    if not groups:
        return "Backtest-Historie vorhanden, aber noch keine belastbare Gruppe mit mindestens 20 Fällen.", [
            {
                "Messpunkt": "Gespeicherte Backtests",
                "Wert": str(len(history)),
                "Bedeutung": "Die gespeicherten Tabellen enthalten noch keine Gruppe mit mindestens 20 Fällen und vollständig berechenbaren Kennzahlen.",
            },
            {
                "Messpunkt": "Belastbare Gruppen",
                "Wert": "0",
                "Bedeutung": "Unter 20 Fällen bleibt die App bewusst bei `Datenbasis zu klein`.",
            },
            {
                "Messpunkt": "Kalibrierungsregel",
                "Wert": "Keine Kalibrierung",
                "Bedeutung": "Backtests werden nur angezeigt; Score-Gewichtungen ändern sich nie automatisch.",
            },
        ]

    total_cases = sum(group["count"] for group in groups)
    weighted_hit_rate = sum(group["hit_rate"] * group["count"] for group in groups) / total_cases
    weighted_return = sum(group["avg_return"] * group["count"] for group in groups) / total_cases
    worst_drawdown = min(group["drawdown"] for group in groups)
    best = max(groups, key=lambda group: (group["hit_rate"], group["avg_return"], group["count"]))
    weakest = min(groups, key=lambda group: (group["avg_return"], group["hit_rate"]))
    permission, meaning = calibration_permission(total_cases)
    history_status, learning_hint = backtest_confidence_context(total_cases, weighted_hit_rate, weighted_return)
    if total_cases < 20:
        status = "Datenbasis zu klein. Backtest-Historie wird nur gezählt."
    elif total_cases <= 50:
        status = "Vorsichtiger Backtest-Lernkontext möglich. Gewichtungen bleiben unverändert."
    else:
        status = "Backtest-Lernkontext verfügbar. Änderungen bleiben manuell, dokumentations- und testpflichtig."

    rows = [
        {
            "Messpunkt": "Gespeicherte Backtests",
            "Wert": str(len(history)),
            "Bedeutung": "Lokale Backtest-Datei; keine Brokerdaten und keine Kauf-/Verkaufsautomatisierung.",
        },
        {
            "Messpunkt": "Belastbare Gruppen",
            "Wert": str(len(groups)),
            "Bedeutung": "Nur Gruppen mit mindestens 20 Fällen und vollständigen Kennzahlen werden interpretiert.",
        },
        {
            "Messpunkt": "Backtest-Fälle",
            "Wert": str(total_cases),
            "Bedeutung": "Summe der historischen Fälle aus gespeicherten Backtest-Gruppen; kann Überschneidungen enthalten.",
        },
        {
            "Messpunkt": "Gewichtete Trefferquote",
            "Wert": "Datenbasis zu klein" if total_cases < 20 else f"{weighted_hit_rate:.1f}%",
            "Bedeutung": "Nach Fallzahl gewichtete Trefferquote der gespeicherten Backtest-Gruppen.",
        },
        {
            "Messpunkt": "Gewichtete Durchschnittsrendite",
            "Wert": "Datenbasis zu klein" if total_cases < 20 else f"{weighted_return:+.2f}%",
            "Bedeutung": "Nach Fallzahl gewichtete Durchschnittsrendite; fehlende Daten werden nicht geschätzt.",
        },
        {
            "Messpunkt": "Schwächster Drawdown",
            "Wert": "Datenbasis zu klein" if total_cases < 20 else f"{worst_drawdown:.2f}%",
            "Bedeutung": "Stärkster historischer Rückgang innerhalb der gespeicherten Backtest-Gruppen.",
        },
        {
            "Messpunkt": "Beste gespeicherte Gruppe",
            "Wert": backtest_group_label(best["record"], best["row"]),
            "Bedeutung": f"{best['hit_rate']:.1f}% Treffer, {best['avg_return']:+.2f}% Ø, {best['count']} Fälle.",
        },
        {
            "Messpunkt": "Schwächste gespeicherte Gruppe",
            "Wert": backtest_group_label(weakest["record"], weakest["row"]),
            "Bedeutung": f"{weakest['hit_rate']:.1f}% Treffer, {weakest['avg_return']:+.2f}% Ø, {weakest['count']} Fälle.",
        },
        {
            "Messpunkt": "Confidence-Kontext",
            "Wert": history_status,
            "Bedeutung": learning_hint,
        },
        {
            "Messpunkt": "Kalibrierungsregel",
            "Wert": permission,
            "Bedeutung": f"{meaning} Backtests verändern keine Gewichtung automatisch.",
        },
    ]
    return status, rows


def build_backtest_record(
    symbol: str,
    asset_identity: dict,
    asset_profile: AssetProfile,
    backtest_status: str,
    backtest_rows: list[dict[str, str]],
    analysis_history_label: str,
) -> dict:
    return {
        "created_at": pd.Timestamp.now().isoformat(),
        "symbol": symbol,
        "name": asset_identity.get("name", symbol),
        "asset_type": asset_profile.asset_type,
        "analysis_history": analysis_history_label,
        "status": backtest_status,
        "rows": backtest_rows,
        "note": "Backtest speichert nur historische Signal-Auswertung. Keine Brokerdaten, keine Order, keine Kauf- oder Verkaufsautomatisierung.",
    }


def similar_setup_rows(
    asset_profile: AssetProfile,
    market_phase: MarketPhase,
    action: str,
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
    history_quality_rows: list[dict[str, str]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    target_family = action_family(action)
    target_buy_bucket = score_bucket(buy_signal.score)
    target_quality_bucket = score_bucket(asset_quality.score)
    similar: list[dict] = []
    for case in cases:
        similarity_points = 0
        if case["asset_type"] == asset_profile.asset_type:
            similarity_points += 2
        if case["action_family"] == target_family:
            similarity_points += 2
        if case["market_phase"] == market_phase.phase:
            similarity_points += 1
        if case["buy_signal_bucket"] == target_buy_bucket:
            similarity_points += 1
        if case["quality_bucket"] == target_quality_bucket:
            similarity_points += 1
        if similarity_points >= 4:
            similar.append(case)

    count = len(similar)
    if count < 20:
        status = "Datenbasis zu klein. Ähnliche historische Setups werden gezählt, aber noch nicht zur Kalibrierung verwendet."
        permission = "Keine Kalibrierung"
    elif count <= 50:
        status = "Vorsichtige Hinweise aus ähnlichen Setups möglich. Gewichtungen bleiben unverändert."
        permission = "Nur Hinweis"
    else:
        status = "Ausreichend ähnliche Setups für belastbarere Hinweise. Gewichtungen werden trotzdem nicht automatisch geändert."
        permission = "Vorschläge möglich"

    hit_rate = None if count == 0 else sum(1 for case in similar if case["hit"]) / count * 100
    avg_return = None if count == 0 else float(np.mean([case["return_pct"] for case in similar]))
    quality_status, quality_hint = local_history_quality_context(history_quality_rows or [])
    rows = [
        {"Messpunkt": "Alle ausgewerteten Historienfälle", "Wert": str(len(cases)), "Bedeutung": "Basis aus Trade-Journal, Forward-Tests, Entscheidungen und Prognosen."},
        {"Messpunkt": "Datenqualität lokaler Historien", "Wert": quality_status, "Bedeutung": quality_hint},
        {"Messpunkt": "Ähnliche Setups", "Wert": str(count), "Bedeutung": f"Ähnlichkeit nach Asset-Typ, Aktion, Marktphase, Kaufsignal und Asset-Qualität. {status}"},
        {"Messpunkt": "Trefferquote ähnlicher Setups", "Wert": "Datenbasis zu klein" if hit_rate is None or count < 20 else f"{hit_rate:.1f}%", "Bedeutung": "Treffer wird gegen die damalige Empfehlung gemessen; keine automatische Gewichtungsänderung."},
        {"Messpunkt": "Durchschnittsrendite ähnlicher Setups", "Wert": "Datenbasis zu klein" if avg_return is None or count < 20 else f"{avg_return:+.2f}%", "Bedeutung": "Nur echte ausgewertete Kursdaten; keine fehlenden Renditen geschätzt."},
        {"Messpunkt": "Mindestdatenmenge", "Wert": "20 ähnliche Setups", "Bedeutung": "Unter 20 ähnlichen Fällen bleibt die Aussage rein explorativ."},
        {"Messpunkt": "Kalibrierungsregel", "Wert": permission, "Bedeutung": "Version 1 ändert Score-Gewichtungen niemals automatisch."},
    ]
    context_fields = [
        ("Szenario-Lesart", "scenario_read"),
        ("Fehlursache", "miss_reason"),
        ("Decision-Alignment", "decision_alignment"),
        ("Historienstatus", "history_status"),
        ("Kalibrierungskontext", "calibration_context"),
        ("Kalibrierungshinweis", "calibration_hint"),
    ]
    for label, key in context_fields:
        values = [
            str(case.get(key))
            for case in similar
            if str(case.get(key) or "").lower() not in {"", "none", "daten nicht verfügbar"}
        ]
        if values:
            top_value = max(set(values), key=values.count)
            rows.append(
                {
                    "Messpunkt": f"Häufigster Kontext: {label}",
                    "Wert": top_value,
                    "Bedeutung": f"{values.count(top_value)} ähnliche Fälle mit diesem Kontext; nur Hinweis, keine automatische Gewichtung.",
                }
            )
    rows.extend(signal_calibration_rows(similar))
    return status, rows

def similar_setup_statistics(
    asset_type: str,
    market_phase: str,
    direction: str,
    buy_signal_score: float | None,
) -> dict[str, str | int | float | None]:
    bucket = signal_bucket(buy_signal_score)
    evaluated = historical_review_cases()
    similar = [
        case
        for case in evaluated
        if case["asset_type"] == asset_type
        and (case["market_phase"] == market_phase or case["signal_bucket"] == bucket or case["direction"] == direction)
    ]
    count = len(similar)
    hits = sum(1 for case in similar if case["hit"])
    hit_rate = round(hits / count * 100, 1) if count else None
    if count < 20:
        status = "Datenbasis zu klein"
        summary = f"Ähnliche historische Setups: {count}. Datenbasis zu klein; Trefferquote wird nicht als belastbar gewertet."
    elif count <= 50:
        status = "vorsichtiger Hinweis"
        summary = f"Ähnliche historische Setups: {count}, Trefferquote {hit_rate:.1f} %. Nur vorsichtig interpretieren; Gewichtungen bleiben unverändert."
    else:
        status = "belastbarer Hinweis"
        summary = f"Ähnliche historische Setups: {count}, Trefferquote {hit_rate:.1f} %. Kalibrierungsvorschläge wären erlaubt, aber keine automatische Anpassung."
    return {"count": count, "hits": hits, "hit_rate": hit_rate, "status": status, "summary": summary}

def calibration_status_rows(
    trade_history: list[dict],
    forward_tests: list[dict] | None = None,
    decisions: list[dict] | None = None,
    predictions: list[dict] | None = None,
    history_quality_rows: list[dict[str, str]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    forward_tests = forward_tests or []
    decisions = decisions or []
    predictions = predictions or []
    completed_reviews = count_completed_reviews(forward_tests) + count_completed_reviews(predictions)
    cases = len(trade_history) + len(forward_tests) + len(decisions) + len(predictions) + completed_reviews
    if cases < 20:
        status = "Datenbasis zu klein. Score-Gewichtungen werden nicht angepasst."
        permission = "Keine Kalibrierung erlaubt"
    elif cases <= 50:
        status = "Vorsichtige Hinweise möglich. Score-Gewichtungen bleiben unverändert."
        permission = "Nur Hinweise"
    else:
        status = "Kalibrierungsvorschläge erlaubt. Änderungen müssen dokumentiert und getestet werden."
        permission = "Vorschläge erlaubt"
    quality_status, quality_hint = local_history_quality_context(history_quality_rows or [])
    if quality_status == "Eingeschränkt":
        status = f"{status} Lokale Historienqualität eingeschränkt."

    rows = [
        {"Messpunkt": "Dokumentierte Fälle gesamt", "Wert": str(cases), "Bedeutung": status},
        {"Messpunkt": "Datenqualität lokaler Historien", "Wert": quality_status, "Bedeutung": quality_hint},
        {"Messpunkt": "Forward-Tests", "Wert": str(len(forward_tests)), "Bedeutung": f"Ausgewertete Zeiträume: {count_completed_reviews(forward_tests)}."},
        {"Messpunkt": "Entscheidungen", "Wert": str(len(decisions)), "Bedeutung": "Nutzerentscheidungen für spätere Opportunitätskostenanalyse."},
        {"Messpunkt": "Prognosen", "Wert": str(len(predictions)), "Bedeutung": f"Ausgewertete Zeiträume: {count_completed_reviews(predictions)}."},
        {"Messpunkt": "Mindestdatenmenge", "Wert": "20 Fälle", "Bedeutung": "Darunter sind Trefferquoten statistisch zu dünn."},
        {"Messpunkt": "Kalibrierungsregel", "Wert": permission, "Bedeutung": "Version 1 ändert Gewichtungen niemals automatisch."},
    ]
    return status, rows


def learning_guardrail_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    decisions: list[dict],
    predictions: list[dict],
    history_quality_rows: list[dict[str, str]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    evaluated_cases = evaluated_history_cases(trade_history, forward_tests, predictions, decisions)
    documented_cases = len(trade_history) + len(forward_tests) + len(decisions) + len(predictions)
    evaluated_count = len(evaluated_cases)
    if evaluated_count < 20:
        status = "Lernmodus: nur sammeln. Datenbasis zu klein für belastbare Trefferquoten."
        permission = "Keine Kalibrierung"
    elif evaluated_count <= 50:
        status = "Lernmodus: vorsichtige Hinweise erlaubt. Gewichtungen bleiben unverändert."
        permission = "Vorsichtige Hinweise"
    else:
        status = "Lernmodus: manuelle Kalibrierungsvorschläge erlaubt. Änderungen bleiben dokumentations- und testpflichtig."
        permission = "Manuelle Vorschläge erlaubt"

    rows = [
        {
            "Regel": "Dokumentierte Fälle",
            "Status": str(documented_cases),
            "Bedeutung": "Gespeicherte Trade-, Forward-, Decision- und Prognoseeinträge. Nicht jeder Eintrag ist schon ausgewertet.",
        },
        {
            "Regel": "Ausgewertete Fälle",
            "Status": str(evaluated_count),
            "Bedeutung": "Nur Fälle mit echter Review-Auswertung und Rendite/Hit werden für Trefferquoten genutzt.",
        },
        {
            "Regel": "Unter 20 Fällen",
            "Status": "Nur zählen",
            "Bedeutung": "Keine belastbaren Trefferquoten und keine Kalibrierungsvorschläge.",
        },
        {
            "Regel": "20 bis 50 Fälle",
            "Status": "Vorsichtige Hinweise",
            "Bedeutung": "Auffälligkeiten dürfen angezeigt werden, aber nicht als robuste Regel gelten.",
        },
        {
            "Regel": "Über 50 Fälle",
            "Status": "Manuelle Vorschläge erlaubt",
            "Bedeutung": "Kalibrierungsvorschläge sind erlaubt, müssen aber dokumentiert und getestet werden.",
        },
        {
            "Regel": "Automatische Gewichtungsänderung",
            "Status": "Nein",
            "Bedeutung": "Das Lernsystem analysiert nur. Es verändert keine Score-Gewichtungen, keine Kaufsignal-Schwellen und keine Portfolio-Logik automatisch.",
        },
        {
            "Regel": "Aktuelle Freigabe",
            "Status": permission,
            "Bedeutung": status,
        },
    ]
    return status, rows


def signal_learning_rows(forward_tests: list[dict], predictions: list[dict]) -> tuple[str, list[dict[str, str]]]:
    evaluated: list[dict] = []
    for item in [*forward_tests, *predictions]:
        review_after = item.get("review_after", {})
        if not isinstance(review_after, dict):
            continue
        for period, result in review_after.items():
            if isinstance(result, dict):
                evaluated.append({"period": period, "record": item, "result": result})

    count = len(evaluated)
    if count < 20:
        status = "Datenbasis zu klein. Signalanalyse zeigt nur den Sammelstand."
    elif count <= 50:
        status = "Vorsichtige Hinweise möglich. Noch keine automatischen Gewichtungsänderungen."
    else:
        status = "Datenbasis groß genug für Kalibrierungsvorschläge. Änderungen bleiben manuell und testpflichtig."

    positive = sum(1 for item in evaluated if value_or_none(item["result"].get("return_pct")) is not None and float(item["result"].get("return_pct")) > 0)
    negative = sum(1 for item in evaluated if value_or_none(item["result"].get("return_pct")) is not None and float(item["result"].get("return_pct")) <= 0)
    rows = [
        {"Signal": "Ausgewertete Fälle", "Wert": str(count), "Hinweis": status},
        {"Signal": "Positive Ausgänge", "Wert": str(positive), "Hinweis": "Rendite über 0 % im jeweiligen Auswertungszeitraum."},
        {"Signal": "Negative Ausgänge", "Wert": str(negative), "Hinweis": "Rendite bei oder unter 0 % im jeweiligen Auswertungszeitraum."},
    ]

    if count >= 20:
        by_asset: dict[str, list[float]] = {}
        by_module: dict[str, list[float]] = {}
        by_scenario: dict[str, list[float]] = {}
        by_miss_reason: dict[str, list[float]] = {}
        for item in evaluated:
            asset_type = str(item["record"].get("asset_type") or "Unbekannt")
            return_pct = value_or_none(item["result"].get("return_pct"))
            if return_pct is not None:
                return_value = float(return_pct)
                by_asset.setdefault(asset_type, []).append(return_value)
                scenario_read = item["result"].get("scenario_read")
                if scenario_read:
                    by_scenario.setdefault(str(scenario_read), []).append(return_value)
                miss_reason = item["result"].get("miss_reason")
                if miss_reason and return_value <= 0:
                    by_miss_reason.setdefault(str(miss_reason), []).append(return_value)
                module_scores = item["record"].get("module_scores")
                if isinstance(module_scores, list):
                    for module in module_scores:
                        if not isinstance(module, dict):
                            continue
                        name = str(module.get("name") or "Unbekanntes Modul")
                        by_module.setdefault(f"{name} ({score_bucket(module.get('score'))})", []).append(return_value)
        for asset_type, values in sorted(by_asset.items()):
            hit_rate = sum(1 for value in values if value > 0) / len(values) * 100
            rows.append(
                {
                    "Signal": f"Trefferquote {asset_type}",
                    "Wert": f"{hit_rate:.1f}%",
                    "Hinweis": f"{len(values)} ausgewertete Fälle; nur Hinweis, keine automatische Gewichtung.",
                }
            )
        for scenario, values in sorted(by_scenario.items()):
            hit_rate = sum(1 for value in values if value > 0) / len(values) * 100
            rows.append(
                {
                    "Signal": f"Szenario-Lesart {scenario}",
                    "Wert": f"{hit_rate:.1f}%",
                    "Hinweis": f"{len(values)} ausgewertete Fälle; Szenario-Lesart stammt aus echter Kursauswertung.",
                }
            )
        for module_bucket, values in sorted(by_module.items()):
            hit_rate = sum(1 for value in values if value > 0) / len(values) * 100
            rows.append(
                {
                    "Signal": f"Modulgruppe {module_bucket}",
                    "Wert": f"{hit_rate:.1f}%",
                    "Hinweis": f"{len(values)} ausgewertete Fälle; Modulgruppen ändern Gewichtungen nicht automatisch.",
                }
            )
        for reason, values in sorted(by_miss_reason.items()):
            rows.append(
                {
                    "Signal": f"Fehlursache {reason}",
                    "Wert": str(len(values)),
                    "Hinweis": "Nur aus negativen ausgewerteten Prognosen; keine automatische Gewichtungsänderung.",
                }
            )
    return status, rows


def prediction_hit_rate_rows(predictions: list[dict]) -> tuple[str, list[dict[str, str]]]:
    evaluated: list[dict] = []
    for record in predictions:
        if not isinstance(record, dict):
            continue
        for period, result in review_results(record):
            hit = setup_result_is_hit(result)
            return_pct = value_or_none(result.get("return_pct")) if isinstance(result, dict) else None
            if hit is None or return_pct is None:
                continue
            evaluated.append({"record": record, "period": period, "hit": hit, "return_pct": float(return_pct)})

    if not evaluated:
        return "Keine ausgewerteten Prognosen vorhanden.", [
            {
                "Dimension": "Gesamt",
                "Gruppe": "Daten nicht verfügbar",
                "Fälle": "0",
                "Trefferquote": "Datenbasis zu klein",
                "Durchschnittsrendite": "Datenbasis zu klein",
                "Bedeutung": "Prognosen werden erst nach echter Kursauswertung berücksichtigt.",
            }
        ]

    status = (
        "Datenbasis zu klein. Prognose-Trefferquoten werden gezählt, aber noch nicht belastbar interpretiert."
        if len(evaluated) < 20
        else "Vorsichtige Prognose-Trefferquoten möglich. Gewichtungen werden nicht automatisch geändert."
        if len(evaluated) <= 50
        else "Prognose-Datenbasis groß genug für manuelle Kalibrierungshinweise. Gewichtungen bleiben testpflichtig."
    )

    grouped: dict[tuple[str, str], list[dict]] = {}
    for case in evaluated:
        record = case["record"]
        grouped.setdefault(("Asset-Typ", str(record.get("asset_type") or "Unbekannt")), []).append(case)
        review_after = record.get("review_after", {})
        period_result = review_after.get(case["period"]) if isinstance(review_after, dict) else None
        if isinstance(period_result, dict):
            scenario_read = period_result.get("scenario_read")
            if scenario_read:
                grouped.setdefault(("Szenario-Lesart", str(scenario_read)), []).append(case)
            miss_reason = period_result.get("miss_reason")
            if miss_reason and not case["hit"]:
                grouped.setdefault(("Fehlursache", str(miss_reason)), []).append(case)
        module_scores = record.get("module_scores")
        if isinstance(module_scores, list):
            for module in module_scores:
                if not isinstance(module, dict):
                    continue
                name = str(module.get("name") or "Unbekanntes Modul")
                bucket = score_bucket(module.get("score"))
                grouped.setdefault(("Modul", f"{name} ({bucket})"), []).append(case)
        else:
            signal_snapshot = record.get("signal_snapshot")
            if isinstance(signal_snapshot, dict):
                for name, bucket in signal_snapshot.items():
                    grouped.setdefault(("Signal", f"{name} ({bucket})"), []).append(case)

    rows: list[dict[str, str]] = []
    for (dimension, group), cases in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        count = len(cases)
        hit_rate = sum(1 for case in cases if case["hit"]) / count * 100
        avg_return = float(np.mean([case["return_pct"] for case in cases]))
        if count < 20:
            interpretation = "Datenbasis zu klein; nur Zählwert, keine Kalibrierung."
            hit_text = "Datenbasis zu klein"
            avg_text = "Datenbasis zu klein"
        elif count <= 50:
            interpretation = "Vorsichtiger Hinweis; keine automatische Gewichtungsänderung."
            hit_text = f"{hit_rate:.1f}%"
            avg_text = f"{avg_return:+.2f}%"
        else:
            interpretation = "Manueller Kalibrierungshinweis erlaubt; keine automatische Änderung."
            hit_text = f"{hit_rate:.1f}%"
            avg_text = f"{avg_return:+.2f}%"
        rows.append(
            {
                "Dimension": dimension,
                "Gruppe": group,
                "Fälle": str(count),
                "Trefferquote": hit_text,
                "Durchschnittsrendite": avg_text,
                "Bedeutung": interpretation,
            }
        )

    return status, rows


def evaluated_basic_history_cases(trade_history: list[dict], forward_tests: list[dict], predictions: list[dict]) -> list[dict]:
    cases: list[dict] = []
    for source, items in [("Trade Journal", trade_history), ("Forward-Test", forward_tests), ("Prognose", predictions)]:
        for item in items:
            review_after = item.get("review_after", {})
            if not isinstance(review_after, dict):
                continue
            for period, result in review_after.items():
                if isinstance(result, dict):
                    cases.append({"source": source, "period": period, "record": item, "result": result})
    return cases


def case_is_positive(case: dict) -> bool | None:
    result = case.get("result", {})
    if not isinstance(result, dict):
        return None
    if "target_hit" in result and result.get("target_hit") is True:
        return True
    if str(result.get("result", "")).lower() in {"treffer", "positiv", "positiv offen"}:
        return True
    return_pct = value_or_none(result.get("return_pct") or result.get("decision_return_pct"))
    if return_pct is None:
        return None
    return float(return_pct) > 0


def historical_confidence_rows(
    trade_history: list[dict],
    forward_tests: list[dict],
    predictions: list[dict],
    asset_profile: AssetProfile,
    market_phase: MarketPhase,
) -> tuple[str, list[dict[str, str]]]:
    cases = evaluated_basic_history_cases(trade_history, forward_tests, predictions)
    similar = [
        case for case in cases
        if str(case["record"].get("asset_type") or case["record"].get("Asset-Typ") or "").lower() == asset_profile.asset_type.lower()
        or str(case["record"].get("market_phase") or case["record"].get("Marktphase") or "") == market_phase.phase
    ]
    positives = [case for case in similar if case_is_positive(case) is True]
    evaluated = [case for case in similar if case_is_positive(case) is not None]
    count = len(evaluated)

    if count < 20:
        status = "Datenbasis zu klein. Confidence bleibt primär signalbasiert; historische Trefferquote wird noch nicht belastbar ausgewiesen."
        hit_rate_text = "Datenbasis zu klein"
    elif count <= 50:
        hit_rate = len(positives) / count * 100
        status = "Vorsichtige historische Einordnung möglich. Keine automatische Gewichtungsänderung."
        hit_rate_text = f"{hit_rate:.1f}%"
    else:
        hit_rate = len(positives) / count * 100
        status = "Historische Einordnung verfügbar. Gewichtungen bleiben trotzdem manuell und testpflichtig."
        hit_rate_text = f"{hit_rate:.1f}%"

    rows = [
        {"Kennzahl": "Ähnliche ausgewertete Setups", "Wert": str(count), "Bedeutung": "Gleicher Asset-Typ oder gleiche Marktphase aus lokaler Historie."},
        {"Kennzahl": "Historische Trefferquote", "Wert": hit_rate_text, "Bedeutung": status},
        {"Kennzahl": "Mindestdatenmenge", "Wert": "20 Fälle", "Bedeutung": "Darunter zeigt die App bewusst keine belastbare Trefferquote."},
        {"Kennzahl": "Automatische Gewichtung", "Wert": "Nein", "Bedeutung": "Historie erklärt Confidence, verändert aber keine Scores automatisch."},
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


def daily_chart_frame_from_analysis(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Reuse daily analysis history for the chart and avoid a duplicate Yahoo request."""
    if df.empty or period == "max":
        return df.copy()
    if period == "1d":
        return df.tail(1).copy()
    if period == "5d":
        return df.tail(5).copy()
    period_months = {"1mo": 1, "3mo": 3, "6mo": 6, "1y": 12, "5y": 60}
    months = period_months.get(period)
    if months is None:
        return df.copy()
    try:
        cutoff = pd.Timestamp(df.index.max()) - pd.DateOffset(months=months)
        return df.loc[pd.to_datetime(df.index) >= cutoff].copy()
    except (TypeError, ValueError):
        approximate_rows = {"1mo": 23, "3mo": 66, "6mo": 132, "1y": 264, "5y": 1320}
        return df.tail(approximate_rows[period]).copy()


def history_label_from_frame(df: pd.DataFrame, fallback: str) -> str:
    if df.empty:
        return fallback
    try:
        start = pd.Timestamp(df.index.min()).date()
        end = pd.Timestamp(df.index.max()).date()
        years = max((end - start).days / 365.25, 0)
        if years >= 1:
            return f"{years:.1f} Jahre ({start} bis {end})"
        days = max((end - start).days, 1)
        return f"{days} Tage ({start} bis {end})"
    except Exception:
        return fallback


def load_portfolio_file() -> tuple[dict | None, str | None]:
    return load_portfolio_document(PORTFOLIO_PATH)


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
    return calculate_position_market_value(position, latest_portfolio_price)


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
    return evaluate_portfolio_data(
        symbol,
        portfolio,
        asset_profile,
        position_value_loader=position_market_value,
    )


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


def score_crypto_fundamentals(info: dict, technical: ModuleScore, macro: ModuleScore, df: pd.DataFrame) -> ModuleScore:
    latest = df.iloc[-1]
    volatility = value_or_none(latest.get("Volatility"))
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))

    details = [
        data_coverage_detail(
            "Krypto-Spezialdaten",
            [
                ("Fear & Greed", None),
                ("ETF-Flows", None),
                ("On-Chain-Daten", None),
                ("Orderbuch-/Spread-Daten", None),
                ("Stablecoin-Liquidität", None),
                ("Volumenvergleich", volume if volume is not None and volume_avg is not None else None),
            ],
        ),
        score_neutrality_detail("Krypto-Spezialdaten"),
        "Bitcoin-Zyklus: wird im Research-Krypto-Zyklusmodul aus Halving-Zeitfenster und Marktdaten eingeordnet.",
        "Fear & Greed: Daten nicht verfügbar.",
        "ETF-Flows: Daten nicht verfügbar.",
        "On-Chain-Daten: Daten nicht verfügbar.",
        "Orderbuch-/Spread-Daten: Daten nicht verfügbar.",
        "Stablecoin-Liquidität: Daten nicht verfügbar.",
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


def score_asset_quality_from_info(symbol: str, profile: AssetProfile, df: pd.DataFrame, info: dict) -> ModuleScore:
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

        details.insert(
            0,
            data_coverage_detail(
                "Krypto-Asset-Qualität",
                [
                    ("Marktkapitalisierung", market_cap),
                    ("Volumenvergleich", volume if volume is not None and volume_avg is not None else None),
                    ("Volatilität", volatility),
                    ("Institutionelle Akzeptanz", None),
                    ("ETF-Flows", None),
                    ("On-Chain-Daten", None),
                ],
            ),
        )
        details.insert(1, score_neutrality_detail("Krypto-Asset-Qualität"))
        details.extend(
            [
                "Makroabhängigkeit: wird im Kaufsignal/Makro-Kontext betrachtet, nicht als langfristige Qualität erfunden.",
                "Institutionelle Akzeptanz: Daten nicht verfügbar.",
                "ETF-Flows: Daten nicht verfügbar.",
                "On-Chain-Daten: Daten nicht verfügbar.",
                "Entwickleraktivität, aktive Adressen, Hashrate oder Total Value Locked: Daten nicht verfügbar.",
            ]
        )
        if not points:
            return ModuleScore(5.0, "Krypto-Asset-Qualität neutral, weil Spezialdaten nicht verfügbar sind.", details)
        score = round(float(np.mean(points)), 1)
        return ModuleScore(score, f"Krypto-Asset-Qualität {score}/10 aus verfügbaren Langfristdaten.", details)
    return score_unknown_fundamentals(profile)


def score_asset_quality(symbol: str, profile: AssetProfile, df: pd.DataFrame) -> ModuleScore:
    return score_asset_quality_from_info(symbol, profile, df, load_ticker_info(symbol))


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


def parse_watchlist_symbols(raw: str) -> list[str]:
    symbols: list[str] = []
    for item in raw.replace("\n", ",").replace(";", ",").split(","):
        symbol = item.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols[:20]


def scanner_direction(buy_signal: ModuleScore, market_phase: MarketPhase) -> str:
    if buy_signal.score >= 6.5:
        return "Long"
    if buy_signal.score <= 3.5 and market_phase.phase == "Bärenmarkt":
        return "Short / Absicherung"
    return "Beobachten"


def scanner_confidence(df: pd.DataFrame, market_phase: MarketPhase, latest: pd.Series) -> float:
    points: list[float] = []
    points.append(8.0 if len(df) >= 200 else 6.0 if len(df) >= 120 else 4.0)
    points.append(market_phase_clarity_score(market_phase))
    points.append(signal_stability_score(df))

    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    if volume is not None and volume_avg is not None and volume_avg > 0:
        points.append(7.0 if volume > 0 else 4.5)
    else:
        points.append(4.0)

    return round(score_from_optional(points), 1)


def scanner_factor_snapshot(
    info: dict,
    profile: AssetProfile,
    latest: pd.Series,
    asset_quality: ModuleScore,
    macro: ModuleScore,
    news: ModuleScore,
) -> dict[str, str]:
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    if volume is not None and volume_avg is not None and volume_avg > 0:
        liquidity_ratio = volume / volume_avg
        liquidity_text = f"{liquidity_ratio:.2f}x 20T-Volumen"
    else:
        liquidity_text = "Daten nicht verfügbar"

    valuation_fields = [
        info.get("trailingPE"),
        info.get("forwardPE"),
        info.get("priceToSalesTrailing12Months"),
        info.get("priceToBook"),
        info.get("enterpriseToRevenue"),
    ]
    has_valuation = any(value_or_none(value) is not None for value in valuation_fields)
    if profile.asset_type == "Krypto":
        valuation_text = "Zyklus/On-Chain: Daten nicht verfügbar"
    elif has_valuation:
        valuation_text = f"Proxy über Asset-Qualität {asset_quality.score:.1f}/10"
    else:
        valuation_text = "Daten nicht verfügbar"

    institutional_fields = [
        info.get("heldPercentInstitutions"),
        info.get("heldPercentInsiders"),
        info.get("shortPercentOfFloat"),
    ]
    if any(value_or_none(value) is not None for value in institutional_fields):
        institutional_text = "Yahoo-Daten teilweise verfügbar"
    else:
        institutional_text = "Daten nicht verfügbar"

    return {
        "News": f"{news.score:.1f}/10",
        "Makro": f"{macro.score:.1f}/10",
        "Liquidität": liquidity_text,
        "Bewertung": valuation_text,
        "Institutionelle Faktoren": institutional_text,
    }


def scan_opportunities(symbols: list[str]) -> tuple[list[dict], list[str]]:
    results: list[dict] = []
    errors: list[str] = []
    macro = score_macro()
    backtest_history = load_backtest_history()

    for symbol in symbols:
        try:
            raw_data = load_price_data(symbol, "1y", "1d")
            if raw_data.empty or "Close" not in raw_data:
                errors.append(f"{symbol}: keine Kursdaten verfügbar.")
                continue

            df = calculate_indicators(raw_data, "1d")
            if df.empty:
                errors.append(f"{symbol}: Indikatoren konnten nicht berechnet werden.")
                continue

            supports = local_levels(df["Low"], "support") if "Low" in df else []
            resistances = local_levels(df["High"], "resistance") if "High" in df else []
            score_result = calculate_score_v2(df, supports, resistances)
            latest = df.iloc[-1]
            info = load_ticker_info(symbol)
            identity = build_asset_identity(symbol, info, ticker_candidate(symbol, source="Scanner"))
            profile = detect_asset_type(symbol, info)
            market_phase = detect_market_phase(df)
            close_value = float(latest["Close"])
            risk_reward = calculate_risk_reward(close_value, supports, resistances)
            asset_quality = score_asset_quality_from_info(symbol, profile, df, info)
            buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, profile)
            confidence = scanner_confidence(df, market_phase, latest)
            news = score_news(symbol)
            factor_snapshot = scanner_factor_snapshot(info, profile, latest, asset_quality, macro, news)

            opportunity_score = round(clamp(buy_signal.score * 0.55 + asset_quality.score * 0.20 + risk_reward.score * 0.15 + confidence * 0.10), 1)
            direction = scanner_direction(buy_signal, market_phase)
            historical_stats = similar_setup_statistics(profile.asset_type, market_phase.phase, direction, buy_signal.score)
            calibration_status, calibration_hint = backtest_calibration_context(backtest_history, market_phase.phase, buy_signal.score)
            reasons = [
                f"Kaufsignal {buy_signal.score:.1f}/10",
                f"Asset-Qualität {asset_quality.score:.1f}/10",
                f"Marktphase: {market_phase.phase}",
                risk_reward.summary,
            ]
            if macro.summary:
                reasons.append(f"Makro: {macro.summary}")
            reasons.append(f"News: {news.summary}")

            results.append(
                {
                    "Asset": identity.get("name", symbol),
                    "Ticker": symbol,
                    "Typ": profile.asset_type,
                    "Richtung": direction,
                    "Opportunity Score": opportunity_score,
                    "Vertrauen": confidence,
                    "Zeithorizont": "2-8 Wochen",
                    "Kaufsignal": buy_signal.score,
                    "Asset-Qualität": asset_quality.score,
                    "News": factor_snapshot["News"],
                    "Makro": factor_snapshot["Makro"],
                    "Liquidität": factor_snapshot["Liquidität"],
                    "Bewertung": factor_snapshot["Bewertung"],
                    "Institutionelle Faktoren": factor_snapshot["Institutionelle Faktoren"],
                    "Ähnliche Setups": historical_stats["count"],
                    "Trefferquote ähnliche Setups": historical_stats["hit_rate"],
                    "Historienstatus": historical_stats["status"],
                    "Kalibrierungskontext": calibration_status,
                    "Kalibrierungshinweis": calibration_hint,
                    "CRV": "Daten nicht verfügbar" if risk_reward.ratio is None else f"{risk_reward.ratio:.2f}",
                    "Wichtigste Begründungen": " | ".join([*reasons[:5], str(historical_stats["summary"]), calibration_hint]),
                }
            )
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")

    results.sort(key=lambda item: (item["Opportunity Score"], item["Vertrauen"]), reverse=True)
    return results, errors


def fallback_move_from_volatility(latest: pd.Series, default: float = 0.08) -> float:
    volatility = value_or_none(latest.get("Volatility"))
    if volatility is None:
        return default
    return min(max(volatility / 4, 0.04), 0.25)


def setup_probability(direction: str, buy_signal: ModuleScore, confidence: float, crv: float | None) -> int:
    if direction == "Short / Absicherung":
        base = 45 + (5 - buy_signal.score) * 6 + (confidence - 5) * 3
    else:
        base = 45 + (buy_signal.score - 5) * 7 + (confidence - 5) * 3
    if crv is not None:
        base += min(max(crv - 1.5, -1.0), 2.0) * 4
    return int(round(min(max(base, 20), 82)))


def build_trading_setup(symbol: str) -> tuple[dict | None, str | None]:
    try:
        raw_data = load_price_data(symbol, "1y", "1d")
        if raw_data.empty or "Close" not in raw_data:
            return None, f"{symbol}: keine Kursdaten verfügbar."

        df = calculate_indicators(raw_data, "1d")
        latest = df.iloc[-1]
        close = float(latest["Close"])
        supports = local_levels(df["Low"], "support") if "Low" in df else []
        resistances = local_levels(df["High"], "resistance") if "High" in df else []
        score_result = calculate_score_v2(df, supports, resistances)
        info = load_ticker_info(symbol)
        identity = build_asset_identity(symbol, info, ticker_candidate(symbol, source="Trading-Modus"))
        profile = detect_asset_type(symbol, info)
        market_phase = detect_market_phase(df)
        risk_reward = calculate_risk_reward(close, supports, resistances)
        asset_quality = score_asset_quality_from_info(symbol, profile, df, info)
        buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, profile)
        confidence = scanner_confidence(df, market_phase, latest)
        direction = scanner_direction(buy_signal, market_phase)
        move = fallback_move_from_volatility(latest)

        support = supports[0] if supports else None
        resistance = resistances[0] if resistances else None
        if direction == "Short / Absicherung":
            target = support if support is not None else close * (1 - move)
            stop = resistance if resistance is not None else close * (1 + move * 0.75)
            reward_pct = (close - target) / close if target < close else None
            risk_pct = (stop - close) / close if stop > close else None
            setup_label = "Short / Absicherung"
        else:
            target = resistance if resistance is not None else close * (1 + move)
            stop = support * 0.98 if support is not None else close * (1 - move * 0.75)
            reward_pct = (target - close) / close if target > close else None
            risk_pct = (close - stop) / close if stop < close else None
            setup_label = "Long" if buy_signal.score >= 6.5 else "Beobachten"

        crv = reward_pct / risk_pct if reward_pct is not None and risk_pct is not None and risk_pct > 0 else None
        chance = setup_probability(direction, buy_signal, confidence, crv)
        historical_stats = similar_setup_statistics(profile.asset_type, market_phase.phase, direction, buy_signal.score)
        calibration_status, calibration_hint = backtest_calibration_context(load_backtest_history(), market_phase.phase, buy_signal.score)
        risks = [
            "Setup verliert Aussagekraft, wenn die Stop-Zone klar gebrochen wird.",
            "Hohe Volatilität kann Ziel und Stop schnell anlaufen.",
            "Makro- oder News-Schocks können technische Signale überlagern.",
        ]
        if calibration_status not in {"Daten nicht verfügbar", "Keine auffällige Backtest-Warnung"}:
            risks.insert(0, calibration_hint)
        chances = [
            "Besseres CRV, wenn Einstieg nahe Unterstützung oder nach Bestätigung erfolgt.",
            "Momentum verbessert sich, wenn MACD und Marktphase drehen.",
            "Zielzone wird wahrscheinlicher, wenn Volumen die Bewegung bestätigt.",
        ]
        if direction == "Beobachten":
            risks.insert(0, "Noch kein klares Trading-Setup; der Kandidat gehört auf die Beobachtungsliste.")

        return {
            "Datum": pd.Timestamp.now().isoformat(),
            "Asset": identity.get("name", symbol),
            "Ticker": symbol,
            "Asset-Typ": profile.asset_type,
            "Richtung": setup_label,
            "Einstieg": close,
            "Zielzone": target,
            "Stop-Zone": stop,
            "Chance": chance,
            "Confidence": confidence,
            "Ähnliche Setups": historical_stats["count"],
            "Treffer ähnliche Setups": historical_stats["hits"],
            "Trefferquote ähnliche Setups": historical_stats["hit_rate"],
            "Historienstatus": historical_stats["status"],
            "Historienhinweis": historical_stats["summary"],
            "Kalibrierungskontext": calibration_status,
            "Kalibrierungshinweis": calibration_hint,
            "CRV": None if crv is None else round(crv, 2),
            "Zeithorizont": "2-8 Wochen",
            "Marktphase": market_phase.phase,
            "Kaufsignal": buy_signal.score,
            "Asset-Qualität": asset_quality.score,
            "signal_snapshot": build_signal_snapshot(latest, risk_reward, []),
            "Risiken": risks[:3],
            "Chancen": chances[:3],
            "Begründung": f"{setup_label}: Kaufsignal {buy_signal.score:.1f}/10, Confidence {confidence:.1f}/10, Marktphase {market_phase.phase}. {calibration_hint}",
            "review_after": empty_review_schedule(),
            "Hinweis": "Nur Analyse und Dokumentation. Keine automatische Kauf- oder Verkaufsfunktion.",
        }, None
    except Exception as exc:
        return None, f"{symbol}: {exc}"


def next_known_event_date(info: dict, now: pd.Timestamp | None = None) -> pd.Timestamp | None:
    reference = (now or pd.Timestamp.now()).tz_localize(None)
    for key in ["earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd"]:
        raw_value = info.get(key)
        if raw_value in {None, ""}:
            continue
        try:
            if isinstance(raw_value, (int, float)):
                timestamp = pd.to_datetime(raw_value, unit="s", utc=True).tz_convert(None)
            else:
                timestamp = pd.Timestamp(raw_value)
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.tz_convert(None)
        except Exception:
            continue
        if timestamp >= reference.normalize():
            return timestamp
    return None


def swing_trade_republic_asset(setup: dict) -> dict:
    metadata = dict(setup.get("universe_metadata") or {})
    return {
        "ticker": setup.get("symbol") or setup.get("ticker"),
        "name": setup.get("asset_name") or setup.get("name"),
        "isin": setup.get("isin") or metadata.get("isin"),
        "exchange": setup.get("exchange") or metadata.get("exchange"),
        "original_currency": setup.get("original_currency") or metadata.get("original_currency"),
    }


def swing_trade_republic_context(
    setup: dict,
    settings: dict,
    *,
    current_exposure_eur: float | None = None,
    current_risk_eur: float | None = None,
) -> dict:
    asset = swing_trade_republic_asset(setup)
    reference = trade_republic_reference(asset)
    price = trade_republic_price(asset)
    analysis_plan = dict(setup.get("order_plan") or {})
    execution_plan = build_trade_republic_execution_plan(
        analysis_plan,
        reference,
        price,
        trading_capital_eur=settings.get("trading_capital_eur"),
        max_risk_pct=float(settings.get("max_risk_pct") or 0),
        asset_type=str(setup.get("asset_type") or "Aktie"),
        max_total_exposure_pct=float(settings.get("max_total_exposure_pct") or 0),
        current_exposure_eur=(
            float(current_exposure_eur)
            if current_exposure_eur is not None
            else active_trade_exposure_eur(load_trade_history())
        ),
        max_position_exposure_pct=float(settings.get("max_position_exposure_pct") or 0),
        max_total_risk_pct=(
            float(settings["max_total_open_risk_pct"])
            if settings.get("max_total_open_risk_pct") is not None
            else None
        ),
        current_risk_eur=(
            float(current_risk_eur)
            if current_risk_eur is not None
            else active_trade_open_risk_eur(load_trade_history())
        ),
    )
    return {
        "asset": asset,
        "reference": reference,
        "price": price,
        "execution_plan": execution_plan,
        "execution_ready": execution_plan is not None,
    }


def swing_setup_trade_record(setup: dict) -> dict:
    order_plan = dict(setup.get("order_plan") or {})
    return normalize_trade_record(
        {
            "Datum": setup["evaluated_at"],
            "Setup-ID": setup["setup_id"],
            "Status": "Paper",
            "Asset": setup["asset_name"],
            "Ticker": setup["symbol"],
            "Asset-Typ": setup["asset_type"],
            "Richtung": "Long",
            "Setup-Typ": setup["setup_type"],
            "Aktueller Kurs EUR": setup["current_price_eur"],
            "Einstieg": setup["entry_reference"],
            "Einstieg EUR": setup["entry_reference_eur"],
            "Einstiegszone von EUR": setup["entry_low_eur"],
            "Einstiegszone bis EUR": setup["entry_high_eur"],
            "Eintrittsbedingung": setup["entry_condition"],
            "Stop-Zone": setup["stop"],
            "Stop-Loss EUR": setup["stop_eur"],
            "Zielzone": setup["target_1"],
            "Kursziel 1 EUR": setup["target_1_eur"],
            "Kursziel 2 EUR": setup.get("target_2_eur"),
            "Maximaler Einstieg EUR": setup["max_entry_eur"],
            "Ungültig unter EUR": setup["invalidation_eur"],
            "Orderplan": order_plan,
            "Ordertyp": order_plan.get("order_type"),
            "Aktivierung EUR": order_plan.get("activation_price_eur"),
            "Limitpreis EUR": order_plan.get("limit_price_eur"),
            "Frühester Einstieg": order_plan.get("earliest_entry_day"),
            "Signalkerze": order_plan.get("signal_bar_day"),
            "Plan-Fingerabdruck": order_plan.get("plan_fingerprint"),
            "Initialer Stop EUR": order_plan.get("initial_stop_eur", setup["stop_eur"]),
            "Stop-Vertrag Version": order_plan.get("stop_contract_version"),
            "CRV": round(setup["crv"], 2),
            "Chance je Einheit EUR": setup["chance_eur_per_unit"],
            "Risiko je Einheit EUR": setup["risk_eur_per_unit"],
            "Chance %": setup["chance_pct"],
            "Risiko %": setup["risk_pct"],
            "Erwarteter Wert R": setup.get("expected_value_r"),
            "Erwarteter Wert": setup["expected_value_text"],
            "Trefferwahrscheinlichkeit": setup["hit_rate_text"],
            "Zeithorizont": setup["holding_period"],
            "Gültig bis": setup["valid_until"],
            "Marktphase": setup["market_phase"],
            "Qualität": setup["quality_score"],
            "Gründe": setup["reasons"],
            "Größtes Risiko": setup["largest_risk"],
            "Nicht mehr einsteigen wenn": setup["no_entry_conditions"],
            "Originalwährung": setup["original_currency"],
            "FX zu EUR": setup["fx_rate_to_eur"],
            "Ähnliche Setups": setup["historical_cases"],
            "Trefferquote ähnliche Setups": setup.get("historical_hit_rate"),
            "Historienstatus": (
                "belastbar" if setup.get("historical_hit_rate") is not None else "Datenbasis zu klein"
            ),
            "Historienhinweis": setup["hit_rate_text"],
            "review_after": empty_review_schedule(),
            "Hinweis": "Automatisch dokumentierter Paper-Trade. Keine Order und keine Broker-Anbindung.",
        }
    )


def active_trade_records(history: list[dict] | None = None) -> list[dict]:
    return [
        normalize_trade_record(record)
        for record in (history if history is not None else load_trade_history())
        if str(record.get("Status")) == "Aktiv"
    ]


def active_trade_exposure_eur(history: list[dict] | None = None) -> float:
    return round(
        sum(
            float(record.get("Tatsächlicher Einstieg EUR") or 0)
            * float(record.get("Tatsächliche Stückzahl") or 0)
            for record in active_trade_records(history)
        ),
        2,
    )


def active_trade_open_risk_eur(history: list[dict] | None = None) -> float:
    total = 0.0
    for record in active_trade_records(history):
        try:
            entry = float(record.get("Tatsächlicher Einstieg EUR") or 0)
            quantity = float(record.get("Tatsächliche Stückzahl") or 0)
            stop = float(
                record.get("Aktueller Stop EUR")
                or record.get("Initialer Stop EUR")
                or record.get("Stop-Loss EUR")
                or 0
            )
        except (TypeError, ValueError):
            continue
        if entry > 0 and quantity > 0 and stop > 0:
            total += max(entry - stop, 0.0) * quantity
    return round(total, 2)


def _normalized_market_history(frame: object) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized = normalized.loc[:, ~normalized.columns.duplicated()].copy()
    for column in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        if column in normalized:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if "Close" not in normalized:
        return pd.DataFrame()
    return normalized.dropna(subset=["Close"])


def _histories_from_yfinance_batch(payload: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    if not isinstance(payload, pd.DataFrame) or payload.empty:
        return histories
    if not isinstance(payload.columns, pd.MultiIndex):
        if len(tickers) == 1:
            normalized = _normalized_market_history(payload)
            if not normalized.empty:
                histories[tickers[0]] = normalized
        return histories

    level_zero = {str(value).upper() for value in payload.columns.get_level_values(0)}
    level_one = {str(value).upper() for value in payload.columns.get_level_values(1)}
    for ticker in tickers:
        try:
            if ticker.upper() in level_zero:
                frame = payload.xs(ticker, axis=1, level=0, drop_level=True)
            elif ticker.upper() in level_one:
                frame = payload.xs(ticker, axis=1, level=1, drop_level=True)
            else:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        normalized = _normalized_market_history(frame)
        if not normalized.empty:
            histories[ticker] = normalized
    return histories


def load_swing_prefilter_histories(
    assets: list[SwingUniverseAsset],
    *,
    batch_size: int = 100,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Download daily histories in bounded batches so stage one avoids ticker-by-ticker metadata calls."""
    histories: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    tickers = [asset.ticker for asset in assets if asset.active]
    safe_batch_size = max(1, min(int(batch_size), 200))
    for offset in range(0, len(tickers), safe_batch_size):
        batch = tickers[offset : offset + safe_batch_size]
        try:
            payload = yf.download(
                batch,
                period="1y",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=True,
            )
        except Exception as exc:
            errors.append(
                f"Kursdatenpaket {offset // safe_batch_size + 1} ({len(batch)} Assets): {exc}"
            )
            continue
        histories.update(_histories_from_yfinance_batch(payload, batch))
    return histories, errors


def _evaluate_swing_asset(
    asset: SwingUniverseAsset,
    raw_data: pd.DataFrame,
    *,
    settings: dict,
    thresholds: SwingTradeThresholds,
    macro: ModuleScore,
    scan_time: pd.Timestamp,
) -> dict:
    frame = calculate_indicators(raw_data, "1d")
    latest = frame.iloc[-1]
    supports = local_levels(frame["Low"], "support") if "Low" in frame else []
    resistances = local_levels(frame["High"], "resistance") if "High" in frame else []
    score_result = calculate_score_v2(frame, supports, resistances)
    info = load_ticker_info(asset.ticker)
    identity = build_asset_identity(
        asset.ticker,
        info,
        {"name": asset.name, "source": f"Swing-Universum {asset.version}"},
    )
    detected_profile = detect_asset_type(asset.ticker, info)
    profile = AssetProfile(
        asset_type=asset.asset_type,
        quote_type=detected_profile.quote_type,
        summary=detected_profile.summary,
        weights=detected_profile.weights,
    )
    market_phase = detect_market_phase(frame)
    close = float(latest["Close"])
    risk_reward = calculate_risk_reward(close, supports, resistances)
    asset_quality = score_asset_quality_from_info(asset.ticker, profile, frame, info)
    buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, profile)
    confidence = scanner_confidence(frame, market_phase, latest)
    historical = similar_setup_statistics(asset.asset_type, market_phase.phase, "Long", buy_signal.score)
    original_currency = str(identity.get("currency") or info.get("currency") or "EUR").upper()
    fx_rate, _ = get_fx_rate_to_eur(original_currency)
    assessment = evaluate_swing_trade(
        frame,
        symbol=asset.ticker,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        market_phase=market_phase.phase,
        buy_signal=buy_signal.score,
        asset_quality=asset_quality.score,
        confidence=confidence,
        market_score=macro.score,
        fx_rate=fx_rate,
        original_currency=original_currency,
        region=asset.region,
        historical_cases=int(historical.get("count") or 0),
        historical_hit_rate=historical.get("hit_rate"),
        event_date=next_known_event_date(info, scan_time),
        now=scan_time.to_pydatetime(),
        thresholds=thresholds,
    )
    universe_metadata = asset.as_dict()
    exchange = str(identity.get("exchange") or "").strip()
    if exchange and exchange != "Daten nicht verfügbar":
        universe_metadata["exchange"] = exchange
    isin = str(info.get("isin") or "").strip().upper()
    if isin:
        universe_metadata["isin"] = isin
    universe_metadata.update(
        {
            "quote_type": identity.get("quote_type") or info.get("quoteType"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "metadata_observed_at": scan_time.isoformat(),
            "metadata_source": "Swing-Universum und Yahoo Finance/yfinance",
        }
    )
    assessment["universe_metadata"] = universe_metadata
    assessment["volatility_regime"] = volatility_bucket(latest.get("Volatility"))
    tr_asset = swing_trade_republic_asset(assessment)
    assessment["trade_republic"] = trade_republic_reference(tr_asset)
    assessment["trade_republic_price"] = trade_republic_price(tr_asset)
    if asset.asset_type not in set(settings.get("allowed_asset_types") or []):
        assessment["approved"] = False
        assessment["rejection_reasons"] = [
            f"Asset-Typ {asset.asset_type} ist nach der internen Risikoregel nicht erlaubt."
        ]
    return assessment


def _release_swing_candidates(
    candidates: list[dict],
    *,
    settings: dict,
    current_exposure_eur: float,
    current_risk_eur: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    released: list[dict] = []
    rejected: list[dict] = []
    shadow_signals: list[dict] = []
    running_exposure = current_exposure_eur
    running_risk = current_risk_eur
    for assessment in candidates:
        assessment = apply_swing_risk_engine(
            assessment,
            settings,
            current_exposure_eur=running_exposure,
            current_risk_eur=running_risk,
            execution_mode="analysis_only",
        )
        position_size = dict(assessment["position_size"])
        if settings.get("trading_capital_eur") and not position_size.get("quantity"):
            reason = str(position_size["explanation"])
            assessment["forward_evidence_kind"] = "shadow_dynamic_risk_budget"
            assessment["forward_exclusion_reason"] = reason
            assessment["scanner_qualified"] = True
            shadow_signals.append(assessment)
            rejected.append(
                {
                    "Ticker": assessment.get("symbol"),
                    "Asset": assessment.get("asset_name"),
                    "Asset-Typ": assessment.get("asset_type"),
                    "Ablehnungsgründe": [reason],
                }
            )
            continue
        assessment["forward_evidence_kind"] = "scanner_released"
        assessment["forward_exclusion_reason"] = None
        assessment["scanner_qualified"] = True
        released.append(assessment)
        running_exposure += float(position_size.get("position_value_eur") or 0)
        running_risk += float(position_size.get("actual_risk_eur") or 0)
    return released, rejected, shadow_signals


def scan_swing_market(
    settings: dict,
    *,
    universe_path: Path = DEFAULT_SWING_UNIVERSE_PATH,
    thresholds: SwingTradeThresholds = DEFAULT_SWING_THRESHOLDS,
    prefilter_thresholds=DEFAULT_PREFILTER_THRESHOLDS,
    histories_loader: Callable[[list[SwingUniverseAsset]], tuple[dict[str, pd.DataFrame], list[str]]] = load_swing_prefilter_histories,
    scope_name: str = "manual_full",
    scope_regions: set[str] | None = None,
    scope_asset_types: set[str] | None = None,
    objective_forward: bool = False,
) -> dict:
    scan_time = pd.Timestamp(datetime.now().astimezone())
    universe_report = load_swing_universe(universe_path)
    assets = active_swing_assets(universe_report)
    if scope_regions is not None:
        assets = [asset for asset in assets if asset.region in scope_regions]
    if scope_asset_types is not None:
        assets = [asset for asset in assets if asset.asset_type in scope_asset_types]
    histories, download_errors = histories_loader(assets)
    macro = score_macro()
    history = [] if objective_forward else load_trade_history()
    current_exposure = active_trade_exposure_eur(history)
    current_risk = active_trade_open_risk_eur(history)

    result = execute_multistage_scan(
        assets,
        histories,
        lambda asset, frame: _evaluate_swing_asset(
            asset,
            frame,
            settings=settings,
            thresholds=thresholds,
            macro=macro,
            scan_time=scan_time,
        ),
        download_errors=[*download_errors, *universe_report.errors],
        thresholds=prefilter_thresholds,
    )
    strategy_candidates = list(result["approved"])
    strategy_qualified_total = len(strategy_candidates)
    released, portfolio_rejected, shadow_signals = _release_swing_candidates(
        result["approved"],
        settings=settings,
        current_exposure_eur=current_exposure,
        current_risk_eur=current_risk,
    )
    result["approved"] = released
    result["shadow_signals"] = shadow_signals
    result["rejected"].extend(portfolio_rejected)
    result["statistics"]["approved_trades"] = len(released)
    result["statistics"]["strategy_qualified_total"] = strategy_qualified_total
    result["statistics"]["shadow_signals"] = len(shadow_signals)
    result["asset_type_funnel"] = apply_portfolio_release_to_funnel(
        result.get("asset_type_funnel") or {},
        released,
    )
    result["asset_type_bias_audit"] = asset_type_bias_audit(result["asset_type_funnel"])
    result["portfolio_cluster_audit"] = swing_portfolio_cluster_audit(
        strategy_candidates,
        histories,
    )

    all_rejections = [*result["rejected"], *result["prefilter_rejected"]]
    reason_counts: dict[str, int] = {}
    for item in all_rejections:
        for reason in item.get("Ablehnungsgründe", []):
            reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
    result.update(
        {
            "checked_assets": result["statistics"]["universe_size"],
            "scan_scope": str(scope_name),
            "objective_forward": bool(objective_forward),
            "last_scan": scan_time.isoformat(),
            "market_label": "Unterstützend" if macro.score >= 6 else "Belastet" if macro.score < 4 else "Neutral",
            "market_summary": macro.summary,
            "main_rejection": (
                max(reason_counts.items(), key=lambda item: item[1])[0]
                if reason_counts
                else "Alle Qualitätsfilter wurden geprüft."
            ),
            "thresholds": thresholds_as_dict(thresholds),
            "risk_policy": risk_policy_as_dict(),
            "universe_report": {
                "path": str(Path(universe_path).resolve()),
                "version": assets[0].version if assets else "nicht verfügbar",
                "total_rows": universe_report.total_rows,
                "active_count": universe_report.active_count,
                "inactive_count": universe_report.inactive_count,
                "duplicate_count": universe_report.duplicate_count,
                "forbidden_count": universe_report.forbidden_count,
                "selected_count": len(assets),
                "scan_scope": str(scope_name),
            },
        }
    )
    return result


def scan_swing_trades(
    symbols: list[str],
    settings: dict,
    thresholds: SwingTradeThresholds = DEFAULT_SWING_THRESHOLDS,
) -> dict:
    approved: list[dict] = []
    rejected: list[dict] = []
    errors: list[str] = []
    scan_time = pd.Timestamp(datetime.now().astimezone())
    macro = score_macro()
    history = load_trade_history()
    current_exposure = active_trade_exposure_eur(history)
    current_risk = active_trade_open_risk_eur(history)
    allowed_asset_types = set(settings.get("allowed_asset_types") or ["Aktie", "ETF", "Krypto"])

    for symbol in symbols:
        try:
            raw_data = load_price_data(symbol, "1y", "1d")
            if raw_data.empty or "Close" not in raw_data:
                rejected.append({"Ticker": symbol, "Ablehnungsgründe": ["Keine Kursdaten verfügbar."]})
                continue
            frame = calculate_indicators(raw_data, "1d")
            latest = frame.iloc[-1]
            supports = local_levels(frame["Low"], "support") if "Low" in frame else []
            resistances = local_levels(frame["High"], "resistance") if "High" in frame else []
            score_result = calculate_score_v2(frame, supports, resistances)
            info = load_ticker_info(symbol)
            identity = build_asset_identity(symbol, info, ticker_candidate(symbol, source="Swing-Scanner"))
            profile = detect_asset_type(symbol, info)
            market_phase = detect_market_phase(frame)
            close = float(latest["Close"])
            risk_reward = calculate_risk_reward(close, supports, resistances)
            asset_quality = score_asset_quality_from_info(symbol, profile, frame, info)
            buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, profile)
            confidence = scanner_confidence(frame, market_phase, latest)
            historical = similar_setup_statistics(profile.asset_type, market_phase.phase, "Long", buy_signal.score)
            original_currency = str(identity.get("currency") or info.get("currency") or "EUR").upper()
            fx_rate, _ = get_fx_rate_to_eur(original_currency)
            assessment = evaluate_swing_trade(
                frame,
                symbol=symbol,
                asset_name=str(identity.get("name") or symbol),
                asset_type=profile.asset_type,
                market_phase=market_phase.phase,
                buy_signal=buy_signal.score,
                asset_quality=asset_quality.score,
                confidence=confidence,
                market_score=macro.score,
                fx_rate=fx_rate,
                original_currency=original_currency,
                historical_cases=int(historical.get("count") or 0),
                historical_hit_rate=historical.get("hit_rate"),
                event_date=next_known_event_date(info, scan_time),
                now=scan_time.to_pydatetime(),
                thresholds=thresholds,
            )
            universe_metadata = {
                "asset_id": f"manual|{symbol.upper()}",
                "version": "manual-swing-scan",
                "region": None,
                "category": "Manuelle Auswahl",
                "exchange": identity.get("exchange"),
                "isin": str(info.get("isin") or "").strip().upper() or None,
                "quote_type": identity.get("quote_type") or info.get("quoteType"),
                "metadata_observed_at": scan_time.isoformat(),
                "metadata_source": "Manuelle Auswahl und Yahoo Finance/yfinance",
            }
            assessment["universe_metadata"] = universe_metadata
            tr_asset = swing_trade_republic_asset(assessment)
            assessment["trade_republic"] = trade_republic_reference(tr_asset)
            assessment["trade_republic_price"] = trade_republic_price(tr_asset)
            if profile.asset_type not in allowed_asset_types:
                assessment["approved"] = False
                assessment["rejection_reasons"] = [
                    f"Asset-Typ {profile.asset_type} ist in den Trading-Einstellungen nicht erlaubt."
                ]
            if assessment["approved"]:
                assessment = apply_swing_risk_engine(
                    assessment,
                    settings,
                    current_exposure_eur=current_exposure,
                    current_risk_eur=current_risk,
                    execution_mode="analysis_only",
                )
                position_size = dict(assessment["position_size"])
                if settings.get("trading_capital_eur") and not position_size.get("quantity"):
                    assessment["approved"] = False
                    assessment["rejection_reasons"] = [position_size["explanation"]]
            if assessment["approved"]:
                approved.append(assessment)
                current_exposure += float((assessment.get("position_size") or {}).get("position_value_eur") or 0)
                current_risk += float((assessment.get("position_size") or {}).get("actual_risk_eur") or 0)
            else:
                rejected.append(
                    {
                        "Ticker": symbol,
                        "Asset": assessment.get("asset_name", identity.get("name", symbol)),
                        "Asset-Typ": profile.asset_type,
                        "Datenqualität": assessment.get("data_quality"),
                        "Relatives Volumen": assessment.get("relative_volume"),
                        "Ablehnungsgründe": assessment.get("rejection_reasons") or ["Kein freigegebenes Setup."],
                    }
                )
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")

    approved.sort(
        key=lambda item: (
            item.get("expected_value_r") if item.get("expected_value_r") is not None else -999,
            item.get("quality_score", 0),
            item.get("crv", 0),
        ),
        reverse=True,
    )
    reason_counts: dict[str, int] = {}
    for item in rejected:
        for reason in item.get("Ablehnungsgründe", []):
            reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
    main_rejection = (
        max(reason_counts.items(), key=lambda item: item[1])[0]
        if reason_counts
        else ("Kurs- oder Stammdaten waren nicht vollständig verfügbar." if errors else "Alle Qualitätsfilter wurden geprüft.")
    )
    market_label = "Unterstützend" if macro.score >= 6 else "Belastet" if macro.score < 4 else "Neutral"
    return {
        "approved": approved,
        "rejected": rejected,
        "errors": errors,
        "checked_assets": len(symbols),
        "last_scan": scan_time.isoformat(),
        "market_label": market_label,
        "market_summary": macro.summary,
        "main_rejection": main_rejection,
        "thresholds": thresholds_as_dict(thresholds),
    }


def replace_trade_history_record(setup_id: str, updated_record: dict) -> bool:
    history = load_trade_history()
    replaced = False
    for index, record in enumerate(history):
        if str(record.get("Setup-ID") or record.get("setup_id")) == str(setup_id):
            history[index] = normalize_trade_record(updated_record)
            replaced = True
            break
    return replaced and save_json_dict_list(TRADE_HISTORY_PATH, history)


def mark_trade_manually_open(
    setup_id: str,
    actual_entry_eur: float,
    quantity: float,
    opened_at: object,
) -> tuple[bool, str]:
    for record in load_trade_history():
        if str(record.get("Setup-ID") or record.get("setup_id")) != str(setup_id):
            continue
        updated, error = open_trade_record(normalize_trade_record(record), actual_entry_eur, quantity, opened_at)
        if error or updated is None:
            return False, error or "Trade konnte nicht geöffnet werden."
        if replace_trade_history_record(setup_id, updated):
            return True, "Trade wurde manuell als aktiv markiert. Es wurde keine Order ausgelöst."
        return False, "Aktiver Trade konnte nicht lokal gespeichert werden."
    return False, "Das zugehörige Paper-Setup wurde nicht gefunden."


def update_manual_trade_stop(setup_id: str, new_stop_eur: float) -> tuple[bool, str]:
    for record in load_trade_history():
        if str(record.get("Setup-ID") or record.get("setup_id")) != str(setup_id):
            continue
        normalized = normalize_trade_record(record)
        updated, error = tighten_active_trade_stop(
            normalized,
            new_stop_eur,
            datetime.now().astimezone(),
        )
        if error or updated is None:
            return False, error or "Stop konnte nicht angepasst werden."
        if replace_trade_history_record(setup_id, updated):
            return True, "Stop wurde lokal aktualisiert. Keine Order wurde verändert."
        return False, "Stop konnte nicht gespeichert werden."
    return False, "Aktiver Trade wurde nicht gefunden."


def mark_trade_manually_closed(setup_id: str, exit_eur: float, closed_at: object) -> tuple[bool, str]:
    for record in load_trade_history():
        if str(record.get("Setup-ID") or record.get("setup_id")) != str(setup_id):
            continue
        updated, error = close_trade_record(normalize_trade_record(record), exit_eur, closed_at)
        if error or updated is None:
            return False, error or "Trade konnte nicht geschlossen werden."
        if replace_trade_history_record(setup_id, updated):
            return True, "Ausstieg wurde manuell dokumentiert. Es wurde keine Order ausgeführt."
        return False, "Ausstieg konnte nicht lokal gespeichert werden."
    return False, "Aktiver Trade wurde nicht gefunden."


def expire_due_paper_trades() -> int:
    history = load_trade_history()
    changed = 0
    updated_history: list[dict] = []
    for record in history:
        updated, expired = expire_paper_trade(normalize_trade_record(record))
        updated_history.append(updated)
        changed += int(expired)
    if changed:
        save_json_dict_list(TRADE_HISTORY_PATH, updated_history)
    return changed


def setup_display_rows(setups: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for setup in setups:
        rows.append(
            {
                "Asset": setup["Asset"],
                "Ticker": setup["Ticker"],
                "Richtung": setup["Richtung"],
                "Chance": f"{setup['Chance']}%",
                "Confidence": f"{setup['Confidence']:.1f}/10",
                "Ähnliche Setups": setup.get("Ähnliche Setups", 0),
                "Historienstatus": setup.get("Historienstatus", "Datenbasis zu klein"),
                "Kalibrierungskontext": setup.get("Kalibrierungskontext", "Daten nicht verfügbar"),
                "Trefferquote ähnliche Setups": "Datenbasis zu klein" if setup.get("Trefferquote ähnliche Setups") is None else f"{setup['Trefferquote ähnliche Setups']:.1f}%",
                "Einstieg": format_currency(float(setup["Einstieg"])),
                "Zielzone": format_currency(float(setup["Zielzone"])) if setup.get("Zielzone") is not None else "Daten nicht verfügbar",
                "Stop-Zone": format_currency(float(setup["Stop-Zone"])) if setup.get("Stop-Zone") is not None else "Daten nicht verfügbar",
                "CRV": "Daten nicht verfügbar" if setup.get("CRV") is None else f"{setup['CRV']:.2f}",
                "Zeithorizont": setup["Zeithorizont"],
                "Begründung": setup["Begründung"],
            }
        )
    return rows


def render_trading_mode(setups: list[dict], errors: list[str]) -> None:
    st.subheader("Trading-Modus")
    st.caption("Trading-Setups entstehen nur aus Scanner-Kandidaten. Sie sind Vorschläge zur Prüfung, keine Order und keine Broker-Anbindung.")

    if errors:
        with st.expander("Nicht erstellte Setups", expanded=False):
            for error in errors:
                st.write(f"- {error}")

    if not setups:
        st.info("Keine belastbaren Trading-Setups aus den aktuellen Scanner-Kandidaten ableitbar.")
        return

    st.dataframe(pd.DataFrame(setup_display_rows(setups)), use_container_width=True, hide_index=True)

    with st.expander("Risiken und Chancen je Setup", expanded=False):
        for setup in setups:
            st.markdown(f"**{setup['Ticker']} · {setup['Richtung']}**")
            st.write("Chancen: " + " ".join(setup["Chancen"]))
            st.write("Risiken: " + " ".join(setup["Risiken"]))

    if st.button("Trading-Setups lokal im Trade Journal speichern", use_container_width=True):
        if append_trade_records(setups):
            st.success("Trading-Setups in `trade_history.json` gespeichert. Es wurde keine Order ausgelöst.")
        else:
            st.error("Trading-Setups konnten nicht gespeichert werden.")


def render_opportunity_scanner(results: list[dict], errors: list[str]) -> None:
    st.subheader("Opportunity Scanner")
    st.caption("Der Scanner vergleicht eine definierte Watchlist. Er macht nur Vorschläge und löst keine Käufe oder Verkäufe aus.")

    if errors:
        with st.expander("Datenqualität / nicht gescannte Ticker", expanded=False):
            for error in errors:
                st.write(f"- {error}")

    if not results:
        st.info("Keine verwertbaren Scanner-Ergebnisse. Bitte Watchlist oder Ticker prüfen.")
        return

    long_rows = [item for item in results if item["Richtung"] == "Long"]
    short_rows = [item for item in results if item["Richtung"] == "Short / Absicherung"]
    watch_rows = [item for item in results if item["Richtung"] == "Beobachten"]

    st.markdown("**Top Long Chancen**")
    if long_rows:
        st.dataframe(pd.DataFrame(long_rows[:10]), use_container_width=True, hide_index=True)
    else:
        st.info("Keine klare Long-Chance in der aktuellen Watchlist.")

    st.markdown("**Top Short / Absicherungs-Kandidaten**")
    if short_rows:
        st.dataframe(pd.DataFrame(short_rows[:10]), use_container_width=True, hide_index=True)
    else:
        st.info("Keine klare Short- oder Absicherungs-Chance in der aktuellen Watchlist.")

    if watch_rows:
        with st.expander("Beobachtungsliste", expanded=False):
            st.dataframe(pd.DataFrame(watch_rows[:10]), use_container_width=True, hide_index=True)


def _render_swing_trade_card_legacy(setup: dict, settings: dict, active_setup_ids: set[str]) -> None:
    with st.container(border=True):
        st.subheader(f"{setup['asset_name']} · {setup['symbol']}")
        metadata = setup.get("universe_metadata", {})
        st.caption(
            f"{setup['asset_type']} · {metadata.get('region', 'Region nicht verfügbar')} · "
            f"{metadata.get('category', 'Kategorie nicht verfügbar')} · Long · {setup['setup_type']} · "
            f"Qualität {setup['quality_score']:.1f}/10"
        )
        st.caption(
            f"Analysiertes Listing: {setup['symbol']} · "
            f"{metadata.get('exchange', 'Börsenplatz nicht verfügbar')} · {setup['original_currency']}. "
            f"Kursquelle: {setup.get('price_source', 'Yahoo Finance / yfinance')} · "
            f"Signalkerze: {setup.get('signal_bar_day', 'nicht verfügbar')}."
        )
        if setup.get("original_currency") != "EUR":
            st.warning(
                "Die Euro-Werte sind nur die Umrechnung des Kurses dieses Listings. "
                "Sie sind kein Trade-Republic- oder LS-Exchange-Livekurs und dürfen nicht auf ein ADR/GDR "
                "oder anderes Listing übertragen werden."
            )

        order_plan = setup.get("order_plan") or {}
        st.markdown("**Orderplan – es wird keine Order gesendet**")
        order_col, limit_col, activation_col, earliest_col = st.columns(4)
        order_col.metric("Ordertyp", order_plan.get("order_type", "Nicht verfügbar"))
        limit_col.metric(
            "Limitpreis",
            format_money(order_plan.get("limit_price_eur"), "EUR"),
        )
        activation_col.metric(
            "Aktivierung ab",
            format_money(order_plan.get("activation_price_eur"), "EUR"),
        )
        earliest_col.metric("Frühester Einstieg", order_plan.get("earliest_entry_day", "Nicht verfügbar"))
        st.caption(
            "Die Signalkerze muss vollständig abgeschlossen sein. Ein möglicher Einstieg wird erst in einer späteren "
            "Handelssitzung geprüft und niemals rückwirkend zum bestätigenden Schlusskurs angenommen."
        )
        st.write(
            f"**Maximalpreis:** {format_money(order_plan.get('maximum_entry_eur'), 'EUR')} · "
            f"**Initialer Stop:** {format_money(order_plan.get('initial_stop_eur'), 'EUR')} · "
            f"**Gültig bis:** {order_plan.get('valid_until', setup['valid_until'])}"
        )
        if order_plan.get("position_calculated"):
            planned_quantity = order_plan.get("quantity")
            quantity_text = (
                f"{int(planned_quantity)} Anteile"
                if setup["asset_type"] in {"Aktie", "ETF"}
                else f"{float(planned_quantity):.6f} Einheiten"
            )
            st.write(
                f"**Stückzahl:** {quantity_text} · "
                f"**Kapitaleinsatz:** {format_money(order_plan.get('capital_committed_eur'), 'EUR')} · "
                f"**Geplanter Verlust:** {format_money(order_plan.get('planned_loss_eur'), 'EUR')}"
            )
            if order_plan.get("target_2_eur") is not None:
                st.write(
                    f"**Teilgewinn Ziel 1 ({float(order_plan.get('target_1_exit_fraction') or 0.5) * 100:.0f}%):** "
                    f"{format_money(order_plan.get('possible_gain_1_eur'), 'EUR')} · "
                    f"**Kumuliert bei Ziel 2:** {format_money(order_plan.get('possible_gain_2_eur'), 'EUR')}"
                )
            else:
                st.write(
                    f"**Möglicher Gewinn bei Ziel 1:** {format_money(order_plan.get('possible_gain_1_eur'), 'EUR')}"
                )
        else:
            st.caption("Ohne gültiges Tradingkapital enthält der Orderplan bewusst keine erfundene Stückzahl.")
        with st.expander("Lösch- und Widerlegungsbedingungen", expanded=False):
            for condition in order_plan.get("delete_conditions", setup["no_entry_conditions"]):
                st.write(f"- {condition}")

        signal_id = str(setup.get("forward_signal_id") or "")
        if signal_id and signal_id not in active_setup_ids:
            with st.expander("Trade getätigt", expanded=False):
                st.caption(
                    "Nur bestätigen, wenn du den Trade bereits selbst außerhalb der App ausgeführt hast. "
                    "Hierdurch wird keine Order gesendet."
                )
                with st.form(f"user_trade_open_{signal_id}"):
                    traded_identifier = st.text_input(
                        "Ticker oder ISIN des tatsächlich gehandelten Listings",
                        value=str(setup["symbol"]),
                    )
                    actual_entry = st.number_input(
                        "Tatsächlicher Einstieg in Euro",
                        min_value=0.000001,
                        value=float(order_plan.get("limit_price_eur") or 0.000001),
                        format="%.6f",
                    )
                    planned_quantity = order_plan.get("quantity")
                    actual_quantity = st.number_input(
                        "Tatsächliche Stückzahl",
                        min_value=0.0,
                        value=float(planned_quantity or 0.0),
                        step=1.0 if setup["asset_type"] in {"Aktie", "ETF"} else 0.000001,
                        format="%.6f",
                    )
                    opened_date = st.date_input(
                        "Einstiegsdatum",
                        value=pd.Timestamp.now().date(),
                        key=f"user_open_date_{signal_id}",
                    )
                    opened_time = st.time_input(
                        "Einstiegszeit",
                        value=pd.Timestamp.now().time().replace(microsecond=0),
                        key=f"user_open_time_{signal_id}",
                    )
                    note = st.text_input("Optionale Notiz", value="")
                    confirm_deviation = st.checkbox(
                        "Abweichungen vom Systemplan ausdrücklich bestätigen",
                        value=False,
                    )
                    open_submitted = st.form_submit_button(
                        "Extern ausgeführten Trade lokal speichern",
                        use_container_width=True,
                    )
                if open_submitted:
                    listing_ok, listing_message = validate_traded_listing(
                        traded_identifier,
                        expected_symbol=str(setup["symbol"]),
                        expected_isin=metadata.get("isin"),
                    )
                    if not listing_ok:
                        st.error(listing_message)
                        return
                    try:
                        create_swing_user_trade(
                            signal_id,
                            dict(setup.get("forward_signal_snapshot") or {}),
                            actual_entry,
                            actual_quantity,
                            datetime.combine(opened_date, opened_time).astimezone(),
                            note=note,
                            confirm_deviations=confirm_deviation,
                        )
                    except SwingUserTradeDeviationConfirmationRequired as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Nutzertrade konnte nicht gespeichert werden: {exc}")
                    else:
                        st.success("Persönlicher Trade wurde lokal getrennt gespeichert. Es wurde keine Order gesendet.")
                        st.rerun()
        elif signal_id:
            st.info("Dieser objektive Plan besitzt bereits einen getrennt gespeicherten persönlichen Nutzertrade.")

        price_col, entry_col, stop_col, target_col, crv_col = st.columns(5)
        price_col.metric("Signalkurs (Schluss)", format_money(setup["current_price_eur"], "EUR"))
        entry_col.metric(
            "Einstiegszone",
            f"{format_money(setup['entry_low_eur'], 'EUR')} bis {format_money(setup['entry_high_eur'], 'EUR')}",
        )
        stop_col.metric("Stop-Loss", format_money(setup["stop_eur"], "EUR"))
        target_col.metric("Kursziel 1", format_money(setup["target_1_eur"], "EUR"))
        crv_col.metric("CRV", f"{setup['crv']:.2f}")

        st.markdown(f"**Genaue Eintrittsbedingung:** {setup['entry_condition']}")
        st.write(f"**Automatischer Stop:** {setup.get('stop_reason', 'Aus Kursstruktur und Schwankung abgeleitet.')}")
        target_2_text = (
            format_money(setup["target_2_eur"], "EUR")
            if setup.get("target_2_eur") is not None
            else "Kein zweites strukturelles Ziel belastbar ableitbar"
        )
        detail_col, risk_col = st.columns(2)
        with detail_col:
            st.write(f"**Kursziel 2:** {target_2_text}")
            st.write(f"**Maximal akzeptierter Einstieg:** {format_money(setup['max_entry_eur'], 'EUR')}")
            st.write(f"**Geschätzte Haltedauer:** {setup['holding_period']}")
            st.write(f"**Gültig bis:** {setup['valid_until']}")
        with risk_col:
            position_size = setup["position_size"]
            quantity = position_size.get("quantity")
            quantity_text = (
                "Nicht berechnet"
                if quantity is None
                else f"{int(quantity)} Anteile"
                if setup["asset_type"] in {"Aktie", "ETF"}
                else f"{quantity:.6f} Einheiten"
            )
            st.write(f"**Automatische Positionsgröße:** {quantity_text}")
            st.write(
                "**Investierter Betrag:** "
                + (
                    "Nicht berechnet"
                    if position_size.get("position_value_eur") is None
                    else format_money(position_size["position_value_eur"], "EUR")
                )
            )
            st.write(
                "**Möglicher Gewinn Ziel 1 / Ziel 2:** "
                f"{format_money(position_size['potential_gain_1_eur'], 'EUR') if position_size.get('potential_gain_1_eur') is not None else 'Nicht berechnet'} / "
                f"{format_money(position_size['potential_gain_2_eur'], 'EUR') if position_size.get('potential_gain_2_eur') is not None else 'Nicht berechnet'}"
            )
            st.write(
                "**Risiko / Gewinn bezogen auf Tradingkapital:** "
                f"{position_size['risk_pct_of_capital']:.2f}% Risiko"
                if position_size.get("risk_pct_of_capital") is not None
                else "**Risiko / Gewinn bezogen auf Tradingkapital:** Nicht berechnet"
            )
            if position_size.get("gain_1_pct_of_capital") is not None:
                gain_2_pct = position_size.get("gain_2_pct_of_capital")
                st.write(
                    f"**Gewinn Ziel 1 / Ziel 2 in Prozent:** {position_size['gain_1_pct_of_capital']:.2f}% / "
                    f"{f'{gain_2_pct:.2f}%' if gain_2_pct is not None else 'Nicht berechnet'}"
                )
            st.write(f"**Erwarteter Wert:** {setup['expected_value_text']}")

        st.info(setup["hit_rate_text"])
        st.markdown("**Wichtigste Gründe**")
        for reason in setup["reasons"][:3]:
            st.write(f"- {reason}")
        st.markdown(f"**Größtes Risiko:** {setup['largest_risk']}")
        st.warning(setup["position_size"]["planned_loss_notice"])
        st.markdown("**Nicht mehr einsteigen, wenn**")
        for condition in setup["no_entry_conditions"]:
            st.write(f"- {condition}")
        st.caption(setup["position_size"]["explanation"])
        st.caption("Keine Broker-Anbindung, keine Order und keine automatische Ausführung.")


def render_trade_republic_reference_editor(setup: dict, context: dict, *, key: str) -> None:
    asset = dict(context["asset"])
    reference = dict(context["reference"])
    analysis_listing = dict(reference.get("analysis_listing") or {})
    tr_listing = dict(reference.get("tr_listing") or {})
    status = str(reference.get("status") or TR_STATUS_UNKNOWN)
    with st.expander("Trade-Republic-Listing dauerhaft zuordnen", expanded=False):
        st.caption(
            "Die Zuordnung gilt nur für das konkrete analysierte Listing. Es findet keine automatische "
            "Brokerabfrage und keine Order statt. Änderungen werden append-only protokolliert."
        )
        st.write(
            f"**Analyse-Listing:** {analysis_listing.get('ticker') or asset.get('ticker') or 'unbekannt'} · "
            f"{analysis_listing.get('exchange') or asset.get('exchange') or 'Handelsplatz unbekannt'} · "
            f"ISIN {analysis_listing.get('isin') or asset.get('isin') or 'unbekannt'}"
        )
        with st.form(f"tr_listing_reference_{key}"):
            selected_status = st.selectbox(
                "Status",
                list(TR_STATUS_OPTIONS),
                index=list(TR_STATUS_OPTIONS).index(status) if status in TR_STATUS_OPTIONS else 2,
            )
            analysis_isin = st.text_input(
                "ISIN des analysierten Instruments",
                value=str(analysis_listing.get("isin") or asset.get("isin") or ""),
            )
            tr_ticker = st.text_input(
                "Ticker/Instrument bei Trade Republic",
                value=str(tr_listing.get("ticker") or asset.get("ticker") or ""),
            )
            tr_isin = st.text_input(
                "ISIN bei Trade Republic",
                value=str(tr_listing.get("isin") or analysis_isin or ""),
            )
            tr_exchange = st.text_input(
                "Konkreter TR-Handelsplatz",
                value=str(tr_listing.get("exchange") or ""),
            )
            tr_name = st.text_input(
                "Instrumentname bei Trade Republic (optional)",
                value=str(tr_listing.get("name") or asset.get("name") or ""),
            )
            note = st.text_input("Optionale Prüfnotiz", value="")
            submitted = st.form_submit_button("TR-Status dauerhaft speichern", use_container_width=True)
        if submitted:
            try:
                record_trade_republic_status(
                    asset,
                    selected_status,
                    analysis_isin=analysis_isin,
                    tr_ticker=tr_ticker,
                    tr_isin=tr_isin,
                    tr_exchange=tr_exchange,
                    tr_currency="EUR",
                    tr_name=tr_name,
                    note=note,
                )
            except Exception as exc:
                st.error(f"TR-Status konnte nicht gespeichert werden: {exc}")
            else:
                st.success("Die listing-spezifische TR-Markierung wurde dauerhaft gespeichert.")
                st.rerun()

        if status == TR_STATUS_TRADEABLE:
            st.markdown("**Aktuellen Trade-Republic-Preis erfassen**")
            st.caption(
                "Der Preis muss direkt zum oben verknüpften TR-Listing gehören. Er verfällt nach 15 Minuten. "
                "Yahoo wird niemals als Ersatz verwendet."
            )
            with st.form(f"tr_price_reference_{key}"):
                price_eur = st.number_input(
                    "Aktueller Preis bei Trade Republic in EUR",
                    min_value=0.000001,
                    value=float(context["price"].get("price_eur") or 0.000001),
                    format="%.6f",
                )
                analysis_comparison_price = st.text_input(
                    "Zeitgleicher Vergleichskurs des analysierten Listings in EUR",
                    value="",
                    help=(
                        "Nicht der ältere Signalkurs: Für die Listing-Basis wird ein zum selben Zeitpunkt "
                        "abgelesener Kurs des analysierten Listings benötigt."
                    ),
                )
                analysis_comparison_source = st.text_input(
                    "Quelle des zeitgleichen Vergleichskurses",
                    value=str(setup.get("price_source") or "Yahoo Finance / yfinance"),
                )
                price_note = st.text_input("Optionale Preisnotiz", value="")
                price_submitted = st.form_submit_button("TR-Preis erfassen", use_container_width=True)
            if price_submitted:
                try:
                    record_trade_republic_price(
                        asset,
                        price_eur,
                        analysis_comparison_price_eur=str(analysis_comparison_price).replace(",", "."),
                        analysis_price_source=analysis_comparison_source,
                        note=price_note,
                    )
                except Exception as exc:
                    st.error(f"TR-Preis konnte nicht gespeichert werden: {exc}")
                else:
                    st.success("Der listing-spezifische TR-Preis wurde gespeichert.")
                    st.rerun()


def trade_republic_user_signal_snapshot(setup: dict, context: dict) -> dict:
    execution_plan = dict(context.get("execution_plan") or {})
    if not execution_plan:
        raise ValueError("TR-Ausführungsplan ist nicht verfügbar.")
    snapshot = copy.deepcopy(dict(setup.get("forward_signal_snapshot") or {}))
    if not snapshot:
        raise ValueError("Das unveränderbare Forward-Signal fehlt.")
    snapshot["analysis_order_plan"] = copy.deepcopy(dict(snapshot.get("order_plan") or {}))
    snapshot["order_plan"] = execution_plan
    reference = dict(context.get("reference") or {})
    price = dict(context.get("price") or {})
    snapshot["trade_republic_execution"] = {
        "status": reference.get("status"),
        "execution_ready": True,
        "analysis_listing": dict(reference.get("analysis_listing") or {}),
        "tr_listing": dict(reference.get("tr_listing") or {}),
        "price_eur": price.get("price_eur"),
        "price_source": price.get("source"),
        "price_observed_at": price.get("observed_at"),
        "analysis_comparison_price_eur": price.get("analysis_comparison_price_eur"),
        "analysis_price_source": price.get("analysis_price_source"),
        "automatic_order_execution": False,
        "broker_connection": False,
    }
    return snapshot


def render_swing_trade_card(
    setup: dict,
    settings: dict,
    active_setup_ids: set[str],
    *,
    paper_only: bool = False,
) -> None:
    context = swing_trade_republic_context(setup, settings)
    reference = dict(context["reference"])
    price = dict(context["price"])
    execution_plan = dict(context.get("execution_plan") or {})
    metadata = dict(setup.get("universe_metadata") or {})
    tr_listing = dict(reference.get("tr_listing") or {})
    card_key = str(setup.get("forward_signal_id") or setup.get("setup_id") or setup.get("symbol"))

    with st.container(border=True):
        st.subheader(f"{setup['asset_name']} · {setup['symbol']}")
        st.caption(
            f"{setup['asset_type']} · {metadata.get('region', 'Region nicht verfügbar')} · "
            f"Long · {setup['setup_type']} · Qualität {setup['quality_score']:.1f}/10"
        )
        st.write(f"**Trade-Republic-Status:** {reference.get('status', TR_STATUS_UNKNOWN)}")
        if reference.get("status") == TR_STATUS_TRADEABLE:
            st.caption(
                f"TR-Listing: {tr_listing.get('ticker', 'unbekannt')} · "
                f"ISIN {tr_listing.get('isin', 'unbekannt')} · "
                f"{tr_listing.get('exchange', 'Handelsplatz unbekannt')} · EUR"
            )
        render_trade_republic_reference_editor(setup, context, key=card_key)

        if paper_only:
            st.info(
                "Nur Paper / nicht bei Trade Republic handelbar: Das Signal bleibt vollständig im "
                "Forward-Test und in der Scannerstatistik, ist aber kein Nutzertrade."
            )
        elif reference.get("status") == TR_STATUS_TRADEABLE:
            current_col, source_col = st.columns(2)
            current_col.metric(
                "Aktueller Preis",
                format_money(price.get("price_eur"), "EUR") if price.get("available") else "TR-Preis nicht verfügbar",
            )
            source_col.metric("Preisquelle", price.get("source") or "Trade Republic – nicht verfügbar")
            if not price.get("available"):
                st.error(f"TR-Preis nicht verfügbar. {price.get('reason', '')}")
            elif not execution_plan:
                st.error(
                    "TR-Ausführungsplan nicht verfügbar. Für ältere Signale ohne getrennten Analyse-Referenzkurs "
                    "werden keine Kursmarken geschätzt."
                )
            else:
                st.markdown("**Ausführungsplan für das konkrete TR-Listing – es wird keine Order gesendet**")
                order_col, limit_col, activation_col, earliest_col = st.columns(4)
                order_col.metric("Ordertyp", execution_plan.get("order_type", "Nicht verfügbar"))
                limit_col.metric("Limit", format_money(execution_plan.get("limit_price_eur"), "EUR"))
                activation_col.metric(
                    "Aktivierung ab", format_money(execution_plan.get("activation_price_eur"), "EUR")
                )
                earliest_col.metric(
                    "Frühester Einstieg", execution_plan.get("earliest_entry_day", "Nicht verfügbar")
                )
                st.write(
                    f"**Maximalpreis:** {format_money(execution_plan.get('maximum_entry_eur'), 'EUR')} · "
                    f"**Stop:** {format_money(execution_plan.get('initial_stop_eur'), 'EUR')} · "
                    f"**Ziel 1:** {format_money(execution_plan.get('target_1_eur'), 'EUR')} · "
                    f"**Ziel 2:** "
                    f"{format_money(execution_plan.get('target_2_eur'), 'EUR') if execution_plan.get('target_2_eur') is not None else 'Nicht vorhanden'}"
                )
                if execution_plan.get("position_calculated"):
                    quantity = execution_plan.get("quantity")
                    quantity_text = (
                        f"{int(quantity)} Anteile"
                        if setup["asset_type"] in {"Aktie", "ETF"}
                        else f"{float(quantity):.6f} Einheiten"
                    )
                    st.write(
                        f"**Stückzahl:** {quantity_text} · "
                        f"**EUR-Betrag:** {format_money(execution_plan.get('capital_committed_eur'), 'EUR')} · "
                        f"**Geplanter Verlust:** {format_money(execution_plan.get('planned_loss_eur'), 'EUR')}"
                    )
                else:
                    st.caption("Ohne hinterlegtes Tradingkapital wird keine Stückzahl erfunden.")
                st.caption(str(execution_plan.get("translation_policy") or ""))

                signal_id = str(setup.get("forward_signal_id") or "")
                if signal_id and signal_id not in active_setup_ids:
                    with st.expander("Extern ausgeführten Trade dokumentieren", expanded=False):
                        st.caption("Nur nach externer eigener Ausführung. Die App sendet keine Order.")
                        with st.form(f"tr_user_trade_open_{signal_id}"):
                            traded_identifier = st.text_input(
                                "TR-Ticker oder ISIN des tatsächlich gehandelten Listings",
                                value=str(tr_listing.get("isin") or tr_listing.get("ticker") or ""),
                            )
                            actual_entry = st.number_input(
                                "Tatsächlicher Einstieg bei Trade Republic in EUR",
                                min_value=0.000001,
                                value=float(execution_plan.get("limit_price_eur") or 0.000001),
                                format="%.6f",
                            )
                            actual_quantity = st.number_input(
                                "Tatsächliche Stückzahl",
                                min_value=0.0,
                                value=float(execution_plan.get("quantity") or 0.0),
                                step=1.0 if setup["asset_type"] in {"Aktie", "ETF"} else 0.000001,
                                format="%.6f",
                            )
                            opened_date = st.date_input("Einstiegsdatum", value=pd.Timestamp.now().date())
                            opened_time = st.time_input(
                                "Einstiegszeit", value=pd.Timestamp.now().time().replace(microsecond=0)
                            )
                            note = st.text_input("Optionale Notiz", value="")
                            confirm_deviation = st.checkbox(
                                "Abweichungen vom TR-Systemplan ausdrücklich bestätigen", value=False
                            )
                            submitted = st.form_submit_button(
                                "Extern ausgeführten Trade lokal speichern", use_container_width=True
                            )
                        if submitted:
                            listing_ok, listing_message = validate_traded_listing(
                                traded_identifier,
                                expected_symbol=str(tr_listing.get("ticker") or ""),
                                expected_isin=str(tr_listing.get("isin") or ""),
                            )
                            if not listing_ok:
                                st.error(listing_message)
                            else:
                                try:
                                    create_swing_user_trade(
                                        signal_id,
                                        trade_republic_user_signal_snapshot(setup, context),
                                        actual_entry,
                                        actual_quantity,
                                        datetime.combine(opened_date, opened_time).astimezone(),
                                        note=note,
                                        confirm_deviations=confirm_deviation,
                                    )
                                except SwingUserTradeDeviationConfirmationRequired as exc:
                                    st.error(str(exc))
                                except Exception as exc:
                                    st.error(f"Nutzertrade konnte nicht gespeichert werden: {exc}")
                                else:
                                    st.success("Der externe TR-Trade wurde lokal gespeichert; keine Order wurde gesendet.")
                                    st.rerun()
                elif signal_id:
                    st.info("Für dieses objektive Signal ist bereits ein persönlicher Nutzertrade gespeichert.")

        with st.expander("Technische Analyse und objektiver Forward-Plan", expanded=paper_only):
            st.caption(
                f"Analyse-Listing: {setup['symbol']} · "
                f"{metadata.get('exchange', 'Börsenplatz nicht verfügbar')} · {setup['original_currency']}. "
                f"Quelle: {setup.get('price_source', 'Yahoo Finance / yfinance')}. "
                "Diese Analysewerte sind kein Trade-Republic-Preis."
            )
            analysis_cols = st.columns(5)
            analysis_cols[0].metric("Signalkurs (Analyse)", format_money(setup["current_price_eur"], "EUR"))
            analysis_cols[1].metric(
                "Einstiegszone (Analyse)",
                f"{format_money(setup['entry_low_eur'], 'EUR')} bis {format_money(setup['entry_high_eur'], 'EUR')}",
            )
            analysis_cols[2].metric("Stop (Analyse)", format_money(setup["stop_eur"], "EUR"))
            analysis_cols[3].metric("Ziel 1 (Analyse)", format_money(setup["target_1_eur"], "EUR"))
            analysis_cols[4].metric("CRV", f"{setup['crv']:.2f}")
            st.write(f"**Eintrittsbedingung:** {setup['entry_condition']}")
            st.write(f"**Gültig bis:** {setup['valid_until']}")
            st.caption(
                "Der objektive Yahoo-/Marktdatenplan bleibt unverändert für Paper- und Forward-Auswertung gespeichert."
            )

        st.info(setup["hit_rate_text"])
        st.markdown("**Wichtigste Gründe**")
        for reason in setup["reasons"][:3]:
            st.write(f"- {reason}")
        st.markdown(f"**Größtes Risiko:** {setup['largest_risk']}")
        st.markdown("**Nicht mehr einsteigen, wenn**")
        for condition in setup["no_entry_conditions"]:
            st.write(f"- {condition}")
        st.caption("Keine Broker-Anbindung, keine Order und keine automatische Ausführung.")


def current_active_trade_snapshot(record: dict) -> tuple[dict | None, str | None]:
    symbol = str(record.get("Ticker") or "")
    if not symbol:
        return None, "Ticker fehlt."
    try:
        data = load_price_data(symbol, "5d", "1d")
        if data.empty or "Close" not in data:
            return None, "Aktueller Kurs ist nicht verfügbar."
        current_original = float(data["Close"].dropna().iloc[-1])
        currency = str(record.get("Originalwährung") or "EUR")
        fx_rate, _ = get_fx_rate_to_eur(currency)
        if fx_rate is None:
            return None, "Aktueller Wechselkurs in Euro ist nicht verfügbar."
        return active_trade_snapshot(record, current_original * fx_rate), None
    except Exception as exc:
        return None, str(exc)


def _render_swing_background_signals_legacy() -> int:
    if not DEFAULT_SWING_FORWARD_DB_PATH.exists():
        return 0
    signals = load_swing_forward_signals(DEFAULT_SWING_FORWARD_DB_PATH)
    archive_rows = swing_forward_statistics(signals).get("archive_rows") or []
    status_by_signal = {
        str(row.get("Signal-ID") or ""): str(row.get("Status") or "") for row in archive_rows
    }
    visible_signals = [
        signal
        for signal in signals
        if status_by_signal.get(str(signal.get("signal_id") or "")) in {"stored", "still_active"}
    ]
    if not visible_signals:
        return 0

    active_ids = {
        str(state["snapshot"].get("signal_id") or "")
        for state in (
            load_swing_user_trade_states(DEFAULT_SWING_USER_DB_PATH)
            if DEFAULT_SWING_USER_DB_PATH.exists()
            else []
        )
    }
    st.subheader("Automatisch gefundene Swing-Signale")
    st.caption(
        "Diese Pläne stammen aus den regionalen Hintergrundscans. Sie sind unveränderbar gespeichert; "
        "es wurde keine Order gesendet."
    )
    for signal in reversed(visible_signals[-10:]):
        signal_id = str(signal.get("signal_id") or "")
        snapshot = dict(signal.get("snapshot") or {})
        asset = dict(snapshot.get("asset") or {})
        strategy = dict(snapshot.get("strategy") or {})
        order_plan = dict(snapshot.get("order_plan") or {})
        status = status_by_signal.get(signal_id, "stored")
        with st.container(border=True):
            st.subheader(f"{asset.get('name', asset.get('ticker', 'Unbekannt'))} · {asset.get('ticker', '')}")
            st.caption(
                f"{asset.get('asset_type', 'Asset-Typ nicht verfügbar')} · "
                f"{asset.get('region', 'Region nicht verfügbar')} · Long · "
                f"{strategy.get('setup_type', 'Setup nicht verfügbar')} · "
                f"Signal {snapshot.get('signal_at', 'Zeit nicht verfügbar')}"
            )
            st.caption(
                f"Analysiertes Listing: {asset.get('ticker', 'nicht verfügbar')} · "
                f"{asset.get('exchange', 'Börsenplatz nicht verfügbar')} · "
                f"{order_plan.get('original_currency', asset.get('original_currency', 'Währung nicht verfügbar'))}. "
                f"Kursquelle: {snapshot.get('price_source', 'Yahoo Finance / yfinance')} · "
                f"Signalkerze: {order_plan.get('signal_bar_day', 'nicht verfügbar')}."
            )
            if order_plan.get("original_currency", asset.get("original_currency")) != "EUR":
                st.warning(
                    "Die Euro-Werte sind nur eine Währungsumrechnung dieses Listings. Sie sind kein "
                    "Trade-Republic- oder LS-Exchange-Livekurs und gelten nicht für ein ADR/GDR oder anderes Listing."
                )
            if status == "still_active":
                st.info("Der objektive Paper-Trade ist aktiv und wird automatisch weiter ausgewertet.")
            else:
                st.info("Der Einstieg wird erst ab der zulässigen Folgesitzung automatisch geprüft.")
            st.markdown("**Unveränderbarer Orderplan – es wird keine Order gesendet**")
            order_col, limit_col, entry_col, stop_col = st.columns(4)
            order_col.metric("Ordertyp", order_plan.get("order_type", "Nicht verfügbar"))
            limit_col.metric("Limitpreis", format_money(order_plan.get("limit_price_eur"), "EUR"))
            entry_col.metric("Frühester Einstieg", order_plan.get("earliest_entry_day", "Nicht verfügbar"))
            stop_col.metric("Initialer Stop", format_money(order_plan.get("initial_stop_eur"), "EUR"))
            st.write(
                f"**Aktivierung ab:** {format_money(order_plan.get('activation_price_eur'), 'EUR')} · "
                f"**Maximalpreis:** {format_money(order_plan.get('maximum_entry_eur'), 'EUR')} · "
                f"**Ziel 1:** {format_money(order_plan.get('target_1_eur'), 'EUR')} · "
                f"**Ziel 2:** {format_money(order_plan.get('target_2_eur'), 'EUR') if order_plan.get('target_2_eur') is not None else 'Nicht vorhanden'}"
            )
            st.caption(
                f"Gültig bis {order_plan.get('valid_until', 'Nicht verfügbar')} · "
                f"Originalwährung {order_plan.get('original_currency', asset.get('original_currency', 'Nicht verfügbar'))} · "
                "ohne Tradingkapital keine erfundene Stückzahl."
            )
            with st.expander("Lösch- und Widerlegungsbedingungen", expanded=False):
                for condition in order_plan.get("delete_conditions") or []:
                    st.write(f"- {condition}")

            if signal_id and signal_id not in active_ids:
                with st.expander("Trade getätigt", expanded=False):
                    st.caption(
                        "Nur bestätigen, wenn du den Trade bereits selbst außerhalb der App ausgeführt hast. "
                        "Hierdurch wird keine Order gesendet."
                    )
                    with st.form(f"background_user_trade_open_{signal_id}"):
                        traded_identifier = st.text_input(
                            "Ticker oder ISIN des tatsächlich gehandelten Listings",
                            value=str(asset.get("ticker") or ""),
                            key=f"background_user_listing_{signal_id}",
                        )
                        actual_entry = st.number_input(
                            "Tatsächlicher Einstieg in Euro",
                            min_value=0.000001,
                            value=float(order_plan.get("limit_price_eur") or 0.000001),
                            format="%.6f",
                        )
                        actual_quantity = st.number_input(
                            "Tatsächliche Stückzahl",
                            min_value=0.0,
                            value=float(order_plan.get("quantity") or 0.0),
                            step=1.0 if asset.get("asset_type") in {"Aktie", "ETF"} else 0.000001,
                            format="%.6f",
                        )
                        opened_date = st.date_input(
                            "Einstiegsdatum",
                            value=pd.Timestamp.now().date(),
                            key=f"background_user_open_date_{signal_id}",
                        )
                        opened_time = st.time_input(
                            "Einstiegszeit",
                            value=pd.Timestamp.now().time().replace(microsecond=0),
                            key=f"background_user_open_time_{signal_id}",
                        )
                        note = st.text_input("Optionale Notiz", value="", key=f"background_user_note_{signal_id}")
                        confirm_deviation = st.checkbox(
                            "Abweichungen vom Systemplan ausdrücklich bestätigen",
                            value=False,
                            key=f"background_user_deviation_{signal_id}",
                        )
                        open_submitted = st.form_submit_button(
                            "Extern ausgeführten Trade lokal speichern",
                            use_container_width=True,
                        )
                    if open_submitted:
                        listing_ok, listing_message = validate_traded_listing(
                            traded_identifier,
                            expected_symbol=str(asset.get("ticker") or ""),
                            expected_isin=asset.get("isin"),
                        )
                        if not listing_ok:
                            st.error(listing_message)
                            continue
                        try:
                            create_swing_user_trade(
                                signal_id,
                                snapshot,
                                actual_entry,
                                actual_quantity,
                                datetime.combine(opened_date, opened_time).astimezone(),
                                note=note,
                                confirm_deviations=confirm_deviation,
                            )
                        except SwingUserTradeDeviationConfirmationRequired as exc:
                            st.error(str(exc))
                        except Exception as exc:
                            st.error(f"Nutzertrade konnte nicht gespeichert werden: {exc}")
                        else:
                            st.success(
                                "Persönlicher Trade wurde lokal getrennt gespeichert. Es wurde keine Order gesendet."
                            )
                            st.rerun()
            elif signal_id:
                st.info("Dieser objektive Plan besitzt bereits einen getrennt gespeicherten persönlichen Nutzertrade.")
    return len(visible_signals)


def swing_forward_signal_as_setup(signal: dict) -> dict:
    snapshot = dict(signal.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    strategy = dict(snapshot.get("strategy") or {})
    plan = dict(snapshot.get("order_plan") or {})
    entry = float(plan.get("limit_price_eur") or 0)
    stop = float(plan.get("initial_stop_eur") or 0)
    target = float(plan.get("target_1_eur") or 0)
    risk = entry - stop
    crv = (target - entry) / risk if risk > 0 and target > entry else 0.0
    historical_cases = int(strategy.get("historical_cases") or 0)
    historical_hit_rate = strategy.get("historical_hit_rate")
    return {
        "asset_name": str(asset.get("name") or asset.get("ticker") or "Unbekannt"),
        "symbol": str(asset.get("ticker") or ""),
        "asset_type": str(asset.get("asset_type") or "Unbekannt"),
        "setup_type": str(strategy.get("setup_type") or "Unbekannt"),
        "quality_score": float(strategy.get("quality_score") or 0),
        "universe_metadata": {
            "isin": asset.get("isin"),
            "exchange": asset.get("exchange"),
            "region": asset.get("region"),
            "category": asset.get("category"),
        },
        "original_currency": str(plan.get("original_currency") or asset.get("original_currency") or ""),
        "price_source": str((snapshot.get("data_contract") or {}).get("price_source") or "Yahoo Finance / yfinance"),
        "signal_bar_day": plan.get("signal_bar_day"),
        "current_price_eur": float(plan.get("analysis_reference_price_eur") or entry),
        "entry_low_eur": float(plan.get("activation_price_eur") or entry),
        "entry_high_eur": float(plan.get("maximum_entry_eur") or entry),
        "stop_eur": stop,
        "target_1_eur": target,
        "target_2_eur": plan.get("target_2_eur"),
        "max_entry_eur": plan.get("maximum_entry_eur"),
        "crv": crv,
        "entry_condition": str(plan.get("entry_method") or "Regel des unveränderbaren Analyseplans"),
        "valid_until": str(plan.get("valid_until") or "Nicht verfügbar"),
        "hit_rate_text": (
            f"Historische Trefferquote dieses Segments: {float(historical_hit_rate):.1f}% aus {historical_cases} Fällen."
            if historical_hit_rate is not None and historical_cases >= DEFAULT_SWING_THRESHOLDS.min_historical_cases
            else "Trefferwahrscheinlichkeit noch nicht belastbar."
        ),
        "reasons": [
            f"Objektives Forward-Signal der Strategie {strategy.get('strategy_version', 'unbekannt')}.",
            f"Setup: {strategy.get('setup_type', 'unbekannt')}.",
        ],
        "largest_risk": "Das technische Setup kann durch Markt-, Nachrichten- oder Kurslückenrisiken ungültig werden.",
        "no_entry_conditions": list(plan.get("delete_conditions") or []),
        "position_size": {
            "quantity": plan.get("quantity"),
            "position_value_eur": plan.get("capital_committed_eur"),
            "planned_loss_notice": "Der Forward-Plan ist eine Paper-Dokumentation und keine Order.",
        },
        "order_plan": plan,
        "forward_signal_id": str(signal.get("signal_id") or ""),
        "forward_signal_snapshot": snapshot,
        "setup_id": str(snapshot.get("setup_id") or signal.get("signal_id") or ""),
    }


def swing_forward_trade_republic_references(signals: list[dict], settings: dict) -> dict[str, dict]:
    references: dict[str, dict] = {}
    for signal in signals:
        setup = swing_forward_signal_as_setup(signal)
        context = swing_trade_republic_context(setup, settings)
        reference = dict(context.get("reference") or {})
        listing_key = str(reference.get("analysis_listing_key") or "")
        if listing_key:
            references[listing_key] = {
                **reference,
                "execution_ready": bool(context.get("execution_ready")),
            }
        signal_id = str(signal.get("signal_id") or "")
        if signal_id:
            references[signal_id] = {
                **reference,
                "execution_ready": bool(context.get("execution_ready")),
            }
    return references


def render_swing_background_signals(settings: dict) -> int:
    if not DEFAULT_SWING_FORWARD_DB_PATH.exists():
        return 0
    signals = load_swing_forward_signals(DEFAULT_SWING_FORWARD_DB_PATH)
    archive_rows = swing_forward_statistics(signals).get("archive_rows") or []
    status_by_signal = {
        str(row.get("Signal-ID") or ""): str(row.get("Status") or "") for row in archive_rows
    }
    visible_signals = [
        signal
        for signal in signals
        if status_by_signal.get(str(signal.get("signal_id") or "")) in {"stored", "still_active"}
    ]
    if not visible_signals:
        return 0
    active_ids = {
        str(state["snapshot"].get("signal_id") or "")
        for state in (
            load_swing_user_trade_states(DEFAULT_SWING_USER_DB_PATH)
            if DEFAULT_SWING_USER_DB_PATH.exists()
            else []
        )
    }
    setups = [swing_forward_signal_as_setup(signal) for signal in reversed(visible_signals[-10:])]
    tr_setups: list[dict] = []
    paper_setups: list[dict] = []
    for setup in setups:
        target = (
            tr_setups
            if trade_republic_reference(swing_trade_republic_asset(setup)).get("status")
            == TR_STATUS_TRADEABLE
            else paper_setups
        )
        target.append(setup)
    executable_count = sum(
        swing_trade_republic_context(setup, settings).get("execution_ready") for setup in tr_setups
    )
    st.subheader("Automatisch gefundene Swing-Signale")
    st.caption(
        f"Scannerqualität gesamt: {len(setups)} sichtbare Signale · "
        f"TR-handelbare Listings: {len(tr_setups)} · aktuell ausführbare TR-Pläne: {executable_count}. "
        "Alle Paper-Signale werden unverändert weiter ausgewertet."
    )
    if tr_setups:
        st.markdown("**Bei Trade Republic handelbar**")
        for setup in tr_setups:
            render_swing_trade_card(setup, settings, active_ids)
    else:
        st.info("Kein sichtbares Signal ist aktuell listing-spezifisch als bei Trade Republic handelbar verifiziert.")
    if paper_setups:
        with st.expander("Nur Paper / nicht bei Trade Republic handelbar", expanded=False):
            for setup in paper_setups:
                render_swing_trade_card(setup, settings, active_ids, paper_only=True)
    return len(visible_signals)


def render_swing_user_trades() -> None:
    st.subheader("Meine aktiven Trades")
    if not DEFAULT_SWING_USER_DB_PATH.exists():
        st.caption("Keine persönlich bestätigten Trades vorhanden.")
        return
    states = load_swing_user_trade_states(DEFAULT_SWING_USER_DB_PATH)
    active = [state for state in states if state["status"] == "Aktiv"]
    if not active:
        st.caption("Keine persönlich bestätigten aktiven Trades vorhanden.")
    for state in active:
        snapshot = dict(state["snapshot"])
        asset = dict(snapshot.get("asset") or {})
        plan = dict(snapshot.get("system_order_plan") or {})
        tr_execution = dict(snapshot.get("trade_republic_execution") or {})
        analysis_listing = dict(tr_execution.get("analysis_listing") or {})
        tr_price_asset = {
            "ticker": analysis_listing.get("ticker"),
            "isin": analysis_listing.get("isin"),
            "exchange": analysis_listing.get("exchange"),
            "original_currency": analysis_listing.get("currency"),
        }
        current_tr_price = (
            trade_republic_price(tr_price_asset)
            if analysis_listing.get("ticker")
            else {
                "available": False,
                "label": "TR-Preis nicht verfügbar",
                "reason": "Dieser ältere Nutzertrade besitzt keine listing-spezifische TR-Zuordnung.",
            }
        )
        trade_id = str(state["user_trade_id"])
        entry = float(snapshot["actual_entry_eur"])
        remaining = float(state["remaining_quantity"])
        with st.container(border=True):
            st.markdown(f"**{asset.get('name', asset.get('ticker', 'Trade'))} · {asset.get('ticker', '')}**")
            st.caption(
                f"Persönlicher Nutzertrade · eröffnet {snapshot['opened_at']} · "
                "objektiver Paper-Verlauf bleibt unverändert"
            )
            cols = st.columns(5)
            cols[0].metric(
                "Aktueller Preis",
                format_money(current_tr_price.get("price_eur"), "EUR")
                if current_tr_price.get("available")
                else "TR-Preis nicht verfügbar",
            )
            cols[1].metric("Einstieg", format_money(entry, "EUR"))
            cols[2].metric("Restmenge", f"{remaining:g}")
            cols[3].metric("Initialer Stop", format_money(snapshot["initial_stop_eur"], "EUR"))
            cols[4].metric("Aktueller Stop", format_money(state["current_stop_eur"], "EUR"))
            if current_tr_price.get("available"):
                st.caption(
                    f"Aktueller Preis: {current_tr_price.get('source')} · "
                    f"erfasst {current_tr_price.get('observed_at')} · konkretes TR-Listing."
                )
            else:
                st.warning(
                    f"TR-Preis nicht verfügbar. {current_tr_price.get('reason', '')} "
                    "Yahoo wird nicht als Ersatz für Preis oder Gewinn/Verlust verwendet."
                )
            if analysis_listing.get("ticker"):
                with st.expander("Aktuellen TR-Preis aktualisieren", expanded=False):
                    with st.form(f"active_user_tr_price_{trade_id}"):
                        refreshed_tr_price = st.number_input(
                            "Aktueller Preis des verknüpften TR-Listings in EUR",
                            min_value=0.000001,
                            value=float(current_tr_price.get("price_eur") or entry),
                            format="%.6f",
                        )
                        refreshed_analysis_price = st.text_input(
                            "Zeitgleicher Vergleichskurs des analysierten Listings in EUR",
                            value="",
                        )
                        refreshed_analysis_source = st.text_input(
                            "Quelle des zeitgleichen Vergleichskurses",
                            value="Yahoo Finance / yfinance",
                        )
                        submitted_price = st.form_submit_button(
                            "TR-Preis erfassen",
                            use_container_width=True,
                        )
                    if submitted_price:
                        try:
                            record_trade_republic_price(
                                tr_price_asset,
                                refreshed_tr_price,
                                analysis_comparison_price_eur=str(refreshed_analysis_price).replace(",", "."),
                                analysis_price_source=refreshed_analysis_source,
                            )
                        except Exception as exc:
                            st.error(f"TR-Preis konnte nicht gespeichert werden: {exc}")
                        else:
                            st.success("Der aktuelle TR-Preis wurde listing-spezifisch gespeichert.")
                            st.rerun()
            guidance = None
            try:
                ticker = str(asset.get("ticker") or "")
                current_data = load_price_data(ticker, "6mo", "1d")
                current_original = float(current_data["Close"].dropna().iloc[-1])
                current_fx, _ = get_fx_rate_to_eur(str(asset.get("original_currency") or "EUR"))
                if current_fx is not None and current_tr_price.get("available"):
                    guidance_time = datetime.now().astimezone()
                    market_context = swing_market_context_from_daily_bars(
                        current_data,
                        fx_rate_to_eur=current_fx,
                        evaluated_at=guidance_time,
                        asset_type=str(asset.get("asset_type") or "Aktie"),
                        region=asset.get("region"),
                    )
                    refreshed_event = None
                    try:
                        refreshed_event = next_known_event_date(load_ticker_info(ticker), pd.Timestamp(guidance_time))
                    except Exception:
                        refreshed_event = None
                    stored_event = (snapshot.get("strategy") or {}).get("known_event_date_at_signal")
                    event_value = refreshed_event or stored_event
                    if event_value is not None:
                        event_timestamp = pd.Timestamp(event_value)
                        if event_timestamp.tzinfo is not None:
                            event_timestamp = event_timestamp.tz_convert(None)
                        market_context["days_to_known_event"] = (
                            event_timestamp.date() - guidance_time.date()
                        ).days
                        market_context["known_event_date"] = event_timestamp.date().isoformat()
                        market_context["event_source"] = (
                            "aktuell geladene Yahoo-Metadaten" if refreshed_event is not None else "unveränderbarer Signal-Snapshot"
                        )
                        market_context["unavailable_factors"] = [
                            factor
                            for factor in market_context.get("unavailable_factors") or []
                            if factor != "kommende Unternehmensereignisse"
                        ]
                        market_context.setdefault("checked_factors", []).append("kommendes Unternehmensereignis")
                    guidance = swing_user_trade_guidance(
                        state,
                        float(current_tr_price["price_eur"]),
                        guidance_time,
                        market_context=market_context,
                    )
            except Exception:
                guidance = None
            if guidance is None:
                guidance = {
                    "status": "Daten derzeit nicht belastbar",
                    "reason": (
                        "Ein frischer Trade-Republic-Preis ist nicht verfügbar. Deshalb werden aktueller "
                        "Gewinn/Verlust und preisabhängige Handlungshinweise nicht aus Yahoo abgeleitet. "
                        "Der gespeicherte Stop bleibt unverändert."
                    ),
                    "automatic_order_execution": False,
                }
            st.markdown(f"**Aktuelle Bewertung:** {guidance['status']}")
            st.write(guidance["reason"])
            if guidance.get("checked_factors"):
                st.caption("Automatisch geprüft: " + ", ".join(guidance["checked_factors"]))
            if guidance.get("unavailable_factors"):
                st.caption("Noch nicht belastbar automatisch geprüft: " + ", ".join(guidance["unavailable_factors"]))
            if guidance.get("unrealized_pnl_eur") is not None:
                st.write(
                    f"**Nicht realisiert:** {format_money(guidance['unrealized_pnl_eur'], 'EUR')} "
                    f"({guidance['unrealized_pnl_pct']:+.2f} %)"
                )
            st.write(
                f"**Nächstes Systemziel:** {format_money(plan.get('target_1_eur'), 'EUR')} · "
                f"**Bisher realisiert:** {format_money(state['realized_pnl_eur'], 'EUR')}"
            )
            if snapshot.get("deviations"):
                st.warning("Bestätigte Abweichungen: " + " | ".join(snapshot["deviations"]))
            stop_col, partial_col, close_col = st.columns(3)
            with stop_col:
                with st.form(f"user_stop_{trade_id}"):
                    new_stop = st.number_input(
                        "Neuer engerer Stop EUR",
                        min_value=0.000001,
                        value=float(state["current_stop_eur"]),
                        format="%.6f",
                    )
                    submitted = st.form_submit_button("Stop nachgezogen", use_container_width=True)
                if submitted:
                    try:
                        tighten_swing_user_stop(trade_id, new_stop, datetime.now().astimezone())
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        st.success("Stop-Nachzug lokal dokumentiert. Keine Order wurde geändert.")
                        st.rerun()
            with partial_col:
                with st.form(f"user_partial_{trade_id}"):
                    partial_quantity = st.number_input(
                        "Teilverkaufsmenge",
                        min_value=0.0,
                        value=0.0,
                        format="%.6f",
                    )
                    partial_exit = st.number_input(
                        "Teilverkaufskurs EUR",
                        min_value=0.000001,
                        value=entry,
                        format="%.6f",
                    )
                    submitted = st.form_submit_button("Teilverkauf erfasst", use_container_width=True)
                if submitted:
                    try:
                        record_swing_user_partial_sale(
                            trade_id,
                            partial_quantity,
                            partial_exit,
                            datetime.now().astimezone(),
                        )
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        st.success("Teilverkauf lokal dokumentiert. Keine Order wurde ausgeführt.")
                        st.rerun()
            with close_col:
                with st.form(f"user_close_{trade_id}"):
                    close_exit = st.number_input(
                        "Ausstiegskurs EUR",
                        min_value=0.000001,
                        value=entry,
                        format="%.6f",
                    )
                    submitted = st.form_submit_button("Trade geschlossen", use_container_width=True)
                if submitted:
                    try:
                        close_swing_user_trade(
                            trade_id,
                            close_exit,
                            datetime.now().astimezone(),
                        )
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        st.success("Persönlicher Trade lokal geschlossen. Keine Order wurde ausgeführt.")
                        st.rerun()

    closed = [state for state in states if state["status"] == "Geschlossen"]
    if closed:
        with st.expander(f"Geschlossene persönliche Trades ({len(closed)})", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Ticker": (state["snapshot"].get("asset") or {}).get("ticker"),
                            "Eröffnet": state["snapshot"].get("opened_at"),
                            "Einstieg EUR": state["snapshot"].get("actual_entry_eur"),
                            "Realisierter Gewinn/Verlust EUR": state["realized_pnl_eur"],
                        }
                        for state in closed
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )


def render_swing_walk_forward_research() -> None:
    with st.expander("Historische Walk-Forward-Forschung", expanded=False):
        try:
            campaign_config = load_campaign_config()
            campaign_state = load_campaign_state()
            campaign_universe = load_swing_universe(DEFAULT_SWING_UNIVERSE_PATH)
            campaign_tickers = [asset.ticker for asset in campaign_universe.assets if asset.active]
            current_campaign_jobs = campaign_jobs(
                campaign_config,
                campaign_tickers,
                now=datetime.now().astimezone(),
                weekly_epoch=campaign_state.get("active_week_epoch"),
            )
            current_campaign_status = campaign_status(current_campaign_jobs, campaign_state)
        except Exception as exc:
            st.caption(f"Forschungskampagnenstatus nicht verfügbar: {exc}")
        else:
            st.write(
                "Rotierende Forschungskampagne: "
                f"{current_campaign_status['jobs_completed']}/{current_campaign_status['jobs_total']} Shards "
                f"abgeschlossen · {current_campaign_status['jobs_pending']} offen"
            )
            fixed_rounds = list(current_campaign_status.get("fixed_rounds") or [])
            if fixed_rounds:
                st.caption(
                    "Historische Testrunden: "
                    + " · ".join(
                        f"{item['selection_round']} {item['jobs_completed']}/{item['jobs_total']}"
                        for item in fixed_rounds
                    )
                )
            st.caption(
                "Offene Shards starten tagsüber im 15-Minuten-Raster, jedoch nie parallel. Geschützte Zeiten "
                "für reale Swing-Scans und Abendprognosen werden ausgelassen. Wiederholte Evidenz wird nicht doppelt gezählt."
            )
        if not st.checkbox(
            "Historische Detailauswertung laden",
            value=False,
            key="load_swing_walk_forward_research_details",
        ):
            st.caption(
                "Die große append-only Forschungsdatenbank wird erst auf Wunsch ausgewertet, "
                "damit der Swing-Bereich schnell öffnet."
            )
            return
        summary = swing_walk_forward_summary(DEFAULT_SWING_WALK_FORWARD_DB_PATH)
        raw_evaluated = int(summary.get("raw_evaluated") or summary.get("evaluated") or 0)
        effective_evaluated = int(
            summary.get("effective_independent_evaluated") or raw_evaluated
        )
        if summary.get("current_research_cases"):
            st.write(
                f"Aktueller Forschungsvertrag: {summary['cases']} Rohfälle · ausgewertet: "
                f"{raw_evaluated} roh / {effective_evaluated} effektiv unabhängig · "
                f"ältere getrennte Fälle: {summary.get('legacy_cases', 0)}"
            )
        else:
            st.write(
                f"Bisherige technische Kontrollfälle: {summary['cases']} Rohfälle · ausgewertet: "
                f"{raw_evaluated} roh / {effective_evaluated} effektiv unabhängig"
            )
        if summary.get("hit_rate_pct") is not None:
            metric_text = (
                f"Trefferquote: {summary['hit_rate_pct']:.1f}% · "
                f"Durchschnitt: {float(summary.get('average_r') or 0):+.3f} R"
            )
            if summary.get("profit_factor") is not None:
                metric_text += f" · Profitfaktor: {summary['profit_factor']:.2f}"
            st.write(metric_text)
        if summary.get("dependency_adjustment_required"):
            st.caption(
                f"Robustheitsinterpretation: {summary.get('dependent_listing_clusters', 0)} "
                "überlappende Issuer-/Listingcluster werden bei Unsicherheit und Mindestfallgates nicht "
                "als vollständig unabhängige Evidenz gezählt. Einzeltrades, Trefferquote, R, "
                "Profitfaktor und Drawdown oben bleiben unveränderte Rohmetriken."
            )
        st.caption(
            "Historische Fälle bleiben technisch getrennt von echten Forward-Trades. Sie dürfen nur "
            "versionierte Shadow-Challenger begründen und aktivieren niemals automatisch Produktionsregeln."
        )
        forward_linkage = dict(summary.get("real_forward_linkage") or {})
        if forward_linkage.get("links"):
            st.write(
                "Verknüpfung mit echten Forward-Tests: "
                f"{forward_linkage.get('exact_same_trade', 0)} exakt gleiche Trades · "
                f"{forward_linkage.get('related_same_asset_day', 0)} verwandte Fälle · "
                f"{forward_linkage.get('historical_monitoring_excluded', 0)} historische "
                "Doppelzählungen ausgeschlossen"
            )
        st.caption(
            "Bei exakt gleichem Asset, Signaltag, Setup und Ausführungsplan hat der echte Forward-Fall Vorrang. "
            "Andere Strategien oder Pläne bleiben getrennte Experimente; keine Quelldatei wird umgeschrieben."
        )
        observational_report = dict(summary.get("observational_rsi_ema") or {})
        if observational_report.get("feature_cases"):
            st.markdown("**Beobachtende RSI-/EMA-Segmente**")
            st.write(
                f"Features vorhanden: {observational_report.get('feature_cases', 0)} von "
                f"{observational_report.get('eligible_cases', 0)} geeigneten Fällen · "
                f"Legacy/noch nicht vorhanden: {observational_report.get('legacy_or_unavailable_cases', 0)}"
            )
            st.caption(
                "Diese festen Segmente beschreiben ausschließlich historische Muster. Kleine Gruppen bleiben "
                "als nicht belastbar markiert; es erfolgt weder eine Schwellenwertsuche noch eine automatische "
                "Regel-, Profil- oder Produktionsänderung. Holdout wird nicht zur nachträglichen Regelauswahl verwendet."
            )
            segment_titles = {
                "rsi_ranges": "RSI-Bereiche",
                "ema20_vs_ema50": "EMA20 gegenüber EMA50",
                "close_vs_ema20": "Kurs gegenüber EMA20",
                "close_vs_ema50": "Kurs gegenüber EMA50",
                "close_ema_stack": "Kurs-/EMA-Anordnung",
                "rsi_by_setup": "RSI nach Setup",
                "ema20_vs_ema50_by_setup": "EMA20/EMA50 nach Setup",
                "close_ema_stack_by_setup": "Kurs-/EMA-Anordnung nach Setup",
                "market_phases": "Marktphase",
                "volatility_regimes": "Volatilitätsregime",
            }
            with st.expander("RSI-/EMA-Segmenttabellen", expanded=False):
                for segment_key, segment_rows in dict(
                    observational_report.get("segments") or {}
                ).items():
                    display_rows = []
                    for segment_row in segment_rows:
                        split_metrics = {
                            "Gesamt": segment_row,
                            "Development": dict(segment_row.get("by_split") or {}).get(
                                "development", {}
                            ),
                            "Validation": dict(segment_row.get("by_split") or {}).get(
                                "validation", {}
                            ),
                            "Holdout": dict(segment_row.get("by_split") or {}).get(
                                "holdout", {}
                            ),
                        }
                        for split_label, metrics_row in split_metrics.items():
                            display_rows.append(
                                {
                                    "Segment": segment_row.get("segment"),
                                    "Fenster": split_label,
                                    "Fälle": int(metrics_row.get("cases") or 0),
                                    "Ausgewertet": int(metrics_row.get("evaluated") or 0),
                                    "Ø R": metrics_row.get("average_r"),
                                    "Profitfaktor": metrics_row.get("profit_factor"),
                                    "Trefferquote %": metrics_row.get("hit_rate_pct"),
                                    "Max Drawdown R": metrics_row.get("maximum_drawdown_r"),
                                    "Kleine Stichprobe": bool(
                                        int(metrics_row.get("effective_independent_evaluated") or 0)
                                        < int(observational_report.get("minimum_segment_cases") or 50)
                                    ),
                                }
                            )
                    if display_rows:
                        st.markdown(f"**{segment_titles.get(segment_key, segment_key)}**")
                        st.dataframe(
                            pd.DataFrame(display_rows),
                            use_container_width=True,
                            hide_index=True,
                        )
        recent_monitoring = dict(summary.get("recent_monitoring") or {})
        if recent_monitoring.get("evaluated"):
            st.write(
                "Jüngstes Monitoring: "
                f"{recent_monitoring['evaluated']} Ergebnisse · "
                f"Trefferquote {float(recent_monitoring.get('hit_rate_pct') or 0):.1f}% · "
                f"Durchschnitt {float(recent_monitoring.get('average_r') or 0):+.3f} R"
            )
            st.caption(
                "Diese wiederkehrenden jüngsten Fälle messen aktuelle Marktpassung. Sie dürfen Validation, "
                "Holdout und Strategiefreigabe nicht verbessern."
            )
        comparison = dict(summary.get("strategy_comparison") or {})
        comparison_rows = list(comparison.get("rows") or [])
        if comparison_rows:
            st.markdown("**Strategievergleich mit getrenntem Holdout**")
            st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)
            st.caption(
                "Pareto bedeutet nur: Im unberührten Holdout wurde keine andere geprüfte Version sowohl bei "
                "Trefferquote als auch Durchschnitts-R eindeutig besser. Es ist keine Produktionsfreigabe."
            )
        challenger_report = dict(summary.get("technical_challengers") or {})
        challenger_rows = list(challenger_report.get("challengers") or [])
        if challenger_rows:
            st.markdown("**Technische Long-v1-Challenger (nur Forschung)**")
            st.dataframe(pd.DataFrame(challenger_rows), use_container_width=True, hide_index=True)
            st.caption(
                "RSI, EMA20/EMA50, Kombinationen sowie Pullback und Breakout bleiben getrennt. "
                "Interessant bedeutet nur einen stabilen Vorteil in Validation und Holdout; "
                "eine automatische Produktionsaktivierung ist ausgeschlossen."
            )
        if summary.get("by_market_phase"):
            st.markdown("**Ergebnisse nach Marktphase**")
            st.dataframe(pd.DataFrame(summary["by_market_phase"]), use_container_width=True, hide_index=True)
        for title, key in (
            ("Ergebnisse nach Asset-Typ", "by_asset_type"),
            ("Ergebnisse nach Setup", "by_setup_type"),
            ("Ergebnisse nach Volatilität", "by_volatility_regime"),
            ("Ergebnisse nach Forschungsfenster", "by_research_split"),
            ("Ergebnisse nach historischer Testrunde", "by_selection_round"),
            ("Ergebnisse nach Samplingmodus", "by_sampling_mode"),
            ("Ergebnisse nach Signaljahr", "by_signal_year"),
        ):
            if summary.get(key):
                st.markdown(f"**{title}**")
                st.dataframe(pd.DataFrame(summary[key]), use_container_width=True, hide_index=True)
        cases = load_swing_walk_forward_cases(DEFAULT_SWING_WALK_FORWARD_DB_PATH, limit=500)
        archive_rows = swing_walk_forward_archive_rows(cases)
        if archive_rows:
            st.markdown("**Einzelne historische Fälle – neueste 500**")
            st.dataframe(pd.DataFrame(archive_rows), use_container_width=True, hide_index=True)


def render_swing_bot_evidence_status() -> None:
    with st.expander("Autonomer Paper-Bot und Shadow-Live", expanded=False):
        paper_audit = paper_bot_store_audit(DEFAULT_SWING_PAPER_DB_PATH)
        shadow_audit = shadow_live_store_audit(DEFAULT_SWING_SHADOW_DB_PATH)
        freeze_audit = strategy_freeze_store_audit(DEFAULT_STRATEGY_FREEZE_DB_PATH)
        st.write(
            f"Paper-Bot: {paper_audit.get('signals', 0)} Signale · "
            f"{paper_audit.get('events', 0)} Zustandsereignisse · Status {paper_audit.get('status')}"
        )
        st.write(
            f"Shadow-Live: {shadow_audit.get('drafts', 0)} Orderentwürfe · "
            f"Status {shadow_audit.get('status')}"
        )
        st.write(
            f"Strategie-Freezes: {freeze_audit.get('freezes', 0)} unveränderbare Versionen · "
            f"Status {freeze_audit.get('status')}"
        )
        if DEFAULT_SWING_PAPER_DB_PATH.exists() and DEFAULT_SWING_SHADOW_DB_PATH.exists():
            comparison = shadow_paper_comparison(
                DEFAULT_SWING_SHADOW_DB_PATH,
                DEFAULT_SWING_PAPER_DB_PATH,
            )
            st.caption(
                f"Paper/Shadow verglichen: {comparison['compared']} · "
                f"abweichende Pläne: {comparison['plan_deviations']}"
            )
        signals = load_paper_signals(DEFAULT_SWING_PAPER_DB_PATH)
        if signals:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Ticker": (item["snapshot"].get("asset") or {}).get("ticker"),
                            "Signal": item["snapshot"].get("signal_at"),
                            "Setup": (item["snapshot"].get("strategy") or {}).get("setup_type"),
                            "Letzter Zustand": (
                                item["events"][-1].get("event_type")
                                if item.get("events")
                                else "virtuelle Order gespeichert"
                            ),
                            "Positionsstatus": derive_paper_position_state(item)["status"],
                        }
                        for item in signals[-200:]
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        st.caption(
            "Alle drei Speicher sind append-only und strikt von Walk-Forward, echtem Forward-Test "
            "und persönlichen Trades getrennt. Paper und Shadow besitzen keinen Broker- oder Echtgeldpfad."
        )


def render_active_swing_trades() -> None:
    records = active_trade_records()
    st.subheader("Offene Trades")
    if not records:
        st.caption("Keine manuell geöffneten Trades vorhanden.")
        return
    for record in records:
        setup_id = str(record.get("Setup-ID") or record.get("setup_id") or record.get("Ticker"))
        snapshot, error = current_active_trade_snapshot(record)
        with st.container(border=True):
            st.markdown(f"**{record.get('Asset', record.get('Ticker'))} · {record.get('Ticker')}**")
            st.caption(f"{record.get('Setup-Typ', 'Swing-Trade')} · eröffnet {record.get('Eröffnet am', 'Datum nicht verfügbar')}")
            if error or snapshot is None:
                st.warning(f"Aktualisierung nicht möglich: {error}")
                continue
            price_col, pnl_col, stop_col, target_col = st.columns(4)
            price_col.metric("Aktueller Kurs", format_money(snapshot["current_price_eur"], "EUR"))
            pnl_col.metric(
                "Gewinn / Verlust",
                format_money(snapshot["pnl_eur"], "EUR"),
                f"{snapshot['pnl_pct']:+.2f} %",
            )
            stop_col.metric(
                "Aktueller Stop",
                "Nicht verfügbar" if snapshot["current_stop_eur"] is None else format_money(snapshot["current_stop_eur"], "EUR"),
            )
            target_col.metric(
                "Nächstes Ziel",
                "Kein weiteres Ziel" if snapshot["next_target_eur"] is None else format_money(snapshot["next_target_eur"], "EUR"),
            )
            st.markdown(f"**Aktuelle Handlung:** {snapshot['action']}")
            st.write(snapshot["reason"])
            st.caption(f"Letzte Aktualisierung: {snapshot['updated_at']}")

            control_col, exit_col = st.columns(2)
            with control_col:
                with st.form(f"stop_update_{setup_id}"):
                    current_stop = float(snapshot["current_stop_eur"] or record.get("Tatsächlicher Einstieg EUR") or 0.01)
                    new_stop = st.number_input(
                        "Neuer Stop in Euro",
                        min_value=0.000001,
                        value=current_stop,
                        format="%.6f",
                    )
                    stop_submitted = st.form_submit_button("Stop lokal aktualisieren", use_container_width=True)
                if stop_submitted:
                    success, message = update_manual_trade_stop(setup_id, new_stop)
                    (st.success if success else st.error)(message)
                    if success:
                        st.rerun()
            with exit_col:
                with st.form(f"close_trade_{setup_id}"):
                    exit_price = st.number_input(
                        "Tatsächlicher Ausstiegskurs in Euro",
                        min_value=0.000001,
                        value=float(snapshot["current_price_eur"]),
                        format="%.6f",
                    )
                    exit_date = st.date_input("Ausstiegsdatum", value=pd.Timestamp.now().date(), key=f"exit_date_{setup_id}")
                    exit_time = st.time_input(
                        "Ausstiegszeit",
                        value=pd.Timestamp.now().time().replace(microsecond=0),
                        key=f"exit_time_{setup_id}",
                    )
                    exit_submitted = st.form_submit_button("Ausstieg dokumentieren", use_container_width=True)
                if exit_submitted:
                    success, message = mark_trade_manually_closed(
                        setup_id,
                        exit_price,
                        datetime.combine(exit_date, exit_time),
                    )
                    (st.success if success else st.error)(message)
                    if success:
                        st.rerun()


def render_swing_scanner(scan_result: dict, settings: dict) -> None:
    approved = scan_result.get("approved", [])
    rejected = scan_result.get("rejected", [])
    errors = scan_result.get("errors", [])
    statistics = scan_result.get("statistics", {})
    summary_cols = st.columns(4)
    summary_cols[0].metric("Marktlage", scan_result.get("market_label", "Nicht verfügbar"))
    summary_cols[1].metric("Scanzeitpunkt", pd.Timestamp(scan_result["last_scan"]).strftime("%d.%m.%Y %H:%M"))
    summary_cols[2].metric("Universum", int(statistics.get("universe_size", scan_result.get("checked_assets", 0))))
    summary_cols[3].metric("Kursdaten geladen", int(statistics.get("loaded_assets", 0)))
    stage_cols = st.columns(4)
    stage_cols[0].metric("Vorfilter ausgewählt", int(statistics.get("prefilter_candidates", 0)))
    stage_cols[1].metric("Tief geprüft", int(statistics.get("fully_evaluated", 0)))
    stage_cols[2].metric("Freigegeben", len(approved))
    stage_cols[3].metric("Datenfehler", int(statistics.get("failed_downloads", 0)))
    st.caption(
        f"Schnellen Vorfilter bestanden: {int(statistics.get('prefilter_passed_total', 0))}. "
        "Alle bestandenen Kandidaten wurden vollständig geprüft."
    )
    st.caption(scan_result.get("market_summary", "Marktumfeld nicht verfügbar."))
    if scan_result.get("forward_documentation"):
        st.caption(str(scan_result["forward_documentation"]))

    tr_tradeable: list[dict] = []
    paper_only: list[dict] = []
    for setup in approved:
        target = (
            tr_tradeable
            if trade_republic_reference(swing_trade_republic_asset(setup)).get("status")
            == TR_STATUS_TRADEABLE
            else paper_only
        )
        target.append(setup)
    st.subheader("Bei Trade Republic handelbare Swing-Trades")
    st.caption(
        f"Scannerqualität gesamt: {len(approved)} freigegebene Signale · "
        f"TR-handelbare Listings: {len(tr_tradeable)} · Nur Paper/unbekannt: {len(paper_only)}"
    )
    if not tr_tradeable:
        st.info("Aktuell ist kein freigegebenes Signal listing-spezifisch als bei Trade Republic handelbar verifiziert.")
    if approved:
        active_ids = {
            str(state["snapshot"].get("signal_id") or "")
            for state in (
                load_swing_user_trade_states(DEFAULT_SWING_USER_DB_PATH)
                if DEFAULT_SWING_USER_DB_PATH.exists()
                else []
            )
        }
        for setup in tr_tradeable:
            render_swing_trade_card(setup, settings, active_ids)
        if paper_only:
            with st.expander("Nur Paper / nicht bei Trade Republic handelbar", expanded=False):
                st.caption(
                    "Diese Signale bleiben vollständig in Forward-Test, Qualitätsmessung und Lernbestand. "
                    "Sie werden nicht als ausführbare Nutzertrades angeboten."
                )
                for setup in paper_only:
                    render_swing_trade_card(setup, settings, active_ids, paper_only=True)
    else:
        st.success("Aktuell kein hochwertiges Scanner-Signal vorhanden.")

    with st.expander("Erweiterte Einblicke und Datenqualität", expanded=False):
        cluster_audit = dict(scan_result.get("portfolio_cluster_audit") or {})
        if cluster_audit:
            st.markdown("**Gleichzeitige Risiko-Cluster**")
            st.caption(
                "Branchenhäufungen und stark gleichlaufende Kandidaten werden gemessen, aber nicht heimlich abgewertet."
            )
            st.write(
                f"Qualifizierte Kandidaten: {cluster_audit.get('qualified_candidates', 0)} · "
                f"stark korrelierte Paare: {len(cluster_audit.get('high_correlation_pairs') or [])}"
            )
            if cluster_audit.get("concentrated_sectors"):
                st.write(
                    "Branchenhäufungen: "
                    + ", ".join(
                        f"{sector}: {count}"
                        for sector, count in cluster_audit["concentrated_sectors"].items()
                    )
                )
            if cluster_audit.get("high_correlation_pairs"):
                st.dataframe(
                    pd.DataFrame(cluster_audit["high_correlation_pairs"]),
                    use_container_width=True,
                    hide_index=True,
                )
        asset_type_funnel = scan_result.get("asset_type_funnel") or {}
        if asset_type_funnel:
            st.markdown("**Assetklassen-Funnel**")
            funnel_rows = [
                {
                    "Asset-Typ": asset_type,
                    "Universum": values.get("universe_assets", 0),
                    "Geladen": values.get("loaded_assets", 0),
                    "Grobfilter bestanden": values.get("prefilter_passed", 0),
                    "Tief geprüft": values.get("fully_evaluated", 0),
                    "Setup bestanden": values.get("setup_approved", 0),
                    "Freigegeben": values.get("portfolio_released", 0),
                    "Grobfilter-Quote": values.get("prefilter_pass_rate_pct"),
                    "Finalfilter-Quote": values.get("setup_approval_rate_pct"),
                }
                for asset_type, values in asset_type_funnel.items()
                if int(values.get("universe_assets") or 0) > 0
            ]
            st.dataframe(pd.DataFrame(funnel_rows), use_container_width=True, hide_index=True)
            bias_audit = scan_result.get("asset_type_bias_audit") or {}
            if bias_audit:
                st.caption(str(bias_audit.get("observation") or ""))
                contributions = list(bias_audit.get("filter_contributions") or [])
                if contributions:
                    st.markdown("**Rechnerische Ursachen der ETF-/Aktien-Grobfilterdifferenz**")
                    st.caption(
                        "Positive Prozentpunkte bedeuten: Dieser Filter lehnt Aktien im aktuellen Lauf häufiger ab. "
                        "Das ist eine Messung, keine Zielquote und keine automatische Gewichtungsänderung."
                    )
                    st.dataframe(pd.DataFrame(contributions), use_container_width=True, hide_index=True)
                final_rows = [
                    {
                        "Asset-Typ": asset_type,
                        "Finalfilter": filter_code,
                        "Auslösungen": count,
                    }
                    for asset_type, values in asset_type_funnel.items()
                    for filter_code, count in (values.get("final_rejection_filters") or {}).items()
                    if int(values.get("universe_assets") or 0) > 0
                ]
                if final_rows:
                    st.markdown("**Finalfilter-Auslösungen nach Assetklasse**")
                    st.caption("Mehrere Filter können beim selben Kandidaten gleichzeitig auslösen.")
                    st.dataframe(pd.DataFrame(final_rows), use_container_width=True, hide_index=True)

        prefilter_rejected = scan_result.get("prefilter_rejected", [])
        all_rejected = [*rejected, *prefilter_rejected]
        st.markdown("**Abgelehnte Kandidaten**")
        if not all_rejected and not errors:
            st.caption("Keine zusätzlichen abgelehnten Kandidaten vorhanden.")
        if all_rejected:
            rejection_rows = [
                {
                    "Ticker": item.get("Ticker"),
                    "Asset": item.get("Asset"),
                    "Stufe": "Tiefenanalyse" if item in rejected else "Vorfilter",
                    "Grund": " | ".join(str(reason) for reason in item.get("Ablehnungsgründe", [])),
                }
                for item in all_rejected
            ]
            st.dataframe(pd.DataFrame(rejection_rows), use_container_width=True, hide_index=True)
        if errors:
            st.markdown("**Datenfehler**")
            for error in errors:
                st.write(f"- {error}")

        st.markdown("**Methodik und zentrale Grenzwerte**")
        thresholds = scan_result.get("thresholds", {})
        st.write(f"- Mindest-Datenqualität: {thresholds.get('min_data_quality', 7.0):.1f}/10")
        st.write(f"- Mindest-CRV: {thresholds.get('min_crv', 2.0):.2f}")
        st.write(f"- Mindest-Kaufsignal: {thresholds.get('min_buy_signal', 5.8):.1f}/10")
        st.write("- Asset-Qualität: nur Diagnose und Dokumentation, kein kurzfristiges Swing-Hard-Gate")
        st.write(f"- Mindest-Confidence: {thresholds.get('min_confidence', 5.8):.1f}/10")
        st.write(
            f"- Belastbare Trefferquote erst ab {thresholds.get('min_historical_cases', 20)} ausgewerteten Fällen"
        )
        st.write("- Nur Long-Swing-Trades: Rücksetzer im Aufwärtstrend oder bestätigter Ausbruch")

        st.markdown("**Interne konservative Risikoregeln (nur lesbar)**")
        policy = scan_result.get("risk_policy", risk_policy_as_dict())
        st.write(f"- Maximales Risiko je Trade: {policy.get('max_risk_pct_per_trade', 0.5):.2f}%")
        st.write(
            f"- Dynamisches Gesamt-Risikobudget aller offenen Trades: "
            f"{policy.get('max_total_open_risk_pct', 2.0):.2f}%"
        )
        st.write("- Keine feste Anzahl offener Trades; Risiko und Kapitalbindung bestimmen die Grenze")
        st.write(f"- Maximale Gesamtbelastung: {policy.get('max_total_exposure_pct', 50.0):.1f}%")
        st.write(f"- Maximale Einzelposition: {policy.get('max_position_exposure_pct', 20.0):.1f}%")
        st.write("- Stop-Abstand maximal: Aktien 8%, ETFs 7%, Krypto 12%")

        st.markdown("**Paper-Trading-Statistik**")
        statistics = paper_trade_statistics(load_trade_history())
        st.write(
            f"Signale: {statistics['signals']} · ausgewertet: {statistics['evaluated']} · "
            f"abgelaufen: {statistics['expired']}"
        )
        if statistics["hit_rate_pct"] is None or statistics["evaluated"] < DEFAULT_SWING_THRESHOLDS.min_historical_cases:
            st.info("Trefferwahrscheinlichkeit noch nicht belastbar.")
        else:
            st.write(f"Trefferquote: {statistics['hit_rate_pct']:.1f} %")
        if statistics["expected_value_pct"] is not None:
            st.write(f"Durchschnittlicher Ergebniswert: {statistics['expected_value_pct']:.2f} %")
        if statistics["profit_factor"] is not None:
            st.write(f"Profitfaktor: {statistics['profit_factor']:.2f}")
        if statistics["max_drawdown_pct"] is not None:
            st.write(f"Maximaler kumulierter Drawdown: {statistics['max_drawdown_pct']:.2f} %")

        if DEFAULT_SWING_FORWARD_DB_PATH.exists():
            st.markdown("**Unveränderbarer Swing-Forward-Test**")
            forward_audit = swing_forward_store_audit(DEFAULT_SWING_FORWARD_DB_PATH)
            forward_signals = load_swing_forward_signals(DEFAULT_SWING_FORWARD_DB_PATH)
            forward_scans = load_swing_forward_scans(DEFAULT_SWING_FORWARD_DB_PATH)
            rejection_controls = load_swing_rejection_controls(DEFAULT_SWING_FORWARD_DB_PATH)
            user_signal_ids = {
                str((state.get("snapshot") or {}).get("signal_id") or "")
                for state in (
                    load_swing_user_trade_states(DEFAULT_SWING_USER_DB_PATH)
                    if DEFAULT_SWING_USER_DB_PATH.exists()
                    else []
                )
            }
            user_signal_ids.discard("")
            tr_forward_references = swing_forward_trade_republic_references(
                forward_signals,
                settings,
            )
            forward_stats = swing_forward_statistics(
                forward_signals,
                user_signal_ids=user_signal_ids,
                tr_references=tr_forward_references,
            )
            learning_readiness = swing_learning_readiness(forward_signals)
            asset_type_forward_comparison = swing_forward_asset_type_comparison(
                forward_signals,
                strategy_versions={SWING_STRATEGY_VERSION},
            )
            st.write(
                f"Echte Scans: {forward_audit['scans']} · Signale: {forward_stats['signals']} · "
                f"Paper-Einstiege: {forward_stats['paper_entries']} · eindeutig ausgewertet: {forward_stats['evaluated']}"
            )
            st.write(
                f"Verpasst: {forward_stats['missed']} · vor Einstieg ungültig: "
                f"{forward_stats['invalidated_before_entry']} · ohne Einstieg abgelaufen: "
                f"{forward_stats['expired_without_entry']} · unklare Reihenfolge: {forward_stats['ambiguous']}"
            )
            counterfactual = forward_stats["counterfactual_controls"]
            rejection_control_stats = swing_rejection_control_statistics(rejection_controls)
            st.write(
                f"Getrennte Nachkontrollen verpasster/ungültiger Signale: {counterfactual['cases']} "
                "gereifte Horizonte."
            )
            st.caption(
                "Diese Nachkontrollen zeigen nur, was nach einer korrekten Ablehnung geschah. "
                "Sie sind keine Trades und verändern weder Trefferquote noch Gewinn-/Verluststatistik."
            )
            st.write(
                f"Reproduzierbare Tiefenanalyse-Ablehnungsstichprobe: "
                f"{rejection_control_stats['controls']} Kandidaten, "
                f"{rejection_control_stats['outcomes']} gereifte Kontrollhorizonte."
            )
            if rejection_control_stats["rows"]:
                st.dataframe(
                    pd.DataFrame(rejection_control_stats["rows"]),
                    use_container_width=True,
                    hide_index=True,
                )
            split_cols = st.columns(3)
            split_cols[0].metric(
                "Scannerqualität gesamt",
                int(forward_stats["scanner_quality_total"]["signals"]),
            )
            split_cols[1].metric(
                "TR-handelbare Listings",
                int(forward_stats["tr_tradeable_listings"]["signals"]),
            )
            split_cols[2].metric(
                "TR-ausführbare Pläne",
                int(forward_stats["tr_executable_trades"]["signals"]),
            )
            st.caption(
                "Gesamtqualität wird über alle objektiven Paper-/Forward-Signale gemessen. "
                "TR-Ausführbarkeit verlangt zusätzlich verifiziertes Listing, frischen TR-Preis und vollständigen TR-Plan."
            )
            st.write(
                f"Nutzerportfolio freigegeben: {forward_stats['portfolio_released']['signals']} · "
                f"Shadow-Signale trotz fachlicher Scannerfreigabe: "
                f"{forward_stats['shadow_strategy_signals']['signals']}"
            )
            st.caption(
                f"Lernfreigabe: {learning_readiness['evaluated']}/{learning_readiness['minimum_evaluated']} "
                f"eindeutige Ergebnisse und {learning_readiness['observation_days']} Tage Beobachtungsdauer. "
                "Historische Walk-Forward-Fälle zählen niemals als echte Forward-Fälle."
            )
            if forward_stats["evaluated"] < DEFAULT_SWING_THRESHOLDS.min_historical_cases:
                st.info("Trefferwahrscheinlichkeit noch nicht belastbar.")
            else:
                st.write(f"Eindeutige Trefferquote: {forward_stats['hit_rate_pct']:.1f} %")
            st.markdown("**ETF-/Aktien-Vergleich der neutralisierten Strategieversion**")
            st.caption(asset_type_forward_comparison["message"])
            st.dataframe(
                pd.DataFrame(asset_type_forward_comparison["rows"]),
                use_container_width=True,
                hide_index=True,
            )
            if forward_stats["archive_rows"]:
                archive_rows = forward_stats["archive_rows"]
                archive_search = st.text_input(
                    "Archiv durchsuchen (Asset, Ticker, ISIN oder Signal-ID)",
                    key="swing_archive_search",
                )
                filter_columns = st.columns(3)
                selected_statuses = set(
                    filter_columns[0].multiselect(
                        "Archivstatus",
                        sorted({str(row["Status"]) for row in archive_rows}),
                        key="swing_archive_status_filter",
                    )
                )
                selected_setups = set(
                    filter_columns[1].multiselect(
                        "Setup",
                        sorted({str(row["Setup"]) for row in archive_rows}),
                        key="swing_archive_setup_filter",
                    )
                )
                selected_regions = set(
                    filter_columns[2].multiselect(
                        "Region",
                        sorted({str(row["Region"]) for row in archive_rows}),
                        key="swing_archive_region_filter",
                    )
                )
                second_filter_columns = st.columns(3)
                selected_asset_types = set(
                    second_filter_columns[0].multiselect(
                        "Asset-Typ",
                        sorted({str(row["Asset-Typ"]) for row in archive_rows}),
                        key="swing_archive_asset_type_filter",
                    )
                )
                selected_quality = set(
                    second_filter_columns[1].multiselect(
                        "Datenqualität",
                        sorted({str(row["Datenqualität"]) for row in archive_rows}),
                        key="swing_archive_quality_filter",
                    )
                )
                selected_fx = set(
                    second_filter_columns[2].multiselect(
                        "Historischer FX",
                        sorted({str(row["Historischer FX"]) for row in archive_rows}),
                        key="swing_archive_fx_filter",
                    )
                )
                third_filter_columns = st.columns(3)
                selected_entry_methods = set(
                    third_filter_columns[0].multiselect(
                        "Einstiegsmethode",
                        sorted({str(row["Einstiegsmethode"]) for row in archive_rows}),
                        key="swing_archive_entry_method_filter",
                    )
                )
                selected_sources = set(
                    third_filter_columns[1].multiselect(
                        "Quellentyp",
                        sorted({str(row["Quelle"]) for row in archive_rows}),
                        key="swing_archive_source_filter",
                    )
                )
                selected_strategy_versions = set(
                    third_filter_columns[2].multiselect(
                        "Strategieversion",
                        sorted({str(row["Strategieversion"]) for row in archive_rows}),
                        key="swing_archive_strategy_version_filter",
                    )
                )
                fourth_filter_columns = st.columns(2)
                selected_user_trade_states = set(
                    fourth_filter_columns[0].multiselect(
                        "Nutzertrade dokumentiert",
                        sorted({str(row["Nutzertrade"]) for row in archive_rows}),
                        key="swing_archive_user_trade_filter",
                    )
                )
                selected_result_states = set(
                    fourth_filter_columns[1].multiselect(
                        "Paper-Ergebnis",
                        ["Gewinn", "Verlust/Null", "Noch offen/nicht wertbar"],
                        key="swing_archive_result_filter",
                    )
                )
                evidence_filter_columns = st.columns(3)
                selected_market_phases = set(
                    evidence_filter_columns[0].multiselect(
                        "Marktphase",
                        sorted({str(row["Marktphase"]) for row in archive_rows}),
                        key="swing_archive_market_phase_filter",
                    )
                )
                selected_volatility_regimes = set(
                    evidence_filter_columns[1].multiselect(
                        "Volatilitätsregime",
                        sorted({str(row["Volatilitätsregime"]) for row in archive_rows}),
                        key="swing_archive_volatility_regime_filter",
                    )
                )
                selected_evidence_kinds = set(
                    evidence_filter_columns[2].multiselect(
                        "Evidenzart",
                        sorted({str(row["Evidenzart"]) for row in archive_rows}),
                        key="swing_archive_evidence_kind_filter",
                    )
                )
                signal_days = sorted(
                    {
                        pd.Timestamp(row["Signalzeit"]).date()
                        for row in archive_rows
                        if row.get("Signalzeit")
                    }
                )
                date_filter_columns = st.columns(2)
                selected_signal_from = date_filter_columns[0].date_input(
                    "Signal von",
                    value=signal_days[0],
                    min_value=signal_days[0],
                    max_value=signal_days[-1],
                    key="swing_archive_signal_from",
                )
                selected_signal_to = date_filter_columns[1].date_input(
                    "Signal bis",
                    value=signal_days[-1],
                    min_value=signal_days[0],
                    max_value=signal_days[-1],
                    key="swing_archive_signal_to",
                )
                filtered_rows = filter_swing_forward_archive_rows(
                    archive_rows,
                    statuses=selected_statuses,
                    setups=selected_setups,
                    asset_types=selected_asset_types,
                    regions=selected_regions,
                    market_phases=selected_market_phases,
                    volatility_regimes=selected_volatility_regimes,
                    evidence_kinds=selected_evidence_kinds,
                    data_qualities=selected_quality,
                    fx_states=selected_fx,
                    strategy_versions=selected_strategy_versions,
                    sources=selected_sources,
                    user_trade_states=selected_user_trade_states,
                    entry_methods=selected_entry_methods,
                    result_states=selected_result_states,
                    search=archive_search,
                    signal_from=selected_signal_from,
                    signal_to=selected_signal_to,
                )
                st.caption(f"{len(filtered_rows)} von {len(archive_rows)} Archivfällen sichtbar.")
                st.dataframe(
                    pd.DataFrame(filtered_rows),
                    use_container_width=True,
                    hide_index=True,
                )
                if filtered_rows:
                    labels = {
                        f"{row['Ticker']} · {row['Setup']} · {row['Signalzeit']} · {row['Signal-ID'][:8]}": row["Signal-ID"]
                        for row in filtered_rows
                    }
                    selected_label = st.selectbox(
                        "Archivfall im Detail",
                        list(labels),
                        key="swing_archive_detail_selection",
                    )
                    selected_signal = next(
                        signal for signal in forward_signals if signal["signal_id"] == labels[selected_label]
                    )
                    detail_snapshot = dict(selected_signal.get("snapshot") or {})
                    detail_events = list(selected_signal.get("events") or [])
                    st.markdown("**Unveränderbarer Systemplan**")
                    st.json(detail_snapshot.get("order_plan") or {}, expanded=False)
                    st.markdown("**Append-only Ereignisverlauf**")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Zeit": event.get("occurred_at"),
                                    "Ereignis": event.get("event_type"),
                                    "Datenqualität": (event.get("payload") or {}).get("data_quality"),
                                    "Grund": (event.get("payload") or {}).get("reason"),
                                }
                                for event in detail_events
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                if forward_stats["segments"]:
                    st.markdown("**Segmentierte Messwerte**")
                    st.dataframe(
                        pd.DataFrame(forward_stats["segments"]),
                        use_container_width=True,
                        hide_index=True,
                    )
            failure_rows = swing_asset_failure_rows(forward_scans)
            if failure_rows:
                st.markdown("**Scanübergreifende technische Asset-Fehler**")
                st.caption(
                    "Wiederkehrende Fehler werden sichtbar gesammelt. Ein Ticker wird daraus niemals automatisch gelöscht."
                )
                st.dataframe(
                    pd.DataFrame(failure_rows),
                    use_container_width=True,
                    hide_index=True,
                )


POSITIVE_WORDS = {
    "beat", "beats", "growth", "record", "upgrade", "bullish", "surge", "rally", "profit",
    "strong", "positive", "buy", "outperform", "erholung", "wachstum", "gewinn", "stark",
}
NEGATIVE_WORDS = {
    "miss", "cuts", "cut", "downgrade", "bearish", "fall", "falls", "drop", "risk", "loss",
    "weak", "lawsuit", "probe", "sell", "underperform", "crash", "verlust", "schwach", "risiko",
}
GEOPOLITICAL_RISK_TERMS = {
    "war", "conflict", "invasion", "missile", "sanction", "sanctions", "tariff", "tariffs",
    "trade war", "export control", "export controls", "blockade", "military", "geopolitical",
    "geopolitics", "taiwan", "red sea", "supply disruption", "oil shock", "opec", "russia",
    "ukraine", "iran", "israel", "krieg", "konflikt", "sanktion", "sanktionen", "zoll",
    "zölle", "exportkontrolle", "blockade", "militär", "geopolitik",
}
GEOPOLITICAL_RELIEF_TERMS = {
    "ceasefire", "truce", "peace", "deal", "agreement", "diplomacy", "de-escalation",
    "deescalation", "waiver", "tariff relief", "waffenruhe", "frieden", "abkommen",
    "diplomatie", "deeskalation", "zollpause",
}


@st.cache_data(ttl=30 * 60)
def load_news_items(symbol: str) -> list[dict]:
    try:
        news = yf.Ticker(symbol).news or []
        return news[:8]
    except Exception:
        return []


def news_field(item: dict, *keys: str) -> object:
    current: object = item
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalized_news_item(item: dict, symbol: str) -> dict[str, object]:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    title = (
        item.get("title")
        or news_field(content, "title")
        or news_field(content, "headline")
        or ""
    )
    publisher = (
        item.get("publisher")
        or news_field(item, "provider", "displayName")
        or news_field(content, "provider", "displayName")
        or news_field(content, "publisher")
        or "Daten nicht verfügbar"
    )
    published_at = (
        item.get("providerPublishTime")
        or news_field(content, "pubDate")
        or news_field(content, "displayTime")
        or news_field(content, "providerPublishTime")
    )
    link = item.get("link") or news_field(content, "canonicalUrl", "url") or news_field(content, "clickThroughUrl", "url")
    related = item.get("relatedTickers") or news_field(content, "finance", "stockTickers") or []
    if not isinstance(related, list):
        related = []
    return {
        "title": str(title or "").strip(),
        "publisher": str(publisher or "Daten nicht verfügbar").strip(),
        "published": format_news_date(published_at),
        "link": str(link or "Daten nicht verfügbar").strip(),
        "related": [str(value).upper() for value in related],
        "symbol": symbol.upper(),
    }


def format_news_date(value: object) -> str:
    if value is None or value == "":
        return "Daten nicht verfügbar"
    numeric = value_or_none(value)
    try:
        if numeric is not None:
            return pd.Timestamp.fromtimestamp(float(numeric)).strftime("%Y-%m-%d %H:%M")
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "Daten nicht verfügbar"


def news_sentiment_from_title(title: str) -> tuple[int, str, int, int]:
    lower = title.lower()
    pos = sum(1 for word in POSITIVE_WORDS if word in lower)
    neg = sum(1 for word in NEGATIVE_WORDS if word in lower)
    raw = pos - neg
    if pos > neg:
        tone = "positiv"
    elif neg > pos:
        tone = "negativ"
    else:
        tone = "neutral"
    return raw, tone, pos, neg


def news_relevance(item: dict[str, object]) -> tuple[str, str]:
    title = str(item.get("title") or "")
    related = item.get("related") if isinstance(item.get("related"), list) else []
    symbol = str(item.get("symbol") or "").upper()
    if symbol and symbol in related:
        return "hoch", "Ticker steht in den Yahoo-Related-Tickers."
    if title:
        clean_symbol = symbol.split(".")[0].replace("-", " ")
        if clean_symbol and clean_symbol.lower() in title.lower():
            return "mittel", "Ticker/Asset wird im Titel erwähnt."
        return "mittel", "Titel vorhanden, aber direkter Tickerbezug nicht eindeutig."
    return "niedrig", "Titel oder Tickerbezug fehlen."


def score_news(symbol: str) -> ModuleScore:
    news = load_news_items(symbol)
    if not news:
        return ModuleScore(
            5.0,
            "News-Daten nicht verfügbar oder keine aktuellen Nachrichten über Yahoo Finance gefunden. News wird neutral behandelt.",
            [
                "Datenabdeckung News: 0/4 Felder verfügbar (Quelle, Datum, Titel, Tickerbezug).",
                score_neutrality_detail("News"),
                "Keine News verfügbar.",
            ],
        )

    sentiment_values: list[int] = []
    details: list[str] = []
    normalized_items = [normalized_news_item(item, symbol) for item in news[:5] if isinstance(item, dict)]
    coverage_fields = []
    for normalized in normalized_items:
        coverage_fields.extend(
            [
                ("Quelle", None if normalized["publisher"] == "Daten nicht verfügbar" else normalized["publisher"]),
                ("Datum", None if normalized["published"] == "Daten nicht verfügbar" else normalized["published"]),
                ("Titel", normalized["title"]),
                ("Tickerbezug", normalized["related"]),
            ]
        )
    details.append(data_coverage_detail("News", coverage_fields or [("Quelle", None), ("Datum", None), ("Titel", None), ("Tickerbezug", None)]))
    details.append(score_neutrality_detail("News"))

    low_quality = 0
    for normalized in normalized_items:
        title = str(normalized.get("title") or "").strip()
        if not title:
            low_quality += 1
            continue
        raw_sentiment, tone, pos, neg = news_sentiment_from_title(title)
        sentiment_values.append(raw_sentiment)
        relevance, relevance_reason = news_relevance(normalized)
        if relevance == "niedrig":
            low_quality += 1
        details.append(
            f"{tone}: {title} | Quelle: {normalized['publisher']} | Datum: {normalized['published']} | "
            f"Relevanz: {relevance} ({relevance_reason}) | Sentiment-Qualität: "
            f"{'klar' if pos != neg else 'unklar'} ({pos} positive, {neg} negative Treffer)."
        )

    if not sentiment_values:
        return ModuleScore(5.0, "Nachrichten vorhanden, aber ohne klares Sentiment. News wird neutral behandelt.", details + ["Sentiment-Qualität: Daten nicht verfügbar."])

    avg_sentiment = float(np.mean(sentiment_values))
    score = round(clamp(5 + avg_sentiment * 1.5), 1)
    quality_text = "hoch" if low_quality == 0 else "eingeschränkt" if low_quality < len(sentiment_values) else "niedrig"
    if score >= 6.5:
        summary = "News-Sentiment ist überwiegend positiv."
    elif score <= 4.0:
        summary = "News-Sentiment ist überwiegend negativ."
    else:
        summary = "News-Sentiment ist überwiegend neutral."
    summary = f"{summary} Sentiment-Qualität: {quality_text}; Quelle/Datum/Relevanz werden je Nachricht ausgewiesen."
    return ModuleScore(score, summary, details[:5])


def geopolitical_term_hits(title: str) -> tuple[list[str], list[str]]:
    lower = title.lower()
    risk_hits = sorted(term for term in GEOPOLITICAL_RISK_TERMS if term in lower)
    relief_hits = sorted(term for term in GEOPOLITICAL_RELIEF_TERMS if term in lower)
    return risk_hits, relief_hits


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
    macro_fields = [
        ("Risikoappetit / Nasdaq", data.get("Nasdaq")),
        ("US-Zinsen 10J", data.get("US-Zinsen 10J")),
        ("Dollar-Index", data.get("Dollar-Index")),
        ("Inflations-/Realzinsproxy TIP", data.get("Inflationserwartung Proxy")),
    ]
    details: list[str] = [
        data_coverage_detail("Makro", macro_fields),
        score_neutrality_detail("Makro"),
        "Liquiditätsproxy direkt: Daten nicht verfügbar. Die App nutzt Nasdaq, Dollar und Zinsen nur als indirekte Risikoappetit-/Liquiditätsproxies.",
    ]
    score = 5.0

    nasdaq_change = trend_change(data.get("Nasdaq", pd.DataFrame()))
    if nasdaq_change is not None:
        adjustment = 1.5 if nasdaq_change > 0.08 else 0.7 if nasdaq_change > 0 else -1.0
        score += adjustment
        details.append(f"Risikoappetit / Nasdaq-Trend 3M: {nasdaq_change * 100:+.1f}% ({adjustment:+.1f}).")
    else:
        details.append(data_missing("Risikoappetit / Nasdaq-Trend"))

    rates_change = trend_change(data.get("US-Zinsen 10J", pd.DataFrame()))
    if rates_change is not None:
        adjustment = -1.0 if rates_change > 0.08 else 0.6 if rates_change < -0.08 else 0.0
        score += adjustment
        details.append(f"Zinsdruck / US-Zinsen 10J 3M: {rates_change * 100:+.1f}% ({adjustment:+.1f}).")
    else:
        details.append(data_missing("Zinsdruck / US-Zinsen 10J"))

    dollar_change = trend_change(data.get("Dollar-Index", pd.DataFrame()))
    if dollar_change is not None:
        adjustment = -0.7 if dollar_change > 0.04 else 0.4 if dollar_change < -0.04 else 0.0
        score += adjustment
        details.append(f"Dollar-/Liquiditätsdruck 3M: {dollar_change * 100:+.1f}% ({adjustment:+.1f}).")
    else:
        details.append(data_missing("Dollar-/Liquiditätsdruck"))

    inflation_proxy = trend_change(data.get("Inflationserwartung Proxy", pd.DataFrame()))
    if inflation_proxy is not None:
        adjustment = 0.4 if inflation_proxy > 0 else -0.4
        score += adjustment
        details.append(f"Inflations-/Realzins-Proxy TIP 3M: {inflation_proxy * 100:+.1f}% ({adjustment:+.1f}).")
    else:
        details.append(data_missing("Inflations-/Realzinsproxy TIP"))

    final_score = round(clamp(score), 1)
    if nasdaq_change is None and rates_change is None and dollar_change is None and inflation_proxy is None:
        return ModuleScore(5.0, "Makrodaten konnten nicht geladen werden. Makro wird neutral bewertet.", details + ["Keine Makrodaten verfügbar."])

    if final_score >= 6.5:
        summary = "Makroumfeld ist eher unterstützend."
    elif final_score <= 4.0:
        summary = "Makroumfeld ist belastend."
    else:
        summary = "Makroumfeld ist gemischt."
    return ModuleScore(final_score, summary, details)


def load_external_analysis_context(symbol: str) -> dict[str, object]:
    """Load independent Yahoo research inputs concurrently without changing scores."""
    neutral_macro = ModuleScore(
        5.0,
        "Makrodaten konnten nicht geladen werden. Makro wird neutral bewertet.",
        ["Keine Makrodaten verfügbar."],
    )
    neutral_news = ModuleScore(
        5.0,
        "News-Daten nicht verfügbar. News wird neutral behandelt.",
        ["Keine News verfügbar."],
    )
    defaults: dict[str, object] = {
        "ticker_info": {},
        "macro": neutral_macro,
        "news": neutral_news,
        "commodity_data": {},
        "earnings_dates": pd.DataFrame(),
    }
    tasks: dict[str, Callable[[], object]] = {
        "ticker_info": lambda: load_ticker_info(symbol),
        "macro": score_macro,
        "news": lambda: score_news(symbol),
        "commodity_data": load_commodity_prices,
        "earnings_dates": lambda: load_earnings_dates(symbol),
    }
    results = dict(defaults)
    errors: list[str] = []
    script_context = get_script_run_ctx(suppress_warning=True)
    with ThreadPoolExecutor(
        max_workers=len(tasks),
        thread_name_prefix="analysis-data",
        initializer=add_script_run_ctx,
        initargs=(None, script_context),
    ) as executor:
        futures = {name: executor.submit(task) for name, task in tasks.items()}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:
                errors.append(f"{name}: {exc}")
    results["errors"] = errors
    return results


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


def research_geopolitical_context(symbol: str, profile: AssetProfile) -> ResearchModule:
    news = load_news_items(symbol)
    coverage_fields: list[tuple[str, object]] = []
    details: list[str] = [
        score_neutrality_detail("Geopolitik"),
        "Datenquelle: Yahoo-Finance-News-Titel. Es werden keine geopolitischen Ereignisse außerhalb der verfügbaren News erfunden.",
    ]
    if not news:
        details.insert(0, data_coverage_detail("Geopolitik", [("News-Titel", None), ("Quelle", None), ("Datum", None), ("Tickerbezug", None)]))
        details.append("Geopolitische Spezialdaten: Daten nicht verfügbar.")
        details.append("Praktische Bedeutung: fehlende Treffer sind keine Entwarnung, sondern eine eingeschränkte Datenlage.")
        beginner = "Geopolitik meint Risiken durch Krieg, Sanktionen, Zölle oder Lieferketten. Wenn keine belastbaren Daten vorliegen, sollte die App daraus keine Sicherheit ableiten."
        return ResearchModule("Geopolitik-Score", None, "Geopolitische Daten nicht verfügbar.", details, beginner)

    normalized_items = [normalized_news_item(item, symbol) for item in news[:8] if isinstance(item, dict)]
    risk_titles: list[str] = []
    relief_titles: list[str] = []
    risk_hit_count = 0
    relief_hit_count = 0

    for normalized in normalized_items:
        title = str(normalized.get("title") or "").strip()
        coverage_fields.extend(
            [
                ("News-Titel", title),
                ("Quelle", None if normalized["publisher"] == "Daten nicht verfügbar" else normalized["publisher"]),
                ("Datum", None if normalized["published"] == "Daten nicht verfügbar" else normalized["published"]),
                ("Tickerbezug", normalized["related"]),
            ]
        )
        if not title:
            continue
        risk_hits, relief_hits = geopolitical_term_hits(title)
        if risk_hits:
            risk_hit_count += len(risk_hits)
            risk_titles.append(f"{title} | Risikotreffer: {', '.join(risk_hits[:4])}.")
        if relief_hits:
            relief_hit_count += len(relief_hits)
            relief_titles.append(f"{title} | Entlastungstreffer: {', '.join(relief_hits[:4])}.")

    details.insert(0, data_coverage_detail("Geopolitik", coverage_fields or [("News-Titel", None), ("Quelle", None), ("Datum", None), ("Tickerbezug", None)]))
    details.append(f"Geopolitische Risikotreffer: {risk_hit_count}.")
    details.append(f"Geopolitische Entlastungstreffer: {relief_hit_count}.")

    if risk_titles:
        details.extend(risk_titles[:3])
    else:
        details.append("Keine geopolitischen Risikobegriffe in den verfügbaren Yahoo-News-Titeln gefunden. Das ist keine vollständige Entwarnung.")
    if relief_titles:
        details.extend(relief_titles[:2])
    else:
        details.append("Keine geopolitischen Entlastungsbegriffe in den verfügbaren Yahoo-News-Titeln gefunden.")

    asset_effects = {
        "Aktie": "Für Aktien zählen besonders Lieferketten, Absatzregionen, Sanktionen, Zölle und Exportkontrollen.",
        "ETF": "Für ETFs hängt die Wirkung von Region, Sektor und Indexgewichtung ab; breite ETFs sind meist indirekter betroffen.",
        "Krypto": "Für Krypto wirkt Geopolitik meist über Risikoappetit, Dollar, Kapitalverkehr und Regulierung.",
        "Derivat / unbekannt": "Bei unbekannten Assets ist die geopolitische Wirkung schwer belastbar; Risikobegrenzung ist wichtiger.",
    }
    details.append("Asset-Typ-Wirkung: " + asset_effects.get(profile.asset_type, asset_effects["Derivat / unbekannt"]))

    score = clamp(6.0 - min(risk_hit_count, 5) * 0.9 + min(relief_hit_count, 3) * 0.5)
    final_score = round(score, 1)
    if risk_hit_count >= 3:
        summary = f"Geopolitischer Gegenwind in verfügbaren News erhöht. Score {final_score}/10."
    elif risk_hit_count > 0:
        summary = f"Einzelne geopolitische Risikohinweise in verfügbaren News. Score {final_score}/10."
    else:
        summary = f"Keine geopolitischen Risikotreffer in verfügbaren News-Titeln. Score {final_score}/10 bei begrenzter Datenlage."
    beginner = "Der Geopolitik-Score prüft, ob aktuelle News Hinweise auf Krieg, Sanktionen, Zölle oder Lieferkettenstress enthalten. Praktisch heißt das: niedrige Werte erhöhen Vorsicht; fehlende Treffer sind keine Garantie."
    return ResearchModule("Geopolitik-Score", final_score, summary, details, beginner)


def research_commodity_context(
    profile: AssetProfile,
    commodity_data: dict[str, pd.DataFrame] | None = None,
) -> ResearchModule:
    if commodity_data is None:
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


def crypto_halving_cycle_context(today: pd.Timestamp | None = None) -> dict:
    reference_today = (today or pd.Timestamp.today()).normalize()
    last_halving = pd.Timestamp("2024-04-20")
    next_halving_estimate = pd.Timestamp("2028-04-20")
    days_since_halving = int((reference_today - last_halving).days)
    days_to_next_halving = int((next_halving_estimate - reference_today).days)
    cycle_length = max(int((next_halving_estimate - last_halving).days), 1)
    progress = clamp(days_since_halving / cycle_length, 0.0, 1.0)

    if days_since_halving < 0:
        phase = "vor der aktuellen Halving-Referenz"
        score = 5.0
        practical_meaning = "Das bekannte Halving-Fenster liefert noch keinen positiven oder negativen Zyklusimpuls."
    elif days_since_halving < 180:
        phase = "frühe Nach-Halving-Phase"
        score = 6.5
        practical_meaning = "Für Anleger bedeutet das: Zyklus-Rückenwind ist möglich, aber Kursbestätigung und Liquidität sind wichtiger als das Datum allein."
    elif days_since_halving < 550:
        phase = "mittlere Zyklusphase"
        score = 7.0
        practical_meaning = "Für Anleger bedeutet das: Der Zykluskontext ist konstruktiv, Nachkäufe sollten trotzdem an Trend, Volumen und Unterstützungen gekoppelt bleiben."
    elif days_since_halving < 900:
        phase = "späte Zyklusphase mit erhöhtem Rückschlagsrisiko"
        score = 5.0
        practical_meaning = "Für Anleger bedeutet das: Nicht aggressiv nur wegen des Halving-Zyklus kaufen; Rücksetzer und Bestätigung werden wichtiger."
    else:
        phase = "späte/Übergangsphase vor dem nächsten Halving"
        score = 4.5
        practical_meaning = "Für Anleger bedeutet das: Der Zyklus spricht eher für vorsichtige Positionsgrößen und klare Risikomarken."

    return {
        "last_halving": last_halving,
        "next_halving_estimate": next_halving_estimate,
        "days_since_halving": days_since_halving,
        "days_to_next_halving": days_to_next_halving,
        "progress_pct": round(progress * 100, 1),
        "phase": phase,
        "score": score,
        "practical_meaning": practical_meaning,
    }


def research_crypto_cycle(symbol: str, profile: AssetProfile, df: pd.DataFrame) -> ResearchModule:
    if profile.asset_type != "Krypto":
        return ResearchModule("Krypto-Zyklus", None, "Nicht relevant für diesen Asset-Typ.", ["Asset ist nicht als Krypto erkannt."], "Dieses Modul gilt nur für Kryptowährungen.")

    latest = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    volatility = value_or_none(latest.get("Volatility"))
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    close = value_or_none(latest.get("Close"))
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    cycle_context = crypto_halving_cycle_context()
    days_since_halving = cycle_context["days_since_halving"]
    days_to_next_halving = cycle_context["days_to_next_halving"]
    phase = str(cycle_context["phase"])
    cycle_score = float(cycle_context["score"])

    details = [
        data_coverage_detail(
            "Krypto-Zyklus",
            [
                ("Halving-Zeitfenster", days_since_halving),
                ("Zyklusfortschritt", cycle_context["progress_pct"]),
                ("Volatilität", volatility),
                ("Volumenvergleich", volume if volume is not None and volume_avg is not None else None),
                ("Trendstruktur", close if close is not None and sma_50 is not None and sma_200 is not None else None),
                ("Fear & Greed", None),
                ("ETF-Flows", None),
                ("On-Chain-Daten", None),
                ("Orderbuch-/Spread-Daten", None),
                ("Stablecoin-Liquidität", None),
            ],
        ),
        score_neutrality_detail("Krypto-Zyklus"),
        f"Ticker: {symbol}.",
        f"Letztes Bitcoin-Halving: 20.04.2024; Tage seitdem: {days_since_halving}.",
        f"Nächstes Halving grob geschätzt um 2028; Tage bis zur Schätzung: {days_to_next_halving}.",
        f"Zyklusfortschritt bis zur nächsten groben Halving-Schätzung: {cycle_context['progress_pct']:.1f}%.",
        f"Zyklusphase: {phase} -> {cycle_score:.1f}/10.",
        f"Praktische Bedeutung: {cycle_context['practical_meaning']}",
        "Unsicherheit: Der Halving-Zyklus ist ein Kontextsignal, kein Kaufsignal. Trend, Liquidität, Volatilität, Makro und Risikomarken können wichtiger sein.",
        "ETF-Flows: Daten nicht verfügbar.",
        "Fear & Greed: Daten nicht verfügbar.",
        "On-Chain-Daten: Daten nicht verfügbar.",
        "Orderbuch-, Spread-, Börsentiefe- und Stablecoin-Liquiditätsdaten: Daten nicht verfügbar.",
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

    if close is not None and sma_50 is not None and sma_200 is not None:
        if close > sma_50 > sma_200:
            market_structure_score = 7.5
            structure = "Trendstruktur konstruktiv: Kurs über 50er- und 200er-Durchschnitt."
        elif close < sma_50 < sma_200:
            market_structure_score = 3.5
            structure = "Trendstruktur schwach: Kurs unter 50er- und 200er-Durchschnitt."
        else:
            market_structure_score = 5.5
            structure = "Trendstruktur gemischt: Durchschnitte liefern kein klares Krypto-Struktursignal."
        points.append(market_structure_score)
        details.append(f"{structure} -> {market_structure_score:.1f}/10.")
    else:
        details.append(data_missing("Krypto-Marktstruktur / 50er- und 200er-Durchschnitt"))

    score = round(float(np.mean(points)), 1)
    summary = f"Krypto-Zyklus {score}/10. {phase}."
    beginner = "Krypto-Zyklen können nach Bitcoin-Halvings Muster zeigen, sind aber keine Garantie. Praktisch heißt das: Der Zyklus kann Rückenwind oder Vorsicht anzeigen, ersetzt aber keine Prüfung von Trend, Volumen, Volatilität und Unterstützungen. Dieses Modul trennt verfügbare Marktdaten von fehlenden Spezialdaten wie ETF-Flows, Fear & Greed, On-Chain, Orderbuch und Stablecoin-Liquidität."
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


def volatility_risk_score(volatility: float, asset_type: str) -> tuple[float, str]:
    thresholds = {
        "ETF": (0.18, 0.30, 0.50),
        "Aktie": (0.25, 0.45, 0.75),
        "Krypto": (0.45, 0.75, 1.10),
        "Derivat / unbekannt": (0.20, 0.35, 0.60),
    }.get(asset_type, (0.20, 0.35, 0.60))
    low, medium, high = thresholds
    if volatility <= low:
        return 8.0, "ruhig für diesen Asset-Typ"
    if volatility <= medium:
        return 6.0, "normal bis moderat für diesen Asset-Typ"
    if volatility <= high:
        return 4.0, "hoch für diesen Asset-Typ"
    return 2.5, "sehr hoch für diesen Asset-Typ"


def research_risk_score(df: pd.DataFrame, risk_reward: RiskReward, profile: AssetProfile) -> ResearchModule:
    latest = df.iloc[-1]
    volatility = value_or_none(latest.get("Volatility"))
    points: list[float] = []
    details: list[str] = [
        data_coverage_detail(
            "Risiko",
            [
                ("Volatilität", volatility),
                ("Risiko bis Unterstützung", risk_reward.risk_pct),
                ("Potenzial bis Widerstand", risk_reward.reward_pct),
                ("CRV", risk_reward.ratio),
            ],
        ),
        score_neutrality_detail("Risiko"),
    ]
    if volatility is not None:
        vol_score, vol_label = volatility_risk_score(volatility, profile.asset_type)
        points.append(vol_score)
        details.append(f"Volatilität {volatility * 100:.1f}% ({vol_label}) -> {vol_score:.1f}/10.")
    else:
        details.append(data_missing("Volatilität"))
    if risk_reward.risk_pct is not None:
        details.append(f"Risiko bis nächste Unterstützung: {percent_text(risk_reward.risk_pct)}.")
    else:
        details.append(data_missing("Risiko bis Unterstützung"))
    if risk_reward.reward_pct is not None:
        details.append(f"Potenzial bis nächster Widerstand: {percent_text(risk_reward.reward_pct)}.")
    else:
        details.append(data_missing("Potenzial bis Widerstand"))
    if risk_reward.ratio is not None:
        if risk_reward.ratio >= 2:
            crv_text = "attraktiv, weil das Potenzial mindestens doppelt so hoch ist wie das Risiko"
        elif risk_reward.ratio >= 1:
            crv_text = "brauchbar, aber nicht besonders komfortabel"
        else:
            crv_text = "schwach, weil das Potenzial das Risiko nicht klar übersteigt"
        details.append(f"CRV-Einordnung: {risk_reward.ratio:.2f} -> {crv_text}.")
    else:
        details.append(data_missing("CRV-Einordnung"))
    points.append(risk_reward.score)
    details.append(f"CRV-Score: {risk_reward.score:.1f}/10. {risk_reward.summary}")
    score = score_from_optional(points)
    beginner = "Der Risiko-Score bewertet Schwankungen, Abstand zur Unterstützung und Potenzial bis zum Widerstand. Hoch heißt: Das Risiko ist für diesen Asset-Typ besser planbar."
    return ResearchModule("Risiko-Score", score, f"Risiko {score}/10. {risk_reward.summary}", details, beginner)


def research_liquidity_score(df: pd.DataFrame, info: dict, profile: AssetProfile) -> ResearchModule:
    latest = df.iloc[-1]
    volume = value_or_none(latest.get("Volume"))
    volume_avg = value_or_none(latest.get("Volume_SMA_20"))
    avg_volume = value_or_none(info.get("averageVolume"))
    avg_volume_10d = value_or_none(info.get("averageVolume10days"))
    points: list[float] = []
    details: list[str] = [
        data_coverage_detail(
            "Liquidität",
            [
                ("aktuelles Volumen", volume),
                ("20er-Volumenschnitt", volume_avg),
                ("Yahoo-Durchschnittsvolumen", avg_volume),
                ("Yahoo-10T-Durchschnittsvolumen", avg_volume_10d),
            ],
        ),
        score_neutrality_detail("Liquidität"),
    ]
    if volume is not None and volume_avg is not None and volume_avg > 0:
        ratio = volume / volume_avg
        score = 8.0 if ratio >= 1.0 else 6.0 if ratio >= 0.5 else 3.5
        points.append(score)
        if ratio >= 1.0:
            ratio_text = "aktueller Handel ist mindestens durchschnittlich aktiv"
        elif ratio >= 0.5:
            ratio_text = "Handel ist unterdurchschnittlich, aber nicht extrem dünn"
        else:
            ratio_text = "Handel ist dünn; Signale sind weniger belastbar"
        details.append(f"Aktuelles Volumen zu 20er-Schnitt: {ratio:.2f}x -> {score:.1f}/10; {ratio_text}.")
    else:
        details.append(data_missing("aktuelles Volumen"))
    if avg_volume is not None:
        if profile.asset_type == "ETF":
            score = 8.0 if avg_volume >= 500_000 else 6.0 if avg_volume >= 50_000 else 4.0
        elif profile.asset_type == "Krypto":
            score = 8.0 if avg_volume >= 1_000_000 else 6.0 if avg_volume >= 100_000 else 4.0
        else:
            score = 8.0 if avg_volume >= 1_000_000 else 6.0 if avg_volume >= 100_000 else 4.0
        points.append(score)
        details.append(f"Durchschnittsvolumen Yahoo: {format_currency(avg_volume)} Stück/Einheiten -> {score:.1f}/10 für Asset-Typ {profile.asset_type}.")
    else:
        details.append(data_missing("Yahoo-Durchschnittsvolumen"))
    if avg_volume_10d is not None:
        details.append(f"10T-Durchschnittsvolumen Yahoo: {format_currency(avg_volume_10d)} Stück/Einheiten.")
    else:
        details.append(data_missing("Yahoo-10T-Durchschnittsvolumen"))
    if profile.asset_type == "Krypto":
        details.append("Orderbuch-, Spread-, Börsentiefe- und Stablecoin-Liquiditätsdaten: Daten nicht verfügbar.")
    else:
        details.append("Bid-Ask-Spread und Orderbuchtiefe: Daten nicht verfügbar.")
    score = score_from_optional(points)
    beginner = "Liquidität zeigt, wie leicht ein Asset typischerweise handelbar ist. Hoch heißt: Volumen spricht eher dafür, dass Signale belastbarer sind; Spread- und Orderbuchdaten fehlen aber weiterhin."
    return ResearchModule("Liquiditäts-Score", score, f"Liquidität {score}/10 aus verfügbaren Volumendaten.", details, beginner)


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


def coverage_value_available(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, pd.DataFrame):
        return not value.empty
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return str(value) not in {"", "Daten nicht verfügbar"}


def data_coverage_detail(module_name: str, fields: list[tuple[str, object]]) -> str:
    available = sum(1 for _, value in fields if coverage_value_available(value))
    labels = ", ".join(label for label, _ in fields)
    return f"Datenabdeckung {module_name}: {available}/{len(fields)} Felder verfügbar ({labels})."


def score_neutrality_detail(module_name: str) -> str:
    return f"Score-Neutralität {module_name}: Fehlende Daten werden nicht geschätzt und nicht als Fakt gewertet."


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
        data_coverage_detail(
            "Analysten-Konsens",
            [
                ("Durchschnittskursziel", target_mean),
                ("höchstes Kursziel", target_high),
                ("niedrigstes Kursziel", target_low),
                ("Anzahl Analystenmeinungen", analyst_count),
                ("Recommendation-Mean", recommendation_mean),
                ("Yahoo-Empfehlung", recommendation_key),
            ],
        ),
        score_neutrality_detail("Analysten-Konsens"),
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


@st.cache_data(ttl=60 * 60)
def load_earnings_dates(symbol: str) -> pd.DataFrame:
    try:
        return safe_dataframe_from_yfinance(yf.Ticker(symbol).get_earnings_dates(limit=8))
    except Exception:
        return pd.DataFrame()


def research_earnings_module(
    symbol: str,
    info: dict,
    profile: AssetProfile,
    earnings_dates: pd.DataFrame | None = None,
) -> ResearchModule:
    if profile.asset_type != "Aktie":
        return ResearchModule(
            "Earnings-Modul",
            None,
            "Daten nicht verfügbar. Earnings-Modul ist nur für Aktien sinnvoll.",
            ["Nächster Quartalsbericht: Daten nicht verfügbar.", "Letzter Quartalsbericht: Daten nicht verfügbar."],
            "Earnings sind Quartalszahlen. Für ETFs und viele Kryptos gibt es keine klassischen Unternehmensgewinne.",
        )

    if earnings_dates is None:
        earnings_dates = load_earnings_dates(symbol)
    details: list[str] = []
    next_report = format_optional_date(info.get("earningsTimestamp") or info.get("earningsTimestampStart"))
    last_report = format_optional_date(info.get("mostRecentQuarter"))
    revenue_estimate = value_or_none(info.get("revenueEstimate"))
    earnings_estimate = value_or_none(info.get("earningsEstimate"))
    details.append(
        data_coverage_detail(
            "Earnings-Modul",
            [
                ("nächster Quartalsbericht", None if next_report == "Daten nicht verfügbar" else next_report),
                ("letzter Quartalsbericht", None if last_report == "Daten nicht verfügbar" else last_report),
                ("Earnings-Kalender", None if earnings_dates.empty else "verfügbar"),
                ("Umsatzschätzung", revenue_estimate),
                ("Gewinnschätzung", earnings_estimate),
            ],
        )
    )
    details.append(score_neutrality_detail("Earnings-Modul"))
    details.append(f"Nächster Quartalsbericht: {next_report}.")
    details.append(f"Letzter Quartalsbericht: {last_report}.")

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
    earnings_date = format_optional_date(info.get("earningsTimestamp") or info.get("earningsTimestampStart"))
    details = [
        data_coverage_detail(
            "Event-Risiko",
            [
                ("Earnings-Termin", None if earnings_date == "Daten nicht verfügbar" else earnings_date),
                ("Makro-Score", macro.score),
                ("Fed-Sitzungen", None),
                ("EZB-Sitzungen", None),
                ("CPI/Inflationsdaten", None),
                ("Arbeitsmarktdaten", None),
                ("ETF-Entscheidungen", None),
            ],
        ),
        score_neutrality_detail("Event-Risiko"),
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
        data_coverage_detail(
            "Institutionelle Daten",
            [
                ("institutionelle Beteiligungen", held_institutions),
                ("Insider-Beteiligungen", held_insiders),
                ("Short Interest Aktien", shares_short),
                ("Short Ratio", short_ratio),
                ("Short Interest vom Float", short_percent_float),
                ("Insiderkäufe", None),
                ("Insiderverkäufe", None),
                ("ETF-Flows", None),
            ],
        ),
        score_neutrality_detail("Institutionelle Daten"),
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
    asset_type: str,
    buy_signal_score: float,
) -> ResearchModule:
    data_sources = available_data_source_count(modules, institutional_modules)
    source_score = 8.0 if data_sources >= 8 else 6.5 if data_sources >= 5 else 4.5 if data_sources >= 3 else 3.0
    phase_score = market_phase_clarity_score(market_phase)
    stability_score = signal_stability_score(df)
    liquidity_score = liquidity.score if liquidity.score is not None else 4.0
    data_quality_score = data_quality.score if data_quality.score is not None else 4.0
    final_score = score_from_optional([data_quality_score, liquidity_score, source_score, phase_score, stability_score])
    historical_stats = similar_setup_statistics(asset_type, market_phase.phase, "Long" if buy_signal_score >= 5 else "Beobachten", buy_signal_score)
    details = [
        f"Datenqualität: {data_quality_score:.1f}/10.",
        f"Liquidität: {liquidity_score:.1f}/10.",
        f"Verfügbare Datenquellen: {data_sources} -> {source_score:.1f}/10.",
        f"Klarheit der Marktphase: {phase_score:.1f}/10.",
        f"Stabilität der Signale: {stability_score:.1f}/10.",
        str(historical_stats["summary"]),
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
    geopolitics: ResearchModule,
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
    if geopolitics.score is None:
        factors.append("Geopolitische Risikodaten sind nicht verfügbar; externe Ereignisse können die Analyse trotzdem widerlegen.")
    elif geopolitics.score <= 4.5:
        factors.append("Erhöhte geopolitische Risikohinweise können positive Markt- oder News-Signale überlagern.")
    if not supports:
        factors.append("Keine klare Unterstützung erkannt; dadurch fehlt eine belastbare Risikomarke.")
    if market_phase_clarity_score(market_phase) < 5:
        factors.append("Marktphase ist nicht klar; Signale können häufiger kippen.")
    while len(factors) < 3:
        factors.append("Neue externe Daten können die Einschätzung verändern.")
    return factors[:5]


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
    chart_history_label: str | None = None,
    analysis_history_label: str | None = None,
    chart_rows: int | None = None,
    external_research: bool = True,
    portfolio_result: PortfolioResult | None = None,
    has_position: bool = False,
    ticker_info: dict | None = None,
    commodity_data: dict[str, pd.DataFrame] | None = None,
    earnings_dates: pd.DataFrame | None = None,
) -> ResearchPack:
    latest = df.iloc[-1]
    close = float(latest["Close"])
    info = ticker_info if ticker_info is not None else load_ticker_info(symbol)
    data_quality = data_quality_check(symbol, asset_profile, asset_identity, df, chart_history_label, analysis_history_label, chart_rows)
    chart = research_chart_score(df, supports, resistances, market_phase)
    momentum = research_momentum_score(df)
    valuation = research_valuation_score(info, asset_profile, df, macro)
    fundamentals = research_fundamental_module(asset_quality, asset_profile)
    future_potential = research_future_potential(info, asset_profile, asset_quality, news)
    market_regime = research_market_regime(df, market_phase, macro)
    macro_impact = research_macro_impact(asset_profile, macro)
    geopolitics = (
        research_geopolitical_context(symbol, asset_profile)
        if external_research
        else ResearchModule(
            "Geopolitischer Kontext",
            None,
            "Im täglichen Hintergrundlauf werden keine massenhaften News-Abfragen durchgeführt.",
            ["Abdeckung: Preis-, Fundamentaldaten- und Makrologik aktiv; asset-spezifische News hier bewusst ausgelassen."],
            "Dieser Kontext bleibt offen, damit fehlende News nicht als positives oder negatives Signal gewertet werden.",
        )
    )
    commodity_context = research_commodity_context(asset_profile, commodity_data)
    bubble_risk = research_bubble_risk(info, df, valuation, momentum, news)
    priced_expectations = research_priced_expectations(info, asset_profile, valuation, momentum, news)
    innovation = research_innovation_context(info, asset_profile, asset_quality, bubble_risk, news)
    crypto_cycle = research_crypto_cycle(symbol, asset_profile, df)
    macro_module = module_from_existing("Makro-Score", macro, "Der Makro-Score bewertet Zinsen, Nasdaq, Dollar und Inflationsumfeld. Hoch heißt: Das Umfeld hilft eher.")
    news_module = module_from_existing("News-Score", news, "Der News-Score bewertet die Nachrichtenstimmung. Hoch heißt: Nachrichten geben eher Rückenwind.")
    risk = research_risk_score(df, risk_reward, asset_profile)
    liquidity = research_liquidity_score(df, info, asset_profile)
    analyst = research_analyst_consensus(info, asset_profile, original_currency, fx_rate, currency_mode)
    earnings = (
        research_earnings_module(symbol, info, asset_profile, earnings_dates)
        if external_research
        else ResearchModule(
            "Earnings-/Event-Kalender",
            None,
            "Im täglichen Hintergrundlauf wird kein separater Earnings-Kalender je Asset abgefragt.",
            ["Abdeckung: allgemeine Ticker-Metadaten vorhanden; zusätzlicher Kalenderabruf bewusst ausgelassen."],
            "Der fehlende Kalender senkt die Datenabdeckung und wird nicht als neutrales Ereignissignal ausgegeben.",
        )
    )
    event_risk = research_event_risk_module(info, asset_profile, macro)
    institutional = research_institutional_data(info, asset_profile)
    expected_value = research_expected_value(close, supports, resistances, buy_signal, asset_quality, risk_reward, market_phase, latest)
    modules = [fundamentals, future_potential, valuation, priced_expectations, bubble_risk, chart, momentum, expected_value, innovation, market_regime, macro_impact, geopolitics, commodity_context, macro_module, news_module, risk, liquidity]
    if asset_profile.asset_type == "Krypto":
        modules.insert(5, crypto_cycle)
    institutional_modules = [analyst, earnings, event_risk, institutional]
    confidence = research_confidence_score(data_quality, liquidity, market_phase, df, modules, institutional_modules, asset_profile.asset_type, buy_signal.score)
    uncertainty_factors = build_uncertainty_factors(data_quality, event_risk, earnings, geopolitics, news, macro, latest, market_phase, supports)
    scenarios = build_scenarios(close, supports, resistances, buy_signal, asset_quality, risk_reward, market_phase, latest, original_currency, fx_rate, currency_mode)
    buy_zones = build_buy_zones(close, supports, resistances, latest, original_currency, fx_rate, currency_mode)
    decision = synthesize_investment_recommendation(
        asset_profile,
        asset_quality,
        future_potential,
        valuation,
        priced_expectations,
        bubble_risk,
        buy_signal,
        expected_value,
        macro,
        market_phase,
        risk_reward,
        confidence,
        data_quality,
        supports,
        resistances,
        df,
        latest,
        original_currency,
        fx_rate,
        currency_mode,
        uncertainty_factors,
        portfolio_result,
        has_position,
        info,
    )
    action = str(decision["Titel"])
    conclusion = build_research_conclusion(action, modules, buy_signal, asset_quality, risk_reward, supports, resistances, latest, original_currency, fx_rate, currency_mode)
    conclusion["Welche Marke ist entscheidend?"] = str(decision["Widerlegungsbedingung"])
    conclusion["Was wäre mein konkreter Plan?"] = (
        f"{decision['Nächste Handlung']} Alternative: {decision['Alternative Handlung']}"
    )
    return ResearchPack(data_quality, modules, institutional_modules, confidence, uncertainty_factors, scenarios, buy_zones, action, decision, conclusion)


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
        "professional_decision": research_pack.decision,
        "signal_snapshot": build_signal_snapshot(latest, risk_reward, research_pack.modules),
        "scenarios": research_pack.scenarios,
        "buy_zones": research_pack.buy_zones,
        "module_scores": [
            {"name": module.name, "score": module.score, "summary": module.summary}
            for module in research_pack.modules
        ],
        "review_after": empty_review_schedule(),
        "note": "Forward-Test speichert nur die Analyse. Keine Kauf- oder Verkaufsautomatisierung.",
    }


def build_decision_record(
    symbol: str,
    asset_identity: dict,
    asset_profile: AssetProfile,
    latest: pd.Series,
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    market_phase: MarketPhase,
    research_pack: ResearchPack,
    decision: str,
    user_note: str,
) -> dict:
    return {
        "created_at": pd.Timestamp.now().isoformat(),
        "symbol": symbol,
        "name": asset_identity.get("name", ""),
        "asset_type": asset_profile.asset_type,
        "price_at_decision": value_or_none(latest.get("Close")),
        "decision": decision,
        "user_note": user_note.strip(),
        "app_action": research_pack.action,
        "professional_decision": research_pack.decision,
        "asset_quality": asset_quality.score,
        "buy_signal": buy_signal.score,
        "confidence": research_pack.confidence.score,
        "market_phase": market_phase.phase,
        "signal_snapshot": build_signal_snapshot(latest, RiskReward(None, None, None, 5.0, "CRV für Nutzerentscheidung nicht separat berechnet."), research_pack.modules),
        "module_scores": [
            {"name": module.name, "score": module.score, "summary": module.summary}
            for module in research_pack.modules
        ],
        "review_after": empty_review_schedule(),
        "note": "Decision Tracking dokumentiert nur eine Nutzerentscheidung. Keine Order, keine Broker-Anbindung.",
    }


def build_prediction_record(
    symbol: str,
    asset_identity: dict,
    asset_profile: AssetProfile,
    latest: pd.Series,
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    research_pack: ResearchPack,
) -> dict:
    return {
        "created_at": pd.Timestamp.now().isoformat(),
        "symbol": symbol,
        "name": asset_identity.get("name", ""),
        "asset_type": asset_profile.asset_type,
        "price_at_prediction": value_or_none(latest.get("Close")),
        "market_phase": market_phase.phase,
        "confidence": research_pack.confidence.score,
        "risk_reward_score": risk_reward.score,
        "risk_reward_ratio": risk_reward.ratio,
        "signal_snapshot": build_signal_snapshot(latest, risk_reward, research_pack.modules),
        "simple_trend_baseline": simple_trend_snapshot(df["Close"].tolist()),
        "module_scores": [
            {"name": module.name, "score": module.score, "summary": module.summary}
            for module in research_pack.modules
        ],
        "professional_decision": research_pack.decision,
        "scenarios": research_pack.scenarios,
        "decisive_mark": research_pack.conclusion.get("Welche Marke ist entscheidend?"),
        "invalidation_or_buy_zones": research_pack.buy_zones,
        "review_after": empty_review_schedule(),
        "note": "Prognose-Tracking speichert nur Szenarien zur späteren Auswertung. Keine Order, keine Broker-Anbindung.",
    }


def forecast_direction_from_signal(buy_signal_score: float) -> str:
    """Map the existing buy-signal score to the documented direction metric."""
    if buy_signal_score >= 5.5:
        return "Steigend"
    if buy_signal_score <= 4.5:
        return "Fallend"
    return "Seitwärts"


def build_background_forecast_snapshot(
    asset: dict,
    run_date: str,
    logic_version: str = FORECAST_LOGIC_VERSION,
) -> dict:
    """Run the existing analysis pipeline without a Streamlit session or mass news calls."""
    symbol = str(asset.get("ticker") or "").strip().upper()
    if not symbol:
        raise ValueError("Asset ohne Ticker im Prognoseuniversum")

    analysis_raw_data = load_price_data(symbol, "max", "1d")
    if analysis_raw_data.empty or "Close" not in analysis_raw_data:
        raise RuntimeError("Keine belastbaren Kursdaten verfügbar")

    df = calculate_indicators(analysis_raw_data, "1d")
    supports = local_levels(df["Low"], "support")
    resistances = local_levels(df["High"], "resistance")
    score_result = calculate_score_v2(df, supports, resistances)
    latest = df.iloc[-1]
    close = float(latest["Close"])
    ticker_info = load_ticker_info(symbol)
    candidate = {
        "name": asset.get("name") or symbol,
        "exchange": ticker_info.get("exchangeName") or ticker_info.get("exchange") or "Daten nicht verfügbar",
    }
    asset_identity = build_asset_identity(symbol, ticker_info, candidate)
    original_currency = asset_identity["currency"]
    fx_rate, _ = get_fx_rate_to_eur(original_currency)
    auto_profile = detect_asset_type(symbol, ticker_info)
    curated_type = str(asset.get("asset_type") or "")
    if auto_profile.asset_type == "Derivat / unbekannt" and curated_type in {"Aktie", "ETF", "Krypto"}:
        asset_profile = override_asset_profile(auto_profile, curated_type)
    else:
        asset_profile = auto_profile

    market_phase = detect_market_phase(df)
    risk_reward = calculate_risk_reward(close, supports, resistances)
    macro = score_macro()
    asset_quality = score_asset_quality_from_info(symbol, asset_profile, df, ticker_info)
    news = ModuleScore(
        5.0,
        "Asset-spezifische News werden im täglichen Massenlauf bewusst nicht abgefragt.",
        ["News-Abdeckung: ausgelassen; die neutrale Ersatzlage verändert keine Score-Gewichtung."],
    )
    buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, asset_profile)
    history_label = history_label_from_frame(analysis_raw_data, "maximale verfügbare Historie")
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
        "Nur EUR",
        history_label,
        history_label,
        len(analysis_raw_data),
        external_research=False,
    )
    data_quality_label, _, _ = data_quality_status(research_pack.data_quality, [])
    levels = numeric_scenario_levels(close, supports, resistances, buy_signal.score)
    direction = forecast_direction_from_signal(buy_signal.score)
    probability_snapshot = build_raw_up_probability(
        research_pack.scenarios,
        levels,
        close,
    )

    def eur(value: float | None) -> float | None:
        if value is None or fx_rate is None:
            return None
        return round(float(value) * float(fx_rate), 6)

    target = levels["resistance"] if direction == "Steigend" else levels["support"] if direction == "Fallend" else levels["base"]
    risk = levels["support"] if direction == "Steigend" else levels["resistance"] if direction == "Fallend" else None
    horizons = [
        {
            "horizon": label,
            "days": days,
            "expected_direction": direction,
            "expected_low_eur": eur(levels["low"]),
            "expected_high_eur": eur(levels["high"]),
            "target_eur": eur(target),
            "risk_eur": eur(risk),
            "probability_up": probability_snapshot.get("probability_up"),
            "probability_schema_version": probability_snapshot.get("schema_version"),
        }
        for label, days in FORECAST_HORIZONS.items()
    ]
    return {
        "run_date": run_date,
        "created_at": datetime.now().astimezone().isoformat(),
        "ticker": symbol,
        "asset_name": asset_identity.get("name") or asset.get("name") or symbol,
        "asset_type": asset_profile.asset_type,
        "region": asset.get("region") or "Unbekannt",
        "category": asset.get("category") or "Unbekannt",
        "price_original": close,
        "original_currency": original_currency,
        "fx_rate_to_eur": fx_rate,
        "price_eur": eur(close),
        "asset_quality": asset_quality.score,
        "buy_signal": buy_signal.score,
        "market_phase": market_phase.phase,
        "predicted_direction": direction,
        "confidence": research_pack.confidence.score,
        "data_quality": research_pack.data_quality.score,
        "data_quality_label": data_quality_label,
        "history_rows": len(analysis_raw_data),
        "data_coverage": "Kursdaten, Ticker-Metadaten, Fundamentaldaten und Makrodaten; keine massenhaften asset-spezifischen News- oder Earnings-Abfragen.",
        "uncertainties": research_pack.uncertainty_factors,
        "scenarios": research_pack.scenarios,
        "professional_decision": research_pack.decision,
        "signal_snapshot": build_signal_snapshot(latest, risk_reward, research_pack.modules),
        "probability_snapshot": probability_snapshot,
        "module_scores": [
            {"name": module.name, "score": module.score, "summary": module.summary}
            for module in research_pack.modules
        ],
        "horizons": horizons,
        "model_type": FORECAST_MODEL_ENTRY,
        "logic_version": logic_version,
        "source": "daily-background",
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
    decision: dict[str, object],
) -> tuple[str, str]:
    title = str(decision.get("Titel") or research_action_text)
    reasons = " ".join(decision_items(decision, "Hauptgründe")[:3])
    risks = " ".join(decision_items(decision, "Zentrale Risiken")[:2])
    html = f"""
    <div class="decision-box">
        <div class="recommendation-label">Zentrale Einschätzung</div>
        <div class="decision-title">{title}</div>
        <div class="decision-section"><strong>Warum:</strong> {reasons or decision.get("Gesamtfazit", buy_signal.summary)}</div>
        <div class="decision-section"><strong>Nächste Handlung:</strong> {decision.get("Nächste Handlung", research_action_text)}</div>
        <div class="decision-section"><strong>Alternative:</strong> {decision.get("Alternative Handlung", "Daten nicht verfügbar")}</div>
        <div class="decision-section"><strong>Risiken:</strong> {risks or risk_reward.summary}</div>
        <div class="decision-section"><strong>Confidence:</strong> {decision.get("Confidence", recommendation_confidence_label(confidence.score))} · <strong>Anlagehorizont:</strong> {decision.get("Anlagehorizont", "mehrjährig")}</div>
    </div>
    """
    return title, html


def format_probabilities(probabilities: dict[str, int]) -> str:
    return " · ".join(f"{name}: {value}%" for name, value in probabilities.items())


def beginner_buy_answer(buy_signal_score: float, action_title: str) -> tuple[str, str]:
    if action_title == "Jetzt kaufen":
        answer = "Ja, mit Plan"
    elif action_title == "Erste Tranche kaufen":
        answer = "Eher ja, klein starten"
    elif action_title == "Bei Bestätigung kaufen":
        answer = "Noch nicht – Bestätigung abwarten"
    elif action_title == "Auf konkrete Kaufzone warten":
        answer = "Noch nicht – Kaufzone abwarten"
    elif action_title == "Halten":
        answer = "Halten"
    elif action_title == "Teilweise reduzieren":
        answer = "Eher reduzieren"
    else:
        answer = "Nein, aktuell vermeiden"

    score_text = str(buy_signal_score).replace(".", ",")
    text = (
        f"Meine einfache Einschätzung heute: {answer}. "
        f"Die zentrale Empfehlung lautet „{action_title}“; das separate Kaufsignal liegt bei {score_text}/10. "
        "Die Empfehlung berücksichtigt zusätzlich Qualität, Bewertung, CRV, Marktphase, Risiken, Datenlage und optional den Depot-Effekt. "
        "Für bedingte Einstiege stehen konkrete Rücksetzer-, Bestätigungs- und Widerlegungsmarken in der Analyse. "
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


def decision_items(decision: dict[str, object], key: str) -> list[str]:
    value = decision.get(key)
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def render_text_card(label: str, value: object, note: str | None = None) -> None:
    safe_note = f'<div class="text-card-note">{html_escape(note)}</div>' if note else ""
    st.markdown(
        f"""
        <div class="text-card">
            <div class="text-card-label">{html_escape(label)}</div>
            <div class="text-card-value">{html_escape(str(value))}</div>
            {safe_note}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recommendation_summary(
    decision: dict[str, object],
    asset_quality: ModuleScore,
    buy_signal: ModuleScore,
    risk_reward: RiskReward,
    portfolio_result: PortfolioResult,
) -> None:
    del asset_quality, buy_signal, risk_reward, portfolio_result
    title = str(decision.get("Titel") or "Keine Empfehlung verfügbar")
    st.markdown("### Empfehlung und konkreter Plan")
    message = f"Empfehlung: {title}"
    if title in {"Jetzt kaufen", "Erste Tranche kaufen", "Halten"}:
        st.success(message)
    elif title in {"Bei Bestätigung kaufen", "Auf konkrete Kaufzone warten"}:
        st.info(message)
    elif title == "Teilweise reduzieren":
        st.warning(message)
    else:
        st.error(message)

    assessment_cols = st.columns(3)
    with assessment_cols[0]:
        render_text_card(
            "Langfristige Attraktivität",
            decision.get("Langfristige Einschätzung") or "Nicht verfügbar",
            "Qualität, Wachstum und langfristige Risiken",
        )
    with assessment_cols[1]:
        render_text_card(
            "Preisattraktivität",
            decision.get("Preisattraktivität") or "Nicht verfügbar",
            "Preis im Verhältnis zu Bewertung und erwarteter Rendite",
        )
    with assessment_cols[2]:
        render_text_card(
            "Kurzfristiges Timing",
            decision.get("Aktuelles Timing") or "Nicht verfügbar",
            "Trend, Bodenbildung, Zonen und Momentum",
        )

    reason_col, risk_col = st.columns(2)
    with reason_col:
        st.markdown("**Warum?**")
        for reason in decision_items(decision, "Hauptgründe")[:3]:
            st.write(f"- {reason}")
    with risk_col:
        st.markdown("**Wichtigste Risiken**")
        for risk in decision_items(decision, "Zentrale Risiken")[:2]:
            st.write(f"- {risk}")

    st.markdown("**Konkreter Handlungsplan**")
    st.write(f"**Jetzt:** {decision.get('Handlung jetzt', 'Analyse neu bewerten.')}")
    st.write(f"**Rücksetzer-Kaufzone:** {decision.get('Kaufzone', 'Keine belastbare Kaufzone verfügbar.')}")
    st.write(f"**Reihenfolge der Tranchen:** {decision.get('Tranchierung', 'Keine belastbare Staffelung verfügbar.')}")
    st.write(f"**Bei einem Rücksetzer:** {decision.get('Handlung bei Rücksetzer', 'Keine belastbare Kaufzone verfügbar.')}")
    st.write(f"**Falls der Rücksetzer nicht kommt:** {decision.get('Handlung bei weiterer Stärke', 'Keine belastbare Bestätigung verfügbar.')}")
    st.warning(f"**Widerlegung:** {decision.get('Widerlegungsbedingung', 'Keine belastbare Marke verfügbar.')}")
    st.caption(f"Gültigkeit: {decision.get('Gültigkeit', 'Bei neuen Daten neu bewerten.')}")
    st.caption(str(decision.get("Positionsgröße") or "Prozentangaben beziehen sich auf die geplante Position; keine Eurobeträge werden erfunden."))


def modules_with_names(modules: list[ResearchModule], *markers: str) -> list[ResearchModule]:
    lowered = [marker.lower() for marker in markers]
    return [module for module in modules if any(marker in module.name.lower() for marker in lowered)]


def render_module_expander(
    label: str,
    modules: list[ResearchModule],
    *,
    beginner_mode: bool = False,
    details: list[str] | None = None,
) -> None:
    with st.expander(label, expanded=False):
        if not modules and not details:
            st.info("Für diesen Bereich sind derzeit keine belastbaren Daten verfügbar.")
            return
        for module in modules:
            score_text = "n/a" if module.score is None else f"{module.score:.1f}/10"
            st.markdown(f"**{module.name} · {score_text}**")
            st.write(module.summary)
            if beginner_mode and module.beginner:
                st.caption(module.beginner)
            for detail in module.details:
                st.write(f"- {detail}")
        for detail in details or []:
            st.write(f"- {detail}")


def user_relevant_modules(modules: list[ResearchModule]) -> list[ResearchModule]:
    relevant: list[ResearchModule] = []
    for module in modules:
        summary = module.summary.strip().lower()
        if module.score is None and (not summary or "nicht verfügbar" in summary):
            continue
        if "daten nicht verfügbar" in summary and module.score in {None, 5.0}:
            continue
        relevant.append(module)
    return relevant


def unique_text_items(*groups: Iterable[str], limit: int = 5) -> list[str]:
    items: list[str] = []
    for group in groups:
        for raw_item in group:
            item = str(raw_item).strip()
            if not item or item in items or item.lower().startswith("keine klar"):
                continue
            items.append(item)
            if len(items) >= limit:
                return items
    return items


def user_facing_detail_text(text: str) -> str:
    raw = str(text).strip()
    lowered = raw.lower()
    if "asset-qualität" in lowered:
        return "Die verfügbaren Qualitätsdaten unterstützen die langfristige Investmentthese."
    if "zukunftspotenzial" in lowered:
        return "Wachstum, Margen und verfügbare Zukunftsdaten unterstützen die Investmentthese."
    if "charttechnik" in lowered:
        return "Kursstruktur, Trend und Momentum liefern aktuell Rückenwind."
    if "bewertung" in lowered and "/10" in lowered:
        return "Die Bewertung wurde gegen Wachstum, Qualität und eingepreiste Erwartungen abgewogen."
    without_scores = re.sub(r"\b\d+(?:[.,]\d+)?/10\b", "", raw)
    without_counts = re.sub(r"\s+aus\s+\d+\s+verfügbaren\s+Kennzahlen", "", without_scores, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", without_counts).replace(" .", ".").strip()


def compact_scenario_rows(scenarios: list[dict]) -> list[dict[str, str]]:
    triggers = {
        "Bull-Case": "Bestätigter Aufwärtstrend und positive operative Entwicklung.",
        "Base-Case": "Intakte Kursstruktur bei weitgehend stabilen Rahmenbedingungen.",
        "Bear-Case": "Bruch der zentralen These oder deutliche Verschlechterung des Umfelds.",
    }
    return [
        {
            "Szenario": str(row.get("Szenario") or "Szenario"),
            "Notwendige Entwicklung": str(row.get("Was müsste passieren?") or "Daten nicht verfügbar"),
            "Wahrscheinlichkeit": str(row.get("Wahrscheinlichkeit") or "Daten nicht verfügbar"),
            "Mögliche Folge": str(row.get("Kursziel") or "Daten nicht verfügbar"),
            "Wichtigster Auslöser": triggers.get(str(row.get("Szenario")), "Neue belastbare Markt- oder Asset-Daten."),
        }
        for row in scenarios
    ]


def recommendation_risk_rows(decision: dict[str, object]) -> list[dict[str, str]]:
    value = decision.get("Risiko-Details")
    if not isinstance(value, list):
        return []
    return [
        {
            "Risiko": str(item.get("Risiko") or "Daten nicht verfügbar"),
            "Relevanz": str(item.get("Relevanz") or "nicht eingestuft"),
            "Erkennbar an": str(item.get("Erkennbar an") or "neuen belastbaren Daten"),
        }
        for item in value
        if isinstance(item, dict)
    ]


def detail_analysis_tab_labels(portfolio_enabled: bool) -> list[str]:
    labels = [
        "Investmentthese",
        "Preis & Bewertung",
        "Einstieg & Vorgehen",
        "Chancen",
        "Risiken",
        "Szenarien",
        "Markt & Umfeld",
    ]
    if portfolio_enabled:
        labels.append("Portfolio-Effekt")
    return labels


def advanced_analysis_tab_labels() -> list[str]:
    return ["Technische Kennzahlen", "Fundamentale Kennzahlen", "Datenqualität", "Methodik", "Prognosequalität"]


def forecast_status_messages(summary: dict, last_run: dict | None = None) -> list[str]:
    evaluated = int(summary.get("evaluated") or 0)
    open_count = int(summary.get("open") or 0)
    due = int(summary.get("due") or 0)
    missing_market_data = int(summary.get("missing_market_data") or 0)
    total = evaluated + open_count
    if total == 0:
        messages = ["Noch keine Prognosen vorhanden."]
        if last_run is None:
            messages.append(
                "Die automatische Prognoseerfassung ist noch nicht aktiv oder in der Prognosedatenbank wurde noch kein Hintergrundlauf dokumentiert."
            )
        else:
            messages.append(
                f"Der letzte Hintergrundlauf vom {last_run.get('run_date', 'unbekannten Datum')} hat noch keine auswertbaren Prognosen hinterlassen."
            )
        return messages

    messages = [
        f"{evaluated} Prognosezeiträume ausgewertet.",
        f"{open_count} Prognosezeiträume noch offen.",
    ]
    if missing_market_data:
        messages.append(
            f"{missing_market_data} fällige Auswertungen sind wegen fehlender verwertbarer Marktdaten derzeit nicht möglich."
        )
    other_due = max(due - missing_market_data, 0)
    if other_due:
        messages.append(
            f"{other_due} weitere Prognosen sind bereits fällig und werden beim nächsten Hintergrundlauf erneut geprüft."
        )
    not_due = max(open_count - due, 0)
    if not_due:
        messages.append(f"{not_due} Prognosezeiträume sind vorhanden, aber noch nicht fällig.")
    next_due = summary.get("next_due_date")
    if next_due:
        parsed = pd.to_datetime(next_due, errors="coerce")
        formatted = str(next_due) if pd.isna(parsed) else parsed.strftime("%d.%m.%Y")
        messages.append(f"Erste nächste Auswertung möglich ab: {formatted}.")
    if last_run is None:
        messages.append("Hintergrundbetrieb noch nicht dokumentiert; Einrichtung oder ersten Lauf prüfen.")
    return messages


def analysis_search_candidates(query: str, history: list[dict] | None = None) -> list[dict]:
    history = history if history is not None else load_search_history()
    recent = [
        ticker_candidate(
            str(item.get("symbol") or ""),
            name=str(item.get("name") or item.get("symbol") or ""),
            exchange=str(item.get("exchange") or "Daten nicht verfügbar"),
            currency=str(item.get("currency") or ""),
            source="Zuletzt analysiert",
        )
        for item in history
        if item.get("symbol")
    ]
    clean_query = normalize_query(query)
    if not clean_query:
        if recent:
            return dedupe_candidates(recent)[:8]
        return [ticker_candidate(symbol, source="Beispiel") for symbol in ["NVDA", "NOW", "EUNL.DE", "BTC-EUR"]]
    matching_recent = [
        candidate
        for candidate in recent
        if clean_query in normalize_query(f"{candidate.get('symbol', '')} {candidate.get('name', '')}")
    ]
    return dedupe_candidates([*matching_recent, *find_ticker_candidates(query)])[:8]


def render_forecast_quality_panel(
    database_path: Path = DEFAULT_DATABASE_PATH,
    calibration_path: Path = DEFAULT_CALIBRATION_PATH,
) -> None:
    st.subheader("Prognosequalität")
    st.caption(
        "Zentrale Erfolgsdefinition: Richtungstrefferquote. Fehlende oder nicht wertbare Daten werden nicht gezählt."
    )
    summary = forecast_summary(database_path)
    last_run = recent_run_status(database_path)
    operation = forecast_operational_status(database_path)
    with st.container(border=True):
        st.markdown("**Automatischer Datenlauf**")
        status_cols = st.columns(4)
        status_cols[0].metric("Betriebsstatus", operation["label"])
        last_run_value = operation.get("last_run") or {}
        status_cols[1].metric("Letzter Lauf", last_run_value.get("run_date") or "Noch keiner")
        status_cols[2].metric(
            "Verarbeitet",
            f"{int(last_run_value.get('processed_count') or 0)} / {int(last_run_value.get('universe_count') or 0)}",
        )
        next_run = pd.to_datetime(operation.get("next_run_at"), errors="coerce")
        status_cols[3].metric(
            "Nächster geplanter Lauf",
            "Unbekannt" if pd.isna(next_run) else next_run.strftime("%d.%m. %H:%M"),
        )
        message_renderer = {
            "success": st.success,
            "info": st.info,
            "warning": st.warning,
            "error": st.error,
        }.get(operation.get("severity"), st.info)
        message_renderer(operation["message"])
        sampling = last_run_value.get("sampling") or {}
        if sampling.get("mode") == "weekly_cohort":
            st.caption(
                "Wochenstichprobe: "
                f"{sampling.get('cohort_label') or sampling.get('cohort_id')} · "
                f"{int(sampling.get('scheduled_assets') or 0)} Assets aus "
                f"{int(sampling.get('weekly_universe_count') or 0)} pro Woche · "
                f"Universum {sampling.get('universe_version') or 'unbekannt'}"
            )
        elif sampling.get("mode") == "evaluation_only":
            st.caption(
                "Dieser Termin prüft nur fällige Ergebnisse. Es werden keine neuen "
                "Forward-Snapshots erzeugt."
            )
        if last_run_value.get("sampling_invalid"):
            st.warning("Die gespeicherten Wochenkohorten-Metadaten sind nicht lesbar.")
        if int(last_run_value.get("failure_count") or 0):
            st.caption(f"Fehlgeschlagene Assets im letzten Lauf: {int(last_run_value['failure_count'])}")
        operation_details = []
        if last_run_value.get("elapsed_seconds") is not None:
            operation_details.append(f"Laufzeit: {float(last_run_value['elapsed_seconds']):.1f} Sekunden")
        if last_run_value.get("processed_per_minute") is not None:
            operation_details.append(
                f"Tempo: {float(last_run_value['processed_per_minute']):.2f} Assets/Minute"
            )
        operation_details.append(
            f"Rate-Limit-Fehler: {int(last_run_value.get('rate_limit_failures') or 0)}"
        )
        if last_run_value.get("database_growth_bytes") is not None:
            operation_details.append(
                f"Datenbankwachstum: {int(last_run_value['database_growth_bytes']):+d} Bytes"
            )
        st.caption(" · ".join(operation_details))
        if operation.get("last_error"):
            st.caption(f"Letzter dokumentierter Fehler: {operation['last_error']}")
        if int(operation.get("consecutive_problem_runs") or 0) >= 2:
            st.error(
                f"{int(operation['consecutive_problem_runs'])} aufeinanderfolgende Läufe hatten Probleme. "
                "Bitte Aufgabenplanung, Internetverbindung und Laufprotokoll prüfen."
            )
    weekly_report = load_weekly_report()
    if weekly_report:
        with st.expander("Wöchentliche Marktstichprobe", expanded=False):
            schedule = weekly_report.get("schedule") or {}
            if schedule.get("active") is False:
                start_day = pd.to_datetime(schedule.get("start_date"), errors="coerce")
                start_text = (
                    "unbekannt" if pd.isna(start_day) else start_day.strftime("%d.%m.%Y")
                )
                st.info(f"Die neue Wochenrotation startet am {start_text}.")
            coverage = weekly_report.get("coverage") or {}
            universe = weekly_report.get("universe") or {}
            operations = weekly_report.get("operations") or {}
            weekly_cols = st.columns(4)
            weekly_cols[0].metric(
                "Erfolgreiche Assets",
                f"{int(coverage.get('successful_assets') or 0)} / "
                f"{int(universe.get('planned_assets') or 0)}",
            )
            weekly_cols[1].metric(
                "Abgeschlossene Kohorten",
                f"{int(coverage.get('completed_cohorts') or 0)} / "
                f"{int(coverage.get('planned_cohorts') or 0)}",
            )
            weekly_cols[2].metric(
                "Fehlgeschlagene Assets",
                int(coverage.get("failed_assets") or 0),
            )
            weekly_cols[3].metric(
                "Rate-Limit-Fehler",
                int(operations.get("rate_limit_failures") or 0),
            )
            overdue = coverage.get("overdue_cohorts") or []
            if overdue:
                st.warning(
                    f"{len(overdue)} fällige Wochenkohorte(n) fehlen noch und werden ohne "
                    "Rückdatierung beim nächsten möglichen Termin nachgeholt."
                )
            st.caption(
                f"Universum {universe.get('version') or 'unbekannt'} · "
                f"Abdeckung {float(coverage.get('successful_asset_coverage_pct') or 0):.2f} % · "
                f"Datenbankintegrität {(weekly_report.get('evaluations') or {}).get('integrity') or 'unbekannt'}"
            )
    st.info("\n\n".join(forecast_status_messages(summary, last_run)))
    metric_cols = st.columns(4)
    metric_cols[0].metric(
        "Gesamte Trefferquote",
        (
            "Getrennt nach Analyseart"
            if summary.get("mixed_models")
            else "Noch keine Daten" if summary["hit_rate"] is None else f"{summary['hit_rate']:.1f} %"
        ),
    )
    metric_cols[1].metric("Ausgewertet", int(summary["evaluated"]))
    metric_cols[2].metric("Offen", int(summary["open"]))
    metric_cols[3].metric(
        "Ø Abweichung",
        "n/a" if summary["average_deviation_pct"] is None else f"{summary['average_deviation_pct']:.2f} %",
    )
    outcome_cols = st.columns(4)
    outcome_cols[0].metric(
        "Immer-steigend-Referenz",
        "Noch keine Daten"
        if summary.get("always_up_hit_rate") is None
        else f"{float(summary['always_up_hit_rate']):.1f} %",
    )
    outcome_cols[1].metric(
        "Vorsprung zur Referenz",
        "Noch keine Daten"
        if summary.get("model_advantage_vs_always_up_pct") is None
        else f"{float(summary['model_advantage_vs_always_up_pct']):+.1f} Pp.",
    )
    outcome_cols[2].metric(
        "Ø Rendite",
        "Noch keine Daten"
        if summary.get("average_return_pct") is None
        else f"{float(summary['average_return_pct']):+.2f} %",
    )
    outcome_cols[3].metric(
        "Ø schlechteste Bewegung",
        "Noch keine Daten"
        if summary.get("average_drawdown_pct") is None
        else f"{float(summary['average_drawdown_pct']):+.2f} %",
    )
    if summary.get("evaluation_coverage_pct") is not None:
        st.caption(
            f"Ergebnisabdeckung fälliger Fälle: {float(summary['evaluation_coverage_pct']):.1f} % · "
            f"davon für Richtungsmetriken wertbar: {float(summary.get('metric_coverage_pct') or 0):.1f} %."
        )
    if summary.get("simple_trend_hit_rate") is not None:
        st.caption(
            f"20-Tage-Trendreferenz: {float(summary['simple_trend_hit_rate']):.1f} % · "
            f"Modellvorsprung: {float(summary.get('model_advantage_vs_simple_trend_pct') or 0):+.1f} Pp. · "
            f"Ø Überschussrendite zum Marktbenchmark: "
            f"{float(summary.get('average_excess_return_pct') or 0):+.2f} %."
        )
    if summary["evaluated"] < 20:
        st.caption("Noch nicht belastbar – weniger als 20 Prognosezeiträume wurden ausgewertet.")
    if summary.get("hit_rate_ci_low_pct") is not None:
        st.caption(
            "95-%-Unsicherheitsbereich der Richtungstrefferquote: "
            f"{float(summary['hit_rate_ci_low_pct']):.1f} bis "
            f"{float(summary['hit_rate_ci_high_pct']):.1f} %."
        )
    if summary.get("up_precision_pct") is not None:
        classification_parts = [
            f"Precision Steigend: {float(summary['up_precision_pct']):.1f} %",
            f"Recall Steigend: {float(summary.get('up_recall_pct') or 0):.1f} %",
        ]
        if summary.get("balanced_accuracy_pct") is not None:
            classification_parts.append(
                f"Balanced Accuracy: {float(summary['balanced_accuracy_pct']):.1f} %"
            )
        st.caption(" · ".join(classification_parts))
    if int(summary.get("probability_evaluated") or 0) > 0:
        st.caption(
            "Nicht kalibrierte Rohwahrscheinlichkeit · "
            f"{int(summary['probability_evaluated'])} Fälle · "
            f"Brier Score {float(summary['brier_score']):.4f} · "
            f"Log Loss {float(summary['log_loss']):.4f} · "
            f"Kalibrierungsfehler {float(summary['calibration_error_pct']):.1f} %."
        )
        if int(summary["probability_evaluated"]) < 50:
            st.caption(
                "Diese Wahrscheinlichkeitswerte sind noch nicht belastbar kalibriert; "
                "sie dienen zunächst nur der ehrlichen Forward-Messung."
            )
    if summary.get("mixed_models"):
        st.caption(
            "Mehrere Analysearten werden nicht zu einer gemeinsamen Trefferquote vermischt. "
            "Die belastbare Einordnung steht getrennt unter Analyseart."
        )

    calibration_profile = load_calibration_profile(calibration_path)
    with st.expander("Automatisches Kalibrierungsprofil", expanded=False):
        if not calibration_profile:
            st.info(
                "Noch kein Kalibrierungsprofil vorhanden. Es wird nach dem nächsten Hintergrundlauf "
                "automatisch aus echten Auswertungen erzeugt."
            )
        else:
            calibration_overall = calibration_profile.get("overall") or {}
            calibration_cols = st.columns(3)
            calibration_cols[0].metric(
                "Ausgewertete Fälle", int(calibration_overall.get("evaluated_cases") or 0)
            )
            calibration_cols[1].metric(
                "Reifegrad", calibration_overall.get("maturity_label") or "Daten nicht verfügbar"
            )
            calibration_cols[2].metric(
                "Manuelle Prüfhinweise",
                len(calibration_profile.get("manual_review_suggestions") or []),
            )
            st.caption(
                f"Profilversion: {calibration_profile.get('profile_version') or 'Unbekannt'} · "
                f"Datenfingerabdruck: {str(calibration_profile.get('data_fingerprint') or 'Unbekannt')[:12]}"
            )
            st.success(
                "Das Profil sammelt und bewertet historische Ergebnisse. Produktionsregeln und "
                "Score-Gewichte werden dadurch nicht automatisch verändert."
            )
            if int(calibration_overall.get("probability_evaluated") or 0) > 0:
                st.caption(
                    f"Rohwahrscheinlichkeiten: {int(calibration_overall['probability_evaluated'])} Fälle · "
                    f"Brier {float(calibration_overall['brier_score']):.4f} · "
                    f"Log Loss {float(calibration_overall['log_loss']):.4f} · "
                    f"Kalibrierungsfehler {float(calibration_overall['calibration_error_pct']):.1f} %."
                )
            learning_readiness = calibration_profile.get("learning_readiness") or {}
            st.caption(
                "Lern-Datensatz: "
                f"{int(learning_readiness.get('eligible_cases') or 0)} verifizierte gereifte Fälle · "
                f"Status {learning_readiness.get('status') or 'nicht verfügbar'} · "
                "Produktivaktivierung: gesperrt."
            )
            monitoring = calibration_profile.get("monitoring") or {}
            if monitoring:
                operations = monitoring.get("operational") or {}
                evaluation_coverage = operations.get("evaluation_coverage_pct")
                run_success_coverage = operations.get("recent_run_success_coverage_pct")
                stale_due_total = int(operations.get("stale_due_total") or 0)
                evaluation_coverage_text = (
                    "noch nicht messbar"
                    if evaluation_coverage is None
                    else f"{float(evaluation_coverage):.1f} %"
                )
                run_success_coverage_text = (
                    "noch nicht messbar"
                    if run_success_coverage is None
                    else f"{float(run_success_coverage):.1f} %"
                )
                st.markdown("**Rollierende Qualitäts- und Driftüberwachung**")
                st.caption(
                    f"Status {monitoring.get('status') or 'nicht verfügbar'} · "
                    f"Kalendarisch fällige Ergebnisabdeckung {evaluation_coverage_text} · "
                    f"mehr als drei Tage fällig: {stale_due_total} · "
                    f"Asset-Erfolgsabdeckung im jüngsten Fenster {run_success_coverage_text} · "
                    "rein beobachtend, keine automatische Modell- oder Regeländerung."
                )
                monitoring_alerts = monitoring.get("alerts") or []
                if monitoring_alerts:
                    for alert in monitoring_alerts[:10]:
                        message = (
                            f"{alert.get('scope') or 'Monitoring'}: "
                            f"{alert.get('message') or 'Prüfung erforderlich.'}"
                        )
                        if alert.get("severity") == "critical":
                            st.error(message)
                        else:
                            st.warning(message)
                else:
                    st.caption(
                        "Noch kein belastbarer Driftvergleich oder keine auffällige Verschlechterung; "
                        "kleine Datenmengen werden nicht als Drift ausgegeben."
                    )
            for suggestion in (calibration_profile.get("manual_review_suggestions") or [])[:10]:
                st.write(
                    f"- **{suggestion.get('priority', 'mittel').title()} · "
                    f"{suggestion.get('scope', 'Segment')}:** {suggestion.get('suggestion')} "
                    f"{suggestion.get('evidence')}"
                )

    breakdown_cols = st.columns(3)
    with breakdown_cols[0]:
        st.markdown("**Trefferquote nach Zeitraum**")
        horizon_rows = [
            {
                "Zeitraum": row["label"],
                "Ausgewertet": int(row["evaluated"] or 0),
                "Trefferquote": "n/a" if row["hit_rate"] is None else f"{float(row['hit_rate']):.1f} %",
                "Brier": (
                    "n/a"
                    if row.get("brier_score") is None
                    else f"{float(row['brier_score']):.4f}"
                ),
            }
            for row in summary["by_horizon"]
        ]
        st.dataframe(pd.DataFrame(horizon_rows), use_container_width=True, hide_index=True)
    with breakdown_cols[1]:
        st.markdown("**Trefferquote nach Asset-Typ**")
        type_rows = [
            {
                "Asset-Typ": row["label"],
                "Ausgewertet": int(row["evaluated"] or 0),
                "Trefferquote": "n/a" if row["hit_rate"] is None else f"{float(row['hit_rate']):.1f} %",
            }
            for row in summary["by_asset_type"]
        ]
        st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)
    with breakdown_cols[2]:
        st.markdown("**Trefferquote nach Analyseart**")
        model_rows = [
            {
                "Analyseart": row["label"],
                "Ausgewertet": int(row["evaluated"] or 0),
                "Trefferquote": "n/a" if row["hit_rate"] is None else f"{float(row['hit_rate']):.1f} %",
                "Brier": (
                    "n/a"
                    if row.get("brier_score") is None
                    else f"{float(row['brier_score']):.4f}"
                ),
            }
            for row in summary["by_model"]
        ]
        st.dataframe(pd.DataFrame(model_rows), use_container_width=True, hide_index=True)

    with st.expander("Weitere Qualitätssegmente", expanded=False):
        st.caption(
            "Gesamtwerte können Schwächen einzelner Regionen, Marktphasen, Datenqualitäten oder "
            "Logikversionen verdecken. Segmente ohne echte Auswertung bleiben als nicht belastbar sichtbar."
        )

        def segment_table(rows: list[dict]) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {
                        "Segment": row.get("label") or "Unbekannt",
                        "Ausgewertet": int(row.get("evaluated") or 0),
                        "Trefferquote": (
                            "n/a"
                            if row.get("hit_rate") is None
                            else f"{float(row['hit_rate']):.1f} %"
                        ),
                        "Ø Rendite": (
                            "n/a"
                            if row.get("average_return_pct") is None
                            else f"{float(row['average_return_pct']):+.2f} %"
                        ),
                        "Ø Überschuss": (
                            "n/a"
                            if row.get("average_excess_return_pct") is None
                            else f"{float(row['average_excess_return_pct']):+.2f} %"
                        ),
                    }
                    for row in rows[:20]
                ]
            )

        segment_cols = st.columns(2)
        with segment_cols[0]:
            st.markdown("**Region**")
            st.dataframe(segment_table(summary.get("by_region") or []), use_container_width=True, hide_index=True)
            st.markdown("**Datenqualität**")
            st.dataframe(
                segment_table(summary.get("by_data_quality") or []),
                use_container_width=True,
                hide_index=True,
            )
        with segment_cols[1]:
            st.markdown("**Marktphase**")
            st.dataframe(
                segment_table(summary.get("by_market_phase") or []),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("**Logikversion**")
            st.dataframe(
                segment_table(summary.get("by_logic_version") or []),
                use_container_width=True,
                hide_index=True,
            )

    filter_cols = st.columns([2, 1, 1, 1, 1])
    search = filter_cols[0].text_input("Asset oder Ticker", key="forecast_quality_search")
    asset_type = filter_cols[1].selectbox(
        "Asset-Typ", ["Alle", "Aktie", "ETF", "Krypto", "Derivat / unbekannt"], key="forecast_quality_type"
    )
    model_labels = {"Alle": "Alle", **{label: key for key, label in FORECAST_MODEL_LABELS.items()}}
    model_label = filter_cols[2].selectbox(
        "Analyseart", list(model_labels), key="forecast_quality_model"
    )
    horizon = filter_cols[3].selectbox(
        "Prognosezeitraum", ["Alle", *FORECAST_HORIZONS], key="forecast_quality_horizon"
    )
    result_status = filter_cols[4].selectbox(
        "Ergebnis", ["Alle", "Offen", "Treffer", "Fehler"], key="forecast_quality_result"
    )
    today = pd.Timestamp.now().date()
    created_range = st.date_input(
        "Erstellungszeitraum",
        value=(today - pd.Timedelta(days=365), today),
        key="forecast_quality_created_range",
    )
    if isinstance(created_range, (list, tuple)) and len(created_range) == 2:
        created_from, created_to = created_range
    else:
        created_from = created_to = None
    page_size = 50
    page = st.number_input("Seite", min_value=1, value=1, step=1, key="forecast_quality_page")
    rows, total = forecast_quality_rows(
        database_path,
        search=search,
        asset_type=asset_type,
        model_type=model_labels[model_label],
        horizon=horizon,
        result_status=result_status,
        created_from=created_from,
        created_to=created_to,
        limit=page_size,
        offset=(int(page) - 1) * page_size,
    )
    st.caption(f"{total} passende Prognosezeiträume · maximal {page_size} Zeilen pro Seite")
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Für die gewählten Filter liegen noch keine Prognosedaten vor.")
    if last_run:
        st.caption(
            f"Letzter Hintergrundlauf: {last_run['run_date']} · {last_run['status']} · "
            f"{last_run['success_count']} erfolgreich · {last_run['failure_count']} fehlgeschlagen"
        )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    st.markdown(
        """
        <style>
        :root {
            --ia-radius: 16px;
            --ia-border: rgba(148, 163, 184, 0.28);
            --ia-surface: rgba(15, 23, 42, 0.30);
            --ia-muted: #cbd5e1;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: var(--ia-radius);
            border-color: var(--ia-border);
            background: linear-gradient(145deg, rgba(30, 41, 59, 0.24), rgba(15, 23, 42, 0.12));
            box-shadow: 0 12px 32px rgba(2, 6, 23, 0.10);
        }
        .stButton > button {
            border-radius: 12px;
            min-height: 2.8rem;
            font-weight: 650;
        }
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
        .text-card {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 8px;
            padding: 14px 16px;
            background: rgba(15, 23, 42, 0.30);
            margin-bottom: 12px;
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .text-card-label {
            color: #9ca3af;
            font-size: 0.86rem;
            margin-bottom: 4px;
        }
        .text-card-value {
            font-size: 1.25rem;
            font-weight: 650;
            line-height: 1.3;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .text-card-note {
            color: #cbd5e1;
            font-size: 0.88rem;
            line-height: 1.4;
            margin-top: 6px;
            white-space: normal;
            overflow-wrap: anywhere;
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
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] > div,
        [data-testid="stMarkdownContainer"],
        [data-testid="stAlertContainer"] {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word;
        }
        @media (max-width: 700px) {
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
            [data-testid="stColumn"] {
                flex: 1 1 100% !important;
                width: 100% !important;
                min-width: 100% !important;
            }
            .recommendation-value, .decision-title {
                font-size: 1.8rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    page_state_key = "active_page"
    valid_pages = {
        "home",
        "analysis",
        "opportunities",
        "swing_finder",
        "scanner",
        "research_knowledge",
    }
    if page_state_key not in st.session_state:
        st.session_state[page_state_key] = "home"
    if st.session_state[page_state_key] == "scanner":
        st.session_state[page_state_key] = "swing_finder"
    if st.session_state[page_state_key] not in valid_pages:
        st.session_state[page_state_key] = "home"
    active_page = st.session_state[page_state_key]

    if active_page == "home":
        home_title_col, home_quality_col = st.columns([4, 1])
        with home_title_col:
            st.title("Investment Assistant")
        with home_quality_col:
            quality_summary = forecast_summary()
            operation = forecast_operational_status()
            hit_rate = quality_summary["hit_rate"]
            st.metric(
                "Prognose-Trefferquote",
                "Nach Analyseart" if quality_summary.get("mixed_models") else "–" if hit_rate is None else f"{hit_rate:.1f} %",
            )
            st.caption(f"Datenlauf: {operation['label']}")
            if operation["severity"] == "error":
                st.error("Automatischen Datenlauf prüfen")
            for status_line in forecast_status_messages(quality_summary, recent_run_status())[:3]:
                st.caption(status_line)
            if quality_summary["evaluated"] < 20:
                st.caption("Noch nicht belastbar")
        st.subheader("Was möchtest du untersuchen?")
        st.write("Drei getrennte Anlagebereiche plus eine isolierte Research-Infrastruktur.")

        analysis_col, opportunities_col, scanner_col = st.columns(3, gap="large")
        with analysis_col:
            with st.container(border=True):
                st.subheader("Asset-Analyse")
                st.caption("Bekanntes Asset · konkreter Einstieg")
                st.write("Eine Aktie, einen ETF oder eine Kryptowährung gezielt bewerten.")
                if st.button("Asset-Analyse öffnen", type="primary", use_container_width=True):
                    st.session_state[page_state_key] = "analysis"
                    st.rerun()

        with opportunities_col:
            with st.container(border=True):
                st.subheader("Investment Opportunities")
                st.caption("Monate bis Jahre · neue Ideen")
                st.write("Hochwertige mittel- und langfristige Investmentchancen entdecken.")
                if st.button("Investment Opportunities öffnen", use_container_width=True):
                    st.session_state[page_state_key] = "opportunities"
                    st.rerun()

        with scanner_col:
            with st.container(border=True):
                st.subheader("Swing Trade Finder")
                st.caption("Tage bis Wochen · konkrete Setups")
                st.write("Selektive Long-Swing-Trades mit Einstieg, Stop und Zielen finden.")
                if st.button("Swing Trade Finder öffnen", use_container_width=True):
                    st.session_state[page_state_key] = "swing_finder"
                    st.rerun()

        with st.container(border=True):
            research_text_col, research_button_col = st.columns([3, 1])
            with research_text_col:
                st.subheader("Research Knowledge Base")
                st.caption("Quellen · Hypothesen · Experimente · Ergebnisse · Evidence Ledger")
                st.write("Geprüftes Research-Wissen dauerhaft dokumentieren und frühere negative Ergebnisse wiederfinden.")
            with research_button_col:
                if st.button("Knowledge Base öffnen", use_container_width=True):
                    st.session_state[page_state_key] = "research_knowledge"
                    st.rerun()

        st.warning(DISCLAIMER)
        st.caption("Keine Broker-Anbindung. Keine Kauf- oder Verkaufsautomatisierung. Die letzte Entscheidung trifft immer der Nutzer.")
        return

    if st.button("← Zurück zur Startseite", key=f"back_to_home_{active_page}"):
        st.session_state[page_state_key] = "home"
        st.rerun()

    if active_page == "research_knowledge":
        render_research_knowledge_base(RESEARCH_KNOWLEDGE_PATH)
        return

    if active_page == "opportunities":
        st.title("Investment Opportunities")
        st.write("Neue mittel- und langfristige Investmentideen entdecken.")
        st.info(
            "Dieser Bereich wird als eigenständiges Modul aufgebaut. Der heutige Swing Trade Finder wird dafür "
            "nicht fachlich wiederverwendet, und es werden keine scheinbaren Kandidaten erzeugt."
        )
        current_col, future_col = st.columns(2, gap="large")
        with current_col:
            with st.container(border=True):
                st.subheader("Aktuell attraktiv")
                st.caption("Mehrere Monate bis ungefähr drei Jahre")
                st.write("Geplant: gute Unternehmen mit attraktivem Verhältnis aus Preis, Potenzial und Risiko.")
        with future_col:
            with st.container(border=True):
                st.subheader("Zukunftschancen 3+ Jahre")
                st.caption("Drei bis sieben Jahre")
                st.write("Geplant: Unternehmen mit strukturellem Wachstum und noch nicht voll eingepreistem Potenzial.")
        st.warning(DISCLAIMER)
        st.caption("Keine Broker-Anbindung. Keine Kauf- oder Verkaufsautomatisierung.")
        return

    if active_page == "swing_finder":
        st.title("Swing Trade Finder")
        st.write("Automatischer Marktfilter für wenige, vollständig geprüfte Long-Swing-Setups.")

        if not load_risk_acknowledgement(SWING_RISK_ACK_PATH):
            st.warning(RISK_NOTICE)
            st.caption("Diese Bestätigung wird nur lokal gespeichert und muss pro Installation einmal erfolgen.")
            if st.button("Verstanden und fortfahren", type="primary", use_container_width=True):
                acknowledged_at = datetime.now().astimezone().isoformat()
                if save_risk_acknowledgement(SWING_RISK_ACK_PATH, acknowledged_at):
                    st.rerun()
                else:
                    st.error("Die lokale Bestätigung konnte nicht sicher gespeichert werden.")
            return

        st.caption("Die App führt keine Käufe, Verkäufe oder Orders aus.")

        expire_due_paper_trades()
        trading_capital_eur = st.number_input(
            "Verfügbares Tradingkapital in Euro",
            min_value=0.0,
            value=0.0,
            step=1_000.0,
            help="Ein Kapital größer als 0 € ermöglicht die automatische, konservative Positionsberechnung.",
        )
        settings = internal_swing_settings(trading_capital_eur)

        universe_report = load_swing_universe(DEFAULT_SWING_UNIVERSE_PATH)
        with st.expander("Erweiterte Einstellungen und Universum", expanded=False):
            st.caption("Alle Werte sind intern festgelegt und hier bewusst nicht veränderbar.")
            policy = risk_policy_as_dict()
            st.write(
                f"Risikoregel {policy['version']}: höchstens {policy['max_risk_pct_per_trade']:.2f}% Risiko je Trade, "
                f"{policy['max_total_open_risk_pct']:.2f}% offenes Gesamtrisiko, "
                f"{policy['max_total_exposure_pct']:.1f}% Gesamtbelastung "
                f"und {policy['max_position_exposure_pct']:.1f}% je Position."
            )
            st.caption("Die Anzahl gleichzeitiger Trades ist dynamisch und nicht mehr auf drei begrenzt.")
            prefilter = prefilter_thresholds_as_dict()
            st.write(
                f"Vorfilter: mindestens {prefilter['min_history_rows']} Tageszeilen; anschließend werden "
                "alle ernsthaft möglichen Kandidaten vollständig analysiert."
            )
            st.write(
                f"Universum {universe_report.assets[0].version if universe_report.assets else 'nicht verfügbar'}: "
                f"{universe_report.active_count} aktive gültige Assets."
            )
            if universe_report.errors:
                for error in universe_report.errors:
                    st.error(error)
            if universe_report.assets:
                universe_rows = [asset.as_dict() for asset in universe_report.assets]
                st.dataframe(pd.DataFrame(universe_rows), use_container_width=True, hide_index=True)

        scan_requested = st.button("Markt jetzt scannen", type="primary", use_container_width=True)

        scan_state_key = "swing_scanner_result"
        if scan_requested:
            if universe_report.active_count < 1_000:
                st.error("Der Scan wurde gestoppt: Das geprüfte Universum enthält weniger als 1.000 aktive Assets.")
                return
            with st.spinner("Lade das Marktuniversum, filtere schnell vor und prüfe alle möglichen Kandidaten vollständig..."):
                scan_result = scan_swing_market(settings)
            try:
                forward_record = record_swing_forward_scan(scan_result)
                signal_snapshots = {
                    str(item["signal_id"]): dict(item["snapshot"])
                    for item in load_swing_forward_signals(DEFAULT_SWING_FORWARD_DB_PATH)
                }
                for setup in scan_result["approved"]:
                    signal_id = forward_record["signal_ids_by_setup"].get(str(setup.get("setup_id") or ""))
                    if signal_id:
                        setup["forward_signal_id"] = signal_id
                        setup["forward_signal_snapshot"] = signal_snapshots.get(signal_id, {})
                try:
                    scan_result["historical_real_forward_linkage"] = (
                        refresh_swing_walk_forward_forward_links(
                            DEFAULT_SWING_WALK_FORWARD_DB_PATH,
                            DEFAULT_SWING_FORWARD_DB_PATH,
                        )
                    )
                except Exception as linkage_exc:
                    scan_result["historical_real_forward_linkage"] = {
                        "status": "attention",
                        "error": str(linkage_exc),
                        "automatic_rule_change": False,
                    }
                scan_result["forward_documentation"] = (
                    f"Echter Forward-Scan unveränderbar gespeichert: Scan {forward_record['scan_id'][:12]}, "
                    f"{forward_record['signals_total']} Signal(e)."
                )
            except Exception as exc:
                scan_result["forward_documentation"] = f"Forward-Speicherung fehlgeschlagen: {exc}"
                scan_result["errors"].append(scan_result["forward_documentation"])
            paper_records = [swing_setup_trade_record(setup) for setup in scan_result["approved"]]
            documented_count, documented_message = auto_document_trade_setups(paper_records)
            scan_result["paper_documentation"] = documented_message
            st.session_state[scan_state_key] = scan_result
            if documented_count:
                st.success(documented_message)

        render_swing_user_trades()
        render_swing_bot_evidence_status()
        render_swing_walk_forward_research()

        scan_result = st.session_state.get(scan_state_key)
        if not isinstance(scan_result, dict):
            latest_background_scan = None
            if DEFAULT_SWING_FORWARD_DB_PATH.exists():
                background_scans = load_swing_forward_scans(DEFAULT_SWING_FORWARD_DB_PATH)
                latest_background_scan = background_scans[-1] if background_scans else None
            initial_cols = st.columns(4)
            if latest_background_scan is None:
                initial_cols[0].metric("Marktlage", "Noch kein Scan")
                initial_cols[1].metric("Universum", universe_report.active_count)
                initial_cols[2].metric("Kursdaten geladen", 0)
                initial_cols[3].metric("Freigegeben", 0)
                st.info(
                    "Starte den Scan. Alle Assets durchlaufen zuerst den schnellen Vorfilter; alle ernsthaft möglichen "
                    "Kandidaten werden tief analysiert. Wenn nichts alle Mindestregeln erfüllt, wird kein Trade erzwungen."
                )
            else:
                background_snapshot = dict(latest_background_scan.get("snapshot") or {})
                background_statistics = dict(background_snapshot.get("statistics") or {})
                initial_cols[0].metric("Marktlage", background_snapshot.get("market_label", "Nicht verfügbar"))
                initial_cols[1].metric("Zuletzt geprüft", int(background_statistics.get("universe_size") or 0))
                initial_cols[2].metric("Kursdaten geladen", int(background_statistics.get("loaded_assets") or 0))
                initial_cols[3].metric("Freigegeben", int(background_statistics.get("approved_trades") or 0))
                st.caption(
                    f"Letzter automatischer Regional-Scan: {latest_background_scan.get('observed_at', 'Zeit nicht verfügbar')} · "
                    f"Bereich {background_snapshot.get('scan_scope', 'nicht verfügbar')}. "
                    "Ein manueller Vollscan ist für diese gespeicherten Ergebnisse nicht erforderlich."
                )
                render_swing_background_signals(settings)
            return

        render_swing_scanner(scan_result, settings)
        return

    heading_col, settings_col = st.columns([5, 1])
    with heading_col:
        st.title("Asset-Analyse")
        st.write("Einzelne Aktien, ETFs oder Kryptowährungen analysieren und bewerten.")
    with settings_col:
        with st.popover("⚙ Einstellungen", use_container_width=True):
            period_label = st.selectbox("Zeitraum", list(PERIOD_OPTIONS), index=2)
            interval = st.selectbox("Intervall", INTERVAL_OPTIONS, index=4)
            refresh_label = st.selectbox("Auto-Refresh", list(REFRESH_OPTIONS), index=0)
            currency_label = st.selectbox(
                "Währungsanzeige", ["Nur Euro", "Euro und Originalwährung"], index=0
            )
            currency_mode = "Nur EUR" if currency_label == "Nur Euro" else "EUR + Originalwährung"
            position_status = st.radio(
                "Aktuelle Position", ["Ich habe keine Position", "Ich halte bereits"], index=0
            )
            portfolio_enabled = st.toggle("Portfolio in Bewertung einbeziehen", value=False)
            beginner_mode = st.toggle("Anfänger-Modus", value=True)
            with st.expander("Erweiterte Einstellungen", expanded=False):
                manual_asset_type = st.selectbox(
                    "Asset-Typ manuell korrigieren",
                    ["Automatisch", "Aktie", "ETF", "Krypto", "Unbekannt"],
                    index=0,
                )
                st.caption("Nur verwenden, wenn die automatische Erkennung unzutreffend ist.")
            with st.expander("Erweiterte Einblicke", expanded=False):
                show_forecast_quality = st.toggle("Prognosequalität", value=False)

    st.warning(DISCLAIMER)
    st.caption("Keine Broker-Anbindung. Keine Kauf- oder Verkaufsautomatisierung. Die letzte Entscheidung trifft immer der Nutzer.")

    if show_forecast_quality:
        render_forecast_quality_panel()
        st.divider()

    st.subheader("Asset suchen")
    search_col, button_col = st.columns([5, 1])
    with search_col:
        query = st.text_input(
            "Asset-Name oder Yahoo-Finance-Ticker",
            value="",
            placeholder="z. B. ServiceNow, NVDA, EUNL.DE oder Bitcoin",
            label_visibility="collapsed",
        )
    with button_col:
        analyze_clicked = st.button("Analysieren", type="primary", use_container_width=True)

    candidates = analysis_search_candidates(query)
    candidate_labels = [
        f"{format_candidate(candidate)} · {candidate.get('source', 'Yahoo Finance')}"
        for candidate in candidates
    ]
    selected_candidate_data = None
    if candidate_labels:
        selected_label = st.selectbox(
            "Vorschläge",
            candidate_labels,
            help="Zuletzt erfolgreich analysierte Assets werden priorisiert; bei Eingabe kommen Yahoo-Finance-Treffer hinzu.",
        )
        selected_candidate_data = candidates[candidate_labels.index(selected_label)]
        st.caption(
            f"Auswahl: {selected_candidate_data['name']} · {selected_candidate_data['symbol']} · "
            f"{selected_candidate_data['exchange']}"
        )
    elif query.strip():
        st.error("Kein passender Yahoo-Finance-Treffer gefunden. Fehlgeschlagene Suchen werden nicht gespeichert.")
        similar = similar_ticker_suggestions(query)
        if similar:
            st.info("Mögliche Alternativen: " + ", ".join(format_candidate(item) for item in similar))

    if analyze_clicked:
        if selected_candidate_data:
            st.session_state["analysis_candidate"] = dict(selected_candidate_data)
            st.session_state["analysis_query"] = query.strip() or selected_candidate_data["symbol"]
            st.session_state["analysis_started_at"] = datetime.now().astimezone().isoformat()
            detail_state_key = f"analysis_detail_visible_{str(selected_candidate_data['symbol']).upper()}"
            st.session_state[detail_state_key] = False
        else:
            st.error("Bitte wähle zuerst ein Asset aus der Vorschlagsliste aus.")

    selected_candidate_data = st.session_state.get("analysis_candidate")
    symbol = str(selected_candidate_data.get("symbol", "")).upper() if selected_candidate_data else ""
    analyze = bool(symbol)

    refresh_seconds = REFRESH_OPTIONS[refresh_label]
    if refresh_seconds:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_seconds}'>", unsafe_allow_html=True)
        st.caption(f"Auto-Refresh aktiv: Die Seite lädt alle {refresh_seconds} Sekunden neu. Yahoo-Finance-Daten können verzögert sein.")

    if not analyze:
        st.info("Wähle einen Vorschlag und starte die Analyse.")
        return

    if analyze:
        selected_period = PERIOD_OPTIONS[period_label]
        if interval in {"1m", "5m", "15m"} and selected_period not in {"1d", "5d", "1mo"}:
            selected_period = "5d"
            st.info("Intraday-Daten sind bei Yahoo Finance nur für kürzere Zeiträume sinnvoll. Der Zeitraum wurde für diesen Abruf auf 5 Tage gesetzt.")
        chart_history_label = PERIOD_HISTORY_LABELS.get(selected_period, selected_period)
        with st.spinner(f"Lade langfristige Analyse-Daten für {symbol}..."):
            try:
                analysis_raw_data = load_price_data(symbol, "max", "1d")
            except RuntimeError as exc:
                st.error(str(exc))
                return
        if interval == "1d":
            chart_raw_data = daily_chart_frame_from_analysis(analysis_raw_data, selected_period)
        else:
            with st.spinner(f"Lade Chart-Daten für {symbol}..."):
                try:
                    chart_raw_data = load_price_data(symbol, selected_period, interval)
                except RuntimeError as exc:
                    st.error(str(exc))
                    return

        if analysis_raw_data.empty or "Close" not in analysis_raw_data:
            st.error("Für diesen Ticker konnten keine Kursdaten geladen werden. Prüfe das Yahoo-Finance-Symbol oder probiere eine andere Börse.")
            return
        if chart_raw_data.empty or "Close" not in chart_raw_data:
            st.warning("Chart-Daten für den gewählten Zeitraum konnten nicht geladen werden. Der Chart nutzt ersatzweise die letzten Analyse-Daten.")
            chart_raw_data = analysis_raw_data.tail(252)
            chart_history_label = "letzte Analyse-Daten als Ersatz"

        df = calculate_indicators(analysis_raw_data, "1d")
        chart_df = calculate_indicators(chart_raw_data, interval)
        analysis_history_label = history_label_from_frame(analysis_raw_data, "maximale verfügbare Historie")
        chart_supports = local_levels(chart_df["Low"], "support") if "Low" in chart_df else []
        chart_resistances = local_levels(chart_df["High"], "resistance") if "High" in chart_df else []
        supports = local_levels(df["Low"], "support")
        resistances = local_levels(df["High"], "resistance")
        score_result = calculate_score_v2(df, supports, resistances)
        latest = df.iloc[-1]
        has_position = position_status == "Ich halte bereits"
        close_value = float(latest["Close"])
        with st.spinner(f"Lade externe Research-Daten für {symbol} parallel..."):
            external_context = load_external_analysis_context(symbol)
        ticker_info_value = external_context.get("ticker_info")
        ticker_info = dict(ticker_info_value) if isinstance(ticker_info_value, dict) else {}
        macro_value = external_context.get("macro")
        macro = macro_value if isinstance(macro_value, ModuleScore) else ModuleScore(5.0, "Makrodaten nicht verfügbar.", [])
        news_value = external_context.get("news")
        news = news_value if isinstance(news_value, ModuleScore) else ModuleScore(5.0, "News-Daten nicht verfügbar.", [])
        commodity_value = external_context.get("commodity_data")
        commodity_data = commodity_value if isinstance(commodity_value, dict) else {}
        earnings_value = external_context.get("earnings_dates")
        earnings_dates = earnings_value if isinstance(earnings_value, pd.DataFrame) else pd.DataFrame()
        if selected_candidate_data:
            ticker_info = dict(ticker_info)
            if selected_candidate_data.get("quote_type") and not ticker_info.get("quoteType"):
                ticker_info["quoteType"] = selected_candidate_data["quote_type"]
            if selected_candidate_data.get("currency") and not ticker_info.get("currency"):
                ticker_info["currency"] = selected_candidate_data["currency"]
        asset_identity = build_asset_identity(symbol, ticker_info, selected_candidate_data)
        original_currency = asset_identity["currency"]
        fx_rate, fx_ticker = get_fx_rate_to_eur(original_currency)
        save_successful_search(str(st.session_state.get("analysis_query") or symbol), asset_identity)
        auto_profile = detect_asset_type(symbol, ticker_info)
        if auto_profile.asset_type == "Derivat / unbekannt" and manual_asset_type == "Automatisch":
            st.warning("Der Asset-Typ konnte nicht sicher erkannt werden. Bitte korrigiere ihn nur bei sicherer Kenntnis.")
            uncertain_type = st.selectbox(
                "Asset-Typ korrigieren",
                ["Unbekannt", "Aktie", "ETF", "Krypto"],
                key=f"uncertain_asset_type_{symbol}",
            )
            manual_asset_type = uncertain_type
        asset_profile = override_asset_profile(auto_profile, manual_asset_type)
        market_phase = detect_market_phase(df)
        risk_reward = calculate_risk_reward(close_value, supports, resistances)
        technical = technical_module(score_result, market_phase)
        asset_quality = score_asset_quality_from_info(symbol, asset_profile, df, ticker_info)
        fundamentals = asset_quality
        buy_signal = score_buy_signal(score_result, market_phase, risk_reward, latest, asset_profile)
        portfolio_result = evaluate_portfolio(symbol, portfolio_enabled, buy_signal.score, asset_profile)
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
            chart_history_label,
            analysis_history_label,
            len(chart_raw_data),
            portfolio_result=portfolio_result,
            has_position=has_position,
            ticker_info=ticker_info,
            commodity_data=commodity_data,
            earnings_dates=earnings_dates,
        )
        data_source_warnings = build_data_source_warnings(
            ticker_info,
            original_currency,
            fx_rate,
            fx_ticker,
            news,
            macro,
        )
        trade_history = load_trade_history()
        forward_history = load_forward_tests()
        decision_history = load_decision_history()
        prediction_history = load_prediction_history()
        backtest_history = load_backtest_history()
        local_history_quality_status, local_history_quality_table = local_history_quality_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
            backtest_history,
        )
        calibration_status, calibration_rows = calibration_status_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
            local_history_quality_table,
        )
        learning_guardrail_status, learning_guardrail_table = learning_guardrail_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
        )
        calibration_context_status, calibration_context_table = calibration_context_summary_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
        )
        signal_learning_status, signal_learning_table = signal_learning_rows(forward_history, prediction_history)
        prediction_hit_status, prediction_hit_table = prediction_hit_rate_rows(prediction_history)
        segmented_learning_status, segmented_learning_table = segmented_learning_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
        )
        negative_cause_status, negative_cause_table = negative_case_cause_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
        )
        calibration_suggestion_status, calibration_suggestion_table = calibration_suggestion_rows(
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
            backtest_history,
        )
        backtest_learning_status, backtest_learning_table = backtest_history_learning_rows(backtest_history)
        backtest_status, backtest_table = backtest_signal_buckets(df, asset_profile)
        backtest_compact_status, backtest_compact_table = backtest_compact_rows(backtest_table)
        historical_confidence_status, historical_confidence_table = historical_confidence_rows(
            trade_history,
            forward_history,
            prediction_history,
            asset_profile,
            market_phase,
        )
        action_title = str(research_pack.decision.get("Titel") or research_pack.action)
        similar_setup_status, similar_setup_table = similar_setup_rows(
            asset_profile,
            market_phase,
            action_title,
            asset_quality,
            buy_signal,
            trade_history,
            forward_history,
            decision_history,
            prediction_history,
        )
        score_result.recommendation = action_title
        display_df = converted_price_frame(chart_df, fx_rate)
        display_chart_supports = converted_levels(chart_supports, fx_rate)
        display_chart_resistances = converted_levels(chart_resistances, fx_rate)
        quality_label, quality_summary, quality_highlights = data_quality_status(research_pack.data_quality, data_source_warnings)

        analysis_started_at = str(st.session_state.get("analysis_started_at") or datetime.now().astimezone().isoformat())
        try:
            analysis_time = datetime.fromisoformat(analysis_started_at).astimezone().strftime("%d.%m.%Y · %H:%M Uhr")
        except ValueError:
            analysis_time = datetime.now().astimezone().strftime("%d.%m.%Y · %H:%M Uhr")

        st.subheader(f"{asset_identity['name']} · {asset_identity['symbol']}")
        identity_cols = st.columns(4)
        identity_cols[0].metric(
            "Aktueller Kurs",
            format_display_money(float(latest["Close"]), original_currency, fx_rate, currency_mode),
        )
        identity_cols[1].metric("Anlagehorizont", str(research_pack.decision.get("Anlagehorizont") or "mehrjährig"))
        identity_cols[2].metric("Confidence", str(research_pack.decision.get("Confidence") or "niedrig").capitalize())
        identity_cols[3].metric("Asset-Typ", asset_profile.asset_type)
        st.caption(
            f"Analyse: {analysis_time} · Börse: {asset_identity['exchange']} · Ticker: {asset_identity['symbol']}"
        )
        if original_currency == "EUR":
            st.caption("Originalwährung: EUR · keine Umrechnung nötig")
        elif fx_rate is None:
            st.warning(
                f"Die EUR-Umrechnung für {original_currency} ist derzeit nicht verfügbar ({fx_ticker}). "
                "Betroffene Beträge werden transparent in Originalwährung gekennzeichnet."
            )
        elif currency_mode == "EUR + Originalwährung":
            st.caption(f"Originalwährung: {original_currency} · 1 {original_currency} = {fx_rate:.4f} EUR ({fx_ticker})")

        render_recommendation_summary(
            research_pack.decision,
            asset_quality,
            buy_signal,
            risk_reward,
            portfolio_result,
        )

        detail_state_key = f"analysis_detail_visible_{symbol}"
        detail_visible = bool(st.session_state.get(detail_state_key, False))
        detail_button_label = "Analyse im Detail ausblenden" if detail_visible else "Analyse im Detail anzeigen"
        if st.button(detail_button_label, type="secondary", use_container_width=True, key=f"detail_toggle_{symbol}"):
            detail_visible = not detail_visible
            st.session_state[detail_state_key] = detail_visible
            st.rerun()
        if not detail_visible:
            st.caption("Weitere fachliche Einordnung und technische Nachweise bleiben bis zum Öffnen bewusst ausgeblendet.")
            return

        st.divider()
        st.markdown("## Verständliche Detailanalyse")
        st.caption("Warum lautet die Empfehlung so? Die technische Berechnung folgt getrennt in der erweiterten Analyse.")

        all_research_modules = [*research_pack.modules, *research_pack.institutional_modules]
        fundamental_modules = modules_with_names(research_pack.modules, "fundamentaldaten", "krypto-netzwerk")
        future_modules = modules_with_names(research_pack.modules, "zukunftspotenzial")
        valuation_modules = modules_with_names(research_pack.modules, "bewertungsscore")
        expectation_modules = modules_with_names(research_pack.modules, "eingepreiste erwartungen")
        innovation_modules = modules_with_names(research_pack.modules, "innovation")
        risk_modules = modules_with_names(research_pack.modules, "risiko-score", "blasenrisiko")
        market_modules = modules_with_names(research_pack.modules, "marktregime")
        macro_modules = modules_with_names(research_pack.modules, "makro-wirkung", "makro-score")
        commodity_modules = modules_with_names(research_pack.modules, "rohstoff", "krypto-zyklus")
        news_modules = modules_with_names(research_pack.modules, "news-score", "geopolitik")
        event_modules = modules_with_names(research_pack.institutional_modules, "earnings", "event-risiko")
        institutional_modules = modules_with_names(research_pack.institutional_modules, "analyst", "institutionelle")
        top_chances = unique_text_items(
            [user_facing_detail_text(item) for item in list(research_pack.conclusion.get("Was spricht für Kauf?", []))],
            [user_facing_detail_text(module.summary) for module in user_relevant_modules([*future_modules, *innovation_modules])],
            limit=5,
        )
        risk_rows = recommendation_risk_rows(research_pack.decision)

        detail_labels = detail_analysis_tab_labels(portfolio_result.enabled)
        detail_tabs = st.tabs(detail_labels)
        thesis_tab, valuation_tab, entry_tab, chances_tab, risks_tab, scenarios_tab, market_tab = detail_tabs[:7]
        portfolio_tab = detail_tabs[7] if portfolio_result.enabled else None

        with thesis_tab:
            st.markdown("### Investmentthese")
            st.info(
                f"Kurzfazit: Langfristige Attraktivität {research_pack.decision.get('Langfristige Einschätzung')}. "
                "Diese Sicht bewertet Qualität und Zukunftspotenzial getrennt vom heutigen Preis und vom Einstiegstiming."
            )
            st.markdown("**Warum könnte das Investment langfristig funktionieren?**")
            for item in top_chances[:3] or ["Die vorhandenen Daten liefern derzeit keinen belastbaren positiven Langfristtreiber."]:
                st.write(f"- {item}")
            st.markdown("**Zentrale Annahme**")
            st.write(str(research_pack.decision.get("Zentrale Annahme")))
            st.markdown("**Was würde die These beschädigen?**")
            st.write(str(research_pack.decision.get("These beschädigt wenn")))

        with valuation_tab:
            st.markdown("### Preis und Bewertung")
            st.info(
                f"Kurzfazit: Der aktuelle Preis ist {str(research_pack.decision.get('Preisattraktivität')).lower()}. "
                "Der Kursabstand zum Hoch wird nur zusammen mit Bewertung, These und erwarteter Rendite beurteilt."
            )
            valuation_cols = st.columns(2)
            with valuation_cols[0]:
                render_text_card("Preisattraktivität", research_pack.decision.get("Preisattraktivität"))
            with valuation_cols[1]:
                render_text_card("Bewertungsdaten", research_pack.decision.get("Bewertungseinordnung"))
            st.markdown("**Abstand zum früheren Hoch**")
            st.write(str(research_pack.decision.get("Allzeithoch-Kontext")))
            st.markdown("**Fundamentaldaten beziehungsweise These seit dem Hoch**")
            st.write(str(research_pack.decision.get("Fundamentaldaten seit Hoch")))
            st.markdown("**Möglicher Grund für den Kursrückgang**")
            st.write(str(research_pack.decision.get("Grund für Kursrückgang")))
            st.markdown("**Wie passt die Bewertung zum Wachstum?**")
            st.write(str(research_pack.decision.get("Bewertung und Wachstum")))
            st.markdown("**Erwartete Rendite der Szenarien**")
            st.write(str(research_pack.decision.get("Szenario-Rendite")))
            st.markdown("**Welche Erwartungen sind bereits eingepreist?**")
            expectation_summaries = [user_facing_detail_text(module.summary) for module in user_relevant_modules(expectation_modules)]
            st.write(expectation_summaries[0] if expectation_summaries else "Daten nicht verfügbar; es wird keine Erwartung erfunden.")
            st.markdown("**Anfälligkeit für Enttäuschungen**")
            st.write(str(research_pack.decision.get("Enttäuschungsanfälligkeit")))
            st.caption("Einzelne Bewertungsmultiplikatoren stehen ausschließlich in der erweiterten Analyse.")

        with entry_tab:
            st.markdown("### Einstieg und Vorgehen")
            st.info(
                f"Kurzfazit: Timing {research_pack.decision.get('Aktuelles Timing')} · "
                f"Empfehlung {action_title}. Alle folgenden Wege verwenden dieselben zentralen Zonen wie die Hauptansicht."
            )
            st.write(f"**Jetzt:** {research_pack.decision.get('Handlung jetzt')}")
            st.write(f"**Rücksetzer-Kaufzone:** {research_pack.decision.get('Kaufzone')}")
            st.write(f"**Reihenfolge der Tranchen:** {research_pack.decision.get('Tranchierung')}")
            st.write(f"**Bei Rücksetzer:** {research_pack.decision.get('Handlung bei Rücksetzer')}")
            st.write(f"**Falls der Rücksetzer nicht kommt:** {research_pack.decision.get('Handlung bei weiterer Stärke')}")
            st.warning(f"**Widerlegungsmarke:** {research_pack.decision.get('Widerlegungsbedingung')}")
            st.caption(f"Gültigkeit: {research_pack.decision.get('Gültigkeit')}")
            chart_currency = "EUR" if fx_rate is not None else original_currency
            st.plotly_chart(
                render_price_chart(display_df, display_chart_supports, display_chart_resistances, chart_currency),
                use_container_width=True,
            )

        with chances_tab:
            st.markdown("### Chancen")
            st.info("Kurzfazit: Die wichtigsten Chancen sind nach ihrer Bedeutung für die langfristige These geordnet.")
            for index, item in enumerate(top_chances or ["Keine belastbare zentrale Chance verfügbar."], start=1):
                st.markdown(f"**{index}. {item}**")
            st.caption("Die Reihenfolge priorisiert die für die aktuelle Empfehlung verwendeten Langfrist- und Research-Treiber.")

        with risks_tab:
            st.markdown("### Risiken")
            st.info("Kurzfazit: Entscheidend sind die Risiken, die Preis, These oder Einstieg konkret widerlegen können.")
            if not risk_rows:
                st.info("Keine strukturierten zentralen Risiken verfügbar; neue Daten können die Einschätzung dennoch verändern.")
            for row in risk_rows:
                st.markdown(f"**{row['Risiko']}**")
                st.write(f"Relevanz: {row['Relevanz']}")
                st.caption(f"Erkennbar an: {row['Erkennbar an']}")

        with scenarios_tab:
            st.markdown("### Szenarien")
            st.info("Kurzfazit: Die Szenarien zeigen mögliche Bandbreiten und Auslöser; sie sind keine garantierten Kursziele.")
            for scenario in compact_scenario_rows(research_pack.scenarios):
                st.markdown(f"**{scenario['Szenario']} · {scenario['Wahrscheinlichkeit']}**")
                st.write(f"Notwendige Entwicklung: {scenario['Notwendige Entwicklung']}")
                st.write(f"Mögliche Folge: {scenario['Mögliche Folge']}")
                st.caption(f"Wichtigster Auslöser: {scenario['Wichtigster Auslöser']}")
            st.caption("Szenarien sind Bandbreiten, keine garantierten Kursziele.")

        with market_tab:
            st.markdown("### Markt und Umfeld")
            st.info("Kurzfazit: Angezeigt werden nur Markt-, Branchen-, Makro- und Nachrichtenfaktoren, die für dieses Asset relevant und verfügbar sind.")
            st.markdown("**Gesamtmarkt**")
            st.write(f"{market_phase.phase}: {market_phase.summary}")
            sector = str(ticker_info.get("sector") or "").strip()
            industry = str(ticker_info.get("industry") or "").strip()
            if sector or industry:
                st.markdown("**Branche**")
                st.write(" · ".join(item for item in [sector, industry] if item))
            for module in user_relevant_modules([*macro_modules, *news_modules]):
                st.markdown(f"**{module.name}**")
                st.write(user_facing_detail_text(module.summary))
            sector_context = f"{sector} {industry}".lower()
            commodity_relevant = asset_profile.asset_type == "Krypto" or any(
                marker in sector_context for marker in ["energy", "basic materials", "utilities", "industrial", "rohstoff"]
            )
            if commodity_relevant:
                for module in user_relevant_modules(commodity_modules):
                    st.markdown(f"**{module.name}**")
                    st.write(user_facing_detail_text(module.summary))
            st.caption("Leere oder für das Asset nicht relevante Proxy-Module werden in dieser Ebene nicht angezeigt.")

        if portfolio_tab is not None:
            with portfolio_tab:
                st.markdown("### Portfolio-Effekt")
                st.info("Kurzfazit: Der Depot-Effekt verändert weder die langfristige Attraktivität noch das kurzfristige Kaufsignal; er steuert nur das Portfoliorisiko.")
                if not portfolio_result.available:
                    st.warning(portfolio_result.summary)
                else:
                    st.write(portfolio_result.summary)
                    for detail in portfolio_result.details:
                        st.write(f"- {detail}")
                    st.caption(str(research_pack.decision.get("Positionsgröße")))

        with st.expander("Erweiterte Analyse", expanded=False):
            st.caption("Technische Parameter, Rohdaten und Modellinformationen zur Kontrolle und Nachvollziehbarkeit.")
            technical_tab, fundamental_tab, data_tab, methodology_tab, forecast_tab = st.tabs(advanced_analysis_tab_labels())

            with technical_tab:
                close_value = float(latest["Close"])
                technical_metrics = st.columns(4)
                rsi_value = latest_value(latest, "RSI_14")
                macd_value = latest_value(latest, "MACD")
                volatility_value = latest_value(latest, "Volatility")
                technical_metrics[0].metric("RSI 14", "n/a" if rsi_value is None else f"{rsi_value:.2f}")
                technical_metrics[1].metric("MACD", "n/a" if macd_value is None else f"{macd_value:.4f}")
                technical_metrics[2].metric("Volatilität", "n/a" if volatility_value is None else f"{volatility_value * 100:.1f}%")
                technical_metrics[3].metric("CRV", "n/a" if risk_reward.ratio is None else f"{risk_reward.ratio:.2f}")
                explanations = [
                    ("RSI 14", *rsi_explanation(rsi_value)),
                    ("MACD", *macd_explanation(macd_value, latest_value(latest, "MACD_Signal"))),
                    ("Gleitende Durchschnitte", *trend_explanation(close_value, latest_value(latest, "SMA_50"), latest_value(latest, "SMA_200"))),
                    ("Unterstützung und Widerstand", *level_explanation(close_value, supports, resistances, original_currency, fx_rate, currency_mode)),
                    ("Volatilität", *volatility_explanation(volatility_value)),
                ]
                for title, status, explanation in explanations:
                    render_analysis_card(title, status, explanation)
                st.markdown("**Technische Berechnungsdetails**")
                for name, points, text in score_result.breakdown:
                    st.write(f"- {name}: {points:g} Punkte · {text}")
                st.write(risk_reward.summary)
                st.dataframe(pd.DataFrame(research_pack.buy_zones), use_container_width=True, hide_index=True)
                with st.expander("Indikator-Charts und Kursrohdaten", expanded=False):
                    chart_cols = st.columns(2)
                    with chart_cols[0]:
                        rsi_fig = render_line_chart(chart_df, ["RSI_14"], "RSI 14")
                        rsi_fig.add_hline(y=70, line_dash="dot", line_color="#dc2626")
                        rsi_fig.add_hline(y=30, line_dash="dot", line_color="#16a34a")
                        st.plotly_chart(rsi_fig, use_container_width=True)
                    with chart_cols[1]:
                        st.plotly_chart(render_line_chart(chart_df, ["MACD", "MACD_Signal"], "MACD und Signal-Linie"), use_container_width=True)
                    st.plotly_chart(render_volume_chart(chart_df), use_container_width=True)
                    st.dataframe(df.tail(250), use_container_width=True)

            with fundamental_tab:
                if asset_profile.asset_type == "Aktie":
                    profitability_details = [
                        detail for detail in fundamentals.details
                        if any(marker in detail.lower() for marker in ["marge", "roe", "roa", "kapitalrendite", "profitabil"])
                    ]
                    balance_details = [
                        detail for detail in fundamentals.details
                        if any(marker in detail.lower() for marker in ["cash", "verschuld", "debt", "bilanz", "free cashflow"])
                    ]
                    render_module_expander("Umsatz, Wachstum und Qualität", [*fundamental_modules, *future_modules], beginner_mode=beginner_mode)
                    render_module_expander("Margen und Kapitalrendite", [], details=profitability_details)
                    render_module_expander("Cashflow, Bilanz und Verschuldung", [], details=balance_details)
                else:
                    render_module_expander("Asset-spezifische Fundamentaldaten", [*fundamental_modules, *future_modules], beginner_mode=beginner_mode)
                    render_module_expander("Zyklus, Struktur und Adoption", commodity_modules, beginner_mode=beginner_mode)
                render_module_expander("Bewertungsmultiplikatoren und Erwartungen", [*valuation_modules, *expectation_modules], beginner_mode=beginner_mode)
                render_module_expander("Analysten- und institutionelle Daten", [*institutional_modules, *event_modules], beginner_mode=beginner_mode)

            with data_tab:
                quality_score_text = "n/a" if research_pack.data_quality.score is None else f"{research_pack.data_quality.score:.1f}/10"
                quality_message = f"Datenqualität {quality_label} ({quality_score_text}): {quality_summary}"
                if quality_label == "Grün":
                    st.success(quality_message)
                elif quality_label == "Gelb":
                    st.warning(quality_message)
                else:
                    st.error(quality_message)
                st.write("**Wichtigste Hinweise:** " + " | ".join(quality_highlights))
                st.markdown("**Vorhandene, fehlende und eingeschränkte Daten**")
                for detail in [*research_pack.data_quality.details, *data_source_warnings, *research_pack.uncertainty_factors[:5]]:
                    st.write(f"- {detail}")

            with methodology_tab:
                st.write("Asset-Qualität, Kaufsignal und Depot-Effekt bleiben getrennte Bewertungen.")
                st.dataframe(pd.DataFrame(score_weight_rows(asset_profile)), use_container_width=True, hide_index=True)
                st.markdown("**Confidence-Berechnung**")
                st.write(research_pack.confidence.summary)
                for detail in research_pack.confidence.details:
                    st.write(f"- {detail}")
                module_rows = [
                    {
                        "Modul": module.name,
                        "Score": "n/a" if module.score is None else f"{module.score:.1f}/10",
                        "Einordnung": score_band(module.score, is_warning_score_module(module)),
                        "Kurzfazit": module.summary,
                    }
                    for module in all_research_modules
                ]
                st.dataframe(pd.DataFrame(module_rows), use_container_width=True, hide_index=True)
                st.caption(f"Logikversion: {FORECAST_LOGIC_VERSION}")

            with forecast_tab:
                st.markdown("**Frühere Prognosen und Richtungstrefferquote**")
                st.write(prediction_hit_status)
                st.dataframe(pd.DataFrame(prediction_hit_table), use_container_width=True, hide_index=True)
                with st.expander("Ähnliche historische Fälle", expanded=False):
                    st.write(similar_setup_status)
                    st.dataframe(pd.DataFrame(similar_setup_table), use_container_width=True, hide_index=True)
                with st.expander("Historien-, Lern- und Opportunitätskosten-Kontext", expanded=False):
                    st.write(local_history_quality_status)
                    st.dataframe(pd.DataFrame(local_history_quality_table), use_container_width=True, hide_index=True)
                    st.write(negative_cause_status)
                    st.dataframe(pd.DataFrame(negative_cause_table), use_container_width=True, hide_index=True)
                    st.write(calibration_status)
                    st.dataframe(pd.DataFrame(calibration_rows), use_container_width=True, hide_index=True)
                    st.write(signal_learning_status)
                    st.dataframe(pd.DataFrame(signal_learning_table), use_container_width=True, hide_index=True)
                with st.expander("Backtesting", expanded=False):
                    st.write(backtest_status)
                    st.dataframe(pd.DataFrame(backtest_compact_table), use_container_width=True, hide_index=True)
                    if st.button("Backtest-Ergebnis lokal speichern", use_container_width=True, key=f"save_backtest_{symbol}"):
                        backtest_record = build_backtest_record(
                            symbol,
                            asset_identity,
                            asset_profile,
                            backtest_status,
                            backtest_table,
                            analysis_history_label,
                        )
                        if save_backtest_result(backtest_record):
                            st.success("Backtest-Ergebnis lokal gespeichert. Es wurde keine Order ausgelöst.")
                        else:
                            st.error("Backtest-Ergebnis konnte nicht gespeichert werden.")
                with st.expander("Eigene Entscheidung dokumentieren", expanded=False):
                    decision_choice = st.selectbox(
                        "Was machst du mit dieser Analyse?",
                        [
                            "Keine Aktion",
                            "Jetzt kaufen",
                            "Erste Tranche kaufen",
                            "Bei Bestätigung kaufen",
                            "Auf konkrete Kaufzone warten",
                            "Halten",
                            "Teilweise reduzieren",
                            "Verkaufen oder vermeiden",
                        ],
                        index=0,
                        key=f"decision_choice_{symbol}",
                    )
                    decision_note = st.text_area("Optionaler Kommentar", value="", key=f"decision_note_{symbol}")
                    if st.button("Entscheidung speichern", use_container_width=True, key=f"save_decision_{symbol}"):
                        decision_record = build_decision_record(
                            symbol,
                            asset_identity,
                            asset_profile,
                            latest,
                            asset_quality,
                            buy_signal,
                            market_phase,
                            research_pack,
                            decision_choice,
                            decision_note,
                        )
                        if save_decision_record(decision_record):
                            st.success("Entscheidung lokal gespeichert. Es wurde keine Order ausgelöst.")
                        else:
                            st.error("Entscheidung konnte nicht gespeichert werden.")

        return

if __name__ == "__main__":
    main()
