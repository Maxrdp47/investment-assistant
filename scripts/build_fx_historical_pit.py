from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fx_carry_pit import default_fx_pair_contracts, normalize_fx_ohlc  # noqa: E402
from fx_historical_pit import (  # noqa: E402
    DEFAULT_HISTORICAL_FX_DB_PATH,
    FX_HISTORICAL_PIT_VERSION,
    append_fx_coverage_snapshot,
    append_historical_fx_records,
    fx_coverage_matrix,
    historical_fx_inventory,
    load_historical_fx_records,
)


DEFAULT_EXPORT_PATH = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "fx_historical_pit_2026-08-29-v1.json"
)
DEFAULT_START = "2010-01-01"
SESSION_AVAILABILITY_DELAY_MINUTES = 15
YFINANCE_CACHE_PATH = PROJECT_ROOT / ".yfinance-cache"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _session_times(day: date, contract: Mapping[str, object]) -> tuple[str, str]:
    close_hour, close_minute = map(
        int, str(contract["canonical_daily_close"]).split(":", maxsplit=1)
    )
    local_close = datetime.combine(
        day,
        time(close_hour, close_minute),
        tzinfo=ZoneInfo(str(contract["session_timezone"])),
    )
    available = local_close + timedelta(minutes=SESSION_AVAILABILITY_DELAY_MINUTES)
    return (
        local_close.astimezone(timezone.utc).isoformat(),
        available.astimezone(timezone.utc).isoformat(),
    )


def _download_pair_history(
    contract: Mapping[str, object], start: str, end: str
) -> list[dict[str, object]]:
    YFINANCE_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YFINANCE_CACHE_PATH))
    frame = yf.download(
        str(contract["source_ticker"]),
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )
    if frame is None or frame.empty:
        return []
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    rows: list[dict[str, object]] = []
    for index, row in frame.iterrows():
        values = {
            "date": pd.Timestamp(index).date().isoformat(),
            "open": row.get("Open"),
            "high": row.get("High"),
            "low": row.get("Low"),
            "close": row.get("Close"),
            "adj_close": row.get("Adj Close"),
            "volume": row.get("Volume"),
        }
        if any(pd.isna(values[key]) for key in ("open", "high", "low", "close")):
            continue
        rows.append(values)
    return rows


HistoryLoader = Callable[[Mapping[str, object], str, str], Sequence[Mapping[str, object]]]


