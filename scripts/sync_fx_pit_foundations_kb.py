from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fx_pit_collector import DEFAULT_COLLECTOR_DB_PATH, fx_pit_collector_audit  # noqa: E402
from research_knowledge import (  # noqa: E402
    DEFAULT_DATABASE_PATH,
    ResearchKnowledgeBase,
    ResearchWorkflow,
)


WORK_REQUEST_ID = "1f6201fe-2cbd-4fc1-9bf1-291a4221bdfa"
HYPOTHESIS_ID = "0a6350d5-718f-437d-97c1-f484fb8e11bf"
EXPERIMENT_ID = "793d4731-4de5-4c16-a7f3-dd44dea1761c"
RESULT_ID = "a4c0b1c7-ab1d-4802-bfc6-48d869843cb6"
DEFAULT_IDENTITY_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "research_identity_registry_2026-08-29-v1.json"
)
DEFAULT_HISTORICAL_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "fx_historical_pit_2026-08-29-v1.json"
)
DEFAULT_EXPORT_PATH = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "fx_pit_foundations_kb_completion_2026-08-29-v1.json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_artifact(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _latest_collector_run(path: Path) -> dict[str, object]:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT run_json FROM collector_runs ORDER BY started_at DESC, run_id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise RuntimeError("Kein FX-PIT-Collector-Pilot vorhanden.")
    return json.loads(str(row[0]))


def sync_references(
    *,
    knowledge: ResearchKnowledgeBase,
    workflow: ResearchWorkflow,
    references: list[Mapping[str, object]],
    created_at: str,
) -> dict[str, object]:
    request = workflow.get_work_request(WORK_REQUEST_ID, include_context=False)
    experiment = knowledge.get_experiment(EXPERIMENT_ID)
    result = knowledge.get_result(RESULT_ID)
    if request["current_status"] != "COMPLETED" or request.get("result_id") != RESULT_ID:
        raise RuntimeError("FX-Carry-Work-Request ist nicht mit dem kanonischen Resultat abgeschlossen.")
    if request.get("hypothesis_id") != HYPOTHESIS_ID or request.get("experiment_id") != EXPERIMENT_ID:
        raise RuntimeError("FX-Carry-KB-IDs stimmen nicht mit dem Vertrag überein.")
    if experiment["current_status"] != "COMPLETED" or result["experiment_id"] != EXPERIMENT_ID:
        raise RuntimeError("FX-Carry-Experiment/Resultat ist inkonsistent.")

    existing = {
        (
            str(item["system"]),
            str(item["record_type"]),
            str(item["record_id"]),
        )
        for item in result.get("references", [])
    }
    inserted = deduplicated = 0
    for reference in references:
        key = (
            str(reference["system"]),
            str(reference["record_type"]),
            str(reference["record_id"]),
        )
        if key in existing:
            deduplicated += 1
            continue
        knowledge.add_external_reference(
            target_type="result",
            target_id=RESULT_ID,
            system=key[0],
            record_type=key[1],
            record_id=key[2],
            uri=str(reference.get("uri") or "") or None,
            description=str(reference.get("description") or ""),
            created_at=created_at,
        )
        inserted += 1
        existing.add(key)
    return {
        "work_request_status": request["current_status"],
        "experiment_status": experiment["current_status"],
        "result_conclusion_unchanged": result["conclusion"],
        "result_sample_size_unchanged": result["sample_size"],
        "references_inserted": inserted,
        "references_deduplicated": deduplicated,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FX-PIT-Grundlagen an bestehendes KB-Resultat anhängen")
    parser.add_argument("--knowledge-db", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY_ARTIFACT)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL_ARTIFACT)
    parser.add_argument("--collector-db", type=Path, default=DEFAULT_COLLECTOR_DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT_PATH)
    parser.add_argument("--at")
    args = parser.parse_args()
    created_at = args.at or datetime.now(timezone.utc).isoformat()
    identity = _load_artifact(args.identity)
    historical = _load_artifact(args.historical)
    collector_run = _latest_collector_run(args.collector_db)
    collector_audit = fx_pit_collector_audit(args.collector_db)
    if collector_audit["status"] != "ok":
        raise RuntimeError("FX-PIT-Collector-Audit ist nicht in Ordnung.")
    references = [
        {
            "system": "research_identity_v3",
            "record_type": "registry_coverage_artifact",
            "record_id": identity["artifact_fingerprint"],
            "uri": str(args.identity),
            "description": "Versioniertes Issuer-/Listing-Register; unbekannte Zuordnungen bleiben sichtbar und zählen nicht als unabhängig.",
        },
        {
            "system": "fx_historical_pit",
            "record_type": "coverage_artifact",
            "record_id": historical["artifact_fingerprint"],
            "uri": str(args.historical),
            "description": "Historische FX-Tagespreise und ehrliche Coverage-Matrix; Erwartungen/Vintages/BidAsk bleiben unverfügbar.",
        },
        {
            "system": "fx_pit_observer",
            "record_type": "collector_pilot_run",
            "record_id": collector_run["run_id"],
            "uri": str(args.collector_db),
            "description": "Append-only FX-PIT-Observer-Pilot; reine Datensammlung ohne Strategie, Trades oder Broker.",
        },
    ]
    sync = sync_references(
        knowledge=ResearchKnowledgeBase(args.knowledge_db),
        workflow=ResearchWorkflow(args.knowledge_db),
        references=references,
        created_at=created_at,
    )
    payload: dict[str, object] = {
        "status": "PIPELINE_READY_WITH_PARTIAL_COVERAGE",
        "created_at": created_at,
        "work_request_id": WORK_REQUEST_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "experiment_id": EXPERIMENT_ID,
        "result_id": RESULT_ID,
        "sync": sync,
        "identity": {
            "artifact_fingerprint": identity["artifact_fingerprint"],
            "verified_issuer_mapping_n": identity["verified_issuer_mapping_n"],
            "unresolved_mapping_n": identity["unresolved_mapping_n"],
        },
        "historical_fx": {
            "artifact_fingerprint": historical["artifact_fingerprint"],
            "record_n": historical["inventory"]["record_n"],
            "period_start": historical["inventory"]["period_start"],
            "period_end": historical["inventory"]["period_end"],
        },
        "collector": {
            "run_id": collector_run["run_id"],
            "status": collector_run["status"],
            "audit": collector_audit,
        },
        "historical_result_rewritten": False,
        "research_test_started": False,
        "strategy_activated": False,
        "multi_asset_scan_started": False,
    }
    payload["artifact_fingerprint"] = _fingerprint(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
