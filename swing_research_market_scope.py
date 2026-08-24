from __future__ import annotations

"""Fail-closed market-scope contracts for future Swing research.

The module only prepares and validates research metadata.  It cannot change a
strategy, open unseen evidence, write a research store, or activate trading.
"""

import hashlib
import json
from typing import Mapping, Sequence


MARKET_SCOPE_CONTRACT_VERSION = "swing-research-market-scope-2026.08.23-v1"
MARKET_SCOPES = (
    "EQUITIES",
    "ETF",
    "FX",
    "FUTURES",
    "COMMODITIES",
    "CRYPTO",
    "CROSS_ASSET",
    "GENERAL_METHOD",
)
DIRECT_ASSET_SCOPES = frozenset(
    {"EQUITIES", "ETF", "FX", "FUTURES", "COMMODITIES", "CRYPTO"}
)
NON_ACTIVATING_SCOPES = frozenset({"CROSS_ASSET", "GENERAL_METHOD"})
RESULT_STATUSES = frozenset({"VALIDATED", "REJECTED", "INCONCLUSIVE", "NOT_TESTED"})
EVIDENCE_STATUSES = frozenset({"NOT_RUN", "PASSED", "FAILED", "UNDERPOWERED", "INVALID"})


class MarketScopeError(ValueError):
    """Raised when research scope would be missing, ambiguous, or transferred."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _verify_record_fingerprint(
    record: Mapping[str, object],
    *,
    fingerprint_field: str,
    label: str,
) -> None:
    payload = dict(record)
    expected = str(payload.pop(fingerprint_field, ""))
    if not expected or _fingerprint(payload) != expected:
        raise MarketScopeError(f"{label}-Fingerabdruck fehlt oder wurde verändert.")


def _required_text(value: object, field: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise MarketScopeError(f"{field} darf nicht leer sein.")
    return clean


def normalize_market_scopes(
    scopes: Sequence[str],
    *,
    field: str = "market_scope",
) -> tuple[str, ...]:
    if isinstance(scopes, (str, bytes)):
        raise MarketScopeError(f"{field} muss eine Liste von Market Scopes sein.")
    normalized = {str(scope or "").strip().upper() for scope in scopes}
    if "" in normalized:
        raise MarketScopeError(f"{field} enthält einen leeren Market Scope.")
    unknown = sorted(normalized - set(MARKET_SCOPES))
    if unknown:
        raise MarketScopeError(
            f"{field} enthält unbekannte Market Scopes: {', '.join(unknown)}"
        )
    if not normalized:
        raise MarketScopeError(f"{field} benötigt mindestens einen Market Scope.")
    return tuple(scope for scope in MARKET_SCOPES if scope in normalized)


def market_scope_contract(
    *,
    source_scopes: Sequence[str],
    test_scopes: Sequence[str],
) -> dict[str, object]:
    source = normalize_market_scopes(source_scopes, field="source_scope")
    tested = normalize_market_scopes(test_scopes, field="test_scope")
    cross_market = bool(set(source) != set(tested))
    contract: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "market_scope": list(dict.fromkeys((*source, *tested))),
        "source_scope": list(source),
        "test_scope": list(tested),
        "cross_market_transfer": cross_market,
        "cross_market_transfer_requires_new_experiment": cross_market,
        "validated_scopes": [],
        "rejected_scopes": [],
        "validation_is_never_inherited_across_scopes": True,
        "validated_without_matching_scope_can_activate": False,
        "automatic_activation": False,
    }
    contract["scope_fingerprint"] = _fingerprint(contract)
    return contract


def build_scoped_research_hypothesis(
    *,
    hypothesis_id: str,
    name: str,
    origin: str,
    source_scopes: Sequence[str],
    test_scopes: Sequence[str],
) -> dict[str, object]:
    scope = market_scope_contract(source_scopes=source_scopes, test_scopes=test_scopes)
    hypothesis: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "record_type": "research_hypothesis_scope",
        "hypothesis_id": _required_text(hypothesis_id, "hypothesis_id"),
        "name": _required_text(name, "name"),
        "origin": _required_text(origin, "origin"),
        "scope": scope,
        "status": "REGISTERED_NOT_TESTED",
        "outcomes_seen": False,
        "existing_research_removed": False,
        "automatic_strategy_change": False,
        "automatic_activation": False,
    }
    hypothesis["hypothesis_scope_fingerprint"] = _fingerprint(hypothesis)
    return hypothesis


def build_scoped_research_feature(
    *,
    feature_id: str,
    name: str,
    definition: str,
    causal_cutoff: str,
    source_scopes: Sequence[str],
    test_scopes: Sequence[str],
) -> dict[str, object]:
    scope = market_scope_contract(source_scopes=source_scopes, test_scopes=test_scopes)
    feature: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "record_type": "research_feature_scope",
        "feature_id": _required_text(feature_id, "feature_id"),
        "name": _required_text(name, "name"),
        "definition": _required_text(definition, "definition"),
        "causal_cutoff": _required_text(causal_cutoff, "causal_cutoff"),
        "scope": scope,
        "status": "REGISTERED_RESEARCH_ONLY",
        "cross_market_validation_inherited": False,
        "live_signal_influence": False,
        "automatic_strategy_change": False,
        "automatic_activation": False,
    }
    feature["feature_scope_fingerprint"] = _fingerprint(feature)
    return feature


def build_scoped_research_experiment(
    *,
    experiment_id: str,
    hypothesis: Mapping[str, object],
    test_scopes: Sequence[str],
    asset_universe: str,
    period_start: str,
    period_end: str,
    timeframe: str,
    baseline: str,
    split_design: str,
) -> dict[str, object]:
    _verify_record_fingerprint(
        hypothesis,
        fingerprint_field="hypothesis_scope_fingerprint",
        label="Hypothesen-Scope",
    )
    hypothesis_scope = dict(dict(hypothesis.get("scope") or {}))
    source_scopes = normalize_market_scopes(
        hypothesis_scope.get("source_scope") or (), field="hypothesis.source_scope"
    )
    intended_scopes = normalize_market_scopes(
        hypothesis_scope.get("test_scope") or (), field="hypothesis.test_scope"
    )
    tested = normalize_market_scopes(test_scopes, field="experiment.test_scope")
    if not set(tested) <= set(intended_scopes):
        raise MarketScopeError(
            "Ein zusätzlicher Testmarkt benötigt zuerst eine neue unabhängige "
            "Cross-Market-Hypothese."
        )
    start = _required_text(period_start, "period_start")
    end = _required_text(period_end, "period_end")
    if end < start:
        raise MarketScopeError("period_end darf nicht vor period_start liegen.")
    experiment: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "record_type": "research_experiment_scope",
        "experiment_id": _required_text(experiment_id, "experiment_id"),
        "hypothesis_id": _required_text(hypothesis.get("hypothesis_id"), "hypothesis_id"),
        "hypothesis_scope_fingerprint": _required_text(
            hypothesis.get("hypothesis_scope_fingerprint"),
            "hypothesis_scope_fingerprint",
        ),
        "source_scope": list(source_scopes),
        "hypothesis_test_scope": list(intended_scopes),
        "test_scope": list(tested),
        "asset_universe": _required_text(asset_universe, "asset_universe"),
        "period": {"start": start, "end": end},
        "timeframe": _required_text(timeframe, "timeframe"),
        "baseline": _required_text(baseline, "baseline"),
        "split_design": _required_text(split_design, "split_design"),
        "sample_size": None,
        "is_status": "NOT_RUN",
        "oos_status": "NOT_RUN",
        "walk_forward_status": "NOT_RUN",
        "status": "PREPARED_NOT_STARTED",
        "outcomes_seen": False,
        "scope_validation_inherited": False,
        "automatic_strategy_change": False,
        "automatic_activation": False,
    }
    experiment["experiment_scope_fingerprint"] = _fingerprint(experiment)
    return experiment


def build_scoped_research_result(
    *,
    experiment: Mapping[str, object],
    sample_size: int,
    is_status: str,
    oos_status: str,
    walk_forward_status: str,
    result_status: str,
    validated_scopes: Sequence[str] = (),
    rejected_scopes: Sequence[str] = (),
) -> dict[str, object]:
    _verify_record_fingerprint(
        experiment,
        fingerprint_field="experiment_scope_fingerprint",
        label="Experiment-Scope",
    )
    tested = normalize_market_scopes(
        experiment.get("test_scope") or (), field="experiment.test_scope"
    )
    validated = (
        normalize_market_scopes(validated_scopes, field="validated_scopes")
        if validated_scopes
        else ()
    )
    rejected = (
        normalize_market_scopes(rejected_scopes, field="rejected_scopes")
        if rejected_scopes
        else ()
    )
    if set(validated) & set(rejected):
        raise MarketScopeError("Ein Scope kann nicht zugleich validiert und verworfen sein.")
    if not set(validated) | set(rejected) <= set(tested):
        raise MarketScopeError("Result-Scope muss Teil des tatsächlich getesteten Scopes sein.")
    evidence = {
        "is_status": str(is_status).strip().upper(),
        "oos_status": str(oos_status).strip().upper(),
        "walk_forward_status": str(walk_forward_status).strip().upper(),
    }
    unknown_evidence = sorted(set(evidence.values()) - EVIDENCE_STATUSES)
    if unknown_evidence:
        raise MarketScopeError(
            "Unbekannter IS/OOS/Walk-Forward-Status: " + ", ".join(unknown_evidence)
        )
    result_state = str(result_status).strip().upper()
    if result_state not in RESULT_STATUSES:
        raise MarketScopeError(f"Unbekannter Research-Ergebnisstatus: {result_state}")
    if int(sample_size) < 0:
        raise MarketScopeError("sample_size darf nicht negativ sein.")
    if result_state == "VALIDATED":
        if not validated:
            raise MarketScopeError("VALIDATED benötigt mindestens einen validierten Market Scope.")
        if evidence["oos_status"] != "PASSED" or evidence["walk_forward_status"] != "PASSED":
            raise MarketScopeError("VALIDATED benötigt bestandene OOS- und Walk-Forward-Evidenz.")
    if result_state == "REJECTED" and not rejected:
        raise MarketScopeError("REJECTED benötigt mindestens einen verworfenen Market Scope.")
    result: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "record_type": "research_result_scope",
        "experiment_id": _required_text(experiment.get("experiment_id"), "experiment_id"),
        "experiment_scope_fingerprint": _required_text(
            experiment.get("experiment_scope_fingerprint"),
            "experiment_scope_fingerprint",
        ),
        "source_scope": list(
            normalize_market_scopes(
                experiment.get("source_scope") or (), field="experiment.source_scope"
            )
        ),
        "test_scope": list(tested),
        "asset_universe": _required_text(experiment.get("asset_universe"), "asset_universe"),
        "period": dict(experiment.get("period") or {}),
        "timeframe": _required_text(experiment.get("timeframe"), "timeframe"),
        "baseline": _required_text(experiment.get("baseline"), "baseline"),
        "sample_size": int(sample_size),
        **evidence,
        "result_status": result_state,
        "validated_scopes": list(validated),
        "rejected_scopes": list(rejected),
        "negative_results_are_retained": True,
        "scope_validation_inherited": False,
        "automatic_strategy_change": False,
        "automatic_activation": False,
    }
    result["result_scope_fingerprint"] = _fingerprint(result)
    return result


def assert_market_scope_activation_allowed(
    result: Mapping[str, object],
    *,
    target_scope: str,
) -> dict[str, object]:
    _verify_record_fingerprint(
        result,
        fingerprint_field="result_scope_fingerprint",
        label="Result-Scope",
    )
    target = normalize_market_scopes([target_scope], field="target_scope")[0]
    if target not in DIRECT_ASSET_SCOPES:
        raise MarketScopeError(
            "GENERAL_METHOD und CROSS_ASSET können keine Assetklasse direkt aktivieren."
        )
    if str(result.get("result_status") or "").upper() != "VALIDATED":
        raise MarketScopeError("VALIDATED allein fehlt oder das Ergebnis ist nicht validiert.")
    validated = set(result.get("validated_scopes") or ())
    tested = set(result.get("test_scope") or ())
    if target not in validated or target not in tested:
        raise MarketScopeError(
            "VALIDATED reicht ohne passend validierten Market Scope nicht zur Aktivierung."
        )
    return {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "target_scope": target,
        "matching_validated_scope": True,
        "scope_gate_passed": True,
        "scope_gate_is_not_strategy_release": True,
        "remaining_freeze_oos_forward_and_manual_gates_required": True,
        "automatic_activation": False,
    }


def prepare_cross_market_transfer(
    *,
    source_result: Mapping[str, object],
    transfer_experiment_id: str,
    target_scopes: Sequence[str],
) -> dict[str, object]:
    _verify_record_fingerprint(
        source_result,
        fingerprint_field="result_scope_fingerprint",
        label="Source-Result-Scope",
    )
    source_tested = normalize_market_scopes(
        source_result.get("test_scope") or (), field="source_result.test_scope"
    )
    targets = normalize_market_scopes(target_scopes, field="target_scope")
    if set(targets) <= set(source_tested):
        raise MarketScopeError("Kein Cross-Market-Transfer: Ziel wurde bereits separat getestet.")
    transfer: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "record_type": "cross_market_transfer",
        "transfer_experiment_id": _required_text(
            transfer_experiment_id, "transfer_experiment_id"
        ),
        "source_result_scope_fingerprint": _required_text(
            source_result.get("result_scope_fingerprint"),
            "source_result_scope_fingerprint",
        ),
        "source_scope": list(source_tested),
        "test_scope": list(targets),
        "status": "INDEPENDENT_EXPERIMENT_REQUIRED",
        "inherited_validated_scopes": [],
        "inherited_performance_evidence": False,
        "new_oos_and_walk_forward_required": True,
        "automatic_activation": False,
    }
    transfer["transfer_fingerprint"] = _fingerprint(transfer)
    return transfer


def build_research_knowledge_entry(
    *,
    knowledge_id: str,
    origin: str,
    source_scopes: Sequence[str],
    test_scopes: Sequence[str],
    result_scope_fingerprint: str,
    outcome: str,
    validated_scopes: Sequence[str] = (),
    rejected_scopes: Sequence[str] = (),
) -> dict[str, object]:
    source = normalize_market_scopes(source_scopes, field="source_scope")
    tested = normalize_market_scopes(test_scopes, field="test_scope")
    validated = (
        normalize_market_scopes(validated_scopes, field="validated_scopes")
        if validated_scopes
        else ()
    )
    rejected = (
        normalize_market_scopes(rejected_scopes, field="rejected_scopes")
        if rejected_scopes
        else ()
    )
    if not set(validated) | set(rejected) <= set(tested):
        raise MarketScopeError("Knowledge-Base-Scopes müssen tatsächlich getestet worden sein.")
    if set(validated) & set(rejected):
        raise MarketScopeError("Knowledge-Base-Scope ist widersprüchlich.")
    clean_outcome = str(outcome or "").strip().upper()
    if clean_outcome not in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}:
        raise MarketScopeError("Knowledge-Base-outcome ist ungültig.")
    if clean_outcome == "NEGATIVE" and not rejected:
        raise MarketScopeError("Negative Evidenz benötigt den verworfenen Test-Scope.")
    entry: dict[str, object] = {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "record_type": "research_knowledge_scope",
        "knowledge_id": _required_text(knowledge_id, "knowledge_id"),
        "origin": _required_text(origin, "origin"),
        "source_scope": list(source),
        "test_scope": list(tested),
        "validated_scopes": list(validated),
        "rejected_scopes": list(rejected),
        "result_scope_fingerprint": _required_text(
            result_scope_fingerprint, "result_scope_fingerprint"
        ),
        "outcome": clean_outcome,
        "negative_results_are_first_class_knowledge": True,
        "cross_market_transfer_is_evidence": False,
        "automatic_activation": False,
    }
    entry["knowledge_scope_fingerprint"] = _fingerprint(entry)
    return entry


def legacy_unscoped_research_contract() -> dict[str, object]:
    return {
        "version": MARKET_SCOPE_CONTRACT_VERSION,
        "status": "LEGACY_SCOPE_NOT_RECORDED",
        "scope_may_be_inferred_from_positive_result": False,
        "activation_allowed": False,
        "migration_may_rewrite_old_evidence": False,
        "new_scoped_validation_required_before_activation": True,
    }
