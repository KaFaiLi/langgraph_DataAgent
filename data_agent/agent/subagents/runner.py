"""Admission, bounded execution, and cleanup for conversational children."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from data_agent.agent.factory import build_react_graph
from data_agent.agent.prompts import build_child_system_prompt
from data_agent.agent.runtime import invoke_scoped_graph
from data_agent.agent.subagents.contracts import (
    DelegationPolicy,
    DelegationRequest,
    DelegationResult,
    InvocationContext,
    RunScope,
    SubagentSpec,
)
from data_agent.agent.subagents.middleware import (
    ChildBudgetExceeded,
    ChildCallBudget,
    ChildCallLimitMiddleware,
)
from data_agent.agent.subagents.registry import SubagentRegistry, SubagentSpecError
from data_agent.skills.loader import Skill
from data_agent.skills.tools import build_skill_tools, render_skills_overview

_SECRET = re.compile(
    r"(?i)\b(api[-_]?key|token|password|secret|authorization|cookie)\b\s*[:=]\s*([^\s,;]+)"
)
_TRUNCATION_MARKER = "\n... (truncated)"


def _sanitize_error(error: BaseException | str, *, limit: int = 1_000) -> str:
    text = str(error)
    text = _SECRET.sub(r"\1=[REDACTED]", text).replace("\x00", "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _safe_agent_name(value: object) -> str:
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value[:128]
    return "unknown"


def _content_text(content: Any) -> str:
    """Normalize provider text blocks into one bounded plain string."""

    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, Mapping):
                text = block.get("text")
                if block.get("type") in {"text", "output_text"} and isinstance(text, str):
                    chunks.append(text)
            # Ignore non-text content blocks (including provider reasoning
            # blocks) instead of accidentally returning hidden payloads.
        return "".join(chunks)
    if isinstance(content, Mapping):
        text = content.get("text")
        return (
            str(text) if content.get("type") in {"text", "output_text"} and text is not None else ""
        )
    return ""


def _bound_text(text: str, limit: int) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= limit:
        return text, False
    if limit <= len(_TRUNCATION_MARKER):
        return text[:limit], True
    return text[: limit - len(_TRUNCATION_MARKER)] + _TRUNCATION_MARKER, True


class DelegationRunner:
    """Execute one-level child graphs using a validated root dependency catalog."""

    def __init__(
        self,
        *,
        model: Any,
        tools: Sequence[BaseTool],
        skills: Sequence[Skill] = (),
        registry: SubagentRegistry,
        policy: DelegationPolicy,
        max_iterations: int = 10,
        graph_builder: Callable[..., Any] = build_react_graph,
    ) -> None:
        self.model = model
        self.tools = tuple(tools)
        self.tool_by_name = {tool.name: tool for tool in self.tools}
        self.skills = tuple(skills)
        self.skill_by_name = {skill.name: skill for skill in self.skills}
        self.registry = registry
        self.policy = policy
        self.max_iterations = max_iterations
        self.graph_builder = graph_builder
        self._scopes: set[RunScope] = set()

    @property
    def active_scopes(self) -> tuple[RunScope, ...]:
        """Snapshot of currently active root scopes."""

        return tuple(self._scopes)

    @property
    def active_tasks(self) -> tuple[asyncio.Task[Any], ...]:
        tasks: list[asyncio.Task[Any]] = []
        for scope in self._scopes:
            tasks.extend(scope.active_tasks)
        return tuple(tasks)

    def register_scope(self, scope: RunScope) -> None:
        self._scopes.add(scope)

    def unregister_scope(self, scope: RunScope) -> None:
        self._scopes.discard(scope)

    async def run(
        self,
        request: DelegationRequest | dict[str, Any],
        *,
        scope: RunScope,
        config: RunnableConfig | None = None,
        tool_call_id: str | None = None,
        parent_depth: int = 0,
    ) -> DelegationResult:
        """Admit and execute one child, returning a bounded result envelope."""

        try:
            request = (
                request
                if isinstance(request, DelegationRequest)
                else DelegationRequest.model_validate(request)
            )
        except Exception:  # noqa: BLE001 - normalize request validation for the model
            return self._result(
                child_id=str(uuid4()),
                agent_name=_safe_agent_name(getattr(request, "agent_name", "unknown")),
                status="rejected",
                error="invalid delegation request",
            )

        if not self.policy.enabled:
            return self._result(
                child_id=str(uuid4()),
                agent_name=request.agent_name,
                status="rejected",
                error="sub-agent delegation is disabled",
            )
        if parent_depth >= 1:
            return self._result(
                child_id=str(uuid4()),
                agent_name=request.agent_name,
                status="rejected",
                error="nested sub-agent delegation is not available",
            )
        if len(request.task) + len(request.context) > self.policy.max_input_chars:
            return self._result(
                child_id=str(uuid4()),
                agent_name=request.agent_name,
                status="rejected",
                error=(
                    f"task and context exceed the {self.policy.max_input_chars}-character "
                    "input limit"
                ),
            )

        try:
            spec = self.registry.require(request.agent_name)
        except SubagentSpecError as exc:
            return self._result(
                child_id=str(uuid4()),
                agent_name=request.agent_name,
                status="rejected",
                error=_sanitize_error(exc),
            )

        key = tool_call_id or request.tool_call_id
        kind, existing, child_id = await scope.reserve_attempt(key)
        if kind == "cached":
            return existing  # type: ignore[return-value]
        if kind == "inflight":
            return await asyncio.shield(existing)  # type: ignore[arg-type]
        if kind == "rejected":
            return self._result(
                child_id=str(uuid4()),
                agent_name=request.agent_name,
                status="budget_exceeded",
                error="maximum child attempts exceeded",
            )

        assert child_id is not None
        future = existing if hasattr(existing, "set_result") else None
        budget = ChildCallBudget(
            max_model_calls=self.policy.max_model_calls,
            max_tool_calls=self.policy.max_tool_calls,
        )
        task = asyncio.current_task()
        if task is not None:
            scope.track(task)
        result: DelegationResult | None = None
        try:
            try:
                async with asyncio.timeout(self.policy.timeout_seconds):
                    async with scope.semaphore:
                        result = await self._execute(
                            spec,
                            request,
                            child_id,
                            scope=scope,
                            config=config,
                            budget=budget,
                        )
            except TimeoutError:
                result = self._result(
                    child_id=child_id,
                    agent_name=spec.name,
                    status="timed_out",
                    error=f"child exceeded {self.policy.timeout_seconds:g}-second deadline",
                    model_calls=budget.model_calls,
                    tool_calls=budget.tool_calls,
                )
            except asyncio.CancelledError:
                result = self._result(
                    child_id=child_id,
                    agent_name=spec.name,
                    status="failed",
                    error="child execution cancelled",
                    model_calls=budget.model_calls,
                    tool_calls=budget.tool_calls,
                )
                raise
            except Exception as exc:  # noqa: BLE001 - provider failures become bounded results
                result = self._result(
                    child_id=child_id,
                    agent_name=spec.name,
                    status="failed",
                    error=_sanitize_error(exc),
                    model_calls=budget.model_calls,
                    tool_calls=budget.tool_calls,
                )
            return result
        finally:
            if result is not None:
                await scope.finish_attempt(key, result, future)  # type: ignore[arg-type]
            elif future is not None and not future.done():
                future.cancel()
            if task is not None:
                scope.untrack(task)

    async def _execute(
        self,
        spec: SubagentSpec,
        request: DelegationRequest,
        child_id: str,
        *,
        scope: RunScope,
        config: RunnableConfig | None,
        budget: ChildCallBudget,
    ) -> DelegationResult:
        graph = self._build_child_graph(spec, budget)
        child_config = self._child_config(config, scope=scope, child_id=child_id, spec=spec)
        child_context = InvocationContext(
            scope=scope,
            runner=self,
            agent_id=child_id,
            agent_name=spec.name,
            parent_agent_id=scope.root_agent_id,
            depth=1,
            graph="chat",
        )
        prompt = request.task
        if request.context:
            prompt += "\n\nSelected context:\n" + request.context
        try:
            state = await invoke_scoped_graph(
                graph,
                {"messages": [{"role": "user", "content": prompt}]},
                config=child_config,
                context=child_context,
            )
        except ChildBudgetExceeded as exc:
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="budget_exceeded",
                error=str(exc),
                model_calls=budget.model_calls,
                tool_calls=budget.tool_calls,
            )
        messages = state.get("messages", []) if isinstance(state, Mapping) else []
        final = messages[-1] if messages else None
        if not isinstance(final, AIMessage):
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="failed",
                error="child did not return a final assistant message",
                model_calls=budget.model_calls,
                tool_calls=budget.tool_calls,
            )
        if final.invalid_tool_calls:
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="failed",
                error="child returned malformed tool calls",
                model_calls=budget.model_calls,
                tool_calls=budget.tool_calls,
            )
        if final.tool_calls:
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="failed",
                error="child returned unresolved tool calls",
                model_calls=budget.model_calls,
                tool_calls=budget.tool_calls,
            )
        if budget.exceeded_kind is not None:
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="budget_exceeded",
                error="child model/tool call budget exceeded",
                model_calls=budget.model_calls,
                tool_calls=budget.tool_calls,
            )
        output, truncated = _bound_text(_content_text(final.content), self.policy.max_result_chars)
        if not output:
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="failed",
                error="child returned an empty final answer",
                model_calls=budget.model_calls,
                tool_calls=budget.tool_calls,
            )
        return self._result(
            child_id=child_id,
            agent_name=spec.name,
            status="completed",
            output=output,
            truncated=truncated,
            model_calls=budget.model_calls,
            tool_calls=budget.tool_calls,
        )

    def _build_child_graph(self, spec: SubagentSpec, budget: ChildCallBudget) -> Any:
        selected_tools = [self.tool_by_name[name] for name in spec.tool_names]
        selected_skills = [self.skill_by_name[name] for name in spec.skill_names]
        child_skill_tools = build_skill_tools(selected_skills)
        child_tools = [*selected_tools, *child_skill_tools]
        names = [tool.name for tool in child_tools]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate child tool names for {spec.name!r}")
        prompt = build_child_system_prompt(
            spec.system_prompt,
            render_skills_overview(selected_skills),
        )
        return self.graph_builder(
            self.model,
            child_tools,
            system_prompt=prompt,
            middleware=(ChildCallLimitMiddleware(budget),),
            context_schema=InvocationContext,
            checkpointer=False,
            name=f"subagent_{spec.name}",
        )

    def _child_config(
        self,
        config: RunnableConfig | None,
        *,
        scope: RunScope,
        child_id: str,
        spec: SubagentSpec,
    ) -> RunnableConfig:
        child_config: dict[str, Any] = dict(config or {})
        child_config.pop("run_id", None)
        # A child graph is intentionally compiled without a checkpointer.  Clear
        # configurable identity as well so host thread/checkpoint values cannot be
        # accidentally interpreted as a child namespace by a provider/runtime.
        child_config["configurable"] = {
            key: value
            for key, value in (child_config.get("configurable") or {}).items()
            if key in {"__pregel_stream", "__pregel_runtime"}
        }
        # Parent recursion settings bound the root loop. A child has its own
        # model/tool budget and needs enough graph steps to consume it.
        child_config["recursion_limit"] = self.policy.max_model_calls * 3 + 2
        metadata = {
            key: value
            for key, value in (child_config.get("metadata") or {}).items()
            if key in {"risk_agent_graph", "risk_agent_specialist"}
        }
        metadata.update(
            {
                "data_agent_id": child_id,
                "data_agent_parent_id": scope.root_agent_id,
                "data_agent_name": spec.name,
                "data_agent_depth": 1,
                "data_agent_graph": "chat",
            }
        )
        child_config["metadata"] = metadata
        return child_config

    def _result(
        self,
        *,
        child_id: str,
        agent_name: str,
        status: Any,
        output: str = "",
        truncated: bool = False,
        error: str | None = None,
        model_calls: int = 0,
        tool_calls: int = 0,
    ) -> DelegationResult:
        result = DelegationResult(
            output=output,
            status=status,
            child_id=child_id,
            agent_name=agent_name,
            truncated=truncated,
            error=error,
            model_calls=model_calls,
            tool_calls=tool_calls,
        )
        return result


__all__ = ["DelegationRunner"]
