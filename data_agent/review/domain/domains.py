"""Source classifications and active specialist review domains."""

from enum import StrEnum


class SpecialistDomain(StrEnum):
    """A review-domain identifier retained for source-manifest compatibility."""

    RISK_METRICS = "risk_metrics"
    PNL = "pnl"
    INCOME_ATTRIBUTION = "income_attribution"
    POST_TRADE_CONTROLS = "post_trade_controls"
    RISK_COMMENTARY = "risk_commentary"
    PNL_VALIDATION = "pnl_validation"
    PNL_ADJUSTMENTS = "pnl_adjustments"


# Validation, adjustment, and income attribution remain valid source classifications,
# but the composite PnL skill owns their review. Keeping the enum members preserves
# existing manifests while ensuring orchestration creates one PnL sub-agent rather than
# overlapping source-specific agents.
SPECIALIST_DOMAINS: tuple[SpecialistDomain, ...] = (
    SpecialistDomain.RISK_METRICS,
    SpecialistDomain.PNL,
    SpecialistDomain.POST_TRADE_CONTROLS,
    SpecialistDomain.RISK_COMMENTARY,
)

SOURCE_DOMAINS: tuple[SpecialistDomain, ...] = tuple(SpecialistDomain)


