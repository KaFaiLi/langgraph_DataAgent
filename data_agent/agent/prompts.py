"""System prompt construction for the agent."""

from __future__ import annotations

BASE_SYSTEM_PROMPT = """\
You are a capable, careful assistant that solves tasks using tools.

Operating principles:
- Prefer calling a tool over guessing. If a tool can get you a fact, use it.
- Read each tool's description before calling it; pass well-formed arguments.
- Be economical with context: request only what you need, and don't dump large
  tool outputs back to the user verbatim -- summarize.
- If you cannot complete a task with the available tools, say so clearly.
"""


def build_system_prompt(skills_overview: str) -> str:
    """Combine the base prompt with the (cheap) skills catalog."""
    return f"{BASE_SYSTEM_PROMPT}\n{skills_overview}\n"


def build_child_system_prompt(system_prompt: str, skills_overview: str) -> str:
    """Build a fresh, bounded child prompt from a trusted spec.

    The parent conversation is intentionally absent.  The runner supplies only
    the delegated task and selected context as a user message.
    """

    trusted = system_prompt.strip()
    if not trusted:
        trusted = "You are a focused child assistant. Complete the delegated task carefully."
    return (
        f"{BASE_SYSTEM_PROMPT}\n"
        "You are a one-level child agent. Do not delegate to another agent. "
        "Use only the tools listed for this task, and cite source paths or locators "
        "when they support your answer.\n\n"
        f"Trusted child instructions:\n{trusted}\n\n"
        f"{skills_overview}\n"
    )


__all__ = ["BASE_SYSTEM_PROMPT", "build_child_system_prompt", "build_system_prompt"]
