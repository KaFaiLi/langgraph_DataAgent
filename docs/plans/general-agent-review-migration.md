# General-agent review migration plan

Status: in progress; M1–M7 implemented and validated.
Date: 2026-09-22.

## Objective and architectural decision

Make the general-purpose DataAgent perform the same review tasks as the current
review service through skills, MCP tools, and model-selected subagents. The ReAct
agent chooses what to investigate, which capabilities to invoke, how to delegate,
and when to revise its work.

The new execution path must not invoke `ReviewService`, `build_parent_graph`, or
`build_specialist_graph`, including through a tool that wraps the old workflow.
The standard ReAct model/tool loop remains supported. Deterministic calculations,
evidence validation, capability restrictions, budgets, and artifact validation
remain code-owned operations; they do not prescribe a fixed review graph.

This user-selected target supersedes the recommendation to retain the controlled
coordinator in the [architecture options research](../research/review-service-architecture-options.md)
for this migration. Preserve the existing implementation as a regression reference
until the new path passes the acceptance criteria below.

Scope includes risk metrics, composite PnL, post-trade controls, risk commentary,
cross-specialist synthesis, compatible review artifacts, and restart/resume.
Preserve downstream compatibility for `risk-ppt`; redesigning presentation generation
and adding new document formats are separate work.

## Checklist conventions

- `[x]` means verified in the current repository or completed during implementation.
- `[ ]` means remaining work, including acceptance checks that have not yet run.
- Existing review-service behavior is reusable implementation, not proof that the
  general agent supports that behavior.
- Mark a milestone complete only when its implementation and acceptance checks pass.

## Milestone overview

| Milestone | Outcome | Depends on | Status |
| --- | --- | --- | --- |
| M0 | Audit the reusable foundation and record gaps | None | Complete |
| M1 | Extract graph-independent review capabilities | M0 | Complete |
| M2 | Make one specialist skill executable through the general agent | M1 | Complete |
| M3 | Add persistent review context, coverage, and scoped MCP access | M1; integrates M2 | Complete |
| M4 | Support typed specialist and independent verification roles | M2, M3 | Complete |
| M5 | Complete all specialist domains and verification parity | M4 | Complete |
| M6 | Produce validated lead synthesis and compatible artifacts | M5 | Complete |
| M7 | Add durable resume and reliable terminal status | M3; validates M4-M6 | Complete |
| M8 | Validate packaging, parity, documentation, and entrypoint cutover | M6, M7 | Pending |

## M0 — Completed foundation and baseline

- [x] Confirm the top-level `review/` package has already moved into `data_agent/review`.
- [x] Confirm shared source, document, table, and statistics implementations are
  registered with the [MCP server](../../data_agent/mcp_server/server.py).
- [x] Confirm the four specialist skills and `lead-review` contain domain instructions
  and trusted analysis entrypoints under `skills/`.
- [x] Confirm shared skill discovery and instruction loading exist under
  [data_agent/skills](../../data_agent/skills).
- [x] Confirm the general agent supports bounded parallel delegation, trusted child
  profiles, tool restrictions, and execution tracing.
- [x] Identify reusable evidence models, verification rules, report schemas, renderers,
  source validation, and run-bundle validation in `data_agent/review`.
- [x] Run the existing suite: `uv run pytest -q` — **401 passed**.
- [x] Run lint: `uv run ruff check .` — **passed**.
- [x] Check formatting: `uv run ruff format --check .` — **63 files would be reformatted**;
  inspected examples have CRLF working-tree endings against the configured LF format.
- [x] Build a wheel successfully and inspect it outside the source checkout.
- [x] Reproduce the packaging defect: the wheel contains no `SKILL.md` files, and CLI
  import fails while locating the eagerly initialized review skill registry, even
  when attempting `--help`.
- [x] Reproduce the status defect: a malformed `run_manifest.json` yields `completed`
  from `ReviewService.status`, while `resume` rejects the same manifest.

These checks establish the legacy baseline. General-agent review parity remains unverified.
The formatting failure is recorded baseline debt, not a completed formatting fix.

## M1 — Graph-independent capabilities

Primary sources: [skill runtime](../../data_agent/skills/runtime.py),
[review package initialization](../../data_agent/review/__init__.py),
[verification](../../data_agent/review/verification), and
[synthesis](../../data_agent/review/synthesis).

