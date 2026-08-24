"""Durable, research-only knowledge base for investment hypotheses.

The package deliberately has no dependency on trading, scoring, scanning or order
code.  Consumers must opt in explicitly and may only use the stored knowledge for
research workflows.
"""

from .schema import (
    ALLOWED_AREAS,
    ALLOWED_CAPABILITY_OUTCOMES,
    ALLOWED_CLAIM_RESOLUTIONS,
    ALLOWED_EVIDENCE_STRENGTHS,
    ALLOWED_HYPOTHESIS_STATUSES,
    ALLOWED_RATINGS,
    ALLOWED_INTEGRATION_DECISIONS,
    ALLOWED_SOURCE_TYPES,
    CURRENT_SCHEMA_VERSION,
    DEFAULT_DATABASE_PATH,
    RATING_GUIDANCE,
    initialize_database,
)
from .store import ResearchKnowledgeBase
from .workflow import ResearchWorkflow

__all__ = [
    "ALLOWED_AREAS",
    "ALLOWED_CAPABILITY_OUTCOMES",
    "ALLOWED_CLAIM_RESOLUTIONS",
    "ALLOWED_EVIDENCE_STRENGTHS",
    "ALLOWED_HYPOTHESIS_STATUSES",
    "ALLOWED_RATINGS",
    "ALLOWED_INTEGRATION_DECISIONS",
    "ALLOWED_SOURCE_TYPES",
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_DATABASE_PATH",
    "ResearchKnowledgeBase",
    "ResearchWorkflow",
    "RATING_GUIDANCE",
    "initialize_database",
]
