from __future__ import annotations

"""Versioned execution contract for Multi-Asset Discovery v1 Development.

The immutable pilot contract remains the only source of research semantics.
This module applies a small, explicitly whitelisted execution overlay and
fails closed if any research rule differs.
"""

import copy
import json
from pathlib import Path
from typing import Mapping, Sequence

from multi_asset_discovery_v1 import (
    canonical_json,
    file_sha256,
    fingerprint,
    load_discovery_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DEVELOPMENT_OVERLAY = (
    PROJECT_ROOT / "config" / "multi_asset_discovery_development_v1.json"
)
DEVELOPMENT_CONTRACT_VERSION = (
    "multi-asset-opportunity-discovery-development-2026.09.01-v1"
)
DEVELOPMENT_CONTRACT_ARTIFACT_VERSION = (
    "multi-asset-development-contract-artifact-2026.09.01-v1"
)
DEVELOPMENT_CONTRACT_DIFF_VERSION = (
    "multi-asset-development-contract-diff-2026.09.01-v1"
)


class MultiAssetDevelopmentContractError(ValueError):
    """The Development overlay violates the immutable parent contract."""


def development_code_fingerprint() -> str:
    files = (
        PROJECT_ROOT / "config" / "multi_asset_discovery_development_v1.json",
        PROJECT_ROOT / "multi_asset_discovery_v1.py",
        PROJECT_ROOT / "multi_asset_development_contract.py",
        PROJECT_ROOT / "multi_asset_development_execution.py",
        PROJECT_ROOT / "multi_asset_development_runner.py",
        PROJECT_ROOT / "fx_carry_pit.py",
        PROJECT_ROOT / "historical_dependency_policy.py",
        PROJECT_ROOT / "swing_broad_research.py",
        PROJECT_ROOT / "swing_run_lock.py",
        PROJECT_ROOT / "swing_walk_forward_campaign.py",
        PROJECT_ROOT / "config" / "swing_walk_forward_campaign.json",
        PROJECT_ROOT / "scripts" / "run_multi_asset_development.py",
        PROJECT_ROOT / "multi_asset_development_readiness_v2.py",
        PROJECT_ROOT / "scripts" / "run_multi_asset_development_readiness_v2.py",
        PROJECT_ROOT / "scripts" / "run_multi_asset_development.cmd",
        PROJECT_ROOT / "scripts" / "install_multi_asset_development_task.ps1",
    )
    return fingerprint(
        {
            "version": DEVELOPMENT_CONTRACT_VERSION,
            "files": [
                {
                    "path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "sha256": file_sha256(path),
                }
                for path in files
                if path.exists()
            ],
        }
    )


def _load_overlay(path: Path = DEFAULT_DEVELOPMENT_OVERLAY) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("development_contract_version") != DEVELOPMENT_CONTRACT_VERSION:
        raise MultiAssetDevelopmentContractError(
            "Unerwartete Development-Contract-Version."
        )
    return payload


def _apply_execution_overrides(
    parent: Mapping[str, object], overlay: Mapping[str, object]
) -> dict[str, object]:
    derived = copy.deepcopy(dict(parent))
    derived.pop("contract_fingerprint", None)
    overrides = dict(overlay.get("execution_overrides") or {})
    allowed_roots = {
        "research_role",
        "candidate_generation",
        "pilot_contract",
        "store_contract",
    }
    unexpected = sorted(set(overrides) - allowed_roots)
    if unexpected:
        raise MultiAssetDevelopmentContractError(
            f"Nicht erlaubte Override-Wurzeln: {unexpected}"
        )
    derived["contract_version"] = DEVELOPMENT_CONTRACT_VERSION
    derived["research_role"] = overrides.get("research_role")
    for root in ("candidate_generation", "pilot_contract", "store_contract"):
        target = dict(derived.get(root) or {})
        target.update(dict(overrides.get(root) or {}))
        derived[root] = target
    derived["parent_contract"] = {
        "version": overlay.get("parent_contract_version"),
        "fingerprint": overlay.get("parent_contract_fingerprint"),
        "freeze_fingerprint": overlay.get("parent_freeze_fingerprint"),
        "immutable": True,
    }
    references = dict(overlay.get("references") or {})
    references["development_code_fingerprint"] = development_code_fingerprint()
    derived["reference_fingerprints"] = references
    derived["development_execution"] = dict(
        overlay.get("development_execution") or {}
    )
    derived["contract_fingerprint"] = fingerprint(derived)
    return derived


def _recursive_diff(
    parent: object, development: object, path: str = ""
) -> list[dict[str, object]]:
    if isinstance(parent, Mapping) and isinstance(development, Mapping):
        rows: list[dict[str, object]] = []
        keys = sorted(set(parent) | set(development))
        for key in keys:
            child = f"{path}.{key}" if path else str(key)
            if key not in parent:
                if isinstance(development[key], Mapping):
                    rows.extend(_recursive_diff({}, development[key], child))
                else:
                    rows.append(
                        {
                            "path": child,
                            "change": "ADDED",
                            "parent": None,
                            "development": development[key],
                        }
                    )
            elif key not in development:
                if isinstance(parent[key], Mapping):
                    rows.extend(_recursive_diff(parent[key], {}, child))
                else:
                    rows.append(
                        {
                            "path": child,
                            "change": "REMOVED",
                            "parent": parent[key],
                            "development": None,
                        }
                    )
            else:
                rows.extend(_recursive_diff(parent[key], development[key], child))
        return rows
    if isinstance(parent, Sequence) and not isinstance(parent, (str, bytes)):
        if isinstance(development, Sequence) and not isinstance(
            development, (str, bytes)
        ):
            if canonical_json(parent) == canonical_json(development):
                return []
    if canonical_json(parent) == canonical_json(development):
        return []
    return [
        {
            "path": path,
            "change": "CHANGED",
            "parent": parent,
            "development": development,
        }
    ]


def classify_contract_diff_path(path: str) -> str:
    if path in {
        "contract_version",
        "research_role",
        "candidate_generation.mode",
        "candidate_generation.full_development_scan_allowed",
        "pilot_contract.large_scan_allowed",
    } or path.startswith("parent_contract"):
        return "A_EXECUTION_SCOPE"
    if path.startswith("store_contract") or path.startswith(
        "reference_fingerprints"
    ):
        return "B_RUNTIME_STORE"
    if path.startswith("development_execution"):
        scheduling_terms = (
            "scheduler",
            "checkpoint",
            "process_lock",
            "maximum_attempts",
            "production_protection",
        )
        return (
            "C_SCHEDULING_RESUME"
            if any(term in path for term in scheduling_terms)
            else "B_RUNTIME_STORE"
        )
    return "D_RESEARCH_SEMANTICS"


def build_development_contract_diff(
    *,
    parent: Mapping[str, object],
    development: Mapping[str, object],
) -> dict[str, object]:
    comparable_parent = copy.deepcopy(dict(parent))
    comparable_parent.pop("contract_fingerprint", None)
    comparable_development = copy.deepcopy(dict(development))
    comparable_development.pop("contract_fingerprint", None)
    differences = _recursive_diff(comparable_parent, comparable_development)
    classified = [
        {**row, "classification": classify_contract_diff_path(str(row["path"]))}
        for row in differences
    ]
    semantic = [
        row
        for row in classified
        if row["classification"] == "D_RESEARCH_SEMANTICS"
    ]
    payload: dict[str, object] = {
        "version": DEVELOPMENT_CONTRACT_DIFF_VERSION,
        "parent_version": parent.get("contract_version"),
        "development_version": development.get("contract_version"),
        "parent_fingerprint": parent.get("contract_fingerprint"),
        "development_fingerprint": development.get("contract_fingerprint"),
        "differences": classified,
        "difference_count": len(classified),
        "research_semantics_diff_count": len(semantic),
        "unauthorized_differences": semantic,
        "status": "PASS" if not semantic else "FAIL",
    }
    payload["diff_fingerprint"] = fingerprint(payload)
    return payload


def validate_development_contract(contract: Mapping[str, object]) -> None:
    overlay = _load_overlay()
    parent = load_discovery_contract(
        PROJECT_ROOT / str(overlay["parent_contract_path"])
    )
    if parent["contract_fingerprint"] != overlay.get("parent_contract_fingerprint"):
        raise MultiAssetDevelopmentContractError(
            "Parent-Contract-Fingerprint stimmt nicht."
        )
    diff = build_development_contract_diff(parent=parent, development=contract)
    if diff["status"] != "PASS":
        raise MultiAssetDevelopmentContractError(
            "Development-Contract verändert Research-Semantik."
        )
    candidate = dict(contract.get("candidate_generation") or {})
    stores = dict(contract.get("store_contract") or {})
    execution = dict(contract.get("development_execution") or {})
    lifecycle = dict(contract.get("lifecycle") or {})
    checks = {
        "research_role": contract.get("research_role") == "development",
        "full_universe": candidate.get("mode") == "full_eligibility_universe",
        "full_scan": candidate.get("full_development_scan_allowed") is True,
        "large_scan": dict(contract.get("pilot_contract") or {}).get(
            "large_scan_allowed"
        )
        is True,
        "development_feature_store": "development"
        in str(stores.get("feature_store") or ""),
        "development_outcome_store": "development"
        in str(stores.get("outcome_store") or ""),
        "development_only": execution.get("development_end") == "2021-12-31",
        "validation_closed": execution.get("validation_access_allowed") is False,
        "holdout_closed": execution.get("holdout_access_allowed") is False,
        "lifecycle_closed": all(value is False for value in lifecycle.values()),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise MultiAssetDevelopmentContractError(
            f"Development-Ausführungsvertrag unvollständig: {failed}"
        )


def load_development_contract(
    path: Path = DEFAULT_DEVELOPMENT_OVERLAY,
) -> dict[str, object]:
    overlay = _load_overlay(path)
    parent_path = PROJECT_ROOT / str(overlay["parent_contract_path"])
    parent = load_discovery_contract(parent_path)
    if parent.get("contract_version") != overlay.get("parent_contract_version"):
        raise MultiAssetDevelopmentContractError("Parent-Version stimmt nicht.")
    if parent.get("contract_fingerprint") != overlay.get(
        "parent_contract_fingerprint"
    ):
        raise MultiAssetDevelopmentContractError("Parent-Fingerprint stimmt nicht.")
    development = _apply_execution_overrides(parent, overlay)
    validate_development_contract(development)
    return development


def build_development_contract_artifact(
    *, git_branch: str, git_commit: str, frozen_at: str
) -> tuple[dict[str, object], dict[str, object]]:
    overlay = _load_overlay()
    parent = load_discovery_contract(
        PROJECT_ROOT / str(overlay["parent_contract_path"])
    )
    contract = load_development_contract()
    diff = build_development_contract_diff(parent=parent, development=contract)
    if diff["status"] != "PASS":
        raise MultiAssetDevelopmentContractError(
            "Research-Semantik-Diff ist nicht null."
        )
    artifact: dict[str, object] = {
        "version": DEVELOPMENT_CONTRACT_ARTIFACT_VERSION,
        "frozen_at": frozen_at,
        "contract": contract,
        "contract_fingerprint": contract["contract_fingerprint"],
        "development_code_fingerprint": contract["reference_fingerprints"][
            "development_code_fingerprint"
        ],
        "parent_contract_version": parent["contract_version"],
        "parent_contract_fingerprint": parent["contract_fingerprint"],
        "parent_freeze_fingerprint": overlay["parent_freeze_fingerprint"],
        "git": {"branch": git_branch, "commit": git_commit},
        "research_semantics_diff_count": 0,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "true_forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_opened": False,
    }
    artifact["artifact_fingerprint"] = fingerprint(artifact)
    return artifact, diff


def verify_development_contract_artifact(artifact: Mapping[str, object]) -> bool:
    stored = str(artifact.get("artifact_fingerprint") or "")
    comparable = dict(artifact)
    comparable.pop("artifact_fingerprint", None)
    return bool(stored and stored == fingerprint(comparable))
