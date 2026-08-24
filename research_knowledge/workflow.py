from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import (
    ALLOWED_CAPABILITY_OUTCOMES,
    ALLOWED_CLAIM_RESOLUTIONS,
    ALLOWED_EVIDENCE_STRENGTHS,
    ALLOWED_INTEGRATION_DECISIONS,
    ALLOWED_INTEGRATION_EVENTS,
    ALLOWED_MARKET_SCOPE_TARGETS,
    ALLOWED_RETEST_BASES,
    DEFAULT_DATABASE_PATH,
    database,
)
from .store import (
    ResearchKnowledgeBase,
    _choice,
    _claim_fingerprint,
    _id,
    _json,
    _json_value,
    _number,
    _optional,
    _required,
    _timestamp,
    normalize_claim,
)


MAX_INTEGRATION_FEATURES = 5


def _flag(value: object, label: str) -> int:
    if not isinstance(value, bool):
        raise ValueError(f"{label} muss ausdrücklich wahr oder falsch sein.")
    return int(value)


def _count(value: object, label: str, *, positive: bool = False) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} muss eine ganze Zahl sein.") from exc
    if not number.is_integer() or number < (1 if positive else 0):
        minimum = "größer als null" if positive else "nicht negativ"
        raise ValueError(f"{label} muss ganzzahlig und {minimum} sein.")
    return int(number)


