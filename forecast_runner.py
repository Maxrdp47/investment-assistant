from __future__ import annotations

import csv
import json
import logging
import tempfile
import time
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

import pandas as pd
import yfinance as yf

from forecast_baselines import direction_hit as baseline_direction_hit, market_benchmark_definition
from forecast_calibration import write_calibration_profile
from forecast_lock import ForecastRunLock, lock_path_for_database
from forecast_horizon_schedule import apply_horizon_collection_policy
from forecast_sampling import build_weekly_cohort_plan, select_weekly_cohort
from forecast_store import (
    DEFAULT_DATABASE_PATH,
    FORECAST_LOGIC_VERSION,
    database_health,
    completed_sampling_cohort_ids,
    finish_run,
    interrupt_run,
    latest_horizon_start_dates,
    maintain_database,
    measurement_contract_audit,
    pending_evaluations,
    record_asset_failure,
    record_evaluation,
    record_evaluation_failure,
    record_forecast,
    record_run_operations,
    sampling_for_run_date,
    start_or_resume_run,
    successful_tickers,
)
from forecast_weekly_report import write_weekly_report


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "forecast_settings.json"


def load_settings(path: Path = DEFAULT_SETTINGS_PATH, *, strict: bool = False) -> dict:
    defaults = {
        "task_name": "InvestmentAssistantDailyForecasts",
        "local_run_time": "22:30",
        "database_path": "runtime/forecasts.sqlite3",
        "log_path": "runtime/logs/forecast_runner.log",
        "calibration_path": "runtime/calibration_profile.json",
        "universe_path": "config/forecast_universe.csv",
        "reference_universe_path": "",
        "weekly_universe_path": "",
        "weekly_minimum_assets": 1500,
        "weekly_schedule_start_date": "",
        "weekly_report_directory": "runtime/weekly_reports",
        "batch_size": 25,
        "request_delay_seconds": 1.0,
        "batch_pause_seconds": 8.0,
        "max_retries": 2,
        "evaluation_limit": 1000,
        "logic_version": FORECAST_LOGIC_VERSION,
    }
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        if strict:
            raise ValueError(f"Die Prognosekonfiguration ist nicht lesbar: {Path(path)}") from exc
        data = {}
    if not isinstance(data, dict):
        if strict:
            raise ValueError("Die Prognosekonfiguration muss ein JSON-Objekt sein.")
        data = {}
    defaults.update(data)
    return defaults


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_universe(path: Path) -> list[dict[str, str]]:
    required = {"ticker", "asset_type", "name", "region", "category", "version"}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Das Prognoseuniversum besitzt nicht alle erforderlichen Spalten.")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        result.append({key: str(row.get(key) or "").strip() for key in required})
        result[-1]["ticker"] = ticker
    if not result:
        raise ValueError("Das Prognoseuniversum enthält keine verwendbaren Ticker.")
    return result


def _verify_writable_parent(target_path: Path) -> None:
    parent = Path(target_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".forecast-preflight-", dir=parent, delete=True):
        pass


