from __future__ import annotations

"""Read-only, deterministic export of domain-specific general knowledge."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator

from .schema import ALLOWED_KNOWLEDGE_DOMAINS, CURRENT_SCHEMA_VERSION, DEFAULT_DATABASE_PATH
from .source_identity import sha256_file


EXPORT_SCHEMA_VERSION = 1


def _json_value(value: object, default: object) -> object:
    try:
        return json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return default


def _latest_nonempty(rows: list[dict[str, Any]], field: str) -> object | None:
    for row in reversed(rows):
        value = row.get(field)
        if value not in (None, ""):
            return value
    return None


class KnowledgeExporter:
    """Exports without initializing, migrating or writing to the source database."""

    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Knowledge Base nicht gefunden: {self.path}")

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version < 7:
            connection.close()
            raise RuntimeError("Domain-Export benötigt Knowledge-Base-Schema 7 oder neuer.")
        if version > CURRENT_SCHEMA_VERSION:
            connection.close()
            raise RuntimeError("Knowledge Base stammt aus einer neueren App-Version.")
        return connection

    @staticmethod
    def _source_payload(connection: sqlite3.Connection, source_id: str) -> dict[str, Any]:
        source_row = connection.execute(
            "SELECT * FROM research_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if source_row is None:  # pragma: no cover - foreign key protects this
            raise RuntimeError(f"Source fehlt: {source_id}")
        source = dict(source_row)
        provenance = [
            dict(item)
            for item in connection.execute(
                """
                SELECT * FROM source_provenance
                WHERE source_id = ? ORDER BY captured_at, id
                """,
                (source_id,),
            )
        ]
        transcript_reference: dict[str, Any] | None = None
        for raw in connection.execute(
            """
            SELECT * FROM source_transcription_records
            WHERE source_id = ? AND status IN ('EXISTING', 'GENERATED')
            ORDER BY created_at DESC, id DESC
            """,
            (source_id,),
        ):
            item = dict(raw)
            path_text = str(item.get("transcript_path") or "").strip()
            artifact = Path(path_text) if path_text else None
            if artifact is None or not artifact.is_file():
                continue
            expected_hash = str(item.get("transcript_sha256") or "")
            if expected_hash and sha256_file(artifact) != expected_hash:
                continue
            transcript_reference = {
                "status": item["status"],
                "path": str(artifact),
                "sha256": item.get("transcript_sha256"),
                "language": item.get("language"),
                "engine": item.get("engine"),
                "engine_version": item.get("engine_version"),
                "model": item.get("model"),
                "machine_generated": bool(item.get("machine_generated")),
                "created_at": item.get("created_at"),
            }
            break
        return {
            "source_id": source_id,
            "source_title": source["title"],
            "source_type": source["source_type"],
            "creator": _latest_nonempty(provenance, "creator"),
            "platform": _latest_nonempty(provenance, "platform"),
            "original_url": _latest_nonempty(provenance, "direct_url") or source.get("reference"),
            "normalized_url": _latest_nonempty(provenance, "normalized_url"),
            "published_date": _latest_nonempty(provenance, "published_date") or source.get("source_date"),
            "source_fingerprint": _latest_nonempty(provenance, "source_fingerprint"),
            "transcript_reference": transcript_reference,
        }

    @staticmethod
    def _latest_classification(
        connection: sqlite3.Connection,
        claim_id: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT * FROM claim_domain_assessments
            WHERE claim_id = ?
            ORDER BY classified_at DESC, rowid DESC LIMIT 1
            """,
            (claim_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["secondary_domains"] = _json_value(
            result.pop("secondary_domains_json", None),
            [],
        )
        return result

    @staticmethod
    def _latest_verification(
        connection: sqlite3.Connection,
        claim_id: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT * FROM claim_verification_assessments
            WHERE claim_id = ?
            ORDER BY assessed_at DESC, rowid DESC LIMIT 1
            """,
            (claim_id,),
        ).fetchone()
        if row is None:
            return None
        verification = dict(row)
        references = [
            dict(item)
            for item in connection.execute(
                """
                SELECT * FROM claim_verification_references
                WHERE assessment_id = ? ORDER BY reference_type, reference_fingerprint, id
                """,
                (verification["id"],),
            )
        ]
        verification["verifying_sources"] = [
            item for item in references if item["reference_type"] == "VERIFYING"
        ]
        verification["counter_evidence"] = [
            item for item in references if item["reference_type"] == "COUNTER_EVIDENCE"
        ]
        return verification

    @staticmethod
    def _relations(connection: sqlite3.Connection, claim_id: str) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in connection.execute(
                """
                SELECT r.id, r.claim_id, r.related_claim_id, r.relation_type,
                       r.rationale, r.created_at,
                       CASE WHEN r.claim_id = ? THEN 'outgoing' ELSE 'incoming' END AS direction
                FROM knowledge_claim_relations r
                WHERE r.claim_id = ? OR r.related_claim_id = ?
                ORDER BY r.created_at, r.id
                """,
                (claim_id, claim_id, claim_id),
            )
        ]

    def iter_domain_claims(
        self,
        domain: str,
        *,
        verified_only: bool = False,
    ) -> Iterator[dict[str, Any]]:
        domain_value = str(domain).strip().upper()
        if domain_value not in ALLOWED_KNOWLEDGE_DOMAINS:
            raise ValueError(f"Unbekannte Wissensdomäne: {domain}")
        connection = self._connection()
        try:
            source_cache: dict[str, dict[str, Any]] = {}
            rows = connection.execute(
                """
                SELECT * FROM source_claims
                ORDER BY created_at, source_id, id
                """
            ).fetchall()
            for raw in rows:
                claim = dict(raw)
                classification = self._latest_classification(connection, str(claim["id"]))
                if classification is None:
                    continue
                secondary = set(classification["secondary_domains"])
                if classification["primary_domain"] != domain_value and domain_value not in secondary:
                    continue
                verification = self._latest_verification(connection, str(claim["id"]))
                if verified_only and (
                    verification is None or verification["verification_state"] == "UNVERIFIED"
                ):
                    continue
                source_id = str(claim["source_id"])
                if source_id not in source_cache:
                    source_cache[source_id] = self._source_payload(connection, source_id)
                source = dict(source_cache[source_id])
                payload = {
                    **source,
                    "export_key": f"{source_id}:{claim['id']}",
                    "claim_id": claim["id"],
                    "claim_text": claim["claim_text"],
                    "claim_fingerprint": claim["claim_fingerprint"],
                    "primary_domain": classification["primary_domain"],
                    "secondary_domains": classification["secondary_domains"],
                    "subcategory": classification.get("subcategory"),
                    "trading_relevance": classification["trading_relevance"],
                    "trading_path_approved": bool(classification["trading_path_approved"]),
                    "classification_rationale": classification["rationale"],
                    "classification_at": classification["classified_at"],
                    "verification_state": (
                        verification["verification_state"] if verification else "UNVERIFIED"
                    ),
                    "evidence_strength": (
                        verification["evidence_strength"] if verification else "weak"
                    ),
                    "confidence": verification.get("confidence") if verification else None,
                    "verifying_sources": verification.get("verifying_sources", []) if verification else [],
                    "counter_evidence": verification.get("counter_evidence", []) if verification else [],
                    "limitations": verification.get("limitations", "") if verification else "",
                    "jurisdiction": verification.get("jurisdiction") if verification else None,
                    "valid_from": verification.get("valid_from") if verification else None,
                    "valid_until": verification.get("valid_until") if verification else None,
                    "valid_as_of": verification.get("valid_as_of") if verification else None,
                    "update_required": bool(verification.get("update_required")) if verification else False,
                    "verification_rationale": verification.get("rationale", "") if verification else "",
                    "verified_at": verification.get("assessed_at") if verification else None,
                    "captured_at": claim["created_at"],
                    "relationships": self._relations(connection, str(claim["id"])),
                }
                yield payload
        finally:
            connection.close()

    def export(
        self,
        domain: str,
        *,
        verified_only: bool = False,
    ) -> dict[str, Any]:
        domain_value = str(domain).strip().upper()
        claims = list(self.iter_domain_claims(domain_value, verified_only=verified_only))
        payload: dict[str, Any] = {
            "export_schema_version": EXPORT_SCHEMA_VERSION,
            "domain": domain_value,
            "verified_only": verified_only,
            "claims": claims,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            allow_nan=False,
        )
        payload["export_fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload

    def export_json(self, domain: str, *, verified_only: bool = False) -> str:
        return json.dumps(
            self.export(domain, verified_only=verified_only),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str,
            allow_nan=False,
        ) + "\n"

    def export_markdown(self, domain: str, *, verified_only: bool = False) -> str:
        payload = self.export(domain, verified_only=verified_only)
        lines = [
            f"# Knowledge Export: {payload['domain']}",
            "",
            f"Export-Fingerprint: `{payload['export_fingerprint']}`",
            "",
        ]
        for item in payload["claims"]:
            lines.extend(
                [
                    f"## {item['claim_text']}",
                    "",
                    f"- Source: {item['source_title']} (`{item['source_id']}`)",
                    f"- Domain: {item['primary_domain']}",
                    f"- Unterkategorie: {item['subcategory'] or '–'}",
                    f"- Trading-Relevanz: {item['trading_relevance']}",
                    f"- Verifikation: {item['verification_state']}",
                    f"- Evidenz/Confidence: {item['evidence_strength']} / {item['confidence'] if item['confidence'] is not None else '–'}",
                    f"- Jurisdiktion: {item['jurisdiction'] or '–'}",
                    f"- Valid as of: {item['valid_as_of'] or '–'}",
                    f"- Einschränkungen: {item['limitations'] or '–'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


__all__ = ["EXPORT_SCHEMA_VERSION", "KnowledgeExporter"]
