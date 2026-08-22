from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from long_term_analysis import LongTermSource, source_freshness_issues, source_validation_issues


SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_ARCHIVE_DOCUMENT_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_without_dashes}/{document}"
)
SEC_SOURCE_ADAPTER_VERSION = "2026.08.02-sec-filings-v1"
SEC_MAX_RESPONSE_BYTES = 20 * 1024 * 1024
SEC_MAX_ATTEMPTS = 3
SEC_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
SEC_RETRY_BACKOFF_SECONDS = (0.5, 1.0)

ANNUAL_FORMS = frozenset({"10-K", "20-F", "40-F"})
QUARTERLY_FORMS = frozenset({"10-Q"})
SUPPORTED_FORMS = ANNUAL_FORMS | QUARTERLY_FORMS

SecJsonLoader = Callable[[str, str], object]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class SecSourceError(RuntimeError):
    """Safe SEC source-discovery error without request credentials."""


@dataclass(frozen=True)
class SecFilingSourceDiscovery:
    adapter_version: str
    available: bool
    ticker: str
    cik: int | None
    company_name: str | None
    status: str
    sources: tuple[LongTermSource, ...]
    warnings: tuple[str, ...]


def validate_sec_user_agent(user_agent: str) -> str:
    """Require the descriptive contact form requested by SEC fair-access rules."""

    clean = str(user_agent or "").strip()
    if len(clean) < 8 or "@" not in clean or not any(character.isspace() for character in clean):
        raise ValueError(
            "SEC_USER_AGENT muss einen Namen und eine Kontaktadresse enthalten und darf nicht im Projekt gespeichert werden."
        )
    if "\r" in clean or "\n" in clean:
        raise ValueError("SEC_USER_AGENT enthält unzulässige Zeilenumbrüche.")
    return clean


def load_sec_json(url: str, user_agent: str) -> object:
    """Load one bounded public SEC JSON document with a declared user agent."""

    clean_agent = validate_sec_user_agent(user_agent)
    if not (
        url == SEC_TICKER_MAP_URL
        or url.startswith("https://data.sec.gov/submissions/CIK")
        or url.startswith("https://data.sec.gov/api/xbrl/companyfacts/CIK")
    ):
        raise ValueError("Nicht zugelassene SEC-JSON-Adresse.")
    request = Request(
        url,
        headers={
            "User-Agent": clean_agent,
            "Accept": "application/json",
        },
        method="GET",
    )
    payload: bytes | None = None
    for attempt in range(SEC_MAX_ATTEMPTS):
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read(SEC_MAX_RESPONSE_BYTES + 1)
            break
        except HTTPError as exc:
            retryable = exc.code in SEC_RETRYABLE_STATUS_CODES and attempt < SEC_MAX_ATTEMPTS - 1
            if not retryable:
                raise SecSourceError(f"SEC-Daten konnten nicht geladen werden: HTTP {exc.code}.") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
            try:
                delay = float(retry_after) if retry_after is not None else SEC_RETRY_BACKOFF_SECONDS[attempt]
            except (TypeError, ValueError):
                delay = SEC_RETRY_BACKOFF_SECONDS[attempt]
            time.sleep(min(max(delay, 0.1), 5.0))
        except (URLError, TimeoutError, OSError) as exc:
            if attempt >= SEC_MAX_ATTEMPTS - 1:
                raise SecSourceError(
                    f"SEC-Daten konnten nach {SEC_MAX_ATTEMPTS} Versuchen nicht geladen werden: "
                    f"{type(exc).__name__}."
                ) from exc
            time.sleep(SEC_RETRY_BACKOFF_SECONDS[attempt])
    if payload is None:
        raise SecSourceError("SEC-Daten konnten nach begrenzten Versuchen nicht geladen werden.")
    if len(payload) > SEC_MAX_RESPONSE_BYTES:
        raise SecSourceError("SEC-Antwort überschreitet die zulässige Größe.")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecSourceError("SEC-Antwort enthält kein gültiges UTF-8-JSON.") from exc


