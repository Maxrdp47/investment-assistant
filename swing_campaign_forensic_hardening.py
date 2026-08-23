from __future__ import annotations

"""Future-only hardening derived from the immutable Swing campaign-v1 postmortem.

This module is intentionally not imported by the legacy walk-forward runner or
the currently running Broad epoch.  It provides the contracts and append-only
ledgers required by a future campaign implementation without rewriting v1.
"""

import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


FORENSIC_HARDENING_VERSION = "swing-campaign-forensic-hardening-2026.08.23-v1"
CANONICAL_SETUP_ID_VERSION = "swing-canonical-setup-id-2026.08.23-v1"
FUNNEL_CONTRACT_VERSION = "swing-candidate-funnel-2026.08.23-v1"
MONITORING_CONTRACT_VERSION = "swing-incremental-monitoring-2026.08.23-v1"
RETRY_PROVENANCE_VERSION = "swing-campaign-retry-provenance-2026.08.23-v1"

BASE_CAMPAIGN_METHODOLOGY_VERSION = "swing-campaign-methodology-2026.08.23-v2.1"
BASE_ABC_VERSION = "swing-ground-up-abc-2026.08.23-v2.1"
PROTECTED_V1_DATASET_FINGERPRINT = (
    "e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed"
)


class SwingCampaignHardeningError(ValueError):
    """Raised when future campaign evidence would become ambiguous."""


class CanonicalSetupId(str, Enum):
    LONG_PULLBACK_TREND = "LONG_PULLBACK_TREND"
    LONG_BREAKOUT_CONFIRMED = "LONG_BREAKOUT_CONFIRMED"


SETUP_PRESENTATION_LABELS = {
    CanonicalSetupId.LONG_PULLBACK_TREND: "Rücksetzer im intakten Aufwärtstrend",
    CanonicalSetupId.LONG_BREAKOUT_CONFIRMED: "Bestätigter Ausbruch",
}

FUNNEL_STAGES = (
    "universe",
    "sufficient_data",
    "trend_context_eligible",
    "structural_candidate",
    "setup_candidate",
    "candidate_selected",
    "setup_filter_passed",
    "entry_eligible",
    "entry_activated",
    "entry_executed",
    "label_available",
    "evaluated",
)

TERMINAL_REASONS = (
    "no_setup",
    "setup_not_selected",
    "data_unavailable",
    "insufficient_history",
    "rejected_data_quality",
    "rejected_liquidity",
    "rejected_structure",
    "rejected_confirmation",
    "rejected_entry",
    "rejected_crv",
    "rejected_expected_value",
    "missed",
    "invalidated",
    "expired",
    "ambiguous",
    "insufficient_future",
    "overlap_purged",
    "deduplicated",
    "other_explicit_reason",
)

MONITORING_EVIDENCE_KINDS = (
    "historical_baseline",
    "initial_monitoring_baseline",
    "new_incremental_evidence",
    "historical_backfill",
    "true_forward",
)

_OUTCOME_KEYS = frozenset(
    {
        "outcome",
        "result",
        "result_r",
        "return",
        "forward_return",
        "mfe",
        "mae",
        "pnl",
        "profit",
        "loss",
        "winner",
        "label",
        "label_value",
        "realized_r",
        "expectancy",
        "exit_price",
        "target_hit",
        "profit_factor",
        "hit_rate",
    }
)


def _clean_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SwingCampaignHardeningError(f"{field} darf nicht leer sein.")
    return text


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


