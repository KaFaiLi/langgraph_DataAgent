"""Graph-independent structured lead output contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.reports import FinalFinding

MAX_LEAD_FINDINGS = 8
MAX_LEAD_LIST_ITEMS = 8
MAX_LEAD_UNRESOLVED_ITEMS = 32
MAX_FINAL_FINDING_EVIDENCE = 12
MAX_LOCATOR_OWNERS_FOR_DERIVATION = 2
LeadNarrativeItem = Annotated[str, Field(max_length=500)]


class LeadEvidenceReference(EvidenceReference):
    """Concise evidence pointer used only at the lead generation boundary."""

    locator: str = Field(max_length=500)
    quote: str | None = Field(default=None, max_length=500)

    @field_validator("quote", mode="before")
    @classmethod
    def _bound_quote(cls, value: object) -> object:
        return value[:500] if isinstance(value, str) else value


class LeadFinalFinding(FinalFinding):
    """Output-bounded final finding for reliable lead structured generation."""

    final_id: str = Field(max_length=80)
    title: str = Field(max_length=200)
    statement: str = Field(max_length=900)
    derived_from: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[LeadEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=6
    )
    cross_source_cluster_ids: list[str] = Field(default_factory=list, max_length=6)
    unresolved_dependencies: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("final_id", mode="before")
    @classmethod
    def _bound_final_id(cls, value: object) -> object:
        return value[:80] if isinstance(value, str) else value

    @field_validator("title", mode="before")
    @classmethod
    def _bound_title(cls, value: object) -> object:
        return value[:200] if isinstance(value, str) else value

    @field_validator("statement", mode="before")
    @classmethod
    def _bound_statement(cls, value: object) -> object:
        return value[:900] if isinstance(value, str) else value

    @field_validator("derived_from", mode="before")
    @classmethod
    def _bound_derived_from(cls, value: object) -> object:
        return value[:8] if isinstance(value, list) else value

    @field_validator("evidence", mode="before")
    @classmethod
    def _bound_evidence(cls, value: object) -> object:
        return value[:6] if isinstance(value, list) else value

    @field_validator("cross_source_cluster_ids", mode="before")
    @classmethod
    def _bound_clusters(cls, value: object) -> object:
        return value[:6] if isinstance(value, list) else value

    @field_validator("unresolved_dependencies", mode="before")
    @classmethod
    def _bound_dependencies(cls, value: object) -> object:
        return value[:8] if isinstance(value, list) else value


class LeadDraft(BaseModel):
    """Bounded interpretive fields produced by the lead model.

    Deterministic clusters, the evidence index, and specialist references are
    assembled by Python after synthesis. Keeping those copied structures out
    of the model response materially reduces long structured calls without
    removing any analytical input.
    """

    executive_summary: str = Field(max_length=2_500)
    overall_desk_risk_assessment: str = Field(max_length=1_800)
    key_findings: list[LeadFinalFinding] = Field(default_factory=list, max_length=MAX_LEAD_FINDINGS)
    potential_unauthorized_activity_indicators: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )
    control_weaknesses: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )
    pnl_risk_inconsistencies: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )
    unresolved_questions: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_UNRESOLVED_ITEMS
    )
    recommended_follow_up: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )

    @field_validator("executive_summary", mode="before")
    @classmethod
    def _bound_summary(cls, value: object) -> object:
        return value[:2_500] if isinstance(value, str) else value

    @field_validator("overall_desk_risk_assessment", mode="before")
    @classmethod
    def _bound_assessment(cls, value: object) -> object:
        return value[:1_800] if isinstance(value, str) else value

    @field_validator("key_findings", mode="before")
    @classmethod
    def _bound_key_findings(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [
            item.model_dump(mode="json") if isinstance(item, FinalFinding) else item
            for item in value[:MAX_LEAD_FINDINGS]
        ]

    @field_validator(
        "potential_unauthorized_activity_indicators",
        "control_weaknesses",
        "pnl_risk_inconsistencies",
        "recommended_follow_up",
        mode="before",
    )
    @classmethod
    def _bound_narrative_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:500] if isinstance(item, str) else item for item in value[:8]]

    @field_validator("unresolved_questions", mode="before")
    @classmethod
    def _bound_unresolved(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:500] if isinstance(item, str) else item for item in value[:32]]


from data_agent.review.domain.verification import LeadChallenge, VerifierDecision

MAX_LEAD_CHALLENGES = 32
MAX_LEAD_CHECKS = 64
MAX_LEAD_FEEDBACK = 4_000


class LeadVerifierOutput(BaseModel):
    """The lead verifier's structured verdict."""

    decision: VerifierDecision
    feedback: str = Field(default="", max_length=MAX_LEAD_FEEDBACK)
    checks: list[str] = Field(default_factory=list, max_length=MAX_LEAD_CHECKS)
    challenges: list[LeadChallenge] = Field(
        default_factory=list,
        max_length=MAX_LEAD_CHALLENGES,
    )

    @field_validator("feedback", mode="before")
    @classmethod
    def _bound_feedback(cls, value: object) -> object:
        return value[:MAX_LEAD_FEEDBACK] if isinstance(value, str) else value

    @field_validator("checks", mode="before")
    @classmethod
    def _bound_checks(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:500] if isinstance(item, str) else item for item in value[:MAX_LEAD_CHECKS]]

    @field_validator("challenges", mode="before")
    @classmethod
    def _bound_challenges(cls, value: object) -> object:
        return value[:MAX_LEAD_CHALLENGES] if isinstance(value, list) else value
