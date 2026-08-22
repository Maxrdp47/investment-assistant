from __future__ import annotations

"""Print read-only real-forward stopout diagnostics as JSON."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_edge_diagnostics import (  # noqa: E402
    analyze_real_forward_trades,
    build_frozen_forward_context,
    render_forward_status_markdown,
)
from swing_research_dataset import (  # noqa: E402
    load_frozen_histories,
    load_research_dataset_manifest,
)


DEFAULT_SWING_FORWARD_DB_PATH = PROJECT_ROOT / "runtime" / "swing_forward.sqlite3"
DEFAULT_FIXED_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)


def _load_forward_signals_read_only(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        signals = connection.execute(
            "SELECT signal_id, snapshot_json FROM swing_signals ORDER BY signal_at, signal_id"
        ).fetchall()
        events = connection.execute(
            """SELECT signal_id, event_id, event_type, occurred_at, source_key, payload_json
            FROM swing_events ORDER BY occurred_at, event_id"""
        ).fetchall()
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
    finally:
        connection.close()
    if quick_check != "ok":
        raise RuntimeError(f"Swing-Forward-Datenbankintegrität ist nicht ok: {quick_check}")
    by_signal: dict[str, list[dict]] = {}
    for row in events:
        envelope = json.loads(row["payload_json"])
        by_signal.setdefault(str(row["signal_id"]), []).append(
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "source_key": str(row["source_key"]),
                "payload": dict(envelope.get("payload") or {}),
            }
        )
    return [
        {
            "signal_id": str(row["signal_id"]),
            "snapshot": json.loads(row["snapshot_json"]),
            "events": by_signal.get(str(row["signal_id"]), []),
        }
        for row in signals
    ]


def _frozen_histories(manifest_path: Path, symbols: list[str]) -> tuple[dict[str, pd.DataFrame], str]:
    manifest = load_research_dataset_manifest(manifest_path)
    dataset_root = manifest_path.parent.parent
    frames: dict[str, list[pd.DataFrame]] = {symbol: [] for symbol in symbols}
    for raw_scope in (manifest.get("scopes") or {}).values():
        contract = dict(raw_scope.get("contract") or {})
        histories, _ = load_frozen_histories(
            dataset_root,
            manifest,
            tickers=symbols,
            start=contract.get("start"),
            end=contract.get("end"),
        )
        for symbol, history in histories.items():
            frames.setdefault(symbol, []).append(history)
    combined: dict[str, pd.DataFrame] = {}
    for symbol, parts in frames.items():
        if not parts:
            continue
        frame = pd.concat(parts).sort_index()
        combined[symbol] = frame.loc[~frame.index.duplicated(keep="last")]
    return combined, str(manifest["dataset_fingerprint"])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Rein lesende Forensik abgeschlossener echter Swing-Forward-Stopouts."
    )
    parser.add_argument("--forward-database", type=Path, default=DEFAULT_SWING_FORWARD_DB_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FIXED_MANIFEST)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Kompakten PROJECT_STATUS-Abschnitt statt JSON ausgeben.",
    )
    args = parser.parse_args()

    signals = _load_forward_signals_read_only(args.forward_database)
    symbols = sorted(
        {
            str((signal.get("snapshot") or {}).get("asset", {}).get("ticker") or "").upper()
            for signal in signals
            if (signal.get("snapshot") or {}).get("asset", {}).get("ticker")
        }
    )
    histories, dataset_fingerprint = _frozen_histories(args.manifest, symbols)
    contexts: dict[str, dict] = {}
    for signal in signals:
        snapshot = dict(signal.get("snapshot") or {})
        asset = dict(snapshot.get("asset") or {})
        symbol = str(asset.get("ticker") or "").upper()
        context = build_frozen_forward_context(
            signal,
            histories.get(symbol, pd.DataFrame()),
            dataset_fingerprint=dataset_fingerprint,
        )
        contexts[str(signal.get("signal_id") or "")] = context
    report = analyze_real_forward_trades(signals, contexts=contexts)
    if args.markdown:
        print(render_forward_status_markdown(report))
        return 0
    if args.summary_only:
        report = {key: value for key, value in report.items() if key not in {"cases", "segments"}}
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
