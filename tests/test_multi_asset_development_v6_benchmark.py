from __future__ import annotations

import json
from pathlib import Path

import pytest

import multi_asset_development_v6_benchmark as benchmark
from multi_asset_discovery_v1 import fingerprint


_TEST_INPUT_PRECHECK: dict[str, object] = {
    "version": "test-v6-input-precheck",
    "status": "PASS",
}
_TEST_INPUT_PRECHECK["artifact_fingerprint"] = fingerprint(_TEST_INPUT_PRECHECK)


def _input_compute_paths(tmp_path: Path) -> dict[str, Path]:
    precheck_path = tmp_path / "runtime" / "input-precheck-v1-r2.json"
    precheck_path.parent.mkdir(parents=True, exist_ok=True)
    precheck_path.write_text(
        json.dumps(_TEST_INPUT_PRECHECK, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"input_precheck_artifact": precheck_path}


def _contract() -> dict[str, object]:
    return {
        "contract_version": "v6",
        "parent_contract_fingerprint": "parent-fp",
        "reference_fingerprints": {"combined_input_fingerprint": "input-fp"},
    }


def _descriptive_plan(
    *, created_at: str = "2026-09-04T00:00:00+00:00"
) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": benchmark.DESCRIPTIVE_PLAN_VERSION,
        "status": "FROZEN",
        "created_at": created_at,
        "combined_input_fingerprint": "input-fp",
        "inferential_claims_allowed": False,
        "selection_or_optimization_allowed": False,
    }
    payload["artifact_fingerprint"] = fingerprint(payload)
    return payload


def _safe_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    monkeypatch.setattr(
        benchmark,
        "benchmark_dispatch_readiness",
        lambda **kwargs: (True, "CLEAR", {"synthetic_test": True}),
    )
    return {
        "descriptive_plan": _descriptive_plan(),
        "compute_paths": _input_compute_paths(tmp_path),
        "process_lock_path": tmp_path / "benchmark.lock",
        "global_research_lock_path": tmp_path / "research.lock",
        "fx_observer_lock_path": tmp_path / "fx.lock",
        "production_protection_config": tmp_path / "unused.json",
        "project_root": tmp_path,
    }


def _configuration(workers: int, seconds: float, digest: str = "same") -> dict[str, object]:
    return {
        "worker_count": workers,
        "status": "PASS",
        "wall_seconds": seconds,
        "throughput_cases_per_second": 10.0,
        "case_count": 10,
        "asset_result_count": 4,
        "work_unit_count": 8,
        "receipt_count": 8,
        "peak_ram_upper_bound_bytes": 1024,
        "worker_process_count_observed": workers,
        "worker_cpu_seconds": 1.0,
        "parent_cpu_seconds": 0.1,
        "aggregate_cpu_utilization_pct_of_one_logical_cpu": 50.0,
        "aggregate_cpu_utilization_pct_of_available_worker_capacity": 25.0,
        "central_writer_elapsed_seconds": 0.1,
        "central_writer_pid": 123,
        "central_writer_transaction_count": 8,
        "writer_wait_seconds_total": 0.0,
        "writer_wait_seconds_max": 0.0,
        "errors": [],
        "retries": 0,
        "scientific_digest": fingerprint(digest),
        "worker_result_digest_check_count": 4,
        "worker_result_digests_verified": True,
        "sqlite_writer_count": 1,
        "technical_coverage_gates": {
            name: True for name in benchmark.REQUIRED_TECHNICAL_COVERAGE_GATES
        },
    }


def test_six_workers_only_when_real_cpu_and_memory_allow_it() -> None:
    assert benchmark.eligible_worker_counts(
        {"logical_cpu_count": 12, "total_physical_memory_bytes": 16 * 1024**3}
    ) == (1, 2, 4, 6)
    assert benchmark.eligible_worker_counts(
        {"logical_cpu_count": 4, "total_physical_memory_bytes": 16 * 1024**3}
    ) == (1, 2, 4)
    assert benchmark.eligible_worker_counts(
        {"logical_cpu_count": 12, "total_physical_memory_bytes": 8 * 1024**3}
    ) == (1, 2, 4)


