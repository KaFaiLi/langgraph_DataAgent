"""Logging helpers.

MCP stdio servers must keep ``stdout`` clean for JSON-RPC, so all logs go to
``stderr``. Rich makes them readable during development.
"""

from __future__ import annotations

import logging
import sys

from rich.logging import RichHandler

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging to stderr exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = RichHandler(
        console=None,
        rich_tracebacks=True,
        show_path=False,
    )
    # Force stderr so stdio MCP transport is never polluted.
    handler.console.file = sys.stderr  # type: ignore[attr-defined]
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger (call :func:`setup_logging` first)."""
    return logging.getLogger(name)
