from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from typer.testing import CliRunner

from data_agent.cli import app
from data_agent.tracing import EventType, ExecutionEvent, JsonlTraceSink, TraceStatus

runner = CliRunner()


def test_unified_cli_exposes_chat_and_review() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "chat" in result.stdout
    assert "review" in result.stdout


def test_chat_passes_one_joined_message_to_agent(monkeypatch) -> None:
    messages: list[str] = []

    class FakeBundle:
        async def ask(self, message: str, **kwargs) -> str:
            del kwargs
            messages.append(message)
            return "answer"

    async def fake_build_agent() -> FakeBundle:
        return FakeBundle()

    monkeypatch.setattr("data_agent.cli.build_agent", fake_build_agent)
    monkeypatch.setattr("data_agent.cli.get_settings", lambda: SimpleNamespace(log_level="WARNING"))

    result = runner.invoke(app, ["chat", "hello", "world"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "answer"
    assert messages == ["hello world"]


def test_chat_renders_tool_trace_to_stderr_without_polluting_answer(monkeypatch) -> None:
    event_values = {
        "timestamp": datetime.now(UTC),
        "logical_run_id": "CHAT-1",
        "attempt_id": uuid4(),
        "callback_run_id": uuid4(),
        "name": "inspect_table",
    }

    class FakeBundle:
        async def ask(self, message: str, *, trace_sinks) -> str:
            del message
            for sink in trace_sinks:
                sink.emit(
                    ExecutionEvent(
                        sequence=1,
                        event_type=EventType.TOOL_STARTED,
                        status=TraceStatus.STARTED,
                        arguments='{"path":"risk.csv"}',
                        **event_values,
                    )
                )
                sink.emit(
                    ExecutionEvent(
                        sequence=2,
                        event_type=EventType.TOOL_SUCCEEDED,
                        status=TraceStatus.SUCCEEDED,
                        duration_ms=12,
                        result_size=20,
                        **event_values,
                    )
                )
            return "answer"

    async def fake_build_agent() -> FakeBundle:
        return FakeBundle()

    monkeypatch.setattr("data_agent.cli.build_agent", fake_build_agent)
    monkeypatch.setattr("data_agent.cli.get_settings", lambda: SimpleNamespace(log_level="WARNING"))

    result = runner.invoke(app, ["chat", "hello"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "answer"
    assert "inspect_table" in result.stderr
    assert "risk.csv" in result.stderr

    quiet = runner.invoke(app, ["chat", "--trace", "off", "hello"])
    assert quiet.exit_code == 0
    assert quiet.stdout.strip() == "answer"
    assert quiet.stderr == ""


def test_review_status_reports_missing_run(tmp_path: Path) -> None:
    result = runner.invoke(app, ["review", "status", str(tmp_path / "missing")])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "not_found"


def test_review_run_persists_preflight_failure(tmp_path: Path) -> None:
    desk = tmp_path / "desk.json"
    desk.write_text(
        json.dumps(
            {
                "desk_name": "Test Desk",
                "business_description": "Fixture",
                "review_start": "2025-01-01",
                "review_end": "2025-12-31",
            }
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "review",
            "run",
            "--source",
            str(tmp_path / "missing-source"),
            "--output",
            str(run_dir),
            "--review-start",
            "2025-01-01",
            "--review-end",
            "2025-12-31",
            "--desk-template",
            str(desk),
            "--run-id",
            "RUN-CLI",
        ],
    )
    assert result.exit_code == 1
    assert (run_dir / "failure.json").is_file()


def test_review_trace_reads_tail_as_json_and_summary(tmp_path: Path) -> None:
    trace_path = tmp_path / "telemetry" / "execution_trace.jsonl"
    sink = JsonlTraceSink(trace_path)
    for sequence, name in enumerate(("first_tool", "second_tool"), start=1):
        sink.emit(
            ExecutionEvent(
                sequence=sequence,
                event_type=EventType.TOOL_STARTED,
                status=TraceStatus.STARTED,
                logical_run_id="RUN-TRACE",
                attempt_id=uuid4(),
                callback_run_id=uuid4(),
                name=name,
            )
        )

    raw = runner.invoke(app, ["review", "trace", str(tmp_path), "--tail", "1", "--json"])
    assert raw.exit_code == 0
    payload = json.loads(raw.stdout)
    assert payload["name"] == "second_tool"

    summary = runner.invoke(app, ["review", "trace", str(tmp_path), "--tail", "1"])
    assert summary.exit_code == 0
    assert "second_tool" in summary.stdout
    assert "first_tool" not in summary.stdout


def test_review_trace_rejects_malformed_event(tmp_path: Path) -> None:
    trace_path = tmp_path / "telemetry" / "execution_trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text("{bad}\n", encoding="utf-8")

    result = runner.invoke(app, ["review", "trace", str(tmp_path)])

    assert result.exit_code == 1
    assert "invalid trace event at line 1" in result.stderr
