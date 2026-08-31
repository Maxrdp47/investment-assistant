from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from fx_historical_pit import append_historical_fx_records
from fx_historical_remediation import (
    FX_HISTORICAL_ACTIVE_DATASET_VERSION,
    fx_ohlc_envelope_violations,
    remediate_historical_fx_store,
)


STAMP = "2026-09-01T00:10:00+00:00"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(day: str, ohlc: dict[str, float]) -> dict[str, object]:
    return {
        "feature": "PRICE",
        "pair_id": "EUR/USD",
        "observation_date": day,
        "release_at": f"{day}T22:00:00+00:00",
        "available_at": f"{day}T22:15:00+00:00",
        "vintage_date": day,
        "first_seen_at": STAMP,
        "imported_at": STAMP,
        "value": ohlc["close"],
        "unit": "USD_per_EUR",
        "source": "Yahoo Finance/yfinance unadjusted daily FX bar",
        "source_record_id": f"EURUSD=X:{day}:1d",
        "source_type": "HISTORICAL_PIT",
        "coverage_status": "AVAILABLE_PIT",
        "metadata": {
            "ohlc": ohlc,
            "source_ticker": "EURUSD=X",
            "source_is_inverse": False,
            "session_timezone": "America/New_York",
            "canonical_daily_close": "17:00",
            "availability_basis": "CONSERVATIVE_SESSION_CLOSE_PLUS_15_MINUTES",
            "adjusted": False,
        },
    }


def _previous_artifact(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "fx-historical-pit-2026.08.29-v1",
                "artifact_fingerprint": "previous-artifact",
                "source_health": {
                    "EUR/USD": {"bar_n": 3, "invalid_bar_n": 1}
                },
            }
        ),
        encoding="utf-8",
    )


def test_envelope_forensics_reports_absolute_pips_and_relative_size() -> None:
    violations = fx_ohlc_envelope_violations(
        {"open": 1.09, "high": 1.12, "low": 1.10, "close": 1.08},
        pair_id="EUR/USD",
    )
    assert [item["violation"] for item in violations] == [
        "OPEN_BELOW_LOW",
        "CLOSE_BELOW_LOW",
    ]
    assert violations[0]["pips"] == pytest.approx(100.0)
    assert violations[1]["relative_pct"] == pytest.approx(1.8181818)


def test_remediation_keeps_v1_immutable_and_excludes_invalid_bar(tmp_path: Path) -> None:
    source = tmp_path / "v1.sqlite3"
    target = tmp_path / "v2.sqlite3"
    artifact = tmp_path / "v1.json"
    append_historical_fx_records(
        [
            _record(
                "2020-01-01",
                {"open": 1.10, "high": 1.12, "low": 1.09, "close": 1.11},
            ),
            _record(
                "2020-01-02",
                {"open": 1.08, "high": 1.12, "low": 1.09, "close": 1.11},
            ),
        ],
        path=source,
    )
    _previous_artifact(artifact)
    source_hash = _hash(source)

    result = remediate_historical_fx_store(
        source_path=source,
        target_path=target,
        previous_artifact_path=artifact,
        created_at=STAMP,
        code_commit="abc123",
        branch="codex/test",
        command="test",
    )

    assert _hash(source) == source_hash
    assert result["version"] == FX_HISTORICAL_ACTIVE_DATASET_VERSION
    assert result["v2_invalid_source_bar_n"] == 1
    assert result["active_envelope_anomaly_n"] == 0
    assert result["no_clipping"] is True
    assert result["no_imputation"] is True
    assert result["legacy_229_and_v2_231_same_group"] is False
    assert result["coverage"]["EUR/USD"]["raw_bars"] == 3
    assert result["coverage"]["EUR/USD"]["active_valid_bars"] == 1
    assert result["coverage"]["EUR/USD"]["missing_source_sessions"] == 2

    with sqlite3.connect(target) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM historical_fx_records").fetchone()[0] == 1
        invalid = json.loads(
            connection.execute(
                "SELECT invalid_json FROM historical_fx_invalid_bars"
            ).fetchone()[0]
        )
        assert invalid["classification"] == "INVALID_SOURCE_BAR"
        assert invalid["pipeline_admission_root_cause"] == (
            "ASYMMETRIC_ENVELOPE_VALIDATOR_MISSED_LOW_SIDE_VIOLATIONS"
        )
        assert invalid["provider_or_session_root_cause"] == (
            "UNKNOWN_NOT_PROVABLE_FROM_PRESERVED_V1_MATERIAL"
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM historical_fx_invalid_bars")

    replay = remediate_historical_fx_store(
        source_path=source,
        target_path=target,
        previous_artifact_path=artifact,
        created_at=STAMP,
        code_commit="abc123",
        branch="codex/test",
        command="test",
    )
    assert replay["dataset_fingerprint"] == result["dataset_fingerprint"]

