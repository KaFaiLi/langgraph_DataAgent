"""Colibris excess-workflow checks."""

# ruff: noqa: F403, F405
from .shared import *
from .sources import _norm


def _excess_usage(item: ExcessRow) -> float:
    return abs(item.value) / abs(item.limit_value)


def _has_increase_id(item: ExcessRow) -> bool:
    return item.increase_id not in {"", "0", "0.0"}


def _excess_workflow(excesses: list[ExcessRow], sgmr: list[SgmrRow]) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    as_of_candidates = [item.day for item in sgmr]
    as_of_candidates.extend(item.created.date() for item in excesses)
    as_of = max(as_of_candidates, default=None)
    groups: dict[tuple[str, str, str, float], list[ExcessRow]] = defaultdict(list)
    for item in excesses:
        groups[
            (
                _norm(item.pc),
                _norm(item.indicator),
                _norm(item.unit),
                round(item.limit_value, 8),
            )
        ].append(item)
    tables: list[dict[str, object]] = [
        {
            "table_type": "excess_population",
            "events": len(excesses),
            "open_events": sum(item.still_open for item in excesses),
            "manually_closed_events": sum(item.closed_manually is True for item in excesses),
            "date_start": min((item.created.date() for item in excesses), default=None),
            "date_end": max((item.created.date() for item in excesses), default=None),
            "analysis_as_of": as_of,
            "workflow_states": dict(Counter(item.workflow_status for item in excesses)),
            "validation_classes": dict(
                Counter(item.validation_classification for item in excesses)
            ),
        }
    ]
    for _key, raw_rows in sorted(groups.items()):
        rows = sorted(raw_rows, key=lambda item: (item.created, item.row))
        usages = [_excess_usage(item) for item in rows]
        table = {
            "table_type": "excess_group",
            "pc": rows[0].pc,
            "indicator": rows[0].indicator,
            "unit": rows[0].unit,
            "limit_value": rows[0].limit_value,
            "events": len(rows),
            "open_events": sum(item.still_open for item in rows),
            "first_created": rows[0].created,
            "last_created": rows[-1].created,
            "max_last_usage": round(max(usages), 4),
            "max_recorded_usage_pct": max(
                (item.max_usage_pct for item in rows if item.max_usage_pct is not None),
                default=None,
            ),
            "max_days_in_excess": max(
                (item.days_in_excess for item in rows if item.days_in_excess is not None),
                default=None,
            ),
            "example_locators": [_locator(item.path, item.sheet, item.row) for item in rows[:3]],
        }
        tables.append(table)
        if len(rows) >= 3:
            flags.append(
                _flag(
                    "repeated_excess_population",
                    rows[-1].path,
                    rows[-1].sheet,
                    rows[-1].row,
                    pc=rows[-1].pc,
                    indicator=rows[-1].indicator,
                    unit=rows[-1].unit,
                    limit_value=rows[-1].limit_value,
                    events=len(rows),
                    open_events=sum(item.still_open for item in rows),
                    first_created=rows[0].created.isoformat(),
                    last_created=rows[-1].created.isoformat(),
                    max_last_usage=round(max(usages), 4),
                    locators=[
                        _locator(item.path, item.sheet, item.row) for item in [*rows[:2], rows[-1]]
                    ],
                    detail="selected excess population; denominator is not all risk days",
                )
            )
    for item in excesses:
        usage = _excess_usage(item)
        if item.usage_pct is not None and abs(item.usage_pct - usage) > 0.015:
            flags.append(
                _flag(
                    "colibris_usage_reperformance_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    reported_usage=item.usage_pct,
                    expected_usage=round(usage, 6),
                )
            )
        if item.max_usage_pct is not None and item.max_usage_pct / 100 + 0.01 < usage:
            flags.append(
                _flag(
                    "colibris_max_usage_below_last_usage",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    max_usage_pct=item.max_usage_pct,
                    last_usage=round(usage, 6),
                )
            )
        status_open = "OPEN" in _norm(item.workflow_status)
        state_issue = (
            status_open != item.still_open
            or (item.still_open and (item.close_time is not None or item.closing_day is not None))
            or (not item.still_open and (item.close_time is None or item.closing_day is None))
        )
        if state_issue:
            flags.append(
                _flag(
                    "colibris_state_closure_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    still_open=item.still_open,
                    workflow_status=item.workflow_status,
                    close_time=item.close_time,
                    closing_day=item.closing_day,
                )
            )
        temporal_issues: list[str] = []
        if item.value_day > item.created.date():
            temporal_issues.append("consumption_after_event_creation")
        if item.explanation_time is not None and item.explanation_time < item.created:
            temporal_issues.append("explanation_before_event_creation")
        if item.validation_time is not None and item.validation_time < item.created:
            temporal_issues.append("validation_before_event_creation")
        if (
            item.lod2_time is not None
            and item.validation_time is not None
            and item.lod2_time < item.validation_time
        ):
            temporal_issues.append("lod2_before_validation")
        if item.close_time is not None and item.close_time < item.created:
            temporal_issues.append("closure_before_event_creation")
        if temporal_issues:
            flags.append(
                _flag(
                    "colibris_workflow_date_order_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    issues=temporal_issues,
                )
            )
        overdue: list[str] = []
        if item.still_open and as_of is not None:
            if item.action_deadline is not None and item.action_deadline < as_of:
                overdue.append("explanation_action_deadline")
            if item.technical_deadline is not None and item.technical_deadline < as_of:
                overdue.append("technical_deadline")
        if overdue:
            flags.append(
                _flag(
                    "open_excess_past_recorded_deadline",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    pc=item.pc,
                    indicator=item.indicator,
                    created=item.created.isoformat(),
                    analysis_as_of=as_of.isoformat() if as_of else None,
                    past_deadlines=overdue,
                    action_deadline=item.action_deadline,
                    technical_deadline=item.technical_deadline,
                    detail="confirm extract freshness and later closure before escalation",
                )
            )
        if item.still_open and (
            item.explanation_time is None
            or not item.explanation_cause
            or not item.action_plan
            or not item.solution
        ):
            flags.append(
                _flag(
                    "open_excess_missing_response_fields",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    missing=[
                        name
                        for name, value in (
                            ("explanation_time", item.explanation_time),
                            ("explanation_cause", item.explanation_cause),
                            ("action_plan", item.action_plan),
                            ("solution", item.solution),
                        )
                        if not value
                    ],
                )
            )
        if item.still_open and item.validation_satisfactory is True:
            flags.append(
                _flag(
                    "open_excess_marked_satisfactory",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                )
            )
        has_increase = _has_increase_id(item)
        if not has_increase and item.increase_status:
            flags.append(
                _flag(
                    "limit_increase_status_without_increase_id",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    increase_id=item.increase_id,
                    increase_status=item.increase_status,
                )
            )
        if has_increase and not item.increase_status:
            flags.append(
                _flag(
                    "limit_increase_id_without_status",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    increase_id=item.increase_id,
                )
            )
        if has_increase and "APPROV" in _norm(item.increase_status):
            missing_approvals = [
                name
                for name, value in (
                    ("increaseCreationDate", item.increase_created),
                    (
                        "increaseValidationTrdDirCreationDate",
                        item.increase_trader_approved,
                    ),
                    ("increaseValidationRisqCreationDate", item.increase_risk_approved),
                )
                if value is None
            ]
            if missing_approvals:
                flags.append(
                    _flag(
                        "approved_limit_increase_missing_timestamps",
                        item.path,
                        item.sheet,
                        item.row,
                        excess_id=item.excess_id,
                        increase_id=item.increase_id,
                        missing=missing_approvals,
                    )
                )
        if item.closed_manually is True:
            flags.append(
                _flag(
                    "manually_closed_excess",
                    item.path,
                    item.sheet,
                    item.row,
                    excess_id=item.excess_id,
                    detail="manual closure is a review candidate, not evidence of improper closure",
                )
            )
    return AnalysisResult(
        name="risk_excess_workflow",
        summary=(
            f"Profiled {len(excesses)} excess event(s) across {len(groups)} comparable "
            f"perimeter/metric/limit populations as of {as_of}; {len(flags)} recurrence, "
            f"state, timing, or governance candidate(s)."
        ),
        tables=tables,
        flag_candidates=flags[:MAX_FLAGS],
    )
