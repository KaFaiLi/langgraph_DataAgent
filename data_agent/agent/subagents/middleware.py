"""Per-child model/tool call accounting middleware."""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import AIMessage, ToolMessage


class ChildBudgetExceeded(RuntimeError):
    """Raised when a child attempts a model or tool call beyond its allowance."""

    def __init__(self, kind: str, limit: int) -> None:
        self.kind = kind
        self.limit = limit
        super().__init__(f"__SUBAGENT_BUDGET_EXCEEDED__: {kind} call limit {limit} reached")


class ChildCallBudget:
    """Atomic per-child counters shared by all middleware hooks for that child."""

    def __init__(self, *, max_model_calls: int, max_tool_calls: int) -> None:
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls
        self.model_calls = 0
        self.tool_calls = 0
        self.exceeded_kind: str | None = None
        self._lock = threading.Lock()

    async def reserve_model(self) -> int:
        with self._lock:
            if self.model_calls >= self.max_model_calls:
                self.exceeded_kind = "model"
                raise ChildBudgetExceeded("model", self.max_model_calls)
            self.model_calls += 1
            return self.model_calls

    async def reserve_tool(self) -> int:
        with self._lock:
            if self.tool_calls >= self.max_tool_calls:
                self.exceeded_kind = "tool"
                raise ChildBudgetExceeded("tool", self.max_tool_calls)
            self.tool_calls += 1
            return self.tool_calls

    def reserve_model_sync(self) -> int:
        with self._lock:
            if self.model_calls >= self.max_model_calls:
                self.exceeded_kind = "model"
                raise ChildBudgetExceeded("model", self.max_model_calls)
            self.model_calls += 1
            return self.model_calls

    def reserve_tool_sync(self) -> int:
        with self._lock:
            if self.tool_calls >= self.max_tool_calls:
                self.exceeded_kind = "tool"
                raise ChildBudgetExceeded("tool", self.max_tool_calls)
            self.tool_calls += 1
            return self.tool_calls


class ChildCallLimitMiddleware(AgentMiddleware[Any, Any]):
    """Reserve each child model/tool call before dispatching it.

    The limits are intentionally enforced in middleware, adjacent to the actual
    LangChain call, rather than by graph recursion counting.  The latter counts
    graph steps and cannot distinguish a model retry from a tool call.
    """

    def __init__(self, budget: ChildCallBudget) -> None:
        self.budget = budget

    @property
    def name(self) -> str:
        return "ChildCallLimitMiddleware"

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any] | AIMessage:
        await self.budget.reserve_model()
        return await handler(request)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage:
        self.budget.reserve_model_sync()
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage]],
    ) -> ToolMessage | Any:
        try:
            await self.budget.reserve_tool()
        except ChildBudgetExceeded as exc:
            return ToolMessage(
                content=str(exc),
                name=request.tool_call["name"],
                tool_call_id=request.tool_call["id"],
                status="error",
                additional_kwargs={"subagent_budget_exceeded": True},
            )
        return await handler(request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage],
    ) -> ToolMessage | Any:
        try:
            self.budget.reserve_tool_sync()
        except ChildBudgetExceeded as exc:
            return ToolMessage(
                content=str(exc),
                name=request.tool_call["name"],
                tool_call_id=request.tool_call["id"],
                status="error",
                additional_kwargs={"subagent_budget_exceeded": True},
            )
        return handler(request)


__all__ = ["ChildBudgetExceeded", "ChildCallBudget", "ChildCallLimitMiddleware"]
