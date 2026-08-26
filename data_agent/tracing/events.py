"""Typed, versioned execution events shared by chat and review tracing."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TraceMode(StrEnum):
    """How much execution detail a console adapter renders."""

    OFF = "off"
    SUMMARY = "summary"
    FULL = "full"


class EventType(StrEnum):
    """Normalized lifecycle events emitted by the tracing module."""

    MODEL_STARTED = "model_started"
    MODEL_SUCCEEDED = "model_succeeded"
    MODEL_FAILED = "model_failed"
    NODE_STARTED = "node_started"
    NODE_SUCCEEDED = "node_succeeded"
    NODE_FAILED = "node_failed"
    TOOL_STARTED = "tool_started"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"


class TraceStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExecutionEvent(BaseModel):
    """One strict operational event suitable for console or JSONL adapters."""

    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    sequence: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: EventType
    status: TraceStatus

    logical_run_id: str
    attempt_id: UUID
    callback_run_id: UUID
    parent_callback_run_id: UUID | None = None

    graph: str | None = None
    node: str | None = None
    specialist: str | None = None
    name: str | None = None
    arguments: str | None = None

    duration_ms: float | None = Field(default=None, ge=0)
    result_size: int | None = Field(default=None, ge=0)
    result_sha256: str | None = None
    locator_count: int | None = Field(default=None, ge=0)
    truncated: bool = False
    result_preview: str | None = None

    error_type: str | None = None
    error_message: str | None = None


__all__ = ["EventType", "ExecutionEvent", "TraceMode", "TraceStatus"]
