"""Thin MCP registration for shared host-bound review capabilities."""

from __future__ import annotations

from fastmcp import FastMCP

from data_agent.config import Settings
from data_agent.skills.review import discover_skills
from data_agent.tools.review_runs import ReviewWorkspace, build_review_run_tools


def register(mcp: FastMCP, settings: Settings) -> None:
    """Use identical operations for local and MCP access; no orchestration lives here."""
    definitions = {
        definition.name: definition for definition in discover_skills(settings.skills_path)
    }
    workspace = ReviewWorkspace(
        settings.source_path,
        settings.review_workspace_path,
        definitions,
        settings.review_run_id or None,
        settings.review_assignment_id or None,
    )
    for tool in build_review_run_tools(workspace):
        mcp.tool(tool.func, name=tool.name, description=tool.description)
