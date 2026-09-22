from __future__ import annotations

"""Idempotently archive the preregistered R6 no-candidate result in the KB."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multi_asset_v2_r6_review import COMPLETION_SUMMARY, DESCRIPTIVE_REPORT, FINAL_AUDIT  # noqa: E402
from multi_asset_v2_r6_runner import R6_MANIFEST, R6_REVIEW_CONTRACT, verify_self_fingerprint  # noqa: E402
from research_knowledge import ResearchKnowledgeBase  # noqa: E402


DEFAULT_KB = ROOT / "runtime" / "research_knowledge.sqlite3"
HYPOTHESIS_TITLE = "Multi-Asset Discovery v2 – robuste Einzelfeature-Assoziation"
HYPOTHESIS_CLAIM = (
    "Im eingefrorenen Development-v2-Scope erfüllt mindestens ein vorab benanntes "
    "Einzelfeature alle kanonischen Quality-C-Dimensionen und ist als einfacher "
    "Challenger freeze-fähig."
)
EXPERIMENT_TITLE = "R6 Discovery v2 – präregistrierter Einzelfeature-Development-Review"


def _load_verified(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not verify_self_fingerprint(payload):
        raise RuntimeError(f"Invalid R6 artifact fingerprint: {path}")
    return payload


def _one_by_title(kb_path: Path, table: str, title: str) -> dict[str, Any] | None:
    with sqlite3.connect(kb_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT * FROM {table} WHERE title=? ORDER BY rowid", (title,)
        ).fetchall()
    if len(rows) > 1:
        raise RuntimeError(f"Duplicate archival KB record: {table}/{title}")
    return dict(rows[0]) if rows else None


def sync(
    *,
    kb_path: Path = DEFAULT_KB,
    audit_path: Path = FINAL_AUDIT,
    report_path: Path = DESCRIPTIVE_REPORT,
    summary_path: Path = COMPLETION_SUMMARY,
    manifest_path: Path = R6_MANIFEST,
    review_contract_path: Path = R6_REVIEW_CONTRACT,
) -> dict[str, object]:
    audit = _load_verified(audit_path)
    report = _load_verified(report_path)
    summary = _load_verified(summary_path)
    manifest = _load_verified(manifest_path)
    contract = json.loads(review_contract_path.read_text(encoding="utf-8"))
    if (
        audit.get("status") != "PASS"
        or report.get("status") != "R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE"
        or summary.get("status") != "R6_COMPLETE_NO_ROBUST_CANDIDATES_R7_NOT_OPENED"
        or int(report.get("robust_candidate_count", -1)) != 0
    ):
        raise RuntimeError("R6 is not eligible for terminal archival KB synchronization.")
    kb = ResearchKnowledgeBase(kb_path)
    existing_hypothesis = _one_by_title(kb_path, "hypotheses", HYPOTHESIS_TITLE)
    if existing_hypothesis is None:
        hypothesis = kb.create_hypothesis(
            title=HYPOTHESIS_TITLE,
            area="opportunity_scanner",
            category="multi_asset_discovery",
            claim=HYPOTHESIS_CLAIM,
            mechanism=(
                "Kausale Preis-, Relative-Strength-, Struktur-, Volatilitäts- und "
                "Liquiditätsmerkmale könnten spätere Aufwärts-/Risikopfade unterscheiden."
            ),
            external_evidence="weak",
            rating="B",
            risks_limitations=(
                "Archivaler KB-Spiegel eines zuvor dateibasiert eingefrorenen Vertrags; "
                "Survivorship unbekannt, historische Issuer-Dependencies Effective N = 0, "
                "fehlende PIT-Familien bleiben Shadow/Unavailable. Kein Tradingfilter."
            ),
            status="REJECTED",
            strategy="descriptive multi-asset opportunity discovery",
            asset_class="EQUITIES/ETF/CRYPTO",
            creation_reason=(
                "Nachträgliche transparente Katalogisierung des vor Ergebnissichtung in "
                "R5/R6 dateibasiert eingefrorenen Versuchs; keine neue Hypothese."
            ),
        )
    else:
        hypothesis = kb.get_hypothesis(str(existing_hypothesis["id"]), include_details=False)
        if hypothesis["claim"] != HYPOTHESIS_CLAIM:
            raise RuntimeError("Existing R6 archival hypothesis has a different claim.")
    existing_experiment = _one_by_title(kb_path, "experiments", EXPERIMENT_TITLE)
    if existing_experiment is None:
        experiment = kb.create_experiment(
            str(hypothesis["id"]),
            title=EXPERIMENT_TITLE,
            test_definition=(
                "31 vorab benannte Einzelfeatures gegen getrennte 20/60/120/252-"
                "Return-/MFE-/MAE-Populationen; keine Schwellen, Kombinationen oder "
                "Profit-Rangfolge. Der maßgebliche Freeze liegt in den referenzierten "
                "R5/R6-Artefakten und zeitlich vor der Ergebnissichtung."
            ),
            features=[str(item["name"]) for item in contract["continuous_features"]],
            data_universe="Frozen EQUITIES/ETF/CRYPTO Development scope, 2016-2021",
            point_in_time_rules=(
                "Nur bis einschließlich abgeschlossener Signalkerze bekannte Werte; "
                "Unknown bleibt missing und wird nie zu False/0."
            ),
            baseline="unveränderte v7-r2 Development-Grundpopulation",
            parameters={
                "program_id": manifest["program_id"],
                "run_id": manifest["run_id"],
                "r5_contract_fingerprint": manifest["development_contract_fingerprint"],
                "review_contract_fingerprint": manifest["review_contract_fingerprint"],
                "run_manifest_fingerprint": manifest["run_manifest_fingerprint"],
                "archival_catalog_created_after_result": True,
            },
            test_status="COMPLETED",
            period_start="2016-01-01",
            period_end="2021-12-31",
        )
    else:
        experiment = kb.get_experiment(str(existing_experiment["id"]))
        if str(experiment["hypothesis_id"]) != str(hypothesis["id"]):
            raise RuntimeError("Existing R6 archival experiment belongs to another hypothesis.")
    result = kb.record_result(
        str(experiment["id"]),
        title="R6 Discovery v2 – kein robuster Quality-C-Kandidat",
        conclusion="inconclusive",
        interpretation=(
            "Der vollständige präregistrierte Development-Review erzeugte keinen "
            "freeze-fähigen Kandidaten. Die harte Quality-C-Grenze war historisch "
            "verifizierte Issuer-Dependencies Effective N = 0. Deskriptive "
            "Assoziationen sind weder Validation noch Handels- oder Produktionsevidenz."
        ),
        sample_size=int(report["cases_reviewed"]),
        in_sample={
            "scope": "previously_seen_development_only",
            "run_id": manifest["run_id"],
            "features": int(report["feature_count"]),
            "robust_candidates": 0,
            "candidate_gate_reason": report["candidate_gate_reason"],
            "audit_fingerprint": audit["artifact_fingerprint"],
            "report_fingerprint": report["artifact_fingerprint"],
            "completion_fingerprint": summary["artifact_fingerprint"],
        },
        validation=None,
        out_of_sample=None,
        walk_forward=None,
        forward=None,
        papertrade=None,
        costs=None,
        slippage=None,
        idempotency_key=(
            f"{manifest['program_id']}:R6:{report['artifact_fingerprint']}"
        ),
    )
    references = [
        ("r6_final_audit", audit_path, audit["artifact_fingerprint"]),
        ("r6_descriptive_report", report_path, report["artifact_fingerprint"]),
        ("r6_completion_summary", summary_path, summary["artifact_fingerprint"]),
        ("r6_run_manifest", manifest_path, manifest["artifact_fingerprint"]),
    ]
    existing_refs = {
        (item["record_type"], item["record_id"]) for item in result.get("references") or []
    }
    for record_type, path, record_id in references:
        if (record_type, record_id) in existing_refs:
            continue
        kb.add_external_reference(
            target_type="result",
            target_id=str(result["id"]),
            system="finite_research_program",
            record_type=record_type,
            record_id=str(record_id),
            uri=str(path.resolve()),
            description="Immutable R6 Development evidence; Validation/Holdout unopened.",
        )
    return {
        "hypothesis_id": hypothesis["id"],
        "hypothesis_status": hypothesis["current_status"],
        "experiment_id": experiment["id"],
        "experiment_status": experiment["current_status"],
        "result_id": result["id"],
        "result_conclusion": result["conclusion"],
        "idempotent_replay": bool(result.get("idempotent_replay")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-base", type=Path, default=DEFAULT_KB)
    args = parser.parse_args()
    print(json.dumps(sync(kb_path=args.knowledge_base), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
