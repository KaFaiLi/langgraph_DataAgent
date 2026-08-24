"""Assigned-source, traced tools for bounded specialist ReAct research."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from data_agent.tools import source_tools, statistics_tools, tabular_tools
from data_agent.review.domain.evidence import parse_locator
from data_agent.tools.review_context import ToolContext

MAX_RESULT_CHARS = 12_000
LOCATOR_PATTERN = re.compile(r"source://[^\s\]\[\)\(\"']+")


def build_research_tools(
    ctx: ToolContext,
    assigned_paths: list[str],
    trace: list[dict[str, Any]],
    *,
    max_calls: int,
    research_round: int = 0,
) -> list[BaseTool]:
    """Bind safe in-process tools to exactly one specialist source scope."""

    allowed = {Path(path).as_posix() for path in assigned_paths}
    lock = threading.Lock()

    def checked(path: str) -> str:
        normalized = Path(path).as_posix()
        if normalized not in allowed:
            raise ToolException(f"source path is outside this specialist scope: {path!r}")
        return normalized

    def call(name: str, arguments: dict[str, Any], operation: Any) -> str:
        with lock:
            if len(trace) >= max_calls:
                raise ToolException(f"specialist tool-call budget exhausted ({max_calls})")
        error: str | None = None
        try:
            value = operation()
            raw = value if isinstance(value, str) else json.dumps(value, default=str)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raw = error
        rendered = raw[:MAX_RESULT_CHARS]
        record = {
            "tool": name,
            "arguments": arguments,
            "result_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "result_preview": rendered,
            "locators": sorted(set(LOCATOR_PATTERN.findall(raw))),
            "truncated": len(raw) > MAX_RESULT_CHARS,
            "error": error,
            "round": research_round,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with lock:
            if len(trace) >= max_calls:
                raise ToolException(f"specialist tool-call budget exhausted ({max_calls})")
            trace.append(record)
        if error is not None:
            raise ToolException(error)
        return rendered

    def list_assigned_sources() -> str:
        """List only the immutable sources assigned to this specialist."""
        return call(
            "list_assigned_sources",
            {},
            lambda: [
                source.model_dump(mode="json")
                for source in ctx.manifest.sources
                if source.path in allowed
            ],
        )

    def inspect_table(path: str, sheet: str | None = None, preview_rows: int = 5) -> str:
        """Inspect columns, row count, and a bounded table preview."""
        path = checked(path)
        return call(
            "inspect_table",
            {"path": path, "sheet": sheet, "preview_rows": preview_rows},
            lambda: tabular_tools.inspect_table(ctx.source_root, path, sheet, preview_rows),
        )

    def read_rows(
        path: str, start: int, end: int, sheet: str | None = None
    ) -> str:
        """Read bounded 1-based inclusive rows from an assigned table."""
        path = checked(path)
        return call(
            "read_rows",
            {"path": path, "start": start, "end": end, "sheet": sheet},
            lambda: tabular_tools.read_rows(ctx.source_root, path, start, end, sheet),
        )

    def describe_columns(path: str, sheet: str | None = None) -> str:
        """Describe column types, nulls, cardinality, and numeric ranges."""
        path = checked(path)
        return call(
            "describe_columns",
            {"path": path, "sheet": sheet},
            lambda: tabular_tools.describe_columns(ctx.source_root, path, sheet),
        )

    def group_by(
        path: str,
        group_columns: list[str],
        agg_column: str,
        agg: str = "sum",
        sheet: str | None = None,
    ) -> str:
        """Aggregate one assigned table by selected columns."""
        path = checked(path)
        return call(
            "group_by",
            {
                "path": path,
                "group_columns": group_columns,
                "agg_column": agg_column,
                "agg": agg,
                "sheet": sheet,
            },
            lambda: tabular_tools.group_by(
                ctx.source_root, path, group_columns, agg_column, agg, sheet
            ),
        )

    def join_tables(
        left: str,
        right: str,
        on: list[str],
        how: Literal["inner", "left", "outer", "full", "cross"] = "inner",
    ) -> str:
        """Join two assigned tables and return a bounded result."""
        left = checked(left)
        right = checked(right)
        return call(
            "join_tables",
            {"left": left, "right": right, "on": on, "how": how},
            lambda: tabular_tools.join_tables(ctx.source_root, left, right, on, how),
        )

    def run_duckdb_query(sql: str, max_rows: int = 1000) -> str:
        """Run one read-only query over assigned registered source tables."""
        all_names = {
            tabular_tools._table_name(Path(source.path)): source.path
            for source in ctx.manifest.sources
            if Path(source.path).suffix.lower() in tabular_tools.SUPPORTED_SUFFIXES
        }
        forbidden = [name for name, path in all_names.items() if path not in allowed and re.search(rf"\b{re.escape(name)}\b", sql, re.I)]
        if forbidden:
            raise ToolException(f"query references tables outside specialist scope: {forbidden}")
        return call(
            "run_duckdb_query",
            {"sql": sql, "max_rows": max_rows},
            lambda: tabular_tools.run_duckdb_query(ctx.source_root, sql, max_rows),
        )

    def search_text(pattern: str, case_insensitive: bool = False, max_results: int = 50) -> str:
        """Search text only within assigned source files."""
        def operation() -> dict[str, Any]:
            matches: list[Any] = []
            for path in sorted(allowed):
                result = source_tools.search_text_data(
                    ctx.source_root,
                    pattern,
                    case_insensitive=case_insensitive,
                    max_results=max_results,
                    path=path,
                )
                matches.extend(result.get("matches", []))
                if len(matches) >= max_results:
                    break
            return {"matches": matches[:max_results], "truncated": len(matches) > max_results}

        return call(
            "search_text",
            {
                "pattern": pattern,
                "case_insensitive": case_insensitive,
                "max_results": max_results,
            },
            operation,
        )

    def read_lines(path: str, start: int, end: int, max_lines: int = 200) -> str:
        """Read bounded lines from an assigned text source."""
        path = checked(path)
        return call(
            "read_lines",
            {"path": path, "start": start, "end": end, "max_lines": max_lines},
            lambda: source_tools.read_lines_data(
                ctx.source_root, path, start, end, max_lines=max_lines
            ),
        )

    def reopen_evidence(locator: str) -> str:
        """Reopen a source locator only when it belongs to an assigned source."""
        parsed = parse_locator(locator)
        checked(parsed.path)
        return call(
            "reopen_evidence",
            {"locator": locator},
            lambda: source_tools.read_document_section_data(ctx.source_root, locator),
        )

    def zscore(values: list[float | None]) -> str:
        """Compute deterministic z-scores."""
        return call("zscore", {"values": values}, lambda: statistics_tools.zscore(values))

    def outlier_detection(values: list[float | None], threshold: float = 3.0) -> str:
        """Return deterministic z-score outlier candidates."""
        return call(
            "outlier_detection",
            {"values": values, "threshold": threshold},
            lambda: statistics_tools.outlier_detection(values, threshold),
        )

    def change_point_candidates(values: list[float], window: int = 5, threshold: float = 2.0) -> str:
        """Return deterministic rolling change-point candidates."""
        return call(
            "change_point_candidates",
            {"values": values, "window": window, "threshold": threshold},
            lambda: statistics_tools.change_point_candidates(values, window, threshold),
        )

    def pearson_correlation(left: list[float | None], right: list[float | None]) -> str:
        """Compute deterministic Pearson correlation."""
        return call(
            "pearson_correlation",
            {"left": left, "right": right},
            lambda: statistics_tools.pearson_correlation(left, right),
        )

    functions = [
        list_assigned_sources,
        inspect_table,
        read_rows,
        describe_columns,
        group_by,
        join_tables,
        run_duckdb_query,
        search_text,
        read_lines,
        reopen_evidence,
        zscore,
        outlier_detection,
        change_point_candidates,
        pearson_correlation,
    ]
    return [
        StructuredTool.from_function(function, handle_tool_errors=True)
        for function in functions
    ]
