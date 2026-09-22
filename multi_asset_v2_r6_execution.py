from __future__ import annotations

"""Outcome-blind R6 enrichment over immutable v7-r2 Development evidence.

The worker layer reads the audited parent stores and the frozen OHLC projections,
but never writes SQLite.  It materializes only the new R4-B/R4-H feature delta
and a compact reference to the unchanged parent outcome.  The main process owns
all writes through the existing append-only, single-writer store implementation.
"""

import json
import math
import sqlite3
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from crypto_r4h_features import build_crypto_r4h_features, load_contract as load_r4h_contract
from multi_asset_development_v6_inputs import load_v6_asset_history
from multi_asset_discovery_v1 import fingerprint
from multi_asset_v2_r4b_features import build_r4b_features, load_contract as load_r4b_contract


ROOT = Path(__file__).resolve().parent
PARENT_RUN_ID = "mad1-development-v7-recovery-20260913-v2"
PARENT_CONTROL_STORE = ROOT / "runtime" / "multi_asset_discovery_v1_development_v7r2_control.sqlite3"
PARENT_FEATURE_STORE = ROOT / "runtime" / "multi_asset_discovery_v1_development_v7r2_features.sqlite3"
PARENT_OUTCOME_STORE = ROOT / "runtime" / "multi_asset_discovery_v1_development_v7r2_outcomes.sqlite3"
R6_COMPUTE_VERSION = "multi-asset-discovery-v2-r6-compute-2026.09.22-v1"
R6_FEATURE_VERSION = "multi-asset-discovery-v2-r6-feature-delta-2026.09.22-v1"
R6_OUTCOME_REFERENCE_VERSION = "multi-asset-discovery-v2-r6-outcome-reference-2026.09.22-v1"
R6_PLAN_VERSION = "multi-asset-discovery-v2-r6-plan-2026.09.22-v1"
CHECKPOINTS = (20, 60, 120, 252)


class MultiAssetV2R6ExecutionError(RuntimeError):
    """R6 cannot proceed without violating frozen provenance or semantics."""


def _read_only(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise MultiAssetV2R6ExecutionError(f"Required immutable parent store missing: {resolved}")
    return sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=120)


def build_r6_universe_and_work_plan(
    *,
    r5_contract_fingerprint: str,
    parent_control_store: Path = PARENT_CONTROL_STORE,
) -> tuple[dict[str, object], dict[str, object]]:
    """Reuse only the audited Equity/ETF/Crypto parent partition, never FX."""

    with _read_only(parent_control_store) as connection:
        run = connection.execute(
            "SELECT status,contract_fingerprint,total_planned_work_units FROM runs WHERE run_id=?",
            (PARENT_RUN_ID,),
        ).fetchone()
        if run is None or str(run[0]) != "COMPLETED" or int(run[2]) != 60_504:
            raise MultiAssetV2R6ExecutionError("Parent v7-r2 run is not the audited terminal run.")
        rows = connection.execute(
            "SELECT work_unit_id,asset_key,asset_class,symbol,period_start,period_end,status "
            "FROM work_units WHERE run_id=? AND asset_class IN ('EQUITIES','ETF','CRYPTO') "
            "ORDER BY asset_class,symbol,period_start",
            (PARENT_RUN_ID,),
        ).fetchall()
    if len(rows) != 60_432:
        raise MultiAssetV2R6ExecutionError("R6 parent work-plan count changed.")
    if any(str(row[6]) not in {"COMPLETED", "SKIPPED"} for row in rows):
        raise MultiAssetV2R6ExecutionError("R6 parent work plan contains non-terminal units.")
    units = [
        {
            "work_unit_id": str(row[0]),
            "asset_key": str(row[1]),
            "asset_class": str(row[2]),
            "symbol": str(row[3]),
            "period_start": str(row[4]),
            "period_end": str(row[5]),
            "parent_status": str(row[6]),
        }
        for row in rows
    ]
    assets = [
        {"asset_key": key, "asset_class": asset_class, "symbol": symbol}
        for key, asset_class, symbol in sorted(
            {(item["asset_key"], item["asset_class"], item["symbol"]) for item in units},
            key=lambda item: (item[1], item[2]),
        )
    ]
    if len(assets) != 2_518:
        raise MultiAssetV2R6ExecutionError("R6 parent asset count changed.")
    universe_basis = {
        "r5_contract_fingerprint": r5_contract_fingerprint,
        "parent_run_id": PARENT_RUN_ID,
        "assets": assets,
    }
    universe = {
        "version": R6_PLAN_VERSION,
        **universe_basis,
        "asset_count": len(assets),
        "asset_class_counts": {
            name: sum(item["asset_class"] == name for item in assets)
            for name in ("EQUITIES", "ETF", "CRYPTO")
        },
        "universe_fingerprint": fingerprint(universe_basis),
        "validation_opened": False,
        "holdout_opened": False,
    }
    plan_units = [
        {key: value for key, value in item.items() if key != "parent_status"}
        for item in units
    ]
    plan = {
        "version": R6_PLAN_VERSION,
        "run_id": "mad2-development-v2-20260922-v1",
        "parent_run_id": PARENT_RUN_ID,
        "partition": "asset_by_calendar_quarter",
        "total_planned_work_units": len(plan_units),
        "units": plan_units,
        "parent_status_by_work_unit": {
            item["work_unit_id"]: item["parent_status"] for item in units
        },
        "work_plan_fingerprint": fingerprint(plan_units),
        "validation_opened": False,
        "holdout_opened": False,
    }
    return universe, plan


