"""Public review interface over the checkpointed parent graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_agent.review.application.review_service import ReviewService as _GraphReviewService
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.interface import (
    ReviewRequest,
    ReviewResult,
    ReviewRunStatus,
    ReviewStatus,
)
from data_agent.review.llm import DEFAULT_LLM_PROVIDER, ReviewLLMProvider
from data_agent.review.telemetry import ReviewTelemetryHandler


class ReviewService:
    """Start, resume, and inspect controlled reviews through one interface."""

    def __init__(self, llm_provider: ReviewLLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or DEFAULT_LLM_PROVIDER

    def start(
        self,
        request: ReviewRequest,
        llm_provider: ReviewLLMProvider | None = None,
    ) -> ReviewResult:
        provider = llm_provider or self.llm_provider
        graph_service = _GraphReviewService(
            llm_provider=provider,
            callbacks=[ReviewTelemetryHandler(request.output_dir / "telemetry" / "llm_usage.jsonl")],
        )
        output = graph_service.start(
            source=request.source_root,
            output_dir=request.output_dir,
            run_id=request.run_id,
            desk_template=DeskContext.model_validate(request.desk_context),
            review_period=request.review_period,
        )
        return self._result(output, request.output_dir)

    def resume(
        self,
        run_dir: str | Path,
        llm_provider: ReviewLLMProvider | None = None,
    ) -> ReviewResult:
        root = Path(run_dir).resolve()
        provider = llm_provider or self.llm_provider
        output = _GraphReviewService(
            llm_provider=provider,
            callbacks=[ReviewTelemetryHandler(root / "telemetry" / "llm_usage.jsonl")],
        ).resume(root)
        return self._result(output, root)

    def status(self, run_dir: str | Path) -> ReviewRunStatus:
        root = Path(run_dir).resolve()
        completed = root / "run_manifest.json"
        failure = root / "failure.json"
        context = self._read_json(root / "run_context.json")
        run_id = str(context.get("run_id") or root.name)
        if completed.is_file():
            manifest = self._read_json(completed)
            return ReviewRunStatus(
                status=ReviewStatus.COMPLETED,
                run_id=str(manifest.get("run_id") or run_id),
                output_dir=root,
                completed_specialists=self._completed_specialists(root),
            )
        if failure.is_file():
            data = self._read_json(failure)
            return ReviewRunStatus(
                status=ReviewStatus.FAILED,
                run_id=str(data.get("run_id") or run_id),
                output_dir=root,
                failure_reason=data.get("failure_reason"),
                completed_specialists=self._completed_specialists(root),
            )
        return ReviewRunStatus(
            status=(ReviewStatus.RUNNING if root.is_dir() else ReviewStatus.NOT_FOUND),
            run_id=run_id,
            output_dir=root,
            completed_specialists=self._completed_specialists(root),
        )

    def _result(self, output: dict[str, Any], root: Path) -> ReviewResult:
        status = ReviewStatus(str(output.get("status", "failed")))
        result = ReviewResult(
            status=status,
            run_id=str(output.get("run_id") or root.name),
            output_dir=root.resolve(),
            failure_reason=output.get("failure_reason"),
            final_report=output.get("final_report"),
            specialist_reports=dict(output.get("specialist_reports", {})),
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
        return result

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
        return sorted(path.stem for path in directory.glob("*.json") if ".verification" not in path.name)
