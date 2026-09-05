from __future__ import annotations

"""Fail-closed reprocessing contract for Multi-Asset Development v6.

The completed v5 Development contract is the immutable parent.  This module
does not rebuild research semantics: it copies the frozen v5 contract and may
only apply the technical changes explicitly classified below.  The contract
cannot be loaded or frozen until the input precheck, worker benchmark and
descriptive-plan artifacts exist, validate their own fingerprints and expose
their required PASS/FROZEN states.
"""

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from multi_asset_development_v6_benchmark import (
    REQUIRED_TECHNICAL_COVERAGE_GATES,
    classify_worker_configurations,
    configuration_evidence_checks,
    eligible_worker_counts,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_V6_CONFIG_PATH = (
    PROJECT_ROOT / "config" / "multi_asset_discovery_development_v6.json"
)

DEVELOPMENT_V6_CONTRACT_VERSION = (
    "multi-asset-opportunity-discovery-development-2026.09.05-v6"
)
DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION = (
    "multi-asset-development-contract-artifact-2026.09.05-v6"
)
DEVELOPMENT_V6_CONTRACT_DIFF_VERSION = (
    "multi-asset-development-contract-diff-2026.09.05-v6"
)
DEVELOPMENT_V5_CONTRACT_VERSION = (
    "multi-asset-opportunity-discovery-development-2026.09.01-v5"
)

ALLOWED_REPAIR_CATEGORIES = frozenset(
    {
        "DATA_PROJECTION",
        "MISSINGNESS_VALIDITY",
        "TERMINAL_RETRY",
        "WORKER_RUNTIME",
        "OUTPUT_PROVENANCE",
    }
)
ALLOWED_WORKER_COUNTS = (1, 2, 4, 6)
LIFECYCLE_CHAIN = (
    "PRECHECK",
    "RUN",
    "FINAL_AUDIT",
    "DESCRIPTIVE_REPORT",
    "SUMMARY",
    "STOP",
)
SEMANTIC_INVARIANT_ROOTS = (
    "analysis_resolution",
    "asset_class_analysis",
    "candidate_generation",
    "dependency_contract",
    "deterioration_contract",
    "feature_contract",
    "lifecycle",
    "market_scope",
    "outcome_contract",
    "parent_contract",
    "pilot_contract",
    "point_in_time",
    "research_role",
    "safe_zone_contract",
    "sell_zone_contract",
    "stage_contract",
)

_REQUIRED_INPUT_FINGERPRINTS = (
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
    "implementation_fingerprint",
)
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


class MultiAssetDevelopmentV6ContractError(ValueError):
    """v6 cannot prove an immutable parent or an authorized technical diff."""


def _grouped_safe_prefixes() -> dict[str, str]:
    data_projection = {
        "reference_fingerprints.dataset_fingerprint",
        "reference_fingerprints.dataset_manifest_sha256",
        "reference_fingerprints.fx_dataset_fingerprint",
        "reference_fingerprints.identity_registry_fingerprint",
        "reference_fingerprints.combined_input_fingerprint",
        "reference_fingerprints.equity_etf_projection_fingerprint",
        "reference_fingerprints.crypto_projection_fingerprint",
        "reference_fingerprints.fx_projection_fingerprint",
        "reference_fingerprints.equity_etf_store_sha256",
        "reference_fingerprints.crypto_store_sha256",
        "reference_fingerprints.fx_store_sha256",
        "reference_fingerprints.source_dataset_manifest_sha256",
        "reference_fingerprints.identity_store_sha256",
        "reference_fingerprints.input_precheck_artifact_fingerprint",
        "development_execution.input_precheck_artifact",
        "technical_reprocessing_contract.data_projection",
    }
    missingness = {
        "reference_fingerprints.gap_policy_fingerprint",
        "technical_reprocessing_contract.missingness_validity",
    }
    terminal_retry = {
        "store_contract.work_unit_completion_receipt_required",
        "store_contract.incomplete_write_reconciliation_required",
        "development_execution.terminal_noop_after_stop",
        "technical_reprocessing_contract.terminal_retry",
    }
    worker_runtime = {
        "reference_fingerprints.worker_benchmark_artifact_fingerprint",
        "development_execution.worker_count",
        "development_execution.worker_benchmark_artifact",
        "technical_reprocessing_contract.worker_runtime",
    }
    output_provenance = {
        "contract_version",
        "reprocessing_parent",
        "technical_reprocessing_contract.authorized_categories",
        "reference_fingerprints.development_code_fingerprint",
        "reference_fingerprints.descriptive_plan_artifact_fingerprint",
        "store_contract.feature_store",
        "store_contract.outcome_store",
        "store_contract.control_store",
        "store_contract.schema_version",
        "development_execution.research_epoch",
        "development_execution.process_lock",
        "development_execution.chain_state",
        "development_execution.run_manifest",
        "development_execution.contract_artifact",
        "development_execution.contract_diff_artifact",
        "development_execution.readiness_artifact",
        "development_execution.descriptive_plan_artifact",
        "development_execution.final_audit_artifact",
        "development_execution.descriptive_report_artifact",
        "development_execution.completion_summary_artifact",
        "development_execution.log_path",
        "development_execution.runner_script",
        "development_execution.scheduler_wrapper",
        "development_execution.scheduler_task_name",
        "development_execution.development_not_before",
        "development_execution.full_development_run_allowed",
        "development_execution.lifecycle_chain",
        "development_execution.chain_transition_requires_prior_pass",
        "development_execution.final_audit_required_before_report",
        "development_execution.stop_after_summary",
        "technical_reprocessing_contract.output_provenance",
    }
    result: dict[str, str] = {}
    for category, paths in (
        ("DATA_PROJECTION", data_projection),
        ("MISSINGNESS_VALIDITY", missingness),
        ("TERMINAL_RETRY", terminal_retry),
        ("WORKER_RUNTIME", worker_runtime),
        ("OUTPUT_PROVENANCE", output_provenance),
    ):
        result.update({path: category for path in paths})
    return result


_SAFE_PREFIX_CATEGORIES = _grouped_safe_prefixes()


def _load_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} ist nicht lesbar: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} muss ein JSON-Objekt sein: {path}"
        )
    return value


def _require_hash(value: object, *, label: str) -> str:
    normalized = str(value or "")
    if _HASH_PATTERN.fullmatch(normalized) is None:
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} muss ein exakter lowercase SHA-256/Fingerprint sein."
        )
    return normalized


def _resolve_configured_path(project_root: Path, value: object, *, label: str) -> Path:
    relative = Path(str(value or ""))
    if not str(relative) or relative.is_absolute():
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} muss ein relativer Projektpfad sein."
        )
    root = Path(project_root).resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} verlässt den Projektpfad."
        ) from exc
    return resolved


def _path_matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + ".")


