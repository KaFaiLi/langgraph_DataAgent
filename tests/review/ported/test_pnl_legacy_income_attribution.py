"""Legacy income-attribution behavior through the composite PnL skill seam."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from tests.review.fixtures.builder import make_csv

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.skills.review import discover_skills, load_analysis_runner
from data_agent.tools.review_context import ToolContext

ATTRIBUTION_PATH = "income_attribution/attribution.csv"
_DAYS = 40
_SPLIT = _DAYS // 2
_MISMATCH_INDEX = 25
_MISMATCH_PNL = 12.0
_FIRST_HALF = {"carry": 5.0, "vol": 0.5, "residual": 0.2, "hedge": 0.1}
_SECOND_HALF = {"carry": 1.0, "vol": 4.5, "residual": 0.2, "hedge": 0.1}
_LEGACY_NAMES = [
    "driver_concentration",
    "unexpected_drivers",
    "income_source_shifts",
    "risk_consistency",
    "risk_pnl_mismatch",
]


def _day(index: int) -> str:
    return (date(2025, 1, 2) + timedelta(days=index)).isoformat()


def _legacy_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(_DAYS):
        amounts = _FIRST_HALF if index < _SPLIT else _SECOND_HALF
        for driver, amount in amounts.items():
            rows.append(
                {
                    "date": _day(index),
                    "driver": driver,
                    "pnl_musd": _MISMATCH_PNL
                    if index == _MISMATCH_INDEX and driver == "hedge"
                    else amount,
                    "var": 4.0,
                }
            )
    return rows


@pytest.fixture()
def legacy_context(tmp_path: Path) -> ToolContext:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    (source / "income_attribution").mkdir(parents=True)
    workspace.mkdir()
    make_csv(source / ATTRIBUTION_PATH, _legacy_rows())
    return ToolContext(
        source_root=source,
        workspace_root=workspace,
        manifest=build_catalog(source),
    )


def _legacy_results(ctx: ToolContext) -> list[object]:
    definition = next(
        skill for skill in discover_skills() if skill.domain is SpecialistDomain.PNL
    )
    runner = load_analysis_runner(definition)
    results = runner(ctx, [ATTRIBUTION_PATH])
    return [result for result in results if result.name in _LEGACY_NAMES]


def test_composite_pnl_skill_preserves_legacy_attribution_order_and_locator(
    legacy_context: ToolContext,
) -> None:
    results = _legacy_results(legacy_context)

    assert [result.name for result in results] == _LEGACY_NAMES
    concentration = results[0]
    assert concentration.tables[0]["drivers"] == 4
    assert concentration.overviews[0].source_locators == [
        "source://income_attribution/attribution.csv#rows=2:161"
    ]


def test_composite_pnl_skill_preserves_legacy_attribution_flags(
    legacy_context: ToolContext,
) -> None:
    results = {result.name: result for result in _legacy_results(legacy_context)}

    shift_drivers = {flag["driver"] for flag in results["income_source_shifts"].flag_candidates}
    mismatch = results["risk_pnl_mismatch"].flag_candidates

    assert shift_drivers == {"carry", "vol"}
    assert mismatch[0]["date"] == _day(_MISMATCH_INDEX)
    assert float(mismatch[0]["pnl"]) == pytest.approx(_MISMATCH_PNL)
