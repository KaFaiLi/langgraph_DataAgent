"""Behavior tests for the lead-review skill's deterministic analysis interface."""

from __future__ import annotations

from datetime import date, datetime

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.reports import CrossSpecialistAnalysis, SpecialistReport
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.skills.review import load_lead_analysis_runner

EVIDENCE = EvidenceReference(locator="source://risk.csv#rows=2:2")
RUN_ANALYSIS = load_lead_analysis_runner()


def make_finding(
    finding_id: str,
    claim: str,
    *,
    start: str = "2025-03-10",
    end: str = "2025-03-12",
    category: str = "limit_breach",
) -> Finding:
    return Finding(
        finding_id=finding_id,
        title=claim[:50],
        category=category,
        severity=Severity.HIGH,
        confidence=0.8,
        claim=claim,
        period=DateRange(start=date.fromisoformat(start), end=date.fromisoformat(end)),
        evidence=[EVIDENCE],
        verifier_status=VerificationStatus.PASSED,
    )


def analyze(*findings: Finding) -> CrossSpecialistAnalysis:
    report = SpecialistReport(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="TEST",
        title="Test specialist report",
        review_period=DateRange(start=date(2025, 1, 1), end=date(2025, 12, 31)),
        generated_at=datetime(2025, 12, 31),
        scope="Test",
        findings=list(findings),
        overall_conclusion="Test",
    )
    return CrossSpecialistAnalysis.model_validate(RUN_ANALYSIS([report]))


def test_same_day_and_entity_link_into_one_cluster() -> None:
    result = analyze(
        make_finding("RISK-001", "VaR increased above the FX options limit."),
        make_finding("PNL-001", "Large loss in FX options PnL.", category="pnl_jump"),
    )

    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    assert cluster.findings == ["PNL-001", "RISK-001"]
    assert "same_date" in cluster.relationship_types
    assert "shared_entity" in cluster.relationship_types


def test_unrelated_findings_stay_separate() -> None:
    result = analyze(
        make_finding(
            "RISK-001", "VaR increased for rates.", start="2025-01-02", end="2025-01-03"
        ),
        make_finding(
            "CONTROLS-001",
            "Credit mapping breach closed late.",
            start="2025-06-01",
            end="2025-06-02",
            category="resolution_late",
        ),
    )

    assert len(result.clusters) == 2


def test_same_category_alone_does_not_merge() -> None:
    result = analyze(
        make_finding(
            "RISK-001", "VaR increased for rates.", start="2025-01-02", end="2025-01-03"
        ),
        make_finding(
            "RISK-002", "Exposure up on credit.", start="2025-06-01", end="2025-06-02"
        ),
    )

    assert len(result.clusters) == 2


def test_contradiction_candidates_pair_opposite_polarity() -> None:
    result = analyze(
        make_finding("RISK-001", "VaR increased and exceeded the limit."),
        make_finding(
            "COMMENTARY-001",
            "VaR remained within limits throughout the period.",
            category="commentary",
        ),
    )

    assert len(result.contradiction_candidates) == 1
    contradiction = result.contradiction_candidates[0]
    assert contradiction.finding_a == "RISK-001"
    assert contradiction.finding_b == "COMMENTARY-001"


def test_no_contradiction_when_polarities_agree() -> None:
    result = analyze(
        make_finding("RISK-001", "VaR increased sharply."),
        make_finding("PNL-001", "PnL losses increased."),
    )

    assert result.contradiction_candidates == []


def test_entity_tokens_require_recurrence() -> None:
    result = analyze(
        make_finding("RISK-001", "VaR increased for the options book."),
        make_finding("PNL-001", "Options book PnL fell."),
    )

    assert "options" in result.clusters[0].shared_entities


def test_numeric_tokens_are_not_entities() -> None:
    result = analyze(
        make_finding("RISK-001", "VaR event 2026 affected Atlas."),
        make_finding("PNL-001", "PnL event 2026 affected Harbor."),
    )

    assert "2026" not in result.clusters[0].shared_entities


def test_one_generic_shared_token_does_not_merge_findings() -> None:
    result = analyze(
        make_finding(
            "RISK-001", "Atlas workflow anomaly.", start="2025-01-02", end="2025-01-03"
        ),
        make_finding(
            "PNL-001", "Harbor workflow delay.", start="2025-06-01", end="2025-06-02"
        ),
    )

    assert len(result.clusters) == 2


def test_broad_overlapping_periods_are_not_treated_as_same_day_events() -> None:
    result = analyze(
        make_finding(
            "RISK-001",
            "Atlas VaR profile over the annual window.",
            start="2025-01-01",
            end="2025-12-31",
        ),
        make_finding(
            "PNL-001",
            "Harbor PnL profile over the second half.",
            start="2025-07-01",
            end="2025-12-31",
        ),
    )

    assert len(result.clusters) == 2
