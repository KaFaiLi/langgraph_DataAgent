"""Lead verifier: independent check of the final synthesis (high-cost model).

Bounded to 2 rounds; on exhaustion the current report is accepted with the
verifier's feedback recorded in the unresolved questions (honest disclosure,
spec section 23).
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.reports import CrossSourceCluster, FinalReport, SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER
from data_agent.review.domain.verification import VerifierDecision
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceValidationSummary,
    EvidenceValidator,
)
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.state import ParentState
from data_agent.skills.review import load_lead_review_skill
from data_agent.tools.review_context import ToolContext

MAX_LEAD_ROUNDS = 2

LEAD_VERIFIER_SYSTEM = load_lead_review_skill().verifier_policy


class LeadVerifierOutput(BaseModel):
    """The lead verifier's structured verdict."""

    decision: VerifierDecision
    feedback: str = ""
    checks: list[str] = Field(default_factory=list)


class FatalEvidenceIntegrityError(RuntimeError):
    """Raised when reviewed evidence no longer matches the run manifest."""


def _provider(config: RunnableConfig) -> ReviewLLMProvider:
    provider = (config or {}).get("configurable", {}).get("llm_provider")
    if provider is None:
        return DEFAULT_LLM_PROVIDER
    return provider


def _specialist_findings(
    state: ParentState,
) -> tuple[dict[str, Finding], set[str], set[str], list[str], dict[str, Finding]]:
    """Index specialist findings while rejecting ambiguous IDs deterministically."""
    verified: dict[str, Finding] = {}
    unresolved_ids: set[str] = set()
    all_ids: set[str] = set()
    all_findings: dict[str, Finding] = {}
    feedback: list[str] = []
    for data in state.get("specialist_reports", {}).values():
        report = SpecialistReport.model_validate(data)
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


def _ctx(state: ParentState) -> ToolContext:
    """Build the run tool context from parent state (no config dependency)."""
    from pathlib import Path

    from data_agent.review.domain.source import SourceManifest

    manifest = SourceManifest.model_validate(state["manifest"])
    return ToolContext(
        source_root=Path(state["source_root"]),
        workspace_root=Path(state["output_dir"]) / "workspace",
        manifest=manifest,
    )


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
        details = "; ".join(
            f"{failure.locator}: {failure.reason}" for failure in fatal
        )
        raise FatalEvidenceIntegrityError(
            f"fatal evidence integrity failure in {label}: {details}"
        )
    feedback.extend(
        f"{label} locator {failure.locator} could not be reopened: {failure.reason}"
        for failure in validation.failures
    )


def validate_final_report(state: ParentState, report: FinalReport) -> list[str]:
    """Return deterministic lead blockers; no model may override these."""
    verified, unresolved_ids, all_ids, feedback, all_findings = _specialist_findings(state)
    context = _ctx(state)
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
        for cluster in state.get("clusters", [])
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
            or (
                finding_id in unresolved_ids
                and finding_id in finding.unresolved_dependencies
            )
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
                reference.locator
                for item in declared_support
                for reference in item.evidence
            }
            for reference in finding.evidence:
                final_locators.add(reference.locator)
                if reference.locator not in support_locators:
                    feedback.append(
                        f"{finding.final_id}: evidence {reference.locator} was not copied "
                        "from supporting findings"
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
        final_locators.update(
            reference.locator for reference in cluster.supporting_evidence
        )
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

    for raw_cluster in state.get("clusters", []):
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


def lead_verifier(state: ParentState, config: RunnableConfig) -> dict:
    """Verify the final report; returns the next-state update."""
    report_data = state.get("final_report")
    if not report_data:
        return {"status": "failed", "failure_reason": "lead review produced no report"}
    report = FinalReport.model_validate(report_data)
    round_number = state.get("lead_round", 0) + 1
    try:
        feedback_parts = validate_final_report(state, report)
    except FatalEvidenceIntegrityError as exc:
        return {
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": str(exc),
        }
    if feedback_parts:
        feedback = "\n".join(feedback_parts)
        if round_number >= MAX_LEAD_ROUNDS:
            return {
                "lead_round": round_number,
                "lead_feedback": "",
                "lead_status": "complete",
                "status": "failed",
                "failure_reason": "lead verification deterministic checks failed: " + feedback,
            }
        return {
            "lead_round": round_number,
            "lead_feedback": feedback,
            "lead_status": "running",
        }

    _verified, _unresolved_ids, _all_ids, _index_feedback, all_findings = (
        _specialist_findings(state)
    )
    specialist_findings = [
        {
            "finding_id": finding.finding_id,
            "title": finding.title,
            "verifier_status": finding.verifier_status.value,
        }
        for finding in sorted(all_findings.values(), key=lambda item: item.finding_id)
    ]

    user = (
        f"Verification round: {round_number}\n\nFINAL REPORT (JSON):\n"
        + json.dumps(report_data, indent=2, default=str)
        + "\n\nSPECIALIST FINDINGS (verified and explicitly unresolved):\n"
        + json.dumps(specialist_findings, indent=2)
        + "\n\nReturn your structured verdict."
    )
    runnable = _provider(config)(ModelTier.HIGH_COST, LeadVerifierOutput)
    output = invoke_structured(
        runnable,
        [SystemMessage(content=LEAD_VERIFIER_SYSTEM), HumanMessage(content=user)],
        schema=LeadVerifierOutput,
    )
    verdict = (
        output
        if isinstance(output, LeadVerifierOutput)
        else LeadVerifierOutput.model_validate(output)
    )
    if verdict.decision is VerifierDecision.REVISE:
        feedback = verdict.feedback
        if round_number >= MAX_LEAD_ROUNDS:
            # Bounded: accept with honest disclosure (spec section 23).
            note = f"Lead verification (round {round_number}): {feedback}"
            report.unresolved_questions = [*report.unresolved_questions, note]
            return {
                "final_report": report.model_dump(mode="json"),
                "lead_round": round_number,
                "lead_feedback": "",
                "lead_status": "complete",
            }
        return {
            "lead_round": round_number,
            "lead_feedback": feedback,
            "lead_status": "running",
        }

    return {
        "lead_round": round_number,
        "lead_feedback": "",
        "lead_status": "complete",
    }
