from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _holding_days(start: object, end: object) -> float | None:
    try:
        start_time = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        if (start_time.tzinfo is None) != (end_time.tzinfo is None):
            return None
        seconds = (end_time - start_time).total_seconds()
    except (TypeError, ValueError):
        return None
    return round(seconds / 86_400, 3) if seconds >= 0 else None


def _terminal_outcome(signal: dict) -> dict | None:
    snapshot = dict(signal.get("snapshot") or {})
    plan = dict(snapshot.get("order_plan") or {})
    target_2_exists = plan.get("target_2_original") is not None
    terminal_types = {"stop_reached", "target_2_reached"}
    if not target_2_exists:
        terminal_types.add("target_1_reached")
    candidates = [
        event for event in signal.get("events") or [] if event.get("event_type") in terminal_types
    ]
    return candidates[-1] if candidates else None


def _signal_status(signal: dict) -> str:
    events = list(signal.get("events") or [])
    terminal = _terminal_outcome(signal)
    if terminal is not None:
        return str(terminal["event_type"])
    visible_states = {
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
        "ambiguous_sequence",
        "not_evaluable",
        "paper_entry_opened",
        "still_active",
    }
    for event in reversed(events):
        event_type = str(event.get("event_type") or "")
        if event_type not in visible_states:
            continue
        if event_type == "not_evaluable" and bool(
            dict(event.get("payload") or {}).get("retry_allowed")
        ):
            continue
        if event_type in {"paper_entry_opened", "still_active"}:
            return "still_active"
        return event_type
    return "stored"


