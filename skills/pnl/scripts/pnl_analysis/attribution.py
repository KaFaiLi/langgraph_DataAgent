"""Legacy-format income-attribution calculations owned by the composite PnL skill.

Every number here is produced by code (polars + the shared statistics
primitives); the analyst LLM only interprets the results. Analysis inputs are
the run's allowed roots only.
"""

from __future__ import annotations

import contextlib
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
)
from data_agent.review.domain.source import SourceType
from data_agent.tools.analysis_helpers import tabular_row_offset
from data_agent.tools.review_context import ToolContext
from data_agent.tools.statistics_tools import pearson_correlation, rolling_std
from data_agent.tools.tabular_helpers import (
    DATE_COLUMN_NAMES,
    find_column,
    flag,
    group_sum,
    hhi,
    load_frame,
    mean,
    pstdev,
    top_share,
)

_DATE_NAMES = DATE_COLUMN_NAMES
_DRIVER_NAMES = {"driver", "factor", "attribution_driver", "source"}
_PNL_NAMES = {"pnl", "pnl_musd", "value", "income"}
_VAR_NAMES = {"var", "value_at_risk", "daily_var"}

_UNEXPECTED_TOKENS = ("other", "unexplained", "residual", "misc")
_RISK_TOKENS = ("risk", "hedge")

_ABS_COLUMN = "abs_pnl_calc"
_TOP_N = 3
_TOP3_SHARE = 0.7
_DATE_TOP3_SHARE = 0.8
_SHIFT_THRESHOLD = 0.2
_WEAK_CORRELATION = 0.2
_ROLLING_WINDOW = 5
_MIN_PAIRS = 10
_MISMATCH_SIGMAS = 2.0
_MAX_FLAGS = 25


class AttributionView(NamedTuple):
    """One attribution table with its discovered driver/PnL/date columns."""

    path: str
    frame: pl.DataFrame
    date_col: str | None
    driver_col: str
    pnl_col: str


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _view(ctx: ToolContext, path: str) -> AttributionView | None:
    """Load one attribution file, or None when the domain columns are absent."""
    frame = load_frame(ctx, path)
    if frame is None or frame.height == 0:
        return None
    driver_col = find_column(frame, _DRIVER_NAMES)
    pnl_col = find_column(frame, _PNL_NAMES)
    if driver_col is None or pnl_col is None:
        return None
    date_col = find_column(frame, _DATE_NAMES)
    working = frame
    if date_col is not None:
        with contextlib.suppress(pl.exceptions.InvalidOperationError, TypeError):
            working = working.sort(date_col)
    return AttributionView(
        path=path,
        frame=working,
        date_col=date_col,
        driver_col=driver_col,
        pnl_col=pnl_col,
    )


def _rows(view: AttributionView) -> list[tuple[str, str, float]]:
    """(date, driver, pnl) triples with unparsable PnL values dropped."""
    out: list[tuple[str, str, float]] = []
    for row in view.frame.iter_rows(named=True):
        value = _as_float(row.get(view.pnl_col))
        if value is None:
            continue
        date_text = "" if view.date_col is None else str(row.get(view.date_col, ""))
        out.append((date_text, str(row.get(view.driver_col, "")).strip(), value))
    return out


def _abs_totals_by_date(
    rows: list[tuple[str, str, float]],
) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = {}
    for date_text, driver, value in rows:
        bucket = totals.setdefault(date_text, {})
        bucket[driver] = bucket.get(driver, 0.0) + abs(value)
    return totals


