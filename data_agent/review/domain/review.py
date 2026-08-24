"""Review-run persistence contracts and specialist review tasks."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.source import DateRange, SourceManifest

CoverageStatus = Literal["pending", "reviewed", "irrelevant", "unsupported"]


class RunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class SourceCoverage(BaseModel):
    """Coverage-gate tracking for one source (spec section 19)."""

    source_id: str
    required_reviewers: list[str] = Field(default_factory=list)
    completed_reviewers: list[str] = Field(default_factory=list)
    status: CoverageStatus = "pending"
    notes: str | None = None

    def is_settled(self) -> bool:
        """True when the source no longer blocks synthesis."""
        return self.status != "pending"


class ReviewTask(BaseModel):
    """One specialist review task created by the parent dispatcher."""

    task_id: str
    domain: SpecialistDomain
    source_ids: list[str] = Field(default_factory=list)
    scope: DateRange | None = None


class RunContext(BaseModel):
    """Persisted inputs needed to safely resume a checkpointed review.

    This is deliberately separate from :class:`ReviewRun`: a completed run is
    an archive of reviewed outputs, while this model records the original,
    authoritative invocation inputs before the graph can mutate its state.
    """

    schema_version: Literal[1] = 1
    run_id: str
    source_root: str
    output_dir: str
    desk_template: DeskContext
    review_period: DateRange


class ReviewRun(BaseModel):
    """Persisted top-level run record."""

    run_id: str
    status: RunStatus
    created_at: datetime
    source_root: str
    output_dir: str

    manifest: SourceManifest
    coverage: list[SourceCoverage] = Field(default_factory=list)
    tasks: list[ReviewTask] = Field(default_factory=list)

    failure_reason: str | None = None


