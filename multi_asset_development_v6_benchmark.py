from __future__ import annotations

"""Controlled worker benchmark for the Development-v6 compute path."""

import json
import os
import platform
import sqlite3
import tempfile
import time
import uuid
from collections import Counter
from contextlib import closing
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from multi_asset_development_v6_execution import (
    compute_v6_asset_batch,
    result_scientific_digest,
)
from multi_asset_development_v6_inputs import (
    MultiAssetV6InputError,
    build_v6_implementation_provenance,
    verify_v6_current_sources,
)
from multi_asset_development_v6_store import (
    initialize_v6_run,
    persist_and_complete_work_unit,
    skip_work_unit,
)
from multi_asset_discovery_v1 import canonical_json, fingerprint
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_walk_forward_campaign import (
    campaign_active_production_jobs,
    load_campaign_config,
)


PROJECT_ROOT = Path(__file__).resolve().parent
BENCHMARK_VERSION = "multi-asset-development-v6-worker-benchmark-2026.09.05-v1"
DEFAULT_BENCHMARK_ARTIFACT = Path(
    "runtime/research_exports/multi_asset_development_v6_worker_benchmark_2026-09-05-v1-r6.json"
)
DEFAULT_BENCHMARK_PROCESS_LOCK = (
    PROJECT_ROOT / "runtime" / "multi_asset_development_v6_worker_benchmark.lock"
)
DEFAULT_GLOBAL_RESEARCH_LOCK = (
    PROJECT_ROOT / "runtime" / "swing_walk_forward_research.lock"
)
DEFAULT_FX_OBSERVER_LOCK = PROJECT_ROOT / "runtime" / "fx_forward_pit.collector.lock"
DEFAULT_PRODUCTION_PROTECTION_CONFIG = (
    PROJECT_ROOT / "config" / "swing_walk_forward_campaign.json"
)
DESCRIPTIVE_PLAN_VERSION = (
    "multi-asset-development-v6-descriptive-plan-2026.09.05-v1"
)
FIXED_SYMBOLS = (
    ("EQUITIES", "AAPL"),
    ("EQUITIES", "MSFT"),
    ("EQUITIES", "CNL"),
    ("EQUITIES", "SW"),
    ("ETF", "SPY"),
    ("ETF", "QQQ"),
    ("CRYPTO", "BTC-USD"),
    ("CRYPTO", "AAVE-USD"),
    ("CRYPTO", "ICP-USD"),
    ("CRYPTO", "SHIB-USD"),
    ("CRYPTO", "AVAX-USD"),
    ("CRYPTO", "APT21794-USD"),
    ("FX", "EUR/USD"),
    ("FX", "GBP/USD"),
    ("FX", "USD/JPY"),
)
FIXED_PERIODS = (
    ("2016-10-01", "2016-12-31"),
    ("2018-10-01", "2018-12-31"),
    ("2020-10-01", "2020-12-31"),
    ("2021-10-01", "2021-12-31"),
)
# This probe is selected only from the immutable input-continuity topology, not
# from returns or outcomes.  In the fixed benchmark sample, SW is the asset with
# an at-least-220-observation segment that ends at a peer-observed missing
# session in Q1 2018.  The targeted quarter therefore exercises the existing
# no-cross-boundary censoring contract without expanding every asset/period
# combination.  Peer observation is technical evidence, not an assertion that
# the peer consensus is an official exchange calendar.
FIXED_TECHNICAL_PROBES = (
    {
        "asset_class": "EQUITIES",
        "symbol": "SW",
        "period_start": "2018-01-01",
        "period_end": "2018-03-31",
        "purpose": "INPUT_GAP_CENSORING",
        "selection_basis": "immutable_input_continuity_topology",
        "selection_used_outcomes": False,
        "calendar_semantics": "peer_observed_sessions_not_official_calendar",
        "continuity_segment": {
            "start": "2016-11-14",
            "end": "2018-01-22",
            "active_observations": 298,
            "minimum_required_observations": 220,
        },
        "input_gap_boundary": {
            "after": "2018-01-22",
            "next_valid_observation": "2018-01-26",
            "archived_invalid_sessions": [
                "2018-01-23",
                "2018-01-24",
                "2018-01-25",
            ],
            "peer_observed_missing_sessions": [
                "2018-01-23",
                "2018-01-24",
                "2018-01-25",
            ],
            "peer_group": "MIC:US-CONSOLIDATED",
        },
        "expected_technical_coverage": {
            "eligible_probe_signals": 13,
            "required_forward_horizon_bars": 252,
            "outcome_status": "CENSORED_AT_INPUT_GAP",
        },
    },
)
REQUIRED_TECHNICAL_COVERAGE_GATES = (
    "all_four_asset_classes_exercised_and_classified",
    "known_gap_asset_exercised",
    "input_gap_censoring_exercised",
    "structural_r_na_exercised",
    "stage_boundary_censoring_exercised",
    "no_data_skip_exercised",
    "gap_safe_history_skip_exercised",
    "no_unexpected_asset_skip",
    "multiple_quarters_exercised",
    "different_history_lengths_exercised",
)
STRUCTURAL_R_NA_REASONS = (
    "MISSING_ATR",
    "MISSING_INVALIDATION",
    "NON_POSITIVE_STRUCTURAL_RISK",
)


class DevelopmentV6BenchmarkError(RuntimeError):
    pass