def swing_forward_archive_rows(
    signals: list[dict],
    *,
    user_signal_ids: set[str] | None = None,
    tr_references: dict[str, dict] | None = None,
) -> list[dict]:
    documented_user_signals = {str(value) for value in (user_signal_ids or set())}
    rows: list[dict] = []
    for signal in signals:
        snapshot = dict(signal.get("snapshot") or {})
        asset = dict(snapshot.get("asset") or {})
        strategy = dict(snapshot.get("strategy") or {})
        plan = dict(snapshot.get("order_plan") or {})
        forward_evidence = dict(snapshot.get("forward_evidence") or {})
        stored_tr = dict(snapshot.get("trade_republic") or {})
        analysis_listing_key = str(stored_tr.get("analysis_listing_key") or "")
        signal_id = str(signal.get("signal_id") or "")
        current_tr = dict(
            (tr_references or {}).get(signal_id)
            or (tr_references or {}).get(analysis_listing_key)
            or {}
        )
        tr_status = str(current_tr.get("status") or stored_tr.get("status") or "unbekannt")
        tr_execution_ready = bool(
            current_tr.get("execution_ready")
            if "execution_ready" in current_tr
            else stored_tr.get("execution_ready_at_signal")
        )
        tr_listing = dict(current_tr.get("tr_listing") or stored_tr.get("tr_listing") or {})
        entry_event = next(
            (
                event
                for event in signal.get("events") or []
                if event.get("event_type") == "paper_entry_opened"
            ),
            None,
        )
        outcome = _terminal_outcome(signal)
        outcome_payload = dict((outcome or {}).get("payload") or {})
        active_measurements = [
            event
            for event in signal.get("events") or []
            if event.get("event_type") == "still_active"
        ]
        active_measurement = max(
            active_measurements,
            key=lambda event: (
                str(event.get("occurred_at") or ""),
                bool((event.get("payload") or {}).get("active_measurement_version")),
                str(event.get("event_id") or ""),
            ),
            default=None,
        )
        movement_event = outcome or active_measurement
        movement_payload = dict((movement_event or {}).get("payload") or {})
        retryable_provider_event = next(
            (
                event
                for event in reversed(signal.get("events") or [])
                if event.get("event_type") == "not_evaluable"
                and bool(dict(event.get("payload") or {}).get("retry_allowed"))
            ),
            None,
        )
        outcome_source_key = str((outcome or {}).get("source_key") or "")
        fx_valuation = next(
            (
                event
                for event in signal.get("events") or []
                if event.get("event_type") == "historical_fx_valuation"
                and str((event.get("payload") or {}).get("terminal_source_key") or "") == outcome_source_key
            ),
            None,
        )
        fx_payload = dict((fx_valuation or {}).get("payload") or {})
        result_r = _number(outcome_payload.get("result_r"))
        result_state = "Noch offen/nicht wertbar"
        if result_r is not None:
            result_state = "Gewinn" if result_r > 0 else "Verlust/Null"
        rows.append(
            {
                "Signal-ID": signal_id,
                "Asset": str(asset.get("name") or asset.get("ticker") or "Unbekannt"),
                "Ticker": str(asset.get("ticker") or ""),
                "ISIN": str(asset.get("isin") or ""),
                "TR-Status": tr_status,
                "TR-Listing": " · ".join(
                    value
                    for value in (
                        str(tr_listing.get("ticker") or ""),
                        str(tr_listing.get("isin") or ""),
                        str(tr_listing.get("exchange") or ""),
                    )
                    if value
                ),
                "TR-handelbares Listing": "Ja" if tr_status == "TR handelbar" else "Nein",
                "TR-ausführbarer Plan": (
                    "Ja" if tr_status == "TR handelbar" and tr_execution_ready else "Nein"
                ),
                "Setup": str(strategy.get("setup_type") or "Unbekannt"),
                "Einstiegsmethode": str(plan.get("entry_method") or "Unbekannt"),
                "Asset-Typ": str(asset.get("asset_type") or "Unbekannt"),
                "Region": str(asset.get("region") or "Unbekannt"),
                "Marktphase": str(strategy.get("market_phase") or "Unbekannt"),
                "Volatilitätsregime": str(strategy.get("volatility_regime") or "Nicht verfügbar"),
                "Evidenzart": str(forward_evidence.get("kind") or "scanner_released"),
                "Nutzerportfolio freigegeben": (
                    "Ja" if forward_evidence.get("user_portfolio_released", True) else "Nein"
                ),
                "Shadow-Grund": str(forward_evidence.get("exclusion_reason") or ""),
                "Signalzeit": str(snapshot.get("signal_at") or ""),
                "Status": _signal_status(signal),
                "Paper-Einstieg": (
                    (entry_event.get("payload") or {}).get("paper_entry_after_costs_original")
                    if entry_event
                    else None
                ),
                "Paper-Einstiegszeit": entry_event.get("occurred_at") if entry_event else None,
                "Paper-Ausstiegszeit": outcome.get("occurred_at") if outcome else None,
                "Haltedauer Tage": _holding_days(
                    entry_event.get("occurred_at") if entry_event else None,
                    movement_event.get("occurred_at") if movement_event else None,
                ),
                "Ergebnis %": _number(outcome_payload.get("result_pct")),
                "Ergebnis R": result_r,
                "Aktuell %": _number(movement_payload.get("unrealized_result_pct")),
                "Aktuell R": _number(movement_payload.get("unrealized_result_r")),
                "Abstand Stop %": _number(movement_payload.get("distance_to_stop_pct")),
                "Abstand nächstes Ziel %": _number(
                    movement_payload.get("distance_to_next_target_pct")
                ),
                "Ergebnisstatus": result_state,
                "Max. Zwischengewinn %": _number(
                    movement_payload.get("maximum_favorable_excursion_pct")
                ),
                "Max. Zwischenverlust %": _number(
                    movement_payload.get("maximum_adverse_excursion_pct")
                ),
                "Ergebnis EUR je Einheit": _number(fx_payload.get("result_eur_per_unit")),
                "Historischer FX": "Bewertet" if fx_valuation is not None else ("Ausstehend" if outcome else "Nicht fällig"),
                "Datenqualität": str(outcome_payload.get("data_quality") or "Noch nicht abschließend"),
                "Temporärer Providerhinweis": "Ja" if retryable_provider_event else "Nein",
                "Strategieversion": str(strategy.get("strategy_version") or "Unbekannt"),
                "Quelle": str(snapshot.get("source_kind") or "Unbekannt"),
                "Nutzertrade": "Ja" if str(signal.get("signal_id") or "") in documented_user_signals else "Nein",
            }
        )
    return rows


