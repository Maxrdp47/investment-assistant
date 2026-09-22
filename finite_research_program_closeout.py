from __future__ import annotations

"""Fail-closed R8 trigger review and R9 closeout for the finite program."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from multi_asset_discovery_v1 import fingerprint
from multi_asset_v2_r6_review import COMPLETION_SUMMARY, DESCRIPTIVE_REPORT, FINAL_AUDIT
from multi_asset_v2_r6_runner import R6_MANIFEST, verify_self_fingerprint


ROOT = Path(__file__).resolve().parent
PROGRAM_ID = "finite-research-program-2026-09-15-v1"
R8_REVIEW = ROOT / "runtime" / "research_exports" / "finite_research_program_r8_trigger_review_2026-09-22-v1.json"
R8_REVIEW_MARKDOWN = ROOT / "FINITE_RESEARCH_PROGRAM_R8_TRIGGER_REVIEW_2026-09-22.md"
R8_VERSION = "finite-research-program-r8-trigger-review-2026.09.22-v1"
SEEN_DATA_REGISTER = ROOT / "runtime" / "research_exports" / "finite_research_program_seen_data_register_2026-09-22-v1.json"
R9_DECISION = ROOT / "runtime" / "research_exports" / "finite_research_program_r9_decision_2026-09-22-v1.json"
FINAL_ATTESTED_REPORT = ROOT / "runtime" / "research_exports" / "finite_research_program_final_report_2026-09-22-v1.json"
FINAL_ATTESTED_REPORT_MARKDOWN = ROOT / "runtime" / "research_exports" / "FINITE_RESEARCH_PROGRAM_FINAL_REPORT_2026-09-22.md"
SEEN_VERSION = "finite-research-program-seen-data-register-2026.09.22-v1"
R9_VERSION = "finite-research-program-r9-decision-2026.09.22-v1"
FINAL_REPORT_VERSION = "finite-research-program-final-report-2026.09.22-v1"


class FiniteResearchProgramCloseoutError(RuntimeError):
    """The finite program cannot advance without violating its frozen chain."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_verified(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FiniteResearchProgramCloseoutError(f"Required artifact unreadable: {path}") from exc
    if not verify_self_fingerprint(payload):
        raise FiniteResearchProgramCloseoutError(f"Artifact fingerprint invalid: {path}")
    return payload


def _self_fingerprinted(payload: Mapping[str, object]) -> dict[str, object]:
    result = dict(payload)
    result.pop("artifact_fingerprint", None)
    result["artifact_fingerprint"] = fingerprint(result)
    return result


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()