def runtime_preflight(settings_path: Path = DEFAULT_SETTINGS_PATH) -> dict:
    """Validate the unattended runtime without requesting market data or creating forecasts."""
    settings = load_settings(settings_path, strict=True)
    scheduled_time = str(settings.get("local_run_time") or "")
    try:
        datetime.strptime(scheduled_time, "%H:%M")
    except ValueError as exc:
        raise ValueError("Die konfigurierte Startzeit muss das Format HH:MM verwenden.") from exc

    numeric_rules = {
        "batch_size": (int, 0),
        "request_delay_seconds": (float, 0.0),
        "batch_pause_seconds": (float, 0.0),
        "max_retries": (int, 0),
        "evaluation_limit": (int, 1),
        "weekly_minimum_assets": (int, 1),
    }
    for key, (converter, minimum) in numeric_rules.items():
        try:
            value = converter(settings[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Ungültiger Konfigurationswert: {key}") from exc
        if value < minimum:
            raise ValueError(f"Konfigurationswert {key} muss mindestens {minimum} sein.")

    logic_version = str(settings.get("logic_version") or "").strip()
    if not logic_version:
        raise ValueError("Die Prognosekonfiguration benötigt eine Logikversion.")

    universe_path = project_path(settings["universe_path"])
    database_path = project_path(settings["database_path"])
    log_path = project_path(settings["log_path"])
    calibration_path = project_path(settings["calibration_path"])
    universe = load_universe(universe_path)
    weekly_summary = None
    weekly_universe_value = str(settings.get("weekly_universe_path") or "").strip()
    if weekly_universe_value:
        reference_value = str(settings.get("reference_universe_path") or "").strip()
        reference_path = project_path(reference_value or settings["universe_path"])
        weekly_universe_path = project_path(weekly_universe_value)
        plan = build_weekly_cohort_plan(
            weekly_universe_path,
            reference_path,
            minimum_active_assets=int(settings["weekly_minimum_assets"]),
        )
        schedule_start_value = str(settings.get("weekly_schedule_start_date") or "").strip()
        if schedule_start_value:
            try:
                date.fromisoformat(schedule_start_value)
            except ValueError as exc:
                raise ValueError(
                    "Der Start des Wochenplans muss das Format JJJJ-MM-TT verwenden."
                ) from exc
        weekly_summary = {
            key: value
            for key, value in plan.items()
            if key != "cohorts"
        }
        _verify_writable_parent(
            project_path(settings["weekly_report_directory"]) / "weekly-report.json"
        )
    _verify_writable_parent(database_path)
    _verify_writable_parent(log_path)
    _verify_writable_parent(calibration_path)
    health = database_health(database_path)
    asset_types: dict[str, int] = {}
    for asset in universe:
        asset_type = str(asset.get("asset_type") or "Unbekannt")
        asset_types[asset_type] = asset_types.get(asset_type, 0) + 1

    return {
        "status": "ok" if health["status"] == "ok" else "attention",
        "settings_path": str(Path(settings_path)),
        "scheduled_time": scheduled_time,
        "logic_version": logic_version,
        "universe": {
            "path": str(universe_path),
            "count": len(universe),
            "unique_tickers": len({asset["ticker"] for asset in universe}),
            "asset_types": asset_types,
        },
        "weekly_sampling": weekly_summary,
        "database": health,
        "log_path": str(log_path),
        "calibration_path": str(calibration_path),
        "market_data_requested": False,
        "forecasts_written": False,
        "data_deleted": False,
    }


def configure_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("investment_assistant.forecasts")
    logger.setLevel(logging.INFO)
    for existing_handler in list(logger.handlers):
        logger.removeHandler(existing_handler)
        existing_handler.close()
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def close_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.flush()
        handler.close()


def safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).replace("\r", " ").replace("\n", " ").split())
    return f"{type(exc).__name__}: {message[:500]}"


def is_rate_limit_error(exc: BaseException | str) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in ("429", "too many requests", "rate limit", "ratelimit"))


def operational_run_metrics(
    collection: dict,
    elapsed_seconds: float,
    database_bytes_before: int,
    maintenance: dict,
) -> dict:
    processed = int(collection.get("processed") or 0)
    failed = int(collection.get("failed") or 0)
    elapsed = max(float(elapsed_seconds), 0.0)
    database_bytes_after = int(maintenance.get("database_bytes") or 0)
    return {
        "elapsed_seconds": round(elapsed, 2),
        "processed_per_minute": round(processed / elapsed * 60, 2) if processed and elapsed else 0.0,
        "failure_rate_pct": round(failed / processed * 100, 2) if processed else 0.0,
        "rate_limit_failures": int(collection.get("rate_limit_failures") or 0),
        "database_bytes_before": int(database_bytes_before),
        "database_bytes_after": database_bytes_after,
        "database_growth_bytes": database_bytes_after - int(database_bytes_before),
        "schema_version": maintenance.get("schema_version"),
        "database_status": maintenance.get("status"),
    }


def default_snapshot_builder(asset: dict, run_date: str, logic_version: str) -> dict:
    from app import build_background_forecast_snapshot

    return build_background_forecast_snapshot(asset, run_date, logic_version)


