from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from long_term_analysis import (
    ENTRY_TIMING_SECTION,
    LONG_TERM_MODEL_TYPE,
    LONG_TERM_MODEL_VERSION,
    LongTermReadinessReport,
)


LONG_TERM_SCORING_MODEL_VERSION = "2026.08.02-score-v1"
LONG_TERM_MIN_HORIZON_YEARS = 3
LONG_TERM_MAX_HORIZON_YEARS = 7


@dataclass(frozen=True)
class LongTermFactorDefinition:
    label: str
    weight: float
    required_sections: tuple[str, ...]


LONG_TERM_FACTOR_DEFINITIONS: dict[str, LongTermFactorDefinition] = {
    "business_quality": LongTermFactorDefinition(
        "Geschäfts- und Umsatzmodell",
        0.15,
        ("business_model", "revenue_model"),
    ),
    "market_opportunity": LongTermFactorDefinition(
        "Marktpotenzial",
        0.15,
        ("market_opportunity",),
    ),
    "competitive_advantage": LongTermFactorDefinition(
        "Wettbewerbsposition und Skalierbarkeit",
        0.15,
        ("competitive_position",),
    ),
    "management_capital_allocation": LongTermFactorDefinition(
        "Management und Kapitalverwendung",
        0.10,
        ("management_capital_allocation",),
    ),
    "financial_quality": LongTermFactorDefinition(
        "Finanz- und Bilanzqualität",
        0.15,
        ("financial_quality",),
    ),
    "valuation": LongTermFactorDefinition(
        "Bewertung und eingepreiste Erwartungen",
        0.15,
        ("valuation",),
    ),
    "capital_preservation": LongTermFactorDefinition(
        "Schutz vor dauerhaftem Kapitalverlust",
        0.15,
        ("long_term_risks",),
    ),
}


@dataclass(frozen=True)
class LongTermFactorAssessment:
    factor: str
    score: float
    rationale: str
    evidence_sections: tuple[str, ...]


@dataclass(frozen=True)
class LongTermScenario:
    name: str
    probability_pct: float
    target_value: float
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class LongTermScenarioResult:
    name: str
    probability_pct: float
    target_value: float
    total_return_pct: float
    annualized_return_pct: float
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class LongTermScoringResult:
    model_type: str
    evidence_model_version: str
    scoring_model_version: str
    ready: bool
    status: str
    horizon_years: int
    weighted_score: float | None
    company_quality_score: float | None
    future_potential_score: float | None
    valuation_score: float | None
    capital_preservation_score: float | None
    expected_target_value: float | None
    expected_total_return_pct: float | None
    expected_annualized_return_pct: float | None
    factor_assessments: tuple[LongTermFactorAssessment, ...]
    scenarios: tuple[LongTermScenarioResult, ...]
    warnings: tuple[str, ...]


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _blocked_result(
    readiness: LongTermReadinessReport,
    horizon_years: int,
    warning: str,
) -> LongTermScoringResult:
    return LongTermScoringResult(
        model_type=LONG_TERM_MODEL_TYPE,
        evidence_model_version=LONG_TERM_MODEL_VERSION,
        scoring_model_version=LONG_TERM_SCORING_MODEL_VERSION,
        ready=False,
        status="Keine Long-Term-Bewertung: Die Quellenbasis ist nicht vollständig freigegeben.",
        horizon_years=horizon_years,
        weighted_score=None,
        company_quality_score=None,
        future_potential_score=None,
        valuation_score=None,
        capital_preservation_score=None,
        expected_target_value=None,
        expected_total_return_pct=None,
        expected_annualized_return_pct=None,
        factor_assessments=(),
        scenarios=(),
        warnings=tuple(dict.fromkeys((*readiness.warnings, warning))),
    )


