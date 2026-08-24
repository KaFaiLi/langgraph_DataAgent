"""Build the FastMCP server.

The server itself is tiny: it creates a :class:`fastmcp.FastMCP` instance,
gives it useful ``instructions`` (these are shown to MCP clients / the model),
and lets each tool module register its tools. Put your real tools in the
``tools/`` package.
"""

from __future__ import annotations

from fastmcp import FastMCP

from data_agent.config import Settings, get_settings
from data_agent.logging_utils import get_logger, setup_logging
from data_agent.tools import (
    context_tools,
    example_tools,
    grep_tools,
    python_tools,
    source_tools,
    statistics_tools,
    tabular_tools,
)

logger = get_logger(__name__)

SERVER_INSTRUCTIONS = """\
This server exposes guarded local source and analysis tools to an LLM agent via MCP.

How to use it well:
- Every tool's docstring is its contract for the model. Read it before calling.
- Tools return compact, structured results. Prefer calling a tool over guessing.
- `list_sources`, `search_text`, `read_lines`, and `read_document_section` read
  only the configured `SOURCE_ROOT`; paths are guarded and all results are
  bounded. `grep` is a separate workspace-relative development search.
- Use tabular/statistics tools for deterministic local analysis and the Python
  tool only for its documented restricted execution contract.
- The `context_*` tools exist to help you *measure and debug* how tools consume
  the model's context window.

Source tools use `Settings.source_root` (the `SOURCE_ROOT` environment variable).
All tool modules register against this one server instance.
"""


def build_server(settings: Settings | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance."""
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    mcp = FastMCP(
        name=settings.mcp_server_name,
        instructions=SERVER_INSTRUCTIONS,
    )

    # Register tool groups. Add your own modules here.
    example_tools.register(mcp)
    context_tools.register(mcp)
    grep_tools.register(mcp)
    source_tools.register(mcp, root=settings.source_path)
    tabular_tools.register(mcp, root=settings.source_path, settings=settings)
    statistics_tools.register(mcp)
    python_tools.register(mcp, root=settings.source_path, settings=settings)

    logger.info("FastMCP server '%s' built.", settings.mcp_server_name)
    return mcp


def run(settings: Settings | None = None) -> None:
    """Run the server using the transport from settings."""
    settings = settings or get_settings()
    mcp = build_server(settings)

    transport = settings.mcp_transport.lower().strip()
    if transport == "stdio":
        logger.info("Starting MCP server on STDIO transport.")
        mcp.run()  # defaults to stdio
    elif transport == "http":
        logger.info("Starting MCP server on HTTP transport at %s", settings.mcp_http_url)
        mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)
    else:
        raise ValueError(f"Unsupported MCP_TRANSPORT={transport!r}. Use 'stdio' or 'http'.")
