"""Authoritative, versioned state for model-directed reviews."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.source import DateRange, SourceManifest
from data_agent.review.domain.verification import CandidateDispositionRecord


class SourceDisposition(BaseModel):
    status: Literal["reviewed", "irrelevant", "unsupported"]
    reason: str = Field(min_length=1, max_length=2000)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=12)


class AssignmentRecord(BaseModel):
    assignment_id: str
    skill_name: str
    source_ids: list[str]
    rationale: str
    analysis_ref: str | None = None
    candidate_ref: str | None = None
    dispositions: dict[str, SourceDisposition] = Field(default_factory=dict)
    candidate_dispositions: dict[str, CandidateDispositionRecord] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    findings: dict[str, dict] = Field(default_factory=dict)
    verification: dict[str, list[dict]] = Field(default_factory=dict)
    unresolved_items: list[str] = Field(default_factory=list)
    omission_disclosure: str | None = None
    rescue_attempts: int = 0
    report: dict | None = None


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    run_id: str
    source_root: str
    output_dir: str
    created_at: datetime
    review_period: DateRange
    desk_context: DeskContext
    manifest: SourceManifest
    manifest_digest: str
    classifications: dict[str, list[str]] = Field(default_factory=dict)
    classification_reasons: dict[str, str] = Field(default_factory=dict)
    assignments: dict[str, AssignmentRecord] = Field(default_factory=dict)
    source_dispositions: dict[str, SourceDisposition] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    trace: list[dict] = Field(default_factory=list)
    failures: list[dict] = Field(default_factory=list)
    role_results: dict[str, dict] = Field(default_factory=dict)
    child_runs: dict[str, dict] = Field(default_factory=dict)
    tool_calls: int = 0
    max_tool_calls: int = 400
    max_verifier_rounds: int = Field(default=2, ge=1, le=2)
    status: Literal["running", "interrupted", "failed", "completed"] = "running"
