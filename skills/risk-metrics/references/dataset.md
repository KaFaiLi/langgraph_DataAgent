# Finalized Risk Metrics Dataset Contract

Use this contract for the finalized SGMR consumption and Colibris excess files. Match
columns case-insensitively and allow additional columns, but do not silently substitute a
field with a different business meaning.

## SGMR limit-consumption history

The finalized parquet contains daily observations at the expected grain:

`consoValueDate × limId × stranaNodeName × rmRiskIndicator × consoVersion`.

In the use-case-1 file this is 12,528 rows: 261 business dates, 12 portfolios, four risk
metrics, and 48 limit/portfolio/metric series. The grain must still be established from
each reviewed source; these counts are not universal thresholds.

### Material fields

| Purpose | Columns | Interpretation |
| --- | --- | --- |
| Limit identity and type | `limId`, `limType`, `limFrequency`, `limEligibleCheckpoint` | Stable limit definition and monitoring cadence |
| Limit dates | `limStartDate`, `limEndDate`, `eligibleCheckpointStartDate` | Test whether a value date lies in the stated effective range; they are not approval dates |
| Current bounds | `limMinValue`, `limMaxValue` | Directional lower and upper bounds used for utilization when valid |
| Initial and temporary bounds | `limInitialMinValue`, `limInitialMaxValue`, `limTempMinValue`, `limTempMaxValue` | Initial/current differences are change candidates; temporary values require separate timing and precedence evidence |
| Warning threshold | `limRelativeThreshold` | Dimensionless early-warning ratio when strictly between zero and one; not the hard limit |
| Units | `limUnit`, `limDisplayUnit`, `consoValueEur` | `MEUR` means millions of euros; do not infer another scale from `rmCurrency` |
| Metric definition | `rmRiskIndicator`, `rmRiskMetricName`, `rmRiskMetricLabel`, `rmRiskMetricNameGeneric`, `rmRiskMeasureId`, `metricType_LB`, `paramTypeId` | Keep definitions stable within a series; labels do not supply horizon, confidence, or scenario methodology |
| Observation | `consoId`, `id`, `consoValue`, `consoValueDate`, `consoLastValueDate`, `consoCreationDate`, `consoVersion`, `consoOfficialStampIndic`, `consoSource` | Risk value, business date, lineage, version, and processing timing |
| Desk hierarchy | `stranaBu`, `stranaSbu`, `stranaGrppc1`, `stranaGrppc2`, `stranaGrppc3`, `stranaPc`, `stranaNodeName`, `flatStrana` | Explicit hierarchy normally ends at portfolio (`stranaNodeName`); reperform the JSON-to-column mapping in `flatStrana` |
| Risk descriptors | `rmProductType`, `rmProductName`, `rmCurrency`, `rmGeographicalArea`, `rmPositionType`, `rmActivitySector`, `rmDNDScope` and their `Lnk` variants | Explain the desk risk represented by a series; labels are not necessarily aggregation keys |
| Factor/scenario axes | `metricSpecification*_LB`, `underlyings*_LB`, `rmUnderlying*`, `rmTimeBucket*`, `rmStrikeBucketLnk`, `rmCurrencyPair*`, `bucket_LB`, `maturity_LB`, `consoSttScenario`, `STT Equivalent Shock`, `Sensibility Shock` | Use only populated, well-defined axes; absence prevents granular concentration or scenario claims |
| Governance ownership | `limRequestOwner`, `limConsumptionOwner`, `limDelegation`, `limReporting` | Ownership and routing evidence, not proof of approval |
| Cross-system hint | `colibrisId` | Potential reference only; establish value-level matches before using it as a join key |

The exported schema also contains sparse `param1`–`param10`, custom axes, issuer, credit
index, curve, liquidity, rating, debt-seniority, product-link, position-link, and second-
underlying fields. Null optional axes do not constitute missing data unless the metric
definition or review scope requires them.

### Utilization rules

- For a non-negative `consoValue`, calculate `consoValue / limMaxValue`.
- For a negative `consoValue`, calculate `abs(consoValue) / abs(limMinValue)`.
- A utilization above 1 is a hard-bound breach candidate. A utilization at or above a
  valid `limRelativeThreshold` is a warning/proximity candidate.
- Do not replace the current bound with a temporary bound unless the source supplies its
  effective dates, approval, and precedence. Surface the ambiguity instead.
- Do not sum VaR, SVaR, or stress across portfolios. Such measures are normally
  non-additive. Aggregate exposure only when its measure definition explicitly permits it.
- `consoValueEur` supports common-currency comparison only when its scale and relationship
  to the limit are consistent. `rmCurrency` describes the risk currency and does not
  override a `MEUR` reporting unit.

## Colibris excess and workflow history

The finalized CSV contains one current/history record per `excessId`. It is an
excess-selected population, not all daily risk observations.

### Material fields

