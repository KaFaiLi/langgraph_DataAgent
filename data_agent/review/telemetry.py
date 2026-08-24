"""Bounded JSONL telemetry for review-model calls."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from data_agent.config import get_settings

_START_TIMES: dict[str, float] = {}
_LOCK = threading.Lock()


def _model_id(serialized: dict[str, Any]) -> str:
    values = [serialized.get("kwargs", {})]
    bound = values[0].get("bound")
    if isinstance(bound, dict):
        values.append(bound.get("kwargs", {}))
    for kwargs in values:
        for key in ("model", "model_name"):
            if isinstance(kwargs.get(key), str):
                return kwargs[key]
    return "unknown"


def _tier(model_id: str) -> str:
    settings = get_settings()
    if model_id in {
        settings.socgenai_low_cost_model,
        settings.deepseek_low_cost_model,
    }:
        return "low_cost"
    if model_id in {
        settings.socgenai_high_cost_model,
        settings.deepseek_high_cost_model,
    }:
        return "high_cost"
    return "unknown"


class ReviewTelemetryHandler(BaseCallbackHandler):
    """Append invocation metadata and token counts without prompt/source content."""

    def __init__(self, log_path: str | Path) -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict[str, object]) -> None:
        with _LOCK, self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id)
        with _LOCK:
            _START_TIMES[key] = time.monotonic()
        model_id = _model_id(serialized)
        metadata = metadata or {}
        self._append(
            {
                "event": "llm_start",
                "run_id": key,
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "node": metadata.get("langgraph_node"),
                "graph": metadata.get("risk_agent_graph"),
                "specialist": metadata.get("risk_agent_specialist"),
                "model_id": model_id,
                "tier": _tier(model_id),
                "start_time": time.time(),
            }
        )

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        key = str(run_id)
        with _LOCK:
            start = _START_TIMES.pop(key, None)
        usage: dict[str, int] = {}
        for generations in response.generations:
            for generation in generations:
                if isinstance(generation, ChatGeneration) and isinstance(generation.message, AIMessage):
                    usage = dict(generation.message.usage_metadata or {})
                    break
        self._append(
            {
                "event": "llm_end",
                "run_id": key,
                "duration_seconds": round(time.monotonic() - start, 3) if start else None,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "success": True,
            }
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        key = str(run_id)
        with _LOCK:
            start = _START_TIMES.pop(key, None)
        self._append(
            {
                "event": "llm_error",
                "run_id": key,
                "duration_seconds": round(time.monotonic() - start, 3) if start else None,
                "error": f"{type(error).__name__}: {error}",
                "success": False,
            }
        )
