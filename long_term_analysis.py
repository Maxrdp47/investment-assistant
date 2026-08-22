from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlparse


LONG_TERM_MODEL_TYPE = "long_term_analysis"
LONG_TERM_MODEL_VERSION = "2026.08.02-evidence-v2"
ENTRY_TIMING_SECTION = "entry_timing"
SOURCE_FUTURE_TOLERANCE = timedelta(minutes=5)

SOURCE_MAX_AGE_DAYS: dict[str, int] = {
    "company_official": 365,
    "regulatory_filing": 550,
    "annual_report": 550,
    "quarterly_report": 190,
    "investor_presentation": 550,
    "earnings_call": 190,
    "government_data": 730,
    "industry_research": 1_095,
    "exchange_data": 7,
    "market_data": 7,
    "yahoo_finance": 7,
    "news": 30,
    "other": 365,
}

PRIMARY_SOURCE_TYPES = frozenset(
    {
        "company_official",
        "regulatory_filing",
        "annual_report",
        "quarterly_report",
        "investor_presentation",
        "earnings_call",
    }
)
INDEPENDENT_SOURCE_TYPES = frozenset(
    {
        "government_data",
        "industry_research",
        "exchange_data",
    }
)
QUALIFIED_SOURCE_TYPES = PRIMARY_SOURCE_TYPES | INDEPENDENT_SOURCE_TYPES | {"market_data"}
CONTEXT_ONLY_SOURCE_TYPES = frozenset({"yahoo_finance", "news", "other"})
KNOWN_SOURCE_TYPES = QUALIFIED_SOURCE_TYPES | CONTEXT_ONLY_SOURCE_TYPES


@dataclass(frozen=True)
class LongTermSource:
    source_id: str
    title: str
    url: str
    publisher: str
    source_type: str
    accessed_at: str
    purpose: str
    published_at: str | None = None


@dataclass(frozen=True)
class LongTermEvidence:
    section: str
    statement: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class LongTermSectionRequirement:
    label: str
    minimum_qualified_sources: int = 1
    requires_primary_source: bool = False
    requires_independent_source: bool = False


@dataclass(frozen=True)
class LongTermSectionStatus:
    section: str
    label: str
    ready: bool
    source_ids: tuple[str, ...]
    gaps: tuple[str, ...]


@dataclass(frozen=True)
class LongTermReadinessReport:
    model_type: str
    model_version: str
    ready: bool
    status: str
    covered_sections: tuple[str, ...]
    missing_sections: tuple[str, ...]
    section_statuses: tuple[LongTermSectionStatus, ...]
    referenced_source_count: int
    qualified_source_count: int
    primary_source_count: int
    independent_source_count: int
    invalid_source_ids: tuple[str, ...]
    stale_source_ids: tuple[str, ...]
    future_source_ids: tuple[str, ...]
    unresolved_source_ids: tuple[str, ...]
    warnings: tuple[str, ...]


LONG_TERM_SECTION_REQUIREMENTS: dict[str, LongTermSectionRequirement] = {
    "business_model": LongTermSectionRequirement(
        "Geschäftsmodell, Produkte und Kundengruppen",
        requires_primary_source=True,
    ),
    "revenue_model": LongTermSectionRequirement(
        "Umsatz- und Gewinnquellen",
        requires_primary_source=True,
    ),
    "market_opportunity": LongTermSectionRequirement(
        "Marktgröße und strukturelles Wachstum",
        requires_independent_source=True,
    ),
    "competitive_position": LongTermSectionRequirement(
        "Wettbewerb, Marktstellung und Skalierbarkeit",
        minimum_qualified_sources=2,
        requires_primary_source=True,
        requires_independent_source=True,
    ),
    "management_capital_allocation": LongTermSectionRequirement(
        "Management, Kapitalverwendung und Verwässerung",
        requires_primary_source=True,
    ),
    "financial_quality": LongTermSectionRequirement(
        "Fundamentaldaten, Cashflow und Bilanzqualität",
        requires_primary_source=True,
    ),
    "valuation": LongTermSectionRequirement(
        "Bewertung und eingepreiste Erwartungen",
    ),
    "long_term_risks": LongTermSectionRequirement(
        "Langfristige Risiken und Kapitalverlustgefahr",
        requires_primary_source=True,
    ),
    "scenarios": LongTermSectionRequirement(
        "Bull-, Basis- und Bear-Szenarien",
        minimum_qualified_sources=2,
    ),
    "thesis_conditions": LongTermSectionRequirement(
        "Bedingungen und Widerlegung der Investmentthese",
        minimum_qualified_sources=2,
    ),
}


