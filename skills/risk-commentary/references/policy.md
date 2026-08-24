# Risk Commentary Verifier Policy

Verify conclusions against the supplied final Markdown extracts only. Reopen every cited
line locator and prefer the quoted source record over a derived executive summary.

For each candidate, check whether the cited line contains the same event date, metric,
desk or perimeter, alert wording, comment, validation state, and scenario claimed by the
finding. Reproduce occurrence counts after deduplicating repeated copies of the same
evidence ID. Keep movement-review triggers separate from absolute-limit breaches and do
not independently confirm amounts, limits, timeliness, or closure from commentary alone.

Treat a trigger phrase and reassuring text in one quoted record as an internal-
consistency candidate. Check whether the phrases refer to different sub-books, fields,
or scopes before escalating. Treat `No data`, `pending`, and blank validation as evidence
or closure gaps, not proof that the underlying risk value or control process failed.

Apply `PASS` only when exact Markdown evidence supports the calibrated claim and its
population. Apply `REVISE` to fixable scope, locator, count, causality, or severity
problems; `REJECT` to unsupported conclusions; and `UNRESOLVED` when underlying source
data or a field dictionary is required and was not supplied.
