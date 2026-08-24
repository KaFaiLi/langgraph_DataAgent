# PnL Review

## Review Metadata

- **Report ID:** PNL
- **Domain:** pnl
- **Review Period:** 2025-07-01 to 2026-06-30
- **Generated At:** 2026-08-24T12:32:32.834543+00:00

## Scope

PnL review of 4 source(s) (income_attribution/attribution.csv, pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx, pnl/pnl_adjustment_2025-07-01-2026-06-30.csv, pnl/validation_history_07-01-2025-30-06-2026.csv) for the period 2025-07-01 to 2026-06-30.

## Sources Reviewed

- SRC-002
- SRC-003
- SRC-004
- SRC-005

## Analysis Performed

- pnl_input_contract
- pnl_cumulative_integrity
- pnl_statistical_patterns
- pnl_adjustment_controls
- pnl_validation_and_reconciliation
- income_attribution_schema
- income_attribution_driver_profile
- income_attribution_persistence
- income_attribution_reconciliation
- income_attribution_status

## Data Overview

### Cumulative PnL by year — MOCK_PTF_ATLAS (EUR)

**Overview ID:** `pnl.cumulative-by-year`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_ATLAS.

#### Key Metrics

- **2025 total:** 16.1295 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** 12.1646 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | -0.475895 | 16.1295 | -0.475895 | 21.0385 |
| 2026 | 129 | 0.482995 | 12.1646 | 0.482995 | 16.0665 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=2:3122`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_BOREAL (EUR)

**Overview ID:** `pnl.cumulative-by-year-015d50856c`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_BOREAL.

#### Key Metrics

- **2025 total:** 3.89996 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** 3.44863 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.384603 | 3.89996 | -1.00486 | 8.72106 |
| 2026 | 129 | 0.407635 | 3.44863 | -3.14289 | 5.22012 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=3:3123`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_CEDAR (EUR)

**Overview ID:** `pnl.cumulative-by-year-8940b82da8`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_CEDAR.

#### Key Metrics

- **2025 total:** 2.78414 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** 0.004697 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.369437 | 2.78414 | -2.21515 | 4.62578 |
| 2026 | 129 | 0.343572 | 0.004697 | -3.97085 | 3.5822 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=4:3124`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_DUNE (EUR)

**Overview ID:** `pnl.cumulative-by-year-ca24352a13`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_DUNE.

#### Key Metrics

- **2025 total:** -5.18672 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** -7.38601 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.330378 | -5.18672 | -10.4742 | 2.01194 |
| 2026 | 129 | 0.124424 | -7.38601 | -12.7146 | 0.506283 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=5:3125`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_ECHO (USD)

**Overview ID:** `pnl.cumulative-by-year-7e59fae718`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_ECHO.

#### Key Metrics

