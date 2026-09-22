# General-agent review migration validation

Validated on 2026-09-23. Each milestone was tested, exercised through the actual configured
API/CLI, committed and pushed before the next milestone began. The implementation and
acceptance checklist are in `docs/plans/general-agent-review-migration.md`.

The results below describe the migration before legacy graph retirement. The subsequent
cleanup and its retained/migrated coverage are recorded in
`docs/validation/legacy-review-graph-removal.md`.

## Automated and deployment checks

- Full suite: **463 tests passed**. Deterministic calculations, candidate identities,
  overviews, evidence admission and report contracts retain the legacy assertions.
- Ruff lint and repository-wide formatting checks pass; no baseline formatting debt
  remains. No unrelated behavioral refactoring was needed for formatting.
- Full ReAct integration runs all four domains with legacy `ReviewService`, parent and
  specialist graph builders patched to fail on invocation. Two valid work orders pass;
  an injected child failure is retried through the model-selected tool path.
- Coverage includes premature publication, malformed/unsupported evidence, independent
  verification, severity constraints, omission disclosure, exhausted revisions, provider
  failures, aggregate budgets, cancellation, restart and atomic publication recovery.
- Root checkpoints retain conversation and accepted results after process restart.
  Corrupt, incomplete or changed bundles fail status validation. Completed resume is
  idempotent. Large lead contexts retain all disclosures without duplicating the report.
- Wheel and source distributions build. The wheel includes all **7 skill documents**,
  references, scripts and presentation assets, with no Python bytecode. An isolated
  installation outside the checkout discovers **4 analytical skills and 50 MCP tools**,
  loads the trusted lead entrypoint, starts CLI help, and reopens the completed bundle.
- The installed CLI also called the real API, loaded risk-metrics, executed its trusted
  calculations and reproduced the synthetic **130% maximum utilization** and missing
  Colibris limitation. This was a bounded analysis check, not an independently verified
  finding.

## Separate live four-domain evaluation

The evaluation used six synthetic files created from the existing test fixture builders
in a separate local source directory. It did not use evaluation gold or production data.
Execution used `data-agent review run` and a later `data-agent chat` continuation with
real configured DeepSeek models; no fake model or scripted coordinator drove this run.
The model chose assignments, calculations, research, candidate interpretation, independent
challenge/adjudication, revision and lead synthesis.

Local reproducibility artifacts (not committed):

- Source scope: `/tmp/data-agent-m8-source`
- Durable run: `/tmp/data-agent-m8-run`
- Published bundle: `/tmp/data-agent-m8-run/bundle`
- Evaluation JSON: `/tmp/data-agent-m8-evaluation.json`
- CLI logs: `/tmp/data-agent-m8-live-cli.log`, `/tmp/data-agent-m8-resume-cli.log`
- Installed CLI check: `/tmp/data-agent-m8-installed-cli.log`

The separate evaluator was run with:

```bash
uv run python -m evals.general_review \
  --run-dir /tmp/data-agent-m8-run --output /tmp/data-agent-m8-evaluation.json
```

| Domain | Sources | Candidate IDs accounted for | Overviews | Findings | Verification rounds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Composite PnL | 3 | 2 | 3 | 3 unresolved | 6 |
| Post-trade controls | 1 | 17 | 2 | 4 unresolved | 8 |
| Risk metrics | 1 | 2 | 1 | 2 unresolved | 4 |
| Risk commentary | 1 | 5 | 2 | 3 unresolved | 6 |

All six sources were dispositioned and all 26 deterministic candidate IDs accounted for.
The completed bundle contains four specialist reports, eight overviews and **65 explicit
unresolved questions**. Independent lead verification accepted a synthesis with **zero
promoted final findings**, consistent with the absence of verified specialist support.
The complete bundle loader and integrity seal passed; the installed CLI reopened it.

Manual inspection found the expected source observations retained: WTD 99 versus a
re-accumulated 3, the 10 × 0.9 versus 8 adjustment discrepancy, 120%/130% SGMR utilization,
control recurrence/approval gaps, and quoted commentary validation/repetition signals.
The system kept causal, scope and materiality qualifications visible and did not promote
these unresolved observations into verified conclusions. Some model wording remains
imprecise (for example describing a two-day PnL fragment in months, and speculative
adjustment-direction alternatives); the unresolved status does not certify that prose.
Structural support is not a semantic precision score. This small fixture validates the
migration's obligations and supported scope, not broad financial-review quality.

The live run exposed two host issues that were corrected and regression-tested:
lead/report identifiers needed clearer instructions and a multi-domain reading budget;
the lead verifier received duplicate final-report context. Removing the duplicate reduced
its input to **100,961 characters**, below the unchanged 120,000-character input limit,
without dropping claims or disclosures. Restart retained all specialist verification;
only lead synthesis/verification and publication continued. Earlier child/tool failures
remain observable in the durable record rather than being erased.

## Latency and cost measurements

The completed run recorded **288 logical model calls**, **414 tool calls**, **62 child
attempts**, and approximately **960 seconds of active execution**. Summed model latency
was 1,533 seconds because independent children ran concurrently. Provider telemetry
reported **9,361,478 input tokens** and **228,670 output tokens** (9,590,148 total).
No monetary cost was supplied, so no dollar estimate is asserted.

| Role | Calls | Total reported tokens |
| --- | ---: | ---: |
| Root | 61 | 6,124,287 |
| Challenger | 158 | 2,354,704 |
| Adjudicator | 42 | 420,635 |
| Lead | 23 | 569,769 |
| Lead verifier | 4 | 120,753 |

The initial process's telemetry lacked model IDs; role attribution was recovered by
joining trace callback IDs. Telemetry now records LangChain model metadata directly, and
the resumed process recorded its configured model names. These totals include failures,
revisions and the context-size debugging attempts. They show substantial repeated-context
cost, not a steady-state efficiency benchmark. Accepted-finding production and efficiency
on representative sources remain quality work beyond this architectural migration.
