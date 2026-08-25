"""Immutable dependencies and budgets for one generic specialist graph."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.tools.review_context import ToolContext


@dataclass(frozen=True)
class SpecialistSpec:
    """Skill identity, guidance, policy, and deterministic analysis entrypoint."""

    domain: SpecialistDomain
    report_id: str
    domain_label: str
    policy_text: str
    analyses_runner: Callable[[ToolContext, list[str]], Sequence[BaseModel]]
    research_guidance: str = ""


@dataclass(frozen=True)
class AdversarialBudget:
    """Bounded low-cost challenger execution limits.

    The challenger is intentionally cheaper and more tightly bounded than
    the analyst.  Initial and revision limits are separate so a revision can
    never inherit the larger initial budget.
    """

    max_initial_tool_calls: int = 8
    max_revision_tool_calls: int = 4
    max_initial_cycles: int = 6
    max_revision_cycles: int = 3
    max_context_chars: int = 40_000

    def __post_init__(self) -> None:
        for name in (
            "max_initial_tool_calls",
            "max_revision_tool_calls",
            "max_initial_cycles",
            "max_revision_cycles",
            "max_context_chars",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")


@dataclass(frozen=True)
class SpecialistRuntime:
    """Frozen adapters and bounded execution settings for a specialist graph.

    Skill loading supplies the deterministic runner through ``SpecialistSpec``;
    this runtime contains only immutable execution dependencies and budgets.
    """

    spec: SpecialistSpec
    llm_provider: ReviewLLMProvider = DEFAULT_LLM_PROVIDER
    max_verifier_rounds: int = 2
    adversarial_budget: AdversarialBudget = field(default_factory=AdversarialBudget)
    max_omission_rescue_rounds: int = 1

    max_initial_research_cycles: int = 12
    max_revision_research_cycles: int = 6
    max_initial_tool_calls: int = 24
    max_revision_tool_calls: int = 12
    max_research_context_chars: int = 60_000
    max_material_chars: int = 12_000
    max_revision_context_chars: int = 40_000

    def __post_init__(self) -> None:
        if self.max_verifier_rounds < 1 or self.max_verifier_rounds > 2:
            raise ValueError("max_verifier_rounds must be between 1 and 2")
        if not 0 <= self.max_omission_rescue_rounds <= 1:
            raise ValueError("max_omission_rescue_rounds must be 0 or 1")
        for name in (
            "max_initial_research_cycles",
            "max_revision_research_cycles",
            "max_initial_tool_calls",
            "max_revision_tool_calls",
            "max_research_context_chars",
            "max_material_chars",
            "max_revision_context_chars",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")


__all__ = ["AdversarialBudget", "SpecialistRuntime", "SpecialistSpec"]
