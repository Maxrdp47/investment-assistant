from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "archive"
END_STATUS = "SWINGTRADER_MASTER_ROADMAP_REBUILT_AWAITING_START"


def read_document(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_master_roadmap_has_exact_phase_order_and_is_compact() -> None:
    roadmap = read_document("ROADMAP.md")
    assert roadmap.startswith("# Oberstes Produktziel – SwingTrader\n")
    phases = re.findall(r"^\| (\d+) \| ([^|]+) \|$", roadmap, re.MULTILINE)
    assert [int(number) for number, _ in phases] == list(range(19))
    for phase, title in {
        0: "Datenbetrieb", 1: "Point-in-Time", 2: "Opportunity", 3: "Thesis",
        4: "Entry", 5: "Independent Risk", 6: "Position Monitor", 7: "Dynamic Exit",
        8: "Fixed Challenger", 9: "Development / Walk-Forward", 10: "Validation",
        11: "Holdout", 12: "External Unseen Universe", 13: "True Forward Signals",
        14: "Autonomous Paper", 15: "Shadow Live", 16: "Echtgeld-Gate",
        17: "Live-Bot", 18: "Skalierung",
    }.items():
        assert title in phases[phase][1]
    legacy = (ARCHIVE / "ROADMAP_LEGACY_THROUGH_2026-09-26.md").read_text(encoding="utf-8")
    assert len(roadmap) < 0.70 * len(legacy)


def test_plan_is_not_a_run_or_stage_authorization() -> None:
    roadmap = read_document("ROADMAP.md")
    status = read_document("PROJECT_STATUS.md")
    resume = read_document("VACATION_WORKQUEUE_RESUME.md")
    for text in (roadmap, status, resume):
        assert END_STATUS in text
    for text in (
        "keine neue Ausführungsfreigabe", "Ein allgemeines Startsignal öffnet weder",
        "**derselben Phase**", "auf Nutzer-Startsignal warten", "MANUAL_MODEL_RESUME_REQUIRED",
        "Dieser Dokumentationsauftrag richtet keine Automation ein",
        "geplante Obergrenzen", "kein Reset abgeschlossener Attempt-Budgets",
    ):
        assert text in roadmap
    assert "NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM" in status
    assert "RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA" in status
    assert "NONE_CONFIRMED" in status
    assert "kein Experiment, Research-Runner, Performance-Lauf" in status
    assert "--resume" not in resume
    assert "keine aktive Fortsetzungsanweisung" in resume
    assert "PRIO A:" not in read_document("README.md")
    assert "Die Urlaubs-Queue ist dokumentiert, aber noch nicht gestartet" not in read_document("README.md")
    for obsolete in ("### TR-01", "### TR-02", "### TR-03", "vacation-workqueue-2026", "17:15", "21:30"):
        assert obsolete not in roadmap


def test_pit_packages_health_and_coverage_cannot_be_conflated() -> None:
    roadmap = read_document("ROADMAP.md")
    packages = re.findall(r"^\| (1[A-I]) –", roadmap, re.MULTILINE)
    assert packages == [f"1{letter}" for letter in "ABCDEFGHI"]
    for required in (
        "HEALTHY", "STALE", "PARTIAL", "FAILED", "NOT_CONFIGURED", "NOT_APPLICABLE",
        "ACTIVE_PIT", "LIMITED_SCOPE", "SHADOW", "UNAVAILABLE",
        "expected_known_at < release_at", "accepted_at", "filed_at", "first_seen_at",
        "published_at", "effective_at", "valid_from", "valid_to", "Vintages/Revisions",
        "kein künstliches Effective N", "Heutige Identity nicht rückdatieren",
        "keine neue Suche", "Nicht 100 % Coverage verlangen", "Fehlender Collector",
    ):
        assert required in roadmap
    assert "1C – Expectations" in roadmap and "Forward" in roadmap


def test_signal_risk_monitor_exit_and_execution_are_separate() -> None:
    roadmap = read_document("ROADMAP.md")
    architecture = read_document("SWINGTRADER_PRODUCT_ARCHITECTURE.md")
    states = "UNIVERSE → WATCH → ENTRY_READY → BUY_SIGNAL → POSITION_OPEN → HOLD → PROTECT → SELL_SIGNAL → CLOSED"
    for document in (roadmap, architecture):
        assert states in document
        for state in ("NO_TRADE", "WAIT", "DATA_INSUFFICIENT", "ENTRY_INVALID", "ATTENTION", "EXIT_REVIEW", "PARTIAL_EXIT", "FULL_EXIT"):
            assert state in document
        assert "Zeit allein löst keinen Exit aus" in document
        assert "Monate" in document
    for boundary in (
        "noch kein `BUY_SIGNAL`", "kein prognostischer Candidate-Vorfilter",
        "Nutzer führt reale Orders selbst aus", "Risk Engine nie überschreiben",
        "nur nach oben", "niemals nach unten erweitern", "kleinere Position",
        "20 / 60 / 120 / 252", "kein fixer 2R-Produktzwang", "niemals senden",
        "kein automatischer PASS", "neuer ausdrücklicher Nutzerfreigabe",
        "kein automatisches exponentielles Scaling",
    ):
        assert boundary in roadmap


def test_research_budgets_and_full_portfolio_simulation_precede_oos() -> None:
    roadmap = read_document("ROADMAP.md")
    rows = dict(re.findall(r"^\| (\d+) – ([^\n]+)$", roadmap, re.MULTILINE))
    assert sorted(map(int, rows)) == list(range(2, 19))
    for phase in range(2, 19):
        assert re.search(r"\*\*[0126]\*\*", rows[str(phase)])
    assert "**6** Familien" in rows["2"] and "**2** begründete Interaktionen" in rows["2"]
    assert "Hypothese" in roadmap and "Kill Rule" in roadmap and "Stop-Bedingung" in roadmap
    assert "Fehlt ein Pflichtwert, startet kein Test" in roadmap
    assert "Purging/Embargo" in roadmap and "kein Testen bis irgendetwas positiv wird" in roadmap
    for metric in (
        "Portfolio-Cash", "Sizing", "Korrelation", "Sektorcluster", "offenes Risiko",
        "Kosten/Slippage/Gaps", "Finanzierungs-/Haltekosten", "realisierte/unrealisierte P&L",
        "Kapitalbindung", "Expected R", "PF", "Win/Loss", "Max Drawdown", "Turnover",
    ):
        assert metric in rows["9"]
    assert "FAIL/UNDERPOWERED/INVALID" in rows["10"] and "kein Holdout" in rows["10"]
    assert "keine Produktionsfreigabe" in rows["11"]
    assert "Seen bleibt seen" in roadmap
    assert "keine zusätzliche unabhängige Evidenz" in roadmap


def test_terminal_research_and_reserve_are_not_reopened() -> None:
    roadmap = read_document("ROADMAP.md")
    for name in ("Buyer Confirmation v1", "Fibonacci", "Failed Seller", "Overnight Bias", "Wasser R1", "Discovery v1/v2 Technical-only", "FX Carry PIT"):
        assert name in roadmap
    for boundary in (
        "keine offene Wiederholungsqueue", "plus neuer ausdrücklicher Auftrag",
        "keine Retunes", "Kein Holdout zur Auswahl", "zuerst nur Development",
        "nicht mehrere Reserveindikatoren gleichzeitig", "Fehlende PIT-Provenienz",
    ):
        assert boundary in roadmap
    for indicator in ("Stochastic", "Williams %R", "CCI", "ROC", "MACD", "Moving-Average", "Ichimoku", "Supertrend", "Candlestick"):
        assert indicator in roadmap


@pytest.mark.parametrize(("filename", "expected_digest"), [
    ("ROADMAP_LEGACY_THROUGH_2026-09-26.md", "0017f59d52d12c90583e449696d5a3dd782f9f78182ce09868da2925fa45a81b"),
    ("VACATION_WORKQUEUE_RESUME_LEGACY_THROUGH_2026-09-26.md", "3614ac85a4d1e26a155e0e86c766c55c50d831bb106cbb585a972664050884f8"),
])
def test_archived_full_documents_are_unchanged_across_checkout_line_endings(filename: str, expected_digest: str) -> None:
    content = (ARCHIVE / filename).read_text(encoding="utf-8")
    assert hashlib.sha256(content.encode("utf-8")).hexdigest() == expected_digest


def test_old_backlog_evidence_references_survive_archival() -> None:
    legacy = (ARCHIVE / "ROADMAP_LEGACY_THROUGH_2026-09-26.md").read_text(encoding="utf-8")
    for reference in (
        "3721453e-158f-42cb-8d76-a28f054b7d97", "78bcdab6-e542-4844-bc95-fbdf1b3b1f9b",
        "b2e990f1-16f9-4bad-a5ad-09184c4225c2", "4fdfb983-ddbc-4178-bd36-7aa34267df0b",
        "f8e6a64b-1cf9-431f-9477-4a7a17ab5478", "255532e0-3b54-412a-a29e-866bfe4bda82",
    ):
        assert reference in legacy
    assert "kein Resultat" in legacy
    assert "keine positive Evidenz" in read_document("PROJECT_STATUS.md")


@pytest.mark.parametrize("name", [
    "ROADMAP.md", "PROJECT_STATUS.md", "SWINGTRADER_PRODUCT_ARCHITECTURE.md",
    "VACATION_WORKQUEUE_RESUME.md", "README.md", "CHANGELOG.md",
    "docs/archive/ROADMAP_ARCHIVE_2026-09-26.md",
])
def test_current_document_local_markdown_links_resolve(name: str) -> None:
    document = ROOT / name
    for target in re.findall(r"\[[^\]\n]+\]\(([^)\s]+)\)", document.read_text(encoding="utf-8")):
        link = urlsplit(target)
        if link.scheme or link.netloc or not link.path:
            continue
        path = (document.parent / unquote(link.path)).resolve()
        assert path.is_relative_to(ROOT.resolve()), (name, target)
        assert path.exists(), (name, target)
