"""Checkpoint/resume integration test for the review service (fakes)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tests.review.fixtures.builder import make_risky_tree
from tests.review.ported_graph.test_orchestration import DESK_TEMPLATE, FakeParentProvider

from data_agent.review.application.review_service import ReviewService
from data_agent.review.domain.desk_context import DeskContext
from data_agent.review.domain.source import DateRange


def _desk() -> DeskContext:
    return DeskContext.model_validate(DESK_TEMPLATE)


def test_resume_returns_checkpointed_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    make_risky_tree(source)
    run_dir = tmp_path / "runs" / "RUN-1"

    provider = FakeParentProvider()
    service = ReviewService(llm_provider=provider)
    first = service.run(
        source=str(source),
        output_dir=str(run_dir),
        run_id="RUN-1",
        desk_template=_desk(),
        review_period=DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30)),
    )
    assert first.get("status") == "completed", first.get("failure_reason")
    calls_after_first = len(provider.calls)

    resumed = service.run(
        source=str(source),
        output_dir=str(run_dir),
        run_id="RUN-1",
        desk_template=_desk(),
        review_period=DateRange(start=date(2025, 1, 1), end=date(2026, 6, 30)),
        resume=True,
    )
    assert resumed.get("status") == "completed"
    assert resumed["run_id"] == "RUN-1"
    # Resuming a completed run re-reads the checkpoint without new LLM calls.
    assert len(provider.calls) == calls_after_first
    assert (run_dir / "checkpoints.sqlite").exists()


