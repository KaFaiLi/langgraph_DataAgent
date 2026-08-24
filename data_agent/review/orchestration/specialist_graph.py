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
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol, cast

from fastmcp.exceptions import ToolError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding, VerificationStatus
from data_agent.review.domain.overview import DataOverview, OverviewStatus
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.domain.source import DateRange
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
from data_agent.review.llm import ModelTier, create_llm, create_structured_llm
from data_agent.review.llm.structured import invoke_structured
from data_agent.review.orchestration.specialist_schemas import (
    MAX_ANALYST_FINDINGS,
    AnalystOutput,
    VerifierOutput,
)
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
MAX_ANALYSIS_PROMPT_CHARS = 60_000
MAX_REVISION_ANALYSIS_CHARS = 25_000
MAX_REVISION_CONTEXT_CHARS = 40_000
MAX_VERIFIER_SUPPORT_CHARS = 18_000
MAX_CANDIDATE_FINDINGS = MAX_ANALYST_FINDINGS
MAX_PERSISTED_FINDING_EVIDENCE = 8
MAX_INITIAL_RESEARCH_CYCLES = 12
MAX_REVISION_RESEARCH_CYCLES = 6
MAX_INITIAL_TOOL_CALLS = 24
MAX_REVISION_TOOL_CALLS = 12
MAX_RESEARCH_CONTEXT_CHARS = 60_000


class LLMProvider(Protocol):
    """Injected model factory: (tier, schema?) -> Runnable.

    Production uses the configured cost-tier review provider; tests inject
    fakes so no external call is ever made.
    """

    def __call__(
        self, tier: ModelTier, schema: type[BaseModel] | None = None
    ) -> Runnable[Any, Any]: ...


class DefaultLLMProvider:
    """Production adapter over the configured review-model factory."""

    def __call__(
        self, tier: ModelTier, schema: type[BaseModel] | None = None
    ) -> Runnable[Any, Any]:
        if schema is None:
            return create_llm(tier)
        return create_structured_llm(tier, schema)


DEFAULT_LLM_PROVIDER: LLMProvider = DefaultLLMProvider()


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


