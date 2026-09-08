"""Ordered internal runner for the risk-metrics deterministic analysis battery."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from data_agent.tools.analysis_receipts import attach_execution
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
    results = [
        _input_contract(tables, load_issues, parse_issues, sgmr, excesses),
        _data_integrity(sgmr, excesses),
        _limit_consumption(sgmr),
        _metric_dynamics(sgmr),
        _excess_workflow(excesses, sgmr),
        _cross_source_consistency(sgmr, excesses),
    ]
    issues = [*load_issues, *parse_issues]
    return attach_execution(
        results,
        ctx,
        source_paths,
        rows_processed=len(sgmr) + len(excesses),
        rows_rejected=len(issues),
        issue_codes=[str(issue.get("kind", "parse_failure")) for issue in issues],
        calculation_basis="typed SGMR and excess-workflow rows",
    )
