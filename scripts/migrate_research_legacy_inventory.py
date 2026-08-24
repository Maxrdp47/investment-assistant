from __future__ import annotations

"""Idempotent reconciliation of the known A–O research inventory.

This migration deliberately uses the Knowledge-Base APIs for Sources, Claims,
Hypotheses, Experiments and Work Requests.  The small reconciliation table is
only an append-only audit of decisions; it is not a second knowledge store.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import DEFAULT_DATABASE_PATH, ResearchKnowledgeBase, ResearchWorkflow
from research_knowledge.schema import database
from research_knowledge.store import _json, _timestamp, normalize_claim


RECONCILIATION_VERSION = "legacy-research-inventory-a-o-2026.08.24-v1"

SOURCES: dict[str, dict[str, Any]] = {
    "A": {"name": "50%-Pullback / Buyer Confirmation TikTok", "title": "50%-Pullback und Buyer Confirmation", "source_type": "tiktok", "creator": None, "summary": "Starker Impuls, ungefährer 50-%-Pullback, bearish candle count, Buyer Confirmation und 2R-Benchmark."},
    "B": {"name": "Quantitativer Corn-/Weather-Research-Workflow", "title": "Quantitativer Corn- und Weather-Research-Workflow", "source_type": "other", "creator": None, "summary": "Methodischer Point-in-Time-Researchablauf und getrennte Weather→Yield- sowie Weather→Price-Hypothesen."},
    "C": {"name": "Automatisierter Multi-Market-Setup-Scanner / Telegram", "title": "Multi-Market Setup Scanner und Telegram", "source_type": "other", "creator": None, "summary": "Candidate→Qualification→Signal-Architektur; Profitdarstellung ist kein Edge-Nachweis."},
    "D": {"name": "Fibonacci 61,8–78,6", "title": "Fibonacci 61,8–78,6 Pullback-Zone", "source_type": "other", "creator": None, "summary": "Schwache, falsifizierbare Pullback-Zonen-Hypothese mit kontinuierlicher Tiefe und Non-Fib-Kontrollzonen."},
    "E": {"name": "ML / Fundamental Expectation / Surprise", "title": "Expectation-, Surprise- und spätere ML-Features", "source_type": "other", "creator": None, "summary": "Marktreaktion relativ zur Erwartung; ML erst nach sauberer Point-in-Time-Historie und OOS-/Walk-Forward-Nachweis."},
    "F": {"name": "COT / Positionierung", "title": "COT-Positionierung und Teilnehmerklassen", "source_type": "other", "creator": None, "summary": "Offizielle CFTC-Daten mit getrennten Teilnehmerklassen, Point-in-Time-Veröffentlichung und relativen Positionierungsfeatures."},
    "G": {"name": "Monty Finance – langes FX-Framework", "title": "Monty Finance – FX Macro/COT/Technical Framework", "source_type": "youtube", "creator": "Monty Finance", "direct_url": "https://youtu.be/iEfzr-4NV8Q?is=VOSJDIdeZmVFstv2", "summary": "FX-Framework aus Macro Bias, COT, Seasonality, Opening Levels, Volume Profile, BOS, Fibonacci und Confluence."},
    "H": {"name": "Monty – Technische Analyse muss objektiv sein", "title": "Monty Finance – objektive und backtestbare technische Analyse", "source_type": "tiktok", "creator": "Monty Finance", "profile_url": "https://www.tiktok.com/@montyfinance", "summary": "Technische Regeln müssen objektiv, reproduzierbar, backtestbar und statistisch prüfbar sein."},
    "I": {"name": "Monty – Macro + COT + Technical Confluence", "title": "Monty Finance – Macro COT Technical Confluence", "source_type": "tiktok", "creator": "Monty Finance", "profile_url": "https://www.tiktok.com/@montyfinance", "summary": "FX-fokussierte Macro-, COT-, Level-, Opening- und Volume-Confluence ohne Nachweis, dass mehr Filter automatisch besser sind."},
    "J": {"name": "Moderna / asymmetrische Opportunity", "title": "Moderna und asymmetrische Investment Opportunity", "source_type": "other", "creator": None, "summary": "Bilanz-/Net-Cash-Downside, Cash Runway, konkrete Catalysts und probability-weighted Szenarien einschließlich Biotech-Binärrisiko."},
    "K": {"name": "Monty – JPY / Carry Trade", "title": "Monty Finance – Yen Carry Trade und BoJ-Ausblick", "source_type": "tiktok", "creator": "Monty Finance", "profile_url": "https://www.tiktok.com/@montyfinance", "summary": "Carry-Unwind, erwartete relative Zinsdifferenz, Volatilität, Positionierung und nicht belastbare feste JPY-Prognose."},
    "L": {"name": "cem_trades – Failed Seller Attempts / Close Location", "title": "cem_trades – Failed Seller Attempts im Pullback", "source_type": "tiktok", "creator": "cem_trades", "summary": "Gescheiterte Verkäufer-Pushs und Close Location als begrenzte Pullback-Fortsetzungsfeatures."},
    "M": {"name": "Finanzballon – Best Days / Overnight vs Intraday", "title": "Finanzballon – Market Timing und Overnight-/Intraday-Renditen", "source_type": "tiktok", "creator": "Finanzballon", "profile_url": "https://www.tiktok.com/@finanzballon", "summary": "Langfristiger Best-Days-Kontext und getrennte Overnight-/Intraday-Renditezerlegung."},
    "N": {"name": "Monty – Bitcoin Regime / Ensemble / Thesis Invalidation", "title": "Monty Finance – Bitcoin-Regime, Modellkonsens und Thesis Invalidation", "source_type": "tiktok", "creator": "Monty Finance", "profile_url": "https://www.tiktok.com/@montyfinance", "summary": "Crypto-Regime, späterer Modellkonsens und objektive System-Invalidation statt subjektivem Bias."},
    "O": {"name": "Monty – EUR/NZD Key Level + BOS + Fib + Volume/Open", "title": "Monty Finance – EURNZD Key-Level-, BOS- und Pullback-Confluence", "source_type": "tiktok", "creator": "Monty Finance", "profile_url": "https://www.tiktok.com/@montyfinance", "summary": "EUR/NZD Key Level, BOS, 0,618–0,786 Pullback, Volume/POC und Monthly Open als getrennt zu prüfende Komponenten."},
}

KNOWN_TITLE_MARKERS = {
    "K": ("yen carry trade", "boj"),
    "L": ("failed seller attempts",),
    "M": ("overnight", "intraday"),
    "N": ("bitcoin-regime", "modellkonsens"),
    "O": ("eurnzd", "bos", "pullback"),
}


def _counts(path: Path) -> dict[str, int]:
    with database(path) as connection:
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        mapping = {
            "sources": "research_sources",
            "source_claims": "source_claims",
            "hypotheses": "hypotheses",
            "experiments": "experiments",
            "results": "research_results",
            "work_requests": "research_work_requests",
            "ledger_events": "evidence_ledger",
            "integration_candidates": "integration_candidates",
        }
        return {
            label: (int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if table in tables else 0)
            for label, table in mapping.items()
        }


def _existing_reconciliation(path: Path, key: str) -> dict[str, Any] | None:
    with database(path) as connection:
        row = connection.execute(
            "SELECT * FROM legacy_research_reconciliations WHERE candidate_key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    for name in ("hypothesis_ids", "experiment_ids", "work_request_ids"):
        result[name] = json.loads(result.pop(name + "_json"))
    result["candidate"] = key
    return result


def _find_source(path: Path, key: str, title: str) -> str | None:
    markers = KNOWN_TITLE_MARKERS.get(key)
    with database(path) as connection:
        rows = connection.execute("SELECT id, title FROM research_sources ORDER BY created_at, id").fetchall()
        if markers:
            for row in rows:
                normalized = normalize_claim(row["title"])
                if all(normalize_claim(marker) in normalized for marker in markers):
                    return str(row["id"])
        provenance_marker = f"Legacy inventory {RECONCILIATION_VERSION}/{key}"
        row = connection.execute(
            "SELECT source_id FROM source_provenance WHERE provenance = ? ORDER BY captured_at, id LIMIT 1",
            (provenance_marker,),
        ).fetchone()
        if row is not None:
            return str(row["source_id"])
        normalized_title = normalize_claim(title)
        for row in rows:
            if normalize_claim(row["title"]) == normalized_title:
                return str(row["id"])
    return None


def _ensure_source(kb: ResearchKnowledgeBase, key: str) -> tuple[dict[str, Any], bool]:
    spec = SOURCES[key]
    existing_id = _find_source(kb.path, key, spec["title"])
    if existing_id:
        return kb.get_source(existing_id), False
    intake = kb.intake_source(
        title=spec["title"],
        source_type=spec["source_type"],
        summary=spec["summary"],
        platform=spec["source_type"] if spec["source_type"] in {"youtube", "tiktok"} else None,
        creator=spec.get("creator"),
        direct_url=spec.get("direct_url"),
        profile_url=spec.get("profile_url"),
        provenance=f"Legacy inventory {RECONCILIATION_VERSION}/{key}",
        confirm_distinct=True,
        distinct_rationale="Eigener Legacy-Kandidat mit materiell anderer Bezeichnung; keine automatische Titel-Zusammenführung.",
    )
    return intake["source"], intake["status"] == "NEW_SOURCE"


def _claim(workflow: ResearchWorkflow, source_id: str, text: str, scope: str) -> dict[str, Any]:
    normalized = normalize_claim(text)
    with database(workflow.path) as connection:
        row = connection.execute(
            "SELECT id FROM source_claims WHERE source_id = ? AND normalized_claim = ?",
            (source_id, normalized),
        ).fetchone()
    if row is not None:
        return workflow.get_source_claim(str(row["id"]))
    return workflow.capture_source_claim(
        source_id,
        claim=text,
        original_market_scope=scope,
        extraction_notes=f"Idempotenter Legacy-Abgleich {RECONCILIATION_VERSION}.",
    )


def _resolve_no_action(workflow: ResearchWorkflow, claim: Mapping[str, Any], rationale: str) -> None:
    if claim["resolutions"]:
        return
    workflow.resolve_claim_without_research(
        str(claim["id"]), resolution="NO_ACTION", rationale=rationale
    )


def _resolve_existing(
    workflow: ResearchWorkflow,
    claim: Mapping[str, Any],
    hypothesis_id: str,
    rationale: str,
) -> None:
    if any(str(item.get("hypothesis_id") or "") == hypothesis_id for item in claim["resolutions"]):
        return
    workflow.resolve_claim_with_existing_hypothesis(
        str(claim["id"]),
        hypothesis_id,
        rationale=rationale,
        stance="context",
    )


def _find_hypothesis(path: Path, *title_terms: str) -> str | None:
    terms = [normalize_claim(item) for item in title_terms]
    with database(path) as connection:
        for row in connection.execute("SELECT id, title FROM hypotheses ORDER BY created_at, id"):
            normalized = normalize_claim(row["title"])
            if all(term in normalized for term in terms):
                return str(row["id"])
    return None


def _ensure_new_hypothesis(
    workflow: ResearchWorkflow,
    claim: Mapping[str, Any],
    *,
    title: str,
    area: str,
    category: str,
    mechanism: str,
    rating: str,
    risks: str,
    asset_class: str,
    region: str,
    universe: str,
    timeframe: str,
    strategy: str | None,
) -> tuple[dict[str, Any], bool]:
    exact = workflow.knowledge.find_similar_hypotheses(
        title=title, claim=str(claim["claim_text"]), minimum_score=0, limit=1_000
    )
    exact = next((item for item in exact if item["exact_claim_match"]), None)
    if exact:
        _resolve_existing(workflow, claim, str(exact["id"]), "Exakter Claim bereits vorhanden.")
        return workflow.knowledge.get_hypothesis(str(exact["id"])), False
    created = workflow.create_hypothesis_from_claim(
        str(claim["id"]),
        title=title,
        area=area,
        category=category,
        mechanism=mechanism,
        external_evidence="medium",
        rating=rating,
        risks_limitations=risks,
        strategy=strategy,
        asset_class=asset_class,
        market_region=region,
        market_universe=universe,
        market_timeframe=timeframe,
    )
    return created, True


def _latest_capability(path: Path, hypothesis_id: str) -> dict[str, Any] | None:
    with database(path) as connection:
        row = connection.execute(
            "SELECT * FROM application_capability_assessments WHERE hypothesis_id = ? ORDER BY assessed_at DESC, rowid DESC LIMIT 1",
            (hypothesis_id,),
        ).fetchone()
    return None if row is None else dict(row)


def _ensure_capability(
    workflow: ResearchWorkflow,
    hypothesis_id: str,
    *,
    outcome: str,
    experiment_id: str | None,
    infrastructure: str,
    assets: Mapping[str, object],
    rationale: str,
) -> dict[str, Any]:
    existing = _latest_capability(workflow.path, hypothesis_id)
    if existing and existing["outcome"] == outcome and existing["experiment_id"] == experiment_id:
        return existing
    return workflow.record_application_assessment(
        hypothesis_id,
        experiment_id=experiment_id,
        outcome=outcome,
        feature_available=outcome != "NEW_DATA_REQUIRED",
        required_data_available=outcome != "NEW_DATA_REQUIRED",
        existing_research_test=experiment_id is not None,
        market_scope_reviewed=True,
        active_rule_exists=False,
        infrastructure_needed=infrastructure,
        existing_assets=assets,
        rationale=rationale,
    )


def _ensure_experiment(
    kb: ResearchKnowledgeBase,
    hypothesis_id: str,
    *,
    title: str,
    features: list[str],
    baseline: str,
) -> dict[str, Any]:
    detail = kb.get_hypothesis(hypothesis_id)
    existing = next((item for item in detail["experiments"] if item["title"] == title), None)
    if existing:
        return existing
    return kb.create_experiment(
        hypothesis_id,
        title=title,
        test_definition="Vorregistrierter inkrementeller Vergleich ohne Änderung der aktiven Strategie.",
        features=features,
        data_universe="Bestehendes versioniertes Swing-Research-Universum.",
        point_in_time_rules="Nur kausale Point-in-Time-Features; OOS und Walk-Forward vor Ergebnisbewertung.",
        baseline=baseline,
        parameters={"controls": "kontinuierliche und gleich breite Kontrollzonen"},
        test_status="PLANNED",
    )


def _ensure_experiment_scope(workflow: ResearchWorkflow, experiment_id: str) -> None:
    with database(workflow.path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM market_scope_assessments WHERE target_type='experiment' AND target_id=?",
            (experiment_id,),
        ).fetchone()
    if exists is None:
        workflow.record_market_scope(
            target_type="experiment",
            target_id=experiment_id,
            asset_class="EQUITIES",
            region="Bestehender SwingTrader-Scope",
            universe="Versioniertes liquides Swing-Research-Universum",
            timeframe="Daily; bestehende Forward-Horizonte",
            scope_notes="Eigener EQUITIES-Testscope; keine Cross-Market-Vererbung und keine automatische Integration.",
        )


def _ensure_actionable_request(
    workflow: ResearchWorkflow,
    *,
    source_id: str,
    hypothesis_id: str,
    experiment_id: str,
    capability: Mapping[str, Any],
) -> str | None:
    outcome = str(capability["outcome"])
    request_type = {
        "TESTABLE_NOW": "RESEARCH_TEST",
        "CODE_EXTENSION_REQUIRED": "CODE_EXTENSION",
        "NEW_DATA_REQUIRED": "DATA_PIPELINE",
    }.get(outcome)
    if request_type is None:
        return None
    request = workflow.create_work_request(
        hypothesis_id,
        capability_assessment_id=str(capability["id"]),
        experiment_id=experiment_id,
        source_id=source_id,
        request_type=request_type,
        task={
            "TESTABLE_NOW": "Führe den vorregistrierten inkrementellen Research-Test aus und schreibe das Resultat direkt in die KB.",
            "CODE_EXTENSION_REQUIRED": "Ergänze ausschließlich die im Experiment fehlenden kausalen Research-Features und führe danach den vorregistrierten Test aus.",
            "NEW_DATA_REQUIRED": "Baue die fehlende versionierte Point-in-Time-Datenpipeline für das bestehende Experiment; keine Strategieaktivierung.",
        }[outcome],
        expected_output="Experimentstatus, persistentes KB-Resultat und Artefakt-/Run-/DB-Referenzen.",
        required_infrastructure=str(capability["infrastructure_needed"]),
        scope={"hypothesis_id": hypothesis_id, "experiment_id": experiment_id, "no_cross_market_transfer": True},
        safeguards={"no_loss_repair": True, "no_threshold_tuning": True, "negative_results_retained": True},
        idempotency_key=f"{RECONCILIATION_VERSION}:{hypothesis_id}:{experiment_id}:{request_type}",
    )
    return str(request["id"])


def _record_reconciliation(
    path: Path,
    *,
    key: str,
    outcome: str,
    source_id: str | None,
    hypothesis_ids: list[str],
    experiment_ids: list[str],
    work_request_ids: list[str],
    rationale: str,
) -> dict[str, Any]:
    with database(path) as connection:
        connection.execute(
            """
            INSERT INTO legacy_research_reconciliations (
                candidate_key, candidate_name, outcome, source_id,
                hypothesis_ids_json, experiment_ids_json, work_request_ids_json,
                rationale, reconciled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                SOURCES[key]["name"],
                outcome,
                source_id,
                _json(hypothesis_ids),
                _json(experiment_ids),
                _json(work_request_ids),
                rationale,
                _timestamp(None),
            ),
        )
    return _existing_reconciliation(path, key) or {}


