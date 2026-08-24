"""Adapter from a validated analytical skill to the generic specialist graph."""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from data_agent.review.orchestration import specialist_prompts
from data_agent.review.orchestration.specialist_graph import (
    DEFAULT_LLM_PROVIDER,
    LLMProvider,
    SpecialistSpec,
    build_specialist_graph,
)
from data_agent.skills.review import SkillDefinition, load_analysis_runner


def build_skill_graph(
    definition: SkillDefinition,
    llm_provider: LLMProvider = DEFAULT_LLM_PROVIDER,
) -> CompiledStateGraph:
    """Build the bounded analyst/verifier workflow configured by one skill."""

    def analyst_prompt(
        domain_label: str,
        desk_context: str,
        material_summary: str,
        analyses_json: str,
    ) -> str:
        return specialist_prompts.analyst_system_prompt(
            domain_label,
            desk_context,
            material_summary,
            analyses_json,
            definition.analyst_guidance,
        )

    def verifier_prompt(policy_text: str) -> str:
        return specialist_prompts.verifier_system_prompt(definition.label, policy_text)

    specialist = SpecialistSpec(
        domain=definition.domain,
        report_id=definition.report_id,
        domain_label=definition.label,
        policy_text=definition.verifier_policy,
        analyses_runner=load_analysis_runner(definition),
        analyst_system_prompt=analyst_prompt,
        verifier_system_prompt=verifier_prompt,
        research_guidance=definition.analyst_guidance,
    )
    return build_specialist_graph(specialist, llm_provider=llm_provider)
