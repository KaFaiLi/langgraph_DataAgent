"""Behavioral tests for deterministic specialist data overviews."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.overview import (
    DataOverview,
    LineVisual,
    OverviewMetric,
    OverviewPoint,
    OverviewSeries,
    OverviewStatus,
)
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.source import DateRange
from data_agent.review.reporting.markdown import render_specialist_report


def _pnl_overview() -> DataOverview:
    return DataOverview(
        overview_id="pnl.cumulative-by-year",
        domain=SpecialistDomain.PNL,
        source_family="pnl",
        title="Cumulative PnL by calendar year",
        summary="Daily DTD PnL is accumulated from zero within each calendar year.",
        status=OverviewStatus.AVAILABLE,
        primary_for_deck=True,
        metrics=[
            OverviewMetric(
                label="2025 total",
                value="3.0",
                unit="USDm",
                basis="calendar-year cumulative DTD",
            )
        ],
        visual=LineVisual(
            x_label="Business date",
            y_label="Cumulative PnL",
            unit="USDm",
            series=[
                OverviewSeries(
                    name="2025",
                    points=[
                        OverviewPoint(label="2025-01-02", value=1.0),
                        OverviewPoint(label="2025-01-03", value=3.0),
                    ],
                )
            ],
        ),
        evidence=[EvidenceReference(locator="source://pnl/pnl.csv#rows=2:3")],
        limitations=["One documented PTF/currency series; no cross-currency aggregation."],
    )


def test_data_overview_has_stable_fingerprint_and_requires_evidence() -> None:
    overview = _pnl_overview()

    dumped = overview.model_dump(mode="json")
    assert dumped["data_fingerprint"] == overview.data_fingerprint
    assert DataOverview.model_validate(dumped).data_fingerprint == overview.data_fingerprint

    with pytest.raises(ValueError, match="evidence"):
        DataOverview(
            overview_id="pnl.unsourced",
            domain=SpecialistDomain.PNL,
            source_family="pnl",
            title="Unsourced",
            summary="No source.",
            status=OverviewStatus.AVAILABLE,
            visual=LineVisual(
                x_label="Date",
                y_label="PnL",
                series=[
                    OverviewSeries(
                        name="2025",
                        points=[OverviewPoint(label="2025-01-02", value=1.0)],
                    )
                ],
            ),
        )


def test_specialist_report_preserves_and_renders_data_overview() -> None:
    report = SpecialistReport(
        domain=SpecialistDomain.PNL,
        report_id="PNL",
        title="PnL Review",
        review_period=DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30)),
        generated_at=datetime(2026, 7, 1, tzinfo=UTC),
        scope="Finalized PnL bundle.",
        data_overviews=[_pnl_overview()],
        overall_conclusion="No conclusion for this contract test.",
    )

    restored = SpecialistReport.model_validate(report.model_dump(mode="json"))
    assert restored.data_overviews[0].visual.kind == "line"
    markdown = render_specialist_report(restored)
    assert markdown.index("## Data Overview") < markdown.index("## Findings")
    assert "### Cumulative PnL by calendar year" in markdown
    assert "| 2025 | 2 | 1 | 3 | 1 | 3 |" in markdown
    assert "`source://pnl/pnl.csv#rows=2:3`" in markdown


def test_specialist_report_rejects_duplicate_overview_ids() -> None:
    with pytest.raises(ValueError, match="duplicate overview"):
        SpecialistReport(
            domain=SpecialistDomain.PNL,
            report_id="PNL",
            title="PnL Review",
            review_period=DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30)),
            generated_at=datetime(2026, 7, 1, tzinfo=UTC),
            scope="Finalized PnL bundle.",
            data_overviews=[_pnl_overview(), _pnl_overview()],
            overall_conclusion="No conclusion for this contract test.",
        )
