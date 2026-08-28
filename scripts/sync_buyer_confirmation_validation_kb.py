from __future__ import annotations

"""Idempotently link the frozen Buyer Confirmation run to the research KB."""

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import ResearchKnowledgeBase, ResearchWorkflow  # noqa: E402


HYPOTHESIS_ID = "9f8b5cc4-ecb1-4769-81be-8e3826592bf5"
EXPERIMENT_TITLE = "Buyer Confirmation v1 – Frozen Validation/Holdout"
WORK_REQUEST_KEY = "buyer-confirmation-objective-pullback-v1:unseen-evaluation"
CLAIM_TOKEN = "buyer-confirmation-objective-pullback-v1-claim"
WORKER_CONTEXT = "codex/buyer-confirmation-validation"
TERMINAL_VALIDATION_REJECTION = "REJECTED_AT_VALIDATION"


def _connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _result_payload(report: dict[str, object], final_decision: str) -> dict[str, object]:
    status = str(report.get("status") or "")
    treatment = dict(report.get("treatment") or {})
    geometry = dict(treatment.get("risk_and_entry_geometry") or {})
    if final_decision.startswith("REJECTED"):
        conclusion = "negative"
    elif final_decision == "ELIGIBLE_FOR_TRUE_FORWARD":
        conclusion = "supports"
    else:
        conclusion = "inconclusive"
    return {
        "title": f"Buyer Confirmation v1 – {status}",
        "conclusion": conclusion,
        "interpretation": (
            f"Frozen unseen evaluation ended as {final_decision}; no retuning, additional filter, "
            "production activation, or broker action was performed."
        ),
        "sample_size": int(treatment.get("evaluated_n") or 0),
        "hit_rate": treatment.get("win_rate_pct"),
        "expectancy": treatment.get("expectancy_r"),
        "profit_factor": treatment.get("profit_factor"),
        "mfe": dict(geometry.get("mfe_r") or {}).get("mean"),
        "mae": dict(geometry.get("mae_r") or {}).get("mean"),
        "drawdown": dict(report.get("candidate_sequence_drawdown") or {}).get(
            "maximum_drawdown_r"
        ),
        "slippage": 5.0,
        "validation": report,
    }


def _validate_terminal_decision(report: dict[str, object], final_decision: str) -> None:
    if final_decision != TERMINAL_VALIDATION_REJECTION:
        return
    expected_failed_gates = {
        "conservative_execution_treatment_pf_above_one",
        "conservative_execution_treatment_positive",
        "positive_in_at_least_60pct_of_years",
    }
    if (
        str(report.get("status") or "") != "VALIDATION_FAIL"
        or str(report.get("research_stage") or "") != "validation"
        or report.get("next_stage_allowed") is not False
        or set(report.get("failed_gates") or ()) != expected_failed_gates
    ):
        raise ValueError(
            "REJECTED_AT_VALIDATION widerspricht dem gespeicherten Validation-Bericht."
        )


