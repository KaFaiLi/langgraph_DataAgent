"""Contracts shared by deterministic and adversarial verification.

The review graph stores these models as JSON-friendly Pydantic data.  The
models intentionally describe *what* was checked and decided; source access,
LLM invocation, and graph routing live in the verification/orchestration
packages respectively.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding

# Importing this validator contract here keeps evidence-gate artifacts typed at
# the persistence seam.  ``evidence_validator`` only imports domain evidence
# and source contracts, so this does not create a cycle.
from data_agent.review.ingestion.evidence_validator import EvidenceValidationResult


class VerifierDecision(StrEnum):
    """Outcome of one verifier pass over one finding."""

    PASS = "pass"
    REVISE = "revise"
    REJECT = "reject"
    UNRESOLVED = "unresolved"


class ChallengeType(StrEnum):
    """Generic adversarial questions required before a finding can pass."""

    EVIDENCE_SUPPORT = "evidence_support"
    REPRODUCIBILITY = "reproducibility"
    POPULATION_SCOPE = "population_scope"
    COUNTER_EVIDENCE = "counter_evidence"
    ALTERNATIVE_EXPLANATION = "alternative_explanation"
    TEMPORAL_VALIDITY = "temporal_validity"
    DATA_QUALITY = "data_quality"
    CAUSALITY = "causality"
    CROSS_SOURCE_CONSISTENCY = "cross_source_consistency"
    SEVERITY = "severity"


class ChallengeStatus(StrEnum):
    """Outcome of one independent challenge."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ChallengeResult(BaseModel):
    """One bounded, source-backed adversarial challenge result.

    ``NOT_APPLICABLE`` is represented in data rather than inferred from an
    omitted category.  The pure challenge rules module validates that it has a
    non-empty explanation and that all required categories are present.
    """

    challenge_type: ChallengeType
    status: ChallengeStatus
    explanation: str = Field(default="", max_length=4_000)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=16)
    material: bool = False


class AdversarialCase(BaseModel):
    """Independent research case handed to the adjudicator."""

    finding_id: str
    challenges: list[ChallengeResult] = Field(default_factory=list, max_length=32)
    strongest_counter_hypothesis: str | None = Field(default=None, max_length=4_000)
    contradictory_evidence: list[EvidenceReference] = Field(default_factory=list, max_length=16)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=32)
    assigned_source_paths: list[str] = Field(default_factory=list, max_length=256)
    research_complete: bool = True
    provider_error: bool = False

    @model_validator(mode="after")
    def _unique_challenge_types(self) -> AdversarialCase:
        # Duplicate challenge categories make the deterministic completeness
        # result ambiguous.  Keep parsing strict at this persistence seam.
        categories = [challenge.challenge_type for challenge in self.challenges]
        if len(categories) != len(set(categories)):
            raise ValueError(f"adversarial case {self.finding_id}: duplicate challenge types")
        return self


class AdjudicationResult(BaseModel):
    """High-cost decision based on a finding, evidence gate, and challenge case."""

    finding_id: str
    decision: VerifierDecision
    feedback: str = Field(default="", max_length=4_000)
    checks: list[str] = Field(default_factory=list, max_length=64)
    challenge_summary: list[ChallengeResult] = Field(default_factory=list, max_length=32)
    evidence_gate: "EvidenceGateResult | None" = None  # noqa: UP037
    analyst_response: str | None = Field(default=None, max_length=4_000)
    adversarial_case: AdversarialCase | None = None


class EvidenceGateResult(BaseModel):
    """Deterministic reopening result for primary and counter evidence.

    A gate is deliberately more detailed than a boolean.  Callers need to
    distinguish a repairable citation problem from an inaccessible source and
    a fatal source-integrity change when deciding whether to revise or fail
    closed.
    """

    finding_id: str
    decision: VerifierDecision = VerifierDecision.PASS
    primary_results: list[EvidenceValidationResult] = Field(default_factory=list)
    counter_results: list[EvidenceValidationResult] = Field(default_factory=list)
    reopened_primary: list[EvidenceReference] = Field(default_factory=list)
    reopened_counter: list[EvidenceReference] = Field(default_factory=list)
    reopened_snippets: dict[str, str] = Field(default_factory=dict)
    failed_locators: list[str] = Field(default_factory=list)
    feedback: str = Field(default="", max_length=4_000)
    fatal_integrity_failure: bool = False
    evidence_inaccessible: bool = False
    repairable: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_evidence_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "primary_results" not in data:
            data["primary_results"] = data.get("primary_evidence", data.get("primary", []))
        if "counter_results" not in data:
            data["counter_results"] = data.get("counter_evidence", data.get("counter", []))
        if "reopened_snippets" not in data:
            snippets = {}
            for result in [*data["primary_results"], *data["counter_results"]]:
                if (
                    isinstance(result, dict)
                    and result.get("valid")
                    and result.get("snippet") is not None
                ):
                    snippets[str(result.get("locator", ""))] = str(result["snippet"])
                elif (
                    getattr(result, "valid", False) and getattr(result, "snippet", None) is not None
                ):
                    snippets[str(result.locator)] = str(result.snippet)
            data["reopened_snippets"] = snippets
        return data

    @property
    def valid(self) -> bool:
        """Whether every primary and counter reference reopened successfully."""
        return all(result.valid for result in [*self.primary_results, *self.counter_results])

    @property
    def integrity_failed(self) -> bool:
        """Alias used by PASS guards and callers with older terminology."""
        return self.fatal_integrity_failure

    @property
    def primary_evidence(self) -> list[EvidenceValidationResult]:
        """Compatibility-friendly name for primary validation outcomes."""
        return self.primary_results

    @property
    def counter_evidence(self) -> list[EvidenceValidationResult]:
        """Compatibility-friendly name for counter validation outcomes."""
        return self.counter_results

    @property
    def primary(self) -> list[EvidenceValidationResult]:
        return self.primary_results

    @property
    def counter(self) -> list[EvidenceValidationResult]:
        return self.counter_results


