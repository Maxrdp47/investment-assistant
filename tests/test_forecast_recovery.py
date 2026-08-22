from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from forecast_recovery import (
    finish_recovery_run,
    record_recovery_asset,
    recovery_bars,
    start_recovery_run,
)


TARGET = datetime.fromisoformat("2026-08-06T22:30:00+02:00")


def frame(index: list[object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0] * len(index),
            "High": [102.0] * len(index),
            "Low": [99.0] * len(index),
            "Close": [101.0] * len(index),
            "Adj Close": [101.0] * len(index),
            "Volume": [1000.0] * len(index),
        },
        index=index,
    )


def test_recovery_filters_every_bar_at_the_cutoff() -> None:
    daily = recovery_bars(
        frame([pd.Timestamp("2026-08-05"), pd.Timestamp("2026-08-06")]),
        interval="1d",
        target_at=TARGET,
    )
    intraday = recovery_bars(
        frame(
            [
                pd.Timestamp("2026-08-06T20:20:00Z"),
                pd.Timestamp("2026-08-06T20:25:00Z"),
                pd.Timestamp("2026-08-06T20:30:00Z"),
                pd.Timestamp("2026-08-06T20:35:00Z"),
            ]
        ),
        interval="5m",
        target_at=TARGET,
    )

    assert [bar["market_date"] for bar in daily] == ["2026-08-05"]
    assert [bar["bar_time_utc"] for bar in intraday] == [
        "2026-08-06T20:20:00+00:00",
        "2026-08-06T20:25:00+00:00",
    ]
    assert all(bar["bar_end_utc"] <= "2026-08-06T20:30:00+00:00" for bar in intraday)


def test_recovery_database_is_separate_and_never_forward_eligible() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "recovery.sqlite3"
        run_id = start_recovery_run(database_path, TARGET, 1)
        daily = recovery_bars(
            frame([pd.Timestamp("2026-08-05")]), interval="1d", target_at=TARGET
        )
        intraday = recovery_bars(
            frame([pd.Timestamp("2026-08-06T20:25:00Z")]),
            interval="5m",
            target_at=TARGET,
        )
        asset = {
            "ticker": "TEST",
            "name": "Test Asset",
            "asset_type": "Aktie",
            "region": "Test",
            "category": "Test",
        }

        record_recovery_asset(database_path, run_id, asset, daily, intraday)
        record_recovery_asset(database_path, run_id, asset, daily, intraday)
        summary = finish_recovery_run(database_path, run_id)

        assert summary["status"] == "completed"
        assert summary["bar_count"] == 2
        assert summary["forward_test_eligible"] == 0
        assert summary["prediction_generated_at_target"] == 0
        assert summary["database_integrity"] == "ok"
        assert len(summary["data_fingerprint"]) == 64
        with closing(sqlite3.connect(database_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        assert "forecasts" not in tables
        assert "forecast_evaluations" not in tables


def test_recovery_rejects_ambiguous_or_future_target() -> None:
    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(ValueError, match="Zeitzone"):
            start_recovery_run(
                Path(directory) / "naive.sqlite3", datetime(2026, 8, 6, 22, 30), 1
            )
        with pytest.raises(ValueError, match="Zukunft"):
            start_recovery_run(
                Path(directory) / "future.sqlite3",
                datetime(2099, 1, 1, tzinfo=timezone.utc),
                1,
            )
