"""Typed review operations, independent of graph state and invocation configuration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import parse_locator
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.overview import DataOverview, OverviewStatus
from data_agent.review.domain.reports import CrossSpecialistAnalysis, SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import (
    CandidateDispositionRecord,
    EvidenceGateResult,
    OmissionAuditResult,
    VerificationRound,
)
from data_agent.review.ingestion.evidence_validator import EvidenceDisposition, EvidenceValidator
from data_agent.review.verification.candidates import assign_candidate_ids
from data_agent.review.verification.evidence import evaluate_evidence_gate
from data_agent.review.verification.finding_policy import sanitize_finding_references
from data_agent.review.verification.omission import audit_omissions
from data_agent.skills.review import (
    AnalysisRunner,
    load_lead_analysis_runner,
    load_lead_review_skill,
)
from data_agent.tools.review_context import ToolContext, source_file


@dataclass(frozen=True)
class AnalysisRequest:
    context: ToolContext
    source_paths: tuple[str, ...]


def prepare_analysis(request: AnalysisRequest, runner: AnalysisRunner) -> list[AnalysisResult]:
    """Run a trusted calculation and assign stable identities without graph state."""
    for path in request.source_paths:
        source_file(request.context, path)
    results = []
    for raw in runner(request.context, list(request.source_paths)):
        analysis = AnalysisResult.model_validate(raw.model_dump(mode="json"))
        analysis.flag_candidates = assign_candidate_ids(analysis.name, analysis.flag_candidates)
        results.append(analysis)
    return results


@dataclass(frozen=True)
class EvidenceRequest:
    context: ToolContext
    finding: Finding
    round_number: int = 1
    max_rounds: int = 2
    raise_on_fatal: bool = True


def validate_evidence(request: EvidenceRequest) -> EvidenceGateResult:
    """Reopen finding evidence using the established deterministic verification gate."""
    return evaluate_evidence_gate(
        request.finding,
        EvidenceValidator.source_backed(request.context.source_root, request.context.manifest),
        round_number=request.round_number,
        max_verifier_rounds=request.max_rounds,
        raise_on_fatal=request.raise_on_fatal,
    )


@dataclass(frozen=True)
class OmissionRequest:
    context: ToolContext
    source_paths: tuple[str, ...]
    analyses: Sequence[AnalysisResult]
    verified: Sequence[Finding] = ()
    rejected: Sequence[Finding] = ()
    unresolved: Sequence[Finding] = ()
    dispositions: Sequence[CandidateDispositionRecord] = ()
    rescue_used: bool = False


def audit_candidates(request: OmissionRequest) -> OmissionAuditResult:
    """Only assigned, reopenable disposition evidence may account for a candidate."""
    validator = EvidenceValidator.source_backed(
        request.context.source_root, request.context.manifest
    )
    records = []
    for record in request.dispositions:
        validation = validator.validate_references(record.evidence)
        valid = {result.locator for result in validation.results if result.valid}
        evidence = [
            ref
            for ref in record.evidence
            if ref.locator in valid and parse_locator(ref.locator).path in request.source_paths
        ]
        records.append(record.model_copy(update={"evidence": evidence}))
    return audit_omissions(
        request.analyses,
        request.verified,
        rejected_findings=request.rejected,
        unresolved_findings=request.unresolved,
        candidate_dispositions=records,
        rescue_used=request.rescue_used,
    )


def analyze_reports(
    reports: Sequence[SpecialistReport], *, skills_root: Path | None = None
) -> CrossSpecialistAnalysis:
    """Execute the lead skill's trusted cross-report calculations on typed reports."""
    definition = load_lead_review_skill(skills_root=skills_root) if skills_root else None
    return CrossSpecialistAnalysis.model_validate(
        load_lead_analysis_runner(definition)(list(reports))
    )


@dataclass(frozen=True)
class ReportRequest:
    context: ToolContext
    domain: SpecialistDomain
    domain_label: str
    report_id: str
    period: DateRange
    scope: str
    source_ids: list[str]
    analyses: list[AnalysisResult] = field(default_factory=list)
    verified: list[Finding] = field(default_factory=list)
    unresolved: list[Finding] = field(default_factory=list)
    rejected: list[Finding] = field(default_factory=list)
    history: dict[str, list[VerificationRound]] = field(default_factory=dict)
    omission_audit: OmissionAuditResult | None = None
    unresolved_items: list[str] = field(default_factory=list)


def construct_report(request: ReportRequest) -> SpecialistReport:
    """Construct the compatible specialist artifact, retaining evidence integrity gates."""
    ctx, period = request.context, request.period
    verified, unresolved_findings, rejected = request.verified, request.unresolved, request.rejected
    history, omission_audit = request.history, request.omission_audit
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
    unresolved_items.extend(request.unresolved_items)
    conclusion = (
        f"{request.domain_label} review completed: {len(verified)} finding(s) verified, "
        f"{len(rejected)} rejected, {len(unresolved_findings)} unresolved. "
        f"Top findings: {top_text}."
    )
    if omission_audit is not None and omission_audit.material_omission_exists:
        conclusion += (
            f" {len(omission_audit.material_candidate_ids)} deterministic candidate(s) "
            "remain disclosed as omission risk."
        )
    data_overviews: list[DataOverview] = []
    for raw_analysis in request.analyses:
        analysis = raw_analysis
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
        domain=request.domain,
        report_id=request.report_id,
        title=f"{request.domain_label} Review",
        review_period=period,
        generated_at=datetime.now(UTC),
        scope=request.scope,
        sources_reviewed=request.source_ids,
        analysis_performed=[analysis.name for analysis in request.analyses],
        data_overviews=data_overviews,
        findings=all_findings,
        unresolved_items=unresolved_items,
        overall_conclusion=conclusion,
        verification_history=history,
        omission_audit=omission_audit,
    )
    return report
