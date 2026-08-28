from __future__ import annotations

"""Run the preregistered Failed-Seller feature epoch on Broad Development only."""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from failed_seller_research import (
    FAILED_SELLER_FEATURE_VERSION,
    FAILED_SELLER_WORK_REQUEST_ID,
    build_failed_seller_feature,
    causal_atr14,
    failed_seller_feature_contract,
    finalize_run_payload,
    initialize_failed_seller_store,
)
from swing_research_dataset import normalized_research_history


DEFAULT_BROAD_DB = PROJECT_ROOT / "runtime" / "swing_broad_research.sqlite3"
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "runtime"
    / "swing_walk_forward_datasets"
    / "f7109e21474a027892eb01ed"
    / "manifest.json"
)
DEFAULT_OUTPUT_DB = PROJECT_ROOT / "runtime" / "failed_seller_research.sqlite3"
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "runtime"
    / "research_exports"
    / "failed_seller_development_2026-08-28-v1.json"
)


QUERY = """SELECT
 c.candidate_id, c.symbol, c.signal_day, c.issuer_id, c.listing_id,
 json_extract(c.feature_json, '$.identity.identity_confidence') identity_confidence,
 json_extract(c.feature_json, '$.pullback.impulse_high_day') pullback_start_day,
 json_extract(c.feature_json, '$.asset.asset_type') asset_class,
 json_extract(c.feature_json, '$.asset.region') region,
 json_extract(c.feature_json, '$.technical.market_phase') regime,
 json_extract(e.experiment_json, '$.results.pullback_low_atr_buffer.exits.fixed_2r.result_r') result_r,
 json_extract(l.label_json, '$.mfe_pct') mfe_pct,
 json_extract(l.label_json, '$.mae_pct') mae_pct
FROM broad_research_candidates c
JOIN broad_research_labels l ON l.candidate_id = c.candidate_id
JOIN broad_research_counterfactuals e ON e.candidate_id = c.candidate_id
WHERE c.research_split = 'development'
  AND c.setup_family = 'objective_pullback'
  AND json_extract(c.feature_json, '$.asset.asset_type') IN ('Aktie', 'ETF')
ORDER BY c.symbol, c.signal_day, c.candidate_id"""


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (PROJECT_ROOT / "failed_seller_research.py", Path(__file__).resolve()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git(*args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _history_for_symbol(manifest_path: Path, manifest: Mapping[str, object], symbol: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for scope in dict(manifest.get("scopes") or {}).values():
        descriptor = dict(dict(scope).get("assets") or {}).get(symbol)
        if not isinstance(descriptor, Mapping) or descriptor.get("status") != "available":
            continue
        file_name = str(descriptor.get("file") or "")
        if not file_name:
            continue
        frames.append(pd.read_parquet(manifest_path.parent / file_name))
    if not frames:
        return pd.DataFrame()
    return normalized_research_history(pd.concat(frames).sort_index())


class _Stats:
    def __init__(self) -> None:
        self.raw_n = 0
        self.evaluated_n = 0
        self.result_sum = 0.0
        self.positive_sum = 0.0
        self.negative_sum_abs = 0.0
        self.wins = 0
        self.mfe_sum = 0.0
        self.mfe_n = 0
        self.mae_sum = 0.0
        self.mae_n = 0
        self.known_issuers: set[str] = set()
        self.unknown_dependency_n = 0

    @staticmethod
    def _number(value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if pd.notna(number) else None

    def update(self, row: Mapping[str, object]) -> None:
        self.raw_n += 1
        result = self._number(row.get("result_r"))
        if result is not None:
            self.evaluated_n += 1
            self.result_sum += result
            self.wins += int(result > 0)
            if result > 0:
                self.positive_sum += result
            elif result < 0:
                self.negative_sum_abs += abs(result)
        mfe = self._number(row.get("mfe_pct"))
        if mfe is not None:
            self.mfe_sum += mfe
            self.mfe_n += 1
        mae = self._number(row.get("mae_pct"))
        if mae is not None:
            self.mae_sum += mae
            self.mae_n += 1
        issuer = str(row.get("issuer_id") or "").strip()
        if row.get("dependency_status") == "KNOWN" and issuer:
            self.known_issuers.add(issuer)
        else:
            self.unknown_dependency_n += 1

    def result(self) -> dict[str, object]:
        expectancy = self.result_sum / self.evaluated_n if self.evaluated_n else None
        return {
            "raw_n": self.raw_n,
            "evaluated_n": self.evaluated_n,
            "effective_n_known_issuer_clusters_only": len(self.known_issuers),
            "unknown_dependency_n": self.unknown_dependency_n,
            "expectancy_r": expectancy,
            "profit_factor": (
                self.positive_sum / self.negative_sum_abs
                if self.positive_sum and self.negative_sum_abs else None
            ),
            "hit_rate_pct": self.wins / self.evaluated_n * 100 if self.evaluated_n else None,
            "average_mfe_pct": self.mfe_sum / self.mfe_n if self.mfe_n else None,
            "average_mae_pct": self.mae_sum / self.mae_n if self.mae_n else None,
            "cost_stress_expectancy_r": {
                "additional_0.05R": expectancy - 0.05 if expectancy is not None else None,
                "additional_0.10R": expectancy - 0.10 if expectancy is not None else None,
            },
        }


def _existing_run(path: Path, run_id: str) -> dict[str, object] | None:
    if not path.exists():
        return None
    initialize_failed_seller_store(path)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT run_json FROM failed_seller_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def run(args: argparse.Namespace) -> dict[str, object]:
    contract = failed_seller_feature_contract()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    dataset_fingerprint = str(manifest.get("dataset_fingerprint") or "")
    if not dataset_fingerprint:
        raise RuntimeError("Frozen Dataset besitzt keinen Fingerprint.")
    code_fingerprint = _code_fingerprint()
    identity = {
        "version": FAILED_SELLER_FEATURE_VERSION,
        "work_request_id": FAILED_SELLER_WORK_REQUEST_ID,
        "dataset_fingerprint": dataset_fingerprint,
        "feature_contract_fingerprint": contract["feature_contract_fingerprint"],
        "code_fingerprint": code_fingerprint,
        "scope": "development_objective_pullback_equities_etf",
    }
    run_id = f"failed-seller-{_fingerprint(identity)[:32]}"
    existing = _existing_run(Path(args.output_db), run_id)
    if existing is not None:
        existing["idempotent_replay"] = True
        return existing

    started_at = datetime.now(timezone.utc).isoformat()
    broad_before = {
        "size": Path(args.broad_db).stat().st_size,
        "mtime_ns": Path(args.broad_db).stat().st_mtime_ns,
    }
    manifest_sha = _file_sha256(Path(args.manifest))
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    commit_hash = _git("rev-parse", "HEAD")

    variants = (
        "failed_seller_attempts_exactly_1",
        "failed_seller_attempts_exactly_2",
        "confirmation_close_location_gte_0_70",
        "confirmation_close_location_gte_0_80",
    )
    stats = {
        variant: {"selected": _Stats(), "control": _Stats()} for variant in variants
    }
    baseline = _Stats()
    strata = {key: Counter() for key in ("asset_class", "year", "regime", "region", "market_scope")}
    missing_reasons: Counter[str] = Counter()
    raw_case_n = 0
    valid_feature_n = 0
    universe_digest = hashlib.sha256()

    stage_fd, stage_name = tempfile.mkstemp(prefix="failed-seller-stage-", suffix=".sqlite3")
    os.close(stage_fd)
    stage_path = Path(stage_name)
    stage = sqlite3.connect(stage_path)
    stage.execute(
        "CREATE TABLE features (candidate_id TEXT PRIMARY KEY, feature_json TEXT NOT NULL, feature_fingerprint TEXT NOT NULL)"
    )
    stage.execute("PRAGMA synchronous=OFF")
    try:
        current_symbol: str | None = None
        history = pd.DataFrame()
        atr = pd.Series(dtype=float)
        day_positions: dict[str, int] = {}
        with _readonly(Path(args.broad_db)) as source:
            for row in source.execute(QUERY):
                raw_case_n += 1
                item = dict(row)
                symbol = str(item["symbol"])
                if symbol != current_symbol:
                    if current_symbol is not None:
                        stage.commit()
                    current_symbol = symbol
                    try:
                        history = _history_for_symbol(Path(args.manifest), manifest, symbol)
                        atr = causal_atr14(history) if not history.empty else pd.Series(dtype=float)
                        day_positions = {
                            pd.Timestamp(day).date().isoformat(): index
                            for index, day in enumerate(history.index)
                        }
                    except Exception:
                        history = pd.DataFrame()
                        atr = pd.Series(dtype=float)
                        day_positions = {}
                universe_digest.update(
                    f"{symbol}|{item.get('listing_id')}|{item.get('issuer_id')}\n".encode("utf-8")
                )
                signal_day = str(item["signal_day"])
                start_day = str(item.get("pullback_start_day") or "")
                try:
                    if history.empty:
                        raise RuntimeError("frozen_history_unavailable")
                    signal_position = day_positions[signal_day]
                    start_position = day_positions[start_day]
                    feature = build_failed_seller_feature(
                        history,
                        pullback_start_day=start_day,
                        signal_day=signal_day,
                        candidate_id=str(item["candidate_id"]),
                        dataset_fingerprint=dataset_fingerprint,
                        prepared_history=True,
                        pullback_start_position=start_position,
                        signal_position=signal_position,
                        atr14_series=atr,
                    )
                    feature["feature_status"] = "available"
                    feature["feature_fingerprint"] = _fingerprint(
                        {key: value for key, value in feature.items() if key != "feature_fingerprint"}
                    )
                    valid_feature_n += 1
                    flags = dict(feature["isolated_variant_flags"])
                    dependency_status = (
                        "KNOWN" if str(item.get("identity_confidence") or "").lower() == "verified"
                        else "UNKNOWN"
                    )
                    evaluation = {
                        **item,
                        "dependency_status": dependency_status,
                    }
                    baseline.update(evaluation)
                    for variant in variants:
                        stats[variant]["selected" if flags[variant] else "control"].update(evaluation)
                    strata["asset_class"][str(item.get("asset_class") or "UNKNOWN")] += 1
                    strata["year"][signal_day[:4]] += 1
                    strata["regime"][str(item.get("regime") or "UNKNOWN")] += 1
                    strata["region"][str(item.get("region") or "UNKNOWN")] += 1
                    strata["market_scope"][
                        "ETF" if str(item.get("asset_class")) == "ETF" else "EQUITIES"
                    ] += 1
                except Exception as exc:
                    reason = str(exc) or exc.__class__.__name__
                    missing_reasons[reason] += 1
                    feature = {
                        "feature_version": FAILED_SELLER_FEATURE_VERSION,
                        "feature_contract_fingerprint": contract["feature_contract_fingerprint"],
                        "candidate_id": str(item["candidate_id"]),
                        "dataset_fingerprint": dataset_fingerprint,
                        "feature_at": signal_day,
                        "feature_status": "unavailable",
                        "reason": reason,
                        "future_bars_used": 0,
                        "labels_present": False,
                        "automatic_trade_rule": False,
                    }
                    feature["feature_fingerprint"] = _fingerprint(feature)
                stage.execute(
                    "INSERT INTO features VALUES (?, ?, ?)",
                    (
                        feature["candidate_id"],
                        _canonical_json(feature),
                        feature["feature_fingerprint"],
                    ),
                )
                if raw_case_n % 10_000 == 0:
                    stage.commit()
                    print(
                        json.dumps(
                            {"processed": raw_case_n, "available": valid_feature_n},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
        stage.commit()

        variant_results: dict[str, object] = {}
        for variant in variants:
            selected = stats[variant]["selected"].result()
            control = stats[variant]["control"].result()
            variant_results[variant] = {
                "selected": selected,
                "control": control,
                "incremental_expectancy_r": (
                    float(selected["expectancy_r"]) - float(control["expectancy_r"])
                    if selected["expectancy_r"] is not None and control["expectancy_r"] is not None
                    else None
                ),
            }

        result = {
            "status": "DEVELOPMENT_ONLY_DESCRIPTIVE_IDENTITY_LIMITED",
            "raw_case_n": raw_case_n,
            "valid_feature_n": valid_feature_n,
            "missing_feature_n": raw_case_n - valid_feature_n,
            "missing_reasons": dict(missing_reasons.most_common()),
            "baseline": baseline.result(),
            "variants": variant_results,
            "strata_counts": {
                key: dict(sorted(values.items())) for key, values in strata.items()
            },
            "research_attempt_count": len(variants),
            "attempts": list(variants),
            "combination_variants_evaluated": [],
            "combination_gate": "BLOCKED_UNTIL_ISOLATED_OOS_AND_WALK_FORWARD_VALUE",
            "result_direction": "INCONCLUSIVE",
            "identity_limit": (
                "Broad-v1 issuer IDs are predominantly name-derived; they are not promoted "
                "to verified independent evidence in this new epoch."
            ),
            "validation_opened": False,
            "holdout_opened": False,
            "strategy_activated": False,
        }
        completed_at = datetime.now(timezone.utc).isoformat()
        run = finalize_run_payload(
            {
                "run_id": run_id,
                "work_request_id": FAILED_SELLER_WORK_REQUEST_ID,
                "branch": branch,
                "commit_hash": commit_hash,
                "code_fingerprint": code_fingerprint,
                "dataset_fingerprint": dataset_fingerprint,
                "feature_contract_fingerprint": contract["feature_contract_fingerprint"],
                "research_contract_fingerprint": _fingerprint(contract),
                "universe_fingerprint": universe_digest.hexdigest(),
                "start_time": started_at,
                "end_time": completed_at,
                "command": "scripts/run_failed_seller_research.py --development-only",
                "config": {
                    "research_split": "development",
                    "setup_scope": "objective_pullback",
                    "asset_scopes": ["EQUITIES", "ETF"],
                    "source_database_mode": "read_only",
                    "manifest_sha256": manifest_sha,
                },
                "attempts": list(variants),
                "result": result,
                "output_artifacts": [
                    str(Path(args.output_db).relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    str(Path(args.report).relative_to(PROJECT_ROOT)).replace("\\", "/"),
                ],
                "status": "COMPLETED_DEVELOPMENT_ONLY",
                "automatic_strategy_change": False,
                "multi_asset_scan_started": False,
            }
        )

        initialize_failed_seller_store(Path(args.output_db))
        with sqlite3.connect(args.output_db) as destination:
            destination.execute("PRAGMA foreign_keys=ON")
            destination.execute(
                "INSERT INTO failed_seller_runs VALUES (?, ?, ?)",
                (run_id, _canonical_json(run), run["run_fingerprint"]),
            )
            destination.execute("ATTACH DATABASE ? AS stage", (str(stage_path),))
            destination.execute(
                """INSERT INTO failed_seller_features
                   SELECT ?, candidate_id, feature_json, feature_fingerprint FROM stage.features""",
                (run_id,),
            )
            for index, variant in enumerate(variants, start=1):
                destination.execute(
                    "INSERT INTO failed_seller_attempt_ledger VALUES (?, ?, ?)",
                    (run_id, index, variant),
                )
            destination.commit()
        with sqlite3.connect(args.output_db) as destination:
            destination.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        broad_after = {
            "size": Path(args.broad_db).stat().st_size,
            "mtime_ns": Path(args.broad_db).stat().st_mtime_ns,
        }
        if broad_before != broad_after:
            raise RuntimeError("Protected Broad-v1 database changed during the read-only run.")
        report_payload = {
            **run,
            "protected_broad_snapshot_before": broad_before,
            "protected_broad_snapshot_after": broad_after,
            "protected_broad_unchanged": True,
            "output_database_sha256": _file_sha256(Path(args.output_db)),
        }
        report_payload["report_fingerprint"] = _fingerprint(report_payload)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report_payload
    finally:
        stage.close()
        if stage_path.exists():
            stage_path.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--broad-db", type=Path, default=DEFAULT_BROAD_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> None:
    payload = run(_parser().parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
