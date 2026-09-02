"""Lead verifier: independent check of the final synthesis (high-cost model).

The verifier has one semantic revision opportunity.  Deterministic report and
evidence gates always fail closed; a persistent semantic objection is never
accepted merely because the round budget was exhausted.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field, field_validator

from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.reports import (
    CrossSourceCluster,
    FinalReport,
    SpecialistReport,
)
from data_agent.review.domain.severity import SEVERITY_ORDER
from data_agent.review.domain.verification import (
    LeadChallenge,
    ObjectionMateriality,
    VerifierDecision,
)
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
MAX_LEAD_CHALLENGES = 32
MAX_LEAD_CHECKS = 64
MAX_LEAD_FEEDBACK = 4_000

_MATERIALITY_ORDER = {
    ObjectionMateriality.INFORMATIONAL: 0,
    ObjectionMateriality.LOW: 1,
    ObjectionMateriality.MEDIUM: 2,
    ObjectionMateriality.HIGH: 3,
    ObjectionMateriality.CRITICAL: 4,
}
_MATERIAL_OBJECTION_LEVEL = _MATERIALITY_ORDER[ObjectionMateriality.MEDIUM]

LEAD_VERIFIER_SYSTEM = load_lead_review_skill().verifier_policy


class LeadVerifierOutput(BaseModel):
    """The lead verifier's structured verdict."""

    decision: VerifierDecision
    feedback: str = Field(default="", max_length=MAX_LEAD_FEEDBACK)
    checks: list[str] = Field(default_factory=list, max_length=MAX_LEAD_CHECKS)
    challenges: list[LeadChallenge] = Field(
        default_factory=list,
        max_length=MAX_LEAD_CHALLENGES,
    )

    @field_validator("feedback", mode="before")
    @classmethod
    def _bound_feedback(cls, value: object) -> object:
        return value[:MAX_LEAD_FEEDBACK] if isinstance(value, str) else value

    @field_validator("checks", mode="before")
    @classmethod
    def _bound_checks(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:500] if isinstance(item, str) else item for item in value[:MAX_LEAD_CHECKS]]

    @field_validator("challenges", mode="before")
    @classmethod
    def _bound_challenges(cls, value: object) -> object:
        return value[:MAX_LEAD_CHALLENGES] if isinstance(value, list) else value


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
        details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in fatal)
        raise FatalEvidenceIntegrityError(f"fatal evidence integrity failure in {label}: {details}")
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
    specialist_issues = {
        issue.issue_id: issue
        for data in state.get("specialist_reports", {}).values()
        for issue in SpecialistReport.model_validate(data).issues
        if issue.status.value != "resolved"
    }
    final_issue_ids = {issue.issue_id for issue in report.unresolved_issues}
    missing_issues = sorted(set(specialist_issues) - final_issue_ids)
    if missing_issues:
        feedback.append(f"unresolved specialist issues are not carried forward: {missing_issues}")
    disclosed_issue_text = "\n".join(report.unresolved_questions)
    undisclosed_material = sorted(
        issue_id
        for issue_id, issue in specialist_issues.items()
        if issue.material and issue_id not in disclosed_issue_text
    )
    if undisclosed_material:
        feedback.append(f"material review issues are not disclosed: {undisclosed_material}")

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

    for raw_cluster in state.get("clusters") or []:
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


def _prior_lead_history(state: ParentState) -> list[dict]:
    """Return prior lead rounds as plain JSON-compatible mappings.

    Parent checkpoints intentionally contain primitives rather than Pydantic
    instances.  Be defensive when resuming an older checkpoint that did not
    have a lead history field yet.
    """
    history = state.get("lead_verification_history", [])
    if not isinstance(history, list):
        return []
    return [dict(entry) for entry in history if isinstance(entry, dict)]


def _history_entry(
    round_number: int,
    *,
    decision: VerifierDecision,
    feedback: str = "",
    checks: Iterable[str] = (),
    challenges: Iterable[LeadChallenge] = (),
) -> dict:
    """Serialize one lead-verifier result without leaking Pydantic objects."""
    return {
        "round_number": round_number,
        "decision": decision.value,
        "feedback": feedback[:MAX_LEAD_FEEDBACK],
        "checks": [str(check)[:500] for check in list(checks)[:MAX_LEAD_CHECKS]],
        "challenges": [
            challenge.model_dump(mode="json")
            for challenge in list(challenges)[:MAX_LEAD_CHALLENGES]
        ],
    }


