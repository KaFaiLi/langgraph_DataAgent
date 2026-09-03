"""Coverage gate: synthesis may never start with unreviewed sources (spec 19)."""

from __future__ import annotations

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.plan import CheckApplicability, ReviewPlan
from data_agent.review.orchestration.state import ParentState


def coverage_gate(state: ParentState, config: RunnableConfig) -> dict:
    """Fail the run loudly if any source lacks a settled review disposition."""
    pending = [entry for entry in state.get("coverage", []) if entry["status"] == "pending"]
    if pending:
        ids = ", ".join(sorted(entry["source_id"] for entry in pending))
        return {
            "status": "failed",
            "failure_reason": f"coverage gate failed: {len(pending)} source(s) unreviewed: {ids}",
        }
    plan_data = state.get("review_plan")
    if not plan_data:
        return {"status": "failed", "failure_reason": "coverage gate failed: review plan missing"}
    plan = ReviewPlan.model_validate(plan_data)
    reports = state.get("specialist_reports", {})
    recorded = {
        check["check_id"]: check
        for report in reports.values()
        for check in report.get("check_coverage", [])
    }
    incomplete = [
        check.check_id
        for check in plan.checks
        if check.applicability is CheckApplicability.APPLICABLE
        and (
            check.check_id not in recorded
            or not recorded[check.check_id].get("performed")
            or not recorded[check.check_id].get("population_definition")
            or not recorded[check.check_id].get("result")
            or "evidence" not in recorded[check.check_id]
            or "limitations" not in recorded[check.check_id]
        )
    ]
    if incomplete:
        return {
            "status": "failed",
            "failure_reason": "coverage gate failed: planned checks incomplete: "
            + ", ".join(sorted(incomplete)),
        }
    return {}
