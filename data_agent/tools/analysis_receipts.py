"""Shared construction of deterministic analysis population receipts."""

from __future__ import annotations

from collections.abc import Iterable

from data_agent.review.domain.analysis import (
    AnalysisExecution,
    AnalysisResult,
    AnalysisStatus,
    PopulationReceipt,
    SourceBinding,
)
from data_agent.review.domain.source import DateRange
from data_agent.tools.review_context import ToolContext


def population_receipt(
    ctx: ToolContext,
    paths: Iterable[str],
    *,
    dataset_id: str,
    rows_read: int,
    rows_processed: int,
    rows_rejected: int = 0,
    rows_excluded: int = 0,
    exclusion_reasons: dict[str, int] | None = None,
    actual_date_range: DateRange | None = None,
    calculation_basis: str,
    observations_produced: int = 0,
    issues: list[str] | None = None,
) -> PopulationReceipt:
    """Serialize parser-supplied accounting with immutable source identities."""
    sources = [ctx.manifest.by_path(path) for path in dict.fromkeys(paths)]
    rows_in_scope = max(rows_read - rows_excluded, 0)
    return PopulationReceipt(
        source_bindings=[
            SourceBinding(source_id=source.source_id, path=source.path, sha256=source.sha256)
            for source in sources
        ],
        dataset_id=dataset_id,
        rows_read=rows_read,
        rows_in_scope=rows_in_scope,
        rows_processed=rows_processed,
        rows_rejected=rows_rejected,
        rows_excluded=rows_excluded,
        exclusion_reasons=exclusion_reasons or {},
        actual_date_range=actual_date_range,
        calculation_basis=calculation_basis,
        observations_produced=observations_produced,
        issues=issues or [],
    )


def attach_execution(
    results: Iterable[AnalysisResult],
    ctx: ToolContext,
    paths: Iterable[str],
    *,
    dataset_id: str,
    rows_read: int,
    rows_processed: int,
    rows_rejected: int = 0,
    issue_codes: list[str] | None = None,
    calculation_basis: str,
    rows_excluded: int = 0,
    exclusion_reasons: dict[str, int] | None = None,
) -> list[AnalysisResult]:
    """Attach one truthful shared population to a coherent analysis battery."""
    status = (
        AnalysisStatus.UNAVAILABLE
        if rows_rejected or issue_codes
        else AnalysisStatus.EMPTY
        if rows_processed == 0
        else AnalysisStatus.SUCCEEDED
    )
    bound_paths = list(paths)
    receipt = population_receipt(
        ctx,
        bound_paths,
        dataset_id=dataset_id,
        rows_read=rows_read,
        rows_processed=rows_processed,
        rows_rejected=rows_rejected,
        rows_excluded=rows_excluded,
        exclusion_reasons=exclusion_reasons,
        calculation_basis=calculation_basis,
        issues=issue_codes,
    )
    execution = AnalysisExecution(status=status, population=receipt, issue_codes=issue_codes or [])
    return [result.model_copy(update={"execution": execution}) for result in results]
