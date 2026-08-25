"""Pure rules that prevent unsupported model-generated ``PASS`` decisions."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.domain.verification import (
    AdjudicationResult,
    AdversarialCase,
    ChallengeCompletenessResult,
    ChallengeResult,
    ChallengeStatus,
    ChallengeType,
    EvidenceGateResult,
    RuleCheckResult,
    VerifierDecision,
)

# Cross-source consistency is conditional: the caller adds it when the
# assigned source population has more than one relevant source.
REQUIRED_CHALLENGE_TYPES: tuple[ChallengeType, ...] = (
    ChallengeType.EVIDENCE_SUPPORT,
    ChallengeType.REPRODUCIBILITY,
    ChallengeType.POPULATION_SCOPE,
    ChallengeType.COUNTER_EVIDENCE,
    ChallengeType.ALTERNATIVE_EXPLANATION,
    ChallengeType.TEMPORAL_VALIDITY,
    ChallengeType.DATA_QUALITY,
    ChallengeType.CAUSALITY,
    ChallengeType.SEVERITY,
)


def _challenge_values(
    challenges: Sequence[ChallengeResult] | AdversarialCase | None,
) -> list[ChallengeResult]:
    if challenges is None:
        return []
    if isinstance(challenges, AdversarialCase):
        return list(challenges.challenges)
    return list(challenges)


def required_challenge_types(*, cross_source_required: bool = False) -> tuple[ChallengeType, ...]:
    """Return the deterministic challenge set for one finding."""

    if cross_source_required:
        return (*REQUIRED_CHALLENGE_TYPES, ChallengeType.CROSS_SOURCE_CONSISTENCY)
    return REQUIRED_CHALLENGE_TYPES


def check_challenge_completeness(
    challenges: Sequence[ChallengeResult] | AdversarialCase | None,
    *,
    required: Iterable[ChallengeType] | None = None,
    required_types: Iterable[ChallengeType] | None = None,
    cross_source_required: bool = False,
) -> ChallengeCompletenessResult:
    """Validate category coverage, explanations, and material blockers.

    This function never treats omitted categories as ``NOT_APPLICABLE``.  A
    challenger must explicitly return that status with an explanation.
    """

    results = _challenge_values(challenges)
    selected_required = required if required is not None else required_types
    required_types = tuple(
        selected_required
        if selected_required is not None
        else required_challenge_types(cross_source_required=cross_source_required)
    )
    by_type: dict[ChallengeType, list[ChallengeResult]] = {}
    for result in results:
        by_type.setdefault(result.challenge_type, []).append(result)

    missing = [challenge_type for challenge_type in required_types if challenge_type not in by_type]
    invalid: list[ChallengeType] = []
    explanations_required: list[ChallengeType] = []
    material_blockers: list[ChallengeType] = []
    for challenge_type, values in by_type.items():
        if len(values) != 1:
            invalid.append(challenge_type)
        for result in values:
            if not result.explanation.strip():
                invalid.append(challenge_type)
                explanations_required.append(challenge_type)
            if result.status in (ChallengeStatus.FAIL, ChallengeStatus.UNKNOWN) and result.material:
                material_blockers.append(challenge_type)

    # Keep outputs deterministic and avoid duplicate category names when a
    # malformed model response includes repeated challenge entries.
    invalid = list(dict.fromkeys(invalid))
    explanations_required = list(dict.fromkeys(explanations_required))
    material_blockers = list(dict.fromkeys(material_blockers))
    return ChallengeCompletenessResult(
        valid=not missing and not invalid,
        missing=missing,
        invalid=invalid,
        material_blockers=material_blockers,
        explanations_required=explanations_required,
    )


def validate_challenge_completeness(
    challenges: Sequence[ChallengeResult] | AdversarialCase | None,
    *,
    required: Iterable[ChallengeType] | None = None,
    required_types: Iterable[ChallengeType] | None = None,
    cross_source_required: bool = False,
) -> ChallengeCompletenessResult:
    """Named validation entry point; equivalent to ``check_challenge_completeness``."""

    return check_challenge_completeness(
        challenges,
        required=required,
        required_types=required_types,
        cross_source_required=cross_source_required,
    )


def missing_challenge_types(
    challenges: Sequence[ChallengeResult] | AdversarialCase | None,
    *,
    required: Iterable[ChallengeType] | None = None,
    required_types: Iterable[ChallengeType] | None = None,
    cross_source_required: bool = False,
) -> list[ChallengeType]:
    """Return required categories absent from a challenger response."""

    return check_challenge_completeness(
        challenges,
        required=required,
        required_types=required_types,
        cross_source_required=cross_source_required,
    ).missing


def _severity(value: Severity | str | None) -> Severity | None:
    if value is None:
        return None
    if isinstance(value, Severity):
        return value
    try:
        return Severity(str(value).lower())
    except ValueError:
        return None


def _gate_blockers(gate: EvidenceGateResult | None) -> tuple[list[str], bool]:
    if gate is None:
        return [], False
    blockers: list[str] = []
    terminal = False
    if gate.fatal_integrity_failure:
        blockers.append("fatal evidence integrity failure")
        terminal = True
    if gate.evidence_inaccessible:
        blockers.append("evidence is inaccessible")
        terminal = True
    if not gate.valid:
        failed = gate.failed_locators or ["one or more evidence locators"]
        blockers.append("evidence gate failed: " + ", ".join(failed))
    if gate.decision is not VerifierDecision.PASS:
        blockers.append(f"evidence gate decision is {gate.decision.value}")
    return blockers, terminal


def can_pass(
    finding: Finding,
    challenges: Sequence[ChallengeResult] | AdversarialCase | None = None,
    *,
    evidence_gate: EvidenceGateResult | None = None,
    required: Iterable[ChallengeType] | None = None,
    required_types: Iterable[ChallengeType] | None = None,
    cross_source_required: bool = False,
    severity_ceiling: Severity | str | None = None,
    deterministic_severity_ceiling: Severity | str | None = None,
    evidence_integrity_ok: bool | None = None,
    evidence_inaccessible: bool | None = None,
    research_complete: bool | None = None,
    provider_error: bool | None = None,
) -> RuleCheckResult:
    """Evaluate all deterministic guards for a candidate ``PASS``.

    A non-empty blocker list is an invariant that the adjudicator cannot
    override.  The return type is a model rather than a bare boolean so the
    caller can persist concrete feedback for an analyst revision.
    """

    blockers: list[str] = []
    checks: list[str] = []

    if not finding.evidence:
        # Verification is stricter than draft construction: even a factual
        # observation needs reopenable primary evidence before it can survive
        # into a controlled report.
        blockers.append(f"finding {finding.finding_id}: primary evidence is missing")
    else:
        try:
            finding.assert_evidence_policy()
        except ValueError as exc:
            blockers.append(str(exc))
        else:
            checks.append("finding evidence policy satisfied")

    gate_failures, _terminal = _gate_blockers(evidence_gate)
    blockers.extend(gate_failures)
    if evidence_integrity_ok is False:
        blockers.append("evidence integrity failed")
    if evidence_inaccessible:
        blockers.append("evidence is inaccessible")

    adversarial_case = challenges if isinstance(challenges, AdversarialCase) else None
    if research_complete is False or (
        research_complete is None
        and adversarial_case is not None
        and not adversarial_case.research_complete
    ):
        blockers.append("adversarial research is incomplete")
    if provider_error is True or (
        provider_error is None and adversarial_case is not None and adversarial_case.provider_error
    ):
        blockers.append("adversarial research provider failed")
    if adversarial_case is not None and adversarial_case.contradictory_evidence:
        blockers.append("adversarial contradiction remains unresolved")
    if adversarial_case is not None and adversarial_case.unresolved_questions:
        blockers.append("adversarial case retains unresolved questions")

    completeness = check_challenge_completeness(
        challenges,
        required=required,
        required_types=required_types,
        cross_source_required=cross_source_required,
    )
    if completeness.missing:
        blockers.append(
            "missing required challenges: "
            + ", ".join(challenge.value for challenge in completeness.missing)
        )
    if completeness.invalid:
        blockers.append(
            "invalid challenge responses: "
            + ", ".join(challenge.value for challenge in completeness.invalid)
        )

    for challenge in _challenge_values(challenges):
        if (
            challenge.status in (ChallengeStatus.FAIL, ChallengeStatus.UNKNOWN)
            and challenge.material
        ):
            blockers.append(
                f"material {challenge.status.value} challenge: {challenge.challenge_type.value}"
            )
        if challenge.status is ChallengeStatus.NOT_APPLICABLE and not challenge.explanation.strip():
            blockers.append(
                f"{challenge.challenge_type.value} marked not applicable without explanation"
            )
    if completeness.valid and not completeness.material_blockers:
        checks.append("required adversarial challenges complete")

    ceiling = _severity(deterministic_severity_ceiling or severity_ceiling)
    if ceiling is not None and SEVERITY_ORDER[finding.severity] > SEVERITY_ORDER[ceiling]:
        blockers.append(
            f"severity {finding.severity.value} exceeds deterministic ceiling {ceiling.value}"
        )
    elif ceiling is not None:
        checks.append(f"severity within deterministic ceiling {ceiling.value}")

    # De-duplicate blockers while preserving the order in which the guards ran.
    blockers = list(dict.fromkeys(blockers))
    return RuleCheckResult(
        allowed=not blockers,
        blockers=blockers,
        checks=checks,
        feedback="; ".join(blockers),
    )


def guard_adjudication(
    finding: Finding,
    adjudication: AdjudicationResult,
    *,
    evidence_gate: EvidenceGateResult | None = None,
    required: Iterable[ChallengeType] | None = None,
    required_types: Iterable[ChallengeType] | None = None,
    cross_source_required: bool = False,
    severity_ceiling: Severity | str | None = None,
    deterministic_severity_ceiling: Severity | str | None = None,
    research_complete: bool | None = None,
    provider_error: bool | None = None,
) -> AdjudicationResult:
    """Override only an unsafe model ``PASS``; preserve other decisions."""

    if adjudication.decision is not VerifierDecision.PASS:
        return adjudication
    gate = evidence_gate or adjudication.evidence_gate
    challenge_input: Sequence[ChallengeResult] | AdversarialCase = (
        adjudication.adversarial_case
        if adjudication.adversarial_case is not None
        else adjudication.challenge_summary
    )
    result = can_pass(
        finding,
        challenge_input,
        evidence_gate=gate,
        required=required,
        required_types=required_types,
        cross_source_required=cross_source_required,
        severity_ceiling=severity_ceiling,
        deterministic_severity_ceiling=deterministic_severity_ceiling,
        research_complete=research_complete,
        provider_error=provider_error,
    )
    if result.allowed:
        return adjudication

    terminal = bool(gate and (gate.fatal_integrity_failure or gate.evidence_inaccessible))
    decision = VerifierDecision.UNRESOLVED if terminal else VerifierDecision.REVISE
    feedback = result.feedback or "deterministic PASS guard failed"
    return adjudication.model_copy(
        update={
            "decision": decision,
            "feedback": "; ".join(item for item in (adjudication.feedback, feedback) if item),
            "checks": [*adjudication.checks, *result.checks, *result.blockers],
            "evidence_gate": gate,
        }
    )


def apply_pass_guards(*args, **kwargs) -> AdjudicationResult:
    """Compatibility alias for callers describing the operation as applying guards."""

    return guard_adjudication(*args, **kwargs)
