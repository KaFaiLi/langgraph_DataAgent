"""Finding contract tests."""

from __future__ import annotations

from datetime import date

import pytest

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange

EVIDENCE = EvidenceReference(locator="source://risk.xlsx#sheet=DailyRisk&rows=120:128")


def make_finding(**overrides) -> Finding:
    values = {
        "finding_id": "RISK-001",
        "title": "VaR level shift",
        "category": "limit_breach",
        "severity": Severity.HIGH,
        "confidence": 0.85,
        "claim": "Daily VaR exceeded the effective limit on three consecutive days.",
        "period": DateRange(start=date(2025, 3, 10), end=date(2025, 3, 12)),
        "evidence": [EVIDENCE],
    }
    values.update(overrides)
    return Finding(**values)


def test_valid_finding() -> None:
    finding = make_finding()
    assert finding.verifier_status is VerificationStatus.PENDING
    finding.assert_evidence_policy()


def test_confidence_bounds_enforced() -> None:
    with pytest.raises(ValueError):
        make_finding(confidence=1.5)
    with pytest.raises(ValueError):
        make_finding(confidence=-0.1)


def test_non_observation_finding_requires_evidence() -> None:
    finding = make_finding(evidence=[])
    with pytest.raises(ValueError, match="evidence"):
        finding.assert_evidence_policy()


def test_observation_may_omit_evidence() -> None:
    finding = make_finding(evidence=[], is_observation=True)
    finding.assert_evidence_policy()


def test_optional_fields_default() -> None:
    finding = make_finding(period=None, recommendation=None)
    assert finding.period is None
    assert finding.recommendation is None
    assert finding.alternative_explanations == []
