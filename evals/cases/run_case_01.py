"""Run case 01 through the checkpointed controlled-review pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from data_agent.review.domain.review import RunContext
from data_agent.review.interface import ReviewRequest
from data_agent.review.service import ReviewService


class _EvaluationReviewService(ReviewService):
    def __init__(self, *, max_concurrency: int) -> None:
        super().__init__()
        self.max_concurrency = max_concurrency

    def _config(self, context: RunContext, root: Path) -> dict:
        config = super()._config(context, root)
        config["max_concurrency"] = self.max_concurrency
        return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-concurrency", type=int, default=1)
    args = parser.parse_args()
    if args.max_concurrency < 1:
        parser.error("--max-concurrency must be at least 1")

    case_root = Path(__file__).resolve().parent / "case_01"
    desk_context = json.loads(
        (case_root / "desk_context.json").read_text(encoding="utf-8")
    )
    result = _EvaluationReviewService(max_concurrency=args.max_concurrency).start(
        ReviewRequest(
            source_root=case_root / "source",
            output_dir=args.output,
            run_id=args.run_id,
            review_start=date(2025, 7, 1),
            review_end=date(2026, 6, 30),
            desk_context=desk_context,
        )
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
