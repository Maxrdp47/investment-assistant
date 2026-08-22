from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


STRATEGY_FREEZE_SCHEMA_VERSION = 1
STRATEGY_FREEZE_CONTRACT_VERSION = "swing-strategy-freeze-2026.08.18-v1"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_STRATEGY_FREEZE_DB_PATH = PROJECT_ROOT / "runtime" / "swing_strategy_freezes.sqlite3"

REQUIRED_DOMAINS = (
    "strategy",
    "parameters",
    "filters",
    "risk_rules",
    "order_logic",
    "position_management",
    "exit_rules",
    "cost_model",
    "data_contract",
)


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


def _file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_project_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_strategy_freeze_artifact(
    *,
    strategy_name: str,
    strategy_family: str,
    strategy_role: str,
    components: Mapping[str, object],
    code_paths: Sequence[Path],
    config_paths: Sequence[Path],
    created_at: str | None = None,
) -> dict:
    """Build an immutable research freeze; no performance result can release it."""
    normalized_components = {str(key): value for key, value in components.items()}
    missing = [domain for domain in REQUIRED_DOMAINS if domain not in normalized_components]
    if missing:
        raise ValueError(f"Strategie-Freeze unvollständig: {', '.join(missing)}")
    code_fingerprints = {
        _relative_project_path(Path(path)): _file_fingerprint(Path(path))
        for path in sorted({Path(item).resolve() for item in code_paths}, key=str)
    }
    config_fingerprints = {
        _relative_project_path(Path(path)): _file_fingerprint(Path(path))
        for path in sorted({Path(item).resolve() for item in config_paths}, key=str)
    }
    component_fingerprints = {
        name: _fingerprint(normalized_components[name]) for name in REQUIRED_DOMAINS
    }
    identity_payload = {
        "freeze_contract_version": STRATEGY_FREEZE_CONTRACT_VERSION,
        "strategy_name": str(strategy_name),
        "strategy_family": str(strategy_family),
        "strategy_role": str(strategy_role),
        "component_fingerprints": component_fingerprints,
        "code_fingerprints": code_fingerprints,
        "config_fingerprints": config_fingerprints,
    }
    artifact_fingerprint = _fingerprint(identity_payload)
    safe_name = "-".join(str(strategy_name).strip().lower().replace("_", "-").split())
    artifact = {
        "freeze_contract_version": STRATEGY_FREEZE_CONTRACT_VERSION,
        "strategy_version": f"{safe_name}-{artifact_fingerprint[:16]}",
        "strategy_name": str(strategy_name),
        "strategy_family": str(strategy_family),
        "strategy_role": str(strategy_role),
        "created_at": str(created_at or datetime.now(timezone.utc).isoformat()),
        "components": normalized_components,
        "component_fingerprints": component_fingerprints,
        "code_fingerprints": code_fingerprints,
        "config_fingerprints": config_fingerprints,
        "code_fingerprint": _fingerprint(code_fingerprints),
        "configuration_fingerprint": _fingerprint(config_fingerprints),
        "data_contract_fingerprint": component_fingerprints["data_contract"],
        "release": {
            "state": (
                "existing_baseline_unchanged"
                if str(strategy_role) == "existing_baseline"
                else "research_frozen_not_released"
            ),
            "approved_from_performance": False,
            "automatic_production_activation": False,
            "broker_execution_allowed": False,
            "manual_future_gate_required": True,
        },
        "append_only": True,
        "artifact_fingerprint": artifact_fingerprint,
    }
    return artifact


def validate_strategy_freeze_artifact(artifact: Mapping[str, object]) -> None:
    payload = dict(artifact)
    fingerprint = str(payload.pop("artifact_fingerprint", ""))
    identity_payload = {
        "freeze_contract_version": payload.get("freeze_contract_version"),
        "strategy_name": payload.get("strategy_name"),
        "strategy_family": payload.get("strategy_family"),
        "strategy_role": payload.get("strategy_role"),
        "component_fingerprints": payload.get("component_fingerprints"),
        "code_fingerprints": payload.get("code_fingerprints"),
        "config_fingerprints": payload.get("config_fingerprints"),
    }
    if not fingerprint or fingerprint != _fingerprint(identity_payload):
        raise ValueError("Strategie-Freeze-Fingerprint ist ungültig.")
    expected_version_suffix = fingerprint[:16]
    if not str(payload.get("strategy_version") or "").endswith(expected_version_suffix):
        raise ValueError("Strategieversion passt nicht zum Freeze-Fingerprint.")
    release = dict(payload.get("release") or {})
    if release.get("approved_from_performance") or release.get("automatic_production_activation"):
        raise ValueError("Ein Forschungs-Freeze darf keine Performance- oder Produktionsfreigabe enthalten.")
    components = dict(payload.get("components") or {})
    if any(domain not in components for domain in REQUIRED_DOMAINS):
        raise ValueError("Strategie-Freeze enthält nicht alle Pflichtbereiche.")


