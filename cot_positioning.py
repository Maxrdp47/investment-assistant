from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import ssl
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


COT_SCHEMA_VERSION = 2
COT_FEATURE_VERSION = "cot-shadow-features-2026.08.18-v1"
COT_SHADOW_POLICY_VERSION = "cot-shadow-only-2026.08.18-v1"
COT_FORWARD_CONTEXT_VERSION = "cot-forward-signal-sidecar-2026.08.23-v1"
CFTC_API_ROOT = "https://publicreporting.cftc.gov/resource"
CFTC_DATASETS = {
    "tff_futures_only": "gpe5-46if",
    "disaggregated_futures_only": "72hh-3qpy",
}
DEFAULT_COT_DB_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_COT_DB_PATH",
        Path(__file__).resolve().parent / "runtime" / "cot_shadow.sqlite3",
    )
)
DEFAULT_COT_MAPPING_PATH = Path(__file__).resolve().parent / "config" / "cot_market_mapping.json"

CATEGORY_FIELDS = {
    "tff_futures_only": {
        "dealer_intermediary": (
            ("dealer_positions_long_all",),
            ("dealer_positions_short_all",),
        ),
        "asset_manager_institutional": (
            ("asset_mgr_positions_long", "asset_mgr_positions_long_all"),
            ("asset_mgr_positions_short", "asset_mgr_positions_short_all"),
        ),
        "leveraged_money": (
            ("lev_money_positions_long", "lev_money_positions_long_all"),
            ("lev_money_positions_short", "lev_money_positions_short_all"),
        ),
        "other_reportables": (
            ("other_rept_positions_long", "other_rept_positions_long_all"),
            ("other_rept_positions_short", "other_rept_positions_short_all"),
        ),
        "non_reportables": (
            ("nonrept_positions_long_all", "nonrept_positions_long"),
            ("nonrept_positions_short_all", "nonrept_positions_short"),
        ),
    },
    "disaggregated_futures_only": {
        "producer_merchant_processor_user": (
            ("prod_merc_positions_long", "prod_merc_positions_long_all"),
            ("prod_merc_positions_short", "prod_merc_positions_short_all"),
        ),
        "swap_dealer": (
            ("swap_positions_long_all", "swap_positions_long"),
            ("swap__positions_short_all", "swap_positions_short_all"),
        ),
        "managed_money": (
            ("m_money_positions_long_all", "m_money_positions_long"),
            ("m_money_positions_short_all", "m_money_positions_short"),
        ),
        "other_reportables": (
            ("other_rept_positions_long", "other_rept_positions_long_all"),
            ("other_rept_positions_short", "other_rept_positions_short_all"),
        ),
        "non_reportables": (
            ("nonrept_positions_long_all", "nonrept_positions_long"),
            ("nonrept_positions_short_all", "nonrept_positions_short"),
        ),
    },
}

CATEGORY_NOTES = {
    "dealer_intermediary": "CFTC-Klasse Dealer/Intermediary; keine pauschale Smart-Money-Wertung.",
    "asset_manager_institutional": "CFTC-Klasse Asset Manager/Institutional; keine pauschale Smart-Money-Wertung.",
    "leveraged_money": "CFTC-Klasse Leveraged Money; keine pauschale Smart-Money-Wertung.",
    "producer_merchant_processor_user": "CFTC-Klasse Producer/Merchant/Processor/User; keine pauschale Smart-Money-Wertung.",
    "swap_dealer": "CFTC-Klasse Swap Dealer; keine pauschale Smart-Money-Wertung.",
    "managed_money": "CFTC-Klasse Managed Money; keine pauschale Smart-Money-Wertung.",
    "other_reportables": "CFTC-Klasse Other Reportables.",
    "non_reportables": "CFTC-Klasse Non-Reportables; ausdrücklich nicht mit Retail gleichgesetzt.",
}


