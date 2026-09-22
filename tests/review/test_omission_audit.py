from __future__ import annotations

from datetime import date

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import (
    CandidateDisposition,
    CandidateDispositionRecord,
)
from data_agent.review.verification.omission import audit_omissions

LOCATOR = "source://risk_metrics/risk.csv#rows=2:2"


def _finding(*, candidate_ids: list[str] | None = None) -> Finding:
    return Finding(
        finding_id="RISK-F-1",
        title="Material breach",
        category="limit",
        severity=Severity.HIGH,
        confidence=0.8,
        claim="The limit was exceeded.",
        period=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 2)),
        evidence=[EvidenceReference(locator=LOCATOR)],
        deterministic_candidate_ids=candidate_ids or [],
    )


def _analysis() -> list[dict]:
    return [
        {
            "name": "limits",
            "flag_candidates": [{"kind": "breach", "locator": LOCATOR, "severity": "high"}],
        }
    ]


def test_omission_audit_uses_stable_ids_and_locator_overlap() -> None:
    audit = audit_omissions(_analysis(), [_finding()])

    assert audit.covered_candidate_ids
    assert not audit.material_omission_exists


def test_finding_disposition_without_finding_does_not_cover_candidate() -> None:
    candidate = _analysis()[0]["flag_candidates"][0]
    disposition = CandidateDispositionRecord(
        candidate_id="limits:breach:wrong",
        disposition=CandidateDisposition.FINDING,
        reason="A finding was intended.",
        evidence=[EvidenceReference(locator=LOCATOR)],
    )

    audit = audit_omissions(_analysis(), [], candidate_dispositions=[disposition])

    assert audit.material_omission_exists
    assert audit.uncovered_candidates[0].details["kind"] == candidate["kind"]


def test_non_finding_disposition_requires_reason_and_evidence() -> None:
    candidate_id = next(iter(audit_omissions(_analysis(), []).uncovered_candidate_ids))
    incomplete = CandidateDispositionRecord(
        candidate_id=candidate_id,
        disposition=CandidateDisposition.BENIGN,
    )
    audit = audit_omissions(_analysis(), [], candidate_dispositions=[incomplete])
    assert audit.material_omission_exists

    supported = incomplete.model_copy(
        update={
            "reason": "The breach is a documented test-row exception.",
            "evidence": [EvidenceReference(locator=LOCATOR)],
        }
    )
    covered = audit_omissions(_analysis(), [], candidate_dispositions=[supported])
    assert not covered.material_omission_exists


def test_omission_rescue_records_uncovered_then_supported_dispositions(tool_ctx) -> None:
    from data_agent.review.domain.analysis import AnalysisResult
    from data_agent.tools.review_operations import OmissionRequest, audit_candidates

    analyses = [
        AnalysisResult.model_validate({**item, "summary": "Limit analysis"}) for item in _analysis()
    ]
    first = audit_candidates(
        OmissionRequest(tool_ctx, ("risk_metrics/risk.csv",), analyses, rescue_used=True)
    )
    assert first.rescue_used and first.material_omission_exists
    candidate_id = first.uncovered_candidate_ids[0]
    disposition = CandidateDispositionRecord(
        candidate_id=candidate_id,
        disposition=CandidateDisposition.BENIGN,
        reason="Documented test-row exception.",
        evidence=[EvidenceReference(locator=LOCATOR)],
    )
    second = audit_candidates(
        OmissionRequest(
            tool_ctx,
            ("risk_metrics/risk.csv",),
            analyses,
            dispositions=[disposition],
            rescue_used=True,
        )
    )
    assert second.rescue_used
    assert not second.material_omission_exists
