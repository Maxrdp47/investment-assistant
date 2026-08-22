from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import tempfile
from typing import Callable

import pandas as pd
import yfinance as yf

from historical_fx import HISTORICAL_FX_POLICY_VERSION, historical_fx_evidence
from swing_forward_evaluation import evaluate_swing_signal_bars
from swing_forward_store import (
    DEFAULT_SWING_FORWARD_DB_PATH,
    append_swing_rejection_control_event,
    append_swing_signal_event,
    load_swing_rejection_controls,
    load_swing_forward_signals,
    swing_forward_store_audit,
)


BarsLoader = Callable[[dict, pd.Timestamp], tuple[pd.DataFrame, str, str]]
FxLoader = Callable[[str, object], dict | None]


COUNTERFACTUAL_HORIZONS = (5, 20)


def _missing_counterfactual_horizons(signal: dict) -> list[int]:
    existing = {
        int((event.get("payload") or {}).get("horizon_sessions"))
        for event in signal.get("events") or []
        if event.get("event_type") == "counterfactual_outcome"
        and (event.get("payload") or {}).get("horizon_sessions") is not None
    }
    return [value for value in COUNTERFACTUAL_HORIZONS if value not in existing]


PROJECT_ROOT = Path(__file__).resolve().parent
YFINANCE_CACHE_DIR = PROJECT_ROOT / ".yfinance-cache"
try:
    YFINANCE_CACHE_DIR.mkdir(exist_ok=True)
except OSError:
    YFINANCE_CACHE_DIR = Path(tempfile.gettempdir()) / "investment-assistent-yfinance-cache"
    YFINANCE_CACHE_DIR.mkdir(exist_ok=True)
yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))


def load_swing_signal_bars(
    signal_snapshot: dict,
    evaluated_at: pd.Timestamp,
) -> tuple[pd.DataFrame, str, str]:
    symbol = str((signal_snapshot.get("asset") or {}).get("ticker") or "").strip()
    if not symbol:
        return pd.DataFrame(), "", "Ticker fehlt."
    attempts = (("5m", "60d"), ("60m", "730d"), ("1d", "max"))
    errors: list[str] = []
    for interval, period in attempts:
        try:
            frame = yf.Ticker(symbol).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:
            errors.append(f"{interval}: {exc}")
            continue
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame, interval, f"Yahoo Finance/yfinance {interval}"
        errors.append(f"{interval}: keine Daten")
    return pd.DataFrame(), "", " | ".join(errors)[:1_000]


def _is_terminal(signal: dict) -> bool:
    plan = dict((signal.get("snapshot") or {}).get("order_plan") or {})
    target_2_exists = plan.get("target_2_original") is not None
    terminal_types = {
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
        "target_2_reached",
        "stop_reached",
    }
    if not target_2_exists:
        terminal_types.add("target_1_reached")
    return any(event.get("event_type") in terminal_types for event in signal.get("events") or [])


def _terminal_event(signal: dict) -> dict | None:
    plan = dict((signal.get("snapshot") or {}).get("order_plan") or {})
    terminal_types = {"entry_missed", "invalidated_before_entry", "expired_without_entry", "stop_reached"}
    terminal_types.add("target_2_reached" if plan.get("target_2_original") is not None else "target_1_reached")
    candidates = [event for event in signal.get("events") or [] if event.get("event_type") in terminal_types]
    return candidates[-1] if candidates else None


