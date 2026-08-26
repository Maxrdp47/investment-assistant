from __future__ import annotations

"""Frozen Buyer Confirmation challenger evaluation on unseen historical stages.

Broad-v1, its frozen OHLCV dataset, and the authoritative Development report are
read-only inputs.  Freeze, stage openings, ground-up cases, completions, and
reviews are stored in a separate append-only SQLite database.
"""

import hashlib
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from swing_broad_research import (
    BROAD_RESEARCH_CANDIDATE_VERSION,
    BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
    BROAD_RESEARCH_FEATURE_VERSION,
    BROAD_RESEARCH_LABEL_VERSION,
    BROAD_RESEARCH_PATTERN_VERSION,
    BROAD_RESEARCH_SPLIT_VERSION,
    SWING_EXECUTION_COST_VERSION,
    broad_research_code_fingerprint,
    broad_research_feature_contract_fingerprint,
    build_asset_broad_research,
)
from swing_broad_research_audit import (
    MIN_EFFECTIVE_GROUP_N,
    MIN_GROUP_SHARE,
    MIN_RAW_GROUP_N,
    VALIDITY_PASS,
    VALIDITY_UNDERPOWERED,
    validity_gate,
)
from swing_buyer_confirmation_robustness import (
    BASELINE_ENTRY_POLICY,
    BUYER_RULE,
    CONSERVATIVE_EXTRA_SLIPPAGE_BPS_ONE_WAY,
    DECISION_C_RECOMMENDATION,
    EXIT_CONTRACT,
    MATCH_EFFECTIVE_ADEQUACY_FLOOR,
    MATCH_RAW_ADEQUACY_FLOOR,
    REGION_CLUSTER_MATCH_KEYS,
    SETUP_SCOPE,
    STOP_CONTRACT,
    STRICT_ASSET_CLUSTER_MATCH_KEYS,
    _choose_match,
    _geometry_assessment,
    _number,
    _record_from_sql,
    execution_simulation,
    matching_seed_sensitivity,
    outcome_blind_exact_match,
    summarize_rows,
    verify_report_fingerprint,
)


FREEZE_VERSION = "buyer-confirmation-challenger-freeze-2026.08.26-v1"
STORE_VERSION = "buyer-confirmation-unseen-evaluation-2026.08.26-v1"
CHALLENGER_ID = "buyer-confirmation-objective-pullback"
CHALLENGER_VERSION = "buyer-confirmation-objective-pullback-v1"
HYPOTHESIS_ID = "buyer_confirmation"
EXPECTED_BROAD_MANIFEST_FINGERPRINT = (
    "7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5"
)
EXPECTED_DEVELOPMENT_REPORT_FINGERPRINT = (
    "5400858a75aa4cb581e5af2552b0b78d7df3f7a10facdd2cb53a2baee4db1b74"
)
EXPECTED_DATASET_FINGERPRINT = (
    "e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed"
)
EXPECTED_FEATURE_FINGERPRINT = (
    "c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd"
)
EXPECTED_CODE_FINGERPRINT = (
    "77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946"
)
ALLOWED_STAGE_STATUSES = {
    "validation": {
        "VALIDATION_PASS",
        "VALIDATION_FAIL",
        "VALIDATION_UNDERPOWERED",
        "VALIDATION_INVALID",
    },
    "holdout": {
        "HOLDOUT_PASS",
        "HOLDOUT_FAIL",
        "HOLDOUT_UNDERPOWERED",
        "HOLDOUT_INVALID",
    },
}


class BuyerConfirmationValidationError(RuntimeError):
    pass


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    return value


