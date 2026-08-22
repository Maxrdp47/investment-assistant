from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import pytest

from scripts import run_swing_walk_forward as cli
from swing_research_dataset import (
    FrozenResearchDatasetError,
    load_frozen_histories,
    research_history_compatible_fingerprints,
    research_history_fingerprint,
)


def history() -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=250)
    close = np.linspace(50.0, 75.0, len(index))
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": np.full(len(index), 500_000.0),
        },
        index=index,
    )


def test_cache_key_separates_different_research_windows(tmp_path) -> None:
    first = cli._cache_file(tmp_path, "AAPL", "2016|latest|adjusted")
    second = cli._cache_file(tmp_path, "AAPL", "2010|latest|adjusted")

    assert first != second
    assert first.parent == tmp_path
    assert second.parent == tmp_path


def test_research_history_fingerprint_ignores_datetime_storage_resolution() -> None:
    base = history()
    fingerprints = []
    for unit in ("s", "ms", "us", "ns"):
        variant = base.copy()
        variant.index = variant.index.as_unit(unit)
        fingerprints.append(research_history_fingerprint("AAA", variant))

    assert len(set(fingerprints)) == 1


def test_failed_bulk_download_uses_isolated_parallel_symbol_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(cli.yf, "download", lambda *args, **kwargs: pd.DataFrame())

    class FakeTicker:
        def __init__(self, ticker: str):
            self.ticker = ticker

        def history(self, **kwargs):
            return pd.DataFrame() if self.ticker == "BAD" else history()

    monkeypatch.setattr(cli.yf, "Ticker", FakeTicker)

    histories, missing = cli._download_histories(
        ["AAA", "BAD", "BBB"],
        start="2016-01-01",
        end=None,
    )

    assert set(histories) == {"AAA", "BBB"}
    assert missing == ["BAD"]


def test_analysis_jobs_are_disjoint_balanced_and_keep_asset_metadata() -> None:
    histories = {ticker: history() for ticker in ("AAA", "BBB", "CCC", "DDD", "EEE")}
    assets = [
        {"ticker": ticker, "asset_type": "ETF" if ticker == "BBB" else "Aktie", "region": "Europa"}
        for ticker in histories
    ]

    jobs = cli._analysis_jobs(histories, assets, workers=3, parameters={"future_sessions": 25})

    assigned = [ticker for job in jobs for ticker in job["histories"]]
    assert len(jobs) == 3
    assert sorted(assigned) == sorted(histories)
    assert len(assigned) == len(set(assigned))
    assert sorted(len(job["histories"]) for job in jobs) == [1, 2, 2]
    bbb_job = next(job for job in jobs if "BBB" in job["histories"])
    assert bbb_job["asset_types"]["BBB"] == "ETF"
    assert bbb_job["regions"]["BBB"] == "Europa"


def test_parallel_analysis_returns_deterministic_job_order(monkeypatch) -> None:
    jobs = [
        {"marker": marker, "delay": delay, "histories": {marker: history()}}
        for marker, delay in (("FIRST", 0.06), ("SECOND", 0.03), ("THIRD", 0.0))
    ]

    def analyze(job: dict) -> dict:
        time.sleep(float(job["delay"]))
        return {"marker": job["marker"]}

    monkeypatch.setattr(cli, "_analyze_history_job", analyze)
    runs = cli._analyze_histories_parallel(jobs, workers=3, executor_mode="threads")

    assert [run["marker"] for run in runs] == ["FIRST", "SECOND", "THIRD"]


def test_worker_failure_is_visible_and_never_falls_back_to_hidden_partial_result(monkeypatch) -> None:
    jobs = [
        {"marker": marker, "histories": {marker: history()}}
        for marker in ("GOOD", "BAD")
    ]

    def analyze(job: dict) -> dict:
        if job["marker"] == "BAD":
            raise RuntimeError("worker exploded")
        return {"marker": job["marker"]}

    monkeypatch.setattr(cli, "_analyze_history_job", analyze)

    with pytest.raises(cli.AnalysisWorkerFailure) as raised:
        cli._analyze_histories_parallel(jobs, workers=2, executor_mode="threads")

    assert raised.value.failures[0]["tickers"] == ["BAD"]
    assert raised.value.failures[0]["resume_required"] is True
    assert raised.value.failures[0]["sqlite_written_by_worker"] is False


