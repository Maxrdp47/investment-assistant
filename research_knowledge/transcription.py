from __future__ import annotations

"""Conditional, local speech-to-text fallback for research media.

This module deliberately performs no claim extraction or LLM analysis.  It only
stores transcript artifacts and their provenance on an already identified
research source.
"""

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .schema import (
    ALLOWED_TRANSCRIPTION_STATUSES,
    DEFAULT_DATABASE_PATH,
    database,
    initialize_database,
)
from .source_identity import sha256_file
from .store import ResearchKnowledgeBase


DEFAULT_TRANSCRIPTION_MODEL = "small"
DEFAULT_TRANSCRIPTION_DEVICE = "cpu"
DEFAULT_TRANSCRIPTION_COMPUTE_TYPE = "int8"


class InsufficientAudioError(RuntimeError):
    """Raised when a media file has no usable spoken content."""


class TranscriptionEngineError(RuntimeError):
    """Raised when the optional local speech-to-text engine cannot run."""


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None = None
    segments: tuple[Mapping[str, object], ...] = ()
    quality_note: str = ""


class MediaTranscriber(Protocol):
    engine: str
    engine_version: str
    model: str

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        ...


class FasterWhisperTranscriber:
    """Lazy faster-whisper adapter with resource-conscious CPU defaults."""

    engine = "faster-whisper"

    def __init__(
        self,
        *,
        model: str = DEFAULT_TRANSCRIPTION_MODEL,
        device: str = DEFAULT_TRANSCRIPTION_DEVICE,
        compute_type: str = DEFAULT_TRANSCRIPTION_COMPUTE_TYPE,
    ) -> None:
        self.model = str(model).strip() or DEFAULT_TRANSCRIPTION_MODEL
        self.device = str(device).strip() or DEFAULT_TRANSCRIPTION_DEVICE
        self.compute_type = str(compute_type).strip() or DEFAULT_TRANSCRIPTION_COMPUTE_TYPE
        try:
            self.engine_version = metadata.version("faster-whisper")
        except metadata.PackageNotFoundError:
            self.engine_version = "not-installed"
        self._model: object | None = None

    def _load_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionEngineError(
                "faster-whisper ist nicht installiert. Installiere die optionale lokale "
                "Transkriptionsabhängigkeit aus requirements-transcription.txt."
            ) from exc
        try:
            self._model = WhisperModel(
                self.model,
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as exc:  # pragma: no cover - depends on optional runtime/model files
            raise TranscriptionEngineError(f"faster-whisper konnte nicht geladen werden: {exc}") from exc
        return self._model

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        model = self._load_model()
        try:
            raw_segments, info = model.transcribe(  # type: ignore[attr-defined]
                str(media_path),
                language=language,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            segments: list[dict[str, object]] = []
            text_parts: list[str] = []
            for item in raw_segments:
                text = str(getattr(item, "text", "")).strip()
                if not text:
                    continue
                text_parts.append(text)
                segment: dict[str, object] = {
                    "start": float(getattr(item, "start", 0.0)),
                    "end": float(getattr(item, "end", 0.0)),
                    "text": text,
                }
                average_logprob = getattr(item, "avg_logprob", None)
                no_speech_prob = getattr(item, "no_speech_prob", None)
                if average_logprob is not None:
                    segment["average_log_probability"] = float(average_logprob)
                if no_speech_prob is not None:
                    segment["no_speech_probability"] = float(no_speech_prob)
                segments.append(segment)
        except TranscriptionEngineError:
            raise
        except Exception as exc:  # pragma: no cover - exact decoder errors are environment-specific
            raise TranscriptionEngineError(f"Lokale Transkription fehlgeschlagen: {exc}") from exc
        transcript = " ".join(text_parts).strip()
        if not transcript:
            raise InsufficientAudioError("Kein ausreichend verständlicher Sprachinhalt erkannt.")
        detected_language = str(getattr(info, "language", "") or "").strip() or None
        probability = getattr(info, "language_probability", None)
        language_note = ""
        if probability is not None:
            language_note = f" Erkannte Sprachwahrscheinlichkeit: {float(probability):.3f}."
        return TranscriptionResult(
            text=transcript,
            language=detected_language,
            segments=tuple(segments),
            quality_note=(
                "Automatische Speech-to-Text-Ausgabe; Confidence-Werte sind nur technische "
                "Hinweise. Eigennamen, Ticker, Zahlen, Prozente, Kursniveaus, Daten und "
                f"Fachbegriffe müssen gegen das Original geprüft werden.{language_note}"
            ),
        )


def _timestamp(value: object | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Zeitpunkt muss ein gültiger ISO-Zeitpunkt sein.") from exc
    if parsed.tzinfo is None:
        raise ValueError("Zeitpunkt benötigt eine Zeitzone.")
    return parsed.isoformat()


def _stable_key(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    ).encode("utf-8")
    return "transcription:v1:" + hashlib.sha256(encoded).hexdigest()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ResearchMediaTranscription:
    """Coordinates cache lookup, fallback transcription and private artifacts."""

    def __init__(
        self,
        path: Path = DEFAULT_DATABASE_PATH,
        *,
        artifact_root: Path | None = None,
        transcriber: MediaTranscriber | None = None,
        model: str = DEFAULT_TRANSCRIPTION_MODEL,
        device: str = DEFAULT_TRANSCRIPTION_DEVICE,
        compute_type: str = DEFAULT_TRANSCRIPTION_COMPUTE_TYPE,
    ) -> None:
        self.path = Path(path)
        initialize_database(self.path)
        self.knowledge_base = ResearchKnowledgeBase(self.path)
        self.artifact_root = (
            Path(artifact_root)
            if artifact_root is not None
            else self.path.parent / "research-media" / "transcripts"
        ).resolve()
        self._transcriber = transcriber
        self.model = str(model).strip() or DEFAULT_TRANSCRIPTION_MODEL
        self.device = str(device).strip() or DEFAULT_TRANSCRIPTION_DEVICE
        self.compute_type = str(compute_type).strip() or DEFAULT_TRANSCRIPTION_COMPUTE_TYPE

    def _source_context(
        self,
        source_id: str,
        *,
        media_path: Path | None = None,
    ) -> dict[str, str | None]:
        source = self.knowledge_base.get_source(str(source_id))
        provenance = list(source["provenance"])
        if not provenance:
            raise ValueError("Source besitzt keine nachvollziehbare Provenienz.")
        file_hash: str | None = None
        selected: Mapping[str, object]
        if media_path is not None:
            media = Path(media_path)
            if not media.is_file():
                raise FileNotFoundError(f"Mediendatei nicht gefunden: {media}")
            file_hash = sha256_file(media)
            matching = [item for item in provenance if item.get("file_sha256") == file_hash]
            if not matching:
                raise ValueError(
                    "Die Mediendatei ist nicht über ihren SHA-256 mit dieser Source verknüpft. "
                    "Zuerst Source-Intake/Provenienz ergänzen."
                )
            selected = matching[-1]
        else:
            selected = provenance[-1]
        content_id = str(selected.get("content_id") or "").strip() or None
        if content_id is None:
            for item in reversed(provenance):
                candidate = str(item.get("content_id") or "").strip()
                if candidate:
                    content_id = candidate
                    break
        return {
            "source_id": str(source["id"]),
            "source_fingerprint": str(selected["source_fingerprint"]),
            "content_id": content_id,
            "file_sha256": file_hash or (str(selected.get("file_sha256") or "").strip() or None),
        }

    def _safe_artifact_path(self, raw_path: object) -> Path | None:
        text = str(raw_path or "").strip()
        if not text:
            return None
        candidate = Path(text).resolve()
        try:
            candidate.relative_to(self.artifact_root)
        except ValueError:
            return None
        return candidate

    def list_records(self, source_id: str) -> list[dict[str, Any]]:
        self.knowledge_base.get_source(source_id)
        with database(self.path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM source_transcription_records
                WHERE source_id = ? ORDER BY created_at, id
                """,
                (source_id,),
            ).fetchall()
        records: list[dict[str, Any]] = []
        for raw in rows:
            record = dict(raw)
            try:
                record["segments"] = json.loads(record.pop("segments_json"))
            except (TypeError, json.JSONDecodeError):
                record["segments"] = []
            artifact = self._safe_artifact_path(record.get("transcript_path"))
            available = bool(artifact and artifact.is_file())
            if available and record.get("transcript_sha256"):
                available = sha256_file(artifact) == record["transcript_sha256"]
            record["artifact_available"] = available
            records.append(record)
        return records

    def get_available_transcript(self, source_id: str) -> dict[str, Any] | None:
        for record in reversed(self.list_records(source_id)):
            if record["status"] not in {"EXISTING", "GENERATED"}:
                continue
            if not record["artifact_available"]:
                continue
            reused = dict(record)
            reused["original_status"] = record["status"]
            reused["status"] = "EXISTING"
            reused["reused"] = True
            return reused
        return None

    def _record(
        self,
        context: Mapping[str, str | None],
        *,
        status: str,
        quality_note: str,
        idempotency_key: str,
        transcript_path: Path | None = None,
        transcript_sha256: str | None = None,
        language: str | None = None,
        engine: str | None = None,
        engine_version: str | None = None,
        model: str | None = None,
        segments: Sequence[Mapping[str, object]] = (),
        machine_generated: bool = False,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        if status not in ALLOWED_TRANSCRIPTION_STATUSES:
            raise ValueError(f"Ungültiger Transkriptionsstatus: {status}")
        timestamp = _timestamp(created_at)
        record_id = str(uuid.uuid4())
        with database(self.path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO source_transcription_records (
                    id, source_id, source_fingerprint, content_id, file_sha256,
                    status, transcript_path, transcript_sha256, language, engine,
                    engine_version, model, segments_json, quality_note,
                    machine_generated, idempotency_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    context["source_id"],
                    context["source_fingerprint"],
                    context.get("content_id"),
                    context.get("file_sha256"),
                    status,
                    None if transcript_path is None else str(transcript_path.resolve()),
                    transcript_sha256,
                    str(language or "").strip() or None,
                    str(engine or "").strip() or None,
                    str(engine_version or "").strip() or None,
                    str(model or "").strip() or None,
                    json.dumps(list(segments), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    str(quality_note).strip(),
                    int(machine_generated),
                    idempotency_key,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM source_transcription_records WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if row is None:  # pragma: no cover - protected by the transaction above
            raise RuntimeError("Transkriptionsdatensatz konnte nicht gespeichert werden.")
        result = dict(row)
        if result["source_id"] != context["source_id"] or result["status"] != status:
            raise ValueError("Idempotency-Key gehört zu einem anderen Transkriptionsvorgang.")
        if transcript_sha256 and result.get("transcript_sha256") != transcript_sha256:
            raise ValueError("Idempotency-Key kollidiert mit einem anderen Transcript-Artefakt.")
        result["segments"] = json.loads(result.pop("segments_json"))
        result["artifact_available"] = bool(
            result.get("transcript_path") and Path(result["transcript_path"]).is_file()
        )
        result["reused"] = result["id"] != record_id
        return result

    def _persist_transcript(self, source_id: str, text: str) -> tuple[Path, str]:
        normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise InsufficientAudioError("Transcript enthält keinen verwertbaren Text.")
        normalized += "\n"
        transcript_hash = _text_sha256(normalized)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        target = (self.artifact_root / f"{source_id}-{transcript_hash[:16]}.txt").resolve()
        target.relative_to(self.artifact_root)
        if target.is_file() and sha256_file(target) == transcript_hash:
            return target, transcript_hash
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.artifact_root,
                prefix=".transcript-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(normalized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, target)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return target, transcript_hash

    @staticmethod
    def _normalize_result(value: object) -> TranscriptionResult:
        if isinstance(value, TranscriptionResult):
            return value
        if not isinstance(value, Mapping):
            raise TranscriptionEngineError("Transkriptionsengine lieferte kein gültiges Ergebnis.")
        raw_segments = value.get("segments") or ()
        if not isinstance(raw_segments, Sequence) or isinstance(raw_segments, (str, bytes)):
            raise TranscriptionEngineError("Transkriptionssegmente haben ein ungültiges Format.")
        segments = tuple(item for item in raw_segments if isinstance(item, Mapping))
        return TranscriptionResult(
            text=str(value.get("text") or ""),
            language=str(value.get("language") or "").strip() or None,
            segments=segments,
            quality_note=str(value.get("quality_note") or ""),
        )

    def process(
        self,
        source_id: str,
        *,
        direct_content_sufficient: bool,
        decision_reason: str,
        media_path: Path | None = None,
        existing_transcript_path: Path | None = None,
        existing_transcript_text: str | None = None,
        language: str | None = None,
        idempotency_key: str | None = None,
        created_at: object | None = None,
    ) -> dict[str, Any]:
        """Apply the conservative cache → direct-content → transcript → STT order."""

        reason = str(decision_reason).strip()
        if not reason:
            raise ValueError("Die Transkriptionsentscheidung benötigt eine Begründung.")
        if existing_transcript_path is not None and existing_transcript_text is not None:
            raise ValueError("Vorhandenes Transcript entweder als Pfad oder als Text angeben.")

        cached = self.get_available_transcript(source_id)
        if cached is not None:
            return cached

        context = self._source_context(source_id)
        if direct_content_sufficient:
            key = idempotency_key or _stable_key(
                {
                    "action": "not_required",
                    "source_id": source_id,
                    "source_fingerprint": context["source_fingerprint"],
                }
            )
            return self._record(
                context,
                status="NOT_REQUIRED",
                quality_note=reason,
                idempotency_key=key,
                created_at=created_at,
            )

        provided_text: str | None = existing_transcript_text
        if existing_transcript_path is not None:
            try:
                provided_text = Path(existing_transcript_path).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                key = idempotency_key or _stable_key(
                    {
                        "action": "existing_transcript_failed",
                        "source_id": source_id,
                        "path": str(existing_transcript_path),
                    }
                )
                return self._record(
                    context,
                    status="FAILED",
                    quality_note=f"Vorhandenes Transcript konnte nicht gelesen werden: {exc}",
                    idempotency_key=key,
                    created_at=created_at,
                )
        if provided_text is not None:
            try:
                transcript_path, transcript_hash = self._persist_transcript(source_id, provided_text)
            except InsufficientAudioError as exc:
                key = idempotency_key or _stable_key(
                    {"action": "existing_transcript_empty", "source_id": source_id}
                )
                return self._record(
                    context,
                    status="FAILED",
                    quality_note=str(exc),
                    idempotency_key=key,
                    created_at=created_at,
                )
            key = idempotency_key or _stable_key(
                {
                    "action": "existing_transcript",
                    "source_id": source_id,
                    "source_fingerprint": context["source_fingerprint"],
                    "transcript_sha256": transcript_hash,
                }
            )
            return self._record(
                context,
                status="EXISTING",
                transcript_path=transcript_path,
                transcript_sha256=transcript_hash,
                language=language,
                quality_note=(
                    f"{reason} Vom Nutzer bereitgestelltes Transcript; relevante Namen, "
                    "Ticker, Zahlen und Fachbegriffe gegen das Original prüfen."
                ),
                idempotency_key=key,
                created_at=created_at,
            )

        if media_path is None:
            key = idempotency_key or _stable_key(
                {"action": "missing_media", "source_id": source_id, "source_fingerprint": context["source_fingerprint"]}
            )
            return self._record(
                context,
                status="FAILED",
                quality_note="Transkription war erforderlich, aber keine lokale Mediendatei wurde angegeben.",
                idempotency_key=key,
                created_at=created_at,
            )

        context = self._source_context(source_id, media_path=Path(media_path))
        transcriber = self._transcriber or FasterWhisperTranscriber(
            model=self.model,
            device=self.device,
            compute_type=self.compute_type,
        )
        engine = str(getattr(transcriber, "engine", type(transcriber).__name__))
        engine_version = str(getattr(transcriber, "engine_version", "unknown"))
        model = str(getattr(transcriber, "model", self.model))
        key = idempotency_key or _stable_key(
            {
                "action": "speech_to_text",
                "source_id": source_id,
                "source_fingerprint": context["source_fingerprint"],
                "content_id": context.get("content_id"),
                "file_sha256": context.get("file_sha256"),
                "engine": engine,
                "engine_version": engine_version,
                "model": model,
                "language": language,
            }
        )
        with database(self.path) as connection:
            existing = connection.execute(
                "SELECT id FROM source_transcription_records WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
        if existing is not None:
            reused = next(item for item in self.list_records(source_id) if item["id"] == existing["id"])
            reused["reused"] = True
            return reused
        try:
            raw_result = transcriber.transcribe(Path(media_path), language=language)
            result = self._normalize_result(raw_result)
            transcript_path, transcript_hash = self._persist_transcript(source_id, result.text)
        except InsufficientAudioError as exc:
            return self._record(
                context,
                status="INSUFFICIENT_AUDIO",
                quality_note=str(exc),
                engine=engine,
                engine_version=engine_version,
                model=model,
                idempotency_key=key,
                created_at=created_at,
            )
        except Exception as exc:
            return self._record(
                context,
                status="FAILED",
                quality_note=f"Lokale Transkription fehlgeschlagen: {exc}",
                engine=engine,
                engine_version=engine_version,
                model=model,
                idempotency_key=key,
                created_at=created_at,
            )
        return self._record(
            context,
            status="GENERATED",
            transcript_path=transcript_path,
            transcript_sha256=transcript_hash,
            language=result.language or language,
            engine=engine,
            engine_version=engine_version,
            model=model,
            segments=result.segments,
            quality_note=result.quality_note or reason,
            machine_generated=True,
            idempotency_key=key,
            created_at=created_at,
        )


__all__ = [
    "DEFAULT_TRANSCRIPTION_COMPUTE_TYPE",
    "DEFAULT_TRANSCRIPTION_DEVICE",
    "DEFAULT_TRANSCRIPTION_MODEL",
    "FasterWhisperTranscriber",
    "InsufficientAudioError",
    "MediaTranscriber",
    "ResearchMediaTranscription",
    "TranscriptionEngineError",
    "TranscriptionResult",
]