- [x] Define typed operation inputs/results that do not require `ParentState`,
  `SpecialistState`, or graph-specific `RunnableConfig` values.
- [x] Extract reusable analysis preparation, verification, omission auditing,
  cross-report analysis, and report construction from graph nodes.
- [x] Keep domain calculations in trusted skill scripts and reuse existing models
  and validation rules instead of creating parallel implementations.
- [x] Remove eager graph/service/registry initialization from imports needed by
  general-agent tools, domain models, and skill loading.
- [x] Keep shared tool implementations in `data_agent/tools`, skill loading and
  registration in `data_agent/skills`, and transport adapters in `data_agent/mcp_server`.
- [x] Preserve existing review-service tests while extracting the shared operations.

Acceptance:

- [x] Operations can be invoked with typed inputs independently of either review graph.
- [x] Importing reusable capabilities does not construct or initialize a review workflow.
- [x] Existing behavior tests remain green through the extracted interfaces.

## M2 — Executable skills and the first specialist

Primary sources: [skill tools](../../data_agent/skills/tools.py),
[trusted analysis loader](../../data_agent/skills/review.py), and
[risk-metrics skill](../../skills/risk-metrics/SKILL.md).

- [x] Add a contained, bounded way to load a selected skill's dataset and policy references.
- [x] Expose trusted analysis execution by registered skill identity; never accept an
  arbitrary Python module, script path, or callable from model arguments.
- [x] Preserve entrypoint validation, containment checks, deterministic calculations,
  stable candidate IDs, evidence locators, and data overviews.
- [x] Return bounded result summaries and references to stored detailed results.
- [x] Add an overall review playbook explaining objectives, capability selection,
  required evidence, coverage obligations, uncertainty, and expected deliverables.
- [x] Update specialist instructions to name available tools and reference-loading
  operations rather than assuming the old runtime has prepared their inputs.
- [x] Implement a first vertical slice with `risk-metrics`: load instructions and
  references, execute analysis, inspect evidence, and submit a typed candidate result.

Acceptance:

- [x] The general agent completes this slice without invoking a review graph.
- [x] Trusted analysis outputs match the existing deterministic skill on the same fixture.
- [x] Missing references, unknown skills, and escaped entrypoints return explicit errors.
- [x] Truncation remains visible and cannot be interpreted as complete population coverage.

## M3 — Run context, coverage, and scoped MCP tools

Primary sources: [tool context](../../data_agent/tools/review_context.py),
[assigned-source research tools](../../data_agent/tools/research.py),
[dispatch](../../data_agent/review/orchestration/nodes/dispatch.py), and
[coverage](../../data_agent/review/orchestration/nodes/coverage.py).

- [x] Introduce a persistent run record containing source/output roots, review period,
  desk context, immutable source manifest, assignments, and artifact references.
- [x] Expose bounded operations to initialize a run, inspect inventory, assign work,
  inspect coverage, and record source/candidate dispositions.
- [x] Preserve complete discovery, source hashing, parse failures, and explicit
  handling of ambiguous or unclassified sources.
- [x] Bind source access to trusted run and assignment context. A run ID or path
  supplied by the model must not grant broader filesystem access.
- [x] Enforce the same source restrictions for MCP and in-process tool calls,
  including table joins, SQL, search, and evidence reopening.
- [x] Keep source and candidate coverage authoritative in stored records, independently
  of the model's summary of what it believes it has reviewed.
- [x] Register review capability adapters with MCP over the shared implementations;
  keep local subagent orchestration owned by the agent host.

Acceptance:

- [x] Concurrent runs and specialist assignments cannot read each other's unauthorized sources.
- [x] Source changes and out-of-scope evidence are detected consistently across transports.
- [x] Every discovered source has a visible required disposition; omitted work is reported.

## M4 — Typed subagents and independent verification roles

Primary sources: [subagent contracts](../../data_agent/agent/subagents/contracts.py),
[registry](../../data_agent/agent/subagents/registry.py), and
[runner](../../data_agent/agent/subagents/runner.py).

- [x] Register trusted specialist, challenger, adjudicator, and lead profiles with
  explicit skills, tool subsets, input contracts, and result schemas.