def filter_swing_forward_archive_rows(
    rows: list[dict],
    *,
    statuses: set[str] | None = None,
    setups: set[str] | None = None,
    asset_types: set[str] | None = None,
    regions: set[str] | None = None,
    market_phases: set[str] | None = None,
    volatility_regimes: set[str] | None = None,
    evidence_kinds: set[str] | None = None,
    data_qualities: set[str] | None = None,
    fx_states: set[str] | None = None,
    strategy_versions: set[str] | None = None,
    sources: set[str] | None = None,
    user_trade_states: set[str] | None = None,
    entry_methods: set[str] | None = None,
    result_states: set[str] | None = None,
    search: str = "",
    signal_from: date | str | None = None,
    signal_to: date | str | None = None,
    minimum_result_r: float | None = None,
    maximum_result_r: float | None = None,
) -> list[dict]:
    filters = (
        ("Status", statuses),
        ("Setup", setups),
        ("Asset-Typ", asset_types),
        ("Region", regions),
        ("Marktphase", market_phases),
        ("Volatilitätsregime", volatility_regimes),
        ("Evidenzart", evidence_kinds),
        ("Datenqualität", data_qualities),
        ("Historischer FX", fx_states),
        ("Strategieversion", strategy_versions),
        ("Quelle", sources),
        ("Nutzertrade", user_trade_states),
        ("Einstiegsmethode", entry_methods),
    )

    def normalized_day(value: date | str | None) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    from_day = normalized_day(signal_from)
    to_day = normalized_day(signal_to)
    query_tokens = [token for token in str(search or "").casefold().split() if token]

    def matches(row: dict) -> bool:
        if not all(not selected or str(row.get(field) or "") in selected for field, selected in filters):
            return False
        haystack = " ".join(
            str(row.get(field) or "") for field in ("Asset", "Ticker", "ISIN", "Signal-ID")
        ).casefold()
        if query_tokens and not all(token in haystack for token in query_tokens):
            return False
        row_day = normalized_day(row.get("Signalzeit"))
        if from_day is not None and (row_day is None or row_day < from_day):
            return False
        if to_day is not None and (row_day is None or row_day > to_day):
            return False
        result_r = _number(row.get("Ergebnis R"))
        result_state = str(row.get("Ergebnisstatus") or "Noch offen/nicht wertbar")
        if result_states and result_state not in result_states:
            return False
        if minimum_result_r is not None and (result_r is None or result_r < float(minimum_result_r)):
            return False
        if maximum_result_r is not None and (result_r is None or result_r > float(maximum_result_r)):
            return False
        return True

    return [
        dict(row)
        for row in rows
        if matches(row)
    ]


