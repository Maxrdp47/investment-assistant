from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

import multi_asset_development_v6_inputs as inputs_module
from multi_asset_development_v6_inputs import (
    MINIMUM_SEGMENT_HISTORY,
    MultiAssetV6InputError,
    SegmentedAssetHistory,
    _segments_for_rows,
    build_crypto_projection,
    build_v6_implementation_provenance,
    build_v6_input_precheck,
    default_implementation_paths,
    load_v6_asset_history,
    verify_v6_current_sources,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


STAMP = "2026-09-05T12:00:00+00:00"


def test_default_implementation_paths_cover_direct_runtime_dependencies() -> None:
    labels = {
        str(path.relative_to(Path(__file__).resolve().parents[1])).replace("\\", "/")
        for path in default_implementation_paths()
    }
    assert {
        "config/multi_asset_discovery_development_v6.json",
        "config/multi_asset_discovery_v1.json",
        "config/multi_asset_discovery_development_v5.json",
        "config/swing_walk_forward_campaign.json",
        "fx_carry_pit.py",
        "historical_dependency_policy.py",
        "multi_asset_development_contract.py",
        "multi_asset_development_execution.py",
        "multi_asset_discovery_v1.py",
        "multi_asset_development_v6_inputs.py",
        "multi_asset_development_v6_contract.py",
        "multi_asset_development_v6_execution.py",
        "multi_asset_development_v6_outcomes.py",
        "multi_asset_development_v6_store.py",
        "multi_asset_development_v6_benchmark.py",
        "multi_asset_development_v6_audit.py",
        "multi_asset_development_v6_reporting.py",
        "multi_asset_development_v6_runner.py",
        "multi_asset_development_v6_preflight.py",
        "swing_broad_research.py",
        "swing_research_identity_v3.py",
        "swing_run_lock.py",
        "swing_walk_forward_campaign.py",
        "scripts/build_multi_asset_development_v6_inputs.py",
        "scripts/build_multi_asset_development_v6_contract.py",
        "scripts/build_multi_asset_development_v6_preflight.py",
        "scripts/run_multi_asset_development_v6_chain.py",
        "scripts/run_multi_asset_development_v6_chain.cmd",
        "scripts/install_multi_asset_development_v6_task.ps1",
    } <= labels
    assert all(path.is_file() for path in default_implementation_paths())


def test_implementation_provenance_rehashes_current_code(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("VALUE = 1\n", encoding="utf-8")
    second.write_text("VALUE = 2\n", encoding="utf-8")

    initial = build_v6_implementation_provenance(
        [first, second], project_root=tmp_path
    )
    assert initial["complete"] is True
    assert initial["implementation_paths"] == ["first.py", "second.py"]
    assert initial["implementation_fingerprint"] == fingerprint(
        initial["implementation_sha256"]
    )

    first.write_text("VALUE = 3\n", encoding="utf-8")
    changed = build_v6_implementation_provenance(
        [first, second], project_root=tmp_path
    )
    assert changed["implementation_fingerprint"] != initial[
        "implementation_fingerprint"
    ]

    missing = build_v6_implementation_provenance(
        [first, tmp_path / "missing.py"], project_root=tmp_path
    )
    assert missing["complete"] is False
    assert missing["implementation_fingerprint"] is None
    assert missing["missing_implementation_files"] == ["missing.py"]


def test_store_sha_is_cached_by_unchanged_file_stat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "large.sqlite3"
    store.write_bytes(b"abc")
    calls: list[Path] = []

    def fake_sha256(path: Path) -> str:
        calls.append(Path(path))
        return f"sha-for-{Path(path).stat().st_size}"

    inputs_module._sha256_for_unchanged_stat.cache_clear()
    monkeypatch.setattr(inputs_module, "file_sha256", fake_sha256)
    assert inputs_module._matches_immutable_sha256(store, "sha-for-3") is True
    assert inputs_module._matches_immutable_sha256(store, "sha-for-3") is True
    assert len(calls) == 1

    store.write_bytes(b"abcd")
    assert inputs_module._matches_immutable_sha256(store, "sha-for-4") is True
    assert len(calls) == 2
    inputs_module._sha256_for_unchanged_stat.cache_clear()


def test_public_loader_reuses_store_hash_and_same_size_mutation_invalidates_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "equity.sqlite3"
    store.write_bytes(b"alpha")
    calls: list[str] = []

    def fake_sha256(path: Path) -> str:
        calls.append(Path(path).read_text(encoding="utf-8"))
        return "sha-" + Path(path).read_text(encoding="utf-8")

    def fake_history(
        asset_class: str,
        symbol: str,
        *,
        combined_input_fingerprint: str | None = None,
        **kwargs,
    ) -> SegmentedAssetHistory:
        del kwargs
        return SegmentedAssetHistory(
            asset_class=asset_class,
            symbol=symbol,
            frame=pd.DataFrame(),
            availability={},
            dataset_fingerprint="equity-fp",
            combined_input_fingerprint=combined_input_fingerprint,
            gap_boundaries=(),
            coverage={},
            segment_end_reasons={},
        )

    precheck: dict[str, object] = {
        "status": "PASS",
        "contract_inputs": {
            "combined_input_fingerprint": "combined-fp",
            "equity_etf_projection_fingerprint": "equity-fp",
            "equity_etf_store_sha256": "sha-alpha",
        },
    }
    consensus: dict[str, object] = {
        "version": inputs_module.PEER_SESSION_CONSENSUS_VERSION,
        "method": "UNION_OF_ACTIVE_BARS_WITHIN_FROZEN_SESSION_GROUP",
        "equities_etf_group_source": "FROZEN_IDENTITY_REGISTRY_MIC",
        "fx_group_source": "FROZEN_THREE_PAIR_ACTIVE_SESSION_UNION",
        "identity_registry_fingerprint": "registry-fp",
        "official_exchange_or_fx_calendar_asserted": False,
        "dates_without_any_active_group_observation_asserted_as_sessions": False,
        "limitation": "fixture",
        "groups": {"MIC:TEST": ["2020-01-02"]},
        "asset_group_keys": {
            f"EQUITIES:{symbol}": "MIC:TEST" for symbol in ("AAA", "BBB", "CCC")
        },
        "group_member_counts": {"MIC:TEST": 3},
    }
    consensus["fingerprint"] = fingerprint(consensus)
    policy = inputs_module.gap_policy(
        peer_session_consensus_fingerprint=str(consensus["fingerprint"])
    )
    precheck["peer_session_consensus"] = consensus
    precheck["gap_policy"] = policy
    precheck["contract_inputs"]["gap_policy_fingerprint"] = policy["fingerprint"]
    precheck["artifact_fingerprint"] = fingerprint(precheck)
    inputs_module._sha256_for_unchanged_stat.cache_clear()
    monkeypatch.setattr(inputs_module, "file_sha256", fake_sha256)
    monkeypatch.setattr(inputs_module, "load_segmented_asset_history", fake_history)

    for symbol in ("AAA", "BBB"):
        loaded = load_v6_asset_history(
            {"asset_class": "EQUITIES", "symbol": symbol},
            input_precheck=precheck,
            equity_etf_store=store,
        )
        assert loaded.dataset_fingerprint == "equity-fp"
    assert calls == ["alpha"]

    prior = store.stat().st_mtime_ns
    store.write_bytes(b"bravo")  # same byte length, different immutable content
    os.utime(store, ns=(prior + 10_000_000, prior + 10_000_000))
    with pytest.raises(MultiAssetV6InputError, match="Input-Store-Hash"):
        load_v6_asset_history(
            {"asset_class": "EQUITIES", "symbol": "CCC"},
            input_precheck=precheck,
            equity_etf_store=store,
        )
    assert calls == ["alpha", "bravo"]
    inputs_module._sha256_for_unchanged_stat.cache_clear()


def _artifact(path: Path, payload: dict[str, object], field: str) -> None:
    body = dict(payload)
    body[field] = fingerprint(body)
    path.write_text(
        json.dumps(body, sort_keys=True, allow_nan=False), encoding="utf-8"
    )


def _crypto_asset(
    symbol: str, relative: str, *, asset_id: str, listing_id: str
) -> dict[str, object]:
    return {
        "asset_key": f"CRYPTO:{symbol}",
        "symbol": symbol,
        "asset_class": "CRYPTO",
        "modern_file": relative,
        "modern_history_fingerprint": f"history-{symbol}",
        "identity": {"asset_id": asset_id, "listing_id": listing_id},
    }


def _write_crypto_sources(root: Path) -> list[dict[str, object]]:
    definitions = (
        ("AAVE-USD", "2020-10-02", "aave"),
        ("ICP-USD", "2021-05-10", "icp"),
        ("SHIB-USD", "2021-04-16", "shib"),
    )
    assets: list[dict[str, object]] = []
    for symbol, invalid_day, stem in definitions:
        index = pd.DatetimeIndex(
            [pd.Timestamp(invalid_day), pd.Timestamp(invalid_day) + pd.Timedelta(days=1)],
            name="Date",
        )
        frame = pd.DataFrame(
            {
                "Open": [0.0, 10.0],
                "High": [1.0, 11.0],
                "Low": [0.0, 9.0],
                "Close": [1.0, 10.5],
                "Volume": [100.0, 101.0],
            },
            index=index,
        )
        relative = f"{stem}.parquet"
        frame.to_parquet(root / relative)
        assets.append(
            _crypto_asset(
                symbol,
                relative,
                asset_id=f"asset-{stem}",
                listing_id=f"listing-{stem}",
            )
        )
    empty = pd.DataFrame(
        columns=["Open", "High", "Low", "Close", "Volume"],
        index=pd.DatetimeIndex([], name="Date"),
    )
    empty.to_parquet(root / "apt.parquet")
    assets.append(
        _crypto_asset(
            "APT21794-USD",
            "apt.parquet",
            asset_id="asset-apt",
            listing_id="listing-apt",
        )
    )
    return assets


def _build_crypto_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, list[dict[str, object]]]:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"dataset_fingerprint":"frozen-dataset","frozen":true}\n',
        encoding="utf-8",
    )
    identity = tmp_path / "identity.sqlite3"
    _create_identity_store(identity)
    assets = _write_crypto_sources(tmp_path)
    store = tmp_path / "crypto.sqlite3"
    artifact = tmp_path / "crypto.json"
    build_crypto_projection(
        target_path=store,
        artifact_path=artifact,
        manifest_path=manifest,
        identity_store=identity,
        assets=assets,
        created_at=STAMP,
    )
    return store, artifact, manifest, identity, assets