def _ensure_negative_validation_assessment(
    path: Path,
    *,
    workflow: ResearchWorkflow,
    result_id: str,
    decision_report_path: Path,
    report: dict[str, object],
    final_decision: str,
) -> dict[str, object] | None:
    """Append the missing negative gate assessment exactly once.

    The hypothesis-level validation-selection table intentionally remains empty:
    its schema accepts only fully qualified supporting results.  A failed
    Validation belongs in the result assessment and evidence ledger instead.
    """

    if final_decision != TERMINAL_VALIDATION_REJECTION:
        return None
    with _connection(path) as connection:
        existing = connection.execute(
            "SELECT * FROM result_validation_assessments WHERE result_id=? "
            "ORDER BY assessed_at, rowid",
            (result_id,),
        ).fetchall()
    if len(existing) > 1:
        raise ValueError("Buyer-Validation besitzt mehrere KB-Gate-Assessments.")
    if existing:
        assessment = dict(existing[0])
        expected = {
            "result_direction": "NEGATIVE",
            "oos_status": "FAILED",
            "walk_forward_status": "FAILED",
            "external_unseen_status": "NOT_RUN",
            "forward_status": "NOT_RUN",
            "paper_status": "NOT_RUN",
            "sample_size_status": "PASSED",
            "uncertainty_status": "PASSED",
            "costs_slippage_status": "FAILED",
            "data_quality_status": "PASSED",
            "leakage_status": "PASSED",
            "pit_status": "PASSED",
        }
        mismatches = {
            key: {"expected": value, "stored": assessment.get(key)}
            for key, value in expected.items()
            if assessment.get(key) != value
        }
        if mismatches:
            raise ValueError(
                "Gespeichertes Buyer-Validation-Assessment widerspricht dem Endstatus: "
                + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
            )
        assessment["idempotent_replay"] = True
        return assessment
    failed_gates = ", ".join(str(item) for item in report.get("failed_gates") or ())
    report_path = Path(decision_report_path).resolve()
    return workflow.assess_result_for_validation(
        result_id,
        research_type="tradable_strategy_feature",
        result_direction="NEGATIVE",
        source_scopes=("EQUITIES",),
        hypothesis_test_scopes=("EQUITIES",),
        experiment_test_scopes=("EQUITIES",),
        validated_scopes=(),
        rejected_scopes=("EQUITIES",),
        is_status="PASSED",
        oos_status="FAILED",
        walk_forward_status="FAILED",
        external_unseen_status="NOT_RUN",
        forward_status="NOT_RUN",
        paper_status="NOT_RUN",
        sample_size_status="PASSED",
        uncertainty_status="PASSED",
        costs_slippage_status="FAILED",
        data_quality_status="PASSED",
        leakage_status="PASSED",
        pit_status="PASSED",
        critical_blocker=False,
        limitations=(
            "Negative Evidenz gilt nur für die exakt eingefrorene objective_pullback-Regel; "
            "das historische Universum ist nicht vollständig survivorship-free."
        ),
        artifact_references=(
            {
                "system": "buyer_confirmation_validation",
                "record_type": "stage_decision",
                "record_id": str(report.get("review_fingerprint") or "VALIDATION_FAIL"),
                "uri": str(report_path),
                "sha256": _file_sha256(report_path),
            },
        ),
        rationale=(
            "Die vollständig ausgeführte ungesehene Validation ist terminal fehlgeschlagen. "
            f"Fehlgeschlagene vorab definierte Gates: {failed_gates}. Holdout blieb gesperrt."
        ),
        assessed_at=report.get("reviewed_at"),
    )


