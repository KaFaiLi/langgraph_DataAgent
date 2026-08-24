"""Lead review: cross-material synthesis by the high-cost model (spec sections 22-23).

The lead model receives the DeskContext, verified specialist findings,
deterministic cross-source clusters, contradictions, and unresolved
questions. It never re-reads the raw source directory.
"""

from __future__ import annotations

import json
from typing import Annotated

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field, field_validator

from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.reports import FinalFinding, FinalReport, SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.models import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.state import ParentState
from data_agent.skills.review import load_lead_review_skill

MAX_LEAD_FINDINGS = 8
MAX_LEAD_LIST_ITEMS = 8
MAX_LEAD_UNRESOLVED_ITEMS = 32
MAX_FINAL_FINDING_EVIDENCE = 12
MAX_LOCATOR_OWNERS_FOR_DERIVATION = 2
LeadNarrativeItem = Annotated[str, Field(max_length=500)]


class LeadEvidenceReference(EvidenceReference):
    """Concise evidence pointer used only at the lead generation boundary."""

    locator: str = Field(max_length=500)
    quote: str | None = Field(default=None, max_length=500)

    @field_validator("quote", mode="before")
    @classmethod
    def _bound_quote(cls, value: object) -> object:
        return value[:500] if isinstance(value, str) else value


class LeadFinalFinding(FinalFinding):
    """Output-bounded final finding for reliable lead structured generation."""

    final_id: str = Field(max_length=80)
    title: str = Field(max_length=200)
    statement: str = Field(max_length=900)
    derived_from: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[LeadEvidenceReference] = Field(  # type: ignore[assignment]
        default_factory=list, max_length=6
    )
    cross_source_cluster_ids: list[str] = Field(default_factory=list, max_length=6)
    unresolved_dependencies: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("final_id", mode="before")
    @classmethod
    def _bound_final_id(cls, value: object) -> object:
        return value[:80] if isinstance(value, str) else value

    @field_validator("title", mode="before")
    @classmethod
    def _bound_title(cls, value: object) -> object:
        return value[:200] if isinstance(value, str) else value

    @field_validator("statement", mode="before")
    @classmethod
    def _bound_statement(cls, value: object) -> object:
        return value[:900] if isinstance(value, str) else value

    @field_validator("derived_from", mode="before")
    @classmethod
    def _bound_derived_from(cls, value: object) -> object:
        return value[:8] if isinstance(value, list) else value

    @field_validator("evidence", mode="before")
    @classmethod
    def _bound_evidence(cls, value: object) -> object:
        return value[:6] if isinstance(value, list) else value

    @field_validator("cross_source_cluster_ids", mode="before")
    @classmethod
    def _bound_clusters(cls, value: object) -> object:
        return value[:6] if isinstance(value, list) else value

    @field_validator("unresolved_dependencies", mode="before")
    @classmethod
    def _bound_dependencies(cls, value: object) -> object:
        return value[:8] if isinstance(value, list) else value


class LeadDraft(BaseModel):
    """Bounded interpretive fields produced by the lead model.

    Deterministic clusters, the evidence index, and specialist references are
    assembled by Python after synthesis. Keeping those copied structures out
    of the model response materially reduces long structured calls without
    removing any analytical input.
    """

    executive_summary: str = Field(max_length=2_500)
    overall_desk_risk_assessment: str = Field(max_length=1_800)
    key_findings: list[LeadFinalFinding] = Field(default_factory=list, max_length=MAX_LEAD_FINDINGS)
    potential_unauthorized_activity_indicators: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )
    control_weaknesses: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )
    pnl_risk_inconsistencies: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )
    unresolved_questions: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_UNRESOLVED_ITEMS
    )
    recommended_follow_up: list[LeadNarrativeItem] = Field(
        default_factory=list, max_length=MAX_LEAD_LIST_ITEMS
    )

    @field_validator("executive_summary", mode="before")
    @classmethod
    def _bound_summary(cls, value: object) -> object:
        return value[:2_500] if isinstance(value, str) else value

    @field_validator("overall_desk_risk_assessment", mode="before")
    @classmethod
    def _bound_assessment(cls, value: object) -> object:
        return value[:1_800] if isinstance(value, str) else value

    @field_validator("key_findings", mode="before")
    @classmethod
    def _bound_key_findings(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [
            item.model_dump(mode="json") if isinstance(item, FinalFinding) else item
            for item in value[:MAX_LEAD_FINDINGS]
        ]

    @field_validator(
        "potential_unauthorized_activity_indicators",
        "control_weaknesses",
        "pnl_risk_inconsistencies",
        "recommended_follow_up",
        mode="before",
    )
    @classmethod
    def _bound_narrative_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:500] if isinstance(item, str) else item for item in value[:8]]

    @field_validator("unresolved_questions", mode="before")
    @classmethod
    def _bound_unresolved(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item[:500] if isinstance(item, str) else item for item in value[:32]]


