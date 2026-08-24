"""Finding severity levels with a total order for weighting and escalation."""

from enum import StrEnum


class Severity(StrEnum):
    """Severity of a finding, from least to most severe."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def at_least(severity: Severity, threshold: Severity) -> bool:
    """True when ``severity`` is at least as severe as ``threshold``."""
    return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[threshold]
