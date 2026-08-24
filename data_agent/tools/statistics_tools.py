"""Shared deterministic statistical primitives with FastMCP adapters.

The functions in this module are deliberately independent of MCP so that the
numeric behavior can be unit tested and reused by local analysis code.  The
``register`` function adds JSON-friendly adapters for the ten public tools;
model results are converted to plain dictionaries at that boundary.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, Field


class TrendResult(BaseModel):
    """Ordinary least-squares trend over an evenly spaced series."""

    slope: float
    intercept: float
    r_squared: float


class PeriodComparison(BaseModel):
    """Comparison of the means before and after a requested split."""

    mean_before: float | None
    mean_after: float | None
    pct_change: float | None


def _require_values(values: Sequence[float | None]) -> list[float]:
    """Convert a series to floats, dropping explicit null observations."""
    cleaned = [float(value) for value in values if value is not None]
    if len(cleaned) < 2:
        raise ValueError("at least two non-null values are required")
    return cleaned


def zscore(values: Sequence[float | None]) -> list[float]:
    """Return population z-scores, treating a constant series as all zeros."""
    cleaned = _require_values(values)
    mean = statistics.fmean(cleaned)
    stdev = statistics.pstdev(cleaned)
    if stdev == 0:
        return [0.0] * len(cleaned)
    return [(value - mean) / stdev for value in cleaned]


def rolling_mean(values: Sequence[float], window: int) -> list[float | None]:
    """Return trailing population means, with nulls during the warm-up."""
    if window < 1:
        raise ValueError("window must be >= 1")
    cleaned = list(values)
    out: list[float | None] = [None] * len(cleaned)
    for index in range(window - 1, len(cleaned)):
        out[index] = statistics.fmean(cleaned[index - window + 1 : index + 1])
    return out


def rolling_std(values: Sequence[float], window: int) -> list[float | None]:
    """Return trailing population standard deviations with warm-up nulls."""
    if window < 1:
        raise ValueError("window must be >= 1")
    cleaned = list(values)
    out: list[float | None] = [None] * len(cleaned)
    for index in range(window - 1, len(cleaned)):
        segment = cleaned[index - window + 1 : index + 1]
        if len(segment) == 1:
            out[index] = 0.0
        else:
            out[index] = statistics.pstdev(segment)
    return out


def quantile(values: Sequence[float], q: float) -> float:
    """Return a linearly interpolated quantile of a non-empty series."""
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("at least one value is required")
    position = q * (len(ordered) - 1)
    lower = int(position)
    if lower >= len(ordered) - 1:
        return ordered[-1]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[lower + 1] * fraction


def rolling_quantile(values: Sequence[float], window: int, q: float) -> list[float | None]:
    """Return trailing linearly interpolated quantiles with warm-up nulls."""
    if window < 1:
        raise ValueError("window must be >= 1")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    cleaned = list(values)
    out: list[float | None] = [None] * len(cleaned)
    for index in range(window - 1, len(cleaned)):
        segment = cleaned[index - window + 1 : index + 1]
        out[index] = quantile(segment, q)
    return out


def percent_change(values: Sequence[float]) -> list[float | None]:
    """Return absolute-denominator period-over-period changes."""
    cleaned = list(values)
    out: list[float | None] = [None] * len(cleaned)
    for index in range(1, len(cleaned)):
        previous = cleaned[index - 1]
        if previous == 0:
            out[index] = None
        else:
            out[index] = (cleaned[index] - previous) / abs(previous)
    return out


def outlier_detection(values: Sequence[float | None], z_threshold: float = 3.0) -> list[int]:
    """Return indices whose absolute population z-score exceeds a threshold."""
    if z_threshold <= 0:
        raise ValueError("z_threshold must be positive")
    scores = zscore(values)
    return [index for index, score in enumerate(scores) if abs(score) > z_threshold]


def change_point_candidates(
    values: Sequence[float],
    window: int = 20,
    z_threshold: float = 2.5,
) -> list[int]:
    """Return candidate level-shift indices from preceding-window deviations."""
    if window < 2:
        raise ValueError("window must be >= 2")
    cleaned = list(values)
    candidates: list[int] = []
    for index in range(window, len(cleaned)):
        history = cleaned[index - window : index]
        sigma = statistics.pstdev(history)
        if sigma == 0:
            continue
        mean = statistics.fmean(history)
        z = abs(cleaned[index] - mean) / sigma
        if z > z_threshold:
            candidates.append(index)
    return candidates


def pearson_correlation(a: Sequence[float | None], b: Sequence[float | None]) -> float:
    """Return Pearson correlation, ignoring pairs with either null value."""
    if len(a) != len(b):
        raise ValueError("series must have equal length")
    pairs = [
        (float(x), float(y)) for x, y in zip(a, b, strict=True) if x is not None and y is not None
    ]
    if len(pairs) < 2:
        raise ValueError("at least two aligned pairs are required")
    mean_x = statistics.fmean(x for x, _ in pairs)
    mean_y = statistics.fmean(y for _, y in pairs)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x, _ in pairs)
    var_y = sum((y - mean_y) ** 2 for _, y in pairs)
    if var_x == 0 or var_y == 0:
        return 0.0
    return covariance / math.sqrt(var_x * var_y)


def trend_analysis(values: Sequence[float | None]) -> TrendResult:
    """Return the slope, intercept, and R-squared of an evenly spaced series."""
    cleaned = _require_values(values)
    n = len(cleaned)
    xs = list(range(n))
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(cleaned)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, cleaned, strict=True))
    syy = sum((y - mean_y) ** 2 for y in cleaned)
    slope = 0.0 if sxx == 0 else sxy / sxx
    intercept = mean_y - slope * mean_x
    r_squared = 0.0 if syy == 0 else (sxy**2) / (sxx * syy) if sxx else 0.0
    return TrendResult(slope=slope, intercept=intercept, r_squared=r_squared)


def period_comparison(values: Sequence[float | None], split: int) -> PeriodComparison:
    """Return means and relative change for the two sides of a split."""
    cleaned = _require_values(values)
    if not 0 < split < len(cleaned):
        raise ValueError("split must be strictly inside the series")
    before = cleaned[:split]
    after = cleaned[split:]
    mean_before = statistics.fmean(before)
    mean_after = statistics.fmean(after)
    pct_change = None if mean_before == 0 else (mean_after - mean_before) / abs(mean_before)
    return PeriodComparison(mean_before=mean_before, mean_after=mean_after, pct_change=pct_change)


def register(mcp: FastMCP) -> None:
    """Attach the ten statistical tools to a FastMCP server."""

    @mcp.tool(name="zscore")
    def zscore_tool(
        values: Annotated[list[float | None], Field(description="Numeric series to standardize.")],
    ) -> list[float]:
        """Calculate population z-scores for a numeric series.

        Null observations are omitted; constant series return zeros.
        """
        return zscore(values)

    @mcp.tool(name="rolling_mean")
    def rolling_mean_tool(
        values: Annotated[list[float], Field(description="Numeric series.")],
        window: Annotated[int, Field(ge=1, description="Trailing window size.")],
    ) -> list[float | None]:
        """Calculate trailing means, returning nulls until the window is full."""
        return rolling_mean(values, window)

    @mcp.tool(name="rolling_std")
    def rolling_std_tool(
        values: Annotated[list[float], Field(description="Numeric series.")],
        window: Annotated[int, Field(ge=1, description="Trailing window size.")],
    ) -> list[float | None]:
        """Calculate trailing population standard deviations with warm-up nulls."""
        return rolling_std(values, window)

    @mcp.tool(name="rolling_quantile")
    def rolling_quantile_tool(
        values: Annotated[list[float], Field(description="Numeric series.")],
        window: Annotated[int, Field(ge=1, description="Trailing window size.")],
        q: Annotated[float, Field(ge=0.0, le=1.0, description="Quantile in [0, 1].")],
    ) -> list[float | None]:
        """Calculate trailing interpolated quantiles with warm-up nulls."""
        return rolling_quantile(values, window, q)

    @mcp.tool(name="percent_change")
    def percent_change_tool(
        values: Annotated[list[float], Field(description="Numeric series.")],
    ) -> list[float | None]:
        """Calculate period-over-period changes using an absolute denominator."""
        return percent_change(values)

    @mcp.tool(name="outlier_detection")
    def outlier_detection_tool(
        values: Annotated[list[float | None], Field(description="Numeric series to inspect.")],
        z_threshold: Annotated[
            float, Field(gt=0.0, description="Strict positive z-score threshold.")
        ] = 3.0,
    ) -> list[int]:
        """Return indices with absolute z-scores above the given threshold."""
        return outlier_detection(values, z_threshold)

    @mcp.tool(name="change_point_candidates")
    def change_point_candidates_tool(
        values: Annotated[list[float], Field(description="Numeric series.")],
        window: Annotated[int, Field(ge=2, description="Preceding history size.")] = 20,
        z_threshold: Annotated[
            float, Field(description="Strict z-score candidate threshold.")
        ] = 2.5,
    ) -> list[int]:
        """Return candidate level-shift indices for verifier review."""
        return change_point_candidates(values, window, z_threshold)

    @mcp.tool(name="pearson_correlation")
    def pearson_correlation_tool(
        a: Annotated[list[float | None], Field(description="First numeric series.")],
        b: Annotated[list[float | None], Field(description="Second numeric series.")],
    ) -> float:
        """Calculate Pearson correlation for equal-length aligned series."""
        return pearson_correlation(a, b)

    @mcp.tool(name="trend_analysis")
    def trend_analysis_tool(
        values: Annotated[list[float | None], Field(description="Numeric series.")],
    ) -> dict[str, float]:
        """Calculate least-squares slope, intercept, and R-squared."""
        return trend_analysis(values).model_dump()

    @mcp.tool(name="period_comparison")
    def period_comparison_tool(
        values: Annotated[list[float | None], Field(description="Numeric series.")],
        split: Annotated[int, Field(description="Strict interior split index.")],
    ) -> dict[str, float | None]:
        """Compare means and relative change before and after a split."""
        return period_comparison(values, split).model_dump()


__all__ = [
    "PeriodComparison",
    "TrendResult",
    "change_point_candidates",
    "outlier_detection",
    "pearson_correlation",
    "percent_change",
    "period_comparison",
    "quantile",
    "register",
    "rolling_mean",
    "rolling_quantile",
    "rolling_std",
    "trend_analysis",
    "zscore",
]
