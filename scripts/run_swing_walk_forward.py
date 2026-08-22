from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_research_dataset import (  # noqa: E402
    FrozenResearchDatasetError,
    finalize_research_dataset_manifest,
    frozen_history_descriptor,
    frozen_history_path,
    load_frozen_histories,
    load_research_dataset_manifest,
    normalized_research_history,
    research_dataset_manifest_path,
    research_dataset_scope,
    research_dataset_scope_id,
    store_frozen_history,
)
from swing_walk_forward import (  # noqa: E402
    DEFAULT_SWING_WALK_FORWARD_DB_PATH,
    TECHNICAL_CHALLENGER_PROFILE_NAMES,
    record_swing_walk_forward_run,
    run_historical_walk_forward,
    swing_walk_forward_store_audit,
    swing_walk_forward_strategy_profiles,
    swing_walk_forward_summary,
)
from swing_research_identity import derive_swing_research_identity  # noqa: E402


DEFAULT_CACHE_PATH = PROJECT_ROOT / "runtime" / "swing_walk_forward_cache"
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "runtime" / "swing_walk_forward_datasets"
DEFAULT_RESEARCH_START = "2016-01-01"
DEFAULT_DEVELOPMENT_END = "2021-12-31"
DEFAULT_VALIDATION_END = "2023-12-31"


class AnalysisWorkerFailure(RuntimeError):
    """Fail one resumable campaign job without hiding a worker failure."""

    def __init__(self, failures: list[dict[str, object]]) -> None:
        self.failures = [dict(failure) for failure in failures]
        super().__init__(
            "Mindestens ein historischer Analyseworker ist fehlgeschlagen; "
            "der Kampagnenjob bleibt für einen unveränderten Resume-Lauf offen."
        )


def _analysis_jobs(
    histories: dict[str, pd.DataFrame],
    batch_assets: list[dict],
    *,
    workers: int,
    parameters: dict,
) -> list[dict]:
    """Build deterministic disjoint jobs; workers never write the shared database."""
    asset_by_ticker = {
        str(asset["ticker"]).upper(): asset
        for asset in batch_assets
    }
    ordered_tickers = [
        ticker for ticker in asset_by_ticker if ticker in histories
    ]
    worker_count = max(1, min(int(workers), len(ordered_tickers) or 1))
    ticker_groups: list[list[str]] = [[] for _ in range(worker_count)]
    for index, ticker in enumerate(ordered_tickers):
        ticker_groups[index % worker_count].append(ticker)
    jobs: list[dict] = []
    for tickers in ticker_groups:
        if not tickers:
            continue
        jobs.append(
            {
                "histories": {ticker: histories[ticker] for ticker in tickers},
                "asset_types": {
                    ticker: str(asset_by_ticker[ticker].get("asset_type") or "Aktie")
                    for ticker in tickers
                },
                "regions": {
                    ticker: str(asset_by_ticker[ticker].get("region") or "USA")
                    for ticker in tickers
                },
                "asset_identities": {
                    ticker: derive_swing_research_identity(asset_by_ticker[ticker])
                    for ticker in tickers
                },
                "parameters": parameters,
            }
        )
    return jobs


def _analyze_history_job(job: dict) -> dict:
    parameters = dict(job["parameters"])
    return run_historical_walk_forward(
        job["histories"],
        asset_types=job["asset_types"],
        regions=job["regions"],
        asset_identities=job["asset_identities"],
        **parameters,
    )


