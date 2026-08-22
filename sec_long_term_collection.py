from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from long_term_analysis import (
    LongTermEvidence,
    LongTermReadinessReport,
    LongTermSource,
    assess_long_term_readiness,
)
from sec_filing_sources import (
    SEC_COMPANY_FACTS_URL,
    SecFairAccessClient,
    SecFilingSourceDiscovery,
    SecJsonLoader,
    SecSourceError,
    discover_sec_filing_sources,
)
from sec_financial_facts import (
    SecFinancialFactsSnapshot,
    build_sec_financial_evidence,
    build_sec_financial_trend_evidence,
    extract_annual_sec_financial_trends,
    extract_latest_annual_sec_facts,
)
from sec_json_cache import DEFAULT_SEC_JSON_CACHE_DIR, SecCachedJsonClient


SEC_LONG_TERM_COLLECTION_VERSION = "2026.08.02-sec-collection-v1"


@dataclass(frozen=True)
class SecLongTermCollectionResult:
    collection_version: str
    ticker: str
    available: bool
    status: str
    source_discovery: SecFilingSourceDiscovery
    financial_snapshot: SecFinancialFactsSnapshot | None
    sources: tuple[LongTermSource, ...]
    evidence: tuple[LongTermEvidence, ...]
    readiness: LongTermReadinessReport
    warnings: tuple[str, ...]


def build_cached_sec_loader(
    user_agent: str,
    *,
    cache_dir: Path = DEFAULT_SEC_JSON_CACHE_DIR,
) -> SecJsonLoader:
    fair_access = SecFairAccessClient(user_agent)
    return SecCachedJsonClient(fair_access, cache_dir=cache_dir)


def collect_sec_long_term_context(
    ticker: str,
    *,
    user_agent: str,
    json_loader: SecJsonLoader | None = None,
    now: datetime | None = None,
) -> SecLongTermCollectionResult:
    """Collect source-linked SEC financial evidence without scoring or writing.

    The result is intentionally expected to remain not ready: SEC filings can
    cover official company and financial facts, but independent market and
    competition evidence and the other required sections must come from
    separate adapters.
    """

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("SEC-Sammelzeitpunkt benötigt eine Zeitzone.")
    reference_time = reference_time.astimezone(timezone.utc)
    loader = json_loader or build_cached_sec_loader(user_agent)
    discovery = discover_sec_filing_sources(
        ticker,
        user_agent=user_agent,
        json_loader=loader,
        now=reference_time,
    )
    if not discovery.available or discovery.cik is None:
        readiness = assess_long_term_readiness(discovery.sources, (), as_of=reference_time)
        return SecLongTermCollectionResult(
            collection_version=SEC_LONG_TERM_COLLECTION_VERSION,
            ticker=discovery.ticker,
            available=False,
            status=discovery.status,
            source_discovery=discovery,
            financial_snapshot=None,
            sources=discovery.sources,
            evidence=(),
            readiness=readiness,
            warnings=discovery.warnings,
        )

    warnings = list(discovery.warnings)
    try:
        company_facts_payload = loader(
            SEC_COMPANY_FACTS_URL.format(cik=discovery.cik),
            user_agent,
        )
        financial_snapshot = extract_latest_annual_sec_facts(
            company_facts_payload,
            as_of=reference_time,
        )
        evidence_result = build_sec_financial_evidence(financial_snapshot, discovery.sources)
        trend_snapshot = extract_annual_sec_financial_trends(
            company_facts_payload,
            as_of=reference_time,
        )
        trend_evidence_result = build_sec_financial_trend_evidence(
            trend_snapshot,
            discovery.sources,
        )
        evidence = (*evidence_result.evidence, *trend_evidence_result.evidence)
        warnings.extend(financial_snapshot.warnings)
        warnings.extend(evidence_result.warnings)
        warnings.extend(trend_snapshot.warnings)
        warnings.extend(trend_evidence_result.warnings)
    except SecSourceError as exc:
        financial_snapshot = None
        evidence = ()
        warnings.append(str(exc))

    readiness = assess_long_term_readiness(discovery.sources, evidence, as_of=reference_time)
    warnings.extend(readiness.warnings)
    available = bool(discovery.sources or evidence)
    status = (
        f"SEC-Kontext gesammelt: {len(discovery.sources)} Filingquelle(n), "
        f"{len(evidence)} belegte Finanzangabe(n); Long-Term-Gesamtfreigabe bleibt getrennt."
        if available
        else "Keine verwendbare SEC-Quelle oder verknüpfte Finanzangabe verfügbar."
    )
    return SecLongTermCollectionResult(
        collection_version=SEC_LONG_TERM_COLLECTION_VERSION,
        ticker=discovery.ticker,
        available=available,
        status=status,
        source_discovery=discovery,
        financial_snapshot=financial_snapshot,
        sources=discovery.sources,
        evidence=evidence,
        readiness=readiness,
        warnings=tuple(dict.fromkeys(warnings)),
    )
