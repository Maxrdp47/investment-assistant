from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from scripts.complete_multi_asset_prerequisites import (
    FAILED_SELLER_REQUEST_ID,
    FIBONACCI_REQUEST_ID,
    FX_CARRY_REQUEST_ID,
    GOLD_SILVER_REQUEST_ID,
    WATER_REQUEST_ID,
    build_fibonacci_reuse,
    build_identity_gate,
    complete_all,
)


ROOT = Path(__file__).resolve().parents[1]


def _status(path: Path, request_id: str) -> tuple[str, str | None]:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT current_status, result_id FROM research_work_requests WHERE id=?",
            (request_id,),
        ).fetchone()
    assert row is not None
    return str(row[0]), None if row[1] is None else str(row[1])


def _failed_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "COMPLETED_DEVELOPMENT_ONLY",
                "run_id": "pytest-failed-seller-run",
                "multi_asset_scan_started": False,
                "result": {
                    "result_direction": "INCONCLUSIVE",
                    "valid_feature_n": 12,
                    "baseline": {
                        "hit_rate_pct": 50.0,
                        "expectancy_r": 0.0,
                        "profit_factor": 1.0,
                        "average_mfe_pct": 2.0,
                        "average_mae_pct": -1.0,
                    },
                    "variants": {},
                    "validation_opened": False,
                    "holdout_opened": False,
                    "strategy_activated": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_identity_and_fibonacci_contracts_are_explicit() -> None:
    identity = build_identity_gate(created_at="2026-08-28T00:00:00+00:00")
    assert identity["issuer_resolution"]["unknown_assumed_independent"] is False
    assert identity["multi_asset_scan_started"] is False

    fibonacci = build_fibonacci_reuse(created_at="2026-08-28T00:00:00+00:00")
    assert fibonacci["new_research_run_started"] is False
    assert fibonacci["contract_identity"]["equal_width_controls"] == [
        [0.45, 0.618],
        [0.786, 0.954],
    ]
    assert fibonacci["existing_development_result"]["conclusion"] == (
        "INCONCLUSIVE_DEVELOPMENT_B_ONLY"
    )


def test_completion_is_idempotent_and_leaves_other_ready_requests_untouched(
    tmp_path: Path,
) -> None:
    kb = tmp_path / "research_knowledge.sqlite3"
    shutil.copy2(ROOT / "runtime" / "research_knowledge.sqlite3", kb)
    report = tmp_path / "failed.json"
    _failed_report(report)
    export_root = tmp_path / "exports"
    fx_database = tmp_path / "fx.sqlite3"

    first = complete_all(
        knowledge_base=kb,
        export_root=export_root,
        fx_database=fx_database,
        failed_seller_report=report,
        completed_at="2026-08-28T00:00:00+00:00",
    )
    result_ids = {
        request_id: _status(kb, request_id)[1]
        for request_id in (FIBONACCI_REQUEST_ID, FX_CARRY_REQUEST_ID, FAILED_SELLER_REQUEST_ID)
    }
    second = complete_all(
        knowledge_base=kb,
        export_root=export_root,
        fx_database=fx_database,
        failed_seller_report=report,
        completed_at="2026-08-28T00:00:00+00:00",
    )

    assert first["multi_asset_scan_started"] is False
    assert second["multi_asset_scan_started"] is False
    assert second["idempotent_replay"] is True
    assert second["artifact_fingerprint"] == first["artifact_fingerprint"]
    for request_id, result_id in result_ids.items():
        assert _status(kb, request_id) == ("COMPLETED", result_id)
        with sqlite3.connect(kb) as connection:
            result_n = connection.execute(
                "SELECT COUNT(*) FROM research_result_identities WHERE idempotency_key=?",
                (f"work_request:{request_id}",),
            ).fetchone()[0]
            request_artifacts = connection.execute(
                "SELECT artifact_references_json FROM research_work_requests WHERE id=?",
                (request_id,),
            ).fetchone()[0]
        assert result_n == 1
        assert json.loads(request_artifacts)
    assert _status(kb, GOLD_SILVER_REQUEST_ID) == ("READY", None)
    assert _status(kb, WATER_REQUEST_ID) == ("READY", None)