def _aware_timestamp(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DevelopmentV6BenchmarkError(f"Invalid {label} timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DevelopmentV6BenchmarkError(f"{label} timestamp must include a timezone.")
    return parsed


def _descriptive_plan_reference(
    plan: Mapping[str, object],
    *,
    benchmark_created_at: str,
    expected_contract_basis_fingerprint: str,
) -> dict[str, str]:
    payload = dict(plan)
    stated = str(payload.pop("artifact_fingerprint", ""))
    if (
        len(stated) != 64
        or fingerprint(payload) != stated
        or payload.get("version") != DESCRIPTIVE_PLAN_VERSION
        or payload.get("status") != "FROZEN"
        or payload.get("inferential_claims_allowed") is not False
        or payload.get("selection_or_optimization_allowed") is not False
    ):
        raise DevelopmentV6BenchmarkError(
            "Descriptive plan must be self-valid, frozen and non-inferential "
            "before the benchmark."
        )
    if (
        payload.get("contract_basis_fingerprint")
        != expected_contract_basis_fingerprint
    ):
        raise DevelopmentV6BenchmarkError(
            "Descriptive plan contract basis does not match the benchmark contract."
        )
    plan_created_at = str(payload.get("created_at") or "")
    if _aware_timestamp(plan_created_at, label="descriptive-plan.created_at") > (
        _aware_timestamp(benchmark_created_at, label="benchmark.created_at")
    ):
        raise DevelopmentV6BenchmarkError(
            "Descriptive plan was frozen after the benchmark timestamp."
        )
    return {
        "artifact_fingerprint": stated,
        "created_at": plan_created_at,
    }


def _validated_benchmark_compute_paths(
    compute_paths: Mapping[str, Path] | None,
    *,
    input_precheck_fingerprint: str,
    contract_input_precheck_fingerprint: str,
    contract_input_precheck_path: str,
    contract_input_precheck_version: str,
    contract_development_code_fingerprint: str,
    project_root: Path,
) -> tuple[dict[str, Path], dict[str, object]]:
    raw_paths = dict(compute_paths or {})
    if "input_precheck_artifact" not in raw_paths:
        raise DevelopmentV6BenchmarkError(
            "Benchmark compute_paths must explicitly bind input_precheck_artifact."
        )
    root = Path(project_root).resolve()
    normalized = {
        str(name): (
            Path(value).resolve()
            if Path(value).is_absolute()
            else (root / Path(value)).resolve()
        )
        for name, value in raw_paths.items()
    }
    precheck_path = normalized["input_precheck_artifact"]
    expected_relative = Path(str(contract_input_precheck_path))
    if expected_relative.is_absolute():
        raise DevelopmentV6BenchmarkError(
            "Benchmark contract input precheck path must be project-relative."
        )
    expected_path = (root / expected_relative).resolve()
    try:
        expected_path.relative_to(root)
    except ValueError as exc:
        raise DevelopmentV6BenchmarkError(
            "Benchmark contract input precheck path leaves the project root."
        ) from exc
    if precheck_path != expected_path:
        raise DevelopmentV6BenchmarkError(
            "Benchmark worker input precheck path does not match the benchmark "
            "contract."
        )
    try:
        relative_path = precheck_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise DevelopmentV6BenchmarkError(
            "Benchmark input precheck must remain inside the project root."
        ) from exc
    try:
        precheck = json.loads(precheck_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentV6BenchmarkError(
            "Benchmark input precheck is not readable JSON."
        ) from exc
    if not isinstance(precheck, dict):
        raise DevelopmentV6BenchmarkError(
            "Benchmark input precheck must be a JSON object."
        )
    basis = dict(precheck)
    stated = str(basis.pop("artifact_fingerprint", ""))
    if (
        len(stated) != 64
        or fingerprint(basis) != stated
        or stated != str(input_precheck_fingerprint)
        or precheck.get("status") != "PASS"
    ):
        raise DevelopmentV6BenchmarkError(
            "Benchmark worker input precheck does not match the declared PASS "
            "artifact fingerprint."
        )
    if precheck.get("version") != str(contract_input_precheck_version):
        raise DevelopmentV6BenchmarkError(
            "Benchmark worker input precheck schema version does not match the "
            "benchmark contract."
        )
    if stated != str(contract_input_precheck_fingerprint):
        raise DevelopmentV6BenchmarkError(
            "Benchmark worker input precheck does not match the benchmark "
            "contract reference fingerprint."
        )
    try:
        source_audit = verify_v6_current_sources(
            input_precheck_artifact=precheck_path,
            input_precheck=precheck,
            project_root=root,
        )
        implementation = build_v6_implementation_provenance(project_root=root)
    except (MultiAssetV6InputError, OSError, TypeError, ValueError) as exc:
        raise DevelopmentV6BenchmarkError(
            "Benchmark worker input precheck current-source verification failed."
        ) from exc
    stored_implementation_hashes = dict(precheck.get("implementation_sha256") or {})
    stored_implementation_fingerprint = str(
        dict(precheck.get("contract_inputs") or {}).get(
            "implementation_fingerprint"
        )
        or ""
    )
    current_implementation_hashes = dict(
        implementation.get("implementation_sha256") or {}
    )
    current_implementation_fingerprint = str(
        implementation.get("implementation_fingerprint") or ""
    )
    if (
        source_audit.get("status") != "PASS"
        or implementation.get("complete") is not True
        or not stored_implementation_hashes
        or current_implementation_hashes != stored_implementation_hashes
        or current_implementation_fingerprint != stored_implementation_fingerprint
        or current_implementation_fingerprint
        != str(contract_development_code_fingerprint)
    ):
        raise DevelopmentV6BenchmarkError(
            "Benchmark worker input precheck implementation provenance does not "
            "match current code and the benchmark contract."
        )
    return normalized, {
        "path": relative_path,
        "artifact_fingerprint": stated,
        "version": str(precheck["version"]),
        "current_sources_verified_before_compute": True,
        "current_source_set_fingerprint": str(
            source_audit.get("source_set_fingerprint") or ""
        ),
        "implementation_fingerprint": current_implementation_fingerprint,
    }


def _probe_lock_clear(path: Path) -> tuple[bool, str]:
    lock = SwingRunLock(Path(path))
    try:
        lock.acquire()
    except SwingRunAlreadyActiveError:
        return False, f"ACTIVE_LOCK:{Path(path).name}"
    else:
        lock.release()
        return True, "CLEAR"


def benchmark_dispatch_readiness(
    *,
    production_protection_config: Path = DEFAULT_PRODUCTION_PROTECTION_CONFIG,
    fx_observer_lock_path: Path = DEFAULT_FX_OBSERVER_LOCK,
    project_root: Path = PROJECT_ROOT,
) -> tuple[bool, str, dict[str, object]]:
    """Fail closed immediately before each benchmark compute configuration."""

    active = campaign_active_production_jobs(
        load_campaign_config(Path(production_protection_config)),
        project_root=Path(project_root),
    )
    detail: dict[str, object] = {"active_production_jobs": list(active)}
    if active:
        return False, "ACTIVE_PRODUCTION_JOB:" + ",".join(active), detail
    fx_clear, fx_reason = _probe_lock_clear(Path(fx_observer_lock_path))
    detail["fx_observer_lock"] = fx_reason
    if not fx_clear:
        return False, fx_reason, detail
    return True, "CLEAR", detail


def _write_immutable(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_json(existing) != canonical_json(payload):
            raise DevelopmentV6BenchmarkError(f"Immutable benchmark differs: {path}")
        return
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if canonical_json(existing) != canonical_json(payload):
                raise DevelopmentV6BenchmarkError(
                    f"Parallel immutable benchmark differs: {path}"
                )
    finally:
        temporary.unlink(missing_ok=True)


def _memory_snapshot() -> dict[str, int]:
    if os.name != "nt":
        try:
            import resource

            peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        except (ImportError, AttributeError):  # pragma: no cover
            peak = 0
        return {"working_set_bytes": peak, "peak_working_set_bytes": peak}
    import ctypes
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    # ctypes defaults an undeclared function result to a 32-bit C ``int``.
    # On 64-bit Windows that truncates the -1 pseudo handle returned by
    # GetCurrentProcess to 0x00000000ffffffff, so GetProcessMemoryInfo fails
    # with ERROR_INVALID_HANDLE and silently produced zero-byte evidence.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info = psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    get_process_memory_info.restype = wintypes.BOOL

    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if not get_process_memory_info(
        get_current_process(), ctypes.byref(counters), counters.cb
    ):
        error_code = ctypes.get_last_error()
        raise DevelopmentV6BenchmarkError(
            "Windows process-memory measurement failed "
            f"with error code {error_code}."
        )
    if counters.WorkingSetSize <= 0 or counters.PeakWorkingSetSize <= 0:
        raise DevelopmentV6BenchmarkError(
            "Windows process-memory measurement returned non-positive evidence."
        )
    return {
        "working_set_bytes": int(counters.WorkingSetSize),
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
    }


def system_resources() -> dict[str, object]:
    total = 0
    available = 0
    if os.name == "nt":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        state = MEMORYSTATUSEX()
        state.dwLength = ctypes.sizeof(state)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            total = int(state.ullTotalPhys)
            available = int(state.ullAvailPhys)
    return {
        "logical_cpu_count": int(os.cpu_count() or 1),
        "total_physical_memory_bytes": total,
        "available_physical_memory_bytes_at_start": available,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def eligible_worker_counts(resources: Mapping[str, object]) -> tuple[int, ...]:
    counts = [1, 2, 4]
    if int(resources.get("logical_cpu_count") or 0) >= 8 and int(
        resources.get("total_physical_memory_bytes") or 0
    ) >= 12 * 1024**3:
        counts.append(6)
    return tuple(counts)


def fixed_benchmark_sample(universe: Mapping[str, object]) -> dict[str, object]:
    lookup = {
        (str(item["asset_class"]), str(item["symbol"])): dict(item)
        for item in universe.get("assets") or []
    }
    missing = [item for item in FIXED_SYMBOLS if item not in lookup]
    if missing:
        raise DevelopmentV6BenchmarkError(f"Fixed benchmark assets missing: {missing}")
    invalid_probes = [
        probe
        for probe in FIXED_TECHNICAL_PROBES
        if (
            str(probe["asset_class"]),
            str(probe["symbol"]),
        )
        not in FIXED_SYMBOLS
        or (str(probe["asset_class"]), str(probe["symbol"])) not in lookup
    ]
    if invalid_probes:
        raise DevelopmentV6BenchmarkError(
            f"Fixed technical-probe assets missing: {invalid_probes}"
        )
    assets = [lookup[item] for item in FIXED_SYMBOLS]
    units_by_asset: dict[str, list[dict[str, object]]] = {}
    units: list[dict[str, object]] = []
    for asset in assets:
        asset_units = []
        asset_identity = (str(asset["asset_class"]), str(asset["symbol"]))
        probe_periods = [
            (str(probe["period_start"]), str(probe["period_end"]))
            for probe in FIXED_TECHNICAL_PROBES
            if (str(probe["asset_class"]), str(probe["symbol"]))
            == asset_identity
        ]
        periods = (*FIXED_PERIODS, *probe_periods)
        if len(periods) != len(set(periods)):
            raise DevelopmentV6BenchmarkError(
                f"Duplicate fixed benchmark period for {asset_identity}: {periods}"
            )
        for period_start, period_end in periods:
            identity = {
                "version": BENCHMARK_VERSION,
                "asset_key": asset["asset_key"],
                "period_start": period_start,
                "period_end": period_end,
            }
            unit = {
                "work_unit_id": "madv6-benchmark-unit-" + fingerprint(identity)[:24],
                "asset_key": asset["asset_key"],
                "asset_class": asset["asset_class"],
                "symbol": asset["symbol"],
                "period_start": period_start,
                "period_end": period_end,
                "attempts": 1,
            }
            asset_units.append(unit)
            units.append(unit)
        units_by_asset[str(asset["asset_key"])] = asset_units
    return {
        "selection": "fixed_technical_not_outcome_selected",
        "assets": assets,
        "units": units,
        "units_by_asset": units_by_asset,
        "sample_fingerprint": fingerprint(
            {
                "symbols": FIXED_SYMBOLS,
                "periods": FIXED_PERIODS,
                "technical_probes": FIXED_TECHNICAL_PROBES,
                "universe_fingerprint": universe["universe_fingerprint"],
            }
        ),
    }


def _worker_compute(kwargs: Mapping[str, object]) -> dict[str, object]:
    started = time.perf_counter()
    cpu_started = time.process_time()
    result = compute_v6_asset_batch(**dict(kwargs))
    return {
        "worker_pid": os.getpid(),
        "worker_wall_seconds": time.perf_counter() - started,
        "worker_cpu_seconds": time.process_time() - cpu_started,
        "worker_memory": _memory_snapshot(),
        "scientific_digest": result_scientific_digest(result),
        "result": result,
    }


def _benchmark_manifest(
    *, worker_count: int, contract: Mapping[str, object], sample: Mapping[str, object]
) -> dict[str, object]:
    basis = {
        "version": BENCHMARK_VERSION,
        "worker_count": worker_count,
        "sample_fingerprint": sample["sample_fingerprint"],
        "contract_version": contract["contract_version"],
        "combined_input_fingerprint": dict(contract["reference_fingerprints"])[
            "combined_input_fingerprint"
        ],
    }
    payload: dict[str, object] = {
        "run_id": "madv6-worker-benchmark-" + fingerprint(basis)[:20],
        "development_contract_fingerprint": str(
            contract.get("contract_fingerprint") or fingerprint(contract)
        ),
        "combined_input_fingerprint": basis["combined_input_fingerprint"],
        "universe_fingerprint": "benchmark:" + str(sample["sample_fingerprint"]),
        "work_plan_fingerprint": fingerprint(sample["units"]),
        "commit": "BENCHMARK_PRE_FREEZE",
        "worker_count": worker_count,
        "sqlite_writer_count": 1,
        "started_at": "2026-09-05T00:00:00+00:00",
    }
    payload["run_manifest_fingerprint"] = fingerprint(payload)
    return payload


def _technical_coverage(
    *, outputs: Sequence[Mapping[str, object]], sample: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, bool]]:
    """Prove that the fixed benchmark exercised its declared technical cases.

    These counters are strictly operational gates.  They never inspect which
    worker configuration produced more favorable market outcomes and cannot
    participate in research selection.
    """

    class_by_asset = {
        str(item["asset_key"]): str(item["asset_class"])
        for item in sample.get("assets") or []
    }
    cases_by_class: Counter[str] = Counter()
    outcome_statuses: Counter[str] = Counter()
    r_unavailable = 0
    structural_r_na_reasons: Counter[str] = Counter()
    no_data_assets = 0
    gap_safe_history_unavailable_assets = 0
    unexpected_skip_assets = 0
    known_gap_assets = 0
    periods_with_cases: set[tuple[str, str]] = set()
    history_observation_counts: dict[str, int] = {}
    exercised_classes: set[str] = set()
    classified_classes: set[str] = set()
    for raw in outputs:
        result = dict(raw)
        asset_key = str(result.get("asset_key") or "")
        asset_class = class_by_asset.get(asset_key, "UNKNOWN")
        if asset_class != "UNKNOWN":
            exercised_classes.add(asset_class)
        coverage = dict(result.get("coverage") or {})
        active_observations = coverage.get("active_valid_bars")
        if (
            isinstance(active_observations, int)
            and not isinstance(active_observations, bool)
            and active_observations > 0
        ):
            history_observation_counts[asset_key] = active_observations
        skip_reason_code = str(result.get("skip_reason_code") or "")
        if skip_reason_code == "EXPECTED_NO_DEVELOPMENT_DATA":
            no_data_assets += 1
            if asset_class != "UNKNOWN":
                classified_classes.add(asset_class)
        elif skip_reason_code == "NO_GAP_SAFE_220_OBSERVATION_HISTORY":
            gap_safe_history_unavailable_assets += 1
            if asset_class != "UNKNOWN":
                classified_classes.add(asset_class)
        elif skip_reason_code:
            unexpected_skip_assets += 1
        if int(result.get("gap_boundary_count") or 0) > 0:
            known_gap_assets += 1
        for raw_unit in result.get("unit_results") or []:
            unit = dict(raw_unit)
            feature_count = len(unit.get("features") or [])
            cases_by_class[asset_class] += feature_count
            if feature_count and asset_class != "UNKNOWN":
                classified_classes.add(asset_class)
            unit_identity = dict(unit.get("unit") or {})
            if feature_count:
                periods_with_cases.add(
                    (
                        str(unit_identity.get("period_start") or ""),
                        str(unit_identity.get("period_end") or ""),
                    )
                )
            for raw_outcome in unit.get("outcomes") or []:
                outcome = dict(raw_outcome)
                outcome_statuses[str(outcome.get("status") or "UNKNOWN")] += 1
                if outcome.get("r_metrics_status") != "AVAILABLE":
                    r_unavailable += 1
                r_reason = str(outcome.get("r_metrics_reason") or "")
                if (
                    outcome.get("r_metrics_status") == "UNAVAILABLE"
                    and r_reason in STRUCTURAL_R_NA_REASONS
                ):
                    structural_r_na_reasons[r_reason] += 1
    required_classes = {"EQUITIES", "ETF", "CRYPTO", "FX"}
    declared_periods = {
        (str(unit.get("period_start")), str(unit.get("period_end")))
        for unit in sample.get("units") or []
    }
    distinct_history_lengths = sorted(set(history_observation_counts.values()))
    counters: dict[str, object] = {
        "cases_by_asset_class": dict(sorted(cases_by_class.items())),
        "outcome_status_counts": dict(sorted(outcome_statuses.items())),
        "r_unavailable_cases": r_unavailable,
        "structural_r_na_reason_counts": dict(sorted(structural_r_na_reasons.items())),
        "no_data_asset_results": no_data_assets,
        "gap_safe_history_unavailable_asset_results": (
            gap_safe_history_unavailable_assets
        ),
        "unexpected_skip_asset_results": unexpected_skip_assets,
        "exercised_asset_classes": sorted(exercised_classes),
        "classified_asset_classes": sorted(classified_classes),
        "known_gap_asset_results": known_gap_assets,
        "declared_distinct_periods": len(declared_periods),
        "distinct_periods_with_cases": len(periods_with_cases),
        "periods_with_cases": [list(item) for item in sorted(periods_with_cases)],
        "history_observation_counts": dict(sorted(history_observation_counts.items())),
        "distinct_positive_history_lengths": len(distinct_history_lengths),
        "minimum_history_observations": (
            distinct_history_lengths[0] if distinct_history_lengths else None
        ),
        "maximum_history_observations": (
            distinct_history_lengths[-1] if distinct_history_lengths else None
        ),
        "history_length_observation_spread": (
            distinct_history_lengths[-1] - distinct_history_lengths[0]
            if distinct_history_lengths
            else None
        ),
    }
    gates = {
        "all_four_asset_classes_exercised_and_classified": (
            required_classes <= exercised_classes
            and required_classes <= classified_classes
        ),
        "known_gap_asset_exercised": known_gap_assets > 0,
        "input_gap_censoring_exercised": outcome_statuses["CENSORED_AT_INPUT_GAP"] > 0,
        "structural_r_na_exercised": sum(structural_r_na_reasons.values()) > 0,
        "stage_boundary_censoring_exercised": outcome_statuses[
            "CENSORED_AT_STAGE_BOUNDARY"
        ]
        > 0,
        "no_data_skip_exercised": no_data_assets > 0,
        "gap_safe_history_skip_exercised": (
            gap_safe_history_unavailable_assets > 0
        ),
        "no_unexpected_asset_skip": unexpected_skip_assets == 0,
        "multiple_quarters_exercised": len(periods_with_cases) >= 2,
        "different_history_lengths_exercised": len(distinct_history_lengths) >= 2,
    }
    return counters, gates


def configuration_evidence_checks(
    configuration: Mapping[str, object],
) -> dict[str, bool]:
    """Validate non-scientific benchmark evidence without outcome selection."""

    item = dict(configuration)
    raw_technical = item.get("technical_coverage_gates")
    technical = dict(raw_technical) if isinstance(raw_technical, Mapping) else {}

    def integer(name: str) -> int | None:
        value = item.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def numeric(name: str, *, positive: bool = False) -> bool:
        value = item.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        return float(value) > 0.0 if positive else float(value) >= 0.0

    worker_count = integer("worker_count")
    work_unit_count = integer("work_unit_count")
    receipt_count = integer("receipt_count")
    asset_result_count = integer("asset_result_count")
    digest_check_count = integer("worker_result_digest_check_count")
    observed_workers = integer("worker_process_count_observed")
    writer_pid = integer("central_writer_pid")
    digest = str(item.get("scientific_digest") or "")
    return {
        "configuration_status_pass": item.get("status") == "PASS",
        "worker_count_positive": worker_count is not None and worker_count > 0,
        "work_units_fully_receipted": work_unit_count is not None
        and work_unit_count > 0
        and receipt_count == work_unit_count,
        "asset_results_observed": asset_result_count is not None
        and asset_result_count > 0,
        "worker_result_digests_verified": item.get(
            "worker_result_digests_verified"
        )
        is True
        and digest_check_count is not None
        and digest_check_count == asset_result_count,
        "scientific_digest_recorded": len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest),
        "all_technical_gates_present": set(technical)
        == set(REQUIRED_TECHNICAL_COVERAGE_GATES),
        "all_technical_gates_pass": bool(technical)
        and all(value is True for value in technical.values()),
        "single_sqlite_writer": item.get("sqlite_writer_count") == 1,
        "central_writer_recorded": writer_pid is not None and writer_pid > 0,
        "writer_transactions_match_receipts": integer(
            "central_writer_transaction_count"
        )
        == receipt_count
        and receipt_count is not None,
        "no_errors_or_retries": not list(item.get("errors") or [])
        and item.get("retries") == 0,
        "worker_process_count_plausible": observed_workers is not None
        and worker_count is not None
        and 0 < observed_workers <= worker_count,
        "wall_time_recorded": numeric("wall_seconds", positive=True),
        "throughput_recorded": numeric("throughput_cases_per_second", positive=True),
        "ram_recorded": numeric("peak_ram_upper_bound_bytes", positive=True),
        "worker_cpu_recorded": numeric("worker_cpu_seconds"),
        "parent_cpu_recorded": numeric("parent_cpu_seconds"),
        "cpu_utilization_recorded": numeric(
            "aggregate_cpu_utilization_pct_of_one_logical_cpu"
        )
        and numeric("aggregate_cpu_utilization_pct_of_available_worker_capacity"),
        "writer_timing_recorded": numeric("central_writer_elapsed_seconds")
        and numeric("writer_wait_seconds_total")
        and numeric("writer_wait_seconds_max"),
    }


def _validated_skipped_unit_ids(
    result: Mapping[str, object], expected_unit_ids: Sequence[str]
) -> list[str]:
    raw_unit_ids = result.get("unit_ids")
    returned = (
        [str(item) for item in raw_unit_ids]
        if isinstance(raw_unit_ids, list)
        else []
    )
    expected = [str(item) for item in expected_unit_ids]
    if (
        not isinstance(raw_unit_ids, list)
        or len(returned) != len(set(returned))
        or set(returned) != set(expected)
    ):
        raise DevelopmentV6BenchmarkError(
            "Skipped asset returned a different or duplicate benchmark "
            "work-unit set."
        )
    return returned


def _read_receipt_count(control_path: Path) -> int:
    """Read the benchmark receipt count without leaking a Windows DB handle."""

    with closing(sqlite3.connect(Path(control_path))) as connection:
        return int(
            connection.execute("SELECT COUNT(*) FROM unit_receipts").fetchone()[0]
        )


def run_worker_configuration(
    *,
    worker_count: int,
    contract: Mapping[str, object],
    sample: Mapping[str, object],
    compute_paths: Mapping[str, Path] | None = None,
) -> dict[str, object]:
    compute_paths = {key: Path(value) for key, value in dict(compute_paths or {}).items()}
    units = list(sample["units"])
    work_plan = {"total_planned_work_units": len(units), "units": units}
    manifest = _benchmark_manifest(
        worker_count=worker_count, contract=contract, sample=sample
    )
    started = time.perf_counter()
    parent_cpu_started = time.process_time()
    completed_times: dict[int, float] = {}
    writer_waits: list[float] = []
    writer_seconds = 0.0
    errors: list[dict[str, str]] = []
    outputs: list[dict[str, object]] = []
    worker_peaks: dict[int, int] = {}
    worker_cpu = 0.0
    verified_worker_digests = 0
    with tempfile.TemporaryDirectory(prefix=f"madv6-benchmark-{worker_count}-") as root:
        root_path = Path(root)
        feature_path = root_path / "features.sqlite3"
        outcome_path = root_path / "outcomes.sqlite3"
        control_path = root_path / "control.sqlite3"
        initialize_v6_run(
            run_manifest=manifest,
            work_plan=work_plan,
            feature_path=feature_path,
            outcome_path=outcome_path,
            control_path=control_path,
        )
        jobs = []
        for asset in sample["assets"]:
            kwargs = {
                "asset": dict(asset),
                "units": list(sample["units_by_asset"][str(asset["asset_key"])]),
                "contract": dict(contract),
                **compute_paths,
            }
            jobs.append(kwargs)
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures: list[Future[dict[str, object]]] = []
            for kwargs in jobs:
                future = pool.submit(_worker_compute, kwargs)
                future.add_done_callback(
                    lambda done, target=completed_times: target.__setitem__(
                        id(done), time.perf_counter()
                    )
                )
                futures.append(future)
            for future in as_completed(futures):
                write_started = time.perf_counter()
                writer_waits.append(
                    max(0.0, write_started - completed_times.get(id(future), write_started))
                )
                try:
                    wrapped = future.result()
                    result = dict(wrapped["result"])
                    if str(wrapped.get("scientific_digest") or "") != result_scientific_digest(
                        result
                    ):
                        raise DevelopmentV6BenchmarkError(
                            "Worker scientific digest differs from returned payload."
                        )
                    verified_worker_digests += 1
                    outputs.append(result)
                    worker_pid = int(wrapped["worker_pid"])
                    worker_peaks[worker_pid] = max(
                        worker_peaks.get(worker_pid, 0),
                        int(dict(wrapped["worker_memory"])["peak_working_set_bytes"]),
                    )
                    worker_cpu += float(wrapped["worker_cpu_seconds"])
                    writer_started = time.perf_counter()
                    asset_units = {
                        str(unit["work_unit_id"]): unit
                        for unit in sample["units_by_asset"][str(result["asset_key"])]
                    }
                    if result.get("skip_reason_code"):
                        _validated_skipped_unit_ids(result, list(asset_units))
                        for unit in asset_units.values():
                            skip_work_unit(
                                writer_pid=os.getpid(),
                                run_id=str(manifest["run_id"]),
                                unit=unit,
                                reason_code=str(result["skip_reason_code"]),
                                reason=str(result["skip_reason"]),
                                feature_path=feature_path,
                                outcome_path=outcome_path,
                                control_path=control_path,
                            )
                    else:
                        for unit_result in result.get("unit_results") or []:
                            persist_and_complete_work_unit(
                                writer_pid=os.getpid(),
                                run_id=str(manifest["run_id"]),
                                unit=dict(unit_result["unit"]),
                                features=unit_result["features"],
                                outcomes=unit_result["outcomes"],
                                summary=dict(unit_result["summary"]),
                                feature_path=feature_path,
                                outcome_path=outcome_path,
                                control_path=control_path,
                            )
                    writer_seconds += time.perf_counter() - writer_started
                except Exception as exc:  # benchmark records, then fails closed
                    errors.append(
                        {"error_class": type(exc).__name__, "error": str(exc)[:1000]}
                    )
        receipt_count = _read_receipt_count(control_path)
    wall = time.perf_counter() - started
    case_count = sum(
        len(unit["features"])
        for result in outputs
        for unit in result.get("unit_results") or []
    )
    scientific_digest = fingerprint(
        sorted(
            (str(result["asset_key"]), result_scientific_digest(result))
            for result in outputs
        )
    )
    coverage, coverage_gates = _technical_coverage(outputs=outputs, sample=sample)
    technical_pass = all(coverage_gates.values())
    aggregate_cpu_seconds = worker_cpu + (time.process_time() - parent_cpu_started)
    return {
        "worker_count": worker_count,
        "status": (
            "PASS"
            if not errors and receipt_count == len(units) and technical_pass
            else "FAIL"
        ),
        "wall_seconds": round(wall, 6),
        "throughput_cases_per_second": round(case_count / wall, 6) if wall else None,
        "case_count": case_count,
        "asset_result_count": len(outputs),
        "work_unit_count": len(units),
        "receipt_count": receipt_count,
        "peak_ram_upper_bound_bytes": sum(worker_peaks.values())
        + int(_memory_snapshot()["peak_working_set_bytes"]),
        "worker_process_count_observed": len(worker_peaks),
        "worker_cpu_seconds": round(worker_cpu, 6),
        "parent_cpu_seconds": round(time.process_time() - parent_cpu_started, 6),
        "aggregate_cpu_utilization_pct_of_one_logical_cpu": round(
            100.0 * aggregate_cpu_seconds / wall, 3
        )
        if wall
        else None,
        "aggregate_cpu_utilization_pct_of_available_worker_capacity": round(
            100.0 * aggregate_cpu_seconds / (wall * worker_count), 3
        )
        if wall and worker_count
        else None,
        "central_writer_elapsed_seconds": round(writer_seconds, 6),
        "central_writer_pid": os.getpid(),
        "central_writer_transaction_count": receipt_count,
        "writer_wait_seconds_total": round(sum(writer_waits), 6),
        "writer_wait_seconds_max": round(max(writer_waits, default=0.0), 6),
        "errors": errors,
        "retries": 0,
        "scientific_digest": scientific_digest,
        "worker_result_digest_check_count": verified_worker_digests,
        "worker_result_digests_verified": verified_worker_digests == len(outputs)
        and bool(outputs),
        "sqlite_writer_count": 1,
        "technical_coverage": coverage,
        "technical_coverage_gates": coverage_gates,
    }


def classify_worker_configurations(
    results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Classify configurations against the mandatory one-worker reference."""

    configurations = [dict(item) for item in results]
    reference_rows = [
        item for item in configurations if item.get("worker_count") == 1
    ]
    reference = reference_rows[0] if len(reference_rows) == 1 else None
    reference_checks = (
        configuration_evidence_checks(reference) if reference is not None else {}
    )
    reference_pass = bool(reference_checks) and all(reference_checks.values())
    reference_digest = (
        str(reference.get("scientific_digest") or "")
        if reference_pass and reference is not None
        else None
    )
    decisions: dict[str, dict[str, object]] = {}
    candidates: list[int] = []
    excluded_multi: list[dict[str, object]] = []
    for item in configurations:
        worker_count = item.get("worker_count")
        label = str(worker_count)
        checks = configuration_evidence_checks(item)
        reasons = [
            f"CONFIGURATION_EVIDENCE_FAILED:{name}"
            for name, passed in checks.items()
            if not passed
        ]
        digest_matches_reference = bool(reference_digest) and str(
            item.get("scientific_digest") or ""
        ) == reference_digest
        if worker_count != 1 and not digest_matches_reference:
            reasons.append("SCIENTIFIC_DIGEST_DIFFERS_FROM_ONE_WORKER_REFERENCE")
        if not reference_pass:
            reasons.append("ONE_WORKER_REFERENCE_NOT_VALID")
        eligible = not reasons and reference_pass
        if eligible and isinstance(worker_count, int) and not isinstance(
            worker_count, bool
        ):
            candidates.append(worker_count)
        decision = {
            "worker_count": worker_count,
            "status": item.get("status"),
            "evidence_checks": checks,
            "digest_matches_one_worker_reference": digest_matches_reference,
            "eligible_for_selection": eligible,
            "exclusion_reasons": sorted(set(reasons)),
        }
        decisions[label] = decision
        if worker_count != 1 and not eligible:
            excluded_multi.append(
                {
                    "worker_count": worker_count,
                    "reasons": decision["exclusion_reasons"],
                }
            )
    return {
        "reference_worker_count": 1,
        "reference_configuration_count": len(reference_rows),
        "reference_configuration_passed": reference_pass,
        "reference_scientific_digest": reference_digest,
        "configuration_decisions": decisions,
        "selection_candidate_worker_counts": sorted(candidates),
        "excluded_multi_worker_configurations": sorted(
            excluded_multi, key=lambda item: int(item.get("worker_count") or 0)
        ),
    }


def select_worker_count(results: Sequence[Mapping[str, object]]) -> int:
    classification = classify_worker_configurations(results)
    if classification.get("reference_configuration_passed") is not True:
        raise DevelopmentV6BenchmarkError(
            "The mandatory one-worker reference configuration did not pass."
        )
    candidate_counts = set(
        classification.get("selection_candidate_worker_counts") or []
    )
    passing = [
        item for item in results if item.get("worker_count") in candidate_counts
    ]
    if not passing:
        raise DevelopmentV6BenchmarkError(
            "No configuration is stable and identical to the one-worker reference."
        )
    fastest = min(passing, key=lambda item: float(item["wall_seconds"]))
    near_fastest = [
        item
        for item in passing
        if float(item["wall_seconds"]) <= float(fastest["wall_seconds"]) * 1.10
    ]
    return min(int(item["worker_count"]) for item in near_fastest)


def _run_v6_worker_benchmark_with_locks_held(
    *,
    contract: Mapping[str, object],
    universe: Mapping[str, object],
    input_precheck_fingerprint: str,
    descriptive_plan: Mapping[str, object],
    output_path: Path = DEFAULT_BENCHMARK_ARTIFACT,
    compute_paths: Mapping[str, Path] | None = None,
    worker_input_precheck: Mapping[str, str] | None = None,
    created_at: str | None = None,
    production_protection_config: Path = DEFAULT_PRODUCTION_PROTECTION_CONFIG,
    fx_observer_lock_path: Path = DEFAULT_FX_OBSERVER_LOCK,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    benchmark_created_at = created_at or datetime.now(timezone.utc).isoformat()
    plan_reference = _descriptive_plan_reference(
        descriptive_plan,
        benchmark_created_at=benchmark_created_at,
        expected_contract_basis_fingerprint=fingerprint(contract),
    )
    combined_input_fingerprint = str(
        dict(contract["reference_fingerprints"])["combined_input_fingerprint"]
    )
    if descriptive_plan.get("combined_input_fingerprint") != combined_input_fingerprint:
        raise DevelopmentV6BenchmarkError(
            "Descriptive plan and benchmark contract use different inputs."
        )
    resources = system_resources()
    sample = fixed_benchmark_sample(universe)
    results: list[dict[str, object]] = []
    readiness_checks: list[dict[str, object]] = []
    for count in eligible_worker_counts(resources):
        clear, reason, detail = benchmark_dispatch_readiness(
            production_protection_config=Path(production_protection_config),
            fx_observer_lock_path=Path(fx_observer_lock_path),
            project_root=Path(project_root),
        )
        readiness_checks.append(
            {
                "worker_count": count,
                "status": "PASS" if clear else "BLOCKED",
                "reason": reason,
                "detail": detail,
            }
        )
        if not clear:
            raise DevelopmentV6BenchmarkError(
                f"Benchmark compute blocked by protected runtime: {reason}"
            )
        results.append(
            run_worker_configuration(
                worker_count=count,
                contract=contract,
                sample=sample,
                compute_paths=compute_paths,
            )
        )
    evidence_checks = {
        str(item["worker_count"]): configuration_evidence_checks(item)
        for item in results
    }
    complete_evidence = bool(evidence_checks) and all(
        checks and all(checks.values()) for checks in evidence_checks.values()
    )
    classification = classify_worker_configurations(results)
    reference_pass = classification["reference_configuration_passed"] is True
    selected = select_worker_count(results) if reference_pass else None
    reference_digest = classification.get("reference_scientific_digest")
    configuration_digests = [
        str(item.get("scientific_digest") or "") for item in results
    ]
    all_payloads_equal = bool(reference_digest) and all(
        digest == reference_digest for digest in configuration_digests
    )
    selection_candidates = set(
        classification.get("selection_candidate_worker_counts") or []
    )
    selectable_payloads_identical = bool(selection_candidates) and all(
        str(item.get("scientific_digest") or "") == reference_digest
        for item in results
        if item.get("worker_count") in selection_candidates
    )
    excluded_multi = list(
        classification.get("excluded_multi_worker_configurations") or []
    )
    fallback_to_reference = selected == 1
    fallback_reasons: list[str] = []
    if fallback_to_reference:
        if excluded_multi:
            fallback_reasons.append(
                "ONE_OR_MORE_MULTI_WORKER_CONFIGURATIONS_EXCLUDED"
            )
        eligible_multi = sorted(count for count in selection_candidates if count > 1)
        if not eligible_multi:
            fallback_reasons.append(
                "NO_STABLE_IDENTICAL_MULTI_WORKER_CONFIGURATION"
            )
        else:
            fallback_reasons.append(
                "MULTI_WORKER_NOT_MATERIALLY_FASTER_THAN_REFERENCE"
            )
    expected_counts = list(eligible_worker_counts(resources))
    benchmark_completed = sorted(int(item["worker_count"]) for item in results) == sorted(
        expected_counts
    )
    benchmark_pass = reference_pass and selected is not None and benchmark_completed
    payload: dict[str, object] = {
        "version": BENCHMARK_VERSION,
        "created_at": benchmark_created_at,
        "status": "PASS" if benchmark_pass else "FAIL",
        "input_precheck_fingerprint": input_precheck_fingerprint,
        "worker_input_precheck_artifact": dict(worker_input_precheck or {}),
        "combined_input_fingerprint": combined_input_fingerprint,
        "descriptive_plan_artifact_fingerprint": plan_reference[
            "artifact_fingerprint"
        ],
        "descriptive_plan_created_at": plan_reference["created_at"],
        "scientific_parent_contract_fingerprint": contract.get(
            "parent_contract_fingerprint"
        ),
        "sample_fingerprint": sample["sample_fingerprint"],
        "sample_assets": [
            {"asset_class": item[0], "symbol": item[1]} for item in FIXED_SYMBOLS
        ],
        "sample_periods": [list(item) for item in FIXED_PERIODS],
        "sample_technical_probes": [dict(item) for item in FIXED_TECHNICAL_PROBES],
        "selection_used_outcomes": False,
        "resources": resources,
        "protected_runtime_checks_before_each_configuration": readiness_checks,
        "exclusive_benchmark_process_lock_held": True,
        "global_research_lock_held": True,
        "configurations": results,
        "configuration_evidence_checks": evidence_checks,
        "all_configuration_evidence_complete": complete_evidence,
        "benchmark_completed": benchmark_completed,
        "reference_worker_count": classification["reference_worker_count"],
        "reference_configuration_count": classification[
            "reference_configuration_count"
        ],
        "reference_configuration_passed": reference_pass,
        "reference_scientific_digest": reference_digest,
        "configuration_decisions": classification["configuration_decisions"],
        "selection_candidate_worker_counts": classification[
            "selection_candidate_worker_counts"
        ],
        "excluded_multi_worker_configurations": excluded_multi,
        "all_tested_payloads_equal_to_reference": all_payloads_equal,
        "all_selection_candidates_identical_to_reference": (
            selectable_payloads_identical
        ),
        "deterministic_payloads_equal": all_payloads_equal,
        "selected_worker_count": selected,
        "selected_digest_matches_one_worker_reference": selected is not None
        and any(
            item.get("worker_count") == selected
            and str(item.get("scientific_digest") or "") == reference_digest
            for item in results
        ),
        "fallback_to_one_worker": fallback_to_reference,
        "fallback_reasons": fallback_reasons,
        "multi_worker_instability_is_not_a_start_blocker": True,
        "sqlite_writer_count": 1,
        "selection_rule": "smallest_configuration_within_10_percent_of_fastest_stable_identical",
        "benchmark_used_for_research_selection": False,
        "validation_opened": False,
        "holdout_opened": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    _write_immutable(Path(output_path), payload)
    return payload


def run_v6_worker_benchmark(
    *,
    contract: Mapping[str, object],
    universe: Mapping[str, object],
    input_precheck_fingerprint: str,
    descriptive_plan: Mapping[str, object],
    output_path: Path = DEFAULT_BENCHMARK_ARTIFACT,
    compute_paths: Mapping[str, Path] | None = None,
    created_at: str | None = None,
    process_lock_path: Path = DEFAULT_BENCHMARK_PROCESS_LOCK,
    global_research_lock_path: Path = DEFAULT_GLOBAL_RESEARCH_LOCK,
    production_protection_config: Path = DEFAULT_PRODUCTION_PROTECTION_CONFIG,
    fx_observer_lock_path: Path = DEFAULT_FX_OBSERVER_LOCK,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    """Run the benchmark under its own and the global research lock."""

    verified_compute_paths, worker_input_precheck = (
        _validated_benchmark_compute_paths(
            compute_paths,
            input_precheck_fingerprint=input_precheck_fingerprint,
            contract_input_precheck_fingerprint=str(
                dict(contract.get("reference_fingerprints") or {}).get(
                    "input_precheck_artifact_fingerprint"
                )
                or ""
            ),
            contract_input_precheck_path=str(
                dict(contract.get("development_execution") or {}).get(
                    "input_precheck_artifact"
                )
                or ""
            ),
            contract_input_precheck_version=str(
                dict(contract.get("development_execution") or {}).get(
                    "input_precheck_version"
                )
                or ""
            ),
            contract_development_code_fingerprint=str(
                dict(contract.get("reference_fingerprints") or {}).get(
                    "development_code_fingerprint"
                )
                or ""
            ),
            project_root=Path(project_root),
        )
    )
    process_lock = SwingRunLock(Path(process_lock_path))
    research_lock = SwingRunLock(Path(global_research_lock_path))
    try:
        process_lock.acquire()
    except SwingRunAlreadyActiveError as exc:
        raise DevelopmentV6BenchmarkError(
            "Another Development-v6 worker benchmark is already active."
        ) from exc
    try:
        try:
            research_lock.acquire()
        except SwingRunAlreadyActiveError as exc:
            raise DevelopmentV6BenchmarkError(
                "Global historical research lock is already active."
            ) from exc
        try:
            return _run_v6_worker_benchmark_with_locks_held(
                contract=contract,
                universe=universe,
                input_precheck_fingerprint=input_precheck_fingerprint,
                descriptive_plan=descriptive_plan,
                output_path=Path(output_path),
                compute_paths=verified_compute_paths,
                worker_input_precheck=worker_input_precheck,
                created_at=created_at,
                production_protection_config=Path(production_protection_config),
                fx_observer_lock_path=Path(fx_observer_lock_path),
                project_root=Path(project_root),
            )
        finally:
            research_lock.release()
    finally:
        process_lock.release()


__all__ = [
    "BENCHMARK_VERSION",
    "DEFAULT_BENCHMARK_ARTIFACT",
    "DevelopmentV6BenchmarkError",
    "FIXED_PERIODS",
    "FIXED_SYMBOLS",
    "FIXED_TECHNICAL_PROBES",
    "REQUIRED_TECHNICAL_COVERAGE_GATES",
    "configuration_evidence_checks",
    "classify_worker_configurations",
    "eligible_worker_counts",
    "fixed_benchmark_sample",
    "run_v6_worker_benchmark",
    "run_worker_configuration",
    "select_worker_count",
    "system_resources",
]
