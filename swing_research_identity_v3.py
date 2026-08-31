from __future__ import annotations

"""Verified issuer/listing identities for future research only.

This layer is deliberately separate from the immutable Broad-v1 identity code.
It accepts issuer links only when an explicit, auditable anchor is present.
Names remain search hints and can never create a verified dependency by
themselves.
"""

import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from swing_research_identity_v2 import ResearchIdentityError, validate_listing_scoped_bundle


RESEARCH_IDENTITY_V3_VERSION = "swing-research-identity-2026.08.29-v3"
RESEARCH_DEPENDENCY_V3_VERSION = "swing-research-dependency-2026.08.29-v3"
IDENTITY_REGISTRY_SCHEMA_VERSION = 2
DEFAULT_IDENTITY_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "runtime" / "research_identity_registry.sqlite3"
)

VERIFIED_ISSUER_ANCHORS = {
    "LEI",
    "SEC_CIK",
    "FIGI_ISSUER_REFERENCE",
    "ISIN_ISSUER_REFERENCE",
    "EXCHANGE_ISSUER_REFERENCE",
    "DOCUMENTED_ADR_RELATION",
}
MAPPING_STATUSES = {
    "VERIFIED",
    "CANDIDATE_UNVERIFIED",
    "UNRESOLVED",
    "CONFLICT",
}
LISTING_ROLES = {"PRIMARY", "SECONDARY", "UNKNOWN"}
QUALITY_LEVELS = {"HIGH", "MEDIUM", "UNKNOWN"}


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


def _text(value: object) -> str | None:
    result = str(value or "").strip()
    return result or None


def _upper(value: object) -> str | None:
    result = _text(value)
    return result.upper() if result else None


def _utc(value: object, field: str) -> str:
    text = _text(value)
    if text is None:
        raise ResearchIdentityError(f"{field} fehlt.")
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchIdentityError(f"{field} ist kein ISO-Zeitpunkt.") from exc
    if stamp.tzinfo is None:
        raise ResearchIdentityError(f"{field} benötigt eine Zeitzone.")
    return stamp.astimezone(timezone.utc).isoformat()


def _day(value: object, field: str, *, required: bool = False) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise ResearchIdentityError(f"{field} fehlt.")
        return None
    candidate = text[:10]
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ResearchIdentityError(f"{field} ist kein ISO-Datum.") from exc
    return candidate


def _stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}-{_fingerprint([RESEARCH_IDENTITY_V3_VERSION, *parts])[:28]}"


def _normalized_name(value: object) -> str | None:
    text = str(value or "").casefold().replace("&", " and ")
    tokens = re.findall(r"[a-z0-9]+", text)
    suffixes = {
        "ag",
        "co",
        "company",
        "corp",
        "corporation",
        "inc",
        "limited",
        "ltd",
        "nv",
        "plc",
        "sa",
        "se",
    }
    while tokens and tokens[-1] in suffixes:
        tokens.pop()
    return " ".join(tokens) or None


def _instrument_type(record: Mapping[str, object]) -> str:
    value = _upper(
        record.get("instrument_type")
        or record.get("security_type")
        or record.get("quote_type")
    ) or "UNKNOWN"
    aliases = {"EQUITY": "COMMON_STOCK", "STOCK": "COMMON_STOCK"}
    return aliases.get(value, value)


def _asset_class(record: Mapping[str, object]) -> str:
    value = _upper(record.get("asset_class") or record.get("asset_type")) or "UNKNOWN"
    aliases = {"AKTIE": "EQUITIES", "EQUITY": "EQUITIES", "STOCK": "EQUITIES"}
    return aliases.get(value, value)


