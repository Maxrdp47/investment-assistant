from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from cot_positioning import (
    append_cot_report,
    append_cot_shadow_link,
    build_asset_cot_shadow_context,
    compare_strategy_with_cot_shadow,
    cot_shadow_assessment,
    cot_shadow_store_audit,
    derive_cot_features,
    initialize_cot_shadow_store,
    ingest_cftc_rows,
    load_cot_market_mapping,
    load_cot_reports_as_of,
    map_cot_market,
    normalize_cftc_row,
)


UTC = timezone.utc


def tff_row(day: str, *, asset_long: int, asset_short: int, lev_long: int, lev_short: int, oi: int = 1000) -> dict:
    return {
        "report_date_as_yyyy_mm_dd": f"{day}T00:00:00.000",
        "cftc_contract_market_code": "13874A",
        "contract_market_name": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
        "commodity_name": "S&P 500 Consolidated",
        "open_interest_all": str(oi),
        "dealer_positions_long_all": "100",
        "dealer_positions_short_all": "120",
        "asset_mgr_positions_long": str(asset_long),
        "asset_mgr_positions_short": str(asset_short),
        "lev_money_positions_long": str(lev_long),
        "lev_money_positions_short": str(lev_short),
        "other_rept_positions_long": "60",
        "other_rept_positions_short": "55",
        "nonrept_positions_long_all": "80",
        "nonrept_positions_short_all": "75",
    }


def normalized_week(index: int, *, published: bool = True) -> dict:
    report_day = datetime(2026, 1, 6, tzinfo=UTC) + timedelta(days=7 * index)
    publication = report_day + timedelta(days=3, hours=22)
    return normalize_cftc_row(
        tff_row(
            report_day.date().isoformat(),
            asset_long=200 + index * 20,
            asset_short=180,
            lev_long=150 + index * 5,
            lev_short=170,
            oi=1000 + index * 50,
        ),
        report_type="tff_futures_only",
        retrieved_at=publication + timedelta(hours=1),
        acquisition_mode="historical_backfill",
        published_at=publication if published else None,
    )


def test_historical_backfill_without_verified_release_is_point_in_time_blocked() -> None:
    report = normalized_week(0, published=False)

    assert report["pit_eligible"] is False
    assert report["available_at"] is None
    assert report["availability_basis"] == "historical_release_timestamp_unverified"
    assert derive_cot_features([report], decision_at="2026-12-31T23:00:00+00:00")["status"] == "unavailable_point_in_time"


def test_forward_observation_becomes_available_only_when_first_seen() -> None:
    report = normalize_cftc_row(
        tff_row("2026-01-06", asset_long=220, asset_short=180, lev_long=170, lev_short=160),
        report_type="tff_futures_only",
        retrieved_at="2026-01-09T22:15:00+00:00",
        acquisition_mode="forward",
    )

    before = derive_cot_features([report], decision_at="2026-01-09T22:14:59+00:00")
    after = derive_cot_features([report], decision_at="2026-01-09T22:15:00+00:00")

    assert before["status"] == "unavailable_point_in_time"
    assert after["report_id"] == report["report_id"]


def test_features_use_only_published_past_and_calculate_1w_4w_percentile_zscore() -> None:
    reports = [normalized_week(index) for index in range(6)]
    decision = reports[4]["available_at"]

    features = derive_cot_features(reports, decision_at=decision)
    asset_manager = features["categories"]["asset_manager_institutional"]

    assert features["report_id"] == reports[4]["report_id"]
    assert asset_manager["net_position"] == 100
    assert asset_manager["net_change_1w"] == 20
    assert asset_manager["net_change_4w"] == 80
    assert asset_manager["historical_percentile"] == 100.0
    assert asset_manager["historical_z_score"] > 1
    assert features["open_interest_change_1w"] == 50
    assert features["open_interest_change_4w"] == 200
    assert reports[5]["report_id"] != features["report_id"]


def test_original_participant_classes_are_preserved_without_retail_or_smart_money_claims() -> None:
    report = normalized_week(1)

    assert "non_reportables" in report["categories"]
    assert "nicht mit Retail" in report["categories"]["non_reportables"]["classification_note"]
    assert report["classification_guardrails"]["non_reportables_are_retail"] is False
    assert report["classification_guardrails"]["commercials_are_smart_money"] is False


