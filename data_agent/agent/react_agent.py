"""Build a LangGraph ReAct agent wired to the MCP server + skills + LLM.

The star of the show is :func:`build_agent`, an async factory that:

1. connects to the FastMCP server (stdio subprocess by default) and loads its
   tools via ``langchain-mcp-adapters``;
2. discovers skills from the skills folder and exposes them as tools;
3. builds the native SocGenAI chat model;
4. assembles a LangChain ``create_agent`` graph with a skills-aware system prompt.

It's async because loading MCP tools requires a live client session.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from copy import copy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackManager
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from data_agent.agent.prompts import build_system_prompt
from data_agent.config import Settings, get_settings
from data_agent.llm import get_chat_model
from data_agent.logging_utils import get_logger, setup_logging
from data_agent.skills.loader import Skill, discover_skills
from data_agent.skills.tools import build_skill_tools, render_skills_overview
from data_agent.tracing import ExecutionTraceHandler, TraceSink

logger = get_logger(__name__)

# Logical name for our server inside MultiServerMCPClient.
SERVER_KEY = "template"


def build_mcp_client(settings: Settings | None = None) -> MultiServerMCPClient:
    """Create a ``MultiServerMCPClient`` configured for our server.

    - ``stdio`` (default): spawns ``python -m data_agent.mcp_server`` as a
      subprocess. No separate server process to manage -- ideal for a template.
        - ``http``: connects to an already-running server at the URL derived from
            ``MCP_HOST`` and ``MCP_PORT``.
    """
    settings = settings or get_settings()
    transport = settings.mcp_transport.lower().strip()

    if transport == "stdio":
        # Force the child to stdio regardless of the parent's .env, and inherit
        # the current environment so the package + credentials are visible.
        child_env = {
            **os.environ,
            "MCP_TRANSPORT": "stdio",
            # Forward an explicitly supplied source root to the child MCP
            # process; otherwise Settings overrides would only affect the
            # parent and source tools would silently use the .env value.
            "SOURCE_ROOT": str(settings.source_path),
        }
        connection: dict[str, Any] = {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "data_agent.mcp_server"],
            "env": child_env,
        }
    elif transport == "http":
        connection = {
            "transport": "streamable_http",
            "url": settings.mcp_http_url,
            "timeout": settings.mcp_tool_timeout,
            "sse_read_timeout": settings.mcp_read_timeout,
        }
    else:
        raise ValueError(f"Unsupported MCP_TRANSPORT={transport!r}. Use 'stdio' or 'http'.")

    # MCP tool errors are returned as ToolMessage(status="error") by
    # langchain-mcp-adapters, so the LLM can reason over them and continue
    # the run instead of crashing.
    return MultiServerMCPClient({SERVER_KEY: connection})


@dataclass
class AgentBundle:
    """Everything you get back from :func:`build_agent`.

    Keep a reference to this around; it holds the compiled ``agent`` graph plus
    the pieces you'll want to inspect in a notebook.
    """

    agent: Any
    model: BaseChatModel
    mcp_client: MultiServerMCPClient
    mcp_tools: list[BaseTool]
    skill_tools: list[BaseTool] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    system_prompt: str = ""
    max_iterations: int = 10  # mirrors Settings.agent_max_iterations
    trace_result_preview_chars: int = 0

    @property
    def all_tools(self) -> list[BaseTool]:
        return [*self.mcp_tools, *self.skill_tools]

    def _run_config(self, extra: dict | None = None) -> dict:
        """Build a LangGraph run config that enforces ``max_iterations``.

        The limit remains conservative across model/tool graph steps and keeps
        the public ``agent_max_iterations`` setting as the controlling budget.
        """
        cfg: dict = {"recursion_limit": self.max_iterations * 3 + 2}
        if extra:
            cfg.update(extra)
        return cfg

    async def ainvoke(
        self,
        message: str,
        *,
        trace_sinks: Sequence[TraceSink] = (),
        **kwargs: Any,
    ) -> dict:
        """Convenience: send a single user message and return the raw state."""
        config = self._run_config(kwargs.pop("config", None))
        if trace_sinks:
            handler = ExecutionTraceHandler(
                logical_run_id=f"chat-{uuid4()}",
                sinks=trace_sinks,
                result_preview_chars=self.trace_result_preview_chars,
            )
            callbacks = config.get("callbacks")
            if callbacks is None:
                config["callbacks"] = [handler]
            elif isinstance(callbacks, list):
                config["callbacks"] = [*callbacks, handler]
            elif isinstance(callbacks, BaseCallbackManager):
                manager = copy(callbacks)
                manager.add_handler(handler, inherit=True)
                config["callbacks"] = manager
            else:
                raise TypeError("config callbacks must be a callback list or manager")
        return await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            **kwargs,
        )

    async def ask(
        self,
        message: str,
        *,
        trace_sinks: Sequence[TraceSink] = (),
        **kwargs: Any,
    ) -> str:
        """Convenience: send a message, return just the final text answer."""
        result = await self.ainvoke(message, trace_sinks=trace_sinks, **kwargs)
        return result["messages"][-1].content


async def build_agent(
    settings: Settings | None = None,
    *,
    model: BaseChatModel | None = None,
    extra_tools: list[BaseTool] | None = None,
) -> AgentBundle:
    """Build the ReAct agent and return an :class:`AgentBundle`.

    Args:
        settings: Override settings (defaults to :func:`get_settings`).
        model: Provide a pre-built chat model (skips native model construction).
        extra_tools: Additional LangChain tools to expose to the agent.
    """
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    # 1. MCP tools.
    mcp_client = build_mcp_client(settings)
    logger.info("Loading MCP tools (transport=%s)...", settings.mcp_transport)
    mcp_tools = await mcp_client.get_tools()
    logger.info("Loaded %d MCP tool(s): %s", len(mcp_tools), [t.name for t in mcp_tools])

    # 2. Skills -> tools + prompt overview.
    skills = discover_skills(settings.skills_path)
    skill_tools = build_skill_tools(skills)
    overview = render_skills_overview(skills)

    # 3. Model.
    model = model or get_chat_model(settings=settings)

    # 4. Assemble the graph. The skills-first directive is part of the stable
    #    system prompt because LangChain create_agent supersedes the deprecated
    #    pre-model-hook ReAct helper.
    tools: list[BaseTool] = [*mcp_tools, *skill_tools, *(extra_tools or [])]
    system_prompt = build_system_prompt(overview)
    if skills:
        skill_lines = "\n".join(f"  - {skill.name}: {skill.description}" for skill in skills)
        system_prompt += (
            "\n\nSKILL PLANNING — before any other action:\n"
            f"Available skills:\n{skill_lines}\n\n"
            "If a skill description matches the request, the first tool call must be "
            "load_skill(name=...). Follow its instructions before using another tool."
        )
    agent = create_agent(model, tools, system_prompt=system_prompt)

    return AgentBundle(
        agent=agent,
        model=model,
        mcp_client=mcp_client,
        mcp_tools=mcp_tools,
        skill_tools=skill_tools,
        skills=skills,
        system_prompt=system_prompt,
        max_iterations=settings.agent_max_iterations,
        trace_result_preview_chars=settings.trace_result_preview_chars,
    )
