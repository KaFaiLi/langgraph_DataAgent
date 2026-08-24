"""Graph entrypoint for LangGraph Server / ``langgraph dev``.

``langgraph.json`` points at ``make_graph`` here. It must be async because
loading MCP tools requires a live client session.

    langgraph dev            # then open the studio URL it prints
"""

from __future__ import annotations

from typing import Any

from data_agent.agent.react_agent import build_agent


async def make_graph() -> Any:
    """Build and return the compiled ReAct agent graph."""
    bundle = await build_agent()
    return bundle.agent

