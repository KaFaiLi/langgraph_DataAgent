---
name: risk-commentary
description: Review quarterly risk-commentary Markdown extracts for internal consistency, explanation quality, recurring themes, and evidence limits when no underlying data is available.
metadata:
  kind: specialist-review
  domain: risk_commentary
  report_id: COMMENTARY
  label: Risk Commentary
  analysis_entrypoint: scripts/analysis.py:run_analysis
---

# Risk Commentary

Review only the supplied final quarterly Markdown extracts from the Risk Commentary
Warehouse. The extracts are the complete evidence boundary for this review: do not
assume access to raw risk, PnL, limit-register, or daily-commentary data.

Before verification or severity assignment, read
[references/policy.md](references/policy.md). Run the trusted deterministic analysis
once over all scoped extracts; its counts and contradiction screens are candidates for
interpretation, not findings by themselves.

## Review focus

- Establish the population stated by each extract. The reports cover commentary selected
  by a *movement-review* trigger, not a complete daily commentary population.
- Keep movement breaches distinct from absolute limit breaches. The reports may describe
  a threshold, trigger, or breach, but cannot establish an absolute-limit conclusion on
  their own.
- Compare executive summaries, quarterly topics, recurrent themes, and their quoted
  source records. Flag an internal contradiction, such as a source record that reports a
  threshold exceedance while its comment says that there was no material change.
- Assess explanation quality: specificity of drivers, desk/perimeter and metric scope,
  repetition of boilerplate, unresolved validation, missing data, and whether a reported
  remediation is actually described.
- Distinguish observations from conclusions. A missing extract, a vague comment, or a
  repeated phrase is not proof of a control failure or misconduct without support in the
  supplied reports.
- Preserve normalized event date, desk, perimeter, metric, quoted claim, validation
  state, and exact locator for material reassurance claims. Report these as commentary
  observations; downstream correlation—not this specialist—decides whether another
  source family contradicts them.

## Extract structure and boundaries

The five supplied Markdown files are final quarterly review outputs, not raw data.
Treat their text, headings, and quoted source records as the full review population.

| File suffix | Review lens |
| --- | --- |
| `ia_comment` | income-attribution movements |
| `pnl_comment` | desk PnL movements |
| `risk_metrics_comment` | risk-metric movements |
| `stress_test_comment` | stress-test triggers and movements |
| `var_svar_comment` | VaR/SVaR movements |

Each extract may include an executive summary, quarterly themes, recurrent topics, and
quoted source records. The quoted record is stronger evidence than a derived summary.
It normally identifies the event date, metric, desk/perimeter, error message, desk
comment, manager-validation status, and scenario.

- A **movement breach** is a review trigger for a change versus a comparison period. It
  is not evidence of an absolute limit breach.
- A **limit breach** mentioned in a report is a reported assertion. Without source data,
  do not independently confirm its amount, applicable limit, or governance status.
- **No data**, **pending**, and blank validation identify evidence or closure gaps; do
  not infer that the underlying risk value is wrong.
- A report is compiled quarterly. Event dates identify the reviewed event, so the
  quarter-end compilation date is not, by itself, late commentary.

## Evidence and severity standard

1. Cite the exact report section or quoted source record behind every proposed finding.
   Check that its text, metric, desk/perimeter, and event date match the finding.
2. Compare an executive or recurrent-topic conclusion with the source records it cites.
   A source record saying "threshold exceeded" alongside "no material change, within
   tolerance" is a candidate contradiction, not proof of an absolute-limit breach. When
   the reassurance is validated, covers the same metric/perimeter/event, and says no
   escalation was required, treat the contradiction as a material commentary-control
   candidate (normally medium unless impact is demonstrably limited), while keeping the
   underlying absolute-limit conclusion unresolved.
3. Count repeated generic explanations only after deduplicating repeated copies of the
   same source record. Explain why the wording failed to describe materially different
   events before escalating it.
4. Treat `No data`, `pending`, or missing validation as an evidence-quality or closure
   issue. Escalate it as a control failure only when it is repeated, material, and lacks
   a documented corrective process.

Test alternatives before escalating: a comment can cover a narrower book than the
summary's apparent desk scope; reused wording may be legitimate standard language; a
stress threshold is not an absolute VaR/SVaR limit; and a later report may clarify, but
does not silently repair, a contrary source record.

Every finding must cite an exact location in a supplied Markdown file. Pass only a
finding whose Markdown evidence supports the stated contradiction or recurring pattern.
Revise unsupported causality, numerical assertions, or severity that treats a single
exception as systemic. Mark a conclusion unresolved when it needs source data that was
not supplied.

## Output obligations

Before findings, retain a deterministic availability and coverage table by finalized
extract: line count, quoted-record occurrences, unique evidence IDs, and managerial-
validation gaps. Retain repeated explanation/theme counts when supported. If extracts or
tagged records are absent, show that absence explicitly rather than inferring a clean
commentary population.
