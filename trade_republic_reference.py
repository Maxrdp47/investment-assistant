from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_assistant import calculate_position_size, finalize_swing_order_plan


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TR_REFERENCE_DB_PATH = PROJECT_ROOT / "runtime" / "trade_republic_reference.sqlite3"

TR_STATUS_TRADEABLE = "TR handelbar"
TR_STATUS_NOT_TRADEABLE = "TR nicht handelbar"
TR_STATUS_UNKNOWN = "unbekannt"
TR_STATUS_OPTIONS = (
    TR_STATUS_TRADEABLE,
    TR_STATUS_NOT_TRADEABLE,
    TR_STATUS_UNKNOWN,
)
TR_REFERENCE_SCHEMA_VERSION = 1
TR_EXECUTION_PLAN_VERSION = "trade-republic-execution-plan-2026.08.11-v1"
DEFAULT_TR_PRICE_MAX_AGE_MINUTES = 15


def _canonical(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _upper(value: object) -> str:
    return _text(value).upper()


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: object | None = None) -> datetime:
    parsed = datetime.now().astimezone() if value is None else datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def listing_identity(asset: dict) -> dict:
    """Create a venue-specific identity for the listing used by the analysis feed."""
    metadata = dict(asset.get("universe_metadata") or {})
    identity = {
        "ticker": _upper(asset.get("ticker") or asset.get("symbol")),
        "isin": _upper(asset.get("isin") or metadata.get("isin")),
        "exchange": _upper(asset.get("exchange") or metadata.get("exchange")),
        "currency": _upper(
            asset.get("original_currency")
            or asset.get("currency")
            or metadata.get("original_currency")
        ),
        "name": _text(asset.get("name") or asset.get("asset_name")),
    }
    key_payload = {field: identity[field] for field in ("ticker", "isin", "exchange", "currency")}
    identity["listing_key"] = _fingerprint(key_payload)
    identity["identity_fingerprint"] = _fingerprint(
        {field: identity[field] for field in ("ticker", "isin", "exchange", "currency")}
    )
    return identity


