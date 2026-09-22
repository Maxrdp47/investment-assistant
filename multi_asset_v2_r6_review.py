from __future__ import annotations

"""Final integrity audit and preregistered descriptive review for R6."""

import argparse
import json
import math
import os
import sqlite3
import tempfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from multi_asset_development_v6_store import checkpoint_status
from multi_asset_discovery_v1 import fingerprint
from multi_asset_v2_r6_execution import (
    PARENT_FEATURE_STORE,
    PARENT_OUTCOME_STORE,
    PARENT_RUN_ID,
)
from multi_asset_v2_r6_runner import (
    R6_CHAIN_STATE,
    R6_MANIFEST,
    R6_RUN_ID,
    load_r6_review_contract,
    r6_paths,
    verify_self_fingerprint,
)


ROOT = Path(__file__).resolve().parent
FINAL_AUDIT = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_final_audit_2026-09-22-v1.json"
DESCRIPTIVE_REPORT = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_descriptive_report_2026-09-22-v1.json"
COMPLETION_SUMMARY = ROOT / "runtime" / "research_exports" / "multi_asset_discovery_v2_r6_completion_summary_2026-09-22-v1.json"
FINAL_AUDIT_MARKDOWN = ROOT / "R6_MULTI_ASSET_DISCOVERY_V2_FINAL_AUDIT_2026-09-22.md"
DESCRIPTIVE_REPORT_MARKDOWN = ROOT / "R6_MULTI_ASSET_DISCOVERY_V2_DESCRIPTIVE_DEVELOPMENT_REPORT_2026-09-22.md"
COMPLETION_SUMMARY_MARKDOWN = ROOT / "R6_MULTI_ASSET_DISCOVERY_V2_COMPLETION_SUMMARY_2026-09-22.md"
AUDIT_VERSION = "multi-asset-discovery-v2-r6-final-audit-2026.09.22-v1"
REPORT_VERSION = "multi-asset-discovery-v2-r6-descriptive-report-2026.09.22-v1"
SUMMARY_VERSION = "multi-asset-discovery-v2-r6-completion-summary-2026.09.22-v1"
EXPECTED_APPEND_ONLY_TRIGGERS = {
    "control": {
        "no_delete_run_events",
        "no_delete_runs",
        "no_delete_unit_receipts",
        "no_delete_work_units",
        "no_reopen_terminal_run",
        "no_reopen_terminal_work_unit",
        "no_update_run_events",
        "no_update_unit_receipts",
    },
    "feature": {
        "no_delete_feature_rows",
        "no_delete_store_metadata",
        "no_update_feature_rows",
        "no_update_store_metadata",
    },
    "outcome": {
        "no_delete_outcome_rows",
        "no_delete_store_metadata",
        "no_update_outcome_rows",
        "no_update_store_metadata",
    },
}


