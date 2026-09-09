"""Strict, versioned contracts for deterministic review planning."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_agent.review.domain.analysis import AnalysisStatus, PopulationReceipt
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import DateRange


class StrictPlanModel(BaseModel):
    """Fail closed when a persisted plan contains unknown fields."""

    model_config = ConfigDict(extra="forbid")


class CheckApplicability(StrEnum):
    APPLICABLE = "applicable"
    BLOCKED = "blocked"
    INAPPLICABLE = "inapplicable"


class CheckStatus(StrEnum):
    PERFORMED = "performed"
    UNRESOLVED = "unresolved"


class AnalysisRequirement(StrictPlanModel):
    """Immutable, analysis-level input and population contract."""

    name: str = Field(min_length=1)
    required_source_ids: tuple[str, ...] = ()
    supporting_source_ids: tuple[str, ...] = ()
    minimum_observations: int = Field(default=0, ge=0)
    date_range_required: bool = False
    empty_population_allowed: bool = False

    @model_validator(mode="after")
    def _unique_bindings(self) -> AnalysisRequirement:
        if len(self.required_source_ids) != len(set(self.required_source_ids)):
            raise ValueError(f"{self.name}: required source ids must be unique")
        if set(self.required_source_ids) & set(self.supporting_source_ids):
            raise ValueError(f"{self.name}: a source cannot be both required and supporting")
        return self


class PlannedCheck(StrictPlanModel):
    check_id: str = Field(pattern=r"^CHECK-[A-Z0-9_-]+$")
    domain: SpecialistDomain
    title: str = Field(min_length=1)
    playbook: str = Field(min_length=1)
    playbook_version: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+){0,2}(?:\+[a-f0-9]{12})?$")
    required_source_domains: list[SpecialistDomain] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    analysis_names: list[str] = Field(min_length=1)
    analysis_requirements: tuple[AnalysisRequirement, ...] = ()
    applicability: CheckApplicability
    applicability_reason: str = Field(min_length=1)
    completion_criteria: list[str] = Field(min_length=1)
    empty_population_allowed: bool = False
    partial_rejection_allowed: bool = False
    policy_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _validate_collections(self) -> PlannedCheck:
        for label, values in (
            ("required source domains", self.required_source_domains),
            ("source ids", self.source_ids),
            ("analysis names", self.analysis_names),
            ("completion criteria", self.completion_criteria),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{self.check_id}: {label} must be unique")
        if self.applicability is CheckApplicability.APPLICABLE and not self.source_ids:
            raise ValueError(f"{self.check_id}: applicable check requires sources")
        if self.analysis_requirements:
            requirement_names = [item.name for item in self.analysis_requirements]
            if requirement_names != self.analysis_names:
                raise ValueError(
                    f"{self.check_id}: analysis requirements must match declared analyses in order"
                )
        return self


class ReviewPlan(StrictPlanModel):
    schema_version: Literal[2] = 2
    plan_id: str = Field(pattern=r"^PLAN-[A-F0-9]{16}$")
    review_period: DateRange
    checks: list[PlannedCheck]

    @model_validator(mode="after")
    def _unique_checks(self) -> ReviewPlan:
        ids = [check.check_id for check in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("review plan check ids must be unique")
        return self

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class AnalysisReceipt(StrictPlanModel):
    """Proof that one declared deterministic analysis emitted a result."""

    analysis_name: str = Field(min_length=1)
    status: AnalysisStatus
    population: PopulationReceipt
    result_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    issue_codes: list[str] = Field(default_factory=list)


class CheckResult(StrictPlanModel):
    """Authoritative execution result for one planned check and attempt."""

    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    check_id: str
    attempt_id: str
    domain: SpecialistDomain
    status: CheckStatus
    source_ids: list[str]
    receipts: list[AnalysisReceipt]
    completion_rule_passed: bool = False
    limitations: list[str] = Field(default_factory=list)
