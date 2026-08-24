from __future__ import annotations

"""Small CLI for DB-Chat ↔ Work-Chat handoff through the shared SQLite KB."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import DEFAULT_DATABASE_PATH, ResearchWorkflow


def _json_file(path: Path | None, *, default: object) -> object:
    if path is None:
        return default
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offene Research Work Requests direkt aus der gemeinsamen Knowledge Base lesen und abschließen."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="Work Requests auflisten")
    list_parser.add_argument("--status", default="READY")
    list_parser.add_argument("--limit", type=int, default=100)

    show_parser = commands.add_parser("show", help="Work Request mit vollem Kontext laden")
    show_parser.add_argument("work_request_id")

    claim_parser = commands.add_parser("claim", help="READY Request atomar übernehmen")
    claim_parser.add_argument("work_request_id")
    claim_parser.add_argument("--worker", required=True)
    claim_parser.add_argument("--claim-token")

    block_parser = commands.add_parser("block", help="Übernommenen Request blockieren")
    block_parser.add_argument("work_request_id")
    block_parser.add_argument("--worker", required=True)
    block_parser.add_argument("--claim-token", required=True)
    block_parser.add_argument("--reason", required=True)

    retry_parser = commands.add_parser("retry", help="BLOCKED Request bewusst wieder READY setzen")
    retry_parser.add_argument("work_request_id")
    retry_parser.add_argument("--actor", required=True)
    retry_parser.add_argument("--reason", required=True)

    complete_parser = commands.add_parser(
        "complete", help="Resultat direkt speichern und Request abschließen"
    )
    complete_parser.add_argument("work_request_id")
    complete_parser.add_argument("--worker", required=True)
    complete_parser.add_argument("--claim-token", required=True)
    complete_parser.add_argument("--result-json", type=Path, required=True)
    complete_parser.add_argument("--artifacts-json", type=Path)
    complete_parser.add_argument("--result-reference")
    return parser


def run_command(args: argparse.Namespace) -> object:
    workflow = ResearchWorkflow(Path(args.database))
    if args.command == "list":
        return workflow.list_work_requests(status=args.status, limit=args.limit)
    if args.command == "show":
        return workflow.get_work_request(args.work_request_id)
    if args.command == "claim":
        return workflow.claim_work_request(
            args.work_request_id,
            worker_context=args.worker,
            claim_token=args.claim_token,
        )
    if args.command == "block":
        return workflow.block_work_request(
            args.work_request_id,
            claim_token=args.claim_token,
            blocker_reason=args.reason,
            worker_context=args.worker,
        )
    if args.command == "retry":
        return workflow.retry_blocked_work_request(
            args.work_request_id,
            reason=args.reason,
            actor=args.actor,
        )
    if args.command == "complete":
        result = _json_file(args.result_json, default={})
        artifacts = _json_file(args.artifacts_json, default=[])
        if not isinstance(result, dict):
            raise ValueError("--result-json muss ein JSON-Objekt enthalten.")
        if not isinstance(artifacts, list) or not all(isinstance(item, dict) for item in artifacts):
            raise ValueError("--artifacts-json muss eine Liste von JSON-Objekten enthalten.")
        return workflow.complete_work_request(
            args.work_request_id,
            claim_token=args.claim_token,
            worker_context=args.worker,
            result=result,
            result_reference=args.result_reference,
            artifact_references=artifacts,
        )
    raise ValueError(f"Unbekanntes Kommando: {args.command}")


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    payload: Any = run_command(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