def build_historical_fx_foundation(
    *,
    start: str,
    end: str,
    imported_at: str,
    db_path: Path,
    export_path: Path,
    history_loader: HistoryLoader = _download_pair_history,
) -> dict[str, object]:
    contracts = default_fx_pair_contracts()
    records: list[dict[str, object]] = []
    source_health: dict[str, dict[str, object]] = {}
    for pair_id, contract in contracts.items():
        invalid_bars: list[dict[str, str]] = []
        try:
            bars = list(history_loader(contract, start, end))
            source_health[pair_id] = {
                "status": "SUCCESS" if bars else "NO_RELIABLE_DATA",
                "bar_n": len(bars),
                "source": contract["source"],
                "source_ticker": contract["source_ticker"],
            }
        except Exception as exc:
            bars = []
            source_health[pair_id] = {
                "status": "PROVIDER_FAILURE",
                "bar_n": 0,
                "source": contract["source"],
                "source_ticker": contract["source_ticker"],
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }
        for raw in bars:
            observation_day = date.fromisoformat(str(raw["date"])[:10])
            try:
                ohlc = normalize_fx_ohlc(contract, raw)
            except Exception as exc:
                invalid_bars.append(
                    {
                        "date": observation_day.isoformat(),
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:200],
                    }
                )
                continue
            release_at, available_at = _session_times(observation_day, contract)
            records.append(
                {
                    "feature": "PRICE",
                    "pair_id": pair_id,
                    "observation_date": observation_day.isoformat(),
                    "release_at": release_at,
                    "available_at": available_at,
                    "vintage_date": observation_day.isoformat(),
                    "first_seen_at": imported_at,
                    "imported_at": imported_at,
                    "value": ohlc["close"],
                    "unit": f"{contract['quote_currency']}_per_{contract['base_currency']}",
                    "source": "Yahoo Finance/yfinance unadjusted daily FX bar",
                    "source_record_id": f"{contract['source_ticker']}:{observation_day.isoformat()}:1d",
                    "source_type": "HISTORICAL_PIT",
                    "coverage_status": "AVAILABLE_PIT",
                    "metadata": {
                        "ohlc": ohlc,
                        "source_ticker": contract["source_ticker"],
                        "source_is_inverse": contract["source_is_inverse"],
                        "session_timezone": contract["session_timezone"],
                        "canonical_daily_close": contract["canonical_daily_close"],
                        "availability_basis": "CONSERVATIVE_SESSION_CLOSE_PLUS_15_MINUTES",
                        "provider_first_seen_historically_observed": False,
                        "price_fact_available_only_after_completed_session": True,
                        "adjusted": False,
                        "volume_reliable": False,
                    },
                }
            )
        if invalid_bars:
            source_health[pair_id]["invalid_bar_n"] = len(invalid_bars)
            source_health[pair_id]["invalid_bar_examples"] = invalid_bars[:5]
            if source_health[pair_id]["status"] == "SUCCESS":
                source_health[pair_id]["status"] = "SUCCESS_WITH_INVALID_BARS_SKIPPED"

    store_result = append_historical_fx_records(records, path=db_path)
    stored = load_historical_fx_records(path=db_path)
    first_year = int(start[:4])
    last_year = int((datetime.fromisoformat(end).date() - timedelta(days=1)).year)
    coverage = fx_coverage_matrix(
        stored,
        pair_ids=list(contracts),
        years=list(range(first_year, last_year + 1)),
    )
    append_fx_coverage_snapshot(coverage, created_at=imported_at, path=db_path)
    inventory = historical_fx_inventory(stored)
    payload: dict[str, object] = {
        "status": "HISTORICAL_FX_PIT_READY_WITH_PARTIAL_COVERAGE",
        "version": FX_HISTORICAL_PIT_VERSION,
        "created_at": imported_at,
        "requested_start": start,
        "requested_end_exclusive": end,
        "frequency": "1d",
        "pairs": list(contracts),
        "pair_contract_fingerprints": {
            pair_id: contract["pair_fingerprint"] for pair_id, contract in contracts.items()
        },
        "database_path": str(db_path),
        "inventory": inventory,
        "coverage": coverage,
        "source_health": source_health,
        "store_result": store_result,
        "classification": {
            "price": "AVAILABLE_PIT_AFTER_CONSERVATIVE_SESSION_CLOSE",
            "policy_rate": "UNAVAILABLE",
            "rate_differential": "UNAVAILABLE",
            "expected_rate": "UNAVAILABLE",
            "macro_vintage": "UNAVAILABLE",
            "surprise": "UNAVAILABLE",
            "cot": "SEPARATE_OFFICIAL_PIPELINE; RELEASE_ELIGIBILITY_REQUIRED",
            "historical_bid_ask": "UNAVAILABLE",
            "costs": "PROXY_CONTRACT_ONLY; NO_NUMBERS_INVENTED",
        },
        "historical_vendor_first_seen_claimed": False,
        "today_revised_macro_backdated": False,
        "multi_asset_scan_started": False,
        "strategy_activated": False,
        "trade_signal_generated": False,
    }
    payload["artifact_fingerprint"] = _fingerprint(payload)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Historische kausale FX-PIT-Grundlage")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--at")
    parser.add_argument("--db", type=Path, default=DEFAULT_HISTORICAL_FX_DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT_PATH)
    args = parser.parse_args()
    created_at = args.at or datetime.now(timezone.utc).isoformat()
    result = build_historical_fx_foundation(
        start=args.start,
        end=args.end,
        imported_at=created_at,
        db_path=args.db,
        export_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return (
        0
        if any(
            str(item["status"]).startswith("SUCCESS")
            for item in result["source_health"].values()
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
