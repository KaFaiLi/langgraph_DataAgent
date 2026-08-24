"""Build a LangGraph ReAct agent wired to the MCP server + skills + LLM.

The star of the show is :func:`build_agent`, an async factory that:

1. connects to the FastMCP server (stdio subprocess by default) and loads its
   tools via ``langchain-mcp-adapters``;
2. discovers skills from the skills folder and exposes them as tools;
3. builds the native SocGenAI chat model;
4. assembles a ``create_react_agent`` graph with a skills-aware system prompt.

It's async because loading MCP tools requires a live client session.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from data_agent.agent.prompts import build_system_prompt
from data_agent.config import Settings, get_settings
from data_agent.llm import get_chat_model
from data_agent.logging_utils import get_logger, setup_logging
from data_agent.skills.loader import Skill, discover_skills
from data_agent.skills.tools import build_skill_tools, render_skills_overview

logger = get_logger(__name__)

# Logical name for our server inside MultiServerMCPClient.
SERVER_KEY = "template"


def _make_skill_planner_hook(skills: list[Skill]):
    """Return a ``pre_model_hook`` that injects a skill-evaluation directive.

    On the **first** LLM call of each run (no AI messages in history yet), the
    hook prepends a ``SystemMessage`` that tells the model to check whether any
    available skill matches the user request before doing anything else.  On
    every subsequent call the messages are passed through unchanged.

    Using ``llm_input_messages`` means the injection is ephemeral — it never
    touches the persisted conversation state.
    """
    if not skills:
        # No skills → pass messages straight through on every call.
        def noop_hook(state: dict) -> dict:
            return {"llm_input_messages": state.get("messages", [])}
        return noop_hook

    skill_lines = "\n".join(f"  • {s.name}: {s.description}" for s in skills)
    directive = SystemMessage(
        content=(
            "SKILL PLANNING — do this once, before any other action:\n"
            f"Available skills:\n{skill_lines}\n\n"
            "Rule: if a skill description matches the user's request, your "
            "FIRST tool call MUST be load_skill(name=...). "
            "Follow the returned instructions before using any other tool. "
            "If no skill applies, skip this step and proceed with the available tools."
        )
    )

    def hook(state: dict) -> dict:
        messages = state.get("messages", [])
        # First call: no AI message in history yet → inject directive.
        if not any(isinstance(m, AIMessage) for m in messages):
            return {"llm_input_messages": [directive, *messages]}
        # Subsequent calls: pass messages through unchanged.
        return {"llm_input_messages": messages}

    return hook


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
        raise ValueError(
            f"Unsupported MCP_TRANSPORT={transport!r}. Use 'stdio' or 'http'."
        )

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

    @property
    def all_tools(self) -> list[BaseTool]:
        return [*self.mcp_tools, *self.skill_tools]

    def _run_config(self, extra: dict | None = None) -> dict:
        """Build a LangGraph run config that enforces ``max_iterations``.

        Each ReAct round (hook + model + tool) costs ~3 graph steps, so we set
        ``recursion_limit = max_iterations * 3 + 2`` to give exact headroom.
        """
        cfg: dict = {"recursion_limit": self.max_iterations * 3 + 2}
        if extra:
            cfg.update(extra)
        return cfg

    async def ainvoke(self, message: str, **kwargs: Any) -> dict:
        """Convenience: send a single user message and return the raw state."""
        return await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=self._run_config(kwargs.pop("config", None)),
            **kwargs,
        )

    async def ask(self, message: str, **kwargs: Any) -> str:
        """Convenience: send a message, return just the final text answer."""
        result = await self.ainvoke(message, **kwargs)
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

    # 4. Skill planner hook: injects an ephemeral skill-evaluation directive
    #    into the LLM context on the first call of every run.
    skill_hook = _make_skill_planner_hook(skills)

    # 5. Assemble the graph.
    tools: list[BaseTool] = [*mcp_tools, *skill_tools, *(extra_tools or [])]
    system_prompt = build_system_prompt(overview)
    agent = create_react_agent(model, tools, prompt=system_prompt, pre_model_hook=skill_hook)

    return AgentBundle(
        agent=agent,
        model=model,
        mcp_client=mcp_client,
        mcp_tools=mcp_tools,
        skill_tools=skill_tools,
        skills=skills,
        system_prompt=system_prompt,
        max_iterations=settings.agent_max_iterations,
    )
