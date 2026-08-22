from __future__ import annotations

import json
from pathlib import Path

import app
from analysis_models import AssetProfile
from portfolio_analysis import (
    evaluate_portfolio_data,
    load_portfolio_file,
    normalize_symbol,
    portfolio_positions,
    position_market_value,
)


def test_portfolio_loader_is_read_only_and_reports_invalid_documents(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.json"

    portfolio, error = load_portfolio_file(path)
    assert portfolio is None
    assert error == "Keine Portfolio-Datei gefunden. Portfolio-Modus kann nicht verwendet werden."
    assert not path.exists()

    path.write_text("[]", encoding="utf-8")
    portfolio, error = load_portfolio_file(path)
    assert portfolio is None
    assert error == "portfolio.json ist ungültig. Erwartet wird ein JSON-Objekt."

    document = {"cash": 500, "positions": [{"ticker": "NVDA", "shares": 2}]}
    path.write_text(json.dumps(document), encoding="utf-8")
    portfolio, error = load_portfolio_file(path)
    assert portfolio == document
    assert error is None


def test_portfolio_helpers_normalize_and_ignore_invalid_positions() -> None:
    assert normalize_symbol(" nvda ") == "NVDA"
    assert portfolio_positions({"positions": [None, {"ticker": "NVDA"}, "BTC-EUR"]}) == [
        {"ticker": "NVDA"}
    ]
    assert portfolio_positions({"positions": "invalid"}) == []


def test_position_market_value_prefers_saved_values_and_supports_injected_prices() -> None:
    price_requests: list[str] = []

    def latest_price(symbol: str) -> float:
        price_requests.append(symbol)
        return 125.0

    assert position_market_value({"market_value": 750, "ticker": "NVDA"}, latest_price) == 750.0
    assert price_requests == []
    assert position_market_value({"ticker": "NVDA", "shares": 2}, latest_price) == 250.0
    assert price_requests == ["NVDA"]
    assert position_market_value({"ticker": "NVDA"}, latest_price) == 0.0


def test_portfolio_evaluation_penalizes_concentration_and_high_crypto_weight() -> None:
    portfolio = {
        "cash": 1_000,
        "target_cash_pct": 0.20,
        "planned_buy_amount": 500,
        "max_single_position_pct": 0.40,
        "positions": [
            {
                "ticker": "BTC-EUR",
                "market_value": 1_000,
                "buy_price": 25_000,
                "lots": [{"shares": 0.01}, {"shares": 0.02}],
            }
        ],
    }
    profile = AssetProfile("Krypto", "CRYPTOCURRENCY", "Krypto", {})

    result = evaluate_portfolio_data(" btc-eur ", portfolio, profile)

    assert result.enabled is True
    assert result.available is True
    assert result.score == 3.5
    assert result.asset_weight == 0.5
    assert result.cash_weight == 0.5
    assert result.position_value == 1_000
    assert result.summary == "Depot-Score schwach: Portfolio spricht gegen einen zusätzlichen Nachkauf."
    assert any("Übergewichtet" in detail for detail in result.details)
    assert any("Einzelkäufe erfasst: 2" in detail for detail in result.details)
    assert any("Krypto-Anteil ist hoch" in detail for detail in result.details)


def test_app_portfolio_interface_remains_compatible_after_extraction(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "portfolio.json"
    path.write_text(
        json.dumps(
            {
                "cash": 100,
                "positions": [{"ticker": "NVDA", "shares": 2, "current_price": 50}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(app, "PORTFOLIO_PATH", path)

    result = app.evaluate_portfolio("NVDA", True, 8.0)

    assert result.available is True
    assert result.position_value == 100.0
    assert result.asset_weight == 0.5
    assert app.normalize_symbol(" nvda ") == "NVDA"
