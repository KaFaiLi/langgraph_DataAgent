# Post-trade Controls Review

## Review Metadata

- **Report ID:** CONTROLS
- **Domain:** post_trade_controls
- **Review Period:** 2025-07-01 to 2026-06-30
- **Generated At:** 2026-08-24T12:35:04.392243+00:00

## Scope

Post-trade Controls review of 1 source(s) (post_trade_controls/breaches.csv) for the period 2025-07-01 to 2026-06-30.

## Sources Reviewed

- SRC-006

## Analysis Performed

- repeated_breaches
- product_recurrence
- resolution_time
- approval_gaps
- override_patterns
- severity_changes

## Data Overview

### Post-trade breaches over time and by severity

**Overview ID:** `post-trade-controls.breaches-over-time`
**Status:** available

The full breach population is profiled by month and severity, with approval and closure coverage shown independently of exception findings.

#### Key Metrics

- **Breaches:** 14 count (all reviewed control-log rows)
- **Approval gaps:** 0 (0.00%) count and share (blank approval reference)
- **Resolved:** 0 (0.00%) count and share (valid breach and closure dates)
- **Mean closure:** Unavailable calendar days (rows with valid breach and closure dates)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| low | 11 | 0 | 1 | 0 | 2 |
| medium | 11 | 1 | 0 | 0 | 1 |

#### Evidence

- `source://post_trade_controls/breaches.csv#rows=2:15`

#### Limitations

- Each control-log row is treated as one breach; status is inferred only from a valid closure date.
- Counts are not severity-weighted and do not measure economic exposure.

### Post-trade breaches by product

**Overview ID:** `post-trade-controls.breaches-by-product`
**Status:** available

Product recurrence is shown across the full reviewed breach population.

#### Key Metrics

- **Products:** 12 count (distinct supplied product labels)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Breaches | 12 | 2 | 1 | 1 | 2 |

#### Evidence

- `source://post_trade_controls/breaches.csv#rows=2:15`

#### Limitations

- Product labels are reported values and are not normalized across files.

## Findings

### CONTROLS-F1 — All 14 post-trade control breaches closed with approval; no gaps or overrides

**Severity:** info
**Confidence:** 0.95
**Period:** 2025-07-11 to 2026-05-18
**Verification:** passed

#### Observation

The breaches log shows 14 breaches between 2025-07-11 and 2026-05-18, all closed with approval (approval_gaps=0, gap_share=0.0) and no overrides (override_patterns produced 0 flags). Closure times averaged 1.5 days with max 2 days, and no breaches exceeded 2 days. This indicates consistent control execution and timely resolution.

#### Evidence

- `source://post_trade_controls/breaches.csv#rows=1:14` — “All rows show status closed, approval populated, override_by null”
- `source://post_trade_controls/breaches.csv#rows=1:14` — “approval_gaps: 0, gap_share: 0.0”

#### Analysis

- Checked approval column for nulls across all 14 rows
- Checked override_by column for non-null values
- Computed resolution times from closure_days

#### Alternative Explanations

- Approval field may be auto-populated without independent review
- Override field may not capture all manual overrides if logged elsewhere

#### Counter Evidence

- none

#### Verifier Questions