def test_selection_prefers_simpler_configuration_for_marginal_gain() -> None:
    assert benchmark.select_worker_count(
        [_configuration(1, 100), _configuration(2, 55), _configuration(4, 51)]
    ) == 2
    assert benchmark.select_worker_count(
        [_configuration(1, 100), _configuration(2, 80), _configuration(4, 50)]
    ) == 4


def test_failed_configuration_is_never_selected() -> None:
    failed = _configuration(4, 10)
    failed["status"] = "FAIL"
    assert benchmark.select_worker_count([_configuration(1, 100), failed]) == 1
    with pytest.raises(benchmark.DevelopmentV6BenchmarkError):
        benchmark.select_worker_count([failed])


def test_fixed_sample_is_not_selected_from_outcomes() -> None:
    assets = [
        {"asset_class": asset_class, "symbol": symbol, "asset_key": f"{asset_class}:{symbol}"}
        for asset_class, symbol in benchmark.FIXED_SYMBOLS
    ]
    sample = benchmark.fixed_benchmark_sample(
        {"universe_fingerprint": "u", "assets": assets}
    )
    assert sample["selection"] == "fixed_technical_not_outcome_selected"
    assert len(sample["units"]) == len(benchmark.FIXED_SYMBOLS) * len(
        benchmark.FIXED_PERIODS
    )
    with pytest.raises(benchmark.DevelopmentV6BenchmarkError):
        benchmark.fixed_benchmark_sample(
            {"universe_fingerprint": "u", "assets": assets[:-1]}
        )


def test_technical_coverage_requires_real_gap_na_stage_and_all_classes() -> None:
    assets = [
        {"asset_key": f"{name}:X", "asset_class": name}
        for name in ("EQUITIES", "ETF", "CRYPTO", "FX")
    ]
    units = [
        {"period_start": "2020-10-01", "period_end": "2020-12-31"},
        {"period_start": "2021-10-01", "period_end": "2021-12-31"},
    ]
    statuses = {
        "EQUITIES": "CENSORED_AT_INPUT_GAP",
        "ETF": "COMPLETE",
        "CRYPTO": "CENSORED_AT_STAGE_BOUNDARY",
        "FX": "COMPLETE",
    }
    outputs = []
    for asset in assets:
        name = asset["asset_class"]
        history_length = {
            "EQUITIES": 1500,
            "ETF": 1400,
            "CRYPTO": 700,
            "FX": 900,
        }[name]
        outputs.append(
            {
                "asset_key": asset["asset_key"],
                "coverage": {"active_valid_bars": history_length},
                "gap_boundary_count": 1 if name == "EQUITIES" else 0,
                "skip_reason_code": None,
                "unit_results": [
                    {
                        "unit": {
                            "period_start": units[0]["period_start"],
                            "period_end": units[0]["period_end"],
                        },
                        "features": [{"case_id": name}],
                        "outcomes": [
                            {
                                "status": statuses[name],
                                "r_metrics_status": (
                                    "UNAVAILABLE" if name == "ETF" else "AVAILABLE"
                                ),
                                "r_metrics_reason": (
                                    "MISSING_INVALIDATION" if name == "ETF" else None
                                ),
                            }
                        ],
                    },
                    {
                        "unit": {
                            "period_start": units[1]["period_start"],
                            "period_end": units[1]["period_end"],
                        },
                        "features": [{"case_id": f"{name}-second"}],
                        "outcomes": [
                            {
                                "status": "COMPLETE",
                                "r_metrics_status": "AVAILABLE",
                                "r_metrics_reason": None,
                            }
                        ],
                    },
                ],
            }
        )
    fx_output = next(
        item for item in outputs if item["asset_key"] == "FX:X"
    )
    fx_output["skip_reason_code"] = "NO_GAP_SAFE_220_OBSERVATION_HISTORY"
    fx_output["unit_results"] = []
    outputs.append(
        {
            "asset_key": "CRYPTO:NO-DATA",
            "skip_reason_code": "EXPECTED_NO_DEVELOPMENT_DATA",
            "gap_boundary_count": 0,
            "unit_results": [],
        }
    )
    sample = {"assets": assets, "units": units}

    counters, gates = benchmark._technical_coverage(outputs=outputs, sample=sample)

    assert all(gates.values())
    assert counters["r_unavailable_cases"] == 1
    assert counters["structural_r_na_reason_counts"] == {"MISSING_INVALIDATION": 1}
    assert counters["no_data_asset_results"] == 1
    assert counters["gap_safe_history_unavailable_asset_results"] == 1
    assert counters["classified_asset_classes"] == [
        "CRYPTO",
        "EQUITIES",
        "ETF",
        "FX",
    ]
    assert counters["distinct_periods_with_cases"] == 2
    assert counters["distinct_positive_history_lengths"] == 4
    assert counters["history_length_observation_spread"] == 800
    outputs[0]["gap_boundary_count"] = 0
    _counters, failed = benchmark._technical_coverage(outputs=outputs, sample=sample)
    assert failed["known_gap_asset_exercised"] is False
    assert failed["input_gap_censoring_exercised"] is True

    outputs[1]["unit_results"][0]["outcomes"][0][
        "r_metrics_reason"
    ] = "NO_REFERENCE_ENTRY"
    _counters, failed = benchmark._technical_coverage(outputs=outputs, sample=sample)
    assert failed["structural_r_na_exercised"] is False

    outputs[1]["unit_results"][0]["outcomes"][0][
        "r_metrics_reason"
    ] = "MISSING_INVALIDATION"
    for output in outputs[:-1]:
        output["coverage"]["active_valid_bars"] = 1000
    _counters, failed = benchmark._technical_coverage(outputs=outputs, sample=sample)
    assert failed["different_history_lengths_exercised"] is False


