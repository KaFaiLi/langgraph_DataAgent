"""Public checkpointed review interface."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from data_agent.config import get_settings
from data_agent.review.application.run_bundle import (
    load_completed_run,
    load_resume_context,
    write_run_context,
)
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.review import RunContext
from data_agent.review.interface import (
    ReviewRequest,
    ReviewResult,
    ReviewRunStatus,
    ReviewStatus,
)
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.llm.errors import RetryableLLMError, is_retryable_provider_error
from data_agent.review.orchestration.graph import build_parent_graph
from data_agent.review.telemetry import ReviewTelemetryHandler
from data_agent.tracing import (
    ExecutionTraceHandler,
    JsonlTraceSink,
    TraceSink,
    read_trace,
)


class ReviewService:
    """Start, resume, and inspect controlled reviews through one interface."""

    def __init__(
        self,
        llm_provider: ReviewLLMProvider | None = None,
        *,
        checkpoint_db_name: str = "checkpoints.sqlite",
        trace_sinks: Sequence[TraceSink] = (),
    ) -> None:
        self.llm_provider = llm_provider or DEFAULT_LLM_PROVIDER
        self.checkpoint_db_name = checkpoint_db_name
        self.trace_sinks = tuple(trace_sinks)

    def start(self, request: ReviewRequest) -> ReviewResult:
        """Persist authoritative inputs and execute a fresh review."""
        context = write_run_context(
            request.output_dir,
            run_id=request.run_id,
            source_root=request.source_root,
            desk_template=DeskContext.model_validate(request.desk_context),
            review_period=request.review_period,
        )
        root = Path(context.output_dir)
        self._write_execution_status(root, ReviewStatus.RUNNING, context.run_id)
        try:
            with SqliteSaver.from_conn_string(str(root / self.checkpoint_db_name)) as checkpointer:
                output = self._build_graph(checkpointer).invoke(
                    {
                        "run_id": context.run_id,
                        "source_root": context.source_root,
                        "output_dir": str(root),
                    },
                    config=self._config(context, root),
                )
        except (KeyboardInterrupt, InterruptedError):
            self._write_execution_status(root, ReviewStatus.INTERRUPTED, context.run_id)
            raise
        except Exception as exc:  # noqa: BLE001 - service persistence boundary
            return self._exception_result(root, context.run_id, exc)
        return self._result(output, root)

    def resume(self, run_dir: str | Path) -> ReviewResult:
        """Resume an interrupted review or reopen a validated completed bundle."""
        root = Path(run_dir).resolve()
        if (root / "run_manifest.json").is_file():
            bundle = load_completed_run(root)
            trace_path, last_event_at = self._trace_status(root)
            return ReviewResult(
                status=ReviewStatus.COMPLETED,
                run_id=bundle.run.run_id,
                output_dir=bundle.run_dir,
                final_report=bundle.final_report.model_dump(mode="json"),
                specialist_reports={
                    domain.value: report.model_dump(mode="json")
                    for domain, report in bundle.specialist_reports.items()
                },
                trace_path=trace_path,
                last_event_at=last_event_at,
            )

        context = load_resume_context(root, checkpoint_db_name=self.checkpoint_db_name)
        self._write_execution_status(root, ReviewStatus.RUNNING, context.run_id)
        try:
            with SqliteSaver.from_conn_string(str(root / self.checkpoint_db_name)) as checkpointer:
                output = self._build_graph(checkpointer).invoke(
                    None,
                    config=self._config(context, root),
                )
        except (KeyboardInterrupt, InterruptedError):
            self._write_execution_status(root, ReviewStatus.INTERRUPTED, context.run_id)
            raise
        except Exception as exc:  # noqa: BLE001 - service persistence boundary
            return self._exception_result(root, context.run_id, exc)
        return self._result(output, root)

    def status(self, run_dir: str | Path) -> ReviewRunStatus:
        """Return persisted run status without invoking the graph or a model."""
        root = Path(run_dir).resolve()
        completed = root / "run_manifest.json"
        failure = root / "failure.json"
        context = self._read_json(root / "run_context.json")
        run_id = str(context.get("run_id") or root.name)
        if completed.is_file():
            manifest = self._read_json(completed)
            trace_path, last_event_at = self._trace_status(root)
            return ReviewRunStatus(
                status=ReviewStatus.COMPLETED,
                run_id=str(manifest.get("run_id") or run_id),
                output_dir=root,
                completed_specialists=self._completed_specialists(root),
                trace_path=trace_path,
                last_event_at=last_event_at,
            )
        execution = self._read_json(root / "execution_status.json")
        persisted_status = execution.get("status")
        if persisted_status in {
            ReviewStatus.RUNNING.value,
            ReviewStatus.INTERRUPTED.value,
            ReviewStatus.RETRYABLE_FAILURE.value,
        }:
            trace_path, last_event_at = self._trace_status(root)
            return ReviewRunStatus(
                status=ReviewStatus(persisted_status),
                run_id=str(execution.get("run_id") or run_id),
                output_dir=root,
                failure_reason=execution.get("failure_reason"),
                completed_specialists=self._completed_specialists(root),
                trace_path=trace_path,
                last_event_at=last_event_at,
            )
        if failure.is_file():
            data = self._read_json(failure)
            trace_path, last_event_at = self._trace_status(root)
            return ReviewRunStatus(
                status=ReviewStatus.FAILED,
                run_id=str(data.get("run_id") or run_id),
                output_dir=root,
                failure_reason=data.get("failure_reason"),
                completed_specialists=self._completed_specialists(root),
                trace_path=trace_path,
                last_event_at=last_event_at,
            )
        trace_path, last_event_at = self._trace_status(root)
        return ReviewRunStatus(
            status=ReviewStatus.RUNNING if root.is_dir() else ReviewStatus.NOT_FOUND,
            run_id=run_id,
            output_dir=root,
            completed_specialists=self._completed_specialists(root),
            trace_path=trace_path,
            last_event_at=last_event_at,
        )

    def _build_graph(self, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
        return build_parent_graph(
            llm_provider=self.llm_provider,
            checkpointer=checkpointer,
        )

    def _config(self, context: RunContext, root: Path) -> RunnableConfig:
        settings = get_settings()
        trace_path = self._trace_path(root)
        operational_sink = JsonlTraceSink(
            trace_path,
            include_preview=settings.trace_result_preview_chars > 0,
        )
        callbacks: list[BaseCallbackHandler] = [
            ReviewTelemetryHandler(root / "telemetry" / "llm_usage.jsonl"),
            ExecutionTraceHandler(
                logical_run_id=context.run_id,
                sinks=[operational_sink, *self.trace_sinks],
                result_preview_chars=settings.trace_result_preview_chars,
            ),
        ]
        return {
            "configurable": {
                "thread_id": context.run_id,
                "desk_template": context.desk_template.model_dump(mode="json"),
                "review_period": context.review_period,
                "llm_provider": self.llm_provider,
            },
            "metadata": {"risk_agent_graph": "parent"},
            "callbacks": callbacks,
        }

    @staticmethod
    def _result(output: dict[str, Any], root: Path) -> ReviewResult:
        status = ReviewStatus(str(output.get("status", "failed")))
        result = ReviewResult(
            status=status,
            run_id=str(output.get("run_id") or root.name),
            output_dir=root.resolve(),
            failure_reason=output.get("failure_reason"),
            final_report=output.get("final_report"),
            specialist_reports=dict(output.get("specialist_reports", {})),
            trace_path=ReviewService._existing_trace_path(root),
            last_event_at=ReviewService._last_event_at(root),
        )
        if status is ReviewStatus.FAILED:
            root.mkdir(parents=True, exist_ok=True)
            (root / "failure.json").write_text(
                json.dumps(
                    {
                        "run_id": result.run_id,
                        "status": result.status.value,
                        "failure_reason": result.failure_reason,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        ReviewService._write_execution_status(
            root, status, result.run_id, failure_reason=result.failure_reason
        )
        return result

    @staticmethod
    def _exception_result(root: Path, run_id: str, exc: Exception) -> ReviewResult:
        status = (
            ReviewStatus.RETRYABLE_FAILURE
            if isinstance(exc, RetryableLLMError) or is_retryable_provider_error(exc)
            else ReviewStatus.FAILED
        )
        reason = f"{type(exc).__name__}: {exc}"
        ReviewService._write_execution_status(root, status, run_id, failure_reason=reason)
        if status is ReviewStatus.FAILED:
            ReviewService._atomic_json(
                root / "failure.json",
                {"run_id": run_id, "status": status.value, "failure_reason": reason},
            )
        return ReviewResult(
            status=status,
            run_id=run_id,
            output_dir=root.resolve(),
            failure_reason=reason,
            trace_path=ReviewService._existing_trace_path(root),
            last_event_at=ReviewService._last_event_at(root),
        )

    @staticmethod
    def _write_execution_status(
        root: Path,
        status: ReviewStatus,
        run_id: str,
        *,
        failure_reason: str | None = None,
    ) -> None:
        root.mkdir(parents=True, exist_ok=True)
        if status in {
            ReviewStatus.RUNNING,
            ReviewStatus.INTERRUPTED,
            ReviewStatus.RETRYABLE_FAILURE,
        }:
            # A previous terminal attempt must not override the authoritative
            # status of a later resume attempt.
            (root / "failure.json").unlink(missing_ok=True)
        ReviewService._atomic_json(
            root / "execution_status.json",
            {
                "run_id": run_id,
                "status": status.value,
                "failure_reason": failure_reason,
                "updated_at": datetime.now().astimezone().isoformat(),
            },
        )

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _completed_specialists(root: Path) -> list[str]:
        directory = root / "specialists"
        if not directory.is_dir():
            return []
        return sorted(path.stem for path in directory.glob("*.json") if "." not in path.stem)

    @staticmethod
    def _trace_path(root: Path) -> Path:
        return (root / "telemetry" / "execution_trace.jsonl").resolve()

    @staticmethod
    def _existing_trace_path(root: Path) -> Path | None:
        path = ReviewService._trace_path(root)
        return path if path.is_file() else None

    @staticmethod
    def _last_event_at(root: Path) -> datetime | None:
        path = ReviewService._existing_trace_path(root)
        if path is None:
            return None
        try:
            events = read_trace(path)
        except (OSError, ValueError):
            return None
        return events[-1].timestamp if events else None

    @staticmethod
    def _trace_status(root: Path) -> tuple[Path | None, datetime | None]:
        return ReviewService._existing_trace_path(root), ReviewService._last_event_at(root)
