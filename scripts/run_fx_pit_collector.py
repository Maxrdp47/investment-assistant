from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cot_positioning import (  # noqa: E402
    DEFAULT_COT_DB_PATH,
    load_all_cot_reports_as_of,
    refresh_official_cot_forward,
)
from fx_carry_pit import normalize_fx_ohlc  # noqa: E402
from fx_pit_collector import (  # noqa: E402
    DEFAULT_COLLECTOR_DB_PATH,
    DEFAULT_COLLECTOR_LOCK_PATH,
    fx_pit_collector_audit,
    run_fx_pit_collector,
)


DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "fx_pit_collector.json"
YFINANCE_CACHE_PATH = PROJECT_ROOT / ".yfinance-cache"


def _git(*args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc(value: object) -> datetime:
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Collector-Zeitpunkt benötigt eine Zeitzone.")
    return stamp.astimezone(timezone.utc)


def _source_timestamp(value: object, fallback: datetime) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.to_pydatetime().isoformat() if not pd.isna(stamp) else fallback.isoformat()


def yahoo_daily_ohlc_provider(context: Mapping[str, object], *, offline: bool = False) -> dict[str, object]:
    observed = _utc(context["observed_at"])
    pairs = dict(context["pairs"])
    if offline:
        return {
            "status": "NOT_SCHEDULED",
            "source": "Yahoo Finance/yfinance daily FX bars",
            "missingness": {"offline_pilot": True, "bid_ask_available": False},
            "coverage": [
                {"pair_id": pair_id, "feature": "PRICE", "status": "UNKNOWN", "reason": "offline pilot; provider not called"}
                for pair_id in pairs
            ],
            "response_quality": "NOT_CALLED",
        }
    observations = []
    coverage = []
    errors = []
    YFINANCE_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YFINANCE_CACHE_PATH))
    for pair_id, contract in pairs.items():
        ticker = str(contract["source_ticker"])
        try:
            frame = yf.Ticker(ticker).history(
                period="5d",
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
            if frame.empty:
                raise RuntimeError("empty daily FX history")
            row = frame.iloc[-1]
            normalized = normalize_fx_ohlc(
                contract,
                {
                    "open": row["Open"],
                    "high": row["High"],
                    "low": row["Low"],
                    "close": row["Close"],
                },
            )
            bar_timestamp = _source_timestamp(frame.index[-1], observed)
            raw_fingerprint = hashlib.sha256(
                json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            observations.append(
                {
                    "observation_type": "FX_PRICE_BAR",
                    "entity_id": pair_id,
                    "pair_id": pair_id,
                    "status": "OBSERVED",
                    "source_type": "FORWARD_PIT",
                    "source": "Yahoo Finance/yfinance daily FX bars",
                    "source_record_id": f"{ticker}:{bar_timestamp}:{raw_fingerprint[:16]}",
                    "source_timestamp": bar_timestamp,
                    "observed_at": observed.isoformat(),
                    "first_seen_at": observed.isoformat(),
                    "imported_at": observed.isoformat(),
                    "payload": {
                        **normalized,
                        "interval": "1d",
                        "source_ticker": ticker,
                        "canonical_pair_orientation": pair_id,
                        "source_is_inverse": bool(contract["source_is_inverse"]),
                        "bid_ask_available": False,
                    },
                    "quality": "AGGREGATOR_DAILY_BAR_NOT_BID_ASK",
                }
            )
            coverage.append(
                {"pair_id": pair_id, "feature": "PRICE", "status": "AVAILABLE_PIT", "reason": "forward daily bar with real first_seen_at"}
            )
        except Exception as exc:
            errors.append({"pair_id": pair_id, "error": str(exc)})
            observations.append(
                {
                    "observation_type": "MISSINGNESS",
                    "entity_id": pair_id,
                    "pair_id": pair_id,
                    "status": "PROVIDER_FAILURE",
                    "source_type": "FORWARD_PIT",
                    "source": "Yahoo Finance/yfinance daily FX bars",
                    "source_record_id": f"{context['schedule_slot']}:{ticker}:failure",
                    "observed_at": observed.isoformat(),
                    "first_seen_at": observed.isoformat(),
                    "imported_at": observed.isoformat(),
                    "payload": {"price_bar_available": False, "bid_ask_available": False},
                    "error": str(exc),
                    "quality": "FAILED",
                }
            )
            coverage.append(
                {"pair_id": pair_id, "feature": "PRICE", "status": "UNKNOWN", "reason": "provider failure is not structural absence"}
            )
    return {
        "status": "PROVIDER_FAILURE" if errors and not any(item["status"] == "OBSERVED" for item in observations) else "OBSERVED",
        "source": "Yahoo Finance/yfinance daily FX bars",
        "observations": observations,
        "coverage": coverage,
        "error": json.dumps(errors, ensure_ascii=False) if errors else None,
        "response_quality": "PARTIAL" if errors else "AGGREGATOR_DAILY_BAR",
    }


def official_cftc_provider(
    context: Mapping[str, object],
    *,
    offline: bool = False,
    force_refresh: bool = False,
) -> dict[str, object]:
    observed = _utc(context["observed_at"])
    settings = dict(context["settings"])
    names_by_currency = dict(settings.get("cot_currency_market_names") or {})
    schedule = dict(settings.get("schedule") or {})
    refresh_weekday = int(schedule.get("cot_refresh_weekday_utc", 4))
    refresh = {"status": "not_scheduled", "errors": []}
    if offline:
        return {
            "status": "NOT_SCHEDULED",
            "source": "official_cftc_public_reporting",
            "missingness": {"offline_pilot": True, "refresh_called": False},
            "coverage": [
                {"pair_id": pair_id, "feature": "COT", "status": "UNKNOWN", "reason": "offline pilot; provider not called"}
                for pair_id in context["pairs"]
            ],
            "response_quality": "NOT_CALLED",
        }
    if force_refresh or observed.weekday() == refresh_weekday:
        refresh = refresh_official_cot_forward(
            retrieved_at=observed,
            path=DEFAULT_COT_DB_PATH,
        )
    reports = load_all_cot_reports_as_of(observed, DEFAULT_COT_DB_PATH)
    observations = []
    available_currencies = set()
    for currency, market_names in sorted(names_by_currency.items()):
        patterns = [str(name).upper() for name in market_names]
        matches = [
            report
            for report in reports
            if report.get("pit_eligible")
            and str(report.get("report_type")) == "tff_futures_only"
            and any(pattern in str(report.get("market_name") or "").upper() for pattern in patterns)
        ]
        if not matches:
            continue
        latest = max(
            matches,
            key=lambda report: (
                str(report.get("available_at") or ""),
                str(report.get("report_date") or ""),
                str(report.get("report_id") or ""),
            ),
        )
        available_at = str(
            latest.get("available_at")
            or latest.get("published_at")
            or latest.get("first_seen_at")
        )
        observations.append(
            {
                "observation_type": "COT",
                "entity_id": f"COT:{currency}",
                "currency": currency,
                "status": "OBSERVED",
                "source_type": "FORWARD_PIT",
                "source": "official_cftc_public_reporting",
                "source_record_id": str(latest["report_id"]),
                "source_timestamp": available_at,
                "observed_at": observed.isoformat(),
                "first_seen_at": observed.isoformat(),
                "imported_at": observed.isoformat(),
                "payload": {
                    "report_date": latest.get("report_date"),
                    "published_at": latest.get("published_at"),
                    "available_at": latest.get("available_at"),
                    "first_seen_at": latest.get("first_seen_at"),
                    "market_code": latest.get("market_code"),
                    "market_name": latest.get("market_name"),
                    "report_type": latest.get("report_type"),
                    "open_interest": latest.get("open_interest"),
                    "categories": latest.get("categories"),
                    "classification_guardrails": latest.get("classification_guardrails"),
                    "shadow_only": True,
                },
                "quality": "OFFICIAL_CFTC_FORWARD_AVAILABILITY",
            }
        )
        available_currencies.add(currency)
    coverage = []
    for pair_id, contract in context["pairs"].items():
        currencies = {str(contract["base_currency"]), str(contract["quote_currency"])}
        coverage.append(
            {
                "pair_id": pair_id,
                "feature": "COT",
                "status": "AVAILABLE_PIT" if currencies <= available_currencies else "AVAILABLE_SHADOW" if currencies & available_currencies else "UNAVAILABLE",
                "reason": "official CFTC report available after verified/forward availability cutoff",
            }
        )
    refresh_errors = list(refresh.get("errors") or [])
    return {
        "status": "PROVIDER_FAILURE" if refresh_errors and not observations else "OBSERVED" if observations else "NO_RELIABLE_DATA",
        "source": "official_cftc_public_reporting",
        "observations": observations,
        "coverage": coverage,
        "error": json.dumps(refresh_errors, ensure_ascii=False) if refresh_errors else None,
        "missingness": {"no_new_release": not observations, "refresh_status": refresh.get("status")},
        "response_quality": "OFFICIAL_WITH_REFRESH_ERRORS" if refresh_errors else "OFFICIAL",
    }


def unavailable_provider(
    name: str,
    features: tuple[str, ...],
):
    def provider(context: Mapping[str, object]) -> dict[str, object]:
        return {
            "status": "NO_RELIABLE_DATA",
            "source": name,
            "missingness": {
                "reliable_adapter_available": False,
                "values_approximated": False,
                "absence_means_no_event": False,
            },
            "coverage": [
                {"pair_id": pair_id, "feature": feature, "status": "UNAVAILABLE", "reason": "no reliable free PIT adapter configured"}
                for pair_id in context["pairs"]
                for feature in features
            ],
            "response_quality": "NO_RELIABLE_ADAPTER",
        }

    return provider


def load_settings(path: Path) -> dict[str, object]:
    settings = json.loads(path.read_text(encoding="utf-8"))
    if settings.get("mode") != "FX_PIT_OBSERVER":
        raise ValueError("FX-PIT-Konfiguration besitzt nicht den sicheren Observer-Modus.")
    return settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Append-only FX-PIT-Observer ohne Strategie-/Tradepfad")
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--at")
    parser.add_argument("--slot")
    parser.add_argument("--offline-pilot", action="store_true")
    parser.add_argument("--force-cot-refresh", action="store_true")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    settings = load_settings(args.settings)
    database = args.database or PROJECT_ROOT / str(settings.get("database_path") or DEFAULT_COLLECTOR_DB_PATH)
    lock_path = args.lock or PROJECT_ROOT / str(settings.get("lock_path") or DEFAULT_COLLECTOR_LOCK_PATH)
    if args.audit:
        print(json.dumps(fx_pit_collector_audit(database), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    observed = _utc(args.at or datetime.now(timezone.utc).isoformat())
    providers = {
        "yahoo_daily_ohlc": lambda context: yahoo_daily_ohlc_provider(context, offline=args.offline_pilot),
        "official_cftc_cot": lambda context: official_cftc_provider(
            context,
            offline=args.offline_pilot,
            force_refresh=args.force_cot_refresh,
        ),
        "actual_policy_rates": unavailable_provider("verified_actual_policy_rate_source", ("POLICY_RATE", "RATE_DIFFERENTIAL")),
        "macro_expectations_vintages": unavailable_provider("verified_macro_expectation_vintage_source", ("EXPECTED_RATE", "MACRO_VINTAGE", "SURPRISE", "INTERVENTION", "RISK_REGIME", "VOLATILITY")),
        "reliable_bid_ask": unavailable_provider("reliable_historical_or_forward_bid_ask_source", ("SPREAD_BIDASK",)),
    }
    result = run_fx_pit_collector(
        settings,
        providers,
        path=database,
        lock_path=lock_path,
        observed_at=observed.isoformat(),
        schedule_slot=args.slot or observed.date().isoformat() + (":offline-pilot" if args.offline_pilot else ":daily"),
        provenance={
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit_hash": _git("rev-parse", "HEAD"),
            "code_fingerprint": _sha256(PROJECT_ROOT / "fx_pit_collector.py"),
            "command": "scripts/run_fx_pit_collector.py",
        },
    )
    result["audit"] = fx_pit_collector_audit(database)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["audit"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
