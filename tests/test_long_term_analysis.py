from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from long_term_analysis import (
    ENTRY_TIMING_SECTION,
    LONG_TERM_MODEL_TYPE,
    LONG_TERM_MODEL_VERSION,
    LONG_TERM_SECTION_REQUIREMENTS,
    LongTermEvidence,
    LongTermSource,
    assess_long_term_readiness,
    source_freshness_issues,
    source_validation_issues,
)


TEST_AS_OF = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)


def source(source_id: str, source_type: str, *, purpose: str = "Long-Term-Research") -> LongTermSource:
    return LongTermSource(
        source_id=source_id,
        title=f"Quelle {source_id}",
        url=f"https://example.com/{source_id}",
        publisher="Example Publisher",
        source_type=source_type,
        accessed_at="2026-08-02T18:00:00+02:00",
        purpose=purpose,
        published_at="2026-07-31",
    )


def complete_evidence() -> tuple[list[LongTermSource], list[LongTermEvidence]]:
    sources = [
        source("annual", "annual_report"),
        source("industry", "industry_research"),
        source("market", "market_data"),
    ]
    mapping = {
        "business_model": ("annual",),
        "revenue_model": ("annual",),
        "market_opportunity": ("industry",),
        "competitive_position": ("annual", "industry"),
        "management_capital_allocation": ("annual",),
        "financial_quality": ("annual",),
        "valuation": ("annual", "market"),
        "long_term_risks": ("annual",),
        "scenarios": ("annual", "industry"),
        "thesis_conditions": ("annual", "industry"),
    }
    evidence = [
        LongTermEvidence(section, f"Belegte Aussage für {section}.", source_ids)
        for section, source_ids in mapping.items()
    ]
    return sources, evidence


def test_empty_research_never_produces_a_ready_long_term_gate() -> None:
    report = assess_long_term_readiness([], [], as_of=TEST_AS_OF)

    assert report.ready is False
    assert report.model_type == LONG_TERM_MODEL_TYPE
    assert report.model_version == LONG_TERM_MODEL_VERSION
    assert report.covered_sections == ()
    assert set(report.missing_sections) == set(LONG_TERM_SECTION_REQUIREMENTS)
    assert "keine Long-Term-Bewertung" in report.status


def test_yahoo_only_context_cannot_support_long_term_claims() -> None:
    yahoo = source("yahoo", "yahoo_finance")
    evidence = [
        LongTermEvidence(section, "Aussage nur aus Yahoo.", ("yahoo",))
        for section in LONG_TERM_SECTION_REQUIREMENTS
    ]

    report = assess_long_term_readiness([yahoo], evidence, as_of=TEST_AS_OF)

    assert report.ready is False
    assert report.qualified_source_count == 0
    assert report.missing_sections == tuple(LONG_TERM_SECTION_REQUIREMENTS)
    assert any("zählen nicht als Long-Term-Beleg" in warning for warning in report.warnings)


def test_complete_primary_and_independent_evidence_is_ready_for_synthesis() -> None:
    sources, evidence = complete_evidence()

    report = assess_long_term_readiness(sources, evidence, as_of=TEST_AS_OF)

    assert report.ready is True
    assert report.missing_sections == ()
    assert report.covered_sections == tuple(LONG_TERM_SECTION_REQUIREMENTS)
    assert report.referenced_source_count == 3
    assert report.qualified_source_count == 3
    assert report.primary_source_count == 1
    assert report.independent_source_count == 1
    assert "darf erstellt werden" in report.status


def test_competitive_position_requires_primary_and_independent_view() -> None:
    sources, evidence = complete_evidence()
    evidence = [
        replace(item, source_ids=("annual",))
        if item.section == "competitive_position"
        else item
        for item in evidence
    ]

    report = assess_long_term_readiness(sources, evidence, as_of=TEST_AS_OF)
    status = next(item for item in report.section_statuses if item.section == "competitive_position")

    assert status.ready is False
    assert "Mindestens 2 belastbare Quelle(n) erforderlich." in status.gaps
    assert "Mindestens eine unabhängige belastbare Quelle erforderlich." in status.gaps


def test_missing_or_invalid_source_reference_stays_a_visible_gap() -> None:
    sources, evidence = complete_evidence()
    evidence = [
        replace(item, source_ids=("missing",)) if item.section == "business_model" else item
        for item in evidence
    ]

    report = assess_long_term_readiness(sources, evidence, as_of=TEST_AS_OF)

    assert report.ready is False
    assert report.unresolved_source_ids == ("missing",)
    assert "business_model" in report.missing_sections