def test_crypto_projection_archives_known_bad_sessions_and_is_append_only(
    tmp_path: Path,
) -> None:
    store, artifact, manifest, identity, assets = _build_crypto_fixture(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert payload["counts"] == {
        "assets": 4,
        "raw_bars": 6,
        "active_valid_bars": 3,
        "invalid_source_bars": 3,
        "no_data_assets": 1,
        "source_missing_calendar_days": 0,
        "gap_boundaries": 3,
    }
    assert payload["target_store_sha256"] == file_sha256(store)
    assert payload["source_manifest_sha256"] == file_sha256(manifest)
    assert payload["no_imputation"] is True
    with sqlite3.connect(store) as connection:
        assert connection.execute(
            "SELECT ticker,session_date FROM invalid_source_bars "
            "ORDER BY ticker"
        ).fetchall() == [
            ("AAVE-USD", "2020-10-02"),
            ("ICP-USD", "2021-05-10"),
            ("SHIB-USD", "2021-04-16"),
        ]
        assert connection.execute(
            "SELECT coverage_status FROM asset_coverage WHERE ticker='APT21794-USD'"
        ).fetchone()[0] == "NO_DATA"
        assert connection.execute(
            "SELECT COUNT(*) FROM active_bars WHERE open<=0 OR high<=0 OR low<=0 OR close<=0"
        ).fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE active_bars SET close=close")

    replay = build_crypto_projection(
        target_path=store,
        artifact_path=artifact,
        manifest_path=manifest,
        identity_store=identity,
        assets=assets,
        created_at=STAMP,
    )
    assert replay["artifact_fingerprint"] == payload["artifact_fingerprint"]


def test_gap_segments_restart_warmup_and_outcomes_never_cross_boundary() -> None:
    first = date(2020, 1, 1)
    first_segment = [first + timedelta(days=index) for index in range(220)]
    invalid_day = first_segment[-1] + timedelta(days=1)
    second_start = invalid_day + timedelta(days=1)
    second_segment = [second_start + timedelta(days=index) for index in range(221)]
    rows = [
        {
            "Date": day.isoformat(),
            "Open": 10.0,
            "High": 11.0,
            "Low": 9.0,
            "Close": 10.5,
            "Volume": 100.0,
            "available_at": None,
        }
        for day in [*first_segment, *second_segment]
    ]
    frame, boundaries, reasons = _segments_for_rows(
        asset_class="CRYPTO",
        ticker="TEST-USD",
        rows=rows,
        invalid_days=[invalid_day.isoformat()],
    )
    history = SegmentedAssetHistory(
        asset_class="CRYPTO",
        symbol="TEST-USD",
        frame=frame,
        availability_status="AVAILABLE_WITH_EXCLUSIONS_OR_GAPS",
        availability={},
        dataset_fingerprint="crypto-dataset",
        combined_input_fingerprint="combined",
        gap_boundaries=boundaries,
        coverage={},
        segment_end_reasons=reasons,
    )

    assert len(history.segments) == 2
    assert history.frame.iloc[220]["SEGMENT_POSITION"] == 0
    assert history.frame.iloc[219]["SEGMENT_END_REASON"] == (
        "ARCHIVED_INVALID_SOURCE_SESSION+MISSING_CALENDAR_OBSERVATIONS"
    )
    assert 219 not in history.eligible_signal_positions()
    assert 439 in history.eligible_signal_positions()
    assert history.outcome_positions(218, horizon=20) == [219]
    assert history.outcome_positions(219, horizon=20) == []
    assert history.segment_metadata[1][
        "first_eligible_signal_position_within_segment"
    ] == (
        MINIMUM_SEGMENT_HISTORY - 1
    )


def test_peer_observed_mic_session_creates_boundary_without_calendar_claim() -> None:
    rows = [
        {
            "Date": day,
            "Open": 10.0,
            "High": 11.0,
            "Low": 9.0,
            "Close": 10.5,
            "Volume": 100.0,
            "available_at": None,
        }
        for day in ("2020-01-03", "2020-01-07")
    ]
    frame, boundaries, reasons = _segments_for_rows(
        asset_class="EQUITIES",
        ticker="EQ",
        rows=rows,
        invalid_days=[],
        peer_observed_group_sessions=(
            "2020-01-03",
            "2020-01-06",
            "2020-01-07",
        ),
        session_group_key="MIC:TEST",
    )

    assert len(frame.groupby("SEGMENT_ID")) == 2
    assert boundaries == (
        {
            "asset_class": "EQUITIES",
            "ticker": "EQ",
            "boundary_type": "TARGET_MISSING_ON_PEER_OBSERVED_GROUP_SESSION",
            "session_group_key": "MIC:TEST",
            "after_date": "2020-01-03",
            "before_date": "2020-01-07",
            "missing_observations": 1,
            "first_missing_session_date": "2020-01-06",
            "last_missing_session_date": "2020-01-06",
        },
    )
    assert reasons[0] == "TARGET_MISSING_ON_PEER_OBSERVED_GROUP_SESSION"

    continuous, no_boundaries, _ = _segments_for_rows(
        asset_class="EQUITIES",
        ticker="EQ",
        rows=rows,
        invalid_days=[],
        peer_observed_group_sessions=("2020-01-03", "2020-01-07"),
        session_group_key="MIC:TEST",
    )
    assert len(continuous.groupby("SEGMENT_ID")) == 1
    assert no_boundaries == ()


def _create_equity_store(path: Path) -> str:
    dataset_fingerprint = "equity-projection"
    available = {
        "asset_key": "EQUITIES:EQ",
        "asset_id": "asset-eq",
        "listing_id": "listing-eq",
        "ticker": "EQ",
        "asset_class": "EQUITIES",
        "active_valid_bars": 1,
        "invalid_source_bars": 0,
    }
    no_data = {
        "asset_key": "ETF:NODATA",
        "asset_id": "asset-etf",
        "listing_id": "listing-etf",
        "ticker": "NODATA",
        "asset_class": "ETF",
        "active_valid_bars": 0,
        "invalid_source_bars": 0,
    }
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE active_bars (
                asset_id TEXT, listing_id TEXT, ticker TEXT, asset_class TEXT,
                session_date TEXT, open REAL, high REAL, low REAL, close REAL,
                volume REAL, source_history_fingerprint TEXT
            );
            CREATE TABLE invalid_source_bars (
                asset_id TEXT, listing_id TEXT, ticker TEXT, asset_class TEXT,
                session_date TEXT
            );
            CREATE TABLE asset_coverage (asset_key TEXT, coverage_json TEXT);
            CREATE TABLE projection_versions (dataset_fingerprint TEXT);
            """
        )
        connection.execute(
            "INSERT INTO active_bars VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "asset-eq", "listing-eq", "EQ", "EQUITIES", "2020-01-02",
                10.0, 11.0, 9.0, 10.5, 100.0, "history-eq",
            ),
        )
        connection.executemany(
            "INSERT INTO asset_coverage VALUES (?,?)",
            [
                (available["asset_key"], canonical_json(available)),
                (no_data["asset_key"], canonical_json(no_data)),
            ],
        )
        connection.execute("INSERT INTO projection_versions VALUES (?)", (dataset_fingerprint,))
    return dataset_fingerprint


def _create_fx_store(path: Path) -> str:
    dataset_fingerprint = "fx-projection"
    record = {
        "feature": "PRICE",
        "pair_id": "EUR/USD",
        "observation_date": "2020-01-02",
        "available_at": "2020-01-02T22:15:00+00:00",
        "pit_eligible": True,
        "metadata": {
            "ohlc": {"open": 1.10, "high": 1.12, "low": 1.09, "close": 1.11}
        },
    }
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE historical_fx_records (
                pair_id TEXT, feature TEXT, pit_eligible INTEGER,
                observation_date TEXT, record_json TEXT
            );
            CREATE TABLE historical_fx_invalid_bars (
                pair_id TEXT, observation_date TEXT
            );
            CREATE TABLE fx_dataset_versions (dataset_fingerprint TEXT);
            """
        )
        connection.execute(
            "INSERT INTO historical_fx_records VALUES (?,?,?,?,?)",
            ("EUR/USD", "PRICE", 1, "2020-01-02", canonical_json(record)),
        )
        connection.execute("INSERT INTO fx_dataset_versions VALUES (?)", (dataset_fingerprint,))
    return dataset_fingerprint


