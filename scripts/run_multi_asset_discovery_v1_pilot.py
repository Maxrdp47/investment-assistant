from __future__ import annotations

"""Freeze and run the small Multi-Asset Discovery v1 integrity pilot only."""

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fx_carry_pit import default_fx_pair_contracts, normalize_fx_ohlc  # noqa: E402
from historical_dependency_policy import (  # noqa: E402
    build_historical_dependency_policy,
    classify_historical_dependency,
)
from multi_asset_discovery_v1 import (  # noqa: E402
    build_contract_freeze,
    build_feature_snapshot,
    build_outcome,
    canonical_json,
    checkpoint_pilot_stores,
    evaluate_integrity_pilot,
    file_sha256,
    fingerprint,
    load_discovery_contract,
    record_freeze_and_features,
    record_outcomes_and_dependency,
    temporal_dependency_report,
    audit_pilot_stores,
)
from swing_research_identity_v3 import resolve_research_identity_v3  # noqa: E402


DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)
DEFAULT_IDENTITY_STORE = PROJECT_ROOT / "runtime" / "research_identity_registry.sqlite3"
DEFAULT_FX_STORE = (
    PROJECT_ROOT / "runtime" / "fx_historical_pit_2026-09-01-v2.sqlite3"
)
DEFAULT_FEATURE_STORE = (
    PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_pilot_v2_features.sqlite3"
)
DEFAULT_OUTCOME_STORE = (
    PROJECT_ROOT / "runtime" / "multi_asset_discovery_v1_pilot_v2_outcomes.sqlite3"
)
DEFAULT_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "research_exports"
DEFAULT_FREEZE_OUTPUT = (
    DEFAULT_EXPORT_ROOT
    / "multi_asset_discovery_v1_contract_freeze_2026-09-01-v1-implementation-r5.json"
)
DEFAULT_PILOT_OUTPUT = (
    DEFAULT_EXPORT_ROOT
    / "multi_asset_discovery_v1_integrity_pilot_2026-09-01-v1-authoritative-r5.json"
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=PROJECT_ROOT, text=True, encoding="utf-8"
    ).strip()


def _load_latest_identity_registry(path: Path) -> dict[str, object]:
    uri = f"file:{Path(path).as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute(
            "SELECT registry_json FROM registry_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise RuntimeError("Identity-Registry ist leer.")
    return json.loads(str(row[0]))


