"""Review-run persistence contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.review import (
    ReviewRun,
    ReviewTask,
    RunStatus,
    SourceCoverage,
)
from data_agent.review.domain.source import Source, SourceManifest, SourceType


def make_run(coverage: list[SourceCoverage] | None = None) -> ReviewRun:
    source = Source(
        source_id="SRC-001",
        path="risk.xlsx",
        source_type=SourceType.XLSX,
        sha256="a" * 64,
        size_bytes=10,
    )
    return ReviewRun(
        run_id="RUN-1",
        status=RunStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_root="./source",
        output_dir="./runs/RUN-1",
        manifest=SourceManifest(sources=[source]),
        coverage=coverage or [],
    )


def settled(source_id: str, status: str = "reviewed") -> SourceCoverage:
    return SourceCoverage(
        source_id=source_id,
        required_reviewers=["risk_metrics"],
        completed_reviewers=["risk_metrics"],
        status=status,  # type: ignore[arg-type]
    )


def test_review_run_round_trips_persisted_coverage() -> None:
    run = make_run(coverage=[settled("SRC-001")])
    restored = ReviewRun.model_validate(run.model_dump(mode="json"))
    assert restored.coverage[0].status == "reviewed"
    assert restored.status is RunStatus.COMPLETED


def test_review_task_contract() -> None:
    task = ReviewTask(
        task_id="T-1",
        domain=SpecialistDomain.RISK_METRICS,
        source_ids=["SRC-001"],
    )
    assert task.domain is SpecialistDomain.RISK_METRICS
