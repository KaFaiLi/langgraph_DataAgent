"""Small, dependency-light contracts used by conversational delegation.

The contracts in this module intentionally do not import the agent bootstrap,
MCP client, or review workflow.  They can therefore be used by tools and tests
without causing graph construction as a side effect.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from data_agent.config import Settings


class SubagentSpec(BaseModel):
    """Trusted application-owned description of a child agent.

    A spec is deliberately declarative.  The model may choose a spec by name,
    but it cannot supply prompts, tools, skills, credentials, or limits.  The
    registry validates every tool and skill name against the already-authorized
    root catalog before exposing a spec to the runner.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    system_prompt: str = ""
    tool_names: tuple[str, ...] = ()
    skill_names: tuple[str, ...] = ()
    input_schema: type[BaseModel] | None = None
    result_schema: type[BaseModel] | None = None
    model_role: Literal["general", "low_cost", "high_cost"] = "general"
    max_model_calls: int | None = Field(default=None, gt=0)
    max_tool_calls: int | None = Field(default=None, ge=0)

    @field_validator("name", "description", "system_prompt", mode="before")
    @classmethod
    def _text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("sub-agent text fields must be strings")
        return value

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("sub-agent name must not be blank")
        return value

    @field_validator("tool_names", "skill_names", mode="before")
    @classmethod
    def _names(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = (value,)
        try:
            values = tuple(value)  # type: ignore[arg-type]
        except TypeError as exc:
            raise TypeError("tool_names and skill_names must be sequences") from exc
        cleaned: list[str] = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("tool and skill names must be non-empty strings")
            cleaned.append(item.strip())
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("tool and skill names must be unique")
        return tuple(cleaned)


class DelegationRequest(BaseModel):
    """Validated model-facing request for one child attempt."""

    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(min_length=1, max_length=128)
    task: str = Field(min_length=1)
    context: str = ""
    tool_call_id: str | None = None

    @field_validator("agent_name", "task", "context", mode="before")
    @classmethod
    def _require_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("delegation request fields must be strings")
        return value

    @field_validator("agent_name", "task")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("delegation request fields must not be blank")
        return value


DelegationStatus = Literal["completed", "failed", "timed_out", "budget_exceeded", "rejected"]


class DelegationResult(BaseModel):
    """Bounded host-generated envelope returned to the parent tool call."""

    model_config = ConfigDict(extra="forbid")

    output: str = ""
    status: DelegationStatus
    child_id: str
    agent_name: str = Field(max_length=128)
    truncated: bool = False
    error: str | None = None
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    structured_output: dict[str, Any] | None = None
    result_ref: str | None = None

    def envelope(self) -> dict[str, Any]:
        """Return the compact model-visible result mapping."""

        return self.model_dump(mode="json")


class DelegationPolicy(BaseModel):
    """Validated limits for one root invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    max_runs: int = Field(default=4, gt=0)
    max_concurrency: int = Field(default=2, gt=0)
    max_model_calls: int = Field(default=6, gt=0)
    max_tool_calls: int = Field(default=12, gt=0)
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_input_chars: int = Field(default=16_000, gt=0)
    max_result_chars: int = Field(default=8_000, gt=0)

    @model_validator(mode="after")
    def _validate_limits(self) -> DelegationPolicy:
        if self.max_concurrency > self.max_runs:
            raise ValueError("max_concurrency must not exceed max_runs")
        if not math.isfinite(self.timeout_seconds):
            raise ValueError("timeout_seconds must be finite")
        return self

    @classmethod
    def from_settings(cls, settings: Settings) -> DelegationPolicy:
        """Build policy from the typed application settings."""

        return cls(
            enabled=settings.subagents_enabled,
            max_runs=settings.subagent_max_runs,
            max_concurrency=settings.subagent_max_concurrency,
            max_model_calls=settings.subagent_max_model_calls,
            max_tool_calls=settings.subagent_max_tool_calls,
            timeout_seconds=settings.subagent_timeout_seconds,
            max_input_chars=settings.subagent_max_input_chars,
            max_result_chars=settings.subagent_max_result_chars,
        )


@dataclass(frozen=True)
class ChildPreparation:
    """Trusted per-attempt tools/context and an optional validated-result publisher."""

    prompt: str
    tools: tuple[Any, ...]
    skill_names: tuple[str, ...] | None = None
    accept: Any = None


@dataclass
class InvocationContext:
    """Runtime-only dependency injection context passed to graph tools.

    It is intentionally a mutable-free carrier of references.  The contained
    scope owns all mutable admission state and is never placed in graph state or
    a checkpoint.
    """

    scope: RunScope
    runner: Any
    agent_id: str
    agent_name: str
    parent_agent_id: str | None
    depth: int
    graph: str = "chat"


@dataclass(eq=False)
class RunScope:
    """Per-root invocation ledger and child task owner.

    A new instance is made for every lifecycle graph invocation.  No mutable
    counters or tasks live on the reusable AgentBundle.
    """

    policy: DelegationPolicy
    root_agent_id: str = field(default_factory=lambda: str(uuid4()))
    root_agent_name: str = "root"
    child_attempts: int = 0
    closed: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)
    _tasks: set[asyncio.Task[Any]] = field(default_factory=set, init=False, repr=False)
    _inflight: dict[str, asyncio.Future[DelegationResult]] = field(
        default_factory=dict, init=False, repr=False
    )
    _completed: dict[str, DelegationResult] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.policy.max_concurrency)

    @property
    def active_tasks(self) -> tuple[asyncio.Task[Any], ...]:
        """Snapshot of locally tracked child tasks for cleanup diagnostics."""

        return tuple(task for task in self._tasks if not task.done())

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    async def reserve_attempt(
        self, key: str | None
    ) -> tuple[str, DelegationResult | asyncio.Future[DelegationResult] | None, str | None]:
        """Atomically reserve a child or return a cached/in-flight result.

        The first tuple item is ``new``, ``cached``, ``inflight`` or ``rejected``.
        ``key`` is normally the parent tool-call ID; it is scoped to this root.
        """

        async with self._lock:
            if key:
                if key in self._completed:
                    return "cached", self._completed[key], None
                if key in self._inflight:
                    return "inflight", self._inflight[key], None
            if self.closed:
                return "rejected", None, "invocation scope is closed"
            if self.child_attempts >= self.policy.max_runs:
                return "rejected", None, "maximum child attempts exceeded"
            self.child_attempts += 1
            future: asyncio.Future[DelegationResult] | None = None
            if key:
                future = asyncio.get_running_loop().create_future()
                self._inflight[key] = future
            return "new", future, str(uuid4())

    async def finish_attempt(
        self,
        key: str | None,
        result: DelegationResult,
        future: asyncio.Future[DelegationResult] | None,
    ) -> None:
        async with self._lock:
            if key:
                self._inflight.pop(key, None)
                self._completed[key] = result
            if future is not None and not future.done():
                future.set_result(result)

    def track(self, task: asyncio.Task[Any]) -> None:
        self._tasks.add(task)

    def untrack(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)

    async def close(self) -> None:
        """Cancel and await all local child tasks, including on root cancellation."""

        async with self._lock:
            self.closed = True
            tasks = [task for task in self._tasks if task is not asyncio.current_task()]
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        async with self._lock:
            for future in self._inflight.values():
                if not future.done():
                    future.cancel()
            self._inflight.clear()


__all__ = [
    "DelegationPolicy",
    "DelegationRequest",
    "DelegationResult",
    "DelegationStatus",
    "InvocationContext",
    "RunScope",
    "SubagentSpec",
]
