"""Focused per-call and cancellation isolation tests for child execution."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from data_agent.agent.subagents.contracts import DelegationPolicy, RunScope, SubagentSpec
from data_agent.agent.subagents.registry import SubagentRegistry
from data_agent.agent.subagents.runner import DelegationRunner


class _ContextGraph:
    def __init__(
        self, *, started: asyncio.Event | None = None, release: asyncio.Event | None = None
    ):
        self.started = started
        self.release = release

    async def ainvoke(self, state: dict[str, Any], *, config: Any, context: Any) -> dict[str, Any]:
        del state, config
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            await self.release.wait()
        return {"messages": [AIMessage(content=context.agent_id)]}


def _runner(graph_builder: Any, policy: DelegationPolicy | None = None) -> DelegationRunner:
    policy = policy or DelegationPolicy(enabled=True)
    registry = SubagentRegistry.build([SubagentSpec(name="research")], tools=[], skills=[])
    return DelegationRunner(
        model=object(),
        tools=[],
        registry=registry,
        policy=policy,
        graph_builder=graph_builder,
    )


def _request(task: str = "work") -> dict[str, str]:
    return {"agent_name": "research", "task": task}


@pytest.mark.asyncio
async def test_same_tool_call_id_deduplicates_only_inside_one_scope() -> None:
    created: list[_ContextGraph] = []
    started = asyncio.Event()
    release = asyncio.Event()

    def build_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> _ContextGraph:
        del model, tools, kwargs
        graph = _ContextGraph(started=started, release=release)
        created.append(graph)
        return graph

    runner = _runner(build_graph)
    scope = RunScope(policy=runner.policy)
    first = asyncio.create_task(runner.run(_request(), scope=scope, tool_call_id="same"))
    await started.wait()
    second = asyncio.create_task(runner.run(_request(), scope=scope, tool_call_id="same"))
    await asyncio.sleep(0)
    release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert len(created) == 1
    assert first_result.child_id == second_result.child_id
    assert first_result.output == second_result.output
    await scope.close()


@pytest.mark.asyncio
async def test_two_root_scopes_never_share_child_identity() -> None:
    def build_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> _ContextGraph:
        del model, tools, kwargs
        return _ContextGraph()

    runner = _runner(build_graph)
    scope_a = RunScope(policy=runner.policy)
    scope_b = RunScope(policy=runner.policy)
    result_a, result_b = await asyncio.gather(
        runner.run(_request("a"), scope=scope_a, tool_call_id="same"),
        runner.run(_request("b"), scope=scope_b, tool_call_id="same"),
    )

    assert result_a.child_id != result_b.child_id
    assert result_a.output != result_b.output
    await scope_a.close()
    await scope_b.close()


@pytest.mark.asyncio
async def test_scope_close_cancels_and_awaits_a_child_task() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    def build_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> _ContextGraph:
        del model, tools, kwargs
        return _ContextGraph(started=started, release=release)

    runner = _runner(build_graph)
    scope = RunScope(policy=runner.policy)
    task = asyncio.create_task(runner.run(_request(), scope=scope, tool_call_id="cancel"))
    await started.wait()

    await scope.close()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert scope.active_tasks == ()
