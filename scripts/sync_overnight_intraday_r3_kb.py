from __future__ import annotations

"""Idempotently link the completed, descriptive R3 review to the Knowledge Base."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from overnight_intraday_r3 import DEFAULT_CONTRACT, digest, load_contract, project_path  # noqa: E402
from research_knowledge import ResearchKnowledgeBase  # noqa: E402


DEFAULT_KB = ROOT / "runtime" / "research_knowledge.sqlite3"


def verified_review(contract: dict, contract_fingerprint: str, store_path: Path) -> tuple[dict, str]:
    with sqlite3.connect(f"file:{store_path.as_posix()}?mode=ro", uri=True) as store:
        if store.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("R3 result store integrity failed")
        if store.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("R3 result store foreign keys failed")
        manifest = store.execute(
            "SELECT contract_fingerprint,source_dataset_fingerprint FROM run_manifest WHERE version=?",
            (contract["version"],),
        ).fetchone()
        if manifest != (contract_fingerprint, contract["source"]["dataset_fingerprint"]):
            raise RuntimeError("R3 frozen manifest mismatch")
        row = store.execute(
            "SELECT review_json,review_digest FROM final_review WHERE version=?",
            (contract["version"],),
        ).fetchone()
        if row is None:
            raise RuntimeError("R3 review is not complete")
        review = json.loads(row[0])
        if digest(review) != row[1]:
            raise RuntimeError("R3 review digest mismatch")
        completed = store.execute("SELECT COUNT(*) FROM asset_progress").fetchone()[0]
        source_bars = store.execute("SELECT SUM(source_bar_count) FROM asset_progress").fetchone()[0]
        if completed != review["source_assets"] or source_bars != review["source_bars"]:
            raise RuntimeError("R3 review does not cover completed source assets")
    if (
        review["status"] != "DEVELOPMENT_DESCRIPTIVE_ONLY_SEEN_DATA"
        or review["validation"] != "NOT_OPENED"
        or review["holdout"] != "NOT_OPENED"
        or review["robust_challenger_eligible"] is not False
    ):
        raise RuntimeError("R3 review violates the frozen safety gate")
    return review, row[1]


def sync(contract_path: Path = DEFAULT_CONTRACT, *, kb_path: Path = DEFAULT_KB) -> dict:
    contract, fingerprint = load_contract(contract_path)
    store_path = project_path(contract["runtime"]["result_store"])
    review, review_digest = verified_review(contract, fingerprint, store_path)
    kb = ResearchKnowledgeBase(kb_path)
    experiment_id = contract["knowledge_base_experiment_id"]
    experiment = kb.get_experiment(experiment_id)
    if experiment["current_status"] not in {"PLANNED", "RUNNING", "COMPLETED"}:
        raise RuntimeError("Unexpected R3 Knowledge Base experiment state")
    horizon_stats = review["development"]
    result = kb.record_result(
        experiment_id,
        title="R3 Overnight-Bias, eingefrorener deskriptiver Development-Versuch",
        conclusion="negative",
        interpretation=(
            "Der vorab festgelegte 20-Sitzungs-Overnight-Bias zeigt gegenüber der "
            "einfachen Close-to-Close-Baseline in bereits gesehenen Development-Jahren "
            "keinen stabilen inkrementellen Zusammenhang. Die Jahrrichtung wechselt, "
            "historische Dependencies und damit das unabhängige Effective N sind ungeklärt. "
            "Dies ist kein allgemeiner Beweis gegen Overnight-Effekte und keine "
            "Validation-, Holdout- oder handelbare Strategie-Evidenz."
        ),
        sample_size=None,
        in_sample={
            "scope": "previously_seen_development_only",
            "source_assets": review["source_assets"],
            "source_bars": review["source_bars"],
            "horizons": horizon_stats,
            "effective_n": review["effective_n"],
            "contract_fingerprint": fingerprint,
            "review_digest": review_digest,
        },
        validation=None,
        out_of_sample=None,
        walk_forward=None,
        forward=None,
        papertrade=None,
        costs=None,
        slippage=None,
        idempotency_key=f"{contract['program_id']}:R3:{review_digest}",
    )
    reference_key = ("overnight_intraday_r3", "append_only_development_review", review_digest)
    references = result.get("references") or []
    if not any(
        (item.get("system"), item.get("record_type"), item.get("record_id")) == reference_key
        for item in references
    ):
        kb.add_external_reference(
            target_type="result",
            target_id=result["id"],
            system=reference_key[0],
            record_type=reference_key[1],
            record_id=reference_key[2],
            uri=str(store_path),
            description="Append-only R3 Development review; Validation/Holdout unopened.",
        )
    if experiment["current_status"] != "COMPLETED":
        kb.change_experiment_status(
            experiment_id,
            "COMPLETED",
            reason="Einzelner R3-Development-Versuch deskriptiv abgeschlossen; kein Challenger, keine Validation/Holdout-Freigabe.",
        )
    return {
        "experiment_id": experiment_id,
        "result_id": result["id"],
        "idempotent_replay": bool(result.get("idempotent_replay")),
        "conclusion": result["conclusion"],
        "review_digest": review_digest,
        "experiment_status": "COMPLETED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--knowledge-base", type=Path, default=DEFAULT_KB)
    args = parser.parse_args()
    print(json.dumps(sync(args.contract, kb_path=args.knowledge_base), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
