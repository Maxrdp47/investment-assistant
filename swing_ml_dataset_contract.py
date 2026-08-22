from __future__ import annotations

"""Point-in-time dataset contract for later, strictly shadow-only Swing ML research."""

import hashlib
import json
import math
from datetime import datetime
from typing import Mapping, Sequence


SWING_ML_DATASET_SCHEMA_VERSION = "swing-ml-dataset-schema-2026.08.22-v1"
SWING_BROAD_ML_FEATURE_SCHEMA_VERSION = "swing-ml-broad-research-frozen-first-pass-2026.08.22-v3"
FORBIDDEN_FEATURE_NAMES = {
    "result_r",
    "result_pct",
    "forward_return",
    "forward_returns",
    "mfe",
    "mfe_r",
    "mae",
    "mae_r",
    "paper_exit_original",
    "terminal_event",
}


class SwingMLDatasetContractError(ValueError):
    """The proposed row would violate feature/label or point-in-time separation."""


def _timestamp(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _clean_feature_value(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _clean_feature_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_feature_value(item) for item in value]
    return value


def _forbidden_feature_paths(value: object, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            path = f"{prefix}.{key}" if prefix else str(key)
            if normalized in FORBIDDEN_FEATURE_NAMES:
                paths.append(path)
            paths.extend(_forbidden_feature_paths(item, path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            paths.extend(_forbidden_feature_paths(item, f"{prefix}[{index}]"))
    return paths


def _terminal_payload(case: Mapping[str, object]) -> tuple[str | None, dict]:
    terminal_types = {
        "target_1_reached",
        "target_2_reached",
        "stop_reached",
        "ambiguous_sequence",
        "entry_missed",
        "invalidated_before_entry",
        "expired_without_entry",
        "not_evaluable",
    }
    for event in reversed(list(case.get("events") or [])):
        item = dict(event or {})
        payload = dict(item.get("payload") or {})
        event_type = str(item.get("event_type") or "")
        if event_type in terminal_types and (
            event_type != "target_1_reached" or payload.get("terminal", True)
        ):
            return event_type, payload
    return None, {}


def _validate_sources(feature_at: datetime, sources: Sequence[Mapping[str, object]]) -> list[dict]:
    normalized: list[dict] = []
    for source in sources:
        item = {str(key): _clean_feature_value(value) for key, value in dict(source).items()}
        available_at = _timestamp(item.get("available_at") or item.get("published_at"))
        if available_at is None:
            raise SwingMLDatasetContractError(
                "Jede externe Featurequelle benötigt einen belastbaren Verfügbarkeitszeitpunkt."
            )
        comparable_feature = feature_at
        if available_at.tzinfo is None and comparable_feature.tzinfo is not None:
            comparable_feature = comparable_feature.replace(tzinfo=None)
        elif available_at.tzinfo is not None and comparable_feature.tzinfo is None:
            available_at = available_at.replace(tzinfo=None)
        if available_at > comparable_feature:
            raise SwingMLDatasetContractError(
                "Eine erst nach dem Featurezeitpunkt verfügbare Quelle darf nicht in Features gelangen."
            )
        item["available_at"] = available_at.isoformat()
        normalized.append(item)
    return normalized


def build_swing_ml_dataset_row(
    case: Mapping[str, object],
    *,
    additional_features: Mapping[str, object] | None = None,
    feature_sources: Sequence[Mapping[str, object]] = (),
) -> dict:
    """Create one immutable candidate row; it has no model or trading side effects."""
    case_id = str(case.get("case_id") or "").strip()
    feature_at = _timestamp(case.get("signal_at"))
    if not case_id or feature_at is None:
        raise SwingMLDatasetContractError("Fall-ID und gültiger Featurezeitpunkt sind Pflicht.")
    snapshot = dict(case.get("snapshot") or {})
    asset = dict(snapshot.get("asset") or {})
    strategy = dict(snapshot.get("strategy") or {})
    stored_features = dict(snapshot.get("signal_features") or {})
    observational = dict(case.get("observational_features") or {})
    observational_values = dict(observational.get("values") or {})
    extras = dict(additional_features or {})
    forbidden = sorted(
        key for key in extras if str(key).strip().lower() in FORBIDDEN_FEATURE_NAMES
    )
    if forbidden:
        raise SwingMLDatasetContractError(
            f"Zielvariablen sind im Featurebereich verboten: {', '.join(forbidden)}"
        )
    features = {
        **{str(key): _clean_feature_value(value) for key, value in stored_features.items()},
        **{str(key): _clean_feature_value(value) for key, value in observational_values.items()},
        **{str(key): _clean_feature_value(value) for key, value in extras.items()},
    }
    terminal_event, terminal_payload = _terminal_payload(case)
    labels = {
        "result_r": _clean_feature_value(
            case.get("result_r")
            if case.get("result_r") is not None
            else terminal_payload.get("result_r")
        ),
        "result_pct": _clean_feature_value(
            case.get("result_pct")
            if case.get("result_pct") is not None
            else terminal_payload.get("result_pct")
        ),
        "mfe_pct": _clean_feature_value(terminal_payload.get("maximum_favorable_excursion_pct")),
        "mae_pct": _clean_feature_value(terminal_payload.get("maximum_adverse_excursion_pct")),
        "terminal_event": terminal_event,
    }
    row = {
        "schema_version": SWING_ML_DATASET_SCHEMA_VERSION,
        "case_id": case_id,
        "logical_case_id": str(case.get("logical_case_id") or case.get("evidence_key") or case_id),
        "feature_at": feature_at.isoformat(),
        "identity": {
            "asset": str(case.get("symbol") or asset.get("ticker") or ""),
            "issuer_id": str(
                (case.get("research_identity") or {}).get("issuer_id")
                or asset.get("issuer_id")
                or ""
            ),
            "listing_id": str(
                (case.get("research_identity") or {}).get("listing_id")
                or asset.get("listing_id")
                or ""
            ),
            "asset_type": str(asset.get("asset_type") or "Unbekannt"),
            "region": str(asset.get("region") or "Unbekannt"),
        },
        "strategy": {
            "strategy_version": str(strategy.get("strategy_version") or "Unbekannt"),
            "engine_version": str(strategy.get("engine_version") or case.get("case_version") or "Unbekannt"),
            "setup_type": str(strategy.get("setup_type") or "Unbekannt"),
        },
        "features": features,
        "feature_missing": sorted(key for key, value in features.items() if value is None),
        "feature_sources": _validate_sources(feature_at, feature_sources),
        "labels": labels,
        "research_split": str(case.get("research_split") or "Unbekannt"),
        "dataset_revision": str(case.get("case_data_fingerprint") or "Unbekannt"),
        "shadow_only": True,
        "random_split_allowed": False,
        "automatic_trade_effect": False,
        "automatic_rule_change": False,
    }
    row["row_fingerprint"] = _fingerprint(row)
    return row


def build_broad_research_ml_row(
    candidate: Mapping[str, object],
    *,
    labels: Mapping[str, object] | None = None,
) -> dict:
    """Adapt one broad candidate without training, filtering or opening Holdout."""
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    feature = dict(candidate.get("feature") or {})
    feature_at = _timestamp(feature.get("feature_at"))
    feature_fingerprint = str(feature.get("feature_fingerprint") or "")
    comparable_feature = dict(feature)
    comparable_feature.pop("feature_fingerprint", None)
    if (
        not candidate_id
        or feature_at is None
        or not feature_fingerprint
        or feature_fingerprint != _fingerprint(comparable_feature)
    ):
        raise SwingMLDatasetContractError(
            "Broad-Research-Kandidat benötigt ein gültiges unverändertes Feature-Artefakt."
        )
    forbidden_paths = _forbidden_feature_paths(feature)
    if forbidden_paths:
        raise SwingMLDatasetContractError(
            "Zielvariablen sind im Featurebereich verboten: " + ", ".join(forbidden_paths)
        )
    cot = dict(feature.get("cot") or {})
    if cot.get("status") == "available":
        available_at = _timestamp(cot.get("available_at"))
        if available_at is None:
            raise SwingMLDatasetContractError(
                "Verfügbarer COT-Kontext benötigt einen Veröffentlichungszeitpunkt."
            )
        comparable = feature_at
        if available_at.tzinfo is None and comparable.tzinfo is not None:
            comparable = comparable.replace(tzinfo=None)
        elif available_at.tzinfo is not None and comparable.tzinfo is None:
            available_at = available_at.replace(tzinfo=None)
        if available_at > comparable:
            raise SwingMLDatasetContractError(
                "COT-Daten nach dem Featurezeitpunkt sind im ML-Datensatz verboten."
            )
    label_payload = _clean_feature_value(dict(labels or {}))
    row = {
        "schema_version": SWING_ML_DATASET_SCHEMA_VERSION,
        "feature_schema_version": SWING_BROAD_ML_FEATURE_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "feature_at": feature_at.isoformat(),
        "identity": _clean_feature_value(feature.get("identity") or {}),
        "direction": str(
            candidate.get("direction") or feature.get("research_direction") or "long"
        ).lower(),
        "setup_family": str(candidate.get("setup_family") or feature.get("setup_family") or ""),
        "research_split": str(candidate.get("research_split") or "Unbekannt"),
        "dataset_fingerprint": str(candidate.get("dataset_fingerprint") or feature.get("dataset_fingerprint") or ""),
        "feature_fingerprint": feature_fingerprint,
        "features": _clean_feature_value(feature),
        "labels": label_payload,
        "feature_missing": list(feature.get("feature_missing") or []),
        "split_policy": "time_based_purged_walk_forward_only",
        "development_pattern_discovery_only": True,
        "random_split_allowed": False,
        "model_training_performed": False,
        "automatic_feature_selection": False,
        "shadow_only": True,
        "automatic_trade_effect": False,
        "automatic_rule_change": False,
        "production_activation_allowed": False,
    }
    row["row_fingerprint"] = _fingerprint(row)
    return row


def swing_ml_dataset_manifest(rows: Sequence[Mapping[str, object]]) -> dict:
    fingerprints = [str(row.get("row_fingerprint") or "") for row in rows]
    if not fingerprints or any(not value for value in fingerprints):
        raise SwingMLDatasetContractError("Ein Dataset benötigt fingerprintete Zeilen.")
    return {
        "schema_version": SWING_ML_DATASET_SCHEMA_VERSION,
        "feature_schema_versions": sorted(
            {
                str(row.get("feature_schema_version") or SWING_ML_DATASET_SCHEMA_VERSION)
                for row in rows
            }
        ),
        "rows": len(rows),
        "row_fingerprints": fingerprints,
        "dataset_fingerprint": _fingerprint(fingerprints),
        "split_policy": "time_based_purged_walk_forward_only",
        "random_split_allowed": False,
        "shadow_only": True,
        "production_activation_allowed": False,
    }