def trade_republic_listing_identity(
    *,
    ticker: object,
    isin: object,
    exchange: object,
    currency: object = "EUR",
    name: object = "",
) -> dict:
    identity = {
        "ticker": _upper(ticker),
        "isin": _upper(isin),
        "exchange": _upper(exchange),
        "currency": _upper(currency),
        "name": _text(name),
    }
    key_payload = {field: identity[field] for field in ("ticker", "isin", "exchange", "currency")}
    identity["listing_key"] = _fingerprint(key_payload)
    return identity


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_trade_republic_reference_store(
    path: Path = DEFAULT_TR_REFERENCE_DB_PATH,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tr_reference_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tr_listing_events (
                event_id TEXT PRIMARY KEY,
                analysis_listing_key TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                status TEXT NOT NULL,
                analysis_listing_json TEXT NOT NULL,
                tr_listing_json TEXT NOT NULL,
                source TEXT NOT NULL,
                note TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL UNIQUE
            );

            CREATE INDEX IF NOT EXISTS idx_tr_listing_events_latest
            ON tr_listing_events (analysis_listing_key, recorded_at, event_id);

            CREATE TABLE IF NOT EXISTS tr_price_observations (
                observation_id TEXT PRIMARY KEY,
                analysis_listing_key TEXT NOT NULL,
                tr_listing_key TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                price_eur REAL NOT NULL,
                source TEXT NOT NULL,
                analysis_comparison_price_eur REAL NOT NULL,
                analysis_price_source TEXT NOT NULL,
                note TEXT NOT NULL,
                observation_fingerprint TEXT NOT NULL UNIQUE
            );

            CREATE INDEX IF NOT EXISTS idx_tr_price_observations_latest
            ON tr_price_observations (analysis_listing_key, tr_listing_key, observed_at, observation_id);

            CREATE TRIGGER IF NOT EXISTS tr_listing_events_no_update
            BEFORE UPDATE ON tr_listing_events
            BEGIN
                SELECT RAISE(ABORT, 'tr_listing_events is append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS tr_listing_events_no_delete
            BEFORE DELETE ON tr_listing_events
            BEGIN
                SELECT RAISE(ABORT, 'tr_listing_events is append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS tr_price_observations_no_update
            BEFORE UPDATE ON tr_price_observations
            BEGIN
                SELECT RAISE(ABORT, 'tr_price_observations is append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS tr_price_observations_no_delete
            BEFORE DELETE ON tr_price_observations
            BEGIN
                SELECT RAISE(ABORT, 'tr_price_observations is append-only');
            END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM tr_reference_meta WHERE key = 'schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO tr_reference_meta (key, value) VALUES ('schema_version', ?)",
                (str(TR_REFERENCE_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != TR_REFERENCE_SCHEMA_VERSION:
            raise RuntimeError(
                f"Nicht unterstütztes TR-Referenzschema {existing['value']}; "
                f"erwartet {TR_REFERENCE_SCHEMA_VERSION}."
            )


def trade_republic_reference(
    asset: dict,
    path: Path = DEFAULT_TR_REFERENCE_DB_PATH,
) -> dict:
    analysis_listing = listing_identity(asset)
    empty = {
        "analysis_listing": analysis_listing,
        "analysis_listing_key": analysis_listing["listing_key"],
        "status": TR_STATUS_UNKNOWN,
        "status_source": "Keine dauerhafte Markierung vorhanden",
        "status_recorded_at": None,
        "tr_listing": {},
        "tr_listing_key": "",
        "automatic_detection": False,
        "broker_connection": False,
    }
    path = Path(path)
    if not path.exists():
        return empty
    initialize_trade_republic_reference_store(path)
    with _connect(path) as connection:
        row = connection.execute(
            """
            SELECT * FROM tr_listing_events
            WHERE analysis_listing_key = ?
            ORDER BY recorded_at DESC, event_id DESC
            LIMIT 1
            """,
            (analysis_listing["listing_key"],),
        ).fetchone()
        if row is None and analysis_listing["isin"]:
            candidates = connection.execute(
                "SELECT * FROM tr_listing_events ORDER BY recorded_at DESC, event_id DESC"
            ).fetchall()
            for candidate in candidates:
                try:
                    stored = json.loads(candidate["analysis_listing_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if all(
                    _upper(stored.get(field)) == analysis_listing[field]
                    for field in ("ticker", "isin", "exchange", "currency")
                ):
                    row = candidate
                    break
    if row is None:
        return empty
    tr_listing = json.loads(row["tr_listing_json"])
    stored_analysis_listing = json.loads(row["analysis_listing_json"])
    return {
        **empty,
        "analysis_listing": stored_analysis_listing,
        "analysis_listing_key": str(row["analysis_listing_key"]),
        "status": str(row["status"]),
        "status_source": str(row["source"]),
        "status_recorded_at": str(row["recorded_at"]),
        "tr_listing": tr_listing,
        "tr_listing_key": str(tr_listing.get("listing_key") or ""),
        "note": str(row["note"]),
    }


def record_trade_republic_status(
    asset: dict,
    status: str,
    *,
    tr_ticker: object = "",
    tr_isin: object = "",
    tr_exchange: object = "",
    tr_currency: object = "EUR",
    tr_name: object = "",
    analysis_isin: object = "",
    note: object = "",
    recorded_at: object | None = None,
    path: Path = DEFAULT_TR_REFERENCE_DB_PATH,
) -> dict:
    normalized_status = _text(status)
    if normalized_status not in TR_STATUS_OPTIONS:
        raise ValueError(f"Ungültiger Trade-Republic-Status: {status}")
    analysis_listing = listing_identity(asset)
    manually_verified_analysis_isin = _upper(analysis_isin)
    if manually_verified_analysis_isin:
        analysis_listing["isin"] = manually_verified_analysis_isin
        analysis_listing["identity_fingerprint"] = _fingerprint(
            {
                field: analysis_listing[field]
                for field in ("ticker", "isin", "exchange", "currency")
            }
        )
        analysis_listing["isin_source"] = "Manuell verifiziert"
    tr_listing = trade_republic_listing_identity(
        ticker=tr_ticker,
        isin=tr_isin,
        exchange=tr_exchange,
        currency=tr_currency,
        name=tr_name,
    )
    if normalized_status == TR_STATUS_TRADEABLE:
        if not analysis_listing["isin"]:
            raise ValueError(
                "TR handelbar kann erst gespeichert werden, wenn die ISIN des analysierten Listings bekannt ist."
            )
        if not tr_listing["isin"] or not tr_listing["exchange"] or not tr_listing["ticker"]:
            raise ValueError("Für TR handelbar werden TR-Ticker, ISIN und Handelsplatz benötigt.")
        if tr_listing["isin"] != analysis_listing["isin"]:
            raise ValueError(
                "Die TR-ISIN stimmt nicht mit der ISIN des analysierten Listings überein. "
                "ADR, GDR oder ein anderes Instrument darf nicht verknüpft werden."
            )
        if tr_listing["currency"] != "EUR":
            raise ValueError("Der in der Nutzeransicht verwendete TR-Ausführungskurs muss in EUR vorliegen.")
    timestamp = _timestamp(recorded_at).isoformat()
    payload = {
        "analysis_listing": analysis_listing,
        "tr_listing": tr_listing if normalized_status == TR_STATUS_TRADEABLE else {},
        "status": normalized_status,
        "recorded_at": timestamp,
        "source": "Manuelle dauerhafte Trade-Republic-Markierung",
        "note": _text(note)[:2_000],
    }
    fingerprint = _fingerprint(payload)
    event_id = _fingerprint({"kind": "tr_listing_status", "fingerprint": fingerprint})
    initialize_trade_republic_reference_store(path)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT event_id FROM tr_listing_events WHERE event_fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if existing is not None:
            return {"event_id": str(existing["event_id"]), "inserted": False}
        connection.execute(
            """
            INSERT INTO tr_listing_events (
                event_id, analysis_listing_key, recorded_at, status,
                analysis_listing_json, tr_listing_json, source, note, event_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                analysis_listing["listing_key"],
                timestamp,
                normalized_status,
                _canonical(analysis_listing),
                _canonical(payload["tr_listing"]),
                payload["source"],
                payload["note"],
                fingerprint,
            ),
        )
    return {"event_id": event_id, "inserted": True}


def record_trade_republic_price(
    asset: dict,
    price_eur: float,
    *,
    analysis_comparison_price_eur: float,
    analysis_price_source: str = "Yahoo Finance / yfinance – zeitgleicher Vergleichskurs",
    observed_at: object | None = None,
    note: object = "",
    path: Path = DEFAULT_TR_REFERENCE_DB_PATH,
) -> dict:
    reference = trade_republic_reference(asset, path)
    if reference["status"] != TR_STATUS_TRADEABLE or not reference["tr_listing_key"]:
        raise ValueError("Ein TR-Preis kann nur für ein dauerhaft als TR handelbar markiertes Listing erfasst werden.")
    price = _number(price_eur)
    if price is None or price <= 0:
        raise ValueError("Der Trade-Republic-Preis muss größer als null sein.")
    analysis_comparison = _number(analysis_comparison_price_eur)
    if analysis_comparison is None or analysis_comparison <= 0:
        raise ValueError(
            "Für die sichere Listing-Basis wird ein zeitgleich erfasster Vergleichskurs des analysierten Listings benötigt."
        )
    normalized_analysis_source = _text(analysis_price_source)
    if not normalized_analysis_source:
        raise ValueError("Die Quelle des zeitgleichen Analyse-Vergleichskurses fehlt.")
    timestamp = _timestamp(observed_at).isoformat()
    payload = {
        "analysis_listing_key": reference["analysis_listing_key"],
        "tr_listing_key": reference["tr_listing_key"],
        "observed_at": timestamp,
        "price_eur": price,
        "source": "Manuell aus Trade Republic erfasst",
        "analysis_comparison_price_eur": analysis_comparison,
        "analysis_price_source": normalized_analysis_source,
        "note": _text(note)[:2_000],
    }
    fingerprint = _fingerprint(payload)
    observation_id = _fingerprint({"kind": "tr_price", "fingerprint": fingerprint})
    initialize_trade_republic_reference_store(path)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT observation_id FROM tr_price_observations WHERE observation_fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if existing is not None:
            return {"observation_id": str(existing["observation_id"]), "inserted": False}
        connection.execute(
            """
            INSERT INTO tr_price_observations (
                observation_id, analysis_listing_key, tr_listing_key,
                observed_at, price_eur, source, analysis_comparison_price_eur,
                analysis_price_source, note, observation_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                reference["analysis_listing_key"],
                reference["tr_listing_key"],
                timestamp,
                price,
                payload["source"],
                analysis_comparison,
                normalized_analysis_source,
                payload["note"],
                fingerprint,
            ),
        )
    return {"observation_id": observation_id, "inserted": True}


def trade_republic_price(
    asset: dict,
    *,
    now: object | None = None,
    max_age_minutes: int = DEFAULT_TR_PRICE_MAX_AGE_MINUTES,
    path: Path = DEFAULT_TR_REFERENCE_DB_PATH,
) -> dict:
    reference = trade_republic_reference(asset, path)
    unavailable = {
        "available": False,
        "label": "TR-Preis nicht verfügbar",
        "price_eur": None,
        "observed_at": None,
        "source": None,
        "analysis_comparison_price_eur": None,
        "analysis_price_source": None,
        "reason": "Kein frischer, listing-spezifischer Trade-Republic-Preis vorhanden.",
    }
    if reference["status"] != TR_STATUS_TRADEABLE or not reference["tr_listing_key"]:
        return {**unavailable, "reason": "Das konkrete Listing ist nicht als TR handelbar verifiziert."}
    path = Path(path)
    if not path.exists():
        return unavailable
    with _connect(path) as connection:
        row = connection.execute(
            """
            SELECT * FROM tr_price_observations
            WHERE analysis_listing_key = ? AND tr_listing_key = ?
            ORDER BY observed_at DESC, observation_id DESC
            LIMIT 1
            """,
            (reference["analysis_listing_key"], reference["tr_listing_key"]),
        ).fetchone()
    if row is None:
        return unavailable
    observed = _timestamp(row["observed_at"])
    current = _timestamp(now)
    status_recorded_at = reference.get("status_recorded_at")
    if status_recorded_at and observed.astimezone(timezone.utc) < _timestamp(
        status_recorded_at
    ).astimezone(timezone.utc):
        return {
            **unavailable,
            "observed_at": observed.isoformat(),
            "source": str(row["source"]),
            "reason": "Nach der letzten TR-Listing-Zuordnung wurde noch kein neuer TR-Preis erfasst.",
        }
    age = current.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
    if age < timedelta(minutes=-5):
        return {
            **unavailable,
            "observed_at": observed.isoformat(),
            "source": str(row["source"]),
            "reason": "Der erfasste TR-Preis liegt unplausibel in der Zukunft.",
        }
    if age > timedelta(
        minutes=max(int(max_age_minutes), 0)
    ):
        return {
            **unavailable,
            "observed_at": observed.isoformat(),
            "source": str(row["source"]),
            "reason": (
                f"Der letzte erfasste TR-Preis ist älter als {max(int(max_age_minutes), 0)} Minuten."
            ),
        }
    return {
        "available": True,
        "label": f"{float(row['price_eur']):.6f} EUR",
        "price_eur": float(row["price_eur"]),
        "observed_at": observed.isoformat(),
        "source": str(row["source"]),
        "analysis_comparison_price_eur": float(row["analysis_comparison_price_eur"]),
        "analysis_price_source": str(row["analysis_price_source"]),
        "reason": "Frischer manueller TR-Preis für das exakt verknüpfte Listing.",
    }


def build_trade_republic_execution_plan(
    analysis_order_plan: dict,
    reference: dict,
    price_observation: dict,
    *,
    trading_capital_eur: float | None,
    max_risk_pct: float,
    asset_type: str,
    max_total_exposure_pct: float,
    current_exposure_eur: float,
    max_position_exposure_pct: float,
    max_total_risk_pct: float | None = None,
    current_risk_eur: float = 0.0,
) -> dict | None:
    """Translate relative technical levels to one verified, EUR-denominated TR listing."""
    if reference.get("status") != TR_STATUS_TRADEABLE or not price_observation.get("available"):
        return None
    analysis_listing = dict(reference.get("analysis_listing") or {})
    tr_listing = dict(reference.get("tr_listing") or {})
    if not analysis_listing.get("isin") or analysis_listing.get("isin") != tr_listing.get("isin"):
        return None
    analysis_reference = _number(analysis_order_plan.get("analysis_reference_price_eur"))
    analysis_comparison = _number(price_observation.get("analysis_comparison_price_eur"))
    tr_price = _number(price_observation.get("price_eur"))
    if (
        analysis_reference is None
        or analysis_reference <= 0
        or analysis_comparison is None
        or analysis_comparison <= 0
        or tr_price is None
        or tr_price <= 0
    ):
        return None
    scale = tr_price / analysis_comparison

    def translated(field: str) -> float | None:
        value = _number(analysis_order_plan.get(field))
        return value * scale if value is not None else None

    limit_price = translated("limit_price_eur")
    initial_stop = translated("initial_stop_eur")
    target_1 = translated("target_1_eur")
    if limit_price is None or initial_stop is None or target_1 is None:
        return None
    if not 0 < initial_stop < limit_price < target_1:
        return None
    target_2 = translated("target_2_eur")
    payload = {
        "plan_version": TR_EXECUTION_PLAN_VERSION,
        "stop_contract_version": analysis_order_plan.get("stop_contract_version"),
        "status": "ready_with_fresh_manual_tr_price",
        "direction": "Long",
        "entry_method": analysis_order_plan.get("entry_method"),
        "order_type": analysis_order_plan.get("order_type"),
        "activation_type": analysis_order_plan.get("activation_type"),
        "current_tr_price_eur": tr_price,
        "activation_price_eur": translated("activation_price_eur"),
        "limit_price_eur": limit_price,
        "maximum_entry_eur": translated("maximum_entry_eur"),
        "initial_stop_eur": initial_stop,
        "target_1_eur": target_1,
        "target_2_eur": target_2,
        "target_1_exit_fraction": analysis_order_plan.get("target_1_exit_fraction"),
        "target_2_exit_fraction": analysis_order_plan.get("target_2_exit_fraction"),
        "invalidation_eur": translated("invalidation_eur"),
        "original_currency": "EUR",
        "signal_bar_day": analysis_order_plan.get("signal_bar_day"),
        "earliest_entry_day": analysis_order_plan.get("earliest_entry_day"),
        "valid_until": analysis_order_plan.get("valid_until"),
        "execution_policy": analysis_order_plan.get("execution_policy"),
        "stop_policy": analysis_order_plan.get("stop_policy"),
        "delete_conditions": list(analysis_order_plan.get("delete_conditions") or []),
        "automatic_order_execution": False,
        "broker_connection": False,
        "trade_republic_listing": tr_listing,
        "execution_price_source": price_observation.get("source"),
        "execution_price_observed_at": price_observation.get("observed_at"),
        "analysis_price_source": analysis_order_plan.get("analysis_price_source"),
        "analysis_reference_price_eur": analysis_reference,
        "analysis_reference_observed_at": analysis_order_plan.get("analysis_reference_observed_at"),
        "basis_analysis_price_eur": analysis_comparison,
        "basis_analysis_price_source": price_observation.get("analysis_price_source"),
        "basis_observed_at": price_observation.get("observed_at"),
        "analysis_plan_fingerprint": analysis_order_plan.get("plan_fingerprint"),
        "translation_factor": scale,
        "translation_policy": (
            "Ein zeitgleich erfasster Vergleichskurs des analysierten Listings bestimmt zusammen mit dem frischen "
            "manuellen TR-EUR-Preis ausschließlich die Listing-Basis. Diese Basis wird auf die unveränderten "
            "technischen Marken des Analyseplans angewendet. Alle absoluten Ausführungsmarken gehören zum "
            "verknüpften TR-Listing; Yahoo wird nicht als TR-Preis ausgegeben."
        ),
        "execution_cost_contract": dict(analysis_order_plan.get("execution_cost_contract") or {}),
    }
    position = calculate_position_size(
        trading_capital_eur,
        max_risk_pct,
        limit_price,
        initial_stop,
        asset_type=asset_type,
        max_total_exposure_pct=max_total_exposure_pct,
        current_exposure_eur=current_exposure_eur,
        max_position_exposure_pct=max_position_exposure_pct,
        max_total_risk_pct=max_total_risk_pct,
        current_risk_eur=current_risk_eur,
        target_1_eur=target_1,
        target_2_eur=target_2,
    )
    return finalize_swing_order_plan(payload, position)


def trade_republic_reference_store_audit(
    path: Path = DEFAULT_TR_REFERENCE_DB_PATH,
) -> dict:
    path = Path(path)
    if not path.exists():
        return {"status": "not_created", "listing_events": 0, "price_observations": 0}
    initialize_trade_republic_reference_store(path)
    invalid: list[str] = []
    with _connect(path) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        listing_events = connection.execute("SELECT * FROM tr_listing_events").fetchall()
        prices = connection.execute("SELECT * FROM tr_price_observations").fetchall()
    for row in listing_events:
        try:
            if str(row["status"]) not in TR_STATUS_OPTIONS:
                invalid.append(f"listing_event:{row['event_id']}:status")
            json.loads(row["analysis_listing_json"])
            json.loads(row["tr_listing_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            invalid.append(f"listing_event:{row['event_id']}:json")
    for row in prices:
        if (
            _number(row["price_eur"]) is None
            or float(row["price_eur"]) <= 0
            or _number(row["analysis_comparison_price_eur"]) is None
            or float(row["analysis_comparison_price_eur"]) <= 0
        ):
            invalid.append(f"price:{row['observation_id']}:value")
    return {
        "status": "ok" if integrity == "ok" and not invalid else "attention",
        "integrity_check": integrity,
        "listing_events": len(listing_events),
        "price_observations": len(prices),
        "invalid": invalid,
        "append_only": True,
        "broker_connection": False,
    }