def _canonical_json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(
        _clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        allow_nan=False,
        indent=indent,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_snapshot(path: Path, *, hash_file: bool) -> dict[str, object]:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    result: dict[str, object] = {
        "path": str(resolved),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if hash_file:
        result["sha256"] = _file_sha256(resolved)
    return result


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, timeout=60
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _connect(path: Path) -> sqlite3.Connection:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(destination, timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def initialize_validation_store(path: Path) -> None:
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS buyer_challenger_freezes (
                challenger_version TEXT PRIMARY KEY,
                freeze_json TEXT NOT NULL,
                freeze_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS buyer_integrity_receipts (
                challenger_version TEXT NOT NULL,
                gate_name TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                receipt_fingerprint TEXT NOT NULL,
                PRIMARY KEY (challenger_version, gate_name)
            );
            CREATE TABLE IF NOT EXISTS buyer_stage_openings (
                challenger_version TEXT NOT NULL,
                research_stage TEXT NOT NULL,
                opening_json TEXT NOT NULL,
                opening_fingerprint TEXT NOT NULL,
                PRIMARY KEY (challenger_version, research_stage)
            );
            CREATE TABLE IF NOT EXISTS buyer_stage_cases (
                case_id TEXT PRIMARY KEY,
                challenger_version TEXT NOT NULL,
                research_stage TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                comparison_group TEXT NOT NULL,
                case_json TEXT NOT NULL,
                case_fingerprint TEXT NOT NULL,
                UNIQUE (challenger_version, research_stage, candidate_id)
            );
            CREATE TABLE IF NOT EXISTS buyer_stage_completions (
                challenger_version TEXT NOT NULL,
                research_stage TEXT NOT NULL,
                symbol TEXT NOT NULL,
                completion_json TEXT NOT NULL,
                completion_fingerprint TEXT NOT NULL,
                PRIMARY KEY (challenger_version, research_stage, symbol)
            );
            CREATE TABLE IF NOT EXISTS buyer_stage_reviews (
                challenger_version TEXT NOT NULL,
                research_stage TEXT NOT NULL,
                decision TEXT NOT NULL,
                review_json TEXT NOT NULL,
                review_fingerprint TEXT NOT NULL,
                PRIMARY KEY (challenger_version, research_stage)
            );
            """
        )
        for table in (
            "buyer_challenger_freezes",
            "buyer_integrity_receipts",
            "buyer_stage_openings",
            "buyer_stage_cases",
            "buyer_stage_completions",
            "buyer_stage_reviews",
        ):
            connection.executescript(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_no_update
                BEFORE UPDATE ON {table}
                BEGIN SELECT RAISE(ABORT, 'append-only table'); END;
                CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                BEFORE DELETE ON {table}
                BEGIN SELECT RAISE(ABORT, 'append-only table'); END;
                """
            )


def _broad_reference(path: Path) -> dict[str, object]:
    with _read_only_connection(path) as connection:
        manifests = connection.execute(
            "SELECT manifest_json, manifest_fingerprint FROM broad_research_manifests"
        ).fetchall()
        hypothesis_key = f"{BROAD_RESEARCH_PATTERN_VERSION}|{HYPOTHESIS_ID}"
        hypothesis = connection.execute(
            "SELECT hypothesis_json, hypothesis_fingerprint "
            "FROM broad_research_hypotheses WHERE hypothesis_id=?",
            (hypothesis_key,),
        ).fetchone()
        mutable_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "broad_research_challengers",
                "broad_research_challenger_trades",
                "broad_research_challenger_rescan_completions",
                "broad_research_challenger_reviews",
            )
        }
    if len(manifests) != 1 or hypothesis is None:
        raise BuyerConfirmationValidationError(
            "Broad-v1 manifest or Buyer Confirmation hypothesis is missing."
        )
    manifest = json.loads(manifests[0]["manifest_json"])
    hypothesis_payload = json.loads(hypothesis["hypothesis_json"])
    if _fingerprint(manifest) != str(manifests[0]["manifest_fingerprint"]):
        raise BuyerConfirmationValidationError("Broad-v1 manifest fingerprint is invalid.")
    if _fingerprint(hypothesis_payload) != str(hypothesis["hypothesis_fingerprint"]):
        raise BuyerConfirmationValidationError("Broad-v1 hypothesis fingerprint is invalid.")
    expected = {
        "dataset_fingerprint": EXPECTED_DATASET_FINGERPRINT,
        "feature_contract_fingerprint": EXPECTED_FEATURE_FINGERPRINT,
        "code_fingerprint": EXPECTED_CODE_FINGERPRINT,
    }
    mismatches = {
        key: {"stored": manifest.get(key), "expected": value}
        for key, value in expected.items()
        if str(manifest.get(key) or "") != value
    }
    if mismatches or str(manifests[0]["manifest_fingerprint"]) != EXPECTED_BROAD_MANIFEST_FINGERPRINT:
        raise BuyerConfirmationValidationError(
            f"Broad-v1 immutable identity mismatch: {mismatches}"
        )
    if any(mutable_counts.values()):
        raise BuyerConfirmationValidationError(
            "Broad-v1 already contains challenger-stage writes; separate evaluation is required."
        )
    return {
        "manifest_fingerprint": str(manifests[0]["manifest_fingerprint"]),
        "hypothesis_key": hypothesis_key,
        "hypothesis_fingerprint": str(hypothesis["hypothesis_fingerprint"]),
        "stored_development_classification": hypothesis_payload.get("classification"),
        "separate_robustness_decision_required": True,
        "legacy_challenger_table_counts": mutable_counts,
        **expected,
    }


def build_challenger_freeze(
    *,
    development_report_path: Path,
    broad_path: Path,
    dataset_manifest_path: Path,
    expected_assets: int,
    frozen_at: str,
) -> dict[str, object]:
    report = json.loads(Path(development_report_path).read_text(encoding="utf-8"))
    if not verify_report_fingerprint(report):
        raise BuyerConfirmationValidationError("Development report fingerprint is invalid.")
    if str(report.get("report_fingerprint") or "") != EXPECTED_DEVELOPMENT_REPORT_FINGERPRINT:
        raise BuyerConfirmationValidationError("Unexpected authoritative Development report.")
    decision = dict(report.get("manual_decision") or {})
    draft = dict(report.get("challenger_specification_draft") or {})
    if (
        decision.get("decision") != DECISION_C_RECOMMENDATION
        or decision.get("failed_hard_criteria") != []
        or report.get("freeze_created") is not False
        or report.get("challenger_created") is not False
        or dict(report.get("data_access") or {}).get("validation_opened") is not False
        or dict(report.get("data_access") or {}).get("holdout_opened") is not False
    ):
        raise BuyerConfirmationValidationError("Development evidence is not eligible for freeze.")
    expected_draft = {
        "setup_scope": SETUP_SCOPE,
        "single_rule": BUYER_RULE,
        "entry_contract": BASELINE_ENTRY_POLICY,
        "stop_contract": STOP_CONTRACT,
        "exit_contract": EXIT_CONTRACT,
        "additional_filters": [],
    }
    if any(draft.get(key) != value for key, value in expected_draft.items()):
        raise BuyerConfirmationValidationError("Development challenger draft changed.")
    broad = _broad_reference(broad_path)
    manifest = json.loads(Path(dataset_manifest_path).read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "finalized"
        or str(manifest.get("dataset_fingerprint") or "") != EXPECTED_DATASET_FINGERPRINT
        or int(expected_assets) <= 0
    ):
        raise BuyerConfirmationValidationError("Frozen dataset is not finalized or mismatched.")
    if broad_research_code_fingerprint() != EXPECTED_CODE_FINGERPRINT:
        raise BuyerConfirmationValidationError("Current code does not reproduce Broad-v1.")
    if broad_research_feature_contract_fingerprint() != EXPECTED_FEATURE_FINGERPRINT:
        raise BuyerConfirmationValidationError("Current feature contract does not reproduce Broad-v1.")
    payload = {
        "freeze_version": FREEZE_VERSION,
        "challenger_id": CHALLENGER_ID,
        "challenger_version": CHALLENGER_VERSION,
        "name": "Buyer Confirmation for objective pullbacks",
        "hypothesis_id": HYPOTHESIS_ID,
        "research_reference": broad,
        "setup_scope": SETUP_SCOPE,
        "single_new_rule": {
            "name": "buyer_confirmation",
            "definition": BUYER_RULE,
            "point_in_time": "completed signal candle t only",
        },
        "additional_filters": [],
        "forbidden_rules": [
            "RSI", "EMA", "BOS", "Fibonacci", "bearish_candle_count", "volume",
            "volatility", "market_regime", "region", "USA_only", "confluence", "ML",
        ],
        "entry_contract": BASELINE_ENTRY_POLICY,
        "stop_contract": STOP_CONTRACT,
        "exit_contract": EXIT_CONTRACT,
        "cost_and_slippage_contract": {
            "version": SWING_EXECUTION_COST_VERSION,
            "baseline": "stored Broad-v1 one-way spread/slippage/fee contract",
            "conservative_execution": (
                f"baseline plus {CONSERVATIVE_EXTRA_SLIPPAGE_BPS_ONE_WAY:g} bps "
                "adverse slippage one-way at entry and exit"
            ),
            "same_bar_order": "gap_then_stop_before_target",
        },
        "identity": {
            "dataset_fingerprint": EXPECTED_DATASET_FINGERPRINT,
            "feature_contract_fingerprint": EXPECTED_FEATURE_FINGERPRINT,
            "code_fingerprint": EXPECTED_CODE_FINGERPRINT,
            "candidate_version": BROAD_RESEARCH_CANDIDATE_VERSION,
            "feature_version": BROAD_RESEARCH_FEATURE_VERSION,
            "label_version": BROAD_RESEARCH_LABEL_VERSION,
            "counterfactual_version": BROAD_RESEARCH_COUNTERFACTUAL_VERSION,
            "split_version": BROAD_RESEARCH_SPLIT_VERSION,
        },
        "development_source": {
            "path": str(Path(development_report_path).resolve()),
            "report_fingerprint": report["report_fingerprint"],
            "decision": decision["decision"],
            "development_only": True,
        },
        "frozen_at": str(frozen_at),
        "expected_assets_per_stage": int(expected_assets),
        "split_contract": {
            "validation": ["2013-01-01..2014-12-31", "2022-01-01..2023-12-31"],
            "holdout": ["2015-01-01..2015-12-31", "2024-01-01 onward"],
            "chronological_and_preexisting": True,
        },
        "predeclared_gates": {
            "minimum_raw_group_n": MIN_RAW_GROUP_N,
            "minimum_effective_group_n": MIN_EFFECTIVE_GROUP_N,
            "minimum_group_share": MIN_GROUP_SHARE,
            "matching_raw_adequacy_floor": MATCH_RAW_ADEQUACY_FLOOR,
            "matching_effective_adequacy_floor": MATCH_EFFECTIVE_ADEQUACY_FLOOR,
            "expectancy_positive": True,
            "profit_factor_above_one": True,
            "treatment_better_than_control": True,
            "positive_year_share_minimum": 0.60,
            "single_year_absolute_result_contribution_maximum": 0.50,
            "scope_concentration_allowance_over_case_share": 0.20,
            "scope_concentration_absolute_floor": 0.50,
            "conservative_execution_must_remain_positive": True,
            "baseline_execution_reconstruction_mismatch_maximum": 0,
            "all_expected_assets_must_complete": True,
        },
        "known_limitations": [
            "USA dominates the Development sample",
            "Europe is slightly negative in Development",
            "small regions can be underpowered",
            "historical universe is not fully survivorship-free",
            "C_RECOMMENDATION is Development evidence only",
            "no production approval",
        ],
        "source_snapshots": {
            "broad_v1": _source_snapshot(broad_path, hash_file=False),
            "dataset_manifest": _source_snapshot(dataset_manifest_path, hash_file=True),
            "development_report": _source_snapshot(development_report_path, hash_file=True),
        },
        "rules_mutable_after_freeze": False,
        "validation_opened": False,
        "holdout_opened": False,
        "production_eligible": False,
        "automatic_production_activation": False,
    }
    payload["freeze_fingerprint"] = _fingerprint(payload)
    return payload


def record_challenger_freeze(freeze: Mapping[str, object], path: Path) -> dict[str, object]:
    initialize_validation_store(path)
    payload = {key: value for key, value in dict(freeze).items() if key != "freeze_fingerprint"}
    fingerprint = _fingerprint(payload)
    if fingerprint != freeze.get("freeze_fingerprint"):
        raise BuyerConfirmationValidationError("Freeze fingerprint is invalid.")
    version = str(payload.get("challenger_version") or "")
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT freeze_fingerprint FROM buyer_challenger_freezes WHERE challenger_version=?",
            (version,),
        ).fetchone()
        if existing is not None and str(existing[0]) != fingerprint:
            raise BuyerConfirmationValidationError("Challenger version is already frozen differently.")
        if existing is None:
            connection.execute(
                "INSERT INTO buyer_challenger_freezes VALUES (?, ?, ?)",
                (version, _canonical_json(payload), fingerprint),
            )
    return {**payload, "freeze_fingerprint": fingerprint}


