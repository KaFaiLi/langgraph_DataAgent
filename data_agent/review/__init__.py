"""Evidence-backed review contracts and the general-agent review service."""

from data_agent.review.interface import ReviewRequest

__all__ = [
    "AgentReviewResult",
    "AgentReviewService",
    "ReviewRequest",
]


def __getattr__(name: str):
    if name in {"AgentReviewService", "AgentReviewResult"}:
        from data_agent.review.agent_service import AgentReviewResult, AgentReviewService

        return {"AgentReviewService": AgentReviewService, "AgentReviewResult": AgentReviewResult}[
            name
        ]
    raise AttributeError(name)
