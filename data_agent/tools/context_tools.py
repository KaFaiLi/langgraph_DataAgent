"""Context-engineering tools shared by local and MCP callers.

These tools exist to help you *build and challenge* tools with respect to the
model's context window -- the scarcest resource an agent has. Keep them while
developing; you can remove them before shipping.

They let the agent (and you, via the inspector) answer questions like:
  - "How many tokens does this tool output actually cost?"
  - "What happens to the agent when a tool returns 5k tokens of junk?"
  - "Is my payload small enough to be worth returning?"
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from data_agent.context_lab.tokens import estimate_tokens, payload_stats


def register(mcp: FastMCP) -> None:
    """Attach the context-lab tools to the server."""

    @mcp.tool
    def estimate_token_cost(
        text: Annotated[str, Field(description="Text to measure.")],
        model: Annotated[
            str, Field(description="Model name for tokenizer selection.")
        ] = "gpt-4o-mini",
    ) -> dict[str, Any]:
        """Estimate how many tokens a string would consume.

        Use this to check whether a tool's output is 'context-cheap'. Returns
        the estimated token count, the tokenizer used, and character length.
        """
        tokens, method = estimate_tokens(text, model=model)
        return {
            "tokens": tokens,
            "characters": len(text),
            "tokenizer": method,
            "model": model,
        }

    @mcp.tool
    def inspect_payload(
        payload: Annotated[str, Field(description="Serialized payload to inspect.")],
    ) -> dict[str, Any]:
        """Report the size profile of a payload (tokens, bytes, chars, lines).

        Call this on a candidate tool response to sanity-check its context cost
        before you commit to that response shape.
        """
        return payload_stats(payload)

    @mcp.tool
    def generate_filler(
        approx_tokens: Annotated[
            int,
            Field(ge=1, le=20000, description="Approximate token size to generate."),
        ],
    ) -> dict[str, Any]:
        """Generate throwaway text of roughly `approx_tokens` tokens.

        A stress-test utility: point a real tool at this to see how your agent
        copes when a tool floods the context window. Returns the filler plus its
        measured size so you can verify the target was hit.
        """
        if approx_tokens < 1:
            raise ToolError("approx_tokens must be >= 1.")
        # ~1 token per word for this simple filler vocabulary.
        word = "lorem "
        text = (word * approx_tokens).strip()
        tokens, method = estimate_tokens(text)
        return {
            "requested_tokens": approx_tokens,
            "measured_tokens": tokens,
            "tokenizer": method,
            "text": text,
        }