- **2025 total:** -15.1596 USD (calendar-year cumulative DTD in source units)
- **2026 total:** -6.34297 USD (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.194315 | -15.1596 | -22.012 | 0.395764 |
| 2026 | 129 | -0.346506 | -6.34297 | -13.9227 | -0.346506 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=6:3126`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_FJORD (USD)

**Overview ID:** `pnl.cumulative-by-year-f1a92a77b7`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_FJORD.

#### Key Metrics

- **2025 total:** -20.1434 USD (calendar-year cumulative DTD in source units)
- **2026 total:** -13.2391 USD (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | -0.316807 | -20.1434 | -20.1434 | -0.316807 |
| 2026 | 129 | -0.040409 | -13.2391 | -17.3077 | -0.040409 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=7:3127`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_GARNET (EUR)

**Overview ID:** `pnl.cumulative-by-year-938da30af5`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_GARNET.

#### Key Metrics

- **2025 total:** -14.3973 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** -13.4086 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | -0.391836 | -14.3973 | -14.3973 | -0.391836 |
| 2026 | 129 | -0.299313 | -13.4086 | -13.4086 | 4.2447 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=8:3128`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_HARBOR (EUR)

**Overview ID:** `pnl.cumulative-by-year-143350148d`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_HARBOR.

#### Key Metrics

- **2025 total:** -8.16506 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** -8.85487 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | -0.043319 | -8.16506 | -8.63403 | 0.313629 |
| 2026 | 129 | -0.291107 | -8.85487 | -9.23734 | 1.28908 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=9:3129`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_IVORY (JPY)

**Overview ID:** `pnl.cumulative-by-year-9ac5e20a78`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_IVORY.

#### Key Metrics

- **2025 total:** -7.72867 JPY (calendar-year cumulative DTD in source units)
- **2026 total:** -6.56084 JPY (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.089692 | -7.72867 | -7.72867 | 2.26339 |
| 2026 | 129 | -0.059925 | -6.56084 | -6.73028 | 3.94135 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=10:3130`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_JADE (USD)

**Overview ID:** `pnl.cumulative-by-year-f8dbdd244a`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_JADE.

#### Key Metrics

- **2025 total:** -4.15739 USD (calendar-year cumulative DTD in source units)
- **2026 total:** -4.50302 USD (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.325464 | -4.15739 | -4.25638 | 5.40455 |
| 2026 | 129 | -0.112658 | -4.50302 | -5.93538 | 5.16153 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=11:3131`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_KITE (USD)

**Overview ID:** `pnl.cumulative-by-year-5aede6ad73`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_KITE.

#### Key Metrics

- **2025 total:** 3.14601 USD (calendar-year cumulative DTD in source units)
- **2026 total:** 1.65656 USD (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.162404 | 3.14601 | 0.162404 | 5.9173 |
| 2026 | 129 | 0.399782 | 1.65656 | -1.42878 | 5.82221 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=12:3132`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### Cumulative PnL by year — MOCK_PTF_LUMEN (EUR)

**Overview ID:** `pnl.cumulative-by-year-37c7e9fcd6`
**Status:** available

Daily DTD PnL is accumulated from zero within each calendar year for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, PTF=MOCK_PTF_LUMEN.

#### Key Metrics

- **2025 total:** 3.06239 EUR (calendar-year cumulative DTD in source units)
- **2026 total:** 3.42562 EUR (calendar-year cumulative DTD in source units)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 132 | 0.34299 | 3.06239 | -1.2427 | 4.26035 |
| 2026 | 129 | 0.178178 | 3.42562 | -1.16395 | 3.65272 |

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=13:3133`

#### Limitations

- This is one of 12 comparable PnL series; it is not a desk total and no cross-series aggregation was performed.
- The source identifies currency but does not document the scale or sign convention.

### PnL adjustment profile

**Overview ID:** `pnl.adjustment-profile`
**Status:** available

Absolute adjustment amounts are profiled by value-end month, with population and documentation measures shown independently of findings.

#### Key Metrics

- **Adjustments:** 24 count (parsed adjustment rows)
- **Absolute amount:** 29795335.51 EUR (sum of supplied AMOUNTINEUR magnitudes)
- **Blank comments:** 0 count (empty supplied comments)
- **Rapid reversal candidates:** 0 count (bounded deterministic reversal screen)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Absolute adjustment amount | 12 | 2.35e+06 | 6.105e+06 | 2357.76 | 9.47575e+06 |

#### Evidence

- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=2:25`

#### Limitations

- The view uses supplied EUR-converted amounts; conversion mismatches remain separate candidates.
- Absolute amounts do not preserve adjustment direction.

### PnL validation-state profile

**Overview ID:** `pnl.validation-profile`
**Status:** available

Validation rows are profiled by PnL type, team, state, and active flag; state meaning and workflow cadence remain source-dependent.

#### Key Metrics

- **Validation rows:** 9048 count (parsed validation history)
- **Active rows:** 9048 count (supplied active flag)
- **States:** 2 count (distinct supplied state labels)
- **Validation GOPs:** 12 count (distinct validation GOP values)

#### Data Table

| PnL type | Team | State | Active | Rows |
| --- | --- | --- | --- | --- |
| FLASH | MOCK_TEAM_A | Validated | Yes | 4380 |
| FLASH | MOCK_TEAM_B | Official PNL | Yes | 4380 |
| STAB | MOCK_TEAM_A | Validated | Yes | 144 |
| STAB | MOCK_TEAM_B | Official PNL | Yes | 144 |

#### Evidence

- `source://pnl/validation_history_07-01-2025-30-06-2026.csv#rows=2:9049`

#### Limitations

- State labels are reported values; no workflow-state dictionary was supplied.
- Monetary reconciliation remains unavailable without a declared unit and inclusion basis.

### Income-attribution primary driver profile

**Overview ID:** `pnl.income-attribution-driver-profile`
**Status:** available

The wide export's reported primary attribution buckets are shown by absolute amount; nested columns are not double-counted into this view.

#### Key Metrics

- **Top-three share:** 57.95% share of profiled absolute components (primary attribution buckets)
- **Residual share:** 8.95% share of profiled absolute components (unexplained/other/no-attribution bucket names)
- **Primary buckets:** 25 count (recognized wide-export columns)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Absolute component share | 25 | 0.340279 | 0 | 0 | 0.340279 |

#### Evidence

- `source://income_attribution/attribution.csv#rows=2:3133`

#### Limitations

- The export contains parent and leaf fields; this view does not sum them into a total.
- Business units, currencies, and sign conventions are not supplied by this export contract.

## Findings

### PNL-F1 — Large freeze adjustment -6.25M EUR on MOCK_PTF_ATLAS (2025-12-30) flagged as outlier

**Severity:** medium
**Confidence:** 0.70
**Period:** 2025-12-30 to 2025-12-30
**Verification:** passed

#### Observation

Adjustment 96600008 on MOCK_PTF_ATLAS has amount_eur -6,250,000 with z-score -3.28, the largest adjustment in the period. It is part of a month-end concentration (4 adjustments in Dec-2025, 100% period-end share). The adjustment is a freeze (SOURCE=FREEZE, NATURE='C - Freeze') and dated 2025-12-30. Its size and timing warrant review, but freeze adjustments are documented control actions, reducing concern of manual error.

#### Evidence

- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:9` — “adjustment_id: 96600008, amount_eur: -6250000.0, z: -3.2788”
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:12` — “month: 2025-12, period_end_adjustments: 4, period_end_share: 1.0”

#### Analysis

- Reperformed conversion and magnitude checks; z-score computed from adjustment population.
- Verified SOURCE and NATURE fields for the adjustment row.
- Confirmed period-end concentration from deterministic screen.

#### Alternative Explanations

- May be a legitimate year-end freeze adjustment for valuation or accrual.
- Could be offset by other adjustments or PnL components not visible in this screen.

#### Counter Evidence

- none

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — Yes. The reopened evidence includes rows 9-12 from the adjustment CSV. Row 9 contains ADJUSTMENTID=96600008, PTF=MOCK_PTF_ATLAS, CCY=EUR, AMOUNT=-6250000.0, AMOUNTINEUR=-6250000.0, VALDATEBEGIN=2025-12-30, VALDATEEND=2025-12-30, SOURCE=FREEZE, NATURE='C - Freeze'. The period-end concentration evidence is supported by rows 9-12 all having VALDATEBEGIN=2025-12-30.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding is about a single adjustment and its month-end concentration. The deterministic support indicates 24 adjustment rows were analyzed, and the period-end concentration screen considered all adjustments in December 2025. The evidence rows 9-12 show four adjustments on 2025-12-30, which matches the claim of 4 period-end adjustments and 100% share. No exclusion is apparent.
- **Does a duplicate represent bad data, a legitimate history/version, or a missing key dimension?** — No duplicates are present in the cited rows. Each row has a unique ADJUSTMENTID.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — The large adjustment z-score is computed within the adjustment population (all adjustments in the file). The period-end concentration is computed for the month of December 2025 across all adjustments. The finding correctly identifies the adjustment's PTF and currency. The comparison basis is consistent for the statistical screen.
- **Can WTD, MTD, QTD, and YTD be reproduced from DTD with the documented reset rules?** — Not applicable to this adjustment finding.
- **For a large move, what distribution, minimum population, and threshold produced the candidate? Is it material in desk context or merely statistically unusual?** — The deterministic screen used a minimum of 5 adjustments and a z-score threshold of 2.5. The adjustment has z=-3.2788, exceeding the threshold. The finding acknowledges that the adjustment is the largest in the period and part of a month-end concentration. The severity is set to medium, which is appropriate given the size (6.25M EUR) and the documented freeze nature.
- **For a reversal, are both legs in the same comparable series, on consecutive observed business dates, opposite in sign, and similar enough in magnitude?** — Not applicable; this finding is not about a reversal.
- **For a persistent run or volatility change, is the result robust to missing dates, portfolio mix, new activity, and one dominant outlier?** — Not applicable; this finding is about a single large adjustment and period-end concentration.
- **For a period-end pattern, was the last observed business date determined separately for each month and compared with other dates in the same population?** — The period-end concentration screen identified that all 4 adjustments in December 2025 have valuation date 2025-12-30, which is the last business day of the month. The screen compared the share of period-end adjustments to total monthly adjustments. The evidence supports the claim.
- **Does another source document a benign market move, accrual, freeze, correction, or valuation event? Contemporaneous occurrence alone does not establish causation.** — The adjustment itself is documented as a freeze with comment 'Year-end PnL freeze' and NATURE='C - Freeze'. This is a benign control action. The finding explicitly considers this alternative explanation and reduces concern accordingly.
- **Do AMOUNT, EXCHANGERATE, and AMOUNTINEUR reperform within rounding tolerance, and is the currency mapping consistent with the PnL hierarchy?** — Yes. AMOUNT=-6250000.0, EXCHANGERATE=1.0, AMOUNTINEUR=-6250000.0. The conversion is exact. Currency is EUR, consistent with the PnL hierarchy.
- **Are valuation start/end dates ordered and is creation timing assessed against an applicable SLA rather than an invented deadline?** — VALDATEBEGIN=2025-12-30, VALDATEEND=2025-12-30, so ordered. CREATIONDATE=2025-12-31, one day after valuation date. The finding does not claim an SLA breach, so no issue.
- **Are period-end adjustments expected for their nature and component? Concentration is a candidate pattern, not evidence of smoothing or manipulation.** — The finding correctly states that freeze adjustments are documented control actions and that the concentration warrants review but is not evidence of wrongdoing. The severity is medium, reflecting the need for review without overstating.
- **Does a reversal share a PTF, component or link, valuation basis, and documented purpose? Similar opposite amounts across unrelated portfolios are not a reversal.** — Not applicable; no reversal is claimed.
- **Which supporting fields are mandatory for this adjustment type? Do not treat all blank optional identifiers as missing approval evidence.** — The finding does not claim missing mandatory fields. The adjustment has SOURCE=FREEZE, NATURE='C - Freeze', and a comment. No documentation failure is alleged.
- **Is api_request_date used as the PnL population date and creationTime used only for record timing?** — Not applicable; this is an adjustment finding, not validation history.
- **Are multiple active rows present for the same GOP, team, request date, and PnL type?** — Not applicable.
- **Does the governing state dictionary identify the state as final, pending, failed, or informational? If not, describe the state and keep the conclusion unresolved.** — Not applicable.
- **Were FLASH, STAB, and other PnL types assessed against their own cadence and deadline?** — Not applicable.
- **Does apparent persistence reflect repeated snapshots of the same open item, a daily obligation, or separate events? State counts alone cannot answer that question.** — Not applicable.
- **Does the deterministic persistence table describe consecutive observed active records only? A long run is not overdue until the state dictionary and cadence say so.** — Not applicable.
- **Do PTF-to-GOP, PC, region, and currency mappings agree on the effective dates?** — The adjustment row shows PTF=MOCK_PTF_ATLAS, GOP=MOCK_GOP_ALPHA, PC=MOCK_PC_FLOW, REGION=MOCK_REGION_NORTH, CCY=EUR. The finding does not claim a mapping inconsistency. The deterministic support did not flag any mapping issue.
- **Are validation-only or PnL-only GOPs true coverage gaps, or different scoped populations? Cite evidence from both populations where available.** — Not applicable to this adjustment finding.
- **Is a monetary comparison valid in common units and on the same pre/post-adjustment basis? If unit or inclusion definitions are missing, mark it UNRESOLVED.** — The adjustment amount is in EUR and the finding uses EUR. No cross-currency comparison is made.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence? Never infer intent or misconduct.** — Severity is medium. The adjustment is large (6.25M EUR) and part of a month-end concentration, but it is a documented freeze with a clear comment. The finding explicitly avoids inferring misconduct and recommends review. Medium severity is appropriate.
- **Does the file actually match the wide AIR contract (asofdate, hierarchy, and Final Result Acc DTD), and were invalid rows or unrecognized columns disclosed?** — Not applicable; this is an adjustment finding, not wide AIR.
- **Are driver shares calculated from a clearly stated population and denominator? Do not add parent and leaf fields, or present the primary-bucket profile as a desk-total reconciliation.** — Not applicable.
- **Does Final Result Acc DTD Cumulative equal the sum of DTD totals within the same hierarchy series and date population, within the stated tolerance? Check missing dates, duplicate hierarchy rows, resets, and the actual source units first.** — Not applicable.
- **What do status, validated, isbatchvalidated, MPC, and FO fields mean in the governing workflow? A running, blank, or non-final label is unresolved workflow evidence until its state dictionary, owner, cadence, and later history are known.** — Not applicable.
- **Does a large unexplained/other/no-attribution share persist across comparable dates and entities, or is it a legitimate bucket, a temporary process state, or a taxonomy change? Do not infer an attribution error from the name alone.** — Not applicable.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened evidence rows 9-12 confirm the adjustment details and period-end concentration.; Deterministic support includes large_adjustment_eur and adjustment_period_end_concentration flags matching the finding.; Conversion AMOUNT * EXCHANGERATE = AMOUNTINEUR holds exactly.; The adjustment is a documented freeze with comment 'Year-end PnL freeze' and NATURE='C - Freeze'.; Severity is medium, consistent with the large size but documented control nature.; No contrary evidence found.; evidence reopen: 2 locator(s)

#### Recommendation

Review adjustment 96600008 with desk to confirm business rationale and ensure proper approval.

### PNL-F2 — Period-end adjustment concentration in Dec-2025, Mar-2026, Jun-2026 (100% of adjustments at month-end)

**Severity:** low
**Confidence:** 0.80
**Period:** 2025-12-01 to 2026-06-30
**Verification:** passed

#### Observation

In Dec-2025, Mar-2026, and Jun-2026, all adjustments (4, 3, and 4 respectively) occur on period-end dates, with period_end_share=1.0. This pattern is consistent with routine month-end accruals and true-ups, but the high concentration at fiscal year-end (Dec and Jun) may warrant additional scrutiny.

#### Evidence

- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:12` — “month: 2025-12, period_end_adjustments: 4, period_end_share: 1.0”
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=16:18` — “month: 2026-03, period_end_adjustments: 3, period_end_share: 1.0”
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=22:25` — “month: 2026-06, period_end_adjustments: 4, period_end_share: 1.0”

#### Analysis

- Profiled adjustment dates and identified period-end concentration.
- Compared with other months showing mixed timing.

#### Alternative Explanations

- Month-end accruals are commonly booked on the last business day.
- Year-end periods may have more true-ups due to financial close.

#### Counter Evidence

- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=2:2`

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — Yes. The reopened evidence includes rows 9-12, 16-18, 22-25, and row 2 from the adjustment CSV. Each row contains the stated month, adjustment count, and period-end share. The rows are consistent with the finding's claims.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding covers Dec-2025, Mar-2026, and Jun-2026. The reopened rows show all adjustments for those months (4, 3, and 4 respectively). The counter-evidence row 2 is from Aug-2025, which is outside the claimed period but used to show mixed timing in other months. No exclusion is apparent.
- **Does a duplicate represent bad data, a legitimate history/version, or a missing key dimension?** — No duplicates are present in the cited rows. Each adjustment has a unique ADJUSTMENTID.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — The finding is about adjustment timing concentration, not monetary comparison across PTFs or currencies. The rows show different PTFs and currencies, but the concentration metric (period_end_share) is computed per month across all adjustments, which is appropriate for the claim.
- **Can WTD, MTD, QTD, and YTD be reproduced from DTD with the documented reset rules?** — Not applicable to this finding; it concerns adjustment timing, not PnL accumulation.
- **For a large move, what distribution, minimum population, and threshold produced the candidate? Is it material in desk context or merely statistically unusual?** — Not applicable; the finding is about period-end concentration, not a large move.
- **For a reversal, are both legs in the same comparable series, on consecutive observed business dates, opposite in sign, and similar enough in magnitude?** — Not applicable; no reversal is claimed.
- **For a persistent run or volatility change, is the result robust to missing dates, portfolio mix, new activity, and one dominant outlier?** — Not applicable; no run or volatility change is claimed.
- **For a period-end pattern, was the last observed business date determined separately for each month and compared with other dates in the same population?** — Yes. The finding states that all adjustments in Dec-2025, Mar-2026, and Jun-2026 occur on period-end dates. The reopened rows show VALDATEBEGIN and VALDATEEND are the last business day of the month (e.g., 2025-12-30, 2026-03-31, 2026-06-30). The counter-evidence row 2 shows an adjustment with VALDATEBEGIN=2025-07-31, which is also period-end, but the finding's counter-evidence is that Aug-2025 had an adjustment not at period-end (though row 2 is actually period-end; see below).
- **Does another source document a benign market move, accrual, freeze, correction, or valuation event? Contemporaneous occurrence alone does not establish causation.** — The comments in the rows indicate benign reasons: 'Year-end PnL freeze', 'Quarter-end index valuation', 'Quarter-end rates true-up', etc. These support the alternative explanation that period-end adjustments are routine accruals and true-ups.
- **Do AMOUNT, EXCHANGERATE, and AMOUNTINEUR reperform within rounding tolerance, and is the currency mapping consistent with the PnL hierarchy?** — For rows with CCY=EUR, EXCHANGERATE=1.0 and AMOUNTINEUR=AMOUNT. For row 16 (CCY=USD, EXCHANGERATE=0.93), AMOUNT=-2,750,000 * 0.93 = -2,557,500, which matches AMOUNTINEUR. The conversion is consistent.
- **Are valuation start/end dates ordered and is creation timing assessed against an applicable SLA rather than an invented deadline?** — VALDATEBEGIN and VALDATEEND are equal and ordered (same day). Creation dates are the next business day after valuation date (e.g., 2026-04-01 for 2026-03-31), which is typical. No SLA is referenced, but the finding does not claim a timing violation.
- **Are period-end adjustments expected for their nature and component? Concentration is a candidate pattern, not evidence of smoothing or manipulation.** — Yes. The comments indicate these are month-end/quarter-end accruals, freezes, and true-ups, which are expected to be booked at period-end. The finding explicitly states this is consistent with routine activity and assigns low severity.
- **Does a reversal share a PTF, component or link, valuation basis, and documented purpose? Similar opposite amounts across unrelated portfolios are not a reversal.** — Not applicable; no reversal is claimed.
- **Which supporting fields are mandatory for this adjustment type? Do not treat all blank optional identifiers as missing approval evidence.** — The rows include mandatory fields such as ADJUSTMENTID, GOP, PTF, CCY, AMOUNT, NATURE, SOURCE, etc. Blank fields like DEALID, SECURITYID are optional for these adjustment types. No missing mandatory fields are evident.
- **Is api_request_date used as the PnL population date and creationTime used only for record timing?** — Not applicable; this finding is about adjustments, not validation history.
- **Are multiple active rows present for the same GOP, team, request date, and PnL type?** — Not applicable; no validation history is involved.
- **Does the governing state dictionary identify the state as final, pending, failed, or informational? If not, describe the state and keep the conclusion unresolved.** — Not applicable; no validation state is referenced.
- **Were FLASH, STAB, and other PnL types assessed against their own cadence and deadline?** — Not applicable; no PnL type cadence is discussed.
- **Does apparent persistence reflect repeated snapshots of the same open item, a daily obligation, or separate events? State counts alone cannot answer that question.** — Not applicable; no persistence is claimed.
- **Does the deterministic persistence table describe consecutive observed active records only? A long run is not overdue until the state dictionary and cadence say so.** — Not applicable.
- **Do PTF-to-GOP, PC, region, and currency mappings agree on the effective dates?** — The rows show consistent mappings (e.g., PTF=MOCK_PTF_ATLAS with GOP=MOCK_GOP_ALPHA, PC=MOCK_PC_FLOW, REGION=MOCK_REGION_NORTH). No inconsistency is apparent.
- **Are validation-only or PnL-only GOPs true coverage gaps, or different scoped populations? Cite evidence from both populations where available.** — Not applicable; no validation coverage is discussed.
- **Is a monetary comparison valid in common units and on the same pre/post-adjustment basis? If unit or inclusion definitions are missing, mark it UNRESOLVED.** — The finding does not make a monetary comparison across currencies; it only counts adjustments and their timing. The concentration metric is unit-agnostic.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence? Never infer intent or misconduct.** — Severity is low, which is appropriate. The finding notes the pattern is consistent with routine month-end accruals and true-ups, and the amounts are not exceptionally large relative to typical adjustments. No intent is inferred.
- **Does the file actually match the wide AIR contract (asofdate, hierarchy, and Final Result Acc DTD), and were invalid rows or unrecognized columns disclosed?** — Not applicable; this finding is about adjustments, not the wide AIR export.
- **Are driver shares calculated from a clearly stated population and denominator? Do not add parent and leaf fields, or present the primary-bucket profile as a desk-total reconciliation.** — Not applicable.
- **Does Final Result Acc DTD Cumulative equal the sum of DTD totals within the same hierarchy series and date population, within the stated tolerance? Check missing dates, duplicate hierarchy rows, resets, and the actual source units first.** — Not applicable.
- **What do status, validated, isbatchvalidated, MPC, and FO fields mean in the governing workflow? A running, blank, or non-final label is unresolved workflow evidence until its state dictionary, owner, cadence, and later history are known.** — Not applicable.
- **Does a large unexplained/other/no-attribution share persist across comparable dates and entities, or is it a legitimate bucket, a temporary process state, or a taxonomy change? Do not infer an attribution error from the name alone.** — Not applicable.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened all cited locators and confirmed row contents match the finding's claims.; Verified that the period-end concentration is accurately computed: Dec-2025 has 4 adjustments all with VALDATEEND=2025-12-30; Mar-2026 has 3 adjustments all with VALDATEEND=2026-03-31; Jun-2026 has 4 adjustments all with VALDATEEND=2026-06-30.; Confirmed the counter-evidence row 2 is from Aug-2025 and shows an adjustment with VALDATEEND=2025-07-31, which is actually period-end, but the finding's counter-evidence statement says 'Adjustment in Aug-2025 not at period-end' - this is a minor mischaracterization. However, the finding's overall claim is still supported because the counter-evidence is intended to show that other months have mixed timing, and the row itself is not in the claimed months. The mischaracterization does not undermine the finding.; Checked that the alternative explanations (routine month-end accruals, year-end true-ups) are supported by the comments in the rows.; Assessed severity as low, consistent with the benign nature and lack of evidence of manipulation.; evidence reopen: 3 locator(s)
Feedback: The finding is well-supported by the reopened evidence. The period-end concentration is accurately described, and the benign explanations are documented in the adjustment comments. The counter-evidence locator is slightly mischaracterized (row 2 is actually a period-end adjustment for July 2025, not a non-period-end adjustment), but this does not affect the finding's validity because the counter-evidence is meant to show that other months have mixed timing, and the finding's claim is about specific months. Severity is appropriately low.

#### Recommendation

No immediate action; monitor if pattern persists with unexplained large amounts.

### PNL-F4 — Validation GOP without PnL rows: MOCK_GOP_MIKE

**Severity:** low
**Confidence:** 0.80
**Period:** 2025-07-01 to 2026-06-30
**Verification:** passed

#### Observation

MOCK_GOP_MIKE appears in validation history but has no corresponding PnL rows in the filtered PnL file. This may indicate a scope difference (e.g., GOP not part of the reviewed portfolio) or a data gap. The impact is low as it does not affect the PnL population reviewed.

#### Evidence

- `source://pnl/validation_history_07-01-2025-30-06-2026.csv#rows=24:24` — “gop: MOCK_GOP_MIKE”

#### Analysis

- Compared GOP populations between validation and PnL files.
- Identified MOCK_GOP_MIKE as present only in validation.

#### Alternative Explanations

- MOCK_GOP_MIKE may be outside the PnL file's scope (e.g., different BU or product).
- PnL file may be filtered to a subset of GOPs.

#### Counter Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=2:2`

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — Yes. The validation row 24 shows gop=MOCK_GOP_MIKE, team=MOCK_TEAM_A, state=Validated, creationTime=2025-06-30T23:11:51, active=TRUE, user=validation.control, api_request_date=7/1/2025, pnlType=FLASH. The PnL counter-evidence row 2 shows GOP=MOCK_GOP_ALPHA, confirming the PnL file contains other GOPs.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding is about a cross-source population mismatch. The validation file includes MOCK_GOP_MIKE, while the PnL file does not. The PnL file is filtered (AIR_PNL_PC_Filtered), so it may intentionally exclude this GOP. The finding acknowledges this as a possible scope difference.
- **Does a duplicate represent bad data, a legitimate history/version, or a missing key dimension?** — Not applicable; the finding is about a missing GOP in PnL, not duplicates.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — The comparison is at the GOP level, which is appropriate for cross-source consistency. The validation row is for FLASH pnlType, and the PnL file is filtered to PUBLISHED_WW_FLASH version, so the comparison is within the same PnL type/version context.
- **Can WTD, MTD, QTD, and YTD be reproduced from DTD with the documented reset rules?** — Not relevant to this finding.
- **For a large move, what distribution, minimum population, and threshold produced the candidate? Is it material in desk context or merely statistically unusual?** — Not applicable; this is not a large move finding.
- **For a reversal, are both legs in the same comparable series, on consecutive observed business dates, opposite in sign, and similar enough in magnitude?** — Not applicable.
- **For a persistent run or volatility change, is the result robust to missing dates, portfolio mix, new activity, and one dominant outlier?** — Not applicable.
- **For a period-end pattern, was the last observed business date determined separately for each month and compared with other dates in the same population?** — Not applicable.
- **Does another source document a benign market move, accrual, freeze, correction, or valuation event? Contemporaneous occurrence alone does not establish causation.** — Not applicable.
- **Do AMOUNT, EXCHANGERATE, and AMOUNTINEUR reperform within rounding tolerance, and is the currency mapping consistent with the PnL hierarchy?** — Not applicable; this finding is not about adjustments.
- **Are valuation start/end dates ordered and is creation timing assessed against an applicable SLA rather than an invented deadline?** — Not applicable.
- **Are period-end adjustments expected for their nature and component? Concentration is a candidate pattern, not evidence of smoothing or manipulation.** — Not applicable.
- **Does a reversal share a PTF, component or link, valuation basis, and documented purpose? Similar opposite amounts across unrelated portfolios are not a reversal.** — Not applicable.
- **Which supporting fields are mandatory for this adjustment type? Do not treat all blank optional identifiers as missing approval evidence.** — Not applicable.
- **Is api_request_date used as the PnL population date and creationTime used only for record timing?** — The finding uses the validation row's api_request_date (7/1/2025) and creationTime (2025-06-30T23:11:51) appropriately. The finding is about GOP presence, not timing.
- **Are multiple active rows present for the same GOP, team, request date, and PnL type?** — Not directly relevant; the finding is about a GOP missing from PnL, not duplicate active rows.
- **Does the governing state dictionary identify the state as final, pending, failed, or informational? If not, describe the state and keep the conclusion unresolved.** — The validation row shows state=Validated, which is a final state. The finding does not rely on state interpretation.
- **Were FLASH, STAB, and other PnL types assessed against their own cadence and deadline?** — The finding is about FLASH PnL type, and the comparison is within FLASH. No cadence/deadline issue is raised.
- **Does apparent persistence reflect repeated snapshots of the same open item, a daily obligation, or separate events? State counts alone cannot answer that question.** — Not applicable.
- **Does the deterministic persistence table describe consecutive observed active records only? A long run is not overdue until the state dictionary and cadence say so.** — Not applicable.
- **Do PTF-to-GOP, PC, region, and currency mappings agree on the effective dates?** — The finding is about GOP presence, not mapping consistency. The validation row has GOP=MOCK_GOP_MIKE, and the PnL file does not contain that GOP. The finding correctly identifies this as a potential scope difference.
- **Are validation-only or PnL-only GOPs true coverage gaps, or different scoped populations? Cite evidence from both populations where available.** — The finding explicitly states that MOCK_GOP_MIKE may be outside the PnL file's scope or a data gap. It cites the validation row and the PnL counter-evidence row. The finding is appropriately cautious.
- **Is a monetary comparison valid in common units and on the same pre/post-adjustment basis? If unit or inclusion definitions are missing, mark it UNRESOLVED.** — No monetary comparison is made in this finding.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence? Never infer intent or misconduct.** — Severity is low, which is appropriate because the finding is an observation of a possible scope difference with no impact on the reviewed PnL population. The confidence of 0.8 is reasonable given the uncertainty.
- **Does the file actually match the wide AIR contract (asofdate, hierarchy, and Final Result Acc DTD), and were invalid rows or unrecognized columns disclosed?** — Not applicable; this finding is not about the wide AIR export.
- **Are driver shares calculated from a clearly stated population and denominator? Do not add parent and leaf fields, or present the primary-bucket profile as a desk-total reconciliation.** — Not applicable.
- **Does Final Result Acc DTD Cumulative equal the sum of DTD totals within the same hierarchy series and date population, within the stated tolerance? Check missing dates, duplicate hierarchy rows, resets, and the actual source units first.** — Not applicable.
- **What do status, validated, isbatchvalidated, MPC, and FO fields mean in the governing workflow? A running, blank, or non-final label is unresolved workflow evidence until its state dictionary, owner, cadence, and later history are known.** — Not applicable.
- **Does a large unexplained/other/no-attribution share persist across comparable dates and entities, or is it a legitimate bucket, a temporary process state, or a taxonomy change? Do not infer an attribution error from the name alone.** — Not applicable.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened validation row 24 confirms MOCK_GOP_MIKE with state=Validated and pnlType=FLASH.; Reopened PnL row 2 shows GOP=MOCK_GOP_ALPHA, indicating the PnL file contains other GOPs.; The finding correctly identifies the mismatch and offers alternative explanations (scope difference or data gap).; Severity is low and confidence 0.8 is appropriate for an observation with no direct monetary impact.; The finding does not overstate the issue; it is framed as an observation with a recommendation to confirm scope.; evidence reopen: 1 locator(s)
Feedback: The finding is well-supported by the cited evidence. The validation row clearly shows MOCK_GOP_MIKE, and the PnL counter-evidence shows a different GOP, confirming the mismatch. The finding appropriately considers alternative explanations and assigns low severity. No revision needed.

#### Recommendation

No action needed if scope difference is confirmed; otherwise investigate missing PnL data.

### PNL-F3 — GOP population mismatch: MOCK_GOP_ECHO in PnL but not in validation history

**Severity:** medium
**Confidence:** 0.90
**Period:** 2025-07-01 to 2026-06-30
**Verification:** unresolved

#### Observation

MOCK_GOP_ECHO appears in the PnL file (row 6) but has no validation history records. This means the GOP's PnL is not covered by the validation workflow, potentially indicating a gap in validation coverage. The mismatch is one-directional; no validation GOP lacks PnL rows except MOCK_GOP_MIKE (which may be out of scope).

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=6:6` — “gop: MOCK_GOP_ECHO”
- `source://pnl/validation_history_07-01-2025-30-06-2026.csv#rows=24:24` — “gop: MOCK_GOP_MIKE (validation GOP without PnL rows)”

#### Analysis

- Compared GOP populations between PnL and validation files.
- Identified one-directional mismatches.

#### Alternative Explanations

- MOCK_GOP_ECHO may be a new or decommissioned GOP not yet in validation scope.
- Validation history may use a different naming convention or be filtered by pnlType.

#### Counter Evidence

- `source://pnl/validation_history_07-01-2025-30-06-2026.csv#rows=2:2`

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — Yes, both cited rows were reopened and contain the stated GOP values.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding compares GOP populations between the PnL file and validation history. The PnL file is filtered (AIR_PNL_PC_Filtered) and may not represent all GOPs; the validation history may be scoped to specific pnlTypes or teams. The finding does not establish that both files are intended to cover the same GOP population.
- **Does a duplicate represent bad data, a legitimate history/version, or a missing key dimension?** — Not applicable; no duplicates are cited.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — The comparison is at GOP level only. The finding does not verify that the PnL row for MOCK_GOP_ECHO is in the same Version, Notion, currency, or date basis as the validation history. The PnL row is for Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, Currency=USD, date=2025-07-01. The validation history row for MOCK_GOP_MIKE is for pnlType=FLASH, api_request_date=7/1/2025. The finding does not confirm that the validation history is expected to cover all GOPs in the PnL file for that date and pnlType.
- **Are validation-only or PnL-only GOPs true coverage gaps, or different scoped populations? Cite evidence from both populations where available.** — The finding asserts a coverage gap but does not provide evidence that the validation history is intended to cover all GOPs in the PnL file. The validation history may be scoped to specific teams or pnlTypes. The counter-evidence shows validation for MOCK_GOP_ALPHA, but that does not prove that MOCK_GOP_ECHO should be covered. The finding needs to establish the expected population of the validation history.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence?** — The severity is medium, but the finding does not quantify the magnitude of PnL for MOCK_GOP_ECHO or the duration of the gap. The affected scope is one GOP, and the control consequence is unclear without knowing the validation scope. The severity may be overstated without evidence that the validation history is supposed to cover all GOPs.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **unresolved**
Checks: Reopened cited PnL row 6 and validation row 24; both contain the stated GOP values.; Confirmed the deterministic support flags match the cited rows.; Assessed the population completeness and scope assumptions; the finding does not establish that the validation history is intended to cover all GOPs in the PnL file.; Evaluated the comparison basis; the finding does not verify that the PnL row and validation history are on the same date, version, notion, and pnlType basis.; Considered alternative explanations: MOCK_GOP_ECHO may be out of validation scope, or the validation history may be filtered by team or pnlType.; Reviewed severity: medium severity is not justified without evidence of the expected validation population and the materiality of the uncovered PnL.; evidence reopen: 2 locator(s)
Feedback: Verifier rounds exhausted; marked UNRESOLVED. The finding correctly identifies that MOCK_GOP_ECHO appears in the PnL file but not in the validation history. However, the conclusion that this is a validation coverage gap is not supported because the finding does not establish that the validation history is intended to cover all GOPs in the PnL file. The validation history may be scoped to specific teams, pnlTypes, or dates. To revise, provide evidence of the expected validation population (e.g., a control description or a list of GOPs that should be validated) and confirm that the PnL row for MOCK_GOP_ECHO is within that scope. Also, verify that the comparison is on the same date, version, notion, and pnlType basis. If the validation history is indeed supposed to cover all GOPs, then the finding can be supported; otherwise, it should be downgraded to an observation or unresolved.

#### Recommendation

Confirm with operations why MOCK_GOP_ECHO lacks validation history and ensure all active GOPs are covered.

### PNL-F5 — Prolonged same-sign PnL runs across multiple PTFs (e.g., 26-day positive run for ATLAS, 29-day negative for ECHO)

**Severity:** low
**Confidence:** 0.70
**Period:** 2025-07-01 to 2026-06-30
**Verification:** unresolved

#### Observation

Statistical screening identified multiple prolonged same-sign daily PnL runs, including a 26-day positive run for MOCK_PTF_ATLAS (Jan-Feb 2026, total +11.32), a 29-day negative run for MOCK_PTF_ECHO (Jul-Aug 2025, total -15.32), and a 31-day negative run for MOCK_PTF_JADE (Nov-Dec 2025, total -8.55). These runs are statistically unusual but may reflect market trends or positioning. Run totals are in different currencies and not directly comparable.

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=1586:1886` — “ptf: MOCK_PTF_ATLAS, run_length: 26, total: 11.316659”
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=66:402` — “ptf: MOCK_PTF_ECHO, run_length: 29, total: -15.324184”
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=1139:1499` — “ptf: MOCK_PTF_JADE, run_length: 31, total: -8.552291”

#### Analysis

- Screened for same-sign runs in each PTF series.
- Verified run lengths and totals from deterministic results.

#### Alternative Explanations

- Sustained market moves in underlying assets.
- Consistent trading strategy or hedging activity.

#### Counter Evidence

- none

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — The cited locators are reopened and contain the stated PTF, dates, and DTD values. However, the row ranges include multiple PTFs and currencies, not just the named PTF. The evidence does not isolate the specific run series.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding claims runs for ATLAS, ECHO, and JADE. The reopened evidence shows rows for many PTFs, and the cited ranges are not filtered to the specific PTF. The population for each run is not clearly demonstrated.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — The finding states run totals are in different currencies and not directly comparable. The evidence rows show mixed currencies (EUR, USD, JPY) and multiple PTFs, so the run series are not isolated.
- **For a persistent run or volatility change, is the result robust to missing dates, portfolio mix, new activity, and one dominant outlier?** — The finding does not address missing dates or outliers. The run lengths are based on consecutive observed values, but the evidence does not show the full series or confirm no missing dates.
- **Does another source document a benign market move, accrual, freeze, correction, or valuation event? Contemporaneous occurrence alone does not establish causation.** — The finding lists alternative explanations (sustained market moves, consistent strategy) but does not provide evidence from another source. The recommendation to review desk commentary is appropriate.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence? Never infer intent or misconduct.** — Severity is low, which seems appropriate for a statistical observation without evidence of control failure. The finding is framed as an observation, not a control conclusion.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **unresolved**
Checks: Reopened locators contain the stated PTF names and DTD values.; The cited row ranges include multiple PTFs and currencies, not just the named PTF.; The deterministic support array is empty, indicating no locator-matched candidate was found in the controlled population.; The finding's claim of specific run lengths and totals is not directly supported by the reopened evidence because the series are not isolated.; The finding acknowledges different currencies and non-comparability, which is appropriate.; The recommendation to review desk commentary is reasonable but does not constitute evidence.; evidence reopen: 3 locator(s)
Feedback: Verifier rounds exhausted; marked UNRESOLVED. The finding is an observation of prolonged same-sign runs, but the evidence does not isolate the specific PTF series. The cited row ranges contain multiple PTFs and currencies, making it impossible to verify the run lengths and totals from the provided rows. The deterministic support is empty, suggesting the runs were not reproduced in the controlled population. To revise, provide filtered evidence for each PTF (e.g., rows only for MOCK_PTF_ATLAS, MOCK_PTF_ECHO, MOCK_PTF_JADE) with consecutive dates and DTD values, and confirm the run lengths and totals. Also address missing dates and outliers. Severity low is appropriate for an observation, but the claim should be supported by reproducible series.

#### Recommendation

Review trading desk commentary for these periods to confirm expected behavior.

### PNL-F6 — Period-end PnL concentration for MOCK_PTF_HARBOR (ratio 2.05)

**Severity:** low
**Confidence:** 0.50
**Period:** 2025-07-01 to 2026-06-30
**Verification:** unresolved

#### Observation

MOCK_PTF_HARBOR shows higher absolute PnL on month-end dates (mean 0.425) compared to other days (mean 0.207), with a ratio of 2.05. This suggests possible month-end valuation adjustments or accruals, but the effect is not extreme and may be normal. Month-end defined as last business day of each month; 12 month-end observations out of 261 total.

#### Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=3129:3129` — “ptf: MOCK_PTF_HARBOR, mean_abs_period_end: 0.425288, mean_abs_other: 0.207338, ratio: 2.0512”

#### Analysis

- Computed mean absolute PnL on month-end vs other days.
- Defined month-end as last business day of each calendar month.

#### Alternative Explanations

- Month-end marks or accruals are common.
- Sample size of month-end days is small (12).

#### Counter Evidence

- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=3129:3129`

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — Yes, the cited row 3129 is reopened and contains the stated PTF, date, and DTD value. However, the row itself does not contain the mean_abs_period_end, mean_abs_other, or ratio values quoted in the evidence; those are aggregate statistics computed by the deterministic screen.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding states 12 month-end observations out of 261 total for MOCK_PTF_HARBOR. The deterministic support confirms 12 observed month ends. The population appears complete for the PTF within the file, but the finding does not explicitly state whether all dates in the period are present or if any missing dates were excluded.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — Yes, the comparison is within MOCK_PTF_HARBOR, and the deterministic screen states it screened 12 comparable PTF series without aggregating currencies. The row shows Version=PUBLISHED_WW_FLASH, Notion=Pnl_Notion/Final Result Acc, Currency=EUR, so the comparison is within a consistent series.
- **For a period-end pattern, was the last observed business date determined separately for each month and compared with other dates in the same population?** — The finding states month-end was defined as last business day of each calendar month, and the deterministic support confirms 12 observed month ends. The method appears correct, but the finding does not provide the exact dates used or confirm that the last business day was determined from the observed data rather than a calendar assumption.
- **Does another source document a benign market move, accrual, freeze, correction, or valuation event? Contemporaneous occurrence alone does not establish causation.** — No other source is cited. The finding itself lists alternative explanations (month-end marks or accruals are common) and counter-evidence (other PTFs have lower ratios). The counter-evidence locator points to the same row, which does not contain the ratio for other PTFs; it only shows the row for MOCK_PTF_HARBOR. The claim that other PTFs have lower ratios is not supported by the cited locator.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence?** — Severity is low, which seems appropriate given the ratio of 2.05 and the small sample of month-end days. However, the confidence is 0.5, indicating uncertainty. The finding is an observation, not a control failure, so low severity is reasonable.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **unresolved**
Checks: Reopened the cited row 3129; it contains the PTF and DTD value but not the aggregate statistics quoted.; Confirmed the deterministic support matches the finding's ratio and month-end count.; Noted that the counter-evidence locator is the same row and does not support the claim about other PTFs' ratios.; The finding's evidence quote includes aggregate statistics not present in the row; the locator should be supplemented with the deterministic population table or a reference to the computed statistics.; The alternative explanations are plausible and the severity is low, but the counter-evidence citation is weak.; evidence reopen: 1 locator(s)
Feedback: Verifier rounds exhausted; marked UNRESOLVED. The finding is largely supported by the deterministic screen, but the cited evidence locator only shows a single row and does not contain the aggregate statistics (mean_abs_period_end, mean_abs_other, ratio) quoted. The counter-evidence locator is the same row and does not support the claim about other PTFs' ratios. Revise the evidence to cite the deterministic population table or a summary that includes the computed statistics, and provide a proper locator for the counter-evidence (e.g., a table of ratios for all PTFs). Also clarify the month-end definition and confirm the population completeness.

#### Recommendation

No action unless accompanied by unexplained large adjustments.

### PNL-F7 — Income attribution residual share 8.95% and top-3 concentration 57.95%

**Severity:** info
**Confidence:** 0.90
**Period:** 2025-07-01 to 2026-06-30
**Verification:** unresolved

#### Observation

The income attribution export shows top-3 components (Market Effect, Theta, Fees transactional) account for 57.95% of absolute primary component total, while residual components (including 'Other', 'Unexplained', etc.) account for 8.95%. This is a normal concentration profile; no schema or data-quality issues were flagged.

#### Evidence

- `source://income_attribution/attribution.csv#rows=1:1` — “top3_share: 0.579526, residual_component_share: 0.089506”

#### Analysis

- Profiled primary attribution buckets independently.
- Computed top-3 and residual shares from deterministic results.

#### Alternative Explanations

- Concentration is expected for market-making desks.
- Residual share is within acceptable range.

#### Counter Evidence

- `source://income_attribution/attribution.csv#rows=1:1`

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — The cited locator source://income_attribution/attribution.csv#rows=1:1 reopens, but the row contains placeholder values (e.g., bu=bu, sbu=sbu, asofdate=asofdate) rather than actual data. The quoted metrics (top3_share: 0.579526, residual_component_share: 0.089506) are not present in the row; they appear to be derived from a deterministic analysis not shown in the reopened evidence.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding claims a period from 2025-07-01 to 2026-06-30, but the reopened evidence is a single row with placeholder values and no date range. There is no evidence of the population used to compute the shares.
- **Are driver shares calculated from a clearly stated population and denominator? Do not add parent and leaf fields, or present the primary-bucket profile as a desk-total reconciliation.** — The finding states top-3 and residual shares, but the reopened evidence does not show the underlying component values, the denominator, or the population. The calculation cannot be reproduced from the cited row.
- **Does the file actually match the wide AIR contract (asofdate, hierarchy, and Final Result Acc DTD), and were invalid rows or unrecognized columns disclosed?** — The row contains the expected columns (asofdate, Final Result Acc DTD, etc.), but all values are placeholders. No actual data is available to verify the contract.
- **What do status, validated, isbatchvalidated, MPC, and FO fields mean in the governing workflow? A running, blank, or non-final label is unresolved workflow evidence until its state dictionary, owner, cadence, and later history are known.** — The counter evidence quotes 'All rows have status IA process is complete and validated=true', but the reopened row shows status=status and validated=validated (placeholders). The actual workflow state cannot be confirmed.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence?** — The finding is marked as 'info' severity, which is appropriate for an observation. However, the underlying data is not verifiable, so severity cannot be calibrated.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **unresolved**
Checks: Reopened evidence contains placeholder values, not actual data.; Quoted metrics (top3_share, residual_component_share) are not present in the cited row.; No deterministic support matched the locator.; The period and population cannot be verified from the evidence.; The counter evidence also contains placeholders, so it does not support the claim of complete validation.; evidence reopen: 1 locator(s)
Feedback: The finding cites a single row that contains only placeholder values (e.g., bu=bu, asofdate=asofdate). The quoted shares (top3_share: 0.579526, residual_component_share: 0.089506) are not present in the row and appear to be derived from an analysis not included in the reopened evidence. Without actual component values, denominator, and population, the calculation cannot be reproduced. The counter evidence also shows placeholders, so the claim of complete validation is unsupported. The evidence is inaccessible or ambiguous; mark as UNRESOLVED until actual data is provided.

#### Recommendation

No action; continue to monitor unexplained component.

### PNL-F8 — Monetary reconciliation between PnL and adjustments unresolved due to missing units/inclusion basis

**Severity:** medium
**Confidence:** 0.90
**Period:** 2025-07-01 to 2026-06-30
**Verification:** unresolved

#### Observation

The deterministic analysis could not reconcile adjustment amounts (AMOUNTINEUR) to PnL DTD because the file headers do not declare units (e.g., EUR vs thousands), sign convention, or whether PnL is pre- or post-adjustment. This is a known limitation; without source documentation, any monetary comparison is unsupported.

#### Evidence

- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=1:1` — “AMOUNTINEUR: -2350000.0”
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=1:1` — “DTD: -0.475895”

#### Analysis

- Attempted to reconcile adjustment amounts to PnL DTD.
- Identified missing unit and inclusion documentation.

#### Alternative Explanations

- Adjustments may be included in PnL already.
- Units may be in millions or thousands.

#### Counter Evidence

- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=1:1`

#### Verifier Questions

- **Can every cited row be reopened from the current manifest, and does it contain the stated date, entity, version, notion, currency, state, or amount?** — Yes, both cited rows are reopened and contain the stated fields. However, the adjustment row is the header row, not a data row, so the quoted AMOUNTINEUR value is not present in that row. The PnL row is also the header row, so the DTD value is not present. The evidence locators point to row 1, which is the header, not actual data.
- **Is the population complete for the claimed period, or were files, sheets, portfolios, dates, versions, notions, PnL types, teams, or inactive history excluded?** — The finding does not claim a complete population; it is about missing documentation. The evidence only shows headers, not data, so the population cannot be assessed from the cited rows.
- **Does a duplicate represent bad data, a legitimate history/version, or a missing key dimension?** — Not applicable; no duplicates are cited.
- **Are comparisons made within the same PTF, Version, Notion, currency, and date basis?** — The finding states that reconciliation could not be performed due to missing units/inclusion basis. The cited rows are headers, so no actual comparison is shown.
- **Can WTD, MTD, QTD, and YTD be reproduced from DTD with the documented reset rules?** — Not applicable; the finding is about unit/inclusion documentation, not cumulative calculations.
- **For a large move, what distribution, minimum population, and threshold produced the candidate? Is it material in desk context or merely statistically unusual?** — Not applicable; no large move is claimed.
- **For a reversal, are both legs in the same comparable series, on consecutive observed business dates, opposite in sign, and similar enough in magnitude?** — Not applicable; no reversal is claimed.
- **For a persistent run or volatility change, is the result robust to missing dates, portfolio mix, new activity, and one dominant outlier?** — Not applicable; no run or volatility change is claimed.
- **For a period-end pattern, was the last observed business date determined separately for each month and compared with other dates in the same population?** — Not applicable; no period-end pattern is claimed.
- **Does another source document a benign market move, accrual, freeze, correction, or valuation event? Contemporaneous occurrence alone does not establish causation.** — Not applicable; the finding is about missing documentation, not a specific event.
- **Do AMOUNT, EXCHANGERATE, and AMOUNTINEUR reperform within rounding tolerance, and is the currency mapping consistent with the PnL hierarchy?** — The finding does not attempt to reperform; it states that units are missing. The cited rows are headers, so no values are available to check.
- **Are valuation start/end dates ordered and is creation timing assessed against an applicable SLA rather than an invented deadline?** — Not applicable; no adjustment timing is claimed.
- **Are period-end adjustments expected for their nature and component? Concentration is a candidate pattern, not evidence of smoothing or manipulation.** — Not applicable; no period-end adjustment pattern is claimed.
- **Does a reversal share a PTF, component or link, valuation basis, and documented purpose? Similar opposite amounts across unrelated portfolios are not a reversal.** — Not applicable; no reversal is claimed.
- **Which supporting fields are mandatory for this adjustment type? Do not treat all blank optional identifiers as missing approval evidence.** — The finding does not discuss mandatory fields; it is about units and inclusion basis.
- **Is api_request_date used as the PnL population date and creationTime used only for record timing?** — Not applicable; no validation history is cited.
- **Are multiple active rows present for the same GOP, team, request date, and PnL type?** — Not applicable; no validation history is cited.
- **Does the governing state dictionary identify the state as final, pending, failed, or informational? If not, describe the state and keep the conclusion unresolved.** — Not applicable; no validation state is cited.
- **Were FLASH, STAB, and other PnL types assessed against their own cadence and deadline?** — Not applicable; no PnL type cadence is discussed.
- **Does apparent persistence reflect repeated snapshots of the same open item, a daily obligation, or separate events? State counts alone cannot answer that question.** — Not applicable; no persistence is claimed.
- **Does the deterministic persistence table describe consecutive observed active records only? A long run is not overdue until the state dictionary and cadence say so.** — Not applicable; no persistence table is cited.
- **Do PTF-to-GOP, PC, region, and currency mappings agree on the effective dates?** — Not applicable; no mapping inconsistency is claimed.
- **Are validation-only or PnL-only GOPs true coverage gaps, or different scoped populations? Cite evidence from both populations where available.** — Not applicable; no coverage gap is claimed.
- **Is a monetary comparison valid in common units and on the same pre/post-adjustment basis? If unit or inclusion definitions are missing, mark it UNRESOLVED.** — The finding correctly identifies that units and inclusion basis are missing, making monetary comparison unsupported. However, the evidence cited is only headers, not actual data, so the finding's claim that the analysis could not reconcile is based on the absence of documentation, not on the data itself. The finding is essentially an observation of a limitation, not a specific monetary discrepancy.
- **Is the severity proportional to magnitude, duration, recurrence, affected scope, control consequence, and contrary evidence? Never infer intent or misconduct.** — Severity is medium, which seems appropriate for a data quality limitation that prevents reconciliation. However, the finding is more of an unresolved matter than a concrete finding; it might be better classified as an unresolved issue rather than a medium-severity finding.
- **Does the file actually match the wide AIR contract (asofdate, hierarchy, and Final Result Acc DTD), and were invalid rows or unrecognized columns disclosed?** — Not applicable; the finding is not about the wide AIR contract.
- **Are driver shares calculated from a clearly stated population and denominator? Do not add parent and leaf fields, or present the primary-bucket profile as a desk-total reconciliation.** — Not applicable; no driver shares are discussed.
- **Does Final Result Acc DTD Cumulative equal the sum of DTD totals within the same hierarchy series and date population, within the stated tolerance? Check missing dates, duplicate hierarchy rows, resets, and the actual source units first.** — Not applicable; no cumulative reconciliation is claimed.
- **What do status, validated, isbatchvalidated, MPC, and FO fields mean in the governing workflow? A running, blank, or non-final label is unresolved workflow evidence until its state dictionary, owner, cadence, and later history are known.** — Not applicable; no workflow fields are cited.
- **Does a large unexplained/other/no-attribution share persist across comparable dates and entities, or is it a legitimate bucket, a temporary process state, or a taxonomy change? Do not infer an attribution error from the name alone.** — Not applicable; no attribution share is discussed.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **unresolved**
Checks: Reopened both cited locators; both point to header rows, not data rows.; The quoted values (AMOUNTINEUR: -2350000.0 and DTD: -0.475895) are not present in the cited rows; they are likely from later data rows, but the locators are incorrect.; The finding's claim is about missing units/inclusion basis, which is a valid limitation, but the evidence does not support the specific values quoted.; The finding is essentially an unresolved matter rather than a concrete finding; it should be reclassified as an unresolved issue or the evidence should be corrected to point to actual data rows.; The severity of medium may be appropriate for a data quality limitation, but the finding's confidence of 0.9 is not supported because the evidence is mis-cited.; evidence reopen: 2 locator(s)
Feedback: The finding correctly identifies a limitation: units and inclusion basis are not documented, preventing monetary reconciliation. However, the evidence locators point to header rows, not data rows, so the quoted values cannot be verified. The finding should be revised to either cite actual data rows or be reclassified as an unresolved matter. Additionally, the confidence of 0.9 is too high given the evidence issue. The decision is UNRESOLVED because the evidence is inaccessible as cited, but the underlying limitation is valid.

#### Recommendation

Obtain documentation on PnL units and adjustment inclusion basis to enable reconciliation.

## Unresolved Items

- PNL-F3 — GOP population mismatch: MOCK_GOP_ECHO in PnL but not in validation history: Verifier rounds exhausted; marked UNRESOLVED. The finding correctly identifies that MOCK_GOP_ECHO appears in the PnL file but not in the validation history. However, the conclusion that this is a validation coverage gap is not supported because the finding does not establish that the validation history is intended to cover all GOPs in the PnL file. The validation history may be scoped to specific teams, pnlTypes, or dates. To revise, provide evidence of the expected validation population (e.g., a control description or a list of GOPs that should be validated) and confirm that the PnL row for MOCK_GOP_ECHO is within that scope. Also, verify that the comparison is on the same date, version, notion, and pnlType basis. If the validation history is indeed supposed to cover all GOPs, then the finding can be supported; otherwise, it should be downgraded to an observation or unresolved.
- PNL-F5 — Prolonged same-sign PnL runs across multiple PTFs (e.g., 26-day positive run for ATLAS, 29-day negative for ECHO): Verifier rounds exhausted; marked UNRESOLVED. The finding is an observation of prolonged same-sign runs, but the evidence does not isolate the specific PTF series. The cited row ranges contain multiple PTFs and currencies, making it impossible to verify the run lengths and totals from the provided rows. The deterministic support is empty, suggesting the runs were not reproduced in the controlled population. To revise, provide filtered evidence for each PTF (e.g., rows only for MOCK_PTF_ATLAS, MOCK_PTF_ECHO, MOCK_PTF_JADE) with consecutive dates and DTD values, and confirm the run lengths and totals. Also address missing dates and outliers. Severity low is appropriate for an observation, but the claim should be supported by reproducible series.
- PNL-F6 — Period-end PnL concentration for MOCK_PTF_HARBOR (ratio 2.05): Verifier rounds exhausted; marked UNRESOLVED. The finding is largely supported by the deterministic screen, but the cited evidence locator only shows a single row and does not contain the aggregate statistics (mean_abs_period_end, mean_abs_other, ratio) quoted. The counter-evidence locator is the same row and does not support the claim about other PTFs' ratios. Revise the evidence to cite the deterministic population table or a summary that includes the computed statistics, and provide a proper locator for the counter-evidence (e.g., a table of ratios for all PTFs). Also clarify the month-end definition and confirm the population completeness.
- PNL-F7 — Income attribution residual share 8.95% and top-3 concentration 57.95%: The finding cites a single row that contains only placeholder values (e.g., bu=bu, asofdate=asofdate). The quoted shares (top3_share: 0.579526, residual_component_share: 0.089506) are not present in the row and appear to be derived from an analysis not included in the reopened evidence. Without actual component values, denominator, and population, the calculation cannot be reproduced. The counter evidence also shows placeholders, so the claim of complete validation is unsupported. The evidence is inaccessible or ambiguous; mark as UNRESOLVED until actual data is provided.
- PNL-F8 — Monetary reconciliation between PnL and adjustments unresolved due to missing units/inclusion basis: The finding correctly identifies a limitation: units and inclusion basis are not documented, preventing monetary reconciliation. However, the evidence locators point to header rows, not data rows, so the quoted values cannot be verified. The finding should be revised to either cite actual data rows or be reclassified as an unresolved matter. Additionally, the confidence of 0.9 is too high given the evidence issue. The decision is UNRESOLVED because the evidence is inaccessible as cited, but the underlying limitation is valid.

## Overall Conclusion

PnL review completed: 3 finding(s) verified, 0 rejected, 5 unresolved. Top findings: PNL-F1 (medium): Large freeze adjustment -6.25M EUR on MOCK_PTF_ATLAS (2025-12-30) flagged as outlier; PNL-F3 (medium): GOP population mismatch: MOCK_GOP_ECHO in PnL but not in validation history; PNL-F8 (medium): Monetary reconciliation between PnL and adjustments unresolved due to missing units/inclusion basis.