def _analyze_histories_parallel(
    jobs: list[dict],
    *,
    workers: int,
    executor_mode: str = "threads",
    executor: Executor | None = None,
) -> list[dict]:
    if len(jobs) <= 1 or workers <= 1:
        return [_analyze_history_job(job) for job in jobs]
    owns_executor = executor is None
    if executor is None:
        executor_type = ProcessPoolExecutor if executor_mode == "processes" else ThreadPoolExecutor
        executor = executor_type(max_workers=max(1, int(workers)))
    results: dict[int, dict] = {}
    failures: list[dict[str, object]] = []
    try:
        futures = {
            executor.submit(_analyze_history_job, job): (index, job)
            for index, job in enumerate(jobs)
        }
        for future in as_completed(futures):
            index, job = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                failure = {
                    "worker_job_index": index,
                    "tickers": sorted(job["histories"]),
                    "error": f"{type(exc).__name__}: {exc}",
                    "resume_required": True,
                    "sqlite_written_by_worker": False,
                }
                failures.append(failure)
                print(
                    json.dumps({"analysis_worker_failed": failure}, ensure_ascii=False),
                    flush=True,
                )
    finally:
        if owns_executor:
            executor.shutdown(wait=True, cancel_futures=True)
    if failures:
        raise AnalysisWorkerFailure(failures)
    # Completion order is intentionally ignored. The main process persists runs
    # in the same deterministic order in which the disjoint jobs were built.
    return [results[index] for index in range(len(jobs))]


def _persist_runs_serially(runs: list[dict], database: Path) -> dict[str, int]:
    """Keep every SQLite mutation in the main process and in deterministic order."""
    inserted_runs = 0
    inserted_cases = 0
    inserted_observational_features = 0
    for run in runs:
        stored = record_swing_walk_forward_run(run, database)
        inserted_runs += int(bool(stored["run_inserted"]))
        inserted_cases += int(stored["cases_inserted"])
        inserted_observational_features += int(
            stored.get("observational_features_inserted") or 0
        )
    return {
        "runs_inserted": inserted_runs,
        "cases_inserted": inserted_cases,
        "observational_features_inserted": inserted_observational_features,
    }


def _cache_file(cache_path: Path, ticker: str, cache_scope: str) -> Path:
    digest = hashlib.sha256(
        f"{str(ticker).upper()}|{cache_scope}".encode("utf-8")
    ).hexdigest()[:20]
    return cache_path / f"{digest}.parquet"


def _valid_history(frame: object) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not isinstance(frame, pd.DataFrame) or frame.empty or not set(required).issubset(frame.columns):
        return pd.DataFrame()
    result = frame.loc[:, required].copy()
    result.index = pd.to_datetime(result.index, errors="coerce")
    if getattr(result.index, "tz", None) is not None:
        result.index = result.index.tz_convert(None)
    result = result.loc[~result.index.isna()].sort_index()
    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["Open", "High", "Low", "Close"])