def load_challenger_freeze(path: Path, version: str = CHALLENGER_VERSION) -> dict[str, object]:
    initialize_validation_store(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT freeze_json, freeze_fingerprint FROM buyer_challenger_freezes "
            "WHERE challenger_version=?",
            (version,),
        ).fetchone()
    if row is None:
        raise BuyerConfirmationValidationError("Challenger has not been frozen.")
    payload = json.loads(row["freeze_json"])
    if _fingerprint(payload) != str(row["freeze_fingerprint"]):
        raise BuyerConfirmationValidationError("Stored freeze is damaged.")
    return {**payload, "freeze_fingerprint": str(row["freeze_fingerprint"])}


def pre_validation_integrity_gate(
    freeze: Mapping[str, object],
    *,
    broad_path: Path,
    dataset_manifest_path: Path,
    development_report_path: Path,
    store_path: Path,
    checked_at: str,
) -> dict[str, object]:
    expected_rule = {
        "name": "buyer_confirmation",
        "definition": BUYER_RULE,
        "point_in_time": "completed signal candle t only",
    }
    checks = {
        "freeze_fingerprint_valid": _fingerprint(
            {key: value for key, value in freeze.items() if key != "freeze_fingerprint"}
        ) == freeze.get("freeze_fingerprint"),
        "frozen_dataset_unchanged": _source_snapshot(
            dataset_manifest_path, hash_file=True
        ) == dict(freeze["source_snapshots"]["dataset_manifest"]),
        "broad_v1_unchanged": _source_snapshot(broad_path, hash_file=False)
        == dict(freeze["source_snapshots"]["broad_v1"]),
        "development_artifact_unchanged": _source_snapshot(
            development_report_path, hash_file=True
        ) == dict(freeze["source_snapshots"]["development_report"]),
        "code_fingerprint_unchanged": broad_research_code_fingerprint()
        == freeze["identity"]["code_fingerprint"],
        "feature_contract_unchanged": broad_research_feature_contract_fingerprint()
        == freeze["identity"]["feature_contract_fingerprint"],
        "single_rule_exact": dict(freeze.get("single_new_rule") or {}) == expected_rule,
        "no_additional_rules": freeze.get("additional_filters") == [],
        "no_hidden_defaults": set(freeze) >= {
            "entry_contract", "stop_contract", "exit_contract", "cost_and_slippage_contract",
        },
        "no_cross_market_transfer": freeze.get("setup_scope") == SETUP_SCOPE,
        "no_region_or_regime_selection": all(
            item in set(freeze.get("forbidden_rules") or [])
            for item in ("region", "USA_only", "volatility", "market_regime")
        ),
        "development_is_c_recommendation_only": (
            freeze.get("development_source") or {}
        ).get("decision") == DECISION_C_RECOMMENDATION,
        "rules_immutable": freeze.get("rules_mutable_after_freeze") is False,
    }
    initialize_validation_store(store_path)
    with _connect(store_path) as connection:
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "buyer_stage_openings", "buyer_stage_cases", "buyer_stage_completions",
                "buyer_stage_reviews",
            )
        }
    checks["validation_previously_unopened"] = counts["buyer_stage_openings"] == 0
    checks["holdout_previously_unopened"] = counts["buyer_stage_reviews"] == 0
    status = "PASS" if all(checks.values()) else "INVALID"
    return {
        "gate_version": "buyer-confirmation-pre-validation-integrity-2026.08.26-v1",
        "challenger_version": freeze["challenger_version"],
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "checked_at": str(checked_at),
        "status": status,
        "checks": checks,
        "failed_checks": sorted(key for key, passed in checks.items() if passed is not True),
        "existing_stage_counts": counts,
        "validation_open_allowed": status == "PASS",
        "holdout_open_allowed": False,
        "production_changed": False,
    }