class MultiAssetV2R6ReviewError(RuntimeError):
    """R6 audit/review cannot make a trustworthy terminal statement."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiAssetV2R6ReviewError(f"JSON artifact unreadable: {path}") from exc


def _self_fingerprinted(payload: Mapping[str, object]) -> dict[str, object]:
    result = dict(payload)
    result.pop("artifact_fingerprint", None)
    result["artifact_fingerprint"] = fingerprint(result)
    return result


def _atomic_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    if path.exists():
        existing = _read_json(path)
        if not verify_self_fingerprint(existing) or existing != dict(payload):
            raise MultiAssetV2R6ReviewError(f"Immutable report conflict: {path}")
        return
    _atomic_write(path, payload)


def _write_text_immutable(path: Path, content: str) -> None:
    normalized = content.rstrip() + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != normalized:
            raise MultiAssetV2R6ReviewError(f"Immutable report conflict: {path}")
        return
    path.write_text(normalized, encoding="utf-8", newline="\n")


def _number(value: object, digits: int = 6) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/v"
    return f"{float(value):.{digits}f}"


def render_final_audit_markdown(audit: Mapping[str, object]) -> str:
    runtime = dict(audit["runtime"])
    integrity = dict(audit["case_integrity"])
    health = dict(audit["database_health"])
    lines = [
        "# R6 Multi-Asset Discovery v2 – Final Audit",
        "",
        f"- Status: `{audit['status']}`",
        f"- Run: `{audit['run_id']}`",
        f"- Ausführungs-Commit: `{audit['commit']}`",
        f"- Audit-Fingerprint: `{audit['artifact_fingerprint']}`",
        f"- Vollständige Work-Units/Receipts: {runtime['completed'] + runtime['skipped']:,} / {runtime['receipts']:,}",
        f"- Feature-/Outcome-Referenzen: {integrity['feature_rows']:,} / {integrity['outcome_reference_rows']:,}",
        f"- Signalzeitraum: {integrity['minimum_signal_day']} bis {integrity['maximum_signal_day']}",
        "",
        "## Integrität",
        "",
        "| Store | SQLite quick check | FK-Fehler | Append-only-Trigger |",
        "|---|---|---:|---:|",
    ]
    for role in ("control", "feature", "outcome"):
        item = dict(health[role])
        lines.append(
            f"| {role} | `{item['quick_check']}` | {item['foreign_key_errors']} | "
            f"{item['append_only_trigger_count']} |"
        )
    lines.extend(
        [
            "",
            "Doppelte Cases, verwaiste Referenzen und Feature-Link-Abweichungen: "
            f"{integrity['duplicate_feature_cases']} / {integrity['orphan_features']} / "
            f"{integrity['feature_link_mismatches']}.",
            "",
            "## Stage-Schutz",
            "",
            "Validation, Holdout, External, Forward, Paper, Shadow-Ausführung und Broker "
            "blieben geschlossen. Der Audit verändert keine eingefrorenen Eltern- oder "
            "Research-Daten.",
        ]
    )
    return "\n".join(lines)


def render_descriptive_report_markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# R6 Multi-Asset Discovery v2 – Descriptive Development Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Run: `{report['run_id']}`",
        f"- Fälle: {int(report['cases_reviewed']):,}",
        f"- Vorab benannte Einzelfeatures: {report['feature_count']}",
        f"- Robuste Kandidaten: {report['robust_candidate_count']}",
        f"- Report-Fingerprint: `{report['artifact_fingerprint']}`",
        "",
        "Die Tabelle enthält alle vorab festgelegten Einzelassoziationen, keine nach "
        "Rendite ausgewählte Rangliste. Pearson-r ist ausschließlich deskriptiv auf "
        "bereits gesehenen Development-Daten. `n/v` bedeutet nicht verfügbar.",
        "",
        "| Feature | Familie | Horizont | N Return | r Return | N MFE | r MFE | N MAE | r MAE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["association_rows"]:
        row = dict(item)
        outcomes = dict(row["outcomes"])
        returned = dict(outcomes["return_pct"])
        mfe = dict(outcomes["mfe_pct"])
        mae = dict(outcomes["mae_pct"])
        lines.append(
            f"| `{row['feature']}` | {row['family']} | {row['horizon']} | "
            f"{returned['n']:,} | {_number(returned['correlation'])} | "
            f"{mfe['n']:,} | {_number(mfe['correlation'])} | "
            f"{mae['n']:,} | {_number(mae['correlation'])} |"
        )
    dimensions = dict(report["quality_c_dimensions"])
    lines.extend(
        [
            "",
            "## Quality-C-Entscheidung",
            "",
            f"- Gate: `{report['candidate_gate_reason']}`",
            f"- Dependencies: `{dimensions['DEPENDENCIES']}`",
            "- Historisch verifizierte Issuer-Dependencies besitzen im eingefrorenen "
            "2016–2021-Scope Effective N = 0. Da alle Quality-C-Dimensionen bestehen "
            "müssen, ist kein R7-Kandidat zulässig.",
            "- Jahres-, Assetklassen- und Regime-Slices sowie alle Mittelwerte und "
            "Fallzahlen stehen vollständig im fingerprint-geschützten JSON-Artefakt.",
            "",
            "Es wurden keine Schwellen, Quantile, Parameter, Featurekombinationen oder "
            "Profit-Ranglisten gesucht. Validation und Holdout blieben geschlossen.",
        ]
    )
    return "\n".join(lines)


def render_completion_summary_markdown(summary: Mapping[str, object]) -> str:
    return "\n".join(
        [
            "# R6 Multi-Asset Discovery v2 – Completion Summary",
            "",
            f"- Status: `{summary['status']}`",
            f"- Run: `{summary['run_id']}`",
            f"- Fälle: {int(summary['cases']):,}",
            f"- Features: {summary['features']}",
            f"- Robuste Kandidaten: {summary['robust_candidate_count']}",
            f"- R7 geöffnet: `{summary['r7_opened']}`",
            f"- Nächster Programmschritt: `{summary['next_step']}`",
            f"- Summary-Fingerprint: `{summary['artifact_fingerprint']}`",
            "",
            "Validation, Holdout, External, Forward, Paper, Shadow-Ausführung und Broker "
            "wurden nicht geöffnet. Die v7-r2-Elternstores und alle früheren "
            "Research-Artefakte blieben unverändert.",
        ]
    )


def _read_only(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise MultiAssetV2R6ReviewError(f"Required store missing: {resolved}")
    return sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=120)


def _decode(blob: bytes) -> dict[str, Any]:
    return json.loads(zlib.decompress(blob).decode("utf-8"))


def _payload_fingerprint(payload: Mapping[str, object], field: str) -> str:
    basis = dict(payload)
    basis.pop(field, None)
    return fingerprint(basis)


def _joined_payloads_valid(
    *,
    case_id: str,
    delta_fingerprint: str,
    r6_outcome_fingerprint: str,
    r6_feature_link: str,
    parent_feature_fingerprint: str,
    parent_outcome_fingerprint: str,
    parent_outcome_link: str,
    delta: Mapping[str, object],
    r6_outcome: Mapping[str, object],
    parent_feature: Mapping[str, object],
    parent_outcome: Mapping[str, object],
) -> bool:
    """Verify every immutable payload and every cross-store lineage link."""

    return bool(
        delta.get("case_id") == case_id
        and delta.get("parent_case_id") == case_id
        and delta.get("feature_fingerprint") == delta_fingerprint
        and _payload_fingerprint(delta, "feature_fingerprint") == delta_fingerprint
        and r6_feature_link == delta_fingerprint
        and r6_outcome.get("case_id") == case_id
        and r6_outcome.get("parent_case_id") == case_id
        and r6_outcome.get("outcome_fingerprint") == r6_outcome_fingerprint
        and _payload_fingerprint(r6_outcome, "outcome_fingerprint")
        == r6_outcome_fingerprint
        and r6_outcome.get("feature_fingerprint") == delta_fingerprint
        and r6_outcome.get("parent_outcome_fingerprint")
        == parent_outcome_fingerprint
        and r6_outcome.get("outcome_values_copied") is False
        and parent_feature.get("case_id") == case_id
        and parent_feature.get("feature_fingerprint") == parent_feature_fingerprint
        and _payload_fingerprint(parent_feature, "feature_fingerprint")
        == parent_feature_fingerprint
        and parent_outcome.get("case_id") == case_id
        and parent_outcome.get("outcome_fingerprint") == parent_outcome_fingerprint
        and _payload_fingerprint(parent_outcome, "outcome_fingerprint")
        == parent_outcome_fingerprint
        and parent_outcome_link == parent_feature_fingerprint
        and delta.get("parent_feature_fingerprint") == parent_feature_fingerprint
    )


def build_final_audit() -> dict[str, object]:
    if FINAL_AUDIT.is_file():
        existing = _read_json(FINAL_AUDIT)
        if verify_self_fingerprint(existing) and existing.get("status") == "PASS":
            _write_text_immutable(FINAL_AUDIT_MARKDOWN, render_final_audit_markdown(existing))
            return existing
        raise MultiAssetV2R6ReviewError("Existing R6 final audit is invalid.")
    paths = r6_paths()
    manifest = _read_json(R6_MANIFEST)
    if not verify_self_fingerprint(manifest):
        raise MultiAssetV2R6ReviewError("R6 manifest is invalid.")
    status = checkpoint_status(control_path=paths["control"], run_id=R6_RUN_ID)
    if (
        status["status"] != "COMPLETED"
        or status["progress_pct"] != 100.0
        or status["pending"]
        or status["active"]
    ):
        raise MultiAssetV2R6ReviewError(
            "R6 is not terminally complete; no final audit artifact was written."
        )
    issues: list[str] = []
    if status["failed"]:
        issues.append("FAILED_WORK_UNITS_PRESENT")
    if status["receipts"] != status["total_planned_work_units"]:
        issues.append("RECEIPT_COUNT_MISMATCH")
    if status["feature_rows"] != status["outcome_rows"]:
        issues.append("R6_CROSS_STORE_ROW_COUNT_MISMATCH")
    database_health: dict[str, object] = {}
    for role in ("control", "feature", "outcome"):
        with _read_only(paths[role]) as connection:
            quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
            triggers = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                )
            }
            database_health[role] = {
                "quick_check": quick,
                "foreign_key_errors": foreign_keys,
                "append_only_trigger_count": len(triggers),
                "append_only_triggers": sorted(triggers),
            }
            if quick != "ok" or foreign_keys:
                issues.append(f"{role.upper()}_DATABASE_INTEGRITY_FAILURE")
            if triggers != EXPECTED_APPEND_ONLY_TRIGGERS[role]:
                issues.append(f"{role.upper()}_APPEND_ONLY_TRIGGER_MISMATCH")
    with _read_only(paths["feature"]) as features:
        features.execute(
            f"ATTACH DATABASE 'file:{paths['outcome'].resolve().as_posix()}?mode=ro' AS r6o"
        )
        feature_count, feature_distinct, min_day, max_day = features.execute(
            "SELECT COUNT(*),COUNT(DISTINCT case_id),MIN(signal_day),MAX(signal_day) "
            "FROM feature_rows WHERE run_id=?",
            (R6_RUN_ID,),
        ).fetchone()
        outcome_count, outcome_distinct = features.execute(
            "SELECT COUNT(*),COUNT(DISTINCT case_id) FROM r6o.outcome_rows WHERE run_id=?",
            (R6_RUN_ID,),
        ).fetchone()
        orphan_outcomes = int(
            features.execute(
                "SELECT COUNT(*) FROM r6o.outcome_rows o LEFT JOIN feature_rows f "
                "ON f.case_id=o.case_id AND f.run_id=? WHERE o.run_id=? AND f.case_id IS NULL",
                (R6_RUN_ID, R6_RUN_ID),
            ).fetchone()[0]
        )
        orphan_features = int(
            features.execute(
                "SELECT COUNT(*) FROM feature_rows f LEFT JOIN r6o.outcome_rows o "
                "ON o.case_id=f.case_id AND o.run_id=? WHERE f.run_id=? AND o.case_id IS NULL",
                (R6_RUN_ID, R6_RUN_ID),
            ).fetchone()[0]
        )
        cross_mismatch = int(
            features.execute(
                "SELECT COUNT(*) FROM feature_rows f JOIN r6o.outcome_rows o ON o.case_id=f.case_id "
                "WHERE f.run_id=? AND o.run_id=? AND o.feature_fingerprint<>f.feature_fingerprint",
                (R6_RUN_ID, R6_RUN_ID),
            ).fetchone()[0]
        )
    if int(feature_count) != int(feature_distinct) or int(outcome_count) != int(outcome_distinct):
        issues.append("DUPLICATE_CASE_IDS")
    if int(feature_count) != int(status["feature_rows"]) or int(outcome_count) != int(status["outcome_rows"]):
        issues.append("CONTROL_EVIDENCE_COUNT_MISMATCH")
    if orphan_outcomes or orphan_features or cross_mismatch:
        issues.append("CROSS_STORE_CASE_OR_LINK_MISMATCH")
    if str(min_day) < "2016-01-01" or str(max_day) > "2021-12-31":
        issues.append("NON_DEVELOPMENT_DATE_PRESENT")
    parent_counts: dict[str, int] = {}
    with _read_only(PARENT_FEATURE_STORE) as parent_features, _read_only(PARENT_OUTCOME_STORE) as parent_outcomes:
        parent_counts["features_in_scope"] = int(
            parent_features.execute(
                "SELECT COUNT(*) FROM feature_rows WHERE run_id=? AND asset_class IN ('EQUITIES','ETF','CRYPTO')",
                (PARENT_RUN_ID,),
            ).fetchone()[0]
        )
        parent_counts["outcomes_in_scope"] = int(
            parent_outcomes.execute(
                "SELECT COUNT(*) FROM outcome_rows WHERE run_id=? AND asset_class IN ('EQUITIES','ETF','CRYPTO')",
                (PARENT_RUN_ID,),
            ).fetchone()[0]
        )
    if int(feature_count) != parent_counts["features_in_scope"] or int(outcome_count) != parent_counts["outcomes_in_scope"]:
        issues.append("PARENT_SCOPE_CASE_COUNT_MISMATCH")
    audit = _self_fingerprinted(
        {
            "version": AUDIT_VERSION,
            "status": "PASS" if not issues else "FAIL",
            "created_at": utc_now(),
            "run_id": R6_RUN_ID,
            "commit": manifest["commit"],
            "run_manifest_fingerprint": manifest["run_manifest_fingerprint"],
            "runtime": status,
            "database_health": database_health,
            "case_integrity": {
                "feature_rows": int(feature_count),
                "outcome_reference_rows": int(outcome_count),
                "duplicate_feature_cases": int(feature_count) - int(feature_distinct),
                "duplicate_outcome_cases": int(outcome_count) - int(outcome_distinct),
                "orphan_outcomes": orphan_outcomes,
                "orphan_features": orphan_features,
                "feature_link_mismatches": cross_mismatch,
                "minimum_signal_day": min_day,
                "maximum_signal_day": max_day,
                "parent_scope": parent_counts,
            },
            "issues": issues,
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
            "forward_opened": False,
            "paper_opened": False,
            "shadow_execution_opened": False,
            "broker_opened": False,
        }
    )
    _write_immutable(FINAL_AUDIT, audit)
    _write_text_immutable(FINAL_AUDIT_MARKDOWN, render_final_audit_markdown(audit))
    return audit


@dataclass
class Moments:
    n: int = 0
    sx: float = 0.0
    sy: float = 0.0
    sxx: float = 0.0
    syy: float = 0.0
    sxy: float = 0.0

    def update(self, x: np.ndarray, y: np.ndarray) -> None:
        mask = np.isfinite(x) & np.isfinite(y)
        if not bool(mask.any()):
            return
        xv = x[mask]
        yv = y[mask]
        self.n += int(mask.sum())
        self.sx += float(xv.sum())
        self.sy += float(yv.sum())
        self.sxx += float(np.dot(xv, xv))
        self.syy += float(np.dot(yv, yv))
        self.sxy += float(np.dot(xv, yv))

    def result(self) -> dict[str, object]:
        if self.n < 2:
            correlation = None
        else:
            numerator = self.n * self.sxy - self.sx * self.sy
            denominator = math.sqrt(
                max(self.n * self.sxx - self.sx * self.sx, 0.0)
                * max(self.n * self.syy - self.sy * self.sy, 0.0)
            )
            correlation = numerator / denominator if denominator > 0 else None
        return {
            "n": self.n,
            "correlation": correlation,
            "mean_feature": self.sx / self.n if self.n else None,
            "mean_outcome": self.sy / self.n if self.n else None,
        }


def _available_feature(parent: Mapping[str, object], name: str) -> float | None:
    cell = dict(dict(parent.get("features") or {}).get(name) or {})
    value = cell.get("value") if cell.get("status") == "AVAILABLE" else None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _feature_values(
    parent_feature: Mapping[str, object],
    parent_outcome: Mapping[str, object],
    delta: Mapping[str, object],
    configured_names: Sequence[str],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for name in (
        "return_20", "return_60", "rsi_14", "atr_pct", "volatility_20",
        "volatility_60", "volume_ratio_20",
    ):
        value = _available_feature(parent_feature, name)
        if value is not None:
            result[f"core.{name}"] = value
    close = parent_outcome.get("signal_close")
    ema20 = _available_feature(parent_feature, "ema_20")
    ema50 = _available_feature(parent_feature, "ema_50")
    if isinstance(close, (int, float)) and float(close) > 0:
        close_value = float(close)
        if ema20 and ema20 > 0:
            result["core.close_vs_ema20_pct"] = close_value / ema20 - 1.0
        if ema20 and ema50 and ema50 > 0:
            result["core.ema20_vs_ema50_pct"] = ema20 / ema50 - 1.0
        safe_zones = dict(parent_feature.get("safe_zones") or {})
        for zone in ("A", "B", "C"):
            lower = dict(safe_zones.get(zone) or {}).get("lower")
            if isinstance(lower, (int, float)) and float(lower) > 0:
                result[f"core.safe_zone_{zone.lower()}_distance_pct"] = close_value / float(lower) - 1.0
    for name, value in dict(delta.get("feature_values") or {}).items():
        if isinstance(value, bool):
            result[str(name)] = float(value)
        elif isinstance(value, (int, float)) and math.isfinite(float(value)):
            result[str(name)] = float(value)
    allowed = set(configured_names)
    return {name: value for name, value in result.items() if name in allowed}


def _iter_joined_rows(feature_store: Path, *, chunk_size: int = 5000) -> Iterable[list[tuple[Any, ...]]]:
    connection = _read_only(feature_store)
    try:
        connection.execute(
            f"ATTACH DATABASE 'file:{r6_paths()['outcome'].resolve().as_posix()}?mode=ro' AS r6o"
        )
        connection.execute(
            f"ATTACH DATABASE 'file:{PARENT_FEATURE_STORE.resolve().as_posix()}?mode=ro' AS pf"
        )
        connection.execute(
            f"ATTACH DATABASE 'file:{PARENT_OUTCOME_STORE.resolve().as_posix()}?mode=ro' AS po"
        )
        cursor = connection.execute(
            "SELECT f.case_id,f.asset_class,f.signal_day,f.feature_fingerprint,f.payload_zlib,"
            "r.outcome_fingerprint,r.feature_fingerprint,r.payload_zlib,"
            "pf.feature_fingerprint,pf.payload_zlib,"
            "po.outcome_fingerprint,po.feature_fingerprint,po.payload_zlib "
            "FROM feature_rows f JOIN r6o.outcome_rows r ON r.case_id=f.case_id "
            "JOIN pf.feature_rows pf ON pf.case_id=f.case_id "
            "JOIN po.outcome_rows po ON po.case_id=f.case_id "
            "WHERE f.run_id=? AND r.run_id=? AND pf.run_id=? AND po.run_id=? "
            "ORDER BY f.work_unit_id,f.case_id",
            (R6_RUN_ID, R6_RUN_ID, PARENT_RUN_ID, PARENT_RUN_ID),
        )
        while True:
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                break
            yield rows
    finally:
        connection.close()


def build_descriptive_report() -> dict[str, object]:
    if DESCRIPTIVE_REPORT.is_file():
        existing = _read_json(DESCRIPTIVE_REPORT)
        if verify_self_fingerprint(existing):
            _write_text_immutable(
                DESCRIPTIVE_REPORT_MARKDOWN,
                render_descriptive_report_markdown(existing),
            )
            return existing
        raise MultiAssetV2R6ReviewError("Existing R6 descriptive report is invalid.")
    audit = build_final_audit()
    if audit["status"] != "PASS":
        raise MultiAssetV2R6ReviewError("R6 final audit failed; review remains closed.")
    contract, contract_fingerprint = load_r6_review_contract()
    feature_names = [str(item["name"]) for item in contract["continuous_features"]]
    horizons = [int(item) for item in dict(contract["outcomes"])["checkpoints"]]
    metrics = [str(item) for item in dict(contract["outcomes"])["metrics"]]
    overall: dict[tuple[str, int, str], Moments] = {}
    slices: dict[tuple[str, str, str, int], Moments] = {}
    processed = 0
    payload_errors = 0
    for rows in _iter_joined_rows(r6_paths()["feature"]):
        records: list[dict[str, object]] = []
        for row in rows:
            (
                case_id, asset_class, signal_day, delta_fp, delta_blob,
                r6_outcome_fp, r6_feature_link, r6_outcome_blob,
                parent_feature_fp, parent_feature_blob,
                parent_outcome_fp, parent_outcome_link, parent_outcome_blob,
            ) = row
            delta = _decode(delta_blob)
            r6_outcome = _decode(r6_outcome_blob)
            parent_feature = _decode(parent_feature_blob)
            parent_outcome = _decode(parent_outcome_blob)
            if not _joined_payloads_valid(
                case_id=str(case_id),
                delta_fingerprint=str(delta_fp),
                r6_outcome_fingerprint=str(r6_outcome_fp),
                r6_feature_link=str(r6_feature_link),
                parent_feature_fingerprint=str(parent_feature_fp),
                parent_outcome_fingerprint=str(parent_outcome_fp),
                parent_outcome_link=str(parent_outcome_link),
                delta=delta,
                r6_outcome=r6_outcome,
                parent_feature=parent_feature,
                parent_outcome=parent_outcome,
            ):
                payload_errors += 1
                continue
            values = _feature_values(parent_feature, parent_outcome, delta, feature_names)
            record: dict[str, object] = {
                **values,
                "year": str(signal_day)[:4],
                "asset_class": str(asset_class),
                "market_regime": str(parent_feature.get("market_regime") or "UNKNOWN"),
            }
            checkpoints = dict(parent_outcome.get("checkpoints") or {})
            for horizon in horizons:
                checkpoint = dict(checkpoints.get(str(horizon)) or {})
                if int(checkpoint.get("observations") or 0) != horizon:
                    continue
                for metric in metrics:
                    value = checkpoint.get(metric)
                    if isinstance(value, (int, float)) and math.isfinite(float(value)):
                        record[f"outcome.{horizon}.{metric}"] = float(value)
            records.append(record)
        if payload_errors:
            raise MultiAssetV2R6ReviewError("R6/parent payload integrity failed during review.")
        processed += len(records)
        if not records:
            continue
        for feature in feature_names:
            x = np.asarray([record.get(feature, np.nan) for record in records], dtype=float)
            for horizon in horizons:
                for metric in metrics:
                    y = np.asarray(
                        [record.get(f"outcome.{horizon}.{metric}", np.nan) for record in records],
                        dtype=float,
                    )
                    overall.setdefault((feature, horizon, metric), Moments()).update(x, y)
                y_return = np.asarray(
                    [record.get(f"outcome.{horizon}.return_pct", np.nan) for record in records],
                    dtype=float,
                )
                for dimension in ("year", "asset_class", "market_regime"):
                    labels = np.asarray([str(record[dimension]) for record in records], dtype=object)
                    for label in np.unique(labels):
                        mask = labels == label
                        slices.setdefault((dimension, str(label), feature, horizon), Moments()).update(
                            x[mask], y_return[mask]
                        )
    if processed != int(dict(audit["case_integrity"])["feature_rows"]):
        raise MultiAssetV2R6ReviewError("R6 review join did not consume the audited case set.")
    association_rows: list[dict[str, object]] = []
    for feature in feature_names:
        family = next(
            str(item["family"])
            for item in contract["continuous_features"]
            if item["name"] == feature
        )
        for horizon in horizons:
            row = {
                "feature": feature,
                "family": family,
                "horizon": horizon,
                "outcomes": {
                    metric: overall.get((feature, horizon, metric), Moments()).result()
                    for metric in metrics
                },
                "return_stability": {},
            }
            for dimension in ("year", "asset_class", "market_regime"):
                details = {
                    label: moments.result()
                    for (candidate_dimension, label, candidate_feature, candidate_horizon), moments in slices.items()
                    if candidate_dimension == dimension
                    and candidate_feature == feature
                    and candidate_horizon == horizon
                }
                row["return_stability"][dimension] = details
            association_rows.append(row)
    dimensions = {
        name: (
            "FAIL_HISTORICAL_VERIFIED_ISSUER_EFFECTIVE_N_ZERO"
            if name == "DEPENDENCIES"
            else "DESCRIPTIVE_ONLY_NOT_RELEASE_ASSESSED"
        )
        for name in dict(contract["candidate_gate"])["quality_dimensions"]
    }
    report = _self_fingerprinted(
        {
            "version": REPORT_VERSION,
            "status": "R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE",
            "created_at": utc_now(),
            "run_id": R6_RUN_ID,
            "audit_fingerprint": audit["artifact_fingerprint"],
            "review_contract_fingerprint": contract_fingerprint,
            "cases_reviewed": processed,
            "feature_count": len(feature_names),
            "association_method": dict(contract["method"])["association"],
            "association_rows": association_rows,
            "quality_c_dimensions": dimensions,
            "robust_candidate_count": 0,
            "candidate_gate_reason": "MANDATORY_DEPENDENCIES_DIMENSION_FAILED_EFFECTIVE_N_ZERO",
            "unresolved_information_gaps": [
                {
                    "gap": "HISTORICAL_VERIFIED_ISSUER_DEPENDENCIES_EFFECTIVE_N_ZERO",
                    "reserve_technical_indicator_can_measure_gap": False,
                }
            ],
            "justified_reserve_trigger_identified": False,
            "ranking_or_top_feature_selection_performed": False,
            "feature_combinations_tested": 0,
            "validation_opened": False,
            "holdout_opened": False,
            "interpretation": (
                "All associations are descriptive on already-seen 2016-2021 Development data. "
                "Unknown historical issuer dependencies contribute zero to effective N, so no "
                "feature can pass the mandatory all-dimensions Quality-C gate."
            ),
        }
    )
    _write_immutable(DESCRIPTIVE_REPORT, report)
    _write_text_immutable(
        DESCRIPTIVE_REPORT_MARKDOWN,
        render_descriptive_report_markdown(report),
    )
    return report


def build_completion_summary() -> dict[str, object]:
    if COMPLETION_SUMMARY.is_file():
        existing = _read_json(COMPLETION_SUMMARY)
        if verify_self_fingerprint(existing):
            _write_text_immutable(
                COMPLETION_SUMMARY_MARKDOWN,
                render_completion_summary_markdown(existing),
            )
            return existing
        raise MultiAssetV2R6ReviewError("Existing R6 completion summary is invalid.")
    audit = build_final_audit()
    report = build_descriptive_report()
    summary = _self_fingerprinted(
        {
            "version": SUMMARY_VERSION,
            "status": "R6_COMPLETE_NO_ROBUST_CANDIDATES_R7_NOT_OPENED",
            "created_at": utc_now(),
            "run_id": R6_RUN_ID,
            "audit_fingerprint": audit["artifact_fingerprint"],
            "descriptive_report_fingerprint": report["artifact_fingerprint"],
            "cases": report["cases_reviewed"],
            "features": report["feature_count"],
            "robust_candidate_count": 0,
            "r7_opened": False,
            "validation_opened": False,
            "holdout_opened": False,
            "external_opened": False,
            "forward_opened": False,
            "paper_opened": False,
            "shadow_execution_opened": False,
            "broker_opened": False,
            "next_step": "R8_JUSTIFIED_RESERVE_TRIGGER_REVIEW",
        }
    )
    _write_immutable(COMPLETION_SUMMARY, summary)
    _write_text_immutable(
        COMPLETION_SUMMARY_MARKDOWN,
        render_completion_summary_markdown(summary),
    )
    state = _self_fingerprinted(
        {
            "version": "multi-asset-discovery-v2-r6-chain-state-2026.09.22-v1",
            "status": summary["status"],
            "phase": "STOP",
            "run_id": R6_RUN_ID,
            "audit_fingerprint": audit["artifact_fingerprint"],
            "report_fingerprint": report["artifact_fingerprint"],
            "summary_fingerprint": summary["artifact_fingerprint"],
            "validation_opened": False,
            "holdout_opened": False,
            "updated_at": utc_now(),
        }
    )
    _atomic_write(R6_CHAIN_STATE, state)
    return summary


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("audit", "review", "complete"))
    args = parser.parse_args(argv)
    result = (
        build_final_audit()
        if args.action == "audit"
        else build_descriptive_report()
        if args.action == "review"
        else build_completion_summary()
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())


__all__ = [
    "COMPLETION_SUMMARY",
    "COMPLETION_SUMMARY_MARKDOWN",
    "DESCRIPTIVE_REPORT",
    "DESCRIPTIVE_REPORT_MARKDOWN",
    "FINAL_AUDIT",
    "FINAL_AUDIT_MARKDOWN",
    "Moments",
    "MultiAssetV2R6ReviewError",
    "build_completion_summary",
    "build_descriptive_report",
    "build_final_audit",
    "render_completion_summary_markdown",
    "render_descriptive_report_markdown",
    "render_final_audit_markdown",
]
