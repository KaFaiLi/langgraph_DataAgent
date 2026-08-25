"""Small bounded LangChain agent adapter used by review research nodes."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel


class AgentCapabilityError(RuntimeError):
    """Raised when a provider cannot support the required bounded tool loop."""


def run_bounded_structured_agent(
    model: Any,
    *,
    tools: list[Any],
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    max_cycles: int,
    name: str,
    config: RunnableConfig | None = None,
) -> BaseModel:
    """Run one tool-capable structured agent within a hard recursion bound.

    The adapter deliberately has no fallback to an unstructured model call:
    a challenger that cannot both inspect assigned sources and produce its
    bounded schema is a provider failure and must not be allowed to pass.
    """

    if max_cycles < 1:
        raise ValueError("max_cycles must be >= 1")
    if not callable(getattr(model, "bind_tools", None)):
        raise AgentCapabilityError("provider model does not support bound tools")
    try:
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy
    except (ImportError, AttributeError) as exc:  # pragma: no cover - dependency probe
        raise AgentCapabilityError(
            "LangChain structured tool-agent capability is unavailable"
        ) from exc

    agent = create_agent(
        model,
        tools,
        system_prompt=system_prompt,
        response_format=ToolStrategy(schema),
        name=name,
    )
    invoke_config: dict[str, Any] = {
        "recursion_limit": max_cycles * 2 + 2,
    }
    if config:
        for key in ("callbacks", "tags", "metadata"):
            if key in config:
                invoke_config[key] = config[key]
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_prompt}]},
        config=invoke_config,
    )
    response = result.get("structured_response") if isinstance(result, dict) else None
    if response is None:
        raise AgentCapabilityError("structured challenger response was not returned")
    if isinstance(response, schema):
        return response
    return schema.model_validate(response)


def run_bounded_agent(
    model: Any,
    *,
    tools: list[Any],
    system_prompt: str,
    user_prompt: str,
    max_cycles: int,
    name: str,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Run a bounded unstructured tool loop for analyst research."""

    if max_cycles < 1:
        raise ValueError("max_cycles must be >= 1")
    if not callable(getattr(model, "bind_tools", None)):
        raise AgentCapabilityError("provider model does not support bound tools")
    try:
        from langchain.agents import create_agent
    except (ImportError, AttributeError) as exc:  # pragma: no cover - dependency probe
        raise AgentCapabilityError("LangChain tool-agent capability is unavailable") from exc
    agent = create_agent(model, tools, system_prompt=system_prompt, name=name)
    invoke_config: dict[str, Any] = {"recursion_limit": max_cycles * 2 + 2}
    if config:
        for key in ("callbacks", "tags", "metadata"):
            if key in config:
                invoke_config[key] = config[key]
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_prompt}]},
        config=invoke_config,
    )
    return result if isinstance(result, dict) else {}


__all__ = ["AgentCapabilityError", "run_bounded_agent", "run_bounded_structured_agent"]
