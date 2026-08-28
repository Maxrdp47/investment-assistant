from __future__ import annotations

"""Read-only integrity and reproducibility audit for Buyer Confirmation v1."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping

from swing_buyer_confirmation_validation import CHALLENGER_VERSION, _fingerprint


EXPECTED_TABLES = {
    "buyer_challenger_freezes",
    "buyer_integrity_receipts",
    "buyer_stage_openings",
    "buyer_stage_cases",
    "buyer_stage_completions",
    "buyer_stage_reviews",
}
EXPECTED_COUNTS = {
    "buyer_challenger_freezes": 1,
    "buyer_integrity_receipts": 1,
    "buyer_stage_openings": 1,
    "buyer_stage_cases": 181_473,
    "buyer_stage_completions": 2_520,
    "buyer_stage_reviews": 1,
}
EXPECTED_GROUP_COUNTS = {"control": 151_121, "treatment": 30_352}
EXPECTED_FAILED_GATES = {
    "conservative_execution_treatment_pf_above_one",
    "conservative_execution_treatment_positive",
    "positive_in_at_least_60pct_of_years",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _stream_digest(rows: Iterable[sqlite3.Row], fields: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        values = [str(row[field]) for field in fields]
        digest.update(("\x1f".join(values) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _payload_integrity(
    connection: sqlite3.Connection,
    table: str,
    payload_column: str,
    fingerprint_column: str,
) -> dict[str, object]:
    checked = 0
    invalid = 0
    for row in connection.execute(
        f"SELECT {payload_column}, {fingerprint_column} FROM {table}"  # noqa: S608
    ):
        checked += 1
        payload = json.loads(str(row[payload_column]))
        if _fingerprint(payload) != str(row[fingerprint_column]):
            invalid += 1
    return {"checked": checked, "invalid": invalid, "passed": invalid == 0}


def _source_snapshot_checks(freeze: Mapping[str, object]) -> dict[str, object]:
    checks: dict[str, object] = {}
    for name, raw_snapshot in dict(freeze.get("source_snapshots") or {}).items():
        snapshot = dict(raw_snapshot)
        path = Path(str(snapshot.get("path") or ""))
        exists = path.is_file()
        stat = path.stat() if exists else None
        current = {
            "exists": exists,
            "size_matches": bool(stat and stat.st_size == int(snapshot.get("size") or -1)),
            "mtime_matches": bool(
                stat and stat.st_mtime_ns == int(snapshot.get("mtime_ns") or -1)
            ),
        }
        if snapshot.get("sha256"):
            current["sha256_matches"] = bool(
                exists and file_sha256(path) == str(snapshot["sha256"])
            )
        current["passed"] = all(bool(value) for value in current.values())
        checks[str(name)] = current
    return checks


def audit_validation_store(
    path: Path,
    *,
    decision_report_path: Path | None = None,
) -> dict[str, object]:
    """Verify the immutable Validation store without opening it for writes."""

    database_path = Path(path).resolve()
    with _read_only_connection(database_path) as connection:
        integrity_check = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        actual_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in sorted(EXPECTED_TABLES & actual_tables)
        }
        stages = {
            table: [
                str(row[0])
                for row in connection.execute(
                    f"SELECT DISTINCT research_stage FROM {table} ORDER BY research_stage"
                )
            ]
            for table in (
                "buyer_stage_openings",
                "buyer_stage_cases",
                "buyer_stage_completions",
                "buyer_stage_reviews",
            )
            if table in actual_tables
        }
        group_counts = {
            str(row[0]): int(row[1])
            for row in connection.execute(
                "SELECT comparison_group, COUNT(*) FROM buyer_stage_cases "
                "GROUP BY comparison_group ORDER BY comparison_group"
            )
        }
        candidate_ids = int(
            connection.execute(
                "SELECT COUNT(DISTINCT candidate_id) FROM buyer_stage_cases"
            ).fetchone()[0]
        )
        symbols = int(
            connection.execute(
                "SELECT COUNT(DISTINCT symbol) FROM buyer_stage_completions"
            ).fetchone()[0]
        )
        payloads = {
            "freezes": _payload_integrity(
                connection, "buyer_challenger_freezes", "freeze_json", "freeze_fingerprint"
            ),
            "receipts": _payload_integrity(
                connection,
                "buyer_integrity_receipts",
                "receipt_json",
                "receipt_fingerprint",
            ),
            "openings": _payload_integrity(
                connection,
                "buyer_stage_openings",
                "opening_json",
                "opening_fingerprint",
            ),
            "cases": _payload_integrity(
                connection, "buyer_stage_cases", "case_json", "case_fingerprint"
            ),
            "completions": _payload_integrity(
                connection,
                "buyer_stage_completions",
                "completion_json",
                "completion_fingerprint",
            ),
            "reviews": _payload_integrity(
                connection, "buyer_stage_reviews", "review_json", "review_fingerprint"
            ),
        }
        freeze_row = connection.execute(
            "SELECT freeze_json, freeze_fingerprint FROM buyer_challenger_freezes "
            "WHERE challenger_version=?",
            (CHALLENGER_VERSION,),
        ).fetchone()
        receipt_row = connection.execute(
            "SELECT receipt_json, receipt_fingerprint FROM buyer_integrity_receipts "
            "WHERE challenger_version=?",
            (CHALLENGER_VERSION,),
        ).fetchone()
        opening_row = connection.execute(
            "SELECT opening_json, opening_fingerprint FROM buyer_stage_openings "
            "WHERE challenger_version=? AND research_stage='validation'",
            (CHALLENGER_VERSION,),
        ).fetchone()
        review_row = connection.execute(
            "SELECT decision, review_json, review_fingerprint FROM buyer_stage_reviews "
            "WHERE challenger_version=? AND research_stage='validation'",
            (CHALLENGER_VERSION,),
        ).fetchone()
        holdout_counts = {
            table: int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE research_stage='holdout'"
                ).fetchone()[0]
            )
            for table in (
                "buyer_stage_openings",
                "buyer_stage_cases",
                "buyer_stage_completions",
                "buyer_stage_reviews",
            )
        }
        case_contract_violations = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM buyer_stage_cases
                WHERE research_stage <> 'validation'
                   OR challenger_version <> ?
                   OR json_extract(case_json, '$.research_stage') IS NOT research_stage
                   OR json_extract(case_json, '$.challenger_version') IS NOT challenger_version
                   OR json_extract(case_json, '$.candidate_id') IS NOT candidate_id
                   OR json_extract(case_json, '$.comparison_group') IS NOT comparison_group
                   OR json_extract(case_json, '$.ground_up_from_frozen_ohlcv') IS NOT 1
                   OR json_extract(case_json, '$.development_case_read') IS NOT 0
                   OR json_extract(case_json, '$.additional_filter_applied') IS NOT 0
                   OR json_extract(case_json, '$.parameters_changed') IS NOT 0
                   OR json_extract(case_json, '$.automatic_production_activation') IS NOT 0
                   OR (comparison_group='treatment' AND json_extract(case_json, '$.buyer_confirmation') IS NOT 1)
                   OR (comparison_group='control' AND json_extract(case_json, '$.buyer_confirmation') IS NOT 0)
                   OR json_extract(case_json, '$.alias_confirmation')
                      IS NOT json_extract(case_json, '$.buyer_confirmation')
                """,
                (CHALLENGER_VERSION,),
            ).fetchone()[0]
        )
    freeze = json.loads(str(freeze_row["freeze_json"])) if freeze_row else {}
    receipt = json.loads(str(receipt_row["receipt_json"])) if receipt_row else {}
    opening = json.loads(str(opening_row["opening_json"])) if opening_row else {}
    review = json.loads(str(review_row["review_json"])) if review_row else {}
    report_check: dict[str, object] | None = None
    if decision_report_path is not None:
        report_path = Path(decision_report_path).resolve()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        stored_report_fingerprint = str(report.get("review_fingerprint") or "")
        report_payload = {key: value for key, value in report.items() if key != "review_fingerprint"}
        report_check = {
            "path": str(report_path),
            "sha256": file_sha256(report_path),
            "fingerprint_valid": _fingerprint(report_payload) == stored_report_fingerprint,
            "matches_store_review": report_payload == review,
            "matches_store_fingerprint": bool(
                review_row and stored_report_fingerprint == str(review_row["review_fingerprint"])
            ),
        }
        report_check["passed"] = all(
            bool(report_check[key])
            for key in ("fingerprint_valid", "matches_store_review", "matches_store_fingerprint")
        )
    source_checks = _source_snapshot_checks(freeze) if freeze else {}
    pre_run_contract_checks = {
        "single_rule_exact": dict(freeze.get("single_new_rule") or {}).get("definition")
        == "Close[t] > High[t-1]",
        "objective_pullback_scope": freeze.get("setup_scope") == "objective_pullback",
        "no_additional_filters": freeze.get("additional_filters") == [],
        "rules_immutable": freeze.get("rules_mutable_after_freeze") is False,
        "receipt_passed": receipt.get("status") == "PASS",
        "receipt_checks_passed": bool(receipt.get("checks"))
        and all(bool(value) for value in dict(receipt.get("checks") or {}).values()),
        "validation_opened_without_outcomes": opening.get("outcomes_seen_before_open") is False,
        "development_cases_not_read": opening.get("development_cases_read") is False,
        "parameters_immutable": opening.get("parameters_mutable") is False,
        "ground_up_from_frozen_ohlcv": opening.get("ground_up_from_frozen_ohlcv") is True,
    }
    terminal_contract_checks = {
        "validation_complete": review.get("completed_assets") == review.get("expected_assets") == 2520,
        "validity_and_power_passed": dict(review.get("validity_gate") or {}).get("status")
        == "PASS",
        "missing_feature_n_zero": review.get("missing_feature_n") == 0,
        "failed_gates_exact": set(review.get("failed_gates") or ()) == EXPECTED_FAILED_GATES,
        "validation_failed": review.get("status") == "VALIDATION_FAIL",
        "next_stage_blocked": review.get("next_stage_allowed") is False,
        "no_retuning": review.get("retuning_performed") is False,
        "parameters_unchanged": review.get("parameters_changed") is False,
        "production_unchanged": review.get("production_changed") is False,
        "no_automatic_activation": review.get("automatic_production_activation") is False,
        "negative_evidence_retained": review.get("negative_evidence_retained") is True,
    }
    expected_shape = (
        actual_tables == EXPECTED_TABLES
        and counts == EXPECTED_COUNTS
        and group_counts == EXPECTED_GROUP_COUNTS
        and candidate_ids == EXPECTED_COUNTS["buyer_stage_cases"]
        and symbols == EXPECTED_COUNTS["buyer_stage_completions"]
        and all(value == 0 for value in holdout_counts.values())
        and all(value == ["validation"] for value in stages.values())
    )
    result_integrity = all(
        (
            integrity_check == "ok",
            not foreign_key_violations,
            expected_shape,
            all(bool(item["passed"]) for item in payloads.values()),
            case_contract_violations == 0,
            opening.get("allowed") is True,
            all(pre_run_contract_checks.values()),
            all(terminal_contract_checks.values()),
            bool(review_row and str(review_row["decision"]) == "VALIDATION_FAIL"),
            all(bool(item["passed"]) for item in source_checks.values()),
            report_check is None or bool(report_check["passed"]),
        )
    )
    return {
        "audit_version": "buyer-confirmation-validation-provenance-2026.08.27-v1",
        "database": str(database_path),
        "database_sha256": file_sha256(database_path),
        "sqlite_integrity_check": integrity_check,
        "foreign_key_violations": foreign_key_violations,
        "tables": sorted(actual_tables),
        "counts": counts,
        "stages": stages,
        "group_counts": group_counts,
        "distinct_candidate_ids": candidate_ids,
        "distinct_completion_symbols": symbols,
        "holdout_counts": holdout_counts,
        "payload_fingerprint_checks": payloads,
        "case_contract_violations": case_contract_violations,
        "pre_run_contract_checks": pre_run_contract_checks,
        "terminal_contract_checks": terminal_contract_checks,
        "freeze_fingerprint": str(freeze_row["freeze_fingerprint"]) if freeze_row else None,
        "receipt_fingerprint": str(receipt_row["receipt_fingerprint"]) if receipt_row else None,
        "opening_fingerprint": str(opening_row["opening_fingerprint"]) if opening_row else None,
        "review_fingerprint": str(review_row["review_fingerprint"]) if review_row else None,
        "stage_decision": str(review_row["decision"]) if review_row else None,
        "failed_gates": list(review.get("failed_gates") or ()),
        "source_snapshot_checks": source_checks,
        "decision_report_check": report_check,
        "result_integrity": "VERIFIED" if result_integrity else "FAILED",
    }