class ResearchWorkflow:
    """Intake-to-integration-review workflow over the existing knowledge model.

    The workflow only records research decisions.  It has no import or callback
    into scanners, strategies, scoring, paper trading or order execution.
    """

    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path)
        self.knowledge = ResearchKnowledgeBase(self.path)

    def capture_source_claim(
        self,
        source_id: str,
        *,
        claim: str,
        original_market_scope: str,
        extraction_notes: str = "",
        similarity_threshold: float = 0.2,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        if similarity_threshold < 0 or similarity_threshold > 1:
            raise ValueError("Ähnlichkeitsschwelle muss zwischen 0 und 1 liegen.")
        source = self.knowledge.get_source(source_id)
        claim_text = _required(claim, "Extrahierter Claim")
        normalized = normalize_claim(claim_text)
        fingerprint = _claim_fingerprint(normalized)
        timestamp = _timestamp(created_at)
        matches = self.knowledge.find_similar_hypotheses(
            title=str(source["title"]),
            claim=claim_text,
            minimum_score=similarity_threshold,
            limit=25,
        )
        with database(self.path) as connection:
            existing = connection.execute(
                "SELECT id FROM source_claims WHERE source_id = ? AND claim_fingerprint = ?",
                (source_id, fingerprint),
            ).fetchone()
            if existing is not None:
                raise ValueError("Dieser Claim wurde aus derselben Quelle bereits erfasst.")
            claim_id = _id()
            connection.execute(
                """
                INSERT INTO source_claims (
                    id, source_id, claim_text, normalized_claim, claim_fingerprint,
                    original_market_scope, extraction_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    source_id,
                    claim_text,
                    normalized,
                    fingerprint,
                    _required(original_market_scope, "Ursprünglicher Market Scope"),
                    str(extraction_notes or "").strip(),
                    timestamp,
                ),
            )
            connection.executemany(
                """
                INSERT INTO source_claim_matches (
                    id, claim_id, hypothesis_id, similarity_score, exact_claim_match,
                    hypothesis_status, was_rejected, source_count, experiment_count,
                    result_count, rejection_reason, matched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        _id(),
                        claim_id,
                        item["id"],
                        item["similarity_score"],
                        int(bool(item["exact_claim_match"])),
                        item["current_status"],
                        int(bool(item["was_rejected"])),
                        item["source_count"],
                        item["experiment_count"],
                        item["result_count"],
                        item["rejection_reason"],
                        timestamp,
                    )
                    for item in matches
                ],
            )
        return self.get_source_claim(claim_id)

    def get_source_claim(self, claim_id: str) -> dict[str, Any]:
        with database(self.path) as connection:
            row = connection.execute(
                """
                SELECT sc.*, s.title AS source_title, s.source_type, s.reference
                FROM source_claims sc
                JOIN research_sources s ON s.id = sc.source_id
                WHERE sc.id = ?
                """,
                (claim_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unbekannter Source-Claim: {claim_id}")
            result = dict(row)
            result["matches"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT scm.*, h.title AS hypothesis_title, h.claim AS hypothesis_claim
                    FROM source_claim_matches scm
                    JOIN hypotheses h ON h.id = scm.hypothesis_id
                    WHERE scm.claim_id = ?
                    ORDER BY scm.similarity_score DESC, scm.matched_at, scm.id
                    """,
                    (claim_id,),
                )
            ]
            result["resolutions"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT scr.*, h.title AS hypothesis_title
                    FROM source_claim_resolutions scr
                    LEFT JOIN hypotheses h ON h.id = scr.hypothesis_id
                    WHERE scr.claim_id = ?
                    ORDER BY scr.resolved_at, scr.id
                    """,
                    (claim_id,),
                )
            ]
        return result

    def list_source_claims(self, *, limit: int = 200) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1_000:
            raise ValueError("Limit muss zwischen 1 und 1000 liegen.")
        with database(self.path) as connection:
            rows = connection.execute(
                """
                SELECT
                    sc.*,
                    s.title AS source_title,
                    s.source_type,
                    (SELECT scr.resolution FROM source_claim_resolutions scr
                     WHERE scr.claim_id = sc.id
                     ORDER BY scr.resolved_at DESC, scr.rowid DESC LIMIT 1) AS latest_resolution,
                    (SELECT scr.hypothesis_id FROM source_claim_resolutions scr
                     WHERE scr.claim_id = sc.id
                     ORDER BY scr.resolved_at DESC, scr.rowid DESC LIMIT 1) AS resolved_hypothesis_id,
                    (SELECT h.title FROM source_claim_resolutions scr
                     JOIN hypotheses h ON h.id = scr.hypothesis_id
                     WHERE scr.claim_id = sc.id
                     ORDER BY scr.resolved_at DESC, scr.rowid DESC LIMIT 1) AS resolved_hypothesis_title,
                    (SELECT COUNT(*) FROM source_claim_matches scm
                     WHERE scm.claim_id = sc.id) AS match_count,
                    (SELECT scm.similarity_score FROM source_claim_matches scm
                     WHERE scm.claim_id = sc.id
                     ORDER BY scm.similarity_score DESC, scm.rowid LIMIT 1) AS top_similarity,
                    (SELECT MAX(scm.was_rejected) FROM source_claim_matches scm
                     WHERE scm.claim_id = sc.id) AS matched_rejected_knowledge
                FROM source_claims sc
                JOIN research_sources s ON s.id = sc.source_id
                ORDER BY sc.created_at DESC, sc.id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(item) for item in rows]

    def resolve_claim_with_existing_hypothesis(
        self,
        claim_id: str,
        hypothesis_id: str,
        *,
        rationale: str,
        stance: str = "context",
        link_note: str = "",
        new_evidence_basis: str | None = None,
        updated_evidence_strength: str | None = None,
        evidence_confidence: object | None = None,
        resolved_at: object | None = None,
    ) -> dict[str, Any]:
        claim = self.get_source_claim(claim_id)
        hypothesis = self.knowledge.get_hypothesis(hypothesis_id, include_details=False)
        timestamp = _timestamp(resolved_at)
        basis = (
            None
            if new_evidence_basis is None
            else _choice(new_evidence_basis, ALLOWED_RETEST_BASES, "Neubewertungsgrund")
        )
        if hypothesis["current_status"] == "REJECTED" and basis is None:
            # Linking remains allowed, but the resolution must not imply an automatic retest.
            resolution_note = " Quelle verknüpft; kein erneuter Test ohne neue Grundlage."
        else:
            resolution_note = ""
        rationale_value = _required(rationale, "Wissensabgleich-Begründung") + resolution_note
        if updated_evidence_strength is None and evidence_confidence is not None:
            raise ValueError("Confidence kann nur zusammen mit einer Evidenzstärke aktualisiert werden.")
        strength_value = (
            None
            if updated_evidence_strength is None
            else _choice(
                updated_evidence_strength,
                ALLOWED_EVIDENCE_STRENGTHS,
                "Evidenzstärke",
            )
        )
        confidence_value = _number(evidence_confidence, "Evidenz-Confidence", minimum=0)
        if confidence_value is not None and confidence_value > 100:
            raise ValueError("Evidenz-Confidence darf höchstens 100 betragen.")
        with database(self.path) as connection:
            existing_link = connection.execute(
                """
                SELECT id FROM hypothesis_sources
                WHERE hypothesis_id = ? AND source_id = ?
                """,
                (hypothesis_id, claim["source_id"]),
            ).fetchone()
            if existing_link is None:
                connection.execute(
                    """
                    INSERT INTO hypothesis_sources (
                        id, hypothesis_id, source_id, stance, note, linked_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id(),
                        hypothesis_id,
                        claim["source_id"],
                        _choice(stance, ("supports", "contradicts", "mixed", "context"), "Evidenzrichtung"),
                        str(link_note or "").strip(),
                        timestamp,
                    ),
                )
            resolution_id = _id()
            connection.execute(
                """
                INSERT INTO source_claim_resolutions (
                    id, claim_id, resolution, hypothesis_id, new_evidence_basis,
                    rationale, resolved_at
                ) VALUES (?, ?, 'LINKED_EXISTING', ?, ?, ?, ?)
                """,
                (resolution_id, claim_id, hypothesis_id, basis, rationale_value, timestamp),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, source_id, metadata_json
                ) VALUES (?, 'claim_linked_existing', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    f"Neuer Claim aus „{claim['source_title']}“ dem bestehenden Wissen zugeordnet: {rationale_value}",
                    claim["source_id"],
                    _json(
                        {
                            "claim_id": claim_id,
                            "claim": claim["claim_text"],
                            "new_evidence_basis": basis,
                            "source_link_created": existing_link is None,
                        }
                    ),
                ),
            )
            if strength_value is not None:
                evidence_rationale = (
                    f"Evidenz nach Source-Claim {claim_id} neu bewertet: {rationale_value}"
                )
                connection.execute(
                    """
                    INSERT INTO hypothesis_evidence_assessments (
                        id, hypothesis_id, source_id, strength, confidence,
                        rationale, assessed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id(),
                        hypothesis_id,
                        claim["source_id"],
                        strength_value,
                        confidence_value,
                        evidence_rationale,
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO evidence_ledger (
                        hypothesis_id, event_type, event_at, summary,
                        source_id, metadata_json
                    ) VALUES (?, 'evidence_reassessed', ?, ?, ?, ?)
                    """,
                    (
                        hypothesis_id,
                        timestamp,
                        evidence_rationale,
                        claim["source_id"],
                        _json(
                            {
                                "strength": strength_value,
                                "confidence": confidence_value,
                            }
                        ),
                    ),
                )
        return self.get_source_claim(claim_id)

    def resolve_claim_without_research(
        self,
        claim_id: str,
        *,
        resolution: str,
        rationale: str,
        resolved_at: object | None = None,
    ) -> dict[str, Any]:
        if resolution not in {"DEFERRED", "NO_ACTION"}:
            raise ValueError("Ohne Hypothese ist nur DEFERRED oder NO_ACTION zulässig.")
        self.get_source_claim(claim_id)
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO source_claim_resolutions (
                    id, claim_id, resolution, hypothesis_id, new_evidence_basis,
                    rationale, resolved_at
                ) VALUES (?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    _id(),
                    claim_id,
                    resolution,
                    _required(rationale, "Abschlussbegründung"),
                    _timestamp(resolved_at),
                ),
            )
        return self.get_source_claim(claim_id)

    def create_hypothesis_from_claim(
        self,
        claim_id: str,
        *,
        title: str,
        area: str,
        category: str,
        mechanism: str,
        external_evidence: str,
        rating: str,
        risks_limitations: str,
        strategy: str | None,
        asset_class: str,
        market_region: str,
        market_universe: str,
        market_timeframe: str,
        material_difference: str | None = None,
        similarity_threshold: float = 0.45,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        claim = self.get_source_claim(claim_id)
        asset_class_value = _required(asset_class, "Assetklasse")
        market_region_value = _required(market_region, "Market-Scope-Region")
        market_universe_value = _required(market_universe, "Market-Scope-Universum")
        market_timeframe_value = _required(market_timeframe, "Market-Scope-Zeitrahmen")
        current_matches = self.knowledge.find_similar_hypotheses(
            title=title,
            claim=claim["claim_text"],
            minimum_score=0,
            limit=100,
        )
        exact = next((item for item in current_matches if item["exact_claim_match"]), None)
        difference = _optional(material_difference)
        if exact is not None:
            same_asset_class = (
                str(exact.get("asset_class") or "").casefold()
                == asset_class_value.casefold()
            )
            if difference is None or same_asset_class:
                raise ValueError(
                    "Derselbe Claim existiert bereits. Die neue Quelle muss mit der bestehenden Hypothese verknüpft werden."
                )
            # Identical wording in a genuinely different market is a new,
            # explicitly related hypothesis with an independent scope.
            similar = exact
        else:
            similar = next(
                (
                    item
                    for item in current_matches
                    if float(item["similarity_score"]) >= similarity_threshold
                ),
                None,
            )
        if similar is not None and difference is None:
            raise ValueError(
                "Ein sehr ähnlicher Claim existiert bereits. Eine neue Hypothese benötigt eine materiell andere Definition."
            )
        timestamp = _timestamp(created_at)
        created = self.knowledge.create_hypothesis(
            title=title,
            area=area,
            category=category,
            claim=str(claim["claim_text"]),
            mechanism=mechanism,
            external_evidence=external_evidence,
            rating=rating,
            risks_limitations=risks_limitations,
            strategy=strategy,
            asset_class=asset_class_value,
            creation_reason=f"Aus Source-Claim {claim_id} nach Wissensabgleich angelegt.",
            created_at=timestamp,
        )
        self.knowledge.link_source(
            created["id"],
            claim["source_id"],
            stance="context",
            note="Ursprungsquelle des extrahierten Claims.",
            linked_at=timestamp,
        )
        resolution = "CREATED_HYPOTHESIS"
        if similar is not None:
            resolution = "MATERIAL_VARIANT"
            self.knowledge.link_hypotheses(
                created["id"],
                similar["id"],
                relation_type="extends",
                note=_required(difference, "Materieller Unterschied"),
                created_at=timestamp,
            )
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO source_claim_resolutions (
                    id, claim_id, resolution, hypothesis_id, new_evidence_basis,
                    rationale, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id(),
                    claim_id,
                    resolution,
                    created["id"],
                    "materially_different_hypothesis" if similar is not None else None,
                    difference or "Kein bestehender gleicher oder hinreichend ähnlicher Claim gefunden.",
                    timestamp,
                ),
            )
        self.record_market_scope(
            target_type="hypothesis",
            target_id=created["id"],
            asset_class=asset_class_value,
            region=market_region_value,
            universe=market_universe_value,
            timeframe=market_timeframe_value,
            scope_notes=f"Eigener Hypothesenscope; Quellenscope: {claim['original_market_scope']}",
            assessed_at=timestamp,
        )
        return self.knowledge.get_hypothesis(created["id"])

    def record_evidence_assessment(
        self,
        hypothesis_id: str,
        *,
        strength: str,
        rationale: str,
        confidence: object | None = None,
        source_id: str | None = None,
        assessed_at: object | None = None,
    ) -> dict[str, Any]:
        self.knowledge.get_hypothesis(hypothesis_id, include_details=False)
        timestamp = _timestamp(assessed_at)
        confidence_value = _number(confidence, "Evidenz-Confidence", minimum=0)
        if confidence_value is not None and confidence_value > 100:
            raise ValueError("Evidenz-Confidence darf höchstens 100 betragen.")
        assessment_id = _id()
        strength_value = _choice(strength, ALLOWED_EVIDENCE_STRENGTHS, "Evidenzstärke")
        rationale_value = _required(rationale, "Evidenzbegründung")
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO hypothesis_evidence_assessments (
                    id, hypothesis_id, source_id, strength, confidence, rationale, assessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    hypothesis_id,
                    source_id,
                    strength_value,
                    confidence_value,
                    rationale_value,
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, source_id, metadata_json
                ) VALUES (?, 'evidence_reassessed', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    rationale_value,
                    source_id,
                    _json({"strength": strength_value, "confidence": confidence_value}),
                ),
            )
        return self.knowledge.get_hypothesis(hypothesis_id, include_details=False)

    def record_application_assessment(
        self,
        hypothesis_id: str,
        *,
        outcome: str,
        feature_available: bool,
        required_data_available: bool,
        existing_research_test: bool,
        market_scope_reviewed: bool,
        active_rule_exists: bool,
        infrastructure_needed: str,
        existing_assets: Mapping[str, object],
        rationale: str,
        experiment_id: str | None = None,
        assessed_at: object | None = None,
    ) -> dict[str, Any]:
        self.knowledge.get_hypothesis(hypothesis_id, include_details=False)
        outcome_value = _choice(outcome, ALLOWED_CAPABILITY_OUTCOMES, "Testbarkeits-Ergebnis")
        flags = {
            "feature_available": _flag(feature_available, "Feature vorhanden"),
            "required_data_available": _flag(required_data_available, "Benötigte Daten vorhanden"),
            "existing_research_test": _flag(existing_research_test, "Research-Test vorhanden"),
            "market_scope_reviewed": _flag(market_scope_reviewed, "Market Scope geprüft"),
            "active_rule_exists": _flag(active_rule_exists, "Aktive Regel vorhanden"),
        }
        infrastructure = _required(infrastructure_needed, "Benötigte Infrastruktur")
        if outcome_value == "TESTABLE_NOW" and not flags["required_data_available"]:
            raise ValueError("TESTABLE_NOW benötigt bereits verfügbare Daten.")
        if outcome_value == "NEW_DATA_REQUIRED" and flags["required_data_available"]:
            raise ValueError("NEW_DATA_REQUIRED widerspricht bereits verfügbaren Daten.")
        if outcome_value == "CODE_EXTENSION_REQUIRED" and infrastructure.casefold() in {"keine", "none", "nicht nötig"}:
            raise ValueError("CODE_EXTENSION_REQUIRED benötigt eine konkrete Research-Erweiterung.")
        actionable_outcomes = {
            "ALREADY_AVAILABLE",
            "TESTABLE_NOW",
            "CODE_EXTENSION_REQUIRED",
            "NEW_DATA_REQUIRED",
        }
        if outcome_value in actionable_outcomes and not flags["market_scope_reviewed"]:
            raise ValueError(f"{outcome_value} benötigt einen geprüften Market Scope.")
        if outcome_value == "ALREADY_AVAILABLE" and not any(
            flags[key]
            for key in (
                "feature_available",
                "required_data_available",
                "existing_research_test",
                "active_rule_exists",
            )
        ):
            raise ValueError("ALREADY_AVAILABLE benötigt mindestens ein vorhandenes App-Artefakt.")
        if outcome_value in actionable_outcomes and not existing_assets:
            raise ValueError(f"{outcome_value} benötigt Referenzen auf vorhandene App-Artefakte.")
        timestamp = _timestamp(assessed_at)
        assessment_id = _id()
        rationale_value = _required(rationale, "Testbarkeitsbegründung")
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO application_capability_assessments (
                    id, hypothesis_id, experiment_id, outcome, feature_available,
                    required_data_available, existing_research_test, market_scope_reviewed,
                    active_rule_exists, infrastructure_needed, existing_assets_json,
                    rationale, assessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    hypothesis_id,
                    experiment_id,
                    outcome_value,
                    *flags.values(),
                    infrastructure,
                    _json(dict(existing_assets)),
                    rationale_value,
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, experiment_id, metadata_json
                ) VALUES (?, 'application_capability_assessed', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    f"App-Abgleich {outcome_value}: {rationale_value}",
                    experiment_id,
                    _json({"assessment_id": assessment_id, "outcome": outcome_value, **flags}),
                ),
            )
        return self.workflow_for_hypothesis(hypothesis_id)["application_assessments"][-1]

    def record_market_scope(
        self,
        *,
        target_type: str,
        target_id: str,
        asset_class: str,
        region: str,
        universe: str,
        timeframe: str,
        scope_notes: str,
        assessed_at: object | None = None,
    ) -> dict[str, Any]:
        target_value = _choice(target_type, ALLOWED_MARKET_SCOPE_TARGETS, "Scope-Zieltyp")
        timestamp = _timestamp(assessed_at)
        scope_id = _id()
        values = (
            scope_id,
            target_value,
            target_id,
            _required(asset_class, "Scope-Assetklasse"),
            _required(region, "Scope-Region"),
            _required(universe, "Scope-Universum"),
            _required(timeframe, "Scope-Zeitrahmen"),
            _required(scope_notes, "Scope-Erläuterung"),
            timestamp,
        )
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO market_scope_assessments (
                    id, target_type, target_id, asset_class, region, universe,
                    timeframe, scope_notes, assessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            hypothesis_id = self._hypothesis_for_workflow_target(connection, target_value, target_id)
            if hypothesis_id:
                connection.execute(
                    """
                    INSERT INTO evidence_ledger (
                        hypothesis_id, event_type, event_at, summary, metadata_json
                    ) VALUES (?, 'market_scope_recorded', ?, ?, ?)
                    """,
                    (
                        hypothesis_id,
                        timestamp,
                        f"Market Scope für {target_value} dokumentiert: {values[3]}, {values[4]}, {values[5]}, {values[6]}.",
                        _json({"scope_id": scope_id, "target_type": target_value, "target_id": target_id}),
                    ),
                )
        return {
            "id": scope_id,
            "target_type": target_value,
            "target_id": target_id,
            "asset_class": values[3],
            "region": values[4],
            "universe": values[5],
            "timeframe": values[6],
            "scope_notes": values[7],
            "assessed_at": timestamp,
        }

    @staticmethod
    def _hypothesis_for_workflow_target(
        connection: sqlite3.Connection,
        target_type: str,
        target_id: str,
    ) -> str | None:
        if target_type == "hypothesis":
            return target_id
        if target_type == "source_claim":
            row = connection.execute(
                """
                SELECT hypothesis_id FROM source_claim_resolutions
                WHERE claim_id = ? AND hypothesis_id IS NOT NULL
                ORDER BY resolved_at DESC, rowid DESC LIMIT 1
                """,
                (target_id,),
            ).fetchone()
        elif target_type == "experiment":
            row = connection.execute(
                "SELECT hypothesis_id FROM experiments WHERE id = ?", (target_id,)
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT hypothesis_id FROM integration_candidates WHERE id = ?", (target_id,)
            ).fetchone()
        return None if row is None else str(row["hypothesis_id"])

    def create_cross_market_hypothesis(
        self,
        parent_hypothesis_id: str,
        *,
        title: str,
        claim: str,
        target_asset_class: str,
        target_region: str,
        target_universe: str,
        target_timeframe: str,
        mechanism: str,
        category: str,
        area: str,
        external_evidence: str,
        rating: str,
        risks_limitations: str,
        strategy: str | None = None,
        material_difference: str,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        parent = self.knowledge.get_hypothesis(parent_hypothesis_id, include_details=False)
        target_asset = _required(target_asset_class, "Ziel-Assetklasse")
        if str(parent.get("asset_class") or "").casefold() == target_asset.casefold():
            raise ValueError("Cross-Market-Übertragung benötigt eine andere Assetklasse.")
        timestamp = _timestamp(created_at)
        created = self.knowledge.create_hypothesis(
            title=title,
            area=area,
            category=category,
            claim=claim,
            mechanism=mechanism,
            external_evidence=external_evidence,
            rating=rating,
            risks_limitations=risks_limitations,
            strategy=strategy,
            asset_class=target_asset,
            creation_reason="Eigenständige Cross-Market-Hypothese; keine Übertragung einer bestehenden Validierung.",
            created_at=timestamp,
        )
        self.knowledge.link_hypotheses(
            created["id"],
            parent_hypothesis_id,
            relation_type="extends",
            note=_required(material_difference, "Materieller Cross-Market-Unterschied"),
            created_at=timestamp,
        )
        self.record_market_scope(
            target_type="hypothesis",
            target_id=created["id"],
            asset_class=target_asset,
            region=target_region,
            universe=target_universe,
            timeframe=target_timeframe,
            scope_notes="Eigenständige Validierung für Cross-Market-Übertragung erforderlich.",
            assessed_at=timestamp,
        )
        return self.knowledge.get_hypothesis(created["id"])

    def create_integration_candidate(
        self,
        hypothesis_id: str,
        result_id: str,
        *,
        feature_combination: Iterable[str],
        incremental_value_assessment: str,
        oos_walk_forward_assessment: str,
        forward_paper_assessment: str,
        sample_size_assessment: str,
        costs_slippage_assessment: str,
        feature_redundancy_assessment: str,
        complexity_assessment: str,
        overfiltering_assessment: str,
        market_scope_assessment: str,
        simpler_variant_assessment: str,
        baseline_trade_count: object,
        candidate_trade_count: object,
        incremental_value_confirmed: bool,
        oos_walk_forward_confirmed: bool,
        forward_paper_confirmed: bool,
        sample_size_sufficient: bool,
        costs_included: bool,
        redundancy_acceptable: bool,
        complexity_justified: bool,
        overfiltering_acceptable: bool,
        trade_count_acceptable: bool,
        market_scope_validated: bool,
        simpler_solution_preferred: bool,
        limitations: str,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        features = sorted({_required(item, "Integrationsfeature") for item in feature_combination}, key=str.casefold)
        if not features:
            raise ValueError("Ein Integration Candidate benötigt mindestens ein fachlich begründetes Feature.")
        if len(features) > MAX_INTEGRATION_FEATURES:
            raise ValueError(
                f"Zum Overfiltering-Schutz sind höchstens {MAX_INTEGRATION_FEATURES} Features pro Candidate zulässig."
            )
        baseline_count = _count(baseline_trade_count, "Baseline-Tradezahl", positive=True)
        candidate_count = _count(candidate_trade_count, "Candidate-Tradezahl", positive=True)
        checks = {
            "incremental_value_confirmed": _flag(incremental_value_confirmed, "Inkrementeller Mehrwert bestätigt"),
            "oos_walk_forward_confirmed": _flag(oos_walk_forward_confirmed, "OOS/Walk-Forward bestätigt"),
            "forward_paper_confirmed": _flag(forward_paper_confirmed, "Forward/Paper bestätigt"),
            "sample_size_sufficient": _flag(sample_size_sufficient, "Sample Size ausreichend"),
            "costs_included": _flag(costs_included, "Kosten berücksichtigt"),
            "redundancy_acceptable": _flag(redundancy_acceptable, "Redundanz akzeptabel"),
            "complexity_justified": _flag(complexity_justified, "Komplexität gerechtfertigt"),
            "overfiltering_acceptable": _flag(overfiltering_acceptable, "Overfiltering akzeptabel"),
            "trade_count_acceptable": _flag(trade_count_acceptable, "Tradezahl akzeptabel"),
            "market_scope_validated": _flag(market_scope_validated, "Market Scope validiert"),
            "simpler_solution_preferred": _flag(
                simpler_solution_preferred,
                "Einfachste ähnlich wirksame Lösung bevorzugt",
            ),
        }
        assessments = (
            _required(incremental_value_assessment, "Inkrementeller Mehrwert"),
            _required(oos_walk_forward_assessment, "OOS-/Walk-Forward-Stabilität"),
            _required(forward_paper_assessment, "Forward-/Papertrade-Bestätigung"),
            _required(sample_size_assessment, "Sample-Size-Einordnung"),
            _required(costs_slippage_assessment, "Kosten-/Slippage-Einordnung"),
            _required(feature_redundancy_assessment, "Feature-Redundanz"),
            _required(complexity_assessment, "Komplexität"),
            _required(overfiltering_assessment, "Overfiltering"),
            _required(market_scope_assessment, "Market-Scope-Gültigkeit"),
            _required(simpler_variant_assessment, "Einfachere Variante"),
        )
        timestamp = _timestamp(created_at)
        candidate_id = _id()
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO integration_candidates (
                    id, hypothesis_id, result_id, feature_combination_json,
                    incremental_value_assessment, oos_walk_forward_assessment,
                    forward_paper_assessment, sample_size_assessment,
                    costs_slippage_assessment, feature_redundancy_assessment,
                    complexity_assessment, overfiltering_assessment,
                    market_scope_assessment, simpler_variant_assessment,
                    baseline_trade_count, candidate_trade_count,
                    incremental_value_confirmed, oos_walk_forward_confirmed,
                    forward_paper_confirmed, sample_size_sufficient, costs_included,
                    redundancy_acceptable, complexity_justified,
                    overfiltering_acceptable, trade_count_acceptable,
                    market_scope_validated, simpler_solution_preferred,
                    limitations, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    hypothesis_id,
                    result_id,
                    _json(features),
                    *assessments,
                    baseline_count,
                    candidate_count,
                    *checks.values(),
                    _required(limitations, "Aktuelle Einschränkungen"),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, result_id, metadata_json
                ) VALUES (?, 'integration_candidate_created', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    "Positives Research-Ergebnis als INTEGRATION_CANDIDATE dokumentiert; keine Strategieänderung ausgeführt.",
                    result_id,
                    _json(
                        {
                            "candidate_id": candidate_id,
                            "features": features,
                            "baseline_trade_count": baseline_count,
                            "candidate_trade_count": candidate_count,
                            "checks": checks,
                            "automatic_integration": False,
                        }
                    ),
                ),
            )
        return self._integration_candidate(candidate_id)

    def record_integration_decision(
        self,
        candidate_id: str,
        *,
        decision: str,
        rationale: str,
        decided_by: str,
        decided_at: object | None = None,
    ) -> dict[str, Any]:
        candidate = self._integration_candidate(candidate_id)
        decision_value = _choice(decision, ALLOWED_INTEGRATION_DECISIONS, "Integrationsentscheidung")
        timestamp = _timestamp(decided_at)
        decision_id = _id()
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO integration_decisions (
                    id, candidate_id, decision, rationale, decided_by, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    candidate_id,
                    decision_value,
                    _required(rationale, "Integrationsbegründung"),
                    _required(decided_by, "Bewusster Entscheider/Review"),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, metadata_json
                ) VALUES (?, 'integration_decision_recorded', ?, ?, ?)
                """,
                (
                    candidate["hypothesis_id"],
                    timestamp,
                    f"Separate Integrationsentscheidung {decision_value}: {_required(rationale, 'Integrationsbegründung')}",
                    _json({"candidate_id": candidate_id, "decision_id": decision_id, "decision": decision_value}),
                ),
            )
        return self._integration_decision(decision_id)

    def record_integration_event(
        self,
        candidate_id: str,
        decision_id: str,
        *,
        event_type: str,
        implementation_reference: str,
        summary: str,
        occurred_at: object | None = None,
    ) -> dict[str, Any]:
        candidate = self._integration_candidate(candidate_id)
        decision = self._integration_decision(decision_id)
        if decision["candidate_id"] != candidate_id:
            raise ValueError("Integrationsentscheidung gehört nicht zu diesem Candidate.")
        event_value = _choice(event_type, ALLOWED_INTEGRATION_EVENTS, "Integrationsereignis")
        if event_value == "ROLLED_BACK" and not any(
            item["event_type"] == "INTEGRATED" for item in candidate["events"]
        ):
            raise ValueError("Ein Rollback setzt ein zuvor dokumentiertes INTEGRATED-Ereignis voraus.")
        timestamp = _timestamp(occurred_at)
        event_id = _id()
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO integration_events (
                    id, candidate_id, decision_id, event_type,
                    implementation_reference, summary, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    candidate_id,
                    decision_id,
                    event_value,
                    _required(implementation_reference, "Implementierungsreferenz"),
                    _required(summary, "Integrationszusammenfassung"),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, metadata_json
                ) VALUES (?, 'integration_event_recorded', ?, ?, ?)
                """,
                (
                    candidate["hypothesis_id"],
                    timestamp,
                    f"Externe Implementierungshistorie {event_value}: {_required(summary, 'Integrationszusammenfassung')}",
                    _json(
                        {
                            "candidate_id": candidate_id,
                            "decision_id": decision_id,
                            "integration_event_id": event_id,
                            "event_type": event_value,
                            "knowledge_base_changed_trading_logic": False,
                        }
                    ),
                ),
            )
        return {
            "id": event_id,
            "candidate_id": candidate_id,
            "decision_id": decision_id,
            "event_type": event_value,
            "implementation_reference": implementation_reference,
            "summary": summary,
            "occurred_at": timestamp,
        }

    def _integration_candidate(self, candidate_id: str) -> dict[str, Any]:
        with database(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM integration_candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unbekannter Integration Candidate: {candidate_id}")
            result = dict(row)
            result["feature_combination"] = _json_value(result.pop("feature_combination_json"))
            result["decisions"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM integration_decisions WHERE candidate_id = ? ORDER BY decided_at, id",
                    (candidate_id,),
                )
            ]
            result["events"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM integration_events WHERE candidate_id = ? ORDER BY occurred_at, id",
                    (candidate_id,),
                )
            ]
        return result

    def _integration_decision(self, decision_id: str) -> dict[str, Any]:
        with database(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM integration_decisions WHERE id = ?", (decision_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unbekannte Integrationsentscheidung: {decision_id}")
        return dict(row)

    def workflow_for_hypothesis(self, hypothesis_id: str) -> dict[str, Any]:
        hypothesis = self.knowledge.get_hypothesis(hypothesis_id, include_details=False)
        with database(self.path) as connection:
            evidence = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM hypothesis_evidence_assessments WHERE hypothesis_id = ? ORDER BY assessed_at, rowid",
                    (hypothesis_id,),
                )
            ]
            claims = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT sc.*, scr.resolution, scr.new_evidence_basis,
                           scr.rationale AS resolution_rationale, scr.resolved_at,
                           s.title AS source_title
                    FROM source_claim_resolutions scr
                    JOIN source_claims sc ON sc.id = scr.claim_id
                    JOIN research_sources s ON s.id = sc.source_id
                    WHERE scr.hypothesis_id = ?
                    ORDER BY scr.resolved_at, scr.id
                    """,
                    (hypothesis_id,),
                )
            ]
            capability = []
            for item in connection.execute(
                "SELECT * FROM application_capability_assessments WHERE hypothesis_id = ? ORDER BY assessed_at, id",
                (hypothesis_id,),
            ):
                assessment = dict(item)
                assessment["existing_assets"] = _json_value(assessment.pop("existing_assets_json"))
                capability.append(assessment)
            experiment_ids = [
                str(item[0])
                for item in connection.execute(
                    "SELECT id FROM experiments WHERE hypothesis_id = ?", (hypothesis_id,)
                )
            ]
            candidate_ids = [
                str(item[0])
                for item in connection.execute(
                    "SELECT id FROM integration_candidates WHERE hypothesis_id = ? ORDER BY created_at, id",
                    (hypothesis_id,),
                )
            ]
            scope_conditions = ["(target_type = 'hypothesis' AND target_id = ?)"]
            scope_parameters: list[object] = [hypothesis_id]
            if experiment_ids:
                scope_conditions.append(
                    f"(target_type = 'experiment' AND target_id IN ({','.join('?' for _ in experiment_ids)}))"
                )
                scope_parameters.extend(experiment_ids)
            if candidate_ids:
                scope_conditions.append(
                    f"(target_type = 'integration_candidate' AND target_id IN ({','.join('?' for _ in candidate_ids)}))"
                )
                scope_parameters.extend(candidate_ids)
            scopes = [
                dict(item)
                for item in connection.execute(
                    f"SELECT * FROM market_scope_assessments WHERE {' OR '.join(scope_conditions)} ORDER BY assessed_at, id",
                    scope_parameters,
                )
            ]
        return {
            "hypothesis_id": hypothesis_id,
            "current_status": hypothesis["current_status"],
            "current_evidence_strength": evidence[-1]["strength"],
            "current_evidence_confidence": evidence[-1]["confidence"],
            "evidence_assessments": evidence,
            "source_claims": claims,
            "application_assessments": capability,
            "market_scopes": scopes,
            "integration_candidates": [self._integration_candidate(item) for item in candidate_ids],
            "automatic_strategy_integration": False,
        }

    def summary(self) -> dict[str, int]:
        with database(self.path) as connection:
            return {
                "source_claims": int(connection.execute("SELECT COUNT(*) FROM source_claims").fetchone()[0]),
                "claim_resolutions": int(connection.execute("SELECT COUNT(*) FROM source_claim_resolutions").fetchone()[0]),
                "capability_assessments": int(connection.execute("SELECT COUNT(*) FROM application_capability_assessments").fetchone()[0]),
                "integration_candidates": int(connection.execute("SELECT COUNT(*) FROM integration_candidates").fetchone()[0]),
                "integration_decisions": int(connection.execute("SELECT COUNT(*) FROM integration_decisions").fetchone()[0]),
                "integration_events": int(connection.execute("SELECT COUNT(*) FROM integration_events").fetchone()[0]),
            }
