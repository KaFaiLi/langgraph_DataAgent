"""Central normalization and evidence helpers for deterministic skill analyses.

Domain scripts own business rules. This module keeps generic table-value parsing,
physical row numbering, and source-locator construction consistent across skills.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from data_agent.review.domain.evidence import Locator, format_locator
from data_agent.review.domain.source import SourceType


def normalized_columns(frame: pl.DataFrame) -> set[str]:
    """Return stripped, case-insensitive column names for schema matching."""
    return {column.strip().lower() for column in frame.columns}


def column_map(frame: pl.DataFrame) -> dict[str, str]:
    """Map normalized column names back to their source spelling."""
    return {column.strip().lower(): column for column in frame.columns}


def text_value(value: object) -> str:
    """Normalize a nullable cell to stripped text."""
    return "" if value is None else str(value).strip()


def float_value(value: object) -> float | None:
    """Parse a finite numeric cell without imposing a domain unit."""
    try:
        parsed = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else None


def int_value(value: object) -> int | None:
    """Parse an integer-like numeric cell."""
    parsed = float_value(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


def date_value(value: object) -> dt.date | None:
    """Parse common source date representations, preferring ISO then month-first."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = text_value(value)
    for parser in (
        lambda: dt.date.fromisoformat(text[:10]),
        lambda: dt.datetime.strptime(text, "%m/%d/%Y").date(),
        lambda: dt.datetime.strptime(text, "%d/%m/%Y").date(),
    ):
        try:
            return parser()
        except ValueError:
            continue
    return None


def datetime_value(value: object) -> dt.datetime | None:
    """Parse an ISO timestamp, preserving any supplied timezone offset."""
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    text = text_value(value).replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def bool_value(value: object) -> bool | None:
    """Parse common boolean cell representations."""
    if isinstance(value, bool):
        return value
    normalized = text_value(value).lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def percent_value(value: object) -> float | None:
    """Parse either a decimal ratio or a percent-formatted cell to a ratio."""
    text = text_value(value)
    if not text:
        return None
    if text.endswith("%"):
        parsed = float_value(text[:-1])
        return None if parsed is None else parsed / 100.0
    parsed = float_value(text)
    if parsed is None:
        return None
    return parsed / 100.0 if parsed > 2 else parsed


def tabular_row_offset(source_type: SourceType) -> int:
    """Return the first data-row locator number for a parsed table."""
    return 1 if source_type is SourceType.PARQUET else 2


def indexed_rows(frame: pl.DataFrame, row_offset: int) -> list[dict[str, object]]:
    """Return table rows carrying their physical evidence row number."""
    return frame.with_row_index("_source_row", offset=row_offset).to_dicts()


def row_locator(path: str, sheet: str | None, row: int) -> str:
    """Build a reopenable locator for one physical tabular row."""
    return format_locator(Locator(path=path, sheet=sheet, rows=(row, row)))


def candidate_flag(
    kind: str,
    path: str,
    sheet: str | None,
    row: int,
    **details: object,
) -> dict[str, object]:
    """Build a deterministic candidate with its exact row locator."""
    return {
        "kind": kind,
        "path": path,
        "sheet": sheet,
        "row": row,
        "locator": row_locator(path, sheet, row),
        **details,
    }