def normalize_identity_mapping(record: Mapping[str, object]) -> dict[str, object]:
    """Validate one versioned registry record without guessing an issuer link."""

    ticker = _upper(record.get("ticker") or record.get("symbol"))
    if ticker is None:
        raise ResearchIdentityError("Ein Mapping benötigt einen Ticker.")
    exchange = _text(record.get("exchange"))
    mic = _upper(record.get("mic"))
    currency = _upper(record.get("currency"))
    mapping_version = _text(record.get("mapping_version"))
    source = _text(record.get("source"))
    source_reference = _text(record.get("source_reference"))
    if not mapping_version or not source or not source_reference:
        raise ResearchIdentityError(
            "Mapping-Version, Quelle und belastbare Quellenreferenz sind Pflicht."
        )

    status = _upper(record.get("mapping_status")) or "UNRESOLVED"
    if status not in MAPPING_STATUSES:
        raise ResearchIdentityError(
            "mapping_status muss VERIFIED, CANDIDATE_UNVERIFIED, "
            "UNRESOLVED oder CONFLICT sein."
        )
    anchor_type = _upper(record.get("issuer_anchor_type"))
    anchor_value = _text(record.get("issuer_anchor_value"))
    explicit_issuer = _text(record.get("issuer_id") or record.get("company_id"))
    if status == "VERIFIED":
        if anchor_type not in VERIFIED_ISSUER_ANCHORS or not anchor_value:
            raise ResearchIdentityError(
                "VERIFIED benötigt einen zulässigen Issuer-Anker und dessen Wert."
            )
        issuer_id = explicit_issuer or _stable_id("issuer", anchor_type, anchor_value)
    else:
        if explicit_issuer:
            raise ResearchIdentityError(
                f"{status} darf keine sichere issuer_id behaupten."
            )
        issuer_id = None
        anchor_type = None
        anchor_value = None

    listing_role = _upper(
        record.get("primary_listing_status") or record.get("listing_role")
    ) or "UNKNOWN"
    if listing_role not in LISTING_ROLES:
        raise ResearchIdentityError(
            "primary_listing_status muss PRIMARY, SECONDARY oder UNKNOWN sein."
        )
    quality = _upper(record.get("quality")) or "UNKNOWN"
    if quality not in QUALITY_LEVELS:
        raise ResearchIdentityError("quality muss HIGH, MEDIUM oder UNKNOWN sein.")
    confidence = record.get("confidence")
    if confidence is None:
        confidence_number = 0 if status == "UNRESOLVED" else None
    else:
        try:
            confidence_number = int(confidence)
        except (TypeError, ValueError) as exc:
            raise ResearchIdentityError("confidence muss eine Ganzzahl sein.") from exc
        if confidence_number < 0 or confidence_number > 100:
            raise ResearchIdentityError("confidence muss zwischen 0 und 100 liegen.")
    if status == "VERIFIED" and confidence_number is None:
        raise ResearchIdentityError("VERIFIED benötigt confidence.")

    isin = _upper(record.get("isin"))
    figi = _upper(record.get("figi"))
    composite_figi = _upper(record.get("composite_figi"))
    share_class_figi = _upper(record.get("share_class_figi"))
    lei = _upper(record.get("lei"))
    sec_cik = _text(record.get("sec_cik"))
    share_class = _text(record.get("share_class"))
    instrument_type = _instrument_type(record)
    is_dr = bool(
        record.get("is_depositary_receipt")
        or instrument_type in {"ADR", "ADS", "GDR", "DEPOSITARY_RECEIPT"}
    )

    listing_anchor = figi or (
        f"ISIN:{isin}|MIC:{mic}" if isin and mic else None
    ) or _text(record.get("listing_source_id"))
    if listing_anchor:
        listing_id = _text(record.get("listing_id")) or _stable_id(
            "listing", listing_anchor
        )
        listing_identity_quality = "ANCHORED"
    else:
        listing_id = _text(record.get("listing_id")) or _stable_id(
            "listing-unresolved",
            ticker,
            mic or exchange or "UNKNOWN",
            currency or "UNKNOWN",
            instrument_type,
        )
        listing_identity_quality = "UNRESOLVED_ANCHOR"

    asset_anchor = share_class_figi or (
        f"{issuer_id}|{share_class or 'DEFAULT'}" if issuer_id else None
    )
    asset_id = _text(record.get("asset_id")) or _stable_id(
        "asset", asset_anchor or listing_id
    )
    valid_from = _day(record.get("valid_from"), "valid_from")
    valid_to = _day(record.get("valid_to"), "valid_to")
    if valid_from and valid_to and valid_from > valid_to:
        raise ResearchIdentityError("valid_from darf nicht nach valid_to liegen.")

    payload: dict[str, object] = {
        "identity_version": RESEARCH_IDENTITY_V3_VERSION,
        "dependency_version": RESEARCH_DEPENDENCY_V3_VERSION,
        "mapping_version": mapping_version,
        "mapping_status": status,
        "mapping_source": source,
        "source_reference": source_reference,
        "source_identifier": _text(record.get("source_identifier")) or anchor_value,
        "evidence": list(record.get("evidence") or []),
        "confidence": confidence_number,
        "quality": quality,
        "asset_id": asset_id,
        "listing_id": listing_id,
        "issuer_id": issuer_id,
        "company_id": issuer_id,
        "issuer_dependency_cluster": f"issuer:{issuer_id}" if issuer_id else "UNKNOWN",
        "listing_dependency_cluster": f"listing:{listing_id}",
        "dependency_cluster_id": f"issuer:{issuer_id}" if issuer_id else "UNKNOWN",
        "dependency_status": "KNOWN" if issuer_id else "UNKNOWN",
        "ticker": ticker,
        "ticker_aliases": sorted(
            {_upper(item) for item in record.get("ticker_aliases", []) if _upper(item)}
        ),
        "name": _text(record.get("name") or record.get("company_name")),
        "issuer_candidate_key": _normalized_name(
            record.get("name") or record.get("company_name")
        ),
        "exchange": exchange,
        "mic": mic,
        "currency": currency,
        "instrument_type": instrument_type,
        "asset_class": _asset_class(record),
        "isin": isin,
        "figi": figi,
        "composite_figi": composite_figi,
        "share_class_figi": share_class_figi,
        "lei": lei,
        "sec_cik": sec_cik,
        "primary_listing_status": listing_role,
        "listing_role": listing_role,
        "is_primary_listing": (
            True if listing_role == "PRIMARY" else False if listing_role == "SECONDARY" else None
        ),
        "is_depositary_receipt": is_dr,
        "depositary_receipt_type": instrument_type if is_dr else None,
        "depositary_ratio": record.get("depositary_ratio"),
        "share_class": share_class,
        "exchange_timezone": _text(record.get("exchange_timezone")),
        "issuer_anchor_type": anchor_type,
        "issuer_anchor_value": anchor_value,
        "listing_identity_quality": listing_identity_quality,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "first_seen_at": _utc(record.get("first_seen_at"), "first_seen_at"),
        "imported_at": _utc(record.get("imported_at"), "imported_at"),
        "research_dependency_only": True,
        "pit_trading_feature": False,
        "unknown_is_independent_evidence": False,
        "metadata": dict(record.get("metadata") or {}),
    }
    payload["mapping_fingerprint"] = _fingerprint(payload)
    return payload


