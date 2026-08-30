from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from failed_seller_reclassification import (  # noqa: E402
    DEPENDENCY_METHOD,
    FAILED_SELLER_RECLASSIFICATION_VERSION,
    VARIANTS,
    assess_interpretation,
    dependency_results,
    fingerprint,
    make_accumulators,
    update_accumulators,
    verify_original_counts,
)
from research_identity_multisource import file_sha256  # noqa: E402


DEFAULT_ORIGINAL_REPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "failed_seller_development_2026-08-28-v1.json"
)
DEFAULT_FAILED_SELLER_DB = PROJECT_ROOT / "runtime" / "failed_seller_research.sqlite3"
DEFAULT_BROAD_DB = PROJECT_ROOT / "runtime" / "swing_broad_research.sqlite3"
DEFAULT_IDENTITY_REGISTRY = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "research_identity_registry_2026-08-30-v2.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "failed_seller_dependency_reclassification_2026-08-30-v1.json"
)
DEFAULT_STORE = PROJECT_ROOT / "runtime" / "failed_seller_reclassifications.sqlite3"


QUERY = """SELECT
 c.symbol,
 c.signal_day,
 json_extract(f.feature_json, '$.isolated_variant_flags.failed_seller_attempts_exactly_1'),
 json_extract(f.feature_json, '$.isolated_variant_flags.failed_seller_attempts_exactly_2'),
 json_extract(f.feature_json, '$.isolated_variant_flags.confirmation_close_location_gte_0_70'),
 json_extract(f.feature_json, '$.isolated_variant_flags.confirmation_close_location_gte_0_80')
FROM failed.failed_seller_features f
JOIN broad_research_candidates c ON c.candidate_id = f.candidate_id
WHERE f.run_id = ?
ORDER BY c.signal_day, c.candidate_id"""


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _snapshot(path: Path) -> dict[str, int]:
    stat = Path(path).stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _code_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (
        PROJECT_ROOT / "failed_seller_reclassification.py",
        Path(__file__).resolve(),
        PROJECT_ROOT / "swing_research_identity_v3.py",
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS failed_seller_dependency_reclassifications (
                reclassification_id TEXT PRIMARY KEY,
                original_run_id TEXT NOT NULL,
                identity_registry_fingerprint TEXT NOT NULL,
                artifact_json TEXT NOT NULL,
                output_digest TEXT NOT NULL UNIQUE
            );
            CREATE TRIGGER IF NOT EXISTS failed_seller_reclassification_no_update
            BEFORE UPDATE ON failed_seller_dependency_reclassifications
            BEGIN SELECT RAISE(ABORT, 'failed seller reclassification append-only'); END;
            CREATE TRIGGER IF NOT EXISTS failed_seller_reclassification_no_delete
            BEFORE DELETE ON failed_seller_dependency_reclassifications
            BEGIN SELECT RAISE(ABORT, 'failed seller reclassification append-only'); END;
            """
        )


def _append_store(path: Path, payload: Mapping[str, object]) -> int:
    _initialize_store(path)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with sqlite3.connect(path) as connection:
        existing = connection.execute(
            "SELECT output_digest FROM failed_seller_dependency_reclassifications "
            "WHERE reclassification_id=?",
            (payload["reclassification_id"],),
        ).fetchone()
        if existing is not None:
            if str(existing[0]) != str(payload["output_digest"]):
                raise RuntimeError("Reclassification ID exists with a different digest.")
            return 0
        connection.execute(
            "INSERT INTO failed_seller_dependency_reclassifications VALUES (?, ?, ?, ?, ?)",
            (
                payload["reclassification_id"],
                payload["original_run_id"],
                payload["identity_registry_fingerprint"],
                serialized,
                payload["output_digest"],
            ),
        )
    return 1


def run(args: argparse.Namespace) -> dict[str, object]:
    original_path = Path(args.original_report)
    identity_path = Path(args.identity_registry)
    original = json.loads(original_path.read_text(encoding="utf-8"))
    registry = json.loads(identity_path.read_text(encoding="utf-8"))
    original_result = dict(original["result"])
    original_run_id = str(original["run_id"])
    identity_by_ticker = {
        str(record["ticker"]).upper(): dict(record) for record in registry["records"]
    }
    protected_before = {
        "failed_seller": _snapshot(Path(args.failed_seller_db)),
        "broad": _snapshot(Path(args.broad_db)),
        "original_report_sha256": file_sha256(original_path),
    }
    ledger_before = None
    with _readonly(Path(args.failed_seller_db)) as failed:
        ledger_before = failed.execute(
            "SELECT COUNT(*) FROM failed_seller_attempt_ledger WHERE run_id=?",
            (original_run_id,),
        ).fetchone()[0]

    accumulators = make_accumulators()
    with _readonly(Path(args.broad_db)) as connection:
        failed_uri = f"file:{Path(args.failed_seller_db).resolve().as_posix()}?mode=ro"
        connection.execute("ATTACH DATABASE ? AS failed", (failed_uri,))
        for row in connection.execute(QUERY, (original_run_id,)):
            ticker = str(row[0]).upper()
            identity = identity_by_ticker.get(ticker) or {
                "ticker": ticker,
                "mapping_status": "UNRESOLVED",
                "dependency_status": "UNKNOWN",
                "issuer_id": None,
                "listing_id": f"unresolved:{ticker}",
            }
            flags = {variant: bool(row[index + 2]) for index, variant in enumerate(VARIANTS)}
            update_accumulators(
                accumulators,
                signal_day=str(row[1]),
                identity=identity,
                flags=flags,
            )
    dependency = dependency_results(accumulators)
    verify_original_counts(original_result, dependency)
    interpretation = assess_interpretation(original_result, dependency)
    protected_after = {
        "failed_seller": _snapshot(Path(args.failed_seller_db)),
        "broad": _snapshot(Path(args.broad_db)),
        "original_report_sha256": file_sha256(original_path),
    }
    with _readonly(Path(args.failed_seller_db)) as failed:
        ledger_after = failed.execute(
            "SELECT COUNT(*) FROM failed_seller_attempt_ledger WHERE run_id=?",
            (original_run_id,),
        ).fetchone()[0]
    if protected_before != protected_after or ledger_before != ledger_after:
        raise RuntimeError("Protected original inputs changed during read-only reclassification.")

    identity = {
        "version": FAILED_SELLER_RECLASSIFICATION_VERSION,
        "original_run_id": original_run_id,
        "original_report_fingerprint": original.get("report_fingerprint"),
        "identity_registry_fingerprint": registry["registry_fingerprint"],
        "dependency_method": DEPENDENCY_METHOD,
    }
    payload: dict[str, object] = {
        **identity,
        "reclassification_id": f"failed-seller-reclassification-{fingerprint(identity)[:32]}",
        "created_at": registry["created_at"],
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": _git("rev-parse", "HEAD"),
        "code_fingerprint": _code_fingerprint(),
        "mapping_version": registry["mapping_version"],
        "mapping_fingerprint": registry["registry_fingerprint"],
        "input_artifacts": {
            "original_report": str(original_path.resolve()),
            "original_report_sha256": protected_before["original_report_sha256"],
            "failed_seller_database": str(Path(args.failed_seller_db).resolve()),
            "broad_database": str(Path(args.broad_db).resolve()),
            "identity_registry": str(identity_path.resolve()),
            "identity_registry_sha256": file_sha256(identity_path),
        },
        "command": "python scripts/reclassify_failed_seller_dependencies.py",
        "original_result_snapshot": {
            "status": original_result["status"],
            "result_direction": original_result["result_direction"],
            "baseline": original_result["baseline"],
            "variants": original_result["variants"],
            "research_attempt_count": original_result["research_attempt_count"],
            "validation_opened": original_result["validation_opened"],
            "holdout_opened": original_result["holdout_opened"],
        },
        "raw_metrics_changed": False,
        "dependency_reclassification": dependency,
        "assessment": interpretation,
        "protected_inputs_before": protected_before,
        "protected_inputs_after": protected_after,
        "protected_inputs_unchanged": True,
        "attempt_ledger_before": ledger_before,
        "attempt_ledger_after": ledger_after,
        "new_research_attempts": 0,
        "validation_opened": False,
        "holdout_opened": False,
        "multi_asset_scan_started": False,
        "strategy_activated": False,
        "status": "COMPLETED_READ_ONLY_RECLASSIFICATION",
    }
    payload["output_digest"] = fingerprint(payload)
    _append_store(Path(args.store), payload)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Failed-Seller dependency reclassification")
    parser.add_argument("--original-report", type=Path, default=DEFAULT_ORIGINAL_REPORT)
    parser.add_argument("--failed-seller-db", type=Path, default=DEFAULT_FAILED_SELLER_DB)
    parser.add_argument("--broad-db", type=Path, default=DEFAULT_BROAD_DB)
    parser.add_argument("--identity-registry", type=Path, default=DEFAULT_IDENTITY_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    args = parser.parse_args()
    payload = run(args)
    summary = {
        "status": payload["status"],
        "reclassification_id": payload["reclassification_id"],
        "output_digest": payload["output_digest"],
        "classification_change": payload["assessment"]["classification_change"],
        "baseline_dependency": payload["dependency_reclassification"]["baseline"],
        "new_research_attempts": payload["new_research_attempts"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
