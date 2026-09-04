from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from pathlib import Path

import pandas as pd
import pytest

from equity_etf_historical_remediation import (
    PROJECTION_VERSION,
    build_equity_etf_clean_projection,
    ohlc_source_violations,
)
from multi_asset_discovery_v1 import canonical_json


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ohlc_source_violations_reports_exact_boundary_distance() -> None:
    result = ohlc_source_violations(
        {"Open": 9.0, "High": 11.0, "Low": 10.0, "Close": 12.0}
    )
    assert [item["violation"] for item in result] == [
        "OPEN_BELOW_LOW",
        "CLOSE_ABOVE_HIGH",
    ]
    assert result[0]["absolute"] == 1.0
    assert result[1]["relative_pct"] == pytest.approx(100 / 11)


def test_clean_projection_excludes_without_repair_and_is_append_only(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "dataset"
    source_dir.mkdir()
    parquet = source_dir / "asset.parquet"
    frame = pd.DataFrame(
        {
            "Open": [10.0, 9.0, 12.0],
            "High": [11.0, 11.0, 13.0],
            "Low": [9.0, 10.0, 11.0],
            "Close": [10.5, 10.5, 12.5],
            "Volume": [100.0, 200.0, 300.0],
        },
        index=pd.DatetimeIndex(
            ["2020-01-02", "2020-01-03", "2020-01-06"], name="Date"
        ),
    )
    frame.to_parquet(parquet)
    manifest_path = source_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_fingerprint": "frozen-dataset",
                "manifest_version": "v1",
                "dataset_revision": "r1",
                "provider_policy": {"price_adjustment": "auto_adjust_true"},
            }
        ),
        encoding="utf-8",
    )
    outcome_path = tmp_path / "outcomes.sqlite3"
    with sqlite3.connect(outcome_path) as connection:
        connection.execute(
            "CREATE TABLE outcome_rows(case_id TEXT,symbol TEXT,asset_class TEXT,"
            "signal_day TEXT,status TEXT,payload_zlib BLOB)"
        )
        payload = {
            "case_id": "case-1",
            "reason": "SOURCE_OHLC_ENVELOPE_ANOMALY",
        }
        connection.execute(
            "INSERT INTO outcome_rows VALUES (?,?,?,?,?,?)",
            (
                "case-1",
                "TEST",
                "EQUITIES",
                "2020-01-02",
                "INVALID_TECHNICAL_ELIGIBILITY",
                zlib.compress(canonical_json(payload).encode("utf-8"), level=9),
            ),
        )
    source_hash = _hash(parquet)
    target = tmp_path / "projection.sqlite3"
    artifact = tmp_path / "projection.json"
    asset = {
        "asset_key": "EQUITIES:TEST",
        "symbol": "TEST",
        "asset_class": "EQUITIES",
        "modern_file": "asset.parquet",
        "modern_history_fingerprint": "history",
        "identity": {"asset_id": "asset-test", "listing_id": "listing-test"},
    }

    result = build_equity_etf_clean_projection(
        target_path=target,
        artifact_path=artifact,
        manifest_path=manifest_path,
        outcome_path=outcome_path,
        assets=[asset],
        created_at="2026-09-03T12:00:00+00:00",
        code_commit="abc123",
        branch="codex/test",
        command="test",
    )

    assert _hash(parquet) == source_hash
    assert result["version"] == PROJECTION_VERSION
    assert result["counts"]["raw_bars"] == 3
    assert result["counts"]["active_valid_bars"] == 2
    assert result["counts"]["invalid_source_bars"] == 1
    assert result["active_envelope_anomaly_count"] == 0
    assert result["case_impact"]["legacy_ohlc_invalid_case_count"] == 1
    assert result["no_clipping"] is True
    assert result["no_imputation"] is True
    with sqlite3.connect(target) as connection:
        invalid = json.loads(
            connection.execute(
                "SELECT invalid_json FROM invalid_source_bars"
            ).fetchone()[0]
        )
        assert invalid["open"] == 9.0
        assert invalid["remediation"] == "EXCLUDED_WITHOUT_REPLACEMENT"
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM active_bars")

    replay = build_equity_etf_clean_projection(
        target_path=target,
        artifact_path=artifact,
        manifest_path=manifest_path,
        outcome_path=outcome_path,
        assets=[asset],
        created_at="later",
        code_commit="different",
        branch="codex/test",
        command="test",
    )
    assert replay["dataset_fingerprint"] == result["dataset_fingerprint"]
