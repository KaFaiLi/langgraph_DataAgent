"""Analyst drafting and bounded revision node."""

from __future__ import annotations

import json
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.verification import CandidateDispositionRecord
from data_agent.review.llm import ModelTier
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.finding_policy import normalize_findings
from data_agent.review.orchestration.prompt_projection import (
    MAX_ANALYSIS_PROMPT_CHARS,
    MAX_REVISION_ANALYSIS_CHARS,
    bounded_analyses_json,
    bounded_revision_feedback,
    revision_candidates_json,
)
from data_agent.review.orchestration.specialist.prompts import analyst_system_prompt
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.schemas import AnalystOutput
from data_agent.review.orchestration.specialist.state import (
    SpecialistState,
    dumps_finding,
    loads_finding,
)


def draft_findings(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Generate or revise bounded findings using the low-cost analyst model."""
    desk_json = json.dumps(state.get("desk_context", {}), indent=2)
    feedback = state.get("verifier_feedback", "")
    analyses_json = bounded_analyses_json(
        list(state.get("analyses", [])),
        max_chars=(MAX_REVISION_ANALYSIS_CHARS if feedback else MAX_ANALYSIS_PROMPT_CHARS),
    )
    system = analyst_system_prompt(
        runtime.spec.domain_label,
        desk_json,
        state.get("material_summary", ""),
        analyses_json,
        runtime.spec.research_guidance,
    )
    if state.get("research_mode") == "omission_rescue":
        omission = json.dumps(state.get("omission_audit", {}), indent=2, default=str)
        user = (
            "This is the single bounded omission-rescue opportunity after the normal "
            "verification rounds have settled. Investigate only the material deterministic "
            "candidates listed below. Do not rewrite or restate settled findings. For each "
            "candidate, either create a new evidence-backed finding, or return a benign, "
            "immaterial, duplicate, or unresolved candidate disposition with a concrete "
            "reason and source-backed evidence. Any candidate you cannot resolve remains an "
            "unresolved disclosure.\n\n"
            f"OMISSION AUDIT:\n{omission[: runtime.max_revision_context_chars]}\n\n"
            f"RESEARCH SUMMARY:\n{state.get('research_summary', '')}\n\n"
            "Return only the bounded analyst schema."
        )
    elif feedback:
        previous = revision_candidates_json(list(state.get("candidate_findings", [])))
        fixed_context_chars = len(previous) + 400
        bounded_feedback = bounded_revision_feedback(
            feedback,
            max_chars=max(runtime.max_revision_context_chars - fixed_context_chars, 1_000),
        )
        user = (
            "The verifier rejected your previous draft. Revise the findings to "
            "address every point, keeping their finding IDs and evidence locators.\n\n"
            f"VERIFIER FEEDBACK:\n{bounded_feedback}\n\n"
            f"PREVIOUS DRAFT:\n{previous}\n\n"
            f"RESEARCH SUMMARY:\n{state.get('research_summary', '')}\n\n"
            "Return the corrected findings."
        )
    else:
        user = (
            "Analyze the material and the deterministic analysis results. Produce "
            "findings for every material risk observation or conclusion. "
            "Every non-observation finding MUST cite evidence as source:// locators "
            "that appear in the material summary or deterministic analysis results. "
            "Do not invent locators.\n\n"
            f"RESEARCH SUMMARY:\n{state.get('research_summary', '')}"
        )
    runnable = runtime.llm_provider(ModelTier.LOW_COST, AnalystOutput)
    analyst_output = cast(
        AnalystOutput,
        invoke_structured(
            runnable,
            [SystemMessage(content=system), HumanMessage(content=user)],
            schema=AnalystOutput,
        ),
    )
    state_round = state.get("verifier_round", 0)
    previous_findings = (
        [loads_finding(item) for item in state.get("candidate_findings", [])]
        if state_round > 0
        else None
    )
    repaired, revised_ids = normalize_findings(
        analyst_output.findings,
        analyses=state.get("analyses", []),
        desk_context=state.get("desk_context", {}),
        report_id=runtime.spec.report_id,
        previous=previous_findings,
    )
    findings = [dumps_finding(finding) for finding in repaired]
    disposition_history = _merge_candidate_dispositions(
        state.get("candidate_dispositions", []),
        analyst_output.candidate_dispositions,
    )
    if state_round == 0:
        return {
            "candidate_findings": findings,
            "initial_candidates": findings,
            "candidate_dispositions": disposition_history,
            "verifier_feedback": "",
        }
    # Revision round: record the analyst's response in every finding's history.
    history: dict[str, list[dict]] = dict(state.get("verification_history", {}))
    for finding in repaired:
        records = list(history.get(finding.finding_id, []))
        if records:
            records[-1]["analyst_response"] = (
                analyst_output.revision_notes or "Draft revised per verifier feedback."
                if finding.finding_id in revised_ids
                else (
                    "Analyst omitted this candidate from the revision response; "
                    "the prior draft was retained for final verifier adjudication."
                )
            )
        history[finding.finding_id] = records
    return {
        "candidate_findings": findings,
        "verification_history": history,
        "candidate_dispositions": disposition_history,
    }


def _merge_candidate_dispositions(
    previous: list[dict], current: list[CandidateDispositionRecord]
) -> list[dict]:
    """Persist the latest bounded accounting response for each candidate."""

    merged: dict[str, dict] = {}
    for raw in previous:
        try:
            record = CandidateDispositionRecord.model_validate(raw)
        except ValueError:
            continue
        merged[record.candidate_id] = record.model_dump(mode="json")
    for record in current:
        merged[record.candidate_id] = record.model_dump(mode="json")
    return list(merged.values())


__all__ = ["draft_findings"]
