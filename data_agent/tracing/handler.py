"""LangChain callback adapter for normalized execution events."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from langchain_core.callbacks import BaseCallbackHandler

from data_agent.tracing.events import EventType, ExecutionEvent, TraceStatus
from data_agent.tracing.sinks import CompositeTraceSink, TraceSink

_SENSITIVE_KEY = re.compile(
    r"(?:api[-_]?key|access[-_]?token|refresh[-_]?token|authorization|cookie|password|secret|token)",
    re.IGNORECASE,
)
_INLINE_SECRET = re.compile(
    r"(?i)\b(api[-_]?key|token|password|secret|authorization|cookie)\b\s*[:=]\s*([^\s,;]+)"
)
_LOCATOR = re.compile(r"source://[^\s\]\[\)\(\"']+")
_ARGUMENT_LIMIT = 500
_DELEGATION_TOOL = "run_subagent"


@dataclass(frozen=True)
class _ActiveRun:
    kind: str
    started: float
    parent_run_id: UUID | None
    graph: str | None
    node: str | None
    specialist: str | None
    name: str | None
    agent_id: str | None
    parent_agent_id: str | None
    agent_name: str | None
    agent_depth: int | None


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else _redact(nested)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _INLINE_SECRET.sub(r"\1=[REDACTED]", value)
    return value


def render_arguments(value: Any, *, limit: int = _ARGUMENT_LIMIT) -> str:
    """Render recursively redacted arguments within a stable character bound."""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    redacted = _redact(value)
    try:
        rendered = json.dumps(redacted, ensure_ascii=False, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        rendered = str(redacted)
    return rendered if len(rendered) <= limit else rendered[:limit] + "…"


def _coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _text_length(value: Any) -> int:
    """Return a length without including the value itself in a trace."""

    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    return len(str(value))


def render_delegation_arguments(value: Any, *, limit: int = _ARGUMENT_LIMIT) -> str:
    """Render only safe identifiers and lengths for a ``run_subagent`` call.

    Delegation task and context text can contain private user data.  They are
    deliberately excluded even when ordinary tool-result previews are enabled.
    """

    value = _coerce_json(value)
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {
            "agent_name": str(value["agent_name"])[:100]
            if value.get("agent_name") is not None
            else None,
            "task_chars": _text_length(value.get("task")),
            "context_chars": _text_length(value.get("context")),
            "input_chars": _text_length(value.get("task")) + _text_length(value.get("context")),
        }
        for key in ("agent_id", "parent_agent_id"):
            if value.get(key) is not None:
                safe[key] = str(value[key])[:100]
    else:
        safe = {"input_chars": _text_length(value)}
    return render_arguments(safe, limit=limit)


def _result_text(output: Any) -> str:
    content = getattr(output, "content", None)
    if content is not None:
        output = content
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, ensure_ascii=False, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(output)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_depth(value: Any) -> int | None:
    if value is None:
        return None
    try:
        depth = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return depth if depth >= 0 else None


def _metadata(
    metadata: Mapping[str, Any] | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    int | None,
]:
    metadata = metadata or {}
    return (
        _optional_str(metadata.get("data_agent_graph") or metadata.get("risk_agent_graph")),
        metadata.get("langgraph_node"),
        _optional_str(metadata.get("risk_agent_specialist")),
        _optional_str(metadata.get("data_agent_id")),
        _optional_str(metadata.get("data_agent_parent_id")),
        _optional_str(metadata.get("data_agent_name")),
        _optional_depth(metadata.get("data_agent_depth")),
    )


def _is_delegation_tool(name: str | None) -> bool:
    return bool(name) and name.rsplit(".", 1)[-1].lower() == _DELEGATION_TOOL


def _serialized_name(serialized: dict[str, Any] | None, fallback: str | None = None) -> str | None:
    serialized = serialized or {}
    identifier = serialized.get("id")
    identifier_name = identifier[-1] if isinstance(identifier, list) and identifier else None
    return serialized.get("name") or identifier_name or fallback


class ExecutionTraceHandler(BaseCallbackHandler):
    """Translate callback activity into one ordered execution-event stream."""

    def __init__(
        self,
        logical_run_id: str,
        sinks: Sequence[TraceSink],
        *,
        attempt_id: UUID | None = None,
        result_preview_chars: int = 0,
    ) -> None:
        if not 0 <= result_preview_chars <= 4000:
            raise ValueError("result_preview_chars must be between 0 and 4000")
        self.logical_run_id = logical_run_id
        self.attempt_id = attempt_id or uuid4()
        self.result_preview_chars = result_preview_chars
        self._sink = CompositeTraceSink(sinks)
        self._lock = threading.Lock()
        self._emit_lock = threading.Lock()
        self._sequence = 0
        self._active: dict[UUID, _ActiveRun] = {}

    def _emit(self, **values: Any) -> None:
        with self._emit_lock:
            self._sequence += 1
            event = ExecutionEvent(
                sequence=self._sequence,
                logical_run_id=self.logical_run_id,
                attempt_id=self.attempt_id,
                **values,
            )
            self._sink.emit(event)

    def _start(
        self,
        *,
        kind: str,
        event_type: EventType,
        run_id: UUID,
        parent_run_id: UUID | None,
        metadata: Mapping[str, Any] | None,
        name: str | None,
        arguments: str | None = None,
    ) -> None:
        graph, node, specialist, agent_id, parent_agent_id, agent_name, agent_depth = _metadata(
            metadata
        )
        active = _ActiveRun(
            kind=kind,
            started=time.monotonic(),
            parent_run_id=parent_run_id,
            graph=graph,
            node=node,
            specialist=specialist,
            name=name,
            agent_id=agent_id,
            parent_agent_id=parent_agent_id,
            agent_name=agent_name,
            agent_depth=agent_depth,
        )
        with self._lock:
            # A callback manager can propagate the same lifecycle start more
            # than once.  Keep one active record so one logical callback run
            # cannot produce duplicate start events or mismatched durations.
            if run_id in self._active:
                return
            self._active[run_id] = active
        self._emit(
            event_type=event_type,
            status=TraceStatus.STARTED,
            callback_run_id=run_id,
            parent_callback_run_id=parent_run_id,
            graph=graph,
            node=node,
            specialist=specialist,
            name=name,
            agent_id=agent_id,
            parent_agent_id=parent_agent_id,
            agent_name=agent_name,
            agent_depth=agent_depth,
            arguments=arguments,
        )

    def _finish(
        self,
        run_id: UUID,
        *,
        success_type: EventType,
        failure_type: EventType,
        error: BaseException | None = None,
        output: Any = None,
    ) -> None:
        with self._lock:
            active = self._active.pop(run_id, None)
        if active is None:
            return
        values: dict[str, Any] = {
            "event_type": failure_type if error else success_type,
            "status": TraceStatus.FAILED if error else TraceStatus.SUCCEEDED,
            "callback_run_id": run_id,
            "parent_callback_run_id": active.parent_run_id,
            "graph": active.graph,
            "node": active.node,
            "specialist": active.specialist,
            "name": active.name,
            "agent_id": active.agent_id,
            "parent_agent_id": active.parent_agent_id,
            "agent_name": active.agent_name,
            "agent_depth": active.agent_depth,
            "duration_ms": max(0.0, (time.monotonic() - active.started) * 1000),
        }
        if error is not None:
            if active.kind == "tool" and _is_delegation_tool(active.name):
                # ToolMessage errors can echo the delegated prompt or child
                # result.  Keep the failure type while dropping its body.
                message = f"{active.name or _DELEGATION_TOOL} failed"
            elif active.agent_depth is not None and active.agent_depth > 0:
                # Child model/provider and node exceptions can echo the private
                # delegated prompt.  Preserve the type for diagnosis without
                # retaining provider-controlled error text.
                message = f"{active.kind} failed ({type(error).__name__})"
            else:
                message = str(_redact(str(error)))
            values.update(
                error_type=type(error).__name__,
                error_message=message[:_ARGUMENT_LIMIT]
                + ("…" if len(message) > _ARGUMENT_LIMIT else ""),
            )
        elif active.kind == "tool":
            raw = _result_text(output)
            preview = _redact(raw)
            preview = str(preview)
            limit = self.result_preview_chars
            values.update(
                result_size=len(raw),
                result_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                locator_count=len(set(_LOCATOR.findall(raw))),
                truncated=len(raw) > limit,
                result_preview=preview[:limit] if limit else None,
            )
        self._emit(**values)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = _serialized_name(serialized, kwargs.get("name"))
        tool_input = inputs if inputs is not None else input_str
        arguments = (
            render_delegation_arguments(tool_input)
            if _is_delegation_tool(tool_name)
            else render_arguments(tool_input)
        )
        self._start(
            kind="tool",
            event_type=EventType.TOOL_STARTED,
            run_id=run_id,
            parent_run_id=parent_run_id,
            metadata=metadata,
            name=tool_name,
            arguments=arguments,
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        status = getattr(output, "status", None)
        if status is None and isinstance(output, Mapping):
            status = output.get("status")
        if status == "error":
            self._finish(
                run_id,
                success_type=EventType.TOOL_SUCCEEDED,
                failure_type=EventType.TOOL_FAILED,
                error=RuntimeError(_result_text(output)),
            )
            return
        self._finish(
            run_id,
            success_type=EventType.TOOL_SUCCEEDED,
            failure_type=EventType.TOOL_FAILED,
            output=output,
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(
            run_id,
            success_type=EventType.TOOL_SUCCEEDED,
            failure_type=EventType.TOOL_FAILED,
            error=error,
        )

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del prompts
        self._start(
            kind="model",
            event_type=EventType.MODEL_STARTED,
            run_id=run_id,
            parent_run_id=parent_run_id,
            metadata=metadata,
            name=_serialized_name(serialized, kwargs.get("name")),
        )

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(
            run_id,
            success_type=EventType.MODEL_SUCCEEDED,
            failure_type=EventType.MODEL_FAILED,
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(
            run_id,
            success_type=EventType.MODEL_SUCCEEDED,
            failure_type=EventType.MODEL_FAILED,
            error=error,
        )

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del inputs
        _, node, _, _, _, _, _ = _metadata(metadata)
        name = _serialized_name(serialized, kwargs.get("name"))
        if not node or name != node:
            return
        self._start(
            kind="node",
            event_type=EventType.NODE_STARTED,
            run_id=run_id,
            parent_run_id=parent_run_id,
            metadata=metadata,
            name=name,
        )

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        del outputs
        self._finish(
            run_id,
            success_type=EventType.NODE_SUCCEEDED,
            failure_type=EventType.NODE_FAILED,
        )

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(
            run_id,
            success_type=EventType.NODE_SUCCEEDED,
            failure_type=EventType.NODE_FAILED,
            error=error,
        )


__all__ = ["ExecutionTraceHandler", "render_arguments", "render_delegation_arguments"]
