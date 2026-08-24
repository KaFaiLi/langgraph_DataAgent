"""PnL integrity, behavior, and overview checks."""

# ruff: noqa: F403, F405
from .shared import *


def _series_key(item: PnlRow) -> tuple[str, str, str, str]:
    return (item.version, item.notion, item.ptf, item.currency)


def _period_key(day: dt.date, period: str) -> object:
    if period == "wtd":
        return day - dt.timedelta(days=day.weekday())
    if period == "mtd":
        return (day.year, day.month)
    if period == "qtd":
        return (day.year, (day.month - 1) // 3 + 1)
    return day.year


def _overview_evidence(rows: Sequence[_EvidenceRow]) -> list[EvidenceReference]:
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


def _pnl_overviews(pnl: list[PnlRow]) -> list[DataOverview]:
    grouped: dict[tuple[str, str, str, str], list[PnlRow]] = defaultdict(list)
    for item in pnl:
        grouped[_series_key(item)].append(item)
    if not grouped:
        return [
            DataOverview(
                overview_id="pnl.cumulative-by-year",
                domain=SpecialistDomain.PNL,
                source_family="pnl",
                title="Cumulative PnL by calendar year",
                summary="No compatible finalized PnL series was available for charting.",
                status=OverviewStatus.UNAVAILABLE,
                primary_for_deck=True,
                limitations=["Rerun the review with a recognized AIR accumulated-PnL table."],
            )
        ]

    overviews: list[DataOverview] = []
    for index, (key, raw_rows) in enumerate(sorted(grouped.items())):
        rows = sorted(raw_rows, key=lambda item: (item.day, item.path, item.row))
        by_year: dict[int, list[PnlRow]] = defaultdict(list)
        for item in rows:
            by_year[item.day.year].append(item)
        series: list[OverviewSeries] = []
        metrics: list[OverviewMetric] = []
        for year, year_rows in sorted(by_year.items()):
            running = 0.0
            points: list[OverviewPoint] = []
            for item in year_rows:
                running += item.dtd
                points.append(OverviewPoint(label=item.day.isoformat(), value=round(running, 6)))
            series.append(OverviewSeries(name=str(year), points=points))
            metrics.append(
                OverviewMetric(
                    label=f"{year} total",
                    value=f"{running:g}",
                    unit=key[3],
                    basis="calendar-year cumulative DTD in source units",
                )
            )
        digest = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:10]
        overview_id = "pnl.cumulative-by-year" if index == 0 else f"pnl.cumulative-by-year-{digest}"
        limitation = (
            "No aggregation across currencies, notions, versions, or PTFs was performed."
            if len(grouped) == 1
            else (
                f"This is one of {len(grouped)} comparable PnL series; it is not a "
                "desk total and no cross-series aggregation was performed."
            )
        )
        overviews.append(
            DataOverview(
                overview_id=overview_id,
                domain=SpecialistDomain.PNL,
                source_family="pnl",
                title=f"Cumulative PnL by year — {key[2]} ({key[3]})",
                summary=(
                    "Daily DTD PnL is accumulated from zero within each calendar year "
                    f"for Version={key[0]}, Notion={key[1]}, PTF={key[2]}."
                ),
                status=OverviewStatus.AVAILABLE,
                primary_for_deck=index == 0,
                metrics=metrics,
                visual=LineVisual(
                    x_label="Business date",
                    y_label="Cumulative PnL",
                    unit=key[3],
                    series=series,
                ),
                evidence=_overview_evidence(rows),
                limitations=[
                    limitation,
                    (
                        "The source identifies currency but does not document the scale "
                        "or sign convention."
                    ),
                ],
            )
        )
    return overviews


