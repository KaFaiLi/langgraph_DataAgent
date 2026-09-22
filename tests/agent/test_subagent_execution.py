"""Focused execution tests for the conversational child runner."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from data_agent.agent.subagents.contracts import (
    DelegationPolicy,
    InvocationContext,
    RunScope,
    SubagentSpec,
)
from data_agent.agent.subagents.registry import SubagentRegistry
from data_agent.agent.subagents.runner import DelegationRunner
from data_agent.tools.delegation import build_delegation_tool


class _StaticGraph:
    def __init__(self, output: Any, calls: list[dict[str, Any]]) -> None:
        self.output = output
        self.calls = calls

    async def ainvoke(self, state: dict[str, Any], *, config: Any, context: Any) -> dict[str, Any]:
        self.calls.append({"state": state, "config": config, "context": context})
        return {"messages": [AIMessage(content=self.output)]}


def _runner(
    graph_builder: Any,
    *,
    policy: DelegationPolicy | None = None,
) -> DelegationRunner:
    spec = SubagentSpec(
        name="research",
        description="Test research child",
        system_prompt="Answer with concise findings.",
    )
    registry = SubagentRegistry.build([spec], tools=[], skills=[])
    return DelegationRunner(
        model=object(),
        tools=[],
        registry=registry,
        policy=policy or DelegationPolicy(enabled=True),
        graph_builder=graph_builder,
    )


def test_delegation_tool_hides_injected_runtime_from_model_schema() -> None:
    tool = build_delegation_tool(object())

    assert set(tool.args) == {"agent_name", "task", "context"}
    assert "runtime" not in tool.tool_call_schema.model_fields
    assert "runtime" in tool.args_schema.model_fields


@pytest.mark.asyncio
async def test_runner_executes_a_fresh_child_graph_and_bounds_the_envelope() -> None:
    calls: list[dict[str, Any]] = []

    def build_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> _StaticGraph:
        del model
        assert list(tools) == []
        assert kwargs["checkpointer"] is False
        assert kwargs["context_schema"] is InvocationContext
        return _StaticGraph("child answer", calls)

    runner = _runner(build_graph)
    scope = RunScope(policy=runner.policy)
    result = await runner.run(
        {
            "agent_name": "research",
            "task": "Find the answer",
            "context": "The selected source is report.txt.",
        },
        scope=scope,
        tool_call_id="call-1",
    )

    assert result.status == "completed"
    assert result.output == "child answer"
    assert result.child_id
    assert result.model_calls == 0
    assert result.tool_calls == 0
    assert len(calls) == 1
    assert calls[0]["state"]["messages"][0]["content"] == (
        "Find the answer\n\nSelected context:\nThe selected source is report.txt."
    )
    assert isinstance(calls[0]["context"], InvocationContext)
    await scope.close()


@pytest.mark.asyncio
async def test_runner_uses_text_blocks_and_does_not_return_reasoning_blocks() -> None:
    def build_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> _StaticGraph:
        del model, tools, kwargs
        return _StaticGraph(
            [
                {"type": "text", "text": "visible answer"},
                {"type": "reasoning", "text": "private reasoning"},
            ],
            [],
        )

    policy = DelegationPolicy(enabled=True, max_result_chars=7)
    runner = _runner(build_graph, policy=policy)
    result = await runner.run(
        {"agent_name": "research", "task": "Summarize"},
        scope=RunScope(policy=policy),
    )

    assert result.status == "completed"
    assert result.output == "visible"
    assert result.truncated is True
    assert "private reasoning" not in result.output
