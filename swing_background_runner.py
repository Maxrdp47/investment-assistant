from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from cot_positioning import (
    DEFAULT_COT_MAPPING_PATH,
    collect_forward_cot_contexts,
    cot_shadow_store_audit,
)
from swing_forward_runner import run_swing_forward_evaluations
from swing_forward_store import (
    SWING_STRATEGY_VERSION,
    record_swing_forward_scan,
    swing_forward_store_audit,
)
from swing_event_research import (
    collect_forward_event_contexts,
    event_research_store_audit,
)
from swing_paper_bot import (
    paper_bot_store_audit,
    paper_portfolio_state,
    record_paper_scan_cycle,
    run_paper_bot_evaluations,
)
from swing_shadow_live import (
    record_shadow_execution_observations,
    record_shadow_live_drafts,
    shadow_live_store_audit,
    shadow_paper_comparison,
)
from swing_walk_forward import refresh_swing_walk_forward_forward_links
from swing_run_lock import SwingRunAlreadyActiveError, SwingRunLock
from swing_scanner import internal_swing_settings
from swing_universe import active_swing_assets, load_swing_universe


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SWING_BACKGROUND_SETTINGS_PATH = PROJECT_ROOT / "config" / "swing_background_settings.json"


def _strategy_forward_configuration(payload: dict) -> dict:
    configured = payload.get("strategy_forward")
    if configured is None:
        return {
            "enabled": True,
            "lifecycle_status": "ACTIVE_LEGACY_DEFAULT",
            "strategy_version": SWING_STRATEGY_VERSION,
            "new_strategy_signals_allowed": True,
            "new_paper_cycles_allowed": True,
            "new_shadow_drafts_allowed": True,
            "broker_order_allowed": False,
        }
    strategy_forward = dict(configured)
    if strategy_forward.get("enabled") is False:
        required_false = (
            "new_strategy_signals_allowed",
            "new_paper_cycles_allowed",
            "new_shadow_drafts_allowed",
            "broker_order_allowed",
        )
        unsafe = [name for name in required_false if strategy_forward.get(name) is not False]
        if unsafe:
            raise ValueError(
                "Ein eingefrorener Strategy-Forward muss fail-closed sein: "
                + ", ".join(unsafe)
            )
        if str(strategy_forward.get("lifecycle_status") or "") != "LEGACY_RESEARCH_FROZEN":
            raise ValueError(
                "Ein deaktivierter Strategy-Forward muss als LEGACY_RESEARCH_FROZEN markiert sein."
            )
        if str(strategy_forward.get("strategy_version") or "") != SWING_STRATEGY_VERSION:
            raise ValueError("Die eingefrorene Strategy-Version stimmt nicht mit Forward v1 überein.")
    return strategy_forward