def _with_history(state: ParentState, entry: dict) -> list[dict]:
    return [*_prior_lead_history(state), entry]


def _challenge_feedback(challenges: Iterable[LeadChallenge]) -> str:
    """Render concise, concrete structured objections for lead revision."""
    parts: list[str] = []
    for challenge in challenges:
        targets = ", ".join(challenge.affected_finding_ids) or "report-wide"
        explanation = challenge.explanation.strip() or "No explanation was supplied."
        resolution = (
            f" Proposed resolution: {challenge.proposed_resolution.strip()}"
            if challenge.proposed_resolution and challenge.proposed_resolution.strip()
            else ""
        )
        parts.append(
            f"[{challenge.materiality.value}] {challenge.challenge_type.value} "
            f"(affected: {targets}): {explanation}{resolution}"
        )
    return "\n".join(parts)[:MAX_LEAD_FEEDBACK]


def _challenge_disclosure(challenge: LeadChallenge, *, suppressed: bool) -> str:
    targets = ", ".join(challenge.affected_finding_ids) or "report-wide"
    action = "suppressed" if suppressed else "disclosed"
    explanation = challenge.explanation.strip() or "No explanation was supplied."
    return (
        f"Lead verification {action} {challenge.materiality.value} "
        f"{challenge.challenge_type.value} objection (affected: {targets}): {explanation}"
    )


def _rebuild_synthesis_after_suppression(
    state: ParentState,
    report: FinalReport,
    suppressed_ids: set[str],
) -> list[dict]:
    """Remove challenged conclusions and rebuild dependent cluster/index data.

    The lead model is not allowed to leave a stale cluster or evidence index
    referring to a semantically suppressed final finding.  Deterministic
    clusters are filtered in parallel because the final hard gate validates
    their relationship to the parent state.
    """
    suppressed_locators = {
        reference.locator
        for finding in report.key_findings
        if finding.final_id in suppressed_ids
        for reference in finding.evidence
    }
    retained_final_locators = {
        reference.locator
        for finding in report.key_findings
        if finding.final_id not in suppressed_ids
        for reference in finding.evidence
    }
    filtered_state_clusters: list[dict] = []
    state_cluster_ids: set[str] = set()
    for raw_cluster in state.get("clusters", []):
        try:
            cluster = CrossSourceCluster.model_validate(raw_cluster)
        except ValueError:
            # validate_final_report already reports malformed deterministic
            # clusters before semantic review.  Keep malformed data untouched
            # here so that the hard gate remains authoritative if encountered.
            continue
        cluster.findings = [
            finding_id for finding_id in cluster.findings if finding_id not in suppressed_ids
        ]
        if not cluster.findings:
            continue
        cluster.supporting_evidence = [
            reference
            for reference in cluster.supporting_evidence
            if reference.locator not in suppressed_locators
            or reference.locator in retained_final_locators
        ]
        state_cluster_ids.add(cluster.cluster_id)
        filtered_state_clusters.append(cluster.model_dump(mode="json"))

    retained_clusters: list[CrossSourceCluster] = []
    for cluster in report.cross_source_findings:
        cluster.findings = [
            finding_id for finding_id in cluster.findings if finding_id not in suppressed_ids
        ]
        if not cluster.findings or cluster.cluster_id not in state_cluster_ids:
            continue
        cluster.supporting_evidence = [
            reference
            for reference in cluster.supporting_evidence
            if reference.locator not in suppressed_locators
            or reference.locator in retained_final_locators
        ]
        retained_clusters.append(cluster)
    retained_cluster_ids = {cluster.cluster_id for cluster in retained_clusters}

    retained_findings = []
    for finding in report.key_findings:
        if finding.final_id in suppressed_ids:
            continue
        finding.cross_source_cluster_ids = [
            cluster_id
            for cluster_id in finding.cross_source_cluster_ids
            if cluster_id in retained_cluster_ids
        ]
        retained_findings.append(finding)

    suppressed_findings = [
        finding for finding in report.key_findings if finding.final_id in suppressed_ids
    ]
    stale_tokens = {
        token.casefold()
        for finding in suppressed_findings
        for token in [finding.final_id, finding.title, finding.statement]
        if token.strip()
    }

    def is_stale(text: str) -> bool:
        lowered = text.casefold()
        return any(token in lowered for token in stale_tokens)

    def retain_narrative(items: list[str]) -> list[str]:
        return [item for item in items if not is_stale(item)]

    report.key_findings = retained_findings
    report.cross_source_findings = retained_clusters
    report.potential_unauthorized_activity_indicators = retain_narrative(
        report.potential_unauthorized_activity_indicators
    )
    report.control_weaknesses = retain_narrative(report.control_weaknesses)
    report.pnl_risk_inconsistencies = retain_narrative(report.pnl_risk_inconsistencies)
    report.recommended_follow_up = retain_narrative(report.recommended_follow_up)
    if is_stale(report.executive_summary):
        report.executive_summary = (
            f"Lead review retained {len(retained_findings)} verified conclusion(s); "
            "materially challenged conclusions were suppressed and disclosed below."
        )
    if is_stale(report.overall_desk_risk_assessment):
        report.overall_desk_risk_assessment = (
            "The overall assessment is limited to the retained verified conclusions "
            "and the unresolved issues disclosed in this report."
        )

    evidence_index = []
    seen_locators: set[str] = set()
    for reference in [
        *(reference for finding in report.key_findings for reference in finding.evidence),
        *(reference for cluster in retained_clusters for reference in cluster.supporting_evidence),
    ]:
        if reference.locator in seen_locators:
            continue
        seen_locators.add(reference.locator)
        evidence_index.append(reference)
    report.evidence_index = evidence_index
    return filtered_state_clusters


