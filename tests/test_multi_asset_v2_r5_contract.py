from __future__ import annotations

import copy
import json

import pytest

from multi_asset_v2_r5_contract import load_contract, validate_contract_structure, validate_freeze


def test_canonical_r5_freeze_and_all_provenance_pass() -> None:
    contract, fingerprint = load_contract()
    result = validate_freeze()
    assert result["status"] == "PASS_R5_FREEZE_VALID"
    assert result["contract_fingerprint"] == fingerprint
    assert result["feature_family_count"] == 19
    assert result["outcomes_opened"] is False
    assert all(item["status"] in {
        "ACTIVE_PIT", "ACTIVE_PIT_LIMITED_SCOPE", "SHADOW", "UNAVAILABLE",
        "STRUCTURAL_NOT_APPLICABLE",
    } for item in contract["capabilities"])


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("outcome_contract", "checkpoints"), [20, 60, 252], "horizon/outcome"),
        (("missingness_contract", "missing_never_becomes_false_or_zero"), False, "missingness"),
        (("stage_contract", "validation_opened"), True, "stage sealing"),
        (("review_quality_c_gate", "ranking_by_profit"), True, "review gate"),
        (("r6_execution_contract", "sqlite_writer_count"), 2, "execution safety"),
    ],
)
def test_r5_scientific_or_safety_mutations_fail_closed(path, value, message) -> None:
    contract, _ = load_contract()
    changed = copy.deepcopy(contract)
    changed[path[0]][path[1]] = value
    with pytest.raises(ValueError, match=message):
        validate_contract_structure(changed)


def test_r5_duplicate_family_and_malformed_fingerprint_fail_closed() -> None:
    contract, _ = load_contract()
    changed = copy.deepcopy(contract)
    changed["capabilities"].append(copy.deepcopy(changed["capabilities"][0]))
    with pytest.raises(ValueError, match="families"):
        validate_contract_structure(changed)
    changed = copy.deepcopy(contract)
    changed["sources"]["equity_etf"]["dataset_fingerprint"] = "short"
    with pytest.raises(ValueError, match="SHA-256"):
        validate_contract_structure(changed)
