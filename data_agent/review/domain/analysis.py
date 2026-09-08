"""Shared deterministic-analysis result contract for all specialists and skills."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from data_agent.review.domain.overview import DataOverview
from data_agent.review.domain.source import DateRange


class AnalysisStatus(StrEnum):
    """Whether an analysis produced a usable population-level result."""

    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class SourceBinding(BaseModel):
    source_id: str
    path: str
    sha256: str


class PopulationReceipt(BaseModel):
    """Auditable accounting for the population actually processed."""

    source_bindings: list[SourceBinding] = Field(default_factory=list)
    rows_read: int = Field(ge=0)
    rows_in_scope: int = Field(ge=0)
    rows_processed: int = Field(ge=0)
    rows_rejected: int = Field(ge=0)
    rows_excluded: int = Field(ge=0)
    exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    actual_date_range: DateRange | None = None
    calculation_basis: str


class AnalysisExecution(BaseModel):
    status: AnalysisStatus
    population: PopulationReceipt
    issue_codes: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """One deterministic analysis, ready for the analyst LLM."""

    name: str
    summary: str
    tables: list[dict[str, object]] = Field(default_factory=list)
    flag_candidates: list[dict[str, object]] = Field(default_factory=list)
    """Code-flagged candidates the analyst must interpret (never auto-findings)."""
    overviews: list[DataOverview] = Field(default_factory=list)
    """Code-owned report/deck views; never reconstructed by an LLM."""
    execution: AnalysisExecution | None = None