def swing_asset_failure_rows(scans: list[dict], *, recurring_threshold: int = 3) -> list[dict]:
    grouped: dict[str, dict] = {}
    for scan in scans:
        snapshot = dict(scan.get("snapshot") or {})
        observed_at = str(scan.get("observed_at") or snapshot.get("observed_at") or "")
        scope = str(snapshot.get("scan_scope") or "Unbekannt")
        for failure in snapshot.get("technical_failures") or []:
            ticker = str(failure.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            current = grouped.setdefault(
                ticker,
                {
                    "Ticker": ticker,
                    "Asset": str(failure.get("asset") or ticker),
                    "Fehlschläge": 0,
                    "Erster Fehlschlag": observed_at,
                    "Letzter Fehlschlag": observed_at,
                    "Bereiche": set(),
                    "Gründe": set(),
                },
            )
            current["Fehlschläge"] += 1
            current["Letzter Fehlschlag"] = observed_at
            current["Bereiche"].add(scope)
            current["Gründe"].update(str(reason) for reason in failure.get("reasons") or [])
    rows: list[dict] = []
    for item in grouped.values():
        count = int(item["Fehlschläge"])
        rows.append(
            {
                **item,
                "Bereiche": ", ".join(sorted(item["Bereiche"])),
                "Gründe": " | ".join(sorted(item["Gründe"])),
                "Wiederkehrend": count >= max(int(recurring_threshold), 1),
                "Maßnahme": "Manuell prüfen; niemals automatisch aus dem Universum löschen.",
            }
        )
    return sorted(rows, key=lambda row: (-int(row["Fehlschläge"]), str(row["Ticker"])))


def _outcome_summary(rows: list[dict]) -> dict:
    evaluated = [row for row in rows if _number(row.get("Ergebnis R")) is not None]
    r_values = [float(row["Ergebnis R"]) for row in evaluated]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value <= 0]
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in r_values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return {
        "evaluated": len(evaluated),
        "wins": len(wins),
        "losses": len(losses),
        "hit_rate_pct": len(wins) / len(evaluated) * 100 if evaluated else None,
        "average_r": sum(r_values) / len(r_values) if r_values else None,
        "average_win_r": sum(wins) / len(wins) if wins else None,
        "average_loss_r": sum(losses) / len(losses) if losses else None,
        "profit_factor_r": sum(wins) / abs(sum(losses)) if wins and sum(losses) < 0 else None,
        "max_drawdown_r": max_drawdown if r_values else None,
    }


def _counterfactual_summary(signals: list[dict]) -> dict:
    grouped: dict[int, list[float]] = defaultdict(list)
    for signal in signals:
        for event in signal.get("events") or []:
            if event.get("event_type") != "counterfactual_outcome":
                continue
            payload = dict(event.get("payload") or {})
            horizon = payload.get("horizon_sessions")
            result = _number(payload.get("return_pct"))
            if horizon is None or result is None:
                continue
            grouped[int(horizon)].append(result)
    rows = []
    for horizon, values in sorted(grouped.items()):
        rows.append(
            {
                "horizon_sessions": horizon,
                "cases": len(values),
                "positive_rate_pct": sum(value > 0 for value in values) / len(values) * 100,
                "average_return_pct": sum(values) / len(values),
                "minimum_return_pct": min(values),
                "maximum_return_pct": max(values),
            }
        )
    return {
        "cases": sum(len(values) for values in grouped.values()),
        "rows": rows,
        "separate_from_trade_results": True,
        "automatic_rule_change": False,
    }


def swing_rejection_control_statistics(controls: list[dict]) -> dict:
    outcomes: list[dict] = []
    for control in controls:
        snapshot = dict(control.get("snapshot") or {})
        for event in control.get("events") or []:
            payload = dict(event.get("payload") or {})
            result = _number(payload.get("return_pct"))
            if result is None:
                continue
            outcomes.append(
                {
                    "horizon_sessions": int(event.get("horizon_sessions") or 0),
                    "return_pct": result,
                    "market_phase": str(snapshot.get("market_phase") or "Unbekannt"),
                    "rejection_filters": list(snapshot.get("rejection_filters") or []),
                }
            )
    grouped: dict[int, list[dict]] = defaultdict(list)
    for outcome in outcomes:
        grouped[int(outcome["horizon_sessions"])].append(outcome)
    rows = []
    for horizon, values in sorted(grouped.items()):
        returns = [float(value["return_pct"]) for value in values]
        rows.append(
            {
                "horizon_sessions": horizon,
                "cases": len(values),
                "positive_rate_pct": sum(value > 0 for value in returns) / len(returns) * 100,
                "average_return_pct": sum(returns) / len(returns),
            }
        )
    return {
        "controls": len(controls),
        "outcomes": len(outcomes),
        "rows": rows,
        "control_only": True,
        "counts_as_trade_result": False,
        "automatic_rule_change": False,
    }


