"""Central skill discovery for chat and controlled analytical reviews.

A *skill* is a directory containing a ``SKILL.md`` file with YAML frontmatter:

    ---
    name: web_research
    description: How to research a topic on the web and cite sources.
    ---
    # Web research
    ...step-by-step instructions the model should follow...

The agent is told (in its system prompt) which skills exist and what they're
for, then pulls the full instructions on demand via the ``load_skill`` tool.
This "progressive disclosure" keeps the base prompt small while giving the model
deep, task-specific know-how when it needs it. Trusted analytical validation,
and registration live in sibling modules in this package and
are imported explicitly so general chat stays lightweight.
"""

__all__ = ["Skill", "build_skill_tools", "discover_skills", "render_skills_overview"]


def __getattr__(name: str):
    if name in {"Skill", "discover_skills"}:
        from data_agent.skills import loader

        return getattr(loader, name)
    if name in {"build_skill_tools", "render_skills_overview"}:
        from data_agent.skills import tools

        return getattr(tools, name)
    raise AttributeError(name)
