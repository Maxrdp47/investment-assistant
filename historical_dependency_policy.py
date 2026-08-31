from __future__ import annotations

"""Outcome-independent temporal issuer dependency policy for historical research."""

import hashlib
import json
from datetime import date
from typing import Mapping


HISTORICAL_DEPENDENCY_POLICY_VERSION = (
    "multi-asset-historical-dependency-policy-2026.09.01-v1"
)
ALLOWED_TEMPORAL_EVIDENCE = {
    "CONTEMPORANEOUS_REGULATORY_FILING",
    "OFFICIAL_LISTING_RELATION_HISTORY",
    "VERSIONED_CORPORATE_ACTION_LEDGER",
}


class HistoricalDependencyPolicyError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _day(value: object, field: str, *, required: bool = True) -> str | None:
    if value in (None, ""):
        if required:
            raise HistoricalDependencyPolicyError(f"{field} ist erforderlich.")
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise HistoricalDependencyPolicyError(f"{field} ist kein ISO-Datum.") from exc


def build_historical_dependency_policy() -> dict[str, object]:
    policy: dict[str, object] = {
        "version": HISTORICAL_DEPENDENCY_POLICY_VERSION,
        "purpose": "POST_HOC_STATISTICAL_DEPENDENCY_CLUSTERING_ONLY",
        "outcome_independent": True,
        "trading_feature": False,
        "candidate_status_may_change": False,
        "entry_may_change": False,
        "safe_zone_may_change": False,
        "outcome_may_change": False,
        "unknown_historical_relation_contributes_to_effective_n": 0,
        "current_registry_valid_from_semantics": "MAPPING_EVIDENCE_AVAILABLE_FROM_NOT_RELATIONSHIP_VALID_FROM",
        "known_relation_requirements": {
            "current_mapping_status": "VERIFIED",
            "issuer_id_required": True,
            "historical_status": "VERIFIED",
            "historical_valid_from_required": True,
            "historical_valid_to_optional": True,
            "evidence_source_required": True,
            "allowed_evidence_types": sorted(ALLOWED_TEMPORAL_EVIDENCE),
        },
        "corporate_action_rules": {
            "later_merger_may_not_merge_pre_merger_issuers": True,
            "spin_off_is_separate_until_explicit_temporal_relation": True,
            "predecessor_successor_windows_must_not_overlap_without_evidence": True,
            "ticker_or_listing_change_does_not_change_issuer_only_with_temporal_evidence": True,
            "adr_and_primary_listing_cluster_only_within_verified_overlap": True,
            "share_classes_cluster_only_within_verified_issuer_window": True,
        },
        "fail_closed": True,
        "automatic_backdating": False,
        "names_or_tickers_are_identifiers": False,
    }
    policy["policy_fingerprint"] = fingerprint(policy)
    return policy


def verify_historical_dependency_policy(policy: Mapping[str, object]) -> bool:
    stored = str(policy.get("policy_fingerprint") or "")
    comparable = dict(policy)
    comparable.pop("policy_fingerprint", None)
    return bool(stored and stored == fingerprint(comparable))


