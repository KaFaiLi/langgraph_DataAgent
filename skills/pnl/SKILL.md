---
name: pnl
description: Review finalized AIR PnL, income-attribution, adjustment, and validation-history files together for numerical integrity, unusual patterns, workflow gaps, and cross-file inconsistencies.
metadata:
  kind: specialist-review
  domain: pnl
  source_domains:
    - pnl
    - pnl_validation
    - pnl_adjustments
    - income_attribution
  report_id: PNL
  label: PnL
  analysis_entrypoint: scripts/analysis.py:run_analysis
---

# PnL Review

Review the finalized PnL bundle as one evidence set: accumulated desk PnL, wide AIR
income attribution, manual and freeze adjustments, and PnL-validation history. Python
establishes populations, reperforms calculations, and produces candidates. The analyst
interprets those results and must not turn a statistical flag, attribution concentration,
or workflow state into a control conclusion by itself.

This is an intentional composite review for a finalized three-file bundle. Treat its PnL,
adjustment, and validation inputs as one specialist scope; do not duplicate the same
sources into additional specialist conclusions without an explicit coverage split.

Before reviewing, read [references/dataset.md](references/dataset.md) for the exact
schemas, grains, joins, date semantics, and unresolved unit assumptions. Read
[references/policy.md](references/policy.md) before verifying or assigning severity.

## Review objective

Determine whether the supplied records support evidence-backed observations about:

- completeness and internal consistency of DTD, WTD, MTD, QTD, and YTD PnL;
- large or recurring PnL moves, reversals, one-directional runs, volatility changes,
  and period-end concentration at a comparable portfolio level;
- size, timing, recurrence, reversal, currency conversion, and documentation of manual
  or freeze adjustments;
- validation coverage, active-record uniqueness, state persistence, and processing
  timing by GOP, team, and PnL type; and
- inconsistent entity mappings, dates, or populations across the source families; and
- whether the wide attribution export explains reported income, preserves its cumulative
  values, and reports a settled processing/validation state.

Do not review trading misconduct, limit compliance, or valuation-model correctness. Do
not infer that an attribution bucket is wrong merely because it is concentrated or named
"other"; use the supplied hierarchy, workflow state, desk context, and contrary evidence.

## Method

1. Classify tables by their required columns rather than by filename. Record missing,
   duplicate, unreadable, or unrecognized inputs before analyzing values.
2. Run the trusted deterministic entrypoint. Treat its flags as review candidates, not
   findings. Reperform WTD/MTD/QTD/YTD from DTD within the same Version, Notion, PTF,
   and Currency series.
3. Analyze PnL patterns within comparable series. Do not aggregate currencies or compare
   PnL with adjustments until their units, sign conventions, and inclusion basis are
   documented.
4. Review adjustments using valuation dates for economic timing and creation dates for
   processing timing. Reperform `AMOUNT * EXCHANGERATE = AMOUNTINEUR`; test entity
   mappings against PnL; distinguish `MANUAL` from `FREEZE`; and inspect period-end or
   rapidly reversing activity. When the deterministic screen identifies an
   opposite-signed adjustment that nearly offsets same-day DTD under an explicit unit
   conversion, assess the offset, linked reversal, and ordinary adjustment population
   together; the candidate is not proof of smoothing. When the offset is followed by a
   near-mirror reversal in the bounded reversal window, treat the supported close-
   integrity pattern as at least high severity while keeping intent and the exact PnL
   inclusion basis explicit.
5. Review validation history as workflow-state evidence. Use `api_request_date` for the
   PnL population date and `creationTime` for record timing. Do not reinterpret `state`
   as a monetary validation break or assume that an unfamiliar state is failed. Give
   specific attention to recognized non-final states that coincide with an unusual
   adjustment date, while retaining normal team/state history as contrary evidence.
   Such a coincident active non-final state is at least a medium close-control candidate;
   it does not by itself establish that reported PnL was wrong.
6. Join PnL to adjustments through PTF plus consistent GOP, PC, and currency mappings;
   join validation through GOP. Report coverage mismatches in both directions.
