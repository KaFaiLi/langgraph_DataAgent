"""Single command-line interface for DataAgent chat and controlled reviews."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import typer

from data_agent.agent.react_agent import build_agent
from data_agent.config import get_settings
from data_agent.logging_utils import setup_logging
from data_agent.review.interface import ReviewRequest, ReviewStatus
from data_agent.review.service import ReviewService
from data_agent.tracing import ConsoleTraceSink, TraceMode, follow_trace, read_trace

app = typer.Typer(no_args_is_help=True, help="Chat with DataAgent or run a controlled review.")
review_app = typer.Typer(no_args_is_help=True, help="Run, resume, and inspect controlled reviews.")
app.add_typer(review_app, name="review")


def _console_sink(mode: TraceMode, *, review: bool = False) -> ConsoleTraceSink:
    return ConsoleTraceSink(mode, show_nodes=review)


async def _chat_once(message: str, trace_mode: TraceMode) -> None:
    bundle = await build_agent()
    typer.echo(await bundle.ask(message, trace_sinks=[_console_sink(trace_mode)]))


async def _chat_repl(trace_mode: TraceMode) -> None:
    bundle = await build_agent()
    typer.echo(
        f"Connected. {len(bundle.mcp_tools)} MCP tool(s), "
        f"{len(bundle.skills)} skill(s). Type 'exit' to quit.\n"
    )
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo()
            return
        if message.lower() in {"exit", "quit"}:
            return
        if not message:
            continue
        answer = await bundle.ask(message, trace_sinks=[_console_sink(trace_mode)])
        typer.echo(f"agent> {answer}\n")


@app.command("chat")
def chat(
    message: list[str] | None = typer.Argument(None),  # noqa: B008
    trace_mode: TraceMode = typer.Option(TraceMode.SUMMARY, "--trace"),  # noqa: B008
) -> None:
    """Send one message, or start an interactive session when MESSAGE is omitted."""
    setup_logging(get_settings().log_level)
    if message:
        asyncio.run(_chat_once(" ".join(message), trace_mode))
    else:
        asyncio.run(_chat_repl(trace_mode))


def _json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    typer.echo(json.dumps(value, indent=2, default=str))


def _date(value: str, option: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("expected YYYY-MM-DD", param_hint=option) from exc


@review_app.command("run")
def run_review(
    source: Path = typer.Option(..., exists=False, file_okay=False),  # noqa: B008 - Typer parameter declaration
    output: Path = typer.Option(..., file_okay=False),  # noqa: B008 - Typer parameter declaration
    review_start: str = typer.Option(...),
    review_end: str = typer.Option(...),
    desk_template: Path = typer.Option(..., exists=True, dir_okay=False),  # noqa: B008 - Typer parameter declaration
    run_id: str | None = typer.Option(None),
    trace_mode: TraceMode = typer.Option(TraceMode.SUMMARY, "--trace"),  # noqa: B008
) -> None:
    """Start one checkpointed review."""
    start_date = _date(review_start, "--review-start")
    end_date = _date(review_end, "--review-end")
    if start_date > end_date:
        raise typer.BadParameter("review start must not be after review end")
    try:
        desk = json.loads(desk_template.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"invalid desk template JSON: {exc}") from exc
    if not isinstance(desk, dict):
        raise typer.BadParameter("desk template must contain one JSON object")
    for key, expected in (("review_start", start_date), ("review_end", end_date)):
        existing = desk.get(key)
        if existing is not None and str(existing) != expected.isoformat():
            raise typer.BadParameter(f"desk template {key} differs from CLI review period")
        desk[key] = expected.isoformat()
    identifier = run_id or datetime.now(UTC).strftime("RUN-%Y%m%dT%H%M%SZ")
    result = ReviewService(trace_sinks=[_console_sink(trace_mode, review=True)]).start(
        ReviewRequest(
            source_root=source,
            output_dir=output,
            run_id=identifier,
            review_start=start_date,
            review_end=end_date,
            desk_context=desk,
        )
    )
    _json(result)
    if result.status is ReviewStatus.FAILED:
        raise typer.Exit(1)


@review_app.command("resume")
def resume_review(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),  # noqa: B008 - Typer parameter declaration
    trace_mode: TraceMode = typer.Option(TraceMode.SUMMARY, "--trace"),  # noqa: B008
) -> None:
    """Resume an incomplete checkpoint or reopen a completed run."""
    result = ReviewService(trace_sinks=[_console_sink(trace_mode, review=True)]).resume(run_dir)
    _json(result)
    if result.status is ReviewStatus.FAILED:
        raise typer.Exit(1)


@review_app.command("status")
def review_status(
    run_dir: Path = typer.Argument(..., exists=False, file_okay=False),  # noqa: B008 - Typer parameter declaration
) -> None:
    """Read persisted status without running the graph."""
    _json(ReviewService().status(run_dir))


@review_app.command("trace")
def review_trace(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),  # noqa: B008
    tail: int = typer.Option(50, min=0),
    follow: bool = typer.Option(False, "--follow"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect or follow a review's persisted operational trace."""
    trace_path = run_dir.resolve() / "telemetry" / "execution_trace.jsonl"
    if not trace_path.is_file():
        typer.echo(f"Trace not found: {trace_path}", err=True)
        raise typer.Exit(1)
    try:
        events = read_trace(trace_path)
        selected = events[-tail:] if tail else events
        stream = follow_trace(trace_path, tail=tail) if follow else iter(selected)
        renderer = ConsoleTraceSink(
            TraceMode.SUMMARY,
            stream=sys.stdout,
            show_nodes=True,
            show_models=True,
        )
        for event in stream:
            if as_json:
                typer.echo(event.model_dump_json())
            else:
                rendered = renderer.render(event)
                if rendered is not None:
                    typer.echo(rendered)
    except KeyboardInterrupt:
        typer.echo()
    except (OSError, ValueError) as exc:
        typer.echo(f"Cannot read trace: {exc}", err=True)
        raise typer.Exit(1) from exc


def main() -> None:
    app()


if __name__ == "__main__":
    main()