def classify_historical_dependency(
    mapping: Mapping[str, object],
    *,
    as_of: object,
    policy: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Classify dependency without exposing post-hoc identity as a trading feature."""

    active_policy = dict(policy or build_historical_dependency_policy())
    if not verify_historical_dependency_policy(active_policy):
        raise HistoricalDependencyPolicyError("Historical-Dependency-Policy ist ungültig.")
    as_of_day = _day(as_of, "as_of")
    metadata = dict(mapping.get("metadata") or {})
    historical = dict(
        mapping.get("historical_dependency")
        or metadata.get("historical_dependency")
        or {}
    )
    mapping_status = str(mapping.get("mapping_status") or "UNRESOLVED").upper()
    current_issuer = str(mapping.get("issuer_id") or "").strip() or None
    reason = "CURRENT_IDENTITY_IS_NOT_AUTOMATIC_HISTORICAL_EVIDENCE"
    known = False
    valid_from = None
    valid_to = None
    evidence_type = str(historical.get("evidence_type") or "").upper() or None
    evidence_source = str(historical.get("evidence_source") or "").strip() or None
    historical_status = str(historical.get("status") or "UNKNOWN").upper()

    if mapping_status != "VERIFIED" or not current_issuer:
        reason = "CURRENT_ISSUER_MAPPING_NOT_VERIFIED"
    elif historical_status != "VERIFIED":
        reason = "HISTORICAL_RELATION_NOT_VERIFIED"
    elif evidence_type not in ALLOWED_TEMPORAL_EVIDENCE or not evidence_source:
        reason = "HISTORICAL_TEMPORAL_EVIDENCE_INSUFFICIENT"
    else:
        valid_from = _day(historical.get("valid_from"), "historical.valid_from")
        valid_to = _day(
            historical.get("valid_to"), "historical.valid_to", required=False
        )
        if valid_to and valid_to < valid_from:
            raise HistoricalDependencyPolicyError(
                "historical.valid_to darf nicht vor valid_from liegen."
            )
        if as_of_day < valid_from:
            reason = "RELATION_NOT_YET_VALID_AT_RESEARCH_DATE"
        elif valid_to and as_of_day > valid_to:
            reason = "RELATION_NO_LONGER_VALID_AT_RESEARCH_DATE"
        else:
            known = True
            reason = "VERIFIED_TEMPORAL_RELATION_ACTIVE_AT_RESEARCH_DATE"

    result = {
        "asset_id": mapping.get("asset_id"),
        "listing_id": mapping.get("listing_id"),
        "ticker": mapping.get("ticker"),
        "mapping_status": mapping_status,
        "issuer_id": current_issuer if known else None,
        "dependency_status": "KNOWN" if known else "UNKNOWN",
        "historical_dependency_status": "KNOWN" if known else "DEPENDENCY_UNKNOWN",
        "historical_dependency_reason": reason,
        "historical_valid_from": valid_from,
        "historical_valid_to": valid_to,
        "historical_evidence_type": evidence_type,
        "historical_evidence_source": evidence_source,
        "historical_as_of": as_of_day,
        "historical_dependency_policy_version": active_policy["version"],
        "historical_dependency_policy_fingerprint": active_policy[
            "policy_fingerprint"
        ],
        "unknown_dependency_contribution_to_effective_n": 0,
        "research_dependency_only": True,
        "pit_trading_feature": False,
        "feature_values_mutated": False,
        "candidate_status_mutated": False,
        "entry_mutated": False,
        "safe_zone_mutated": False,
        "outcome_mutated": False,
    }
    result["classification_fingerprint"] = fingerprint(result)
    return result


def historical_dependency_policy_self_check() -> dict[str, object]:
    policy = build_historical_dependency_policy()
    base = {
        "ticker": "PRIMARY",
        "asset_id": "asset-1",
        "listing_id": "listing-primary",
        "issuer_id": "issuer-1",
        "mapping_status": "VERIFIED",
        "metadata": {},
    }
    current_only = classify_historical_dependency(base, as_of="2020-01-01", policy=policy)
    verified = {
        **base,
        "metadata": {
            "historical_dependency": {
                "status": "VERIFIED",
                "valid_from": "2010-01-01",
                "valid_to": "2024-12-31",
                "evidence_type": "CONTEMPORANEOUS_REGULATORY_FILING",
                "evidence_source": "official:test",
            }
        },
    }
    inside = classify_historical_dependency(verified, as_of="2020-01-01", policy=policy)
    before = classify_historical_dependency(verified, as_of="2009-12-31", policy=policy)
    after = classify_historical_dependency(verified, as_of="2025-01-01", policy=policy)
    merger_successor = {
        **verified,
        "issuer_id": "issuer-successor",
        "metadata": {
            "historical_dependency": {
                "status": "VERIFIED",
                "valid_from": "2022-06-01",
                "evidence_type": "VERSIONED_CORPORATE_ACTION_LEDGER",
                "evidence_source": "official:merger-ledger",
            }
        },
    }
    pre_merger = classify_historical_dependency(
        merger_successor, as_of="2021-12-31", policy=policy
    )
    checks = {
        "policy_fingerprint_valid": verify_historical_dependency_policy(policy),
        "current_identity_not_backdated": current_only["dependency_status"] == "UNKNOWN",
        "verified_relation_active_inside_window": inside["dependency_status"] == "KNOWN",
        "valid_from_enforced": before["dependency_status"] == "UNKNOWN",
        "valid_to_enforced": after["dependency_status"] == "UNKNOWN",
        "post_merger_identity_not_backdated": pre_merger["dependency_status"] == "UNKNOWN",
        "unknown_contributes_zero": all(
            item["unknown_dependency_contribution_to_effective_n"] == 0
            for item in (current_only, before, after, pre_merger)
        ),
        "no_feature_mutation": all(
            item["feature_values_mutated"] is False
            and item["candidate_status_mutated"] is False
            and item["entry_mutated"] is False
            and item["safe_zone_mutated"] is False
            and item["outcome_mutated"] is False
            for item in (current_only, inside, before, after, pre_merger)
        ),
    }
    payload: dict[str, object] = {
        "version": HISTORICAL_DEPENDENCY_POLICY_VERSION,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "policy": policy,
        "examples": {
            "current_only": current_only,
            "verified_inside_window": inside,
            "pre_merger": pre_merger,
        },
    }
    payload["self_check_fingerprint"] = fingerprint(payload)
    return payload
