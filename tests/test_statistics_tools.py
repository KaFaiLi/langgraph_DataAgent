"""Behavior tests for the migrated statistical MCP tools."""

from __future__ import annotations

import pytest

from data_agent.tools import statistics_tools

SERIES = [1.0, 2.0, 3.0, 4.0, 5.0]


def test_zscore_uses_population_standard_deviation() -> None:
    scores = statistics_tools.zscore(SERIES)

    assert scores[0] == pytest.approx(-2 / (2**0.5))
    assert scores[-1] == pytest.approx(2 / (2**0.5))


def test_zscore_constant_and_null_values() -> None:
    assert statistics_tools.zscore([7.0, 7.0, 7.0]) == [0.0, 0.0, 0.0]
    assert statistics_tools.zscore([1.0, None, 3.0]) == pytest.approx([-1.0, 1.0])


def test_rolling_mean_returns_warmup_nulls() -> None:
    assert statistics_tools.rolling_mean(SERIES, 3) == [None, None, 2.0, 3.0, 4.0]
    assert statistics_tools.rolling_mean(SERIES, 10) == [None] * len(SERIES)


def test_rolling_std_uses_population_standard_deviation() -> None:
    assert statistics_tools.rolling_std(SERIES, 2) == [None, 0.5, 0.5, 0.5, 0.5]
    assert statistics_tools.rolling_std([4.0], 1) == [0.0]


def test_quantile_interpolates_and_rolling_quantile() -> None:
    assert statistics_tools.quantile([4.0, 1.0, 3.0, 2.0], 0.25) == pytest.approx(1.75)
    assert statistics_tools.rolling_quantile(SERIES, 3, 0.5) == [
        None,
        None,
        2.0,
        3.0,
        4.0,
    ]


def test_percent_change_handles_initial_and_zero_previous_values() -> None:
    assert statistics_tools.percent_change([1.0, 2.0, 3.0]) == [
        None,
        pytest.approx(1.0),
        pytest.approx(0.5),
    ]
    assert statistics_tools.percent_change([0.0, 2.0, 1.0]) == [None, None, -0.5]


def test_outlier_detection_returns_indices_above_strict_threshold() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 100.0]

    assert statistics_tools.outlier_detection(values, z_threshold=1.5) == [4]
    assert statistics_tools.outlier_detection(values, z_threshold=3.0) == []


def test_change_point_candidates_find_level_shift() -> None:
    values = [0.0] * 30 + [10.0] * 10

    candidates = statistics_tools.change_point_candidates(values, window=10, z_threshold=2.5)

    assert candidates
    assert all(29 <= index <= 34 for index in candidates)
    assert statistics_tools.change_point_candidates([1.0] * 10, window=2) == []


def test_pearson_correlation_and_null_pair_filtering() -> None:
    assert statistics_tools.pearson_correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(
        1.0
    )
    assert statistics_tools.pearson_correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(
        -1.0
    )
    assert statistics_tools.pearson_correlation(
        [1.0, None, 3.0], [2.0, 100.0, 6.0]
    ) == pytest.approx(1.0)
    assert statistics_tools.pearson_correlation([5.0, 5.0], [1.0, 2.0]) == 0.0


def test_trend_analysis_returns_ordinary_least_squares_result() -> None:
    trend = statistics_tools.trend_analysis([1.0, 2.0, 3.0])

    assert trend.slope == pytest.approx(1.0)
    assert trend.intercept == pytest.approx(1.0)
    assert trend.r_squared == pytest.approx(1.0)


def test_period_comparison_compares_contiguous_periods() -> None:
    comparison = statistics_tools.period_comparison([1.0, 1.0, 1.0, 3.0, 3.0, 3.0], split=3)

    assert comparison.mean_before == pytest.approx(1.0)
    assert comparison.mean_after == pytest.approx(3.0)
    assert comparison.pct_change == pytest.approx(2.0)
    assert statistics_tools.period_comparison([0.0, 0.0, 2.0, 2.0], 2).pct_change is None


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: statistics_tools.zscore([1.0]), "at least two"),
        (lambda: statistics_tools.zscore([None, None]), "at least two"),
        (lambda: statistics_tools.rolling_mean(SERIES, 0), "window"),
        (lambda: statistics_tools.rolling_std(SERIES, 0), "window"),
        (lambda: statistics_tools.quantile(SERIES, -0.1), "between"),
        (lambda: statistics_tools.quantile([], 0.5), "at least one"),
        (lambda: statistics_tools.rolling_quantile(SERIES, 0, 0.5), "window"),
        (lambda: statistics_tools.rolling_quantile(SERIES, 2, 1.5), "between"),
        (lambda: statistics_tools.outlier_detection(SERIES, 0), "positive"),
        (lambda: statistics_tools.change_point_candidates(SERIES, 1), "window"),
        (lambda: statistics_tools.pearson_correlation([1.0], [1.0, 2.0]), "equal"),
        (lambda: statistics_tools.pearson_correlation([1.0], [2.0]), "aligned"),
        (lambda: statistics_tools.trend_analysis([1.0]), "at least two"),
        (lambda: statistics_tools.period_comparison(SERIES, 0), "strictly"),
        (lambda: statistics_tools.period_comparison(SERIES, len(SERIES)), "strictly"),
    ],
)
def test_invalid_arguments_raise_value_error(call, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()


@pytest.mark.asyncio
async def test_register_exposes_exactly_ten_json_friendly_tools() -> None:
    from fastmcp import FastMCP

    mcp = FastMCP("statistics-test")
    statistics_tools.register(mcp)
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    expected = {
        "zscore",
        "rolling_mean",
        "rolling_std",
        "rolling_quantile",
        "percent_change",
        "outlier_detection",
        "change_point_candidates",
        "pearson_correlation",
        "trend_analysis",
        "period_comparison",
    }
    assert set(tools) == expected

    trend = await tools["trend_analysis"].run(arguments={"values": [1.0, 2.0, 3.0]})
    comparison = await tools["period_comparison"].run(
        arguments={"values": [1.0, 1.0, 3.0, 3.0], "split": 2}
    )
    assert trend.structured_content == {
        "slope": 1.0,
        "intercept": 1.0,
        "r_squared": 1.0,
    }
    assert comparison.structured_content == {
        "mean_before": 1.0,
        "mean_after": 3.0,
        "pct_change": 2.0,
    }