def _repair_finding(finding: Finding) -> Finding:
    """Deterministic repairs for live-model output quirks.

    - inverted date ranges are swapped;
    - confidence is clamped to [0, 1].
    """
    if finding.period is not None and finding.period.start > finding.period.end:
        finding.period = DateRange(start=finding.period.end, end=finding.period.start)
    finding.confidence = min(1.0, max(0.0, finding.confidence))
    return finding


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Keep the last revision of each finding ID (live models can duplicate)."""
    seen: dict[str, Finding] = {}
    order: list[str] = []
    for finding in findings:
        if finding.finding_id not in seen:
            order.append(finding.finding_id)
        seen[finding.finding_id] = finding
    return [seen[finding_id] for finding_id in order]


def _compact_prompt_value(value: object, *, depth: int = 0) -> object:
    """Bound nested deterministic output while retaining interpretable evidence fields."""
    if depth >= 5:
        return "[nested value omitted]"
    if isinstance(value, str):
        return value if len(value) <= 2_000 else value[:1_997] + "..."
    if isinstance(value, list):
        compacted = [_compact_prompt_value(item, depth=depth + 1) for item in value[:20]]
        if len(value) > 20:
            compacted.append(f"[{len(value) - 20} item(s) omitted]")
        return compacted
    if isinstance(value, dict):
        return {
            str(key): _compact_prompt_value(item, depth=depth + 1)
            for key, item in list(value.items())[:50]
        }
    return value


def _bounded_analyses_json(
    analyses: list[dict[str, object]], *, max_chars: int = MAX_ANALYSIS_PROMPT_CHARS
) -> str:
    """Create a fair, deterministic LLM projection of potentially large analyses.

    Flag candidates are included round-robin across analyses before bulky tables so one
    source family cannot consume the entire context window. Full results remain in graph
    state and continue to own report overviews; this only bounds the analyst prompt.
    """
    payload: list[dict[str, object]] = []
    for analysis in analyses:
        flags = analysis.get("flag_candidates", [])
        tables = analysis.get("tables", [])
        payload.append(
            {
                "name": analysis.get("name", "?"),
                "summary": _compact_prompt_value(analysis.get("summary", "")),
                "flag_candidate_count": len(flags) if isinstance(flags, list) else 0,
                "table_count": len(tables) if isinstance(tables, list) else 0,
                "flag_candidates": [],
                "tables": [],
            }
        )

    def add_round_robin(field: str) -> bool:
        positions = [0] * len(analyses)
        while True:
            progressed = False
            for index, analysis in enumerate(analyses):
                values = analysis.get(field, [])
                if not isinstance(values, list) or positions[index] >= len(values):
                    continue
                progressed = True
                candidate = _compact_prompt_value(values[positions[index]])
                target = payload[index][field]
                if not isinstance(target, list):
                    raise TypeError(f"prompt projection field {field!r} must be a list")
                target.append(candidate)
                encoded = json.dumps(payload, indent=2, default=str)
                if len(encoded) > max_chars:
                    target.pop()
                    return False
                positions[index] += 1
            if not progressed:
                return True

    flags_complete = add_round_robin("flag_candidates")
    if flags_complete:
        add_round_robin("tables")
    return json.dumps(payload, indent=2, default=str)


def _source_locators(value: object) -> set[str]:
    """Collect source locators from a nested deterministic-analysis value."""
    if isinstance(value, str):
        return {value} if value.startswith("source://") else set()
    if isinstance(value, list):
        return {locator for item in value for locator in _source_locators(item)}
    if isinstance(value, dict):
        return {locator for item in value.values() for locator in _source_locators(item)}
    return set()


def _finding_analysis_support_json(
    finding: Finding,
    analyses: list[dict[str, object]],
    *,
    max_chars: int = MAX_VERIFIER_SUPPORT_CHARS,
) -> str:
    """Project Python-computed candidates that share a finding's reopened evidence.

    The verifier still receives and adjudicates the immutable source snippets. This
    projection supplies the deterministic population calculation behind aggregate
    claims, instead of asking the model to reconstruct it from representative rows.
    Unrelated candidates are excluded to keep each independent verification bounded.
    """
    finding_locators = {
        reference.locator for reference in [*finding.evidence, *finding.counter_evidence]
    }
    payload: list[dict[str, object]] = []
    for analysis in analyses:
        flags = analysis.get("flag_candidates", [])
        if not isinstance(flags, list):
            continue
        matching_flags = [
            _compact_prompt_value(flag)
            for flag in flags
            if finding_locators.intersection(_source_locators(flag))
        ]
        if not matching_flags:
            continue
        payload.append(
            {
                "name": analysis.get("name", "?"),
                "summary": _compact_prompt_value(analysis.get("summary", "")),
                "matching_flag_candidates": matching_flags,
            }
        )

    encoded = json.dumps(payload, indent=2, default=str)
    if len(encoded) <= max_chars:
        return encoded

    # Preserve every matching analysis and allocate flag detail fairly when support is
    # unusually large. The same bounded projection rules used by the analyst apply.
    bounded = [
        {
            "name": item["name"],
            "summary": _compact_prompt_value(item["summary"]),
            "matching_flag_candidates": [],
        }
        for item in payload
    ]
    positions = [0] * len(payload)
    while True:
        progressed = False
        for index, item in enumerate(payload):
            flags = item["matching_flag_candidates"]
            if not isinstance(flags, list) or positions[index] >= len(flags):
                continue
            progressed = True
            target = bounded[index]["matching_flag_candidates"]
            if not isinstance(target, list):
                raise TypeError("matching_flag_candidates must be a list")
            target.append(flags[positions[index]])
            candidate = json.dumps(bounded, indent=2, default=str)
            if len(candidate) > max_chars:
                target.pop()
                return json.dumps(bounded, indent=2, default=str)
            positions[index] += 1
        if not progressed:
            return json.dumps(bounded, indent=2, default=str)


def _revision_candidates_json(candidates: list[dict[str, Any]]) -> str:
    """Compact every prior candidate while preserving IDs and evidence locators."""
    payload = [
        {
            "finding_id": candidate.get("finding_id"),
            "title": str(candidate.get("title", ""))[:300],
            "category": candidate.get("category"),
            "severity": candidate.get("severity"),
            "confidence": candidate.get("confidence"),
            "claim": str(candidate.get("claim", ""))[:1_200],
            "period": candidate.get("period"),
            "evidence": _compact_prompt_value(candidate.get("evidence", [])),
            "alternative_explanations": _compact_prompt_value(
                candidate.get("alternative_explanations", [])
            ),
            "counter_evidence": _compact_prompt_value(candidate.get("counter_evidence", [])),
            "recommendation": str(candidate.get("recommendation") or "")[:500],
        }
        for candidate in candidates
    ]
    encoded = json.dumps(payload, separators=(",", ":"), default=str)
    if len(encoded) <= 28_000:
        return encoded
    minimal = [
        {
            "finding_id": candidate.get("finding_id"),
            "title": str(candidate.get("title", ""))[:200],
            "claim": str(candidate.get("claim", ""))[:600],
            "period": candidate.get("period"),
            "evidence_locators": [
                reference.get("locator")
                for reference in candidate.get("evidence", [])
                if isinstance(reference, dict)
            ],
        }
        for candidate in candidates
    ]
    return json.dumps(minimal, separators=(",", ":"), default=str)


def _bounded_revision_feedback(feedback: str, *, max_chars: int) -> str:
    """Retain a fair slice of every per-finding verifier response."""
    if len(feedback) <= max_chars:
        return feedback
    sections = feedback.split("\n\n---\n\n")
    per_section = max(400, max_chars // max(len(sections), 1))
    return "\n\n---\n\n".join(section[:per_section] for section in sections)[:max_chars]


def _limit_candidate_findings(findings: list[Finding]) -> list[Finding]:
    """Keep analyst output bounded in its stated priority order."""
    return findings[:MAX_CANDIDATE_FINDINGS]


def _sanitize_finding_references(
    finding: Finding, validator: EvidenceValidator
) -> tuple[Finding, list[EvidenceValidationResult]]:
    """Remove non-reopenable citations from persisted findings.

    The verifier history retains the failure reason. Fatal integrity failures
    still abort the run; only unresolved region/citation defects are removed
    from fields that promise reopenable ``EvidenceReference`` values.
    """
    updates: dict[str, object] = {}
    failures: list[EvidenceValidationResult] = []
    for field_name, references in (
        ("evidence", finding.evidence),
        ("counter_evidence", finding.counter_evidence),
    ):
        validation = validator.validate_references(references)
        fatal = [
            failure
            for failure in validation.failures
            if failure.disposition is EvidenceDisposition.FATAL
        ]
        if fatal:
            details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in fatal)
            raise RuntimeError(f"fatal evidence integrity failure: {details}")
        valid_locators = {result.locator for result in validation.results if result.valid}
        updates[field_name] = [
            reference for reference in references if reference.locator in valid_locators
        ]
        failures.extend(validation.failures)
    return finding.model_copy(update=updates), failures


def _infer_finding_period(finding: Finding, analyses: list[dict[str, Any]]) -> Finding:
    """Fill a missing period from deterministic flags sharing cited locators."""
    if finding.period is not None:
        return finding
    cited = {reference.locator for reference in finding.evidence}
    if not cited:
        return finding
    dates: list[date] = []
    for analysis in analyses:
        for candidate in analysis.get("flag_candidates", []):
            if not isinstance(candidate, dict):
                continue
            locator_values: list[object] = [candidate.get("locator")]
            raw_locators = candidate.get("locators", [])
            if isinstance(raw_locators, list):
                locator_values.extend(raw_locators)
            candidate_locators = {value for value in locator_values if isinstance(value, str)}
            if not cited.intersection(candidate_locators):
                continue
            for key in (
                "event_date",
                "value_date",
                "effective_date",
                "date",
                "first_date",
                "last_date",
            ):
                value = candidate.get(key)
                if not isinstance(value, str):
                    continue
                try:
                    dates.append(date.fromisoformat(value[:10]))
                except ValueError:
                    continue
    if not dates:
        return finding
    return finding.model_copy(update={"period": DateRange(start=min(dates), end=max(dates))})


def _apply_deterministic_severity_floor(
    finding: Finding, analyses: list[dict[str, object]]
) -> Finding:
    """Apply policy-owned severity floors from exact locator-matched Python flags."""
    finding_locators = {reference.locator for reference in finding.evidence}
    finding_text = " ".join(
        [finding.title, finding.category, finding.claim, *finding.analysis_performed]
    ).lower()
    floors: list[Severity] = []
    measured_observation = False
    for analysis in analyses:
        candidates = analysis.get("flag_candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if not finding_locators.intersection(_source_locators(candidate)):
                continue
            match_terms = candidate.get("severity_match_terms", [])
            if isinstance(match_terms, list) and match_terms:
                matched_terms = sum(
                    1
                    for term in match_terms
                    if isinstance(term, str) and term.lower() in finding_text
                )
                if matched_terms < min(2, len(match_terms)):
                    continue
            raw_floor = candidate.get("severity_floor")
            try:
                floors.append(Severity(str(raw_floor)))
            except ValueError:
                continue
            if candidate.get("measured_observation") is True:
                measured_observation = True
    updates: dict[str, object] = {}
    if floors:
        floor = max(floors, key=lambda severity: SEVERITY_ORDER[severity])
        if SEVERITY_ORDER[finding.severity] < SEVERITY_ORDER[floor]:
            updates["severity"] = floor
    if measured_observation:
        updates["is_observation"] = True
    if not updates:
        return finding
    return finding.model_copy(update=updates)


def _add_deterministic_candidate_evidence(
    finding: Finding, analyses: list[dict[str, object]]
) -> Finding:
    """Persist the complete bounded locator set for a matched measured population."""

    finding_locators = {reference.locator for reference in finding.evidence}
    finding_text = " ".join(
        [finding.title, finding.category, finding.claim, *finding.analysis_performed]
    ).lower()
    evidence = list(finding.evidence)
    seen = set(finding_locators)
    for analysis in analyses:
        candidates = analysis.get("flag_candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("measured_observation") is not True:
                continue
            candidate_locators = _source_locators(candidate)
            if not finding_locators.intersection(candidate_locators):
                continue
            match_terms = candidate.get("severity_match_terms", [])
            if isinstance(match_terms, list) and match_terms:
                matched_terms = sum(
                    1
                    for term in match_terms
                    if isinstance(term, str) and term.lower() in finding_text
                )
                if matched_terms < min(2, len(match_terms)):
                    continue
            for locator in sorted(candidate_locators):
                if locator in seen:
                    continue
                seen.add(locator)
                evidence.append(EvidenceReference(locator=locator))
                if len(evidence) >= MAX_PERSISTED_FINDING_EVIDENCE:
                    return finding.model_copy(update={"evidence": evidence})
    return finding.model_copy(update={"evidence": evidence})


_CONTEXT_MATCH_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "for",
        "from",
        "reported",
        "review",
        "source",
        "that",
        "the",
        "this",
        "with",
    }
)


def _add_relevant_context_evidence(finding: Finding, desk_context: dict[str, object]) -> Finding:
    """Attach exact source-backed facts needed by a finding's unit or basis claims."""

    def terms(value: object) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", str(value).lower())
            if len(token) >= 3 and token not in _CONTEXT_MATCH_STOPWORDS
        }

    finding_terms = terms(
        " ".join([finding.title, finding.category, finding.claim, *finding.analysis_performed])
    )
    evidence = list(finding.evidence)
    seen = {reference.locator for reference in evidence}
    facts = desk_context.get("source_backed_facts", [])
    if not isinstance(facts, list):
        return finding
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        if len(finding_terms & terms(fact.get("statement", ""))) < 2:
            continue
        references = fact.get("evidence", [])
        if not isinstance(references, list):
            continue
        for raw_reference in references:
            try:
                reference = EvidenceReference.model_validate(raw_reference)
            except ValueError:
                continue
            if reference.locator in seen:
                continue
            seen.add(reference.locator)
            evidence.append(reference)
            if len(evidence) >= MAX_PERSISTED_FINDING_EVIDENCE:
                return finding.model_copy(update={"evidence": evidence})
    return finding.model_copy(update={"evidence": evidence})


