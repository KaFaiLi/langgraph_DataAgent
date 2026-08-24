"""Verifier contracts: decisions, challenge questions, results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class VerifierDecision(StrEnum):
    """Outcome of one verifier pass over one finding."""

    PASS = "pass"
    REVISE = "revise"
    REJECT = "reject"
    UNRESOLVED = "unresolved"


class VerificationQuestion(BaseModel):
    """One challenge question the verifier must answer for a finding.

    The standard challenge set (spec section 15) includes: source support,
    reproducibility, outlier-only basis, contrary evidence, timing, causation
    vs. correlation, benign explanations, control-version effectiveness,
    cross-source contradictions, and severity calibration.
    """

    question: str
    answer: str | None = None
    pass_required: bool = True
    """When True, an affirmative answer is required for the finding to PASS."""


class VerifierResult(BaseModel):
    """The verifier's structured verdict for one finding."""

    finding_id: str
    decision: VerifierDecision
    questions: list[VerificationQuestion] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    """Deterministic checks performed (e.g. locator reopened, calc reproduced)."""

    feedback: str = ""
    """For REVISE: concrete instructions back to the analyst."""

    evidence_inaccessible: bool = False
    """True when a cited locator could not be reopened - never silently pass."""


class VerificationRound(BaseModel):
    """One complete analyst/verifier round for one finding (rendered in the report)."""

    round_number: int
    decision: VerifierDecision
    questions: list[VerificationQuestion] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    feedback: str = ""
    analyst_response: str | None = None
    """The analyst's revision notes answering the previous round's feedback."""