def swing_forward_statistics(
    signals: list[dict],
    *,
    user_signal_ids: set[str] | None = None,
    tr_references: dict[str, dict] | None = None,
) -> dict:
    rows = swing_forward_archive_rows(
        signals,
        user_signal_ids=user_signal_ids,
        tr_references=tr_references,
    )
    statuses: dict[str, int] = defaultdict(int)
    for row in rows:
        statuses[str(row["Status"])] += 1
    segments: list[dict] = []
    for field in (
        "Setup",
        "Einstiegsmethode",
        "Asset-Typ",
        "Region",
        "Marktphase",
        "Volatilitätsregime",
        "Evidenzart",
        "Nutzerportfolio freigegeben",
        "Datenqualität",
        "Strategieversion",
        "Quelle",
        "Nutzertrade",
        "TR-Status",
        "TR-ausführbarer Plan",
    ):
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            groups[str(row.get(field) or "Unbekannt")].append(row)
        for value, grouped_rows in sorted(groups.items()):
            summary = _outcome_summary(grouped_rows)
            segments.append(
                {
                    "Segment": field,
                    "Wert": value,
                    "Signale": len(grouped_rows),
                    "Ausgewertet": summary["evaluated"],
                    "Trefferquote %": summary["hit_rate_pct"],
                    "Durchschnitt R": summary["average_r"],
                    "Profitfaktor R": summary["profit_factor_r"],
                }
            )
    overall = _outcome_summary(rows)
    tr_tradeable_rows = [row for row in rows if row["TR-handelbares Listing"] == "Ja"]
    tr_executable_rows = [row for row in rows if row["TR-ausführbarer Plan"] == "Ja"]
    paper_only_rows = [row for row in rows if row["TR-ausführbarer Plan"] != "Ja"]
    released_rows = [row for row in rows if row["Nutzerportfolio freigegeben"] == "Ja"]
    shadow_rows = [row for row in rows if row["Nutzerportfolio freigegeben"] == "Nein"]
    return {
        "signals": len(rows),
        "paper_entries": sum(row["Paper-Einstieg"] is not None for row in rows),
        "active": statuses.get("still_active", 0),
        "missed": statuses.get("entry_missed", 0),
        "invalidated_before_entry": statuses.get("invalidated_before_entry", 0),
        "expired_without_entry": statuses.get("expired_without_entry", 0),
        "ambiguous": statuses.get("ambiguous_sequence", 0),
        "not_evaluable": statuses.get("not_evaluable", 0),
        **overall,
        "statuses": dict(statuses),
        "archive_rows": rows,
        "segments": segments,
        "scanner_quality_total": {"signals": len(rows), **overall},
        "portfolio_released": {
            "signals": len(released_rows),
            **_outcome_summary(released_rows),
        },
        "shadow_strategy_signals": {
            "signals": len(shadow_rows),
            **_outcome_summary(shadow_rows),
        },
        "tr_tradeable_listings": {
            "signals": len(tr_tradeable_rows),
            **_outcome_summary(tr_tradeable_rows),
        },
        "tr_executable_trades": {
            "signals": len(tr_executable_rows),
            **_outcome_summary(tr_executable_rows),
        },
        "paper_only": {
            "signals": len(paper_only_rows),
            **_outcome_summary(paper_only_rows),
        },
        "counterfactual_controls": _counterfactual_summary(signals),
    }


