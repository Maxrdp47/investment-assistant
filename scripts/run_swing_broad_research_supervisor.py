from __future__ import annotations

"""Run safe Broad-Research batches back-to-back outside production windows."""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from time import monotonic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_swing_broad_research import (  # noqa: E402
    DEFAULT_FIXED_MANIFEST,
    _campaign_status,
)
from swing_broad_research import (  # noqa: E402
    DEFAULT_BROAD_RESEARCH_DB_PATH,
    completed_broad_research_symbols,
)
from swing_research_dataset import load_research_dataset_manifest  # noqa: E402
from swing_universe import DEFAULT_SWING_UNIVERSE_PATH, load_swing_universe  # noqa: E402
from swing_walk_forward_campaign import (  # noqa: E402
    historical_research_runtime_gate,
)


DEFAULT_BROAD_WORKERS = 6
DEFAULT_ASSETS_PER_BATCH = 32


def broad_supervisor_guard(now: datetime) -> dict[str, object]:
    """Return a read-only decision; the child runner repeats the same gates."""

    campaign, config, _, _ = _campaign_status(now)
    if int(campaign.get("jobs_pending") or 0) > 0:
        return {
            "run_allowed": False,
            "reason": "existing_campaign_not_finished",
            "campaign": campaign,
        }
    runtime_gate = historical_research_runtime_gate(
        config,
        project_root=PROJECT_ROOT,
    )
    if not runtime_gate["run_allowed"]:
        return {
            "run_allowed": False,
            "reason": "blocked_real_conflict",
            "runtime_gate": runtime_gate,
        }
    return {"run_allowed": True, "reason": "clear", "runtime_gate": runtime_gate}


def broad_progress(
    *,
    manifest_path: Path,
    database_path: Path,
    universe_path: Path,
) -> dict[str, object]:
    manifest = load_research_dataset_manifest(manifest_path)
    dataset_fingerprint = str(manifest["dataset_fingerprint"])
    universe = load_swing_universe(universe_path)
    if universe.errors:
        raise RuntimeError("; ".join(universe.errors))
    expected_assets = len([asset for asset in universe.assets if asset.active])
    completed_assets = len(
        completed_broad_research_symbols(
            dataset_fingerprint=dataset_fingerprint,
            path=database_path,
        )
    )
    return {
        "asset_completions": completed_assets,
        "expected_assets": expected_assets,
        "remaining_assets": max(0, expected_assets - completed_assets),
        "completion_pct": round(
            completed_assets / expected_assets * 100 if expected_assets else 100.0,
            4,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sicherer Broad-Research-Supervisor ohne Leerlauf zwischen den "
            "kleinen Resume-Blöcken."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FIXED_MANIFEST)
    parser.add_argument("--database", type=Path, default=DEFAULT_BROAD_RESEARCH_DB_PATH)
    parser.add_argument("--universe", type=Path, default=DEFAULT_SWING_UNIVERSE_PATH)
    parser.add_argument("--workers", type=int, default=DEFAULT_BROAD_WORKERS)
    parser.add_argument(
        "--maximum-assets-per-batch",
        type=int,
        default=DEFAULT_ASSETS_PER_BATCH,
    )
    parser.add_argument(
        "--maximum-batches",
        type=int,
        default=None,
        help="Optionales Diagnose-Limit; standardmäßig bis zum nächsten Schutzgate.",
    )
    args = parser.parse_args()

    workers = int(args.workers)
    assets_per_batch = int(args.maximum_assets_per_batch)
    if not 1 <= workers <= 8:
        parser.error("--workers muss zwischen 1 und 8 liegen.")
    if not 1 <= assets_per_batch <= 64:
        parser.error("--maximum-assets-per-batch muss zwischen 1 und 64 liegen.")
    if args.maximum_batches is not None and int(args.maximum_batches) < 1:
        parser.error("--maximum-batches muss mindestens 1 sein.")

    batches = 0
    while True:
        before = broad_progress(
            manifest_path=args.manifest,
            database_path=args.database,
            universe_path=args.universe,
        )
        print(
            json.dumps(
                {"broad_supervisor": "progress", **before},
                ensure_ascii=False,
            ),
            flush=True,
        )
        if int(before["remaining_assets"]) == 0:
            print(
                json.dumps(
                    {"broad_supervisor": "complete", **before},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return 0
        if args.maximum_batches is not None and batches >= int(args.maximum_batches):
            print(
                json.dumps(
                    {"broad_supervisor": "batch_limit_reached", **before},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return 0

        guard = broad_supervisor_guard(datetime.now().astimezone())
        if not bool(guard["run_allowed"]):
            print(
                json.dumps(
                    {"broad_supervisor": "paused", **guard, **before},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return 0

        batch_assets = min(assets_per_batch, int(before["remaining_assets"]))
        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_swing_broad_research.py"),
            "--automatic-handoff",
            "--workers",
            str(workers),
            "--maximum-assets",
            str(batch_assets),
            "--manifest",
            str(args.manifest),
            "--database",
            str(args.database),
            "--universe",
            str(args.universe),
        ]
        started = monotonic()
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        elapsed_seconds = round(monotonic() - started, 2)
        if result.returncode != 0:
            print(
                json.dumps(
                    {
                        "broad_supervisor": "child_failed",
                        "returncode": result.returncode,
                        "elapsed_seconds": elapsed_seconds,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return int(result.returncode)

        after = broad_progress(
            manifest_path=args.manifest,
            database_path=args.database,
            universe_path=args.universe,
        )
        progress_delta = int(after["asset_completions"]) - int(before["asset_completions"])
        print(
            json.dumps(
                {
                    "broad_supervisor": "batch_complete",
                    "workers": workers,
                    "scheduled_assets": batch_assets,
                    "processed_assets": progress_delta,
                    "elapsed_seconds": elapsed_seconds,
                    **after,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if progress_delta <= 0:
            print(
                json.dumps(
                    {
                        "broad_supervisor": "paused_without_progress",
                        "reason": "child_gate_or_lock",
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return 0
        batches += 1


if __name__ == "__main__":
    raise SystemExit(main())
