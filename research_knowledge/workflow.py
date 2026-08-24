from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import (
    ALLOWED_CAPABILITY_OUTCOMES,
    ALLOWED_CLAIM_VERIFICATION_STATES,
    ALLOWED_CLAIM_RESOLUTIONS,
    ALLOWED_EVIDENCE_STRENGTHS,
    ALLOWED_INTEGRATION_DECISIONS,
    ALLOWED_INTEGRATION_EVENTS,
    ALLOWED_KNOWLEDGE_CLAIM_RELATIONS,
    ALLOWED_KNOWLEDGE_DOMAINS,
    ALLOWED_MARKET_SCOPE_TARGETS,
    ALLOWED_RESULT_DIRECTIONS,
    ALLOWED_RETEST_BASES,
    ALLOWED_TRADING_RELEVANCES,
    ALLOWED_VALIDATION_GATE_STATUSES,
    ALLOWED_WORK_REQUEST_STATUSES,
    ALLOWED_WORK_REQUEST_TYPES,
    DEFAULT_DATABASE_PATH,
    database,
)
from .store import (
    ResearchKnowledgeBase,
    _choice,
    _claim_fingerprint,
    _date_text,
    _id,
    _json,
    _json_value,
    _number,
    _optional,
    _required,
    _timestamp,
    normalize_claim,
)
from swing_research_market_scope import (
    MARKET_SCOPE_CONTRACT_VERSION,
    build_scoped_research_experiment,
    build_scoped_research_hypothesis,
    build_scoped_research_result,
)


MAX_INTEGRATION_FEATURES = 5


class WorkRequestConflict(RuntimeError):
    """Raised when another worker owns a request or its state changed."""


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


def _gate_status(value: object, label: str) -> str:
    return _choice(
        str(value or "").strip().upper(),
        ALLOWED_VALIDATION_GATE_STATUSES,
        label,
    )


