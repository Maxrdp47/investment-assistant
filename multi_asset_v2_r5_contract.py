from __future__ import annotations

"""Fail-closed validator for the outcome-blind Discovery-v2 R5 freeze."""

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT / "config" / "multi_asset_discovery_v2_r5_freeze.json"
SHA256 = re.compile(r"[0-9a-f]{64}")
ALLOWED_STATUSES = {
    "ACTIVE_PIT",
    "ACTIVE_PIT_LIMITED_SCOPE",
    "SHADOW",
    "UNAVAILABLE",
    "STRUCTURAL_NOT_APPLICABLE",
}
EXPECTED_FAMILIES = {
    "PRICE_RETURNS",
    "MOMENTUM_TREND_VOLATILITY",
    "CONFIRMED_STRUCTURE_CONTEXT",
    "RELATIVE_STRENGTH_GLOBAL_ACWI",
    "RELATIVE_STRENGTH_REGION_SECTOR",
    "MARKET_REGIME_GLOBAL_ACWI",
    "REPORTED_VOLUME_RELATIVE",
    "GAP_OVERNIGHT_INTRADAY_RAW",
    "SUPPORT_RESISTANCE_GEOMETRY",
    "FUNDAMENTALS_SEC",
    "COMPANY_EVENTS",
    "MACRO_RATES_EXPECTATIONS",
    "COT",
    "POLICY_GEOPOLITICS",
    "FX_SPECIFIC",
    "CRYPTO_BTC_RELATIVE",
    "CRYPTO_ONCHAIN_DOMINANCE",
    "HISTORICAL_ISSUER_DEPENDENCY",
    "HISTORICAL_UNIVERSE_MEMBERSHIP",
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = DEFAULT_CONTRACT) -> tuple[dict[str, Any], str]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_contract_structure(contract)
    return contract, fingerprint(contract)


def validate_contract_structure(contract: Mapping[str, Any]) -> None:
    if (
        contract.get("program_block") != "R5"
        or contract.get("freeze_status") != "FROZEN_NO_OUTCOMES_OPENED"
        or contract.get("market_scopes") != ["EQUITIES", "ETF", "CRYPTO"]
        or contract.get("analysis_resolution") != "COMPLETED_DAILY_BARS_ONLY"
    ):
        raise ValueError("R5 freeze identity or market scope changed")
    capabilities = contract.get("capabilities")
    if not isinstance(capabilities, list):
        raise ValueError("R5 capabilities must be a list")
    families = [str(item.get("family")) for item in capabilities if isinstance(item, Mapping)]
    if len(families) != len(set(families)) or set(families) != EXPECTED_FAMILIES:
        raise ValueError("R5 feature families are missing, duplicated, or changed")
    for item in capabilities:
        if not isinstance(item, Mapping) or item.get("status") not in ALLOWED_STATUSES:
            raise ValueError("R5 capability has an invalid status")
        if not item.get("scope") or not str(item.get("limit") or "").strip():
            raise ValueError("R5 capability scope/limit must be explicit")
    missing = contract.get("missingness_contract") or {}
    if (
        set(missing.get("states") or []) != {
            "AVAILABLE", "UNKNOWN", "UNAVAILABLE", "SHADOW", "PROVIDER_FAILURE",
            "STRUCTURAL_NOT_APPLICABLE",
        }
        or not missing.get("missing_never_becomes_false_or_zero")
        or not missing.get("no_imputation")
        or not missing.get("no_interpolation")
        or not missing.get("no_cross_segment_fill")
        or not missing.get("shadow_families_excluded_from_r6_features")
        or not missing.get("unavailable_families_excluded_from_r6_features")
    ):
        raise ValueError("R5 missingness guardrails changed")
    outcome = contract.get("outcome_contract") or {}
    if (
        outcome.get("checkpoints") != [20, 60, 120, 252]
        or not outcome.get("each_checkpoint_uses_its_own_fully_observable_population")
        or not outcome.get("longer_checkpoint_missing_does_not_censor_shorter_complete_checkpoint")
        or outcome.get("outcome_may_cross_stage_or_segment_boundary") is not False
        or not outcome.get("no_intrabar_order_invention")
    ):
        raise ValueError("R5 horizon/outcome contract changed")
    stages = contract.get("stage_contract") or {}
    if (
        stages.get("development") != ["2016-01-01", "2021-12-31"]
        or stages.get("development_is_already_seen") is not True
        or any(stages.get(key) for key in (
            "validation_opened", "holdout_opened", "external_opened", "forward_opened",
            "paper_opened", "shadow_execution_opened",
        ))
    ):
        raise ValueError("R5 stage sealing changed")
    cost = contract.get("cost_contract") or {}
    if (
        not cost.get("r6_is_descriptive_path_research_not_tradeable_strategy")
        or cost.get("net_return_profit_factor_or_strategy_expectancy_allowed") is not False
        or cost.get("numeric_cost_assumption_invented") is not False
    ):
        raise ValueError("R5 cost/non-strategy contract changed")
    gate = contract.get("review_quality_c_gate") or {}
    if (
        not gate.get("all_dimensions_must_pass_for_robust_candidate")
        or not gate.get("unknown_dependency_or_effective_n_may_not_be_replaced_by_raw_n")
        or gate.get("automatic_feature_combinations") is not False
        or gate.get("composite_opportunity_score") is not False
        or gate.get("parameter_grid_or_threshold_search") is not False
        or gate.get("ranking_by_profit") is not False
    ):
        raise ValueError("R5 canonical review gate weakened")
    execution = contract.get("r6_execution_contract") or {}
    if (
        execution.get("run_id") != "mad2-development-v2-20260922-v1"
        or execution.get("sqlite_writer_count") != 1
        or execution.get("worker_count") != 6
        or not execution.get("new_append_only_stores_required")
        or not execution.get("deterministic_replay_required")
        or not execution.get("pilot_and_integrity_gate_required_before_full_run")
        or execution.get("validation_holdout_external_forward_paper_shadow_broker_orders_opened") is not False
    ):
        raise ValueError("R5/R6 execution safety contract changed")
    for value in _all_fingerprint_values(contract):
        if SHA256.fullmatch(value) is None:
            raise ValueError("R5 contains a malformed declared SHA-256/fingerprint")


