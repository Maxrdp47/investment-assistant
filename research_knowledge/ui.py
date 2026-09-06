from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from .schema import (
    ALLOWED_AREAS,
    ALLOWED_HYPOTHESIS_STATUSES,
    ALLOWED_RATINGS,
    DEFAULT_DATABASE_PATH,
    RATING_GUIDANCE,
)
from .store import ResearchKnowledgeBase
from .workflow import ResearchWorkflow


AREA_LABELS = {
    "swing_trader": "SwingTrader",
    "opportunity_scanner": "Opportunity Scanner",
    "investment": "Investment",
    "cross_cutting": "Übergreifend",
}
EVIDENCE_LABELS = {"weak": "schwach", "medium": "mittel", "strong": "stark"}
STANCE_LABELS = {
    "supports": "unterstützt",
    "contradicts": "widerspricht",
    "mixed": "gemischt",
    "context": "Kontext",
}
CONCLUSION_LABELS = {
    "supports": "unterstützt",
    "contradicts": "widerspricht",
    "mixed": "gemischt",
    "inconclusive": "nicht eindeutig",
    "negative": "negatives Ergebnis",
}


def _filter_choice(label: str, values: list[str], *, key: str) -> str | None:
    selected = st.selectbox(label, ["Alle", *values], key=key)
    return None if selected == "Alle" else selected


def hypothesis_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Titel": item["title"],
            "Status": item["current_status"],
            "A/B/C": item["rating"],
            "Bereich": AREA_LABELS.get(str(item["area"]), item["area"]),
            "Kategorie": item["category"],
            "Evidenz": EVIDENCE_LABELS.get(
                str(item.get("effective_external_evidence") or item["external_evidence"]),
                item.get("effective_external_evidence") or item["external_evidence"],
            ),
            "Strategie": item.get("strategy") or "–",
            "Assetklasse": item.get("asset_class") or "–",
            "Quellen": item["source_count"],
            "Experimente": item["experiment_count"],
            "Ergebnisse": item["result_count"],
            "Negative Ergebnisse": item["negative_result_count"],
            "Früher verworfen": "Ja" if item["was_rejected"] else "Nein",
        }
        for item in rows
    ]


def _result_metric_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    labels = (
        ("Sample Size", "sample_size"),
        ("Trefferquote", "hit_rate"),
        ("Expectancy", "expectancy"),
        ("Profit Factor", "profit_factor"),
        ("MFE", "mfe"),
        ("MAE", "mae"),
        ("Drawdown", "drawdown"),
        ("R-Multiples", "r_multiples"),
        ("Kosten", "costs"),
        ("Slippage", "slippage"),
    )
    return [
        {"Kennzahl": label, "Wert": result.get(key)}
        for label, key in labels
        if result.get(key) is not None
    ]


def result_lifecycle_status(result: dict[str, Any]) -> str | None:
    """Expose a terminal challenger status without changing hypothesis semantics."""

    validation = result.get("validation")
    if not isinstance(validation, dict):
        return None
    if (
        result.get("conclusion") == "negative"
        and validation.get("status") == "VALIDATION_FAIL"
        and validation.get("next_stage_allowed") is False
    ):
        return "REJECTED_AT_VALIDATION"
    return None


def result_validation_assessment_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for assessment in result.get("validation_assessments") or ():
        rows.append(
            {
                "Richtung": assessment["result_direction"],
                "OOS": assessment["oos_status"],
                "Walk-Forward": assessment["walk_forward_status"],
                "External/Unseen": assessment["external_unseen_status"],
                "Forward": assessment["forward_status"],
                "Paper": assessment["paper_status"],
                "Sample Size": assessment["sample_size_status"],
                "Unsicherheit": assessment["uncertainty_status"],
                "Kosten/Slippage": assessment["costs_slippage_status"],
                "Datenqualität": assessment["data_quality_status"],
                "Leakage": assessment["leakage_status"],
                "PIT": assessment["pit_status"],
                "Kritischer Blocker": "Ja" if assessment["critical_blocker"] else "Nein",
                "Begründung": assessment["rationale"],
            }
        )
    return rows


