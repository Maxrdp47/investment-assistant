from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from fx_carry_pit import fx_pair_contract, normalize_fx_ohlc
from multi_asset_discovery_v1 import (
    MultiAssetDiscoveryContractError,
    audit_pilot_stores,
    build_contract_freeze,
    build_feature_snapshot,
    build_outcome,
    canonical_json,
    evaluate_integrity_pilot,
    fingerprint,
    load_discovery_contract,
    record_freeze_and_features,
    record_outcomes_and_dependency,
    temporal_dependency_report,
    verify_contract_freeze,
)


def _history(*, calendar: bool = False) -> pd.DataFrame:
    index = (
        pd.date_range("2019-01-01", periods=1_100, freq="D")
        if calendar
        else pd.bdate_range("2019-01-01", periods=800)
    )
    x = np.arange(len(index), dtype=float)
    close = 100.0 + 0.035 * x + 5.0 * np.sin(x / 11.0) + 1.5 * np.sin(x / 3.0)
    open_ = close * (1 + 0.002 * np.sin(x / 7.0))
    high = np.maximum(open_, close) + 1.0 + 0.2 * np.sin(x / 5.0) ** 2
    low = np.minimum(open_, close) - 1.0 - 0.2 * np.cos(x / 5.0) ** 2
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": 1_000_000 + x * 1_000,
        },
        index=index,
    )


def _asset(asset_class: str = "EQUITIES") -> dict[str, object]:
    return {
        "ticker": "TEST",
        "asset_id": "asset-test",
        "asset_class": asset_class,
        "listing_id": "listing-test",
        "issuer_id": "issuer-test" if asset_class == "EQUITIES" else None,
        "mapping_status": "VERIFIED" if asset_class == "EQUITIES" else "UNRESOLVED",
        "dependency_status": "KNOWN" if asset_class == "EQUITIES" else "UNKNOWN",
    }


def _feature(
    frame: pd.DataFrame,
    position: int,
    *,
    asset_class: str = "EQUITIES",
) -> dict[str, object]:
    day = pd.Timestamp(frame.index[position]).date().isoformat()
    return build_feature_snapshot(
        asset=_asset(asset_class),
        frame=frame,
        decision_position=position,
        decision_time=f"{day}T23:59:59+00:00",
        dataset_fingerprint="dataset-test-v1",
    )


def _freeze() -> dict[str, object]:
    return build_contract_freeze(
        source_snapshots={
            "dataset_fingerprint": "dataset-test-v1",
            "identity_registry_fingerprint": "identity-test-v1",
            "fx_store_sha256": "a" * 64,
            "dataset_manifest_sha256": "b" * 64,
        },
        git_branch="codex/test",
        git_commit="c" * 40,
        frozen_at="2026-08-31T18:00:00+00:00",
    )


def test_contract_is_frozen_complete_and_blocks_later_lifecycle() -> None:
    contract = load_discovery_contract()

    assert contract["contract_version"].endswith("v1")
    assert contract["candidate_generation"]["full_development_scan_allowed"] is False
    assert contract["candidate_generation"]["predictive_prefilter_allowed"] is False
    assert contract["candidate_generation"]["composite_opportunity_score_allowed"] is False
    assert contract["safe_zone_contract"]["models"] == [
        "A_CONFIRMED_SWING_LOW",
        "B_CONFIRMED_SUPPORT_ZONE",
        "C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14",
    ]
    assert contract["outcome_contract"]["horizon_daily_observations"] == 252
    assert all(value is False for value in contract["lifecycle"].values())
    assert contract["contract_fingerprint"] == fingerprint(
        {key: value for key, value in contract.items() if key != "contract_fingerprint"}
    )


def test_freeze_has_all_required_fingerprints_and_detects_mutation() -> None:
    freeze = _freeze()

    assert verify_contract_freeze(freeze) is True
    for key in (
        "contract_fingerprint",
        "code_fingerprint",
        "feature_contract_fingerprint",
        "outcome_contract_fingerprint",
        "universe_fingerprint",
        "identity_contract_fingerprint",
        "dependency_contract_fingerprint",
        "dataset_fingerprint",
        "stage_split_fingerprint",
        "safe_zone_fingerprint",
        "event_pit_availability_fingerprint",
    ):
        assert freeze[key]
    changed = json.loads(canonical_json(freeze))
    changed["full_development_scan_started"] = True
    assert verify_contract_freeze(changed) is False


