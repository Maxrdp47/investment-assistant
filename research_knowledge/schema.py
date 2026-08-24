from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = Path(
    os.environ.get(
        "INVESTMENT_ASSISTANT_RESEARCH_KB_DB",
        PROJECT_ROOT / "runtime" / "research_knowledge.sqlite3",
    )
)
CURRENT_SCHEMA_VERSION = 6

ALLOWED_SOURCE_TYPES = (
    "tiktok",
    "youtube",
    "paper",
    "study",
    "own_observation",
    "other",
)
ALLOWED_AREAS = (
    "swing_trader",
    "opportunity_scanner",
    "investment",
    "cross_cutting",
)
ALLOWED_EVIDENCE_STRENGTHS = ("weak", "medium", "strong")
ALLOWED_RATINGS = ("A", "B", "C")
RATING_GUIDANCE = {
    "A": "Dokumentieren; kein Experiment erforderlich, solange kein ausreichender Research-Nutzen besteht.",
    "B": "Plausible und testbare Hypothese; Research-Backlog oder Experiment ist zulässig.",
    "C": "Priorisierte eigene Validierung; niemals automatische Strategieintegration.",
}
ALLOWED_HYPOTHESIS_STATUSES = (
    "RAW",
    "HYPOTHESIS",
    "TESTING",
    "WATCH",
    "VALIDATED",
    "REJECTED",
)
ALLOWED_SOURCE_STANCES = ("supports", "contradicts", "mixed", "context")
ALLOWED_EXPERIMENT_STATUSES = (
    "DRAFT",
    "PLANNED",
    "RUNNING",
    "COMPLETED",
    "CANCELLED",
)
ALLOWED_RESULT_CONCLUSIONS = (
    "supports",
    "contradicts",
    "mixed",
    "inconclusive",
    "negative",
)
ALLOWED_RELATION_TYPES = ("similar", "extends", "contradicts", "supersedes")
ALLOWED_RETEST_BASES = (
    "new_evidence",
    "new_data",
    "materially_different_hypothesis",
)
ALLOWED_CLAIM_RESOLUTIONS = (
    "LINKED_EXISTING",
    "CREATED_HYPOTHESIS",
    "MATERIAL_VARIANT",
    "DEFERRED",
    "NO_ACTION",
)
ALLOWED_CAPABILITY_OUTCOMES = (
    "ALREADY_AVAILABLE",
    "TESTABLE_NOW",
    "CODE_EXTENSION_REQUIRED",
    "NEW_DATA_REQUIRED",
    "DEFERRED",
    "NO_ACTION",
)
ALLOWED_INTEGRATION_DECISIONS = (
    "APPROVED_FOR_IMPLEMENTATION",
    "REJECTED",
    "DEFERRED",
    "MORE_RESEARCH_REQUIRED",
)
ALLOWED_INTEGRATION_EVENTS = ("INTEGRATED", "ROLLED_BACK")
ALLOWED_MARKET_SCOPE_TARGETS = (
    "source_claim",
    "hypothesis",
    "experiment",
    "integration_candidate",
)
ALLOWED_WORK_REQUEST_TYPES = (
    "RESEARCH_TEST",
    "CODE_EXTENSION",
    "DATA_PIPELINE",
    "INTEGRATION_REVIEW",
)
ALLOWED_WORK_REQUEST_STATUSES = (
    "READY",
    "IN_PROGRESS",
    "COMPLETED",
    "BLOCKED",
    "CANCELLED",
)
ALLOWED_RESULT_DIRECTIONS = ("SUPPORTING", "NEGATIVE", "INCONCLUSIVE")
ALLOWED_VALIDATION_GATE_STATUSES = (
    "PASSED",
    "FAILED",
    "NOT_REQUIRED",
    "NOT_RUN",
    "UNDERPOWERED",
    "INVALID",
)
ALLOWED_LEGACY_RECONCILIATION_OUTCOMES = (
    "ALREADY_MIGRATED",
    "LINK_SOURCE_TO_EXISTING",
    "IMPORT_SOURCE_ONLY",
    "IMPORT_NEW_CLAIMS",
    "CREATE_NEW_HYPOTHESIS",
    "UPDATE_EVIDENCE",
    "SKIP_DUPLICATE",
    "NO_ACTION",
)
ALLOWED_TRANSCRIPTION_STATUSES = (
    "NOT_REQUIRED",
    "EXISTING",
    "GENERATED",
    "FAILED",
    "INSUFFICIENT_AUDIO",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


SCHEMA_MIGRATIONS = {
    1: f"""
        CREATE TABLE research_sources (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL CHECK(source_type IN ({_quoted(ALLOWED_SOURCE_TYPES)})),
            reference TEXT,
            source_date TEXT,
            neutral_summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE hypotheses (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            area TEXT NOT NULL CHECK(area IN ({_quoted(ALLOWED_AREAS)})),
            category TEXT NOT NULL,
            claim TEXT NOT NULL,
            normalized_claim TEXT NOT NULL,
            claim_fingerprint TEXT NOT NULL,
            mechanism TEXT NOT NULL,
            external_evidence TEXT NOT NULL CHECK(external_evidence IN ({_quoted(ALLOWED_EVIDENCE_STRENGTHS)})),
            rating TEXT NOT NULL CHECK(rating IN ({_quoted(ALLOWED_RATINGS)})),
            current_status TEXT NOT NULL CHECK(current_status IN ({_quoted(ALLOWED_HYPOTHESIS_STATUSES)})),
            risks_limitations TEXT NOT NULL,
            strategy TEXT,
            asset_class TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE hypothesis_sources (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            source_id TEXT NOT NULL REFERENCES research_sources(id),
            stance TEXT NOT NULL CHECK(stance IN ({_quoted(ALLOWED_SOURCE_STANCES)})),
            note TEXT NOT NULL DEFAULT '',
            linked_at TEXT NOT NULL,
            UNIQUE(hypothesis_id, source_id)
        );

        CREATE TABLE experiments (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            title TEXT NOT NULL,
            test_definition TEXT NOT NULL,
            data_universe TEXT NOT NULL,
            period_start TEXT,
            period_end TEXT,
            point_in_time_rules TEXT NOT NULL,
            baseline TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            current_status TEXT NOT NULL CHECK(current_status IN ({_quoted(ALLOWED_EXPERIMENT_STATUSES)})),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE experiment_features (
            experiment_id TEXT NOT NULL REFERENCES experiments(id),
            feature TEXT NOT NULL COLLATE NOCASE,
            PRIMARY KEY(experiment_id, feature)
        );

        CREATE TABLE experiment_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL REFERENCES experiments(id),
            from_status TEXT,
            to_status TEXT NOT NULL CHECK(to_status IN ({_quoted(ALLOWED_EXPERIMENT_STATUSES)})),
            changed_at TEXT NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE research_results (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL REFERENCES experiments(id),
            title TEXT NOT NULL,
            conclusion TEXT NOT NULL CHECK(conclusion IN ({_quoted(ALLOWED_RESULT_CONCLUSIONS)})),
            sample_size INTEGER CHECK(sample_size IS NULL OR sample_size >= 0),
            hit_rate REAL,
            expectancy REAL,
            profit_factor REAL CHECK(profit_factor IS NULL OR profit_factor >= 0),
            mfe REAL,
            mae REAL,
            drawdown REAL,
            r_multiples REAL,
            costs REAL,
            slippage REAL,
            in_sample_json TEXT,
            validation_json TEXT,
            out_of_sample_json TEXT,
            walk_forward_json TEXT,
            forward_json TEXT,
            papertrade_json TEXT,
            interpretation TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE hypothesis_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            from_status TEXT,
            to_status TEXT NOT NULL CHECK(to_status IN ({_quoted(ALLOWED_HYPOTHESIS_STATUSES)})),
            changed_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            retest_basis TEXT CHECK(retest_basis IS NULL OR retest_basis IN ({_quoted(ALLOWED_RETEST_BASES)}))
        );

        CREATE TABLE evidence_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            event_type TEXT NOT NULL,
            event_at TEXT NOT NULL,
            summary TEXT NOT NULL,
            source_id TEXT REFERENCES research_sources(id),
            experiment_id TEXT REFERENCES experiments(id),
            result_id TEXT REFERENCES research_results(id),
            from_status TEXT,
            to_status TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{{}}'
        );

        CREATE TABLE hypothesis_relations (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            related_hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            relation_type TEXT NOT NULL CHECK(relation_type IN ({_quoted(ALLOWED_RELATION_TYPES)})),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            CHECK(hypothesis_id <> related_hypothesis_id),
            UNIQUE(hypothesis_id, related_hypothesis_id, relation_type)
        );

        CREATE TABLE status_change_context (
            hypothesis_id TEXT PRIMARY KEY REFERENCES hypotheses(id),
            reason TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            retest_basis TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{{}}'
        );

        CREATE TABLE experiment_status_change_context (
            experiment_id TEXT PRIMARY KEY REFERENCES experiments(id),
            reason TEXT NOT NULL,
            changed_at TEXT NOT NULL
        );

        CREATE INDEX idx_hypotheses_category ON hypotheses(category COLLATE NOCASE);
        CREATE INDEX idx_hypotheses_status ON hypotheses(current_status);
        CREATE INDEX idx_hypotheses_rating ON hypotheses(rating);
        CREATE INDEX idx_hypotheses_area ON hypotheses(area);
        CREATE INDEX idx_hypotheses_strategy ON hypotheses(strategy COLLATE NOCASE);
        CREATE INDEX idx_hypotheses_asset_class ON hypotheses(asset_class COLLATE NOCASE);
        CREATE INDEX idx_hypotheses_claim_fingerprint ON hypotheses(claim_fingerprint);
        CREATE INDEX idx_hypothesis_sources_hypothesis ON hypothesis_sources(hypothesis_id);
        CREATE INDEX idx_hypothesis_sources_source ON hypothesis_sources(source_id);
        CREATE INDEX idx_experiments_hypothesis ON experiments(hypothesis_id);
        CREATE INDEX idx_experiment_features_feature ON experiment_features(feature COLLATE NOCASE);
        CREATE INDEX idx_results_experiment ON research_results(experiment_id);
        CREATE INDEX idx_status_history_hypothesis ON hypothesis_status_history(hypothesis_id, id);
        CREATE INDEX idx_evidence_hypothesis_time ON evidence_ledger(hypothesis_id, event_at, id);
        CREATE INDEX idx_relations_hypothesis ON hypothesis_relations(hypothesis_id);
        CREATE INDEX idx_relations_related ON hypothesis_relations(related_hypothesis_id);

        CREATE TRIGGER research_sources_no_update
        BEFORE UPDATE ON research_sources BEGIN
            SELECT RAISE(ABORT, 'research_sources is append-only');
        END;
        CREATE TRIGGER research_sources_no_delete
        BEFORE DELETE ON research_sources BEGIN
            SELECT RAISE(ABORT, 'research_sources is append-only');
        END;
        CREATE TRIGGER hypothesis_sources_no_update
        BEFORE UPDATE ON hypothesis_sources BEGIN
            SELECT RAISE(ABORT, 'hypothesis_sources is append-only');
        END;
        CREATE TRIGGER hypothesis_sources_no_delete
        BEFORE DELETE ON hypothesis_sources BEGIN
            SELECT RAISE(ABORT, 'hypothesis_sources is append-only');
        END;
        CREATE TRIGGER experiment_features_no_update
        BEFORE UPDATE ON experiment_features BEGIN
            SELECT RAISE(ABORT, 'experiment_features is append-only');
        END;
        CREATE TRIGGER experiment_features_no_delete
        BEFORE DELETE ON experiment_features BEGIN
            SELECT RAISE(ABORT, 'experiment_features is append-only');
        END;
        CREATE TRIGGER research_results_no_update
        BEFORE UPDATE ON research_results BEGIN
            SELECT RAISE(ABORT, 'research_results is append-only');
        END;
        CREATE TRIGGER research_results_no_delete
        BEFORE DELETE ON research_results BEGIN
            SELECT RAISE(ABORT, 'research_results is append-only');
        END;
        CREATE TRIGGER hypothesis_status_history_no_update
        BEFORE UPDATE ON hypothesis_status_history BEGIN
            SELECT RAISE(ABORT, 'hypothesis_status_history is append-only');
        END;
        CREATE TRIGGER hypothesis_status_history_no_delete
        BEFORE DELETE ON hypothesis_status_history BEGIN
            SELECT RAISE(ABORT, 'hypothesis_status_history is append-only');
        END;
        CREATE TRIGGER experiment_status_history_no_update
        BEFORE UPDATE ON experiment_status_history BEGIN
            SELECT RAISE(ABORT, 'experiment_status_history is append-only');
        END;
        CREATE TRIGGER experiment_status_history_no_delete
        BEFORE DELETE ON experiment_status_history BEGIN
            SELECT RAISE(ABORT, 'experiment_status_history is append-only');
        END;
        CREATE TRIGGER evidence_ledger_no_update
        BEFORE UPDATE ON evidence_ledger BEGIN
            SELECT RAISE(ABORT, 'evidence_ledger is append-only');
        END;
        CREATE TRIGGER evidence_ledger_no_delete
        BEFORE DELETE ON evidence_ledger BEGIN
            SELECT RAISE(ABORT, 'evidence_ledger is append-only');
        END;
        CREATE TRIGGER hypothesis_relations_no_update
        BEFORE UPDATE ON hypothesis_relations BEGIN
            SELECT RAISE(ABORT, 'hypothesis_relations is append-only');
        END;
        CREATE TRIGGER hypothesis_relations_no_delete
        BEFORE DELETE ON hypothesis_relations BEGIN
            SELECT RAISE(ABORT, 'hypothesis_relations is append-only');
        END;
        CREATE TRIGGER hypotheses_no_delete
        BEFORE DELETE ON hypotheses BEGIN
            SELECT RAISE(ABORT, 'hypotheses cannot be deleted');
        END;
        CREATE TRIGGER hypotheses_core_immutable
        BEFORE UPDATE ON hypotheses
        WHEN NEW.title IS NOT OLD.title
          OR NEW.area IS NOT OLD.area
          OR NEW.category IS NOT OLD.category
          OR NEW.claim IS NOT OLD.claim
          OR NEW.normalized_claim IS NOT OLD.normalized_claim
          OR NEW.claim_fingerprint IS NOT OLD.claim_fingerprint
          OR NEW.mechanism IS NOT OLD.mechanism
          OR NEW.external_evidence IS NOT OLD.external_evidence
          OR NEW.rating IS NOT OLD.rating
          OR NEW.risks_limitations IS NOT OLD.risks_limitations
          OR NEW.strategy IS NOT OLD.strategy
          OR NEW.asset_class IS NOT OLD.asset_class
          OR NEW.created_at IS NOT OLD.created_at
        BEGIN
            SELECT RAISE(ABORT, 'hypothesis definition is immutable; create a related revision');
        END;
        CREATE TRIGGER experiments_no_delete
        BEFORE DELETE ON experiments BEGIN
            SELECT RAISE(ABORT, 'experiments cannot be deleted');
        END;
        CREATE TRIGGER experiments_core_immutable
        BEFORE UPDATE ON experiments
        WHEN NEW.hypothesis_id IS NOT OLD.hypothesis_id
          OR NEW.title IS NOT OLD.title
          OR NEW.test_definition IS NOT OLD.test_definition
          OR NEW.data_universe IS NOT OLD.data_universe
          OR NEW.period_start IS NOT OLD.period_start
          OR NEW.period_end IS NOT OLD.period_end
          OR NEW.point_in_time_rules IS NOT OLD.point_in_time_rules
          OR NEW.baseline IS NOT OLD.baseline
          OR NEW.parameters_json IS NOT OLD.parameters_json
          OR NEW.created_at IS NOT OLD.created_at
        BEGIN
            SELECT RAISE(ABORT, 'experiment definition is immutable; create a new experiment');
        END;

        CREATE TRIGGER hypothesis_insert_cannot_validate_without_result
        BEFORE INSERT ON hypotheses
        WHEN NEW.current_status = 'VALIDATED'
        BEGIN
            SELECT RAISE(ABORT, 'VALIDATED requires an internal experiment result');
        END;
        CREATE TRIGGER hypothesis_update_cannot_validate_without_result
        BEFORE UPDATE OF current_status ON hypotheses
        WHEN NEW.current_status = 'VALIDATED'
          AND OLD.current_status <> 'VALIDATED'
          AND NOT EXISTS (
              SELECT 1
              FROM experiments e
              JOIN research_results r ON r.experiment_id = e.id
              WHERE e.hypothesis_id = NEW.id
          )
        BEGIN
            SELECT RAISE(ABORT, 'VALIDATED requires an internal experiment result');
        END;
        CREATE TRIGGER rejected_hypothesis_retest_requires_basis
        BEFORE UPDATE OF current_status ON hypotheses
        WHEN OLD.current_status = 'REJECTED'
          AND NEW.current_status <> 'REJECTED'
          AND NOT EXISTS (
              SELECT 1 FROM status_change_context
              WHERE hypothesis_id = NEW.id
                AND retest_basis IN ('new_evidence', 'new_data', 'materially_different_hypothesis')
          )
        BEGIN
            SELECT RAISE(ABORT, 'retesting REJECTED requires new evidence, new data or a materially different hypothesis');
        END;

        CREATE TRIGGER hypothesis_status_audit
        AFTER UPDATE OF current_status ON hypotheses
        WHEN OLD.current_status <> NEW.current_status
        BEGIN
            INSERT INTO hypothesis_status_history (
                hypothesis_id, from_status, to_status, changed_at, reason, retest_basis
            ) VALUES (
                NEW.id,
                OLD.current_status,
                NEW.current_status,
                COALESCE((SELECT changed_at FROM status_change_context WHERE hypothesis_id = NEW.id), NEW.updated_at),
                COALESCE((SELECT reason FROM status_change_context WHERE hypothesis_id = NEW.id), 'Direkte Statusänderung ohne Repository-Kontext'),
                (SELECT retest_basis FROM status_change_context WHERE hypothesis_id = NEW.id)
            );
            INSERT INTO evidence_ledger (
                hypothesis_id, event_type, event_at, summary, from_status, to_status, metadata_json
            ) VALUES (
                NEW.id,
                'status_changed',
                COALESCE((SELECT changed_at FROM status_change_context WHERE hypothesis_id = NEW.id), NEW.updated_at),
                COALESCE((SELECT reason FROM status_change_context WHERE hypothesis_id = NEW.id), 'Direkte Statusänderung ohne Repository-Kontext'),
                OLD.current_status,
                NEW.current_status,
                COALESCE((SELECT metadata_json FROM status_change_context WHERE hypothesis_id = NEW.id), '{{}}')
            );
            DELETE FROM status_change_context WHERE hypothesis_id = NEW.id;
        END;

        CREATE TRIGGER experiment_status_audit
        AFTER UPDATE OF current_status ON experiments
        WHEN OLD.current_status <> NEW.current_status
        BEGIN
            INSERT INTO experiment_status_history (
                experiment_id, from_status, to_status, changed_at, reason
            ) VALUES (
                NEW.id,
                OLD.current_status,
                NEW.current_status,
                COALESCE((SELECT changed_at FROM experiment_status_change_context WHERE experiment_id = NEW.id), NEW.updated_at),
                COALESCE((SELECT reason FROM experiment_status_change_context WHERE experiment_id = NEW.id), 'Direkte Statusänderung ohne Repository-Kontext')
            );
            INSERT INTO evidence_ledger (
                hypothesis_id, event_type, event_at, summary, experiment_id, metadata_json
            ) VALUES (
                NEW.hypothesis_id,
                'experiment_status_changed',
                COALESCE((SELECT changed_at FROM experiment_status_change_context WHERE experiment_id = NEW.id), NEW.updated_at),
                COALESCE((SELECT reason FROM experiment_status_change_context WHERE experiment_id = NEW.id), 'Direkte Statusänderung ohne Repository-Kontext'),
                NEW.id,
                json_object('from_status', OLD.current_status, 'to_status', NEW.current_status)
            );
            DELETE FROM experiment_status_change_context WHERE experiment_id = NEW.id;
        END;
    """,
    2: """
        CREATE TABLE external_references (
            id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL CHECK(target_type IN ('source', 'hypothesis', 'experiment', 'result')),
            target_id TEXT NOT NULL,
            system TEXT NOT NULL,
            record_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            uri TEXT,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(target_type, target_id, system, record_type, record_id)
        );
        CREATE INDEX idx_external_references_target ON external_references(target_type, target_id);
        CREATE INDEX idx_external_references_record ON external_references(system, record_type, record_id);
        CREATE TRIGGER external_references_no_update
        BEFORE UPDATE ON external_references BEGIN
            SELECT RAISE(ABORT, 'external_references is append-only');
        END;
        CREATE TRIGGER external_references_no_delete
        BEFORE DELETE ON external_references BEGIN
            SELECT RAISE(ABORT, 'external_references is append-only');
        END;
        CREATE TRIGGER external_reference_source_exists
        BEFORE INSERT ON external_references
        WHEN NEW.target_type = 'source'
          AND NOT EXISTS (SELECT 1 FROM research_sources WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'external reference source target does not exist');
        END;
        CREATE TRIGGER external_reference_hypothesis_exists
        BEFORE INSERT ON external_references
        WHEN NEW.target_type = 'hypothesis'
          AND NOT EXISTS (SELECT 1 FROM hypotheses WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'external reference hypothesis target does not exist');
        END;
        CREATE TRIGGER external_reference_experiment_exists
        BEFORE INSERT ON external_references
        WHEN NEW.target_type = 'experiment'
          AND NOT EXISTS (SELECT 1 FROM experiments WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'external reference experiment target does not exist');
        END;
        CREATE TRIGGER external_reference_result_exists
        BEFORE INSERT ON external_references
        WHEN NEW.target_type = 'result'
          AND NOT EXISTS (SELECT 1 FROM research_results WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'external reference result target does not exist');
        END;
    """,
    3: f"""
        CREATE TABLE source_claims (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES research_sources(id),
            claim_text TEXT NOT NULL,
            normalized_claim TEXT NOT NULL,
            claim_fingerprint TEXT NOT NULL,
            original_market_scope TEXT NOT NULL,
            extraction_notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(source_id, claim_fingerprint)
        );

        CREATE TABLE source_claim_matches (
            id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL REFERENCES source_claims(id),
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            similarity_score REAL NOT NULL CHECK(similarity_score >= 0 AND similarity_score <= 1),
            exact_claim_match INTEGER NOT NULL CHECK(exact_claim_match IN (0, 1)),
            hypothesis_status TEXT NOT NULL,
            was_rejected INTEGER NOT NULL CHECK(was_rejected IN (0, 1)),
            source_count INTEGER NOT NULL CHECK(source_count >= 0),
            experiment_count INTEGER NOT NULL CHECK(experiment_count >= 0),
            result_count INTEGER NOT NULL CHECK(result_count >= 0),
            rejection_reason TEXT,
            matched_at TEXT NOT NULL,
            UNIQUE(claim_id, hypothesis_id)
        );

        CREATE TABLE source_claim_resolutions (
            id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL REFERENCES source_claims(id),
            resolution TEXT NOT NULL CHECK(resolution IN ({_quoted(ALLOWED_CLAIM_RESOLUTIONS)})),
            hypothesis_id TEXT REFERENCES hypotheses(id),
            new_evidence_basis TEXT CHECK(
                new_evidence_basis IS NULL OR
                new_evidence_basis IN ({_quoted(ALLOWED_RETEST_BASES)})
            ),
            rationale TEXT NOT NULL,
            resolved_at TEXT NOT NULL,
            CHECK(
                resolution IN ('DEFERRED', 'NO_ACTION') OR hypothesis_id IS NOT NULL
            )
        );

        CREATE TABLE hypothesis_evidence_assessments (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            source_id TEXT REFERENCES research_sources(id),
            strength TEXT NOT NULL CHECK(strength IN ({_quoted(ALLOWED_EVIDENCE_STRENGTHS)})),
            confidence REAL CHECK(confidence IS NULL OR (confidence >= 0 AND confidence <= 100)),
            rationale TEXT NOT NULL,
            assessed_at TEXT NOT NULL
        );

        CREATE TABLE application_capability_assessments (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            experiment_id TEXT REFERENCES experiments(id),
            outcome TEXT NOT NULL CHECK(outcome IN ({_quoted(ALLOWED_CAPABILITY_OUTCOMES)})),
            feature_available INTEGER NOT NULL CHECK(feature_available IN (0, 1)),
            required_data_available INTEGER NOT NULL CHECK(required_data_available IN (0, 1)),
            existing_research_test INTEGER NOT NULL CHECK(existing_research_test IN (0, 1)),
            market_scope_reviewed INTEGER NOT NULL CHECK(market_scope_reviewed IN (0, 1)),
            active_rule_exists INTEGER NOT NULL CHECK(active_rule_exists IN (0, 1)),
            infrastructure_needed TEXT NOT NULL,
            existing_assets_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            assessed_at TEXT NOT NULL
        );

        CREATE TABLE integration_candidates (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            result_id TEXT NOT NULL REFERENCES research_results(id),
            candidate_status TEXT NOT NULL DEFAULT 'INTEGRATION_CANDIDATE'
                CHECK(candidate_status = 'INTEGRATION_CANDIDATE'),
            feature_combination_json TEXT NOT NULL,
            incremental_value_assessment TEXT NOT NULL,
            oos_walk_forward_assessment TEXT NOT NULL,
            forward_paper_assessment TEXT NOT NULL,
            sample_size_assessment TEXT NOT NULL,
            costs_slippage_assessment TEXT NOT NULL,
            feature_redundancy_assessment TEXT NOT NULL,
            complexity_assessment TEXT NOT NULL,
            overfiltering_assessment TEXT NOT NULL,
            market_scope_assessment TEXT NOT NULL,
            simpler_variant_assessment TEXT NOT NULL,
            baseline_trade_count INTEGER NOT NULL CHECK(baseline_trade_count >= 0),
            candidate_trade_count INTEGER NOT NULL CHECK(candidate_trade_count >= 0),
            incremental_value_confirmed INTEGER NOT NULL CHECK(incremental_value_confirmed IN (0, 1)),
            oos_walk_forward_confirmed INTEGER NOT NULL CHECK(oos_walk_forward_confirmed IN (0, 1)),
            forward_paper_confirmed INTEGER NOT NULL CHECK(forward_paper_confirmed IN (0, 1)),
            sample_size_sufficient INTEGER NOT NULL CHECK(sample_size_sufficient IN (0, 1)),
            costs_included INTEGER NOT NULL CHECK(costs_included IN (0, 1)),
            redundancy_acceptable INTEGER NOT NULL CHECK(redundancy_acceptable IN (0, 1)),
            complexity_justified INTEGER NOT NULL CHECK(complexity_justified IN (0, 1)),
            overfiltering_acceptable INTEGER NOT NULL CHECK(overfiltering_acceptable IN (0, 1)),
            trade_count_acceptable INTEGER NOT NULL CHECK(trade_count_acceptable IN (0, 1)),
            market_scope_validated INTEGER NOT NULL CHECK(market_scope_validated IN (0, 1)),
            simpler_solution_preferred INTEGER NOT NULL CHECK(simpler_solution_preferred IN (0, 1)),
            limitations TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(hypothesis_id, result_id)
        );

        CREATE TABLE integration_decisions (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES integration_candidates(id),
            decision TEXT NOT NULL CHECK(decision IN ({_quoted(ALLOWED_INTEGRATION_DECISIONS)})),
            rationale TEXT NOT NULL,
            decided_by TEXT NOT NULL,
            decided_at TEXT NOT NULL
        );

        CREATE TABLE integration_events (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES integration_candidates(id),
            decision_id TEXT NOT NULL REFERENCES integration_decisions(id),
            event_type TEXT NOT NULL CHECK(event_type IN ({_quoted(ALLOWED_INTEGRATION_EVENTS)})),
            implementation_reference TEXT NOT NULL,
            summary TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );

        CREATE TABLE market_scope_assessments (
            id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL CHECK(target_type IN ({_quoted(ALLOWED_MARKET_SCOPE_TARGETS)})),
            target_id TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            region TEXT NOT NULL,
            universe TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            scope_notes TEXT NOT NULL,
            assessed_at TEXT NOT NULL
        );

        CREATE INDEX idx_source_claims_source ON source_claims(source_id, created_at);
        CREATE INDEX idx_source_claims_fingerprint ON source_claims(claim_fingerprint);
        CREATE INDEX idx_source_claim_matches_claim ON source_claim_matches(claim_id, similarity_score DESC);
        CREATE INDEX idx_source_claim_resolutions_claim ON source_claim_resolutions(claim_id, resolved_at);
        CREATE INDEX idx_evidence_assessments_hypothesis ON hypothesis_evidence_assessments(hypothesis_id, assessed_at);
        CREATE INDEX idx_capability_assessments_hypothesis ON application_capability_assessments(hypothesis_id, assessed_at);
        CREATE INDEX idx_integration_candidates_hypothesis ON integration_candidates(hypothesis_id, created_at);
        CREATE INDEX idx_integration_decisions_candidate ON integration_decisions(candidate_id, decided_at);
        CREATE INDEX idx_integration_events_candidate ON integration_events(candidate_id, occurred_at);
        CREATE INDEX idx_market_scope_target ON market_scope_assessments(target_type, target_id, assessed_at);
        CREATE INDEX idx_market_scope_search ON market_scope_assessments(asset_class, region, timeframe);

        INSERT INTO hypothesis_evidence_assessments (
            id, hypothesis_id, source_id, strength, confidence, rationale, assessed_at
        )
        SELECT
            lower(hex(randomblob(16))),
            id,
            NULL,
            external_evidence,
            NULL,
            'Initiale Evidenzeinstufung aus dem bestehenden Hypotheseneintrag.',
            created_at
        FROM hypotheses;

        CREATE TRIGGER source_claims_no_update
        BEFORE UPDATE ON source_claims BEGIN
            SELECT RAISE(ABORT, 'source_claims is append-only');
        END;
        CREATE TRIGGER source_claims_no_delete
        BEFORE DELETE ON source_claims BEGIN
            SELECT RAISE(ABORT, 'source_claims is append-only');
        END;
        CREATE TRIGGER source_claim_matches_no_update
        BEFORE UPDATE ON source_claim_matches BEGIN
            SELECT RAISE(ABORT, 'source_claim_matches is append-only');
        END;
        CREATE TRIGGER source_claim_matches_no_delete
        BEFORE DELETE ON source_claim_matches BEGIN
            SELECT RAISE(ABORT, 'source_claim_matches is append-only');
        END;
        CREATE TRIGGER source_claim_resolutions_no_update
        BEFORE UPDATE ON source_claim_resolutions BEGIN
            SELECT RAISE(ABORT, 'source_claim_resolutions is append-only');
        END;
        CREATE TRIGGER source_claim_resolutions_no_delete
        BEFORE DELETE ON source_claim_resolutions BEGIN
            SELECT RAISE(ABORT, 'source_claim_resolutions is append-only');
        END;
        CREATE TRIGGER hypothesis_evidence_assessments_no_update
        BEFORE UPDATE ON hypothesis_evidence_assessments BEGIN
            SELECT RAISE(ABORT, 'hypothesis_evidence_assessments is append-only');
        END;
        CREATE TRIGGER hypothesis_evidence_assessments_no_delete
        BEFORE DELETE ON hypothesis_evidence_assessments BEGIN
            SELECT RAISE(ABORT, 'hypothesis_evidence_assessments is append-only');
        END;
        CREATE TRIGGER application_capability_assessments_no_update
        BEFORE UPDATE ON application_capability_assessments BEGIN
            SELECT RAISE(ABORT, 'application_capability_assessments is append-only');
        END;
        CREATE TRIGGER application_capability_assessments_no_delete
        BEFORE DELETE ON application_capability_assessments BEGIN
            SELECT RAISE(ABORT, 'application_capability_assessments is append-only');
        END;
        CREATE TRIGGER integration_candidates_no_update
        BEFORE UPDATE ON integration_candidates BEGIN
            SELECT RAISE(ABORT, 'integration_candidates is append-only');
        END;
        CREATE TRIGGER integration_candidates_no_delete
        BEFORE DELETE ON integration_candidates BEGIN
            SELECT RAISE(ABORT, 'integration_candidates is append-only');
        END;
        CREATE TRIGGER integration_decisions_no_update
        BEFORE UPDATE ON integration_decisions BEGIN
            SELECT RAISE(ABORT, 'integration_decisions is append-only');
        END;
        CREATE TRIGGER integration_decisions_no_delete
        BEFORE DELETE ON integration_decisions BEGIN
            SELECT RAISE(ABORT, 'integration_decisions is append-only');
        END;
        CREATE TRIGGER integration_events_no_update
        BEFORE UPDATE ON integration_events BEGIN
            SELECT RAISE(ABORT, 'integration_events is append-only');
        END;
        CREATE TRIGGER integration_events_no_delete
        BEFORE DELETE ON integration_events BEGIN
            SELECT RAISE(ABORT, 'integration_events is append-only');
        END;
        CREATE TRIGGER market_scope_assessments_no_update
        BEFORE UPDATE ON market_scope_assessments BEGIN
            SELECT RAISE(ABORT, 'market_scope_assessments is append-only');
        END;
        CREATE TRIGGER market_scope_assessments_no_delete
        BEFORE DELETE ON market_scope_assessments BEGIN
            SELECT RAISE(ABORT, 'market_scope_assessments is append-only');
        END;

        CREATE TRIGGER hypothesis_evidence_source_must_be_linked
        BEFORE INSERT ON hypothesis_evidence_assessments
        WHEN NEW.source_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM hypothesis_sources
              WHERE hypothesis_id = NEW.hypothesis_id AND source_id = NEW.source_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'evidence source must be linked to hypothesis');
        END;

        CREATE TRIGGER capability_experiment_must_match_hypothesis
        BEFORE INSERT ON application_capability_assessments
        WHEN NEW.experiment_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM experiments
              WHERE id = NEW.experiment_id AND hypothesis_id = NEW.hypothesis_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'capability experiment must belong to hypothesis');
        END;

        CREATE TRIGGER integration_candidate_result_must_match_hypothesis
        BEFORE INSERT ON integration_candidates
        WHEN NOT EXISTS (
            SELECT 1
            FROM research_results r
            JOIN experiments e ON e.id = r.experiment_id
            WHERE r.id = NEW.result_id
              AND e.hypothesis_id = NEW.hypothesis_id
              AND r.conclusion = 'supports'
        )
        BEGIN
            SELECT RAISE(ABORT, 'integration candidate requires a supporting result from this hypothesis');
        END;

        CREATE TRIGGER integration_approval_requires_all_gates
        BEFORE INSERT ON integration_decisions
        WHEN NEW.decision = 'APPROVED_FOR_IMPLEMENTATION'
          AND EXISTS (
              SELECT 1 FROM integration_candidates c
              WHERE c.id = NEW.candidate_id
                AND (
                    c.incremental_value_confirmed = 0 OR
                    c.oos_walk_forward_confirmed = 0 OR
                    c.forward_paper_confirmed = 0 OR
                    c.sample_size_sufficient = 0 OR
                    c.costs_included = 0 OR
                    c.redundancy_acceptable = 0 OR
                    c.complexity_justified = 0 OR
                    c.overfiltering_acceptable = 0 OR
                    c.trade_count_acceptable = 0 OR
                    c.market_scope_validated = 0 OR
                    c.simpler_solution_preferred = 0
                )
          )
        BEGIN
            SELECT RAISE(ABORT, 'integration approval requires all research and simplicity gates');
        END;

        CREATE TRIGGER integration_event_requires_approved_matching_decision
        BEFORE INSERT ON integration_events
        WHEN NEW.event_type = 'INTEGRATED'
          AND NOT EXISTS (
              SELECT 1 FROM integration_decisions d
              WHERE d.id = NEW.decision_id
                AND d.candidate_id = NEW.candidate_id
                AND d.decision = 'APPROVED_FOR_IMPLEMENTATION'
          )
        BEGIN
            SELECT RAISE(ABORT, 'integration event requires an approved matching decision');
        END;

        CREATE TRIGGER market_scope_source_claim_exists
        BEFORE INSERT ON market_scope_assessments
        WHEN NEW.target_type = 'source_claim'
          AND NOT EXISTS (SELECT 1 FROM source_claims WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'market scope source claim target does not exist');
        END;
        CREATE TRIGGER market_scope_hypothesis_exists
        BEFORE INSERT ON market_scope_assessments
        WHEN NEW.target_type = 'hypothesis'
          AND NOT EXISTS (SELECT 1 FROM hypotheses WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'market scope hypothesis target does not exist');
        END;
        CREATE TRIGGER market_scope_experiment_exists
        BEFORE INSERT ON market_scope_assessments
        WHEN NEW.target_type = 'experiment'
          AND NOT EXISTS (SELECT 1 FROM experiments WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'market scope experiment target does not exist');
        END;
        CREATE TRIGGER market_scope_integration_candidate_exists
        BEFORE INSERT ON market_scope_assessments
        WHEN NEW.target_type = 'integration_candidate'
          AND NOT EXISTS (SELECT 1 FROM integration_candidates WHERE id = NEW.target_id)
        BEGIN
            SELECT RAISE(ABORT, 'market scope integration candidate target does not exist');
        END;
    """,
    4: f"""
        CREATE TABLE source_provenance (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES research_sources(id),
            platform TEXT,
            creator TEXT,
            provenance_title TEXT,
            direct_url TEXT,
            normalized_url TEXT,
            content_id TEXT,
            profile_url TEXT,
            published_date TEXT,
            local_filename TEXT,
            file_sha256 TEXT,
            file_size INTEGER CHECK(file_size IS NULL OR file_size >= 0),
            captured_at TEXT NOT NULL,
            provenance TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL,
            provenance_fingerprint TEXT NOT NULL,
            UNIQUE(source_id, provenance_fingerprint)
        );

        CREATE TABLE source_identity_keys (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES research_sources(id),
            provenance_id TEXT NOT NULL REFERENCES source_provenance(id),
            identity_type TEXT NOT NULL CHECK(
                identity_type IN ('platform_content_id', 'normalized_url', 'file_sha256')
            ),
            identity_value TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(identity_type, identity_value)
        );

        CREATE TABLE source_duplicate_assessments (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES research_sources(id),
            possible_duplicate_source_id TEXT NOT NULL REFERENCES research_sources(id),
            decision TEXT NOT NULL CHECK(decision IN ('POSSIBLE_DUPLICATE', 'CONFIRMED_DISTINCT')),
            rationale TEXT NOT NULL,
            assessed_at TEXT NOT NULL,
            CHECK(source_id <> possible_duplicate_source_id),
            UNIQUE(source_id, possible_duplicate_source_id, decision)
        );

        CREATE TABLE research_result_identities (
            idempotency_key TEXT PRIMARY KEY,
            result_id TEXT NOT NULL UNIQUE REFERENCES research_results(id),
            created_at TEXT NOT NULL
        );

        CREATE TABLE result_validation_assessments (
            id TEXT PRIMARY KEY,
            result_id TEXT NOT NULL REFERENCES research_results(id),
            research_type TEXT NOT NULL,
            gate_contract_version TEXT NOT NULL,
            result_direction TEXT NOT NULL CHECK(result_direction IN ({_quoted(ALLOWED_RESULT_DIRECTIONS)})),
            scope_contract_json TEXT NOT NULL,
            result_scope_fingerprint TEXT NOT NULL,
            scope_gate_passed INTEGER NOT NULL CHECK(scope_gate_passed IN (0, 1)),
            oos_status TEXT NOT NULL CHECK(oos_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            walk_forward_status TEXT NOT NULL CHECK(walk_forward_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            external_unseen_status TEXT NOT NULL CHECK(external_unseen_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            forward_status TEXT NOT NULL CHECK(forward_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            paper_status TEXT NOT NULL CHECK(paper_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            sample_size_status TEXT NOT NULL CHECK(sample_size_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            uncertainty_status TEXT NOT NULL CHECK(uncertainty_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            costs_slippage_status TEXT NOT NULL CHECK(costs_slippage_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            data_quality_status TEXT NOT NULL CHECK(data_quality_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            leakage_status TEXT NOT NULL CHECK(leakage_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            pit_status TEXT NOT NULL CHECK(pit_status IN ({_quoted(ALLOWED_VALIDATION_GATE_STATUSES)})),
            critical_blocker INTEGER NOT NULL CHECK(critical_blocker IN (0, 1)),
            limitations TEXT NOT NULL,
            artifact_references_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            assessed_at TEXT NOT NULL
        );

        CREATE TABLE hypothesis_validation_evidence (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            result_id TEXT NOT NULL REFERENCES research_results(id),
            assessment_id TEXT NOT NULL REFERENCES result_validation_assessments(id),
            selected_by TEXT NOT NULL,
            rationale TEXT NOT NULL,
            selected_at TEXT NOT NULL,
            UNIQUE(hypothesis_id, assessment_id)
        );

        CREATE TABLE research_work_requests (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),
            experiment_id TEXT REFERENCES experiments(id),
            source_id TEXT REFERENCES research_sources(id),
            capability_assessment_id TEXT REFERENCES application_capability_assessments(id),
            request_type TEXT NOT NULL CHECK(request_type IN ({_quoted(ALLOWED_WORK_REQUEST_TYPES)})),
            current_status TEXT NOT NULL CHECK(current_status IN ({_quoted(ALLOWED_WORK_REQUEST_STATUSES)})),
            task TEXT NOT NULL,
            expected_output TEXT NOT NULL,
            required_infrastructure TEXT NOT NULL,
            scope_json TEXT NOT NULL,
            safeguards_json TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            claimed_at TEXT,
            completed_at TEXT,
            claimed_by TEXT,
            claim_token TEXT,
            worker_context TEXT,
            result_id TEXT REFERENCES research_results(id),
            result_reference TEXT,
            artifact_references_json TEXT NOT NULL DEFAULT '[]',
            blocker_reason TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE work_request_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_request_id TEXT NOT NULL REFERENCES research_work_requests(id),
            from_status TEXT,
            to_status TEXT NOT NULL CHECK(to_status IN ({_quoted(ALLOWED_WORK_REQUEST_STATUSES)})),
            changed_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE work_request_status_change_context (
            work_request_id TEXT PRIMARY KEY REFERENCES research_work_requests(id),
            changed_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE work_request_result_links (
            id TEXT PRIMARY KEY,
            work_request_id TEXT NOT NULL UNIQUE REFERENCES research_work_requests(id),
            result_id TEXT NOT NULL UNIQUE REFERENCES research_results(id),
            linked_at TEXT NOT NULL
        );

        CREATE INDEX idx_source_provenance_source ON source_provenance(source_id, captured_at, id);
        CREATE INDEX idx_source_provenance_metadata ON source_provenance(platform, creator, published_date);
        CREATE INDEX idx_source_identity_source ON source_identity_keys(source_id, identity_type);
        CREATE INDEX idx_source_duplicate_source ON source_duplicate_assessments(source_id, assessed_at);
        CREATE INDEX idx_result_validation_result ON result_validation_assessments(result_id, assessed_at, id);
        CREATE INDEX idx_validation_evidence_hypothesis ON hypothesis_validation_evidence(hypothesis_id, selected_at, id);
        CREATE INDEX idx_work_requests_status ON research_work_requests(current_status, created_at, id);
        CREATE INDEX idx_work_requests_hypothesis ON research_work_requests(hypothesis_id, created_at, id);
        CREATE INDEX idx_work_status_history_request ON work_request_status_history(work_request_id, changed_at, id);

        CREATE TRIGGER source_provenance_no_update
        BEFORE UPDATE ON source_provenance BEGIN
            SELECT RAISE(ABORT, 'source_provenance is append-only');
        END;
        CREATE TRIGGER source_provenance_no_delete
        BEFORE DELETE ON source_provenance BEGIN
            SELECT RAISE(ABORT, 'source_provenance is append-only');
        END;
        CREATE TRIGGER source_identity_keys_no_update
        BEFORE UPDATE ON source_identity_keys BEGIN
            SELECT RAISE(ABORT, 'source_identity_keys is append-only');
        END;
        CREATE TRIGGER source_identity_keys_no_delete
        BEFORE DELETE ON source_identity_keys BEGIN
            SELECT RAISE(ABORT, 'source_identity_keys is append-only');
        END;
        CREATE TRIGGER source_duplicate_assessments_no_update
        BEFORE UPDATE ON source_duplicate_assessments BEGIN
            SELECT RAISE(ABORT, 'source_duplicate_assessments is append-only');
        END;
        CREATE TRIGGER source_duplicate_assessments_no_delete
        BEFORE DELETE ON source_duplicate_assessments BEGIN
            SELECT RAISE(ABORT, 'source_duplicate_assessments is append-only');
        END;
        CREATE TRIGGER research_result_identities_no_update
        BEFORE UPDATE ON research_result_identities BEGIN
            SELECT RAISE(ABORT, 'research_result_identities is append-only');
        END;
        CREATE TRIGGER research_result_identities_no_delete
        BEFORE DELETE ON research_result_identities BEGIN
            SELECT RAISE(ABORT, 'research_result_identities is append-only');
        END;
        CREATE TRIGGER result_validation_assessments_no_update
        BEFORE UPDATE ON result_validation_assessments BEGIN
            SELECT RAISE(ABORT, 'result_validation_assessments is append-only');
        END;
        CREATE TRIGGER result_validation_assessments_no_delete
        BEFORE DELETE ON result_validation_assessments BEGIN
            SELECT RAISE(ABORT, 'result_validation_assessments is append-only');
        END;
        CREATE TRIGGER hypothesis_validation_evidence_no_update
        BEFORE UPDATE ON hypothesis_validation_evidence BEGIN
            SELECT RAISE(ABORT, 'hypothesis_validation_evidence is append-only');
        END;
        CREATE TRIGGER hypothesis_validation_evidence_no_delete
        BEFORE DELETE ON hypothesis_validation_evidence BEGIN
            SELECT RAISE(ABORT, 'hypothesis_validation_evidence is append-only');
        END;
        CREATE TRIGGER work_request_status_history_no_update
        BEFORE UPDATE ON work_request_status_history BEGIN
            SELECT RAISE(ABORT, 'work_request_status_history is append-only');
        END;
        CREATE TRIGGER work_request_status_history_no_delete
        BEFORE DELETE ON work_request_status_history BEGIN
            SELECT RAISE(ABORT, 'work_request_status_history is append-only');
        END;
        CREATE TRIGGER work_request_result_links_no_update
        BEFORE UPDATE ON work_request_result_links BEGIN
            SELECT RAISE(ABORT, 'work_request_result_links is append-only');
        END;
        CREATE TRIGGER work_request_result_links_no_delete
        BEFORE DELETE ON work_request_result_links BEGIN
            SELECT RAISE(ABORT, 'work_request_result_links is append-only');
        END;

        CREATE TRIGGER research_work_requests_no_delete
        BEFORE DELETE ON research_work_requests BEGIN
            SELECT RAISE(ABORT, 'research_work_requests cannot be deleted');
        END;
        CREATE TRIGGER research_work_requests_core_immutable
        BEFORE UPDATE ON research_work_requests
        WHEN NEW.hypothesis_id IS NOT OLD.hypothesis_id
          OR NEW.experiment_id IS NOT OLD.experiment_id
          OR NEW.source_id IS NOT OLD.source_id
          OR NEW.capability_assessment_id IS NOT OLD.capability_assessment_id
          OR NEW.request_type IS NOT OLD.request_type
          OR NEW.task IS NOT OLD.task
          OR NEW.expected_output IS NOT OLD.expected_output
          OR NEW.required_infrastructure IS NOT OLD.required_infrastructure
          OR NEW.scope_json IS NOT OLD.scope_json
          OR NEW.safeguards_json IS NOT OLD.safeguards_json
          OR NEW.idempotency_key IS NOT OLD.idempotency_key
          OR NEW.created_at IS NOT OLD.created_at
        BEGIN
            SELECT RAISE(ABORT, 'work request definition is immutable; create a new request');
        END;
        CREATE TRIGGER work_request_transition_allowed
        BEFORE UPDATE OF current_status ON research_work_requests
        WHEN OLD.current_status <> NEW.current_status
          AND NOT (
              (OLD.current_status = 'READY' AND NEW.current_status IN ('IN_PROGRESS', 'CANCELLED')) OR
              (OLD.current_status = 'IN_PROGRESS' AND NEW.current_status IN ('COMPLETED', 'BLOCKED', 'CANCELLED')) OR
              (OLD.current_status = 'BLOCKED' AND NEW.current_status IN ('READY', 'CANCELLED'))
          )
        BEGIN
            SELECT RAISE(ABORT, 'invalid work request status transition');
        END;
        CREATE TRIGGER work_request_completion_requires_result
        BEFORE UPDATE OF current_status ON research_work_requests
        WHEN NEW.current_status = 'COMPLETED'
          AND (
              NEW.result_id IS NULL OR
              NOT EXISTS (
                  SELECT 1 FROM work_request_result_links l
                  WHERE l.work_request_id = NEW.id AND l.result_id = NEW.result_id
              )
          )
        BEGIN
            SELECT RAISE(ABORT, 'COMPLETED work request requires its directly linked result');
        END;
        CREATE TRIGGER work_request_status_audit
        AFTER UPDATE OF current_status ON research_work_requests
        WHEN OLD.current_status <> NEW.current_status
        BEGIN
            INSERT INTO work_request_status_history (
                work_request_id, from_status, to_status, changed_at, actor, reason
            ) VALUES (
                NEW.id,
                OLD.current_status,
                NEW.current_status,
                COALESCE((SELECT changed_at FROM work_request_status_change_context WHERE work_request_id = NEW.id), NEW.updated_at),
                COALESCE((SELECT actor FROM work_request_status_change_context WHERE work_request_id = NEW.id), 'unknown'),
                COALESCE((SELECT reason FROM work_request_status_change_context WHERE work_request_id = NEW.id), 'Direkte Statusänderung ohne Repository-Kontext')
            );
            INSERT INTO evidence_ledger (
                hypothesis_id, event_type, event_at, summary, experiment_id, result_id, metadata_json
            ) VALUES (
                NEW.hypothesis_id,
                'work_request_status_changed',
                COALESCE((SELECT changed_at FROM work_request_status_change_context WHERE work_request_id = NEW.id), NEW.updated_at),
                COALESCE((SELECT reason FROM work_request_status_change_context WHERE work_request_id = NEW.id), 'Direkte Statusänderung ohne Repository-Kontext'),
                NEW.experiment_id,
                NEW.result_id,
                json_object('work_request_id', NEW.id, 'from_status', OLD.current_status, 'to_status', NEW.current_status)
            );
            DELETE FROM work_request_status_change_context WHERE work_request_id = NEW.id;
        END;

        CREATE TRIGGER work_request_experiment_matches_hypothesis
        BEFORE INSERT ON research_work_requests
        WHEN NEW.experiment_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM experiments e
              WHERE e.id = NEW.experiment_id AND e.hypothesis_id = NEW.hypothesis_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'work request experiment must belong to hypothesis');
        END;
        CREATE TRIGGER work_request_capability_matches_hypothesis
        BEFORE INSERT ON research_work_requests
        WHEN NEW.capability_assessment_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM application_capability_assessments a
              WHERE a.id = NEW.capability_assessment_id AND a.hypothesis_id = NEW.hypothesis_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'work request capability assessment must belong to hypothesis');
        END;
        CREATE TRIGGER work_request_source_matches_hypothesis
        BEFORE INSERT ON research_work_requests
        WHEN NEW.source_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM hypothesis_sources hs
              WHERE hs.hypothesis_id = NEW.hypothesis_id AND hs.source_id = NEW.source_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'work request source must be linked to hypothesis');
        END;

        CREATE TRIGGER validation_selection_requires_qualified_result
        BEFORE INSERT ON hypothesis_validation_evidence
        WHEN NOT EXISTS (
            SELECT 1
            FROM result_validation_assessments a
            JOIN research_results r ON r.id = a.result_id
            JOIN experiments e ON e.id = r.experiment_id
            WHERE a.id = NEW.assessment_id
              AND a.result_id = NEW.result_id
              AND e.hypothesis_id = NEW.hypothesis_id
              AND e.current_status = 'COMPLETED'
              AND r.conclusion = 'supports'
              AND a.result_direction = 'SUPPORTING'
              AND a.scope_gate_passed = 1
              AND a.oos_status = 'PASSED'
              AND a.walk_forward_status = 'PASSED'
              AND a.external_unseen_status IN ('PASSED', 'NOT_REQUIRED')
              AND a.forward_status IN ('PASSED', 'NOT_REQUIRED')
              AND a.paper_status IN ('PASSED', 'NOT_REQUIRED')
              AND a.sample_size_status = 'PASSED'
              AND a.uncertainty_status = 'PASSED'
              AND a.costs_slippage_status IN ('PASSED', 'NOT_REQUIRED')
              AND a.data_quality_status = 'PASSED'
              AND a.leakage_status = 'PASSED'
              AND a.pit_status = 'PASSED'
              AND a.critical_blocker = 0
        )
        BEGIN
            SELECT RAISE(ABORT, 'validation selection requires a completed supporting result with every applicable gate passed');
        END;

        DROP TRIGGER hypothesis_update_cannot_validate_without_result;
        CREATE TRIGGER hypothesis_update_cannot_validate_without_result
        BEFORE UPDATE OF current_status ON hypotheses
        WHEN NEW.current_status = 'VALIDATED'
          AND OLD.current_status <> 'VALIDATED'
          AND NOT EXISTS (
              SELECT 1 FROM hypothesis_validation_evidence v
              WHERE v.hypothesis_id = NEW.id
          )
        BEGIN
            SELECT RAISE(ABORT, 'VALIDATED requires an explicitly selected supporting result with completed validation gates');
        END;
    """,
    5: f"""
        CREATE TABLE legacy_research_reconciliations (
            candidate_key TEXT PRIMARY KEY,
            candidate_name TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK(outcome IN ({_quoted(ALLOWED_LEGACY_RECONCILIATION_OUTCOMES)})),
            source_id TEXT REFERENCES research_sources(id),
            hypothesis_ids_json TEXT NOT NULL,
            experiment_ids_json TEXT NOT NULL,
            work_request_ids_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            reconciled_at TEXT NOT NULL
        );

        CREATE TRIGGER legacy_research_reconciliations_no_update
        BEFORE UPDATE ON legacy_research_reconciliations BEGIN
            SELECT RAISE(ABORT, 'legacy_research_reconciliations is append-only');
        END;
        CREATE TRIGGER legacy_research_reconciliations_no_delete
        BEFORE DELETE ON legacy_research_reconciliations BEGIN
            SELECT RAISE(ABORT, 'legacy_research_reconciliations is append-only');
        END;
    """,
    6: f"""
        CREATE TABLE source_transcription_records (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES research_sources(id),
            source_fingerprint TEXT NOT NULL,
            content_id TEXT,
            file_sha256 TEXT,
            status TEXT NOT NULL CHECK(status IN ({_quoted(ALLOWED_TRANSCRIPTION_STATUSES)})),
            transcript_path TEXT,
            transcript_sha256 TEXT,
            language TEXT,
            engine TEXT,
            engine_version TEXT,
            model TEXT,
            segments_json TEXT NOT NULL DEFAULT '[]',
            quality_note TEXT NOT NULL,
            machine_generated INTEGER NOT NULL CHECK(machine_generated IN (0, 1)),
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            CHECK(
                (status IN ('EXISTING', 'GENERATED')
                 AND transcript_path IS NOT NULL
                 AND transcript_sha256 IS NOT NULL)
                OR
                (status IN ('NOT_REQUIRED', 'FAILED', 'INSUFFICIENT_AUDIO')
                 AND transcript_path IS NULL
                 AND transcript_sha256 IS NULL)
            ),
            CHECK(status <> 'GENERATED' OR machine_generated = 1),
            CHECK(status <> 'GENERATED' OR (engine IS NOT NULL AND model IS NOT NULL))
        );

        CREATE INDEX idx_source_transcriptions_source
            ON source_transcription_records(source_id, created_at, id);
        CREATE INDEX idx_source_transcriptions_file
            ON source_transcription_records(file_sha256, created_at, id);

        CREATE TRIGGER source_transcription_source_fingerprint_exists
        BEFORE INSERT ON source_transcription_records
        WHEN NOT EXISTS (
            SELECT 1 FROM source_provenance p
            WHERE p.source_id = NEW.source_id
              AND p.source_fingerprint = NEW.source_fingerprint
        )
        BEGIN
            SELECT RAISE(ABORT, 'transcript fingerprint must belong to source provenance');
        END;

        CREATE TRIGGER source_transcription_records_no_update
        BEFORE UPDATE ON source_transcription_records BEGIN
            SELECT RAISE(ABORT, 'source_transcription_records is append-only');
        END;
        CREATE TRIGGER source_transcription_records_no_delete
        BEFORE DELETE ON source_transcription_records BEGIN
            SELECT RAISE(ABORT, 'source_transcription_records is append-only');
        END;
    """,
}


@contextmanager
def database(path: Path = DEFAULT_DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path = DEFAULT_DATABASE_PATH) -> None:
    with database(Path(path)) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                "Die Research-Knowledge-Base stammt aus einer neueren App-Version "
                f"(Schema {version}, unterstützt bis {CURRENT_SCHEMA_VERSION})."
            )
        for target_version in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
            migration = SCHEMA_MIGRATIONS.get(target_version)
            if migration is None:
                raise RuntimeError(f"Fehlende Knowledge-Base-Migration {target_version}.")
            connection.executescript(migration)
            connection.execute(f"PRAGMA user_version = {target_version}")
