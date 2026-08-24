"""Shared deterministic-analysis result contract for all specialists and skills."""

from __future__ import annotations

from pydantic import BaseModel, Field

from data_agent.review.domain.overview import DataOverview


class AnalysisResult(BaseModel):
    """One deterministic analysis, ready for the analyst LLM."""

    name: str
    summary: str
    tables: list[dict[str, object]] = Field(default_factory=list)
    flag_candidates: list[dict[str, object]] = Field(default_factory=list)
    """Code-flagged candidates the analyst must interpret (never auto-findings)."""
    overviews: list[DataOverview] = Field(default_factory=list)
    """Code-owned report/deck views; never reconstructed by an LLM."""
