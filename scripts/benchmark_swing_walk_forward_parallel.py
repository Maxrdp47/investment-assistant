from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_swing_walk_forward as cli  # noqa: E402
from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_walk_forward import swing_walk_forward_strategy_profiles  # noqa: E402


def _canonical_fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_result_payload(runs: list[dict]) -> dict[str, object]:
    cases = sorted(
        (
            {
                "case_id": case["case_id"],
                "case_fingerprint": case["case_fingerprint"],
                "symbol": case["symbol"],
                "signal_at": case["signal_at"],
                "status": case["status"],
                "result_r": case.get("result_r"),
                "result_pct": case.get("result_pct"),
            }
            for run in runs
            for case in run["cases"]
        ),
        key=lambda case: (str(case["case_id"]), str(case["case_fingerprint"])),
    )
    data_fingerprints = {
        ticker: fingerprint
        for run in runs
        for ticker, fingerprint in run["data_fingerprints"].items()
    }
    return {
        "cases": cases,
        "data_fingerprints": dict(sorted(data_fingerprints.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DB-freier Laufzeitvergleich auf einem real gecachten Swing-Kampagnen-Teilschard."
    )
    parser.add_argument("--executor", choices=("threads", "processes"), required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--shard-index", type=int, default=3)
    parser.add_argument("--shard-count", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--cache-path", type=Path, default=cli.DEFAULT_CACHE_PATH)
    args = parser.parse_args()

    report = load_swing_universe(args.universe_path)
    if report.errors:
        raise RuntimeError("; ".join(report.errors))
    assets = [asset.as_dict() for asset in report.assets if asset.active]
    shard_assets = assets[int(args.shard_index) :: max(int(args.shard_count), 1)]
    scope = "2016-01-01|latest|1d|yfinance_auto_adjust_true"
    cached, _ = cli._load_cached_histories(
        [str(asset["ticker"]).upper() for asset in shard_assets],
        args.cache_path,
        cache_scope=scope,
        maximum_age_hours=float("inf"),
        refresh=False,
    )
    selected_assets = [
        asset
        for asset in shard_assets
        if str(asset["ticker"]).upper() in cached
    ][: max(int(args.sample_size), 1)]
    histories = {
        str(asset["ticker"]).upper(): cached[str(asset["ticker"]).upper()]
        for asset in selected_assets
    }
    if len(histories) < max(int(args.sample_size), 1):
        raise RuntimeError("Nicht genügend reale Cache-Daten für den repräsentativen Benchmark vorhanden.")

    parameters = {
        "step_sessions": 5,
        "future_sessions": 25,
        "sampling_mode": "balanced_history",
        "maximum_cases": 25_000,
        "maximum_cases_per_symbol": 6,
        "selection_round": 0,
        "selection_round_role": "exploration",
        "strategy_profiles": swing_walk_forward_strategy_profiles(
            ("current", "balanced", "precision", "payoff")
        ),
        "purge_overlapping_signals": True,
        "price_adjustment": "yfinance_auto_adjust_true",
        "research_split_boundaries": {
            "development_end": "2021-12-31",
            "validation_end": "2023-12-31",
            "last_signal_day": date.today().isoformat(),
        },
    }
    jobs = cli._analysis_jobs(
        histories,
        selected_assets,
        workers=max(int(args.workers), 1),
        parameters=parameters,
    )
    cpu_started = time.process_time()
    wall_started = time.perf_counter()
    runs = cli._analyze_histories_parallel(
        jobs,
        workers=max(int(args.workers), 1),
        executor_mode=str(args.executor),
    )
    wall_seconds = time.perf_counter() - wall_started
    main_process_cpu_seconds = time.process_time() - cpu_started
    stable = _stable_result_payload(runs)
    payload = {
        "benchmark_version": "swing-parallel-benchmark-2026.08.18-v1",
        "executor": str(args.executor),
        "workers": max(int(args.workers), 1),
        "logical_cpus": os.cpu_count(),
        "sample_kind": "real_cached_campaign_subshard",
        "sample_shard": f"{int(args.shard_index) + 1}-of-{max(int(args.shard_count), 1)}",
        "sample_tickers": list(histories),
        "assets": len(histories),
        "profiles": ["current", "balanced", "precision", "payoff"],
        "cases": len(stable["cases"]),
        "wall_seconds": round(wall_seconds, 6),
        "main_process_cpu_seconds": round(main_process_cpu_seconds, 6),
        "stable_result_fingerprint": _canonical_fingerprint(stable),
        "stable_result": stable,
        "database_writes": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in payload.items() if key != "stable_result"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
