from __future__ import annotations

"""Append-only forward Point-in-Time observer for FX research data.

This module is intentionally unable to generate a strategy signal, trade plan,
paper trade, shadow order or broker request.  Providers return observations or
explicit missingness/source-health states; the collector only persists them.
"""

import hashlib
import json
import math
import os
import platform
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from fx_carry_pit import default_fx_pair_contracts
from swing_run_lock import SwingRunLock


FX_PIT_COLLECTOR_VERSION = "fx-pit-observer-2026.08.29-v1"
FX_PIT_SCHEMA_VERSION = 1
FX_DERIVED_FEATURE_VERSION = "fx-pit-derived-2026.08.29-v1"

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_COLLECTOR_DB_PATH = PROJECT_ROOT / "runtime" / "fx_forward_pit.sqlite3"
DEFAULT_COLLECTOR_LOCK_PATH = PROJECT_ROOT / "runtime" / "fx_forward_pit.collector.lock"

OBSERVATION_TYPES = {
    "POLICY_RATE",
    "CENTRAL_BANK_EVENT",
    "EXPECTATION",
    "MACRO_EVENT",
    "COT",
    "FX_QUOTE",
    "FX_PRICE_BAR",
    "REGIME_CONTEXT",
    "MISSINGNESS",
}
OBSERVATION_STATUSES = {
    "OBSERVED",
    "NO_EVENT_OBSERVED",
    "NO_RELIABLE_DATA",
    "PROVIDER_FAILURE",
    "NOT_SCHEDULED",
    "UNKNOWN",
}
SOURCE_TYPES = {
    "FORWARD_PIT",
    "SHADOW_CONTEXT",
    "PROXY",
}
SPECIALIZED_TABLES = {
    "CENTRAL_BANK_EVENT": "central_bank_events",
    "EXPECTATION": "expectations",
    "MACRO_EVENT": "macro_events",
    "COT": "cot_observations",
    "FX_QUOTE": "quote_observations",
}
PROHIBITED_OUTPUT_KEYS = {
    "buy",
    "sell",
    "entry",
    "stop",
    "target",
    "position",
    "paper_trade",
    "shadow_order",
    "expected_r",
    "strategy_signal",
    "broker_order",
}


class FxPitCollectorError(ValueError):
    pass


Provider = Callable[[Mapping[str, object]], Mapping[str, object]]


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: object) -> str | None:
    result = str(value or "").strip()
    return result or None


def _utc(value: object, field: str, *, required: bool = True) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise FxPitCollectorError(f"{field} fehlt.")
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FxPitCollectorError(f"{field} ist kein ISO-Zeitpunkt.") from exc
    if stamp.tzinfo is None:
        raise FxPitCollectorError(f"{field} benötigt eine Zeitzone.")
    return stamp.astimezone(timezone.utc).isoformat()