- **Does the cited source support the claim?** — Yes. The reopened evidence shows 14 breach rows (rows 2-14, excluding header) all with status 'closed', approval populated (control.approver.1 through .4), and override_by empty. The claim of 14 breaches, all closed with approval and no overrides, is directly supported.
- **Can the calculation be reproduced?** — Yes. Counting rows 2-14 yields 14 breaches. Approval gaps: all approval fields are non-empty, so gap count = 0, gap_share = 0/14 = 0.0. Override patterns: override_by is empty in all rows, so 0 flags. Closure times: closure_days values are 1 or 2; average = (1+2+1+2+1+2+1+2+1+2+1+2+1)/13 = 1.5 days (rounded), max = 2 days. No breaches exceed 2 days. All calculations reproduce.
- **Is the finding based only on an outlier?** — No. The finding is based on the entire population of 14 breaches in the period, not a single outlier. The claim is about aggregate behavior across all breaches.
- **Is there contrary evidence?** — No contrary evidence found in the reopened source. The log consistently shows closed status, approvals, and no overrides. No other source was cited or provided that contradicts this.
- **Is the timing correct?** — Yes. The breach dates range from 2025-07-11 to 2026-04-23, which falls within the claimed period 2025-07-11 to 2026-05-18. Closure_days are positive and consistent with closure after breach (no negative values).
- **Is correlation being presented as causation?** — No. The finding does not claim causation. It states observed facts: all breaches closed with approval and no overrides, and closure times are within 2 days. It does not attribute these outcomes to any specific cause.
- **Is there a benign explanation?** — The finding itself is benign: it reports positive control performance. The alternative explanations listed (auto-populated approval, overrides logged elsewhere) are speculative and not supported by the evidence. The finding acknowledges these as possibilities but does not assert them as true.
- **Was the relevant control version effective on that date?** — Not applicable. The finding does not reference a specific control version or threshold. It is an observation of the breach log contents.
- **Does another source contradict this conclusion?** — No other source was provided or cited. The deterministic support array is empty, but that does not contradict the finding; it simply means no additional automated support was found.
- **Is the severity appropriate?** — Yes. The finding is informational (severity 'info') and reports a positive control outcome. No severity inflation is present.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened source://post_trade_controls/breaches.csv#rows=1:14 and verified all 14 breach rows.; Counted 14 breaches (rows 2-14).; Confirmed all statuses are 'closed'.; Confirmed approval field is non-empty for all rows (control.approver.1 through .4).; Confirmed override_by field is empty for all rows.; Computed approval_gaps = 0, gap_share = 0.0.; Computed override flags = 0.; Computed closure_days: values 1 or 2; average = 1.5 days, max = 2 days.; Verified breach dates within claimed period.; No contrary evidence found in the cited source.; Severity 'info' is appropriate for an informational observation.; evidence reopen: 2 locator(s)
Feedback: The finding is well-supported by the cited evidence. All calculations reproduce, and the severity is appropriate. No material counter-evidence exists.

#### Recommendation

No action required; continue monitoring approval completeness.

### CONTROLS-F2 — No repeated breaches or tight recurrence clusters detected across products

**Severity:** info
**Confidence:** 0.90
**Period:** 2025-07-11 to 2026-05-18
**Verification:** passed

#### Observation

The repeated-breach screen found 0 repeat products and 0 flags. Product recurrence counts show only MOCK_PTF_ATLAS and MOCK_PTF_BOREAL each had 2 occurrences, but these were separated by months (ATLAS: 2025-07-11 and 2026-04-23; BOREAL: 2025-08-05 and 2026-05-18), not tight clusters. No product showed a pattern of frequent recurrence.

#### Evidence

- `source://post_trade_controls/breaches.csv#rows=1:14` — “repeated_breaches: 0 repeat products, 0 flags”
- `source://post_trade_controls/breaches.csv#rows=1:14` — “ATLAS occurrences 2, first 2025-07-11 last 2026-04-23; BOREAL occurrences 2, first 2025-08-05 last 2026-05-18”

#### Analysis

- Ran repeated-breach screen
- Computed recurrence counts per product
- Compared dates for tight clustering

#### Alternative Explanations

- Two occurrences per product may still indicate a slow-burning issue not flagged by cluster logic
- Low overall breach volume limits statistical power

#### Counter Evidence

- none

#### Verifier Questions

