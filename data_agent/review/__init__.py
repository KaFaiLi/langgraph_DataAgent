"""Controlled, evidence-backed risk review workflow."""

from data_agent.review.interface import (
    ReviewRequest,
    ReviewResult,
    ReviewRunStatus,
    ReviewStatus,
)

__all__ = [
    "ReviewRequest",
    "ReviewResult",
    "ReviewRunStatus",
    "ReviewService",
    "ReviewStatus",
]


def __getattr__(name: str) -> object:
    """Keep the service API lazy so domain imports cannot re-enter the skill registry."""
    if name == "ReviewService":
        from data_agent.review.service import ReviewService

        return ReviewService
    raise AttributeError(name)
