from __future__ import annotations

from datetime import date

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import (
    CandidateDisposition,
    CandidateDispositionRecord,
)
from data_agent.review.orchestration.specialist.omission import audit_omission_candidates
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime, SpecialistSpec
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


def test_omission_audit_requires_explicit_candidate_relationship() -> None:
    audit = audit_omissions(_analysis(), [_finding()])

    assert audit.covered_candidate_ids == []
    assert audit.material_omission_exists


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


def test_omission_node_requests_one_rescue_then_routes_to_finalize(tool_ctx) -> None:
    spec = SpecialistSpec(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="RISK",
        domain_label="Risk Metrics",
        policy_text="",
        analyses_runner=lambda _ctx, _paths: [],
    )
    runtime = SpecialistRuntime(spec=spec)
    candidate = _analysis()[0]["flag_candidates"][0]
    candidate_id = audit_omissions(_analysis(), []).uncovered_candidate_ids[0]
    state = {
        "source_paths": ["risk_metrics/risk.csv"],
        "analyses": _analysis(),
        "verified_findings": [],
        "rejected_findings": [],
        "unresolved_findings": [],
        "candidate_dispositions": [],
        "omission_rescue_used": False,
    }
    first = audit_omission_candidates(
        runtime,
        state,
        {"configurable": {"tool_ctx": tool_ctx}},
    )

    assert first["omission_rescue_requested"] is True
    assert first["omission_rescue_used"] is True
    assert first["research_mode"] == "omission_rescue"
    assert candidate["kind"] in first["verifier_feedback"]
    assert candidate_id in first["omission_audit"]["material_candidate_ids"]

    state.update(first)
    benign = CandidateDispositionRecord(
        candidate_id=candidate_id,
        disposition=CandidateDisposition.BENIGN,
        reason="Documented test-row exception.",
        evidence=[EvidenceReference(locator=LOCATOR)],
    )
    state["candidate_dispositions"] = [benign.model_dump(mode="json")]
    second = audit_omission_candidates(
        runtime,
        state,
        {"configurable": {"tool_ctx": tool_ctx}},
    )
    assert second["omission_rescue_requested"] is False
    assert second["loop_status"] == "complete"
    assert second["omission_audit"]["rescue_used"] is True
    assert second["omission_audit"]["material_candidate_ids"] == []
