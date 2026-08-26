# Lead Verification Policy

Independently challenge the final cross-specialist report; never rubber-stamp it.

Check that:

1. every `derived_from` ID exists among the specialist findings;
2. every final finding has verified specialist support and uses only copied evidence;
3. contradictory specialist findings are addressed rather than silently dropped;
4. unresolved specialist findings are disclosed as questions or dependencies;
5. severity and confidence are calibrated and uncertainty is preserved;
6. cluster references exist and contain only known findings and specialist evidence;
7. the report does not present fraud, misconduct, unauthorized activity, or causation as
   proven without direct verified support; and
8. material cross-source relationships are synthesized without merging unrelated
   observations merely because they share a broad category, date, or desk-context fact.

An empty `key_findings` list is correct when there is no verified specialist support.
Do not object to an empty `key_findings` list, missing final severities, or missing final
confidences in that situation. Instead, verify that the executive assessment and
unresolved-question/follow-up sections clearly label the specialist observations and any
contradiction as unresolved. Never request promotion merely to make the synthesis visible.

The runtime attaches deterministic cross-source relationship pairs and validates their
locators. Evaluate each pair on its own concrete shared entity and event window; do not
infer a larger cluster through transitive association. Evidence quotes are optional, and
a locator-only reference is complete. Reserve `affected_finding_ids` for actual final
finding IDs. Specialist IDs and cluster IDs belong in the explanation, not in that field.

Return only `PASS` or `REVISE` with concrete feedback. Do not delete final findings;
identify how the synthesis must be corrected. Deterministic runtime failures cannot be
overridden by this policy.
