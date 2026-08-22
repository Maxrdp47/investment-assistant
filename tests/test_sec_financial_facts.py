from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from long_term_analysis import LongTermSource
from sec_financial_facts import (
    SEC_METRIC_DEFINITIONS,
    build_sec_financial_evidence,
    build_sec_financial_trend_evidence,
    extract_annual_sec_financial_trends,
    extract_latest_annual_sec_facts,
)


NOW = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)


def entry(value: object, *, end: str, filed: str, form: str = "10-K", accn: str = "0001045810-26-000001") -> dict:
    return {
        "start": f"{int(end[:4]) - 1}-02-01",
        "end": end,
        "val": value,
        "accn": accn,
        "fy": int(end[:4]),
        "fp": "FY",
        "form": form,
        "filed": filed,
    }


def company_facts_payload() -> dict:
    facts: dict[str, dict] = {}
    for definition in SEC_METRIC_DEFINITIONS.values():
        concept = definition.concepts[0]
        facts[concept] = {
            "units": {
                "USD": [
                    entry(90.0, end="2024-01-31", filed="2024-03-01", accn="0001045810-24-000001"),
                    entry(100.0, end="2025-01-31", filed="2025-03-01", accn="0001045810-25-000001"),
                    entry(120.0, end="2026-01-31", filed="2026-03-01"),
                    entry(999.0, end="2026-04-30", filed="2026-05-20", form="10-Q"),
                    entry(777.0, end="2027-01-31", filed="2027-03-01"),
                ]
            }
        }
    return {"cik": 1045810, "entityName": "NVIDIA CORP", "facts": {"us-gaap": facts}}


def filing_source(accession: str = "0001045810-26-000001") -> LongTermSource:
    compact = accession.replace("-", "")
    return LongTermSource(
        source_id=f"sec-1045810-{compact}-10-k",
        title="NVIDIA CORP: SEC 10-K",
        url=f"https://www.sec.gov/Archives/edgar/data/1045810/{compact}/nvda-202610k.htm",
        publisher="U.S. Securities and Exchange Commission (SEC)",
        source_type="annual_report",
        accessed_at=NOW.isoformat(),
        purpose="Finanzqualität",
        published_at="2026-03-01",
    )


def test_extracts_latest_completed_annual_values_and_ignores_quarterly_or_future_rows() -> None:
    payload = company_facts_payload()
    before = deepcopy(payload)

    snapshot = extract_latest_annual_sec_facts(payload, as_of=NOW)

    assert snapshot.available is True
    assert len(snapshot.facts) == len(SEC_METRIC_DEFINITIONS)
    assert all(fact.value == 120.0 for fact in snapshot.facts)
    assert all(fact.period_end == "2026-01-31" for fact in snapshot.facts)
    assert all(fact.form == "10-K" for fact in snapshot.facts)
    assert snapshot.missing_metrics == ()
    assert payload == before


def test_concept_priority_is_deterministic_instead_of_combining_duplicates() -> None:
    payload = company_facts_payload()
    payload["facts"]["us-gaap"]["Revenues"] = {
        "units": {"USD": [entry(500.0, end="2026-01-31", filed="2026-03-01")]}
    }

    snapshot = extract_latest_annual_sec_facts(payload, as_of=NOW)
    revenue = next(fact for fact in snapshot.facts if fact.metric == "revenue")

    assert revenue.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert revenue.value == 120.0


def test_non_finite_and_invalid_accession_values_remain_missing() -> None:
    payload = company_facts_payload()
    revenue_concept = SEC_METRIC_DEFINITIONS["revenue"].concepts[0]
    payload["facts"]["us-gaap"][revenue_concept]["units"]["USD"] = [
        entry(float("nan"), end="2026-01-31", filed="2026-03-01"),
        entry(120.0, end="2026-01-31", filed="2026-03-01", accn="../../bad"),
    ]

    snapshot = extract_latest_annual_sec_facts(payload, as_of=NOW)

    assert "revenue" in snapshot.missing_metrics
    assert all(fact.metric != "revenue" for fact in snapshot.facts)


def test_incomplete_payload_has_explicit_safe_empty_state() -> None:
    snapshot = extract_latest_annual_sec_facts({"cik": 1045810}, as_of=NOW)

    assert snapshot.available is False
    assert snapshot.facts == ()
    assert set(snapshot.missing_metrics) == set(SEC_METRIC_DEFINITIONS)
    assert snapshot.warnings


def test_facts_become_evidence_only_with_matching_official_filing_source() -> None:
    snapshot = extract_latest_annual_sec_facts(company_facts_payload(), as_of=NOW)

    result = build_sec_financial_evidence(snapshot, [filing_source()])

    assert len(result.evidence) == len(SEC_METRIC_DEFINITIONS)
    assert result.unresolved_accessions == ()
    assert all(item.section == "financial_quality" for item in result.evidence)
    assert all(item.source_ids == (filing_source().source_id,) for item in result.evidence)
    assert all("SEC-XBRL-Konzept" in item.statement for item in result.evidence)


def test_unmatched_or_non_sec_source_never_creates_financial_evidence() -> None:
    snapshot = extract_latest_annual_sec_facts(company_facts_payload(), as_of=NOW)
    wrong = filing_source("0001045810-25-000001")

    result = build_sec_financial_evidence(snapshot, [wrong])

    assert result.evidence == ()
    assert result.unresolved_accessions == ("0001045810-26-000001",)
    assert result.warnings


def test_two_annual_values_create_factual_trend_without_quality_judgment() -> None:
    payload = company_facts_payload()
    snapshot = extract_annual_sec_financial_trends(payload, as_of=NOW)
    sources = [
        filing_source("0001045810-25-000001"),
        filing_source("0001045810-26-000001"),
    ]

    result = build_sec_financial_trend_evidence(snapshot, sources)

    assert snapshot.available is True
    assert len(snapshot.trends) == len(SEC_METRIC_DEFINITIONS)
    assert all(trend.change_pct == pytest.approx(20.0) for trend in snapshot.trends)
    assert len(result.evidence) == len(SEC_METRIC_DEFINITIONS)
    assert all(len(item.source_ids) == 2 for item in result.evidence)
    assert all("rechnerische Veränderung +20.00 %" in item.statement for item in result.evidence)
    assert all("gut" not in item.statement.lower() for item in result.evidence)


def test_non_positive_previous_value_has_no_misleading_percentage() -> None:
    payload = company_facts_payload()
    concept = SEC_METRIC_DEFINITIONS["net_income"].concepts[0]
    payload["facts"]["us-gaap"][concept]["units"]["USD"][1]["val"] = -10.0

    snapshot = extract_annual_sec_financial_trends(payload, as_of=NOW)
    trend = next(item for item in snapshot.trends if item.metric == "net_income")

    assert trend.change_pct is None


def test_trend_needs_both_exact_filing_sources() -> None:
    snapshot = extract_annual_sec_financial_trends(company_facts_payload(), as_of=NOW)

    result = build_sec_financial_trend_evidence(snapshot, [filing_source()])

    assert result.evidence == ()
    assert result.unresolved_accessions == ("0001045810-25-000001",)
    assert result.warnings
