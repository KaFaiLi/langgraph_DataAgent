"""Coverage gate: synthesis may never start with unreviewed sources (spec 19)."""

from __future__ import annotations

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.orchestration.state import ParentState


def coverage_gate(state: ParentState, config: RunnableConfig) -> dict:
    """Fail the run loudly if any source lacks a settled review disposition."""
    pending = [entry for entry in state.get("coverage", []) if entry["status"] == "pending"]
    if pending:
        ids = ", ".join(sorted(entry["source_id"] for entry in pending))
        return {
            "status": "failed",
            "failure_reason": (f"coverage gate failed: {len(pending)} source(s) unreviewed: {ids}"),
        }
    return {}
