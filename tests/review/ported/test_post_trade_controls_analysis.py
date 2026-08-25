"""Deterministic post-trade controls analysis tests over a planted breach log."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.skills.registry import get_specialist
from data_agent.skills.review import load_analysis_runner
from data_agent.tools.review_context import ToolContext
from tests.review.fixtures.builder import make_csv

run_post_trade_controls_analyses = load_analysis_runner(
    get_specialist(SpecialistDomain.POST_TRADE_CONTROLS).skill
)

BREACH_PATH = "post_trade_controls/breaches.csv"
NO_APPROVAL_PATH = "post_trade_controls/breaches_no_approval.csv"
MISC_PATH = "post_trade_controls/notes.csv"

# breach_date, product, severity, approved_by, closed_date, override_by
_LOG: list[tuple[str, str, str, str, str, str]] = [
    ("2025-01-06", "FXOPT", "low", "ops_a", "2025-01-07", ""),
    ("2025-01-08", "IRS", "low", "ops_a", "2025-01-09", ""),
    ("2025-01-10", "FXOPT", "low", "ops_b", "2025-01-11", ""),
    ("2025-01-14", "EQD", "low", "ops_a", "2025-01-16", ""),
    ("2025-01-16", "FXOPT", "medium", "", "2025-01-19", "trader_a"),
    ("2025-01-20", "CMD", "low", "ops_b", "2025-01-22", ""),
    ("2025-02-03", "FXOPT", "high", "ops_a", "2025-02-07", "trader_a"),
    ("2025-02-05", "IRS", "high", "", "2025-02-10", "trader_a"),
    ("2025-02-10", "EQD", "high", "ops_b", "2025-02-16", ""),
    ("2025-02-14", "FXOPT", "high", "ops_a", "2025-02-21", "trader_b"),
    ("2025-02-18", "CMD", "medium", "ops_b", "2025-02-26", ""),
    ("2025-02-24", "MM", "high", "ops_a", "2025-03-05", ""),
]


def _breach_rows() -> list[dict]:
    return [
        {
            "breach_date": breach_date,
            "product": product,
            "severity": severity,
            "approved_by": approver,
            "closed_date": closed_date,
            "override_by": override,
        }
        for breach_date, product, severity, approver, closed_date, override in _LOG
    ]


def _durations() -> list[int]:
    return [
        (date.fromisoformat(row["closed_date"]) - date.fromisoformat(row["breach_date"])).days
        for row in _breach_rows()
    ]


@pytest.fixture()
def ctx(tmp_path: Path) -> ToolContext:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    (source / "post_trade_controls").mkdir(parents=True)
    workspace.mkdir()
    directory = source / "post_trade_controls"
    make_csv(directory / "breaches.csv", _breach_rows())
    make_csv(
        directory / "breaches_no_approval.csv",
        [
            {"breach_date": "2025-01-06", "product": "FXOPT", "severity": "low"},
            {"breach_date": "2025-01-09", "product": "IRS", "severity": "high"},
        ],
    )
    make_csv(
        directory / "notes.csv",
        [{"date": "2025-01-02", "note": "narrative without any control columns"}],
    )
    return ToolContext(
        source_root=source,
        workspace_root=workspace,
        manifest=build_catalog(source),
    )


def _results(ctx: ToolContext, path: str = BREACH_PATH) -> dict:
    return {analysis.name: analysis for analysis in run_post_trade_controls_analyses(ctx, [path])}


def test_full_battery_runs(ctx: ToolContext) -> None:
    results = run_post_trade_controls_analyses(ctx, [BREACH_PATH])
    assert [analysis.name for analysis in results] == [
        "repeated_breaches",
        "product_recurrence",
        "resolution_time",
        "approval_gaps",
        "override_patterns",
        "severity_changes",
    ]
    assert all(analysis.summary for analysis in results)
    assert all(analysis.tables for analysis in results)


def test_all_analyses_deterministic(ctx: ToolContext) -> None:
    first = run_post_trade_controls_analyses(ctx, [BREACH_PATH])
    second = run_post_trade_controls_analyses(ctx, [BREACH_PATH])
    assert [a.model_dump(mode="json") for a in first] == [a.model_dump(mode="json") for a in second]


def test_repeated_breaches_only_for_recurring_product(ctx: ToolContext) -> None:
    result = _results(ctx)["repeated_breaches"]
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table["product"] == "FXOPT"
    assert table["occurrences"] == 5
    assert table["first_date"] == "2025-01-06"
    assert table["last_date"] == "2025-02-14"
    flags = result.flag_candidates
    assert len(flags) == 1
    assert flags[0]["kind"] == "repeated_breaches"
    assert flags[0]["product"] == "FXOPT"
    assert flags[0]["date"] == "2025-02-14"


def test_control_population_overviews_are_preserved(ctx: ToolContext) -> None:
    result = _results(ctx)["repeated_breaches"]
    primary = next(view for view in result.overviews if view.primary_for_deck)
    product = next(
        view
        for view in result.overviews
        if view.overview_id == "post-trade-controls.breaches-by-product"
    )

    assert primary.overview_id == "post-trade-controls.breaches-over-time"
    assert primary.visual is not None
    assert primary.visual.kind == "stacked_bar"
    assert [point.label for point in primary.visual.series[0].points] == [
        "2025-01",
        "2025-02",
    ]
    metrics = {metric.label: metric.value for metric in primary.metrics}
    assert metrics == {
        "Breaches": "12",
        "Approval gaps": "2 (16.67%)",
        "Resolved": "12 (100.00%)",
        "Mean closure": "4.08 days",
    }
    assert product.visual is not None
    assert product.visual.kind == "bar"
    assert [(point.label, point.value) for point in product.visual.series[0].points] == [
        ("FXOPT", 5.0),
        ("CMD", 2.0),
        ("EQD", 2.0),
        ("IRS", 2.0),
        ("MM", 1.0),
    ]
    assert primary.source_locators == ["source://post_trade_controls/breaches.csv#rows=2:13"]


def test_product_recurrence_counts_and_cluster(ctx: ToolContext) -> None:
    result = _results(ctx)["product_recurrence"]
    counts = {table["product"]: table["occurrences"] for table in result.tables}
    assert counts == {"FXOPT": 5, "IRS": 2, "EQD": 2, "CMD": 2, "MM": 1}
    assert result.tables[0]["product"] == "FXOPT"  # most frequent first
    assert result.tables[0]["distinct_days"] == 5
    clusters = result.flag_candidates
    assert len(clusters) == 1
    assert clusters[0]["kind"] == "recurrence_cluster"
    assert clusters[0]["product"] == "FXOPT"
    assert clusters[0]["window_start"] == "2025-01-06"
    assert clusters[0]["date"] == "2025-01-16"
    assert clusters[0]["span_days"] == 10


def test_resolution_time_and_trend(ctx: ToolContext) -> None:
    durations = _durations()
    result = _results(ctx)["resolution_time"]
    table = result.tables[0]
    assert table["resolved_breaches"] == len(durations)
    assert table["mean_days"] == pytest.approx(sum(durations) / len(durations), abs=1e-4)
    assert table["max_days"] == pytest.approx(max(durations))
    assert table["days_beyond_t2"] == sum(1 for value in durations if value > 2)
    assert float(table["trend_slope"]) > 0
    slow = [f for f in result.flag_candidates if f["kind"] == "slow_resolution"]
    assert len(slow) == sum(1 for value in durations if value > 2)
    assert all(int(f["resolution_days"]) > 2 for f in slow)
    assert any(f["kind"] == "resolution_time_trend_up" for f in result.flag_candidates)


def test_approval_gaps_flagged(ctx: ToolContext) -> None:
    result = _results(ctx)["approval_gaps"]
    table = result.tables[0]
    assert table["approval_column"] == "approved_by"
    assert table["rows"] == len(_LOG)
    assert table["approval_gaps"] == 2
    assert float(table["gap_share"]) == pytest.approx(2 / len(_LOG), abs=1e-4)
    flags = result.flag_candidates
    assert {f["date"] for f in flags} == {"2025-01-16", "2025-02-05"}
    assert all(f["kind"] == "approval_gap" for f in flags)


def test_missing_approval_column_flagged(ctx: ToolContext) -> None:
    result = _results(ctx, NO_APPROVAL_PATH)["approval_gaps"]
    flags = result.flag_candidates
    assert len(flags) == 1
    assert flags[0]["kind"] == "approval_column_missing"
    assert flags[0]["rows"] == 2
    assert result.tables[0]["gap_share"] == pytest.approx(1.0)


def test_override_patterns_flag_top_overrider(ctx: ToolContext) -> None:
    result = _results(ctx)["override_patterns"]
    table = result.tables[0]
    assert table["override_column"] == "override_by"
    assert table["overrides"] == 4
    assert table["by_user"] == [
        {"user": "trader_a", "overrides": 3, "share": 0.75},
        {"user": "trader_b", "overrides": 1, "share": 0.25},
    ]
    top = [f for f in result.flag_candidates if f["kind"] == "top_overrider"]
    repeated = [f for f in result.flag_candidates if f["kind"] == "repeated_override"]
    assert len(top) == 1
    assert top[0]["user"] == "trader_a"
    assert top[0]["overrides"] == 3
    assert top[0]["date"] == "2025-02-05"  # last breach that user overrode
    assert [f["user"] for f in repeated] == ["trader_a"]


def test_severity_mix_shift_flagged(ctx: ToolContext) -> None:
    result = _results(ctx)["severity_changes"]
    table = result.tables[0]
    assert table["breaches"] == len(_LOG)
    assert table["first_half"] == "2025-01-06..2025-01-20"
    assert table["second_half"] == "2025-02-03..2025-02-24"
    shares = {row["severity"]: row for row in table["severity_shares"]}
    assert shares["low"]["first_half_share"] == pytest.approx(5 / 6, abs=1e-4)
    assert shares["high"]["second_half_share"] == pytest.approx(5 / 6, abs=1e-4)
    assert shares["medium"]["shift"] == pytest.approx(0.0)
    flags = result.flag_candidates
    assert {f["severity"] for f in flags} == {"low", "high"}
    assert all(f["date"] == "2025-02-03" for f in flags)


def test_file_without_control_columns_is_skipped(ctx: ToolContext) -> None:
    results = run_post_trade_controls_analyses(ctx, [MISC_PATH])
    assert len(results) == 6
    assert all(not analysis.tables for analysis in results)
    assert all(not analysis.flag_candidates for analysis in results)
