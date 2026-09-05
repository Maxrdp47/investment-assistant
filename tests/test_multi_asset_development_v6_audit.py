from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

import multi_asset_development_v6_store as store
from multi_asset_development_v6_audit import (
    DevelopmentV6AuditError,
    build_v6_full_audit,
    verify_self_fingerprinted_artifact,
)
from multi_asset_development_v6_contract import (
    DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
    DEVELOPMENT_V6_CONTRACT_VERSION,
)
from multi_asset_development_v6_outcomes import (
    V6_OUTCOME_POLICY_VERSION,
    V6_OUTCOME_VERSION,
)
from multi_asset_discovery_v1 import fingerprint


RUN_ID = "madv6-audit-test"
DEPENDENCY_VERSION = "dependency-policy-v1"
DEPENDENCY_FINGERPRINT = "dependency-policy-fp"


def _plan() -> dict[str, object]:
    payload: dict[str, object] = {
        "total_planned_work_units": 2,
        "units": [
            {
                "work_unit_id": "unit-1",
                "asset_key": "EQUITIES:AAA",
                "asset_class": "EQUITIES",
                "symbol": "AAA",
                "period_start": "2020-01-01",
                "period_end": "2020-03-31",
            },
            {
                "work_unit_id": "unit-2",
                "asset_key": "CRYPTO:NO-DATA",
                "asset_class": "CRYPTO",
                "symbol": "NO-DATA",
                "period_start": "2020-01-01",
                "period_end": "2020-03-31",
            },
        ],
    }
    payload["work_plan_fingerprint"] = fingerprint(payload["units"])
    return payload


def _manifest(
    *,
    contract_artifact: dict[str, object],
    input_precheck: dict[str, object],
) -> dict[str, object]:
    contract = dict(contract_artifact["contract"])
    references = dict(contract["reference_fingerprints"])
    payload: dict[str, object] = {
        "run_id": RUN_ID,
        "development_contract_version": contract["contract_version"],
        "development_contract_fingerprint": contract["contract_fingerprint"],
        "contract_artifact_fingerprint": contract_artifact["artifact_fingerprint"],
        "combined_input_fingerprint": references["combined_input_fingerprint"],
        "equity_etf_projection_fingerprint": references[
            "equity_etf_projection_fingerprint"
        ],
        "crypto_projection_fingerprint": references["crypto_projection_fingerprint"],
        "fx_projection_fingerprint": references["fx_projection_fingerprint"],
        "input_precheck_artifact_fingerprint": input_precheck[
            "artifact_fingerprint"
        ],
        "code_fingerprint": references["development_code_fingerprint"],
        "identity_fingerprint": references["identity_registry_fingerprint"],
        "dependency_policy_fingerprint": references[
            "historical_dependency_policy_fingerprint"
        ],
        "universe_fingerprint": "universe-fp",
        "work_plan_fingerprint": _plan()["work_plan_fingerprint"],
        "commit": "abc123",
        "worker_count": 2,
        "sqlite_writer_count": 1,
        "total_planned_work_units": 2,
        "started_at": "2026-09-05T18:00:00+00:00",
        "development_only": True,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
        "automatic_orders_allowed": False,
    }
    payload["run_manifest_fingerprint"] = fingerprint(payload)
    return payload


