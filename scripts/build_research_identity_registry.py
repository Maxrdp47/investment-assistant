from __future__ import annotations

import argparse
import csv
import hashlib
import json
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from urllib.request import Request, urlopen

import certifi


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_research_identity_v3 import (  # noqa: E402
    DEFAULT_IDENTITY_REGISTRY_PATH,
    append_identity_registry,
    build_identity_registry,
    dependency_evidence_report_v3,
)


SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_UNIVERSE_PATH = PROJECT_ROOT / "config" / "swing_universe.csv"
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "runtime" / "identity_sources"
DEFAULT_EXPORT_PATH = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "research_identity_registry_2026-08-29-v1.json"
)
DEFAULT_MAPPING_VERSION = "research-identity-registry-2026.08.29-sec-v1"
UNRESOLVED_MAPPING_VERSION = "research-identity-registry-2026.08.29-unresolved-v1"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fetch_sec_company_tickers(*, timeout_seconds: int = 30) -> bytes:
    request = Request(
        SEC_COMPANY_TICKERS_URL,
        headers={
            "User-Agent": "investment-assistant-research/1.0 github.com/Maxrdp47/investment-assistant",
            "Accept": "application/json",
        },
    )
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=timeout_seconds, context=context) as response:  # nosec B310
        return response.read()


def parse_sec_company_tickers(payload: bytes) -> dict[str, dict[str, object]]:
    raw = json.loads(payload.decode("utf-8"))
    rows = raw.values() if isinstance(raw, dict) else raw
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        cik = str(row.get("cik_str") or "").strip()
        title = str(row.get("title") or "").strip()
        if not ticker or not cik.isdigit() or not title:
            continue
        candidate = {
            "ticker": ticker,
            "sec_cik": cik.zfill(10),
            "title": title,
        }
        existing = result.get(ticker)
        if existing is not None and existing["sec_cik"] != candidate["sec_cik"]:
            raise ValueError(f"SEC-Ticker {ticker} ist im Snapshot nicht eindeutig.")
        result[ticker] = candidate
    return result