@lru_cache(maxsize=4)
def _benchmark_frame(asset_class: str, symbol: str) -> pd.DataFrame:
    history = load_v6_asset_history(
        {"asset_class": asset_class, "symbol": symbol},
        verify_store_sha256=False,
    )
    frame = history.frame[["Open", "High", "Low", "Close", "Volume", "SEGMENT_ID"]].copy()
    frame = frame.rename(columns={"SEGMENT_ID": "SegmentId"})
    return frame


def _asset_history(asset_class: str, symbol: str) -> pd.DataFrame:
    history = load_v6_asset_history(
        {"asset_class": asset_class, "symbol": symbol},
        verify_store_sha256=False,
    )
    return history.frame.copy()


def _r4b_enrichment(asset_class: str, symbol: str) -> tuple[pd.DataFrame, str]:
    _, contract_fingerprint = load_r4b_contract()
    history = _asset_history(asset_class, symbol)
    if history.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="Date")), contract_fingerprint
    benchmark = _benchmark_frame("ETF", "ACWI")[["Close", "SegmentId"]]
    parts: list[pd.DataFrame] = []
    for _, segment in history.groupby("SEGMENT_ID", sort=True):
        parts.append(
            build_r4b_features(
                segment[["Open", "High", "Low", "Close"]], benchmark
            )
        )
    return pd.concat(parts).sort_index(kind="stable"), contract_fingerprint


def _r4h_enrichment(symbol: str) -> tuple[pd.DataFrame, str]:
    _, contract_fingerprint = load_r4h_contract()
    history = _asset_history("CRYPTO", symbol)
    if history.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="Date")), contract_fingerprint
    asset = history[["Open", "High", "Low", "Close", "Volume", "SEGMENT_ID"]].rename(
        columns={"SEGMENT_ID": "SegmentId"}
    )
    benchmark = _benchmark_frame("CRYPTO", "BTC-USD")
    return build_crypto_r4h_features(asset, benchmark), contract_fingerprint


def _scalar(value: object) -> object:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _feature_delta(
    *, row: pd.Series, family: str, signal_day: str
) -> tuple[dict[str, object], dict[str, dict[str, str]]]:
    prefix = "r4b" if family == "R4B" else "r4h"
    metadata = {
        "r4b_contract_fingerprint",
        "r4h_contract_fingerprint",
        "source_dataset_fingerprint",
        "strategy_filter_created",
    }
    unavailable_columns = {
        "sector_benchmark_status",
        "onchain_status",
        "dominance_status",
    }
    unknown_columns = {"historical_region_status", "reported_volume_units_status"}
    values: dict[str, object] = {}
    missing: dict[str, dict[str, str]] = {}
    for name in row.index:
        if name in metadata:
            continue
        key = f"{prefix}.{name}"
        value = _scalar(row[name])
        if name in unavailable_columns:
            missing[key] = {"status": "UNAVAILABLE", "reason": str(value)}
        elif name in unknown_columns:
            missing[key] = {"status": "UNKNOWN", "reason": str(value)}
        elif name == "confirmed_structure_sequence" and value == "INSUFFICIENT_CONFIRMED_PIVOTS":
            missing[key] = {"status": "UNKNOWN", "reason": str(value)}
        elif value is None or (isinstance(value, str) and not value):
            missing[key] = {
                "status": "UNKNOWN",
                "reason": "SOURCE_OR_CAUSAL_LOOKBACK_NOT_AVAILABLE",
            }
        else:
            values[key] = value
    return values, missing


