"""Correlate: deterministic cross-source clustering + contradiction candidates."""

from __future__ import annotations

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.orchestration.state import ParentState
from data_agent.tools.review_operations import analyze_reports


def correlate(state: ParentState, config: RunnableConfig) -> dict:
    """Run the lead skill's deterministic cross-specialist analysis."""
    reports = [
        SpecialistReport.model_validate(data)
        for data in state.get("specialist_reports", {}).values()
    ]
    analysis = analyze_reports(reports)
    return {
        "clusters": [cluster.model_dump(mode="json") for cluster in analysis.clusters],
        "contradictions": [
            candidate.model_dump(mode="json") for candidate in analysis.contradiction_candidates
        ],
    }