def record_integrity_receipt(receipt: Mapping[str, object], path: Path) -> dict[str, object]:
    initialize_validation_store(path)
    payload = dict(receipt)
    fingerprint = _fingerprint(payload)
    version = str(payload["challenger_version"])
    gate_name = str(payload["gate_version"])
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT receipt_fingerprint FROM buyer_integrity_receipts "
            "WHERE challenger_version=? AND gate_name=?",
            (version, gate_name),
        ).fetchone()
        if existing is not None and str(existing[0]) != fingerprint:
            raise BuyerConfirmationValidationError("Integrity gate is already recorded differently.")
        if existing is None:
            connection.execute(
                "INSERT INTO buyer_integrity_receipts VALUES (?, ?, ?, ?)",
                (version, gate_name, _canonical_json(payload), fingerprint),
            )
    return {**payload, "receipt_fingerprint": fingerprint}


def stage_allowed(freeze: Mapping[str, object], stage: str, path: Path) -> dict[str, object]:
    requested = str(stage)
    if requested not in {"validation", "holdout"}:
        raise BuyerConfirmationValidationError(f"Unsupported historical stage: {requested}")
    initialize_validation_store(path)
    with _connect(path) as connection:
        integrity = connection.execute(
            "SELECT receipt_json FROM buyer_integrity_receipts "
            "WHERE challenger_version=? ORDER BY gate_name LIMIT 1",
            (freeze["challenger_version"],),
        ).fetchone()
        validation_review = connection.execute(
            "SELECT decision FROM buyer_stage_reviews WHERE challenger_version=? "
            "AND research_stage='validation'",
            (freeze["challenger_version"],),
        ).fetchone()
    predecessor = None if requested == "validation" else "validation"
    predecessor_decision = str(validation_review[0]) if validation_review else None
    allowed = bool(integrity and json.loads(integrity[0]).get("status") == "PASS")
    if requested == "holdout":
        allowed = allowed and predecessor_decision == "VALIDATION_PASS"
    return {
        "challenger_version": freeze["challenger_version"],
        "research_stage": requested,
        "predecessor": predecessor,
        "predecessor_decision": predecessor_decision,
        "allowed": allowed,
        "parameters_mutable": False,
        "automatic_production_activation": False,
    }