def test_configuration_evidence_requires_cpu_ram_writer_and_technical_gates() -> None:
    complete = _configuration(2, 5.0)
    assert all(benchmark.configuration_evidence_checks(complete).values())

    incomplete = dict(complete)
    incomplete.pop("peak_ram_upper_bound_bytes")
    checks = benchmark.configuration_evidence_checks(incomplete)
    assert checks["ram_recorded"] is False

    no_gap = dict(complete)
    no_gap["technical_coverage_gates"] = dict(
        complete["technical_coverage_gates"]
    )
    no_gap["technical_coverage_gates"]["input_gap_censoring_exercised"] = False
    checks = benchmark.configuration_evidence_checks(no_gap)
    assert checks["all_technical_gates_pass"] is False

    malformed = dict(complete)
    malformed["worker_count"] = "two"
    malformed["technical_coverage_gates"] = "not-a-mapping"
    checks = benchmark.configuration_evidence_checks(malformed)
    assert checks["worker_count_positive"] is False
    assert checks["all_technical_gates_present"] is False


def test_artifact_falls_back_to_reference_when_worker_payloads_differ(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        benchmark,
        "system_resources",
        lambda: {"logical_cpu_count": 4, "total_physical_memory_bytes": 16 * 1024**3},
    )
    monkeypatch.setattr(benchmark, "eligible_worker_counts", lambda resources: (1, 2))
    monkeypatch.setattr(
        benchmark,
        "fixed_benchmark_sample",
        lambda universe: {
            "sample_fingerprint": "sample-fp",
            "assets": [],
            "units": [],
            "units_by_asset": {},
        },
    )
    monkeypatch.setattr(
        benchmark,
        "run_worker_configuration",
        lambda *, worker_count, **kwargs: _configuration(
            worker_count, 1.0, digest=f"digest-{worker_count}"
        ),
    )
    output = tmp_path / "benchmark.json"
    runtime = _safe_runtime(monkeypatch, tmp_path)
    artifact = benchmark.run_v6_worker_benchmark(
        contract=_contract(),
        universe={},
        input_precheck_fingerprint=str(
            _TEST_INPUT_PRECHECK["artifact_fingerprint"]
        ),
        output_path=output,
        created_at="2026-09-05T00:00:00+00:00",
        **runtime,
    )
    assert artifact["status"] == "PASS"
    assert artifact["selected_worker_count"] == 1
    assert artifact["deterministic_payloads_equal"] is False
    assert artifact["fallback_to_one_worker"] is True
    assert artifact["selection_candidate_worker_counts"] == [1]
    assert artifact["worker_input_precheck_artifact"] == {
        "path": "runtime/input-precheck-v1-r2.json",
        "artifact_fingerprint": _TEST_INPUT_PRECHECK["artifact_fingerprint"],
    }
    assert artifact["excluded_multi_worker_configurations"][0]["worker_count"] == 2
    assert "SCIENTIFIC_DIGEST_DIFFERS_FROM_ONE_WORKER_REFERENCE" in artifact[
        "excluded_multi_worker_configurations"
    ][0]["reasons"]
    stored = json.loads(output.read_text(encoding="utf-8"))
    expected = stored.pop("artifact_fingerprint")
    assert expected == fingerprint(stored)


