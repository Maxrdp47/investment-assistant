from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from analysis_models import AssetProfile, PortfolioResult
from technical_analysis import clamp, value_or_none


PositionValueLoader = Callable[[dict], float]


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def load_portfolio_file(path: Path) -> tuple[dict | None, str | None]:
    """Load an optional portfolio document without changing or creating it."""
    if not path.exists():
        return None, "Keine Portfolio-Datei gefunden. Portfolio-Modus kann nicht verwendet werden."
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return None, "portfolio.json ist ungültig. Erwartet wird ein JSON-Objekt."
        return data, None
    except json.JSONDecodeError as exc:
        return None, f"portfolio.json ist kein gültiges JSON: {exc}"
    except OSError as exc:
        return None, f"portfolio.json konnte nicht gelesen werden: {exc}"


def portfolio_positions(portfolio: dict) -> list[dict]:
    positions = portfolio.get("positions", [])
    if not isinstance(positions, list):
        return []
    return [position for position in positions if isinstance(position, dict)]


def portfolio_position_ticker(position: dict) -> str:
    return str(position.get("ticker") or position.get("symbol") or "").strip()


def portfolio_position_shares(position: dict) -> float | None:
    return value_or_none(position.get("shares") or position.get("quantity"))


def portfolio_position_buy_price(position: dict) -> float | None:
    return value_or_none(position.get("buy_price") or position.get("average_buy_price"))


def position_market_value(
    position: dict,
    latest_price_loader: Callable[[str], float | None] | None = None,
) -> float:
    value = value_or_none(position.get("market_value"))
    if value is not None:
        return value
    quantity = portfolio_position_shares(position)
    price = value_or_none(position.get("current_price") or position.get("price"))
    if price is None and quantity is not None and latest_price_loader is not None:
        symbol = portfolio_position_ticker(position)
        price = latest_price_loader(symbol) if symbol else None
    if quantity is not None and price is not None:
        return quantity * price
    return 0.0


