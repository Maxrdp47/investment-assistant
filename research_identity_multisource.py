from __future__ import annotations

"""Conservative multi-source issuer resolution for research dependency control.

This module never uses issuer names as proof.  An exact SEC CIK or an official,
curated issuer relation may verify an issuer.  OpenFIGI is used as listing and
share-class evidence only; it is deliberately not promoted to an issuer ID.
"""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from swing_research_identity_v3 import build_identity_registry, dependency_evidence_report_v3


MULTISOURCE_MAPPING_VERSION = "research-identity-registry-2026.08.30-multisource-v2"
MULTISOURCE_METHOD_VERSION = "research-issuer-resolution-2026.08.30-v1"
PREDECLARED_MINIMUM_VERIFIED_COVERAGE_PCT = 80.0
SEC_DERIVED_SNAPSHOT_URL = (
    "https://raw.githubusercontent.com/jadchaar/sec-cik-mapper/"
    "7883b83389836f9bba9bdfe53031467235746334/mappings/stocks/mappings.csv"
)
OPENFIGI_API_URL = "https://api.openfigi.com/v3/mapping"


EXCHANGE_SUFFIXES: dict[str, dict[str, str]] = {
    ".DE": {"exch_code": "GR", "mic": "XETR", "currency": "EUR", "timezone": "Europe/Berlin"},
    ".T": {"exch_code": "JP", "mic": "XTKS", "currency": "JPY", "timezone": "Asia/Tokyo"},
    ".HK": {"exch_code": "HK", "mic": "XHKG", "currency": "HKD", "timezone": "Asia/Hong_Kong"},
    ".PA": {"exch_code": "FP", "mic": "XPAR", "currency": "EUR", "timezone": "Europe/Paris"},
    ".L": {"exch_code": "LN", "mic": "XLON", "currency": "GBP", "timezone": "Europe/London"},
    ".NS": {"exch_code": "IN", "mic": "XNSE", "currency": "INR", "timezone": "Asia/Kolkata"},
    ".KS": {"exch_code": "KS", "mic": "XKRX", "currency": "KRW", "timezone": "Asia/Seoul"},
    ".SW": {"exch_code": "SW", "mic": "XSWX", "currency": "CHF", "timezone": "Europe/Zurich"},
    ".AS": {"exch_code": "NA", "mic": "XAMS", "currency": "EUR", "timezone": "Europe/Amsterdam"},
    ".TW": {"exch_code": "TT", "mic": "XTAI", "currency": "TWD", "timezone": "Asia/Taipei"},
    ".MI": {"exch_code": "IM", "mic": "XMIL", "currency": "EUR", "timezone": "Europe/Rome"},
    ".CO": {"exch_code": "DC", "mic": "XCSE", "currency": "DKK", "timezone": "Europe/Copenhagen"},
    ".MC": {"exch_code": "SM", "mic": "XMAD", "currency": "EUR", "timezone": "Europe/Madrid"},
}
US_DEFAULT = {
    "exch_code": "US",
    "mic": "US-CONSOLIDATED",
    "currency": "USD",
    "timezone": "America/New_York",
}


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sec_derived_csv(path: Path) -> dict[str, list[dict[str, str]]]:
    """Read an immutable SEC-derived mirror; duplicate tickers stay conflicts."""

    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("Ticker") or row.get("ticker") or "").strip().upper()
            cik = str(row.get("CIK") or row.get("cik") or "").strip()
            if not ticker or not cik.isdigit():
                continue
            item = {
                "ticker": ticker,
                "sec_cik": cik.zfill(10),
                "name": str(row.get("Name") or row.get("name") or "").strip(),
                "exchange": str(row.get("Exchange") or row.get("exchange") or "").strip(),
            }
            if item not in result[ticker]:
                result[ticker].append(item)
    return dict(result)


