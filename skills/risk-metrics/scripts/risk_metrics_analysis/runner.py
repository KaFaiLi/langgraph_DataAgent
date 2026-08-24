"""Ordered internal runner for the risk-metrics deterministic analysis battery."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from data_agent.tools.review_context import ToolContext

from .cross_source import _cross_source_consistency
from .dynamics import _metric_dynamics
from .integrity import _data_integrity
from .limits import _limit_consumption
from .sources import _excess_rows, _input_contract, _load_sources, _sgmr_rows
from .workflow import _excess_workflow


def run_analysis(ctx: ToolContext, source_paths: list[str]) -> Sequence[BaseModel]:
    """Run the complete deterministic finalized risk-metrics analysis battery."""
    tables, load_issues = _load_sources(ctx, source_paths)
    sgmr, sgmr_issues = _sgmr_rows(tables)
    excesses, excess_issues = _excess_rows(tables)
    parse_issues = [*sgmr_issues, *excess_issues]
    return [
        _input_contract(tables, load_issues, parse_issues, sgmr, excesses),
        _data_integrity(sgmr, excesses),
        _limit_consumption(sgmr),
        _metric_dynamics(sgmr),
        _excess_workflow(excesses, sgmr),
        _cross_source_consistency(sgmr, excesses),
    ]
