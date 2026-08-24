# Final Findings

## Executive Summary

The Cross-Asset Market Making Desk review identified a material VaR limit breach on MOCK_PTF_ATLAS MOCK_PC_FLOW in late March 2026, followed by a limit increase that appears to have become effective before workflow approvals were recorded. Recurring excess events and data inconsistencies in the Colibris workflow system raise governance concerns. Post-trade controls were consistently closed with approval and timely resolution, and PnL adjustments showed expected period-end concentrations. Several cross-source reconciliation issues remain unresolved due to missing unique identifiers and unit documentation.

## Overall Desk Risk Assessment

The desk exhibits a moderate risk profile with isolated high-severity governance concerns around limit management and data integrity. The VaR breach and subsequent limit increase timing suggest potential control circumvention, though no direct evidence of unauthorized activity was verified. Recurring excess events indicate the limit framework may be misaligned with trading activity. Post-trade controls appear robust, and PnL adjustments are consistent with routine month-end processes. Unresolved data gaps limit full reconciliation and require follow-up.

## Key Findings

### LF-001 — VaR limit breach on MOCK_PC_FLOW with subsequent limit increase effective before approval

**Severity:** high
**Confidence:** 0.80

MOCK_LIMIT_01_01 (VaR, MEUR, upper bound 7.0) was breached on 2026-03-25, 2026-03-26, and 2026-03-27, with worst value 7.55 on 2026-03-26. The limit was increased to 9.0 effective 2026-04-01, but the associated Colibris workflow shows request date 2026-04-02, trader approval 2026-04-12, and risk approval 2026-04-15, indicating the effective date precedes recorded approvals.

**Derived from:** RISK-F1, RISK-F2, RISK-F6
**Evidence:** `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9169:9169`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9217:9217`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9265:9265`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=42:42`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9409:9409`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=32:32`
**Cross-source clusters:** CL-002

### LF-002 — Recurring VaR excess events on MOCK_PC_FLOW with open items

**Severity:** medium
**Confidence:** 0.90

MOCK_PC_FLOW VaR had 9 excess events between 2025-07-01 and 2026-04-07, with 2 still open as of 2026-06-30. Max recorded usage reached 116%. This recurring pattern suggests the limit may be misaligned with trading activity or that breaches are not being effectively remediated.

**Derived from:** RISK-F3
**Evidence:** `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=44:44`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=6:6`
**Cross-source clusters:** CL-002

### LF-003 — Data inconsistencies in Colibris workflow records

**Severity:** low
**Confidence:** 0.90

Multiple Colibris excess records have increaseWorkflowStatus 'APPROVED' but increaseId equals 0, and some records show explanation/validation timestamps before creation date. These inconsistencies undermine the reliability of workflow data for governance assessment.

**Derived from:** RISK-F5, RISK-F6, RISK-F2
**Evidence:** `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=7:7`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=12:12`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=32:32`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=42:42`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9409:9409`
**Cross-source clusters:** CL-002, CL-011

### LF-004 — Cross-source limit type mismatch between Colibris and SGMR

**Severity:** medium
**Confidence:** 0.80

Colibris records for MOCK_PC_FLOW and MOCK_PC_HEDGE VaR excesses show limitType 'RELATIVE_THRESHOLD', while matched SGMR limit definitions are 'ABSOLUTE_THRESHOLD'. This discrepancy affects interpretation of limit breaches and requires clarification.

