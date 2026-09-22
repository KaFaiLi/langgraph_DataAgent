"""Structured-output schemas for specialist analyst, challenger, and adjudicator models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.verification import (
    CandidateDispositionRecord,
    ChallengeResult,
    VerifierDecision,
)

MAX_ANALYST_FINDINGS = 8
MAX_CANDIDATE_DISPOSITIONS = 64
ShortAnalystText = Annotated[str, Field(max_length=300)]


class AnalystEvidenceReference(EvidenceReference):
    """Concise evidence pointer used only at the structured-generation boundary."""

    locator: str = Field(max_length=500)
    quote: str | None = Field(default=None, max_length=500)


class AnalystFinding(Finding):
    """Output-bounded finding contract for reliable structured generation."""

    finding_id: str = Field(max_length=80)
    title: str = Field(max_length=160)
    category: str = Field(max_length=100)
    claim: str = Field(max_length=700)
    # Pydantic supports narrowing nested models at an output boundary; list
    # invariance makes the otherwise-safe Finding override opaque to mypy.
    evidence: list[AnalystEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=4
    )
    analysis_performed: list[ShortAnalystText] = Field(default_factory=list, max_length=4)
    alternative_explanations: list[ShortAnalystText] = Field(default_factory=list, max_length=3)
    counter_evidence: list[AnalystEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=3
    )
    recommendation: str | None = Field(default=None, max_length=400)

    @field_validator("finding_id", mode="before")
    @classmethod
    def _bound_finding_id(cls, value: object) -> object:
        return value[:80] if isinstance(value, str) else value

    @field_validator("title", mode="before")
    @classmethod
    def _bound_title(cls, value: object) -> object:
        return value[:160] if isinstance(value, str) else value

    @field_validator("category", mode="before")
    @classmethod
    def _bound_category(cls, value: object) -> object:
        return value[:100] if isinstance(value, str) else value

    @field_validator("claim", mode="before")
    @classmethod
    def _bound_claim(cls, value: object) -> object:
        return value[:700] if isinstance(value, str) else value

    @field_validator("recommendation", mode="before")
    @classmethod
    def _bound_recommendation(cls, value: object) -> object:
        return value[:400] if isinstance(value, str) else value

    @field_validator("evidence", mode="before")
    @classmethod
    def _bound_evidence(cls, value: object) -> object:
        return value[:4] if isinstance(value, list) else value

    @field_validator("counter_evidence", mode="before")
    @classmethod
    def _bound_counter_evidence(cls, value: object) -> object:
        return value[:3] if isinstance(value, list) else value

    @field_validator("analysis_performed", mode="before")
    @classmethod
    def _bound_analysis(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:300] if isinstance(item, str) else item for item in value[:4]]

    @field_validator("alternative_explanations", mode="before")
    @classmethod
    def _bound_alternatives(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:300] if isinstance(item, str) else item for item in value[:3]]


class AnalystOutput(BaseModel):
    """The low-cost analyst's structured output (one pass over the material)."""

    findings: list[AnalystFinding] = Field(default_factory=list, max_length=MAX_ANALYST_FINDINGS)
    revision_notes: str = Field(default="", max_length=600)
    candidate_dispositions: list[CandidateDispositionRecord] = Field(
        default_factory=list, max_length=MAX_CANDIDATE_DISPOSITIONS
    )

    @field_validator("findings", mode="before")
    @classmethod
    def _coerce_finding_models(cls, value: object) -> object:
        """Let injected tests and internal callers supply base domain models."""
        if not isinstance(value, list):
            return value
        return [
            item.model_dump(mode="json") if isinstance(item, Finding) else item
            for item in value[:MAX_ANALYST_FINDINGS]
        ]

    @field_validator("revision_notes", mode="before")
    @classmethod
    def _bound_revision_notes(cls, value: object) -> object:
        return value[:600] if isinstance(value, str) else value

    @field_validator("candidate_dispositions", mode="before")
    @classmethod
    def _bound_candidate_dispositions(cls, value: object) -> object:
        return value[:MAX_CANDIDATE_DISPOSITIONS] if isinstance(value, list) else value


MAX_CHALLENGES = 12
MAX_CHALLENGE_EVIDENCE = 8


class ChallengerChallenge(ChallengeResult):
    """Output-bounded challenge record emitted by the low-cost challenger."""

    explanation: str = Field(default="", max_length=1_200)
    evidence: list[AnalystEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=MAX_CHALLENGE_EVIDENCE
    )


class ChallengerOutput(BaseModel):
    """Independent adversarial research; it contains no decision field."""

    finding_id: str = Field(max_length=80)
    challenges: list[ChallengerChallenge] = Field(default_factory=list, max_length=MAX_CHALLENGES)
    strongest_counter_hypothesis: str | None = Field(default=None, max_length=1_200)
    contradictory_evidence: list[AnalystEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=MAX_CHALLENGE_EVIDENCE
    )
    unresolved_questions: list[ShortAnalystText] = Field(default_factory=list, max_length=12)
    research_complete: bool = True

    @field_validator("finding_id", mode="before")
    @classmethod
    def _bound_finding_id(cls, value: object) -> object:
        return value[:80] if isinstance(value, str) else value

    @field_validator("challenges", mode="before")
    @classmethod
    def _bound_challenges(cls, value: object) -> object:
        return value[:MAX_CHALLENGES] if isinstance(value, list) else value

    @field_validator("unresolved_questions", mode="before")
    @classmethod
    def _bound_questions(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:300] if isinstance(item, str) else item for item in value[:12]]


class AdjudicatorOutput(BaseModel):
    """High-cost, no-tool decision over one finding and its challenge case."""

    finding_id: str = Field(max_length=80)
    decision: VerifierDecision
    feedback: str = Field(default="", max_length=1_500)
    checks: list[ShortAnalystText] = Field(default_factory=list, max_length=24)
    analyst_response: str | None = Field(default=None, max_length=1_200)

    @field_validator("finding_id", mode="before")
    @classmethod
    def _bound_finding_id(cls, value: object) -> object:
        return value[:80] if isinstance(value, str) else value

    @field_validator("checks", mode="before")
    @classmethod
    def _bound_checks(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:300] if isinstance(item, str) else item for item in value[:24]]


__all__ = [
    "MAX_ANALYST_FINDINGS",
    "MAX_CANDIDATE_DISPOSITIONS",
    "MAX_CHALLENGES",
    "AdjudicatorOutput",
    "AnalystEvidenceReference",
    "AnalystFinding",
    "AnalystOutput",
    "ChallengerChallenge",
    "ChallengerOutput",
]
