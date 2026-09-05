from __future__ import annotations

"""Build the immutable Crypto projection and/or the v6 input precheck.

This command never downloads data and never starts Development, Validation,
Holdout, External, Forward, Paper, Production, or broker activity.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_asset_development_execution import (  # noqa: E402
    DEFAULT_DATASET_MANIFEST,
    DEFAULT_FX_STORE,
    DEFAULT_IDENTITY_STORE,
)
from multi_asset_development_v6_inputs import (  # noqa: E402
    DEFAULT_CRYPTO_ARTIFACT,
    DEFAULT_CRYPTO_STORE,
    DEFAULT_EQUITY_ETF_ARTIFACT,
    DEFAULT_EQUITY_ETF_STORE,
    DEFAULT_FX_ARTIFACT,
    DEFAULT_INPUT_PRECHECK_ARTIFACT,
    build_crypto_projection,
    build_v6_input_precheck,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("crypto", "precheck", "all"),
        default="all",
        help="`all` builds Crypto first and then audits the combined inputs.",
    )
    parser.add_argument("--dataset-manifest", type=Path, default=DEFAULT_DATASET_MANIFEST)
    parser.add_argument("--identity-store", type=Path, default=DEFAULT_IDENTITY_STORE)
    parser.add_argument("--equity-etf-store", type=Path, default=DEFAULT_EQUITY_ETF_STORE)
    parser.add_argument(
        "--equity-etf-artifact", type=Path, default=DEFAULT_EQUITY_ETF_ARTIFACT
    )
    parser.add_argument("--crypto-store", type=Path, default=DEFAULT_CRYPTO_STORE)
    parser.add_argument("--crypto-artifact", type=Path, default=DEFAULT_CRYPTO_ARTIFACT)
    parser.add_argument("--fx-store", type=Path, default=DEFAULT_FX_STORE)
    parser.add_argument("--fx-artifact", type=Path, default=DEFAULT_FX_ARTIFACT)
    parser.add_argument(
        "--input-precheck-artifact",
        type=Path,
        default=DEFAULT_INPUT_PRECHECK_ARTIFACT,
    )
    parser.add_argument(
        "--implementation-path",
        action="append",
        type=Path,
        help=(
            "Override the complete implementation file set. Repeat once per file; "
            "omission uses the fail-closed production list."
        ),
    )
    parser.add_argument("--created-at")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    result: dict[str, object] = {
        "phase": args.phase,
        "development_run_started": False,
    }
    if args.phase in {"crypto", "all"}:
        result["crypto_projection"] = build_crypto_projection(
            target_path=args.crypto_store,
            artifact_path=args.crypto_artifact,
            manifest_path=args.dataset_manifest,
            identity_store=args.identity_store,
            created_at=args.created_at,
        )
    if args.phase in {"precheck", "all"}:
        result["input_precheck"] = build_v6_input_precheck(
            equity_etf_store=args.equity_etf_store,
            equity_etf_artifact=args.equity_etf_artifact,
            crypto_store=args.crypto_store,
            crypto_artifact=args.crypto_artifact,
            fx_store=args.fx_store,
            fx_artifact=args.fx_artifact,
            dataset_manifest=args.dataset_manifest,
            identity_store=args.identity_store,
            implementation_paths=args.implementation_path,
            artifact_path=args.input_precheck_artifact,
            created_at=args.created_at,
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    result = run(parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    precheck = result.get("input_precheck")
    return 0 if not isinstance(precheck, dict) or precheck.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
