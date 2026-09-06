from __future__ import annotations

"""Transactional ENTRY-to-trading research handoff import.

The importer deliberately ends at research candidates and DRAFT experiment
definitions.  It has no dependency on scanners, strategy configuration,
backtest runners, paper trading, user trades, brokers, or order execution.
"""

import hashlib
import json
import re
import sqlite3
import tempfile
import unicodedata
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import (
    ALLOWED_AREAS,
    ALLOWED_EVIDENCE_STRENGTHS,
    ALLOWED_RATINGS,
    DEFAULT_DATABASE_PATH,
    initialize_database,
)
from .source_identity import inspect_source_identity, normalize_source_url
from .store import ResearchKnowledgeBase, normalize_claim


SCHEMA_VERSION = "trading_handoff_v1"
ORIGIN_SYSTEM = "ENTRY"
IMPORT_STATUSES = {
    "IMPORTED",
    "UPDATED",
    "NO_CHANGE",
    "CONFLICT",
    "REJECTED_INVALID",
    "FAILED_RETRYABLE",
}
EXIT_CODES = {
    "IMPORTED": 0,
    "UPDATED": 0,
    "NO_CHANGE": 0,
    "CONFLICT": 3,
    "REJECTED_INVALID": 2,
    "FAILED_RETRYABLE": 75,
}
VERIFICATION_ALIASES = {"MOSTLY_SUPPORTED": "PARTIALLY_SUPPORTED"}
ALLOWED_VERIFICATION_STATES = {
    "UNVERIFIED",
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONFLICTING_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "REFUTED",
    "OUTDATED",
}
TRADING_ELIGIBLE = {"TRADING_RELEVANT"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class HandoffValidationError(ValueError):
    """Raised when a handoff package cannot safely enter the research store."""


class HandoffConflict(RuntimeError):
    """Raised internally for an exact source-identity collision."""


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HandoffValidationError(f"Pflichtfeld '{field}' fehlt oder ist leer.")
    return text


def _nullable_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HandoffValidationError(f"Feld '{field}' muss Text oder null sein.")
    return value.strip() or None


def _iso_date(value: object, field: str, *, required: bool = False) -> str | None:
    if value is None or str(value).strip() == "":
        if required:
            raise HandoffValidationError(f"Pflichtfeld '{field}' fehlt oder ist leer.")
        return None
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as exc:
        raise HandoffValidationError(f"Feld '{field}' muss ein ISO-Datum YYYY-MM-DD sein.") from exc


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise HandoffValidationError(f"Feld '{field}' muss eine Liste sein.")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _required_text(item, f"{field}[{index}]")
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _reference(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HandoffValidationError(f"Feld '{field}' muss ein Objekt sein.")
    url = _nullable_text(value.get("url"), f"{field}.url")
    if url and normalize_source_url(url) is None:
        raise HandoffValidationError(f"Feld '{field}.url' enthält keine gültige HTTP(S)-URL.")
    return {
        "title": _required_text(value.get("title"), f"{field}.title"),
        "url": url,
        "publisher": _nullable_text(value.get("publisher"), f"{field}.publisher"),
        "published_date": _iso_date(value.get("published_date"), f"{field}.published_date"),
        "notes": str(value.get("notes") or "").strip(),
    }


def _references(value: object, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise HandoffValidationError(f"Feld '{field}' muss eine Liste sein.")
    unique: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value):
        normalized = _reference(item, f"{field}[{index}]")
        unique[_fingerprint(normalized)] = normalized
    return [unique[key] for key in sorted(unique)]


def _video_timestamps(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise HandoffValidationError(f"Feld '{field}' muss eine Liste sein.")
    normalized: list[object] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            normalized.append(_required_text(item, f"{field}[{index}]"))
        elif isinstance(item, Mapping):
            if not item:
                raise HandoffValidationError(f"Feld '{field}[{index}]' darf nicht leer sein.")
            normalized.append(dict(item))
        else:
            raise HandoffValidationError(
                f"Feld '{field}[{index}]' muss Text oder ein Zeitstempel-Objekt sein."
            )
    return normalized


def _suggestion(value: object, field: str) -> str | dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _required_text(value, field)
    if isinstance(value, Mapping):
        if not value:
            raise HandoffValidationError(f"Feld '{field}' darf nicht leer sein.")
        return dict(value)
    raise HandoffValidationError(f"Feld '{field}' muss Text, Objekt oder null sein.")


def _validate_structured_hypothesis(value: object, field: str) -> dict[str, Any] | None:
    suggestion = _suggestion(value, field)
    if not isinstance(suggestion, dict):
        return None
    required = {
        "title",
        "area",
        "category",
        "claim",
        "mechanism",
        "external_evidence",
        "rating",
        "risks_limitations",
    }
    missing = sorted(name for name in required if not str(suggestion.get(name) or "").strip())
    if missing:
        raise HandoffValidationError(
            f"Strukturierte Hypothese '{field}' benötigt: {', '.join(missing)}."
        )
    if suggestion["area"] not in ALLOWED_AREAS:
        raise HandoffValidationError(f"Feld '{field}.area' hat einen unbekannten Wert.")
    if suggestion["external_evidence"] not in ALLOWED_EVIDENCE_STRENGTHS:
        raise HandoffValidationError(f"Feld '{field}.external_evidence' hat einen unbekannten Wert.")
    if suggestion["rating"] not in ALLOWED_RATINGS:
        raise HandoffValidationError(f"Feld '{field}.rating' hat einen unbekannten Wert.")
    return suggestion


def _validate_structured_test(value: object, field: str) -> dict[str, Any] | None:
    suggestion = _suggestion(value, field)
    if not isinstance(suggestion, dict):
        return None
    required = {"title", "test_definition", "data_universe", "point_in_time_rules", "baseline"}
    missing = sorted(name for name in required if not str(suggestion.get(name) or "").strip())
    if missing:
        raise HandoffValidationError(
            f"Strukturierter Testvorschlag '{field}' benötigt: {', '.join(missing)}."
        )
    features = suggestion.get("features", [])
    if not isinstance(features, list):
        raise HandoffValidationError(f"Feld '{field}.features' muss eine Liste sein.")
    parameters = suggestion.get("parameters", {})
    if not isinstance(parameters, Mapping):
        raise HandoffValidationError(f"Feld '{field}.parameters' muss ein Objekt sein.")
    _iso_date(suggestion.get("period_start"), f"{field}.period_start")
    _iso_date(suggestion.get("period_end"), f"{field}.period_end")
    return suggestion


def validate_handoff(package: object) -> dict[str, Any]:
    if not isinstance(package, Mapping):
        raise HandoffValidationError("Das Handoff muss ein JSON-Objekt sein.")
    schema_version = _required_text(package.get("schema_version"), "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise HandoffValidationError(
            f"Nicht unterstützte Schema-Version '{schema_version}'; erwartet wird '{SCHEMA_VERSION}'."
        )
    source_hash = _required_text(package.get("source_hash"), "source_hash").casefold()
    if not SHA256_PATTERN.fullmatch(source_hash):
        raise HandoffValidationError("Feld 'source_hash' muss ein SHA-256 mit 64 Hex-Zeichen sein.")
    url = _nullable_text(package.get("url"), "url")
    if url and normalize_source_url(url, platform=package.get("platform")) is None:
        raise HandoffValidationError("Feld 'url' enthält keine gültige HTTP(S)-URL.")
    raw_claims = package.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise HandoffValidationError("Pflichtfeld 'claims' muss eine nicht leere Liste sein.")

    claims: list[dict[str, Any]] = []
    ignored_claim_ids: list[str] = []
    seen_origin_ids: set[str] = set()
    for index, raw in enumerate(raw_claims):
        field = f"claims[{index}]"
        if not isinstance(raw, Mapping):
            raise HandoffValidationError(f"Feld '{field}' muss ein Objekt sein.")
        origin_claim_id = _required_text(raw.get("origin_claim_id"), f"{field}.origin_claim_id")
        if origin_claim_id in seen_origin_ids:
            raise HandoffValidationError(f"Doppelte origin_claim_id '{origin_claim_id}' im Paket.")
        seen_origin_ids.add(origin_claim_id)
        trading_relevance = _required_text(
            raw.get("trading_relevance"), f"{field}.trading_relevance"
        )
        if trading_relevance not in TRADING_ELIGIBLE:
            ignored_claim_ids.append(origin_claim_id)
            continue
        state_raw = _required_text(raw.get("verification_status"), f"{field}.verification_status").upper()
        state = VERIFICATION_ALIASES.get(state_raw, state_raw)
        if state not in ALLOWED_VERIFICATION_STATES:
            raise HandoffValidationError(f"Feld '{field}.verification_status' hat einen unbekannten Wert.")
        evidence_strength = _required_text(
            raw.get("evidence_strength"), f"{field}.evidence_strength"
        ).casefold()
        if evidence_strength not in ALLOWED_EVIDENCE_STRENGTHS:
            raise HandoffValidationError(f"Feld '{field}.evidence_strength' hat einen unbekannten Wert.")
        confidence = raw.get("confidence")
        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise HandoffValidationError(f"Feld '{field}.confidence' muss numerisch oder null sein.")
            if not 0 <= float(confidence) <= 100:
                raise HandoffValidationError(f"Feld '{field}.confidence' muss zwischen 0 und 100 liegen.")
        hypothesis = _suggestion(raw.get("suggested_hypothesis"), f"{field}.suggested_hypothesis")
        test = _suggestion(raw.get("suggested_test"), f"{field}.suggested_test")
        if hypothesis is None and test is None:
            raise HandoffValidationError(
                f"'{field}' benötigt 'suggested_hypothesis' oder 'suggested_test'."
            )
        structured_hypothesis = _validate_structured_hypothesis(
            raw.get("suggested_hypothesis"), f"{field}.suggested_hypothesis"
        )
        structured_test = _validate_structured_test(
            raw.get("suggested_test"), f"{field}.suggested_test"
        )
        if structured_test is not None and structured_hypothesis is None:
            raise HandoffValidationError(
                f"'{field}' benötigt für einen strukturierten Testvorschlag auch eine strukturierte Hypothese."
            )
        raw_tags = _string_list(raw.get("tags", []), f"{field}.tags")
        tags_by_key: dict[str, str] = {}
        for tag in raw_tags:
            tags_by_key.setdefault(_normalize_tag(tag), tag)
        claim = {
            "origin_claim_id": origin_claim_id,
            "claim_text": _required_text(raw.get("claim_text"), f"{field}.claim_text"),
            "video_timestamps": _video_timestamps(
                raw.get("video_timestamps"), f"{field}.video_timestamps"
            ),
            "claim_type": _required_text(raw.get("claim_type"), f"{field}.claim_type"),
            "trading_relevance": trading_relevance,
            "market_scope": _required_text(raw.get("market_scope"), f"{field}.market_scope"),
            "verification_status": state,
            "entry_verification_status": state_raw,
            "evidence_strength": evidence_strength,
            "confidence": None if confidence is None else float(confidence),
            "rationale": _required_text(raw.get("rationale"), f"{field}.rationale"),
            "evidence": _references(raw.get("evidence"), f"{field}.evidence"),
            "counter_evidence": _references(
                raw.get("counter_evidence"), f"{field}.counter_evidence"
            ),
            "limitations": _string_list(raw.get("limitations"), f"{field}.limitations"),
            "risks": _string_list(raw.get("risks"), f"{field}.risks"),
            "valid_as_of": _iso_date(raw.get("valid_as_of"), f"{field}.valid_as_of", required=True),
            "tags": [tags_by_key[key] for key in sorted(tags_by_key)],
            "suggested_hypothesis": hypothesis,
            "suggested_test": test,
            "structured_hypothesis": structured_hypothesis,
            "structured_test": structured_test,
        }
        claims.append(claim)
    if not claims:
        raise HandoffValidationError("Das Paket enthält keine ausdrücklich tradingrelevanten Claims.")
    claims.sort(key=lambda item: item["origin_claim_id"])
    try:
        origin_payload = json.loads(_canonical_json(package))
    except (TypeError, ValueError) as exc:
        raise HandoffValidationError(
            "Das Handoff enthält nicht kanonisch darstellbare JSON-Werte."
        ) from exc
    normalized = {
        "schema_version": schema_version,
        "handoff_id": _required_text(package.get("handoff_id"), "handoff_id"),
        "entry_source_id": _required_text(package.get("entry_source_id"), "entry_source_id"),
        "source_hash": source_hash,
        "title": _required_text(package.get("title"), "title"),
        "platform": _required_text(package.get("platform"), "platform").casefold(),
        "creator": _nullable_text(package.get("creator"), "creator"),
        "url": url,
        "published_date": _iso_date(package.get("published_date"), "published_date"),
        "neutral_summary": _required_text(package.get("neutral_summary"), "neutral_summary"),
        "claims": claims,
        "ignored_claim_ids": sorted(ignored_claim_ids),
        "origin_payload": origin_payload,
    }
    normalized["handoff_fingerprint"] = _fingerprint(origin_payload)
    return normalized


def _source_type(platform: str) -> str:
    return platform if platform in {"youtube", "tiktok"} else "other"


def _latest_handoff(connection: sqlite3.Connection, handoff_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM entry_handoff_imports
        WHERE origin_system = 'ENTRY' AND handoff_id = ?
        ORDER BY imported_at DESC, rowid DESC LIMIT 1
        """,
        (handoff_id,),
    ).fetchone()


def _latest_claim_import(
    connection: sqlite3.Connection, origin_source_id: str, origin_claim_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM entry_claim_imports
        WHERE origin_system = 'ENTRY' AND origin_source_id = ? AND origin_claim_id = ?
        ORDER BY imported_at DESC, rowid DESC LIMIT 1
        """,
        (origin_source_id, origin_claim_id),
    ).fetchone()


def _semantic_row(row: sqlite3.Row | None, excluded: Iterable[str] = ()) -> dict[str, Any] | None:
    if row is None:
        return None
    excluded_set = set(excluded)
    return {key: row[key] for key in row.keys() if key not in excluded_set}


def _managed_state(
    connection: sqlite3.Connection,
    claim_id: str,
    hypothesis_id: str | None,
    experiment_id: str | None,
) -> str:
    claim = connection.execute("SELECT * FROM source_claims WHERE id = ?", (claim_id,)).fetchone()
    domain = connection.execute(
        """SELECT * FROM claim_domain_assessments WHERE claim_id = ?
           ORDER BY classified_at DESC, rowid DESC LIMIT 1""",
        (claim_id,),
    ).fetchone()
    verification = connection.execute(
        """SELECT * FROM claim_verification_assessments WHERE claim_id = ?
           ORDER BY assessed_at DESC, rowid DESC LIMIT 1""",
        (claim_id,),
    ).fetchone()
    references: list[dict[str, Any]] = []
    if verification is not None:
        references = [
            _semantic_row(row, {"id", "assessment_id"}) or {}
            for row in connection.execute(
                """SELECT * FROM claim_verification_references
                   WHERE assessment_id = ? ORDER BY reference_type, reference_fingerprint""",
                (verification["id"],),
            )
        ]
    hypothesis = (
        connection.execute("SELECT * FROM hypotheses WHERE id = ?", (hypothesis_id,)).fetchone()
        if hypothesis_id
        else None
    )
    experiment = (
        connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        if experiment_id
        else None
    )
    features = (
        [
            str(row["feature"])
            for row in connection.execute(
                "SELECT feature FROM experiment_features WHERE experiment_id = ? ORDER BY feature COLLATE NOCASE",
                (experiment_id,),
            )
        ]
        if experiment_id
        else []
    )
    entry_tags = [
        str(row["normalized_tag"])
        for row in connection.execute(
            """SELECT normalized_tag FROM source_claim_tags
               WHERE claim_id = ? AND origin_system = 'ENTRY' ORDER BY normalized_tag""",
            (claim_id,),
        )
    ]
    state = {
        "claim": _semantic_row(claim, {"id", "created_at"}),
        "domain": _semantic_row(domain, {"id", "classified_at", "classification_fingerprint"}),
        "verification": _semantic_row(
            verification, {"id", "assessed_at", "assessment_fingerprint"}
        ),
        "references": references,
        "entry_tags": entry_tags,
        "hypothesis": _semantic_row(hypothesis, {"id", "created_at", "updated_at"}),
        "experiment": _semantic_row(experiment, {"id", "created_at", "updated_at"}),
        "features": features,
    }
    return _fingerprint(state)


def _record_conflict(
    connection: sqlite3.Connection,
    package: Mapping[str, Any],
    *,
    origin_claim_id: str | None,
    existing_import_id: str | None,
    conflict_type: str,
    reason: str,
    details: Mapping[str, Any],
    detected_at: str,
) -> str:
    conflict_id = _id()
    connection.execute(
        """
        INSERT OR IGNORE INTO entry_handoff_conflicts (
            id, handoff_id, origin_system, origin_source_id, origin_claim_id,
            existing_import_id, incoming_fingerprint, conflict_type, reason,
            details_json, incoming_payload_json, detected_at
        ) VALUES (?, ?, 'ENTRY', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conflict_id,
            package["handoff_id"],
            package["entry_source_id"],
            origin_claim_id or "",
            existing_import_id,
            package["handoff_fingerprint"],
            conflict_type,
            reason,
            _canonical_json(details),
            _canonical_json(package["origin_payload"]),
            detected_at,
        ),
    )
    row = connection.execute(
        """SELECT id FROM entry_handoff_conflicts
           WHERE handoff_id = ? AND origin_claim_id IS ?
             AND incoming_fingerprint = ? AND conflict_type = ?""",
        (
            package["handoff_id"],
            origin_claim_id or "",
            package["handoff_fingerprint"],
            conflict_type,
        ),
    ).fetchone()
    return str(row["id"] if row else conflict_id)


def _find_or_create_source(
    connection: sqlite3.Connection, package: Mapping[str, Any], imported_at: str
) -> tuple[str, bool]:
    prior = connection.execute(
        """SELECT source_id FROM entry_handoff_imports
           WHERE origin_system = 'ENTRY' AND origin_source_id = ?
           ORDER BY imported_at DESC, rowid DESC LIMIT 1""",
        (package["entry_source_id"],),
    ).fetchone()
    if prior is None:
        prior = connection.execute(
            """SELECT source_id FROM entry_handoff_imports
               WHERE origin_system = 'ENTRY' AND source_hash = ?
               ORDER BY imported_at DESC, rowid DESC LIMIT 1""",
            (package["source_hash"],),
        ).fetchone()
    identity = inspect_source_identity(
        title=package["title"],
        platform=package["platform"],
        creator=package["creator"],
        direct_url=package["url"],
        published_date=package["published_date"],
    )
    exact_source_ids: set[str] = set()
    for identity_type, identity_value in identity["identity_keys"]:
        row = connection.execute(
            "SELECT source_id FROM source_identity_keys WHERE identity_type = ? AND identity_value = ?",
            (identity_type, identity_value),
        ).fetchone()
        if row is not None:
            exact_source_ids.add(str(row["source_id"]))
    if prior is not None:
        exact_source_ids.add(str(prior["source_id"]))
    if len(exact_source_ids) > 1:
        raise HandoffConflict("ENTRY-Herkunft und exakte Quellenidentität zeigen auf verschiedene Quellen.")
    created = False
    if exact_source_ids:
        source_id = next(iter(exact_source_ids))
    else:
        source_id = _id()
        connection.execute(
            """INSERT INTO research_sources (
                   id, title, source_type, reference, source_date, neutral_summary, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source_id,
                package["title"],
                _source_type(package["platform"]),
                package["url"],
                package["published_date"],
                package["neutral_summary"],
                imported_at,
            ),
        )
        created = True
    ResearchKnowledgeBase._append_source_provenance(
        connection,
        source_id=source_id,
        identity=identity,
        provenance=f"ENTRY-Handoff {package['handoff_id']}",
        captured_at=imported_at,
    )
    return source_id, created


def _insert_domain_assessment(
    connection: sqlite3.Connection, claim_id: str, claim: Mapping[str, Any], imported_at: str
) -> None:
    payload = {
        "primary_domain": "TRADING_INVESTMENT",
        "secondary_domains": [],
        "subcategory": claim["claim_type"],
        "trading_relevance": "TRADING_RELEVANT",
        "trading_path_approved": True,
        "rationale": "Von ENTRY ausdrücklich als tradingrelevanter Claim freigegeben.",
    }
    connection.execute(
        """INSERT OR IGNORE INTO claim_domain_assessments (
               id, claim_id, primary_domain, secondary_domains_json, subcategory,
               trading_relevance, trading_path_approved, rationale,
               classification_fingerprint, classified_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _id(),
            claim_id,
            payload["primary_domain"],
            "[]",
            payload["subcategory"],
            payload["trading_relevance"],
            1,
            payload["rationale"],
            _fingerprint(payload),
            imported_at,
        ),
    )


def _insert_verification(
    connection: sqlite3.Connection, claim_id: str, claim: Mapping[str, Any], imported_at: str
) -> str:
    references: list[dict[str, Any]] = []
    for reference_type, items in (
        ("VERIFYING", claim["evidence"]),
        ("COUNTER_EVIDENCE", claim["counter_evidence"]),
    ):
        for raw in items:
            item = {"reference_type": reference_type, **raw}
            item["reference_fingerprint"] = _fingerprint(item)
            references.append(item)
    references.sort(key=lambda item: item["reference_fingerprint"])
    payload = {
        "verification_state": claim["verification_status"],
        "evidence_strength": claim["evidence_strength"],
        "confidence": claim["confidence"],
        "limitations": "\n".join(claim["limitations"]),
        "jurisdiction": None,
        "valid_from": None,
        "valid_until": None,
        "valid_as_of": claim["valid_as_of"],
        "update_required": False,
        "rationale": claim["rationale"],
        "references": references,
    }
    assessment_fingerprint = _fingerprint(payload)
    assessment_id = _id()
    connection.execute(
        """INSERT OR IGNORE INTO claim_verification_assessments (
               id, claim_id, verification_state, evidence_strength, confidence,
               limitations, jurisdiction, valid_from, valid_until, valid_as_of,
               update_required, rationale, assessment_fingerprint, assessed_at
           ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, 0, ?, ?, ?)""",
        (
            assessment_id,
            claim_id,
            claim["verification_status"],
            claim["evidence_strength"],
            claim["confidence"],
            payload["limitations"],
            claim["valid_as_of"],
            claim["rationale"],
            assessment_fingerprint,
            imported_at,
        ),
    )
    row = connection.execute(
        """SELECT id FROM claim_verification_assessments
           WHERE claim_id = ? AND assessment_fingerprint = ?""",
        (claim_id, assessment_fingerprint),
    ).fetchone()
    if row is None:  # pragma: no cover - transaction invariant
        raise RuntimeError("Verifikationsbewertung konnte nicht gespeichert werden.")
    assessment_id = str(row["id"])
    for item in references:
        connection.execute(
            """INSERT OR IGNORE INTO claim_verification_references (
                   id, assessment_id, reference_type, title, url, publisher,
                   published_date, notes, reference_fingerprint
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _id(),
                assessment_id,
                item["reference_type"],
                item["title"],
                item["url"],
                item["publisher"],
                item["published_date"],
                item["notes"],
                item["reference_fingerprint"],
            ),
        )
    return assessment_id


def _normalize_tag(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(text.split())


def _create_hypothesis(
    connection: sqlite3.Connection,
    source_id: str,
    claim_id: str,
    claim: Mapping[str, Any],
    imported_at: str,
) -> str | None:
    suggestion = claim.get("structured_hypothesis")
    if not isinstance(suggestion, Mapping):
        return None
    hypothesis_id = _id()
    normalized = normalize_claim(suggestion["claim"])
    risks = str(suggestion["risks_limitations"]).strip()
    connection.execute(
        """INSERT INTO hypotheses (
               id, title, area, category, claim, normalized_claim, claim_fingerprint,
               mechanism, external_evidence, rating, current_status, risks_limitations,
               strategy, asset_class, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'HYPOTHESIS', ?, ?, ?, ?, ?)""",
        (
            hypothesis_id,
            str(suggestion["title"]).strip(),
            suggestion["area"],
            str(suggestion["category"]).strip(),
            str(suggestion["claim"]).strip(),
            normalized,
            hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            str(suggestion["mechanism"]).strip(),
            suggestion["external_evidence"],
            suggestion["rating"],
            risks,
            str(suggestion.get("strategy") or "").strip() or None,
            str(suggestion.get("asset_class") or "").strip() or None,
            imported_at,
            imported_at,
        ),
    )
    reason = "Aus ENTRY-Handoff als ungetestete Research-Hypothese vorgemerkt."
    connection.execute(
        """INSERT INTO hypothesis_status_history (
               hypothesis_id, from_status, to_status, changed_at, reason
           ) VALUES (?, NULL, 'HYPOTHESIS', ?, ?)""",
        (hypothesis_id, imported_at, reason),
    )
    stance = {
        "SUPPORTED": "supports",
        "PARTIALLY_SUPPORTED": "mixed",
        "CONFLICTING_EVIDENCE": "mixed",
        "REFUTED": "contradicts",
    }.get(claim["verification_status"], "context")
    connection.execute(
        """INSERT INTO hypothesis_sources (
               id, hypothesis_id, source_id, stance, note, linked_at
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        (_id(), hypothesis_id, source_id, stance, reason, imported_at),
    )
    connection.execute(
        """INSERT INTO hypothesis_evidence_assessments (
               id, hypothesis_id, source_id, strength, confidence, rationale, assessed_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            _id(),
            hypothesis_id,
            source_id,
            suggestion["external_evidence"],
            claim["confidence"],
            claim["rationale"],
            imported_at,
        ),
    )
    connection.execute(
        """INSERT INTO source_claim_resolutions (
               id, claim_id, resolution, hypothesis_id, new_evidence_basis, rationale, resolved_at
           ) VALUES (?, ?, 'CREATED_HYPOTHESIS', ?, NULL, ?, ?)""",
        (_id(), claim_id, hypothesis_id, reason, imported_at),
    )
    connection.execute(
        """INSERT INTO evidence_ledger (
               hypothesis_id, event_type, event_at, summary, source_id, to_status, metadata_json
           ) VALUES (?, 'hypothesis_created', ?, ?, ?, 'HYPOTHESIS', ?)""",
        (
            hypothesis_id,
            imported_at,
            reason,
            source_id,
            _canonical_json(
                {
                    "origin_system": "ENTRY",
                    "origin_claim_id": claim["origin_claim_id"],
                    "research_only": True,
                    "automatic_strategy_integration": False,
                    "empirical_test_status": "NOT_TESTED",
                }
            ),
        ),
    )
    return hypothesis_id


def _create_draft_experiment(
    connection: sqlite3.Connection,
    hypothesis_id: str | None,
    claim: Mapping[str, Any],
    imported_at: str,
) -> str | None:
    suggestion = claim.get("structured_test")
    if not isinstance(suggestion, Mapping) or hypothesis_id is None:
        return None
    experiment_id = _id()
    period_start = _iso_date(suggestion.get("period_start"), "suggested_test.period_start")
    period_end = _iso_date(suggestion.get("period_end"), "suggested_test.period_end")
    connection.execute(
        """INSERT INTO experiments (
               id, hypothesis_id, title, test_definition, data_universe,
               period_start, period_end, point_in_time_rules, baseline,
               parameters_json, current_status, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)""",
        (
            experiment_id,
            hypothesis_id,
            str(suggestion["title"]).strip(),
            str(suggestion["test_definition"]).strip(),
            str(suggestion["data_universe"]).strip(),
            period_start,
            period_end,
            str(suggestion["point_in_time_rules"]).strip(),
            str(suggestion["baseline"]).strip(),
            _canonical_json(dict(suggestion.get("parameters", {}))),
            imported_at,
            imported_at,
        ),
    )
    for feature in sorted(
        {_required_text(item, "suggested_test.features") for item in suggestion.get("features", [])},
        key=str.casefold,
    ):
        connection.execute(
            "INSERT OR IGNORE INTO experiment_features (experiment_id, feature) VALUES (?, ?)",
            (experiment_id, feature),
        )
    connection.execute(
        """INSERT INTO experiment_status_history (
               experiment_id, from_status, to_status, changed_at, reason
           ) VALUES (?, NULL, 'DRAFT', ?, ?)""",
        (experiment_id, imported_at, "ENTRY-Testidee nur vorgemerkt; kein Test gestartet."),
    )
    connection.execute(
        """INSERT INTO evidence_ledger (
               hypothesis_id, event_type, event_at, summary, experiment_id, metadata_json
           ) VALUES (?, 'experiment_created', ?, ?, ?, ?)""",
        (
            hypothesis_id,
            imported_at,
            "ENTRY-Testidee als DRAFT vorgemerkt; kein Backtest gestartet.",
            experiment_id,
            _canonical_json(
                {
                    "origin_system": "ENTRY",
                    "research_only": True,
                    "empirical_test_status": "NOT_TESTED",
                }
            ),
        ),
    )
    return experiment_id


def _apply_import(connection: sqlite3.Connection, package: dict[str, Any]) -> dict[str, Any]:
    imported_at = _now()
    previous_handoff = _latest_handoff(connection, package["handoff_id"])
    if previous_handoff is not None:
        if str(previous_handoff["origin_source_id"]) != package["entry_source_id"]:
            conflict_id = _record_conflict(
                connection,
                package,
                origin_claim_id=None,
                existing_import_id=str(previous_handoff["id"]),
                conflict_type="HANDOFF_SOURCE_CHANGED",
                reason="Die Handoff-ID ist bereits einer anderen ENTRY-Source-ID zugeordnet.",
                details={
                    "stored_origin_source_id": previous_handoff["origin_source_id"],
                    "incoming_origin_source_id": package["entry_source_id"],
                },
                detected_at=imported_at,
            )
            return {
                "status": "CONFLICT",
                "reason": "Handoff-ID und ENTRY-Source-ID kollidieren.",
                "handoff_id": package["handoff_id"],
                "conflict_ids": [conflict_id],
                "source_id": None,
                "claim_ids": [],
            }
        if str(previous_handoff["handoff_fingerprint"]) == package["handoff_fingerprint"]:
            rows = connection.execute(
                "SELECT claim_id FROM entry_claim_imports WHERE handoff_import_id = ? ORDER BY origin_claim_id",
                (previous_handoff["id"],),
            ).fetchall()
            return {
                "status": "NO_CHANGE",
                "reason": "Dieses Handoff-Paket wurde unverändert bereits importiert.",
                "handoff_id": package["handoff_id"],
                "handoff_import_id": str(previous_handoff["id"]),
                "source_id": str(previous_handoff["source_id"]),
                "claim_ids": [str(row["claim_id"]) for row in rows],
                "conflict_ids": [],
            }

    conflicts: list[str] = []
    for claim in package["claims"]:
        prior = _latest_claim_import(
            connection, package["entry_source_id"], claim["origin_claim_id"]
        )
        incoming_claim_fingerprint = _fingerprint(claim)
        if prior is None or str(prior["claim_payload_fingerprint"]) == incoming_claim_fingerprint:
            continue
        actual = _managed_state(
            connection,
            str(prior["claim_id"]),
            str(prior["hypothesis_id"]) if prior["hypothesis_id"] else None,
            str(prior["experiment_id"]) if prior["experiment_id"] else None,
        )
        if actual != str(prior["managed_state_fingerprint"]):
            conflicts.append(
                _record_conflict(
                    connection,
                    package,
                    origin_claim_id=claim["origin_claim_id"],
                    existing_import_id=str(prior["handoff_import_id"]),
                    conflict_type="LOCAL_MANAGED_STATE_CHANGED",
                    reason="Lokale Änderungen überschneiden sich mit einer geänderten ENTRY-Revision.",
                    details={
                        "stored_managed_state_fingerprint": prior["managed_state_fingerprint"],
                        "current_managed_state_fingerprint": actual,
                        "previous_claim_payload_fingerprint": prior["claim_payload_fingerprint"],
                        "incoming_claim_payload_fingerprint": incoming_claim_fingerprint,
                    },
                    detected_at=imported_at,
                )
            )
    if conflicts:
        return {
            "status": "CONFLICT",
            "reason": "Mindestens ein lokal geänderter Research-Eintrag würde konkurrierend aktualisiert.",
            "handoff_id": package["handoff_id"],
            "source_id": str(previous_handoff["source_id"]) if previous_handoff else None,
            "claim_ids": [],
            "conflict_ids": conflicts,
        }

    try:
        source_id, source_created = _find_or_create_source(connection, package, imported_at)
    except HandoffConflict as exc:
        conflict_id = _record_conflict(
            connection,
            package,
            origin_claim_id=None,
            existing_import_id=str(previous_handoff["id"]) if previous_handoff else None,
            conflict_type="SOURCE_IDENTITY_COLLISION",
            reason=str(exc),
            details={},
            detected_at=imported_at,
        )
        return {
            "status": "CONFLICT",
            "reason": str(exc),
            "handoff_id": package["handoff_id"],
            "source_id": None,
            "claim_ids": [],
            "conflict_ids": [conflict_id],
        }

    handoff_import_id = _id()
    connection.execute(
        """INSERT INTO entry_handoff_imports (
               id, handoff_id, origin_system, origin_source_id, source_id, source_hash,
               handoff_fingerprint, payload_json, imported_at
           ) VALUES (?, ?, 'ENTRY', ?, ?, ?, ?, ?, ?)""",
        (
            handoff_import_id,
            package["handoff_id"],
            package["entry_source_id"],
            source_id,
            package["source_hash"],
            package["handoff_fingerprint"],
            _canonical_json(package["origin_payload"]),
            imported_at,
        ),
    )
    claim_ids: list[str] = []
    hypothesis_ids: list[str] = []
    experiment_ids: list[str] = []
    assessment_ids: list[str] = []
    for claim in package["claims"]:
        prior = _latest_claim_import(
            connection, package["entry_source_id"], claim["origin_claim_id"]
        )
        normalized = normalize_claim(claim["claim_text"])
        claim_text_fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        claim_id: str | None = None
        if prior is not None:
            prior_claim = connection.execute(
                "SELECT claim_fingerprint FROM source_claims WHERE id = ?", (prior["claim_id"],)
            ).fetchone()
            if prior_claim is not None and prior_claim["claim_fingerprint"] == claim_text_fingerprint:
                claim_id = str(prior["claim_id"])
        if claim_id is None:
            existing_claim = connection.execute(
                """SELECT id FROM source_claims
                   WHERE source_id = ? AND claim_fingerprint = ?""",
                (source_id, claim_text_fingerprint),
            ).fetchone()
            if existing_claim is not None:
                claim_id = str(existing_claim["id"])
            else:
                claim_id = _id()
                notes = _canonical_json(
                    {
                        "origin_system": "ENTRY",
                        "origin_claim_id": claim["origin_claim_id"],
                        "claim_type": claim["claim_type"],
                        "video_timestamps": claim["video_timestamps"],
                        "risks": claim["risks"],
                        "suggested_hypothesis": claim["suggested_hypothesis"],
                        "suggested_test": claim["suggested_test"],
                    }
                )
                connection.execute(
                    """INSERT INTO source_claims (
                           id, source_id, claim_text, normalized_claim, claim_fingerprint,
                           original_market_scope, extraction_notes, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        claim_id,
                        source_id,
                        claim["claim_text"],
                        normalized,
                        claim_text_fingerprint,
                        claim["market_scope"],
                        notes,
                        imported_at,
                    ),
                )
                if prior is not None and str(prior["claim_id"]) != claim_id:
                    connection.execute(
                        """INSERT OR IGNORE INTO knowledge_claim_relations (
                               id, claim_id, related_claim_id, relation_type, rationale, created_at
                           ) VALUES (?, ?, ?, 'SUPERSEDES', ?, ?)""",
                        (
                            _id(),
                            claim_id,
                            str(prior["claim_id"]),
                            "Geänderte Claim-Fassung aus derselben ENTRY-Herkunft.",
                            imported_at,
                        ),
                    )
        _insert_domain_assessment(connection, claim_id, claim, imported_at)
        assessment_ids.append(_insert_verification(connection, claim_id, claim, imported_at))
        for tag in claim["tags"]:
            connection.execute(
                """INSERT OR IGNORE INTO source_claim_tags (
                       claim_id, tag, normalized_tag, origin_system, created_at
                   ) VALUES (?, ?, ?, 'ENTRY', ?)""",
                (claim_id, tag, _normalize_tag(tag), imported_at),
            )

        claim_payload_fingerprint = _fingerprint(claim)
        reuse_suggestion = False
        hypothesis_id: str | None = None
        experiment_id: str | None = None
        if prior is not None:
            previous_payload = json.loads(str(prior["payload_json"]))
            same_hypothesis = previous_payload.get("structured_hypothesis") == claim.get(
                "structured_hypothesis"
            )
            same_test = previous_payload.get("structured_test") == claim.get("structured_test")
            if same_hypothesis and same_test:
                hypothesis_id = str(prior["hypothesis_id"]) if prior["hypothesis_id"] else None
                experiment_id = str(prior["experiment_id"]) if prior["experiment_id"] else None
                reuse_suggestion = True
        if not reuse_suggestion:
            hypothesis_id = _create_hypothesis(
                connection, source_id, claim_id, claim, imported_at
            )
            experiment_id = _create_draft_experiment(
                connection, hypothesis_id, claim, imported_at
            )
        managed = _managed_state(connection, claim_id, hypothesis_id, experiment_id)
        connection.execute(
            """INSERT INTO entry_claim_imports (
                   id, handoff_import_id, claim_id, hypothesis_id, experiment_id,
                   origin_system, origin_source_id, origin_claim_id, handoff_id,
                   handoff_fingerprint, source_hash, claim_payload_fingerprint,
                   managed_state_fingerprint, source_verification_status,
                   empirical_test_status, research_status, payload_json, imported_at
               ) VALUES (?, ?, ?, ?, ?, 'ENTRY', ?, ?, ?, ?, ?, ?, ?, ?,
                         'NOT_TESTED', 'CANDIDATE', ?, ?)""",
            (
                _id(),
                handoff_import_id,
                claim_id,
                hypothesis_id,
                experiment_id,
                package["entry_source_id"],
                claim["origin_claim_id"],
                package["handoff_id"],
                package["handoff_fingerprint"],
                package["source_hash"],
                claim_payload_fingerprint,
                managed,
                claim["entry_verification_status"],
                _canonical_json(claim),
                imported_at,
            ),
        )
        claim_ids.append(claim_id)
        if hypothesis_id:
            hypothesis_ids.append(hypothesis_id)
        if experiment_id:
            experiment_ids.append(experiment_id)

    return {
        "status": "UPDATED" if previous_handoff is not None else "IMPORTED",
        "reason": (
            "Geänderte ENTRY-Handoff-Revision append-only übernommen."
            if previous_handoff is not None
            else "ENTRY-Handoff transaktional in die bestehende Research-Struktur importiert."
        ),
        "handoff_id": package["handoff_id"],
        "handoff_import_id": handoff_import_id,
        "source_id": source_id,
        "source_created": source_created,
        "claim_ids": claim_ids,
        "hypothesis_ids": hypothesis_ids,
        "experiment_ids": experiment_ids,
        "verification_assessment_ids": assessment_ids,
        "ignored_claim_ids": package["ignored_claim_ids"],
        "conflict_ids": [],
    }


def _run_on_database(package: dict[str, Any], database_path: Path) -> dict[str, Any]:
    initialize_database(database_path)
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    try:
        connection.execute("BEGIN IMMEDIATE")
        result = _apply_import(connection, package)
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise sqlite3.IntegrityError("Fremdschlüsselprüfung nach Import fehlgeschlagen.")
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def import_handoff(
    package: object,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized = validate_handoff(package)
    target = Path(database_path).resolve()
    if not dry_run:
        result = _run_on_database(normalized, target)
        result["dry_run"] = False
        result["database_path"] = str(target)
        return result

    with tempfile.TemporaryDirectory(prefix="entry-handoff-dry-run-") as directory:
        simulated = Path(directory) / "research_knowledge.sqlite3"
        if target.exists():
            source = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
            destination = sqlite3.connect(simulated)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
        result = _run_on_database(normalized, simulated)
    result["dry_run"] = True
    result["database_path"] = str(target)
    result["reason"] = f"Dry-Run erfolgreich: {result['reason']} Es wurde nichts gespeichert."
    return result


def failure_response(status: str, reason: str, **details: object) -> dict[str, Any]:
    if status not in IMPORT_STATUSES:
        raise ValueError(f"Unbekannter Importstatus: {status}")
    return {"status": status, "reason": reason, **details}
