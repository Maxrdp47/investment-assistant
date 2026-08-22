from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd


@dataclass(frozen=True)
class SwingTradeThresholds:
    """Central, versioned quality gates for the first swing-trading release."""

    filter_policy_version: str = "swing-filter-neutrality-2026.08.11-v1"
    min_history_rows: int = 200
    min_data_quality: float = 7.0
    min_relative_volume: float = 0.50
    min_average_turnover_eur_stock: float = 1_000_000.0
    min_average_turnover_eur_etf: float = 500_000.0
    min_average_turnover_eur_crypto: float = 5_000_000.0
    min_buy_signal: float = 5.8
    asset_quality_role: str = "diagnostic_not_hard_gate"
    min_confidence: float = 5.8
    min_market_score: float = 4.0
    min_crv: float = 2.0
    min_historical_cases: int = 20
    min_expected_value_r: float = 0.0
    pullback_touch_tolerance_pct: float = 1.5
    pullback_max_extension_pct: float = 4.0
    pullback_touch_atr_multiple: float = 0.75
    pullback_extension_atr_multiple: float = 1.50
    min_pullback_touch_pct: float = 0.35
    min_pullback_extension_pct: float = 1.00
    breakout_buffer_pct: float = 0.10
    breakout_max_extension_pct: float = 2.5
    breakout_extension_atr_multiple: float = 0.75
    min_breakout_extension_pct: float = 0.50
    breakout_min_volume_ratio: float = 1.20
    stop_buffer_pct: float = 1.0
    validity_days: int = 7
    event_block_days: int = 3
    event_warning_days: int = 14
    max_target_distance_pct: float = 18.0
    max_stop_distance_pct_stock: float = 8.0
    max_stop_distance_pct_etf: float = 7.0
    max_stop_distance_pct_crypto: float = 12.0
    min_stop_distance_pct_stock: float = 0.50
    min_stop_distance_pct_etf: float = 0.35
    min_stop_distance_pct_crypto: float = 1.00


DEFAULT_SWING_THRESHOLDS = SwingTradeThresholds()
SWING_ORDER_PLAN_VERSION = "swing-order-plan-2026.08.11-v3"
SWING_STOP_CONTRACT_VERSION = "swing-stop-2026.08.09-v1"
SWING_EXECUTION_COST_VERSION = "swing-paper-costs-2026.08.09-v1"


def thresholds_as_dict(thresholds: SwingTradeThresholds = DEFAULT_SWING_THRESHOLDS) -> dict:
    return asdict(thresholds)


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def swing_order_plan_fingerprint(order_plan: dict) -> str:
    payload = dict(order_plan)
    payload.pop("plan_fingerprint", None)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _latest_value(row: pd.Series, name: str) -> float | None:
    return _number(row.get(name))


