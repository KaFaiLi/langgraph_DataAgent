"""Adjustment controls and reconciliation checks."""

from itertools import pairwise

from .pnl import _overview_evidence
from .shared import *


def _adjustment_controls(adjustments: list[AdjustmentRow], pnl: list[PnlRow]) -> AnalysisResult:
    flags: list[dict[str, object]] = []
    mappings: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for pnl_item in pnl:
        mappings[pnl_item.ptf].add((pnl_item.gop, pnl_item.pc, pnl_item.currency))

    for item in adjustments:
        expected_eur = item.amount * item.exchange_rate
        tolerance = max(0.01, abs(expected_eur) * 0.00000001)
        if abs(item.amount_eur - expected_eur) > tolerance:
            flags.append(
                _flag(
                    "adjustment_eur_conversion_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    adjustment_id=item.adjustment_id,
                    actual_eur=round(item.amount_eur, 6),
                    expected_eur=round(expected_eur, 6),
                )
            )
        if item.value_start > item.value_end or item.creation_date < item.value_end:
            flags.append(
                _flag(
                    "adjustment_date_order_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    adjustment_id=item.adjustment_id,
                    value_start=item.value_start.isoformat(),
                    value_end=item.value_end.isoformat(),
                    creation_date=item.creation_date.isoformat(),
                )
            )
        expected_mappings = mappings.get(item.ptf, set())
        actual_mapping = (item.gop, item.pc, item.currency)
        if actual_mapping not in expected_mappings:
            flags.append(
                _flag(
                    "adjustment_pnl_mapping_mismatch",
                    item.path,
                    item.sheet,
                    item.row,
                    adjustment_id=item.adjustment_id,
                    ptf=item.ptf,
                    adjustment_mapping=list(actual_mapping),
                    pnl_mappings=[list(value) for value in sorted(expected_mappings)],
                )
            )

    pnl_by_date: dict[tuple[str, dt.date], list[PnlRow]] = defaultdict(list)
    for pnl_item in pnl:
        pnl_by_date[(pnl_item.ptf, pnl_item.day)].append(pnl_item)
    offset_count = 0
    for item in adjustments:
        amount_meur = item.amount_eur / 1_000_000
        if amount_meur == 0:
            continue
        pnl_candidates = pnl_by_date.get((item.ptf, item.value_end), [])
        opposite = [row for row in pnl_candidates if row.dtd * amount_meur < 0 and row.dtd != 0]
        if not opposite:
            continue
        pnl_item = max(opposite, key=lambda row: abs(row.dtd))
        ratio = abs(amount_meur / pnl_item.dtd)
        if not 0.75 <= ratio <= 1.25 or abs(pnl_item.dtd) < 1.0:
            continue
        offset_count += 1
        flags.append(
            _flag(
                "adjustment_offsets_unusual_daily_pnl",
                item.path,
                item.sheet,
                item.row,
                adjustment_id=item.adjustment_id,
                ptf=item.ptf,
                gop=item.gop,
                value_date=item.value_end.isoformat(),
                adjustment_amount_eur=round(item.amount_eur, 2),
                adjustment_amount_meur_candidate=round(amount_meur, 6),
                pnl_dtd=round(pnl_item.dtd, 6),
                offset_ratio=round(ratio, 4),
                pnl_locator=_locator(pnl_item.path, pnl_item.sheet, pnl_item.row),
                link_id=item.link_id,
                detail=(
                    "AMOUNTINEUR divided by one million nearly offsets opposite-signed "
                    "DTD; confirm the DTD unit and pre/post-adjustment basis"
                ),
            )
        )
    reversal_groups: dict[tuple[str, ...], list[AdjustmentRow]] = defaultdict(list)
    for item in adjustments:
        key = (
            ("link", item.link_id, item.currency)
            if item.link_id
            else ("mapping", item.ptf, item.component, item.currency)
        )
        reversal_groups[key].append(item)
    reversal_count = 0
    for rows in reversal_groups.values():
        ordered = sorted(rows, key=lambda item: (item.value_end, item.creation_date, item.row))
        reversal_candidates: list[tuple[AdjustmentRow, AdjustmentRow, float]] = []
        for first, second in pairwise(ordered):
            if first.amount_eur * second.amount_eur >= 0 or first.amount_eur == 0:
                continue
            gap_days = (second.value_end - first.value_end).days
            ratio = abs(second.amount_eur / first.amount_eur)
            if (
                0 <= gap_days <= ADJUSTMENT_REVERSAL_DAYS
                and ADJUSTMENT_REVERSAL_RATIO_MIN <= ratio <= ADJUSTMENT_REVERSAL_RATIO_MAX
            ):
                reversal_candidates.append((first, second, ratio))
        if not reversal_candidates:
            continue
        first, second, ratio = min(
            reversal_candidates,
            key=lambda candidate: (candidate[1].value_end - candidate[0].value_end).days,
        )
        reversal_count += len(reversal_candidates)
        flags.append(
            _flag(
                "adjustment_reversal_candidate",
                first.path,
                first.sheet,
                first.row,
                adjustment_id=first.adjustment_id,
                next_adjustment_id=second.adjustment_id,
                next_locator=_locator(second.path, second.sheet, second.row),
                ptf=first.ptf,
                component=first.component,
                link_id=first.link_id,
                value_end=first.value_end.isoformat(),
                next_value_end=second.value_end.isoformat(),
                amount_eur=round(first.amount_eur, 6),
                next_amount_eur=round(second.amount_eur, 6),
                magnitude_ratio=round(ratio, 4),
                group_candidates=len(reversal_candidates),
            )
        )

    amounts = [item.amount_eur for item in adjustments]
    if len(amounts) >= 5:
        for item, z in zip(adjustments, zscore(amounts), strict=True):
            if abs(z) >= ADJUSTMENT_OUTLIER_Z and len(flags) < MAX_FLAGS:
                flags.append(
                    _flag(
                        "large_adjustment_eur",
                        item.path,
                        item.sheet,
                        item.row,
                        adjustment_id=item.adjustment_id,
                        value_end=item.value_end.isoformat(),
                        ptf=item.ptf,
                        amount_eur=round(item.amount_eur, 6),
                        z=round(z, 4),
                    )
                )

    by_month: dict[tuple[int, int], list[AdjustmentRow]] = defaultdict(list)
    for item in adjustments:
        by_month[(item.value_end.year, item.value_end.month)].append(item)
    period_tables: list[dict[str, object]] = []
    for month, rows in sorted(by_month.items()):
        total = sum(abs(item.amount_eur) for item in rows)
        at_end = [item for item in rows if item.value_end.day >= 28]
        end_total = sum(abs(item.amount_eur) for item in at_end)
        share = end_total / total if total else 0.0
        period_tables.append(
            {
                "month": f"{month[0]:04d}-{month[1]:02d}",
                "adjustments": len(rows),
                "period_end_adjustments": len(at_end),
                "absolute_amount_eur": round(total, 2),
                "period_end_share": round(share, 4),
            }
        )
        if len(rows) >= 3 and len(at_end) >= 2 and share >= 0.5 and len(flags) < MAX_FLAGS:
            example = at_end[0]
            flags.append(
                _flag(
                    "adjustment_period_end_concentration",
                    example.path,
                    example.sheet,
                    example.row,
                    month=f"{month[0]:04d}-{month[1]:02d}",
                    period_end_adjustments=len(at_end),
                    period_end_share=round(share, 4),
                    locators=[_locator(item.path, item.sheet, item.row) for item in at_end],
                )
            )

    table = {
        "adjustment_rows": len(adjustments),
        "currencies": dict(Counter(item.currency for item in adjustments)),
        "sources": dict(Counter(item.source for item in adjustments)),
        "natures": dict(Counter(item.nature for item in adjustments)),
        "date_start": min((item.value_start for item in adjustments), default=None),
        "date_end": max((item.value_end for item in adjustments), default=None),
        "absolute_amount_eur": round(sum(abs(value) for value in amounts), 2),
        "blank_comments": sum(not item.comment for item in adjustments),
        "rapid_reversal_candidates": reversal_count,
        "daily_pnl_offset_candidates": offset_count,
    }
    adjustment_overview = (
        DataOverview(
            overview_id="pnl.adjustment-profile",
            domain=SpecialistDomain.PNL,
            source_family="pnl_adjustments",
            title="PnL adjustment profile",
            summary=(
                "Absolute adjustment amounts are profiled by value-end month, with "
                "population and documentation measures shown independently of findings."
            ),
            status=OverviewStatus.AVAILABLE,
            metrics=[
                OverviewMetric(
                    label="Adjustments",
                    value=str(len(adjustments)),
                    unit="count",
                    basis="parsed adjustment rows",
                ),
                OverviewMetric(
                    label="Absolute amount",
                    value=f"{sum(abs(value) for value in amounts):.2f}",
                    unit="EUR",
                    basis="sum of supplied AMOUNTINEUR magnitudes",
                ),
                OverviewMetric(
                    label="Blank comments",
                    value=str(sum(not item.comment for item in adjustments)),
                    unit="count",
                    basis="empty supplied comments",
                ),
                OverviewMetric(
                    label="Rapid reversal candidates",
                    value=str(reversal_count),
                    unit="count",
                    basis="bounded deterministic reversal screen",
                ),
            ],
            visual=BarVisual(
                x_label="Value-end month",
                y_label="Absolute adjustment amount",
                unit="EUR",
                series=[
                    OverviewSeries(
                        name="Absolute adjustment amount",
                        points=[
                            OverviewPoint(
                                label=str(period["month"]),
                                value=float(str(period["absolute_amount_eur"])),
                            )
                            for period in period_tables
                        ],
                    )
                ],
            ),
            evidence=_overview_evidence(adjustments),
            limitations=[
                (
                    "The view uses supplied EUR-converted amounts; conversion mismatches "
                    "remain separate candidates."
                ),
                "Absolute amounts do not preserve adjustment direction.",
            ],
        )
        if adjustments
        else DataOverview(
            overview_id="pnl.adjustment-profile",
            domain=SpecialistDomain.PNL,
            source_family="pnl_adjustments",
            title="PnL adjustment profile",
            summary="No compatible adjustment population was available for profiling.",
            status=OverviewStatus.UNAVAILABLE,
            limitations=[
                "Overview unavailable because no rows matched the finalized adjustment schema."
            ],
        )
    )
    offset_adjustment_ids = {
        str(flag.get("adjustment_id"))
        for flag in flags
        if flag.get("kind") == "adjustment_offsets_unusual_daily_pnl"
    }
    reversing_adjustment_ids = {
        str(flag.get("adjustment_id"))
        for flag in flags
        if flag.get("kind") == "adjustment_reversal_candidate"
    }
    linked_offset_reversals = offset_adjustment_ids & reversing_adjustment_ids
    for flag in flags:
        if (
            flag.get("kind")
            in {"adjustment_offsets_unusual_daily_pnl", "adjustment_reversal_candidate"}
            and str(flag.get("adjustment_id")) in linked_offset_reversals
        ):
            flag["severity_floor"] = "high"
            flag["severity_basis"] = (
                "a material same-day PnL offset followed by a near-mirror reversal is "
                "a high-priority close-integrity pattern; intent remains unproven"
            )
            flag["severity_match_terms"] = ["offset", "reversal"]
            flag["measured_observation"] = True
    return AnalysisResult(
        name="pnl_adjustment_controls",
        summary=(
            f"Reperformed conversion, date ordering, hierarchy mapping, magnitude, and "
            f"period-end and reversal screens for {len(adjustments)} adjustment row(s); "
            f"{len(flags)} candidate(s)."
        ),
        tables=[table, *period_tables],
        flag_candidates=flags[:MAX_FLAGS],
        overviews=[adjustment_overview],
    )
