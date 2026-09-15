from __future__ import annotations

"""Prepare and run the finite R1 water-infrastructure research chain."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import ResearchWorkflow  # noqa: E402
from swing_run_lock import SwingRunLock  # noqa: E402
from swing_walk_forward_campaign import (  # noqa: E402
    historical_research_runtime_gate,
    load_campaign_config,
)
from water_infrastructure_research import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    STAGES,
    file_sha256,
    freeze_research_contract,
    load_contract,
    persist_stage,
    read_price_snapshot,
    store_status,
    write_append_only_artifact,
    write_price_snapshot,
)


DEFAULT_KB_PATH = PROJECT_ROOT / "runtime" / "research_knowledge.sqlite3"
WORKER_CONTEXT = "finite-research-program-2026-09-15-v1:R1"
CLAIM_TOKEN = "finite-research-program-2026-09-15-v1:R1:water-v1"


def _path(contract: dict[str, object], key: str) -> Path:
    value = Path(str(dict(contract["runtime"])[key]))
    return value if value.is_absolute() else PROJECT_ROOT / value


def _artifact_path(contract: dict[str, object], name: str) -> Path:
    return _path(contract, "artifact_root") / name


def _runtime_gate() -> dict[str, object]:
    gate = historical_research_runtime_gate(load_campaign_config(), project_root=PROJECT_ROOT)
    if gate.get("run_allowed") is not True:
        raise RuntimeError("Historical research runtime gate blocked R1: " + json.dumps(gate, sort_keys=True))
    return gate


def _download(contract: dict[str, object]) -> dict[str, object]:
    data = dict(contract["data"])
    yf.set_tz_cache_location(str(PROJECT_ROOT / ".yfinance-cache"))
    frames = {}
    for ticker in data["symbols"]:
        frame = yf.download(
            str(ticker),
            start=str(data["start"]),
            end=str(data["end_exclusive"]),
            interval=str(data["interval"]),
            auto_adjust=bool(data["auto_adjust"]),
            repair=bool(data["repair"]),
            keepna=bool(data["keepna"]),
            actions=False,
            progress=False,
            threads=False,
            multi_level_index=False,
        )
        if frame.empty:
            raise RuntimeError(f"Yahoo Finance returned no data for {ticker}.")
        frames[str(ticker)] = frame
    return frames


def prepare_dataset(contract: dict[str, object]) -> dict[str, object]:
    _runtime_gate()
    frames = _download(contract)
    manifest = write_price_snapshot(
        frames,
        contract=contract,
        path=_path(contract, "dataset_store"),
    )
    manifest.pop("idempotent_replay", None)
    return write_append_only_artifact(_artifact_path(contract, "dataset_manifest.json"), manifest)


def _claim(workflow: ResearchWorkflow, contract: dict[str, object], timestamp: str) -> dict[str, object]:
    request_id = str(dict(contract["knowledge_base"])["work_request_id"])
    current = workflow.get_work_request(request_id, include_context=False)
    if current["current_status"] == "COMPLETED":
        return {**current, "idempotent_replay": True}
    return workflow.claim_work_request(
        request_id,
        worker_context=WORKER_CONTEXT,
        claim_token=CLAIM_TOKEN,
        claimed_at=timestamp,
    )


def _artifact_reference(path: Path, *, record_type: str, record_id: str) -> dict[str, object]:
    return {
        "system": "water_infrastructure_research",
        "record_type": record_type,
        "record_id": record_id,
        "uri": str(path.resolve()),
        "description": "Finite R1 append-only research evidence",
    }


def _complete_kb(
    workflow: ResearchWorkflow,
    contract: dict[str, object],
    claim: dict[str, object],
    terminal_review: dict[str, object],
    reports: dict[str, dict[str, object]],
    completed_at: str,
) -> dict[str, object]:
    request_id = str(dict(contract["knowledge_base"])["work_request_id"])
    decision = str(terminal_review["decision"])
    if decision == "HOLDOUT_PASS":
        conclusion = "supports"
    elif decision.endswith("_FAIL"):
        conclusion = "negative"
    else:
        conclusion = "inconclusive"
    development = reports.get("development") or {}
    treatment = dict(development.get("treatment") or {})
    validation = reports.get("validation") or {"status": "NOT_RUN"}
    holdout = reports.get("holdout") or {"status": "NOT_RUN"}
    result = {
        "title": "Wasser-Infrastruktur: Korrektur-plus-Breakout, endlicher R1-Versuch",
        "conclusion": conclusion,
        "interpretation": (
            "Die unveränderte 15%-/60-Sitzungs-Primärregel wurde mit XYL, BMI und PNR "
            "sowie SPY/PHO-, Matched-Control-, Buy-and-Hold- und Korbkontrollen geprüft. "
            f"Terminale Entscheidung: {decision}. Ein Fail oder Underpowered-Resultat wird nicht retuned."
        ),
        "sample_size": int(treatment.get("n") or 0),
        "hit_rate": treatment.get("hit_rate"),
        "expectancy": treatment.get("mean"),
        "profit_factor": treatment.get("profit_factor"),
        "drawdown": treatment.get("max_sequence_drawdown"),
        "costs": dict(contract["costs"]),
        "slippage": {
            "included_in_one_way_bps": True,
            "equity_one_way_bps": dict(contract["costs"])["equity_one_way_bps"],
            "etf_one_way_bps": dict(contract["costs"])["etf_one_way_bps"],
        },
        "in_sample": development,
        "validation": validation,
        "out_of_sample": holdout,
        "walk_forward": dict(development.get("year_stability") or {}),
        "forward": {"status": "NOT_RUN_NOT_AUTHORIZED"},
        "papertrade": {"status": "NOT_RUN_NOT_AUTHORIZED"},
    }
    references = []
    for stage, report in reports.items():
        path = _artifact_path(contract, f"{stage}_review.json")
        references.append(
            _artifact_reference(path, record_type=f"{stage}_review", record_id=str(report["review_fingerprint"]))
        )
    references.append(
        _artifact_reference(
            _artifact_path(contract, "contract_freeze.json"),
            record_type="contract_freeze",
            record_id=str(contract["version"]),
        )
    )
    return workflow.complete_work_request(
        request_id,
        claim_token=str(claim["claim_token"]),
        worker_context=WORKER_CONTEXT,
        result=result,
        result_reference=str(_artifact_path(contract, f"{str(terminal_review['stage'])}_review.json").resolve()),
        artifact_references=references,
        completed_at=completed_at,
    )


def run_auto(contract: dict[str, object], *, knowledge_base: Path = DEFAULT_KB_PATH) -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).isoformat()
    _runtime_gate()
    frames, manifest = read_price_snapshot(_path(contract, "dataset_store"), contract)
    freeze = freeze_research_contract(
        _path(contract, "result_store"),
        contract=contract,
        dataset_manifest=manifest,
        code_fingerprint=file_sha256(PROJECT_ROOT / "water_infrastructure_research.py"),
        frozen_at=timestamp,
    )
    freeze.pop("idempotent_replay", None)
    write_append_only_artifact(_artifact_path(contract, "contract_freeze.json"), freeze)
    workflow = ResearchWorkflow(knowledge_base)
    claim = _claim(workflow, contract, timestamp)
    if claim.get("current_status") == "COMPLETED":
        return {"status": "TERMINAL_NO_OP", "work_request": claim, "store": store_status(_path(contract, "result_store"))}
    reports: dict[str, dict[str, object]] = {}
    for stage in STAGES:
        if stage == "validation" and reports["development"]["decision"] != "DEVELOPMENT_PASS":
            break
        if stage == "holdout" and reports["validation"]["decision"] != "VALIDATION_PASS":
            break
        _runtime_gate()
        report = persist_stage(
            _path(contract, "result_store"),
            frames=frames,
            contract=contract,
            stage=stage,
            run_at=datetime.now(timezone.utc).isoformat(),
        )
        report.pop("idempotent_replay", None)
        reports[stage] = report
        write_append_only_artifact(_artifact_path(contract, f"{stage}_review.json"), report)
        if report["decision"] not in {"DEVELOPMENT_PASS", "VALIDATION_PASS", "HOLDOUT_PASS"}:
            break
        if report["decision"] == "HOLDOUT_PASS":
            break
    terminal = reports[next(reversed(reports))]
    completed = _complete_kb(
        workflow,
        contract,
        claim,
        terminal,
        reports,
        datetime.now(timezone.utc).isoformat(),
    )
    return {
        "status": terminal["decision"],
        "reports": reports,
        "work_request": {
            "id": completed["id"],
            "status": completed["current_status"],
            "result_id": completed.get("result_id"),
        },
        "store": store_status(_path(contract, "result_store")),
        "safety": {
            "external_opened": False,
            "forward_opened": False,
            "paper_opened": False,
            "shadow_opened": False,
            "broker_opened": False,
            "orders_opened": False,
            "production_opened": False,
        },
    }


def _with_locks(contract: dict[str, object], function):
    process = SwingRunLock(_path(contract, "process_lock"))
    global_research = SwingRunLock(_path(contract, "global_research_lock"))
    with process:
        with global_research:
            _runtime_gate()
            return function()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "status"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--knowledge-base", type=Path, default=DEFAULT_KB_PATH)
    args = parser.parse_args()
    contract = load_contract(args.config)
    if args.command == "prepare":
        result = _with_locks(contract, lambda: prepare_dataset(contract))
    elif args.command == "run":
        result = _with_locks(contract, lambda: run_auto(contract, knowledge_base=args.knowledge_base))
    else:
        result = {
            "dataset_exists": _path(contract, "dataset_store").exists(),
            "result_store": store_status(_path(contract, "result_store")),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