def swing_learning_readiness(
    signals: list[dict],
    *,
    minimum_evaluated: int = 100,
    minimum_observation_weeks: int = 12,
    minimum_per_segment: int = 20,
) -> dict:
    rows = swing_forward_archive_rows(signals)
    evaluated = [row for row in rows if _number(row.get("Ergebnis R")) is not None]
    signal_days = []
    for row in rows:
        try:
            signal_days.append(datetime.fromisoformat(str(row.get("Signalzeit")).replace("Z", "+00:00")))
        except (TypeError, ValueError):
            continue
    observation_days = 0
    if len(signal_days) >= 2:
        earliest = min(value.replace(tzinfo=None) for value in signal_days)
        latest = max(value.replace(tzinfo=None) for value in signal_days)
        observation_days = max((latest - earliest).days, 0)
    segment_counts: dict[str, dict[str, int]] = {}
    for field in ("Asset-Typ", "Marktphase", "Volatilitätsregime", "Strategieversion"):
        counts: dict[str, int] = defaultdict(int)
        for row in evaluated:
            counts[str(row.get(field) or "Unbekannt")] += 1
        segment_counts[field] = dict(counts)
    thin_segments = {
        field: {key: value for key, value in counts.items() if value < minimum_per_segment}
        for field, counts in segment_counts.items()
        if counts
    }
    ready = (
        len(evaluated) >= max(int(minimum_evaluated), 1)
        and observation_days >= max(int(minimum_observation_weeks), 1) * 7
        and not thin_segments
    )
    return {
        "status": "manual_review_possible" if ready else "collecting_evidence",
        "evaluated": len(evaluated),
        "minimum_evaluated": max(int(minimum_evaluated), 1),
        "observation_days": observation_days,
        "minimum_observation_weeks": max(int(minimum_observation_weeks), 1),
        "minimum_per_segment": max(int(minimum_per_segment), 1),
        "segment_counts": segment_counts,
        "thin_segments": thin_segments,
        "manual_review_possible": ready,
        "automatic_rule_change": False,
        "automatic_weight_change": False,
        "historical_walk_forward_counts_as_real_forward": False,
    }


def swing_forward_asset_type_comparison(
    signals: list[dict],
    *,
    minimum_evaluated_per_class: int = 20,
    strategy_versions: set[str] | None = None,
) -> dict:
    rows = swing_forward_archive_rows(signals)
    if strategy_versions:
        rows = [row for row in rows if str(row.get("Strategieversion") or "") in strategy_versions]
    comparison_rows: list[dict] = []
    for asset_type in ("Aktie", "ETF"):
        asset_rows = [row for row in rows if str(row.get("Asset-Typ") or "") == asset_type]
        summary = _outcome_summary(asset_rows)
        ready = summary["evaluated"] >= minimum_evaluated_per_class
        comparison_rows.append(
            {
                "asset_type": asset_type,
                "signals": len(asset_rows),
                "evaluated": summary["evaluated"],
                "minimum_evaluated": minimum_evaluated_per_class,
                "ready": ready,
                "hit_rate_pct": summary["hit_rate_pct"] if ready else None,
                "average_r": summary["average_r"] if ready else None,
                "profit_factor_r": summary["profit_factor_r"] if ready else None,
                "max_drawdown_r": summary["max_drawdown_r"] if ready else None,
            }
        )
    ready = all(row["ready"] for row in comparison_rows)
    return {
        "status": "ready_for_descriptive_comparison" if ready else "collecting_forward_results",
        "minimum_evaluated_per_class": minimum_evaluated_per_class,
        "strategy_versions": sorted(strategy_versions or []),
        "rows": comparison_rows,
        "comparison_ready": ready,
        "causal_claim": False,
        "automatic_weight_change": False,
        "quota_or_asset_class_target": False,
        "message": (
            "ETF und Aktien können deskriptiv anhand echter Ergebnisse verglichen werden; eine Kausalwirkung ist damit nicht bewiesen."
            if ready
            else "ETF-/Aktien-Ergebnisvergleich noch nicht belastbar; echte Forward-Ergebnisse werden weiter gesammelt."
        ),
    }
