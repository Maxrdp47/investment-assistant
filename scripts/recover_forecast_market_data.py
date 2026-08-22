from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forecast_recovery import (  # noqa: E402
    finish_recovery_run,
    record_recovery_asset,
    recovery_bars,
    start_recovery_run,
)
from forecast_runner import load_universe  # noqa: E402


def histories_from_batch(payload: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    if not isinstance(payload, pd.DataFrame) or payload.empty:
        return histories
    if not isinstance(payload.columns, pd.MultiIndex):
        if len(tickers) == 1 and "Close" in payload:
            histories[tickers[0]] = payload.dropna(subset=["Close"])
        return histories

    level_zero = {str(value).upper() for value in payload.columns.get_level_values(0)}
    level_one = {str(value).upper() for value in payload.columns.get_level_values(1)}
    for ticker in tickers:
        try:
            if ticker.upper() in level_zero:
                frame = payload.xs(ticker, axis=1, level=0, drop_level=True)
            elif ticker.upper() in level_one:
                frame = payload.xs(ticker, axis=1, level=1, drop_level=True)
            else:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        frame = frame.loc[:, ~frame.columns.duplicated()].copy()
        if "Close" in frame:
            frame = frame.dropna(subset=["Close"])
        if not frame.empty:
            histories[ticker] = frame
    return histories


def download_batch(
    tickers: list[str],
    *,
    interval: str,
    start: str,
    end: str,
) -> tuple[dict[str, pd.DataFrame], str | None]:
    try:
        payload = yf.download(
            tickers,
            start=start,
            end=end,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:300]}"
    return histories_from_batch(payload, tickers), None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rettet historische OHLCV-Daten ohne nachträgliche Forward-Prognosen."
    )
    parser.add_argument("--target", required=True, help="ISO-Zeitpunkt mit Zeitzone")
    parser.add_argument(
        "--database", default=str(PROJECT_ROOT / "runtime" / "forecast_recovery.sqlite3")
    )
    parser.add_argument(
        "--universe", default=str(PROJECT_ROOT / "config" / "forecast_universe.csv")
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--batch-pause", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = datetime.fromisoformat(args.target)
    if target.tzinfo is None or target.utcoffset() is None:
        raise ValueError("--target benötigt eine explizite Zeitzone.")
    universe = load_universe(Path(args.universe))
    database_path = Path(args.database)
    run_id = start_recovery_run(database_path, target, len(universe))
    safe_batch_size = max(1, min(int(args.batch_size), 100))
    daily_start = (target.date() - timedelta(days=370)).isoformat()
    daily_end = target.date().isoformat()
    intraday_start = target.date().isoformat()
    intraday_end = (target.date() + timedelta(days=1)).isoformat()

    for offset in range(0, len(universe), safe_batch_size):
        assets = universe[offset : offset + safe_batch_size]
        tickers = [asset["ticker"] for asset in assets]
        daily, daily_error = download_batch(
            tickers, interval="1d", start=daily_start, end=daily_end
        )
        intraday, intraday_error = download_batch(
            tickers, interval="5m", start=intraday_start, end=intraday_end
        )
        for asset in assets:
            ticker = asset["ticker"]
            errors = []
            if daily_error:
                errors.append(f"1d: {daily_error}")
            if intraday_error:
                errors.append(f"5m: {intraday_error}")
            if ticker not in daily:
                errors.append("1d: keine Daten")
            if ticker not in intraday:
                errors.append("5m: keine Daten")
            record_recovery_asset(
                database_path,
                run_id,
                asset,
                recovery_bars(daily.get(ticker, pd.DataFrame()), interval="1d", target_at=target),
                recovery_bars(
                    intraday.get(ticker, pd.DataFrame()), interval="5m", target_at=target
                ),
                errors,
            )
        completed = min(offset + len(assets), len(universe))
        print(f"Recovery-Fortschritt: {completed}/{len(universe)}", flush=True)
        if completed < len(universe) and float(args.batch_pause) > 0:
            time.sleep(float(args.batch_pause))

    print(json.dumps(finish_recovery_run(database_path, run_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
