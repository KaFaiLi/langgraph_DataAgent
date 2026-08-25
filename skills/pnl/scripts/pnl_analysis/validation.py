"""Input-contract, validation-workflow, and reconciliation checks."""

from .pnl import _overview_evidence
from .shared import *


def _input_contract(
    tables: list[SourceTable],
    load_issues: list[dict[str, object]],
    parse_issues: list[dict[str, object]],
    pnl: list[PnlRow],
    adjustments: list[AdjustmentRow],
    validation: list[ValidationRow],
    income_attribution: list[IncomeAttributionRow],
    income_issues: list[dict[str, object]],
) -> AnalysisResult:
    role_counts = Counter(table.role for table in tables)
    flags = [*load_issues, *parse_issues, *income_issues]
    for role in ("pnl", "adjustment", "validation"):
        if role_counts[role] == 0:
            flags.append({"kind": "missing_pnl_source_role", "role": role})

    seen_pnl: dict[tuple[dt.date, str, str, str, str], PnlRow] = {}
    for pnl_item in pnl:
        pnl_key = (
            pnl_item.day,
            pnl_item.version,
            pnl_item.notion,
            pnl_item.ptf,
            pnl_item.currency,
        )
        if pnl_key in seen_pnl:
            flags.append(
                _flag(
                    "duplicate_pnl_business_key",
                    pnl_item.path,
                    pnl_item.sheet,
                    pnl_item.row,
                    date=pnl_item.day.isoformat(),
                    version=pnl_item.version,
                    notion=pnl_item.notion,
                    ptf=pnl_item.ptf,
                    currency=pnl_item.currency,
                )
            )
        else:
            seen_pnl[pnl_key] = pnl_item

    seen_adjustments: dict[str, AdjustmentRow] = {}
    for item in adjustments:
        if item.adjustment_id in seen_adjustments:
            flags.append(
                _flag(
                    "duplicate_adjustment_id",
                    item.path,
                    item.sheet,
                    item.row,
                    adjustment_id=item.adjustment_id,
                )
            )
        else:
            seen_adjustments[item.adjustment_id] = item

    active_validation: dict[tuple[str, str, dt.date, str], ValidationRow] = {}
    for validation_item in validation:
        if not validation_item.active:
            continue
        validation_key = (
            validation_item.gop,
            validation_item.team,
            validation_item.request_date,
            validation_item.pnl_type,
        )
        if validation_key in active_validation:
            flags.append(
                _flag(
                    "duplicate_active_validation_key",
                    validation_item.path,
                    validation_item.sheet,
                    validation_item.row,
                    gop=validation_item.gop,
                    team=validation_item.team,
                    request_date=validation_item.request_date.isoformat(),
                    pnl_type=validation_item.pnl_type,
                )
            )
        else:
            active_validation[validation_key] = validation_item

    table_rows: list[dict[str, object]] = [
        {
            "path": table.path,
            "sheet": table.sheet,
            "role": table.role,
            "rows": table.frame.height,
            "columns": list(table.frame.columns),
            "row_locator_offset": table.row_offset,
        }
        for table in tables
    ]
    table_rows.append(
        {
            "parsed_pnl_rows": len(pnl),
            "parsed_adjustment_rows": len(adjustments),
            "parsed_validation_rows": len(validation),
            "parsed_income_attribution_rows": len(income_attribution),
            "contract_issues": len(flags),
        }
    )
    return AnalysisResult(
        name="pnl_input_contract",
        summary=(
            f"Classified {len(tables)} table(s): {len(pnl)} PnL row(s), "
            f"{len(adjustments)} adjustment row(s), and {len(validation)} validation "
            f"row(s), plus {len(income_attribution)} income-attribution row(s); "
            f"{len(flags)} contract candidate(s)."
        ),
        tables=table_rows,
        flag_candidates=flags[:MAX_FLAGS],
    )