def _provenance_bundle(
    root: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, Path],
    dict[str, object],
]:
    source_names = (
        "equity_etf_store",
        "crypto_store",
        "fx_store",
        "dataset_manifest",
        "identity_store",
        "equity_etf_artifact",
        "crypto_artifact",
        "fx_artifact",
        "crypto_frozen:crypto/AAA.csv",
    )
    paths: dict[str, Path] = {}
    source_hashes: dict[str, str] = {}
    for index, name in enumerate(source_names):
        path = root / "protected" / name.replace(":", "_").replace("/", "_")
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"protected-{index}-{name}\n".encode()
        path.write_bytes(content)
        paths[name] = path
        source_hashes[name] = hashlib.sha256(content).hexdigest()
    implementation_path = (root / "frozen_implementation.py").resolve()
    implementation_content = b"FROZEN_IMPLEMENTATION = True\n"
    implementation_path.write_bytes(implementation_content)
    implementation_hashes = {
        str(implementation_path): hashlib.sha256(implementation_content).hexdigest()
    }

    gap_policy: dict[str, object] = {
        "version": "gap-policy-v1",
        "entry_may_cross_segment_boundary": False,
        "outcome_may_cross_segment_boundary": False,
    }
    gap_policy["fingerprint"] = fingerprint(gap_policy)
    inputs = {
        "combined_input_fingerprint": "input-fp",
        "equity_etf_projection_fingerprint": "equity-fp",
        "crypto_projection_fingerprint": "crypto-fp",
        "fx_projection_fingerprint": "fx-fp",
        "equity_etf_store_sha256": source_hashes["equity_etf_store"],
        "crypto_store_sha256": source_hashes["crypto_store"],
        "fx_store_sha256": source_hashes["fx_store"],
        "source_dataset_manifest_sha256": source_hashes["dataset_manifest"],
        "source_dataset_fingerprint": "source-dataset-fp",
        "identity_store_sha256": source_hashes["identity_store"],
        "identity_registry_fingerprint": "identity-fp",
        "gap_policy_fingerprint": gap_policy["fingerprint"],
        "implementation_fingerprint": fingerprint(implementation_hashes),
    }
    precheck: dict[str, object] = {
        "version": "input-precheck-v1",
        "status": "PASS",
        "contract_inputs": inputs,
        "checks": {"all_sources_valid": True, "no_imputation": True},
        "gap_policy": gap_policy,
        "source_sha256_before": source_hashes,
        "source_sha256_after": source_hashes,
        "implementation_paths": list(implementation_hashes),
        "implementation_sha256": implementation_hashes,
        "missing_implementation_files": [],
    }
    precheck["artifact_fingerprint"] = fingerprint(precheck)
    references = {
        **inputs,
        "dataset_fingerprint": inputs["combined_input_fingerprint"],
        "dataset_manifest_sha256": inputs["source_dataset_manifest_sha256"],
        "fx_dataset_fingerprint": inputs["fx_projection_fingerprint"],
        "development_code_fingerprint": inputs["implementation_fingerprint"],
        "input_precheck_artifact_fingerprint": precheck["artifact_fingerprint"],
        "historical_dependency_policy_version": DEPENDENCY_VERSION,
        "historical_dependency_policy_fingerprint": DEPENDENCY_FINGERPRINT,
    }
    contract: dict[str, object] = {
        "contract_version": DEVELOPMENT_V6_CONTRACT_VERSION,
        "reference_fingerprints": references,
    }
    contract["contract_fingerprint"] = fingerprint(contract)
    artifact: dict[str, object] = {
        "version": DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
        "contract": contract,
        "contract_fingerprint": contract["contract_fingerprint"],
    }
    artifact["artifact_fingerprint"] = fingerprint(artifact)
    manifest = _manifest(contract_artifact=artifact, input_precheck=precheck)
    return artifact, precheck, paths, manifest


