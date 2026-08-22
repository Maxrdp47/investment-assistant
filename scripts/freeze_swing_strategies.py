from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swing_forward_store import SWING_STRATEGY_VERSION  # noqa: E402
from swing_scanner import (  # noqa: E402
    prefilter_thresholds_as_dict,
    risk_policy_as_dict,
)
from swing_strategy_freeze import (  # noqa: E402
    DEFAULT_STRATEGY_FREEZE_DB_PATH,
    build_strategy_freeze_artifact,
    register_strategy_freeze,
    strategy_freeze_store_audit,
)
from swing_walk_forward import (  # noqa: E402
    SWING_WALK_FORWARD_RESEARCH_CONTRACT,
    TECHNICAL_CHALLENGER_PROFILE_NAMES,
    swing_walk_forward_strategy_profiles,
)
from trading_assistant import (  # noqa: E402
    SWING_EXECUTION_COST_VERSION,
    SWING_ORDER_PLAN_VERSION,
    SWING_STOP_CONTRACT_VERSION,
    swing_execution_cost_contract,
)


def _components(profile: dict) -> dict:
    return {
        "strategy": {
            "production_baseline_version": SWING_STRATEGY_VERSION,
            "research_strategy_name": profile["name"],
            "research_strategy_version": profile["version"],
            "strategy_family": profile["strategy_family"],
            "parameter_variant": profile["parameter_variant"],
            "direction": "long_only",
            "research_only": profile["name"] != "current",
            "automatic_production_activation": False,
        },
        "parameters": dict(profile["thresholds_snapshot"]),
        "filters": {
            "asset_type_neutral_prefilter": prefilter_thresholds_as_dict(),
            "technical_challenger_filter": dict(profile["technical_filter"]),
            "future_data_allowed_for_signal": False,
        },
        "risk_rules": {
            **risk_policy_as_dict(),
            "independent_risk_engine_required": True,
            "strategy_may_bypass_risk_engine": False,
        },
        "order_logic": {
            "version": SWING_ORDER_PLAN_VERSION,
            "entry_after_completed_signal_bar": True,
            "retroactive_fill_allowed": False,
            "broker_adapter_present": False,
        },
        "position_management": {
            "partial_target_1_fraction": 0.5,
            "remaining_target_2_fraction": 0.5,
            "initial_stop_may_be_widened": False,
            "idempotent_event_processing_required": True,
        },
        "exit_rules": {
            "stop_contract_version": SWING_STOP_CONTRACT_VERSION,
            "initial_stop": "immutable",
            "target_sequence": ["target_1_partial", "target_2_remaining"],
            "same_bar_ambiguity": "conservative",
        },
        "cost_model": {
            "version": SWING_EXECUTION_COST_VERSION,
            "stock": swing_execution_cost_contract("Aktie"),
            "etf": swing_execution_cost_contract("ETF"),
            "crypto": swing_execution_cost_contract("Krypto"),
        },
        "data_contract": {
            "walk_forward_contract": SWING_WALK_FORWARD_RESEARCH_CONTRACT,
            "chronological_development_validation_holdout": True,
            "purging_required": True,
            "adjusted_historical_ohlcv_required": True,
            "signal_features_end_at_signal_bar": True,
            "walk_forward_forward_paper_shadow_user_evidence_separate": True,
            "trade_republic_execution_data_never_inferred": True,
        },
    }


def freeze_all(
    *,
    database: Path = DEFAULT_STRATEGY_FREEZE_DB_PATH,
    export_directory: Path | None = None,
) -> dict:
    names = ("current", *TECHNICAL_CHALLENGER_PROFILE_NAMES)
    profiles = swing_walk_forward_strategy_profiles(names)
    code_paths = [
        PROJECT_ROOT / "trading_assistant.py",
        PROJECT_ROOT / "swing_scanner.py",
        PROJECT_ROOT / "swing_risk_engine.py",
        PROJECT_ROOT / "swing_forward_evaluation.py",
        PROJECT_ROOT / "swing_walk_forward.py",
        PROJECT_ROOT / "swing_paper_bot.py",
        PROJECT_ROOT / "swing_shadow_live.py",
    ]
    config_paths = [
        PROJECT_ROOT / "config" / "swing_background_settings.json",
        PROJECT_ROOT / "config" / "swing_walk_forward_campaign.json",
    ]
    output = Path(export_directory or PROJECT_ROOT / "runtime" / "strategy_freezes")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for profile in profiles.values():
        artifact = build_strategy_freeze_artifact(
            strategy_name=str(profile["name"]),
            strategy_family=str(profile["strategy_family"]),
            strategy_role=(
                "existing_baseline" if profile["name"] == "current" else "research_challenger"
            ),
            components=_components(profile),
            code_paths=code_paths,
            config_paths=config_paths,
        )
        registration = register_strategy_freeze(artifact, database)
        destination = output / f"{artifact['strategy_version']}.json"
        encoded = json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if destination.exists():
            existing = json.loads(destination.read_text(encoding="utf-8"))
            if existing.get("artifact_fingerprint") != artifact["artifact_fingerprint"]:
                raise ValueError(f"Freeze-Datei {destination.name} ist bereits abweichend belegt.")
        else:
            destination.write_text(encoded, encoding="utf-8", newline="\n")
        results.append({**registration, "artifact_path": str(destination)})
    return {
        "freezes": results,
        "audit": strategy_freeze_store_audit(database),
        "baseline_released_from_performance": False,
        "challenger_production_activation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Unveränderbare Swing-Strategie-Freezes erzeugen.")
    parser.add_argument("--database", type=Path, default=DEFAULT_STRATEGY_FREEZE_DB_PATH)
    parser.add_argument("--export-directory", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(freeze_all(database=args.database, export_directory=args.export_directory), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
