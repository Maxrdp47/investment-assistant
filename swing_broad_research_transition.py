from __future__ import annotations

"""Fail-closed handoff from the immutable 248-job campaign to broad research."""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


EXPECTED_CAMPAIGN_JOBS = 248
TRANSITION_VERSION = "swing-broad-research-transition-2026.08.23-v2"
DEFAULT_TRANSITION_DIR = (
    Path(__file__).resolve().parent / "runtime" / "swing_broad_research_transition"
)


class BroadResearchTransitionError(RuntimeError):
    """The old campaign cannot safely hand off to broad research."""


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def broad_transition_identity(
    *,
    campaign_status: Mapping[str, object],
    manifest: Mapping[str, object],
    code_fingerprint: str,
    feature_contract_fingerprint: str,
) -> dict[str, object]:
    return {
        "transition_version": TRANSITION_VERSION,
        "campaign_jobs_total": int(campaign_status.get("jobs_total") or 0),
        "campaign_jobs_completed": int(campaign_status.get("jobs_completed") or 0),
        "campaign_jobs_pending": int(campaign_status.get("jobs_pending") or 0),
        "dataset_epoch": str(manifest.get("dataset_epoch") or ""),
        "dataset_fingerprint": str(manifest.get("dataset_fingerprint") or ""),
        "dataset_revision": str(manifest.get("dataset_revision") or ""),
        "dataset_manifest_version": str(manifest.get("manifest_version") or ""),
        "broad_code_fingerprint": str(code_fingerprint),
        "broad_feature_contract_fingerprint": str(feature_contract_fingerprint),
    }


def validate_broad_research_transition(
    *,
    campaign_status: Mapping[str, object],
    campaign_state: Mapping[str, object],
    campaign_jobs: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
    walk_forward_audit: Mapping[str, object],
    code_fingerprint: str,
    feature_contract_fingerprint: str,
) -> dict[str, object]:
    """Validate completion, immutable dataset and historical store fingerprints."""
    total = int(campaign_status.get("jobs_total") or 0)
    completed_count = int(campaign_status.get("jobs_completed") or 0)
    pending = int(campaign_status.get("jobs_pending") or 0)
    if total != EXPECTED_CAMPAIGN_JOBS or len(campaign_jobs) != EXPECTED_CAMPAIGN_JOBS:
        raise BroadResearchTransitionError(
            f"Unerwarteter Kampagnenvertrag: {total}/{len(campaign_jobs)} statt 248."
        )
    if completed_count != EXPECTED_CAMPAIGN_JOBS or pending != 0:
        raise BroadResearchTransitionError(
            f"Bestehende Kampagne ist noch nicht vollständig: {completed_count}/{total}, offen {pending}."
        )
    completed = dict(campaign_state.get("completed") or {})
    job_keys = [str(job.get("job_key") or "") for job in campaign_jobs]
    missing = [key for key in job_keys if not key or key not in completed]
    if missing:
        raise BroadResearchTransitionError(
            f"Abschlussnachweise fehlen für {len(missing)} Kampagnenjobs."
        )
    if str(manifest.get("status") or "") != "finalized":
        raise BroadResearchTransitionError("Der Frozen-Datensatz ist nicht finalisiert.")
    dataset_fingerprint = str(manifest.get("dataset_fingerprint") or "")
    if not dataset_fingerprint or dataset_fingerprint != str(
        manifest.get("dataset_revision") or ""
    ):
        raise BroadResearchTransitionError(
            "Dataset-Fingerprint und unveränderbare Revision stimmen nicht überein."
        )
    if not str(manifest.get("dataset_epoch") or "").endswith("|fixed"):
        raise BroadResearchTransitionError(
            "Der breite Lauf darf nur den festen, nicht den wöchentlichen Datensatz verwenden."
        )
    fixed_jobs = [
        dict(job)
        for job in campaign_jobs
        if str(dict(job.get("contract") or {}).get("recurrence") or "once") == "once"
    ]
    monitoring_jobs = [
        dict(job)
        for job in campaign_jobs
        if str(dict(job.get("contract") or {}).get("recurrence") or "once") == "weekly"
    ]
    fixed_job_keys = [str(job.get("job_key") or "") for job in fixed_jobs]
    fixed_dataset_epochs = {
        str(dict(completed[key] or {}).get("dataset_epoch") or "")
        for key in fixed_job_keys
    }
    fixed_dataset_fingerprints = {
        str(dict(completed[key] or {}).get("dataset_fingerprint") or "")
        for key in fixed_job_keys
    }
    if not fixed_job_keys:
        raise BroadResearchTransitionError(
            "Die Kampagne enthält keine festen Forschungsjobs für den Broad-Übergang."
        )
    if fixed_dataset_epochs != {str(manifest.get("dataset_epoch") or "")}:
        raise BroadResearchTransitionError(
            "Nicht alle festen Kampagnenjobs verweisen auf dieselbe Frozen-Dataset-Epoche."
        )
    if fixed_dataset_fingerprints != {dataset_fingerprint}:
        raise BroadResearchTransitionError(
            "Nicht alle festen Kampagnenjobs verweisen auf denselben Frozen-Datensatz."
        )
    monitoring_datasets: dict[str, set[str]] = {}
    for job in monitoring_jobs:
        key = str(job.get("job_key") or "")
        epoch = str(job.get("epoch") or "")
        completion = dict(completed[key] or {})
        completion_epoch = str(completion.get("dataset_epoch") or "")
        completion_fingerprint = str(completion.get("dataset_fingerprint") or "")
        if not epoch or not completion_epoch.endswith(f"|{epoch}"):
            raise BroadResearchTransitionError(
                "Ein wöchentlicher Monitoringjob verweist auf eine falsche Dataset-Epoche."
            )
        if not completion_fingerprint:
            raise BroadResearchTransitionError(
                "Ein wöchentlicher Monitoringjob besitzt keinen Dataset-Fingerprint."
            )
        monitoring_datasets.setdefault(completion_epoch, set()).add(
            completion_fingerprint
        )
    if any(len(fingerprints) != 1 for fingerprints in monitoring_datasets.values()):
        raise BroadResearchTransitionError(
            "Wöchentliche Monitoringjobs derselben Epoche besitzen unterschiedliche Dataset-Fingerprints."
        )
    if (
        str(walk_forward_audit.get("quick_check") or "") != "ok"
        or str(walk_forward_audit.get("status") or "") != "ok"
        or int(walk_forward_audit.get("invalid_count") or 0) != 0
    ):
        raise BroadResearchTransitionError(
            "Walk-Forward-Datenbank oder gespeicherte Fingerprints sind nicht vollständig gültig."
        )
    if not code_fingerprint or not feature_contract_fingerprint:
        raise BroadResearchTransitionError("Code- oder Feature-Vertragsfingerprint fehlt.")
    identity = broad_transition_identity(
        campaign_status=campaign_status,
        manifest=manifest,
        code_fingerprint=code_fingerprint,
        feature_contract_fingerprint=feature_contract_fingerprint,
    )
    payload = {
        **identity,
        "campaign_job_keys_fingerprint": _fingerprint(job_keys),
        "campaign_completion_fingerprint": _fingerprint(
            [
                {
                    "job_key": key,
                    "dataset_epoch": dict(completed[key] or {}).get("dataset_epoch"),
                    "dataset_fingerprint": dict(completed[key] or {}).get(
                        "dataset_fingerprint"
                    ),
                    "contract": dict(completed[key] or {}).get("contract"),
                    "shard_index": dict(completed[key] or {}).get("shard_index"),
                }
                for key in job_keys
            ]
        ),
        "walk_forward_store": {
            "schema_version": walk_forward_audit.get("schema_version"),
            "quick_check": walk_forward_audit.get("quick_check"),
            "runs": int(walk_forward_audit.get("runs") or 0),
            "cases": int(walk_forward_audit.get("cases") or 0),
            "observational_features": int(
                walk_forward_audit.get("observational_features") or 0
            ),
            "invalid_count": int(walk_forward_audit.get("invalid_count") or 0),
            "status": walk_forward_audit.get("status"),
        },
        "campaign_dataset_groups": {
            "fixed_jobs": len(fixed_jobs),
            "fixed_dataset_epoch": str(manifest.get("dataset_epoch") or ""),
            "fixed_dataset_fingerprint": dataset_fingerprint,
            "monitoring_jobs": len(monitoring_jobs),
            "monitoring_datasets": {
                epoch: next(iter(fingerprints))
                for epoch, fingerprints in sorted(monitoring_datasets.items())
            },
        },
        "existing_campaign_changed": False,
        "existing_campaign_restarted": False,
        "new_market_data_download_allowed": False,
        "automatic_production_activation": False,
    }
    return {**payload, "transition_fingerprint": _fingerprint(payload)}