def _render_sources(detail: dict[str, Any]) -> None:
    st.subheader("Quellen und externe Evidenz")
    if not detail["sources"]:
        st.info("Noch keine Quelle mit dieser Hypothese verknüpft.")
        return
    def transcription_label(source: dict[str, Any]) -> str:
        records = source.get("transcriptions") or []
        if not records:
            return "–"
        latest = records[-1]
        if latest["status"] in {"EXISTING", "GENERATED"} and not latest.get("artifact_available"):
            return f"{latest['status']} (Artefakt fehlt)"
        return str(latest["status"])

    st.dataframe(
        [
            {
                "Titel": source["title"],
                "Typ": source["source_type"],
                "Plattform": (source["provenance"][-1].get("platform") if source["provenance"] else None) or "–",
                "Creator": (source["provenance"][-1].get("creator") if source["provenance"] else None) or "–",
                "Content-ID": (source["provenance"][-1].get("content_id") if source["provenance"] else None) or "–",
                "Normalisierte URL": (source["provenance"][-1].get("normalized_url") if source["provenance"] else None) or "–",
                "Fingerprint": (source["provenance"][-1].get("source_fingerprint") if source["provenance"] else None) or "–",
                "Transcript": transcription_label(source),
                "Datum": source["source_date"] or "–",
                "Richtung": STANCE_LABELS.get(source["stance"], source["stance"]),
                "Referenz": source["reference"] or "–",
                "Zusammenfassung": source["neutral_summary"],
                "Einordnung": source["link_note"] or "–",
            }
            for source in detail["sources"]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_experiments(detail: dict[str, Any]) -> None:
    st.subheader("Experimente und Ergebnisse")
    if not detail["experiments"]:
        st.info("Noch kein Experiment verknüpft. Das ist für A-Einträge ausdrücklich zulässig.")
        return
    for experiment in detail["experiments"]:
        with st.expander(
            f"{experiment['title']} · {experiment['current_status']} · {len(experiment['results'])} Ergebnis(se)",
            expanded=False,
        ):
            st.markdown(f"**Testdefinition:** {experiment['test_definition']}")
            st.write(f"Features: {', '.join(experiment['features'])}")
            st.write(f"Datenuniversum: {experiment['data_universe']}")
            period = " bis ".join(
                value for value in (experiment["period_start"], experiment["period_end"]) if value
            )
            st.write(f"Zeitraum: {period or 'nicht festgelegt'}")
            st.write(f"Point-in-Time-Regeln: {experiment['point_in_time_rules']}")
            st.write(f"Baseline: {experiment['baseline']}")
            st.write("Parameter/Varianten:", experiment["parameters"])
            if experiment["references"]:
                st.caption(
                    "Referenzierte bestehende Research-Artefakte: "
                    + ", ".join(
                        f"{item['system']}/{item['record_type']}/{item['record_id']}"
                        for item in experiment["references"]
                    )
                )
            for result in experiment["results"]:
                lifecycle_status = result_lifecycle_status(result)
                st.markdown(
                    f"**{result['title']} · {CONCLUSION_LABELS.get(result['conclusion'], result['conclusion'])}"
                    + (f" · `{lifecycle_status}`" if lifecycle_status else "")
                    + "**"
                )
                metric_rows = _result_metric_rows(result)
                if metric_rows:
                    st.dataframe(metric_rows, use_container_width=True, hide_index=True)
                st.write(result["interpretation"])
                stage_labels = (
                    ("In-Sample", "in_sample"),
                    ("Validation", "validation"),
                    ("Out-of-Sample", "out_of_sample"),
                    ("Walk-Forward", "walk_forward"),
                    ("Forward", "forward"),
                    ("Papertrade", "papertrade"),
                )
                available_stages = [
                    {"Stufe": label, "Ergebnis": result[key]}
                    for label, key in stage_labels
                    if result.get(key) is not None
                ]
                if available_stages:
                    st.dataframe(available_stages, use_container_width=True, hide_index=True)
                assessment_rows = result_validation_assessment_rows(result)
                if assessment_rows:
                    st.markdown("**Resultat-Gate-Bewertung**")
                    st.dataframe(assessment_rows, use_container_width=True, hide_index=True)


def _render_ledger(detail: dict[str, Any]) -> None:
    st.subheader("Evidence Ledger")
    st.caption("Chronologisch und append-only: Frühere Entscheidungen werden nicht überschrieben.")
    st.dataframe(
        [
            {
                "Zeitpunkt": event["event_at"],
                "Ereignis": event["event_type"],
                "Zusammenfassung": event["summary"],
                "Status vorher": event["from_status"] or "–",
                "Status danach": event["to_status"] or "–",
            }
            for event in detail["ledger"]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_workflow(workflow: dict[str, Any]) -> None:
    st.subheader("Research-Workflow")
    status_cols = st.columns(6)
    status_cols[0].metric("Source-Claims", len(workflow["source_claims"]))
    status_cols[1].metric("App-Abgleiche", len(workflow["application_assessments"]))
    status_cols[2].metric("Market Scopes", len(workflow["market_scopes"]))
    status_cols[3].metric("Integration Candidates", len(workflow["integration_candidates"]))
    status_cols[4].metric("Work Requests", len(workflow["work_requests"]))
    status_cols[5].metric("Validierungs-Auswahl", len(workflow["validation_evidence"]))
    st.caption(
        "Workflow-Einträge steuern nur Research. Sie aktivieren weder Features noch Filter, "
        "Strategien oder Orders."
    )

    if workflow["source_claims"]:
        st.markdown("**Claims und Wissensabgleich**")
        st.dataframe(
            [
                {
                    "Quelle": item["source_title"],
                    "Claim": item["claim_text"],
                    "Quellenscope": item["original_market_scope"],
                    "Auflösung": item["resolution"],
                    "Neubewertungsgrund": item["new_evidence_basis"] or "–",
                    "Begründung": item["resolution_rationale"],
                }
                for item in workflow["source_claims"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if workflow["evidence_assessments"]:
        st.markdown("**Evidenz- und Confidence-Historie**")
        st.dataframe(
            [
                {
                    "Zeitpunkt": item["assessed_at"],
                    "Stärke": EVIDENCE_LABELS.get(item["strength"], item["strength"]),
                    "Confidence": item["confidence"] if item["confidence"] is not None else "–",
                    "Begründung": item["rationale"],
                }
                for item in workflow["evidence_assessments"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if workflow["application_assessments"]:
        st.markdown("**Abgleich mit der bestehenden Anwendung**")
        st.dataframe(
            [
                {
                    "Zeitpunkt": item["assessed_at"],
                    "Ergebnis": item["outcome"],
                    "Feature vorhanden": "Ja" if item["feature_available"] else "Nein",
                    "Daten vorhanden": "Ja" if item["required_data_available"] else "Nein",
                    "Research-Test vorhanden": "Ja" if item["existing_research_test"] else "Nein",
                    "Aktive Regel vorhanden": "Ja" if item["active_rule_exists"] else "Nein",
                    "Infrastruktur": item["infrastructure_needed"],
                    "Begründung": item["rationale"],
                }
                for item in workflow["application_assessments"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if workflow["market_scopes"]:
        st.markdown("**Getrennte Market Scopes**")
        st.dataframe(
            [
                {
                    "Gilt für": item["target_type"],
                    "Assetklasse": item["asset_class"],
                    "Region": item["region"],
                    "Universum": item["universe"],
                    "Zeitrahmen": item["timeframe"],
                    "Einschränkung": item["scope_notes"],
                }
                for item in workflow["market_scopes"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if workflow["work_requests"]:
        st.markdown("**DB-Chat ↔ Work-Chat Requests**")
        st.dataframe(
            [
                {
                    "ID": item["id"],
                    "Typ": item["request_type"],
                    "Status": item["current_status"],
                    "Aufgabe": item["task"],
                    "Ergebnis": item["result_id"],
                    "Blocker": item["blocker_reason"],
                }
                for item in workflow["work_requests"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if workflow["validation_evidence"]:
        st.markdown("**Explizit ausgewählte Validierungsevidenz**")
        st.dataframe(
            workflow["validation_evidence"],
            use_container_width=True,
            hide_index=True,
        )

    for candidate in workflow["integration_candidates"]:
        with st.expander(
            f"INTEGRATION_CANDIDATE · {', '.join(candidate['feature_combination'])}",
            expanded=False,
        ):
            st.warning(
                "Dieser Eintrag ist keine aktive Strategieänderung. Freigabe und tatsächliche "
                "Integration werden separat dokumentiert."
            )
            gate_labels = (
                ("Inkrementeller Mehrwert", "incremental_value_confirmed", "incremental_value_assessment"),
                ("OOS / Walk-Forward", "oos_walk_forward_confirmed", "oos_walk_forward_assessment"),
                ("Forward / Papertrade", "forward_paper_confirmed", "forward_paper_assessment"),
                ("Sample Size", "sample_size_sufficient", "sample_size_assessment"),
                ("Kosten / Slippage", "costs_included", "costs_slippage_assessment"),
                ("Feature-Redundanz", "redundancy_acceptable", "feature_redundancy_assessment"),
                ("Komplexität", "complexity_justified", "complexity_assessment"),
                ("Overfiltering", "overfiltering_acceptable", "overfiltering_assessment"),
                ("Tradezahl", "trade_count_acceptable", "overfiltering_assessment"),
                ("Market Scope", "market_scope_validated", "market_scope_assessment"),
                ("Einfachere Lösung bevorzugt", "simpler_solution_preferred", "simpler_variant_assessment"),
            )
            st.dataframe(
                [
                    {
                        "Gate": label,
                        "Bestanden": "Ja" if candidate[flag] else "Nein",
                        "Bewertung": candidate[assessment],
                    }
                    for label, flag, assessment in gate_labels
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"Tradezahl: Baseline {candidate['baseline_trade_count']} · Candidate {candidate['candidate_trade_count']}"
            )
            st.write(f"Aktuelle Einschränkungen: {candidate['limitations']}")
            if candidate["decisions"]:
                st.markdown("**Bewusste Integrationsentscheidungen**")
                st.dataframe(candidate["decisions"], use_container_width=True, hide_index=True)
            if candidate["events"]:
                st.markdown("**Tatsächliche externe Integrationsereignisse**")
                st.dataframe(candidate["events"], use_container_width=True, hide_index=True)


def render_research_knowledge_base(
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    st.title("Research Knowledge Base")
    st.caption("Dauerhafte Research-Erinnerung · keine Tradingstrategie · keine automatische Filter- oder Orderwirkung")
    st.info(
        "Ein externer Input kann niemals allein durch seine Quelle validiert werden. "
        "VALIDATED benötigt ein explizit ausgewähltes unterstützendes Resultat eines "
        "abgeschlossenen Experiments mit bestandenem Scope-, OOS-, Walk-Forward-, "
        "PIT-, Leakage- und allen weiteren geltenden Gates."
    )
    try:
        knowledge = ResearchKnowledgeBase(database_path)
        workflow_service = ResearchWorkflow(database_path)
        health = knowledge.health()
        workflow_summary = workflow_service.summary()
        filter_values = knowledge.filter_values()
    except Exception as exc:
        st.error(f"Die Research Knowledge Base konnte nicht geöffnet werden: {exc}")
        return

    metrics = st.columns(6)
    metrics[0].metric("Hypothesen", health["hypotheses"])
    metrics[1].metric("Quellen", health["sources"])
    metrics[2].metric("Experimente", health["experiments"])
    metrics[3].metric("Ergebnisse", health["results"])
    metrics[4].metric("Ledger-Ereignisse", health["ledger_events"])
    metrics[5].metric("Work Requests", health["work_requests"])
    st.caption(
        f"Workflow: {workflow_summary['source_claims']} Claims · "
        f"{workflow_summary['capability_assessments']} App-Abgleiche · "
        f"{workflow_summary['integration_candidates']} Integration Candidates · "
        f"{workflow_summary['work_requests']} Work Requests · "
        f"{workflow_summary['integration_events']} dokumentierte Integrationsereignisse"
    )

    source_claims = workflow_service.list_source_claims()
    with st.expander(
        f"Claim Intake und Wissensabgleich · {len(source_claims)} Einträge",
        expanded=False,
    ):
        if source_claims:
            st.dataframe(
                [
                    {
                        "Quelle": item["source_title"],
                        "Claim": item["claim_text"],
                        "Primäre Domain": item["primary_domain"] or "–",
                        "Sekundäre Domains": ", ".join(item["secondary_domains"]) or "–",
                        "Unterkategorie": item["subcategory"] or "–",
                        "Trading-Relevanz": item["trading_relevance"] or "–",
                        "Verifikation": item["verification_state"] or "UNVERIFIED",
                        "Herkunft": item["origin_system"] or "Direkt-Intake",
                        "ENTRY Quellenprüfung": item["source_verification_status"] or "–",
                        "Empirischer Test": item["empirical_test_status"] or "–",
                        "Research-Status": item["research_status"] or "–",
                        "Tags": item["tags_text"] or "–",
                        "Verification-Confidence": (
                            f"{float(item['verification_confidence']):.1f} %"
                            if item["verification_confidence"] is not None
                            else "–"
                        ),
                        "Ursprünglicher Scope": item["original_market_scope"],
                        "Ähnliche Einträge": item["match_count"],
                        "Höchste Ähnlichkeit": (
                            "–"
                            if item["top_similarity"] is None
                            else f"{float(item['top_similarity']) * 100:.1f} %"
                        ),
                        "Verworfenes Wissen gefunden": (
                            "Ja" if item["matched_rejected_knowledge"] else "Nein"
                        ),
                        "Auflösung": item["latest_resolution"] or "OFFEN",
                        "Hypothese": item["resolved_hypothesis_title"] or "–",
                    }
                    for item in source_claims
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Noch keine extrahierten Source-Claims erfasst.")

    st.subheader("Hypothesen suchen")
    query = st.text_input("Freitext", key="research_kb_query")
    first_filters = st.columns(4)
    with first_filters[0]:
        status = _filter_choice("Status (aktuell oder historisch)", list(ALLOWED_HYPOTHESIS_STATUSES), key="research_kb_status")
    with first_filters[1]:
        rating = _filter_choice("A/B/C", list(ALLOWED_RATINGS), key="research_kb_rating")
    with first_filters[2]:
        area_label = _filter_choice("Bereich", [AREA_LABELS[item] for item in ALLOWED_AREAS], key="research_kb_area")
        area = None if area_label is None else next(key for key, value in AREA_LABELS.items() if value == area_label)
    with first_filters[3]:
        category = _filter_choice("Kategorie", filter_values["categories"], key="research_kb_category")
    second_filters = st.columns(4)
    with second_filters[0]:
        feature = _filter_choice("Feature", filter_values["features"], key="research_kb_feature")
    with second_filters[1]:
        strategy = _filter_choice("Strategie", filter_values["strategies"], key="research_kb_strategy")
    with second_filters[2]:
        asset_class = _filter_choice("Assetklasse", filter_values["asset_classes"], key="research_kb_asset_class")
    with second_filters[3]:
        source = st.text_input("Quelle", key="research_kb_source")

    rows = knowledge.search_hypotheses(
        query=query,
        category=category,
        feature=feature,
        strategy=strategy,
        asset_class=asset_class,
        source=source,
        status=status,
        rating=rating,
        area=area,
    )
    st.caption(f"{len(rows)} passende Hypothese(n)")
    if not rows:
        st.info(
            "Noch keine passenden Einträge. Bestehende Projekthypothesen werden bewusst nicht blind rekonstruiert; "
            "die Knowledge Base wird nur mit eindeutig belegten Informationen befüllt."
        )
        return
    st.dataframe(hypothesis_table_rows(rows), use_container_width=True, hide_index=True)

    labels = {
        f"{item['title']} · {item['current_status']} · {item['rating']} · {str(item['id'])[:8]}": str(item["id"])
        for item in rows
    }
    selected_label = st.selectbox("Detailansicht", list(labels), key="research_kb_detail")
    detail = knowledge.get_hypothesis(labels[selected_label])
    st.divider()
    st.subheader(detail["title"])
    overview = st.columns(4)
    overview[0].metric("Status", detail["current_status"])
    overview[1].metric("A/B/C", detail["rating"])
    overview[2].metric(
        "Evidenz",
        EVIDENCE_LABELS.get(detail["effective_external_evidence"], detail["effective_external_evidence"]),
    )
    overview[3].metric("Bereich", AREA_LABELS.get(detail["area"], detail["area"]))
    st.caption(f"Research-Priorität {detail['rating']}: {RATING_GUIDANCE[detail['rating']]}")
    st.markdown(f"**Überprüfbare Behauptung:** {detail['claim']}")
    st.markdown(f"**Vermuteter Mechanismus:** {detail['mechanism']}")
    st.markdown(f"**Risiken/Limitierungen:** {detail['risks_limitations']}")
    if detail["relations"]:
        st.caption(
            "Verwandte Hypothesen: "
            + ", ".join(
                f"{item['other_title']} ({item['relation_type']})" for item in detail["relations"]
            )
        )
    _render_workflow(workflow_service.workflow_for_hypothesis(detail["id"]))
    _render_sources(detail)
    _render_experiments(detail)
    _render_ledger(detail)
