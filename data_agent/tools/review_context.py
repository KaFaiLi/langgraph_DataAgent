"""Run-scoped context for controlled-review use of shared tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from data_agent.tools.source_tools import SourcePathError, resolve_source_path
from data_agent.review.domain.source import SourceManifest


@dataclass(frozen=True)
class ToolContext:
    """The immutable source scope and workspace assigned to one review run."""

    source_root: Path
    workspace_root: Path
    manifest: SourceManifest


def source_file(ctx: ToolContext, relative_path: str) -> Path:
    """Resolve a manifest source through the same guard used by MCP tools."""
    try:
        ctx.manifest.by_path(relative_path)
        return resolve_source_path(ctx.source_root, relative_path)
    except (KeyError, SourcePathError) as exc:
        raise SourcePathError(
            f"source is outside the review manifest: {relative_path!r}"
        ) from exc
