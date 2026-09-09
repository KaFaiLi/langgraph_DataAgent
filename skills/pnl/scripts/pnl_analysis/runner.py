"""Ordered internal runner for the composite PnL deterministic analysis battery."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from pydantic import BaseModel

from data_agent.review.domain.analysis import AnalysisExecution, AnalysisStatus
from data_agent.review.domain.source import DateRange
from data_agent.tools.analysis_receipts import population_receipt
from data_agent.tools.review_context import ToolContext

from .adjustments import _adjustment_controls
from .attribution import run_income_attribution_analyses
from .attribution_wide import (
    _income_attribution_driver_profile,
    _income_attribution_reconciliation,
    _income_attribution_schema,
    _income_attribution_status,
    _persistent_income_attribution,
)
from .pnl import _pnl_integrity, _pnl_patterns
from .shared import (
    AnalysisResult,
)
from .sources import (
    _adjustment_rows,
    _income_attribution_rows,
    _load_sources,
    _pnl_rows,
    _validation_rows,
)
from .validation import _input_contract, _validation_and_reconciliation


def run_analysis(ctx: ToolContext, source_paths: list[str]) -> Sequence[BaseModel]:
    """Run every deterministic check for the finalized PnL review bundle."""
    tables, load_issues = _load_sources(ctx, source_paths)
    pnl, pnl_issues = _pnl_rows(tables)
    adjustments, adjustment_issues = _adjustment_rows(tables)
    validation, validation_issues = _validation_rows(tables)
    income_attribution, income_issues = _income_attribution_rows(tables)
    before_scope = {
        "pnl": len(pnl),
        "adjustment": len(adjustments),
        "validation": len(validation),
        "income_attribution": len(income_attribution),
    }
    calculation_pnl = pnl
    if ctx.review_period is not None:
        start, end = ctx.review_period.start, ctx.review_period.end
        pnl = [row for row in pnl if start <= row.day <= end]
        adjustments = [
            row for row in adjustments if row.value_start <= end and row.value_end >= start
        ]
        validation = [row for row in validation if start <= row.request_date <= end]
        income_attribution = [row for row in income_attribution if start <= row.day <= end]
    legacy_income_paths = list(
        dict.fromkeys(table.path for table in tables if table.role == "income_attribution_legacy")
    )
    parse_issues = [*pnl_issues, *adjustment_issues, *validation_issues]
    results: list[AnalysisResult] = [
        _input_contract(
            tables,
            load_issues,
            parse_issues,
            pnl,
            adjustments,
            validation,
            income_attribution,
            income_issues,
        ),
        _pnl_integrity(calculation_pnl),
        _pnl_patterns(pnl),
        _adjustment_controls(adjustments, pnl),
        _validation_and_reconciliation(validation, pnl, adjustments),
    ]
    if ctx.review_period is not None:
        integrity = results[1]

        def _reportable(candidate: dict[str, object]) -> bool:
            raw = candidate.get("date") or candidate.get("day")
            try:
                day = date.fromisoformat(str(raw)[:10])
            except ValueError:
                return True
            return ctx.review_period.start <= day <= ctx.review_period.end

        results[1] = integrity.model_copy(
            update={
                "flag_candidates": [item for item in integrity.flag_candidates if _reportable(item)]
            }
        )
    if any(table.role == "income_attribution" for table in tables):
        results.extend(
            [
                _income_attribution_schema(income_attribution, tables, income_issues),
                _income_attribution_driver_profile(income_attribution),
                _persistent_income_attribution(income_attribution),
                _income_attribution_reconciliation(income_attribution),
                _income_attribution_status(income_attribution),
            ]
        )
    if legacy_income_paths:
        results.extend(run_income_attribution_analyses(ctx, legacy_income_paths))
    role_rows = {
        "pnl": pnl,
        "adjustment": adjustments,
        "validation": validation,
        "income_attribution": income_attribution,
    }
    analysis_roles = {
        "pnl_input_contract": tuple(role_rows),
        "pnl_cumulative_integrity": ("pnl",),
        "pnl_statistical_patterns": ("pnl",),
        "pnl_adjustment_controls": ("adjustment",),
        "pnl_validation_and_reconciliation": ("validation", "pnl", "adjustment"),
        "income_attribution_schema": ("income_attribution",),
        "income_attribution_driver_profile": ("income_attribution",),
        "income_attribution_persistence": ("income_attribution",),
        "income_attribution_reconciliation": ("income_attribution",),
        "income_attribution_status": ("income_attribution",),
    }
    paths_by_role = {
        role: [table.path for table in tables if table.role == role] for role in role_rows
    }
    rows_read_by_role = {
        role: sum(table.frame.height for table in tables if table.role == role)
        for role in role_rows
    }
    unrecognized_rows = sum(
        int(issue.get("rows_read", 0))
        for issue in load_issues
        if issue.get("kind") == "unrecognized_pnl_table"
    )
    issue_codes = [
        str(issue.get("kind", "parse_failure"))
        for issue in [*load_issues, *parse_issues, *income_issues]
    ]
    enriched: list[AnalysisResult] = []
    for result in results:
        if result.execution is not None:
            enriched.append(result)
            continue
        roles = analysis_roles.get(result.name)
        if roles is None:  # Legacy attribution has its own stable analysis contract.
            roles = ("income_attribution",)
        processed = sum(len(role_rows[role]) for role in roles)
        excluded = sum(before_scope[role] - len(role_rows[role]) for role in roles)
        paths = [path for role in roles for path in paths_by_role[role]]
        rows_read = sum(rows_read_by_role[role] for role in roles)
        rejected = max(rows_read - sum(before_scope[role] for role in roles), 0)
        relevant_issues = issue_codes if result.name == "pnl_input_contract" else []
        if result.name == "pnl_input_contract":
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
            getattr(row, "day", getattr(row, "request_date", None))
            for role in roles
            for row in role_rows[role]
        ]
        days = [day for day in days if day is not None]
        actual_range = DateRange(start=min(days), end=max(days)) if days else None
        execution = AnalysisExecution(
            status=status,
            population=population_receipt(
                ctx,
                paths,
                dataset_id="pnl:" + "+".join(roles),
                rows_read=rows_read,
                rows_processed=processed,
                rows_rejected=rejected,
                rows_excluded=excluded,
                exclusion_reasons={"outside_reporting_period": excluded} if excluded else {},
                actual_date_range=actual_range,
                calculation_basis="typed rows within the configured reporting period",
                issues=relevant_issues,
            ),
            issue_codes=relevant_issues,
        )
        enriched.append(result.model_copy(update={"execution": execution}))
    return enriched
