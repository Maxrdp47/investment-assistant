from __future__ import annotations

"""Listing-safe identities for research epochs after immutable Broad-v1.

Broad-v1 deliberately keeps using ``swing_research_identity.py``.  This module
is a new contract so that improving issuer/listing semantics cannot rewrite the
historical Broad-v1 code fingerprint or its stored cases.
"""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from typing import Mapping, Sequence


RESEARCH_IDENTITY_V2_VERSION = "swing-research-identity-2026.08.28-v2"
RESEARCH_DEPENDENCY_V2_VERSION = "swing-research-dependency-2026.08.28-v2"

_UNKNOWN = {"", "unknown", "unbekannt", "none", "n/a", "null"}
_DR_PATTERN = re.compile(
    r"\b(?:adr|ads|gdr)s?\b|\b(?:american\s+)?(?:depositary|depository)\s+"
    r"(?:receipt|receipts|share|shares)\b",
    re.IGNORECASE,
)


class ResearchIdentityError(ValueError):
    """A future research identity or listing bundle is internally inconsistent."""


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
    text = str(value or "").strip()
    return text or None


def _upper(value: object) -> str | None:
    text = _text(value)
    return text.upper() if text else None


def _known(value: object) -> bool:
    return str(value or "").strip().casefold() not in _UNKNOWN


def _normalized_name(value: object) -> str | None:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("&", " and ")
    tokens = re.findall(r"[a-z0-9]+", text)
    legal_suffixes = {
        "ag", "co", "company", "corp", "corporation", "inc", "incorporated",
        "limited", "ltd", "nv", "plc", "sa", "se", "spa",
    }
    while tokens and tokens[-1] in legal_suffixes:
        tokens.pop()
    return " ".join(tokens) or None


def _stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}-{_fingerprint([RESEARCH_IDENTITY_V2_VERSION, *parts])[:24]}"


def _asset_class(asset: Mapping[str, object]) -> str:
    value = str(
        asset.get("asset_class")
        or asset.get("asset_type")
        or asset.get("quote_type")
        or "UNKNOWN"
    ).strip().upper()
    aliases = {
        "AKTIE": "EQUITIES",
        "EQUITY": "EQUITIES",
        "STOCK": "EQUITIES",
        "CRYPTOCURRENCY": "CRYPTO",
        "KRYPTO": "CRYPTO",
        "FOREX": "FX",
    }
    return aliases.get(value, value or "UNKNOWN")


def _instrument_type(asset: Mapping[str, object], *, depositary_receipt: bool) -> str:
    explicit = str(
        asset.get("instrument_type")
        or asset.get("security_type")
        or asset.get("quote_type")
        or ""
    ).strip().upper()
    if depositary_receipt:
        text = " ".join(str(asset.get(key) or "") for key in ("name", "instrument_type"))
        if re.search(r"\b(?:ads|american\s+depositary\s+share)s?\b", text, re.IGNORECASE):
            return "ADS"
        if re.search(r"\bgdrs?\b", text, re.IGNORECASE):
            return "GDR"
        return "ADR"
    aliases = {
        "EQUITY": "COMMON_STOCK",
        "STOCK": "COMMON_STOCK",
        "AKTIE": "COMMON_STOCK",
        "CRYPTOCURRENCY": "CRYPTO_ASSET",
    }
    return aliases.get(explicit, explicit or "UNKNOWN")