def test_artifact_falls_back_to_reference_when_multi_worker_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        benchmark,
        "system_resources",
        lambda: {"logical_cpu_count": 4, "total_physical_memory_bytes": 16 * 1024**3},
    )
    monkeypatch.setattr(benchmark, "eligible_worker_counts", lambda resources: (1, 2))
    monkeypatch.setattr(
        benchmark,
        "fixed_benchmark_sample",
        lambda universe: {
            "sample_fingerprint": "sample-fp",
            "assets": [],
            "units": [],
            "units_by_asset": {},
        },
    )

    def configuration(*, worker_count: int, **kwargs: object) -> dict[str, object]:
        result = _configuration(worker_count, 1.0)
        if worker_count == 2:
            result["status"] = "FAIL"
            result["errors"] = [{"error_class": "Synthetic", "error": "failed"}]
        return result

    monkeypatch.setattr(benchmark, "run_worker_configuration", configuration)
    runtime = _safe_runtime(monkeypatch, tmp_path)
    artifact = benchmark.run_v6_worker_benchmark(
        contract=_contract(),
        universe={},
        input_precheck_fingerprint=str(
            _TEST_INPUT_PRECHECK["artifact_fingerprint"]
        ),
        output_path=tmp_path / "benchmark-fallback.json",
        **runtime,
    )
    assert artifact["status"] == "PASS"
    assert artifact["selected_worker_count"] == 1
    assert artifact["fallback_to_one_worker"] is True
    assert artifact["all_configuration_evidence_complete"] is False
    assert "CONFIGURATION_EVIDENCE_FAILED:configuration_status_pass" in artifact[
        "excluded_multi_worker_configurations"
    ][0]["reasons"]


def test_artifact_fails_when_mandatory_reference_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        benchmark,
        "system_resources",
        lambda: {"logical_cpu_count": 4, "total_physical_memory_bytes": 16 * 1024**3},
    )
    monkeypatch.setattr(benchmark, "eligible_worker_counts", lambda resources: (1, 2))
    monkeypatch.setattr(
        benchmark,
        "fixed_benchmark_sample",
        lambda universe: {
            "sample_fingerprint": "sample-fp",
            "assets": [],
            "units": [],
            "units_by_asset": {},
        },
    )

    def configuration(*, worker_count: int, **kwargs: object) -> dict[str, object]:
        result = _configuration(worker_count, 1.0)
        if worker_count == 1:
            result["status"] = "FAIL"
        return result

    monkeypatch.setattr(benchmark, "run_worker_configuration", configuration)
    runtime = _safe_runtime(monkeypatch, tmp_path)
    artifact = benchmark.run_v6_worker_benchmark(
        contract=_contract(),
        universe={},
        input_precheck_fingerprint=str(
            _TEST_INPUT_PRECHECK["artifact_fingerprint"]
        ),
        output_path=tmp_path / "benchmark-reference-fail.json",
        **runtime,
    )
    assert artifact["status"] == "FAIL"
    assert artifact["selected_worker_count"] is None
    assert artifact["reference_configuration_passed"] is False


