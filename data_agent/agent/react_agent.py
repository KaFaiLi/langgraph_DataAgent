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
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackManager
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from data_agent.agent.factory import build_react_graph
from data_agent.agent.prompts import build_system_prompt
from data_agent.agent.runtime import build_lifecycle_graph
from data_agent.agent.subagents.contracts import DelegationPolicy, InvocationContext, SubagentSpec
from data_agent.agent.subagents.registry import SubagentRegistry, validate_tool_names
from data_agent.agent.subagents.runner import DelegationRunner
from data_agent.config import Settings, get_settings
from data_agent.llm import get_chat_model
from data_agent.logging_utils import get_logger, setup_logging
from data_agent.skills.loader import Skill, discover_skills
from data_agent.skills.tools import build_skill_tools, render_skills_overview
from data_agent.tools.delegation import build_delegation_tool
from data_agent.tools.review_skills import build_review_skill_tools
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
            "SKILLS_DIR": str(settings.skills_path),
            "REVIEW_WORKSPACE": str(settings.review_workspace_path),
            "REVIEW_RUN_ID": settings.review_run_id or "",
            "REVIEW_ASSIGNMENT_ID": settings.review_assignment_id or "",
            "REVIEW_OUTPUT_DIR": settings.review_output_dir or "",
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
    root_tools: list[BaseTool] = field(default_factory=list)
    delegation_tool: BaseTool | None = None
    delegation_runner: DelegationRunner | None = None
    delegation_policy: DelegationPolicy | None = None
    checkpoint_graph: Any = None

    @property
    def all_tools(self) -> list[BaseTool]:
        if self.root_tools:
            return list(self.root_tools)
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
    subagent_specs: Sequence[SubagentSpec] | None = None,
    role_models: dict[str, BaseChatModel] | None = None,
    checkpointer: Any = None,
    execution: Any = None,
) -> AgentBundle:
    """Build the ReAct agent and return an :class:`AgentBundle`.

    Args:
        settings: Override settings (defaults to :func:`get_settings`).
        model: Provide a pre-built chat model (skips native model construction).
        extra_tools: Additional LangChain tools to expose to the agent.
        subagent_specs: Optional trusted child profiles. When omitted and delegation
            is enabled, the built-in read-only research profile is used.
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
    if not settings.review_run_id:
        skill_tools += build_review_skill_tools(
            settings.source_path,
            settings.review_workspace_path,
            skills,
        )
    overview = render_skills_overview(skills)

    # 3. Model.
    model = model or get_chat_model(settings=settings)

    # 4. Assemble the root tool collection. Validate collisions before graph
    #    construction because ToolNode otherwise silently picks one definition.
    base_tools: list[BaseTool] = [*mcp_tools, *skill_tools, *(extra_tools or [])]
    validate_tool_names(base_tools)
    system_prompt = build_system_prompt(overview)
    if skills:
        skill_lines = "\n".join(f"  - {skill.name}: {skill.description}" for skill in skills)
        system_prompt += (
            "\n\nSKILL PLANNING — before any other action:\n"
            f"Available skills:\n{skill_lines}\n\n"
            "If a skill description matches the request, the first tool call must be "
            "load_skill(name=...). Follow its instructions before using another tool."
        )

    policy = DelegationPolicy.from_settings(settings)
    delegation_tool: BaseTool | None = None
    runner: DelegationRunner | None = None
    tools = base_tools
    parent_agent: Any
    registry: SubagentRegistry | None = None
    child_adapter = None
    if policy.enabled and settings.review_run_id and not settings.review_assignment_id:
        from data_agent.agent.subagents.review import ReviewRoleAdapter, review_profiles
        from data_agent.review.llm import ConfiguredReviewProvider, ModelTier
        from data_agent.skills.review import discover_skills as discover_review_skills
        from data_agent.tools.review_runs import ReviewWorkspace

        definitions = {s.name: s for s in discover_review_skills(settings.skills_path)}
        workspace = ReviewWorkspace(
            settings.source_path,
            settings.review_workspace_path,
            definitions,
            settings.review_run_id,
            output_dir=Path(settings.review_output_dir) if settings.review_output_dir else None,
        )
        child_adapter = ReviewRoleAdapter(workspace, settings.review_run_id)
        subagent_specs = subagent_specs or review_profiles(definitions)
        if role_models is None:
            provider = ConfiguredReviewProvider(settings)
            role_models = {
                "low_cost": provider(ModelTier.LOW_COST),
                "high_cost": provider(ModelTier.HIGH_COST),
            }
        policy = DelegationPolicy(
            enabled=True,
            max_runs=settings.review_child_max_runs,
            max_concurrency=settings.review_child_max_concurrency,
            max_model_calls=settings.review_child_max_model_calls,
            max_tool_calls=settings.review_child_max_tool_calls,
            timeout_seconds=settings.review_child_timeout_seconds,
            max_input_chars=settings.review_child_max_input_chars,
            max_result_chars=settings.review_child_max_result_chars,
        )
    if policy.enabled:
        registry = SubagentRegistry.build(
            subagent_specs,
            tools=base_tools,
            skills=skills,
        )
        runner = DelegationRunner(
            model=model,
            tools=base_tools,
            skills=skills,
            registry=registry,
            policy=policy,
            max_iterations=settings.agent_max_iterations,
            role_models=role_models,
            child_adapter=child_adapter,
            execution=execution,
        )
        delegation_tool = build_delegation_tool(runner)
        validate_tool_names([*base_tools, delegation_tool])
        tools = [*base_tools, delegation_tool]
        spec_lines = "\n".join(f"  - {spec.name}: {spec.description}" for spec in registry.specs)
        if child_adapter:
            system_prompt += (
                f"\nThe host-authorized review run_id is {settings.review_run_id!r}. "
                "Review peers require context as a JSON string matching the described input contract. "
                "The host supplies source context and role models; free-form child text cannot verify a report. "
                "Select and coordinate peers according to the outstanding obligations.\n"
            )
        system_prompt += (
            "\n\nDELEGATION — you may delegate one focused task to a trusted child "
            "agent and wait for its bounded result. Split independent work into "
            "independent calls, then synthesize the final answer yourself. Children "
            "cannot delegate further. Available child agents:\n"
            f"{spec_lines}\n"
            "Call run_subagent(agent_name=..., task=..., context=...) only when it "
            "improves the answer. Treat child findings as evidence to assess, and "
            "disclose failed, incomplete, or truncated work in your final synthesis."
        )
        parent_agent = build_react_graph(
            model,
            tools,
            system_prompt=system_prompt,
            context_schema=InvocationContext,
            checkpointer=checkpointer if checkpointer is not None else False,
            middleware=(execution_middleware(execution),) if execution else (),
            name="chat_parent",
        )
        agent = build_lifecycle_graph(
            parent_agent,
            runner,
            policy,
            checkpoint_thread_id=settings.review_run_id if checkpointer is not None else None,
        )
    else:
        parent_agent = build_react_graph(
            model, tools, system_prompt=system_prompt, name="chat_parent"
        )
        agent = parent_agent

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
        root_tools=tools,
        delegation_tool=delegation_tool,
        delegation_runner=runner,
        delegation_policy=policy,
        checkpoint_graph=parent_agent if checkpointer is not None else None,
    )


def execution_middleware(execution):
    from data_agent.review.application.execution import PersistentBudgetMiddleware

    return PersistentBudgetMiddleware(execution)