def _counterfactual_outcome_candidates(
    signal: dict,
    bars: pd.DataFrame,
    *,
    interval: str,
    evaluated_at: pd.Timestamp,
) -> list[dict]:
    terminal = _terminal_event(signal)
    if terminal is None or terminal.get("event_type") not in {
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
    }:
        return []
    missing_horizons = _missing_counterfactual_horizons(signal)
    if not missing_horizons or bars.empty or not {"Open", "High", "Low", "Close"}.issubset(bars.columns):
        return []
    frame = bars.copy().sort_index()
    index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame.loc[~index.isna()].copy()
    frame.index = index[~index.isna()]
    evaluation_day = evaluated_at.tz_convert(None).date() if evaluated_at.tzinfo else evaluated_at.date()
    frame = frame.loc[frame.index.map(lambda value: pd.Timestamp(value).date() < evaluation_day)]
    if frame.empty:
        return []
    try:
        terminal_day = pd.Timestamp(terminal["occurred_at"]).date()
    except Exception:
        return []
    frame["_session_day"] = [pd.Timestamp(value).date() for value in frame.index]
    sessions = (
        frame.groupby("_session_day", sort=True)
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
        )
        .dropna(subset=["Open", "High", "Low", "Close"])
    )
    eligible = sessions.loc[[day >= terminal_day for day in sessions.index]]
    if eligible.empty:
        return []
    reference_day = eligible.index[0]
    reference_price = float(eligible.iloc[0]["Open"])
    if reference_price <= 0:
        return []
    later = eligible.loc[[day > reference_day for day in eligible.index]]
    candidates: list[dict] = []
    for horizon in missing_horizons:
        if len(later) < horizon:
            continue
        window = later.iloc[:horizon]
        outcome_day = window.index[-1]
        outcome_close = float(window.iloc[-1]["Close"])
        candidates.append(
            {
                "event_type": "counterfactual_outcome",
                "occurred_at": outcome_day.isoformat(),
                "source_key": (
                    f"counterfactual:{terminal.get('source_key')}:{horizon}:{outcome_day.isoformat()}"
                ),
                "payload": {
                    "control_version": "swing-counterfactual-2026.08.16-v1",
                    "control_only": True,
                    "not_a_trade_result": True,
                    "terminal_event_type": str(terminal.get("event_type")),
                    "terminal_source_key": str(terminal.get("source_key") or ""),
                    "terminal_reason": str((terminal.get("payload") or {}).get("reason") or ""),
                    "reference_day": reference_day.isoformat(),
                    "reference_price_original": reference_price,
                    "horizon_sessions": horizon,
                    "outcome_day": outcome_day.isoformat(),
                    "outcome_close_original": outcome_close,
                    "return_pct": (outcome_close / reference_price - 1) * 100,
                    "maximum_favorable_excursion_pct": (
                        float(window["High"].max()) / reference_price - 1
                    )
                    * 100,
                    "maximum_adverse_excursion_pct": (
                        float(window["Low"].min()) / reference_price - 1
                    )
                    * 100,
                    "market_data_interval": interval,
                    "broker_order_sent": False,
                },
            }
        )
    return candidates


