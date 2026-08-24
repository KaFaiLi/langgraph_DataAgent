"""Deterministic source ingestion: parsing, cataloguing, evidence reopening.

No LLM is involved in file type detection, hashing, sheet discovery, row
counts, column discovery, or date-range extraction. The low-cost model is only
ever consulted later, for semantic classification of uncategorized sources.
"""

from data_agent.review.ingestion.catalog import build_catalog, guess_domains_from_path
from data_agent.review.ingestion.evidence_reader import (
    LocatorValidationError,
    reopen_locator,
    validate_locator,
)
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceFailureCode,
    EvidenceValidationResult,
    EvidenceValidationSummary,
    EvidenceValidator,
)

__all__ = [
    "LocatorValidationError",
    "build_catalog",
    "guess_domains_from_path",
    "reopen_locator",
    "validate_locator",
    "EvidenceDisposition",
    "EvidenceFailureCode",
    "EvidenceValidationResult",
    "EvidenceValidationSummary",
    "EvidenceValidator",
]
