"""Pure graph routing for the bounded specialist loop."""

from __future__ import annotations

from data_agent.review.orchestration.specialist.state import SpecialistState


def route(state: SpecialistState) -> str:
    """Continue pending verification or hand settled findings to omission audit."""
    return "omission_audit" if state.get("loop_status") == "complete" else "react_research"


__all__ = ["route"]
