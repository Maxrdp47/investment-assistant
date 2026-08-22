from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from long_term_analysis import LongTermEvidence, LongTermSource


SEC_FINANCIAL_FACTS_MODEL_VERSION = "2026.08.02-sec-facts-v1"
ANNUAL_SEC_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})


@dataclass(frozen=True)
class SecMetricDefinition:
    label: str
    concepts: tuple[str, ...]
    unit: str


SEC_METRIC_DEFINITIONS: dict[str, SecMetricDefinition] = {
    "revenue": SecMetricDefinition(
        "Umsatz",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
        "USD",
    ),
    "net_income": SecMetricDefinition("Nettoergebnis", ("NetIncomeLoss",), "USD"),
    "operating_cashflow": SecMetricDefinition(
        "Operativer Cashflow",
        ("NetCashProvidedByUsedInOperatingActivities",),
        "USD",
    ),
    "assets": SecMetricDefinition("Vermögenswerte", ("Assets",), "USD"),
    "liabilities": SecMetricDefinition("Verbindlichkeiten", ("Liabilities",), "USD"),
    "cash": SecMetricDefinition(
        "Zahlungsmittel",
        ("CashAndCashEquivalentsAtCarryingValue",),
        "USD",
    ),
}


@dataclass(frozen=True)
class SecFinancialFact:
    metric: str
    label: str
    taxonomy: str
    concept: str
    unit: str
    value: float
    period_start: str | None
    period_end: str
    filed_at: str
    accession_number: str
    form: str
    fiscal_year: int | None


@dataclass(frozen=True)
class SecFinancialFactsSnapshot:
    model_version: str
    available: bool
    cik: int | None
    entity_name: str | None
    status: str
    facts: tuple[SecFinancialFact, ...]
    missing_metrics: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SecFinancialEvidenceResult:
    evidence: tuple[LongTermEvidence, ...]
    unresolved_accessions: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SecFinancialTrend:
    metric: str
    label: str
    previous: SecFinancialFact
    current: SecFinancialFact
    change_pct: float | None


@dataclass(frozen=True)
class SecFinancialTrendSnapshot:
    available: bool
    trends: tuple[SecFinancialTrend, ...]
    missing_metrics: tuple[str, ...]
    warnings: tuple[str, ...]


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fact_candidate(
    item: object,
    *,
    metric: str,
    definition: SecMetricDefinition,
    concept: str,
    as_of_date: date,
) -> SecFinancialFact | None:
    if not isinstance(item, dict):
        return None
    form = str(item.get("form") or "").strip().upper()
    accession = str(item.get("accn") or "").strip()
    filed_at = str(item.get("filed") or "").strip()
    period_end = str(item.get("end") or "").strip()
    filed_date = _iso_date(filed_at)
    end_date = _iso_date(period_end)
    value = _finite_number(item.get("val"))
    if form not in ANNUAL_SEC_FORMS or filed_date is None or end_date is None or value is None:
        return None
    if filed_date > as_of_date or end_date > as_of_date:
        return None
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
        return None
    fiscal_period = str(item.get("fp") or "").strip().upper()
    if fiscal_period and fiscal_period != "FY":
        return None
    fiscal_year: int | None = None
    try:
        fiscal_year = int(item.get("fy")) if item.get("fy") is not None else None
    except (TypeError, ValueError):
        fiscal_year = None
    period_start = str(item.get("start") or "").strip() or None
    if period_start is not None and _iso_date(period_start) is None:
        return None
    return SecFinancialFact(
        metric=metric,
        label=definition.label,
        taxonomy="us-gaap",
        concept=concept,
        unit=definition.unit,
        value=value,
        period_start=period_start,
        period_end=period_end,
        filed_at=filed_at,
        accession_number=accession,
        form=form,
        fiscal_year=fiscal_year,
    )


def _metric_candidates(
    us_gaap: dict,
    *,
    metric: str,
    definition: SecMetricDefinition,
    as_of_date: date,
) -> tuple[SecFinancialFact, ...]:
    for concept in definition.concepts:
        concept_payload = us_gaap.get(concept)
        units = concept_payload.get("units") if isinstance(concept_payload, dict) else None
        entries = units.get(definition.unit) if isinstance(units, dict) else None
        if not isinstance(entries, list):
            continue
        candidates = [
            candidate
            for item in entries
            if (
                candidate := _fact_candidate(
                    item,
                    metric=metric,
                    definition=definition,
                    concept=concept,
                    as_of_date=as_of_date,
                )
            )
            is not None
        ]
        if candidates:
            unique = {
                (item.period_end, item.accession_number): item
                for item in candidates
            }
            return tuple(
                sorted(unique.values(), key=lambda item: (item.period_end, item.filed_at), reverse=True)
            )
    return ()


