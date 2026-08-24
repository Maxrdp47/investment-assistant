from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import (
    ALLOWED_AREAS,
    ALLOWED_EVIDENCE_STRENGTHS,
    ALLOWED_EXPERIMENT_STATUSES,
    ALLOWED_HYPOTHESIS_STATUSES,
    ALLOWED_RATINGS,
    ALLOWED_RELATION_TYPES,
    ALLOWED_RETEST_BASES,
    ALLOWED_RESULT_CONCLUSIONS,
    ALLOWED_SOURCE_STANCES,
    ALLOWED_SOURCE_TYPES,
    DEFAULT_DATABASE_PATH,
    CURRENT_SCHEMA_VERSION,
    database,
    initialize_database,
)
from .source_identity import inspect_source_identity, normalize_source_title, normalize_source_url


_TARGET_TABLES = {
    "source": "research_sources",
    "hypothesis": "hypotheses",
    "experiment": "experiments",
    "result": "research_results",
}
_STOP_WORDS = {
    "aber",
    "als",
    "auch",
    "bei",
    "das",
    "dass",
    "dem",
    "den",
    "der",
    "die",
    "ein",
    "eine",
    "einer",
    "fuer",
    "für",
    "ist",
    "mit",
    "nach",
    "oder",
    "sich",
    "the",
    "und",
    "von",
    "wenn",
    "wird",
    "zu",
}


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} darf nicht leer sein.")
    return text


def _optional(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _choice(value: object, allowed: Iterable[str], label: str) -> str:
    text = _required(value, label)
    choices = tuple(allowed)
    if text not in choices:
        raise ValueError(f"{label} muss einer der Werte {', '.join(choices)} sein.")
    return text


def _date_text(value: object, label: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label} muss ein ISO-Datum im Format YYYY-MM-DD sein.") from exc


def _timestamp(value: object | None) -> str:
    if value is None:
        return _now()
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _required(value, "Zeitpunkt")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Zeitpunkt muss ein gültiger ISO-Zeitpunkt sein.") from exc
    if parsed.tzinfo is None:
        raise ValueError("Zeitpunkt benötigt eine Zeitzone.")
    return parsed.isoformat()


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )


def _json_value(value: str | None) -> object | None:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _number(value: object, label: str, *, minimum: float | None = None) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} muss numerisch sein.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} muss endlich sein.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} muss mindestens {minimum:g} sein.")
    return number


def normalize_claim(value: object) -> str:
    text = unicodedata.normalize("NFKC", _required(value, "Behauptung")).casefold()
    return " ".join(re.findall(r"[a-z0-9äöüß]+", text))


def _claim_fingerprint(normalized_claim: str) -> str:
    return hashlib.sha256(normalized_claim.encode("utf-8")).hexdigest()


def _tokens(value: object) -> set[str]:
    normalized = normalize_claim(value)
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in _STOP_WORDS
    }


def _row(row: object) -> dict[str, Any] | None:
    return None if row is None else dict(row)  # type: ignore[arg-type]