def _clean(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (datetime, date, Path)):
        return str(value.isoformat() if hasattr(value, "isoformat") else value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return _clean(item())
    return value


def _canonical_json(payload: object) -> str:
    return json.dumps(
        _clean(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc(value: datetime | str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Zeitpunkte müssen eine Zeitzone besitzen.")
    return parsed.astimezone(timezone.utc)


def _day(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _first_number(row: Mapping[str, object], fields: Sequence[str]) -> float | None:
    for field in fields:
        value = _number(row.get(field))
        if value is not None:
            return value
    return None


def fetch_cftc_rows(
    report_type: str,
    *,
    start: date | str,
    end: date | str,
    limit: int = 50_000,
    timeout_seconds: int = 30,
) -> list[dict]:
    """Read official CFTC Public Reporting data without modifying local state."""
    dataset = CFTC_DATASETS.get(report_type)
    if dataset is None:
        raise ValueError(f"Nicht unterstützter CFTC-Reporttyp: {report_type}")
    start_day, end_day = _day(start), _day(end)
    if end_day < start_day:
        raise ValueError("Das CFTC-Enddatum liegt vor dem Startdatum.")
    safe_limit = max(1, min(int(limit), 100_000))
    where = (
        f"report_date_as_yyyy_mm_dd between '{start_day.isoformat()}T00:00:00.000' "
        f"and '{end_day.isoformat()}T23:59:59.999'"
    )
    tls_context = ssl.create_default_context(cafile=certifi.where())
    page_size = min(1_000, safe_limit)
    rows: list[dict] = []
    while len(rows) < safe_limit:
        query = urlencode(
            {
                "$where": where,
                "$order": "report_date_as_yyyy_mm_dd asc,id asc",
                "$limit": min(page_size, safe_limit - len(rows)),
                "$offset": len(rows),
            }
        )
        url = f"{CFTC_API_ROOT}/{dataset}.json?{query}"
        request = Request(url, headers={"User-Agent": "investment-assistent-cot-shadow/1"})
        with urlopen(  # nosec B310 - fixed official host with certificate verification
            request, timeout=timeout_seconds, context=tls_context
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("Die offizielle CFTC-Antwort besitzt nicht das erwartete Listenformat.")
        rows.extend(dict(row) for row in payload)
        if len(payload) < page_size:
            break
    return rows


def normalize_cftc_row(
    row: Mapping[str, object],
    *,
    report_type: str,
    retrieved_at: datetime | str,
    acquisition_mode: str,
    published_at: datetime | str | None = None,
) -> dict:
    """Normalize one CFTC row while failing closed on unverified historical availability."""
    if report_type not in CATEGORY_FIELDS:
        raise ValueError(f"Nicht unterstützter CFTC-Reporttyp: {report_type}")
    if acquisition_mode not in {"forward", "historical_backfill"}:
        raise ValueError("acquisition_mode muss forward oder historical_backfill sein.")
    retrieved = _utc(retrieved_at)
    raw_report_date = row.get("report_date_as_yyyy_mm_dd") or row.get("report_date_as_mm_dd_yyyy")
    if not raw_report_date:
        raise ValueError("CFTC-Zeile ohne Berichtsstichtag.")
    report_day = _day(str(raw_report_date))
    market_code = str(row.get("cftc_contract_market_code") or "").strip()
    market_name = str(
        row.get("contract_market_name") or row.get("market_and_exchange_names") or ""
    ).strip()
    if not market_code or not market_name:
        raise ValueError("CFTC-Zeile ohne stabilen Marktcode oder Marktnamen.")

    available: datetime | None
    availability_basis: str
    if published_at is not None:
        available = _utc(published_at)
        if available.date() < report_day:
            raise ValueError("Veröffentlichungszeitpunkt liegt vor dem Berichtsstichtag.")
        availability_basis = "verified_publication_timestamp"
    elif acquisition_mode == "forward":
        available = retrieved
        availability_basis = "first_observed_publicly_available"
    else:
        available = None
        availability_basis = "historical_release_timestamp_unverified"

    categories: dict[str, dict] = {}
    for name, (long_fields, short_fields) in CATEGORY_FIELDS[report_type].items():
        long_value = _first_number(row, long_fields)
        short_value = _first_number(row, short_fields)
        if long_value is None or short_value is None:
            continue
        categories[name] = {
            "long": long_value,
            "short": short_value,
            "net": long_value - short_value,
            "classification_note": CATEGORY_NOTES[name],
        }
    if not categories:
        raise ValueError("CFTC-Zeile besitzt keine unterstützten Teilnehmerpositionen.")

    core = {
        "schema_version": COT_SCHEMA_VERSION,
        "report_type": report_type,
        "dataset_id": CFTC_DATASETS[report_type],
        "report_date": report_day.isoformat(),
        "available_at": available.isoformat() if available else None,
        "published_at": (
            available.isoformat()
            if available is not None and availability_basis == "verified_publication_timestamp"
            else None
        ),
        "first_seen_at": retrieved.isoformat(),
        "availability_basis": availability_basis,
        "pit_eligible": available is not None,
        "retrieved_at": retrieved.isoformat(),
        "market_code": market_code,
        "market_name": market_name,
        "commodity_code": str(row.get("cftc_commodity_code") or "").strip(),
        "commodity_name": str(row.get("commodity_name") or "").strip(),
        "open_interest": _number(row.get("open_interest_all")),
        "categories": categories,
        "classification_guardrails": {
            "non_reportables_are_retail": False,
            "commercials_are_smart_money": False,
            "category_names_preserved": True,
        },
        "source_url": f"{CFTC_API_ROOT}/{CFTC_DATASETS[report_type]}.json",
    }
    content_for_identity = {
        key: value
        for key, value in core.items()
        if key
        not in {
            "retrieved_at",
            "available_at",
            "published_at",
            "first_seen_at",
            "availability_basis",
            "pit_eligible",
        }
    }
    core["report_key"] = _fingerprint(
        {"report_type": report_type, "market_code": market_code, "report_date": report_day.isoformat()}
    )
    core["content_fingerprint"] = _fingerprint(content_for_identity)
    core["report_id"] = _fingerprint(
        {"report_key": core["report_key"], "content_fingerprint": core["content_fingerprint"]}
    )
    return core


def load_cot_market_mapping(path: Path = DEFAULT_COT_MAPPING_PATH) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("shadow_only") is not True:
        raise ValueError("COT-Mapping muss ausdrücklich shadow_only sein.")
    return payload


def map_cot_market(report: Mapping[str, object], mapping: Mapping[str, object]) -> dict:
    """Map only explicit rules; ambiguity fails closed instead of guessing."""
    searchable = " ".join(
        str(report.get(field) or "") for field in ("market_name", "commodity_name", "market_code")
    ).upper()
    matches = []
    for rule in mapping.get("rules") or []:
        report_types = {str(value) for value in rule.get("report_types") or []}
        tokens = [str(value).upper() for value in rule.get("match_any") or [] if str(value).strip()]
        if str(report.get("report_type") or "") not in report_types or not tokens:
            continue
        if any(token in searchable for token in tokens):
            matches.append(dict(rule))
    groups = {str(item.get("asset_group") or "") for item in matches}
    if len(matches) == 1 or (matches and len(groups) == 1):
        selected = matches[0]
        return {
            "status": "mapped",
            "asset_group": selected["asset_group"],
            "scope": selected.get("scope", "broad_market_context"),
            "rule_id": selected["rule_id"],
            "mapping_version": mapping.get("version"),
            "issuer_specific": False,
        }
    return {
        "status": "ambiguous" if matches else "unmapped",
        "asset_group": None,
        "scope": None,
        "rule_id": None,
        "mapping_version": mapping.get("version"),
        "issuer_specific": False,
    }


def route_swing_asset_to_cot_groups(
    asset: Mapping[str, object], mapping: Mapping[str, object]
) -> dict:
    ticker = str(asset.get("ticker") or "").upper()
    asset_type = str(asset.get("asset_type") or "")
    region = str(asset.get("region") or "")
    matches = []
    for route in mapping.get("asset_context_routes") or []:
        tickers = {str(value).upper() for value in route.get("tickers") or []}
        asset_types = {str(value) for value in route.get("asset_types") or []}
        regions = {str(value) for value in route.get("regions") or []}
        if tickers and ticker not in tickers:
            continue
        if asset_types and asset_type not in asset_types:
            continue
        if regions and region not in regions:
            continue
        matches.append(dict(route))
    groups = sorted(
        {str(group) for route in matches for group in route.get("asset_groups") or [] if str(group)}
    )
    if len(matches) == 1 and groups:
        return {
            "status": "mapped",
            "asset_groups": groups,
            "scope": matches[0].get("scope"),
            "route_id": matches[0].get("route_id"),
            "mapping_version": mapping.get("version"),
            "issuer_specific": False,
        }
    return {
        "status": "ambiguous" if matches else "unmapped",
        "asset_groups": [],
        "scope": None,
        "route_id": None,
        "mapping_version": mapping.get("version"),
        "issuer_specific": False,
    }


def build_asset_cot_shadow_context(
    asset: Mapping[str, object],
    reports: Sequence[Mapping[str, object]],
    *,
    decision_at: datetime | str,
    mapping: Mapping[str, object],
    technical_direction: str = "long",
) -> dict:
    """Select a broad context causally; never claim issuer-specific positioning."""
    asset_mapping = route_swing_asset_to_cot_groups(asset, mapping)
    if asset_mapping["status"] != "mapped":
        features = derive_cot_features([], decision_at=decision_at)
        return {
            "mapping": asset_mapping,
            "features": features,
            "assessment": cot_shadow_assessment(features, technical_direction=technical_direction),
        }
    allowed_groups = set(asset_mapping["asset_groups"])
    by_market: dict[tuple[str, str], list[dict]] = {}
    market_mappings: dict[tuple[str, str], dict] = {}
    for report in reports:
        market_mapping = map_cot_market(report, mapping)
        if market_mapping.get("status") != "mapped" or market_mapping.get("asset_group") not in allowed_groups:
            continue
        key = (str(report.get("market_code") or ""), str(report.get("report_type") or ""))
        by_market.setdefault(key, []).append(dict(report))
        market_mappings[key] = market_mapping
    candidates = []
    for key, market_reports in by_market.items():
        features = derive_cot_features(market_reports, decision_at=decision_at)
        if features.get("status") == "available":
            candidates.append((float(features.get("open_interest") or 0), key, features))
    if not candidates:
        features = derive_cot_features([], decision_at=decision_at)
        return {
            "mapping": asset_mapping,
            "features": features,
            "assessment": cot_shadow_assessment(features, technical_direction=technical_direction),
        }
    _, selected_key, features = max(candidates, key=lambda item: (item[0], item[1]))
    selected_mapping = dict(asset_mapping)
    selected_mapping.update(
        {
            "cot_market": market_mappings[selected_key],
            "selected_market_code": selected_key[0],
            "selected_report_type": selected_key[1],
            "selection_basis": "highest_current_open_interest_within_explicit_asset_group",
            "issuer_specific": False,
        }
    )
    return {
        "mapping": selected_mapping,
        "features": features,
        "assessment": cot_shadow_assessment(features, technical_direction=technical_direction),
    }


def _percentile(values: Sequence[float], current: float) -> float | None:
    if not values:
        return None
    return 100.0 * sum(value <= current for value in values) / len(values)


def _z_score(values: Sequence[float], current: float) -> float | None:
    if len(values) < 2:
        return None
    deviation = pstdev(values)
    return 0.0 if deviation == 0 else (current - fmean(values)) / deviation


def derive_cot_features(
    reports: Sequence[Mapping[str, object]],
    *,
    decision_at: datetime | str,
    lookback_reports: int = 156,
) -> dict:
    """Create causal features using only reports already available at the decision time."""
    decision = _utc(decision_at)
    eligible = [
        dict(item)
        for item in reports
        if item.get("pit_eligible") is True
        and item.get("available_at")
        and _utc(str(item["available_at"])) <= decision
    ]
    if not eligible:
        return {
            "feature_version": COT_FEATURE_VERSION,
            "status": "unavailable_point_in_time",
            "decision_at": decision.isoformat(),
            "shadow_only": True,
        }
    market_codes = {str(item.get("market_code") or "") for item in eligible}
    report_types = {str(item.get("report_type") or "") for item in eligible}
    if len(market_codes) != 1 or len(report_types) != 1:
        raise ValueError("COT-Merkmale dürfen Märkte oder Reporttypen nicht vermischen.")

    # Corrections are new revisions. At each report date use only the last revision available then.
    by_key: dict[str, dict] = {}
    for item in sorted(eligible, key=lambda value: str(value.get("available_at") or "")):
        by_key[str(item.get("report_key") or item.get("report_id"))] = item
    ordered = sorted(by_key.values(), key=lambda value: (str(value["report_date"]), str(value["available_at"])))
    history = ordered[-max(5, int(lookback_reports)) :]
    latest = history[-1]
    features: dict[str, dict] = {}
    for category, current_values in dict(latest.get("categories") or {}).items():
        series = [
            float(item["categories"][category]["net"])
            for item in history
            if category in dict(item.get("categories") or {})
        ]
        if not series:
            continue
        current = float(current_values["net"])
        features[category] = {
            "long": float(current_values["long"]),
            "short": float(current_values["short"]),
            "net_position": current,
            "net_change_1w": current - series[-2] if len(series) >= 2 else None,
            "net_change_4w": current - series[-5] if len(series) >= 5 else None,
            "historical_percentile": _percentile(series, current),
            "historical_z_score": _z_score(series, current),
            "history_reports": len(series),
            "classification_note": CATEGORY_NOTES.get(category, "Originale CFTC-Klasse."),
        }
    open_interest_series = [
        float(item["open_interest"]) for item in history if item.get("open_interest") is not None
    ]
    current_oi = float(latest["open_interest"]) if latest.get("open_interest") is not None else None
    divergences = []
    positive = [name for name, values in features.items() if (values["historical_z_score"] or 0) >= 1.0]
    negative = [name for name, values in features.items() if (values["historical_z_score"] or 0) <= -1.0]
    for long_class in positive:
        for short_class in negative:
            divergences.append({"positive_class": long_class, "negative_class": short_class})
    return {
        "feature_version": COT_FEATURE_VERSION,
        "status": "available",
        "decision_at": decision.isoformat(),
        "report_id": latest["report_id"],
        "report_date": latest["report_date"],
        "available_at": latest["available_at"],
        "market_code": latest["market_code"],
        "market_name": latest["market_name"],
        "report_type": latest["report_type"],
        "open_interest": current_oi,
        "open_interest_change_1w": (
            current_oi - open_interest_series[-2] if current_oi is not None and len(open_interest_series) >= 2 else None
        ),
        "open_interest_change_4w": (
            current_oi - open_interest_series[-5] if current_oi is not None and len(open_interest_series) >= 5 else None
        ),
        "categories": features,
        "divergences": divergences,
        "shadow_only": True,
        "production_effect": "none",
    }


def cot_shadow_assessment(features: Mapping[str, object], *, technical_direction: str = "long") -> dict:
    """Create a research label only; it is never a score or trade gate."""
    if str(features.get("status")) != "available":
        label, reason = "unavailable", "Kein Point-in-Time-berechtigter COT-Report vorhanden."
    else:
        categories = dict(features.get("categories") or {})
        z_scores = [
            float(values["historical_z_score"])
            for values in categories.values()
            if values.get("historical_z_score") is not None
        ]
        four_week = [
            float(values["net_change_4w"])
            for values in categories.values()
            if values.get("net_change_4w") is not None
        ]
        direction = 1.0 if technical_direction.lower() == "long" else -1.0
        extreme_against = any(direction * value <= -2.0 for value in z_scores)
        mean_z = fmean(z_scores) * direction if z_scores else 0.0
        mean_change = fmean(four_week) * direction if four_week else 0.0
        if extreme_against:
            label, reason = "extreme_contrarian", "Mindestens eine originale CFTC-Klasse ist historisch extrem gegen die technische Richtung positioniert."
        elif z_scores and mean_z >= 0.5 and mean_change > 0:
            label, reason = "confirms", "Die klassenübergreifende Positionierung bestätigt die technische Richtung als Forschungshypothese."
        elif z_scores and mean_z <= -0.5 and mean_change < 0:
            label, reason = "contradicts", "Die klassenübergreifende Positionierung widerspricht der technischen Richtung als Forschungshypothese."
        else:
            label, reason = "neutral", "Die Positionierung liefert kein eindeutiges klassenübergreifendes Shadow-Signal."
    return {
        "policy_version": COT_SHADOW_POLICY_VERSION,
        "label": label,
        "reason": reason,
        "shadow_only": True,
        "changes_trade_decision": False,
        "changes_score_or_weight": False,
        "automatic_activation": False,
    }


def _comparison_metrics(cases: Sequence[Mapping[str, object]]) -> dict:
    rows = [dict(case) for case in cases if _number(case.get("result_r")) is not None]
    results = [float(case["result_r"]) for case in rows]
    positives = sum(value for value in results if value > 0)
    negatives = abs(sum(value for value in results if value < 0))
    equity = drawdown = peak = 0.0
    for value in results:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    mfe = [_number(case.get("mfe_r")) for case in rows]
    mae = [_number(case.get("mae_r")) for case in rows]
    return {
        "cases": len(rows),
        "hit_rate": (sum(value > 0 for value in results) / len(results)) if results else None,
        "average_r": fmean(results) if results else None,
        "profit_factor": positives / negatives if negatives > 0 else None,
        "maximum_drawdown_r": drawdown if results else None,
        "average_mfe_r": fmean([value for value in mfe if value is not None]) if any(value is not None for value in mfe) else None,
        "average_mae_r": fmean([value for value in mae if value is not None]) if any(value is not None for value in mae) else None,
    }


def compare_strategy_with_cot_shadow(cases: Sequence[Mapping[str, object]]) -> dict:
    """Compare the champion with a declared counterfactual that excludes contradictions."""
    baseline = [dict(case) for case in cases]
    overlay = [case for case in baseline if str(case.get("cot_shadow_label")) != "contradicts"]
    return {
        "comparison_version": "cot-shadow-comparison-2026.08.18-v1",
        "counterfactual_policy": "exclude_cot_contradicts_keep_all_other_labels",
        "existing_strategy": _comparison_metrics(baseline),
        "strategy_plus_positioning_shadow": _comparison_metrics(overlay),
        "excluded_as_contradiction": len(baseline) - len(overlay),
        "shadow_only": True,
        "production_effect": "none",
        "automatic_rule_change": False,
    }


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_cot_shadow_store(path: Path = DEFAULT_COT_DB_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cot_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cot_reports (
                report_id TEXT PRIMARY KEY,
                report_key TEXT NOT NULL,
                report_date TEXT NOT NULL,
                available_at TEXT,
                retrieved_at TEXT NOT NULL,
                market_code TEXT NOT NULL,
                report_type TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cot_report_availability (
                evidence_id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                available_at TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                availability_basis TEXT NOT NULL,
                source_url TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES cot_reports(report_id)
            );
            CREATE TABLE IF NOT EXISTS cot_shadow_links (
                link_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                signal_at TEXT NOT NULL,
                report_id TEXT,
                created_at TEXT NOT NULL,
                mapping_json TEXT NOT NULL,
                features_json TEXT NOT NULL,
                assessment_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cot_forward_contexts (
                context_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL UNIQUE,
                signal_at TEXT NOT NULL,
                asset_id TEXT,
                listing_id TEXT,
                issuer_id TEXT,
                report_id TEXT,
                status TEXT NOT NULL CHECK (
                    status IN ('available', 'cot_context_unavailable')
                ),
                created_at TEXT NOT NULL,
                signal_snapshot_fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                context_fingerprint TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cot_reports_asof
            ON cot_reports(market_code, report_type, available_at, report_date);
            CREATE INDEX IF NOT EXISTS idx_cot_report_availability_asof
            ON cot_report_availability(report_id, available_at, first_seen_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cot_shadow_signal_policy
            ON cot_shadow_links(signal_id, report_id, link_id);
            CREATE TRIGGER IF NOT EXISTS cot_reports_no_update BEFORE UPDATE ON cot_reports BEGIN
                SELECT RAISE(ABORT, 'cot_reports is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_reports_no_delete BEFORE DELETE ON cot_reports BEGIN
                SELECT RAISE(ABORT, 'cot_reports is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_report_availability_no_update BEFORE UPDATE ON cot_report_availability BEGIN
                SELECT RAISE(ABORT, 'cot_report_availability is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_report_availability_no_delete BEFORE DELETE ON cot_report_availability BEGIN
                SELECT RAISE(ABORT, 'cot_report_availability is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_shadow_links_no_update BEFORE UPDATE ON cot_shadow_links BEGIN
                SELECT RAISE(ABORT, 'cot_shadow_links is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_shadow_links_no_delete BEFORE DELETE ON cot_shadow_links BEGIN
                SELECT RAISE(ABORT, 'cot_shadow_links is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_forward_contexts_no_update BEFORE UPDATE ON cot_forward_contexts BEGIN
                SELECT RAISE(ABORT, 'cot_forward_contexts is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS cot_forward_contexts_no_delete BEFORE DELETE ON cot_forward_contexts BEGIN
                SELECT RAISE(ABORT, 'cot_forward_contexts is append-only');
            END;
            """
        )
        row = connection.execute("SELECT value FROM cot_meta WHERE key = 'schema_version'").fetchone()
        if row is None:
            connection.execute("INSERT INTO cot_meta (key, value) VALUES ('schema_version', ?)", (str(COT_SCHEMA_VERSION),))
        elif int(row["value"]) == 1 and COT_SCHEMA_VERSION == 2:
            connection.execute(
                "UPDATE cot_meta SET value = ? WHERE key = 'schema_version'",
                (str(COT_SCHEMA_VERSION),),
            )
        elif int(row["value"]) != COT_SCHEMA_VERSION:
            raise RuntimeError(f"Nicht unterstütztes COT-Schema {row['value']}.")


def _append_cot_availability_evidence(
    connection: sqlite3.Connection,
    report: Mapping[str, object],
) -> bool:
    available_at = report.get("available_at")
    if not available_at or report.get("pit_eligible") is not True:
        return False
    report_id = str(report["report_id"])
    if connection.execute(
        "SELECT 1 FROM cot_report_availability WHERE report_id = ? LIMIT 1",
        (report_id,),
    ).fetchone() is not None:
        return False
    first_seen_at = str(report.get("first_seen_at") or report.get("retrieved_at") or available_at)
    evidence = {
        "report_id": report_id,
        "available_at": _utc(str(available_at)).isoformat(),
        "first_seen_at": _utc(first_seen_at).isoformat(),
        "availability_basis": str(report.get("availability_basis") or "unknown"),
        "source_url": str(report.get("source_url") or ""),
    }
    evidence_id = _fingerprint({"kind": "cot_report_availability", **evidence})
    cursor = connection.execute(
        """INSERT OR IGNORE INTO cot_report_availability
        (evidence_id, report_id, available_at, first_seen_at, availability_basis, source_url)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            evidence_id,
            evidence["report_id"],
            evidence["available_at"],
            evidence["first_seen_at"],
            evidence["availability_basis"],
            evidence["source_url"],
        ),
    )
    return cursor.rowcount == 1


def append_cot_report(report: Mapping[str, object], path: Path = DEFAULT_COT_DB_PATH) -> bool:
    initialize_cot_shadow_store(path)
    payload = dict(report)
    with _connect(Path(path)) as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO cot_reports
            (report_id, report_key, report_date, available_at, retrieved_at, market_code, report_type, content_fingerprint, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["report_id"], payload["report_key"], payload["report_date"], payload.get("available_at"),
                payload["retrieved_at"], payload["market_code"], payload["report_type"], payload["content_fingerprint"],
                _canonical_json(payload),
            ),
        )
        _append_cot_availability_evidence(connection, payload)
        return cursor.rowcount == 1


def ingest_cftc_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    report_type: str,
    retrieved_at: datetime | str,
    acquisition_mode: str = "forward",
    publication_times: Mapping[str, datetime | str] | None = None,
    path: Path = DEFAULT_COT_DB_PATH,
) -> dict:
    """Normalize and persist a batch; invalid rows are reported and never partly invented."""
    initialize_cot_shadow_store(path)
    stored = duplicates = 0
    errors: list[dict] = []
    with _connect(Path(path)) as connection:
        for position, row in enumerate(rows):
            report_date = str(
                row.get("report_date_as_yyyy_mm_dd") or row.get("report_date_as_mm_dd_yyyy") or ""
            )[:10]
            published_at = (publication_times or {}).get(report_date)
            try:
                normalized = normalize_cftc_row(
                    row,
                    report_type=report_type,
                    retrieved_at=retrieved_at,
                    acquisition_mode=acquisition_mode,
                    published_at=published_at,
                )
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO cot_reports
                    (report_id, report_key, report_date, available_at, retrieved_at, market_code, report_type, content_fingerprint, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        normalized["report_id"], normalized["report_key"], normalized["report_date"],
                        normalized.get("available_at"), normalized["retrieved_at"], normalized["market_code"],
                        normalized["report_type"], normalized["content_fingerprint"], _canonical_json(normalized),
                    ),
                )
                if cursor.rowcount == 1:
                    stored += 1
                else:
                    duplicates += 1
                _append_cot_availability_evidence(connection, normalized)
            except (KeyError, TypeError, ValueError) as exc:
                errors.append({"row": position, "report_date": report_date or None, "error": str(exc)})
    return {
        "report_type": report_type,
        "acquisition_mode": acquisition_mode,
        "received": stored + duplicates + len(errors),
        "stored": stored,
        "duplicates": duplicates,
        "errors": errors,
        "shadow_only": True,
        "production_effect": "none",
    }


def load_cot_reports_as_of(
    market_code: str,
    report_type: str,
    decision_at: datetime | str,
    path: Path = DEFAULT_COT_DB_PATH,
) -> list[dict]:
    initialize_cot_shadow_store(path)
    cutoff = _utc(decision_at).isoformat()
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            """SELECT r.payload_json,
                COALESCE(
                    r.available_at,
                    (SELECT MIN(a.available_at) FROM cot_report_availability a WHERE a.report_id = r.report_id)
                ) AS effective_available_at,
                (SELECT a.first_seen_at FROM cot_report_availability a
                 WHERE a.report_id = r.report_id ORDER BY a.available_at, a.first_seen_at LIMIT 1)
                    AS evidence_first_seen_at,
                (SELECT a.availability_basis FROM cot_report_availability a
                 WHERE a.report_id = r.report_id ORDER BY a.available_at, a.first_seen_at LIMIT 1)
                    AS evidence_basis
            FROM cot_reports r
            WHERE r.market_code = ? AND r.report_type = ?
              AND COALESCE(
                    r.available_at,
                    (SELECT MIN(a.available_at) FROM cot_report_availability a WHERE a.report_id = r.report_id)
                  ) <= ?
            ORDER BY r.report_date, effective_available_at, r.retrieved_at""",
            (market_code, report_type, cutoff),
        ).fetchall()
    return [_cot_report_with_availability(row) for row in rows]


def _cot_report_with_availability(row: Mapping[str, object]) -> dict:
    payload = json.loads(str(row["payload_json"]))
    effective = row["effective_available_at"]
    if effective:
        payload["available_at"] = str(effective)
        payload["pit_eligible"] = True
        if row["evidence_first_seen_at"]:
            payload["first_seen_at"] = str(row["evidence_first_seen_at"])
        if row["evidence_basis"]:
            payload["availability_basis"] = str(row["evidence_basis"])
    return payload


def load_all_cot_reports_as_of(
    decision_at: datetime | str,
    path: Path = DEFAULT_COT_DB_PATH,
) -> list[dict]:
    """Load every report proven available by the cutoff, including later forward evidence."""
    initialize_cot_shadow_store(path)
    cutoff = _utc(decision_at).isoformat()
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            """SELECT r.payload_json,
                COALESCE(
                    r.available_at,
                    (SELECT MIN(a.available_at) FROM cot_report_availability a WHERE a.report_id = r.report_id)
                ) AS effective_available_at,
                (SELECT a.first_seen_at FROM cot_report_availability a
                 WHERE a.report_id = r.report_id ORDER BY a.available_at, a.first_seen_at LIMIT 1)
                    AS evidence_first_seen_at,
                (SELECT a.availability_basis FROM cot_report_availability a
                 WHERE a.report_id = r.report_id ORDER BY a.available_at, a.first_seen_at LIMIT 1)
                    AS evidence_basis
            FROM cot_reports r
            WHERE COALESCE(
                    r.available_at,
                    (SELECT MIN(a.available_at) FROM cot_report_availability a WHERE a.report_id = r.report_id)
                  ) <= ?
            ORDER BY r.report_date, effective_available_at, r.retrieved_at""",
            (cutoff,),
        ).fetchall()
    return [_cot_report_with_availability(row) for row in rows]


def append_cot_shadow_link(
    *,
    signal_id: str,
    signal_at: datetime | str,
    mapping: Mapping[str, object],
    features: Mapping[str, object],
    assessment: Mapping[str, object],
    created_at: datetime | str,
    path: Path = DEFAULT_COT_DB_PATH,
) -> str:
    initialize_cot_shadow_store(path)
    created = _utc(created_at).isoformat()
    signal_time = _utc(signal_at).isoformat()
    report_id = str(features.get("report_id") or "") or None
    identity = {
        "signal_id": str(signal_id), "report_id": report_id,
        "feature_version": features.get("feature_version"), "policy_version": assessment.get("policy_version"),
    }
    link_id = _fingerprint(identity)
    with _connect(Path(path)) as connection:
        connection.execute(
            """INSERT OR IGNORE INTO cot_shadow_links
            (link_id, signal_id, signal_at, report_id, created_at, mapping_json, features_json, assessment_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (link_id, str(signal_id), signal_time, report_id, created, _canonical_json(mapping), _canonical_json(features), _canonical_json(assessment)),
        )
    return link_id


def _cot_listing_identity(asset: Mapping[str, object]) -> str:
    return _fingerprint(
        {
            "ticker": str(asset.get("ticker") or "").upper(),
            "isin": asset.get("isin"),
            "exchange": asset.get("exchange"),
            "original_currency": asset.get("original_currency"),
        }
    )


def _read_forward_signals_for_cot(
    forward_path: Path,
    signal_ids: Sequence[str] | None,
) -> list[dict]:
    path = Path(forward_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Swing-Forward-Datenbank fehlt: {path}")
    requested = {str(value) for value in signal_ids} if signal_ids is not None else None
    uri = f"file:{path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT signal_id, signal_at, snapshot_json, snapshot_fingerprint "
            "FROM swing_signals ORDER BY signal_at, signal_id"
        ).fetchall()
    result = []
    for row in rows:
        signal_id = str(row["signal_id"])
        if requested is not None and signal_id not in requested:
            continue
        result.append(
            {
                "signal_id": signal_id,
                "signal_at": str(row["signal_at"]),
                "snapshot": json.loads(str(row["snapshot_json"])),
                "snapshot_fingerprint": str(row["snapshot_fingerprint"]),
            }
        )
    if requested is not None:
        missing = requested - {item["signal_id"] for item in result}
        if missing:
            raise ValueError(f"Unbekannte Forward-Signal-IDs: {', '.join(sorted(missing))}")
    return result


def _participant_forward_features(
    selected: Mapping[str, object],
    reports: Sequence[Mapping[str, object]],
) -> dict:
    selected_market = str(selected.get("market_code") or "")
    selected_type = str(selected.get("report_type") or "")
    selected_report = str(selected.get("report_id") or "")
    market_reports = [
        dict(item)
        for item in reports
        if str(item.get("market_code") or "") == selected_market
        and str(item.get("report_type") or "") == selected_type
    ]
    current = derive_cot_features(
        market_reports,
        decision_at=str(selected["decision_at"]),
        lookback_reports=52,
    )
    eligible = sorted(
        (
            item
            for item in market_reports
            if item.get("pit_eligible") is True
            and item.get("available_at")
            and _utc(str(item["available_at"])) <= _utc(str(selected["decision_at"]))
        ),
        key=lambda item: (str(item.get("report_date") or ""), str(item.get("available_at") or "")),
    )
    prior = None
    for index, report in enumerate(eligible):
        if str(report.get("report_id") or "") == selected_report and index > 0:
            prior = derive_cot_features(
                market_reports,
                decision_at=str(eligible[index - 1]["available_at"]),
                lookback_reports=52,
            )
            break
    output: dict[str, dict] = {}
    current_oi = _number(current.get("open_interest"))
    prior_categories = dict((prior or {}).get("categories") or {})
    for participant, values in dict(current.get("categories") or {}).items():
        current_z = _number(values.get("historical_z_score"))
        prior_z = _number(dict(prior_categories.get(participant) or {}).get("historical_z_score"))
        reversal: bool | None = None
        reversal_direction: str | None = None
        if prior_z is not None and current_z is not None:
            reversal = (prior_z >= 2.0 and current_z < 2.0) or (
                prior_z <= -2.0 and current_z > -2.0
            )
            if reversal:
                reversal_direction = (
                    "from_positive_extreme" if prior_z >= 2.0 else "from_negative_extreme"
                )
        output[str(participant)] = {
            "net_position": _number(values.get("net_position")),
            "open_interest": current_oi,
            "net_position_open_interest_ratio": (
                float(values["net_position"]) / current_oi
                if current_oi not in (None, 0) and values.get("net_position") is not None
                else None
            ),
            "net_change_1w": _number(values.get("net_change_1w")),
            "net_change_4w": _number(values.get("net_change_4w")),
            "percentile_52w": _number(values.get("historical_percentile")),
            "z_score_52w": current_z,
            "extreme_state": (
                "positive_extreme"
                if current_z is not None and current_z >= 2.0
                else "negative_extreme"
                if current_z is not None and current_z <= -2.0
                else "not_extreme"
                if current_z is not None
                else None
            ),
            "reversal_from_extreme": reversal,
            "reversal_direction": reversal_direction,
            "classification_note": values.get("classification_note"),
        }
    return {
        "classes": output,
        "participant_spreads_or_divergences": list(current.get("divergences") or []),
        "open_interest_change_1w": _number(current.get("open_interest_change_1w")),
        "open_interest_change_4w": _number(current.get("open_interest_change_4w")),
        "lookback_reports_maximum": 52,
    }


def build_cot_forward_signal_context(
    signal: Mapping[str, object],
    reports: Sequence[Mapping[str, object]],
    *,
    mapping: Mapping[str, object],
    created_at: datetime | str,
) -> dict:
    snapshot = dict(signal.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    signal_id = str(signal.get("signal_id") or "")
    signal_at = _utc(str(signal.get("signal_at") or snapshot.get("signal_at") or ""))
    if not signal_id:
        raise ValueError("COT-Forward-Sidecar benötigt eine Signal-ID.")
    context = build_asset_cot_shadow_context(
        asset,
        reports,
        decision_at=signal_at,
        mapping=mapping,
        technical_direction=str(dict(snapshot.get("strategy") or {}).get("direction") or "long"),
    )
    features = dict(context.get("features") or {})
    selected_report = next(
        (
            dict(item)
            for item in reports
            if str(item.get("report_id") or "") == str(features.get("report_id") or "")
        ),
        None,
    )
    available = features.get("status") == "available" and selected_report is not None
    listing_id = _cot_listing_identity(asset)
    explicit_publication = None
    if selected_report is not None:
        explicit_publication = selected_report.get("published_at")
        if not explicit_publication and selected_report.get("availability_basis") == "verified_publication_timestamp":
            explicit_publication = selected_report.get("available_at")
    payload = {
        "context_version": COT_FORWARD_CONTEXT_VERSION,
        "signal_id": signal_id,
        "signal_cutoff": signal_at.isoformat(),
        "sidecar_created_at": _utc(created_at).isoformat(),
        "asset_identity": {
            "asset_id": asset.get("asset_id"),
            "listing_id": listing_id,
            "issuer_id": None,
            "issuer_id_missing_reason": "Kein belastbarer Issuer-Identifier im Forward-Snapshot.",
            "ticker": asset.get("ticker"),
            "isin": asset.get("isin"),
            "exchange": asset.get("exchange"),
            "original_currency": asset.get("original_currency"),
            "asset_type": asset.get("asset_type"),
            "region": asset.get("region"),
        },
        "status": "available" if available else "cot_context_unavailable",
        "mapping": dict(context.get("mapping") or {}),
        "mapping_confidence": (
            {"level": "explicit_deterministic", "value": 1.0}
            if available
            else {"level": "unavailable", "value": None}
        ),
        "report": (
            {
                "report_id": selected_report.get("report_id"),
                "cftc_market": selected_report.get("market_name"),
                "cftc_market_code": selected_report.get("market_code"),
                "report_type": selected_report.get("report_type"),
                "report_date": selected_report.get("report_date"),
                "verified_published_at": explicit_publication,
                "verified_public_availability_at": selected_report.get("available_at"),
                "local_first_seen_at": selected_report.get("first_seen_at")
                or selected_report.get("retrieved_at"),
                "availability_basis": selected_report.get("availability_basis"),
                "source": selected_report.get("source_url"),
                "source_fingerprint": selected_report.get("content_fingerprint"),
            }
            if available
            else None
        ),
        "participant_context": (
            _participant_forward_features(features, reports) if available else None
        ),
        "assessment": dict(context.get("assessment") or {}),
        "missingness": {
            "cot_context_unavailable": not available,
            "no_later_report_substitution": True,
            "verified_publication_timestamp_missing": bool(
                available and explicit_publication is None
            ),
        },
        "guardrails": {
            "shadow_only": True,
            "research_only": True,
            "changes_trade_decision": False,
            "changes_score_or_weight": False,
            "changes_position_stop_or_target": False,
            "broad_feature_schema_changed": False,
            "broker_order_allowed": False,
            "production_effect": "none",
        },
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def append_cot_forward_context(
    context: Mapping[str, object],
    *,
    signal_snapshot_fingerprint: str,
    path: Path = DEFAULT_COT_DB_PATH,
) -> dict:
    initialize_cot_shadow_store(path)
    payload = dict(context)
    expected = payload.pop("fingerprint", None)
    fingerprint = _fingerprint(payload)
    if expected != fingerprint:
        raise ValueError("COT-Forward-Kontext besitzt einen ungültigen Fingerabdruck.")
    payload["fingerprint"] = fingerprint
    signal_id = str(payload.get("signal_id") or "")
    context_id = _fingerprint(
        {"kind": "cot_forward_signal_context", "version": COT_FORWARD_CONTEXT_VERSION, "signal_id": signal_id}
    )
    asset = dict(payload.get("asset_identity") or {})
    report = dict(payload.get("report") or {})
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT context_id, context_fingerprint, payload_json FROM cot_forward_contexts WHERE signal_id = ?",
            (signal_id,),
        ).fetchone()
        if existing is not None:
            stored_payload = json.loads(str(existing["payload_json"]))
            comparable_stored = {
                key: value
                for key, value in stored_payload.items()
                if key not in {"sidecar_created_at", "fingerprint"}
            }
            comparable_new = {
                key: value
                for key, value in payload.items()
                if key not in {"sidecar_created_at", "fingerprint"}
            }
            if _fingerprint(comparable_stored) != _fingerprint(comparable_new):
                raise ValueError("Das Signal besitzt bereits einen abweichenden COT-Sidecar.")
            return {"context_id": str(existing["context_id"]), "inserted": False}
        connection.execute(
            """INSERT INTO cot_forward_contexts
            (context_id, signal_id, signal_at, asset_id, listing_id, issuer_id, report_id,
             status, created_at, signal_snapshot_fingerprint, payload_json, context_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                context_id,
                signal_id,
                str(payload["signal_cutoff"]),
                asset.get("asset_id"),
                asset.get("listing_id"),
                asset.get("issuer_id"),
                report.get("report_id") or None,
                str(payload["status"]),
                str(payload["sidecar_created_at"]),
                str(signal_snapshot_fingerprint),
                _canonical_json(payload),
                fingerprint,
            ),
        )
    return {"context_id": context_id, "inserted": True}


def load_cot_forward_contexts(path: Path = DEFAULT_COT_DB_PATH) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_cot_shadow_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT context_id, signal_id, payload_json FROM cot_forward_contexts "
            "ORDER BY signal_at, context_id"
        ).fetchall()
    return [
        {
            "context_id": str(row["context_id"]),
            "signal_id": str(row["signal_id"]),
            "context": json.loads(str(row["payload_json"])),
        }
        for row in rows
    ]


def refresh_official_cot_forward(
    *,
    retrieved_at: datetime | str,
    path: Path = DEFAULT_COT_DB_PATH,
    days: int = 21,
    fetcher=fetch_cftc_rows,
) -> dict:
    retrieved = _utc(retrieved_at)
    end = retrieved.date()
    start = end - timedelta(days=max(7, int(days)))
    results = []
    errors = []
    for report_type in CFTC_DATASETS:
        try:
            rows = fetcher(report_type, start=start, end=end)
            results.append(
                ingest_cftc_rows(
                    rows,
                    report_type=report_type,
                    retrieved_at=retrieved,
                    acquisition_mode="forward",
                    path=path,
                )
            )
        except Exception as exc:
            errors.append({"report_type": report_type, "error": str(exc)})
    return {
        "status": "ok" if not errors else "research_attention",
        "source": "official_cftc_public_reporting",
        "retrieved_at": retrieved.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "results": results,
        "errors": errors,
        "production_effect": "none",
    }


def collect_forward_cot_contexts(
    *,
    signal_ids: Sequence[str] | None,
    forward_path: Path,
    collected_at: datetime | str,
    path: Path = DEFAULT_COT_DB_PATH,
    mapping_path: Path = DEFAULT_COT_MAPPING_PATH,
    refresh_official: bool = False,
    fetcher=fetch_cftc_rows,
) -> dict:
    """Attach causal COT sidecars without ever changing the immutable Forward store."""
    signals = _read_forward_signals_for_cot(forward_path, signal_ids)
    refresh = {
        "status": "not_requested",
        "source": "official_cftc_public_reporting",
        "errors": [],
        "production_effect": "none",
    }
    if refresh_official and signals:
        refresh = refresh_official_cot_forward(
            retrieved_at=collected_at,
            path=path,
            fetcher=fetcher,
        )
    initialize_cot_shadow_store(path)
    stored_contexts = load_cot_forward_contexts(path)
    existing = {item["signal_id"] for item in stored_contexts}
    pending = [signal for signal in signals if signal["signal_id"] not in existing]
    max_cutoff = max((_utc(signal["signal_at"]) for signal in pending), default=None)
    reports = load_all_cot_reports_as_of(max_cutoff, path) if max_cutoff else []
    mapping = load_cot_market_mapping(mapping_path)
    inserted = linked = unavailable = 0
    errors: list[dict] = []
    for signal in pending:
        try:
            context = build_cot_forward_signal_context(
                signal,
                reports,
                mapping=mapping,
                created_at=collected_at,
            )
            result = append_cot_forward_context(
                context,
                signal_snapshot_fingerprint=signal["snapshot_fingerprint"],
                path=path,
            )
            inserted += int(result["inserted"])
            linked += int(context["status"] == "available")
            unavailable += int(context["status"] == "cot_context_unavailable")
        except Exception as exc:
            errors.append({"signal_id": signal["signal_id"], "error": str(exc)})
    current_contexts = load_cot_forward_contexts(path)
    linked_total = sum(
        item["context"].get("status") == "available" for item in current_contexts
    )
    unavailable_total = sum(
        item["context"].get("status") == "cot_context_unavailable"
        for item in current_contexts
    )
    return {
        "status": "ok" if not errors and not refresh.get("errors") else "research_attention",
        "signals_requested": len(signals),
        "contexts_inserted": inserted,
        "contexts_existing": len(signals) - len(pending),
        "cot_linked": linked,
        "cot_context_unavailable": unavailable,
        "forward_linked_total": linked_total,
        "forward_unavailable_total": unavailable_total,
        "refresh": refresh,
        "errors": errors,
        "shadow_only": True,
        "research_only": True,
        "production_effect": "none",
        "scan_or_signal_blocked": False,
        "broad_research_blocked": False,
    }


def cot_shadow_store_audit(path: Path = DEFAULT_COT_DB_PATH) -> dict:
    initialize_cot_shadow_store(path)
    with _connect(Path(path)) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        reports = int(connection.execute("SELECT COUNT(*) FROM cot_reports").fetchone()[0])
        links = int(connection.execute("SELECT COUNT(*) FROM cot_shadow_links").fetchone()[0])
        unverified = int(
            connection.execute(
                """SELECT COUNT(*) FROM cot_reports r
                WHERE r.available_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM cot_report_availability a WHERE a.report_id = r.report_id
                  )"""
            ).fetchone()[0]
        )
        availability = int(connection.execute("SELECT COUNT(*) FROM cot_report_availability").fetchone()[0])
        contexts = int(connection.execute("SELECT COUNT(*) FROM cot_forward_contexts").fetchone()[0])
        linked = int(connection.execute("SELECT COUNT(*) FROM cot_forward_contexts WHERE status='available'").fetchone()[0])
        unavailable = int(connection.execute("SELECT COUNT(*) FROM cot_forward_contexts WHERE status='cot_context_unavailable'").fetchone()[0])
        report_types = [
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT report_type FROM cot_forward_contexts c JOIN cot_reports r ON r.report_id=c.report_id ORDER BY report_type"
            ).fetchall()
        ]
    return {
        "status": "ok" if integrity == "ok" else "attention",
        "integrity": integrity,
        "reports": reports,
        "shadow_links": links,
        "pit_unverified_reports": unverified,
        "availability_evidence": availability,
        "forward_contexts": contexts,
        "forward_linked": linked,
        "forward_unavailable": unavailable,
        "linked_report_types": report_types,
        "append_only": True,
        "shadow_only": True,
        "production_effect": "none",
    }
