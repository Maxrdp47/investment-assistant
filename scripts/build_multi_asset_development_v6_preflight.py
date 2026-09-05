from __future__ import annotations

"""Build the final Development-v6 start gate from explicit verification evidence."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_v6_preflight import (  # noqa: E402
    DEFAULT_CONTRACT_ARTIFACT,
    DEFAULT_CONTRACT_DIFF,
    build_start_gate,
)


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} is not readable JSON: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} must be a JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the frozen Development-v6 contract, inputs, resources, Git, "
            "local gates, CI and scheduler contract. A canonical artifact is "
            "written only for a complete PASS."
        )
    )
    parser.add_argument("--local-gates-json", type=Path, required=True)
    parser.add_argument("--ci-evidence-json", type=Path, required=True)
    parser.add_argument("--scheduler-evidence-json", type=Path, required=True)
    parser.add_argument("--environment-json", type=Path)
    parser.add_argument("--operational-observations-json", type=Path)
    parser.add_argument("--contract-artifact", type=Path, default=DEFAULT_CONTRACT_ARTIFACT)
    parser.add_argument("--contract-diff", type=Path, default=DEFAULT_CONTRACT_DIFF)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "multi_asset_discovery_development_v6.json")
    parser.add_argument("--input-precheck", type=Path)
    parser.add_argument("--worker-benchmark", type=Path)
    parser.add_argument("--descriptive-plan", type=Path)
    parser.add_argument("--artifact-path", type=Path)
    parser.add_argument("--created-at")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate and print the report without writing even when it passes.",
    )
    args = parser.parse_args()

    payload = build_start_gate(
        contract_artifact_path=args.contract_artifact,
        contract_diff_path=args.contract_diff,
        local_gate_results=_json_object(
            args.local_gates_json, label="local-gate evidence"
        ),
        ci_evidence=_json_object(args.ci_evidence_json, label="CI evidence"),
        scheduler_evidence=_json_object(
            args.scheduler_evidence_json, label="scheduler evidence"
        ),
        config_path=args.config,
        project_root=PROJECT_ROOT,
        input_precheck_path=args.input_precheck,
        worker_benchmark_path=args.worker_benchmark,
        descriptive_plan_path=args.descriptive_plan,
        environment_snapshot=(
            _json_object(args.environment_json, label="environment snapshot")
            if args.environment_json
            else None
        ),
        operational_observations=(
            _json_object(
                args.operational_observations_json,
                label="operational observations",
            )
            if args.operational_observations_json
            else None
        ),
        artifact_path=args.artifact_path,
        created_at=args.created_at,
        persist=not args.dry_run,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