def collect_forecasts(
    universe: list[dict],
    database_path: Path = DEFAULT_DATABASE_PATH,
    run_date: str | None = None,
    logic_version: str = FORECAST_LOGIC_VERSION,
    snapshot_builder: Callable[[dict, str, str], dict] = default_snapshot_builder,
    max_retries: int = 2,
    request_delay_seconds: float = 1.0,
    batch_size: int = 25,
    batch_pause_seconds: float = 8.0,
    force: bool = False,
    interrupt_after: int | None = None,
    logger: logging.Logger | None = None,
    sampling: dict | None = None,
    market_benchmark_snapshots: dict[str, dict] | None = None,
) -> dict:
    run_date = run_date or date.today().isoformat()
    start = start_or_resume_run(
        run_date,
        len(universe),
        database_path,
        logic_version,
        force,
        sampling,
    )
    if not start.should_run:
        return {
            "run_id": start.run_id,
            "status": "skipped_same_day",
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "rate_limit_failures": 0,
            "resumed": False,
        }

    completed = successful_tickers(start.run_id, database_path)
    processed = succeeded = failed = rate_limit_failures = 0
    try:
        for index, asset in enumerate(universe, start=1):
            ticker = str(asset.get("ticker") or "").upper()
            if ticker in completed:
                continue
            last_error: BaseException | None = None
            for attempt in range(max(int(max_retries), 0) + 1):
                if logger:
                    logger.info(
                        "Asset-Versuch gestartet | run_id=%s | ticker=%s | position=%s/%s | attempt=%s/%s",
                        start.run_id,
                        ticker,
                        index,
                        len(universe),
                        attempt + 1,
                        max(int(max_retries), 0) + 1,
                    )
                try:
                    snapshot = snapshot_builder(asset, run_date, logic_version)
                    benchmark_snapshot = (market_benchmark_snapshots or {}).get(ticker)
                    if benchmark_snapshot is not None:
                        snapshot.setdefault("market_benchmark_snapshot", benchmark_snapshot)
                    if sampling is not None:
                        snapshot.setdefault(
                            "sampling",
                            {
                                **sampling,
                                "sampling_role": asset.get("sampling_role"),
                                "asset_cohort_weekday": asset.get("cohort_weekday"),
                                "asset_cohort_label": asset.get("cohort_label"),
                                "liquidity_class": asset.get("liquidity_class"),
                                "source_group": asset.get("source_group"),
                            },
                        )
                    snapshot = apply_horizon_collection_policy(
                        snapshot,
                        date.fromisoformat(run_date),
                        latest_horizon_start_dates(
                            ticker,
                            database_path,
                            model_type=str(snapshot.get("model_type") or "entry_analysis"),
                        ),
                    )
                    record_forecast(start.run_id, snapshot, database_path)
                    succeeded += 1
                    last_error = None
                    if logger:
                        logger.info("Prognose gespeichert | ticker=%s | attempt=%s", ticker, attempt + 1)
                    break
                except Exception as exc:  # one asset must never cancel the daily universe
                    last_error = exc
                    if attempt < max_retries:
                        time.sleep(max(float(request_delay_seconds), 0.0))
            if last_error is not None:
                record_asset_failure(start.run_id, ticker, safe_error(last_error), database_path)
                failed += 1
                rate_limit_failures += int(is_rate_limit_error(last_error))
                if logger:
                    logger.warning("Asset fehlgeschlagen | ticker=%s | error=%s", ticker, safe_error(last_error))
            processed += 1
            if interrupt_after is not None and processed >= interrupt_after:
                raise InterruptedError("Simulierter Teilabbruch für Wiederaufnahmetest")
            if request_delay_seconds > 0:
                time.sleep(float(request_delay_seconds))
            if batch_size > 0 and index % batch_size == 0 and batch_pause_seconds > 0:
                time.sleep(float(batch_pause_seconds))
    except BaseException as exc:
        interrupt_run(start.run_id, safe_error(exc), database_path)
        if logger:
            logger.error("Lauf unterbrochen | run_id=%s | error=%s", start.run_id, safe_error(exc))
        return {
            "run_id": start.run_id,
            "status": "interrupted",
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "rate_limit_failures": rate_limit_failures,
            "resumed": start.resumed,
        }

    status = finish_run(
        start.run_id,
        database_path,
        f"{succeeded} erfolgreich, {failed} fehlgeschlagen; bereits vorhandene Assets wurden übersprungen.",
    )
    return {
        "run_id": start.run_id,
        "status": status,
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "rate_limit_failures": rate_limit_failures,
        "resumed": start.resumed,
    }