**Derived from:** RISK-F7, RISK-F8
**Evidence:** `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`, `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=10:10`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=1:1`
**Cross-source clusters:** CL-002

### LF-005 — Large freeze adjustment on MOCK_PTF_ATLAS at year-end

**Severity:** medium
**Confidence:** 0.70

Adjustment 96600008 on MOCK_PTF_ATLAS has amount_eur -6,250,000 with z-score -3.28, the largest adjustment in the period. It is a freeze adjustment dated 2025-12-30, part of a month-end concentration. While freeze adjustments are documented control actions, its size and timing warrant review.

**Derived from:** PNL-F1, PNL-F2
**Evidence:** `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:9`, `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:12`, `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=16:18`, `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=22:25`
**Cross-source clusters:** CL-007

### LF-006 — Period-end adjustment concentration in Dec-2025, Mar-2026, Jun-2026

**Severity:** low
**Confidence:** 0.80

In Dec-2025, Mar-2026, and Jun-2026, all adjustments occur on period-end dates, with period_end_share=1.0. This pattern is consistent with routine month-end accruals and true-ups, but the high concentration at fiscal year-end may warrant additional scrutiny.

**Derived from:** PNL-F2, PNL-F1
**Evidence:** `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:12`, `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=16:18`, `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=22:25`, `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:9`
**Cross-source clusters:** CL-007

### LF-008 — Commentary reassurance claim on VaR exposure within appetite conflicts with breach evidence

**Severity:** medium
**Confidence:** 0.80

A validated commentary claim dated 2026-03-27 states 'Exposure remained within appetite and the applicable limit framework; no escalation was required.' This conflicts with the verified VaR breach on the same date for MOCK_PC_FLOW. The claim may cover a different perimeter or be based on incomplete information.

**Derived from:** COMMENTARY-FIND-002, RISK-F1
**Evidence:** `source://risk_commentary/quarterly_reviews_summary_var_svar_comment.md#lines=269:269`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9265:9265`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9169:9169`, `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9217:9217`
**Cross-source clusters:** CL-002

## Cross-source Findings

- **CL-001**: findings COMMENTARY-FIND-001 (same_date, shared_entity, same_category) | entities: commentary, these, validation
- **CL-002**: findings COMMENTARY-FIND-002, CONTROLS-F2, PNL-F5, RISK-F1, RISK-F2, RISK-F3, RISK-F5, RISK-F7, RISK-F8 (same_date, shared_entity) | entities: approval, atlas, breach, colibris, commentary, id, meur, mock_limit_01_01, mock_pc_flow, mock_ptf_atlas, sgmr, these, threshold, workflow
- **CL-003**: findings COMMENTARY-FIND-003 (same_date, shared_entity, same_category) | entities: commentary, threshold
- **CL-004**: findings CONTROLS-F1 (same_date, shared_entity, same_category) | entities: approval
- **CL-005**: findings CONTROLS-F3 (same_date, same_category) | entities: none
- **CL-006**: findings CONTROLS-F4 (same_date, same_category) | entities: none
- **CL-007**: findings PNL-F1, PNL-F2, PNL-F6, PNL-F8 (same_date, shared_entity) | entities: adjustment, adjustments, dec-2025, eur, mock_ptf_atlas, period-end
- **CL-008**: findings PNL-F3, PNL-F4 (same_date, shared_entity, same_category) | entities: gop, mock_gop_mike, validation, workflow
- **CL-009**: findings PNL-F7 (same_date, same_category) | entities: none
- **CL-010**: findings RISK-F4 (same_date, same_category) | entities: none
- **CL-011**: findings RISK-F6 (same_date, shared_entity, same_category) | entities: workflow

## Potential Unauthorized Activity Indicators

- Limit increase effective before workflow approval following a breach (RISK-F2) suggests possible retrospective limit change.
- Recurring VaR excess events on MOCK_PC_FLOW with open items (RISK-F3, RISK-F4) may indicate deliberate limit circumvention or inadequate escalation.
- Data inconsistencies in Colibris workflow records (RISK-F5, RISK-F6) could mask unauthorized limit changes or approvals.
- Cross-source limit type mismatch (RISK-F7) may lead to misinterpretation of limit breaches and potential unauthorized risk-taking.
- Large freeze adjustment at year-end (PNL-F1) could be used to smooth PnL, though documented as a control action.

## Control Weaknesses

