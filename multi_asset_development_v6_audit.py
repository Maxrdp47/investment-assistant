from __future__ import annotations

"""Full, read-only final integrity audit for Development v6.

The audit deliberately performs no sampling.  It reads every feature/outcome
payload, reconciles every work unit with its immutable receipt, and writes at
most one self-fingerprinted JSON artifact.  Source stores are always opened in
SQLite read-only mode.
"""

import hashlib
import json
import math
import sqlite3
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

from multi_asset_development_v6_contract import (
    DEVELOPMENT_V6_CONTRACT_VERSION,
    verify_development_v6_contract_artifact,
)
from multi_asset_development_v6_inputs import (
    DEFAULT_CRYPTO_ARTIFACT,
    DEFAULT_CRYPTO_STORE,
    DEFAULT_DATASET_MANIFEST,
    DEFAULT_EQUITY_ETF_ARTIFACT,
    DEFAULT_EQUITY_ETF_STORE,
    DEFAULT_FX_ARTIFACT,
    DEFAULT_FX_STORE,
    DEFAULT_IDENTITY_STORE,
)
from multi_asset_development_v6_outcomes import (
    V6_OUTCOME_POLICY_VERSION,
    V6_OUTCOME_VERSION,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
AUDIT_VERSION = "multi-asset-development-v6-final-integrity-audit-2026.09.05-v3"
DEFAULT_AUDIT_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v6_final_integrity_audit_2026-09-05-v1.json"
)

_FEATURE_COLUMNS = (
    "case_id",
    "feature_fingerprint",
    "run_id",
    "work_unit_id",
    "asset_id",
    "symbol",
    "asset_class",
    "signal_day",
    "research_split",
    "dependency_status",
)
_OUTCOME_COLUMNS = (
    "case_id",
    "outcome_fingerprint",
    "feature_fingerprint",
    "run_id",
    "work_unit_id",
    "asset_id",
    "symbol",
    "asset_class",
    "signal_day",
    "research_split",
    "status",
    "r_availability",
    "dependency_status",
)
_TERMINAL_UNIT_STATUSES = frozenset({"COMPLETED", "SKIPPED"})
# These are machine-recorded execution classifications, not labels inferred by
# the audit from an empty payload.  Expanding this set is therefore a versioned
# contract change rather than a reporting convenience.
ALLOWED_SKIP_REASON_CODES = frozenset(
    {
        "EXPECTED_NO_DEVELOPMENT_DATA",
        "NO_GAP_SAFE_220_OBSERVATION_HISTORY",
    }
)
_OUTCOME_STATUSES = frozenset(
    {
        "COMPLETE",
        "CENSORED_AT_INPUT_GAP",
        "CENSORED_AT_END_OF_AVAILABLE_DATA",
        "CENSORED_AT_STAGE_BOUNDARY",
    }
)
_SUMMARY_COUNTERS = (
    "r_na_cases",
    "censored_cases",
    "missing_reference_entry",
    "missingness_exclusions",
)
_CORE_PROTECTED_SOURCE_KEYS = frozenset(
    {
        "equity_etf_store",
        "crypto_store",
        "fx_store",
        "dataset_manifest",
        "identity_store",
        "equity_etf_artifact",
        "crypto_artifact",
        "fx_artifact",
    }
)


class DevelopmentV6AuditError(RuntimeError):
    """The final audit cannot be performed or its artifact is inconsistent."""


def _ro(path: Path) -> sqlite3.Connection:
    path = Path(path)
    if not path.is_file():
        raise DevelopmentV6AuditError(f"Required SQLite store is missing: {path}")
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=120
    )
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _artifact_fingerprint(payload: Mapping[str, object]) -> str:
    basis = dict(payload)
    basis.pop("artifact_fingerprint", None)
    return fingerprint(basis)


def verify_self_fingerprinted_artifact(payload: Mapping[str, object]) -> bool:
    claimed = payload.get("artifact_fingerprint")
    return isinstance(claimed, str) and claimed == _artifact_fingerprint(payload)


def _load_mapping(value: Mapping[str, object] | Path | str) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _record_binding(
    bindings: dict[str, dict[str, object]],
    issues: Counter[str],
    *,
    name: str,
    expected: object,
    actual: object,
) -> None:
    matches = expected is not None and str(actual) == str(expected)
    bindings[name] = {
        "expected": expected,
        "actual": actual,
        "matches": matches,
    }
    if not matches:
        issues[f"provenance_binding_mismatch:{name}"] += 1


def _default_protected_source_paths(
    expected_hashes: Mapping[str, object],
) -> dict[str, Path]:
    paths = {
        "equity_etf_store": DEFAULT_EQUITY_ETF_STORE,
        "crypto_store": DEFAULT_CRYPTO_STORE,
        "fx_store": DEFAULT_FX_STORE,
        "dataset_manifest": DEFAULT_DATASET_MANIFEST,
        "identity_store": DEFAULT_IDENTITY_STORE,
        "equity_etf_artifact": DEFAULT_EQUITY_ETF_ARTIFACT,
        "crypto_artifact": DEFAULT_CRYPTO_ARTIFACT,
        "fx_artifact": DEFAULT_FX_ARTIFACT,
    }
    manifest_root = Path(DEFAULT_DATASET_MANIFEST).resolve().parent
    for key in expected_hashes:
        if not str(key).startswith("crypto_frozen:"):
            continue
        relative = str(key).split(":", 1)[1]
        candidate = (manifest_root / relative).resolve()
        try:
            candidate.relative_to(manifest_root)
        except ValueError as exc:
            raise DevelopmentV6AuditError(
                f"Protected Crypto source escapes the frozen dataset: {relative}"
            ) from exc
        paths[str(key)] = candidate
    return paths