7. For the wide income-attribution export, use `asofdate` as the observation date and
   `Final Result Acc DTD` as the reported total. Profile primary buckets independently;
   do not add parent and leaf columns together. Compare the supplied cumulative total
   within each complete hierarchy series and treat `status`, `validated`, and
   `isbatchvalidated` as workflow evidence whose meaning requires a source dictionary.
   Interpret a persistent single-component window at its exact hierarchy and dates;
   never add parent and leaf attribution fields or infer missing risk representation.
8. Test benign explanations and contrary evidence before escalating: normal accruals,
   documented freezes, scheduled period-end valuation, reporting calendars, different
   PnL versions, and team-specific workflow responsibilities.
9. Relate candidates to desk materiality using source-backed units, magnitude, duration,
   recurrence, affected hierarchy, validation/control consequence, and desk context.
   Statistical thresholds only select records for review; they do not assign severity.
10. Present the scoped result, reopen every cited locator, apply the verifier policy, and
   issue only `PASS`, `REVISE`, `REJECT`, or `UNRESOLVED` verification outcomes.

## Screening and materiality

The deterministic screening defaults are documented in
[references/policy.md](references/policy.md). They make candidate selection reproducible,
but none is a business materiality threshold. Do not describe a candidate as material
until source units and desk context support that conclusion. If a result reports more
candidates than the emitted locator cap, use its population tables, narrow the review
scope through orchestration, or keep coverage `UNRESOLVED`; never treat truncation as a
clean population.

## Evidence and conclusion standard

- Every material claim must cite an exact, reopenable `source://` locator. For a pattern,
  cite representative rows and retain the deterministic population statistics.
- Separate facts, code-generated candidates, interpretations, and unresolved questions.
- A single large day or adjustment is not a systemic issue. A repeated pattern still
  needs magnitude, population, affected entities, dates, and plausible alternatives.
- Missing optional adjustment fields are not automatically a documentation failure.
  Establish which fields are required for the adjustment type or source first.
- A persistent non-final validation state is a workflow observation until the state
  dictionary, team responsibility, deadline, and later history establish overdue work.
- A GOP or PTF population mismatch may reflect scope or mapping differences. Call it an
  inconsistency only after checking the stated population of each file.
- If PnL units, adjustment inclusion, state meanings, reporting calendars, or approval
  requirements are absent, keep dependent conclusions `UNRESOLVED`; do not guess.

## Failure and uncertainty handling

- Continue only analyses that remain valid when one source family is missing, unreadable,
  or malformed. Mark dependent cross-source, validation, adjustment, or monetary
  conclusions `UNRESOLVED` and disclose the excluded population.
- A source path outside the manifest, parse failure, or locator that cannot be reopened is
  not evidence. Correct a fixable citation through `REVISE`; after the bounded workflow
  cannot repair it, use `UNRESOLVED`.
- Never compensate for missing units, calendars, state dictionaries, or inclusion rules
  with an assumed conversion, deadline, state meaning, or external data lookup.

## Output obligations

Present the result in this order: scope and data quality; PnL integrity and behavior;
income-attribution coverage, driver profile, cumulative reconciliation, and processing
state; adjustment profile and controls; validation coverage and persistence; cross-source
consistency; findings; unresolved matters and required evidence.

Before findings, retain deterministic data overviews in the report: daily DTD PnL
accumulated from zero separately within each calendar year for every comparable
Version/Notion/PTF/Currency series, plus adjustment and validation profiles. Show annual
endpoint totals. Never combine currencies or overlapping/ambiguous portfolio series;
state explicitly when the result is not a desk total. If the necessary population,
units, or evidence cannot be reopened, publish an unavailable or partial overview with
the limitation instead of an unsupported chart.

State the reviewed files, date ranges, row counts, versions, notions, currencies, PnL
types, teams, and excluded or unusable records. For each finding, identify the affected
date and entity, quantify the result in source units, explain the deterministic check,
cite the supporting rows, address contrary evidence, and calibrate severity. End with
explicit reconciliation limitations and evidence needed to close them.
