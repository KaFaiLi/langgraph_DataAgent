# Case 01 end-to-end review report

## Scope and outcome

- Reviewer: GPT-5.6 Sol.
- Source set: `evals/cases/case_01/source`.
- Review period: 2025-07-01 through 2026-06-30.
- Successful run: `runs/case01-e2e-deepseek-20260902-sol-review-r2`.
- Final execution status: completed.
- Final analytical disposition: 0 verified final findings, 0 retained cross-source
  clusters, 60 unresolved questions, and 23 typed unresolved issues.
- Specialist disposition: risk metrics 8 unresolved; PnL 8 unresolved; post-trade
  controls 0 findings; risk commentary 3 unresolved.

The pipeline now completes without silently promoting unsupported claims. The result is
safe in that narrow sense, but it is not decision-useful: all 19 specialist findings were
either unresolved or absent, while the narrative still describes apparent anomalies and
an elevated-but-uncertain risk profile. Readers must treat the output as a failed evidence-
gathering exercise rather than a substantive desk conclusion.

## Failure and restart log

| Attempt | Result | Failure or intervention | Recovery action |
|---|---|---|---|
| Original run | Failed before analysis | `langchain-deepseek` was not installed | Installed the locked `deepseek` extra and resumed the checkpoint |
| Restart 01 | Interrupted | CLI resume did not preserve the evaluation runner's sequential concurrency setting; concurrent branches made no observable progress for more than five minutes | Terminated the process, recorded an interrupted execution status, and resumed through `_EvaluationReviewService(max_concurrency=1)` |
| Restart 02 | Interrupted | A model-authored dotted DuckDB table name spent more than two minutes in binding/registration | Added early rejection for dotted/path-like table names |
| Restart 03 | Interrupted | A valid-looking but unregistered table name caused eager registration of every source table, including large workbooks | Added `src_*` table validation and lazy registration of only referenced tables |
| Restart 04 | Failed in lead synthesis | `_repair_report_structure()` assigned raw issue dictionaries directly to a typed report and then dereferenced `issue_id` | Rehydrated every carried issue as `ReviewIssue` |
| Restart 05/06 | Terminal checkpoint replay | Resuming an already terminal LangGraph checkpoint returned the prior failed state; code changes could not reopen it | Started a fresh `-r2` run with the same source manifest |
| Fresh `-r2` run | Completed | No execution failure | Used this sealed bundle for quality and presentation review |
| PPT attempt 01 | Failed | The model copied unresolved specialist IDs into `finding_ids`, although the final report had no verified findings | Removed unverified IDs deterministically and disclosed the removal as a slide limitation |
| PPT attempt 02 | Failed | `python-pptx` was not installed | Added and installed the `presentation` optional dependency |
| PPT attempt 03 | Completed | Initial synthesis wording implied desk stress despite zero verified findings | Rebuilt the synthesis slide with a deterministic no-verified-findings message and regenerated the deck |

Run-local logs are retained under both run directories, including `initial_run.log`,
`restart-*.log`, `ppt_build*.log`, execution traces, LLM usage, and checkpoint databases.

## Operational quality

### What worked

- Checkpoint artifacts preserved completed specialist work across process restarts.
- Typed issues survived into the final report; no omission disclosure disappeared during
  lead collection.
- The successful run rejected every unsupported finding rather than manufacturing a
  positive result.
- Candidate and issue accounting remained present in specialist verification artifacts.
- The final bundle and PPT conversion artifacts passed their structural validators.

### What did not work well

- The successful run required 208 model calls, approximately 3.09 million input tokens,
  75,131 output tokens, and 838 seconds of accumulated model latency.
- The trace contains 62 failed tool calls. The dominant categories were exhausted tool
  budgets, attempts to use external/path-based DuckDB syntax, and attempts to read skill
  reference paths that were outside specialist source scope.
