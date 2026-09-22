# Post-trade control sources

Review assigned tabular control logs. The trusted parser recognizes date/event_date/
breach_date, product/product_family/instrument, severity/breach_severity,
approval/approved_by/approver/approval_ref, closed_date/resolution_date/resolved_date,
closure_days/resolution_days/days_to_close, status/workflow_status/breach_status, and
override/override_by/override_user. Inspect the actual columns and record missing fields.
Rows are control records, not trades or a complete trading population. Do not infer a
trade-level denominator, a binding SLA, approval authority or closure effectiveness
without a source-backed definition. Keep date parsing failures and unavailable fields
visible. Use exact row locators from trusted analysis and apply the policy reference
before interpreting recurrence, delays, approvals or severity.