def _clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parsed_timestamp(value: str | None, *, require_timezone: bool) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if require_timezone and (parsed.tzinfo is None or parsed.utcoffset() is None):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _valid_timestamp(value: str | None, *, required: bool, require_timezone: bool = False) -> bool:
    if value is None or not str(value).strip():
        return not required
    return _parsed_timestamp(value, require_timezone=require_timezone) is not None


def source_validation_issues(source: LongTermSource) -> tuple[str, ...]:
    issues: list[str] = []
    if not _clean_text(source.source_id):
        issues.append("Quellen-ID fehlt.")
    if not _clean_text(source.title):
        issues.append("Quellentitel fehlt.")
    if not _clean_text(source.publisher):
        issues.append("Herausgeber fehlt.")
    if not _clean_text(source.purpose):
        issues.append("Verwendungszweck fehlt.")
    if source.source_type not in KNOWN_SOURCE_TYPES:
        issues.append("Quellentyp ist nicht zugelassen.")
    parsed_url = urlparse(_clean_text(source.url))
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        issues.append("Quelle benötigt eine vollständige HTTP(S)-Adresse.")
    if not _valid_timestamp(source.accessed_at, required=True, require_timezone=True):
        issues.append("Abrufzeitpunkt fehlt, ist ungültig oder besitzt keine Zeitzone.")
    if not _valid_timestamp(source.published_at, required=False):
        issues.append("Veröffentlichungszeitpunkt ist ungültig.")
    return tuple(issues)


def source_freshness_issues(
    source: LongTermSource,
    *,
    as_of: datetime | None = None,
) -> tuple[str, ...]:
    """Return explicit time-consistency and source-age issues.

    Publication time is authoritative when present. A recent download therefore
    cannot make an old report current. For rolling market/context data without a
    publication date, the access time is used as the conservative fallback.
    """

    reference_time = as_of or datetime.now(timezone.utc)
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("Prüfzeitpunkt für Long-Term-Quellen benötigt eine Zeitzone.")
    reference_time = reference_time.astimezone(timezone.utc)
    accessed_at = _parsed_timestamp(source.accessed_at, require_timezone=True)
    published_at = _parsed_timestamp(source.published_at, require_timezone=False)
    if accessed_at is None:
        return ()

    issues: list[str] = []
    if accessed_at > reference_time + SOURCE_FUTURE_TOLERANCE:
        issues.append("Abrufzeitpunkt liegt unzulässig in der Zukunft.")
    if published_at is not None and published_at > reference_time + timedelta(days=1):
        issues.append("Veröffentlichungszeitpunkt liegt unzulässig in der Zukunft.")

    freshness_time = published_at or accessed_at
    maximum_age = SOURCE_MAX_AGE_DAYS.get(source.source_type)
    if maximum_age is not None and freshness_time < reference_time - timedelta(days=maximum_age):
        basis = "Veröffentlichung" if published_at is not None else "Abruf"
        issues.append(
            f"Quelle ist veraltet: {basis} älter als {maximum_age} Tage für Typ {source.source_type}."
        )
    return tuple(issues)


