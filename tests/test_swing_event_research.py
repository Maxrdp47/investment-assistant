from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from swing_event_research import (
    EVENT_CODE_FINGERPRINT,
    EVENT_CONTEXT_VERSION,
    EVENT_SCHEMA_VERSION,
    EVENT_TRANSMISSION_MATRIX_VERSION,
    TRANSMISSION_MATRIX,
    append_event_hypothesis_ledger_entry,
    append_event_record,
    append_market_reaction_label,
    append_signal_event_context,
    build_forward_event_diagnostics,
    build_signal_event_context,
    collect_forward_event_contexts,
    event_coverage_report,
    event_relevance,
    event_research_store_audit,
    initialize_event_research_store,
    ingest_event_records,
    load_events_as_of,
    load_signal_event_contexts,
    normalize_event_record,
)


UTC = timezone.utc
SIGNAL_AT = datetime(2026, 8, 23, 10, 30, tzinfo=UTC)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def company_event(**overrides) -> dict:
    payload = {
        "event_type": "company",
        "event_subtype": "earnings",
        "published_at": "2026-08-23T09:00:00+00:00",
        "source_id": "official-company-release-1",
        "source_type": "company_ir",
        "source_quality": "official_primary",
        "title": "Quarterly results",
        "summary": "Reported quarterly results.",
        "affected_assets": ["TEST"],
        "affected_companies": ["Test AG"],
        "affected_sectors": ["Technology"],
        "affected_regions": ["Europe"],
        "direction": "unknown",
        "severity": 0.7,
        "confidence": 0.95,
        "source_locator": "https://example.invalid/release",
        "raw_source_fingerprint": "raw-1",
        "retrieved_via": "official feed",
    }
    payload.update(overrides)
    return payload


def normalized(**overrides) -> dict:
    return normalize_event_record(
        company_event(**overrides),
        first_seen_at="2026-08-23T09:01:00+00:00",
    )


