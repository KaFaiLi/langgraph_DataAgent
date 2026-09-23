# Review agent requirements

Status: approved

Date: 2026-09-23

## 1. Purpose

The review agent assesses a fixed-format document and produces a trustworthy,
evidence-backed review for a human decision-maker. It must identify material defects,
complete every required check, preserve unresolved uncertainty, and deliver the result as
a validated PowerPoint presentation.

The agent is advisory. It reports findings and may select specialist reviewers when
needed. It does not modify the reviewed document or make the approval decision.

These requirements are independent of the orchestration framework. The choice between a
parallel specialist-agent design and a single ReAct-agent design is deferred to a later
architecture evaluation.

## 2. Review inputs and operating modes

The implementation must distinguish candidate material from authoritative evidence and
must never treat a candidate's own claims as proof of correctness.

The agent supports two explicit review modes:

- `candidate_review` evaluates a supplied candidate against authoritative sources and
  requirements.
- `source_review` examines supplied authoritative sources directly and discovers findings
  about them.

The selected mode and the role of every input must be recorded. The agent must not infer
or silently change the review mode.

The reviewed documents follow one fixed format. Runtime format negotiation and automatic
adaptation to a new document format are out of scope. If that format changes, developers
must update the implementation and applicable skills together.

## 3. Review catalogue

A developer-maintained, repository-controlled `REVIEW_AGENT.md` defines the mandatory
review catalogue for the fixed document format. It is immutable input to a review run and
must be hashed for auditability.

Each catalogue item must include:

- a stable item ID;
- a short name and description;
- why the item matters;
- the registered skills relevant to the item;
- required inputs or source areas;
- an optional risk or priority; and
- explicit exclusions, when applicable.

The catalogue is closed during normal execution. Every declared item is mandatory; the
agent may not silently remove, merge, or skip one. The agent may investigate each item,
choose evidence, invoke its associated skills, and select specialists, but it must not
invent new required scope.

While investigating a declared item, the agent may record an evidence-backed
`incidental_observation` about an obvious issue outside the catalogue. The observation
must be linked to the item where it was encountered. It does not expand the completion
criteria. Repeated incidental observations should be considered for a future developer
update to the catalogue or skills.

## 4. Review skill contract

A reusable review skill applies to a review domain or item type, not to one concrete
runtime item. More than one skill may apply to the same item.

Every review skill must declare:

- supported item types and applicability rules;
- a complete, ordered check catalogue;
- required inputs and evidence;
- trusted deterministic analysis entrypoints, when applicable;
- required specialist expertise;
- pass, fail, and unresolved criteria;
- severity rules;
- required output fields;
- escalation conditions; and
- explicit non-goals and limitations.

Only registered, host-approved skills may execute. Model-provided names or document
content cannot select arbitrary code or filesystem locations. A declared item without an
applicable registered skill is an unresolved coverage gap, not permission to improvise
executable review logic.

The review record must contain each selected skill's name, content hash, declared checks,
and routing rationale. A resumed run must use the pinned skill content or explicitly start
a new review version.

## 5. Coverage and check execution

Every applicable check from every skill associated with every declared item must run.
Each item-skill-check combination must receive exactly one terminal status:

- `passed`;
- `failed`;
- `not_applicable`, with a reason; or
- `unresolved`, with the blocking uncertainty or missing evidence.

Completion requires every declared item to:

1. map to at least one registered skill;
2. run every applicable check declared by those skills;
3. give each check a terminal status;
4. preserve its evidence and specialist conclusions; and
5. appear in the structured review bundle and the PPTX coverage summary.

Missing evidence, failed specialist work, or exhausted budgets must never produce an
implicit pass. Independent items should continue when another item is blocked. The whole
review stops only when missing or invalid input prevents trustworthy scoping or item
evaluation.

## 6. Evidence and findings

A finding must identify the affected catalogue item and checks, state its severity, and
cite reproducible evidence from authoritative inputs. Unsupported claims and fabricated
evidence are disqualifying review failures.

The review must prioritize correctness, requirement coverage, internal consistency,
evidence quality, and material risk. Style-only criticism is secondary unless presentation
quality affects correctness or usability.