| Purpose | Columns | Interpretation |
| --- | --- | --- |
| Event and timing | `excessId`, `excessCreationDate`, `excessLastConsoValueDate`, `excessCloseDate`, `closingConsDate` | Event identity, recorded consumption date, workflow creation, and closure |
| Desk and metric | `perimeterMnemonic`, `perimeterLevel`, `colibrisSbu`, `riskIndicator`, `riskType`, `riskMetricName`, `scenario`, `underlying` | Event scope; `perimeterMnemonic` is commonly PC-level and may not identify one portfolio |
| Limit and magnitude | `limitType`, `limitValue`, `unit`, `excessLastConsoValue`, `creationConsValue`, `creationConsDate`, `usage`, `excessMaxUsage`, `frequency` | Reperform current usage; `excessMaxUsage` is a percentage, while `usage` is formatted text |
| State | `excessStillOpen`, `excessWorkflowStatus`, `daysInExcess`, `excessCloseDate`, `closedManually` | Check state/closure consistency; duration convention may be calendar or business days |
| Explanation | `lastExcessExplanationCreationDate`, `lastExcessExplanationClassification`, `lastExcessExplanationIsExcessConfirmed`, `lastExcessExplanationCause`, `lastExcessExplanationAnticipation`, `lastExcessExplanationActionPlan`, `lastExcessExplanationDeadline`, `lastExcessExplanationSolution`, `lastExcessExplanationFullname`, `lastExplanationRequestDate` | First-line explanation and remediation evidence |
| Validation | `lastExcessValidationCreationDate`, `lastExcessValidationClassification`, `lastExcessValidationDecisionDetails`, `lastExcessValidationIsSatisfactory`, `lastExcessValidationFullname` | Risk/control validation evidence; classification values require a state dictionary |
| Technical follow-up | `lastExcessValidationTechnicalType`, `lastExcessValidationTechnicalSubType`, `lastExcessValidationTechnicalDeadline`, `lastExcessValidationTechnicalFollowUp`, `excessValidationTechnicalConsumptionOwners` | Technical remediation and owners |
| LoD2 | `lastExcessValidationLod2CreationDate`, `lastExcessValidationLod2DecisionDetails`, `lastExcessValidationLod2IsSatisfactory`, `lastExcessValidationLod2Fullname` | Second-line review evidence; confirm which events require it |
| Limit increase | `increaseId`, `increaseWorkflowStatus`, `increaseCreationDate`, `increaseValidationTrdDirCreationDate`, `increaseValidationRisqCreationDate` | Workflow timeline; no field here states the changed limit's effective date |
| Timeliness summaries | `daysWithoutValidationTotal`, `daysWithoutExplanation`, `daysWithoutValidateExplanation`, `nbDaysFoFirstComment`, `totalNbDaysFo`, `avgNbDaysFo`, `nbDaysMmgFirstComment`, `nbDaysMmgLastComment`, `totalNbDaysMmg`, `avgNbDaysMmg`, `nbDaysWaitingTrader`, `nbDaysWaitingMacc` | Profile distributions; do not call them SLA failures without the governing calendar and threshold |
| Ownership/governance | `requestOwner`, `consumptionOwner`, `limitDelegation`, `delegationRisq`, `limitRegulatoryFlag` | Ownership and regulatory classification |
| System reference | `sgmrId` | Potential lineage key, but it must match a field in the supplied SGMR extract before use |
| Derived tags | `LLM_Explanation_Cause`, `LLM_Explanation_Solution` | Machine-generated annotations; never independent evidence of cause, solution, or approval |

`riskMetricComment`, customer-deal flags, validation technical fields, user names, and
decision details may add context. Blank values are control gaps only when the applicable
workflow requires them for that event state and classification.

## Date and state semantics

- Consumption/value dates describe risk. Creation timestamps describe system or workflow
  processing. Do not substitute one for the other.
- Recalculate calendar lag from timestamps, but apply business-day SLA conclusions only
  with a calendar, timezone, cutoff, and policy threshold.
- A record marked open with a past action deadline is an unresolved/stale candidate as of
  the extract, not automatically a confirmed overdue breach. Confirm file freshness and
  later history.
- `VALIDATED`, `TECHNICAL`, `PASSIVE`, and similar labels are categorical evidence. Their
  finality and escalation meaning require the state dictionary.
- A populated limit-increase status with no usable ID or dates is an internal consistency
  candidate. Approval dates after an excess do not prove retrospective limit application
  because the changed limit's effective date is not present.

## Cross-source joins

| Question | Colibris fields | SGMR fields | Qualification |
| --- | --- | --- | --- |
| Same limit definition | `perimeterMnemonic`, `riskIndicator`, `riskMetricName`, `unit`, `limitValue` | `stranaPc`, `rmRiskIndicator`, `rmRiskMetricName`, `limUnit`, directional bound | Compare normalized text and numeric tolerance; inspect type and owner differences separately |
| Event date covered | above fields plus `excessLastConsoValueDate` | above fields plus `consoValueDate` | A weekend/holiday or out-of-period date can legitimately lack a daily row |
| Event-to-observation lineage | `sgmrId` | `limId`, `consoId`, `id`, or a documented mapping | Must be unique and source-backed; semantic matching alone is insufficient |
| Portfolio assignment | PC-level event plus `underlying` | `stranaPc`, `stranaNodeName`, risk axes | One PC can contain many portfolios; do not choose one without a bridge |
| Limit governance | increase workflow timestamps | current/initial/temporary bounds and effective dates | Requires the changed limit, effective date, and approval record in the same lineage |

When direct IDs do not match and a PC contains several portfolios, definition coverage
can still be tested, but event-value reconciliation remains `UNRESOLVED`. Report exact
semantic-date matches, ambiguous matches, weekends/holidays, and dates outside the SGMR
extract separately.