- [x] Extend child execution to validate structured outputs or return validated stored
  result references; free-form text alone must not establish a completed review result.
- [x] Add host-configured model roles that preserve low-cost research/challenge and
  high-cost adjudication allocation. Keep provider configuration out of skill documents.
- [x] Give challengers independent context and evidence access; preserve removal of
  anchoring fields from their inputs and the adjudicator's restricted capabilities.
- [x] Let the root select and coordinate peer roles within the existing one-level
  delegation model; deeper delegation is not required for this migration.
- [x] Configure budgets sufficient for specialists, verification, revisions, and lead
  synthesis, with explicit failure, timeout, truncation, and cancellation results.

Acceptance:

- [x] Different roles receive only their authorized tools, sources, context, and model tier.
- [x] Malformed child output cannot become an authoritative report or verification decision.
- [x] Parallel children retain isolated state, trace ancestry, and bounded execution.

## M5 — All specialist domains and verification parity

Primary sources: [evidence validation](../../data_agent/review/ingestion/evidence_validator.py),
[verification rules](../../data_agent/review/verification/rules.py),
[omission auditing](../../data_agent/review/verification/omission.py), and the four domain skills.

- [x] Extend the first slice to composite PnL, post-trade controls, and risk commentary.
- [x] Preserve composite PnL ownership of income attribution, validation, and adjustments.
- [x] Expose evidence validation, independent challenge, adjudication, revision, and
  candidate-disposition capabilities without embedding the specialist graph in a tool.
- [x] Preserve `PASS`, `REVISE`, `REJECT`, and `UNRESOLVED`, severity constraints,
  counter-evidence, bounded revisions, and exhausted-revision handling.
- [x] Persist verification records bound to the finding version and its evidence;
  editing a finding must invalidate any acceptance that no longer applies.
- [x] Expose omission auditing and preserve bounded rescue or explicit unresolved
  disclosure for material deterministic candidates that remain unaccounted for.
- [x] Reject self-declared verification status unsupported by authoritative records.

Acceptance:

- [x] Each domain produces compatible typed findings and data overviews through the general agent.
- [x] Invalid evidence, missing independent challenge, failed adjudication, and material
  omissions cannot silently become a successful verified result.
- [x] Tests validate obligations and outcomes while permitting different valid tool-call sequences.

## M6 — Lead synthesis and artifact publication

Primary sources: [lead-review skill](../../skills/lead-review/SKILL.md),
[final validation](../../data_agent/review/synthesis/lead_verifier.py),
[report renderers](../../data_agent/review/reporting/markdown.py), and
[run-bundle validation](../../data_agent/review/application/run_bundle.py).

- [x] Expose the lead skill's deterministic cross-report analysis over stored specialist reports.
- [x] Supply the lead role with validated reports, clusters, contradictions, and unresolved
  items while preserving its prohibition on rereading raw sources.
- [x] Support typed lead draft submission and independent lead verification/revision.
- [x] Preserve `derived_from` links, finding-specific evidence, severity ceilings,
  stable identities, and unresolved disclosures.
- [x] Add a publication operation that validates coverage, verification records, evidence,
  and report structure and returns actionable unmet requirements to the agent.
- [x] Render compatible specialist/final JSON and Markdown, data overviews, verification
  history, research traces, and run manifests.
- [x] Publish artifacts atomically and validate the complete bundle before sealing completion.
- [x] Preserve downstream completed-bundle consumption, including `risk-ppt` inputs.

Acceptance:

- [x] The agent can repair reported deficiencies and retry publication without a fixed graph route.
- [x] Early publication, unsupported severity increases, and invented evidence are rejected.
- [x] Existing bundle consumers can open a completed general-agent review.

## M7 — Durable resume and reliable status

Primary sources: [agent lifecycle](../../data_agent/agent/runtime.py),
[review service](../../data_agent/review/service.py), and
[run bundles](../../data_agent/review/application/run_bundle.py).

- [x] Persist assignments, analysis outputs, findings, verification history, coverage,
  artifact references, and cumulative budgets independently of conversation text.
- [x] Add root conversation checkpointing and a resume interface that reconnects the
  agent to the authoritative run record and outstanding work.
