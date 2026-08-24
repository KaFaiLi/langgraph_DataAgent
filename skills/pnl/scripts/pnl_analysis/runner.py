"""Ordered internal runner for the composite PnL deterministic analysis battery."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

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
        _pnl_integrity(pnl),
        _pnl_patterns(pnl),
        _adjustment_controls(adjustments, pnl),
        _validation_and_reconciliation(validation, pnl, adjustments),
    ]
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
    return results
