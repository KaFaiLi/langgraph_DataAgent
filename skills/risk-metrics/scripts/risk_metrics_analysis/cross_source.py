"""Cross-source SGMR and Colibris consistency checks."""

from .limits import _close
from .shared import *
from .sources import _norm


def _definition_key_sgmr(item: SgmrRow) -> tuple[str, str, str, str]:
    return (
        _norm(item.pc),
        _norm(item.indicator),
        _norm(item.metric_name),
        _norm(item.unit),
    )


def _definition_key_excess(item: ExcessRow) -> tuple[str, str, str, str]:
    return (
        _norm(item.pc),
        _norm(item.indicator),
        _norm(item.metric_name),
        _norm(item.unit),
    )


def _cross_source_consistency(sgmr: list[SgmrRow], excesses: list[ExcessRow]) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    definitions: dict[tuple[str, str, str, str], list[SgmrRow]] = defaultdict(list)
    dated_definitions: dict[tuple[str, str, str, str, dt.date], list[SgmrRow]] = defaultdict(list)
    for item in sgmr:
        definitions[_definition_key_sgmr(item)].append(item)
        dated_definitions[(*_definition_key_sgmr(item), item.day)].append(item)
    distinct_excess_definitions: dict[tuple[str, str, str, str, float, str], ExcessRow] = {}
    for excess in excesses:
        distinct_excess_definitions.setdefault(
            (
                *_definition_key_excess(excess),
                round(excess.limit_value, 8),
                _norm(excess.limit_type),
            ),
            excess,
        )
    matched_definitions = 0
    for excess in distinct_excess_definitions.values():
        candidates = definitions.get(_definition_key_excess(excess), [])
        limit_matches = [row for row in candidates if _close(row.upper_limit, excess.limit_value)]
        if not candidates:
            flags.append(
                _flag(
                    "colibris_definition_without_sgmr_limit",
                    excess.path,
                    excess.sheet,
                    excess.row,
                    excess_id=excess.excess_id,
                    pc=excess.pc,
                    indicator=excess.indicator,
                    metric_name=excess.metric_name,
                    unit=excess.unit,
                )
            )
            continue
        if not limit_matches:
            flags.append(
                _flag(
                    "limit_bound_difference_across_sources",
                    excess.path,
                    excess.sheet,
                    excess.row,
                    excess_id=excess.excess_id,
                    pc=excess.pc,
                    indicator=excess.indicator,
                    colibris_limit=excess.limit_value,
                    sgmr_upper_limits=sorted({row.upper_limit for row in candidates}),
                    sgmr_locator=_locator(
                        candidates[0].path, candidates[0].sheet, candidates[0].row
                    ),
                )
            )
            continue
        matched_definitions += 1
        sgmr_types = {_norm(row.limit_type) for row in limit_matches}
        if _norm(excess.limit_type) not in sgmr_types:
            example = limit_matches[0]
            flags.append(
                _flag(
                    "limit_type_difference_across_sources",
                    excess.path,
                    excess.sheet,
                    excess.row,
                    excess_id=excess.excess_id,
                    pc=excess.pc,
                    indicator=excess.indicator,
                    colibris_limit_type=excess.limit_type,
                    sgmr_limit_types=sorted(sgmr_types),
                    sgmr_locator=_locator(example.path, example.sheet, example.row),
                    detail="confirm whether Colibris type describes event trigger or limit type",
                )
            )
        owners = {_norm(row.consumption_owner) for row in limit_matches}
        delegations = {_norm(row.delegation) for row in limit_matches}
        if (
            _norm(excess.consumption_owner) not in owners
            or _norm(excess.delegation) not in delegations
        ):
            example = limit_matches[0]
            flags.append(
                _flag(
                    "limit_owner_difference_across_sources",
                    excess.path,
                    excess.sheet,
                    excess.row,
                    excess_id=excess.excess_id,
                    colibris_consumption_owner=excess.consumption_owner,
                    sgmr_consumption_owners=sorted(owners),
                    colibris_delegation=excess.delegation,
                    sgmr_delegations=sorted(delegations),
                    sgmr_locator=_locator(example.path, example.sheet, example.row),
                )
            )

    changed_regimes: dict[tuple[str, str, str, str, str], SgmrRow] = {}
    for row in sgmr:
        if row.initial_lower is None or row.initial_upper is None:
            continue
        if _close(row.lower_limit, row.initial_lower) and _close(
            row.upper_limit, row.initial_upper
        ):
            continue
        key = (*_definition_key_sgmr(row), row.limit_id)
        current = changed_regimes.get(key)
        if current is None or (row.limit_start, row.day, row.row) < (
            current.limit_start,
            current.day,
            current.row,
        ):
            changed_regimes[key] = row
    for changed in sorted(
        changed_regimes.values(), key=lambda row: (row.limit_start, row.limit_id)
    ):
        workflows = [
            excess
            for excess in excesses
            if _definition_key_excess(excess) == _definition_key_sgmr(changed)
            and excess.increase_id not in {"", "0"}
            and any(
                value is not None
                for value in (
                    excess.increase_created,
                    excess.increase_trader_approved,
                    excess.increase_risk_approved,
                )
            )
        ]
        if not workflows:
            continue
        workflow = min(
            workflows,
            key=lambda item: abs((item.created.date() - changed.limit_start).days),
        )
        milestones = [
            value
            for value in (
                workflow.increase_created,
                workflow.increase_trader_approved,
                workflow.increase_risk_approved,
            )
            if value is not None
        ]
        if not any(value.date() > changed.limit_start for value in milestones):
            continue
        prior_breaches = [
            row
            for row in sgmr
            if row.limit_id == changed.limit_id
            and row.day < changed.limit_start
            and (changed.limit_start - row.day).days <= 30
            and (
                (row.value >= 0 and row.upper_limit > 0 and row.value > row.upper_limit)
                or (row.value < 0 and row.lower_limit < 0 and row.value < row.lower_limit)
            )
        ]
        flags.append(
            _flag(
                "limit_effective_before_workflow_approval",
                changed.path,
                changed.sheet,
                changed.row,
                limit_id=changed.limit_id,
                portfolio=changed.portfolio,
                pc=changed.pc,
                indicator=changed.indicator,
                effective_date=changed.limit_start.isoformat(),
                initial_bounds=[changed.initial_lower, changed.initial_upper],
                changed_bounds=[changed.lower_limit, changed.upper_limit],
                workflow_excess_id=workflow.excess_id,
                workflow_locator=_locator(workflow.path, workflow.sheet, workflow.row),
                request_date=(
                    workflow.increase_created.date().isoformat()
                    if workflow.increase_created
                    else None
                ),
                trader_approval_date=(
                    workflow.increase_trader_approved.date().isoformat()
                    if workflow.increase_trader_approved
                    else None
                ),
                risk_approval_date=(
                    workflow.increase_risk_approved.date().isoformat()
                    if workflow.increase_risk_approved
                    else None
                ),
                prior_breach_observations=len(prior_breaches),
                prior_breach_locators=[
                    _locator(row.path, row.sheet, row.row) for row in prior_breaches[:5]
                ],
                detail=(
                    "changed limit effective date precedes one or more recorded workflow "
                    "milestones; source lineage and approval applicability require review"
                ),
            )
        )

    for excess in excesses:
        cause = _norm(excess.explanation_cause)
        mapping_terms = ("MAPPING", "FEED", "EXCLUDED", "OMITTED")
        exception_terms = ("EXCEPTION", "PENDING", "REMEDIATION", "EXCLUDED")
        if not any(term in cause for term in mapping_terms) or not any(
            term in cause for term in exception_terms
        ):
            continue
        flags.append(
            _flag(
                "mapping_or_feed_control_exception",
                excess.path,
                excess.sheet,
                excess.row,
                excess_id=excess.excess_id,
                pc=excess.pc,
                indicator=excess.indicator,
                underlying=excess.underlying,
                created=excess.created.date().isoformat(),
                still_open=excess.still_open,
                workflow_status=excess.workflow_status,
                validation_satisfactory=excess.validation_satisfactory,
                explanation_cause=excess.explanation_cause,
                severity_floor=(
                    "high"
                    if excess.still_open
                    and excess.indicator == "VAR"
                    and any(term in cause for term in ("EXCLUDED", "OMITTED"))
                    else "medium"
                ),
                severity_basis=(
                    "an explicit open mapping/feed exception that excludes or omits a "
                    "VaR component is a material risk-representation control weakness"
                ),
                severity_match_terms=["mapping", "var"],
                measured_observation=True,
            )
        )

    mapping_gaps: dict[tuple[str, str, str, str, str, int], list[SgmrRow]] = defaultdict(list)
    for row in sgmr:
        mapping_gaps[
            (
                row.limit_id,
                row.portfolio,
                row.pc,
                row.indicator,
                row.metric_name,
                row.version,
            )
        ].append(row)
    for rows in mapping_gaps.values():
        ordered = sorted(rows, key=lambda row: (row.day, row.row))
        missing = [row for row in ordered if not row.underlying]
        mapped = [row for row in ordered if row.underlying]
        if len(missing) < 5 or not mapped:
            continue
        first = missing[0]
        last = missing[-1]
        flags.append(
            _flag(
                "persistent_metric_mapping_gap",
                first.path,
                first.sheet,
                first.row,
                portfolio=first.portfolio,
                pc=first.pc,
                indicator=first.indicator,
                risk_currency=first.risk_currency,
                missing_observations=len(missing),
                first_date=first.day.isoformat(),
                last_date=last.day.isoformat(),
                last_locator=_locator(last.path, last.sheet, last.row),
                mapped_example_locator=_locator(mapped[0].path, mapped[0].sheet, mapped[0].row),
                missing_mean_abs_value=round(
                    statistics.fmean(abs(row.value) for row in missing), 6
                ),
                mapped_mean_abs_value=round(statistics.fmean(abs(row.value) for row in mapped), 6),
                detail="repeated blank factor mapping within an otherwise mapped series",
            )
        )

    sgmr_min = min((item.day for item in sgmr), default=None)
    sgmr_max = max((item.day for item in sgmr), default=None)
    semantic_matches = 0
    unique_semantic_matches = 0
    ambiguous_semantic_matches = 0
    non_business_dates = 0
    outside_period = 0
    missing_business_dates = 0
    for excess in excesses:
        candidates = [
            row
            for row in dated_definitions.get(
                (*_definition_key_excess(excess), excess.value_day), []
            )
            if _close(row.upper_limit, excess.limit_value)
        ]
        if candidates:
            semantic_matches += 1
            if len(candidates) == 1:
                unique_semantic_matches += 1
            else:
                ambiguous_semantic_matches += 1
            continue
        if sgmr_min is None or sgmr_max is None or not sgmr_min <= excess.value_day <= sgmr_max:
            outside_period += 1
        elif excess.value_day.weekday() >= 5:
            non_business_dates += 1
        else:
            missing_business_dates += 1
            flags.append(
                _flag(
                    "colibris_event_without_in_period_sgmr_date",
                    excess.path,
                    excess.sheet,
                    excess.row,
                    excess_id=excess.excess_id,
                    pc=excess.pc,
                    indicator=excess.indicator,
                    value_date=excess.value_day.isoformat(),
                )
            )

    sgmr_ids: dict[str, list[SgmrRow]] = defaultdict(list)
    for item in sgmr:
        for identifier in (item.limit_id, item.consumption_id, item.record_id):
            if identifier:
                sgmr_ids[identifier].append(item)
    direct_matches = sum(
        1 for excess in excesses if excess.sgmr_id and len(sgmr_ids[excess.sgmr_id]) == 1
    )
    reconciliation = "SUPPORTED" if excesses and direct_matches == len(excesses) else "UNRESOLVED"
    table = {
        "colibris_definition_variants": len(distinct_excess_definitions),
        "matched_definition_variants": matched_definitions,
        "colibris_events": len(excesses),
        "semantic_date_matches": semantic_matches,
        "unique_semantic_date_matches": unique_semantic_matches,
        "ambiguous_semantic_date_matches": ambiguous_semantic_matches,
        "non_business_date_without_match": non_business_dates,
        "outside_sgmr_period_without_match": outside_period,
        "in_period_business_date_without_match": missing_business_dates,
        "unique_direct_id_matches": direct_matches,
        "event_to_sgmr_row_reconciliation": reconciliation,
        "reason": (
            "A unique source-backed sgmrId bridge is required; PC/metric/date semantic "
            "matches can map one Colibris event to several SGMR portfolios."
            if reconciliation == "UNRESOLVED"
            else "Every supplied event has a unique direct identifier match."
        ),
    }
    return AnalysisResult(
        name="risk_cross_source_consistency",
        summary=(
            f"Matched {matched_definitions}/{len(distinct_excess_definitions)} Colibris "
            f"limit-definition variant(s) to SGMR and found {semantic_matches}/"
            f"{len(excesses)} semantic date match(es); event-to-row reconciliation is "
            f"{reconciliation}."
        ),
        tables=[table],
        flag_candidates=flags[:MAX_FLAGS],
    )
