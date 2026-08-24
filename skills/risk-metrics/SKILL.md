---
name: risk-metrics
description: Review finalized SGMR risk-consumption and Colibris excess-workflow data for desk risk, limit usage, metric behavior, governance, and cross-source consistency.
metadata:
  kind: specialist-review
  domain: risk_metrics
  report_id: RISK
  label: Risk Metrics
  analysis_entrypoint: scripts/analysis.py:run_analysis
---

# Risk Metrics Review

Review SGMR limit-consumption history and Colibris excess-workflow records as one risk
evidence set. Python establishes populations, calculates utilization and timing, and
produces review candidates. The analyst relates those results to the desk's portfolios,
risk types, limits, and control response without treating a statistical signal or an
LLM-generated source tag as a finding by itself.

Before analysis, read [references/dataset.md](references/dataset.md) for the exact
schemas, grains, units, hierarchy, joins, and unresolved assumptions. Before verification
or severity assignment, read [references/policy.md](references/policy.md).

## Review objective

Determine what the supplied evidence supports about:

- the desk risk inventory by BU, SBU, PC, portfolio, region, currency, risk metric, and
  limit;
- current and historical limit utilization, remaining headroom, breaches, repeated
  proximity, effective-date coverage, and changes from initial or temporary bounds;
- VaR, SVaR, stress, exposure, or sensitivity behavior within comparable portfolio-level
  series, including sustained shifts, volatility regimes, and unusual observations;
- the frequency, duration, magnitude, open status, explanation, validation, escalation,
  remediation, and closure of excess events; and
- consistency between the SGMR limit definitions and Colibris event population.

Do not infer position direction, loss, capital impact, model quality, unauthorized risk,
or misconduct from risk consumption alone. PnL, attribution, positions, approvals,
commentary, and control procedures require their own evidence.

## Risk interpretation

- VaR is a model-based normal-market loss estimate at an unstated confidence horizon
  unless the metric definition says otherwise. It is neither a worst-case loss nor an
  additive portfolio exposure.
- SVaR applies stressed calibration or conditions. Compare it with VaR only when horizon,
  confidence, methodology, currency, hierarchy, and date are compatible.
- Stress results are scenario-dependent. State the scenario and sign convention; a large
  stress value cannot be interpreted without its shock and loss/magnitude definition.
- Exposure measures position size or risk-factor quantity, not expected loss. Confirm
  whether it is gross, net, delta-equivalent, or another measure before aggregation.
- Utilization is dimensionless headroom against the applicable directional bound. Rank
  unlike risk metrics by utilization only, not by their raw values.
- Portfolio, underlying, bucket, maturity, or currency axes describe where risk may sit.
  Do not call their distribution a concentration unless the measure is additive and the
  population is complete.

## Workflow

1. **Establish scope.** Classify tables from required columns, not filenames. Record each
   source, date range, row count, hierarchy, metric, unit, and unusable record. Stop
   dependent conclusions when a source family or material field is missing.
2. **Run deterministic analysis.** Call the trusted `run_analysis` entrypoint once with
   the guarded context and all scoped paths. Use its results as calculations and leads;
   never recompute or override them in prose.
3. **Build the desk risk map.** Identify the reviewed hierarchy and the portfolios and
   metrics attached to each PC. Use the most granular stable source level. Keep changes
   in hierarchy or metric mapping visible rather than silently merging them.
4. **Assess limits and headroom.** Apply the positive value to `limMaxValue` and a
   negative value to `limMinValue`; use the source warning threshold only when valid.
   Confirm the limit was effective on the value date. Report worst, current, p95, breach
   count, and repeated-proximity observations per comparable series. Do not apply
   temporary bounds without documented timing and approval semantics.
5. **Assess metric behavior.** Review levels and changes within the same portfolio,
   metric definition, unit, and limit series. Treat outliers, daily jumps, sustained
   shifts, trends, and volatility changes as candidates. Check missing dates, model or
   version changes, new activity, market moves, and reversals before interpreting them.
   A comparable exposure/stress rise with stable headline VaR is a divergence candidate,
   not an additive desk total: keep every metric separate and inspect factor mapping.
   When comparable component exposure grows at least fourfold, stress at least twofold,
   and headline VaR changes by no more than ten percent, treat the supported divergence
   as at least high severity; reserve critical for corroborated desk materiality or
   capital/control consequences.
6. **Assess excess governance.** Treat Colibris as a selected excess population, not the
   full daily risk population. Profile recurrence and severity, then inspect open/closed
   state, explanations, validation, LoD2 review, action deadlines, manual closure, and
   limit-increase workflow. Apply an SLA only when a source-backed policy defines it.
   When SGMR records a changed effective bound, compare that effective date to the
   request and approval milestones of the matching Colibris change workflow. Preserve
   pre-approved changes as contrary evidence. A changed regime recorded as effective
   before its request or approvals, especially after a hard-bound breach, is normally a
   material governance candidate (medium or high depending on linkage and impact), not a
   low-severity data observation. Timing alone still does not prove retrospective action,
   control circumvention, or misconduct.
