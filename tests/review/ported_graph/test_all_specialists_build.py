"""Every specialist domain builds and completes its bounded loop (fakes)."""

from __future__ import annotations

from datetime import date

import pytest
from langchain_core.runnables import RunnableLambda

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SPECIALIST_DOMAINS, SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import VerifierDecision
from data_agent.review.llm.models import ModelTier
from data_agent.review.orchestration.specialist_schemas import (
    AnalystOutput,
    VerifierOutput,
)
from data_agent.skills.registry import build_specialist, get_specialist
from data_agent.tools.review_context import ToolContext


def _fake_finding(finding_id: str) -> Finding:
    return Finding(
        finding_id=finding_id,
        title="Sample observation",
        category="observation",
        severity=Severity.INFO,
        confidence=0.9,
        claim="The source file contains daily records.",
        period=DateRange(start=date(2025, 1, 2), end=date(2025, 1, 6)),
        evidence=[EvidenceReference(locator="source://risk_metrics/risk.csv#rows=2:2")],
    )


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ModelTier]] = []

    def __call__(self, tier, schema=None):
        name = schema.__name__ if schema else "plain"
        self.calls.append((name, tier))
        if schema is AnalystOutput:
            return RunnableLambda(
                lambda _m: AnalystOutput(findings=[_fake_finding("F-1")])
            )
        if schema is VerifierOutput:
            return RunnableLambda(
                lambda _m: VerifierOutput(
                    finding_id="F-1", decision=VerifierDecision.PASS
                )
            )
        raise AssertionError(f"unexpected schema {schema}")


@pytest.mark.parametrize("domain", list(SPECIALIST_DOMAINS), ids=lambda d: d.value)
def test_specialist_graph_completes(tool_ctx: ToolContext, domain: SpecialistDomain) -> None:
    provider = _FakeProvider()
    registration = get_specialist(domain)
    graph = build_specialist(domain, llm_provider=provider)
    state = {
        "task_id": f"TASK-{domain.value}",
        "domain": domain.value,
        "report_id": registration.report_id,
        "domain_label": registration.label,
        "source_ids": [source.source_id for source in tool_ctx.manifest.sources],
        "source_paths": [source.path for source in tool_ctx.manifest.sources],
        "desk_context": DeskContext(
            desk_name="EM Rates",
            business_description="EM rates market making.",
            review_start=date(2025, 1, 1),
            review_end=date(2026, 6, 30),
        ).model_dump(mode="json"),
        "review_period": {"start": "2025-01-01", "end": "2026-06-30"},
    }
    result = graph.invoke(
        state, config={"configurable": {"tool_ctx": tool_ctx}}
    )

    assert result.get("loop_status") == "complete"
    assert result["report"]
    assert result["markdown"].startswith(f"# {registration.label} Review")
    assert "## Findings" in result["markdown"]
    # Model allocation holds for every specialist.
    assert ("AnalystOutput", ModelTier.LOW_COST) in provider.calls
    assert ("VerifierOutput", ModelTier.HIGH_COST) in provider.calls
