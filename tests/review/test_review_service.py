"""Preflight failures remain visible without initializing an agent or checkpoint."""

from datetime import date
from pathlib import Path

import pytest

from data_agent.review import AgentReviewService, ReviewRequest


@pytest.mark.asyncio
async def test_failed_preflight_is_persisted_and_visible_through_status(tmp_path: Path) -> None:
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

    async def forbidden_agent(*args, **kwargs):
        pytest.fail("preflight failure must not start an agent")

    service = AgentReviewService(agent_builder=forbidden_agent)
    result = await service.start(request)
    assert result.status == "failed"
    assert result.failure_reason == "preflight_source_error"
    assert (request.output_dir / "failure.json").is_file()
    assert not (request.output_dir / "conversation.sqlite").exists()
    assert service.status(request.output_dir) == result
    assert await service.resume(request.output_dir) == result


@pytest.mark.asyncio
async def test_legacy_checkpoint_is_rejected_without_reading_or_resuming_it(tmp_path):
    checkpoint = tmp_path / "checkpoints.sqlite"
    checkpoint.write_bytes(b"legacy checkpoint must never be deserialized")

    async def forbidden_agent(*args, **kwargs):
        pytest.fail("legacy checkpoint must not start the current agent")

    service = AgentReviewService(agent_builder=forbidden_agent)
    status = service.status(tmp_path)
    assert status.status == "failed" and not status.retryable
    assert status.failure_reason == "legacy_checkpoint_unsupported"
    assert await service.resume(tmp_path) == status
    assert checkpoint.read_bytes() == b"legacy checkpoint must never be deserialized"
    assert not (tmp_path / "conversation.sqlite").exists()
