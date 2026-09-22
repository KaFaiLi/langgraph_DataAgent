"""Typed final-report validation without an orchestration state or model dependency."""

from __future__ import annotations

from dataclasses import dataclass

from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.reports import CrossSourceCluster, FinalReport, SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceValidationSummary,
    EvidenceValidator,
)
from data_agent.tools.review_context import ToolContext


class FatalEvidenceIntegrityError(RuntimeError):
    """Reviewed evidence no longer matches the immutable manifest."""


@dataclass(frozen=True)
class FinalValidationRequest:
    context: ToolContext
    reports: list[SpecialistReport]
    clusters: list[CrossSourceCluster]


def _specialist_findings(
    request: FinalValidationRequest,
) -> tuple[dict[str, Finding], set[str], set[str], list[str], dict[str, Finding]]:
    """Index specialist findings while rejecting ambiguous IDs deterministically."""
    verified: dict[str, Finding] = {}
    unresolved_ids: set[str] = set()
    all_ids: set[str] = set()
    all_findings: dict[str, Finding] = {}
    feedback: list[str] = []
    for report in request.reports:
        for finding in report.findings:
            if finding.finding_id in all_ids:
                feedback.append(
                    f"duplicate specialist finding ID {finding.finding_id}; "
                    "lead support is ambiguous"
                )
            all_ids.add(finding.finding_id)
            all_findings[finding.finding_id] = finding
            if finding.verifier_status in (
                VerificationStatus.PASSED,
                VerificationStatus.REVISED,
            ):
                verified[finding.finding_id] = finding
            elif finding.verifier_status is VerificationStatus.UNRESOLVED:
                unresolved_ids.add(finding.finding_id)
    return verified, unresolved_ids, all_ids, feedback, all_findings


def _record_evidence_failures(
    feedback: list[str],
    validation: EvidenceValidationSummary,
    *,
    label: str,
) -> None:
    fatal = [
        failure
        for failure in validation.failures
        if failure.disposition is EvidenceDisposition.FATAL
    ]
    if fatal:
        details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in fatal)
        raise FatalEvidenceIntegrityError(f"fatal evidence integrity failure in {label}: {details}")
    feedback.extend(
        f"{label} locator {failure.locator} could not be reopened: {failure.reason}"
        for failure in validation.failures
    )


