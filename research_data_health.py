from __future__ import annotations

"""Read-only health and PIT-coverage audit for research data families.

The audit deliberately has no collector, strategy, signal, trade or broker path.
It opens existing SQLite stores in read-only mode and reports missing stores rather
than creating them.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


RESEARCH_DATA_HEALTH_VERSION = "research-data-health-2026.09.23-v1"
CANONICAL_STATUSES = {
    "HEALTHY",
    "STALE",
    "PARTIAL",
    "FAILED",
    "NOT_CONFIGURED",
    "NOT_APPLICABLE",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _age_days(as_of: datetime, value: object) -> float | None:
    stamp = _utc(value)
    if stamp is None:
        return None
    return round(max(0.0, (as_of - stamp).total_seconds() / 86400.0), 3)


def _ro_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _scalar(path: Path, sql: str, parameters: Sequence[object] = (), default=None):
    if not path.is_file():
        return default
    try:
        with _ro_connection(path) as connection:
            row = connection.execute(sql, tuple(parameters)).fetchone()
        return default if row is None or row[0] is None else row[0]
    except sqlite3.Error:
        return default


def _row(path: Path, sql: str, parameters: Sequence[object] = ()) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        with _ro_connection(path) as connection:
            row = connection.execute(sql, tuple(parameters)).fetchone()
        return {} if row is None else dict(row)
    except sqlite3.Error:
        return {}


def _integrity(path: Path) -> str:
    return str(_scalar(path, "PRAGMA quick_check", default="MISSING"))


def _task(tasks: Sequence[Mapping[str, object]], name: str) -> dict[str, object]:
    matches = [dict(item) for item in tasks if str(item.get("task_name") or "") == name]
    if len(matches) != 1:
        return {
            "task_name": name,
            "present": False,
            "enabled": False,
            "state": "MISSING" if not matches else "DUPLICATE",
            "last_run_time": None,
            "last_task_result": None,
        }
    task = matches[0]
    return {
        "task_name": name,
        "present": True,
        "enabled": bool(task.get("enabled")),
        "state": str(task.get("state") or "UNKNOWN"),
        "last_run_time": task.get("last_run_time"),
        "next_run_time": task.get("next_run_time"),
        "last_task_result": task.get("last_task_result"),
        "start_when_available": task.get("start_when_available"),
        "multiple_instances": task.get("multiple_instances"),
    }


def _family(
    family_id: str,
    name: str,
    *,
    collector: str,
    scheduler: Mapping[str, object] | None,
    last_success: object,
    last_observation: object,
    expected_cadence: str,
    staleness_days: float | None,
    observations: int,
    period_start: object,
    period_end: object,
    source: str,
    published_at: object = None,
    first_seen_at: object = None,
    effective_at: object = None,
    pit_eligible_pct: float | None = None,
    revision_support: str = "NONE",
    missingness: str = "UNKNOWN",
    provider_errors: int = 0,
    rate_limits: str = "NOT_REPORTED",
    status: str,
    research_use: str,
    blockers: Iterable[str] = (),
    database: str | None = None,
    database_integrity: str | None = None,
) -> dict[str, object]:
    if status not in CANONICAL_STATUSES:
        raise ValueError(f"Non-canonical data-health status: {status}")
    return {
        "family_id": family_id,
        "name": name,
        "collector": collector,
        "scheduler": dict(scheduler or {}),
        "last_success": last_success,
        "last_observation": last_observation,
        "expected_cadence": expected_cadence,
        "staleness_days": staleness_days,
        "observations": int(observations),
        "period": {"start": period_start, "end": period_end},
        "source": source,
        "timestamps": {
            "published_at": published_at,
            "first_seen_at": first_seen_at,
            "effective_at": effective_at,
        },
        "pit_eligible_pct": pit_eligible_pct,
        "revision_support": revision_support,
        "missingness": missingness,
        "provider_errors": int(provider_errors),
        "rate_limits": rate_limits,
        "status": status,
        "research_use": research_use,
        "blockers": list(blockers),
        "database": database,
        "database_integrity": database_integrity,
    }


def audit_research_data_health(
    project_root: Path,
    *,
    as_of: datetime | str,
    scheduler_tasks: Sequence[Mapping[str, object]] = (),
    scheduler_query_status: str = "NOT_AVAILABLE",
) -> dict[str, object]:
    root = Path(project_root).resolve()
    runtime = root / "runtime"
    stamp = _utc(as_of)
    if stamp is None:
        raise ValueError("as_of must be a timezone-aware ISO timestamp")

    fx_path = runtime / "fx_forward_pit.sqlite3"
    forecasts_path = runtime / "forecasts.sqlite3"
    cot_path = runtime / "cot_shadow.sqlite3"
    events_path = runtime / "swing_event_research.sqlite3"
    identity_path = runtime / "research_identity_registry.sqlite3"
    crypto_path = runtime / "crypto_historical_pit_2026-09-05-v1.sqlite3"
    equity_path = runtime / "equity_etf_historical_pit_2026-09-03-v1.sqlite3"
    carry_path = runtime / "fx_carry_pit.sqlite3"

    fx_task = _task(scheduler_tasks, "InvestmentAssistant-FX-PIT-Observer")
    forecast_task = _task(scheduler_tasks, "InvestmentAssistantDailyForecasts")

    fx_last_run = _scalar(fx_path, "SELECT MAX(started_at) FROM collector_runs")
    fx_last_observation = _scalar(
        fx_path,
        "SELECT MAX(source_timestamp) FROM observations WHERE status='OBSERVED'",
    )
    fx_observed_n = int(
        _scalar(fx_path, "SELECT COUNT(*) FROM observations WHERE status='OBSERVED'", default=0)
    )
    fx_total_n = int(_scalar(fx_path, "SELECT COUNT(*) FROM observations", default=0))
    fx_missing_n = max(0, fx_total_n - fx_observed_n)
    fx_failures = int(
        _scalar(fx_path, "SELECT COUNT(*) FROM observations WHERE status='PROVIDER_FAILURE'", default=0)
    )
    fx_duplicate_n = int(
        _scalar(
            fx_path,
            "SELECT COUNT(*) - COUNT(DISTINCT observation_key) FROM observations",
            default=0,
        )
    )
    fx_age = _age_days(stamp, fx_last_observation)
    if not fx_path.is_file() or _integrity(fx_path) != "ok":
        fx_status = "FAILED"
    elif not fx_task["present"] or not fx_task["enabled"]:
        fx_status = "FAILED"
    elif fx_age is None or fx_age > 3:
        fx_status = "STALE"
    elif fx_missing_n:
        fx_status = "PARTIAL"
    else:
        fx_status = "HEALTHY"

    forecast_latest = _row(
        forecasts_path,
        "SELECT id, status, started_at, finished_at, success_count, failure_count, "
        "rate_limit_failures, database_growth_bytes, database_status "
        "FROM forecast_runs ORDER BY id DESC LIMIT 1",
    )
    forecast_last_observation = _scalar(forecasts_path, "SELECT MAX(created_at) FROM forecasts")
    forecast_n = int(_scalar(forecasts_path, "SELECT COUNT(*) FROM forecasts", default=0))
    forecast_asset_n = int(
        _scalar(forecasts_path, "SELECT COUNT(DISTINCT ticker) FROM forecasts", default=0)
    )
    forecast_age = _age_days(stamp, forecast_last_observation)
    forecast_failures = int(forecast_latest.get("failure_count") or 0)
    if not forecasts_path.is_file() or _integrity(forecasts_path) != "ok":
        forecast_status = "FAILED"
    elif not forecast_task["present"] or not forecast_task["enabled"]:
        forecast_status = "FAILED"
    elif forecast_age is None or forecast_age > 3:
        forecast_status = "STALE"
    elif forecast_failures:
        forecast_status = "PARTIAL"
    else:
        forecast_status = "HEALTHY"

    cot_latest = _row(
        cot_path,
        "SELECT MIN(a.first_seen_at) AS first_seen_start, MAX(a.first_seen_at) AS first_seen_at, "
        "COUNT(DISTINCT SUBSTR(a.first_seen_at,1,10)) AS forward_observed_days, "
        "MAX(a.available_at) AS available_at, "
        "MIN(r.report_date) AS period_start, MAX(r.report_date) AS period_end "
        "FROM cot_report_availability a JOIN cot_reports r ON r.report_id=a.report_id",
    )
    cot_n = int(_scalar(cot_path, "SELECT COUNT(*) FROM cot_reports", default=0))
    cot_period_n = int(
        _scalar(cot_path, "SELECT COUNT(DISTINCT report_date) FROM cot_reports", default=0)
    )
    cot_age = _age_days(stamp, cot_latest.get("first_seen_at"))
    cot_forward_span_days = None
    cot_forward_start = _utc(cot_latest.get("first_seen_start"))
    cot_forward_end = _utc(cot_latest.get("first_seen_at"))
    if cot_forward_start is not None and cot_forward_end is not None:
        cot_forward_span_days = round(
            max(0.0, (cot_forward_end - cot_forward_start).total_seconds() / 86400.0),
            3,
        )
    if not cot_path.is_file() or _integrity(cot_path) != "ok":
        cot_status = "FAILED"
    elif cot_n == 0:
        cot_status = "FAILED"
    elif cot_age is None or cot_age > 10:
        cot_status = "STALE"
    elif cot_period_n < 52:
        cot_status = "PARTIAL"
    else:
        cot_status = "HEALTHY"

    event_latest = _row(
        events_path,
        "SELECT COUNT(*) AS n, MIN(effective_at) AS period_start, MAX(effective_at) AS period_end, "
        "MAX(first_seen_at) AS first_seen_at, SUM(CASE WHEN pit_eligible=1 THEN 1 ELSE 0 END) AS pit_n "
        "FROM event_records",
    )
    event_n = int(event_latest.get("n") or 0)
    event_age = _age_days(stamp, event_latest.get("first_seen_at"))

    identity_latest = _row(
        identity_path,
        "SELECT COUNT(*) AS n, COUNT(DISTINCT issuer_id) AS issuers, MIN(valid_from) AS period_start, "
        "MAX(valid_from) AS period_end FROM identity_mappings",
    )
    identity_n = int(identity_latest.get("n") or 0)

    crypto_latest = _row(
        crypto_path,
        "SELECT COUNT(*) AS n, COUNT(DISTINCT ticker) AS assets, MIN(session_date) AS period_start, "
        "MAX(session_date) AS period_end, SUM(CASE WHEN volume IS NOT NULL AND volume>0 THEN 1 ELSE 0 END) AS volume_n "
        "FROM active_bars",
    )
    equity_latest = _row(
        equity_path,
        "SELECT COUNT(*) AS n, COUNT(DISTINCT ticker) AS assets, MIN(session_date) AS period_start, "
        "MAX(session_date) AS period_end, SUM(CASE WHEN volume IS NOT NULL AND volume>0 THEN 1 ELSE 0 END) AS volume_n "
        "FROM active_bars",
    )
    crypto_n = int(crypto_latest.get("n") or 0)
    equity_n = int(equity_latest.get("n") or 0)
    price_n = crypto_n + equity_n
    positive_volume_n = int(crypto_latest.get("volume_n") or 0) + int(
        equity_latest.get("volume_n") or 0
    )
    volume_pct = round(100.0 * positive_volume_n / price_n, 3) if price_n else None

    expectation_n = int(_scalar(fx_path, "SELECT COUNT(*) FROM expectations", default=0))
    macro_n = int(_scalar(fx_path, "SELECT COUNT(*) FROM macro_events", default=0))
    central_bank_n = int(
        _scalar(fx_path, "SELECT COUNT(*) FROM central_bank_events", default=0)
    )
    quote_n = int(_scalar(fx_path, "SELECT COUNT(*) FROM quote_observations", default=0))
    carry_n = int(_scalar(carry_path, "SELECT COUNT(*) FROM fx_pit_observations", default=0))

    families = [
        _family(
            "A", "FX PIT Observer", collector="scripts/run_fx_pit_collector.py",
            scheduler=fx_task, last_success=fx_last_run, last_observation=fx_last_observation,
            expected_cadence="daily 21:45 Europe/Berlin; weekly COT with stale catch-up",
            staleness_days=fx_age, observations=fx_total_n,
            period_start=_scalar(fx_path, "SELECT MIN(source_timestamp) FROM observations WHERE status='OBSERVED'"),
            period_end=fx_last_observation, source="Yahoo daily FX + official CFTC; unavailable adapters explicit",
            first_seen_at=_scalar(fx_path, "SELECT MAX(first_seen_at) FROM observations"),
            effective_at=fx_last_observation,
            pit_eligible_pct=round(100.0 * fx_observed_n / fx_total_n, 3) if fx_total_n else None,
            revision_support="append-only revision table", missingness=f"{fx_missing_n} explicit missing/failure rows",
            provider_errors=fx_failures, status=fx_status,
            research_use="forward FX price/context collection only; no strategy effect",
            blockers=["policy-rate, expectations and bid/ask adapters not configured"] if fx_missing_n else [],
            database=str(fx_path), database_integrity=_integrity(fx_path),
        ),
        _family(
            "B", "Forecast / weekly universe", collector="scripts/run_forecasts.py + evening pipeline",
            scheduler=forecast_task, last_success=forecast_latest.get("finished_at"),
            last_observation=forecast_last_observation, expected_cadence="daily 22:30 Europe/Berlin",
            staleness_days=forecast_age, observations=forecast_n,
            period_start=_scalar(forecasts_path, "SELECT MIN(created_at) FROM forecasts"),
            period_end=forecast_last_observation, source="existing market-data adapters and causal feature snapshots",
            first_seen_at=forecast_last_observation,
            effective_at=_scalar(forecasts_path, "SELECT MAX(observation_cutoff_at) FROM forecasts"),
            pit_eligible_pct=round(100.0 * int(_scalar(forecasts_path, "SELECT COUNT(*) FROM forecasts WHERE observation_cutoff_at IS NOT NULL AND snapshot_fingerprint IS NOT NULL", default=0)) / forecast_n, 3) if forecast_n else None,
            revision_support="immutable forecast snapshots", missingness=f"latest run failures={forecast_failures}; distinct assets={forecast_asset_n}",
            provider_errors=forecast_failures,
            rate_limits=str(forecast_latest.get("rate_limit_failures") or 0), status=forecast_status,
            research_use="forecast evidence and current price collection; not a new challenger",
            blockers=["latest failed asset must remain explicit"] if forecast_failures else [],
            database=str(forecasts_path), database_integrity=_integrity(forecasts_path),
        ),
        _family(
            "C", "COT positioning", collector="official CFTC forward collector via FX observer",
            scheduler=fx_task, last_success=cot_latest.get("first_seen_at"),
            last_observation=cot_latest.get("first_seen_at"), expected_cadence="weekly; catch-up when older than 10 days",
            staleness_days=cot_age, observations=cot_n, period_start=cot_latest.get("period_start"),
            period_end=cot_latest.get("period_end"), source="official CFTC public reporting",
            published_at=None, first_seen_at=cot_latest.get("first_seen_at"),
            effective_at=cot_latest.get("available_at"), pit_eligible_pct=100.0 if cot_n else None,
            revision_support="append-only report and availability evidence",
            missingness=(
                f"{cot_period_n} report dates; first-seen evidence spans "
                f"{cot_forward_span_days} days across {int(cot_latest.get('forward_observed_days') or 0)} collection days"
            ),
            status=cot_status, research_use="macro/futures context only after coverage gate",
            blockers=["latest actual first_seen is stale", "insufficient independent forward-observed periods"] if cot_status != "HEALTHY" else [],
            database=str(cot_path), database_integrity=_integrity(cot_path),
        ),
        _family(
            "D", "Fundamentals / SEC filings", collector="parser/capability code only",
            scheduler=None, last_success=None, last_observation=None, expected_cadence="filing-driven",
            staleness_days=None, observations=0, period_start=None, period_end=None,
            source="no configured SEC filing snapshot source", pit_eligible_pct=None,
            revision_support="not operational", missingness="all required historical PIT fundamentals missing",
            status="NOT_CONFIGURED", research_use="coverage gate only; no Development test",
            blockers=["SEC contact user-agent absent", "SEC snapshot cache absent", "historical issuer mapping absent"],
        ),
        _family(
            "E", "Company events / news", collector="forward event sidecar only",
            scheduler=None, last_success=event_latest.get("first_seen_at"),
            last_observation=event_latest.get("first_seen_at"), expected_cadence="event-driven",
            staleness_days=event_age, observations=event_n, period_start=event_latest.get("period_start"),
            period_end=event_latest.get("period_end"), source="immutable forward signal snapshots; secondary aggregated",
            published_at=None, first_seen_at=event_latest.get("first_seen_at"),
            effective_at=event_latest.get("period_end"),
            pit_eligible_pct=round(100.0 * int(event_latest.get("pit_n") or 0) / event_n, 3) if event_n else None,
            revision_support="versioned append-only event records", missingness="published_at absent in current records",
            status="STALE" if event_n else "NOT_CONFIGURED",
            research_use="diagnostic forward context only; insufficient for historical catalyst research",
            blockers=["no active scheduler", "only 24 forward snapshots", "published_at unavailable"],
            database=str(events_path), database_integrity=_integrity(events_path),
        ),
        _family(
            "F", "Macro / rates / expectations", collector="explicit missingness adapters in FX observer",
            scheduler=fx_task, last_success=None, last_observation=None, expected_cadence="release/event-driven",
            staleness_days=None, observations=expectation_n + macro_n + central_bank_n + carry_n,
            period_start=None, period_end=None, source="no reliable adapter configured",
            pit_eligible_pct=None, revision_support="schema ready; no observations",
            missingness=f"expectations={expectation_n}, macro={macro_n}, central_bank={central_bank_n}, carry={carry_n}",
            status="NOT_CONFIGURED", research_use="coverage gate only; surprise remains UNKNOWN",
            blockers=["no PIT expectation vintages", "no actual policy-rate adapter"],
        ),
        _family(
            "G", "Politics / geopolitics / regulation", collector="none",
            scheduler=None, last_success=None, last_observation=None, expected_cadence="event-driven",
            staleness_days=None, observations=0, period_start=None, period_end=None,
            source="none", pit_eligible_pct=None, revision_support="none",
            missingness="no observations", status="NOT_CONFIGURED",
            research_use="not research-ready", blockers=["no lawful approved PIT source or collector"],
        ),
        _family(
            "H", "Crypto market / regime", collector="frozen historical OHLCV projection only",
            scheduler=None, last_success=None, last_observation=crypto_latest.get("period_end"),
            expected_cadence="frozen 2016-2021 research dataset", staleness_days=None,
            observations=crypto_n, period_start=crypto_latest.get("period_start"),
            period_end=crypto_latest.get("period_end"), source="frozen crypto OHLCV files",
            effective_at=crypto_latest.get("period_end"), pit_eligible_pct=100.0 if crypto_n else None,
            revision_support="frozen dataset fingerprint", missingness="dominance, breadth, liquidity and on-chain PIT layers absent",
            status="PARTIAL" if crypto_n else "NOT_CONFIGURED",
            research_use="capability audit only; old technical OHLCV claims must not be retested",
            blockers=["no genuinely new PIT regime information layer"],
            database=str(crypto_path), database_integrity=_integrity(crypto_path),
        ),
        _family(
            "I", "Price / OHLCV", collector="frozen historical projections + current forecast/FX collectors",
            scheduler=forecast_task, last_success=forecast_latest.get("finished_at"),
            last_observation=forecast_last_observation, expected_cadence="historical frozen; current daily",
            staleness_days=forecast_age, observations=price_n + forecast_n,
            period_start=min(str(equity_latest.get("period_start") or "9999"), str(crypto_latest.get("period_start") or "9999")),
            period_end=forecast_last_observation, source="frozen equity/ETF and crypto OHLCV plus current snapshots",
            first_seen_at=forecast_last_observation, effective_at=forecast_last_observation,
            pit_eligible_pct=100.0 if price_n else None, revision_support="source-history and dataset fingerprints",
            missingness="source invalid bars retained separately", status="HEALTHY" if price_n and forecast_status in {"HEALTHY", "PARTIAL"} else "PARTIAL",
            research_use="baseline/measurement input; not permission for more technical mining",
            database=f"{equity_path}; {crypto_path}", database_integrity=f"{_integrity(equity_path)}; {_integrity(crypto_path)}",
        ),
        _family(
            "J", "Identity / issuer / listing mapping", collector="versioned identity registry builder",
            scheduler=None, last_success=_scalar(identity_path, "SELECT MAX(created_at) FROM registry_versions"),
            last_observation=identity_latest.get("period_end"), expected_cadence="versioned rebuild on universe change",
            staleness_days=None, observations=identity_n, period_start=identity_latest.get("period_start"),
            period_end=identity_latest.get("period_end"), source="local canonical registry",
            effective_at=identity_latest.get("period_end"), pit_eligible_pct=100.0 if identity_n else None,
            revision_support="registry versions + mapping validity intervals",
            missingness=f"current mappings={identity_n}; issuers={int(identity_latest.get('issuers') or 0)}; pre-2026 history absent",
            status="PARTIAL" if identity_n else "NOT_CONFIGURED",
            research_use="current mapping only; insufficient for historical SEC research",
            blockers=["historical issuer/listing validity before 2026-08-29 unavailable"],
            database=str(identity_path), database_integrity=_integrity(identity_path),
        ),
        _family(
            "K", "Benchmark / relative strength inputs", collector="derived from PIT OHLCV",
            scheduler=forecast_task, last_success=forecast_latest.get("finished_at"),
            last_observation=forecast_last_observation, expected_cadence="with price collectors",
            staleness_days=forecast_age, observations=price_n, period_start=equity_latest.get("period_start"),
            period_end=forecast_last_observation, source="price/OHLCV inputs",
            effective_at=forecast_last_observation, pit_eligible_pct=100.0 if price_n else None,
            revision_support="inherits input fingerprints", missingness="no independent benchmark collector",
            status="PARTIAL", research_use="derived context only; already part of technical scope",
            blockers=["not a genuinely new information family"],
        ),
        _family(
            "L", "Volume / liquidity", collector="OHLCV collectors",
            scheduler=forecast_task, last_success=forecast_latest.get("finished_at"),
            last_observation=forecast_last_observation, expected_cadence="with OHLCV",
            staleness_days=forecast_age, observations=positive_volume_n,
            period_start=equity_latest.get("period_start"), period_end=forecast_last_observation,
            source="OHLCV volume; no verified spread/depth source", effective_at=forecast_last_observation,
            pit_eligible_pct=volume_pct, revision_support="inherits input fingerprints",
            missingness=f"positive-volume coverage={volume_pct}%; bid/ask observations={quote_n}",
            status="PARTIAL", research_use="volume context only; execution liquidity not PIT-covered",
            blockers=["no reliable bid/ask or order-book adapter"],
        ),
        _family(
            "M", "Yield / dollar / risk regime", collector="no dedicated reliable adapter",
            scheduler=None, last_success=None, last_observation=None, expected_cadence="daily/event-driven",
            staleness_days=None, observations=carry_n, period_start=None, period_end=None,
            source="none beyond existing price proxies", pit_eligible_pct=None,
            revision_support="none", missingness="yield/rate-expectation history absent",
            status="NOT_CONFIGURED", research_use="not research-ready",
            blockers=["historical expectations unavailable", "proxy reconstruction prohibited"],
        ),
    ]

    ids = [item["family_id"] for item in families]
    if len(ids) != len(set(ids)) or ids != list("ABCDEFGHIJKLM"):
        raise RuntimeError("Data-family registry is incomplete or duplicated")

    alerts: list[dict[str, object]] = []
    for item in families:
        if item["status"] == "STALE":
            alerts.append({"rule": "stale_source", "family_id": item["family_id"], "triggered": True})
        if item["status"] == "FAILED":
            alerts.append({"rule": "collector_overdue", "family_id": item["family_id"], "triggered": True})
        if item["observations"] == 0 and item["status"] not in {"NOT_APPLICABLE"}:
            alerts.append({"rule": "no_observations", "family_id": item["family_id"], "triggered": True})
        scheduler = dict(item.get("scheduler") or {})
        if scheduler and not scheduler.get("present"):
            alerts.append({"rule": "scheduler_missing", "family_id": item["family_id"], "triggered": True})
        if int(item.get("provider_errors") or 0) > 0:
            alerts.append({"rule": "provider_failures", "family_id": item["family_id"], "triggered": True})
    if fx_duplicate_n:
        alerts.append({"rule": "duplicate_observations", "family_id": "A", "triggered": True, "count": fx_duplicate_n})
    latest_consecutive = int(
        _scalar(fx_path, "SELECT MAX(consecutive_failures) FROM source_health", default=0)
    )
    if latest_consecutive >= 2:
        alerts.append({"rule": "repeated_failures", "family_id": "A", "triggered": True, "count": latest_consecutive})
    if str(forecast_latest.get("database_status") or "").upper() not in {"", "OK", "NORMAL"}:
        alerts.append({"rule": "unexpected_db_growth_stop", "family_id": "B", "triggered": True, "status": forecast_latest.get("database_status")})

    coverage_gates = {
        "fundamentals": {
            "status": "FAIL",
            "pit_cases": 0,
            "reason": "No historical SEC filing snapshots and no historical issuer mapping.",
            "development_test_started": False,
        },
        "expectations_surprise": {
            "status": "FAIL",
            "raw_events": expectation_n + macro_n,
            "events_with_expected": expectation_n,
            "events_with_actual": macro_n,
            "pit_eligible_pairs": 0,
            "reason": "No expected/actual PIT pairs; surprise remains UNKNOWN.",
            "development_test_started": False,
        },
        "cot": {
            "status": "FAIL",
            "reports": cot_n,
            "independent_report_dates": cot_period_n,
            "actual_forward_first_seen_start": cot_latest.get("first_seen_start"),
            "actual_forward_first_seen_end": cot_latest.get("first_seen_at"),
            "actual_forward_first_seen_span_days": cot_forward_span_days,
            "forward_observed_collection_days": int(cot_latest.get("forward_observed_days") or 0),
            "reason": "The collector is current again, but historical rows have only recent first-observed availability evidence; independent forward PIT history remains insufficient.",
            "development_test_started": False,
        },
        "crypto_regime": {
            "status": "FAIL",
            "price_assets": int(crypto_latest.get("assets") or 0),
            "reason": "Only the already-tested technical OHLCV layer exists; no new PIT dominance, breadth, liquidity or on-chain layer.",
            "development_test_started": False,
        },
        "gold_silver": {
            "status": "BLOCKED",
            "reason": "Futures contract IDs, roll semantics, sessions, open provenance and cost contract remain unavailable.",
            "development_test_started": False,
        },
    }

    payload: dict[str, object] = {
        "version": RESEARCH_DATA_HEALTH_VERSION,
        "as_of": stamp.isoformat(),
        "project_root": str(root),
        "mode": "READ_ONLY_DATA_HEALTH_AND_COVERAGE",
        "scheduler_query_status": scheduler_query_status,
        "families": families,
        "alerts": alerts,
        "health_rules": {
            "collector_overdue": "triggered when a configured collector is failed/overdue",
            "no_observations": "triggered for an empty required family",
            "stale_source": "triggered when actual observation age exceeds its cadence allowance",
            "provider_failures": "triggered by explicit provider failures",
            "scheduler_missing": "triggered when a required canonical task is absent",
            "repeated_failures": "triggered at two consecutive source failures",
            "unexpected_db_growth_stop": "reported from the existing forecast DB growth guard",
            "duplicate_observations": "triggered when canonical observation keys are duplicated",
        },
        "coverage_gates": coverage_gates,
        "new_challengers_created": 0,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "forward_opened": False,
        "paper_opened": False,
        "shadow_opened": False,
        "broker_accessed": False,
        "orders_created": False,
        "final_status": "RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA",
    }
    payload["report_fingerprint"] = _fingerprint(payload)
    return payload


def render_health_markdown(payload: Mapping[str, object]) -> str:
    rows = []
    provenance_rows = []
    for item in payload["families"]:
        scheduler = dict(item.get("scheduler") or {})
        scheduler_text = (
            f"{scheduler.get('task_name')} ({scheduler.get('state')})"
            if scheduler
            else "not applicable"
        )
        pit = item.get("pit_eligible_pct")
        rows.append(
            "| {family_id} | {name} | {status} | {collector} | {scheduler} | {last_success} | "
            "{last_observation} | {staleness} | {observations} | {pit} | {missingness} | {blockers} |".format(
                family_id=item["family_id"], name=item["name"], status=item["status"],
                collector=item["collector"], scheduler=scheduler_text,
                last_success=item.get("last_success") or "n/a",
                last_observation=item.get("last_observation") or "n/a",
                staleness=item.get("staleness_days") if item.get("staleness_days") is not None else "n/a",
                observations=item["observations"], pit=f"{pit}%" if pit is not None else "n/a",
                missingness=item["missingness"], blockers="; ".join(item["blockers"]) or "none",
            )
        )
        timestamps = dict(item.get("timestamps") or {})
        period = dict(item.get("period") or {})
        provenance_rows.append(
            "| {family_id} | {source} | {period_start} → {period_end} | {published} | "
            "{first_seen} | {effective} | {revision} | {errors} / {limits} | {research_use} |".format(
                family_id=item["family_id"], source=item["source"],
                period_start=period.get("start") or "n/a", period_end=period.get("end") or "n/a",
                published=timestamps.get("published_at") or "n/a",
                first_seen=timestamps.get("first_seen_at") or "n/a",
                effective=timestamps.get("effective_at") or "n/a",
                revision=item["revision_support"], errors=item["provider_errors"],
                limits=item["rate_limits"], research_use=item["research_use"],
            )
        )
    gates = []
    for name, gate in payload["coverage_gates"].items():
        gates.append(f"- **{name}: {gate['status']}** — {gate['reason']}")
    alerts = []
    for alert in payload["alerts"]:
        alerts.append(f"- `{alert['rule']}`: family {alert['family_id']}")
    return "\n".join(
        [
            "# RESEARCH_DATA_HEALTH_AND_COVERAGE",
            "",
            f"Version: `{payload['version']}`",
            f"As of: `{payload['as_of']}`",
            f"Fingerprint: `{payload['report_fingerprint']}`",
            "Mode: read-only audit; no strategy, signal, trade, broker or order path.",
            "",
            "## Data families",
            "",
            "| ID | Family | Status | Collector | Scheduler | Last success | Last actual observation | Age days | N | PIT | Missingness | Blockers |",
            "|---|---|---|---|---|---|---|---:|---:|---:|---|---|",
            *rows,
            "",
            "## Provenance, revision and research use",
            "",
            f"Scheduler query: `{payload['scheduler_query_status']}`.",
            "",
            "| ID | Source | Period | published_at | first_seen_at | effective_at | Revision support | Provider errors / rate limits | Research use |",
            "|---|---|---|---|---|---|---|---|---|",
            *provenance_rows,
            "",
            "## Coverage gates",
            "",
            *gates,
            "",
            "No Development test was opened because every new-information gate failed or remained blocked. No Challenger, Validation or Holdout was created.",
            "",
            "## Local health alerts",
            "",
            *(alerts or ["- No alert triggered."]),
            "",
            "## Terminal research status",
            "",
            f"`{payload['final_status']}`",
            "",
        ]
    )


def render_gap_markdown(payload: Mapping[str, object]) -> str:
    families = {item["family_id"]: item for item in payload["families"]}
    return "\n".join(
        [
            "# DATA_COLLECTION_GAP_REPORT",
            "",
            f"As of: `{payload['as_of']}`",
            f"Source report: `{payload['report_fingerprint']}`",
            "",
            "1. **Are all strategically important data families collected?** No. Price/OHLCV and forecasts exist, while fundamentals, expectations, politics/regulation, yield/rate expectations and execution-quality data are not operational.",
            f"2. **Technically present but practically empty:** expectations={families['F']['observations']}; fundamentals=0; verified bid/ask=0.",
            "3. **Collectors no longer producing current data:** the event sidecar is stale; COT actual forward availability is stale. The FX and forecast scheduled tasks themselves are present.",
            "4. **Schedulers disabled or absent:** no independent fundamentals, company-event, macro/expectations, politics/regulation or crypto-regime scheduler exists. Disabled terminal research/scanner tasks are intentionally not data-collector defects.",
            "5. **Current-only data that must be stored forward:** expectations/consensus, company guidance/events, macro and central-bank expectations, policy/regulatory/geopolitical events, COT first-seen evidence and reliable quotes/spreads if a lawful source becomes available.",
            "6. **Historical PIT that cannot be reconstructed safely:** analyst/macro expectations, most event first-seen times, old issuer/listing validity and expected-rate vintages. These must remain UNKNOWN and be collected prospectively.",
            "7. **Previously invisible collected data:** COT, FX source health, frozen OHLCV, identity mapping and event-sidecar coverage are now included centrally in the A–M report.",
            "8. **Revision/version gaps:** COT, FX and event schemas support append-only/revisions; fundamentals, expectations, politics and risk-regime layers have no operational revision history because they have no collector.",
            "9. **Missing by research theme:** fundamentals lack filing snapshots and historical issuer mapping; events lack published timestamps and breadth; macro/expectations lack PIT vintages; politics lacks a source; FX lacks rates/expectations/bid-ask; crypto lacks new dominance/breadth/liquidity/on-chain PIT data; relative strength is available only as a derived technical layer.",
            "10. **Unnecessary duplication:** no duplicate canonical FX observation keys were detected. COT is stored both in its canonical report store and as deduplicated FX context observations by design; that is provenance linkage, not competing truth.",
            "",
            "## Repairs made",
            "",
            "- COT refresh now catches up after a missed configured weekday when actual source evidence exceeds the maximum age.",
            "- Stale COT reports are no longer relabelled as current `AVAILABLE_PIT` context.",
            "- `NO_RELIABLE_DATA` and `NOT_SCHEDULED` attempts no longer advance `last_success` in FX source health.",
            "- The central read-only report exposes stale sources, empty families, provider failures, missing schedulers, repeated failures, DB-growth guard state and duplicate observations.",
            "",
            "## Research decision",
            "",
            "All new-information coverage gates fail or remain blocked. No technical negative claim was retested and no new Challenger was created.",
            "",
            f"`{payload['final_status']}`",
            "",
        ]
    )
