# Legacy review graph removal

Follow-up to the general-agent migration, validated on 2026-09-23.

## Removal boundary

Removed the deterministic parent/specialist graph package, `ReviewService`, skill graph
builders, graph-specific lead/challenger/adjudicator adapters, bounded legacy model runners,
and old checkpoint-resume helpers. Removed the unused v1 `ReviewResult`, `ReviewRunStatus`
and `ReviewStatus` APIs and the import-time default review provider instance.

The supported Python entrypoint is `AgentReviewService`, with async `start()`/`resume()`,
synchronous `status()`, `ReviewRequest` inputs and schema-v2 `AgentReviewResult` outputs.
The ordinary general ReAct graph, current checkpoints and peer role execution are retained.
`data_agent/review` still owns active models, evidence/verification policy, archive and
publication support, reporting, execution infrastructure and cost-tier model configuration.

Completed legacy bundles remain readable without invoking a graph. Interrupted legacy
checkpoints return `legacy_checkpoint_unsupported`; their source inputs must be rerun.

## Regression coverage

Finding normalization, candidate limits, revision retention, evidence enrichment and
severity-floor assertions now import the active policy/schema modules directly in
`test_finding_policy.py`. Lead derivation, evidence, severity, unresolved-support, cluster
and source-integrity cases now exercise `validate_final_report` in `test_lead_validation.py`.
Challenger admission and omission checks also use shared capabilities directly.

Preflight failure and completed-archive resume tests now exercise `AgentReviewService`.
Lead rejection, exhausted semantic objections and revision history are checked through
`PublicationCapabilities`. A checkpoint regression proves old checkpoint bytes are never
read into a graph or altered. An architecture check verifies removed modules and public
adapters cannot be imported. The four-domain ReAct integration, durable restart/replay,
source containment, independent verification and atomic publication suites remain active.

Retired tests asserted old graph node ordering, graph-specific prompt truncation and
automatic draft repairs, legacy checkpoint reconstruction, or duplicate legacy service
end-to-end behavior. Their implementation no longer exists. This is why the suite has
fewer tests than the pre-cleanup migration, while active domain/evidence guards remain.

## Validation

- Full suite: **410 tests passed** (five existing PyMuPDF/SWIG deprecation warnings).
- Repository lint and formatting checks pass.
- All 35 retired production modules are absent; an AST import audit finds no remaining
  production imports of them.
- Wheel and source distribution build successfully. The wheel has all seven skill
  documents and contains no retired implementation, bytecode or `.env`.
- An isolated wheel installation outside the checkout discovers four analytical skills,
  starts CLI help, and validates/reopens `/tmp/data-agent-m8-run` through status/resume.

Live validation uses a fresh five-row synthetic SGMR dataset, including 120% and 130%
utilization observations. It uses the configured API via the actual CLI, without fake
models, evaluation gold, or production data. Run artifacts and logs remain untracked.

The fresh CLI run completed and sealed its bundle in approximately **383 seconds** of
active execution (93 logical model calls, 111 tool calls, 12 child attempts). It reviewed
one source and published one specialist report with one overview. Both findings remained
`unresolved` after bounded independent verification; the lead verifier passed a synthesis
with zero promoted final findings and 21 explicit unresolved questions. The missing
Colibris candidate remained an explicit omission disclosure. Invalid tool arguments and
failed bounded child attempts were visible and recovered through the current runtime;
this check establishes execution/guard compatibility, not model-prose accuracy.

Separate `review status` and `review resume` CLI processes returned `completed`, with
identical cumulative budgets. The sealed-bundle loader and source hash validation passed.
The existing four-domain bundle also remained readable in the isolated wheel install.

Local artifacts (not committed):

- Run root: `/var/folders/vs/hvh1gfl53z582fcwwvhx27km0000gn/T/data-agent-legacy-removal-ppxr0gb8`
- Published report: `<run root>/run/bundle/final_findings.md`
- Live CLI log: `/tmp/data-agent-legacy-removal-cli.log`
- Status/resume: `/tmp/data-agent-legacy-removal-status.json`, `/tmp/data-agent-legacy-removal-resume.json`
- Automated checks: `/tmp/data-agent-legacy-removal-tests.log`, `/tmp/data-agent-legacy-removal-build.log`

CLI invocation (from the checkout with the configured `.env`):

```bash
TASK_RUN_ROOT=/var/folders/vs/hvh1gfl53z582fcwwvhx27km0000gn/T/data-agent-legacy-removal-ppxr0gb8
uv run data-agent review run --source "$TASK_RUN_ROOT/source" \
  --output "$TASK_RUN_ROOT/run" --desk-template "$TASK_RUN_ROOT/desk.json" \
  --review-start 2025-01-01 --review-end 2025-01-31 --run-id LEGACY-REMOVAL
uv run data-agent review status "$TASK_RUN_ROOT/run"
uv run data-agent review resume "$TASK_RUN_ROOT/run" --trace off
```

To repeat a fresh run, regenerate the fixture in a new temporary root or choose a fresh
output directory and run ID. Completed-run resume intentionally performs no new analysis.
