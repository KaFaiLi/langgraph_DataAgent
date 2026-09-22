"""All supported domains execute through the general ReAct host and shared skill contracts."""

from __future__ import annotations

import json
from datetime import date

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from data_agent.agent import react_agent
from data_agent.config import Settings
from data_agent.review.domain.desk_context import DeskContext
from data_agent.skills.review import discover_skills, load_analysis_runner
from data_agent.tools.review_context import ToolContext
from data_agent.tools.review_runs import ReviewWorkspace, build_review_run_tools
from tests.agent.test_agent_entrypoints import RoutingModel, _call
from tests.review.fixtures.migration import make_migration_sources


@pytest.mark.asyncio
async def test_general_agent_delegates_four_domains_with_compatible_deterministic_outputs(
    tmp_path, monkeypatch
):
    sources = make_migration_sources(tmp_path / "source", tmp_path / "fixtures")
    definitions = {s.name: s for s in discover_skills()}
    workspace = ReviewWorkspace(
        tmp_path / "source", tmp_path / "output", definitions, "ALL-DOMAINS"
    )
    access = workspace.access("ALL-DOMAINS")
    record = access.store.initialize(
        DeskContext(
            desk_name="Synthetic",
            business_description="Supported-domain migration fixture",
            review_start=date(2025, 1, 1),
            review_end=date(2025, 7, 31),
        ),
        definitions,
    )
    assignments = {}
    for name, paths in sources.items():
        ids = [record.manifest.by_path(path).source_id for path in paths]
        for identifier in ids:
            access.classify(identifier, [name], "Synthetic schema ownership")
        assignments[name] = access.assign(name, ids, "Review all assigned sources")["assignment_id"]
    tools = build_review_run_tools(workspace)

    class Client:
        async def get_tools(self):
            return tools

    monkeypatch.setattr(react_agent, "build_mcp_client", lambda settings: Client())

    def root_response(messages, names):
        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(
                content="Four typed specialist results recorded; verification remains pending."
            )
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "run_subagent",
                    "id": "delegate-" + name,
                    "args": {
                        "agent_name": "review-" + name,
                        "task": "Inspect assigned population",
                        "context": json.dumps({"assignment_id": assignment}),
                    },
                }
                for name, assignment in reversed(assignments.items())
            ],
        )

    def specialist_response(messages, names):
        human = next(m for m in messages if isinstance(m, HumanMessage))
        context = json.loads(human.content.split("\n", 1)[1])
        if not any(isinstance(m, ToolMessage) for m in messages):
            return _call(
                "execute_assigned_analysis",
                {
                    "run_id": context["run_id"],
                    "assignment_id": context["assignment_id"],
                },
                "analyze",
            )
        path = context["source_paths"][0]
        suffix = "lines=4:4" if path.endswith(".md") else "rows=2:2"
        return _call(
            "CandidateSubmission",
            {
                "findings": [
                    {
                        "finding_id": "F1",
                        "title": "Source population observation",
                        "category": "scope",
                        "claim": "The assigned source includes a recorded observation.",
                        "severity": "low",
                        "confidence": 0.8,
                        "is_observation": True,
                        "evidence": [{"locator": f"source://{path}#{suffix}"}],
                    }
                ]
            },
            "draft",
        )

    settings = Settings(
        _env_file=None,
        source_root=workspace.source_root,
        review_workspace=str(workspace.workspace_root),
        review_run_id="ALL-DOMAINS",
        subagents_enabled=True,
    )
    bundle = await react_agent.build_agent(
        settings,
        model=RoutingModel(respond=root_response),
        role_models={
            "low_cost": RoutingModel(respond=specialist_response),
            "high_cost": RoutingModel(respond=specialist_response),
        },
    )
    result = await bundle.agent.ainvoke(
        {"messages": [{"role": "user", "content": "Review all four domains."}]},
        config={"recursion_limit": 60},
    )
    assert "Four typed" in result["messages"][-1].content
    current = access.store.read()
    assert len(current.role_results) == 4
    assert {a.skill_name for a in current.assignments.values()} == set(sources)
    for assignment in current.assignments.values():
        assert assignment.candidate_ref and assignment.findings
        assert all(f["verifier_status"] == "pending" for f in assignment.findings.values())
        stored = access._execution(assignment).load(assignment.analysis_ref)
        ctx = ToolContext(workspace.source_root, tmp_path / "direct", stored.manifest)
        direct = load_analysis_runner(definitions[assignment.skill_name])(ctx, stored.source_paths)
        assert [a.model_dump(mode="json")["tables"] for a in stored.analyses] == [
            a.model_dump(mode="json")["tables"] for a in direct
        ]
        assert [a.overviews for a in stored.analyses] == [a.overviews for a in direct]
        assert any(a.overviews for a in stored.analyses)
    pnl_assignment = current.assignments[assignments["pnl"]]
    assert len(pnl_assignment.source_ids) == 3
    assert not access.coverage()["publication_ready"]
