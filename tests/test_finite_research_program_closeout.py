from __future__ import annotations

import pytest

from finite_research_program_closeout import (
    FiniteResearchProgramCloseoutError,
    evaluate_r8_trigger,
    render_final_attested_report,
    render_r8_markdown,
)
from multi_asset_discovery_v1 import fingerprint


def _evidence() -> tuple[dict[str, object], dict[str, object]]:
    report: dict[str, object] = {
        "status": "R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE",
        "robust_candidate_count": 0,
        "justified_reserve_trigger_identified": False,
        "quality_c_dimensions": {
            "DEPENDENCIES": "FAIL_HISTORICAL_VERIFIED_ISSUER_EFFECTIVE_N_ZERO"
        },
    }
    report["artifact_fingerprint"] = fingerprint(report)
    summary: dict[str, object] = {
        "status": "R6_COMPLETE_NO_ROBUST_CANDIDATES_R7_NOT_OPENED",
        "r7_opened": False,
    }
    summary["artifact_fingerprint"] = fingerprint(summary)
    return report, summary


def test_r8_skips_unjustified_indicator_rescue() -> None:
    report, summary = _evidence()
    result = evaluate_r8_trigger(report, summary, created_at="2026-09-22T00:00:00+00:00")
    assert result["status"] == "SKIPPED_NO_JUSTIFIED_RESERVE_TRIGGER"
    assert result["attempt_count"] == 0
    assert result["reserve_hypotheses_activated"] == []
    assert result["validation_opened"] is False
    assert result["holdout_opened"] is False
    assert result["artifact_fingerprint"] == fingerprint(
        {key: value for key, value in result.items() if key != "artifact_fingerprint"}
    )
    assert "kein Stochastic" in render_r8_markdown(result)


def test_r8_cannot_skip_an_open_r7_candidate() -> None:
    report, summary = _evidence()
    summary["r7_opened"] = True
    with pytest.raises(FiniteResearchProgramCloseoutError, match="cannot bypass"):
        evaluate_r8_trigger(report, summary, created_at="2026-09-22T00:00:00+00:00")


def test_final_report_states_bounded_negative_conclusion_and_safety() -> None:
    payload = {
        "artifact_fingerprint": "final-fp",
        "start_head": "start",
        "final_head": "final",
        "branch": "codex/test",
        "push_status": "PUSHED",
        "ci_status": "SUCCESS",
        "ci_url": "https://example.invalid/ci",
        "r6_cases": 100,
        "r6_features": 31,
        "tests": ["pytest: PASS"],
        "decision": {
            "status": "NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM",
            "attempt_ledger": [
                {"block": "R8", "attempts": 0, "status": "SKIPPED"}
            ],
        },
    }
    rendered = render_final_attested_report(payload)
    assert "NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM" in rendered
    assert "kein universeller Beweis" in rendered
    assert "External, Forward, Paper, Shadow-Ausführung, Broker" in rendered
    assert "Finaler HEAD: `final`" in rendered
