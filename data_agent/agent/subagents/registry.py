"""Validation and lookup for trusted conversational sub-agent specs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from langchain_core.tools import BaseTool

from data_agent.agent.subagents.contracts import SubagentSpec
from data_agent.skills.loader import Skill

DEFAULT_RESEARCH_SPEC = SubagentSpec(
    name="research",
    description="Read and search the configured source material.",
    system_prompt=(
        "You are a focused research assistant. Use the supplied read-only source "
        "tools to gather facts, cite source paths or locators, and report limitations."
    ),
    tool_names=(
        "list_sources",
        "search_text",
        "read_lines",
        "read_document_section",
        "inspect_table",
        "read_rows",
    ),
)


class SubagentSpecError(ValueError):
    """Raised when application-owned child capabilities are not authorized."""


@dataclass(frozen=True)
class SubagentRegistry:
    """Immutable validated spec catalog used by a runner."""

    specs: tuple[SubagentSpec, ...]
    by_name: Mapping[str, SubagentSpec]

    @classmethod
    def build(
        cls,
        specs: Sequence[SubagentSpec] | None,
        *,
        tools: Iterable[BaseTool],
        skills: Iterable[Skill],
    ) -> SubagentRegistry:
        selected = tuple(specs) if specs is not None else (DEFAULT_RESEARCH_SPEC,)
        seen: set[str] = set()
        for spec in selected:
            if not isinstance(spec, SubagentSpec):
                raise SubagentSpecError("subagent_specs must contain SubagentSpec values")
            if spec.name in seen:
                raise SubagentSpecError(f"duplicate sub-agent spec name {spec.name!r}")
            seen.add(spec.name)

        tool_names = [tool.name for tool in tools]
        tool_set = set(tool_names)
        skill_set = {skill.name for skill in skills}
        for spec in selected:
            unknown_tools = sorted(set(spec.tool_names) - tool_set)
            if unknown_tools:
                raise SubagentSpecError(
                    f"sub-agent {spec.name!r} requests unavailable tools: "
                    + ", ".join(unknown_tools)
                )
            unknown_skills = sorted(set(spec.skill_names) - skill_set)
            if unknown_skills:
                raise SubagentSpecError(
                    f"sub-agent {spec.name!r} requests unavailable skills: "
                    + ", ".join(unknown_skills)
                )
            if "run_subagent" in spec.tool_names:
                raise SubagentSpecError("sub-agent specs cannot include run_subagent")
            # The root loader closes over the complete discovered catalog.  A
            # child must request skills through ``skill_names`` so its loader is
            # rebuilt over the explicitly selected subset.
            if "load_skill" in spec.tool_names:
                raise SubagentSpecError(
                    "sub-agent specs must use skill_names instead of root load_skill"
                )

        return cls(specs=selected, by_name=MappingProxyType({spec.name: spec for spec in selected}))

    def get(self, name: str) -> SubagentSpec | None:
        return self.by_name.get(name)

    def require(self, name: str) -> SubagentSpec:
        spec = self.get(name)
        if spec is None:
            available = ", ".join(self.by_name) or "(none)"
            raise SubagentSpecError(f"unknown sub-agent {name!r}; available: {available}")
        return spec


def validate_tool_names(tools: Iterable[BaseTool]) -> None:
    """Reject collisions before a graph is built.

    LangGraph's ToolNode keeps a name-to-tool mapping and would otherwise silently
    select one of two colliding tools.  Silent capability substitution is unsafe
    for both root and child tool collections.
    """

    seen: set[str] = set()
    duplicates: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if not isinstance(name, str) or not name:
            raise ValueError("every tool must have a non-empty name")
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise ValueError("duplicate tool names: " + ", ".join(sorted(duplicates)))


__all__ = [
    "DEFAULT_RESEARCH_SPEC",
    "SubagentRegistry",
    "SubagentSpecError",
    "validate_tool_names",
]
