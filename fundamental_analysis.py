from __future__ import annotations

import numpy as np
import pandas as pd

from analysis_models import EtfFundamentalSnapshot, ModuleScore, StockFundamentalSnapshot
from currency_utils import format_currency
from technical_analysis import clamp, value_or_none


def format_percent_or_missing(value: float | None) -> str:
    if value is None:
        return "Daten nicht verfügbar"
    return f"{value * 100:.1f}%"


def format_money_or_missing(value: float | None) -> str:
    if value is None:
        return "Daten nicht verfügbar"
    return format_currency(value)


def data_missing(label: str) -> str:
    return f"{label}: Daten nicht verfügbar."


def score_profitability_metric(value: float) -> float:
    if value >= 0.20:
        return 8.5
    if value >= 0.10:
        return 7.0
    if value >= 0.03:
        return 5.5
    if value >= 0:
        return 4.5
    return 2.5


def stock_fundamental_snapshot(info: dict) -> StockFundamentalSnapshot:
    return StockFundamentalSnapshot(
        revenue_growth=value_or_none(info.get("revenueGrowth")),
        earnings_growth=value_or_none(info.get("earningsGrowth")),
        profit_margin=value_or_none(info.get("profitMargins")),
        operating_margin=value_or_none(info.get("operatingMargins")),
        gross_margin=value_or_none(info.get("grossMargins")),
        return_on_equity=value_or_none(info.get("returnOnEquity")),
        return_on_assets=value_or_none(info.get("returnOnAssets")),
        total_cash=value_or_none(info.get("totalCash")),
        total_debt=value_or_none(info.get("totalDebt")),
        free_cashflow=value_or_none(info.get("freeCashflow")),
        operating_cashflow=value_or_none(info.get("operatingCashflow")),
        trailing_pe=value_or_none(info.get("trailingPE")),
        forward_pe=value_or_none(info.get("forwardPE")),
        price_to_sales=value_or_none(info.get("priceToSalesTrailing12Months")),
        price_to_book=value_or_none(info.get("priceToBook")),
        enterprise_to_ebitda=value_or_none(info.get("enterpriseToEbitda")),
        market_cap=value_or_none(info.get("marketCap")),
    )


def score_valuation_multiple(
    value: float | None,
    thresholds: tuple[float, float, float],
) -> tuple[float | None, str]:
    if value is None or value <= 0:
        return None, "Daten nicht verfügbar"
    cheap, fair, expensive = thresholds
    if value <= cheap:
        return 8.0, "günstig"
    if value <= fair:
        return 6.5, "fair"
    if value <= expensive:
        return 4.5, "teuer"
    return 3.0, "sehr teuer"


def stock_fundamental_overview(snapshot: StockFundamentalSnapshot) -> list[str]:
    net_cash_text = "Daten nicht verfügbar"
    if snapshot.total_cash is not None and snapshot.total_debt is not None:
        net_cash_text = format_currency(snapshot.total_cash - snapshot.total_debt)
    return [
        f"Umsatzwachstum: {format_percent_or_missing(snapshot.revenue_growth)}.",
        f"Gewinnwachstum: {format_percent_or_missing(snapshot.earnings_growth)}.",
        f"Nettomarge: {format_percent_or_missing(snapshot.profit_margin)}.",
        f"Operative Marge: {format_percent_or_missing(snapshot.operating_margin)}.",
        f"Bruttomarge: {format_percent_or_missing(snapshot.gross_margin)}.",
        f"Free Cashflow: {format_money_or_missing(snapshot.free_cashflow)}.",
        f"Operativer Cashflow: {format_money_or_missing(snapshot.operating_cashflow)}.",
        f"Cashbestand: {format_money_or_missing(snapshot.total_cash)}.",
        f"Verschuldung: {format_money_or_missing(snapshot.total_debt)}.",
        f"Netto-Cash / Netto-Schulden: {net_cash_text}.",
        f"KGV: {'Daten nicht verfügbar' if snapshot.trailing_pe is None else f'{snapshot.trailing_pe:.1f}'}",
        f"Forward-KGV: {'Daten nicht verfügbar' if snapshot.forward_pe is None else f'{snapshot.forward_pe:.1f}'}",
        (
            "Kurs-Umsatz-Verhältnis: Daten nicht verfügbar"
            if snapshot.price_to_sales is None
            else f"Kurs-Umsatz-Verhältnis: {snapshot.price_to_sales:.1f}"
        ),
        (
            "Kurs-Buchwert-Verhältnis: Daten nicht verfügbar"
            if snapshot.price_to_book is None
            else f"Kurs-Buchwert-Verhältnis: {snapshot.price_to_book:.1f}"
        ),
        (
            "EV/EBITDA: Daten nicht verfügbar"
            if snapshot.enterprise_to_ebitda is None
            else f"EV/EBITDA: {snapshot.enterprise_to_ebitda:.1f}"
        ),
    ]


