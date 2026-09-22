from __future__ import annotations

"""Outcome-free, read-only coverage and deterministic pilot for R4-B."""

import argparse
from bisect import bisect_left
from datetime import date
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multi_asset_v2_r4b_features import DEFAULT_CONTRACT, build_r4b_features, load_contract  # noqa: E402


DEFAULT_SOURCE = ROOT / "runtime" / "equity_etf_historical_pit_2026-09-03-v1.sqlite3"


def audit(source_path: Path = DEFAULT_SOURCE, contract_path: Path = DEFAULT_CONTRACT) -> dict:
    contract, contract_fingerprint = load_contract(contract_path)
    with sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True) as source:
        row = source.execute(
            "SELECT dataset_fingerprint FROM projection_versions WHERE version=?",
            (contract["source_projection_version"],),
        ).fetchone()
        if row is None or row[0] != contract["source_dataset_fingerprint"]:
            raise RuntimeError("R4-B frozen source fingerprint mismatch")
        benchmark_rows = source.execute(
            "SELECT session_date,close FROM active_bars "
            "WHERE ticker=? AND asset_class='ETF' ORDER BY session_date",
            (contract["market_benchmark"],),
        ).fetchall()
        if len({row[0] for row in benchmark_rows}) != len(benchmark_rows):
            raise RuntimeError("R4-B benchmark date is ambiguous")
        if len(benchmark_rows) < 121:
            raise RuntimeError("R4-B benchmark history is too short")
        benchmark = pd.DataFrame(
            {"Close": [row[1] for row in benchmark_rows]},
            index=pd.to_datetime([row[0] for row in benchmark_rows]),
        )
        day_counts = dict(source.execute("SELECT session_date,COUNT(*) FROM active_bars GROUP BY session_date"))
        benchmark_days = [row[0] for row in benchmark_rows]
        total_bars = sum(day_counts.values())
        eligible = 0
        warm120 = 0
        for day, count in day_counts.items():
            prior = bisect_left(benchmark_days, day) - 1
            if prior < 0 or (date.fromisoformat(day) - date.fromisoformat(benchmark_days[prior])).days > 5:
                continue
            eligible += count
            if prior >= 120:
                warm120 += count
        units = source.execute(
            "SELECT asset_id,listing_id,asset_class,COUNT(*) FROM active_bars "
            "GROUP BY asset_id,listing_id,asset_class HAVING COUNT(*) >= 140 "
            "ORDER BY asset_class,asset_id,listing_id"
        ).fetchall()
        selected = {}
        for asset_id, listing_id, asset_class, count in units:
            if asset_class not in selected:
                selected[asset_class] = (asset_id, listing_id, count)
        if set(selected) != {"EQUITIES", "ETF"}:
            raise RuntimeError("R4-B pilot lacks an eligible Equity or ETF")
        pilot = []
        for asset_class in ("EQUITIES", "ETF"):
            asset_id, listing_id, _ = selected[asset_class]
            bars = source.execute(
                "SELECT session_date,open,high,low,close FROM active_bars "
                "WHERE asset_id=? AND listing_id IS ? ORDER BY session_date",
                (asset_id, listing_id),
            ).fetchall()
            frame = pd.DataFrame(
                [row[1:] for row in bars],
                columns=["Open", "High", "Low", "Close"],
                index=pd.to_datetime([row[0] for row in bars]),
            )
            features = build_r4b_features(frame, benchmark, contract_path=contract_path)
            pilot.append(
                {
                    "asset_id": asset_id,
                    "listing_id": listing_id,
                    "asset_class": asset_class,
                    "source_bars": len(frame),
                    "relative_momentum_20_available": int(features["relative_momentum_20"].notna().sum()),
                    "relative_momentum_60_available": int(features["relative_momentum_60"].notna().sum()),
                    "relative_momentum_120_available": int(features["relative_momentum_120"].notna().sum()),
                    "confirmed_structure_available": int(
                        features["confirmed_structure_sequence"].ne("INSUFFICIENT_CONFIRMED_PIVOTS").sum()
                    ),
                    "sector_benchmark_available": False,
                    "historical_region_verified": False,
                }
            )
    return {
        "version": contract["version"],
        "contract_fingerprint": contract_fingerprint,
        "source_dataset_fingerprint": contract["source_dataset_fingerprint"],
        "benchmark_symbol": contract["market_benchmark"],
        "benchmark_bars": len(benchmark_rows),
        "source_bars": total_bars,
        "strictly_prior_fresh_benchmark_bars": eligible,
        "strictly_prior_fresh_benchmark_coverage_pct": round(100 * eligible / total_bars, 6),
        "benchmark_120_session_warmup_upper_bound_bars": warm120,
        "benchmark_120_session_warmup_upper_bound_pct": round(100 * warm120 / total_bars, 6),
        "pilot": pilot,
        "outcomes_read": False,
        "production_rules_changed": False,
        "capability_status": "ACTIVE_PIT_LIMITED_SCOPE_GLOBAL_BENCHMARK_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    print(json.dumps(audit(args.source, args.contract), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