def _load_provenance_context(
    *,
    final_contract: Mapping[str, object] | Path | str,
    input_precheck: Mapping[str, object] | Path | str,
    protected_source_paths: Mapping[str, Path | str] | None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], Counter[str]]:
    """Validate and rehash the frozen input/contract chain exactly once."""

    issues: Counter[str] = Counter()
    supplied_contract = _load_mapping(final_contract)
    contract_artifact_fingerprint: str | None = None
    if isinstance(supplied_contract.get("contract"), Mapping):
        if not verify_development_v6_contract_artifact(supplied_contract):
            issues["final_contract_artifact_self_fingerprint_mismatch"] += 1
        contract_artifact_fingerprint = str(
            supplied_contract.get("artifact_fingerprint") or ""
        ) or None
        contract = dict(supplied_contract.get("contract") or {})
        if str(supplied_contract.get("contract_fingerprint")) != str(
            contract.get("contract_fingerprint")
        ):
            issues["final_contract_artifact_inner_contract_mismatch"] += 1
    else:
        contract = supplied_contract

    contract_basis = dict(contract)
    contract_claim = contract_basis.pop("contract_fingerprint", None)
    if not contract_claim or contract_claim != fingerprint(contract_basis):
        issues["final_contract_self_fingerprint_mismatch"] += 1
    if contract.get("contract_version") != DEVELOPMENT_V6_CONTRACT_VERSION:
        issues["final_contract_version_mismatch"] += 1

    precheck = _load_mapping(input_precheck)
    if not verify_self_fingerprinted_artifact(precheck):
        issues["input_precheck_self_fingerprint_mismatch"] += 1
    if precheck.get("status") != "PASS":
        issues["input_precheck_not_pass"] += 1
    precheck_checks = dict(precheck.get("checks") or {})
    if not precheck_checks or any(value is not True for value in precheck_checks.values()):
        issues["input_precheck_contains_non_pass_check"] += 1

    expected_hashes = {
        str(key): str(value)
        for key, value in dict(precheck.get("source_sha256_before") or {}).items()
    }
    precheck_after = {
        str(key): str(value)
        for key, value in dict(precheck.get("source_sha256_after") or {}).items()
    }
    missing_core = sorted(_CORE_PROTECTED_SOURCE_KEYS - set(expected_hashes))
    if missing_core:
        issues["input_precheck_missing_core_protected_hash"] += len(missing_core)
    if not any(key.startswith("crypto_frozen:") for key in expected_hashes):
        issues["input_precheck_missing_crypto_frozen_source_hashes"] += 1
    if expected_hashes != precheck_after:
        issues["input_precheck_source_before_after_mismatch"] += 1

    paths = (
        _default_protected_source_paths(expected_hashes)
        if protected_source_paths is None
        else {str(key): Path(value) for key, value in protected_source_paths.items()}
    )
    if set(paths) != set(expected_hashes):
        issues["protected_source_path_set_mismatch"] += len(
            set(paths).symmetric_difference(expected_hashes)
        )
    observed_hashes: dict[str, str | None] = {}
    resolved_paths: dict[str, str] = {}
    for key in sorted(expected_hashes):
        path = paths.get(key)
        if path is None:
            observed_hashes[key] = None
            continue
        resolved = Path(path).resolve()
        resolved_paths[key] = str(resolved)
        if not resolved.is_file():
            observed_hashes[key] = None
            issues[f"protected_source_missing:{key}"] += 1
            continue
        try:
            # Deliberately exactly one full-file read per protected source.
            observed_hashes[key] = file_sha256(resolved)
        except OSError:
            observed_hashes[key] = None
            issues[f"protected_source_unreadable:{key}"] += 1
    hash_matches = {
        key: observed_hashes.get(key) == expected_hashes[key]
        for key in sorted(expected_hashes)
    }
    for key, matches in hash_matches.items():
        if not matches:
            issues[f"protected_source_hash_mismatch:{key}"] += 1

    expected_implementation_hashes = {
        str(key): str(value)
        for key, value in dict(precheck.get("implementation_sha256") or {}).items()
    }
    declared_implementation_paths = [
        str(value) for value in list(precheck.get("implementation_paths") or [])
    ]
    if not expected_implementation_hashes:
        issues["input_precheck_missing_implementation_hashes"] += 1
    if set(declared_implementation_paths) != set(expected_implementation_hashes):
        issues["input_precheck_implementation_path_set_mismatch"] += len(
            set(declared_implementation_paths).symmetric_difference(
                expected_implementation_hashes
            )
        )
    if len(declared_implementation_paths) != len(set(declared_implementation_paths)):
        issues["input_precheck_duplicate_implementation_path"] += 1
    if precheck.get("missing_implementation_files") not in ([], ()):
        issues["input_precheck_declares_missing_implementation_files"] += 1
    observed_implementation_hashes: dict[str, str | None] = {}
    resolved_implementation_paths: dict[str, str] = {}
    project_root = PROJECT_ROOT.resolve()
    for label in sorted(expected_implementation_hashes):
        declared = Path(label)
        resolved = declared.resolve() if declared.is_absolute() else (project_root / declared).resolve()
        if not declared.is_absolute():
            try:
                resolved.relative_to(project_root)
            except ValueError:
                observed_implementation_hashes[label] = None
                issues[f"protected_implementation_path_escapes_project:{label}"] += 1
                continue
        resolved_implementation_paths[label] = str(resolved)
        if not resolved.is_file():
            observed_implementation_hashes[label] = None
            issues[f"protected_implementation_missing:{label}"] += 1
            continue
        try:
            # Exactly one full-file read for each implementation member.
            observed_implementation_hashes[label] = file_sha256(resolved)
        except OSError:
            observed_implementation_hashes[label] = None
            issues[f"protected_implementation_unreadable:{label}"] += 1
    implementation_hash_matches = {
        label: observed_implementation_hashes.get(label)
        == expected_implementation_hashes[label]
        for label in sorted(expected_implementation_hashes)
    }
    for label, matches in implementation_hash_matches.items():
        if not matches:
            issues[f"protected_implementation_hash_mismatch:{label}"] += 1

    inputs = dict(precheck.get("contract_inputs") or {})
    references = dict(contract.get("reference_fingerprints") or {})
    bindings: dict[str, dict[str, object]] = {}
    for name in (
        "combined_input_fingerprint",
        "equity_etf_projection_fingerprint",
        "crypto_projection_fingerprint",
        "fx_projection_fingerprint",
        "equity_etf_store_sha256",
        "crypto_store_sha256",
        "fx_store_sha256",
        "source_dataset_manifest_sha256",
        "identity_store_sha256",
        "identity_registry_fingerprint",
        "gap_policy_fingerprint",
    ):
        _record_binding(
            bindings,
            issues,
            name=f"contract_to_precheck:{name}",
            expected=inputs.get(name),
            actual=references.get(name),
        )
    _record_binding(
        bindings,
        issues,
        name="contract_to_precheck:input_precheck_artifact_fingerprint",
        expected=precheck.get("artifact_fingerprint"),
        actual=references.get("input_precheck_artifact_fingerprint"),
    )
    _record_binding(
        bindings,
        issues,
        name="contract_to_precheck:implementation_fingerprint",
        expected=inputs.get("implementation_fingerprint"),
        actual=references.get("development_code_fingerprint"),
    )
    _record_binding(
        bindings,
        issues,
        name="precheck_implementation_hashes:aggregate_fingerprint",
        expected=inputs.get("implementation_fingerprint"),
        actual=(
            fingerprint(expected_implementation_hashes)
            if expected_implementation_hashes
            else None
        ),
    )
    expected_implementation_fingerprint = (
        fingerprint(expected_implementation_hashes)
        if expected_implementation_hashes
        else None
    )
    observed_implementation_fingerprint = (
        fingerprint(observed_implementation_hashes)
        if observed_implementation_hashes
        and all(value is not None for value in observed_implementation_hashes.values())
        else None
    )
    implementation_aggregate_matches = bool(expected_implementation_fingerprint) and (
        inputs.get("implementation_fingerprint")
        == expected_implementation_fingerprint
        == observed_implementation_fingerprint
    )
    for alias, input_name in (
        ("dataset_fingerprint", "combined_input_fingerprint"),
        ("dataset_manifest_sha256", "source_dataset_manifest_sha256"),
        ("fx_dataset_fingerprint", "fx_projection_fingerprint"),
    ):
        _record_binding(
            bindings,
            issues,
            name=f"contract_alias:{alias}",
            expected=inputs.get(input_name),
            actual=references.get(alias),
        )
    for source_name, input_name in (
        ("equity_etf_store", "equity_etf_store_sha256"),
        ("crypto_store", "crypto_store_sha256"),
        ("fx_store", "fx_store_sha256"),
        ("dataset_manifest", "source_dataset_manifest_sha256"),
        ("identity_store", "identity_store_sha256"),
    ):
        _record_binding(
            bindings,
            issues,
            name=f"precheck_source_hash:{source_name}",
            expected=inputs.get(input_name),
            actual=expected_hashes.get(source_name),
        )

    gap = dict(precheck.get("gap_policy") or {})
    gap_basis = dict(gap)
    gap_claim = gap_basis.pop("fingerprint", None)
    if not gap_claim or gap_claim != fingerprint(gap_basis):
        issues["input_precheck_gap_policy_self_fingerprint_mismatch"] += 1
    _record_binding(
        bindings,
        issues,
        name="precheck_gap_policy:contract_input",
        expected=inputs.get("gap_policy_fingerprint"),
        actual=gap.get("fingerprint"),
    )

    context: dict[str, object] = {
        "contract": {
            "contract_version": contract.get("contract_version"),
            "contract_fingerprint": contract.get("contract_fingerprint"),
            "contract_artifact_fingerprint": contract_artifact_fingerprint,
            "historical_dependency_policy_version": references.get(
                "historical_dependency_policy_version"
            ),
            "historical_dependency_policy_fingerprint": references.get(
                "historical_dependency_policy_fingerprint"
            ),
        },
        "input_precheck": {
            "version": precheck.get("version"),
            "status": precheck.get("status"),
            "artifact_fingerprint": precheck.get("artifact_fingerprint"),
            "all_declared_checks_pass": bool(precheck_checks)
            and all(value is True for value in precheck_checks.values()),
        },
        "contract_precheck_bindings": bindings,
        "protected_sources": {
            "hash_algorithm": "sha256",
            "rehash_count_per_source": 1,
            "expected_source_keys": sorted(expected_hashes),
            "resolved_paths": resolved_paths,
            "expected_sha256": expected_hashes,
            "observed_sha256": observed_hashes,
            "hash_matches": hash_matches,
            "all_hashes_match": bool(hash_matches) and all(hash_matches.values()),
            "core_source_keys_present": not missing_core,
            "crypto_frozen_sources_present": any(
                key.startswith("crypto_frozen:") for key in expected_hashes
            ),
        },
        "protected_implementation": {
            "hash_algorithm": "sha256",
            "rehash_count_per_file": 1,
            "expected_paths": sorted(expected_implementation_hashes),
            "resolved_paths": resolved_implementation_paths,
            "expected_sha256": expected_implementation_hashes,
            "observed_sha256": observed_implementation_hashes,
            "hash_matches": implementation_hash_matches,
            "all_hashes_match": bool(implementation_hash_matches)
            and all(implementation_hash_matches.values())
            and implementation_aggregate_matches,
            "expected_implementation_fingerprint": inputs.get(
                "implementation_fingerprint"
            ),
            "recomputed_expected_implementation_fingerprint": (
                expected_implementation_fingerprint
            ),
            "recomputed_observed_implementation_fingerprint": (
                observed_implementation_fingerprint
            ),
            "aggregate_fingerprint_matches": implementation_aggregate_matches,
        },
    }
    context["binding_fingerprint"] = fingerprint(context)
    return contract, precheck, context, issues