Material findings require verification in an independent context that did not author the
finding. This may be another specialist agent or an isolated model invocation. A governing
skill may permit self-verification only for routine, low-risk checks.

Specialist results must include:

- the relevant item and check IDs;
- a scoped conclusion;
- evidence references;
- reasoning and confidence; and
- unresolved questions.

Original specialist conclusions and evidence must be preserved. The lead reviewer may
produce a clearly labelled reconciled finding when the evidence supports one, but must not
erase disagreement or manufacture consensus. An unresolved conflict remains
`unresolved`.

## 7. Specialist selection and orchestration boundary

The lead reviewer may select a specialist when an item:

- requires domain expertise;
- carries high impact;
- has ambiguous or conflicting evidence; or
- cannot otherwise be independently verified.

Routine, low-risk items do not require a specialist unless their applicable skill says
otherwise.

These requirements do not prescribe parallelism, a graph, or a single ReAct loop. The
next architecture stage must compare the advantages and disadvantages of the available
frameworks. Regardless of the selected framework, observable coverage, evidence,
verification, and delivery requirements remain unchanged.

## 8. Format validation and failure handling

The document structure must be validated before substantive review.

- Missing or malformed required content should produce an explicit format finding against
  the relevant catalogue item when reliable review remains possible.
- A document that cannot be parsed reliably must fail the review.
- The agent must not produce a completed deck from an untrustworthy parse.

Review and exploration budgets must be explicit and bounded at aggregate and item levels.
Retries must also be bounded. Budget exhaustion results in a disclosed `unresolved`
status, never a pass.

## 9. Authoritative review bundle

The complete structured review record is authoritative. It must include:

- the selected review mode and identified inputs;
- the hash of `REVIEW_AGENT.md`;
- the full item-skill-check coverage ledger;
- findings, evidence, severity, and verification results;
- specialist outputs and preserved disagreements;
- incidental observations;
- unresolved items and missing evidence;
- selected skill identities and content hashes; and
- budget and limitation disclosures.

The review bundle must be validated and sealed before presentation generation. A completed
review may contain explicitly disclosed unresolved items; completion means the required
work has a validated terminal disposition, not that every check passed.

## 10. PowerPoint delivery

The PPTX is the primary human-facing delivery, while the sealed structured bundle remains
the authoritative record. Presentation generation must consume only that sealed bundle
and must not introduce claims absent from it.

The main deck must communicate:

- the executive conclusion;
- scope and method;
- catalogue and check coverage;
- material findings;
- relevant specialist input and disagreement;
- unresolved questions and limitations; and
- recommended next actions.

An appendix must provide item-level results and stable IDs linking slides to the structured
record. Decision-critical information belongs in the main deck rather than only in the
appendix.

A supplied template or brand guide is authoritative. Otherwise, presentation generation
uses the controlled default design system. Visual styling must not change severity,
suppress unresolved items, or obscure evidence limitations.

Successful delivery requires:

- PPTX structural validation;
- rendered-slide visual inspection;
- readable content without clipping or overlap;
- traceability to sealed findings;
- editability where practical; and
- confirmation that no unsupported claim was introduced.

## 11. Completion milestones

The workflow has two distinct milestones:

1. `review_completed`: every required item-skill-check combination has a validated
   terminal disposition and the authoritative review bundle is sealed.
2. `delivery_completed`: the PPTX has been generated from that bundle and has passed
   structural and visual validation.

The overall request succeeds only at `delivery_completed`. A presentation-generation
failure must not invalidate, rewrite, or discard an already sealed review bundle.

## 12. Acceptance criteria

An implementation satisfies these requirements only when it can demonstrate that:

- all declared catalogue items are present in the coverage ledger;
- every applicable skill check has a justified terminal status;
- material conclusions have reproducible evidence and independent verification;
- missing evidence, disagreement, and budget exhaustion remain visible;
- neither model input nor reviewed content can select untrusted executable skills;
- malformed or unparseable documents cannot yield a misleading completion state;
- the sealed structured bundle remains authoritative and immutable during deck creation;
- the PPTX contains the required narrative and item-level traceability; and
- the delivered PPTX passes both structural and rendered visual validation.

Architecture selection, framework-specific control flow, and implementation planning are
intentionally outside this requirements document.
