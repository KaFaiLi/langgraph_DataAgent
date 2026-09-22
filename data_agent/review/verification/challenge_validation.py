"""Graph-independent admission of independent challenge evidence."""

from __future__ import annotations

from collections.abc import Sequence

from data_agent.review.domain.evidence import EvidenceReference, parse_locator
from data_agent.review.domain.outputs import ChallengerChallenge, ChallengerOutput
from data_agent.review.domain.verification import (
    AdversarialCase,
    ChallengeResult,
    ChallengeStatus,
    ChallengeType,
)
from data_agent.review.ingestion.evidence_validator import EvidenceDisposition, EvidenceValidator
from data_agent.review.verification.rules import required_challenge_types


def _evidence_validation(
    references: Sequence[EvidenceReference],
    *,
    validator: EvidenceValidator,
    assigned_paths: set[str],
) -> tuple[list[EvidenceReference], list[str], bool]:
    """Keep valid challenge evidence and return errors/fatality separately."""

    valid: list[EvidenceReference] = []
    errors: list[str] = []
    fatal = False
    summary = validator.validate_references(references)
    by_locator = {result.locator: result for result in summary.results}
    for reference in references:
        result = by_locator.get(reference.locator)
        try:
            path = parse_locator(reference.locator).path
        except ValueError as exc:
            errors.append(f"{reference.locator}: malformed locator: {exc}")
            continue
        if path not in assigned_paths:
            errors.append(f"{reference.locator}: source path is not assigned to this challenger")
            continue
        if result is None:
            errors.append(f"{reference.locator}: validator returned no result")
            continue
        if result.disposition is EvidenceDisposition.FATAL:
            fatal = True
            errors.append(f"{reference.locator}: {result.reason or 'fatal evidence failure'}")
        elif result.valid:
            valid.append(reference)
        else:
            errors.append(f"{reference.locator}: {result.reason or 'invalid evidence'}")
    return valid, errors, fatal


def _sanitize_challenge_case(
    output: ChallengerOutput,
    *,
    finding_id: str,
    validator: EvidenceValidator,
    assigned_paths: Sequence[str],
) -> AdversarialCase:
    """Validate challenge locators and make omissions material UNKNOWNs."""

    assigned = set(assigned_paths)
    unique: dict[ChallengeType, ChallengerChallenge] = {}
    for challenge in output.challenges:
        if challenge.challenge_type in unique:
            previous = unique[challenge.challenge_type]
            unique[challenge.challenge_type] = previous.model_copy(
                update={
                    "status": ChallengeStatus.UNKNOWN,
                    "material": True,
                    "explanation": (
                        previous.explanation + " Duplicate challenge category was returned."
                    ).strip(),
                    "evidence": [],
                }
            )
            continue
        unique[challenge.challenge_type] = challenge

    sanitized: list[ChallengeResult] = []
    for challenge in unique.values():
        evidence, errors, fatal = _evidence_validation(
            challenge.evidence,
            validator=validator,
            assigned_paths=assigned,
        )
        if fatal:
            raise RuntimeError("fatal evidence integrity failure in adversarial challenge")
        if errors:
            challenge = challenge.model_copy(
                update={
                    "status": ChallengeStatus.UNKNOWN,
                    "material": True,
                    "evidence": [],
                    "explanation": (
                        challenge.explanation + " Invalid challenge evidence: " + "; ".join(errors)
                    ).strip(),
                }
            )
        else:
            challenge = challenge.model_copy(update={"evidence": evidence})
        if challenge.status is ChallengeStatus.NOT_APPLICABLE and not challenge.explanation.strip():
            challenge = challenge.model_copy(
                update={
                    "status": ChallengeStatus.UNKNOWN,
                    "material": True,
                    "explanation": "NOT_APPLICABLE requires an explanation.",
                }
            )
        sanitized.append(challenge)

    required = required_challenge_types(cross_source_required=len(set(assigned_paths)) > 1)
    present = {challenge.challenge_type for challenge in sanitized}
    for challenge_type in required:
        if challenge_type not in present:
            sanitized.append(
                ChallengeResult(
                    challenge_type=challenge_type,
                    status=ChallengeStatus.UNKNOWN,
                    material=True,
                    explanation="Challenger omitted this required category.",
                )
            )

    contradictory, errors, fatal = _evidence_validation(
        output.contradictory_evidence,
        validator=validator,
        assigned_paths=assigned,
    )
    if fatal:
        raise RuntimeError("fatal evidence integrity failure in adversarial contradiction evidence")
    if errors:
        for index, challenge in enumerate(sanitized):
            if challenge.challenge_type is ChallengeType.COUNTER_EVIDENCE:
                sanitized[index] = challenge.model_copy(
                    update={
                        "status": ChallengeStatus.UNKNOWN,
                        "material": True,
                        "explanation": (
                            challenge.explanation
                            + " Invalid contradictory evidence: "
                            + "; ".join(errors)
                        ).strip(),
                        "evidence": [],
                    }
                )
                break

    return AdversarialCase(
        finding_id=finding_id,
        challenges=sanitized,
        strongest_counter_hypothesis=output.strongest_counter_hypothesis,
        contradictory_evidence=contradictory,
        unresolved_questions=list(output.unresolved_questions),
        assigned_source_paths=list(assigned_paths),
        research_complete=output.research_complete,
    )