def test_feature_snapshot_is_causal_deterministic_and_has_no_score() -> None:
    frame = _history()
    position = 300
    first = _feature(frame, position)
    changed_future = frame.copy()
    changed_future.iloc[position + 1 :, changed_future.columns.get_loc("Close")] *= 5
    changed_future.iloc[position + 1 :, changed_future.columns.get_loc("High")] *= 5
    second = _feature(changed_future, position)

    assert first == second
    assert first["feature_fingerprint"] == second["feature_fingerprint"]
    assert first["history_end_day"] == first["signal_day"]
    assert first["candidate_selected_from_outcome"] is False
    assert first["predictive_prefilter_used"] is False
    assert first["composite_opportunity_score"] is None
    assert set(first["safe_zones"]) == {
        "safe_zone_version",
        "A",
        "B",
        "C",
        "confirmed_swing_low_count",
        "original_zone_immutable",
    }


def test_event_fact_after_decision_is_rejected() -> None:
    frame = _history()
    position = 300
    day = frame.index[position].date().isoformat()

    with pytest.raises(MultiAssetDiscoveryContractError, match="Zukünftiger Event-Fakt"):
        build_feature_snapshot(
            asset=_asset(),
            frame=frame,
            decision_position=position,
            decision_time=f"{day}T23:59:59+00:00",
            dataset_fingerprint="dataset-test-v1",
            event_facts=[
                {
                    "known_at": "2026-01-01T00:00:00+00:00",
                    "published_at": "2026-01-01T00:00:00+00:00",
                    "effective_at": "2026-01-01T00:00:00+00:00",
                    "source": "test",
                    "coverage_status": "AVAILABLE",
                    "pit_eligible": True,
                }
            ],
        )


def test_outcome_uses_next_open_252_observations_and_separate_measurements() -> None:
    frame = _history()
    position = 300
    feature = _feature(frame, position)
    outcome = build_outcome(feature_snapshot=feature, frame=frame)

    assert outcome["entry_day"] == frame.index[position + 1].date().isoformat()
    assert outcome["entry_open"] == pytest.approx(frame.iloc[position + 1]["Open"])
    assert outcome["observations_available"] == 252
    assert outcome["status"] == "COMPLETE"
    assert set(outcome["checkpoints"]) == {"20", "60", "120", "252"}
    assert set(outcome["r_level_hits"]) == {"1.0", "2.0", "3.0"}
    assert set(outcome["deterioration"]) == {
        "PRICE_STRUCTURE",
        "MOMENTUM",
        "VOLATILITY",
        "LIQUIDITY",
        "EVENT",
    }
    for zone in outcome["safe_zone_breaches"].values():
        if zone["status"] == "AVAILABLE":
            assert "intraday_breach_observation" in zone
            assert "close_breach_observation" in zone
    assert outcome["protective_ratchet"]["never_lowered"] is True
    assert outcome["future_features_written_to_feature_store"] is False
    assert outcome["no_intrabar_order_invented"] is True


def test_outcome_censors_at_stage_boundary_without_reading_validation() -> None:
    frame = _history()
    index = pd.to_datetime(frame.index)
    position = int(np.flatnonzero(index == pd.Timestamp("2021-12-15"))[0])
    feature = _feature(frame, position)
    outcome = build_outcome(feature_snapshot=feature, frame=frame)

    assert outcome["research_split"] == "development"
    assert outcome["status"] == "CENSORED_AT_STAGE_BOUNDARY"
    assert outcome["outcome_end_day"] <= "2021-12-31"
    assert outcome["observations_available"] < 252
    assert outcome["checkpoints"]["252"] is None


def test_fx_missingness_is_explicit_and_not_imputed() -> None:
    feature = _feature(_history(calendar=True), 300, asset_class="FX")

    assert feature["features"]["volume_ratio_20"] == {
        "status": "STRUCTURAL_NOT_APPLICABLE",
        "value": None,
        "reason": "FX_DAILY_VOLUME_UNRELIABLE",
    }
    assert feature["features"]["event_context"]["status"] == "UNKNOWN"
    assert feature["features"]["fundamental_context"]["status"] == "UNAVAILABLE"