def _split_yfinance_payload(payload: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    if not isinstance(payload, pd.DataFrame) or payload.empty:
        return histories
    if not isinstance(payload.columns, pd.MultiIndex):
        if len(tickers) == 1:
            normalized = _valid_history(payload)
            if not normalized.empty:
                histories[tickers[0]] = normalized
        return histories
    first = {str(value).upper() for value in payload.columns.get_level_values(0)}
    second = {str(value).upper() for value in payload.columns.get_level_values(1)}
    for ticker in tickers:
        try:
            if ticker.upper() in first:
                frame = payload.xs(ticker, axis=1, level=0, drop_level=True)
            elif ticker.upper() in second:
                frame = payload.xs(ticker, axis=1, level=1, drop_level=True)
            else:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        normalized = _valid_history(frame)
        if not normalized.empty:
            histories[ticker] = normalized
    return histories


def _load_cached_histories(
    tickers: list[str],
    cache_path: Path,
    *,
    cache_scope: str,
    maximum_age_hours: float,
    refresh: bool,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    histories: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    now = time.time()
    for ticker in tickers:
        path = _cache_file(cache_path, ticker, cache_scope)
        fresh = path.exists() and (now - path.stat().st_mtime) <= maximum_age_hours * 3600
        if refresh or not fresh:
            missing.append(ticker)
            continue
        try:
            frame = _valid_history(pd.read_parquet(path))
        except Exception:
            frame = pd.DataFrame()
        if frame.empty:
            missing.append(ticker)
        else:
            histories[ticker] = frame
    return histories, missing


def _store_cache(
    cache_path: Path,
    histories: dict[str, pd.DataFrame],
    *,
    cache_scope: str,
) -> None:
    cache_path.mkdir(parents=True, exist_ok=True)
    for ticker, frame in histories.items():
        destination = _cache_file(cache_path, ticker, cache_scope)
        temporary = destination.with_suffix(".tmp.parquet")
        frame.to_parquet(temporary, index=True)
        temporary.replace(destination)


def _parse_dataset_scope(value: str) -> tuple[str, str | None]:
    start, separator, end = str(value).partition("|")
    if not separator or not start.strip():
        raise ValueError("Dataset-Zeitfenster muss als START|ENDE beziehungsweise START|latest angegeben werden.")
    normalized_end = end.strip()
    return start.strip(), None if normalized_end in {"", "latest"} else normalized_end


def _prepare_frozen_research_dataset(
    assets: list[dict],
    *,
    dataset_root: Path,
    dataset_epoch: str,
    scopes: list[tuple[str, str | None]],
    cache_path: Path,
    batch_size: int,
) -> dict[str, object]:
    manifest_path = research_dataset_manifest_path(dataset_root, dataset_epoch)
    expected_tickers = sorted({str(asset["ticker"]).strip().upper() for asset in assets})
    expected_scopes = {
        research_dataset_scope_id(start, end): research_dataset_scope(start, end)
        for start, end in scopes
    }
    if manifest_path.exists():
        manifest = load_research_dataset_manifest(manifest_path)
        if str(manifest.get("dataset_epoch") or "") != str(dataset_epoch):
            raise FrozenResearchDatasetError("Finalisiertes Dataset gehört zu einer anderen Research-Epoch.")
        actual_scopes = dict(manifest.get("scopes") or {})
        if set(actual_scopes) != set(expected_scopes):
            raise FrozenResearchDatasetError(
                "Finalisiertes Dataset besitzt andere Zeitfenster; eine neue Dataset-Revision ist erforderlich."
            )
        for scope_id, contract in expected_scopes.items():
            scope = dict(actual_scopes[scope_id])
            if dict(scope.get("contract") or {}) != contract:
                raise FrozenResearchDatasetError("Finalisierter Dataset-Vertrag ist abweichend.")
            if set((scope.get("assets") or {})) != set(expected_tickers):
                raise FrozenResearchDatasetError(
                    "Finalisiertes Dataset besitzt ein anderes Asset-Universum; eine neue Dataset-Revision ist erforderlich."
                )
        return manifest

    frozen_scopes: dict[str, dict[str, object]] = {}
    for start, end in sorted(set(scopes), key=lambda item: (item[0], item[1] or "")):
        scope_id = research_dataset_scope_id(start, end)
        cache_scope = f"{start}|{end or 'latest'}|1d|yfinance_auto_adjust_true"
        descriptors: dict[str, dict[str, object]] = {}
        for offset in range(0, len(expected_tickers), max(int(batch_size), 1)):
            tickers = expected_tickers[offset : offset + max(int(batch_size), 1)]
            pending: list[str] = []
            for ticker in tickers:
                frozen_path = frozen_history_path(
                    dataset_root,
                    dataset_epoch,
                    scope_id=scope_id,
                    ticker=ticker,
                )
                if frozen_path.exists():
                    try:
                        existing = normalized_research_history(pd.read_parquet(frozen_path))
                    except Exception:
                        existing = pd.DataFrame()
                    if not existing.empty:
                        descriptors[ticker] = frozen_history_descriptor(
                            dataset_root,
                            dataset_epoch,
                            scope_id=scope_id,
                            ticker=ticker,
                            frame=existing,
                        )
                        continue
                pending.append(ticker)
            cached, cache_misses = _load_cached_histories(
                pending,
                cache_path,
                cache_scope=cache_scope,
                maximum_age_hours=float("inf"),
                refresh=False,
            )
            downloaded, provider_misses = (
                _download_histories(cache_misses, start=start, end=end)
                if cache_misses
                else ({}, [])
            )
            if downloaded:
                _store_cache(cache_path, downloaded, cache_scope=cache_scope)
            for ticker, frame in sorted({**cached, **downloaded}.items()):
                descriptors[ticker] = store_frozen_history(
                    dataset_root,
                    dataset_epoch,
                    scope_id=scope_id,
                    ticker=ticker,
                    frame=frame,
                )
            for ticker in provider_misses:
                descriptors[ticker] = {
                    "ticker": ticker,
                    "status": "missing",
                    "reason": "provider_unavailable_during_epoch_freeze",
                }
            print(
                json.dumps(
                    {
                        "dataset_freeze_progress": {
                            "dataset_epoch": dataset_epoch,
                            "scope": research_dataset_scope(start, end),
                            "processed": min(offset + max(int(batch_size), 1), len(expected_tickers)),
                            "total": len(expected_tickers),
                            "provider_misses": len(provider_misses),
                        }
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        frozen_scopes[scope_id] = {
            "contract": research_dataset_scope(start, end),
            "assets": descriptors,
        }
    return finalize_research_dataset_manifest(
        dataset_root,
        dataset_epoch,
        scopes=frozen_scopes,
    )


def _download_histories(
    tickers: list[str],
    *,
    start: str,
    end: str | None,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    if not tickers:
        return {}, []
    try:
        payload = yf.download(
            tickers,
            start=start,
            end=end,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            actions=False,
            repair=False,
            keepna=False,
            progress=False,
            threads=True,
            timeout=30,
        )
    except Exception:
        payload = pd.DataFrame()
    histories = _split_yfinance_payload(payload, tickers)
    missing = [ticker for ticker in tickers if ticker not in histories]
    # A failed symbol never discards an otherwise successful batch. Independent
    # fallbacks run concurrently so one provider timeout cannot serialize 100 assets.
    def load_one(ticker: str) -> tuple[str, pd.DataFrame]:
        try:
            frame = yf.Ticker(ticker).history(
                start=start,
                end=end,
                interval="1d",
                auto_adjust=True,
                actions=False,
                repair=False,
                timeout=15,
            )
        except Exception:
            return ticker, pd.DataFrame()
        return ticker, _valid_history(frame)

    if missing:
        with ThreadPoolExecutor(max_workers=min(16, len(missing))) as executor:
            futures = {executor.submit(load_one, ticker): ticker for ticker in missing}
            for future in as_completed(futures):
                ticker, normalized = future.result()
                if not normalized.empty:
                    histories[ticker] = normalized
        missing = [ticker for ticker in missing if ticker not in histories]
    return histories, missing


def _selected_assets(args: argparse.Namespace) -> list[dict]:
    requested = {str(ticker).strip().upper() for ticker in args.tickers if str(ticker).strip()}
    report = load_swing_universe(args.universe_path)
    if report.errors:
        raise RuntimeError("; ".join(report.errors))
    assets = [asset.as_dict() for asset in report.assets if asset.active]
    if requested:
        known = {str(asset["ticker"]).upper(): asset for asset in assets}
        return [known.get(ticker, {"ticker": ticker, "asset_type": "Aktie", "region": "USA"}) for ticker in sorted(requested)]
    return assets


def _execute_analysis_batches(
    args: argparse.Namespace,
    assets: list[dict],
    *,
    profiles: dict[str, dict],
    boundaries: dict[str, object],
    cache_path: Path,
    batch_size: int,
    analysis_workers: int,
    dataset_manifest: dict[str, object] | None,
    dataset_contract: dict[str, object] | None,
) -> dict[str, object]:
    cache_scope = f"{args.start}|{args.end or 'latest'}|1d|yfinance_auto_adjust_true"
    totals: dict[str, object] = {
        "assets_requested": len(assets),
        "assets_loaded": 0,
        "assets_failed": 0,
        "runs_inserted": 0,
        "cases_inserted": 0,
        "observational_features_inserted": 0,
        "batches": 0,
        "analysis_workers": analysis_workers,
        "analysis_executor": args.analysis_executor,
        "central_worker_pool": analysis_workers > 1,
        "sqlite_writer": "main_process_serial_only",
        "dataset_epoch": (dataset_contract or {}).get("dataset_epoch"),
        "dataset_fingerprint": (dataset_contract or {}).get("dataset_fingerprint"),
        "provider_access_during_job": dataset_manifest is None,
        "failures": [],
    }

    def run_batches(executor: Executor | None) -> None:
        for offset in range(0, len(assets), batch_size):
            batch_assets = assets[offset : offset + batch_size]
            tickers = [str(asset["ticker"]).upper() for asset in batch_assets]
            print(
                json.dumps(
                    {
                        "batch_started": {
                            "number": offset // batch_size + 1,
                            "first_asset": offset + 1,
                            "last_asset": min(offset + batch_size, len(assets)),
                            "total": len(assets),
                        }
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            if dataset_manifest is not None:
                histories, failed = load_frozen_histories(
                    args.dataset_root,
                    dataset_manifest,
                    tickers=tickers,
                    start=args.start,
                    end=args.end,
                    repair_cache_path=cache_path,
                )
            else:
                cached, missing = _load_cached_histories(
                    tickers,
                    cache_path,
                    cache_scope=cache_scope,
                    maximum_age_hours=max(float(args.cache_max_age_hours), 0.0),
                    refresh=bool(args.refresh_cache),
                )
                downloaded, failed = _download_histories(missing, start=args.start, end=args.end)
                if downloaded:
                    _store_cache(cache_path, downloaded, cache_scope=cache_scope)
                histories = {**cached, **downloaded}
            totals["assets_loaded"] = int(totals["assets_loaded"]) + len(histories)
            totals["assets_failed"] = int(totals["assets_failed"]) + len(failed)
            failures = totals["failures"]
            if not isinstance(failures, list):
                raise TypeError("Interne Fehlerliste des Kampagnenjobs ist ungültig.")
            failures.extend(failed)
            totals["batches"] = int(totals["batches"]) + 1
            if histories:
                parameters = {
                    "step_sessions": args.step_sessions,
                    "future_sessions": args.future_sessions,
                    "sampling_mode": args.sampling_mode,
                    "maximum_cases": args.maximum_cases,
                    "maximum_cases_per_symbol": args.maximum_cases_per_symbol,
                    "selection_round": args.selection_round,
                    "selection_round_role": args.selection_round_role,
                    "strategy_profiles": profiles,
                    "purge_overlapping_signals": True,
                    "price_adjustment": "yfinance_auto_adjust_true",
                    "research_split_boundaries": boundaries,
                    "research_dataset": dataset_contract,
                }
                jobs = _analysis_jobs(
                    histories,
                    batch_assets,
                    workers=analysis_workers,
                    parameters=parameters,
                )
                runs = _analyze_histories_parallel(
                    jobs,
                    workers=analysis_workers,
                    executor_mode=args.analysis_executor,
                    executor=executor,
                )
                stored = _persist_runs_serially(runs, args.database)
                totals["runs_inserted"] = int(totals["runs_inserted"]) + stored["runs_inserted"]
                totals["cases_inserted"] = int(totals["cases_inserted"]) + stored["cases_inserted"]
                totals["observational_features_inserted"] = int(
                    totals["observational_features_inserted"]
                ) + stored["observational_features_inserted"]
            print(
                json.dumps(
                    {
                        "progress": {
                            "processed": min(offset + batch_size, len(assets)),
                            "total": len(assets),
                            "batch_loaded": len(histories),
                            "batch_failed": len(failed),
                        }
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    if analysis_workers <= 1:
        run_batches(None)
    else:
        executor_type = ProcessPoolExecutor if args.analysis_executor == "processes" else ThreadPoolExecutor
        # Exactly one central pool exists for the whole campaign job. Network/cache
        # preparation happens in the parent before a batch is submitted.
        with executor_type(max_workers=analysis_workers) as executor:
            run_batches(executor)
    totals["failures"] = list(totals["failures"])[:100]
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Breiter, gecachter und zeitlich getrennter Historical-Walk-Forward-Forschungsbetrieb; "
            "keine echten Forward-Fälle und keine automatische Regeländerung."
        )
    )
    parser.add_argument("tickers", nargs="*", help="Optional; ohne Ticker wird das aktive Swing-Universum verwendet.")
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--start", default=DEFAULT_RESEARCH_START)
    parser.add_argument("--end", default=None)
    parser.add_argument("--development-end", default=DEFAULT_DEVELOPMENT_END)
    parser.add_argument("--validation-end", default=DEFAULT_VALIDATION_END)
    parser.add_argument("--step-sessions", type=int, default=5)
    parser.add_argument("--future-sessions", type=int, default=25)
    parser.add_argument(
        "--sampling-mode",
        choices=("balanced_history", "recent_incremental"),
        default="balanced_history",
    )
    parser.add_argument("--maximum-cases", type=int, default=25_000)
    parser.add_argument("--maximum-cases-per-symbol", type=int, default=12)
    parser.add_argument(
        "--selection-round",
        type=int,
        default=0,
        help="Outcome-blinde, disjunkte Auswahlrunde: 0=A, 1=B, 2=C.",
    )
    parser.add_argument(
        "--selection-round-role",
        choices=("exploration", "locked_validation", "final_confirmation", "monitoring"),
        default=None,
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--analysis-workers",
        type=int,
        default=min(6, max(os.cpu_count() or 1, 1)),
        help="Parallele reine Analyseworker; nur der Hauptpfad schreibt SQLite.",
    )
    parser.add_argument(
        "--analysis-executor",
        choices=("threads", "processes"),
        default="processes",
        help="CPU-Analyse läuft standardmäßig in kontrollierten Prozessen; der Hauptprozess schreibt SQLite seriell.",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=(
            "current", "balanced", "precision", "payoff",
            *TECHNICAL_CHALLENGER_PROFILE_NAMES,
        ),
        default=("current",),
        help="Explizite Research-Profile; current ist am schnellsten, Kandidaten bleiben Shadow-only.",
    )
    parser.add_argument(
        "--expected-profile-version",
        action="append",
        default=[],
        metavar="NAME=VERSION",
        help="Optionaler Strategie-Freeze; bricht bei einer abweichenden Profilversion ab.",
    )
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--cache-max-age-hours", type=float, default=168.0)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument(
        "--dataset-epoch",
        default=None,
        help="Eindeutige Research-Epoch für einen finalisierten, providerfreien Kursdatensatz.",
    )
    parser.add_argument(
        "--dataset-scope",
        action="append",
        default=[],
        metavar="START|ENDE",
        help="Beim Dataset-Freeze vorzubereitendes Zeitfenster; ENDE darf latest sein.",
    )
    parser.add_argument("--prepare-dataset", action="store_true")
    parser.add_argument("--expected-dataset-fingerprint", default=None)
    parser.add_argument("--database", type=Path, default=DEFAULT_SWING_WALK_FORWARD_DB_PATH)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--skip-final-report",
        action="store_true",
        help="Für Shard-Kampagnen: keinen vollständigen globalen Summary-/Audit-Scan nach jedem Teiljob.",
    )
    args = parser.parse_args()
    if args.audit_only:
        print(json.dumps(swing_walk_forward_store_audit(args.database), ensure_ascii=False, indent=2))
        return 0
    if args.summary_only:
        print(json.dumps(swing_walk_forward_summary(args.database), ensure_ascii=False, indent=2))
        return 0

    cache_path = args.cache_path
    try:
        cache_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        cache_path = Path(tempfile.gettempdir()) / "investment-assistent-swing-walk-forward-cache"
        cache_path.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(PROJECT_ROOT / ".yfinance-cache"))

    assets = _selected_assets(args)
    if not assets:
        raise RuntimeError("Keine aktiven Assets für den historischen Forschungsbetrieb gefunden.")
    batch_size = max(1, min(int(args.batch_size), 200))
    analysis_workers = max(1, min(int(args.analysis_workers), 8))
    if args.prepare_dataset:
        if not args.dataset_epoch:
            raise ValueError("Der Dataset-Freeze benötigt eine explizite Research-Epoch.")
        scopes = [
            _parse_dataset_scope(value)
            for value in (args.dataset_scope or [f"{args.start}|{args.end or 'latest'}"])
        ]
        manifest = _prepare_frozen_research_dataset(
            assets,
            dataset_root=args.dataset_root,
            dataset_epoch=str(args.dataset_epoch),
            scopes=scopes,
            cache_path=cache_path,
            batch_size=batch_size,
        )
        print(
            json.dumps(
                {
                    "dataset_epoch": manifest["dataset_epoch"],
                    "dataset_fingerprint": manifest["dataset_fingerprint"],
                    "dataset_revision": manifest["dataset_revision"],
                    "manifest": str(research_dataset_manifest_path(args.dataset_root, str(args.dataset_epoch))),
                    "status": manifest["status"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    dataset_manifest: dict[str, object] | None = None
    dataset_contract: dict[str, object] | None = None
    if args.dataset_epoch:
        if args.refresh_cache:
            raise ValueError("Eine finalisierte Research-Epoch darf nicht still aktualisiert werden.")
        manifest_path = research_dataset_manifest_path(args.dataset_root, str(args.dataset_epoch))
        dataset_manifest = load_research_dataset_manifest(manifest_path)
        if str(dataset_manifest.get("dataset_epoch") or "") != str(args.dataset_epoch):
            raise FrozenResearchDatasetError("Research-Epoch stimmt nicht mit dem Dataset-Manifest überein.")
        actual_fingerprint = str(dataset_manifest.get("dataset_fingerprint") or "")
        if args.expected_dataset_fingerprint and actual_fingerprint != str(args.expected_dataset_fingerprint):
            raise FrozenResearchDatasetError("Dataset-Fingerprint weicht vom Kampagnenvertrag ab.")
        dataset_contract = {
            "dataset_epoch": str(dataset_manifest["dataset_epoch"]),
            "dataset_revision": str(dataset_manifest["dataset_revision"]),
            "dataset_fingerprint": actual_fingerprint,
            "scope_id": research_dataset_scope_id(args.start, args.end),
            "provider_access_during_job": False,
            "manifest_version": dataset_manifest["manifest_version"],
        }
    profiles = swing_walk_forward_strategy_profiles(args.profiles)
    actual_profile_versions = {
        str(profile.get("name") or ""): version
        for version, profile in profiles.items()
    }
    expected_profile_versions: dict[str, str] = {}
    for item in args.expected_profile_version:
        name, separator, version = str(item).partition("=")
        if not separator or not name.strip() or not version.strip():
            raise ValueError("Profil-Freeze muss als NAME=VERSION angegeben werden.")
        expected_profile_versions[name.strip()] = version.strip()
    for name, expected_version in expected_profile_versions.items():
        actual_version = actual_profile_versions.get(name)
        if actual_version != expected_version:
            raise RuntimeError(
                f"Strategie-Freeze verletzt: {name} erwartet {expected_version}, aktuell {actual_version}."
            )
    boundaries = {
        "development_end": args.development_end,
        "validation_end": args.validation_end,
        "last_signal_day": args.end or date.today().isoformat(),
    }
    totals = _execute_analysis_batches(
        args,
        assets,
        profiles=profiles,
        boundaries=boundaries,
        cache_path=cache_path,
        batch_size=batch_size,
        analysis_workers=analysis_workers,
        dataset_manifest=dataset_manifest,
        dataset_contract=dataset_contract,
    )
    final_payload = {"totals": totals}
    if not args.skip_final_report:
        final_payload["summary"] = swing_walk_forward_summary(args.database)
        final_payload["audit"] = swing_walk_forward_store_audit(args.database)
    print(json.dumps(final_payload, ensure_ascii=False, indent=2))
    return 0 if totals["assets_loaded"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