def test_database_writes_are_serial_and_keep_worker_result_order(monkeypatch, tmp_path) -> None:
    written: list[str] = []

    def record(run: dict, database) -> dict:
        assert database == tmp_path / "research.sqlite3"
        written.append(str(run["marker"]))
        return {
            "run_inserted": True,
            "cases_inserted": 2,
            "observational_features_inserted": 2,
        }

    monkeypatch.setattr(cli, "record_swing_walk_forward_run", record)
    totals = cli._persist_runs_serially(
        [{"marker": "FIRST"}, {"marker": "SECOND"}],
        tmp_path / "research.sqlite3",
    )

    assert written == ["FIRST", "SECOND"]
    assert totals == {
        "runs_inserted": 2,
        "cases_inserted": 4,
        "observational_features_inserted": 4,
    }


def test_frozen_epoch_reuses_cache_then_never_calls_provider(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "cache"
    dataset_root = tmp_path / "datasets"
    scope = "2016-01-01|latest|1d|yfinance_auto_adjust_true"
    cli._store_cache(
        cache_path,
        {"AAA": history(), "BBB": history() * 1.01},
        cache_scope=scope,
    )
    provider_calls: list[list[str]] = []

    def no_provider(tickers, *, start, end):
        provider_calls.append(list(tickers))
        raise AssertionError("Ein gültiger Cache darf den Provider nicht aufrufen.")

    monkeypatch.setattr(cli, "_download_histories", no_provider)
    assets = [
        {"ticker": "AAA", "asset_type": "Aktie", "region": "USA"},
        {"ticker": "BBB", "asset_type": "Aktie", "region": "USA"},
    ]
    first = cli._prepare_frozen_research_dataset(
        assets,
        dataset_root=dataset_root,
        dataset_epoch="test-fixed-v1",
        scopes=[("2016-01-01", None)],
        cache_path=cache_path,
        batch_size=1,
    )
    second = cli._prepare_frozen_research_dataset(
        assets,
        dataset_root=dataset_root,
        dataset_epoch="test-fixed-v1",
        scopes=[("2016-01-01", None)],
        cache_path=cache_path,
        batch_size=2,
    )
    loaded, unavailable = load_frozen_histories(
        dataset_root,
        first,
        tickers=["AAA", "BBB"],
        start="2016-01-01",
        end=None,
    )

    assert provider_calls == []
    assert first["dataset_fingerprint"] == second["dataset_fingerprint"]
    assert set(loaded) == {"AAA", "BBB"}
    assert unavailable == []


def test_finalized_epoch_auto_accepts_only_legacy_datetime_resolution(tmp_path) -> None:
    cache_path = tmp_path / "cache"
    dataset_root = tmp_path / "datasets"
    scope = "2016-01-01|latest|1d|yfinance_auto_adjust_true"
    cli._store_cache(cache_path, {"AAA": history()}, cache_scope=scope)
    manifest = cli._prepare_frozen_research_dataset(
        [{"ticker": "AAA", "asset_type": "Aktie", "region": "USA"}],
        dataset_root=dataset_root,
        dataset_epoch="test-legacy-datetime-unit-v1",
        scopes=[("2016-01-01", None)],
        cache_path=cache_path,
        batch_size=1,
    )
    descriptor = next(iter(next(iter(manifest["scopes"].values()))["assets"].values()))
    epoch_directory = cli.research_dataset_manifest_path(
        dataset_root, "test-legacy-datetime-unit-v1"
    ).parent
    frozen_path = epoch_directory / str(descriptor["file"])
    frozen = pd.read_parquet(frozen_path)
    canonical = research_history_fingerprint("AAA", frozen)
    legacy_candidates = research_history_compatible_fingerprints("AAA", frozen) - {
        canonical
    }
    assert legacy_candidates
    descriptor["history_fingerprint"] = sorted(legacy_candidates)[0]

    loaded, unavailable = load_frozen_histories(
        dataset_root,
        manifest,
        tickers=["AAA"],
        start="2016-01-01",
        end=None,
    )

    assert set(loaded) == {"AAA"}
    assert unavailable == []

    changed = frozen.copy()
    changed.iloc[0, changed.columns.get_loc("Close")] += 0.01
    changed.to_parquet(frozen_path, index=True)
    with pytest.raises(FrozenResearchDatasetError, match="abweichende Daten"):
        load_frozen_histories(
            dataset_root,
            manifest,
            tickers=["AAA"],
            start="2016-01-01",
            end=None,
        )


def test_finalized_epoch_fails_closed_on_corrupt_parquet(tmp_path) -> None:
    cache_path = tmp_path / "cache"
    dataset_root = tmp_path / "datasets"
    scope = "2016-01-01|latest|1d|yfinance_auto_adjust_true"
    cli._store_cache(cache_path, {"AAA": history()}, cache_scope=scope)
    manifest = cli._prepare_frozen_research_dataset(
        [{"ticker": "AAA", "asset_type": "Aktie", "region": "USA"}],
        dataset_root=dataset_root,
        dataset_epoch="test-corrupt-v1",
        scopes=[("2016-01-01", None)],
        cache_path=cache_path,
        batch_size=1,
    )
    descriptor = next(iter(next(iter(manifest["scopes"].values()))["assets"].values()))
    epoch_directory = cli.research_dataset_manifest_path(
        dataset_root, "test-corrupt-v1"
    ).parent
    (epoch_directory / str(descriptor["file"])).write_bytes(b"corrupt")

    with pytest.raises(FrozenResearchDatasetError, match="nicht lesbar"):
        load_frozen_histories(
            dataset_root,
            manifest,
            tickers=["AAA"],
            start="2016-01-01",
            end=None,
        )


def test_finalized_epoch_auto_restores_only_exact_manifest_cache(tmp_path) -> None:
    cache_path = tmp_path / "cache"
    dataset_root = tmp_path / "datasets"
    scope = "2016-01-01|latest|1d|yfinance_auto_adjust_true"
    cli._store_cache(cache_path, {"AAA": history()}, cache_scope=scope)
    manifest = cli._prepare_frozen_research_dataset(
        [{"ticker": "AAA", "asset_type": "Aktie", "region": "USA"}],
        dataset_root=dataset_root,
        dataset_epoch="test-auto-repair-v1",
        scopes=[("2016-01-01", None)],
        cache_path=cache_path,
        batch_size=1,
    )
    descriptor = next(iter(next(iter(manifest["scopes"].values()))["assets"].values()))
    epoch_directory = cli.research_dataset_manifest_path(
        dataset_root, "test-auto-repair-v1"
    ).parent
    frozen_path = epoch_directory / str(descriptor["file"])
    frozen_path.write_bytes(b"corrupt-frozen-file")

    loaded, unavailable = load_frozen_histories(
        dataset_root,
        manifest,
        tickers=["AAA"],
        start="2016-01-01",
        end=None,
        repair_cache_path=cache_path,
    )

    assert set(loaded) == {"AAA"}
    assert unavailable == []
    assert list((frozen_path.parent / ".recovery").glob("*.invalid"))

    frozen_path.write_bytes(b"corrupt-again")
    changed_cache = history()
    changed_cache.iloc[0, changed_cache.columns.get_loc("Close")] += 0.01
    cli._store_cache(cache_path, {"AAA": changed_cache}, cache_scope=scope)
    with pytest.raises(FrozenResearchDatasetError, match="nicht lesbar"):
        load_frozen_histories(
            dataset_root,
            manifest,
            tickers=["AAA"],
            start="2016-01-01",
            end=None,
            repair_cache_path=cache_path,
        )


def test_finalized_epoch_rejects_manifest_revision_tampering(tmp_path) -> None:
    cache_path = tmp_path / "cache"
    dataset_root = tmp_path / "datasets"
    cli._store_cache(
        cache_path,
        {"AAA": history()},
        cache_scope="2016-01-01|latest|1d|yfinance_auto_adjust_true",
    )
    cli._prepare_frozen_research_dataset(
        [{"ticker": "AAA", "asset_type": "Aktie", "region": "USA"}],
        dataset_root=dataset_root,
        dataset_epoch="test-manifest-tamper-v1",
        scopes=[("2016-01-01", None)],
        cache_path=cache_path,
        batch_size=1,
    )
    manifest_path = cli.research_dataset_manifest_path(
        dataset_root, "test-manifest-tamper-v1"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["dataset_revision"] = "tampered"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FrozenResearchDatasetError, match="Revision"):
        cli.load_research_dataset_manifest(manifest_path)
