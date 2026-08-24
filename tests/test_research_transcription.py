from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research_knowledge import ResearchKnowledgeBase
from research_knowledge.transcription import (
    InsufficientAudioError,
    ResearchMediaTranscription,
    TranscriptionResult,
)
from scripts.transcribe_research_media import _parser as transcription_parser, run_command


class CountingTranscriber:
    engine = "fake-local-stt"
    engine_version = "1.0"
    model = "small-test"

    def __init__(self, text: str = "Der Ticker ABC steigt möglicherweise um zwei Prozent.") -> None:
        self.calls = 0
        self.text = text

    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        self.calls += 1
        return TranscriptionResult(
            text=self.text,
            language=language or "de",
            segments=(
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": self.text,
                    "average_log_probability": -0.2,
                },
            ),
            quality_note="Maschinell erzeugt; Zahlen und Ticker gegen das Video prüfen.",
        )


class NoAudioTranscriber(CountingTranscriber):
    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        self.calls += 1
        raise InsufficientAudioError("Keine verständliche Sprache erkannt.")


class FailingTranscriber(CountingTranscriber):
    def transcribe(self, media_path: Path, *, language: str | None = None) -> TranscriptionResult:
        self.calls += 1
        raise RuntimeError("Decoder defekt")


def _video_source(
    kb: ResearchKnowledgeBase,
    tmp_path: Path,
    *,
    video_id: str = "AbCdEf12345",
    creator: str = "Research Creator",
    content: bytes = b"video-one",
) -> tuple[dict, Path]:
    media = tmp_path / f"{video_id}.mp4"
    media.write_bytes(content)
    intake = kb.intake_source(
        title=f"Research Clip {video_id}",
        source_type="youtube",
        summary="Neutraler Video-Input ohne abgeleitete Claims.",
        platform="youtube",
        creator=creator,
        direct_url=f"https://youtu.be/{video_id}?si=tracking",
        local_file=media,
        provenance="DB-Chat Video-Intake",
    )
    return intake, media


def test_existing_transcript_and_directly_sufficient_video_skip_stt(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, _ = _video_source(kb, tmp_path)
    transcriber = CountingTranscriber()
    service = ResearchMediaTranscription(database, transcriber=transcriber)

    existing = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Vollständiges Transcript wurde mitgeliefert.",
        existing_transcript_text="Vollständiger, vom Nutzer gelieferter Transcript-Text.",
        language="de",
    )
    duplicate_use = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Gesprochener Inhalt ist direkt nicht sicher verständlich.",
    )

    second_intake, _ = _video_source(
        kb,
        tmp_path,
        video_id="ZyXwVu98765",
        content=b"video-two",
    )
    not_required = service.process(
        second_intake["source_id"],
        direct_content_sufficient=True,
        decision_reason="Eingeblendete Untertitel sind vollständig und gut lesbar.",
    )

    assert existing["status"] == "EXISTING"
    assert existing["machine_generated"] == 0
    assert Path(existing["transcript_path"]).is_file()
    assert duplicate_use["status"] == "EXISTING"
    assert duplicate_use["reused"] is True
    assert not_required["status"] == "NOT_REQUIRED"
    assert transcriber.calls == 0


def test_unintelligible_video_uses_local_fallback_and_keeps_transcript_on_source(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, media = _video_source(kb, tmp_path)
    transcriber = CountingTranscriber()
    service = ResearchMediaTranscription(database, transcriber=transcriber)

    generated = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Keine vollständigen Untertitel; relevante Aussagen sind akustisch unklar.",
        media_path=media,
    )
    source = kb.get_source(intake["source_id"])

    assert generated["status"] == "GENERATED"
    assert generated["machine_generated"] == 1
    assert generated["engine"] == "fake-local-stt"
    assert generated["model"] == "small-test"
    assert generated["language"] == "de"
    assert generated["segments"][0]["start"] == 0.0
    assert generated["file_sha256"] == source["provenance"][0]["file_sha256"]
    assert Path(generated["transcript_path"]).read_text(encoding="utf-8").startswith("Der Ticker ABC")
    assert source["transcriptions"][0]["source_id"] == intake["source_id"]
    assert source["transcriptions"][0]["artifact_available"] is True
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM source_transcription_records").fetchone()[0] == 1
    assert transcriber.calls == 1