def etf_fundamental_snapshot(info: dict) -> EtfFundamentalSnapshot:
    return EtfFundamentalSnapshot(
        category=info.get("category") or None,
        fund_family=info.get("fundFamily") or None,
        annual_report_expense_ratio=value_or_none(info.get("annualReportExpenseRatio")),
        expense_ratio=value_or_none(info.get("expenseRatio")),
        total_assets=value_or_none(info.get("totalAssets")),
        net_assets=value_or_none(info.get("netAssets")),
        holdings_count=value_or_none(info.get("holdingsCount") or info.get("numberOfHoldings")),
        fifty_two_week_change=value_or_none(info.get("52WeekChange")),
        three_year_return=value_or_none(info.get("threeYearAverageReturn")),
        five_year_return=value_or_none(info.get("fiveYearAverageReturn")),
        beta_3y=value_or_none(info.get("beta3Year")),
        ytd_return=value_or_none(info.get("ytdReturn")),
    )


def etf_fundamental_overview(snapshot: EtfFundamentalSnapshot) -> list[str]:
    ter = snapshot.annual_report_expense_ratio or snapshot.expense_ratio
    assets = snapshot.total_assets or snapshot.net_assets
    return [
        f"ETF-Kategorie / Region / Sektor: {snapshot.category or 'Daten nicht verfügbar'}.",
        f"Fondsgesellschaft: {snapshot.fund_family or 'Daten nicht verfügbar'}.",
        f"TER/Kostenquote: {format_percent_or_missing(ter)}.",
        f"Fondsvolumen: {format_money_or_missing(assets)}.",
        (
            "Diversifikation / Anzahl Positionen: Daten nicht verfügbar."
            if snapshot.holdings_count is None
            else f"Diversifikation / Anzahl Positionen: {snapshot.holdings_count:.0f}."
        ),
        f"1J-Performance: {format_percent_or_missing(snapshot.fifty_two_week_change)}.",
        f"YTD-Performance: {format_percent_or_missing(snapshot.ytd_return)}.",
        f"3J-Durchschnittsrendite: {format_percent_or_missing(snapshot.three_year_return)}.",
        f"5J-Durchschnittsrendite: {format_percent_or_missing(snapshot.five_year_return)}.",
        "Beta 3 Jahre: Daten nicht verfügbar."
        if snapshot.beta_3y is None
        else f"Beta 3 Jahre: {snapshot.beta_3y:.2f}.",
    ]


