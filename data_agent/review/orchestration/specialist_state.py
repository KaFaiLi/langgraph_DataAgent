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

    review_period: dict[str, str]  # {"start": iso, "end": iso}
    scope: str
    source_ids: list[str]
    source_paths: list[str]

    desk_context: dict

    material_summary: str
    analyses: list[dict]  # deterministic AnalysisResult dumps
    research_summary: str
    research_trace: list[dict]
    research_round: int
    research_budget_exhausted: bool

    candidate_findings: list[dict]  # Finding dumps under active verification
    initial_candidates: list[dict]  # first-round drafts (eval telemetry, D7)
    verification_history: dict[str, list[dict]]  # finding_id -> VerificationRound dumps
    rejected_findings: list[dict]
    unresolved_findings: list[dict]
    verified_findings: list[dict]

    verifier_feedback: str
    verifier_round: int
    loop_status: str  # "running" | "complete"

    report: dict | None  # SpecialistReport dump
    markdown: str
    error: str | None


def dumps_finding(finding: Finding) -> dict:
    return finding.model_dump(mode="json")


def loads_finding(data: dict) -> Finding:
    return Finding.model_validate(data)


def dumps_round(record: VerificationRound) -> dict:
    return record.model_dump(mode="json")


def dumps_period(period: DateRange) -> dict[str, str]:
    return {"start": period.start.isoformat(), "end": period.end.isoformat()}


def loads_period(data: dict[str, str]) -> DateRange:
    return DateRange(start=data["start"], end=data["end"])  # type: ignore[arg-type]


def domain_of(state: SpecialistState) -> SpecialistDomain:
    return SpecialistDomain(state["domain"])

