"""DeskContext contract tests."""

from __future__ import annotations

from datetime import date

import pytest

from data_agent.review.domain.desk_context import (
    ControlDefinition,
    DeskContext,
    DeskFact,
    FactProvenance,
    RiskLimit,
)
from data_agent.review.domain.evidence import EvidenceReference


def make_context() -> DeskContext:
    return DeskContext(
        desk_name="EM Rates",
        business_description="Emerging-market rates market making.",
        products=["BRL swaps", "MXN bonds"],
        currencies=["BRL", "MXN"],
        risk_metrics=["VaR", "SVaR", "Stress"],
        review_start=date(2025, 1, 1),
        review_end=date(2026, 6, 30),
        limits=[
            RiskLimit(
                limit_id="LIM-01",
                name="Daily VaR",
                metric="VaR",
                value=5.0,
                unit="mUSD",
                effective_from=date(2025, 1, 1),
            )
        ],
        controls=[
            ControlDefinition(
                control_id="CTL-01",
                name="Post-trade mapping check",
                description="T+0 mapping validation",
                effective_from=date(2025, 1, 1),
                effective_to=date(2025, 12, 31),
            )
        ],
    )


def test_source_backed_fact_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        DeskFact(
            fact_id="F-1",
            statement="The desk runs a VaR limit.",
            provenance=FactProvenance.SOURCE_BACKED,
        )


def test_inferred_fact_may_omit_evidence() -> None:
    fact = DeskFact(
        fact_id="F-2",
        statement="Likely driven by elections",
        provenance=FactProvenance.INFERRED,
    )
    assert fact.provenance is FactProvenance.INFERRED


def test_context_can_record_withheld_source_fact() -> None:
    context = make_context()
    context.unresolved_items.append("F-3: evidence changed; fact withheld")
    assert context.unresolved_items == ["F-3: evidence changed; fact withheld"]


def test_add_fact_routes_by_provenance() -> None:
    context = make_context()
    backed = DeskFact(
        fact_id="F-1",
        statement="VaR limit is 5 mUSD.",
        provenance=FactProvenance.SOURCE_BACKED,
        evidence=[EvidenceReference(locator="source://limits.md#lines=2:4")],
    )
    inferred = DeskFact(
        fact_id="F-2",
        statement="Maybe election driven.",
        provenance=FactProvenance.INFERRED,
    )
    context.add_fact(backed)
    context.add_fact(inferred)
    assert context.source_backed_facts == [backed]
    assert context.inferred_facts == [inferred]


def test_effective_limits_respect_dates() -> None:
    context = make_context()
    assert context.effective_limits(date(2025, 6, 1))[0].limit_id == "LIM-01"
    assert context.effective_limits(date(2024, 12, 31)) == []


def test_effective_controls_respect_dates() -> None:
    context = make_context()
    assert context.effective_controls(date(2025, 6, 1))[0].control_id == "CTL-01"
    assert context.effective_controls(date(2026, 1, 1)) == []


def test_rejects_reversed_review_window() -> None:
    with pytest.raises(ValueError):
        DeskContext(
            desk_name="X",
            business_description="Y",
            review_start=date(2026, 1, 1),
            review_end=date(2025, 1, 1),
        )


