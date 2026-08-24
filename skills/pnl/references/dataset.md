# Finalized PnL Dataset Contract

Use this contract for the finalized use-case-1 structure. Match column names
case-insensitively and permit additional columns, but do not silently substitute fields
with different business meanings.

## AIR accumulated PnL

Expected columns:

`Value Date`, `Version`, `BU`, `SBU`, `GPC1`, `GPC2`, `GPC3`, `PC`, `GGOP`, `GOP`,
`PTF`, `Notion`, `REGION`, `Currency`, `DTD`, `WTD`, `MTD`, `QTD`, `YTD`.

- Expected grain: one row per Value Date, Version, Notion, and PTF for a stable hierarchy
  and currency. If the source contains several rows at that key, first determine whether
  another dimension is needed; do not sum duplicates blindly.
- `Value Date` is the business date of PnL. It is not a file-creation timestamp.
- `DTD` is the daily movement. Reperform `WTD`, `MTD`, `QTD`, and `YTD` as cumulative DTD
  within the same Version, Notion, PTF, and Currency series, using calendar week (Monday
  start), month, calendar quarter, and calendar year resets.
- The hierarchy is `BU -> SBU -> GPC1 -> GPC2 -> GPC3 -> PC -> GGOP -> GOP -> PTF`.
  Blank `GGOP` is permitted only when the source population supports that mapping; core
  keys such as Value Date, Version, GOP, PTF, Notion, Currency, and DTD must be present.
- `Currency` identifies the row currency, but the headers do not state whether PnL is in
  currency units, thousands, millions, or a common reporting currency. Do not aggregate
  across currencies or reconcile to `AMOUNTINEUR` without external unit documentation.
- The headers do not declare whether positive DTD is income and negative DTD is loss in
  every notion/version. Describe sign direction until the selected notion's convention is
  source-backed; do not silently invert a series.

## PnL adjustments

Expected columns:

`ADJUSTMENTID`, `GOP`, `PTF`, `CCY`, `AMOUNT`, `AMOUNTINEUR`, `COMMENTS`,
`CREATIONDATE`, `USER`, `VALDATEBEGIN`, `VALDATEEND`, `SBU`, `PC`, `NATURE`,
`ADJUSTMENTLINKID`, `INSTRUMENT`, `FILEPATH`, `JEDAIID`, `JEDAIIDLINK`, `FOLDER`,
`SOURCE`, `REGION`, `PNLCOMPONENT`, `CRAFTINDICATOR`, `DEALID`, `SECURITYID`,
`CCYPAIR`, `EXCHANGERATE`, `PNLTYPE`, `TPR`, `NATUREID`, `TYPE`, `TYPO`,
`MACROTYPO`, `ENDEVENT`, `MACRONAME`, `MACROLOG`, `INCIDENTID`, `DOCUMENTID`,
`ADJUSTMENTSOURCE`, `RCCODE`, `CPMIMPACT`.

- Expected grain: one adjustment record per `ADJUSTMENTID`. A link ID may connect related
  entries and is not necessarily unique.
- `VALDATEBEGIN` and `VALDATEEND` define the economic period. `CREATIONDATE` measures
  processing timing. Never use creation date as a substitute for valuation date.
- `AMOUNT` is in `CCY`; `AMOUNTINEUR` is the EUR-translated amount. Reperform the supplied
  conversion as `AMOUNT * EXCHANGERATE`, allowing only documented rounding tolerance.
- Positive and negative adjustment amounts are directional entries. A negative amount is
  not automatically a correction or reversal; use nature, component, link, valuation
  dates, and the opposite entry together.
- `SOURCE`, `NATURE`, `NATUREID`, `TYPE`, `INSTRUMENT`, `TPR`, and `PNLCOMPONENT` describe
  different classifications. Do not collapse them into a single manual/freeze label.
- Empty deal, security, incident, document, or filepath fields can be structurally valid.
  Their control significance depends on adjustment type and the applicable procedure.

## Validation history

Expected columns:

`gop`, `team`, `state`, `creationTime`, `active`, `user`, `api_request_date`, `pnlType`.

- Expected grain: a validation-state record for GOP, team, API request date, and PnL
  type. History may contain more than one record at that grain, but there must not be
  multiple active records for the same business key unless the workflow specification
  permits them.
- `api_request_date` identifies the PnL population date. `creationTime` is the validation
  record timestamp. Negative or long lags must be interpreted using the PnL-type schedule
  and timezone; they are not automatically late.
- `pnlType` populations such as FLASH and STAB may have different calendars and
  deadlines. Measure each separately.
- `state` is categorical workflow evidence. This format provides no monetary difference,
  unexplained PnL, age, approval, or break amount. Do not run amount-based validation
  tests from state text.
- `active` selects the currently applicable record; preserve inactive rows as history.

## Cross-source joins

| Question | Left fields | Right fields | Required qualification |
| --- | --- | --- | --- |
| Adjustment belongs to PnL hierarchy | adjustment PTF | PnL PTF | GOP, PC, and CCY/Currency must agree |
| Adjustment has an applicable PnL date | VALDATEBEGIN..VALDATEEND | Value Date | Respect business calendars and ranges |
| Validation covers a PnL population | validation gop | PnL GOP | Compare stated scope, Version, Notion, and PnL type |
| Processing timing | CREATIONDATE or creationTime | valuation/request date | Use the relevant workflow SLA and timezone |
| Monetary reconciliation | AMOUNTINEUR | DTD or accumulated PnL | Requires units, sign, version, notion, and inclusion rule |

The last relationship is deliberately unresolved by the file headers. Do not infer that
the accumulated PnL is pre-adjustment or post-adjustment, or that DTD is denominated in
EUR millions, without source-backed documentation.

## Wide AIR income attribution export

The supported wide export has one observation per `asofdate` and reported hierarchy,
including `bu`, `sbu`, `grppc100`, `grppc200`, `grppc300`, `td`, `pc`, `ggop`, and `gop`.
The pasted FSI format contains 131 columns and is recognized when it provides at least:

`asofdate`, `gop`, and `Final Result Acc DTD`.

The non-cumulative attribution fields include `Unexplained`, `Market Effect`, `FX`, fee
fields, `Theta/FIN`, `N&M`, `Other`, `EDM/EDMN`, `Profit Sharing`, `Other NTX`, `Other
S/F`, the `ia_*` flags, `No IA`, and `hypo_pnl_dtd`. The corresponding fields ending in
` Cumulative` are supplied cumulative values. Product and risk breakdowns such as
`Equity`, `Rates`, `Credit`, and their child fields are retained as source columns but
are not added to their parent buckets.

Use `asofdate` for time ordering. `Final Result Acc DTD` is the reported total in the
source's own units; no currency, scale, sign convention, or pre/post-adjustment basis is
declared by these headers. `status`, `validated`, `isbatchvalidated`,
`air_mpc_validation_status`, and `air_fo_validation status` are categorical workflow
fields. A value such as `IA process is running` is an observation requiring the workflow
state dictionary and applicable SLA, not proof of a control failure.

The deterministic runner compares the final DTD total with `Final Result Acc DTD
Cumulative` within each complete hierarchy series. It also profiles primary buckets
independently and reports their residual/concentration shares. Those views are not a
substitute for a monetary reconciliation because the export contains nested fields and
does not declare how parent and leaf amounts should relate.
