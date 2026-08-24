---
name: post-trade-controls
description: Review post-trade breaches, approvals, remediation, recurrence, control ownership, and workflow timeliness.
metadata:
  kind: specialist-review
  domain: post_trade_controls
  source_domains:
    - post_trade_controls
  report_id: CONTROLS
  label: Post-trade Controls
  analysis_entrypoint: scripts/analysis.py:run_analysis
---

# Post-trade Controls Review

Review only the assigned post-trade control sources. Run the trusted deterministic
analysis before interpreting control events. Treat exceptions as review candidates,
not proof of misconduct or control failure.

Read [references/policy.md](references/policy.md) before drafting or verifying findings.
Reconcile event dates, owners, approval and closure state, remediation, recurrence,
severity and available counter-evidence. Every non-observation conclusion must cite a
reopenable `source://` locator. Use only PASS, REVISE, REJECT, or UNRESOLVED verification
outcomes; inaccessible evidence is UNRESOLVED and exhausted revisions remain unresolved.
