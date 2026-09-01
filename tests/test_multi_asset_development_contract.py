from __future__ import annotations

import copy

from multi_asset_development_contract import (
    DEVELOPMENT_CONTRACT_VERSION,
    build_development_contract_artifact,
    build_development_contract_diff,
    development_code_fingerprint,
    load_development_contract,
    verify_development_contract_artifact,
)
from multi_asset_discovery_v1 import file_sha256, load_discovery_contract


def test_pilot_contract_remains_immutable_while_development_is_new_version() -> None:
    parent_path = __import__("pathlib").Path("config/multi_asset_discovery_v1.json")
    before = file_sha256(parent_path)
    parent = load_discovery_contract()
    development = load_development_contract()
    after = file_sha256(parent_path)

    assert before == after
    assert parent["research_role"] == "technical_integrity_pilot_only"
    assert parent["candidate_generation"]["full_development_scan_allowed"] is False
    assert development["contract_version"] == DEVELOPMENT_CONTRACT_VERSION
    assert development["contract_fingerprint"] != parent["contract_fingerprint"]
    assert development["parent_contract"]["fingerprint"] == parent["contract_fingerprint"]


def test_contract_diff_contains_only_authorized_execution_changes() -> None:
    parent = load_discovery_contract()
    development = load_development_contract()
    report = build_development_contract_diff(parent=parent, development=development)

    assert report["status"] == "PASS"
    assert report["research_semantics_diff_count"] == 0
    assert report["differences"]
    assert {item["classification"] for item in report["differences"]} <= {
        "A_EXECUTION_SCOPE",
        "B_RUNTIME_STORE",
        "C_SCHEDULING_RESUME",
    }
    assert "C_SCHEDULING_RESUME" in {
        item["classification"] for item in report["differences"]
    }


def test_semantic_mutation_fails_the_diff_gate() -> None:
    parent = load_discovery_contract()
    development = copy.deepcopy(load_development_contract())
    development["safe_zone_contract"]["zone_c_atr_buffer"] = 0.75
    report = build_development_contract_diff(parent=parent, development=development)

    assert report["status"] == "FAIL"
    assert report["research_semantics_diff_count"] == 1
    assert report["unauthorized_differences"][0]["path"] == (
        "safe_zone_contract.zone_c_atr_buffer"
    )


def test_development_scope_opens_only_execution_and_keeps_lifecycle_closed() -> None:
    contract = load_development_contract()

    assert contract["research_role"] == "development"
    assert contract["candidate_generation"]["mode"] == "full_eligibility_universe"
    assert contract["candidate_generation"]["full_development_scan_allowed"] is True
    assert contract["pilot_contract"]["large_scan_allowed"] is True
    assert "development" in contract["store_contract"]["feature_store"]
    assert "development" in contract["store_contract"]["outcome_store"]
    assert all(value is False for value in contract["lifecycle"].values())
    assert contract["development_execution"]["validation_access_allowed"] is False
    assert contract["development_execution"]["holdout_access_allowed"] is False
    assert contract["development_execution"]["broker_output_allowed"] is False


def test_development_contract_artifact_is_fingerprinted_and_parent_linked() -> None:
    artifact, diff = build_development_contract_artifact(
        git_branch="codex/test",
        git_commit="a" * 40,
        frozen_at="2026-09-01T12:00:00+00:00",
    )

    assert verify_development_contract_artifact(artifact) is True
    assert artifact["research_semantics_diff_count"] == 0
    assert diff["status"] == "PASS"
    assert artifact["development_code_fingerprint"] == development_code_fingerprint()
