"""Report contract tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.reports import FinalFinding, FinalReport, SpecialistReport
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange


def make_report(**overrides) -> SpecialistReport:
    values = dict(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="RISK",
        title="Risk Metrics Review",
        review_period=DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30)),
        generated_at=datetime(2026, 7, 1, tzinfo=UTC),
        scope="All daily risk files.",
        overall_conclusion="Nothing material.",
    )
    values.update(overrides)
    return SpecialistReport(**values)


def make_finding(finding_id: str = "RISK-001") -> Finding:
    return Finding(
        finding_id=finding_id,
        title="VaR shift",
        category="limit_breach",
        severity=Severity.HIGH,
        confidence=0.8,
        claim="VaR shifted up.",
        evidence=[],
        is_observation=True,
    )


def test_specialist_report_rejects_duplicate_finding_ids() -> None:
    finding = make_finding()
    with pytest.raises(ValueError, match="duplicate"):
        make_report(findings=[finding, finding])


def test_verified_and_unresolved_partitions() -> None:
    passed = make_finding("RISK-001")
    passed.verifier_status = VerificationStatus.PASSED
    unresolved = make_finding("RISK-002")
    unresolved.verifier_status = VerificationStatus.UNRESOLVED
    report = make_report(findings=[passed, unresolved])
    assert [f.finding_id for f in report.verified_findings()] == ["RISK-001"]
    assert [f.finding_id for f in report.unresolved_findings()] == ["RISK-002"]


def test_final_finding_requires_derivation() -> None:
    with pytest.raises(ValueError, match="reference specialist"):
        FinalFinding(
            final_id="FINAL-001",
            title="X",
            severity=Severity.HIGH,
            confidence=0.8,
            statement="Y",
        )


def test_final_report_rejects_duplicate_final_ids() -> None:
    finding = FinalFinding(
        final_id="FINAL-001",
        title="X",
        severity=Severity.HIGH,
        confidence=0.8,
        statement="Y",
        derived_from=["RISK-001"],
    )
    with pytest.raises(ValueError, match="duplicate"):
        FinalReport(
            executive_summary="s",
            overall_desk_risk_assessment="a",
            key_findings=[finding, finding],
        )


