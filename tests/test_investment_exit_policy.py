from __future__ import annotations

import pytest

from investment_exit_policy import (
    InvestmentExitPolicyError,
    assess_investment_sale,
    swing_exit_separation_contract,
)


def test_short_term_fear_and_loss_never_create_an_investment_sell_trigger() -> None:
    result = assess_investment_sale(
        thesis="INTACT",
        fundamentals="STABLE",
        valuation="FAIR_OR_MIXED",
        balance_risk="STABLE",
        concentration="ACCEPTABLE",
        capital_allocation="CURRENT_HOLDING_PREFERRED",
        short_term_market_fear=True,
        short_term_price_loss=True,
    )

    assert result["decision"] == "NO_DOCUMENTED_LONG_TERM_SELL_TRIGGER"
    assert result["structural_triggers"] == []
    assert result["allocation_triggers"] == []
    assert result["short_term_fear_is_sell_trigger"] is False
    assert result["price_loss_is_sell_trigger"] is False
    assert result["hold_means_never_sell"] is False
    assert result["automatic_sell_order"] is False


@pytest.mark.parametrize(
    ("field", "value", "expected_trigger"),
    [
        ("thesis", "INVALIDATED", "investment_thesis_changed_or_invalidated"),
        ("fundamentals", "DETERIORATED", "fundamentals_deteriorated"),
        ("balance_risk", "DETERIORATED", "balance_or_risk_profile_deteriorated"),
    ],
)
def test_structural_changes_create_a_review_not_an_automatic_order(
    field: str,
    value: str,
    expected_trigger: str,
) -> None:
    kwargs = {field: value}
    result = assess_investment_sale(**kwargs)

    assert result["decision"] == "REVIEW_PARTIAL_OR_FULL_EXIT"
    assert expected_trigger in result["structural_triggers"]
    assert result["automatic_sell_order"] is False


@pytest.mark.parametrize(
    ("field", "value", "expected_trigger"),
    [
        ("valuation", "NO_LONGER_ATTRACTIVE", "valuation_no_longer_attractive"),
        (
            "concentration",
            "PROBLEMATIC",
            "position_size_or_concentration_problematic",
        ),
        (
            "capital_allocation",
            "BETTER_ALTERNATIVE",
            "better_capital_allocation_available",
        ),
    ],
)
def test_allocation_reasons_create_a_reduction_review(
    field: str,
    value: str,
    expected_trigger: str,
) -> None:
    result = assess_investment_sale(**{field: value})

    assert result["decision"] == "REVIEW_REDUCTION_OR_REALLOCATION"
    assert expected_trigger in result["allocation_triggers"]


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(InvestmentExitPolicyError):
        assess_investment_sale(thesis="probably fine")


def test_swing_exit_contract_stays_strictly_separate() -> None:
    contract = swing_exit_separation_contract()

    assert contract["decision_domain"] == "SWING_TRADING"
    assert contract["investment_sale_policy_applies"] is False
    assert contract["swing_rules_changed"] is False
    assert contract["automatic_cross_domain_signal_transfer"] is False
