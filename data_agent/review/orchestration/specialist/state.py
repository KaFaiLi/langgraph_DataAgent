"""LangGraph state for one specialist review.

State values are JSON-friendly primitives (dicts/lists/strings) so LangGraph
checkpointers can serialize them; Pydantic domain objects are rehydrated at
node boundaries.
"""

from __future__ import annotations

from typing import TypedDict

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import VerificationRound


class SpecialistState(TypedDict, total=False):
    """One specialist's working state through the review graph."""

    task_id: str
    domain: str
    report_id: str
    domain_label: str

    review_period: dict[str, str]
    scope: str
    source_ids: list[str]
    source_paths: list[str]

    desk_context: dict

    material_summary: str
    analyses: list[dict]
    research_summary: str
    research_trace: list[dict]
    research_round: int
    research_budget_exhausted: bool

    candidate_findings: list[dict]
    initial_candidates: list[dict]
    candidate_dispositions: list[dict]
    verification_history: dict[str, list[dict]]
    rejected_findings: list[dict]
    unresolved_findings: list[dict]
    verified_findings: list[dict]

    verifier_feedback: str
    verifier_round: int
    loop_status: str

    # Verification artifacts are plain JSON at the graph seam.  Typed
    # EvidenceGateResult/AdversarialCase/AdjudicationResult instances are
    # rehydrated only inside their respective nodes.
    evidence_gates: dict[str, dict]
    adversarial_cases: dict[str, dict]
    adversarial_trace: dict[str, list[dict]]
    adversarial_errors: dict[str, str]
    adjudications: dict[str, dict]
    research_mode: str
    omission_audit: dict | None
    omission_rescue_used: bool
    omission_rescue_requested: bool

    report: dict | None
    markdown: str
    error: str | None


def dumps_finding(finding: Finding) -> dict:
    """Serialize a domain finding at a graph state seam."""
    return finding.model_dump(mode="json")


def loads_finding(data: dict) -> Finding:
    """Rehydrate a domain finding from JSON-friendly graph state."""
    return Finding.model_validate(data)


def dumps_round(record: VerificationRound) -> dict:
    """Serialize one verification-round record."""
    return record.model_dump(mode="json")


def dumps_period(period: DateRange) -> dict[str, str]:
    """Serialize a review period without retaining a Pydantic object in state."""
    return {"start": period.start.isoformat(), "end": period.end.isoformat()}


def loads_period(data: dict[str, str]) -> DateRange:
    """Rehydrate a review period from ISO strings."""
    return DateRange(start=data["start"], end=data["end"])  # type: ignore[arg-type]


def domain_of(state: SpecialistState) -> SpecialistDomain:
    """Return the typed domain represented by specialist state."""
    return SpecialistDomain(state["domain"])


__all__ = [
    "SpecialistState",
    "domain_of",
    "dumps_finding",
    "dumps_period",
    "dumps_round",
    "loads_finding",
    "loads_period",
]
