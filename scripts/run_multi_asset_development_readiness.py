from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_readiness import (  # noqa: E402
    READY_STATUS,
    evaluate_multi_asset_development_readiness,
)
from multi_asset_discovery_v1 import (  # noqa: E402
    load_discovery_contract,
    verify_contract_freeze,
)


EXPORTS = PROJECT_ROOT / "runtime" / "research_exports"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _quick_check(path: Path) -> str:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return str(connection.execute("PRAGMA quick_check").fetchone()[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freeze",
        type=Path,
        default=EXPORTS
        / "multi_asset_discovery_v1_contract_freeze_2026-09-01-v1-implementation-r5.json",
    )
    parser.add_argument(
        "--pilot",
        type=Path,
        default=EXPORTS
        / "multi_asset_discovery_v1_integrity_pilot_2026-09-01-v1-authoritative-r5.json",
    )
    parser.add_argument(
        "--fx-remediation",
        type=Path,
        default=EXPORTS / "fx_historical_pit_remediation_2026-09-01-v2.json",
    )
    parser.add_argument(
        "--historical-dependency",
        type=Path,
        default=EXPORTS / "historical_dependency_policy_2026-09-01-v1.json",
    )
    parser.add_argument(
        "--identity-precheck",
        type=Path,
        default=EXPORTS / "multi_asset_final_precheck_2026-08-31-v1.json",
    )
    parser.add_argument(
        "--fx-observer",
        type=Path,
        default=EXPORTS / "fx_pit_scheduler_audit_2026-08-31-v3.json",
    )
    parser.add_argument(
        "--fx-active-store",
        type=Path,
        default=PROJECT_ROOT / "runtime" / "fx_historical_pit_2026-09-01-v2.sqlite3",
    )
    parser.add_argument(
        "--fx-forward-store",
        type=Path,
        default=PROJECT_ROOT / "runtime" / "fx_forward_pit.sqlite3",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=EXPORTS
        / "multi_asset_final_development_readiness_2026-09-01-v1.json",
    )
    parser.add_argument("--at")
    args = parser.parse_args()

    contract = load_discovery_contract()
    freeze = _json(args.freeze)
    forward_before = args.fx_forward_store.stat().st_mtime_ns
    result = evaluate_multi_asset_development_readiness(
        contract=contract,
        expected_contract_fingerprint=(
            "68994e462f90e2a4f1ad4adbdc858cc43fb0ddb85b0c2662d0f647e1dfa6c05a"
        ),
        freeze_valid=verify_contract_freeze(freeze),
        pilot=_json(args.pilot),
        fx_remediation=_json(args.fx_remediation),
        historical_dependency=_json(args.historical_dependency),
        identity_precheck=_json(args.identity_precheck),
        fx_observer=_json(args.fx_observer),
        database_integrity={
            "fx_active_v2": _quick_check(args.fx_active_store),
            "fx_forward": _quick_check(args.fx_forward_store),
        },
        protected_sources_unchanged=(
            args.fx_forward_store.stat().st_mtime_ns == forward_before
        ),
    )
    result.update(
        {
            "created_at": args.at or datetime.now(timezone.utc).isoformat(),
            "contract_fingerprint": contract["contract_fingerprint"],
            "freeze_fingerprint": freeze["freeze_fingerprint"],
            "pilot_fingerprint": _json(args.pilot)["pilot_fingerprint"],
            "fx_dataset_fingerprint": _json(args.fx_remediation)[
                "dataset_fingerprint"
            ],
            "historical_dependency_policy_fingerprint": _json(
                args.historical_dependency
            )["policy"]["policy_fingerprint"],
        }
    )
    result.pop("gate_fingerprint", None)
    result["gate_fingerprint"] = __import__(
        "multi_asset_development_readiness"
    ).fingerprint(result)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        existing = _json(args.output)
        if existing != result:
            raise RuntimeError(f"Append-only-Artefakt weicht ab: {args.output}")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["status"] == READY_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())

