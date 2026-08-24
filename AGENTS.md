# Repository Guidelines

## Project Structure & Module Organization

Production code lives in `data_agent/`. Keep conversational ReAct behavior in
`data_agent/agent`, controlled risk workflows in `data_agent/review`, model adapters in
`data_agent/llm`, and MCP transport in `data_agent/mcp_server`. Shared implementations
belong in `data_agent/tools` and shared skill loading/registration in `data_agent/skills`;
do not recreate private tool or skill packages under callers. Domain playbooks and trusted
deterministic entrypoints live in top-level `skills/<kebab-case-name>/`. Tests mirror the
code under `tests/`, with review-specific suites in `tests/review/`. Treat `evals/` as
controlled evaluation material, not production fixtures.

## Build, Test, and Development Commands

- `uv sync --extra dev` installs locked runtime and development dependencies.
- `uv run pytest -q` runs the complete test suite.
- `uv run pytest tests/review/test_review_service.py -q` runs one focused module.
- `uv run ruff format .` formats Python; add `--check` for CI-style verification.
- `uv run ruff check .` performs static lint checks.
- `uv build` builds wheel and source distributions.
- `uv run data-agent --help` shows the unified `chat` and `review` commands.
- `uv run python -m data_agent.mcp_server` starts the MCP server over configured transport.

## Coding Style & Naming Conventions

Target Python 3.12, four-space indentation, double quotes, LF endings, and a 100-character
line limit. Use `snake_case` for functions/modules, `PascalCase` for classes and Pydantic
models, and `UPPER_CASE` for constants. Add type hints to public interfaces. Prefer a
small public interface with implementation details localized behind it. Use Ruff for
mechanical formatting; do not hand-format around it.

## Testing Guidelines

Use pytest and `pytest-asyncio`. Name files `test_<behavior>.py` and tests
`test_<expected_outcome>`. Add focused unit tests for deterministic logic and integration
tests for graph routing, evidence validation, checkpoint/resume, and CLI behavior. No
numeric coverage threshold is configured; every change must keep the full suite passing.
Never read or copy evaluation gold data into tests.

## Commit & Pull Request Guidelines

History uses short, imperative subjects such as `format: ruff format` and
`Ignore evaluation case sources`. Keep commits focused and avoid generated run artifacts.
Pull requests should explain intent, affected modules, validation commands/results, and
configuration changes. Link the relevant issue; include screenshots only for visible
output changes and sample artifact paths for report changes.

## Security & Configuration

Copy `.env.example` locally and keep `.env`, credentials, SQLite checkpoints, logs, and
review workspaces untracked. Preserve source containment and read-only guarantees. Do not
add arbitrary filesystem, process, Python, or network access to specialist tools.