def _create_identity_store(path: Path) -> None:
    records = []
    for ticker, asset_class, asset_id, listing_id in (
        ("EQ", "EQUITIES", "asset-eq", "listing-eq"),
        ("NODATA", "ETF", "asset-etf", "listing-etf"),
        ("AAVE-USD", "KRYPTO", "asset-aave", "listing-aave"),
        ("ICP-USD", "KRYPTO", "asset-icp", "listing-icp"),
        ("SHIB-USD", "KRYPTO", "asset-shib", "listing-shib"),
        ("APT21794-USD", "KRYPTO", "asset-apt", "listing-apt"),
    ):
        records.append(
            {
                "ticker": ticker,
                "asset_class": asset_class,
                "asset_id": asset_id,
                "listing_id": listing_id,
                "currency": "USD",
                "mic": "TEST",
                "exchange": "TEST",
                "exchange_timezone": "UTC",
            }
        )
    registry = {"records": records}
    registry["registry_fingerprint"] = fingerprint(registry)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE registry_versions (registry_json TEXT)")
        connection.execute(
            "INSERT INTO registry_versions VALUES (?)", (canonical_json(registry),)
        )


def test_combined_precheck_binds_all_inputs_and_public_loader(
    tmp_path: Path,
) -> None:
    crypto_store, crypto_artifact, manifest, identity_placeholder, assets = (
        _build_crypto_fixture(tmp_path)
    )
    equity_store = tmp_path / "equity.sqlite3"
    fx_store = tmp_path / "fx.sqlite3"
    equity_fingerprint = _create_equity_store(equity_store)
    fx_fingerprint = _create_fx_store(fx_store)
    equity_artifact = tmp_path / "equity.json"
    fx_artifact = tmp_path / "fx.json"
    _artifact(
        equity_artifact,
        {
            "dataset_fingerprint": equity_fingerprint,
            "target_store_sha256": file_sha256(equity_store),
            "source_manifest_sha256": file_sha256(manifest),
            "source_dataset_fingerprint": "frozen-dataset",
            "no_imputation": True,
        },
        "artifact_fingerprint",
    )
    _artifact(
        fx_artifact,
        {"dataset_fingerprint": fx_fingerprint, "no_imputation": True},
        "manifest_fingerprint",
    )
    implementation = [tmp_path / "implementation-a.py", tmp_path / "runner.py"]
    for path in implementation:
        path.write_text("# frozen implementation\n", encoding="utf-8")
    precheck_path = tmp_path / "precheck.json"
    result = build_v6_input_precheck(
        equity_etf_store=equity_store,
        equity_etf_artifact=equity_artifact,
        crypto_store=crypto_store,
        crypto_artifact=crypto_artifact,
        fx_store=fx_store,
        fx_artifact=fx_artifact,
        dataset_manifest=manifest,
        identity_store=identity_placeholder,
        implementation_paths=implementation,
        expected_asset_counts={"EQUITIES_ETF": 2, "CRYPTO": 4, "FX": 1},
        expected_no_data_counts={"EQUITIES_ETF": 1, "CRYPTO": 1, "FX": 0},
        expected_active_bar_counts={"EQUITIES_ETF": 1, "CRYPTO": 3, "FX": 1},
        expected_invalid_bar_counts={"EQUITIES_ETF": 0, "CRYPTO": 3, "FX": 0},
        expected_eligible_signal_position_counts={
            "EQUITIES_ETF": 0,
            "CRYPTO": 0,
            "FX": 0,
        },
        expected_crypto_invalid_sessions={
            "AAVE-USD": ["2020-10-02"],
            "ICP-USD": ["2021-05-10"],
            "SHIB-USD": ["2021-04-16"],
        },
        artifact_path=precheck_path,
        created_at=STAMP,
    )

    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["coverage"]["active_bar_count"] == 5
    assert result["coverage"]["no_data_asset_count"] == 2
    assert result["contract_inputs"]["implementation_fingerprint"]
    assert result["contract_inputs"]["crypto_store_sha256"] == file_sha256(
        crypto_store
    )
    assert set(result["source_paths"]) == set(result["source_sha256_before"])
    assert all(
        not Path(str(entry["relative_path"])).is_absolute()
        and ".." not in Path(str(entry["relative_path"])).parts
        for entry in result["source_paths"].values()
    )
    assert result["development_run_started"] is False
    consensus = result["peer_session_consensus"]
    assert consensus["official_exchange_or_fx_calendar_asserted"] is False
    assert (
        result["gap_policy"]["peer_session_consensus_fingerprint"]
        == consensus["fingerprint"]
    )
    assert result["coverage"]["actual_eligible_signal_position_counts"] == {
        "EQUITIES_ETF": 0,
        "CRYPTO": 0,
        "FX": 0,
    }

    source_audit = verify_v6_current_sources(
        input_precheck_artifact=precheck_path,
        input_precheck=result,
    )
    assert source_audit["status"] == "PASS"
    assert source_audit["source_sha256"] == result["source_sha256_before"]

    history = load_v6_asset_history(
        assets[0],
        input_precheck=result,
        equity_etf_store=equity_store,
        crypto_store=crypto_store,
        fx_store=fx_store,
    )
    assert history.source_fingerprint == result["contract_inputs"][
        "crypto_projection_fingerprint"
    ]
    assert history.combined_input_fingerprint == result["contract_inputs"][
        "combined_input_fingerprint"
    ]
    assert history.availability_status == "AVAILABLE_WITH_EXCLUSIONS_OR_GAPS"
    assert len(history.frame) == 1
    tampered = dict(result)
    tampered["status"] = "FAIL"
    with pytest.raises(MultiAssetV6InputError, match="nicht selbstgültig/PASS"):
        load_v6_asset_history(
            assets[0],
            input_precheck=tampered,
            equity_etf_store=equity_store,
            crypto_store=crypto_store,
            fx_store=fx_store,
        )

    consensus_tampered = json.loads(json.dumps(result))
    consensus_tampered["peer_session_consensus"]["groups"][
        "FX:FROZEN_THREE_PAIR_ACTIVE_SESSION_UNION"
    ].append("2020-01-03")
    consensus_tampered.pop("artifact_fingerprint")
    consensus_tampered["artifact_fingerprint"] = fingerprint(consensus_tampered)
    with pytest.raises(MultiAssetV6InputError, match="Session-Konsens"):
        load_v6_asset_history(
            assets[0],
            input_precheck=consensus_tampered,
            equity_etf_store=equity_store,
            crypto_store=crypto_store,
            fx_store=fx_store,
        )

    failed = build_v6_input_precheck(
        equity_etf_store=equity_store,
        equity_etf_artifact=equity_artifact,
        crypto_store=crypto_store,
        crypto_artifact=crypto_artifact,
        fx_store=fx_store,
        fx_artifact=fx_artifact,
        dataset_manifest=manifest,
        identity_store=identity_placeholder,
        implementation_paths=implementation,
        expected_asset_counts={"EQUITIES_ETF": 2, "CRYPTO": 4, "FX": 1},
        expected_no_data_counts={"EQUITIES_ETF": 1, "CRYPTO": 1, "FX": 0},
        expected_active_bar_counts={"EQUITIES_ETF": 1, "CRYPTO": 4, "FX": 1},
        expected_invalid_bar_counts={"EQUITIES_ETF": 0, "CRYPTO": 3, "FX": 0},
        expected_eligible_signal_position_counts={
            "EQUITIES_ETF": 0,
            "CRYPTO": 0,
            "FX": 0,
        },
        expected_crypto_invalid_sessions={
            "AAVE-USD": ["2020-10-02"],
            "ICP-USD": ["2021-05-10"],
            "SHIB-USD": ["2021-04-16"],
        },
        artifact_path=tmp_path / "failed-precheck.json",
        created_at=STAMP,
    )
    assert failed["status"] == "FAIL"
    assert failed["checks"]["expected_active_bar_counts_match"] is False

    replay = build_v6_input_precheck(
        equity_etf_store=equity_store,
        equity_etf_artifact=equity_artifact,
        crypto_store=crypto_store,
        crypto_artifact=crypto_artifact,
        fx_store=fx_store,
        fx_artifact=fx_artifact,
        dataset_manifest=manifest,
        identity_store=identity_placeholder,
        implementation_paths=implementation,
        expected_asset_counts={"EQUITIES_ETF": 2, "CRYPTO": 4, "FX": 1},
        expected_no_data_counts={"EQUITIES_ETF": 1, "CRYPTO": 1, "FX": 0},
        expected_active_bar_counts={"EQUITIES_ETF": 1, "CRYPTO": 3, "FX": 1},
        expected_invalid_bar_counts={"EQUITIES_ETF": 0, "CRYPTO": 3, "FX": 0},
        expected_eligible_signal_position_counts={
            "EQUITIES_ETF": 0,
            "CRYPTO": 0,
            "FX": 0,
        },
        expected_crypto_invalid_sessions={
            "AAVE-USD": ["2020-10-02"],
            "ICP-USD": ["2021-05-10"],
            "SHIB-USD": ["2021-04-16"],
        },
        artifact_path=precheck_path,
    )
    assert replay["artifact_fingerprint"] == result["artifact_fingerprint"]

    equity_artifact.write_text(
        equity_artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(MultiAssetV6InputError, match="weichen vom PASS-Precheck ab"):
        verify_v6_current_sources(
            input_precheck_artifact=precheck_path,
            input_precheck=result,
        )
