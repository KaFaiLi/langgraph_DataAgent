"""Review-run and coverage-gate contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from data_agent.review.domain.domains import SpecialistDomain
from data_agent.review.domain.review import (
    CoverageError,
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


def test_full_coverage_passes() -> None:
    run = make_run(coverage=[settled("SRC-001")])
    run.assert_full_coverage()


def test_pending_source_blocks_and_reports_id() -> None:
    run = make_run(coverage=[settled("SRC-001"), SourceCoverage(source_id="SRC-002")])
    with pytest.raises(CoverageError, match="SRC-002"):
        run.assert_full_coverage()


def test_irrelevant_and_unsupported_are_settled() -> None:
    run = make_run(
        coverage=[settled("SRC-001", "irrelevant"), settled("SRC-002", "unsupported")]
    )
    run.assert_full_coverage()


def test_pending_sources_listing() -> None:
    run = make_run(coverage=[settled("SRC-001"), SourceCoverage(source_id="SRC-002")])
    assert [entry.source_id for entry in run.pending_sources()] == ["SRC-002"]


def test_mark_failed_records_reason() -> None:
    run = make_run()
    run.mark_failed("parser error in source/SRC-003")
    assert run.status is RunStatus.FAILED
    assert run.failure_reason == "parser error in source/SRC-003"


def test_review_task_contract() -> None:
    task = ReviewTask(
        task_id="T-1",
        domain=SpecialistDomain.RISK_METRICS,
        source_ids=["SRC-001"],
    )
    assert task.domain is SpecialistDomain.RISK_METRICS


