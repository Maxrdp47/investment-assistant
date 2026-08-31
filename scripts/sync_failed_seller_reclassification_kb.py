from __future__ import annotations

"""Link a read-only Failed-Seller dependency assessment to its immutable KB result."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import ResearchKnowledgeBase  # noqa: E402


RESULT_ID = "07f46840-35e1-41f4-949c-264c7cf08fbe"
ORIGINAL_RUN_ID = "failed-seller-7d9cb30f0ca866ac752c6759c965af94"
DEFAULT_KB = PROJECT_ROOT / "runtime" / "research_knowledge.sqlite3"
DEFAULT_RECLASSIFICATION = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "failed_seller_dependency_reclassification_2026-08-30-v2.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "failed_seller_dependency_reclassification_kb_sync_2026-08-31-v1.json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _result_core(result: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"references", "validation_assessments", "work_request_links"}
    }


def sync_reference(
    knowledge: ResearchKnowledgeBase,
    *,
    payload: Mapping[str, object],
    artifact_path: Path,
    created_at: str,
) -> dict[str, object]:
    if payload.get("status") != "COMPLETED_READ_ONLY_RECLASSIFICATION":
        raise RuntimeError("Failed-Seller reclassification is not complete.")
    if payload.get("original_run_id") != ORIGINAL_RUN_ID:
        raise RuntimeError("Failed-Seller reclassification references the wrong original run.")
    if payload.get("raw_metrics_changed") is not False:
        raise RuntimeError("Failed-Seller raw metrics were not preserved.")

    before = knowledge.get_result(RESULT_ID)
    core_before = _result_core(before)
    record_id = str(payload["reclassification_id"])
    existing = [
        item
        for item in before.get("references", [])
        if item.get("system") == "failed_seller_dependency_reclassification"
        and item.get("record_type") == "read_only_dependency_assessment"
        and item.get("record_id") == record_id
    ]
    inserted = 0
    if not existing:
        knowledge.add_external_reference(
            target_type="result",
            target_id=RESULT_ID,
            system="failed_seller_dependency_reclassification",
            record_type="read_only_dependency_assessment",
            record_id=record_id,
            uri=str(artifact_path.resolve()),
            description=(
                "Versionierte read-only Dependency-/Effective-N-Neueinordnung; "
                "Rohmetriken und INCONCLUSIVE-Ergebnis bleiben unverändert."
            ),
            created_at=created_at,
        )
        inserted = 1

    after = knowledge.get_result(RESULT_ID)
    core_after = _result_core(after)
    if core_before != core_after:
        raise RuntimeError("Immutable Failed-Seller result changed during KB sync.")
    return {
        "result_id": RESULT_ID,
        "result_core_fingerprint_before": _fingerprint(core_before),
        "result_core_fingerprint_after": _fingerprint(core_after),
        "result_core_unchanged": True,
        "reference_inserted": inserted,
        "reference_deduplicated": int(not inserted),
        "reference_record_id": record_id,
    }


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach Failed-Seller dependency assessment to the immutable KB result"
    )
    parser.add_argument("--knowledge-db", type=Path, default=DEFAULT_KB)
    parser.add_argument("--reclassification", type=Path, default=DEFAULT_RECLASSIFICATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--at")
    args = parser.parse_args()
    created_at = args.at or datetime.now(timezone.utc).isoformat()
    payload = json.loads(args.reclassification.read_text(encoding="utf-8"))
    sync = sync_reference(
        ResearchKnowledgeBase(args.knowledge_db),
        payload=payload,
        artifact_path=args.reclassification,
        created_at=created_at,
    )
    result: dict[str, object] = {
        "version": "failed-seller-reclassification-kb-sync-2026.08.31-v1",
        "status": "COMPLETED_APPEND_ONLY_REFERENCE_SYNC",
        "created_at": created_at,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": _git("rev-parse", "HEAD"),
        "command": "python " + " ".join(sys.argv),
        "reclassification_id": payload["reclassification_id"],
        "reclassification_output_digest": payload["output_digest"],
        "sync": sync,
        "raw_metrics_changed": False,
        "new_research_attempts": 0,
        "validation_opened": False,
        "holdout_opened": False,
        "strategy_activated": False,
        "multi_asset_scan_started": False,
    }
    result["output_digest"] = _fingerprint(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if existing.get("reclassification_id") != result["reclassification_id"]:
            raise RuntimeError("KB sync artifact path already contains another assessment.")
        result = existing
    else:
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
