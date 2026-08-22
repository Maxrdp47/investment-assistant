from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_event_research import (  # noqa: E402
    DEFAULT_EVENT_RESEARCH_DB_PATH,
    build_forward_event_diagnostics,
    collect_forward_event_contexts,
    event_research_store_audit,
    load_signal_event_contexts,
)


DEFAULT_FORWARD_DB_PATH = PROJECT_ROOT / "runtime" / "swing_forward.sqlite3"


def _read_forward_database(path: Path) -> list[dict]:
    if not path.exists():
        return []
    uri = path.resolve().as_uri().replace("file:///", "file:") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        signals = connection.execute(
            "SELECT signal_id, signal_at, snapshot_json FROM swing_signals ORDER BY signal_at, signal_id"
        ).fetchall()
        events = connection.execute(
            """SELECT signal_id, event_type, occurred_at, payload_json
            FROM swing_events ORDER BY occurred_at, event_id"""
        ).fetchall()
    finally:
        connection.close()
    by_signal: dict[str, list[dict]] = {}
    for row in events:
        envelope = json.loads(row["payload_json"])
        by_signal.setdefault(str(row["signal_id"]), []).append(
            {
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "payload": dict(envelope.get("payload") or {}),
            }
        )
    return [
        {
            "signal_id": str(row["signal_id"]),
            "signal_at": str(row["signal_at"]),
            "snapshot": json.loads(row["snapshot_json"]),
            "events": by_signal.get(str(row["signal_id"]), []),
        }
        for row in signals
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Point-in-Time-sicheren Swing-Event-Research-Sidecar prüfen oder fortsetzen."
    )
    parser.add_argument("--event-database", type=Path, default=DEFAULT_EVENT_RESEARCH_DB_PATH)
    parser.add_argument("--forward-database", type=Path, default=DEFAULT_FORWARD_DB_PATH)
    parser.add_argument(
        "--link-existing-forward",
        action="store_true",
        help="Nur bereits im unveränderbaren Signalsnapshot vorhandene Termine in den Sidecar übernehmen.",
    )
    parser.add_argument(
        "--collect-current-news",
        action="store_true",
        help="Zusätzlich aktuelle Yahoo-News mit tatsächlichem Abrufzeitpunkt sammeln; nie rückdatieren.",
    )
    args = parser.parse_args()

    forward_signals = _read_forward_database(args.forward_database)
    collection = None
    if args.link_existing_forward or args.collect_current_news:
        collection = collect_forward_event_contexts(
            signal_ids=[str(signal["signal_id"]) for signal in forward_signals],
            forward_path=args.forward_database,
            collected_at=datetime.now().astimezone(),
            path=args.event_database,
            collect_news=bool(args.collect_current_news),
        )
    contexts = load_signal_event_contexts(args.event_database)
    output = {
        "audit": event_research_store_audit(args.event_database),
        "forward_event_diagnostics": build_forward_event_diagnostics(forward_signals, contexts),
        "collection": collection,
        "forward_database_opened_read_only": True,
        "event_features_research_shadow_only": True,
        "production_effect": "none",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
