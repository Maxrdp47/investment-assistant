from __future__ import annotations

"""Strictly separate long-term investment sale review from Swing exits."""

from collections.abc import Mapping


INVESTMENT_EXIT_POLICY_VERSION = "investment-exit-policy-2026.08.23-v1"

THESIS_STATUSES = frozenset({"NOT_ASSESSED", "INTACT", "CHANGED", "INVALIDATED"})
FUNDAMENTAL_STATUSES = frozenset({"NOT_ASSESSED", "STABLE", "DETERIORATED"})
VALUATION_STATUSES = frozenset(
    {"NOT_ASSESSED", "ATTRACTIVE", "FAIR_OR_MIXED", "NO_LONGER_ATTRACTIVE"}
)
BALANCE_RISK_STATUSES = frozenset({"NOT_ASSESSED", "STABLE", "DETERIORATED"})
CONCENTRATION_STATUSES = frozenset({"NOT_ASSESSED", "ACCEPTABLE", "PROBLEMATIC"})
CAPITAL_ALLOCATION_STATUSES = frozenset(
    {"NOT_ASSESSED", "CURRENT_HOLDING_PREFERRED", "BETTER_ALTERNATIVE"}
)


class InvestmentExitPolicyError(ValueError):
    """Raised for ambiguous or unknown long-term sale evidence."""


def _status(value: object, allowed: frozenset[str], field: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise InvestmentExitPolicyError(
            f"Unbekannter Status für {field}: {normalized or '<leer>'}."
        )
    return normalized


def assess_investment_sale(
    *,
    thesis: str = "NOT_ASSESSED",
    fundamentals: str = "NOT_ASSESSED",
    valuation: str = "NOT_ASSESSED",
    balance_risk: str = "NOT_ASSESSED",
    concentration: str = "NOT_ASSESSED",
    capital_allocation: str = "NOT_ASSESSED",
    short_term_market_fear: bool = False,
    short_term_price_loss: bool = False,
) -> dict[str, object]:
    """Assess whether a long-term holding warrants a documented sale review.

    The result never sends an order.  Short-term fear and price losses are
    reported as context and cannot enter the trigger list.
    """

    statuses = {
        "thesis": _status(thesis, THESIS_STATUSES, "thesis"),
        "fundamentals": _status(
            fundamentals, FUNDAMENTAL_STATUSES, "fundamentals"
        ),
        "valuation": _status(valuation, VALUATION_STATUSES, "valuation"),
        "balance_risk": _status(
            balance_risk, BALANCE_RISK_STATUSES, "balance_risk"
        ),
        "concentration": _status(
            concentration, CONCENTRATION_STATUSES, "concentration"
        ),
        "capital_allocation": _status(
            capital_allocation,
            CAPITAL_ALLOCATION_STATUSES,
            "capital_allocation",
        ),
    }

    structural_triggers: list[str] = []
    if statuses["thesis"] in {"CHANGED", "INVALIDATED"}:
        structural_triggers.append("investment_thesis_changed_or_invalidated")
    if statuses["fundamentals"] == "DETERIORATED":
        structural_triggers.append("fundamentals_deteriorated")
    if statuses["balance_risk"] == "DETERIORATED":
        structural_triggers.append("balance_or_risk_profile_deteriorated")

    allocation_triggers: list[str] = []
    if statuses["valuation"] == "NO_LONGER_ATTRACTIVE":
        allocation_triggers.append("valuation_no_longer_attractive")
    if statuses["concentration"] == "PROBLEMATIC":
        allocation_triggers.append("position_size_or_concentration_problematic")
    if statuses["capital_allocation"] == "BETTER_ALTERNATIVE":
        allocation_triggers.append("better_capital_allocation_available")

    if structural_triggers:
        decision = "REVIEW_PARTIAL_OR_FULL_EXIT"
        explanation = (
            "Mindestens ein langfristiger Strukturgrund ist dokumentiert; Teil- oder "
            "Vollausstieg sachlich prüfen, aber nicht automatisch ausführen."
        )
    elif allocation_triggers:
        decision = "REVIEW_REDUCTION_OR_REALLOCATION"
        explanation = (
            "Bewertung, Konzentration oder bessere Kapitalallokation rechtfertigt "
            "eine Reduktionsprüfung; kurzfristige Kursbewegung ist nicht der Auslöser."
        )
    else:
        decision = "NO_DOCUMENTED_LONG_TERM_SELL_TRIGGER"
        explanation = (
            "Kein dokumentierter langfristiger Verkaufsgrund. Das bedeutet Halten "
            "unter Beobachtung, nicht eine Regel, niemals zu verkaufen."
        )

    return {
        "version": INVESTMENT_EXIT_POLICY_VERSION,
        "decision_domain": "LONG_TERM_INVESTMENT",
        "decision": decision,
        "statuses": statuses,
        "structural_triggers": structural_triggers,
        "allocation_triggers": allocation_triggers,
        "short_term_context": {
            "market_fear": bool(short_term_market_fear),
            "price_loss": bool(short_term_price_loss),
        },
        "short_term_fear_is_sell_trigger": False,
        "price_loss_is_sell_trigger": False,
        "hold_means_never_sell": False,
        "automatic_sell_order": False,
        "explanation": explanation,
    }


def swing_exit_separation_contract() -> Mapping[str, object]:
    """Document the boundary; it does not reimplement or alter Swing rules."""

    return {
        "version": INVESTMENT_EXIT_POLICY_VERSION,
        "decision_domain": "SWING_TRADING",
        "governed_by": "existing_entry_stop_target_and_exit_rules",
        "investment_sale_policy_applies": False,
        "swing_rules_changed": False,
        "automatic_cross_domain_signal_transfer": False,
    }
