from __future__ import annotations

"""Frozen technical-integrity contract for Multi-Asset Opportunity Discovery v1.

This module is research infrastructure only.  It cannot start the later full
Development scan and has no production, paper, shadow, broker or order path.
"""

import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from swing_broad_research import BROAD_RESEARCH_SPLIT_VERSION, broad_research_split
from swing_research_identity_v3 import dependency_episode_report_v3


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT_PATH = PROJECT_ROOT / "config" / "multi_asset_discovery_v1.json"
DEFAULT_FEATURE_STORE = PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_pilot_features.sqlite3"
DEFAULT_OUTCOME_STORE = PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_pilot_outcomes.sqlite3"

DISCOVERY_VERSION = "multi-asset-opportunity-discovery-2026.08.31-v1"
FEATURE_VERSION = "multi-asset-discovery-features-2026.08.31-v1"
OUTCOME_VERSION = "multi-asset-discovery-outcomes-2026.08.31-v1"
PILOT_VERSION = "multi-asset-discovery-integrity-pilot-2026.08.31-v1"

ALLOWED_ASSET_CLASSES = {"EQUITIES", "ETF", "FX", "CRYPTO"}
ALLOWED_MISSINGNESS = {
    "AVAILABLE",
    "UNKNOWN",
    "UNAVAILABLE",
    "SHADOW",
    "PROVIDER_FAILURE",
    "STRUCTURAL_NOT_APPLICABLE",
}


class MultiAssetDiscoveryContractError(ValueError):
    """A value or operation violates the immutable v1 research contract."""


_FEATURE_CONTEXT_TOKEN = object()


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        stamp = pd.Timestamp(value)
        return stamp.isoformat()
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return float(value)
    return value


