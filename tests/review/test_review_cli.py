from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from data_agent.cli import app


runner = CliRunner()


def test_unified_cli_exposes_chat_and_review() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "chat" in result.stdout
    assert "review" in result.stdout


def test_chat_passes_one_joined_message_to_agent(monkeypatch) -> None:
    messages: list[str] = []

    class FakeBundle:
        async def ask(self, message: str) -> str:
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