def _stable_key(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _claim_is_trading_eligible(classification: Mapping[str, object] | None) -> bool:
    if classification is None:
        return False
    relevance = str(classification.get("trading_relevance") or "")
    return relevance == "TRADING_RELEVANT" or (
        relevance == "POTENTIALLY_TRADING_RELEVANT"
        and bool(classification.get("trading_path_approved"))
    )


def _domain_classification_values(
    *,
    primary_domain: str,
    secondary_domains: Iterable[str],
    subcategory: str | None,
    trading_relevance: str,
    trading_path_approved: bool,
    rationale: str,
) -> dict[str, object]:
    primary = _choice(primary_domain, ALLOWED_KNOWLEDGE_DOMAINS, "Primäre Wissensdomäne")
    secondary = sorted(
        {
            _choice(item, ALLOWED_KNOWLEDGE_DOMAINS, "Sekundäre Wissensdomäne")
            for item in secondary_domains
            if str(item).strip()
        }
    )
    if primary in secondary:
        secondary.remove(primary)
    relevance = _choice(
        trading_relevance,
        ALLOWED_TRADING_RELEVANCES,
        "Trading-Relevanz",
    )
    if not isinstance(trading_path_approved, bool):
        raise ValueError("Trading-Pfad-Freigabe muss ausdrücklich wahr oder falsch sein.")
    if relevance == "TRADING_RELEVANT":
        approved = True
    elif relevance == "NOT_TRADING_RELEVANT":
        approved = False
    else:
        approved = trading_path_approved
    values: dict[str, object] = {
        "primary_domain": primary,
        "secondary_domains": secondary,
        "subcategory": _optional(subcategory),
        "trading_relevance": relevance,
        "trading_path_approved": approved,
        "rationale": _required(rationale, "Begründung der Domain-Einordnung"),
    }
    values["classification_fingerprint"] = _stable_key(values)
    return values


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
        return self.capture_knowledge_claim(
            source_id,
            claim=claim,
            primary_domain="TRADING_INVESTMENT",
            secondary_domains=(),
            subcategory=None,
            trading_relevance="TRADING_RELEVANT",
            trading_path_approved=True,
            classification_rationale="Trading-/Investment-Claim aus dem bestehenden Research-Intake.",
            original_market_scope=original_market_scope,
            extraction_notes=extraction_notes,
            similarity_threshold=similarity_threshold,
            created_at=created_at,
        )

    def capture_knowledge_claim(
        self,
        source_id: str,
        *,
        claim: str,
        primary_domain: str,
        secondary_domains: Iterable[str] = (),
        subcategory: str | None = None,
        trading_relevance: str,
        trading_path_approved: bool = False,
        classification_rationale: str,
        original_market_scope: str | None = None,
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
        classification = _domain_classification_values(
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            subcategory=subcategory,
            trading_relevance=trading_relevance,
            trading_path_approved=trading_path_approved,
            rationale=classification_rationale,
        )
        eligible = _claim_is_trading_eligible(classification)
        market_scope = (
            _required(original_market_scope, "Ursprünglicher Market Scope")
            if eligible
            else (_optional(original_market_scope) or "NOT_APPLICABLE")
        )
        matches = (
            self.knowledge.find_similar_hypotheses(
                title=str(source["title"]),
                claim=claim_text,
                minimum_score=similarity_threshold,
                limit=25,
            )
            if eligible
            else []
        )
        with database(self.path) as connection:
            existing = connection.execute(
                "SELECT id FROM source_claims WHERE source_id = ? AND claim_fingerprint = ?",
                (source_id, fingerprint),
            ).fetchone()
            duplicate_claim = existing is not None
            if existing is None:
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
                        market_scope,
                        str(extraction_notes or "").strip(),
                        timestamp,
                    ),
                )
            else:
                claim_id = str(existing["id"])
            connection.executemany(
                """
                INSERT OR IGNORE INTO source_claim_matches (
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
            classification_id = _id()
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO claim_domain_assessments (
                    id, claim_id, primary_domain, secondary_domains_json, subcategory,
                    trading_relevance, trading_path_approved, rationale,
                    classification_fingerprint, classified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    classification_id,
                    claim_id,
                    classification["primary_domain"],
                    _json(classification["secondary_domains"]),
                    classification["subcategory"],
                    classification["trading_relevance"],
                    int(bool(classification["trading_path_approved"])),
                    classification["rationale"],
                    classification["classification_fingerprint"],
                    timestamp,
                ),
            )
            classification_added = cursor.rowcount == 1
            connection.execute(
                """
                INSERT INTO claim_verification_assessments (
                    id, claim_id, verification_state, evidence_strength, confidence,
                    limitations, jurisdiction, valid_from, valid_until, valid_as_of,
                    update_required, rationale, assessment_fingerprint, assessed_at
                )
                SELECT ?, ?, 'UNVERIFIED', 'weak', NULL, ?, NULL, NULL, NULL, NULL,
                       0, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM claim_verification_assessments WHERE claim_id = ?
                )
                """,
                (
                    _id(),
                    claim_id,
                    "Noch nicht fachlich verifiziert.",
                    "Initialer Verifikationsstatus beim Claim-Intake.",
                    f"initial-unverified:{claim_id}",
                    timestamp,
                    claim_id,
                ),
            )
        result = self.get_source_claim(claim_id)
        result["duplicate_claim"] = duplicate_claim
        result["classification_added"] = classification_added
        return result

    def classify_claim(
        self,
        claim_id: str,
        *,
        primary_domain: str,
        secondary_domains: Iterable[str] = (),
        subcategory: str | None = None,
        trading_relevance: str,
        trading_path_approved: bool = False,
        rationale: str,
        similarity_threshold: float = 0.2,
        classified_at: object | None = None,
    ) -> dict[str, Any]:
        if similarity_threshold < 0 or similarity_threshold > 1:
            raise ValueError("Ähnlichkeitsschwelle muss zwischen 0 und 1 liegen.")
        claim = self.get_source_claim(claim_id)
        values = _domain_classification_values(
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            subcategory=subcategory,
            trading_relevance=trading_relevance,
            trading_path_approved=trading_path_approved,
            rationale=rationale,
        )
        timestamp = _timestamp(classified_at)
        matches = (
            self.knowledge.find_similar_hypotheses(
                title=str(claim["source_title"]),
                claim=str(claim["claim_text"]),
                minimum_score=similarity_threshold,
                limit=25,
            )
            if _claim_is_trading_eligible(values)
            else []
        )
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO claim_domain_assessments (
                    id, claim_id, primary_domain, secondary_domains_json, subcategory,
                    trading_relevance, trading_path_approved, rationale,
                    classification_fingerprint, classified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id(),
                    claim_id,
                    values["primary_domain"],
                    _json(values["secondary_domains"]),
                    values["subcategory"],
                    values["trading_relevance"],
                    int(bool(values["trading_path_approved"])),
                    values["rationale"],
                    values["classification_fingerprint"],
                    timestamp,
                ),
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO source_claim_matches (
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

    def record_claim_verification(
        self,
        claim_id: str,
        *,
        verification_state: str,
        evidence_strength: str,
        confidence: object | None,
        rationale: str,
        limitations: str,
        verifying_sources: Iterable[Mapping[str, object]] = (),
        counter_evidence: Iterable[Mapping[str, object]] = (),
        jurisdiction: str | None = None,
        valid_from: object | None = None,
        valid_until: object | None = None,
        valid_as_of: object | None = None,
        update_required: bool = False,
        assessed_at: object | None = None,
    ) -> dict[str, Any]:
        self.get_source_claim(claim_id)
        state = _choice(
            verification_state,
            ALLOWED_CLAIM_VERIFICATION_STATES,
            "Verifikationsstatus",
        )
        strength = _choice(evidence_strength, ALLOWED_EVIDENCE_STRENGTHS, "Evidenzstärke")
        confidence_value = _number(confidence, "Verification-Confidence", minimum=0)
        if confidence_value is not None and confidence_value > 100:
            raise ValueError("Verification-Confidence darf höchstens 100 betragen.")
        if not isinstance(update_required, bool):
            raise ValueError("Aktualisierungspflicht muss ausdrücklich wahr oder falsch sein.")
        from_date = _date_text(valid_from, "Gültig ab")
        until_date = _date_text(valid_until, "Gültig bis")
        as_of_date = _date_text(valid_as_of, "Datenstand")
        if from_date and until_date and from_date > until_date:
            raise ValueError("Gültig-bis darf nicht vor Gültig-ab liegen.")

        references: list[dict[str, object]] = []
        for reference_type, items in (
            ("VERIFYING", verifying_sources),
            ("COUNTER_EVIDENCE", counter_evidence),
        ):
            for raw in items:
                item = {
                    "reference_type": reference_type,
                    "title": _required(raw.get("title"), "Titel der Verifikationsquelle"),
                    "url": _optional(raw.get("url")),
                    "publisher": _optional(raw.get("publisher")),
                    "published_date": _date_text(
                        raw.get("published_date"),
                        "Veröffentlichungsdatum der Verifikationsquelle",
                    ),
                    "notes": str(raw.get("notes") or "").strip(),
                }
                item["reference_fingerprint"] = _stable_key(item)
                references.append(item)
        references.sort(key=lambda item: str(item["reference_fingerprint"]))
        payload: dict[str, object] = {
            "verification_state": state,
            "evidence_strength": strength,
            "confidence": confidence_value,
            "limitations": str(limitations or "").strip(),
            "jurisdiction": _optional(jurisdiction),
            "valid_from": from_date,
            "valid_until": until_date,
            "valid_as_of": as_of_date,
            "update_required": update_required,
            "rationale": _required(rationale, "Verifikationsbegründung"),
            "references": references,
        }
        assessment_fingerprint = _stable_key(payload)
        timestamp = _timestamp(assessed_at)
        assessment_id = _id()
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO claim_verification_assessments (
                    id, claim_id, verification_state, evidence_strength, confidence,
                    limitations, jurisdiction, valid_from, valid_until, valid_as_of,
                    update_required, rationale, assessment_fingerprint, assessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    claim_id,
                    state,
                    strength,
                    confidence_value,
                    payload["limitations"],
                    payload["jurisdiction"],
                    from_date,
                    until_date,
                    as_of_date,
                    int(update_required),
                    payload["rationale"],
                    assessment_fingerprint,
                    timestamp,
                ),
            )
            row = connection.execute(
                """
                SELECT id FROM claim_verification_assessments
                WHERE claim_id = ? AND assessment_fingerprint = ?
                """,
                (claim_id, assessment_fingerprint),
            ).fetchone()
            if row is None:  # pragma: no cover - protected by transaction
                raise RuntimeError("Claim-Verifikation konnte nicht gespeichert werden.")
            stored_assessment_id = str(row["id"])
            connection.executemany(
                """
                INSERT OR IGNORE INTO claim_verification_references (
                    id, assessment_id, reference_type, title, url, publisher,
                    published_date, notes, reference_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        _id(),
                        stored_assessment_id,
                        item["reference_type"],
                        item["title"],
                        item["url"],
                        item["publisher"],
                        item["published_date"],
                        item["notes"],
                        item["reference_fingerprint"],
                    )
                    for item in references
                ],
            )
        detail = self.get_source_claim(claim_id)
        return next(
            item
            for item in detail["verification_assessments"]
            if item["id"] == stored_assessment_id
        )

    def relate_claims(
        self,
        claim_id: str,
        related_claim_id: str,
        *,
        relation_type: str,
        rationale: str,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        self.get_source_claim(claim_id)
        self.get_source_claim(related_claim_id)
        relation = _choice(
            relation_type,
            ALLOWED_KNOWLEDGE_CLAIM_RELATIONS,
            "Claim-Beziehung",
        )
        timestamp = _timestamp(created_at)
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO knowledge_claim_relations (
                    id, claim_id, related_claim_id, relation_type, rationale, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _id(),
                    claim_id,
                    related_claim_id,
                    relation,
                    _required(rationale, "Begründung der Claim-Beziehung"),
                    timestamp,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM knowledge_claim_relations
                WHERE claim_id = ? AND related_claim_id = ? AND relation_type = ?
                """,
                (claim_id, related_claim_id, relation),
            ).fetchone()
        if row is None:  # pragma: no cover - protected by transaction
            raise RuntimeError("Claim-Beziehung konnte nicht gespeichert werden.")
        return dict(row)

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
            result["domain_assessments"] = []
            for raw in connection.execute(
                """
                SELECT * FROM claim_domain_assessments
                WHERE claim_id = ? ORDER BY classified_at, rowid
                """,
                (claim_id,),
            ):
                assessment = dict(raw)
                assessment["secondary_domains"] = _json_value(
                    assessment.pop("secondary_domains_json", None)
                ) or []
                result["domain_assessments"].append(assessment)
            result["latest_classification"] = (
                result["domain_assessments"][-1]
                if result["domain_assessments"]
                else None
            )
            result["verification_assessments"] = []
            for raw in connection.execute(
                """
                SELECT * FROM claim_verification_assessments
                WHERE claim_id = ? ORDER BY assessed_at, rowid
                """,
                (claim_id,),
            ):
                assessment = dict(raw)
                references = [
                    dict(item)
                    for item in connection.execute(
                        """
                        SELECT * FROM claim_verification_references
                        WHERE assessment_id = ? ORDER BY reference_type, id
                        """,
                        (assessment["id"],),
                    )
                ]
                assessment["verifying_sources"] = [
                    item for item in references if item["reference_type"] == "VERIFYING"
                ]
                assessment["counter_evidence"] = [
                    item
                    for item in references
                    if item["reference_type"] == "COUNTER_EVIDENCE"
                ]
                result["verification_assessments"].append(assessment)
            result["latest_verification"] = (
                result["verification_assessments"][-1]
                if result["verification_assessments"]
                else None
            )
            result["knowledge_relations"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT r.*,
                           CASE WHEN r.claim_id = ? THEN 'outgoing' ELSE 'incoming' END AS direction,
                           other.claim_text AS related_claim_text
                    FROM knowledge_claim_relations r
                    JOIN source_claims other
                      ON other.id = CASE
                          WHEN r.claim_id = ? THEN r.related_claim_id
                          ELSE r.claim_id
                      END
                    WHERE r.claim_id = ? OR r.related_claim_id = ?
                    ORDER BY r.created_at, r.id
                    """,
                    (claim_id, claim_id, claim_id, claim_id),
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
                     WHERE scm.claim_id = sc.id) AS matched_rejected_knowledge,
                    (SELECT cda.primary_domain FROM claim_domain_assessments cda
                     WHERE cda.claim_id = sc.id
                     ORDER BY cda.classified_at DESC, cda.rowid DESC LIMIT 1) AS primary_domain,
                    (SELECT cda.secondary_domains_json FROM claim_domain_assessments cda
                     WHERE cda.claim_id = sc.id
                     ORDER BY cda.classified_at DESC, cda.rowid DESC LIMIT 1) AS secondary_domains_json,
                    (SELECT cda.subcategory FROM claim_domain_assessments cda
                     WHERE cda.claim_id = sc.id
                     ORDER BY cda.classified_at DESC, cda.rowid DESC LIMIT 1) AS subcategory,
                    (SELECT cda.trading_relevance FROM claim_domain_assessments cda
                     WHERE cda.claim_id = sc.id
                     ORDER BY cda.classified_at DESC, cda.rowid DESC LIMIT 1) AS trading_relevance,
                    (SELECT cda.trading_path_approved FROM claim_domain_assessments cda
                     WHERE cda.claim_id = sc.id
                     ORDER BY cda.classified_at DESC, cda.rowid DESC LIMIT 1) AS trading_path_approved,
                    (SELECT cva.verification_state FROM claim_verification_assessments cva
                     WHERE cva.claim_id = sc.id
                     ORDER BY cva.assessed_at DESC, cva.rowid DESC LIMIT 1) AS verification_state,
                    (SELECT cva.confidence FROM claim_verification_assessments cva
                     WHERE cva.claim_id = sc.id
                     ORDER BY cva.assessed_at DESC, cva.rowid DESC LIMIT 1) AS verification_confidence
                FROM source_claims sc
                JOIN research_sources s ON s.id = sc.source_id
                ORDER BY sc.created_at DESC, sc.id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = [dict(item) for item in rows]
        for item in result:
            item["secondary_domains"] = _json_value(
                item.pop("secondary_domains_json", None)
            ) or []
        return result

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
        if not _claim_is_trading_eligible(claim.get("latest_classification")):
            raise ValueError(
                "Nicht-Trading-Claim darf keiner Trading-Hypothese zugeordnet werden."
            )
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
        if not _claim_is_trading_eligible(claim.get("latest_classification")):
            raise ValueError(
                "Nicht-Trading-Claim darf keine Trading-Hypothese erzeugen."
            )
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

    def assess_result_for_validation(
        self,
        result_id: str,
        *,
        research_type: str,
        result_direction: str,
        source_scopes: Iterable[str],
        hypothesis_test_scopes: Iterable[str],
        experiment_test_scopes: Iterable[str],
        validated_scopes: Iterable[str] = (),
        rejected_scopes: Iterable[str] = (),
        is_status: str,
        oos_status: str,
        walk_forward_status: str,
        external_unseen_status: str,
        forward_status: str,
        paper_status: str,
        sample_size_status: str,
        uncertainty_status: str,
        costs_slippage_status: str,
        data_quality_status: str,
        leakage_status: str,
        pit_status: str,
        critical_blocker: bool,
        limitations: str,
        artifact_references: Iterable[Mapping[str, object]] = (),
        rationale: str,
        assessed_at: object | None = None,
    ) -> dict[str, Any]:
        """Record a versioned gate assessment without changing hypothesis status."""

        result = self.knowledge.get_result(result_id)
        experiment = self.knowledge.get_experiment(str(result["experiment_id"]))
        hypothesis = self.knowledge.get_hypothesis(
            str(experiment["hypothesis_id"]), include_details=False
        )
        direction = _choice(
            str(result_direction or "").strip().upper(),
            ALLOWED_RESULT_DIRECTIONS,
            "Ergebnisrichtung",
        )
        expected_direction = {
            "supports": "SUPPORTING",
            "contradicts": "NEGATIVE",
            "negative": "NEGATIVE",
            "mixed": "INCONCLUSIVE",
            "inconclusive": "INCONCLUSIVE",
        }[str(result["conclusion"])]
        if direction != expected_direction:
            raise ValueError(
                "Ergebnisrichtung widerspricht der dauerhaft gespeicherten Resultat-Einordnung."
            )
        source_scope_values = tuple(source_scopes)
        hypothesis_scope_values = tuple(hypothesis_test_scopes)
        experiment_scope_values = tuple(experiment_test_scopes)
        validated_scope_values = tuple(validated_scopes)
        rejected_scope_values = tuple(rejected_scopes)
        with database(self.path) as connection:
            hypothesis_scope_row = connection.execute(
                """
                SELECT * FROM market_scope_assessments
                WHERE target_type = 'hypothesis' AND target_id = ?
                ORDER BY assessed_at DESC, rowid DESC LIMIT 1
                """,
                (hypothesis["id"],),
            ).fetchone()
            experiment_scope_row = connection.execute(
                """
                SELECT * FROM market_scope_assessments
                WHERE target_type = 'experiment' AND target_id = ?
                ORDER BY assessed_at DESC, rowid DESC LIMIT 1
                """,
                (experiment["id"],),
            ).fetchone()
        if hypothesis_scope_row is None or experiment_scope_row is None:
            raise ValueError(
                "VALIDATED-Evidenz benötigt getrennt dokumentierten Hypothesen- und Experiment-Scope."
            )
        if str(hypothesis_scope_row["asset_class"]).strip().upper() not in {
            str(item).strip().upper() for item in hypothesis_scope_values
        }:
            raise ValueError("Hypothesen-Scope widerspricht dem gespeicherten KB-Market-Scope.")
        if str(experiment_scope_row["asset_class"]).strip().upper() not in {
            str(item).strip().upper() for item in experiment_scope_values
        }:
            raise ValueError("Experiment-Scope widerspricht dem gespeicherten KB-Market-Scope.")
        hypothesis_scope = build_scoped_research_hypothesis(
            hypothesis_id=str(hypothesis["id"]),
            name=str(hypothesis["title"]),
            origin=f"research_knowledge.market_scope_assessments/{hypothesis_scope_row['id']}",
            source_scopes=source_scope_values,
            test_scopes=hypothesis_scope_values,
        )
        if not experiment.get("period_start") or not experiment.get("period_end"):
            raise ValueError("Validierung benötigt einen expliziten Experiment-Zeitraum.")
        experiment_scope = build_scoped_research_experiment(
            experiment_id=str(experiment["id"]),
            hypothesis=hypothesis_scope,
            test_scopes=experiment_scope_values,
            asset_universe=str(experiment["data_universe"]),
            period_start=str(experiment["period_start"]),
            period_end=str(experiment["period_end"]),
            timeframe=str(experiment_scope_row["timeframe"]),
            baseline=str(experiment["baseline"]),
            split_design=str(experiment["point_in_time_rules"]),
        )
        if result.get("sample_size") is None:
            raise ValueError("Validierungsassessment benötigt eine dokumentierte Sample Size.")
        result_state = {
            "SUPPORTING": "VALIDATED",
            "NEGATIVE": "REJECTED",
            "INCONCLUSIVE": "INCONCLUSIVE",
        }[direction]
        scope_contract = build_scoped_research_result(
            experiment=experiment_scope,
            sample_size=int(result["sample_size"]),
            is_status=str(is_status),
            oos_status=str(oos_status),
            walk_forward_status=str(walk_forward_status),
            result_status=result_state,
            validated_scopes=validated_scope_values,
            rejected_scopes=rejected_scope_values,
        )
        gate_values = {
            "oos_status": _gate_status(oos_status, "OOS-Status"),
            "walk_forward_status": _gate_status(walk_forward_status, "Walk-Forward-Status"),
            "external_unseen_status": _gate_status(external_unseen_status, "External/Unseen-Status"),
            "forward_status": _gate_status(forward_status, "Forward-Status"),
            "paper_status": _gate_status(paper_status, "Paper-Status"),
            "sample_size_status": _gate_status(sample_size_status, "Sample-Size-Status"),
            "uncertainty_status": _gate_status(uncertainty_status, "Unsicherheits-Status"),
            "costs_slippage_status": _gate_status(costs_slippage_status, "Kosten-/Slippage-Status"),
            "data_quality_status": _gate_status(data_quality_status, "Datenqualitäts-Status"),
            "leakage_status": _gate_status(leakage_status, "Leakage-Status"),
            "pit_status": _gate_status(pit_status, "Point-in-Time-Status"),
        }
        blocker_flag = _flag(critical_blocker, "Kritische Datensperre")
        timestamp = _timestamp(assessed_at)
        assessment_id = _id()
        artifact_values = [dict(item) for item in artifact_references]
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO result_validation_assessments (
                    id, result_id, research_type, gate_contract_version,
                    result_direction, scope_contract_json, result_scope_fingerprint,
                    scope_gate_passed, oos_status, walk_forward_status,
                    external_unseen_status, forward_status, paper_status,
                    sample_size_status, uncertainty_status, costs_slippage_status,
                    data_quality_status, leakage_status, pit_status, critical_blocker,
                    limitations, artifact_references_json, rationale, assessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    result_id,
                    _required(research_type, "Research-Typ"),
                    MARKET_SCOPE_CONTRACT_VERSION,
                    direction,
                    _json(scope_contract),
                    scope_contract["result_scope_fingerprint"],
                    *gate_values.values(),
                    blocker_flag,
                    _required(limitations, "Resultat-Limitierungen"),
                    _json(artifact_values),
                    _required(rationale, "Validierungsbegründung"),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary,
                    experiment_id, result_id, metadata_json
                ) VALUES (?, 'result_validation_assessed', ?, ?, ?, ?, ?)
                """,
                (
                    hypothesis["id"],
                    timestamp,
                    f"Resultat-Gates {direction} bewertet; keine automatische Status- oder Strategieänderung.",
                    experiment["id"],
                    result_id,
                    _json(
                        {
                            "assessment_id": assessment_id,
                            "gate_contract_version": MARKET_SCOPE_CONTRACT_VERSION,
                            "gate_statuses": gate_values,
                            "critical_blocker": bool(blocker_flag),
                            "automatic_validation": False,
                            "automatic_integration": False,
                        }
                    ),
                ),
            )
        return self.knowledge.get_result(result_id)["validation_assessments"][-1]

    def select_result_for_validation(
        self,
        hypothesis_id: str,
        result_id: str,
        assessment_id: str,
        *,
        selected_by: str,
        rationale: str,
        selected_at: object | None = None,
    ) -> dict[str, Any]:
        """Explicitly select one already qualified internal result for status review."""

        timestamp = _timestamp(selected_at)
        selection_id = _id()
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO hypothesis_validation_evidence (
                    id, hypothesis_id, result_id, assessment_id,
                    selected_by, rationale, selected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selection_id,
                    hypothesis_id,
                    result_id,
                    assessment_id,
                    _required(selected_by, "Auswählender Kontext"),
                    _required(rationale, "Auswahlbegründung"),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, result_id, metadata_json
                ) VALUES (?, 'validation_result_selected', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    "Qualifiziertes internes Resultat explizit für eine bewusste VALIDATED-Statusentscheidung ausgewählt.",
                    result_id,
                    _json(
                        {
                            "selection_id": selection_id,
                            "assessment_id": assessment_id,
                            "automatic_status_change": False,
                            "automatic_integration": False,
                        }
                    ),
                ),
            )
        return {
            "id": selection_id,
            "hypothesis_id": hypothesis_id,
            "result_id": result_id,
            "assessment_id": assessment_id,
            "selected_by": selected_by,
            "rationale": rationale,
            "selected_at": timestamp,
        }

    def create_work_request(
        self,
        hypothesis_id: str,
        *,
        capability_assessment_id: str,
        request_type: str,
        task: str,
        expected_output: str,
        required_infrastructure: str,
        scope: Mapping[str, object],
        safeguards: Mapping[str, object],
        experiment_id: str | None = None,
        source_id: str | None = None,
        idempotency_key: str | None = None,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        request_type_value = _choice(request_type, ALLOWED_WORK_REQUEST_TYPES, "Work-Request-Typ")
        with database(self.path) as connection:
            assessment = connection.execute(
                """
                SELECT * FROM application_capability_assessments
                WHERE id = ? AND hypothesis_id = ?
                """,
                (capability_assessment_id, hypothesis_id),
            ).fetchone()
            latest = connection.execute(
                """
                SELECT id FROM application_capability_assessments
                WHERE hypothesis_id = ? ORDER BY assessed_at DESC, rowid DESC LIMIT 1
                """,
                (hypothesis_id,),
            ).fetchone()
        if assessment is None:
            raise ValueError("Capability Assessment gehört nicht zu dieser Hypothese.")
        if latest is None or str(latest["id"]) != capability_assessment_id:
            raise ValueError("Work Request benötigt das aktuelle Capability Assessment.")
        outcome = str(assessment["outcome"])
        if outcome in {"NO_ACTION", "DEFERRED", "ALREADY_AVAILABLE"}:
            raise ValueError(f"{outcome} darf keinen Work Request erzeugen.")
        expected_outcome = {
            "RESEARCH_TEST": "TESTABLE_NOW",
            "CODE_EXTENSION": "CODE_EXTENSION_REQUIRED",
            "DATA_PIPELINE": "NEW_DATA_REQUIRED",
            "INTEGRATION_REVIEW": "TESTABLE_NOW",
        }[request_type_value]
        if outcome != expected_outcome:
            raise ValueError(
                f"{request_type_value} passt nicht zum Capability Outcome {outcome}."
            )
        if request_type_value == "RESEARCH_TEST" and experiment_id is None:
            raise ValueError("RESEARCH_TEST benötigt ein eindeutig referenziertes Experiment.")
        scope_value = dict(scope)
        safeguards_value = {
            **dict(safeguards),
            "automatic_strategy_change": False,
            "automatic_integration": False,
            "broker_or_order_execution": False,
        }
        if not scope_value:
            raise ValueError("Work Request benötigt einen expliziten Scope.")
        task_value = _required(task, "Fachliche Aufgabe")
        key = _optional(idempotency_key) or _stable_key(
            {
                "hypothesis_id": hypothesis_id,
                "experiment_id": experiment_id,
                "source_id": source_id,
                "request_type": request_type_value,
                "task": task_value,
            }
        )
        timestamp = _timestamp(created_at)
        request_id = _id()
        with database(self.path) as connection:
            existing = connection.execute(
                "SELECT id FROM research_work_requests WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                replay = self.get_work_request(str(existing["id"]), include_context=False)
                replay["idempotent_replay"] = True
                return replay
            connection.execute(
                """
                INSERT INTO research_work_requests (
                    id, hypothesis_id, experiment_id, source_id,
                    capability_assessment_id, request_type, current_status,
                    task, expected_output, required_infrastructure,
                    scope_json, safeguards_json, idempotency_key,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'READY', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    hypothesis_id,
                    experiment_id,
                    source_id,
                    capability_assessment_id,
                    request_type_value,
                    task_value,
                    _required(expected_output, "Erwarteter Output"),
                    _required(required_infrastructure, "Benötigte Infrastruktur"),
                    _json(scope_value),
                    _json(safeguards_value),
                    key,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO work_request_status_history (
                    work_request_id, from_status, to_status, changed_at, actor, reason
                ) VALUES (?, NULL, 'READY', ?, 'research_workflow', 'Work Request aus aktuellem Capability Assessment erzeugt')
                """,
                (request_id, timestamp),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, source_id,
                    experiment_id, metadata_json
                ) VALUES (?, 'work_request_created', ?, ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    f"READY Work Request {request_type_value} angelegt: {task_value}",
                    source_id,
                    experiment_id,
                    _json(
                        {
                            "work_request_id": request_id,
                            "capability_assessment_id": capability_assessment_id,
                            "automatic_execution": False,
                        }
                    ),
                ),
            )
        return self.get_work_request(request_id, include_context=False)

    def get_work_request(
        self,
        work_request_id: str,
        *,
        include_context: bool = True,
    ) -> dict[str, Any]:
        with database(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM research_work_requests WHERE id = ?", (work_request_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unbekannter Work Request: {work_request_id}")
            result = dict(row)
            result["scope"] = _json_value(result.pop("scope_json", None))
            result["safeguards"] = _json_value(result.pop("safeguards_json", None))
            result["artifact_references"] = _json_value(
                result.pop("artifact_references_json", None)
            )
            result["status_history"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM work_request_status_history WHERE work_request_id = ? ORDER BY changed_at, id",
                    (work_request_id,),
                )
            ]
        if include_context:
            result["hypothesis"] = self.knowledge.get_hypothesis(
                str(result["hypothesis_id"]), include_details=True
            )
            result["experiment"] = (
                None
                if result["experiment_id"] is None
                else self.knowledge.get_experiment(str(result["experiment_id"]))
            )
            result["source"] = (
                None
                if result["source_id"] is None
                else self.knowledge.get_source(str(result["source_id"]))
            )
        return result

    def list_work_requests(
        self,
        *,
        status: str | None = "READY",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1_000:
            raise ValueError("Limit muss zwischen 1 und 1000 liegen.")
        parameters: list[object] = []
        where = ""
        if status and status != "ALL":
            where = "WHERE current_status = ?"
            parameters.append(_choice(status, ALLOWED_WORK_REQUEST_STATUSES, "Work-Status"))
        parameters.append(limit)
        with database(self.path) as connection:
            ids = [
                str(item["id"])
                for item in connection.execute(
                    f"SELECT id FROM research_work_requests {where} ORDER BY created_at, id LIMIT ?",
                    parameters,
                )
            ]
        return [self.get_work_request(item, include_context=False) for item in ids]

    def claim_work_request(
        self,
        work_request_id: str,
        *,
        worker_context: str,
        claim_token: str | None = None,
        claimed_at: object | None = None,
    ) -> dict[str, Any]:
        worker = _required(worker_context, "Ausführender Kontext")
        timestamp = _timestamp(claimed_at)
        token = _optional(claim_token) or _id()
        replay = False
        with database(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM research_work_requests WHERE id = ?", (work_request_id,)
            ).fetchone()
            if current is None:
                raise KeyError(f"Unbekannter Work Request: {work_request_id}")
            if str(current["current_status"]) == "IN_PROGRESS":
                if (
                    claim_token
                    and str(current["claim_token"] or "") == claim_token
                    and str(current["claimed_by"] or "") == worker
                ):
                    replay = True
                else:
                    raise WorkRequestConflict("Work Request wurde bereits von einer anderen Session übernommen.")
            elif str(current["current_status"]) != "READY":
                raise WorkRequestConflict(
                    f"Work Request ist {current['current_status']} und kann nicht übernommen werden."
                )
            else:
                connection.execute(
                    """
                    INSERT INTO work_request_status_change_context (
                        work_request_id, changed_at, actor, reason
                    ) VALUES (?, ?, ?, 'Work Request atomar übernommen')
                    """,
                    (work_request_id, timestamp, worker),
                )
                cursor = connection.execute(
                    """
                    UPDATE research_work_requests
                    SET current_status = 'IN_PROGRESS', claimed_at = ?, claimed_by = ?,
                        claim_token = ?, worker_context = ?, updated_at = ?
                    WHERE id = ? AND current_status = 'READY'
                    """,
                    (timestamp, worker, token, worker, timestamp, work_request_id),
                )
                if cursor.rowcount != 1:
                    raise WorkRequestConflict("Work Request wurde parallel übernommen.")
        result = self.get_work_request(work_request_id)
        result["claim_token"] = token if not replay else claim_token
        result["idempotent_replay"] = replay
        return result

    def block_work_request(
        self,
        work_request_id: str,
        *,
        claim_token: str,
        blocker_reason: str,
        worker_context: str,
        blocked_at: object | None = None,
    ) -> dict[str, Any]:
        return self._transition_claimed_work_request(
            work_request_id,
            claim_token=claim_token,
            new_status="BLOCKED",
            reason=_required(blocker_reason, "Blocker-/Abbruchbegründung"),
            worker_context=worker_context,
            changed_at=blocked_at,
        )

    def retry_blocked_work_request(
        self,
        work_request_id: str,
        *,
        reason: str,
        actor: str,
        retried_at: object | None = None,
    ) -> dict[str, Any]:
        timestamp = _timestamp(retried_at)
        with database(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT current_status FROM research_work_requests WHERE id = ?",
                (work_request_id,),
            ).fetchone()
            if current is None:
                raise KeyError(f"Unbekannter Work Request: {work_request_id}")
            if str(current["current_status"]) != "BLOCKED":
                raise WorkRequestConflict("Nur ein BLOCKED Work Request kann erneut READY gesetzt werden.")
            connection.execute(
                """
                INSERT INTO work_request_status_change_context (
                    work_request_id, changed_at, actor, reason
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    work_request_id,
                    timestamp,
                    _required(actor, "Akteur"),
                    _required(reason, "Retry-Begründung"),
                ),
            )
            connection.execute(
                """
                UPDATE research_work_requests
                SET current_status = 'READY', claimed_at = NULL, claimed_by = NULL,
                    claim_token = NULL, worker_context = NULL, blocker_reason = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, work_request_id),
            )
        return self.get_work_request(work_request_id, include_context=False)

    def _transition_claimed_work_request(
        self,
        work_request_id: str,
        *,
        claim_token: str,
        new_status: str,
        reason: str,
        worker_context: str,
        changed_at: object | None,
    ) -> dict[str, Any]:
        status = _choice(new_status, ("BLOCKED", "CANCELLED"), "Work-Status")
        timestamp = _timestamp(changed_at)
        worker = _required(worker_context, "Ausführender Kontext")
        with database(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT current_status, claim_token FROM research_work_requests WHERE id = ?",
                (work_request_id,),
            ).fetchone()
            if current is None:
                raise KeyError(f"Unbekannter Work Request: {work_request_id}")
            if str(current["current_status"]) != "IN_PROGRESS" or str(current["claim_token"] or "") != claim_token:
                raise WorkRequestConflict("Claim-Token oder Work-Status stimmt nicht.")
            connection.execute(
                """
                INSERT INTO work_request_status_change_context (
                    work_request_id, changed_at, actor, reason
                ) VALUES (?, ?, ?, ?)
                """,
                (work_request_id, timestamp, worker, reason),
            )
            connection.execute(
                """
                UPDATE research_work_requests
                SET current_status = ?, blocker_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, reason if status == "BLOCKED" else None, timestamp, work_request_id),
            )
        return self.get_work_request(work_request_id, include_context=False)

    def complete_work_request(
        self,
        work_request_id: str,
        *,
        claim_token: str,
        worker_context: str,
        result: Mapping[str, object],
        result_reference: str | None = None,
        artifact_references: Iterable[Mapping[str, object]] = (),
        completed_at: object | None = None,
    ) -> dict[str, Any]:
        """Persist the work result idempotently and complete the same KB request."""

        request = self.get_work_request(work_request_id, include_context=False)
        if request["current_status"] == "COMPLETED" and request.get("result_id"):
            request["idempotent_replay"] = True
            return request
        if request["current_status"] != "IN_PROGRESS" or request.get("claim_token") != claim_token:
            raise WorkRequestConflict("Claim-Token oder Work-Status stimmt nicht.")
        experiment_id = request.get("experiment_id")
        if experiment_id is None:
            raise ValueError("Direkter Resultatrückkanal benötigt einen Work Request mit Experiment.")
        experiment = self.knowledge.get_experiment(str(experiment_id))
        if experiment["current_status"] != "COMPLETED":
            self.knowledge.change_experiment_status(
                str(experiment_id),
                "COMPLETED",
                reason=f"Work Request {work_request_id} durch {worker_context} abgeschlossen.",
                changed_at=completed_at,
            )
        allowed_result_fields = {
            "title",
            "conclusion",
            "interpretation",
            "sample_size",
            "hit_rate",
            "expectancy",
            "profit_factor",
            "mfe",
            "mae",
            "drawdown",
            "r_multiples",
            "costs",
            "slippage",
            "in_sample",
            "validation",
            "out_of_sample",
            "walk_forward",
            "forward",
            "papertrade",
        }
        unknown = sorted(set(result) - allowed_result_fields)
        if unknown:
            raise ValueError("Unbekannte Resultatfelder: " + ", ".join(unknown))
        result_values = dict(result)
        stored_result = self.knowledge.record_result(
            str(experiment_id),
            **result_values,
            idempotency_key=f"work_request:{work_request_id}",
            recorded_at=completed_at,
        )
        artifacts = [dict(item) for item in artifact_references]
        for artifact in artifacts:
            required = {"system", "record_type", "record_id"}
            missing = sorted(required - set(artifact))
            if missing:
                raise ValueError("Artefaktreferenz fehlt: " + ", ".join(missing))
            try:
                self.knowledge.add_external_reference(
                    target_type="result",
                    target_id=str(stored_result["id"]),
                    system=str(artifact["system"]),
                    record_type=str(artifact["record_type"]),
                    record_id=str(artifact["record_id"]),
                    uri=_optional(artifact.get("uri")),
                    description=str(artifact.get("description") or ""),
                    created_at=completed_at,
                )
            except sqlite3.IntegrityError:
                pass
        timestamp = _timestamp(completed_at)
        worker = _required(worker_context, "Ausführender Kontext")
        with database(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT current_status, claim_token, result_id FROM research_work_requests WHERE id = ?",
                (work_request_id,),
            ).fetchone()
            if current is None:
                raise KeyError(f"Unbekannter Work Request: {work_request_id}")
            if str(current["current_status"]) == "COMPLETED":
                if str(current["result_id"] or "") != str(stored_result["id"]):
                    raise WorkRequestConflict("Work Request wurde mit einem anderen Resultat abgeschlossen.")
            else:
                if str(current["current_status"]) != "IN_PROGRESS" or str(current["claim_token"] or "") != claim_token:
                    raise WorkRequestConflict("Claim-Token oder Work-Status stimmt nicht.")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO work_request_result_links (
                        id, work_request_id, result_id, linked_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (_id(), work_request_id, stored_result["id"], timestamp),
                )
                connection.execute(
                    """
                    INSERT INTO work_request_status_change_context (
                        work_request_id, changed_at, actor, reason
                    ) VALUES (?, ?, ?, 'Arbeitsergebnis direkt in derselben Knowledge Base gespeichert')
                    """,
                    (work_request_id, timestamp, worker),
                )
                connection.execute(
                    """
                    UPDATE research_work_requests
                    SET current_status = 'COMPLETED', completed_at = ?, worker_context = ?,
                        result_id = ?, result_reference = ?, artifact_references_json = ?,
                        blocker_reason = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        timestamp,
                        worker,
                        stored_result["id"],
                        _optional(result_reference),
                        _json(artifacts),
                        timestamp,
                        work_request_id,
                    ),
                )
        completed = self.get_work_request(work_request_id, include_context=False)
        completed["result"] = self.knowledge.get_result(str(stored_result["id"]))
        return completed

    record_work_result = complete_work_request

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
            validation_evidence = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT v.*, a.gate_contract_version, a.result_direction,
                           a.result_scope_fingerprint
                    FROM hypothesis_validation_evidence v
                    JOIN result_validation_assessments a ON a.id = v.assessment_id
                    WHERE v.hypothesis_id = ?
                    ORDER BY v.selected_at, v.id
                    """,
                    (hypothesis_id,),
                )
            ]
            work_request_ids = [
                str(item[0])
                for item in connection.execute(
                    "SELECT id FROM research_work_requests WHERE hypothesis_id = ? ORDER BY created_at, id",
                    (hypothesis_id,),
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
            "validation_evidence": validation_evidence,
            "work_requests": [
                self.get_work_request(item, include_context=False) for item in work_request_ids
            ],
            "automatic_strategy_integration": False,
        }

    def summary(self) -> dict[str, int]:
        with database(self.path) as connection:
            return {
                "source_claims": int(connection.execute("SELECT COUNT(*) FROM source_claims").fetchone()[0]),
                "domain_assessments": int(connection.execute("SELECT COUNT(*) FROM claim_domain_assessments").fetchone()[0]),
                "claim_verification_assessments": int(connection.execute("SELECT COUNT(*) FROM claim_verification_assessments").fetchone()[0]),
                "claim_resolutions": int(connection.execute("SELECT COUNT(*) FROM source_claim_resolutions").fetchone()[0]),
                "capability_assessments": int(connection.execute("SELECT COUNT(*) FROM application_capability_assessments").fetchone()[0]),
                "integration_candidates": int(connection.execute("SELECT COUNT(*) FROM integration_candidates").fetchone()[0]),
                "integration_decisions": int(connection.execute("SELECT COUNT(*) FROM integration_decisions").fetchone()[0]),
                "integration_events": int(connection.execute("SELECT COUNT(*) FROM integration_events").fetchone()[0]),
                "work_requests": int(connection.execute("SELECT COUNT(*) FROM research_work_requests").fetchone()[0]),
                "work_requests_ready": int(connection.execute("SELECT COUNT(*) FROM research_work_requests WHERE current_status = 'READY'").fetchone()[0]),
                "validation_assessments": int(connection.execute("SELECT COUNT(*) FROM result_validation_assessments").fetchone()[0]),
                "validation_selections": int(connection.execute("SELECT COUNT(*) FROM hypothesis_validation_evidence").fetchone()[0]),
            }
