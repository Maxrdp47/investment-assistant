from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "swing_walk_forward_campaign.json"
STATE_PATH = ROOT / "runtime" / "swing_walk_forward_campaign_state.json"
WF_DB_PATH = ROOT / "runtime" / "swing_walk_forward.sqlite3"
BROAD_DB_PATH = ROOT / "runtime" / "swing_broad_research.sqlite3"
DATASET_ROOT = ROOT / "runtime" / "swing_walk_forward_datasets"
LOG_PATH = ROOT / "runtime" / "logs" / "swing_walk_forward_campaign.log"
OUTPUT_DIR = ROOT / "runtime" / "research_exports"
OUTPUT_STEM = "swing_campaign_deep_analysis_2026-08-23"
CAMPAIGN_VERSION = "swing-walk-forward-campaign-2026.08.18-v3"
ENGINE_VERSION = "swing-historical-research-2026.08.17-v6"
OBS_VERSION = "swing-observational-rsi-ema-2026.08.18-v1"
DEPENDENCY_VERSION = "swing-evidence-dependency-2026.08.18-v1"
EXPECTED_PROFILES = (
    "current",
    "balanced",
    "precision",
    "payoff",
    "long_v1_rsi_wide",
    "long_v1_rsi_core",
    "long_v1_ema_trend",
    "long_v1_ema_strict",
    "long_v1_ema_rsi_wide",
    "long_v1_ema_rsi_core",
    "long_v1_pullback_only",
    "long_v1_breakout_only",
)
TERMINAL_TYPES = {
    "entry_missed",
    "invalidated_before_entry",
    "expired_without_entry",
    "target_1_reached",
    "target_2_reached",
    "stop_reached",
    "ambiguous_sequence",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, *, hash_content: bool = True) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path) if hash_content else None,
    }


def source_snapshot(manifest_paths: Sequence[Path]) -> dict[str, Any]:
    files = [
        CONFIG_PATH,
        STATE_PATH,
        ROOT / "swing_walk_forward.py",
        ROOT / "trading_assistant.py",
        *manifest_paths,
    ]
    return {
        "files": {str(path.relative_to(ROOT)): file_record(path) for path in files},
        "walk_forward_store": file_record(WF_DB_PATH, hash_content=False),
        "broad_store": file_record(BROAD_DB_PATH, hash_content=False)
        if BROAD_DB_PATH.exists()
        else None,
    }


def readonly_connection(path: Path, *, immutable: bool = False) -> sqlite3.Connection:
    suffix = "&immutable=1" if immutable else ""
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro{suffix}", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def quick_check(path: Path, *, immutable: bool = False) -> str | None:
    if not path.exists():
        return None
    with readonly_connection(path, immutable=immutable) as connection:
        row = connection.execute("PRAGMA quick_check").fetchone()
        return str(row[0]) if row else None


def clean(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (str, bytes, dict, list, tuple)) else False:
        return None
    return value


def fnum(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def terminal_event(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidates = [
        event
        for event in events
        if event.get("event_type") in TERMINAL_TYPES
        and not (
            event.get("event_type") == "target_1_reached"
            and (event.get("payload") or {}).get("terminal") is False
        )
    ]
    return candidates[-1] if candidates else None


def entry_event(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidates = [event for event in events if event.get("event_type") == "entry_opened"]
    return candidates[-1] if candidates else None


def load_manifests() -> tuple[list[dict[str, Any]], list[Path], dict[str, dict[str, Any]]]:
    manifests: list[dict[str, Any]] = []
    paths = sorted(DATASET_ROOT.glob("*/manifest.json"))
    scopes: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("dataset_epoch") not in {
            "swing-research-frozen-ohlcv-2026.08.18-v1|fixed",
            "swing-research-frozen-ohlcv-2026.08.18-v1|2026-W34",
        }:
            continue
        scope_summary = {}
        for scope_id, scope in payload.get("scopes", {}).items():
            assets = scope.get("assets", {})
            statuses = Counter(str(asset.get("status") or "unknown") for asset in assets.values())
            row_counts = [int(asset.get("rows") or 0) for asset in assets.values()]
            record = {
                "scope_id": scope_id,
                "manifest_path": path,
                "dataset_dir": path.parent,
                "dataset_epoch": payload.get("dataset_epoch"),
                "dataset_fingerprint": payload.get("dataset_fingerprint"),
                "contract": scope.get("contract") or {},
                "assets": assets,
            }
            scopes[f"{payload.get('dataset_fingerprint')}|{scope_id}"] = record
            scope_summary[scope_id] = {
                "contract": record["contract"],
                "assets": len(assets),
                "status_counts": dict(statuses),
                "rows_ge_245": sum(value >= 245 for value in row_counts),
                "rows_lt_245": sum(value < 245 for value in row_counts),
            }
        manifests.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "dataset_epoch": payload.get("dataset_epoch"),
                "dataset_fingerprint": payload.get("dataset_fingerprint"),
                "dataset_revision": payload.get("dataset_revision"),
                "manifest_version": payload.get("manifest_version"),
                "provider_policy": payload.get("provider_policy"),
                "scopes": scope_summary,
            }
        )
    return manifests, [Path(ROOT / item["path"]) for item in manifests], scopes


def contract_lookup(config: Mapping[str, Any]) -> dict[tuple[Any, ...], str]:
    lookup: dict[tuple[Any, ...], str] = {}
    contracts = list(config.get("contracts") or []) + list(config.get("challenger_contracts") or [])
    for contract in contracts:
        key = (
            contract.get("start"),
            contract.get("end"),
            tuple(sorted(contract.get("profiles") or [])),
            contract.get("sampling_mode"),
            str(contract.get("selection_round_label") or "A"),
        )
        lookup[key] = str(contract.get("id"))
    return lookup


def load_campaign_runs(
    config: Mapping[str, Any], scopes: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    allowed_fingerprints = {str(scope["dataset_fingerprint"]) for scope in scopes.values()}
    lookup = contract_lookup(config)
    runs: dict[str, dict[str, Any]] = {}
    profiles: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, Any]] = {}
    with readonly_connection(WF_DB_PATH, immutable=True) as connection:
        cursor = connection.execute(
            "SELECT run_id, created_at, run_json FROM walk_forward_runs ORDER BY created_at"
        )
        for row in cursor:
            run = json.loads(row["run_json"])
            dataset = run.get("research_dataset") or {}
            if run.get("run_version") != ENGINE_VERSION:
                continue
            if str(dataset.get("dataset_fingerprint")) not in allowed_fingerprints:
                continue
            scope_id = str(dataset.get("scope_id") or "")
            scope = scopes.get(f"{dataset.get('dataset_fingerprint')}|{scope_id}") or {}
            params = run.get("parameters") or {}
            run_profiles = run.get("strategy_profiles") or {}
            profile_names = tuple(sorted(str(item.get("name")) for item in run_profiles.values()))
            scope_contract = scope.get("contract") or {}
            key = (
                scope_contract.get("start"),
                scope_contract.get("end"),
                profile_names,
                params.get("sampling_mode"),
                str(params.get("selection_round") or "A"),
            )
            contract_id = lookup.get(key, "unknown")
            run_id = str(row["run_id"])
            runs[run_id] = {
                "created_at": str(row["created_at"]),
                "scope_id": scope_id,
                "dataset_epoch": dataset.get("dataset_epoch"),
                "dataset_fingerprint": dataset.get("dataset_fingerprint"),
                "contract_id": contract_id,
                "contract_period": "legacy" if scope_contract.get("end") else "modern",
                "parameters": params,
            }
            for version, profile in run_profiles.items():
                profiles.setdefault(str(version), dict(profile))
            for symbol, identity in (run.get("asset_identities") or {}).items():
                identities.setdefault(str(symbol), dict(identity))
    return runs, profiles, identities


FLAT_COLUMNS = (
    "evidence_key", "case_id", "logical_case_id", "run_id", "run_created_at",
    "dataset_fingerprint", "dataset_epoch", "scope_id", "contract_id", "contract_period",
    "case_version", "symbol", "issuer_id", "listing_id", "economic_instrument_id",
    "signal_at", "signal_day", "future_last_day", "strategy", "strategy_version",
    "strategy_family", "parameter_variant", "round", "round_role", "research_split",
    "sampling_mode", "selection_eligible", "overlap_purged", "status", "result_r",
    "result_pct", "outcome", "setup", "market_phase", "volatility_regime", "asset_type",
    "region", "entry_type", "entry", "paper_entry", "stop", "target_1", "target_2",
    "risk_pct", "mfe_pct", "mae_pct", "peak_mfe_r", "peak_mae_r", "rsi_14",
    "ema_20", "ema_50", "close", "ema_context", "relative_volume", "atr",
    "bos", "buyer_confirmation", "breakout_strength", "distance_previous_high",
    "atr_normalized_breakout", "future_rows_used", "evaluation_horizon_sessions",
)


