"""Shared guarded tool implementations and MCP registration adapters.

Source, tabular, statistical, grep, and restricted-Python modules expose pure
in-process functions plus ``register(mcp)`` transport adapters. Review context,
research, and analysis helpers add run scoping without reimplementing those
operations. To add a new general tool group:

1. Create ``my_tools.py`` with a ``register(mcp)`` function.
2. Import it in ``server.build_server`` and call ``my_tools.register(mcp)``.
"""
