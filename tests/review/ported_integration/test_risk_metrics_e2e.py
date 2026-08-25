"""End-to-end risk_metrics review over a real sample tree (fake LLMs)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from langchain_core.runnables import RunnableLambda

from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.reports import SpecialistReport
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import ChallengeStatus, VerifierDecision
from data_agent.review.llm.models import ModelTier
from data_agent.review.orchestration.specialist.schemas import (
    AdjudicatorOutput,
    AnalystOutput,
    ChallengerChallenge,
    ChallengerOutput,
)
from data_agent.review.verification.rules import required_challenge_types
from data_agent.skills.registry import build_specialist
from data_agent.tools.review_context import ToolContext


@pytest.fixture(autouse=True)
def _complete_challenger(monkeypatch: pytest.MonkeyPatch) -> None:
    from data_agent.review.domain.verification import ChallengeType
    from data_agent.review.verification import challenger

    def run_challenger(_model, **kwargs):
        payload = json.loads(kwargs["user_prompt"])
        required = required_challenge_types(
            cross_source_required=len(set(payload["assigned_source_paths"])) > 1
        )
        return ChallengerOutput(
            finding_id=payload["finding"]["finding_id"],
            challenges=[
                ChallengerChallenge(
                    challenge_type=challenge_type,
                    status=ChallengeStatus.PASS,
                    explanation="Checked independently against assigned sources.",
                    evidence=(
                        [{"locator": payload["reopened_evidence"][0]["locator"]}]
                        if challenge_type is ChallengeType.EVIDENCE_SUPPORT
                        else []
                    ),
                )
                for challenge_type in required
            ],
        )

    monkeypatch.setattr(challenger, "run_bounded_structured_agent", run_challenger)


def _provider():
    finding = Finding(
        finding_id="RISK-001",
        title="VaR limit proximity",
        category="limit_proximity",
        severity=Severity.MEDIUM,
        confidence=0.7,
        claim="VaR sat close to the limit during early January 2025.",
        period=DateRange(start=date(2025, 1, 2), end=date(2025, 1, 6)),
        evidence=[EvidenceReference(locator="source://risk_metrics/risk.csv#rows=2:3")],
    )

    class Provider:
        def __call__(self, tier, schema=None):
            if schema is None:
                assert tier is ModelTier.LOW_COST
                return object()
            if schema is AnalystOutput:
                assert tier is ModelTier.LOW_COST
                return RunnableLambda(lambda _m: AnalystOutput(findings=[finding]))
            if schema is AdjudicatorOutput:
                assert tier is ModelTier.HIGH_COST
                return RunnableLambda(
                    lambda _m: AdjudicatorOutput(
                        finding_id="RISK-001",
                        decision=VerifierDecision.PASS,
                        checks=["locators reopened"],
                    )
                )
            raise AssertionError(f"unexpected schema {schema}")

    return Provider()


def test_end_to_end_review_writes_markdown(tool_ctx: ToolContext, tmp_path: Path) -> None:
    graph = build_specialist(SpecialistDomain.RISK_METRICS, llm_provider=_provider())
    state = {
        "task_id": "T-1",
        "domain": "risk_metrics",
        "report_id": "RISK",
        "domain_label": "Risk Metrics",
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
    result = graph.invoke(state, config={"configurable": {"tool_ctx": tool_ctx}})

    # The report rehydrates into the domain contract without error.
    report = SpecialistReport.model_validate(result["report"])
    assert report.domain.value == "risk_metrics"
    assert report.findings[0].verifier_status.value == "passed"
    assert report.sources_reviewed

    markdown_path = tmp_path / "risk_metrics.md"
    markdown_path.write_text(result["markdown"], encoding="utf-8")
    text = markdown_path.read_text(encoding="utf-8")
    assert text.startswith("# Risk Metrics Review")
    assert "## Sources Reviewed" in text
    assert "## Overall Conclusion" in text
    assert "source://risk_metrics/risk.csv#rows=2:3" in text


def test_two_runs_are_deterministic_up_to_timestamp(
    tool_ctx: ToolContext,
) -> None:
    graph = build_specialist(SpecialistDomain.RISK_METRICS, llm_provider=_provider())
    state = {
        "task_id": "T-1",
        "domain": "risk_metrics",
        "report_id": "RISK",
        "domain_label": "Risk Metrics",
        "source_ids": [],
        "source_paths": ["risk_metrics/risk.csv"],
        "desk_context": DeskContext(
            desk_name="EM Rates",
            business_description="EM rates market making.",
            review_start=date(2025, 1, 1),
            review_end=date(2026, 6, 30),
        ).model_dump(mode="json"),
        "review_period": {"start": "2025-01-01", "end": "2026-06-30"},
    }
    config = {"configurable": {"tool_ctx": tool_ctx}}
    first = graph.invoke(state, config=config)
    second = graph.invoke(state, config=config)

    def _without_timestamp(report: dict) -> dict:
        copy = dict(report)
        copy["generated_at"] = "<now>"
        return copy

    assert _without_timestamp(first["report"]) == _without_timestamp(second["report"])
