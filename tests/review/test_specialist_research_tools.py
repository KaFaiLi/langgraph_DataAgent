from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.tools import ToolException

from data_agent.review.domain.source import Source, SourceManifest, SourceType
from data_agent.tools.review_context import ToolContext
from data_agent.tools.research import build_research_tools


def _context(tmp_path: Path) -> ToolContext:
    source = tmp_path / "sources"
    source.mkdir()
    (source / "assigned.csv").write_text("desk,value\nA,1\nB,2\n", encoding="utf-8")
    (source / "other.csv").write_text("desk,value\nX,99\n", encoding="utf-8")
    manifest = SourceManifest(
        sources=[
            Source(
                source_id="SRC-001",
                path="assigned.csv",
                source_type=SourceType.CSV,
                sha256="a" * 64,
                size_bytes=20,
            ),
            Source(
                source_id="SRC-002",
                path="other.csv",
                source_type=SourceType.CSV,
                sha256="b" * 64,
                size_bytes=20,
            ),
        ]
    )
    return ToolContext(source_root=source, workspace_root=tmp_path / "workspace", manifest=manifest)


def test_research_tools_trace_results_and_reject_unassigned_sources(tmp_path: Path) -> None:
    trace: list[dict] = []
    tools = {
        tool.name: tool
        for tool in build_research_tools(
            _context(tmp_path), ["assigned.csv"], trace, max_calls=4
        )
    }

    inspected = tools["inspect_table"].invoke(
        {"path": "assigned.csv", "preview_rows": 2}
    )
    with pytest.raises(ToolException, match="outside this specialist scope"):
        tools["inspect_table"].invoke({"path": "other.csv"})

    assert '"row_count": 2' in inspected
    assert len(trace) == 1
    assert trace[0]["tool"] == "inspect_table"
    assert len(trace[0]["result_sha256"]) == 64


def test_research_tool_budget_is_hard_capped(tmp_path: Path) -> None:
    trace: list[dict] = []
    tool = {
        item.name: item
        for item in build_research_tools(
            _context(tmp_path), ["assigned.csv"], trace, max_calls=1
        )
    }["list_assigned_sources"]

    assert "SRC-001" in tool.invoke({})
    with pytest.raises(ToolException, match="budget exhausted"):
        tool.invoke({})
    assert len(trace) == 1
