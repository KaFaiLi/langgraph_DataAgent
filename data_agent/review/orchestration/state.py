"""Parent-graph state (JSON-friendly primitives for checkpoint compatibility)."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ParentState(TypedDict, total=False):
    """Top-level state of one review run."""

    run_id: str
    source_root: str
    output_dir: str
    review_period: dict[str, str]

    manifest: dict | None
    desk_context: dict | None
    tasks: list[dict]
    active_task: dict
    specialist_outcomes: Annotated[list[dict], operator.add]
    coverage: list[dict]

    specialist_reports: dict[str, dict]
    specialist_markdown: dict[str, str]

    clusters: list[dict]
    contradictions: list[dict]
    final_report: dict | None
    final_markdown: str
    lead_round: int
    lead_feedback: str
    lead_status: str  # "running" | "complete"

    status: str  # "running" | "completed" | "failed"
    failure_reason: str | None