def score_stock_fundamentals(info: dict) -> ModuleScore:
    snapshot = stock_fundamental_snapshot(info)
    details: list[str] = []
    points: list[float] = []

    revenue_growth = snapshot.revenue_growth
    if revenue_growth is not None:
        score = clamp(5 + revenue_growth * 20)
        points.append(score)
        details.append(f"Umsatzwachstum: {revenue_growth * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Umsatzwachstum"))

    earnings_growth = snapshot.earnings_growth
    if earnings_growth is not None:
        score = clamp(5 + earnings_growth * 18)
        points.append(score)
        details.append(f"Gewinnwachstum: {earnings_growth * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Gewinnwachstum"))

    cash = snapshot.total_cash
    debt = snapshot.total_debt
    if cash is not None and debt is not None:
        cash_debt = cash / debt if debt > 0 else 3.0
        score = clamp(3 + cash_debt * 3)
        points.append(score)
        details.append(f"Cash/Verschuldung: {cash_debt:.2f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Cashbestand oder Verschuldung"))

    free_cashflow = snapshot.free_cashflow
    if free_cashflow is not None:
        score = 8.0 if free_cashflow > 0 else 3.0
        points.append(score)
        details.append(f"Free Cashflow: {format_currency(free_cashflow)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Free Cashflow"))

    margin_candidates = [
        ("Nettomarge", snapshot.profit_margin),
        ("Operative Marge", snapshot.operating_margin),
        ("Bruttomarge", snapshot.gross_margin),
    ]
    margin_label = None
    margin_value = None
    for label, raw_value in margin_candidates:
        parsed_value = value_or_none(raw_value)
        if parsed_value is not None:
            margin_label = label
            margin_value = parsed_value
            break
    if margin_value is not None and margin_label is not None:
        score = score_profitability_metric(margin_value)
        points.append(score)
        details.append(f"{margin_label}: {margin_value * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Marge"))

    roe = snapshot.return_on_equity
    roa = snapshot.return_on_assets
    if roe is not None:
        score = score_profitability_metric(roe)
        points.append(score)
        details.append(f"Eigenkapitalrendite: {roe * 100:.1f}% -> {score:.1f}/10.")
    elif roa is not None:
        score = score_profitability_metric(roa)
        points.append(score)
        details.append(f"Kapitalrendite: {roa * 100:.1f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("Eigenkapitalrendite / Kapitalrendite"))

    pe = snapshot.trailing_pe or snapshot.forward_pe
    if pe is not None and pe > 0:
        if pe <= 15:
            score = 8.0
        elif pe <= 30:
            score = 6.5
        elif pe <= 60:
            score = 4.5
        else:
            score = 3.0
        points.append(score)
        details.append(f"KGV: {pe:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("KGV"))

    price_to_sales = snapshot.price_to_sales
    if price_to_sales is not None and price_to_sales > 0:
        score = (
            8.0
            if price_to_sales <= 3
            else 6.5
            if price_to_sales <= 8
            else 4.5
            if price_to_sales <= 15
            else 3.0
        )
        points.append(score)
        details.append(f"Kurs-Umsatz-Verhältnis: {price_to_sales:.1f} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Kurs-Umsatz-Verhältnis"))

    price_to_book_score, price_to_book_label = score_valuation_multiple(
        snapshot.price_to_book,
        (2.5, 5.0, 10.0),
    )
    if price_to_book_score is not None:
        points.append(price_to_book_score)
        details.append(
            f"Kurs-Buchwert-Verhältnis: {snapshot.price_to_book:.1f} ({price_to_book_label}) -> "
            f"{price_to_book_score:.1f}/10."
        )
    else:
        details.append(data_missing("Kurs-Buchwert-Verhältnis"))

    ev_ebitda_score, ev_ebitda_label = score_valuation_multiple(
        snapshot.enterprise_to_ebitda,
        (10.0, 18.0, 30.0),
    )
    if ev_ebitda_score is not None:
        points.append(ev_ebitda_score)
        details.append(
            f"EV/EBITDA: {snapshot.enterprise_to_ebitda:.1f} ({ev_ebitda_label}) -> "
            f"{ev_ebitda_score:.1f}/10."
        )
    else:
        details.append(data_missing("EV/EBITDA"))

    market_cap = snapshot.market_cap
    if market_cap is not None:
        score = 7.5 if market_cap >= 10_000_000_000 else 6.0 if market_cap >= 1_000_000_000 else 4.5
        points.append(score)
        details.append(f"Marktkapitalisierung: {format_currency(market_cap)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Marktkapitalisierung"))

    if not points:
        return ModuleScore(
            5.0,
            "Aktien-Fundamentaldaten nicht ausreichend verfügbar. Der Score wird neutral gewertet.",
            details,
        )

    details.extend(stock_fundamental_overview(snapshot))
    final_score = round(float(np.mean(points)), 1)
    return ModuleScore(
        final_score,
        f"Aktien-Fundamentalscore {final_score}/10 aus {len(points)} verfügbaren Kennzahlen.",
        details,
    )


