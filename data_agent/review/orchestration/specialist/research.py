"""Bounded low-cost research node for one specialist."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.llm import AgentCapabilityError, ModelTier, run_bounded_agent
from data_agent.review.orchestration.prompt_projection import (
    MAX_ANALYSIS_PROMPT_CHARS,
    bounded_analyses_json,
)
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.scope import context_from_config
from data_agent.review.orchestration.specialist.state import SpecialistState
from data_agent.tools.research import build_research_tools


def react_research(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict:
    """Let the low-cost analyst investigate assigned sources with bounded tools."""
    ctx = context_from_config(config)
    revision = state.get("verifier_round", 0) > 0
    rescue = state.get("research_mode") == "omission_rescue"
    output_mode = "omission_rescue" if rescue else ("revision" if revision else "initial")
    max_cycles = (
        runtime.max_revision_research_cycles if revision else runtime.max_initial_research_cycles
    )
    max_calls = runtime.max_revision_tool_calls if revision else runtime.max_initial_tool_calls
    trace: list[dict[str, Any]] = []
    previous_trace = list(state.get("research_trace", []))
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
    )[: runtime.max_research_context_chars]
    prompt = (
        f"You are the {runtime.spec.domain_label} research analyst. Python has already "
        "computed the deterministic review. Use the assigned-source tools to "
        "inspect material leads, reopen relevant evidence, test alternatives, and "
        "review every tool result before concluding. Never access an unassigned "
        "source and never invent a source:// locator. End with a concise research "
        "summary describing support, counter-evidence, limitations, and locators.\n\n"
        f"DOMAIN GUIDANCE:\n{runtime.spec.research_guidance}"
    )
    try:
        model = runtime.llm_provider(ModelTier.LOW_COST)
    except AssertionError:
        # Legacy deterministic fakes may intentionally implement only the
        # structured analyst/verifier calls.
        return {
            "research_summary": research_context,
            "research_trace": previous_trace,
            "research_round": state.get("research_round", 0) + 1,
            "research_budget_exhausted": False,
            "research_mode": output_mode,
        }
    if not hasattr(model, "bind_tools"):
        # Deterministic/fake providers can skip the tool loop; production
        # capability probes require a tool-bindable chat model.
        return {
            "research_summary": research_context,
            "research_trace": previous_trace,
            "research_round": state.get("research_round", 0) + 1,
            "research_budget_exhausted": False,
            "research_mode": output_mode,
        }
    exhausted = False
    try:
        result = run_bounded_agent(
            model,
            tools=tools,
            system_prompt=prompt,
            user_prompt=research_context,
            max_cycles=max_cycles,
            name=f"{runtime.spec.domain.value}_research",
            config=config,
        )
        messages = result.get("messages", [])
        summary = str(getattr(messages[-1], "content", "")) if messages else ""
    except AgentCapabilityError as exc:
        exhausted = True
        summary = (
            "Research could not start because the configured model lacks the bounded "
            f"tool capability: {exc}. Disclose remaining gaps."
        )
    except Exception as exc:  # noqa: BLE001 - bounded failure is disclosed
        exhausted = True
        summary = (
            f"Research stopped at its bounded execution limit: {type(exc).__name__}: {exc}. "
            "Use deterministic analysis and completed tool evidence; disclose remaining gaps."
        )
    if len(trace) >= max_calls:
        exhausted = True
    return {
        "research_summary": summary[: runtime.max_research_context_chars],
        "research_trace": [*previous_trace, *trace],
        "research_round": state.get("research_round", 0) + 1,
        "research_budget_exhausted": exhausted,
        "research_mode": output_mode,
    }


__all__ = ["react_research"]