def _load_manifest(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _modern_history(
    manifest: Mapping[str, object], manifest_path: Path, symbol: str
) -> tuple[pd.DataFrame, dict[str, object]]:
    selected = None
    for raw_scope in (manifest.get("scopes") or {}).values():
        scope = dict(raw_scope)
        contract = dict(scope.get("contract") or {})
        asset = dict((scope.get("assets") or {}).get(symbol) or {})
        if contract.get("start") == "2016-01-01" and asset.get("status") == "available":
            selected = asset
            break
    if selected is None:
        raise RuntimeError(f"Keine moderne Frozen-Historie für {symbol}.")
    file_path = manifest_path.parent / str(selected["file"])
    return pd.read_parquet(file_path), selected


def _load_fx_histories(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, str]], str]:
    uri = f"file:{Path(path).as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT record_json FROM historical_fx_records "
            "WHERE feature='PRICE' AND pit_eligible=1 ORDER BY pair_id, observation_date"
        ).fetchall()
        version_row = connection.execute(
            "SELECT dataset_fingerprint FROM fx_dataset_versions "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    if version_row is None:
        raise RuntimeError("FX-v2-Store besitzt keinen Dataset-Fingerprint.")
    contracts = default_fx_pair_contracts()
    values: dict[str, list[dict[str, object]]] = {pair: [] for pair in contracts}
    availability: dict[str, dict[str, str]] = {pair: {} for pair in contracts}
    for row in rows:
        record = json.loads(str(row[0]))
        pair = str(record.get("pair_id") or "")
        if pair not in contracts:
            continue
        normalized = normalize_fx_ohlc(contracts[pair], dict(record["metadata"]["ohlc"]))
        observation_day = str(record["observation_date"])
        values[pair].append({"Date": observation_day, **{key.title(): value for key, value in normalized.items()}})
        availability[pair][observation_day] = str(record["available_at"])
    frames = {
        pair: pd.DataFrame(items).set_index("Date")
        for pair, items in values.items()
        if items
    }
    return frames, availability, str(version_row[0])


def _resolve_asset(
    symbol: str,
    asset_class: str,
    registry: Mapping[str, object],
    *,
    as_of: str,
    dependency_policy: Mapping[str, object],
) -> dict[str, object]:
    resolved = resolve_research_identity_v3(
        {
            "ticker": symbol,
            "mic": "US-CONSOLIDATED",
            "asset_class": "KRYPTO" if asset_class == "CRYPTO" else asset_class,
            "first_seen_at": "2026-08-31T00:00:00+00:00",
            "imported_at": "2026-08-31T00:00:00+00:00",
        },
        registry=registry,
        as_of=None,
    )
    historical = classify_historical_dependency(
        resolved, as_of=as_of, policy=dependency_policy
    )
    mapping_status = str(resolved.get("mapping_status") or "UNRESOLVED").upper()
    issuer_id = historical.get("issuer_id")
    return {
        "ticker": symbol,
        "asset_id": resolved.get("asset_id") or symbol,
        "asset_class": asset_class,
        "listing_id": resolved.get("listing_id"),
        "issuer_id": issuer_id,
        "mapping_status": mapping_status,
        "dependency_status": historical["dependency_status"],
        "historical_dependency_policy_version": historical[
            "historical_dependency_policy_version"
        ],
        "historical_dependency_policy_fingerprint": historical[
            "historical_dependency_policy_fingerprint"
        ],
        "historical_dependency_reason": historical["historical_dependency_reason"],
        "pit_trading_feature": False,
    }


def _fx_asset(pair: str) -> dict[str, object]:
    return {
        "pair_id": pair,
        "asset_id": f"fx-pair:{pair.replace('/', '-').lower()}",
        "asset_class": "FX",
        "listing_id": f"fx-listing:{pair.replace('/', '-').lower()}",
        "issuer_id": None,
        "mapping_status": "UNRESOLVED",
        "dependency_status": "UNKNOWN",
    }


def _position(frame: pd.DataFrame, day: str) -> int:
    index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    matches = [index_position for index_position, stamp in enumerate(index) if stamp == pd.Timestamp(day)]
    if len(matches) != 1:
        raise RuntimeError(f"Pilot-Tag {day} fehlt oder ist nicht eindeutig.")
    return matches[0]


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_json(existing) != canonical_json(payload):
            raise RuntimeError(f"Append-only-Artefakt weicht ab: {path}")
        return
    path.write_text(encoded, encoding="utf-8")


def _build_cases(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path,
    registry: Mapping[str, object],
    fx_frames: Mapping[str, pd.DataFrame],
    fx_availability: Mapping[str, Mapping[str, str]],
    fx_dataset_fingerprint: str,
    dependency_policy: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, pd.DataFrame]]:
    contract = load_discovery_contract()
    pilot = dict(contract["pilot_contract"])
    normal_day = str(pilot["fixed_decision_day"])
    features: list[dict[str, object]] = []
    frames_by_case: dict[str, pd.DataFrame] = {}
    dataset_fingerprint = str(manifest["dataset_fingerprint"])
    for asset_class, key in (("EQUITIES", "equities"), ("ETF", "etf"), ("CRYPTO", "crypto")):
        for symbol in pilot[key]:
            frame, source = _modern_history(manifest, manifest_path, str(symbol))
            asset = _resolve_asset(
                str(symbol),
                asset_class,
                registry,
                as_of=normal_day,
                dependency_policy=dependency_policy,
            )
            decision_time = f"{normal_day}T23:59:59+00:00"
            feature = build_feature_snapshot(
                asset=asset,
                frame=frame,
                decision_position=_position(frame, normal_day),
                decision_time=decision_time,
                dataset_fingerprint=f"{dataset_fingerprint}:{source['history_fingerprint']}",
            )
            features.append(feature)
            frames_by_case[str(feature["case_id"])] = frame
    for pair in pilot["fx"]:
        frame = fx_frames[str(pair)]
        decision_time = str(fx_availability[str(pair)][normal_day])
        feature = build_feature_snapshot(
            asset=_fx_asset(str(pair)),
            frame=frame,
            decision_position=_position(frame, normal_day),
            decision_time=decision_time,
            dataset_fingerprint=f"fx-historical-pit:{fx_dataset_fingerprint}",
        )
        features.append(feature)
        frames_by_case[str(feature["case_id"])] = frame
    boundary_day = str(pilot["boundary_censoring_decision_day"])
    symbol = str(pilot["extra_boundary_case"])
    frame, source = _modern_history(manifest, manifest_path, symbol)
    boundary = build_feature_snapshot(
        asset=_resolve_asset(
            symbol,
            "EQUITIES",
            registry,
            as_of=boundary_day,
            dependency_policy=dependency_policy,
        ),
        frame=frame,
        decision_position=_position(frame, boundary_day),
        decision_time=f"{boundary_day}T23:59:59+00:00",
        dataset_fingerprint=f"{dataset_fingerprint}:{source['history_fingerprint']}",
    )
    features.append(boundary)
    frames_by_case[str(boundary["case_id"])] = frame
    return features, frames_by_case