def _pnl_integrity(pnl: list[PnlRow]) -> AnalysisResult:
    grouped: dict[tuple[str, str, str, str], list[PnlRow]] = defaultdict(list)
    reference_dates: dict[tuple[str, str, str], set[dt.date]] = defaultdict(set)
    mappings: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for item in pnl:
        grouped[_series_key(item)].append(item)
        reference_dates[(item.version, item.notion, item.currency)].add(item.day)
        mappings[item.ptf].add((item.gop, item.pc, item.currency))

    flags: list[dict[str, object]] = []
    for ptf, values in sorted(mappings.items()):
        if len(values) <= 1:
            continue
        example = next(item for item in pnl if item.ptf == ptf)
        flags.append(
            _flag(
                "unstable_pnl_hierarchy_mapping",
                example.path,
                example.sheet,
                example.row,
                ptf=ptf,
                mappings=[list(value) for value in sorted(values)],
            )
        )

    tables: list[dict[str, object]] = []
    mismatch_total = 0
    for key, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: (item.day, item.path, item.row))
        population_dates = reference_dates[(key[0], key[1], key[3])]
        observed_dates = {item.day for item in ordered}
        coverage = len(observed_dates) / len(population_dates) if population_dates else 0.0
        if coverage < SERIES_COVERAGE_MIN:
            example = ordered[0]
            flags.append(
                _flag(
                    "incomplete_pnl_series_coverage",
                    example.path,
                    example.sheet,
                    example.row,
                    version=example.version,
                    notion=example.notion,
                    ptf=example.ptf,
                    currency=example.currency,
                    observed_dates=len(observed_dates),
                    population_dates=len(population_dates),
                    coverage=round(coverage, 4),
                )
            )
        mismatches: Counter[str] = Counter()
        running: dict[str, tuple[object, float]] = {}
        for item in ordered:
            for field in ("wtd", "mtd", "qtd", "ytd"):
                period = _period_key(item.day, field)
                previous_period, previous_total = running.get(field, (None, 0.0))
                expected = item.dtd if period != previous_period else previous_total + item.dtd
                running[field] = (period, expected)
                actual = float(getattr(item, field))
                tolerance = max(0.00001, abs(expected) * 0.000001)
                if abs(actual - expected) <= tolerance:
                    continue
                mismatches[field] += 1
                if len(flags) < MAX_FLAGS:
                    flags.append(
                        _flag(
                            "pnl_cumulative_mismatch",
                            item.path,
                            item.sheet,
                            item.row,
                            date=item.day.isoformat(),
                            ptf=item.ptf,
                            field=field.upper(),
                            actual=round(actual, 6),
                            expected=round(expected, 6),
                        )
                    )
        tables.append(
            {
                "version": key[0],
                "notion": key[1],
                "ptf": key[2],
                "currency": key[3],
                "rows": len(ordered),
                "observed_dates": len(observed_dates),
                "population_dates": len(population_dates),
                "coverage": round(coverage, 4),
                "date_start": ordered[0].day.isoformat(),
                "date_end": ordered[-1].day.isoformat(),
                "dtd_total": round(sum(item.dtd for item in ordered), 6),
                "cumulative_mismatches": dict(mismatches),
            }
        )
        mismatch_total += sum(mismatches.values())
    return AnalysisResult(
        name="pnl_cumulative_integrity",
        summary=(
            f"Reperformed accumulated PnL for {len(tables)} comparable series; "
            f"{mismatch_total} cumulative mismatch(es) and "
            f"{sum(len(values) > 1 for values in mappings.values())} unstable mapping(s)."
        ),
        tables=tables,
        flag_candidates=flags,
        overviews=_pnl_overviews(pnl),
    )