def build_identity_registry(
    records: Iterable[Mapping[str, object]],
    *,
    mapping_version: str,
    created_at: object,
) -> dict[str, object]:
    normalized = [normalize_identity_mapping(record) for record in records]
    if any(item["mapping_version"] != mapping_version for item in normalized):
        raise ResearchIdentityError("Alle Einträge müssen dieselbe Mapping-Version besitzen.")
    normalized.sort(
        key=lambda item: (
            str(item["ticker"]),
            str(item.get("mic") or ""),
            str(item.get("valid_from") or ""),
            str(item["mapping_fingerprint"]),
        )
    )
    fingerprints = [str(item["mapping_fingerprint"]) for item in normalized]
    if len(fingerprints) != len(set(fingerprints)):
        raise ResearchIdentityError("Doppelte Mapping-Einträge sind nicht zulässig.")
    payload: dict[str, object] = {
        "schema_version": IDENTITY_REGISTRY_SCHEMA_VERSION,
        "identity_version": RESEARCH_IDENTITY_V3_VERSION,
        "dependency_version": RESEARCH_DEPENDENCY_V3_VERSION,
        "mapping_version": mapping_version,
        "created_at": _utc(created_at, "created_at"),
        "records": normalized,
        "record_n": len(normalized),
        "verified_issuer_n": sum(item["mapping_status"] == "VERIFIED" for item in normalized),
        "candidate_unverified_n": sum(
            item["mapping_status"] == "CANDIDATE_UNVERIFIED" for item in normalized
        ),
        "unresolved_n": sum(item["mapping_status"] == "UNRESOLVED" for item in normalized),
        "conflict_n": sum(item["mapping_status"] == "CONFLICT" for item in normalized),
        "name_only_links_created": 0,
        "automatic_fuzzy_links_created": 0,
    }
    payload["registry_fingerprint"] = _fingerprint(payload)
    return payload


