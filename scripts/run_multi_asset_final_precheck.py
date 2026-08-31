from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_final_precheck import evaluate_multi_asset_final_precheck  # noqa: E402
from swing_research_identity_v3 import validate_listing_scoped_bundle_v3  # noqa: E402


EXPORT_ROOT = PROJECT_ROOT / "runtime" / "research_exports"
DEFAULT_IDENTITY = EXPORT_ROOT / "research_identity_registry_2026-08-30-v2.json"
DEFAULT_RECLASSIFICATION = (
    EXPORT_ROOT / "failed_seller_dependency_reclassification_2026-08-30-v2.json"
)
DEFAULT_SCHEDULER = EXPORT_ROOT / "fx_pit_scheduler_audit_2026-08-31-v3.json"
DEFAULT_HISTORICAL_FX = EXPORT_ROOT / "fx_historical_pit_2026-08-29-v1.json"
DEFAULT_KB_SYNC = (
    EXPORT_ROOT / "failed_seller_dependency_reclassification_kb_sync_2026-08-31-v1.json"
)
DEFAULT_BUYER_FREEZE = (
    EXPORT_ROOT / "buyer_confirmation_challenger_freeze_2026-08-26-v1.json"
)
DEFAULT_BUYER_DECISION = (
    EXPORT_ROOT / "buyer_confirmation_validation_decision_2026-08-26-v1.json"
)
DEFAULT_FAILED_SELLER = EXPORT_ROOT / "failed_seller_development_2026-08-28-v1.json"
DEFAULT_OUTPUT = EXPORT_ROOT / "multi_asset_final_precheck_2026-08-31-v1.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _snapshot_unchanged(snapshot: dict[str, object]) -> bool:
    path = Path(str(snapshot["path"]))
    stat = path.stat()
    return stat.st_size == int(snapshot["size"]) and stat.st_mtime_ns == int(
        snapshot["mtime_ns"]
    )


def run(args: argparse.Namespace) -> dict[str, object]:
    paths = {
        "identity": Path(args.identity),
        "reclassification": Path(args.reclassification),
        "scheduler": Path(args.scheduler),
        "historical_fx": Path(args.historical_fx),
        "kb_sync": Path(args.kb_sync),
        "buyer_freeze": Path(args.buyer_freeze),
        "buyer_decision": Path(args.buyer_decision),
        "failed_seller": Path(args.failed_seller),
    }
    loaded = {name: _load(path) for name, path in paths.items()}
    freeze = loaded["buyer_freeze"]
    snapshots = dict(freeze["source_snapshots"])
    buyer_decision = loaded["buyer_decision"]
    reclassification = loaded["reclassification"]
    research_integrity = {
        "broad_v1_snapshot_unchanged": _snapshot_unchanged(dict(snapshots["broad_v1"])),
        "frozen_dataset_manifest_unchanged": _sha256(
            Path(str(dict(snapshots["dataset_manifest"])["path"]))
        )
        == dict(snapshots["dataset_manifest"])["sha256"],
        "buyer_development_artifact_unchanged": _sha256(
            Path(str(dict(snapshots["development_report"])["path"]))
        )
        == dict(snapshots["development_report"])["sha256"],
        "buyer_validation_terminal_and_holdout_closed": buyer_decision.get("status")
        == "VALIDATION_FAIL"
        and buyer_decision.get("next_stage_allowed") is False
        and buyer_decision.get("production_changed") is False,
        "failed_seller_original_report_unchanged": _sha256(paths["failed_seller"])
        == dict(reclassification["input_artifacts"])["original_report_sha256"],
        "listing_bundle_guard_present": callable(validate_listing_scoped_bundle_v3),
    }
    result = evaluate_multi_asset_final_precheck(
        identity=loaded["identity"],
        reclassification=reclassification,
        scheduler=loaded["scheduler"],
        historical_fx=loaded["historical_fx"],
        kb_sync=loaded["kb_sync"],
        research_integrity=research_integrity,
    )
    result.update(
        {
            "created_at": args.at or datetime.now(timezone.utc).isoformat(),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": _git("rev-parse", "HEAD"),
            "command": "python " + " ".join(sys.argv),
            "code_fingerprint": _sha256(Path(__file__))[:64],
            "identity_registry_fingerprint": loaded["identity"]["registry_fingerprint"],
            "mapping_fingerprint": loaded["identity"]["mapping_fingerprint"],
            "dependency_method": reclassification["dependency_method"],
            "input_artifacts": {
                name: {"path": str(path.resolve()), "sha256": _sha256(path)}
                for name, path in paths.items()
            },
        }
    )
    result["output_digest"] = hashlib.sha256(
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    output = Path(args.output)
    if output.exists():
        raise RuntimeError(f"Append-only precheck artifact already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final read-only Multi-Asset precheck")
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--reclassification", type=Path, default=DEFAULT_RECLASSIFICATION)
    parser.add_argument("--scheduler", type=Path, default=DEFAULT_SCHEDULER)
    parser.add_argument("--historical-fx", type=Path, default=DEFAULT_HISTORICAL_FX)
    parser.add_argument("--kb-sync", type=Path, default=DEFAULT_KB_SYNC)
    parser.add_argument("--buyer-freeze", type=Path, default=DEFAULT_BUYER_FREEZE)
    parser.add_argument("--buyer-decision", type=Path, default=DEFAULT_BUYER_DECISION)
    parser.add_argument("--failed-seller", type=Path, default=DEFAULT_FAILED_SELLER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--at")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
