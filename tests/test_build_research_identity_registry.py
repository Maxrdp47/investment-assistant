from __future__ import annotations

import json
from pathlib import Path

from scripts.build_research_identity_registry import (
    build_and_store_registry,
    build_records,
    parse_sec_company_tickers,
)


STAMP = "2026-08-29T10:00:00+00:00"


def _sec_payload() -> bytes:
    return json.dumps(
        {
            "0": {"cik_str": 1001, "ticker": "AAA", "title": "Alpha Corp"},
            "1": {"cik_str": 1001, "ticker": "AAA.A", "title": "Alpha Corp Class A"},
            "2": {"cik_str": 2002, "ticker": "ETF1", "title": "Fund Trust"},
        }
    ).encode("utf-8")


def test_sec_parser_and_records_use_exact_ticker_cik_not_name_fuzziness() -> None:
    sec = parse_sec_company_tickers(_sec_payload())
    universe = [
        {"version": "v1", "ticker": "AAA", "name": "Different Display Name", "asset_type": "Aktie", "region": "USA", "source_group": "test"},
        {"version": "v1", "ticker": "BBB", "name": "Alpha Corp", "asset_type": "Aktie", "region": "USA", "source_group": "test"},
        {"version": "v1", "ticker": "ETF1", "name": "Fund Trust", "asset_type": "ETF", "region": "USA", "source_group": "test"},
    ]
    records = build_records(
        universe,
        sec,
        mapping_version="pytest-v1",
        imported_at=STAMP,
        source_snapshot_fingerprint="abc",
    )
    assert records[0]["issuer_id"] == "sec-cik:0000001001"
    assert records[1]["mapping_status"] == "UNRESOLVED"
    assert records[2]["mapping_status"] == "UNRESOLVED"


def test_registry_build_is_append_only_and_reports_unknowns(tmp_path: Path) -> None:
    universe = tmp_path / "universe.csv"
    universe.write_text(
        "version,ticker,name,asset_type,region,category,active,liquidity_class,source_group\n"
        "v1,AAA,Alpha,Aktie,USA,Test,true,A,test\n"
        "v1,BBB,Beta,Aktie,Europa,Test,true,A,test\n",
        encoding="utf-8",
    )
    arguments = {
        "universe_path": universe,
        "source_payload": _sec_payload(),
        "source_root": tmp_path / "sources",
        "registry_path": tmp_path / "identity.sqlite3",
        "export_path": tmp_path / "coverage.json",
        "mapping_version": "pytest-registry-v1",
        "imported_at": STAMP,
    }
    first = build_and_store_registry(**arguments)
    second = build_and_store_registry(**arguments)
    assert first == second
    assert first["verified_issuer_mapping_n"] == 1
    assert first["unresolved_mapping_n"] == 1
    assert first["dependency"]["unknown_counted_as_independent"] is False
    assert first["multi_asset_scan_started"] is False


def test_provider_failure_creates_only_visible_unresolved_mappings(tmp_path: Path) -> None:
    universe = tmp_path / "universe.csv"
    universe.write_text(
        "version,ticker,name,asset_type,region,category,active,liquidity_class,source_group\n"
        "v1,AAA,Alpha,Aktie,USA,Test,true,A,test\n",
        encoding="utf-8",
    )
    result = build_and_store_registry(
        universe_path=universe,
        source_payload=None,
        source_root=tmp_path / "sources",
        registry_path=tmp_path / "identity.sqlite3",
        export_path=tmp_path / "coverage.json",
        mapping_version="pytest-unresolved-v1",
        imported_at=STAMP,
        source_error="HTTPError: 403",
    )
    assert result["source_status"] == "PROVIDER_FAILURE"
    assert result["verified_issuer_mapping_n"] == 0
    assert result["unresolved_mapping_n"] == 1
    assert result["dependency"]["effective_n_known_issuers_only"] == 0
    assert result["dependency"]["unknown_counted_as_independent"] is False