def forward_database(path: Path, *, known_event: bool = True) -> str:
    signal_id = "signal-1"
    snapshot = {
        "asset": {
            "ticker": "TEST",
            "name": "Test AG",
            "asset_type": "Aktie",
            "region": "Europa",
        },
        "strategy": {
            "strategy_version": "swing-long-pullback-breakout-2026.08.11-v3",
            "known_event_date_at_signal": "2026-08-26" if known_event else None,
            "event_days_at_signal": 3 if known_event else None,
        },
        "universe": {"sector": "Technology", "industry": "Software"},
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE swing_signals (
            signal_id TEXT PRIMARY KEY, signal_at TEXT NOT NULL, snapshot_json TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO swing_signals VALUES (?, ?, ?)",
            (signal_id, SIGNAL_AT.isoformat(), json.dumps(snapshot)),
        )
    return signal_id


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_is_versioned_deterministic_and_missingness_stays_visible() -> None:
    first = normalized(expected_value=None, actual_value=2.0)
    second = normalized(expected_value=None, actual_value=2.0)

    assert first == second
    assert first["event_schema_version"] == EVENT_SCHEMA_VERSION
    assert first["data_fingerprint"] == second["data_fingerprint"]
    assert {
        "event_id",
        "event_version",
        "event_type",
        "event_subtype",
        "published_at",
        "first_seen_at",
        "effective_at",
        "source_id",
        "source_type",
        "source_quality",
        "title",
        "summary",
        "affected_assets",
        "affected_companies",
        "affected_sectors",
        "affected_regions",
        "affected_commodities",
        "affected_macro_factors",
        "direction",
        "severity",
        "confidence",
        "expected_value",
        "actual_value",
        "surprise_value",
        "surprise_normalized",
        "uncertainty",
        "event_expiry",
        "provenance",
        "data_fingerprint",
    } <= set(first)
    assert len(EVENT_CODE_FINGERPRINT) == 64
    assert first["expectation"]["surprise_status"] == "unavailable"
    assert first["expectation"]["surprise_value"] is None
    assert first["missingness"]["expectation"] is True
    assert first["guardrails"]["changes_trade_decision"] is False
    assert first["guardrails"]["short_strategy"] is False
    assert first["guardrails"]["broker_order"] is False


def test_expected_actual_and_surprise_are_strictly_separate() -> None:
    event = normalized(
        expected_value=1.0,
        actual_value=1.5,
        surprise_value=0.5,
        surprise_normalized=1.2,
        expectation_source_id="consensus-at-08-59",
        expectation_available_at="2026-08-23T08:59:00+00:00",
    )

    assert event["expectation"] == {
        "expected_value": 1.0,
        "actual_value": 1.5,
        "surprise_value": 0.5,
        "surprise_normalized": 1.2,
        "expectation_source_id": "consensus-at-08-59",
        "expectation_available_at": "2026-08-23T08:59:00+00:00",
        "surprise_status": "available",
        "no_consensus_reconstruction": True,
    }
    with pytest.raises(ValueError, match="widerspricht"):
        normalized(
            expected_value=1.0,
            actual_value=1.5,
            surprise_value=0.7,
            expectation_source_id="consensus-at-08-59",
            expectation_available_at="2026-08-23T08:59:00+00:00",
        )
    with pytest.raises(ValueError, match="Quelle und damaligen"):
        normalized(expected_value=1.0, actual_value=1.5)
    with pytest.raises(ValueError, match="nicht kausal"):
        normalized(
            expected_value=1.0,
            actual_value=1.5,
            expectation_source_id="late-consensus",
            expectation_available_at="2026-08-23T09:30:00+00:00",
        )


def test_published_and_first_seen_are_strictly_causal_and_backfill_is_blocked(tmp_path) -> None:
    with pytest.raises(ValueError, match="published_at"):
        normalize_event_record(company_event(), first_seen_at="2026-08-23T08:59:00+00:00")

    path = tmp_path / "events.sqlite3"
    historical = normalize_event_record(
        company_event(),
        first_seen_at="2026-08-24T10:00:00+00:00",
        acquisition_mode="historical_backfill",
    )
    assert historical["pit_eligible"] is False
    append_event_record(historical, path)
    assert load_events_as_of("2026-08-25T00:00:00+00:00", path) == []


def test_later_article_revision_is_not_retroactively_available(tmp_path) -> None:
    path = tmp_path / "events.sqlite3"
    first = normalized(event_version="1")
    revision = normalize_event_record(
        company_event(event_version="2", summary="Revised later"),
        first_seen_at="2026-08-23T11:00:00+00:00",
    )
    append_event_record(first, path)
    append_event_record(revision, path)

    before = load_events_as_of("2026-08-23T10:30:00+00:00", path)
    after = load_events_as_of("2026-08-23T11:00:00+00:00", path)

    assert [event["event_version"] for event in before] == ["1"]
    assert [event["event_version"] for event in after] == ["1", "2"]
    context_after = build_signal_event_context(
        signal_id="signal-after-revision",
        signal_at="2026-08-23T11:00:00+00:00",
        asset={"ticker": "TEST"},
        created_at="2026-08-23T11:00:00+00:00",
        events=after,
    )
    assert [event["event_version"] for event in context_after["events"]] == ["2"]


def test_relevance_is_hierarchical_deterministic_and_not_keyword_only() -> None:
    event = normalized()
    direct = event_relevance(event, {"ticker": "TEST", "sector": "Other", "region": "USA"})
    sector = event_relevance(event, {"ticker": "OTHER", "sector": "Technology", "region": "USA"})
    region = event_relevance(event, {"ticker": "OTHER", "sector": "Other", "region": "Europe"})

    assert direct == event_relevance(event, {"ticker": "TEST", "sector": "Other", "region": "USA"})
    assert direct["relevance_level"] == 1
    assert sector["relevance_level"] == 2
    assert region["relevance_level"] == 4
    assert direct["no_keyword_only_mapping"] is True
    assert direct["direction_for_asset"] == "unknown"


def test_signal_context_excludes_future_information_and_marks_missing_data_honestly() -> None:
    available = normalized()
    future_revision = normalize_event_record(
        company_event(event_version="2", summary="Later revision"),
        first_seen_at="2026-08-23T11:00:00+00:00",
    )
    context = build_signal_event_context(
        signal_id="signal-1",
        signal_at=SIGNAL_AT,
        asset={"ticker": "TEST", "sector": "Technology", "region": "Europe"},
        created_at=SIGNAL_AT + timedelta(minutes=5),
        events=[available, future_revision],
    )
    empty = build_signal_event_context(
        signal_id="signal-2",
        signal_at=SIGNAL_AT,
        asset={"ticker": "NONE"},
        created_at=SIGNAL_AT,
        events=[],
    )

    assert context["context_schema_version"] == EVENT_CONTEXT_VERSION
    assert [event["event_version"] for event in context["events"]] == ["1"]
    assert context["guardrails"]["forward_snapshot_changed"] is False
    assert empty["no_reliable_event_data_available"] is True
    assert empty["missing_event_data_is_not_no_event"] is True


def test_store_is_append_only_resume_safe_and_conflict_safe(tmp_path) -> None:
    path = tmp_path / "events.sqlite3"
    event = normalized()
    assert append_event_record(event, path)["inserted"] is True
    assert append_event_record(event, path)["inserted"] is False
    context = build_signal_event_context(
        signal_id="signal-1",
        signal_at=SIGNAL_AT,
        asset={"ticker": "TEST"},
        created_at=SIGNAL_AT,
        events=[event],
    )
    assert append_signal_event_context(context, path)["inserted"] is True
    assert append_signal_event_context(context, path)["inserted"] is False
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE event_records SET event_type='macro'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM event_signal_contexts")


def test_event_features_and_later_reaction_labels_are_physically_separate(tmp_path) -> None:
    path = tmp_path / "events.sqlite3"
    event = normalized()
    append_event_record(event, path)
    with pytest.raises(ValueError, match="strikt nach"):
        append_market_reaction_label(
            event_record_id=event["event_record_id"],
            horizon="1D",
            observed_at=event["first_seen_at"],
            data_granularity="daily",
            metrics={"return_pct": 2.0},
            path=path,
        )
    label = append_market_reaction_label(
        event_record_id=event["event_record_id"],
        horizon="1D",
        observed_at="2026-08-24T20:00:00+00:00",
        data_granularity="daily",
        metrics={"return_pct": 2.0, "mfe_pct": 3.0, "mae_pct": -1.0},
        path=path,
    )
    with sqlite3.connect(path) as connection:
        event_columns = {row[1] for row in connection.execute("PRAGMA table_info(event_records)")}
        label_columns = {row[1] for row in connection.execute("PRAGMA table_info(event_market_reaction_labels)")}

    assert label["label"]["association_only"] is True
    assert label["label"]["causality_claimed"] is False
    assert label["label"]["metrics"]["return_pct"] == 2.0
    assert label["label"]["metric_missingness"]["sector_relative_return_pct"] is True
    assert "label_json" not in event_columns
    assert "label_json" in label_columns
    with pytest.raises(ValueError, match="Daily-Daten"):
        append_market_reaction_label(
            event_record_id=event["event_record_id"],
            horizon="1h",
            observed_at="2026-08-24T20:00:00+00:00",
            data_granularity="daily",
            metrics={"return_pct": 2.0},
            path=path,
        )


def test_market_transmission_never_claims_causality() -> None:
    event = normalized(
        market_transmission=[
            {
                "factor": "oil",
                "observed_at": "2026-08-23T09:30:00+00:00",
                "return_pct": 2.4,
                "data_granularity": "30m",
            }
        ]
    )

    assert event["market_transmission"][0]["association_only"] is True
    assert event["market_transmission"][0]["causality_claimed"] is False
    assert TRANSMISSION_MATRIX["version"] == EVENT_TRANSMISSION_MATRIX_VERSION
    assert TRANSMISSION_MATRIX["research_only"] is True


def test_clinical_contract_does_not_invent_missing_medical_meaning() -> None:
    event = normalized(
        event_subtype="clinical_trial",
        clinical={"trial_id": "NCT123", "phase": "2", "primary_endpoint": "PFS"},
    )

    assert event["clinical"]["trial_id"] == "NCT123"
    assert event["clinical"]["primary_endpoint"] == "PFS"
    assert event["clinical"]["statistical_significance"] is None
    assert event["clinical"]["safety_findings"] is None
    assert event["clinical"]["peer_reviewed"] is None


def test_forward_collector_uses_only_immutable_snapshot_evidence_and_preserves_forward_db(tmp_path) -> None:
    forward_path = tmp_path / "forward.sqlite3"
    event_path = tmp_path / "events.sqlite3"
    signal_id = forward_database(forward_path, known_event=True)
    before = sha256(forward_path)

    result = collect_forward_event_contexts(
        signal_ids=[signal_id],
        forward_path=forward_path,
        collected_at=SIGNAL_AT + timedelta(minutes=2),
        path=event_path,
        news_loader=lambda _symbol: [],
    )
    repeated = collect_forward_event_contexts(
        signal_ids=[signal_id],
        forward_path=forward_path,
        collected_at=SIGNAL_AT + timedelta(minutes=5),
        path=event_path,
        news_loader=lambda _symbol: pytest.fail("Resume darf Provider nicht erneut aufrufen."),
    )
    contexts = load_signal_event_contexts(event_path)

    assert sha256(forward_path) == before
    assert result["contexts_inserted"] == 1
    assert result["production_effect"] == "none"
    assert result["broad_research_blocked"] is False
    assert result["long_v1_changed"] is False
    assert result["short_strategy"] is False
    assert result["broker_order"] is False
    assert repeated["contexts_existing"] == 1
    assert contexts[0]["known_future_events"][0]["effective_date"] == "2026-08-26"
    assert contexts[0]["known_future_events"][0]["session_distance"] is None


def test_news_first_seen_after_signal_is_stored_but_not_backdated_into_context(tmp_path) -> None:
    forward_path = tmp_path / "forward.sqlite3"
    event_path = tmp_path / "events.sqlite3"
    signal_id = forward_database(forward_path, known_event=False)
    news = {
        "uuid": "article-1",
        "title": "Test AG reports quarterly results",
        "providerPublishTime": int((SIGNAL_AT - timedelta(hours=1)).timestamp()),
        "relatedTickers": ["TEST"],
        "publisher": "Example Finance",
        "link": "https://example.invalid/article-1",
    }

    result = collect_forward_event_contexts(
        signal_ids=[signal_id],
        forward_path=forward_path,
        collected_at=SIGNAL_AT + timedelta(minutes=2),
        path=event_path,
        news_loader=lambda _symbol: [news],
    )
    contexts = load_signal_event_contexts(event_path)
    coverage = event_coverage_report(event_path)

    assert result["events_inserted"] == 1
    assert coverage["events"] == 1
    assert coverage["current_sources"] == ["news_aggregator"]
    assert contexts[0]["event_count"] == 0
    assert contexts[0]["no_reliable_event_data_available"] is True


def test_batch_ingestion_reports_errors_without_activating_production(tmp_path) -> None:
    result = ingest_event_records(
        [company_event(), {"event_type": "unknown", "source_id": "broken"}],
        first_seen_at="2026-08-23T09:01:00+00:00",
        path=tmp_path / "events.sqlite3",
    )

    assert result["inserted"] == 1
    assert len(result["errors"]) == 1
    assert result["production_effect"] == "none"
    assert result["research_shadow_only"] is True


def test_research_ledger_is_append_only_development_first_and_deduplicated(tmp_path) -> None:
    path = tmp_path / "events.sqlite3"
    kwargs = {
        "hypothesis_id": "guidance-bos-v1",
        "recorded_at": "2026-08-23T12:00:00+00:00",
        "action": "defined",
        "hypothesis": "Long-BOS plus positive guidance surprise",
        "event_type": "company",
        "parameters": {"event_subtype": "guidance_increase", "technical": "bos"},
        "dataset_fingerprint": "development-only-dataset",
        "similar_hypotheses": ["guidance-breakout-v0"],
        "path": path,
    }
    first = append_event_hypothesis_ledger_entry(**kwargs)
    second = append_event_hypothesis_ledger_entry(**kwargs)

    assert first["inserted"] is True
    assert second["inserted"] is False
    assert first["entry"]["development_first"] is True
    assert first["entry"]["freeze_before_validation"] is True
    assert first["entry"]["holdout_selection_forbidden"] is True
    assert first["entry"]["automatic_production_activation"] is False


def test_coverage_and_audit_are_explicitly_incomplete_and_production_neutral(tmp_path) -> None:
    path = tmp_path / "events.sqlite3"
    initialize_event_research_store(path)
    append_event_record(normalized(), path)
    report = event_coverage_report(path)
    audit = event_research_store_audit(path)

    assert report["historical_coverage_complete"] is False
    assert report["supported_event_groups"] == ["company", "geopolitics_policy", "macro", "market_shock"]
    assert report["by_event_type"]["company"]["events"] == 1
    assert report["by_event_type"]["company"]["expectation_share"] == 0.0
    assert audit["integrity"] == "ok"
    assert audit["invalid_event_fingerprints"] == 0
    assert audit["append_only"] is True
    assert audit["automatic_production_activation"] is False


def test_forward_event_diagnostics_remain_descriptive_and_small_sample_neutral() -> None:
    diagnostics = build_forward_event_diagnostics(
        [
            {
                "signal_id": "signal-1",
                "snapshot": {"asset": {"ticker": "TEST"}},
                "events": [
                    {
                        "event_type": "stop_reached",
                        "payload": {"result_r": -1.05},
                    }
                ],
            }
        ],
        [
            {
                "signal_id": "signal-1",
                "no_reliable_event_data_available": False,
                "events": [
                    {
                        "event_type": "geopolitics_policy",
                        "event_subtype": "sanctions",
                        "expectation": {"surprise_value": None},
                        "relevance": {"direction_for_asset": "unknown"},
                    }
                ],
            }
        ],
    )

    assert diagnostics["closed_forward_trades"] == 1
    assert diagnostics["losses_with_geopolitical_context"] == 1
    assert diagnostics["small_sample_rule_change_forbidden"] is True
    assert diagnostics["automatic_strategy_change"] is False
    assert diagnostics["production_effect"] == "none"


def test_roadmap_status_and_runtime_config_keep_event_layer_separate_from_broad_and_production() -> None:
    roadmap = (PROJECT_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    status = (PROJECT_ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    settings = json.loads(
        (PROJECT_ROOT / "config" / "swing_background_settings.json").read_text(encoding="utf-8")
    )

    assert "G2.7 – getrennter Point-in-Time Event-/News-/Makro-/Geopolitik-Edge-Layer" in roadmap
    assert "Der technische Broad-Vollpass wartet ausdrücklich **nicht**" in roadmap
    assert "Point-in-Time Event-/News-/Makro-/Geopolitik-Research" in status
    assert EVENT_CODE_FINGERPRINT in status
    assert "24 generische, damals bekannte Unternehmenstermine" in status
    assert settings["event_research"] == {
        "enabled": True,
        "database_path": "runtime/swing_event_research.sqlite3",
        "research_only": True,
        "changes_trade_decision": False,
        "broker_order_allowed": False,
    }