def _apply_final_round_challenges(
    state: ParentState,
    report: FinalReport,
    challenges: list[LeadChallenge],
) -> tuple[FinalReport, list[dict], set[str], list[str]]:
    """Apply final-round materiality rules to structured semantic objections.

    High/critical report-wide or ambiguously targeted objections fail closed.
    Medium-or-higher targeted objections suppress only the explicitly named
    final findings.  Informational/low objections are retained as disclosures.
    """
    report_ids = {finding.final_id for finding in report.key_findings}
    suppressed_ids: set[str] = set()
    blockers: list[str] = []
    disclosures: list[str] = []

    for challenge in challenges:
        targets = list(dict.fromkeys(challenge.affected_finding_ids))
        unknown_targets = sorted(set(targets) - report_ids)
        materiality = _MATERIALITY_ORDER[challenge.materiality]
        if materiality < _MATERIAL_OBJECTION_LEVEL:
            disclosures.append(_challenge_disclosure(challenge, suppressed=False))
            continue

        # A material objection without a precise final-finding target cannot
        # be safely repaired by deleting arbitrary synthesis.  We fail closed
        # for medium as well as high/critical; high/critical is called out in
        # the user-facing reason because it is the strongest safety boundary.
        if not targets or unknown_targets:
            qualifier = "report-wide" if not targets else f"unknown targets {unknown_targets}"
            blockers.append(
                f"{challenge.materiality.value} {challenge.challenge_type.value} objection "
                f"is ambiguously targeted ({qualifier})"
            )
            continue

        if materiality >= _MATERIAL_OBJECTION_LEVEL:
            suppressed_ids.update(targets)
            disclosures.append(_challenge_disclosure(challenge, suppressed=True))

    if blockers:
        return report, list(state.get("clusters") or []), suppressed_ids, blockers

    filtered_clusters = _rebuild_synthesis_after_suppression(state, report, suppressed_ids)
    report.unresolved_questions = [*report.unresolved_questions, *disclosures]
    return report, filtered_clusters, suppressed_ids, []


def _needs_semantic_revision(challenges: Iterable[LeadChallenge]) -> bool:
    return any(
        _MATERIALITY_ORDER[challenge.materiality] >= _MATERIAL_OBJECTION_LEVEL
        for challenge in challenges
    )


