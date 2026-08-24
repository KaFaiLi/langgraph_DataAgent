# Specialist Skill Development

## Scope and Current Status

This file governs `skills/`. `risk-metrics`, composite `pnl`, and `risk-commentary` are
implemented analytical skills discovered by `src/risk_analysis_agent/skills/` and
executed through the generic bounded specialist graph. `risk-ppt` remains the downstream
presentation skill. The composite `pnl` skill owns PnL, income-attribution, validation,
and adjustment source domains so these related records are reviewed by one bounded
specialist. Post-trade controls is also a first-class skill-backed specialist. There
are no legacy capability adapters or per-domain specialist graphs. `lead-review` owns
the cross-specialist synthesis policy, verifier policy, and deterministic candidate
linking; evidence integrity, severity bounds, and graph routing remain shared Python
responsibilities.

Read `risk-ppt/SKILL.md` before changing the PPT skill. It consumes completed review
Markdown/JSON only, keeps raw risk sources out of scope, validates semantic SVGs, and
uses the project DeepSeek factory through production Python code.

## Ownership Boundary

- A skill owns what a specialist should do: domain concepts, expected datasets,
  materiality, mandatory checks, alternative explanations, evidence discipline,
  verifier challenges, uncertainty, and output expectations.
- Shared Python owns how safe operations work: parsers, guarded file access, locator
  handling, date normalization, tabular reads, generic statistics, sandboxing, and
  search primitives.
- LangGraph owns when work runs: preparation, deterministic analysis, analyst/verifier
  routing, retry limits, coverage, aggregation, failure, and checkpointing.

The `lead-review` skill is not a specialist and has no source domain or raw-source
analysis entrypoint. Its trusted entrypoint consumes completed specialist reports and
returns deterministic cross-specialist candidates; it also configures the lead analyst
and lead verifier prompts. Do not register it in `SPECIALISTS` or dispatch a review task
for it.

Do not place VaR definitions, smoothing methodology, control-governance rules, column
dictionaries, or domain verifier checklists in orchestration. Do not copy generic table,
date, locator, or statistical helpers into each skill.

## Proposed Analytical Skill Layout

Use kebab-case skill folders and snake_case runtime domain IDs:

```text
skills/risk-metrics/
|-- SKILL.md
|-- references/
|   |-- dataset.md
|   `-- policy.md
`-- scripts/
    `-- analysis.py
```

The analytical skill set is `risk-metrics`, composite `pnl`, `post-trade-controls`, and
`risk-commentary`, alongside `risk-ppt`. Income attribution belongs to the composite
`pnl` specialist because it must be reviewed with PnL in one report. Do not create
separate `pnl-validation`, `pnl-adjustments`, or `income-attribution` runtime skills;
those source domains belong to the composite `pnl` specialist.

Use YAML front matter consistent with `risk-ppt/SKILL.md`. A proposed analytical shape
is:

```yaml
---
name: risk-metrics
description: Review risk metrics, limits, stresses, sensitivities, and governance.
metadata:
  kind: specialist-review
  domain: risk_metrics
  source_domains:
    - risk_metrics
  report_id: RISK
  label: Risk Metrics
  analysis_entrypoint: scripts/analysis.py:run_analysis
---
```

The schema is formalized in Pydantic. `domain` is the active specialist identity;
`source_domains` lists the manifest classifications owned by that specialist and
defaults to the primary domain. Validate unique names/domains/report IDs, exclusive
source-domain ownership, required documentation, relative paths, allowed skill kind,
and entrypoint containment. Do not add model IDs, API keys, or retry policy to each
skill.

## SKILL.md and References

Keep `SKILL.md` compact enough to load as working instructions. It should identify the
review purpose and sources, key domain concepts, questions to answer, mandatory
deterministic checks and interpretation, cross-source checks, materiality thresholds,
insufficient evidence, benign alternatives, locator requirements, verifier challenges,
output obligations, and uncertainty/failure handling.

Put column meanings, aliases, units, sign conventions, and dataset examples in
`references/dataset.md`. Put the detailed challenge checklist and decision methodology
in `references/policy.md`. A skill must stand on domain reasoning, not eval case wording;
never include planted gold answers or case-specific shortcuts.

## Deterministic Analysis Contract

Domain-specific numerical logic moves from a temporary
`capabilities/<domain>/analysis.py` module to the skill's trusted script. Use the
validated entrypoint shape:

```python
def run_analysis(
    ctx: ToolContext,
    source_paths: list[str],
) -> Sequence[BaseModel]:
    ...
```

The script is authoritative for calculations; the LLM interprets its structured output.
Keep logic deterministic, independently unit-testable, and source-locator aware. Reuse
`tools/` and `ingestion/` rather than reimplementing them.

The lead-review entrypoint has a separate cross-specialist contract:

```python
def run_analysis(
    reports: list[SpecialistReport],
) -> CrossSpecialistAnalysis:
    ...
```

It owns deterministic entity extraction, temporal matching, clustering, and
contradiction-candidate detection over verified and unresolved specialist findings. It
must not reread raw review sources or turn a candidate into a final conclusion.

Only load version-controlled scripts beneath the expected repository `skills/` root.
Reject absolute paths, `..`, symlink escapes, unrecognized entrypoint formats, and code
from review source data. Never use `eval()` or arbitrary user-provided imports. Skill
scripts receive guarded source/workspace access, must not open the network, must not read
credentials or eval gold, and must not instantiate LLM clients.

## Generic Runtime and Discovery

The runtime uses one generic bounded specialist workflow, not per-domain graph
implementations.
A validated `SkillDefinition` plus loader/registry provides the playbook, deterministic
runner, identity, report metadata, and classifier description to that workflow. Source
classification consumes registered specialists dynamically. Adding a migrated specialist
requires a skill folder and tests, not a new graph-builder or parallel label/report-ID
maps.

Preserve low-cost analyst and high-cost verifier allocation, evidence reopening, PASS/REVISE/
REJECT/UNRESOLVED behavior, exhausted-REVISE handling, report schemas, and verification
artifacts. `SpecialistDomain` is the typed identity used by manifests and orchestration.

## Migration and Tests

Do not add compatibility adapters or parallel implementations. Shared guarded source,
tabular, statistical, grep, and restricted-Python behavior is owned by
`data_agent.tools`; review code adds only manifest scoping, research budgets,
tracing, and domain analysis.

Behavior-oriented tests should prove all analytical skills are discoverable, front
matter and entrypoints validate, documentation and deterministic runners exist, every
registered skill runs through the generic graph, model tiers are correct, verifier loops
stay bounded, evidence and coverage guards survive, artifacts remain compatible,
checkpoint/resume works, and provider/sandbox/gold-isolation policies still pass. Move
domain analysis tests with their implementation; do not delete valuable assertions.
