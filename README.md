# DataAgent

A general-purpose ReAct agent with shared MCP tools and trusted analytical skills.
The agent chooses investigations, delegates independent roles, and revises its work.
Code validates source scope, evidence, coverage, budgets and published artifacts.
Supported review domains are risk metrics, composite PnL (including income attribution,
validation and adjustments), post-trade controls, and risk commentary.

## Run locally

```bash
uv sync --extra dev --extra deepseek
cp .env.example .env
# Set your provider credentials and models in .env.
uv run data-agent chat "Inspect the supplied sources and describe their contents."
```

Start a complete review with a desk JSON containing `desk_name` and
`business_description`. The CLI sets its review period (any dates already present must
match). Source files remain read-only; use a separate output directory.

```bash
uv run data-agent review run \
  --source /absolute/path/to/sources \
  --output /absolute/path/to/review-run \
  --review-start 2025-01-01 --review-end 2025-07-31 \
  --desk-template /absolute/path/to/desk.json --run-id REVIEW-001
uv run data-agent review status /absolute/path/to/review-run
uv run data-agent review resume /absolute/path/to/review-run
uv run data-agent review trace /absolute/path/to/review-run --tail 30
```

Review commands enable typed specialist, challenger, adjudicator and lead peers. They use
`AgentReviewService`, not the legacy controlled graphs. A completed run returns
`bundle_path`, normally `<output>/bundle`, containing the compatible reviewed JSON/Markdown,
overviews, verification history and manifest. Give that path to reviewed-output consumers
such as risk-ppt. Unresolved questions remain explicit; completion does not mean all
findings were verified. An `interrupted` result has resumable work. CLI exit code 1 means
failure; status JSON schema version 2 also exposes budgets and machine-readable reasons.

To interact with an existing review through chat or its REPL:

```bash
REVIEW_RUN_ID=REVIEW-001 REVIEW_OUTPUT_DIR=/absolute/path/to/review-run \
  uv run data-agent chat "Inspect outstanding work and continue verification."
```

A root conversation checkpoint and authoritative run record persist results across
process restarts. Do not edit sources midway through a run; integrity failures require
a new review. Repeated resume of a completed run validates and reopens its bundle.
Legacy completed bundles remain readable; legacy graph checkpoints must be rerun through
the new entrypoint. The old service/graphs remain available only for regression and
explicit legacy integrations.

## Installed use and configuration

`uv build` produces a wheel containing all trusted skill documents, references, scripts,
and presentation assets. Install the wheel with the `deepseek` extra for that provider.
Installed CLI, chat and MCP resolve bundled skills by default; `SKILLS_DIR` can point to
an explicitly deployed trusted skill directory. Model arguments never select scripts.
For installed use, `.env` and relative source/workspace paths resolve from the current
working directory; source checkouts retain repository-relative defaults.

`.env.example` documents providers and limits. Review roots use the general chat model;
specialists/challengers use the configured low-cost model, while adjudication and lead
roles use the high-cost model. Per-child limits and aggregate `REVIEW_MAX_MODEL_CALLS`,
`REVIEW_MAX_TOOL_CALLS`, `REVIEW_CHILD_MAX_RUNS`, and `REVIEW_MAX_ACTIVE_SECONDS` bound
execution. Existing run allowances cannot be reset by changing environment settings.
`REVIEW_ROOT_MAX_ITERATIONS` bounds a root turn. Defaults allow a multi-domain review;
actual provider cost depends on usage. Keep credentials, source data and run artifacts
outside version control.

Start the shared MCP transport with `uv run python -m data_agent.mcp_server`.
`REVIEW_RUN_ID` and optional `REVIEW_ASSIGNMENT_ID` bind it to a host-authorized scope;
bound servers expose review capabilities without unrestricted source/Python tools.
For an explicit output directory also set `REVIEW_OUTPUT_DIR`. HTTP clients must connect
to a server configured with the same host binding.

## Validation and architecture

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

See [runtime contracts](docs/architecture/general-agent-review-runtime.md),
[subagent configuration](docs/subagents.md), and the
[migration acceptance plan](docs/plans/general-agent-review-migration.md).
Synthetic integration fixtures are under `tests/review/fixtures`; controlled evaluations
run separately under `evals/`. Evaluation gold is never production input or test data.
