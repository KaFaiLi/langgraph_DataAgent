"""Final-report validation assertions retained without graph orchestration."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.lead_outputs import (
    MAX_LEAD_UNRESOLVED_ITEMS,
    LeadDraft,
    LeadFinalFinding,
)
from data_agent.review.domain.reports import CrossSourceCluster, FinalReport, SpecialistReport
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange, SourceManifest
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.synthesis.validation import (
    FatalEvidenceIntegrityError,
    FinalValidationRequest,
    validate_final_report,
)
from data_agent.tools.review_context import ToolContext
from tests.review.fixtures.builder import make_risky_tree

LOCATOR = "source://risk_metrics/risk.csv#rows=2:2"
PERIOD = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))


def _validate(state):
    request = FinalValidationRequest(
        context=ToolContext(
            Path(state["source_root"]),
            Path(state["output_dir"]),
            SourceManifest.model_validate(state["manifest"]),
        ),
        reports=[SpecialistReport.model_validate(r) for r in state["specialist_reports"].values()],
        clusters=[CrossSourceCluster.model_validate(c) for c in state.get("clusters", [])],
    )
    return validate_final_report(request, FinalReport.model_validate(state["final_report"]))


def test_lead_draft_can_disclose_every_bounded_specialist_candidate() -> None:
    questions = [f"Question {index}" for index in range(MAX_LEAD_UNRESOLVED_ITEMS)]
    draft = LeadDraft(
        executive_summary="summary",
        overall_desk_risk_assessment="assessment",
        unresolved_questions=questions,
    )
    assert draft.unresolved_questions == questions


def test_lead_output_boundary_repairs_verbose_model_values() -> None:
    finding = _report().key_findings[0].model_dump(mode="json")
    finding["statement"] = "s" * 1_200
    finding["derived_from"] = [f"RISK-{index:03d}" for index in range(12)]
    draft = LeadDraft(
        executive_summary="e" * 3_000,
        overall_desk_risk_assessment="a" * 2_000,
        key_findings=[finding] * 11,
        control_weaknesses=["w" * 700] * 12,
        unresolved_questions=["q" * 700] * 40,
    )

    assert len(draft.executive_summary) == 2_500
    assert len(draft.overall_desk_risk_assessment) == 1_800
    assert len(draft.key_findings) == 8
    assert isinstance(draft.key_findings[0], LeadFinalFinding)
    assert len(draft.key_findings[0].statement) == 900
    assert len(draft.key_findings[0].derived_from) == 8
    assert len(draft.control_weaknesses) == 8
    assert len(draft.control_weaknesses[0]) == 500
    assert len(draft.unresolved_questions) == 32


def _state(tmp_path, report: FinalReport) -> dict:
    source = tmp_path / "source"
    make_risky_tree(source)
    finding = Finding(
        finding_id="RISK-001",
        title="Risk limit breach",
        category="risk",
        severity=Severity.HIGH,
        confidence=0.8,
        claim="Risk exceeded its limit.",
        evidence=[EvidenceReference(locator=LOCATOR)],
        verifier_status=VerificationStatus.PASSED,
    )
    specialist = SpecialistReport(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="risk_metrics",
        title="Risk Metrics Review",
        review_period=PERIOD,
        generated_at=datetime.now(UTC),
        scope="scope",
        findings=[finding],
        overall_conclusion="conclusion",
    )
    return {
        "source_root": str(source),
        "output_dir": str(tmp_path / "out"),
        "manifest": build_catalog(source).model_dump(mode="json"),
        "specialist_reports": {"risk_metrics": specialist.model_dump(mode="json")},
        "final_report": report.model_dump(mode="json"),
        "lead_round": 0,
    }


def _report(*, derived_from: list[str] | None = None) -> FinalReport:
    return FinalReport(
        executive_summary="summary",
        overall_desk_risk_assessment="assessment",
        key_findings=[
            {
                "final_id": "KF-001",
                "title": "Limit breach",
                "severity": "high",
                "confidence": 0.8,
                "statement": "Risk exceeded its limit.",
                "derived_from": derived_from or ["RISK-001"],
                "evidence": [{"locator": LOCATOR}],
            }
        ],
        evidence_index=[EvidenceReference(locator=LOCATOR)],
    )


def test_unknown_derivation_blocks_validation(tmp_path) -> None:
    result = _validate(
        _state(tmp_path, _report(derived_from=["DOES-NOT-EXIST"])),
    )

    assert result
    assert "unknown" in " ".join(result).lower()


def test_missing_final_evidence_blocks_validation(tmp_path) -> None:
    report = _report()
    report.key_findings[0].evidence = []
    result = _validate(
        _state(tmp_path, report),
    )

    assert result
    assert "evidence" in " ".join(result).lower()


def test_source_mutation_fails_immediately_without_model_judgment(tmp_path) -> None:
    state = _state(tmp_path, _report())
    source = Path(state["source_root"]) / "risk_metrics" / "risk.csv"
    source.write_bytes(source.read_bytes().replace(b"3.1", b"9.9", 1))
    with pytest.raises(FatalEvidenceIntegrityError, match="fatal evidence integrity failure"):
        _validate(state)


def _add_unresolved_support(state: dict, *, locator: str = LOCATOR) -> None:
    report = SpecialistReport.model_validate(state["specialist_reports"]["risk_metrics"])
    report.findings.append(
        Finding(
            finding_id="RISK-002",
            title="Unresolved risk detail",
            category="risk",
            severity=Severity.MEDIUM,
            confidence=0.5,
            claim="The source detail remains incomplete.",
            evidence=[EvidenceReference(locator=locator)],
            verifier_status=VerificationStatus.UNRESOLVED,
        )
    )
    state["specialist_reports"]["risk_metrics"] = report.model_dump(mode="json")


def test_duplicate_specialist_ids_block_validation(tmp_path) -> None:
    state = _state(tmp_path, _report())
    duplicate = dict(state["specialist_reports"]["risk_metrics"])
    duplicate["domain"] = "pnl"
    duplicate["report_id"] = "pnl"
    state["specialist_reports"]["pnl"] = duplicate

    result = _validate(state)

    assert result
    assert "duplicate" in " ".join(result).lower()


def test_severity_escalation_blocks_validation(tmp_path) -> None:
    report = _report()
    report.key_findings[0].severity = Severity.CRITICAL

    result = _validate(
        _state(tmp_path, report),
    )

    assert result
    assert "exceeds" in " ".join(result).lower()


def test_non_copied_evidence_blocks_validation(tmp_path) -> None:
    report = _report()
    invented = EvidenceReference(locator="source://risk_metrics/risk.csv#rows=3:3")
    report.key_findings[0].evidence = [invented]
    report.evidence_index = [invented]

    result = _validate(
        _state(tmp_path, report),
    )

    assert result
    assert "not copied" in " ".join(result).lower()


def test_undeclared_unresolved_support_blocks_validation(tmp_path) -> None:
    report = _report(derived_from=["RISK-001", "RISK-002"])
    state = _state(tmp_path, report)
    _add_unresolved_support(state)

    result = _validate(state)

    assert result
    assert "unverified support" in " ".join(result).lower()


def test_verified_and_declared_unresolved_support_can_pass(tmp_path) -> None:
    report = _report(derived_from=["RISK-001", "RISK-002"])
    report.key_findings[0].unresolved_dependencies = ["RISK-002"]
    state = _state(tmp_path, report)
    _add_unresolved_support(state)

    result = _validate(state)

    assert result == []


def test_declared_unresolved_support_may_contribute_distinct_evidence(tmp_path) -> None:
    unresolved_locator = "source://risk_metrics/risk.csv#rows=3:3"
    report = _report(derived_from=["RISK-001", "RISK-002"])
    report.key_findings[0].unresolved_dependencies = ["RISK-002"]
    report.key_findings[0].evidence.append(EvidenceReference(locator=unresolved_locator))
    report.evidence_index.append(EvidenceReference(locator=unresolved_locator))
    state = _state(tmp_path, report)
    _add_unresolved_support(state, locator=unresolved_locator)

    result = _validate(state)

    assert result == []


def test_unknown_cluster_and_missing_evidence_index_block_validation(tmp_path) -> None:
    report = _report()
    report.key_findings[0].cross_source_cluster_ids = ["CLUSTER-404"]
    report.evidence_index = []

    result = _validate(
        _state(tmp_path, report),
    )

    assert result
    assert "cluster" in " ".join(result).lower()
    assert "evidence_index" in " ".join(result)


def test_evidence_index_must_include_cluster_support(tmp_path) -> None:
    report = _report()
    cluster_locator = "source://risk_metrics/risk.csv#rows=3:3"
    cluster = CrossSourceCluster(
        cluster_id="CLUSTER-001",
        findings=["RISK-001"],
        supporting_evidence=[EvidenceReference(locator=cluster_locator)],
    )
    report.key_findings[0].cross_source_cluster_ids = ["CLUSTER-001"]
    report.cross_source_findings = [cluster]
    state = _state(tmp_path, report)
    state["clusters"] = [cluster.model_dump(mode="json")]
    state["specialist_reports"]["risk_metrics"]["findings"][0]["counter_evidence"] = [
        {"locator": cluster_locator}
    ]

    result = _validate(
        state,
    )

    assert result
    assert cluster_locator in " ".join(result)
    assert "evidence_index" in " ".join(result)
