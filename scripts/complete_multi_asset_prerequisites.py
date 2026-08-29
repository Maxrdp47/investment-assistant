from __future__ import annotations

"""Close the three preregistered prerequisites without starting a new scan.

The command is intentionally an administrative result handoff.  It creates no
candidate, label, trade, strategy or unseen-stage run.  Replays are idempotent
through the existing work-request result channel.
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from failed_seller_research import failed_seller_feature_contract  # noqa: E402
from fx_carry_pit import (  # noqa: E402
    DEFAULT_FX_CARRY_DB_PATH,
    default_fx_pair_contracts,
    fx_pipeline_coverage_report,
    store_fx_pair_contracts,
)
from research_knowledge import ResearchWorkflow  # noqa: E402
from swing_research_identity_v2 import (  # noqa: E402
    RESEARCH_DEPENDENCY_V2_VERSION,
    RESEARCH_IDENTITY_V2_VERSION,
)


FIBONACCI_REQUEST_ID = "d941320c-48ca-43fb-9bd9-0c362d8873ea"
FX_CARRY_REQUEST_ID = "1f6201fe-2cbd-4fc1-9bf1-291a4221bdfa"
FX_CARRY_HYPOTHESIS_ID = "0a6350d5-718f-437d-97c1-f484fb8e11bf"
FX_CARRY_EXPERIMENT_ID = "793d4731-4de5-4c16-a7f3-dd44dea1761c"
FAILED_SELLER_REQUEST_ID = "d4dbaf10-b321-4223-9a0b-91f0bc245151"
GOLD_SILVER_REQUEST_ID = "4fdfb983-ddbc-4178-bd36-7aa34267df0b"
WATER_REQUEST_ID = "3721453e-158f-42cb-8d76-a28f054b7d97"

WORKER_CONTEXT = "codex/multi-asset-prerequisites-2026.08.28"
DEFAULT_KB = PROJECT_ROOT / "runtime" / "research_knowledge.sqlite3"
DEFAULT_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "research_exports"
DEFAULT_FAILED_REPORT = DEFAULT_EXPORT_ROOT / "failed_seller_development_2026-08-28-v1.json"
FIB_AUDIT_JSON = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "swing_broad_v1_method_audit_2026-08-25-v3-reviewed.json"
)
FIB_AUDIT_MD = PROJECT_ROOT / "research_reports" / "BROAD_V1_METHOD_AUDIT_2026-08-25.md"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_artifact(path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    value = dict(payload)
    value["artifact_fingerprint"] = _fingerprint(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def _display_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def _git(*args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def build_identity_gate(*, created_at: str) -> dict[str, object]:
    """Describe the mandatory future identity gate, not current market evidence."""

    return {
        "status": "READY_FOR_FUTURE_RESEARCH_WITH_UNKNOWN_DEPENDENCY_REPORTED",
        "created_at": created_at,
        "identity_version": RESEARCH_IDENTITY_V2_VERSION,
        "dependency_version": RESEARCH_DEPENDENCY_V2_VERSION,
        "separate_ids": ["asset_id", "listing_id", "issuer_id"],
        "listing_fields": [
            "ticker",
            "exchange",
            "currency",
            "instrument_type",
            "listing_role",
            "is_depositary_receipt",
            "depositary_ratio",
            "isin",
            "exchange_timezone",
            "valid_from",
            "valid_to",
        ],
        "issuer_resolution": {
            "accepted": ["explicit", "versioned_registry"],
            "normalized_name": "candidate_key_only",
            "unknown_allowed": True,
            "unknown_assumed_independent": False,
        },
        "listing_bundle_guard": (
            "OHLCV, price, volume, spread, trading hours, technical levels, entry, "
            "stop, target, liquidity and gaps must share the selected listing_id and currency"
        ),
        "evidence_contract": {
            "raw_n_separate": True,
            "issuer_cluster_n_separate": True,
            "unknown_dependency_n_separate": True,
            "unknown_effective_n": 0,
            "multiple_listings_not_independent": True,
        },
        "current_versioned_issuer_registry": "NOT_AVAILABLE",
        "limitation": (
            "The immutable Broad-v1 name-derived issuer field is not promoted to verified "
            "issuer identity. Future research must report UNKNOWN until a versioned mapping exists."
        ),
        "broad_v1_modified": False,
        "multi_asset_scan_started": False,
        "strategy_activated": False,
    }


def build_fibonacci_reuse(*, created_at: str) -> dict[str, object]:
    for source in (FIB_AUDIT_JSON, FIB_AUDIT_MD):
        if not source.exists():
            raise FileNotFoundError(source)
    payload = {
        "status": "COMPLETED_BY_IDENTICAL_EXISTING_DEVELOPMENT_RESULT",
        "created_at": created_at,
        "work_request_id": FIBONACCI_REQUEST_ID,
        "new_research_run_started": False,
        "contract_identity": {
            "setup_scope": "objective_pullback",
            "treatment_zone": [0.618, 0.786],
            "equal_width_controls": [[0.450, 0.618], [0.786, 0.954]],
            "continuous_pullback_depth_control": True,
            "same_entry_cost_label_result_contract": True,
            "extensions_tested": 0,
        },
        "existing_development_result": {
            "recommendation": "B",
            "treatment_n": 23_575,
            "control_n": 358_065,
            "effective_n_treatment": 18_124,
            "effective_n_control": 105_677,
            "treatment_expectancy_r": 0.0446,
            "treatment_profit_factor": 1.072,
            "lower_control_expectancy_r": 0.0264,
            "upper_control_expectancy_r": -0.0705,
            "delta_vs_mean_equal_width_controls_r": 0.0667,
            "depth_adjusted_residual_delta_r": 0.0232,
            "positive_years": 5,
            "year_n": 9,
            "additional_slippage_result": "NEGATIVE",
            "conclusion": "INCONCLUSIVE_DEVELOPMENT_B_ONLY",
        },
        "unseen_stage_opened": False,
        "new_level_search": False,
        "strategy_activated": False,
        "source_artifacts": [
            {
                "path": str(FIB_AUDIT_JSON.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": _file_sha256(FIB_AUDIT_JSON),
            },
            {
                "path": str(FIB_AUDIT_MD.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": _file_sha256(FIB_AUDIT_MD),
            },
        ],
    }
    return payload


def build_fx_coverage(*, created_at: str, database: Path) -> dict[str, object]:
    contracts = default_fx_pair_contracts()
    store_fx_pair_contracts(contracts.values(), path=database, created_at=created_at)
    coverage = fx_pipeline_coverage_report((), contracts=contracts)
    code_path = PROJECT_ROOT / "fx_carry_pit.py"
    pair_fingerprint = _fingerprint(sorted(contracts))
    research_contract_fingerprint = _fingerprint(
        {
            "comparison_order": [
                "absolute_rates",
                "expected_differential",
                "volatility",
                "positioning",
                "surprise",
            ],
            "research_label_horizons": [5, 10, 20, 60],
            "horizons_are_exit_rules": False,
            "coverage_fields": coverage["fields"],
        }
    )
    return {
        **coverage,
        "run_id": f"fx-carry-pit-pipeline-{str(coverage['coverage_fingerprint'])[:24]}",
        "created_at": created_at,
        "start_time": created_at,
        "end_time": created_at,
        "work_request_id": FX_CARRY_REQUEST_ID,
        "hypothesis_id": FX_CARRY_HYPOTHESIS_ID,
        "experiment_id": FX_CARRY_EXPERIMENT_ID,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit_hash": _git("rev-parse", "HEAD"),
        "code_fingerprint": _file_sha256(code_path),
        "dataset_fingerprint": "NO_HISTORICAL_PIT_DATASET_AVAILABLE",
        "feature_contract_fingerprint": coverage["coverage_fingerprint"],
        "research_contract_fingerprint": research_contract_fingerprint,
        "universe_pair_fingerprint": pair_fingerprint,
        "command": "scripts/complete_multi_asset_prerequisites.py",
        "config": {
            "pairs": sorted(contracts),
            "point_in_time_required": True,
            "missing_values_approximated": False,
            "research_label_horizons": [5, 10, 20, 60],
            "exit_rule_created": False,
        },
        "pair_contract_n": len(contracts),
        "runtime_database": _display_path(database),
        "runtime_database_sha256": _file_sha256(database),
        "output_artifacts": [
            _display_path(database),
            "runtime/research_exports/fx_carry_pit_coverage_2026-08-28-v1.json",
        ],
        "historical_observations_imported": 0,
        "research_attempt_count": 0,
        "research_result_computed": False,
        "multi_asset_scan_started": False,
    }


def _artifact_reference(
    *, system: str, record_type: str, record_id: str, path: Path
) -> dict[str, object]:
    return {
        "system": system,
        "record_type": record_type,
        "record_id": record_id,
        "uri": str(path.resolve()),
        "sha256": _file_sha256(path),
    }


def complete_request(
    workflow: ResearchWorkflow,
    request_id: str,
    *,
    result: Mapping[str, object],
    result_reference: Path,
    artifact_references: tuple[Mapping[str, object], ...],
    completed_at: str,
) -> dict[str, object]:
    token = f"multi-asset-prerequisites-2026.08.28:{request_id}"
    request = workflow.get_work_request(request_id, include_context=False)
    if request["current_status"] == "COMPLETED":
        if not request.get("result_id"):
            raise RuntimeError(f"Completed request {request_id} has no result.")
        request["idempotent_replay"] = True
        return request
    if request["current_status"] not in {"READY", "IN_PROGRESS"}:
        raise RuntimeError(
            f"Work Request {request_id} is {request['current_status']}, expected READY."
        )
    claimed = workflow.claim_work_request(
        request_id,
        worker_context=WORKER_CONTEXT,
        claim_token=token,
        claimed_at=completed_at,
    )
    return workflow.complete_work_request(
        request_id,
        claim_token=str(claimed["claim_token"]),
        worker_context=WORKER_CONTEXT,
        result=result,
        result_reference=str(result_reference.resolve()),
        artifact_references=artifact_references,
        completed_at=completed_at,
    )


def _request_state(path: Path, request_id: str) -> dict[str, object]:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, current_status, experiment_id, result_id FROM research_work_requests WHERE id=?",
            (request_id,),
        ).fetchone()
    if row is None:
        raise KeyError(request_id)
    return dict(row)


def complete_all(
    *,
    knowledge_base: Path,
    export_root: Path,
    fx_database: Path,
    failed_seller_report: Path,
    completed_at: str | None = None,
) -> dict[str, object]:
    timestamp = completed_at or datetime.now(timezone.utc).isoformat()
    failed = json.loads(failed_seller_report.read_text(encoding="utf-8"))
    failed_result = dict(failed.get("result") or {})
    if (
        failed.get("status") != "COMPLETED_DEVELOPMENT_ONLY"
        or failed.get("multi_asset_scan_started") is not False
        or failed_result.get("result_direction") != "INCONCLUSIVE"
    ):
        raise RuntimeError("Failed-Seller report violates the Development-only gate.")

    final_path = export_root / "multi_asset_prerequisites_completion_2026-08-28-v1.json"
    completed_states = {
        request_id: _request_state(knowledge_base, request_id)
        for request_id in (
            FIBONACCI_REQUEST_ID,
            FX_CARRY_REQUEST_ID,
            FAILED_SELLER_REQUEST_ID,
        )
    }
    if final_path.exists() and all(
        state["current_status"] == "COMPLETED" and state["result_id"]
        for state in completed_states.values()
    ):
        stored = json.loads(final_path.read_text(encoding="utf-8"))
        if stored.get("multi_asset_scan_started") is not False:
            raise RuntimeError("Stored prerequisite completion violates the no-scan gate.")
        for request_id in (GOLD_SILVER_REQUEST_ID, WATER_REQUEST_ID):
            if _request_state(knowledge_base, request_id)["current_status"] != "READY":
                raise RuntimeError("A protected specialized work request changed unexpectedly.")
        return {**stored, "idempotent_replay": True}

    identity_path = export_root / "multi_asset_identity_gate_2026-08-28-v1.json"
    fib_path = export_root / "fibonacci_broad_v1_reuse_2026-08-28-v1.json"
    fx_path = export_root / "fx_carry_pit_coverage_2026-08-28-v1.json"
    identity = _write_artifact(identity_path, build_identity_gate(created_at=timestamp))
    fibonacci = _write_artifact(fib_path, build_fibonacci_reuse(created_at=timestamp))
    fx = _write_artifact(
        fx_path,
        build_fx_coverage(created_at=timestamp, database=fx_database),
    )

    workflow = ResearchWorkflow(knowledge_base)
    fib_completed = complete_request(
        workflow,
        FIBONACCI_REQUEST_ID,
        result={
            "title": "Fibonacci 61,8–78,6 – vorhandenes Broad-v1-Ergebnis wiederverwendet",
            "conclusion": "inconclusive",
            "interpretation": (
                "Der READY-Vertrag ist fachlich identisch mit dem unveränderlichen Broad-v1-"
                "Development-Audit. Deshalb wurde kein neuer Lauf gestartet. Das B-Ergebnis "
                "ist klein, unter Zusatzslippage negativ und öffnet keine ungesehene Stufe."
            ),
            "sample_size": 23_575,
            "expectancy": 0.0446,
            "profit_factor": 1.072,
            "in_sample": fibonacci,
            "validation": {"status": "NOT_RUN"},
            "out_of_sample": {"status": "NOT_RUN"},
            "walk_forward": {"status": "NOT_RUN"},
            "forward": {"status": "NOT_RUN"},
            "papertrade": {"status": "NOT_RUN"},
        },
        result_reference=fib_path,
        artifact_references=(
            _artifact_reference(
                system="swing_broad_v1",
                record_type="fibonacci_contract_reuse",
                record_id=str(fibonacci["artifact_fingerprint"]),
                path=fib_path,
            ),
            _artifact_reference(
                system="swing_broad_v1",
                record_type="reviewed_method_audit",
                record_id="2026-08-25-v3-reviewed",
                path=FIB_AUDIT_JSON,
            ),
        ),
        completed_at=timestamp,
    )
    fx_completed = complete_request(
        workflow,
        FX_CARRY_REQUEST_ID,
        result={
            "title": "FX Carry-to-Risk – Point-in-Time-Datenpipeline",
            "conclusion": "inconclusive",
            "interpretation": (
                "Paar-, Inversions-, Zeit-, Verfügbarkeits- und Revisionsvertrag sind gebaut. "
                "Lokale historische Erwartungen, Pre-Release-Konsense und Vintages fehlen; "
                "deshalb wurden weder Werte approximiert noch ein Research-Test gestartet."
            ),
            "sample_size": 0,
            "in_sample": fx,
            "validation": {"status": "NOT_RUN"},
            "out_of_sample": {"status": "NOT_RUN"},
            "walk_forward": {"status": "NOT_RUN"},
            "forward": {"status": "NOT_RUN"},
            "papertrade": {"status": "NOT_RUN"},
        },
        result_reference=fx_path,
        artifact_references=(
            _artifact_reference(
                system="fx_carry_pit",
                record_type="coverage_report",
                record_id=str(fx["artifact_fingerprint"]),
                path=fx_path,
            ),
        ),
        completed_at=timestamp,
    )
    baseline = dict(failed_result.get("baseline") or {})
    failed_completed = complete_request(
        workflow,
        FAILED_SELLER_REQUEST_ID,
        result={
            "title": "Failed Seller Attempts – kausaler Development-Featuretest",
            "conclusion": "inconclusive",
            "interpretation": (
                "Die vier vorab gespeicherten Einzelvarianten wurden nur im Development "
                "ausgewertet. Unverifizierte Issuer-Abhängigkeiten verhindern eine belastbare "
                "Evidenzfreigabe; Kombinationen, Validation und Strategieaktivierung bleiben gesperrt."
            ),
            "sample_size": int(failed_result.get("valid_feature_n") or 0),
            "hit_rate": baseline.get("hit_rate_pct"),
            "expectancy": baseline.get("expectancy_r"),
            "profit_factor": baseline.get("profit_factor"),
            "mfe": baseline.get("average_mfe_pct"),
            "mae": baseline.get("average_mae_pct"),
            "in_sample": failed_result,
            "validation": {"status": "NOT_RUN"},
            "out_of_sample": {"status": "NOT_RUN"},
            "walk_forward": {"status": "NOT_RUN"},
            "forward": {"status": "NOT_RUN"},
            "papertrade": {"status": "NOT_RUN"},
        },
        result_reference=failed_seller_report,
        artifact_references=(
            _artifact_reference(
                system="failed_seller_research",
                record_type="development_only_run",
                record_id=str(failed.get("run_id")),
                path=failed_seller_report,
            ),
        ),
        completed_at=timestamp,
    )

    gold = _request_state(knowledge_base, GOLD_SILVER_REQUEST_ID)
    water = _request_state(knowledge_base, WATER_REQUEST_ID)
    if gold["current_status"] != "READY" or water["current_status"] != "READY":
        raise RuntimeError("Gold/Silver or Water work request was changed unexpectedly.")

    final = {
        "status": "PREREQUISITES_COMPLETED_NO_SCAN",
        "completed_at": timestamp,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit_hash_at_execution": _git("rev-parse", "HEAD"),
        "identity_gate": identity,
        "work_requests": {
            FIBONACCI_REQUEST_ID: {
                "status": fib_completed["current_status"],
                "result_id": fib_completed.get("result_id"),
            },
            FX_CARRY_REQUEST_ID: {
                "status": fx_completed["current_status"],
                "result_id": fx_completed.get("result_id"),
            },
            FAILED_SELLER_REQUEST_ID: {
                "status": failed_completed["current_status"],
                "result_id": failed_completed.get("result_id"),
            },
        },
        "untouched_ready_requests": {
            GOLD_SILVER_REQUEST_ID: gold["current_status"],
            WATER_REQUEST_ID: water["current_status"],
        },
        "failed_seller_feature_contract_fingerprint": failed_seller_feature_contract()[
            "feature_contract_fingerprint"
        ],
        "multi_asset_scan_started": False,
        "strategy_activated": False,
        "unseen_stage_opened": False,
        "broker_accessed": False,
    }
    return _write_artifact(final_path, final)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-base", type=Path, default=DEFAULT_KB)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--fx-database", type=Path, default=DEFAULT_FX_CARRY_DB_PATH)
    parser.add_argument("--failed-seller-report", type=Path, default=DEFAULT_FAILED_REPORT)
    parser.add_argument("--at")
    args = parser.parse_args()
    output = complete_all(
        knowledge_base=args.knowledge_base,
        export_root=args.export_root,
        fx_database=args.fx_database,
        failed_seller_report=args.failed_seller_report,
        completed_at=args.at,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
