"""Generic bounded specialist graph: flash analyst -> pro verifier, <= N rounds.

Spec sections 14-16. Every specialist adapter is built by this factory:

    START -> prepare_scope -> inspect_material -> run_deterministic_analysis
          -> analyst (flash) -> verifier (pro)
             PASS/REJECT/UNRESOLVED -> finalize -> render_markdown -> END
             REVISE -> analyst (with feedback) -> verifier   [<= max rounds]

Deterministic hard rules enforced by the verifier node regardless of the LLM:

- every cited evidence locator is reopened from the source root; inaccessible
  evidence forces UNRESOLVED without consulting the model;
- PASS on a non-observation finding without evidence is converted to REVISE;
- the loop is bounded: final-round REVISE verdicts become UNRESOLVED.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from fastmcp.exceptions import ToolError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.overview import DataOverview, OverviewStatus
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.domain.verification import (
    VerificationRound,
    VerifierDecision,
    VerifierResult,
)
from data_agent.review.ingestion.evidence_validator import (
    EvidenceDisposition,
    EvidenceValidationResult,
    EvidenceValidator,
)
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ModelTier, ReviewLLMProvider
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.finding_policy import (
    normalize_findings,
    sanitize_finding_references,
)
from data_agent.review.orchestration.prompt_projection import (
    MAX_ANALYSIS_PROMPT_CHARS,
    MAX_REVISION_ANALYSIS_CHARS,
    bounded_analyses_json,
    bounded_revision_feedback,
    finding_analysis_support_json,
    revision_candidates_json,
)
from data_agent.review.orchestration.specialist_schemas import AnalystOutput, VerifierOutput
from data_agent.review.orchestration.specialist_state import (
    SpecialistState,
    dumps_finding,
    dumps_period,
    dumps_round,
    loads_finding,
    loads_period,
)
from data_agent.review.reporting.markdown import render_specialist_report
from data_agent.tools.review_context import ToolContext
from data_agent.tools.tabular_tools import inspect_table
from data_agent.tools.research import build_research_tools

MAX_MATERIAL_CHARS = 12_000
MAX_REVISION_CONTEXT_CHARS = 40_000
MAX_INITIAL_RESEARCH_CYCLES = 12
MAX_REVISION_RESEARCH_CYCLES = 6
MAX_INITIAL_TOOL_CALLS = 24
MAX_REVISION_TOOL_CALLS = 12
MAX_RESEARCH_CONTEXT_CHARS = 60_000


@dataclass(frozen=True)
class SpecialistSpec:
    """Configuration supplied to the generic specialist workflow."""

    domain: SpecialistDomain
    report_id: str
    domain_label: str
    policy_text: str
    analyses_runner: Callable[[ToolContext, list[str]], Sequence[BaseModel]]
    analyst_system_prompt: Callable[[str, str, str, str], str]
    verifier_system_prompt: Callable[[str], str]
    research_guidance: str = ""


def _ctx(config: RunnableConfig) -> ToolContext:
    ctx = (config or {}).get("configurable", {}).get("tool_ctx")
    if ctx is None:
        raise RuntimeError("specialist graph requires config['configurable']['tool_ctx']")
    return ctx


def _review_period(config: RunnableConfig, state: SpecialistState) -> tuple[str, str]:
    period = (config or {}).get("configurable", {}).get("review_period")
    if period is not None:
        return dumps_period(period)["start"], dumps_period(period)["end"]
    if state.get("review_period"):
        return state["review_period"]["start"], state["review_period"]["end"]
    raise RuntimeError("specialist graph requires a review period")


def build_specialist_graph(
    spec: SpecialistSpec,
    llm_provider: ReviewLLMProvider = DEFAULT_LLM_PROVIDER,
    max_verifier_rounds: int = 2,
) -> CompiledStateGraph:
    """Build the bounded analyst/verifier graph for one specialist domain."""
    if max_verifier_rounds < 1:
        raise ValueError("max_verifier_rounds must be >= 1")

    def prepare_scope(state: SpecialistState, config: RunnableConfig) -> dict:
        start, end = _review_period(config, state)
        sources = ", ".join(state.get("source_paths", []))
        return {
            "scope": (
                f"{spec.domain_label} review of {len(state.get('source_paths', []))} "
                f"source(s) ({sources}) for the period {start} to {end}."
            ),
            "verifier_round": 0,
            "loop_status": "running",
            "error": None,
            "research_summary": "",
            "research_trace": [],
            "research_round": 0,
            "research_budget_exhausted": False,
        }

    def inspect_material(state: SpecialistState, config: RunnableConfig) -> dict:
        ctx = _ctx(config)
        lines: list[str] = []
        for source in ctx.manifest.sources:
            if state.get("source_ids") and source.source_id not in state["source_ids"]:
                continue
            lines.append(
                f"SOURCE {source.source_id} | {source.path} | type={source.source_type.value} "
                f"| rows={source.row_count} | columns={source.column_names} "
                f"| date_range={source.date_range.start.isoformat() if source.date_range else None}"
                f"..{source.date_range.end.isoformat() if source.date_range else None}"
            )
        for path in state.get("source_paths", []):
            try:
                # Small files (limit registers, control logs) are shown in
                # full so the analyst can cite exact row numbers; large
                # tables get a bounded preview.
                inspection = inspect_table(ctx.source_root, path, preview_rows=3)
                if inspection["row_count"] <= 25 and inspection["row_count"] > 0:
                    inspection = inspect_table(
                        ctx.source_root, path, preview_rows=inspection["row_count"]
                    )
            except (FileNotFoundError, OSError, ValueError, ToolError):
                continue
            preview_lines = "\n".join(
                f"  row {index}: " + json.dumps(row, default=str)
                for index, row in enumerate(inspection["preview"], start=1)
            )
            lines.append(
                f"PREVIEW {path} (sheet={inspection['sheet']}, "
                f"rows={inspection['row_count']}):\n{preview_lines}"
            )
        summary = "\n".join(lines)[:MAX_MATERIAL_CHARS]
        return {"material_summary": summary}

    def run_deterministic_analysis(state: SpecialistState, config: RunnableConfig) -> dict:
        ctx = _ctx(config)
        analyses = spec.analyses_runner(ctx, list(state.get("source_paths", [])))
        return {"analyses": [analysis.model_dump(mode="json") for analysis in analyses]}

    def react_research(state: SpecialistState, config: RunnableConfig) -> dict:
        """Let the low-cost analyst investigate assigned sources with bounded tools."""
        ctx = _ctx(config)
        revision = state.get("verifier_round", 0) > 0
        max_cycles = MAX_REVISION_RESEARCH_CYCLES if revision else MAX_INITIAL_RESEARCH_CYCLES
        max_calls = MAX_REVISION_TOOL_CALLS if revision else MAX_INITIAL_TOOL_CALLS
        trace: list[dict[str, Any]] = []
        tools = build_research_tools(
            ctx,
            list(state.get("source_paths", [])),
            trace,
            max_calls=max_calls,
            research_round=int(state.get("verifier_round", 0)),
        )
        analyses = bounded_analyses_json(
            list(state.get("analyses", [])), max_chars=MAX_ANALYSIS_PROMPT_CHARS
        )
        research_context = (
            f"SCOPE:\n{state.get('scope', '')}\n\n"
            f"MATERIAL SUMMARY:\n{state.get('material_summary', '')}\n\n"
            f"DETERMINISTIC ANALYSIS:\n{analyses}\n\n"
            f"VERIFIER FEEDBACK:\n{state.get('verifier_feedback', '') or '(none)'}"
        )[:MAX_RESEARCH_CONTEXT_CHARS]
        prompt = (
            f"You are the {spec.domain_label} research analyst. Python has already "
            "computed the deterministic review. Use the assigned-source tools to "
            "inspect material leads, reopen relevant evidence, test alternatives, and "
            "review every tool result before concluding. Never access an unassigned "
            "source and never invent a source:// locator. End with a concise research "
            "summary describing support, counter-evidence, limitations, and locators.\n\n"
            f"DOMAIN GUIDANCE:\n{spec.research_guidance}"
        )
        try:
            model = llm_provider(ModelTier.LOW_COST)
        except AssertionError:
            # Legacy deterministic fakes may intentionally implement only the
            # structured analyst/verifier calls.
            return {
                "research_summary": research_context,
                "research_trace": [],
                "research_round": state.get("research_round", 0) + 1,
                "research_budget_exhausted": False,
            }
        if not hasattr(model, "bind_tools"):
            # Deterministic/fake providers used by graph tests can skip the tool loop;
            # production capability probes require SocGenAI tool binding.
            return {
                "research_summary": research_context,
                "research_trace": [],
                "research_round": state.get("research_round", 0) + 1,
                "research_budget_exhausted": False,
            }
        agent = create_react_agent(model, tools, prompt=prompt, name=f"{spec.domain.value}_research")
        exhausted = False
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": research_context}]},
                config={
                    "recursion_limit": max_cycles * 2 + 2,
                    "callbacks": (config or {}).get("callbacks"),
                    "tags": (config or {}).get("tags"),
                },
            )
            messages = result.get("messages", [])
            summary = str(getattr(messages[-1], "content", "")) if messages else ""
        except Exception as exc:  # bounded exhaustion/provider failure is disclosed
            exhausted = True
            summary = (
                f"Research stopped at its bounded execution limit: {type(exc).__name__}: {exc}. "
                "Use deterministic analysis and completed tool evidence; disclose remaining gaps."
            )
        if len(trace) >= max_calls:
            exhausted = True
        return {
            "research_summary": summary[:MAX_RESEARCH_CONTEXT_CHARS],
            "research_trace": trace,
            "research_round": state.get("research_round", 0) + 1,
            "research_budget_exhausted": exhausted,
        }

    def draft_findings(state: SpecialistState, config: RunnableConfig) -> dict:
        desk_json = json.dumps(state.get("desk_context", {}), indent=2)
        feedback = state.get("verifier_feedback", "")
        analyses_json = bounded_analyses_json(
            list(state.get("analyses", [])),
            max_chars=(MAX_REVISION_ANALYSIS_CHARS if feedback else MAX_ANALYSIS_PROMPT_CHARS),
        )
        system = spec.analyst_system_prompt(
            spec.domain_label, desk_json, state.get("material_summary", ""), analyses_json
        )
        if feedback:
            previous = revision_candidates_json(list(state.get("candidate_findings", [])))
            fixed_context_chars = len(previous) + 400
            bounded_feedback = bounded_revision_feedback(
                feedback,
                max_chars=max(MAX_REVISION_CONTEXT_CHARS - fixed_context_chars, 1_000),
            )
            user = (
                "The verifier rejected your previous draft. Revise the findings to "
                f"address every point, keeping their finding IDs and evidence locators.\n\n"
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
        runnable = llm_provider(ModelTier.LOW_COST, AnalystOutput)
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
            report_id=spec.report_id,
            previous=previous_findings,
        )
        findings = [dumps_finding(f) for f in repaired]
        if state_round == 0:
            return {
                "candidate_findings": findings,
                "initial_candidates": findings,
                "verifier_feedback": "",
            }
        # Revision round: record the analyst's response in the history of every finding.
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
        }

    def _reopen_evidence(
        finding: Finding, validator: EvidenceValidator
    ) -> tuple[str, list[EvidenceValidationResult]]:
        """Reopen all cited locators; returns (appendix, failures)."""
        parts: list[str] = []
        failures: list[EvidenceValidationResult] = []
        for label, references in (
            ("EVIDENCE", finding.evidence),
            ("COUNTER EVIDENCE", finding.counter_evidence),
        ):
            validation = validator.validate_references(references)
            for result in validation.results:
                if result.valid:
                    parts.append(f"{label} LOCATOR {result.locator}\n{result.snippet}")
                else:
                    failures.append(result)
        return "\n\n".join(parts), failures

    def verifier(state: SpecialistState, config: RunnableConfig) -> dict:
        ctx = _ctx(config)
        evidence_validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
        round_number = state.get("verifier_round", 0) + 1
        candidates = [loads_finding(d) for d in state.get("candidate_findings", [])]

        results: dict[str, VerifierResult] = {}
        for finding in candidates:
            appendix, failures = _reopen_evidence(finding, evidence_validator)
            fatal_failures = [
                failure for failure in failures if failure.disposition is EvidenceDisposition.FATAL
            ]
            if fatal_failures:
                message = "; ".join(
                    f"{failure.locator}: {failure.reason}" for failure in fatal_failures
                )
                raise RuntimeError(f"fatal evidence integrity failure: {message}")
            if failures:
                unresolved_failures = [
                    failure
                    for failure in failures
                    if failure.disposition is EvidenceDisposition.UNRESOLVED
                ]
                results[finding.finding_id] = VerifierResult(
                    finding_id=finding.finding_id,
                    decision=(
                        VerifierDecision.UNRESOLVED
                        if unresolved_failures
                        else VerifierDecision.REVISE
                    ),
                    checks=[f"locator reopened: FAILED ({len(failures)})"],
                    feedback="Evidence locator validation failed:\n"
                    + "\n".join(f"{failure.locator}: {failure.reason}" for failure in failures),
                    evidence_inaccessible=bool(unresolved_failures),
                )
                continue
            system = spec.verifier_system_prompt(spec.policy_text)
            deterministic_support = finding_analysis_support_json(
                finding, state.get("analyses", [])
            )
            user = (
                f"Verification round: {round_number}\n\n"
                f"FINDING:\n{json.dumps(dumps_finding(finding), indent=2, default=str)}\n\n"
                f"REOPENED EVIDENCE:\n{appendix or '(observation: no evidence cited)'}\n\n"
                "MATCHED DETERMINISTIC SUPPORT:\n"
                f"{deterministic_support}\n\n"
                "Python computed this support from the controlled source population. "
                "Use it to verify aggregate calculations, while treating the reopened "
                "source locators above as the required citation basis. An empty array "
                "means no locator-matched deterministic candidate was found.\n\n"
                "Return your structured verdict."
            )
            runnable = llm_provider(ModelTier.HIGH_COST, VerifierOutput)
            verifier_output = cast(
                VerifierOutput,
                invoke_structured(
                    runnable,
                    [SystemMessage(content=system), HumanMessage(content=user)],
                    schema=VerifierOutput,
                ),
            )
            results[finding.finding_id] = VerifierResult(**verifier_output.model_dump())

        # Deterministic guards over every verdict (spec sections 7, 15, 41).
        for finding in candidates:
            result = results[finding.finding_id]
            if result.decision is VerifierDecision.PASS:
                if result.evidence_inaccessible:
                    result.decision = VerifierDecision.UNRESOLVED
                    result.feedback = "Evidence inaccessible; cannot pass."
                try:
                    finding.assert_evidence_policy()
                except ValueError as exc:
                    result.decision = VerifierDecision.REVISE
                    result.feedback = f"{exc}. Add valid evidence locators and resubmit."

        pending_revise = [
            finding
            for finding in candidates
            if results[finding.finding_id].decision is VerifierDecision.REVISE
        ]
        final_round = round_number >= max_verifier_rounds

        history: dict[str, list[dict]] = dict(state.get("verification_history", {}))
        updated_findings: list[dict] = []

        # Seed the terminal lists with prior-round decisions, EXCLUDING the
        # candidates being re-verified this round (a finding may move from
        # UNRESOLVED to PASS across rounds and must not appear twice).
        current_ids = {finding.finding_id for finding in candidates}
        rejected: list[dict] = [
            entry
            for entry in state.get("rejected_findings", [])
            if entry["finding_id"] not in current_ids
        ]
        unresolved: list[dict] = [
            entry
            for entry in state.get("unresolved_findings", [])
            if entry["finding_id"] not in current_ids
        ]
        verified: list[dict] = [
            entry
            for entry in state.get("verified_findings", [])
            if entry["finding_id"] not in current_ids
        ]

        for finding in candidates:
            result = results[finding.finding_id]
            decision = result.decision
            if decision is VerifierDecision.REVISE and final_round:
                decision = VerifierDecision.UNRESOLVED
                result.feedback = (
                    "Verifier rounds exhausted; marked UNRESOLVED. " + result.feedback
                ).strip()
            record = VerificationRound(
                round_number=round_number,
                decision=decision,
                questions=result.questions,
                checks=[*result.checks, f"evidence reopen: {len(finding.evidence)} locator(s)"],
                feedback=result.feedback,
            )
            history[finding.finding_id] = [
                *history.get(finding.finding_id, []),
                dumps_round(record),
            ]

            if decision is VerifierDecision.PASS:
                finding.verifier_status = VerificationStatus.PASSED
                updated_findings.append(dumps_finding(finding))
                verified.append(dumps_finding(finding))
            elif decision is VerifierDecision.REJECT:
                finding.verifier_status = VerificationStatus.REJECTED
                rejected.append(dumps_finding(finding))
            elif decision is VerifierDecision.UNRESOLVED:
                finding.verifier_status = VerificationStatus.UNRESOLVED
                updated_findings.append(dumps_finding(finding))
                unresolved.append(dumps_finding(finding))
            else:  # REVISE on a non-final round: stays pending for the analyst
                finding.verifier_status = VerificationStatus.PENDING
                updated_findings.append(dumps_finding(finding))

        if pending_revise and not final_round:
            feedback = "\n\n---\n\n".join(
                f"[{f.finding_id}] {results[f.finding_id].feedback}" for f in pending_revise
            )
            return {
                "candidate_findings": updated_findings,
                "verification_history": history,
                "verifier_round": round_number,
                "verifier_feedback": feedback,
                "loop_status": "running",
                "verified_findings": verified,
                "rejected_findings": rejected,
                "unresolved_findings": unresolved,
            }
        return {
            "candidate_findings": updated_findings,
            "verification_history": history,
            "verifier_round": round_number,
            "verifier_feedback": "",
            "loop_status": "complete",
            "verified_findings": verified,
            "rejected_findings": rejected,
            "unresolved_findings": unresolved,
        }

    def route(state: SpecialistState) -> str:
        return "finalize" if state.get("loop_status") == "complete" else "react_research"

    def finalize(state: SpecialistState, config: RunnableConfig) -> dict:
        ctx = _ctx(config)
        period = loads_period(state["review_period"])
        verified = [loads_finding(d) for d in state.get("verified_findings", [])]
        unresolved_findings = [loads_finding(d) for d in state.get("unresolved_findings", [])]
        rejected = [loads_finding(d) for d in state.get("rejected_findings", [])]
        evidence_validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
        sanitized_verified: list[Finding] = []
        for finding in verified:
            sanitized, failures = sanitize_finding_references(finding, evidence_validator)
            if failures:
                details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in failures)
                raise RuntimeError(
                    f"verified finding {finding.finding_id} retained invalid evidence: {details}"
                )
            sanitized_verified.append(sanitized)
        verified = sanitized_verified
        unresolved_findings = [
            sanitize_finding_references(finding, evidence_validator)[0]
            for finding in unresolved_findings
        ]
        history = {
            finding_id: [VerificationRound.model_validate(r) for r in rounds]
            for finding_id, rounds in state.get("verification_history", {}).items()
        }

        all_findings = [*verified, *unresolved_findings]
        top = sorted(all_findings, key=lambda f: SEVERITY_ORDER[f.severity], reverse=True)[:3]
        top_text = (
            "; ".join(f"{f.finding_id} ({f.severity.value}): {f.title}" for f in top) or "none"
        )
        unresolved_items = [
            f"{f.finding_id} — {f.title}: "
            + next(
                (r.feedback for r in reversed(history.get(f.finding_id, []))),
                "no verifier feedback",
            )
            for f in unresolved_findings
        ]
        conclusion = (
            f"{spec.domain_label} review completed: {len(verified)} finding(s) verified, "
            f"{len(rejected)} rejected, {len(unresolved_findings)} unresolved. "
            f"Top findings: {top_text}."
        )
        data_overviews: list[DataOverview] = []
        for raw_analysis in state.get("analyses", []):
            analysis = AnalysisResult.model_validate(raw_analysis)
            for overview in analysis.overviews:
                validation = evidence_validator.validate_references(overview.evidence)
                overview_failures = [
                    f"{failure.locator}: {failure.reason}" for failure in validation.failures
                ]
                fatal_failures = [
                    failure
                    for failure in validation.failures
                    if failure.disposition is EvidenceDisposition.FATAL
                ]
                if fatal_failures:
                    details = "; ".join(
                        f"{failure.locator}: {failure.reason}" for failure in fatal_failures
                    )
                    raise RuntimeError(
                        f"fatal evidence integrity failure in data overview "
                        f"{overview.overview_id}: {details}"
                    )
                if overview_failures:
                    overview = overview.model_copy(
                        update={
                            "status": OverviewStatus.UNAVAILABLE,
                            "visual": None,
                            "metrics": [],
                            "limitations": [
                                *overview.limitations,
                                (
                                    "Overview suppressed because report evidence could "
                                    "not be reopened: "
                                )
                                + "; ".join(overview_failures),
                            ],
                        }
                    )
                data_overviews.append(overview)
        report = SpecialistReport(
            domain=spec.domain,
            report_id=spec.report_id,
            title=f"{spec.domain_label} Review",
            review_period=period,
            generated_at=datetime.now(UTC),
            scope=state.get("scope", ""),
            sources_reviewed=list(state.get("source_ids", [])),
            analysis_performed=[a.get("name", "?") for a in state.get("analyses", [])],
            data_overviews=data_overviews,
            findings=all_findings,
            unresolved_items=unresolved_items,
            overall_conclusion=conclusion,
            verification_history=history,
        )
        return {
            "report": report.model_dump(mode="json"),
            "unresolved_findings": [dumps_finding(f) for f in unresolved_findings],
        }

    def render_markdown(state: SpecialistState) -> dict:
        report_data = state.get("report")
        if not report_data:
            return {"error": "finalize produced no report"}
        report = SpecialistReport.model_validate(report_data)
        return {"markdown": render_specialist_report(report)}

    graph = StateGraph(SpecialistState)
    graph.add_node("prepare_scope", prepare_scope)
    graph.add_node("inspect_material", inspect_material)
    graph.add_node("run_deterministic_analysis", run_deterministic_analysis)
    graph.add_node("react_research", react_research)
    graph.add_node("draft_findings", draft_findings)
    graph.add_node("verifier", verifier)
    graph.add_node("finalize", finalize)
    graph.add_node("render_markdown", render_markdown)

    graph.add_edge(START, "prepare_scope")
    graph.add_edge("prepare_scope", "inspect_material")
    graph.add_edge("inspect_material", "run_deterministic_analysis")
    graph.add_edge("run_deterministic_analysis", "react_research")
    graph.add_edge("react_research", "draft_findings")
    graph.add_edge("draft_findings", "verifier")
    graph.add_conditional_edges(
        "verifier", route, {"react_research": "react_research", "finalize": "finalize"}
    )
    graph.add_edge("finalize", "render_markdown")
    graph.add_edge("render_markdown", END)
    return graph.compile()
