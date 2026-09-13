from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_trading_research_backlog_is_ordered_and_not_started() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    development = roadmap.index(
        "Aktuellen Multi-Asset-Discovery-/Development-Pfad vollständig abschließen"
    )
    water = roadmap.index("### TR-01 – Wasser-Infrastruktur-Aktien")
    metals = roadmap.index("### TR-02 – Gold-/Silber-Nachzügler")
    overnight = roadmap.index("### TR-03 – Overnight-/Intraday-Renditetrennung")

    assert development < water < metals < overnight
    assert "Planungsstatus: `PLANNED_NOT_STARTED`" in roadmap
    assert "Aktuelle Ausführungsfreigabe: `false`" in roadmap
    assert "`CONDITIONAL_RESEARCH_RESERVE`" in roadmap


def test_backlog_references_and_evidence_boundaries_are_complete() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    project_status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")

    references = {
        "3721453e-158f-42cb-8d76-a28f054b7d97",
        "78bcdab6-e542-4844-bc95-fbdf1b3b1f9b",
        "b2e990f1-16f9-4bad-a5ad-09184c4225c2",
        "4fdfb983-ddbc-4178-bd36-7aa34267df0b",
        "f8e6a64b-1cf9-431f-9477-4a7a17ab5478",
        "255532e0-3b54-412a-a29e-866bfe4bda82",
    }
    for reference in references:
        assert reference in roadmap

    assert "kein Resultat" in roadmap
    assert "keine positive Evidenz" in project_status
    assert "kein Experiment, Research-Runner, Performance-Lauf" in project_status


def test_terminal_research_is_not_reopened_as_active_backlog() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert "Buyer Confirmation v1 bleibt `REJECTED_AT_VALIDATION`" in roadmap
    assert "Fibonacci bleibt abgeschlossen beziehungsweise inconclusive" in roadmap
    assert "Failed Seller Attempts bleibt abgeschlossen" in roadmap
    assert "FX Carry PIT bleibt abgeschlossen beziehungsweise inconclusive" in roadmap
    assert "keine offenen Aufgaben des Trading-Research-Backlogs" in roadmap