def assess_long_term_readiness(
    sources: Iterable[LongTermSource],
    evidence: Iterable[LongTermEvidence],
    *,
    as_of: datetime | None = None,
) -> LongTermReadinessReport:
    """Check whether a source-based long-term synthesis is safe to build.

    The function deliberately does not calculate an investment score. It only
    verifies provenance and minimum coverage. Technical entry evidence is kept
    outside the long-term gate and therefore cannot improve long-term readiness.
    """

    source_items = tuple(sources)
    evidence_items = tuple(evidence)
    source_ids = [_clean_text(item.source_id) for item in source_items if _clean_text(item.source_id)]
    duplicate_ids = {source_id for source_id in source_ids if source_ids.count(source_id) > 1}

    valid_sources: dict[str, LongTermSource] = {}
    invalid_source_ids: set[str] = set(duplicate_ids)
    stale_source_ids: set[str] = set()
    future_source_ids: set[str] = set()
    warnings: list[str] = []
    for source in source_items:
        source_id = _clean_text(source.source_id)
        validation_issues = source_validation_issues(source)
        freshness_issues = source_freshness_issues(source, as_of=as_of) if not validation_issues else ()
        issues = (*validation_issues, *freshness_issues)
        if any("veraltet" in issue for issue in freshness_issues):
            stale_source_ids.add(source_id or "<ohne-id>")
        if any("Zukunft" in issue for issue in freshness_issues):
            future_source_ids.add(source_id or "<ohne-id>")
        if source_id in duplicate_ids:
            issues = (*issues, "Quellen-ID ist nicht eindeutig.")
        if issues:
            invalid_source_ids.add(source_id or "<ohne-id>")
            warnings.append(f"Quelle {source_id or '<ohne-id>'}: {' '.join(issues)}")
            continue
        valid_sources[source_id] = source

    evidence_by_section: dict[str, list[LongTermEvidence]] = {
        section: [] for section in LONG_TERM_SECTION_REQUIREMENTS
    }
    unresolved_source_ids: set[str] = set()
    for item in evidence_items:
        section = _clean_text(item.section)
        if section == ENTRY_TIMING_SECTION:
            continue
        if section not in LONG_TERM_SECTION_REQUIREMENTS:
            warnings.append(f"Unbekannter Long-Term-Bereich ignoriert: {section or '<leer>'}.")
            continue
        if not _clean_text(item.statement):
            warnings.append(
                f"Leere Aussage im Bereich {LONG_TERM_SECTION_REQUIREMENTS[section].label} ignoriert."
            )
            continue
        normalized_ids = tuple(
            dict.fromkeys(
                _clean_text(source_id)
                for source_id in (item.source_ids or ())
                if _clean_text(source_id)
            )
        )
        for source_id in normalized_ids:
            if source_id not in valid_sources:
                unresolved_source_ids.add(source_id)
        evidence_by_section[section].append(
            LongTermEvidence(section=section, statement=_clean_text(item.statement), source_ids=normalized_ids)
        )

    section_statuses: list[LongTermSectionStatus] = []
    all_referenced_ids: set[str] = set()
    for section, requirement in LONG_TERM_SECTION_REQUIREMENTS.items():
        cited_ids = {
            source_id
            for item in evidence_by_section[section]
            for source_id in item.source_ids
            if source_id in valid_sources
        }
        all_referenced_ids.update(cited_ids)
        qualified_ids = {
            source_id
            for source_id in cited_ids
            if valid_sources[source_id].source_type in QUALIFIED_SOURCE_TYPES
        }
        primary_ids = {
            source_id
            for source_id in cited_ids
            if valid_sources[source_id].source_type in PRIMARY_SOURCE_TYPES
        }
        independent_ids = {
            source_id
            for source_id in cited_ids
            if valid_sources[source_id].source_type in INDEPENDENT_SOURCE_TYPES
        }

        gaps: list[str] = []
        if not evidence_by_section[section]:
            gaps.append("Keine prüfbare Aussage vorhanden.")
        if len(qualified_ids) < requirement.minimum_qualified_sources:
            gaps.append(
                f"Mindestens {requirement.minimum_qualified_sources} belastbare Quelle(n) erforderlich."
            )
        if requirement.requires_primary_source and not primary_ids:
            gaps.append("Mindestens eine offizielle Primärquelle erforderlich.")
        if requirement.requires_independent_source and not independent_ids:
            gaps.append("Mindestens eine unabhängige belastbare Quelle erforderlich.")
        context_only_ids = cited_ids - qualified_ids
        if context_only_ids:
            warnings.append(
                f"{requirement.label}: Kontextquelle(n) {', '.join(sorted(context_only_ids))} "
                "zählen nicht als Long-Term-Beleg."
            )

        section_statuses.append(
            LongTermSectionStatus(
                section=section,
                label=requirement.label,
                ready=not gaps,
                source_ids=tuple(sorted(cited_ids)),
                gaps=tuple(gaps),
            )
        )

    covered_sections = tuple(status.section for status in section_statuses if status.ready)
    missing_sections = tuple(status.section for status in section_statuses if not status.ready)
    referenced_sources = [valid_sources[source_id] for source_id in sorted(all_referenced_ids)]
    qualified_source_count = sum(
        source.source_type in QUALIFIED_SOURCE_TYPES for source in referenced_sources
    )
    primary_source_count = sum(
        source.source_type in PRIMARY_SOURCE_TYPES for source in referenced_sources
    )
    independent_source_count = sum(
        source.source_type in INDEPENDENT_SOURCE_TYPES for source in referenced_sources
    )
    ready = not missing_sections
    status = (
        "Quellenbasis vollständig; eine getrennte Long-Term-Synthese darf erstellt werden."
        if ready
        else "Datenbasis unvollständig; keine Long-Term-Bewertung oder Empfehlung erzeugen."
    )

    return LongTermReadinessReport(
        model_type=LONG_TERM_MODEL_TYPE,
        model_version=LONG_TERM_MODEL_VERSION,
        ready=ready,
        status=status,
        covered_sections=covered_sections,
        missing_sections=missing_sections,
        section_statuses=tuple(section_statuses),
        referenced_source_count=len(referenced_sources),
        qualified_source_count=qualified_source_count,
        primary_source_count=primary_source_count,
        independent_source_count=independent_source_count,
        invalid_source_ids=tuple(sorted(invalid_source_ids)),
        stale_source_ids=tuple(sorted(stale_source_ids)),
        future_source_ids=tuple(sorted(future_source_ids)),
        unresolved_source_ids=tuple(sorted(unresolved_source_ids)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
