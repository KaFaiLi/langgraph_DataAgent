"""Preflight: validate inputs and prepare the run layout. Fails loudly (spec 41)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.source import DateRange
from data_agent.review.orchestration.state import ParentState


def preflight(state: ParentState, config: RunnableConfig) -> dict:
    """Validate the source root and create the output layout."""
    source_root = Path(state["source_root"])
    output_dir = Path(state["output_dir"])
    run_id = state.get("run_id") or _new_run_id()

    if not source_root.is_dir():
        return {
            "run_id": run_id,
            "status": "failed",
            "failure_reason": f"source root does not exist: {source_root}",
        }

    period = _review_period(config)
    if period is None:
        return {
            "run_id": run_id,
            "status": "failed",
            "failure_reason": (
                "no review period configured: pass config['configurable']"
                "['review_period'] as a DateRange"
            ),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "specialists").mkdir(exist_ok=True)
    (output_dir / "workspace").mkdir(exist_ok=True)
    (output_dir / "telemetry").mkdir(exist_ok=True)

    return {
        "run_id": run_id,
        "review_period": {
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
        },
        "status": "running",
        "failure_reason": None,
    }


def _review_period(config: RunnableConfig) -> DateRange | None:
    period = (config or {}).get("configurable", {}).get("review_period")
    if isinstance(period, DateRange):
        return period
    if isinstance(period, dict):
        try:
            return DateRange(start=period["start"], end=period["end"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"RUN-{stamp}"