def _feature(
    *,
    contract: dict[str, object],
    invalid_fingerprint: bool = False,
    input_provenance_override: dict[str, object] | None = None,
) -> dict[str, object]:
    references = dict(contract["reference_fingerprints"])
    source_fingerprint = fingerprint(
        {
            "combined_input_fingerprint": references["combined_input_fingerprint"],
            "projection_fingerprint": references[
                "equity_etf_projection_fingerprint"
            ],
            "asset_key": "EQUITIES:AAA",
        }
    )
    identity = {
        "asset_id": "asset-1",
        "signal_day": "2020-03-02",
        "contract_version": contract["contract_version"],
        "dataset_fingerprint": source_fingerprint,
    }
    payload: dict[str, object] = {
        **identity,
        "case_id": f"mad1-{fingerprint(identity)[:32]}",
        "feature_version": "feature-v1",
        "symbol": "AAA",
        "asset_class": "EQUITIES",
        "listing_id": "listing-1",
        "issuer_id": "issuer-1",
        "mapping_status": "MAPPED",
        "dependency_status": "UNKNOWN",
        "historical_dependency_policy_version": DEPENDENCY_VERSION,
        "historical_dependency_policy_fingerprint": DEPENDENCY_FINGERPRINT,
        "historical_dependency_reason": "HISTORICAL_RELATION_NOT_VERIFIED",
        "decision_time": "2020-03-02T23:59:59+00:00",
        "known_at_lte_decision_time": True,
        "research_split": "development",
        "history_end_day": "2020-03-02",
        "source_integrity": {
            "ohlc_envelope_anomaly_count_to_decision": 0,
            "provider_values_repaired": False,
        },
        "features": {
            "rsi_14": {
                "status": "AVAILABLE",
                "value": 55.0,
                "known_at": "2020-03-02T23:59:59+00:00",
            }
        },
        "market_regime": "UPTREND",
        "safe_zones": {
            "A": {"status": "AVAILABLE", "lower": 98.0},
            "B": {"status": "UNAVAILABLE", "reason": "NO_STRUCTURE"},
            "C": {"status": "AVAILABLE", "lower": 97.0},
        },
        "sell_zones": {
            "A": {"status": "AVAILABLE", "value": 105.0},
            "B": {"status": "UNAVAILABLE", "reason": "NO_STRUCTURE"},
            "C": {"status": "AVAILABLE", "value": 106.0},
        },
        "candidate_selected_from_outcome": False,
        "predictive_prefilter_used": False,
        "full_development_scan_started": False,
        "input_provenance": input_provenance_override
        or {
            "combined_input_fingerprint": references[
                "combined_input_fingerprint"
            ],
            "projection_fingerprint": references[
                "equity_etf_projection_fingerprint"
            ],
            "source_fingerprint": source_fingerprint,
            "gap_policy_fingerprint": references["gap_policy_fingerprint"],
            "provider_values_repaired": False,
        },
    }
    payload["feature_fingerprint"] = (
        "deliberately-wrong" if invalid_fingerprint else fingerprint(payload)
    )
    return payload


def _outcome(feature: dict[str, object]) -> dict[str, object]:
    checkpoint = {
        "observations": 20,
        "end_day": "2020-03-30",
        "return_pct": 1.0,
        "mfe_pct": 2.0,
        "mae_pct": -1.0,
        "mfe_atr": 1.0,
        "mae_atr": -0.5,
        "mfe_r": 0.66,
        "mae_r": -0.33,
    }
    payload: dict[str, object] = {
        "outcome_version": V6_OUTCOME_VERSION,
        "outcome_policy_version": V6_OUTCOME_POLICY_VERSION,
        "contract_version": feature["contract_version"],
        "case_id": feature["case_id"],
        "feature_fingerprint": feature["feature_fingerprint"],
        "asset_id": feature["asset_id"],
        "symbol": feature["symbol"],
        "asset_class": feature["asset_class"],
        "listing_id": feature["listing_id"],
        "issuer_id": feature["issuer_id"],
        "mapping_status": feature["mapping_status"],
        "dependency_status": feature["dependency_status"],
        "research_split": "development",
        "signal_day": feature["signal_day"],
        "status": "COMPLETE",
        "reason": None,
        "censoring_reason": None,
        "measurement_status": "COMPLETE",
        "measurement_reason": None,
        "r_metrics_status": "AVAILABLE",
        "r_metrics_reason": None,
        "atr_metrics_status": "AVAILABLE",
        "atr_metrics_reason": None,
        "input_segment": {
            "segment_id": "segment-1",
            "start_day": "2019-01-01",
            "end_day": "2021-12-31",
            "declared_end_reason": None,
            "single_segment_verified": True,
        },
        "entry_day": "2020-03-03",
        "entry_open": 100.0,
        "entry_gap_atr": 0.1,
        "structural_risk": 3.0,
        "mfe_pct": 2.0,
        "mae_pct": -1.0,
        "mfe_atr": 1.0,
        "mae_atr": -0.5,
        "mfe_r": 0.66,
        "mae_r": -0.33,
        "final_return_pct": 1.0,
        "r_level_hits": {"1.0": None, "2.0": None, "3.0": None},
        "checkpoints": {"20": checkpoint, "60": None, "120": None, "252": None},
        "safe_zone_breaches": {
            "A": {
                "status": "AVAILABLE",
                "intraday_breach_observation": None,
                "close_breach_observation": None,
            }
        },
        "sell_zone_measurements": {
            "A": {"status": "AVAILABLE", "hit_observation": None, "max_overshoot_pct": 0.0}
        },
        "source_integrity": {
            "ohlc_envelope_anomaly_count_in_outcome": 0,
            "provider_values_repaired": False,
            "cross_segment_observations_used": 0,
        },
        "path_quality": {"peak_giveback_r": 0.2, "final_giveback_r": 0.3},
        "future_features_written_to_feature_store": False,
        "no_intrabar_order_invented": True,
        "cross_segment_observations_used": 0,
    }
    payload["outcome_fingerprint"] = fingerprint(payload)
    return payload


