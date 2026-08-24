# PnL Review and Verification Policy

Use these challenges for every candidate conclusion.

## Deterministic screening defaults

These are reproducible candidate-selection settings, not desk materiality or severity
thresholds:

| Screen | Default |
| --- | --- |
| PnL series coverage | Flag below 95% of observed dates for the same Version, Notion, and currency population |
| Cumulative re-performance | Tolerance is the greater of `0.00001` source units and one part per million of expected accumulated PnL |
| Statistical population | At least 20 comparable observations |
| Large DTD | Absolute population z-score at least 3.0 |
| DTD reversal | Consecutive opposite signs; both absolute z-scores at least 2.0; magnitude ratio 0.5–1.5 |
| Same-sign run | At least five consecutive observed values |
| PnL period-end concentration | At least three observed month ends and mean absolute month-end DTD at least twice other dates |
| Adjustment EUR conversion | Tolerance is the greater of EUR 0.01 and one part per hundred million of expected EUR amount |
| Large adjustment | At least five adjustments and absolute EUR z-score at least 2.5 |
| Rapid adjustment reversal | Same link, or same PTF/component/currency when no link; opposite signs within five calendar days; magnitude ratio 0.8–1.25 |
| Adjustment period-end proxy | At least three monthly adjustments, at least two with valuation day 28 or later, representing at least 50% of absolute monthly EUR amount |

The runner emits at most 50 representative flags per result while retaining population
counts in its tables. If the cap is reached, verify the unrepresented population or mark
coverage unresolved; do not infer that later candidates are immaterial.

## Evidence and population

1. Can every cited row be reopened from the current manifest, and does it contain the
   stated date, entity, version, notion, currency, state, or amount?
2. Is the population complete for the claimed period, or were files, sheets, portfolios,
   dates, versions, notions, PnL types, teams, or inactive history excluded?
3. Does a duplicate represent bad data, a legitimate history/version, or a missing key
   dimension?
4. Are comparisons made within the same PTF, Version, Notion, currency, and date basis?

## PnL calculations and patterns

5. Can WTD, MTD, QTD, and YTD be reproduced from DTD with the documented reset rules?
6. For a large move, what distribution, minimum population, and threshold produced the
   candidate? Is it material in desk context or merely statistically unusual?
7. For a reversal, are both legs in the same comparable series, on consecutive observed
   business dates, opposite in sign, and similar enough in magnitude?
8. For a persistent run or volatility change, is the result robust to missing dates,
   portfolio mix, new activity, and one dominant outlier?
9. For a period-end pattern, was the last observed business date determined separately
   for each month and compared with other dates in the same population?
10. Does another source document a benign market move, accrual, freeze, correction, or
    valuation event? Contemporaneous occurrence alone does not establish causation.

## Adjustments

11. Do `AMOUNT`, `EXCHANGERATE`, and `AMOUNTINEUR` reperform within rounding tolerance,
    and is the currency mapping consistent with the PnL hierarchy?
12. Are valuation start/end dates ordered and is creation timing assessed against an
    applicable SLA rather than an invented deadline?
13. Are period-end adjustments expected for their nature and component? Concentration is
    a candidate pattern, not evidence of smoothing or manipulation.
14. Does a reversal share a PTF, component or link, valuation basis, and documented
    purpose? Similar opposite amounts across unrelated portfolios are not a reversal.
15. Which supporting fields are mandatory for this adjustment type? Do not treat all
    blank optional identifiers as missing approval evidence.

## Validation history

16. Is `api_request_date` used as the PnL population date and `creationTime` used only for
    record timing?
17. Are multiple active rows present for the same GOP, team, request date, and PnL type?
18. Does the governing state dictionary identify the state as final, pending, failed, or
    informational? If not, describe the state and keep the conclusion unresolved.
19. Were FLASH, STAB, and other PnL types assessed against their own cadence and deadline?
20. Does apparent persistence reflect repeated snapshots of the same open item, a daily
    obligation, or separate events? State counts alone cannot answer that question.
21. Does the deterministic persistence table describe consecutive observed active
    records only? A long run is not overdue until the state dictionary and cadence say so.

## Cross-source and severity

22. Do PTF-to-GOP, PC, region, and currency mappings agree on the effective dates?
23. Are validation-only or PnL-only GOPs true coverage gaps, or different scoped
    populations? Cite evidence from both populations where available.
24. Is a monetary comparison valid in common units and on the same pre/post-adjustment
    basis? If unit or inclusion definitions are missing, mark it `UNRESOLVED`.
25. Is the severity proportional to magnitude, duration, recurrence, affected scope,
    control consequence, and contrary evidence? Never infer intent or misconduct.

## Wide income-attribution challenges

26. Does the file actually match the wide AIR contract (`asofdate`, hierarchy, and
    `Final Result Acc DTD`), and were invalid rows or unrecognized columns disclosed?
27. Are driver shares calculated from a clearly stated population and denominator? Do
    not add parent and leaf fields, or present the primary-bucket profile as a desk-total
    reconciliation.
28. Does `Final Result Acc DTD Cumulative` equal the sum of DTD totals within the same
    hierarchy series and date population, within the stated tolerance? Check missing
    dates, duplicate hierarchy rows, resets, and the actual source units first.
29. What do `status`, `validated`, `isbatchvalidated`, MPC, and FO fields mean in the
    governing workflow? A running, blank, or non-final label is unresolved workflow
    evidence until its state dictionary, owner, cadence, and later history are known.
30. Does a large unexplained/other/no-attribution share persist across comparable dates
    and entities, or is it a legitimate bucket, a temporary process state, or a taxonomy
    change? Do not infer an attribution error from the name alone.

Decide `PASS`, `REVISE`, `REJECT`, or `UNRESOLVED`. Never pass inaccessible evidence,
non-reproducible calculations, mixed-unit totals, assumed state meanings, or unsupported
causal language.
