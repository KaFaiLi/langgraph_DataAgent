"""Specialist report finalization and Markdown rendering nodes."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.overview import DataOverview, OverviewStatus
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER
from data_agent.review.domain.verification import (
    OmissionAuditResult,
    ReviewIssue,
    ReviewIssueKind,
    ReviewIssueStatus,
    VerificationRound,
)
from data_agent.review.ingestion.evidence_validator import EvidenceDisposition, EvidenceValidator
from data_agent.review.orchestration.finding_policy import sanitize_finding_references
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.scope import context_from_config
from data_agent.review.orchestration.specialist.state import (
    SpecialistState,
    dumps_finding,
    loads_finding,
    loads_period,
)
from data_agent.review.reporting.markdown import render_specialist_report


def finalize(runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig) -> dict:
    """Sanitize terminal findings and construct the specialist report."""
    ctx = context_from_config(config)
    period = loads_period(state["review_period"])
    verified = [loads_finding(data) for data in state.get("verified_findings", [])]
    unresolved_findings = [loads_finding(data) for data in state.get("unresolved_findings", [])]
    rejected = [loads_finding(data) for data in state.get("rejected_findings", [])]
    evidence_validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
    sanitized_verified: list[Finding] = []
    for finding in verified:
        sanitized, failures = sanitize_finding_references(finding, evidence_validator)
        if failures:
            details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in failures)
            raise RuntimeError(
                f"verified finding {finding.finding_id} retained invalid evidence: {details}"
            )
        sanitized_verified.append(sanitized)
    verified = sanitized_verified
    unresolved_findings = [
        sanitize_finding_references(finding, evidence_validator)[0]
        for finding in unresolved_findings
    ]
    history = {
        finding_id: [VerificationRound.model_validate(record) for record in rounds]
        for finding_id, rounds in state.get("verification_history", {}).items()
    }
    raw_omission_audit = state.get("omission_audit")
    omission_audit = (
        OmissionAuditResult.model_validate(raw_omission_audit) if raw_omission_audit else None
    )

    all_findings = [*verified, *unresolved_findings]
    top = sorted(all_findings, key=lambda finding: SEVERITY_ORDER[finding.severity], reverse=True)[
        :3
    ]
    top_text = (
        "; ".join(
            f"{finding.finding_id} ({finding.severity.value}): {finding.title}" for finding in top
        )
        or "none"
    )
    unresolved_items = [
        f"{finding.finding_id} — {finding.title}: "
        + next(
            (record.feedback for record in reversed(history.get(finding.finding_id, []))),
            "no verifier feedback",
        )
        for finding in unresolved_findings
    ]
    if omission_audit is not None:
        unresolved_items.extend(
            f"Omission disclosure: {disclosure}"
            for disclosure in omission_audit.unresolved_disclosures
        )
    issues_by_id = {
        issue.issue_id: issue
        for raw in state.get("issues_by_id", {}).values()
        for issue in [ReviewIssue.model_validate(raw)]
    }
    for finding in unresolved_findings:
        issue_id = f"unresolved-finding:{finding.finding_id}"
        issues_by_id.setdefault(
            issue_id,
            ReviewIssue(
                issue_id=issue_id,
                kind=ReviewIssueKind.VERIFICATION_OBJECTION,
                status=ReviewIssueStatus.DISCLOSED,
                description=next(
                    (record.feedback for record in reversed(history.get(finding.finding_id, []))),
                    f"{finding.finding_id} remains unresolved",
                ),
                material=True,
                finding_ids=[finding.finding_id],
                evidence=finding.evidence,
            ),
        )
    if omission_audit is not None:
        candidates = {item.candidate_id: item for item in omission_audit.uncovered_candidates}
        for candidate_id in omission_audit.material_candidate_ids:
            candidate = candidates.get(candidate_id)
            issue_id = f"omitted-candidate:{candidate_id}"
            issues_by_id.setdefault(
                issue_id,
                ReviewIssue(
                    issue_id=issue_id,
                    kind=ReviewIssueKind.OMITTED_CANDIDATE,
                    status=ReviewIssueStatus.DISCLOSED,
                    description=(candidate.reason if candidate else "Material candidate omitted"),
                    material=True,
                    candidate_ids=[candidate_id],
                    evidence=(candidate.evidence if candidate else []),
                ),
            )
    if state.get("research_budget_exhausted"):
        issue_id = f"research-exhausted:{runtime.spec.report_id}"
        issues_by_id.setdefault(
            issue_id,
            ReviewIssue(
                issue_id=issue_id,
                kind=ReviewIssueKind.RESEARCH_EXHAUSTED,
                status=ReviewIssueStatus.DISCLOSED,
                description="Specialist research budget was exhausted.",
                material=bool(unresolved_findings),
            ),
        )
    conclusion = (
        f"{runtime.spec.domain_label} review completed: {len(verified)} finding(s) verified, "
        f"{len(rejected)} rejected, {len(unresolved_findings)} unresolved. "
        f"Top findings: {top_text}."
    )
    if omission_audit is not None and omission_audit.material_omission_exists:
        conclusion += (
            f" {len(omission_audit.material_candidate_ids)} deterministic candidate(s) "
            "remain disclosed as omission risk."
        )
    data_overviews: list[DataOverview] = []
    for raw_analysis in state.get("analyses", []):
        analysis = AnalysisResult.model_validate(raw_analysis)
        for overview in analysis.overviews:
            validation = evidence_validator.validate_references(overview.evidence)
            overview_failures = [
                f"{failure.locator}: {failure.reason}" for failure in validation.failures
            ]
            fatal_failures = [
                failure
                for failure in validation.failures
                if failure.disposition is EvidenceDisposition.FATAL
            ]
            if fatal_failures:
                details = "; ".join(
                    f"{failure.locator}: {failure.reason}" for failure in fatal_failures
                )
                raise RuntimeError(
                    f"fatal evidence integrity failure in data overview "
                    f"{overview.overview_id}: {details}"
                )
            if overview_failures:
                overview = overview.model_copy(
                    update={
                        "status": OverviewStatus.UNAVAILABLE,
                        "visual": None,
                        "metrics": [],
                        "limitations": [
                            *overview.limitations,
                            ("Overview suppressed because report evidence could not be reopened: ")
                            + "; ".join(overview_failures),
                        ],
                    }
                )
            data_overviews.append(overview)
    report = SpecialistReport(
        domain=runtime.spec.domain,
        report_id=runtime.spec.report_id,
        title=f"{runtime.spec.domain_label} Review",
        review_period=period,
        generated_at=datetime.now(UTC),
        scope=state.get("scope", ""),
        sources_reviewed=list(state.get("source_ids", [])),
        analysis_performed=[analysis.get("name", "?") for analysis in state.get("analyses", [])],
        data_overviews=data_overviews,
        findings=all_findings,
        unresolved_items=unresolved_items,
        overall_conclusion=conclusion,
        verification_history=history,
        omission_audit=omission_audit,
        issues=list(issues_by_id.values()),
        check_coverage=list(state.get("checks_by_id", {}).values()),
    )
    return {
        "report": report.model_dump(mode="json"),
        "unresolved_findings": [dumps_finding(finding) for finding in unresolved_findings],
    }


def render_markdown(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Render the finalized report as the external Markdown artifact."""
    del runtime, config
    report_data = state.get("report")
    if not report_data:
        return {"error": "finalize produced no report"}
    report = SpecialistReport.model_validate(report_data)
    return {"markdown": render_specialist_report(report)}


__all__ = ["finalize", "render_markdown"]
