from __future__ import annotations

"""Robustness-first, production-neutral Swing research quality contracts."""

import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


RESEARCH_QUALITY_SCHEMA_VERSION = 1
RESEARCH_QUALITY_VERSION = "swing-research-quality-2026.08.23-v1"
PLACEBO_VERSION = "regime-matched-hash-placebo-2026.08.23-v1"
PLATEAU_VERSION = "predeclared-neighborhood-plateau-2026.08.23-v1"
ENTRY_EFFICIENCY_VERSION = "swing-entry-efficiency-daily-2026.08.23-v1"
EXECUTION_STRESS_VERSION = "swing-execution-stress-2026.08.23-v1"
DEFAULT_RESEARCH_QUALITY_DB_PATH = (
    Path(__file__).resolve().parent / "runtime" / "swing_research_quality.sqlite3"
)

RESEARCH_OBJECTIVE = (
    "Die einfachste Strategie mit robust positivem Edge nach Kosten, die über unterschiedliche "
    "Zeiträume, Assets und Marktregime stabil bleibt, ausreichende unabhängige Evidenz besitzt "
    "und bei leicht schlechteren Parametern und Ausführungsannahmen nicht zusammenbricht."
)
FORBIDDEN_OBJECTIVE = "Strategie mit maximalem historischen Gewinn"
STAGE_ORDER = ("development", "manual_selection", "freeze", "validation", "holdout", "external", "true_forward")
STRESS_SCENARIOS = {
    "base": 0.0,
    "elevated_slippage": 0.05,
    "adverse_entry": 0.10,
    "higher_total_cost": 0.15,
    "conservative_gap_stop": 0.25,
}


