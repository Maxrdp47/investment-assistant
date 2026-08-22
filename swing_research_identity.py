from __future__ import annotations

import hashlib
import re
import unicodedata
from functools import lru_cache
from typing import Mapping, Sequence


SWING_RESEARCH_IDENTITY_VERSION = "swing-research-identity-2026.08.18-v1"

_DEPENDENCY_QUALIFIER = re.compile(
    r"\b(?:adr|ads|gdr|depositary|depository|ordinary|common|preferred|preference|"
    r"stamm(?:aktie)?|vorzugs?(?:aktie)?|share\s*class|class|series)\b",
    re.IGNORECASE,
)
_PARENTHETICAL = re.compile(r"\(([^()]*)\)")
_INSTRUMENT_WORDS = re.compile(
    r"\b(?:sponsored\s+)?(?:american\s+)?(?:depositary|depository)\s+"
    r"(?:receipt|receipts|share|shares)\b|\b(?:adr|ads|gdr)s?\b|"
    r"\b(?:ordinary|common|preferred|preference)\s+(?:stock|share|shares)\b|"
    r"\b(?:class|series)\s+[a-z0-9]+\b|\b(?:stammaktie|stammaktien|"
    r"vorzugsaktie|vorzugsaktien)\b",
    re.IGNORECASE,
)
_DEPOSITARY_RECEIPT = re.compile(
    r"\b(?:adr|ads|gdr)s?\b|\b(?:american\s+)?(?:depositary|depository)\s+"
    r"(?:receipt|receipts|share|shares)\b",
    re.IGNORECASE,
)
_LEGAL_SUFFIXES = {
    "ag",
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "ltd",
    "nv",
    "plc",
    "sa",
    "se",
    "spa",
}


def _normalized_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", text).strip()


def normalized_issuer_name(value: object) -> str:
    """Normalize only legal/listing wrappers, never ticker-specific aliases."""

    text = _normalized_text(value)

    def keep_or_remove(match: re.Match[str]) -> str:
        content = match.group(1)
        return " " if _DEPENDENCY_QUALIFIER.search(content) else f" {content} "

    text = _PARENTHETICAL.sub(keep_or_remove, text)
    text = _INSTRUMENT_WORDS.sub(" ", text)
    tokens = re.findall(r"[a-z0-9]+", text)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join([SWING_RESEARCH_IDENTITY_VERSION, *(str(part or "") for part in parts)])
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def derive_swing_research_identity(asset: Mapping[str, object]) -> dict:
    ticker = str(asset.get("ticker") or asset.get("symbol") or "").strip().upper()
    name = str(asset.get("name") or asset.get("company_name") or "").strip()
    asset_type = str(asset.get("asset_type") or "Aktie").strip()
    region = str(asset.get("region") or "").strip()
    exchange = str(asset.get("exchange") or "").strip() or None
    isin = str(asset.get("isin") or "").strip().upper() or None
    explicit_listing_id = str(asset.get("listing_id") or asset.get("asset_id") or "").strip()
    listing_id = explicit_listing_id or _stable_id(
        "listing", ticker, exchange or "", region, asset_type, isin or ""
    )

    explicit_issuer_id = str(asset.get("issuer_id") or asset.get("company_id") or "").strip()
    normalized_name = normalized_issuer_name(name)
    if explicit_issuer_id:
        issuer_id = explicit_issuer_id
        issuer_source = "explicit_issuer_or_company_id"
        confidence = "verified"
    elif normalized_name:
        issuer_id = _stable_id("issuer", normalized_name)
        issuer_source = "normalized_issuer_name"
        confidence = "derived"
    else:
        # Missing issuer evidence must never merge otherwise unrelated listings.
        issuer_id = _stable_id("issuer-listing-fallback", listing_id)
        issuer_source = "listing_fallback"
        confidence = "listing_only"

    instrument_text = " ".join(
        str(asset.get(key) or "")
        for key in ("name", "instrument_type", "quote_type", "security_type")
    )
    share_class_match = re.search(
        r"\b(?:class|series)\s+([a-z0-9]+)\b",
        _normalized_text(instrument_text),
    )
    economic_instrument_id = str(asset.get("economic_instrument_id") or "").strip() or None
    if economic_instrument_id is None and isin:
        economic_instrument_id = f"isin:{isin}"

    return {
        "identity_version": SWING_RESEARCH_IDENTITY_VERSION,
        "listing_id": listing_id,
        "issuer_id": issuer_id,
        "company_id": issuer_id,
        "issuer_name": name or None,
        "normalized_issuer_name": normalized_name or None,
        "issuer_identity_source": issuer_source,
        "identity_confidence": confidence,
        "ticker": ticker,
        "exchange": exchange,
        "isin": isin,
        "asset_type": asset_type,
        "region": region or None,
        "economic_instrument_id": economic_instrument_id,
        "is_depositary_receipt": bool(_DEPOSITARY_RECEIPT.search(instrument_text)),
        "share_class": share_class_match.group(1).upper() if share_class_match else None,
    }


def swing_research_identity_map(assets: Sequence[Mapping[str, object]]) -> dict[str, dict]:
    identities: dict[str, dict] = {}
    for asset in assets:
        identity = derive_swing_research_identity(asset)
        ticker = str(identity.get("ticker") or "")
        if ticker:
            identities[ticker] = identity
    return identities


@lru_cache(maxsize=1)
def default_swing_research_identity_map() -> dict[str, dict]:
    """Derive legacy identities without modifying historical case payloads."""

    try:
        from swing_universe import load_swing_universe

        report = load_swing_universe(minimum_active_assets=1)
    except Exception:
        return {}
    return swing_research_identity_map([asset.as_dict() for asset in report.assets])
