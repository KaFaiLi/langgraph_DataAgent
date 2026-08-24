"""Review-run contracts: run status, coverage gate, review tasks."""

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


class CoverageError(RuntimeError):
    """Raised when the coverage gate blocks synthesis (never silent)."""


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
    """Top-level run record with the hard source-coverage gate."""

    run_id: str
    status: RunStatus
    created_at: datetime
    source_root: str
    output_dir: str

    manifest: SourceManifest
    coverage: list[SourceCoverage] = Field(default_factory=list)
    tasks: list[ReviewTask] = Field(default_factory=list)

    failure_reason: str | None = None

    def pending_sources(self) -> list[SourceCoverage]:
        return [entry for entry in self.coverage if not entry.is_settled()]

    def assert_full_coverage(self) -> None:
        """Raise ``CoverageError`` while any source is still pending review."""
        pending = self.pending_sources()
        if pending:
            ids = ", ".join(sorted(entry.source_id for entry in pending))
            raise CoverageError(f"coverage gate failed: {len(pending)} source(s) unreviewed: {ids}")

    def coverage_for(self, source_id: str) -> SourceCoverage:
        for entry in self.coverage:
            if entry.source_id == source_id:
                return entry
        raise KeyError(f"no coverage entry for source {source_id!r}")

    def mark_failed(self, reason: str) -> None:
        """Record an explicit failure; runs never fail silently (spec section 41)."""
        self.status = RunStatus.FAILED
        self.failure_reason = reason


