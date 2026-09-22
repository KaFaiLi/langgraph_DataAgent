---
name: general-review
description: Coordinate an evidence-backed review across risk metrics, composite PnL, post-trade controls and risk commentary using trusted tools and specialist roles.
---

# General review

Establish the requested review period, desk context, source scope, and output location.
The model chooses investigations, specialist assignments, peer verification, revisions,
and synthesis. Use capabilities as operations; never invoke the legacy review service
or a tool wrapping a fixed review graph.

Load the relevant specialist instructions with `load_skill`, then read its `dataset`
and `policy` using `load_skill_reference`. Follow `next_offset` until every required
reference page is read. Select domains from source schemas and content; composite `pnl`
owns income attribution, validation, and adjustments together with PnL.

For a persistent review, call `initialize_review_run(run_id, desk_context)` using the
host's configured source/output roots, then page through `review_inventory`. Resolve
ambiguous or unclassified sources with `classify_review_source` and create specialist
assignments with `assign_review_work`. Use `execute_assigned_analysis`,
`read_assigned_analysis`, `review_source_tool`, and `submit_assigned_candidate` for
those assignments. Record source and candidate dispositions with their named operations.
Use `review_coverage` as the authoritative outstanding-work list; findings, material
omissions and unsupported sources remain visible independently of conversation text.
A host-bound review server exposes only these scoped capabilities. A run or assignment
ID does not grant access to another scope.

For an isolated exploratory slice without a run, use `list_sources` and table/document
inspection to identify all supplied material.
Explicitly disclose unreadable, ambiguous, unclassified and out-of-period sources.
A bounded inventory or preview is not proof of complete source or population coverage.

Call `execute_review_analysis(skill_name, source_paths)` for the selected specialist.
The tool resolves only registered trusted calculations. Inspect `read_analysis_result`
for candidates, overviews and full details, following pagination. Retain stable
candidate IDs. Reopen supporting and contrary evidence with `reopen_analysis_evidence`.
Calculations establish leads; interpret alternative explanations, data quality,
population, timing, severity and uncertainty before drafting findings.

Submit an evidence-backed draft with `submit_candidate_result`. This returns a stored
reference with pending verification status. It is not a verified report. Account for
every material deterministic candidate with a finding, source-backed disposition, or
explicit unresolved disclosure. Do not silently drop findings or candidates to fit a
response limit. Source integrity failures must stop dependent conclusions.

When independent roles and publication capabilities are available, coordinate trusted
specialists, challengers, adjudicators and the lead using their declared contracts.
Challengers must independently investigate without analyst anchoring; adjudicators
must not conduct raw-source research. The lead synthesizes validated specialist reports
and deterministic cross-report analysis without rereading raw sources. Require valid
verification records tied to each finding version, complete source/candidate accounting,
reopenable evidence, copied finding-specific support, and severity ceilings.

Deliver specialist JSON/Markdown, data overviews, verification history, research traces,
final synthesis and a validated run manifest through the publication capability.
Repair reported unmet requirements and retry within the remaining budgets. Never equate
a draft reference, successful tool execution or free-form answer with published completion.
If capabilities or budgets cannot meet the requested scope, describe the missing work
and preserve pending results for continuation. Report truncation, failures, interruption
and unresolved dependencies explicitly; never invent PASS decisions or completed artifacts.