class SecFairAccessClient:
    """Serialize SEC requests, pace starts, and reuse the ticker map in one process.

    The user agent remains memory-only. The ticker map is copied at the public
    boundary so callers cannot alter the shared cached value.
    """

    def __init__(
        self,
        user_agent: str,
        *,
        loader: SecJsonLoader = load_sec_json,
        minimum_interval_seconds: float = 0.12,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self._user_agent = validate_sec_user_agent(user_agent)
        interval = float(minimum_interval_seconds)
        if not 0.1 <= interval <= 5.0:
            raise ValueError("SEC-Anfrageintervall muss zwischen 0,1 und 5 Sekunden liegen.")
        self._loader = loader
        self._minimum_interval_seconds = interval
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_started_at: float | None = None
        self._ticker_map_cache: object | None = None
        self._lock = Lock()

    def __call__(self, url: str, user_agent: str) -> object:
        if validate_sec_user_agent(user_agent) != self._user_agent:
            raise ValueError("SEC-Client darf nicht mit einer anderen Kontaktkennung wiederverwendet werden.")
        with self._lock:
            if url == SEC_TICKER_MAP_URL and self._ticker_map_cache is not None:
                return deepcopy(self._ticker_map_cache)

            now = self._clock()
            if self._last_request_started_at is not None:
                elapsed = now - self._last_request_started_at
                remaining = self._minimum_interval_seconds - elapsed
                if remaining > 0:
                    self._sleeper(remaining)
                    now = self._clock()
            self._last_request_started_at = now
            payload = self._loader(url, self._user_agent)
            if url == SEC_TICKER_MAP_URL:
                self._ticker_map_cache = deepcopy(payload)
                return deepcopy(payload)
            return payload


def _ticker_record(payload: object, ticker: str) -> tuple[int, str] | None:
    if not isinstance(payload, dict):
        raise SecSourceError("SEC-Tickerdatei besitzt kein JSON-Objekt.")
    fields = payload.get("fields")
    rows = payload.get("data")
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise SecSourceError("SEC-Tickerdatei enthält keine gültige Feld-/Datenstruktur.")
    indexes = {str(field): index for index, field in enumerate(fields)}
    required = {"cik", "name", "ticker"}
    if not required.issubset(indexes):
        raise SecSourceError("SEC-Tickerdatei enthält nicht alle Pflichtfelder.")
    for row in rows:
        if not isinstance(row, list) or len(row) <= max(indexes.values()):
            continue
        if str(row[indexes["ticker"]] or "").strip().upper() != ticker:
            continue
        try:
            cik = int(row[indexes["cik"]])
        except (TypeError, ValueError):
            raise SecSourceError("SEC-Tickertreffer enthält keine gültige CIK.")
        company_name = str(row[indexes["name"]] or "").strip()
        if cik <= 0 or not company_name:
            raise SecSourceError("SEC-Tickertreffer enthält unvollständige Unternehmensdaten.")
        return cik, company_name
    return None


def _recent_filing_rows(payload: object) -> tuple[dict[str, object], ...]:
    if not isinstance(payload, dict):
        raise SecSourceError("SEC-Submissionsdatei besitzt kein JSON-Objekt.")
    filings = payload.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        raise SecSourceError("SEC-Submissionsdatei enthält keine aktuellen Einreichungen.")
    required_fields = ("accessionNumber", "filingDate", "form", "primaryDocument")
    columns = {field: recent.get(field) for field in required_fields}
    if not all(isinstance(values, list) for values in columns.values()):
        raise SecSourceError("SEC-Submissionsdatei enthält unvollständige Pflichtspalten.")
    row_count = min(len(values) for values in columns.values())
    return tuple(
        {field: columns[field][index] for field in required_fields}  # type: ignore[index]
        for index in range(row_count)
    )


def _source_from_filing(
    row: dict[str, object],
    *,
    cik: int,
    company_name: str,
    accessed_at: datetime,
) -> LongTermSource | None:
    form = str(row.get("form") or "").strip().upper()
    accession = str(row.get("accessionNumber") or "").strip()
    filing_date = str(row.get("filingDate") or "").strip()
    document = str(row.get("primaryDocument") or "").strip()
    if form not in SUPPORTED_FORMS:
        return None
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", filing_date):
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]+", document):
        return None
    accession_compact = accession.replace("-", "")
    document_url = SEC_ARCHIVE_DOCUMENT_URL.format(
        cik=cik,
        accession_without_dashes=accession_compact,
        document=document,
    )
    source_type = "annual_report" if form in ANNUAL_FORMS else "quarterly_report"
    purpose = (
        "Offizieller Jahresbericht für Geschäftsmodell, Risiken, Finanzqualität und Kapitalverwendung."
        if source_type == "annual_report"
        else "Offizieller Quartalsbericht für aktuelle Finanzqualität, Risiken und These-Veränderungen."
    )
    return LongTermSource(
        source_id=f"sec-{cik}-{accession_compact}-{form.lower()}",
        title=f"{company_name}: SEC {form} vom {filing_date}",
        url=document_url,
        publisher="U.S. Securities and Exchange Commission (SEC)",
        source_type=source_type,
        accessed_at=accessed_at.isoformat(),
        purpose=purpose,
        published_at=filing_date,
    )


