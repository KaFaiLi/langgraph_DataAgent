"""Single command-line interface for DataAgent chat and controlled reviews."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import typer

from data_agent.agent.react_agent import build_agent
from data_agent.config import get_settings
from data_agent.logging_utils import setup_logging
from data_agent.review.interface import ReviewRequest, ReviewStatus
from data_agent.review.service import ReviewService


app = typer.Typer(no_args_is_help=True, help="Chat with DataAgent or run a controlled review.")
review_app = typer.Typer(no_args_is_help=True, help="Run, resume, and inspect controlled reviews.")
app.add_typer(review_app, name="review")


async def _chat_once(message: str) -> None:
    bundle = await build_agent()
    typer.echo(await bundle.ask(message))


async def _chat_repl() -> None:
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
        typer.echo(f"agent> {await bundle.ask(message)}\n")


@app.command("chat")
def chat(message: list[str] | None = typer.Argument(None)) -> None:
    """Send one message, or start an interactive session when MESSAGE is omitted."""
    setup_logging(get_settings().log_level)
    if message:
        asyncio.run(_chat_once(" ".join(message)))
    else:
        asyncio.run(_chat_repl())


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
    source: Path = typer.Option(..., exists=False, file_okay=False),
    output: Path = typer.Option(..., file_okay=False),
    review_start: str = typer.Option(...),
    review_end: str = typer.Option(...),
    desk_template: Path = typer.Option(..., exists=True, dir_okay=False),
    run_id: str | None = typer.Option(None),
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
    result = ReviewService().start(
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
def resume_review(run_dir: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Resume an incomplete checkpoint or reopen a completed run."""
    result = ReviewService().resume(run_dir)
    _json(result)
    if result.status is ReviewStatus.FAILED:
        raise typer.Exit(1)


@review_app.command("status")
def review_status(run_dir: Path = typer.Argument(..., exists=False, file_okay=False)) -> None:
    """Read persisted status without running the graph."""
    _json(ReviewService().status(run_dir))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
