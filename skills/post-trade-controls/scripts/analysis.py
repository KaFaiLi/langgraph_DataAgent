"""Post-trade Controls specialist: deterministic analyses (spec section 17).

Every number here is produced by code (polars + the shared statistics
primitives); the analyst LLM only interprets the results. Analysis inputs are
the run's allowed roots only.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
from collections import defaultdict
from typing import NamedTuple

import polars as pl

from data_agent.review.domain.analysis import AnalysisResult
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference, Locator, format_locator
from data_agent.review.domain.overview import (
    BarVisual,
    DataOverview,
    OverviewMetric,
    OverviewPoint,
    OverviewSeries,
    OverviewStatus,
    StackedBarVisual,
)
from data_agent.review.domain.source import SourceType
from data_agent.tools.analysis_helpers import tabular_row_offset
from data_agent.tools.review_context import ToolContext
from data_agent.tools.statistics_tools import trend_analysis
from data_agent.tools.tabular_helpers import (
    find_column,
    flag,
    load_frame,
    mean,
)

_DATE_NAMES = {"date", "breach_date", "event_date"}
_PRODUCT_NAMES = {"product", "product_family", "instrument"}
_SEVERITY_NAMES = {"severity", "breach_severity"}
_APPROVAL_NAMES = {"approval", "approved_by", "approver", "approval_ref"}
_CLOSED_NAMES = {"closed_date", "resolution_date", "resolved_date"}
_CLOSURE_DAYS_NAMES = {"closure_days", "resolution_days", "days_to_close"}
_STATUS_NAMES = {"status", "workflow_status", "breach_status"}
_OVERRIDE_NAMES = {"override", "override_by", "override_user"}

_REPEAT_THRESHOLD = 3
_CLUSTER_DAYS = 10
_MAX_RESOLUTION_DAYS = 2
_MIN_TREND_POINTS = 5
_TREND_R2 = 0.3
_SEVERITY_SHIFT = 0.2
_MAX_FLAGS = 25
_BLANK = "(blank)"
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class ControlsView(NamedTuple):
    """One post-trade control log with its discovered columns."""

    path: str
    frame: pl.DataFrame
    date_col: str | None
    product_col: str | None
    severity_col: str | None
    approval_col: str | None
    closed_col: str | None
    closure_days_col: str | None
    status_col: str | None
    override_col: str | None
    row_offset: int


class BreachRecord(NamedTuple):
    """One breach row reduced to the fields the analyses need."""

    row: int
    date: dt.date | None
    date_text: str
    product: str
    severity: str
    approval: str
    closed: dt.date | None
    closure_days: float | None
    status: str
    override: str


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(value: object) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_float(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _view(ctx: ToolContext, path: str) -> ControlsView | None:
    """Load one controls file, or None when no control column is present."""
    frame = load_frame(ctx, path)
    if frame is None or frame.height == 0:
        return None
    date_col = find_column(frame, _DATE_NAMES)
    product_col = find_column(frame, _PRODUCT_NAMES)
    severity_col = find_column(frame, _SEVERITY_NAMES)
    approval_col = find_column(frame, _APPROVAL_NAMES)
    closed_col = find_column(frame, _CLOSED_NAMES)
    closure_days_col = find_column(frame, _CLOSURE_DAYS_NAMES)
    status_col = find_column(frame, _STATUS_NAMES)
    override_col = find_column(frame, _OVERRIDE_NAMES)
    control_columns = (
        product_col,
        severity_col,
        approval_col,
        closed_col,
        closure_days_col,
        status_col,
        override_col,
    )
    if all(column is None for column in control_columns):
        return None
    working = frame
    if date_col is not None:
        with contextlib.suppress(pl.exceptions.InvalidOperationError, TypeError):
            working = working.sort(date_col)
    return ControlsView(
        path=path,
        frame=working,
        date_col=date_col,
        product_col=product_col,
        severity_col=severity_col,
        approval_col=approval_col,
        closed_col=closed_col,
        closure_days_col=closure_days_col,
        status_col=status_col,
        override_col=override_col,
        row_offset=tabular_row_offset(ctx.manifest.by_path(path).source_type),
    )


def _records(view: ControlsView) -> list[BreachRecord]:
    """Date-sorted breach records; missing columns become empty fields."""
    records: list[BreachRecord] = []
    for index, row in enumerate(view.frame.iter_rows(named=True), start=view.row_offset):
        raw_date = None if view.date_col is None else row.get(view.date_col)
        records.append(
            BreachRecord(
                row=index,
                date=_parse_date(raw_date),
                date_text=_text(raw_date),
                product=(_text(row.get(view.product_col)) if view.product_col else ""),
                severity=(_text(row.get(view.severity_col)) if view.severity_col else ""),
                approval=(_text(row.get(view.approval_col)) if view.approval_col else ""),
                closed=(_parse_date(row.get(view.closed_col)) if view.closed_col else None),
                closure_days=(
                    _parse_float(row.get(view.closure_days_col)) if view.closure_days_col else None
                ),
                status=_text(row.get(view.status_col)) if view.status_col else "",
                override=(_text(row.get(view.override_col)) if view.override_col else ""),
            )
        )
    return records


def _record_locator(view: ControlsView, record: BreachRecord) -> str:
    return format_locator(Locator(path=view.path, rows=(record.row, record.row)))


def _product_dates(records: list[BreachRecord]) -> dict[str, list[BreachRecord]]:
    grouped: dict[str, list[BreachRecord]] = {}
    for record in records:
        grouped.setdefault(record.product or _BLANK, []).append(record)
    return grouped


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _shares(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {key: 0.0 for key in counts}
    return {key: value / total for key, value in counts.items()}


def _overview_evidence(ctx: ToolContext, view: ControlsView) -> EvidenceReference:
    source = ctx.manifest.by_path(view.path)
    first_row = tabular_row_offset(source.source_type)
    sheet = (
        source.sheet_names[0]
        if source.source_type in {SourceType.XLSX, SourceType.XLSM} and len(source.sheet_names) == 1
        else None
    )
    return EvidenceReference(
        locator=format_locator(
            Locator(
                path=view.path,
                sheet=sheet,
                rows=(first_row, first_row + view.frame.height - 1),
            )
        )
    )


def _control_overviews(
    ctx: ToolContext, view: ControlsView, *, primary: bool
) -> list[DataOverview]:
    records = _records(view)
    if not records:
        return []
    suffix = "" if primary else f".{hashlib.sha256(view.path.encode()).hexdigest()[:8]}"
    months = sorted(
        {record.date.strftime("%Y-%m") if record.date else "(undated)" for record in records}
    )
    severities = sorted({record.severity.lower() or _BLANK for record in records})
    approval_gaps = sum(1 for record in records if not record.approval)
    resolved = [
        (record.closed - record.date).days
        for record in records
        if record.date is not None and record.closed is not None and record.closed >= record.date
    ]
    evidence = [_overview_evidence(ctx, view)]
    approval_basis = (
        f"{approval_gaps} ({approval_gaps / len(records):.2%})"
        if view.approval_col is not None
        else f"{len(records)} (100.00%)"
    )
    closure_metric = f"{sum(resolved) / len(resolved):.2f} days" if resolved else "Unavailable"
    overviews = [
        DataOverview(
            overview_id=f"post-trade-controls.breaches-over-time{suffix}",
            domain=SpecialistDomain.POST_TRADE_CONTROLS,
            source_family="post_trade_controls",
            title="Post-trade breaches over time and by severity",
            summary=(
                "The full breach population is profiled by month and severity, with approval "
                "and closure coverage shown independently of exception findings."
            ),
            status=OverviewStatus.AVAILABLE,
            primary_for_deck=primary,
            metrics=[
                OverviewMetric(
                    label="Breaches",
                    value=str(len(records)),
                    unit="count",
                    basis="all reviewed control-log rows",
                ),
                OverviewMetric(
                    label="Approval gaps",
                    value=approval_basis,
                    unit="count and share",
                    basis=(
                        "blank approval reference"
                        if view.approval_col is not None
                        else "approval column not supplied"
                    ),
                ),
                OverviewMetric(
                    label="Resolved",
                    value=f"{len(resolved)} ({len(resolved) / len(records):.2%})",
                    unit="count and share",
                    basis="valid breach and closure dates",
                ),
                OverviewMetric(
                    label="Mean closure",
                    value=closure_metric,
                    unit="calendar days",
                    basis="rows with valid breach and closure dates",
                ),
            ],
            visual=StackedBarVisual(
                x_label="Breach month",
                y_label="Breach count",
                unit="count",
                series=[
                    OverviewSeries(
                        name=severity,
                        points=[
                            OverviewPoint(
                                label=month,
                                value=float(
                                    sum(
                                        1
                                        for record in records
                                        if (record.severity.lower() or _BLANK) == severity
                                        and (
                                            record.date.strftime("%Y-%m")
                                            if record.date
                                            else "(undated)"
                                        )
                                        == month
                                    )
                                ),
                            )
                            for month in months
                        ],
                    )
                    for severity in severities
                ],
            ),
            evidence=evidence,
            limitations=[
                (
                    "Each control-log row is treated as one breach; status is inferred "
                    "only from a valid closure date."
                ),
                "Counts are not severity-weighted and do not measure economic exposure.",
            ],
        )
    ]
    if view.product_col is not None:
        product_counts = _counts([record.product or _BLANK for record in records])
        ordered_products = sorted(
            product_counts, key=lambda product: (-product_counts[product], product)
        )
        overviews.append(
            DataOverview(
                overview_id=f"post-trade-controls.breaches-by-product{suffix}",
                domain=SpecialistDomain.POST_TRADE_CONTROLS,
                source_family="post_trade_controls",
                title="Post-trade breaches by product",
                summary="Product recurrence is shown across the full reviewed breach population.",
                status=OverviewStatus.AVAILABLE,
                metrics=[
                    OverviewMetric(
                        label="Products",
                        value=str(len(product_counts)),
                        unit="count",
                        basis="distinct supplied product labels",
                    )
                ],
                visual=BarVisual(
                    x_label="Product",
                    y_label="Breach count",
                    unit="count",
                    series=[
                        OverviewSeries(
                            name="Breaches",
                            points=[
                                OverviewPoint(
                                    label=product,
                                    value=float(product_counts[product]),
                                )
                                for product in ordered_products
                            ],
                        )
                    ],
                ),
                evidence=evidence,
                limitations=[
                    ("Product labels are reported values and are not normalized across files.")
                ],
            )
        )
    return overviews


def repeated_breaches(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Products breaching post-trade controls three or more times."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    overviews: list[DataOverview] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None:
            continue
        overviews.extend(_control_overviews(ctx, view, primary=not overviews))
        if view.product_col is None:
            continue
        grouped = _product_dates(_records(view))
        for product in sorted(grouped):
            occurrences = grouped[product]
            if len(occurrences) < _REPEAT_THRESHOLD:
                continue
            dates = [record.date_text for record in occurrences if record.date_text]
            tables.append(
                {
                    "path": path,
                    "product": product,
                    "occurrences": len(occurrences),
                    "first_date": dates[0] if dates else "",
                    "last_date": dates[-1] if dates else "",
                    "dates": dates[:10],
                }
            )
            if len(flags) < _MAX_FLAGS:
                last_record = occurrences[-1]
                flags.append(
                    flag(
                        "repeated_breaches",
                        path,
                        dates[-1] if dates else "",
                        product=product,
                        occurrences=len(occurrences),
                        first_date=dates[0] if dates else "",
                        open_occurrences=sum(
                            record.status.lower() in {"open", "unresolved", "pending"}
                            for record in occurrences
                        ),
                        locator=_record_locator(view, last_record),
                        locators=[_record_locator(view, record) for record in occurrences[:10]],
                        detail=(
                            "the same product breached post-trade controls "
                            f"{len(occurrences)} times in the period"
                        ),
                    )
                )
            override_groups: dict[str, list[BreachRecord]] = defaultdict(list)
            for record in occurrences:
                if record.override:
                    override_groups[record.override].append(record)
            for actor, overridden in sorted(override_groups.items()):
                if len(overridden) < _REPEAT_THRESHOLD or len(flags) >= _MAX_FLAGS:
                    continue
                last_override = overridden[-1]
                open_overrides = sum(
                    record.status.lower() in {"open", "unresolved", "pending"}
                    for record in overridden
                )
                maximum_severity = max(
                    (_SEVERITY_RANK.get(record.severity.lower(), 0) for record in overridden),
                    default=0,
                )
                flags.append(
                    flag(
                        "recurring_override_perimeter",
                        path,
                        last_override.date_text,
                        product=product,
                        override_actor=actor,
                        occurrences=len(overridden),
                        first_date=overridden[0].date_text,
                        open_occurrences=open_overrides,
                        locator=_record_locator(view, last_override),
                        locators=[_record_locator(view, record) for record in overridden[:10]],
                        severity_floor=(
                            "high"
                            if open_overrides and maximum_severity >= _SEVERITY_RANK["high"]
                            else "medium"
                        ),
                        severity_match_terms=["override", "control"],
                        measured_observation=True,
                        detail=(
                            f"the same actor recorded {len(overridden)} overrides for one "
                            "product perimeter"
                        ),
                    )
                )
    summary = (
        f"Repeated-breach screen produced {len(tables)} repeat product(s) and "
        f"{len(flags)} flag(s) by code."
    )
    if not overviews:
        overviews.append(
            DataOverview(
                overview_id="post-trade-controls.breaches-over-time",
                domain=SpecialistDomain.POST_TRADE_CONTROLS,
                source_family="post_trade_controls",
                title="Post-trade breach population",
                summary="No compatible control-log population was available for profiling.",
                status=OverviewStatus.UNAVAILABLE,
                primary_for_deck=True,
                limitations=[
                    (
                        "Overview unavailable because no source exposed compatible "
                        "post-trade control columns."
                    )
                ],
            )
        )
    return AnalysisResult(
        name="repeated_breaches",
        summary=summary,
        tables=tables,
        flag_candidates=flags,
        overviews=overviews,
    )


def product_recurrence(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Full same-product recurrence counts plus tight recurrence clusters."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None or view.product_col is None:
            continue
        grouped = _product_dates(_records(view))
        for product in sorted(grouped, key=lambda name: (-len(grouped[name]), name)):
            occurrences = grouped[product]
            dates = [record.date_text for record in occurrences if record.date_text]
            parsed = sorted(record.date for record in occurrences if record.date is not None)
            tables.append(
                {
                    "path": path,
                    "product": product,
                    "occurrences": len(occurrences),
                    "distinct_days": len(set(dates)),
                    "first_date": dates[0] if dates else "",
                    "last_date": dates[-1] if dates else "",
                }
            )
            for index in range(len(parsed) - _REPEAT_THRESHOLD + 1):
                window_end = parsed[index + _REPEAT_THRESHOLD - 1]
                span = (window_end - parsed[index]).days
                if span > _CLUSTER_DAYS or len(flags) >= _MAX_FLAGS:
                    continue
                flags.append(
                    flag(
                        "recurrence_cluster",
                        path,
                        window_end.isoformat(),
                        product=product,
                        occurrences=_REPEAT_THRESHOLD,
                        span_days=span,
                        window_start=parsed[index].isoformat(),
                        detail=(
                            f"{_REPEAT_THRESHOLD} breaches of the same product within {span} day(s)"
                        ),
                    )
                )
    summary = (
        f"Recurrence counts computed for {len(tables)} product row(s); "
        f"{len(flags)} tight cluster(s) flagged by code."
    )
    return AnalysisResult(
        name="product_recurrence", summary=summary, tables=tables, flag_candidates=flags
    )


def resolution_time(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Days from breach date to closure, against the T+2 expectation."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if (
            view is None
            or view.date_col is None
            or (view.closed_col is None and view.closure_days_col is None)
        ):
            continue
        durations: list[float] = []
        records = _records(view)
        by_product: dict[str, list[tuple[BreachRecord, float]]] = defaultdict(list)
        for record in records:
            if record.date is None:
                continue
            days = (
                record.closure_days
                if record.closure_days is not None
                else (
                    float((record.closed - record.date).days) if record.closed is not None else None
                )
            )
            if days is None:
                if record.status.lower() in {"open", "unresolved", "pending"}:
                    flags.append(
                        flag(
                            "open_control_item",
                            path,
                            record.date_text,
                            product=record.product,
                            severity=record.severity,
                            locator=_record_locator(view, record),
                            severity_floor="medium",
                            severity_match_terms=["open"],
                            measured_observation=True,
                            detail="control item remains open with no recorded closure duration",
                        )
                    )
                continue
            if days < 0:
                continue
            durations.append(days)
            by_product[record.product or _BLANK].append((record, days))
            if days <= _MAX_RESOLUTION_DAYS or len(flags) >= _MAX_FLAGS:
                continue
            flags.append(
                flag(
                    "slow_resolution",
                    path,
                    record.date_text,
                    product=record.product,
                    closed_date=record.closed.isoformat() if record.closed else None,
                    resolution_days=days,
                    locator=_record_locator(view, record),
                    detail=f"breach closed after T+{days}, beyond the T+2 expectation",
                )
            )
        if not durations:
            continue
        table: dict[str, object] = {
            "path": path,
            "resolved_breaches": len(durations),
            "mean_days": round(mean(durations), 4),
            "max_days": max(durations),
            "days_beyond_t2": sum(1 for value in durations if value > _MAX_RESOLUTION_DAYS),
        }
        if len(durations) >= _MIN_TREND_POINTS:
            trend = trend_analysis(durations)
            table["trend_slope"] = round(trend.slope, 6)
            table["trend_r2"] = round(trend.r_squared, 4)
            if trend.slope > 0 and trend.r_squared >= _TREND_R2:
                flags.append(
                    flag(
                        "resolution_time_trend_up",
                        path,
                        "",
                        trend_slope=round(trend.slope, 6),
                        trend_r2=round(trend.r_squared, 4),
                        mean_days=round(mean(durations), 4),
                        detail="time to close breaches grows over the review period",
                    )
                )
        for product, product_rows in sorted(by_product.items()):
            if len(product_rows) < _MIN_TREND_POINTS:
                continue
            values = [days for _record, days in product_rows]
            trend = trend_analysis(values)
            if trend.slope <= 0 or trend.r_squared < _TREND_R2:
                continue
            first_record = product_rows[0][0]
            last_record = product_rows[-1][0]
            flags.append(
                flag(
                    "resolution_time_trend_up_by_product",
                    path,
                    last_record.date_text,
                    product=product,
                    observations=len(values),
                    first_date=first_record.date_text,
                    last_date=last_record.date_text,
                    first_resolution_days=values[0],
                    last_resolution_days=values[-1],
                    trend_slope=round(trend.slope, 6),
                    trend_r2=round(trend.r_squared, 4),
                    locator=_record_locator(view, last_record),
                    first_locator=_record_locator(view, first_record),
                    severity_floor="medium",
                    severity_match_terms=["remediation", "deterior"],
                    measured_observation=True,
                    detail="time to close repeated breaches rises within one product",
                )
            )
        tables.append(table)
    summary = (
        f"Resolution times computed for {len(tables)} control log(s); "
        f"{len(flags)} slow-resolution/trend flag(s)."
    )
    return AnalysisResult(
        name="resolution_time", summary=summary, tables=tables, flag_candidates=flags
    )


def approval_gaps(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Breaches recorded without an approval reference or approver."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None:
            continue
        records = _records(view)
        if view.approval_col is None:
            tables.append(
                {
                    "path": path,
                    "approval_column": "",
                    "rows": len(records),
                    "approval_gaps": len(records),
                    "gap_share": 1.0,
                }
            )
            flags.append(
                flag(
                    "approval_column_missing",
                    path,
                    "",
                    rows=len(records),
                    detail="the control log records no approval or approver column at all",
                )
            )
            continue
        gaps = 0
        for record in records:
            if record.approval:
                continue
            gaps += 1
            if len(flags) < _MAX_FLAGS:
                flags.append(
                    flag(
                        "approval_gap",
                        path,
                        record.date_text,
                        product=record.product,
                        severity=record.severity,
                        locator=_record_locator(view, record),
                        severity_floor="medium",
                        severity_match_terms=["approval"],
                        measured_observation=True,
                        detail="breach row carries no approval reference or approver",
                    )
                )
        tables.append(
            {
                "path": path,
                "approval_column": view.approval_col,
                "rows": len(records),
                "approval_gaps": gaps,
                "gap_share": round(gaps / len(records), 4) if records else 0.0,
            }
        )
    summary = (
        f"Approval coverage checked for {len(tables)} control log(s); "
        f"{len(flags)} approval gap flag(s) produced by code."
    )
    return AnalysisResult(
        name="approval_gaps", summary=summary, tables=tables, flag_candidates=flags
    )


def override_patterns(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Who overrides post-trade controls, and how concentrated that is."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None or view.override_col is None:
            continue
        records = _records(view)
        counts = _counts([record.override for record in records if record.override])
        if not counts:
            continue
        shares = _shares(counts)
        ordered = sorted(counts, key=lambda name: (-counts[name], name))
        tables.append(
            {
                "path": path,
                "override_column": view.override_col,
                "overrides": sum(counts.values()),
                "override_share_of_rows": round(sum(counts.values()) / len(records), 4),
                "by_user": [
                    {
                        "user": name,
                        "overrides": counts[name],
                        "share": round(shares[name], 4),
                    }
                    for name in ordered
                ],
            }
        )
        top = ordered[0]
        last_date = next(
            (record.date_text for record in reversed(records) if record.override == top),
            "",
        )
        flags.append(
            flag(
                "top_overrider",
                path,
                last_date,
                user=top,
                overrides=counts[top],
                share=round(shares[top], 4),
                detail="single user accounts for the largest share of control overrides",
            )
        )
        for name in ordered:
            if counts[name] < _REPEAT_THRESHOLD or len(flags) >= _MAX_FLAGS:
                continue
            flags.append(
                flag(
                    "repeated_override",
                    path,
                    "",
                    user=name,
                    overrides=counts[name],
                    share=round(shares[name], 4),
                    detail=f"{counts[name]} control overrides recorded for one user",
                )
            )
    summary = (
        f"Override patterns computed for {len(tables)} control log(s); "
        f"{len(flags)} override flag(s) produced by code."
    )
    return AnalysisResult(
        name="override_patterns", summary=summary, tables=tables, flag_candidates=flags
    )


def severity_changes(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Severity mix in the first half of the period versus the second half."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None or view.severity_col is None:
            continue
        records = [record for record in _records(view) if record.severity]
        if len(records) < 4:
            continue
        split = len(records) // 2
        first = _shares(_counts([record.severity.lower() for record in records[:split]]))
        second = _shares(_counts([record.severity.lower() for record in records[split:]]))
        rows: list[dict[str, object]] = []
        for severity in sorted(set(first) | set(second)):
            first_share = first.get(severity, 0.0)
            second_share = second.get(severity, 0.0)
            shift = second_share - first_share
            rows.append(
                {
                    "severity": severity,
                    "first_half_share": round(first_share, 4),
                    "second_half_share": round(second_share, 4),
                    "shift": round(shift, 4),
                }
            )
            if abs(shift) < _SEVERITY_SHIFT or len(flags) >= _MAX_FLAGS:
                continue
            flags.append(
                flag(
                    "severity_mix_shift",
                    path,
                    records[split].date_text,
                    severity=severity,
                    first_half_share=round(first_share, 4),
                    second_half_share=round(second_share, 4),
                    shift=round(shift, 4),
                    detail="severity mix moved by >= 20 percentage points between halves",
                )
            )
        tables.append(
            {
                "path": path,
                "severity_column": view.severity_col,
                "breaches": len(records),
                "first_half": f"{records[0].date_text}..{records[split - 1].date_text}",
                "second_half": f"{records[split].date_text}..{records[-1].date_text}",
                "severity_shares": rows,
            }
        )
    summary = (
        f"Severity mix compared for {len(tables)} control log(s); "
        f"{len(flags)} severity shift flag(s)."
    )
    return AnalysisResult(
        name="severity_changes", summary=summary, tables=tables, flag_candidates=flags
    )


def run_post_trade_controls_analyses(
    ctx: ToolContext, source_paths: list[str]
) -> list[AnalysisResult]:
    """Run the full deterministic post-trade controls battery (spec section 17)."""
    return [
        repeated_breaches(ctx, source_paths),
        product_recurrence(ctx, source_paths),
        resolution_time(ctx, source_paths),
        approval_gaps(ctx, source_paths),
        override_patterns(ctx, source_paths),
        severity_changes(ctx, source_paths),
    ]


run_analysis = run_post_trade_controls_analyses
