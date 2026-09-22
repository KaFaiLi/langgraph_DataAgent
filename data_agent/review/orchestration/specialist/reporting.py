"""Thin graph adapters for shared report construction."""

from __future__ import annotations

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.verification import OmissionAuditResult, VerificationRound
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.scope import context_from_config
from data_agent.review.orchestration.specialist.state import (
    SpecialistState,
    loads_finding,
    loads_period,
)
from data_agent.review.reporting.markdown import render_specialist_report
from data_agent.tools.review_operations import ReportRequest, construct_report


def finalize(runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig) -> dict:
    report = construct_report(
        ReportRequest(
            context=context_from_config(config),
            domain=runtime.spec.domain,
            domain_label=runtime.spec.domain_label,
            report_id=runtime.spec.report_id,
            period=loads_period(state["review_period"]),
            scope=state.get("scope", ""),
            source_ids=list(state.get("source_ids", [])),
            analyses=[AnalysisResult.model_validate(a) for a in state.get("analyses", [])],
            verified=[loads_finding(f) for f in state.get("verified_findings", [])],
            unresolved=[loads_finding(f) for f in state.get("unresolved_findings", [])],
            rejected=[loads_finding(f) for f in state.get("rejected_findings", [])],
            history={
                key: [VerificationRound.model_validate(r) for r in rounds]
                for key, rounds in state.get("verification_history", {}).items()
            },
            omission_audit=OmissionAuditResult.model_validate(state["omission_audit"])
            if state.get("omission_audit")
            else None,
        )
    )
    return {
        "report": report.model_dump(mode="json"),
        "unresolved_findings": [f.model_dump(mode="json") for f in report.unresolved_findings()],
    }


def render_markdown(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    if not state.get("report"):
        return {"error": "finalize produced no report"}
    return {"markdown": render_specialist_report(SpecialistReport.model_validate(state["report"]))}


__all__ = ["finalize", "render_markdown"]
