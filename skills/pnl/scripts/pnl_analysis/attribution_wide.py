"""Wide AIR income-attribution schema, profile, and workflow checks."""

# ruff: noqa: F403, F405
from .pnl import _overview_evidence
from .shared import *


def _income_attribution_schema(
    rows: list[IncomeAttributionRow],
    tables: list[SourceTable],
    issues: list[dict[str, object]],
) -> AnalysisResult:
    """Report the wide export contract and its explicitly observed populations."""
    income_tables = [table for table in tables if table.role == "income_attribution"]
    table_rows: list[dict[str, object]] = []
    for table in income_tables:
        table_rows.append(
            {
                "path": table.path,
                "sheet": table.sheet,
                "rows": table.frame.height,
                "columns": len(table.frame.columns),
                "date_column": column_map(table.frame).get("asofdate"),
                "total_column": column_map(table.frame).get("final result acc dtd"),
                "component_columns": [
                    name
                    for name in INCOME_PRIMARY_COMPONENTS
                    if name.lower() in normalized_columns(table.frame)
                ],
                "cumulative_columns": [
                    name
                    for name in INCOME_PRIMARY_COMPONENTS
                    if f"{name.lower()} cumulative" in normalized_columns(table.frame)
                ],
            }
        )
    dates = sorted({item.day for item in rows})
    statuses = Counter(item.status for item in rows if item.status)
    table_rows.append(
        {
            "parsed_rows": len(rows),
            "entities": len({item.entity for item in rows}),
            "date_start": dates[0] if dates else None,
            "date_end": dates[-1] if dates else None,
            "status_counts": dict(sorted(statuses.items())),
            "invalid_rows": len(issues),
        }
    )
    return AnalysisResult(
        name="income_attribution_schema",
        summary=(
            f"Recognized {len(income_tables)} wide income-attribution table(s) with "
            f"{len(rows)} parsed row(s), {len({item.entity for item in rows})} entity "
            f"population(s), and {len(issues)} schema/data-quality candidate(s)."
        ),
        tables=table_rows,
        flag_candidates=issues[:MAX_FLAGS],
    )


def _income_attribution_driver_profile(
    rows: list[IncomeAttributionRow],
) -> AnalysisResult:
    """Profile primary reported buckets while keeping nested leaf fields separate."""
    signed: defaultdict[str, float] = defaultdict(float)
    absolute: defaultdict[str, float] = defaultdict(float)
    nonzero: Counter[str] = Counter()
    for item in rows:
        for component, value in item.components.items():
            signed[component] += value
            absolute[component] += abs(value)
            if value != 0:
                nonzero[component] += 1

    total_absolute = sum(absolute.values())
    shares = (
        {name: value / total_absolute for name, value in absolute.items()} if total_absolute else {}
    )
    ordered = sorted(shares.items(), key=lambda pair: (-pair[1], pair[0]))
    top_three = sum(share for _, share in ordered[:3])
    residual_absolute = sum(
        value for name, value in absolute.items() if name.lower() in INCOME_RESIDUAL_COMPONENTS
    )
    residual_share = residual_absolute / total_absolute if total_absolute else 0.0
    table = {
        "rows": len(rows),
        "components": len(absolute),
        "absolute_primary_component_total": round(total_absolute, 6),
        "top3_share": round(top_three, 6),
        "residual_component_share": round(residual_share, 6),
        "components_by_absolute_amount": [
            {
                "component": component,
                "signed_amount": round(signed[component], 6),
                "absolute_amount": round(absolute[component], 6),
                "share": round(share, 6),
                "nonzero_rows": nonzero[component],
            }
            for component, share in ordered
        ],
        "interpretation": (
            "Primary buckets are profiled independently. Parent and leaf attribution "
            "columns are not added together and this view is not a monetary reconciliation."
        ),
    }
    flags: list[dict[str, object]] = []
    representative = rows[0] if rows else None
    if representative is not None and top_three >= 0.7:
        flags.append(
            _flag(
                "income_attribution_primary_concentration",
                representative.path,
                representative.sheet,
                representative.row,
                top3_share=round(top_three, 6),
                component_count=len(absolute),
                detail=(
                    "three primary attribution buckets contain at least 70% of "
                    "profiled absolute amounts"
                ),
            )
        )
    if representative is not None and residual_share >= 0.2:
        flags.append(
            _flag(
                "income_attribution_residual_share",
                representative.path,
                representative.sheet,
                representative.row,
                residual_share=round(residual_share, 6),
                detail=(
                    "residual, unexplained, or no-attribution buckets contain at least "
                    "20% of profiled absolute amounts"
                ),
            )
        )
    overview = (
        DataOverview(
            overview_id="pnl.income-attribution-driver-profile",
            domain=SpecialistDomain.PNL,
            source_family="income_attribution",
            title="Income-attribution primary driver profile",
            summary=(
                "The wide export's reported primary attribution buckets are shown by "
                "absolute amount; nested columns are not double-counted into this view."
            ),
            status=OverviewStatus.AVAILABLE,
            metrics=[
                OverviewMetric(
                    label="Top-three share",
                    value=f"{top_three:.2%}",
                    unit="share of profiled absolute components",
                    basis="primary attribution buckets",
                ),
                OverviewMetric(
                    label="Residual share",
                    value=f"{residual_share:.2%}",
                    unit="share of profiled absolute components",
                    basis="unexplained/other/no-attribution bucket names",
                ),
                OverviewMetric(
                    label="Primary buckets",
                    value=str(len(absolute)),
                    unit="count",
                    basis="recognized wide-export columns",
                ),
            ],
            visual=BarVisual(
                x_label="Primary attribution bucket",
                y_label="Share of profiled absolute components",
                unit="share",
                series=[
                    OverviewSeries(
                        name="Absolute component share",
                        points=[
                            OverviewPoint(label=component, value=round(share, 8))
                            for component, share in ordered
                        ],
                    )
                ],
            ),
            evidence=_overview_evidence(rows),
            limitations=[
                (
                    "The export contains parent and leaf fields; this view does not "
                    "sum them into a total."
                ),
                (
                    "Business units, currencies, and sign conventions are not supplied "
                    "by this export contract."
                ),
            ],
        )
        if rows
        else DataOverview(
            overview_id="pnl.income-attribution-driver-profile",
            domain=SpecialistDomain.PNL,
            source_family="income_attribution",
            title="Income-attribution primary driver profile",
            summary="No valid wide-export rows were available for driver profiling.",
            status=OverviewStatus.UNAVAILABLE,
            limitations=[
                "Profile unavailable because asofdate, GOP, or total fields were invalid."
            ],
        )
    )
    return AnalysisResult(
        name="income_attribution_driver_profile",
        summary=(
            f"Profiled {len(absolute)} primary attribution bucket(s) across {len(rows)} "
            f"row(s); top-three share is {top_three:.2%} and residual share is "
            f"{residual_share:.2%}."
        ),
        tables=[table] if rows else [],
        flag_candidates=flags,
        overviews=[overview],
    )


