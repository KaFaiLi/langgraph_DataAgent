"""Strict, versioned contracts for deterministic review planning."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import DateRange


class StrictPlanModel(BaseModel):
    """Fail closed when a persisted plan contains unknown fields."""

    model_config = ConfigDict(extra="forbid")


class CheckApplicability(StrEnum):
    APPLICABLE = "applicable"
    BLOCKED = "blocked"
    INAPPLICABLE = "inapplicable"


class PlannedCheck(StrictPlanModel):
    check_id: str = Field(pattern=r"^CHECK-[A-Z0-9_-]+$")
    domain: SpecialistDomain
    title: str = Field(min_length=1)
    playbook: str = Field(min_length=1)
    playbook_version: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+){0,2}(?:\+[a-f0-9]{12})?$")
    required_source_domains: list[SpecialistDomain] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    analysis_names: list[str] = Field(min_length=1)
    applicability: CheckApplicability
    applicability_reason: str = Field(min_length=1)
    completion_criteria: list[str] = Field(min_length=1)
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
        return self


class ReviewPlan(StrictPlanModel):
    schema_version: Literal[1] = 1
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
    result_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class CheckResult(StrictPlanModel):
    """Authoritative execution result for one planned check and attempt."""

    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    check_id: str
    domain: SpecialistDomain
    source_ids: list[str]
    receipts: list[AnalysisReceipt]
    population_start: str
    population_end: str
    completion_rule_passed: bool = False
    limitations: list[str] = Field(default_factory=list)
