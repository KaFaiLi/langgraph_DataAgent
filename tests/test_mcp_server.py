"""End-to-end-ish test: spawn the real MCP server over stdio and list tools.

No LLM/credentials needed -- this validates the server + adapter wiring.
"""

from pathlib import Path

import pytest

from data_agent.agent.react_agent import build_mcp_client
from data_agent.config import Settings
from data_agent.tool_results import tool_json

MIGRATED_TOOL_CALLS = {
    "list_sources": {"max_sources": 10},
    "search_text": {"pattern": "alpha"},
    "grep": {
        "pattern": "def build_server",
        "path": "data_agent/mcp_server/server.py",
        "include": "**/*.py",
        "max_results": 2,
    },
    "read_lines": {"path": "notes.md", "start": 1, "end": 2},
    "read_document_section": {"locator": "source://sales.csv#rows=2:2"},
    "inspect_table": {"path": "sales.csv"},
    "read_rows": {"path": "sales.csv", "start": 1, "end": 2},
    "describe_columns": {"path": "sales.csv"},
    "group_by": {
        "path": "sales.csv",
        "group_columns": ["desk"],
        "agg_column": "amount",
    },
    "join_tables": {"left": "sales.csv", "right": "sales.csv", "on": ["desk"]},
    "run_duckdb_query": {"sql": "SELECT * FROM src_sales_csv"},
    "zscore": {"values": [1, 2, 3]},
    "rolling_mean": {"values": [1, 2, 3], "window": 2},
    "rolling_std": {"values": [1, 2, 3], "window": 2},
    "rolling_quantile": {"values": [1, 2, 3], "window": 2, "q": 0.5},
    "percent_change": {"values": [1, 2, 3]},
    "outlier_detection": {"values": [1, 2, 3]},
    "change_point_candidates": {"values": [1, 2, 3], "window": 2},
    "pearson_correlation": {"a": [1, 2, 3], "b": [1, 2, 3]},
    "trend_analysis": {"values": [1, 2, 3]},
    "period_comparison": {"values": [1, 2, 3], "split": 1},
    "run_python_analysis": {"code": "print(1)"},
}
MIGRATED_TOOL_NAMES = frozenset(MIGRATED_TOOL_CALLS)
TEMPLATE_TOOL_NAMES = frozenset(
    {
        "ping",
        "server_time",
        "add",
        "search_items",
        "estimate_token_cost",
        "inspect_payload",
        "generate_filler",
    }
)


@pytest.mark.asyncio
async def test_stdio_server_exposes_tools():
    settings = Settings(mcp_transport="stdio")
    client = build_mcp_client(settings)
    tools = await client.get_tools()
    names = {t.name for t in tools}

    expected = MIGRATED_TOOL_NAMES | TEMPLATE_TOOL_NAMES
    assert names == expected, (
        f"tool catalog mismatch; missing={sorted(expected - names)}, extra={sorted(names - expected)}"
    )


@pytest.mark.asyncio
async def test_ping_tool_returns_pong():
    settings = Settings(mcp_transport="stdio")
    client = build_mcp_client(settings)
    tools = await client.get_tools()
    ping = next(t for t in tools if t.name == "ping")
    result = await ping.ainvoke({})
    assert "pong" in str(result)


@pytest.mark.asyncio
async def test_grep_tool_finds_project_source():
    settings = Settings(mcp_transport="stdio")
    client = build_mcp_client(settings)
    tools = await client.get_tools()
    grep = next(t for t in tools if t.name == "grep")

    result = tool_json(
        await grep.ainvoke({"pattern": "def build_server", "include": "**/*.py", "max_results": 5})
    )

    assert isinstance(result, dict)
    assert result["count"] >= 1
    assert any(match["path"].endswith("mcp_server/server.py") for match in result["matches"])


@pytest.mark.asyncio
async def test_all_migrated_tools_are_exposed_and_callable(tmp_path: Path):
    from data_agent.config import Settings
    from data_agent.mcp_server.server import build_server

    (tmp_path / "notes.md").write_text("alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "sales.csv").write_text("desk,amount\nA,10\nB,5\n", encoding="utf-8")
    server = build_server(Settings(source_root=str(tmp_path)))
    tools = {tool.name for tool in await server.list_tools()}

    assert MIGRATED_TOOL_NAMES == frozenset(MIGRATED_TOOL_CALLS)
    assert tools == MIGRATED_TOOL_NAMES | TEMPLATE_TOOL_NAMES
    for name, arguments in MIGRATED_TOOL_CALLS.items():
        result = await server.call_tool(name, arguments)
        assert not result.is_error, f"{name} returned an MCP error: {result}"
