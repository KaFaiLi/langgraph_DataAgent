# Model-directed review runtime

`AgentReviewService` owns execution infrastructure around the general ReAct agent.
It does not select domains, sequence specialists, decide what to investigate, or route
revisions. The model chooses those operations using the `general-review` playbook.
The legacy `ReviewService`, parent/specialist graphs and graph adapters have been removed.
`data_agent/review` retains the active service, models, evidence validation, verification
policy, reporting, persistence and cost-tier provider configuration.

## Authoritative state and restart

A run directory contains `review_record.sqlite`, `conversation.sqlite`, an OS execution
lease, telemetry, content-addressed analysis/candidate outputs, and a published `bundle/`.
The run record binds immutable source/output roots, source hashes, desk and period.
Assignments, candidates, dispositions, independent role receipts, verification versions,
lead acceptance and cumulative budgets remain authoritative independently of conversation
text. A root checkpoint stores each ordinary ReAct model/tool step. Children have isolated,
non-checkpointed conversations and cannot inherit the root's checkpoint coordinates.

A process holds an exclusive advisory lease for the invocation. Restart detects an
abandoned invocation, retains committed budgets, and resumes the pending root checkpoint.
Delegation tool-call IDs are persisted. Accepted child results are reused even if a
process dies before its tool receipt is checkpointed; unfinished children return an
explicit interruption under their original ID. The model may choose a fresh bounded
attempt. Source edits invalidate continuation. Checkpoint files and sources are never
chosen through model-controlled filesystem paths.

Model/tool dispatch reservations and child attempts commit before execution. Provider
retries remain bounded by provider settings; counters measure logical dispatched calls,
while telemetry records token usage returned by the provider. Total active elapsed time
is bounded across invocations. After an unclean process exit, elapsed time since its last
start is conservatively charged, capped at the run allowance. Settings changes do not
reset a persisted allowance. Existing experimental run records acquire accounting when
first opened through this runtime; earlier unrecorded model calls cannot be reconstructed.

## Status contract

`AgentReviewResult` is schema version 2. It retains `running`, `completed`, `failed` and
`not_found`, and adds `interrupted`, `retryable`, cumulative budget fields, `bundle_path`,
and an unresolved-item count. A normal turn ending before publication is `interrupted`
with `work_remaining`; it is not successful completion. `completed` requires the full
bundle loader, content seal and stored input fingerprint to agree. Disclosed unresolved
findings remain limitations in a completed report, not verified conclusions; no warning
status is introduced.

Stable failure reasons include `process_interrupted`, `cancelled`, `iteration_limit`,
`work_remaining`, `budget_exhausted`, `source_integrity_failure`, `invalid_checkpoint`,
`invalid_run_state`, `bundle_integrity_invalid`, and `execution_error:<ExceptionType>`.
Provider/transport exception text is not persisted in public status. Tool failures and
child failures are recorded separately. Integrity and aggregate-budget failures cannot
be reset by resuming. A `run_busy` response identifies another active root process.

## Publication and compatibility

Publication validates coverage, current independent verification, evidence, lead support
and deterministic report structure. It writes and validates a complete temporary bundle,
seals artifact hashes, and atomically renames it to `bundle/`. A crash before the database
completion commit is recoverable by validating and adopting that same sealed directory.
Partial or mismatched directories never imply completion. Repeated publication preserves
artifact identities. The bundle retains specialist/final JSON and Markdown, overviews,
verification/research history, catalog, desk context, lead verification and run manifest
for existing reviewed-output consumers, including risk-ppt. Additional derived presentation
files may be created without rewriting sealed review artifacts.


## Entry points and installed assets

`data-agent review run/resume/status` and host-bound review chat now use this runtime.
The Python API is async `AgentReviewService.start(ReviewRequest(...))` and
`AgentReviewService.resume(path)`, with synchronous read-only `status(path)`.
Legacy completed bundles reopen through the same validated consumer. Old graph checkpoints
are identified as `legacy_checkpoint_unsupported`; rerun their sources through the current
entrypoint. Legacy graph builders, `ReviewService`, `skills.runtime.build_skill_graph`,
`skills.registry.build_specialist` and the v1 result/status contracts are no longer
exported. The old checkpoint-resume helpers and model runners are also removed.
Use `AgentReviewResult` for the current result/status contract. Archive reading does
not execute or deserialize legacy graph checkpoints.

Wheel distributions package `skills/` at `data_agent/_bundled_skills/`. Checkouts retain
their editable skill tree; an explicit `SKILLS_DIR` selects one trusted deployment tree
for chat discovery, MCP, specialist calculations and lead analysis. Installed writable
paths and `.env` resolve from the current working directory, never site-packages.