def extract_latest_annual_sec_facts(
    payload: object,
    *,
    as_of: datetime | None = None,
) -> SecFinancialFactsSnapshot:
    reference_time = as_of or datetime.now(timezone.utc)
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("SEC-Fakten-Prüfzeitpunkt benötigt eine Zeitzone.")
    as_of_date = reference_time.astimezone(timezone.utc).date()
    if not isinstance(payload, dict):
        return SecFinancialFactsSnapshot(
            SEC_FINANCIAL_FACTS_MODEL_VERSION,
            False,
            None,
            None,
            "SEC-Company-Facts enthalten kein JSON-Objekt.",
            (),
            tuple(SEC_METRIC_DEFINITIONS),
            ("Keine auswertbare SEC-Faktenstruktur.",),
        )

    try:
        cik = int(payload.get("cik"))
    except (TypeError, ValueError):
        cik = None
    entity_name = str(payload.get("entityName") or "").strip() or None
    facts_root = payload.get("facts")
    us_gaap = facts_root.get("us-gaap") if isinstance(facts_root, dict) else None
    if cik is None or cik <= 0 or entity_name is None or not isinstance(us_gaap, dict):
        return SecFinancialFactsSnapshot(
            SEC_FINANCIAL_FACTS_MODEL_VERSION,
            False,
            cik if cik and cik > 0 else None,
            entity_name,
            "SEC-Company-Facts enthalten keine vollständige US-GAAP-Unternehmensstruktur.",
            (),
            tuple(SEC_METRIC_DEFINITIONS),
            ("CIK, Unternehmensname oder US-GAAP-Fakten fehlen.",),
        )

    selected: list[SecFinancialFact] = []
    missing: list[str] = []
    warnings: list[str] = []
    for metric, definition in SEC_METRIC_DEFINITIONS.items():
        candidates = _metric_candidates(
            us_gaap,
            metric=metric,
            definition=definition,
            as_of_date=as_of_date,
        )
        chosen = candidates[0] if candidates else None
        if chosen is None:
            missing.append(metric)
            warnings.append(f"{definition.label}: kein gültiger aktueller Jahreswert in SEC Company Facts.")
        else:
            selected.append(chosen)

    available = bool(selected)
    return SecFinancialFactsSnapshot(
        model_version=SEC_FINANCIAL_FACTS_MODEL_VERSION,
        available=available,
        cik=cik,
        entity_name=entity_name,
        status=(
            f"{len(selected)} strukturierte SEC-Jahreswerte verfügbar; keine Bewertung abgeleitet."
            if available
            else "Keine unterstützten strukturierten SEC-Jahreswerte verfügbar."
        ),
        facts=tuple(selected),
        missing_metrics=tuple(missing),
        warnings=tuple(warnings),
    )


def extract_annual_sec_financial_trends(
    payload: object,
    *,
    as_of: datetime | None = None,
) -> SecFinancialTrendSnapshot:
    reference_time = as_of or datetime.now(timezone.utc)
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("SEC-Trend-Prüfzeitpunkt benötigt eine Zeitzone.")
    as_of_date = reference_time.astimezone(timezone.utc).date()
    facts_root = payload.get("facts") if isinstance(payload, dict) else None
    us_gaap = facts_root.get("us-gaap") if isinstance(facts_root, dict) else None
    if not isinstance(us_gaap, dict):
        return SecFinancialTrendSnapshot(
            available=False,
            trends=(),
            missing_metrics=tuple(SEC_METRIC_DEFINITIONS),
            warnings=("Keine auswertbare US-GAAP-Struktur für Jahresvergleiche.",),
        )

    trends: list[SecFinancialTrend] = []
    missing: list[str] = []
    warnings: list[str] = []
    for metric, definition in SEC_METRIC_DEFINITIONS.items():
        candidates = _metric_candidates(
            us_gaap,
            metric=metric,
            definition=definition,
            as_of_date=as_of_date,
        )
        if len(candidates) < 2:
            missing.append(metric)
            warnings.append(f"{definition.label}: weniger als zwei gültige Jahreswerte verfügbar.")
            continue
        current, previous = candidates[0], candidates[1]
        change_pct = (
            (current.value / previous.value - 1.0) * 100.0
            if previous.value > 0.0
            else None
        )
        trends.append(
            SecFinancialTrend(
                metric=metric,
                label=definition.label,
                previous=previous,
                current=current,
                change_pct=change_pct,
            )
        )
    return SecFinancialTrendSnapshot(
        available=bool(trends),
        trends=tuple(trends),
        missing_metrics=tuple(missing),
        warnings=tuple(warnings),
    )