def _format_currency(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def evaluate_portfolio_data(
    symbol: str,
    portfolio: dict,
    asset_profile: AssetProfile | None = None,
    *,
    position_value_loader: PositionValueLoader = position_market_value,
) -> PortfolioResult:
    """Evaluate portfolio effects from already loaded data, independently of UI and I/O."""
    positions = portfolio_positions(portfolio)
    cash = value_or_none(portfolio.get("cash")) or 0.0
    target_cash_pct = value_or_none(portfolio.get("target_cash_pct"))
    if target_cash_pct is None:
        target_cash_pct = 0.10
    planned_buy = value_or_none(portfolio.get("planned_buy_amount")) or 0.0
    overweight_limit = value_or_none(portfolio.get("max_single_position_pct"))
    if overweight_limit is None:
        overweight_limit = 0.20

    total_positions = sum(position_value_loader(position) for position in positions)
    total_value = total_positions + cash
    if total_value <= 0:
        return PortfolioResult(
            enabled=True,
            available=True,
            score=5.0,
            summary="Portfolio-Datei gefunden, aber Gesamtwert ist 0. Depot-Score wird neutral bewertet.",
            details=["Bitte market_value oder quantity/current_price in portfolio.json eintragen."],
            cash_weight=None,
        )

    symbol_norm = normalize_symbol(symbol)
    matching_positions = [
        position for position in positions if normalize_symbol(portfolio_position_ticker(position)) == symbol_norm
    ]
    position_value = sum(position_value_loader(position) for position in matching_positions)
    asset_weight = position_value / total_value
    cash_weight = cash / total_value
    post_buy_total = total_value + planned_buy
    post_buy_position = position_value + planned_buy
    post_buy_weight = post_buy_position / post_buy_total if post_buy_total > 0 else asset_weight
    post_buy_cash_weight = max(cash - planned_buy, 0.0) / post_buy_total if post_buy_total > 0 else cash_weight

    score = 10.0
    details: list[str] = []
    if matching_positions:
        details.append(
            f"Du hältst dieses Asset bereits: {_format_currency(position_value)} "
            f"({asset_weight * 100:.1f}% des Portfolios)."
        )
        for position in matching_positions:
            avg_buy_price = portfolio_position_buy_price(position)
            if avg_buy_price is not None:
                details.append(
                    f"Durchschnittlicher Einstandskurs laut portfolio.json: {_format_currency(avg_buy_price)}."
                )
            lots = position.get("lots")
            if isinstance(lots, list) and lots:
                details.append(f"Einzelkäufe erfasst: {len(lots)} Lots.")
    else:
        details.append("Du hältst dieses Asset laut portfolio.json noch nicht.")

    if asset_weight > overweight_limit:
        penalty = min(4.0, (asset_weight - overweight_limit) * 25)
        score -= penalty
        details.append(
            f"Übergewichtet: aktueller Anteil {asset_weight * 100:.1f}% liegt über dem Limit von "
            f"{overweight_limit * 100:.1f}%."
        )
    else:
        details.append(
            f"Kein Klumpenrisiko nach Limit: aktueller Anteil {asset_weight * 100:.1f}% von maximal "
            f"{overweight_limit * 100:.1f}%."
        )

    if planned_buy > 0:
        details.append(f"Geplanter Nachkauf aus portfolio.json: {_format_currency(planned_buy)}.")
        if post_buy_weight > overweight_limit:
            penalty = min(3.0, (post_buy_weight - overweight_limit) * 25)
            score -= penalty
            details.append(
                f"Nachkauf würde den Anteil auf {post_buy_weight * 100:.1f}% erhöhen und damit das Risiko steigern."
            )
        else:
            details.append(
                f"Nachkauf würde den Anteil auf {post_buy_weight * 100:.1f}% erhöhen und bleibt unter dem Limit."
            )
        if post_buy_cash_weight < target_cash_pct:
            penalty = min(2.5, (target_cash_pct - post_buy_cash_weight) * 20)
            score -= penalty
            details.append(
                f"Cash-Reserve nach Nachkauf wäre {post_buy_cash_weight * 100:.1f}% und damit unter Ziel "
                f"{target_cash_pct * 100:.1f}%."
            )
        else:
            details.append(
                f"Cash-Reserve nach Nachkauf bleibt bei {post_buy_cash_weight * 100:.1f}% und damit ausreichend."
            )
    else:
        details.append(
            "Kein geplanter Nachkaufbetrag eingetragen. Nachkauf-Risiko wird nur anhand der aktuellen "
            "Gewichtung bewertet."
        )
        if cash_weight < target_cash_pct:
            penalty = min(2.0, (target_cash_pct - cash_weight) * 20)
            score -= penalty
            details.append(
                f"Cash-Reserve ist niedrig: {cash_weight * 100:.1f}% statt Ziel {target_cash_pct * 100:.1f}%."
            )
        else:
            details.append(
                f"Cash-Reserve ist ausreichend: {cash_weight * 100:.1f}% bei Ziel {target_cash_pct * 100:.1f}%."
            )

    if asset_profile and asset_profile.asset_type == "Krypto" and asset_weight > 0.15:
        score -= 1.0
        details.append(
            "Krypto-Anteil ist hoch; wegen hoher Schwankungen wird ein zusätzlicher Risikoabschlag berücksichtigt."
        )

    score = round(clamp(score), 1)
    if score >= 7:
        summary = "Depot-Score positiv: Portfolio spricht nicht gegen die Asset-Empfehlung."
    elif score >= 5:
        summary = "Depot-Score neutral: Nachkauf nur vorsichtig, Portfolio-Risiken sind moderat."
    else:
        summary = "Depot-Score schwach: Portfolio spricht gegen einen zusätzlichen Nachkauf."

    return PortfolioResult(
        enabled=True,
        available=True,
        score=score,
        summary=summary,
        details=details,
        asset_weight=asset_weight,
        cash_weight=cash_weight,
        position_value=position_value,
    )
