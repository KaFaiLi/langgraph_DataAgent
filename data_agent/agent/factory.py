"""Pure graph construction helpers.

Resource discovery belongs to :mod:`data_agent.agent.react_agent`; this module
only turns already-loaded dependencies into a graph.  Child execution uses this
seam so it never recursively calls ``build_agent`` or reopens MCP sessions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool


def build_react_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    system_prompt: str,
    middleware: Sequence[AgentMiddleware[Any, Any]] = (),
    context_schema: type[Any] | None = None,
    checkpointer: Any = None,
    name: str | None = None,
) -> Any:
    """Build a ReAct graph from supplied model/tools without side effects."""

    return create_agent(
        model,
        list(tools),
        system_prompt=system_prompt,
        middleware=tuple(middleware),
        context_schema=context_schema,
        checkpointer=checkpointer,
        name=name,
    )


__all__ = ["build_react_graph"]
