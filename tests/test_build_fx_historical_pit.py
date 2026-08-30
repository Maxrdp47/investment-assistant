from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.build_fx_historical_pit import build_historical_fx_foundation


STAMP = "2026-08-29T12:00:00+00:00"


def _loader(contract, start, end):
    assert start == "2020-01-01"
    assert end == "2020-01-03"
    return [
        {
            "date": "2020-01-01",
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
        }
    ]


def test_builder_stores_three_pairs_and_visible_missingness(tmp_path: Path) -> None:
    result = build_historical_fx_foundation(
        start="2020-01-01",
        end="2020-01-03",
        imported_at=STAMP,
        db_path=tmp_path / "historical.sqlite3",
        export_path=tmp_path / "artifact.json",
        history_loader=_loader,
    )
    assert result["inventory"]["record_n"] == 3
    assert result["inventory"]["pit_eligible_n"] == 3
    assert result["coverage"]["matrix"]["EUR/USD"]["2020"]["PRICE"] == "AVAILABLE_PIT"
    assert result["coverage"]["matrix"]["EUR/USD"]["2020"]["EXPECTED_RATE"] == "UNAVAILABLE"
    assert result["historical_vendor_first_seen_claimed"] is False
    assert result["multi_asset_scan_started"] is False

    second = build_historical_fx_foundation(
        start="2020-01-01",
        end="2020-01-03",
        imported_at="2026-08-30T12:00:00+00:00",
        db_path=tmp_path / "historical.sqlite3",
        export_path=tmp_path / "artifact-2.json",
        history_loader=_loader,
    )
    assert second["store_result"] == {"inserted": 0, "deduplicated": 3}
    assert second["inventory"]["record_n"] == 3


def test_canonical_new_york_close_is_timezone_aware_across_dst(tmp_path: Path) -> None:
    def dst_loader(contract, start, end):
        return [
            {"date": "2020-01-15", "open": 1, "high": 1.2, "low": 0.9, "close": 1.1},
            {"date": "2020-07-15", "open": 1, "high": 1.2, "low": 0.9, "close": 1.1},
        ]

    build_historical_fx_foundation(
        start="2020-01-01",
        end="2021-01-01",
        imported_at=STAMP,
        db_path=tmp_path / "historical.sqlite3",
        export_path=tmp_path / "artifact.json",
        history_loader=dst_loader,
    )
    import sqlite3, json

    with sqlite3.connect(tmp_path / "historical.sqlite3") as connection:
        rows = [json.loads(row[0]) for row in connection.execute("SELECT record_json FROM historical_fx_records")]
    eur = sorted(
        (row for row in rows if row["pair_id"] == "EUR/USD"),
        key=lambda row: row["observation_date"],
    )
    winter = datetime.fromisoformat(eur[0]["release_at"])
    summer = datetime.fromisoformat(eur[1]["release_at"])
    assert winter.hour == 22
    assert summer.hour == 21


def test_invalid_provider_bar_is_skipped_and_visible(tmp_path: Path) -> None:
    def bad_loader(contract, start, end):
        return [
            {"date": "2020-01-01", "open": 2, "high": 1.2, "low": 1, "close": 1.1}
        ]

    result = build_historical_fx_foundation(
        start="2020-01-01",
        end="2020-01-03",
        imported_at=STAMP,
        db_path=tmp_path / "historical.sqlite3",
        export_path=tmp_path / "artifact.json",
        history_loader=bad_loader,
    )
    assert result["inventory"]["record_n"] == 0
    assert result["source_health"]["EUR/USD"]["invalid_bar_n"] == 1
    assert result["source_health"]["EUR/USD"]["status"] == "SUCCESS_WITH_INVALID_BARS_SKIPPED"