def test_fx_orientation_and_crypto_utc_decision_are_explicitly_causal() -> None:
    inverse = fx_pair_contract(
        "EUR",
        "USD",
        source_ticker="USDEUR=X",
        source_base_currency="USD",
        source_quote_currency="EUR",
    )
    normalized = normalize_fx_ohlc(
        inverse,
        {"open": 0.8, "high": 0.82, "low": 0.79, "close": 0.81},
    )
    crypto = _feature(_history(calendar=True), 300, asset_class="CRYPTO")

    assert inverse["source_is_inverse"] is True
    assert normalized == pytest.approx(
        {
            "open": 1 / 0.8,
            "high": 1 / 0.79,
            "low": 1 / 0.82,
            "close": 1 / 0.81,
        }
    )
    assert crypto["decision_time"].endswith("+00:00")
    assert crypto["known_at_lte_decision_time"] is True


def test_dependency_groups_overlaps_and_unknowns_contribute_zero() -> None:
    cases = [
        {
            "case_id": "a",
            "listing_id": "listing-a",
            "issuer_id": "issuer-a",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2020-01-01",
            "entry_day": "2020-01-02",
            "outcome_end_day": "2020-12-31",
        },
        {
            "case_id": "b",
            "listing_id": "listing-a",
            "issuer_id": "issuer-a",
            "mapping_status": "VERIFIED",
            "dependency_status": "KNOWN",
            "signal_day": "2020-06-01",
            "entry_day": "2020-06-02",
            "outcome_end_day": "2021-05-31",
        },
        {
            "case_id": "unknown",
            "listing_id": "listing-u",
            "issuer_id": None,
            "mapping_status": "UNRESOLVED",
            "dependency_status": "UNKNOWN",
            "signal_day": "2020-01-01",
            "entry_day": "2020-01-02",
            "outcome_end_day": "2020-12-31",
        },
    ]
    report = temporal_dependency_report(cases)

    overlap = next(item for item in report["temporal_listing_clusters"] if item["listing_id"] == "listing-a")
    assert overlap["case_ids"] == ["a", "b"]
    assert report["raw_n"] == 3
    assert report["issuer_adjusted"]["effective_independent_issuer_count"] == 1
    assert report["unknown_dependency_contribution_to_effective_n"] == 0
    assert report["effective_n_le_raw_n"] is True


