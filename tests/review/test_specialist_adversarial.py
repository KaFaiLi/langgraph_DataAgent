from __future__ import annotations

from datetime import date

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.outputs import ChallengerChallenge, ChallengerOutput
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import (
    AdjudicationResult,
    ChallengeStatus,
    ChallengeType,
    EvidenceGateResult,
    VerifierDecision,
)
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.verification import reduce_verification
from data_agent.review.verification.challenge_validation import _sanitize_challenge_case
from data_agent.review.verification.evidence import EvidenceGateError, evaluate_evidence_gate
from data_agent.review.verification.projection import _finding_projection


def _finding() -> Finding:
    return Finding(
        finding_id="RISK-F-1",
        title="Repeated breach",
        category="limit",
        severity=Severity.HIGH,
        confidence=0.91,
        claim="The limit was breached repeatedly.",
        period=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 2)),
        recommendation="Escalate.",
        is_observation=True,
    )


def test_challenger_projection_hides_anchoring_fields() -> None:
    projection = _finding_projection(_finding())
    assert "severity" not in projection
    assert "confidence" not in projection
    assert "recommendation" not in projection
    assert projection["claim"] == "The limit was breached repeatedly."


def test_invalid_challenger_locator_becomes_material_unknown(tool_ctx) -> None:
    output = ChallengerOutput(
        finding_id="RISK-F-1",
        challenges=[
            ChallengerChallenge(
                challenge_type=ChallengeType.EVIDENCE_SUPPORT,
                status=ChallengeStatus.PASS,
                explanation="The cited region supports the claim.",
                evidence=[{"locator": "source://not-assigned.csv#rows=2:2"}],
            )
        ],
    )
    case = _sanitize_challenge_case(
        output,
        finding_id="RISK-F-1",
        validator=EvidenceValidator.source_backed(tool_ctx.source_root, tool_ctx.manifest),
        assigned_paths=[tool_ctx.manifest.sources[0].path],
    )
    challenge = next(
        item for item in case.challenges if item.challenge_type is ChallengeType.EVIDENCE_SUPPORT
    )
    assert challenge.status is ChallengeStatus.UNKNOWN
    assert challenge.material is True
    assert challenge.evidence == []


def test_evidence_gate_default_is_pass() -> None:
    gate = EvidenceGateResult(finding_id="RISK-F-1")
    assert gate.decision is VerifierDecision.PASS


def test_second_revise_is_unresolved() -> None:
    finding = _finding()
    transition = reduce_verification(
        [finding],
        {
            finding.finding_id: AdjudicationResult(
                finding_id=finding.finding_id,
                decision=VerifierDecision.REVISE,
                feedback="Still unresolved.",
            )
        },
        round_number=2,
        max_verifier_rounds=2,
    )
    assert transition.pending == []
    assert transition.unresolved[0].verifier_status.value == "unresolved"


def test_fatal_source_mutation_raises_while_missing_source_is_unresolved(tool_ctx) -> None:
    source = tool_ctx.manifest.sources[0]
    finding = _finding().model_copy(
        update={"evidence": [EvidenceReference(locator=f"source://{source.path}#rows=2:2")]}
    )
    path = tool_ctx.source_root / source.path
    original = path.read_bytes()
    path.write_bytes(original + b"changed")
    validator = EvidenceValidator.source_backed(tool_ctx.source_root, tool_ctx.manifest)
    try:
        try:
            evaluate_evidence_gate(finding, validator, raise_on_fatal=True)
        except EvidenceGateError:
            pass
        else:
            raise AssertionError("source mutation must fail closed")
    finally:
        path.write_bytes(original)

    path.unlink()
    missing = EvidenceValidator.source_backed(tool_ctx.source_root, tool_ctx.manifest)
    result = evaluate_evidence_gate(finding, missing)
    assert result.evidence_inaccessible is True
    assert result.decision is VerifierDecision.UNRESOLVED
