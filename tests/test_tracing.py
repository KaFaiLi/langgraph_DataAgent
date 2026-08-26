from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from data_agent.config import Settings
from data_agent.tracing import (
    ConsoleTraceSink,
    EventType,
    ExecutionEvent,
    ExecutionTraceHandler,
    InMemoryTraceSink,
    JsonlTraceSink,
    TraceMode,
    TraceStatus,
    read_trace,
)


def test_handler_correlates_and_redacts_tool_lifecycle() -> None:
    sink = InMemoryTraceSink()
    handler = ExecutionTraceHandler("RUN-1", [sink], result_preview_chars=40)
    run_id = uuid4()
    parent_id = uuid4()

    handler.on_tool_start(
        {"name": "read_rows"},
        "",
        run_id=run_id,
        parent_run_id=parent_id,
        metadata={
            "risk_agent_graph": "specialist:risk_metrics",
            "langgraph_node": "react_research",
            "risk_agent_specialist": "risk_metrics",
        },
        inputs={"path": "risk.csv", "api_key": "secret", "nested": {"token": "value"}},
    )
    handler.on_tool_end(
        "token=hidden source://risk.csv#rows=1:2 and more content",
        run_id=run_id,
    )

    started, completed = sink.events
    assert [started.sequence, completed.sequence] == [1, 2]
    assert started.parent_callback_run_id == parent_id
    assert started.graph == "specialist:risk_metrics"
    assert started.node == "react_research"
    assert started.specialist == "risk_metrics"
    assert "secret" not in (started.arguments or "")
    assert "value" not in (started.arguments or "")
    assert completed.event_type is EventType.TOOL_SUCCEEDED
    assert completed.duration_ms is not None
    assert completed.locator_count == 1
    assert completed.result_sha256
    assert "hidden" not in (completed.result_preview or "")
    assert completed.truncated is True


def test_handler_records_tool_error() -> None:
    sink = InMemoryTraceSink()
    handler = ExecutionTraceHandler("RUN-ERROR", [sink])
    run_id = uuid4()

    handler.on_tool_start(
        {"name": "inspect_table"},
        '{"api_key":"hidden","path":"risk.csv"}',
        run_id=run_id,
    )
    handler.on_tool_error(ValueError("bad input token=hidden"), run_id=run_id)

    started = sink.events[0]
    failed = sink.events[-1]
    assert "hidden" not in (started.arguments or "")
    assert failed.event_type is EventType.TOOL_FAILED
    assert failed.status is TraceStatus.FAILED
    assert failed.error_type == "ValueError"
    assert failed.error_message == "bad input token=[REDACTED]"


def _event(sequence: int) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=sequence,
        timestamp=datetime.now(UTC),
        event_type=EventType.TOOL_STARTED,
        status=TraceStatus.STARTED,
        logical_run_id="RUN-CONCURRENT",
        attempt_id=uuid4(),
        callback_run_id=uuid4(),
        name=f"tool_{sequence}",
    )


def test_jsonl_sink_is_thread_safe_and_strict(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    sink = JsonlTraceSink(path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda number: sink.emit(_event(number)), range(1, 51)))

    events = read_trace(path)
    assert len(events) == 50
    assert len({event.event_id for event in events}) == 50

    path.write_text(path.read_text(encoding="utf-8") + "{bad}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 51"):
        read_trace(path)


def test_console_modes_keep_summary_bounded() -> None:
    event = _event(1).model_copy(
        update={
            "event_type": EventType.TOOL_SUCCEEDED,
            "status": TraceStatus.SUCCEEDED,
            "duration_ms": 12.0,
            "result_size": 500,
            "result_sha256": "a" * 64,
            "truncated": True,
            "result_preview": "SENSITIVE_PAYLOAD",
        }
    )
    summary_stream = io.StringIO()
    ConsoleTraceSink(TraceMode.SUMMARY, stream=summary_stream).emit(event)
    assert "SENSITIVE_PAYLOAD" not in summary_stream.getvalue()
    assert "500 chars" in summary_stream.getvalue()

    full_stream = io.StringIO()
    ConsoleTraceSink(TraceMode.FULL, stream=full_stream).emit(event)
    assert "SENSITIVE_PAYLOAD" in full_stream.getvalue()

    off_stream = io.StringIO()
    ConsoleTraceSink(TraceMode.OFF, stream=off_stream).emit(event)
    assert off_stream.getvalue() == ""


def test_jsonl_sink_can_omit_captured_preview(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    sink = JsonlTraceSink(path, include_preview=False)
    event = _event(1).model_copy(update={"result_preview": "source content"})

    sink.emit(event)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["result_preview"] is None


def test_trace_preview_setting_is_safely_bounded() -> None:
    assert Settings(trace_result_preview_chars=0).trace_result_preview_chars == 0
    assert Settings(trace_result_preview_chars=4_000).trace_result_preview_chars == 4_000
    with pytest.raises(ValidationError):
        Settings(trace_result_preview_chars=4_001)