def _completed_stores(
    root: Path,
    *,
    contract: dict[str, object],
    manifest: dict[str, object],
    invalid_fingerprint: bool = False,
    input_provenance_override: dict[str, object] | None = None,
    feature_overrides: dict[str, object] | None = None,
    skip_reason_code: str = "EXPECTED_NO_DEVELOPMENT_DATA",
    skip_reason: str = "no Development rows",
) -> tuple[Path, Path, Path]:
    feature_path = root / "features.sqlite3"
    outcome_path = root / "outcomes.sqlite3"
    control_path = root / "control.sqlite3"
    store.initialize_v6_run(
        run_manifest=manifest,
        work_plan=_plan(),
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    first_batch = store.claim_next_asset_batch(control_path=control_path, run_id=RUN_ID)
    if first_batch[0]["asset_class"] == "CRYPTO":
        store.skip_work_unit(
            writer_pid=os.getpid(),
            run_id=RUN_ID,
            unit=first_batch[0],
            reason_code=skip_reason_code,
            reason=skip_reason,
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
        units = store.claim_next_asset_batch(control_path=control_path, run_id=RUN_ID)
    else:
        units = first_batch
    feature = _feature(
        contract=contract,
        invalid_fingerprint=invalid_fingerprint,
        input_provenance_override=input_provenance_override,
    )
    if feature_overrides:
        feature.update(feature_overrides)
        feature.pop("feature_fingerprint", None)
        feature["feature_fingerprint"] = fingerprint(feature)
    store.persist_and_complete_work_unit(
        writer_pid=os.getpid(),
        run_id=RUN_ID,
        unit=units[0],
        features=[feature],
        outcomes=[_outcome(feature)],
        summary={
            "r_na_cases": 0,
            "censored_cases": 0,
            "missing_reference_entry": 0,
            "missingness_exclusions": 0,
        },
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
    )
    # If lexical ordering changes, finish the remaining no-data asset here.
    remaining = store.claim_next_asset_batch(control_path=control_path, run_id=RUN_ID)
    if remaining:
        store.skip_work_unit(
            writer_pid=os.getpid(),
            run_id=RUN_ID,
            unit=remaining[0],
            reason_code=skip_reason_code,
            reason=skip_reason,
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
    assert store.mark_run_complete(control_path=control_path, run_id=RUN_ID)
    return feature_path, outcome_path, control_path


def test_full_v6_audit_checks_all_stores_receipts_and_payloads(tmp_path: Path) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    artifact = tmp_path / "audit.json"
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=artifact,
        created_at="2026-09-05T20:00:00+00:00",
    )
    assert result["status"] == "PASS"
    assert result["no_sampling"] is True
    assert result["counts"]["audited_payload_pairs"] == 1
    assert result["counts"]["work_units"] == 2
    assert result["counts"]["receipts"] == 2
    assert result["work_unit_classification_counts"] == {
        "COMPLETED_RECONCILED": 1,
        "SKIPPED_WITH_EMPTY_RECEIPT": 1,
    }
    exclusions = result["skipped_work_unit_exclusions"]
    assert exclusions["total_skipped_work_units"] == 1
    assert exclusions["classified_skipped_work_units"] == 1
    assert exclusions["all_skipped_units_reconciled"] is True
    assert exclusions["by_reason_code"]["EXPECTED_NO_DEVELOPMENT_DATA"] == {
        "work_units": 1,
        "by_asset_class": {"CRYPTO": 1},
    }
    assert exclusions["by_reason_code"][
        "NO_GAP_SAFE_220_OBSERVATION_HISTORY"
    ] == {"work_units": 0, "by_asset_class": {}}
    assert result["issue_count"] == 0
    assert all(result["gates"].values())
    assert result["provenance_bindings"]["protected_sources"][
        "all_hashes_match"
    ] is True
    assert result["provenance_bindings"]["protected_implementation"][
        "all_hashes_match"
    ] is True
    assert result["gates"]["all_implementation_hashes_reverified"] is True
    assert result["gates"][
        "store_metadata_bound_to_contract_input_and_run_manifest"
    ] is True
    assert result["per_payload_provenance_contract"][
        "outcome_input_provenance_is_transitive_via_feature_fingerprint"
    ] is True
    assert result["per_payload_provenance_contract"][
        "contract_fingerprint_present_in_feature_payload"
    ] is False
    assert result["per_payload_provenance_contract"][
        "contract_fingerprint_present_in_outcome_payload"
    ] is False
    assert verify_self_fingerprinted_artifact(result)


def test_full_v6_audit_accepts_and_reports_gap_safe_history_skip_code(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
        skip_reason_code="NO_GAP_SAFE_220_OBSERVATION_HISTORY",
    )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )

    assert result["status"] == "PASS"
    assert result["skipped_work_unit_exclusions"]["by_reason_code"][
        "NO_GAP_SAFE_220_OBSERVATION_HISTORY"
    ] == {"work_units": 1, "by_asset_class": {"CRYPTO": 1}}


def test_full_v6_audit_rejects_unapproved_skip_reason_without_relabeling(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
        skip_reason_code="FREE_TEXT_GUESS",
    )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )

    assert result["status"] == "FAIL"
    assert result["issues"][
        "skipped_unit_unapproved_reason_code:FREE_TEXT_GUESS"
    ] == 1
    assert result["gates"][
        "all_skipped_units_have_allowed_reconciled_reason"
    ] is False
    assert result["skipped_work_unit_exclusions"][
        "classified_skipped_work_units"
    ] == 0


