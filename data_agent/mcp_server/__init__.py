"""FastMCP server package.

``server.build_server()`` returns a ready-to-run :class:`fastmcp.FastMCP`
instance with all tool modules registered. Run it with ``python -m
data_agent.mcp_server`` (see ``__main__.py``).
"""

from data_agent.mcp_server.server import build_server

__all__ = ["build_server"]