def _validate_config(config: Mapping[str, object]) -> dict[str, object]:
    result = copy.deepcopy(dict(config))
    version_checks = {
        "development_v6_contract_version": DEVELOPMENT_V6_CONTRACT_VERSION,
        "artifact_version": DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
        "diff_version": DEVELOPMENT_V6_CONTRACT_DIFF_VERSION,
    }
    for key, expected in version_checks.items():
        if result.get(key) != expected:
            raise MultiAssetDevelopmentV6ContractError(
                f"Unerwartete v6-Version in {key}."
            )

    parent = dict(result.get("parent_reprocessing") or {})
    required_parent = {
        "artifact_path",
        "artifact_sha256",
        "artifact_version",
        "artifact_fingerprint",
        "contract_version",
        "contract_fingerprint",
        "run_manifest_path",
        "run_manifest_sha256",
        "run_manifest_version",
        "run_manifest_fingerprint",
        "run_id",
    }
    missing_parent = sorted(required_parent - set(parent))
    if missing_parent:
        raise MultiAssetDevelopmentV6ContractError(
            f"v5-Reprocessing-Parent ist unvollständig: {missing_parent}"
        )
    if parent.get("contract_version") != DEVELOPMENT_V5_CONTRACT_VERSION:
        raise MultiAssetDevelopmentV6ContractError(
            "v6 muss exakt den Development-v5-Vertrag als Parent verwenden."
        )
    for key in (
        "artifact_sha256",
        "artifact_fingerprint",
        "contract_fingerprint",
        "run_manifest_sha256",
        "run_manifest_fingerprint",
    ):
        _require_hash(parent.get(key), label=f"parent_reprocessing.{key}")

    required_artifacts = dict(result.get("required_runtime_artifacts") or {})
    expected_artifacts = {
        "input_precheck": ("PASS", "v6-input-precheck"),
        "worker_benchmark": ("PASS", "v6-worker-benchmark"),
        "descriptive_plan": ("FROZEN", "v6-descriptive-plan"),
    }
    if set(required_artifacts) != set(expected_artifacts):
        raise MultiAssetDevelopmentV6ContractError(
            "Genau Input-Precheck, Worker-Benchmark und Auswertungsplan sind Pflicht."
        )
    for name, (status, version_fragment) in expected_artifacts.items():
        specification = dict(required_artifacts[name] or {})
        if specification.get("status") != status:
            raise MultiAssetDevelopmentV6ContractError(
                f"Unerwarteter Pflichtstatus für {name}."
            )
        if version_fragment not in str(specification.get("version") or ""):
            raise MultiAssetDevelopmentV6ContractError(
                f"Unversioniertes Pflichtartefakt: {name}."
            )
        if not specification.get("path"):
            raise MultiAssetDevelopmentV6ContractError(
                f"Pflichtartefaktpfad fehlt: {name}."
            )

    runtime = dict(result.get("runtime") or {})
    if tuple(runtime.get("allowed_worker_counts") or ()) != ALLOWED_WORKER_COUNTS:
        raise MultiAssetDevelopmentV6ContractError(
            "Der begrenzte Worker-Benchmark muss 1/2/4/6 verwenden."
        )
    if runtime.get("sqlite_writer_count") != 1:
        raise MultiAssetDevelopmentV6ContractError(
            "v6 erlaubt weiterhin exakt einen SQLite-Writer."
        )
    if tuple(runtime.get("lifecycle_chain") or ()) != LIFECYCLE_CHAIN:
        raise MultiAssetDevelopmentV6ContractError(
            "Die v6-Lifecycle-Kette ist nicht vollständig geschlossen."
        )
    stores = dict(runtime.get("stores") or {})
    execution = dict(runtime.get("execution") or {})
    if set(stores) != {
        "feature_store",
        "outcome_store",
        "control_store",
        "schema_version",
    }:
        raise MultiAssetDevelopmentV6ContractError("v6-Storedefinition ist unvollständig.")
    required_execution = {
        "process_lock",
        "chain_state",
        "run_manifest",
        "contract_artifact",
        "contract_diff_artifact",
        "start_gate_artifact",
        "final_audit_artifact",
        "descriptive_report_artifact",
        "completion_summary_artifact",
        "log_path",
        "runner_script",
        "scheduler_wrapper",
        "scheduler_task_name",
    }
    if set(execution) != required_execution:
        raise MultiAssetDevelopmentV6ContractError(
            "v6-Ausgabepfade/Runner/Scheduler sind unvollständig oder unerwartet."
        )
    runtime_paths = [
        value
        for key, value in {**stores, **execution}.items()
        if key not in {"schema_version", "scheduler_task_name"}
    ]
    if any("v6" not in str(value).casefold() for value in runtime_paths):
        raise MultiAssetDevelopmentV6ContractError(
            "Jeder neue Store-/Artefakt-/Runnerpfad muss v6-isoliert sein."
        )
    store_paths = [str(stores[key]) for key in ("feature_store", "outcome_store", "control_store")]
    if len(set(store_paths)) != 3:
        raise MultiAssetDevelopmentV6ContractError("v6-Stores müssen getrennt sein.")

    roots = tuple(result.get("semantic_invariant_roots") or ())
    if roots != SEMANTIC_INVARIANT_ROOTS:
        raise MultiAssetDevelopmentV6ContractError(
            "Die fest codierten Research-Semantik-Invarianten wurden verändert."
        )

    rules = list(result.get("authorized_changes") or [])
    seen: set[str] = set()
    for raw in rules:
        rule = dict(raw or {})
        prefix = str(rule.get("prefix") or "")
        category = str(rule.get("category") or "")
        finding = str(rule.get("repair_finding") or "")
        if prefix in seen:
            raise MultiAssetDevelopmentV6ContractError(
                f"Doppelte Diff-Autorisierung: {prefix}"
            )
        seen.add(prefix)
        if _SAFE_PREFIX_CATEGORIES.get(prefix) != category:
            raise MultiAssetDevelopmentV6ContractError(
                f"Nicht erlaubte Diff-Autorisierung: {prefix}/{category}"
            )
        if category not in ALLOWED_REPAIR_CATEGORIES or not finding:
            raise MultiAssetDevelopmentV6ContractError(
                f"Ungültige Reparaturzuordnung: {prefix}"
            )
    if seen != set(_SAFE_PREFIX_CATEGORIES):
        missing = sorted(set(_SAFE_PREFIX_CATEGORIES) - seen)
        extra = sorted(seen - set(_SAFE_PREFIX_CATEGORIES))
        raise MultiAssetDevelopmentV6ContractError(
            f"Diff-Autorisierung unvollständig (fehlend={missing}, extra={extra})."
        )
    return result


def _load_config(path: Path = DEFAULT_V6_CONFIG_PATH) -> dict[str, object]:
    return _validate_config(_load_json(Path(path), label="v6-Konfiguration"))


def _verify_self_fingerprint(
    payload: Mapping[str, object], *, field: str, label: str
) -> str:
    stored = _require_hash(payload.get(field), label=f"{label}.{field}")
    comparable = dict(payload)
    comparable.pop(field, None)
    if stored != fingerprint(comparable):
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} besitzt keinen gültigen Self-Fingerprint."
        )
    return stored


def _verify_contract_fingerprint(contract: Mapping[str, object], *, label: str) -> str:
    stored = _require_hash(
        contract.get("contract_fingerprint"), label=f"{label}.contract_fingerprint"
    )
    comparable = dict(contract)
    comparable.pop("contract_fingerprint", None)
    if stored != fingerprint(comparable):
        raise MultiAssetDevelopmentV6ContractError(
            f"{label} besitzt einen ungültigen Contract-Fingerprint."
        )
    return stored