def test_full_v6_audit_rejects_empty_skip_reason_text(tmp_path: Path) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
        skip_reason="",
    )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )

    assert result["status"] == "FAIL"
    assert result["issues"]["skipped_unit_without_reason_text"] == 1
    assert result["skipped_work_unit_exclusions"][
        "all_skipped_units_reconciled"
    ] is False


def test_full_v6_audit_artifact_is_exactly_once_and_idempotent(tmp_path: Path) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    artifact = tmp_path / "audit.json"
    first = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=artifact,
        created_at="first",
    )
    second = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=artifact,
        created_at="later",
    )
    assert first == second
    assert second["created_at"] == "first"


def test_full_v6_audit_fails_closed_on_payload_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
        invalid_fingerprint=True,
    )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="2026-09-05T20:00:00+00:00",
    )
    assert result["status"] == "FAIL"
    assert result["issues"]["feature_payload_fingerprint_mismatch"] == 1


def test_full_v6_audit_rehashes_every_protected_source_and_detects_mutation(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    protected["crypto_frozen:crypto/AAA.csv"].write_text(
        "mutated after precheck\n", encoding="utf-8"
    )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )
    assert result["status"] == "FAIL"
    assert result["issues"][
        "protected_source_hash_mismatch:crypto_frozen:crypto/AAA.csv"
    ] == 1
    assert result["gates"]["all_protected_input_hashes_reverified"] is False


def test_full_v6_audit_rehashes_implementation_and_detects_mutation(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    implementation_path = Path(str(precheck["implementation_paths"][0]))
    implementation_path.write_text("FROZEN_IMPLEMENTATION = False\n", encoding="utf-8")
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )
    label = str(implementation_path)
    assert result["status"] == "FAIL"
    assert result["issues"][f"protected_implementation_hash_mismatch:{label}"] == 1
    assert result["gates"]["all_implementation_hashes_reverified"] is False
    evidence = result["provenance_bindings"]["protected_implementation"]
    assert evidence["expected_sha256"][label] != evidence["observed_sha256"][label]


