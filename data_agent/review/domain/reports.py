"""Report contracts: specialist reports, cross-source clusters, final findings."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.overview import DataOverview
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import VerificationRound


class SpecialistReport(BaseModel):
    """One specialist's standardized report (the Markdown external contract)."""

    domain: SpecialistDomain
    report_id: str
    title: str
    review_period: DateRange
    generated_at: datetime

    scope: str
    sources_reviewed: list[str] = Field(default_factory=list)
    analysis_performed: list[str] = Field(default_factory=list)
    data_overviews: list[DataOverview] = Field(default_factory=list)

    findings: list[Finding] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    overall_conclusion: str

    verification_history: dict[str, list[VerificationRound]] = Field(default_factory=dict)
    """Per-finding analyst/verifier rounds (rendered in the report template)."""

    @model_validator(mode="after")
    def _unique_finding_ids(self) -> SpecialistReport:
        ids = [finding.finding_id for finding in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError(f"report {self.report_id}: duplicate finding ids in {ids}")
        overview_ids = [overview.overview_id for overview in self.data_overviews]
        if len(overview_ids) != len(set(overview_ids)):
            raise ValueError(f"report {self.report_id}: duplicate overview ids in {overview_ids}")
        return self

    def verified_findings(self) -> list[Finding]:
        """Findings that survived verification (PASSED or REVISED)."""
        return [
            finding
            for finding in self.findings
            if finding.verifier_status in (VerificationStatus.PASSED, VerificationStatus.REVISED)
        ]

    def unresolved_findings(self) -> list[Finding]:
        return [
            finding
            for finding in self.findings
            if finding.verifier_status is VerificationStatus.UNRESOLVED
        ]


class CrossSourceCluster(BaseModel):
    """Deterministically linked findings across specialists (spec section 21)."""

    cluster_id: str
    findings: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)

    start_date: date | None = None
    end_date: date | None = None

    shared_entities: list[str] = Field(default_factory=list)

    supporting_evidence: list[EvidenceReference] = Field(default_factory=list)


class ContradictionCandidate(BaseModel):
    """Two specialist findings that may make opposing claims."""

    contradiction_id: str
    finding_a: str
    finding_b: str
    kind: str
    note: str


class CrossSpecialistAnalysis(BaseModel):
    """Deterministic candidates supplied to lead-review synthesis."""

    clusters: list[CrossSourceCluster] = Field(default_factory=list)
    contradiction_candidates: list[ContradictionCandidate] = Field(default_factory=list)


class FinalFinding(BaseModel):
    """A cross-material conclusion in the lead review (spec section 25)."""

    final_id: str
    title: str
    severity: Severity
    confidence: float
    statement: str

    derived_from: list[str] = Field(default_factory=list)
    """Specialist finding IDs this final finding is built on."""

    evidence: list[EvidenceReference] = Field(default_factory=list)
    cross_source_cluster_ids: list[str] = Field(default_factory=list)
    unresolved_dependencies: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return value

    @model_validator(mode="after")
    def _check_derivation(self) -> FinalFinding:
        if not self.derived_from:
            raise ValueError(
                f"final finding {self.final_id}: every final finding must "
                "reference specialist finding ids"
            )
        return self


class FinalReport(BaseModel):
    """Structured form of ``final_findings.md`` (spec section 25)."""

    executive_summary: str
    overall_desk_risk_assessment: str
    key_findings: list[FinalFinding] = Field(default_factory=list)
    cross_source_findings: list[CrossSourceCluster] = Field(default_factory=list)
    potential_unauthorized_activity_indicators: list[str] = Field(default_factory=list)
    control_weaknesses: list[str] = Field(default_factory=list)
    pnl_risk_inconsistencies: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    recommended_follow_up: list[str] = Field(default_factory=list)
    evidence_index: list[EvidenceReference] = Field(default_factory=list)
    specialist_report_references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_final_ids(self) -> FinalReport:
        ids = [finding.final_id for finding in self.key_findings]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate final finding ids in {ids}")
        return self
