from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from overnight_intraday_r3 import (
    DEFAULT_CONTRACT,
    asset_summaries,
    digest,
    load_contract,
    run,
    source_connection,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "frozen.sqlite3"
    result = tmp_path / "r3.sqlite3"
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["source"]["path"] = str(source)
    contract["source"]["dataset_fingerprint"] = "test-frozen-fingerprint"
    contract["runtime"]["result_store"] = str(result)
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE projection_versions(version TEXT, dataset_fingerprint TEXT)")
        connection.execute(
            "INSERT INTO projection_versions VALUES (?,?)",
            (contract["source"]["projection_version"], "test-frozen-fingerprint"),
        )
        connection.execute(
            "CREATE TABLE active_bars(asset_id TEXT, listing_id TEXT, asset_class TEXT, "
            "session_date TEXT, open REAL, high REAL, low REAL, close REAL)"
        )
        for asset_id, offset in (("a", 0), ("b", 2)):
            for day in range(90):
                date = (pd.Timestamp("2016-01-04") + pd.offsets.BDay(day)).date().isoformat()
                close = 100 + offset + day * 0.3 + (day % 7) * 0.09
                opening = close - 0.1 + (day % 5) * 0.03
                connection.execute(
                    "INSERT INTO active_bars VALUES (?,?,?,?,?,?,?,?)",
                    (asset_id, None, "EQUITIES", date, opening, close + 0.2, opening - 0.2, close),
                )
    return contract_path, source, result


def test_contract_and_source_fingerprint_are_fail_closed(tmp_path: Path) -> None:
    contract_path, source, result = _fixture(tmp_path)
    contract, fingerprint = load_contract(contract_path)
    assert fingerprint == digest(contract)
    with source_connection(contract) as connection:
        rows, count = asset_summaries(
            connection, asset_id="a", listing_id=None, asset_class="EQUITIES", contract=contract
        )
    assert count == 90
    assert {row["horizon_sessions"] for row in rows} == {1, 5, 20}
    assert all(row["seen_data_only"] for row in rows)
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE projection_versions SET dataset_fingerprint='altered'")
    with pytest.raises(RuntimeError, match="fingerprint mismatch"):
        run(contract_path)
    assert not result.exists()


def test_single_attempt_resume_and_terminal_no_op(tmp_path: Path) -> None:
    contract_path, source, result_path = _fixture(tmp_path)
    first = run(contract_path, max_assets=1)
    assert first["completed_assets"] == 1
    assert first["complete"] is False
    second = run(contract_path)
    assert second["complete"] is True
    assert second["review"]["source_assets"] == 2
    assert second["review"]["source_bars"] == 180
    assert second["review"]["validation"] == "NOT_OPENED"
    assert second["review"]["robust_challenger_eligible"] is False
    with sqlite3.connect(result_path) as connection:
        before = [connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("asset_progress", "summaries", "final_review")]
    assert before == [2, 6, 1]
    assert run(contract_path)["terminal_no_op"] is True
    with sqlite3.connect(result_path) as connection:
        after = [connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("asset_progress", "summaries", "final_review")]
    assert after == before
    assert source.exists()


def test_production_pause_does_not_add_partial_asset(tmp_path: Path) -> None:
    contract_path, _, result_path = _fixture(tmp_path)
    paused = run(contract_path, should_pause=lambda: True)
    assert paused["paused_for_production"] is True
    assert paused["completed_assets"] == 0
    with sqlite3.connect(result_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 0