@pytest.mark.parametrize(
    "field",
    (
        "contract_fingerprint",
        "combined_input_fingerprint",
        "run_manifest_fingerprint",
    ),
)
def test_full_v6_audit_rejects_store_metadata_not_bound_to_frozen_chain(
    tmp_path: Path, field: str
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    with sqlite3.connect(feature_path) as connection:
        encoded = str(
            connection.execute(
                "SELECT metadata_json FROM store_metadata LIMIT 1"
            ).fetchone()[0]
        )
        metadata = json.loads(encoded)
        metadata[field] = "wrong-binding"
        connection.execute(
            "INSERT INTO store_metadata VALUES (?,?)",
            (fingerprint(metadata), json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
        )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )
    assert result["status"] == "FAIL"
    assert result["issues"][
        f"provenance_binding_mismatch:feature_store_metadata:{field}"
    ] == 1
    assert result["gates"][
        "store_metadata_bound_to_contract_input_and_run_manifest"
    ] is False


def test_full_v6_audit_rejects_self_valid_but_cross_unbound_contract(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    bad_artifact = json.loads(json.dumps(contract_artifact))
    bad_contract = dict(bad_artifact["contract"])
    bad_references = dict(bad_contract["reference_fingerprints"])
    bad_references["combined_input_fingerprint"] = "other-input-fp"
    bad_contract["reference_fingerprints"] = bad_references
    bad_contract.pop("contract_fingerprint")
    bad_contract["contract_fingerprint"] = fingerprint(bad_contract)
    bad_artifact["contract"] = bad_contract
    bad_artifact["contract_fingerprint"] = bad_contract["contract_fingerprint"]
    bad_artifact.pop("artifact_fingerprint")
    bad_artifact["artifact_fingerprint"] = fingerprint(bad_artifact)
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=bad_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )
    assert result["status"] == "FAIL"
    assert result["issues"][
        "provenance_binding_mismatch:contract_to_precheck:combined_input_fingerprint"
    ] == 1


def test_full_v6_audit_rejects_payload_with_wrong_input_and_dependency_provenance(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
        input_provenance_override={
            "combined_input_fingerprint": "wrong-input",
            "projection_fingerprint": "wrong-projection",
            "source_fingerprint": "wrong-source",
            "gap_policy_fingerprint": "wrong-gap",
            "provider_values_repaired": False,
        },
        feature_overrides={
            "historical_dependency_policy_fingerprint": "wrong-dependency"
        },
    )
    result = build_v6_full_audit(
        run_id=RUN_ID,
        feature_path=feature_path,
        outcome_path=outcome_path,
        control_path=control_path,
        expected_work_plan=_plan(),
        final_contract=contract_artifact,
        input_precheck=precheck,
        expected_run_manifest=manifest,
        protected_source_paths=protected,
        artifact_path=tmp_path / "audit.json",
        created_at="now",
    )
    assert result["status"] == "FAIL"
    for issue in (
        "feature_combined_input_fingerprint_mismatch",
        "feature_projection_fingerprint_mismatch",
        "feature_gap_policy_fingerprint_mismatch",
        "feature_source_fingerprint_mismatch",
        "feature_dependency_policy_fingerprint_mismatch",
    ):
        assert result["issues"][issue] == 1


def test_existing_audit_fastpath_rechecks_current_protected_source_hashes(
    tmp_path: Path,
) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    feature_path, outcome_path, control_path = _completed_stores(
        tmp_path,
        contract=dict(contract_artifact["contract"]),
        manifest=manifest,
    )
    artifact_path = tmp_path / "audit.json"
    common = {
        "run_id": RUN_ID,
        "feature_path": feature_path,
        "outcome_path": outcome_path,
        "control_path": control_path,
        "expected_work_plan": _plan(),
        "final_contract": contract_artifact,
        "input_precheck": precheck,
        "expected_run_manifest": manifest,
        "protected_source_paths": protected,
        "artifact_path": artifact_path,
    }
    assert build_v6_full_audit(**common, created_at="first")["status"] == "PASS"
    protected["identity_store"].write_text("changed\n", encoding="utf-8")
    with pytest.raises(DevelopmentV6AuditError, match="no longer matches"):
        build_v6_full_audit(**common, created_at="retry")


def test_existing_corrupt_audit_is_never_overwritten(tmp_path: Path) -> None:
    contract_artifact, precheck, protected, manifest = _provenance_bundle(tmp_path)
    artifact = tmp_path / "audit.json"
    artifact.write_text('{"artifact_fingerprint":"wrong"}\n', encoding="utf-8")
    with pytest.raises(DevelopmentV6AuditError, match="corrupt"):
        build_v6_full_audit(
            run_id=RUN_ID,
            feature_path=tmp_path / "missing-feature.sqlite3",
            outcome_path=tmp_path / "missing-outcome.sqlite3",
            control_path=tmp_path / "missing-control.sqlite3",
            expected_work_plan=_plan(),
            final_contract=contract_artifact,
            input_precheck=precheck,
            expected_run_manifest=manifest,
            protected_source_paths=protected,
            artifact_path=artifact,
            created_at="now",
        )
