"""Skill-owned severity constraints shared by review runtimes."""

from __future__ import annotations

from collections.abc import Sequence

from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import SEVERITY_ORDER, Severity
from data_agent.review.verification.candidates import candidate_locators


def _severity_ceiling(finding: Finding, analyses: Sequence[dict]) -> Severity | None:
    """Read an optional skill-owned ceiling from locator-matched candidates."""

    locators = {reference.locator for reference in [*finding.evidence, *finding.counter_evidence]}
    ceilings: list[Severity] = []
    for analysis in analyses:
        flags = analysis.get("flag_candidates", [])
        if not isinstance(flags, list):
            continue
        for flag in flags:
            if not isinstance(flag, dict):
                continue
            raw_locators = candidate_locators(flag)
            if not raw_locators.intersection(locators):
                continue
            value = flag.get("severity_ceiling", flag.get("max_severity"))
            try:
                if value is not None:
                    ceilings.append(Severity(str(value).lower()))
            except ValueError:
                continue
    return min(ceilings, key=lambda severity: SEVERITY_ORDER[severity]) if ceilings else None