def _merge_revision_findings(
    previous: list[Finding], revised: list[Finding]
) -> tuple[list[Finding], set[str]]:
    """Replace revised IDs while retaining omitted candidates for adjudication."""
    revised_by_id = {finding.finding_id: finding for finding in revised}
    revised_ids = set(revised_by_id)
    merged = [revised_by_id.get(finding.finding_id, finding) for finding in previous]
    previous_ids = {finding.finding_id for finding in previous}
    merged.extend(finding for finding in revised if finding.finding_id not in previous_ids)
    return _limit_candidate_findings(merged), revised_ids


def _namespace_finding_ids(findings: list[Finding], report_id: str) -> list[Finding]:
    """Make specialist finding IDs globally unambiguous across the parent graph."""
    prefix = f"{report_id}-"
    for finding in findings:
        if not finding.finding_id.startswith(prefix):
            finding.finding_id = prefix + finding.finding_id
    return findings


def build_specialist_graph(
    spec: SpecialistSpec,
    llm_provider: LLMProvider = DEFAULT_LLM_PROVIDER,
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
        analyses = _bounded_analyses_json(
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
        analyses_json = _bounded_analyses_json(
            list(state.get("analyses", [])),
            max_chars=(MAX_REVISION_ANALYSIS_CHARS if feedback else MAX_ANALYSIS_PROMPT_CHARS),
        )
        system = spec.analyst_system_prompt(
            spec.domain_label, desk_json, state.get("material_summary", ""), analyses_json
        )
        if feedback:
            previous = _revision_candidates_json(list(state.get("candidate_findings", [])))
            fixed_context_chars = len(previous) + 400
            bounded_feedback = _bounded_revision_feedback(
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
        repaired = _limit_candidate_findings(
            _dedupe_findings(
                _namespace_finding_ids(
                    [
                        _apply_deterministic_severity_floor(
                            _add_relevant_context_evidence(
                                _infer_finding_period(
                                    _add_deterministic_candidate_evidence(
                                        _repair_finding(finding),
                                        state.get("analyses", []),
                                    ),
                                    state.get("analyses", []),
                                ),
                                state.get("desk_context", {}),
                            ),
                            state.get("analyses", []),
                        )
                        for finding in analyst_output.findings
                    ],
                    spec.report_id,
                )
            )
        )
        revised_ids = {finding.finding_id for finding in repaired}
        state_round = state.get("verifier_round", 0)
        if state_round > 0:
            previous_findings = [
                loads_finding(item) for item in state.get("candidate_findings", [])
            ]
            repaired, revised_ids = _merge_revision_findings(previous_findings, repaired)
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
            deterministic_support = _finding_analysis_support_json(
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
            sanitized, failures = _sanitize_finding_references(finding, evidence_validator)
            if failures:
                details = "; ".join(f"{failure.locator}: {failure.reason}" for failure in failures)
                raise RuntimeError(
                    f"verified finding {finding.finding_id} retained invalid evidence: {details}"
                )
            sanitized_verified.append(sanitized)
        verified = sanitized_verified
        unresolved_findings = [
            _sanitize_finding_references(finding, evidence_validator)[0]
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
