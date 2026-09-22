from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from overnight_intraday_r3 import DEFAULT_CONTRACT, digest
from scripts.sync_overnight_intraday_r3_kb import verified_review


def _store(tmp_path: Path) -> tuple[dict, str, Path, dict]:
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    fingerprint = digest(contract)
    path = tmp_path / "review.sqlite3"
    review = {
        "version": contract["version"],
        "status": "DEVELOPMENT_DESCRIPTIVE_ONLY_SEEN_DATA",
        "source_assets": 1,
        "source_bars": 50,
        "development": [],
        "validation": "NOT_OPENED",
        "holdout": "NOT_OPENED",
        "robust_challenger_eligible": False,
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE run_manifest(version TEXT, contract_fingerprint TEXT, source_dataset_fingerprint TEXT)"
        )
        connection.execute("CREATE TABLE asset_progress(asset_key TEXT, source_bar_count INTEGER)")
        connection.execute("CREATE TABLE final_review(version TEXT, review_json TEXT, review_digest TEXT)")
        connection.execute(
            "INSERT INTO run_manifest VALUES (?,?,?)",
            (contract["version"], fingerprint, contract["source"]["dataset_fingerprint"]),
        )
        connection.execute("INSERT INTO asset_progress VALUES (?,?)", ("a", 50))
        connection.execute(
            "INSERT INTO final_review VALUES (?,?,?)",
            (contract["version"], json.dumps(review), digest(review)),
        )
    return contract, fingerprint, path, review


def test_verified_review_accepts_only_complete_seen_development(tmp_path: Path) -> None:
    contract, fingerprint, path, review = _store(tmp_path)
    assert verified_review(contract, fingerprint, path) == (review, digest(review))
    with sqlite3.connect(path) as connection:
        changed = dict(review, validation="OPENED")
        connection.execute(
            "UPDATE final_review SET review_json=?,review_digest=?",
            (json.dumps(changed), digest(changed)),
        )
    with pytest.raises(RuntimeError, match="safety gate"):
        verified_review(contract, fingerprint, path)


def test_verified_review_rejects_fingerprint_and_coverage_drift(tmp_path: Path) -> None:
    contract, fingerprint, path, review = _store(tmp_path)
    with pytest.raises(RuntimeError, match="manifest mismatch"):
        verified_review(contract, "different", path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE asset_progress SET source_bar_count=49")
    with pytest.raises(RuntimeError, match="does not cover"):
        verified_review(contract, fingerprint, path)