def open_stage(
    freeze: Mapping[str, object], stage: str, *, opened_at: str, path: Path
) -> dict[str, object]:
    gate = stage_allowed(freeze, stage, path)
    if not gate["allowed"]:
        raise BuyerConfirmationValidationError(f"Stage {stage} is locked.")
    payload = {
        **gate,
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "opened_at": str(opened_at),
        "ground_up_from_frozen_ohlcv": True,
        "development_cases_read": False,
        "rules_changed": False,
        "outcomes_seen_before_open": False,
    }
    fingerprint = _fingerprint(payload)
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT opening_fingerprint FROM buyer_stage_openings "
            "WHERE challenger_version=? AND research_stage=?",
            (freeze["challenger_version"], stage),
        ).fetchone()
        if existing is not None and str(existing[0]) != fingerprint:
            raise BuyerConfirmationValidationError("Stage was already opened differently.")
        if existing is None:
            connection.execute(
                "INSERT INTO buyer_stage_openings VALUES (?, ?, ?, ?)",
                (
                    freeze["challenger_version"], stage, _canonical_json(payload), fingerprint,
                ),
            )
    return {**payload, "opening_fingerprint": fingerprint}


def _candidate_record(
    candidate: Mapping[str, object],
    label: Mapping[str, object],
    experiment: Mapping[str, object],
) -> dict[str, object]:
    feature = dict(candidate.get("feature") or {})
    asset = dict(feature.get("asset") or {})
    technical = dict(feature.get("technical") or {})
    pullback = dict(feature.get("pullback") or {})
    candle = dict(feature.get("candle_quality") or {})
    relative = dict(feature.get("relative_strength") or {})
    trend = dict(feature.get("trend_quality") or {})
    structure = dict(feature.get("market_structure") or {})
    entry = dict(label.get("entry") or {})
    stop_group = dict(
        dict(experiment.get("results") or {}).get("pullback_low_atr_buffer") or {}
    )
    selected = dict(dict(stop_group.get("exits") or {}).get("fixed_2r") or {})
    buyer = pullback.get("buyer_confirmation_close_above_prior_high")
    alias = candle.get("close_above_prior_high")
    row = {
        "candidate_id": candidate.get("candidate_id"),
        "symbol": candidate.get("symbol"),
        "signal_day": candidate.get("signal_day"),
        "dependency_cluster": candidate.get("dependency_cluster"),
        "asset_type": asset.get("asset_type"),
        "region": asset.get("region"),
        "market_phase": technical.get("market_phase"),
        "volatility_regime": technical.get("volatility_regime"),
        "pullback_status": pullback.get("status"),
        "buyer_type": None if buyer is None else "true" if buyer is True else "false",
        "buyer_confirmation": buyer,
        "alias_type": None if alias is None else "true" if alias is True else "false",
        "alias_confirmation": alias,
        "bearish_candles": pullback.get("bearish_candles"),
        "pullback_depth": pullback.get("pullback_depth"),
        "pullback_duration": pullback.get("pullback_duration_sessions"),
        "relative_momentum": relative.get("relative_momentum_20d"),
        "close_location": candle.get("close_position_in_range"),
        "ema_ratio": technical.get("ema20_relative_to_ema50"),
        "ema20_slope": trend.get("ema20_slope_atr_per_session"),
        "bos_type": None if structure.get("close_break") is None else "boolean",
        "bos_close_break": structure.get("close_break"),
        "signal_close": technical.get("close"),
        "atr14": technical.get("atr_14"),
        "pullback_low": pullback.get("pullback_low"),
        "entry_policy": entry.get("policy"),
        "entry_day": entry.get("entry_day"),
        "entry_raw": entry.get("raw"),
        "entry_after_costs": entry.get("after_costs"),
        "cost_bps_one_way": entry.get("cost_bps_one_way"),
        "retroactive_entry": entry.get("retroactive_signal_close_entry"),
        "mfe_pct": label.get("mfe_pct"),
        "mae_pct": label.get("mae_pct"),
        "sessions_to_mfe": label.get("time_to_mfe_sessions"),
        "sessions_to_exit": label.get("time_to_exit_sessions"),
        "stored_gap_event_n": len(label.get("gap_events") or []),
        "stop": stop_group.get("stop"),
        "result_r": selected.get("result_r"),
        "exit_status": selected.get("status"),
        "result_sessions": selected.get("sessions"),
    }
    return _record_from_sql(row)