class ResearchQualityError(ValueError):
    pass


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _json(value: object) -> str:
    return json.dumps(_clean(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _aware(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchQualityError("Zeitpunkt ist ungültig.") from exc
    if parsed.tzinfo is None:
        raise ResearchQualityError("Zeitpunkt benötigt eine Zeitzone.")
    return parsed.isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def initialize_research_quality_store(path: Path = DEFAULT_RESEARCH_QUALITY_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS research_quality_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_hypothesis_attempts(
                attempt_id TEXT PRIMARY KEY,
                hypothesis_id TEXT NOT NULL,
                family_id TEXT NOT NULL,
                hypothesis_signature TEXT NOT NULL UNIQUE,
                family_attempt_number INTEGER NOT NULL,
                defined_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                UNIQUE(family_id, family_attempt_number)
            );
            CREATE TABLE IF NOT EXISTS research_hypothesis_events(
                event_id TEXT PRIMARY KEY,
                attempt_id TEXT NOT NULL REFERENCES research_hypothesis_attempts(attempt_id),
                recorded_at TEXT NOT NULL,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                UNIQUE(attempt_id, action, payload_fingerprint)
            );
            CREATE TRIGGER IF NOT EXISTS research_attempts_no_update BEFORE UPDATE ON research_hypothesis_attempts BEGIN
                SELECT RAISE(ABORT, 'research_hypothesis_attempts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS research_attempts_no_delete BEFORE DELETE ON research_hypothesis_attempts BEGIN
                SELECT RAISE(ABORT, 'research_hypothesis_attempts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS research_events_no_update BEFORE UPDATE ON research_hypothesis_events BEGIN
                SELECT RAISE(ABORT, 'research_hypothesis_events is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS research_events_no_delete BEFORE DELETE ON research_hypothesis_events BEGIN
                SELECT RAISE(ABORT, 'research_hypothesis_events is append-only');
            END;
            """
        )
        row = connection.execute("SELECT value FROM research_quality_meta WHERE key='schema_version'").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO research_quality_meta VALUES('schema_version', ?)",
                (str(RESEARCH_QUALITY_SCHEMA_VERSION),),
            )
        elif int(row["value"]) != RESEARCH_QUALITY_SCHEMA_VERSION:
            raise ResearchQualityError("Nicht unterstützte Research-Quality-Datenbankversion.")


def _family(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    if not clean:
        raise ResearchQualityError("Hypothesenfamilie fehlt.")
    return clean


def register_research_hypothesis(
    *,
    hypothesis_id: str,
    name: str,
    description: str,
    defined_at: str,
    research_origin: str,
    family_id: str,
    features: Sequence[str],
    parameters: Mapping[str, object],
    dataset_fingerprint: str,
    feature_fingerprint: str,
    code_fingerprint: str,
    related_hypotheses: Sequence[str] = (),
    path: Path = DEFAULT_RESEARCH_QUALITY_DB_PATH,
) -> dict[str, object]:
    """Register one semantic attempt; renamed duplicates keep the same attempt."""
    initialize_research_quality_store(path)
    family = _family(family_id)
    signature_payload = {
        "family_id": family,
        "features": sorted({str(value).strip().casefold() for value in features if str(value).strip()}),
        "parameters": dict(parameters),
        "dataset_fingerprint": str(dataset_fingerprint),
        "feature_fingerprint": str(feature_fingerprint),
        "code_fingerprint": str(code_fingerprint),
    }
    signature = _fingerprint(signature_payload)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT payload_json FROM research_hypothesis_attempts WHERE hypothesis_signature=?",
            (signature,),
        ).fetchone()
        if existing is not None:
            return {"inserted": False, "attempt": json.loads(existing["payload_json"])}
        attempt_number = int(
            connection.execute(
                "SELECT COUNT(*) FROM research_hypothesis_attempts WHERE family_id=?", (family,)
            ).fetchone()[0]
        ) + 1
        payload = {
            "quality_version": RESEARCH_QUALITY_VERSION,
            "hypothesis_id": str(hypothesis_id).strip(),
            "name": str(name).strip(),
            "description": str(description).strip(),
            "defined_at": _aware(defined_at),
            "research_origin": str(research_origin).strip(),
            "family_id": family,
            "family_attempt_number": attempt_number,
            "features": signature_payload["features"],
            "parameters": dict(parameters),
            "dataset_fingerprint": str(dataset_fingerprint),
            "feature_fingerprint": str(feature_fingerprint),
            "code_fingerprint": str(code_fingerprint),
            "related_hypotheses": sorted({str(value) for value in related_hypotheses}),
            "development_accessed": False,
            "validation_accessed": False,
            "holdout_accessed": False,
            "result": None,
            "decision": "defined",
            "automatic_strategy_selection": False,
            "research_objective": RESEARCH_OBJECTIVE,
        }
        attempt_id = f"attempt-{signature[:32]}"
        payload["attempt_id"] = attempt_id
        fingerprint = _fingerprint(payload)
        connection.execute(
            "INSERT INTO research_hypothesis_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                attempt_id,
                str(hypothesis_id).strip(),
                family,
                signature,
                attempt_number,
                payload["defined_at"],
                _json(payload),
                fingerprint,
            ),
        )
    return {"inserted": True, "attempt": payload}


def append_research_hypothesis_event(
    attempt_id: str,
    *,
    recorded_at: str,
    action: str,
    result: Mapping[str, object],
    path: Path = DEFAULT_RESEARCH_QUALITY_DB_PATH,
) -> dict[str, object]:
    allowed = {"evaluated", "rejected", "continue", "frozen"}
    clean_action = str(action).strip().casefold()
    if clean_action not in allowed:
        raise ResearchQualityError("Unbekannte Research-Entscheidung.")
    forbidden = bool(result.get("production_activated") or result.get("automatic_parameter_tuning"))
    if forbidden:
        raise ResearchQualityError("Ledger-Ereignis darf weder Produktion noch Tuning aktivieren.")
    initialize_research_quality_store(path)
    with _connect(Path(path)) as connection:
        if connection.execute(
            "SELECT 1 FROM research_hypothesis_attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone() is None:
            raise ResearchQualityError("Research-Versuch ist nicht registriert.")
        payload = {
            "quality_version": RESEARCH_QUALITY_VERSION,
            "attempt_id": attempt_id,
            "recorded_at": _aware(recorded_at),
            "action": clean_action,
            "result": dict(result),
            "automatic_strategy_selection": False,
            "validation_opened_automatically": False,
            "holdout_opened_automatically": False,
            "production_activated": False,
        }
        fingerprint = _fingerprint(
            {
                "quality_version": RESEARCH_QUALITY_VERSION,
                "attempt_id": attempt_id,
                "action": clean_action,
                "result": dict(result),
            }
        )
        event_id = f"event-{fingerprint[:32]}"
        inserted = connection.execute(
            "INSERT OR IGNORE INTO research_hypothesis_events VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, attempt_id, payload["recorded_at"], clean_action, _json(payload), fingerprint),
        ).rowcount == 1
    return {"inserted": inserted, "event": payload, "event_id": event_id}


def _dependency_components(rows: Sequence[Mapping[str, object]]) -> list[list[int]]:
    """Build conservative, deterministic components from known trade dependencies."""
    parents = list(range(len(rows)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parents[max(a, b)] = min(a, b)

    seen: dict[tuple[str, str], int] = {}
    identity_keys = (
        "dependency_cluster",
        "signal_day",
        "issuer_id",
        "economic_instrument_id",
        "correlation_cluster",
    )
    for index, row in enumerate(rows):
        for key in identity_keys:
            value = str(row.get(key) or "").strip().casefold()
            if not value or value in {"unknown", "unbekannt", "none"}:
                continue
            identity = (key, value)
            if identity in seen:
                union(index, seen[identity])
            else:
                seen[identity] = index
    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        components[find(index)].append(index)
    return [components[key] for key in sorted(components)]


def _distinct_known(rows: Sequence[Mapping[str, object]], key: str) -> int:
    values = {
        str(row.get(key)).strip().casefold()
        for row in rows
        if str(row.get(key) or "").strip().casefold() not in {"", "unknown", "unbekannt", "none"}
    }
    return len(values)


def robustness_metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ordered = sorted(rows, key=lambda row: (str(row.get("signal_day") or ""), str(row.get("candidate_id") or "")))
    values = [_number(row.get("result_r")) for row in ordered]
    results = [value for value in values if value is not None]
    gross_profit = sum(value for value in results if value > 0)
    gross_loss = abs(sum(value for value in results if value < 0))
    cumulative = peak = maximum_drawdown = 0.0
    loss_streak = maximum_loss_streak = 0
    for value in results:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown = max(maximum_drawdown, peak - cumulative)
        loss_streak = loss_streak + 1 if value <= 0 else 0
        maximum_loss_streak = max(maximum_loss_streak, loss_streak)
    evaluated_rows = [row for row in ordered if _number(row.get("result_r")) is not None]
    components = _dependency_components(evaluated_rows)
    years: dict[str, list[float]] = defaultdict(list)
    for row in ordered:
        value = _number(row.get("result_r"))
        if value is None:
            continue
        years[str(row.get("signal_day") or "")[:4] or "unknown"].append(value)
    cluster_means = [
        sum(float(evaluated_rows[index]["result_r"]) for index in component) / len(component)
        for component in components
        if component
    ]
    cluster_mean = sum(cluster_means) / len(cluster_means) if cluster_means else None
    cluster_se = None
    if len(cluster_means) >= 2:
        variance = sum((value - float(cluster_mean)) ** 2 for value in cluster_means) / (len(cluster_means) - 1)
        cluster_se = math.sqrt(variance / len(cluster_means))
    yearly = {year: sum(group) / len(group) for year, group in sorted(years.items())}
    yearly_total_r = {year: sum(group) for year, group in sorted(years.items())}
    positive_year_totals = [value for value in yearly_total_r.values() if value > 0]
    positive_contribution = sum(positive_year_totals)
    top_year_share = (
        max(positive_year_totals) / positive_contribution if positive_contribution > 0 else None
    )
    return {
        "raw_cases": len(rows),
        "evaluated": len(results),
        "effective_independent_cases": min(len(components), len(results)),
        "independent_signal_clusters": len(components),
        "dependency_cluster_method": (
            "connected_components_over_signal_day_issuer_economic_instrument_and_correlation_cluster"
        ),
        "same_day_clusters": _distinct_known(evaluated_rows, "signal_day"),
        "issuer_clusters": _distinct_known(evaluated_rows, "issuer_id"),
        "economic_instrument_clusters": _distinct_known(evaluated_rows, "economic_instrument_id"),
        "correlation_clusters": _distinct_known(evaluated_rows, "correlation_cluster"),
        "regime_clusters": _distinct_known(evaluated_rows, "market_phase"),
        "volatility_regime_clusters": _distinct_known(evaluated_rows, "volatility_regime"),
        "sector_clusters": _distinct_known(evaluated_rows, "sector"),
        "region_clusters": _distinct_known(evaluated_rows, "region"),
        "expectancy_r": sum(results) / len(results) if results else None,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "hit_rate_pct": sum(value > 0 for value in results) / len(results) * 100 if results else None,
        "maximum_drawdown_r": maximum_drawdown,
        "maximum_loss_streak": maximum_loss_streak,
        "average_mfe_r": _mean(row.get("mfe_r") for row in ordered),
        "average_mae_r": _mean(row.get("mae_r") for row in ordered),
        "cluster_mean_expectancy_r": cluster_mean,
        "cluster_robust_standard_error_r": cluster_se,
        "time_stability": time_stability_report(
            ordered,
            yearly=yearly,
            yearly_total_r=yearly_total_r,
            top_year_share=top_year_share,
        ),
        "regime_stability": segment_stability_report(ordered),
        "raw_trade_count_is_independent_evidence": False,
    }


def _mean(values) -> float | None:
    clean = [number for value in values if (number := _number(value)) is not None]
    return sum(clean) / len(clean) if clean else None


def time_stability_report(
    rows: Sequence[Mapping[str, object]],
    *,
    yearly: Mapping[str, float] | None = None,
    yearly_total_r: Mapping[str, float] | None = None,
    top_year_share: float | None = None,
) -> dict[str, object]:
    grouped: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        value = _number(row.get("result_r"))
        day = str(row.get("signal_day") or "")
        if value is not None and re.match(r"^\d{4}", day):
            grouped[int(day[:4])].append(value)
    annual = dict(yearly or {str(year): sum(values) / len(values) for year, values in sorted(grouped.items())})

    def rolling(width: int) -> dict[str, float]:
        years = sorted(grouped)
        output = {}
        for index in range(width - 1, len(years)):
            selected = years[index - width + 1 : index + 1]
            if selected != list(range(selected[0], selected[-1] + 1)):
                continue
            values = [value for year in selected for value in grouped[year]]
            output[f"{selected[0]}-{selected[-1]}"] = sum(values) / len(values)
        return output

    evaluated_years = sorted(int(year) for year in annual if str(year).isdigit())
    longest_nonpositive = current = 0
    for year in evaluated_years:
        current = current + 1 if annual[str(year)] <= 0 else 0
        longest_nonpositive = max(longest_nonpositive, current)
    before = [value for year, values in grouped.items() if year < 2020 for value in values]
    after = [value for year, values in grouped.items() if year >= 2020 for value in values]
    cumulative = peak = maximum_temporal_drawdown = 0.0
    for row in sorted(rows, key=lambda item: (str(item.get("signal_day") or ""), str(item.get("candidate_id") or ""))):
        value = _number(row.get("result_r"))
        if value is None:
            continue
        cumulative += value
        peak = max(peak, cumulative)
        maximum_temporal_drawdown = max(maximum_temporal_drawdown, peak - cumulative)
    return {
        "by_calendar_year": annual,
        "total_r_by_calendar_year": dict(yearly_total_r or {}),
        "rolling_2_year_expectancy": rolling(2),
        "rolling_3_year_expectancy": rolling(3),
        "profitable_year_share_pct": (
            sum(value > 0 for value in annual.values()) / len(annual) * 100 if annual else None
        ),
        "worst_year": min(annual, key=annual.get) if annual else None,
        "worst_year_expectancy_r": min(annual.values()) if annual else None,
        "longest_nonpositive_edge_years": longest_nonpositive,
        "maximum_temporal_drawdown_r": maximum_temporal_drawdown,
        "before_2020_expectancy_r": sum(before) / len(before) if before else None,
        "from_2020_expectancy_r": sum(after) / len(after) if after else None,
        "largest_positive_year_contribution_share": top_year_share,
        "time_concentration_visible": True,
    }


def segment_stability_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for dimension in ("market_phase", "volatility_regime"):
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            value = _number(row.get("result_r"))
            if value is not None:
                grouped[str(row.get(dimension) or "unknown")].append(value)
        output[dimension] = {
            key: {
                "cases": len(values),
                "expectancy_r": sum(values) / len(values),
                "positive": sum(values) / len(values) > 0,
            }
            for key, values in sorted(grouped.items())
        }
    return output


def regime_matched_placebo(
    selected_rows: Sequence[Mapping[str, object]],
    eligible_control_rows: Sequence[Mapping[str, object]],
    *,
    seed_material: str,
) -> dict[str, object]:
    """Select controls by pre-result identity hash within matching regimes."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in selected_rows:
        counts[(str(row.get("market_phase") or "unknown"), str(row.get("volatility_regime") or "unknown"))] += 1
    selected_ids = {str(row.get("candidate_id") or "") for row in selected_rows}
    controls = []
    for regime, count in sorted(counts.items()):
        pool = [
            row for row in eligible_control_rows
            if str(row.get("candidate_id") or "") not in selected_ids
            and (str(row.get("market_phase") or "unknown"), str(row.get("volatility_regime") or "unknown")) == regime
        ]
        pool.sort(
            key=lambda row: hashlib.sha256(
                f"{seed_material}|{row.get('candidate_id')}|{row.get('signal_day')}".encode("utf-8")
            ).hexdigest()
        )
        controls.extend(pool[:count])
    real = robustness_metrics(selected_rows)
    placebo = robustness_metrics(controls)
    return {
        "placebo_version": PLACEBO_VERSION,
        "selection": "stable_identity_hash_within_same_market_and_volatility_regime",
        "selection_uses_outcomes": False,
        "future_information_used": False,
        "real": real,
        "placebo": placebo,
        "requested_control_cases": len(selected_rows),
        "selected_control_cases": len(controls),
        "complete_regime_matching": len(controls) == len(selected_rows),
        "difference": {
            key: (
                float(real[key]) - float(placebo[key])
                if _number(real.get(key)) is not None and _number(placebo.get(key)) is not None
                else None
            )
            for key in ("expectancy_r", "profit_factor", "hit_rate_pct", "maximum_drawdown_r")
        },
        "placebo_is_strategy": False,
        "uncertainty": "Clusterrobuste Standardfehler und effektive Fallzahlen beider Gruppen beachten.",
    }


def placebo_test_suite(
    selected_rows: Sequence[Mapping[str, object]],
    eligible_control_rows: Sequence[Mapping[str, object]],
    *,
    seed_material: str,
    shifted_signal_rows: Sequence[Mapping[str, object]] = (),
    matched_random_entry_rows: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Compare supplied causal controls without turning any placebo into a strategy."""
    tests = {
        "neutral_regime_matched_control": regime_matched_placebo(
            selected_rows, eligible_control_rows, seed_material=seed_material
        )
    }
    for name, rows in (
        ("time_shifted_same_asset", shifted_signal_rows),
        ("random_entry_matched_holding_window", matched_random_entry_rows),
    ):
        if not rows:
            tests[name] = {"status": "not_available", "reason": "Keine kausal vorbereiteten Kontrollzeilen übergeben."}
            continue
        real, placebo = robustness_metrics(selected_rows), robustness_metrics(rows)
        tests[name] = {
            "status": "available",
            "real": real,
            "placebo": placebo,
            "difference": {
                key: _difference(real, placebo, key)
                for key in ("expectancy_r", "profit_factor", "hit_rate_pct", "maximum_drawdown_r")
            },
            "control_rows_declared_point_in_time": all(
                row.get("point_in_time_prepared") is True for row in rows
            ),
            "selection_uses_outcomes": False,
            "placebo_is_strategy": False,
        }
    return {
        "tests": tests,
        "same_cost_and_execution_contract_required": True,
        "same_holding_window_contract_required": True,
        "future_information_used": False,
        "automatic_strategy_selection": False,
    }


def parameter_plateau_report(variants: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ordered = sorted((dict(row) for row in variants), key=lambda row: float(row["parameter_value"]))
    positive = [row for row in ordered if (_number(row.get("expectancy_r")) or 0) > 0]
    isolated_best = False
    if ordered:
        best_index = max(range(len(ordered)), key=lambda index: _number(ordered[index].get("expectancy_r")) or -math.inf)
        neighbors = ordered[max(0, best_index - 1) : best_index] + ordered[best_index + 1 : best_index + 2]
        isolated_best = bool(neighbors and all((_number(row.get("expectancy_r")) or 0) <= 0 for row in neighbors))
    cases = [_number(row.get("raw_cases")) for row in ordered]
    known_cases = [value for value in cases if value is not None]
    median_cases = sorted(known_cases)[len(known_cases) // 2] if known_cases else None
    return {
        "plateau_version": PLATEAU_VERSION,
        "variants": ordered,
        "predeclared_neighborhood_only": True,
        "single_best_parameter_selected": False,
        "positive_variant_share": len(positive) / len(ordered) if ordered else None,
        "isolated_positive_peak": isolated_best,
        "wide_positive_zone_visible": len(positive) >= 2,
        "neighbor_profit_factors": [row.get("profit_factor") for row in ordered],
        "neighbor_drawdowns_r": [row.get("maximum_drawdown_r") for row in ordered],
        "neighbor_case_counts": cases,
        "smallest_to_median_case_ratio": (
            min(known_cases) / median_cases if known_cases and median_cases and median_cases > 0 else None
        ),
        "robustness_dimensions": {
            "expectancy": "reported",
            "profit_factor": "reported",
            "drawdown": "reported",
            "case_count": "reported",
        },
        "automatic_robust_c_approval": False,
        "validation_opened": False,
        "holdout_opened": False,
    }


def feature_ablation_report(
    baseline: Mapping[str, object],
    ablations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    base_features = set(str(value) for value in baseline.get("features") or [])
    rows = []
    for raw in ablations:
        item = dict(raw)
        removed = str(item.get("removed_feature") or "")
        remaining = set(str(value) for value in item.get("features") or [])
        if not removed or remaining != base_features - {removed}:
            raise ResearchQualityError("Ablation darf genau ein vorhandenes Feature entfernen.")
        metrics = dict(item.get("metrics") or {})
        base_metrics = dict(baseline.get("metrics") or {})
        rows.append(
            {
                **item,
                "delta_expectancy_r": _difference(metrics, base_metrics, "expectancy_r"),
                "delta_profit_factor": _difference(metrics, base_metrics, "profit_factor"),
                "delta_maximum_drawdown_r": _difference(metrics, base_metrics, "maximum_drawdown_r"),
                "delta_cases": _difference(metrics, base_metrics, "raw_cases"),
                "trade_retention": (
                    float(metrics["raw_cases"]) / float(base_metrics["raw_cases"])
                    if _number(metrics.get("raw_cases")) is not None
                    and _number(base_metrics.get("raw_cases")) not in (None, 0)
                    else None
                ),
                "time_stability": metrics.get("time_stability"),
                "regime_stability": metrics.get("regime_stability"),
                "simpler_expectancy_not_lower": (
                    _number(metrics.get("expectancy_r")) is not None
                    and _number(base_metrics.get("expectancy_r")) is not None
                    and float(metrics["expectancy_r"]) >= float(base_metrics["expectancy_r"])
                ),
                "simpler_profit_factor_not_lower": (
                    _number(metrics.get("profit_factor")) is not None
                    and _number(base_metrics.get("profit_factor")) is not None
                    and float(metrics["profit_factor"]) >= float(base_metrics["profit_factor"])
                ),
                "only_removed_feature_changed": True,
            }
        )
    return {
        "baseline": dict(baseline),
        "ablations": rows,
        "simpler_strategy_preferred_when_oos_similar": True,
        "automatic_feature_removal": False,
    }


def _difference(left: Mapping[str, object], right: Mapping[str, object], key: str) -> float | None:
    a, b = _number(left.get(key)), _number(right.get(key))
    return a - b if a is not None and b is not None else None


def entry_efficiency_report(
    *,
    entry: float,
    stop: float,
    direction: str,
    bars: Sequence[Mapping[str, object]],
    final_result_r: float | None = None,
) -> dict[str, object]:
    if direction not in {"long", "short"}:
        raise ResearchQualityError("Entry-Efficiency unterstützt long oder short.")
    risk = entry - stop if direction == "long" else stop - entry
    if risk <= 0:
        raise ResearchQualityError("Stop und Entry besitzen keine gültige Risikodistanz.")
    paths = []
    peak_mfe = peak_mae = 0.0
    peak_mfe_session = peak_mae_session = None
    first = {"plus_0_5r": None, "plus_1r": None, "minus_0_5r": None, "minus_1r": None}
    same_bar_ambiguities = []
    for session, bar in enumerate(bars, start=1):
        high, low = _number(bar.get("High")), _number(bar.get("Low"))
        if high is None or low is None:
            continue
        mfe = (high - entry) / risk if direction == "long" else (entry - low) / risk
        mae = (low - entry) / risk if direction == "long" else (entry - high) / risk
        paths.append((session, mfe, mae))
        if mfe > peak_mfe:
            peak_mfe, peak_mfe_session = mfe, session
        if mae < peak_mae:
            peak_mae, peak_mae_session = mae, session
        for key, matched in (
            ("plus_0_5r", mfe >= 0.5), ("plus_1r", mfe >= 1.0),
            ("minus_0_5r", mae <= -0.5), ("minus_1r", mae <= -1.0),
        ):
            if matched and first[key] is None:
                first[key] = session
        if mfe >= 0.5 and mae <= -0.5:
            same_bar_ambiguities.append(session)
    def horizon(number: int, kind: str) -> float | None:
        values = [row[1 if kind == "mfe" else 2] for row in paths if row[0] <= number]
        return (max(values) if kind == "mfe" else min(values)) if values else None
    plus, minus = first["plus_0_5r"], first["minus_0_5r"]
    first_half = (
        "plus_0_5r" if plus is not None and (minus is None or plus < minus)
        else "minus_0_5r" if minus is not None and (plus is None or minus < plus)
        else "ambiguous_same_daily_bar" if plus is not None and minus is not None
        else "neither"
    )
    if peak_mfe < 0.5 and peak_mae <= -1.0:
        diagnostic_class = "A"
        diagnostic_reason = "Richtung oder Setup vermutlich falsch; kaum günstige Bewegung vor voller Risikobelastung."
    elif final_result_r is not None and final_result_r <= 0 and peak_mfe >= 1.0:
        diagnostic_class = "C"
        diagnostic_reason = "Entry erreichte mindestens 1R MFE, das Endergebnis blieb jedoch nicht positiv."
    elif peak_mfe >= 0.5 and (first_half in {"minus_0_5r", "ambiguous_same_daily_bar"} or peak_mae <= -0.5):
        diagnostic_class = "B"
        diagnostic_reason = "Richtung teilweise richtig, aber Entry erlitt früh oder zugleich deutliche Gegenbewegung."
    else:
        diagnostic_class = "D"
        diagnostic_reason = "Aus den verfügbaren Daily-Daten ist keine eindeutige Ursache ableitbar."
    return {
        "entry_efficiency_version": ENTRY_EFFICIENCY_VERSION,
        "mfe_r": {f"{n}s": horizon(n, "mfe") for n in (1, 3, 5)},
        "mae_r": {f"{n}s": horizon(n, "mae") for n in (1, 3, 5)},
        "sessions_to": first,
        "first_half_r_event": first_half,
        "peak_mfe_r": peak_mfe,
        "peak_mae_r": peak_mae,
        "sessions_to_peak_mfe": peak_mfe_session,
        "sessions_to_peak_mae": peak_mae_session,
        "same_daily_bar_sequence_ambiguities": same_bar_ambiguities,
        "diagnostic_class": diagnostic_class,
        "diagnostic_reason": diagnostic_reason,
        "diagnostic_class_is_strategy_grade": False,
        "intrabar_sequence_claimed": False,
        "future_bars_outside_supplied_window_used": 0,
    }


def execution_stress_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    scenarios = {}
    for name, penalty in STRESS_SCENARIOS.items():
        stressed = []
        for row in rows:
            value = _number(row.get("result_r"))
            if value is None:
                continue
            applied = penalty if name != "conservative_gap_stop" or bool(row.get("gap_affected")) else 0.0
            stressed.append({**dict(row), "result_r": value - applied})
        scenarios[name] = {
            "penalty_r": penalty,
            "metrics": robustness_metrics(stressed),
            "historical_result_rewritten": False,
        }
    base = scenarios["base"]["metrics"]
    for name, payload in scenarios.items():
        payload["change_vs_base"] = {
            key: _difference(payload["metrics"], base, key)
            for key in ("expectancy_r", "profit_factor", "maximum_drawdown_r", "raw_cases")
        }
    return {
        "stress_version": EXECUTION_STRESS_VERSION,
        "scenarios": scenarios,
        "predeclared": True,
        "stress_is_historical_reality": False,
        "automatic_rule_change": False,
    }


def complexity_report(rule: Mapping[str, object], features: Sequence[str]) -> dict[str, object]:
    active = {str(key): value for key, value in rule.items() if value not in (None, False, "")}
    parameter_count = sum(isinstance(value, (int, float)) and not isinstance(value, bool) for value in active.values())
    families = {str(value).split(".", 1)[0] for value in features}
    return {
        "active_rules": len(active),
        "parameters": parameter_count,
        "feature_families": len(families),
        "features": sorted(set(str(value) for value in features)),
        "simpler_strategy_preferred_when_oos_similar": True,
        "complexity_requires_incremental_robust_edge": True,
    }


def survivorship_bias_audit(
    *,
    uses_current_frozen_universe: bool,
    historical_constituents_available: bool,
    delistings_available: bool,
    bankruptcies_available: bool,
    point_in_time_universe_available: bool,
) -> dict[str, object]:
    missing = []
    for available, label in (
        (historical_constituents_available, "historical_constituents"),
        (delistings_available, "delistings"),
        (bankruptcies_available, "bankruptcies"),
        (point_in_time_universe_available, "point_in_time_universe"),
    ):
        if not available:
            missing.append(label)
    fully_excluded = not uses_current_frozen_universe and not missing
    return {
        "current_frozen_universe_used": bool(uses_current_frozen_universe),
        "historical_constituents_available": bool(historical_constituents_available),
        "delistings_available": bool(delistings_available),
        "bankruptcies_available": bool(bankruptcies_available),
        "point_in_time_universe_available": bool(point_in_time_universe_available),
        "missing_evidence": missing,
        "survivorship_bias_fully_excluded": fully_excluded,
        "broad_research_blocked": False,
        "future_extensions": ["historical_constituents", "delisting_data", "point_in_time_universe"],
    }


def forward_research_quality_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Reuse diagnostics without merging historical, forward, paper or shadow evidence."""
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        evidence_type = str(row.get("evidence_type") or "unknown").casefold()
        grouped[evidence_type].append(row)
    return {
        "evidence": {key: robustness_metrics(value) for key, value in sorted(grouped.items())},
        "entry_efficiency_fields_supported": True,
        "cost_and_gap_fields_supported": True,
        "market_regime_fields_supported": True,
        "evidence_types_merged": False,
        "historical_results_modified": False,
        "automatic_strategy_selection": False,
    }


def build_research_quality_report(
    *,
    attempt: Mapping[str, object],
    selected_rows: Sequence[Mapping[str, object]],
    eligible_control_rows: Sequence[Mapping[str, object]],
    seed_material: str,
    rule: Mapping[str, object],
    features: Sequence[str],
    parameter_variants: Sequence[Mapping[str, object]] = (),
    ablations: Sequence[Mapping[str, object]] = (),
    entry_efficiency: Sequence[Mapping[str, object]] = (),
    survivorship: Mapping[str, object] | None = None,
) -> dict[str, object]:
    metrics = robustness_metrics(selected_rows)
    placebo = regime_matched_placebo(selected_rows, eligible_control_rows, seed_material=seed_material)
    plateau = parameter_plateau_report(parameter_variants) if parameter_variants else {
        "status": "not_applicable_or_not_yet_evaluated",
        "automatic_robust_c_approval": False,
    }
    baseline = {"features": list(features), "metrics": metrics}
    ablation = feature_ablation_report(baseline, ablations) if ablations else {
        "status": "not_yet_evaluated",
        "automatic_feature_removal": False,
    }
    stress = execution_stress_report(selected_rows)
    survivorship_report = dict(survivorship or survivorship_bias_audit(
        uses_current_frozen_universe=True,
        historical_constituents_available=False,
        delistings_available=False,
        bankruptcies_available=False,
        point_in_time_universe_available=False,
    ))
    attempts = int(attempt.get("family_attempt_number") or 1)
    dimensions = {
        "positive_expectancy_after_costs": (_number(metrics.get("expectancy_r")) or 0) > 0,
        "profit_factor": metrics.get("profit_factor"),
        "maximum_drawdown_r": metrics.get("maximum_drawdown_r"),
        "effective_independent_cases": metrics.get("effective_independent_cases"),
        "time_stability": metrics.get("time_stability"),
        "regime_stability": metrics.get("regime_stability"),
        "parameter_plateau": plateau,
        "placebo_advantage": placebo.get("difference"),
        "feature_ablation": ablation,
        "execution_stress": stress,
        "complexity": complexity_report(rule, features),
    }
    return {
        "quality_version": RESEARCH_QUALITY_VERSION,
        "research_objective": RESEARCH_OBJECTIVE,
        "forbidden_objective": FORBIDDEN_OBJECTIVE,
        "attempt": dict(attempt),
        "research_attempt_number_in_family": attempts,
        "metrics": metrics,
        "entry_efficiency": list(entry_efficiency),
        "robustness_dimensions": dimensions,
        "survivorship_bias_audit": survivorship_report,
        "why_could_this_be_false_positive": false_positive_risks(
            attempts_in_family=attempts,
            metrics=metrics,
            plateau=plateau,
            survivorship_free=bool(survivorship_report.get("survivorship_bias_fully_excluded")),
            stress=stress,
        ),
        "abc_result": "manual_review_required",
        "clear_reason": "Alle Robustheitsdimensionen werden getrennt berichtet; keine automatische C- oder Produktionsfreigabe.",
        "validation_opened": False,
        "holdout_opened": False,
        "automatic_strategy_selection": False,
        "automatic_parameter_tuning": False,
        "automatic_confluence_building": False,
        "production_activated": False,
    }


def record_development_quality_ledger(
    development_report: Mapping[str, object],
    *,
    dataset_fingerprint: str,
    feature_fingerprint: str,
    code_fingerprint: str,
    recorded_at: str,
    path: Path = DEFAULT_RESEARCH_QUALITY_DB_PATH,
) -> dict[str, object]:
    """Append Development attempts and their immutable summaries to the separate ledger."""
    inserted_attempts = inserted_events = 0
    rows = list(development_report.get("hypotheses") or [])
    related = [str(row.get("hypothesis_id") or "") for row in rows]
    for row in rows:
        hypothesis_id = str(row.get("hypothesis_id") or "").strip()
        registered = register_research_hypothesis(
            hypothesis_id=hypothesis_id,
            name=hypothesis_id.replace("_", " "),
            description="Vorab festgelegte Broad-Development-Einzelhypothese.",
            defined_at=recorded_at,
            research_origin=str(development_report.get("pattern_version") or "broad_development"),
            family_id="broad-development-single-feature",
            features=[hypothesis_id],
            parameters={},
            dataset_fingerprint=dataset_fingerprint,
            feature_fingerprint=feature_fingerprint,
            code_fingerprint=code_fingerprint,
            related_hypotheses=[value for value in related if value != hypothesis_id],
            path=path,
        )
        inserted_attempts += int(bool(registered["inserted"]))
        selected = dict(row.get("selected") or {})
        event = append_research_hypothesis_event(
            str(registered["attempt"]["attempt_id"]),
            recorded_at=recorded_at,
            action="evaluated",
            result={
                "accessed_stages": ["development"],
                "development_accessed": True,
                "validation_accessed": False,
                "holdout_accessed": False,
                "raw_cases": selected.get("cases"),
                "effective_independent_cases": selected.get("effective_independent_cases"),
                "classification": row.get("classification"),
                "decision": "continue" if row.get("eligible_for_manual_fixed_challenger") else "evaluated",
                "production_activated": False,
                "automatic_parameter_tuning": False,
            },
            path=path,
        )
        inserted_events += int(bool(event["inserted"]))
    return {
        "hypotheses_seen": len(rows),
        "attempts_inserted": inserted_attempts,
        "events_inserted": inserted_events,
        "audit": research_quality_store_audit(path),
        "validation_opened": False,
        "holdout_opened": False,
        "production_activated": False,
    }


def false_positive_risks(
    *,
    attempts_in_family: int,
    metrics: Mapping[str, object],
    plateau: Mapping[str, object] | None,
    survivorship_free: bool,
    stress: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    risks = []
    if attempts_in_family > 1:
        risks.append({"risk": "multiple_testing", "detail": f"{attempts_in_family} Versuche in derselben Familie."})
    if int(metrics.get("effective_independent_cases") or 0) < int(metrics.get("raw_cases") or 0):
        risks.append({"risk": "dependent_cases", "detail": "Rohfälle sind nicht vollständig unabhängig."})
    concentration = _number(dict(metrics.get("time_stability") or {}).get("largest_positive_year_contribution_share"))
    if concentration is not None and concentration > 0.5:
        risks.append({"risk": "time_concentration", "detail": "Mehr als die Hälfte des positiven Jahresbeitrags stammt aus einem Jahr."})
    if plateau and plateau.get("isolated_positive_peak"):
        risks.append({"risk": "parameter_sensitivity", "detail": "Positiver Edge liegt nur an einem isolierten Parameterwert."})
    if not survivorship_free:
        risks.append({"risk": "survivorship_bias", "detail": "Historische Universumsbasis ist nicht vollständig survivorship-bias-frei."})
    if stress:
        base = _number(stress["scenarios"]["base"]["metrics"].get("expectancy_r"))
        severe = _number(stress["scenarios"]["higher_total_cost"]["metrics"].get("expectancy_r"))
        if base is not None and base > 0 and (severe is None or severe <= 0):
            risks.append({"risk": "execution_sensitivity", "detail": "Edge verschwindet bei leicht höheren Gesamtkosten."})
    return risks


def research_quality_store_audit(path: Path = DEFAULT_RESEARCH_QUALITY_DB_PATH) -> dict[str, object]:
    initialize_research_quality_store(path)
    with _connect(Path(path)) as connection:
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        attempts = int(connection.execute("SELECT COUNT(*) FROM research_hypothesis_attempts").fetchone()[0])
        events = int(connection.execute("SELECT COUNT(*) FROM research_hypothesis_events").fetchone()[0])
        families = int(connection.execute("SELECT COUNT(DISTINCT family_id) FROM research_hypothesis_attempts").fetchone()[0])
        family_attempts = {
            str(row["family_id"]): int(row["attempts"])
            for row in connection.execute(
                "SELECT family_id, COUNT(*) attempts FROM research_hypothesis_attempts GROUP BY family_id ORDER BY family_id"
            )
        }
        invalid_fingerprints = 0
        for row in connection.execute(
            "SELECT payload_json, payload_fingerprint FROM research_hypothesis_attempts"
        ):
            if _fingerprint(json.loads(row["payload_json"])) != str(row["payload_fingerprint"]):
                invalid_fingerprints += 1
        for row in connection.execute(
            "SELECT attempt_id, action, payload_json, payload_fingerprint FROM research_hypothesis_events"
        ):
            payload = json.loads(row["payload_json"])
            expected = _fingerprint(
                {
                    "quality_version": payload.get("quality_version"),
                    "attempt_id": row["attempt_id"],
                    "action": row["action"],
                    "result": payload.get("result") or {},
                }
            )
            if expected != str(row["payload_fingerprint"]):
                invalid_fingerprints += 1
    return {
        "schema_version": RESEARCH_QUALITY_SCHEMA_VERSION,
        "quality_version": RESEARCH_QUALITY_VERSION,
        "quick_check": quick,
        "registered_hypotheses": attempts,
        "research_families": families,
        "attempts_by_family": family_attempts,
        "ledger_events": events,
        "invalid_fingerprints": invalid_fingerprints,
        "append_only": True,
        "stage_order": list(STAGE_ORDER),
        "automatic_strategy_selection": False,
        "automatic_parameter_tuning": False,
        "validation_mining": False,
        "holdout_mining": False,
        "production_activation": False,
        "research_objective": RESEARCH_OBJECTIVE,
    }
