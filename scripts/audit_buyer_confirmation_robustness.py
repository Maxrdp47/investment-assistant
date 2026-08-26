from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swing_buyer_confirmation_robustness import (  # noqa: E402
    apply_manual_decision,
    build_robustness_report,
    refresh_prior_audit_verification,
    verify_report_fingerprint,
    write_append_only_json,
)


DEFAULT_BROAD = ROOT / "runtime" / "swing_broad_research.sqlite3"
DEFAULT_DATASET = (
    ROOT / "runtime" / "swing_walk_forward_datasets" / "f7109e21474a027892eb01ed"
)
DEFAULT_PRIOR_AUDIT = (
    ROOT
    / "runtime"
    / "research_exports"
    / "swing_broad_v1_method_audit_2026-08-25-v3-reviewed.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runtime"
    / "research_exports"
    / "buyer_confirmation_development_robustness_2026-08-25.json"
)


def _progress(stage: str, done: int, total: int) -> None:
    print(
        json.dumps({"stage": stage, "completed": done, "total": total}),
        file=sys.stderr,
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Development robustness check for Buyer Confirmation."
    )
    parser.add_argument("--broad", type=Path, default=DEFAULT_BROAD)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--prior-audit", type=Path, default=DEFAULT_PRIOR_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--analysis",
        type=Path,
        help="Reuse a completed fingerprint-verified analysis instead of recomputing it.",
    )
    parser.add_argument("--decision-file", type=Path)
    args = parser.parse_args()

    if args.analysis:
        report = json.loads(args.analysis.read_text(encoding="utf-8"))
        if not verify_report_fingerprint(report):
            raise RuntimeError("The reused robustness analysis fingerprint is invalid.")
        if report.get("manual_decision") is not None:
            raise RuntimeError("The reused analysis already has a manual decision.")
        report = refresh_prior_audit_verification(report, args.prior_audit)
    else:
        report = build_robustness_report(
            args.broad,
            args.dataset,
            args.prior_audit,
            progress_callback=_progress,
        )
    if args.decision_file:
        decision = json.loads(args.decision_file.read_text(encoding="utf-8"))
        report = apply_manual_decision(
            report,
            decision=str(decision["decision"]),
            reason=str(decision["reason"]),
            decided_at=str(
                decision.get("decided_at") or datetime.now().astimezone().isoformat()
            ),
        )
    receipt = write_append_only_json(report, args.output)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
