"""MCP Agent Template.

A batteries-included starting point for building and *testing* MCP tools with a
LangGraph ReAct agent, pluggable skills, and a swappable LLM backend.

Package layout
--------------
- ``config``       : typed settings loaded from the environment / ``.env``.
- ``llm``          : the GenAI API manager (LLM provider abstraction).
- ``mcp_server``   : the FastMCP server + where you implement your tools.
- ``skills``       : discover ``SKILL.md`` files and expose them to the agent.
- ``agent``        : the LangGraph ReAct agent wiring everything together.
- ``context_lab``  : helpers to inspect/challenge tools (linting, token budget).
"""

from data_agent.config import Settings, get_settings

__all__ = ["Settings", "get_settings", "__version__"]

__version__ = "0.1.0"
