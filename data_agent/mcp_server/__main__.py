"""Entry point so the server can be launched as a subprocess.

    python -m data_agent.mcp_server        # stdio (default)
    MCP_TRANSPORT=http python -m data_agent.mcp_server

This is exactly the command the agent uses to spawn the server over stdio, and
the command you point the MCP Inspector at.
"""

from __future__ import annotations

from data_agent.mcp_server.server import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
