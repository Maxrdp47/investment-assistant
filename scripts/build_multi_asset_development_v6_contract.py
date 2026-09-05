from __future__ import annotations

"""Check or append-only freeze the gated Multi-Asset Development v6 contract.

The default mode is read-only.  ``--write`` is deliberately explicit and is
accepted only from a clean committed worktree after all three prerequisite
artifacts validate.  This script never starts Development or a scheduler task.
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_v6_contract import (  # noqa: E402
    DEFAULT_V6_CONFIG_PATH,
    MultiAssetDevelopmentV6ContractError,
    build_development_v6_contract_artifact,
)
from multi_asset_discovery_v1 import fingerprint  # noqa: E402


def _git(project_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _require_clean_commit(project_root: Path) -> tuple[str, str]:
    status = _git(project_root, "status", "--porcelain")
    if status:
        raise MultiAssetDevelopmentV6ContractError(
            "Ein v6-Freeze ist nur aus einem sauberen committed Worktree erlaubt."
        )
    branch = _git(project_root, "branch", "--show-current")
    commit = _git(project_root, "rev-parse", "HEAD")
    if not branch or len(commit) != 40:
        raise MultiAssetDevelopmentV6ContractError(
            "Branch/Commit für den v6-Freeze ist nicht eindeutig."
        )
    return branch, commit


def _existing_matches(
    path: Path, payload: Mapping[str, object], *, fingerprint_field: str
) -> bool:
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiAssetDevelopmentV6ContractError(
            f"Bestehendes append-only Artefakt ist nicht lesbar: {path}"
        ) from exc
    stored = str(existing.get(fingerprint_field) or "")
    comparable = dict(existing)
    comparable.pop(fingerprint_field, None)
    if not stored or stored != fingerprint(comparable):
        raise MultiAssetDevelopmentV6ContractError(
            f"Bestehendes Artefakt besitzt keinen gültigen Fingerprint: {path}"
        )
    return stored == str(payload.get(fingerprint_field) or "")


def _append_only_json(
    path: Path, payload: Mapping[str, object], *, fingerprint_field: str
) -> str:
    """Publish one complete JSON file without overwriting an existing artifact."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not _existing_matches(path, payload, fingerprint_field=fingerprint_field):
            raise MultiAssetDevelopmentV6ContractError(
                f"Append-only Ziel ist bereits abweichend belegt: {path}"
            )
        return "UNCHANGED"
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if not _existing_matches(path, payload, fingerprint_field=fingerprint_field):
                raise MultiAssetDevelopmentV6ContractError(
                    f"Paralleler append-only Freeze kollidiert: {path}"
                )
            return "UNCHANGED"
        return "CREATED"
    finally:
        temporary.unlink(missing_ok=True)


def _resolve_output(project_root: Path, value: object) -> Path:
    root = project_root.resolve()
    path = (root / str(value)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise MultiAssetDevelopmentV6ContractError(
            "Contract-Ausgabe verlässt den Projektpfad."
        ) from exc
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_V6_CONFIG_PATH)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--parent-artifact", type=Path)
    parser.add_argument("--input-precheck", type=Path)
    parser.add_argument("--worker-benchmark", type=Path)
    parser.add_argument("--descriptive-plan", type=Path)
    parser.add_argument("--frozen-at")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Append-only Contract- und Diff-Artefakt erzeugen; startet keinen Run.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    project_root = Path(args.project_root).resolve()
    if args.write:
        branch, commit = _require_clean_commit(project_root)
    else:
        branch = _git(project_root, "branch", "--show-current")
        commit = _git(project_root, "rev-parse", "HEAD")
    frozen_at = args.frozen_at or datetime.now(timezone.utc).isoformat()
    artifact, diff = build_development_v6_contract_artifact(
        git_branch=branch,
        git_commit=commit,
        frozen_at=frozen_at,
        config_path=Path(args.config),
        project_root=project_root,
        parent_artifact_path=args.parent_artifact,
        input_precheck_path=args.input_precheck,
        worker_benchmark_path=args.worker_benchmark,
        descriptive_plan_path=args.descriptive_plan,
    )
    contract = dict(artifact["contract"])
    execution = dict(contract["development_execution"])
    writes: dict[str, str] = {}
    if args.write:
        diff_path = _resolve_output(
            project_root, execution["contract_diff_artifact"]
        )
        contract_path = _resolve_output(
            project_root, execution["contract_artifact"]
        )
        writes["contract_diff_artifact"] = _append_only_json(
            diff_path, diff, fingerprint_field="diff_fingerprint"
        )
        writes["contract_artifact"] = _append_only_json(
            contract_path, artifact, fingerprint_field="artifact_fingerprint"
        )
    return {
        "mode": "WRITE_APPEND_ONLY" if args.write else "CHECK_ONLY",
        "status": "PASS",
        "contract_version": contract["contract_version"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "diff_fingerprint": diff["diff_fingerprint"],
        "unauthorized_research_semantics_count": diff[
            "unauthorized_research_semantics_count"
        ],
        "full_development_run_authorized": artifact[
            "full_development_run_authorized"
        ],
        "development_run_started": False,
        "writes": writes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    result = run(parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