def _active_on(record: Mapping[str, object], as_of: str | None) -> bool:
    if as_of is None:
        return record.get("valid_to") is None
    day = as_of[:10]
    return bool(
        (not record.get("valid_from") or str(record["valid_from"]) <= day)
        and (not record.get("valid_to") or day <= str(record["valid_to"]))
    )


def resolve_research_identity_v3(
    asset: Mapping[str, object],
    *,
    registry: Mapping[str, object] | None = None,
    as_of: object | None = None,
) -> dict[str, object]:
    ticker = _upper(asset.get("ticker") or asset.get("symbol"))
    if ticker is None:
        raise ResearchIdentityError("Eine Research-Identität benötigt einen Ticker.")
    mic = _upper(asset.get("mic"))
    exchange = _text(asset.get("exchange"))
    as_of_day = _day(as_of, "as_of") if as_of is not None else None
    records = list((registry or {}).get("records") or [])
    candidates = [
        dict(item)
        for item in records
        if (
            ticker == _upper(item.get("ticker"))
            or ticker in set(item.get("ticker_aliases") or [])
        )
        and (mic is None or not item.get("mic") or mic == _upper(item.get("mic")))
        and (exchange is None or not item.get("exchange") or exchange == item.get("exchange"))
        and _active_on(item, as_of_day)
    ]
    if len(candidates) > 1:
        raise ResearchIdentityError(
            "Mehrere Registry-Einträge passen; MIC/Börse oder as_of müssen eindeutiger sein."
        )
    if candidates:
        identity = candidates[0]
        for field, normalizer in (("currency", _upper), ("mic", _upper)):
            supplied = normalizer(asset.get(field))
            stored = normalizer(identity.get(field))
            if supplied and stored and supplied != stored:
                raise ResearchIdentityError(
                    f"Asset-{field} widerspricht dem verifizierten Listing-Mapping."
                )
        return identity

    unresolved = {
        "ticker": ticker,
        "ticker_aliases": [],
        "name": _text(asset.get("name") or asset.get("company_name")),
        "exchange": exchange,
        "mic": mic,
        "currency": _upper(asset.get("currency")),
        "instrument_type": _instrument_type(asset),
        "asset_class": _asset_class(asset),
        "primary_listing_status": _upper(asset.get("primary_listing_status")) or "UNKNOWN",
        "share_class": _text(asset.get("share_class")),
        "exchange_timezone": _text(asset.get("exchange_timezone")),
        "mapping_version": str((registry or {}).get("mapping_version") or "UNRESOLVED"),
        "mapping_status": "UNRESOLVED",
        "source": "local_unresolved_identity",
        "source_reference": f"unresolved:{ticker}",
        "quality": "UNKNOWN",
        "confidence": 0,
        "first_seen_at": _utc(
            asset.get("first_seen_at") or datetime.now(timezone.utc).isoformat(),
            "first_seen_at",
        ),
        "imported_at": _utc(
            asset.get("imported_at") or datetime.now(timezone.utc).isoformat(),
            "imported_at",
        ),
    }
    return normalize_identity_mapping(unresolved)