def validate_final_report(request: FinalValidationRequest, report: FinalReport) -> list[str]:
    """Return deterministic lead blockers; no model may override these."""
    verified, unresolved_ids, all_ids, feedback, all_findings = _specialist_findings(request)
    context = request.context
    validator = EvidenceValidator.source_backed(context.source_root, context.manifest)
    all_primary_locators = {
        reference.locator for finding in all_findings.values() for reference in finding.evidence
    }
    all_specialist_locators = {
        reference.locator
        for finding in all_findings.values()
        for reference in [*finding.evidence, *finding.counter_evidence]
    }
    final_locators: set[str] = set()

    cluster_ids = {
        str(cluster.get("cluster_id", ""))
        for cluster in [c.model_dump(mode="json") for c in request.clusters]
        if isinstance(cluster, dict)
    }
    for finding in report.key_findings:
        unknown = [finding_id for finding_id in finding.derived_from if finding_id not in all_ids]
        if unknown:
            feedback.append(
                f"{finding.final_id}: derived_from references unknown specialist "
                f"finding ids {unknown}"
            )
        support = [
            verified[finding_id] for finding_id in finding.derived_from if finding_id in verified
        ]
        declared_support = [
            all_findings[finding_id]
            for finding_id in finding.derived_from
            if finding_id in verified
            or (finding_id in unresolved_ids and finding_id in finding.unresolved_dependencies)
        ]
        if not support:
            feedback.append(
                f"{finding.final_id}: derived_from requires at least one verified "
                "specialist finding"
            )
        unsupported = [
            finding_id
            for finding_id in finding.derived_from
            if finding_id not in verified
            and not (finding_id in unresolved_ids and finding_id in finding.unresolved_dependencies)
        ]
        if unsupported:
            feedback.append(
                f"{finding.final_id}: unverified support must be an explicitly declared "
                f"unresolved dependency, got {unsupported}"
            )
        if support and SEVERITY_ORDER[finding.severity] > max(
            SEVERITY_ORDER[item.severity] for item in support
        ):
            feedback.append(
                f"{finding.final_id}: severity {finding.severity.value} exceeds verified support"
            )
        if not finding.evidence:
            feedback.append(f"{finding.final_id}: final finding requires copied evidence")
        else:
            support_locators = {
                reference.locator for item in declared_support for reference in item.evidence
            }
            for reference in finding.evidence:
                final_locators.add(reference.locator)
                if reference.locator not in support_locators:
                    feedback.append(
                        f"{finding.final_id}: evidence {reference.locator} was not copied "
                        "from supporting findings"
                    )
            copied_locators = {reference.locator for reference in finding.evidence}
            for item in declared_support:
                if not copied_locators.intersection(ref.locator for ref in item.evidence):
                    feedback.append(
                        f"{finding.final_id}: supporting finding {item.finding_id} "
                        "requires its own copied evidence"
                    )
            evidence_validation = validator.validate_references(finding.evidence)
            _record_evidence_failures(
                feedback,
                evidence_validation,
                label=f"{finding.final_id}: evidence",
            )
        missing_clusters = [
            cluster_id
            for cluster_id in finding.cross_source_cluster_ids
            if cluster_id not in cluster_ids
        ]
        if missing_clusters:
            feedback.append(f"{finding.final_id}: unknown cross-source clusters {missing_clusters}")
        for dependency in finding.unresolved_dependencies:
            if dependency in all_ids and dependency not in unresolved_ids:
                feedback.append(
                    f"{finding.final_id}: dependency {dependency} is not an unresolved "
                    "specialist finding"
                )

    declared_unresolved = "\n".join(report.unresolved_questions)
    dependency_ids = {
        dependency
        for finding in report.key_findings
        for dependency in finding.unresolved_dependencies
    }
    missing_unresolved = sorted(
        finding_id
        for finding_id in unresolved_ids
        if finding_id not in dependency_ids and finding_id not in declared_unresolved
    )
    if missing_unresolved:
        feedback.append(f"unresolved specialist findings are not disclosed: {missing_unresolved}")

    report_cluster_ids: set[str] = set()
    for cluster in report.cross_source_findings:
        if cluster.cluster_id in report_cluster_ids:
            feedback.append(f"duplicate final cross-source cluster ID {cluster.cluster_id}")
        report_cluster_ids.add(cluster.cluster_id)
        if cluster.cluster_id not in cluster_ids:
            feedback.append(f"final report references unknown cluster {cluster.cluster_id}")
        unknown_cluster_findings = [
            finding_id for finding_id in cluster.findings if finding_id not in all_ids
        ]
        if unknown_cluster_findings:
            feedback.append(
                f"cluster {cluster.cluster_id} contains unknown specialist findings "
                f"{unknown_cluster_findings}"
            )
        final_locators.update(reference.locator for reference in cluster.supporting_evidence)
        cluster_validation = validator.validate_references(cluster.supporting_evidence)
        _record_evidence_failures(
            feedback,
            cluster_validation,
            label=f"cluster {cluster.cluster_id}: evidence",
        )
        unknown_cluster_evidence = sorted(
            reference.locator
            for reference in cluster.supporting_evidence
            if reference.locator not in all_specialist_locators
        )
        if unknown_cluster_evidence:
            feedback.append(
                f"cluster {cluster.cluster_id} contains non-specialist evidence "
                f"{unknown_cluster_evidence}"
            )

    for raw_cluster in [c.model_dump(mode="json") for c in request.clusters]:
        try:
            cluster = CrossSourceCluster.model_validate(raw_cluster)
        except ValueError as exc:
            feedback.append(f"invalid deterministic cluster: {exc}")
            continue
        unknown_cluster_findings = [
            finding_id for finding_id in cluster.findings if finding_id not in all_ids
        ]
        if unknown_cluster_findings:
            feedback.append(
                f"deterministic cluster {cluster.cluster_id} contains unknown findings "
                f"{unknown_cluster_findings}"
            )
        cluster_validation = validator.validate_references(cluster.supporting_evidence)
        _record_evidence_failures(
            feedback,
            cluster_validation,
            label=f"deterministic cluster {cluster.cluster_id}: evidence",
        )
        unknown_cluster_evidence = sorted(
            reference.locator
            for reference in cluster.supporting_evidence
            if reference.locator not in all_specialist_locators
        )
        if unknown_cluster_evidence:
            feedback.append(
                f"deterministic cluster {cluster.cluster_id} contains non-specialist evidence "
                f"{unknown_cluster_evidence}"
            )

    indexed = {reference.locator for reference in report.evidence_index}
    missing_index = sorted(final_locators - indexed)
    if missing_index:
        feedback.append(f"evidence_index omits final report evidence {missing_index}")
    unknown_index = sorted(indexed - all_primary_locators)
    if unknown_index:
        feedback.append(f"evidence_index contains non-specialist evidence {unknown_index}")
    index_validation = validator.validate_references(report.evidence_index)
    _record_evidence_failures(feedback, index_validation, label="evidence_index")
    return feedback