def _reconcile_candidate(
    kb: ResearchKnowledgeBase, workflow: ResearchWorkflow, key: str
) -> dict[str, Any]:
    previous = _existing_reconciliation(kb.path, key)
    if previous:
        previous["idempotent_replay"] = True
        return previous
    source, source_created = _ensure_source(kb, key)
    source_id = str(source["id"])
    hypotheses: list[str] = []
    experiments: list[str] = []
    requests: list[str] = []
    outcome = "IMPORT_SOURCE_ONLY" if source_created else "ALREADY_MIGRATED"
    rationale = "Source gegen URL-/ID-/Hash-/Provenienz- und Metadatenbestand geprüft."

    if key == "A":
        claim = _claim(workflow, source_id, "Pullback-Tiefe, bearish candle count und Buyer Confirmation könnten inkrementelle Information für Momentum-Fortsetzungen enthalten; 50 Prozent und 2R sind nur Benchmarks.", "EQUITIES / ETF; Daily Swing")
        idea, created = _ensure_new_hypothesis(
            workflow, claim,
            title="Pullback-Tiefe und Buyer Confirmation als inkrementelle Merkmale",
            area="swing_trader", category="Pullback / Momentum Continuation",
            mechanism="Pullback-Geometrie und abgeschlossene Käuferbestätigung können getrennte, messbare Fortsetzungsinformation liefern.",
            rating="B", risks="Keine magische 50-%-Marke; kontinuierliche Tiefe, Kosten, OOS/WF und alternative Stops/Exits getrennt prüfen.",
            asset_class="EQUITIES", region="Bestehender SwingTrader-Scope", universe="Versioniertes Aktien-/ETF-Research-Universum", timeframe="Daily; Tage bis Wochen", strategy="Long Pullback",
        )
        hypotheses.append(str(idea["id"]))
        _ensure_capability(workflow, str(idea["id"]), outcome="ALREADY_AVAILABLE", experiment_id=None, infrastructure="Keine neue Infrastruktur; bestehende Broad-Pullback-, Buyer-Confirmation- und Exit-Benchmark-Artefakte nutzen.", assets={"broad": "swing_broad_research.py", "policy": "swing_research_policy.py"}, rationale="Features und methodische Kontrollen sind bereits vorhanden; nur Wissen aktualisieren.")
        outcome = "CREATE_NEW_HYPOTHESIS" if created else "LINK_SOURCE_TO_EXISTING"
    elif key == "B":
        c1 = _claim(workflow, source_id, "Weather zu Yield und Weather zu handelbarem Corn-Preis sind getrennte Hypothesen; Point-in-Time-Daten, OOS, Walk-Forward und Multiple-Testing-Kontrolle sind erforderlich.", "GENERAL_METHOD / COMMODITIES")
        c2 = _claim(workflow, source_id, "Ein p-value oder Z-Score allein beweist keinen handelbaren Edge und Interaktionen müssen separat geprüft werden.", "GENERAL_METHOD")
        _resolve_no_action(workflow, c1, "Methodischer Research-Vertrag ist bereits projektweit verankert; konkretes Corn-Modell bleibt ohne eindeutigen Daten-/Projektauftrag offen.")
        _resolve_no_action(workflow, c2, "Methodisches Wissen aktualisiert; kein neues Trading-Feature oder Work Request.")
        outcome = "IMPORT_NEW_CLAIMS"
    elif key == "C":
        claim = _claim(workflow, source_id, "Candidate→Qualification→Signal ist eine sinnvolle Scanner-Architektur, beweist aber ohne Risiko-, Drawdown- und Tradezahlkontext keinen Edge.", "CROSS_ASSET / GENERAL_METHOD")
        _resolve_no_action(workflow, claim, "Bestehende Scanner-Architektur ist vorhanden; kein neuer Edge und kein Handlungsbedarf.")
        outcome = "NO_ACTION"
    elif key == "D":
        claim = _claim(workflow, source_id, "Pullbacks zwischen 61,8 und 78,6 Prozent könnten gegenüber kontinuierlicher Pullback-Tiefe und gleich breiten Non-Fib-Kontrollzonen besondere Entry-Qualität besitzen.", "EQUITIES / ETF; Daily Swing")
        idea, created = _ensure_new_hypothesis(
            workflow, claim,
            title="Fibonacci-Pullback-Zone gegen kontinuierliche und Non-Fib-Kontrollen",
            area="swing_trader", category="Pullback / Fibonacci Control",
            mechanism="Falls die Zone mehr als eine nachträgliche Narrativgrenze ist, muss sie robuste inkrementelle OOS-Information gegenüber Kontrollzonen zeigen.",
            rating="B", risks="Schwache externe Evidenz; keine weiteren Fib-Level bei negativem Ergebnis; Kosten, Tradezahl und Parameterplateau prüfen.",
            asset_class="EQUITIES", region="Bestehender SwingTrader-Scope", universe="Versioniertes Aktien-/ETF-Research-Universum", timeframe="Daily; Tage bis Wochen", strategy="Long Pullback",
        )
        hypotheses.append(str(idea["id"]))
        experiment = _ensure_experiment(kb, str(idea["id"]), title="Fib 61,8–78,6 gegen kontinuierliche und Non-Fib-Kontrollen", features=["pullback_depth", "fib_zone_0618_0786", "non_fib_control_zone"], baseline="Kontinuierliche Pullback-Tiefe ohne Fib-Sonderstatus.")
        experiments.append(str(experiment["id"]))
        _ensure_experiment_scope(workflow, str(experiment["id"]))
        capability = _ensure_capability(workflow, str(idea["id"]), outcome="TESTABLE_NOW", experiment_id=str(experiment["id"]), infrastructure="Bestehender Broad-Research-Pfad und bereits definierte Fib-Kontrollen.", assets={"broad": "swing_broad_research.py", "policy": "swing_research_policy.py"}, rationale="Test ist mit vorhandenen kausalen Pullback-/Fib-Features möglich; keine aktive Regel.")
        request_id = _ensure_actionable_request(workflow, source_id=source_id, hypothesis_id=str(idea["id"]), experiment_id=str(experiment["id"]), capability=capability)
        if request_id:
            requests.append(request_id)
        outcome = "CREATE_NEW_HYPOTHESIS" if created else "LINK_SOURCE_TO_EXISTING"
    elif key == "E":
        claim = _claim(workflow, source_id, "Überraschung relativ zur Point-in-Time-Erwartung kann informativer sein als der absolute Fundamental- oder Makrowert; ML benötigt saubere Historie, OOS/WF und Shadow/Paper-Nachweis.", "EQUITIES / MACRO / GENERAL_METHOD")
        idea, created = _ensure_new_hypothesis(
            workflow, claim,
            title="Point-in-Time Expectation- und Surprise-Features",
            area="cross_cutting", category="Fundamental / Macro Surprise",
            mechanism="Preise reagieren auf Abweichungen vom vorher bekannten Konsens; Erwartungen und Actuals müssen kausal getrennt sein.",
            rating="B", risks="Konsensrevisionen, Publication Lag, Leakage, kleine Samples und unbekannte Modellvielfalt.",
            asset_class="CROSS_ASSET", region="Je Datenquelle getrennt", universe="Nur Assets mit Point-in-Time-Konsens und Actuals", timeframe="Event-Horizonte getrennt", strategy=None,
        )
        hypotheses.append(str(idea["id"]))
        _ensure_capability(workflow, str(idea["id"]), outcome="ALREADY_AVAILABLE", experiment_id=None, infrastructure="Bestehende Surprise-, Event- und ML-Datenverträge nutzen; kein neues ML-Modell.", assets={"event": "swing_event_research.py", "ml_contract": "swing_ml_dataset_contract.py"}, rationale="Datenverträge und Surprise-Felder bestehen; konkretes Modell erst mit sauberer Historie.")
        outcome = "CREATE_NEW_HYPOTHESIS" if created else "LINK_SOURCE_TO_EXISTING"
    elif key == "F":
        claim = _claim(workflow, source_id, "COT-Teilnehmerklassen, relative Positionierung zu Open Interest, Änderungen und Extreme können nur mit Point-in-Time-Veröffentlichungszeit als Research-Kontext geprüft werden.", "FUTURES / FX / COMMODITIES")
        idea, created = _ensure_new_hypothesis(
            workflow, claim,
            title="COT-Positionierung als Point-in-Time Research-Kontext",
            area="cross_cutting", category="COT / Positioning",
            mechanism="Teilnehmerklassen und relative Positionsänderungen können Crowding oder Unwind-Risiko abbilden, sind aber kein pauschales Smart-Money-Signal.",
            rating="B", risks="Commercials sind nicht pauschal Smart Money; Non-reportables kein sauberer Retail-Proxy; Publication Lag und Markt-Mapping.",
            asset_class="FUTURES", region="CFTC-Märkte", universe="Explizit gemappte Futures-/FX-Kontexte", timeframe="Wöchentlich; 1W/4W/52W", strategy=None,
        )
        hypotheses.append(str(idea["id"]))
        _ensure_capability(workflow, str(idea["id"]), outcome="ALREADY_AVAILABLE", experiment_id=None, infrastructure="Bestehenden COT-Shadow-Layer und Markt-Mapping verwenden.", assets={"cot": "cot_positioning.py", "mapping": "config/cot_market_mapping.json"}, rationale="COT ist technisch bereits Point-in-Time und research-only umgesetzt; keine neue Infrastruktur.")
        outcome = "CREATE_NEW_HYPOTHESIS" if created else "LINK_SOURCE_TO_EXISTING"
    elif key in {"G", "H", "I"}:
        targets: list[tuple[str | None, str]] = []
        if key in {"G", "I"}:
            targets.extend([
                (_find_hypothesis(kb.path, "zinsdifferenz", "carry"), "FX Macro-/Carry-Komponente bereits als eigene Hypothese vorhanden."),
                (_find_hypothesis(kb.path, "fx-confluence"), "FX-Confluence bleibt getrennt und DEFERRED."),
            ])
        if key == "H":
            targets.append((_find_hypothesis(kb.path, "objektive system-invalidation"), "Methodischer Objektivitätsclaim ergänzt bestehende Governance-Hypothese."))
        claim_text = {
            "G": "Ein FX-Framework aus Macro Bias, COT, objektiven Levels, BOS, Opening/Volume und Fibonacci muss seine Einzelkomponenten getrennt validieren, bevor Confluence geprüft wird.",
            "H": "Technische Regeln müssen objektiv, reproduzierbar, backtestbar und statistisch prüfbar sein; gezeichnete Linien allein bewegen keinen Markt.",
            "I": "Macro Bias, COT und technische FX-Levels können erst nach unabhängiger Einzelvalidierung als begrenzte Confluence-Hypothese geprüft werden; mehr Filter bedeuten nicht automatisch höhere Wahrscheinlichkeit.",
        }[key]
        claim = _claim(workflow, source_id, claim_text, "FX" if key != "H" else "GENERAL_METHOD")
        linked = []
        for target, note in targets:
            if target:
                _resolve_existing(workflow, claim, target, note)
                linked.append(target)
        hypotheses.extend(linked)
        if not linked:
            _resolve_no_action(workflow, claim, "Kein hinreichend passender KB-Claim; methodisch dokumentiert, ohne neuen Edge oder Work Request.")
        outcome = "LINK_SOURCE_TO_EXISTING" if linked else "NO_ACTION"
    elif key == "J":
        claim = _claim(workflow, source_id, "Eine asymmetrische Investment Opportunity benötigt begrenzten fundamental begründeten Downside, Cash Runway und konkrete probability-weighted Catalysts; Net Cash relativ zur Market Cap allein ist kein Kaufsignal.", "EQUITIES / Investment Opportunities")
        idea, created = _ensure_new_hypothesis(
            workflow, claim,
            title="Bilanz-Downside und probability-weighted Catalysts als asymmetrische Opportunity",
            area="opportunity_scanner", category="Asymmetric Opportunity",
            mechanism="Bilanzpuffer kann Downside begrenzen, während konkrete Catalysts szenariogewichteten Upside liefern; Biotech bleibt binär.",
            rating="B", risks="Cash Burn, Debt, Catalyst priced in, klinische/regulatorische Binärrisiken und falsche Wahrscheinlichkeiten.",
            asset_class="EQUITIES", region="Global nach Datenabdeckung", universe="Bilanz- und Catalyst-geprüfte Einzelaktien", timeframe="Mittel- bis langfristig", strategy=None,
        )
        hypotheses.append(str(idea["id"]))
        _ensure_capability(workflow, str(idea["id"]), outcome="ALREADY_AVAILABLE", experiment_id=None, infrastructure="Bestehende Fundamental-, Szenario- und Opportunity-Scanner-Module nutzen.", assets={"fundamental": "fundamental_analysis.py", "scenarios": "scenario_analysis.py", "opportunities": "future_potential_analysis.py"}, rationale="Die benötigten Bilanz-/Szenario-Bausteine bestehen; Wissen aktualisieren, kein automatisches Kaufsignal.")
        outcome = "CREATE_NEW_HYPOTHESIS" if created else "LINK_SOURCE_TO_EXISTING"
    else:
        linked_hypotheses = {
            "K": [_find_hypothesis(kb.path, "zinsdifferenz", "carry")],
            "L": [_find_hypothesis(kb.path, "failed seller attempts")],
            "M": [_find_hypothesis(kb.path, "overnight", "intraday"), _find_hypothesis(kb.path, "langfristige investments")],
            "N": [_find_hypothesis(kb.path, "objektive system-invalidation"), _find_hypothesis(kb.path, "crypto-regimewechsel"), _find_hypothesis(kb.path, "modellkonsens")],
            "O": [_find_hypothesis(kb.path, "fx-confluence")],
        }[key]
        hypotheses.extend([item for item in linked_hypotheses if item])
        outcome = "ALREADY_MIGRATED" if not source_created else "IMPORT_SOURCE_ONLY"
        rationale = "Bereits vorhandene Live-Source samt Claims, Hypothesen, Experimenten und Capability-Stand wiedererkannt; keine Duplikate angelegt." if not source_created else "Source-Metadaten erfasst; ohne vorhandenen eindeutigen Claim wurde keine Hypothese erfunden."
        for hypothesis_id in hypotheses:
            detail = kb.get_hypothesis(hypothesis_id)
            experiments.extend(str(item["id"]) for item in detail["experiments"])
            capability = _latest_capability(kb.path, hypothesis_id)
            if capability and capability.get("experiment_id"):
                request_id = _ensure_actionable_request(
                    workflow,
                    source_id=source_id,
                    hypothesis_id=hypothesis_id,
                    experiment_id=str(capability["experiment_id"]),
                    capability=capability,
                )
                if request_id:
                    requests.append(request_id)

    return _record_reconciliation(
        kb.path,
        key=key,
        outcome=outcome,
        source_id=source_id,
        hypothesis_ids=sorted(set(hypotheses)),
        experiment_ids=sorted(set(experiments)),
        work_request_ids=sorted(set(requests)),
        rationale=rationale,
    )


def reconcile_legacy_inventory(path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    path = Path(path)
    before = _counts(path) if path.exists() else {name: 0 for name in ("sources", "source_claims", "hypotheses", "experiments", "results", "work_requests", "ledger_events", "integration_candidates")}
    kb = ResearchKnowledgeBase(path)
    workflow = ResearchWorkflow(path)
    results = [_reconcile_candidate(kb, workflow, key) for key in SOURCES]
    after = _counts(path)
    return {
        "version": RECONCILIATION_VERSION,
        "before": before,
        "after": after,
        "candidates": results,
        "legacy_backlog_complete": "UNKNOWN",
        "reason": "Mehrere Legacy-Videos besitzen weder direkte URL/Content-ID noch Datei-Hash; vollständige Source-Identität ist deshalb nicht belegbar.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotenter A–O-Abgleich der Research Knowledge Base")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--json", action="store_true", help="Maschinenlesbaren Bericht ausgeben")
    args = parser.parse_args()
    report = reconcile_legacy_inventory(args.database)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"Legacy-Abgleich {report['version']}: {report['legacy_backlog_complete']}")
    for item in report["candidates"]:
        print(f"{item['candidate']}: {item['outcome']} · Source={item['source_id']}")


if __name__ == "__main__":
    main()
