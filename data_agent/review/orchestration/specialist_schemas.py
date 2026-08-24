"""Structured-output schemas for the specialist analyst and verifier LLMs."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.verification import (
    VerificationQuestion,
    VerifierDecision,
)

MAX_ANALYST_FINDINGS = 8
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
    # Pydantic supports narrowing nested models at an output boundary; list invariance
    # makes the otherwise-safe Finding override opaque to mypy.
    evidence: list[AnalystEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=4
    )
    analysis_performed: list[ShortAnalystText] = Field(default_factory=list, max_length=4)
    alternative_explanations: list[ShortAnalystText] = Field(
        default_factory=list, max_length=3
    )
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
    """The flash analyst's structured output (one pass over the material)."""

    findings: list[AnalystFinding] = Field(
        default_factory=list, max_length=MAX_ANALYST_FINDINGS
    )
    revision_notes: str = Field(default="", max_length=600)
    """On REVISE rounds: how the analyst addressed the verifier's feedback."""

    @field_validator("findings", mode="before")
    @classmethod
    def _coerce_finding_models(cls, value: object) -> object:
        """Let injected tests and internal callers supply the base domain model."""
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


class VerifierOutput(BaseModel):
    """The pro verifier's structured verdict for a single finding."""

    finding_id: str
    decision: VerifierDecision
    questions: list[VerificationQuestion] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    feedback: str = ""
    evidence_inaccessible: bool = False


