from __future__ import annotations

"""Offline, CIK-keyed SEC Company Facts history with conservative daily PIT cutoff.

This adapter does not fetch data, map present-day tickers backward, or activate
fundamental trading features. A filing-date-only row becomes available no
earlier than the next calendar day; exact intraday acceptance is not claimed.
"""

import hashlib
import json
import math
import re
from datetime import date, timedelta
from typing import Any, Mapping

from sec_financial_facts import ANNUAL_SEC_FORMS, SEC_METRIC_DEFINITIONS


VERSION = "sec-pit-fundamentals-2026.09.22-v1"
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}")


def _day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def extract_annual_pit_history(
    company_facts: Mapping[str, Any], *, source_snapshot_sha256: str
) -> dict[str, Any]:
    """Preserve distinct filing revisions; never collapse them into current truth."""

    if not re.fullmatch(r"[0-9a-f]{64}", source_snapshot_sha256):
        raise ValueError("Versioned SEC source snapshot SHA-256 is required")
    try:
        cik = int(company_facts["cik"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("SEC Company Facts CIK is required") from exc
    if cik < 1:
        raise ValueError("SEC CIK must be positive")
    taxonomy = company_facts.get("facts", {})
    if taxonomy is None:
        taxonomy = {}
    if not isinstance(taxonomy, dict):
        raise ValueError("SEC facts must be an object")
    us_gaap = taxonomy.get("us-gaap", {})
    if us_gaap is None:
        us_gaap = {}
    if not isinstance(us_gaap, dict):
        raise ValueError("SEC us-gaap facts must be an object")
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for metric, definition in SEC_METRIC_DEFINITIONS.items():
        for concept_rank, concept in enumerate(definition.concepts):
            payload = us_gaap.get(concept)
            units = payload.get("units") if isinstance(payload, dict) else None
            entries = units.get(definition.unit) if isinstance(units, dict) else None
            if not isinstance(entries, list):
                continue
            for item in entries:
                if not isinstance(item, dict):
                    continue
                form = str(item.get("form") or "").upper()
                accession = str(item.get("accn") or "")
                filed = _day(item.get("filed"))
                period_end = _day(item.get("end"))
                period_start = _day(item.get("start")) if item.get("start") else None
                if (
                    form not in ANNUAL_SEC_FORMS
                    or ACCESSION.fullmatch(accession) is None
                    or filed is None
                    or period_end is None
                    or period_end > filed
                    or (period_start is not None and period_start > period_end)
                    or str(item.get("fp") or "FY").upper() != "FY"
                ):
                    continue
                try:
                    value = float(item["val"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not math.isfinite(value):
                    continue
                key = (metric, period_end.isoformat(), accession)
                if key in rows and rows[key]["concept_rank"] <= concept_rank:
                    continue
                rows[key] = {
                    "metric": metric,
                    "concept": concept,
                    "concept_rank": concept_rank,
                    "unit": definition.unit,
                    "value": value,
                    "period_start": period_start.isoformat() if period_start else None,
                    "period_end": period_end.isoformat(),
                    "filed_at": filed.isoformat(),
                    "first_usable_date": (filed + timedelta(days=1)).isoformat(),
                    "accession_number": accession,
                    "form": form,
                    "cik": cik,
                    "source_snapshot_sha256": source_snapshot_sha256,
                    "availability_semantics": "FILED_DATE_ONLY_CONSERVATIVE_NEXT_DAY",
                }
    facts = sorted(
        rows.values(),
        key=lambda item: (item["metric"], item["period_end"], item["filed_at"], item["accession_number"]),
    )
    for fact in facts:
        fact.pop("concept_rank")
    return {
        "version": VERSION,
        "cik": cik,
        "entity_name": str(company_facts.get("entityName") or ""),
        "source_snapshot_sha256": source_snapshot_sha256,
        "facts": facts,
        "history_fingerprint": hashlib.sha256(
            json.dumps(facts, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
        "historical_ticker_join_performed": False,
        "current_fundamentals_backdated": False,
    }


def annual_facts_as_of(history: Mapping[str, Any], signal_date: str) -> dict[str, dict[str, Any]]:
    """Return latest known annual period and revision per metric at a daily cutoff."""

    as_of = _day(signal_date)
    if as_of is None:
        raise ValueError("Signal date must be ISO YYYY-MM-DD")
    latest: dict[str, dict[str, Any]] = {}
    for fact in history.get("facts") or []:
        if _day(fact.get("first_usable_date")) is None:
            raise ValueError("Malformed PIT fact availability")
        if fact["first_usable_date"] > as_of.isoformat():
            continue
        metric = str(fact["metric"])
        prior = latest.get(metric)
        ranking = (fact["period_end"], fact["filed_at"], fact["accession_number"])
        if prior is None or ranking > (prior["period_end"], prior["filed_at"], prior["accession_number"]):
            latest[metric] = dict(fact)
    return latest