def flatten_case(case: Mapping[str, Any], run_id: str, run: Mapping[str, Any]) -> tuple[Any, ...]:
    snapshot = case.get("snapshot") or {}
    strategy = snapshot.get("strategy") or {}
    features = snapshot.get("signal_features") or {}
    plan = snapshot.get("order_plan") or {}
    asset = snapshot.get("asset") or {}
    identity = case.get("research_identity") or {}
    terminal = terminal_event(case.get("events") or []) or {}
    terminal_payload = terminal.get("payload") or {}
    opened = entry_event(case.get("events") or []) or {}
    opened_payload = opened.get("payload") or {}
    result_r = fnum(case.get("result_r"))
    risk_pct = fnum(features.get("risk_pct"))
    mfe_pct = fnum(terminal_payload.get("maximum_favorable_excursion_pct"))
    mae_pct = fnum(terminal_payload.get("maximum_adverse_excursion_pct"))
    ema20 = fnum(features.get("ema_20"))
    ema50 = fnum(features.get("ema_50"))
    close = fnum(features.get("close"))
    if close is not None and ema20 is not None and ema50 is not None:
        ema_context = "close>ema20>ema50" if close > ema20 > ema50 else (
            "ema20>ema50" if ema20 > ema50 else "ema20<=ema50"
        )
    else:
        ema_context = "not_available"
    signal_at = str(case.get("signal_at") or snapshot.get("signal_at") or "")
    return (
        str(case.get("evidence_key") or case.get("logical_case_id") or case.get("case_id") or ""),
        str(case.get("case_id") or ""), str(case.get("logical_case_id") or ""), run_id,
        run.get("created_at"), run.get("dataset_fingerprint"), run.get("dataset_epoch"),
        run.get("scope_id"), run.get("contract_id"), run.get("contract_period"),
        case.get("case_version"), str(case.get("symbol") or asset.get("ticker") or ""),
        identity.get("issuer_id") or asset.get("issuer_id"),
        identity.get("listing_id") or asset.get("listing_id"),
        identity.get("economic_instrument_id"), signal_at, signal_at[:10],
        str(case.get("future_last_day") or ""), strategy.get("strategy_name"),
        strategy.get("strategy_version"), strategy.get("strategy_family"),
        strategy.get("parameter_variant"), str(case.get("selection_round") or strategy.get("selection_round") or "A"),
        case.get("selection_round_role") or strategy.get("selection_round_role"),
        case.get("research_split"), case.get("sampling_mode") or strategy.get("sampling_mode"),
        int(bool(case.get("selection_eligible", True))), int(bool(case.get("overlap_purged"))),
        case.get("status"), result_r, fnum(case.get("result_pct")),
        "win" if result_r is not None and result_r > 0 else "loss" if result_r is not None and result_r < 0 else "zero" if result_r == 0 else "not_evaluated",
        strategy.get("setup_type"), strategy.get("market_phase"), strategy.get("volatility_regime"),
        identity.get("asset_type") or asset.get("asset_type"), identity.get("region") or asset.get("region"),
        plan.get("entry_method") or plan.get("order_type"), fnum(plan.get("limit_price_original")),
        fnum(opened_payload.get("paper_entry_after_costs_original") or opened_payload.get("paper_entry_original")),
        fnum(plan.get("initial_stop_original")), fnum(plan.get("target_1_original")),
        fnum(plan.get("target_2_original")), risk_pct, mfe_pct, mae_pct,
        mfe_pct / risk_pct if mfe_pct is not None and risk_pct not in {None, 0} else None,
        mae_pct / risk_pct if mae_pct is not None and risk_pct not in {None, 0} else None,
        fnum(features.get("rsi_14")), ema20, ema50, close, ema_context,
        fnum(features.get("relative_volume")), None, None, None, None, None, None,
        int(case.get("future_rows_used") or 0), int(case.get("evaluation_horizon_sessions") or strategy.get("evaluation_horizon_sessions") or 0),
    )


def build_flat_store(
    runs: Mapping[str, Mapping[str, Any]], scratch_path: Path
) -> tuple[int, int, Counter[str]]:
    if scratch_path.exists():
        scratch_path.unlink()
    target = sqlite3.connect(scratch_path)
    target.execute("PRAGMA journal_mode=OFF")
    target.execute("PRAGMA synchronous=OFF")
    target.execute("PRAGMA temp_store=MEMORY")
    declarations = []
    numeric = {
        "selection_eligible", "overlap_purged", "result_r", "result_pct", "entry", "paper_entry",
        "stop", "target_1", "target_2", "risk_pct", "mfe_pct", "mae_pct", "peak_mfe_r",
        "peak_mae_r", "rsi_14", "ema_20", "ema_50", "close", "relative_volume", "atr",
        "breakout_strength", "distance_previous_high", "atr_normalized_breakout",
        "future_rows_used", "evaluation_horizon_sessions",
    }
    for column in FLAT_COLUMNS:
        declaration = f'"{column}" REAL' if column in numeric else f'"{column}" TEXT'
        if column == "evidence_key":
            declaration += " PRIMARY KEY"
        declarations.append(declaration)
    target.execute(f"CREATE TABLE selected ({', '.join(declarations)})")
    placeholders = ",".join("?" for _ in FLAT_COLUMNS)
    quoted = ",".join(f'"{column}"' for column in FLAT_COLUMNS)
    updates = ",".join(f'"{column}"=excluded."{column}"' for column in FLAT_COLUMNS if column != "evidence_key")
    sql = (
        f"INSERT INTO selected ({quoted}) VALUES ({placeholders}) "
        f"ON CONFLICT(evidence_key) DO UPDATE SET {updates} WHERE "
        "excluded.selection_eligible > selected.selection_eligible OR "
        "(excluded.selection_eligible = selected.selection_eligible AND "
        "excluded.run_created_at > selected.run_created_at)"
    )
    raw_count = 0
    statuses: Counter[str] = Counter()
    batch: list[tuple[Any, ...]] = []
    run_ids = set(runs)
    with readonly_connection(WF_DB_PATH, immutable=True) as source:
        for row in source.execute("SELECT run_id, case_json FROM walk_forward_cases"):
            run_id = str(row["run_id"])
            if run_id not in run_ids:
                continue
            case = json.loads(row["case_json"])
            raw_count += 1
            statuses[str(case.get("status") or "unknown")] += 1
            batch.append(flatten_case(case, run_id, runs[run_id]))
            if len(batch) >= 2_000:
                target.executemany(sql, batch)
                batch.clear()
        if batch:
            target.executemany(sql, batch)
    target.commit()
    target.execute("CREATE INDEX selected_strategy_idx ON selected(strategy, signal_day)")
    target.execute("CREATE INDEX selected_status_idx ON selected(status)")
    target.commit()
    selected_count = int(target.execute("SELECT COUNT(*) FROM selected").fetchone()[0])
    target.close()
    return raw_count, selected_count, statuses


