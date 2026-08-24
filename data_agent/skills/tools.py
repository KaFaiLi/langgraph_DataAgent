"""Turn discovered skills into LangChain tools + a system-prompt overview."""

from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import BaseModel, Field

from data_agent.skills.loader import Skill


class _LoadSkillInput(BaseModel):
    """Input schema for the ``load_skill`` tool."""

    name: str = Field(description="Exact skill name shown in the system prompt.")


def render_skills_overview(skills: list[Skill]) -> str:
    """Render a compact catalog of skills for the system prompt.

    Only names + descriptions (cheap on context). The full body is fetched on
    demand via ``load_skill``.
    """
    if not skills:
        return "No skills are currently available."
    lines = ["You have access to the following skills (load one before using it):"]
    for s in skills:
        lines.append(f"- {s.name}: {s.description}")
    lines.append(
        "\nCall `load_skill(name=...)` to read a skill's full instructions, then "
        "follow them."
    )
    return "\n".join(lines)


def build_skill_tools(skills: list[Skill]) -> list[BaseTool]:
    """Build the on-demand skill loader for the catalog already in the prompt."""
    by_name = {s.name: s for s in skills}
    if not by_name:
        return []

    def load_skill(name: str) -> str:
        """Load a skill's full instructions by name, then follow them.

        Args:
            name: The exact skill name shown in the system prompt.

        Raises:
            ToolException: if no skill with the given name exists.  The agent
                receives the error message and can try another name or proceed
                without the skill.
        """
        skill = by_name.get(name)
        if skill is None:
            available = ", ".join(by_name) or "(none)"
            raise ToolException(
                f"Unknown skill {name!r}. Available skills: {available}."
            )
        return skill.instructions

    load_tool = StructuredTool.from_function(
        func=load_skill,
        name="load_skill",
        args_schema=_LoadSkillInput,
        description=(
            "Load a skill's full step-by-step instructions by name. Call this "
            "before attempting a task a skill covers, then follow the returned "
            "instructions."
        ),
        handle_tool_errors=True,
    )
    return [load_tool]