def _identity_digests(path: Path) -> dict[str, str]:
    with _read_only_connection(path) as connection:
        return {
            "cases": _stream_digest(
                connection.execute(
                    "SELECT candidate_id, comparison_group, case_fingerprint "
                    "FROM buyer_stage_cases ORDER BY candidate_id"
                ),
                ("candidate_id", "comparison_group", "case_fingerprint"),
            ),
            "completions": _stream_digest(
                connection.execute(
                    "SELECT symbol, completion_fingerprint FROM buyer_stage_completions "
                    "ORDER BY symbol"
                ),
                ("symbol", "completion_fingerprint"),
            ),
        }


def compare_validation_stores(reference_path: Path, reproduction_path: Path) -> dict[str, object]:
    """Compare two independently produced stores by immutable logical records."""

    reference = audit_validation_store(reference_path)
    reproduction = audit_validation_store(reproduction_path)
    reference_digests = _identity_digests(reference_path)
    reproduction_digests = _identity_digests(reproduction_path)
    immutable_keys = (
        "counts",
        "group_counts",
        "distinct_candidate_ids",
        "distinct_completion_symbols",
        "freeze_fingerprint",
        "receipt_fingerprint",
        "opening_fingerprint",
        "review_fingerprint",
        "stage_decision",
        "failed_gates",
    )
    comparisons = {
        key: reference.get(key) == reproduction.get(key) for key in immutable_keys
    }
    comparisons["case_identity_digest"] = reference_digests["cases"] == reproduction_digests["cases"]
    comparisons["completion_identity_digest"] = (
        reference_digests["completions"] == reproduction_digests["completions"]
    )
    return {
        "comparison_version": "buyer-confirmation-validation-reproduction-2026.08.27-v1",
        "reference_database": str(Path(reference_path).resolve()),
        "reproduction_database": str(Path(reproduction_path).resolve()),
        "reference_database_sha256": reference["database_sha256"],
        "reproduction_database_sha256": reproduction["database_sha256"],
        "byte_identical": reference["database_sha256"] == reproduction["database_sha256"],
        "reference_result_integrity": reference["result_integrity"],
        "reproduction_result_integrity": reproduction["result_integrity"],
        "reference_identity_digests": reference_digests,
        "reproduction_identity_digests": reproduction_digests,
        "comparisons": comparisons,
        "logical_records_identical": all(comparisons.values()),
    }
