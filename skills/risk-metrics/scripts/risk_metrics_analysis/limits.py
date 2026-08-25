"""Limit-consumption calculations and utilization overview checks."""

from .shared import *


def _close(left: float, right: float, tolerance: float = FLOAT_TOLERANCE) -> bool:
    return abs(left - right) <= max(tolerance, abs(right) * tolerance)


def _utilization(item: SgmrRow) -> float | None:
    if item.value >= 0:
        return None if item.upper_limit <= 0 else item.value / item.upper_limit
    return None if item.lower_limit >= 0 else abs(item.value) / abs(item.lower_limit)


def _longest_streak(rows: list[SgmrRow], predicate: Callable[[SgmrRow], bool]) -> list[SgmrRow]:
    longest: list[SgmrRow] = []
    current: list[SgmrRow] = []
    for item in rows:
        if predicate(item):
            current.append(item)
            if len(current) > len(longest):
                longest = list(current)
        else:
            current = []
    return longest


def _series_key(item: SgmrRow) -> tuple[str, str, str, str, str, int]:
    return (
        item.limit_id,
        item.portfolio,
        item.pc,
        item.indicator,
        item.metric_name,
        item.version,
    )


def _risk_overview_evidence(rows: list[SgmrRow]) -> list[EvidenceReference]:
    grouped: dict[tuple[str, str | None], list[int]] = defaultdict(list)
    for item in rows:
        grouped[(item.path, item.sheet)].append(item.row)
    return [
        EvidenceReference(
            locator=format_locator(
                Locator(
                    path=path,
                    sheet=sheet,
                    rows=(min(source_rows), max(source_rows)),
                )
            )
        )
        for (path, sheet), source_rows in sorted(grouped.items())
    ]


