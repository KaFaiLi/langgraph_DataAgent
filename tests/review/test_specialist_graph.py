from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.severity import Severity
from data_agent.review.domain.source import DateRange
from data_agent.review.domain.verification import ChallengeStatus, ChallengeType, VerifierDecision
from data_agent.review.ingestion.catalog import build_catalog
from data_agent.review.orchestration.specialist import (
    SpecialistRuntime,
    SpecialistSpec,
    build_specialist_graph,
)
from data_agent.review.orchestration.specialist.schemas import (
    AdjudicatorOutput,
    AnalystOutput,
    ChallengerChallenge,
    ChallengerOutput,
)
from data_agent.review.verification.rules import REQUIRED_CHALLENGE_TYPES
from data_agent.tools.review_context import ToolContext


class ResearchModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "scripted-research"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        completed = sum(isinstance(message, ToolMessage) for message in messages)
        if completed == 0:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "inspect_table",
                        "args": {"path": "assigned.csv", "preview_rows": 2},
                        "id": "inspect-1",
                        "type": "tool_call",
                    }
                ],
            )
        elif completed == 1:
            assert "row_count" in str(messages[-1].content)
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_rows",
                        "args": {"path": "assigned.csv", "start": 1, "end": 2},
                        "id": "rows-1",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            assert "desk" in str(messages[-1].content)
            message = AIMessage(
                content="Reviewed both tool results; source://assigned.csv#rows=2:2 supports the observation."
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


class Provider:
    def __call__(self, tier, schema=None):
        if schema is None:
            return ResearchModel()
        if schema is AnalystOutput:
            return RunnableLambda(
                lambda _messages: AnalystOutput(
                    findings=[
                        Finding(
                            finding_id="F-1",
                            title="Assigned source reviewed",
                            category="observation",
                            severity=Severity.INFO,
                            confidence=0.9,
                            claim="The assigned source contains desk records.",
                            period=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 2)),
                            evidence=[EvidenceReference(locator="source://assigned.csv#rows=2:2")],
                            is_observation=True,
                        )
                    ]
                )
            )
        if schema is AdjudicatorOutput:
            return RunnableLambda(
                lambda _messages: AdjudicatorOutput(
                    finding_id="F-1", decision=VerifierDecision.PASS
                )
            )
        raise AssertionError(schema)


def test_specialist_researches_with_multiple_tools_before_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from data_agent.review.verification import challenger

    def complete_challenge(_model, **kwargs):
        payload = json.loads(kwargs["user_prompt"])
        return ChallengerOutput(
            finding_id=payload["finding"]["finding_id"],
            challenges=[
                ChallengerChallenge(
                    challenge_type=challenge_type,
                    status=ChallengeStatus.PASS,
                    explanation="Checked independently.",
                    evidence=(
                        [{"locator": payload["reopened_evidence"][0]["locator"]}]
                        if challenge_type is ChallengeType.EVIDENCE_SUPPORT
                        else []
                    ),
                )
                for challenge_type in REQUIRED_CHALLENGE_TYPES
            ],
        )

    monkeypatch.setattr(challenger, "run_bounded_structured_agent", complete_challenge)
    source = tmp_path / "source"
    source.mkdir()
    (source / "assigned.csv").write_text(
        "date,desk,value\n2025-01-01,A,1\n2025-01-02,B,2\n", encoding="utf-8"
    )
    manifest = build_catalog(source)
    ctx = ToolContext(
        source_root=source,
        workspace_root=tmp_path / "workspace",
        manifest=manifest,
    )
    spec = SpecialistSpec(
        domain=SpecialistDomain.RISK_METRICS,
        report_id="RISK",
        domain_label="Risk Metrics",
        policy_text="Verify all evidence.",
        analyses_runner=lambda _ctx, _paths: [],
        research_guidance="Inspect the assigned table before drafting.",
    )
    runtime = SpecialistRuntime(
        spec=spec,
        llm_provider=Provider(),
    )
    graph = build_specialist_graph(runtime)

    result = graph.invoke(
        {
            "task_id": "TASK-risk_metrics",
            "domain": "risk_metrics",
            "report_id": "RISK",
            "domain_label": "Risk Metrics",
            "source_ids": [manifest.sources[0].source_id],
            "source_paths": ["assigned.csv"],
            "desk_context": {},
            "review_period": {"start": "2025-01-01", "end": "2025-01-02"},
        },
        config={"configurable": {"tool_ctx": ctx}},
    )

    assert [entry["tool"] for entry in result["research_trace"]] == [
        "inspect_table",
        "read_rows",
    ]
    assert "Reviewed both tool results" in result["research_summary"]
    assert result["verified_findings"][0]["finding_id"] == "RISK-F-1"
