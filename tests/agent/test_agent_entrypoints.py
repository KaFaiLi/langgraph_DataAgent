"""Exercise delegation through the public graph and bundle interfaces."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from langchain.tools import ToolRuntime
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph

from data_agent.agent import graph as graph_entrypoint
from data_agent.agent import react_agent
from data_agent.agent.subagents.contracts import SubagentSpec
from data_agent.config import Settings
from data_agent.tools.source_tools import read_lines_data
from data_agent.tracing import EventType, InMemoryTraceSink


class RoutingModel(BaseChatModel):
    """Route scripted responses using bound tools, with no shared response cursor."""

    respond: Callable[[list[BaseMessage], tuple[str, ...]], AIMessage]

    @property
    def _llm_type(self) -> str:
        return "entrypoint-test-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self.bind(bound_tool_names=tuple(tool.name for tool in tools))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        message = self.respond(messages, tuple(kwargs.get("bound_tool_names", ())))
        return ChatResult(generations=[ChatGeneration(message=message)])


def _call(name: str, arguments: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": arguments, "id": call_id}])


def _user_text(messages: list[BaseMessage]) -> str:
    return "\n".join(
        str(message.content) for message in messages if isinstance(message, HumanMessage)
    )


def _relay(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
    if "run_subagent" not in names:
        return AIMessage(content=f"child result: {_user_text(messages)}")
    if isinstance(messages[-1], ToolMessage):
        return AIMessage(content=str(messages[-1].content))
    return _call(
        "run_subagent",
        {"agent_name": "research", "task": _user_text(messages), "context": ""},
        "same-call-id",
    )


async def _bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    respond: Callable[[list[BaseMessage], tuple[str, ...]], AIMessage] = _relay,
    tools: list[BaseTool] | None = None,
    **overrides: Any,
) -> react_agent.AgentBundle:
    loaded_tools = tools or []

    class Client:
        loads = 0

        async def get_tools(self) -> list[BaseTool]:
            self.loads += 1
            return loaded_tools

    client = Client()
    monkeypatch.setattr(react_agent, "build_mcp_client", lambda settings: client)
    settings = Settings(
        _env_file=None,
        subagents_enabled=True,
        skills_dir=str(tmp_path / "no-skills"),
        **overrides,
    )
    bundle = await react_agent.build_agent(
        settings,
        model=RoutingModel(respond=respond),
        subagent_specs=[
            SubagentSpec(
                name="research",
                description="Research the assigned task.",
                system_prompt="Investigate this task and report the result.",
                tool_names=tuple(tool.name for tool in loaded_tools),
                skill_names=(),
            )
        ],
    )
    assert client.loads == 1
    return bundle


@pytest.mark.asyncio
async def test_concurrent_raw_graph_calls_have_independent_child_budgets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = await _bundle(
        monkeypatch,
        tmp_path,
        subagent_max_runs=1,
        subagent_max_concurrency=1,
    )
    outputs = await asyncio.gather(
        *(
            bundle.agent.ainvoke({"messages": [{"role": "user", "content": name}]})
            for name in ("alpha", "beta")
        )
    )
    results = [json.loads(output["messages"][-1].content) for output in outputs]
    assert [result["status"] for result in results] == ["completed", "completed"]
    assert results[0]["child_id"] != results[1]["child_id"]
    assert "alpha" in results[0]["output"] and "beta" not in results[0]["output"]
    assert "beta" in results[1]["output"] and "alpha" not in results[1]["output"]
    assert bundle.mcp_client.loads == 1
    again = json.loads(await bundle.ask("gamma"))
    assert again["status"] == "completed"
    assert again["child_id"] not in {result["child_id"] for result in results}


@pytest.mark.asyncio
async def test_raw_graph_enforces_inner_parent_recursion_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    parent_calls = 0

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        nonlocal parent_calls
        if "run_subagent" not in names:
            return AIMessage(content="child finished")
        parent_calls += 1
        return _call(
            "run_subagent",
            {"agent_name": "research", "task": "repeat", "context": ""},
            "repeat-call",
        )

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond, agent_max_iterations=1)
    with pytest.raises(GraphRecursionError):
        await asyncio.wait_for(
            bundle.agent.ainvoke({"messages": [HumanMessage(content="loop forever")]}),
            timeout=5,
        )
    assert parent_calls <= 5


@pytest.mark.asyncio
async def test_child_call_budget_is_independent_of_parent_recursion_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def read_lines() -> str:
        """Return one small research observation."""
        return "observation"

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            completed = sum(isinstance(message, ToolMessage) for message in messages)
            if completed < 3:
                return _call("read_lines", {}, f"research-{completed}")
            return AIMessage(content="three observations completed")
        return _relay(messages, names)

    bundle = await _bundle(
        monkeypatch,
        tmp_path,
        respond=respond,
        tools=[StructuredTool.from_function(read_lines)],
        agent_max_iterations=1,
        subagent_max_model_calls=6,
    )
    result = json.loads(await bundle.ask("delegate a longer investigation"))
    assert result["status"] == "completed"
    assert result["model_calls"] == 4
    assert result["tool_calls"] == 3


@pytest.mark.asyncio
async def test_make_graph_stream_preserves_parent_messages_and_delegation_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = await _bundle(monkeypatch, tmp_path)

    async def build() -> react_agent.AgentBundle:
        return bundle

    monkeypatch.setattr(graph_entrypoint, "build_agent", build)
    graph = await graph_entrypoint.make_graph()
    states = [
        state
        async for state in graph.astream(
            {"messages": [HumanMessage(content="stream request", id="original-user")]},
            stream_mode="values",
        )
    ]
    messages = states[-1]["messages"]
    assert sum(message.id == "original-user" for message in messages) == 1
    assert len([message for message in messages if isinstance(message, HumanMessage)]) == 1
    assert json.loads(messages[-1].content)["status"] == "completed"
    results = [message for message in messages if isinstance(message, ToolMessage)]
    assert len(results) == 1
    assert results[0].tool_call_id == "same-call-id"


@pytest.mark.asyncio
async def test_host_checkpointer_does_not_persist_child_conversation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" in names and not isinstance(messages[-1], ToolMessage):
            return _call(
                "run_subagent",
                {"agent_name": "research", "task": "PRIVATE_CHILD_TASK", "context": ""},
                "checkpoint-call",
            )
        return _relay(messages, names)

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond)
    host = StateGraph(MessagesState)
    host.add_node("chat", bundle.agent)
    host.add_edge(START, "chat")
    host.add_edge("chat", END)
    saver = InMemorySaver()
    graph = host.compile(checkpointer=saver)
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="checkpoint parent")]},
        config={"configurable": {"thread_id": "host-thread"}},
    )
    assert json.loads(result["messages"][-1].content)["status"] == "completed"
    checkpoints = list(saver.list(None))
    assert checkpoints
    saved_human_messages = [
        message
        for checkpoint in checkpoints
        for message in checkpoint.checkpoint["channel_values"].get("messages", [])
        if isinstance(message, HumanMessage)
    ]
    assert saved_human_messages
    assert all(message.content == "checkpoint parent" for message in saved_human_messages)


@pytest.mark.asyncio
async def test_parallel_children_respect_ceiling_and_preserve_tool_call_pairing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    labels = ("first", "second", "third")
    started = {label: asyncio.Event() for label in labels}
    release = {label: asyncio.Event() for label in labels}
    finished: list[str] = []
    active = 0
    peak = 0

    async def read_lines(label: str) -> str:
        """Wait for a controlled source result."""
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        started[label].set()
        try:
            await release[label].wait()
            finished.append(label)
            return label
        finally:
            active -= 1

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            if isinstance(messages[-1], ToolMessage):
                return AIMessage(content=str(messages[-1].content))
            return _call("read_lines", {"label": _user_text(messages)}, "read-label")
        if isinstance(messages[-1], ToolMessage):
            results = [
                {"call_id": message.tool_call_id, **json.loads(message.content)}
                for message in messages
                if isinstance(message, ToolMessage)
            ]
            return AIMessage(content=json.dumps(results))
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "run_subagent",
                    "args": {"agent_name": "research", "task": label},
                    "id": f"delegate-{label}",
                }
                for label in labels
            ],
        )

    bundle = await _bundle(
        monkeypatch,
        tmp_path,
        respond=respond,
        tools=[StructuredTool.from_function(coroutine=read_lines)],
        subagent_max_runs=3,
        subagent_max_concurrency=2,
    )
    task = asyncio.create_task(bundle.ask("Run independent investigations"))
    try:
        await asyncio.wait_for(
            asyncio.gather(started["first"].wait(), started["second"].wait()), timeout=5
        )
        assert not started["third"].is_set()
        release["second"].set()
        await asyncio.wait_for(started["third"].wait(), timeout=5)
        assert not task.done()
        release["third"].set()
        release["first"].set()
        results = json.loads(await asyncio.wait_for(task, timeout=5))
    finally:
        for event in release.values():
            event.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert peak == 2
    assert active == 0
    assert finished[0] == "second"
    assert [result["call_id"] for result in results] == [f"delegate-{label}" for label in labels]
    assert [result["output"] for result in results] == list(labels)
    assert all(result["status"] == "completed" for result in results)


@pytest.mark.asyncio
@pytest.mark.parametrize("model_limit,tool_limit", [(1, 3), (3, 1)])
async def test_child_call_limits_stop_dispatch_before_overspending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, model_limit: int, tool_limit: int
) -> None:
    reads: list[str] = []
    model_calls = 0

    async def read_lines(label: str) -> str:
        """Record a source read."""
        reads.append(label)
        return label

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        nonlocal model_calls
        if "run_subagent" in names:
            return _relay(messages, names)
        model_calls += 1
        if isinstance(messages[-1], ToolMessage):
            return AIMessage(content="Research finished")
        return AIMessage(
            content="",
            tool_calls=[
                {"name": "read_lines", "args": {"label": label}, "id": label}
                for label in ("first", "second")
            ],
        )

    bundle = await _bundle(
        monkeypatch,
        tmp_path,
        respond=respond,
        tools=[StructuredTool.from_function(coroutine=read_lines)],
        subagent_max_model_calls=model_limit,
        subagent_max_tool_calls=tool_limit,
    )
    result = json.loads(await bundle.ask("Read the sources"))
    assert result["status"] == "budget_exceeded"
    assert model_calls == result["model_calls"] == min(model_limit, 2)
    assert len(reads) == result["tool_calls"] == min(tool_limit, 2)


@pytest.mark.asyncio
async def test_failed_child_preserves_sibling_and_consumes_attempt_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            if _user_text(messages) == "fail":
                raise RuntimeError("provider token=TEST_SECRET")
            return AIMessage(content="successful research")
        results = [
            json.loads(message.content) for message in messages if isinstance(message, ToolMessage)
        ]
        if len(results) == 3:
            return AIMessage(content=json.dumps(results))
        tasks = ("fail", "succeed") if not results else ("retry",)
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "run_subagent",
                    "args": {"agent_name": "research", "task": task},
                    "id": f"delegate-{task}",
                }
                for task in tasks
            ],
        )

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond, subagent_max_runs=2)
    results = json.loads(await bundle.ask("Run both investigations"))
    assert [result["status"] for result in results] == [
        "failed",
        "completed",
        "budget_exceeded",
    ]
    assert results[1]["output"] == "successful research"
    assert "TEST_SECRET" not in json.dumps(results)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_name,task",
    [("x" * 129, "job"), ("unknown", "job"), ("research", " "), ("research", "too long")],
)
async def test_invalid_delegation_returns_bounded_rejection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, agent_name: str, task: str
) -> None:
    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        assert "run_subagent" in names, "rejected inputs must not start a child"
        if isinstance(messages[-1], ToolMessage):
            assert messages[-1].status == "error"
            return AIMessage(content=str(messages[-1].content))
        return _call("run_subagent", {"agent_name": agent_name, "task": task}, "invalid-request")

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond, subagent_max_input_chars=3)
    result = json.loads(await bundle.ask("Reject invalid requests"))
    assert result["status"] == "rejected"
    assert len(result["agent_name"]) <= 128
    assert result["output"] == ""
    assert result["model_calls"] == result["tool_calls"] == 0


@pytest.mark.asyncio
async def test_child_does_not_inherit_parent_configurable_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[dict[str, Any]] = []
    model_metadata: list[dict[str, Any]] = []

    class MetadataObserver(BaseCallbackHandler):
        def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
            model_metadata.append(dict(kwargs.get("metadata") or {}))

    async def read_lines(runtime: ToolRuntime[Any]) -> str:
        """Observe child configuration without returning it to the model."""
        observed.append(dict(runtime.config))
        return "read completed"

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            if isinstance(messages[-1], ToolMessage):
                return AIMessage(content="finished")
            return _call("read_lines", {}, "inspect-config")
        return _relay(messages, names)

    bundle = await _bundle(
        monkeypatch,
        tmp_path,
        respond=respond,
        tools=[StructuredTool.from_function(coroutine=read_lines)],
    )
    result = await bundle.agent.ainvoke(
        {"messages": [HumanMessage(content="inspect child isolation")]},
        config={
            "configurable": {"thread_id": "parent-thread", "parent_only": "private"},
            "metadata": {"caller_only": "PRIVATE_METADATA"},
            "callbacks": [MetadataObserver()],
        },
    )
    assert json.loads(result["messages"][-1].content)["status"] == "completed"
    assert len(observed) == 1
    assert "parent_only" not in observed[0]["configurable"]
    assert observed[0]["configurable"].get("thread_id") != "parent-thread"
    child_metadata = [item for item in model_metadata if item.get("data_agent_depth") == 1]
    assert child_metadata
    for metadata in [observed[0]["metadata"], *child_metadata]:
        assert "caller_only" not in metadata
        assert "parent_only" not in metadata
        assert metadata.get("thread_id") != "parent-thread"
    root_metadata = [item for item in model_metadata if item.get("data_agent_depth") == 0]
    assert root_metadata
    assert all(item["caller_only"] == "PRIVATE_METADATA" for item in root_metadata)


@pytest.mark.asyncio
async def test_trace_identifies_children_without_exposing_delegated_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private = "PRIVATE_CONTEXT_MUST_NOT_ENTER_TRACE"

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" in names and not isinstance(messages[-1], ToolMessage):
            return _call(
                "run_subagent",
                {"agent_name": "research", "task": "research", "context": private},
                "trace-call",
            )
        return _relay(messages, names)

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond)
    sink = InMemoryTraceSink()
    result = json.loads(await bundle.ask("trace the work", trace_sinks=[sink]))
    assert result["status"] == "completed"
    serialized = "\n".join(event.model_dump_json() for event in sink.events)
    assert private not in serialized
    child_events = [event for event in sink.events if event.agent_depth == 1]
    assert child_events
    assert {event.agent_id for event in child_events} == {result["child_id"]}
    assert all(event.parent_agent_id for event in child_events)
    starts = [event for event in sink.events if event.event_type is EventType.MODEL_STARTED]
    assert len(starts) == 3
    assert len({event.callback_run_id for event in starts}) == 3


@pytest.mark.asyncio
async def test_invalid_child_tool_call_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            return AIMessage(
                content="I will read the file.",
                invalid_tool_calls=[
                    {"name": "read_lines", "args": "{", "id": "invalid-call", "error": "bad JSON"}
                ],
            )
        return _relay(messages, names)

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond)
    result = json.loads(await bundle.ask("read a source"))
    assert result["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["ask", "raw", "stream"])
async def test_cancellation_stops_running_child_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entrypoint: str
) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def wait_for_source() -> str:
        """Wait until the caller cancels this source read."""
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
        return "unreachable"

    tool = StructuredTool.from_function(coroutine=wait_for_source, name="read_lines")

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            return _call("read_lines", {}, "blocking-read")
        return _relay(messages, names)

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond, tools=[tool])

    async def invoke() -> None:
        if entrypoint == "ask":
            await bundle.ask("cancel child")
        elif entrypoint == "raw":
            await bundle.agent.ainvoke({"messages": [HumanMessage(content="cancel child")]})
        else:
            async for _ in bundle.agent.astream(
                {"messages": [HumanMessage(content="cancel child")]}, stream_mode="updates"
            ):
                pass

    task = asyncio.create_task(invoke())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(stopped.wait(), timeout=5)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_closing_stream_cancels_child_after_progress_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stopped = asyncio.Event()

    async def read_lines() -> str:
        """Publish progress and then wait for cancellation."""
        get_stream_writer()({"phase": "child_running"})
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
        return "unreachable"

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            return _call("read_lines", {}, "stream-read")
        return _relay(messages, names)

    bundle = await _bundle(
        monkeypatch,
        tmp_path,
        respond=respond,
        tools=[StructuredTool.from_function(coroutine=read_lines)],
    )
    stream = bundle.agent.astream(
        {"messages": [HumanMessage(content="stream child progress")]},
        stream_mode="custom",
        subgraphs=True,
    )
    try:
        event = await asyncio.wait_for(anext(stream), timeout=5)
        assert "child_running" in str(event)
    finally:
        await stream.aclose()
    await asyncio.wait_for(stopped.wait(), timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,expected_status", [("notes.txt", "completed"), ("../outside.txt", "failed")]
)
async def test_delegated_source_reads_keep_existing_containment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: str, expected_status: str
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "notes.txt").write_text("inside source", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("OUTSIDE_SECRET", encoding="utf-8")

    def read_lines(path: str, start: int, end: int) -> str:
        """Read lines under the configured source root."""
        return str(read_lines_data(source_root, path, start, end))

    tool = StructuredTool.from_function(read_lines)

    def respond(messages: list[BaseMessage], names: tuple[str, ...]) -> AIMessage:
        if "run_subagent" not in names:
            if isinstance(messages[-1], ToolMessage):
                return AIMessage(content=str(messages[-1].content))
            return _call("read_lines", {"path": path, "start": 1, "end": 1}, "source-read")
        return _relay(messages, names)

    bundle = await _bundle(monkeypatch, tmp_path, respond=respond, tools=[tool])
    result = json.loads(await bundle.ask("read the source"))
    assert result["status"] == expected_status
    assert "OUTSIDE_SECRET" not in json.dumps(result)
    if expected_status == "completed":
        assert "inside source" in result["output"]
