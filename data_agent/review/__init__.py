"""Evidence-backed review contracts; workflow construction is explicitly opt-in."""

from data_agent.review.interface import ReviewRequest, ReviewResult, ReviewRunStatus, ReviewStatus

__all__ = [
    "AgentReviewResult",
    "AgentReviewService",
    "ReviewRequest",
    "ReviewResult",
    "ReviewRunStatus",
    "ReviewService",
    "ReviewStatus",
]


def __getattr__(name: str):
    if name in {"AgentReviewService", "AgentReviewResult"}:
        from data_agent.review.agent_service import AgentReviewResult, AgentReviewService

        return {"AgentReviewService": AgentReviewService, "AgentReviewResult": AgentReviewResult}[
            name
        ]
    if name == "ReviewService":
        from data_agent.review.service import ReviewService

        return ReviewService
    raise AttributeError(name)
