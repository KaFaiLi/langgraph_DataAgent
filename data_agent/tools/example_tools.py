'''Example tools and guidelines for shared tool development.

============================================================================
 HOW TO WRITE A GREAT TOOL  (read this before adding your own)
============================================================================
An MCP tool is a Python function. What the model sees is derived automatically:

  - the tool NAME       -> the function name (or `name=` in the decorator)
  - the DESCRIPTION     -> the function docstring
  - the INPUT SCHEMA    -> the parameter type hints + defaults + `Field(...)`
  - the OUTPUT SCHEMA   -> the return type hint

So the quality of your type hints and docstring *is* the quality of your tool.

Checklist (the `context_lab.tool_linter` enforces most of these):
  1. NAME: a short verb_noun, lowercase, unambiguous (`search_orders`, not `do`).
  2. DESCRIPTION: 1-3 sentences. Say what it does, when to use it, and what it
     returns. Mention side effects. Write it for a competent stranger.
  3. PARAMETERS: annotate every param. Use `Annotated[T, Field(description=...)]`
     to describe non-obvious params. Give sensible defaults for optional ones.
  4. OUTPUT: keep it small and structured. Return dicts/models, not giant blobs.
     Tokens are the agent's budget -- every field you return costs context.
  5. ERRORS: raise `ToolError` with an actionable message. Never leak stack
     traces or secrets. Failing loudly beats returning ambiguous junk.
  6. DETERMINISM: same input -> same output where possible; it makes tools
     testable and cacheable.
  7. PAGINATION: for potentially large results, take `limit`/`offset` (or a
     cursor) instead of dumping everything.

Delete these examples once you have your own tools -- they exist to show the
patterns above, not to ship in production.
'''

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field


def register(mcp: FastMCP) -> None:
    """Attach the example tools to the server."""

    @mcp.tool
    def ping() -> str:
        """Health check. Returns 'pong' so you can confirm the server is up.

        Use this first when debugging connectivity from a client/inspector.
        """
        return "pong"

    @mcp.tool
    def server_time() -> dict[str, str]:
        """Return the server's current time in UTC (ISO-8601).

        Handy for anchoring the agent to "now" instead of its training cutoff.
        """
        now = datetime.now(UTC)
        return {"utc": now.isoformat(), "unix": str(int(now.timestamp()))}

    @mcp.tool
    def add(
        a: Annotated[float, Field(description="First addend.")],
        b: Annotated[float, Field(description="Second addend.")],
    ) -> float:
        """Add two numbers and return the sum.

        A minimal, correct example: typed params with descriptions, a clear
        docstring, and a small typed return value.
        """
        return a + b

    @mcp.tool
    def search_items(
        query: Annotated[str, Field(description="Free-text search string.")],
        limit: Annotated[
            int, Field(ge=1, le=50, description="Max results to return (1-50).")
        ] = 5,
    ) -> dict[str, Any]:
        """Search a demo catalog and return matching items.

        This is a PLACEHOLDER that returns synthetic data so you can see the
        shape of a good response: a small, paginated, structured payload rather
        than an unbounded dump. Replace the body with a real data source
        (DB query, API call, vector search, ...).

        Returns a dict with `query`, `count`, and a `results` list of
        `{id, title, score}` objects.
        """
        # ----- BEGIN placeholder implementation ---------------------------
        if not query.strip():
            raise ToolError("query must not be empty.")

        fake_catalog = [f"{query} result {i}" for i in range(1, 21)]
        results = [
            {"id": i, "title": title, "score": round(1.0 - i * 0.03, 3)}
            for i, title in enumerate(fake_catalog[:limit], start=1)
        ]
        return {"query": query, "count": len(results), "results": results}
        # ----- END placeholder implementation -----------------------------

    # ----------------------------------------------------------------------
    # TODO: Add your real tools below, following the checklist at the top.
    #
    # @mcp.tool
    # def get_customer(customer_id: Annotated[str, Field(description="...")]):
    #     """One-line summary. When to use. What it returns."""
    #     ...
    # ----------------------------------------------------------------------
