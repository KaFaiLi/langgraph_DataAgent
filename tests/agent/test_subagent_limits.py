"""Focused admission and budget tests for conversational children."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from data_agent.agent.subagents.contracts import DelegationPolicy, RunScope, SubagentSpec
from data_agent.agent.subagents.middleware import ChildBudgetExceeded, ChildCallBudget
from data_agent.agent.subagents.registry import SubagentRegistry
from data_agent.agent.subagents.runner import DelegationRunner


def _policy(**overrides: Any) -> DelegationPolicy:
    values = {"enabled": True}
    values.update(overrides)
    return DelegationPolicy(**values)


def _runner(graph_builder: Any, policy: DelegationPolicy) -> DelegationRunner:
    registry = SubagentRegistry.build(
        [SubagentSpec(name="research")],
        tools=[],
        skills=[],
    )
    return DelegationRunner(
        model=object(),
        tools=[],
        registry=registry,
        policy=policy,
        graph_builder=graph_builder,
    )


def test_policy_rejects_invalid_concurrency_and_nonfinite_deadlines() -> None:
    with pytest.raises(ValidationError, match="max_concurrency"):
        _policy(max_runs=1)
    with pytest.raises(ValidationError, match="finite"):
        _policy(timeout_seconds=float("inf"))


@pytest.mark.asyncio
async def test_atomic_scope_admission_does_not_overspend_attempts() -> None:
    scope = RunScope(policy=_policy(max_runs=3, max_concurrency=3))
    reservations = await asyncio.gather(*(scope.reserve_attempt(str(i)) for i in range(12)))

    assert sum(kind == "new" for kind, _, _ in reservations) == 3
    assert sum(kind == "rejected" for kind, _, _ in reservations) == 9
    await scope.close()


@pytest.mark.asyncio
async def test_atomic_child_call_budget_has_one_winner_per_final_slot() -> None:
    budget = ChildCallBudget(max_model_calls=3, max_tool_calls=1)

    async def reserve() -> bool:
        try:
            await budget.reserve_model()
        except ChildBudgetExceeded:
            return False
        return True

    outcomes = await asyncio.gather(*(reserve() for _ in range(10)))

    assert sum(outcomes) == 3
    assert budget.model_calls == 3
    assert budget.exceeded_kind == "model"


@pytest.mark.asyncio
async def test_timeout_includes_waiting_for_a_concurrency_slot() -> None:
    started = asyncio.Event()
    first_cancelled = asyncio.Event()
    release_first = asyncio.Event()
    calls = 0

    class SlowGraph:
        async def ainvoke(
            self, state: dict[str, Any], *, config: Any, context: Any
        ) -> dict[str, Any]:
            nonlocal calls
            del state, config, context
            calls += 1
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                # Keep the semaphore occupied until the queued sibling has
                # reached its own deadline.  This makes the queue assertion
                # independent of event-loop scheduling.
                first_cancelled.set()
                await release_first.wait()
                raise
            return {"messages": [AIMessage(content="late")]}

    def build_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> SlowGraph:
        del model, tools, kwargs
        return SlowGraph()

    policy = _policy(max_runs=2, max_concurrency=1, timeout_seconds=0.05)
    runner = _runner(build_graph, policy)
    scope = RunScope(policy=policy)
    first = asyncio.create_task(
        runner.run({"agent_name": "research", "task": "first"}, scope=scope, tool_call_id="one")
    )
    await started.wait()
    second = asyncio.create_task(
        runner.run({"agent_name": "research", "task": "second"}, scope=scope, tool_call_id="two")
    )
    await first_cancelled.wait()
    second_result = await second
    release_first.set()
    first_result = await first

    assert first_result.status == "timed_out"
    assert second_result.status == "timed_out"
    assert calls == 1
    assert scope.active_tasks == ()
    await scope.close()
