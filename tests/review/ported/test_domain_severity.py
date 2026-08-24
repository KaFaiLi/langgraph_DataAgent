"""Severity ordering tests."""

from __future__ import annotations

from data_agent.review.domain.severity import Severity, at_least


def test_severity_order_is_total() -> None:
    order = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
    for index, severity in enumerate(order):
        for lower in order[: index + 1]:
            assert at_least(severity, lower)
        for higher in order[index + 1 :]:
            assert not at_least(severity, higher)