def _validation_and_reconciliation(
    validation: list[ValidationRow],
    pnl: list[PnlRow],
    adjustments: list[AdjustmentRow],
) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    states = Counter((item.pnl_type, item.team, item.state, item.active) for item in validation)
    state_rows = [
        {
            "pnl_type": key[0],
            "team": key[1],
            "state": key[2],
            "active": key[3],
            "rows": count,
        }
        for key, count in sorted(states.items())
    ]

    pnl_by_gop: dict[str, PnlRow] = {}
    validation_by_gop: dict[str, ValidationRow] = {}
    for item in pnl:
        pnl_by_gop.setdefault(item.gop, item)
    for validation_item in validation:
        validation_by_gop.setdefault(validation_item.gop, validation_item)
    pnl_gops = set(pnl_by_gop)
    validation_gops = set(validation_by_gop)
    for gop in sorted(pnl_gops - validation_gops):
        item = pnl_by_gop[gop]
        flags.append(
            _flag(
                "pnl_gop_without_validation_history",
                item.path,
                item.sheet,
                item.row,
                gop=gop,
            )
        )
    for gop in sorted(validation_gops - pnl_gops):
        validation_row = validation_by_gop[gop]
        flags.append(
            _flag(
                "validation_gop_without_pnl_rows",
                validation_row.path,
                validation_row.sheet,
                validation_row.row,
                gop=gop,
            )
        )

    pnl_dates = {(item.ptf, item.day) for item in pnl}
    unmatched_adjustments = 0
    for adjustment in adjustments:
        applicable = any(
            (adjustment.ptf, day) in pnl_dates
            for day in (
                adjustment.value_start + dt.timedelta(days=offset)
                for offset in range((adjustment.value_end - adjustment.value_start).days + 1)
            )
        )
        if applicable:
            continue
        unmatched_adjustments += 1
        if len(flags) < MAX_FLAGS:
            flags.append(
                _flag(
                    "adjustment_without_pnl_value_date",
                    adjustment.path,
                    adjustment.sheet,
                    adjustment.row,
                    adjustment_id=adjustment.adjustment_id,
                    ptf=adjustment.ptf,
                    value_start=adjustment.value_start.isoformat(),
                    value_end=adjustment.value_end.isoformat(),
                )
            )

    lag_groups: dict[str, list[float]] = defaultdict(list)
    for validation_item in validation:
        request_time = dt.datetime.combine(validation_item.request_date, dt.time.min)
        created = validation_item.created
        if created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        lag_groups[validation_item.pnl_type].append(
            (created - request_time).total_seconds() / 86400
        )
    lag_rows = [
        {
            "pnl_type": pnl_type,
            "rows": len(values),
            "min_creation_lag_days": round(min(values), 4),
            "mean_creation_lag_days": round(mean(values), 4),
            "max_creation_lag_days": round(max(values), 4),
        }
        for pnl_type, values in sorted(lag_groups.items())
    ]
    histories: dict[tuple[str, str, str], list[ValidationRow]] = defaultdict(list)
    for validation_item in validation:
        if validation_item.active:
            histories[(validation_item.gop, validation_item.team, validation_item.pnl_type)].append(
                validation_item
            )
    persistence_rows: list[dict[str, object]] = []
    for key, rows in sorted(histories.items()):
        ordered = sorted(rows, key=lambda item: (item.request_date, item.created, item.row))
        longest: list[ValidationRow] = []
        current: list[ValidationRow] = []
        for history_item in ordered:
            if current and history_item.state != current[-1].state:
                current = []
            current.append(history_item)
            if len(current) > len(longest):
                longest = list(current)
        persistence_rows.append(
            {
                "gop": key[0],
                "team": key[1],
                "pnl_type": key[2],
                "active_observations": len(ordered),
                "longest_same_state": longest[0].state if longest else None,
                "longest_same_state_observations": len(longest),
                "state_run_start": longest[0].request_date if longest else None,
                "state_run_end": longest[-1].request_date if longest else None,
                "start_locator": (
                    _locator(longest[0].path, longest[0].sheet, longest[0].row) if longest else None
                ),
                "end_locator": (
                    _locator(longest[-1].path, longest[-1].sheet, longest[-1].row)
                    if longest
                    else None
                ),
                "interpretation": "state dictionary and cadence required",
            }
        )

    non_final_tokens = ("not validated", "waiting", "pending", "failed", "error")
    adjustments_by_gop_date: dict[tuple[str, dt.date], list[AdjustmentRow]] = defaultdict(list)
    for adjustment in adjustments:
        adjustments_by_gop_date[(adjustment.gop, adjustment.value_end)].append(adjustment)
    grouped_non_final: dict[tuple[str, dt.date], list[ValidationRow]] = defaultdict(list)
    for validation_item in validation:
        if not validation_item.active or not any(
            token in validation_item.state.lower() for token in non_final_tokens
        ):
            continue
        adjustment_key = (validation_item.gop, validation_item.request_date)
        if adjustment_key in adjustments_by_gop_date:
            grouped_non_final[adjustment_key].append(validation_item)
    for (gop, request_date), rows in sorted(grouped_non_final.items()):
        adjustment_rows = adjustments_by_gop_date[(gop, request_date)]
        example = rows[0]
        flags.append(
            _flag(
                "non_final_validation_near_adjustment",
                example.path,
                example.sheet,
                example.row,
                gop=gop,
                request_date=request_date.isoformat(),
                states=sorted({row.state for row in rows}),
                teams=sorted({row.team for row in rows}),
                validation_locators=[_locator(row.path, row.sheet, row.row) for row in rows],
                adjustment_ids=[row.adjustment_id for row in adjustment_rows],
                adjustment_locators=[
                    _locator(row.path, row.sheet, row.row) for row in adjustment_rows
                ],
                detail=(
                    "active non-final validation states coincide with one or more "
                    "adjustment value dates"
                ),
                severity_floor="medium",
                severity_basis=(
                    "recognized active non-final validation states on an adjustment "
                    "date are a material close-control gap pending workflow context"
                ),
                severity_match_terms=["validation", "non-final"],
                measured_observation=True,
            )
        )
    reconciliation = {
        "pnl_gops": len(pnl_gops),
        "validation_gops": len(validation_gops),
        "pnl_only_gops": sorted(pnl_gops - validation_gops),
        "validation_only_gops": sorted(validation_gops - pnl_gops),
        "adjustments_without_pnl_value_date": unmatched_adjustments,
        "monetary_reconciliation": "UNRESOLVED",
        "reason": (
            "PnL unit and pre/post-adjustment inclusion basis are not declared by the "
            "finalized file headers."
        ),
    }
    validation_overview = (
        DataOverview(
            overview_id="pnl.validation-profile",
            domain=SpecialistDomain.PNL,
            source_family="pnl_validation",
            title="PnL validation-state profile",
            summary=(
                "Validation rows are profiled by PnL type, team, state, and active flag; "
                "state meaning and workflow cadence remain source-dependent."
            ),
            status=OverviewStatus.AVAILABLE,
            metrics=[
                OverviewMetric(
                    label="Validation rows",
                    value=str(len(validation)),
                    unit="count",
                    basis="parsed validation history",
                ),
                OverviewMetric(
                    label="Active rows",
                    value=str(sum(item.active for item in validation)),
                    unit="count",
                    basis="supplied active flag",
                ),
                OverviewMetric(
                    label="States",
                    value=str(len({item.state for item in validation})),
                    unit="count",
                    basis="distinct supplied state labels",
                ),
                OverviewMetric(
                    label="Validation GOPs",
                    value=str(len(validation_gops)),
                    unit="count",
                    basis="distinct validation GOP values",
                ),
            ],
            visual=TableVisual(
                columns=["PnL type", "Team", "State", "Active", "Rows"],
                rows=[
                    [
                        str(row["pnl_type"]),
                        str(row["team"]),
                        str(row["state"]),
                        "Yes" if row["active"] else "No",
                        str(row["rows"]),
                    ]
                    for row in state_rows
                ],
            ),
            evidence=_overview_evidence(validation),
            limitations=[
                "State labels are reported values; no workflow-state dictionary was supplied.",
                (
                    "Monetary reconciliation remains unavailable without a declared unit "
                    "and inclusion basis."
                ),
            ],
        )
        if validation
        else DataOverview(
            overview_id="pnl.validation-profile",
            domain=SpecialistDomain.PNL,
            source_family="pnl_validation",
            title="PnL validation-state profile",
            summary="No compatible validation-history population was available for profiling.",
            status=OverviewStatus.UNAVAILABLE,
            limitations=[
                "Overview unavailable because no rows matched the finalized validation schema."
            ],
        )
    )
    return AnalysisResult(
        name="pnl_validation_and_reconciliation",
        summary=(
            f"Profiled {len(validation)} validation row(s), compared GOP populations, "
            f"and checked {len(adjustments)} adjustment valuation range(s) against PnL; "
            f"monetary reconciliation remains unresolved until units and inclusion basis "
            f"are documented."
        ),
        tables=[*state_rows, *lag_rows, *persistence_rows, reconciliation],
        flag_candidates=flags[:MAX_FLAGS],
        overviews=[validation_overview],
    )