def _all_fingerprint_values(value: object, key: str = "") -> list[str]:
    result: list[str] = []
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            result.extend(_all_fingerprint_values(child, str(child_key)))
    elif isinstance(value, list):
        for child in value:
            result.extend(_all_fingerprint_values(child, key))
    elif isinstance(value, str) and ("fingerprint" in key or key.endswith("sha256")):
        result.append(value)
    return result


def _projection_fingerprint(path: Path, version: str) -> str:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError(f"R5 source failed quick_check: {path.name}")
        row = connection.execute(
            "SELECT dataset_fingerprint FROM projection_versions WHERE version=?", (version,)
        ).fetchone()
    if row is None:
        raise ValueError(f"R5 source version missing: {version}")
    return str(row[0])


def validate_freeze(
    path: Path = DEFAULT_CONTRACT,
    root: Path = ROOT,
    *,
    require_runtime_sources: bool = True,
) -> dict[str, Any]:
    contract, contract_fingerprint = load_contract(path)
    for filename, expected in contract["capability_reports"].items():
        target = root / filename
        if not target.is_file() or file_sha256(target) != expected:
            raise ValueError(f"R5 capability report provenance mismatch: {filename}")
    feature_paths = {
        "multi_asset_v2_r4b.json": root / "config" / "multi_asset_v2_r4b.json",
        "crypto_r4h_features.json": root / "config" / "crypto_r4h_features.json",
    }
    for filename, metadata in contract["feature_contracts"].items():
        target = feature_paths[filename]
        if file_sha256(target) != metadata["file_sha256"]:
            raise ValueError(f"R5 feature contract file changed: {filename}")
        payload = json.loads(target.read_text(encoding="utf-8"))
        if fingerprint(payload) != metadata["contract_fingerprint"]:
            raise ValueError(f"R5 feature contract fingerprint changed: {filename}")
    fixed_files = {"universe_manifest_sha256": root / "config" / "swing_universe_sources.json"}
    for key, target in fixed_files.items():
        if not target.is_file() or file_sha256(target) != contract["sources"][key]:
            raise ValueError(f"R5 source artifact changed: {key}")
    if file_sha256(root / "RESEARCH_POLICY.md") != contract["review_quality_c_gate"]["policy_file_sha256"]:
        raise ValueError("R5 canonical research policy changed")
    verified: dict[str, str] = {}
    if require_runtime_sources:
        input_precheck = (
            root / "runtime" / "research_exports"
            / "multi_asset_development_v6_input_precheck_2026-09-05-v1-r7.json"
        )
        if (
            not input_precheck.is_file()
            or file_sha256(input_precheck) != contract["sources"]["input_precheck_sha256"]
        ):
            raise ValueError("R5 source artifact changed: input_precheck_sha256")
        parent_files = {
            "v7_recovery_contract_sha256": root / "runtime" / "research_exports" / "multi_asset_development_v7_recovery_contract_2026-09-13-v2.json",
            "v6_scientific_contract_sha256": root / "runtime" / "research_exports" / "multi_asset_discovery_v1_development_contract_2026-09-05-v6-r3.json",
        }
        for key, target in parent_files.items():
            if not target.is_file() or file_sha256(target) != contract["parent_semantics"][key]:
                raise ValueError(f"R5 parent contract changed: {key}")
        source_paths = {
            "equity_etf": root / "runtime" / "equity_etf_historical_pit_2026-09-03-v1.sqlite3",
            "crypto": root / "runtime" / "crypto_historical_pit_2026-09-05-v1.sqlite3",
        }
        for source, target in source_paths.items():
            metadata = contract["sources"][source]
            actual = _projection_fingerprint(target, metadata["version"])
            if actual != metadata["dataset_fingerprint"]:
                raise ValueError(f"R5 dataset fingerprint changed: {source}")
            verified[source] = actual
    return {
        "status": (
            "PASS_R5_FREEZE_VALID"
            if require_runtime_sources
            else "PASS_R5_FREEZE_REPOSITORY_PROVENANCE_VALID_RUNTIME_NOT_CHECKED"
        ),
        "contract_fingerprint": contract_fingerprint,
        "verified_datasets": verified,
        "runtime_sources_checked": require_runtime_sources,
        "feature_family_count": len(contract["capabilities"]),
        "outcomes_opened": False,
        "validation_opened": False,
        "holdout_opened": False,
    }
