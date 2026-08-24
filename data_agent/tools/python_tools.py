"""Run bounded, no-network Python analysis in a fresh guarded process."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from data_agent.config import REPO_ROOT, Settings, get_settings
from data_agent.tools._safe_paths import root_from

DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TIMEOUT_SECONDS = 120.0
MAX_OUTPUT_CHARS = 100_000
MAX_CODE_CHARS = 500_000

_SCRUB_PREFIXES = (
    "DEEPSEEK_",
    "OPENAI_",
    "ANTHROPIC_",
    "RISK_AGENT_",
    "LANGSMITH_",
    "LANGCHAIN_",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)
_SENSITIVE_ENV_NAME = re.compile(
    r"(?:API[_-]?KEY|ACCESS[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE)",
    re.IGNORECASE,
)


def _scrubbed_env() -> dict[str, str]:
    """Return an environment without credentials, proxy, or LLM settings."""

    env = {key: value for key, value in os.environ.items() if value is not None}
    for key in list(env):
        if any(
            key.startswith(prefix) or key == prefix for prefix in _SCRUB_PREFIXES
        ) or _SENSITIVE_ENV_NAME.search(key):
            env.pop(key, None)
    # ``-I`` ignores these for Python itself; removing them also protects
    # libraries that inspect the process environment directly.
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def _validate_limits(timeout_seconds: float, max_output_chars: int) -> None:
    if not 0.1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ToolError(f"timeout_seconds must be between 0.1 and {MAX_TIMEOUT_SECONDS}")
    if not 1 <= max_output_chars <= MAX_OUTPUT_CHARS:
        raise ToolError(f"max_output_chars must be between 1 and {MAX_OUTPUT_CHARS}")


def run_python_analysis(
    source_root: Path,
    workspace_root: Path,
    code: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_chars: int = MAX_OUTPUT_CHARS,
) -> dict[str, Any]:
    """Execute code with source-read/workspace-write and no-network guards.

    The subprocess may read files below ``source_root`` and write files below
    ``workspace_root``. Imports of networking, process, FFI, and LLM modules
    are denied. Results include bounded stdout/stderr and process status.
    """

    if not isinstance(code, str) or not code.strip():
        raise ToolError("code must not be empty")
    if len(code) > MAX_CODE_CHARS:
        raise ToolError(f"code exceeds the {MAX_CODE_CHARS}-character limit")
    _validate_limits(timeout_seconds, max_output_chars)
    source_root = root_from(source_root, source_root)
    workspace_root = Path(workspace_root).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    workspace_root = root_from(workspace_root, workspace_root)
    script_path = workspace_root / f".analysis_{uuid.uuid4().hex[:16]}.py"
    script_path.write_text(code, encoding="utf-8")
    child_env = _scrubbed_env()
    # Explicit roots are useful to generated code and are not credentials.
    child_env["DATA_AGENT_SOURCE_ROOT"] = str(source_root)
    child_env["DATA_AGENT_WORKSPACE_ROOT"] = str(workspace_root)
    bootstrap = Path(__file__).with_name("sandbox_bootstrap.py").resolve()
    command = [
        sys.executable,
        "-I",
        str(bootstrap),
        str(script_path),
        str(source_root),
        str(workspace_root),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=child_env,
            cwd=str(workspace_root),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"sandbox timed out after {timeout_seconds:g}s",
            "exit_code": -1,
            "ok": False,
            "timed_out": True,
        }
    finally:
        # The child has finished (or was terminated by subprocess.run). Keep
        # user-created workspace files, but never leave the generated script.
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "stdout": completed.stdout[:max_output_chars],
        "stderr": completed.stderr[:max_output_chars],
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "timed_out": False,
    }


def register(
    mcp: FastMCP,
    root: Path | str | None = None,
    *,
    source_root: Path | str | None = None,
    workspace_root: Path | str | None = None,
    settings: Settings | None = None,
) -> None:
    """Register one sandbox binding; roots cannot be supplied by callers."""

    configured_root: Path | str | None = root
    if configured_root is None:
        configured_root = (settings or get_settings()).source_path
    bound_root = root_from(configured_root, REPO_ROOT, must_exist=False)
    bound_source = root_from(source_root, bound_root) if source_root is not None else bound_root
    if workspace_root is not None:
        bound_workspace = Path(workspace_root).resolve()
        bound_workspace.mkdir(parents=True, exist_ok=True)
        bound_workspace = root_from(bound_workspace, bound_workspace)
    else:
        # A one-root registration remains safe by making the default workspace
        # a private child. Explicit split roots are available for deployments
        # that already have separate source/workspace directories.
        bound_workspace = bound_root / ".analysis_workspace"
        # Do not create a missing SOURCE_ROOT merely by starting the server.
        # ``run_python_analysis`` validates the source root before creating the
        # workspace, so a later-mounted source directory still works normally.
        if bound_root.exists():
            bound_workspace.mkdir(parents=True, exist_ok=True)

    @mcp.tool(name="run_python_analysis")
    def run_python_analysis_tool(
        code: Annotated[str, Field(description="Analysis code; no network or process APIs.")],
        timeout_seconds: Annotated[
            float,
            Field(
                ge=0.1,
                le=MAX_TIMEOUT_SECONDS,
                description="Hard subprocess timeout in seconds.",
            ),
        ] = DEFAULT_TIMEOUT_SECONDS,
        max_output_chars: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_OUTPUT_CHARS,
                description="Maximum stdout/stderr characters.",
            ),
        ] = MAX_OUTPUT_CHARS,
    ) -> dict[str, Any]:
        """Execute bounded Python over configured data with no network/process access."""

        return run_python_analysis(
            bound_source,
            bound_workspace,
            code,
            timeout_seconds=timeout_seconds,
            max_output_chars=max_output_chars,
        )
