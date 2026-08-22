from __future__ import annotations

import sqlite3
from copy import deepcopy

import pytest

import swing_walk_forward as walk_forward_module
from swing_research_identity import derive_swing_research_identity
from swing_walk_forward import (
    load_swing_walk_forward_cases,
    record_swing_walk_forward_run,
    run_historical_walk_forward,
    swing_walk_forward_archive_rows,
    swing_walk_forward_case_metrics,
    swing_walk_forward_research_readiness,
    swing_walk_forward_store_audit,
)
from tests.test_swing_walk_forward import breakout_history


def _case(
    ticker: str,
    name: str,
    result_r: float,
    *,
    exchange: str,
    isin: str | None = None,
    signal_day: str = "2025-01-10",
    future_day: str = "2025-02-14",
) -> dict:
    identity = derive_swing_research_identity(
        {
            "ticker": ticker,
            "name": name,
            "asset_type": "Aktie",
            "region": "Global",
            "exchange": exchange,
            "isin": isin,
        }
    )
    return {
        "case_id": f"case-{ticker}",
        "symbol": ticker,
        "signal_at": f"{signal_day}T23:59:00+00:00",
        "future_last_day": future_day,
        "evaluation_horizon_sessions": 25,
        "research_split": "holdout",
        "selection_eligible": True,
        "overlap_purged": True,
        "result_r": result_r,
        "research_identity": identity,
        "snapshot": {
            "asset": {
                "ticker": ticker,
                "asset_type": "Aktie",
                "region": "Global",
                "listing_id": identity["listing_id"],
                "issuer_id": identity["issuer_id"],
            },
            "strategy": {
                "strategy_version": "unchanged-test-strategy",
                "strategy_name": "current",
                "market_phase": "Aufwärtstrend",
                "volatility_regime": "normal",
            },
        },
    }


def test_case_identity_conflict_becomes_append_only_revision_and_resume_is_idempotent(
    tmp_path,
) -> None:
    path = tmp_path / "identity-conflict.sqlite3"
    original_run = run_historical_walk_forward(
        {"GENERIC": breakout_history()},
        minimum_history_rows=300,
        step_sessions=1,
        future_sessions=25,
        maximum_cases=1,
    )
    first = record_swing_walk_forward_run(original_run, path)
    original_case_id = original_run["cases"][0]["case_id"]
    with sqlite3.connect(path) as connection:
        original_before = connection.execute(
            "SELECT case_json, case_fingerprint FROM walk_forward_cases WHERE case_id = ?",
            (original_case_id,),
        ).fetchone()

    expanded_run = deepcopy(original_run)
    expanded_run["run_id"] = "same-research-new-structure"
    expanded_run["created_at"] = "2026-08-18T12:00:00+00:00"
    expanded_case = expanded_run["cases"][0]
    expanded_case["research_data_quality"] = {"issuer_listing_identity": "available"}
    expanded_case["case_fingerprint"] = walk_forward_module._fingerprint(
        {key: value for key, value in expanded_case.items() if key != "case_fingerprint"}
    )

    repaired = record_swing_walk_forward_run(expanded_run, path)
    resumed = record_swing_walk_forward_run(expanded_run, path)
    audit = swing_walk_forward_store_audit(path)
    revisions = load_swing_walk_forward_cases(path, include_superseded_revisions=True)

    assert first["cases_inserted"] == 1
    assert repaired["cases_inserted"] == 1
    assert repaired["identity_conflicts_resolved"] == 1
    assert repaired["identity_conflicts_recorded"] == 1
    assert resumed["run_inserted"] is False
    assert resumed["cases_inserted"] == 0
    assert resumed["identity_conflicts_resolved"] == 1
    assert resumed["identity_conflicts_recorded"] == 0
    assert len(revisions) == 2
    assert sum("identity_revision" in case for case in revisions) == 1
    assert audit["case_identity_conflicts_resolved"] == 1
    assert audit["status"] == "ok"
    with sqlite3.connect(path) as connection:
        original_after = connection.execute(
            "SELECT case_json, case_fingerprint FROM walk_forward_cases WHERE case_id = ?",
            (original_case_id,),
        ).fetchone()
        assert original_after == original_before
        assert connection.execute("SELECT COUNT(*) FROM walk_forward_cases").fetchone()[0] == 2
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM walk_forward_case_identity_conflicts")


