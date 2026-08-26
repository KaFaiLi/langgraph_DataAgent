"""Trace adapters for terminals, durable JSONL, and tests."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Protocol, TextIO

from pydantic import ValidationError

from data_agent.tracing.events import EventType, ExecutionEvent, TraceMode


class TraceSink(Protocol):
    """Small interface implemented by every trace destination."""

    def emit(self, event: ExecutionEvent) -> None: ...


class CompositeTraceSink:
    """Fan one normalized event out to several adapters."""

    def __init__(self, sinks: Sequence[TraceSink]) -> None:
        self._sinks = tuple(sinks)

    def emit(self, event: ExecutionEvent) -> None:
        for sink in self._sinks:
            sink.emit(event)


class InMemoryTraceSink:
    """Thread-safe adapter used by tests and embedding callers."""

    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []
        self._lock = threading.Lock()

    def emit(self, event: ExecutionEvent) -> None:
        with self._lock:
            self.events.append(event)


class JsonlTraceSink:
    """Append complete, validated events as independently durable JSON lines."""

    def __init__(self, path: str | Path, *, include_preview: bool = True) -> None:
        self.path = Path(path)
        self.include_preview = include_preview
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: ExecutionEvent) -> None:
        payload = event.model_dump(mode="json")
        if not self.include_preview:
            payload["result_preview"] = None
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())


class ConsoleTraceSink:
    """Render concise tool activity and optional review-node progress."""

    def __init__(
        self,
        mode: TraceMode = TraceMode.SUMMARY,
        *,
        stream: TextIO | None = None,
        show_nodes: bool = False,
        show_models: bool = False,
    ) -> None:
        self.mode = mode
        self.stream = stream or sys.stderr
        self.show_nodes = show_nodes
        self.show_models = show_models
        self._lock = threading.Lock()

    def emit(self, event: ExecutionEvent) -> None:
        rendered = self.render(event)
        if rendered is None:
            return
        with self._lock:
            print(rendered, file=self.stream, flush=True)

    def render(self, event: ExecutionEvent) -> str | None:
        if self.mode is TraceMode.OFF:
            return None
        if event.event_type.value.startswith("tool_"):
            return self._render_tool(event)
        if event.event_type.value.startswith("node_") and self.show_nodes:
            return self._render_node(event)
        if event.event_type.value.startswith("model_") and self.show_models:
            return self._render_model(event)
        return None

    def _render_tool(self, event: ExecutionEvent) -> str:
        name = event.name or "unknown_tool"
        if event.event_type is EventType.TOOL_STARTED:
            arguments = f" {event.arguments}" if event.arguments else ""
            return f"→ {name}{arguments}"
        duration = _duration(event.duration_ms)
        if event.event_type is EventType.TOOL_FAILED:
            detail = event.error_message or event.error_type or "unknown error"
            return f"✗ {name}{duration} · {detail}"
        facts: list[str] = []
        if event.result_size is not None:
            facts.append(f"{event.result_size} chars")
        if event.locator_count:
            facts.append(f"{event.locator_count} locator(s)")
        if event.result_sha256:
            facts.append(f"sha256={event.result_sha256[:10]}")
        if event.result_preview is not None and event.truncated:
            facts.append("preview truncated")
        rendered = f"✓ {name}{duration}"
        if facts:
            rendered += " · " + " · ".join(facts)
        if self.mode is TraceMode.FULL and event.result_preview:
            rendered += f"\n  {event.result_preview}"
        return rendered

    @staticmethod
    def _render_node(event: ExecutionEvent) -> str:
        label = "/".join(part for part in (event.graph, event.node) if part) or "node"
        if event.event_type is EventType.NODE_STARTED:
            return f"[review] {label} started"
        if event.event_type is EventType.NODE_FAILED:
            return f"[review] {label} failed · {event.error_message or 'unknown error'}"
        return f"[review] {label} completed{_duration(event.duration_ms)}"

    @staticmethod
    def _render_model(event: ExecutionEvent) -> str:
        name = event.name or "model"
        if event.event_type is EventType.MODEL_STARTED:
            return f"[model] {name} started"
        if event.event_type is EventType.MODEL_FAILED:
            return f"[model] {name} failed · {event.error_message or 'unknown error'}"
        return f"[model] {name} completed{_duration(event.duration_ms)}"


def _duration(value: float | None) -> str:
    return f" {value:.0f} ms" if value is not None else ""


def read_trace(path: str | Path) -> list[ExecutionEvent]:
    """Load and strictly validate one complete JSONL trace."""

    trace_path = Path(path)
    events: list[ExecutionEvent] = []
    with trace_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                events.append(ExecutionEvent.model_validate_json(line))
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"invalid trace event at line {line_number}: {exc}") from exc
    return events


def follow_trace(
    path: str | Path,
    *,
    tail: int = 50,
    poll_interval: float = 0.2,
) -> Iterator[ExecutionEvent]:
    """Yield a validated tail, then events appended to the same open trace."""

    if tail < 0:
        raise ValueError("tail must be >= 0")
    trace_path = Path(path)
    with trace_path.open(encoding="utf-8") as handle:
        existing: list[ExecutionEvent] = []
        line_number = 0
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                existing.append(ExecutionEvent.model_validate_json(line))
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"invalid trace event at line {line_number}: {exc}") from exc
        yield from (existing[-tail:] if tail else existing)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(poll_interval)
                continue
            line_number += 1
            try:
                yield ExecutionEvent.model_validate_json(line)
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"invalid trace event at line {line_number}: {exc}") from exc


__all__ = [
    "CompositeTraceSink",
    "ConsoleTraceSink",
    "InMemoryTraceSink",
    "JsonlTraceSink",
    "TraceSink",
    "follow_trace",
    "read_trace",
]