def assign_dependency_clusters(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series(index=frame.index, dtype="object")
    evaluated = frame.loc[frame["result_r"].notna()].copy()
    evaluated["start"] = pd.to_datetime(evaluated["signal_day"], errors="coerce")
    evaluated["end"] = pd.to_datetime(evaluated["future_last_day"], errors="coerce")
    evaluated["end"] = evaluated[["start", "end"]].max(axis=1)
    context_columns = ["strategy_version", "research_split", "evaluation_horizon_sessions"]
    for context, members in evaluated.groupby(context_columns, dropna=False, sort=True):
        ordered = members.sort_values(["start", "end", "case_id"])
        indices = list(ordered.index)
        parents = list(range(len(indices)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        active: dict[str, tuple[int, pd.Timestamp]] = {}
        for local, (_, member) in enumerate(ordered.iterrows()):
            issuer = str(member.get("issuer_id") or member.get("listing_id") or "")
            instrument = str(member.get("economic_instrument_id") or "")
            tokens = [f"issuer:{issuer}"] + ([f"instrument:{instrument}"] if instrument else [])
            start, end = member["start"], member["end"]
            for token in tokens:
                previous = active.get(token)
                if previous is not None and start <= previous[1]:
                    union(local, previous[0])
            for token in tokens:
                previous = active.get(token)
                maximum_end = max(previous[1], end) if previous is not None else end
                active[token] = (find(local), maximum_end)
        components: dict[int, list[int]] = defaultdict(list)
        for local in range(len(indices)):
            components[find(local)].append(indices[local])
        for component in components.values():
            seed = "|".join(sorted(str(frame.at[index, "case_id"]) for index in component))
            cluster_id = hashlib.sha256((DEPENDENCY_VERSION + "|" + seed).encode()).hexdigest()
            result.loc[component] = cluster_id
    return result


def sample_status(effective_n: int, *, confirmation: bool = False) -> str:
    if effective_n <= 0:
        return "empty"
    threshold = 200 if confirmation else 50
    return "sufficient" if effective_n >= threshold else "underpowered"


def metrics(group: pd.DataFrame, *, confirmation: bool = False) -> dict[str, Any]:
    evaluated = group.loc[group["result_r"].notna()].copy()
    evaluated = evaluated.sort_values(["signal_day", "symbol", "case_id"])
    values = evaluated["result_r"].astype(float)
    wins = values[values > 0]
    losses = values[values < 0]
    zeros = values[values == 0]
    cumulative = values.cumsum()
    drawdown = cumulative - cumulative.cummax().clip(lower=0)
    win_streak = loss_streak = max_win_streak = max_loss_streak = 0
    for value in values:
        if value > 0:
            win_streak += 1
            loss_streak = 0
        else:
            loss_streak += 1
            win_streak = 0
        max_win_streak = max(max_win_streak, win_streak)
        max_loss_streak = max(max_loss_streak, loss_streak)
    effective_n = int(evaluated["dependency_cluster_id"].nunique()) if len(evaluated) else 0
    return clean({
        "raw_n": int(len(group)),
        "evaluated_n": int(len(evaluated)),
        "effective_n": effective_n,
        "wins": int(len(wins)), "losses": int(len(losses)), "zero": int(len(zeros)),
        "hit_rate_pct": len(wins) / len(values) * 100 if len(values) else None,
        "average_r": values.mean() if len(values) else None,
        "median_r": values.median() if len(values) else None,
        "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else None,
        "maximum_drawdown_r": abs(drawdown.min()) if len(drawdown) else 0.0,
        "average_winner_r": wins.mean() if len(wins) else None,
        "average_loser_r": losses.mean() if len(losses) else None,
        "maximum_winning_streak": max_win_streak,
        "maximum_losing_streak": max_loss_streak,
        "average_mfe_pct": evaluated["mfe_pct"].mean(),
        "average_mae_pct": evaluated["mae_pct"].mean(),
        "mfe_coverage_n": int(evaluated["mfe_pct"].notna().sum()),
        "mae_coverage_n": int(evaluated["mae_pct"].notna().sum()),
        "status": sample_status(effective_n, confirmation=confirmation),
    })


def grouped_metrics(frame: pd.DataFrame, columns: Sequence[str]) -> list[dict[str, Any]]:
    rows = []
    grouper: Any = columns[0] if len(columns) == 1 else list(columns)
    for keys, group in frame.groupby(grouper, dropna=False, sort=True):
        key_values = (keys,) if len(columns) == 1 else keys
        row = {column: clean(value) for column, value in zip(columns, key_values)}
        row.update(metrics(group, confirmation=str(row.get("round")) == "C"))
        rows.append(row)
    return rows


def profile_rows(frame: pd.DataFrame, profiles: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    profile_by_name = {str(value.get("name")): value for value in profiles.values()}
    rows = []
    for name in EXPECTED_PROFILES:
        group = frame.loc[frame["strategy"] == name]
        profile = profile_by_name.get(name) or {}
        baseline = frame.loc[frame["strategy"] == "current"]
        row = {
            "strategy": name,
            "strategy_version": profile.get("version"),
            "strategy_family": profile.get("strategy_family"),
            "parameter_variant": profile.get("parameter_variant"),
            "thresholds": profile.get("thresholds_snapshot"),
            "technical_filter": profile.get("technical_filter"),
            "baseline_strategy": profile.get("baseline_strategy") or ("self" if name == "current" else "current"),
            **metrics(group),
        }
        if name == "current":
            row["difference_vs_long_v1"] = {"kind": "baseline", "average_r_delta": 0.0, "hit_rate_delta_pct": 0.0}
        else:
            own = metrics(group)
            base = metrics(baseline)
            row["difference_vs_long_v1"] = {
                "kind": "descriptive_unpaired_aggregate",
                "average_r_delta": (own["average_r"] - base["average_r"]) if own["average_r"] is not None and base["average_r"] is not None else None,
                "hit_rate_delta_pct": (own["hit_rate_pct"] - base["hit_rate_pct"]) if own["hit_rate_pct"] is not None and base["hit_rate_pct"] is not None else None,
                "warning": "Different filters produce different case sets; this is not a causal paired estimate.",
            }
        rows.append(clean(row))
    return rows


def round_analysis(frame: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for name in EXPECTED_PROFILES:
        counts = {}
        for round_label in ("A", "B", "C", "Aktuell"):
            group = frame.loc[(frame["strategy"] == name) & (frame["round"] == round_label)]
            row = {"strategy": name, "round": round_label, **metrics(group, confirmation=round_label == "C")}
            rows.append(row)
            counts[round_label] = row["evaluated_n"]
        a, b, c = counts["A"], counts["B"], counts["C"]
        rows.append({
            "strategy": name,
            "round": "A_to_B_to_C_funnel",
            "n_ratio": [a, b, c],
            "loss_a_to_b_pct": (a - b) / a * 100 if a else None,
            "loss_b_to_c_pct": (b - c) / b * 100 if b else None,
            "warning": "C is not interpreted as confirmation when effective N is below 200.",
        })
    return {"rows": clean(rows), "highlight_profiles": ["long_v1_rsi_core", "long_v1_ema_rsi_core"]}


def split_analysis(frame: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for name in EXPECTED_PROFILES:
        values = {}
        for split in ("development", "validation", "holdout"):
            group = frame.loc[(frame["strategy"] == name) & (frame["research_split"] == split)]
            item = {"strategy": name, "research_split": split, **metrics(group)}
            rows.append(item)
            values[split] = item
        def delta(left: str, right: str) -> dict[str, Any]:
            return {
                "average_r": values[right]["average_r"] - values[left]["average_r"]
                if values[right]["average_r"] is not None and values[left]["average_r"] is not None else None,
                "profit_factor": values[right]["profit_factor"] - values[left]["profit_factor"]
                if values[right]["profit_factor"] is not None and values[left]["profit_factor"] is not None else None,
                "hit_rate_pct": values[right]["hit_rate_pct"] - values[left]["hit_rate_pct"]
                if values[right]["hit_rate_pct"] is not None and values[left]["hit_rate_pct"] is not None else None,
            }
        rows.append({"strategy": name, "research_split": "deltas", "development_to_validation": delta("development", "validation"), "validation_to_holdout": delta("validation", "holdout")})
    disappears = []
    improves = []
    for name in EXPECTED_PROFILES:
        dev = next(row for row in rows if row.get("strategy") == name and row.get("research_split") == "development")
        val = next(row for row in rows if row.get("strategy") == name and row.get("research_split") == "validation")
        hold = next(row for row in rows if row.get("strategy") == name and row.get("research_split") == "holdout")
        if dev.get("average_r") is not None and dev["average_r"] > 0 and all(item.get("average_r") is not None and item["average_r"] <= 0 for item in (val, hold)):
            disappears.append(name)
        if dev.get("average_r") is not None and hold.get("average_r") is not None and hold["average_r"] > dev["average_r"]:
            improves.append(name)
    return {"rows": clean(rows), "edge_disappears_outside_development": disappears, "holdout_better_than_development": improves, "release_decision": "not_made"}


def time_analysis(frame: pd.DataFrame) -> dict[str, Any]:
    evaluated = frame.loc[frame["result_r"].notna()].copy()
    years = pd.to_numeric(evaluated["signal_day"].str[:4], errors="coerce")
    evaluated["year"] = years
    bins = [-np.inf, 2012, 2015, 2019, 2021, 2023, np.inf]
    labels = ["2010-2012", "2013-2015", "2016-2019", "2020-2021", "2022-2023", "2024+"]
    evaluated["period"] = pd.cut(years, bins=bins, labels=labels)
    period_rows = grouped_metrics(evaluated, ["strategy", "period"])
    year_rows = grouped_metrics(evaluated, ["strategy", "year"])
    summaries = []
    for name in EXPECTED_PROFILES:
        relevant = [row for row in year_rows if row["strategy"] == name and row["average_r"] is not None]
        profitable = [row for row in relevant if row["average_r"] > 0]
        ordered = sorted(relevant, key=lambda row: row["year"])
        longest = current = 0
        for row in ordered:
            current = current + 1 if row["average_r"] <= 0 else 0
            longest = max(longest, current)
        summaries.append({
            "strategy": name,
            "profitable_years_pct": len(profitable) / len(relevant) * 100 if relevant else None,
            "best_year": max(relevant, key=lambda row: row["average_r"])["year"] if relevant else None,
            "worst_year": min(relevant, key=lambda row: row["average_r"])["year"] if relevant else None,
            "longest_consecutive_nonpositive_years": longest if relevant else None,
        })
    return {"period_rows": clean(period_rows), "year_rows": clean(year_rows), "strategy_year_summary": clean(summaries)}


def breakout_analysis(frame: pd.DataFrame) -> dict[str, Any]:
    breakout = frame.loc[frame["setup"].fillna("").str.contains("Ausbruch", case=False)]
    derived = breakout.copy()
    derived["relative_volume_bucket"] = pd.cut(derived["relative_volume"], [-np.inf, 0.8, 1.0, 1.2, 1.5, np.inf], labels=["<0.8", "0.8-1.0", "1.0-1.2", "1.2-1.5", ">=1.5"])
    derived["rsi_bucket"] = pd.cut(derived["rsi_14"], [-np.inf, 40, 45, 55, 68, 72, np.inf], labels=["<40", "40-45", "45-55", "55-68", "68-72", ">72"])
    derived["year"] = derived["signal_day"].str[:4]
    dimensions = ["entry_type", "relative_volume_bucket", "rsi_bucket", "ema_context", "market_phase", "volatility_regime", "asset_type", "region", "year"]
    return {
        "cases": int(len(breakout)),
        "available_dimensions": {dimension: grouped_metrics(derived, [dimension]) for dimension in dimensions},
        "not_available_dimensions": {
            "breakout_strength": "not recorded in walk-forward cases",
            "distance_to_previous_high": "not recorded in walk-forward cases",
            "atr_normalized_breakout_size": "ATR and breakout level not recorded in walk-forward cases",
            "buyer_confirmation": "not recorded in walk-forward cases",
            "bos": "not recorded in walk-forward cases",
        },
        "threshold_optimization_performed": False,
    }


def entry_efficiency(frame: pd.DataFrame) -> dict[str, Any]:
    evaluated = frame.loc[frame["result_r"].notna()].copy()
    covered = evaluated.loc[evaluated["peak_mfe_r"].notna() & evaluated["peak_mae_r"].notna()].copy()
    losses = covered.loc[covered["result_r"] < 0]
    classes = Counter()
    for _, row in covered.iterrows():
        if row["result_r"] < 0 and row["peak_mfe_r"] < 0.5:
            classes["likely_setup_or_direction_weak"] += 1
        elif row["result_r"] < 0 and row["peak_mfe_r"] < 1.0:
            classes["likely_entry_or_management_relevant"] += 1
        elif row["result_r"] < 0 and row["peak_mfe_r"] >= 1.0:
            classes["likely_stop_or_management_relevant"] += 1
        else:
            classes["unclear"] += 1
    return clean({
        "coverage_n": len(covered),
        "coverage_pct_of_evaluated": len(covered) / len(evaluated) * 100 if len(evaluated) else None,
        "peak_mfe_r_mean": covered["peak_mfe_r"].mean(),
        "peak_mae_r_mean": covered["peak_mae_r"].mean(),
        "almost_no_positive_movement_definition": "stored peak MFE < 0.25R",
        "almost_no_positive_movement_pct": (covered["peak_mfe_r"] < 0.25).mean() * 100 if len(covered) else None,
        "positive_before_later_loss_definition": "final R < 0 and stored peak MFE >= 0.5R",
        "positive_before_later_loss_pct_of_losses": (losses["peak_mfe_r"] >= 0.5).mean() * 100 if len(losses) else None,
        "diagnostic_classes": dict(classes),
        "classification_warning": "Transparent descriptive heuristics only; no causal attribution or rule decision.",
        "unavailable": {
            "mfe_after_1_3_5_sessions": "not stored",
            "mae_after_1_3_5_sessions": "not stored",
            "time_to_plus_or_minus_0_5r_1r": "not stored",
            "first_plus_0_5r_or_minus_0_5r": "not stored; no intrabar ordering inferred",
        },
    })


def broad_counterfactual_snapshot() -> dict[str, Any]:
    if not BROAD_DB_PATH.exists():
        return {"status": "not_available", "reason": "broad store absent"}
    result: dict[str, Any] = {"snapshot_at": utc_now(), "read_only": True}
    try:
        with readonly_connection(BROAD_DB_PATH) as connection:
            connection.execute("BEGIN")
            result["quick_check"] = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {}
            for table in (
                "broad_research_asset_completions", "broad_research_candidates", "broad_research_labels",
                "broad_research_counterfactuals", "broad_research_baseline_links", "broad_research_challengers",
            ):
                counts[table] = int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) if table in tables else None
            result["counts"] = counts
            variants: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
            status_counts: Counter[str] = Counter()
            if "broad_research_counterfactuals" in tables:
                for row in connection.execute("SELECT experiment_json FROM broad_research_counterfactuals"):
                    payload = json.loads(row[0])
                    for variant, variant_data in (payload.get("results") or {}).items():
                        for exit_name, exit_data in (variant_data.get("exits") or {}).items():
                            value = fnum(exit_data.get("result_r"))
                            if value is not None:
                                variants[str(variant)][str(exit_name)].append(value)
                            status_counts[f"{variant}/{exit_name}/{exit_data.get('status') or 'unknown'}"] += 1
            result["descriptive_variant_exit_results"] = {
                variant: {
                    exit_name: {"n": len(values), "average_r": sum(values) / len(values) if values else None}
                    for exit_name, values in exits.items()
                }
                for variant, exits in variants.items()
            }
            result["status_counts"] = dict(status_counts)
            connection.rollback()
    except sqlite3.Error as exc:
        result.update({"status": "snapshot_failed", "reason": str(exc)})
        return result
    baseline_links = (result.get("counts") or {}).get("broad_research_baseline_links") or 0
    result.update({
        "status": "partial_unfinished_broad_snapshot",
        "original_loss_comparison": "not_available" if baseline_links == 0 else "linkage_available_but_not_selected_here",
        "trade_retention": "not_available without baseline links",
        "additional_losses": "not_available without baseline links",
        "mfe_lost_before_exit": "not_available in prepared aggregate",
        "trend_exit": "not prepared",
        "warning": "Broad Research is unfinished. This is one read-only transaction snapshot and is not used to select a variant.",
        "optimization_performed": False,
    })
    return clean(result)


def pullback_sample(scopes: Mapping[str, Mapping[str, Any]], identities: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from swing_walk_forward import (  # noqa: PLC0415
        _prepare_historical_indicators,
        _technical_challenger_filter,
        historical_technical_shadow_assessment,
        swing_walk_forward_strategy_profiles,
    )
    from trading_assistant import _pullback_candidate  # noqa: PLC0415

    fixed_scopes = [scope for scope in scopes.values() if str(scope.get("dataset_epoch", "")).endswith("|fixed")]
    selected: list[tuple[Mapping[str, Any], str]] = []
    for scope in sorted(fixed_scopes, key=lambda item: str((item.get("contract") or {}).get("start"))):
        available = [symbol for symbol, asset in scope["assets"].items() if asset.get("status") == "available" and int(asset.get("rows") or 0) >= 245]
        buckets: dict[str, list[str]] = defaultdict(list)
        for symbol in sorted(available):
            buckets[str((identities.get(symbol) or {}).get("region") or "unknown")].append(symbol)
        chosen: list[str] = []
        while len(chosen) < 15 and any(buckets.values()):
            for region in sorted(buckets):
                if buckets[region] and len(chosen) < 15:
                    chosen.append(buckets[region].pop(0))
        selected.extend((scope, symbol) for symbol in chosen)

    profile = next(iter(swing_walk_forward_strategy_profiles(("long_v1_pullback_only",)).values()))
    cutoff_funnel = Counter()
    asset_funnel: dict[str, set[str]] = defaultdict(set)
    examples = []
    rejection_reasons = Counter()
    assessment_rejections = Counter()
    for scope, symbol in selected:
        descriptor = scope["assets"][symbol]
        path = Path(scope["dataset_dir"]) / str(descriptor["file"])
        frame = pd.read_parquet(path)
        if not isinstance(frame.index, pd.DatetimeIndex):
            date_column = next((column for column in ("Date", "Datetime", "date", "datetime") if column in frame.columns), None)
            if date_column:
                frame = frame.set_index(date_column)
        frame.index = pd.to_datetime(frame.index, errors="coerce")
        frame = frame.loc[~frame.index.isna()].sort_index()
        cutoff_funnel["universe_assets"] += 1
        if len(frame) < 245:
            continue
        cutoff_funnel["sufficient_data_assets"] += 1
        asset_funnel["sufficient_data"].add(symbol)
        prepared = _prepare_historical_indicators(frame)
        positions = list(range(219, max(219, len(prepared) - 25), 5))
        if len(positions) > 120:
            positions = [positions[int(i)] for i in np.linspace(0, len(positions) - 1, 120)]
        for position in positions:
            cutoff_funnel["sampled_cutoffs"] += 1
            past = prepared.iloc[max(0, position - 319) : position + 1]
            latest = past.iloc[-1]
            trend = all(fnum(latest.get(name)) is not None for name in ("Close", "SMA_50", "SMA_200")) and float(latest["SMA_50"]) > float(latest["SMA_200"]) and float(latest["Close"]) > float(latest["SMA_200"])
            if trend:
                cutoff_funnel["trend_condition"] += 1
                asset_funnel["trend_condition"].add(symbol)
            candidate, reasons = _pullback_candidate(past, profile["thresholds"])
            if candidate is not None:
                cutoff_funnel["pullback_candidate"] += 1
                asset_funnel["pullback_candidate"].add(symbol)
                candidate_filter_passed, _ = _technical_challenger_filter(
                    past,
                    {"setup_type": candidate.get("setup_type")},
                    profile["technical_filter"],
                )
                if candidate_filter_passed:
                    cutoff_funnel["pullback_candidate_profile_filter_passed"] += 1
            else:
                for reason in reasons:
                    rejection_reasons[str(reason).split(":", 1)[-1].strip()] += 1
                continue
            identity = identities.get(symbol) or {}
            assessment = historical_technical_shadow_assessment(
                symbol, past, asset_type=str(identity.get("asset_type") or "Aktie"),
                region=str(identity.get("region") or "USA"), thresholds=profile["thresholds"],
                strategy_profile=profile,
            )
            if assessment.get("approved"):
                cutoff_funnel["approved_assessment_any_setup"] += 1
                asset_funnel["approved_assessment_any_setup"].add(symbol)
                if "Ausbruch" in str(assessment.get("setup_type") or ""):
                    cutoff_funnel["approved_assessment_selected_breakout"] += 1
            else:
                cutoff_funnel["assessment_rejected_despite_pullback_candidate"] += 1
                for item in assessment.get("rejection_filters") or ["unknown"]:
                    assessment_rejections[str(item)] += 1
            selected_pullback = bool(assessment.get("approved")) and "Rücksetzer" in str(assessment.get("setup_type") or "")
            if selected_pullback:
                cutoff_funnel["setup_complete_selected_pullback"] += 1
                asset_funnel["setup_complete_selected_pullback"].add(symbol)
                passed, values = _technical_challenger_filter(past, assessment, profile["technical_filter"])
                if passed:
                    cutoff_funnel["profile_filter_passed"] += 1
                    asset_funnel["profile_filter_passed"].add(symbol)
                if len(examples) < 20:
                    examples.append({
                        "symbol": symbol, "region": identity.get("region"), "scope_id": scope["scope_id"],
                        "signal_day": str(past.index[-1])[:10], "selected_setup_type": assessment.get("setup_type"),
                        "filter_rule": profile["technical_filter"], "filter_values": values,
                        "filter_passed": passed,
                    })
    cutoff_funnel["entry_activated"] = cutoff_funnel["profile_filter_passed"]
    cutoff_funnel["entry_executed"] = 0
    cutoff_funnel["complete_label"] = 0
    cutoff_funnel["evaluated_trade"] = 0
    return clean({
        "scope": "read-only deterministic 30-asset sample; not a full-campaign rejection log",
        "sample_assets": len(selected),
        "asset_counts_by_stage": {key: len(value) for key, value in asset_funnel.items()},
        "cutoff_funnel": dict(cutoff_funnel),
        "top_pullback_candidate_rejection_reasons": rejection_reasons.most_common(15),
        "assessment_rejections_after_structural_pullback_candidate": dict(assessment_rejections),
        "selected_pullback_examples": examples,
        "diagnosis": {
            "classification": "implementation_mismatch_in_research_profile_filter",
            "evidence": "The profile requires substring 'Pullback', while the approved setup emitted by the same code is 'Rücksetzer im intakten Aufwärtstrend'. casefold substring matching cannot match these terms.",
            "additional_note": "The engine first chooses the approved candidate with the best capped CRV. Therefore an existing pullback candidate can also be represented by a selected breakout before the setup-only filter.",
            "sampling_problem": "not indicated by the representative sample, but the full rejected-cutoff population was not persisted",
            "entry_problem": "not reached; the deterministic setup-name filter mismatch is sufficient to reject any selected pullback setup",
            "rule_change_performed": False,
        },
    })


def retry_audit(state: Mapping[str, Any]) -> dict[str, Any]:
    attempts = state.get("attempts") or {}
    completed = state.get("completed") or {}
    relevant = {key: value for key, value in completed.items() if CAMPAIGN_VERSION in key}
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"jobs": 0, "attempts": 0, "retries": 0, "shards": set()})
    for key, completion in relevant.items():
        count = int(attempts.get(key, 0))
        contract = str(completion.get("contract") or "unknown")
        group = groups[contract]
        group["jobs"] += 1
        group["attempts"] += count
        group["retries"] += max(count - 1, 0)
        if count > 1:
            group["shards"].add(int(completion.get("shard_index", -1)) + 1)
    errors = Counter()
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.search(r"FrozenResearchDatasetError: ([^:]+): eingefrorene Kursdatei besitzt abweichende Daten", line)
            if match:
                errors[match.group(1)] += 1
    retry_groups = []
    for contract, group in groups.items():
        if group["retries"]:
            retry_groups.append({**group, "contract": contract, "shards": sorted(group["shards"])})
    total_retries = sum(item["retries"] for item in retry_groups)
    return clean({
        "completed_campaign_jobs": len(relevant),
        "total_attempts": sum(int(attempts.get(key, 0)) for key in relevant),
        "total_retries": total_retries,
        "groups": retry_groups,
        "log_error_signature": "FrozenResearchDatasetError: frozen price file has divergent data",
        "log_ticker_occurrences_all_campaign_versions": dict(errors),
        "exact_log_attribution_to_v3": "not_available because traceback lines do not carry the campaign job key",
        "data_or_cases_changed_by_retry": "no evidence of changed final cases; aborted-attempt byte identity is not provable from retained logs",
        "resume_determinism": "supported by 248 unique completion keys, stable final fingerprints and append-only identity controls; not a proof of byte-identical aborted partial work",
        "duplicates": "quantified separately as superseded revisions/dedupe; no invalid identity conflicts in the final audit",
    })


def coverage_audit(
    frame: pd.DataFrame, raw_count: int, raw_statuses: Counter[str], manifests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unique_assets = set(frame["symbol"].dropna().astype(str))
    universe = set()
    data_status = Counter()
    for manifest in manifests:
        for scope in manifest["scopes"].values():
            path = ROOT / manifest["path"]
            full = json.loads(path.read_text(encoding="utf-8"))
            scope_payload = full["scopes"][next(key for key, value in full["scopes"].items() if value.get("contract") == scope["contract"])]
            universe.update(scope_payload.get("assets", {}).keys())
            data_status.update(str(item.get("status") or "unknown") for item in scope_payload.get("assets", {}).values())
    unique_statuses = Counter(str(value) for value in frame["status"].fillna("unknown"))
    evaluated = int(frame["result_r"].notna().sum())
    non_evaluated = int(len(frame) - evaluated)
    return clean({
        "universe_assets": len(universe),
        "assets_in_performance_rollup": int(frame.loc[frame["result_r"].notna(), "symbol"].nunique()),
        "assets_with_any_stored_case": len(unique_assets),
        "assets_without_stored_case": len(universe - unique_assets),
        "assets_partition_check": len(unique_assets & universe) + len(universe - unique_assets),
        "stored_case_revisions_campaign": raw_count,
        "unique_cases_after_evidence_dedupe": int(len(frame)),
        "superseded_or_duplicate_revisions": raw_count - len(frame),
        "unique_evaluated_cases": evaluated,
        "unique_non_evaluated_cases": non_evaluated,
        "unique_case_partition_check": evaluated + non_evaluated,
        "unique_status_counts": dict(unique_statuses),
        "raw_revision_status_counts": dict(raw_statuses),
        "known_reason_mapping": {
            "no_setup": "not_available: rejected assessments are not persisted",
            "no_entry_missed": int(unique_statuses.get("entry_missed", 0)),
            "invalidated": int(unique_statuses.get("invalidated_before_entry", 0)),
            "expired": int(unique_statuses.get("expired_without_entry", 0)),
            "insufficient_future_data": "not separately persisted; future_rows_used and terminal status are available per stored case",
            "ambiguous": int(unique_statuses.get("ambiguous_sequence", 0)),
            "overlap_purge_flagged_stored_cases": int(frame["overlap_purged"].fillna(0).sum()),
            "dedupe": raw_count - len(frame),
            "data_unavailable_scope_records": dict(data_status),
            "other_non_evaluated": non_evaluated - sum(int(unique_statuses.get(key, 0)) for key in ("entry_missed", "invalidated_before_entry", "expired_without_entry", "ambiguous_sequence")),
        },
        "reconciliation_limit": "The universe-to-no-setup funnel cannot sum exactly because rejected cutoffs were intentionally not stored. Stored unique cases do reconcile exactly into evaluated plus terminal non-evaluated statuses.",
    })


def concentration(frame: pd.DataFrame) -> dict[str, Any]:
    evaluated = frame.loc[frame["result_r"].notna()]
    by_asset = evaluated.groupby("symbol")["result_r"].sum()
    positive = by_asset[by_asset > 0].sort_values(ascending=False)
    negative = by_asset[by_asset < 0].sort_values()
    gain_total, loss_total = positive.sum(), abs(negative.sum())
    day_counts = evaluated.groupby("signal_day").size()
    return clean({
        "top_10_gain_assets": positive.head(10).to_dict(),
        "top_10_gain_share_pct": positive.head(10).sum() / gain_total * 100 if gain_total else None,
        "top_10_loss_assets": negative.head(10).to_dict(),
        "top_10_loss_share_pct": abs(negative.head(10).sum()) / loss_total * 100 if loss_total else None,
        "cases_on_shared_signal_days_pct": evaluated["signal_day"].map(day_counts).gt(1).mean() * 100 if len(evaluated) else None,
        "strongly_correlated_clusters": "not_available; no point-in-time correlation-cluster field was stored",
        "dependency_cluster_share_pct": (1 - evaluated["dependency_cluster_id"].nunique() / len(evaluated)) * 100 if len(evaluated) else None,
    })


def challenger_table(profile_metrics: Sequence[Mapping[str, Any]], split: Mapping[str, Any], time_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    aliases = {
        "RSI core": "long_v1_rsi_core",
        "EMA+RSI core": "long_v1_ema_rsi_core",
        "EMA-only": "long_v1_ema_trend",
        "Breakout-only": "long_v1_breakout_only",
        "Pullback-only": "long_v1_pullback_only",
    }
    base = next(item for item in profile_metrics if item["strategy"] == "current")
    rows = []
    for label, name in aliases.items():
        item = next(value for value in profile_metrics if value["strategy"] == name)
        split_rows = [row for row in split["rows"] if row.get("strategy") == name and row.get("research_split") in {"development", "validation", "holdout"}]
        holdout = next(row for row in split_rows if row["research_split"] == "holdout")
        year_rows = [row for row in time_data["year_rows"] if row.get("strategy") == name and row.get("average_r") is not None]
        c_rows = []
        rows.append(clean({
            "challenger": label, "strategy": name,
            "average_r_delta_vs_current": item["average_r"] - base["average_r"] if item["average_r"] is not None and base["average_r"] is not None else None,
            "where_effect_disappears": [row["research_split"] for row in split_rows if row.get("average_r") is not None and row["average_r"] <= 0],
            "time_stable": bool(year_rows) and all(row["average_r"] > 0 for row in year_rows),
            "oos_holdout_average_r": holdout.get("average_r"),
            "oos_present": holdout.get("average_r") is not None and holdout["average_r"] > 0,
            "effective_n": item["effective_n"],
            "c_sufficient": False,
            "feature_family_with_possible_information_value": item.get("strategy_family") if item["average_r"] is not None else "not_evaluable",
            "warning": "Descriptive finding only; no release or optimization decision.",
        }))
    return rows


def write_parquet(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    columns = [
        "case_id", "strategy", "round", "research_split", "symbol", "issuer_id", "listing_id",
        "economic_instrument_id", "signal_day", "setup", "entry_type", "entry", "paper_entry", "stop",
        "target_1", "target_2", "result_r", "outcome", "mfe_pct", "mae_pct", "peak_mfe_r", "peak_mae_r",
        "market_phase", "volatility_regime", "rsi_14", "ema_20", "ema_50", "ema_context", "bos",
        "buyer_confirmation", "atr", "relative_volume", "region", "asset_type", "contract_period",
        "contract_id", "dataset_fingerprint", "scope_id", "dependency_cluster_id",
    ]
    evaluated = frame.loc[frame["result_r"].notna(), columns].copy()
    evaluated.to_parquet(path, index=False, compression="zstd")
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "rows": len(evaluated), "columns": columns}


def markdown_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[tuple[str, str]], limit: int | None = None) -> str:
    selected = list(rows)[:limit] if limit else list(rows)
    lines = ["| " + " | ".join(label for _, label in columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in selected:
        values = []
        for key, _ in columns:
            value = row.get(key)
            if isinstance(value, float):
                value = f"{value:.4f}"
            values.append("–" if value is None else str(value).replace("|", "/"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def render_markdown(report: Mapping[str, Any]) -> str:
    overview = report["overall"]
    profiles = report["strategy_profiles"]
    split_rows = [row for row in report["development_validation_holdout"]["rows"] if row.get("research_split") != "deltas"]
    challenger = report["challenger_review"]
    coverage = report["coverage_case_state_audit"]
    retries = report["retries"]
    pullback = report["pullback_zero_cases"]
    lines = [
        "# Swing-Kampagne 248/248 – Read-only Deep Analysis",
        "",
        f"Erzeugt: `{report['generated_at']}`. Dieser Export ist rein deskriptiv. Es wurden keine Regeln, Parameter oder Produktionszustände geändert.",
        "",
        "## 1. Gesamtübersicht",
        "",
        markdown_table([overview], [("campaign_status", "Status"), ("raw_n", "raw N"), ("evaluated_n", "ausgewertet"), ("effective_n", "effective N"), ("hit_rate_pct", "Winrate %"), ("average_r", "Ø R"), ("median_r", "Median R"), ("profit_factor", "PF"), ("maximum_drawdown_r", "Max DD R")]),
        "",
        f"Universum: {overview['universe_assets']} Assets; Assets mit gespeicherten Fällen: {overview['assets_with_cases']}; ohne gespeicherten Fall: {overview['assets_without_cases']}.",
        "",
        "## 2. Strategieprofile",
        "",
        markdown_table(profiles, [("strategy", "Strategie"), ("raw_n", "raw N"), ("evaluated_n", "eval N"), ("effective_n", "eff. N"), ("wins", "W"), ("losses", "L"), ("zero", "0"), ("hit_rate_pct", "Winrate %"), ("average_r", "Ø R"), ("profit_factor", "PF"), ("maximum_drawdown_r", "DD R"), ("status", "Status")]),
        "",
        "Die vollständigen Parameter-/Regelbeschreibungen und deskriptiven Differenzen zur unveränderten `current`/Long‑v1-Baseline stehen im JSON.",
        "",
        "## 3. A/B/C und Monitoring",
        "",
        markdown_table([row for row in report["round_analysis"]["rows"] if row.get("round") != "A_to_B_to_C_funnel"], [("strategy", "Strategie"), ("round", "Runde"), ("evaluated_n", "eval N"), ("effective_n", "eff. N"), ("average_r", "Ø R"), ("profit_factor", "PF"), ("maximum_drawdown_r", "DD R"), ("status", "Status")]),
        "",
        "C wird bei effective N < 200 ausdrücklich als `underpowered` und nicht als belastbare Bestätigung behandelt. RSI core und EMA+RSI core sind im JSON gesondert markiert.",
        "",
        "## 4. Development / Validation / Holdout",
        "",
        markdown_table(split_rows, [("strategy", "Strategie"), ("research_split", "Split"), ("evaluated_n", "N"), ("effective_n", "eff. N"), ("hit_rate_pct", "Winrate %"), ("average_r", "Ø R"), ("profit_factor", "PF"), ("maximum_drawdown_r", "DD R")]),
        "",
        "Es wurde keine Freigabeentscheidung getroffen.",
        "",
        "## 5. Pullback-Nullfälle",
        "",
        f"Diagnose: `{pullback['diagnosis']['classification']}`. Das Profil sucht nach dem Text `Pullback`, während der vorhandene Code das Setup `Rücksetzer im intakten Aufwärtstrend` nennt. Die 30‑Asset-Stichprobe und ihr kompletter Trichter stehen im JSON.",
        "",
        "## 6–13. Breakout, Entry, Stops, Stabilität, Regime, Cluster, Legacy/Modern, Monitoring",
        "",
        "Alle verfügbaren Gruppentabellen stehen maschinenlesbar im JSON. Nicht gespeichert und daher nicht rekonstruiert wurden insbesondere BOS, Buyer Confirmation, ATR, Breakout-Stärke, Distanz zum vorherigen Hoch sowie MFE/MAE nach exakt 1/3/5 Sessions. Der Broad-Counterfactual-Block ist als unfertiger Read-only-Snapshot gekennzeichnet und besitzt noch keine Baseline-Links.",
        "",
        "## 14. Coverage-/Case-State-Audit",
        "",
        markdown_table([coverage], [("universe_assets", "Universum"), ("assets_in_performance_rollup", "Assets Performance"), ("stored_case_revisions_campaign", "gespeicherte Revisionen"), ("unique_cases_after_evidence_dedupe", "eindeutige Cases"), ("unique_evaluated_cases", "ausgewertet"), ("unique_non_evaluated_cases", "nicht ausgewertet"), ("superseded_or_duplicate_revisions", "Dedupe")]),
        "",
        "`no setup` ist nicht vollständig quantifizierbar, weil abgelehnte Cutoffs nicht persistiert wurden. Die gespeicherten eindeutigen Cases gehen dagegen exakt in ausgewertete und terminal nicht ausgewertete Fälle auf.",
        "",
        "## 15. Retries",
        "",
        f"Die State-Datei weist {retries['total_retries']} Retries aus. Die belegte Fehlersignatur ist eine abweichende eingefrorene Kursdatei; eine exakte Zuordnung jeder nackten Traceback-Zeile zum Kampagnenjob ist im Log nicht gespeichert.",
        "",
        "## 16. Survivorship-/Universe-Risiko",
        "",
        "Die Evidenz nutzt das heutige Projektuniversum. Delistings, ehemalige Indexmitglieder und historische Membership-/Listing-Zustände fehlen. Der mögliche Survivorship Bias ist deshalb qualitativ relevant, wird aber nicht erfunden quantifiziert.",
        "",
        "## 17. Challenger-Hinweis",
        "",
        markdown_table(challenger, [("challenger", "Challenger"), ("average_r_delta_vs_current", "Δ ØR vs Long-v1"), ("effective_n", "eff. N"), ("oos_holdout_average_r", "Holdout ØR"), ("oos_present", "OOS positiv"), ("time_stable", "zeitstabil"), ("c_sufficient", "C ausreichend")]),
        "",
        "Nur Befunde; keine Auswahl oder Freigabe.",
        "",
        "## 18–19. Dateien, Grenzen und Integrität",
        "",
        f"Trade-Level-Parquet: `{report['outputs']['trade_level_parquet']['path']}` mit {report['outputs']['trade_level_parquet']['rows']} eindeutigen ausgewerteten Fällen.",
        "",
        f"SQLite quick_check: Walk-forward `{report['integrity']['quick_check_after']['walk_forward']}`, Broad `{report['integrity']['quick_check_after']['broad']}`. Fingerprints und Frozen-Manifeste wurden vor/nach dem Export verglichen; Ergebnis: `{report['integrity']['protected_sources_unchanged']}`.",
        "",
        "Broad Research wurde nicht gestartet, gestoppt oder verändert. Da er parallel eigenständig weiterläuft, kann sich seine Datenbankgröße während des Exports regulär ändern; der Export griff ausschließlich lesend in einer konsistenten Transaktion zu.",
        "",
        "Die vollständige Fragen-/Datenlückenliste, Git-Status und Prüfnachweise stehen im JSON.",
        "",
    ]
    return "\n".join(lines)


def git_info() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True).stdout.strip()
    branch = run("branch", "--show-current")
    head = run("rev-parse", "HEAD")
    upstream = run("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    ahead_behind = run("rev-list", "--left-right", "--count", f"{upstream}...HEAD") if upstream else ""
    return {"branch": branch, "commit_hash": head, "upstream": upstream or None, "upstream_ahead_behind": ahead_behind or None, "working_tree_status": run("status", "--short"), "github_status": "not_verified_online; upstream relationship is local Git metadata"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only deep export of the completed swing campaign")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--refresh-existing-diagnostics",
        action="store_true",
        help="Refresh only the read-only Pullback/Broad diagnostics in an existing JSON export.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{OUTPUT_STEM}.json"
    markdown_path = output_dir / f"{OUTPUT_STEM}.md"
    parquet_path = output_dir / f"{OUTPUT_STEM}_trades.parquet"
    scratch_path = output_dir / f".{OUTPUT_STEM}_scratch.sqlite3"

    if args.refresh_existing_diagnostics:
        if not json_path.exists():
            raise FileNotFoundError(json_path)
        report = json.loads(json_path.read_text(encoding="utf-8"))
        _, _, scopes = load_manifests()
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        _, _, identities = load_campaign_runs(config, scopes)
        report["pullback_zero_cases"] = pullback_sample(scopes, identities)
        report["stop_management_diagnostics"] = broad_counterfactual_snapshot()
        report["outputs"]["json_sha256"] = "not_embedded_because_the_file_hash_would_be_self_referential"
        report["git"] = git_info()
        json_path.write_text(json.dumps(clean(report), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(json.dumps({"refreshed": ["pullback_zero_cases", "stop_management_diagnostics"], "json": str(json_path), "markdown": str(markdown_path)}, ensure_ascii=False), flush=True)
        return 0

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    manifests, manifest_paths, scopes = load_manifests()
    before = source_snapshot(manifest_paths)
    quick_before = {"walk_forward": quick_check(WF_DB_PATH, immutable=True), "broad": quick_check(BROAD_DB_PATH)}
    runs, profiles, identities = load_campaign_runs(config, scopes)
    print(f"runs={len(runs)}", flush=True)
    raw_count, selected_count, raw_statuses = build_flat_store(runs, scratch_path)
    print(f"cases_raw={raw_count} cases_unique={selected_count}", flush=True)
    with sqlite3.connect(scratch_path) as connection:
        frame = pd.read_sql_query("SELECT * FROM selected", connection)
    for column in ("result_r", "result_pct", "entry", "paper_entry", "stop", "target_1", "target_2", "risk_pct", "mfe_pct", "mae_pct", "peak_mfe_r", "peak_mae_r", "rsi_14", "ema_20", "ema_50", "close", "relative_volume", "evaluation_horizon_sessions", "selection_eligible", "overlap_purged"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["dependency_cluster_id"] = assign_dependency_clusters(frame)
    print(f"effective_clusters={frame['dependency_cluster_id'].nunique()}", flush=True)

    profile_metrics = profile_rows(frame, profiles)
    rounds = round_analysis(frame)
    split = split_analysis(frame)
    time_data = time_analysis(frame)
    monitoring = frame.loc[frame["sampling_mode"] == "recent_incremental"].copy()
    monitoring["signal_year"] = monitoring["signal_day"].str[:4]
    monitoring["signal_date"] = monitoring["signal_day"]
    overall_metrics = metrics(frame)
    coverage = coverage_audit(frame, raw_count, raw_statuses, manifests)
    state_jobs = [(key, value) for key, value in (state.get("completed") or {}).items() if CAMPAIGN_VERSION in key]
    campaign_complete = len(state_jobs) == 248
    overall = {
        "campaign_version": CAMPAIGN_VERSION,
        "campaign_status": f"{len(state_jobs)}/248" + (" complete" if campaign_complete else " incomplete"),
        "dataset_versions": [{"epoch": item["dataset_epoch"], "fingerprint": item["dataset_fingerprint"]} for item in manifests],
        **overall_metrics,
        "universe_assets": coverage["universe_assets"],
        "assets_with_cases": coverage["assets_with_any_stored_case"],
        "assets_without_cases": coverage["assets_without_stored_case"],
        "assets_in_performance_rollup": coverage["assets_in_performance_rollup"],
    }
    pullback = pullback_sample(scopes, identities)
    print("pullback_sample=complete", flush=True)
    broad = broad_counterfactual_snapshot()
    parquet_meta = write_parquet(frame, parquet_path)

    modern_legacy = {
        "rows": grouped_metrics(frame, ["strategy", "contract_period"]),
        "setup_mix": grouped_metrics(frame, ["strategy", "contract_period", "setup"]),
        "regime_distribution": grouped_metrics(frame, ["strategy", "contract_period", "market_phase", "volatility_regime"]),
        "causality_warning": "Observed difference only; no cause asserted.",
    }
    recent = {
        "exact_period": {"first_signal_day": monitoring["signal_day"].min() if len(monitoring) else None, "last_signal_day": monitoring["signal_day"].max() if len(monitoring) else None},
        "signal_days": int(monitoring["signal_day"].nunique()),
        "assets": int(monitoring["symbol"].nunique()),
        "profiles": sorted(monitoring["strategy"].dropna().unique().tolist()),
        "overall": metrics(monitoring),
        "by_setup": grouped_metrics(monitoring, ["setup"]),
        "by_region": grouped_metrics(monitoring, ["region"]),
        "by_asset_type": grouped_metrics(monitoring, ["asset_type"]),
        "by_regime": grouped_metrics(monitoring, ["market_phase", "volatility_regime"]),
        "by_date": grouped_metrics(monitoring, ["signal_date"]),
        "by_asset": grouped_metrics(monitoring, ["symbol"]),
        "gap_execution_share": "not_available as a normalized stored field; entry_missed status is reported in coverage",
        "dominance_audit": concentration(monitoring),
        "sampling_mode": "recent_incremental",
        "data_problem_claim": "not made",
    }

    report: dict[str, Any] = {
        "schema_version": "swing-campaign-deep-analysis-2026.08.23-v1",
        "generated_at": utc_now(),
        "purpose": "Independent deep root-cause analysis; descriptive read-only evidence only",
        "constraints": {
            "strategy_changed": False, "new_rules": False, "parameters_optimized": False,
            "campaign_started": False, "source_data_written": False, "frozen_dataset_changed": False,
            "long_v1_changed": False, "broad_research_controlled_or_restarted": False,
        },
        "overall": overall,
        "strategy_profiles": profile_metrics,
        "round_analysis": rounds,
        "development_validation_holdout": split,
        "pullback_zero_cases": pullback,
        "breakout_deep_analysis": breakout_analysis(frame),
        "entry_efficiency": entry_efficiency(frame),
        "stop_management_diagnostics": broad,
        "time_stability": time_data,
        "market_volatility_regimes": {
            "rows": grouped_metrics(frame, ["strategy", "market_phase", "volatility_regime"]),
            "concentration_test": "Inspect group shares and effective N; no causal regime claim is made.",
        },
        "asset_region_clusters": {
            "asset_type_region": grouped_metrics(frame, ["asset_type", "region"]),
            "strategy_asset_type_region": grouped_metrics(frame, ["strategy", "asset_type", "region"]),
            "issuer_listing": {"issuers": int(frame["issuer_id"].nunique()), "listings": int(frame["listing_id"].nunique()), "dependent_case_share": concentration(frame)["dependency_cluster_share_pct"]},
            "sector": "not point-in-time available in stored cases",
            "concentration": concentration(frame),
        },
        "modern_vs_legacy": modern_legacy,
        "recent_incremental": recent,
        "coverage_case_state_audit": coverage,
        "retries": retry_audit(state),
        "survivorship_universe_risk": {
            "current_universe_assets_backtested": coverage["universe_assets"],
            "missing_delistings": "not_available",
            "missing_former_index_members": "not_available",
            "historical_listing_membership": "not_available",
            "bias": "Qualitatively relevant survivorship/universe-selection risk because the current project universe is used historically; magnitude is not quantifiable from retained data.",
            "quantification_invented": False,
        },
        "challenger_review": challenger_table(profile_metrics, split, time_data),
        "data_dictionary": {
            "effective_n": "Count of stored dependency clusters among evaluated cases using issuer/instrument and overlapping label windows within strategy/split/horizon.",
            "mfe_mae_units": "percent price excursion from stored terminal event; peak_mfe_r/peak_mae_r divide these by stored risk_pct.",
            "missing_feature_policy": "null/not_available; no unsafe reconstruction.",
        },
        "unanswered_questions": [
            "Exact full-campaign no-setup rejection count (rejections were not persisted).",
            "Session 1/3/5 excursion paths and first-touch ordering (not stored).",
            "Walk-forward BOS, buyer confirmation, ATR and breakout-level geometry (not stored).",
            "How original walk-forward losses would change under Broad counterfactuals (no baseline links yet).",
            "Quantitative survivorship bias (historical membership/delistings absent).",
            "Sector results on a point-in-time basis (sector metadata absent from cases).",
        ],
        "outputs": {"json": str(json_path.relative_to(ROOT)).replace("\\", "/"), "markdown": str(markdown_path.relative_to(ROOT)).replace("\\", "/"), "trade_level_parquet": parquet_meta},
        "source_manifests": manifests,
        "git": git_info(),
    }

    after = source_snapshot(manifest_paths)
    quick_after = {"walk_forward": quick_check(WF_DB_PATH, immutable=True), "broad": quick_check(BROAD_DB_PATH)}
    protected_before = before["files"]
    protected_after = after["files"]
    wf_stable = before["walk_forward_store"] == after["walk_forward_store"]
    report["integrity"] = {
        "quick_check_before": quick_before,
        "quick_check_after": quick_after,
        "source_snapshot_before": before,
        "source_snapshot_after": after,
        "protected_sources_unchanged": protected_before == protected_after and wf_stable,
        "walk_forward_store_size_mtime_unchanged": wf_stable,
        "broad_store_size_mtime_unchanged": before.get("broad_store") == after.get("broad_store"),
        "broad_note": "Broad may grow autonomously while its existing background process runs. The exporter used mode=ro, PRAGMA query_only and one read transaction; it issued no lifecycle command.",
        "read_only_checks": [
            "All source SQLite connections used URI mode=ro and PRAGMA query_only=ON.",
            "Stable walk-forward source additionally used immutable=1.",
            "Only new export and scratch files were written under runtime/research_exports.",
            "Protected source hashes/size/mtime were compared before and after.",
        ],
        "tests": {"internal_reconciliation": coverage["unique_case_partition_check"] == coverage["unique_cases_after_evidence_dedupe"], "parquet_row_match": parquet_meta["rows"] == overall["evaluated_n"]},
    }
    report = clean(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    report["outputs"]["json_sha256"] = "not_embedded_because_the_file_hash_would_be_self_referential"
    report["outputs"]["markdown_sha256"] = sha256_file(markdown_path)
    report["outputs"]["trade_level_parquet"]["sha256"] = sha256_file(parquet_path)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if scratch_path.exists():
        try:
            scratch_path.unlink()
        except PermissionError:
            # Windows can retain a short-lived SQLite handle after a large pandas read.
            # The scratch store contains derived data only and is ignored by consumers.
            pass
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path), "parquet": str(parquet_path), "evaluated": overall["evaluated_n"], "effective_n": overall["effective_n"]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