def test_artifact_records_identical_payload_and_single_writer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(benchmark, "system_resources", lambda: {"logical_cpu_count": 12})
    monkeypatch.setattr(benchmark, "eligible_worker_counts", lambda resources: (1, 2, 4))
    monkeypatch.setattr(
        benchmark,
        "fixed_benchmark_sample",
        lambda universe: {
            "sample_fingerprint": "sample-fp",
            "assets": [],
            "units": [],
            "units_by_asset": {},
        },
    )
    monkeypatch.setattr(
        benchmark,
        "run_worker_configuration",
        lambda *, worker_count, **kwargs: _configuration(
            worker_count, {1: 10.0, 2: 6.0, 4: 5.6}[worker_count]
        ),
    )
    runtime = _safe_runtime(monkeypatch, tmp_path)
    artifact = benchmark.run_v6_worker_benchmark(
        contract=_contract(),
        universe={},
        input_precheck_fingerprint=str(
            _TEST_INPUT_PRECHECK["artifact_fingerprint"]
        ),
        output_path=tmp_path / "benchmark.json",
        **runtime,
    )
    assert artifact["status"] == "PASS"
    assert artifact["deterministic_payloads_equal"] is True
    assert artifact["selected_worker_count"] == 2
    assert artifact["sqlite_writer_count"] == 1
    assert artifact["benchmark_used_for_research_selection"] is False


def test_scientific_digest_distinguishes_terminal_skip_evidence() -> None:
    shared = {
        "asset_key": "FX:EUR/USD",
        "input_projection_fingerprint": "projection",
        "combined_input_fingerprint": "combined",
        "gap_boundary_count": 4,
        "coverage": {"active_valid_bars": 100},
        "unit_ids": ["u1", "u2"],
        "unit_results": [],
        "skip_reason": "terminal skip",
    }
    no_data = {**shared, "skip_reason_code": "EXPECTED_NO_DEVELOPMENT_DATA"}
    no_gap_safe = {
        **shared,
        "skip_reason_code": "NO_GAP_SAFE_220_OBSERVATION_HISTORY",
    }

    assert benchmark.result_scientific_digest(no_data) != (
        benchmark.result_scientific_digest(no_gap_safe)
    )
    changed_units = {**no_gap_safe, "unit_ids": ["u1", "u3"]}
    assert benchmark.result_scientific_digest(no_gap_safe) != (
        benchmark.result_scientific_digest(changed_units)
    )
    technical_only = {**no_gap_safe, "run_id": "other", "wall_seconds": 99.0}
    assert benchmark.result_scientific_digest(no_gap_safe) == (
        benchmark.result_scientific_digest(technical_only)
    )


def test_skipped_asset_must_return_exact_unique_work_unit_set() -> None:
    result = {"unit_ids": ["u2", "u1"]}
    assert benchmark._validated_skipped_unit_ids(result, ["u1", "u2"]) == [
        "u2",
        "u1",
    ]
    for invalid in ({}, {"unit_ids": ["u1"]}, {"unit_ids": ["u1", "u1"]}):
        with pytest.raises(benchmark.DevelopmentV6BenchmarkError):
            benchmark._validated_skipped_unit_ids(invalid, ["u1", "u2"])


def test_receipt_connection_closes_before_temporary_directory_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class Cursor:
        def fetchone(self) -> tuple[int]:
            return (7,)

    class Connection:
        def execute(self, statement: str) -> Cursor:
            assert statement == "SELECT COUNT(*) FROM unit_receipts"
            events.append("receipt_query")
            return Cursor()

        def close(self) -> None:
            events.append("connection_closed")

    monkeypatch.setattr(
        benchmark.sqlite3,
        "connect",
        lambda path: Connection(),
    )

    assert benchmark._read_receipt_count(Path("control.sqlite3")) == 7
    events.append("temporary_directory_cleanup")

    assert events == [
        "receipt_query",
        "connection_closed",
        "temporary_directory_cleanup",
    ]


def test_benchmark_requires_explicit_worker_input_precheck_binding(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        benchmark.DevelopmentV6BenchmarkError,
        match="explicitly bind input_precheck_artifact",
    ):
        benchmark.run_v6_worker_benchmark(
            contract=_contract(),
            universe={},
            input_precheck_fingerprint=str(
                _TEST_INPUT_PRECHECK["artifact_fingerprint"]
            ),
            descriptive_plan=_descriptive_plan(),
            output_path=tmp_path / "never.json",
            process_lock_path=tmp_path / "benchmark.lock",
            global_research_lock_path=tmp_path / "research.lock",
            project_root=tmp_path,
        )
    assert not (tmp_path / "never.json").exists()


