"""Shared execution tracing interface and adapters."""

from data_agent.tracing.events import EventType, ExecutionEvent, TraceMode, TraceStatus
from data_agent.tracing.handler import ExecutionTraceHandler, render_arguments
from data_agent.tracing.sinks import (
    CompositeTraceSink,
    ConsoleTraceSink,
    InMemoryTraceSink,
    JsonlTraceSink,
    TraceSink,
    follow_trace,
    read_trace,
)

__all__ = [
    "CompositeTraceSink",
    "ConsoleTraceSink",
    "EventType",
    "ExecutionEvent",
    "ExecutionTraceHandler",
    "InMemoryTraceSink",
    "JsonlTraceSink",
    "TraceMode",
    "TraceSink",
    "TraceStatus",
    "follow_trace",
    "read_trace",
    "render_arguments",
]