def build_stage_asset(
    freeze: Mapping[str, object],
    asset: Mapping[str, object],
    raw_history: pd.DataFrame,
    *,
    research_stage: str,
) -> dict[str, object]:
    stage = str(research_stage)
    if stage not in {"validation", "holdout"}:
        raise BuyerConfirmationValidationError("Only Validation and Holdout are supported.")
    symbol = str(asset.get("ticker") or "").upper()
    rebuilt = build_asset_broad_research(
        symbol,
        asset,
        raw_history,
        dataset_fingerprint=str(freeze["identity"]["dataset_fingerprint"]),
    )
    labels = {str(row["candidate_id"]): row for row in rebuilt.get("labels") or []}
    experiments = {
        str(row["candidate_id"]): row for row in rebuilt.get("counterfactuals") or []
    }
    cases = []
    for candidate in rebuilt.get("candidates") or []:
        if (
            str(candidate.get("research_split")) != stage
            or str(candidate.get("setup_family")) != SETUP_SCOPE
        ):
            continue
        candidate_id = str(candidate["candidate_id"])
        record = _candidate_record(
            candidate, labels.get(candidate_id) or {}, experiments.get(candidate_id) or {}
        )
        selected = record.get("buyer_confirmation")
        group = "missing" if selected is None else "treatment" if selected is True else "control"
        cases.append(
            {
                **record,
                "comparison_group": group,
                "research_stage": stage,
                "challenger_version": freeze["challenger_version"],
                "freeze_fingerprint": freeze["freeze_fingerprint"],
                "candidate_fingerprint": candidate.get("candidate_fingerprint"),
                "feature_fingerprint": dict(candidate.get("feature") or {}).get(
                    "feature_fingerprint"
                ),
                "label_fingerprint": (labels.get(candidate_id) or {}).get("label_fingerprint"),
                "experiment_fingerprint": (experiments.get(candidate_id) or {}).get(
                    "experiment_fingerprint"
                ),
                "ground_up_from_frozen_ohlcv": True,
                "development_case_read": False,
                "additional_filter_applied": False,
                "parameters_changed": False,
                "automatic_production_activation": False,
            }
        )
    return {
        "challenger_version": freeze["challenger_version"],
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "research_stage": stage,
        "symbol": symbol,
        "source_status": rebuilt.get("status"),
        "rebuilt_candidates": len(rebuilt.get("candidates") or []),
        "applicable_cases": len(cases),
        "treatment_cases": sum(row["comparison_group"] == "treatment" for row in cases),
        "control_cases": sum(row["comparison_group"] == "control" for row in cases),
        "missing_cases": sum(row["comparison_group"] == "missing" for row in cases),
        "cases": cases,
        "ground_up_from_frozen_ohlcv": True,
        "development_case_read": False,
        "parameters_changed": False,
    }


def record_stage_asset(result: Mapping[str, object], path: Path) -> dict[str, object]:
    initialize_validation_store(path)
    version = str(result.get("challenger_version") or "")
    stage = str(result.get("research_stage") or "")
    symbol = str(result.get("symbol") or "").upper()
    with _connect(path) as connection:
        opening = connection.execute(
            "SELECT opening_fingerprint FROM buyer_stage_openings "
            "WHERE challenger_version=? AND research_stage=?",
            (version, stage),
        ).fetchone()
        if opening is None:
            raise BuyerConfirmationValidationError(f"Stage {stage} has not been opened.")
        completion_payload = {
            key: result.get(key)
            for key in (
                "challenger_version", "freeze_fingerprint", "research_stage", "symbol",
                "source_status", "rebuilt_candidates", "applicable_cases", "treatment_cases",
                "control_cases", "missing_cases", "ground_up_from_frozen_ohlcv",
                "development_case_read", "parameters_changed",
            )
        }
        completion_fingerprint = _fingerprint(completion_payload)
        existing = connection.execute(
            "SELECT completion_fingerprint FROM buyer_stage_completions "
            "WHERE challenger_version=? AND research_stage=? AND symbol=?",
            (version, stage, symbol),
        ).fetchone()
        if existing is not None:
            if str(existing[0]) != completion_fingerprint:
                raise BuyerConfirmationValidationError("Asset completion differs on resume.")
            return {
                **completion_payload,
                "completion_fingerprint": completion_fingerprint,
                "already_complete": True,
                "cases_inserted": 0,
            }
        inserted = 0
        for raw_case in result.get("cases") or []:
            case = dict(raw_case)
            case_fingerprint = _fingerprint(case)
            case_id = f"buyer-case-{case_fingerprint[:32]}"
            connection.execute(
                "INSERT INTO buyer_stage_cases VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    case_id, version, stage, str(case["candidate_id"]),
                    str(case["comparison_group"]), _canonical_json(case), case_fingerprint,
                ),
            )
            inserted += 1
        connection.execute(
            "INSERT INTO buyer_stage_completions VALUES (?, ?, ?, ?, ?)",
            (
                version, stage, symbol, _canonical_json(completion_payload),
                completion_fingerprint,
            ),
        )
    return {
        **completion_payload,
        "completion_fingerprint": completion_fingerprint,
        "already_complete": False,
        "cases_inserted": inserted,
    }


def completed_stage_symbols(version: str, stage: str, path: Path) -> set[str]:
    initialize_validation_store(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT symbol FROM buyer_stage_completions "
            "WHERE challenger_version=? AND research_stage=?",
            (version, stage),
        ).fetchall()
    return {str(row[0]).upper() for row in rows}


def _stage_rows(version: str, stage: str, path: Path) -> list[dict[str, object]]:
    initialize_validation_store(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT case_json, case_fingerprint FROM buyer_stage_cases "
            "WHERE challenger_version=? AND research_stage=? "
            "ORDER BY json_extract(case_json, '$.signal_day'), candidate_id",
            (version, stage),
        ).fetchall()
    result = []
    for row in rows:
        payload = json.loads(row["case_json"])
        if _fingerprint(payload) != str(row["case_fingerprint"]):
            raise BuyerConfirmationValidationError("Stored stage case is damaged.")
        result.append(payload)
    return result