def _flat_price_data(symbol: str, start: date, end: date) -> pd.DataFrame:
    data = yf.download(
        symbol,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.rename(columns=str.title)


def _normalized_price_history(frame: object) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized = normalized.loc[:, ~normalized.columns.duplicated()].copy()
    normalized.columns = [str(column).title() for column in normalized.columns]
    if "Close" not in normalized:
        return pd.DataFrame()
    for column in ("Open", "High", "Low", "Close", "Volume"):
        if column in normalized:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized.dropna(subset=["Close"])


def _histories_from_batch(payload: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    if not isinstance(payload, pd.DataFrame) or payload.empty:
        return histories
    if not isinstance(payload.columns, pd.MultiIndex):
        if len(tickers) == 1:
            normalized = _normalized_price_history(payload)
            if not normalized.empty:
                histories[tickers[0]] = normalized
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
        normalized = _normalized_price_history(frame)
        if not normalized.empty:
            histories[ticker] = normalized
    return histories


def _batch_price_histories(
    tickers: list[str],
    start: date,
    end: date,
    *,
    batch_size: int = 75,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    histories: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    unique_tickers = list(dict.fromkeys(str(ticker).upper() for ticker in tickers if ticker))
    safe_batch_size = max(1, min(int(batch_size), 100))
    for offset in range(0, len(unique_tickers), safe_batch_size):
        batch = unique_tickers[offset : offset + safe_batch_size]
        try:
            payload = yf.download(
                batch,
                start=start,
                end=end,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                actions=False,
                progress=False,
                threads=True,
            )
        except Exception as exc:
            message = safe_error(exc)
            errors.update({ticker: message for ticker in batch})
            continue
        batch_histories = _histories_from_batch(payload, batch)
        histories.update(batch_histories)
        for ticker in batch:
            if ticker not in batch_histories:
                errors[ticker] = "Keine Kursdaten für die fällige Auswertung verfügbar"
    return histories, errors


def _historic_fx_rate(currency: str, target_day: date, fallback: float | None) -> float | None:
    currency = (currency or "EUR").upper()
    if currency == "EUR":
        return 1.0
    for ticker, inverse in [(f"{currency}EUR=X", False), (f"EUR{currency}=X", True)]:
        try:
            data = _flat_price_data(ticker, target_day - timedelta(days=3), target_day + timedelta(days=8))
        except Exception:
            continue
        if data.empty or "Close" not in data:
            continue
        index_days = pd.Index(pd.to_datetime(data.index).date)
        close = data.loc[index_days >= target_day, "Close"].dropna()
        if close.empty or float(close.iloc[0]) <= 0:
            continue
        value = float(close.iloc[0])
        return 1.0 / value if inverse else value
    return fallback


def prepare_market_benchmark_snapshots(
    universe: list[dict],
    observation_day: date,
) -> dict[str, dict]:
    definitions = {
        str(asset.get("ticker") or "").upper(): market_benchmark_definition(
            asset.get("asset_type"),
            asset.get("region"),
        )
        for asset in universe
        if asset.get("ticker")
    }
    benchmark_tickers = sorted({item["ticker"] for item in definitions.values()})
    histories, errors = _batch_price_histories(
        benchmark_tickers,
        observation_day - timedelta(days=10),
        observation_day + timedelta(days=1),
        batch_size=20,
    )
    fx_cache: dict[tuple[str, date], float | None] = {}
    results: dict[str, dict] = {}
    for asset_ticker, definition in definitions.items():
        benchmark_ticker = str(definition["ticker"])
        history = histories.get(benchmark_ticker)
        if history is None or history.empty or "Close" not in history:
            results[asset_ticker] = {
                **definition,
                "status": "missing",
                "reason": errors.get(benchmark_ticker, "Keine Benchmark-Kursdaten verfügbar"),
            }
            continue
        index_days = pd.Index(pd.to_datetime(history.index).date)
        available = history.loc[index_days <= observation_day]
        if available.empty:
            results[asset_ticker] = {
                **definition,
                "status": "missing",
                "reason": "Kein Benchmark-Schlusskurs bis zum Beobachtungstag verfügbar",
            }
            continue
        row = available.iloc[-1]
        observed_day = pd.Timestamp(available.index[-1]).date()
        currency = str(definition["currency"])
        fx_key = (currency, observed_day)
        if fx_key not in fx_cache:
            fx_cache[fx_key] = _historic_fx_rate(currency, observed_day, None)
        fx_rate = fx_cache[fx_key]
        price_original = float(row["Close"])
        results[asset_ticker] = {
            **definition,
            "status": "available" if fx_rate is not None else "missing",
            "observed_day": observed_day.isoformat(),
            "price_original": price_original,
            "fx_rate_to_eur": fx_rate,
            "price_eur": price_original * fx_rate if fx_rate is not None else None,
            "reason": None if fx_rate is not None else "Historischer FX-Kurs nicht verfügbar",
        }
    return results


def evaluation_market_data_from_history(
    item: dict,
    data: pd.DataFrame,
    *,
    fx_cache: dict[tuple[str, date], float | None] | None = None,
    fx_loader: Callable[[str, date, float | None], float | None] = _historic_fx_rate,
) -> dict:
    created = pd.Timestamp(item["created_at"]).tz_localize(None)
    due_day = (created + pd.Timedelta(days=int(item["days"]))).date()
    if data.empty or "Close" not in data:
        raise RuntimeError("Keine Kursdaten für die fällige Auswertung verfügbar")
    index_days = pd.Index(pd.to_datetime(data.index).date)
    due_mask = index_days >= due_day
    due_data = data.loc[due_mask]
    if due_data.empty:
        raise RuntimeError("Noch kein Handelsschlusskurs am oder nach dem Fälligkeitsdatum verfügbar")
    actual_row = due_data.iloc[0]
    actual_day = pd.Timestamp(due_data.index[0]).date()
    horizon_data = data.loc[index_days <= actual_day]
    currency = str(item.get("original_currency") or "EUR").upper()
    fx_key = (currency, actual_day)
    if fx_cache is not None and fx_key in fx_cache:
        fx_rate = fx_cache[fx_key]
    else:
        fx_rate = fx_loader(currency, actual_day, item.get("fx_rate_to_eur"))
        if fx_cache is not None:
            fx_cache[fx_key] = fx_rate
    actual_original = float(actual_row["Close"])
    max_original = float(horizon_data["High"].max()) if "High" in horizon_data else actual_original
    min_original = float(horizon_data["Low"].min()) if "Low" in horizon_data else actual_original
    day_gap = (actual_day - due_day).days
    return {
        "actual_price_original": actual_original,
        "actual_price_eur": actual_original * fx_rate if fx_rate is not None else None,
        "max_price_eur": max_original * fx_rate if fx_rate is not None else None,
        "min_price_eur": min_original * fx_rate if fx_rate is not None else None,
        "data_quality": "Gut" if day_gap <= 3 else "Eingeschränkt",
        "actual_day": actual_day.isoformat(),
    }


def default_evaluation_market_data(item: dict) -> dict:
    created = pd.Timestamp(item["created_at"]).tz_localize(None)
    due_day = (created + pd.Timedelta(days=int(item["days"]))).date()
    end_day = min(date.today() + timedelta(days=1), due_day + timedelta(days=8))
    data = _flat_price_data(item["ticker"], created.date(), end_day)
    return evaluation_market_data_from_history(item, data)


def default_evaluation_market_data_batch(
    items: list[dict],
    *,
    as_of: date | None = None,
    batch_size: int = 75,
) -> tuple[dict[tuple[int, str], dict], dict[tuple[int, str], str]]:
    if not items:
        return {}, {}
    valuation_day = as_of or date.today()
    created_days = [pd.Timestamp(item["created_at"]).tz_localize(None).date() for item in items]
    due_days = [
        (pd.Timestamp(item["created_at"]).tz_localize(None) + pd.Timedelta(days=int(item["days"]))).date()
        for item in items
    ]
    start_day = min(created_days)
    end_day = min(valuation_day + timedelta(days=1), max(due_days) + timedelta(days=8))
    benchmark_tickers = [
        str((item.get("market_benchmark_snapshot") or {}).get("ticker") or "")
        for item in items
        if (item.get("market_benchmark_snapshot") or {}).get("status") == "available"
    ]
    histories, ticker_errors = _batch_price_histories(
        [str(item["ticker"]) for item in items] + benchmark_tickers,
        start_day,
        end_day,
        batch_size=batch_size,
    )
    results: dict[tuple[int, str], dict] = {}
    errors: dict[tuple[int, str], str] = {}
    fx_cache: dict[tuple[str, date], float | None] = {}
    for item in items:
        key = (int(item["forecast_id"]), str(item["horizon"]))
        ticker = str(item["ticker"]).upper()
        data = histories.get(ticker)
        if data is None:
            errors[key] = ticker_errors.get(
                ticker, "Keine Kursdaten für die fällige Auswertung verfügbar"
            )
            continue
        try:
            market_data = evaluation_market_data_from_history(
                item,
                data,
                fx_cache=fx_cache,
            )
            benchmark = item.get("market_benchmark_snapshot") or {}
            benchmark_ticker = str(benchmark.get("ticker") or "").upper()
            benchmark_history = histories.get(benchmark_ticker)
            benchmark_entry_eur = benchmark.get("price_eur")
            if (
                benchmark.get("status") == "available"
                and benchmark_history is not None
                and benchmark_entry_eur is not None
                and float(benchmark_entry_eur) > 0
            ):
                try:
                    benchmark_market_data = evaluation_market_data_from_history(
                        {
                            "created_at": item["created_at"],
                            "days": item["days"],
                            "original_currency": benchmark.get("currency"),
                            "fx_rate_to_eur": benchmark.get("fx_rate_to_eur"),
                        },
                        benchmark_history,
                        fx_cache=fx_cache,
                    )
                    benchmark_actual_eur = benchmark_market_data.get("actual_price_eur")
                    if benchmark_actual_eur is not None:
                        market_data["market_benchmark_ticker"] = benchmark_ticker
                        market_data["market_benchmark_return_pct"] = (
                            (float(benchmark_actual_eur) - float(benchmark_entry_eur))
                            / float(benchmark_entry_eur)
                            * 100
                        )
                except Exception as exc:
                    market_data["market_benchmark_error"] = safe_error(exc)
            results[key] = market_data
        except Exception as exc:
            errors[key] = safe_error(exc)
    return results, errors


def build_evaluation(item: dict, market_data: dict) -> dict:
    original_entry = item.get("price_eur")
    actual = market_data.get("actual_price_eur")
    if original_entry is None or actual is None or float(original_entry) <= 0:
        return_pct = None
        direction_result = None
    else:
        return_pct = (float(actual) - float(original_entry)) / float(original_entry) * 100
        direction_result = baseline_direction_hit(item.get("predicted_direction"), return_pct)

    low = item.get("expected_low_eur")
    high = item.get("expected_high_eur")
    range_hit = int(float(low) <= float(actual) <= float(high)) if None not in {low, high, actual} else None
    midpoint = (float(low) + float(high)) / 2 if low is not None and high is not None else None
    deviation = ((float(actual) - midpoint) / midpoint * 100) if midpoint and actual is not None else None
    target = item.get("target_eur")
    risk = item.get("risk_eur")
    maximum = market_data.get("max_price_eur")
    minimum = market_data.get("min_price_eur")
    if original_entry is None or float(original_entry) <= 0:
        max_return_pct = min_return_pct = None
    else:
        max_return_pct = (
            (float(maximum) - float(original_entry)) / float(original_entry) * 100
            if maximum is not None
            else None
        )
        min_return_pct = (
            (float(minimum) - float(original_entry)) / float(original_entry) * 100
            if minimum is not None
            else None
        )
    direction = str(item.get("predicted_direction") or "")
    simple_trend = item.get("simple_trend_baseline") or {}
    simple_trend_hit = (
        baseline_direction_hit(simple_trend.get("predicted_direction"), return_pct)
        if simple_trend.get("status") == "available"
        else None
    )
    benchmark_return_pct = market_data.get("market_benchmark_return_pct")
    excess_return_pct = (
        float(return_pct) - float(benchmark_return_pct)
        if return_pct is not None and benchmark_return_pct is not None
        else None
    )
    if target is None or maximum is None or minimum is None:
        target_hit = None
    elif direction == "Fallend":
        target_hit = int(float(minimum) <= float(target))
    else:
        target_hit = int(float(maximum) >= float(target))
    if risk is None or maximum is None or minimum is None:
        risk_hit = None
    elif direction == "Fallend":
        risk_hit = int(float(maximum) >= float(risk))
    else:
        risk_hit = int(float(minimum) <= float(risk))
    return {
        "forecast_id": item["forecast_id"],
        "horizon": item["horizon"],
        "evaluated_at": datetime.now().astimezone().isoformat(),
        "actual_price_original": market_data.get("actual_price_original"),
        "actual_price_eur": actual,
        "actual_return_pct": round(return_pct, 4) if return_pct is not None else None,
        "actual_day": market_data.get("actual_day"),
        "max_return_pct": round(max_return_pct, 4) if max_return_pct is not None else None,
        "min_return_pct": round(min_return_pct, 4) if min_return_pct is not None else None,
        "always_up_hit": int(return_pct > 0) if return_pct is not None else None,
        "no_change_hit": int(abs(return_pct) <= 3) if return_pct is not None else None,
        "simple_trend_hit": simple_trend_hit,
        "market_benchmark_ticker": market_data.get("market_benchmark_ticker"),
        "market_benchmark_return_pct": (
            round(float(benchmark_return_pct), 4) if benchmark_return_pct is not None else None
        ),
        "excess_return_pct": (
            round(float(excess_return_pct), 4) if excess_return_pct is not None else None
        ),
        "direction_hit": direction_result,
        "range_hit": range_hit,
        "deviation_pct": round(deviation, 4) if deviation is not None else None,
        "target_hit": target_hit,
        "risk_hit": risk_hit,
        "data_quality": market_data.get("data_quality") or "Unbekannt",
        "note": "Automatische Auswertung; Richtungstreffer ist die zentrale Erfolgsdefinition.",
    }


def evaluate_due_forecasts(
    database_path: Path = DEFAULT_DATABASE_PATH,
    as_of: date | None = None,
    limit: int = 1000,
    market_data_loader: Callable[[dict], dict] = default_evaluation_market_data,
    logger: logging.Logger | None = None,
) -> dict:
    due = pending_evaluations(as_of, database_path, limit)
    prepared: dict[tuple[int, str], dict] | None = None
    preparation_errors: dict[tuple[int, str], str] = {}
    if market_data_loader is default_evaluation_market_data and due:
        prepared, preparation_errors = default_evaluation_market_data_batch(due, as_of=as_of)

    evaluated = failed = rate_limit_failures = 0
    for item in due:
        try:
            key = (int(item["forecast_id"]), str(item["horizon"]))
            if prepared is None:
                market_data = market_data_loader(item)
            elif key in prepared:
                market_data = prepared[key]
            else:
                raise RuntimeError(
                    preparation_errors.get(
                        key, "Keine Kursdaten für die fällige Auswertung verfügbar"
                    )
                )
            evaluation = build_evaluation(item, market_data)
            if record_evaluation(evaluation, database_path):
                evaluated += 1
        except Exception as exc:
            failed += 1
            rate_limit_failures += int(is_rate_limit_error(exc))
            try:
                record_evaluation_failure(
                    int(item["forecast_id"]),
                    str(item["horizon"]),
                    str(exc),
                    database_path,
                )
            except Exception as persistence_exc:
                if logger:
                    logger.warning(
                        "Auswertungsfehler konnte nicht gespeichert werden | ticker=%s | horizon=%s | error=%s",
                        item.get("ticker"),
                        item.get("horizon"),
                        safe_error(persistence_exc),
                    )
            if logger:
                logger.warning(
                    "Auswertung fehlgeschlagen | ticker=%s | horizon=%s | error=%s",
                    item.get("ticker"),
                    item.get("horizon"),
                    safe_error(exc),
                )
    return {
        "due": len(due),
        "evaluated": evaluated,
        "failed": failed,
        "rate_limit_failures": rate_limit_failures,
    }


def planned_collection(
    settings: dict,
    database_path: Path,
    process_day: date,
) -> tuple[list[dict], dict | None, str]:
    weekly_universe_value = str(settings.get("weekly_universe_path") or "").strip()
    if not weekly_universe_value:
        universe_path = project_path(settings["universe_path"])
        return load_universe(universe_path), None, str(universe_path)

    reference_value = str(settings.get("reference_universe_path") or "").strip()
    reference_path = project_path(reference_value or settings["universe_path"])
    weekly_universe_path = project_path(weekly_universe_value)
    plan = build_weekly_cohort_plan(
        weekly_universe_path,
        reference_path,
        minimum_active_assets=int(settings.get("weekly_minimum_assets") or 1500),
    )
    existing_sampling = sampling_for_run_date(process_day.isoformat(), database_path)
    if existing_sampling is not None:
        weekday = existing_sampling.get("cohort_weekday")
        assets = list(plan["cohorts"].get(int(weekday), [])) if weekday is not None else []
        return assets, existing_sampling, str(weekly_universe_path)

    iso_year, iso_week, _ = process_day.isocalendar()
    completed = completed_sampling_cohort_ids(f"{iso_year}-W{iso_week:02d}", database_path)
    start_value = str(settings.get("weekly_schedule_start_date") or "").strip()
    schedule_start = date.fromisoformat(start_value) if start_value else None
    selection = select_weekly_cohort(
        plan,
        process_day,
        completed_cohort_ids=completed,
        schedule_start_date=schedule_start,
    )
    return selection["assets"], selection["sampling"], str(weekly_universe_path)


def run_daily_process(
    settings_path: Path = DEFAULT_SETTINGS_PATH,
    run_date: str | None = None,
    limit: int | None = None,
    force: bool = False,
    no_delay: bool = False,
) -> dict:
    process_started = time.monotonic()
    settings = load_settings(settings_path)
    log_path = project_path(settings["log_path"])
    logger = configure_logger(log_path)
    run_lock = ForecastRunLock(lock_path_for_database(project_path(settings["database_path"])))
    try:
        database_path = project_path(settings["database_path"])
        run_lock.acquire()
        logger.info("Exklusive Prozesssperre aktiv | lock=%s", run_lock.path)
        try:
            process_day = date.fromisoformat(run_date) if run_date else date.today()
        except ValueError as exc:
            raise ValueError("Das Laufdatum muss das Format JJJJ-MM-TT verwenden.") from exc
        configured_weekly = str(settings.get("weekly_universe_path") or "").strip()
        configured_universe = configured_weekly or str(settings["universe_path"])
        database_bytes_before = database_path.stat().st_size if database_path.exists() else 0
        logger.info(
            "Startvorprüfung | settings=%s | universe=%s | database=%s | logic_version=%s",
            Path(settings_path),
            project_path(configured_universe),
            database_path,
            settings["logic_version"],
        )
        measurement_audit = measurement_contract_audit(database_path)
        logger.info(
            "Measurement contract audit | status=%s | valid=%s | legacy=%s | invalid=%s",
            measurement_audit["status"],
            measurement_audit["valid_records"],
            measurement_audit["legacy_records"],
            measurement_audit["invalid_records"],
        )
        if measurement_audit["status"] != "ok":
            raise RuntimeError(
                "Die Point-in-Time-Messvertraege sind nicht integer; "
                "der Lauf wurde vor Auswertung und neuen Prognosen gestoppt."
            )
        universe, sampling, universe_description = planned_collection(
            settings,
            database_path,
            process_day,
        )
        if limit is not None:
            universe = universe[: max(int(limit), 0)]
            if sampling is not None:
                sampling = {**sampling, "controlled_limit": int(limit), "scheduled_assets": len(universe)}
        logger.info(
            "Täglicher Prognoseprozess gestartet | assets=%s | mode=%s | cohort=%s",
            len(universe),
            (sampling or {}).get("mode", "legacy_daily"),
            (sampling or {}).get("cohort_id"),
        )
        evaluation = evaluate_due_forecasts(
            database_path,
            as_of=process_day,
            limit=int(settings["evaluation_limit"]),
            logger=logger,
        )
        logger.info(
            "Fällige Auswertung beendet | due=%s | evaluated=%s | failed=%s | rate_limits=%s",
            evaluation["due"],
            evaluation["evaluated"],
            evaluation["failed"],
            evaluation["rate_limit_failures"],
        )
        benchmark_snapshots = (
            prepare_market_benchmark_snapshots(universe, process_day) if universe else {}
        )
        if benchmark_snapshots:
            available_benchmarks = sum(
                item.get("status") == "available" for item in benchmark_snapshots.values()
            )
            logger.info(
                "Marktbenchmark-Snapshots vorbereitet | available=%s | missing=%s",
                available_benchmarks,
                len(benchmark_snapshots) - available_benchmarks,
            )
            if universe and available_benchmarks == 0:
                raise RuntimeError(
                    "Keine globale Yahoo-Marktreferenz verfügbar; die Neuprognose wurde "
                    "vor dem ersten Asset sicher pausiert und wird später nachgeholt."
                )
        collection = collect_forecasts(
            universe,
            database_path=database_path,
            run_date=process_day.isoformat(),
            logic_version=str(settings["logic_version"]),
            max_retries=int(settings["max_retries"]),
            request_delay_seconds=0.0 if no_delay else float(settings["request_delay_seconds"]),
            batch_size=int(settings["batch_size"]),
            batch_pause_seconds=0.0 if no_delay else float(settings["batch_pause_seconds"]),
            force=force,
            logger=logger,
            sampling=sampling,
            market_benchmark_snapshots=benchmark_snapshots,
        )
        calibration_path = project_path(settings["calibration_path"])
        try:
            calibration_profile = write_calibration_profile(database_path, calibration_path)
            calibration = {
                "status": "ok",
                "path": str(calibration_path),
                "profile_version": calibration_profile["profile_version"],
                "evaluated_cases": calibration_profile["overall"]["evaluated_cases"],
                "manual_review_suggestions": len(calibration_profile["manual_review_suggestions"]),
                "data_fingerprint": calibration_profile["data_fingerprint"],
                "production_rules_changed": False,
            }
            logger.info(
                "Kalibrierungsprofil aktualisiert | cases=%s | suggestions=%s | fingerprint=%s",
                calibration["evaluated_cases"],
                calibration["manual_review_suggestions"],
                str(calibration["data_fingerprint"])[:12],
            )
        except Exception as exc:
            calibration = {
                "status": "failed",
                "path": str(calibration_path),
                "error": safe_error(exc),
                "production_rules_changed": False,
            }
            logger.warning("Kalibrierungsprofil fehlgeschlagen | error=%s", safe_error(exc))
        maintenance = maintain_database(database_path)
        operations = operational_run_metrics(
            collection,
            time.monotonic() - process_started,
            database_bytes_before,
            maintenance,
        )
        operations["rate_limit_failures"] += int(evaluation.get("rate_limit_failures") or 0)
        if collection["status"] != "skipped_same_day":
            record_run_operations(int(collection["run_id"]), operations, database_path)
        weekly_report = None
        weekly_universe_value = str(settings.get("weekly_universe_path") or "").strip()
        if weekly_universe_value:
            reference_value = str(settings.get("reference_universe_path") or "").strip()
            report_plan = build_weekly_cohort_plan(
                project_path(weekly_universe_value),
                project_path(reference_value or settings["universe_path"]),
                minimum_active_assets=int(settings.get("weekly_minimum_assets") or 1500),
            )
            start_value = str(settings.get("weekly_schedule_start_date") or "").strip()
            weekly_report = write_weekly_report(
                report_plan,
                database_path,
                project_path(settings["weekly_report_directory"]),
                process_day,
                schedule_start_date=date.fromisoformat(start_value) if start_value else None,
            )
            logger.info(
                "Wochenbericht aktualisiert | week=%s | completed_cohorts=%s/%s | "
                "coverage_pct=%s | overdue=%s",
                weekly_report["iso_week"],
                weekly_report["coverage"]["completed_cohorts"],
                weekly_report["coverage"]["planned_cohorts"],
                weekly_report["coverage"]["successful_asset_coverage_pct"],
                len(weekly_report["coverage"]["overdue_cohorts"]),
            )
        logger.info(
            "Täglicher Prognoselauf beendet | status=%s | succeeded=%s | failed=%s | "
            "rate_limits=%s | evaluated=%s | seconds=%s | failure_rate_pct=%s | db_growth_bytes=%s",
            collection["status"],
            collection["succeeded"],
            collection["failed"],
            operations["rate_limit_failures"],
            evaluation["evaluated"],
            operations["elapsed_seconds"],
            operations["failure_rate_pct"],
            operations["database_growth_bytes"],
        )
        return {
            "database_path": str(database_path),
            "universe_count": len(universe),
            "sampling": sampling,
            "collection": collection,
            "evaluation": evaluation,
            "calibration": calibration,
            "operations": operations,
            "maintenance": maintenance,
            "weekly_report": weekly_report,
            "measurement_contract_audit": measurement_audit,
        }
    except BaseException as exc:
        logger.error("Täglicher Prognoselauf vor Abschluss beendet | error=%s", safe_error(exc))
        raise
    finally:
        run_lock.release()
        close_logger(logger)
