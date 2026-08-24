"""A linter for tool definitions.

Great tools are self-describing: a clear name, a docstring that tells the model
when and why to call it, and every parameter documented. This module scores a
tool against those heuristics so you can catch context-hostile tools early.

It is duck-typed: it works on anything exposing ``name`` / ``description`` and a
parameters mapping -- notably LangChain ``BaseTool`` objects returned by
``langchain_mcp_adapters`` (via ``.args``), so you can lint your *live* MCP tools
straight from the notebook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

# Tunable thresholds.
MIN_DESCRIPTION_CHARS = 25
MAX_DESCRIPTION_CHARS = 1024
MAX_NAME_CHARS = 64


@dataclass
class LintReport:
    """Result of linting a single tool."""

    name: str
    score: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if there are no hard errors."""
        return not self.errors

    def summary(self) -> str:
        status = "OK" if self.ok else "FAIL"
        return f"[{status}] {self.name}: score={self.score}/100"


def _extract_params(tool: Any) -> dict[str, dict[str, Any]]:
    """Best-effort extraction of a ``{param_name: json_schema}`` mapping."""
    # LangChain BaseTool exposes `.args` -> {name: schema-ish dict}.
    args = getattr(tool, "args", None)
    if isinstance(args, dict) and args:
        return {k: (v if isinstance(v, dict) else {}) for k, v in args.items()}

    # Pydantic args_schema fallback.
    schema_obj = getattr(tool, "args_schema", None)
    if schema_obj is not None:
        try:
            schema = (
                schema_obj.model_json_schema()
                if hasattr(schema_obj, "model_json_schema")
                else dict(schema_obj)
            )
            return dict(schema.get("properties", {}))
        except Exception:
            return {}
    return {}


def lint_tool(tool: Any) -> LintReport:
    """Lint a single tool object. Returns a :class:`LintReport`."""
    name = str(getattr(tool, "name", "") or "")
    description = str(getattr(tool, "description", "") or "")
    params = _extract_params(tool)

    report = LintReport(name=name or "<unnamed>", score=100)

    # --- name ------------------------------------------------------------
    if not name:
        report.errors.append("Tool has no name.")
        report.score -= 40
    else:
        if len(name) > MAX_NAME_CHARS:
            report.warnings.append(f"Name is long (>{MAX_NAME_CHARS} chars).")
            report.score -= 5
        if not _SNAKE_CASE.match(name):
            report.warnings.append(
                "Name is not lower_snake_case; consider a verb_noun name."
            )
            report.score -= 5

    # --- description -----------------------------------------------------
    stripped = description.strip()
    if not stripped:
        report.errors.append("Missing description/docstring.")
        report.score -= 40
    elif len(stripped) < MIN_DESCRIPTION_CHARS:
        report.warnings.append(
            f"Description is very short (<{MIN_DESCRIPTION_CHARS} chars). "
            "Say what it does, when to use it, and what it returns."
        )
        report.score -= 15
    elif len(stripped) > MAX_DESCRIPTION_CHARS:
        report.warnings.append(
            f"Description is very long (>{MAX_DESCRIPTION_CHARS} chars); it eats "
            "context on every call. Trim it."
        )
        report.score -= 10

    # --- parameters ------------------------------------------------------
    undocumented = []
    for pname, pschema in params.items():
        has_desc = bool(isinstance(pschema, dict) and pschema.get("description"))
        if not has_desc:
            undocumented.append(pname)
    if undocumented:
        report.warnings.append(
            "Parameters missing descriptions: " + ", ".join(sorted(undocumented))
        )
        report.score -= min(20, 4 * len(undocumented))

    report.score = max(0, report.score)
    return report


def lint_tools(tools: list[Any]) -> list[LintReport]:
    """Lint a list of tools, returning one report per tool."""
    return [lint_tool(t) for t in tools]

