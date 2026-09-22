# Autonomous review service architecture comparison

Source of truth: `../review-service-architecture-options.md`

Visual reference only: `../review-service-architecture-deck.html`

Format: 16:9, English, 12 slides

Editorial rule: compare the three plans without ranking or selecting one.

## Slide 1: Autonomous review service architecture

- Three implementation plans for document review, analysis, and evidence-backed results.
- Scope: standalone execution without human intervention.
- Plans: static controlled graph, supervisor with specialist subagents, and one ReAct agent.
- Visual idea: restrained cover with three parallel paths.
- Layout role: cover.
- Required source images: none.

## Slide 2: The plans target the same review outcome

- Review heterogeneous documents through a common service interface.
- Run mandatory domain analysis and bounded model investigation.
- Produce a structured result with reopenable evidence.
- Compare orchestration, context boundaries, validation, runtime, and implementation work.
- Visual idea: one shared outcome on the right fed by three equally weighted paths.
- Layout role: comparison frame.
- Required source images: none.

## Slide 3: The shared contract keeps the comparison consistent

- Preserve `ReviewService.start`, `resume`, and `status`.
- Build an immutable source manifest before analysis.
- Restrict agents to guarded, read-only source tools.
- Bound calls, retries, concurrency, duration, and result size.
- Validate coverage, evidence, and the artifact bundle before completion.
- Visual idea: five-stage horizontal contract with a small current-baseline inset.
- Layout role: context and shared constraints.
- Required source images: none.

## Slide 4: Plan 1 uses a static controlled graph

- Code defines manifest creation, routing, specialist fan-out, synthesis, and publication.
- Specialist nodes combine deterministic analysis with bounded ReAct investigation.
- Evidence reopening, omission audit, and coverage checks are named graph stages.
- Checkpoints align with stage boundaries and support resume.
- Main implementation work: typed state, reducers, routing, replay, retry, and timeout policy.
- Visual idea: six-stage workflow with parallel specialist branches in the middle.
- Layout role: architecture.
- Required source images: none.

## Slide 5: Plan 2 delegates through a supervisor tool call

- A deterministic shell creates the task ledger, source assignments, and budgets.
- The supervisor receives one command: `run_specialist`.
- Each call names a registered domain specialist and supplies trusted task and source IDs.
- Specialists return typed result envelopes rather than full transcripts.
- The final validator checks required delegations, coverage, and evidence.
- Visual idea: shell, supervisor, four specialist lanes, result envelopes, and final validator.
- Layout role: architecture.
- Required source images: none.

## Slide 6: Host policy defines every specialist before execution

- Identity: trusted name, instructions, domain skill, and result schema.
- Scope: immutable source IDs from the assignment ledger.
- Tools: assigned-source research catalog with tracing and result limits.
- Execution: fresh context, fixed model and tool budgets, timeout, and no nested delegation.
- Return: `SpecialistResult` with analysis receipts, findings, evidence, warnings, and usage.
- Runtime controls: `task_id` idempotency, atomic slot reservation, and bounded concurrency.
- Visual idea: specialist specification on the left and runtime lifecycle on the right.
- Layout role: implementation detail.
- Required source images: none.

## Slide 7: Plan 3 combines planning and execution in one ReAct loop

- One agent receives the manifest, objective, and complete bounded review tool catalog.
- Code runs mandatory deterministic domain analyses before the loop.
- The agent chooses read and analysis tools until it produces a structured candidate.
- Middleware limits model calls, tool calls, context growth, retries, and duration.
- External code still validates coverage, evidence, and final artifacts.
- Visual idea: circular tool loop bounded by an outer validation frame.
- Layout role: architecture.
- Required source images: none.

## Slide 8: Tools, skills, and adapters have separate responsibilities

- Document adapters profile formats and reopen stable evidence locations.
- Command tools perform bounded reads, table operations, joins, queries, and statistics.
- Skills provide domain instructions, mandatory deterministic analysis, and verifier policy.
- Supervisor: `run_specialist` only; no raw-source or write tools.
- Specialists: one domain skill and assigned-source tools; no delegation.
- Lead synthesizer: verified reports only; no raw-source access.
- Visual idea: three-layer capability model with a role-to-capability strip.
- Layout role: capability model.
- Required source images: none.

## Slide 9: The three plans divide orchestration work differently

- Compare orchestration owner, source assignment, specialist isolation, evidence checks,
  parallel execution, checkpoint unit, and core engineering work.
- Static graph: explicit stages and branch state.
- Supervisor: ledger-backed child calls and typed envelopes.
- Single ReAct: one shared context and post-loop validation.
- Visual idea: neutral seven-row comparison table with equal column treatment.
- Layout role: comparison matrix.
- Required source images: none.

## Slide 10: Runtime follows the orchestration model

- Static graph work follows configured stages with explicit specialist fan-out.
- Supervisor work varies with planning, child-call count, and synthesis.
- Single ReAct work varies with the tool trajectory and stopping decision.
- Recovery units differ: graph stage, child task envelope, or agent-loop checkpoint.
- Benchmark metrics: calls, tokens, elapsed time, retries, peak concurrency, and recovery work.
- Visual idea: three aligned runtime lanes with the same measurement scale.
- Layout role: runtime comparison.
- Required source images: none.

## Slide 11: Implementation and evaluation use one shared test frame

- Shared work: adapters, manifest, deterministic analyses, evidence reopening, schemas, and
  artifact validation.
- Plan-specific work: graph state and reducers; child lifecycle and idempotency; or context
  and loop controls.
- Run each plan against the same corpus, models, budgets, and concurrency limits.
- Measure coverage, analysis completion, citation support, output variance, resume behavior,
  calls, tokens, latency, and terminal-status accuracy.
- Report correctness separately from runtime and cost.
- Visual idea: shared foundation bar under three implementation columns and a metric strip.
- Layout role: implementation and evaluation comparison.
- Required source images: none.

## Slide 12: Research basis and discussion

- Repository evidence: review service, graph workflows, subagent runtime, shared tools, and
  registered review skills.
- Framework evidence: official LangGraph and LangChain documentation and source.
- Locked environment: LangChain 1.3.17 and LangGraph 1.2.11.
- Discussion points: audience depth, comparison dimensions, benchmark data, and citation
  placement in the final deck.
- Visual idea: two-column source map with a concise discussion footer.
- Layout role: appendix and discussion.
- Required source images: none.
