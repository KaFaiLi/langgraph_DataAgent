"""Shared schema-aware source-role recognition for planning and trusted runners."""

from __future__ import annotations

from collections.abc import Iterable

from data_agent.review.domain.domains import SpecialistDomain


def pnl_source_role(
    columns: Iterable[str], *, allow_legacy_pnl: bool = False
) -> SpecialistDomain | None:
    """Return a P&L-family role only when its identifying schema is present."""
    normalized = {str(column).strip().lower().replace("_", "") for column in columns}
    signatures = (
        (
            SpecialistDomain.PNL_ADJUSTMENTS,
            {"adjustmentid", "amount", "amountineur", "exchangerate"},
        ),
        (SpecialistDomain.PNL_VALIDATION, {"gop", "state", "creationtime", "pnltype"}),
        (SpecialistDomain.INCOME_ATTRIBUTION, {"asofdate", "gop", "final result acc dtd"}),
        (SpecialistDomain.INCOME_ATTRIBUTION, {"date", "driver", "pnlmusd"}),
        (SpecialistDomain.PNL, {"value date", "ptf", "dtd", "ytd"}),
    )
    for role, required in signatures:
        if required <= normalized:
            return role
    if allow_legacy_pnl and {"date", "pnlmusd", "comment"} <= normalized:
        return SpecialistDomain.PNL
    return None