def _provider(config: RunnableConfig) -> ReviewLLMProvider:
    provider = (config or {}).get("configurable", {}).get("llm_provider")
    if provider is None:
        return DEFAULT_LLM_PROVIDER
    return provider


LEAD_REVIEW_SYSTEM = load_lead_review_skill().instructions

LEAD_REVIEW_USER = """\
DESK CONTEXT (JSON):
{desk_context}

VERIFIED SPECIALIST FINDINGS (JSON):
{verified}

UNRESOLVED SPECIALIST FINDINGS (JSON):
{unresolved}

CROSS-SOURCE CLUSTERS (JSON):
{clusters}

CONTRADICTION CANDIDATES (JSON):
{contradictions}

SPECIALIST REPORT REFERENCES:
{references}

Produce the final findings report as structured output.
"""


def _collect(state: ParentState) -> dict:
    reports: dict[str, SpecialistReport] = {
        domain: SpecialistReport.model_validate(data)
        for domain, data in state.get("specialist_reports", {}).items()
    }
    verified: list[dict] = []
    unresolved: list[dict] = []
    for report in reports.values():
        verified.extend(f.model_dump(mode="json") for f in report.verified_findings())
        unresolved.extend(f.model_dump(mode="json") for f in report.unresolved_findings())
    return {
        "reports": reports,
        "verified": verified,
        "unresolved": unresolved,
    }