def _pnl_patterns(pnl: list[PnlRow]) -> AnalysisResult:
    grouped: dict[tuple[str, str, str, str], list[PnlRow]] = defaultdict(list)
    for item in pnl:
        grouped[_series_key(item)].append(item)

    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    for key, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: (item.day, item.path, item.row))
        values = [item.dtd for item in ordered]
        if len(values) < MIN_PATTERN_ROWS:
            tables.append({"ptf": key[2], "rows": len(values), "status": "insufficient"})
            continue
        average = mean(values)
        deviation = pstdev(values)
        scores = zscore(values)
        outlier_matches: list[tuple[PnlRow, float]] = []
        for item, z in zip(ordered, scores, strict=True):
            if abs(z) >= OUTLIER_Z:
                outlier_matches.append((item, z))

        reversal_matches: list[tuple[PnlRow, PnlRow, float, float]] = []
        for index, (first, second) in enumerate(zip(ordered, ordered[1:], strict=False)):
            if first.dtd * second.dtd >= 0 or first.dtd == 0:
                continue
            first_z = abs(scores[index])
            second_z = abs(scores[index + 1])
            ratio = abs(second.dtd / first.dtd)
            if (
                first_z < REVERSAL_Z
                or second_z < REVERSAL_Z
                or not REVERSAL_RATIO_MIN <= ratio <= REVERSAL_RATIO_MAX
            ):
                continue
            reversal_matches.append((first, second, ratio, min(first_z, second_z)))

        run_matches: list[tuple[int, PnlRow, PnlRow, float]] = []
        run_start = 0
        for index in range(1, len(ordered) + 1):
            run_ended = index == len(ordered) or ordered[index].dtd * ordered[run_start].dtd <= 0
            if not run_ended:
                continue
            run_length = index - run_start
            if run_length >= STREAK_MIN and ordered[run_start].dtd != 0:
                start = ordered[run_start]
                end = ordered[index - 1]
                run_matches.append(
                    (
                        run_length,
                        start,
                        end,
                        sum(item.dtd for item in ordered[run_start:index]),
                    )
                )
            run_start = index

        last_by_month: dict[tuple[int, int], dt.date] = {}
        for item in ordered:
            month = (item.day.year, item.day.month)
            last_by_month[month] = max(last_by_month.get(month, item.day), item.day)
        period_end = [
            item for item in ordered if item.day == last_by_month[(item.day.year, item.day.month)]
        ]
        other = [
            item for item in ordered if item.day != last_by_month[(item.day.year, item.day.month)]
        ]
        end_mean = mean([abs(item.dtd) for item in period_end]) if period_end else 0.0
        other_mean = mean([abs(item.dtd) for item in other]) if other else 0.0
        period_end_ratio = end_mean / other_mean if other_mean else None
        period_end_candidate = (
            len(period_end) >= 3
            and period_end_ratio is not None
            and period_end_ratio >= MONTH_END_RATIO
        )

        series_flags: list[dict[str, object]] = []
        if outlier_matches:
            item, z = max(outlier_matches, key=lambda match: abs(match[1]))
            series_flags.append(
                _flag(
                    "large_ptf_dtd",
                    item.path,
                    item.sheet,
                    item.row,
                    date=item.day.isoformat(),
                    ptf=item.ptf,
                    currency=item.currency,
                    dtd=round(item.dtd, 6),
                    z=round(z, 4),
                    series_candidates=len(outlier_matches),
                )
            )
        if reversal_matches:
            first, second, ratio, _ = max(reversal_matches, key=lambda match: match[3])
            series_flags.append(
                _flag(
                    "ptf_dtd_reversal",
                    first.path,
                    first.sheet,
                    first.row,
                    date=first.day.isoformat(),
                    next_date=second.day.isoformat(),
                    next_locator=_locator(second.path, second.sheet, second.row),
                    ptf=first.ptf,
                    dtd=round(first.dtd, 6),
                    next_dtd=round(second.dtd, 6),
                    ratio=round(ratio, 4),
                    series_candidates=len(reversal_matches),
                )
            )
        if run_matches:
            run_length, start, end, total = max(run_matches, key=lambda match: match[0])
            series_flags.append(
                _flag(
                    "ptf_dtd_same_sign_run",
                    start.path,
                    start.sheet,
                    start.row,
                    date=start.day.isoformat(),
                    end_date=end.day.isoformat(),
                    end_locator=_locator(end.path, end.sheet, end.row),
                    ptf=start.ptf,
                    sign="positive" if start.dtd > 0 else "negative",
                    run_length=run_length,
                    total=round(total, 6),
                    series_candidates=len(run_matches),
                )
            )
        if period_end_candidate:
            assert period_end_ratio is not None
            example = period_end[-1]
            series_flags.append(
                _flag(
                    "ptf_period_end_concentration",
                    example.path,
                    example.sheet,
                    example.row,
                    date=example.day.isoformat(),
                    ptf=example.ptf,
                    observed_month_ends=len(period_end),
                    mean_abs_period_end=round(end_mean, 6),
                    mean_abs_other=round(other_mean, 6),
                    ratio=round(period_end_ratio, 4),
                )
            )
        flags.extend(series_flags)
        tables.append(
            {
                "version": key[0],
                "notion": key[1],
                "ptf": key[2],
                "currency": key[3],
                "rows": len(values),
                "mean_dtd": round(average, 6),
                "stdev_dtd": round(deviation, 6),
                "min_dtd": round(min(values), 6),
                "max_dtd": round(max(values), 6),
                "outlier_candidates": len(outlier_matches),
                "reversal_candidates": len(reversal_matches),
                "same_sign_run_candidates": len(run_matches),
                "period_end_ratio": (
                    round(period_end_ratio, 4) if period_end_ratio is not None else None
                ),
            }
        )
    return AnalysisResult(
        name="pnl_statistical_patterns",
        summary=(
            f"Screened {len(tables)} comparable PTF series without aggregating currencies; "
            f"{len(flags)} statistical candidate(s) retained for interpretation."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
    )