- Challenger research frequently ended with provider/tool failure records, causing even
  simple evidence-backed observations to become unresolved.
- Coverage records say checks were performed but usually leave `population_count` and
  `examined_count` empty. This does not yet meet the intended population-accounting
  standard.
- The final report contains 60 unresolved questions, many of which duplicate long
  adjudicator feedback. This overwhelms prioritization and makes the report difficult to
  consume.
- The final executive and overall-risk prose still discusses recurring limit pressure,
  governance concerns, and an elevated risk profile despite having zero verified final
  findings. Qualifiers reduce the risk of overstatement but do not fully solve it.

## Analytical result quality

### Strengths

- The report is explicit that no finding cleared verification.
- Material gaps are visible rather than suppressed.
- The lead removed cross-source clusters whose members were unresolved and converted
  them into investigation leads.
- The output distinguishes absence of verified misconduct from proof that controls were
  effective.

### Weaknesses

- Zero verified findings after extensive deterministic analysis indicates an acceptance-
  contract calibration problem, not necessarily a clean desk.
- Low-risk measured observations were blocked by incomplete generic challenger research
  even when their primary evidence and deterministic calculation were adequate.
- Research agents repeatedly requested unsupported paths or invalid SQL rather than using
  the advertised scoped tools and registered `src_*` names.
- Unresolved issue descriptions expose verbose internal adjudication language and repeated
  rule failures. They should be normalized into short gap, impact, and required-action
  fields before final reporting.
- A completed execution with no verified findings should carry a prominent analytical
  status such as `inconclusive`, separate from the successful execution status.

## PowerPoint visual review

Artifact: `runs/case01-e2e-deepseek-20260902-sol-review-r2/case01_independent_risk_review.pptx`.

### Strengths

- The eight-slide deck has a consistent white, navy, and red editorial system.
- Titles are answer-first, typography is legible, and header/footer alignment is stable.
- Specialist slides use a repeatable commentary-rail plus chart/table layout.
- Charts and tables are crisp, uncluttered, and use restrained emphasis colors.
- Evidence and overview traceability are retained in footers and speaker notes.
- SVG validation, conversion validation, and model verification all passed.

### Weaknesses

- The summary and synthesis slides are visually sparse relative to the specialist pages.
- The original model-authored synthesis title implied that the desk was likely operating
  under stress without any verified finding. The regenerated slide now states that no
  cross-specialist conclusion cleared verification.
- The post-trade slide combines a bar chart of event activity with `RESOLVED 0 (0.00%)`
  and `MEAN CLOSURE Unavailable`. Although technically qualified, this can look internally
  contradictory without a stronger note that invalid dates—not open cases—prevent the
  closure calculation.
- The PnL slide's absolute-amount value is visually precise but lacks compact units and
  digit grouping, reducing executive readability.
- Several specialist headlines are long enough to dominate the page and could be shortened
  by roughly 20 percent.
- With no verified findings, the closing actions are the most useful content and should
  move earlier, immediately after the executive assessment.

## Recommended next changes

1. Persist resume-time concurrency and model/skill configuration in `RunContext`; do not
   let CLI resume silently change execution topology.
2. Make research prompts enumerate exact scoped tool names, source paths, and DuckDB table
   names, and prohibit skill-reference paths in source-tool calls.
3. Separate claim-specific verification from generic challenger completeness so a failed
   optional challenge cannot invalidate an otherwise reproducible observation.
4. Require population and examined counts for checks that make population claims.
5. Add analytical run disposition (`conclusive`, `inconclusive`, `blocked`) alongside
   execution status.
6. Summarize unresolved issues by materiality and required action; keep full adjudication
   histories in appendices/artifacts rather than the executive report.
7. Make the PPT builder use a deterministic no-findings storyline before model planning,
   rather than sanitizing unsupported IDs after planning.
8. Add a clean-process interruption-and-resume integration test that verifies completed
   specialist branches are not repeated and configuration is preserved.
