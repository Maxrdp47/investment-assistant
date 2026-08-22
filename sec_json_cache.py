from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Callable

from sec_filing_sources import SEC_COMPANY_FACTS_URL, SEC_SUBMISSIONS_URL, SEC_TICKER_MAP_URL, SecJsonLoader


SEC_JSON_CACHE_SCHEMA_VERSION = 1
DEFAULT_SEC_JSON_CACHE_DIR = Path(__file__).resolve().parent / "runtime" / "sec_json_cache"
DEFAULT_TICKER_MAP_TTL = timedelta(hours=24)
DEFAULT_SUBMISSIONS_TTL = timedelta(hours=6)
DEFAULT_COMPANY_FACTS_TTL = timedelta(hours=6)

NowProvider = Callable[[], datetime]


def _aware_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def sec_cache_path_for_url(
    url: str,
    cache_dir: Path = DEFAULT_SEC_JSON_CACHE_DIR,
) -> Path:
    if url == SEC_TICKER_MAP_URL:
        filename = "company_tickers_exchange.json"
    else:
        match = re.fullmatch(r"https://data\.sec\.gov/submissions/CIK(\d{10})\.json", url)
        if match:
            filename = f"submissions-CIK{match.group(1)}.json"
        else:
            match = re.fullmatch(
                r"https://data\.sec\.gov/api/xbrl/companyfacts/CIK(\d{10})\.json",
                url,
            )
            if not match:
                raise ValueError("Nicht zugelassene SEC-Cache-Adresse.")
            filename = f"companyfacts-CIK{match.group(1)}.json"
    return Path(cache_dir) / filename


def sec_cache_ttl_for_url(url: str) -> timedelta:
    if url == SEC_TICKER_MAP_URL:
        return DEFAULT_TICKER_MAP_TTL
    if re.fullmatch(r"https://data\.sec\.gov/submissions/CIK\d{10}\.json", url):
        return DEFAULT_SUBMISSIONS_TTL
    if re.fullmatch(r"https://data\.sec\.gov/api/xbrl/companyfacts/CIK\d{10}\.json", url):
        return DEFAULT_COMPANY_FACTS_TTL
    raise ValueError("Nicht zugelassene SEC-Cache-Adresse.")


def load_fresh_sec_json_cache(
    path: Path,
    *,
    url: str,
    now: datetime,
    ttl: timedelta,
) -> object | None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("SEC-Cache-Prüfzeitpunkt benötigt eine Zeitzone.")
    if ttl <= timedelta(0):
        raise ValueError("SEC-Cache-Gültigkeit muss positiv sein.")
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != SEC_JSON_CACHE_SCHEMA_VERSION:
        return None
    if payload.get("url") != url:
        return None
    fetched_at = _aware_datetime(payload.get("fetched_at"))
    if fetched_at is None:
        return None
    current = now.astimezone(timezone.utc)
    if fetched_at > current + timedelta(minutes=5):
        return None
    if current - fetched_at > ttl:
        return None
    if "payload" not in payload:
        return None
    return deepcopy(payload["payload"])


def save_sec_json_cache(
    path: Path,
    *,
    url: str,
    fetched_at: datetime,
    payload: object,
) -> bool:
    expected_path = sec_cache_path_for_url(url, Path(path).parent)
    if expected_path.name != Path(path).name:
        raise ValueError("SEC-Cache-Dateiname passt nicht zur Adresse.")
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError("SEC-Cache-Abrufzeitpunkt benötigt eine Zeitzone.")
    document = {
        "schema_version": SEC_JSON_CACHE_SCHEMA_VERSION,
        "url": url,
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(),
        "payload": payload,
    }
    target = Path(path)
    temporary_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
        return True
    except (OSError, TypeError, ValueError):
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False


class SecCachedJsonClient:
    """Reuse fresh public SEC JSON across process restarts.

    The wrapper never persists the user-agent contact string. Cache failures do
    not turn a successful public read into a failed discovery, while corrupt or
    stale entries are never served.
    """

    def __init__(
        self,
        upstream: SecJsonLoader,
        *,
        cache_dir: Path = DEFAULT_SEC_JSON_CACHE_DIR,
        now_provider: NowProvider = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._upstream = upstream
        self._cache_dir = Path(cache_dir)
        self._now_provider = now_provider
        self._lock = Lock()

    def __call__(self, url: str, user_agent: str) -> object:
        path = sec_cache_path_for_url(url, self._cache_dir)
        ttl = sec_cache_ttl_for_url(url)
        with self._lock:
            now = self._now_provider()
            cached = load_fresh_sec_json_cache(path, url=url, now=now, ttl=ttl)
            if cached is not None:
                return cached
            payload = self._upstream(url, user_agent)
            save_sec_json_cache(path, url=url, fetched_at=now, payload=payload)
            return deepcopy(payload)