def _load_parent(
    *,
    config: Mapping[str, object],
    project_root: Path,
    parent_artifact_path: Path | None,
) -> tuple[dict[str, object], dict[str, object]]:
    specification = dict(config["parent_reprocessing"])
    artifact_path = (
        Path(parent_artifact_path).resolve()
        if parent_artifact_path is not None
        else _resolve_configured_path(
            project_root, specification["artifact_path"], label="v5-Parent-Artefakt"
        )
    )
    if not artifact_path.exists():
        raise MultiAssetDevelopmentV6ContractError(
            f"Unveränderliches v5-Parent-Artefakt fehlt: {artifact_path}"
        )
    if file_sha256(artifact_path) != specification["artifact_sha256"]:
        raise MultiAssetDevelopmentV6ContractError(
            "Der Datei-Hash des v5-Parent-Artefakts weicht ab."
        )
    artifact = _load_json(artifact_path, label="v5-Parent-Artefakt")
    artifact_fingerprint = _verify_self_fingerprint(
        artifact, field="artifact_fingerprint", label="v5-Parent-Artefakt"
    )
    if (
        artifact.get("version") != specification["artifact_version"]
        or artifact_fingerprint != specification["artifact_fingerprint"]
    ):
        raise MultiAssetDevelopmentV6ContractError(
            "v5-Parent-Artefaktversion oder -Fingerprint stimmt nicht."
        )
    contract = dict(artifact.get("contract") or {})
    contract_fingerprint = _verify_contract_fingerprint(
        contract, label="v5-Parent-Contract"
    )
    if (
        contract.get("contract_version") != specification["contract_version"]
        or contract_fingerprint != specification["contract_fingerprint"]
        or artifact.get("contract_fingerprint") != contract_fingerprint
    ):
        raise MultiAssetDevelopmentV6ContractError(
            "v5-Parent-Contract ist nicht exakt die eingefrorene Referenz."
        )

    manifest_path = _resolve_configured_path(
        project_root,
        specification["run_manifest_path"],
        label="v5-Parent-Run-Manifest",
    )
    if not manifest_path.exists():
        raise MultiAssetDevelopmentV6ContractError(
            f"Unveränderliches v5-Run-Manifest fehlt: {manifest_path}"
        )
    if file_sha256(manifest_path) != specification["run_manifest_sha256"]:
        raise MultiAssetDevelopmentV6ContractError(
            "Der Datei-Hash des v5-Run-Manifests weicht ab."
        )
    manifest = _load_json(manifest_path, label="v5-Parent-Run-Manifest")
    manifest_fingerprint = _verify_self_fingerprint(
        manifest,
        field="run_manifest_fingerprint",
        label="v5-Parent-Run-Manifest",
    )
    if (
        manifest.get("version") != specification["run_manifest_version"]
        or manifest.get("run_id") != specification["run_id"]
        or manifest_fingerprint != specification["run_manifest_fingerprint"]
        or manifest.get("development_contract_fingerprint")
        != contract_fingerprint
    ):
        raise MultiAssetDevelopmentV6ContractError(
            "v5-Run-Manifest verweist nicht exakt auf den Reprocessing-Parent."
        )
    return artifact, manifest


def _load_required_runtime_artifact(
    *,
    name: str,
    config: Mapping[str, object],
    project_root: Path,
    override_path: Path | None,
) -> tuple[dict[str, object], Path]:
    specification = dict(dict(config["required_runtime_artifacts"])[name])
    path = (
        Path(override_path).resolve()
        if override_path is not None
        else _resolve_configured_path(
            project_root, specification["path"], label=f"{name}-Artefakt"
        )
    )
    if not path.exists():
        raise MultiAssetDevelopmentV6ContractError(
            f"Pflichtartefakt für v6 fehlt: {name} ({path})"
        )
    artifact = _load_json(path, label=f"v6-{name}")
    _verify_self_fingerprint(
        artifact, field="artifact_fingerprint", label=f"v6-{name}"
    )
    if artifact.get("version") != specification["version"]:
        raise MultiAssetDevelopmentV6ContractError(
            f"Unerwartete Artefaktversion für {name}."
        )
    if artifact.get("status") != specification["status"]:
        raise MultiAssetDevelopmentV6ContractError(
            f"v6-{name} ist nicht {specification['status']}."
        )
    return artifact, path


