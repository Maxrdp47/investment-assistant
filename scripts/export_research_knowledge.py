from __future__ import annotations

"""Read-only domain export for a future general Knowledge Base."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_knowledge import ALLOWED_KNOWLEDGE_DOMAINS, DEFAULT_DATABASE_PATH
from research_knowledge.knowledge_export import KnowledgeExporter


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wissensclaims einer Domain read-only als JSON oder Markdown exportieren."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--domain", required=True, choices=ALLOWED_KNOWLEDGE_DOMAINS)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--verified-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def run_command(args: argparse.Namespace) -> str:
    exporter = KnowledgeExporter(Path(args.database))
    if args.format == "markdown":
        return exporter.export_markdown(args.domain, verified_only=bool(args.verified_only))
    return exporter.export_json(args.domain, verified_only=bool(args.verified_only))


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    payload = run_command(args)
    if args.output is None:
        print(payload, end="")
        return
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8", newline="\n")
    print(str(output.resolve()))


if __name__ == "__main__":
    main()
