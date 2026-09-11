"""Ordered internal runner for the risk-metrics deterministic analysis battery."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisExecution, AnalysisStatus
from data_agent.review.domain.source import DateRange
from data_agent.tools.analysis_receipts import population_receipt
from data_agent.tools.review_context import ToolContext

from .cross_source import _cross_source_consistency
from .dynamics import _metric_dynamics
from .integrity import _data_integrity
from .limits import _limit_consumption
from .sources import _excess_rows, _input_contract, _load_sources, _sgmr_rows
from .workflow import _excess_workflow


def run_analysis(
    ctx: ToolContext, source_paths: list[str], *, analysis_names: tuple[str, ...]
) -> Sequence[BaseModel]:
    """Run the complete deterministic finalized risk-metrics analysis battery."""
    tables, load_issues = _load_sources(ctx, source_paths)
    sgmr, sgmr_issues = _sgmr_rows(tables)
    excesses, excess_issues = _excess_rows(tables)
    before_scope = {"sgmr": len(sgmr), "colibris": len(excesses)}
    if ctx.review_period is not None:
        start, end = ctx.review_period.start, ctx.review_period.end
        sgmr = [row for row in sgmr if start <= row.day <= end]
        excesses = [row for row in excesses if start <= row.value_day <= end]
    parse_issues = [*sgmr_issues, *excess_issues]
    results = [
        _input_contract(tables, load_issues, parse_issues, sgmr, excesses),
        _data_integrity(sgmr, excesses),
        _limit_consumption(sgmr),
        _metric_dynamics(sgmr),
        _excess_workflow(excesses, sgmr),
        _cross_source_consistency(sgmr, excesses),
    ]
    rows = {"sgmr": sgmr, "colibris": excesses}
    analysis_roles = {
        "risk_metrics_input_contract": ("sgmr", "colibris"),
        "risk_metrics_data_integrity": ("sgmr", "colibris"),
        "risk_limit_consumption": ("sgmr",),
        "risk_metric_dynamics": ("sgmr",),
        "risk_excess_workflow": ("colibris", "sgmr"),
        "risk_cross_source_consistency": ("sgmr", "colibris"),
    }
    table_rows = {
        role: sum(table.frame.height for table in tables if table.role == role) for role in rows
    }
    paths_by_role = {role: [table.path for table in tables if table.role == role] for role in rows}
    issue_codes = [
        str(issue.get("kind", "parse_failure")) for issue in [*load_issues, *parse_issues]
    ]
    unrecognized_rows = sum(int(issue.get("rows_read", 0)) for issue in load_issues)
    enriched = []
    for result in results:
        roles = analysis_roles[result.name]
        rows_read = sum(table_rows[role] for role in roles)
        processed = sum(len(rows[role]) for role in roles)
        excluded = sum(before_scope[role] - len(rows[role]) for role in roles)
        rejected = max(rows_read - processed - excluded, 0)
        paths = [path for role in roles for path in paths_by_role[role]]
        relevant_issues = issue_codes if result.name == "risk_metrics_input_contract" else []
        if result.name == "risk_metrics_input_contract":
            paths = list(source_paths)
            rows_read += unrecognized_rows
            rejected += unrecognized_rows
        status = (
            AnalysisStatus.UNAVAILABLE
            if not paths or relevant_issues
            else AnalysisStatus.EMPTY
            if processed == 0
            else AnalysisStatus.SUCCEEDED
        )
        days = [
            row.day if role == "sgmr" else row.value_day for role in roles for row in rows[role]
        ]
        enriched.append(
            result.model_copy(
                update={
                    "execution": AnalysisExecution(
                        status=status,
                        population=population_receipt(
                            ctx,
                            paths,
                            dataset_id="risk_metrics:" + "+".join(roles),
                            rows_read=rows_read,
                            rows_processed=processed,
                            rows_rejected=rejected,
                            rows_excluded=excluded,
                            exclusion_reasons={"outside_reporting_period": excluded}
                            if excluded
                            else {},
                            actual_date_range=(
                                DateRange(start=min(days), end=max(days)) if days else None
                            ),
                            calculation_basis="typed risk-metric rows by source role",
                            observations_produced=processed,
                            issues=relevant_issues,
                        ),
                        issue_codes=relevant_issues,
                    )
                }
            )
        )
    available = {result.name for result in enriched}
    unknown = set(analysis_names) - available
    if unknown:
        raise ValueError(f"unknown risk-metrics analyses requested: {sorted(unknown)}")
    return [result for result in enriched if result.name in analysis_names]