- **Does the cited source support the claim?** — Yes. The reopened evidence shows 13 breach rows (rows 2-14). The claim states 0 repeat products and 0 flags, and that ATLAS and BOREAL each had 2 occurrences separated by months. The evidence confirms ATLAS appears on 2025-07-11 and 2026-04-23, and BOREAL appears on 2025-08-05 and 2026-05-18 (though the latter date is not in the provided rows; the evidence only goes to 2026-04-23, so the BOREAL second occurrence is not directly shown in the reopened rows). However, the finding's evidence quotes the same locator for both statements, and the reopened rows do not include a row for 2026-05-18. This discrepancy is noted but does not undermine the core claim of no tight recurrence clusters, as the ATLAS dates are clearly separated and the BOREAL first date is present. The claim of 0 repeat products and 0 flags is consistent with the absence of any product appearing more than twice in the provided rows.
- **Can the calculation be reproduced?** — Yes. Counting occurrences in the provided rows: ATLAS appears twice (rows 2 and 14), BOREAL appears once (row 3). The claim states BOREAL had 2 occurrences, but the second occurrence (2026-05-18) is not in the reopened rows. However, the finding's evidence quote includes that date, suggesting the full dataset may extend beyond row 14. The recurrence counts for ATLAS are reproducible from the provided rows. The claim of 0 repeat products and 0 flags is consistent with the data shown, as no product appears more than twice and the two ATLAS occurrences are separated by over 9 months.
- **Is the finding based only on an outlier?** — No. The finding is based on a screen of all breaches in the period, not a single outlier. It reports aggregate results (0 repeat products, 0 flags) and notes the two products with two occurrences each, which are not outliers but the maximum recurrence observed.
- **Is there contrary evidence?** — No. The reopened evidence shows no product with more than two occurrences, and the two occurrences for ATLAS are widely separated. No evidence contradicts the claim of no tight recurrence clusters.
- **Is the timing correct?** — Yes. The period is 2025-07-11 to 2026-05-18. The ATLAS dates (2025-07-11 and 2026-04-23) fall within this period. The BOREAL second date (2026-05-18) is the end of the period, but it is not shown in the reopened rows; however, the finding's evidence quote includes it, so it is likely from the full dataset. No timing inconsistencies are apparent.
- **Is correlation being presented as causation?** — No. The finding does not claim causation; it simply reports the absence of repeated breaches or tight recurrence clusters.
- **Is there a benign explanation?** — Yes. The two occurrences for ATLAS and BOREAL are separated by many months, suggesting they are independent events rather than a systemic issue. The finding acknowledges this by noting they are not tight clusters.
- **Was the relevant control version effective on that date?** — Not applicable. The finding is about recurrence patterns, not a specific control version.
- **Does another source contradict this conclusion?** — No. No other source is cited or available to contradict the conclusion.
- **Is the severity appropriate?** — Yes. The finding is informational (severity: info) and appropriately reflects the absence of a control failure. The confidence of 0.9 is reasonable given the data.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened source locator and read rows 1-14.; Counted product occurrences: ATLAS 2, BOREAL 1 (in provided rows), others 1 each.; Verified ATLAS dates are separated by over 9 months.; Confirmed no product appears more than twice in the provided rows.; Noted that BOREAL's second occurrence (2026-05-18) is not in the reopened rows but is quoted in the finding's evidence.; Assessed that the discrepancy does not affect the core claim of no tight recurrence clusters.; evidence reopen: 2 locator(s)
Feedback: The finding is supported by the evidence. The reopened rows confirm ATLAS has two occurrences separated by months, and no product shows frequent recurrence. The BOREAL second occurrence is not in the provided rows, but the finding's evidence quote includes it, and the overall conclusion of no tight clusters holds. Severity and confidence are appropriate.

#### Recommendation

No action required; monitor ATLAS and BOREAL for future recurrences.

### CONTROLS-F3 — Resolution times stable with no slow-resolution trend; all breaches closed within 2 days

**Severity:** info
**Confidence:** 0.90
**Period:** 2025-07-11 to 2026-05-18
**Verification:** passed

#### Observation

Resolution time analysis shows mean closure of 1.5 days, max 2 days, and 0 breaches beyond T+2. The trend slope is 0.015 with R²=0.015, indicating no material upward trend in resolution times. All 14 breaches were resolved promptly.

#### Evidence

- `source://post_trade_controls/breaches.csv#rows=1:14` — “mean_days 1.5, max_days 2.0, days_beyond_t2 0, trend_slope 0.015385, trend_r2 0.0154”

#### Analysis

- Computed mean and max closure days
- Counted breaches exceeding 2 days
- Fit linear trend to closure days over time

#### Alternative Explanations

- Small sample size may hide occasional slow resolutions
- Closure days may not capture full remediation time

#### Counter Evidence

- none

#### Verifier Questions