def build_sec_financial_trend_evidence(
    snapshot: SecFinancialTrendSnapshot,
    filing_sources: Iterable[LongTermSource],
) -> SecFinancialEvidenceResult:
    sources = tuple(filing_sources)
    evidence: list[LongTermEvidence] = []
    unresolved_accessions: set[str] = set()
    for trend in snapshot.trends:
        source_ids: list[str] = []
        for fact in (trend.previous, trend.current):
            compact = fact.accession_number.replace("-", "")
            matches = [
                source.source_id
                for source in sources
                if source.source_type == "annual_report"
                and source.publisher == "U.S. Securities and Exchange Commission (SEC)"
                and compact in source.url
            ]
            if not matches:
                unresolved_accessions.add(fact.accession_number)
            source_ids.extend(matches)
        if any(
            fact.accession_number in unresolved_accessions
            for fact in (trend.previous, trend.current)
        ):
            continue
        change_text = (
            f"; rechnerische Veränderung {trend.change_pct:+.2f} %"
            if trend.change_pct is not None
            else "; keine Prozentänderung berechnet, weil der Vorjahreswert nicht positiv ist"
        )
        evidence.append(
            LongTermEvidence(
                section="financial_quality",
                statement=(
                    f"{trend.label}: {trend.previous.value:,.2f} {trend.previous.unit} "
                    f"zum {trend.previous.period_end} und {trend.current.value:,.2f} "
                    f"{trend.current.unit} zum {trend.current.period_end}{change_text}."
                ),
                source_ids=tuple(dict.fromkeys(source_ids)),
            )
        )
    warnings = (
        (
            "Mindestens eine Filing-Dokumentquelle für den SEC-Jahresvergleich fehlt; "
            "der betroffene Vergleich wurde nicht als Evidenz übernommen."
        ),
    ) if unresolved_accessions else ()
    return SecFinancialEvidenceResult(
        evidence=tuple(evidence),
        unresolved_accessions=tuple(sorted(unresolved_accessions)),
        warnings=warnings,
    )


def build_sec_financial_evidence(
    snapshot: SecFinancialFactsSnapshot,
    filing_sources: Iterable[LongTermSource],
) -> SecFinancialEvidenceResult:
    sources = tuple(filing_sources)
    evidence: list[LongTermEvidence] = []
    unresolved_accessions: set[str] = set()
    warnings: list[str] = []
    for fact in snapshot.facts:
        accession_compact = fact.accession_number.replace("-", "")
        matching_ids = tuple(
            source.source_id
            for source in sources
            if source.source_type == "annual_report"
            and source.publisher == "U.S. Securities and Exchange Commission (SEC)"
            and accession_compact in source.url
        )
        if not matching_ids:
            unresolved_accessions.add(fact.accession_number)
            continue
        value_text = f"{fact.value:,.2f} {fact.unit}"
        statement = (
            f"{fact.label}: {value_text} zum Zeitraumende {fact.period_end}, "
            f"gemeldet am {fact.filed_at} in {fact.form}; SEC-XBRL-Konzept {fact.concept}."
        )
        evidence.append(
            LongTermEvidence(
                section="financial_quality",
                statement=statement,
                source_ids=tuple(dict.fromkeys(matching_ids)),
            )
        )
    if unresolved_accessions:
        warnings.append(
            "Für strukturierte SEC-Fakten fehlt die passend entdeckte Filing-Dokumentquelle; "
            "daraus wurde keine Evidenz erzeugt."
        )
    return SecFinancialEvidenceResult(
        evidence=tuple(evidence),
        unresolved_accessions=tuple(sorted(unresolved_accessions)),
        warnings=tuple(warnings),
    )
