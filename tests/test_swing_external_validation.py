from __future__ import annotations

import sqlite3

import pytest

from swing_external_validation import (
    ExternalUniverseContractError,
    build_external_universe_manifest,
    external_universe_store_audit,
    freeze_external_universe_manifest,
    record_external_universe_result,
)


def _asset(ticker: str, name: str, *, issuer_id: str | None = None) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "asset_type": "Aktie",
        "region": "USA",
        "category": "Industrie",
        "liquidity_class": "A",
        "issuer_id": issuer_id,
    }


def _passed_external_gate(strategy_version: str = "swing-fixed-challenger-v1") -> dict:
    return {
        "allowed": True,
        "challenger_version": strategy_version,
        "requested_stage": "external",
        "predecessor": "holdout",
        "predecessor_decision": "approved_to_next_stage",
        "automatic_production_activation": False,
    }


def test_external_universe_excludes_original_ticker_and_issuer_before_freeze() -> None:
    original = [_asset("OLD", "Original Corp", issuer_id="issuer-original")]
    proposed = [
        _asset("OLD", "Other Listing"),
        _asset("ALT", "Original Corp ADR", issuer_id="issuer-original"),
        _asset("NEW", "New Independent Corp", issuer_id="issuer-new"),
    ]
    manifest = build_external_universe_manifest(
        original,
        proposed,
        source_contract={"selection_before_results": True, "liquidity_policy": "same_as_original"},
        frozen_at="2026-08-22T12:00:00+00:00",
    )

    assert manifest["accepted_count"] == 1
    assert manifest["accepted_assets"][0]["ticker"] == "NEW"
    assert manifest["original_ticker_overlap"] == 0
    assert manifest["original_issuer_overlap"] == 0
    assert manifest["strategy_results_seen_during_selection"] is False


def test_external_universe_rejects_outcome_in_selection() -> None:
    with pytest.raises(ExternalUniverseContractError, match="Strategieergebnisse"):
        build_external_universe_manifest(
            [],
            [{**_asset("NEW", "New Corp", issuer_id="new"), "result_r": 2.0}],
            source_contract={"selection_before_results": True},
            frozen_at="2026-08-22T12:00:00+00:00",
        )


def test_external_result_requires_frozen_universe_and_is_immutable(tmp_path) -> None:
    path = tmp_path / "external.sqlite3"
    manifest = build_external_universe_manifest(
        [],
        [_asset("NEW", "New Corp", issuer_id="issuer-new")],
        source_contract={"selection_before_results": True, "liquidity_policy": "same_as_original"},
        frozen_at="2026-08-22T12:00:00+00:00",
    )
    stored = freeze_external_universe_manifest(manifest, path)
    first = record_external_universe_result(
        universe_version=manifest["universe_version"],
        strategy_version="swing-fixed-challenger-v1",
        metrics={"average_r": 0.2, "profit_factor": 1.2},
        challenger_gate=_passed_external_gate(),
        path=path,
    )
    second = record_external_universe_result(
        universe_version=manifest["universe_version"],
        strategy_version="swing-fixed-challenger-v1",
        metrics={"average_r": 0.2, "profit_factor": 1.2},
        challenger_gate=_passed_external_gate(),
        path=path,
    )

    assert stored["stored"] is True
    assert first["stored"] is True
    assert second["stored"] is False
    assert external_universe_store_audit(path)["quick_check"] == "ok"
    with pytest.raises(ExternalUniverseContractError, match="darf.*nicht verändert"):
        record_external_universe_result(
            universe_version=manifest["universe_version"],
            strategy_version="swing-fixed-challenger-v1",
            metrics={"average_r": 9.0},
            challenger_gate=_passed_external_gate(),
            path=path,
        )
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM external_universe_manifests")


def test_external_result_is_blocked_before_manual_holdout_pass(tmp_path) -> None:
    path = tmp_path / "external-blocked.sqlite3"
    manifest = build_external_universe_manifest(
        [],
        [_asset("NEW", "New Corp", issuer_id="issuer-new")],
        source_contract={"selection_before_results": True},
        frozen_at="2026-08-22T12:00:00+00:00",
    )
    freeze_external_universe_manifest(manifest, path)

    with pytest.raises(ExternalUniverseContractError, match="Holdout"):
        record_external_universe_result(
            universe_version=manifest["universe_version"],
            strategy_version="swing-fixed-challenger-v1",
            metrics={"average_r": 0.2},
            challenger_gate={
                **_passed_external_gate(),
                "allowed": False,
                "predecessor_decision": None,
            },
            path=path,
        )