def _persistent_income_attribution(
    rows: list[IncomeAttributionRow],
) -> AnalysisResult:
    """Detect sustained dominance of one reported primary component by entity."""
    grouped: dict[tuple[str, ...], list[IncomeAttributionRow]] = defaultdict(list)
    for item in rows:
        grouped[item.entity].append(item)
    flags: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    window = 20
    for entity, raw_rows in sorted(grouped.items()):
        ordered = sorted(raw_rows, key=lambda item: (item.day, item.row))
        if len(ordered) < window:
            continue
        best: tuple[float, float, str, list[IncomeAttributionRow]] | None = None
        components = sorted({name for item in ordered for name in item.components})
        for start in range(len(ordered) - window + 1):
            sample = ordered[start : start + window]
            total_absolute = sum(abs(item.total) for item in sample)
            if total_absolute == 0:
                continue
            for component in components:
                values = [item.components.get(component, 0.0) for item in sample]
                absolute_share = sum(abs(value) for value in values) / total_absolute
                nonzero = [value for value in values if value != 0]
                if not nonzero:
                    continue
                same_sign_share = max(
                    sum(value > 0 for value in nonzero),
                    sum(value < 0 for value in nonzero),
                ) / len(nonzero)
                candidate = (absolute_share, same_sign_share, component, sample)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
        if best is None:
            continue
        absolute_share, same_sign_share, component, sample = best
        tables.append(
            {
                "entity": dict(zip(INCOME_HIERARCHY_COLUMNS, entity, strict=True)),
                "component": component,
                "window_observations": window,
                "window_start": sample[0].day,
                "window_end": sample[-1].day,
                "absolute_component_share_of_total": round(absolute_share, 6),
                "same_sign_share": round(same_sign_share, 6),
            }
        )
        if absolute_share < 0.75 or same_sign_share < 0.85:
            continue
        middle = sample[len(sample) // 2]
        flags.append(
            _flag(
                "persistent_income_attribution_contribution",
                sample[-1].path,
                sample[-1].sheet,
                sample[-1].row,
                entity=dict(zip(INCOME_HIERARCHY_COLUMNS, entity, strict=True)),
                gop=entity[-1],
                component=component,
                window_observations=window,
                first_date=sample[0].day.isoformat(),
                last_date=sample[-1].day.isoformat(),
                absolute_component_share_of_total=round(absolute_share, 6),
                same_sign_share=round(same_sign_share, 6),
                locators=[
                    _locator(sample[0].path, sample[0].sheet, sample[0].row),
                    _locator(middle.path, middle.sheet, middle.row),
                    _locator(sample[-1].path, sample[-1].sheet, sample[-1].row),
                ],
                detail=(
                    "one reported attribution component remained dominant across a "
                    "20-observation window; parent and leaf components were not added"
                ),
            )
        )
    return AnalysisResult(
        name="income_attribution_persistence",
        summary=(
            f"Screened {len(grouped)} hierarchy series for sustained single-component "
            f"dominance and produced {len(flags)} candidate(s)."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
    )


def _income_attribution_reconciliation(
    rows: list[IncomeAttributionRow],
) -> AnalysisResult:
    """Compare DTD totals to the supplied cumulative total within each hierarchy series."""
    grouped: dict[tuple[str, str | None, tuple[str, ...]], list[IncomeAttributionRow]] = (
        defaultdict(list)
    )
    for item in rows:
        grouped[(item.path, item.sheet, item.entity)].append(item)
    tables: list[dict[str, object]] = []
    flags: list[dict[str, object]] = []
    compared = 0
    for key, group in sorted(grouped.items(), key=lambda pair: pair[0]):
        ordered = sorted(group, key=lambda item: (item.day, item.row))
        reported = [item.cumulative.get("Final Result Acc DTD") for item in ordered]
        if not any(value is not None for value in reported):
            continue
        expected = sum(item.total for item in ordered)
        last_reported = next(value for value in reversed(reported) if value is not None)
        difference = float(last_reported) - expected
        tolerance = max(0.01, abs(expected) * 0.000001)
        compared += 1
        table: dict[str, object] = {
            "path": key[0],
            "sheet": key[1],
            "entity": dict(zip(INCOME_HIERARCHY_COLUMNS, key[2], strict=True)),
            "rows": len(ordered),
            "date_start": ordered[0].day,
            "date_end": ordered[-1].day,
            "sum_final_result_acc_dtd": round(expected, 6),
            "reported_final_result_acc_dtd_cumulative": round(float(last_reported), 6),
            "difference": round(difference, 6),
            "tolerance": round(tolerance, 6),
        }
        tables.append(table)
        if abs(difference) > tolerance and len(flags) < MAX_FLAGS:
            last = ordered[-1]
            flags.append(
                _flag(
                    "income_attribution_cumulative_mismatch",
                    last.path,
                    last.sheet,
                    last.row,
                    entity=table["entity"],
                    expected=round(expected, 6),
                    reported=round(float(last_reported), 6),
                    difference=round(difference, 6),
                    tolerance=round(tolerance, 6),
                )
            )
    return AnalysisResult(
        name="income_attribution_reconciliation",
        summary=(
            f"Compared {compared} hierarchy series between Final Result Acc DTD and "
            f"its supplied cumulative field; {len(flags)} mismatch candidate(s)."
        ),
        tables=tables,
        flag_candidates=flags,
    )


def _income_attribution_status(rows: list[IncomeAttributionRow]) -> AnalysisResult:
    """Profile processing and validation states without assigning their meanings."""
    status_counts = Counter(item.status or "<blank>" for item in rows)
    validation_counts = Counter(item.validated or "<blank>" for item in rows)
    mpc_counts = Counter(item.mpc_status or "<blank>" for item in rows)
    fo_counts = Counter(item.fo_status or "<blank>" for item in rows)
    batch_counts = Counter(
        (
            "true"
            if item.batch_validated
            else "false"
            if item.batch_validated is not None
            else "<blank>"
        )
        for item in rows
    )
    flags: list[dict[str, object]] = []
    state_tokens = ("running", "failed", "error", "not validated", "invalid")
    for item in rows:
        statuses = {
            "status": item.status,
            "validated": item.validated,
            "air_mpc_validation_status": item.mpc_status,
            "air_fo_validation status": item.fo_status,
        }
        flagged_statuses = {
            field: value
            for field, value in statuses.items()
            if any(token in value.lower() for token in state_tokens)
        }
        if flagged_statuses and len(flags) < MAX_FLAGS:
            flags.append(
                _flag(
                    "income_attribution_processing_state",
                    item.path,
                    item.sheet,
                    item.row,
                    status=item.status,
                    statuses=flagged_statuses,
                    validated=item.validated,
                    batch_validated=item.batch_validated,
                    asofdate=item.day.isoformat(),
                    gop=item.entity[-1],
                    detail=(
                        "reported processing state requires workflow-state and SLA interpretation"
                    ),
                )
            )
    tables: list[dict[str, object]] = [
        {"field": "status", "values": dict(sorted(status_counts.items()))},
        {"field": "validated", "values": dict(sorted(validation_counts.items()))},
        {
            "field": "air_mpc_validation_status",
            "values": dict(sorted(mpc_counts.items())),
        },
        {
            "field": "air_fo_validation status",
            "values": dict(sorted(fo_counts.items())),
        },
        {"field": "isbatchvalidated", "values": dict(sorted(batch_counts.items()))},
        {
            "rows": len(rows),
            "latest_asofdate": max((item.day for item in rows), default=None),
            "distinct_gops": len({item.entity[-1] for item in rows}),
        },
    ]
    return AnalysisResult(
        name="income_attribution_status",
        summary=(
            f"Profiled status and validation fields for {len(rows)} row(s); "
            f"{len(flags)} reported processing-state candidate(s) require workflow interpretation."
        ),
        tables=tables,
        flag_candidates=flags,
    )