class RuleCheckResult(BaseModel):
    """Pure deterministic result used to guard model-generated ``PASS``."""

    allowed: bool
    blockers: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    feedback: str = ""

    @property
    def can_pass(self) -> bool:
        """Readable alias for callers expressing the PASS decision."""
        return self.allowed

    @property
    def blocked(self) -> bool:
        return not self.allowed


class ChallengeCompletenessResult(BaseModel):
    """Deterministic validation of a challenger's category coverage."""

    valid: bool
    missing: list[ChallengeType] = Field(default_factory=list)
    invalid: list[ChallengeType] = Field(default_factory=list)
    material_blockers: list[ChallengeType] = Field(default_factory=list)
    explanations_required: list[ChallengeType] = Field(default_factory=list)

    @property
    def missing_challenge_types(self) -> list[ChallengeType]:
        """Readable alias used by prompt/routing callers."""
        return self.missing

    @property
    def missing_types(self) -> list[ChallengeType]:
        return self.missing

    @property
    def is_complete(self) -> bool:
        return self.valid


class VerificationTransition(BaseModel):
    """Pure reducer output for one bounded verification round."""

    pending: list[Finding] = Field(default_factory=list)
    verified: list[Finding] = Field(default_factory=list)
    rejected: list[Finding] = Field(default_factory=list)
    unresolved: list[Finding] = Field(default_factory=list)
    history: dict[str, list["VerificationRound"]] = Field(default_factory=dict)  # noqa: UP037
    feedback: str = ""
    complete: bool = True
    round_number: int = 1

    @property
    def active(self) -> list[Finding]:
        """Pending findings that still need a bounded revision pass."""
        return self.pending

    @property
    def is_complete(self) -> bool:
        return self.complete


class CandidateDisposition(StrEnum):
    """How an analyst accounted for a deterministic candidate."""

    FINDING = "finding"
    BENIGN = "benign"
    IMMATERIAL = "immaterial"
    DUPLICATE = "duplicate"
    UNRESOLVED = "unresolved"


class CandidateDispositionRecord(BaseModel):
    """Source-backed analyst accounting for one deterministic candidate."""

    candidate_id: str
    disposition: CandidateDisposition
    reason: str = Field(default="", max_length=4_000)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=16)


class OmissionCandidate(BaseModel):
    """Deterministic signal not linked to an analyst finding."""

    candidate_id: str
    analysis_name: str
    reason: str = ""
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=16)
    materiality_hint: str | None = None
    kind: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OmissionAuditResult(BaseModel):
    """Coverage and materiality result for the bounded omission audit."""

    covered_candidate_ids: list[str] = Field(default_factory=list)
    uncovered_candidates: list[OmissionCandidate] = Field(default_factory=list)
    material_candidate_ids: list[str] = Field(default_factory=list)
    candidate_dispositions: list[CandidateDispositionRecord] = Field(default_factory=list)
    material_omission_exists: bool = False
    rescue_required: bool = False
    rescue_used: bool = False
    unresolved_disclosures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent_materiality(self) -> OmissionAuditResult:
        material_ids = set(self.material_candidate_ids)
        uncovered_ids = {candidate.candidate_id for candidate in self.uncovered_candidates}
        if not material_ids <= uncovered_ids:
            raise ValueError("material candidate ids must refer to uncovered candidates")
        if self.material_omission_exists != bool(material_ids):
            raise ValueError("material_omission_exists must match material_candidate_ids")
        if self.rescue_required and not self.material_omission_exists:
            raise ValueError("rescue_required requires a material omission")
        return self

    @property
    def uncovered_candidate_ids(self) -> list[str]:
        return [candidate.candidate_id for candidate in self.uncovered_candidates]


class LeadChallengeType(StrEnum):
    """Structured semantic objections available to lead review."""

    CONTRADICTION_OMISSION = "contradiction_omission"
    INTRODUCED_CAUSALITY = "introduced_causality"
    SEVERITY_INFLATION = "severity_inflation"
    CONFIDENCE_INFLATION = "confidence_inflation"
    HIDDEN_UNCERTAINTY = "hidden_uncertainty"
    HIDDEN_UNRESOLVED_DEPENDENCY = "hidden_unresolved_dependency"
    INCOHERENT_CLUSTER = "incoherent_cluster"
    MISSED_RELATIONSHIP = "missed_relationship"
    UNSUPPORTED_MISCONDUCT = "unsupported_misconduct"


class ObjectionMateriality(StrEnum):
    """Materiality of a lead-review semantic objection."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LeadChallenge(BaseModel):
    """Structured lead-review objection with deterministic targeting metadata."""

    challenge_type: LeadChallengeType
    materiality: ObjectionMateriality
    explanation: str = Field(default="", max_length=4_000)
    affected_finding_ids: list[str] = Field(default_factory=list, max_length=128)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=16)
    proposed_resolution: str | None = Field(default=None, max_length=4_000)


class VerificationRound(BaseModel):
    """One complete analyst/adjudicator round rendered in the report."""

    round_number: int
    decision: VerifierDecision
    checks: list[str] = Field(default_factory=list)
    feedback: str = ""
    analyst_response: str | None = None
    """The analyst's revision notes answering the previous round's feedback."""

    challenges: list[ChallengeResult] = Field(default_factory=list)
    adversarial_case: AdversarialCase | None = None
    adjudication: AdjudicationResult | None = None
    evidence_gate: EvidenceGateResult | None = None
    research_mode: str | None = None