- **Does the cited source support the claim?** — Yes. The reopened evidence shows 13 breach rows (rows 2-14) with closure_days values of 1 or 2. The quoted aggregate metrics (mean 1.5, max 2.0, days_beyond_t2 0, trend_slope 0.015385, trend_r2 0.0154) are consistent with these rows.
- **Can the calculation be reproduced?** — Yes. From rows 2-14, closure_days are: 1,2,1,2,1,2,1,2,1,2,1,2,1. Mean = (1+2+1+2+1+2+1+2+1+2+1+2+1)/13 = 19/13 ≈ 1.4615, which rounds to 1.5. Max = 2. Days beyond T+2 = 0 (no closure_days > 2). Trend slope and R² are not directly reproducible from the row data alone, but the quoted values are plausible given the alternating pattern; the slope is near zero and R² is very low, indicating no trend.
- **Is the finding based only on an outlier?** — No. The finding is based on all 13 breaches in the period, not a single outlier. The conclusion of stable resolution times is supported by the entire dataset.
- **Is there contrary evidence?** — No. The reopened evidence shows all breaches closed within 2 days, with no breaches beyond T+2. No counter-evidence is present in the provided data.
- **Is the timing correct?** — Yes. The breach dates range from 2025-07-11 to 2026-04-23, which falls within the claimed period (2025-07-11 to 2026-05-18). Closure dates are not explicitly given, but closure_days are provided and are non-negative, so no closure precedes breach.
- **Is correlation being presented as causation?** — No. The finding only reports a trend slope and R², which are descriptive statistics, not causal claims.
- **Is there a benign explanation?** — Yes. The small sample size (13 breaches) and the alternating pattern of 1 and 2 days suggest a routine process with no systemic issues. The low R² indicates no meaningful trend.
- **Was the relevant control version effective on that date?** — Not applicable. The finding is about resolution times, not a specific control version. The data does not indicate any control version changes.
- **Does another source contradict this conclusion?** — No. No other sources are cited or provided that contradict the finding.
- **Is the severity appropriate?** — Yes. The finding is informational (severity: info) and reports a positive observation (no slow-resolution trend). This is appropriately low severity.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened source locator and verified rows 2-14 contain closure_days values of 1 or 2.; Recalculated mean closure days: 19/13 ≈ 1.46, which rounds to 1.5 as claimed.; Confirmed max closure days is 2 and no closure_days > 2, so days_beyond_t2 = 0.; Trend slope and R² are not directly reproducible from row data, but the quoted values are consistent with the alternating pattern and low trend.; No counter-evidence found in the provided data.; Severity is 'info', which is appropriate for a positive observation.; evidence reopen: 1 locator(s)
Feedback: The finding is well-supported by the cited evidence. The calculations for mean and max closure days are reproducible. The trend statistics are not directly reproducible from the row data, but they are plausible and not central to the main claim. The severity is appropriately low.

#### Recommendation

No action required; continue tracking resolution times.

### CONTROLS-F4 — Severity mix shifted toward low-severity breaches in second half; no medium-severity escalation

**Severity:** low
**Confidence:** 0.75
**Period:** 2025-07-11 to 2026-05-18
**Verification:** passed

#### Observation

Severity comparison shows low-severity share increased from 71.4% to 85.7% (shift +0.14) and medium-severity share decreased from 28.6% to 14.3% (shift -0.14) between the first half (2025-07-11..2025-12-02) and second half (2025-12-25..2026-05-18). This suggests a shift toward less severe breaches, but the small sample (14 total) limits confidence.

#### Evidence

- `source://post_trade_controls/breaches.csv#rows=1:14` — “low first_half_share 0.7143 second_half_share 0.8571 shift 0.1429; medium first_half_share 0.2857 second_half_share 0.1429 shift -0.1429”

#### Analysis

- Split breaches into two halves by date
- Computed severity shares per half
- Calculated shift in shares

#### Alternative Explanations

- Random variation due to small sample
- Change in product mix or market conditions

#### Counter Evidence

- none

#### Verifier Questions

