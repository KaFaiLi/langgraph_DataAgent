"""Standardized specialist and final Markdown (spec sections 24-25), rendered by code."""

from __future__ import annotations

from data_agent.review.domain.finding import Finding
from data_agent.review.domain.overview import (
    BarVisual,
    DataOverview,
    LineVisual,
    StackedBarVisual,
    TableVisual,
)
from data_agent.review.domain.reports import FinalFinding, FinalReport, SpecialistReport
from data_agent.review.domain.verification import VerificationRound


def _history(report: SpecialistReport, finding_id: str) -> list[VerificationRound]:
    return report.verification_history.get(finding_id, [])


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def _number(value: float) -> str:
    return f"{value:g}"


def _render_overview(overview: DataOverview) -> str:
    lines = [
        f"### {overview.title}",
        "",
        f"**Overview ID:** `{overview.overview_id}`",
        f"**Status:** {overview.status.value}",
        "",
        overview.summary,
        "",
        "#### Key Metrics",
        "",
    ]
    if overview.metrics:
        for metric in overview.metrics:
            suffix = f" {metric.unit}" if metric.unit else ""
            basis = f" ({metric.basis})" if metric.basis else ""
            lines.append(f"- **{metric.label}:** {metric.value}{suffix}{basis}")
    else:
        lines.append("- none")

    visual = overview.visual
    if isinstance(visual, (LineVisual, BarVisual, StackedBarVisual)):
        lines += [
            "",
            "#### Visual Data Summary",
            "",
            "| Series | Observations | Start | End | Minimum | Maximum |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for series in visual.series:
            values = [point.value for point in series.points]
            lines.append(
                "| "
                + " | ".join(
                    [
                        series.name,
                        str(len(values)),
                        _number(values[0]),
                        _number(values[-1]),
                        _number(min(values)),
                        _number(max(values)),
                    ]
                )
                + " |"
            )
    elif isinstance(visual, TableVisual):
        lines += ["", "#### Data Table", ""]
        lines.append("| " + " | ".join(visual.columns) + " |")
        lines.append("| " + " | ".join("---" for _ in visual.columns) + " |")
        lines.extend("| " + " | ".join(row) + " |" for row in visual.rows)

    lines += ["", "#### Evidence", ""]
    lines.extend([f"- `{reference.locator}`" for reference in overview.evidence] or ["- none"])
    lines += ["", "#### Limitations", "", *_bullets(overview.limitations), ""]
    return "\n".join(lines)


def _render_finding(report: SpecialistReport, finding: Finding) -> str:
    rounds = _history(report, finding.finding_id)
    last: VerificationRound | None = rounds[-1] if rounds else None
    period = f"{finding.period.start} to {finding.period.end}" if finding.period else "n/a"
    lines = [
        f"### {finding.finding_id} — {finding.title}",
        "",
        f"**Severity:** {finding.severity.value}",
        f"**Confidence:** {finding.confidence:.2f}",
        f"**Period:** {period}",
        f"**Verification:** {finding.verifier_status.value}",
        "",
        "#### Observation",
        "",
        finding.claim,
        "",
        "#### Evidence",
        "",
    ]
    if finding.evidence:
        lines.extend(
            f"- `{ref.locator}`" + (f" — “{ref.quote}”" if ref.quote else "")
            for ref in finding.evidence
        )
    else:
        lines.append("- none cited")
    lines += [
        "",
        "#### Analysis",
        "",
        *_bullets(finding.analysis_performed),
        "",
        "#### Alternative Explanations",
        "",
        *_bullets(finding.alternative_explanations),
        "",
        "#### Counter Evidence",
        "",
    ]
    if finding.counter_evidence:
        lines.extend(f"- `{ref.locator}`" for ref in finding.counter_evidence)
    else:
        lines.append("- none")
    lines += [
        "",
        "#### Verifier Questions",
        "",
    ]
    if last and last.questions:
        lines.extend(
            f"- **{question.question}** — {question.answer or 'not answered'}"
            for question in last.questions
        )
    else:
        lines.append("- none recorded")
    lines += [
        "",
        "#### Analyst Response",
        "",
        last.analyst_response if last and last.analyst_response else "n/a",
        "",
        "#### Verifier Conclusion",
        "",
        f"Decision: **{last.decision.value if last else 'pending'}**",
    ]
    if last and last.checks:
        lines.append(f"Checks: {'; '.join(last.checks)}")
    if last and last.feedback:
        lines.append(f"Feedback: {last.feedback}")
    lines += [
        "",
        "#### Recommendation",
        "",
        finding.recommendation or "None.",
        "",
    ]
    return "\n".join(lines)


def render_specialist_report(report: SpecialistReport) -> str:
    """Render a specialist report exactly per the standard template."""
    lines = [
        f"# {report.title}",
        "",
        "## Review Metadata",
        "",
        f"- **Report ID:** {report.report_id}",
        f"- **Domain:** {report.domain.value}",
        f"- **Review Period:** {report.review_period.start} to {report.review_period.end}",
        f"- **Generated At:** {report.generated_at.isoformat()}",
        "",
        "## Scope",
        "",
        report.scope,
        "",
        "## Sources Reviewed",
        "",
        *_bullets(report.sources_reviewed),
        "",
        "## Analysis Performed",
        "",
        *_bullets(report.analysis_performed),
        "",
        "## Data Overview",
        "",
    ]
    if not report.data_overviews:
        lines.append("No deterministic data overview was retained for this report.")
    for overview in report.data_overviews:
        lines.append(_render_overview(overview))
    lines += [
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("No findings.")
    for finding in report.findings:
        lines.append(_render_finding(report, finding))
    lines += [
        "## Unresolved Items",
        "",
        *_bullets(report.unresolved_items),
        "",
        "## Overall Conclusion",
        "",
        report.overall_conclusion,
        "",
    ]
    return "\n".join(lines)


def _render_final_finding(finding: FinalFinding) -> str:
    derived = ", ".join(finding.derived_from)
    evidence = ", ".join(f"`{ref.locator}`" for ref in finding.evidence) or "none"
    clusters = ", ".join(finding.cross_source_cluster_ids) or "none"
    return "\n".join(
        [
            f"### {finding.final_id} — {finding.title}",
            "",
            f"**Severity:** {finding.severity.value}",
            f"**Confidence:** {finding.confidence:.2f}",
            "",
            finding.statement,
            "",
            f"**Derived from:** {derived}",
            f"**Evidence:** {evidence}",
            f"**Cross-source clusters:** {clusters}",
            "",
        ]
    )


def render_final_report(report: FinalReport) -> str:
    """Render ``final_findings.md`` per spec section 25."""
    lines = [
        "# Final Findings",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "## Overall Desk Risk Assessment",
        "",
        report.overall_desk_risk_assessment,
        "",
        "## Key Findings",
        "",
    ]
    if not report.key_findings:
        lines.append("No key findings.")
    for finding in report.key_findings:
        lines.append(_render_final_finding(finding))
    lines += [
        "## Cross-source Findings",
        "",
    ]
    if report.cross_source_findings:
        for cluster in report.cross_source_findings:
            lines.append(
                f"- **{cluster.cluster_id}**: findings {', '.join(cluster.findings)} "
                f"({', '.join(cluster.relationship_types) or 'linked'}) "
                f"| entities: {', '.join(cluster.shared_entities) or 'none'}"
            )
    else:
        lines.append("- none")
    lines += [
        "",
        "## Potential Unauthorized Activity Indicators",
        "",
        *_bullets(report.potential_unauthorized_activity_indicators),
        "",
        "## Control Weaknesses",
        "",
        *_bullets(report.control_weaknesses),
        "",
        "## PnL / Risk Inconsistencies",
        "",
        *_bullets(report.pnl_risk_inconsistencies),
        "",
        "## Unresolved Questions",
        "",
        *_bullets(report.unresolved_questions),
        "",
        "## Recommended Follow-up",
        "",
        *_bullets(report.recommended_follow_up),
        "",
        "## Evidence Index",
        "",
    ]
    if report.evidence_index:
        lines.extend(f"- `{ref.locator}`" for ref in report.evidence_index)
    else:
        lines.append("- none")
    lines += [
        "",
        "## Specialist Report References",
        "",
        *_bullets(report.specialist_report_references),
        "",
    ]
    return "\n".join(lines)