def _finite(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FxPitCollectorError(f"{field} ist keine Zahl.") from exc
    if not math.isfinite(result):
        raise FxPitCollectorError(f"{field} muss endlich sein.")
    return result


def _validate_no_trade_payload(payload: object, *, location: str = "payload") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if normalized in PROHIBITED_OUTPUT_KEYS:
                raise FxPitCollectorError(
                    f"{location} enthält verbotenes Trade-/Strategiefeld: {key}"
                )
            _validate_no_trade_payload(value, location=f"{location}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _validate_no_trade_payload(value, location=f"{location}[{index}]")


def normalize_collector_observation(
    observation: Mapping[str, object],
) -> dict[str, object]:
    observation_type = str(observation.get("observation_type") or "").strip().upper()
    if observation_type not in OBSERVATION_TYPES:
        raise FxPitCollectorError(f"Unbekannter observation_type: {observation_type}")
    status = str(observation.get("status") or "").strip().upper()
    if status not in OBSERVATION_STATUSES:
        raise FxPitCollectorError(f"Unbekannter Beobachtungsstatus: {status}")
    source_type = str(observation.get("source_type") or "").strip().upper()
    if source_type not in SOURCE_TYPES:
        raise FxPitCollectorError(f"Unbekannter source_type: {source_type}")
    source = _text(observation.get("source"))
    source_record_id = _text(observation.get("source_record_id"))
    if not source or not source_record_id:
        raise FxPitCollectorError("Beobachtung benötigt Quelle und Quell-ID.")
    payload = dict(observation.get("payload") or {})
    _validate_no_trade_payload(payload)
    if status == "OBSERVED" and not payload:
        raise FxPitCollectorError("OBSERVED benötigt einen nicht leeren Raw-Payload.")
    if status == "PROVIDER_FAILURE" and not _text(observation.get("error")):
        raise FxPitCollectorError("PROVIDER_FAILURE benötigt eine Fehlerbeschreibung.")
    if observation_type == "FX_QUOTE" and status == "OBSERVED":
        for field in ("bid", "ask"):
            if field not in payload:
                raise FxPitCollectorError("FX_QUOTE benötigt echte Bid- und Ask-Werte.")
        bid = _finite(payload["bid"], "bid")
        ask = _finite(payload["ask"], "ask")
        if bid <= 0 or ask <= 0 or ask < bid:
            raise FxPitCollectorError("Bid/Ask ist ungültig.")
        payload["bid"], payload["ask"] = bid, ask
    observed_at = _utc(observation.get("observed_at"), "observed_at")
    first_seen_at = _utc(observation.get("first_seen_at"), "first_seen_at")
    imported_at = _utc(observation.get("imported_at"), "imported_at")
    source_timestamp = _utc(
        observation.get("source_timestamp"), "source_timestamp", required=False
    )
    revision_number = int(observation.get("revision_number") or 0)
    supersedes = _text(observation.get("supersedes"))
    if revision_number < 0:
        raise FxPitCollectorError("revision_number darf nicht negativ sein.")
    if revision_number > 0 and not supersedes:
        raise FxPitCollectorError("Eine Revision benötigt supersedes.")

    identity = {
        "collector_version": FX_PIT_COLLECTOR_VERSION,
        "observation_type": observation_type,
        "entity_id": _text(observation.get("entity_id")) or "GLOBAL",
        "pair_id": _text(observation.get("pair_id")),
        "currency": str(observation.get("currency") or "").strip().upper() or None,
        "source": source,
        "source_record_id": source_record_id,
        "source_timestamp": source_timestamp,
        "source_type": source_type,
        "status": status,
        "revision_number": revision_number,
        "supersedes": supersedes,
        "payload": payload,
        "error": _text(observation.get("error")),
    }
    observation_key = _fingerprint(identity)
    result: dict[str, object] = {
        **identity,
        "observation_id": f"fxobs-{observation_key[:32]}",
        "observation_key": observation_key,
        "observed_at": observed_at,
        "first_seen_at": first_seen_at,
        "imported_at": imported_at,
        "source_timestamp_known": source_timestamp is not None,
        "quality": _text(observation.get("quality")) or "UNKNOWN",
        "scheduled_for": _utc(
            observation.get("scheduled_for"), "scheduled_for", required=False
        ),
        "availability_rule": _text(observation.get("availability_rule"))
        or "first_seen_at_lte_research_cutoff",
        "broker_order_allowed": False,
        "strategy_decision": False,
        "trade_decision": False,
    }
    result["observation_fingerprint"] = _fingerprint(result)
    return result


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize_fx_pit_collector_store(
    path: Path = DEFAULT_COLLECTOR_DB_PATH,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS schema_metadata (
                schema_version INTEGER PRIMARY KEY,
                collector_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS collector_runs (
                run_id TEXT PRIMARY KEY,
                schedule_slot TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                run_fingerprint TEXT NOT NULL UNIQUE,
                run_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fx_pairs (
                pair_fingerprint TEXT PRIMARY KEY,
                pair_id TEXT NOT NULL,
                contract_json TEXT NOT NULL,
                first_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                observation_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                pair_id TEXT,
                currency TEXT,
                status TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                source TEXT NOT NULL,
                source_record_id TEXT NOT NULL,
                source_timestamp TEXT,
                imported_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                supersedes TEXT,
                observation_key TEXT NOT NULL UNIQUE,
                observation_fingerprint TEXT NOT NULL,
                observation_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS macro_events (
                observation_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS expectations (
                observation_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS central_bank_events (
                observation_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cot_observations (
                observation_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quote_observations (
                observation_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                revision_id TEXT PRIMARY KEY,
                observation_id TEXT NOT NULL,
                supersedes_observation_id TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                first_seen_at TEXT NOT NULL,
                revision_fingerprint TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS derived_features (
                feature_id TEXT PRIMARY KEY,
                feature_name TEXT NOT NULL,
                formula_version TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                input_ids_json TEXT NOT NULL,
                feature_json TEXT NOT NULL,
                feature_fingerprint TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS coverage_status (
                coverage_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                pair_id TEXT,
                feature TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                coverage_fingerprint TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS source_health (
                health_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source TEXT NOT NULL,
                last_attempt TEXT NOT NULL,
                last_success TEXT,
                consecutive_failures INTEGER NOT NULL,
                stale_status TEXT NOT NULL,
                rate_limit_status TEXT NOT NULL,
                coverage_status TEXT NOT NULL,
                response_quality TEXT NOT NULL,
                health_fingerprint TEXT NOT NULL UNIQUE,
                health_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scheduled_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                currency TEXT,
                scheduled_for TEXT NOT NULL,
                known_at TEXT NOT NULL,
                source TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL UNIQUE,
                event_json TEXT NOT NULL
            );
            """
        )
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "INSERT OR IGNORE INTO schema_metadata VALUES (?, ?, ?)",
            (FX_PIT_SCHEMA_VERSION, FX_PIT_COLLECTOR_VERSION, now),
        )
        for table in (
            "schema_metadata",
            "collector_runs",
            "fx_pairs",
            "observations",
            "macro_events",
            "expectations",
            "central_bank_events",
            "cot_observations",
            "quote_observations",
            "revisions",
            "derived_features",
            "coverage_status",
            "source_health",
            "scheduled_events",
        ):
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_update "
                f"BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} append-only'); END"
            )
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete "
                f"BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} append-only'); END"
            )


def store_pair_contracts(
    contracts: Iterable[Mapping[str, object]],
    *,
    path: Path,
    first_seen_at: object,
) -> int:
    initialize_fx_pit_collector_store(path)
    stamp = _utc(first_seen_at, "first_seen_at")
    inserted = 0
    with _connect(path) as connection:
        for contract in contracts:
            item = dict(contract)
            fingerprint = str(item.get("pair_fingerprint") or "")
            if not fingerprint:
                raise FxPitCollectorError("FX-Paar besitzt keinen Fingerprint.")
            existing = connection.execute(
                "SELECT contract_json FROM fx_pairs WHERE pair_fingerprint=?",
                (fingerprint,),
            ).fetchone()
            encoded = _canonical_json(item)
            if existing is not None and str(existing[0]) != encoded:
                raise FxPitCollectorError("Gespeicherter Pair-Contract ist inkonsistent.")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO fx_pairs VALUES (?, ?, ?, ?)",
                (fingerprint, item["pair_id"], encoded, stamp),
            )
            inserted += int(cursor.rowcount)
    return inserted


def append_observations(
    observations: Iterable[Mapping[str, object]],
    *,
    run_id: str,
    path: Path = DEFAULT_COLLECTOR_DB_PATH,
) -> dict[str, int]:
    initialize_fx_pit_collector_store(path)
    inserted = deduplicated = revisions = 0
    with _connect(path) as connection:
        for raw in observations:
            item = normalize_collector_observation(raw)
            existing = connection.execute(
                "SELECT observation_json FROM observations WHERE observation_key=?",
                (item["observation_key"],),
            ).fetchone()
            if existing is not None:
                stored = json.loads(str(existing[0]))
                comparable_fields = (
                    "observation_type",
                    "entity_id",
                    "pair_id",
                    "currency",
                    "source",
                    "source_record_id",
                    "source_timestamp",
                    "source_type",
                    "status",
                    "revision_number",
                    "supersedes",
                    "payload",
                    "error",
                )
                if any(stored.get(field) != item.get(field) for field in comparable_fields):
                    raise FxPitCollectorError(
                        "Dieselbe Beobachtungsidentität besitzt abweichenden Inhalt."
                    )
                deduplicated += 1
                continue
            if item.get("supersedes"):
                parent = connection.execute(
                    "SELECT observation_type, entity_id FROM observations WHERE observation_id=?",
                    (item["supersedes"],),
                ).fetchone()
                if parent is None:
                    raise FxPitCollectorError("Revision verweist auf unbekannte Beobachtung.")
                if (
                    str(parent["observation_type"]) != item["observation_type"]
                    or str(parent["entity_id"]) != item["entity_id"]
                ):
                    raise FxPitCollectorError("Revision gehört nicht zur selben Beobachtungsreihe.")
            connection.execute(
                """INSERT INTO observations VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (
                    item["observation_id"],
                    run_id,
                    item["observation_type"],
                    item["entity_id"],
                    item["pair_id"],
                    item["currency"],
                    item["status"],
                    item["observed_at"],
                    item["first_seen_at"],
                    item["source"],
                    item["source_record_id"],
                    item["source_timestamp"],
                    item["imported_at"],
                    item["source_type"],
                    item["revision_number"],
                    item["supersedes"],
                    item["observation_key"],
                    item["observation_fingerprint"],
                    _canonical_json(item),
                ),
            )
            table = SPECIALIZED_TABLES.get(str(item["observation_type"]))
            if table:
                connection.execute(
                    f"INSERT INTO {table} VALUES (?, ?)",
                    (item["observation_id"], _canonical_json(item["payload"])),
                )
            if item.get("supersedes"):
                revision_payload = {
                    "observation_id": item["observation_id"],
                    "supersedes": item["supersedes"],
                    "revision_number": item["revision_number"],
                    "first_seen_at": item["first_seen_at"],
                }
                revision_fingerprint = _fingerprint(revision_payload)
                connection.execute(
                    "INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        f"fxrev-{revision_fingerprint[:32]}",
                        item["observation_id"],
                        item["supersedes"],
                        item["revision_number"],
                        item["first_seen_at"],
                        revision_fingerprint,
                    ),
                )
                revisions += 1
            inserted += 1
    return {"inserted": inserted, "deduplicated": deduplicated, "revisions": revisions}


def build_derived_feature(
    feature_name: str,
    inputs: Sequence[Mapping[str, object]],
    *,
    calculated_at: object,
) -> dict[str, object]:
    name = str(feature_name or "").strip().upper()
    if name not in {"RATE_DIFFERENTIAL", "SURPRISE", "QUOTE_MID", "CARRY_TO_RISK"}:
        raise FxPitCollectorError(f"Unbekanntes Derived Feature: {name}")
    if not inputs:
        raise FxPitCollectorError("Derived Feature benötigt Raw-Input-IDs.")
    normalized_inputs = [dict(item) for item in inputs]
    for item in normalized_inputs:
        if not _text(item.get("observation_id")):
            raise FxPitCollectorError("Derived Input benötigt observation_id.")
    values = [_finite(item.get("value"), "input.value") for item in normalized_inputs]
    if name in {"RATE_DIFFERENTIAL", "SURPRISE"}:
        if len(values) != 2:
            raise FxPitCollectorError(f"{name} benötigt genau zwei geordnete Inputs.")
        value = values[0] - values[1]
        formula = "input_0_minus_input_1"
    elif name == "QUOTE_MID":
        if len(values) != 2:
            raise FxPitCollectorError("QUOTE_MID benötigt Bid und Ask.")
        value = (values[0] + values[1]) / 2.0
        formula = "(bid_plus_ask)/2"
    else:
        if len(values) != 2 or values[1] <= 0:
            raise FxPitCollectorError("CARRY_TO_RISK benötigt Differential und positive Volatilität.")
        value = values[0] / values[1]
        formula = "rate_differential_div_realized_volatility"
    payload: dict[str, object] = {
        "version": FX_DERIVED_FEATURE_VERSION,
        "feature_name": name,
        "formula": formula,
        "formula_version": FX_DERIVED_FEATURE_VERSION,
        "input_ids": [str(item["observation_id"]) for item in normalized_inputs],
        "value": value,
        "calculated_at": _utc(calculated_at, "calculated_at"),
        "raw_inputs_rewritten": False,
        "strategy_decision": False,
    }
    payload["feature_fingerprint"] = _fingerprint(payload)
    payload["feature_id"] = f"fxderived-{str(payload['feature_fingerprint'])[:32]}"
    return payload


def append_derived_feature(
    feature: Mapping[str, object],
    *,
    path: Path = DEFAULT_COLLECTOR_DB_PATH,
) -> bool:
    initialize_fx_pit_collector_store(path)
    item = dict(feature)
    _validate_no_trade_payload(item)
    fingerprint = str(item.get("feature_fingerprint") or "")
    comparable = {key: value for key, value in item.items() if key not in {"feature_id", "feature_fingerprint"}}
    if not fingerprint or _fingerprint(comparable) != fingerprint:
        raise FxPitCollectorError("Derived-Feature-Fingerprint ist ungültig.")
    with _connect(path) as connection:
        for input_id in item.get("input_ids", []):
            if connection.execute(
                "SELECT 1 FROM observations WHERE observation_id=?", (input_id,)
            ).fetchone() is None:
                raise FxPitCollectorError("Derived Feature verweist auf unbekannten Raw-Input.")
        cursor = connection.execute(
            "INSERT OR IGNORE INTO derived_features VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                item["feature_id"],
                item["feature_name"],
                item["formula_version"],
                item["calculated_at"],
                _canonical_json(item["input_ids"]),
                _canonical_json(item),
                fingerprint,
            ),
        )
    return bool(cursor.rowcount)


def append_scheduled_events(
    events: Iterable[Mapping[str, object]],
    *,
    path: Path = DEFAULT_COLLECTOR_DB_PATH,
) -> int:
    initialize_fx_pit_collector_store(path)
    inserted = 0
    with _connect(path) as connection:
        for event in events:
            item = {
                "event_type": str(event.get("event_type") or "").strip().upper(),
                "currency": str(event.get("currency") or "").strip().upper() or None,
                "scheduled_for": _utc(event.get("scheduled_for"), "scheduled_for"),
                "known_at": _utc(event.get("known_at"), "known_at"),
                "source": _text(event.get("source")),
                "source_reference": _text(event.get("source_reference")),
                "result_known": False,
            }
            if not item["event_type"] or not item["source"] or not item["source_reference"]:
                raise FxPitCollectorError("Termin benötigt Typ, Quelle und Quellenreferenz.")
            fingerprint = _fingerprint(item)
            cursor = connection.execute(
                "INSERT OR IGNORE INTO scheduled_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"fxevent-{fingerprint[:32]}",
                    item["event_type"],
                    item["currency"],
                    item["scheduled_for"],
                    item["known_at"],
                    item["source"],
                    fingerprint,
                    _canonical_json(item),
                ),
            )
            inserted += int(cursor.rowcount)
    return inserted


def _last_source_health(connection: sqlite3.Connection, source: str) -> dict[str, object]:
    row = connection.execute(
        "SELECT health_json FROM source_health WHERE source=? ORDER BY last_attempt DESC, health_id DESC LIMIT 1",
        (source,),
    ).fetchone()
    return {} if row is None else json.loads(str(row[0]))


def _append_source_health(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    source: str,
    status: str,
    observed_at: str,
    response_quality: str,
) -> dict[str, object]:
    previous = _last_source_health(connection, source)
    failed = status == "PROVIDER_FAILURE"
    consecutive = int(previous.get("consecutive_failures") or 0) + 1 if failed else 0
    last_success = previous.get("last_success") if failed else observed_at
    health = {
        "run_id": run_id,
        "source": source,
        "last_attempt": observed_at,
        "last_success": last_success,
        "consecutive_failures": consecutive,
        "stale_status": "STALE" if consecutive >= 2 else "ATTENTION" if failed else "CURRENT",
        "rate_limit_status": "UNKNOWN" if failed else "NOT_REPORTED",
        "coverage_status": (
            "PROVIDER_FAILURE"
            if failed
            else "NO_RELIABLE_DATA"
            if status == "NO_RELIABLE_DATA"
            else "NOT_SCHEDULED"
            if status == "NOT_SCHEDULED"
            else "OBSERVED"
        ),
        "response_quality": response_quality,
    }
    fingerprint = _fingerprint(health)
    connection.execute(
        "INSERT OR IGNORE INTO source_health VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            f"fxhealth-{fingerprint[:32]}",
            run_id,
            source,
            observed_at,
            last_success,
            consecutive,
            health["stale_status"],
            health["rate_limit_status"],
            health["coverage_status"],
            response_quality,
            fingerprint,
            _canonical_json(health),
        ),
    )
    return health


def _append_coverage(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    observed_at: str,
    rows: Iterable[Mapping[str, object]],
) -> int:
    inserted = 0
    for raw in rows:
        status = str(raw.get("status") or "UNKNOWN").strip().upper()
        if status not in {"AVAILABLE_PIT", "AVAILABLE_SHADOW", "UNAVAILABLE", "UNKNOWN"}:
            raise FxPitCollectorError(f"Ungültiger Coverage-Status: {status}")
        item = {
            "run_id": run_id,
            "pair_id": _text(raw.get("pair_id")),
            "feature": str(raw.get("feature") or "").strip().upper(),
            "status": status,
            "reason": _text(raw.get("reason")) or "not reported",
            "observed_at": observed_at,
        }
        if not item["feature"]:
            raise FxPitCollectorError("Coverage benötigt ein Feature.")
        fingerprint = _fingerprint(item)
        cursor = connection.execute(
            "INSERT OR IGNORE INTO coverage_status VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"fxcoverage-{fingerprint[:32]}",
                run_id,
                item["pair_id"],
                item["feature"],
                status,
                item["reason"],
                observed_at,
                fingerprint,
            ),
        )
        inserted += int(cursor.rowcount)
    return inserted


def _stored_run(path: Path, run_id: str) -> dict[str, object] | None:
    initialize_fx_pit_collector_store(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT run_json FROM collector_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return None if row is None else json.loads(str(row[0]))


def _run_collector_unlocked(
    settings: Mapping[str, object],
    providers: Mapping[str, Provider],
    *,
    path: Path,
    observed_at: str,
    schedule_slot: str,
    provenance: Mapping[str, object],
) -> dict[str, object]:
    initialize_fx_pit_collector_store(path)
    source_config = dict(settings.get("providers") or {})
    source_config_fingerprint = _fingerprint(source_config)
    pair_contracts = default_fx_pair_contracts()
    pair_universe_fingerprint = _fingerprint(pair_contracts)
    run_key = {
        "version": FX_PIT_COLLECTOR_VERSION,
        "schedule_slot": schedule_slot,
        "source_config_fingerprint": source_config_fingerprint,
        "pair_universe_fingerprint": pair_universe_fingerprint,
    }
    run_id = f"fxpit-run-{_fingerprint(run_key)[:32]}"
    existing = _stored_run(path, run_id)
    if existing is not None:
        return {**existing, "idempotent_replay": True}
    store_pair_contracts(pair_contracts.values(), path=path, first_seen_at=observed_at)

    context = {
        "observed_at": observed_at,
        "schedule_slot": schedule_slot,
        "settings": dict(settings),
        "pairs": pair_contracts,
        "database_path": str(path),
    }
    provider_summaries: list[dict[str, object]] = []
    all_errors: list[dict[str, str]] = []
    total_inserted = total_deduplicated = total_revisions = 0
    for name, raw_config in sorted(source_config.items()):
        config = dict(raw_config or {})
        if config.get("enabled") is False:
            continue
        loader = providers.get(name)
        try:
            if loader is None:
                raise FxPitCollectorError(f"Kein Provider-Adapter für {name} registriert.")
            result = dict(loader(context))
            status = str(result.get("status") or "UNKNOWN").strip().upper()
            if status not in OBSERVATION_STATUSES:
                raise FxPitCollectorError(f"Provider {name} meldet ungültigen Status {status}.")
            source = str(result.get("source") or name)
            observations = list(result.get("observations") or [])
            if not observations:
                observations = [
                    {
                        "observation_type": "MISSINGNESS",
                        "entity_id": "GLOBAL",
                        "status": status,
                        "source_type": "FORWARD_PIT",
                        "source": source,
                        "source_record_id": f"{schedule_slot}:{name}:{status}",
                        "observed_at": observed_at,
                        "first_seen_at": observed_at,
                        "imported_at": observed_at,
                        "payload": dict(result.get("missingness") or {}),
                        "error": result.get("error"),
                        "quality": result.get("response_quality") or "UNKNOWN",
                    }
                ]
            appended = append_observations(observations, run_id=run_id, path=path)
            total_inserted += appended["inserted"]
            total_deduplicated += appended["deduplicated"]
            total_revisions += appended["revisions"]
            with _connect(path) as connection:
                coverage_n = _append_coverage(
                    connection,
                    run_id=run_id,
                    observed_at=observed_at,
                    rows=result.get("coverage") or [],
                )
                health = _append_source_health(
                    connection,
                    run_id=run_id,
                    source=source,
                    status=status,
                    observed_at=observed_at,
                    response_quality=str(result.get("response_quality") or "UNKNOWN"),
                )
            provider_summaries.append(
                {
                    "provider": name,
                    "source": source,
                    "status": status,
                    "observations": len(observations),
                    "coverage_rows": coverage_n,
                    "health": health,
                }
            )
            if status == "PROVIDER_FAILURE":
                all_errors.append({"provider": name, "error": str(result.get("error"))})
        except Exception as exc:
            source = name
            error = str(exc)
            failure = {
                "observation_type": "MISSINGNESS",
                "entity_id": "GLOBAL",
                "status": "PROVIDER_FAILURE",
                "source_type": "FORWARD_PIT",
                "source": source,
                "source_record_id": f"{schedule_slot}:{name}:PROVIDER_FAILURE",
                "observed_at": observed_at,
                "first_seen_at": observed_at,
                "imported_at": observed_at,
                "payload": {"provider_failure": True},
                "error": error,
                "quality": "FAILED",
            }
            appended = append_observations([failure], run_id=run_id, path=path)
            total_inserted += appended["inserted"]
            total_deduplicated += appended["deduplicated"]
            with _connect(path) as connection:
                health = _append_source_health(
                    connection,
                    run_id=run_id,
                    source=source,
                    status="PROVIDER_FAILURE",
                    observed_at=observed_at,
                    response_quality="FAILED",
                )
            provider_summaries.append(
                {
                    "provider": name,
                    "source": source,
                    "status": "PROVIDER_FAILURE",
                    "observations": 1,
                    "coverage_rows": 0,
                    "health": health,
                }
            )
            all_errors.append({"provider": name, "error": error})

    ended_at = datetime.now(timezone.utc).isoformat()
    run: dict[str, object] = {
        "run_id": run_id,
        "collector_version": FX_PIT_COLLECTOR_VERSION,
        "schema_version": FX_PIT_SCHEMA_VERSION,
        "schedule_slot": schedule_slot,
        "status": "COMPLETED_WITH_SOURCE_GAPS" if all_errors else "COMPLETED",
        "start": observed_at,
        "end": ended_at,
        "branch": provenance.get("branch"),
        "commit_hash": provenance.get("commit_hash"),
        "code_fingerprint": provenance.get("code_fingerprint")
        or _file_sha256(Path(__file__)),
        "pair_universe_fingerprint": pair_universe_fingerprint,
        "source_config_fingerprint": source_config_fingerprint,
        "command": provenance.get("command") or "fx_pit_collector.run_fx_pit_collector",
        "worker": provenance.get("worker") or f"{platform.node()}:{os.getpid()}",
        "database_path": str(path),
        "provider_summaries": provider_summaries,
        "observations_inserted": total_inserted,
        "observations_deduplicated": total_deduplicated,
        "revisions_inserted": total_revisions,
        "errors": all_errors,
        "outputs": [str(path)],
        "mode": "FX_PIT_OBSERVER",
        "data_collection_only": True,
        "strategy_forward": False,
        "strategy_signal_generated": False,
        "trade_decision_generated": False,
        "paper_trade_generated": False,
        "shadow_order_generated": False,
        "broker_order_allowed": False,
        "broker_accessed": False,
    }
    _validate_no_trade_payload(
        {key: value for key, value in run.items() if key not in {
            "strategy_signal_generated",
            "trade_decision_generated",
            "paper_trade_generated",
            "shadow_order_generated",
            "broker_order_allowed",
        }}
    )
    run["run_fingerprint"] = _fingerprint(run)
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO collector_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                schedule_slot,
                run["status"],
                observed_at,
                ended_at,
                run["run_fingerprint"],
                _canonical_json(run),
            ),
        )
    return run


def run_fx_pit_collector(
    settings: Mapping[str, object],
    providers: Mapping[str, Provider],
    *,
    path: Path = DEFAULT_COLLECTOR_DB_PATH,
    lock_path: Path | None = DEFAULT_COLLECTOR_LOCK_PATH,
    observed_at: object | None = None,
    schedule_slot: str | None = None,
    provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if settings.get("mode") != "FX_PIT_OBSERVER":
        raise FxPitCollectorError("Collector-Modus muss FX_PIT_OBSERVER sein.")
    safety = dict(settings.get("safety") or {})
    required_false = (
        "strategy_signal_allowed",
        "trade_decision_allowed",
        "paper_trade_allowed",
        "shadow_order_allowed",
        "broker_order_allowed",
    )
    if any(safety.get(field) is not False for field in required_false):
        raise FxPitCollectorError("Collector-Sicherheitsvertrag ist nicht fail-closed.")
    stamp = _utc(observed_at or datetime.now(timezone.utc).isoformat(), "observed_at")
    slot = schedule_slot or str(stamp)[:10] + ":daily"
    arguments = {
        "settings": settings,
        "providers": providers,
        "path": Path(path),
        "observed_at": str(stamp),
        "schedule_slot": slot,
        "provenance": dict(provenance or {}),
    }
    if lock_path is None:
        return _run_collector_unlocked(**arguments)
    with SwingRunLock(Path(lock_path)):
        return _run_collector_unlocked(**arguments)


def fx_pit_collector_audit(
    path: Path = DEFAULT_COLLECTOR_DB_PATH,
) -> dict[str, object]:
    initialize_fx_pit_collector_store(path)
    with _connect(path) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "collector_runs",
                "fx_pairs",
                "observations",
                "macro_events",
                "expectations",
                "central_bank_events",
                "cot_observations",
                "quote_observations",
                "revisions",
                "derived_features",
                "coverage_status",
                "source_health",
                "scheduled_events",
            )
        }
        run_rows = [
            json.loads(str(row[0]))
            for row in connection.execute("SELECT run_json FROM collector_runs")
        ]
        observation_rows = [
            json.loads(str(row[0]))
            for row in connection.execute("SELECT observation_json FROM observations")
        ]
        trigger_n = int(
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%_no_%'"
            ).fetchone()[0]
        )
    prohibited = []
    for index, item in enumerate(observation_rows):
        try:
            _validate_no_trade_payload(item.get("payload") or {})
        except FxPitCollectorError as exc:
            prohibited.append({"observation_index": index, "error": str(exc)})
    invalid_runs = [
        str(run.get("run_id"))
        for run in run_rows
        if any(
            (
                run.get("strategy_signal_generated") is not False,
                run.get("trade_decision_generated") is not False,
                run.get("paper_trade_generated") is not False,
                run.get("shadow_order_generated") is not False,
                run.get("broker_order_allowed") is not False,
                run.get("broker_accessed") is not False,
            )
        )
    ]
    return {
        "status": "ok" if integrity == "ok" and not prohibited and not invalid_runs else "attention",
        "integrity": integrity,
        "schema_version": FX_PIT_SCHEMA_VERSION,
        "collector_version": FX_PIT_COLLECTOR_VERSION,
        "counts": counts,
        "append_only_trigger_n": trigger_n,
        "prohibited_payloads": prohibited,
        "invalid_run_safety_flags": invalid_runs,
        "strategy_signal_generated": False,
        "paper_trade_generated": False,
        "shadow_order_generated": False,
        "broker_order_allowed": False,
    }
