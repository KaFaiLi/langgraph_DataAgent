"""Checkpoint/resume integration test for the review service (fakes)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from data_agent.review import ReviewRequest, ReviewService, ReviewStatus
from data_agent.review.domain.desk_context import DeskContext
from tests.review.fixtures.builder import make_risky_tree
from tests.review.ported_graph.test_orchestration import (
    DESK_TEMPLATE,
    FakeParentProvider,
)


def _desk() -> DeskContext:
    return DeskContext.model_validate(DESK_TEMPLATE)


def test_resume_returns_checkpointed_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    make_risky_tree(source)
    run_dir = tmp_path / "runs" / "RUN-1"

    provider = FakeParentProvider()
    service = ReviewService(llm_provider=provider)
    first = service.start(
        ReviewRequest(
            source_root=source,
            output_dir=run_dir,
            run_id="RUN-1",
            review_start=date(2025, 1, 1),
            review_end=date(2026, 6, 30),
            desk_context=_desk().model_dump(mode="json"),
        )
    )
    assert first.status is ReviewStatus.COMPLETED, first.failure_reason
    calls_after_first = len(provider.calls)

    resumed = service.resume(run_dir)
    assert resumed.status is ReviewStatus.COMPLETED
    assert resumed.run_id == "RUN-1"
    # Resuming a completed run re-reads the checkpoint without new LLM calls.
    assert len(provider.calls) == calls_after_first
    assert (run_dir / "checkpoints.sqlite").exists()
