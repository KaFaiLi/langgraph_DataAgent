"""Verifier contract tests."""

from __future__ import annotations

from data_agent.review.domain.verification import (
    AdjudicationResult,
    EvidenceGateResult,
    VerifierDecision,
)


def test_adjudication_result_pass() -> None:
    result = AdjudicationResult(
        finding_id="RISK-001",
        decision=VerifierDecision.PASS,
        checks=["locator reopened", "calculation reproduced"],
    )
    assert result.decision is VerifierDecision.PASS
    assert result.checks == ["locator reopened", "calculation reproduced"]


def test_adjudication_result_revise_carries_feedback() -> None:
    result = AdjudicationResult(
        finding_id="RISK-002",
        decision=VerifierDecision.REVISE,
        feedback="Severity too high: only one day breached and it reversed.",
    )
    assert result.feedback


def test_inaccessible_evidence_blocks_pass() -> None:
    result = EvidenceGateResult(
        finding_id="RISK-003",
        decision=VerifierDecision.UNRESOLVED,
        evidence_inaccessible=True,
        feedback="Locator source://missing.xlsx#page=1 could not be reopened.",
    )
    assert result.evidence_inaccessible
    assert result.decision is not VerifierDecision.PASS