def test_source_requires_provenance_timestamp_and_purpose() -> None:
    invalid = replace(
        source("broken", "annual_report"),
        url="not-a-url",
        accessed_at="yesterday",
        purpose="",
    )

    issues = source_validation_issues(invalid)

    assert "Verwendungszweck fehlt." in issues
    assert "Quelle benötigt eine vollständige HTTP(S)-Adresse." in issues
    assert "Abrufzeitpunkt fehlt, ist ungültig oder besitzt keine Zeitzone." in issues


def test_old_publication_cannot_be_refreshed_by_recent_download() -> None:
    as_of = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
    stale = replace(
        source("stale", "annual_report"),
        accessed_at=as_of.isoformat(),
        published_at=(as_of - timedelta(days=551)).date().isoformat(),
    )

    issues = source_freshness_issues(stale, as_of=as_of)
    report = assess_long_term_readiness(
        [stale],
        [LongTermEvidence("business_model", "Veraltete Aussage.", ("stale",))],
        as_of=as_of,
    )

    assert any("veraltet" in issue for issue in issues)
    assert report.ready is False
    assert report.stale_source_ids == ("stale",)
    assert report.invalid_source_ids == ("stale",)
    assert report.unresolved_source_ids == ("stale",)


def test_market_data_expires_faster_than_structural_industry_research() -> None:
    as_of = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
    old_timestamp = (as_of - timedelta(days=8)).isoformat()
    market = replace(
        source("market-old", "market_data"),
        accessed_at=old_timestamp,
        published_at=None,
    )
    industry = replace(
        source("industry-ok", "industry_research"),
        accessed_at=old_timestamp,
        published_at=(as_of - timedelta(days=500)).date().isoformat(),
    )

    assert any("veraltet" in issue for issue in source_freshness_issues(market, as_of=as_of))
    assert source_freshness_issues(industry, as_of=as_of) == ()


def test_future_or_timezone_free_access_timestamp_is_never_accepted() -> None:
    as_of = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
    future = replace(source("future", "annual_report"), accessed_at=(as_of + timedelta(hours=1)).isoformat())
    naive = replace(source("naive", "annual_report"), accessed_at="2026-08-02T18:00:00")

    report = assess_long_term_readiness(
        [future],
        [LongTermEvidence("business_model", "Aussage aus der Zukunft.", ("future",))],
        as_of=as_of,
    )

    assert report.future_source_ids == ("future",)
    assert "future" in report.invalid_source_ids
    assert any("Zukunft" in warning for warning in report.warnings)
    assert any("keine Zeitzone" in issue for issue in source_validation_issues(naive))


def test_duplicate_source_ids_are_rejected_instead_of_ambiguously_merged() -> None:
    first = source("duplicate", "annual_report")
    second = replace(source("duplicate", "industry_research"), title="Andere Quelle")
    evidence = [
        LongTermEvidence(section, "Aussage mit mehrdeutiger Quelle.", ("duplicate",))
        for section in LONG_TERM_SECTION_REQUIREMENTS
    ]

    report = assess_long_term_readiness([first, second], evidence, as_of=TEST_AS_OF)

    assert report.ready is False
    assert report.invalid_source_ids == ("duplicate",)
    assert report.unresolved_source_ids == ("duplicate",)
    assert any("Quellen-ID ist nicht eindeutig" in warning for warning in report.warnings)


def test_technical_entry_evidence_cannot_change_long_term_readiness() -> None:
    sources, evidence = complete_evidence()
    incomplete = [item for item in evidence if item.section != "market_opportunity"]
    before = assess_long_term_readiness(sources, incomplete, as_of=TEST_AS_OF)
    after = assess_long_term_readiness(
        [*sources, source("chart", "market_data")],
        [
            *incomplete,
            LongTermEvidence(
                ENTRY_TIMING_SECTION,
                "Kurzfristiger Trend ist positiv.",
                ("chart",),
            ),
        ],
        as_of=TEST_AS_OF,
    )

    assert before.ready is False
    assert after.ready is False
    assert before.missing_sections == after.missing_sections == ("market_opportunity",)
    assert before.referenced_source_count == after.referenced_source_count


def test_assessment_keeps_inputs_unchanged_and_provenance_visible() -> None:
    sources, evidence = complete_evidence()
    original_sources = list(sources)
    original_evidence = list(evidence)

    report = assess_long_term_readiness(sources, evidence, as_of=TEST_AS_OF)
    competition = next(item for item in report.section_statuses if item.section == "competitive_position")

    assert sources == original_sources
    assert evidence == original_evidence
    assert competition.source_ids == ("annual", "industry")