- Limit increase workflow shows effective date before approvals, indicating a gap in change management controls (RISK-F2).
- Recurring excess events with open items suggest ineffective limit breach remediation (RISK-F3, RISK-F4).
- Colibris data inconsistencies (increaseId=0, timestamp order) undermine workflow data integrity (RISK-F5, RISK-F6).
- Cross-source limit type mismatch creates ambiguity in limit interpretation (RISK-F7).
- Missing unique bridge between Colibris and SGMR prevents event-level reconciliation (RISK-F8).
- Validation coverage gap for MOCK_GOP_ECHO (PNL-F3) indicates potential control gap in PnL validation.
- Pending managerial validation on 10 commentary records (COMMENTARY-FIND-001) leaves review trail incomplete.

## PnL / Risk Inconsistencies

- Monetary reconciliation between PnL and adjustments unresolved due to missing units/inclusion basis (PNL-F8).
- GOP population mismatch: MOCK_GOP_ECHO in PnL but not in validation history (PNL-F3).
- Validation GOP without PnL rows: MOCK_GOP_MIKE (PNL-F4).
- Prolonged same-sign PnL runs (e.g., 26-day positive for ATLAS, 29-day negative for ECHO) are statistically unusual but may reflect market trends (PNL-F5).
- Period-end PnL concentration for MOCK_PTF_HARBOR (ratio 2.05) suggests possible month-end valuation adjustments (PNL-F6).
- Income attribution residual share 8.95% and top-3 concentration 57.95% are normal but should be monitored (PNL-F7).

## Unresolved Questions

- Why did the limit increase for MOCK_LIMIT_01_01 become effective before workflow approvals? (RISK-F2)
- What is the root cause of recurring VaR excess events on MOCK_PC_FLOW? (RISK-F3)
- Are the open excess events with past deadlines truly unresolved or is the extract stale? (RISK-F4)
- Why do some Colibris records have increaseId=0 despite APPROVED status? (RISK-F5)
- Why do workflow timestamps precede creation dates on some excess records? (RISK-F6)
- What is the correct limit type for MOCK_PC_FLOW and MOCK_PC_HEDGE VaR limits? (RISK-F7)
- Is there a unique ID bridge between Colibris and SGMR to enable event-level reconciliation? (RISK-F8)
- What is the business rationale for the large freeze adjustment 96600008? (PNL-F1)
- Why does MOCK_GOP_ECHO lack validation history? (PNL-F3)
- Are the prolonged same-sign PnL runs consistent with trading strategy and market conditions? (PNL-F5)
- What are the units and inclusion basis for PnL and adjustment amounts? (PNL-F8)
- Why are 10 commentary records pending managerial validation? (COMMENTARY-FIND-001)
- Does the commentary claim of VaR within appetite on 2026-03-27 cover the same perimeter as the breached limit? (COMMENTARY-FIND-002)
- Unresolved specialist finding PNL-F6: Period-end PnL concentration for MOCK_PTF_HARBOR (ratio 2.05).
- Unresolved specialist finding PNL-F7: Income attribution residual share 8.95% and top-3 concentration 57.95%.
- Unresolved specialist finding COMMENTARY-FIND-003: No internal trigger/reassurance contradictions found in commentary extracts.
- Lead verification (round 2): The final report contains several issues that require correction:
1. LF-001: The evidence for the limit increase effective date (2026-04-01) is not directly supported by the quoted evidence. The quote from SGMR row 9409 shows the limit as 9.0 on 2026-04-01, but the specialist finding RISK-F2 only states the effective date precedes approvals based on Colibris data. The final finding should explicitly reference the Colibris record showing effective date 2026-04-01 and the approval dates, and clarify that the SGMR row is used to confirm the limit was in effect on that date. Additionally, the evidence quote for row 9409 is null in the evidence index, which is inconsistent.
2. LF-003: The evidence includes a quote from SGMR row 9409 with null quote, which is not meaningful. The final finding should only include evidence that directly supports the statement about data inconsistencies in Colibris records.
3. LF-004: The evidence for the SGMR limit type is from row 1, but the specialist finding RISK-F7 likely used a different row. The final finding should ensure the evidence locator matches the specialist evidence.
4. LF-005: The evidence includes quotes about period-end adjustments for months other than December 2025, which are not directly relevant to the large freeze adjustment. The final finding should focus on the specific adjustment and its context.
5. LF-006: The evidence includes a quote about the large freeze adjustment, which is not directly relevant to the period-end concentration pattern. The final finding should only include evidence that supports the concentration pattern.
6. LF-008: The evidence includes quotes for VaR breaches on 2026-03-25 and 2026-03-26, which are not directly relevant to the commentary claim on 2026-03-27. The final finding should only include the breach on 2026-03-27 and the commentary quote.
7. Cross-source clusters: CL-002 includes findings from multiple specialists, but the supporting evidence includes quotes that are null or not directly relevant. The cluster should only include evidence that supports the relationship between the findings.
8. The unresolved specialist findings are not all disclosed in the final report's unresolved_questions. For example, PNL-F6 and PNL-F7 are listed as unresolved in the specialist findings but are not included in the unresolved_questions array. They should be added.
9. The final report includes potential_unauthorized_activity_indicators that are not directly supported by verified findings. For example, the indicator about data inconsistencies masking unauthorized changes is speculative and should be removed or rephrased as a control weakness.
10. The final report's executive summary and overall risk assessment should be revised to reflect the corrections above.

