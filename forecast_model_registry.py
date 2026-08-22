from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any


MODEL_REGISTRY_SCHEMA_VERSION = 1
MODEL_CANDIDATE_VERSION = "forecast-shadow-candidate-2026.08.09-v1"
MODEL_EVENT_VERSION = "forecast-model-event-2026.08.09-v1"
MODEL_PROMOTION_POLICY_VERSION = "forecast-promotion-gate-2026.08.09-v1"
DEFAULT_MODEL_REGISTRY_PATH = Path(__file__).resolve().parent / "runtime" / "forecast_model_registry.sqlite3"
ALLOWED_MODEL_EVENTS = {
    "shadow_evaluated",
    "manual_review_approved",
    "manual_review_rejected",
    "canary_verified",
    "rollback_verified",
}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (Path, date, datetime)):
        return value.isoformat()
    item = getattr(value, "item", None)
    return _clean(item()) if callable(item) else value


def _canonical_json(payload: dict) -> str:
    return json.dumps(_clean(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _valid_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text.lower())


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_model_registry(path: Path = DEFAULT_MODEL_REGISTRY_PATH) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS registry_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_candidates (
                candidate_id TEXT PRIMARY KEY,
                registered_at TEXT NOT NULL,
                model_type TEXT NOT NULL,
                horizon TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                snapshot_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_events (
                event_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL REFERENCES model_candidates(candidate_id),
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS model_candidates_no_update
            BEFORE UPDATE ON model_candidates BEGIN
                SELECT RAISE(ABORT, 'model_candidates is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS model_candidates_no_delete
            BEFORE DELETE ON model_candidates BEGIN
                SELECT RAISE(ABORT, 'model_candidates is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS model_events_no_update
            BEFORE UPDATE ON model_events BEGIN
                SELECT RAISE(ABORT, 'model_events is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS model_events_no_delete
            BEFORE DELETE ON model_events BEGIN
                SELECT RAISE(ABORT, 'model_events is append-only');
            END;
            """
        )
        existing = connection.execute("SELECT value FROM registry_meta WHERE key = 'schema_version'").fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO registry_meta (key, value) VALUES ('schema_version', ?)",
                (str(MODEL_REGISTRY_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != MODEL_REGISTRY_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstütztes Modellregister-Schema.")


def register_shadow_candidate(
    metadata: dict,
    *,
    registered_at: object,
    path: Path = DEFAULT_MODEL_REGISTRY_PATH,
) -> dict:
    required = {
        "model_type",
        "horizon",
        "algorithm",
        "dataset_fingerprint",
        "walk_forward_fingerprint",
        "feature_schema_version",
        "training_code_fingerprint",
        "artifact_fingerprint",
        "training_cutoff_at",
    }
    missing = sorted(required - set(metadata))
    if missing:
        raise ValueError(f"Modellkandidat unvollständig: {', '.join(missing)}")
    for field in (
        "dataset_fingerprint",
        "walk_forward_fingerprint",
        "training_code_fingerprint",
        "artifact_fingerprint",
    ):
        if not _valid_sha256(metadata.get(field)):
            raise ValueError(f"{field} ist kein gültiger SHA-256-Fingerabdruck.")
    snapshot = {
        "candidate_version": MODEL_CANDIDATE_VERSION,
        **dict(metadata),
        "registered_at": str(registered_at),
        "mode": "shadow_only",
        "automatic_production_activation": False,
    }
    candidate_id = _fingerprint(snapshot)
    fingerprint = _fingerprint(snapshot)
    initialize_model_registry(path)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT snapshot_fingerprint FROM model_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if existing is not None:
            if existing["snapshot_fingerprint"] != fingerprint:
                raise ValueError("Modellkandidat besitzt einen Identitätskonflikt.")
            return {"candidate_id": candidate_id, "inserted": False}
        connection.execute(
            "INSERT INTO model_candidates (candidate_id, registered_at, model_type, horizon, snapshot_json, snapshot_fingerprint) VALUES (?, ?, ?, ?, ?, ?)",
            (
                candidate_id,
                str(registered_at),
                str(metadata["model_type"]),
                str(metadata["horizon"]),
                _canonical_json(snapshot),
                fingerprint,
            ),
        )
    return {"candidate_id": candidate_id, "inserted": True}


def append_model_event(
    candidate_id: str,
    event_type: str,
    occurred_at: object,
    payload: dict,
    *,
    path: Path = DEFAULT_MODEL_REGISTRY_PATH,
) -> dict:
    if event_type not in ALLOWED_MODEL_EVENTS:
        raise ValueError("Unbekannter Modellregister-Ereignistyp.")
    wrapper = {
        "event_version": MODEL_EVENT_VERSION,
        "candidate_id": str(candidate_id),
        "event_type": event_type,
        "occurred_at": str(occurred_at),
        "payload": dict(payload),
    }
    fingerprint = _fingerprint(wrapper)
    event_id = fingerprint
    initialize_model_registry(path)
    with _connect(Path(path)) as connection:
        if connection.execute(
            "SELECT 1 FROM model_candidates WHERE candidate_id = ?", (str(candidate_id),)
        ).fetchone() is None:
            raise ValueError("Modellkandidat existiert nicht.")
        existing = connection.execute(
            "SELECT event_fingerprint FROM model_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if existing is not None:
            return {"event_id": event_id, "inserted": False}
        connection.execute(
            "INSERT INTO model_events (event_id, candidate_id, event_type, occurred_at, payload_json, event_fingerprint) VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, str(candidate_id), event_type, str(occurred_at), _canonical_json(wrapper), fingerprint),
        )
    return {"event_id": event_id, "inserted": True}


def load_model_candidates(path: Path = DEFAULT_MODEL_REGISTRY_PATH) -> list[dict]:
    initialize_model_registry(path)
    with _connect(Path(path)) as connection:
        candidates = connection.execute(
            "SELECT candidate_id, snapshot_json FROM model_candidates ORDER BY registered_at, candidate_id"
        ).fetchall()
        events = connection.execute(
            "SELECT candidate_id, event_type, occurred_at, payload_json FROM model_events ORDER BY occurred_at, event_id"
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in events:
        wrapper = json.loads(row["payload_json"])
        grouped.setdefault(str(row["candidate_id"]), []).append(
            {
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "payload": dict(wrapper.get("payload") or {}),
            }
        )
    return [
        {
            "candidate_id": str(row["candidate_id"]),
            "snapshot": json.loads(row["snapshot_json"]),
            "events": grouped.get(str(row["candidate_id"]), []),
        }
        for row in candidates
    ]


def assess_model_promotion(candidate: dict) -> dict:
    events = list(candidate.get("events") or [])
    shadow_indices = [index for index, event in enumerate(events) if event["event_type"] == "shadow_evaluated"]
    shadow_index = shadow_indices[-1] if shadow_indices else -1
    shadow = events[shadow_index] if shadow_index >= 0 else None
    approval_indices = [
        index for index, event in enumerate(events) if event["event_type"] == "manual_review_approved"
    ]
    approval_index = next((index for index in approval_indices if index > shadow_index), -1)
    canary_index = next(
        (
            index
            for index, event in enumerate(events)
            if index > approval_index
            and event["event_type"] == "canary_verified"
            and bool((event.get("payload") or {}).get("passed"))
        ),
        -1,
    )
    rollback_index = next(
        (
            index
            for index, event in enumerate(events)
            if index > approval_index
            and event["event_type"] == "rollback_verified"
            and bool((event.get("payload") or {}).get("passed"))
        ),
        -1,
    )
    shadow_payload = dict((shadow or {}).get("payload") or {})
    checks = {
        "unseen_windows": int(shadow_payload.get("unseen_windows") or 0) >= 3,
        "evaluation_cases": int(shadow_payload.get("evaluation_cases") or 0) >= 1_000,
        "observation_weeks": int(shadow_payload.get("observation_weeks") or 0) >= 12,
        "brier_improvement": float(shadow_payload.get("brier_improvement") or 0) > 0,
        "log_loss_improvement": float(shadow_payload.get("log_loss_improvement") or 0) > 0,
        "no_material_drawdown_regression": float(shadow_payload.get("max_drawdown_delta") or 999) <= 0,
        "segment_breadth": int(shadow_payload.get("segments_passed") or 0) >= 3,
        "manual_review": approval_index > shadow_index >= 0,
        "canary_verified": canary_index > approval_index >= 0,
        "rollback_verified": rollback_index > approval_index >= 0,
        "gate_sequence_valid": shadow_index >= 0 and approval_index > shadow_index and canary_index > approval_index and rollback_index > approval_index,
        "not_rejected": not any(event["event_type"] == "manual_review_rejected" for event in events),
    }
    return {
        "policy_version": MODEL_PROMOTION_POLICY_VERSION,
        "checks": checks,
        "all_gates_passed": all(checks.values()),
        "automatic_activation_performed": False,
        "manual_activation_still_required": True,
        "production_activation_allowed_by_this_function": False,
    }


def model_registry_audit(path: Path = DEFAULT_MODEL_REGISTRY_PATH) -> dict:
    initialize_model_registry(path)
    invalid: list[str] = []
    with _connect(Path(path)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        candidates = connection.execute(
            "SELECT candidate_id, snapshot_json, snapshot_fingerprint FROM model_candidates"
        ).fetchall()
        events = connection.execute("SELECT event_id, payload_json, event_fingerprint FROM model_events").fetchall()
    for row in candidates:
        try:
            if _fingerprint(json.loads(row["snapshot_json"])) != row["snapshot_fingerprint"]:
                invalid.append(f"candidate:{row['candidate_id']}")
        except Exception:
            invalid.append(f"candidate:{row['candidate_id']}:json")
    for row in events:
        try:
            if _fingerprint(json.loads(row["payload_json"])) != row["event_fingerprint"]:
                invalid.append(f"event:{row['event_id']}")
        except Exception:
            invalid.append(f"event:{row['event_id']}:json")
    return {
        "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
        "quick_check": quick_check,
        "candidates": len(candidates),
        "events": len(events),
        "invalid": invalid,
        "status": "ok" if quick_check == "ok" and not invalid else "attention",
        "automatic_production_activation": False,
    }
