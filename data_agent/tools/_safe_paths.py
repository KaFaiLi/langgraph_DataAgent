"""Small path-policy primitives shared by every data-tool caller.

The MCP server binds a root when tools are registered.  Tool callers only ever
provide paths relative to that root; this module is intentionally independent
of the rest of the server so it can also be used by the child-process sandbox.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp.exceptions import ToolError


class SafePathError(ValueError):
    """Raised when a requested path is not within its configured root."""


def resolve_relative(
    root: Path,
    requested: str,
    *,
    must_exist: bool = True,
    file_only: bool = False,
) -> Path:
    """Resolve ``requested`` beneath ``root`` and enforce containment.

    ``Path.resolve`` is used before the containment check, so a symlink inside
    the root cannot be used to reach a file outside it.  Windows drive and UNC
    paths are rejected explicitly even when this function is tested from a
    different platform.
    """

    if not isinstance(requested, str) or not requested.strip():
        raise SafePathError("path must not be empty")
    root = root.resolve()
    raw = requested.replace("\\", "/")
    # ``Path.is_absolute`` handles native paths.  The additional checks make
    # validation deterministic for a Windows-style path on POSIX too.
    path = Path(raw)
    if (
        path.is_absolute()
        or path.drive
        or raw.startswith(("/", "//"))
        or (len(raw) >= 2 and raw[1] == ":")
    ):
        raise SafePathError("path must be relative to the configured root")

    candidate = (root / path).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SafePathError("path must stay inside the configured root") from exc
    if must_exist and not candidate.exists():
        raise FileNotFoundError(f"path does not exist: {requested!r}")
    if file_only and not candidate.is_file():
        raise SafePathError(f"path is not a file: {requested!r}")
    return candidate


def guarded_path(root: Path, requested: str, *, file_only: bool = True) -> Path:
    """Resolve an existing source path and translate policy errors to ToolError."""

    try:
        return resolve_relative(root, requested, file_only=file_only)
    except (SafePathError, FileNotFoundError) as exc:
        raise ToolError(str(exc)) from exc


def guarded_output(root: Path, requested: str) -> Path:
    """Resolve a writable path under ``root`` without creating directories."""

    try:
        return resolve_relative(root, requested, must_exist=False)
    except SafePathError as exc:
        raise ToolError(str(exc)) from exc


def root_from(
    value: Path | str | None,
    fallback: Path,
    *,
    must_exist: bool = True,
) -> Path:
    """Normalize a registration-time root and optionally require a directory."""

    root = Path(value) if value is not None else fallback
    if not root.is_absolute():
        root = fallback / root
    root = root.resolve(strict=False)
    if must_exist and not root.exists():
        raise ValueError(f"configured root does not exist: {root}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"configured root is not a directory: {root}")
    return root


def norm_path(path: str | os.PathLike[str]) -> str:
    """Canonical path helper used by the sandbox guard."""

    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))
