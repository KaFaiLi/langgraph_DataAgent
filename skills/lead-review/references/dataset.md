# Lead input contract

The lead consumes validated specialist reports and deterministic cross-report analysis.
Its input contains the immutable review period and desk context, findings with copied
source locators, verification status, unresolved items, clusters and contradictions.
The finding_identities map is keyed by assignment_id; use that key, never report_id,
when calling read_specialist_report. Follow all pages when additional report detail is
needed. Large data overviews and verification history may be omitted from the initial
projection and remain available in stored reports. Do not read raw source files.

Only passed or revised specialist findings provide verified support for final findings.
Unresolved findings remain explicit uncertainty; rejected findings cannot support final
conclusions. Empty verified support requires an empty key_findings list. The root calls
prepare_lead_review and apply_lead_verification and publishes through publish_review.
