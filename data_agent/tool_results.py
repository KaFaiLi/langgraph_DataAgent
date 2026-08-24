"""Normalize the result of invoking an MCP tool via langchain-mcp-adapters.

Depending on the LangChain / adapter version, ``tool.ainvoke(...)`` may return a
plain string, a JSON string, or a list of content blocks like
``[{"type": "text", "text": "..."}]``. These helpers give you the raw text or a
parsed Python object regardless of that shape.
"""

from __future__ import annotations

import json
from typing import Any


def tool_text(result: Any) -> str:
    """Extract the concatenated text payload from a tool result."""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
            else:
                parts.append(str(item))
        return "".join(parts)
    if isinstance(result, dict) and "text" in result:
        return str(result["text"])
    return str(result)


def tool_json(result: Any) -> Any:
    """Parse a tool result as JSON, falling back to the raw text."""
    text = tool_text(result)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text

