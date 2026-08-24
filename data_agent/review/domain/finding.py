"""Findings: the core unit of a specialist review."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange


class VerificationStatus(StrEnum):
    """Where a finding stands in the bounded verifier loop."""

    PENDING = "pending"
    PASSED = "passed"
    REVISED = "revised"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class Finding(BaseModel):
    """One evidence-backed claim produced by a specialist analyst."""

    finding_id: str
    title: str
    category: str

    severity: Severity
    confidence: float

    claim: str

    period: DateRange | None = None

    evidence: list[EvidenceReference] = Field(default_factory=list)

    analysis_performed: list[str] = Field(default_factory=list)

    alternative_explanations: list[str] = Field(default_factory=list)

    counter_evidence: list[EvidenceReference] = Field(default_factory=list)

    verifier_status: VerificationStatus = VerificationStatus.PENDING

    recommendation: str | None = None

    is_observation: bool = False
    """Observations (facts with no conclusion) may omit evidence references."""

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return value

    def assert_evidence_policy(self) -> None:
        """Enforce spec: evidence is mandatory for non-observation conclusions.

        The verifier calls this before passing a finding; analyst drafts may
        construct findings without evidence and fail verification.
        """
        if not self.is_observation and not self.evidence:
            raise ValueError(
                f"finding {self.finding_id}: non-observation conclusions "
                "require at least one evidence reference"
            )