- [x] Use stable task/result identities and idempotent writes so replay does not duplicate
  accepted work or publish inconsistent artifacts.
- [x] Record failures and interrupted execution explicitly; normalize provider and tool errors.
- [x] Make terminal status depend on validated artifacts rather than manifest-file existence.
- [x] Define machine-readable failure reasons and how disclosed unresolved items affect
  completion; version public/persisted contracts if a warning status is introduced.
- [x] Apply bounded retries, deadlines, cancellation, and aggregate run budgets without
  reinstating a stage-by-stage deterministic review coordinator.

Acceptance:

- [x] A process restart resumes unfinished work with prior accepted results and budgets intact.
- [x] Corrupt or partially written bundles cannot report successful completion.
- [x] Repeated publication/resume attempts preserve stable artifact identities and valid state.

## M8 — Packaging, parity, documentation, and cutover

- [ ] Package trusted skill documents, references, and scripts, or support an explicit
  deployable skill location consistently across chat, review capabilities, and MCP.
- [ ] Verify installed CLI help and tool/skill discovery outside the repository checkout.
- [ ] Add integration tests for the complete model-directed review, covering all domains,
  incomplete coverage, bad evidence, failed children, exhausted budgets, and restart/resume.
- [ ] Add a guard test proving the new path never invokes `ReviewService`,
  `build_parent_graph`, or `build_specialist_graph`.
- [ ] Compare deterministic calculations, candidate accounting, coverage, evidence admission,
  and artifacts against existing synthetic fixtures; do not require identical prose or tool order.
- [ ] Run controlled evaluations separately from tests to assess finding quality, omissions,
  latency, and cost. Never read or copy evaluation gold data into production or test fixtures.
- [ ] Switch the intended review entrypoints to the general-agent runtime after parity checks
  pass, preserving start/resume/status usability and documenting any compatibility changes.
- [ ] Update root and skill `AGENTS.md`, usage examples, configuration documentation, and
  architecture notes to reflect model-directed execution and current package locations.
- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv build`, and installed-package smoke checks; resolve or explicitly account for baseline
  formatting debt without mixing unrelated refactoring into migration changes.
- [ ] Retire unused deterministic graph entrypoints only after callers and compatibility
  requirements have been checked; retain reusable domain logic and valuable assertions.

## Completion criteria

- [ ] A user can request a full review through the general agent and receive a validated,
  reopenable artifact bundle with the same supported analytical scope as the current service.
- [ ] The model controls investigation, delegation, and revision; no old review graph runs.
- [ ] Mandatory analysis, source/candidate coverage, independent verification, evidence integrity,
  and publication validity are enforced by capability contracts and authoritative records.
- [ ] Failure, uncertainty, truncation, interruption, and resume are observable and tested.
- [ ] Deployment works outside the source checkout, and downstream artifact consumers remain usable.

## Completion log

| Date | Milestone | Evidence |
| --- | --- | --- |
| 2026-09-22 | M0 | Repository audit; 401 passing tests; passing lint; formatting debt recorded; wheel startup and malformed-manifest status defects reproduced. |

Add implementation and validation evidence here when completing each later milestone.

| 2026-09-22 | M1 | Extracted typed analysis, evidence, omission, cross-report and report operations; legacy adapters reuse them. Lazy registry/workflow imports verified in a fresh process. `uv run pytest -q`: 405 passed; `uv run ruff check .`: passed; all 18 changed Python files pass format checks. Live `data-agent chat` loaded risk-metrics and answered through the configured API (two HTTP 200 model calls). Fixed a pre-existing POSIX sandbox realpath recursion revealed on this host; path, process, credential and symlink restrictions pass. |
| 2026-09-22 | M2 | Added contained paginated references, registered trusted analysis, hash-bound result storage, evidence reopening, and typed pending candidate submission; general-review playbook and four specialist tool instructions. Guarded ReAct integration invokes no legacy workflow. `uv run pytest -q`: 411 passed; lint and changed-file formatting passed. Live CLI reviewed five synthetic SGMR rows, loaded both references, ran trusted analysis, inspected candidates/overviews, reopened evidence and stored three pending findings, disclosing missing Colibris inputs. Artifacts retained locally at `/tmp/data-agent-m2-results`; no API secrets or run artifacts committed. |
| 2026-09-22 | M3 | Added transactional versioned run records, immutable source manifests, explicit classification/assignment/disposition operations, stored source and candidate coverage, hash-checked scoped research and shared MCP adapters. SQL registers only assigned tables and disables external access. Concurrent writes, cross-run/assignment isolation, parse failures, source changes and pagination tested. Live CLI initialized M3-LIVE, analyzed/submitted/dispositioned through MCP; a fresh assignment-bound process reopened persisted evidence and rejected an unauthorized source. Live coverage exposed and helped fix locator-free candidate ID drift; repeated accounting now reports both candidates covered while publication stays pending. `uv run pytest -q`: 419 passed; lint and changed-file formatting passed. Local records: `/tmp/data-agent-m3-results/runs/M3-LIVE`. |

| 2026-09-22 | M4 | Registered typed specialist, independent challenger, no-research adjudicator and lead peers on the ordinary ReAct delegation host. Host-bound context, low/high cost models, strict raw result validation, version-bound stored receipts and reserved result capacity preserve capability and budget limits. Source-operation schemas and paginated stored assignment reads make live role selection usable. `uv run pytest -q`: 429 passed; lint and changed-file formatting passed. Live CLI researched the stored SGMR finding, persisted an 11-category challenger result, then independently adjudicated with the high-cost model; both stored references agree on the finding version. Malformed-output and exhausted-budget attempts produced no authoritative result. Finding remains pending until M5 verification guards. Live evidence: `/tmp/data-agent-m4-cli.log` and M3-LIVE records. |

| 2026-09-23 | M5 | Added version-bound evidence admission, independent challenge sanitization, guarded adjudication, two-round reduction, idempotent acceptance, revision invalidation, bounded omission rescue/disclosure and compatible specialist reports. All four domains run through the general ReAct host; deterministic tables/overviews match direct trusted scripts and composite PnL owns its three inputs. Paginated gates/omission audits and candidate-disposition receipts expose actual coverage. One bounded schema repair retains independent research and closes further research access. `uv run pytest -q`: 438 passed; lint and all changed Python format checks passed. Live M5-LIVE reviewed six synthetic sources and stored 13 pending findings with all four specialist role references; malformed risk evidence references prompted a schema-description fix and successful peer retry. Live M3-LIVE applied guarded verification, exhausted revisions to explicit unresolved outcomes, and constructed report RISK with two unresolved findings, history and seven disclosures. A fresh PnL verification and evidence pagination CLI check also completed. Logs: `/tmp/data-agent-m5-*-cli.log`; artifacts remain local and untracked. |

| 2026-09-23 | M6 | Extracted pure final validation and bounded semantic revision rules; added version-bound lead roles, cross-report analysis, strict derivation/evidence/severity gates, and atomic compatible bundle publication with an integrity seal. Publication, revision, tampering, staging failure and same-domain identity tests pass; existing consumers reopen the live bundle. `uv run pytest -q`: 447 passed; lint and all changed Python format checks passed. Live CLI independently verified and published `/tmp/data-agent-m3-results/runs/M3-LIVE/bundle`, retaining two unresolved specialist findings and 17 disclosures without promoting unsupported conclusions. The live attempt exposed and fixed a missing lead dataset reference and misspelled skill-tool error handling. Logs: `/tmp/data-agent-m6-*-cli.log`. |

| 2026-09-23 | M7 | Added checkpointed root ReAct execution, a process lease, persisted aggregate dispatch/time budgets, stable delegation replay, accepted-role recovery, machine-readable interruption/failure status and validated completion. Bound review chat uses the durable runtime; legacy status now validates complete bundles too. `uv run pytest -q`: 456 passed; lint and changed-file format checks passed. Restart, cancellation, aggregate exhaustion, source changes, malformed/partial bundles and atomic-rename recovery are tested. Two real CLI processes resumed M5-LIVE: PNL-F2 reached its terminal unresolved disposition, then the second process recovered its conversation/result without repeating children (calls 19→25 model, 20→26 tool, child attempts stayed 2). Logs: `/tmp/data-agent-m7-first-cli.log` and `/tmp/data-agent-m7-restart-cli.log`. |
