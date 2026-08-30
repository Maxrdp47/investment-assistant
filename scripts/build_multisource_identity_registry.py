from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence
from urllib.request import Request, urlopen

import certifi


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_identity_multisource import (  # noqa: E402
    MULTISOURCE_MAPPING_VERSION,
    OPENFIGI_API_URL,
    SEC_DERIVED_SNAPSHOT_URL,
    build_multisource_registry,
    canonical_json,
    exchange_metadata,
    file_sha256,
    load_official_relations,
    load_openfigi_snapshot,
    parse_sec_derived_csv,
    status_counts,
)
from scripts.build_research_identity_registry import load_universe  # noqa: E402
from swing_research_identity_v3 import (  # noqa: E402
    DEFAULT_IDENTITY_REGISTRY_PATH,
    append_identity_registry,
)


DEFAULT_UNIVERSE = PROJECT_ROOT / "config" / "swing_universe.csv"
DEFAULT_RELATIONS = PROJECT_ROOT / "config" / "research_identity_relations_v1.json"
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "runtime" / "identity_sources"
DEFAULT_EXPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "research_identity_registry_2026-08-30-v2.json"
)
DEFAULT_SUMMARY = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "research_identity_coverage_2026-08-30-v2.json"
)


def _download(url: str, *, timeout_seconds: int = 60) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "investment-assistant-research-identity/1.0",
            "Accept": "text/csv,application/json",
        },
    )
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=timeout_seconds, context=context) as response:  # nosec B310
        return response.read()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _code_fingerprint() -> str:
    digest = __import__("hashlib").sha256()
    for path in (
        PROJECT_ROOT / "research_identity_multisource.py",
        PROJECT_ROOT / "swing_research_identity_v3.py",
        Path(__file__).resolve(),
        DEFAULT_RELATIONS,
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def ensure_sec_snapshot(source_root: Path, supplied_path: Path | None = None) -> Path:
    if supplied_path is not None:
        return Path(supplied_path)
    payload = _download(SEC_DERIVED_SNAPSHOT_URL)
    digest = __import__("hashlib").sha256(payload).hexdigest()
    source_root.mkdir(parents=True, exist_ok=True)
    path = source_root / f"sec_derived_cik_7883b833_{digest[:16]}.csv"
    if path.exists() and file_sha256(path) != digest:
        raise RuntimeError("SEC-derived source snapshot changed on disk.")
    if not path.exists():
        path.write_bytes(payload)
    return path


def _openfigi_jobs(
    universe: Sequence[Mapping[str, object]],
    sec_rows: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    jobs = []
    for asset in universe:
        ticker = str(asset.get("ticker") or "").upper()
        asset_type = str(asset.get("asset_type") or "")
        metadata = exchange_metadata(ticker)
        sec_key = metadata["provider_ticker"] if metadata["exch_code"] == "US" else None
        exact_sec = list(sec_rows.get(sec_key or "") or []) if asset_type == "Aktie" else []
        if len(exact_sec) == 1:
            continue
        request = {
            "idType": "TICKER",
            "idValue": metadata["provider_ticker"],
            "marketSecDes": "Equity",
            "exchCode": metadata["exch_code"],
        }
        jobs.append({"universe_ticker": ticker, "request": request})
    return jobs


def fetch_openfigi_snapshot(
    jobs: Sequence[Mapping[str, object]],
    *,
    checkpoint_path: Path,
    at: str,
    batch_size: int = 10,
    minimum_interval_seconds: float = 2.5,
) -> Path:
    existing: dict[str, dict[str, object]] = {}
    if checkpoint_path.exists():
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        existing = {
            str(item.get("universe_ticker")): dict(item)
            for item in payload.get("requests") or []
        }
    pending = [dict(job) for job in jobs if str(job["universe_ticker"]) not in existing]
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        body = json.dumps([item["request"] for item in batch]).encode("utf-8")
        request = Request(
            OPENFIGI_API_URL,
            data=body,
            method="POST",
            headers={
                "User-Agent": "investment-assistant-research-identity/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(request, timeout=60, context=context) as response:  # nosec B310
                answers = json.loads(response.read().decode("utf-8"))
            if len(answers) != len(batch):
                raise RuntimeError("OpenFIGI response count does not match request count.")
            for job, answer in zip(batch, answers, strict=True):
                existing[str(job["universe_ticker"])] = {
                    **job,
                    "response": list(answer.get("data") or []),
                    "provider_warning": answer.get("warning"),
                    "provider_error": answer.get("error"),
                    "error": None,
                }
        except Exception as exc:
            for job in batch:
                existing[str(job["universe_ticker"])] = {
                    **job,
                    "response": [],
                    "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                }
        snapshot = {
            "version": "openfigi-listing-snapshot-2026.08.30-v1",
            "created_at": at,
            "provider_url": OPENFIGI_API_URL,
            "issuer_identifier_claimed": False,
            "requests": [existing[key] for key in sorted(existing)],
        }
        checkpoint_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if offset + batch_size < len(pending):
            time.sleep(minimum_interval_seconds)
    return checkpoint_path


def run(args: argparse.Namespace) -> dict[str, object]:
    imported_at = args.at or datetime.now(timezone.utc).isoformat()
    universe = load_universe(Path(args.universe))
    sec_path = ensure_sec_snapshot(Path(args.source_root), args.sec_csv)
    sec_rows = parse_sec_derived_csv(sec_path)
    openfigi_path = args.openfigi_json
    if openfigi_path is None:
        openfigi_path = Path(args.source_root) / "openfigi_identity_checkpoint_2026-08-30.json"
        jobs = _openfigi_jobs(universe, sec_rows)
        fetch_openfigi_snapshot(
            jobs,
            checkpoint_path=openfigi_path,
            at=imported_at,
            minimum_interval_seconds=args.openfigi_interval_seconds,
        )
    openfigi_rows = load_openfigi_snapshot(openfigi_path)
    official_by_ticker, official_payload = load_official_relations(Path(args.relations))
    provenance = {
        "universe_path": str(Path(args.universe).resolve()),
        "universe_sha256": file_sha256(Path(args.universe)),
        "sec_derived_snapshot_path": str(sec_path.resolve()),
        "sec_derived_snapshot_sha256": file_sha256(sec_path),
        "sec_derived_snapshot_url": SEC_DERIVED_SNAPSHOT_URL,
        "sec_derived_snapshot_commit": "7883b83389836f9bba9bdfe53031467235746334",
        "sec_derived_source_quality": "MEDIUM_PINNED_THIRD_PARTY_MIRROR",
        "openfigi_snapshot_path": str(Path(openfigi_path).resolve()),
        "openfigi_snapshot_sha256": file_sha256(Path(openfigi_path)),
        "openfigi_role": "CURRENT_LISTING_AND_SHARE_CLASS_EVIDENCE_ONLY",
        "official_relations_path": str(Path(args.relations).resolve()),
        "official_relations_sha256": file_sha256(Path(args.relations)),
        "official_relations_version": official_payload.get("version"),
        "direct_sec_endpoint_status": "HTTP_403_ON_THIS_HOST",
    }
    registry = build_multisource_registry(
        universe,
        sec_rows=sec_rows,
        openfigi_rows=openfigi_rows,
        official_relations=official_by_ticker,
        mapping_version=args.mapping_version,
        imported_at=imported_at,
        source_provenance=provenance,
    )
    registry.pop("registry_fingerprint", None)
    registry["branch"] = _git("rev-parse", "--abbrev-ref", "HEAD")
    registry["commit"] = _git("rev-parse", "HEAD")
    registry["code_fingerprint"] = _code_fingerprint()
    registry["mapping_fingerprint"] = __import__("hashlib").sha256(
        canonical_json(
            [record["mapping_fingerprint"] for record in registry["records"]]
        ).encode("utf-8")
    ).hexdigest()
    registry["command"] = "python scripts/build_multisource_identity_registry.py"
    registry["status"] = "IDENTITY_REGISTRY_READY_WITH_VISIBLE_UNKNOWNS"
    registry["output_digest"] = __import__("hashlib").sha256(
        canonical_json(
            {
                "mapping_version": registry["mapping_version"],
                "mapping_fingerprint": registry["mapping_fingerprint"],
                "source_provenance": registry["source_provenance"],
                "coverage_gate": registry["coverage_gate"],
            }
        ).encode("utf-8")
    ).hexdigest()
    registry["registry_fingerprint"] = __import__("hashlib").sha256(
        canonical_json(registry).encode("utf-8")
    ).hexdigest()
    append_identity_registry(registry, path=Path(args.registry))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "version": "research-identity-coverage-2026.08.30-v2",
        "created_at": imported_at,
        "mapping_version": registry["mapping_version"],
        "registry_fingerprint": registry["registry_fingerprint"],
        "mapping_fingerprint": registry["mapping_fingerprint"],
        "branch": registry["branch"],
        "commit": registry["commit"],
        "code_fingerprint": registry["code_fingerprint"],
        "command": registry["command"],
        "status": registry["status"],
        "output_digest": registry["output_digest"],
        "record_n": registry["record_n"],
        "mapping_status_counts": status_counts(registry["records"]),
        "dependency": registry["dependency"],
        "coverage_gate": registry["coverage_gate"],
        "source_provenance": provenance,
        "name_only_links_created": 0,
        "automatic_fuzzy_links_created": 0,
        "unknown_counted_as_independent": False,
        "multi_asset_scan_started": False,
        "strategy_activated": False,
    }
    summary["artifact_fingerprint"] = __import__("hashlib").sha256(
        canonical_json(summary).encode("utf-8")
    ).hexdigest()
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Conservative multi-source issuer registry")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--relations", type=Path, default=DEFAULT_RELATIONS)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--sec-csv", type=Path)
    parser.add_argument("--openfigi-json", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_IDENTITY_REGISTRY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--mapping-version", default=MULTISOURCE_MAPPING_VERSION)
    parser.add_argument("--openfigi-interval-seconds", type=float, default=2.5)
    parser.add_argument("--at")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