def _candidate_sequence_drawdown(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    cumulative = peak = maximum = 0.0
    evaluated = 0
    for row in sorted(rows, key=lambda item: (str(item.get("signal_day")), str(item.get("candidate_id")))):
        result = _number(row.get("result_r"))
        if result is None:
            continue
        evaluated += 1
        cumulative += result
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return {
        "metric_type": "candidate_sequence_drawdown_not_portfolio_drawdown",
        "evaluated_n": evaluated,
        "maximum_drawdown_r": maximum,
        "candidate_order": "signal_day_then_candidate_id",
    }


def evaluate_stage(
    freeze: Mapping[str, object],
    stage: str,
    *,
    path: Path,
    dataset_root: Path,
) -> dict[str, object]:
    requested = str(stage)
    rows = _stage_rows(str(freeze["challenger_version"]), requested, path)
    treatment = [row for row in rows if row.get("comparison_group") == "treatment"]
    control = [row for row in rows if row.get("comparison_group") == "control"]
    missing = [row for row in rows if row.get("comparison_group") == "missing"]
    treatment_summary = summarize_rows(treatment)
    control_summary = summarize_rows(control)
    structural_variants = (
        outcome_blind_exact_match(
            rows, keys=REGION_CLUSTER_MATCH_KEYS, match_id="region_dependency_cluster"
        ),
        outcome_blind_exact_match(
            rows, keys=STRICT_ASSET_CLUSTER_MATCH_KEYS, match_id="symbol_dependency_cluster"
        ),
    )
    selected_match = _choose_match(structural_variants)
    matching = selected_match[2]
    seed_sensitivity = matching_seed_sensitivity(
        rows,
        keys=tuple(matching["strata"]),
        match_id=str(matching["match_id"]),
    )
    execution = execution_simulation(
        selected_match[0], selected_match[1], dataset_root=dataset_root
    )
    valid_rows = treatment + control
    validity = validity_gate(
        universe_n=len(rows),
        applicable_n=len(rows),
        valid_n=len(valid_rows),
        structurally_not_applicable_n=0,
        missing_n=len(missing),
        treatment_n=len(treatment),
        control_n=len(control),
        treatment_effective_n=int(treatment_summary["effective_dependency_cluster_n"]),
        control_effective_n=int(control_summary["effective_dependency_cluster_n"]),
        feature_point_in_time_available=True,
        outcome_independent_definition=True,
        market_scope_correct=True,
        setup_scope_correct=True,
        structural_missingness_treated_as_false=False,
    )
    completed = completed_stage_symbols(str(freeze["challenger_version"]), requested, path)
    expected_assets = int(freeze["expected_assets_per_stage"])
    year_groups = (treatment_summary.get("segments") or {}).get("year", {}).get("groups", {})
    positive_years = sum(
        (_number(value.get("expectancy_r")) or 0) > 0 for value in year_groups.values()
    )
    evaluated_years = len(year_groups)
    segment_reports = (treatment_summary.get("segments") or {}).values()
    gates = {
        "all_expected_assets_completed": len(completed) == expected_assets,
        "validity_and_power_pass": validity.get("status") == VALIDITY_PASS,
        "treatment_expectancy_positive": (_number(treatment_summary.get("expectancy_r")) or 0) > 0,
        "treatment_profit_factor_above_one": (_number(treatment_summary.get("profit_factor")) or 0) > 1,
        "treatment_better_than_control": (
            (_number(treatment_summary.get("expectancy_r")) or 0)
            > (_number(control_summary.get("expectancy_r")) or 0)
        ),
        "matched_delta_positive": (_number(matching.get("delta_expectancy_r")) or 0) > 0,
        "matched_delta_positive_across_predeclared_seeds": seed_sensitivity.get(
            "all_replicates_positive"
        ) is True,
        "positive_in_at_least_60pct_of_years": (
            positive_years / evaluated_years >= 0.60 if evaluated_years else False
        ),
        "no_single_year_above_50pct_absolute_result_contribution": (
            (_number(
                (treatment_summary.get("segments") or {}).get("year", {}).get(
                    "largest_absolute_result_contribution_share"
                )
            ) or 1) <= 0.50
        ),
        "no_disproportionate_regime_or_scope_concentration": all(
            (_number(segment.get("largest_absolute_result_contribution_share")) or 0)
            <= max(0.50, (_number(segment.get("largest_case_share")) or 0) + 0.20)
            for segment in segment_reports
        ),
        "conservative_execution_treatment_positive": (
            _number(execution["treatment"]["conservative"].get("expectancy_r")) or 0
        ) > 0,
        "conservative_execution_treatment_pf_above_one": (
            _number(execution["treatment"]["conservative"].get("profit_factor")) or 0
        ) > 1,
        "conservative_execution_delta_positive": (
            _number(execution.get("conservative_delta_expectancy_r")) or 0
        ) > 0,
        "baseline_execution_reconstruction_exact": (
            int(execution["treatment"]["baseline_reproduction"]["mismatch_n"]) == 0
            and int(execution["control"]["baseline_reproduction"]["mismatch_n"]) == 0
        ),
        "no_integrity_or_scope_violation": all(
            row.get("ground_up_from_frozen_ohlcv") is True
            and row.get("development_case_read") is False
            and row.get("additional_filter_applied") is False
            and row.get("parameters_changed") is False
            for row in rows
        ),
    }
    prefix = requested.upper()
    if not gates["all_expected_assets_completed"] or not gates["no_integrity_or_scope_violation"]:
        status = f"{prefix}_INVALID"
    elif validity.get("status") == VALIDITY_UNDERPOWERED:
        status = f"{prefix}_UNDERPOWERED"
    elif validity.get("status") != VALIDITY_PASS:
        status = f"{prefix}_INVALID"
    elif all(gates.values()):
        status = f"{prefix}_PASS"
    else:
        status = f"{prefix}_FAIL"
    treatment_r = _number(treatment_summary.get("expectancy_r"))
    control_r = _number(control_summary.get("expectancy_r"))
    return {
        "evaluation_version": "buyer-confirmation-unseen-stage-evaluation-2026.08.26-v1",
        "challenger_version": freeze["challenger_version"],
        "freeze_fingerprint": freeze["freeze_fingerprint"],
        "research_stage": requested,
        "status": status,
        "completed_assets": len(completed),
        "expected_assets": expected_assets,
        "raw_n": len(rows),
        "effective_n": {
            "treatment": treatment_summary["effective_dependency_cluster_n"],
            "control": control_summary["effective_dependency_cluster_n"],
        },
        "treatment": treatment_summary,
        "control": control_summary,
        "missing_feature_n": len(missing),
        "delta_expectancy_r": (
            treatment_r - control_r if treatment_r is not None and control_r is not None else None
        ),
        "validity_gate": validity,
        "matching_review": {
            "variants": [item[2] for item in structural_variants],
            "decision_variant": matching,
            "seed_sensitivity": seed_sensitivity,
            "selected_using_outcomes": False,
        },
        "risk_geometry": _geometry_assessment(treatment_summary, control_summary),
        "execution_simulation": execution,
        "candidate_sequence_drawdown": _candidate_sequence_drawdown(treatment),
        "positive_years": positive_years,
        "evaluated_years": evaluated_years,
        "gates": gates,
        "failed_gates": sorted(key for key, passed in gates.items() if passed is not True),
        "parameters_changed": False,
        "retuning_performed": False,
        "next_stage_allowed": status == f"{prefix}_PASS",
        "automatic_production_activation": False,
    }


def record_stage_review(review: Mapping[str, object], *, reviewed_at: str, path: Path) -> dict[str, object]:
    payload = dict(review)
    stage = str(payload.get("research_stage") or "")
    decision = str(payload.get("status") or "")
    if decision not in ALLOWED_STAGE_STATUSES.get(stage, set()):
        raise BuyerConfirmationValidationError("Invalid deterministic stage decision.")
    freeze = load_challenger_freeze(path, str(payload.get("challenger_version") or ""))
    completed = completed_stage_symbols(str(freeze["challenger_version"]), stage, path)
    expected = int(freeze["expected_assets_per_stage"])
    if (
        payload.get("evaluation_version")
        != "buyer-confirmation-unseen-stage-evaluation-2026.08.26-v1"
        or int(payload.get("completed_assets") or -1) != expected
        or int(payload.get("expected_assets") or -1) != expected
        or len(completed) != expected
    ):
        raise BuyerConfirmationValidationError("Stage review requires a complete deterministic evaluation.")
    pass_status = f"{stage.upper()}_PASS"
    if decision == pass_status and (
        payload.get("next_stage_allowed") is not True
        or not payload.get("gates")
        or any(value is not True for value in dict(payload["gates"]).values())
    ):
        raise BuyerConfirmationValidationError("A passing review must satisfy every frozen gate.")
    payload["reviewed_at"] = str(reviewed_at)
    payload["negative_evidence_retained"] = True
    payload["production_changed"] = False
    fingerprint = _fingerprint(payload)
    initialize_validation_store(path)
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT review_fingerprint FROM buyer_stage_reviews "
            "WHERE challenger_version=? AND research_stage=?",
            (payload["challenger_version"], stage),
        ).fetchone()
        if existing is not None and str(existing[0]) != fingerprint:
            raise BuyerConfirmationValidationError("Stage review is already recorded differently.")
        if existing is None:
            connection.execute(
                "INSERT INTO buyer_stage_reviews VALUES (?, ?, ?, ?, ?)",
                (
                    payload["challenger_version"], stage, decision,
                    _canonical_json(payload), fingerprint,
                ),
            )
    return {**payload, "review_fingerprint": fingerprint}


