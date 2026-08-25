"""Deterministic evidence reopening and gate decisions."""

from __future__ import annotations

from data_agent.review.domain.finding import Finding
from data_agent.review.domain.verification import EvidenceGateResult, VerifierDecision
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceValidator,
)


class EvidenceGateError(RuntimeError):
    """Raised when a caller explicitly requires fatal integrity failures to abort."""


def _references_for_results(references, results):
    valid_locators = {result.locator for result in results if result.valid}
    return [reference for reference in references if reference.locator in valid_locators]


def evaluate_evidence_gate(
    finding: Finding,
    validator: EvidenceValidator,
    *,
    round_number: int = 1,
    max_verifier_rounds: int = 2,
    raise_on_fatal: bool = False,
) -> EvidenceGateResult:
    """Reopen primary and counter evidence and derive a bounded gate outcome.

    Fatal source integrity changes are represented in the returned model so
    artifacts remain inspectable.  ``raise_on_fatal`` is available for the
    review service's fail-loudly path and raises only after the structured
    result has been assembled.
    """

    if round_number < 1:
        raise ValueError("round_number must be >= 1")
    if max_verifier_rounds < 1:
        raise ValueError("max_verifier_rounds must be >= 1")

    primary_summary = validator.validate_references(finding.evidence)
    counter_summary = validator.validate_references(finding.counter_evidence)
    all_results = [*primary_summary.results, *counter_summary.results]
    failures = [result for result in all_results if not result.valid]
    failed_locators = [result.locator for result in failures]
    fatal = any(result.disposition is EvidenceDisposition.FATAL for result in failures)
    inaccessible = any(result.disposition is EvidenceDisposition.UNRESOLVED for result in failures)
    repairable = any(result.disposition is EvidenceDisposition.REVISE for result in failures)

    if fatal or inaccessible or (repairable and round_number >= max_verifier_rounds):
        decision = VerifierDecision.UNRESOLVED
    elif repairable:
        decision = VerifierDecision.REVISE
    else:
        decision = VerifierDecision.PASS

    feedback_parts: list[str] = []
    if fatal:
        feedback_parts.append("fatal evidence integrity failure")
    if inaccessible:
        feedback_parts.append("one or more evidence locators are inaccessible")
    if repairable:
        feedback_parts.append("repairable evidence locator failure")
    feedback = "; ".join(feedback_parts)
    result = EvidenceGateResult(
        finding_id=finding.finding_id,
        decision=decision,
        primary_results=primary_summary.results,
        counter_results=counter_summary.results,
        reopened_primary=_references_for_results(finding.evidence, primary_summary.results),
        reopened_counter=_references_for_results(finding.counter_evidence, counter_summary.results),
        reopened_snippets={
            validation.locator: validation.snippet or ""
            for validation in all_results
            if validation.valid and validation.snippet is not None
        },
        failed_locators=failed_locators,
        feedback=feedback,
        fatal_integrity_failure=fatal,
        evidence_inaccessible=inaccessible,
        repairable=repairable,
    )
    if raise_on_fatal and fatal:
        raise EvidenceGateError(feedback or "fatal evidence integrity failure")
    return result


def gate_evidence(*args, **kwargs) -> EvidenceGateResult:
    """Short alias for :func:`evaluate_evidence_gate`."""

    return evaluate_evidence_gate(*args, **kwargs)


def build_evidence_gate(*args, **kwargs) -> EvidenceGateResult:
    """Descriptive alias for callers constructing a gate artifact."""

    return evaluate_evidence_gate(*args, **kwargs)


def assert_evidence_gate(result: EvidenceGateResult) -> EvidenceGateResult:
    """Raise for a fatal gate while returning non-fatal outcomes unchanged."""

    if result.fatal_integrity_failure:
        raise EvidenceGateError(result.feedback or "fatal evidence integrity failure")
    return result
