"""Real stdio MCP coverage for the default conversational research child."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from data_agent.agent import react_agent
from data_agent.config import Settings


def _tool_call(name: str, arguments: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": arguments, "id": call_id}])


class MCPResearchModel(BaseChatModel):
    """Deterministic parent/child routing model with no provider dependency."""

    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "stdio-mcp-test-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        del kwargs
        return self.bind(bound_tool_names=tuple(tool.name for tool in tools))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager
        self.calls += 1
        names = tuple(kwargs.get("bound_tool_names", ()))
        last = messages[-1]

        if "run_subagent" in names:
            if isinstance(last, ToolMessage):
                # The parent receives the bounded JSON result of its delegation
                # tool and returns it as its deterministic summary.
                response = str(last.content)
            else:
                response = _tool_call(
                    "run_subagent",
                    {
                        "agent_name": "research",
                        "task": "Read notes.txt and report its contents.",
                        "context": "",
                    },
                    "parent-delegation",
                )
        elif isinstance(last, ToolMessage):
            response = AIMessage(content=f"Child read result: {last.content}")
        else:
            response = _tool_call(
                "read_lines",
                {"path": "notes.txt", "start": 1, "end": 2},
                "child-read-lines",
            )

        if isinstance(response, str):
            response = AIMessage(content=response)
        return ChatResult(generations=[ChatGeneration(message=response)])


@pytest.mark.asyncio
async def test_stdio_mcp_research_child_reads_source_without_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_root = tmp_path
    (source_root / "notes.txt").write_text("alpha finding\nbeta finding\n", encoding="utf-8")
    empty_skills = tmp_path / "empty-skills"
    empty_skills.mkdir()

    def fail_provider_call(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the injected deterministic model should bypass provider setup")

    monkeypatch.setattr(react_agent, "get_chat_model", fail_provider_call)
    monkeypatch.setenv("FASTMCP_CHECK_FOR_UPDATES", "off")
    monkeypatch.setenv("FASTMCP_SHOW_SERVER_BANNER", "false")
    model = MCPResearchModel()
    settings = Settings(
        _env_file=None,
        subagents_enabled=True,
        source_root=source_root,
        skills_dir=str(empty_skills),
        mcp_transport="stdio",
    )

    bundle = await react_agent.build_agent(settings, model=model)

    mcp_names = {tool.name for tool in bundle.mcp_tools}
    root_names = {tool.name for tool in bundle.all_tools}
    assert "read_lines" in mcp_names
    assert "run_subagent" not in mcp_names
    assert "run_subagent" in root_names

    result = json.loads(await bundle.ask("Delegate reading the notes file."))

    assert result["status"] == "completed"
    assert result["agent_name"] == "research"
    assert "alpha finding" in result["output"]
    assert "beta finding" in result["output"]
    assert model.calls >= 4
