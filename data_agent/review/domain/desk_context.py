"""Shared desk context: one immutable view of the desk under review.

Facts carry provenance and agents may never promote ``INFERRED`` into
``SOURCE_BACKED`` (spec section 20): only facts with evidence references are
classified source-backed, and that classification is enforced here, in code.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from data_agent.review.domain.evidence import EvidenceReference


class FactProvenance(StrEnum):
    """How a desk fact is grounded."""

    SOURCE_BACKED = "source_backed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class DeskFact(BaseModel):
    """One statement about the desk under review."""

    fact_id: str
    statement: str
    provenance: FactProvenance = FactProvenance.UNKNOWN
    evidence: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def _source_backed_requires_evidence(self) -> DeskFact:
        if self.provenance is FactProvenance.SOURCE_BACKED and not self.evidence:
            raise ValueError(
                f"fact {self.fact_id}: SOURCE_BACKED facts require evidence references"
            )
        return self


class RiskLimit(BaseModel):
    """A versioned risk limit definition."""

    limit_id: str
    name: str
    metric: str
    value: float
    unit: str
    effective_from: date | None = None
    effective_to: date | None = None
    version: int = 1

    def effective_on(self, day: date) -> bool:
        after_start = self.effective_from is None or day >= self.effective_from
        before_end = self.effective_to is None or day <= self.effective_to
        return after_start and before_end


class ControlDefinition(BaseModel):
    """A versioned control definition (e.g. a post-trade mapping rule)."""

    control_id: str
    name: str
    description: str
    effective_from: date | None = None
    effective_to: date | None = None

    def effective_on(self, day: date) -> bool:
        after_start = self.effective_from is None or day >= self.effective_from
        before_end = self.effective_to is None or day <= self.effective_to
        return after_start and before_end


class DeskContext(BaseModel):
    """Immutable desk background shared by every specialist (spec section 20)."""

    desk_name: str
    business_description: str
    products: list[str] = Field(default_factory=list)
    currencies: list[str] = Field(default_factory=list)
    risk_metrics: list[str] = Field(default_factory=list)

    review_start: date
    review_end: date

    limits: list[RiskLimit] = Field(default_factory=list)
    controls: list[ControlDefinition] = Field(default_factory=list)

    source_backed_facts: list[DeskFact] = Field(default_factory=list)
    inferred_facts: list[DeskFact] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    """Facts withheld because their cited evidence could not be validated."""

    @model_validator(mode="after")
    def _check_review_window(self) -> DeskContext:
        if self.review_start > self.review_end:
            raise ValueError("review_start must be <= review_end")
        return self

    def add_fact(self, fact: DeskFact) -> None:
        """Route a fact by provenance; INFERRED facts cannot become SOURCE_BACKED."""
        if fact.provenance is FactProvenance.SOURCE_BACKED:
            self.source_backed_facts.append(fact)
        else:
            self.inferred_facts.append(fact)

    def effective_limits(self, on: date) -> list[RiskLimit]:
        return [limit for limit in self.limits if limit.effective_on(on)]

    def effective_controls(self, on: date) -> list[ControlDefinition]:
        return [control for control in self.controls if control.effective_on(on)]
