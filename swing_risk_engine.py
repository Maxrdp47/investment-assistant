from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping

from trade_republic_reference import build_trade_republic_execution_plan
from trading_assistant import calculate_position_size, finalize_swing_order_plan


SWING_RISK_ENGINE_VERSION = "swing-risk-engine-2026.08.18-v1"
ALLOWED_EXECUTION_MODES = {"analysis_only", "paper_only", "shadow_only"}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def apply_swing_risk_engine(
    candidate: Mapping[str, object],
    settings: Mapping[str, object],
    *,
    current_exposure_eur: float,
    current_risk_eur: float,
    execution_mode: str = "analysis_only",
) -> dict:
    """Create one authoritative, non-broker risk decision for every downstream mode."""
    mode = str(execution_mode)
    if mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError(f"Nicht erlaubter Ausführungsmodus: {mode}")
    result = dict(candidate)
    plan_direction = str(dict(result.get("order_plan") or {}).get("direction") or "").strip()
    candidate_direction = str(result.get("direction") or plan_direction or "Long").strip()
    if candidate_direction.lower() != "long" or (
        plan_direction and plan_direction.lower() != "long"
    ):
        raise ValueError(
            "Short-Signale sind für Scanner, Risk Engine, Paper und Shadow nicht freigegeben."
        )
    required = ("entry_reference_eur", "stop_eur", "order_plan")
    missing = [name for name in required if not result.get(name)]
    if missing:
        raise ValueError(f"Risk Engine: Pflichtdaten fehlen: {', '.join(missing)}")
    position_size = calculate_position_size(
        settings.get("trading_capital_eur"),
        _finite(settings.get("max_risk_pct")),
        _finite(result["entry_reference_eur"]),
        _finite(result["stop_eur"]),
        asset_type=str(result.get("asset_type") or "Aktie"),
        max_total_exposure_pct=_finite(settings.get("max_total_exposure_pct")),
        current_exposure_eur=_finite(current_exposure_eur),
        max_position_exposure_pct=_finite(settings.get("max_position_exposure_pct")),
        max_total_risk_pct=(
            _finite(settings.get("max_total_open_risk_pct"))
            if settings.get("max_total_open_risk_pct") is not None
            else None
        ),
        current_risk_eur=_finite(current_risk_eur),
        target_1_eur=result.get("target_1_eur"),
        target_2_eur=result.get("target_2_eur"),
    )
    result["position_size"] = position_size
    result["order_plan"] = finalize_swing_order_plan(
        dict(result["order_plan"]), position_size
    )
    result["trade_republic_execution_plan"] = build_trade_republic_execution_plan(
        dict(result["order_plan"]),
        dict(result.get("trade_republic") or {}),
        dict(result.get("trade_republic_price") or {}),
        trading_capital_eur=settings.get("trading_capital_eur"),
        max_risk_pct=_finite(settings.get("max_risk_pct")),
        asset_type=str(result.get("asset_type") or "Aktie"),
        max_total_exposure_pct=_finite(settings.get("max_total_exposure_pct")),
        current_exposure_eur=_finite(current_exposure_eur),
        max_position_exposure_pct=_finite(settings.get("max_position_exposure_pct")),
        max_total_risk_pct=(
            _finite(settings.get("max_total_open_risk_pct"))
            if settings.get("max_total_open_risk_pct") is not None
            else None
        ),
        current_risk_eur=_finite(current_risk_eur),
    )
    capital_supplied = settings.get("trading_capital_eur") is not None
    approved = bool(
        not capital_supplied or _finite(position_size.get("quantity")) > 0
    )
    decision = {
        "risk_engine_version": SWING_RISK_ENGINE_VERSION,
        "risk_policy_version": str(settings.get("risk_policy_version") or "unknown"),
        "execution_mode": mode,
        "approved": approved,
        "reason": (
            "Risk Check bestanden."
            if approved
            else str(position_size.get("explanation") or "Risk Check abgelehnt.")
        ),
        "input_state": {
            "current_exposure_eur": _finite(current_exposure_eur),
            "current_risk_eur": _finite(current_risk_eur),
        },
        "paper_only": mode == "paper_only",
        "shadow_only": mode == "shadow_only",
        "broker_adapter_present": False,
        "broker_order_allowed": False,
        "broker_order_sent": False,
    }
    decision["decision_fingerprint"] = _fingerprint(decision)
    result["risk_decision"] = decision
    return result


def validate_risk_decision(candidate: Mapping[str, object], *, required_mode: str) -> None:
    decision = dict(candidate.get("risk_decision") or {})
    fingerprint = str(decision.pop("decision_fingerprint", ""))
    if decision.get("risk_engine_version") != SWING_RISK_ENGINE_VERSION:
        raise ValueError("Risk Engine wurde umgangen oder besitzt die falsche Version.")
    if decision.get("execution_mode") != required_mode:
        raise ValueError("Risk-Entscheidung gehört nicht zum erforderlichen Ausführungsmodus.")
    if not fingerprint or fingerprint != _fingerprint(decision):
        raise ValueError("Risk-Entscheidung besitzt keinen gültigen Fingerabdruck.")
    if decision.get("broker_order_allowed") or decision.get("broker_order_sent"):
        raise ValueError("Broker-Ausführung ist in dieser Architektur verboten.")