def run(args: argparse.Namespace) -> dict[str, object]:
    started_at = datetime.now(timezone.utc).isoformat()
    output_path = Path(args.output)
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        if existing.get("code_fingerprint") != __import__(
            "multi_asset_discovery_v1"
        ).code_fingerprint():
            raise RuntimeError("Vorhandener Pilot gehört zu einem anderen Code-Fingerprint.")
        return existing
    contract = load_discovery_contract()
    if contract["candidate_generation"]["full_development_scan_allowed"] is not False:
        raise RuntimeError("Der große Development-Scan ist nicht gesperrt.")
    manifest_path = Path(args.manifest)
    identity_path = Path(args.identity_store)
    fx_path = Path(args.fx_store)
    manifest = _load_manifest(manifest_path)
    registry = _load_latest_identity_registry(identity_path)
    dependency_policy = build_historical_dependency_policy()
    fx_frames, fx_availability, fx_dataset_fingerprint = _load_fx_histories(fx_path)
    source_snapshots = {
        "dataset_fingerprint": manifest["dataset_fingerprint"],
        "dataset_manifest_sha256": file_sha256(manifest_path),
        "identity_registry_fingerprint": registry["registry_fingerprint"],
        "identity_store_sha256": file_sha256(identity_path),
        "fx_store_sha256": file_sha256(fx_path),
        "fx_dataset_fingerprint": fx_dataset_fingerprint,
        "historical_dependency_policy_fingerprint": dependency_policy[
            "policy_fingerprint"
        ],
        "protected_sources_opened_read_only": True,
        "protected_sources_modified": False,
    }
    freeze_path = Path(args.freeze_output)
    if freeze_path.exists():
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        expected = build_contract_freeze(
            source_snapshots=source_snapshots,
            git_branch=_git("branch", "--show-current"),
            git_commit=_git("rev-parse", "HEAD"),
            frozen_at=str(freeze["frozen_at"]),
        )
        if canonical_json(freeze) != canonical_json(expected):
            raise RuntimeError("Vorhandener Freeze weicht vom aktuellen Vertrag oder Code ab.")
    else:
        freeze = build_contract_freeze(
            source_snapshots=source_snapshots,
            git_branch=_git("branch", "--show-current"),
            git_commit=_git("rev-parse", "HEAD"),
            frozen_at=str(args.frozen_at or started_at),
        )
        _write_immutable(freeze_path, freeze)
    features, frames_by_case = _build_cases(
        manifest=manifest,
        manifest_path=manifest_path,
        registry=registry,
        fx_frames=fx_frames,
        fx_availability=fx_availability,
        fx_dataset_fingerprint=fx_dataset_fingerprint,
        dependency_policy=dependency_policy,
    )
    outcomes = [
        build_outcome(feature_snapshot=feature, frame=frames_by_case[str(feature["case_id"])])
        for feature in features
    ]
    replay_features, replay_frames = _build_cases(
        manifest=manifest,
        manifest_path=manifest_path,
        registry=registry,
        fx_frames=fx_frames,
        fx_availability=fx_availability,
        fx_dataset_fingerprint=fx_dataset_fingerprint,
        dependency_policy=dependency_policy,
    )
    replay_outcomes = [
        build_outcome(feature_snapshot=feature, frame=replay_frames[str(feature["case_id"])])
        for feature in replay_features
    ]
    deterministic_replay_match = (
        [item["feature_fingerprint"] for item in features]
        == [item["feature_fingerprint"] for item in replay_features]
        and [item.get("outcome_fingerprint") for item in outcomes]
        == [item.get("outcome_fingerprint") for item in replay_outcomes]
    )
    dependency = temporal_dependency_report(outcomes)
    feature_record = record_freeze_and_features(freeze, features, path=Path(args.feature_store))
    outcome_record = record_outcomes_and_dependency(outcomes, dependency, path=Path(args.outcome_store))
    checkpoint = checkpoint_pilot_stores(
        feature_path=Path(args.feature_store), outcome_path=Path(args.outcome_store)
    )
    store_audit = audit_pilot_stores(
        feature_path=Path(args.feature_store), outcome_path=Path(args.outcome_store)
    )
    result = evaluate_integrity_pilot(
        freeze=freeze,
        features=features,
        outcomes=outcomes,
        dependency=dependency,
        store_audit=store_audit,
        deterministic_replay_match=deterministic_replay_match,
    )
    result.update(
        {
            "run_id": f"mad1-pilot-{fingerprint([freeze['freeze_fingerprint'], started_at])[:24]}",
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "command": "scripts/run_multi_asset_discovery_v1_pilot.py",
            "git": freeze["git"],
            "freeze_fingerprint": freeze["freeze_fingerprint"],
            "contract_fingerprint": freeze["contract_fingerprint"],
            "code_fingerprint": freeze["code_fingerprint"],
            "feature_contract_fingerprint": freeze["feature_contract_fingerprint"],
            "outcome_contract_fingerprint": freeze["outcome_contract_fingerprint"],
            "dataset_fingerprint": freeze["dataset_fingerprint"],
            "identity_contract_fingerprint": freeze["identity_contract_fingerprint"],
            "dependency_contract_fingerprint": freeze["dependency_contract_fingerprint"],
            "stage_split_fingerprint": freeze["stage_split_fingerprint"],
            "safe_zone_fingerprint": freeze["safe_zone_fingerprint"],
            "event_pit_availability_fingerprint": freeze["event_pit_availability_fingerprint"],
            "fx_dataset_fingerprint": fx_dataset_fingerprint,
            "historical_dependency_policy_version": dependency_policy["version"],
            "historical_dependency_policy_fingerprint": dependency_policy[
                "policy_fingerprint"
            ],
            "feature_store_record": feature_record,
            "outcome_store_record": outcome_record,
            "sqlite_checkpoint": checkpoint,
            "outputs": {
                "freeze": str(Path(args.freeze_output).resolve()),
                "pilot": str(Path(args.output).resolve()),
                "feature_store": str(Path(args.feature_store).resolve()),
                "outcome_store": str(Path(args.outcome_store).resolve()),
            },
            "case_digest": fingerprint(
                {
                    "features": [item["feature_fingerprint"] for item in features],
                    "outcomes": [item.get("outcome_fingerprint") for item in outcomes],
                }
            ),
        }
    )
    result.pop("pilot_fingerprint", None)
    result["pilot_fingerprint"] = fingerprint(result)
    _write_immutable(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--identity-store", type=Path, default=DEFAULT_IDENTITY_STORE)
    parser.add_argument("--fx-store", type=Path, default=DEFAULT_FX_STORE)
    parser.add_argument("--feature-store", type=Path, default=DEFAULT_FEATURE_STORE)
    parser.add_argument("--outcome-store", type=Path, default=DEFAULT_OUTCOME_STORE)
    parser.add_argument("--freeze-output", type=Path, default=DEFAULT_FREEZE_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_PILOT_OUTPUT)
    parser.add_argument("--frozen-at")
    return parser.parse_args()


if __name__ == "__main__":
    payload = run(parse_args())
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