def test_share_classes_remain_separate_raw_trades_but_form_one_evidence_cluster() -> None:
    cases = [
        _case("LLYVA", "Liberty Live Holdings, Inc.", 2.0, exchange="NASDAQ"),
        _case("LLYVK", "Liberty Live Holdings, Inc.", -1.0, exchange="NASDAQ"),
    ]

    metrics = swing_walk_forward_case_metrics(cases)
    readiness = swing_walk_forward_research_readiness(
        cases,
        minimum_outcomes=2,
        minimum_symbols=2,
        minimum_holdout_outcomes=1,
        minimum_segment_outcomes=1,
    )
    archive = swing_walk_forward_archive_rows(cases)

    assert len(archive) == 2
    assert len({row["Listing-ID"] for row in archive}) == 2
    assert len({row["Issuer-ID"] for row in archive}) == 1
    assert len({row["Evidenzcluster"] for row in archive}) == 1
    assert all(row["Rohfälle im Evidenzcluster"] == 2 for row in archive)
    assert metrics["raw_evaluated"] == 2
    assert metrics["effective_independent_evaluated"] == 1
    assert metrics["dependent_listing_clusters"] == 1
    assert metrics["hit_rate_pct"] == 50.0
    assert metrics["average_r"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert readiness["technical_challenger_review_allowed"] is False
    assert readiness["minimum_outcomes_basis"] == "effective_independent_evaluated"
    assert readiness["minimum_symbols_basis"] == "issuer_clusters"


def test_adr_and_underlying_share_are_general_issuer_dependencies() -> None:
    adr = _case(
        "EXMPL",
        "Example Holdings SE American Depositary Receipt",
        1.0,
        exchange="NYSE",
    )
    ordinary = _case(
        "EXM.DE",
        "Example Holdings SE Ordinary Shares",
        1.0,
        exchange="XETRA",
    )

    assert adr["research_identity"]["issuer_id"] == ordinary["research_identity"]["issuer_id"]
    assert adr["research_identity"]["listing_id"] != ordinary["research_identity"]["listing_id"]
    assert adr["research_identity"]["is_depositary_receipt"] is True
    assert ordinary["research_identity"]["is_depositary_receipt"] is False
    metrics = swing_walk_forward_case_metrics([adr, ordinary])
    assert metrics["raw_evaluated"] == 2
    assert metrics["effective_independent_evaluated"] == 1


def test_same_company_on_multiple_exchanges_is_clustered_without_ticker_rule() -> None:
    london = _case(
        "EXM.L",
        "Example Manufacturing plc",
        1.0,
        exchange="LSE",
        isin="GB0000000001",
    )
    amsterdam = _case(
        "EXM.AS",
        "Example Mfg N.V.",
        1.0,
        exchange="EURONEXT",
        isin="GB0000000001",
    )

    assert london["research_identity"]["economic_instrument_id"] == amsterdam[
        "research_identity"
    ]["economic_instrument_id"]
    assert london["research_identity"]["listing_id"] != amsterdam["research_identity"]["listing_id"]
    assert swing_walk_forward_case_metrics([london, amsterdam])[
        "effective_independent_evaluated"
    ] == 1


def test_direct_single_listing_keeps_raw_and_effective_statistics_unchanged() -> None:
    direct = _case("ONLY", "Only Company AG", 1.25, exchange="XETRA")

    metrics = swing_walk_forward_case_metrics([direct])

    assert metrics["raw_cases"] == metrics["effective_independent_cases"] == 1
    assert metrics["raw_evaluated"] == metrics["effective_independent_evaluated"] == 1
    assert metrics["dependency_adjustment_required"] is False
    assert metrics["dependent_listing_clusters"] == 0
    assert metrics["hit_rate_pct"] == metrics["independence_adjusted_hit_rate_pct"] == 100.0
    assert metrics["average_r"] == 1.25
