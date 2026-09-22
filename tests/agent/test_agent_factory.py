"""Bootstrap and capability-boundary coverage for conversational agents."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, StructuredTool, ToolException

from data_agent.agent import react_agent
from data_agent.agent.subagents.contracts import (
    DelegationPolicy,
    DelegationResult,
    RunScope,
    SubagentSpec,
)
from data_agent.agent.subagents.registry import (
    DEFAULT_RESEARCH_SPEC,
    SubagentRegistry,
    SubagentSpecError,
    validate_tool_names,
)
from data_agent.agent.subagents.runner import DelegationRunner
from data_agent.config import Settings
from data_agent.skills.loader import Skill


class _NoopModel(BaseChatModel):
    """A graph-buildable model that never contacts a provider."""

    @property
    def _llm_type(self) -> str:
        return "bootstrap-test-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        del tools, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


class _FakeMCPClient:
    def __init__(self, tools: Sequence[BaseTool]) -> None:
        self.tools = list(tools)

    async def get_tools(self) -> list[BaseTool]:
        return self.tools


def _tool(name: str) -> BaseTool:
    def tool(value: str = "") -> str:
        return value

    return StructuredTool.from_function(tool, name=name, description=f"Test tool {name}.")


def _research_tools() -> list[BaseTool]:
    return [_tool(name) for name in DEFAULT_RESEARCH_SPEC.tool_names]


def _skill(name: str, body: str) -> Skill:
    return Skill(
        name=name,
        description=f"{name} description",
        body=body,
        path=Path(name) / "SKILL.md",
    )


def _patch_mcp(monkeypatch: pytest.MonkeyPatch, tools: Sequence[BaseTool]) -> None:
    client = _FakeMCPClient(tools)
    monkeypatch.setattr(react_agent, "build_mcp_client", lambda settings: client)


def _settings(tmp_path: Path, *, enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        subagents_enabled=enabled,
        source_root=tmp_path,
        skills_dir=str(tmp_path),
    )


@pytest.mark.asyncio
async def test_disabled_bootstrap_has_no_delegation_and_keeps_extra_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_tool = _tool("read_lines")
    extra_tool = _tool("test_extra")
    _patch_mcp(monkeypatch, [source_tool])
    provider_calls: list[object] = []

    def fail_provider(*args: Any, **kwargs: Any) -> Any:
        provider_calls.append((args, kwargs))
        raise AssertionError("injected model should bypass provider construction")

    monkeypatch.setattr(react_agent, "get_chat_model", fail_provider)
    bundle = await react_agent.build_agent(
        _settings(tmp_path, enabled=False),
        model=_NoopModel(),
        extra_tools=[extra_tool],
    )

    assert [tool.name for tool in bundle.all_tools] == ["read_lines", "test_extra"]
    assert bundle.delegation_tool is None
    assert bundle.delegation_policy is not None
    assert bundle.delegation_policy.enabled is False
    assert "DELEGATION" not in bundle.system_prompt
    assert provider_calls == []


@pytest.mark.asyncio
async def test_bootstrap_rejects_duplicate_root_tool_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_mcp(monkeypatch, [_tool("read_lines")])

    with pytest.raises(ValueError, match="duplicate tool names: read_lines"):
        await react_agent.build_agent(
            _settings(tmp_path, enabled=False),
            model=_NoopModel(),
            extra_tools=[_tool("read_lines")],
        )


def test_default_research_profile_has_exact_guarded_capabilities() -> None:
    registry = SubagentRegistry.build(None, tools=_research_tools(), skills=[])

    assert registry.specs == (DEFAULT_RESEARCH_SPEC,)
    assert registry.specs[0].tool_names == (
        "list_sources",
        "search_text",
        "read_lines",
        "read_document_section",
        "inspect_table",
        "read_rows",
    )
    assert registry.specs[0].skill_names == ()
    assert "run_subagent" not in registry.specs[0].tool_names
    assert "load_skill" not in registry.specs[0].tool_names


def test_registry_rejects_unknown_tool_and_skill_names() -> None:
    with pytest.raises(SubagentSpecError, match="unavailable tools: missing_tool"):
        SubagentRegistry.build(
            [SubagentSpec(name="research", tool_names=("missing_tool",))],
            tools=[_tool("read_lines")],
            skills=[],
        )

    with pytest.raises(SubagentSpecError, match="unavailable skills: missing_skill"):
        SubagentRegistry.build(
            [
                SubagentSpec(
                    name="research", tool_names=("read_lines",), skill_names=("missing_skill",)
                )
            ],
            tools=[_tool("read_lines")],
            skills=[],
        )


@pytest.mark.parametrize(
    ("tool_name", "message"),
    [
        ("run_subagent", "cannot include run_subagent"),
        ("load_skill", "must use skill_names"),
    ],
)
def test_registry_rejects_root_only_tool_selection(tool_name: str, message: str) -> None:
    with pytest.raises(SubagentSpecError, match=message):
        SubagentRegistry.build(
            [SubagentSpec(name="research", tool_names=(tool_name,))],
            tools=[_tool(tool_name)],
            skills=[],
        )


@pytest.mark.asyncio
async def test_child_graph_exposes_only_named_skill() -> None:
    named = _skill("named", "NAMED_INSTRUCTIONS")
    other = _skill("other", "OTHER_INSTRUCTIONS")
    read_tool = _tool("read_lines")
    registry = SubagentRegistry.build(
        [
            SubagentSpec(
                name="research",
                tool_names=("read_lines",),
                skill_names=("named",),
            )
        ],
        tools=[read_tool],
        skills=[named, other],
    )
    captured: dict[str, Any] = {}

    class _CompletedGraph:
        async def ainvoke(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"messages": [AIMessage(content="child complete")]}

    def capture_graph(model: Any, tools: Sequence[BaseTool], **kwargs: Any) -> _CompletedGraph:
        del model
        captured["tools"] = list(tools)
        captured["kwargs"] = kwargs
        return _CompletedGraph()

    runner = DelegationRunner(
        model=_NoopModel(),
        tools=[read_tool],
        skills=[named, other],
        registry=registry,
        policy=DelegationPolicy(enabled=True),
        graph_builder=capture_graph,
    )
    result = await runner.run(
        {"agent_name": "research", "task": "use the named playbook", "context": ""},
        scope=RunScope(policy=DelegationPolicy(enabled=True)),
    )

    assert isinstance(result, DelegationResult)
    assert result.status == "completed"
    child_tools = captured["tools"]
    assert [tool.name for tool in child_tools] == ["read_lines", "load_skill"]
    skill_loader = child_tools[-1]
    assert "NAMED_INSTRUCTIONS" in skill_loader.invoke({"name": "named"})
    with pytest.raises(ToolException, match="Unknown skill 'other'"):
        skill_loader.invoke({"name": "other"})


def test_validate_tool_names_rejects_collisions_before_graph_creation() -> None:
    with pytest.raises(ValueError, match="duplicate tool names: duplicate"):
        validate_tool_names([_tool("duplicate"), _tool("duplicate")])
