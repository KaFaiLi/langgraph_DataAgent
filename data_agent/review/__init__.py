"""Evidence-backed review contracts; workflow construction is explicitly opt-in."""

from data_agent.review.interface import ReviewRequest, ReviewResult, ReviewRunStatus, ReviewStatus

__all__ = ["ReviewRequest", "ReviewResult", "ReviewRunStatus", "ReviewService", "ReviewStatus"]


def __getattr__(name: str):
    if name == "ReviewService":
        from data_agent.review.service import ReviewService

        return ReviewService
    raise AttributeError(name)