def _project_path(value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_swing_background_settings(
    path: Path = DEFAULT_SWING_BACKGROUND_SETTINGS_PATH,
) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"version", "universe_path", "database_path", "log_path", "task_prefix", "scopes"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Swing-Hintergrundkonfiguration unvollständig: {', '.join(missing)}")
    scopes = payload.get("scopes")
    if not isinstance(scopes, dict) or not scopes:
        raise ValueError("Mindestens ein Swing-Scanbereich muss konfiguriert sein.")
    for name, scope in scopes.items():
        if not isinstance(scope, dict):
            raise ValueError(f"Swing-Scanbereich {name} ist ungültig.")
        run_time = str(scope.get("local_run_time") or "")
        try:
            hour, minute = (int(part) for part in run_time.split(":"))
        except Exception as exc:
            raise ValueError(f"Ungültige lokale Uhrzeit für Swing-Scanbereich {name}.") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Ungültige lokale Uhrzeit für Swing-Scanbereich {name}.")
        if not scope.get("asset_types"):
            raise ValueError(f"Swing-Scanbereich {name} besitzt keine Asset-Typen.")
    paper = dict(payload.get("paper_bot") or {})
    if paper.get("enabled"):
        if not paper.get("paper_only") or float(paper.get("virtual_capital_eur") or 0) <= 0:
            raise ValueError("Der autonome Paper-Bot muss paper_only und mit positivem virtuellem Kapital laufen.")
    shadow = dict(payload.get("shadow_live") or {})
    if shadow.get("enabled") and (
        not shadow.get("shadow_only") or shadow.get("broker_order_allowed") is not False
    ):
        raise ValueError("Shadow-Live muss brokerlos und shadow_only konfiguriert sein.")
    if shadow.get("enabled") and shadow.get("collect_execution_observations") and (
        shadow.get("read_only_quote_provider") not in (None, "")
    ):
        raise ValueError(
            "Es ist derzeit keine belastbare automatische Read-only-Quotequelle konfiguriert."
        )
    cot_context = dict(payload.get("cot_context") or {})
    if cot_context.get("enabled") and (
        cot_context.get("shadow_only") is not True
        or cot_context.get("research_only") is not True
        or cot_context.get("changes_trade_decision") is not False
        or cot_context.get("broker_order_allowed") is not False
    ):
        raise ValueError(
            "COT-Forward-Kontext muss research_only, shadow_only, produktionsneutral und brokerlos sein."
        )
    event_research = dict(payload.get("event_research") or {})
    if event_research.get("enabled") and (
        event_research.get("research_only") is not True
        or event_research.get("changes_trade_decision") is not False
        or event_research.get("broker_order_allowed") is not False
    ):
        raise ValueError(
            "Event-Research muss research_only, produktionsneutral und brokerlos konfiguriert sein."
        )
    strategy_forward = _strategy_forward_configuration(payload)
    observer = dict(payload.get("observer") or {})
    if strategy_forward.get("enabled") is False and observer.get("enabled") is True:
        raise ValueError(
            "Ein Observer darf erst aktiviert werden, wenn er technisch sicher von Strategie-, "
            "Paper- und Shadow-Entscheidungen getrennt ist."
        )
    return payload


def _matches_scope(asset, scope: dict) -> bool:
    asset_types = {str(value) for value in scope.get("asset_types") or []}
    regions = {str(value) for value in scope.get("regions") or []}
    return asset.asset_type in asset_types and (not regions or asset.region in regions)


def swing_background_preflight(
    settings_path: Path = DEFAULT_SWING_BACKGROUND_SETTINGS_PATH,
) -> dict:
    settings = load_swing_background_settings(settings_path)
    strategy_forward = _strategy_forward_configuration(settings)
    observer = dict(settings.get("observer") or {})
    universe_path = _project_path(settings["universe_path"])
    report = load_swing_universe(universe_path)
    assets = active_swing_assets(report)
    scope_counts = {name: 0 for name in settings["scopes"]}
    duplicate_assignments: list[str] = []
    unassigned: list[str] = []
    for asset in assets:
        matches = [name for name, scope in settings["scopes"].items() if _matches_scope(asset, scope)]
        if len(matches) == 1:
            scope_counts[matches[0]] += 1
        elif not matches:
            unassigned.append(asset.ticker)
        else:
            duplicate_assignments.append(f"{asset.ticker}:{','.join(matches)}")
    database_path = _project_path(settings["database_path"])
    database = (
        swing_forward_store_audit(database_path)
        if database_path.exists()
        else {"status": "not_created", "scans": 0, "signals": 0, "events": 0}
    )
    paper_settings = dict(settings.get("paper_bot") or {})
    shadow_settings = dict(settings.get("shadow_live") or {})
    paper_path = _project_path(paper_settings.get("database_path", "runtime/swing_paper_bot.sqlite3"))
    shadow_path = _project_path(shadow_settings.get("database_path", "runtime/swing_shadow_live.sqlite3"))
    event_settings = dict(settings.get("event_research") or {})
    event_path = _project_path(
        event_settings.get("database_path", "runtime/swing_event_research.sqlite3")
    )
    cot_settings = dict(settings.get("cot_context") or {})
    cot_path = _project_path(cot_settings.get("database_path", "runtime/cot_shadow.sqlite3"))
    status = "ok" if assets and not unassigned and not duplicate_assignments and database["status"] in {"ok", "not_created"} else "attention"
    return {
        "status": status,
        "settings_version": settings["version"],
        "universe_path": str(universe_path.resolve()),
        "universe_assets": len(assets),
        "scope_counts": scope_counts,
        "covered_assets": sum(scope_counts.values()),
        "unassigned": unassigned,
        "duplicate_assignments": duplicate_assignments,
        "database": database,
        "task_prefix": settings["task_prefix"],
        "run_times": {
            name: scope["local_run_time"] for name, scope in settings["scopes"].items()
        },
        "schedule_modes": {
            name: scope.get("schedule_mode", "daily") for name, scope in settings["scopes"].items()
        },
        "orders_enabled": False,
        "strategy_forward": {
            "enabled": bool(strategy_forward.get("enabled")),
            "lifecycle_status": strategy_forward.get("lifecycle_status"),
            "strategy_version": strategy_forward.get("strategy_version"),
            "new_strategy_signals_allowed": bool(
                strategy_forward.get("new_strategy_signals_allowed")
            ),
            "new_paper_cycles_allowed": bool(strategy_forward.get("new_paper_cycles_allowed")),
            "new_shadow_drafts_allowed": bool(strategy_forward.get("new_shadow_drafts_allowed")),
            "broker_order_allowed": bool(strategy_forward.get("broker_order_allowed")),
        },
        "observer": {
            "enabled": bool(observer.get("enabled")),
            "market_data_collection_allowed": bool(observer.get("enabled")),
            "strategy_decision_allowed": False,
            "trade_decision_allowed": False,
        },
        "paper_bot": paper_bot_store_audit(paper_path),
        "shadow_live": shadow_live_store_audit(shadow_path),
        "event_research": (
            {"status": "disabled", "production_effect": "none"}
            if not event_settings.get("enabled")
            else event_research_store_audit(event_path)
            if event_path.exists()
            else {
                "status": "not_created",
                "events": 0,
                "signal_contexts": 0,
                "production_effect": "none",
            }
        ),
        "cot_context": (
            {"status": "disabled", "production_effect": "none"}
            if not cot_settings.get("enabled")
            else cot_shadow_store_audit(cot_path)
            if cot_path.exists()
            else {
                "status": "not_created",
                "forward_contexts": 0,
                "forward_linked": 0,
                "forward_unavailable": 0,
                "production_effect": "none",
            }
        ),
    }


def _logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"swing-background:{path}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def run_swing_background_scope(
    scope_name: str,
    *,
    settings_path: Path = DEFAULT_SWING_BACKGROUND_SETTINGS_PATH,
    scan_callable: Callable[..., dict] | None = None,
    evaluation_callable: Callable[..., dict] = run_swing_forward_evaluations,
    event_collection_callable: Callable[..., dict] | None = None,
    cot_collection_callable: Callable[..., dict] | None = None,
    shadow_quote_collection_callable: Callable[..., dict] | None = None,
) -> dict:
    started_at = datetime.now().astimezone()
    started_monotonic = time.monotonic()
    settings = load_swing_background_settings(settings_path)
    if scope_name not in settings["scopes"]:
        raise ValueError(f"Unbekannter Swing-Scanbereich: {scope_name}")
    strategy_forward = _strategy_forward_configuration(settings)
    observer = dict(settings.get("observer") or {})
    if strategy_forward.get("enabled") is False:
        return {
            "status": "legacy_strategy_frozen",
            "scope": scope_name,
            "lifecycle_status": strategy_forward["lifecycle_status"],
            "strategy_version": strategy_forward["strategy_version"],
            "reason": strategy_forward.get("reason"),
            "strategy_forward_enabled": False,
            "observer_enabled": bool(observer.get("enabled")),
            "market_data_loaded": False,
            "strategy_evaluation_started": False,
            "scan_recorded": False,
            "new_strategy_signals": 0,
            "paper_cycle_created": False,
            "shadow_drafts_created": False,
            "broker_order_allowed": False,
            "orders_enabled": False,
        }
    scope = dict(settings["scopes"][scope_name])
    database_path = _project_path(settings["database_path"])
    universe_path = _project_path(settings["universe_path"])
    log = _logger(_project_path(settings["log_path"]))
    lock = SwingRunLock(database_path.with_suffix(".scan.lock"))
    try:
        lock.acquire()
    except SwingRunAlreadyActiveError as exc:
        return {"status": "already_active", "scope": scope_name, "error": str(exc)}
    try:
        log.info("scope_start scope=%s settings=%s", scope_name, settings["version"])
        evaluation = None
        if bool(scope.get("evaluate_open_signals")) and database_path.exists():
            evaluation = evaluation_callable(path=database_path)
        paper_configuration = dict(settings.get("paper_bot") or {})
        shadow_configuration = dict(settings.get("shadow_live") or {})
        event_configuration = dict(settings.get("event_research") or {})
        cot_configuration = dict(settings.get("cot_context") or {})
        paper_path = _project_path(
            paper_configuration.get("database_path", "runtime/swing_paper_bot.sqlite3")
        )
        shadow_path = _project_path(
            shadow_configuration.get("database_path", "runtime/swing_shadow_live.sqlite3")
        )
        event_path = _project_path(
            event_configuration.get("database_path", "runtime/swing_event_research.sqlite3")
        )
        cot_path = _project_path(
            cot_configuration.get("database_path", "runtime/cot_shadow.sqlite3")
        )
        cot_mapping_path = _project_path(
            cot_configuration.get("mapping_path", str(DEFAULT_COT_MAPPING_PATH))
        )
        paper_evaluation = None
        if paper_configuration.get("enabled") and paper_path.exists():
            paper_evaluation = run_paper_bot_evaluations(path=paper_path)
        if scan_callable is None:
            from app import scan_swing_market

            scan_callable = scan_swing_market
        scan = scan_callable(
            internal_swing_settings(0.0),
            universe_path=universe_path,
            scope_name=scope_name,
            scope_regions=set(scope.get("regions") or []) or None,
            scope_asset_types=set(scope.get("asset_types") or []),
            objective_forward=True,
        )
        statistics = dict(scan.get("statistics") or {})
        selected = int(statistics.get("universe_size") or 0)
        loaded = int(statistics.get("loaded_assets") or 0)
        finished_at = datetime.now().astimezone()
        error_texts = [str(error) for error in scan.get("errors") or []]
        rate_limit_errors = sum(
            any(token in error.lower() for token in ("rate limit", "too many requests", "429"))
            for error in error_texts
        )
        run_metrics = {
            "settings_version": settings["version"],
            "scope": scope_name,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(time.monotonic() - started_monotonic, 3),
            "selected_assets": selected,
            "loaded_assets": loaded,
            "failed_downloads": int(statistics.get("failed_downloads") or 0),
            "rate_limit_errors": rate_limit_errors,
            "orders_enabled": False,
        }
        scan["background_run"] = run_metrics
        if selected > 0 and loaded == 0:
            result = {
                "status": "provider_unavailable",
                "scope": scope_name,
                "selected_assets": selected,
                "loaded_assets": 0,
                "scan_recorded": False,
                "evaluation": evaluation,
                "run_metrics": run_metrics,
            }
            log.warning("scope_paused scope=%s reason=provider_unavailable selected=%s", scope_name, selected)
            return result
        stored = record_swing_forward_scan(scan, database_path)
        paper_cycle = None
        shadow_cycle = None
        shadow_quote_cycle = {
            "status": "disabled",
            "production_effect": "none",
            "broker_order_sent": False,
        }
        shadow_paper = None
        if paper_configuration.get("enabled"):
            paper_settings = internal_swing_settings(
                float(paper_configuration["virtual_capital_eur"])
            )
            prior_paper_state = paper_portfolio_state(paper_path)
            if shadow_configuration.get("enabled"):
                shadow_cycle = record_shadow_live_drafts(
                    scan,
                    paper_settings,
                    current_exposure_eur=float(prior_paper_state["exposure_eur"]),
                    current_risk_eur=float(prior_paper_state["risk_eur"]),
                    signal_ids_by_setup=dict(stored.get("signal_ids_by_setup") or {}),
                    path=shadow_path,
                )
                if shadow_configuration.get("collect_execution_observations"):
                    quote_collector = (
                        shadow_quote_collection_callable or record_shadow_execution_observations
                    )
                    try:
                        shadow_quote_cycle = quote_collector(
                            draft_ids=list(shadow_cycle.get("draft_ids") or []),
                            signal_ids_by_setup=dict(stored.get("signal_ids_by_setup") or {}),
                            observed_at=datetime.now().astimezone(),
                            quote_provider=None,
                            path=shadow_path,
                            max_quote_age_seconds=int(
                                shadow_configuration.get("max_quote_age_seconds") or 300
                            ),
                        )
                    except Exception as exc:
                        shadow_quote_cycle = {
                            "status": "research_attention",
                            "error": str(exc),
                            "scan_or_signal_blocked": False,
                            "paper_cycle_blocked": False,
                            "production_effect": "none",
                            "broker_order_sent": False,
                        }
            paper_cycle = record_paper_scan_cycle(scan, paper_settings, path=paper_path)
            if shadow_configuration.get("enabled"):
                shadow_paper = shadow_paper_comparison(shadow_path, paper_path)
        try:
            evidence_links = refresh_swing_walk_forward_forward_links(
                database_path.with_name("swing_walk_forward.sqlite3"),
                database_path,
            )
        except Exception as exc:
            evidence_links = {
                "status": "attention",
                "error": str(exc),
                "automatic_rule_change": False,
            }
        cot_collection = {
            "status": "disabled",
            "shadow_only": True,
            "research_only": True,
            "production_effect": "none",
            "broad_research_blocked": False,
        }
        if cot_configuration.get("enabled"):
            cot_collector = cot_collection_callable or collect_forward_cot_contexts
            try:
                cot_collection = cot_collector(
                    signal_ids=list((stored.get("signal_ids_by_setup") or {}).values()),
                    forward_path=database_path,
                    collected_at=datetime.now().astimezone(),
                    path=cot_path,
                    mapping_path=cot_mapping_path,
                    refresh_official=bool(
                        cot_configuration.get("refresh_official_forward", False)
                    ),
                )
            except Exception as exc:
                cot_collection = {
                    "status": "research_attention",
                    "error": str(exc),
                    "shadow_only": True,
                    "research_only": True,
                    "production_effect": "none",
                    "scan_or_signal_blocked": False,
                    "paper_cycle_blocked": False,
                    "broad_research_blocked": False,
                }
        # The production signal, paper/shadow cycle, and historical evidence linkage
        # are completed before this optional research-only provider work begins.
        event_collection = {
            "status": "disabled",
            "research_shadow_only": True,
            "production_effect": "none",
            "broad_research_blocked": False,
        }
        if event_configuration.get("enabled"):
            collector = event_collection_callable or collect_forward_event_contexts
            try:
                event_collection = collector(
                    signal_ids=list((stored.get("signal_ids_by_setup") or {}).values()),
                    forward_path=database_path,
                    collected_at=datetime.now().astimezone(),
                    path=event_path,
                )
                event_collection["status"] = (
                    "ok" if not event_collection.get("errors") else "research_attention"
                )
            except Exception as exc:
                event_collection = {
                    "status": "research_attention",
                    "error": str(exc),
                    "research_shadow_only": True,
                    "production_effect": "none",
                    "broad_research_blocked": False,
                    "scan_or_signal_blocked": False,
                }
        audit = swing_forward_store_audit(database_path)
        result = {
            "status": "ok" if audit["status"] == "ok" else "attention",
            "scope": scope_name,
            "selected_assets": selected,
            "loaded_assets": loaded,
            "failed_downloads": int(statistics.get("failed_downloads") or 0),
            "approved_signals": len(scan.get("approved") or []),
            "scan_recorded": True,
            "stored": stored,
            "event_research": event_collection,
            "cot_context": cot_collection,
            "historical_real_forward_linkage": evidence_links,
            "evaluation": evaluation,
            "paper_evaluation": paper_evaluation,
            "paper_cycle": paper_cycle,
            "shadow_cycle": shadow_cycle,
            "shadow_execution_observations": shadow_quote_cycle,
            "shadow_paper_comparison": shadow_paper,
            "run_metrics": run_metrics,
            "database": audit,
            "orders_enabled": False,
            "paper_only": True,
            "shadow_only": True,
        }
        log.info(
            "scope_end scope=%s selected=%s loaded=%s signals=%s rate_limits=%s duration_seconds=%s status=%s",
            scope_name,
            selected,
            loaded,
            result["approved_signals"],
            rate_limit_errors,
            run_metrics["duration_seconds"],
            result["status"],
        )
        return result
    finally:
        lock.release()