def test_explicit_mapping_is_broad_context_and_unknown_markets_fail_closed() -> None:
    mapping = load_cot_market_mapping()
    mapped = map_cot_market(normalized_week(0), mapping)
    unknown = dict(normalized_week(0), market_name="UNLISTED TEST FUTURE", commodity_name="UNLISTED")

    assert mapped == {
        "status": "mapped",
        "asset_group": "equities_us_broad_market",
        "scope": "broad_market_context",
        "rule_id": "tff-us-large-cap-equity-index-v1",
        "mapping_version": "cot-market-mapping-2026.08.18-v1",
        "issuer_specific": False,
    }
    assert map_cot_market(unknown, mapping)["status"] == "unmapped"


def test_asset_context_is_broad_never_issuer_specific_and_uses_only_available_reports() -> None:
    mapping = load_cot_market_mapping()
    reports = [normalized_week(index) for index in range(6)]
    context = build_asset_cot_shadow_context(
        {"ticker": "MSFT", "asset_type": "Aktie", "region": "USA"},
        reports,
        decision_at=reports[4]["available_at"],
        mapping=mapping,
    )

    assert context["mapping"]["scope"] == "broad_market_context"
    assert context["mapping"]["issuer_specific"] is False
    assert context["mapping"]["selected_market_code"] == "13874A"
    assert context["features"]["report_id"] == reports[4]["report_id"]
    assert context["assessment"]["changes_trade_decision"] is False


def test_divergence_and_shadow_label_never_change_trade_or_weight() -> None:
    reports = [normalized_week(index) for index in range(6)]
    features = derive_cot_features(reports, decision_at=reports[-1]["available_at"])
    assessment = cot_shadow_assessment(features)

    assert assessment["label"] in {"confirms", "contradicts", "neutral", "extreme_contrarian"}
    assert assessment["shadow_only"] is True
    assert assessment["changes_trade_decision"] is False
    assert assessment["changes_score_or_weight"] is False
    assert assessment["automatic_activation"] is False


def test_shadow_comparison_keeps_champion_and_counterfactual_metrics_separate() -> None:
    comparison = compare_strategy_with_cot_shadow(
        [
            {"result_r": 2.0, "mfe_r": 2.4, "mae_r": -0.4, "cot_shadow_label": "confirms"},
            {"result_r": -1.0, "mfe_r": 0.3, "mae_r": -1.1, "cot_shadow_label": "contradicts"},
            {"result_r": 1.0, "mfe_r": 1.4, "mae_r": -0.2, "cot_shadow_label": "neutral"},
        ]
    )

    assert comparison["existing_strategy"]["cases"] == 3
    assert comparison["existing_strategy"]["profit_factor"] == 3.0
    assert comparison["strategy_plus_positioning_shadow"]["cases"] == 2
    assert comparison["excluded_as_contradiction"] == 1
    assert comparison["production_effect"] == "none"
    assert comparison["automatic_rule_change"] is False


def test_store_is_append_only_and_links_are_separate(tmp_path) -> None:
    path = tmp_path / "cot.sqlite3"
    report = normalized_week(0)
    assert append_cot_report(report, path) is True
    assert append_cot_report(report, path) is False
    loaded = load_cot_reports_as_of(
        report["market_code"], report["report_type"], report["available_at"], path
    )
    features = derive_cot_features(loaded, decision_at=report["available_at"])
    assessment = cot_shadow_assessment(features)
    link_id = append_cot_shadow_link(
        signal_id="signal-1",
        signal_at=report["available_at"],
        mapping={"status": "mapped", "asset_group": "equities_us_large_cap"},
        features=features,
        assessment=assessment,
        created_at="2026-08-18T10:00:00+00:00",
        path=path,
    )

    assert link_id
    assert cot_shadow_store_audit(path) == {
        "integrity": "ok",
        "reports": 1,
        "shadow_links": 1,
        "pit_unverified_reports": 0,
    }
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE cot_reports SET market_code = 'changed'")


def test_batch_ingestion_is_idempotent_and_reports_invalid_rows(tmp_path) -> None:
    path = tmp_path / "cot.sqlite3"
    rows = [
        tff_row("2026-01-06", asset_long=220, asset_short=180, lev_long=170, lev_short=160),
        {"report_date_as_yyyy_mm_dd": "2026-01-06T00:00:00.000"},
    ]
    first = ingest_cftc_rows(
        rows,
        report_type="tff_futures_only",
        retrieved_at="2026-01-09T22:15:00+00:00",
        path=path,
    )
    second = ingest_cftc_rows(
        rows[:1],
        report_type="tff_futures_only",
        retrieved_at="2026-01-09T22:15:00+00:00",
        path=path,
    )

    assert first["stored"] == 1
    assert first["errors"][0]["error"] == "CFTC-Zeile ohne stabilen Marktcode oder Marktnamen."
    assert second["stored"] == 0
    assert second["duplicates"] == 1
