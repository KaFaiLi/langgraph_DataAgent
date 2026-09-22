"""Public agent imports without import-time graph construction.

Lazy attribute loading keeps the contracts and delegation adapter acyclic while
preserving the package's historical ``from data_agent.agent import build_agent``
surface.
"""

from typing import Any

__all__ = ["AgentBundle", "build_agent", "build_mcp_client"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from data_agent.agent.react_agent import AgentBundle, build_agent, build_mcp_client

        return {
            "AgentBundle": AgentBundle,
            "build_agent": build_agent,
            "build_mcp_client": build_mcp_client,
        }[name]
    raise AttributeError(name)
