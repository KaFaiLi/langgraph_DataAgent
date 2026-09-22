"""Start/resume/status for reviews conducted by the general-purpose ReAct agent."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

from data_agent.agent.react_agent import build_agent
from data_agent.config import Settings, get_settings
from data_agent.review.application.execution import ReviewExecution, RunBudgetExceeded, RunBusyError
from data_agent.review.application.run_bundle import RunBundleError, load_completed_run
from data_agent.review.application.sealed_bundle import load_sealed_bundle, validate_seal
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.run_record import ReviewRecord
from data_agent.review.interface import ReviewRequest
from data_agent.review.telemetry import ReviewTelemetryHandler
from data_agent.skills.review import discover_skills
from data_agent.tools.review_publication import PublicationCapabilities, publication_fingerprint
from data_agent.tools.review_runs import RunCapabilities, RunStore
from data_agent.tracing import JsonlTraceSink


class AgentReviewResult(BaseModel):
    """Version 2 adds interruption, budgets and disclosures without a warning status.

    completed means a validated bundle exists. Disclosed unresolved items are data
    quality/scope limitations, never verified findings or hidden execution failures.
    """

    schema_version: Literal[2] = 2
    status: Literal["running", "interrupted", "completed", "failed", "not_found"]
    run_id: str
    output_dir: Path
    bundle_path: Path | None = None
    failure_reason: str | None = None
    retryable: bool = False
    budget_used: dict[str, float] = Field(default_factory=dict)
    budget_limits: dict[str, float] = Field(default_factory=dict)
    unresolved_items: int = 0
    completed_specialists: list[str] = Field(default_factory=list)
    final_report: dict | None = None
    specialist_reports: dict[str, dict] = Field(default_factory=dict)
    message: str | None = None
    trace_path: Path | None = None


def open_run_store(root: Path) -> RunStore:
    """Read an explicitly user-selected run directory without creating a database."""
    root = root.resolve()
    path = root / "review_record.sqlite"
    if path.is_symlink() or not path.is_file():
        raise ValueError("review record is missing or a symlink")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT payload FROM run_record WHERE id=1").fetchone()
    if row is None:
        raise ValueError("review record is empty")
    record = ReviewRecord.model_validate_json(row[0])
    store = RunStore(Path(record.source_root), root, record.run_id)
    store.read()  # Validate immutable identity and manifest binding.
    return store


class AgentReviewService:
    """Infrastructure around model-selected tools, never a deterministic review coordinator."""

    def __init__(
        self, settings: Settings | None = None, *, trace_sinks=(), agent_builder=build_agent
    ):
        self.settings = settings or get_settings()
        self.trace_sinks, self.agent_builder = tuple(trace_sinks), agent_builder

    def _definitions(self):
        return {s.name: s for s in discover_skills(self.settings.skills_path)}

    async def start(self, request: ReviewRequest) -> AgentReviewResult:
        desk = DeskContext.model_validate(request.desk_context)
        if (desk.review_start, desk.review_end) != (request.review_start, request.review_end):
            raise ValueError("desk context differs from requested review period")
        # Apply the same identity contract as bound MCP access.
        from data_agent.tools.review_runs import ReviewWorkspace

        workspace = ReviewWorkspace(
            request.source_root,
            request.output_dir.parent,
            self._definitions(),
            request.run_id,
            output_dir=request.output_dir,
        )
        store = workspace.access(request.run_id).store
        try:
            store.initialize(desk, workspace.definitions)
        except (OSError, ValueError) as exc:
            # The output/source separation was validated before any failure artifact write.
            if store.path.exists():
                raise ValueError("existing run context cannot be replaced") from exc
            store.output_dir.mkdir(parents=True, exist_ok=True)
            result = AgentReviewResult(
                status="failed",
                run_id=request.run_id,
                output_dir=store.output_dir,
                failure_reason="preflight_source_error",
            )
            (store.output_dir / "failure.json").write_text(
                result.model_dump_json(indent=2), encoding="utf-8"
            )
            return result
        return await self.resume(store.output_dir)

    def status(self, run_dir: str | Path, *, include_reports: bool = False) -> AgentReviewResult:
        root = Path(run_dir).resolve()
        result = AgentReviewResult(status="not_found", run_id=root.name, output_dir=root)
        if not root.exists():
            return result
        try:
            if not (root / "review_record.sqlite").exists():
                failure_path = root / "failure.json"
                if failure_path.is_file() and not failure_path.is_symlink():
                    failure = json.loads(failure_path.read_text(encoding="utf-8"))
                    if failure.get("schema_version") == 2:
                        return AgentReviewResult.model_validate(failure)
                if (root / "checkpoints.sqlite").exists() and not (
                    root / "run_manifest.json"
                ).exists():
                    return result.model_copy(
                        update={
                            "status": "failed",
                            "failure_reason": "legacy_checkpoint_unsupported",
                        }
                    )
                # Read-only compatibility: legacy bundles may reopen; old checkpoints
                # are never resumed by invoking the deterministic review service.
                if root.name == "bundle" and (root.parent / "review_record.sqlite").is_file():
                    return self.status(root.parent, include_reports=include_reports)
                bundle = (
                    load_sealed_bundle(root)
                    if (root / "bundle_receipt.json").exists()
                    else load_completed_run(root)
                )
                return self._completed(result, bundle, root, include_reports)
            store = open_run_store(root)
            record = store.read()
            result = result.model_copy(
                update={
                    "run_id": record.run_id,
                    "status": record.status,
                    "budget_used": record.budget_used,
                    "budget_limits": record.budget_limits,
                    "completed_specialists": [
                        a.skill_name for a in record.assignments.values() if a.report
                    ],
                    "trace_path": root / "telemetry" / "execution_trace.jsonl",
                }
            )
            if record.status == "completed":
                target = root / "bundle"
                if record.artifacts.get("bundle") != str(target):
                    raise ValueError("completed bundle path differs from the run binding")
                seal = record.artifacts.get("bundle_seal")
                if not seal:
                    raise ValueError("completed run has no integrity seal")
                receipt = validate_seal(target, seal)
                if receipt["input_fingerprint"] != publication_fingerprint(record):
                    raise ValueError("completed run state differs from its sealed bundle")
                return self._completed(
                    result, load_sealed_bundle(target, seal), target, include_reports
                )
            if record.failures:
                result.failure_reason = record.failures[-1].get("code", "legacy_execution_error")
                result.retryable = record.failures[-1].get("retryable", record.status != "failed")
            if record.invocation.get("status") == "running":
                import fcntl

                lease_path = root / "execution.lock"
                if not lease_path.is_file() or lease_path.is_symlink():
                    raise ValueError("active execution has no valid process lease")
                with lease_path.open("r") as lease:
                    try:
                        fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        result.status = "running"
                    else:
                        result.status, result.failure_reason, result.retryable = (
                            "interrupted",
                            "process_interrupted",
                            True,
                        )
                        fcntl.flock(lease.fileno(), fcntl.LOCK_UN)
            return result
        except (OSError, ValueError, KeyError, RuntimeError, sqlite3.Error) as exc:
            result.status, result.retryable = "failed", False
            result.failure_reason = (
                exc.code if isinstance(exc, RunBundleError) else "invalid_run_state"
            )
            return result

    @staticmethod
    def _completed(result, bundle, path, include_reports):
        result.status, result.bundle_path, result.failure_reason = "completed", path, None
        result.run_id = bundle.run.run_id
        result.retryable = False
        result.completed_specialists = [d.value for d in bundle.specialist_reports]
        result.unresolved_items = len(bundle.final_report.unresolved_questions)
        if include_reports:
            result.final_report = bundle.final_report.model_dump(mode="json")
            result.specialist_reports = {
                d.value: r.model_dump(mode="json") for d, r in bundle.specialist_reports.items()
            }
        return result

    async def resume(
        self,
        run_dir: str | Path,
        *,
        message: str | None = None,
        model: Any = None,
        role_models: dict | None = None,
    ) -> AgentReviewResult:
        root = Path(run_dir).resolve()
        status = self.status(root, include_reports=True)
        if status.status in {"completed", "not_found"} or (
            status.status == "failed" and not status.retryable
        ):
            return status
        store = open_run_store(root)
        definitions = self._definitions()
        limits = {
            "model_calls": self.settings.review_max_model_calls,
            "tool_calls": self.settings.review_max_tool_calls,
            "child_runs": self.settings.review_child_max_runs,
            "active_seconds": self.settings.review_max_active_seconds,
        }
        try:
            with ReviewExecution(store, limits) as execution:
                try:
                    store.check_sources(store.read())
                except (ValueError, OSError):
                    execution.finish("source_integrity_failure", retryable=False)
                    return self.status(root)
                checkpoint = root / "conversation.sqlite"
                if checkpoint.is_symlink():
                    execution.finish("invalid_checkpoint", retryable=False)
                    return self.status(root)
                # Recover a crash between the atomic directory rename and SQLite commit.
                if (root / "bundle").exists():
                    try:
                        recovered = PublicationCapabilities(
                            RunCapabilities(store, definitions)
                        ).publish()
                        if not recovered["published"]:
                            raise ValueError(
                                "existing bundle lacks current publication requirements"
                            )
                    except (OSError, ValueError, RuntimeError):
                        execution.finish("bundle_integrity_invalid", retryable=False)
                        return self.status(root)
                    execution.finish()
                    return self.status(root, include_reports=True)
                settings = self.settings.model_copy(
                    update={
                        "source_root": str(store.source_root),
                        "review_run_id": store.run_id,
                        "review_output_dir": str(root),
                        "review_assignment_id": None,
                        "subagents_enabled": True,
                        "agent_max_iterations": self.settings.review_root_max_iterations,
                    }
                )
                try:
                    async with asyncio.timeout(execution.remaining_seconds()):
                        async with AsyncSqliteSaver.from_conn_string(str(checkpoint)) as saver:
                            bundle = await self.agent_builder(
                                settings,
                                model=model,
                                role_models=role_models,
                                checkpointer=saver,
                                execution=execution,
                            )
                            config = {"configurable": {"thread_id": store.run_id}}
                            snapshot = await bundle.checkpoint_graph.aget_state(config)
                            pending = bool(snapshot.next)
                            record = store.read()
                            prompt = message or (
                                "Load general-review and complete this review with model-selected investigation, "
                                "specialist assignments, independent verification, lead synthesis, and publication. "
                                "Inspect authoritative review_coverage and read_review_assignment, reuse accepted results, "
                                "and repair outstanding obligations within the persisted budgets. "
                                "Do not stop after a progress summary while publication requirements remain achievable. "
                                "If information is unavailable, record specific unresolved disclosures. "
                                f"Host run_id={store.run_id}. Budget used={record.budget_used}; "
                                f"limits={record.budget_limits}."
                            )
                            config["configurable"]["resume_pending"] = pending
                            config["callbacks"] = [
                                ReviewTelemetryHandler(root / "telemetry" / "llm_usage.jsonl")
                            ]
                            result = await bundle.ainvoke(
                                prompt,
                                config=config,
                                trace_sinks=[
                                    JsonlTraceSink(root / "telemetry" / "execution_trace.jsonl"),
                                    *self.trace_sinks,
                                ],
                            )
                            answer = result["messages"][-1].content
                            execution.finish(
                                None if store.read().status == "completed" else "work_remaining"
                            )
                except asyncio.CancelledError:
                    execution.finish("cancelled")
                    raise
                except (RunBudgetExceeded, TimeoutError):
                    execution.finish("budget_exhausted", retryable=False)
                    answer = None
                except GraphRecursionError:
                    execution.finish("iteration_limit")
                    answer = None
                except Exception as exc:  # noqa: BLE001 - provider/transport failures are persisted, never completion
                    execution.finish("execution_error:" + type(exc).__name__)
                    answer = None
                result = self.status(root, include_reports=True)
                result.message = answer if isinstance(answer, str) else json.dumps(answer)
                return result
        except RunBusyError:
            return status.model_copy(
                update={"status": "running", "failure_reason": "run_busy", "retryable": True}
            )