def transition_receipt_path(
    identity: Mapping[str, object],
    directory: Path = DEFAULT_TRANSITION_DIR,
) -> Path:
    return Path(directory) / f"{_fingerprint(dict(identity))}.json"


def load_broad_transition_receipt(
    identity: Mapping[str, object],
    directory: Path = DEFAULT_TRANSITION_DIR,
) -> dict[str, object] | None:
    path = transition_receipt_path(identity, directory)
    if not path.is_file():
        return None
    receipt = json.loads(path.read_text(encoding="utf-8"))
    payload = dict(receipt.get("payload") or {})
    if dict(receipt.get("identity") or {}) != dict(identity):
        raise BroadResearchTransitionError("Transition-Receipt besitzt eine abweichende Identität.")
    if str(receipt.get("transition_fingerprint") or "") != _fingerprint(payload):
        raise BroadResearchTransitionError("Transition-Receipt-Fingerprint ist ungültig.")
    if payload.get("existing_campaign_changed") is not False:
        raise BroadResearchTransitionError("Transition-Receipt erlaubt eine Kampagnenänderung.")
    return receipt


def record_broad_transition_receipt(
    payload: Mapping[str, object],
    *,
    identity: Mapping[str, object],
    directory: Path = DEFAULT_TRANSITION_DIR,
) -> dict[str, object]:
    """Create one immutable receipt; an existing receipt is only verified."""
    path = transition_receipt_path(identity, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_broad_transition_receipt(identity, directory)
    if existing is not None:
        if dict(existing.get("payload") or {}) != dict(payload):
            raise BroadResearchTransitionError(
                "Ein vorhandener Transition-Receipt weicht vom neuen Prüfergebnis ab."
            )
        return existing
    receipt = {
        "identity": dict(identity),
        "validated_at": datetime.now().astimezone().isoformat(),
        "payload": dict(payload),
        "transition_fingerprint": _fingerprint(dict(payload)),
        "append_only": True,
    }
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(_canonical_json(receipt), encoding="utf-8")
    try:
        # os.link fails if the immutable destination already appeared in a race.
        os.link(temporary, path)
    except FileExistsError:
        pass
    finally:
        temporary.unlink(missing_ok=True)
    stored = load_broad_transition_receipt(identity, directory)
    if stored is None:
        raise BroadResearchTransitionError("Transition-Receipt konnte nicht gespeichert werden.")
    if dict(stored.get("payload") or {}) != dict(payload):
        raise BroadResearchTransitionError("Parallel gespeicherter Transition-Receipt weicht ab.")
    return stored
