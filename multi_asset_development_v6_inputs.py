from __future__ import annotations

"""Versioned, fail-closed input layer for Multi-Asset Development v6.

The module never downloads or repairs prices.  It projects the frozen Crypto
source into an append-only store, audits the three versioned input stores and
loads histories as explicit continuity segments.  A new segment always needs
its own 220-bar warm-up and an outcome window may never cross a segment edge.
"""

import json
import math
import os
import sqlite3
import uuid
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from fx_carry_pit import default_fx_pair_contracts, normalize_fx_ohlc
from multi_asset_development_execution import (
    DEFAULT_DATASET_MANIFEST,
    DEFAULT_FX_STORE,
    DEFAULT_IDENTITY_STORE,
    build_development_universe,
)
from multi_asset_discovery_v1 import canonical_json, file_sha256, fingerprint


PROJECT_ROOT = Path(__file__).resolve().parent
DEVELOPMENT_START = "2016-01-01"
DEVELOPMENT_END = "2021-12-31"
MINIMUM_SEGMENT_HISTORY = 220
CRYPTO_PROJECTION_VERSION = "crypto-historical-pit-2026.09.05-v1"
CRYPTO_REMEDIATION_VERSION = "crypto-historical-remediation-2026.09.05-v1"
INPUT_PRECHECK_VERSION = "multi-asset-development-v6-input-precheck-2026.09.05-v1"
GAP_POLICY_VERSION = "multi-asset-development-v6-gap-policy-2026.09.05-v1"
PEER_SESSION_CONSENSUS_VERSION = (
    "multi-asset-development-v6-peer-session-consensus-2026.09.05-v1"
)

DEFAULT_EQUITY_ETF_STORE = (
    PROJECT_ROOT / "runtime" / "equity_etf_historical_pit_2026-09-03-v1.sqlite3"
)
DEFAULT_EQUITY_ETF_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "equity_etf_historical_pit_2026-09-03-v1.json"
)
DEFAULT_CRYPTO_STORE = (
    PROJECT_ROOT / "runtime" / "crypto_historical_pit_2026-09-05-v1.sqlite3"
)
DEFAULT_CRYPTO_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "crypto_historical_pit_2026-09-05-v1.json"
)
DEFAULT_FX_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "fx_historical_pit_remediation_2026-09-01-v2.json"
)
DEFAULT_INPUT_PRECHECK_ARTIFACT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "multi_asset_development_v6_input_precheck_2026-09-05-v1.json"
)

DEFAULT_EXPECTED_ASSET_COUNTS = {"EQUITIES_ETF": 2488, "CRYPTO": 30, "FX": 3}
DEFAULT_EXPECTED_NO_DATA_COUNTS = {"EQUITIES_ETF": 191, "CRYPTO": 1, "FX": 0}
DEFAULT_EXPECTED_ACTIVE_BAR_COUNTS = {
    "EQUITIES_ETF": 3_025_873,
    "CRYPTO": 33_675,
    "FX": 4_508,
}
DEFAULT_EXPECTED_INVALID_BAR_COUNTS = {
    "EQUITIES_ETF": 2_206,
    "CRYPTO": 3,
    "FX": 93,
}
DEFAULT_EXPECTED_ELIGIBLE_SIGNAL_POSITION_COUNTS = {
    "EQUITIES_ETF": 2_329_260,
    "CRYPTO": 27_293,
    "FX": 0,
}
DEFAULT_EXPECTED_CRYPTO_INVALID_SESSIONS = {
    "AAVE-USD": ("2020-10-02",),
    "ICP-USD": ("2021-05-10",),
    "SHIB-USD": ("2021-04-16",),
}
SOURCE_PATH_ROOT_PROJECT = "PROJECT_ROOT"
SOURCE_PATH_ROOT_PRECHECK = "INPUT_PRECHECK_PARENT"
SOURCE_PATH_ROOT_DATASET = "DATASET_MANIFEST_PARENT"


def default_implementation_paths() -> tuple[Path, ...]:
    """Production files that must be frozen into the v6 input precheck.

    The list is deliberately explicit.  A missing file makes the precheck
    fail instead of silently weakening the code-provenance fingerprint.
    """

    return (
        PROJECT_ROOT / "multi_asset_development_v6_inputs.py",
        PROJECT_ROOT / "multi_asset_development_v6_contract.py",
        PROJECT_ROOT / "multi_asset_development_v6_execution.py",
        PROJECT_ROOT / "multi_asset_development_v6_outcomes.py",
        PROJECT_ROOT / "multi_asset_development_v6_store.py",
        PROJECT_ROOT / "multi_asset_development_v6_benchmark.py",
        PROJECT_ROOT / "multi_asset_development_v6_audit.py",
        PROJECT_ROOT / "multi_asset_development_v6_reporting.py",
        PROJECT_ROOT / "multi_asset_development_v6_runner.py",
        PROJECT_ROOT / "multi_asset_development_v6_preflight.py",
        PROJECT_ROOT / "config" / "multi_asset_discovery_development_v6.json",
        PROJECT_ROOT / "config" / "multi_asset_discovery_v1.json",
        PROJECT_ROOT / "scripts" / "build_multi_asset_development_v6_inputs.py",
        PROJECT_ROOT / "scripts" / "build_multi_asset_development_v6_contract.py",
        PROJECT_ROOT / "scripts" / "build_multi_asset_development_v6_preflight.py",
        PROJECT_ROOT / "scripts" / "run_multi_asset_development_v6_chain.py",
        PROJECT_ROOT / "scripts" / "run_multi_asset_development_v6_chain.cmd",
        PROJECT_ROOT / "scripts" / "install_multi_asset_development_v6_task.ps1",
        # Direct project-local runtime/scientific dependencies imported by the
        # v6 modules above.  Leaving these outside the fingerprint would allow
        # the effective implementation to change without invalidating the
        # frozen input/contract chain.
        PROJECT_ROOT / "fx_carry_pit.py",
        PROJECT_ROOT / "historical_dependency_policy.py",
        PROJECT_ROOT / "multi_asset_development_contract.py",
        PROJECT_ROOT / "multi_asset_development_execution.py",
        PROJECT_ROOT / "multi_asset_discovery_v1.py",
        PROJECT_ROOT / "analysis_models.py",
        PROJECT_ROOT / "cot_positioning.py",
        PROJECT_ROOT / "swing_broad_research.py",
        PROJECT_ROOT / "swing_broad_context.py",
        PROJECT_ROOT / "swing_forward_evaluation.py",
        PROJECT_ROOT / "swing_research_dataset.py",
        PROJECT_ROOT / "swing_research_identity.py",
        PROJECT_ROOT / "swing_research_identity_v2.py",
        PROJECT_ROOT / "swing_research_identity_v3.py",
        PROJECT_ROOT / "swing_research_quality.py",
        PROJECT_ROOT / "swing_run_lock.py",
        PROJECT_ROOT / "swing_walk_forward.py",
        PROJECT_ROOT / "swing_walk_forward_campaign.py",
        PROJECT_ROOT / "technical_analysis.py",
        PROJECT_ROOT / "trading_assistant.py",
        PROJECT_ROOT / "config" / "multi_asset_discovery_development_v5.json",
        PROJECT_ROOT / "config" / "swing_walk_forward_campaign.json",
    )


