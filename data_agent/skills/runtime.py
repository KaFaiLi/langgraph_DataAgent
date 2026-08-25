"""Adapter from a validated analytical skill to the generic specialist graph."""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.orchestration.specialist import (
    SpecialistRuntime,
    SpecialistSpec,
    build_specialist_graph,
)
from data_agent.skills.review import SkillDefinition, load_analysis_runner


def build_skill_graph(
    definition: SkillDefinition,
    llm_provider: ReviewLLMProvider = DEFAULT_LLM_PROVIDER,
) -> CompiledStateGraph:
    """Build the bounded analyst/verifier workflow configured by one skill."""

    specialist = SpecialistSpec(
        domain=definition.domain,
        report_id=definition.report_id,
        domain_label=definition.label,
        policy_text=definition.verifier_policy,
        analyses_runner=load_analysis_runner(definition),
        research_guidance=definition.analyst_guidance,
    )
    runtime = SpecialistRuntime(
        spec=specialist,
        llm_provider=llm_provider,
    )
    return build_specialist_graph(runtime)
