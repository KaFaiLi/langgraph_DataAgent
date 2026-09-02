from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from data_agent.review import ReviewRequest, ReviewStatus
from data_agent.review.llm.errors import RetryableLLMError
from data_agent.review.service import ReviewService
from data_agent.tracing import read_trace


def test_failed_preflight_is_persisted_and_visible_through_status(
    tmp_path: Path,
) -> None:
    request = ReviewRequest(
        source_root=tmp_path / "missing",
        output_dir=tmp_path / "run",
        run_id="RUN-MISSING",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 12, 31),
        desk_context={
            "desk_name": "Test Desk",
            "business_description": "Fixture",
            "review_start": "2025-01-01",
            "review_end": "2025-12-31",
        },
    )

    result = ReviewService().start(request)

    assert result.status is ReviewStatus.FAILED
    assert "does not exist" in (result.failure_reason or "")
    assert (request.output_dir / "failure.json").is_file()
    assert result.trace_path is not None
    assert result.trace_path.is_file()
    read_trace(result.trace_path)
    status = ReviewService().status(request.output_dir)
    assert status.status is ReviewStatus.FAILED
    assert status.run_id == "RUN-MISSING"
    assert status.trace_path == result.trace_path


def test_interrupted_invocation_persists_resumable_execution_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    request = ReviewRequest(
        source_root=source,
        output_dir=tmp_path / "run",
        run_id="RUN-INTERRUPTED",
        review_start=date(2025, 1, 1),
        review_end=date(2025, 12, 31),
        desk_context={
            "desk_name": "Test Desk",
            "business_description": "Fixture",
            "review_start": "2025-01-01",
            "review_end": "2025-12-31",
        },
    )
    service = ReviewService()

    def interrupt(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        service,
        "_build_graph",
        lambda _checkpointer: SimpleNamespace(invoke=interrupt),
    )

    with pytest.raises(KeyboardInterrupt):
        service.start(request)

    status = service.status(request.output_dir)
    assert status.status is ReviewStatus.INTERRUPTED
    assert status.run_id == request.run_id


def test_new_execution_status_supersedes_stale_failure_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "failure.json").write_text(
        '{"run_id":"RUN-STALE","failure_reason":"old failure"}', encoding="utf-8"
    )

    ReviewService._write_execution_status(run_dir, ReviewStatus.RUNNING, "RUN-STALE")

    assert not (run_dir / "failure.json").exists()
    assert ReviewService().status(run_dir).status is ReviewStatus.RUNNING


def test_typed_llm_failure_is_persisted_as_resumable(tmp_path: Path) -> None:
    original = ConnectionError("provider unavailable")

    result = ReviewService._exception_result(
        tmp_path, "RUN-RETRY", RetryableLLMError("try later", cause=original, attempts=2)
    )

    assert result.status is ReviewStatus.RETRYABLE_FAILURE
    assert ReviewService().status(tmp_path).status is ReviewStatus.RETRYABLE_FAILURE
    assert not (tmp_path / "failure.json").exists()