def _run_manifest_provenance(
    *,
    manifest: Mapping[str, object],
    contract: Mapping[str, object],
    precheck: Mapping[str, object],
    contract_artifact_fingerprint: object,
) -> tuple[dict[str, object], Counter[str]]:
    issues: Counter[str] = Counter()
    basis = dict(manifest)
    claim = basis.pop("run_manifest_fingerprint", None)
    self_valid = bool(claim) and claim == fingerprint(basis)
    if not self_valid:
        issues["run_manifest_self_fingerprint_mismatch"] += 1
    references = dict(contract.get("reference_fingerprints") or {})
    bindings: dict[str, dict[str, object]] = {}
    expected = {
        "development_contract_version": contract.get("contract_version"),
        "development_contract_fingerprint": contract.get("contract_fingerprint"),
        "combined_input_fingerprint": references.get("combined_input_fingerprint"),
        "equity_etf_projection_fingerprint": references.get(
            "equity_etf_projection_fingerprint"
        ),
        "crypto_projection_fingerprint": references.get(
            "crypto_projection_fingerprint"
        ),
        "fx_projection_fingerprint": references.get("fx_projection_fingerprint"),
        "input_precheck_artifact_fingerprint": precheck.get(
            "artifact_fingerprint"
        ),
        "code_fingerprint": references.get("development_code_fingerprint"),
        "identity_fingerprint": references.get("identity_registry_fingerprint"),
        "dependency_policy_fingerprint": references.get(
            "historical_dependency_policy_fingerprint"
        ),
    }
    if contract_artifact_fingerprint is not None:
        expected["contract_artifact_fingerprint"] = contract_artifact_fingerprint
    for name, value in expected.items():
        _record_binding(
            bindings,
            issues,
            name=f"run_manifest_to_frozen_chain:{name}",
            expected=value,
            actual=manifest.get(name),
        )
    for closed_name in (
        "validation_opened",
        "holdout_opened",
        "external_opened",
        "forward_opened",
        "paper_opened",
        "shadow_opened",
        "broker_opened",
        "automatic_orders_allowed",
    ):
        if manifest.get(closed_name) is not False:
            issues[f"run_manifest_scope_not_closed:{closed_name}"] += 1
    if manifest.get("development_only") is not True:
        issues["run_manifest_not_development_only"] += 1
    result: dict[str, object] = {
        "run_manifest_fingerprint": claim,
        "self_fingerprint_valid": self_valid,
        "bindings": bindings,
        "development_only": manifest.get("development_only") is True,
        "all_unseen_and_trading_scopes_closed": all(
            manifest.get(name) is False
            for name in (
                "validation_opened",
                "holdout_opened",
                "external_opened",
                "forward_opened",
                "paper_opened",
                "shadow_opened",
                "broker_opened",
                "automatic_orders_allowed",
            )
        ),
    }
    return result, issues


