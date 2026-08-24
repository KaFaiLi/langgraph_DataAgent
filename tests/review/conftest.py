"""Shared fixtures for the ported controlled-review behavior suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_agent.review.ingestion.catalog import build_catalog
from data_agent.tools.review_context import ToolContext
from tests.review.fixtures.builder import make_risky_tree


@pytest.fixture()
def tool_ctx(tmp_path: Path) -> ToolContext:
    source_root = tmp_path / "source"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    make_risky_tree(source_root)
    return ToolContext(
        source_root=source_root,
        workspace_root=workspace_root,
        manifest=build_catalog(source_root),
    )