def test_duplicate_url_and_identical_file_reuse_transcript_without_second_run(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, media = _video_source(kb, tmp_path)
    transcriber = CountingTranscriber()
    service = ResearchMediaTranscription(database, transcriber=transcriber)
    first = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Audio wird für die fachliche Bewertung benötigt.",
        media_path=media,
    )

    url_duplicate = kb.intake_source(
        title="Share-URL desselben Clips",
        source_type="youtube",
        summary="Derselbe Clip.",
        platform="youtube",
        creator="Research Creator",
        direct_url="https://www.youtube.com/watch?v=AbCdEf12345&utm_source=chat",
        provenance="Erneute URL-Einreichung",
    )
    file_duplicate = kb.intake_source(
        title="Lokale Kopie desselben Clips",
        source_type="youtube",
        summary="Derselbe Clip als Datei.",
        platform="youtube",
        local_file=media,
        provenance="Erneuter Datei-Upload",
    )
    reused_url = service.process(
        url_duplicate["source_id"],
        direct_content_sufficient=False,
        decision_reason="Audio weiterhin nicht direkt auswertbar.",
    )
    reused_file = service.process(
        file_duplicate["source_id"],
        direct_content_sufficient=False,
        decision_reason="Audio weiterhin nicht direkt auswertbar.",
        media_path=media,
    )

    assert url_duplicate["status"] == "DUPLICATE_SOURCE"
    assert file_duplicate["status"] == "DUPLICATE_SOURCE"
    assert {url_duplicate["source_id"], file_duplicate["source_id"]} == {intake["source_id"]}
    assert reused_url["status"] == reused_file["status"] == "EXISTING"
    assert reused_url["id"] == reused_file["id"] == first["id"]
    assert transcriber.calls == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_transcription_records").fetchone()[0] == 1


def test_url_source_enriched_with_original_file_reuses_same_artifact(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    url_only = kb.intake_source(
        title="Original URL",
        source_type="tiktok",
        summary="TikTok-Research-Input.",
        platform="tiktok",
        creator="Creator A",
        direct_url="https://www.tiktok.com/@creator/video/7123456789012345678",
        provenance="URL zuerst",
    )
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"same-tiktok-video")
    enriched = kb.intake_source(
        title="Originaldatei",
        source_type="tiktok",
        summary="Dieselbe Source als lokale Datei.",
        platform="tiktok",
        direct_url="https://tiktok.com/video/7123456789012345678",
        local_file=media,
        provenance="Originaldatei später ergänzt",
    )
    transcriber = CountingTranscriber()
    service = ResearchMediaTranscription(database, transcriber=transcriber)
    generated = service.process(
        enriched["source_id"],
        direct_content_sufficient=False,
        decision_reason="Fallback erforderlich.",
        media_path=media,
    )
    reused = service.process(
        url_only["source_id"],
        direct_content_sufficient=False,
        decision_reason="Spätere URL-Einreichung.",
    )

    assert enriched["status"] == "DUPLICATE_SOURCE"
    assert enriched["provenance_added"] is True
    assert enriched["source_id"] == url_only["source_id"]
    assert reused["id"] == generated["id"]
    assert reused["status"] == "EXISTING"
    assert transcriber.calls == 1


