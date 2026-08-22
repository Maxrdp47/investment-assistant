from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreResult:
    score: float
    recommendation: str
    reasons: list[str]
    breakdown: list[tuple[str, float, str]] | None = None


@dataclass
class ModuleScore:
    score: float
    summary: str
    details: list[str]


@dataclass
class MarketPhase:
    phase: str
    summary: str
    probabilities: dict[str, int]


@dataclass
class RiskReward:
    risk_pct: float | None
    reward_pct: float | None
    ratio: float | None
    score: float
    summary: str


@dataclass
class AssetProfile:
    asset_type: str
    quote_type: str
    summary: str
    weights: dict[str, float]


@dataclass
class PortfolioResult:
    enabled: bool
    available: bool
    score: float | None
    summary: str
    details: list[str]
    asset_weight: float | None = None
    cash_weight: float | None = None
    position_value: float | None = None
    adjusted_score: float | None = None


@dataclass
class ResearchModule:
    name: str
    score: float | None
    summary: str
    details: list[str]
    beginner: str


@dataclass
class ResearchPack:
    data_quality: ResearchModule
    modules: list[ResearchModule]
    institutional_modules: list[ResearchModule]
    confidence: ResearchModule
    uncertainty_factors: list[str]
    scenarios: list[dict]
    buy_zones: list[dict]
    action: str
    decision: dict[str, object]
    conclusion: dict[str, str | list[str]]


@dataclass
class StockFundamentalSnapshot:
    revenue_growth: float | None
    earnings_growth: float | None
    profit_margin: float | None
    operating_margin: float | None
    gross_margin: float | None
    return_on_equity: float | None
    return_on_assets: float | None
    total_cash: float | None
    total_debt: float | None
    free_cashflow: float | None
    operating_cashflow: float | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_sales: float | None
    price_to_book: float | None
    enterprise_to_ebitda: float | None
    market_cap: float | None


@dataclass
class EtfFundamentalSnapshot:
    category: str | None
    fund_family: str | None
    annual_report_expense_ratio: float | None
    expense_ratio: float | None
    total_assets: float | None
    net_assets: float | None
    holdings_count: float | None
    fifty_two_week_change: float | None
    three_year_return: float | None
    five_year_return: float | None
    beta_3y: float | None
    ytd_return: float | None