def load_universe(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_records(
    universe: list[Mapping[str, object]],
    sec_tickers: Mapping[str, Mapping[str, object]],
    *,
    mapping_version: str,
    imported_at: str,
    source_snapshot_fingerprint: str | None,
    issuer_source_available: bool = True,
) -> list[dict[str, object]]:
    date = imported_at[:10]
    records = []
    for asset in universe:
        ticker = str(asset.get("ticker") or "").strip().upper()
        asset_type = str(asset.get("asset_type") or "").strip()
        sec = dict(sec_tickers.get(ticker) or {}) if asset_type == "Aktie" else {}
        base: dict[str, object] = {
            "ticker": ticker,
            "name": str(asset.get("name") or "").strip(),
            "asset_class": asset_type,
            "instrument_type": "COMMON_STOCK" if asset_type == "Aktie" else asset_type,
            "primary_listing_status": "UNKNOWN",
            "mapping_version": mapping_version,
            "source": (
                "SEC company_tickers.json + local versioned universe"
                if issuer_source_available
                else "local versioned universe; external issuer mapping unavailable"
            ),
            "source_reference": (
                SEC_COMPANY_TICKERS_URL
                if issuer_source_available
                else str(DEFAULT_UNIVERSE_PATH)
            ),
            "quality": "HIGH" if sec else "UNKNOWN",
            "confidence": 95 if sec else 0,
            "valid_from": date,
            "first_seen_at": imported_at,
            "imported_at": imported_at,
            "listing_source_id": f"universe:{asset.get('version')}:{ticker}",
            "metadata": {
                "universe_version": asset.get("version"),
                "region": asset.get("region"),
                "source_group": asset.get("source_group"),
                "sec_snapshot_fingerprint": source_snapshot_fingerprint,
                "issuer_source_available": issuer_source_available,
                "research_dependency_only": True,
            },
        }
        if sec:
            cik = str(sec["sec_cik"])
            base.update(
                {
                    "mapping_status": "VERIFIED",
                    "issuer_id": f"sec-cik:{cik}",
                    "issuer_anchor_type": "SEC_CIK",
                    "issuer_anchor_value": cik,
                    "sec_cik": cik,
                }
            )
        else:
            base["mapping_status"] = "UNRESOLVED"
        records.append(base)
    return records


def build_and_store_registry(
    *,
    universe_path: Path,
    source_payload: bytes | None,
    source_root: Path,
    registry_path: Path,
    export_path: Path,
    mapping_version: str,
    imported_at: str,
    source_error: str | None = None,
) -> dict[str, object]:
    source_fingerprint = _sha256_bytes(source_payload) if source_payload is not None else None
    source_path = None
    if source_payload is not None:
        source_root.mkdir(parents=True, exist_ok=True)
        source_path = source_root / f"sec_company_tickers_{imported_at[:10]}_{source_fingerprint[:16]}.json"
        if not source_path.exists():
            source_path.write_bytes(source_payload)
        elif _sha256_bytes(source_path.read_bytes()) != source_fingerprint:
            raise RuntimeError("Gespeicherter SEC-Snapshot besitzt abweichenden Inhalt.")
    universe = load_universe(universe_path)
    sec_tickers = parse_sec_company_tickers(source_payload) if source_payload is not None else {}
    records = build_records(
        universe,
        sec_tickers,
        mapping_version=mapping_version,
        imported_at=imported_at,
        source_snapshot_fingerprint=source_fingerprint,
        issuer_source_available=source_payload is not None,
    )
    registry = build_identity_registry(
        records,
        mapping_version=mapping_version,
        created_at=imported_at,
    )
    append_identity_registry(registry, path=registry_path)
    dependency = dependency_evidence_report_v3(registry["records"])
    payload: dict[str, object] = {
        "status": "IDENTITY_REGISTRY_READY_WITH_VISIBLE_UNKNOWNS",
        "created_at": imported_at,
        "mapping_version": mapping_version,
        "registry_fingerprint": registry["registry_fingerprint"],
        "source": (
            "SEC official company_tickers.json"
            if source_payload is not None
            else "local versioned universe only; SEC provider request failed"
        ),
        "source_url": SEC_COMPANY_TICKERS_URL,
        "source_status": "AVAILABLE" if source_payload is not None else "PROVIDER_FAILURE",
        "source_error": source_error,
        "source_snapshot_path": str(source_path) if source_path else None,
        "source_snapshot_fingerprint": source_fingerprint,
        "universe_path": str(universe_path),
        "universe_fingerprint": _sha256_bytes(universe_path.read_bytes()),
        "raw_asset_n": len(universe),
        "verified_issuer_mapping_n": registry["verified_issuer_n"],
        "unresolved_mapping_n": registry["unresolved_n"],
        "dependency": dependency,
        "mapping_principles": {
            "sec_exact_ticker_only": True,
            "name_fuzzy_linking": False,
            "etf_cik_promoted_to_issuer": False,
            "unknown_is_independent": False,
            "research_dependency_mapping_is_trading_feature": False,
        },
        "multi_asset_scan_started": False,
        "strategy_activated": False,
    }
    payload["artifact_fingerprint"] = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Versioniertes Research-Issuer-/Listing-Registry")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE_PATH)
    parser.add_argument("--source-json", type=Path)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_IDENTITY_REGISTRY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT_PATH)
    parser.add_argument("--mapping-version", default=DEFAULT_MAPPING_VERSION)
    parser.add_argument("--at")
    args = parser.parse_args()
    imported_at = args.at or datetime.now(timezone.utc).isoformat()
    source_error = None
    if args.source_json:
        source_payload = args.source_json.read_bytes()
    else:
        try:
            source_payload = fetch_sec_company_tickers()
        except Exception as exc:
            source_payload = None
            source_error = f"{type(exc).__name__}: {str(exc)[:500]}"
    mapping_version = (
        args.mapping_version
        if source_payload is not None or args.mapping_version != DEFAULT_MAPPING_VERSION
        else UNRESOLVED_MAPPING_VERSION
    )
    result = build_and_store_registry(
        universe_path=args.universe,
        source_payload=source_payload,
        source_root=args.source_root,
        registry_path=args.registry,
        export_path=args.output,
        mapping_version=mapping_version,
        imported_at=imported_at,
        source_error=source_error,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