def prepare(path: Path, *, prepared_at: str | None = None) -> dict[str, object]:
    knowledge = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    knowledge.get_hypothesis(HYPOTHESIS_ID, include_details=False)
    with _connection(path) as connection:
        experiment_row = connection.execute(
            "SELECT id FROM experiments WHERE hypothesis_id=? AND title=?",
            (HYPOTHESIS_ID, EXPERIMENT_TITLE),
        ).fetchone()
    if experiment_row is None:
        experiment = knowledge.create_experiment(
            HYPOTHESIS_ID,
            title=EXPERIMENT_TITLE,
            test_definition=(
                "Ground-up evaluation of the formally frozen objective_pullback challenger; "
                "the only new rule is Close[t] > High[t-1]. Validation must finish before "
                "Holdout can open, and External remains separately gated."
            ),
            features=["buyer_confirmation_close_above_prior_high"],
            data_universe="Frozen 2520-asset equities/ETF research universe",
            point_in_time_rules=(
                "Completed signal candle only; next-session Open; pullback low minus 0.25 ATR14; "
                "fixed 2R/25 sessions; immutable chronological Development/Validation/Holdout splits"
            ),
            baseline="objective_pullback cases without Buyer Confirmation",
            parameters={
                "challenger_version": "buyer-confirmation-objective-pullback-v1",
                "single_rule": "Close[t] > High[t-1]",
                "additional_filters": [],
                "retuning_allowed": False,
                "production_activation": False,
            },
            test_status="PLANNED",
            period_start="2013-01-01",
            period_end="2026-08-26",
            created_at=prepared_at,
        )
    else:
        experiment = knowledge.get_experiment(str(experiment_row["id"]))
    with _connection(path) as connection:
        scope = connection.execute(
            "SELECT id FROM market_scope_assessments WHERE target_type='experiment' "
            "AND target_id=? ORDER BY assessed_at DESC, rowid DESC LIMIT 1",
            (experiment["id"],),
        ).fetchone()
    if scope is None:
        workflow.record_market_scope(
            target_type="experiment",
            target_id=str(experiment["id"]),
            asset_class="EQUITIES",
            region="Globales eingefrorenes Projektuniversum; natürliche Gewichte",
            universe="Frozen 2520-asset equities/ETF research universe",
            timeframe="Daily; next-session entry; 25-session horizon",
            scope_notes=(
                "Keine USA-only-, Regionen-, Regime- oder Volatilitätsselektion; "
                "nicht vollständig survivorship-free."
            ),
            assessed_at=prepared_at,
        )
    with _connection(path) as connection:
        assessment = connection.execute(
            "SELECT id FROM application_capability_assessments WHERE hypothesis_id=? "
            "AND experiment_id=? AND outcome='TESTABLE_NOW' ORDER BY assessed_at DESC, rowid DESC LIMIT 1",
            (HYPOTHESIS_ID, experiment["id"]),
        ).fetchone()
    if assessment is None:
        assessment_payload = workflow.record_application_assessment(
            HYPOTHESIS_ID,
            outcome="TESTABLE_NOW",
            feature_available=True,
            required_data_available=True,
            existing_research_test=True,
            market_scope_reviewed=True,
            active_rule_exists=False,
            infrastructure_needed="Separate append-only Buyer Confirmation unseen-evaluation store",
            existing_assets={
                "freeze": "buyer-confirmation-objective-pullback-v1",
                "frozen_dataset": "e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed",
                "broad_v1": "7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5",
            },
            rationale=(
                "Frozen OHLCV, exact Broad-v1 code, immutable challenger rule, and predeclared gates "
                "are available; no production rule exists."
            ),
            experiment_id=str(experiment["id"]),
            assessed_at=prepared_at,
        )
        assessment_id = str(assessment_payload["id"])
    else:
        assessment_id = str(assessment["id"])
    with _connection(path) as connection:
        request_row = connection.execute(
            "SELECT id FROM research_work_requests WHERE idempotency_key=?",
            (WORK_REQUEST_KEY,),
        ).fetchone()
    if request_row is None:
        request = workflow.create_work_request(
            HYPOTHESIS_ID,
            capability_assessment_id=assessment_id,
            request_type="RESEARCH_TEST",
            task=(
                "Run the frozen Buyer Confirmation challenger through Validation, then Holdout only "
                "after Validation PASS, then the existing External gate only after Holdout PASS."
            ),
            expected_output=(
                "Append-only stage decisions and exactly one final gate status without retuning or production activation"
            ),
            required_infrastructure=(
                "Frozen OHLCV, global research lock, protected production windows, separate validation SQLite store"
            ),
            scope={
                "setup": "objective_pullback",
                "single_rule": "Close[t] > High[t-1]",
                "stages": ["validation", "holdout", "external"],
                "expected_assets_per_historical_stage": 2520,
            },
            safeguards={
                "broad_v1_immutable": True,
                "frozen_dataset_immutable": True,
                "retuning": False,
                "additional_filters": False,
                "holdout_requires_validation_pass": True,
                "production_activation": False,
            },
            experiment_id=str(experiment["id"]),
            idempotency_key=WORK_REQUEST_KEY,
            created_at=prepared_at,
        )
    else:
        request = workflow.get_work_request(str(request_row["id"]), include_context=False)
    if request["current_status"] == "READY":
        request = workflow.claim_work_request(
            str(request["id"]),
            worker_context=WORKER_CONTEXT,
            claim_token=CLAIM_TOKEN,
            claimed_at=prepared_at,
        )
    elif request["current_status"] == "IN_PROGRESS":
        request = workflow.claim_work_request(
            str(request["id"]),
            worker_context=WORKER_CONTEXT,
            claim_token=CLAIM_TOKEN,
            claimed_at=prepared_at,
        )
    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "experiment_id": str(experiment["id"]),
        "capability_assessment_id": assessment_id,
        "work_request_id": str(request["id"]),
        "work_request_status": request["current_status"],
        "duplicate_hypothesis_created": False,
        "idempotency_key": WORK_REQUEST_KEY,
        "automatic_strategy_change": False,
        "production_activation": False,
    }


