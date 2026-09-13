from __future__ import annotations

"""CLI for the immutable Development-v7 recovery lifecycle."""

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_v7_recovery import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    PILOT_VERSION,
    ROOT_CAUSE_VERSION,
    SCHEDULER_SMOKE_VERSION,
    DevelopmentV7RecoveryError,
    _git,
    _read_json,
    _write_immutable,
    build_recovery_contract,
    build_root_cause_report,
    inspect_reuse_candidates,
    load_recovery_config,
    prepare_recovery,
    recovery_paths,
    run_recovery_pilot,
    scheduler_store_smoke,
    verify_self_fingerprint,
)
from multi_asset_development_v7_runner import (  # noqa: E402
    advance_chain,
    dispatch_readiness,
    read_chain_status,
)
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock  # noqa: E402


GLOBAL_RESEARCH_LOCK = PROJECT_ROOT / "runtime" / "swing_walk_forward_research.lock"


def _scheduler_bootstrap() -> dict[str, object]:
    config = load_recovery_config(DEFAULT_CONFIG_PATH)
    paths = recovery_paths(config, project_root=PROJECT_ROOT)
    clear, reason, detail = dispatch_readiness(config, paths)
    if not clear:
        return {
            "status": "WAITING_FOR_SAFE_RESEARCH_WINDOW",
            "reason": reason,
            "detail": detail,
        }
    lock = SwingRunLock(GLOBAL_RESEARCH_LOCK)
    try:
        lock.acquire()
    except SwingRunAlreadyActiveError:
        return {"status": "WAITING_FOR_GLOBAL_RESEARCH_LOCK"}
    try:
        current_commit = _git("rev-parse", "HEAD", project_root=PROJECT_ROOT)
        if paths["scheduler_smoke_report"].is_file():
            smoke = _read_json(paths["scheduler_smoke_report"])
            if (
                smoke.get("version") != SCHEDULER_SMOKE_VERSION
                or smoke.get("status") != "PASS"
                or smoke.get("commit") != current_commit
                or not verify_self_fingerprint(smoke)
            ):
                raise DevelopmentV7RecoveryError(
                    "Existing scheduler smoke does not bind the current commit."
                )
        else:
            smoke = scheduler_store_smoke(paths["scheduler_smoke_directory"])
            _write_immutable(paths["scheduler_smoke_report"], smoke)
        pilot = run_recovery_pilot(config, project_root=PROJECT_ROOT)
        _write_immutable(paths["pilot_report"], pilot)
        status = "PASS" if smoke["status"] == pilot["status"] == "PASS" else "FAIL"
        return {
            "status": status,
            "commit": current_commit,
            "identity": os.environ.get("USERNAME"),
            "working_directory": os.getcwd(),
            "scheduler_smoke": smoke,
            "pilot": pilot,
        }
    finally:
        lock.release()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare, run, or inspect Development-v7 recovery."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--status", action="store_true")
    action.add_argument("--root-cause", action="store_true")
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--scheduler-bootstrap", action="store_true")
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--advance", action="store_true")
    parser.add_argument("--ci-run-url")
    parser.add_argument("--ci-conclusion")
    parser.add_argument("--maximum-asset-batches", type=int)
    args = parser.parse_args()
    if args.maximum_asset_batches is not None and args.maximum_asset_batches <= 0:
        parser.error("--maximum-asset-batches must be positive")
    if args.prepare and (not args.ci_run_url or not args.ci_conclusion):
        parser.error("--prepare requires --ci-run-url and --ci-conclusion")
    try:
        if args.status:
            payload = read_chain_status()
        elif args.root_cause:
            config = load_recovery_config(DEFAULT_CONFIG_PATH)
            paths = recovery_paths(config, project_root=PROJECT_ROOT)
            payload = build_root_cause_report(config, project_root=PROJECT_ROOT)
            _write_immutable(paths["root_cause_report"], payload)
        elif args.preflight:
            config = load_recovery_config(DEFAULT_CONFIG_PATH)
            contract, diff = build_recovery_contract(config, project_root=PROJECT_ROOT)
            payload = {
                "status": "PASS"
                if contract["research_semantics_diff_count"] == 0
                else "FAIL",
                "recovery_contract": contract,
                "contract_diff": diff,
                "reuse": inspect_reuse_candidates(config, project_root=PROJECT_ROOT),
            }
        elif args.scheduler_bootstrap:
            payload = _scheduler_bootstrap()
        elif args.prepare:
            payload = prepare_recovery(
                ci_run_url=args.ci_run_url,
                ci_conclusion=args.ci_conclusion,
            )
        else:
            payload = advance_chain(maximum_asset_batches=args.maximum_asset_batches)
    except Exception as exc:
        payload = {
            "status": "V7_RECOVERY_BLOCKED_BEFORE_START",
            "error_class": type(exc).__name__,
            "error": str(exc),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if payload.get("status") in {
        "V7_RECOVERY_BLOCKED_BEFORE_START",
        "PAUSED_REQUIRES_REVIEW",
        "FAIL",
    }:
        return 2
    if str(payload.get("status", "")).startswith("WAITING_"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