7. **Reconcile sources at the valid grain.** Compare limit definitions by PC/perimeter,
   risk indicator, metric name, unit, and bound. Use dates for coverage checks. Require a
   documented unique ID and hierarchy bridge before claiming that an excess event ties
   to a particular SGMR consumption row or portfolio.
   Surface persistent blank factor mappings and explicit mapping/feed exceptions as
   separate candidates; their temporal/entity alignment may corroborate a representation
   gap but does not by itself establish omitted risk. An explicit still-open exception
   stating that a VaR component is excluded or omitted is at least a high-severity
   representation-control weakness, while its causal effect on the headline metric may
   remain unresolved.
8. **Interpret for the desk.** Explain which portfolios and risk types drive limit usage,
   whether the pattern is isolated or persistent, what control response is evidenced,
   and what risk remains open. Test benign explanations and contrary evidence.
9. **Present and verify.** Separate facts, deterministic candidates, interpretations,
   and unresolved questions. Reopen every cited locator, reproduce every numeric claim,
   apply the verifier policy, and issue only `PASS`, `REVISE`, `REJECT`, or `UNRESOLVED`.
   A deterministically reproduced divergence or open-state record can pass as a measured
   observation while its business cause or causal effect remains an explicit unresolved
   question. Do not make the measured fact unresolved merely because causation is unknown.

## Screening and materiality

The reproducible screening defaults are documented in
[references/policy.md](references/policy.md). They identify records and series that need
interpretation; they do not establish business materiality or severity. Materiality must
consider utilization, duration, recurrence, affected hierarchy, regulatory or capital
consequence, open control state, and corroborating desk context. If candidate locators
are capped, use the retained population tables, narrow scope through orchestration, or
keep coverage `UNRESOLVED`.

## Evidence and conclusion standard

- Every material claim must cite exact, reopenable `source://` rows. A pattern must retain
  its calculated population, threshold, dates, entities, and representative row locators.
- A Colibris row establishes a recorded excess and workflow state. It does not by itself
  prove that the desk remained over limit for every day in `daysInExcess` or that an
  approval was retrospective.
- `LLM_Explanation_Cause` and `LLM_Explanation_Solution` are derived annotations. They may
  help route review but cannot independently prove cause, remediation, or management
  acceptance. Prefer contemporaneous human-entered and validated fields.
- Old rows marked open or past deadline are candidates for stale or unresolved control
  items. Confirm extract as-of semantics and later closure evidence before calling them
  overdue.
- A current bound different from an initial bound proves a difference, not when or why it
  changed. Require effective-date and approval history for a governance conclusion.
- Recurring excesses need a stable event definition and population denominator. The
  excess register alone cannot establish an excess rate over all observations.
- If metric definitions, confidence horizons, scenario signs, aggregation rules, source
  freshness, limit precedence, SLA, or cross-system identifiers are absent, keep the
  dependent conclusion `UNRESOLVED`.

## Failure and uncertainty handling

- Continue only calculations that remain valid when SGMR or Colibris is missing,
  unreadable, or malformed. Mark dependent limit, workflow, or reconciliation conclusions
  `UNRESOLVED` and disclose the excluded population.
- A path outside the manifest, parse failure, or locator that cannot be reopened is not
  evidence. Correct a fixable citation through `REVISE`; after bounded repair is
  exhausted, use `UNRESOLVED`.
- Do not replace missing metric definitions, limit precedence, business calendars, SLAs,
  state dictionaries, or identifier bridges with an assumed rule or external lookup.

## Output obligations

Present the result in this order: scope and data quality; desk risk profile; limit usage
and headroom; metric behavior; excess and governance profile; cross-source consistency;
findings; unresolved matters and required evidence.

Before findings, retain a deterministic limit-utilization overview for each comparable
metric, portfolio, unit, and effective-limit series. It must preserve the trajectory and
current, worst, p95, warning, and breach statistics with exact evidence locators. Do not
merge unlike metrics, units, hierarchies, or limit regimes to create a desk total. When
the required population or evidence is absent, retain an explicit unavailable or partial
overview and its limitation.

For every finding, state the affected desk entity and risk metric, dates and population,
source unit, magnitude or utilization, deterministic method, exact locators, control or
desk-risk implication, contrary evidence and benign alternatives, confidence, severity,
and the action or evidence needed to close the point. Never add unlike risk metrics or
mixed units into a desk total merely to make the presentation simpler.