def dependency_evidence_report_v3(
    cases: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    issuer_clusters: set[str] = set()
    listing_clusters: set[str] = set()
    unknown = 0
    conflicts = 0
    verified_observations = 0
    issuer_case_counts: Counter[str] = Counter()
    listing_case_counts: Counter[str] = Counter()
    unresolved_listing_keys: set[str] = set()
    for index, case in enumerate(cases):
        listing_id = _text(case.get("listing_id"))
        issuer_id = _text(case.get("issuer_id"))
        mapping_status = str(case.get("mapping_status") or "UNRESOLVED").upper()
        if listing_id:
            listing_clusters.add(listing_id)
            listing_case_counts[listing_id] += 1
        if mapping_status != "VERIFIED":
            unresolved_listing_keys.add(
                listing_id or _text(case.get("ticker")) or f"row:{index}"
            )
        dependency_known = bool(
            issuer_id
            and mapping_status == "VERIFIED"
            and str(case.get("dependency_status") or "KNOWN").upper() == "KNOWN"
        )
        if dependency_known:
            issuer_clusters.add(issuer_id)
            issuer_case_counts[issuer_id] += 1
            verified_observations += 1
        else:
            unknown += 1
            conflicts += int(mapping_status == "CONFLICT")
    raw_n = len(cases)
    payload: dict[str, object] = {
        "version": RESEARCH_DEPENDENCY_V3_VERSION,
        "raw_n": raw_n,
        "raw_observations": raw_n,
        "raw_listings": len(listing_clusters),
        "issuer_cluster_n": len(issuer_clusters),
        "verified_issuer_clusters": len(issuer_clusters),
        "listing_cluster_n": len(listing_clusters),
        "unresolved_listings": len(unresolved_listing_keys),
        "dependency_unknown_n": unknown,
        "dependency_unknown": unknown,
        "conflict_observation_n": conflicts,
        "verified_dependency_observation_n": verified_observations,
        "verified_dependency_coverage_pct": (
            round(verified_observations / raw_n * 100, 6) if raw_n else 0.0
        ),
        "effective_n_known_issuers_only": len(issuer_clusters),
        "effective_independent_issuer_count": len(issuer_clusters),
        "same_issuer_excess_case_n": sum(max(value - 1, 0) for value in issuer_case_counts.values()),
        "same_listing_excess_case_n": sum(max(value - 1, 0) for value in listing_case_counts.values()),
        "unknown_counted_as_independent": False,
        "raw_n_claimed_independent": False,
        "effective_n_status": "COMPLETE" if unknown == 0 else "PARTIAL_UNKNOWN",
        "issuer_clusters": [
            {"issuer_id": key, "observation_n": issuer_case_counts[key]}
            for key in sorted(issuer_case_counts)
        ],
        "listing_clusters": [
            {"listing_id": key, "observation_n": listing_case_counts[key]}
            for key in sorted(listing_case_counts)
        ],
    }
    payload["report_fingerprint"] = _fingerprint(payload)
    return payload


def dependency_episode_report_v3(
    cases: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Count non-overlapping evidence episodes for verified issuers only.

    Rows without a verified issuer contribute zero to the issuer-adjusted
    effective N.  Separate observations for one issuer count again only when
    their outcome windows no longer overlap.
    """

    base = dependency_evidence_report_v3(cases)
    intervals: dict[str, list[tuple[str, str]]] = {}
    for case in cases:
        issuer_id = _text(case.get("issuer_id"))
        status = str(case.get("mapping_status") or "UNRESOLVED").upper()
        dependency_status = str(case.get("dependency_status") or "UNKNOWN").upper()
        if not issuer_id or status != "VERIFIED" or dependency_status != "KNOWN":
            continue
        start = _day(
            case.get("signal_day") or case.get("observation_day"),
            "signal_day",
        )
        end = _day(
            case.get("label_end_day") or case.get("outcome_end_day") or start,
            "label_end_day",
        )
        if start is None:
            # Registry-level coverage has no temporal observation window.  It
            # still represents one dependency cluster, never one row per case.
            start = end = "0001-01-01"
        if end is None:
            end = start
        if end < start:
            raise ResearchIdentityError("label_end_day darf nicht vor signal_day liegen.")
        intervals.setdefault(issuer_id, []).append((start, end))

    episode_n = 0
    issuer_episode_counts: dict[str, int] = {}
    for issuer_id, issuer_intervals in sorted(intervals.items()):
        count = 0
        current_end: str | None = None
        # Earliest-finish greedy selection is the exact maximum-cardinality
        # set of pairwise non-overlapping intervals.
        for start, end in sorted(issuer_intervals, key=lambda item: (item[1], item[0])):
            if current_end is None or start > current_end:
                count += 1
                current_end = end
        issuer_episode_counts[issuer_id] = count
        episode_n += count

    payload = {
        **base,
        "effective_independent_issuer_count": episode_n,
        "effective_n_known_issuers_only": episode_n,
        "effective_n_method": (
            "maximum_pairwise_non_overlapping_outcome_windows_per_verified_issuer"
        ),
        "issuer_episode_counts": issuer_episode_counts,
        "unknown_dependency_contribution_to_effective_n": 0,
        "effective_n_le_raw_n": episode_n <= len(cases),
    }
    payload.pop("report_fingerprint", None)
    payload["report_fingerprint"] = _fingerprint(payload)
    return payload


def validate_listing_scoped_bundle_v3(bundle: Mapping[str, object]) -> dict[str, object]:
    result = validate_listing_scoped_bundle(bundle)
    return {
        **result,
        "identity_version": RESEARCH_IDENTITY_V3_VERSION,
        "issuer_level_values_used_for_listing_technicals": False,
    }


def initialize_identity_registry_store(
    path: Path = DEFAULT_IDENTITY_REGISTRY_PATH,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS registry_versions (
                registry_fingerprint TEXT PRIMARY KEY,
                mapping_version TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                registry_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS identity_mappings (
                mapping_fingerprint TEXT PRIMARY KEY,
                registry_fingerprint TEXT NOT NULL,
                ticker TEXT NOT NULL,
                mic TEXT,
                listing_id TEXT NOT NULL,
                issuer_id TEXT,
                valid_from TEXT,
                valid_to TEXT,
                mapping_json TEXT NOT NULL,
                FOREIGN KEY (registry_fingerprint) REFERENCES registry_versions(registry_fingerprint)
            );
            CREATE TRIGGER IF NOT EXISTS registry_versions_no_update
            BEFORE UPDATE ON registry_versions BEGIN SELECT RAISE(ABORT, 'identity registry append-only'); END;
            CREATE TRIGGER IF NOT EXISTS registry_versions_no_delete
            BEFORE DELETE ON registry_versions BEGIN SELECT RAISE(ABORT, 'identity registry append-only'); END;
            CREATE TRIGGER IF NOT EXISTS identity_mappings_no_update
            BEFORE UPDATE ON identity_mappings BEGIN SELECT RAISE(ABORT, 'identity mappings append-only'); END;
            CREATE TRIGGER IF NOT EXISTS identity_mappings_no_delete
            BEFORE DELETE ON identity_mappings BEGIN SELECT RAISE(ABORT, 'identity mappings append-only'); END;
            """
        )


def append_identity_registry(
    registry: Mapping[str, object],
    *,
    path: Path = DEFAULT_IDENTITY_REGISTRY_PATH,
) -> int:
    initialize_identity_registry_store(path)
    payload = dict(registry)
    fingerprint = str(payload.get("registry_fingerprint") or "")
    comparable = {key: value for key, value in payload.items() if key != "registry_fingerprint"}
    if not fingerprint or _fingerprint(comparable) != fingerprint:
        raise ResearchIdentityError("Registry-Fingerprint ist ungültig.")
    inserted = 0
    with sqlite3.connect(path) as connection:
        current = connection.execute(
            "SELECT registry_fingerprint FROM registry_versions WHERE mapping_version=?",
            (payload["mapping_version"],),
        ).fetchone()
        if current is not None and str(current[0]) != fingerprint:
            raise ResearchIdentityError(
                "Dieselbe Mapping-Version besitzt bereits einen anderen Fingerprint."
            )
        cursor = connection.execute(
            "INSERT OR IGNORE INTO registry_versions VALUES (?, ?, ?, ?)",
            (
                fingerprint,
                payload["mapping_version"],
                payload["created_at"],
                _canonical_json(payload),
            ),
        )
        inserted += int(cursor.rowcount)
        for record in payload.get("records", []):
            connection.execute(
                "INSERT OR IGNORE INTO identity_mappings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["mapping_fingerprint"],
                    fingerprint,
                    record["ticker"],
                    record.get("mic"),
                    record["listing_id"],
                    record.get("issuer_id"),
                    record.get("valid_from"),
                    record.get("valid_to"),
                    _canonical_json(record),
                ),
            )
    return inserted


def load_identity_registry(
    mapping_version: str,
    *,
    path: Path = DEFAULT_IDENTITY_REGISTRY_PATH,
) -> dict[str, object]:
    initialize_identity_registry_store(path)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT registry_json FROM registry_versions WHERE mapping_version=?",
            (mapping_version,),
        ).fetchone()
    if row is None:
        raise KeyError(mapping_version)
    return json.loads(str(row[0]))
