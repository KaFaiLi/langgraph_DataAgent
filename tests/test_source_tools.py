"""Focused tests for the configured-root source MCP tool helpers."""

from pathlib import Path

import pytest

from data_agent.tools.source_tools import (
    SourcePathError,
    list_sources_data,
    read_document_section_data,
    read_lines_data,
    resolve_source_path,
    search_text_data,
)


@pytest.fixture()
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "notes.md").write_text(
        "first finding\nsecond finding\nthird finding\n", encoding="utf-8"
    )
    (root / "risk.csv").write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
    return root


def test_list_sources_returns_metadata_and_is_bounded(source_root: Path):
    result = list_sources_data(source_root, max_sources=1)

    assert result["count"] == 1
    assert result["truncated"]
    source = result["sources"][0]
    assert source["path"] == "notes.md"
    assert len(source["sha256"]) == 64
    assert source["line_count"] == 3


def test_search_text_is_source_only_and_bounded(source_root: Path):
    result = search_text_data(source_root, "finding", max_results=1)

    assert result["count"] == 1
    assert result["truncated"]
    assert result["matches"][0] == {"path": "notes.md", "line": 1, "text": "first finding"}


def test_search_text_rejects_escape_and_invalid_regex(source_root: Path):
    with pytest.raises(SourcePathError, match="inside"):
        search_text_data(source_root, "finding", path="../outside")
    with pytest.raises(ValueError, match="invalid regular expression"):
        search_text_data(source_root, "[")


def test_read_lines_is_one_based_and_bounded(source_root: Path):
    assert read_lines_data(source_root, "notes.md", 2, 3) == (
        "line 2: second finding\nline 3: third finding"
    )
    with pytest.raises(ValueError, match="limited"):
        read_lines_data(source_root, "notes.md", 1, 3, max_lines=2)
    with pytest.raises(SourcePathError):
        read_lines_data(source_root, "../notes.md", 1, 1)
    with pytest.raises(ValueError, match="end"):
        read_lines_data(source_root, "notes.md", 1, 4)


def test_read_lines_caps_total_output(source_root: Path):
    long_path = source_root / "long.txt"
    long_path.write_text("".join("x" * 500 + "\n" for _ in range(20)), encoding="utf-8")
    output = read_lines_data(source_root, "long.txt", 1, 20)
    assert len(output) <= 4_000
    assert output.endswith("(truncated)")


def test_read_document_section_reopens_rows_and_lines(source_root: Path):
    assert "row 2: name=alpha, value=1" in read_document_section_data(
        source_root, "source://risk.csv#rows=2:2"
    )
    assert read_document_section_data(source_root, "source://notes.md#lines=1:1") == (
        "line 1: first finding"
    )
    with pytest.raises(SourcePathError):
        read_document_section_data(source_root, "source://../outside.txt#lines=1:1")
    with pytest.raises(ValueError, match="exactly one"):
        read_document_section_data(
            source_root, "source://notes.md#lines=1:1&rows=1:1"
        )
    with pytest.raises(ValueError, match="out of range"):
        read_document_section_data(source_root, "source://risk.csv#rows=2:4")


def test_resolve_source_path_rejects_absolute_and_escape(source_root: Path):
    with pytest.raises(SourcePathError, match="relative"):
        resolve_source_path(source_root, str(source_root / "notes.md"))
    with pytest.raises(SourcePathError, match="inside"):
        resolve_source_path(source_root, "../notes.md")


def test_reads_cannot_bypass_secret_file_filters(source_root: Path):
    (source_root / ".env").write_text("SECRET=do-not-read", encoding="utf-8")
    with pytest.raises(SourcePathError, match="allowed source"):
        resolve_source_path(source_root, ".env")


@pytest.mark.asyncio
async def test_mcp_registration_exposes_all_source_tools(source_root: Path):
    from data_agent.config import Settings
    from data_agent.mcp_server.server import build_server

    server = build_server(Settings(source_root=str(source_root)))
    tools = await server.list_tools()
    assert {"list_sources", "search_text", "read_lines", "read_document_section"} <= {
        tool.name for tool in tools
    }
