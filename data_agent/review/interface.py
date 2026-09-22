"""Public input contract for model-directed reviews."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, model_validator

from data_agent.review.domain.source import DateRange


class ReviewRequest(BaseModel):
    """Everything needed to start one model-directed review run."""

    source_root: Path
    output_dir: Path
    run_id: str
    review_start: date
    review_end: date
    desk_context: dict[str, Any]

    @model_validator(mode="after")
    def _ordered_period(self) -> ReviewRequest:
        DateRange(start=self.review_start, end=self.review_end)
        return self

    @property
    def review_period(self) -> DateRange:
        return DateRange(start=self.review_start, end=self.review_end)