def _write_json_immutable(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        existing = _read_verified(path)
        if existing != dict(payload):
            raise FiniteResearchProgramCloseoutError(f"Immutable artifact conflict: {path}")
        return
    _atomic_write(path, encoded)


def _write_text_immutable(path: Path, content: str) -> None:
    normalized = content.rstrip() + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != normalized:
            raise FiniteResearchProgramCloseoutError(f"Immutable report conflict: {path}")
        return
    _atomic_write(path, normalized)


def evaluate_r8_trigger(
    report: Mapping[str, object], summary: Mapping[str, object], *, created_at: str
) -> dict[str, object]:
    if report.get("status") != "R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE":
        raise FiniteResearchProgramCloseoutError("R8 requires terminal R6 no-candidate evidence.")
    if summary.get("status") != "R6_COMPLETE_NO_ROBUST_CANDIDATES_R7_NOT_OPENED":
        raise FiniteResearchProgramCloseoutError("R7 is not proven closed.")
    if int(report.get("robust_candidate_count", -1)) != 0 or summary.get("r7_opened") is not False:
        raise FiniteResearchProgramCloseoutError("R8 cannot bypass an R7 candidate or open stage.")
    if report.get("justified_reserve_trigger_identified") is not False:
        raise FiniteResearchProgramCloseoutError("R8 trigger state is missing or not terminally false.")
    dimensions = dict(report.get("quality_c_dimensions") or {})
    dependency = str(dimensions.get("DEPENDENCIES") or "")
    if dependency != "FAIL_HISTORICAL_VERIFIED_ISSUER_EFFECTIVE_N_ZERO":
        raise FiniteResearchProgramCloseoutError("R8 review expected the frozen dependency limitation.")
    return _self_fingerprinted(
        {
            "version": R8_VERSION,
            "program_id": PROGRAM_ID,
            "program_block": "R8",
            "status": "SKIPPED_NO_JUSTIFIED_RESERVE_TRIGGER",
            "created_at": created_at,
            "r6_report_fingerprint": report["artifact_fingerprint"],
            "r6_summary_fingerprint": summary["artifact_fingerprint"],
            "attempt_count": 0,
            "maximum_attempts": 2,
            "prerequisites": {
                "no_holdout_pass_in_r1_to_r7": True,
                "open_r7_candidates": 0,
                "concrete_unresolved_information_gap_measurable_by_reserve": False,
            },
            "observed_release_blocker": "HISTORICAL_VERIFIED_ISSUER_DEPENDENCIES_EFFECTIVE_N_ZERO",
            "reserve_can_measure_release_blocker": False,
            "reserve_hypotheses_activated": [],
            "reserve_items_not_tested": [
                "Stochastic",
                "Williams %R",
                "CCI",
                "additional ROC variants",
                "additional MACD parameter sets",
                "additional moving-average combinations",
                "Ichimoku",
                "Supertrend",
                "larger candlestick-pattern libraries",
            ],
            "selection_by_development_profit_performed": False,
            "grid_search_performed": False,
            "feature_combinations_tested": 0,
            "reason": (
                "R6 produced no Quality-C candidate and no concrete technical measurement gap. "
                "Its terminal release limitation is missing historically verified issuer "
                "dependencies; another technical indicator cannot repair that evidence gap. "
                "Activating a popular reserve indicator would therefore be an unjustified "
                "rescue test rather than the contractually required gap-driven hypothesis."
            ),
            "validation_opened": False,
            "holdout_opened": False,
            "next_step": "R9_FINAL_DECISION_AND_STOP",
        }
    )


def render_r8_markdown(payload: Mapping[str, object]) -> str:
    return "\n".join(
        [
            "# Endliches Research-Programm – R8 Trigger-Review",
            "",
            f"- Status: `{payload['status']}`",
            f"- Aktivierte Reserve-Hypothesen: {payload['attempt_count']} von maximal {payload['maximum_attempts']}",
            f"- R8-Fingerprint: `{payload['artifact_fingerprint']}`",
            "",
            "R6 lieferte keinen zulässigen Quality-C-Kandidaten und keine konkret "
            "dokumentierte technische Messlücke. Die verbleibende harte Release-Grenze "
            "ist Effective N = 0 bei historisch verifizierten Issuer-Dependencies. Ein "
            "weiterer technischer Indikator kann diese Provenienz- und Abhängigkeitslücke "
            "nicht schließen.",
            "",
            "Daher wurde kein Stochastic-, Williams-%R-, CCI-, ROC-, MACD-, Moving-"
            "Average-, Ichimoku-, Supertrend- oder Candlestick-Test aktiviert. Das ist "
            "kein Performance-basiertes Aussortieren, sondern die vorab festgelegte "
            "Schutzregel gegen einen unbegründeten Rettungstest. Validation und Holdout "
            "blieben geschlossen. Nächster und letzter Schritt ist R9.",
        ]
    )


def build_r8_trigger_review() -> dict[str, object]:
    if R8_REVIEW.exists():
        existing = _read_verified(R8_REVIEW)
        _write_text_immutable(R8_REVIEW_MARKDOWN, render_r8_markdown(existing))
        return existing
    report = _read_verified(DESCRIPTIVE_REPORT)
    summary = _read_verified(COMPLETION_SUMMARY)
    payload = evaluate_r8_trigger(report, summary, created_at=utc_now())
    _write_json_immutable(R8_REVIEW, payload)
    _write_text_immutable(R8_REVIEW_MARKDOWN, render_r8_markdown(payload))
    return payload


def build_seen_data_register(*, created_at: str) -> dict[str, object]:
    audit = _read_verified(FINAL_AUDIT)
    report = _read_verified(DESCRIPTIVE_REPORT)
    r8 = _read_verified(R8_REVIEW)
    manifest = _read_verified(R6_MANIFEST)
    entries = [
        {
            "id": "R0_V7_R2_DEVELOPMENT",
            "dataset": "multi-asset-development-v7-r2",
            "stage": "development",
            "asset_scope": "frozen multi-asset v7-r2 universe",
            "period": ["2016-01-01", "2021-12-31"],
            "hypothesis": "multi-asset opportunity discovery v7-r2",
            "version": "mad1-development-v7-recovery-20260913-v2",
            "result_viewed": True,
            "consumed": True,
        },
        {
            "id": "R1_WATER_DEVELOPMENT",
            "dataset": "a12525a8a6b4c1165fe7cea2ee725d42ef6b6f858c49b4ccac9899abd4b2c78d",
            "stage": "development",
            "asset_scope": "XYL,BMI,PNR with SPY/PHO controls",
            "period": ["2010-01-01", "2017-12-31"],
            "hypothesis": "water infrastructure correction plus breakout",
            "version": "water-infrastructure-research-2026.09.15-v1",
            "result_viewed": True,
            "consumed": True,
        },
        {
            "id": "R1_WATER_VALIDATION",
            "dataset": "a12525a8a6b4c1165fe7cea2ee725d42ef6b6f858c49b4ccac9899abd4b2c78d",
            "stage": "validation",
            "asset_scope": "R1 frozen water scope",
            "period": ["2018-01-01", "2021-12-31"],
            "hypothesis": "water infrastructure correction plus breakout",
            "version": "water-infrastructure-research-2026.09.15-v1",
            "result_viewed": False,
            "consumed": False,
            "globally_unseen_claim": False,
            "reason": "stage unopened, but these calendar years were viewed in other Development research",
        },
        {
            "id": "R1_WATER_HOLDOUT",
            "dataset": "a12525a8a6b4c1165fe7cea2ee725d42ef6b6f858c49b4ccac9899abd4b2c78d",
            "stage": "holdout",
            "asset_scope": "R1 frozen water scope",
            "period": ["2022-01-01", "2026-08-23"],
            "hypothesis": "water infrastructure correction plus breakout",
            "version": "water-infrastructure-research-2026.09.15-v1",
            "result_viewed": False,
            "consumed": False,
            "globally_unseen_claim": "NOT_ASSERTED",
        },
        {
            "id": "R2_GOLD_SILVER_PERFORMANCE_STAGES",
            "dataset": None,
            "stage": "development_validation_holdout",
            "asset_scope": "GC/SI futures",
            "period": None,
            "hypothesis": "gold silver laggard after relative divergence",
            "version": "knowledge-base experiment 255532e0-3b54-412a-a29e-866bfe4bda82",
            "result_viewed": False,
            "consumed": False,
            "reason": "blocked before performance by contract/roll/open provenance",
        },
        {
            "id": "R3_OVERNIGHT_DEVELOPMENT",
            "dataset": "321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6",
            "stage": "development",
            "asset_scope": "frozen EQUITIES/ETF projection",
            "period": ["2016-01-01", "2021-12-31"],
            "hypothesis": "incremental overnight bias against close-to-close baseline",
            "version": "overnight-intraday-r3-2026.09.22-v1",
            "result_viewed": True,
            "consumed": True,
        },
        {
            "id": "R6_DISCOVERY_V2_DEVELOPMENT",
            "dataset": manifest["combined_input_fingerprint"],
            "stage": "development",
            "asset_scope": "EQUITIES/ETF/CRYPTO in frozen v2 scope",
            "period": [
                dict(audit["case_integrity"])["minimum_signal_day"],
                dict(audit["case_integrity"])["maximum_signal_day"],
            ],
            "hypothesis": "predeclared individual v2 feature associations",
            "version": manifest["run_id"],
            "result_viewed": True,
            "consumed": True,
            "review_fingerprint": report["artifact_fingerprint"],
        },
        {
            "id": "R7_CHALLENGER_STAGES",
            "dataset": None,
            "stage": "validation_holdout",
            "asset_scope": None,
            "period": None,
            "hypothesis": None,
            "version": None,
            "result_viewed": False,
            "consumed": False,
            "reason": "zero R6 Quality-C candidates; R7 never opened",
        },
        {
            "id": "R8_RESERVE_STAGES",
            "dataset": None,
            "stage": "development_validation_holdout",
            "asset_scope": None,
            "period": None,
            "hypothesis": None,
            "version": None,
            "result_viewed": False,
            "consumed": False,
            "reason": r8["status"],
        },
    ]
    payload = _self_fingerprinted(
        {
            "version": SEEN_VERSION,
            "program_id": PROGRAM_ID,
            "created_at": created_at,
            "entries": entries,
            "consumed_validation_stages": 0,
            "consumed_holdout_stages": 0,
            "new_contract_resets_seen_status": False,
            "unseen_claim_requires_explicit_dataset_stage_evidence": True,
        }
    )
    _write_json_immutable(SEEN_DATA_REGISTER, payload)
    return payload


def build_r9_decision() -> dict[str, object]:
    if R9_DECISION.exists():
        return _read_verified(R9_DECISION)
    r8 = build_r8_trigger_review()
    audit = _read_verified(FINAL_AUDIT)
    report = _read_verified(DESCRIPTIVE_REPORT)
    summary = _read_verified(COMPLETION_SUMMARY)
    if r8["status"] != "SKIPPED_NO_JUSTIFIED_RESERVE_TRIGGER":
        raise FiniteResearchProgramCloseoutError("R8 is not terminally closed.")
    if int(report["robust_candidate_count"]) != 0 or summary["r7_opened"] is not False:
        raise FiniteResearchProgramCloseoutError("An R7 candidate remains open.")
    created_at = utc_now()
    seen = build_seen_data_register(created_at=created_at)
    ledger = [
        {"block": "R0", "attempts": 0, "status": "DONE_V7_R2_ZERO_ROBUST_CANDIDATES"},
        {"block": "R1", "attempts": 1, "status": "DEVELOPMENT_INCONCLUSIVE_UNDERPOWERED"},
        {"block": "R2", "attempts": 0, "status": "BLOCKED_BEFORE_PERFORMANCE_BY_DATA_SEMANTICS"},
        {"block": "R3", "attempts": 1, "status": "DEVELOPMENT_NEGATIVE_NO_ROBUST_INCREMENT"},
        {"block": "R4", "attempts": 0, "status": "DONE_LIMITED_CAPABILITY_A_TO_I"},
        {"block": "R5", "attempts": 0, "status": "DONE_FROZEN_NO_OUTCOMES_OPENED"},
        {"block": "R6", "attempts": 1, "status": report["status"]},
        {"block": "R7", "attempts": 0, "status": "NOT_OPENED_ZERO_ELIGIBLE_CANDIDATES"},
        {"block": "R8", "attempts": 0, "status": r8["status"]},
    ]
    decision = _self_fingerprinted(
        {
            "version": R9_VERSION,
            "program_id": PROGRAM_ID,
            "program_block": "R9",
            "status": "NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM",
            "created_at": created_at,
            "attempt_ledger": ledger,
            "total_new_empirical_attempts": sum(int(item["attempts"]) for item in ledger),
            "r6_audit_fingerprint": audit["artifact_fingerprint"],
            "r6_report_fingerprint": report["artifact_fingerprint"],
            "r6_completion_fingerprint": summary["artifact_fingerprint"],
            "r8_review_fingerprint": r8["artifact_fingerprint"],
            "seen_data_register_fingerprint": seen["artifact_fingerprint"],
            "validated_trading_edge": "NONE_CONFIRMED",
            "autonomous_strategy_search": "PAUSED_AFTER_FINITE_RESEARCH_PROGRAM",
            "software_product": "ACTIVE",
            "research_infrastructure": "ACTIVE",
            "data_collection": "ACTIVE_FOR_PREVIOUSLY_AUTHORIZED_SIGNAL_INDEPENDENT_COLLECTORS_ONLY",
            "limits": [
                "R1 water evidence was underpowered",
                "R2 futures performance was not testable with verified roll/open provenance",
                "historically verified issuer dependency effective N remained zero in R6",
                "fundamentals/events/macro/politics were shadow or unavailable for the frozen historical scope",
                "historical-universe survivorship remained unknown",
            ],
            "scope_of_negative_conclusion": (
                "Only the approved finite program under available, permitted and cleanly "
                "usable data; not a universal claim that no market edge exists."
            ),
            "validation_stages_consumed": 0,
            "holdout_stages_consumed": 0,
            "external_opened": False,
            "forward_opened": False,
            "paper_opened": False,
            "shadow_execution_opened": False,
            "broker_opened": False,
            "orders_opened": False,
            "production_strategy_changed": False,
            "next_step": "STOP_AWAIT_USER_REVIEW",
        }
    )
    _write_json_immutable(R9_DECISION, decision)
    return decision


def render_final_attested_report(payload: Mapping[str, object]) -> str:
    decision = dict(payload["decision"])
    ledger = list(decision["attempt_ledger"])
    lines = [
        "# Finaler Abschlussbericht – begrenztes Research-Programm R0–R9",
        "",
        f"Gesamturteil: `{decision['status']}`",
        "",
        "## A. Git/Code",
        "",
        f"- Start-HEAD: `{payload['start_head']}`",
        f"- Finaler HEAD: `{payload['final_head']}`",
        f"- Branch: `{payload['branch']}`",
        f"- Push: `{payload['push_status']}`",
        f"- CI: `{payload['ci_status']}` – {payload['ci_url']}",
        "",
        "## B. Research-Ledger",
        "",
        "| Block | Attempts | Terminaler Stand |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| {item['block']} | {item['attempts']} | `{item['status']}` |" for item in ledger
    )
    lines.extend(
        [
            "",
            "## C. Wasser",
            "",
            "R1 endete mit `DEVELOPMENT_INCONCLUSIVE_UNDERPOWERED`: sieben primäre "
            "Fälle, Effective N 3/4 statt 100. Validation und Holdout blieben ungeöffnet.",
            "",
            "## D. Gold/Silber",
            "",
            "R2 wurde vor Performance wegen nicht belegbarer Kontrakt-/Roll-/Next-Open-"
            "Provenienz gestoppt. Es gab keinen Research-Versuch und kein Ergebnis-Mining.",
            "",
            "## E. Overnight",
            "",
            "R3 führte genau einen deduplizierten deskriptiven Development-Versuch aus. "
            "Der inkrementelle Zusammenhang war klein und zeitlich instabil; kein Challenger.",
            "",
            "## F. Discovery v2",
            "",
            f"R6 auditierte {payload['r6_cases']:,} Fälle und {payload['r6_features']} "
            "vorab benannte Einzelfeatures in getrennten 20/60/120/252-Populationen. "
            "Es entstanden 0 robuste Quality-C-Kandidaten und R7 wurde nicht geöffnet.",
            "",
            "## G. Fundamentals",
            "",
            "Die SEC-PIT-Logik ist vorbereitet, aber mangels versioniertem historischem "
            "Quellsnapshot und zeitgültigem Join im Frozen Scope nur SHADOW, nicht getestet.",
            "",
            "## H. Makro/Events/Politik",
            "",
            "Historisch belastbare Coverage blieb SHADOW oder UNAVAILABLE. Heutige "
            "Information wurde nicht rückdatiert; ein Fehlen wurde nie als False/0 gewertet.",
            "",
            "## I. FX",
            "",
            "FX blieb historisch nicht testbar: Kontinuitätssegmente erfüllten die "
            "Gap-sichere 220-Beobachtungs-Anforderung nicht; die Regel wurde nicht gelockert.",
            "",
            "## J. Dependencies",
            "",
            "Identity-/Listing-Strukturen wurden verbessert, aber für 2016–2021 blieben "
            "historisch verifizierte Issuer-Dependencies bei Effective N = 0. Raw N wurde "
            "nicht als unabhängige Evidenz ausgegeben.",
            "",
            "## K. Reserve",
            "",
            "R8 aktivierte 0 von maximal 2 Hypothesen. Technische Reserveindikatoren können "
            "die verbleibende Dependency-Provenienzlücke nicht messen und wären ein "
            "unbegründeter Rettungstest gewesen.",
            "",
            "## L. Unseen stages",
            "",
            "Im Programm wurden 0 Validation- und 0 Holdout-Stufen konsumiert. Ungeöffnete "
            "Stufen werden nur vertragsbezogen als ungeöffnet bezeichnet; überlappende "
            "Kalenderperioden werden nicht pauschal wieder als global unseen ausgegeben.",
            "",
            "## M. Safety",
            "",
            "External, Forward, Paper, Shadow-Ausführung, Broker, Orders und produktive "
            "Strategieänderungen blieben geschlossen. Frühere Frozen Stores und Evidenz "
            "wurden nicht verändert.",
            "",
            "## N. Gesamturteil",
            "",
            f"`{decision['status']}`",
            "",
            "Dies ist kein Softwarefehler und kein universeller Beweis gegen Markt-Edges. "
            "Es ist das negative Endergebnis des ausdrücklich begrenzten Programms unter "
            "den verfügbaren, zulässigen und sauber nutzbaren Daten. Software, Research-"
            "Infrastruktur und bereits freigegebene signalunabhängige Datensammlung bleiben "
            "aktiv; die autonome Strategiesuche stoppt bis zu einer neuen Nutzerentscheidung.",
            "",
            "## Abschlussprüfungen",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["tests"])
    lines.append("")
    lines.append(f"Final-Report-Fingerprint: `{payload['artifact_fingerprint']}`")
    return "\n".join(lines)


def build_final_attested_report(
    *,
    final_head: str,
    branch: str,
    ci_url: str,
    ci_status: str,
    push_status: str,
    tests: list[str],
) -> dict[str, object]:
    if ci_status != "SUCCESS":
        raise FiniteResearchProgramCloseoutError("Final attestation requires successful exact-commit CI.")
    decision = build_r9_decision()
    report = _read_verified(DESCRIPTIVE_REPORT)
    payload = _self_fingerprinted(
        {
            "version": FINAL_REPORT_VERSION,
            "created_at": utc_now(),
            "start_head": "fb56ea820ec28befc57a67e091a18d9c19d77b72",
            "final_head": final_head,
            "branch": branch,
            "push_status": push_status,
            "ci_status": ci_status,
            "ci_url": ci_url,
            "tests": tests,
            "r6_cases": int(report["cases_reviewed"]),
            "r6_features": int(report["feature_count"]),
            "decision": decision,
        }
    )
    _write_json_immutable(FINAL_ATTESTED_REPORT, payload)
    _write_text_immutable(FINAL_ATTESTED_REPORT_MARKDOWN, render_final_attested_report(payload))
    return payload


__all__ = [
    "FiniteResearchProgramCloseoutError",
    "FINAL_ATTESTED_REPORT",
    "FINAL_ATTESTED_REPORT_MARKDOWN",
    "R8_REVIEW",
    "R8_REVIEW_MARKDOWN",
    "R9_DECISION",
    "SEEN_DATA_REGISTER",
    "build_final_attested_report",
    "build_r8_trigger_review",
    "build_r9_decision",
    "build_seen_data_register",
    "evaluate_r8_trigger",
    "render_final_attested_report",
    "render_r8_markdown",
]