def load_openfigi_snapshot(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result: dict[str, dict[str, object]] = {}
    for item in payload.get("requests") or []:
        ticker = str(item.get("universe_ticker") or "").upper()
        if ticker:
            result[ticker] = dict(item)
    return result


def load_official_relations(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    by_ticker: dict[str, dict[str, object]] = {}
    for relation in payload.get("relations") or []:
        relation = dict(relation)
        for listing in relation.get("listings") or []:
            ticker = str(listing.get("ticker") or "").upper()
            if not ticker:
                continue
            if ticker in by_ticker:
                raise ValueError(f"Doppelte offizielle Relation für {ticker}.")
            by_ticker[ticker] = {**relation, "listing": dict(listing)}
    return by_ticker, payload


def exchange_metadata(ticker: str) -> dict[str, str]:
    ticker = ticker.upper()
    for suffix, metadata in EXCHANGE_SUFFIXES.items():
        if ticker.endswith(suffix):
            return {**metadata, "provider_ticker": ticker[: -len(suffix)]}
    return {**US_DEFAULT, "provider_ticker": ticker.replace(".", "-")}


def _unique_openfigi(item: Mapping[str, object] | None) -> tuple[dict[str, object] | None, bool]:
    if not item or item.get("error"):
        return None, False
    candidates = [dict(value) for value in item.get("response") or [] if isinstance(value, Mapping)]
    unique = {str(value.get("figi") or ""): value for value in candidates if value.get("figi")}
    if len(unique) == 1:
        return next(iter(unique.values())), False
    return None, len(unique) > 1


def _sec_key(ticker: str) -> str | None:
    if any(ticker.endswith(suffix) for suffix in EXCHANGE_SUFFIXES):
        return None
    return ticker.replace(".", "-")


def build_multisource_records(
    universe: Sequence[Mapping[str, object]],
    *,
    sec_rows: Mapping[str, Sequence[Mapping[str, object]]],
    openfigi_rows: Mapping[str, Mapping[str, object]],
    official_relations: Mapping[str, Mapping[str, object]],
    mapping_version: str,
    imported_at: str,
    source_provenance: Mapping[str, object],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    date = imported_at[:10]
    for asset in universe:
        ticker = str(asset.get("ticker") or "").strip().upper()
        asset_type = str(asset.get("asset_type") or "").strip()
        exchange = exchange_metadata(ticker)
        exact_sec = list(sec_rows.get(_sec_key(ticker) or "") or []) if asset_type == "Aktie" else []
        figi, figi_conflict = _unique_openfigi(openfigi_rows.get(ticker))
        relation = dict(official_relations.get(ticker) or {})
        evidence: list[dict[str, object]] = []
        if exact_sec:
            evidence.append(
                {
                    "type": "SEC_CIK_EXACT_TICKER",
                    "identifier": [row.get("sec_cik") for row in exact_sec],
                    "source": source_provenance.get("sec_derived_snapshot_url"),
                }
            )
        if figi:
            evidence.append(
                {
                    "type": "OPENFIGI_EXACT_LISTING",
                    "identifier": figi.get("figi"),
                    "source": OPENFIGI_API_URL,
                }
            )
        if relation:
            evidence.append(
                {
                    "type": "OFFICIAL_ISSUER_LISTING_RELATION",
                    "identifier": relation.get("issuer_anchor_value"),
                    "source": relation.get("source_reference"),
                    "description": relation.get("evidence"),
                }
            )

        status = "UNRESOLVED"
        issuer_id = None
        anchor_type = None
        anchor_value = None
        confidence = 0
        quality = "UNKNOWN"
        source_identifier = None
        if relation:
            status = "VERIFIED"
            issuer_id = str(relation["issuer_id"])
            anchor_type = "DOCUMENTED_ADR_RELATION"
            anchor_value = str(relation["issuer_anchor_value"])
            source_identifier = anchor_value
            confidence = 100
            quality = "HIGH"
        elif figi_conflict or len({str(row.get("sec_cik")) for row in exact_sec}) > 1:
            status = "CONFLICT"
            confidence = 0
            quality = "UNKNOWN"
        elif len(exact_sec) == 1:
            status = "VERIFIED"
            cik = str(exact_sec[0]["sec_cik"])
            issuer_id = f"sec-cik:{cik}"
            anchor_type = "SEC_CIK"
            anchor_value = cik
            source_identifier = cik
            confidence = 90
            quality = "MEDIUM"
        elif figi:
            # FIGI/shareClassFIGI identifies a listing/share class, not the
            # legal issuer.  It therefore remains fail-closed for issuer N.
            status = "CANDIDATE_UNVERIFIED"
            source_identifier = str(figi.get("figi") or "")
            confidence = 70
            quality = "MEDIUM"

        relation_listing = dict(relation.get("listing") or {})
        instrument_type = str(
            relation_listing.get("instrument_type")
            or (figi or {}).get("securityType2")
            or ("COMMON_STOCK" if asset_type == "Aktie" else asset_type)
        ).upper().replace(" ", "_")
        source_parts = ["local versioned universe"]
        if exact_sec:
            source_parts.append("pinned SEC-derived CIK snapshot")
        if figi or figi_conflict:
            source_parts.append("OpenFIGI listing snapshot")
        if relation:
            source_parts.append("official issuer relation")
        record: dict[str, object] = {
            "ticker": ticker,
            "name": str(asset.get("name") or "").strip(),
            "asset_class": asset_type,
            "instrument_type": instrument_type,
            "primary_listing_status": relation_listing.get("listing_role", "UNKNOWN"),
            "mapping_version": mapping_version,
            "mapping_status": status,
            "source": " + ".join(source_parts),
            "source_reference": str(
                relation.get("source_reference")
                or source_provenance.get("sec_derived_snapshot_url")
                or OPENFIGI_API_URL
            ),
            "source_identifier": source_identifier,
            "evidence": evidence,
            "quality": quality,
            "confidence": confidence,
            "valid_from": date,
            "first_seen_at": imported_at,
            "imported_at": imported_at,
            "listing_source_id": (
                (str((figi or {}).get("figi")) if (figi or {}).get("figi") else None)
                or f"universe:{asset.get('version')}:{ticker}:{exchange['mic']}"
            ),
            "figi": (figi or {}).get("figi"),
            "composite_figi": (figi or {}).get("compositeFIGI"),
            "share_class_figi": (figi or {}).get("shareClassFIGI"),
            "exchange": str((figi or {}).get("exchCode") or exchange["exch_code"]),
            "mic": exchange["mic"],
            "currency": exchange["currency"],
            "exchange_timezone": exchange["timezone"],
            "issuer_id": issuer_id,
            "issuer_anchor_type": anchor_type,
            "issuer_anchor_value": anchor_value,
            "sec_cik": anchor_value if anchor_type == "SEC_CIK" else None,
            "is_depositary_receipt": instrument_type in {"ADR", "ADS", "DEPOSITARY_RECEIPT"},
            "metadata": {
                "universe_version": asset.get("version"),
                "region": asset.get("region"),
                "source_group": asset.get("source_group"),
                "method_version": MULTISOURCE_METHOD_VERSION,
                "name_used_as_identifier": False,
                "unknown_counted_as_independent": False,
            },
        }
        records.append(record)
    return records


def coverage_gate(
    records: Sequence[Mapping[str, object]],
    *,
    official_relations: Mapping[str, Mapping[str, object]],
    minimum_verified_coverage_pct: float = PREDECLARED_MINIMUM_VERIFIED_COVERAGE_PCT,
) -> dict[str, object]:
    eligible = [row for row in records if str(row.get("asset_class")) in {"EQUITIES", "ETF"}]
    verified = [row for row in eligible if row.get("mapping_status") == "VERIFIED"]
    conflict = [row for row in eligible if row.get("mapping_status") == "CONFLICT"]
    universe_tickers = {str(row.get("ticker")) for row in eligible}
    relation_groups: dict[str, set[str]] = defaultdict(set)
    for ticker, relation in official_relations.items():
        if ticker in universe_tickers:
            relation_groups[str(relation.get("issuer_id"))].add(ticker)
    expected_groups = {key: values for key, values in relation_groups.items() if len(values) >= 2}
    actual: dict[str, set[str]] = defaultdict(set)
    for row in verified:
        actual[str(row.get("issuer_id"))].add(str(row.get("ticker")))
    failed_groups = {
        key: sorted(values)
        for key, values in expected_groups.items()
        if not values <= actual.get(key, set())
    }
    coverage_pct = len(verified) / len(eligible) * 100 if eligible else 0.0
    checks = {
        "predeclared_coverage_threshold_met": coverage_pct >= minimum_verified_coverage_pct,
        "known_official_dependency_groups_resolved": not failed_groups,
        "critical_conflicts_absent": not conflict,
        "unresolved_fail_closed": all(
            row.get("dependency_status") == "UNKNOWN"
            for row in eligible
            if row.get("mapping_status") != "VERIFIED"
        ),
        "unknown_not_independent": all(
            row.get("unknown_is_independent_evidence") is False for row in eligible
        ),
    }
    payload = {
        "version": "research-identity-coverage-gate-2026.08.30-v1",
        "method": (
            "predeclared 80% issuer-eligible listing coverage; every configured official "
            "multi-listing relation present in the universe resolved; conflicts fail closed"
        ),
        "minimum_verified_coverage_pct": minimum_verified_coverage_pct,
        "issuer_eligible_listing_n": len(eligible),
        "verified_listing_n": len(verified),
        "verified_coverage_pct": round(coverage_pct, 6),
        "candidate_unverified_n": sum(row.get("mapping_status") == "CANDIDATE_UNVERIFIED" for row in eligible),
        "unresolved_n": sum(row.get("mapping_status") == "UNRESOLVED" for row in eligible),
        "conflict_n": len(conflict),
        "known_official_dependency_group_n": len(expected_groups),
        "failed_official_dependency_groups": failed_groups,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "not_optimized_on_research_results": True,
    }
    payload["fingerprint"] = fingerprint(payload)
    return payload


def build_multisource_registry(
    universe: Sequence[Mapping[str, object]],
    *,
    sec_rows: Mapping[str, Sequence[Mapping[str, object]]],
    openfigi_rows: Mapping[str, Mapping[str, object]],
    official_relations: Mapping[str, Mapping[str, object]],
    mapping_version: str,
    imported_at: str,
    source_provenance: Mapping[str, object],
) -> dict[str, object]:
    raw_records = build_multisource_records(
        universe,
        sec_rows=sec_rows,
        openfigi_rows=openfigi_rows,
        official_relations=official_relations,
        mapping_version=mapping_version,
        imported_at=imported_at,
        source_provenance=source_provenance,
    )
    registry = build_identity_registry(
        raw_records,
        mapping_version=mapping_version,
        created_at=imported_at,
    )
    registry["dependency"] = dependency_evidence_report_v3(registry["records"])
    registry["coverage_gate"] = coverage_gate(
        registry["records"], official_relations=official_relations
    )
    registry["source_provenance"] = dict(source_provenance)
    # Adding the audit envelope changes the registry payload, so calculate one
    # final fingerprint over everything except the fingerprint itself.
    registry.pop("registry_fingerprint", None)
    registry["registry_fingerprint"] = fingerprint(registry)
    return registry


def status_counts(records: Iterable[Mapping[str, object]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("mapping_status")) for row in records).items()))