def score_etf_fundamentals(info: dict, df: pd.DataFrame | None = None) -> ModuleScore:
    snapshot = etf_fundamental_snapshot(info)
    details: list[str] = []
    points: list[float] = []

    category = snapshot.category or snapshot.fund_family
    details.append(f"Index/Region/Sektor: {category}" if category else data_missing("Index/Region/Sektor"))

    ter = snapshot.annual_report_expense_ratio or snapshot.expense_ratio
    if ter is not None:
        score = 8.5 if ter <= 0.0025 else 7.0 if ter <= 0.006 else 5.0 if ter <= 0.012 else 3.5
        points.append(score)
        details.append(f"TER/Kostenquote: {ter * 100:.2f}% -> {score:.1f}/10.")
    else:
        details.append(data_missing("TER/Kostenquote"))

    total_assets = snapshot.total_assets or snapshot.net_assets
    if total_assets is not None:
        score = 8.0 if total_assets >= 5_000_000_000 else 6.5 if total_assets >= 500_000_000 else 4.5
        points.append(score)
        details.append(f"Fondsvolumen: {format_currency(total_assets)} -> {score:.1f}/10.")
    else:
        details.append(data_missing("Fondsvolumen"))

    holdings = snapshot.holdings_count
    if holdings is not None:
        score = 8.0 if holdings >= 500 else 6.5 if holdings >= 100 else 4.5
        points.append(score)
        details.append(f"Diversifikation: {holdings:.0f} Positionen -> {score:.1f}/10.")
    else:
        details.append(data_missing("Diversifikation / Anzahl Positionen"))

    performance_metrics = [
        ("1J-Performance", snapshot.fifty_two_week_change),
        ("YTD-Performance", snapshot.ytd_return),
        ("3J-Performance", snapshot.three_year_return),
        ("5J-Performance", snapshot.five_year_return),
    ]
    for label, performance in performance_metrics:
        if performance is not None:
            score = clamp(5 + performance * 20)
            points.append(score)
            details.append(f"{label}: {performance * 100:.1f}% -> {score:.1f}/10.")
        else:
            details.append(data_missing(label))

    if snapshot.beta_3y is not None:
        beta_score = 8.0 if snapshot.beta_3y <= 1.0 else 6.5 if snapshot.beta_3y <= 1.2 else 5.0
        points.append(beta_score)
        details.append(f"Beta 3 Jahre: {snapshot.beta_3y:.2f} -> {beta_score:.1f}/10.")
    else:
        details.append(data_missing("Beta 3 Jahre"))

    if df is not None and not df.empty and "Volatility" in df.columns:
        volatility = value_or_none(df.iloc[-1].get("Volatility"))
        if volatility is not None:
            score = 8.0 if volatility <= 0.18 else 6.5 if volatility <= 0.28 else 5.0 if volatility <= 0.45 else 3.5
            points.append(score)
            details.append(
                f"Langfristige Stabilität: Volatilität {volatility * 100:.1f}% -> {score:.1f}/10."
            )
        else:
            details.append(data_missing("Langfristige Stabilität / Volatilität"))
    else:
        details.append(data_missing("Langfristige Stabilität / Volatilität"))

    if not points:
        return ModuleScore(
            5.0,
            "ETF-Daten nicht ausreichend verfügbar. Der Score wird neutral gewertet.",
            details,
        )

    details.extend(etf_fundamental_overview(snapshot))
    final_score = round(float(np.mean(points)), 1)
    return ModuleScore(
        final_score,
        f"ETF-Score {final_score}/10 aus verfügbaren Struktur- und Performance-Daten.",
        details,
    )
