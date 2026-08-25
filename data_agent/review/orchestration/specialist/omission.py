"""Bounded deterministic omission auditing and its single rescue request."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.runnables.config import RunnableConfig

from data_agent.review.domain.evidence import EvidenceReference, parse_locator
from data_agent.review.domain.verification import CandidateDispositionRecord, OmissionAuditResult
from data_agent.review.ingestion.evidence_validator import EvidenceValidator
from data_agent.review.orchestration.specialist.runtime import SpecialistRuntime
from data_agent.review.orchestration.specialist.scope import context_from_config
from data_agent.review.orchestration.specialist.state import SpecialistState, loads_finding
from data_agent.review.verification.omission import audit_omissions


def _source_backed_dispositions(
    state: SpecialistState, validator: EvidenceValidator
) -> list[dict[str, Any]]:
    """Retain disposition records, but only valid assigned evidence can cover a signal."""

    assigned = set(state.get("source_paths", []))
    records: list[dict[str, Any]] = []
    for raw in state.get("candidate_dispositions", []):
        try:
            record = CandidateDispositionRecord.model_validate(raw)
        except ValueError:
            continue
        valid: list[EvidenceReference] = []
        validation = validator.validate_references(record.evidence)
        valid_results = {result.locator: result for result in validation.results if result.valid}
        for reference in record.evidence:
            try:
                path = parse_locator(reference.locator).path
            except ValueError:
                continue
            if path in assigned and reference.locator in valid_results:
                valid.append(reference)
        records.append(record.model_copy(update={"evidence": valid}).model_dump(mode="json"))
    return records


def _audit_feedback(audit: OmissionAuditResult, *, max_chars: int) -> str:
    material = [
        {
            "candidate_id": candidate.candidate_id,
            "analysis_name": candidate.analysis_name,
            "kind": candidate.kind,
            "reason": candidate.reason,
            "evidence": [reference.locator for reference in candidate.evidence],
            "details": candidate.details,
        }
        for candidate in audit.uncovered_candidates
        if candidate.candidate_id in set(audit.material_candidate_ids)
    ]
    return (
        "Material deterministic candidates remain unaccounted for. Address each candidate "
        "with a new finding or a source-backed disposition.\n"
        + json.dumps(material, indent=2, default=str)[:max_chars]
    )


def audit_omission_candidates(
    runtime: SpecialistRuntime, state: SpecialistState, config: RunnableConfig
) -> dict[str, Any]:
    """Audit candidate coverage after settlement and request at most one rescue pass."""

    ctx = context_from_config(config)
    validator = EvidenceValidator.source_backed(ctx.source_root, ctx.manifest)
    verified = [loads_finding(raw) for raw in state.get("verified_findings", [])]
    rejected = [loads_finding(raw) for raw in state.get("rejected_findings", [])]
    unresolved = [loads_finding(raw) for raw in state.get("unresolved_findings", [])]
    dispositions = _source_backed_dispositions(state, validator)
    audit = audit_omissions(
        list(state.get("analyses", [])),
        verified,
        rejected_findings=rejected,
        unresolved_findings=unresolved,
        candidate_dispositions=dispositions,
        rescue_used=bool(state.get("omission_rescue_used", False)),
    )

    rescue_available = runtime.max_omission_rescue_rounds > 0
    should_rescue = (
        rescue_available
        and audit.rescue_required
        and not bool(state.get("omission_rescue_used", False))
    )
    if not rescue_available and audit.material_omission_exists:
        audit = audit.model_copy(
            update={
                "rescue_required": False,
                "unresolved_disclosures": [
                    *audit.unresolved_disclosures,
                    *(
                        f"deterministic candidate {candidate_id} remained materially omitted; "
                        "omission rescue was disabled"
                        for candidate_id in audit.material_candidate_ids
                    ),
                ],
            }
        )
    result: dict[str, Any] = {
        "omission_audit": audit.model_dump(mode="json"),
        "omission_rescue_requested": should_rescue,
        "loop_status": "running" if should_rescue else "complete",
    }
    if should_rescue:
        result.update(
            {
                "omission_rescue_used": True,
                "research_mode": "omission_rescue",
                "verifier_feedback": _audit_feedback(
                    audit, max_chars=runtime.max_revision_context_chars
                ),
                # Normal verification is settled.  Only the rescue model's new
                # finding/disposition is active in the next pass.
                "candidate_findings": [],
            }
        )
    elif state.get("omission_rescue_used"):
        # The rescue has already been spent.  Ensure a later checkpoint cannot
        # accidentally route back through a second rescue request.
        result.update(
            {
                "omission_rescue_requested": False,
                "research_mode": "settled",
            }
        )
    return result


def route_omission(state: SpecialistState) -> str:
    """Route one requested rescue to research, otherwise seal the report."""

    return "react_research" if state.get("omission_rescue_requested") else "finalize"


__all__ = ["audit_omission_candidates", "route_omission"]
