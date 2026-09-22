"""Typed peer role contracts, context independence and model allocation."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from data_agent.agent.subagents.contracts import (
    DelegationPolicy,
    DelegationRequest,
    RunScope,
    SubagentSpec,
)
from data_agent.agent.subagents.registry import SubagentRegistry
from data_agent.agent.subagents.review import FindingInput, ReviewRoleAdapter, review_profiles
from data_agent.agent.subagents.runner import DelegationRunner
from data_agent.review.domain.evidence import EvidenceReference
from data_agent.review.domain.finding import Finding
from data_agent.review.domain.outputs import AdjudicatorOutput, ChallengerOutput
from data_agent.tools.review_skills import CandidateSubmission
from tests.review.test_review_runs import _assign
from tests.review.test_review_runs import workspace as _workspace_fixture


@pytest.fixture()
def workspace(tmp_path):
    return _workspace_fixture.__wrapped__(tmp_path)


@pytest.fixture()
def role_context(workspace):
    access, assignment, _ = _assign(workspace, "a.csv")
    access.execute(assignment)
    access.submit(
        assignment,
        CandidateSubmission(
            findings=[
                Finding(
                    finding_id="F1",
                    title="Limit observation",
                    category="limit",
                    severity="high",
                    confidence=0.9,
                    claim="Observed consumption 12 versus bound 10.",
                    recommendation="Inspect governance",
                    evidence=[EvidenceReference(locator="source://a.csv#rows=2:2")],
                )
            ]
        ),
    )
    adapter = ReviewRoleAdapter(workspace, "RUN-A")
    specs = {spec.name: spec for spec in review_profiles(workspace.definitions)}
    request = DelegationRequest(
        agent_name="review-challenger",
        task="PARENT_ANCHOR critical PASS confidence 0.99",
        context=json.dumps({"assignment_id": assignment, "finding_id": "RISK-F1"}),
    )
    return access, assignment, adapter, specs, request


def test_challenger_context_is_independent_and_assignment_bound(role_context):
    access, assignment, adapter, specs, request = role_context
    preparation = adapter.prepare(specs["review-challenger"], request, "child-challenge")
    payload = json.loads(preparation.prompt.split("\n", 1)[1])
    assert "PARENT_ANCHOR" not in preparation.prompt
    assert not {"severity", "confidence", "recommendation", "verifier_status"}.intersection(
        payload["finding"]
    )
    assert {t.name for t in preparation.tools} == {"review_inventory", "review_source_tool"}
    assert preparation.skill_names == ("risk-metrics",)
    receipt = preparation.accept(ChallengerOutput(finding_id="RISK-F1", research_complete=False))
    assert not receipt["verified"]
    record = access.store.read().role_results[receipt["result_ref"]]
    assert record["child_id"] == "child-challenge" and record["model_role"] == "low_cost"
    adjudication = adapter.prepare(specs["review-adjudicator"], request, "child-adjudicate")
    assert adjudication.tools == () and adjudication.skill_names == ()
    assert "independent_challenge" in adjudication.prompt
    before = len(access.store.read().role_results)
    with pytest.raises(ValueError, match="wrong finding"):
        adjudication.accept(AdjudicatorOutput(finding_id="INVENTED", decision="pass"))
    assert len(access.store.read().role_results) == before
    assert (
        access.store.read().assignments[assignment].findings["RISK-F1"]["verifier_status"]
        == "pending"
    )


def test_roles_reject_missing_challenge_wrong_assignment_and_stale_result(role_context):
    access, assignment, adapter, specs, request = role_context
    with pytest.raises(ValueError, match="independent challenge"):
        adapter.prepare(specs["review-adjudicator"], request, "child-adjudicate")
    specialist_request = request.model_copy(
        update={"context": json.dumps({"assignment_id": assignment})}
    )
    with pytest.raises(ValueError, match="does not match"):
        adapter.prepare(specs["review-pnl"], specialist_request, "child-pnl")
    prepared = adapter.prepare(specs["review-challenger"], request, "child-challenge")
    access.store.update(
        lambda record: (
            record.assignments[assignment].findings["RISK-F1"].update({"claim": "Revised claim"})
        )
    )
    with pytest.raises(ValueError, match="finding changed"):
        prepared.accept(ChallengerOutput(finding_id="RISK-F1"))
    assert not access.store.read().role_results
    with pytest.raises(ValueError, match="validated specialist report"):
        adapter.prepare(
            specs["review-lead"], request.model_copy(update={"context": "{}"}), "child-lead"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output",
    [
        "The finding is verified",
        '{"decision":"PASS"}',
        '{"finding_id":"F1","decision":"PASS"}',
        json.dumps(
            {
                "finding_id": "F1",
                "challenges": [
                    {"challenge_type": "data_quality", "status": "pass", "explanation": "x" * 1300}
                ],
            }
        ),
    ],
)
async def test_malformed_or_silently_truncated_child_output_cannot_complete(output):
    spec = SubagentSpec(name="typed", input_schema=FindingInput, result_schema=ChallengerOutput)

    class Graph:
        async def ainvoke(self, *args, **kwargs):
            return {"messages": [AIMessage(content=output)]}

    policy = DelegationPolicy(enabled=True)
    runner = DelegationRunner(
        model=object(),
        tools=[],
        registry=SubagentRegistry.build([spec], tools=[], skills=[]),
        policy=policy,
        graph_builder=lambda *args, **kwargs: Graph(),
    )
    result = await runner.run(
        {
            "agent_name": "typed",
            "task": "challenge",
            "context": '{"assignment_id":"A","finding_id":"F1"}',
        },
        scope=RunScope(policy),
    )
    assert result.status == "failed" and result.result_ref is None
    assert result.structured_output is None


@pytest.mark.asyncio
async def test_host_selects_role_models_and_validates_input_before_execution():
    calls = []
    low, high = object(), object()
    specs = [
        SubagentSpec(
            name=role, input_schema=FindingInput, result_schema=ChallengerOutput, model_role=role
        )
        for role in ("low_cost", "high_cost")
    ]

    class Graph:
        async def ainvoke(self, *args, **kwargs):
            return {
                "messages": [AIMessage(content='{"finding_id":"F1","research_complete":false}')]
            }

    def build(model, tools, **kwargs):
        calls.append((model, tools, kwargs))
        return Graph()

    policy = DelegationPolicy(enabled=True)
    runner = DelegationRunner(
        model=object(),
        tools=[],
        registry=SubagentRegistry.build(specs, tools=[], skills=[]),
        role_models={"low_cost": low, "high_cost": high},
        policy=policy,
        graph_builder=build,
    )
    scope = RunScope(policy)
    for spec in specs:
        result = await runner.run(
            {
                "agent_name": spec.name,
                "task": "challenge",
                "context": '{"assignment_id":"A","finding_id":"F1"}',
            },
            scope=scope,
        )
        assert (
            result.status == "completed" and result.structured_output["research_complete"] is False
        )
    assert [call[0] for call in calls] == [low, high]
    invalid = await runner.run(
        {"agent_name": "low_cost", "task": "challenge", "context": "untyped prose"}, scope=scope
    )
    assert invalid.status == "rejected" and len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [False, True])
async def test_react_schema_transport_preserves_raw_output_for_strict_validation(extra):
    from tests.agent.test_agent_entrypoints import RoutingModel, _call

    payload = {"finding_id": "F1", "research_complete": False}
    if extra:
        payload["decision"] = "pass"
    model = RoutingModel(respond=lambda messages, names: _call("ChallengerOutput", payload, "C1"))
    spec = SubagentSpec(name="typed", input_schema=FindingInput, result_schema=ChallengerOutput)
    policy = DelegationPolicy(enabled=True)
    runner = DelegationRunner(
        model=model,
        tools=[],
        registry=SubagentRegistry.build([spec], tools=[], skills=[]),
        policy=policy,
    )
    result = await runner.run(
        {
            "agent_name": "typed",
            "task": "challenge",
            "context": '{"assignment_id":"A","finding_id":"F1"}',
        },
        scope=RunScope(policy),
    )
    assert result.status == ("failed" if extra else "completed")
    assert result.model_calls == (2 if extra else 1)
    assert result.tool_calls == 0  # Schema transport grants no research capability.
    assert (result.structured_output is None) == extra


@pytest.mark.asyncio
async def test_typed_child_reserves_budget_for_explicit_incomplete_result():
    from langchain_core.tools import StructuredTool

    from tests.agent.test_agent_entrypoints import RoutingModel, _call

    reads = []

    def research() -> str:
        """Perform one independent research operation."""
        reads.append(1)
        return "Additional context is needed."

    tool = StructuredTool.from_function(research)

    def respond(messages, names):
        if "research" in names:
            return _call("research", {}, "research-" + str(len(reads)))
        return _call("ChallengerOutput", {"finding_id": "F1", "research_complete": False}, "C1")

    spec = SubagentSpec(name="typed", tool_names=("research",), result_schema=ChallengerOutput)
    policy = DelegationPolicy(enabled=True, max_tool_calls=5, max_model_calls=8)
    runner = DelegationRunner(
        model=RoutingModel(respond=respond),
        tools=[tool],
        registry=SubagentRegistry.build([spec], tools=[tool], skills=[]),
        policy=policy,
    )
    result = await runner.run({"agent_name": "typed", "task": "challenge"}, scope=RunScope(policy))
    assert result.status == "completed"
    assert result.structured_output["research_complete"] is False
    assert result.tool_calls == len(reads) == 3
    assert result.model_calls == 4


@pytest.mark.asyncio
async def test_one_format_repair_retains_research_and_cannot_reopen_tools():
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.tools import StructuredTool

    from tests.agent.test_agent_entrypoints import RoutingModel, _call

    reads = []

    def research() -> str:
        """Read source evidence."""
        reads.append(1)
        return "Assigned evidence."

    tool = StructuredTool.from_function(research)

    def respond(messages, names):
        if isinstance(messages[-1], HumanMessage) and "failed validation" in messages[-1].content:
            assert names == ("ChallengerOutput",)
            assert any(isinstance(m, ToolMessage) and m.name == "research" for m in messages)
            return _call(
                "ChallengerOutput", {"finding_id": "F1", "research_complete": False}, "fixed"
            )
        if not any(isinstance(m, ToolMessage) for m in messages):
            return _call("research", {}, "read")
        return _call("ChallengerOutput", {"finding_id": "F1", "decision": "pass"}, "invalid")

    spec = SubagentSpec(name="typed", tool_names=("research",), result_schema=ChallengerOutput)
    policy = DelegationPolicy(enabled=True, max_model_calls=5, max_tool_calls=10)
    runner = DelegationRunner(
        model=RoutingModel(respond=respond),
        tools=[tool],
        registry=SubagentRegistry.build([spec], tools=[tool], skills=[]),
        policy=policy,
    )
    result = await runner.run({"agent_name": "typed", "task": "challenge"}, scope=RunScope(policy))
    assert result.status == "completed" and result.model_calls == 3
    assert result.structured_output["research_complete"] is False
    assert result.tool_calls == len(reads) == 1