class ResearchKnowledgeBase:
    """Repository for durable research memory, isolated from trading decisions."""

    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path)
        initialize_database(self.path)

    def create_source(
        self,
        *,
        title: str,
        source_type: str,
        summary: str,
        reference: str | None = None,
        source_date: object | None = None,
        created_at: object | None = None,
        platform: str | None = None,
        creator: str | None = None,
        profile_url: str | None = None,
        local_file: Path | None = None,
        local_filename: str | None = None,
        file_sha256: str | None = None,
        file_size: int | None = None,
        provenance: str = "Research-Intake",
    ) -> dict[str, Any]:
        source_type_value = _choice(source_type, ALLOWED_SOURCE_TYPES, "Quellentyp")
        direct_url = reference
        inferred_profile = profile_url
        if source_type_value in {"youtube", "tiktok"} and reference:
            normalized = normalize_source_url(reference, platform=platform or source_type_value)
            identity = inspect_source_identity(
                title=title,
                platform=platform or source_type_value,
                direct_url=reference,
            )
            if normalized and identity["content_id"] is None:
                direct_url = None
                inferred_profile = inferred_profile or reference
        intake = self.intake_source(
            title=title,
            source_type=source_type_value,
            summary=summary,
            platform=platform or (source_type_value if source_type_value in {"youtube", "tiktok"} else None),
            creator=creator,
            direct_url=direct_url,
            profile_url=inferred_profile,
            published_date=source_date,
            local_file=local_file,
            local_filename=local_filename,
            file_sha256=file_sha256,
            file_size=file_size,
            provenance=provenance,
            captured_at=created_at,
            confirm_distinct=True,
        )
        source = dict(intake["source"])
        source["intake_status"] = intake["status"]
        source["provenance_added"] = intake["provenance_added"]
        return source

    def intake_source(
        self,
        *,
        title: str,
        source_type: str,
        summary: str,
        platform: str | None = None,
        creator: str | None = None,
        direct_url: str | None = None,
        profile_url: str | None = None,
        published_date: object | None = None,
        local_file: Path | None = None,
        local_filename: str | None = None,
        file_sha256: str | None = None,
        file_size: int | None = None,
        provenance: str,
        captured_at: object | None = None,
        confirm_distinct: bool = False,
        distinct_rationale: str | None = None,
        resolve_to_source_id: str | None = None,
    ) -> dict[str, Any]:
        """Identify a source before insertion and append only genuinely new provenance."""

        title_value = _required(title, "Quellentitel")
        source_type_value = _choice(source_type, ALLOWED_SOURCE_TYPES, "Quellentyp")
        summary_value = _required(summary, "Neutrale Zusammenfassung")
        published = _date_text(published_date, "Veröffentlichungsdatum")
        timestamp = _timestamp(captured_at)
        identity = inspect_source_identity(
            title=title_value,
            platform=platform,
            creator=creator,
            direct_url=direct_url,
            profile_url=profile_url,
            published_date=published,
            local_file=local_file,
            local_filename=local_filename,
            file_sha256=file_sha256,
            file_size=file_size,
        )
        provenance_value = _required(provenance, "Provenienz")
        self._backfill_legacy_source_provenance()
        keys = list(identity["identity_keys"])
        matched_source_id: str | None = None
        matched_status: str | None = None
        matched_provenance_added = False
        with database(self.path) as connection:
            matched_source_ids: set[str] = set()
            for identity_type, identity_value in keys:
                row = connection.execute(
                    """
                    SELECT source_id FROM source_identity_keys
                    WHERE identity_type = ? AND identity_value = ?
                    """,
                    (identity_type, identity_value),
                ).fetchone()
                if row is not None:
                    matched_source_ids.add(str(row["source_id"]))
            if len(matched_source_ids) > 1:
                raise ValueError(
                    "Die gelieferten Identitätsmerkmale gehören zu verschiedenen vorhandenen Sources. "
                    "Der Konflikt muss bewusst geprüft werden."
                )
            if matched_source_ids:
                source_id = next(iter(matched_source_ids))
                provenance_added = self._append_source_provenance(
                    connection,
                    source_id=source_id,
                    identity=identity,
                    provenance=provenance_value,
                    captured_at=timestamp,
                )
                matched_source_id = source_id
                matched_status = "PROVENANCE_ENRICHED" if provenance_added else "DUPLICATE_SOURCE"
                matched_provenance_added = provenance_added
            if matched_source_id is not None:
                pass
            else:
                possible = self._possible_duplicate_source_ids(
                    connection,
                    title=title_value,
                    creator=creator,
                    platform=str(identity.get("platform") or "") or None,
                )
                if keys and possible:
                    possible = [
                        possible_id
                        for possible_id in possible
                        if connection.execute(
                            "SELECT 1 FROM source_identity_keys WHERE source_id = ? LIMIT 1",
                            (possible_id,),
                        ).fetchone()
                        is None
                    ]
                if resolve_to_source_id is not None:
                    resolved_id = _required(resolve_to_source_id, "Bewusst gewählte Source-ID")
                    if resolved_id not in possible:
                        raise ValueError(
                            "Die bewusst gewählte Source-ID gehört nicht zu den konservativ ermittelten Possible Duplicates."
                        )
                    provenance_added = self._append_source_provenance(
                        connection,
                        source_id=resolved_id,
                        identity=identity,
                        provenance=provenance_value,
                        captured_at=timestamp,
                    )
                    matched_source_id = resolved_id
                    matched_status = "PROVENANCE_ENRICHED" if provenance_added else "DUPLICATE_SOURCE"
                    matched_provenance_added = provenance_added
                    possible = []
                if matched_source_id is not None:
                    pass
                elif possible and not confirm_distinct:
                    return {
                        "status": "POSSIBLE_DUPLICATE",
                        "source": None,
                        "source_id": None,
                        "provenance_added": False,
                        "possible_duplicate_source_ids": possible,
                        "message": "Ähnliche Metadaten reichen nicht für einen automatischen Merge.",
                    }
                else:
                    source_id = _id()
                    connection.execute(
                    """
                    INSERT INTO research_sources (
                        id, title, source_type, reference, source_date, neutral_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        title_value,
                        source_type_value,
                        _optional(direct_url) or _optional(profile_url),
                        published,
                        summary_value,
                        timestamp,
                    ),
                )
                    self._append_source_provenance(
                        connection,
                        source_id=source_id,
                        identity=identity,
                        provenance=provenance_value,
                        captured_at=timestamp,
                    )
                    for possible_id in possible:
                        connection.execute(
                        """
                        INSERT OR IGNORE INTO source_duplicate_assessments (
                            id, source_id, possible_duplicate_source_id, decision, rationale, assessed_at
                        ) VALUES (?, ?, ?, 'CONFIRMED_DISTINCT', ?, ?)
                        """,
                            (
                                _id(),
                                source_id,
                                possible_id,
                                _required(distinct_rationale, "Begründung für eigenständige Source"),
                                timestamp,
                            ),
                        )
        if matched_source_id is not None:
            return {
                "status": matched_status,
                "source": self.get_source(matched_source_id),
                "source_id": matched_source_id,
                "provenance_added": matched_provenance_added,
                "possible_duplicate_source_ids": [],
                "message": "Source bereits vorhanden; kein neues Workflowobjekt erzeugt.",
            }
        return {
            "status": "NEW_SOURCE",
            "source": self.get_source(source_id),
            "source_id": source_id,
            "provenance_added": True,
            "possible_duplicate_source_ids": possible,
            "message": "Neue Source mit deterministischer Provenienz angelegt.",
        }

    def _backfill_legacy_source_provenance(self) -> None:
        with database(self.path) as connection:
            rows = connection.execute(
                """
                SELECT s.* FROM research_sources s
                WHERE NOT EXISTS (
                    SELECT 1 FROM source_provenance p WHERE p.source_id = s.id
                )
                ORDER BY s.created_at, s.id
                """
            ).fetchall()
            for row in rows:
                source = dict(row)
                source_type = str(source["source_type"])
                reference = _optional(source.get("reference"))
                direct_url = reference
                profile_url = None
                platform = source_type if source_type in {"youtube", "tiktok"} else None
                if platform and reference:
                    inspected_reference = inspect_source_identity(
                        title=str(source["title"]),
                        platform=platform,
                        direct_url=reference,
                    )
                    if inspected_reference["content_id"] is None:
                        direct_url = None
                        profile_url = reference
                identity = inspect_source_identity(
                    title=str(source["title"]),
                    platform=platform,
                    direct_url=direct_url,
                    profile_url=profile_url,
                    published_date=source.get("source_date"),
                )
                self._append_source_provenance(
                    connection,
                    source_id=str(source["id"]),
                    identity=identity,
                    provenance="Schema-v4-Backfill aus unveränderter Legacy-Source",
                    captured_at=str(source["created_at"]),
                )

    @staticmethod
    def _append_source_provenance(
        connection: object,
        *,
        source_id: str,
        identity: Mapping[str, object],
        provenance: str,
        captured_at: str,
    ) -> bool:
        existing = connection.execute(  # type: ignore[attr-defined]
            """
            SELECT id FROM source_provenance
            WHERE source_id = ? AND provenance_fingerprint = ?
            """,
            (source_id, identity["provenance_fingerprint"]),
        ).fetchone()
        if existing is not None:
            return False
        provenance_id = _id()
        connection.execute(  # type: ignore[attr-defined]
            """
            INSERT INTO source_provenance (
                id, source_id, platform, creator, provenance_title, direct_url,
                normalized_url, content_id, profile_url, published_date,
                local_filename, file_sha256, file_size, captured_at, provenance,
                source_fingerprint, provenance_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provenance_id,
                source_id,
                _optional(identity.get("platform")),
                _optional(identity.get("creator")),
                _optional(identity.get("provenance_title")),
                _optional(identity.get("direct_url")),
                _optional(identity.get("normalized_url")),
                _optional(identity.get("content_id")),
                _optional(identity.get("profile_url")),
                _optional(identity.get("published_date")),
                _optional(identity.get("local_filename")),
                _optional(identity.get("file_sha256")),
                identity.get("file_size"),
                captured_at,
                provenance,
                identity["source_fingerprint"],
                identity["provenance_fingerprint"],
            ),
        )
        for identity_type, identity_value in identity.get("identity_keys", []):  # type: ignore[assignment]
            existing_key = connection.execute(  # type: ignore[attr-defined]
                """
                SELECT source_id FROM source_identity_keys
                WHERE identity_type = ? AND identity_value = ?
                """,
                (identity_type, identity_value),
            ).fetchone()
            if existing_key is not None and str(existing_key["source_id"]) != source_id:
                raise ValueError("Neue Provenienz kollidiert mit der exakten Identität einer anderen Source.")
            connection.execute(  # type: ignore[attr-defined]
                """
                INSERT OR IGNORE INTO source_identity_keys (
                    id, source_id, provenance_id, identity_type, identity_value, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (_id(), source_id, provenance_id, identity_type, identity_value, captured_at),
            )
        return True

    @staticmethod
    def _possible_duplicate_source_ids(
        connection: object,
        *,
        title: str,
        creator: str | None,
        platform: str | None,
    ) -> list[str]:
        creator_key = normalize_source_title(creator)
        title_key = normalize_source_title(title)
        if not creator_key or not title_key:
            return []
        rows = connection.execute(  # type: ignore[attr-defined]
            """
            SELECT DISTINCT p.source_id, p.creator, p.provenance_title, p.platform
            FROM source_provenance p
            WHERE p.creator IS NOT NULL AND p.provenance_title IS NOT NULL
            """
        ).fetchall()
        return sorted(
            {
                str(row["source_id"])
                for row in rows
                if normalize_source_title(row["creator"]) == creator_key
                and normalize_source_title(row["provenance_title"]) == title_key
                and (not platform or not row["platform"] or str(row["platform"]).casefold() == platform.casefold())
            }
        )

    def get_source(self, source_id: str) -> dict[str, Any]:
        self._backfill_legacy_source_provenance()
        with database(self.path) as connection:
            result = _row(
                connection.execute(
                    "SELECT * FROM research_sources WHERE id = ?", (source_id,)
                ).fetchone()
            )
            if result is None:
                raise KeyError(f"Unbekannte Quelle: {source_id}")
            result["references"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM external_references WHERE target_type = 'source' AND target_id = ? ORDER BY created_at, id",
                    (source_id,),
                )
            ]
            result["provenance"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM source_provenance WHERE source_id = ? ORDER BY captured_at, id",
                    (source_id,),
                )
            ]
            result["identity_keys"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT identity_type, identity_value, provenance_id, created_at FROM source_identity_keys WHERE source_id = ? ORDER BY identity_type, identity_value",
                    (source_id,),
                )
            ]
            result["possible_duplicates"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT * FROM source_duplicate_assessments
                    WHERE source_id = ? OR possible_duplicate_source_id = ?
                    ORDER BY assessed_at, id
                    """,
                    (source_id, source_id),
                )
            ]
        return result

    def create_hypothesis(
        self,
        *,
        title: str,
        area: str,
        category: str,
        claim: str,
        mechanism: str,
        external_evidence: str,
        rating: str,
        risks_limitations: str,
        status: str = "RAW",
        strategy: str | None = None,
        asset_class: str | None = None,
        creation_reason: str = "Hypothese angelegt",
        created_at: object | None = None,
    ) -> dict[str, Any]:
        hypothesis_id = _id()
        timestamp = _timestamp(created_at)
        status_value = _choice(status, ALLOWED_HYPOTHESIS_STATUSES, "Status")
        normalized = normalize_claim(claim)
        values = (
            hypothesis_id,
            _required(title, "Hypothesentitel"),
            _choice(area, ALLOWED_AREAS, "Bereich"),
            _required(category, "Kategorie"),
            _required(claim, "Überprüfbare Behauptung"),
            normalized,
            _claim_fingerprint(normalized),
            _required(mechanism, "Vermuteter Mechanismus"),
            _choice(external_evidence, ALLOWED_EVIDENCE_STRENGTHS, "Externe Evidenz"),
            _choice(rating, ALLOWED_RATINGS, "A/B/C-Bewertung"),
            status_value,
            _required(risks_limitations, "Risiken und Limitierungen"),
            _optional(strategy),
            _optional(asset_class),
            timestamp,
            timestamp,
        )
        reason = _required(creation_reason, "Anlagebegründung")
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO hypotheses (
                    id, title, area, category, claim, normalized_claim, claim_fingerprint,
                    mechanism, external_evidence, rating, current_status, risks_limitations,
                    strategy, asset_class, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            connection.execute(
                """
                INSERT INTO hypothesis_status_history (
                    hypothesis_id, from_status, to_status, changed_at, reason
                ) VALUES (?, NULL, ?, ?, ?)
                """,
                (hypothesis_id, status_value, timestamp, reason),
            )
            connection.execute(
                """
                INSERT INTO hypothesis_evidence_assessments (
                    id, hypothesis_id, source_id, strength, confidence, rationale, assessed_at
                ) VALUES (?, ?, NULL, ?, NULL, ?, ?)
                """,
                (
                    _id(),
                    hypothesis_id,
                    values[8],
                    "Initiale Evidenzeinstufung beim Anlegen der Hypothese.",
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, to_status, metadata_json
                ) VALUES (?, 'hypothesis_created', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    reason,
                    status_value,
                    _json({"research_only": True, "automatic_strategy_integration": False}),
                ),
            )
        return self.get_hypothesis(hypothesis_id, include_details=False)

    def change_hypothesis_status(
        self,
        hypothesis_id: str,
        new_status: str,
        *,
        reason: str,
        retest_basis: str | None = None,
        validation_result_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        changed_at: object | None = None,
    ) -> dict[str, Any]:
        status_value = _choice(new_status, ALLOWED_HYPOTHESIS_STATUSES, "Status")
        reason_value = _required(reason, "Begründung der Statusänderung")
        timestamp = _timestamp(changed_at)
        with database(self.path) as connection:
            current = connection.execute(
                "SELECT current_status FROM hypotheses WHERE id = ?", (hypothesis_id,)
            ).fetchone()
            if current is None:
                raise KeyError(f"Unbekannte Hypothese: {hypothesis_id}")
            old_status = str(current["current_status"])
            if old_status == status_value:
                raise ValueError("Der neue Status entspricht bereits dem aktuellen Status.")
            if status_value == "VALIDATED":
                if validation_result_id is None:
                    raise ValueError(
                        "VALIDATED benötigt die explizite ID eines qualifiziert ausgewählten Resultats."
                    )
                selected = connection.execute(
                    """
                    SELECT 1 FROM hypothesis_validation_evidence
                    WHERE hypothesis_id = ? AND result_id = ?
                    """,
                    (hypothesis_id, validation_result_id),
                ).fetchone()
                if selected is None:
                    raise ValueError(
                        "Das angegebene Resultat wurde nicht als qualifizierte VALIDATED-Evidenz ausgewählt."
                    )
            basis_value = None
            if old_status == "REJECTED" and status_value != "REJECTED":
                basis_value = _choice(
                    retest_basis,
                    ALLOWED_RETEST_BASES,
                    "Grund für erneuten Test",
                )
            elif retest_basis is not None:
                basis_value = _choice(
                    retest_basis,
                    ALLOWED_RETEST_BASES,
                    "Grund für erneuten Test",
                )
            context_metadata = dict(metadata or {})
            if validation_result_id is not None:
                context_metadata["validation_result_id"] = validation_result_id
            if basis_value:
                context_metadata["retest_basis"] = basis_value
            connection.execute(
                """
                INSERT INTO status_change_context (
                    hypothesis_id, reason, changed_at, retest_basis, metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (hypothesis_id, reason_value, timestamp, basis_value, _json(context_metadata)),
            )
            connection.execute(
                "UPDATE hypotheses SET current_status = ?, updated_at = ? WHERE id = ?",
                (status_value, timestamp, hypothesis_id),
            )
        return self.get_hypothesis(hypothesis_id, include_details=False)

    def link_source(
        self,
        hypothesis_id: str,
        source_id: str,
        *,
        stance: str,
        note: str = "",
        linked_at: object | None = None,
    ) -> dict[str, Any]:
        link_id = _id()
        timestamp = _timestamp(linked_at)
        stance_value = _choice(stance, ALLOWED_SOURCE_STANCES, "Evidenzrichtung")
        note_value = str(note or "").strip()
        with database(self.path) as connection:
            hypothesis = connection.execute(
                "SELECT title FROM hypotheses WHERE id = ?", (hypothesis_id,)
            ).fetchone()
            source = connection.execute(
                "SELECT title FROM research_sources WHERE id = ?", (source_id,)
            ).fetchone()
            if hypothesis is None:
                raise KeyError(f"Unbekannte Hypothese: {hypothesis_id}")
            if source is None:
                raise KeyError(f"Unbekannte Quelle: {source_id}")
            connection.execute(
                """
                INSERT INTO hypothesis_sources (
                    id, hypothesis_id, source_id, stance, note, linked_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_id, hypothesis_id, source_id, stance_value, note_value, timestamp),
            )
            summary = f"Quelle „{source['title']}“ verknüpft ({stance_value})."
            if note_value:
                summary = f"{summary} {note_value}"
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, source_id, metadata_json
                ) VALUES (?, 'source_linked', ?, ?, ?, ?)
                """,
                (hypothesis_id, timestamp, summary, source_id, _json({"stance": stance_value})),
            )
        return {"id": link_id, "hypothesis_id": hypothesis_id, "source_id": source_id, "stance": stance_value, "note": note_value, "linked_at": timestamp}

    def record_external_review(
        self,
        hypothesis_id: str,
        *,
        summary: str,
        outcome: str | None = None,
        metadata: Mapping[str, object] | None = None,
        reviewed_at: object | None = None,
    ) -> dict[str, Any]:
        review_metadata = dict(metadata or {})
        if outcome:
            review_metadata["outcome"] = str(outcome).strip()
        return self.add_evidence_event(
            hypothesis_id,
            event_type="external_review",
            summary=summary,
            metadata=review_metadata,
            event_at=reviewed_at,
        )

    def add_evidence_event(
        self,
        hypothesis_id: str,
        *,
        event_type: str,
        summary: str,
        source_id: str | None = None,
        experiment_id: str | None = None,
        result_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        event_at: object | None = None,
    ) -> dict[str, Any]:
        timestamp = _timestamp(event_at)
        event_type_value = _required(event_type, "Ereignistyp")
        summary_value = _required(summary, "Evidenz-Zusammenfassung")
        with database(self.path) as connection:
            if connection.execute("SELECT 1 FROM hypotheses WHERE id = ?", (hypothesis_id,)).fetchone() is None:
                raise KeyError(f"Unbekannte Hypothese: {hypothesis_id}")
            self._validate_event_links(
                connection,
                hypothesis_id,
                source_id=source_id,
                experiment_id=experiment_id,
                result_id=result_id,
            )
            cursor = connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, source_id,
                    experiment_id, result_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    event_type_value,
                    timestamp,
                    summary_value,
                    source_id,
                    experiment_id,
                    result_id,
                    _json(dict(metadata or {})),
                ),
            )
            ledger_id = int(cursor.lastrowid)
        return {
            "id": ledger_id,
            "hypothesis_id": hypothesis_id,
            "event_type": event_type_value,
            "event_at": timestamp,
            "summary": summary_value,
            "source_id": source_id,
            "experiment_id": experiment_id,
            "result_id": result_id,
            "metadata": dict(metadata or {}),
        }

    @staticmethod
    def _validate_event_links(
        connection: object,
        hypothesis_id: str,
        *,
        source_id: str | None,
        experiment_id: str | None,
        result_id: str | None,
    ) -> None:
        if source_id and connection.execute(  # type: ignore[attr-defined]
            """
            SELECT 1 FROM hypothesis_sources
            WHERE hypothesis_id = ? AND source_id = ?
            """,
            (hypothesis_id, source_id),
        ).fetchone() is None:
            raise ValueError("Die Quelle ist nicht mit dieser Hypothese verknüpft.")
        if experiment_id and connection.execute(  # type: ignore[attr-defined]
            "SELECT 1 FROM experiments WHERE id = ? AND hypothesis_id = ?",
            (experiment_id, hypothesis_id),
        ).fetchone() is None:
            raise ValueError("Das Experiment gehört nicht zu dieser Hypothese.")
        if result_id and connection.execute(  # type: ignore[attr-defined]
            """
            SELECT 1 FROM research_results r
            JOIN experiments e ON e.id = r.experiment_id
            WHERE r.id = ? AND e.hypothesis_id = ?
            """,
            (result_id, hypothesis_id),
        ).fetchone() is None:
            raise ValueError("Das Ergebnis gehört nicht zu dieser Hypothese.")

    def create_experiment(
        self,
        hypothesis_id: str,
        *,
        title: str,
        test_definition: str,
        features: Iterable[str],
        data_universe: str,
        point_in_time_rules: str,
        baseline: str,
        parameters: object,
        test_status: str = "DRAFT",
        period_start: object | None = None,
        period_end: object | None = None,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        experiment_id = _id()
        timestamp = _timestamp(created_at)
        start = _date_text(period_start, "Testbeginn")
        end = _date_text(period_end, "Testende")
        if start and end and start > end:
            raise ValueError("Testbeginn darf nicht nach dem Testende liegen.")
        feature_values = sorted({_required(item, "Feature") for item in features}, key=str.casefold)
        if not feature_values:
            raise ValueError("Mindestens ein verwendetes Feature muss dokumentiert sein.")
        status_value = _choice(test_status, ALLOWED_EXPERIMENT_STATUSES, "Teststatus")
        with database(self.path) as connection:
            if connection.execute("SELECT 1 FROM hypotheses WHERE id = ?", (hypothesis_id,)).fetchone() is None:
                raise KeyError(f"Unbekannte Hypothese: {hypothesis_id}")
            connection.execute(
                """
                INSERT INTO experiments (
                    id, hypothesis_id, title, test_definition, data_universe,
                    period_start, period_end, point_in_time_rules, baseline,
                    parameters_json, current_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    hypothesis_id,
                    _required(title, "Experimenttitel"),
                    _required(test_definition, "Testdefinition"),
                    _required(data_universe, "Datenuniversum"),
                    start,
                    end,
                    _required(point_in_time_rules, "Point-in-Time-Regeln"),
                    _required(baseline, "Baseline"),
                    _json(parameters),
                    status_value,
                    timestamp,
                    timestamp,
                ),
            )
            connection.executemany(
                "INSERT INTO experiment_features (experiment_id, feature) VALUES (?, ?)",
                [(experiment_id, feature) for feature in feature_values],
            )
            connection.execute(
                """
                INSERT INTO experiment_status_history (
                    experiment_id, from_status, to_status, changed_at, reason
                ) VALUES (?, NULL, ?, ?, 'Experiment definiert')
                """,
                (experiment_id, status_value, timestamp),
            )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary, experiment_id, metadata_json
                ) VALUES (?, 'experiment_defined', ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    timestamp,
                    f"Experiment „{_required(title, 'Experimenttitel')}“ definiert.",
                    experiment_id,
                    _json({"test_status": status_value, "features": feature_values}),
                ),
            )
        return self.get_experiment(experiment_id)

    def change_experiment_status(
        self,
        experiment_id: str,
        new_status: str,
        *,
        reason: str,
        changed_at: object | None = None,
    ) -> dict[str, Any]:
        status_value = _choice(new_status, ALLOWED_EXPERIMENT_STATUSES, "Teststatus")
        reason_value = _required(reason, "Begründung der Teststatusänderung")
        timestamp = _timestamp(changed_at)
        with database(self.path) as connection:
            current = connection.execute(
                "SELECT current_status FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
            if current is None:
                raise KeyError(f"Unbekanntes Experiment: {experiment_id}")
            if str(current["current_status"]) == status_value:
                raise ValueError("Der neue Teststatus entspricht bereits dem aktuellen Status.")
            connection.execute(
                """
                INSERT INTO experiment_status_change_context (experiment_id, reason, changed_at)
                VALUES (?, ?, ?)
                """,
                (experiment_id, reason_value, timestamp),
            )
            connection.execute(
                "UPDATE experiments SET current_status = ?, updated_at = ? WHERE id = ?",
                (status_value, timestamp, experiment_id),
            )
        return self.get_experiment(experiment_id)

    def record_result(
        self,
        experiment_id: str,
        *,
        title: str,
        conclusion: str,
        interpretation: str,
        sample_size: int | None = None,
        hit_rate: object | None = None,
        expectancy: object | None = None,
        profit_factor: object | None = None,
        mfe: object | None = None,
        mae: object | None = None,
        drawdown: object | None = None,
        r_multiples: object | None = None,
        costs: object | None = None,
        slippage: object | None = None,
        in_sample: object | None = None,
        validation: object | None = None,
        out_of_sample: object | None = None,
        walk_forward: object | None = None,
        forward: object | None = None,
        papertrade: object | None = None,
        idempotency_key: str | None = None,
        recorded_at: object | None = None,
    ) -> dict[str, Any]:
        result_id = _id()
        timestamp = _timestamp(recorded_at)
        if sample_size is not None:
            try:
                numeric_sample_size = float(sample_size)
            except (TypeError, ValueError) as exc:
                raise ValueError("Sample Size muss eine ganze Zahl sein.") from exc
            if not math.isfinite(numeric_sample_size) or not numeric_sample_size.is_integer():
                raise ValueError("Sample Size muss eine ganze Zahl sein.")
            sample_size = int(numeric_sample_size)
            if sample_size < 0:
                raise ValueError("Sample Size darf nicht negativ sein.")
        conclusion_value = _choice(conclusion, ALLOWED_RESULT_CONCLUSIONS, "Ergebniseinordnung")
        title_value = _required(title, "Ergebnistitel")
        interpretation_value = _required(interpretation, "Ergebnisinterpretation")
        stages = [in_sample, validation, out_of_sample, walk_forward, forward, papertrade]
        stage_json = [None if value is None else _json(value) for value in stages]
        identity_key = _optional(idempotency_key)
        with database(self.path) as connection:
            if identity_key is not None:
                existing_identity = connection.execute(
                    "SELECT result_id FROM research_result_identities WHERE idempotency_key = ?",
                    (identity_key,),
                ).fetchone()
                if existing_identity is not None:
                    existing = self.get_result(str(existing_identity["result_id"]))
                    existing["idempotent_replay"] = True
                    return existing
            experiment = connection.execute(
                "SELECT hypothesis_id FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
            if experiment is None:
                raise KeyError(f"Unbekanntes Experiment: {experiment_id}")
            connection.execute(
                """
                INSERT INTO research_results (
                    id, experiment_id, title, conclusion, sample_size, hit_rate,
                    expectancy, profit_factor, mfe, mae, drawdown, r_multiples,
                    costs, slippage, in_sample_json, validation_json,
                    out_of_sample_json, walk_forward_json, forward_json,
                    papertrade_json, interpretation, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    experiment_id,
                    title_value,
                    conclusion_value,
                    sample_size,
                    _number(hit_rate, "Trefferquote"),
                    _number(expectancy, "Expectancy"),
                    _number(profit_factor, "Profit Factor", minimum=0),
                    _number(mfe, "MFE"),
                    _number(mae, "MAE"),
                    _number(drawdown, "Drawdown"),
                    _number(r_multiples, "R-Multiples"),
                    _number(costs, "Kosten"),
                    _number(slippage, "Slippage"),
                    *stage_json,
                    interpretation_value,
                    timestamp,
                ),
            )
            if identity_key is not None:
                connection.execute(
                    """
                    INSERT INTO research_result_identities (idempotency_key, result_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (identity_key, result_id, timestamp),
                )
            connection.execute(
                """
                INSERT INTO evidence_ledger (
                    hypothesis_id, event_type, event_at, summary,
                    experiment_id, result_id, metadata_json
                ) VALUES (?, 'result_recorded', ?, ?, ?, ?, ?)
                """,
                (
                    str(experiment["hypothesis_id"]),
                    timestamp,
                    f"Ergebnis „{title_value}“: {interpretation_value}",
                    experiment_id,
                    result_id,
                    _json({"conclusion": conclusion_value, "sample_size": sample_size}),
                ),
            )
        return self.get_result(result_id)

    def get_result(self, result_id: str) -> dict[str, Any]:
        with database(self.path) as connection:
            result = _row(
                connection.execute(
                    "SELECT * FROM research_results WHERE id = ?", (result_id,)
                ).fetchone()
            )
            if result is None:
                raise KeyError(f"Unbekanntes Ergebnis: {result_id}")
            self._decode_result(result)
            result["references"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM external_references WHERE target_type = 'result' AND target_id = ? ORDER BY created_at, id",
                    (result_id,),
                )
            ]
            result["validation_assessments"] = []
            for item in connection.execute(
                "SELECT * FROM result_validation_assessments WHERE result_id = ? ORDER BY assessed_at, id",
                (result_id,),
            ):
                assessment = dict(item)
                assessment["scope_contract"] = _json_value(assessment.pop("scope_contract_json", None))
                assessment["artifact_references"] = _json_value(
                    assessment.pop("artifact_references_json", None)
                )
                result["validation_assessments"].append(assessment)
            result["work_request_links"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM work_request_result_links WHERE result_id = ? ORDER BY linked_at, id",
                    (result_id,),
                )
            ]
        return result

    @staticmethod
    def _decode_result(result: dict[str, Any]) -> None:
        for key in (
            "in_sample_json",
            "validation_json",
            "out_of_sample_json",
            "walk_forward_json",
            "forward_json",
            "papertrade_json",
        ):
            result[key.removesuffix("_json")] = _json_value(result.pop(key, None))

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        with database(self.path) as connection:
            result = _row(
                connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
            )
            if result is None:
                raise KeyError(f"Unbekanntes Experiment: {experiment_id}")
            result["parameters"] = _json_value(result.pop("parameters_json", None))
            result["features"] = [
                str(item["feature"])
                for item in connection.execute(
                    "SELECT feature FROM experiment_features WHERE experiment_id = ? ORDER BY feature COLLATE NOCASE",
                    (experiment_id,),
                )
            ]
            result["status_history"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM experiment_status_history WHERE experiment_id = ? ORDER BY changed_at, id",
                    (experiment_id,),
                )
            ]
            result["results"] = []
            for item in connection.execute(
                "SELECT * FROM research_results WHERE experiment_id = ? ORDER BY recorded_at, id",
                (experiment_id,),
            ):
                decoded = dict(item)
                self._decode_result(decoded)
                decoded["references"] = [
                    dict(reference)
                    for reference in connection.execute(
                        "SELECT * FROM external_references WHERE target_type = 'result' AND target_id = ? ORDER BY created_at, id",
                        (decoded["id"],),
                    )
                ]
                result["results"].append(decoded)
            result["references"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM external_references WHERE target_type = 'experiment' AND target_id = ? ORDER BY created_at, id",
                    (experiment_id,),
                )
            ]
        return result

    def link_hypotheses(
        self,
        hypothesis_id: str,
        related_hypothesis_id: str,
        *,
        relation_type: str = "similar",
        note: str = "",
        created_at: object | None = None,
    ) -> dict[str, Any]:
        relation_id = _id()
        relation_value = _choice(relation_type, ALLOWED_RELATION_TYPES, "Beziehungstyp")
        timestamp = _timestamp(created_at)
        note_value = str(note or "").strip()
        if hypothesis_id == related_hypothesis_id:
            raise ValueError("Eine Hypothese kann nicht mit sich selbst verknüpft werden.")
        with database(self.path) as connection:
            rows = connection.execute(
                "SELECT id, title FROM hypotheses WHERE id IN (?, ?)",
                (hypothesis_id, related_hypothesis_id),
            ).fetchall()
            by_id = {str(item["id"]): item for item in rows}
            if hypothesis_id not in by_id:
                raise KeyError(f"Unbekannte Hypothese: {hypothesis_id}")
            if related_hypothesis_id not in by_id:
                raise KeyError(f"Unbekannte Hypothese: {related_hypothesis_id}")
            connection.execute(
                """
                INSERT INTO hypothesis_relations (
                    id, hypothesis_id, related_hypothesis_id, relation_type, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (relation_id, hypothesis_id, related_hypothesis_id, relation_value, note_value, timestamp),
            )
            for owner_id, other_id in (
                (hypothesis_id, related_hypothesis_id),
                (related_hypothesis_id, hypothesis_id),
            ):
                connection.execute(
                    """
                    INSERT INTO evidence_ledger (
                        hypothesis_id, event_type, event_at, summary, metadata_json
                    ) VALUES (?, 'hypothesis_related', ?, ?, ?)
                    """,
                    (
                        owner_id,
                        timestamp,
                        f"Verwandte Hypothese „{by_id[other_id]['title']}“ verknüpft ({relation_value}).",
                        _json({"related_hypothesis_id": other_id, "relation_type": relation_value, "note": note_value}),
                    ),
                )
        return {
            "id": relation_id,
            "hypothesis_id": hypothesis_id,
            "related_hypothesis_id": related_hypothesis_id,
            "relation_type": relation_value,
            "note": note_value,
            "created_at": timestamp,
        }

    def add_external_reference(
        self,
        *,
        target_type: str,
        target_id: str,
        system: str,
        record_type: str,
        record_id: str,
        uri: str | None = None,
        description: str = "",
        created_at: object | None = None,
    ) -> dict[str, Any]:
        if target_type not in _TARGET_TABLES:
            raise ValueError(f"Unbekannter Referenztyp: {target_type}")
        reference_id = _id()
        timestamp = _timestamp(created_at)
        with database(self.path) as connection:
            table = _TARGET_TABLES[target_type]
            target = connection.execute(f"SELECT id FROM {table} WHERE id = ?", (target_id,)).fetchone()
            if target is None:
                raise KeyError(f"Unbekanntes Referenzziel: {target_type}/{target_id}")
            connection.execute(
                """
                INSERT INTO external_references (
                    id, target_type, target_id, system, record_type, record_id,
                    uri, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reference_id,
                    target_type,
                    target_id,
                    _required(system, "Referenzsystem"),
                    _required(record_type, "Datensatztyp"),
                    _required(record_id, "Datensatz-ID"),
                    _optional(uri),
                    str(description or "").strip(),
                    timestamp,
                ),
            )
            hypothesis_id = self._hypothesis_for_target(connection, target_type, target_id)
            if hypothesis_id:
                connection.execute(
                    """
                    INSERT INTO evidence_ledger (
                        hypothesis_id, event_type, event_at, summary, metadata_json
                    ) VALUES (?, 'external_reference_linked', ?, ?, ?)
                    """,
                    (
                        hypothesis_id,
                        timestamp,
                        f"Bestehendes Research-Artefakt {system}/{record_type}/{record_id} referenziert.",
                        _json({"target_type": target_type, "target_id": target_id, "reference_id": reference_id}),
                    ),
                )
        return {
            "id": reference_id,
            "target_type": target_type,
            "target_id": target_id,
            "system": system,
            "record_type": record_type,
            "record_id": record_id,
            "uri": _optional(uri),
            "description": str(description or "").strip(),
            "created_at": timestamp,
        }

    @staticmethod
    def _hypothesis_for_target(connection: object, target_type: str, target_id: str) -> str | None:
        if target_type == "hypothesis":
            return target_id
        if target_type == "source":
            return None
        if target_type == "experiment":
            row = connection.execute(  # type: ignore[attr-defined]
                "SELECT hypothesis_id FROM experiments WHERE id = ?", (target_id,)
            ).fetchone()
            return None if row is None else str(row["hypothesis_id"])
        row = connection.execute(  # type: ignore[attr-defined]
            """
            SELECT e.hypothesis_id FROM research_results r
            JOIN experiments e ON e.id = r.experiment_id WHERE r.id = ?
            """,
            (target_id,),
        ).fetchone()
        return None if row is None else str(row["hypothesis_id"])

    def search_hypotheses(
        self,
        *,
        query: str | None = None,
        category: str | None = None,
        feature: str | None = None,
        strategy: str | None = None,
        asset_class: str | None = None,
        source: str | None = None,
        status: str | None = None,
        rating: str | None = None,
        area: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1_000:
            raise ValueError("Limit muss zwischen 1 und 1000 liegen.")
        conditions: list[str] = []
        parameters: list[object] = []

        def contains(columns: tuple[str, ...], value: str) -> str:
            escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            parameters.extend(pattern for _ in columns)
            return "(" + " OR ".join(f"{column} LIKE ? ESCAPE '\\' COLLATE NOCASE" for column in columns) + ")"

        if query and str(query).strip():
            conditions.append(contains(("h.title", "h.claim", "h.mechanism", "h.risks_limitations"), str(query).strip()))
        if category and str(category).strip():
            conditions.append(contains(("h.category",), str(category).strip()))
        if strategy and str(strategy).strip():
            conditions.append(contains(("h.strategy",), str(strategy).strip()))
        if asset_class and str(asset_class).strip():
            conditions.append(contains(("h.asset_class",), str(asset_class).strip()))
        if area and area != "ALL":
            conditions.append("h.area = ?")
            parameters.append(_choice(area, ALLOWED_AREAS, "Bereich"))
        if rating and rating != "ALL":
            conditions.append("h.rating = ?")
            parameters.append(_choice(rating, ALLOWED_RATINGS, "A/B/C-Bewertung"))
        if status and status != "ALL":
            conditions.append(
                "(h.current_status = ? OR EXISTS (SELECT 1 FROM hypothesis_status_history sh WHERE sh.hypothesis_id = h.id AND sh.to_status = ?))"
            )
            status_value = _choice(status, ALLOWED_HYPOTHESIS_STATUSES, "Status")
            parameters.extend((status_value, status_value))
        if feature and str(feature).strip():
            escaped = str(feature).strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(
                "EXISTS (SELECT 1 FROM experiments e JOIN experiment_features ef ON ef.experiment_id = e.id WHERE e.hypothesis_id = h.id AND ef.feature LIKE ? ESCAPE '\\' COLLATE NOCASE)"
            )
            parameters.append(f"%{escaped}%")
        if source and str(source).strip():
            escaped = str(source).strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(
                """
                EXISTS (
                    SELECT 1 FROM hypothesis_sources hs
                    JOIN research_sources s ON s.id = hs.source_id
                    WHERE hs.hypothesis_id = h.id
                      AND (s.title LIKE ? ESCAPE '\\' COLLATE NOCASE
                           OR s.reference LIKE ? ESCAPE '\\' COLLATE NOCASE
                           OR s.source_type LIKE ? ESCAPE '\\' COLLATE NOCASE)
                )
                """
            )
            parameters.extend((f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"))
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        parameters.append(limit)
        with database(self.path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    h.*,
                    COALESCE(
                        (SELECT hea.strength FROM hypothesis_evidence_assessments hea
                         WHERE hea.hypothesis_id = h.id ORDER BY hea.assessed_at DESC, hea.rowid DESC LIMIT 1),
                        h.external_evidence
                    ) AS effective_external_evidence,
                    (SELECT hea.confidence FROM hypothesis_evidence_assessments hea
                     WHERE hea.hypothesis_id = h.id ORDER BY hea.assessed_at DESC, hea.rowid DESC LIMIT 1)
                        AS evidence_confidence,
                    (SELECT COUNT(*) FROM hypothesis_sources hs WHERE hs.hypothesis_id = h.id) AS source_count,
                    (SELECT COUNT(*) FROM experiments e WHERE e.hypothesis_id = h.id) AS experiment_count,
                    (SELECT COUNT(*) FROM research_results r JOIN experiments e ON e.id = r.experiment_id WHERE e.hypothesis_id = h.id) AS result_count,
                    (SELECT COUNT(*) FROM research_results r JOIN experiments e ON e.id = r.experiment_id WHERE e.hypothesis_id = h.id AND r.conclusion IN ('contradicts', 'negative')) AS negative_result_count,
                    EXISTS(SELECT 1 FROM hypothesis_status_history sh WHERE sh.hypothesis_id = h.id AND sh.to_status = 'REJECTED') AS was_rejected
                FROM hypotheses h
                {where}
                ORDER BY h.updated_at DESC, h.created_at DESC, h.id
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [dict(item) for item in rows]

    def get_hypothesis(self, hypothesis_id: str, *, include_details: bool = True) -> dict[str, Any]:
        with database(self.path) as connection:
            result = _row(connection.execute("SELECT * FROM hypotheses WHERE id = ?", (hypothesis_id,)).fetchone())
            if result is None:
                raise KeyError(f"Unbekannte Hypothese: {hypothesis_id}")
            result["evidence_assessments"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT * FROM hypothesis_evidence_assessments
                    WHERE hypothesis_id = ? ORDER BY assessed_at, rowid
                    """,
                    (hypothesis_id,),
                )
            ]
            latest_evidence = result["evidence_assessments"][-1]
            result["effective_external_evidence"] = latest_evidence["strength"]
            result["evidence_confidence"] = latest_evidence["confidence"]
            if not include_details:
                return result
            result["sources"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT s.*, hs.stance, hs.note AS link_note, hs.linked_at
                    FROM hypothesis_sources hs
                    JOIN research_sources s ON s.id = hs.source_id
                    WHERE hs.hypothesis_id = ?
                    ORDER BY hs.linked_at, hs.id
                    """,
                    (hypothesis_id,),
                )
            ]
            for source in result["sources"]:
                source["provenance"] = [
                    dict(item)
                    for item in connection.execute(
                        "SELECT * FROM source_provenance WHERE source_id = ? ORDER BY captured_at, id",
                        (source["id"],),
                    )
                ]
                source["identity_keys"] = [
                    dict(item)
                    for item in connection.execute(
                        "SELECT identity_type, identity_value, created_at FROM source_identity_keys WHERE source_id = ? ORDER BY identity_type, identity_value",
                        (source["id"],),
                    )
                ]
            experiment_ids = [
                str(item["id"])
                for item in connection.execute(
                    "SELECT id FROM experiments WHERE hypothesis_id = ? ORDER BY created_at, id",
                    (hypothesis_id,),
                )
            ]
            result["experiments"] = [self.get_experiment(item) for item in experiment_ids]
            result["status_history"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM hypothesis_status_history WHERE hypothesis_id = ? ORDER BY changed_at, id",
                    (hypothesis_id,),
                )
            ]
            result["ledger"] = []
            for item in connection.execute(
                "SELECT * FROM evidence_ledger WHERE hypothesis_id = ? ORDER BY event_at, id",
                (hypothesis_id,),
            ):
                event = dict(item)
                event["metadata"] = _json_value(event.pop("metadata_json", None))
                result["ledger"].append(event)
            result["relations"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT hr.*, other.id AS other_id, other.title AS other_title,
                           CASE WHEN hr.hypothesis_id = ? THEN 'outgoing' ELSE 'incoming' END AS direction
                    FROM hypothesis_relations hr
                    JOIN hypotheses other
                      ON other.id = CASE WHEN hr.hypothesis_id = ? THEN hr.related_hypothesis_id ELSE hr.hypothesis_id END
                    WHERE hr.hypothesis_id = ? OR hr.related_hypothesis_id = ?
                    ORDER BY hr.created_at, hr.id
                    """,
                    (hypothesis_id, hypothesis_id, hypothesis_id, hypothesis_id),
                )
            ]
            result["references"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM external_references WHERE target_type = 'hypothesis' AND target_id = ? ORDER BY created_at, id",
                    (hypothesis_id,),
                )
            ]
        return result

    def find_similar_hypotheses(
        self,
        *,
        title: str,
        claim: str,
        category: str | None = None,
        area: str | None = None,
        asset_class: str | None = None,
        exclude_id: str | None = None,
        minimum_score: float = 0.2,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if minimum_score < 0 or minimum_score > 1:
            raise ValueError("Ähnlichkeitsschwelle muss zwischen 0 und 1 liegen.")
        query_normalized = normalize_claim(f"{title} {claim}")
        query_tokens = _tokens(query_normalized)
        exact_fingerprint = _claim_fingerprint(normalize_claim(claim))
        rows = self.search_hypotheses(
            category=category,
            area=area,
            asset_class=asset_class,
            limit=1_000,
        )
        scored: list[dict[str, Any]] = []
        for item in rows:
            if exclude_id and item["id"] == exclude_id:
                continue
            candidate_tokens = _tokens(f"{item['title']} {item['claim']}")
            union = query_tokens | candidate_tokens
            score = len(query_tokens & candidate_tokens) / len(union) if union else 0.0
            exact = item["claim_fingerprint"] == exact_fingerprint
            if exact:
                score = 1.0
            if score < minimum_score:
                continue
            detail = self.get_hypothesis(str(item["id"]))
            rejection = next(
                (
                    status
                    for status in reversed(detail["status_history"])
                    if status["to_status"] == "REJECTED"
                ),
                None,
            )
            scored.append(
                {
                    **item,
                    "similarity_score": round(score, 4),
                    "exact_claim_match": exact,
                    "rejection_reason": None if rejection is None else rejection["reason"],
                    "result_summaries": [
                        {
                            "title": result["title"],
                            "conclusion": result["conclusion"],
                            "interpretation": result["interpretation"],
                        }
                        for experiment in detail["experiments"]
                        for result in experiment["results"]
                    ],
                }
            )
        scored.sort(key=lambda item: (-float(item["similarity_score"]), str(item["updated_at"]), str(item["id"])))
        return scored[:limit]

    def filter_values(self) -> dict[str, list[str]]:
        with database(self.path) as connection:
            def values(column: str) -> list[str]:
                return [
                    str(item[0])
                    for item in connection.execute(
                        f"SELECT DISTINCT {column} FROM hypotheses WHERE {column} IS NOT NULL AND TRIM({column}) <> '' ORDER BY {column} COLLATE NOCASE"
                    )
                ]

            features = [
                str(item[0])
                for item in connection.execute(
                    "SELECT DISTINCT feature FROM experiment_features ORDER BY feature COLLATE NOCASE"
                )
            ]
            return {
                "categories": values("category"),
                "strategies": values("strategy"),
                "asset_classes": values("asset_class"),
                "features": features,
            }

    def health(self) -> dict[str, Any]:
        with database(self.path) as connection:
            quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            counts = {
                "sources": int(connection.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0]),
                "hypotheses": int(connection.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]),
                "experiments": int(connection.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]),
                "results": int(connection.execute("SELECT COUNT(*) FROM research_results").fetchone()[0]),
                "ledger_events": int(connection.execute("SELECT COUNT(*) FROM evidence_ledger").fetchone()[0]),
                "work_requests": int(connection.execute("SELECT COUNT(*) FROM research_work_requests").fetchone()[0]),
            }
        return {
            "status": "ok" if quick_check.lower() == "ok" and version == CURRENT_SCHEMA_VERSION else "attention",
            "quick_check": quick_check,
            "schema_version": version,
            "current_schema_version": CURRENT_SCHEMA_VERSION,
            **counts,
        }