def derive_research_identity_v2(
    asset: Mapping[str, object],
    *,
    issuer_registry: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Create a listing identity without guessing issuer independence.

    A normalized company name is retained only as a candidate key.  It is never
    promoted to ``issuer_id`` and never used as independent evidence unless an
    explicit or registry-backed issuer relationship exists.
    """

    ticker = _upper(asset.get("ticker") or asset.get("symbol"))
    if not ticker:
        raise ResearchIdentityError("Eine Research-Identität benötigt einen Ticker.")
    exchange = _text(asset.get("exchange") or asset.get("exchange_code"))
    currency = _upper(asset.get("currency"))
    name = _text(asset.get("name") or asset.get("company_name"))
    registry = dict((issuer_registry or {}).get(ticker) or {})

    instrument_text = " ".join(
        str(asset.get(key) or registry.get(key) or "")
        for key in ("name", "instrument_type", "security_type", "quote_type")
    )
    depositary_receipt = bool(
        asset.get("is_depositary_receipt")
        if asset.get("is_depositary_receipt") is not None
        else _DR_PATTERN.search(instrument_text)
    )
    instrument_type = _instrument_type(
        {**registry, **dict(asset)}, depositary_receipt=depositary_receipt
    )
    asset_class = _asset_class({**registry, **dict(asset)})
    isin = _upper(asset.get("isin") or registry.get("isin"))

    listing_id = _text(asset.get("listing_id") or registry.get("listing_id"))
    if listing_id is None:
        listing_id = _stable_id(
            "listing", ticker, exchange or "UNKNOWN", currency or "UNKNOWN", instrument_type
        )
    asset_id = _text(asset.get("asset_id") or registry.get("asset_id")) or _stable_id(
        "asset", ticker, asset_class, listing_id
    )

    explicit_issuer = _text(asset.get("issuer_id") or asset.get("company_id"))
    registry_issuer = _text(registry.get("issuer_id") or registry.get("company_id"))
    issuer_id = explicit_issuer or registry_issuer
    if explicit_issuer:
        issuer_source = "EXPLICIT"
    elif registry_issuer:
        issuer_source = "VERSIONED_REGISTRY"
    else:
        issuer_source = "UNKNOWN"

    dependency_status = "KNOWN" if issuer_id else "UNKNOWN"
    dependency_cluster = f"issuer:{issuer_id}" if issuer_id else "UNKNOWN"
    listing_role = str(
        asset.get("listing_role") or registry.get("listing_role") or "UNKNOWN"
    ).strip().upper()
    if listing_role not in {"PRIMARY", "SECONDARY", "UNKNOWN"}:
        raise ResearchIdentityError("listing_role muss PRIMARY, SECONDARY oder UNKNOWN sein.")

    payload: dict[str, object] = {
        "identity_version": RESEARCH_IDENTITY_V2_VERSION,
        "dependency_version": RESEARCH_DEPENDENCY_V2_VERSION,
        "asset_id": asset_id,
        "listing_id": listing_id,
        "issuer_id": issuer_id,
        "company_id": issuer_id,
        "issuer_candidate_key": _normalized_name(name),
        "issuer_identity_source": issuer_source,
        "dependency_status": dependency_status,
        "dependency_cluster_id": dependency_cluster,
        "ticker": ticker,
        "exchange": exchange,
        "currency": currency,
        "instrument_type": instrument_type,
        "asset_class": asset_class,
        "listing_role": listing_role,
        "is_primary_listing": True if listing_role == "PRIMARY" else False if listing_role == "SECONDARY" else None,
        "is_depositary_receipt": depositary_receipt,
        "depositary_receipt_type": instrument_type if depositary_receipt else None,
        "depositary_ratio": asset.get("depositary_ratio") or registry.get("depositary_ratio"),
        "isin": isin,
        "exchange_timezone": _text(
            asset.get("exchange_timezone") or registry.get("exchange_timezone")
        ),
        "valid_from": _text(asset.get("valid_from") or registry.get("valid_from")),
        "valid_to": _text(asset.get("valid_to") or registry.get("valid_to")),
        "registry_version": _text(registry.get("registry_version")),
        "unknown_is_independent_evidence": False,
    }
    payload["identity_fingerprint"] = _fingerprint(payload)
    return payload


def research_identity_catalog_v2(
    assets: Sequence[Mapping[str, object]],
    *,
    issuer_registry: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    identities = [
        derive_research_identity_v2(asset, issuer_registry=issuer_registry)
        for asset in assets
    ]
    listing_ids = [str(item["listing_id"]) for item in identities]
    if len(listing_ids) != len(set(listing_ids)):
        raise ResearchIdentityError("listing_id ist innerhalb des Research-Katalogs nicht eindeutig.")
    clusters: dict[str, list[str]] = {}
    for item in identities:
        if item["dependency_status"] == "KNOWN":
            clusters.setdefault(str(item["dependency_cluster_id"]), []).append(
                str(item["listing_id"])
            )
    payload: dict[str, object] = {
        "identity_version": RESEARCH_IDENTITY_V2_VERSION,
        "dependency_version": RESEARCH_DEPENDENCY_V2_VERSION,
        "identities": identities,
        "known_issuer_clusters": {key: sorted(value) for key, value in sorted(clusters.items())},
        "raw_listing_n": len(identities),
        "known_issuer_listing_n": sum(item["dependency_status"] == "KNOWN" for item in identities),
        "unknown_issuer_listing_n": sum(item["dependency_status"] == "UNKNOWN" for item in identities),
        "unknown_assumed_independent": False,
    }
    payload["catalog_fingerprint"] = _fingerprint(payload)
    return payload


def dependency_evidence_report_v2(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    known_clusters: set[str] = set()
    unknown = 0
    listing_counts: Counter[str] = Counter()
    for case in cases:
        listing = _text(case.get("listing_id"))
        if listing:
            listing_counts[listing] += 1
        issuer = _text(case.get("issuer_id"))
        status = str(case.get("dependency_status") or ("KNOWN" if issuer else "UNKNOWN")).upper()
        if issuer and status == "KNOWN":
            known_clusters.add(issuer)
        else:
            unknown += 1
    payload: dict[str, object] = {
        "version": RESEARCH_DEPENDENCY_V2_VERSION,
        "raw_n": len(cases),
        "known_issuer_cluster_n": len(known_clusters),
        "unknown_dependency_n": unknown,
        "dependency_coverage_complete": unknown == 0,
        "raw_cases_are_independent_evidence": False,
        "unknown_cases_counted_as_independent": False,
        "duplicate_listing_case_n": sum(max(value - 1, 0) for value in listing_counts.values()),
        "effective_n_status": "COMPLETE" if unknown == 0 else "PARTIAL_UNKNOWN",
        "effective_n_known_clusters_only": len(known_clusters),
    }
    payload["report_fingerprint"] = _fingerprint(payload)
    return payload


_LISTING_SCOPED_SECTIONS = (
    "ohlcv",
    "price",
    "volume",
    "spread",
    "trading_hours",
    "technical_levels",
    "entry",
    "stop",
    "target",
    "liquidity",
    "gap",
)


def validate_listing_scoped_bundle(bundle: Mapping[str, object]) -> dict[str, object]:
    """Reject a technical bundle that mixes listings or quote currencies."""

    identity = dict(bundle.get("identity") or {})
    listing_id = _text(identity.get("listing_id"))
    if not listing_id:
        raise ResearchIdentityError("Ein technischer Datenbund benötigt eine listing_id.")
    currency = _upper(identity.get("currency"))
    checked: list[str] = []
    for section_name in _LISTING_SCOPED_SECTIONS:
        raw = bundle.get(section_name)
        if raw is None:
            continue
        section = dict(raw) if isinstance(raw, Mapping) else {}
        if _text(section.get("listing_id")) != listing_id:
            raise ResearchIdentityError(
                f"{section_name} gehört nicht zum gewählten Listing {listing_id}."
            )
        section_currency = _upper(section.get("currency"))
        if currency and section_currency and section_currency != currency:
            raise ResearchIdentityError(
                f"{section_name} verwendet {section_currency} statt Listing-Währung {currency}."
            )
        checked.append(section_name)
    return {
        "status": "LISTING_CONSISTENT",
        "listing_id": listing_id,
        "currency": currency,
        "checked_sections": checked,
        "cross_listing_values_used": False,
        "bundle_fingerprint": _fingerprint(bundle),
    }