def _checkpoint_availability(parent_outcome: Mapping[str, object]) -> dict[str, object]:
    checkpoints = dict(parent_outcome.get("checkpoints") or {})
    result: dict[str, object] = {}
    for horizon in CHECKPOINTS:
        checkpoint = checkpoints.get(str(horizon))
        available = (
            isinstance(checkpoint, Mapping)
            and int(checkpoint.get("observations") or 0) == horizon
            and bool(checkpoint.get("end_day"))
            and str(checkpoint.get("end_day")) <= "2021-12-31"
        )
        result[str(horizon)] = {
            "status": "AVAILABLE" if available else "CENSORED_OR_UNAVAILABLE",
            "observations": horizon if available else None,
            "reason": None if available else str(
                parent_outcome.get("censoring_reason")
                or parent_outcome.get("reason")
                or "CHECKPOINT_NOT_PRESENT"
            ),
        }
    return result


def _verify_parent_unit(
    *,
    unit: Mapping[str, object],
    control: sqlite3.Connection,
    features: sqlite3.Connection,
    outcomes: sqlite3.Connection,
) -> tuple[str, list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    work_unit_id = str(unit["work_unit_id"])
    control_row = control.execute(
        "SELECT status FROM work_units WHERE run_id=? AND work_unit_id=?",
        (PARENT_RUN_ID, work_unit_id),
    ).fetchone()
    receipt = control.execute(
        "SELECT feature_rows,outcome_rows,case_set_digest,feature_payload_digest,"
        "outcome_payload_digest FROM unit_receipts WHERE run_id=? AND work_unit_id=?",
        (PARENT_RUN_ID, work_unit_id),
    ).fetchone()
    if control_row is None or receipt is None:
        raise MultiAssetV2R6ExecutionError(f"Parent unit/receipt missing: {work_unit_id}")
    status = str(control_row[0])
    feature_rows = features.execute(
        "SELECT case_id,feature_fingerprint,asset_id,symbol,asset_class,signal_day,"
        "dependency_status FROM feature_rows WHERE run_id=? AND work_unit_id=? ORDER BY case_id",
        (PARENT_RUN_ID, work_unit_id),
    ).fetchall()
    outcome_rows = outcomes.execute(
        "SELECT case_id,outcome_fingerprint,feature_fingerprint,asset_id,symbol,asset_class,"
        "signal_day,dependency_status,payload_zlib FROM outcome_rows "
        "WHERE run_id=? AND work_unit_id=? ORDER BY case_id",
        (PARENT_RUN_ID, work_unit_id),
    ).fetchall()
    feature_digest_rows = [(str(row[0]), str(row[1]), None) for row in feature_rows]
    outcome_digest_rows = [(str(row[0]), str(row[1]), str(row[2])) for row in outcome_rows]
    expected = (
        len(feature_rows),
        len(outcome_rows),
        fingerprint([row[0] for row in feature_digest_rows]),
        fingerprint(feature_digest_rows),
        fingerprint(outcome_digest_rows),
    )
    if tuple(receipt) != expected:
        raise MultiAssetV2R6ExecutionError(f"Parent receipt mismatch: {work_unit_id}")
    if status not in {"COMPLETED", "SKIPPED"}:
        raise MultiAssetV2R6ExecutionError(f"Parent unit not terminal: {work_unit_id}")
    if status == "SKIPPED" and (feature_rows or outcome_rows):
        raise MultiAssetV2R6ExecutionError(f"Skipped parent unit contains evidence: {work_unit_id}")
    if len(feature_rows) != len(outcome_rows):
        raise MultiAssetV2R6ExecutionError(f"Parent cross-store count mismatch: {work_unit_id}")
    return status, feature_rows, outcome_rows


def compute_r6_asset_batch(
    *,
    asset: Mapping[str, object],
    units: Sequence[Mapping[str, object]],
    r5_contract_fingerprint: str,
    parent_control_store: Path = PARENT_CONTROL_STORE,
    parent_feature_store: Path = PARENT_FEATURE_STORE,
    parent_outcome_store: Path = PARENT_OUTCOME_STORE,
) -> dict[str, object]:
    """Create deterministic v2 deltas/references for one asset batch."""

    asset_class = str(asset["asset_class"])
    symbol = str(asset["symbol"])
    if asset_class in {"EQUITIES", "ETF"}:
        enrichment, feature_contract_fingerprint = _r4b_enrichment(asset_class, symbol)
        family = "R4B"
    elif asset_class == "CRYPTO":
        enrichment, feature_contract_fingerprint = _r4h_enrichment(symbol)
        family = "R4H"
    else:
        raise MultiAssetV2R6ExecutionError(f"R6 excludes asset class: {asset_class}")
    unit_results: list[dict[str, object]] = []
    with (
        _read_only(parent_control_store) as control,
        _read_only(parent_feature_store) as parent_features,
        _read_only(parent_outcome_store) as parent_outcomes,
    ):
        for unit in units:
            parent_status, feature_rows, outcome_rows = _verify_parent_unit(
                unit=unit,
                control=control,
                features=parent_features,
                outcomes=parent_outcomes,
            )
            if parent_status == "SKIPPED":
                unit_results.append(
                    {
                        "unit": dict(unit),
                        "parent_status": parent_status,
                        "features": [],
                        "outcomes": [],
                        "summary": {"source_parent_status": parent_status},
                    }
                )
                continue
            outcome_by_case = {str(row[0]): row for row in outcome_rows}
            new_features: list[dict[str, object]] = []
            new_outcomes: list[dict[str, object]] = []
            checkpoint_counts = {str(item): 0 for item in CHECKPOINTS}
            r_na_cases = 0
            censored_cases = 0
            missing_feature_cells = 0
            for parent_feature in feature_rows:
                parent_case_id = str(parent_feature[0])
                parent_outcome = outcome_by_case.get(parent_case_id)
                if parent_outcome is None or str(parent_outcome[2]) != str(parent_feature[1]):
                    raise MultiAssetV2R6ExecutionError(
                        f"Parent feature/outcome link mismatch: {parent_case_id}"
                    )
                signal_day = str(parent_feature[5])
                if not ("2016-01-01" <= signal_day <= "2021-12-31"):
                    raise MultiAssetV2R6ExecutionError("Non-Development parent case reached R6.")
                timestamp = pd.Timestamp(signal_day)
                if timestamp not in enrichment.index:
                    raise MultiAssetV2R6ExecutionError(
                        f"R6 feature source missing parent signal day: {asset_class}:{symbol}:{signal_day}"
                    )
                values, missing = _feature_delta(
                    row=enrichment.loc[timestamp], family=family, signal_day=signal_day
                )
                missing_feature_cells += len(missing)
                case_basis = {
                    "version": R6_FEATURE_VERSION,
                    "r5_contract_fingerprint": r5_contract_fingerprint,
                    "feature_contract_fingerprint": feature_contract_fingerprint,
                    "parent_run_id": PARENT_RUN_ID,
                    "parent_case_id": parent_case_id,
                    "parent_feature_fingerprint": str(parent_feature[1]),
                }
                # A feature version does not create a new historical signal event.
                # Keep the audited signal-case identity stable and version the
                # feature/outcome-reference payloads independently.
                case_id = parent_case_id
                feature = {
                    "case_id": case_id,
                    "feature_version": R6_FEATURE_VERSION,
                    "r5_contract_fingerprint": r5_contract_fingerprint,
                    "feature_contract_fingerprint": feature_contract_fingerprint,
                    "parent_run_id": PARENT_RUN_ID,
                    "parent_case_id": parent_case_id,
                    "parent_feature_fingerprint": str(parent_feature[1]),
                    "case_lineage_fingerprint": fingerprint(case_basis),
                    "parent_core_features": "IMMUTABLE_REFERENCE_NOT_COPIED",
                    "asset_id": str(parent_feature[2]),
                    "symbol": str(parent_feature[3]),
                    "asset_class": str(parent_feature[4]),
                    "signal_day": signal_day,
                    "decision_time": f"{signal_day}T23:59:59+00:00",
                    "research_split": "development",
                    "dependency_status": str(parent_feature[6]),
                    "active_feature_family": (
                        "RELATIVE_STRENGTH_GLOBAL_ACWI_AND_CONFIRMED_STRUCTURE"
                        if family == "R4B"
                        else "CRYPTO_BTC_RELATIVE_AND_REPORTED_VOLUME"
                    ),
                    "feature_values": values,
                    "missing_features": missing,
                    "shadow_or_unavailable_families_materialized": False,
                    "strategy_filter_created": False,
                    "outcomes_used_for_feature_construction": False,
                }
                feature["feature_fingerprint"] = fingerprint(feature)
                parent_payload = json.loads(zlib.decompress(parent_outcome[8]).decode("utf-8"))
                stored_parent_outcome_fingerprint = str(parent_outcome[1])
                payload_basis = dict(parent_payload)
                payload_basis.pop("outcome_fingerprint", None)
                if (
                    parent_payload.get("case_id") != parent_case_id
                    or fingerprint(payload_basis) != stored_parent_outcome_fingerprint
                ):
                    raise MultiAssetV2R6ExecutionError(
                        f"Parent outcome payload invalid: {parent_case_id}"
                    )
                checkpoint_availability = _checkpoint_availability(parent_payload)
                for horizon, status in checkpoint_availability.items():
                    if dict(status)["status"] == "AVAILABLE":
                        checkpoint_counts[horizon] += 1
                if str(parent_payload.get("r_metrics_status")) != "AVAILABLE":
                    r_na_cases += 1
                if str(parent_payload.get("status", "")).startswith("CENSORED_"):
                    censored_cases += 1
                outcome_reference = {
                    "case_id": case_id,
                    "outcome_version": R6_OUTCOME_REFERENCE_VERSION,
                    "feature_fingerprint": feature["feature_fingerprint"],
                    "parent_run_id": PARENT_RUN_ID,
                    "parent_case_id": parent_case_id,
                    "parent_outcome_fingerprint": stored_parent_outcome_fingerprint,
                    "parent_outcome_payload": "IMMUTABLE_REFERENCE_NOT_COPIED",
                    "asset_id": str(parent_outcome[3]),
                    "symbol": str(parent_outcome[4]),
                    "asset_class": str(parent_outcome[5]),
                    "signal_day": str(parent_outcome[6]),
                    "research_split": "development",
                    "dependency_status": str(parent_outcome[7]),
                    "status": "PARENT_OUTCOME_REFERENCE_VERIFIED",
                    "r_availability": str(parent_payload.get("r_metrics_status") or "UNAVAILABLE"),
                    "parent_measurement_status": parent_payload.get("measurement_status"),
                    "parent_path_status": parent_payload.get("status"),
                    "checkpoint_availability": checkpoint_availability,
                    "outcome_values_copied": False,
                    "validation_opened": False,
                    "holdout_opened": False,
                }
                outcome_reference["outcome_fingerprint"] = fingerprint(outcome_reference)
                new_features.append(feature)
                new_outcomes.append(outcome_reference)
            summary = {
                "source_parent_status": parent_status,
                "parent_cases": len(feature_rows),
                "feature_delta_rows": len(new_features),
                "outcome_reference_rows": len(new_outcomes),
                "missing_feature_cells": missing_feature_cells,
                "checkpoint_available": checkpoint_counts,
                "r_na_cases": r_na_cases,
                "censored_cases": censored_cases,
            }
            unit_results.append(
                {
                    "unit": dict(unit),
                    "parent_status": parent_status,
                    "features": new_features,
                    "outcomes": new_outcomes,
                    "summary": summary,
                }
            )
    result = {
        "compute_version": R6_COMPUTE_VERSION,
        "asset": dict(asset),
        "unit_results": unit_results,
        "r5_contract_fingerprint": r5_contract_fingerprint,
        "feature_contract_fingerprint": feature_contract_fingerprint,
        "validation_opened": False,
        "holdout_opened": False,
    }
    result["scientific_digest"] = r6_result_digest(result)
    return result


def r6_result_digest(result: Mapping[str, object]) -> str:
    basis = {
        "compute_version": result.get("compute_version"),
        "asset": dict(result.get("asset") or {}),
        "r5_contract_fingerprint": result.get("r5_contract_fingerprint"),
        "feature_contract_fingerprint": result.get("feature_contract_fingerprint"),
        "unit_results": [
            {
                "work_unit_id": dict(item["unit"])["work_unit_id"],
                "parent_status": item["parent_status"],
                "features": item["features"],
                "outcomes": item["outcomes"],
                "summary": item["summary"],
            }
            for item in result.get("unit_results") or []
        ],
    }
    return fingerprint(basis)


__all__ = [
    "CHECKPOINTS",
    "MultiAssetV2R6ExecutionError",
    "PARENT_CONTROL_STORE",
    "PARENT_FEATURE_STORE",
    "PARENT_OUTCOME_STORE",
    "PARENT_RUN_ID",
    "R6_COMPUTE_VERSION",
    "R6_FEATURE_VERSION",
    "R6_OUTCOME_REFERENCE_VERSION",
    "build_r6_universe_and_work_plan",
    "compute_r6_asset_batch",
    "r6_result_digest",
]
