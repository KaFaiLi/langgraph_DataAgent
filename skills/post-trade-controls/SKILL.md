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

## General-agent tools

Load these instructions with `load_skill(name="post-trade-controls")`. Read both references using
`load_skill_reference(name="post-trade-controls", reference="dataset")` and `reference="policy"`;
follow `next_offset` on partial results. Inputs are not prepared implicitly by a graph.
Inspect the source inventory and schemas, then call
`execute_review_analysis(skill_name="post-trade-controls", source_paths=[...])` with all assigned
paths. The host resolves the trusted entrypoint; do not supply Python modules or scripts.
Read the stored candidates and overviews with `read_analysis_result`, follow pagination,
and inspect cited regions with `reopen_analysis_evidence`. Submit the typed analyst draft
with `submit_candidate_result`, retaining deterministic candidate IDs, contrary evidence
and unresolved limitations. The submission stays pending until independent verification.
For a persistent run or delegated review role, use the supplied run/assignment IDs with
`execute_assigned_analysis`, `read_assigned_analysis` and `review_source_tool` instead.
Return the required typed JSON result to the host; it records the pending candidate or
independent role result. Tools outside the declared role are unavailable. Challengers
research independently; adjudicators receive evidence and challenges with no source tools.
Tool summaries, truncated references and source previews never establish full coverage.
