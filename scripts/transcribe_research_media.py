from __future__ import annotations

"""Conditional local transcription fallback for an already identified source."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import DEFAULT_DATABASE_PATH, ResearchMediaTranscription
from research_knowledge.transcription import (
    DEFAULT_TRANSCRIPTION_COMPUTE_TYPE,
    DEFAULT_TRANSCRIPTION_DEVICE,
    DEFAULT_TRANSCRIPTION_MODEL,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Vorhandenes Transcript wiederverwenden oder nur bei fachlich unzureichend "
            "verständlichem Video lokal transkribieren. Keine Claim-/LLM-Auswertung."
        )
    )
    parser.add_argument("source_id", help="Bereits durch Source-Intake aufgelöste Source-ID")
    parser.add_argument("media_path", type=Path, nargs="?", help="Bereits zur Source gehörende Video-/Audiodatei")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--artifact-root", type=Path)
    decision = parser.add_mutually_exclusive_group(required=True)
    decision.add_argument(
        "--direct-content-sufficient",
        action="store_true",
        help="Video/Untertitel sind direkt ausreichend; keinen Whisper-Lauf starten",
    )
    decision.add_argument(
        "--transcription-required",
        action="store_true",
        help="Wesentlicher gesprochener Inhalt ist sonst nicht zuverlässig verständlich",
    )
    parser.add_argument("--reason", required=True, help="Begründung der fachlichen Entscheidung")
    parser.add_argument("--existing-transcript", type=Path, help="Bereits geliefertes Transcript")
    parser.add_argument("--language", help="Optionaler ISO-Sprachcode; Standard ist Auto-Erkennung")
    parser.add_argument("--model", default=DEFAULT_TRANSCRIPTION_MODEL)
    parser.add_argument("--device", default=DEFAULT_TRANSCRIPTION_DEVICE)
    parser.add_argument("--compute-type", default=DEFAULT_TRANSCRIPTION_COMPUTE_TYPE)
    parser.add_argument("--idempotency-key")
    return parser


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    service = ResearchMediaTranscription(
        Path(args.database),
        artifact_root=args.artifact_root,
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
    )
    return service.process(
        args.source_id,
        direct_content_sufficient=bool(args.direct_content_sufficient),
        decision_reason=args.reason,
        media_path=args.media_path,
        existing_transcript_path=args.existing_transcript,
        language=args.language,
        idempotency_key=args.idempotency_key,
    )


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    payload = run_command(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    if payload.get("status") in {"FAILED", "INSUFFICIENT_AUDIO"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
