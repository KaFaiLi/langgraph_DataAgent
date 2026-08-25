"""Pure contract tests for bounded adversarial verification."""

from __future__ import annotations

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.verification import (
    AdjudicationResult,
    AdversarialCase,
    CandidateDisposition,
    CandidateDispositionRecord,
    ChallengeResult,
    ChallengeStatus,
    EvidenceGateResult,
    VerifierDecision,
)
from data_agent.review.verification import (
    REQUIRED_CHALLENGE_TYPES,
    audit_omissions,
    can_pass,
    candidate_locators,
    check_challenge_completeness,
    reduce_verification,
    stable_candidate_id,
)


def _finding(*, severity: Severity = Severity.MEDIUM) -> Finding:
    return Finding(
        finding_id="F-1",
        title="Threshold breach",
        category="risk",
        severity=severity,
        confidence=0.8,
        claim="A threshold was breached.",
        evidence=[EvidenceReference(locator="source://risk.csv#rows=2:3")],
    )


def _complete_challenges() -> list[ChallengeResult]:
    return [
        ChallengeResult(
            challenge_type=challenge_type,
            status=ChallengeStatus.PASS,
            explanation="Checked independently.",
        )
        for challenge_type in REQUIRED_CHALLENGE_TYPES
    ]


def test_missing_challenge_is_never_implicit_not_applicable() -> None:
    result = check_challenge_completeness(_complete_challenges()[:-1])

    assert not result.valid
    assert result.missing == [REQUIRED_CHALLENGE_TYPES[-1]]


def test_material_unknown_and_severity_ceiling_block_pass() -> None:
    challenges = _complete_challenges()
    challenges[0] = challenges[0].model_copy(
        update={"status": ChallengeStatus.UNKNOWN, "material": True}
    )

    result = can_pass(
        _finding(severity=Severity.HIGH),
        challenges,
        severity_ceiling=Severity.MEDIUM,
    )

    assert not result.allowed
    assert any("material unknown" in blocker for blocker in result.blockers)
    assert any("exceeds deterministic ceiling" in blocker for blocker in result.blockers)


def test_observation_without_primary_evidence_cannot_pass() -> None:
    finding = _finding().model_copy(update={"is_observation": True, "evidence": []})

    result = can_pass(finding, _complete_challenges())

    assert not result.allowed
    assert any("primary evidence is missing" in blocker for blocker in result.blockers)


def test_surviving_contradiction_overrides_pass() -> None:
    case = AdversarialCase(
        finding_id="F-1",
        challenges=_complete_challenges(),
        contradictory_evidence=[EvidenceReference(locator="source://risk.csv#rows=9:9")],
    )

    result = can_pass(_finding(), case)

    assert not result.allowed
    assert "adversarial contradiction remains unresolved" in result.blockers


def test_second_revise_becomes_unresolved() -> None:
    finding = _finding()
    result = AdjudicationResult(
        finding_id=finding.finding_id,
        decision=VerifierDecision.REVISE,
        feedback="Resolve the contradiction.",
    )

    transition = reduce_verification([finding], [result], round_number=2)

    assert transition.pending == []
    assert transition.unresolved[0].verifier_status is VerificationStatus.UNRESOLVED
    assert transition.history[finding.finding_id][0].round_number == 2


def test_failed_evidence_integrity_overrides_model_pass() -> None:
    finding = _finding()
    gate = EvidenceGateResult(
        finding_id=finding.finding_id,
        decision=VerifierDecision.UNRESOLVED,
        fatal_integrity_failure=True,
        failed_locators=[finding.evidence[0].locator],
    )
    result = AdjudicationResult(
        finding_id=finding.finding_id,
        decision=VerifierDecision.PASS,
        challenge_summary=_complete_challenges(),
    )

    transition = reduce_verification(
        [finding],
        [result],
        evidence_gates={finding.finding_id: gate},
    )

    assert transition.verified == []
    assert transition.unresolved[0].verifier_status is VerificationStatus.UNRESOLVED


def test_candidate_identity_uses_arbitrary_locator_fields_and_ignores_prose() -> None:
    first = {
        "kind": "limit_breach",
        "prior_locator": "source://risk.csv#rows=2:3",
        "summary": "first wording",
    }
    second = {**first, "summary": "different generated wording"}

    assert candidate_locators(first) == {"source://risk.csv#rows=2:3"}
    assert stable_candidate_id("limits", first) == stable_candidate_id("limits", second)


def test_locator_overlap_counts_as_candidate_coverage() -> None:
    candidate = {
        "kind": "limit_breach",
        "locator": "source://risk.csv#rows=2:4",
        "severity": "high",
    }

    result = audit_omissions(
        [{"name": "limits", "flag_candidates": [candidate]}],
        [_finding()],
    )

    assert result.material_omission_exists is False
    assert len(result.covered_candidate_ids) == 1


def test_unsupported_disposition_does_not_hide_material_omission() -> None:
    candidate = {
        "kind": "limit_breach",
        "locator": "source://other.csv#rows=8:8",
        "severity": "high",
    }
    candidate_id = stable_candidate_id("limits", candidate)
    disposition = CandidateDispositionRecord(
        candidate_id=candidate_id,
        disposition=CandidateDisposition.BENIGN,
        reason="Model says benign without reopening a source.",
    )

    result = audit_omissions(
        [{"name": "limits", "flag_candidates": [candidate]}],
        [],
        candidate_dispositions=[disposition],
    )

    assert result.rescue_required
    assert result.material_candidate_ids == [candidate_id]


def test_source_backed_disposition_covers_candidate() -> None:
    candidate = {
        "kind": "limit_breach",
        "locator": "source://other.csv#rows=8:8",
        "severity": "high",
    }
    candidate_id = stable_candidate_id("limits", candidate)
    disposition = CandidateDispositionRecord(
        candidate_id=candidate_id,
        disposition=CandidateDisposition.BENIGN,
        reason="The approved exception register explains the row.",
        evidence=[EvidenceReference(locator="source://exceptions.csv#rows=4:4")],
    )

    result = audit_omissions(
        [{"name": "limits", "flag_candidates": [candidate]}],
        [],
        candidate_dispositions=[disposition],
    )

    assert result.material_omission_exists is False
    assert result.covered_candidate_ids == [candidate_id]
