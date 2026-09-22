# Speaker notes

Delivery style: technical explainer. Present each plan neutrally, define the control boundary,
and connect implementation choices to observable runtime behavior.

## Slide 1: Autonomous review service architecture

This presentation compares three ways to implement the same autonomous review service. Each
plan must review a heterogeneous document set, run the required domain analyses, validate the
evidence behind retained findings, and produce a final artifact without asking a person to
intervene during the run.

The difference lies in orchestration. The first plan uses a controlled graph, the second uses a
supervisor that delegates through tool calls, and the third uses one ReAct agent. The following
slides keep the external contract fixed so we can compare the implementation choices directly.

## Slide 2: The plans target the same review outcome

All three paths lead to the same product outcome. The service receives documents, performs
domain-specific analysis, and returns a structured result with evidence that can be reopened.
The comparison therefore focuses on how each plan organizes the work rather than on changing
what the service promises.

We will compare who chooses the next step, how source scope and context are isolated, where
validation occurs, what can execute in parallel, how a run resumes after interruption, and what
engineering work each design adds.

## Slide 3: The shared contract keeps the comparison consistent

Every plan sits behind the same ReviewService interface. The run starts by creating an immutable
manifest, and agents receive only guarded, read-only operations. Deterministic domain analyses
remain mandatory, while model calls, tool calls, retries, concurrency, elapsed time, and result
size all have explicit bounds.

The current domain covers eight document formats: CSV, XLSX, XLSM, Parquet, PDF, DOCX, Markdown,
and text. A run ends as completed, completed with warnings, or failed. Coverage, evidence, and the
artifact bundle determine that status outside model prose.

## Slide 4: Plan 1 uses a static controlled graph

In Plan 1, code fixes the major stages. The parent graph builds the manifest, routes sources,
fans specialist work out in parallel, merges the results, synthesizes the lead report, audits
coverage, and publishes the final bundle. Each named stage creates a natural checkpoint.

Specialists can still use ReAct behavior inside bounded research nodes. They first receive
host-run deterministic analysis, then investigate assigned material, reopen evidence, test the
draft through adversarial review, and check for omitted deterministic candidates. The main
implementation work is typed state, reducers, routing, retry policy, timeouts, and replay-safe
node behavior.

## Slide 5: Plan 2 delegates through a supervisor tool call

Plan 2 moves the routing decision into a supervisor agent while retaining a deterministic shell.
The shell creates the assignment ledger, source scopes, task identifiers, and budgets. The
supervisor sees one delegation command, run_specialist, and selects a registered domain
specialist by name.

The host resolves the specialist definition and source IDs. The child returns a typed
SpecialistResult envelope containing analysis receipts, findings, evidence, warnings, and usage.
The supervisor does not receive child transcripts or raw filesystem access. A final validator
checks that every required task ran and that coverage and evidence remain complete.

## Slide 6: Host policy defines every specialist before execution

Each specialist exists as trusted configuration before the run starts. Its specification fixes
the identity, instructions, single domain skill, assigned-source tools, model and tool budgets,
timeout, and output schema. The source IDs come from the assignment ledger, so the child cannot
widen its own scope.

At runtime, the host validates the task, reserves a concurrency slot, creates a fresh child
context, and returns one bounded result envelope. The task ID acts as the idempotency key. A child
receives no delegation tool, which keeps the hierarchy to one level and makes repeated or changed
assignments detectable.

## Slide 7: Plan 3 combines planning and execution in one ReAct loop

Plan 3 gives one agent the review objective, the complete manifest, and the bounded review tool
catalog. Code runs every mandatory deterministic domain analysis before the loop, then exposes
the resulting receipts and bounded outputs to the agent.

The agent chooses which source or analysis tool to use next and stops when it can produce a
structured candidate result. Middleware limits model calls, tool calls, context growth, retries,
and total duration. The same external validators still check coverage, evidence, and the final
artifact bundle before publication.

## Slide 8: Tools, skills, and adapters have separate responsibilities

The shared architecture separates three concerns. Document adapters handle file formats by
profiling sources and reopening stable evidence locations. Command tools perform bounded reads,
table operations, joins, queries, and statistics. Skills contain trusted domain instructions,
mandatory deterministic analysis, and verifier policy.

Each agent role receives a different subset. The supervisor gets only run_specialist.
Specialists get one domain skill and tools restricted to assigned sources. Challengers receive a
smaller evidence and analysis subset. The lead synthesizer receives verified specialist reports
without raw-source access. No model-facing role gains arbitrary filesystem, process, Python,
network, or publication access.

## Slide 9: The three plans divide orchestration work differently

This matrix places the three plans against the same seven design dimensions. The static graph
puts orchestration in graph nodes and keeps specialist state in explicit branches. The supervisor
uses ledger-backed tool calls and fresh child context. The single ReAct plan keeps the complete
manifest and tool trajectory in one agent context.

The validation and recovery units also differ. Plan 1 uses specialist and final graph gates with
named stage checkpoints. Plan 2 validates child envelopes and tracks supervisor and child tasks.
Plan 3 validates after the loop and resumes from agent-loop state. These differences determine
where state, idempotency, and observability must be implemented.

## Slide 10: Runtime follows the orchestration model

The runtime profile follows the control flow. Plan 1 executes a configured sequence with explicit
specialist fan-out. Plan 2 adds supervisor planning, a variable number of concurrent child calls,
and synthesis of their envelopes. Plan 3 follows one adaptive tool trajectory whose length ends
at the stopping decision or a configured limit.

The benchmark should measure all three with the same source corpus, models, budgets, and
concurrency limits. The relevant measures include model and tool calls, tokens, elapsed time,
retries, peak concurrency, and the amount of work repeated after resume. Until those runs exist,
the slide describes execution mechanics rather than measured performance.

## Slide 11: Implementation and evaluation use one shared test frame

Much of the implementation belongs to every plan: document adapters, the immutable manifest,
deterministic analyses, evidence reopening, typed results, and artifact validation. Plan-specific
work sits above that foundation. The graph plan adds state, reducers, and node policies. The
supervisor plan adds registry, ledger, task cache, concurrency, and result envelopes. The single
agent plan adds context controls, middleware, and post-loop checks.

Evaluation should separate correctness from runtime and cost. The common test frame measures
source coverage, mandatory-analysis completion, citation support, output variance, resume
behavior, resource use, and terminal-status accuracy under injected faults. That structure lets
the comparison explain both what each plan produced and how it reached the result.

## Slide 12: Research basis and discussion

The current-state assessment comes from the review service, graph workflows, subagent runtime,
shared tools, and registered skills in this repository. Framework behavior comes from official
LangGraph and LangChain documentation and source, checked against the locked environment using
LangChain 1.3.17 and LangGraph 1.2.11.

The remaining presentation choices concern the audience and evidence level. We can expand the
implementation details for an engineering review, shorten them for an executive audience, add
measured benchmark results when available, and decide whether framework citations belong on the
technical slides or only in the appendix.