def _outcome_paths(value: object, *, prefix: str = "metadata") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            clean_key = str(key).strip()
            path = f"{prefix}.{clean_key}"
            if clean_key.casefold() in _OUTCOME_KEYS:
                paths.append(path)
            paths.extend(_outcome_paths(nested, prefix=path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, nested in enumerate(value):
            paths.extend(_outcome_paths(nested, prefix=f"{prefix}[{index}]"))
    return paths


def _verify_fingerprint(
    record: Mapping[str, object],
    *,
    field: str,
    label: str,
) -> None:
    payload = dict(record)
    expected = str(payload.pop(field, ""))
    if not expected or _fingerprint(payload) != expected:
        raise SwingCampaignHardeningError(
            f"{label}-Fingerprint fehlt oder wurde verändert."
        )


def _iso_date(value: object, field: str) -> str:
    text = _clean_text(value, field)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise SwingCampaignHardeningError(
            f"{field} muss ein ISO-Datum YYYY-MM-DD sein."
        ) from exc


def _iso_timestamp(value: object, field: str) -> str:
    text = _clean_text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SwingCampaignHardeningError(
            f"{field} muss ein gültiger ISO-Zeitpunkt sein."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SwingCampaignHardeningError(f"{field} benötigt eine Zeitzone.")
    return parsed.astimezone(timezone.utc).isoformat()


def _sqlite_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_canonical_setup_id(value: object) -> CanonicalSetupId:
    """Accept only an exact stable ID, never a localized label or substring."""

    if isinstance(value, CanonicalSetupId):
        return value
    text = str(value or "").strip()
    try:
        return CanonicalSetupId(text)
    except ValueError as exc:
        raise SwingCampaignHardeningError(
            f"Unbekannte kanonische Setup-ID: {text or '<leer>'}."
        ) from exc


def canonical_setup_identity(
    setup_id: CanonicalSetupId | str,
    *,
    display_name: str | None = None,
) -> dict[str, object]:
    canonical = normalize_canonical_setup_id(setup_id)
    label = (
        _clean_text(display_name, "display_name")
        if display_name is not None
        else SETUP_PRESENTATION_LABELS[canonical]
    )
    result: dict[str, object] = {
        "version": CANONICAL_SETUP_ID_VERSION,
        "canonical_setup_id": canonical.value,
        "display_name": label,
        "display_name_is_presentation_only": True,
        "localized_text_used_for_selection": False,
    }
    result["setup_identity_fingerprint"] = _fingerprint(result)
    return result


def future_setup_profile(
    *,
    profile_id: str,
    allowed_setup_ids: Sequence[CanonicalSetupId | str],
) -> dict[str, object]:
    if isinstance(allowed_setup_ids, (str, bytes)):
        raise SwingCampaignHardeningError("allowed_setup_ids muss eine Liste sein.")
    normalized = tuple(
        dict.fromkeys(
            normalize_canonical_setup_id(value).value for value in allowed_setup_ids
        )
    )
    if not normalized:
        raise SwingCampaignHardeningError(
            "Ein zukünftiges Setup-Profil benötigt mindestens eine kanonische ID."
        )
    profile: dict[str, object] = {
        "version": FORENSIC_HARDENING_VERSION,
        "profile_id": _clean_text(profile_id, "profile_id"),
        "technical_filter": {"canonical_setup_ids": list(normalized)},
        "localized_setup_text_filter": None,
        "substring_selection_allowed": False,
        "future_campaigns_only": True,
        "v1_profile_changed": False,
    }
    profile["profile_fingerprint"] = _fingerprint(profile)
    return profile


def future_setup_profile_matches(
    candidate: Mapping[str, object],
    profile: Mapping[str, object],
) -> bool:
    """Match a future candidate solely through its exact canonical setup ID."""

    _verify_fingerprint(
        profile,
        field="profile_fingerprint",
        label="Future-Setup-Profil",
    )
    rules = dict(profile.get("technical_filter") or {})
    forbidden = set(rules) - {"canonical_setup_ids"}
    if forbidden or "setup_type_contains" in rules:
        raise SwingCampaignHardeningError(
            "Fachliche Setup-Selektion darf keinen Text-/Substring-Filter enthalten."
        )
    candidate_id = normalize_canonical_setup_id(candidate.get("canonical_setup_id"))
    allowed = {
        normalize_canonical_setup_id(value)
        for value in (rules.get("canonical_setup_ids") or [])
    }
    if not allowed:
        raise SwingCampaignHardeningError(
            "Future-Setup-Profil besitzt keine zulässige kanonische ID."
        )
    return candidate_id in allowed


def v1_forensic_reference_contract() -> dict[str, object]:
    """Describe v1 without changing or reclassifying any stored result."""

    contract: dict[str, object] = {
        "version": FORENSIC_HARDENING_VERSION,
        "campaign_v1": "IMMUTABLE_HISTORICAL_REFERENCE",
        "frozen_dataset_fingerprint": PROTECTED_V1_DATASET_FINGERPRINT,
        "old_queue_changed": False,
        "old_cases_changed": False,
        "old_results_changed": False,
        "old_strategy_freezes_changed": False,
        "old_fingerprints_changed": False,
        "long_v1_changed": False,
        "pullback_only_v1": {
            "status": "invalid_historical_profile_due_to_setup_identity_mismatch",
            "zero_cases_are_negative_pullback_evidence": False,
            "historical_backfill_or_recalculation_allowed": False,
        },
        "breakout_and_long_v1": {
            "negative_evidence_retained": True,
            "retuning_allowed": False,
        },
        "rsi_and_ema_rsi": {
            "status": "hypothesis_seed_only",
            "active_rule": False,
        },
    }
    contract["reference_fingerprint"] = _fingerprint(contract)
    return contract


def build_candidate_funnel_record(
    *,
    campaign_version: str,
    contract_id: str,
    dataset_fingerprint: str,
    candidate_id: str,
    reached_stage: str,
    terminal_reason: str | None,
    recorded_at: str,
    canonical_setup_id: CanonicalSetupId | str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    stage = str(reached_stage or "").strip()
    if stage not in FUNNEL_STAGES:
        raise SwingCampaignHardeningError(f"Unbekannte Funnel-Stufe: {stage or '<leer>'}.")
    reason = str(terminal_reason or "").strip() or None
    if reason is not None and reason not in TERMINAL_REASONS:
        raise SwingCampaignHardeningError(f"Unbekannter terminaler Grund: {reason}.")
    if stage != "evaluated" and reason is None:
        raise SwingCampaignHardeningError(
            "Ein vor evaluated endender Funnel-Pfad benötigt genau einen terminalen Grund."
        )
    clean_metadata = dict(metadata or {})
    outcome_paths = sorted(_outcome_paths(clean_metadata))
    if outcome_paths:
        raise SwingCampaignHardeningError(
            "Der outcome-blinde Funnel darf keine Ergebnisfelder speichern: "
            + ", ".join(outcome_paths)
        )
    setup_id = (
        normalize_canonical_setup_id(canonical_setup_id).value
        if canonical_setup_id is not None
        else None
    )
    if FUNNEL_STAGES.index(stage) >= FUNNEL_STAGES.index("setup_candidate") and setup_id is None:
        raise SwingCampaignHardeningError(
            "Ab setup_candidate ist eine kanonische Setup-ID erforderlich."
        )
    record: dict[str, object] = {
        "version": FUNNEL_CONTRACT_VERSION,
        "campaign_version": _clean_text(campaign_version, "campaign_version"),
        "contract_id": _clean_text(contract_id, "contract_id"),
        "dataset_fingerprint": _clean_text(
            dataset_fingerprint, "dataset_fingerprint"
        ),
        "candidate_id": _clean_text(candidate_id, "candidate_id"),
        "last_stage_reached": stage,
        "stages_reached": list(FUNNEL_STAGES[: FUNNEL_STAGES.index(stage) + 1]),
        "terminal_reason": reason,
        "canonical_setup_id": setup_id,
        "recorded_at": _iso_timestamp(recorded_at, "recorded_at"),
        "metadata": clean_metadata,
        "outcomes_used": False,
        "append_only": True,
    }
    record["funnel_record_fingerprint"] = _fingerprint(record)
    return record


def summarize_candidate_funnel(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    seen: set[tuple[str, str, str]] = set()
    normalized: list[Mapping[str, object]] = []
    for record in records:
        _verify_fingerprint(
            record,
            field="funnel_record_fingerprint",
            label="Funnel-Record",
        )
        key = (
            str(record.get("campaign_version")),
            str(record.get("contract_id")),
            str(record.get("candidate_id")),
        )
        if key in seen:
            raise SwingCampaignHardeningError(
                "Ein Kandidat darf im kompakten Funnel nur einen terminalen Record besitzen."
            )
        seen.add(key)
        normalized.append(record)
    stage_counts = {
        stage: sum(stage in (record.get("stages_reached") or []) for record in normalized)
        for stage in FUNNEL_STAGES
    }
    reason_counts = {
        reason: sum(record.get("terminal_reason") == reason for record in normalized)
        for reason in TERMINAL_REASONS
    }
    reason_counts = {key: value for key, value in reason_counts.items() if value}
    trades = stage_counts["entry_executed"]
    non_trades = stage_counts["universe"] - trades
    monotonic = all(
        stage_counts[left] >= stage_counts[right]
        for left, right in zip(FUNNEL_STAGES, FUNNEL_STAGES[1:])
    )
    return {
        "version": FUNNEL_CONTRACT_VERSION,
        "records": len(normalized),
        "stage_counts": stage_counts,
        "terminal_reason_counts": reason_counts,
        "trades": trades,
        "non_trades": non_trades,
        "evaluated": stage_counts["evaluated"],
        "universe_equals_trades_plus_non_trades": (
            stage_counts["universe"] == trades + non_trades
        ),
        "stage_counts_monotonic": monotonic,
        "terminal_reason_is_single_valued": True,
        "status": (
            "ok"
            if monotonic and stage_counts["universe"] == trades + non_trades
            else "invalid"
        ),
        "outcomes_used_for_funnel": False,
    }


class CandidateFunnelLedger:
    """Append-only terminal funnel records for a future campaign database."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        with _sqlite_connection(self.path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidate_funnel_records (
                    campaign_version TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_fingerprint TEXT NOT NULL,
                    PRIMARY KEY (campaign_version, contract_id, candidate_id)
                );
                CREATE TRIGGER IF NOT EXISTS candidate_funnel_no_update
                BEFORE UPDATE ON candidate_funnel_records
                BEGIN SELECT RAISE(ABORT, 'candidate funnel is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS candidate_funnel_no_delete
                BEFORE DELETE ON candidate_funnel_records
                BEGIN SELECT RAISE(ABORT, 'candidate funnel is append-only'); END;
                """
            )

    def append(self, record: Mapping[str, object]) -> dict[str, object]:
        _verify_fingerprint(
            record,
            field="funnel_record_fingerprint",
            label="Funnel-Record",
        )
        key = (
            str(record.get("campaign_version")),
            str(record.get("contract_id")),
            str(record.get("candidate_id")),
        )
        encoded = _canonical_json(dict(record))
        fingerprint = str(record["funnel_record_fingerprint"])
        with _sqlite_connection(self.path) as connection:
            existing = connection.execute(
                """
                SELECT record_json, record_fingerprint
                FROM candidate_funnel_records
                WHERE campaign_version = ? AND contract_id = ? AND candidate_id = ?
                """,
                key,
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["record_fingerprint"]) != fingerprint
                    or str(existing["record_json"]) != encoded
                ):
                    raise SwingCampaignHardeningError(
                        "Divergenter Funnel-Record für dieselbe Kandidatenidentität."
                    )
                return {"inserted": False, "existing": True, "candidate_id": key[2]}
            connection.execute(
                """
                INSERT INTO candidate_funnel_records (
                    campaign_version, contract_id, candidate_id,
                    record_json, record_fingerprint
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (*key, encoded, fingerprint),
            )
        return {"inserted": True, "existing": False, "candidate_id": key[2]}

    def records(self) -> list[dict[str, object]]:
        with _sqlite_connection(self.path) as connection:
            rows = connection.execute(
                """
                SELECT record_json FROM candidate_funnel_records
                ORDER BY campaign_version, contract_id, candidate_id
                """
            ).fetchall()
        return [json.loads(str(row["record_json"])) for row in rows]

    def summary(self) -> dict[str, object]:
        return summarize_candidate_funnel(self.records())


def build_monitoring_contract(
    *,
    monitoring_version: str,
    previous_cutoff: str | None,
    current_cutoff: str,
    dataset_fingerprint: str,
) -> dict[str, object]:
    current = _iso_date(current_cutoff, "current_cutoff")
    previous = (
        _iso_date(previous_cutoff, "previous_cutoff")
        if previous_cutoff is not None
        else None
    )
    if previous is not None and previous >= current:
        raise SwingCampaignHardeningError(
            "previous_cutoff muss vor current_cutoff liegen."
        )
    contract: dict[str, object] = {
        "version": MONITORING_CONTRACT_VERSION,
        "monitoring_version": _clean_text(
            monitoring_version, "monitoring_version"
        ),
        "previous_cutoff": previous,
        "current_cutoff": current,
        "dataset_fingerprint": _clean_text(
            dataset_fingerprint, "dataset_fingerprint"
        ),
        "mode": (
            "recent_incremental" if previous is not None else "initial_monitoring_baseline"
        ),
        "historical_backfill_counts_as_incremental": False,
        "historical_reconstruction_counts_as_forward": False,
        "automatic_strategy_change": False,
    }
    contract["monitoring_contract_fingerprint"] = _fingerprint(contract)
    return contract


def build_monitoring_evidence_record(
    *,
    contract: Mapping[str, object],
    case_identity: str,
    signal_date: str,
    first_eligible_at: str,
    first_seen_in_monitoring: str,
    previously_seen_case_identities: Sequence[str] = (),
    historical_backfill: bool = False,
    true_forward: bool = False,
) -> dict[str, object]:
    _verify_fingerprint(
        contract,
        field="monitoring_contract_fingerprint",
        label="Monitoring-Vertrag",
    )
    signal = _iso_date(signal_date, "signal_date")
    first_eligible = _iso_date(first_eligible_at, "first_eligible_at")
    first_seen = _iso_timestamp(
        first_seen_in_monitoring, "first_seen_in_monitoring"
    )
    previous = contract.get("previous_cutoff")
    current = _iso_date(contract.get("current_cutoff"), "current_cutoff")
    identity = _clean_text(case_identity, "case_identity")
    seen = identity in {str(value) for value in previously_seen_case_identities}
    first_seen_day = first_seen[:10]

    if signal > current or first_eligible > current:
        raise SwingCampaignHardeningError(
            "Noch nicht berechtigte Fälle dürfen nicht in das Monitoring aufgenommen werden."
        )
    if historical_backfill and true_forward:
        raise SwingCampaignHardeningError(
            "Ein historischer Backfill darf nicht zugleich echte Forward-Evidenz sein."
        )
    if true_forward and previous is not None and (
        seen or first_eligible <= str(previous) or first_seen_day <= str(previous)
    ):
        raise SwingCampaignHardeningError(
            "Bereits bekannte oder früher berechtigte Fälle sind keine echte Forward-Evidenz."
        )
    if true_forward:
        kind = "true_forward"
        inclusion_reason = "independently_observed_true_forward_evidence"
    elif historical_backfill:
        kind = "historical_backfill"
        inclusion_reason = "explicit_historical_backfill_not_incremental"
    elif previous is None:
        kind = "initial_monitoring_baseline"
        inclusion_reason = "initial_baseline_for_new_monitoring_version"
    elif seen:
        kind = "historical_baseline"
        inclusion_reason = "case_identity_seen_before_current_monitoring_window"
    elif first_seen_day <= str(previous):
        kind = "historical_baseline"
        inclusion_reason = "case_was_first_seen_at_or_before_previous_cutoff"
    elif first_eligible <= str(previous):
        kind = "historical_baseline"
        inclusion_reason = "case_was_eligible_at_or_before_previous_cutoff"
    else:
        kind = "new_incremental_evidence"
        inclusion_reason = "first_became_eligible_after_previous_cutoff"

    record: dict[str, object] = {
        "version": MONITORING_CONTRACT_VERSION,
        "monitoring_version": contract.get("monitoring_version"),
        "previous_cutoff": previous,
        "current_cutoff": current,
        "dataset_fingerprint": contract.get("dataset_fingerprint"),
        "case_identity": identity,
        "signal_date": signal,
        "first_eligible_at": first_eligible,
        "first_seen_in_monitoring": first_seen,
        "inclusion_reason": inclusion_reason,
        "evidence_kind": kind,
        "counts_as_recent_incremental": kind == "new_incremental_evidence",
        "counts_as_true_forward": kind == "true_forward",
        "historical_backfill": bool(historical_backfill),
        "duplicate_case_identity": bool(seen),
        "automatic_strategy_change": False,
    }
    record["monitoring_record_fingerprint"] = _fingerprint(record)
    return record


def summarize_monitoring_evidence(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    identities: set[tuple[str, str]] = set()
    counts = {kind: 0 for kind in MONITORING_EVIDENCE_KINDS}
    incremental_identities: set[str] = set()
    for record in records:
        _verify_fingerprint(
            record,
            field="monitoring_record_fingerprint",
            label="Monitoring-Record",
        )
        key = (str(record.get("monitoring_version")), str(record.get("case_identity")))
        if key in identities:
            raise SwingCampaignHardeningError(
                "Identischer Fall darf innerhalb einer Monitoring-Version nicht doppelt zählen."
            )
        identities.add(key)
        kind = str(record.get("evidence_kind") or "")
        if kind not in counts:
            raise SwingCampaignHardeningError(f"Unbekannte Evidenzart: {kind}.")
        counts[kind] += 1
        if kind == "new_incremental_evidence":
            identity = str(record.get("case_identity"))
            if identity in incremental_identities:
                raise SwingCampaignHardeningError(
                    "Ein Fall darf versionenübergreifend nicht erneut als neu zählen."
                )
            incremental_identities.add(identity)
    return {
        "version": MONITORING_CONTRACT_VERSION,
        "historical_baseline": (
            counts["historical_baseline"] + counts["initial_monitoring_baseline"]
        ),
        "new_incremental_evidence": counts["new_incremental_evidence"],
        "true_forward": counts["true_forward"],
        "historical_backfill": counts["historical_backfill"],
        "counts_by_kind": counts,
        "backfill_counted_as_incremental": False,
        "historical_baseline_counted_as_true_forward": False,
        "status": "ok",
    }


def normalized_retry_reason(
    exception_class: str,
    message: str,
) -> str:
    class_name = _clean_text(exception_class, "exception_class")
    normalized_message = unicodedata.normalize("NFKC", str(message or "")).casefold()
    if (
        class_name == "FrozenResearchDatasetError"
        and "frozen price file has divergent data" in normalized_message
    ):
        return "frozen_dataset_divergent_data"
    normalized_class = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).casefold()
    normalized_class = re.sub(r"[^a-z0-9]+", "_", normalized_class).strip("_")
    return normalized_class or "unknown_failure"


def build_retry_attempt_record(
    *,
    campaign_version: str,
    contract_id: str,
    job_id: str,
    shard: str,
    attempt_number: int,
    worker_process: str,
    start_time: str,
    end_time: str,
    success: bool,
    dataset_fingerprint: str,
    code_contract_fingerprint: str,
    resume_key: str,
    completion_id: str,
    sample_selection_fingerprint: str,
    result_fingerprint: str | None = None,
    exception_class: str | None = None,
    error_message: str | None = None,
    affected_asset: str | None = None,
) -> dict[str, object]:
    if isinstance(attempt_number, bool) or int(attempt_number) < 1:
        raise SwingCampaignHardeningError("attempt_number muss positiv sein.")
    started = _iso_timestamp(start_time, "start_time")
    ended = _iso_timestamp(end_time, "end_time")
    if ended < started:
        raise SwingCampaignHardeningError("end_time darf nicht vor start_time liegen.")
    exception = str(exception_class or "").strip() or None
    if success:
        if exception is not None or error_message:
            raise SwingCampaignHardeningError(
                "Ein erfolgreicher Versuch darf keine Exception speichern."
            )
        result = _clean_text(result_fingerprint, "result_fingerprint")
        reason = None
    else:
        exception = _clean_text(exception, "exception_class")
        reason = normalized_retry_reason(exception, str(error_message or ""))
        result = None
    record: dict[str, object] = {
        "version": RETRY_PROVENANCE_VERSION,
        "campaign_version": _clean_text(campaign_version, "campaign_version"),
        "contract_id": _clean_text(contract_id, "contract_id"),
        "job_id": _clean_text(job_id, "job_id"),
        "shard": _clean_text(shard, "shard"),
        "attempt_number": int(attempt_number),
        "worker_process": _clean_text(worker_process, "worker_process"),
        "start_time": started,
        "end_time": ended,
        "status": "success" if success else "failure",
        "exception_class": exception,
        "normalized_error_reason": reason,
        "affected_asset": str(affected_asset or "").strip() or None,
        "dataset_fingerprint": _clean_text(
            dataset_fingerprint, "dataset_fingerprint"
        ),
        "code_contract_fingerprint": _clean_text(
            code_contract_fingerprint, "code_contract_fingerprint"
        ),
        "resume_key": _clean_text(resume_key, "resume_key"),
        "completion_id": _clean_text(completion_id, "completion_id"),
        "sample_selection_fingerprint": _clean_text(
            sample_selection_fingerprint, "sample_selection_fingerprint"
        ),
        "result_fingerprint": result,
        "full_traceback_stored_in_database": False,
    }
    record["attempt_fingerprint"] = _fingerprint(record)
    return record


def retry_log_line(
    attempt: Mapping[str, object],
    *,
    event: str,
    traceback_log_reference: str | None = None,
) -> str:
    _verify_fingerprint(
        attempt,
        field="attempt_fingerprint",
        label="Retry-Attempt",
    )
    payload = {
        "event": _clean_text(event, "event"),
        "campaign_version": attempt.get("campaign_version"),
        "contract_id": attempt.get("contract_id"),
        "job_id": attempt.get("job_id"),
        "shard": attempt.get("shard"),
        "attempt_number": attempt.get("attempt_number"),
        "worker_process": attempt.get("worker_process"),
        "status": attempt.get("status"),
        "exception_class": attempt.get("exception_class"),
        "normalized_error_reason": attempt.get("normalized_error_reason"),
        "affected_asset": attempt.get("affected_asset"),
        "dataset_fingerprint": attempt.get("dataset_fingerprint"),
        "resume_key": attempt.get("resume_key"),
        "traceback_log_reference": str(traceback_log_reference or "").strip() or None,
    }
    return _canonical_json(payload)


class CampaignRetryLedger:
    """Append-only attempt and completion provenance for future jobs."""

    _STABLE_FIELDS = (
        "campaign_version",
        "contract_id",
        "shard",
        "dataset_fingerprint",
        "code_contract_fingerprint",
        "resume_key",
        "completion_id",
        "sample_selection_fingerprint",
    )

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        with _sqlite_connection(self.path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaign_attempts (
                    job_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    attempt_json TEXT NOT NULL,
                    attempt_fingerprint TEXT NOT NULL,
                    PRIMARY KEY (job_id, attempt_number)
                );
                CREATE TABLE IF NOT EXISTS campaign_completions (
                    completion_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE,
                    dataset_fingerprint TEXT NOT NULL,
                    code_contract_fingerprint TEXT NOT NULL,
                    sample_selection_fingerprint TEXT NOT NULL,
                    result_fingerprint TEXT NOT NULL,
                    completion_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS campaign_attempts_no_update
                BEFORE UPDATE ON campaign_attempts
                BEGIN SELECT RAISE(ABORT, 'campaign attempts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS campaign_attempts_no_delete
                BEFORE DELETE ON campaign_attempts
                BEGIN SELECT RAISE(ABORT, 'campaign attempts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS campaign_completions_no_update
                BEFORE UPDATE ON campaign_completions
                BEGIN SELECT RAISE(ABORT, 'campaign completions are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS campaign_completions_no_delete
                BEFORE DELETE ON campaign_completions
                BEGIN SELECT RAISE(ABORT, 'campaign completions are append-only'); END;
                """
            )

    def append(self, attempt: Mapping[str, object]) -> dict[str, object]:
        _verify_fingerprint(
            attempt,
            field="attempt_fingerprint",
            label="Retry-Attempt",
        )
        job_id = str(attempt.get("job_id"))
        number = int(attempt.get("attempt_number") or 0)
        encoded = _canonical_json(dict(attempt))
        fingerprint = str(attempt.get("attempt_fingerprint"))
        with _sqlite_connection(self.path) as connection:
            existing = connection.execute(
                """
                SELECT attempt_json, attempt_fingerprint
                FROM campaign_attempts WHERE job_id = ? AND attempt_number = ?
                """,
                (job_id, number),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["attempt_json"]) != encoded
                    or str(existing["attempt_fingerprint"]) != fingerprint
                ):
                    raise SwingCampaignHardeningError(
                        "Divergente Daten für dieselbe Job-/Attempt-ID."
                    )
                return {"inserted": False, "existing": True, "completion_inserted": False}

            prior_rows = connection.execute(
                """
                SELECT attempt_number, attempt_json
                FROM campaign_attempts WHERE job_id = ? ORDER BY attempt_number
                """,
                (job_id,),
            ).fetchall()
            expected_number = len(prior_rows) + 1
            if number != expected_number:
                raise SwingCampaignHardeningError(
                    f"Attempt-Folge muss lückenlos sein; erwartet {expected_number}."
                )
            prior_attempts = [json.loads(str(row["attempt_json"])) for row in prior_rows]
            if any(row.get("status") == "success" for row in prior_attempts):
                raise SwingCampaignHardeningError(
                    "Nach erfolgreicher Completion darf kein weiterer Retry starten."
                )
            for prior in prior_attempts:
                changed = [
                    field
                    for field in self._STABLE_FIELDS
                    if prior.get(field) != attempt.get(field)
                ]
                if changed:
                    raise SwingCampaignHardeningError(
                        "Retry darf Identität, Dataset oder Sample nicht ändern: "
                        + ", ".join(changed)
                    )

            connection.execute(
                """
                INSERT INTO campaign_attempts (
                    job_id, attempt_number, attempt_json, attempt_fingerprint
                ) VALUES (?, ?, ?, ?)
                """,
                (job_id, number, encoded, fingerprint),
            )
            completion_inserted = False
            if attempt.get("status") == "success":
                completion = {
                    "completion_id": attempt.get("completion_id"),
                    "job_id": job_id,
                    "dataset_fingerprint": attempt.get("dataset_fingerprint"),
                    "code_contract_fingerprint": attempt.get(
                        "code_contract_fingerprint"
                    ),
                    "sample_selection_fingerprint": attempt.get(
                        "sample_selection_fingerprint"
                    ),
                    "result_fingerprint": attempt.get("result_fingerprint"),
                }
                existing_completion = connection.execute(
                    """
                    SELECT completion_json FROM campaign_completions
                    WHERE completion_id = ? OR job_id = ?
                    """,
                    (attempt.get("completion_id"), job_id),
                ).fetchone()
                if existing_completion is not None:
                    if json.loads(str(existing_completion["completion_json"])) != completion:
                        raise SwingCampaignHardeningError(
                            "Retry würde eine bestehende Completion verändern."
                        )
                else:
                    connection.execute(
                        """
                        INSERT INTO campaign_completions (
                            completion_id, job_id, dataset_fingerprint,
                            code_contract_fingerprint, sample_selection_fingerprint,
                            result_fingerprint, completion_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            attempt.get("completion_id"),
                            job_id,
                            attempt.get("dataset_fingerprint"),
                            attempt.get("code_contract_fingerprint"),
                            attempt.get("sample_selection_fingerprint"),
                            attempt.get("result_fingerprint"),
                            _canonical_json(completion),
                        ),
                    )
                    completion_inserted = True
        return {
            "inserted": True,
            "existing": False,
            "completion_inserted": completion_inserted,
        }

    def integrity_report(self, job_id: str) -> dict[str, object]:
        job = _clean_text(job_id, "job_id")
        with _sqlite_connection(self.path) as connection:
            rows = connection.execute(
                """
                SELECT attempt_json FROM campaign_attempts
                WHERE job_id = ? ORDER BY attempt_number
                """,
                (job,),
            ).fetchall()
            completions = connection.execute(
                "SELECT completion_json FROM campaign_completions WHERE job_id = ?",
                (job,),
            ).fetchall()
        attempts = [json.loads(str(row["attempt_json"])) for row in rows]
        if not attempts:
            raise KeyError(f"Unbekannter Campaign-Job: {job}")
        stable = {
            field: len({str(attempt.get(field)) for attempt in attempts}) == 1
            for field in self._STABLE_FIELDS
        }
        successes = [attempt for attempt in attempts if attempt.get("status") == "success"]
        return {
            "version": RETRY_PROVENANCE_VERSION,
            "job_id": job,
            "attempts": len(attempts),
            "failures": len(attempts) - len(successes),
            "successes": len(successes),
            "completion_rows": len(completions),
            "stable_identity": stable,
            "identical_completion_id": stable["completion_id"],
            "sample_selection_unchanged": stable["sample_selection_fingerprint"],
            "dataset_unchanged": stable["dataset_fingerprint"],
            "code_contract_unchanged": stable["code_contract_fingerprint"],
            "no_double_counting": len(successes) <= 1 and len(completions) <= 1,
            "result_change_through_retry": False,
            "status": (
                "ok"
                if successes
                and len(successes) == 1
                and len(completions) == 1
                and all(stable.values())
                else "pending_retry"
                if not successes and all(stable.values())
                else "invalid"
            ),
        }


def forensic_hypothesis_seeds() -> list[dict[str, object]]:
    """Neutral postmortem seeds; no mined threshold is promoted to a rule."""

    definitions = (
        (
            "momentum_state_incremental_information",
            "RSI / Momentum",
            "Untersuchen, ob der Momentumzustand inkrementelle Information über die Broad-Baseline liefert.",
        ),
        (
            "participation_relative_volume_information",
            "Relative Volume / Participation",
            "Untersuchen, ob Participation beziehungsweise relatives Volumen inkrementellen Informationswert besitzt.",
        ),
        (
            "volatility_regime_stability",
            "Volatility Regime",
            "Untersuchen, ob die Strategiequalität zwischen Volatilitätsregimen stabil variiert.",
        ),
        (
            "market_regime_trend_correction_stability",
            "Market Regime / Trend Correction",
            "Untersuchen, ob die Strategiequalität zwischen Marktregimen und Trendkorrekturen stabil variiert.",
        ),
        (
            "canonical_pullback_breakout_setup_difference",
            "Setup Type Pullback vs Breakout",
            "Untersuchen, ob die Strategiequalität zwischen kanonisch identifizierten Pullback- und Breakout-Setups stabil variiert.",
        ),
    )
    return [
        {
            "seed_id": seed_id,
            "family": family,
            "claim": claim,
            "source": "campaign_v1_forensic_postmortem",
            "status": "hypothesis_seed_only",
            "knowledge_status": "HYPOTHESIS",
            "available_after_current_broad_pass": True,
            "historical_threshold_is_rule": False,
            "automatic_experiment_start": False,
            "automatic_strategy_change": False,
            "automatic_activation": False,
        }
        for seed_id, family, claim in definitions
    ]


def future_campaign_hardening_contract() -> dict[str, object]:
    contract: dict[str, object] = {
        "version": FORENSIC_HARDENING_VERSION,
        "status": "PREPARED_FUTURE_CAMPAIGNS_ONLY",
        "base_methodology_version": BASE_CAMPAIGN_METHODOLOGY_VERSION,
        "base_abc_version": BASE_ABC_VERSION,
        "v1_reference": v1_forensic_reference_contract(),
        "canonical_setup_identity_version": CANONICAL_SETUP_ID_VERSION,
        "canonical_setup_consumers": {
            "research": "canonical_setup_id",
            "scanner": "canonical_setup_id",
            "campaign": "canonical_setup_id",
            "strategy_freeze": "canonical_setup_id",
            "reporting": "canonical_setup_id",
        },
        "localized_setup_text_is_presentation_only": True,
        "substring_setup_selection_allowed": False,
        "candidate_funnel_version": FUNNEL_CONTRACT_VERSION,
        "incremental_monitoring_version": MONITORING_CONTRACT_VERSION,
        "retry_provenance_version": RETRY_PROVENANCE_VERSION,
        "abc_v2_1_rebuilt": False,
        "abc_v2_1_changed": False,
        "abc_replaces_development_validation_holdout": False,
        "evidence_sequence": [
            "development",
            "fixed_challenger",
            "validation",
            "holdout",
            "external_unseen",
            "true_forward",
            "autonomous_paper",
            "shadow",
        ],
        "positive_c_opens_production": False,
        "sample_size_policy": {
            "fixed_technical_threshold_is_scientific_truth": False,
            "conservative_warning_threshold_may_remain": True,
            "future_power_and_precision_analysis_supported": True,
            "outcomes_may_change_required_sample_after_test": False,
            "underpowered_may_pass": False,
        },
        "current_broad_pass": {
            "feature_contract_changed": False,
            "candidate_definition_changed": False,
            "feature_fingerprint_changed": False,
            "database_changed": False,
            "cases_changed": False,
            "development_hypotheses_changed": False,
            "restart_requested": False,
        },
        "long_v1_retuned": False,
        "old_challenger_activated": False,
        "new_filter_activated": False,
        "broker_or_real_money_function_changed": False,
    }
    contract["hardening_contract_fingerprint"] = _fingerprint(contract)
    return contract