## Recommended Follow-up

- Obtain limit change approval and effective-date history for MOCK_LIMIT_01_01 to confirm whether the change was retrospective.
- Investigate root cause of recurring VaR breaches on MOCK_PC_FLOW and assess limit appropriateness.
- Confirm extract freshness and obtain closure evidence for open excess events.
- Verify Colibris workflow data completeness and correct timestamp/increaseId inconsistencies.
- Clarify limitType definitions in Colibris and SGMR and align interpretations.
- Obtain a documented unique ID bridge between Colibris and SGMR for reconciliation.
- Review adjustment 96600008 with desk to confirm business rationale and approval.
- Follow up on pending managerial validation for commentary records and confirm validation coverage for all active GOPs.

## Evidence Index

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9169:9169`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9217:9217`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9265:9265`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=42:42`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9409:9409`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=32:32`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=44:44`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=6:6`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=7:7`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=12:12`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=10:10`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=1:1`
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:9`
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=9:12`
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=16:18`
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=22:25`
- `source://risk_commentary/quarterly_reviews_summary_var_svar_comment.md#lines=269:269`
- `source://risk_commentary/quarterly_reviews_summary_ia_comment.md#lines=134:134`
- `source://risk_commentary/quarterly_reviews_summary_pnl_comment.md#lines=134:134`
- `source://risk_commentary/quarterly_reviews_summary_risk_metrics_comment.md#lines=134:134`
- `source://risk_commentary/quarterly_reviews_summary_stress_test_comment.md#lines=134:134`
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=1586:1886`
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=66:402`
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=1139:1499`
- `source://post_trade_controls/breaches.csv#rows=1:14`
- `source://risk_commentary/quarterly_reviews_summary_ia_comment.md#lines=1:370`
- `source://risk_commentary/quarterly_reviews_summary_pnl_comment.md#lines=1:370`
- `source://risk_commentary/quarterly_reviews_summary_risk_metrics_comment.md#lines=1:370`
- `source://risk_commentary/quarterly_reviews_summary_stress_test_comment.md#lines=1:370`
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=3129:3129`
- `source://pnl/pnl_adjustment_2025-07-01-2026-06-30.csv#rows=1:1`
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=1:1`
- `source://pnl/validation_history_07-01-2025-30-06-2026.csv#rows=24:24`
- `source://pnl/AIR_PNL_PC_Filtered_Jul2025_Jun2026.xlsx#sheet=Sheet1&rows=6:6`
- `source://income_attribution/attribution.csv#rows=1:1`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=9:9`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=16:16`

## Specialist Report References

- risk_metrics: RISK
- pnl: PNL
- post_trade_controls: CONTROLS
- risk_commentary: COMMENTARY
