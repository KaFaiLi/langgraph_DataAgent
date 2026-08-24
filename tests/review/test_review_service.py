from __future__ import annotations

from datetime import date
from pathlib import Path

from data_agent.review import ReviewRequest, ReviewStatus
from data_agent.review.service import ReviewService


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
    status = ReviewService().status(request.output_dir)
    assert status.status is ReviewStatus.FAILED
    assert status.run_id == "RUN-MISSING"