def _ensure_indicators(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    close = frame["Close"].astype(float)
    if "SMA_50" not in frame:
        frame["SMA_50"] = close.rolling(50).mean()
    if "SMA_200" not in frame:
        frame["SMA_200"] = close.rolling(200).mean()
    if "MACD" not in frame:
        frame["MACD"] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    if "MACD_Signal" not in frame:
        frame["MACD_Signal"] = frame["MACD"].ewm(span=9, adjust=False).mean()
    if "RSI_14" not in frame:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        average_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        average_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        relative_strength = average_gain / average_loss.replace(0, pd.NA)
        frame["RSI_14"] = 100 - (100 / (1 + relative_strength))
    if "Volume_SMA_20" not in frame:
        frame["Volume_SMA_20"] = (
            frame["Volume"].astype(float).rolling(20).mean() if "Volume" in frame else float("nan")
        )
    if "ATR_14" not in frame and {"High", "Low"}.issubset(frame.columns):
        high = frame["High"].astype(float)
        low = frame["Low"].astype(float)
        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        frame["ATR_14"] = true_range.rolling(14).mean()
    return frame


def data_quality_score(data: pd.DataFrame) -> float:
    if data.empty or "Close" not in data:
        return 0.0
    score = 0.0
    row_count = len(data.dropna(subset=["Close"]))
    score += 4.0 if row_count >= 200 else 2.5 if row_count >= 120 else 1.0 if row_count >= 60 else 0.0
    required_prices = [column for column in ["Open", "High", "Low", "Close"] if column in data]
    score += len(required_prices) / 4 * 2.0
    latest = data.iloc[-1]
    indicators = ["SMA_50", "SMA_200", "MACD", "MACD_Signal"]
    score += sum(_latest_value(latest, column) is not None for column in indicators) / len(indicators) * 2.0
    volume = _latest_value(latest, "Volume")
    volume_average = _latest_value(latest, "Volume_SMA_20")
    if volume is not None and volume_average is not None and volume_average > 0:
        score += 2.0
    return round(min(score, 10.0), 1)


def long_trade_metrics(entry: float, stop: float, target: float) -> dict:
    entry_value = _number(entry)
    stop_value = _number(stop)
    target_value = _number(target)
    if entry_value is None or stop_value is None or target_value is None:
        raise ValueError("Einstieg, Stop und Ziel müssen als Zahlen vorliegen.")
    if not 0 < stop_value < entry_value < target_value:
        raise ValueError("Für Long-Trades muss gelten: 0 < Stop < Einstieg < Kursziel.")
    risk = entry_value - stop_value
    chance = target_value - entry_value
    return {
        "entry": entry_value,
        "stop": stop_value,
        "target": target_value,
        "risk": risk,
        "chance": chance,
        "risk_pct": risk / entry_value * 100,
        "chance_pct": chance / entry_value * 100,
        "crv": chance / risk,
    }


def validate_traded_listing(
    traded_identifier: str,
    *,
    expected_symbol: str,
    expected_isin: str | None = None,
) -> tuple[bool, str]:
    """Prevent a user trade from silently being attached to another listing."""
    entered = "".join(str(traded_identifier or "").upper().split())
    allowed = {
        "".join(str(value or "").upper().split())
        for value in (expected_symbol, expected_isin)
        if str(value or "").strip()
    }
    if not entered:
        return False, "Ticker oder ISIN des tatsächlich gehandelten Listings fehlt."
    if entered not in allowed:
        expected = " oder ".join(sorted(allowed)) or "das analysierte Listing"
        return (
            False,
            f"Anderes oder nicht verifiziertes Listing: analysiert wurde {expected}, angegeben wurde {entered}. "
            "Kurs, Einstieg, Stop und Ziele dürfen nicht zwischen Listings übernommen werden.",
        )
    return True, "Listing stimmt mit dem analysierten Instrument überein."


def _next_entry_day(signal_day: date, asset_type: str) -> date:
    if asset_type == "Krypto":
        return signal_day + timedelta(days=1)
    return (pd.Timestamp(signal_day) + pd.offsets.BDay(1)).date()


def _regional_market_clock(region: str | None) -> tuple[ZoneInfo, time] | None:
    normalized_region = str(region or "")
    if normalized_region in {"USA", "Nordamerika", "Südamerika", "Global"}:
        return ZoneInfo("America/New_York"), time(16, 15)
    if normalized_region in {"Asien", "Australien"}:
        return ZoneInfo("Asia/Hong_Kong"), time(16, 15)
    if normalized_region == "Europa":
        return ZoneInfo("Europe/Berlin"), time(17, 45)
    return None


def _market_clock_for_symbol(symbol: str, region: str | None) -> tuple[ZoneInfo, time] | None:
    """Return a conservative clock for the listing, falling back to its region."""
    normalized = str(symbol or "").upper()
    suffix_clocks = {
        ".NS": ("Asia/Kolkata", time(15, 45)),
        ".BO": ("Asia/Kolkata", time(15, 45)),
        ".HK": ("Asia/Hong_Kong", time(16, 15)),
        ".T": ("Asia/Tokyo", time(15, 45)),
        ".AX": ("Australia/Sydney", time(16, 15)),
    }
    for suffix, (zone, close) in suffix_clocks.items():
        if normalized.endswith(suffix):
            return ZoneInfo(zone), close
    return _regional_market_clock(region)


def expected_latest_completed_session_day(
    evaluated_at: datetime,
    *,
    asset_type: str,
    region: str | None,
    symbol: str = "",
) -> date:
    """Return the newest daily bar a trustworthy feed should already contain."""
    aware = evaluated_at if evaluated_at.tzinfo is not None else evaluated_at.astimezone()
    if asset_type == "Krypto":
        candidate = aware.astimezone(ZoneInfo("UTC")).date() - timedelta(days=1)
    else:
        market_clock = _market_clock_for_symbol(symbol, region)
        if market_clock is None:
            local = aware
            candidate = local.date() if local.time() >= time(18, 0) else local.date() - timedelta(days=1)
        else:
            market_zone, conservative_close = market_clock
            local = aware.astimezone(market_zone)
            candidate = local.date() if local.time() >= conservative_close else local.date() - timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
    return candidate


def validate_daily_market_bar(
    frame: pd.DataFrame,
    signal_bar_day: date,
    evaluated_at: datetime,
    *,
    asset_type: str,
    region: str | None,
    symbol: str,
) -> list[str]:
    """Reject stale or internally contradictory OHLC data before trade math."""
    reasons: list[str] = []
    expected_day = expected_latest_completed_session_day(
        evaluated_at,
        asset_type=asset_type,
        region=region,
        symbol=symbol,
    )
    if signal_bar_day < expected_day:
        reasons.append(
            "Kursdaten nicht ausreichend aktuell: Die letzte Tageskerze ist vom "
            f"{signal_bar_day.isoformat()}, erwartet wird mindestens {expected_day.isoformat()}. "
            "Der Trade ist nicht handelbar bestätigt."
        )

    latest = frame.iloc[-1]
    prices = {name: _number(latest.get(name)) for name in ("Open", "High", "Low", "Close")}
    if any(value is None or value <= 0 for value in prices.values()):
        reasons.append("Kursdaten nicht ausreichend verlässlich: Die letzte Tageskerze enthält ungültige OHLC-Werte.")
    else:
        low, high = prices["Low"], prices["High"]
        if low > high or not low <= prices["Open"] <= high or not low <= prices["Close"] <= high:
            reasons.append(
                "Kursdaten nicht ausreichend verlässlich: Open oder Schlusskurs widersprechen Tageshoch/-tief. "
                "Der Trade ist nicht handelbar bestätigt."
            )
    return reasons


def _first_actionable_entry_day(
    signal_bar_day: date,
    evaluated_at: datetime,
    *,
    asset_type: str,
    region: str | None,
) -> date:
    earliest = _next_entry_day(signal_bar_day, asset_type)
    aware_evaluation = evaluated_at if evaluated_at.tzinfo is not None else evaluated_at.astimezone()
    if asset_type == "Krypto":
        observed_utc_day = aware_evaluation.astimezone(ZoneInfo("UTC")).date()
        return max(earliest, observed_utc_day)
    market_clock = _regional_market_clock(region)
    if market_clock is None:
        observed_day = aware_evaluation.date()
        return earliest if earliest >= observed_day else _next_entry_day(observed_day, asset_type)
    market_zone, conservative_close = market_clock
    local_evaluation = aware_evaluation.astimezone(market_zone)
    if local_evaluation.date() < earliest:
        return earliest
    is_business_day = local_evaluation.weekday() < 5
    if is_business_day and local_evaluation.time() < conservative_close:
        return local_evaluation.date()
    return _next_entry_day(local_evaluation.date(), asset_type)


def completed_daily_signal_bar(
    signal_bar_day: date,
    evaluated_at: datetime,
    *,
    asset_type: str,
    region: str | None,
    symbol: str = "",
) -> bool:
    local_evaluation = evaluated_at if evaluated_at.tzinfo is not None else evaluated_at.astimezone()
    if asset_type == "Krypto":
        local_evaluation = local_evaluation.astimezone(ZoneInfo("UTC"))
    else:
        market_clock = _market_clock_for_symbol(symbol, region)
        if market_clock is not None:
            local_evaluation = local_evaluation.astimezone(market_clock[0])
    if signal_bar_day < local_evaluation.date():
        return True
    if signal_bar_day > local_evaluation.date() or asset_type == "Krypto":
        return False
    market_clock = _market_clock_for_symbol(symbol, region)
    if market_clock is None:
        return False
    market_zone, conservative_close = market_clock
    close_timestamp = datetime.combine(signal_bar_day, conservative_close, tzinfo=market_zone)
    return local_evaluation.astimezone(ZoneInfo("UTC")) >= close_timestamp.astimezone(ZoneInfo("UTC"))


def swing_execution_cost_contract(asset_type: str) -> dict:
    if asset_type == "Krypto":
        spread_bps, slippage_bps, fee_bps = 10.0, 10.0, 5.0
    elif asset_type == "ETF":
        spread_bps, slippage_bps, fee_bps = 2.0, 4.0, 1.0
    else:
        spread_bps, slippage_bps, fee_bps = 3.0, 5.0, 1.0
    return {
        "version": SWING_EXECUTION_COST_VERSION,
        "spread_bps_one_way": spread_bps,
        "slippage_bps_one_way": slippage_bps,
        "fee_bps_one_way": fee_bps,
        "policy": "Konservative Paper-Annahme; kein Brokerpreis und keine garantierte Ausführung.",
    }


def build_swing_order_plan(
    candidate: dict,
    *,
    asset_type: str,
    original_currency: str,
    fx_rate_to_eur: float,
    analysis_reference_price_original: float,
    analysis_price_source: str,
    analysis_reference_observed_at: str,
    evaluated_at: datetime,
    signal_bar_day: date,
    valid_until: str,
    region: str | None,
) -> dict:
    conversion = _number(fx_rate_to_eur)
    if conversion is None or conversion <= 0:
        raise ValueError("Für den Swing-Orderplan fehlt ein gültiger FX-Snapshot.")
    analysis_reference = _number(analysis_reference_price_original)
    if analysis_reference is None or analysis_reference <= 0:
        raise ValueError("Fuer den Swing-Orderplan fehlt der Referenzkurs der technischen Analyse.")
    required = ("entry_reference", "entry_low", "max_entry", "stop", "target_1", "invalidation")
    values = {name: _number(candidate.get(name)) for name in required}
    if any(values[name] is None or float(values[name]) <= 0 for name in required):
        raise ValueError("Der Swing-Orderplan besitzt nicht alle erforderlichen Kursmarken.")
    entry = float(values["entry_reference"])
    stop = float(values["stop"])
    target = float(values["target_1"])
    long_trade_metrics(entry, stop, target)
    earliest_entry_day = _first_actionable_entry_day(
        signal_bar_day,
        evaluated_at,
        asset_type=asset_type,
        region=region,
    )
    is_breakout = "Ausbruch" in str(candidate.get("setup_type") or "")
    entry_method = "Schlusskursbestätigung" if is_breakout else "Pullback-Limit"
    order_type = (
        "Limitorder nach Schlusskursbestätigung"
        if is_breakout
        else "Limitorder nach bestätigtem Pullback"
    )
    payload = {
        "plan_version": SWING_ORDER_PLAN_VERSION,
        "stop_contract_version": SWING_STOP_CONTRACT_VERSION,
        "status": "ready_after_completed_daily_signal",
        "direction": "Long",
        "entry_method": entry_method,
        "order_type": order_type,
        "activation_type": "Abgeschlossene Tageskerze",
        "activation_price_original": float(values["entry_low"]),
        "limit_price_original": entry,
        "maximum_entry_original": float(values["max_entry"]),
        "initial_stop_original": stop,
        "target_1_original": target,
        "target_2_original": _number(candidate.get("target_2")),
        "target_1_exit_fraction": 0.5 if _number(candidate.get("target_2")) is not None else 1.0,
        "target_2_exit_fraction": 0.5 if _number(candidate.get("target_2")) is not None else 0.0,
        "invalidation_original": float(values["invalidation"]),
        "original_currency": str(original_currency).upper(),
        "fx_snapshot": {
            "rate_to_eur": conversion,
            "observed_at": evaluated_at.isoformat(),
            "source_policy": "Beim Scan verwendeter Wechselkurs; nachträgliche FX-Werte überschreiben diesen Snapshot nicht.",
        },
        "analysis_reference_price_original": analysis_reference,
        "analysis_reference_price_eur": analysis_reference * conversion,
        "analysis_price_source": str(analysis_price_source),
        "analysis_reference_observed_at": str(analysis_reference_observed_at),
        "analysis_price_policy": (
            "Dieser Kurs ist ausschliesslich die Referenz der technischen Analyse. "
            "Er ist kein Trade-Republic-Ausfuehrungskurs."
        ),
        "limit_price_eur": entry * conversion,
        "activation_price_eur": float(values["entry_low"]) * conversion,
        "maximum_entry_eur": float(values["max_entry"]) * conversion,
        "initial_stop_eur": stop * conversion,
        "target_1_eur": target * conversion,
        "target_2_eur": (
            float(candidate["target_2"]) * conversion
            if _number(candidate.get("target_2")) is not None
            else None
        ),
        "invalidation_eur": float(values["invalidation"]) * conversion,
        "signal_bar_day": signal_bar_day.isoformat(),
        "earliest_entry_day": earliest_entry_day.isoformat(),
        "valid_until": str(valid_until),
        "execution_policy": (
            "Erst in einer späteren Handelssitzung und nur bis zum Maximalpreis; "
            "kein rückwirkender Kauf zum bestätigenden Schlusskurs."
        ),
        "stop_policy": "Der initiale Stop bleibt unveränderbar; ein aktiver Stop darf nur angehoben, niemals erweitert werden.",
        "delete_conditions": [
            "Signalkerze oder spätere Struktur berührt vor Einstieg die Widerlegungsmarke.",
            "Erste handelbare Notierung liegt oberhalb des Maximalpreises.",
            f"Keine Ausführung bis einschließlich {valid_until}.",
        ],
        "automatic_order_execution": False,
        "execution_cost_contract": swing_execution_cost_contract(asset_type),
    }
    payload["plan_fingerprint"] = swing_order_plan_fingerprint(payload)
    return payload


def finalize_swing_order_plan(order_plan: dict, position_size: dict) -> dict:
    """Attach the capital-dependent values and fingerprint the final user-visible plan."""
    if not isinstance(order_plan, dict) or not order_plan:
        raise ValueError("Der Swing-Orderplan fehlt.")
    finalized = dict(order_plan)
    finalized.pop("plan_fingerprint", None)
    full_gain_1 = _number(position_size.get("potential_gain_1_eur"))
    full_gain_2 = _number(position_size.get("potential_gain_2_eur"))
    target_1_fraction = _number(finalized.get("target_1_exit_fraction")) or 1.0
    target_2_fraction = _number(finalized.get("target_2_exit_fraction")) or 0.0
    planned_gain_1 = full_gain_1 * target_1_fraction if full_gain_1 is not None else None
    planned_gain_2 = (
        planned_gain_1 + full_gain_2 * target_2_fraction
        if planned_gain_1 is not None and full_gain_2 is not None and target_2_fraction > 0
        else None
    )
    finalized.update(
        {
            "quantity": _number(position_size.get("quantity")),
            "capital_committed_eur": _number(position_size.get("position_value_eur")),
            "planned_loss_eur": _number(position_size.get("actual_risk_eur")),
            "possible_gain_1_eur": planned_gain_1,
            "possible_gain_2_eur": planned_gain_2,
            "full_position_gain_at_target_1_eur": full_gain_1,
            "full_position_gain_at_target_2_eur": full_gain_2,
            "gain_policy": (
                "Ziel 1 ist der geplante Teilgewinn; Ziel 2 ist der kumulierte Gewinn aus beiden 50/50-Ausstiegen."
                if target_2_fraction > 0
                else "Ohne zweites Ziel entspricht Ziel 1 einem vollständigen Paper-Ausstieg."
            ),
            "position_calculated": _number(position_size.get("quantity")) is not None,
            "position_note": str(position_size.get("explanation") or ""),
        }
    )
    finalized["plan_fingerprint"] = swing_order_plan_fingerprint(finalized)
    return finalized


def assess_swing_order_plan(order_plan: dict, bar: dict, observed_day: date) -> dict:
    """Conservatively evaluate a future daily bar without sending or simulating a broker order."""
    try:
        earliest = date.fromisoformat(str(order_plan["earliest_entry_day"]))
        valid_until = date.fromisoformat(str(order_plan["valid_until"]))
    except (KeyError, TypeError, ValueError):
        return {"status": "not_evaluable", "reason": "Orderplan-Datum ungültig."}
    if observed_day < earliest:
        return {"status": "pending", "reason": "Frühester Einstiegstag ist noch nicht erreicht."}
    if observed_day > valid_until:
        return {"status": "expired", "reason": "Orderplan ist ohne Ausführung abgelaufen."}
    open_price = _number(bar.get("Open"))
    low = _number(bar.get("Low"))
    high = _number(bar.get("High"))
    if open_price is None or low is None or high is None:
        return {"status": "not_evaluable", "reason": "Tagesbalken ist unvollständig."}
    maximum = _number(order_plan.get("maximum_entry_original"))
    limit_price = _number(order_plan.get("limit_price_original"))
    invalidation = _number(order_plan.get("invalidation_original"))
    if maximum is None or limit_price is None or invalidation is None:
        return {"status": "not_evaluable", "reason": "Orderplan-Marken fehlen."}
    if open_price > maximum:
        return {"status": "missed", "reason": "Eröffnungskurs liegt über dem Maximalpreis."}
    if low <= invalidation:
        return {
            "status": "cancelled",
            "reason": "Widerlegungsmarke wurde berührt; bei unbekannter Intraday-Reihenfolge wird keine Ausführung behauptet.",
        }
    if low <= limit_price <= high or open_price <= limit_price:
        fill_price = min(open_price, limit_price) if open_price <= limit_price else limit_price
        return {
            "status": "would_fill",
            "reason": "Limitpreis wurde innerhalb des vollständigen Tagesbalkens erreicht.",
            "paper_entry_original": fill_price,
            "broker_order_sent": False,
        }
    return {"status": "pending", "reason": "Limitpreis wurde noch nicht erreicht."}


def tighten_active_trade_stop(
    record: dict,
    new_stop_eur: float,
    updated_at: object = None,
) -> tuple[dict | None, str | None]:
    if str(record.get("Status")) != "Aktiv":
        return None, "Nur bei einem aktiven Trade kann der Stop angepasst werden."
    new_stop = _number(new_stop_eur)
    current_stop = _number(
        record.get("Aktueller Stop EUR")
        or record.get("Initialer Stop EUR")
        or record.get("Stop-Loss EUR")
        or record.get("stop_eur")
    )
    if new_stop is None or new_stop <= 0 or current_stop is None or current_stop <= 0:
        return None, "Aktueller und neuer Stop müssen größer als null sein."
    if new_stop < current_stop:
        return None, "Der Stop darf bei einem Long-Trade nur angehoben und niemals erweitert werden."
    if math.isclose(new_stop, current_stop, rel_tol=0.0, abs_tol=1e-12):
        return None, "Der neue Stop entspricht bereits dem aktuellen Stop."
    updated = dict(record)
    updated.setdefault("Initialer Stop EUR", current_stop)
    updated.setdefault("Stop-Vertrag Version", SWING_STOP_CONTRACT_VERSION)
    updated["Aktueller Stop EUR"] = new_stop
    updated["Letzte Aktualisierung"] = pd.Timestamp(
        updated_at or datetime.now().astimezone()
    ).isoformat()
    return updated, None


def expected_value_in_r(crv: float, hit_rate_pct: float) -> float:
    ratio = _number(crv)
    probability = _number(hit_rate_pct)
    if ratio is None or ratio <= 0 or probability is None or not 0 <= probability <= 100:
        raise ValueError("CRV und Trefferquote sind ungültig.")
    p = probability / 100
    return p * ratio - (1 - p)


def _turnover_threshold(asset_type: str, thresholds: SwingTradeThresholds) -> float:
    if asset_type == "ETF":
        return thresholds.min_average_turnover_eur_etf
    if asset_type == "Krypto":
        return thresholds.min_average_turnover_eur_crypto
    return thresholds.min_average_turnover_eur_stock


def _event_days(event_date: object, now: datetime) -> int | None:
    if event_date is None:
        return None
    try:
        timestamp = pd.Timestamp(event_date)
    except Exception:
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return (timestamp.date() - now.date()).days


def _event_day_iso(event_date: object) -> str | None:
    if event_date is None:
        return None
    try:
        timestamp = pd.Timestamp(event_date)
    except Exception:
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp.date().isoformat()


def _unique_levels(levels: Iterable[float], minimum: float, maximum: float | None = None) -> list[float]:
    values: list[float] = []
    for raw_value in levels:
        value = _number(raw_value)
        if value is None or value <= minimum or (maximum is not None and value > maximum):
            continue
        if any(abs(value - existing) / existing < 0.004 for existing in values):
            continue
        values.append(value)
    return sorted(values)


def _swing_extrema(series: pd.Series, mode: str, window: int = 3) -> list[float]:
    clean = series.dropna().astype(float)
    if len(clean) < window * 2 + 1:
        return []
    rolling = clean.rolling(window * 2 + 1, center=True)
    extrema = rolling.min() if mode == "low" else rolling.max()
    return clean[clean.eq(extrema)].tolist()


def _common_rejections(
    frame: pd.DataFrame,
    asset_type: str,
    fx_rate: float | None,
    buy_signal: float,
    asset_quality: float,
    confidence: float,
    market_score: float,
    event_date: object,
    now: datetime,
    thresholds: SwingTradeThresholds,
) -> tuple[list[str], list[str], dict]:
    latest = frame.iloc[-1]
    close = _latest_value(latest, "Close") or 0.0
    volume = _latest_value(latest, "Volume")
    volume_average = _latest_value(latest, "Volume_SMA_20")
    relative_volume = volume / volume_average if volume is not None and volume_average and volume_average > 0 else None
    average_turnover_eur = (
        close * volume_average * fx_rate
        if close > 0 and volume_average is not None and volume_average > 0 and fx_rate is not None and fx_rate > 0
        else None
    )
    quality = data_quality_score(frame)
    event_days = _event_days(event_date, now)
    rejections: list[str] = []
    rejection_filters: list[str] = []
    if asset_type not in {"Aktie", "ETF", "Krypto"}:
        rejections.append("Asset-Typ ist für Swing-Trading v1 nicht freigegeben.")
        rejection_filters.append("unsupported_asset_type")
    if quality < thresholds.min_data_quality:
        rejections.append(f"Datenqualität {quality:.1f}/10 liegt unter {thresholds.min_data_quality:.1f}/10.")
        rejection_filters.append("data_quality")
    if fx_rate is None or fx_rate <= 0:
        rejections.append("Keine belastbare Umrechnung des aktuellen Kurses in Euro verfügbar.")
        rejection_filters.append("fx")
    if relative_volume is None or relative_volume < thresholds.min_relative_volume:
        rejections.append("Aktuelles Volumen ist für einen belastbaren Einstieg zu schwach oder nicht verfügbar.")
        rejection_filters.append("relative_volume")
    minimum_turnover = _turnover_threshold(asset_type, thresholds)
    if average_turnover_eur is None or average_turnover_eur < minimum_turnover:
        rejections.append("Durchschnittliche Handelbarkeit liegt unter dem zentralen Liquiditätsminimum.")
        rejection_filters.append("turnover_liquidity")
    if buy_signal < thresholds.min_buy_signal:
        rejections.append(f"Kaufsignal {buy_signal:.1f}/10 liegt unter {thresholds.min_buy_signal:.1f}/10.")
        rejection_filters.append("buy_signal")
    if confidence < thresholds.min_confidence:
        rejections.append(f"Confidence {confidence:.1f}/10 liegt unter {thresholds.min_confidence:.1f}/10.")
        rejection_filters.append("confidence")
    if market_score < thresholds.min_market_score:
        rejections.append("Das aktuelle Marktumfeld ist für einen neuen Long-Trade zu belastend.")
        rejection_filters.append("market")
    if event_days is not None and 0 <= event_days <= thresholds.event_block_days:
        rejections.append(f"Hohes Ereignisrisiko in {event_days} Tagen liegt zu nah am geplanten Einstieg.")
        rejection_filters.append("event")
    return rejections, rejection_filters, {
        "data_quality": quality,
        "relative_volume": relative_volume,
        "average_turnover_eur": average_turnover_eur,
        "event_days": event_days,
        "buy_signal": buy_signal,
        "asset_quality": asset_quality,
        "confidence": confidence,
        "asset_quality_role": thresholds.asset_quality_role,
        "asset_quality_hard_gate": False,
    }


def _adaptive_setup_bands(frame: pd.DataFrame, thresholds: SwingTradeThresholds) -> dict[str, float]:
    latest = frame.iloc[-1]
    close = _latest_value(latest, "Close") or 0.0
    atr = _latest_value(latest, "ATR_14")
    atr_pct = atr / close * 100 if atr is not None and atr > 0 and close > 0 else None
    if atr_pct is None:
        atr_pct = thresholds.min_pullback_extension_pct / thresholds.pullback_extension_atr_multiple
    return {
        "atr_pct": atr_pct,
        "pullback_touch_pct": min(
            thresholds.pullback_touch_tolerance_pct,
            max(thresholds.min_pullback_touch_pct, atr_pct * thresholds.pullback_touch_atr_multiple),
        ),
        "pullback_extension_pct": min(
            thresholds.pullback_max_extension_pct,
            max(
                thresholds.min_pullback_extension_pct,
                atr_pct * thresholds.pullback_extension_atr_multiple,
            ),
        ),
        "breakout_extension_pct": min(
            thresholds.breakout_max_extension_pct,
            max(
                thresholds.min_breakout_extension_pct,
                atr_pct * thresholds.breakout_extension_atr_multiple,
            ),
        ),
    }


def _pullback_candidate(
    frame: pd.DataFrame,
    thresholds: SwingTradeThresholds,
) -> tuple[dict | None, list[str]]:
    latest = frame.iloc[-1]
    adaptive_bands = _adaptive_setup_bands(frame, thresholds)
    previous = frame.iloc[-2]
    close = _latest_value(latest, "Close")
    sma_50 = _latest_value(latest, "SMA_50")
    sma_200 = _latest_value(latest, "SMA_200")
    rsi = _latest_value(latest, "RSI_14")
    if close is None or sma_50 is None or sma_200 is None:
        return None, ["Rücksetzer: Trenddurchschnitte sind nicht vollständig verfügbar."]
    if not (sma_50 > sma_200 and close > sma_200):
        return None, ["Rücksetzer: Kein intakter Aufwärtstrend mit SMA 50 über SMA 200."]
    recent_closes = frame["Close"].tail(2).astype(float)
    if len(recent_closes) == 2 and all(recent_closes < sma_50 * (1 - thresholds.stop_buffer_pct / 100)):
        return None, ["Rücksetzer: Die 50-Tage-Unterstützung wurde bereits vor dem Einstieg auf Tagesschlussbasis gebrochen."]
    if rsi is not None and rsi > 72:
        return None, ["Rücksetzer: RSI über 72 widerspricht einem unverbrauchten Rücksetzer-Einstieg."]

    recent_lows = _swing_extrema(frame["Low"].tail(120), "low") if "Low" in frame else []
    supports = [sma_50, *recent_lows]
    supports = [value for value in supports if value <= close and value >= close * 0.92]
    if not supports:
        return None, ["Rücksetzer: Keine nahe strukturelle Unterstützung erkennbar."]
    support = max(supports)
    recent = frame.tail(7)
    recent_low = float(recent["Low"].min()) if "Low" in recent else float(recent["Close"].min())
    touch_limit = support * (1 + adaptive_bands["pullback_touch_pct"] / 100)
    if recent_low > touch_limit:
        return None, ["Rücksetzer: Der erforderliche Test der Unterstützungszone fehlt."]

    previous_high = _latest_value(previous, "High") or _latest_value(previous, "Close") or support
    required_close = max(previous_high, support * 1.003)
    max_entry = support * (1 + adaptive_bands["pullback_extension_pct"] / 100)
    if close < required_close:
        return None, [f"Rücksetzer: Bestätigung fehlt; Tagesschluss muss mindestens {required_close:.4f} erreichen."]
    if close > max_entry:
        return None, [f"Rücksetzer: Einstieg ist oberhalb {max_entry:.4f} bereits verpasst."]

    atr = _latest_value(latest, "ATR_14") or support * thresholds.stop_buffer_pct / 100
    structure_floor = min(support, recent_low)
    stop_buffer = max(structure_floor * thresholds.stop_buffer_pct / 100, atr * 0.50)
    stop = structure_floor - stop_buffer
    historical_highs = _swing_extrema(frame["High"].iloc[:-1].tail(180), "high") if "High" in frame else []
    targets = _unique_levels(historical_highs, close * 1.015, close * (1 + thresholds.max_target_distance_pct / 100))
    if not targets:
        return None, ["Rücksetzer: Kein realistisches strukturelles Kursziel oberhalb des Einstiegs vorhanden."]
    target_1 = targets[0]
    target_2 = targets[1] if len(targets) > 1 else None
    return {
        "setup_type": "Rücksetzer im intakten Aufwärtstrend",
        "entry_reference": close,
        "entry_low": required_close,
        "entry_high": max_entry,
        "entry_condition": (
            f"Einstieg nur nach Tagesschluss bei mindestens {required_close:.4f}; "
            f"der Test der Unterstützung bei {support:.4f} ist erfolgt."
        ),
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "max_entry": max_entry,
        "invalidation": support * (1 - thresholds.stop_buffer_pct / 100),
        "structure_level": support,
        "confirmation": "Unterstützungstest plus Tagesschluss über dem Hoch des vorherigen Tages",
        "stop_reason": (
            f"Der Stop liegt unter der getesteten Unterstützung {support:.4f} und dem jüngsten Strukturtief "
            f"mit einem Volatilitätspuffer von {stop_buffer:.4f}."
        ),
        "technical_normalization": adaptive_bands,
    }, []


def _breakout_candidate(
    frame: pd.DataFrame,
    thresholds: SwingTradeThresholds,
) -> tuple[dict | None, list[str]]:
    latest = frame.iloc[-1]
    adaptive_bands = _adaptive_setup_bands(frame, thresholds)
    close = _latest_value(latest, "Close")
    sma_50 = _latest_value(latest, "SMA_50")
    sma_200 = _latest_value(latest, "SMA_200")
    macd = _latest_value(latest, "MACD")
    macd_signal = _latest_value(latest, "MACD_Signal")
    volume = _latest_value(latest, "Volume")
    volume_average = _latest_value(latest, "Volume_SMA_20")
    if close is None or len(frame) < 22 or "High" not in frame or "Low" not in frame:
        return None, ["Ausbruch: Zu wenig Kursstruktur für ein bestätigtes Ausbruchsniveau."]

    prior_range = frame.iloc[-21:-1]
    breakout_level = float(prior_range["High"].max())
    required_close = breakout_level * (1 + thresholds.breakout_buffer_pct / 100)
    max_entry = breakout_level * (1 + adaptive_bands["breakout_extension_pct"] / 100)
    if close < required_close:
        return None, [f"Ausbruch: Noch kein Tagesschluss über {required_close:.4f}."]
    if close > max_entry:
        return None, [f"Ausbruch: Einstieg ist oberhalb {max_entry:.4f} bereits verpasst."]

    volume_ratio = volume / volume_average if volume is not None and volume_average and volume_average > 0 else None
    volume_confirmation = volume_ratio is not None and volume_ratio >= thresholds.breakout_min_volume_ratio
    trend_confirmation = (
        sma_50 is not None
        and sma_200 is not None
        and sma_50 > sma_200
        and close > sma_50
        and macd is not None
        and macd_signal is not None
        and macd > macd_signal
    )
    if not (volume_confirmation or trend_confirmation):
        return None, [
            "Ausbruch: Weder Volumenbestätigung noch die Kombination SMA 50 > SMA 200 und MACD > Signal ist erfüllt."
        ]

    atr = _latest_value(latest, "ATR_14") or breakout_level * thresholds.stop_buffer_pct / 100
    stop_buffer = max(breakout_level * thresholds.stop_buffer_pct / 100, atr * 0.50)
    stop = breakout_level - stop_buffer
    range_low = float(prior_range["Low"].min())
    range_height = breakout_level - range_low
    if range_height <= 0:
        return None, ["Ausbruch: Die vorherige Handelsspanne liefert kein realistisches Messziel."]
    measured_target = breakout_level + range_height
    target_cap = close * (1 + thresholds.max_target_distance_pct / 100)
    target_1 = min(measured_target, target_cap)
    historical_highs = _swing_extrema(frame["High"].iloc[:-21].tail(220), "high")
    higher_levels = _unique_levels(historical_highs, target_1 * 1.01, target_cap * 1.25)
    target_2 = higher_levels[0] if higher_levels else None
    confirmation_text = (
        f"Volumen {volume_ratio:.2f}x des 20-Tage-Schnitts"
        if volume_confirmation and volume_ratio is not None
        else "SMA 50 über SMA 200 und MACD über Signal-Linie"
    )
    return {
        "setup_type": "Bestätigter Ausbruch über Widerstand",
        "entry_reference": close,
        "entry_low": required_close,
        "entry_high": max_entry,
        "entry_condition": (
            f"Einstieg nur nach Tagesschluss über {required_close:.4f}; Bestätigung: {confirmation_text}."
        ),
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "max_entry": max_entry,
        "invalidation": stop,
        "structure_level": breakout_level,
        "confirmation": confirmation_text,
        "stop_reason": (
            f"Der Stop liegt unter dem überwundenen Widerstand {breakout_level:.4f}; "
            f"der Puffer {stop_buffer:.4f} berücksichtigt Struktur und aktuelle Schwankung."
        ),
        "technical_normalization": adaptive_bands,
    }, []


def evaluate_swing_trade(
    data: pd.DataFrame,
    *,
    symbol: str,
    asset_name: str,
    asset_type: str,
    market_phase: str,
    buy_signal: float,
    asset_quality: float,
    confidence: float,
    market_score: float,
    fx_rate: float | None = 1.0,
    original_currency: str = "EUR",
    region: str | None = None,
    historical_cases: int = 0,
    historical_hit_rate: float | None = None,
    event_date: object = None,
    now: datetime | None = None,
    thresholds: SwingTradeThresholds = DEFAULT_SWING_THRESHOLDS,
) -> dict:
    timestamp = now or datetime.now().astimezone()
    result = {
        "approved": False,
        "symbol": symbol.upper(),
        "asset_name": asset_name or symbol.upper(),
        "asset_type": asset_type,
        "direction": "Long",
        "market_phase": market_phase,
        "rejection_reasons": [],
        "rejection_filters": [],
        "buy_signal": float(buy_signal),
        "asset_quality": float(asset_quality),
        "confidence": float(confidence),
        "asset_quality_role": thresholds.asset_quality_role,
        "asset_quality_hard_gate": False,
        "evaluated_at": timestamp.isoformat(),
    }
    if data.empty or "Close" not in data:
        result["rejection_reasons"] = ["Keine Kursdaten verfügbar."]
        result["rejection_filters"] = ["data_quality"]
        return result
    frame = _ensure_indicators(data.dropna(subset=["Close"]))
    if len(frame) < 2:
        result["rejection_reasons"] = ["Zu wenig Kursdaten für ein messbares Setup."]
        result["rejection_filters"] = ["data_quality"]
        return result
    try:
        signal_bar_timestamp = pd.Timestamp(frame.index[-1])
        if signal_bar_timestamp.tzinfo is not None:
            signal_bar_timestamp = signal_bar_timestamp.tz_convert(None)
        signal_bar_day = signal_bar_timestamp.date()
    except Exception:
        result["rejection_reasons"] = ["Das Datum der letzten Tageskerze ist nicht verlässlich bestimmbar."]
        result["rejection_filters"] = ["data_quality"]
        return result
    if not completed_daily_signal_bar(
        signal_bar_day,
        timestamp,
        asset_type=asset_type,
        region=region,
        symbol=symbol,
    ):
        result["rejection_reasons"] = [
            "Die letzte Tageskerze ist noch nicht sicher abgeschlossen; ein Einstiegssignal wird erst am Folgetag freigegeben."
        ]
        result["rejection_filters"] = ["bar_completion"]
        return result
    market_bar_rejections = validate_daily_market_bar(
        frame,
        signal_bar_day,
        timestamp,
        asset_type=asset_type,
        region=region,
        symbol=symbol,
    )
    if market_bar_rejections:
        result["market_validation_status"] = "not_tradable_confirmed"
        result["rejection_reasons"] = market_bar_rejections
        result["rejection_filters"] = ["market_bar_validation"]
        return result

    common_rejections, common_rejection_filters, diagnostics = _common_rejections(
        frame,
        asset_type,
        fx_rate,
        float(buy_signal),
        float(asset_quality),
        float(confidence),
        float(market_score),
        event_date,
        timestamp,
        thresholds,
    )
    result.update(diagnostics)
    if common_rejections:
        result["rejection_filters"] = common_rejection_filters
        result["rejection_reasons"] = common_rejections
        return result

    pullback, pullback_rejections = _pullback_candidate(frame, thresholds)
    breakout, breakout_rejections = _breakout_candidate(frame, thresholds)
    candidates = [candidate for candidate in [pullback, breakout] if candidate is not None]
    if not candidates:
        result["rejection_reasons"] = [*pullback_rejections, *breakout_rejections]
        result["rejection_filters"] = ["setup_structure"]
        return result

    approved_candidates: list[tuple[dict, dict]] = []
    metric_rejections: list[str] = []
    metric_rejection_filters: list[str] = []
    for candidate in candidates:
        try:
            metrics = long_trade_metrics(candidate["entry_reference"], candidate["stop"], candidate["target_1"])
        except ValueError as exc:
            metric_rejections.append(f"{candidate['setup_type']}: {exc}")
            metric_rejection_filters.append("invalid_geometry")
            continue
        if metrics["crv"] < thresholds.min_crv:
            metric_rejections.append(
                f"{candidate['setup_type']}: CRV {metrics['crv']:.2f} liegt unter {thresholds.min_crv:.2f}."
            )
            metric_rejection_filters.append("crv")
            continue
        minimum_stop_distance = {
            "ETF": thresholds.min_stop_distance_pct_etf,
            "Krypto": thresholds.min_stop_distance_pct_crypto,
        }.get(asset_type, thresholds.min_stop_distance_pct_stock)
        if metrics["risk_pct"] < minimum_stop_distance:
            metric_rejections.append(
                f"{candidate['setup_type']}: Stop-Abstand {metrics['risk_pct']:.2f}% ist kleiner als das "
                f"konservative Minimum {minimum_stop_distance:.2f}%; das CRV wäre durch einen praktisch zu engen Stop verzerrt."
            )
            metric_rejection_filters.append("stop_distance")
            continue
        maximum_stop_distance = {
            "ETF": thresholds.max_stop_distance_pct_etf,
            "Krypto": thresholds.max_stop_distance_pct_crypto,
        }.get(asset_type, thresholds.max_stop_distance_pct_stock)
        if metrics["risk_pct"] > maximum_stop_distance:
            metric_rejections.append(
                f"{candidate['setup_type']}: struktureller Stop-Abstand {metrics['risk_pct']:.2f}% "
                f"überschreitet das konservative Maximum {maximum_stop_distance:.2f}%."
            )
            metric_rejection_filters.append("stop_distance")
            continue
        expected_r = None
        if historical_cases >= thresholds.min_historical_cases and historical_hit_rate is not None:
            expected_r = expected_value_in_r(metrics["crv"], historical_hit_rate)
            if expected_r <= thresholds.min_expected_value_r:
                metric_rejections.append(
                    f"{candidate['setup_type']}: historischer Erwartungswert {expected_r:.2f} R ist nicht positiv."
                )
                metric_rejection_filters.append("expected_value")
                continue
        approved_candidates.append((candidate, {**metrics, "expected_value_r": expected_r}))

    if not approved_candidates:
        result["rejection_reasons"] = metric_rejections or ["Kein Setup erfüllt das zentrale Mindest-CRV."]
        result["rejection_filters"] = list(dict.fromkeys(metric_rejection_filters or ["crv"]))
        return result

    candidate, metrics = max(
        approved_candidates,
        key=lambda item: (
            item[1]["expected_value_r"] if item[1]["expected_value_r"] is not None else 0.0,
            min(item[1]["crv"], 4.0),
        ),
    )
    rate_is_reliable = historical_cases >= thresholds.min_historical_cases and historical_hit_rate is not None
    hit_rate_text = (
        f"Historische Trefferquote dieses Segments: {historical_hit_rate:.1f}% aus {historical_cases} Fällen."
        if rate_is_reliable
        else "Trefferwahrscheinlichkeit noch nicht belastbar."
    )
    expected_value_text = (
        f"Historischer Erwartungswert: {metrics['expected_value_r']:.2f} R pro Trade."
        if metrics["expected_value_r"] is not None
        else f"Strukturell positives Verhältnis mit CRV {metrics['crv']:.2f}; statistischer Erwartungswert noch nicht belastbar."
    )
    event_days = diagnostics.get("event_days")
    event_warning = (
        f"Bekanntes Ereignis in {event_days} Tagen; vor Einstieg Termin und Risiko erneut prüfen."
        if event_days is not None and thresholds.event_block_days < event_days <= thresholds.event_warning_days
        else "Technische Signale können durch unerwartete Nachrichten oder Makroschocks ungültig werden."
    )
    valid_until = (signal_bar_day + timedelta(days=thresholds.validity_days)).isoformat()
    conversion = float(fx_rate or 0)
    # A setup belongs to its completed signal bar. Weekend scans must not turn
    # the same Friday bar into multiple independent forward samples.
    setup_id = (
        f"{symbol.upper()}|{signal_bar_day.isoformat()}|{candidate['setup_type']}|"
        f"{SWING_ORDER_PLAN_VERSION}"
    )
    order_plan = build_swing_order_plan(
        candidate,
        asset_type=asset_type,
        original_currency=original_currency,
        fx_rate_to_eur=conversion,
        analysis_reference_price_original=float(frame.iloc[-1]["Close"]),
        analysis_price_source="Yahoo Finance / yfinance",
        analysis_reference_observed_at=signal_bar_day.isoformat(),
        evaluated_at=timestamp,
        signal_bar_day=signal_bar_day,
        valid_until=valid_until,
        region=region,
    )
    result.update(
        {
            "approved": True,
            "setup_id": setup_id,
            **candidate,
            **metrics,
            "current_price": float(frame.iloc[-1]["Close"]),
            "current_price_eur": float(frame.iloc[-1]["Close"]) * conversion,
            "price_kind": "completed_daily_close",
            "price_source": "Yahoo Finance / yfinance",
            "price_observed_at": signal_bar_day.isoformat(),
            "market_validation_status": "daily_bar_validated",
            "entry_reference_eur": candidate["entry_reference"] * conversion,
            "entry_low_eur": candidate["entry_low"] * conversion,
            "entry_high_eur": candidate["entry_high"] * conversion,
            "stop_eur": candidate["stop"] * conversion,
            "target_1_eur": candidate["target_1"] * conversion,
            "target_2_eur": candidate["target_2"] * conversion if candidate.get("target_2") else None,
            "max_entry_eur": candidate["max_entry"] * conversion,
            "invalidation_eur": candidate["invalidation"] * conversion,
            "risk_eur_per_unit": metrics["risk"] * conversion,
            "chance_eur_per_unit": metrics["chance"] * conversion,
            "original_currency": original_currency,
            "fx_rate_to_eur": conversion,
            "signal_bar_day": signal_bar_day.isoformat(),
            "valid_until": valid_until,
            "order_plan": order_plan,
            "holding_period": "mehrere Tage bis einige Wochen",
            "historical_cases": historical_cases,
            "historical_hit_rate": historical_hit_rate if rate_is_reliable else None,
            "known_event_date_at_signal": _event_day_iso(event_date),
            "event_days_at_signal": event_days,
            "hit_rate_text": hit_rate_text,
            "expected_value_text": expected_value_text,
            "quality_score": round(
                min(
                    10.0,
                    float(buy_signal) * 0.35
                    + float(confidence) * 0.25
                    + min(metrics["crv"], 4.0) / 4 * 4.0,
                ),
                1,
            ),
            "reasons": [
                f"{candidate['setup_type']} ist mit einer exakten Tagesschluss-Bedingung bestätigt.",
                f"Kaufsignal {buy_signal:.1f}/10 und Confidence {confidence:.1f}/10 erfüllen die Swing-Mindestwerte.",
                f"Asset-Qualität {asset_quality:.1f}/10 bleibt dokumentiert, ist aber kein kurzfristiges Swing-Hard-Gate.",
                f"Chance {metrics['chance_pct']:.2f}% gegenüber Risiko {metrics['risk_pct']:.2f}% ergibt CRV {metrics['crv']:.2f}.",
            ],
            "largest_risk": event_warning,
            "no_entry_conditions": [
                f"Kein Einstieg bei Tagesschluss unter {candidate['invalidation']:.4f}.",
                f"Kein Einstieg oberhalb des maximalen Einstiegskurses {candidate['max_entry']:.4f}.",
                f"Kein Einstieg nach dem {valid_until}; danach muss das Setup neu berechnet werden.",
            ],
            "rejection_reasons": [],
        }
    )
    return result


def calculate_position_size(
    trading_capital_eur: float | None,
    max_risk_pct: float,
    entry_eur: float,
    stop_eur: float,
    *,
    asset_type: str,
    max_total_exposure_pct: float = 60.0,
    current_exposure_eur: float = 0.0,
    max_position_exposure_pct: float = 25.0,
    max_total_risk_pct: float | None = None,
    current_risk_eur: float = 0.0,
    target_1_eur: float | None = None,
    target_2_eur: float | None = None,
) -> dict:
    capital = _number(trading_capital_eur)
    if capital is None or capital <= 0:
        return {
            "quantity": None,
            "risk_budget_eur": None,
            "per_trade_risk_budget_eur": None,
            "total_open_risk_limit_eur": None,
            "remaining_open_risk_before_trade_eur": None,
            "position_value_eur": None,
            "actual_risk_eur": None,
            "potential_gain_1_eur": None,
            "potential_gain_2_eur": None,
            "explanation": "Ohne hinterlegtes Trading-Kapital wird keine konkrete Stückzahl berechnet.",
            "planned_loss_notice": (
                "Ohne hinterlegtes Trading-Kapital wird kein Euro-Risiko berechnet. "
                "Bei Kurslücken kann ein tatsächlicher Verlust dennoch höher als ein geplanter Stop-Verlust ausfallen."
            ),
        }
    metrics = long_trade_metrics(entry_eur, stop_eur, entry_eur + (entry_eur - stop_eur))
    risk_per_unit = metrics["risk"]
    per_trade_risk_budget = capital * max(float(max_risk_pct), 0.0) / 100
    total_risk_limit = (
        capital * max(float(max_total_risk_pct), 0.0) / 100
        if max_total_risk_pct is not None
        else None
    )
    remaining_risk_budget = (
        max(total_risk_limit - max(float(current_risk_eur), 0.0), 0.0)
        if total_risk_limit is not None
        else per_trade_risk_budget
    )
    risk_budget = min(per_trade_risk_budget, remaining_risk_budget)
    risk_quantity = risk_budget / risk_per_unit
    total_limit = capital * max(float(max_total_exposure_pct), 0.0) / 100
    remaining_total = max(total_limit - max(float(current_exposure_eur), 0.0), 0.0)
    position_limit = capital * max(float(max_position_exposure_pct), 0.0) / 100
    exposure_quantity = min(remaining_total, position_limit) / entry_eur
    quantity = min(risk_quantity, exposure_quantity)
    if asset_type in {"Aktie", "ETF"}:
        quantity = float(math.floor(quantity))
    else:
        quantity = round(max(quantity, 0.0), 6)
    position_value = quantity * entry_eur
    actual_risk = quantity * risk_per_unit
    target_1 = _number(target_1_eur)
    target_2 = _number(target_2_eur)
    potential_gain_1 = (
        quantity * (target_1 - entry_eur) if target_1 is not None and target_1 > entry_eur else None
    )
    potential_gain_2 = (
        quantity * (target_2 - entry_eur) if target_2 is not None and target_2 > entry_eur else None
    )
    quantity_text = f"{int(quantity)} Anteile" if asset_type in {"Aktie", "ETF"} else f"{quantity:.6f} Einheiten"
    if quantity <= 0:
        explanation = "Das verfügbare Risiko- oder Gesamtbudget erlaubt aktuell keine Position."
    else:
        explanation = (
            f"Bei maximal {max_risk_pct:.2f}% Risiko je Trade und dem verbleibenden Gesamt-Risikobudget sind höchstens "
            f"{quantity_text} vertretbar; rechnerisches Risiko {actual_risk:.2f} € und Positionswert {position_value:.2f} €."
        )
    return {
        "quantity": quantity,
        "risk_budget_eur": risk_budget,
        "per_trade_risk_budget_eur": per_trade_risk_budget,
        "total_open_risk_limit_eur": total_risk_limit,
        "remaining_open_risk_before_trade_eur": remaining_risk_budget,
        "risk_per_unit_eur": risk_per_unit,
        "actual_risk_eur": actual_risk,
        "position_value_eur": position_value,
        "potential_gain_1_eur": potential_gain_1,
        "potential_gain_2_eur": potential_gain_2,
        "risk_pct_of_capital": actual_risk / capital * 100 if capital > 0 else None,
        "gain_1_pct_of_capital": potential_gain_1 / capital * 100 if potential_gain_1 is not None else None,
        "gain_2_pct_of_capital": potential_gain_2 / capital * 100 if potential_gain_2 is not None else None,
        "explanation": explanation,
        "planned_loss_notice": (
            f"Geplanter Verlust bei Ausführung nahe dem Stop: ca. {actual_risk:.2f} €. "
            "Bei Kurslücken kann der tatsächliche Verlust höher sein."
        ),
    }


def open_trade_record(
    record: dict,
    actual_entry_eur: float,
    quantity: float,
    opened_at: object,
) -> tuple[dict | None, str | None]:
    entry = _number(actual_entry_eur)
    units = _number(quantity)
    if entry is None or entry <= 0 or units is None or units <= 0:
        return None, "Tatsächlicher Einstieg und Stückzahl müssen größer als null sein."
    maximum = _number(record.get("Maximaler Einstieg EUR") or record.get("max_entry_eur"))
    if maximum is not None and entry > maximum:
        return None, f"Der Einstieg ist oberhalb des maximal erlaubten Kurses von {maximum:.2f} €."
    valid_until = record.get("Gültig bis") or record.get("valid_until")
    try:
        opened_timestamp = pd.Timestamp(opened_at)
    except Exception:
        return None, "Datum und Uhrzeit des Einstiegs sind ungültig."
    order_plan = record.get("Orderplan") or record.get("order_plan") or {}
    earliest_entry = (
        record.get("Frühester Einstieg")
        or record.get("earliest_entry_day")
        or (order_plan.get("earliest_entry_day") if isinstance(order_plan, dict) else None)
    )
    if earliest_entry:
        try:
            if opened_timestamp.date() < pd.Timestamp(earliest_entry).date():
                return None, "Der Einstieg liegt vor dem frühesten erlaubten Handelstag des Orderplans."
        except Exception:
            return None, "Der früheste Einstiegstag des Orderplans ist ungültig."
    if valid_until:
        try:
            if opened_timestamp.date() > pd.Timestamp(valid_until).date():
                return None, "Das Setup war zum tatsächlichen Einstieg bereits abgelaufen."
        except Exception:
            pass
    initial_stop = _number(
        record.get("Initialer Stop EUR")
        or record.get("initial_stop_eur")
        or (order_plan.get("initial_stop_eur") if isinstance(order_plan, dict) else None)
        or record.get("Stop-Loss EUR")
        or record.get("stop_eur")
    )
    if initial_stop is None or initial_stop <= 0:
        return None, "Der unveränderbare initiale Stop fehlt oder ist ungültig."
    updated = dict(record)
    updated.update(
        {
            "Status": "Aktiv",
            "Tatsächlicher Einstieg EUR": entry,
            "Tatsächliche Stückzahl": units,
            "Eröffnet am": opened_timestamp.isoformat(),
            "Initialer Stop EUR": initial_stop,
            "Stop-Vertrag Version": str(
                record.get("Stop-Vertrag Version")
                or (order_plan.get("stop_contract_version") if isinstance(order_plan, dict) else "")
                or SWING_STOP_CONTRACT_VERSION
            ),
            "Aktueller Stop EUR": initial_stop,
            "Letzte Aktualisierung": opened_timestamp.isoformat(),
        }
    )
    return updated, None


def close_trade_record(record: dict, actual_exit_eur: float, closed_at: object) -> tuple[dict | None, str | None]:
    exit_price = _number(actual_exit_eur)
    if str(record.get("Status")) != "Aktiv":
        return None, "Nur ein aktiver Trade kann geschlossen werden."
    if exit_price is None or exit_price <= 0:
        return None, "Der tatsächliche Ausstiegskurs muss größer als null sein."
    try:
        closed_timestamp = pd.Timestamp(closed_at)
    except Exception:
        return None, "Datum und Uhrzeit des Ausstiegs sind ungültig."
    entry = _number(record.get("Tatsächlicher Einstieg EUR")) or 0.0
    quantity = _number(record.get("Tatsächliche Stückzahl")) or 0.0
    updated = dict(record)
    updated.update(
        {
            "Status": "Geschlossen",
            "Tatsächlicher Ausstieg EUR": exit_price,
            "Geschlossen am": closed_timestamp.isoformat(),
            "Realisierter Gewinn/Verlust EUR": (exit_price - entry) * quantity,
            "Realisierter Gewinn/Verlust %": (exit_price - entry) / entry * 100 if entry > 0 else None,
            "Letzte Aktualisierung": closed_timestamp.isoformat(),
        }
    )
    return updated, None


def active_trade_snapshot(record: dict, current_price_eur: float, updated_at: object = None) -> dict:
    current = _number(current_price_eur)
    entry = _number(record.get("Tatsächlicher Einstieg EUR"))
    quantity = _number(record.get("Tatsächliche Stückzahl"))
    stop = _number(record.get("Aktueller Stop EUR") or record.get("Stop-Loss EUR") or record.get("stop_eur"))
    target_1 = _number(record.get("Kursziel 1 EUR") or record.get("target_1_eur"))
    target_2 = _number(record.get("Kursziel 2 EUR") or record.get("target_2_eur"))
    if current is None or entry is None or entry <= 0 or quantity is None or quantity <= 0:
        raise ValueError("Aktiver Trade besitzt keine vollständigen Kurs- und Stückzahldaten.")
    pnl_eur = (current - entry) * quantity
    pnl_pct = (current - entry) / entry * 100
    initial_stop = _number(
        record.get("Initialer Stop EUR") or record.get("Stop-Loss EUR") or record.get("stop_eur")
    ) or stop
    initial_risk = entry - initial_stop if initial_stop is not None else None
    if stop is not None and current <= stop:
        action = "Ausstieg empfohlen"
        reason = "Der aktuelle Kurs liegt am oder unter dem bestätigten Stop. Der Nutzer entscheidet und dokumentiert den Ausstieg manuell."
    elif target_2 is not None and current >= target_2:
        action = "Ausstieg empfohlen"
        reason = "Das zweite Kursziel wurde erreicht oder überschritten."
    elif target_1 is not None and current >= target_1:
        action = "Teilgewinn prüfen"
        reason = "Das erste Kursziel wurde erreicht; Restposition und Stop können bewusst neu bewertet werden."
    elif initial_risk is not None and initial_risk > 0 and current >= entry + initial_risk:
        action = "Stop anpassen"
        reason = "Der Gewinn entspricht mindestens dem anfänglichen Risiko; ein engerer Stop kann geprüft werden."
    else:
        action = "Halten"
        reason = "Stop und nächstes Kursziel sind nicht erreicht; das ursprüngliche Setup bleibt aktiv."
    next_target = target_1 if target_1 is not None and current < target_1 else target_2
    return {
        "current_price_eur": current,
        "pnl_eur": pnl_eur,
        "pnl_pct": pnl_pct,
        "current_stop_eur": stop,
        "next_target_eur": next_target,
        "action": action,
        "reason": reason,
        "updated_at": pd.Timestamp(updated_at or datetime.now().astimezone()).isoformat(),
    }


def expire_paper_trade(record: dict, today: date | None = None) -> tuple[dict, bool]:
    if str(record.get("Status") or "Paper") not in {"Paper", "Freigegeben"}:
        return dict(record), False
    valid_until = record.get("Gültig bis") or record.get("valid_until")
    if not valid_until:
        return dict(record), False
    try:
        expired = (today or date.today()) > pd.Timestamp(valid_until).date()
    except Exception:
        return dict(record), False
    if not expired:
        return dict(record), False
    updated = dict(record)
    updated["Status"] = "Abgelaufen"
    updated["Ablaufgrund"] = "Die definierte Setup-Gültigkeit endete ohne manuell dokumentierten Einstieg."
    return updated, True


def paper_trade_statistics(history: list[dict]) -> dict:
    outcomes: list[dict] = []
    expired = 0
    for record in history:
        if str(record.get("Status")) == "Abgelaufen":
            expired += 1
        review_after = record.get("review_after")
        if not isinstance(review_after, dict):
            continue
        reviews = [value for value in review_after.values() if isinstance(value, dict)]
        if not reviews:
            continue
        review = reviews[-1]
        return_pct = _number(review.get("return_pct"))
        if return_pct is None:
            continue
        outcomes.append(
            {
                "return_pct": return_pct,
                "target_hit": bool(review.get("target_hit")),
                "stop_hit": bool(review.get("stop_hit")),
                "setup_type": record.get("Setup-Typ") or record.get("setup_type") or "Unbekannt",
                "market_phase": record.get("Marktphase") or record.get("market_phase") or "Unbekannt",
                "opportunity_cost_pct": _number(review.get("opportunity_cost_pct")),
            }
        )
    wins = [item["return_pct"] for item in outcomes if item["return_pct"] > 0]
    losses = [item["return_pct"] for item in outcomes if item["return_pct"] < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    running = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for item in outcomes:
        running += item["return_pct"]
        peak = max(peak, running)
        max_drawdown = min(max_drawdown, running - peak)
    return {
        "signals": len(history),
        "evaluated": len(outcomes),
        "wins": len(wins),
        "losses": len(losses),
        "hit_rate_pct": len(wins) / len(outcomes) * 100 if outcomes else None,
        "average_win_pct": sum(wins) / len(wins) if wins else None,
        "average_loss_pct": sum(losses) / len(losses) if losses else None,
        "expected_value_pct": sum(item["return_pct"] for item in outcomes) / len(outcomes) if outcomes else None,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "max_drawdown_pct": max_drawdown if outcomes else None,
        "target_hits": sum(item["target_hit"] for item in outcomes),
        "stop_hits": sum(item["stop_hit"] for item in outcomes),
        "expired": expired,
        "average_opportunity_cost_pct": (
            sum(item["opportunity_cost_pct"] for item in outcomes if item["opportunity_cost_pct"] is not None)
            / sum(item["opportunity_cost_pct"] is not None for item in outcomes)
            if any(item["opportunity_cost_pct"] is not None for item in outcomes)
            else None
        ),
    }