def _rejection_control_outcome_candidates(
    control: dict,
    bars: pd.DataFrame,
    *,
    interval: str,
    evaluated_at: pd.Timestamp,
) -> list[dict]:
    snapshot = dict(control.get("snapshot") or {})
    try:
        signal_day = pd.Timestamp(snapshot["signal_day"]).date()
        reference_price = float(snapshot["reference_price_original"])
    except (KeyError, TypeError, ValueError):
        return []
    if reference_price <= 0 or bars.empty or not {"High", "Low", "Close"}.issubset(bars.columns):
        return []
    existing = {
        int(event.get("horizon_sessions"))
        for event in control.get("events") or []
        if event.get("horizon_sessions") is not None
    }
    evaluation_day = evaluated_at.tz_convert(None).date() if evaluated_at.tzinfo else evaluated_at.date()
    due_horizons = [
        horizon
        for horizon in COUNTERFACTUAL_HORIZONS
        if horizon not in existing
        and evaluation_day >= signal_day + timedelta(days=7 if horizon == 5 else 28)
    ]
    if not due_horizons:
        return []
    frame = bars.copy().sort_index()
    index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame.loc[~index.isna()].copy()
    frame.index = index[~index.isna()]
    frame = frame.loc[frame.index.map(lambda value: pd.Timestamp(value).date() < evaluation_day)]
    if frame.empty:
        return []
    frame["_session_day"] = [pd.Timestamp(value).date() for value in frame.index]
    sessions = (
        frame.groupby("_session_day", sort=True)
        .agg(High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
        .dropna(subset=["High", "Low", "Close"])
    )
    later = sessions.loc[[day > signal_day for day in sessions.index]]
    candidates = []
    for horizon in due_horizons:
        if len(later) < horizon:
            continue
        window = later.iloc[:horizon]
        outcome_day = window.index[-1]
        outcome_close = float(window.iloc[-1]["Close"])
        candidates.append(
            {
                "horizon_sessions": horizon,
                "occurred_at": outcome_day.isoformat(),
                "payload": {
                    "control_version": "swing-rejection-control-outcome-2026.08.16-v1",
                    "reference_day": signal_day.isoformat(),
                    "reference_price_original": reference_price,
                    "outcome_day": outcome_day.isoformat(),
                    "outcome_close_original": outcome_close,
                    "return_pct": (outcome_close / reference_price - 1) * 100,
                    "maximum_favorable_excursion_pct": (
                        float(window["High"].max()) / reference_price - 1
                    )
                    * 100,
                    "maximum_adverse_excursion_pct": (
                        float(window["Low"].min()) / reference_price - 1
                    )
                    * 100,
                    "market_data_interval": interval,
                    "rejection_filters": list(snapshot.get("rejection_filters") or []),
                    "broker_order_sent": False,
                },
            }
        )
    return candidates


def _historical_fx_valuation(
    signal: dict,
    *,
    fx_loader: FxLoader,
) -> tuple[dict | None, str | None]:
    events = list(signal.get("events") or [])
    terminal = _terminal_event(signal)
    if terminal is None or terminal.get("event_type") in {
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
    }:
        return None, None
    entry = next((event for event in events if event.get("event_type") == "paper_entry_opened"), None)
    if entry is None:
        return None, "Historischer Paper-Einstieg fehlt."
    terminal_source_key = str(terminal.get("source_key") or "")
    existing = next(
        (
            event
            for event in events
            if event.get("event_type") == "historical_fx_valuation"
            and str((event.get("payload") or {}).get("terminal_source_key") or "") == terminal_source_key
        ),
        None,
    )
    if existing is not None:
        return None, None
    snapshot = dict(signal.get("snapshot") or {})
    plan = dict(snapshot.get("order_plan") or {})
    asset = dict(snapshot.get("asset") or {})
    currency = str(plan.get("original_currency") or asset.get("original_currency") or "EUR").upper()
    entry_evidence = fx_loader(currency, entry.get("occurred_at"))
    terminal_payload = dict(terminal.get("payload") or {})
    exit_legs = list(terminal_payload.get("exit_legs") or [])
    if not exit_legs:
        exit_legs = [
            {
                "paper_exit_after_costs_original": terminal_payload.get("paper_exit_after_costs_original"),
                "exit_fraction": 1.0,
                "occurred_at": terminal.get("occurred_at"),
            }
        ]
    exit_evidence_legs = []
    missing_exit_fx = False
    for leg in exit_legs:
        evidence = fx_loader(currency, leg.get("occurred_at") or terminal.get("occurred_at"))
        if evidence is None:
            missing_exit_fx = True
            continue
        exit_evidence_legs.append({**dict(leg), "fx": dict(evidence)})
    if entry_evidence is None or missing_exit_fx or len(exit_evidence_legs) != len(exit_legs):
        missing = []
        if entry_evidence is None:
            missing.append("Einstiegs-FX")
        if missing_exit_fx:
            missing.append("Ausstiegs-FX")
        return None, f"Historische {' und '.join(missing)} noch nicht verfügbar."
    entry_original = float((entry.get("payload") or {})["paper_entry_after_costs_original"])
    entry_fx = float(entry_evidence["rate_to_eur"])
    entry_eur = entry_original * entry_fx
    exit_eur = sum(
        float(leg["paper_exit_after_costs_original"])
        * float(leg.get("exit_fraction") or 0)
        * float((leg.get("fx") or {})["rate_to_eur"])
        for leg in exit_evidence_legs
    )
    result_eur = exit_eur - entry_eur
    weighted_exit_original = sum(
        float(leg["paper_exit_after_costs_original"]) * float(leg.get("exit_fraction") or 0)
        for leg in exit_evidence_legs
    )
    last_exit_evidence = dict(exit_evidence_legs[-1]["fx"])
    payload = {
        "valuation_version": HISTORICAL_FX_POLICY_VERSION,
        "terminal_event_type": str(terminal.get("event_type")),
        "terminal_source_key": terminal_source_key,
        "entry_source_key": str(entry.get("source_key") or ""),
        "currency": currency,
        "paper_entry_after_costs_original": entry_original,
        "paper_exit_after_costs_original": weighted_exit_original,
        "entry_fx": dict(entry_evidence),
        "exit_fx": last_exit_evidence,
        "exit_fx_legs": exit_evidence_legs,
        "paper_entry_after_costs_eur": entry_eur,
        "paper_exit_after_costs_eur": exit_eur,
        "result_eur_per_unit": result_eur,
        "result_pct_eur": result_eur / entry_eur * 100 if entry_eur > 0 else None,
        "broker_order_sent": False,
    }
    return {
        "event_type": "historical_fx_valuation",
        "occurred_at": terminal.get("occurred_at"),
        "source_key": f"historical-fx:{terminal_source_key}:{HISTORICAL_FX_POLICY_VERSION}",
        "payload": payload,
    }, None


def _append_fx_valuation(
    signal: dict,
    *,
    path: Path,
    fx_loader: FxLoader,
) -> tuple[str, str | None]:
    candidate, pending_reason = _historical_fx_valuation(signal, fx_loader=fx_loader)
    if candidate is None:
        return ("pending" if pending_reason else "existing"), pending_reason
    result = append_swing_signal_event(
        str(signal["signal_id"]),
        str(candidate["event_type"]),
        candidate["occurred_at"],
        str(candidate["source_key"]),
        dict(candidate["payload"]),
        path,
    )
    return ("inserted" if result["inserted"] else "existing"), None


def run_swing_forward_evaluations(
    *,
    path: Path = DEFAULT_SWING_FORWARD_DB_PATH,
    evaluated_at: object = None,
    bars_loader: BarsLoader = load_swing_signal_bars,
    fx_loader: FxLoader = historical_fx_evidence,
) -> dict:
    now = pd.Timestamp(evaluated_at or datetime.now().astimezone())
    signals = load_swing_forward_signals(path)
    summary = {
        "evaluated_at": now.isoformat(),
        "signals_total": len(signals),
        "terminal_skipped": 0,
        "signals_checked": 0,
        "events_inserted": 0,
        "events_existing": 0,
        "data_failures": 0,
        "fx_valuations_inserted": 0,
        "fx_valuations_existing": 0,
        "fx_valuations_pending": 0,
        "fx_pending_reasons": [],
        "counterfactual_events_inserted": 0,
        "counterfactual_events_existing": 0,
        "counterfactual_data_pending": 0,
        "rejection_controls_total": 0,
        "rejection_control_events_inserted": 0,
        "rejection_control_events_existing": 0,
        "rejection_control_data_pending": 0,
        "errors": [],
    }
    for signal in signals:
        if _is_terminal(signal):
            try:
                fx_status, pending_reason = _append_fx_valuation(
                    signal,
                    path=path,
                    fx_loader=fx_loader,
                )
                summary[f"fx_valuations_{fx_status}"] += 1
                if pending_reason:
                    summary["fx_pending_reasons"].append(
                        f"{(signal.get('snapshot', {}).get('asset') or {}).get('ticker', signal['signal_id'])}: {pending_reason}"
                    )
            except Exception as exc:
                summary["errors"].append(f"{signal['signal_id']} FX: {exc}")
            terminal = _terminal_event(signal)
            if terminal is not None and terminal.get("event_type") in {
                "entry_missed",
                "invalidated_before_entry",
                "expired_without_entry",
            } and _missing_counterfactual_horizons(signal):
                try:
                    frame, interval, _source = bars_loader(dict(signal["snapshot"]), now)
                    if frame.empty or not interval:
                        summary["counterfactual_data_pending"] += 1
                    else:
                        controls = _counterfactual_outcome_candidates(
                            signal,
                            frame,
                            interval=interval,
                            evaluated_at=now,
                        )
                        if not controls:
                            summary["counterfactual_data_pending"] += 1
                        for candidate in controls:
                            stored = append_swing_signal_event(
                                str(signal["signal_id"]),
                                str(candidate["event_type"]),
                                candidate["occurred_at"],
                                str(candidate["source_key"]),
                                dict(candidate["payload"]),
                                path,
                            )
                            key = (
                                "counterfactual_events_inserted"
                                if stored["inserted"]
                                else "counterfactual_events_existing"
                            )
                            summary[key] += 1
                except Exception as exc:
                    summary["errors"].append(
                        f"{(signal.get('snapshot', {}).get('asset') or {}).get('ticker', signal['signal_id'])} Kontrolle: {exc}"
                    )
            summary["terminal_skipped"] += 1
            continue
        summary["signals_checked"] += 1
        signal_id = str(signal["signal_id"])
        snapshot = dict(signal["snapshot"])
        try:
            frame, interval, source = bars_loader(snapshot, now)
            if frame.empty or not interval:
                reason = source or "Keine belastbaren Kursdaten verfügbar."
                reason_fingerprint = hashlib.sha256(reason.encode("utf-8")).hexdigest()[:16]
                result = append_swing_signal_event(
                    signal_id,
                    "not_evaluable",
                    now.normalize(),
                    f"provider:{now.date().isoformat()}:{reason_fingerprint}",
                    {
                        "reason": reason,
                        "retry_allowed": True,
                    },
                    path,
                )
                summary["events_inserted" if result["inserted"] else "events_existing"] += 1
                summary["data_failures"] += 1
                continue
            candidates = evaluate_swing_signal_bars(
                snapshot,
                frame,
                interval=interval,
                evaluated_at=now,
            )
            for candidate in candidates:
                payload = dict(candidate["payload"])
                payload["market_data_source"] = source
                result = append_swing_signal_event(
                    signal_id,
                    str(candidate["event_type"]),
                    candidate["occurred_at"],
                    str(candidate["source_key"]),
                    payload,
                    path,
                )
                summary["events_inserted" if result["inserted"] else "events_existing"] += 1
            combined_signal = {**signal, "events": list(signal.get("events") or []) + candidates}
            if _is_terminal(combined_signal):
                fx_status, pending_reason = _append_fx_valuation(
                    combined_signal,
                    path=path,
                    fx_loader=fx_loader,
                )
                summary[f"fx_valuations_{fx_status}"] += 1
                if pending_reason:
                    summary["fx_pending_reasons"].append(
                        f"{(snapshot.get('asset') or {}).get('ticker', signal_id)}: {pending_reason}"
                    )
        except Exception as exc:
            summary["errors"].append(f"{(snapshot.get('asset') or {}).get('ticker', signal_id)}: {exc}")
    controls = load_swing_rejection_controls(path)
    summary["rejection_controls_total"] = len(controls)
    for control in controls:
        snapshot = dict(control.get("snapshot") or {})
        existing_horizons = {
            int(event.get("horizon_sessions"))
            for event in control.get("events") or []
            if event.get("horizon_sessions") is not None
        }
        if all(horizon in existing_horizons for horizon in COUNTERFACTUAL_HORIZONS):
            continue
        try:
            signal_day = pd.Timestamp(snapshot.get("signal_day")).date()
        except Exception:
            continue
        earliest_due = min(
            signal_day + timedelta(days=7 if horizon == 5 else 28)
            for horizon in COUNTERFACTUAL_HORIZONS
            if horizon not in existing_horizons
        )
        current_day = now.tz_convert(None).date() if now.tzinfo else now.date()
        if current_day < earliest_due:
            continue
        try:
            frame, interval, _source = bars_loader(
                {"asset": {"ticker": snapshot.get("ticker")}},
                now,
            )
            if frame.empty or not interval:
                summary["rejection_control_data_pending"] += 1
                continue
            candidates = _rejection_control_outcome_candidates(
                control,
                frame,
                interval=interval,
                evaluated_at=now,
            )
            if not candidates:
                summary["rejection_control_data_pending"] += 1
            for candidate in candidates:
                stored = append_swing_rejection_control_event(
                    str(control["control_id"]),
                    int(candidate["horizon_sessions"]),
                    candidate["occurred_at"],
                    dict(candidate["payload"]),
                    path,
                )
                key = (
                    "rejection_control_events_inserted"
                    if stored["inserted"]
                    else "rejection_control_events_existing"
                )
                summary[key] += 1
        except Exception as exc:
            summary["errors"].append(
                f"{snapshot.get('ticker', control.get('control_id'))} Ablehnungskontrolle: {exc}"
            )
    summary["store_audit"] = swing_forward_store_audit(path)
    return summary
