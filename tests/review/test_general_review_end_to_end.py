"""Complete model-directed reviews across four domains with legacy entrypoints forbidden."""

from __future__ import annotations

import json
from datetime import date

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from data_agent.agent import react_agent
from data_agent.config import Settings
from data_agent.review.agent_service import AgentReviewService
from data_agent.review.application.sealed_bundle import load_sealed_bundle
from data_agent.review.interface import ReviewRequest
from data_agent.skills.review import discover_skills
from data_agent.tools.review_runs import ReviewWorkspace, build_review_run_tools
from tests.agent.test_agent_entrypoints import RoutingModel
from tests.review.fixtures.migration import make_migration_sources


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_all_domains_publish_through_react_and_resume_without_legacy_graphs(
    tmp_path, monkeypatch, reverse
):
    import data_agent.review.orchestration.graph as parent
    import data_agent.review.orchestration.specialist.graph as specialist
    import data_agent.review.service as legacy
    from data_agent.skills import runtime

    def forbidden(*args, **kwargs):
        pytest.fail("new general review invoked a legacy workflow")

    monkeypatch.setattr(legacy.ReviewService, "__init__", forbidden)
    monkeypatch.setattr(parent, "build_parent_graph", forbidden)
    monkeypatch.setattr(legacy, "build_parent_graph", forbidden)
    monkeypatch.setattr(specialist, "build_specialist_graph", forbidden)
    monkeypatch.setattr(runtime, "build_skill_graph", forbidden)

    source, output = tmp_path / "source", tmp_path / "run"
    families = make_migration_sources(source, tmp_path / "fixtures")
    definitions = {s.name: s for s in discover_skills()}
    workspace = ReviewWorkspace(source, tmp_path, definitions, "E2E", output_dir=output)
    access = workspace.access("E2E")

    class Client:
        async def get_tools(self):
            return build_review_run_tools(workspace)

    monkeypatch.setattr(react_agent, "build_mcp_client", lambda settings: Client())
    counter = 0
    early_blockers = []
    failed_once = False

    def call(name, **args):
        nonlocal counter
        counter += 1
        return AIMessage(
            content="", tool_calls=[{"name": name, "id": f"call-{counter}", "args": args}]
        )

    def delegate(role, **context):
        return call(
            "run_subagent",
            agent_name=role,
            task="Review the authoritative context",
            context=json.dumps(context),
        )

    def root(messages, names):
        record = access.store.read()
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        if not tool_messages:
            return call("publish_review", run_id="E2E")
        if not early_blockers:
            first = json.loads(tool_messages[0].content)
            assert not first["published"] and first["blockers"]
            early_blockers.extend(first["blockers"])
        for name in sorted(families, reverse=reverse):
            ids = [record.manifest.by_path(p).source_id for p in families[name]]
            for identifier in ids:
                if record.classifications.get(identifier) != [name]:
                    return call(
                        "classify_review_source",
                        run_id="E2E",
                        source_id=identifier,
                        skill_names=[name],
                        rationale="Fixture schema ownership",
                    )
            if not any(a.skill_name == name for a in record.assignments.values()):
                return call(
                    "assign_review_work",
                    run_id="E2E",
                    skill_name=name,
                    source_ids=ids,
                    rationale="Inspect complete source population",
                )
        for a in sorted(record.assignments.values(), key=lambda a: a.skill_name, reverse=reverse):
            if not a.candidate_ref:
                return delegate("review-" + a.skill_name, assignment_id=a.assignment_id)
            for source_id in a.source_ids:
                if source_id not in a.dispositions:
                    return call(
                        "record_source_disposition",
                        run_id="E2E",
                        assignment_id=a.assignment_id,
                        source_id=source_id,
                        disposition={
                            "status": "reviewed",
                            "reason": "Inspected assigned population",
                        },
                    )
            for finding_id, finding in a.findings.items():
                if finding["verifier_status"] == "pending":
                    role_results = [
                        r
                        for r in record.role_results.values()
                        if r.get("assignment_id") == a.assignment_id
                        and r.get("finding_id") == finding_id
                    ]
                    challenges = [r for r in role_results if r["role"] == "review-challenger"]
                    verdicts = [r for r in role_results if r["role"] == "review-adjudicator"]
                    if not challenges:
                        return delegate(
                            "review-challenger",
                            assignment_id=a.assignment_id,
                            finding_id=finding_id,
                        )
                    if not verdicts:
                        return delegate(
                            "review-adjudicator",
                            assignment_id=a.assignment_id,
                            finding_id=finding_id,
                        )
                    return call(
                        "apply_review_verification",
                        run_id="E2E",
                        assignment_id=a.assignment_id,
                        adjudicator_ref=verdicts[-1]["result_ref"],
                    )
            if not a.omission_disclosure:
                return call(
                    "audit_review_omissions",
                    run_id="E2E",
                    assignment_id=a.assignment_id,
                    action="disclose",
                    reason="This test promotes only a scoped observation; remaining deterministic candidates require separate review.",
                )
            if not a.report:
                return call(
                    "finalize_specialist_report", run_id="E2E", assignment_id=a.assignment_id
                )
        leads = [r for r in record.role_results.values() if r["role"] == "review-lead"]
        verifiers = [r for r in record.role_results.values() if r["role"] == "review-lead-verifier"]
        if not leads:
            return delegate("review-lead")
        if not record.lead_state:
            return call("prepare_lead_review", run_id="E2E", lead_ref=leads[-1]["result_ref"])
        if not verifiers:
            return delegate("review-lead-verifier")
        if record.lead_state["status"] != "accepted":
            return call(
                "apply_lead_verification", run_id="E2E", verifier_ref=verifiers[-1]["result_ref"]
            )
        if record.status != "completed":
            return call("publish_review", run_id="E2E")
        return AIMessage(
            content="Four-domain bundle published with explicit residual candidate disclosures."
        )

    def peer(messages, names):
        nonlocal failed_once
        human = next(m for m in messages if isinstance(m, HumanMessage))
        context = json.loads(human.content.split("\n", 1)[1])
        observed = any(isinstance(m, ToolMessage) for m in messages)
        if "CandidateSubmission" in names:
            if not observed:
                return call(
                    "execute_assigned_analysis",
                    run_id="E2E",
                    assignment_id=context["assignment_id"],
                )
            if reverse and context["skill"] == "risk-commentary" and not failed_once:
                failed_once = True
                raise RuntimeError("controlled provider failure")
            path = context["source_paths"][0]
            locator = f"source://{path}#" + ("lines=4:4" if path.endswith(".md") else "rows=2:2")
            return call(
                "CandidateSubmission",
                findings=[
                    {
                        "finding_id": context["skill"] + "-F1",
                        "title": "Scoped source observation",
                        "category": "scope",
                        "claim": "The assigned source contains a recorded observation.",
                        "severity": "low",
                        "confidence": 0.8,
                        "is_observation": True,
                        "evidence": [{"locator": locator}],
                    }
                ],
            )
        if "ChallengerOutput" in names:
            if not observed:
                return call(
                    "review_source_tool",
                    run_id="E2E",
                    assignment_id=context["assignment_id"],
                    tool_name="reopen_evidence",
                    arguments={"locator": context["finding"]["evidence"][0]["locator"]},
                )
            return call(
                "ChallengerOutput",
                finding_id=context["finding"]["finding_id"],
                research_complete=True,
                challenges=[
                    {
                        "challenge_type": kind,
                        "status": "not_applicable",
                        "explanation": "The scoped source-presence observation makes no claim in this category.",
                    }
                    for kind in context["required_challenge_types"]
                ],
            )
        if "AdjudicatorOutput" in names:
            return call(
                "AdjudicatorOutput", finding_id=context["finding"]["finding_id"], decision="pass"
            )
        if "LeadDraft" in names:
            findings = [f for report in context["specialist_reports"] for f in report["findings"]]
            assert len(findings) == 4 and all(f["verifier_status"] == "passed" for f in findings)
            return call(
                "LeadDraft",
                executive_summary="Four independently verified scoped source observations.",
                overall_desk_risk_assessment="Candidate investigation remains explicitly limited.",
                key_findings=[
                    {
                        "final_id": "FINAL-" + str(i),
                        "title": f["title"],
                        "statement": f["claim"],
                        "severity": "low",
                        "confidence": 0.8,
                        "derived_from": [f["finding_id"]],
                        "evidence": f["evidence"],
                    }
                    for i, f in enumerate(findings)
                ],
            )
        if "LeadVerifierOutput" in names:
            return call("LeadVerifierOutput", decision="pass")
        pytest.fail(f"unexpected peer tools: {names}")

    async def builder(settings, **kwargs):
        kwargs.update(
            model=RoutingModel(respond=root),
            role_models={
                "low_cost": RoutingModel(respond=peer),
                "high_cost": RoutingModel(respond=peer),
            },
        )
        return await react_agent.build_agent(settings, **kwargs)

    service = AgentReviewService(Settings(_env_file=None), agent_builder=builder)
    result = await service.start(
        ReviewRequest(
            source_root=source,
            output_dir=output,
            run_id="E2E",
            review_start=date(2025, 1, 1),
            review_end=date(2025, 7, 31),
            desk_context={
                "desk_name": "Synthetic",
                "business_description": "Fixture",
                "review_start": "2025-01-01",
                "review_end": "2025-07-31",
            },
        )
    )
    assert result.status == "completed", result.model_dump()
    bundle = load_sealed_bundle(result.bundle_path)
    assert len(bundle.specialist_reports) == len(bundle.final_report.key_findings) == 4
    assert all(report.data_overviews for report in bundle.specialist_reports.values())
    assert all(c.status == "reviewed" for c in bundle.run.coverage)
    assert all(r.omission_audit.unresolved_disclosures for r in bundle.specialist_reports.values())
    assert early_blockers and result.unresolved_items > 0
    record = access.store.read()
    assert record.budget_used["child_runs"] == 14 + int(reverse)
    assert len(record.role_results) == 14
    if reverse:
        assert any(f["code"] == "child_failed" for f in record.failures)
    before = result.budget_used
    assert (await service.resume(output)).budget_used == before
