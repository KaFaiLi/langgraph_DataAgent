"""Public contracts for the controlled review module."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from data_agent.review.domain.source import DateRange


class ReviewStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    RETRYABLE_FAILURE = "retryable_failure"
    NOT_FOUND = "not_found"


class ReviewRequest(BaseModel):
    """Everything needed to start one deterministic review run."""

    source_root: Path
    output_dir: Path
    run_id: str
    review_start: date
    review_end: date
    desk_context: dict[str, Any]

    @model_validator(mode="after")
    def _ordered_period(self) -> ReviewRequest:
        DateRange(start=self.review_start, end=self.review_end)
        return self

    @property
    def review_period(self) -> DateRange:
        return DateRange(start=self.review_start, end=self.review_end)


class ReviewResult(BaseModel):
    """Stable result returned by start and resume."""

    status: ReviewStatus
    run_id: str
    output_dir: Path | None = None
    failure_reason: str | None = None
    final_report: dict[str, Any] | None = None
    specialist_reports: dict[str, dict[str, Any]] = Field(default_factory=dict)
    trace_path: Path | None = None
    last_event_at: datetime | None = None


class ReviewRunStatus(BaseModel):
    """Read-only status view for a persisted run."""

    status: ReviewStatus
    run_id: str
    output_dir: Path
    failure_reason: str | None = None
    completed_specialists: list[str] = Field(default_factory=list)
    trace_path: Path | None = None
    last_event_at: datetime | None = None
