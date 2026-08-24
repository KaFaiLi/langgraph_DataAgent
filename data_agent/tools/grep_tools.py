"""A bounded, repository-local grep implementation.

The scanner is deliberately small and dependency-free. It is a good default for
one local workspace, while its explicit limits and structured result make it
safe to replace with ripgrep or an indexed backend when search volume grows.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from data_agent.config import REPO_ROOT

# Keep the demo useful on source trees without walking common generated output.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".langgraph_api",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)
SKIP_SUFFIXES = frozenset({".key", ".pem", ".p12", ".pfx"})
MAX_FILE_BYTES = 1_000_000
MAX_LINE_CHARS = 500
DEFAULT_MAX_RESULTS = 50
DEFAULT_MAX_FILES = 10_000


def _resolve_within_root(root: Path, requested: str) -> Path:
    """Resolve a user path and reject absolute or escaping paths."""
    if not requested.strip():
        raise ToolError("path must not be empty.")

    path = Path(requested)
    if path.is_absolute() or path.drive or path.root != Path().root:
        raise ToolError("path must be relative to the workspace root.")

    root = root.resolve()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ToolError("path must stay inside the workspace root.") from exc

    if not target.exists():
        raise ToolError(f"path does not exist in the workspace: {requested!r}")
    return target


def _matches_include(file_path: Path, root: Path, include: str) -> bool:
    """Apply a POSIX-style glob to a path relative to ``root``."""
    if not include or include in {"*", "**", "**/*"}:
        return True

    relative = PurePosixPath(file_path.relative_to(root).as_posix())
    if relative.match(include):
        return True
    # pathlib's ``**/*.py`` does not match a root-level ``file.py`` on all
    # supported Python versions; treating the prefix as optional is friendlier.
    return include.startswith("**/") and relative.match(include[3:])


def _is_searchable(file_path: Path) -> bool:
    """Return whether a file is safe and useful to inspect."""
    name = file_path.name.lower()
    return not (
        name.startswith(".env")
        or file_path.suffix.lower() in SKIP_SUFFIXES
        or file_path.is_symlink()
    )


def _iter_files(target: Path, root: Path, include: str):
    """Yield deterministic, searchable files below a file or directory."""
    if target.is_file():
        if _is_searchable(target) and _matches_include(target, root, include):
            yield target
        return

    for directory, dirnames, filenames in os.walk(target, topdown=True, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            candidate = Path(directory) / filename
            if _is_searchable(candidate) and _matches_include(candidate, root, include):
                yield candidate


def search_files(
    root: Path,
    pattern: str,
    *,
    path: str = ".",
    include: str = "**/*",
    max_results: int = DEFAULT_MAX_RESULTS,
    max_files: int = DEFAULT_MAX_FILES,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Search text files under ``root`` and return compact structured matches."""
    if not pattern.strip():
        raise ToolError("pattern must not be empty.")
    if max_results < 1:
        raise ToolError("max_results must be at least 1.")
    if max_files < 1:
        raise ToolError("max_files must be at least 1.")

    try:
        expression = re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)
    except re.error as exc:
        raise ToolError(f"invalid regular expression: {exc}") from exc

    root = root.resolve()
    target = _resolve_within_root(root, path)
    matches: list[dict[str, Any]] = []
    files_scanned = 0
    skipped_files = 0
    scan_truncated = False

    # ponytail: linear scan is enough for this demo; use ripgrep or an index when
    # workspace size or query volume makes the bounded scan measurably too slow.
    for file_path in _iter_files(target, root, include):
        if files_scanned >= max_files:
            scan_truncated = True
            break
        files_scanned += 1

        try:
            if file_path.stat().st_size > MAX_FILE_BYTES:
                skipped_files += 1
                continue
            with file_path.open("rb") as raw:
                if b"\x00" in raw.read(4096):
                    skipped_files += 1
                    continue
            with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not expression.search(line):
                        continue
                    text = line.rstrip("\r\n")
                    if len(text) > MAX_LINE_CHARS:
                        text = text[: MAX_LINE_CHARS - 3] + "..."
                    matches.append(
                        {
                            "path": file_path.relative_to(root).as_posix(),
                            "line": line_number,
                            "text": text,
                        }
                    )
                    if len(matches) >= max_results:
                        scan_truncated = True
                        break
        except OSError:
            # A file can disappear or become unreadable during a workspace scan.
            skipped_files += 1

        if scan_truncated:
            break

    return {
        "pattern": pattern,
        "matches": matches,
        "count": len(matches),
        "truncated": scan_truncated,
        "files_scanned": files_scanned,
        "skipped_files": skipped_files,
    }


def register(mcp: FastMCP, root: Path | None = None) -> None:
    """Attach the repository-local grep tool to the shared MCP server."""
    search_root = (root or REPO_ROOT).resolve()

    @mcp.tool
    def grep(
        pattern: Annotated[
            str,
            Field(description="Regular expression to search for in text files."),
        ],
        path: Annotated[
            str,
            Field(description="Relative file or directory inside the workspace."),
        ] = ".",
        include: Annotated[
            str,
            Field(description="Optional relative glob, such as '**/*.py'."),
        ] = "**/*",
        max_results: Annotated[
            int,
            Field(ge=1, le=200, description="Maximum matches to return (1-200)."),
        ] = DEFAULT_MAX_RESULTS,
        max_files: Annotated[
            int,
            Field(ge=1, le=100_000, description="Maximum files to inspect."),
        ] = DEFAULT_MAX_FILES,
        case_sensitive: Annotated[
            bool,
            Field(description="Whether regular-expression matching is case-sensitive."),
        ] = False,
    ) -> dict[str, Any]:
        """Search workspace text files and return matching paths, lines, and text.

        Use this for quick source-code or configuration searches. Paths are
        workspace-relative; generated directories, likely secret files, binary
        files, oversized files, and matches beyond the limits are skipped.
        Results include `truncated`, `files_scanned`, and `skipped_files` so a
        caller can narrow `path`/`include` or raise a limit when needed.
        """
        return search_files(
            search_root,
            pattern,
            path=path,
            include=include,
            max_results=max_results,
            max_files=max_files,
            case_sensitive=case_sensitive,
        )
