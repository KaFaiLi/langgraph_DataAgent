"""Helpers to run the MCP server as a background HTTP process.

Why: MCP's *stdio* client spawns a subprocess and wires its stderr to
``sys.stderr``. Inside a Jupyter kernel ``sys.stderr`` has no real file
descriptor, so stdio can't be used from a notebook. Running the server over HTTP
sidesteps that entirely (and keeps a single long-lived server process instead of
re-spawning one per tool call). Use this from the notebook; the CLI and tests
use stdio directly.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from data_agent.config import REPO_ROOT, Settings, get_settings
from data_agent.logging_utils import get_logger

logger = get_logger(__name__)


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> bool:
    """Poll until ``host:port`` accepts connections or ``timeout`` elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.3)
    return False


def wait_for_port_free(host: str, port: int, timeout: float = 10.0) -> bool:
    """Poll until ``host:port`` is no longer accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _port_open(host, port):
            return True
        time.sleep(0.2)
    return False


def stop_http_server(
    proc: subprocess.Popen | None,
    settings: Settings | None = None,
) -> None:
    """Terminate a server process and wait for its port to be released.

    Safe to call with ``None`` or an already-dead process. Ensures the port is
    actually free before returning, so an immediate restart won't collide.
    """
    settings = settings or get_settings()
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            proc.kill()
    wait_for_port_free(settings.mcp_host, settings.mcp_port)


def spawn_http_server(
    settings: Settings | None = None,
    *,
    log_path: str | Path | None = None,
) -> subprocess.Popen:
    """Start ``python -m data_agent.mcp_server`` over HTTP in the background.

    Returns the :class:`subprocess.Popen` handle. Call ``.terminate()`` when done
    (or use :func:`http_server` as a context manager). Server logs go to
    ``log_path`` (default ``<repo>/mcp_server.log``).
    """
    settings = settings or get_settings()
    if _port_open(settings.mcp_host, settings.mcp_port):
        raise RuntimeError(
            f"{settings.mcp_host}:{settings.mcp_port} is already in use. "
            "Stop the other server or change MCP_PORT."
        )

    env = {
        **os.environ,
        "MCP_TRANSPORT": "http",
        "MCP_HOST": settings.mcp_host,
        "MCP_PORT": str(settings.mcp_port),
    }
    log_file = Path(log_path) if log_path else (REPO_ROOT / "mcp_server.log")
    log_handle = open(log_file, "w", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen(
        [sys.executable, "-m", "data_agent.mcp_server"],
        env=env,
        stdout=log_handle,
        stderr=log_handle,
    )
    if not wait_for_port(settings.mcp_host, settings.mcp_port):
        proc.terminate()
        raise RuntimeError(
            f"MCP HTTP server failed to start on {settings.mcp_http_url}. "
            f"See logs: {log_file}"
        )
    logger.info("MCP HTTP server ready at %s (pid=%s)", settings.mcp_http_url, proc.pid)
    return proc


class http_server:  # noqa: N801 - context-manager style name
    """Context manager wrapping :func:`spawn_http_server`.

    Example::

        with http_server(settings) as proc:
            ...  # server is up
    """

    def __init__(self, settings: Settings | None = None, **kwargs) -> None:
        self.settings = settings
        self.kwargs = kwargs
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> subprocess.Popen:
        self.proc = spawn_http_server(self.settings, **self.kwargs)
        return self.proc

    def __exit__(self, *exc) -> None:
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                self.proc.kill()

