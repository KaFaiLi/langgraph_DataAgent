"""Context lab: utilities to build, measure, and challenge tools.

- ``tokens``      : estimate token / size cost of tool outputs.
- ``tool_linter`` : score tool definitions against best practices so you catch
                    context-hostile tools *before* the agent does.
"""

from data_agent.context_lab.tokens import estimate_tokens, payload_stats
from data_agent.context_lab.tool_linter import (
    LintReport,
    lint_tool,
    lint_tools,
)

__all__ = [
    "LintReport",
    "estimate_tokens",
    "lint_tool",
    "lint_tools",
    "payload_stats",
]
