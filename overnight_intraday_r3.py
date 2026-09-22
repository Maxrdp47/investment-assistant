from __future__ import annotations

"""One append-only, development-only R3 decomposition over frozen OHLC bars."""

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from statistics import median
from typing import Any, Callable

import numpy as np
import pandas as pd

from overnight_intraday_research import (
    add_overnight_intraday_research_labels,
    build_overnight_intraday_features,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT / "config" / "overnight_intraday_r3_v1.json"


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def number(value: Any) -> float | None:
    result = float(value)
    return round(result, 12) if math.isfinite(result) else None


def load_contract(path: Path = DEFAULT_CONTRACT) -> tuple[dict[str, Any], str]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if contract.get("program_block") != "R3" or contract.get("attempt_count") != 1:
        raise ValueError("Only the frozen single-attempt R3 contract is accepted")
    research = contract["research"]
    if research["primary_feature"] != "rolling_overnight_bias":
        raise ValueError("R3 primary feature changed")
    if research["baseline_feature"] != "prior_20_session_close_to_close_return":
        raise ValueError("R3 baseline changed")
    if research["horizons_sessions"] != [1, 5, 20]:
        raise ValueError("R3 horizons changed")
    return contract, digest(contract)


def project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def source_connection(contract: dict[str, Any]) -> sqlite3.Connection:
    source = contract["source"]
    path = project_path(source["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    version = connection.execute(
        "SELECT dataset_fingerprint FROM projection_versions WHERE version=?",
        (source["projection_version"],),
    ).fetchone()
    if version is None or version[0] != source["dataset_fingerprint"]:
        connection.close()
        raise RuntimeError("Frozen R3 source dataset fingerprint mismatch")
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        connection.close()
        raise RuntimeError("Frozen R3 source failed SQLite quick_check")
    return connection


def source_assets(connection: sqlite3.Connection) -> list[tuple[str, str | None, str]]:
    rows = connection.execute(
        "SELECT asset_id, listing_id, MIN(asset_class) "
        "FROM active_bars GROUP BY asset_id, listing_id ORDER BY asset_id, listing_id"
    ).fetchall()
    return [(str(asset), listing, str(asset_class)) for asset, listing, asset_class in rows]


def _partial_correlation(x: np.ndarray, y: np.ndarray, baseline: np.ndarray) -> float | None:
    if len(x) < 3:
        return None
    design = np.column_stack((np.ones(len(x)), baseline))
    x_residual = x - design @ np.linalg.lstsq(design, x, rcond=None)[0]
    y_residual = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
    if np.std(x_residual) <= 1e-14 or np.std(y_residual) <= 1e-14:
        return None
    return number(np.corrcoef(x_residual, y_residual)[0, 1])


def asset_summaries(
    connection: sqlite3.Connection,
    *,
    asset_id: str,
    listing_id: str | None,
    asset_class: str,
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    rows = connection.execute(
        "SELECT session_date, open, high, low, close FROM active_bars "
        "WHERE asset_id=? AND listing_id IS ? ORDER BY session_date",
        (asset_id, listing_id),
    ).fetchall()
    if not rows:
        return [], 0
    frame = pd.DataFrame(rows, columns=["date", "Open", "High", "Low", "Close"])
    frame.index = pd.to_datetime(frame.pop("date"))
    research = contract["research"]
    frame = build_overnight_intraday_features(
        frame, rolling_window=research["rolling_window_sessions"]
    )
    frame["baseline_momentum_20"] = frame["Close"].div(frame["Close"].shift(20)).sub(1)
    frame = add_overnight_intraday_research_labels(
        frame, horizons=research["horizons_sessions"]
    )
    frame = frame.loc[contract["population"]["start"] : contract["population"]["end"]]
    result: list[dict[str, Any]] = []
    for year, cohort in frame.groupby(frame.index.year, sort=True):
        for horizon in research["horizons_sessions"]:
            fields = [
                "rolling_overnight_bias",
                "baseline_momentum_20",
                f"forward_return_{horizon}s",
            ]
            valid = cohort.loc[:, fields].replace([np.inf, -np.inf], np.nan).dropna()
            x = valid[fields[0]].to_numpy(dtype=float)
            b = valid[fields[1]].to_numpy(dtype=float)
            y = valid[fields[2]].to_numpy(dtype=float)
            raw = (
                number(np.corrcoef(x, y)[0, 1])
                if len(valid) >= 3 and np.std(x) > 1e-14 and np.std(y) > 1e-14
                else None
            )
            secondary = {}
            for feature in research["secondary_descriptive_features"]:
                values = pd.to_numeric(cohort[feature], errors="coerce")
                values = values.replace([np.inf, -np.inf], np.nan).dropna()
                secondary[feature] = number(values.mean()) if len(values) else None
            eligible = cohort.loc[valid.index]
            mfe = pd.to_numeric(eligible[f"forward_mfe_{horizon}s"], errors="coerce")
            mae = pd.to_numeric(eligible[f"forward_mae_{horizon}s"], errors="coerce")
            result.append(
                {
                    "asset_id": asset_id,
                    "listing_id": listing_id,
                    "asset_class": asset_class,
                    "year": int(year),
                    "horizon_sessions": horizon,
                    "cases": len(valid),
                    "raw_correlation": raw,
                    "partial_correlation_vs_baseline": _partial_correlation(x, y, b),
                    "mean_forward_return": number(y.mean()) if len(y) else None,
                    "mean_forward_mfe": number(mfe.mean()) if len(mfe) else None,
                    "mean_forward_mae": number(mae.mean()) if len(mae) else None,
                    "secondary_feature_means": secondary,
                    "minimum_cases_met": len(valid) >= research["minimum_asset_year_cases"],
                    "seen_data_only": True,
                }
            )
    return result, len(rows)


def init_result_store(path: Path, *, contract: dict[str, Any], contract_fingerprint: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_manifest (
            version TEXT PRIMARY KEY,
            contract_fingerprint TEXT NOT NULL,
            source_dataset_fingerprint TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS asset_progress (
            asset_key TEXT PRIMARY KEY,
            source_bar_count INTEGER NOT NULL,
            summary_count INTEGER NOT NULL,
            summary_digest TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS summaries (
            asset_key TEXT NOT NULL REFERENCES asset_progress(asset_key),
            year INTEGER NOT NULL,
            horizon_sessions INTEGER NOT NULL,
            summary_json TEXT NOT NULL,
            summary_digest TEXT NOT NULL,
            PRIMARY KEY(asset_key, year, horizon_sessions)
        );
        CREATE TABLE IF NOT EXISTS final_review (
            version TEXT PRIMARY KEY REFERENCES run_manifest(version),
            review_json TEXT NOT NULL,
            review_digest TEXT NOT NULL
        );
        """
    )
    existing = connection.execute(
        "SELECT contract_fingerprint,source_dataset_fingerprint FROM run_manifest WHERE version=?",
        (contract["version"],),
    ).fetchone()
    expected = (contract_fingerprint, contract["source"]["dataset_fingerprint"])
    if existing is None:
        connection.execute(
            "INSERT INTO run_manifest VALUES (?,?,?,?)",
            (contract["version"], *expected, json.dumps(contract, sort_keys=True)),
        )
        connection.commit()
    elif tuple(existing) != expected:
        connection.close()
        raise RuntimeError("R3 append-only result store fingerprint mismatch")
    return connection


def persist_asset(
    store: sqlite3.Connection,
    *,
    asset_key: str,
    summaries: list[dict[str, Any]],
    source_bar_count: int,
) -> None:
    payloads = [json.dumps(item, sort_keys=True, allow_nan=False) for item in summaries]
    with store:
        store.execute(
            "INSERT INTO asset_progress VALUES (?,?,?,?)",
            (asset_key, source_bar_count, len(summaries), digest(summaries)),
        )
        store.executemany(
            "INSERT INTO summaries VALUES (?,?,?,?,?)",
            [
                (
                    asset_key,
                    item["year"],
                    item["horizon_sessions"],
                    payload,
                    digest(item),
                )
                for item, payload in zip(summaries, payloads, strict=True)
            ],
        )


def _review_rows(rows: list[dict[str, Any]], *, contract: dict[str, Any]) -> dict[str, Any]:
    minimum = contract["research"]["minimum_asset_year_cases"]
    summaries = []
    for horizon in contract["research"]["horizons_sessions"]:
        horizon_rows = [
            item for item in rows
            if item["horizon_sessions"] == horizon
            and item["cases"] >= minimum
            and item["partial_correlation_vs_baseline"] is not None
        ]
        by_year = []
        for year in range(2016, 2022):
            subset = [item for item in horizon_rows if item["year"] == year]
            coefficients = [item["partial_correlation_vs_baseline"] for item in subset]
            by_year.append(
                {
                    "year": year,
                    "asset_year_groups": len(subset),
                    "cases": sum(item["cases"] for item in subset),
                    "median_partial_correlation": number(median(coefficients)) if coefficients else None,
                    "positive_group_fraction": number(sum(x > 0 for x in coefficients) / len(coefficients)) if coefficients else None,
                }
            )
        coefficients = [item["partial_correlation_vs_baseline"] for item in horizon_rows]
        summaries.append(
            {
                "horizon_sessions": horizon,
                "asset_year_groups": len(horizon_rows),
                "cases": sum(item["cases"] for item in horizon_rows),
                "median_partial_correlation": number(median(coefficients)) if coefficients else None,
                "positive_group_fraction": number(sum(x > 0 for x in coefficients) / len(coefficients)) if coefficients else None,
                "by_year": by_year,
            }
        )
    return {
        "version": contract["version"],
        "program_block": "R3",
        "attempt_count": 1,
        "source_dataset_fingerprint": contract["source"]["dataset_fingerprint"],
        "development": summaries,
        "status": "DEVELOPMENT_DESCRIPTIVE_ONLY_SEEN_DATA",
        "validation": "NOT_OPENED",
        "holdout": "NOT_OPENED",
        "effective_n": "UNKNOWN_DEPENDENCIES",
        "robust_challenger_eligible": False,
        "trade_rule_created": False,
        "cost_model_status": "NOT_APPLICABLE_NO_TRADABLE_VARIANT",
    }


def run(
    contract_path: Path = DEFAULT_CONTRACT,
    *,
    max_assets: int | None = None,
    should_pause: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    contract, contract_fingerprint = load_contract(contract_path)
    source = source_connection(contract)
    store = init_result_store(
        project_path(contract["runtime"]["result_store"]),
        contract=contract,
        contract_fingerprint=contract_fingerprint,
    )
    try:
        assets = source_assets(source)
        if store.execute("SELECT 1 FROM final_review WHERE version=?", (contract["version"],)).fetchone():
            payload = store.execute(
                "SELECT review_json FROM final_review WHERE version=?", (contract["version"],)
            ).fetchone()[0]
            return {"terminal_no_op": True, "review": json.loads(payload)}
        processed = 0
        for asset_id, listing_id, asset_class in assets:
            asset_key = json.dumps([asset_id, listing_id], separators=(",", ":"))
            if store.execute("SELECT 1 FROM asset_progress WHERE asset_key=?", (asset_key,)).fetchone():
                continue
            if should_pause is not None and should_pause():
                return {
                    "complete": False,
                    "paused_for_production": True,
                    "processed_this_call": processed,
                    "completed_assets": store.execute("SELECT COUNT(*) FROM asset_progress").fetchone()[0],
                    "total_assets": len(assets),
                }
            summaries, source_bars = asset_summaries(
                source,
                asset_id=asset_id,
                listing_id=listing_id,
                asset_class=asset_class,
                contract=contract,
            )
            persist_asset(store, asset_key=asset_key, summaries=summaries, source_bar_count=source_bars)
            processed += 1
            if max_assets is not None and processed >= max_assets:
                break
        completed = store.execute("SELECT COUNT(*) FROM asset_progress").fetchone()[0]
        if completed != len(assets):
            return {"complete": False, "processed_this_call": processed, "completed_assets": completed, "total_assets": len(assets)}
        rows = [json.loads(row[0]) for row in store.execute("SELECT summary_json FROM summaries ORDER BY asset_key,year,horizon_sessions")]
        review = _review_rows(rows, contract=contract)
        review["contract_fingerprint"] = contract_fingerprint
        review["source_assets"] = len(assets)
        review["source_bars"] = store.execute("SELECT SUM(source_bar_count) FROM asset_progress").fetchone()[0]
        with store:
            store.execute(
                "INSERT INTO final_review VALUES (?,?,?)",
                (contract["version"], json.dumps(review, sort_keys=True, allow_nan=False), digest(review)),
            )
        return {"complete": True, "review": review}
    finally:
        source.close()
        store.close()