def _connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_strategy_freeze_store(
    path: Path = DEFAULT_STRATEGY_FREEZE_DB_PATH,
) -> None:
    with _connect(Path(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategy_freeze_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategy_freezes (
                strategy_version TEXT PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                strategy_family TEXT NOT NULL,
                strategy_role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                artifact_fingerprint TEXT NOT NULL UNIQUE,
                artifact_json TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS strategy_freezes_no_update
            BEFORE UPDATE ON strategy_freezes
            BEGIN SELECT RAISE(ABORT, 'strategy freeze append-only'); END;
            CREATE TRIGGER IF NOT EXISTS strategy_freezes_no_delete
            BEFORE DELETE ON strategy_freezes
            BEGIN SELECT RAISE(ABORT, 'strategy freeze append-only'); END;
            """
        )
        existing = connection.execute(
            "SELECT value FROM strategy_freeze_meta WHERE key = 'schema_version'"
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO strategy_freeze_meta(key, value) VALUES ('schema_version', ?)",
                (str(STRATEGY_FREEZE_SCHEMA_VERSION),),
            )
        elif int(existing["value"]) != STRATEGY_FREEZE_SCHEMA_VERSION:
            raise RuntimeError("Nicht unterstützte Strategie-Freeze-Datenbankversion.")


def register_strategy_freeze(
    artifact: Mapping[str, object],
    path: Path = DEFAULT_STRATEGY_FREEZE_DB_PATH,
) -> dict:
    normalized = json.loads(_canonical_json(dict(artifact)))
    validate_strategy_freeze_artifact(normalized)
    initialize_strategy_freeze_store(path)
    version = str(normalized["strategy_version"])
    encoded = _canonical_json(normalized)
    with _connect(Path(path)) as connection:
        existing = connection.execute(
            "SELECT artifact_json FROM strategy_freezes WHERE strategy_version = ?",
            (version,),
        ).fetchone()
        if existing is not None:
            existing_artifact = json.loads(str(existing["artifact_json"]))
            if existing_artifact.get("artifact_fingerprint") != normalized.get(
                "artifact_fingerprint"
            ):
                raise ValueError("Strategieversion besitzt bereits ein abweichendes Freeze-Artefakt.")
            return {"strategy_version": version, "inserted": False, "existing": True}
        connection.execute(
            """
            INSERT INTO strategy_freezes(
                strategy_version, strategy_name, strategy_family, strategy_role,
                created_at, artifact_fingerprint, artifact_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                normalized["strategy_name"],
                normalized["strategy_family"],
                normalized["strategy_role"],
                normalized["created_at"],
                normalized["artifact_fingerprint"],
                encoded,
            ),
        )
    return {"strategy_version": version, "inserted": True, "existing": False}


def load_strategy_freezes(
    path: Path = DEFAULT_STRATEGY_FREEZE_DB_PATH,
) -> list[dict]:
    if not Path(path).exists():
        return []
    initialize_strategy_freeze_store(path)
    with _connect(Path(path)) as connection:
        rows = connection.execute(
            "SELECT artifact_json FROM strategy_freezes ORDER BY created_at, strategy_version"
        ).fetchall()
    return [json.loads(str(row["artifact_json"])) for row in rows]


def strategy_freeze_store_audit(
    path: Path = DEFAULT_STRATEGY_FREEZE_DB_PATH,
) -> dict:
    if not Path(path).exists():
        return {"status": "not_created", "freezes": 0, "invalid": 0}
    initialize_strategy_freeze_store(path)
    invalid: list[str] = []
    freezes = load_strategy_freezes(path)
    for artifact in freezes:
        try:
            validate_strategy_freeze_artifact(artifact)
        except ValueError as exc:
            invalid.append(f"{artifact.get('strategy_version')}: {exc}")
    with _connect(Path(path)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
    return {
        "schema_version": STRATEGY_FREEZE_SCHEMA_VERSION,
        "quick_check": quick_check,
        "freezes": len(freezes),
        "invalid": len(invalid),
        "invalid_details": invalid,
        "status": "ok" if quick_check == "ok" and not invalid else "attention",
        "append_only": True,
        "performance_release_allowed": False,
        "automatic_production_activation": False,
    }
