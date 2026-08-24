# Risk Metrics Review and Verification Policy

Use these challenges for every candidate conclusion.

## Deterministic screening defaults

These settings select review candidates; they do not define desk materiality or severity:

| Screen | Default |
| --- | --- |
| Series coverage | Flag below 95% of observed dates in the scoped SGMR population |
| Hard breach | Directional utilization above 1.0 |
| Warning proximity | Valid source `limRelativeThreshold`; otherwise 90% with an invalid-threshold candidate |
| Repeated proximity | At least three consecutive observed values at or above warning threshold |
| Metric statistics | At least 20 comparable observations |
| Outlier | Absolute population z-score above 3.0 |
| Large daily change | Absolute change at least 25% from the prior observed value |
| Sustained level shift | 20 observations before and after; mean change at least 20%; standardized effect at least 2.5 |
| Volatility regime | At least 50% change between first- and second-half mean rolling 20-observation volatility |
| Persistent trend | Projected full-period change at least 20% and trend R² at least 0.60 |
| Prior-value date gap | Non-positive gap, or more than seven calendar days for a daily extract |
| Repeated excess population | At least three events with the same perimeter, metric, unit, and limit |
| Usage re-performance | Flag a difference above 1.5 percentage points; maximum usage may not be more than 1 point below last usage |
| Numeric limit match | Absolute or relative tolerance of `1e-8` |

The runner emits at most 50 representative flags per result while retaining full
population summaries. Reaching the cap requires population review or an unresolved
coverage statement; it does not imply omitted candidates are immaterial.

## Evidence and population

1. Can every cited row be reopened, and does it contain the stated date, hierarchy,
   metric, unit, limit, value, event, or workflow state?
2. Does the population cover the claimed period and every relevant portfolio, limit,
   risk metric, version, event state, and source family?
3. Does a duplicate indicate bad data, a legitimate version/history record, or a missing
   business-key dimension?
4. Is a Colibris observation being misrepresented as the population of all daily risk?
   State the denominator before reporting event rates.
5. Are derived `LLM_Explanation_*` tags being used as independent evidence? If so, revise
   the claim to use contemporaneous source fields.

## Metric meaning and desk relationship

6. Is the metric definition known: horizon, confidence level, methodology, stress
   scenario and sign, exposure type, sensitivity shock, currency, and scale?
7. Is the analysis at a stable desk hierarchy and metric grain? Check mapping changes and
   do not merge unlike portfolios or metric definitions.
8. Are raw VaR, SVaR, stress, exposure, or sensitivity values being added or compared as
   though they were interchangeable? Use utilization for cross-metric headroom views.
9. Does a factor or portfolio concentration calculation use an additive measure and a
   complete population? If not, describe it only as a distribution proxy.
10. Does the result explain what risk it represents for this desk, rather than repeat a
    high value without portfolio, factor, scenario, or limit context?

## Limits and utilization

11. Was utilization reproduced against the correct directional bound and unit? Check
    zero, missing, asymmetric, and sign-specific bounds.
12. Was the limit effective on the value date? `limStartDate` and `limEndDate` establish
    coverage but not approval.
13. Was a warning threshold confused with a hard limit, or a temporary/initial bound used
    without valid precedence and effective dates?
14. Is a current-versus-initial difference presented only as a change candidate? Require
    lineage, effective date, rationale, and approval before making a governance finding.
15. For breach or proximity claims, are the count, worst and current utilization, first
    and last dates, longest streak, and affected series reproducible?
16. Does a repeated streak survive duplicate removal, missing dates, limit changes, and
    observations that are consecutive only because of an extract gap?

## Metric behavior

17. Is the outlier, jump, trend, level shift, or volatility change calculated within one
    comparable portfolio/metric/unit/version series with an adequate population?
18. Is a single observation being called systemic? Check persistence, reversal, other
    portfolios, and later periods.
19. Could the pattern reflect a market move, new or closed business, model/version
    change, hierarchy remap, hedging, expiry, rebalancing, data delay, or scenario update?
20. Are VaR/SVaR or stress/VaR comparisons aligned by date and portfolio, and are their
    methodology differences clearly qualified?
21. Is a statistical threshold being confused with desk materiality? Relate the signal
    to utilization, duration, affected scope, stress severity, PnL, or control impact.

## Excess workflow and governance

22. Does the record itself support that it is open, closed, validated, satisfactory, or
    manually closed? Reconcile boolean, status, close dates, and validation fields.
23. Is `usage` reproduced from value and limit within stated rounding, and is
    `excessMaxUsage` at least as severe as the recorded last consumption?
24. Are creation, explanation, validation, LoD2, deadline, and closure timestamps ordered
    logically? Distinguish data inconsistency from policy breach.
25. Is a timeliness conclusion based on a documented SLA, business calendar, timezone,
    and event class? Otherwise report the measured lag without calling it late.
26. For an apparently overdue open item, is the extract's as-of state current, and is
    there later closure, accepted risk, waiver, or superseding event evidence?
27. Are repeated events genuinely comparable by perimeter, metric, limit, underlying,
    cause, and time, or are unrelated excesses being collapsed into one pattern?
28. Are explanation, action, owner, deadline, validation, and LoD2 fields required for
    this workflow state and classification? Do not convert every optional blank into a
    control failure.
29. For a limit increase, do the ID, requested bound, effective date, trader/risk approval,
    and relationship to the excess all exist? Timestamps alone do not prove retrospective
    treatment.

## Cross-source and severity

30. Do limit definitions agree on PC/perimeter, risk indicator, metric name, unit, bound,
    type, owner, and relevant date? Explain benign system-label differences.
31. Does the claimed event-to-SGMR match use a documented unique key? If semantic matching
    returns several portfolios, keep row-level reconciliation unresolved.
32. Is a missing daily match explained by weekend/holiday dates, review-period boundaries,
    source cadence, or an actual in-period business-date gap?
33. Does another source contradict the conclusion or provide a benign explanation such
    as approved business, a temporary limit, hedge, market event, or resolved action?
34. Is severity proportionate to utilization, duration, recurrence, scope, regulatory or
    capital consequence, open control state, and evidence strength? An isolated excess is
    not automatically high severity, and a workflow-data inconsistency is not a risk loss.
35. Is causation or intent inferred from timing, co-movement, machine-generated text, or
    missing evidence? Remove unsupported causal and misconduct language.

Decide `PASS`, `REVISE`, `REJECT`, or `UNRESOLVED`. Never pass inaccessible evidence,
non-reproducible numbers, mixed-grain totals, assumed state meanings, invented SLAs,
unproven identifier joins, or inflated severity.