def _limit_consumption(sgmr: list[SgmrRow]) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    overviews: list[DataOverview] = []
    series: dict[tuple[str, str, str, str, str, int], list[SgmrRow]] = defaultdict(list)
    for item in sgmr:
        series[_series_key(item)].append(item)
    breach_series = 0
    proximity_series = 0
    for key, raw_rows in sorted(series.items()):
        rows = sorted(raw_rows, key=lambda item: (item.day, item.row))
        with_util = [(item, _utilization(item)) for item in rows]
        valid = [(item, value) for item, value in with_util if value is not None]
        if not valid:
            item = rows[0]
            flags.append(
                _flag(
                    "invalid_directional_limit_bounds",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    lower_limit=item.lower_limit,
                    upper_limit=item.upper_limit,
                )
            )
            continue
        values = [value for _, value in valid]
        worst_item, worst_util = max(valid, key=lambda pair: pair[1])
        current_item, current_util = valid[-1]
        threshold_values = {
            item.warning_threshold
            for item in rows
            if item.warning_threshold is not None and 0 < item.warning_threshold < 1
        }
        threshold = (
            current_item.warning_threshold
            if current_item.warning_threshold is not None and 0 < current_item.warning_threshold < 1
            else NEAR_LIMIT_DEFAULT
        )
        breaches = [(item, value) for item, value in valid if value > 1.0]
        proximity = [(item, value) for item, value in valid if value >= threshold]

        def exceeds_threshold(item: SgmrRow, *, _threshold: float = threshold) -> bool:
            utilization = _utilization(item)
            return (utilization if utilization is not None else float("-inf")) >= _threshold

        streak = _longest_streak(rows, exceeds_threshold)
        tables.append(
            {
                "limit_id": key[0],
                "portfolio": key[1],
                "pc": key[2],
                "indicator": key[3],
                "metric_name": key[4],
                "version": key[5],
                "unit": current_item.unit,
                "rows": len(rows),
                "date_start": rows[0].day,
                "date_end": rows[-1].day,
                "warning_threshold": round(threshold, 4),
                "mean_utilization": round(statistics.fmean(values), 4),
                "p95_utilization": round(quantile(values, 0.95), 4),
                "max_utilization": round(worst_util, 4),
                "max_utilization_date": worst_item.day,
                "max_utilization_locator": _locator(
                    worst_item.path, worst_item.sheet, worst_item.row
                ),
                "current_utilization": round(current_util, 4),
                "current_date": current_item.day,
                "current_locator": _locator(
                    current_item.path, current_item.sheet, current_item.row
                ),
                "breach_observations": len(breaches),
                "warning_observations": len(proximity),
                "longest_warning_streak_observations": len(streak),
                "current_lower_limit": current_item.lower_limit,
                "current_upper_limit": current_item.upper_limit,
            }
        )
        dates = [item.day.isoformat() for item, _ in valid]
        actual_points = [
            OverviewPoint(label=day, value=round(value, 6))
            for day, (_, value) in zip(dates, valid, strict=True)
        ]
        warning_points = [OverviewPoint(label=day, value=round(threshold, 6)) for day in dates]
        limit_points = [OverviewPoint(label=day, value=1.0) for day in dates]
        digest = hashlib.sha256("|".join(str(part) for part in key).encode("utf-8")).hexdigest()[
            :10
        ]
        overviews.append(
            DataOverview(
                overview_id=(
                    "risk-metrics.limit-utilization"
                    if not overviews
                    else f"risk-metrics.limit-utilization-{digest}"
                ),
                domain=SpecialistDomain.RISK_METRICS,
                source_family="risk_metrics",
                title=f"Limit utilization — {key[1]} {key[3]}",
                summary=(
                    f"Directional utilization for {key[1]} / {key[4]} against the "
                    "effective limit at each observation."
                ),
                status=OverviewStatus.AVAILABLE,
                primary_for_deck=not overviews,
                metrics=[
                    OverviewMetric(
                        label="Current utilization",
                        value=f"{current_util * 100:.1f}%",
                        basis=f"{current_item.day.isoformat()} effective directional limit",
                    ),
                    OverviewMetric(
                        label="Worst utilization",
                        value=f"{worst_util * 100:.1f}%",
                        basis=f"maximum on {worst_item.day.isoformat()}",
                    ),
                    OverviewMetric(
                        label="P95 utilization",
                        value=f"{quantile(values, 0.95) * 100:.1f}%",
                        basis="95th percentile of reviewed observations",
                    ),
                    OverviewMetric(
                        label="Breach observations",
                        value=str(len(breaches)),
                        basis="utilization above 100%",
                    ),
                ],
                visual=LineVisual(
                    x_label="Value date",
                    y_label="Directional utilization",
                    unit="share of effective limit",
                    series=[
                        OverviewSeries(name="Utilization", points=actual_points),
                        OverviewSeries(name="Warning threshold", points=warning_points),
                        OverviewSeries(name="Limit", points=limit_points),
                    ],
                ),
                evidence=_risk_overview_evidence(rows),
                limitations=[
                    "Unlike risk metrics and units are not added or ranked by raw value.",
                    (
                        "Utilization uses the recorded directional bound and does not "
                        "establish position direction."
                    ),
                ],
            )
        )
        if breaches:
            breach_series += 1
            first_item = breaches[0][0]
            last_item = breaches[-1][0]
            flags.append(
                _flag(
                    "limit_breach_population",
                    worst_item.path,
                    worst_item.sheet,
                    worst_item.row,
                    limit_id=worst_item.limit_id,
                    portfolio=worst_item.portfolio,
                    pc=worst_item.pc,
                    indicator=worst_item.indicator,
                    unit=worst_item.unit,
                    breach_observations=len(breaches),
                    first_date=first_item.day.isoformat(),
                    last_date=last_item.day.isoformat(),
                    worst_date=worst_item.day.isoformat(),
                    worst_value=worst_item.value,
                    worst_utilization=round(worst_util, 4),
                    locators=[
                        _locator(item.path, item.sheet, item.row) for item, _ in breaches[:5]
                    ],
                )
            )
        if len(streak) >= NEAR_LIMIT_STREAK:
            proximity_series += 1
            end = streak[-1]
            flags.append(
                _flag(
                    "repeated_limit_proximity",
                    end.path,
                    end.sheet,
                    end.row,
                    limit_id=end.limit_id,
                    portfolio=end.portfolio,
                    indicator=end.indicator,
                    threshold=round(threshold, 4),
                    streak_observations=len(streak),
                    first_date=streak[0].day.isoformat(),
                    last_date=end.day.isoformat(),
                    locators=[_locator(item.path, item.sheet, item.row) for item in streak[:5]],
                )
            )
        limit_levels = {(round(item.lower_limit, 10), round(item.upper_limit, 10)) for item in rows}
        if len(limit_levels) > 1:
            changed = next(
                item
                for item in rows[1:]
                if (item.lower_limit, item.upper_limit)
                != (rows[0].lower_limit, rows[0].upper_limit)
            )
            flags.append(
                _flag(
                    "limit_level_change_in_series",
                    changed.path,
                    changed.sheet,
                    changed.row,
                    limit_id=changed.limit_id,
                    portfolio=changed.portfolio,
                    levels=[list(value) for value in sorted(limit_levels)],
                    detail="approval and effective-date history required for interpretation",
                )
            )
        initial_differences = [
            item
            for item in rows
            if item.initial_lower is not None
            and item.initial_upper is not None
            and (
                not _close(item.lower_limit, item.initial_lower)
                or not _close(item.upper_limit, item.initial_upper)
            )
        ]
        if initial_differences:
            item = initial_differences[0]
            flags.append(
                _flag(
                    "current_limit_differs_from_initial",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    portfolio=item.portfolio,
                    current_bounds=[item.lower_limit, item.upper_limit],
                    initial_bounds=[item.initial_lower, item.initial_upper],
                    detail="difference is not evidence of approval timing",
                )
            )
        temporary = [
            item
            for item in rows
            if item.temporary_lower is not None or item.temporary_upper is not None
        ]
        if temporary:
            item = temporary[0]
            flags.append(
                _flag(
                    "temporary_limit_precedence_unresolved",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    portfolio=item.portfolio,
                    temporary_bounds=[item.temporary_lower, item.temporary_upper],
                    detail="temporary-bound effective dates and approvals are not supplied",
                )
            )
        outside = [
            item for item in rows if item.day < item.limit_start or item.day > item.limit_end
        ]
        if outside:
            item = outside[0]
            flags.append(
                _flag(
                    "consumption_outside_limit_effective_range",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    value_date=item.day.isoformat(),
                    limit_start=item.limit_start.isoformat(),
                    limit_end=item.limit_end.isoformat(),
                    affected_rows=len(outside),
                )
            )
        if len(threshold_values) > 1 or any(
            item.warning_threshold is not None and not 0 < item.warning_threshold < 1
            for item in rows
        ):
            item = rows[0]
            flags.append(
                _flag(
                    "invalid_or_changing_warning_threshold",
                    item.path,
                    item.sheet,
                    item.row,
                    limit_id=item.limit_id,
                    thresholds=sorted(
                        value
                        for value in {item.warning_threshold for item in rows}
                        if value is not None
                    ),
                )
            )
    if not overviews:
        overviews.append(
            DataOverview(
                overview_id="risk-metrics.limit-utilization",
                domain=SpecialistDomain.RISK_METRICS,
                source_family="risk_metrics",
                title="Limit utilization profile",
                summary="No compatible SGMR utilization series was available for charting.",
                status=OverviewStatus.UNAVAILABLE,
                primary_for_deck=True,
                limitations=[
                    "Rerun the review with recognized SGMR rows and valid directional limits."
                ],
            )
        )
    return AnalysisResult(
        name="risk_limit_consumption",
        summary=(
            f"Calculated directional utilization for {len(tables)} comparable series; "
            f"{breach_series} series breached and {proximity_series} had a "
            f"{NEAR_LIMIT_STREAK}+ observation warning streak."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
        overviews=overviews,
    )