def test_benchmark_rejects_worker_input_precheck_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        benchmark.DevelopmentV6BenchmarkError,
        match="does not match the declared PASS artifact fingerprint",
    ):
        benchmark.run_v6_worker_benchmark(
            contract=_contract(),
            universe={},
            input_precheck_fingerprint="f" * 64,
            descriptive_plan=_descriptive_plan(),
            compute_paths=_input_compute_paths(tmp_path),
            output_path=tmp_path / "never.json",
            process_lock_path=tmp_path / "benchmark.lock",
            global_research_lock_path=tmp_path / "research.lock",
            project_root=tmp_path,
        )
    assert not (tmp_path / "never.json").exists()


def test_benchmark_refuses_compute_when_protected_runtime_is_active(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        benchmark,
        "system_resources",
        lambda: {"logical_cpu_count": 2, "total_physical_memory_bytes": 8 * 1024**3},
    )
    monkeypatch.setattr(benchmark, "eligible_worker_counts", lambda resources: (1,))
    monkeypatch.setattr(
        benchmark,
        "fixed_benchmark_sample",
        lambda universe: {
            "sample_fingerprint": "sample-fp",
            "assets": [],
            "units": [],
            "units_by_asset": {},
        },
    )
    monkeypatch.setattr(
        benchmark,
        "benchmark_dispatch_readiness",
        lambda **kwargs: (False, "ACTIVE_PRODUCTION_JOB:test", {}),
    )
    compute_called = False

    def compute(**kwargs: object) -> dict[str, object]:
        nonlocal compute_called
        compute_called = True
        return _configuration(1, 1.0)

    monkeypatch.setattr(benchmark, "run_worker_configuration", compute)
    output = tmp_path / "blocked.json"
    with pytest.raises(benchmark.DevelopmentV6BenchmarkError, match="protected runtime"):
        benchmark.run_v6_worker_benchmark(
            contract=_contract(),
            universe={},
            input_precheck_fingerprint=str(
                _TEST_INPUT_PRECHECK["artifact_fingerprint"]
            ),
            descriptive_plan=_descriptive_plan(),
            compute_paths=_input_compute_paths(tmp_path),
            created_at="2026-09-05T00:00:00+00:00",
            output_path=output,
            process_lock_path=tmp_path / "benchmark.lock",
            global_research_lock_path=tmp_path / "research.lock",
            fx_observer_lock_path=tmp_path / "fx.lock",
            production_protection_config=tmp_path / "unused.json",
            project_root=tmp_path,
        )
    assert compute_called is False
    assert not output.exists()


def test_global_lock_collision_releases_process_lock(
    tmp_path: Path,
) -> None:
    global_lock = benchmark.SwingRunLock(tmp_path / "research.lock")
    global_lock.acquire()
    try:
        with pytest.raises(benchmark.DevelopmentV6BenchmarkError, match="Global"):
            benchmark.run_v6_worker_benchmark(
                contract=_contract(),
                universe={},
                input_precheck_fingerprint=str(
                    _TEST_INPUT_PRECHECK["artifact_fingerprint"]
                ),
                descriptive_plan=_descriptive_plan(),
                compute_paths=_input_compute_paths(tmp_path),
                output_path=tmp_path / "never.json",
                process_lock_path=tmp_path / "benchmark.lock",
                global_research_lock_path=tmp_path / "research.lock",
                project_root=tmp_path,
            )
        process_probe = benchmark.SwingRunLock(tmp_path / "benchmark.lock")
        process_probe.acquire()
        process_probe.release()
    finally:
        global_lock.release()


def test_immutable_publication_detects_parallel_divergence_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "benchmark.json"

    def collide(source: Path, destination: Path) -> None:
        Path(destination).write_text('{"different": true}\n', encoding="utf-8")
        raise FileExistsError

    monkeypatch.setattr(benchmark.os, "link", collide)
    with pytest.raises(benchmark.DevelopmentV6BenchmarkError, match="Parallel"):
        benchmark._write_immutable(output, {"expected": True})
    assert list(tmp_path.glob(".*.tmp")) == []