def build_v6_implementation_provenance(
    implementation_paths: Sequence[Path] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    """Hash the exact current v6 implementation for build/start-gate reuse.

    Paths inside ``project_root`` use stable repository-relative labels.  A
    missing file keeps the result non-complete and suppresses the aggregate
    fingerprint, so callers cannot silently freeze a partial code surface.
    """

    project_root = Path(project_root).resolve()
    paths = tuple(
        Path(path)
        for path in (
            default_implementation_paths()
            if implementation_paths is None
            else implementation_paths
        )
    )
    hashes: dict[str, str] = {}
    missing: list[str] = []
    labels: list[str] = []
    for path in paths:
        resolved = path.resolve()
        try:
            label = str(resolved.relative_to(project_root)).replace("\\", "/")
        except ValueError:
            label = resolved.as_posix()
        if label in labels:
            raise MultiAssetV6InputError(
                f"Doppelter Implementierungspfad im v6-Fingerprint: {label}"
            )
        labels.append(label)
        if not resolved.is_file():
            missing.append(label)
            continue
        hashes[label] = file_sha256(resolved)
    complete = bool(labels) and not missing and len(hashes) == len(labels)
    return {
        "implementation_paths": labels,
        "implementation_sha256": hashes,
        "missing_implementation_files": missing,
        "implementation_fingerprint": fingerprint(hashes) if complete else None,
        "complete": complete,
    }


class MultiAssetV6InputError(RuntimeError):
    """The v6 input contract cannot be satisfied without guessing."""


def gap_policy(
    *, peer_session_consensus_fingerprint: str | None = None
) -> dict[str, object]:
    """Return the immutable continuity rules used by projection and loader."""

    payload: dict[str, object] = {
        "version": GAP_POLICY_VERSION,
        "minimum_history_observations_per_segment": MINIMUM_SEGMENT_HISTORY,
        "observation_count_is_not_calendar_duration": True,
        "archived_invalid_source_session_always_starts_new_segment": True,
        "archived_invalid_source_session_always_creates_boundary": True,
        "trailing_archived_invalid_session_ends_final_segment": True,
        "entry_may_cross_segment_boundary": False,
        "outcome_may_cross_segment_boundary": False,
        "peer_session_consensus_fingerprint": peer_session_consensus_fingerprint,
        "peer_session_consensus_required_for_equities_etf_and_fx": True,
        "official_exchange_calendars_asserted": False,
        "dates_without_any_active_group_observation_asserted_as_sessions": False,
        "rules": {
            "CRYPTO": {
                "calendar_days_without_observation_threshold": 0,
                "boundary_when_calendar_days_without_observation_gt": 0,
                "expected_cadence": "EVERY_CALENDAR_DAY",
            },
            "EQUITIES": {
                "session_group": "FROZEN_IDENTITY_REGISTRY_MIC",
                "boundary_when_target_missing_on_peer_observed_group_session": True,
                "official_exchange_calendar_asserted": False,
            },
            "ETF": {
                "session_group": "FROZEN_IDENTITY_REGISTRY_MIC",
                "boundary_when_target_missing_on_peer_observed_group_session": True,
                "official_exchange_calendar_asserted": False,
            },
            "FX": {
                "session_group": "FROZEN_THREE_PAIR_ACTIVE_SESSION_UNION",
                "boundary_when_target_missing_on_peer_observed_group_session": True,
                "official_fx_calendar_asserted": False,
            },
        },
    }
    payload["fingerprint"] = fingerprint(payload)
    return payload


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiAssetV6InputError(f"JSON-Artefakt nicht lesbar: {path}") from exc


@lru_cache(maxsize=8)
def _read_precheck_for_unchanged_stat(
    path_text: str, size: int, modified_ns: int
) -> dict[str, object]:
    del size, modified_ns
    return _read_json(Path(path_text))


def _read_cached_input_precheck(path: Path) -> dict[str, object]:
    resolved = Path(path).resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise MultiAssetV6InputError(
            f"v6-Input-Precheck nicht lesbar: {resolved}"
        ) from exc
    return dict(
        _read_precheck_for_unchanged_stat(
            str(resolved), int(stat.st_size), int(stat.st_mtime_ns)
        )
    )


def _relative_source_path(*, path: Path, root: Path, label: str) -> str:
    resolved_root = Path(root).resolve()
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise MultiAssetV6InputError(
            f"Source-Pfad verlässt den erlaubten Root ({label}): {path}"
        ) from exc
    value = relative.as_posix()
    if not value or value == "." or Path(value).is_absolute() or ".." in Path(value).parts:
        raise MultiAssetV6InputError(f"Unsicherer relativer Source-Pfad ({label}): {value}")
    return value


def _canonical_source_paths(
    sources: Mapping[str, Path],
    *,
    dataset_manifest: Path,
    artifact_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, dict[str, str]]:
    """Represent every hashed source without embedding foreign absolute paths."""

    project_root = Path(project_root).resolve()
    artifact_parent = Path(artifact_path).resolve().parent
    dataset_parent = Path(dataset_manifest).resolve().parent
    result: dict[str, dict[str, str]] = {}
    for label, source in sources.items():
        source = Path(source).resolve()
        if str(label).startswith("crypto_frozen:"):
            root_name = SOURCE_PATH_ROOT_DATASET
            relative = _relative_source_path(
                path=source, root=dataset_parent, label=str(label)
            )
        else:
            try:
                relative = _relative_source_path(
                    path=source, root=project_root, label=str(label)
                )
                root_name = SOURCE_PATH_ROOT_PROJECT
            except MultiAssetV6InputError:
                # Mini fixtures and explicitly isolated audit builds remain
                # relocatable, but never persist their absolute host path.
                relative = _relative_source_path(
                    path=source, root=artifact_parent, label=str(label)
                )
                root_name = SOURCE_PATH_ROOT_PRECHECK
        result[str(label)] = {"root": root_name, "relative_path": relative}
    return result


def _resolve_source_path_entry(
    entry: Mapping[str, object],
    *,
    project_root: Path,
    precheck_parent: Path,
    dataset_parent: Path | None,
    label: str,
) -> Path:
    if set(entry) != {"root", "relative_path"}:
        raise MultiAssetV6InputError(
            f"Ungültiger kanonischer Source-Pfadvertrag: {label}"
        )
    root_name = str(entry.get("root") or "")
    relative_text = str(entry.get("relative_path") or "")
    relative = Path(relative_text)
    if (
        not relative_text
        or relative_text == "."
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in relative_text
    ):
        raise MultiAssetV6InputError(
            f"Unsicherer kanonischer Source-Pfad: {label}:{relative_text}"
        )
    roots = {
        SOURCE_PATH_ROOT_PROJECT: Path(project_root).resolve(),
        SOURCE_PATH_ROOT_PRECHECK: Path(precheck_parent).resolve(),
    }
    if dataset_parent is not None:
        roots[SOURCE_PATH_ROOT_DATASET] = Path(dataset_parent).resolve()
    root = roots.get(root_name)
    if root is None:
        raise MultiAssetV6InputError(
            f"Unbekannter/noch nicht auflösbarer Source-Root: {label}:{root_name}"
        )
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise MultiAssetV6InputError(
            f"Kanonischer Source-Pfad verlässt seinen Root: {label}"
        ) from exc
    return resolved


def verify_v6_current_sources(
    *,
    input_precheck_artifact: Path = DEFAULT_INPUT_PRECHECK_ARTIFACT,
    input_precheck: Mapping[str, object] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    """Fail closed unless every current source still matches the PASS precheck."""

    artifact_path = Path(input_precheck_artifact).resolve()
    payload = (
        dict(input_precheck)
        if input_precheck is not None
        else _read_json(artifact_path)
    )
    if not _validate_self_fingerprint(payload) or payload.get("status") != "PASS":
        raise MultiAssetV6InputError(
            "v6-Input-Precheck ist für Source-Rehash nicht selbstgültig/PASS."
        )
    stored_before = {
        str(label): str(value)
        for label, value in dict(payload.get("source_sha256_before") or {}).items()
    }
    stored_after = {
        str(label): str(value)
        for label, value in dict(payload.get("source_sha256_after") or {}).items()
    }
    path_contract = {
        str(label): dict(value)
        for label, value in dict(payload.get("source_paths") or {}).items()
        if isinstance(value, Mapping)
    }
    expected_labels = set(stored_before)
    if (
        not expected_labels
        or stored_after != stored_before
        or set(path_contract) != expected_labels
        or len(path_contract) != len(dict(payload.get("source_paths") or {}))
    ):
        raise MultiAssetV6InputError(
            "Source-Hash-/Pfadlabels im v6-Input-Precheck sind unvollständig."
        )
    manifest_entry = path_contract.get("dataset_manifest")
    if manifest_entry is None or manifest_entry.get("root") == SOURCE_PATH_ROOT_DATASET:
        raise MultiAssetV6InputError(
            "Dataset-Manifest besitzt keinen unabhängig auflösbaren Source-Pfad."
        )
    manifest_path = _resolve_source_path_entry(
        manifest_entry,
        project_root=Path(project_root),
        precheck_parent=artifact_path.parent,
        dataset_parent=None,
        label="dataset_manifest",
    )
    resolved_paths: dict[str, Path] = {}
    current_hashes: dict[str, str] = {}
    for label in sorted(path_contract):
        path = _resolve_source_path_entry(
            path_contract[label],
            project_root=Path(project_root),
            precheck_parent=artifact_path.parent,
            dataset_parent=manifest_path.parent,
            label=label,
        )
        if not path.is_file():
            raise MultiAssetV6InputError(f"Aktueller v6-Source fehlt: {label}")
        resolved_paths[label] = path
        current_hashes[label] = file_sha256(path)
    mismatches = sorted(
        label
        for label in expected_labels
        if current_hashes.get(label) != stored_before.get(label)
    )
    if mismatches:
        raise MultiAssetV6InputError(
            f"Aktuelle v6-Sources weichen vom PASS-Precheck ab: {mismatches}"
        )
    return {
        "status": "PASS",
        "source_count": len(current_hashes),
        "source_sha256": current_hashes,
        "source_set_fingerprint": fingerprint(current_hashes),
        "resolved_sources": {
            label: str(path) for label, path in sorted(resolved_paths.items())
        },
    }


def _named_fingerprint_is_valid(
    payload: Mapping[str, object], field: str
) -> bool:
    expected = payload.get(field)
    if not expected:
        return False
    basis = dict(payload)
    basis.pop(field, None)
    return expected == fingerprint(basis)


def _read_only(path: Path) -> sqlite3.Connection:
    path = Path(path).resolve()
    if not path.exists():
        raise MultiAssetV6InputError(f"Pflicht-Store fehlt: {path}")
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


@lru_cache(maxsize=32)
def _sha256_for_unchanged_stat(
    resolved_path: str, size: int, modified_ns: int
) -> str:
    del size, modified_ns
    return file_sha256(Path(resolved_path))


def _matches_immutable_sha256(path: Path, expected: object) -> bool:
    if not expected or not path.exists():
        return False
    stat = path.stat()
    actual = _sha256_for_unchanged_stat(
        str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns)
    )
    return actual == str(expected)


def _write_append_only(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        prior = _read_json(path)
        if (
            not _validate_self_fingerprint(prior)
            or prior.get("artifact_fingerprint")
            != payload.get("artifact_fingerprint")
        ):
            raise MultiAssetV6InputError(
                f"Append-only-Artefakt existiert mit anderem Inhalt: {path}"
            )
        return
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            prior = _read_json(path)
            if (
                not _validate_self_fingerprint(prior)
                or prior.get("artifact_fingerprint")
                != payload.get("artifact_fingerprint")
            ):
                raise MultiAssetV6InputError(
                    f"Paralleler append-only Build kollidiert: {path}"
                )
    finally:
        temporary.unlink(missing_ok=True)


def _append_only_triggers(table: str) -> str:
    return f"""
    CREATE TRIGGER IF NOT EXISTS {table}_no_update
    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'append-only'); END;
    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'append-only'); END;
    """


def _initialize_crypto_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS active_bars (
                bar_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                listing_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                open REAL NOT NULL CHECK(open > 0),
                high REAL NOT NULL CHECK(high > 0),
                low REAL NOT NULL CHECK(low > 0),
                close REAL NOT NULL CHECK(close > 0),
                volume REAL,
                source_file TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                source_history_fingerprint TEXT NOT NULL,
                bar_fingerprint TEXT NOT NULL UNIQUE,
                segment_id INTEGER NOT NULL CHECK(segment_id >= 0),
                segment_position INTEGER NOT NULL CHECK(segment_position >= 0),
                UNIQUE(listing_id, session_date),
                CHECK(low <= open AND open <= high),
                CHECK(low <= close AND close <= high)
            );
            CREATE TABLE IF NOT EXISTS invalid_source_bars (
                invalid_bar_fingerprint TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                listing_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                source_file TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                classification TEXT NOT NULL,
                invalid_json TEXT NOT NULL,
                UNIQUE(listing_id, session_date, source_row)
            );
            CREATE TABLE IF NOT EXISTS gap_boundaries (
                boundary_fingerprint TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                listing_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                boundary_type TEXT NOT NULL,
                after_date TEXT,
                before_date TEXT,
                missing_observations INTEGER,
                boundary_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS asset_coverage (
                asset_key TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                listing_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                raw_bars INTEGER NOT NULL,
                active_valid_bars INTEGER NOT NULL,
                invalid_source_bars INTEGER NOT NULL,
                duplicate_source_rows INTEGER NOT NULL,
                source_missing_calendar_days INTEGER NOT NULL,
                segment_count INTEGER NOT NULL,
                coverage_status TEXT NOT NULL,
                first_active_date TEXT,
                last_active_date TEXT,
                coverage_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projection_versions (
                version TEXT PRIMARY KEY,
                dataset_fingerprint TEXT NOT NULL UNIQUE,
                invalid_manifest_fingerprint TEXT NOT NULL,
                gap_manifest_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                manifest_json TEXT NOT NULL
            );
            """
        )
        for table in (
            "active_bars",
            "invalid_source_bars",
            "gap_boundaries",
            "asset_coverage",
            "projection_versions",
        ):
            connection.executescript(_append_only_triggers(table))


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ohlc_violations(row: Mapping[str, object]) -> list[str]:
    values = {name: _finite_number(row.get(name)) for name in ("Open", "High", "Low", "Close")}
    violations: list[str] = []
    for name, value in values.items():
        if value is None:
            violations.append(f"{name.upper()}_MISSING_OR_NONFINITE")
        elif value <= 0:
            violations.append(f"{name.upper()}_NON_POSITIVE")
    if any(value is None for value in values.values()):
        return violations
    low = float(values["Low"])
    high = float(values["High"])
    if low > high:
        violations.append("LOW_ABOVE_HIGH")
    if float(values["Open"]) < low or float(values["Open"]) > high:
        violations.append("OPEN_OUTSIDE_ENVELOPE")
    if float(values["Close"]) < low or float(values["Close"]) > high:
        violations.append("CLOSE_OUTSIDE_ENVELOPE")
    return violations


def _peer_observed_missing_boundaries(
    *,
    asset_class: str,
    ticker: str,
    active_dates: Sequence[date],
    peer_observed_group_sessions: Sequence[date],
    session_group_key: str | None,
) -> list[dict[str, object]]:
    """Return continuity edges supported by the frozen observed-session union.

    This deliberately is not an exchange-calendar claim.  A date is treated as
    an expected session only when another active member of the frozen MIC/FX
    group has a bar on that date and the target does not.  Dates on which the
    complete group is silent remain unknown and are not invented as sessions.
    """

    if asset_class == "CRYPTO":
        result: list[dict[str, object]] = []
        for previous, current in zip(active_dates, active_dates[1:]):
            missing = (current - previous).days - 1
            if missing > 0:
                result.append(
                    {
                        "asset_class": asset_class,
                        "ticker": ticker,
                        "boundary_type": "MISSING_CALENDAR_OBSERVATIONS",
                        "after_date": previous.isoformat(),
                        "before_date": current.isoformat(),
                        "missing_observations": missing,
                    }
                )
        return result

    if asset_class not in {"EQUITIES", "ETF", "FX"}:
        raise MultiAssetV6InputError(
            f"Unbekannte Assetklasse fuer Session-Konsens: {asset_class}"
        )
    if not session_group_key:
        raise MultiAssetV6InputError(
            f"Session-Gruppe fehlt fuer {asset_class}:{ticker}."
        )
    group_sessions = sorted(set(peer_observed_group_sessions))
    if not group_sessions:
        raise MultiAssetV6InputError(
            f"Beobachteter Session-Konsens ist leer fuer {asset_class}:{ticker}."
        )
    result = []
    for previous, current in zip(active_dates, active_dates[1:]):
        start = bisect_right(group_sessions, previous)
        stop = bisect_left(group_sessions, current)
        missing_sessions = group_sessions[start:stop]
        if not missing_sessions:
            continue
        result.append(
            {
                "asset_class": asset_class,
                "ticker": ticker,
                "boundary_type": "TARGET_MISSING_ON_PEER_OBSERVED_GROUP_SESSION",
                "session_group_key": session_group_key,
                "after_date": previous.isoformat(),
                "before_date": current.isoformat(),
                "missing_observations": len(missing_sessions),
                "first_missing_session_date": missing_sessions[0].isoformat(),
                "last_missing_session_date": missing_sessions[-1].isoformat(),
            }
        )
    return result


def _eligible_positions_after_gap_policy(
    *,
    asset_class: str,
    ticker: str,
    active_dates: Sequence[date],
    invalid_days: Sequence[date],
    peer_observed_group_sessions: Sequence[date] = (),
    session_group_key: str | None = None,
) -> int:
    """Count signal rows with warm-up and a same-segment reference entry."""

    if not active_dates:
        return 0
    boundaries = _peer_observed_missing_boundaries(
        asset_class=asset_class,
        ticker=ticker,
        active_dates=active_dates,
        peer_observed_group_sessions=peer_observed_group_sessions,
        session_group_key=session_group_key,
    )
    before_dates = {
        date.fromisoformat(str(item["before_date"])) for item in boundaries
    }
    starts = {
        index
        for index, active_day in enumerate(active_dates)
        if active_day in before_dates
    }
    for invalid_day in invalid_days:
        next_index = bisect_right(active_dates, invalid_day)
        if next_index < len(active_dates):
            starts.add(next_index)
    points = [0, *sorted(starts), len(active_dates)]
    return sum(
        max(points[index + 1] - points[index] - MINIMUM_SEGMENT_HISTORY, 0)
        for index in range(len(points) - 1)
    )


def _crypto_assets(
    assets: Sequence[Mapping[str, object]] | None,
) -> list[dict[str, object]]:
    source = assets if assets is not None else build_development_universe()["assets"]
    result = [dict(item) for item in source if str(item.get("asset_class")) == "CRYPTO"]
    result.sort(key=lambda item: str(item["symbol"]))
    if not result:
        raise MultiAssetV6InputError("Crypto-Projektion besitzt kein Universe.")
    for asset in result:
        identity = dict(asset.get("identity") or {})
        if not identity.get("asset_id") or not identity.get("listing_id"):
            raise MultiAssetV6InputError(
                f"Crypto-Identity unvollständig: {asset.get('symbol')}"
            )
    for field, values in (
        ("symbol", [str(item["symbol"]) for item in result]),
        (
            "asset_id",
            [str(dict(item["identity"])["asset_id"]) for item in result],
        ),
        (
            "listing_id",
            [str(dict(item["identity"])["listing_id"]) for item in result],
        ),
    ):
        if len(values) != len(set(values)):
            raise MultiAssetV6InputError(f"Crypto-{field} ist nicht eindeutig.")
    return result


def _project_crypto_asset(
    asset: Mapping[str, object], manifest_root: Path
) -> dict[str, object]:
    source_path = manifest_root / str(asset["modern_file"])
    if not source_path.exists():
        raise MultiAssetV6InputError(f"Frozen Crypto-Datei fehlt: {source_path}")
    frame = pd.read_parquet(
        source_path,
        filters=[
            ("Date", ">=", pd.Timestamp(DEVELOPMENT_START)),
            ("Date", "<=", pd.Timestamp(DEVELOPMENT_END)),
        ],
    )
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.sort_index(kind="stable")
    identity = dict(asset["identity"])
    asset_id = str(identity["asset_id"])
    listing_id = str(identity["listing_id"])
    ticker = str(asset["symbol"])
    source_file = str(asset["modern_file"])
    history_fingerprint = str(asset["modern_history_fingerprint"])
    date_counts = frame.index.value_counts()
    duplicate_dates = {stamp for stamp, count in date_counts.items() if count > 1}

    active_basis: list[dict[str, object]] = []
    invalid_basis: list[dict[str, object]] = []
    for source_row, (stamp, series) in enumerate(frame.iterrows()):
        day = stamp.date().isoformat()
        values = {name: _finite_number(series.get(name)) for name in ("Open", "High", "Low", "Close")}
        violations = _ohlc_violations(series)
        if stamp in duplicate_dates:
            violations = [*violations, "DUPLICATE_SOURCE_SESSION"]
        volume = _finite_number(series.get("Volume"))
        common = {
            "asset_id": asset_id,
            "listing_id": listing_id,
            "ticker": ticker,
            "session_date": day,
            "source_file": source_file,
            "source_row": source_row,
            "source_row_in_development_slice": source_row,
            "source_history_fingerprint": history_fingerprint,
            "ohlc": values,
            "volume": volume,
        }
        if violations:
            invalid_payload = {
                **common,
                "classification": (
                    "DUPLICATE_SOURCE_SESSION"
                    if "DUPLICATE_SOURCE_SESSION" in violations
                    else "INVALID_SOURCE_OHLC"
                ),
                "violations": sorted(set(violations)),
                "remediation": "EXCLUDED_WITHOUT_REPLACEMENT",
            }
            invalid_payload["invalid_bar_fingerprint"] = fingerprint(invalid_payload)
            invalid_basis.append(invalid_payload)
            continue
        active_basis.append(common)

    active_basis.sort(key=lambda item: (str(item["session_date"]), int(item["source_row"])))
    active_dates = [date.fromisoformat(str(item["session_date"])) for item in active_basis]
    observed_dates = sorted(set(active_dates))
    boundaries: list[dict[str, object]] = []
    for invalid_session in sorted(
        {str(item["session_date"]) for item in invalid_basis}
    ):
        invalid_day = date.fromisoformat(invalid_session)
        previous = max((item for item in active_dates if item < invalid_day), default=None)
        following = min((item for item in active_dates if item > invalid_day), default=None)
        boundary = {
            "asset_id": asset_id,
            "listing_id": listing_id,
            "ticker": ticker,
            "boundary_type": "ARCHIVED_INVALID_SOURCE_SESSION",
            "invalid_session_date": invalid_day.isoformat(),
            "after_date": previous.isoformat() if previous else None,
            "before_date": following.isoformat() if following else None,
            "missing_observations": 1,
        }
        boundary["boundary_fingerprint"] = fingerprint(boundary)
        boundaries.append(boundary)
    for prior, current in zip(observed_dates, observed_dates[1:]):
        missing = (current - prior).days - 1
        if missing > 0:
            boundary = {
                "asset_id": asset_id,
                "listing_id": listing_id,
                "ticker": ticker,
                "boundary_type": "MISSING_CALENDAR_OBSERVATIONS",
                "after_date": prior.isoformat(),
                "before_date": current.isoformat(),
                "missing_observations": missing,
            }
            boundary["boundary_fingerprint"] = fingerprint(boundary)
            boundaries.append(boundary)
    boundaries.sort(
        key=lambda item: (
            str(item.get("before_date") or "9999-12-31"),
            str(item["boundary_type"]),
            str(item.get("invalid_session_date") or ""),
        )
    )
    segment_starts = {
        str(item["before_date"])
        for item in boundaries
        if item.get("before_date") is not None
    }
    segment_id = 0
    segment_position = 0
    active_rows: list[dict[str, object]] = []
    for index, item in enumerate(active_basis):
        day = str(item["session_date"])
        if index and day in segment_starts:
            segment_id += 1
            segment_position = 0
        bar_basis = {
            "projection_version": CRYPTO_PROJECTION_VERSION,
            **item,
            "segment_id": segment_id,
            "segment_position": segment_position,
        }
        bar_fingerprint = fingerprint(bar_basis)
        active_rows.append(
            {
                **bar_basis,
                "bar_id": f"crypto-bar-{bar_fingerprint[:32]}",
                "bar_fingerprint": bar_fingerprint,
            }
        )
        segment_position += 1
    first = str(active_rows[0]["session_date"]) if active_rows else None
    last = str(active_rows[-1]["session_date"]) if active_rows else None
    expected_days = (
        (date.fromisoformat(last) - date.fromisoformat(first)).days + 1
        if first and last
        else 0
    )
    active_date_count = len({str(item["session_date"]) for item in active_rows})
    invalid_date_count = len(
        {
            str(item["session_date"])
            for item in invalid_basis
            if first and last and first <= str(item["session_date"]) <= last
        }
    )
    coverage = {
        "asset_key": str(asset["asset_key"]),
        "asset_id": asset_id,
        "listing_id": listing_id,
        "ticker": ticker,
        "asset_class": "CRYPTO",
        "period": [DEVELOPMENT_START, DEVELOPMENT_END],
        "raw_bars": len(frame),
        "active_valid_bars": len(active_rows),
        "invalid_source_bars": len(invalid_basis),
        "duplicate_source_rows": sum(
            "DUPLICATE_SOURCE_SESSION" in item["violations"] for item in invalid_basis
        ),
        "source_missing_calendar_days": max(
            0, expected_days - active_date_count - invalid_date_count
        ),
        "segment_count": len({int(item["segment_id"]) for item in active_rows}),
        "coverage_status": (
            "NO_DATA"
            if not len(frame)
            else (
                "NO_USABLE_DATA_INVALID_SOURCE"
                if not active_rows
                else (
                    "AVAILABLE_WITH_EXCLUSIONS_OR_GAPS"
                    if invalid_basis or boundaries
                    else "AVAILABLE"
                )
            )
        ),
        "first_active_date": first,
        "last_active_date": last,
        "coverage_pct_of_source_rows": (
            round(len(active_rows) / len(frame) * 100, 8) if len(frame) else 0.0
        ),
        "no_clipping": True,
        "no_imputation": True,
        "no_interpolation": True,
    }
    return {
        "active_rows": active_rows,
        "invalid_rows": invalid_basis,
        "boundaries": boundaries,
        "coverage": coverage,
        "source_path": source_path,
    }


def build_crypto_projection(
    *,
    target_path: Path = DEFAULT_CRYPTO_STORE,
    artifact_path: Path = DEFAULT_CRYPTO_ARTIFACT,
    manifest_path: Path = DEFAULT_DATASET_MANIFEST,
    identity_store: Path = DEFAULT_IDENTITY_STORE,
    assets: Sequence[Mapping[str, object]] | None = None,
    expected_asset_count: int | None = None,
    expected_raw_bar_count: int | None = None,
    expected_active_bar_count: int | None = None,
    expected_invalid_bar_count: int | None = None,
    expected_no_data_symbols: Sequence[str] | None = None,
    expected_invalid_sessions: Mapping[str, Sequence[str]] | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    """Build one immutable Crypto projection from the frozen source files."""

    target_path = Path(target_path)
    artifact_path = Path(artifact_path)
    manifest_path = Path(manifest_path)
    identity_store = Path(identity_store)
    if artifact_path.exists():
        existing = _read_json(artifact_path)
        if not _validate_self_fingerprint(existing):
            raise MultiAssetV6InputError("Crypto-Artefakt-Fingerprint ist ungültig.")
        if not target_path.exists():
            raise MultiAssetV6InputError(
                "Crypto-Artefakt existiert, aber sein immutable Store fehlt."
            )
        if existing.get("target_store_sha256") != file_sha256(target_path):
            raise MultiAssetV6InputError(
                "Crypto-Store weicht vom append-only Artefakt ab."
            )
        if (
            not manifest_path.exists()
            or existing.get("source_manifest_sha256") != file_sha256(manifest_path)
        ):
            raise MultiAssetV6InputError(
                "Frozen Manifest weicht vom Crypto-Projektionsartefakt ab."
            )
        if existing.get("projection_code_sha256") != file_sha256(Path(__file__)):
            raise MultiAssetV6InputError(
                "Crypto-Projektionscode weicht vom versionierten Artefakt ab."
            )
        expected_identity_sha256 = existing.get("identity_store_sha256")
        if expected_identity_sha256 and (
            not identity_store.exists()
            or file_sha256(identity_store) != expected_identity_sha256
        ):
            raise MultiAssetV6InputError(
                "Identity-Store weicht vom Crypto-Projektionsartefakt ab."
            )
        for relative, expected_sha256 in dict(
            existing.get("source_file_sha256") or {}
        ).items():
            source = manifest_path.parent / str(relative)
            if not source.exists() or file_sha256(source) != expected_sha256:
                raise MultiAssetV6InputError(
                    f"Frozen Crypto-Quelldatei weicht ab: {relative}"
                )
        with _read_only(target_path) as connection:
            row = connection.execute(
                "SELECT dataset_fingerprint FROM projection_versions "
                "ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            quick = connection.execute("PRAGMA quick_check").fetchone()[0]
        if (
            row is None
            or str(row[0]) != str(existing.get("dataset_fingerprint"))
            or quick != "ok"
        ):
            raise MultiAssetV6InputError(
                "Crypto-Store ist nicht integer oder besitzt einen anderen Fingerprint."
            )
        return existing
    now = created_at or datetime.now(timezone.utc).isoformat()
    use_production_expectations = assets is None
    source_manifest_payload = _read_json(manifest_path)
    source_dataset_fingerprint = source_manifest_payload.get("dataset_fingerprint")
    if use_production_expectations and not source_dataset_fingerprint:
        raise MultiAssetV6InputError(
            "Frozen Dataset-Manifest besitzt keinen Dataset-Fingerprint."
        )
    crypto_assets = _crypto_assets(assets)
    source_paths = [manifest_path.parent / str(item["modern_file"]) for item in crypto_assets]
    immutable_paths = [manifest_path, *source_paths, Path(__file__).resolve()]
    if identity_store.exists():
        immutable_paths.append(identity_store)
    before = {str(path.resolve()): file_sha256(path) for path in immutable_paths}
    projected = [_project_crypto_asset(asset, manifest_path.parent) for asset in crypto_assets]
    after = {str(path.resolve()): file_sha256(path) for path in immutable_paths}
    if before != after:
        raise MultiAssetV6InputError("Frozen Crypto-Quelle änderte sich während der Projektion.")

    if use_production_expectations:
        expected_asset_count = 30 if expected_asset_count is None else expected_asset_count
        expected_raw_bar_count = (
            33_678 if expected_raw_bar_count is None else expected_raw_bar_count
        )
        expected_active_bar_count = (
            33_675 if expected_active_bar_count is None else expected_active_bar_count
        )
        expected_invalid_bar_count = (
            3 if expected_invalid_bar_count is None else expected_invalid_bar_count
        )
        expected_no_data_symbols = (
            ("APT21794-USD",)
            if expected_no_data_symbols is None
            else expected_no_data_symbols
        )
        expected_invalid_sessions = (
            DEFAULT_EXPECTED_CRYPTO_INVALID_SESSIONS
            if expected_invalid_sessions is None
            else expected_invalid_sessions
        )
    counts = {
        "assets": len(projected),
        "raw_bars": sum(int(item["coverage"]["raw_bars"]) for item in projected),
        "active_valid_bars": sum(
            int(item["coverage"]["active_valid_bars"]) for item in projected
        ),
        "invalid_source_bars": sum(
            int(item["coverage"]["invalid_source_bars"]) for item in projected
        ),
        "no_data_assets": sum(
            int(item["coverage"]["active_valid_bars"]) == 0 for item in projected
        ),
        "source_missing_calendar_days": sum(
            int(item["coverage"]["source_missing_calendar_days"]) for item in projected
        ),
        "gap_boundaries": sum(len(item["boundaries"]) for item in projected),
    }
    actual_no_data_symbols = tuple(
        sorted(
            str(item["coverage"]["ticker"])
            for item in projected
            if int(item["coverage"]["active_valid_bars"]) == 0
        )
    )
    actual_invalid_sessions: dict[str, tuple[str, ...]] = {}
    for ticker in sorted(
        {
            str(invalid["ticker"])
            for item in projected
            for invalid in item["invalid_rows"]
        }
    ):
        actual_invalid_sessions[ticker] = tuple(
            sorted(
                str(invalid["session_date"])
                for item in projected
                for invalid in item["invalid_rows"]
                if str(invalid["ticker"]) == ticker
            )
        )
    scalar_expectations = {
        "assets": expected_asset_count,
        "raw_bars": expected_raw_bar_count,
        "active_valid_bars": expected_active_bar_count,
        "invalid_source_bars": expected_invalid_bar_count,
    }
    for field, expected in scalar_expectations.items():
        if expected is not None and int(counts[field]) != int(expected):
            raise MultiAssetV6InputError(
                f"Crypto-Projektionscoverage weicht ab: {field}="
                f"{counts[field]} erwartet={expected}"
            )
    if expected_no_data_symbols is not None and actual_no_data_symbols != tuple(
        sorted(str(item) for item in expected_no_data_symbols)
    ):
        raise MultiAssetV6InputError(
            "Crypto-NO_DATA-Klassifikation weicht vom eingefrorenen Vertrag ab."
        )
    if expected_invalid_sessions is not None:
        normalized_expected_invalid = {
            str(ticker): tuple(sorted(str(day) for day in days))
            for ticker, days in expected_invalid_sessions.items()
        }
        if actual_invalid_sessions != normalized_expected_invalid:
            raise MultiAssetV6InputError(
                "Archivierte Crypto-Invalid-Sessions weichen vom Vertrag ab."
            )

    _initialize_crypto_store(target_path)
    with sqlite3.connect(target_path) as connection:
        if connection.execute("SELECT COUNT(*) FROM projection_versions").fetchone()[0]:
            raise MultiAssetV6InputError(
                "Crypto-Store ist bereits final, aber das Artefakt fehlt."
            )
        with connection:
            for result in projected:
                for item in result["active_rows"]:
                    ohlc = dict(item["ohlc"])
                    connection.execute(
                        "INSERT INTO active_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            item["bar_id"], item["asset_id"], item["listing_id"],
                            item["ticker"], item["session_date"], ohlc["Open"],
                            ohlc["High"], ohlc["Low"], ohlc["Close"], item["volume"],
                            item["source_file"], item["source_row"],
                            item["source_history_fingerprint"], item["bar_fingerprint"],
                            item["segment_id"], item["segment_position"],
                        ),
                    )
                for item in result["invalid_rows"]:
                    connection.execute(
                        "INSERT INTO invalid_source_bars VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            item["invalid_bar_fingerprint"], item["asset_id"],
                            item["listing_id"], item["ticker"], item["session_date"],
                            item["source_file"], item["source_row"],
                            item["classification"], canonical_json(item),
                        ),
                    )
                for item in result["boundaries"]:
                    connection.execute(
                        "INSERT INTO gap_boundaries VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            item["boundary_fingerprint"], item["asset_id"],
                            item["listing_id"], item["ticker"], item["boundary_type"],
                            item.get("after_date"), item.get("before_date"),
                            item.get("missing_observations"), canonical_json(item),
                        ),
                    )
                coverage = dict(result["coverage"])
                connection.execute(
                    "INSERT INTO asset_coverage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        coverage["asset_key"], coverage["asset_id"],
                        coverage["listing_id"], coverage["ticker"], coverage["raw_bars"],
                        coverage["active_valid_bars"], coverage["invalid_source_bars"],
                        coverage["duplicate_source_rows"],
                        coverage["source_missing_calendar_days"], coverage["segment_count"],
                        coverage["coverage_status"], coverage["first_active_date"],
                        coverage["last_active_date"], canonical_json(coverage),
                    ),
                )
            active_fingerprints = [
                str(row[0])
                for row in connection.execute(
                    "SELECT bar_fingerprint FROM active_bars ORDER BY ticker,session_date"
                )
            ]
            invalid_fingerprints = [
                str(row[0])
                for row in connection.execute(
                    "SELECT invalid_bar_fingerprint FROM invalid_source_bars "
                    "ORDER BY ticker,session_date,source_row"
                )
            ]
            gap_fingerprints = [
                str(row[0])
                for row in connection.execute(
                    "SELECT boundary_fingerprint FROM gap_boundaries "
                    "ORDER BY ticker,coalesce(before_date,'9999-12-31'),boundary_type"
                )
            ]
            coverage_rows = [
                json.loads(str(row[0]))
                for row in connection.execute(
                    "SELECT coverage_json FROM asset_coverage ORDER BY asset_key"
                )
            ]
            invalid_manifest_fingerprint = fingerprint(invalid_fingerprints)
            gap_manifest_fingerprint = fingerprint(gap_fingerprints)
            dataset_fingerprint = fingerprint(
                {
                    "version": CRYPTO_PROJECTION_VERSION,
                    "source_manifest_sha256": before[str(manifest_path.resolve())],
                    "source_dataset_fingerprint": source_dataset_fingerprint,
                    "projection_code_sha256": before[str(Path(__file__).resolve())],
                    "active_bar_fingerprints": active_fingerprints,
                    "invalid_manifest_fingerprint": invalid_manifest_fingerprint,
                    "gap_manifest_fingerprint": gap_manifest_fingerprint,
                    "coverage": coverage_rows,
                    "gap_policy_fingerprint": gap_policy()["fingerprint"],
                }
            )
            manifest = {
                "version": CRYPTO_PROJECTION_VERSION,
                "dataset_fingerprint": dataset_fingerprint,
                "invalid_manifest_fingerprint": invalid_manifest_fingerprint,
                "gap_manifest_fingerprint": gap_manifest_fingerprint,
                "created_at": now,
            }
            connection.execute(
                "INSERT INTO projection_versions VALUES (?,?,?,?,?,?)",
                (
                    CRYPTO_PROJECTION_VERSION,
                    dataset_fingerprint,
                    invalid_manifest_fingerprint,
                    gap_manifest_fingerprint,
                    now,
                    canonical_json(manifest),
                ),
            )
        quick = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick != "ok":
            raise MultiAssetV6InputError(f"Crypto-Store quick_check: {quick}")

    payload: dict[str, object] = {
        "version": CRYPTO_PROJECTION_VERSION,
        "remediation_version": CRYPTO_REMEDIATION_VERSION,
        "created_at": now,
        "status": "CRYPTO_DEVELOPMENT_INPUT_READY_WITH_EXCLUSIONS",
        "period": [DEVELOPMENT_START, DEVELOPMENT_END],
        "dataset_fingerprint": dataset_fingerprint,
        "invalid_manifest_fingerprint": invalid_manifest_fingerprint,
        "gap_manifest_fingerprint": gap_manifest_fingerprint,
        "gap_policy": gap_policy(),
        "counts": counts,
        "no_data_symbols": list(actual_no_data_symbols),
        "archived_invalid_sessions": {
            ticker: list(days) for ticker, days in actual_invalid_sessions.items()
        },
        "production_coverage_expectations_enforced": use_production_expectations,
        "coverage_pct_of_source_rows": (
            round(counts["active_valid_bars"] / counts["raw_bars"] * 100, 8)
            if counts["raw_bars"]
            else 0.0
        ),
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": before[str(manifest_path.resolve())],
        "source_dataset_fingerprint": source_dataset_fingerprint,
        "projection_code_sha256": before[str(Path(__file__).resolve())],
        "identity_store_sha256": (
            before.get(str(identity_store.resolve())) if identity_store.exists() else None
        ),
        "source_file_sha256": {
            str(path.relative_to(manifest_path.parent)).replace("\\", "/"): before[
                str(path.resolve())
            ]
            for path in source_paths
        },
        "source_hashes_unchanged": before == after,
        "target_store": str(target_path.resolve()),
        "target_store_sha256": file_sha256(target_path),
        "no_downloads": True,
        "no_clipping": True,
        "no_imputation": True,
        "no_interpolation": True,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_append_only(artifact_path, payload)
    return payload


@dataclass(frozen=True)
class SegmentedAssetHistory:
    asset_class: str
    symbol: str
    frame: pd.DataFrame
    availability: Mapping[str, str]
    dataset_fingerprint: str
    combined_input_fingerprint: str | None
    gap_boundaries: tuple[Mapping[str, object], ...]
    coverage: Mapping[str, object]
    segment_end_reasons: Mapping[int, str]
    availability_status: str = "UNKNOWN"

    @property
    def source_fingerprint(self) -> str:
        """Stable projection fingerprint consumed by case identity."""

        return self.dataset_fingerprint

    @property
    def segments(self) -> tuple[pd.DataFrame, ...]:
        """Return independent frames; callers must never stitch them together."""

        if self.frame.empty:
            return ()
        return tuple(
            part.copy()
            for _, part in self.frame.groupby("SEGMENT_ID", sort=True)
        )

    @property
    def segment_metadata(self) -> tuple[Mapping[str, object], ...]:
        if self.frame.empty:
            return ()
        result: list[Mapping[str, object]] = []
        for segment_id, part in self.frame.groupby("SEGMENT_ID", sort=True):
            result.append(
                {
                    "segment_id": int(segment_id),
                    "first_date": part.index.min().date().isoformat(),
                    "last_date": part.index.max().date().isoformat(),
                    "observation_count": len(part),
                    "warmup_observations": min(MINIMUM_SEGMENT_HISTORY, len(part)),
                    "warmup_complete_position_within_segment": (
                        MINIMUM_SEGMENT_HISTORY - 1
                        if len(part) >= MINIMUM_SEGMENT_HISTORY
                        else None
                    ),
                    "first_eligible_signal_position_within_segment": (
                        MINIMUM_SEGMENT_HISTORY - 1
                        if len(part) > MINIMUM_SEGMENT_HISTORY
                        else None
                    ),
                    "end_reason": self.segment_end_reasons[int(segment_id)],
                }
            )
        return tuple(result)

    def eligible_signal_positions(self) -> list[int]:
        """Positions with 220 same-segment bars and same-segment next entry."""

        if self.frame.empty:
            return []
        segment_ids = self.frame["SEGMENT_ID"].to_numpy(dtype=int)
        segment_positions = self.frame["SEGMENT_POSITION"].to_numpy(dtype=int)
        return [
            position
            for position in range(len(self.frame) - 1)
            if segment_positions[position] >= MINIMUM_SEGMENT_HISTORY - 1
            and segment_ids[position + 1] == segment_ids[position]
        ]

    def outcome_positions(
        self, signal_position: int, *, horizon: int = 252, stage_end: str = DEVELOPMENT_END
    ) -> list[int]:
        """Return a horizon clipped before the first segment/stage boundary."""

        if signal_position < 0 or signal_position >= len(self.frame):
            raise IndexError(signal_position)
        segment_id = int(self.frame.iloc[signal_position]["SEGMENT_ID"])
        stage_limit = pd.Timestamp(stage_end)
        positions: list[int] = []
        for position in range(signal_position + 1, len(self.frame)):
            if self.frame.index[position] > stage_limit:
                break
            if int(self.frame.iloc[position]["SEGMENT_ID"]) != segment_id:
                break
            positions.append(position)
            if len(positions) == horizon:
                break
        return positions


def _stored_invalid_days(
    connection: sqlite3.Connection, table: str, ticker_column: str, symbol: str
) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            f"SELECT session_date FROM {table} WHERE {ticker_column}=? ORDER BY session_date",
            (symbol,),
        )
    ]


def _segments_for_rows(
    *,
    asset_class: str,
    ticker: str,
    rows: Sequence[Mapping[str, object]],
    invalid_days: Sequence[str],
    peer_observed_group_sessions: Sequence[str] = (),
    session_group_key: str | None = None,
) -> tuple[
    pd.DataFrame,
    tuple[Mapping[str, object], ...],
    dict[int, str],
]:
    columns = ["Date", "Open", "High", "Low", "Close", "Volume", "available_at"]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        empty = pd.DataFrame(
            columns=[
                "Open", "High", "Low", "Close", "Volume", "SEGMENT_ID",
                "SEGMENT_POSITION", "GAP_BOUNDARY_BEFORE",
            ]
        )
        empty.index = pd.DatetimeIndex([], name="Date")
        return empty, (), {}
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None).dt.normalize()
    frame = frame.sort_values("Date", kind="stable")
    if frame["Date"].duplicated().any():
        raise MultiAssetV6InputError(f"Aktive doppelte Session in {asset_class}-Input.")
    invalid = sorted(date.fromisoformat(item) for item in invalid_days)
    boundaries: list[dict[str, object]] = []
    dates = [stamp.date() for stamp in frame["Date"]]
    for invalid_day in invalid:
        previous = max((item for item in dates if item < invalid_day), default=None)
        following = min((item for item in dates if item > invalid_day), default=None)
        boundaries.append(
            {
                "boundary_type": "ARCHIVED_INVALID_SOURCE_SESSION",
                "invalid_session_date": invalid_day.isoformat(),
                "after_date": previous.isoformat() if previous else None,
                "before_date": following.isoformat() if following else None,
            }
        )
    boundaries.extend(
        _peer_observed_missing_boundaries(
            asset_class=asset_class,
            ticker=ticker,
            active_dates=dates,
            peer_observed_group_sessions=tuple(
                date.fromisoformat(str(item))
                for item in peer_observed_group_sessions
            ),
            session_group_key=session_group_key,
        )
    )
    boundaries.sort(
        key=lambda item: (
            str(item.get("before_date") or "9999-12-31"),
            str(item["boundary_type"]),
            str(item.get("invalid_session_date") or ""),
        )
    )
    segment_starts = {
        str(item["before_date"])
        for item in boundaries
        if item.get("before_date") is not None
    }
    segment_id = 0
    segment_position = 0
    ids: list[int] = []
    positions: list[int] = []
    boundary_before: list[bool] = []
    for index, stamp in enumerate(frame["Date"]):
        start = stamp.date().isoformat() in segment_starts
        if index and start:
            segment_id += 1
            segment_position = 0
        ids.append(segment_id)
        positions.append(segment_position)
        boundary_before.append(start)
        segment_position += 1
    frame["SEGMENT_ID"] = ids
    frame["SEGMENT_POSITION"] = positions
    frame["GAP_BOUNDARY_BEFORE"] = boundary_before
    end_reasons: dict[int, str] = {}
    for boundary in boundaries:
        before = boundary.get("before_date")
        if before is not None:
            matching = frame.index[frame["Date"].dt.date.astype(str) == str(before)]
            if len(matching):
                start_row = int(matching[0])
                next_segment = int(ids[start_row])
                if next_segment > 0:
                    prior_segment = next_segment - 1
                    reason = str(boundary["boundary_type"])
                    existing = end_reasons.get(prior_segment)
                    end_reasons[prior_segment] = (
                        reason if existing is None else "+".join(sorted({existing, reason}))
                    )
        elif boundary.get("after_date") is not None:
            reason = str(boundary["boundary_type"])
            last_segment = int(ids[-1])
            existing = end_reasons.get(last_segment)
            end_reasons[last_segment] = (
                reason if existing is None else "+".join(sorted({existing, reason}))
            )
    last_segment = int(ids[-1])
    end_reasons.setdefault(last_segment, "END_OF_AVAILABLE_DEVELOPMENT_DATA")
    frame["SEGMENT_END_REASON"] = [end_reasons[int(item)] for item in ids]
    frame = frame.set_index("Date")
    return frame, tuple(boundaries), end_reasons


def load_segmented_asset_history(
    asset_class: str,
    symbol: str,
    *,
    equity_etf_store: Path = DEFAULT_EQUITY_ETF_STORE,
    crypto_store: Path = DEFAULT_CRYPTO_STORE,
    fx_store: Path = DEFAULT_FX_STORE,
    combined_input_fingerprint: str | None = None,
    peer_observed_group_sessions: Sequence[str] = (),
    session_group_key: str | None = None,
) -> SegmentedAssetHistory:
    """Load one active history and mark all conservative continuity segments."""

    asset_class = asset_class.upper()
    rows: list[dict[str, object]] = []
    invalid_days: list[str] = []
    availability: dict[str, str] = {}
    coverage: dict[str, object] = {}
    if asset_class in {"EQUITIES", "ETF"}:
        with _read_only(equity_etf_store) as connection:
            rows = [
                {
                    "Date": row[0], "Open": row[1], "High": row[2], "Low": row[3],
                    "Close": row[4], "Volume": row[5], "available_at": None,
                }
                for row in connection.execute(
                    "SELECT session_date,open,high,low,close,volume FROM active_bars "
                    "WHERE asset_class=? AND ticker=? ORDER BY session_date",
                    (asset_class, symbol),
                )
            ]
            invalid_days = [
                str(row[0])
                for row in connection.execute(
                    "SELECT session_date FROM invalid_source_bars "
                    "WHERE asset_class=? AND ticker=? ORDER BY session_date",
                    (asset_class, symbol),
                )
            ]
            record = connection.execute(
                "SELECT coverage_json FROM asset_coverage WHERE asset_class=? AND ticker=?",
                (asset_class, symbol),
            ).fetchone()
            version = connection.execute(
                "SELECT dataset_fingerprint FROM projection_versions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        if record is None:
            raise MultiAssetV6InputError(
                f"Asset fehlt in Equity/ETF-Coverage: {asset_class}:{symbol}"
            )
        coverage = json.loads(str(record[0]))
        if not version:
            raise MultiAssetV6InputError("Equity/ETF-Projektionsfingerprint fehlt.")
        dataset_fingerprint = str(version[0])
    elif asset_class == "CRYPTO":
        with _read_only(crypto_store) as connection:
            rows = [
                {
                    "Date": row[0], "Open": row[1], "High": row[2], "Low": row[3],
                    "Close": row[4], "Volume": row[5], "available_at": None,
                }
                for row in connection.execute(
                    "SELECT session_date,open,high,low,close,volume FROM active_bars "
                    "WHERE ticker=? ORDER BY session_date",
                    (symbol,),
                )
            ]
            invalid_days = _stored_invalid_days(
                connection, "invalid_source_bars", "ticker", symbol
            )
            record = connection.execute(
                "SELECT coverage_json FROM asset_coverage WHERE ticker=?", (symbol,)
            ).fetchone()
            version = connection.execute(
                "SELECT dataset_fingerprint FROM projection_versions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        if record is None:
            raise MultiAssetV6InputError(
                f"Asset fehlt in Crypto-Coverage: {symbol}"
            )
        coverage = json.loads(str(record[0]))
        if not version:
            raise MultiAssetV6InputError("Crypto-Projektionsfingerprint fehlt.")
        dataset_fingerprint = str(version[0])
    elif asset_class == "FX":
        if symbol not in default_fx_pair_contracts():
            raise MultiAssetV6InputError(f"FX-Paar fehlt im PIT-Vertrag: {symbol}")
        with _read_only(fx_store) as connection:
            records = connection.execute(
                "SELECT record_json FROM historical_fx_records WHERE pair_id=? "
                "AND feature='PRICE' AND pit_eligible=1 "
                "AND observation_date BETWEEN ? AND ? ORDER BY observation_date",
                (symbol, DEVELOPMENT_START, DEVELOPMENT_END),
            ).fetchall()
            for (record_json,) in records:
                record = json.loads(str(record_json))
                normalized = normalize_fx_ohlc(
                    default_fx_pair_contracts()[symbol],
                    dict(record["metadata"]["ohlc"]),
                )
                row = {
                    "Date": record["observation_date"],
                    **{name.title(): value for name, value in normalized.items()},
                    "Volume": None,
                    "available_at": record["available_at"],
                }
                rows.append(row)
                availability[str(record["observation_date"])] = str(record["available_at"])
            invalid_days = [
                str(row[0])
                for row in connection.execute(
                    "SELECT observation_date FROM historical_fx_invalid_bars "
                    "WHERE pair_id=? AND observation_date BETWEEN ? AND ? "
                    "ORDER BY observation_date",
                    (symbol, DEVELOPMENT_START, DEVELOPMENT_END),
                )
            ]
            version = connection.execute(
                "SELECT dataset_fingerprint FROM fx_dataset_versions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        if not version:
            raise MultiAssetV6InputError("FX-v2-Fingerprint fehlt.")
        dataset_fingerprint = str(version[0])
        coverage = {
            "asset_key": f"FX:{symbol}",
            "active_valid_bars": len(rows),
            "invalid_source_bars": len(invalid_days),
        }
    else:
        raise MultiAssetV6InputError(f"Unbekannte Assetklasse: {asset_class}")
    frame, boundaries, end_reasons = _segments_for_rows(
        asset_class=asset_class,
        ticker=symbol,
        rows=rows,
        invalid_days=invalid_days,
        peer_observed_group_sessions=peer_observed_group_sessions,
        session_group_key=session_group_key,
    )
    return SegmentedAssetHistory(
        asset_class=asset_class,
        symbol=symbol,
        frame=frame,
        availability_status=str(
            coverage.get("coverage_status")
            or ("AVAILABLE" if not frame.empty else "NO_DATA")
        ),
        availability=availability,
        dataset_fingerprint=dataset_fingerprint,
        combined_input_fingerprint=combined_input_fingerprint,
        gap_boundaries=boundaries,
        coverage=coverage,
        segment_end_reasons=end_reasons,
    )


def load_v6_asset_history(
    asset: Mapping[str, object],
    *,
    input_precheck_artifact: Path = DEFAULT_INPUT_PRECHECK_ARTIFACT,
    input_precheck: Mapping[str, object] | None = None,
    equity_etf_store: Path = DEFAULT_EQUITY_ETF_STORE,
    crypto_store: Path = DEFAULT_CRYPTO_STORE,
    fx_store: Path = DEFAULT_FX_STORE,
    verify_store_sha256: bool = True,
) -> SegmentedAssetHistory:
    """Runner-facing, fail-closed loader bound to one PASS precheck artifact."""

    precheck = (
        dict(input_precheck)
        if input_precheck is not None
        else _read_cached_input_precheck(Path(input_precheck_artifact))
    )
    if not _validate_self_fingerprint(precheck) or precheck.get("status") != "PASS":
        raise MultiAssetV6InputError("v6-Input-Precheck ist nicht selbstgültig/PASS.")
    inputs = dict(precheck.get("contract_inputs") or {})
    asset_class = str(asset.get("asset_class") or "").upper()
    symbol = str(asset.get("symbol") or asset.get("ticker") or asset.get("pair_id") or "")
    consensus = _validated_peer_session_consensus(precheck)
    consensus_fingerprint = str(consensus["fingerprint"])
    policy = dict(precheck.get("gap_policy") or {})
    stated_policy_fingerprint = str(policy.pop("fingerprint", ""))
    if (
        not stated_policy_fingerprint
        or fingerprint(policy) != stated_policy_fingerprint
        or stated_policy_fingerprint != str(inputs.get("gap_policy_fingerprint") or "")
        or str(policy.get("peer_session_consensus_fingerprint") or "")
        != consensus_fingerprint
    ):
        raise MultiAssetV6InputError(
            "v6-Gap-Policy ist nicht an den Session-Konsens gebunden."
        )
    asset_key = f"{asset_class}:{symbol}"
    group_key = dict(consensus.get("asset_group_keys") or {}).get(asset_key)
    if asset_class in {"EQUITIES", "ETF", "FX"} and not group_key:
        raise MultiAssetV6InputError(
            f"Asset fehlt im fingerprinted Session-Konsens: {asset_key}"
        )
    group_sessions = tuple(
        str(item)
        for item in dict(consensus.get("groups") or {}).get(str(group_key), ())
    )
    history = load_segmented_asset_history(
        asset_class,
        symbol,
        equity_etf_store=equity_etf_store,
        crypto_store=crypto_store,
        fx_store=fx_store,
        combined_input_fingerprint=str(inputs["combined_input_fingerprint"]),
        peer_observed_group_sessions=group_sessions,
        session_group_key=str(group_key) if group_key else None,
    )
    key = {
        "EQUITIES": "equity_etf_projection_fingerprint",
        "ETF": "equity_etf_projection_fingerprint",
        "CRYPTO": "crypto_projection_fingerprint",
        "FX": "fx_projection_fingerprint",
    }.get(asset_class)
    store_path, store_sha_key = {
        "EQUITIES": (Path(equity_etf_store), "equity_etf_store_sha256"),
        "ETF": (Path(equity_etf_store), "equity_etf_store_sha256"),
        "CRYPTO": (Path(crypto_store), "crypto_store_sha256"),
        "FX": (Path(fx_store), "fx_store_sha256"),
    }.get(asset_class, (Path(), ""))
    if key is None or history.dataset_fingerprint != str(inputs.get(key)):
        raise MultiAssetV6InputError(
            f"Asset-Historie weicht vom PASS-Input-Precheck ab: {asset_class}:{symbol}"
        )
    if verify_store_sha256 and not _matches_immutable_sha256(
        store_path, inputs.get(store_sha_key)
    ):
        raise MultiAssetV6InputError(
            f"Input-Store-Hash weicht vom PASS-Precheck ab: {asset_class}:{symbol}"
        )
    return history


def _validate_self_fingerprint(payload: Mapping[str, object]) -> bool:
    return _named_fingerprint_is_valid(payload, "artifact_fingerprint")


def _identity_records(
    path: Path,
) -> tuple[dict[str, dict[str, object]], str, tuple[str, ...], bool]:
    with _read_only(path) as connection:
        row = connection.execute(
            "SELECT registry_json FROM registry_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise MultiAssetV6InputError("Identity-Registry ist leer.")
    registry = json.loads(str(row[0]))
    raw_records = [dict(item) for item in registry.get("records") or []]
    tickers = [str(item.get("ticker") or "") for item in raw_records]
    duplicates = tuple(
        sorted({ticker for ticker in tickers if tickers.count(ticker) > 1})
    )
    records = {str(item["ticker"]): item for item in raw_records if item.get("ticker")}
    registry_fingerprint = str(registry.get("registry_fingerprint") or "")
    basis = dict(registry)
    basis.pop("registry_fingerprint", None)
    return (
        records,
        registry_fingerprint,
        duplicates,
        bool(registry_fingerprint) and fingerprint(basis) == registry_fingerprint,
    )


def _mic_session_group_key(
    *,
    asset_class: str,
    ticker: str,
    identity_records: Mapping[str, Mapping[str, object]],
) -> str:
    record = identity_records.get(ticker)
    mic = str((record or {}).get("mic") or "").strip().upper()
    if not mic:
        raise MultiAssetV6InputError(
            f"Frozen MIC fuer Session-Konsens fehlt: {asset_class}:{ticker}"
        )
    return f"MIC:{mic}"


def _peer_session_consensus_payload(
    *,
    equity_groups: Mapping[str, Sequence[str]],
    equity_asset_groups: Mapping[str, str],
    fx_groups: Mapping[str, Sequence[str]],
    fx_asset_groups: Mapping[str, str],
    identity_registry_fingerprint: str,
) -> dict[str, object]:
    groups = {
        str(key): sorted({str(day) for day in days})
        for key, days in {
            **dict(equity_groups),
            **dict(fx_groups),
        }.items()
    }
    asset_group_keys = {
        str(key): str(value)
        for key, value in sorted(
            {
                **dict(equity_asset_groups),
                **dict(fx_asset_groups),
            }.items()
        )
    }
    group_member_counts = {
        group_key: sum(value == group_key for value in asset_group_keys.values())
        for group_key in sorted(groups)
    }
    payload: dict[str, object] = {
        "version": PEER_SESSION_CONSENSUS_VERSION,
        "method": "UNION_OF_ACTIVE_BARS_WITHIN_FROZEN_SESSION_GROUP",
        "equities_etf_group_source": "FROZEN_IDENTITY_REGISTRY_MIC",
        "fx_group_source": "FROZEN_THREE_PAIR_ACTIVE_SESSION_UNION",
        "identity_registry_fingerprint": identity_registry_fingerprint,
        "official_exchange_or_fx_calendar_asserted": False,
        "dates_without_any_active_group_observation_asserted_as_sessions": False,
        "limitation": (
            "Observed peer consensus detects a target omission only when at least "
            "one other frozen group member has an active bar. Group-wide omissions "
            "remain unknown and are not silently labelled trading sessions."
        ),
        "groups": groups,
        "asset_group_keys": asset_group_keys,
        "group_member_counts": group_member_counts,
    }
    payload["fingerprint"] = fingerprint(payload)
    return payload


def _validated_peer_session_consensus(
    precheck: Mapping[str, object],
) -> dict[str, object]:
    raw = precheck.get("peer_session_consensus")
    if not isinstance(raw, Mapping):
        raise MultiAssetV6InputError(
            "v6-Input-Precheck enthaelt keinen Session-Konsens."
        )
    consensus = dict(raw)
    stated_fingerprint = str(consensus.pop("fingerprint", ""))
    if (
        not stated_fingerprint
        or fingerprint(consensus) != stated_fingerprint
        or consensus.get("version") != PEER_SESSION_CONSENSUS_VERSION
        or consensus.get("official_exchange_or_fx_calendar_asserted") is not False
        or consensus.get(
            "dates_without_any_active_group_observation_asserted_as_sessions"
        )
        is not False
    ):
        raise MultiAssetV6InputError(
            "v6-Session-Konsens ist nicht vollstaendig/fingerprint-gueltig."
        )
    consensus["fingerprint"] = stated_fingerprint
    return consensus


def _audit_projection_store(
    path: Path,
    *,
    asset_classes: set[str],
    identity_records: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    violations = 0
    row_count = 0
    assets: set[tuple[str, str]] = set()
    identity_rows: set[tuple[str, str, str, str]] = set()
    active_sessions: set[tuple[str, str, str]] = set()
    active_dates: dict[tuple[str, str], list[date]] = {}
    active_by_asset: dict[tuple[str, str], int] = {}
    invalid_by_asset: dict[tuple[str, str], int] = {}
    invalid_sessions: set[tuple[str, str, str]] = set()
    source_history_fingerprints: set[str] = set()
    session_group_dates: dict[str, set[str]] = {}
    session_group_by_asset: dict[str, str] = {}
    with _read_only(path) as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(active_bars)")}
        has_class = "asset_class" in columns
        query = (
            "SELECT asset_id,listing_id,ticker,asset_class,session_date,open,high,low,close,"
            "source_history_fingerprint "
            "FROM active_bars ORDER BY asset_class,ticker,session_date"
            if has_class
            else "SELECT asset_id,listing_id,ticker,'CRYPTO',session_date,open,high,low,close,"
            "source_history_fingerprint "
            "FROM active_bars ORDER BY ticker,session_date"
        )
        for (
            asset_id,
            listing_id,
            ticker,
            asset_class,
            day,
            open_,
            high,
            low,
            close,
            source_history_fingerprint,
        ) in connection.execute(query):
            asset_class = str(asset_class)
            ticker = str(ticker)
            session_day = str(day)
            if asset_class not in asset_classes:
                violations += 1
            values = [float(open_), float(high), float(low), float(close)]
            if not all(math.isfinite(value) and value > 0 for value in values):
                violations += 1
            if not (float(low) <= float(open_) <= float(high)):
                violations += 1
            if not (float(low) <= float(close) <= float(high)):
                violations += 1
            row_count += 1
            asset_key = (asset_class, ticker)
            assets.add(asset_key)
            active_by_asset[asset_key] = active_by_asset.get(asset_key, 0) + 1
            active_sessions.add((asset_class, ticker, session_day))
            active_dates.setdefault(asset_key, []).append(date.fromisoformat(session_day))
            if asset_class in {"EQUITIES", "ETF"}:
                group_key = _mic_session_group_key(
                    asset_class=asset_class,
                    ticker=ticker,
                    identity_records=identity_records or {},
                )
                session_group_dates.setdefault(group_key, set()).add(session_day)
                session_group_by_asset[f"{asset_class}:{ticker}"] = group_key
            identity_rows.add(
                (
                    ticker,
                    asset_class,
                    "" if asset_id is None else str(asset_id),
                    "" if listing_id is None else str(listing_id),
                )
            )
            if source_history_fingerprint:
                source_history_fingerprints.add(str(source_history_fingerprint))
        group = "asset_class,ticker,session_date" if has_class else "ticker,session_date"
        duplicate_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM (SELECT 1 FROM active_bars GROUP BY {group} HAVING COUNT(*)>1)"
            ).fetchone()[0]
        )
        invalid_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(invalid_source_bars)")
        }
        invalid_has_class = "asset_class" in invalid_columns
        invalid_query = (
            "SELECT asset_id,listing_id,ticker,asset_class,session_date "
            "FROM invalid_source_bars ORDER BY asset_class,ticker,session_date"
            if invalid_has_class
            else "SELECT asset_id,listing_id,ticker,'CRYPTO',session_date "
            "FROM invalid_source_bars ORDER BY ticker,session_date"
        )
        invalid_row_count = 0
        for asset_id, listing_id, ticker, asset_class, day in connection.execute(
            invalid_query
        ):
            invalid_row_count += 1
            asset_key = (str(asset_class), str(ticker))
            invalid_by_asset[asset_key] = invalid_by_asset.get(asset_key, 0) + 1
            invalid_sessions.add((str(asset_class), str(ticker), str(day)))
            identity_rows.add(
                (
                    str(ticker),
                    str(asset_class),
                    "" if asset_id is None else str(asset_id),
                    "" if listing_id is None else str(listing_id),
                )
            )
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        stored_gap_boundaries: list[dict[str, object]] | None = None
        if "gap_boundaries" in tables:
            stored_gap_boundaries = [
                json.loads(str(row[0]))
                for row in connection.execute(
                    "SELECT boundary_json FROM gap_boundaries "
                    "ORDER BY ticker,coalesce(before_date,'9999-12-31'),boundary_type"
                )
            ]
        coverage = [
            json.loads(str(row[0]))
            for row in connection.execute(
                "SELECT coverage_json FROM asset_coverage ORDER BY asset_key"
            )
        ]
        version = connection.execute(
            "SELECT dataset_fingerprint FROM projection_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
    if version is None:
        raise MultiAssetV6InputError(f"Projektionsversion fehlt: {path}")
    singleton_class = next(iter(asset_classes)) if len(asset_classes) == 1 else None
    coverage_mismatches: list[dict[str, object]] = []
    for item in coverage:
        asset_class = str(item.get("asset_class") or singleton_class or "")
        ticker = str(item.get("ticker") or "")
        asset_key = (asset_class, ticker)
        actual_active = active_by_asset.get(asset_key, 0)
        actual_invalid = invalid_by_asset.get(asset_key, 0)
        if (
            not asset_class
            or not ticker
            or int(item.get("active_valid_bars") or 0) != actual_active
            or int(item.get("invalid_source_bars") or 0) != actual_invalid
        ):
            coverage_mismatches.append(
                {
                    "asset_class": asset_class,
                    "ticker": ticker,
                    "declared_active": int(item.get("active_valid_bars") or 0),
                    "actual_active": actual_active,
                    "declared_invalid": int(item.get("invalid_source_bars") or 0),
                    "actual_invalid": actual_invalid,
                }
            )
        identity_rows.add(
            (
                ticker,
                asset_class,
                str(item.get("asset_id") or ""),
                str(item.get("listing_id") or ""),
            )
        )
        if asset_class in {"EQUITIES", "ETF"}:
            group_key = _mic_session_group_key(
                asset_class=asset_class,
                ticker=ticker,
                identity_records=identity_records or {},
            )
            session_group_by_asset[f"{asset_class}:{ticker}"] = group_key
    observed_missing_session_boundaries: list[dict[str, object]] = []
    for (asset_class, ticker), values in sorted(active_dates.items()):
        group_key = session_group_by_asset.get(f"{asset_class}:{ticker}")
        observed_missing_session_boundaries.extend(
            _peer_observed_missing_boundaries(
                asset_class=asset_class,
                ticker=ticker,
                active_dates=values,
                peer_observed_group_sessions=tuple(
                    date.fromisoformat(day)
                    for day in sorted(session_group_dates.get(group_key or "", set()))
                ),
                session_group_key=group_key,
            )
        )
    invalid_session_rows = [
        {"asset_class": item[0], "ticker": item[1], "session_date": item[2]}
        for item in sorted(invalid_sessions)
    ]
    gap_manifest = [
        *(
            {
                **item,
                "boundary_type": "ARCHIVED_INVALID_SOURCE_SESSION",
            }
            for item in invalid_session_rows
        ),
        *observed_missing_session_boundaries,
    ]
    invalid_dates_by_asset: dict[tuple[str, str], list[date]] = {}
    for asset_class, ticker, day in invalid_sessions:
        invalid_dates_by_asset.setdefault((asset_class, ticker), []).append(
            date.fromisoformat(day)
        )
    naive_eligible_positions = sum(
        max(len(values) - MINIMUM_SEGMENT_HISTORY, 0)
        for values in active_dates.values()
    )
    eligible_positions = sum(
        _eligible_positions_after_gap_policy(
            asset_class=asset_class,
            ticker=ticker,
            active_dates=values,
            invalid_days=invalid_dates_by_asset.get((asset_class, ticker), ()),
            peer_observed_group_sessions=tuple(
                date.fromisoformat(day)
                for day in sorted(
                    session_group_dates.get(
                        session_group_by_asset.get(f"{asset_class}:{ticker}", ""),
                        set(),
                    )
                )
            ),
            session_group_key=session_group_by_asset.get(
                f"{asset_class}:{ticker}"
            ),
        )
        for (asset_class, ticker), values in active_dates.items()
    )
    return {
        "dataset_fingerprint": str(version[0]),
        "active_rows": row_count,
        "active_assets": len(assets),
        "coverage_assets": len(coverage),
        "no_data_assets": sum(
            int(item.get("active_valid_bars") or 0) == 0 for item in coverage
        ),
        "invalid_source_bars": invalid_row_count,
        "invalid_source_sessions": len(invalid_sessions),
        "archived_invalid_gap_boundaries": len(invalid_sessions),
        "observed_missing_session_boundaries": len(
            observed_missing_session_boundaries
        ),
        "gap_boundary_count": len(gap_manifest),
        "gap_boundary_manifest_fingerprint": fingerprint(gap_manifest),
        "materialized_gap_boundary_count": (
            len(stored_gap_boundaries)
            if stored_gap_boundaries is not None
            else None
        ),
        "materialized_archived_invalid_gap_boundaries": (
            sum(
                str(item.get("boundary_type"))
                == "ARCHIVED_INVALID_SOURCE_SESSION"
                for item in stored_gap_boundaries
            )
            if stored_gap_boundaries is not None
            else None
        ),
        "invalid_sessions": invalid_session_rows,
        "duplicate_active_sessions": duplicate_count,
        "invalid_active_session_overlap_count": len(
            invalid_sessions.intersection(active_sessions)
        ),
        "ohlc_violation_count": violations,
        "coverage_mismatch_count": len(coverage_mismatches),
        "coverage_mismatches": coverage_mismatches,
        "quick_check": quick,
        "identity_rows": sorted(identity_rows),
        "source_history_fingerprint_count": len(source_history_fingerprints),
        "naive_eligible_signal_position_upper_bound": naive_eligible_positions,
        "eligible_signal_positions_after_gap_warmup": eligible_positions,
        "gap_warmup_position_reduction": (
            naive_eligible_positions - eligible_positions
        ),
        "session_consensus_groups": {
            key: sorted(values) for key, values in sorted(session_group_dates.items())
        },
        "session_group_by_asset": dict(sorted(session_group_by_asset.items())),
    }


def _audit_fx_store(path: Path) -> dict[str, object]:
    rows = 0
    violations = 0
    pairs: set[str] = set()
    active_sessions: set[tuple[str, str]] = set()
    active_dates: dict[str, list[date]] = {}
    record_identity_violations = 0
    availability_violations = 0
    with _read_only(path) as connection:
        for pair, day, record_json in connection.execute(
            "SELECT pair_id,observation_date,record_json FROM historical_fx_records "
            "WHERE feature='PRICE' AND pit_eligible=1 AND observation_date BETWEEN ? AND ? "
            "ORDER BY pair_id,observation_date",
            (DEVELOPMENT_START, DEVELOPMENT_END),
        ):
            record = json.loads(str(record_json))
            if (
                str(record.get("pair_id")) != str(pair)
                or str(record.get("observation_date")) != str(day)
                or str(record.get("feature")) != "PRICE"
                or record.get("pit_eligible") is not True
            ):
                record_identity_violations += 1
            try:
                available_at = pd.Timestamp(record.get("available_at"))
                if pd.isna(available_at):
                    availability_violations += 1
            except (TypeError, ValueError):
                availability_violations += 1
            normalized = normalize_fx_ohlc(
                default_fx_pair_contracts()[str(pair)],
                dict(record["metadata"]["ohlc"]),
            )
            values = [float(normalized[name]) for name in ("open", "high", "low", "close")]
            if not all(math.isfinite(value) and value > 0 for value in values):
                violations += 1
            if not (values[2] <= values[0] <= values[1]):
                violations += 1
            if not (values[2] <= values[3] <= values[1]):
                violations += 1
            rows += 1
            pair = str(pair)
            day = str(day)
            pairs.add(pair)
            active_sessions.add((pair, day))
            active_dates.setdefault(pair, []).append(date.fromisoformat(day))
        duplicates = int(
            connection.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM historical_fx_records "
                "WHERE feature='PRICE' AND pit_eligible=1 "
                "AND observation_date BETWEEN ? AND ? "
                "GROUP BY pair_id,observation_date HAVING COUNT(*)>1)",
                (DEVELOPMENT_START, DEVELOPMENT_END),
            ).fetchone()[0]
        )
        invalid_rows = connection.execute(
                "SELECT pair_id,observation_date FROM historical_fx_invalid_bars "
                "WHERE observation_date BETWEEN ? AND ?",
                (DEVELOPMENT_START, DEVELOPMENT_END),
            ).fetchall()
        invalid_sessions = {(str(row[0]), str(row[1])) for row in invalid_rows}
        invalid = len(invalid_rows)
        version = connection.execute(
            "SELECT dataset_fingerprint FROM fx_dataset_versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
    if version is None:
        raise MultiAssetV6InputError("FX-v2-Version fehlt.")
    fx_group_key = "FX:FROZEN_THREE_PAIR_ACTIVE_SESSION_UNION"
    fx_group_dates = sorted(
        {day.isoformat() for values in active_dates.values() for day in values}
    )
    fx_group_date_objects = tuple(date.fromisoformat(day) for day in fx_group_dates)
    observed_missing_session_boundaries: list[dict[str, object]] = []
    for pair, values in sorted(active_dates.items()):
        observed_missing_session_boundaries.extend(
            _peer_observed_missing_boundaries(
                asset_class="FX",
                ticker=pair,
                active_dates=values,
                peer_observed_group_sessions=fx_group_date_objects,
                session_group_key=fx_group_key,
            )
        )
    invalid_session_rows = [
        {"asset_class": "FX", "ticker": pair, "session_date": day}
        for pair, day in sorted(invalid_sessions)
    ]
    gap_manifest = [
        *(
            {**item, "boundary_type": "ARCHIVED_INVALID_SOURCE_SESSION"}
            for item in invalid_session_rows
        ),
        *observed_missing_session_boundaries,
    ]
    invalid_dates_by_pair: dict[str, list[date]] = {}
    for pair, day in invalid_sessions:
        invalid_dates_by_pair.setdefault(pair, []).append(date.fromisoformat(day))
    naive_eligible_positions = sum(
        max(len(values) - MINIMUM_SEGMENT_HISTORY, 0)
        for values in active_dates.values()
    )
    eligible_positions = sum(
        _eligible_positions_after_gap_policy(
            asset_class="FX",
            ticker=pair,
            active_dates=values,
            invalid_days=invalid_dates_by_pair.get(pair, ()),
            peer_observed_group_sessions=fx_group_date_objects,
            session_group_key=fx_group_key,
        )
        for pair, values in active_dates.items()
    )
    return {
        "dataset_fingerprint": str(version[0]),
        "active_rows": rows,
        "active_assets": len(pairs),
        "coverage_assets": len(pairs),
        "no_data_assets": 0,
        "invalid_source_bars": invalid,
        "invalid_source_sessions": len(invalid_sessions),
        "archived_invalid_gap_boundaries": len(invalid_sessions),
        "observed_missing_session_boundaries": len(
            observed_missing_session_boundaries
        ),
        "gap_boundary_count": len(gap_manifest),
        "gap_boundary_manifest_fingerprint": fingerprint(gap_manifest),
        "invalid_sessions": invalid_session_rows,
        "duplicate_active_sessions": duplicates,
        "invalid_active_session_overlap_count": len(
            invalid_sessions.intersection(active_sessions)
        ),
        "ohlc_violation_count": violations,
        "record_identity_violation_count": record_identity_violations,
        "availability_violation_count": availability_violations,
        "coverage_mismatch_count": 0,
        "quick_check": quick,
        "pairs": sorted(pairs),
        "naive_eligible_signal_position_upper_bound": naive_eligible_positions,
        "eligible_signal_positions_after_gap_warmup": eligible_positions,
        "gap_warmup_position_reduction": (
            naive_eligible_positions - eligible_positions
        ),
        "session_consensus_groups": {fx_group_key: fx_group_dates},
        "session_group_by_asset": {
            f"FX:{pair}": fx_group_key for pair in sorted(pairs)
        },
    }


def build_v6_input_precheck(
    *,
    equity_etf_store: Path = DEFAULT_EQUITY_ETF_STORE,
    equity_etf_artifact: Path = DEFAULT_EQUITY_ETF_ARTIFACT,
    crypto_store: Path = DEFAULT_CRYPTO_STORE,
    crypto_artifact: Path = DEFAULT_CRYPTO_ARTIFACT,
    fx_store: Path = DEFAULT_FX_STORE,
    fx_artifact: Path = DEFAULT_FX_ARTIFACT,
    dataset_manifest: Path = DEFAULT_DATASET_MANIFEST,
    identity_store: Path = DEFAULT_IDENTITY_STORE,
    implementation_paths: Sequence[Path] | None = None,
    expected_asset_counts: Mapping[str, int] | None = None,
    expected_no_data_counts: Mapping[str, int] | None = None,
    expected_active_bar_counts: Mapping[str, int] | None = None,
    expected_invalid_bar_counts: Mapping[str, int] | None = None,
    expected_eligible_signal_position_counts: Mapping[str, int] | None = None,
    expected_crypto_invalid_sessions: Mapping[str, Sequence[str]] | None = None,
    artifact_path: Path = DEFAULT_INPUT_PRECHECK_ARTIFACT,
    created_at: str | None = None,
) -> dict[str, object]:
    """Audit all active inputs and emit the only v6 input start-gate artifact."""

    artifact_path = Path(artifact_path)
    existing_payload: dict[str, object] | None = None
    if artifact_path.exists():
        existing_payload = _read_json(artifact_path)
        if not _validate_self_fingerprint(existing_payload):
            raise MultiAssetV6InputError(
                "Vorhandener v6-Input-Precheck besitzt einen ungültigen Fingerprint."
            )
        if created_at is None:
            created_at = str(existing_payload.get("created_at") or "")
    sources = {
        "equity_etf_store": Path(equity_etf_store),
        "crypto_store": Path(crypto_store),
        "fx_store": Path(fx_store),
        "dataset_manifest": Path(dataset_manifest),
        "identity_store": Path(identity_store),
        "equity_etf_artifact": Path(equity_etf_artifact),
        "crypto_artifact": Path(crypto_artifact),
        "fx_artifact": Path(fx_artifact),
    }
    missing = [name for name, path in sources.items() if not path.exists()]
    implementation_paths = tuple(
        Path(path)
        for path in (
            default_implementation_paths()
            if implementation_paths is None
            else implementation_paths
        )
    )
    implementation_provenance = build_v6_implementation_provenance(
        implementation_paths
    )
    missing_implementation = list(
        implementation_provenance["missing_implementation_files"]
    )
    if missing:
        raise MultiAssetV6InputError(f"Pflichtinputs fehlen: {missing}")
    equity_artifact_payload = _read_json(sources["equity_etf_artifact"])
    crypto_artifact_payload = _read_json(sources["crypto_artifact"])
    fx_artifact_payload = _read_json(sources["fx_artifact"])
    dataset_manifest_payload = _read_json(sources["dataset_manifest"])
    manifest_root = sources["dataset_manifest"].resolve().parent
    for relative in sorted(dict(crypto_artifact_payload.get("source_file_sha256") or {})):
        source_path = (manifest_root / relative).resolve()
        try:
            source_path.relative_to(manifest_root)
        except ValueError as exc:
            raise MultiAssetV6InputError(
                f"Crypto-Quellpfad verlässt das Frozen Dataset: {relative}"
            ) from exc
        sources[f"crypto_frozen:{relative}"] = source_path
    missing = [name for name, path in sources.items() if not path.exists()]
    if missing:
        raise MultiAssetV6InputError(f"Pflichtinputs fehlen: {missing}")
    source_paths = _canonical_source_paths(
        sources,
        dataset_manifest=sources["dataset_manifest"],
        artifact_path=artifact_path,
    )
    before = {name: file_sha256(path) for name, path in sources.items()}
    (
        identity,
        identity_fingerprint,
        duplicate_identity_tickers,
        identity_registry_fingerprint_valid,
    ) = _identity_records(sources["identity_store"])
    equity = _audit_projection_store(
        sources["equity_etf_store"],
        asset_classes={"EQUITIES", "ETF"},
        identity_records=identity,
    )
    crypto = _audit_projection_store(
        sources["crypto_store"], asset_classes={"CRYPTO"}
    )
    fx = _audit_fx_store(sources["fx_store"])
    equity_identity_rows = equity.pop("identity_rows")
    crypto_identity_rows = crypto.pop("identity_rows")
    equity_invalid_sessions = equity.pop("invalid_sessions")
    crypto_invalid_sessions = crypto.pop("invalid_sessions")
    fx_invalid_sessions = fx.pop("invalid_sessions")
    peer_session_consensus = _peer_session_consensus_payload(
        equity_groups=equity.pop("session_consensus_groups"),
        equity_asset_groups=equity.pop("session_group_by_asset"),
        fx_groups=fx.pop("session_consensus_groups"),
        fx_asset_groups=fx.pop("session_group_by_asset"),
        identity_registry_fingerprint=identity_fingerprint,
    )
    # Crypto uses the explicit every-calendar-day rule and therefore has no
    # peer-session group.  Consume the empty audit internals so they cannot be
    # mistaken for an unbound input later in the artifact.
    crypto.pop("session_consensus_groups")
    crypto.pop("session_group_by_asset")
    identity_mismatches: list[dict[str, str]] = []
    for ticker, asset_class, asset_id, listing_id in [
        *equity_identity_rows,
        *crypto_identity_rows,
    ]:
        record = identity.get(ticker)
        normalized_class = (
            "CRYPTO"
            if str((record or {}).get("asset_class")) == "KRYPTO"
            else str((record or {}).get("asset_class"))
        )
        reasons: list[str] = []
        if record is None:
            reasons.append("IDENTITY_RECORD_MISSING")
        else:
            if normalized_class != asset_class:
                reasons.append("ASSET_CLASS_MISMATCH")
            if not asset_id or str(record.get("asset_id") or "") != asset_id:
                reasons.append("ASSET_ID_MISMATCH")
            if not listing_id or str(record.get("listing_id") or "") != listing_id:
                reasons.append("LISTING_ID_MISMATCH")
            if not record.get("currency"):
                reasons.append("CURRENCY_MISSING")
            if asset_class in {"EQUITIES", "ETF"} and (
                not record.get("exchange") or not record.get("exchange_timezone")
            ):
                reasons.append("EXCHANGE_OR_TIMEZONE_MISSING")
            if asset_class == "CRYPTO" and str(record.get("currency")) != "USD":
                reasons.append("CRYPTO_QUOTE_CURRENCY_NOT_USD")
        if reasons:
            identity_mismatches.append(
                {
                    "ticker": ticker,
                    "asset_class": asset_class,
                    "reason": "+".join(sorted(reasons)),
                }
            )
    after = {name: file_sha256(path) for name, path in sources.items()}
    implementation_hashes = dict(
        implementation_provenance["implementation_sha256"]
    )
    implementation_fingerprint = implementation_provenance[
        "implementation_fingerprint"
    ]
    expected_asset_counts = dict(
        expected_asset_counts
        if expected_asset_counts is not None
        else DEFAULT_EXPECTED_ASSET_COUNTS
    )
    expected_no_data_counts = dict(
        expected_no_data_counts
        if expected_no_data_counts is not None
        else DEFAULT_EXPECTED_NO_DATA_COUNTS
    )
    expected_active_bar_counts = dict(
        expected_active_bar_counts
        if expected_active_bar_counts is not None
        else DEFAULT_EXPECTED_ACTIVE_BAR_COUNTS
    )
    expected_invalid_bar_counts = dict(
        expected_invalid_bar_counts
        if expected_invalid_bar_counts is not None
        else DEFAULT_EXPECTED_INVALID_BAR_COUNTS
    )
    expected_eligible_signal_position_counts = dict(
        expected_eligible_signal_position_counts
        if expected_eligible_signal_position_counts is not None
        else DEFAULT_EXPECTED_ELIGIBLE_SIGNAL_POSITION_COUNTS
    )
    expected_crypto_invalid_sessions = {
        str(ticker): tuple(sorted(str(day) for day in days))
        for ticker, days in dict(
            expected_crypto_invalid_sessions
            if expected_crypto_invalid_sessions is not None
            else DEFAULT_EXPECTED_CRYPTO_INVALID_SESSIONS
        ).items()
    }
    expected_keys = {"EQUITIES_ETF", "CRYPTO", "FX"}
    for name, values in (
        ("expected_asset_counts", expected_asset_counts),
        ("expected_no_data_counts", expected_no_data_counts),
        ("expected_active_bar_counts", expected_active_bar_counts),
        ("expected_invalid_bar_counts", expected_invalid_bar_counts),
        (
            "expected_eligible_signal_position_counts",
            expected_eligible_signal_position_counts,
        ),
    ):
        if set(values) != expected_keys:
            raise MultiAssetV6InputError(
                f"{name} muss exakt {sorted(expected_keys)} enthalten."
            )
    actual_crypto_invalid_sessions: dict[str, tuple[str, ...]] = {}
    for ticker in sorted({str(item["ticker"]) for item in crypto_invalid_sessions}):
        actual_crypto_invalid_sessions[ticker] = tuple(
            sorted(
                str(item["session_date"])
                for item in crypto_invalid_sessions
                if str(item["ticker"]) == ticker
            )
        )
    actual_active_bar_counts = {
        "EQUITIES_ETF": int(equity["active_rows"]),
        "CRYPTO": int(crypto["active_rows"]),
        "FX": int(fx["active_rows"]),
    }
    actual_invalid_bar_counts = {
        "EQUITIES_ETF": int(equity["invalid_source_bars"]),
        "CRYPTO": int(crypto["invalid_source_bars"]),
        "FX": int(fx["invalid_source_bars"]),
    }
    actual_eligible_signal_position_counts = {
        "EQUITIES_ETF": int(
            equity["eligible_signal_positions_after_gap_warmup"]
        ),
        "CRYPTO": int(crypto["eligible_signal_positions_after_gap_warmup"]),
        "FX": int(fx["eligible_signal_positions_after_gap_warmup"]),
    }
    declared_target_hashes_match = (
        equity_artifact_payload.get("target_store_sha256")
        == before["equity_etf_store"]
        and crypto_artifact_payload.get("target_store_sha256")
        == before["crypto_store"]
    )
    declared_crypto_source_hashes = dict(
        crypto_artifact_payload.get("source_file_sha256") or {}
    )
    actual_crypto_source_hashes = {
        str(relative): str(before.get(f"crypto_frozen:{relative}") or "")
        for relative in sorted(declared_crypto_source_hashes)
    }
    crypto_frozen_hashes_match = all(
        actual_crypto_source_hashes[str(relative)] == expected_sha256
        for relative, expected_sha256 in declared_crypto_source_hashes.items()
    )
    crypto_frozen_source_set_fingerprint = fingerprint(actual_crypto_source_hashes)
    policy = gap_policy(
        peer_session_consensus_fingerprint=str(
            peer_session_consensus["fingerprint"]
        )
    )
    combined_basis = {
        "version": INPUT_PRECHECK_VERSION,
        "period": [DEVELOPMENT_START, DEVELOPMENT_END],
        "equity_etf_projection_fingerprint": equity["dataset_fingerprint"],
        "crypto_projection_fingerprint": crypto["dataset_fingerprint"],
        "fx_projection_fingerprint": fx["dataset_fingerprint"],
        "equity_etf_store_sha256": before["equity_etf_store"],
        "crypto_store_sha256": before["crypto_store"],
        "fx_store_sha256": before["fx_store"],
        "crypto_frozen_source_set_fingerprint": (
            crypto_frozen_source_set_fingerprint
        ),
        "source_dataset_manifest_sha256": before["dataset_manifest"],
        "source_dataset_fingerprint": dataset_manifest_payload.get(
            "dataset_fingerprint"
        ),
        "identity_store_sha256": before["identity_store"],
        "identity_registry_fingerprint": identity_fingerprint,
        "gap_policy_fingerprint": policy["fingerprint"],
    }
    combined_input_fingerprint = fingerprint(combined_basis)
    checks = {
        "source_hashes_unchanged": before == after,
        "source_path_labels_match_hash_labels": (
            set(source_paths) == set(before) == set(after)
        ),
        "equity_artifact_self_valid": _validate_self_fingerprint(
            equity_artifact_payload
        ),
        "crypto_artifact_self_valid": _validate_self_fingerprint(
            crypto_artifact_payload
        ),
        "crypto_projection_code_matches_artifact": (
            crypto_artifact_payload.get("projection_code_sha256")
            == file_sha256(Path(__file__))
        ),
        "fx_artifact_self_valid": _named_fingerprint_is_valid(
            fx_artifact_payload, "manifest_fingerprint"
        ),
        "projection_artifact_store_hashes_match_where_declared": (
            declared_target_hashes_match
        ),
        "projection_artifact_manifest_lineage_matches": (
            equity_artifact_payload.get("source_manifest_sha256")
            == before["dataset_manifest"]
            and crypto_artifact_payload.get("source_manifest_sha256")
            == before["dataset_manifest"]
            and crypto_artifact_payload.get("identity_store_sha256")
            == before["identity_store"]
            and equity_artifact_payload.get("source_dataset_fingerprint")
            == dataset_manifest_payload.get("dataset_fingerprint")
            and crypto_artifact_payload.get("source_dataset_fingerprint")
            == dataset_manifest_payload.get("dataset_fingerprint")
        ),
        "frozen_dataset_fingerprint_available": bool(
            dataset_manifest_payload.get("dataset_fingerprint")
        ),
        "crypto_frozen_source_hashes_match_projection": (
            bool(crypto_artifact_payload.get("source_file_sha256"))
            and len(dict(crypto_artifact_payload["source_file_sha256"]))
            == int(crypto["coverage_assets"])
            and crypto_frozen_hashes_match
        ),
        "projection_fingerprints_match_stores": (
            equity_artifact_payload.get("dataset_fingerprint")
            == equity["dataset_fingerprint"]
            and crypto_artifact_payload.get("dataset_fingerprint")
            == crypto["dataset_fingerprint"]
            and fx_artifact_payload.get("dataset_fingerprint")
            == fx["dataset_fingerprint"]
        ),
        "all_active_ohlc_valid": sum(
            int(item["ohlc_violation_count"]) for item in (equity, crypto, fx)
        )
        == 0,
        "no_duplicate_active_sessions": sum(
            int(item["duplicate_active_sessions"]) for item in (equity, crypto, fx)
        )
        == 0,
        "no_active_invalid_session_overlap": sum(
            int(item["invalid_active_session_overlap_count"])
            for item in (equity, crypto, fx)
        )
        == 0,
        "coverage_rows_reconcile_with_stores": sum(
            int(item["coverage_mismatch_count"]) for item in (equity, crypto, fx)
        )
        == 0,
        "fx_record_identity_and_availability_valid": (
            int(fx["record_identity_violation_count"]) == 0
            and int(fx["availability_violation_count"]) == 0
        ),
        "identity_listing_currency_consistent": not identity_mismatches,
        "identity_registry_tickers_unique": not duplicate_identity_tickers,
        "identity_registry_fingerprint_valid": identity_registry_fingerprint_valid,
        "peer_session_consensus_fingerprint_valid": (
            fingerprint(
                {
                    key: value
                    for key, value in peer_session_consensus.items()
                    if key != "fingerprint"
                }
            )
            == peer_session_consensus["fingerprint"]
        ),
        "peer_session_consensus_does_not_claim_official_calendars": (
            peer_session_consensus.get(
                "official_exchange_or_fx_calendar_asserted"
            )
            is False
            and peer_session_consensus.get(
                "dates_without_any_active_group_observation_asserted_as_sessions"
            )
            is False
        ),
        "all_stores_quick_check_ok": all(
            item["quick_check"] == "ok" for item in (equity, crypto, fx)
        ),
        "asset_class_counts_match_frozen_universe": (
            equity["coverage_assets"] == expected_asset_counts["EQUITIES_ETF"]
            and crypto["coverage_assets"] == expected_asset_counts["CRYPTO"]
            and fx["coverage_assets"] == expected_asset_counts["FX"]
        ),
        "expected_no_data_assets_classified": (
            equity["no_data_assets"] == expected_no_data_counts["EQUITIES_ETF"]
            and crypto["no_data_assets"] == expected_no_data_counts["CRYPTO"]
            and fx["no_data_assets"] == expected_no_data_counts["FX"]
        ),
        "expected_active_bar_counts_match": (
            actual_active_bar_counts == expected_active_bar_counts
        ),
        "expected_invalid_bar_counts_match": (
            actual_invalid_bar_counts == expected_invalid_bar_counts
        ),
        "expected_gap_adjusted_eligible_signal_positions_match": (
            actual_eligible_signal_position_counts
            == expected_eligible_signal_position_counts
        ),
        "expected_crypto_invalid_sessions_archived": (
            actual_crypto_invalid_sessions == expected_crypto_invalid_sessions
        ),
        "every_archived_invalid_session_is_a_gap_boundary": all(
            int(item["archived_invalid_gap_boundaries"])
            == int(item["invalid_source_sessions"])
            for item in (equity, crypto, fx)
        ),
        "crypto_materialized_gap_manifest_complete": (
            crypto["materialized_gap_boundary_count"]
            == crypto["gap_boundary_count"]
            and crypto["materialized_archived_invalid_gap_boundaries"]
            == crypto["archived_invalid_gap_boundaries"]
        ),
        "implementation_fingerprint_available": implementation_fingerprint is not None,
        "no_missing_implementation_files": not missing_implementation,
        "no_downloads_or_imputation": (
            crypto_artifact_payload.get("no_downloads") is True
            and crypto_artifact_payload.get("no_imputation") is True
            and equity_artifact_payload.get("no_imputation") is True
            and fx_artifact_payload.get("no_imputation") is True
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    contract_inputs = {
        "combined_input_fingerprint": combined_input_fingerprint,
        "equity_etf_projection_fingerprint": equity["dataset_fingerprint"],
        "crypto_projection_fingerprint": crypto["dataset_fingerprint"],
        "fx_projection_fingerprint": fx["dataset_fingerprint"],
        "equity_etf_store_sha256": before["equity_etf_store"],
        "crypto_store_sha256": before["crypto_store"],
        "fx_store_sha256": before["fx_store"],
        "crypto_frozen_source_set_fingerprint": (
            crypto_frozen_source_set_fingerprint
        ),
        "source_dataset_manifest_sha256": before["dataset_manifest"],
        "source_dataset_fingerprint": dataset_manifest_payload.get(
            "dataset_fingerprint"
        ),
        "identity_store_sha256": before["identity_store"],
        "identity_registry_fingerprint": identity_fingerprint,
        "gap_policy_fingerprint": policy["fingerprint"],
        "implementation_fingerprint": implementation_fingerprint,
    }
    payload: dict[str, object] = {
        "version": INPUT_PRECHECK_VERSION,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract_inputs": contract_inputs,
        "checks": checks,
        "period": [DEVELOPMENT_START, DEVELOPMENT_END],
        "gap_policy": policy,
        "peer_session_consensus": peer_session_consensus,
        "coverage": {
            "asset_count": sum(
                int(item["coverage_assets"]) for item in (equity, crypto, fx)
            ),
            "active_asset_count": sum(
                int(item["active_assets"]) for item in (equity, crypto, fx)
            ),
            "no_data_asset_count": sum(
                int(item["no_data_assets"]) for item in (equity, crypto, fx)
            ),
            "active_bar_count": sum(
                int(item["active_rows"]) for item in (equity, crypto, fx)
            ),
            "by_asset_class": {
                "EQUITIES_ETF": equity,
                "CRYPTO": crypto,
                "FX": fx,
            },
            "expected_asset_counts": expected_asset_counts,
            "expected_no_data_counts": expected_no_data_counts,
            "expected_active_bar_counts": expected_active_bar_counts,
            "actual_active_bar_counts": actual_active_bar_counts,
            "expected_invalid_bar_counts": expected_invalid_bar_counts,
            "actual_invalid_bar_counts": actual_invalid_bar_counts,
            "expected_eligible_signal_position_counts": (
                expected_eligible_signal_position_counts
            ),
            "actual_eligible_signal_position_counts": (
                actual_eligible_signal_position_counts
            ),
            "expected_total_eligible_signal_positions": sum(
                int(value)
                for value in expected_eligible_signal_position_counts.values()
            ),
            "expected_combined_active_bar_count": sum(
                int(value) for value in expected_active_bar_counts.values()
            ),
            "expected_crypto_invalid_sessions": {
                ticker: list(days)
                for ticker, days in expected_crypto_invalid_sessions.items()
            },
            "actual_crypto_invalid_sessions": {
                ticker: list(days)
                for ticker, days in actual_crypto_invalid_sessions.items()
            },
        },
        "gap_boundary_provenance": {
            "equity_etf_archived_invalid_sessions": len(equity_invalid_sessions),
            "crypto_archived_invalid_sessions": crypto_invalid_sessions,
            "fx_archived_invalid_sessions": fx_invalid_sessions,
            "loader_derives_boundaries_from_active_and_archived_sessions": True,
            "target_missing_on_peer_observed_group_session_is_boundary": True,
            "official_exchange_or_fx_calendar_asserted": False,
            "group_wide_unobserved_dates_are_not_asserted_sessions": True,
            "session_consensus_fingerprint": peer_session_consensus[
                "fingerprint"
            ],
            "fresh_warmup_bars_after_every_boundary": MINIMUM_SEGMENT_HISTORY,
            "entry_or_outcome_crossing_boundary_allowed": False,
        },
        "identity_mismatches": identity_mismatches,
        "duplicate_identity_tickers": list(duplicate_identity_tickers),
        "source_sha256_before": before,
        "source_sha256_after": after,
        "source_paths": source_paths,
        "implementation_paths": implementation_provenance[
            "implementation_paths"
        ],
        "implementation_sha256": implementation_hashes,
        "missing_implementation_files": missing_implementation,
        "no_downloads": True,
        "no_clipping": True,
        "no_imputation": True,
        "no_interpolation": True,
        "development_run_started": False,
        "validation_opened": False,
        "holdout_opened": False,
        "external_opened": False,
        "broker_opened": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_append_only(artifact_path, payload)
    return payload


__all__ = [
    "CRYPTO_PROJECTION_VERSION",
    "DEFAULT_CRYPTO_ARTIFACT",
    "DEFAULT_CRYPTO_STORE",
    "DEFAULT_EQUITY_ETF_ARTIFACT",
    "DEFAULT_EQUITY_ETF_STORE",
    "DEFAULT_EXPECTED_ACTIVE_BAR_COUNTS",
    "DEFAULT_EXPECTED_ASSET_COUNTS",
    "DEFAULT_EXPECTED_CRYPTO_INVALID_SESSIONS",
    "DEFAULT_EXPECTED_ELIGIBLE_SIGNAL_POSITION_COUNTS",
    "DEFAULT_EXPECTED_INVALID_BAR_COUNTS",
    "DEFAULT_EXPECTED_NO_DATA_COUNTS",
    "DEFAULT_FX_ARTIFACT",
    "DEFAULT_INPUT_PRECHECK_ARTIFACT",
    "GAP_POLICY_VERSION",
    "INPUT_PRECHECK_VERSION",
    "MINIMUM_SEGMENT_HISTORY",
    "MultiAssetV6InputError",
    "PEER_SESSION_CONSENSUS_VERSION",
    "SegmentedAssetHistory",
    "build_crypto_projection",
    "build_v6_implementation_provenance",
    "build_v6_input_precheck",
    "default_implementation_paths",
    "gap_policy",
    "load_segmented_asset_history",
    "load_v6_asset_history",
    "verify_v6_current_sources",
]