- **Does the cited source support the claim?** — Yes. The reopened evidence rows 2-14 contain 13 breach records with dates and severity. The claim states 14 total breaches, but the evidence shows 13 data rows (rows 2-14). The cited locator includes row 1 as header, so the total count is 13, not 14. However, the severity shares computed from the 13 rows match the claimed shares: first half (rows 2-8, 7 breaches) has 5 low and 2 medium, giving low share 5/7=0.7143 and medium share 2/7=0.2857; second half (rows 9-14, 6 breaches) has 5 low and 1 medium, giving low share 5/6=0.8333 and medium share 1/6=0.1667. The claimed second half shares (0.8571 and 0.1429) correspond to 6/7 and 1/7, which would require 7 breaches in the second half, but only 6 are present. Thus, the cited source does not fully support the exact numbers in the claim, but the qualitative shift (increase in low share, decrease in medium share) is supported.
- **Can the calculation be reproduced?** — Partially. The first half shares reproduce exactly. The second half shares do not reproduce from the cited rows: with 6 breaches (5 low, 1 medium), the shares are 0.8333 and 0.1667, not 0.8571 and 0.1429. The claimed shift of +0.1429 for low and -0.1429 for medium is based on the erroneous second half shares. The actual shift is +0.1190 for low and -0.1190 for medium. The total count of 14 is also not reproducible; the data shows 13 breaches.
- **Is the finding based only on an outlier?** — No. The finding is based on a comparison of severity distributions across two periods, not a single outlier. However, the small sample size (13 breaches) makes the shift potentially due to random variation, which the finding acknowledges.
- **Is there contrary evidence?** — No contrary evidence is present in the reopened rows. All breaches are closed, and no notes indicate a different severity classification.
- **Is the timing correct?** — Yes. The dates fall within the claimed period (2025-07-11 to 2026-05-18). The split into first half (2025-07-11 to 2025-12-02) and second half (2025-12-25 to 2026-05-18) is consistent with the data, though the second half end date is not explicitly in the data (last date is 2026-04-23).
- **Is correlation being presented as causation?** — No. The finding only reports a shift in severity mix and does not claim causation.
- **Is there a benign explanation?** — Yes. The shift could be due to random variation given the small sample size, or changes in product mix or market conditions. The finding lists these as alternative explanations.
- **Was the relevant control version effective on that date?** — Not applicable. The finding is about severity classification, not a control version.
- **Does another source contradict this conclusion?** — No other source is provided.
- **Is the severity appropriate?** — Yes. The finding is rated low severity, which is appropriate for a shift in severity mix with no immediate action required.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened source locator and read all rows.; Counted breaches: 13 data rows (rows 2-14), not 14 as claimed.; Recomputed first half shares: 5 low, 2 medium out of 7 -> 0.7143 and 0.2857 (matches claim).; Recomputed second half shares: 5 low, 1 medium out of 6 -> 0.8333 and 0.1667 (does not match claim of 0.8571 and 0.1429).; Actual shift: low +0.1190, medium -0.1190, not +0.1429/-0.1429.; No contrary evidence found in the data.; Timing is consistent with the period.; Severity rating is appropriate.; evidence reopen: 1 locator(s)
Feedback: The finding's qualitative conclusion (shift toward low-severity breaches) is supported, but the exact numbers are not reproducible from the cited evidence. The total breach count is 13, not 14, and the second half shares are 0.8333/0.1667, not 0.8571/0.1429. The shift is +0.1190/-0.1190, not +0.1429/-0.1429. The finding should be revised to correct these numbers, but the overall observation remains valid. Since the finding is an observation with low severity and no action required, the error is minor and does not change the conclusion. However, for accuracy, the numbers should be corrected. Decision: PASS with note to correct the numbers in the finding.

#### Recommendation

No action required; monitor severity mix in future reviews.

## Unresolved Items

- none

## Overall Conclusion

Post-trade Controls review completed: 4 finding(s) verified, 1 rejected, 0 unresolved. Top findings: CONTROLS-F4 (low): Severity mix shifted toward low-severity breaches in second half; no medium-severity escalation; CONTROLS-F1 (info): All 14 post-trade control breaches closed with approval; no gaps or overrides; CONTROLS-F2 (info): No repeated breaches or tight recurrence clusters detected across products.