def _merge_totals(by_date: dict[str, dict[str, float]]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for bucket in by_date.values():
        for driver, value in bucket.items():
            merged[driver] = merged.get(driver, 0.0) + value
    return merged


def _shares(totals: dict[str, float]) -> dict[str, float]:
    total = sum(totals.values())
    if total <= 0:
        return {driver: 0.0 for driver in totals}
    return {driver: value / total for driver, value in totals.items()}


def _overview_evidence(
    ctx: ToolContext, view: AttributionView
) -> EvidenceReference:
    source = ctx.manifest.by_path(view.path)
    first_row = tabular_row_offset(source.source_type)
    sheet = (
        source.sheet_names[0]
        if source.source_type in {SourceType.XLSX, SourceType.XLSM}
        and len(source.sheet_names) == 1
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


def _var_by_date(view: AttributionView, var_col: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in view.frame.iter_rows(named=True):
        value = _as_float(row.get(var_col))
        if value is None:
            continue
        key = "" if view.date_col is None else str(row.get(view.date_col, ""))
        values[key] = value
    return values


def driver_concentration(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Top-3 share and HHI of income drivers, overall and per date."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    overviews: list[DataOverview] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None:
            continue
        working = view.frame.with_columns(
            pl.col(view.pnl_col).cast(pl.Float64, strict=False).abs().alias(_ABS_COLUMN)
        )
        grouped = group_sum(working, view.driver_col, _ABS_COLUMN)
        totals = {
            str(row.get(view.driver_col, "")).strip(): float(_as_float(row.get("value")) or 0.0)
            for row in grouped
        }
        total = sum(totals.values())
        if total <= 0:
            continue
        shares = _shares(totals)
        overall_top3 = top_share(list(shares.values()), _TOP_N)
        overall_hhi = hhi(list(shares.values()))
        ordered = sorted(shares.items(), key=lambda item: (-item[1], item[0]))
        unexpected_share = sum(
            share
            for driver, share in shares.items()
            if any(token in driver.lower() for token in _UNEXPECTED_TOKENS)
        )
        concentrated_dates: list[str] = []
        if view.date_col is not None:
            by_date = _abs_totals_by_date(_rows(view))
            for date_text in sorted(by_date):
                date_shares = list(_shares(by_date[date_text]).values())
                if not date_shares:
                    continue
                date_top3 = top_share(date_shares, _TOP_N)
                if date_top3 < _DATE_TOP3_SHARE:
                    continue
                concentrated_dates.append(date_text)
                if len(flags) < _MAX_FLAGS:
                    flags.append(
                        flag(
                            "daily_driver_concentration",
                            path,
                            date_text,
                            top3_share=round(date_top3, 4),
                            hhi=round(hhi(date_shares), 4),
                            drivers=len(date_shares),
                            detail="top 3 drivers hold >= 80% of that day's absolute income",
                        )
                    )
        tables.append(
            {
                "path": path,
                "driver_column": view.driver_col,
                "drivers": len(totals),
                "top3_share": round(overall_top3, 4),
                "hhi": round(overall_hhi, 4),
                "top_drivers": [
                    {
                        "driver": driver,
                        "abs_pnl": round(totals[driver], 6),
                        "share": round(share, 4),
                    }
                    for driver, share in ordered[:5]
                ],
                "concentrated_days": len(concentrated_dates),
            }
        )
        if not overviews:
            overviews.append(
                DataOverview(
                    overview_id="income-attribution.driver-mix",
                    domain=SpecialistDomain.INCOME_ATTRIBUTION,
                    source_family="income_attribution",
                    title="Absolute PnL contribution by attribution driver",
                    summary=(
                        "Absolute attributed PnL is profiled by driver so concentration "
                        "and residual buckets remain visible alongside findings."
                    ),
                    status=OverviewStatus.AVAILABLE,
                    primary_for_deck=True,
                    metrics=[
                        OverviewMetric(
                            label="Top-three share",
                            value=f"{overall_top3:.2%}",
                            unit="share of absolute PnL",
                            basis="full reviewed period",
                        ),
                        OverviewMetric(
                            label="Residual/unexplained share",
                            value=f"{unexpected_share:.2%}",
                            unit="share of absolute PnL",
                            basis="driver-name token match",
                        ),
                        OverviewMetric(
                            label="Drivers",
                            value=str(len(totals)),
                            unit="count",
                            basis="distinct reported drivers",
                        ),
                    ],
                    visual=BarVisual(
                        x_label="Attribution driver",
                        y_label="Share of absolute PnL",
                        unit="share",
                        series=[
                            OverviewSeries(
                                name="Absolute PnL share",
                                points=[
                                    OverviewPoint(label=driver, value=round(share, 8))
                                    for driver, share in ordered
                                ],
                            )
                        ],
                    ),
                    evidence=[_overview_evidence(ctx, view)],
                    limitations=[
                        "Absolute contribution does not preserve the direction of PnL.",
                        "Residual share is a disclosed driver-name screen, not a control finding.",
                    ],
                )
            )
        if overall_top3 >= _TOP3_SHARE:
            flags.append(
                flag(
                    "driver_concentration",
                    path,
                    "",
                    top3_share=round(overall_top3, 4),
                    hhi=round(overall_hhi, 4),
                    drivers=len(totals),
                    detail="top 3 drivers hold >= 70% of absolute income in the period",
                )
            )
    summary = (
        f"Driver concentration computed for {len(tables)} attribution table(s); "
        f"{len(flags)} concentration flag(s) produced by code."
    )
    if not overviews:
        overviews.append(
            DataOverview(
                overview_id="income-attribution.driver-mix",
                domain=SpecialistDomain.INCOME_ATTRIBUTION,
                source_family="income_attribution",
                title="Absolute PnL contribution by attribution driver",
                summary="No compatible driver and PnL population was available for profiling.",
                status=OverviewStatus.UNAVAILABLE,
                primary_for_deck=True,
                limitations=[
                    (
                        "Overview unavailable because no source exposed compatible driver "
                        "and PnL columns."
                    )
                ],
            )
        )
    return AnalysisResult(
        name="driver_concentration",
        summary=summary,
        tables=tables,
        flag_candidates=flags,
        overviews=overviews,
    )


def unexpected_drivers(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Residual/other/unexplained/misc buckets carrying income."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None:
            continue
        totals = _merge_totals(_abs_totals_by_date(_rows(view)))
        if not totals:
            continue
        shares = _shares(totals)
        matched: list[dict[str, object]] = []
        matched_shares: list[float] = []
        for driver in sorted(totals):
            lowered = driver.lower()
            token = next(
                (name for name in _UNEXPECTED_TOKENS if name in lowered), None
            )
            if token is None:
                continue
            matched.append(
                {
                    "driver": driver,
                    "token": token,
                    "abs_pnl": round(totals[driver], 6),
                    "share": round(shares[driver], 4),
                }
            )
            matched_shares.append(shares[driver])
            if len(flags) < _MAX_FLAGS:
                flags.append(
                    flag(
                        "unexpected_driver",
                        path,
                        "",
                        driver=driver,
                        token=token,
                        abs_pnl=round(totals[driver], 6),
                        share=round(shares[driver], 4),
                        detail="income attributed to a residual/unexplained bucket",
                    )
                )
        tables.append(
            {
                "path": path,
                "drivers": len(totals),
                "unexpected_drivers": matched,
                "unexpected_share": round(sum(matched_shares), 4),
            }
        )
    summary = (
        f"Unexpected-driver screen run over {len(tables)} attribution table(s); "
        f"{len(flags)} residual bucket(s) flagged by code."
    )
    return AnalysisResult(
        name="unexpected_drivers", summary=summary, tables=tables, flag_candidates=flags
    )


def income_source_shifts(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Driver share in the first half of the period versus the second half."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None or view.date_col is None:
            continue
        by_date = _abs_totals_by_date(_rows(view))
        dates = sorted(by_date)
        if len(dates) < 2:
            continue
        split = len(dates) // 2
        first_dates, second_dates = dates[:split], dates[split:]
        first = _shares(_merge_totals({day: by_date[day] for day in first_dates}))
        second = _shares(_merge_totals({day: by_date[day] for day in second_dates}))
        rows: list[dict[str, object]] = []
        for driver in sorted(set(first) | set(second)):
            first_share = first.get(driver, 0.0)
            second_share = second.get(driver, 0.0)
            shift = second_share - first_share
            rows.append(
                {
                    "driver": driver,
                    "first_half_share": round(first_share, 4),
                    "second_half_share": round(second_share, 4),
                    "shift": round(shift, 4),
                }
            )
            if abs(shift) < _SHIFT_THRESHOLD or len(flags) >= _MAX_FLAGS:
                continue
            flags.append(
                flag(
                    "income_source_shift",
                    path,
                    second_dates[0],
                    driver=driver,
                    first_half_share=round(first_share, 4),
                    second_half_share=round(second_share, 4),
                    shift=round(shift, 4),
                    detail="driver share of income moved by >= 20 percentage points",
                )
            )
        tables.append(
            {
                "path": path,
                "first_half": f"{first_dates[0]}..{first_dates[-1]}",
                "second_half": f"{second_dates[0]}..{second_dates[-1]}",
                "driver_shares": rows,
            }
        )
    summary = (
        f"Source-of-income shift analysis run over {len(tables)} table(s); "
        f"{len(flags)} driver shift(s) flagged by code."
    )
    return AnalysisResult(
        name="income_source_shifts", summary=summary, tables=tables, flag_candidates=flags
    )


def risk_consistency(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Correlation of rolling |income| volatility with the reported VaR."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None:
            continue
        var_col = find_column(view.frame, _VAR_NAMES)
        if var_col is None:
            continue
        by_date = _abs_totals_by_date(_rows(view))
        var_by_date = _var_by_date(view, var_col)
        dates = [day for day in sorted(by_date) if day in var_by_date]
        if len(dates) < _MIN_PAIRS:
            continue
        abs_income = [sum(by_date[day].values()) for day in dates]
        window = min(_ROLLING_WINDOW, max(2, len(abs_income) // 4))
        volatility = rolling_std(abs_income, window)
        pairs = [
            (value, var_by_date[day])
            for day, value in zip(dates, volatility, strict=True)
            if value is not None
        ]
        if len(pairs) < _MIN_PAIRS:
            continue
        correlation = pearson_correlation(
            [value for value, _ in pairs], [var for _, var in pairs]
        )
        tables.append(
            {
                "path": path,
                "var_column": var_col,
                "rolling_window": window,
                "observations": len(pairs),
                "correlation": round(correlation, 4),
            }
        )
        if correlation < _WEAK_CORRELATION:
            flags.append(
                flag(
                    "risk_income_relation_weak",
                    path,
                    dates[-1],
                    correlation=round(correlation, 4),
                    observations=len(pairs),
                    detail=(
                        "rolling volatility of attributed income is weakly or negatively "
                        "related to the reported VaR"
                    ),
                )
            )
    summary = (
        f"Risk/income consistency computed for {len(tables)} table(s) with a VaR column; "
        f"{len(flags)} weak-relation flag(s)."
    )
    return AnalysisResult(
        name="risk_consistency", summary=summary, tables=tables, flag_candidates=flags
    )


def risk_pnl_mismatch(ctx: ToolContext, source_paths: list[str]) -> AnalysisResult:
    """Risk/hedge drivers producing large income, which they should not."""
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for path in source_paths:
        view = _view(ctx, path)
        if view is None:
            continue
        rows = _rows(view)
        if len(rows) < 2:
            continue
        magnitudes = [abs(value) for _, _, value in rows]
        threshold = mean(magnitudes) + _MISMATCH_SIGMAS * pstdev(magnitudes)
        matched = 0
        for date_text, driver, value in rows:
            lowered = driver.lower()
            token = next((name for name in _RISK_TOKENS if name in lowered), None)
            if token is None or abs(value) < threshold:
                continue
            matched += 1
            if len(flags) < _MAX_FLAGS:
                flags.append(
                    flag(
                        "risk_driver_large_pnl",
                        path,
                        date_text,
                        driver=driver,
                        token=token,
                        pnl=round(value, 6),
                        threshold=round(threshold, 6),
                        detail="a risk/hedge driver carries an unusually large income amount",
                    )
                )
        tables.append(
            {
                "path": path,
                "rows": len(rows),
                "large_amount_threshold": round(threshold, 6),
                "risk_driver_large_rows": matched,
            }
        )
    summary = (
        f"Risk/income mismatch screen run over {len(tables)} table(s); "
        f"{len(flags)} risk-driver amount(s) flagged by code."
    )
    return AnalysisResult(
        name="risk_pnl_mismatch", summary=summary, tables=tables, flag_candidates=flags
    )


def run_income_attribution_analyses(
    ctx: ToolContext, source_paths: list[str]
) -> list[AnalysisResult]:
    """Run the full deterministic income-attribution battery (spec section 17)."""
    return [
        driver_concentration(ctx, source_paths),
        unexpected_drivers(ctx, source_paths),
        income_source_shifts(ctx, source_paths),
        risk_consistency(ctx, source_paths),
        risk_pnl_mismatch(ctx, source_paths),
    ]
