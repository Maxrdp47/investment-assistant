from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sec_filing_sources import SecSourceError, validate_sec_user_agent
from sec_json_cache import DEFAULT_SEC_JSON_CACHE_DIR
from sec_long_term_collection import build_cached_sec_loader, collect_sec_long_term_context


SEC_USER_AGENT_ENV = "INVESTMENT_ASSISTANT_SEC_USER_AGENT"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offizielle SEC-Teilquellen für eine spätere Long-Term-Analyse sicher sammeln."
    )
    parser.add_argument("ticker", nargs="?", help="Exakter US-Ticker, zum Beispiel NVDA.")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Laufzeitkonfiguration und Cachepfad ohne Netzwerk und ohne Schreibvorgang prüfen.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_SEC_JSON_CACHE_DIR,
        help="Privater Laufzeitcache für öffentliche SEC-JSON-Daten.",
    )
    return parser.parse_args(argv)


def collection_preflight(
    cache_dir: Path,
    *,
    environment: dict[str, str] | os._Environ[str] = os.environ,
) -> dict[str, object]:
    raw_agent = environment.get(SEC_USER_AGENT_ENV, "")
    contact_ready = False
    contact_status = (
        f"{SEC_USER_AGENT_ENV} fehlt; Live-Abruf bleibt gesperrt."
    )
    if raw_agent:
        try:
            validate_sec_user_agent(raw_agent)
            contact_ready = True
            contact_status = "SEC-Fair-Access-Kontakt ist nur zur Laufzeit konfiguriert."
        except ValueError as exc:
            contact_status = str(exc)

    resolved_cache = Path(cache_dir).resolve()
    runtime_root = (PROJECT_ROOT / "runtime").resolve()
    cache_safe = resolved_cache == runtime_root or runtime_root in resolved_cache.parents
    status = "ready" if contact_ready and cache_safe else "configuration_required"
    return {
        "status": status,
        "network_requested": False,
        "data_written": False,
        "contact_configured": contact_ready,
        "contact_status": contact_status,
        "contact_value_exposed": False,
        "cache_path": str(resolved_cache),
        "cache_inside_private_runtime": cache_safe,
        "note": "SEC-Teilkollektion erzeugt keine Long-Term-Empfehlung und öffnet das Gesamtgate nicht allein.",
    }


def run_live_collection(ticker: str, user_agent: str, cache_dir: Path):
    loader = build_cached_sec_loader(user_agent, cache_dir=cache_dir)
    return collect_sec_long_term_context(
        ticker,
        user_agent=user_agent,
        json_loader=loader,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.preflight:
        result = collection_preflight(args.cache_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ready" else 2

    if not args.ticker:
        print(json.dumps({"status": "error", "error": "Ticker fehlt."}, ensure_ascii=False))
        return 2
    user_agent = os.environ.get(SEC_USER_AGENT_ENV, "")
    try:
        validate_sec_user_agent(user_agent)
    except ValueError as exc:
        print(json.dumps({"status": "configuration_required", "error": str(exc)}, ensure_ascii=False))
        return 2

    try:
        result = run_live_collection(args.ticker, user_agent, args.cache_dir)
    except (SecSourceError, ValueError, OSError) as exc:
        print(
            json.dumps(
                {"status": "error", "error": str(exc), "contact_value_exposed": False},
                ensure_ascii=False,
            )
        )
        return 1
    payload = asdict(result)
    payload["contact_value_exposed"] = False
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.available else 3


if __name__ == "__main__":
    raise SystemExit(main())
