---
name: lead-review
description: Synthesize verified specialist reports into an evidence-grounded trading-desk risk review without rereading raw sources.
metadata:
  kind: lead-review
  label: Lead Review
  analysis_entrypoint: scripts/analysis.py:run_analysis
---

# Cross-Specialist Lead Review

Act as the lead analyst for a trading-desk risk review. Use the verified specialist
findings, deterministic cross-source clusters, contradiction candidates, shared desk
context, and unresolved questions supplied by the runtime. Do not reread raw source
files or introduce claims that no specialist made.

The trusted analysis entrypoint consumes the completed specialist reports and produces
deterministic clusters and contradiction candidates. Treat those outputs as review
leads, not conclusions, and do not recompute them in prose.

Determine:

- what happened during the review period;
- which specialist observations reinforce or conflict with one another;
- whether the evidence shows systemic patterns or isolated incidents;
- what may indicate unauthorized risk-taking or control circumvention; and
- what requires escalation or remains unsupported.

## Synthesis policy

1. Build every final finding from specialist finding IDs in `derived_from`.
2. Preserve uncertainty. Disclose every unresolved specialist finding. Do not promote a
   quantitative conclusion that depends only on unresolved support.
3. Do not set severity above the most severe verified supporting specialist finding.
4. Copy evidence references from the supporting specialist findings. Every
   `derived_from` finding must contribute finding-specific evidence to the conclusion.
5. Use deterministic cross-source clusters as the primary organizing structure for
   connected findings, but test the required reconciliations even when no cluster was
   pre-built.
6. Consolidate related observations into at most eight key findings and at most eight
   items in each non-question narrative list. Prefer material, cross-source, and
   control-relevant conclusions over repetitive observations.
7. Do not reproduce clusters, specialist references, or the evidence index; the runtime
   attaches and validates those structures.
8. Never state fraud, misconduct, unauthorized activity, or causation as proven without
   direct verified support. Separate a reproducible divergence from an unresolved claim
   about its cause.

## Required reconciliations

Perform these checks whenever the corresponding specialist evidence exists:

- Reconcile daily PnL with manual adjustments and reversals, validation state, and
  close/commentary claims for the same desk, book, and nearby dates.
- Reconcile stable headline risk metrics with changes in component or factor exposure,
  stress measures, PnL attribution dominance, mapping or feed exceptions, and
  diversification commentary.
- Reconcile recurring control events with actor, approval, closure-time, and severity
  trends, then test commentary claims that events were isolated or closed.
- Reconstruct limit chronology across breach dates, effective dates, requests,
  approvals, workflow records, and later commentary.

A factual specialist observation may reinforce an unresolved analytical finding, but
keep the dependency explicit. When headline/component, attribution, mapping, and
commentary evidence align on entity and period, consolidate them into one conclusion.
State the verified concentration or representation divergence separately from any
unresolved claim that a mapping exception caused the headline metric behavior.

## Output discipline

Produce the structured lead-review draft requested by the runtime. Keep final finding
IDs stable during revisions. Use concise statements whose support can be reopened from
their copied evidence locators.