def _validate_factors(
    factors: Iterable[LongTermFactorAssessment],
    readiness: LongTermReadinessReport,
) -> tuple[LongTermFactorAssessment, ...]:
    items = tuple(factors)
    keys = [str(item.factor or "").strip() for item in items]
    duplicates = sorted({key for key in keys if key and keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Long-Term-Faktoren sind doppelt vorhanden: {', '.join(duplicates)}.")

    expected = set(LONG_TERM_FACTOR_DEFINITIONS)
    received = set(keys)
    unknown = sorted(received - expected)
    missing = sorted(expected - received)
    if unknown:
        raise ValueError(f"Unbekannte Long-Term-Faktoren: {', '.join(unknown)}.")
    if missing:
        raise ValueError(f"Long-Term-Faktoren fehlen: {', '.join(missing)}.")

    covered_sections = set(readiness.covered_sections)
    validated: list[LongTermFactorAssessment] = []
    for item in items:
        definition = LONG_TERM_FACTOR_DEFINITIONS[item.factor]
        score = _finite_number(item.score)
        if score is None or not 0.0 <= score <= 10.0:
            raise ValueError(f"{definition.label}: Score muss endlich und zwischen 0 und 10 liegen.")
        rationale = str(item.rationale or "").strip()
        if not rationale:
            raise ValueError(f"{definition.label}: Begründung fehlt.")
        evidence_sections = tuple(
            dict.fromkeys(str(section or "").strip() for section in item.evidence_sections if str(section or "").strip())
        )
        if ENTRY_TIMING_SECTION in evidence_sections:
            raise ValueError("Technisches Einstiegstiming darf keinen Long-Term-Faktor beeinflussen.")
        required_sections = set(definition.required_sections)
        if not required_sections.issubset(evidence_sections):
            missing_sections = sorted(required_sections - set(evidence_sections))
            raise ValueError(
                f"{definition.label}: erforderliche Evidenzbereiche fehlen: {', '.join(missing_sections)}."
            )
        if not set(evidence_sections).issubset(covered_sections):
            raise ValueError(f"{definition.label}: nicht freigegebener Evidenzbereich verwendet.")
        validated.append(
            LongTermFactorAssessment(
                factor=item.factor,
                score=score,
                rationale=rationale,
                evidence_sections=evidence_sections,
            )
        )
    return tuple(validated)


def _validate_scenarios(
    scenarios: Iterable[LongTermScenario],
    current_value: float,
    horizon_years: int,
) -> tuple[LongTermScenarioResult, ...]:
    items = tuple(scenarios)
    expected_names = ("Bear", "Basis", "Bull")
    by_name: dict[str, LongTermScenario] = {}
    for item in items:
        name = str(item.name or "").strip()
        if name not in expected_names:
            raise ValueError("Long-Term-Szenarien müssen Bear, Basis und Bull heißen.")
        if name in by_name:
            raise ValueError(f"Long-Term-Szenario {name} ist doppelt vorhanden.")
        by_name[name] = item
    if set(by_name) != set(expected_names):
        raise ValueError("Long-Term-Szenarien müssen Bear, Basis und Bull vollständig enthalten.")

    probabilities: list[float] = []
    targets: list[float] = []
    results: list[LongTermScenarioResult] = []
    for name in expected_names:
        item = by_name[name]
        probability = _finite_number(item.probability_pct)
        target = _finite_number(item.target_value)
        if probability is None or probability < 0.0 or probability > 100.0:
            raise ValueError(f"{name}: Wahrscheinlichkeit muss endlich und zwischen 0 und 100 liegen.")
        if target is None or target <= 0.0:
            raise ValueError(f"{name}: Zielwert muss endlich und größer als 0 sein.")
        conditions = tuple(
            condition
            for condition in (str(value or "").strip() for value in item.conditions)
            if condition
        )
        if not conditions:
            raise ValueError(f"{name}: nachvollziehbare Bedingungen fehlen.")
        total_return = (target / current_value - 1.0) * 100.0
        annualized_return = ((target / current_value) ** (1.0 / horizon_years) - 1.0) * 100.0
        probabilities.append(probability)
        targets.append(target)
        results.append(
            LongTermScenarioResult(
                name=name,
                probability_pct=probability,
                target_value=target,
                total_return_pct=total_return,
                annualized_return_pct=annualized_return,
                conditions=conditions,
            )
        )

    if not math.isclose(sum(probabilities), 100.0, abs_tol=1e-6):
        raise ValueError("Die Wahrscheinlichkeiten der Long-Term-Szenarien müssen zusammen 100 ergeben.")
    if not targets[0] < targets[1] < targets[2]:
        raise ValueError("Zielwerte müssen in der Reihenfolge Bear < Basis < Bull liegen.")
    return tuple(results)


def score_long_term_assessment(
    readiness: LongTermReadinessReport,
    factors: Iterable[LongTermFactorAssessment],
    scenarios: Iterable[LongTermScenario],
    *,
    current_value: float,
    horizon_years: int,
) -> LongTermScoringResult:
    """Calculate a transparent long-term score only after the evidence gate passed.

    Inputs are deliberately explicit and source-section bound. The function does
    not infer missing values and does not turn technical entry timing into
    company quality, future potential, valuation, or capital preservation.
    """

    if (
        readiness.model_type != LONG_TERM_MODEL_TYPE
        or readiness.model_version != LONG_TERM_MODEL_VERSION
    ):
        return _blocked_result(readiness, horizon_years, "Quellen- und Bewertungsmodell sind nicht kompatibel.")
    if not readiness.ready:
        return _blocked_result(readiness, horizon_years, readiness.status)
    if isinstance(horizon_years, bool) or not isinstance(horizon_years, int):
        raise ValueError("Long-Term-Horizont muss eine ganze Jahreszahl sein.")
    if not LONG_TERM_MIN_HORIZON_YEARS <= horizon_years <= LONG_TERM_MAX_HORIZON_YEARS:
        raise ValueError("Long-Term-Horizont muss zwischen 3 und 7 Jahren liegen.")
    clean_current_value = _finite_number(current_value)
    if clean_current_value is None or clean_current_value <= 0.0:
        raise ValueError("Aktueller Wert muss endlich und größer als 0 sein.")

    factor_items = _validate_factors(factors, readiness)
    scenario_items = _validate_scenarios(scenarios, clean_current_value, horizon_years)
    factor_by_key = {item.factor: item for item in factor_items}
    weighted_score = sum(
        factor_by_key[key].score * definition.weight
        for key, definition in LONG_TERM_FACTOR_DEFINITIONS.items()
    )
    company_quality = sum(
        factor_by_key[key].score * weight
        for key, weight in (
            ("business_quality", 0.25),
            ("competitive_advantage", 0.25),
            ("management_capital_allocation", 0.20),
            ("financial_quality", 0.30),
        )
    )
    future_potential = sum(
        factor_by_key[key].score * weight
        for key, weight in (
            ("business_quality", 0.20),
            ("market_opportunity", 0.35),
            ("competitive_advantage", 0.30),
            ("financial_quality", 0.15),
        )
    )
    expected_target = sum(
        item.target_value * item.probability_pct / 100.0 for item in scenario_items
    )
    expected_total_return = (expected_target / clean_current_value - 1.0) * 100.0
    expected_annualized_return = (
        (expected_target / clean_current_value) ** (1.0 / horizon_years) - 1.0
    ) * 100.0

    return LongTermScoringResult(
        model_type=LONG_TERM_MODEL_TYPE,
        evidence_model_version=LONG_TERM_MODEL_VERSION,
        scoring_model_version=LONG_TERM_SCORING_MODEL_VERSION,
        ready=True,
        status="Quellengebundene Long-Term-Bewertung berechnet; technischer Einstieg bleibt separat.",
        horizon_years=horizon_years,
        weighted_score=weighted_score,
        company_quality_score=company_quality,
        future_potential_score=future_potential,
        valuation_score=factor_by_key["valuation"].score,
        capital_preservation_score=factor_by_key["capital_preservation"].score,
        expected_target_value=expected_target,
        expected_total_return_pct=expected_total_return,
        expected_annualized_return_pct=expected_annualized_return,
        factor_assessments=factor_items,
        scenarios=scenario_items,
        warnings=readiness.warnings,
    )