def _validated_worker_benchmark_selection(
    worker_benchmark: Mapping[str, object],
) -> dict[str, object]:
    """Validate the selected worker count against the one-worker reference.

    A failed or scientifically divergent multi-worker attempt is valid
    benchmark evidence, but it can never become a selection candidate. The
    mandatory one-worker run and the finally selected run must both satisfy
    every operational/technical evidence gate and have identical scientific
    payload digests.
    """

    raw_configurations = worker_benchmark.get("configurations")
    configurations = (
        [dict(item) for item in raw_configurations if isinstance(item, Mapping)]
        if isinstance(raw_configurations, list)
        else []
    )
    counts = [item.get("worker_count") for item in configurations]
    resources = dict(worker_benchmark.get("resources") or {})
    expected_counts = list(eligible_worker_counts(resources))
    classification = classify_worker_configurations(configurations)
    decisions = dict(classification.get("configuration_decisions") or {})
    selected = worker_benchmark.get("selected_worker_count")
    selected_decision = dict(decisions.get(str(selected)) or {})
    reference_digest = str(
        classification.get("reference_scientific_digest") or ""
    )
    recomputed_evidence = {
        str(item.get("worker_count")): configuration_evidence_checks(item)
        for item in configurations
    }
    stored_evidence = dict(
        worker_benchmark.get("configuration_evidence_checks") or {}
    )
    raw_runtime_checks = worker_benchmark.get(
        "protected_runtime_checks_before_each_configuration"
    )
    runtime_checks = (
        [dict(item) for item in raw_runtime_checks if isinstance(item, Mapping)]
        if isinstance(raw_runtime_checks, list)
        else []
    )
    runtime_check_counts = [item.get("worker_count") for item in runtime_checks]
    runtime_check_counts_well_formed = all(
        isinstance(item, int) and not isinstance(item, bool)
        for item in runtime_check_counts
    )
    recomputed_all_evidence = bool(recomputed_evidence) and all(
        checks and all(value is True for value in checks.values())
        for checks in recomputed_evidence.values()
    )
    all_tested_equal = bool(reference_digest) and all(
        str(item.get("scientific_digest") or "") == reference_digest
        for item in configurations
    )
    fallback_expected = selected == 1
    technical_schema_exact = bool(configurations) and all(
        isinstance(item.get("technical_coverage_gates"), Mapping)
        and set(dict(item.get("technical_coverage_gates") or {}))
        == set(REQUIRED_TECHNICAL_COVERAGE_GATES)
        for item in configurations
    )
    checks = {
        "benchmark_completed": worker_benchmark.get("benchmark_completed") is True,
        "configuration_rows_well_formed": isinstance(raw_configurations, list)
        and len(configurations) == len(raw_configurations),
        "worker_counts_unique": len(counts) == len(set(counts)),
        "worker_counts_match_resource_benchmark": sorted(counts)
        == sorted(expected_counts),
        "technical_gate_schema_exact": technical_schema_exact,
        "configuration_evidence_bound": canonical_json(stored_evidence)
        == canonical_json(recomputed_evidence),
        "all_configuration_evidence_honest": worker_benchmark.get(
            "all_configuration_evidence_complete"
        )
        is recomputed_all_evidence,
        "classification_bound": canonical_json(
            worker_benchmark.get("configuration_decisions") or {}
        )
        == canonical_json(decisions),
        "one_worker_reference_exact_and_passed": worker_benchmark.get(
            "reference_worker_count"
        )
        == 1
        and worker_benchmark.get("reference_configuration_count") == 1
        and worker_benchmark.get("reference_configuration_passed") is True
        and classification.get("reference_configuration_passed") is True,
        "reference_digest_bound": worker_benchmark.get(
            "reference_scientific_digest"
        )
        == classification.get("reference_scientific_digest")
        and len(reference_digest) == 64,
        "selection_candidates_bound": worker_benchmark.get(
            "selection_candidate_worker_counts"
        )
        == classification.get("selection_candidate_worker_counts"),
        "excluded_multi_workers_disclosed": canonical_json(
            worker_benchmark.get("excluded_multi_worker_configurations") or []
        )
        == canonical_json(
            classification.get("excluded_multi_worker_configurations") or []
        ),
        "selected_worker_allowed": not isinstance(selected, bool)
        and selected in ALLOWED_WORKER_COUNTS,
        "selected_worker_eligible": selected_decision.get(
            "eligible_for_selection"
        )
        is True,
        "selected_digest_matches_reference": selected_decision.get(
            "digest_matches_one_worker_reference"
        )
        is True
        and worker_benchmark.get(
            "selected_digest_matches_one_worker_reference"
        )
        is True,
        "selection_candidates_identical": worker_benchmark.get(
            "all_selection_candidates_identical_to_reference"
        )
        is True,
        "all_tested_digest_equality_honest": worker_benchmark.get(
            "all_tested_payloads_equal_to_reference"
        )
        is all_tested_equal
        and worker_benchmark.get("deterministic_payloads_equal")
        is all_tested_equal,
        "fallback_disclosure_honest": worker_benchmark.get(
            "fallback_to_one_worker"
        )
        is fallback_expected
        and (not fallback_expected or bool(worker_benchmark.get("fallback_reasons"))),
        "multi_worker_instability_not_hidden": worker_benchmark.get(
            "multi_worker_instability_is_not_a_start_blocker"
        )
        is True,
        "single_sqlite_writer": worker_benchmark.get("sqlite_writer_count") == 1,
        "selection_did_not_use_research_outcomes": worker_benchmark.get(
            "selection_used_outcomes"
        )
        is False
        and worker_benchmark.get("benchmark_used_for_research_selection") is False,
        "exclusive_benchmark_process_lock_held": worker_benchmark.get(
            "exclusive_benchmark_process_lock_held"
        )
        is True,
        "global_research_lock_held": worker_benchmark.get(
            "global_research_lock_held"
        )
        is True,
        "protected_runtime_checked_before_every_configuration": isinstance(
            raw_runtime_checks, list
        )
        and len(runtime_checks) == len(raw_runtime_checks)
        and runtime_check_counts_well_formed
        and sorted(int(item) for item in runtime_check_counts)
        == sorted(expected_counts)
        and all(
            item.get("status") == "PASS" and item.get("reason") == "CLEAR"
            for item in runtime_checks
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise MultiAssetDevelopmentV6ContractError(
            "Benchmark-Worker-Auswahl ist nicht referenztreu/fail-closed: "
            f"{failed}"
        )
    return {
        "selected_worker_count": selected,
        "reference_scientific_digest": reference_digest,
        "reference_configuration_passed": True,
        "configuration_decisions": decisions,
        "selection_candidate_worker_counts": list(
            classification.get("selection_candidate_worker_counts") or []
        ),
        "excluded_multi_worker_configurations": list(
            classification.get("excluded_multi_worker_configurations") or []
        ),
        "fallback_to_one_worker": fallback_expected,
        "fallback_reasons": list(worker_benchmark.get("fallback_reasons") or []),
        "all_tested_payloads_equal_to_reference": all_tested_equal,
    }


def _aware_artifact_timestamp(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MultiAssetDevelopmentV6ContractError(
            f"Ungültiger Zeitstempel für {label}."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MultiAssetDevelopmentV6ContractError(
            f"Zeitstempel für {label} muss eine Zeitzone enthalten."
        )
    return parsed


def _runtime_sources(
    *,
    config: Mapping[str, object],
    project_root: Path,
    parent_artifact_path: Path | None,
    input_precheck_path: Path | None,
    worker_benchmark_path: Path | None,
    descriptive_plan_path: Path | None,
) -> dict[str, object]:
    parent_artifact, parent_manifest = _load_parent(
        config=config,
        project_root=project_root,
        parent_artifact_path=parent_artifact_path,
    )
    input_precheck, input_path = _load_required_runtime_artifact(
        name="input_precheck",
        config=config,
        project_root=project_root,
        override_path=input_precheck_path,
    )
    worker_benchmark, benchmark_path = _load_required_runtime_artifact(
        name="worker_benchmark",
        config=config,
        project_root=project_root,
        override_path=worker_benchmark_path,
    )
    descriptive_plan, plan_path = _load_required_runtime_artifact(
        name="descriptive_plan",
        config=config,
        project_root=project_root,
        override_path=descriptive_plan_path,
    )

    inputs = _validated_input_contract(input_precheck)

    benchmark_selection = _validated_worker_benchmark_selection(worker_benchmark)
    raw_worker_input_precheck = worker_benchmark.get(
        "worker_input_precheck_artifact"
    )
    worker_input_precheck = (
        dict(raw_worker_input_precheck)
        if isinstance(raw_worker_input_precheck, Mapping)
        else {}
    )
    plan_created_at = str(descriptive_plan.get("created_at") or "")
    benchmark_created_at = str(worker_benchmark.get("created_at") or "")
    plan_time = _aware_artifact_timestamp(
        plan_created_at, label="descriptive_plan.created_at"
    )
    benchmark_time = _aware_artifact_timestamp(
        benchmark_created_at, label="worker_benchmark.created_at"
    )
    parent_contract_fingerprint = dict(config["parent_reprocessing"])[
        "contract_fingerprint"
    ]
    benchmark_lineage_checks = {
        "input_precheck_fingerprint": worker_benchmark.get(
            "input_precheck_fingerprint"
        )
        == input_precheck.get("artifact_fingerprint"),
        "worker_input_precheck_fingerprint": worker_input_precheck.get(
            "artifact_fingerprint"
        )
        == input_precheck.get("artifact_fingerprint"),
        "worker_input_precheck_path": worker_input_precheck.get("path")
        == dict(dict(config["required_runtime_artifacts"])["input_precheck"])[
            "path"
        ],
        "combined_input_fingerprint": worker_benchmark.get(
            "combined_input_fingerprint"
        )
        == inputs["combined_input_fingerprint"],
        "scientific_parent_contract_fingerprint": worker_benchmark.get(
            "scientific_parent_contract_fingerprint"
        )
        == parent_contract_fingerprint,
        "descriptive_plan_artifact_fingerprint": worker_benchmark.get(
            "descriptive_plan_artifact_fingerprint"
        )
        == descriptive_plan.get("artifact_fingerprint"),
        "descriptive_plan_created_at": worker_benchmark.get(
            "descriptive_plan_created_at"
        )
        == plan_created_at,
        "descriptive_plan_frozen_before_benchmark": plan_time <= benchmark_time,
    }
    failed_benchmark_lineage = [
        name for name, passed in benchmark_lineage_checks.items() if not passed
    ]
    if failed_benchmark_lineage:
        raise MultiAssetDevelopmentV6ContractError(
            "Benchmark-Provenienz stimmt nicht mit Parent/Input überein: "
            f"{failed_benchmark_lineage}"
        )
    if descriptive_plan.get("combined_input_fingerprint") != inputs[
        "combined_input_fingerprint"
    ]:
        raise MultiAssetDevelopmentV6ContractError(
            "Auswertungsplan ist nicht an den geprüften v6-Input gebunden."
        )
    if (
        descriptive_plan.get("inferential_claims_allowed") is not False
        or descriptive_plan.get("selection_or_optimization_allowed") is not False
    ):
        raise MultiAssetDevelopmentV6ContractError(
            "Auswertungsplan öffnet nicht freigegebene Inferenz/Optimierung."
        )

    return {
        "parent_artifact": parent_artifact,
        "parent_manifest": parent_manifest,
        "input_precheck": input_precheck,
        "input_precheck_path": input_path,
        "worker_benchmark": worker_benchmark,
        "worker_benchmark_selection": benchmark_selection,
        "worker_benchmark_path": benchmark_path,
        "descriptive_plan": descriptive_plan,
        "descriptive_plan_path": plan_path,
    }


def _validated_input_contract(
    input_precheck: Mapping[str, object],
) -> dict[str, object]:
    inputs = dict(input_precheck.get("contract_inputs") or {})
    missing_inputs = [key for key in _REQUIRED_INPUT_FINGERPRINTS if key not in inputs]
    if missing_inputs:
        raise MultiAssetDevelopmentV6ContractError(
            f"Input-Precheck liefert nicht alle Contract-Fingerprints: {missing_inputs}"
        )
    for key in _REQUIRED_INPUT_FINGERPRINTS:
        _require_hash(inputs[key], label=f"input_precheck.contract_inputs.{key}")
    return inputs


def _reprocessing_parent_reference(
    config: Mapping[str, object],
) -> dict[str, object]:
    parent_spec = dict(config["parent_reprocessing"])
    return {
        "contract_version": parent_spec["contract_version"],
        "contract_fingerprint": parent_spec["contract_fingerprint"],
        "artifact_version": parent_spec["artifact_version"],
        "artifact_fingerprint": parent_spec["artifact_fingerprint"],
        "artifact_sha256": parent_spec["artifact_sha256"],
        "run_id": parent_spec["run_id"],
        "run_manifest_version": parent_spec["run_manifest_version"],
        "run_manifest_fingerprint": parent_spec["run_manifest_fingerprint"],
        "run_manifest_sha256": parent_spec["run_manifest_sha256"],
        "immutable": True,
        "reprocessing_parent_only": True,
    }


def _apply_input_references(
    references: Mapping[str, object],
    *,
    inputs: Mapping[str, object],
    input_precheck_fingerprint: str,
) -> dict[str, object]:
    result = copy.deepcopy(dict(references))
    result.update(
        {
            "dataset_fingerprint": inputs["combined_input_fingerprint"],
            "dataset_manifest_sha256": inputs["source_dataset_manifest_sha256"],
            "development_code_fingerprint": inputs["implementation_fingerprint"],
            "fx_dataset_fingerprint": inputs["fx_projection_fingerprint"],
            "identity_registry_fingerprint": inputs["identity_registry_fingerprint"],
            "combined_input_fingerprint": inputs["combined_input_fingerprint"],
            "equity_etf_projection_fingerprint": inputs[
                "equity_etf_projection_fingerprint"
            ],
            "crypto_projection_fingerprint": inputs["crypto_projection_fingerprint"],
            "fx_projection_fingerprint": inputs["fx_projection_fingerprint"],
            "equity_etf_store_sha256": inputs["equity_etf_store_sha256"],
            "crypto_store_sha256": inputs["crypto_store_sha256"],
            "fx_store_sha256": inputs["fx_store_sha256"],
            "source_dataset_manifest_sha256": inputs[
                "source_dataset_manifest_sha256"
            ],
            "identity_store_sha256": inputs["identity_store_sha256"],
            "gap_policy_fingerprint": inputs["gap_policy_fingerprint"],
            "input_precheck_artifact_fingerprint": input_precheck_fingerprint,
        }
    )
    return result


def build_development_v6_benchmark_contract(
    config_path: Path = DEFAULT_V6_CONFIG_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
    parent_artifact_path: Path | None = None,
    input_precheck_path: Path | None = None,
) -> dict[str, object]:
    """Build a non-runnable v6 compute contract for the pre-freeze benchmark.

    This bootstrap contract deliberately has no stores, run paths, benchmark
    selection or descriptive plan.  It exists only to make benchmark payloads
    use the final v6 contract version while retaining the byte-identical v5
    research semantics and exact PASS input fingerprints.
    """

    config = _load_config(Path(config_path))
    parent_artifact, _parent_manifest = _load_parent(
        config=config,
        project_root=Path(project_root),
        parent_artifact_path=parent_artifact_path,
    )
    input_precheck, _ = _load_required_runtime_artifact(
        name="input_precheck",
        config=config,
        project_root=Path(project_root),
        override_path=input_precheck_path,
    )
    inputs = _validated_input_contract(input_precheck)
    parent = copy.deepcopy(dict(parent_artifact["contract"]))
    parent.pop("contract_fingerprint", None)
    benchmark_contract = copy.deepcopy(parent)
    benchmark_contract["contract_version"] = DEVELOPMENT_V6_CONTRACT_VERSION
    benchmark_contract["contract_state"] = "BENCHMARK_PRE_FREEZE"
    benchmark_contract["parent_contract_fingerprint"] = dict(
        config["parent_reprocessing"]
    )["contract_fingerprint"]
    benchmark_contract["reprocessing_parent"] = _reprocessing_parent_reference(config)
    benchmark_contract["reference_fingerprints"] = _apply_input_references(
        dict(benchmark_contract.get("reference_fingerprints") or {}),
        inputs=inputs,
        input_precheck_fingerprint=str(input_precheck["artifact_fingerprint"]),
    )
    benchmark_contract.pop("store_contract", None)
    parent_execution = dict(benchmark_contract.get("development_execution") or {})
    retained_execution_keys = (
        "universe_mode",
        "work_unit_partition",
        "development_start",
        "development_end",
        "minimum_history_observations",
        "maximum_attempts_per_work_unit",
        "forward_only_time_windows_apply_to_development",
        "active_production_locks_apply_to_development",
        "production_protection_config",
        "validation_access_allowed",
        "holdout_access_allowed",
        "external_access_allowed",
        "true_forward_access_allowed",
        "paper_output_allowed",
        "shadow_output_allowed",
        "broker_output_allowed",
        "automatic_orders_allowed",
        "automatic_strategy_optimization_allowed",
    )
    benchmark_execution = {
        key: copy.deepcopy(parent_execution[key])
        for key in retained_execution_keys
        if key in parent_execution
    }
    benchmark_execution.update(
        {
            "research_epoch": "multi-asset-development-v6-benchmark-pre-freeze",
            "execution_authorization": "BENCHMARK_ONLY",
            "benchmark_pre_freeze": True,
            "full_development_run_allowed": False,
            "sqlite_writer_count": 1,
            "input_precheck_artifact": dict(
                dict(config["required_runtime_artifacts"])["input_precheck"]
            )["path"],
            "input_precheck_version": dict(
                dict(config["required_runtime_artifacts"])["input_precheck"]
            )["version"],
        }
    )
    benchmark_contract["development_execution"] = benchmark_execution
    benchmark_contract["contract_fingerprint"] = fingerprint(benchmark_contract)

    comparable_parent = dict(parent_artifact["contract"])
    for root in SEMANTIC_INVARIANT_ROOTS:
        if canonical_json(comparable_parent.get(root)) != canonical_json(
            benchmark_contract.get(root)
        ):
            raise MultiAssetDevelopmentV6ContractError(
                f"Benchmark-Contract verändert Research-Semantik: {root}"
            )
    if (
        "store_contract" in benchmark_contract
        or benchmark_execution["full_development_run_allowed"] is not False
        or benchmark_contract["contract_state"] != "BENCHMARK_PRE_FREEZE"
        or any(value is not False for value in benchmark_contract["lifecycle"].values())
    ):
        raise MultiAssetDevelopmentV6ContractError(
            "Benchmark-Contract ist nicht strikt non-runnable."
        )
    return benchmark_contract


def _derive_contract(
    *, config: Mapping[str, object], sources: Mapping[str, object]
) -> dict[str, object]:
    parent_artifact = dict(sources["parent_artifact"])
    parent_manifest = dict(sources["parent_manifest"])
    input_precheck = dict(sources["input_precheck"])
    benchmark = dict(sources["worker_benchmark"])
    benchmark_selection = dict(sources["worker_benchmark_selection"])
    plan = dict(sources["descriptive_plan"])
    parent = copy.deepcopy(dict(parent_artifact["contract"]))
    parent.pop("contract_fingerprint", None)
    derived = copy.deepcopy(parent)
    derived["contract_version"] = DEVELOPMENT_V6_CONTRACT_VERSION

    derived["reprocessing_parent"] = _reprocessing_parent_reference(config)

    inputs = dict(input_precheck["contract_inputs"])
    references = _apply_input_references(
        dict(derived.get("reference_fingerprints") or {}),
        inputs=inputs,
        input_precheck_fingerprint=str(input_precheck["artifact_fingerprint"]),
    )
    references.update(
        {
            "worker_benchmark_artifact_fingerprint": benchmark[
                "artifact_fingerprint"
            ],
            "descriptive_plan_artifact_fingerprint": plan[
                "artifact_fingerprint"
            ],
        }
    )
    derived["reference_fingerprints"] = references

    runtime = dict(config["runtime"])
    stores_config = dict(runtime["stores"])
    stores = copy.deepcopy(dict(derived.get("store_contract") or {}))
    stores.update(stores_config)
    stores["work_unit_completion_receipt_required"] = True
    stores["incomplete_write_reconciliation_required"] = True
    derived["store_contract"] = stores

    execution_config = dict(runtime["execution"])
    required_specs = dict(config["required_runtime_artifacts"])
    execution = copy.deepcopy(dict(derived.get("development_execution") or {}))
    execution.update(
        {
            "research_epoch": runtime["research_epoch"],
            "worker_count": benchmark["selected_worker_count"],
            "sqlite_writer_count": 1,
            "process_lock": execution_config["process_lock"],
            "chain_state": execution_config["chain_state"],
            "run_manifest": execution_config["run_manifest"],
            "contract_artifact": execution_config["contract_artifact"],
            "contract_diff_artifact": execution_config["contract_diff_artifact"],
            "readiness_artifact": execution_config["start_gate_artifact"],
            "input_precheck_artifact": dict(required_specs["input_precheck"])["path"],
            "worker_benchmark_artifact": dict(required_specs["worker_benchmark"])[
                "path"
            ],
            "descriptive_plan_artifact": dict(required_specs["descriptive_plan"])[
                "path"
            ],
            "final_audit_artifact": execution_config["final_audit_artifact"],
            "descriptive_report_artifact": execution_config[
                "descriptive_report_artifact"
            ],
            "completion_summary_artifact": execution_config[
                "completion_summary_artifact"
            ],
            "log_path": execution_config["log_path"],
            "runner_script": execution_config["runner_script"],
            "scheduler_wrapper": execution_config["scheduler_wrapper"],
            "scheduler_task_name": execution_config["scheduler_task_name"],
            "development_not_before": runtime["development_not_before"],
            "full_development_run_allowed": True,
            "lifecycle_chain": list(LIFECYCLE_CHAIN),
            "chain_transition_requires_prior_pass": True,
            "final_audit_required_before_report": True,
            "stop_after_summary": True,
            "terminal_noop_after_stop": True,
        }
    )
    derived["development_execution"] = execution

    derived["technical_reprocessing_contract"] = {
        "authorized_categories": sorted(ALLOWED_REPAIR_CATEGORIES),
        "data_projection": {
            "input_precheck_version": input_precheck["version"],
            "input_precheck_artifact_fingerprint": input_precheck[
                "artifact_fingerprint"
            ],
            "combined_input_fingerprint": inputs["combined_input_fingerprint"],
            "equity_etf_projection_fingerprint": inputs[
                "equity_etf_projection_fingerprint"
            ],
            "crypto_projection_fingerprint": inputs["crypto_projection_fingerprint"],
            "fx_projection_fingerprint": inputs["fx_projection_fingerprint"],
            "equity_etf_store_sha256": inputs["equity_etf_store_sha256"],
            "crypto_store_sha256": inputs["crypto_store_sha256"],
            "fx_store_sha256": inputs["fx_store_sha256"],
            "source_dataset_manifest_sha256": inputs[
                "source_dataset_manifest_sha256"
            ],
            "identity_store_sha256": inputs["identity_store_sha256"],
            "identity_registry_fingerprint": inputs["identity_registry_fingerprint"],
            "no_unversioned_source_substitution": True,
        },
        "missingness_validity": {
            "gap_policy_fingerprint": inputs["gap_policy_fingerprint"],
            "gaps_remain_visible": True,
            "clipping_imputation_interpolation_allowed": False,
            "recursive_influence_must_be_explicit": True,
            "non_positive_structural_r_has_substitute_value": False,
            "r_independent_metrics_require_their_own_validity": True,
        },
        "terminal_retry": {
            "no_data_is_terminal_skip": True,
            "deterministic_data_or_contract_error_retryable": False,
            "maximum_transient_attempts_per_work_unit": execution[
                "maximum_attempts_per_work_unit"
            ],
            "completion_timestamp_immutable": True,
            "partial_cross_store_write_reconciled_idempotently": True,
        },
        "worker_runtime": {
            "benchmark_version": benchmark["version"],
            "benchmark_artifact_fingerprint": benchmark["artifact_fingerprint"],
            "selected_worker_count": benchmark["selected_worker_count"],
            "sqlite_writer_count": benchmark["sqlite_writer_count"],
            "deterministic_payloads_equal": benchmark[
                "deterministic_payloads_equal"
            ],
            "one_worker_reference_passed": benchmark_selection[
                "reference_configuration_passed"
            ],
            "one_worker_reference_scientific_digest": benchmark_selection[
                "reference_scientific_digest"
            ],
            "selected_digest_matches_one_worker_reference": benchmark[
                "selected_digest_matches_one_worker_reference"
            ],
            "selection_candidate_worker_counts": benchmark_selection[
                "selection_candidate_worker_counts"
            ],
            "excluded_multi_worker_configurations": benchmark_selection[
                "excluded_multi_worker_configurations"
            ],
            "fallback_to_one_worker": benchmark_selection[
                "fallback_to_one_worker"
            ],
            "fallback_reasons": benchmark_selection["fallback_reasons"],
            "all_tested_payloads_equal_to_reference": benchmark_selection[
                "all_tested_payloads_equal_to_reference"
            ],
            "multi_worker_instability_is_not_a_start_blocker": True,
        },
        "output_provenance": {
            "implementation_fingerprint": inputs["implementation_fingerprint"],
            "descriptive_plan_version": plan["version"],
            "descriptive_plan_artifact_fingerprint": plan["artifact_fingerprint"],
            "v5_parent_run_id": parent_manifest["run_id"],
            "new_v6_stores_only": True,
            "lifecycle_chain": list(LIFECYCLE_CHAIN),
            "validation_holdout_external_forward_paper_shadow_broker_closed": True,
        },
    }
    derived["contract_fingerprint"] = fingerprint(derived)
    return derived


def _recursive_diff(
    parent: object, development: object, path: str = ""
) -> list[dict[str, object]]:
    if isinstance(parent, Mapping) and isinstance(development, Mapping):
        rows: list[dict[str, object]] = []
        for key in sorted(set(parent) | set(development)):
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


def _authorization_rules(config: Mapping[str, object]) -> list[dict[str, str]]:
    rules = [
        {
            "prefix": str(dict(raw)["prefix"]),
            "category": str(dict(raw)["category"]),
            "repair_finding": str(dict(raw)["repair_finding"]),
        }
        for raw in config["authorized_changes"]
    ]
    return sorted(rules, key=lambda item: len(item["prefix"]), reverse=True)


def build_development_v6_contract_diff(
    *,
    parent: Mapping[str, object],
    development: Mapping[str, object],
    config: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return the complete v5→v6 diff with fail-closed classifications."""

    validated_config = _validate_config(config) if config is not None else _load_config()
    comparable_parent = copy.deepcopy(dict(parent))
    comparable_parent.pop("contract_fingerprint", None)
    comparable_development = copy.deepcopy(dict(development))
    comparable_development.pop("contract_fingerprint", None)
    differences = _recursive_diff(comparable_parent, comparable_development)
    rules = _authorization_rules(validated_config)
    classified: list[dict[str, object]] = []
    unauthorized: list[dict[str, object]] = []
    for row in differences:
        path = str(row["path"])
        rule = next(
            (item for item in rules if _path_matches_prefix(path, item["prefix"])),
            None,
        )
        if rule is None:
            item = {
                **row,
                "authorized": False,
                "category": None,
                "repair_finding": None,
                "classification": "UNAUTHORIZED_RESEARCH_SEMANTICS",
            }
            unauthorized.append(item)
        else:
            item = {
                **row,
                "authorized": True,
                "category": rule["category"],
                "repair_finding": rule["repair_finding"],
                "classification": "AUTHORIZED_TECHNICAL_CHANGE",
            }
        classified.append(item)

    invariants: list[dict[str, object]] = []
    for root in SEMANTIC_INVARIANT_ROOTS:
        parent_value = comparable_parent.get(root)
        development_value = comparable_development.get(root)
        invariants.append(
            {
                "path": root,
                "unchanged": canonical_json(parent_value)
                == canonical_json(development_value),
                "parent_fingerprint": fingerprint(parent_value),
                "development_fingerprint": fingerprint(development_value),
            }
        )
    invariant_failures = [item for item in invariants if item["unchanged"] is not True]
    payload: dict[str, object] = {
        "version": DEVELOPMENT_V6_CONTRACT_DIFF_VERSION,
        "parent_version": parent.get("contract_version"),
        "development_version": development.get("contract_version"),
        "parent_fingerprint": parent.get("contract_fingerprint"),
        "development_fingerprint": development.get("contract_fingerprint"),
        "authorized_categories": sorted(ALLOWED_REPAIR_CATEGORIES),
        "differences": classified,
        "difference_count": len(classified),
        "semantic_invariants": invariants,
        "semantic_invariant_failure_count": len(invariant_failures),
        "unauthorized_research_semantics_count": len(unauthorized),
        "research_semantics_diff_count": len(unauthorized),
        "unauthorized_differences": unauthorized,
        "status": (
            "PASS" if not unauthorized and not invariant_failures else "FAIL"
        ),
    }
    payload["diff_fingerprint"] = fingerprint(payload)
    return payload


def _validate_development_v6_contract(
    *,
    contract: Mapping[str, object],
    parent: Mapping[str, object],
    config: Mapping[str, object],
    sources: Mapping[str, object],
) -> None:
    if contract.get("contract_version") != DEVELOPMENT_V6_CONTRACT_VERSION:
        raise MultiAssetDevelopmentV6ContractError("Unerwartete v6-Contract-Version.")
    _verify_contract_fingerprint(contract, label="Development-v6-Contract")
    diff = build_development_v6_contract_diff(
        parent=parent, development=contract, config=config
    )
    if diff["status"] != "PASS":
        raise MultiAssetDevelopmentV6ContractError(
            "Development-v6 verändert nicht autorisierte Research-Semantik."
        )
    candidate = dict(contract.get("candidate_generation") or {})
    pilot = dict(contract.get("pilot_contract") or {})
    stores = dict(contract.get("store_contract") or {})
    execution = dict(contract.get("development_execution") or {})
    lifecycle = dict(contract.get("lifecycle") or {})
    runtime = dict(config["runtime"])
    expected_stores = dict(runtime["stores"])
    expected_execution = dict(runtime["execution"])
    benchmark = dict(sources["worker_benchmark"])
    checks = {
        "development_role_unchanged": contract.get("research_role") == "development",
        "full_universe_unchanged": candidate.get("mode")
        == "full_eligibility_universe",
        "full_scan_inherited": candidate.get("full_development_scan_allowed") is True,
        "large_scan_inherited": pilot.get("large_scan_allowed") is True,
        "full_run_explicitly_allowed": execution.get("full_development_run_allowed")
        is True,
        "new_feature_store": stores.get("feature_store")
        == expected_stores["feature_store"],
        "new_outcome_store": stores.get("outcome_store")
        == expected_stores["outcome_store"],
        "new_control_store": stores.get("control_store")
        == expected_stores["control_store"],
        "serial_writer": stores.get("serial_sqlite_writes_main_process_only")
        is True
        and execution.get("sqlite_writer_count") == 1,
        "append_only": stores.get("append_only") is True,
        "resume_without_duplicates": stores.get("resume_must_not_duplicate") is True,
        "cross_store_completion_proof": stores.get(
            "work_unit_completion_receipt_required"
        )
        is True,
        "worker_from_benchmark": execution.get("worker_count")
        == benchmark.get("selected_worker_count"),
        "development_period_unchanged": execution.get("development_start")
        == dict(parent.get("development_execution") or {}).get("development_start")
        and execution.get("development_end")
        == dict(parent.get("development_execution") or {}).get("development_end"),
        "chain_closed": tuple(execution.get("lifecycle_chain") or ())
        == LIFECYCLE_CHAIN,
        "audit_gates_report": execution.get("final_audit_required_before_report")
        is True,
        "stop_is_terminal": execution.get("stop_after_summary") is True
        and execution.get("terminal_noop_after_stop") is True,
        "validation_closed": execution.get("validation_access_allowed") is False,
        "holdout_closed": execution.get("holdout_access_allowed") is False,
        "external_closed": execution.get("external_access_allowed") is False,
        "forward_closed": execution.get("true_forward_access_allowed") is False,
        "paper_closed": execution.get("paper_output_allowed") is False,
        "shadow_closed": execution.get("shadow_output_allowed") is False,
        "broker_closed": execution.get("broker_output_allowed") is False,
        "orders_closed": execution.get("automatic_orders_allowed") is False,
        "strategy_optimization_closed": execution.get(
            "automatic_strategy_optimization_allowed"
        )
        is False,
        "lifecycle_closed": bool(lifecycle)
        and all(value is False for value in lifecycle.values()),
        "unique_scheduler": execution.get("scheduler_task_name")
        == expected_execution["scheduler_task_name"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise MultiAssetDevelopmentV6ContractError(
            f"Development-v6-Vertrag unvollständig: {failed}"
        )


def load_development_v6_contract(
    config_path: Path = DEFAULT_V6_CONFIG_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
    parent_artifact_path: Path | None = None,
    input_precheck_path: Path | None = None,
    worker_benchmark_path: Path | None = None,
    descriptive_plan_path: Path | None = None,
) -> dict[str, object]:
    """Load v6 only after all immutable parent and runtime gates validate."""

    config = _load_config(Path(config_path))
    sources = _runtime_sources(
        config=config,
        project_root=Path(project_root),
        parent_artifact_path=parent_artifact_path,
        input_precheck_path=input_precheck_path,
        worker_benchmark_path=worker_benchmark_path,
        descriptive_plan_path=descriptive_plan_path,
    )
    parent = dict(dict(sources["parent_artifact"])["contract"])
    contract = _derive_contract(config=config, sources=sources)
    _validate_development_v6_contract(
        contract=contract,
        parent=parent,
        config=config,
        sources=sources,
    )
    return contract


def _validate_frozen_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MultiAssetDevelopmentV6ContractError(
            "frozen_at muss ein ISO-8601-Zeitpunkt sein."
        ) from exc
    if parsed.tzinfo is None:
        raise MultiAssetDevelopmentV6ContractError(
            "frozen_at muss eine Zeitzone enthalten."
        )


def build_development_v6_contract_artifact(
    *,
    git_branch: str,
    git_commit: str,
    frozen_at: str,
    config_path: Path = DEFAULT_V6_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
    parent_artifact_path: Path | None = None,
    input_precheck_path: Path | None = None,
    worker_benchmark_path: Path | None = None,
    descriptive_plan_path: Path | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build (but do not persist) the freeze artifact and its complete diff."""

    if not str(git_branch).strip() or not str(git_commit).strip():
        raise MultiAssetDevelopmentV6ContractError("Git-Provenienz darf nicht leer sein.")
    _validate_frozen_at(frozen_at)
    config = _load_config(Path(config_path))
    sources = _runtime_sources(
        config=config,
        project_root=Path(project_root),
        parent_artifact_path=parent_artifact_path,
        input_precheck_path=input_precheck_path,
        worker_benchmark_path=worker_benchmark_path,
        descriptive_plan_path=descriptive_plan_path,
    )
    parent = dict(dict(sources["parent_artifact"])["contract"])
    contract = _derive_contract(config=config, sources=sources)
    _validate_development_v6_contract(
        contract=contract,
        parent=parent,
        config=config,
        sources=sources,
    )
    diff = build_development_v6_contract_diff(
        parent=parent, development=contract, config=config
    )
    if diff["status"] != "PASS":
        raise MultiAssetDevelopmentV6ContractError(
            "v6 kann mit einem fehlgeschlagenen Parent-Diff nicht eingefroren werden."
        )
    required_specs = dict(config["required_runtime_artifacts"])
    runtime_inputs = {}
    for name in ("input_precheck", "worker_benchmark", "descriptive_plan"):
        source = dict(sources[name])
        runtime_inputs[name] = {
            "path": dict(required_specs[name])["path"],
            "version": source["version"],
            "status": source["status"],
            "artifact_fingerprint": source["artifact_fingerprint"],
        }
    artifact: dict[str, object] = {
        "version": DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION,
        "frozen_at": frozen_at,
        "contract": contract,
        "contract_fingerprint": contract["contract_fingerprint"],
        "development_code_fingerprint": dict(
            contract["reference_fingerprints"]
        )["development_code_fingerprint"],
        "reprocessing_parent": copy.deepcopy(contract["reprocessing_parent"]),
        "runtime_input_artifacts": runtime_inputs,
        "parent_diff_fingerprint": diff["diff_fingerprint"],
        "unauthorized_research_semantics_count": 0,
        "research_semantics_diff_count": 0,
        "git": {"branch": git_branch, "commit": git_commit},
        "full_development_run_authorized": True,
        "development_run_started": False,
        "lifecycle_chain": list(LIFECYCLE_CHAIN),
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


def verify_development_v6_contract_artifact(
    artifact: Mapping[str, object],
) -> bool:
    """Return whether a previously built v6 artifact is self-consistent."""

    stored = str(artifact.get("artifact_fingerprint") or "")
    comparable = dict(artifact)
    comparable.pop("artifact_fingerprint", None)
    return bool(
        _HASH_PATTERN.fullmatch(stored)
        and artifact.get("version") == DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION
        and stored == fingerprint(comparable)
    )


__all__ = [
    "ALLOWED_REPAIR_CATEGORIES",
    "ALLOWED_WORKER_COUNTS",
    "DEFAULT_V6_CONFIG_PATH",
    "DEVELOPMENT_V6_CONTRACT_ARTIFACT_VERSION",
    "DEVELOPMENT_V6_CONTRACT_DIFF_VERSION",
    "DEVELOPMENT_V6_CONTRACT_VERSION",
    "LIFECYCLE_CHAIN",
    "MultiAssetDevelopmentV6ContractError",
    "SEMANTIC_INVARIANT_ROOTS",
    "build_development_v6_benchmark_contract",
    "build_development_v6_contract_artifact",
    "build_development_v6_contract_diff",
    "load_development_v6_contract",
    "verify_development_v6_contract_artifact",
]