def discover_sec_filing_sources(
    ticker: str,
    *,
    user_agent: str,
    json_loader: SecJsonLoader = load_sec_json,
    now: datetime | None = None,
    max_per_type: int = 2,
) -> SecFilingSourceDiscovery:
    """Discover recent official annual and quarterly filing sources for a US ticker.

    The adapter deliberately returns source metadata only. It never turns filing
    text into evidence statements and therefore cannot by itself open the
    long-term scoring gate.
    """

    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        raise ValueError("Ticker für SEC-Quellensuche fehlt.")
    clean_agent = validate_sec_user_agent(user_agent)
    if isinstance(max_per_type, bool) or not isinstance(max_per_type, int) or max_per_type < 1 or max_per_type > 5:
        raise ValueError("SEC-Quellensuche erlaubt ein bis fünf Dokumente je Berichtstyp.")
    accessed_at = now or datetime.now(timezone.utc)
    if accessed_at.tzinfo is None or accessed_at.utcoffset() is None:
        raise ValueError("SEC-Prüfzeitpunkt benötigt eine Zeitzone.")
    accessed_at = accessed_at.astimezone(timezone.utc)

    mapping_payload = json_loader(SEC_TICKER_MAP_URL, clean_agent)
    record = _ticker_record(mapping_payload, clean_ticker)
    if record is None:
        return SecFilingSourceDiscovery(
            adapter_version=SEC_SOURCE_ADAPTER_VERSION,
            available=False,
            ticker=clean_ticker,
            cik=None,
            company_name=None,
            status="Kein eindeutiger SEC-Ticker-/CIK-Treffer; keine offizielle US-Filingquelle übernommen.",
            sources=(),
            warnings=("Nicht-US-Unternehmen oder abweichende SEC-Ticker können einen anderen Quellenadapter benötigen.",),
        )

    cik, company_name = record
    submissions_payload = json_loader(SEC_SUBMISSIONS_URL.format(cik=cik), clean_agent)
    rows = _recent_filing_rows(submissions_payload)
    candidates: list[LongTermSource] = []
    warnings: list[str] = []
    counts = {"annual_report": 0, "quarterly_report": 0}
    for row in rows:
        source = _source_from_filing(
            row,
            cik=cik,
            company_name=company_name,
            accessed_at=accessed_at,
        )
        if source is None:
            continue
        if counts[source.source_type] >= max_per_type:
            continue
        validation_issues = source_validation_issues(source)
        freshness_issues = source_freshness_issues(source, as_of=accessed_at)
        if validation_issues or freshness_issues:
            warnings.append(
                f"{source.title} nicht übernommen: {' '.join((*validation_issues, *freshness_issues))}"
            )
            continue
        candidates.append(source)
        counts[source.source_type] += 1

    available = bool(candidates)
    status = (
        f"{len(candidates)} aktuelle offizielle SEC-Filingquelle(n) gefunden; noch keine Aussagen abgeleitet."
        if available
        else "SEC-Unternehmen gefunden, aber keine aktuelle unterstützte 10-K/20-F/40-F/10-Q-Quelle verfügbar."
    )
    return SecFilingSourceDiscovery(
        adapter_version=SEC_SOURCE_ADAPTER_VERSION,
        available=available,
        ticker=clean_ticker,
        cik=cik,
        company_name=company_name,
        status=status,
        sources=tuple(candidates),
        warnings=tuple(dict.fromkeys(warnings)),
    )