def validation_store_status(path: Path, version: str = CHALLENGER_VERSION) -> dict[str, object]:
    initialize_validation_store(path)
    with _connect(path) as connection:
        result = {
            "store_version": STORE_VERSION,
            "challenger_version": version,
            "freeze_count": int(connection.execute(
                "SELECT COUNT(*) FROM buyer_challenger_freezes WHERE challenger_version=?",
                (version,),
            ).fetchone()[0]),
            "integrity_receipt_count": int(connection.execute(
                "SELECT COUNT(*) FROM buyer_integrity_receipts WHERE challenger_version=?",
                (version,),
            ).fetchone()[0]),
            "stages": {},
        }
        for stage in ("validation", "holdout"):
            review = connection.execute(
                "SELECT decision FROM buyer_stage_reviews WHERE challenger_version=? "
                "AND research_stage=?",
                (version, stage),
            ).fetchone()
            result["stages"][stage] = {
                "opened": connection.execute(
                    "SELECT COUNT(*) FROM buyer_stage_openings WHERE challenger_version=? "
                    "AND research_stage=?",
                    (version, stage),
                ).fetchone()[0] == 1,
                "completed_assets": int(connection.execute(
                    "SELECT COUNT(*) FROM buyer_stage_completions WHERE challenger_version=? "
                    "AND research_stage=?",
                    (version, stage),
                ).fetchone()[0]),
                "cases": int(connection.execute(
                    "SELECT COUNT(*) FROM buyer_stage_cases WHERE challenger_version=? "
                    "AND research_stage=?",
                    (version, stage),
                ).fetchone()[0]),
                "decision": str(review[0]) if review else None,
            }
    result["automatic_production_activation"] = False
    return result


def write_append_only_report(report: Mapping[str, object], path: Path) -> dict[str, object]:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical_json(report, indent=2) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise BuyerConfirmationValidationError(f"Append-only report differs: {destination}")
        return {"path": str(destination), "already_exists": True}
    destination.write_text(encoded, encoding="utf-8", newline="\n")
    return {"path": str(destination), "already_exists": False}
