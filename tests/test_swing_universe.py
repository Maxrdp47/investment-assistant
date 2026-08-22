from pathlib import Path

from scripts.build_swing_universe import _nasdaq_global_select_rows
from swing_universe import (
    DEFAULT_SWING_UNIVERSE_PATH,
    active_swing_assets,
    is_forbidden_leveraged_asset,
    load_swing_universe,
    stable_swing_asset_id,
)


def test_production_universe_is_large_versioned_unique_and_contains_servicenow() -> None:
    report = load_swing_universe(DEFAULT_SWING_UNIVERSE_PATH)
    assets = active_swing_assets(report)

    assert report.errors == ()
    assert 2_000 <= report.active_count <= 3_000
    assert len({asset.ticker for asset in assets}) == len(assets)
    assert any(asset.ticker == "NOW" and asset.name == "ServiceNow" for asset in assets)
    assert all(asset.version for asset in assets)
    assert all(asset.name and asset.region and asset.category for asset in assets)
    assert all(asset.liquidity_class in {"A", "B", "C"} for asset in assets)
    assert len({asset.as_dict()["asset_id"] for asset in assets}) == len(assets)
    assert all(asset.as_dict()["identity_version"] for asset in assets)
    assert any(asset.ticker == "ROP.SW" and asset.name == "Roche" for asset in assets)
    assert not any(asset.ticker == "ROG.SW" for asset in assets)
    assert not any(
        is_forbidden_leveraged_asset(
            ticker=asset.ticker,
            name=asset.name,
            asset_type=asset.asset_type,
            category=asset.category,
        )
        for asset in assets
    )


def test_invalid_universe_rows_are_reported_without_discarding_valid_rows(tmp_path: Path) -> None:
    universe_path = tmp_path / "universe.csv"
    universe_path.write_text(
        "version,ticker,name,asset_type,region,category,active,liquidity_class,source_group\n"
        "v1,NOW,ServiceNow,Aktie,USA,Software,true,A,test\n"
        "v1,TQQQ,Leveraged ETF,ETF,USA,Leveraged 3x,true,A,test\n",
        encoding="utf-8",
    )

    report = load_swing_universe(universe_path, minimum_active_assets=1)

    assert [asset.ticker for asset in report.assets] == ["NOW"]
    assert report.forbidden_count == 1
    assert any("Hebel-/Inverse-Produkt" in error for error in report.errors)


def test_internal_asset_id_is_stable_and_changes_with_identity() -> None:
    first = stable_swing_asset_id("now", "Aktie", "USA")

    assert first == stable_swing_asset_id("NOW", "Aktie", "USA")
    assert first != stable_swing_asset_id("NOW", "ETF", "USA")
    assert first.startswith("swing-")


def test_nasdaq_global_select_source_keeps_only_normal_common_equities() -> None:
    source = [
        {
            "Symbol": "GOOD",
            "Security Name": "Good Company, Inc. - Common Stock",
            "Market Category": "Q",
            "Test Issue": "N",
            "Financial Status": "N",
            "ETF": "N",
        },
        {
            "Symbol": "WRT",
            "Security Name": "Example - Warrant",
            "Market Category": "Q",
            "Test Issue": "N",
            "Financial Status": "N",
            "ETF": "N",
        },
        {
            "Symbol": "LOW",
            "Security Name": "Lower Market Company - Common Stock",
            "Market Category": "S",
            "Test Issue": "N",
            "Financial Status": "N",
            "ETF": "N",
        },
    ]

    rows = _nasdaq_global_select_rows(source, universe_version="test-v1")

    assert [row["ticker"] for row in rows] == ["GOOD"]
    assert rows[0]["liquidity_class"] == "B"
    assert rows[0]["source_group"] == "Nasdaq Global Select Market"