def test_feature_and_outcome_stores_are_separate_append_only_and_resumable(tmp_path) -> None:
    frame = _history()
    feature = _feature(frame, 300)
    outcome = build_outcome(feature_snapshot=feature, frame=frame)
    dependency = temporal_dependency_report([outcome])
    feature_path = tmp_path / "features.sqlite3"
    outcome_path = tmp_path / "outcomes.sqlite3"

    first_feature = record_freeze_and_features(_freeze(), [feature], path=feature_path)
    second_feature = record_freeze_and_features(_freeze(), [feature], path=feature_path)
    first_outcome = record_outcomes_and_dependency([outcome], dependency, path=outcome_path)
    second_outcome = record_outcomes_and_dependency([outcome], dependency, path=outcome_path)
    audit = audit_pilot_stores(feature_path=feature_path, outcome_path=outcome_path)

    assert first_feature["features_inserted"] == 1
    assert second_feature["features_inserted"] == 0
    assert first_outcome["outcomes_inserted"] == 1
    assert second_outcome["outcomes_inserted"] == 0
    assert audit["physically_separate_paths"] is True
    assert audit["outcome_columns_absent_from_feature_store"] is True
    assert audit["feature_columns_absent_from_outcome_store"] is True
    with sqlite3.connect(feature_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute("UPDATE feature_rows SET signal_day='2099-01-01'")


def test_readiness_evaluator_never_starts_development() -> None:
    freeze = _freeze()
    features = [
        {
            "asset_class": asset_class,
            "feature_fingerprint": f"feature-{index}",
            "safe_zones": {
                "safe_zone_version": "v1",
                "A": {},
                "B": {},
                "C": {},
                "confirmed_swing_low_count": 1,
                "original_zone_immutable": True,
            },
            "predictive_prefilter_used": False,
            "composite_opportunity_score": None,
            "full_development_scan_started": False,
        }
        for index, asset_class in enumerate(
            ["EQUITIES", "EQUITIES", "ETF", "ETF", "FX", "FX", "FX", "CRYPTO", "CRYPTO", "CRYPTO", "EQUITIES"]
        )
    ]
    outcomes = [
        {
            "signal_day": "2020-01-01",
            "entry_day": "2020-01-02",
            "feature_fingerprint": f"feature-{index}",
            "status": "CENSORED_AT_STAGE_BOUNDARY" if index == 10 else "COMPLETE",
            "protective_ratchet": {"never_lowered": True},
            "safe_zone_breaches": {
                "C": {
                    "status": "AVAILABLE",
                    "intraday_breach_observation": None,
                    "close_breach_observation": None,
                }
            },
            "checkpoints": {"20": {}, "60": {}, "120": {}, "252": {}},
        }
        for index in range(11)
    ]
    dependency = {
        "unknown_dependency_contribution_to_effective_n": 0,
        "effective_n_le_raw_n": True,
    }
    store_audit = {
        "physically_separate_paths": True,
        "outcome_columns_absent_from_feature_store": True,
        "feature_columns_absent_from_outcome_store": True,
        "feature_store_quick_check": "ok",
        "outcome_store_quick_check": "ok",
    }
    report = evaluate_integrity_pilot(
        freeze=freeze,
        features=features,
        outcomes=outcomes,
        dependency=dependency,
        store_audit=store_audit,
        deterministic_replay_match=True,
    )

    assert report["status"] == "READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT"
    assert report["full_development_scan_started"] is False
    assert report["validation_opened"] is False
    assert report["performance_claim"] is None


def test_source_ohlc_anomaly_blocks_development_readiness_without_repair() -> None:
    freeze = _freeze()
    features = [
        {
            "asset_class": asset_class,
            "feature_fingerprint": f"feature-{index}",
            "safe_zones": {
                "safe_zone_version": "v1",
                "A": {},
                "B": {},
                "C": {},
                "confirmed_swing_low_count": 1,
                "original_zone_immutable": True,
            },
            "source_integrity": {
                "ohlc_envelope_anomaly_count_to_decision": 1 if asset_class == "FX" else 0,
                "provider_values_repaired": False,
            },
            "predictive_prefilter_used": False,
            "composite_opportunity_score": None,
            "full_development_scan_started": False,
        }
        for index, asset_class in enumerate(
            ["EQUITIES", "EQUITIES", "ETF", "ETF", "FX", "FX", "FX", "CRYPTO", "CRYPTO", "CRYPTO", "EQUITIES"]
        )
    ]
    outcomes = [
        {
            "signal_day": "2020-01-01",
            "entry_day": "2020-01-02",
            "feature_fingerprint": f"feature-{index}",
            "status": "CENSORED_AT_STAGE_BOUNDARY" if index == 10 else "COMPLETE",
            "protective_ratchet": {"never_lowered": True},
            "safe_zone_breaches": {
                "C": {
                    "status": "AVAILABLE",
                    "intraday_breach_observation": None,
                    "close_breach_observation": None,
                }
            },
            "checkpoints": {"20": {}, "60": {}, "120": {}, "252": {}},
            "source_integrity": {
                "ohlc_envelope_anomaly_count_in_outcome": 1 if index == 4 else 0,
                "provider_values_repaired": False,
            },
        }
        for index in range(11)
    ]
    report = evaluate_integrity_pilot(
        freeze=freeze,
        features=features,
        outcomes=outcomes,
        dependency={
            "unknown_dependency_contribution_to_effective_n": 0,
            "effective_n_le_raw_n": True,
        },
        store_audit={
            "physically_separate_paths": True,
            "outcome_columns_absent_from_feature_store": True,
            "feature_columns_absent_from_outcome_store": True,
            "feature_store_quick_check": "ok",
            "outcome_store_quick_check": "ok",
        },
        deterministic_replay_match=True,
    )

    assert report["gates"]["no_ohlc_envelope_anomalies"] is False
    assert report["status"] == "NOT_READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT"
    assert report["full_development_scan_started"] is False
