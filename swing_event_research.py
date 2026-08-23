from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


EVENT_STORE_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = "swing-event-pit-2026.08.23-v2"
EVENT_CONTEXT_VERSION = "swing-event-signal-sidecar-2026.08.23-v1"
EVENT_REACTION_SCHEMA_VERSION = "swing-event-market-reaction-2026.08.23-v1"
EVENT_LEDGER_VERSION = "swing-event-research-ledger-2026.08.23-v1"
EVENT_TRANSMISSION_MATRIX_VERSION = "swing-event-transmission-2026.08.23-v1"
EVENT_REACTION_HORIZONS = {"1h", "close", "1d", "3d", "5d", "10d", "20d"}
EVENT_REACTION_METRICS = (
    "return_pct",
    "mfe_pct",
    "mae_pct",
    "volume_change_pct",
    "gap_pct",
    "sector_relative_return_pct",
    "market_relative_return_pct",
)
DEFAULT_EVENT_RESEARCH_DB_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_SWING_EVENT_DB_PATH",
        Path(__file__).resolve().parent / "runtime" / "swing_event_research.sqlite3",
    )
)

EVENT_GROUPS = {
    "company",
    "macro",
    "geopolitics_policy",
    "market_shock",
}
EVENT_SUBTYPES = {
    "company": {
        "earnings",
        "revenue_surprise",
        "eps_surprise",
        "guidance_increase",
        "guidance_decrease",
        "clinical_trial",
        "regulatory_approval",
        "product_technology",
        "merger_acquisition",
        "capital_action",
        "litigation_regulatory",
        "management_change",
        "production_supply_chain",
        "scheduled_corporate_event",
        "company_news_unclassified",
    },
    "macro": {
        "central_bank_rate_decision",
        "inflation_cpi_pce",
        "labor_market",
        "gdp",
        "pmi_ism",
        "wages",
        "bond_yields",
        "central_bank_guidance",
        "macro_unclassified",
    },
    "geopolitics_policy": {
        "war_escalation",
        "deescalation",
        "sanctions",
        "tariffs",
        "export_controls",
        "trade_restrictions",
        "energy_policy",
        "tax_regulation",
        "defense_policy",
        "political_statement",
        "policy_unclassified",
    },
    "market_shock": {
        "oil_gas_shock",
        "vix_shock",
        "bond_yield_shock",
        "dollar_shock",
        "gold_commodity_shock",
        "index_crash_rally",
        "liquidity_volatility_shock",
        "market_shock_unclassified",
    },
}
SOURCE_QUALITY_LEVELS = {
    "official_primary": 1.0,
    "regulatory_primary": 1.0,
    "scientific_primary": 0.95,
    "reputable_wire": 0.85,
    "financial_media": 0.75,
    "secondary_aggregated": 0.6,
    "social_statement_only": 0.45,
    "unknown": 0.0,
}
IMPLEMENTATION_STATUSES = {"rhetoric", "proposal", "announced", "decided", "implemented", "unknown"}

CLINICAL_FIELDS = (
    "trial_id",
    "phase",
    "indication",
    "participant_count",
    "primary_endpoint",
    "secondary_endpoints",
    "control_group",
    "result",
    "statistical_significance",
    "safety_findings",
    "analysis_stage",
    "peer_reviewed",
    "publication_kind",
    "regulatory_next_steps",
)