def _write_once(path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    if not verify_self_fingerprinted_artifact(payload):
        raise DevelopmentV6AuditError("Artifact is not correctly self-fingerprinted.")
    path = Path(path)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not verify_self_fingerprinted_artifact(existing):
            raise DevelopmentV6AuditError(f"Existing artifact is corrupt: {path}")
        if existing["artifact_fingerprint"] != payload["artifact_fingerprint"]:
            raise DevelopmentV6AuditError(
                f"Immutable audit artifact already exists with other content: {path}"
            )
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    except FileExistsError:
        return _write_once(path, payload)
    return dict(payload)


def _validate_existing_artifact(path: Path) -> dict[str, object] | None:
    if not Path(path).exists():
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not verify_self_fingerprinted_artifact(payload):
        raise DevelopmentV6AuditError(f"Existing audit artifact is corrupt: {path}")
    return payload


def _database_health(
    path: Path, *, required_triggers: Iterable[str]
) -> dict[str, object]:
    with _ro(path) as connection:
        quick = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
        integrity = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
        foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check")]
        trigger_names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
    required = set(required_triggers)
    missing = sorted(required - trigger_names)
    return {
        "path": str(Path(path).resolve()),
        "quick_check": quick,
        "quick_check_ok": quick == ["ok"],
        "integrity_check": integrity,
        "integrity_check_ok": integrity == ["ok"],
        "foreign_key_violations": foreign_keys,
        "foreign_keys_ok": not foreign_keys,
        "required_append_only_triggers": sorted(required),
        "present_triggers": sorted(trigger_names),
        "missing_append_only_triggers": missing,
        "append_only_triggers_ok": not missing,
    }


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _walk_known_at(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "known_at" and isinstance(child, str):
                yield child
            yield from _walk_known_at(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_known_at(child)


def _finite_or_none(value: object) -> bool:
    if value is None:
        return True
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _r_values(outcome: Mapping[str, object]) -> Iterable[object]:
    yield outcome.get("mfe_r")
    yield outcome.get("mae_r")
    for value in dict(outcome.get("r_level_hits") or {}).values():
        yield value
    for checkpoint in dict(outcome.get("checkpoints") or {}).values():
        if isinstance(checkpoint, Mapping):
            yield checkpoint.get("mfe_r")
            yield checkpoint.get("mae_r")
    path = dict(outcome.get("path_quality") or {})
    yield path.get("peak_giveback_r")
    yield path.get("final_giveback_r")


def _atr_values(outcome: Mapping[str, object]) -> Iterable[object]:
    yield outcome.get("entry_gap_atr")
    yield outcome.get("mfe_atr")
    yield outcome.get("mae_atr")
    for checkpoint in dict(outcome.get("checkpoints") or {}).values():
        if isinstance(checkpoint, Mapping):
            yield checkpoint.get("mfe_atr")
            yield checkpoint.get("mae_atr")


def _audit_payload_pair(
    feature_columns: Mapping[str, object],
    outcome_columns: Mapping[str, object],
    feature: Mapping[str, object],
    outcome: Mapping[str, object],
    *,
    work_unit: Mapping[str, object] | None,
    expected_provenance: Mapping[str, object],
) -> Counter[str]:
    issues: Counter[str] = Counter()
    feature_basis = dict(feature)
    feature_claim = feature_basis.pop("feature_fingerprint", None)
    if feature_claim != fingerprint(feature_basis):
        issues["feature_payload_fingerprint_mismatch"] += 1
    outcome_basis = dict(outcome)
    outcome_claim = outcome_basis.pop("outcome_fingerprint", None)
    if outcome_claim != fingerprint(outcome_basis):
        issues["outcome_payload_fingerprint_mismatch"] += 1

    expected_contract_version = expected_provenance.get("contract_version")
    if feature.get("contract_version") != expected_contract_version:
        issues["feature_contract_version_mismatch"] += 1
    if outcome.get("contract_version") != expected_contract_version:
        issues["outcome_contract_version_mismatch"] += 1
    expected_run_id = str(expected_provenance.get("run_id") or "")
    for role, columns in (
        ("feature", feature_columns),
        ("outcome", outcome_columns),
    ):
        if str(columns.get("run_id") or "") != expected_run_id:
            issues[f"{role}_run_manifest_binding_mismatch"] += 1

    for key in _FEATURE_COLUMNS:
        if key in {"run_id", "work_unit_id"}:
            continue
        expected = feature.get(key)
        actual = feature_columns.get(key)
        if str(expected if expected is not None else "UNKNOWN") != str(actual):
            issues[f"feature_column_payload_mismatch:{key}"] += 1
    for key in _OUTCOME_COLUMNS:
        if key in {"run_id", "work_unit_id", "r_availability"}:
            continue
        expected = outcome.get(key)
        actual = outcome_columns.get(key)
        if str(expected if expected is not None else "UNKNOWN") != str(actual):
            issues[f"outcome_column_payload_mismatch:{key}"] += 1
    payload_r_status = str(
        outcome.get("r_availability")
        or outcome.get("r_metrics_status")
        or "UNAVAILABLE"
    )
    if payload_r_status != str(outcome_columns.get("r_availability")):
        issues["outcome_r_availability_column_payload_mismatch"] += 1

    for key in (
        "case_id",
        "feature_fingerprint",
        "asset_id",
        "symbol",
        "asset_class",
        "signal_day",
        "research_split",
        "dependency_status",
    ):
        left = feature.get(key)
        right = outcome.get(key)
        if str(left if left is not None else "UNKNOWN") != str(
            right if right is not None else "UNKNOWN"
        ):
            issues[f"feature_outcome_link_mismatch:{key}"] += 1

    provenance = dict(feature.get("input_provenance") or {})
    expected_combined = expected_provenance.get("combined_input_fingerprint")
    if provenance.get("combined_input_fingerprint") != expected_combined:
        issues["feature_combined_input_fingerprint_mismatch"] += 1
    projections = dict(expected_provenance.get("projection_fingerprints") or {})
    asset_class = str(feature.get("asset_class") or "")
    expected_projection = projections.get(asset_class)
    if expected_projection is None or provenance.get("projection_fingerprint") != expected_projection:
        issues["feature_projection_fingerprint_mismatch"] += 1
    expected_gap_policy = expected_provenance.get("gap_policy_fingerprint")
    if provenance.get("gap_policy_fingerprint") != expected_gap_policy:
        issues["feature_gap_policy_fingerprint_mismatch"] += 1
    asset_key = str((work_unit or {}).get("asset_key") or "")
    expected_source_fingerprint = fingerprint(
        {
            "combined_input_fingerprint": expected_combined,
            "projection_fingerprint": expected_projection,
            "asset_key": asset_key,
        }
    )
    if provenance.get("source_fingerprint") != expected_source_fingerprint:
        issues["feature_source_fingerprint_mismatch"] += 1
    if feature.get("dataset_fingerprint") != expected_source_fingerprint:
        issues["feature_dataset_fingerprint_mismatch"] += 1
    if provenance.get("provider_values_repaired") is not False:
        issues["feature_input_provenance_repaired_or_unspecified"] += 1

    expected_dependency_fingerprint = expected_provenance.get(
        "historical_dependency_policy_fingerprint"
    )
    expected_dependency_version = expected_provenance.get(
        "historical_dependency_policy_version"
    )
    if asset_class == "FX":
        if feature.get("dependency_status") != "UNKNOWN":
            issues["fx_dependency_status_not_unknown"] += 1
        if feature.get("historical_dependency_policy_fingerprint") is not None:
            issues["fx_unexpected_historical_dependency_policy_fingerprint"] += 1
        if feature.get("historical_dependency_policy_version") is not None:
            issues["fx_unexpected_historical_dependency_policy_version"] += 1
    else:
        if feature.get("historical_dependency_policy_fingerprint") != (
            expected_dependency_fingerprint
        ):
            issues["feature_dependency_policy_fingerprint_mismatch"] += 1
        if feature.get("historical_dependency_policy_version") != (
            expected_dependency_version
        ):
            issues["feature_dependency_policy_version_mismatch"] += 1
        if feature.get("dependency_status") not in {"KNOWN", "UNKNOWN"}:
            issues["feature_dependency_status_invalid"] += 1
        if not feature.get("historical_dependency_reason"):
            issues["feature_dependency_reason_missing"] += 1
    # Outcome provenance is intentionally transitive through the immutable
    # feature fingerprint; no future/input fields are copied into outcomes.
    if outcome.get("feature_fingerprint") != feature_claim:
        issues["outcome_input_provenance_feature_link_mismatch"] += 1

    if feature.get("research_split") != "development":
        issues["feature_not_development"] += 1
    if outcome.get("research_split") != "development":
        issues["outcome_not_development"] += 1
    if feature.get("known_at_lte_decision_time") is not True:
        issues["feature_causal_flag_missing_or_false"] += 1
    if feature.get("candidate_selected_from_outcome") is not False:
        issues["outcome_selected_candidate"] += 1
    if feature.get("predictive_prefilter_used") is not False:
        issues["predictive_prefilter_used"] += 1
    if feature.get("history_end_day") != feature.get("signal_day"):
        issues["history_end_not_signal_day"] += 1
    decision = _parse_time(feature.get("decision_time"))
    if decision is None:
        issues["decision_time_missing_or_invalid"] += 1
    else:
        for known_at in _walk_known_at(feature):
            parsed = _parse_time(known_at)
            if parsed is None:
                issues["feature_known_at_invalid"] += 1
            else:
                try:
                    after = parsed > decision
                except TypeError:
                    after = True
                if after:
                    issues["feature_known_at_after_decision"] += 1

    identity_keys = ("asset_id", "signal_day", "contract_version", "dataset_fingerprint")
    if all(feature.get(key) is not None for key in identity_keys):
        identity = {key: feature[key] for key in identity_keys}
        if feature.get("case_id") != f"mad1-{fingerprint(identity)[:32]}":
            issues["case_id_identity_mismatch"] += 1

    source = dict(feature.get("source_integrity") or {})
    if source.get("provider_values_repaired") is not False:
        issues["feature_provider_values_repaired_or_unspecified"] += 1
    if int(source.get("ohlc_envelope_anomaly_count_to_decision") or 0) != 0:
        issues["feature_ohlc_anomaly_present"] += 1

    if outcome.get("outcome_version") != V6_OUTCOME_VERSION:
        issues["wrong_or_missing_outcome_version"] += 1
    if outcome.get("outcome_policy_version") != V6_OUTCOME_POLICY_VERSION:
        issues["wrong_or_missing_outcome_policy_version"] += 1
    if outcome.get("status") not in _OUTCOME_STATUSES:
        issues["unexpected_outcome_status"] += 1
    if outcome.get("future_features_written_to_feature_store") is not False:
        issues["future_features_written"] += 1
    if outcome.get("no_intrabar_order_invented") is not True:
        issues["intrabar_order_guard_missing_or_false"] += 1
    if int(outcome.get("cross_segment_observations_used") or 0) != 0:
        issues["cross_segment_observations_used"] += 1
    segment = dict(outcome.get("input_segment") or {})
    if segment.get("single_segment_verified") is not True:
        issues["single_segment_guard_missing_or_false"] += 1
    outcome_source = dict(outcome.get("source_integrity") or {})
    if int(outcome_source.get("cross_segment_observations_used") or 0) != 0:
        issues["source_integrity_cross_segment_observations_used"] += 1
    if int(outcome_source.get("ohlc_envelope_anomaly_count_in_outcome") or 0) != 0:
        issues["outcome_ohlc_anomaly_present"] += 1

    for key in (
        "mfe_pct",
        "mae_pct",
        "mfe_atr",
        "mae_atr",
        "mfe_r",
        "mae_r",
        "final_return_pct",
    ):
        if not _finite_or_none(outcome.get(key)):
            issues[f"non_finite_outcome_metric:{key}"] += 1
    r_status = str(outcome.get("r_metrics_status") or "UNAVAILABLE")
    r_values = list(_r_values(outcome))
    if r_status == "AVAILABLE":
        risk = outcome.get("structural_risk")
        if not _finite_or_none(risk) or risk is None or float(risk) <= 0:
            issues["r_available_without_positive_structural_risk"] += 1
        if outcome.get("mfe_r") is None or outcome.get("mae_r") is None:
            issues["r_available_without_core_r_metrics"] += 1
    elif r_status == "UNAVAILABLE":
        if any(value is not None for value in r_values):
            issues["r_value_present_while_unavailable"] += 1
        if not outcome.get("r_metrics_reason"):
            issues["r_unavailable_without_reason"] += 1
    else:
        issues["unexpected_r_metrics_status"] += 1
    atr_status = str(outcome.get("atr_metrics_status") or "UNAVAILABLE")
    if atr_status == "AVAILABLE":
        if outcome.get("mfe_atr") is None or outcome.get("mae_atr") is None:
            issues["atr_available_without_core_metrics"] += 1
    elif atr_status == "UNAVAILABLE":
        if any(value is not None for value in _atr_values(outcome)):
            issues["atr_value_present_while_unavailable"] += 1
        if not outcome.get("atr_metrics_reason"):
            issues["atr_unavailable_without_reason"] += 1
    else:
        issues["unexpected_atr_metrics_status"] += 1

    if outcome.get("measurement_status") == "NO_REFERENCE_ENTRY":
        if outcome.get("entry_day") is not None or outcome.get("entry_open") is not None:
            issues["no_reference_entry_contains_entry"] += 1
        for key in ("mfe_pct", "mae_pct", "final_return_pct"):
            if outcome.get(key) is not None:
                issues["no_reference_entry_contains_path_metric"] += 1

    if work_unit is None:
        issues["orphan_work_unit_link"] += 1
    else:
        for key in ("run_id", "work_unit_id"):
            if str(feature_columns.get(key)) != str(outcome_columns.get(key)):
                issues[f"feature_outcome_column_mismatch:{key}"] += 1
        if str(feature_columns.get("work_unit_id")) != str(work_unit["work_unit_id"]):
            issues["wrong_work_unit_link"] += 1
        if str(work_unit.get("run_id") or "") != expected_run_id:
            issues["work_unit_run_manifest_binding_mismatch"] += 1
        for key in ("asset_class", "symbol"):
            if str(feature_columns.get(key)) != str(work_unit[key]):
                issues[f"work_unit_identity_mismatch:{key}"] += 1
        day = str(feature_columns.get("signal_day"))
        if not (str(work_unit["period_start"]) <= day <= str(work_unit["period_end"])):
            issues["signal_day_outside_work_unit"] += 1
    return issues


def _scan_unit_evidence(
    path: Path, *, table: str, run_id: str
) -> tuple[dict[str, dict[str, object]], int, int, str, str]:
    if table == "feature_rows":
        query = (
            "SELECT work_unit_id,case_id,feature_fingerprint,NULL "
            "FROM feature_rows WHERE run_id=? ORDER BY work_unit_id,case_id"
        )
    elif table == "outcome_rows":
        query = (
            "SELECT work_unit_id,case_id,outcome_fingerprint,feature_fingerprint "
            "FROM outcome_rows WHERE run_id=? ORDER BY work_unit_id,case_id"
        )
    else:
        raise ValueError(table)
    result: dict[str, dict[str, object]] = {}
    total = 0
    stream = hashlib.sha256()
    case_stream = hashlib.sha256()
    current_id: str | None = None
    current_rows: list[tuple[str, str, str | None]] = []

    def finish() -> None:
        if current_id is None:
            return
        result[current_id] = {
            "rows": len(current_rows),
            "case_set_digest": fingerprint([row[0] for row in current_rows]),
            "payload_digest": fingerprint(current_rows),
        }

    with _ro(path) as connection:
        for unit_id, case_id, payload_fp, feature_fp in connection.execute(query, (run_id,)):
            unit_id = str(unit_id)
            if current_id is not None and unit_id != current_id:
                finish()
                current_rows = []
            current_id = unit_id
            row = (
                str(case_id),
                str(payload_fp),
                None if feature_fp is None else str(feature_fp),
            )
            current_rows.append(row)
            stream.update(canonical_json(row).encode("utf-8"))
            stream.update(b"\n")
            case_stream.update(str(case_id).encode("utf-8"))
            case_stream.update(b"\n")
            total += 1
        finish()
        foreign = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE run_id<>?", (run_id,)
            ).fetchone()[0]
        )
    return result, total, foreign, stream.hexdigest(), case_stream.hexdigest()


def _table_duplicate_count(connection: sqlite3.Connection, table: str, key: str) -> int:
    return int(
        connection.execute(
            f"SELECT COALESCE(SUM(n-1),0) FROM "
            f"(SELECT COUNT(*) n FROM {table} GROUP BY {key} HAVING COUNT(*)>1)"
        ).fetchone()[0]
    )


def build_v6_full_audit(
    *,
    run_id: str,
    feature_path: Path,
    outcome_path: Path,
    control_path: Path,
    expected_work_plan: Mapping[str, object] | Path | str,
    final_contract: Mapping[str, object] | Path | str,
    input_precheck: Mapping[str, object] | Path | str,
    expected_run_manifest: Mapping[str, object] | Path | str,
    artifact_path: Path = DEFAULT_AUDIT_ARTIFACT,
    created_at: str,
    protected_source_paths: Mapping[str, Path | str] | None = None,
) -> dict[str, object]:
    """Audit all v6 evidence and create one immutable final JSON artifact."""

    plan = _load_mapping(expected_work_plan)
    contract, precheck, provenance, provenance_issues = _load_provenance_context(
        final_contract=final_contract,
        input_precheck=input_precheck,
        protected_source_paths=protected_source_paths,
    )
    manifest = _load_mapping(expected_run_manifest)
    manifest_provenance, manifest_issues = _run_manifest_provenance(
        manifest=manifest,
        contract=contract,
        precheck=precheck,
        contract_artifact_fingerprint=dict(provenance["contract"]).get(
            "contract_artifact_fingerprint"
        ),
    )
    provenance.pop("binding_fingerprint", None)
    provenance["run_manifest"] = manifest_provenance
    provenance["binding_fingerprint"] = fingerprint(provenance)
    existing = _validate_existing_artifact(artifact_path)
    if existing is not None:
        if existing.get("version") != AUDIT_VERSION:
            raise DevelopmentV6AuditError(
                "Existing audit uses another audit contract version."
            )
        if existing.get("run_id") != run_id:
            raise DevelopmentV6AuditError("Existing audit belongs to another run.")
        existing_plan = dict(existing.get("expected_work_plan") or {})
        if (
            existing_plan.get("total_planned_work_units")
            != len(plan.get("units") or [])
            or existing_plan.get("provided_work_plan_fingerprint")
            != plan.get("work_plan_fingerprint")
        ):
            raise DevelopmentV6AuditError(
                "Existing audit belongs to another expected work plan."
            )
        run = dict(existing.get("run") or {})
        if (
            manifest.get("run_id") != run_id
            or manifest.get("run_manifest_fingerprint")
            != run.get("run_manifest_fingerprint")
        ):
            raise DevelopmentV6AuditError(
                "Existing audit belongs to another run manifest."
            )
        existing_provenance = dict(existing.get("provenance_bindings") or {})
        if (
            provenance_issues
            or manifest_issues
            or existing_provenance.get("binding_fingerprint")
            != provenance.get("binding_fingerprint")
        ):
            raise DevelopmentV6AuditError(
                "Existing audit no longer matches the frozen contract/input provenance."
            )
        return existing

    plan_units = {
        str(item["work_unit_id"]): dict(item) for item in plan.get("units") or []
    }
    issues: Counter[str] = Counter(provenance_issues)
    issues.update(manifest_issues)
    if len(plan_units) != len(plan.get("units") or []):
        issues["duplicate_work_unit_in_expected_plan"] += 1
    if int(plan.get("total_planned_work_units") or -1) != len(plan_units):
        issues["expected_plan_total_mismatch"] += 1
    claimed_plan_fingerprint = plan.get("work_plan_fingerprint")
    if claimed_plan_fingerprint != fingerprint(list(plan.get("units") or [])):
        issues["expected_work_plan_fingerprint_mismatch"] += 1

    health = {
        "feature_store": _database_health(
            feature_path,
            required_triggers=(
                "no_update_store_metadata",
                "no_delete_store_metadata",
                "no_update_feature_rows",
                "no_delete_feature_rows",
            ),
        ),
        "outcome_store": _database_health(
            outcome_path,
            required_triggers=(
                "no_update_store_metadata",
                "no_delete_store_metadata",
                "no_update_outcome_rows",
                "no_delete_outcome_rows",
            ),
        ),
        "control_store": _database_health(
            control_path,
            required_triggers=(
                "no_delete_runs",
                "no_reopen_terminal_run",
                "no_delete_work_units",
                "no_reopen_terminal_work_unit",
                "no_update_unit_receipts",
                "no_delete_unit_receipts",
                "no_update_run_events",
                "no_delete_run_events",
            ),
        ),
    }
    for role, item in health.items():
        for gate in (
            "quick_check_ok",
            "integrity_check_ok",
            "foreign_keys_ok",
            "append_only_triggers_ok",
        ):
            if not item[gate]:
                issues[f"{role}:{gate}"] += 1

    with _ro(control_path) as control:
        run_rows = control.execute(
            "SELECT run_id,contract_fingerprint,combined_input_fingerprint,"
            "universe_fingerprint,work_plan_fingerprint,run_manifest_fingerprint,"
            "code_commit,worker_count,sqlite_writer_count,total_planned_work_units,"
            "status,started_at,completed_at,last_checkpoint_at,pause_reason "
            "FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchall()
        if len(run_rows) != 1:
            raise DevelopmentV6AuditError(
                f"Expected exactly one control run for {run_id}, found {len(run_rows)}."
            )
        run_names = (
            "run_id",
            "contract_fingerprint",
            "combined_input_fingerprint",
            "universe_fingerprint",
            "work_plan_fingerprint",
            "run_manifest_fingerprint",
            "code_commit",
            "worker_count",
            "sqlite_writer_count",
            "total_planned_work_units",
            "status",
            "started_at",
            "completed_at",
            "last_checkpoint_at",
            "pause_reason",
        )
        run = dict(zip(run_names, run_rows[0]))
        unit_names = (
            "work_unit_id",
            "run_id",
            "asset_key",
            "asset_class",
            "symbol",
            "period_start",
            "period_end",
            "status",
            "attempts",
            "feature_rows",
            "outcome_rows",
            "r_na_cases",
            "censored_cases",
            "missing_reference_entry",
            "missingness_exclusions",
            "started_at",
            "completed_at",
            "last_error_class",
            "last_error_message",
        )
        units = {
            str(row[0]): dict(zip(unit_names, row))
            for row in control.execute(
                "SELECT " + ",".join(unit_names) + " FROM work_units WHERE run_id=?",
                (run_id,),
            )
        }
        receipt_names = (
            "receipt_id",
            "run_id",
            "work_unit_id",
            "feature_rows",
            "outcome_rows",
            "case_set_digest",
            "feature_payload_digest",
            "outcome_payload_digest",
            "writer_pid",
            "committed_at",
            "summary_json",
        )
        receipts = {
            str(row[2]): dict(zip(receipt_names, row))
            for row in control.execute(
                "SELECT " + ",".join(receipt_names) + " FROM unit_receipts WHERE run_id=?",
                (run_id,),
            )
        }
        event_count = int(
            control.execute(
                "SELECT COUNT(*) FROM run_events WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
        foreign_control_rows = {
            table: int(
                control.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE run_id<>?", (run_id,)
                ).fetchone()[0]
            )
            for table in ("runs", "work_units", "unit_receipts", "run_events")
        }
        control_duplicates = {
            "runs_run_id": _table_duplicate_count(control, "runs", "run_id"),
            "work_units_work_unit_id": _table_duplicate_count(
                control, "work_units", "work_unit_id"
            ),
            "receipts_work_unit_id": _table_duplicate_count(
                control, "unit_receipts", "work_unit_id"
            ),
            "receipts_receipt_id": _table_duplicate_count(
                control, "unit_receipts", "receipt_id"
            ),
            "events_event_id": _table_duplicate_count(control, "run_events", "event_id"),
        }

    if str(run["status"]) != "COMPLETED":
        issues["run_not_completed"] += 1
    if run["completed_at"] is None:
        issues["run_completed_at_missing"] += 1
    if int(run["sqlite_writer_count"]) != 1:
        issues["sqlite_writer_count_not_one"] += 1
    if int(run["total_planned_work_units"]) != len(plan_units):
        issues["run_plan_total_mismatch"] += 1
    if str(run["work_plan_fingerprint"]) != str(claimed_plan_fingerprint):
        issues["run_work_plan_fingerprint_mismatch"] += 1
    if set(units) != set(plan_units):
        issues["control_expected_work_unit_set_mismatch"] += 1
    for unit_id, expected in plan_units.items():
        actual = units.get(unit_id)
        if actual is None:
            continue
        for key in ("asset_key", "asset_class", "symbol", "period_start", "period_end"):
            if str(actual.get(key)) != str(expected.get(key)):
                issues[f"expected_work_unit_field_mismatch:{key}"] += 1
    if any(control_duplicates.values()):
        issues["control_duplicate_primary_or_unique_key"] += sum(control_duplicates.values())
    for table, count in foreign_control_rows.items():
        if count:
            issues[f"foreign_run_control_rows:{table}"] += count

    expected_fields = {
        "run_id": "run_id",
        "development_contract_fingerprint": "contract_fingerprint",
        "combined_input_fingerprint": "combined_input_fingerprint",
        "universe_fingerprint": "universe_fingerprint",
        "work_plan_fingerprint": "work_plan_fingerprint",
        "run_manifest_fingerprint": "run_manifest_fingerprint",
        "commit": "code_commit",
        "worker_count": "worker_count",
        "sqlite_writer_count": "sqlite_writer_count",
        "total_planned_work_units": "total_planned_work_units",
    }
    for source_key, run_key in expected_fields.items():
        if str(manifest.get(source_key)) != str(run.get(run_key)):
            issues[f"run_manifest_field_mismatch:{source_key}"] += 1

    (
        feature_units,
        feature_total,
        feature_foreign,
        feature_stream_digest,
        feature_case_stream_digest,
    ) = (
        _scan_unit_evidence(feature_path, table="feature_rows", run_id=run_id)
    )
    (
        outcome_units,
        outcome_total,
        outcome_foreign,
        outcome_stream_digest,
        outcome_case_stream_digest,
    ) = (
        _scan_unit_evidence(outcome_path, table="outcome_rows", run_id=run_id)
    )
    if feature_foreign:
        issues["foreign_run_feature_rows"] += feature_foreign
    if outcome_foreign:
        issues["foreign_run_outcome_rows"] += outcome_foreign

    status_counts = Counter(str(unit["status"]) for unit in units.values())
    unit_classification_counts: Counter[str] = Counter()
    skip_reason_counts: Counter[str] = Counter()
    skip_reason_asset_class_counts: dict[str, Counter[str]] = {
        reason_code: Counter() for reason_code in ALLOWED_SKIP_REASON_CODES
    }
    for unit_id, unit in units.items():
        status = str(unit["status"])
        receipt = receipts.get(unit_id)
        fstats = feature_units.get(
            unit_id,
            {"rows": 0, "case_set_digest": fingerprint([]), "payload_digest": fingerprint([])},
        )
        ostats = outcome_units.get(
            unit_id,
            {"rows": 0, "case_set_digest": fingerprint([]), "payload_digest": fingerprint([])},
        )
        if status not in _TERMINAL_UNIT_STATUSES:
            unit_classification_counts["NON_TERMINAL_INVALID"] += 1
            issues[f"non_terminal_work_unit:{status}"] += 1
            continue
        if receipt is None:
            unit_classification_counts["TERMINAL_WITHOUT_RECEIPT_INVALID"] += 1
            issues["terminal_work_unit_without_receipt"] += 1
            continue
        try:
            parsed_summary = json.loads(str(receipt["summary_json"]))
        except json.JSONDecodeError:
            parsed_summary = {}
            issues["receipt_summary_invalid_json"] += 1
        if not isinstance(parsed_summary, dict):
            summary = {}
            issues["receipt_summary_not_object"] += 1
        else:
            summary = parsed_summary
        if canonical_json(summary) != str(receipt["summary_json"]):
            issues["receipt_summary_not_canonical"] += 1
        comparisons = {
            "feature_rows": int(fstats["rows"]),
            "outcome_rows": int(ostats["rows"]),
            "case_set_digest": str(fstats["case_set_digest"]),
            "feature_payload_digest": str(fstats["payload_digest"]),
            "outcome_payload_digest": str(ostats["payload_digest"]),
        }
        if str(fstats["case_set_digest"]) != str(ostats["case_set_digest"]):
            issues["unit_feature_outcome_case_set_mismatch"] += 1
        for key, expected in comparisons.items():
            actual = receipt[key]
            if str(actual) != str(expected):
                issues[f"receipt_evidence_mismatch:{key}"] += 1
        for key in ("feature_rows", "outcome_rows"):
            if int(unit[key]) != int(fstats["rows"] if key == "feature_rows" else ostats["rows"]):
                issues[f"work_unit_evidence_count_mismatch:{key}"] += 1
        for key in _SUMMARY_COUNTERS:
            if int(unit[key]) != int(summary.get(key) or 0):
                issues[f"work_unit_summary_count_mismatch:{key}"] += 1
        if str(receipt["run_id"]) != run_id or str(receipt["work_unit_id"]) != unit_id:
            issues["receipt_run_or_unit_link_mismatch"] += 1
        if int(receipt["writer_pid"]) <= 0:
            issues["receipt_writer_pid_invalid"] += 1
        if status == "SKIPPED":
            if int(fstats["rows"]) or int(ostats["rows"]):
                issues["skipped_unit_contains_evidence"] += 1
            reason_code = str(summary.get("skip_reason_code") or "").strip()
            reason_text = str(summary.get("skip_reason") or "").strip()
            if not reason_code:
                issues["skipped_unit_without_reason_code"] += 1
            elif reason_code not in ALLOWED_SKIP_REASON_CODES:
                issues[f"skipped_unit_unapproved_reason_code:{reason_code}"] += 1
            else:
                skip_reason_counts[reason_code] += 1
                skip_reason_asset_class_counts[reason_code][
                    str(unit.get("asset_class") or "UNKNOWN")
                ] += 1
            if not reason_text:
                issues["skipped_unit_without_reason_text"] += 1
            if str(unit.get("last_error_class") or "") != reason_code:
                issues["skipped_unit_reason_code_control_mismatch"] += 1
            if str(unit.get("last_error_message") or "") != reason_text:
                issues["skipped_unit_reason_text_control_mismatch"] += 1
            expected_receipt = "madv6-receipt-" + fingerprint(
                {"run_id": run_id, "work_unit_id": unit_id, "summary": summary}
            )[:32]
            unit_classification_counts["SKIPPED_WITH_EMPTY_RECEIPT"] += 1
        else:
            if summary.get("skip_reason_code") is not None or summary.get(
                "skip_reason"
            ) is not None:
                issues["completed_unit_contains_skip_classification"] += 1
            if int(fstats["rows"]) != int(ostats["rows"]):
                issues["completed_unit_feature_outcome_count_mismatch"] += 1
            basis = {
                "run_id": run_id,
                "work_unit_id": unit_id,
                "case_set_digest": receipt["case_set_digest"],
                "feature_payload_digest": receipt["feature_payload_digest"],
                "outcome_payload_digest": receipt["outcome_payload_digest"],
                "summary": summary,
            }
            expected_receipt = "madv6-receipt-" + fingerprint(basis)[:32]
            unit_classification_counts["COMPLETED_RECONCILED"] += 1
        if str(receipt["receipt_id"]) != expected_receipt:
            issues["receipt_id_fingerprint_mismatch"] += 1

    if set(receipts) != {
        unit_id for unit_id, unit in units.items() if str(unit["status"]) in _TERMINAL_UNIT_STATUSES
    }:
        issues["receipt_terminal_work_unit_set_mismatch"] += 1

    with _ro(feature_path) as feature_db:
        feature_db.execute(
            "ATTACH DATABASE ? AS outcomes",
            (f"file:{Path(outcome_path).resolve().as_posix()}?mode=ro",),
        )
        feature_only = int(
            feature_db.execute(
                "SELECT COUNT(*) FROM feature_rows f LEFT JOIN outcomes.outcome_rows o "
                "ON o.case_id=f.case_id WHERE f.run_id=? AND o.case_id IS NULL",
                (run_id,),
            ).fetchone()[0]
        )
        outcome_only = int(
            feature_db.execute(
                "SELECT COUNT(*) FROM outcomes.outcome_rows o LEFT JOIN feature_rows f "
                "ON f.case_id=o.case_id WHERE o.run_id=? AND f.case_id IS NULL",
                (run_id,),
            ).fetchone()[0]
        )
        feature_duplicates = _table_duplicate_count(feature_db, "feature_rows", "case_id")
        outcome_duplicates = _table_duplicate_count(
            feature_db, "outcomes.outcome_rows", "case_id"
        )
        if feature_only:
            issues["feature_orphans"] += feature_only
        if outcome_only:
            issues["outcome_orphans"] += outcome_only
        if feature_duplicates:
            issues["duplicate_feature_case_ids"] += feature_duplicates
        if outcome_duplicates:
            issues["duplicate_outcome_case_ids"] += outcome_duplicates

        select = ",".join(
            [f"f.{name}" for name in _FEATURE_COLUMNS]
            + [f"o.{name}" for name in _OUTCOME_COLUMNS]
            + ["f.payload_zlib", "o.payload_zlib"]
        )
        audited_pairs = 0
        payload_unit_counters: dict[str, Counter[str]] = {}
        payload_digest = hashlib.sha256()
        contract_references = dict(contract.get("reference_fingerprints") or {})
        expected_payload_provenance = {
            "run_id": run_id,
            "run_manifest_fingerprint": manifest.get("run_manifest_fingerprint"),
            "contract_version": contract.get("contract_version"),
            "contract_fingerprint": contract.get("contract_fingerprint"),
            "combined_input_fingerprint": contract_references.get(
                "combined_input_fingerprint"
            ),
            "projection_fingerprints": {
                "EQUITIES": contract_references.get(
                    "equity_etf_projection_fingerprint"
                ),
                "ETF": contract_references.get("equity_etf_projection_fingerprint"),
                "CRYPTO": contract_references.get("crypto_projection_fingerprint"),
                "FX": contract_references.get("fx_projection_fingerprint"),
            },
            "gap_policy_fingerprint": contract_references.get(
                "gap_policy_fingerprint"
            ),
            "historical_dependency_policy_version": contract_references.get(
                "historical_dependency_policy_version"
            ),
            "historical_dependency_policy_fingerprint": contract_references.get(
                "historical_dependency_policy_fingerprint"
            ),
        }
        for row in feature_db.execute(
            f"SELECT {select} FROM feature_rows f JOIN outcomes.outcome_rows o "
            "ON o.case_id=f.case_id WHERE f.run_id=? AND o.run_id=? ORDER BY f.case_id",
            (run_id, run_id),
        ):
            feature_columns = dict(zip(_FEATURE_COLUMNS, row[: len(_FEATURE_COLUMNS)]))
            offset = len(_FEATURE_COLUMNS)
            outcome_columns = dict(
                zip(_OUTCOME_COLUMNS, row[offset : offset + len(_OUTCOME_COLUMNS)])
            )
            feature_blob = row[-2]
            outcome_blob = row[-1]
            try:
                feature = json.loads(zlib.decompress(feature_blob).decode("utf-8"))
            except Exception:  # corrupt evidence is recorded, never ignored
                issues["feature_payload_decode_failure"] += 1
                continue
            try:
                outcome = json.loads(zlib.decompress(outcome_blob).decode("utf-8"))
            except Exception:
                issues["outcome_payload_decode_failure"] += 1
                continue
            unit = units.get(str(feature_columns["work_unit_id"]))
            unit_counter = payload_unit_counters.setdefault(
                str(feature_columns["work_unit_id"]), Counter()
            )
            if outcome.get("r_metrics_status") != "AVAILABLE":
                unit_counter["r_na_cases"] += 1
            if str(outcome.get("status") or "").startswith("CENSORED_"):
                unit_counter["censored_cases"] += 1
            if outcome.get("status") == "CENSORED_AT_INPUT_GAP":
                unit_counter["input_gap_censored_cases"] += 1
            if outcome.get("status") == "CENSORED_AT_END_OF_AVAILABLE_DATA":
                unit_counter["end_of_data_censored_cases"] += 1
            if outcome.get("status") == "CENSORED_AT_STAGE_BOUNDARY":
                unit_counter["stage_censored_cases"] += 1
            issues.update(
                _audit_payload_pair(
                    feature_columns,
                    outcome_columns,
                    feature,
                    outcome,
                    work_unit=unit,
                    expected_provenance=expected_payload_provenance,
                )
            )
            payload_digest.update(
                canonical_json(
                    [
                        feature_columns["case_id"],
                        feature_columns["feature_fingerprint"],
                        outcome_columns["outcome_fingerprint"],
                    ]
                ).encode("utf-8")
            )
            payload_digest.update(b"\n")
            audited_pairs += 1

    for unit_id, receipt in receipts.items():
        try:
            summary = json.loads(str(receipt["summary_json"]))
        except json.JSONDecodeError:
            continue
        observed = payload_unit_counters.get(unit_id, Counter())
        for key in (
            "r_na_cases",
            "censored_cases",
            "input_gap_censored_cases",
            "end_of_data_censored_cases",
            "stage_censored_cases",
        ):
            if int(summary.get(key) or 0) != int(observed[key]):
                issues[f"receipt_payload_classification_mismatch:{key}"] += 1

    metadata_summary: dict[str, object] = {}
    expected_store_metadata = {
        "run_id": run_id,
        "contract_fingerprint": contract.get("contract_fingerprint"),
        "combined_input_fingerprint": dict(
            contract.get("reference_fingerprints") or {}
        ).get("combined_input_fingerprint"),
        "run_manifest_fingerprint": manifest.get("run_manifest_fingerprint"),
    }
    for role, path, expected_role in (
        ("feature_store", feature_path, "FEATURES"),
        ("outcome_store", outcome_path, "OUTCOMES"),
    ):
        valid = 0
        count = 0
        roles: Counter[str] = Counter()
        metadata_bindings: list[dict[str, dict[str, object]]] = []
        with _ro(path) as connection:
            rows = connection.execute(
                "SELECT metadata_fingerprint,metadata_json FROM store_metadata"
            )
            for claimed, encoded in rows:
                count += 1
                try:
                    item = json.loads(str(encoded))
                except json.JSONDecodeError:
                    issues[f"{role}:metadata_invalid_json"] += 1
                    continue
                if str(claimed) != fingerprint(item):
                    issues[f"{role}:metadata_fingerprint_mismatch"] += 1
                else:
                    valid += 1
                roles[str(item.get("store_role"))] += 1
                if item.get("append_only") is not True:
                    issues[f"{role}:append_only_metadata_missing_or_false"] += 1
                row_bindings: dict[str, dict[str, object]] = {}
                for name, expected_value in expected_store_metadata.items():
                    _record_binding(
                        row_bindings,
                        issues,
                        name=f"{role}_metadata:{name}",
                        expected=expected_value,
                        actual=item.get(name),
                    )
                metadata_bindings.append(row_bindings)
        if count != 1:
            issues[f"{role}:metadata_row_count_not_one"] += 1
        if roles != Counter({expected_role: 1}):
            issues[f"{role}:metadata_role_mismatch"] += 1
        metadata_summary[role] = {
            "rows": count,
            "valid_self_fingerprints": valid,
            "roles": dict(sorted(roles.items())),
            "expected_frozen_chain_values": expected_store_metadata,
            "row_bindings": metadata_bindings,
            "all_rows_bound_to_frozen_chain": bool(metadata_bindings)
            and all(
                all(binding["matches"] for binding in row.values())
                for row in metadata_bindings
            ),
        }

    receipt_digest = hashlib.sha256()
    for unit_id in sorted(receipts):
        receipt = receipts[unit_id]
        receipt_digest.update(
            canonical_json(
                [
                    receipt["receipt_id"],
                    receipt["work_unit_id"],
                    receipt["case_set_digest"],
                    receipt["feature_payload_digest"],
                    receipt["outcome_payload_digest"],
                    receipt["summary_json"],
                ]
            ).encode("utf-8")
        )
        receipt_digest.update(b"\n")
    work_unit_digest = hashlib.sha256()
    for unit_id in sorted(units):
        unit = units[unit_id]
        work_unit_digest.update(canonical_json(unit).encode("utf-8"))
        work_unit_digest.update(b"\n")

    skipped_total = int(status_counts.get("SKIPPED") or 0)
    classified_skipped_total = int(sum(skip_reason_counts.values()))
    skip_classification_issue_prefixes = (
        "skipped_unit_without_reason",
        "skipped_unit_unapproved_reason_code:",
        "skipped_unit_reason_code_control_mismatch",
        "skipped_unit_reason_text_control_mismatch",
    )
    all_skipped_units_reconciled = (
        classified_skipped_total == skipped_total
        and not any(
            key.startswith(skip_classification_issue_prefixes) for key in issues
        )
    )
    skipped_work_unit_exclusions: dict[str, object] = {
        "classification_source": "unit_receipts.summary_json.skip_reason_code",
        "control_reconciliation": (
            "work_units.last_error_class_and_last_error_message_exact_match"
        ),
        "allowed_reason_codes": sorted(ALLOWED_SKIP_REASON_CODES),
        "total_skipped_work_units": skipped_total,
        "classified_skipped_work_units": classified_skipped_total,
        "all_skipped_units_reconciled": all_skipped_units_reconciled,
        "by_reason_code": {
            reason_code: {
                "work_units": int(skip_reason_counts.get(reason_code) or 0),
                "by_asset_class": dict(
                    sorted(skip_reason_asset_class_counts[reason_code].items())
                ),
            }
            for reason_code in sorted(ALLOWED_SKIP_REASON_CODES)
        },
        "free_text_reinterpreted_as_reason_code": False,
    }

    payload: dict[str, object] = {
        "version": AUDIT_VERSION,
        "status": "PASS" if not issues else "FAIL",
        "created_at": created_at,
        "run_id": run_id,
        "source_stores_opened_read_only": True,
        "no_sampling": True,
        "all_feature_outcome_payload_pairs_audited": audited_pairs
        == feature_total
        == outcome_total,
        "run": run,
        "provenance_bindings": provenance,
        "per_payload_provenance_contract": {
            **expected_payload_provenance,
            "contract_fingerprint_present_in_feature_payload": False,
            "contract_fingerprint_present_in_outcome_payload": False,
            "feature_binding": (
                "DIRECT_CONTRACT_VERSION_INPUT_PROJECTION_GAP_DEPENDENCY_FIELDS_"
                "PLUS_SELF_FINGERPRINT_AND_STORE_RUN_WORK_UNIT_COLUMNS"
            ),
            "outcome_binding": (
                "DIRECT_CONTRACT_VERSION_AND_DEPENDENCY_STATUS_PLUS_EXACT_"
                "FEATURE_FINGERPRINT_AND_STORE_RUN_WORK_UNIT_COLUMNS"
            ),
            "contract_fingerprint_binding": (
                "TRANSITIVE_VIA_SELF_FINGERPRINTED_STORE_METADATA_BOUND_TO_"
                "RUN_MANIFEST_AND_EXACT_PAYLOAD_RUN_WORK_UNIT_LINKS"
            ),
            "outcome_input_provenance_is_transitive_via_feature_fingerprint": True,
        },
        "expected_work_plan": {
            "total_planned_work_units": len(plan_units),
            "provided_work_plan_fingerprint": plan.get("work_plan_fingerprint")
            or plan.get("artifact_fingerprint"),
        },
        "sqlite": health,
        "append_only_metadata": metadata_summary,
        "counts": {
            "feature_rows": feature_total,
            "outcome_rows": outcome_total,
            "audited_payload_pairs": audited_pairs,
            "work_units": len(units),
            "receipts": len(receipts),
            "run_events": event_count,
            "feature_only_orphans": feature_only,
            "outcome_only_orphans": outcome_only,
            "duplicate_feature_case_ids": feature_duplicates,
            "duplicate_outcome_case_ids": outcome_duplicates,
            "foreign_run_feature_rows": feature_foreign,
            "foreign_run_outcome_rows": outcome_foreign,
        },
        "work_unit_status_counts": dict(sorted(status_counts.items())),
        "work_unit_classification_counts": dict(
            sorted(unit_classification_counts.items())
        ),
        "skipped_work_unit_exclusions": skipped_work_unit_exclusions,
        "control_duplicate_counts": control_duplicates,
        "foreign_run_control_row_counts": foreign_control_rows,
        "digests": {
            "digest_encoding": "sha256(canonical-json-row + LF), ordered",
            "feature_evidence_stream_sha256": feature_stream_digest,
            "outcome_evidence_stream_sha256": outcome_stream_digest,
            "feature_case_membership_stream_sha256": feature_case_stream_digest,
            "outcome_case_membership_stream_sha256": outcome_case_stream_digest,
            "verified_payload_pair_stream_sha256": payload_digest.hexdigest(),
            "receipt_stream_sha256": receipt_digest.hexdigest(),
            "work_unit_stream_sha256": work_unit_digest.hexdigest(),
            "run_record_fingerprint": fingerprint(run),
            "expected_work_plan_units_fingerprint": fingerprint(
                list(plan.get("units") or [])
            ),
        },
        "issue_count": int(sum(issues.values())),
        "issues": dict(sorted(issues.items())),
        "gates": {
            "frozen_contract_self_valid_and_bound_to_pass_input_precheck": not bool(
                provenance_issues
            ),
            "all_protected_input_hashes_reverified": bool(
                dict(provenance["protected_sources"]).get("all_hashes_match")
            ),
            "all_implementation_hashes_reverified": bool(
                dict(provenance["protected_implementation"]).get(
                    "all_hashes_match"
                )
            ),
            "run_manifest_self_valid_and_bound_to_frozen_chain": not bool(
                manifest_issues
            ),
            "store_metadata_bound_to_contract_input_and_run_manifest": all(
                int(item["rows"]) == 1
                and int(item["valid_self_fingerprints"]) == 1
                and bool(item["all_rows_bound_to_frozen_chain"])
                for item in metadata_summary.values()
            ),
            "run_completed": str(run["status"]) == "COMPLETED",
            "expected_work_unit_set_exact": set(units) == set(plan_units),
            "all_units_terminal": all(
                str(unit["status"]) in _TERMINAL_UNIT_STATUSES
                for unit in units.values()
            ),
            "one_receipt_per_terminal_unit": len(receipts) == len(units),
            "all_skipped_units_have_allowed_reconciled_reason": (
                all_skipped_units_reconciled
            ),
            "feature_outcome_case_sets_equal": not feature_only and not outcome_only,
            "all_payload_fingerprints_and_links_valid": not any(
                key.startswith(
                    (
                        "feature_payload",
                        "outcome_payload",
                        "feature_outcome",
                        "feature_contract",
                        "outcome_contract",
                        "feature_combined_input",
                        "feature_projection",
                        "feature_gap_policy",
                        "feature_source_fingerprint",
                        "feature_dataset_fingerprint",
                        "feature_input_provenance",
                        "feature_dependency",
                        "fx_dependency",
                        "fx_unexpected_historical_dependency",
                        "outcome_input_provenance",
                        "feature_run_manifest",
                        "outcome_run_manifest",
                        "work_unit_run_manifest",
                    )
                )
                for key in issues
            ),
            "sqlite_integrity_passed": all(
                item["quick_check_ok"]
                and item["integrity_check_ok"]
                and item["foreign_keys_ok"]
                for item in health.values()
            ),
            "append_only_controls_present": all(
                item["append_only_triggers_ok"] for item in health.values()
            ),
            "single_sqlite_writer_recorded": int(run["sqlite_writer_count"]) == 1,
        },
        "scope_guards": {
            "development_only": True,
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
            "forward_paper_shadow_or_broker_opened": False,
            "strategy_performance_analysis_performed": False,
        },
    }
    # No gate can be false while status claims PASS, even if a future schema
    # adds a gate without a corresponding issue counter.
    if not all(bool(value) for value in payload["gates"].values()):
        payload["status"] = "FAIL"
    payload["artifact_fingerprint"] = _artifact_fingerprint(payload)
    return _write_once(Path(artifact_path), payload)


# Short aliases used by the chain layer.
build_full_audit = build_v6_full_audit


__all__ = [
    "ALLOWED_SKIP_REASON_CODES",
    "AUDIT_VERSION",
    "DEFAULT_AUDIT_ARTIFACT",
    "DevelopmentV6AuditError",
    "build_full_audit",
    "build_v6_full_audit",
    "verify_self_fingerprinted_artifact",
]