def _finding_payload(items: list[dict]) -> list[dict]:
    """Keep every finding while removing repeated quotes and process-only detail."""

    def locators(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [
            {"locator": reference.get("locator")}
            for reference in value
            if isinstance(reference, dict) and reference.get("locator")
        ]

    return [
        {
            "finding_id": item.get("finding_id"),
            "title": str(item.get("title", ""))[:200],
            "category": item.get("category"),
            "severity": item.get("severity"),
            "confidence": item.get("confidence"),
            "claim": str(item.get("claim", ""))[:900],
            "period": item.get("period"),
            "evidence": locators(item.get("evidence")),
            "alternative_explanations": [
                str(value)[:300] for value in item.get("alternative_explanations", [])[:3]
            ],
            "counter_evidence": locators(item.get("counter_evidence")),
            "verifier_status": item.get("verifier_status"),
            "recommendation": str(item.get("recommendation") or "")[:500],
        }
        for item in items
    ]


def _cluster_payload(items: list[dict]) -> list[dict]:
    """Avoid repeating evidence already present in the specialist findings."""
    useful_fields = (
        "cluster_id",
        "findings",
        "relationship_types",
        "start_date",
        "end_date",
        "shared_entities",
    )
    return [{field: item.get(field) for field in useful_fields} for item in items]


def _compact_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def _previous_draft_payload(value: object) -> dict:
    report = FinalReport.model_validate(value)
    return {
        "executive_summary": report.executive_summary,
        "overall_desk_risk_assessment": report.overall_desk_risk_assessment,
        "key_findings": [item.model_dump(mode="json") for item in report.key_findings],
        "potential_unauthorized_activity_indicators": (
            report.potential_unauthorized_activity_indicators
        ),
        "control_weaknesses": report.control_weaknesses,
        "pnl_risk_inconsistencies": report.pnl_risk_inconsistencies,
        "unresolved_questions": report.unresolved_questions,
        "recommended_follow_up": report.recommended_follow_up,
    }


def _repair_report_structure(report: FinalReport, collected: dict) -> FinalReport:
    """Mechanically enforce support bookkeeping without inventing conclusions.

    Models sometimes copy a valid specialist locator but omit that specialist ID from
    ``derived_from``. Discriminative evidence provides an exact deterministic join;
    widely shared context locators do not. Draft conclusions supported only by
    unresolved findings are moved to the unresolved list instead of being promoted.
    """
    verified = [Finding.model_validate(item) for item in collected["verified"]]
    unresolved = [Finding.model_validate(item) for item in collected["unresolved"]]
    verified_by_id = {finding.finding_id: finding for finding in verified}
    unresolved_by_id = {finding.finding_id: finding for finding in unresolved}
    verified_by_locator: dict[str, list[str]] = {}
    unresolved_by_locator: dict[str, list[str]] = {}
    for finding in verified:
        for reference in finding.evidence:
            verified_by_locator.setdefault(reference.locator, []).append(finding.finding_id)
    for finding in unresolved:
        for reference in finding.evidence:
            unresolved_by_locator.setdefault(reference.locator, []).append(finding.finding_id)
    primary_locators = set(verified_by_locator) | set(unresolved_by_locator)
    owners_by_locator = {
        locator: list(dict.fromkeys(verified_by_locator.get(locator, [])))
        + list(dict.fromkeys(unresolved_by_locator.get(locator, [])))
        for locator in primary_locators
    }

    retained: list[FinalFinding] = []
    unresolved_questions = list(report.unresolved_questions)
    for final in report.key_findings:
        # A specialist's counter-evidence may be copied into the model draft, but it may
        # not become affirmative final-report evidence. Keep only primary specialist
        # evidence; the lead verifier independently reopens the retained locators.
        final.evidence = [
            reference for reference in final.evidence if reference.locator in primary_locators
        ]
        evidence_locators = {reference.locator for reference in final.evidence}
        discriminative_locators = {
            locator
            for locator in evidence_locators
            if len(owners_by_locator.get(locator, [])) <= MAX_LOCATOR_OWNERS_FOR_DERIVATION
        }
        declared = list(dict.fromkeys(final.derived_from))
        derived: list[str] = []
        for finding_id in declared:
            declared_finding = verified_by_id.get(finding_id) or unresolved_by_id.get(finding_id)
            if declared_finding is None:
                continue
            finding_locators = {reference.locator for reference in declared_finding.evidence}
            if finding_locators & discriminative_locators:
                derived.append(finding_id)
        for locator in discriminative_locators:
            for finding_id in owners_by_locator.get(locator, []):
                if finding_id not in derived:
                    derived.append(finding_id)
        # If evidence was omitted entirely, preserve the first verified declaration and
        # copy its exact evidence below. Never use this fallback when supplied evidence
        # points only to unresolved support.
        if not final.evidence and not any(item in verified_by_id for item in derived):
            fallback = next((item for item in declared if item in verified_by_id), None)
            if fallback is not None:
                derived.append(fallback)
        dependencies = [item for item in derived if item in unresolved_by_id]
        retained_support_locators = {
            reference.locator
            for finding_id in derived
            for reference in (
                verified_by_id.get(finding_id) or unresolved_by_id[finding_id]
            ).evidence
        }
        final.evidence = [
            reference
            for reference in final.evidence
            if reference.locator in retained_support_locators
        ]
        final.derived_from = derived
        final.unresolved_dependencies = dependencies
        support = [verified_by_id[item] for item in derived if item in verified_by_id]
        if not support:
            unresolved_questions.append(
                f"Lead draft {final.final_id} ({final.title}) was not promoted because "
                "it has no verified specialist support; investigate its unresolved "
                f"dependencies {sorted(set(derived) & set(unresolved_by_id))}."
            )
            continue
        if not final.evidence:
            copied: list[EvidenceReference] = []
            seen_support_locators: set[str] = set()
            for finding in support:
                for reference in finding.evidence:
                    if reference.locator in seen_support_locators:
                        continue
                    seen_support_locators.add(reference.locator)
                    copied.append(reference)
                    if len(copied) >= 4:
                        break
                if len(copied) >= 4:
                    break
            final.evidence = copied
        # Make every final conclusion reopenable against the complete primary evidence
        # of its declared support. The model chooses the support IDs; Python performs the
        # bounded, exact copy and never introduces a new claim or locator.
        declared_support: list[Finding] = []
        for finding_id in derived:
            declared_finding = verified_by_id.get(finding_id) or unresolved_by_id.get(finding_id)
            if declared_finding is not None:
                declared_support.append(declared_finding)
        enriched = list(final.evidence)
        seen_final_locators = {reference.locator for reference in enriched}
        for finding in declared_support:
            for reference in finding.evidence:
                if reference.locator in seen_final_locators:
                    continue
                seen_final_locators.add(reference.locator)
                enriched.append(reference)
                if len(enriched) >= MAX_FINAL_FINDING_EVIDENCE:
                    break
            if len(enriched) >= MAX_FINAL_FINDING_EVIDENCE:
                break
        final.evidence = enriched
        maximum = max(support, key=lambda finding: SEVERITY_ORDER[finding.severity]).severity
        if SEVERITY_ORDER[final.severity] > SEVERITY_ORDER[maximum]:
            final.severity = maximum
        retained.append(final)

    dependency_ids = {
        dependency for final in retained for dependency in final.unresolved_dependencies
    }
    disclosed = "\n".join(unresolved_questions)
    for finding in unresolved:
        if finding.finding_id in dependency_ids or finding.finding_id in disclosed:
            continue
        unresolved_questions.append(
            f"Unresolved specialist finding {finding.finding_id}: {finding.title}."
        )

    indexed = []
    seen_locators: set[str] = set()
    for reference in [
        *(reference for final in retained for reference in final.evidence),
        *(
            reference
            for cluster in report.cross_source_findings
            for reference in cluster.supporting_evidence
        ),
    ]:
        if reference.locator in seen_locators:
            continue
        seen_locators.add(reference.locator)
        indexed.append(reference)

    report.key_findings = retained
    report.unresolved_questions = unresolved_questions
    report.evidence_index = indexed
    return report


def lead_review(state: ParentState, config: RunnableConfig) -> dict:
    """Run one lead-review pass (fresh, or revision with verifier feedback)."""
    collected = _collect(state)
    clusters = state.get("clusters", [])
    user = LEAD_REVIEW_USER.format(
        desk_context=_compact_json(state.get("desk_context", {})),
        verified=_compact_json(_finding_payload(collected["verified"])),
        unresolved=_compact_json(_finding_payload(collected["unresolved"])),
        clusters=_compact_json(_cluster_payload(clusters)),
        contradictions=_compact_json(state.get("contradictions", [])),
        references=", ".join(
            f"{domain}: {report.report_id}" for domain, report in collected["reports"].items()
        ),
    )
    feedback = state.get("lead_feedback", "")
    if feedback:
        previous = _compact_json(_previous_draft_payload(state.get("final_report", {})))
        user += (
            f"\n\nLEAD VERIFIER FEEDBACK:\n{feedback}\n\nPREVIOUS DRAFT:\n{previous}\n"
            "Revise the report to address every point. Keep final finding IDs stable."
        )

    runnable = _provider(config)(ModelTier.HIGH_COST, LeadDraft)
    output = invoke_structured(
        runnable,
        [SystemMessage(content=LEAD_REVIEW_SYSTEM), HumanMessage(content=user)],
        schema=LeadDraft,
    )
    draft = output if isinstance(output, LeadDraft) else LeadDraft.model_validate(output)
    report = FinalReport.model_validate(
        {
            **draft.model_dump(mode="json"),
            "cross_source_findings": clusters,
            "specialist_report_references": [
                f"{domain}: {specialist.report_id}"
                for domain, specialist in collected["reports"].items()
            ],
        }
    )
    report = _repair_report_structure(report, collected)
    return {"final_report": report.model_dump(mode="json")}