def lead_verifier(state: ParentState, config: RunnableConfig) -> dict:
    """Verify the final report; returns the next-state update."""
    report_data = state.get("final_report")
    if not report_data:
        return {"status": "failed", "failure_reason": "lead review produced no report"}
    report = FinalReport.model_validate(report_data)
    round_number = int(state.get("lead_round", 0)) + 1
    try:
        feedback_parts = validate_final_report(state, report)
    except FatalEvidenceIntegrityError as exc:
        failure_reason = str(exc)
        history = _with_history(
            state,
            _history_entry(
                round_number,
                decision=VerifierDecision.UNRESOLVED,
                feedback=failure_reason,
                checks=["deterministic evidence integrity gate failed"],
            ),
        )
        return {
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": failure_reason,
            "lead_verification_history": history,
        }
    if feedback_parts:
        feedback = "\n".join(feedback_parts)
        history = _with_history(
            state,
            _history_entry(
                round_number,
                decision=VerifierDecision.REVISE,
                feedback=feedback,
                checks=["deterministic final-report validation"],
            ),
        )
        if round_number >= MAX_LEAD_ROUNDS:
            return {
                "lead_round": round_number,
                "lead_feedback": "",
                "lead_status": "complete",
                "status": "failed",
                "failure_reason": "lead verification deterministic checks failed: " + feedback,
                "lead_verification_history": history,
            }
        return {
            "lead_round": round_number,
            "lead_feedback": feedback,
            "lead_status": "running",
            "lead_verification_history": history,
        }

    _verified, _unresolved_ids, _all_ids, _index_feedback, all_findings = _specialist_findings(
        state
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
        + json.dumps(report.model_dump(mode="json"), indent=2, default=str)
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
    challenge_feedback = _challenge_feedback(verdict.challenges)
    feedback = "\n".join(part for part in (verdict.feedback.strip(), challenge_feedback) if part)[
        :MAX_LEAD_FEEDBACK
    ]
    history = _with_history(
        state,
        _history_entry(
            round_number,
            decision=verdict.decision,
            feedback=verdict.feedback,
            checks=verdict.checks,
            challenges=verdict.challenges,
        ),
    )

    if verdict.decision in (VerifierDecision.REJECT, VerifierDecision.UNRESOLVED):
        # A semantic rejection is not a successful lead review.  Keeping the
        # report in state for diagnostics is fine, but parent routing must stop
        # with a failed run rather than finalize it as accepted.
        reason = verdict.feedback.strip() or (f"lead verifier returned {verdict.decision.value}")
        return {
            "final_report": report.model_dump(mode="json"),
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": f"lead verification did not pass: {reason}",
            "lead_verification_history": history,
        }

    if verdict.decision is VerifierDecision.REVISE:
        if round_number >= MAX_LEAD_ROUNDS:
            # The one revision budget is exhausted. Apply the structured
            # final-round policy: disclose low objections, suppress precisely
            # targeted material conclusions, and fail only when safe targeting
            # is unavailable.
            final_report, clusters, _suppressed, blockers = _apply_final_round_challenges(
                state,
                report,
                verdict.challenges,
            )
            if not verdict.challenges:
                blockers.append("lead verifier requested revision without structured challenges")
            if blockers:
                reason = feedback or "lead verifier requested another revision"
                return {
                    "final_report": final_report.model_dump(mode="json"),
                    "clusters": clusters,
                    "lead_round": round_number,
                    "lead_feedback": "",
                    "lead_status": "complete",
                    "status": "failed",
                    "failure_reason": (
                        "lead verification remained unresolved after one revision: "
                        + reason
                        + "; "
                        + "; ".join(blockers)
                    ),
                    "lead_verification_history": history,
                }
            return {
                "final_report": final_report.model_dump(mode="json"),
                "clusters": clusters,
                "lead_round": round_number,
                "lead_feedback": "",
                "lead_status": "complete",
                "lead_verification_history": history,
            }
        return {
            "lead_round": round_number,
            "lead_feedback": feedback or "Lead verifier requested a concrete report revision.",
            "lead_status": "running",
            "lead_verification_history": history,
        }

    # A first-round PASS with a material objection is not final: the lead must
    # receive one opportunity to address it.  Low/informational objections can
    # be disclosed immediately because they do not block acceptance.
    if round_number < MAX_LEAD_ROUNDS and _needs_semantic_revision(verdict.challenges):
        return {
            "lead_round": round_number,
            "lead_feedback": feedback or "Lead verifier identified a material objection.",
            "lead_status": "running",
            "lead_verification_history": history,
        }

    final_report, clusters, _suppressed, blockers = _apply_final_round_challenges(
        state,
        report,
        verdict.challenges,
    )
    if blockers:
        return {
            "final_report": final_report.model_dump(mode="json"),
            "clusters": clusters,
            "lead_round": round_number,
            "lead_feedback": "",
            "lead_status": "complete",
            "status": "failed",
            "failure_reason": "lead verification failed closed: " + "; ".join(blockers),
            "lead_verification_history": history,
        }

    return {
        "final_report": final_report.model_dump(mode="json"),
        "clusters": clusters,
        "lead_round": round_number,
        "lead_feedback": "",
        "lead_status": "complete",
        "lead_verification_history": history,
    }