def complete(
    path: Path,
    *,
    decision_report_path: Path,
    final_decision: str,
    completed_at: str | None = None,
) -> dict[str, object]:
    workflow = ResearchWorkflow(path)
    prepared = prepare(path, prepared_at=completed_at)
    request = workflow.get_work_request(str(prepared["work_request_id"]), include_context=False)
    report = json.loads(Path(decision_report_path).read_text(encoding="utf-8"))
    _validate_terminal_decision(report, final_decision)
    payload = _result_payload(report, final_decision)
    if request["current_status"] == "COMPLETED":
        result_id = str(request.get("result_id") or "")
        if not result_id:
            raise ValueError("Abgeschlossener Work Request besitzt kein KB-Resultat.")
        stored_result = workflow.knowledge.get_result(result_id)
        expected_identity = {
            "title": payload["title"],
            "conclusion": payload["conclusion"],
            "sample_size": payload["sample_size"],
        }
        mismatches = {
            key: {"expected": value, "stored": stored_result.get(key)}
            for key, value in expected_identity.items()
            if stored_result.get(key) != value
        }
        if mismatches:
            raise ValueError(
                "Abgeschlossenes Buyer-Validation-Resultat widerspricht dem Entscheidungsbericht: "
                + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
            )
        assessment = _ensure_negative_validation_assessment(
            path,
            workflow=workflow,
            result_id=result_id,
            decision_report_path=decision_report_path,
            report=report,
            final_decision=final_decision,
        )
        return {
            **prepared,
            "work_request_status": "COMPLETED",
            "result_id": result_id,
            "result_validation_assessment_id": assessment.get("id") if assessment else None,
            "candidate_lifecycle_status": final_decision,
            "hypothesis_status_unchanged": True,
            "hypothesis_validation_evidence_selected": False,
            "idempotent_replay": True,
        }
    completed = workflow.complete_work_request(
        str(request["id"]),
        claim_token=CLAIM_TOKEN,
        worker_context=WORKER_CONTEXT,
        result=payload,
        result_reference=str(Path(decision_report_path).resolve()),
        artifact_references=(
            {
                "system": "buyer_confirmation_validation",
                "record_type": "stage_decision",
                "record_id": str(report.get("review_fingerprint") or report.get("status")),
            },
        ),
        completed_at=completed_at,
    )
    result_id = str(completed.get("result_id") or "")
    assessment = _ensure_negative_validation_assessment(
        path,
        workflow=workflow,
        result_id=result_id,
        decision_report_path=decision_report_path,
        report=report,
        final_decision=final_decision,
    )
    return {
        **prepared,
        "work_request_status": completed["current_status"],
        "result_id": result_id,
        "result_validation_assessment_id": assessment.get("id") if assessment else None,
        "final_decision": final_decision,
        "candidate_lifecycle_status": final_decision,
        "hypothesis_status_unchanged": True,
        "hypothesis_validation_evidence_selected": False,
        "negative_evidence_retained": True,
        "automatic_strategy_change": False,
        "production_activation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Buyer Validation with the KB.")
    parser.add_argument("action", choices=("prepare", "complete"))
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--decision-report", type=Path)
    parser.add_argument("--final-decision")
    parser.add_argument("--at")
    args = parser.parse_args()
    if args.action == "prepare":
        output = prepare(args.database, prepared_at=args.at)
    else:
        if args.decision_report is None or not args.final_decision:
            parser.error("complete requires --decision-report and --final-decision")
        output = complete(
            args.database,
            decision_report_path=args.decision_report,
            final_decision=args.final_decision,
            completed_at=args.at,
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
