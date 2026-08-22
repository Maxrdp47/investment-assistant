from __future__ import annotations

"""Immutable gate for a genuinely unseen Swing asset universe.

Universe selection is frozen before strategy results may be attached.  The gate
excludes original tickers, issuers and known economically identical instruments
and never downloads assets or activates a strategy by itself.
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Mapping, Sequence

from swing_research_identity import derive_swing_research_identity


EXTERNAL_UNIVERSE_SCHEMA_VERSION = 1
EXTERNAL_UNIVERSE_CONTRACT_VERSION = "swing-external-unseen-universe-2026.08.22-v1"
DEFAULT_EXTERNAL_UNIVERSE_DB_PATH = (
    Path(__file__).resolve().parent / "runtime" / "swing_external_universes.sqlite3"
)
FORBIDDEN_RESULT_FIELDS = {
    "result",
    "result_r",
    "forward_return",
    "mfe",
    "mae",
    "profit_factor",
    "hit_rate",
    "strategy_performance",
}


class ExternalUniverseContractError(ValueError):
    """The proposed external universe is not genuinely unseen or outcome-blind."""


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_external_universe_store(
    path: Path = DEFAULT_EXTERNAL_UNIVERSE_DB_PATH,
) -> None:
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS external_universe_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS external_universe_manifests (
                universe_version TEXT PRIMARY KEY,
                frozen_at TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                manifest_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS external_universe_results (
                result_id TEXT PRIMARY KEY,
                universe_version TEXT NOT NULL REFERENCES external_universe_manifests(universe_version),
                strategy_version TEXT NOT NULL,
                result_json TEXT NOT NULL,
                result_fingerprint TEXT NOT NULL,
                UNIQUE(universe_version, strategy_version)
            );
            CREATE TRIGGER IF NOT EXISTS external_universe_manifests_no_update
            BEFORE UPDATE ON external_universe_manifests BEGIN
                SELECT RAISE(ABORT, 'external_universe_manifests is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS external_universe_manifests_no_delete
            BEFORE DELETE ON external_universe_manifests BEGIN
                SELECT RAISE(ABORT, 'external_universe_manifests is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS external_universe_results_no_update
            BEFORE UPDATE ON external_universe_results BEGIN
                SELECT RAISE(ABORT, 'external_universe_results is append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS external_universe_results_no_delete
            BEFORE DELETE ON external_universe_results BEGIN
                SELECT RAISE(ABORT, 'external_universe_results is append-only');
            END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM external_universe_meta WHERE key='schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO external_universe_meta VALUES('schema_version', ?)",
                (str(EXTERNAL_UNIVERSE_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != EXTERNAL_UNIVERSE_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstützte External-Universe-Schemaversion.")


def _contains_result_data(asset: Mapping[str, object]) -> bool:
    return any(str(key).strip().lower() in FORBIDDEN_RESULT_FIELDS for key in asset)


def build_external_universe_manifest(
    original_assets: Sequence[Mapping[str, object]],
    proposed_assets: Sequence[Mapping[str, object]],
    *,
    source_contract: Mapping[str, object],
    frozen_at: str,
) -> dict[str, object]:
    """Build an outcome-blind manifest; no strategy result is accepted as input."""
    if not str(frozen_at).strip():
        raise ExternalUniverseContractError("Der Auswahl-Freeze benötigt einen Zeitstempel.")
    if not source_contract or source_contract.get("selection_before_results") is not True:
        raise ExternalUniverseContractError(
            "Die External-Universe-Auswahl muss ausdrücklich vor Ergebnissichtung erfolgen."
        )
    original_identities = [derive_swing_research_identity(asset) for asset in original_assets]
    original_tickers = {str(item["ticker"]) for item in original_identities}
    original_issuers = {str(item["issuer_id"]) for item in original_identities}
    original_instruments = {
        str(item["economic_instrument_id"])
        for item in original_identities
        if item.get("economic_instrument_id")
    }
    accepted: list[dict] = []
    rejected: list[dict] = []
    seen_listings: set[str] = set()
    seen_issuers: set[str] = set()
    for raw in proposed_assets:
        asset = dict(raw)
        if _contains_result_data(asset):
            raise ExternalUniverseContractError(
                "Strategieergebnisse dürfen die External-Universe-Auswahl nicht beeinflussen."
            )
        identity = derive_swing_research_identity(asset)
        reasons = []
        if identity["ticker"] in original_tickers:
            reasons.append("ticker_in_original_universe")
        if identity["issuer_id"] in original_issuers:
            reasons.append("issuer_in_original_universe")
        if (
            identity.get("economic_instrument_id")
            and identity["economic_instrument_id"] in original_instruments
        ):
            reasons.append("economic_instrument_in_original_universe")
        if identity["listing_id"] in seen_listings:
            reasons.append("duplicate_external_listing")
        if identity["issuer_id"] in seen_issuers:
            reasons.append("dependent_external_issuer")
        if identity.get("identity_confidence") == "listing_only":
            reasons.append("issuer_dependency_unknown")
        required = {
            "ticker": identity.get("ticker"),
            "asset_type": asset.get("asset_type"),
            "region": asset.get("region"),
            "liquidity_class": asset.get("liquidity_class"),
        }
        if any(not str(value or "").strip() for value in required.values()):
            reasons.append("missing_quality_or_identity_metadata")
        if reasons:
            rejected.append({"ticker": identity.get("ticker"), "reasons": sorted(set(reasons))})
            continue
        accepted.append(
            {
                "ticker": identity["ticker"],
                "name": asset.get("name"),
                "asset_type": asset.get("asset_type"),
                "region": asset.get("region"),
                "category": asset.get("category"),
                "liquidity_class": asset.get("liquidity_class"),
                "listing_id": identity["listing_id"],
                "issuer_id": identity["issuer_id"],
                "economic_instrument_id": identity.get("economic_instrument_id"),
                "identity_confidence": identity.get("identity_confidence"),
            }
        )
        seen_listings.add(str(identity["listing_id"]))
        seen_issuers.add(str(identity["issuer_id"]))
    accepted.sort(key=lambda item: (str(item["ticker"]), str(item["listing_id"])))
    manifest = {
        "contract_version": EXTERNAL_UNIVERSE_CONTRACT_VERSION,
        "frozen_at": str(frozen_at),
        "source_contract": dict(source_contract),
        "original_universe_assets": len(original_assets),
        "proposed_assets": len(proposed_assets),
        "accepted_assets": accepted,
        "accepted_count": len(accepted),
        "rejected": rejected,
        "rejected_count": len(rejected),
        "selection_before_results": True,
        "original_ticker_overlap": 0,
        "original_issuer_overlap": 0,
        "original_economic_instrument_overlap": 0,
        "strategy_results_seen_during_selection": False,
        "parameters_mutable_after_results": False,
        "same_strategy_version_required": True,
        "automatic_production_activation": False,
    }
    fingerprint = _fingerprint(manifest)
    return {
        **manifest,
        "external_universe_fingerprint": fingerprint,
        "universe_version": f"external-unseen-{fingerprint[:24]}",
    }


def freeze_external_universe_manifest(
    manifest: Mapping[str, object],
    path: Path = DEFAULT_EXTERNAL_UNIVERSE_DB_PATH,
) -> dict[str, object]:
    payload = dict(manifest)
    fingerprint = str(payload.get("external_universe_fingerprint") or "")
    version = str(payload.get("universe_version") or "")
    comparable = dict(payload)
    comparable.pop("external_universe_fingerprint", None)
    comparable.pop("universe_version", None)
    if not fingerprint or fingerprint != _fingerprint(comparable) or not version:
        raise ExternalUniverseContractError("External-Universe-Manifest ist nicht reproduzierbar.")
    initialize_external_universe_store(path)
    with _connect(path) as connection:
        existing = connection.execute(
            "SELECT manifest_fingerprint FROM external_universe_manifests WHERE universe_version=?",
            (version,),
        ).fetchone()
        if existing is not None and existing["manifest_fingerprint"] != fingerprint:
            raise ExternalUniverseContractError("Universe-Version ist bereits abweichend belegt.")
        if existing is None:
            connection.execute(
                "INSERT INTO external_universe_manifests VALUES (?, ?, ?, ?)",
                (version, str(payload["frozen_at"]), _json(payload), fingerprint),
            )
    return {"universe_version": version, "fingerprint": fingerprint, "stored": existing is None}


def record_external_universe_result(
    *,
    universe_version: str,
    strategy_version: str,
    metrics: Mapping[str, object],
    challenger_gate: Mapping[str, object],
    path: Path = DEFAULT_EXTERNAL_UNIVERSE_DB_PATH,
) -> dict[str, object]:
    if not str(strategy_version).startswith("swing-"):
        raise ExternalUniverseContractError("External-Test benötigt eine zuvor eingefrorene Strategieversion.")
    gate = dict(challenger_gate or {})
    if (
        gate.get("allowed") is not True
        or str(gate.get("challenger_version") or "") != str(strategy_version)
        or str(gate.get("requested_stage") or "") != "external"
        or str(gate.get("predecessor") or "") != "holdout"
        or str(gate.get("predecessor_decision") or "") != "approved_to_next_stage"
        or gate.get("automatic_production_activation") is not False
    ):
        raise ExternalUniverseContractError(
            "External-Ergebnisse bleiben bis zum bestandenen, manuell geprüften Holdout gesperrt."
        )
    initialize_external_universe_store(path)
    with _connect(path) as connection:
        manifest = connection.execute(
            "SELECT manifest_fingerprint FROM external_universe_manifests WHERE universe_version=?",
            (str(universe_version),),
        ).fetchone()
        if manifest is None:
            raise ExternalUniverseContractError("External-Universe muss vor dem Ergebnis eingefroren sein.")
        payload = {
            "universe_version": str(universe_version),
            "external_universe_fingerprint": str(manifest["manifest_fingerprint"]),
            "strategy_version": str(strategy_version),
            "challenger_gate": gate,
            "metrics": dict(metrics),
            "same_version_may_be_optimized_from_result": False,
            "historical_result_is_true_forward": False,
            "automatic_production_activation": False,
        }
        fingerprint = _fingerprint(payload)
        result_id = f"external-result-{fingerprint[:24]}"
        existing = connection.execute(
            """SELECT result_fingerprint FROM external_universe_results
            WHERE universe_version=? AND strategy_version=?""",
            (str(universe_version), str(strategy_version)),
        ).fetchone()
        if existing is not None and existing["result_fingerprint"] != fingerprint:
            raise ExternalUniverseContractError(
                "Dieselbe Strategie-/Universe-Version darf nach Ergebnissichtung nicht verändert werden."
            )
        if existing is None:
            connection.execute(
                "INSERT INTO external_universe_results VALUES (?, ?, ?, ?, ?)",
                (result_id, str(universe_version), str(strategy_version), _json(payload), fingerprint),
            )
    return {"result_id": result_id, "fingerprint": fingerprint, "stored": existing is None}


def external_universe_store_audit(
    path: Path = DEFAULT_EXTERNAL_UNIVERSE_DB_PATH,
) -> dict[str, object]:
    initialize_external_universe_store(path)
    with _connect(path) as connection:
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        manifests = int(connection.execute("SELECT COUNT(*) FROM external_universe_manifests").fetchone()[0])
        results = int(connection.execute("SELECT COUNT(*) FROM external_universe_results").fetchone()[0])
    return {
        "status": "ok" if quick == "ok" else "invalid",
        "quick_check": quick,
        "manifests": manifests,
        "results": results,
        "append_only": True,
        "outcome_blind_universe_selection": True,
        "automatic_production_activation": False,
    }
