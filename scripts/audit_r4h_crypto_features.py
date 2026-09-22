from __future__ import annotations

"""Read-only, outcome-free BTC/ETH capability probe for R4-H."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto_r4h_features import build_crypto_r4h_features, load_contract  # noqa: E402


DEFAULT_SOURCE = ROOT / "runtime" / "crypto_historical_pit_2026-09-05-v1.sqlite3"


def _bars(connection: sqlite3.Connection, ticker: str) -> pd.DataFrame:
    rows = connection.execute(
        "SELECT session_date,open,high,low,close,volume,segment_id "
        "FROM active_bars WHERE ticker=? ORDER BY session_date",
        (ticker,),
    ).fetchall()
    if not rows:
        raise ValueError(f"No frozen active bars for {ticker}")
    frame = pd.DataFrame(
        rows,
        columns=["Date", "Open", "High", "Low", "Close", "Volume", "SegmentId"],
    )
    frame["Date"] = pd.to_datetime(frame["Date"], errors="raise")
    return frame.set_index("Date")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    contract, fingerprint = load_contract()
    if not args.source.is_file():
        raise ValueError("Frozen crypto source is absent")
    uri = f"file:{args.source.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Frozen crypto source failed quick_check")
        stored = connection.execute(
            "SELECT dataset_fingerprint FROM projection_versions WHERE version=?",
            (contract["source_projection_version"],),
        ).fetchone()
        if stored is None or stored[0] != contract["source_dataset_fingerprint"]:
            raise ValueError("Frozen crypto source fingerprint mismatch")
        btc = _bars(connection, "BTC-USD")
        eth = _bars(connection, "ETH-USD")
    output = {
        "program_block": "R4-H",
        "contract_fingerprint": fingerprint,
        "source_dataset_fingerprint": stored[0],
        "source_read_only": True,
        "outcomes_opened": False,
        "pilot_tickers": {},
    }
    for ticker, bars in (("BTC-USD", btc), ("ETH-USD", eth)):
        features = build_crypto_r4h_features(bars, btc)
        output["pilot_tickers"][ticker] = {
            "source_bars": len(bars),
            "btc_lagged_return_20_available": int(features["btc_lagged_return_20"].notna().sum()),
            "relative_to_btc_20_available": int(features["relative_to_btc_20"].notna().sum()),
            "relative_to_btc_60_available": int(features["relative_to_btc_60"].notna().sum()),
            "asset_volatility_20_available": int(features["asset_volatility_20"].notna().sum()),
            "reported_volume_ratio_20_available": int(features["reported_volume_ratio_20"].notna().sum()),
            "zero_reported_volume_bars": int(bars["Volume"].eq(0).sum()),
            "segments": int(bars["SegmentId"].nunique()),
        }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
