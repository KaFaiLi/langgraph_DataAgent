"""Shared deterministic helpers for specialist analyses (code computes; LLMs interpret)."""

from __future__ import annotations

from typing import Any, cast

import polars as pl
from fastmcp.exceptions import ToolError

from data_agent.tools.review_context import ToolContext
from data_agent.tools.tabular_tools import load_table

DATE_COLUMN_NAMES = {"date", "business_date", "trade_date", "asof", "as_of", "day"}


def load_frame(
    ctx: ToolContext, path: str, sheet: str | None = None
) -> pl.DataFrame | None:
    """Load a tabular source, returning None for anything unreadable."""
    try:
        return load_table(ctx.source_root, path, sheet)
    except (FileNotFoundError, OSError, ValueError, ToolError):
        return None


def find_column(frame: pl.DataFrame, names: set[str]) -> str | None:
    for column in frame.columns:
        if column.lower() in names:
            return column
    return None


def date_column(frame: pl.DataFrame) -> str | None:
    return find_column(frame, DATE_COLUMN_NAMES)


def dates_list(frame: pl.DataFrame, date_col: str | None) -> list[object]:
    if date_col is not None:
        return list(frame[date_col].to_list())
    return list(range(frame.height))


def floats(series: pl.Series) -> list[float]:
    raw = series.cast(pl.Float64).to_list()
    return [float(cast(Any, value)) for value in raw]


def flag(kind: str, path: str, date: object, **extra: object) -> dict[str, object]:
    return {"kind": kind, "path": path, "date": str(date), **extra}


def month_end_mask(dates: list[object]) -> list[bool]:
    """True for rows whose date is the last calendar day of its month."""
    import datetime as dt

    mask: list[bool] = []
    for value in dates:
        text = str(value)
        try:
            day = dt.date.fromisoformat(text[:10])
        except ValueError:
            mask.append(False)
            continue
        if day.month == 12:
            next_month = day.replace(year=day.year + 1, month=1, day=1)
        else:
            next_month = day.replace(month=day.month + 1, day=1)
        mask.append(day == next_month - dt.timedelta(days=1))
    return mask


def group_sum(
    frame: pl.DataFrame, group_col: str, value_col: str
) -> list[dict[str, object]]:
    grouped = (
        frame.group_by(group_col)
        .agg(pl.col(value_col).cast(pl.Float64).sum().alias("value"))
        .sort("value", descending=True)
    )
    return grouped.to_dicts()


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def pstdev(values: list[float]) -> float:
    average = mean(values)
    return (sum((value - average) ** 2 for value in values) / len(values)) ** 0.5


def top_share(shares: list[float], n: int = 3) -> float:
    ordered = sorted(shares, reverse=True)
    return sum(ordered[:n])


def hhi(shares: list[float]) -> float:
    return sum(share**2 for share in shares)
