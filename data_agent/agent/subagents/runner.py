"""Admission, bounded execution, and cleanup for conversational children."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from data_agent.agent.factory import build_react_graph
from data_agent.agent.prompts import build_child_system_prompt
from data_agent.agent.runtime import invoke_scoped_graph
from data_agent.agent.subagents.contracts import (
    ChildPreparation,
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
        role_models: Mapping[str, Any] | None = None,
        child_adapter: Any = None,
    ) -> None:
        self.model = model
        self.role_models = dict(role_models or {})
        self.child_adapter = child_adapter
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

        if spec.input_schema is not None:
            try:
                spec.input_schema.model_validate_json(request.context)
            except ValueError:
                return self._result(
                    child_id=str(uuid4()),
                    agent_name=spec.name,
                    status="rejected",
                    error="context must match the trusted role input JSON schema",
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
            max_model_calls=min(
                self.policy.max_model_calls, spec.max_model_calls or self.policy.max_model_calls
            ),
            max_tool_calls=min(
                self.policy.max_tool_calls,
                spec.max_tool_calls
                if spec.max_tool_calls is not None
                else self.policy.max_tool_calls,
            ),
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
            except ChildBudgetExceeded as exc:
                result = self._result(
                    child_id=child_id,
                    agent_name=spec.name,
                    status="budget_exceeded",
                    error=str(exc),
                    model_calls=budget.model_calls,
                    tool_calls=budget.tool_calls,
                )
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
        preparation = (
            self.child_adapter.prepare(spec, request, child_id) if self.child_adapter else None
        )
        graph = (
            self._build_child_graph(spec, budget, preparation)
            if preparation
            else self._build_child_graph(spec, budget)
        )
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
        if preparation is not None:
            prompt = preparation.prompt
        if len(prompt) > self.policy.max_input_chars:
            return self._result(
                child_id=child_id,
                agent_name=spec.name,
                status="rejected",
                error="trusted role context exceeds input budget; narrow the assignment",
            )
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
        for result_attempt in range(2):
            messages = state.get("messages", []) if isinstance(state, Mapping) else []
            structured_response = (
                state.get("structured_response") if isinstance(state, Mapping) else None
            )
            # The ordinary ReAct graph resolves its schema transport tool internally.
            # Keep raw JSON until our strict boundary checks have rejected coercion/truncation.
            final = (
                AIMessage(content=json.dumps(structured_response))
                if spec.result_schema is not None and structured_response is not None
                else messages[-1]
                if messages
                else None
            )
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
            output, truncated = _bound_text(
                _content_text(final.content), self.policy.max_result_chars
            )
            if not output:
                return self._result(
                    child_id=child_id,
                    agent_name=spec.name,
                    status="failed",
                    error="child returned an empty final answer",
                    model_calls=budget.model_calls,
                    tool_calls=budget.tool_calls,
                )
            structured = None
            result_ref = None
            if spec.result_schema is not None:
                if truncated:
                    return self._result(
                        child_id=child_id,
                        agent_name=spec.name,
                        status="failed",
                        error="typed child output exceeds result budget",
                        truncated=True,
                        model_calls=budget.model_calls,
                        tool_calls=budget.tool_calls,
                    )
                parsed = None
                try:
                    fenced = re.fullmatch(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", output)
                    raw = json.loads(fenced.group(1) if fenced else output)
                    parsed = validate_typed_output(spec.result_schema, raw)
                    structured = parsed.model_dump(mode="json")
                    if preparation is not None and preparation.accept is not None:
                        receipt = preparation.accept(parsed)
                        result_ref = receipt["result_ref"]
                        structured = receipt
                        output = json.dumps(receipt, ensure_ascii=False)
                except (ValueError, TypeError, KeyError) as exc:
                    if (
                        parsed is None
                        and result_attempt == 0
                        and budget.model_calls < budget.max_model_calls
                    ):
                        # One bounded formatting repair retains this child's independent research.
                        # It cannot reopen research or bypass host admission/version checks.
                        budget.close_research = True
                        state = await invoke_scoped_graph(
                            graph,
                            {
                                "messages": [
                                    *messages,
                                    {
                                        "role": "user",
                                        "content": (
                                            "Your structured result failed validation: "
                                            + _sanitize_error(exc)
                                            + ". Correct the result using the existing evidence. Do not research again. "
                                            "Keep every string and array within its schema limit, use only declared fields "
                                            "and exact source:// evidence locators, and explicitly retain unresolved checks."
                                        ),
                                    },
                                ]
                            },
                            config=child_config,
                            context=child_context,
                        )
                        continue
                    return self._result(
                        child_id=child_id,
                        agent_name=spec.name,
                        status="failed",
                        error=f"invalid typed child result: {_sanitize_error(exc)}; "
                        f"output prefix={_sanitize_error(output[:120])!r}",
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
                structured_output=structured,
                result_ref=result_ref,
            )

    def _build_child_graph(
        self,
        spec: SubagentSpec,
        budget: ChildCallBudget,
        preparation: ChildPreparation | None = None,
    ) -> Any:
        selected_tools = (
            list(preparation.tools)
            if preparation
            else [self.tool_by_name[name] for name in spec.tool_names]
        )
        if any(tool.name not in spec.tool_names for tool in selected_tools):
            raise ValueError("prepared child tools exceed the trusted profile")
        skill_names = (
            preparation.skill_names
            if preparation and preparation.skill_names is not None
            else spec.skill_names
        )
        if set(skill_names) - set(spec.skill_names):
            raise ValueError("prepared child skills exceed the trusted profile")
        selected_skills = [self.skill_by_name[name] for name in skill_names]
        child_skill_tools = build_skill_tools(selected_skills)
        child_tools = [*selected_tools, *child_skill_tools]
        names = [tool.name for tool in child_tools]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate child tool names for {spec.name!r}")
        prompt = build_child_system_prompt(
            spec.system_prompt,
            render_skills_overview(selected_skills),
        )
        if spec.result_schema is not None:
            prompt += (
                "\nFinish by submitting the structured response tool matching this schema exactly.\n"
                + json.dumps(spec.result_schema.model_json_schema())
            )
        model = (
            self.model if spec.model_role == "general" else self.role_models.get(spec.model_role)
        )
        if model is None:
            raise ValueError(f"host has not configured model role {spec.model_role!r}")
        return self.graph_builder(
            model,
            child_tools,
            system_prompt=prompt,
            middleware=(
                ChildCallLimitMiddleware(budget, structured_result=spec.result_schema is not None),
            ),
            context_schema=InvocationContext,
            checkpointer=False,
            name=f"subagent_{spec.name}",
            **(
                {"result_schema": spec.result_schema.model_json_schema()}
                if spec.result_schema
                else {}
            ),
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
        structured_output: dict[str, Any] | None = None,
        result_ref: str | None = None,
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
            structured_output=structured_output,
            result_ref=result_ref,
        )
        return result


__all__ = ["DelegationRunner"]


def validate_typed_output(schema: type[BaseModel], raw: object) -> BaseModel:
    """Reject invalid, extra or silently truncated output before it can become authoritative."""
    parsed = schema.model_validate(raw)
    normalized = parsed.model_dump(mode="json")

    def unchanged(original, validated):
        if isinstance(original, dict):
            return isinstance(validated, dict) and all(
                key in validated and unchanged(value, validated[key])
                for key, value in original.items()
            )
        if isinstance(original, list):
            return (
                isinstance(validated, list)
                and len(original) == len(validated)
                and all(unchanged(a, b) for a, b in zip(original, validated, strict=True))
            )
        return original == validated

    if not unchanged(raw, normalized):
        raise ValueError("output contains extra fields, coercion or silent truncation")
    return parsed