TRANSMISSION_MATRIX = {
    "version": EVENT_TRANSMISSION_MATRIX_VERSION,
    "research_only": True,
    "causality_claimed": False,
    "rules": {
        "oil_supply_threat": {
            "potential_channels": {
                "oil_gas": "potentially_up",
                "energy_producers": "potentially_positive",
                "airlines_transport": "potentially_negative",
                "inflation_expectations": "potentially_up",
                "bonds_yields": "ambiguous",
            }
        },
        "chip_export_controls": {
            "potential_channels": {
                "affected_semiconductor_companies": "mapping_required",
                "suppliers_customers": "explicit_evidence_required",
                "affected_regions": "mapping_required",
            }
        },
        "tariffs": {
            "potential_channels": {
                "import_exposure": "explicit_evidence_required",
                "export_exposure": "explicit_evidence_required",
                "affected_industries": "mapping_required",
            }
        },
    },
}


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    if isinstance(value, (datetime, date, Path)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return _clean(item())
    return value


def _canonical_json(payload: object) -> str:
    return json.dumps(
        _clean(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


EVENT_CODE_FINGERPRINT = _fingerprint(
    {
        "event_schema": EVENT_SCHEMA_VERSION,
        "context_schema": EVENT_CONTEXT_VERSION,
        "reaction_schema": EVENT_REACTION_SCHEMA_VERSION,
        "ledger_schema": EVENT_LEDGER_VERSION,
        "event_groups": sorted(EVENT_GROUPS),
        "event_subtypes": {key: sorted(value) for key, value in EVENT_SUBTYPES.items()},
        "source_hierarchy": SOURCE_QUALITY_LEVELS,
        "transmission_matrix": TRANSMISSION_MATRIX,
    }
)


def _utc(value: datetime | str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Event-Zeitpunkte müssen eine Zeitzone besitzen.")
    return parsed.astimezone(timezone.utc)


def _optional_utc(value: object) -> datetime | None:
    return None if value in (None, "", "unknown", "unavailable") else _utc(value)  # type: ignore[arg-type]


def _number(value: object) -> float | None:
    if value in (None, "", "unknown", "unavailable"):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _strings(value: object, *, upper: bool = False) -> list[str]:
    if value in (None, ""):
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    normalized = []
    for item in values:
        text = str(item or "").strip()
        if text:
            normalized.append(text.upper() if upper else text.casefold())
    return sorted(set(normalized))


def _confidence(value: object) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if not 0.0 <= number <= 1.0:
        raise ValueError("Event-Confidence muss zwischen 0 und 1 liegen.")
    return number


def _expectation_payload(raw: Mapping[str, object]) -> dict:
    expected = _number(raw.get("expected_value"))
    actual = _number(raw.get("actual_value"))
    surprise = actual - expected if expected is not None and actual is not None else None
    supplied_surprise = _number(raw.get("surprise_value"))
    if supplied_surprise is not None and surprise is not None and not math.isclose(
        supplied_surprise, surprise, rel_tol=1e-9, abs_tol=1e-9
    ):
        raise ValueError("Der angegebene Surprise-Wert widerspricht expected/actual.")
    normalized = _number(raw.get("surprise_normalized")) if surprise is not None else None
    return {
        "expected_value": expected,
        "actual_value": actual,
        "surprise_value": surprise,
        "surprise_normalized": normalized,
        "expectation_source_id": raw.get("expectation_source_id") if expected is not None else None,
        "expectation_available_at": (
            _optional_utc(raw.get("expectation_available_at")).isoformat()
            if expected is not None and _optional_utc(raw.get("expectation_available_at")) is not None
            else None
        ),
        "surprise_status": "available" if surprise is not None else "unavailable",
        "no_consensus_reconstruction": True,
    }


def normalize_event_record(
    raw: Mapping[str, object],
    *,
    first_seen_at: datetime | str,
    acquisition_mode: str = "forward",
) -> dict:
    event_type = str(raw.get("event_type") or "").strip().casefold()
    event_subtype = str(raw.get("event_subtype") or "").strip().casefold()
    if event_type not in EVENT_GROUPS:
        raise ValueError(f"Nicht unterstützte Eventgruppe: {event_type or 'leer'}")
    if event_subtype not in EVENT_SUBTYPES[event_type]:
        raise ValueError(f"Nicht unterstützter Eventtyp {event_type}/{event_subtype or 'leer'}.")
    source_id = str(raw.get("source_id") or "").strip()
    source_type = str(raw.get("source_type") or "unknown").strip().casefold()
    source_quality = str(raw.get("source_quality") or "unknown").strip().casefold()
    if not source_id:
        raise ValueError("Ein Event benötigt eine stabile source_id.")
    if source_quality not in SOURCE_QUALITY_LEVELS:
        raise ValueError(f"Unbekannte Quellenqualität: {source_quality}")
    first_seen = _utc(first_seen_at)
    published = _optional_utc(raw.get("published_at"))
    effective = _optional_utc(raw.get("effective_at"))
    expiry = _optional_utc(raw.get("event_expiry"))
    if published is not None and published > first_seen:
        raise ValueError("published_at darf nicht nach first_seen_at liegen.")
    if expiry is not None and effective is not None and expiry < effective:
        raise ValueError("event_expiry darf nicht vor effective_at liegen.")
    availability_basis = str(raw.get("availability_basis") or "forward_first_seen").strip()
    publication_optional = availability_basis in {
        "immutable_forward_signal_snapshot",
        "official_calendar_observed_forward",
    }
    pit_eligible = bool(
        acquisition_mode == "forward"
        and (published is not None or publication_optional)
    )
    affected = {
        "assets": _strings(raw.get("affected_assets"), upper=True),
        "companies": _strings(raw.get("affected_companies")),
        "sectors": _strings(raw.get("affected_sectors")),
        "industries": _strings(raw.get("affected_industries")),
        "regions": _strings(raw.get("affected_regions")),
        "countries": _strings(raw.get("affected_countries")),
        "commodities": _strings(raw.get("affected_commodities")),
        "macro_factors": _strings(raw.get("affected_macro_factors")),
        "relationships": [dict(value) for value in (raw.get("affected_relationships") or []) if isinstance(value, Mapping)],
    }
    clinical_raw = raw.get("clinical") if isinstance(raw.get("clinical"), Mapping) else {}
    clinical = {field: clinical_raw.get(field) for field in CLINICAL_FIELDS}
    expectation = _expectation_payload(raw)
    if expectation["expected_value"] is not None:
        expectation_available = _optional_utc(expectation["expectation_available_at"])
        if not expectation.get("expectation_source_id") or expectation_available is None:
            raise ValueError(
                "Ein historischer Erwartungswert benötigt Quelle und damaligen Verfügbarkeitszeitpunkt."
            )
        if expectation_available > first_seen or (
            published is not None and expectation_available > published
        ):
            raise ValueError("Die Erwartung war vor Eventverfügbarkeit nicht kausal bekannt.")
    implementation_status = str(raw.get("implementation_status") or "unknown").strip().casefold()
    if implementation_status not in IMPLEMENTATION_STATUSES:
        raise ValueError(f"Unbekannter Umsetzungsstatus: {implementation_status}")
    transmission = []
    for observation in raw.get("market_transmission") or []:
        if not isinstance(observation, Mapping):
            continue
        observed_at = _optional_utc(observation.get("observed_at"))
        if observed_at is None:
            continue
        available_at = max(value for value in (first_seen, published) if value is not None)
        if observed_at < available_at:
            raise ValueError("Marktreaktionen dürfen nicht vor Eventverfügbarkeit liegen.")
        transmission.append(
            {
                "factor": str(observation.get("factor") or "unknown"),
                "observed_at": observed_at.isoformat(),
                "return_pct": _number(observation.get("return_pct")),
                "data_granularity": str(observation.get("data_granularity") or "unknown"),
                "association_only": True,
                "causality_claimed": False,
            }
        )
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    version = str(raw.get("event_version") or "1").strip()
    stable_identity = {
        "source_id": source_id,
        "event_type": event_type,
        "event_subtype": event_subtype,
        "primary_assets": affected["assets"],
    }
    event_id = str(raw.get("event_id") or _fingerprint(stable_identity)).strip()
    payload = {
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "event_version": version,
        "event_type": event_type,
        "event_subtype": event_subtype,
        "published_at": published.isoformat() if published is not None else None,
        "first_seen_at": first_seen.isoformat(),
        "effective_at": effective.isoformat() if effective is not None else None,
        "source_id": source_id,
        "source_type": source_type,
        "source_quality": source_quality,
        "source_quality_score": SOURCE_QUALITY_LEVELS[source_quality],
        "title": title or None,
        "summary": summary or None,
        "affected": affected,
        "affected_assets": affected["assets"],
        "affected_companies": affected["companies"],
        "affected_sectors": affected["sectors"],
        "affected_regions": affected["regions"],
        "affected_countries": affected["countries"],
        "affected_commodities": affected["commodities"],
        "affected_macro_factors": affected["macro_factors"],
        "direction": str(raw.get("direction") or "unknown").strip().casefold(),
        "direction_basis": str(raw.get("direction_basis") or "not_objectively_determined"),
        "severity": _number(raw.get("severity")),
        "confidence": _confidence(raw.get("confidence")),
        "expectation": expectation,
        "expected_value": expectation["expected_value"],
        "actual_value": expectation["actual_value"],
        "surprise_value": expectation["surprise_value"],
        "surprise_normalized": expectation["surprise_normalized"],
        "uncertainty": str(raw.get("uncertainty") or "unknown"),
        "event_expiry": expiry.isoformat() if expiry is not None else None,
        "decay_horizon_days": _number(raw.get("decay_horizon_days")),
        "implementation_status": implementation_status,
        "clinical": clinical if event_subtype == "clinical_trial" else None,
        "political_statement": (
            {
                "speaker": raw.get("speaker"),
                "topic": raw.get("topic"),
                "concrete_measure": raw.get("concrete_measure"),
                "target_region": raw.get("target_region"),
                "affected_industries": _strings(raw.get("affected_industries")),
                "implementation_status": implementation_status,
            }
            if event_subtype == "political_statement"
            else None
        ),
        "market_transmission": transmission,
        "provenance": {
            "source_locator": raw.get("source_locator"),
            "raw_source_fingerprint": raw.get("raw_source_fingerprint"),
            "publisher": raw.get("publisher"),
            "acquisition_mode": acquisition_mode,
            "availability_basis": availability_basis,
            "retrieved_via": raw.get("retrieved_via"),
        },
        "pit_eligible": pit_eligible,
        "missingness": {
            "published_at": published is None,
            "effective_at": effective is None,
            "direction": str(raw.get("direction") or "unknown").casefold() == "unknown",
            "severity": _number(raw.get("severity")) is None,
            "confidence": _confidence(raw.get("confidence")) is None,
            "expectation": _number(raw.get("expected_value")) is None,
            "actual": _number(raw.get("actual_value")) is None,
        },
        "guardrails": {
            "research_shadow_only": True,
            "changes_trade_decision": False,
            "changes_score": False,
            "changes_stop_or_position_size": False,
            "automatic_rule_generation": False,
            "short_strategy": False,
            "broker_order": False,
            "causality_claimed": False,
        },
    }
    payload["data_fingerprint"] = _fingerprint(payload)
    payload["event_record_id"] = _fingerprint(
        {"event_id": event_id, "event_version": version, "data_fingerprint": payload["data_fingerprint"]}
    )
    return payload


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_event_research_store(path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS event_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_records (
                event_record_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_subtype TEXT NOT NULL,
                published_at TEXT,
                first_seen_at TEXT NOT NULL,
                effective_at TEXT,
                source_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_quality TEXT NOT NULL,
                pit_eligible INTEGER NOT NULL CHECK (pit_eligible IN (0, 1)),
                acquisition_mode TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                data_fingerprint TEXT NOT NULL,
                UNIQUE (event_id, event_version)
            );
            CREATE TABLE IF NOT EXISTS event_signal_contexts (
                context_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                signal_at TEXT NOT NULL,
                signal_cutoff TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                context_json TEXT NOT NULL,
                context_fingerprint TEXT NOT NULL,
                UNIQUE (signal_id, policy_version)
            );
            CREATE TABLE IF NOT EXISTS event_signal_links (
                link_id TEXT PRIMARY KEY,
                context_id TEXT NOT NULL REFERENCES event_signal_contexts(context_id),
                signal_id TEXT NOT NULL,
                event_record_id TEXT NOT NULL REFERENCES event_records(event_record_id),
                relevance_level INTEGER NOT NULL,
                relevance_confidence REAL,
                payload_json TEXT NOT NULL,
                link_fingerprint TEXT NOT NULL,
                UNIQUE (context_id, event_record_id)
            );
            CREATE TABLE IF NOT EXISTS event_market_reaction_labels (
                reaction_id TEXT PRIMARY KEY,
                event_record_id TEXT NOT NULL REFERENCES event_records(event_record_id),
                horizon TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                data_granularity TEXT NOT NULL,
                label_json TEXT NOT NULL,
                label_fingerprint TEXT NOT NULL,
                UNIQUE (event_record_id, horizon, data_granularity)
            );
            CREATE TABLE IF NOT EXISTS event_hypothesis_ledger (
                ledger_entry_id TEXT PRIMARY KEY,
                hypothesis_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                entry_fingerprint TEXT NOT NULL,
                UNIQUE (hypothesis_id, action, entry_fingerprint)
            );
            CREATE INDEX IF NOT EXISTS idx_event_records_asof
            ON event_records(first_seen_at, published_at, event_type);
            CREATE INDEX IF NOT EXISTS idx_event_context_signal
            ON event_signal_contexts(signal_id, signal_cutoff);
            CREATE TRIGGER IF NOT EXISTS event_records_no_update BEFORE UPDATE ON event_records BEGIN
                SELECT RAISE(ABORT, 'event_records is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_records_no_delete BEFORE DELETE ON event_records BEGIN
                SELECT RAISE(ABORT, 'event_records is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_signal_contexts_no_update BEFORE UPDATE ON event_signal_contexts BEGIN
                SELECT RAISE(ABORT, 'event_signal_contexts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_signal_contexts_no_delete BEFORE DELETE ON event_signal_contexts BEGIN
                SELECT RAISE(ABORT, 'event_signal_contexts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_signal_links_no_update BEFORE UPDATE ON event_signal_links BEGIN
                SELECT RAISE(ABORT, 'event_signal_links is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_signal_links_no_delete BEFORE DELETE ON event_signal_links BEGIN
                SELECT RAISE(ABORT, 'event_signal_links is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_market_reaction_labels_no_update BEFORE UPDATE ON event_market_reaction_labels BEGIN
                SELECT RAISE(ABORT, 'event_market_reaction_labels is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_market_reaction_labels_no_delete BEFORE DELETE ON event_market_reaction_labels BEGIN
                SELECT RAISE(ABORT, 'event_market_reaction_labels is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_hypothesis_ledger_no_update BEFORE UPDATE ON event_hypothesis_ledger BEGIN
                SELECT RAISE(ABORT, 'event_hypothesis_ledger is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS event_hypothesis_ledger_no_delete BEFORE DELETE ON event_hypothesis_ledger BEGIN
                SELECT RAISE(ABORT, 'event_hypothesis_ledger is append-only');
            END;
            """
        )
        row = connection.execute("SELECT value FROM event_meta WHERE key='schema_version'").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO event_meta (key, value) VALUES ('schema_version', ?)",
                (str(EVENT_STORE_SCHEMA_VERSION),),
            )
            connection.execute(
                "INSERT INTO event_meta (key, value) VALUES ('event_schema_version', ?)",
                (EVENT_SCHEMA_VERSION,),
            )
            connection.execute(
                "INSERT INTO event_meta (key, value) VALUES ('event_code_fingerprint', ?)",
                (EVENT_CODE_FINGERPRINT,),
            )
        elif int(row["value"]) != EVENT_STORE_SCHEMA_VERSION:
            raise RuntimeError(f"Nicht unterstütztes Event-Store-Schema {row['value']}.")


def append_event_record(event: Mapping[str, object], path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH) -> dict:
    initialize_event_research_store(path)
    payload = dict(event)
    required = {
        "event_record_id",
        "event_id",
        "event_version",
        "event_type",
        "event_subtype",
        "first_seen_at",
        "source_id",
        "source_type",
        "source_quality",
        "pit_eligible",
        "provenance",
        "data_fingerprint",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Normalisierter Eventvertrag unvollständig: {', '.join(missing)}")
    if _fingerprint({key: value for key, value in payload.items() if key not in {"data_fingerprint", "event_record_id"}}) != payload["data_fingerprint"]:
        raise ValueError("Event-Fingerabdruck ist ungültig.")
    acquisition_mode = str((payload.get("provenance") or {}).get("acquisition_mode") or "unknown")
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT payload_json, data_fingerprint FROM event_records WHERE event_id=? AND event_version=?",
            (payload["event_id"], payload["event_version"]),
        ).fetchone()
        if existing is not None:
            stored = json.loads(existing["payload_json"])
            if existing["data_fingerprint"] == payload["data_fingerprint"]:
                return {"inserted": False, "event": stored}
            comparable_keys = set(stored) - {"first_seen_at", "data_fingerprint", "event_record_id"}
            if all(_canonical_json(stored.get(key)) == _canonical_json(payload.get(key)) for key in comparable_keys):
                return {"inserted": False, "event": stored}
            raise ValueError("Dieselbe Eventversion besitzt abweichende unveränderbare Daten; eine neue event_version ist nötig.")
        connection.execute(
            """INSERT INTO event_records
            (event_record_id, event_id, event_version, event_type, event_subtype, published_at,
             first_seen_at, effective_at, source_id, source_type, source_quality, pit_eligible,
             acquisition_mode, payload_json, data_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["event_record_id"],
                payload["event_id"],
                payload["event_version"],
                payload["event_type"],
                payload["event_subtype"],
                payload.get("published_at"),
                payload["first_seen_at"],
                payload.get("effective_at"),
                payload["source_id"],
                payload["source_type"],
                payload["source_quality"],
                int(bool(payload["pit_eligible"])),
                acquisition_mode,
                _canonical_json(payload),
                payload["data_fingerprint"],
            ),
        )
    return {"inserted": True, "event": payload}


def ingest_event_records(
    rows: Iterable[Mapping[str, object]],
    *,
    first_seen_at: datetime | str,
    acquisition_mode: str = "forward",
    path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH,
) -> dict:
    inserted = duplicates = 0
    errors = []
    for position, raw in enumerate(rows):
        try:
            result = append_event_record(
                normalize_event_record(raw, first_seen_at=first_seen_at, acquisition_mode=acquisition_mode),
                path,
            )
            inserted += int(result["inserted"])
            duplicates += int(not result["inserted"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append({"row": position, "source_id": raw.get("source_id"), "error": str(exc)})
    return {
        "received": inserted + duplicates + len(errors),
        "inserted": inserted,
        "duplicates": duplicates,
        "errors": errors,
        "research_shadow_only": True,
        "production_effect": "none",
    }


def load_events_as_of(
    cutoff: datetime | str,
    path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH,
) -> list[dict]:
    initialize_event_research_store(path)
    cutoff_iso = _utc(cutoff).isoformat()
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            """SELECT payload_json FROM event_records
            WHERE pit_eligible=1 AND first_seen_at <= ? AND (published_at IS NULL OR published_at <= ?)
            ORDER BY COALESCE(published_at, first_seen_at), first_seen_at, event_record_id""",
            (cutoff_iso, cutoff_iso),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def _asset_values(asset: Mapping[str, object], field: str, *, upper: bool = False) -> set[str]:
    value = asset.get(field)
    if field == "ticker" and value:
        value = [value]
    return set(_strings(value, upper=upper))


def event_relevance(event: Mapping[str, object], asset: Mapping[str, object]) -> dict | None:
    affected = event.get("affected") if isinstance(event.get("affected"), Mapping) else {}
    asset_tickers = _asset_values(asset, "ticker", upper=True) | _asset_values(asset, "tickers", upper=True)
    event_tickers = set(_strings(affected.get("assets"), upper=True))
    company_names = _asset_values(asset, "company_names") | _asset_values(asset, "name")
    event_companies = set(_strings(affected.get("companies")))
    sectors = _asset_values(asset, "sector") | _asset_values(asset, "sectors") | _asset_values(asset, "industry")
    event_sectors = set(_strings(affected.get("sectors"))) | set(_strings(affected.get("industries")))
    regions = _asset_values(asset, "region") | _asset_values(asset, "country")
    event_regions = set(_strings(affected.get("regions"))) | set(_strings(affected.get("countries")))
    commodities = _asset_values(asset, "commodity_exposures")
    event_commodities = set(_strings(affected.get("commodities")))
    level = None
    basis = None
    mapping_confidence = None
    if asset_tickers & event_tickers or company_names & event_companies:
        level, basis, mapping_confidence = 1, "direct_company_or_asset", 1.0
    elif sectors & event_sectors:
        level, basis, mapping_confidence = 2, "explicit_sector_or_industry", 0.85
    else:
        for relation in affected.get("relationships") or []:
            if not isinstance(relation, Mapping) or not relation.get("source_id"):
                continue
            related_asset = str(relation.get("asset") or "").upper()
            if related_asset and related_asset in asset_tickers:
                level, basis, mapping_confidence = 3, "explicit_supplier_or_customer", 0.75
                break
    if level is None and regions & event_regions:
        level, basis, mapping_confidence = 4, "explicit_region_or_country", 0.65
    if level is None and event.get("event_type") in {"macro", "market_shock"}:
        level, basis, mapping_confidence = 5, "broad_market_or_macro", 0.5
    if level is None and commodities & event_commodities:
        level, basis, mapping_confidence = 6, "explicit_commodity_exposure", 0.7
    if level is None:
        return None
    event_confidence = _number(event.get("confidence"))
    combined = min(mapping_confidence, event_confidence) if event_confidence is not None else mapping_confidence
    return {
        "relevance_level": level,
        "basis": basis,
        "mapping_confidence": mapping_confidence,
        "event_confidence": event_confidence,
        "relevance_confidence": combined,
        "direction_for_asset": "unknown",
        "no_keyword_only_mapping": True,
        "changes_trade_decision": False,
    }


def _age_bucket(days: float) -> str:
    if days <= 1:
        return "0-1d"
    if days <= 3:
        return "2-3d"
    if days <= 5:
        return "4-5d"
    if days <= 10:
        return "6-10d"
    return ">10d"


def build_signal_event_context(
    *,
    signal_id: str,
    signal_at: datetime | str,
    asset: Mapping[str, object],
    created_at: datetime | str,
    events: Sequence[Mapping[str, object]],
) -> dict:
    cutoff = _utc(signal_at)
    created = _utc(created_at)
    if created < cutoff:
        raise ValueError("Der Event-Sidecar darf nicht vor dem Signal erzeugt werden.")
    links = []
    future_known = []
    latest_versions: dict[str, Mapping[str, object]] = {}
    for event in events:
        first_seen = _utc(str(event["first_seen_at"]))
        published = _optional_utc(event.get("published_at"))
        if first_seen > cutoff or (published is not None and published > cutoff):
            continue
        event_id = str(event.get("event_id") or event.get("event_record_id") or "")
        existing = latest_versions.get(event_id)
        if existing is None or (
            first_seen,
            str(event.get("event_version") or ""),
            str(event.get("event_record_id") or ""),
        ) > (
            _utc(str(existing["first_seen_at"])),
            str(existing.get("event_version") or ""),
            str(existing.get("event_record_id") or ""),
        ):
            latest_versions[event_id] = event
    for event in latest_versions.values():
        first_seen = _utc(str(event["first_seen_at"]))
        published = _optional_utc(event.get("published_at"))
        relevance = event_relevance(event, asset)
        if relevance is None:
            continue
        expiry = _optional_utc(event.get("event_expiry"))
        if expiry is not None and expiry < cutoff:
            continue
        effective = _optional_utc(event.get("effective_at"))
        reference_time = published or effective or first_seen
        age_days = (cutoff - reference_time).total_seconds() / 86_400
        known_schedule = event.get("known_schedule") if isinstance(event.get("known_schedule"), Mapping) else {}
        effective_day = known_schedule.get("effective_date")
        days_to_event = _number(known_schedule.get("days_at_signal"))
        if effective is not None and effective > cutoff:
            days_to_event = (effective - cutoff).total_seconds() / 86_400
            effective_day = effective.date().isoformat()
        link = {
            "event_record_id": event["event_record_id"],
            "event_id": event["event_id"],
            "event_version": event["event_version"],
            "event_type": event["event_type"],
            "event_subtype": event["event_subtype"],
            "published_at": event.get("published_at"),
            "first_seen_at": event["first_seen_at"],
            "effective_at": event.get("effective_at"),
            "time_since_event_days": round(age_days, 6) if age_days >= 0 else None,
            "event_age_bucket": _age_bucket(age_days) if age_days >= 0 else "known_future",
            "days_to_known_event": round(days_to_event, 6) if days_to_event is not None else None,
            "severity": event.get("severity"),
            "confidence": event.get("confidence"),
            "expectation": event.get("expectation"),
            "relevance": relevance,
            "market_transmission": event.get("market_transmission") or [],
            "association_only": True,
            "causality_claimed": False,
        }
        links.append(link)
        if days_to_event is not None and days_to_event >= 0:
            future_known.append(
                {
                    "event_record_id": event["event_record_id"],
                    "effective_date": effective_day,
                    "days_at_signal": days_to_event,
                    "session_distance": None,
                    "session_distance_status": "unavailable_without_point_in_time_trading_calendar",
                }
            )
    links.sort(key=lambda item: (item["relevance"]["relevance_level"], item["event_record_id"]))
    context = {
        "context_schema_version": EVENT_CONTEXT_VERSION,
        "signal_id": str(signal_id),
        "signal_at": cutoff.isoformat(),
        "signal_cutoff": cutoff.isoformat(),
        "created_at": created.isoformat(),
        "asset": _clean(dict(asset)),
        "events": links,
        "event_count": len(links),
        "no_reliable_event_data_available": not bool(links),
        "missing_event_data_is_not_no_event": True,
        "known_future_events": future_known,
        "event_risk_windows": {
            "past_1d": sum(1 for item in links if item["time_since_event_days"] is not None and item["time_since_event_days"] <= 1),
            "past_3d": sum(1 for item in links if item["time_since_event_days"] is not None and item["time_since_event_days"] <= 3),
            "past_5d": sum(1 for item in links if item["time_since_event_days"] is not None and item["time_since_event_days"] <= 5),
            "past_10d": sum(1 for item in links if item["time_since_event_days"] is not None and item["time_since_event_days"] <= 10),
            "future_1d": sum(1 for item in future_known if item["days_at_signal"] <= 1),
            "future_3d": sum(1 for item in future_known if item["days_at_signal"] <= 3),
            "future_5d": sum(1 for item in future_known if item["days_at_signal"] <= 5),
            "session_windows": "unavailable unless explicitly stored point-in-time",
        },
        "guardrails": {
            "sidecar_only": True,
            "forward_snapshot_changed": False,
            "changes_trade_decision": False,
            "changes_score": False,
            "changes_stop_or_position_size": False,
            "automatic_strategy": False,
            "short_strategy": False,
            "broker_order": False,
            "broad_research_gate_dependency": False,
        },
    }
    context["context_fingerprint"] = _fingerprint(context)
    context["context_id"] = _fingerprint(
        {"signal_id": signal_id, "policy_version": EVENT_CONTEXT_VERSION, "signal_cutoff": cutoff.isoformat()}
    )
    return context


def append_signal_event_context(context: Mapping[str, object], path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH) -> dict:
    initialize_event_research_store(path)
    payload = dict(context)
    expected = _fingerprint({key: value for key, value in payload.items() if key not in {"context_fingerprint", "context_id"}})
    if payload.get("context_fingerprint") != expected:
        raise ValueError("Signal-Event-Kontext besitzt einen ungültigen Fingerabdruck.")
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT context_json, context_fingerprint FROM event_signal_contexts WHERE signal_id=? AND policy_version=?",
            (payload["signal_id"], EVENT_CONTEXT_VERSION),
        ).fetchone()
        if existing is not None:
            if existing["context_fingerprint"] != payload["context_fingerprint"]:
                raise ValueError("Ein Signal besitzt bereits einen abweichenden unveränderbaren Event-Sidecar.")
            return {"inserted": False, "context": json.loads(existing["context_json"])}
        connection.execute(
            """INSERT INTO event_signal_contexts
            (context_id, signal_id, signal_at, signal_cutoff, policy_version, created_at, context_json, context_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["context_id"], payload["signal_id"], payload["signal_at"], payload["signal_cutoff"],
                EVENT_CONTEXT_VERSION, payload["created_at"], _canonical_json(payload), payload["context_fingerprint"],
            ),
        )
        for link in payload.get("events") or []:
            event_record_id = str(link["event_record_id"])
            link_identity = {"context_id": payload["context_id"], "event_record_id": event_record_id}
            link_id = _fingerprint(link_identity)
            link_fingerprint = _fingerprint(link)
            connection.execute(
                """INSERT INTO event_signal_links
                (link_id, context_id, signal_id, event_record_id, relevance_level, relevance_confidence, payload_json, link_fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    link_id, payload["context_id"], payload["signal_id"], event_record_id,
                    int(link["relevance"]["relevance_level"]), link["relevance"].get("relevance_confidence"),
                    _canonical_json(link), link_fingerprint,
                ),
            )
    return {"inserted": True, "context": payload}


def append_market_reaction_label(
    *,
    event_record_id: str,
    horizon: str,
    observed_at: datetime | str,
    data_granularity: str,
    metrics: Mapping[str, object],
    path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH,
) -> dict:
    initialize_event_research_store(path)
    observed = _utc(observed_at)
    normalized_horizon = str(horizon).strip().casefold()
    normalized_granularity = str(data_granularity).strip().casefold()
    if normalized_horizon not in EVENT_REACTION_HORIZONS:
        raise ValueError(f"Nicht unterstützter Event-Reaktionshorizont: {horizon}")
    if normalized_horizon == "1h" and normalized_granularity in {"daily", "1d"}:
        raise ValueError("Daily-Daten dürfen kein 1h-Reaktionslabel erzeugen.")
    with _connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT first_seen_at, published_at FROM event_records WHERE event_record_id=?",
            (event_record_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unbekanntes Event für Market-Reaction-Label.")
        available_at = max(
            value for value in (_utc(row["first_seen_at"]), _optional_utc(row["published_at"])) if value is not None
        )
        if observed <= available_at:
            raise ValueError("Market-Reaction-Label muss strikt nach Eventverfügbarkeit beobachtet sein.")
        payload = {
            "reaction_schema_version": EVENT_REACTION_SCHEMA_VERSION,
            "event_record_id": event_record_id,
            "horizon": normalized_horizon,
            "observed_at": observed.isoformat(),
            "data_granularity": normalized_granularity,
            "metrics": {
                field: _number(metrics.get(field)) for field in EVENT_REACTION_METRICS
            },
            "metric_missingness": {
                field: _number(metrics.get(field)) is None for field in EVENT_REACTION_METRICS
            },
            "features_physically_separate": True,
            "association_only": True,
            "causality_claimed": False,
            "not_a_forward_trade_result": True,
        }
        fingerprint = _fingerprint(payload)
        reaction_id = _fingerprint(
            {
                "event_record_id": event_record_id,
                "horizon": normalized_horizon,
                "data_granularity": normalized_granularity,
            }
        )
        existing = connection.execute(
            "SELECT label_fingerprint FROM event_market_reaction_labels WHERE reaction_id=?",
            (reaction_id,),
        ).fetchone()
        if existing is not None:
            if existing["label_fingerprint"] != fingerprint:
                raise ValueError("Dasselbe Reaktionslabel besitzt abweichende unveränderbare Daten.")
            return {"inserted": False, "reaction_id": reaction_id, "label": payload}
        connection.execute(
            """INSERT INTO event_market_reaction_labels
            (reaction_id, event_record_id, horizon, observed_at, data_granularity, label_json, label_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                reaction_id,
                event_record_id,
                normalized_horizon,
                observed.isoformat(),
                normalized_granularity,
                _canonical_json(payload),
                fingerprint,
            ),
        )
    return {"inserted": True, "reaction_id": reaction_id, "label": payload}


def append_event_hypothesis_ledger_entry(
    *,
    hypothesis_id: str,
    recorded_at: datetime | str,
    action: str,
    hypothesis: str,
    event_type: str,
    parameters: Mapping[str, object],
    dataset_fingerprint: str,
    feature_version: str = EVENT_SCHEMA_VERSION,
    classification: str | None = None,
    status: str = "proposed",
    results: Mapping[str, object] | None = None,
    similar_hypotheses: Sequence[str] = (),
    path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH,
) -> dict:
    initialize_event_research_store(path)
    if event_type not in EVENT_GROUPS:
        raise ValueError("Event-Hypothese benötigt eine unterstützte Eventgruppe.")
    if classification not in {None, "A", "B", "C"}:
        raise ValueError("Research-Klassifikation muss A, B, C oder nicht verfügbar sein.")
    payload = {
        "ledger_version": EVENT_LEDGER_VERSION,
        "hypothesis_id": str(hypothesis_id),
        "recorded_at": _utc(recorded_at).isoformat(),
        "action": str(action),
        "hypothesis": str(hypothesis),
        "event_type": event_type,
        "parameters": _clean(dict(parameters)),
        "dataset_fingerprint": str(dataset_fingerprint),
        "feature_version": str(feature_version),
        "results": _clean(dict(results or {})),
        "classification": classification,
        "status": str(status),
        "similar_hypotheses": sorted(set(str(value) for value in similar_hypotheses)),
        "development_first": True,
        "freeze_before_validation": True,
        "holdout_selection_forbidden": True,
        "automatic_production_activation": False,
    }
    fingerprint = _fingerprint(payload)
    entry_id = _fingerprint({"hypothesis_id": hypothesis_id, "action": action, "fingerprint": fingerprint})
    with _connect(Path(path)) as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO event_hypothesis_ledger
            (ledger_entry_id, hypothesis_id, recorded_at, action, payload_json, entry_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (entry_id, hypothesis_id, payload["recorded_at"], action, _canonical_json(payload), fingerprint),
        )
    return {"inserted": cursor.rowcount == 1, "ledger_entry_id": entry_id, "entry": payload}


def _yahoo_news_event(raw: Mapping[str, object], symbol: str) -> dict | None:
    content = raw.get("content") if isinstance(raw.get("content"), Mapping) else {}
    title = str(raw.get("title") or content.get("title") or content.get("headline") or "").strip()
    link = raw.get("link")
    if not link and isinstance(content.get("canonicalUrl"), Mapping):
        link = content["canonicalUrl"].get("url")
    published = raw.get("providerPublishTime") or content.get("pubDate") or content.get("providerPublishTime")
    if isinstance(published, (int, float)):
        published = datetime.fromtimestamp(float(published), timezone.utc).isoformat()
    related = raw.get("relatedTickers") or []
    if not isinstance(related, list):
        related = []
    source_id = str(raw.get("uuid") or link or "").strip()
    if not title or not source_id:
        return None
    raw_fingerprint = _fingerprint(raw)
    lower = title.casefold()
    event_type = "company"
    event_subtype = "company_news_unclassified"
    keyword_groups = (
        (("clinical trial", "phase 1", "phase 2", "phase 3", "endpoint"), "company", "clinical_trial"),
        (("fda", "ema approval", "regulatory approval"), "company", "regulatory_approval"),
        (("earnings", "quarterly results"), "company", "earnings"),
        (("guidance", "outlook"), "company", "company_news_unclassified"),
        (("fed", "ecb", "central bank", "interest rate"), "macro", "central_bank_guidance"),
        (("inflation", "cpi", "pce"), "macro", "inflation_cpi_pce"),
        (("jobs report", "unemployment", "payroll"), "macro", "labor_market"),
        (("sanction", "tariff", "export control"), "geopolitics_policy", "policy_unclassified"),
        (("war", "missile", "invasion", "ceasefire"), "geopolitics_policy", "policy_unclassified"),
        (("vix", "volatility shock", "market crash"), "market_shock", "market_shock_unclassified"),
        (("oil shock", "gas shock", "crude surge"), "market_shock", "oil_gas_shock"),
    )
    for terms, group, subtype in keyword_groups:
        if any(term in lower for term in terms):
            event_type, event_subtype = group, subtype
            break
    provider = raw.get("publisher")
    if not provider and isinstance(raw.get("provider"), Mapping):
        provider = raw["provider"].get("displayName")
    affected_assets = [str(value).upper() for value in related if str(value).strip()]
    if symbol.upper() not in affected_assets:
        affected_assets.append(symbol.upper())
    return {
        "event_id": _fingerprint({"provider": "yahoo_finance_news", "source_id": source_id}),
        "event_version": raw_fingerprint,
        "event_type": event_type,
        "event_subtype": event_subtype,
        "published_at": published,
        "source_id": source_id,
        "source_type": "news_aggregator",
        "source_quality": "secondary_aggregated",
        "title": title,
        "summary": title,
        "affected_assets": affected_assets,
        "direction": "unknown",
        "severity": None,
        "confidence": 0.6,
        "uncertainty": "Headline/Metadaten aus Yahoo-Aggregation; Primärquelle und Sachinhalt nicht automatisch bestätigt.",
        "source_locator": link,
        "publisher": provider,
        "retrieved_via": "Yahoo Finance / yfinance ticker news",
        "raw_source_fingerprint": raw_fingerprint,
        "availability_basis": "forward_first_seen",
    }


def _default_news_loader(symbol: str) -> list[dict]:
    try:
        import yfinance as yf

        return [dict(value) for value in (yf.Ticker(symbol).news or [])[:8] if isinstance(value, Mapping)]
    except Exception:
        return []


def _read_forward_signals_read_only(signal_ids: Sequence[str], forward_path: Path) -> list[dict]:
    if not signal_ids or not Path(forward_path).exists():
        return []
    uri = Path(forward_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in signal_ids)
        rows = connection.execute(
            f"SELECT signal_id, signal_at, snapshot_json FROM swing_signals WHERE signal_id IN ({placeholders}) ORDER BY signal_at, signal_id",
            tuple(signal_ids),
        ).fetchall()
    finally:
        connection.close()
    return [
        {"signal_id": str(row["signal_id"]), "signal_at": str(row["signal_at"]), "snapshot": json.loads(row["snapshot_json"])}
        for row in rows
    ]


def _scheduled_event_from_snapshot(signal: Mapping[str, object]) -> dict | None:
    snapshot = signal.get("snapshot") if isinstance(signal.get("snapshot"), Mapping) else {}
    strategy = snapshot.get("strategy") if isinstance(snapshot.get("strategy"), Mapping) else {}
    asset = snapshot.get("asset") if isinstance(snapshot.get("asset"), Mapping) else {}
    effective_day = strategy.get("known_event_date_at_signal")
    if not effective_day:
        return None
    symbol = str(asset.get("ticker") or "").upper()
    return {
        "event_type": "company",
        "event_subtype": "scheduled_corporate_event",
        "source_id": f"immutable-forward-snapshot|{signal['signal_id']}|{effective_day}",
        "source_type": "immutable_forward_signal_snapshot",
        "source_quality": "secondary_aggregated",
        "published_at": None,
        "availability_basis": "immutable_forward_signal_snapshot",
        "title": "Zum Signalzeitpunkt bekannter Unternehmenstermin",
        "summary": "Terminart und exakte Veröffentlichungszeit sind im Legacy-Snapshot nicht weiter belegt.",
        "affected_assets": [symbol] if symbol else [],
        "effective_at": None,
        "direction": "unknown",
        "severity": None,
        "confidence": 0.6,
        "uncertainty": "Nur Datum aus unveränderbarem Signalsnapshot; keine rückwirkende Ereignisart ergänzt.",
        "source_locator": f"swing_forward.sqlite3#signal:{signal['signal_id']}",
        "retrieved_via": "existing immutable forward snapshot",
        "known_schedule": {
            "effective_date": str(effective_day),
            "days_at_signal": strategy.get("event_days_at_signal"),
        },
    }


def _attach_known_schedule(event: dict, raw: Mapping[str, object]) -> dict:
    if isinstance(raw.get("known_schedule"), Mapping):
        event["known_schedule"] = _clean(dict(raw["known_schedule"]))
        event["data_fingerprint"] = _fingerprint(
            {key: value for key, value in event.items() if key not in {"data_fingerprint", "event_record_id"}}
        )
        event["event_record_id"] = _fingerprint(
            {
                "event_id": event["event_id"],
                "event_version": event["event_version"],
                "data_fingerprint": event["data_fingerprint"],
            }
        )
    return event


def collect_forward_event_contexts(
    *,
    signal_ids: Sequence[str],
    forward_path: Path,
    collected_at: datetime | str,
    path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH,
    news_loader: Callable[[str], Sequence[Mapping[str, object]]] | None = None,
    collect_news: bool = True,
) -> dict:
    initialize_event_research_store(path)
    signals = _read_forward_signals_read_only(list(dict.fromkeys(signal_ids)), Path(forward_path))
    loader = news_loader or _default_news_loader
    inserted_events = duplicate_events = inserted_contexts = existing_contexts = 0
    errors = []
    contexts = []
    for signal in signals:
        signal_id = str(signal["signal_id"])
        with _connect(Path(path)) as connection:
            exists = connection.execute(
                "SELECT context_json FROM event_signal_contexts WHERE signal_id=? AND policy_version=?",
                (signal_id, EVENT_CONTEXT_VERSION),
            ).fetchone()
        if exists is not None:
            contexts.append(json.loads(exists["context_json"]))
            existing_contexts += 1
            continue
        snapshot = signal["snapshot"]
        asset = dict(snapshot.get("asset") or {})
        schedule = _scheduled_event_from_snapshot(signal)
        if schedule is not None:
            normalized = _attach_known_schedule(
                normalize_event_record(schedule, first_seen_at=signal["signal_at"], acquisition_mode="forward"),
                schedule,
            )
            result = append_event_record(normalized, path)
            inserted_events += int(result["inserted"])
            duplicate_events += int(not result["inserted"])
        symbol = str(asset.get("ticker") or "").upper()
        if collect_news and symbol:
            try:
                for raw_news in loader(symbol):
                    normalized_raw = _yahoo_news_event(raw_news, symbol)
                    if normalized_raw is None:
                        continue
                    result = append_event_record(
                        normalize_event_record(normalized_raw, first_seen_at=collected_at, acquisition_mode="forward"),
                        path,
                    )
                    inserted_events += int(result["inserted"])
                    duplicate_events += int(not result["inserted"])
            except Exception as exc:
                errors.append({"signal_id": signal_id, "symbol": symbol, "error": str(exc)})
        universe = snapshot.get("universe") if isinstance(snapshot.get("universe"), Mapping) else {}
        relevance_asset = {
            **asset,
            "sector": universe.get("sector"),
            "industry": universe.get("industry"),
            "region": asset.get("region"),
            "commodity_exposures": universe.get("commodity_exposures") or [],
        }
        context = build_signal_event_context(
            signal_id=signal_id,
            signal_at=signal["signal_at"],
            asset=relevance_asset,
            created_at=collected_at,
            events=load_events_as_of(signal["signal_at"], path),
        )
        stored = append_signal_event_context(context, path)
        inserted_contexts += int(stored["inserted"])
        existing_contexts += int(not stored["inserted"])
        contexts.append(stored["context"])
    return {
        "signals_requested": len(set(signal_ids)),
        "signals_found": len(signals),
        "events_inserted": inserted_events,
        "events_existing": duplicate_events,
        "contexts_inserted": inserted_contexts,
        "contexts_existing": existing_contexts,
        "contexts_without_reliable_event_data": sum(
            bool(context.get("no_reliable_event_data_available")) for context in contexts
        ),
        "errors": errors,
        "research_shadow_only": True,
        "production_effect": "none",
        "broad_research_blocked": False,
        "long_v1_changed": False,
        "short_strategy": False,
        "broker_order": False,
    }


def load_signal_event_contexts(path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH) -> list[dict]:
    initialize_event_research_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT context_json FROM event_signal_contexts ORDER BY signal_at, signal_id"
        ).fetchall()
    return [json.loads(row["context_json"]) for row in rows]


def build_forward_event_diagnostics(
    forward_signals: Sequence[Mapping[str, object]],
    event_contexts: Sequence[Mapping[str, object]],
) -> dict:
    """Describe event context around closed forward trades without deriving a rule."""
    contexts = {str(item.get("signal_id") or ""): dict(item) for item in event_contexts}
    terminal_types = {"target_1_reached", "target_2_reached", "stop_reached", "ambiguous_sequence"}
    rows = []
    for signal in forward_signals:
        events = [dict(item) for item in (signal.get("events") or []) if isinstance(item, Mapping)]
        terminal = next(
            (item for item in reversed(events) if str(item.get("event_type") or "") in terminal_types),
            None,
        )
        if terminal is None:
            continue
        payload = terminal.get("payload") if isinstance(terminal.get("payload"), Mapping) else {}
        result_r = _number(payload.get("result_r"))
        signal_id = str(signal.get("signal_id") or "")
        context = contexts.get(signal_id)
        context_events = list((context or {}).get("events") or [])
        event_types = sorted({str(item.get("event_type") or "unknown") for item in context_events})
        event_subtypes = sorted({str(item.get("event_subtype") or "unknown") for item in context_events})
        positive_surprise = any(
            _number((item.get("expectation") or {}).get("surprise_value")) is not None
            and float((item.get("expectation") or {})["surprise_value"]) > 0
            for item in context_events
            if isinstance(item, Mapping)
        )
        negative_company = any(
            item.get("event_type") == "company"
            and isinstance(item.get("relevance"), Mapping)
            and item["relevance"].get("direction_for_asset") == "negative"
            for item in context_events
            if isinstance(item, Mapping)
        )
        rows.append(
            {
                "signal_id": signal_id,
                "ticker": str(((signal.get("snapshot") or {}).get("asset") or {}).get("ticker") or "unknown"),
                "result_r": result_r,
                "win": result_r is not None and result_r > 0,
                "loss": result_r is not None and result_r < 0,
                "event_context_available": context is not None and bool(context_events),
                "no_reliable_event_data_available": (
                    context is None or bool(context.get("no_reliable_event_data_available"))
                ),
                "event_types": event_types,
                "event_subtypes": event_subtypes,
                "around_earnings": "earnings" in event_subtypes,
                "geopolitical_context": "geopolitics_policy" in event_types,
                "market_shock_context": "market_shock" in event_types,
                "positive_surprise": positive_surprise,
                "negative_company_event": negative_company,
            }
        )
    return {
        "closed_forward_trades": len(rows),
        "with_reliable_event_context": sum(row["event_context_available"] for row in rows),
        "without_reliable_event_context": sum(row["no_reliable_event_data_available"] for row in rows),
        "losses_with_negative_company_event": sum(row["loss"] and row["negative_company_event"] for row in rows),
        "trades_around_earnings": sum(row["around_earnings"] for row in rows),
        "losses_with_geopolitical_context": sum(row["loss"] and row["geopolitical_context"] for row in rows),
        "losses_with_market_shock_context": sum(row["loss"] and row["market_shock_context"] for row in rows),
        "wins_with_positive_surprise": sum(row["win"] and row["positive_surprise"] for row in rows),
        "rows": rows,
        "small_sample_rule_change_forbidden": True,
        "automatic_strategy_change": False,
        "production_effect": "none",
    }


def event_coverage_report(path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH) -> dict:
    initialize_event_research_store(path)
    with _connect(Path(path)) as connection:
        event_rows = connection.execute("SELECT payload_json, acquisition_mode FROM event_records").fetchall()
        links = int(connection.execute("SELECT COUNT(*) FROM event_signal_links").fetchone()[0])
        contexts = int(connection.execute("SELECT COUNT(*) FROM event_signal_contexts").fetchone()[0])
        labels = int(connection.execute("SELECT COUNT(*) FROM event_market_reaction_labels").fetchone()[0])
    events = [json.loads(row["payload_json"]) for row in event_rows]
    by_type = {}
    for event_type in sorted(EVENT_GROUPS):
        subset = [event for event in events if event["event_type"] == event_type]
        by_type[event_type] = {
            "events": len(subset),
            "first_published_at": min((event["published_at"] for event in subset if event.get("published_at")), default=None),
            "last_published_at": max((event["published_at"] for event in subset if event.get("published_at")), default=None),
            "assets": len({asset for event in subset for asset in event.get("affected", {}).get("assets", [])}),
            "exact_timestamp_share": (sum(bool(event.get("published_at")) for event in subset) / len(subset)) if subset else None,
            "expectation_share": (sum(event.get("expectation", {}).get("expected_value") is not None for event in subset) / len(subset)) if subset else None,
            "entity_mapping_share": (sum(bool(event.get("affected", {}).get("assets") or event.get("affected", {}).get("companies")) for event in subset) / len(subset)) if subset else None,
            "missingness": {
                key: sum(bool(event.get("missingness", {}).get(key)) for event in subset)
                for key in ("published_at", "effective_at", "direction", "severity", "confidence", "expectation", "actual")
            },
        }
    return {
        "event_store_schema_version": EVENT_STORE_SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "event_code_fingerprint": EVENT_CODE_FINGERPRINT,
        "supported_event_groups": sorted(EVENT_GROUPS),
        "events": len(events),
        "forward_events": sum(row["acquisition_mode"] == "forward" for row in event_rows),
        "historical_events": sum(row["acquisition_mode"] == "historical_backfill" for row in event_rows),
        "signal_contexts": contexts,
        "event_signal_links": links,
        "market_reaction_labels": labels,
        "by_event_type": by_type,
        "historical_coverage_complete": False,
        "current_sources": sorted({event["source_type"] for event in events}),
        "production_effect": "none",
        "broad_research_gate_dependency": False,
    }


def event_research_store_audit(path: Path = DEFAULT_EVENT_RESEARCH_DB_PATH) -> dict:
    initialize_event_research_store(path)
    coverage = event_coverage_report(path)
    with _connect(Path(path)) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        invalid_fingerprints = 0
        for row in connection.execute("SELECT payload_json, data_fingerprint FROM event_records"):
            payload = json.loads(row["payload_json"])
            expected = _fingerprint(
                {key: value for key, value in payload.items() if key not in {"data_fingerprint", "event_record_id"}}
            )
            invalid_fingerprints += int(expected != row["data_fingerprint"])
    return {
        "integrity": integrity,
        "invalid_event_fingerprints": invalid_fingerprints,
        **coverage,
        "append_only": True,
        "research_shadow_only": True,
        "automatic_production_activation": False,
        "short_strategy": False,
        "broker_order": False,
    }
