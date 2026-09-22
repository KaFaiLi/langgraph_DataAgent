"""Durable general-agent checkpoints, cumulative budgets and trustworthy status."""

from __future__ import annotations

from datetime import date

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from data_agent.agent import react_agent
from data_agent.agent.subagents.contracts import DelegationRequest, DelegationResult
from data_agent.config import Settings
from data_agent.review.agent_service import AgentReviewService
from data_agent.review.application.execution import ReviewExecution, RunBudgetExceeded, RunBusyError
from data_agent.review.domain.desk_context import DeskContext
from data_agent.skills.review import discover_skills
from data_agent.tools.review_runs import ReviewWorkspace, build_review_run_tools
from tests.agent.test_agent_entrypoints import RoutingModel, _call


@pytest.fixture()
def run(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.md").write_text("# Desk notes\nUnconfirmed supplied context.\n")
    definitions = {s.name: s for s in discover_skills()}
    workspace = ReviewWorkspace(source, tmp_path / "output", definitions, "RESUME")
    access = workspace.access("RESUME")
    access.store.initialize(
        DeskContext(
            desk_name="Resume test",
            business_description="Synthetic",
            review_start=date(2025, 1, 1),
            review_end=date(2025, 1, 31),
        ),
        definitions,
    )

    class Client:
        async def get_tools(self):
            return build_review_run_tools(workspace)

    monkeypatch.setattr(react_agent, "build_mcp_client", lambda settings: Client())
    settings = Settings(
        _env_file=None,
        source_root=source,
        review_workspace=str(workspace.workspace_root),
        review_run_id="RESUME",
        review_root_max_iterations=12,
    )
    return access, settings


LIMITS = {"model_calls": 5, "tool_calls": 10, "child_runs": 2, "active_seconds": 120}


@pytest.mark.asyncio
async def test_restart_resumes_pending_root_checkpoint_and_keeps_budgets(run):
    access, settings = run

    def first(messages, names):
        if isinstance(messages[-1], ToolMessage):
            raise RuntimeError("simulated provider interruption")  # noqa: TRY004 - deliberate provider failure
        return _call("review_coverage", {"run_id": "RESUME"}, "coverage-once")

    service = AgentReviewService(settings)
    result = await service.resume(
        access.store.output_dir,
        message="Remember original request",
        model=RoutingModel(respond=first),
        role_models={},
    )
    assert result.status == "interrupted"
    assert result.failure_reason == "execution_error:RuntimeError"
    assert result.budget_used["model_calls"] == 2
    assert result.budget_used["tool_calls"] == 1

    def resumed(messages, names):
        assert any(
            isinstance(m, HumanMessage) and m.content == "Remember original request"
            for m in messages
        )
        assert isinstance(messages[-1], ToolMessage)
        return AIMessage(content="Resumed after the persisted coverage result.")

    restarted = AgentReviewService(settings.model_copy(update={"review_max_model_calls": 9999}))
    second = await restarted.resume(
        access.store.output_dir, model=RoutingModel(respond=resumed), role_models={}
    )
    assert second.message.startswith("Resumed after")
    assert second.status == "interrupted" and second.failure_reason == "work_remaining"
    assert second.budget_used["model_calls"] == 3 and second.budget_used["tool_calls"] == 1
    assert second.budget_limits == result.budget_limits
    assert access.store.read().manifest_digest


def test_process_death_and_child_replay_have_stable_ids_and_no_budget_reset(run):
    access, settings = run
    request = DelegationRequest(agent_name="review-lead", task="Synthesize", context="{}")
    with ReviewExecution(access.store, LIMITS) as execution:
        child_id, cached = execution.begin_child("stable-tool-call", request, "child-1")
        assert child_id == "child-1" and cached is None
        execution.reserve("model_calls", child_id=child_id)
        with pytest.raises(RunBusyError), ReviewExecution(access.store, LIMITS):
            pass
        # Release the OS lease without a finish record, as after process death.
    status = AgentReviewService(settings).status(access.store.output_dir)
    assert status.status == "interrupted" and status.failure_reason == "process_interrupted"
    with ReviewExecution(access.store, {**LIMITS, "child_runs": 999}) as restarted:
        child_id, cached = restarted.begin_child("stable-tool-call", request, "new-child")
        assert child_id == "child-1" and cached.status == "failed"
        assert "process_interrupted" in cached.error
        assert access.store.read().budget_used["child_runs"] == 1
        _, cached = restarted.begin_child("new-tool-call", request, "child-2")
        assert cached is None
        completed = DelegationResult(
            child_id="child-2",
            agent_name=request.agent_name,
            status="completed",
            output="typed result",
            result_ref="stored",
        )
        restarted.finish_child("new-tool-call", completed)
        assert restarted.begin_child("new-tool-call", request, "ignored")[1] == completed
        with pytest.raises(RunBudgetExceeded, match="child"):
            restarted.begin_child("third", request, "child-3")
        restarted.finish("work_remaining")
    assert access.store.read().budget_used["model_calls"] == 1
    assert access.store.read().budget_limits == LIMITS


@pytest.mark.asyncio
async def test_aggregate_budget_exhaustion_cannot_be_reset_by_resume(run):
    access, settings = run
    service = AgentReviewService(settings.model_copy(update={"review_max_model_calls": 1}))

    def response(messages, names):
        return _call("review_coverage", {"run_id": "RESUME"}, "coverage")

    first = await service.resume(
        access.store.output_dir, model=RoutingModel(respond=response), role_models={}
    )
    assert first.status == "failed" and first.failure_reason == "budget_exhausted"
    assert first.budget_used["model_calls"] == 1
    resumed = await AgentReviewService(settings).resume(access.store.output_dir)
    assert resumed.status == "failed" and resumed.budget_used == first.budget_used


@pytest.mark.asyncio
async def test_source_changes_fail_before_model_and_partial_bundle_never_completes(run):
    access, settings = run
    (access.store.source_root / "notes.md").write_text("Changed source")
    service = AgentReviewService(settings)
    result = await service.resume(access.store.output_dir)
    assert result.status == "failed" and result.failure_reason == "source_integrity_failure"
    target = access.store.output_dir / "bundle"
    target.mkdir()
    (target / "run_manifest.json").write_text('{"status":"completed"}')
    access.store.update(lambda r: setattr(r, "status", "completed"))
    assert service.status(access.store.output_dir).status == "failed"
    legacy = target / "legacy"
    legacy.mkdir()
    (legacy / "run_manifest.json").write_text("malformed")
    assert service.status(legacy).status == "failed"


def test_accepted_role_survives_crash_before_delegation_receipt(tmp_path):
    from tests.review.test_review_publication import context as role_fixture
    from tests.review.test_review_publication import workspace as workspace_fixture
    from tests.review.test_review_verification import _independent_result

    context = role_fixture.__wrapped__(workspace_fixture.__wrapped__(tmp_path))
    access, _assignment, _adapter, _specs, request = context
    with ReviewExecution(access.store, LIMITS) as execution:
        adjudication = request.model_copy(update={"agent_name": "review-adjudicator"})
        execution.begin_child("adjudicate-tool", adjudication, "adjudicate-1")
        ref = _independent_result(context)
        # Role admission committed, but the process died before finish_child.
    with ReviewExecution(access.store, LIMITS) as restarted:
        identity, cached = restarted.begin_child("adjudicate-tool", adjudication, "unused")
        assert identity == "adjudicate-1" and cached.status == "completed"
        assert cached.result_ref == ref and cached.structured_output["result_ref"] == ref
        assert access.store.read().budget_used["child_runs"] == 1
        restarted.finish()


def test_legacy_failure_records_remain_resumable_and_bad_legacy_manifest_fails(run):
    access, settings = run
    access.store.update(lambda r: r.failures.append({"code": "source_tool_failed"}))
    status = AgentReviewService(settings).status(access.store.output_dir)
    assert status.retryable and status.failure_reason == "source_tool_failed"
    target = access.store.output_dir / "old-run"
    target.mkdir()
    (target / "run_manifest.json").write_text("not json")
    status = AgentReviewService(settings).status(target)
    assert status.status == "failed" and status.failure_reason


@pytest.mark.asyncio
async def test_cancellation_preserves_checkpointable_run_and_releases_lease(run):
    import asyncio

    access, settings = run
    started = asyncio.Event()

    async def blocked_builder(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    service = AgentReviewService(settings, agent_builder=blocked_builder)
    task = asyncio.create_task(service.resume(access.store.output_dir))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    status = service.status(access.store.output_dir)
    assert status.status == "interrupted" and status.failure_reason == "cancelled"
    with ReviewExecution(access.store, LIMITS) as execution:
        execution.finish("work_remaining")
