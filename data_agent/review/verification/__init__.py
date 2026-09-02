"""Verification contracts and deterministic helpers.

Provider-facing challenger and adjudicator implementations intentionally are
not imported from this package. Keeping this namespace pure prevents callers
that only need candidate IDs or evidence rules from importing orchestration
runtime contracts and avoids a specialist graph import cycle.
"""

from data_agent.review.verification.candidates import (
    assign_candidate_ids,
    candidate_fingerprint,
    candidate_locators,
    candidate_relationship_suggested,
    covered_candidate_ids,
    find_uncovered_candidates,
    finding_covers_candidate,
    link_finding_to_candidates,
    stable_candidate_id,
)
from data_agent.review.verification.evidence import (
    EvidenceGateError,
    assert_evidence_gate,
    build_evidence_gate,
    evaluate_evidence_gate,
    gate_evidence,
)
from data_agent.review.verification.omission import (
    audit_omissions,
    candidate_is_material,
    candidate_to_omission,
)
from data_agent.review.verification.reducer import (
    reduce_verification,
    reduce_verification_results,
)
from data_agent.review.verification.rules import (
    REQUIRED_CHALLENGE_TYPES,
    apply_pass_guards,
    can_pass,
    check_challenge_completeness,
    guard_adjudication,
    missing_challenge_types,
    required_challenge_types,
    validate_challenge_completeness,
)

__all__ = [
    "REQUIRED_CHALLENGE_TYPES",
    "EvidenceGateError",
    "apply_pass_guards",
    "assert_evidence_gate",
    "assign_candidate_ids",
    "audit_omissions",
    "build_evidence_gate",
    "can_pass",
    "candidate_fingerprint",
    "candidate_is_material",
    "candidate_locators",
    "candidate_relationship_suggested",
    "candidate_to_omission",
    "check_challenge_completeness",
    "covered_candidate_ids",
    "evaluate_evidence_gate",
    "find_uncovered_candidates",
    "finding_covers_candidate",
    "gate_evidence",
    "guard_adjudication",
    "link_finding_to_candidates",
    "missing_challenge_types",
    "reduce_verification",
    "reduce_verification_results",
    "required_challenge_types",
    "stable_candidate_id",
    "validate_challenge_completeness",
]
