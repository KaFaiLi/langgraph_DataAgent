"""Pure bounded verification-state reduction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.verification import (
    AdjudicationResult,
    AdversarialCase,
    EvidenceGateResult,
    VerificationRound,
    VerificationTransition,
    VerifierDecision,
)
from data_agent.review.verification.rules import guard_adjudication


def _as_adjudication(
    result: AdjudicationResult | Mapping[str, Any],
    finding_id: str,
) -> AdjudicationResult:
    if isinstance(result, AdjudicationResult):
        return result.model_copy(update={"finding_id": finding_id})
    data = dict(result)
    if "challenge_summary" not in data and "challenges" in data:
        data["challenge_summary"] = data.pop("challenges")
    data["finding_id"] = finding_id
    return AdjudicationResult.model_validate(data)


def _result_map(
    results: Mapping[str, AdjudicationResult | Mapping[str, Any]]
    | Sequence[AdjudicationResult | Mapping[str, Any]],
) -> dict[str, AdjudicationResult]:
    if isinstance(results, Mapping):
        return {
            str(finding_id): _as_adjudication(result, str(finding_id))
            for finding_id, result in results.items()
        }
    mapped: dict[str, AdjudicationResult] = {}
    for result in results:
        finding_id = getattr(result, "finding_id", None)
        if finding_id is None and isinstance(result, Mapping):
            finding_id = result.get("finding_id")
        if finding_id is not None:
            mapped[str(finding_id)] = _as_adjudication(result, str(finding_id))
    return mapped


def _gate_for(
    finding_id: str,
    adjudication: AdjudicationResult,
    gates: Mapping[str, EvidenceGateResult | Mapping[str, Any]] | None,
) -> EvidenceGateResult | None:
    gate = adjudication.evidence_gate
    if gates is not None and finding_id in gates:
        value = gates[finding_id]
        gate = (
            value
            if isinstance(value, EvidenceGateResult)
            else EvidenceGateResult.model_validate(value)
        )
    return gate


def _append_round(
    history: Mapping[str, Sequence[VerificationRound]] | None,
    finding_id: str,
    adjudication: AdjudicationResult,
    *,
    round_number: int,
    evidence_gate: EvidenceGateResult | None,
    analyst_responses: Mapping[str, str | None] | None,
    research_mode: str | None,
) -> dict[str, list[VerificationRound]]:
    updated = {key: list(value) for key, value in (history or {}).items()}
    case = adjudication.adversarial_case
    if case is None and adjudication.challenge_summary:
        case = AdversarialCase(
            finding_id=finding_id,
            challenges=adjudication.challenge_summary,
        )
    analyst_response = (
        analyst_responses.get(finding_id)
        if analyst_responses is not None
        else adjudication.analyst_response
    )
    record = VerificationRound(
        round_number=round_number,
        decision=adjudication.decision,
        challenges=adjudication.challenge_summary,
        adversarial_case=case,
        adjudication=adjudication,
        evidence_gate=evidence_gate,
        checks=adjudication.checks,
        feedback=adjudication.feedback,
        analyst_response=analyst_response,
        research_mode=research_mode,
    )
    updated.setdefault(finding_id, []).append(record)
    return updated


def reduce_verification(
    findings: Sequence[Finding],
    results: Mapping[str, AdjudicationResult | Mapping[str, Any]]
    | Sequence[AdjudicationResult | Mapping[str, Any]],
    history: Mapping[str, Sequence[VerificationRound]] | None = None,
    *,
    round_number: int = 1,
    verifier_round: int | None = None,
    max_verifier_rounds: int = 2,
    evidence_gates: Mapping[str, EvidenceGateResult | Mapping[str, Any]] | None = None,
    analyst_responses: Mapping[str, str | None] | None = None,
    research_mode: str | None = None,
) -> VerificationTransition:
    """Reduce one result set into pending/terminal finding partitions.

    The function is side-effect free.  A first-round ``REVISE`` remains pending;
    a ``REVISE`` at the configured bound becomes ``UNRESOLVED``.  Findings that
    are already terminal and omitted from a result set remain terminal.
    """

    if verifier_round is not None:
        round_number = verifier_round
    if round_number < 1:
        raise ValueError("round_number must be >= 1")
    if max_verifier_rounds < 1:
        raise ValueError("max_verifier_rounds must be >= 1")

    by_id = _result_map(results)
    pending: list[Finding] = []
    verified: list[Finding] = []
    rejected: list[Finding] = []
    unresolved: list[Finding] = []
    updated_history: dict[str, list[VerificationRound]] = {
        key: list(value) for key, value in (history or {}).items()
    }
    feedback: list[str] = []

    for original in findings:
        finding_id = original.finding_id
        adjudication = by_id.get(finding_id)
        if adjudication is None:
            # Missing model output must never silently pass.  An in-progress
            # finding remains pending for the caller to handle/retry.
            if original.verifier_status in (VerificationStatus.PASSED, VerificationStatus.REVISED):
                verified.append(original)
            elif original.verifier_status is VerificationStatus.REJECTED:
                rejected.append(original)
            elif original.verifier_status is VerificationStatus.UNRESOLVED:
                unresolved.append(original)
            else:
                pending.append(original)
            continue

        gate = _gate_for(finding_id, adjudication, evidence_gates)
        if adjudication.decision is VerifierDecision.PASS:
            adjudication = guard_adjudication(original, adjudication, evidence_gate=gate)
        elif gate is not None and gate.fatal_integrity_failure:
            adjudication = adjudication.model_copy(
                update={
                    "decision": VerifierDecision.UNRESOLVED,
                    "feedback": "; ".join(
                        item
                        for item in (
                            adjudication.feedback,
                            gate.feedback or "fatal evidence integrity failure",
                        )
                        if item
                    ),
                }
            )
        updated_history = _append_round(
            updated_history,
            finding_id,
            adjudication,
            round_number=round_number,
            evidence_gate=gate,
            analyst_responses=analyst_responses,
            research_mode=research_mode,
        )
        if adjudication.feedback:
            feedback.append(f"{finding_id}: {adjudication.feedback}")

        if adjudication.decision is VerifierDecision.PASS:
            status = VerificationStatus.REVISED if round_number > 1 else VerificationStatus.PASSED
            verified.append(original.model_copy(update={"verifier_status": status}))
        elif adjudication.decision is VerifierDecision.REJECT:
            rejected.append(
                original.model_copy(update={"verifier_status": VerificationStatus.REJECTED})
            )
        elif (
            adjudication.decision is VerifierDecision.UNRESOLVED
            or round_number >= max_verifier_rounds
        ):
            unresolved.append(
                original.model_copy(update={"verifier_status": VerificationStatus.UNRESOLVED})
            )
        else:
            pending.append(
                original.model_copy(update={"verifier_status": VerificationStatus.PENDING})
            )

    return VerificationTransition(
        pending=pending,
        verified=verified,
        rejected=rejected,
        unresolved=unresolved,
        history=updated_history,
        feedback="\n".join(feedback),
        complete=not pending,
        round_number=round_number,
    )


def reduce_verification_results(*args, **kwargs) -> VerificationTransition:
    """Compatibility alias for the pure verification reducer."""

    return reduce_verification(*args, **kwargs)