def canonical_json(value: object) -> str:
    return json.dumps(
        _clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_discovery_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("contract_version") != DISCOVERY_VERSION:
        raise MultiAssetDiscoveryContractError("Unerwartete Discovery-Vertragsversion.")
    if set(payload.get("market_scope") or []) != ALLOWED_ASSET_CLASSES:
        raise MultiAssetDiscoveryContractError("Der v1-Market-Scope wurde verändert.")
    if payload.get("analysis_resolution") != "completed_daily_bars_only":
        raise MultiAssetDiscoveryContractError("Discovery v1 ist ausschließlich daily.")
    if payload.get("asset_class_analysis") != "strictly_separate":
        raise MultiAssetDiscoveryContractError("Assetklassen dürfen nicht vermischt werden.")
    if payload["candidate_generation"].get("full_development_scan_allowed") is not False:
        raise MultiAssetDiscoveryContractError("Der große Development-Scan muss gesperrt bleiben.")
    if payload["outcome_contract"].get("horizon_daily_observations") != 252:
        raise MultiAssetDiscoveryContractError("Der Outcome-Horizont muss 252 Beobachtungen betragen.")
    if payload["stage_contract"].get("split_version") != BROAD_RESEARCH_SPLIT_VERSION:
        raise MultiAssetDiscoveryContractError("Der Stage-Split weicht vom eingefrorenen Vertrag ab.")
    if set(payload["feature_contract"].get("missingness_states") or []) != ALLOWED_MISSINGNESS:
        raise MultiAssetDiscoveryContractError("Missingness-Zustände wurden verändert.")
    models = payload["safe_zone_contract"].get("models") or []
    if models != [
        "A_CONFIRMED_SWING_LOW",
        "B_CONFIRMED_SUPPORT_ZONE",
        "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
    ]:
        raise MultiAssetDiscoveryContractError("Discovery v1 benötigt exakt drei Safe-Zone-Modelle.")
    if any(value is not False for value in payload["lifecycle"].values()):
        raise MultiAssetDiscoveryContractError("Alle späteren Lifecycle-Stufen müssen geschlossen bleiben.")
    payload["contract_fingerprint"] = fingerprint(payload)
    return payload


def code_fingerprint() -> str:
    files = (
        Path(__file__),
        PROJECT_ROOT / "scripts" / "run_multi_asset_discovery_v1_pilot.py",
        PROJECT_ROOT / "historical_dependency_policy.py",
        PROJECT_ROOT / "fx_historical_remediation.py",
    )
    return fingerprint(
        {
            "version": DISCOVERY_VERSION,
            "files": [
                {"path": path.relative_to(PROJECT_ROOT).as_posix(), "sha256": file_sha256(path)}
                for path in files
                if path.exists()
            ],
        }
    )


def build_contract_freeze(
    *,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    source_snapshots: Mapping[str, object],
    git_branch: str,
    git_commit: str,
    frozen_at: str,
) -> dict[str, object]:
    contract = load_discovery_contract(contract_path)
    feature_contract = contract["feature_contract"]
    outcome_contract = contract["outcome_contract"]
    payload: dict[str, object] = {
        "freeze_version": "multi-asset-discovery-contract-freeze-2026.08.31-v1",
        "frozen_at": frozen_at,
        "contract": contract,
        "contract_fingerprint": contract["contract_fingerprint"],
        "code_fingerprint": code_fingerprint(),
        "feature_contract_fingerprint": fingerprint(feature_contract),
        "outcome_contract_fingerprint": fingerprint(outcome_contract),
        "universe_fingerprint": fingerprint(contract["pilot_contract"]),
        "identity_contract_fingerprint": fingerprint(contract["dependency_contract"]),
        "dependency_contract_fingerprint": fingerprint(
            {
                "dependency": contract["dependency_contract"],
                "horizon": outcome_contract["horizon_daily_observations"],
            }
        ),
        "stage_split_fingerprint": fingerprint(contract["stage_contract"]),
        "safe_zone_fingerprint": fingerprint(contract["safe_zone_contract"]),
        "event_pit_availability_fingerprint": fingerprint(contract["point_in_time"]),
        "dataset_fingerprint": str(source_snapshots.get("dataset_fingerprint") or ""),
        "source_snapshots": dict(source_snapshots),
        "git": {"branch": git_branch, "commit": git_commit},
        "full_development_scan_started": False,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "true_forward_opened": False,
        "production_strategy_changed": False,
    }
    required = (
        "dataset_fingerprint",
        "identity_registry_fingerprint",
        "fx_store_sha256",
        "dataset_manifest_sha256",
    )
    missing = [key for key in required if not source_snapshots.get(key)]
    if missing:
        raise MultiAssetDiscoveryContractError(f"Freeze-Quellen fehlen: {missing}")
    payload["freeze_fingerprint"] = fingerprint(payload)
    return payload


def verify_contract_freeze(freeze: Mapping[str, object]) -> bool:
    stored = str(freeze.get("freeze_fingerprint") or "")
    comparable = dict(freeze)
    comparable.pop("freeze_fingerprint", None)
    return bool(stored and stored == fingerprint(comparable))


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _available(value: object, *, known_at: str, source: str) -> dict[str, object]:
    return {
        "status": "AVAILABLE" if _number(value) is not None else "UNKNOWN",
        "value": _number(value),
        "known_at": known_at,
        "source": source,
    }


def _missing(status: str, reason: str) -> dict[str, object]:
    if status not in ALLOWED_MISSINGNESS:
        raise MultiAssetDiscoveryContractError(f"Unbekannter Missingness-Status: {status}")
    return {"status": status, "value": None, "reason": reason}


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise MultiAssetDiscoveryContractError("OHLCV-Historie ist leer.")
    renamed = frame.rename(columns={str(column).lower(): str(column).title() for column in frame.columns})
    required = ["Open", "High", "Low", "Close"]
    missing = [column for column in required if column not in renamed]
    if missing:
        raise MultiAssetDiscoveryContractError(f"OHLC-Spalten fehlen: {missing}")
    selected = required + (["Volume"] if "Volume" in renamed else [])
    result = renamed[selected].copy()
    result.index = pd.to_datetime(result.index).tz_localize(None).normalize()
    result = result.loc[~result.index.duplicated(keep="last")].sort_index()
    for column in selected:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[required].isna().any().any():
        raise MultiAssetDiscoveryContractError("OHLC enthält fehlende oder nichtnumerische Werte.")
    if (result[required] <= 0).any().any():
        raise MultiAssetDiscoveryContractError("OHLC muss positiv sein.")
    if (result["High"] < result["Low"]).any():
        raise MultiAssetDiscoveryContractError("High liegt unter Low.")
    # Provider bars are retained byte-for-byte.  An Open/Close outside the
    # reported High/Low envelope is never silently repaired; it is exposed as
    # a fail-closed source-integrity fact and blocks Development readiness.
    result["OHLC_ENVELOPE_VALID"] = (
        (result["High"] >= result[["Open", "Close", "Low"]].max(axis=1))
        & (result["Low"] <= result[["Open", "Close", "High"]].min(axis=1))
    )
    if "Volume" not in result:
        result["Volume"] = np.nan
    return result


def prepare_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = normalize_ohlcv(frame)
    prior_close = result["Close"].shift(1)
    true_range = pd.concat(
        [
            result["High"] - result["Low"],
            (result["High"] - prior_close).abs(),
            (result["Low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    delta = result["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    result["ATR_14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    result["RSI_14"] = 100 - (100 / (1 + rs))
    for span in (20, 50, 200):
        result[f"EMA_{span}"] = result["Close"].ewm(span=span, adjust=False, min_periods=span).mean()
    result["RETURN_1"] = result["Close"].pct_change()
    for period in (5, 20, 60):
        result[f"RETURN_{period}"] = result["Close"].pct_change(period)
    result["VOLATILITY_20"] = result["RETURN_1"].rolling(20).std(ddof=0)
    result["VOLATILITY_60"] = result["RETURN_1"].rolling(60).std(ddof=0)
    result["OVERNIGHT_RETURN"] = result["Open"] / prior_close - 1
    result["INTRADAY_RETURN"] = result["Close"] / result["Open"] - 1
    result["GAP_ATR"] = (result["Open"] - prior_close) / result["ATR_14"]
    result["VOLUME_AVG_20"] = result["Volume"].rolling(20).mean()
    result["VOLUME_RATIO_20"] = result["Volume"] / result["VOLUME_AVG_20"]
    result["DOLLAR_VOLUME_20"] = (result["Close"] * result["Volume"]).rolling(20).mean()
    result["ATR_PCT"] = result["ATR_14"] / result["Close"]
    return result


def _freeze_contract_value(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_contract_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_contract_value(item) for item in value)
    return value


@dataclass(frozen=True)
class PreparedFeatureSnapshotContext:
    """Validated immutable-by-contract inputs reused for many signal rows."""

    prepared_frame: pd.DataFrame
    discovery_contract: Mapping[str, object]
    ohlc_anomaly_prefix_counts: tuple[int, ...]
    frame_length: int
    first_timestamp: pd.Timestamp | None
    last_timestamp: pd.Timestamp | None
    _validation_token: object


def prepare_feature_snapshot_context(
    *,
    frame: pd.DataFrame,
    prepared_frame: pd.DataFrame | None = None,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> PreparedFeatureSnapshotContext:
    """Load/validate the frozen contract and OHLC prefix evidence exactly once.

    The returned context is tied to the exact prepared-frame object.  Callers
    must finish constructing that frame before this step and may not mutate it
    afterwards.
    """

    prepared = (
        prepared_frame if prepared_frame is not None else prepare_indicators(frame)
    )
    if "OHLC_ENVELOPE_VALID" not in prepared.columns:
        raise MultiAssetDiscoveryContractError(
            "Prepared Feature-Frame enthält keine OHLC-Integritätsspalte."
        )
    if not pd.api.types.is_bool_dtype(prepared["OHLC_ENVELOPE_VALID"].dtype):
        raise MultiAssetDiscoveryContractError(
            "OHLC-Integritätsspalte im Feature-Kontext ist nicht boolesch."
        )
    contract = load_discovery_contract(Path(contract_path))
    invalid_flags = (~prepared["OHLC_ENVELOPE_VALID"]).fillna(False).astype(np.int64)
    prefix_counts = tuple(
        int(value) for value in invalid_flags.cumsum().to_numpy(dtype=np.int64)
    )
    return PreparedFeatureSnapshotContext(
        prepared_frame=prepared,
        discovery_contract=_freeze_contract_value(contract),
        ohlc_anomaly_prefix_counts=prefix_counts,
        frame_length=len(prepared),
        first_timestamp=(pd.Timestamp(prepared.index[0]) if len(prepared) else None),
        last_timestamp=(pd.Timestamp(prepared.index[-1]) if len(prepared) else None),
        _validation_token=_FEATURE_CONTEXT_TOKEN,
    )


def _confirmed_swings(
    prepared: pd.DataFrame,
    end_position: int,
    *,
    kind: str,
) -> list[dict[str, object]]:
    if kind not in {"low", "high"}:
        raise ValueError(kind)
    values = prepared["Low" if kind == "low" else "High"].to_numpy(dtype=float)
    closes = prepared["Close"].to_numpy(dtype=float)
    atrs = prepared["ATR_14"].to_numpy(dtype=float)
    swings: list[dict[str, object]] = []
    for candidate in range(2, max(2, end_position - 1)):
        if candidate + 2 > end_position or not math.isfinite(atrs[candidate]):
            continue
        neighborhood = values[candidate - 2 : candidate + 3]
        price = values[candidate]
        is_pivot = price <= np.min(neighborhood) if kind == "low" else price >= np.max(neighborhood)
        if not is_pivot:
            continue
        threshold = price + atrs[candidate] if kind == "low" else price - atrs[candidate]
        confirmed = None
        for position in range(candidate + 2, end_position + 1):
            if (kind == "low" and closes[position] >= threshold) or (
                kind == "high" and closes[position] <= threshold
            ):
                confirmed = position
                break
        if confirmed is None:
            continue
        swings.append(
            {
                "kind": kind,
                "candidate_position": candidate,
                "candidate_day": prepared.index[candidate].date().isoformat(),
                "confirmed_position": confirmed,
                "confirmed_day": prepared.index[confirmed].date().isoformat(),
                "price": float(price),
                "atr_14_at_reaction": float(atrs[candidate]),
            }
        )
    return swings


def build_safe_zones(prepared: pd.DataFrame, position: int) -> dict[str, object]:
    atr = _number(prepared.iloc[position].get("ATR_14"))
    lows = _confirmed_swings(prepared, position, kind="low")
    last_low = max(lows, key=lambda item: int(item["confirmed_position"])) if lows else None
    support = None
    for right_index in range(len(lows) - 1, 0, -1):
        right = lows[right_index]
        for left_index in range(right_index - 1, -1, -1):
            left = lows[left_index]
            limit = min(float(left["atr_14_at_reaction"]), float(right["atr_14_at_reaction"]))
            if abs(float(left["price"]) - float(right["price"])) <= limit:
                support = {
                    "lower": min(float(left["price"]), float(right["price"])),
                    "upper": max(float(left["price"]), float(right["price"])),
                    "reaction_days": [left["candidate_day"], right["candidate_day"]],
                    "confirmed_days": [left["confirmed_day"], right["confirmed_day"]],
                    "confirmed_position": max(
                        int(left["confirmed_position"]), int(right["confirmed_position"])
                    ),
                }
                break
        if support is not None:
            break
    zone_a = (
        {
            "model": "A_CONFIRMED_SWING_LOW",
            "status": "AVAILABLE",
            "lower": float(last_low["price"]),
            "upper": float(last_low["price"]),
            "source": last_low,
        }
        if last_low
        else {"model": "A_CONFIRMED_SWING_LOW", "status": "UNAVAILABLE", "reason": "NO_CONFIRMED_SWING_LOW"}
    )
    zone_b = (
        {"model": "B_CONFIRMED_SUPPORT_ZONE", "status": "AVAILABLE", **support}
        if support
        else {
            "model": "B_CONFIRMED_SUPPORT_ZONE",
            "status": "UNAVAILABLE",
            "reason": "TWO_CONFIRMED_REACTIONS_NOT_AVAILABLE",
        }
    )
    base = support or (
        {"lower": float(last_low["price"]), "upper": float(last_low["price"]), "source": last_low}
        if last_low
        else None
    )
    zone_c = (
        {
            "model": "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
            "status": "AVAILABLE",
            "lower": float(base["lower"]) - 0.5 * float(atr),
            "upper": float(base["upper"]),
            "base_model": "B_CONFIRMED_SUPPORT_ZONE" if support else "A_CONFIRMED_SWING_LOW",
            "atr_14": float(atr),
        }
        if base is not None and atr is not None
        else {
            "model": "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
            "status": "UNAVAILABLE",
            "reason": "STRUCTURE_OR_ATR_UNAVAILABLE",
        }
    )
    return {
        "safe_zone_version": "multi-asset-safe-zones-2026.08.31-v1",
        "A": zone_a,
        "B": zone_b,
        "C": zone_c,
        "confirmed_swing_low_count": len(lows),
        "original_zone_immutable": True,
    }


def build_sell_zones(
    prepared: pd.DataFrame,
    position: int,
    safe_zones: Mapping[str, object],
) -> dict[str, object]:
    row = prepared.iloc[position]
    close = float(row["Close"])
    atr = _number(row.get("ATR_14"))
    highs = _confirmed_swings(prepared, position, kind="high")
    above = [item for item in highs if float(item["price"]) > close]
    resistance = min(above, key=lambda item: float(item["price"])) if above else None
    zone_a = (
        {"status": "AVAILABLE", "value": float(resistance["price"]), "source": resistance}
        if resistance
        else {"status": "UNAVAILABLE", "value": None, "reason": "NO_PRIOR_CONFIRMED_RESISTANCE_ABOVE_CLOSE"}
    )
    base = dict(safe_zones.get("B") or {})
    if base.get("status") != "AVAILABLE":
        base = dict(safe_zones.get("A") or {})
    if resistance and base.get("status") == "AVAILABLE":
        base_upper = float(base["upper"])
        projection = float(resistance["price"]) + (float(resistance["price"]) - base_upper)
        zone_b = {"status": "AVAILABLE", "value": projection, "structural_base_upper": base_upper}
    else:
        zone_b = {"status": "UNAVAILABLE", "value": None, "reason": "STRUCTURAL_ANCHORS_UNAVAILABLE"}
    zone_c = (
        {"status": "AVAILABLE", "value": close + 2.0 * float(atr), "signal_close": close, "atr_14": atr}
        if atr is not None
        else {"status": "UNAVAILABLE", "value": None, "reason": "ATR14_UNAVAILABLE"}
    )
    return {
        "sell_zone_version": "multi-asset-sell-zones-2026.08.31-v1",
        "A": zone_a,
        "B": zone_b,
        "C": zone_c,
        "measurement_only": True,
        "automatic_exit_allowed": False,
    }


def _market_regime(row: pd.Series) -> str:
    close = _number(row.get("Close"))
    ema20 = _number(row.get("EMA_20"))
    ema50 = _number(row.get("EMA_50"))
    ema200 = _number(row.get("EMA_200"))
    if None in {close, ema20, ema50, ema200}:
        return "UNKNOWN"
    if close > ema20 > ema50 > ema200:
        return "UPTREND"
    if close < ema20 < ema50 < ema200:
        return "DOWNTREND"
    return "MIXED"


def build_feature_snapshot(
    *,
    asset: Mapping[str, object],
    frame: pd.DataFrame,
    decision_position: int,
    decision_time: str,
    dataset_fingerprint: str,
    event_facts: Sequence[Mapping[str, object]] = (),
    prepared_frame: pd.DataFrame | None = None,
    safe_zones_override: Mapping[str, object] | None = None,
    sell_zones_override: Mapping[str, object] | None = None,
    execution_contract_version: str = DISCOVERY_VERSION,
    prepared_context: PreparedFeatureSnapshotContext | None = None,
) -> dict[str, object]:
    prepared = prepared_frame if prepared_frame is not None else prepare_indicators(frame)
    if prepared_context is None:
        minimum = int(
            load_discovery_contract()["point_in_time"][
                "minimum_history_observations"
            ]
        )
        ohlc_anomaly_count: int | None = None
    else:
        if prepared_context._validation_token is not _FEATURE_CONTEXT_TOKEN:
            raise MultiAssetDiscoveryContractError(
                "Feature-Fastpath-Kontext wurde nicht validiert."
            )
        if prepared is not prepared_context.prepared_frame:
            raise MultiAssetDiscoveryContractError(
                "Feature-Fastpath-Kontext gehört nicht zum Prepared Frame."
            )
        if (
            len(prepared) != prepared_context.frame_length
            or (
                len(prepared)
                and pd.Timestamp(prepared.index[0])
                != prepared_context.first_timestamp
            )
            or (
                len(prepared)
                and pd.Timestamp(prepared.index[-1])
                != prepared_context.last_timestamp
            )
        ):
            raise MultiAssetDiscoveryContractError(
                "Prepared Frame wurde nach Validierung strukturell verändert."
            )
        minimum = int(
            prepared_context.discovery_contract["point_in_time"][
                "minimum_history_observations"
            ]
        )
        if decision_position < 0 or decision_position >= len(
            prepared_context.ohlc_anomaly_prefix_counts
        ):
            raise MultiAssetDiscoveryContractError(
                "Feature-Position liegt außerhalb des validierten Kontexts."
            )
        ohlc_anomaly_count = prepared_context.ohlc_anomaly_prefix_counts[
            decision_position
        ]
    if decision_position < minimum - 1:
        raise MultiAssetDiscoveryContractError("Der Entscheidungspunkt besitzt zu wenig Historie.")
    if decision_position >= len(prepared) - 1:
        raise MultiAssetDiscoveryContractError("Für den Referenzeinstieg fehlt die nächste Session.")
    asset_class = str(asset.get("asset_class") or "").upper()
    if asset_class not in ALLOWED_ASSET_CLASSES:
        raise MultiAssetDiscoveryContractError("Unbekannte Assetklasse.")
    decision_stamp = pd.Timestamp(decision_time)
    if decision_stamp.tzinfo is None:
        raise MultiAssetDiscoveryContractError("decision_time benötigt eine Zeitzone.")
    signal_day = prepared.index[decision_position].date().isoformat()
    if decision_stamp.date().isoformat() < signal_day:
        raise MultiAssetDiscoveryContractError("decision_time liegt vor der Signalkerze.")
    row = prepared.iloc[decision_position]
    safe_zones = (
        dict(safe_zones_override)
        if safe_zones_override is not None
        else build_safe_zones(prepared, decision_position)
    )
    sell_zones = (
        dict(sell_zones_override)
        if sell_zones_override is not None
        else build_sell_zones(prepared, decision_position, safe_zones)
    )
    allowed_events = []
    for event in event_facts:
        known_at = event.get("known_at")
        if not known_at:
            raise MultiAssetDiscoveryContractError("Event-Fakt ohne known_at.")
        if pd.Timestamp(str(known_at)) > decision_stamp:
            raise MultiAssetDiscoveryContractError("Zukünftiger Event-Fakt im Snapshot.")
        required = {"known_at", "published_at", "effective_at", "source", "coverage_status", "pit_eligible"}
        if not required.issubset(event):
            raise MultiAssetDiscoveryContractError("Event-Fakt verletzt den PIT-Vertrag.")
        allowed_events.append(dict(event))
    technical_names = (
        "RETURN_1",
        "RETURN_5",
        "RETURN_20",
        "RETURN_60",
        "EMA_20",
        "EMA_50",
        "EMA_200",
        "RSI_14",
        "ATR_14",
        "ATR_PCT",
        "VOLATILITY_20",
        "VOLATILITY_60",
        "OVERNIGHT_RETURN",
        "INTRADAY_RETURN",
        "GAP_ATR",
        "VOLUME_RATIO_20",
        "DOLLAR_VOLUME_20",
    )
    features = {
        name.lower(): _available(row.get(name), known_at=decision_time, source="completed_daily_ohlcv")
        for name in technical_names
    }
    if asset_class == "FX":
        features["volume_ratio_20"] = _missing("STRUCTURAL_NOT_APPLICABLE", "FX_DAILY_VOLUME_UNRELIABLE")
        features["dollar_volume_20"] = _missing("STRUCTURAL_NOT_APPLICABLE", "FX_DAILY_VOLUME_UNRELIABLE")
    features["fundamental_context"] = _missing("UNAVAILABLE", "NOT_COLLECTED_FOR_TECHNICAL_PILOT")
    features["event_context"] = (
        {"status": "AVAILABLE", "value": allowed_events, "known_at": decision_time}
        if allowed_events
        else _missing("UNKNOWN", "NO_PIT_EVENT_FACT_AVAILABLE_FOR_PILOT_SNAPSHOT")
    )
    if ohlc_anomaly_count is None:
        ohlc_anomaly_count = int(
            (~prepared.iloc[: decision_position + 1]["OHLC_ENVELOPE_VALID"]).sum()
        )
    snapshot: dict[str, object] = {
        "feature_version": FEATURE_VERSION,
        "contract_version": execution_contract_version,
        "asset_id": str(asset.get("asset_id") or asset.get("ticker") or asset.get("pair_id")),
        "symbol": str(asset.get("ticker") or asset.get("pair_id")),
        "asset_class": asset_class,
        "listing_id": asset.get("listing_id"),
        "issuer_id": asset.get("issuer_id"),
        "mapping_status": str(asset.get("mapping_status") or "UNRESOLVED"),
        "dependency_status": str(asset.get("dependency_status") or "UNKNOWN"),
        "historical_dependency_policy_version": asset.get(
            "historical_dependency_policy_version"
        ),
        "historical_dependency_policy_fingerprint": asset.get(
            "historical_dependency_policy_fingerprint"
        ),
        "historical_dependency_reason": asset.get("historical_dependency_reason"),
        "identity_is_trading_feature": False,
        "signal_day": signal_day,
        "decision_time": decision_stamp.tz_convert("UTC").isoformat(),
        "known_at_lte_decision_time": True,
        "research_split": broad_research_split(signal_day),
        "dataset_fingerprint": dataset_fingerprint,
        "history_end_day": signal_day,
        "history_observations": decision_position + 1,
        "source_integrity": {
            "ohlc_envelope_anomaly_count_to_decision": ohlc_anomaly_count,
            "provider_values_repaired": False,
            "fail_closed_for_development_readiness": True,
        },
        "features": features,
        "market_regime": _market_regime(row),
        "safe_zones": safe_zones,
        "sell_zones": sell_zones,
        "candidate_selected_from_outcome": False,
        "predictive_prefilter_used": False,
        "composite_opportunity_score": None,
        "full_development_scan_started": False,
    }
    identity = {
        "asset_id": snapshot["asset_id"],
        "signal_day": signal_day,
        "contract_version": execution_contract_version,
        "dataset_fingerprint": dataset_fingerprint,
    }
    snapshot["case_id"] = f"mad1-{fingerprint(identity)[:32]}"
    snapshot["feature_fingerprint"] = fingerprint(snapshot)
    return snapshot


def _stage_end(signal_day: str) -> pd.Timestamp | None:
    day = pd.Timestamp(signal_day)
    split = broad_research_split(day)
    if split == "outside_contract":
        return None
    if day.year <= 2015:
        return {
            "development": pd.Timestamp("2012-12-31"),
            "validation": pd.Timestamp("2014-12-31"),
            "holdout": pd.Timestamp("2015-12-31"),
        }[split]
    return {
        "development": pd.Timestamp("2021-12-31"),
        "validation": pd.Timestamp("2023-12-31"),
        "holdout": pd.Timestamp.max.normalize(),
    }[split]


def _first_hit(values: pd.Series, threshold: float, *, mode: str) -> int | None:
    mask = values >= threshold if mode == "above" else values < threshold
    positions = np.flatnonzero(mask.to_numpy(dtype=bool))
    return int(positions[0] + 1) if len(positions) else None


def _checkpoint(
    future: pd.DataFrame,
    observations: int,
    *,
    entry: float,
    atr: float,
    risk: float,
) -> dict[str, object] | None:
    if len(future) < observations:
        return None
    part = future.iloc[:observations]
    high = float(part["High"].max())
    low = float(part["Low"].min())
    close = float(part.iloc[-1]["Close"])
    return {
        "observations": observations,
        "end_day": part.index[-1].date().isoformat(),
        "return_pct": (close / entry - 1) * 100,
        "mfe_pct": (high / entry - 1) * 100,
        "mae_pct": (low / entry - 1) * 100,
        "mfe_atr": (high - entry) / atr,
        "mae_atr": (low - entry) / atr,
        "mfe_r": (high - entry) / risk,
        "mae_r": (low - entry) / risk,
    }


def _ratchet_path(
    prepared: pd.DataFrame,
    signal_position: int,
    future_end_position: int,
    *,
    safe_zone_history: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    initial = (
        dict(safe_zone_history[signal_position])
        if safe_zone_history is not None
        else build_safe_zones(prepared, signal_position)
    )
    zone_c = dict(initial.get("C") or {})
    if zone_c.get("status") != "AVAILABLE":
        return {"status": "UNAVAILABLE", "updates": [], "never_lowered": True}
    current = float(zone_c["lower"])
    updates = []
    for position in range(signal_position + 1, future_end_position + 1):
        candidate_source = (
            safe_zone_history[position]
            if safe_zone_history is not None
            else build_safe_zones(prepared, position)
        )
        candidate = dict(candidate_source.get("C") or {})
        if candidate.get("status") != "AVAILABLE":
            continue
        proposed = float(candidate["lower"])
        if proposed > current:
            updates.append(
                {
                    "effective_day": prepared.index[position].date().isoformat(),
                    "prior_lower": current,
                    "new_lower": proposed,
                    "confirmed_structure_required": True,
                }
            )
            current = proposed
    return {
        "status": "AVAILABLE",
        "initial_lower": float(zone_c["lower"]),
        "final_lower": current,
        "updates": updates,
        "never_lowered": all(item["new_lower"] > item["prior_lower"] for item in updates),
    }


def build_outcome(
    *,
    feature_snapshot: Mapping[str, object],
    frame: pd.DataFrame,
    prepared_frame: pd.DataFrame | None = None,
    safe_zone_history: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if not feature_snapshot.get("feature_fingerprint"):
        raise MultiAssetDiscoveryContractError("Outcome benötigt einen eingefrorenen Feature-Snapshot.")
    prepared = prepared_frame if prepared_frame is not None else prepare_indicators(frame)
    signal_day = str(feature_snapshot["signal_day"])
    matching = np.flatnonzero(prepared.index == pd.Timestamp(signal_day))
    if len(matching) != 1:
        raise MultiAssetDiscoveryContractError("Signaltag ist in der Historie nicht eindeutig.")
    signal_position = int(matching[0])
    stage_end = _stage_end(signal_day)
    if stage_end is None:
        raise MultiAssetDiscoveryContractError("Signaltag liegt außerhalb des Stage-Vertrags.")
    available_positions = [
        position
        for position in range(signal_position + 1, len(prepared))
        if prepared.index[position] <= stage_end
    ]
    if not available_positions:
        outcome = {
            "outcome_version": OUTCOME_VERSION,
            "contract_version": feature_snapshot.get("contract_version")
            or DISCOVERY_VERSION,
            "case_id": feature_snapshot["case_id"],
            "feature_fingerprint": feature_snapshot["feature_fingerprint"],
            "asset_id": feature_snapshot["asset_id"],
            "symbol": feature_snapshot["symbol"],
            "asset_class": feature_snapshot["asset_class"],
            "listing_id": feature_snapshot.get("listing_id"),
            "issuer_id": feature_snapshot.get("issuer_id"),
            "mapping_status": feature_snapshot.get("mapping_status"),
            "dependency_status": feature_snapshot.get("dependency_status"),
            "status": "CENSORED_AT_STAGE_BOUNDARY",
            "reason": "NEXT_OPEN_OUTSIDE_STAGE",
            "research_split": feature_snapshot["research_split"],
            "signal_day": signal_day,
            "observations_available": 0,
            "requested_observations": 252,
            "future_features_written_to_feature_store": False,
            "no_intrabar_order_invented": True,
        }
        outcome["outcome_fingerprint"] = fingerprint(outcome)
        return outcome
    horizon_positions = available_positions[:252]
    entry_position = horizon_positions[0]
    future = prepared.iloc[horizon_positions]
    entry = float(prepared.iloc[entry_position]["Open"])
    signal_close = float(prepared.iloc[signal_position]["Close"])
    atr = _number(prepared.iloc[signal_position].get("ATR_14"))
    zone_c = dict((feature_snapshot.get("safe_zones") or {}).get("C") or {})
    invalidation = _number(zone_c.get("lower"))
    if atr is None or invalidation is None or entry <= invalidation:
        raise MultiAssetDiscoveryContractError("Strukturelles R ist für den Pilotfall nicht definiert.")
    risk = entry - invalidation
    highs = future["High"]
    lows = future["Low"]
    closes = future["Close"]
    max_high = float(highs.max())
    min_low = float(lows.min())
    max_high_offset = int(np.argmax(highs.to_numpy(dtype=float)))
    peak_close_after = float(closes.iloc[max_high_offset:].min()) if max_high_offset < len(closes) else float(closes.iloc[-1])
    safe_breaches: dict[str, object] = {}
    for key in ("A", "B", "C"):
        zone = dict((feature_snapshot.get("safe_zones") or {}).get(key) or {})
        lower = _number(zone.get("lower"))
        safe_breaches[key] = (
            {
                "status": "AVAILABLE",
                "lower": lower,
                "intraday_breach_observation": _first_hit(lows, float(lower), mode="below"),
                "close_breach_observation": _first_hit(closes, float(lower), mode="below"),
            }
            if lower is not None
            else {"status": "UNAVAILABLE", "reason": zone.get("reason")}
        )
    sell_measurements: dict[str, object] = {}
    for key in ("A", "B", "C"):
        zone = dict((feature_snapshot.get("sell_zones") or {}).get(key) or {})
        value = _number(zone.get("value"))
        sell_measurements[key] = (
            {
                "status": "AVAILABLE",
                "value": value,
                "hit_observation": _first_hit(highs, float(value), mode="above"),
                "max_overshoot_pct": max(0.0, (max_high / float(value) - 1) * 100),
            }
            if value is not None
            else {"status": "UNAVAILABLE", "reason": zone.get("reason")}
        )
    checkpoints = {
        str(observation): _checkpoint(
            future,
            observation,
            entry=entry,
            atr=float(atr),
            risk=risk,
        )
        for observation in (20, 60, 120, 252)
    }
    r_hits = {
        str(level): _first_hit(highs, entry + level * risk, mode="above")
        for level in (1.0, 2.0, 3.0)
    }
    final_close = float(future.iloc[-1]["Close"])
    outcome: dict[str, object] = {
        "outcome_version": OUTCOME_VERSION,
        "contract_version": feature_snapshot.get("contract_version")
        or DISCOVERY_VERSION,
        "case_id": feature_snapshot["case_id"],
        "feature_fingerprint": feature_snapshot["feature_fingerprint"],
        "asset_id": feature_snapshot["asset_id"],
        "symbol": feature_snapshot["symbol"],
        "asset_class": feature_snapshot["asset_class"],
        "listing_id": feature_snapshot.get("listing_id"),
        "issuer_id": feature_snapshot.get("issuer_id"),
        "mapping_status": feature_snapshot.get("mapping_status"),
        "dependency_status": feature_snapshot.get("dependency_status"),
        "research_split": feature_snapshot["research_split"],
        "signal_day": signal_day,
        "entry_day": prepared.index[entry_position].date().isoformat(),
        "entry_open": entry,
        "signal_close": signal_close,
        "entry_gap_pct": (entry / signal_close - 1) * 100,
        "entry_gap_atr": (entry - signal_close) / float(atr),
        "original_structural_invalidation": invalidation,
        "structural_risk": risk,
        "observations_available": len(future),
        "requested_observations": 252,
        "outcome_end_day": future.index[-1].date().isoformat(),
        "source_integrity": {
            "ohlc_envelope_anomaly_count_in_outcome": int(
                (~future["OHLC_ENVELOPE_VALID"]).sum()
            ),
            "provider_values_repaired": False,
            "fail_closed_for_development_readiness": True,
        },
        "status": "COMPLETE" if len(future) == 252 else "CENSORED_AT_STAGE_BOUNDARY",
        "censoring_reason": None if len(future) == 252 else "STAGE_BOUNDARY_BEFORE_252_OBSERVATIONS",
        "mfe_pct": (max_high / entry - 1) * 100,
        "mae_pct": (min_low / entry - 1) * 100,
        "mfe_atr": (max_high - entry) / float(atr),
        "mae_atr": (min_low - entry) / float(atr),
        "mfe_r": (max_high - entry) / risk,
        "mae_r": (min_low - entry) / risk,
        "final_return_pct": (final_close / entry - 1) * 100,
        "time_to_mfe_observations": max_high_offset + 1,
        "time_to_structural_intraday_invalidation": _first_hit(lows, invalidation, mode="below"),
        "time_to_structural_close_invalidation": _first_hit(closes, invalidation, mode="below"),
        "r_level_hits": r_hits,
        "safe_zone_breaches": safe_breaches,
        "sell_zone_measurements": sell_measurements,
        "checkpoints": checkpoints,
        "protective_ratchet": _ratchet_path(
            prepared,
            signal_position,
            horizon_positions[-1],
            safe_zone_history=safe_zone_history,
        ),
        "path_quality": {
            "mfe_to_mae_ratio": ((max_high - entry) / max(entry - min_low, 1e-12)),
            "positive_close_fraction": float((closes >= entry).mean()),
            "peak_giveback_r": (max_high - peak_close_after) / risk,
            "final_giveback_r": (max_high - final_close) / risk,
        },
        "deterioration": {
            "PRICE_STRUCTURE": {
                "close_below_signal_ema20_count": int(
                    (closes < float(prepared.iloc[signal_position]["EMA_20"])).sum()
                )
            },
            "MOMENTUM": {
                "rsi14_below_40_count": int((future["RSI_14"] < 40).fillna(False).sum())
            },
            "VOLATILITY": {
                "atr14_above_1_5x_signal_count": int(
                    (future["ATR_14"] > 1.5 * float(atr)).fillna(False).sum()
                )
            },
            "LIQUIDITY": (
                {"status": "STRUCTURAL_NOT_APPLICABLE"}
                if feature_snapshot["asset_class"] == "FX"
                else {
                    "volume_ratio_below_0_5_count": int(
                        (future["VOLUME_RATIO_20"] < 0.5).fillna(False).sum()
                    )
                }
            ),
            "EVENT": {"status": "UNKNOWN", "reason": "NO_PIT_EVENT_PATH_IN_TECHNICAL_PILOT"},
        },
        "future_features_written_to_feature_store": False,
        "no_intrabar_order_invented": True,
    }
    outcome["outcome_fingerprint"] = fingerprint(outcome)
    return outcome


def temporal_dependency_report(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    unknown = 0
    for case in cases:
        listing_id = str(case.get("listing_id") or "")
        if not listing_id:
            unknown += 1
            continue
        grouped[listing_id].append(
            (
                str(case.get("entry_day") or case.get("signal_day")),
                str(case.get("outcome_end_day") or case.get("signal_day")),
                str(case.get("case_id")),
            )
        )
    clusters = []
    for listing_id, intervals in sorted(grouped.items()):
        current_start = None
        current_end = None
        members: list[str] = []
        cluster_index = 0
        for start, end, case_id in sorted(intervals):
            if current_end is None or start > current_end:
                if members:
                    clusters.append(
                        {
                            "cluster_id": f"{listing_id}|{cluster_index}",
                            "listing_id": listing_id,
                            "start": current_start,
                            "end": current_end,
                            "case_ids": members,
                        }
                    )
                    cluster_index += 1
                current_start, current_end, members = start, end, [case_id]
            else:
                current_end = max(str(current_end), end)
                members.append(case_id)
        if members:
            clusters.append(
                {
                    "cluster_id": f"{listing_id}|{cluster_index}",
                    "listing_id": listing_id,
                    "start": current_start,
                    "end": current_end,
                    "case_ids": members,
                }
            )
    identity_cases = [
        {
            "issuer_id": case.get("issuer_id"),
            "listing_id": case.get("listing_id"),
            "mapping_status": case.get("mapping_status"),
            "dependency_status": case.get("dependency_status"),
            "signal_day": case.get("entry_day") or case.get("signal_day"),
            "label_end_day": case.get("outcome_end_day") or case.get("signal_day"),
        }
        for case in cases
    ]
    issuer_adjusted = dependency_episode_report_v3(identity_cases)
    payload = {
        "dependency_version": "swing-research-dependency-2026.08.29-v3",
        "raw_n": len(cases),
        "raw_n_claimed_independent": False,
        "temporal_listing_clusters": clusters,
        "temporal_listing_cluster_n": len(clusters),
        "unknown_listing_identity_n": unknown,
        "issuer_adjusted": issuer_adjusted,
        "unknown_dependency_contribution_to_effective_n": 0,
        "effective_n_le_raw_n": int(issuer_adjusted["effective_independent_issuer_count"]) <= len(cases),
    }
    payload["dependency_report_fingerprint"] = fingerprint(payload)
    return payload


def _connect_store(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=60)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def _append_only_triggers(table: str) -> str:
    return f"""
    CREATE TRIGGER IF NOT EXISTS {table}_no_update
    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'append_only'); END;
    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'append_only'); END;
    """


def initialize_feature_store(path: Path = DEFAULT_FEATURE_STORE) -> None:
    with _connect_store(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS contract_freezes (
                freeze_fingerprint TEXT PRIMARY KEY,
                freeze_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feature_rows (
                case_id TEXT PRIMARY KEY,
                feature_fingerprint TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                signal_day TEXT NOT NULL,
                feature_json TEXT NOT NULL
            );
            """
            + _append_only_triggers("contract_freezes")
            + _append_only_triggers("feature_rows")
        )


def initialize_outcome_store(path: Path = DEFAULT_OUTCOME_STORE) -> None:
    with _connect_store(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS outcome_rows (
                case_id TEXT PRIMARY KEY,
                outcome_fingerprint TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                outcome_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dependency_reports (
                dependency_report_fingerprint TEXT PRIMARY KEY,
                report_json TEXT NOT NULL
            );
            """
            + _append_only_triggers("outcome_rows")
            + _append_only_triggers("dependency_reports")
        )


def _insert_immutable(
    connection: sqlite3.Connection,
    *,
    table: str,
    key_column: str,
    key: str,
    fingerprint_column: str,
    content_fingerprint: str,
    columns: Sequence[str],
    values: Sequence[object],
) -> bool:
    existing = connection.execute(
        f"SELECT {fingerprint_column} FROM {table} WHERE {key_column}=?", (key,)
    ).fetchone()
    if existing is not None:
        if str(existing[0]) != content_fingerprint:
            raise MultiAssetDiscoveryContractError(f"Append-only-Konflikt in {table}: {key}")
        return False
    placeholders = ",".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", tuple(values)
    )
    return True


def record_freeze_and_features(
    freeze: Mapping[str, object],
    features: Sequence[Mapping[str, object]],
    *,
    path: Path = DEFAULT_FEATURE_STORE,
) -> dict[str, int]:
    if not verify_contract_freeze(freeze):
        raise MultiAssetDiscoveryContractError("Ungültiger Contract-Freeze.")
    initialize_feature_store(path)
    inserted = 0
    with _connect_store(path) as connection:
        _insert_immutable(
            connection,
            table="contract_freezes",
            key_column="freeze_fingerprint",
            key=str(freeze["freeze_fingerprint"]),
            fingerprint_column="freeze_fingerprint",
            content_fingerprint=str(freeze["freeze_fingerprint"]),
            columns=("freeze_fingerprint", "freeze_json"),
            values=(freeze["freeze_fingerprint"], canonical_json(freeze)),
        )
        for feature in features:
            inserted += int(
                _insert_immutable(
                    connection,
                    table="feature_rows",
                    key_column="case_id",
                    key=str(feature["case_id"]),
                    fingerprint_column="feature_fingerprint",
                    content_fingerprint=str(feature["feature_fingerprint"]),
                    columns=("case_id", "feature_fingerprint", "asset_class", "signal_day", "feature_json"),
                    values=(
                        feature["case_id"],
                        feature["feature_fingerprint"],
                        feature["asset_class"],
                        feature["signal_day"],
                        canonical_json(feature),
                    ),
                )
            )
    return {"features_inserted": inserted, "features_total": len(features)}


def record_outcomes_and_dependency(
    outcomes: Sequence[Mapping[str, object]],
    dependency: Mapping[str, object],
    *,
    path: Path = DEFAULT_OUTCOME_STORE,
) -> dict[str, int]:
    initialize_outcome_store(path)
    inserted = 0
    with _connect_store(path) as connection:
        for outcome in outcomes:
            content_fingerprint = str(outcome.get("outcome_fingerprint") or fingerprint(outcome))
            inserted += int(
                _insert_immutable(
                    connection,
                    table="outcome_rows",
                    key_column="case_id",
                    key=str(outcome["case_id"]),
                    fingerprint_column="outcome_fingerprint",
                    content_fingerprint=content_fingerprint,
                    columns=("case_id", "outcome_fingerprint", "asset_class", "outcome_json"),
                    values=(
                        outcome["case_id"],
                        content_fingerprint,
                        outcome.get("asset_class") or "UNKNOWN",
                        canonical_json(outcome),
                    ),
                )
            )
        report_fingerprint = str(dependency["dependency_report_fingerprint"])
        _insert_immutable(
            connection,
            table="dependency_reports",
            key_column="dependency_report_fingerprint",
            key=report_fingerprint,
            fingerprint_column="dependency_report_fingerprint",
            content_fingerprint=report_fingerprint,
            columns=("dependency_report_fingerprint", "report_json"),
            values=(report_fingerprint, canonical_json(dependency)),
        )
    return {"outcomes_inserted": inserted, "outcomes_total": len(outcomes)}


def audit_pilot_stores(
    *,
    feature_path: Path = DEFAULT_FEATURE_STORE,
    outcome_path: Path = DEFAULT_OUTCOME_STORE,
) -> dict[str, object]:
    with sqlite3.connect(f"file:{Path(feature_path).as_posix()}?mode=ro", uri=True) as feature_db:
        feature_quick = feature_db.execute("PRAGMA quick_check").fetchone()[0]
        feature_count = feature_db.execute("SELECT COUNT(*) FROM feature_rows").fetchone()[0]
        feature_columns = [row[1] for row in feature_db.execute("PRAGMA table_info(feature_rows)")]
    with sqlite3.connect(f"file:{Path(outcome_path).as_posix()}?mode=ro", uri=True) as outcome_db:
        outcome_quick = outcome_db.execute("PRAGMA quick_check").fetchone()[0]
        outcome_count = outcome_db.execute("SELECT COUNT(*) FROM outcome_rows").fetchone()[0]
        outcome_columns = [row[1] for row in outcome_db.execute("PRAGMA table_info(outcome_rows)")]
    return {
        "feature_store_quick_check": feature_quick,
        "outcome_store_quick_check": outcome_quick,
        "feature_rows": int(feature_count),
        "outcome_rows": int(outcome_count),
        "physically_separate_paths": Path(feature_path).resolve() != Path(outcome_path).resolve(),
        "outcome_columns_absent_from_feature_store": "outcome_json" not in feature_columns,
        "feature_columns_absent_from_outcome_store": "feature_json" not in outcome_columns,
    }


def checkpoint_pilot_stores(
    *,
    feature_path: Path = DEFAULT_FEATURE_STORE,
    outcome_path: Path = DEFAULT_OUTCOME_STORE,
) -> dict[str, object]:
    results: dict[str, object] = {}
    for name, path in (("feature_store", feature_path), ("outcome_store", outcome_path)):
        with sqlite3.connect(Path(path), timeout=60) as connection:
            row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        results[name] = {
            "busy": int(row[0]),
            "log_frames": int(row[1]),
            "checkpointed_frames": int(row[2]),
        }
    results["all_checkpointed"] = all(
        item["busy"] == 0 for item in results.values() if isinstance(item, dict)
    )
    return results


def evaluate_integrity_pilot(
    *,
    freeze: Mapping[str, object],
    features: Sequence[Mapping[str, object]],
    outcomes: Sequence[Mapping[str, object]],
    dependency: Mapping[str, object],
    store_audit: Mapping[str, object],
    deterministic_replay_match: bool,
) -> dict[str, object]:
    asset_classes = sorted({str(item.get("asset_class")) for item in features})
    gates = {
        "contract_freeze_valid": verify_contract_freeze(freeze),
        "all_asset_classes_present_and_separate": asset_classes == sorted(ALLOWED_ASSET_CLASSES),
        "fixed_small_pilot_only": len(features) == 11,
        "features_precede_outcomes": all(item.get("feature_fingerprint") for item in outcomes),
        "next_open_entry_only": all(
            item.get("entry_day") > item.get("signal_day")
            for item in outcomes
            if item.get("entry_day")
        ),
        "stage_censoring_exercised": any(
            item.get("status") == "CENSORED_AT_STAGE_BOUNDARY" for item in outcomes
        ),
        "safe_zone_models_exact": all(
            sorted((item.get("safe_zones") or {}).keys())
            == ["A", "B", "C", "confirmed_swing_low_count", "original_zone_immutable", "safe_zone_version"]
            for item in features
        ),
        "ratchet_never_lowers": all(
            bool((item.get("protective_ratchet") or {}).get("never_lowered"))
            for item in outcomes
            if item.get("protective_ratchet")
        ),
        "breaches_separate": all(
            all(
                "intraday_breach_observation" in zone and "close_breach_observation" in zone
                for zone in (item.get("safe_zone_breaches") or {}).values()
                if zone.get("status") == "AVAILABLE"
            )
            for item in outcomes
            if item.get("safe_zone_breaches")
        ),
        "checkpoints_present": all(
            set((item.get("checkpoints") or {}).keys()) == {"20", "60", "120", "252"}
            for item in outcomes
            if item.get("checkpoints")
        ),
        "dependency_fail_closed": dependency.get("unknown_dependency_contribution_to_effective_n") == 0,
        "effective_n_not_inflated": bool(dependency.get("effective_n_le_raw_n")),
        "stores_physically_and_semantically_separate": all(
            bool(store_audit.get(key))
            for key in (
                "physically_separate_paths",
                "outcome_columns_absent_from_feature_store",
                "feature_columns_absent_from_outcome_store",
            )
        ),
        "stores_integrity_ok": store_audit.get("feature_store_quick_check") == "ok"
        and store_audit.get("outcome_store_quick_check") == "ok",
        "deterministic_replay_match": deterministic_replay_match,
        "no_predictive_prefilter": all(item.get("predictive_prefilter_used") is False for item in features),
        "no_composite_score": all(item.get("composite_opportunity_score") is None for item in features),
        "no_large_scan": all(item.get("full_development_scan_started") is False for item in features),
        "no_ohlc_envelope_anomalies": all(
            int((item.get("source_integrity") or {}).get("ohlc_envelope_anomaly_count_to_decision") or 0)
            == 0
            for item in features
        )
        and all(
            int((item.get("source_integrity") or {}).get("ohlc_envelope_anomaly_count_in_outcome") or 0)
            == 0
            for item in outcomes
            if item.get("source_integrity")
        ),
        "later_lifecycle_closed": all(freeze.get(key) is False for key in (
            "validation_opened", "holdout_opened", "external_opened", "true_forward_opened"
        )),
    }
    ready = all(gates.values())
    payload: dict[str, object] = {
        "pilot_version": PILOT_VERSION,
        "status": (
            "READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT"
            if ready
            else "NOT_READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT"
        ),
        "gates": gates,
        "feature_rows": len(features),
        "outcome_rows": len(outcomes),
        "asset_classes": asset_classes,
        "dependency": dict(dependency),
        "store_audit": dict(store_audit),
        "performance_claim": None,
        "technical_integrity_only": True,
        "full_development_scan_started": False,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "true_forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
        "production_strategy_changed": False,
    }
    payload["pilot_fingerprint"] = fingerprint(payload)
    return payload