def test_new_video_from_same_creator_never_reuses_old_transcript(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    first, first_media = _video_source(kb, tmp_path, video_id="AbCdEf12345", content=b"first")
    second, second_media = _video_source(kb, tmp_path, video_id="ZyXwVu98765", content=b"second")
    transcriber = CountingTranscriber()
    service = ResearchMediaTranscription(database, transcriber=transcriber)

    first_result = service.process(
        first["source_id"],
        direct_content_sufficient=False,
        decision_reason="Fallback eins.",
        media_path=first_media,
    )
    second_result = service.process(
        second["source_id"],
        direct_content_sufficient=False,
        decision_reason="Fallback zwei.",
        media_path=second_media,
    )

    assert first["source_id"] != second["source_id"]
    assert first_result["id"] != second_result["id"]
    assert transcriber.calls == 2


@pytest.mark.parametrize(
    ("transcriber", "expected_status"),
    [(NoAudioTranscriber(), "INSUFFICIENT_AUDIO"), (FailingTranscriber(), "FAILED")],
)
def test_audio_and_engine_failures_are_explicit_and_retries_idempotent(
    tmp_path: Path,
    transcriber: CountingTranscriber,
    expected_status: str,
) -> None:
    database = tmp_path / f"{expected_status}.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, media = _video_source(kb, tmp_path, content=expected_status.encode("ascii"))
    service = ResearchMediaTranscription(database, transcriber=transcriber)

    first = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Fallback erforderlich.",
        media_path=media,
    )
    retry = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Identischer Retry.",
        media_path=media,
    )

    assert first["status"] == expected_status
    assert retry["id"] == first["id"]
    assert retry["reused"] is True
    assert transcriber.calls == 1
    assert service.get_available_transcript(intake["source_id"]) is None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM source_transcription_records").fetchone()[0] == 1


def test_deleted_transcript_is_not_reported_as_available(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, _ = _video_source(kb, tmp_path)
    service = ResearchMediaTranscription(database)
    record = service.process(
        intake["source_id"],
        direct_content_sufficient=False,
        decision_reason="Transcript geliefert.",
        existing_transcript_text="Privater Transcript-Text.",
    )
    Path(record["transcript_path"]).unlink()

    assert service.get_available_transcript(intake["source_id"]) is None
    assert kb.get_source(intake["source_id"])["transcriptions"][0]["artifact_available"] is False


def test_wrong_media_file_cannot_be_attached_to_source(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, _ = _video_source(kb, tmp_path)
    wrong = tmp_path / "wrong.mp4"
    wrong.write_bytes(b"different-video")
    service = ResearchMediaTranscription(database, transcriber=CountingTranscriber())

    with pytest.raises(ValueError, match="nicht über ihren SHA-256"):
        service.process(
            intake["source_id"],
            direct_content_sufficient=False,
            decision_reason="Fallback erforderlich.",
            media_path=wrong,
        )
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_transcription_records").fetchone()[0] == 0


def test_cli_uses_small_cpu_int8_defaults_and_runtime_is_gitignored(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, _ = _video_source(kb, tmp_path)
    args = transcription_parser().parse_args(
        [
            intake["source_id"],
            "--database",
            str(database),
            "--direct-content-sufficient",
            "--reason",
            "Lesbare vollständige Untertitel.",
        ]
    )

    assert args.model == "small"
    assert args.device == "cpu"
    assert args.compute_type == "int8"
    assert run_command(args)["status"] == "NOT_REQUIRED"
    gitignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "runtime/" in {line.strip() for line in gitignore.splitlines()}


def test_transcription_rows_are_append_only_and_require_source_fingerprint(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    kb = ResearchKnowledgeBase(database)
    intake, _ = _video_source(kb, tmp_path)
    service = ResearchMediaTranscription(database)
    record = service.process(
        intake["source_id"],
        direct_content_sufficient=True,
        decision_reason="Direkt vollständig verständlich.",
    )

    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE source_transcription_records SET quality_note = 'überschrieben' WHERE id = ?",
                (record["id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="fingerprint must belong"):
            connection.execute(
                """
                INSERT INTO source_transcription_records (
                    id, source_id, source_fingerprint, status, segments_json,
                    quality_note, machine_generated, idempotency_key, created_at
                ) VALUES ('bad', ?, 'wrong', 'NOT_REQUIRED', '[]', 'bad', 0, 'bad', ?)
                """,
                (intake["source_id"], "2026-08-24T10:00:00+00:00"),
            )
